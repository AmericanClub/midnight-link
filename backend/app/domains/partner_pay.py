"""Midnight Link Payment Gateway API for first-party partner apps (e.g. midnight).

A partner app authenticates with a Partner API Key and asks Midnight Link to collect a
payment. Midnight Link creates a Mayar invoice (QRIS + e-wallet + VA on the hosted
checkout) and, once the payment is verified against Mayar, sends an HMAC-signed
`charge.paid` webhook back to the partner. The partner then credits its own users.

Midnight Link never trusts a "paid" claim from the client — every settlement is
re-verified with Mayar. Correlation is by `extraData.charge_id` + Mayar
`paymentLinkId`. All money flows into the operator's single Mayar account
(first-party only).
"""
import asyncio
import hashlib
import json
import logging
import re
import secrets
import time
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Depends, Request, Query
from pydantic import BaseModel, Field

from ..db import db
from ..utils import now_iso
from ..config import settings
from ..url_safety import validate_public_url, UnsafeURLError
from .. import mayar, klikqris
from .admin import require_admin
from .webhooks import sign, _post
from .wallet import verify_paid_record, create_gateway_payment

logger = logging.getLogger("midgate.partner_pay")

router = APIRouter(prefix="/api/pay", tags=["partner-pay"])
admin_router = APIRouter(prefix="/api/admin/partners", tags=["partner-pay-admin"])

MIN_AMOUNT = 10_000
MAX_AMOUNT = 10_000_000  # QRIS per-transaction ceiling (BI regulation)
_RETRY_DELAYS = (0, 3, 8)
_EXPIRE_GRACE_S = 900       # flip pending→expired 15 min AFTER the gateway expiry (covers late settlement)
_NO_EXPIRY_TTL_S = 86_400   # if a charge has no expires_at, expire it 24h after creation


# ------------------------------ helpers ---------------------------------- #
def _gen_key() -> str:
    return "mgpay_live_" + secrets.token_hex(24)


def _gen_secret() -> str:
    return "mgwhsec_" + secrets.token_hex(24)


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _ms_to_iso(ms) -> str | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


def _parse_dt(s) -> datetime | None:
    """Tolerant ISO / 'YYYY-MM-DD HH:MM:SS' parser → aware UTC datetime (None on failure)."""
    if not s:
        return None
    try:
        t = str(s).strip().replace("Z", "+00:00")
        if "T" not in t and " " in t:
            t = t.replace(" ", "T", 1)
        dt = datetime.fromisoformat(t)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _is_stale(charge: dict) -> bool:
    """A pending charge is stale once past its gateway expiry (+grace), or 24h after creation
    when no expiry was stored. Purely clock-based — no gateway call."""
    exp = _parse_dt(charge.get("expires_at"))
    basis = (exp + timedelta(seconds=_EXPIRE_GRACE_S)) if exp else None
    if not basis:
        created = _parse_dt(charge.get("created_at"))
        basis = (created + timedelta(seconds=_NO_EXPIRY_TTL_S)) if created else None
    return bool(basis and datetime.now(timezone.utc) > basis)


async def _expire_if_stale(charge: dict) -> dict:
    if charge.get("status") == "pending" and _is_stale(charge):
        await db.partner_charges.update_one(
            {"id": charge["id"], "status": "pending"},
            {"$set": {"status": "expired", "expired_at": now_iso()}})
        return {**charge, "status": "expired"}
    return charge


async def _sweep_expired(partner_id: str) -> int:
    """Flip all overdue pending charges for a partner to expired (so lists/stats/filters are correct).
    A late-but-valid payment can still recover: the gateway webhook re-settles expired→paid,
    and admin Re-check re-verifies expired charges."""
    pend = await db.partner_charges.find(
        {"partner_id": partner_id, "status": "pending"},
        {"_id": 0, "id": 1, "expires_at": 1, "created_at": 1}).to_list(2000)
    stale = [c["id"] for c in pend if _is_stale(c)]
    if stale:
        await db.partner_charges.update_many(
            {"id": {"$in": stale}, "status": "pending"},
            {"$set": {"status": "expired", "expired_at": now_iso()}})
    return len(stale)



def _charge_public(c: dict, *, include_qr: bool = False) -> dict:
    out = {
        "id": c["id"], "reference_id": c.get("reference_id"), "amount": int(c.get("amount", 0)),
        "currency": c.get("currency", "IDR"), "status": c.get("status", "pending"),
        "gateway": c.get("gateway", "mayar"),
        "checkout_url": c.get("checkout_url"), "qris_url": c.get("qris_url"),
        "pay_amount": int(c.get("pay_amount") or c.get("amount", 0)),
        "description": c.get("description"),
        "created_at": c.get("created_at"), "paid_at": c.get("paid_at"),
        "expires_at": c.get("expires_at"),
    }
    if include_qr:
        # Raw QR (base64 image + hosted url) so the partner app can render the QRIS
        # natively in-app (like Midnight Link's own billing). null for Mayar (hosted checkout only).
        out["qris_image"] = c.get("qris_image")
    return out


async def get_partner(request: Request) -> dict:
    auth = request.headers.get("authorization", "")
    key = auth[7:].strip() if auth.lower().startswith("bearer ") else request.headers.get("x-partner-key")
    if not key:
        raise HTTPException(status_code=401, detail="Missing partner API key")
    p = await db.partners.find_one({"key_hash": _hash(key.strip()), "active": True}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=401, detail="Invalid or inactive partner API key")
    return p


async def _deliver_charge_paid(partner: dict, charge: dict):
    """HMAC-signed `charge.paid` webhook to the partner, with retry + delivery log."""
    if not partner.get("webhook_url") or not partner.get("webhook_secret"):
        return
    delivery_id = str(uuid.uuid4())
    payload = {
        "id": delivery_id, "event": "charge.paid", "created_at": now_iso(),
        "data": {
            "charge_id": charge["id"], "reference_id": charge.get("reference_id"),
            "amount": int(charge.get("amount", 0)), "currency": charge.get("currency", "IDR"),
            "status": "paid", "paid_at": charge.get("paid_at"),
            "customer": charge.get("customer") or {},
        },
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    ts = str(int(time.time()))
    headers = {
        "Content-Type": "application/json", "User-Agent": "MidnightLink-Pay/1.0",
        "X-MidnightLink-Event": "charge.paid", "X-MidnightLink-Delivery": delivery_id,
        "X-MidnightLink-Signature": f"t={ts},v1={sign(partner['webhook_secret'], ts, body)}",
    }
    status, code, error, attempts = "failed", None, None, 0
    try:
        await asyncio.to_thread(validate_public_url, partner["webhook_url"])
        blocked = None
    except UnsafeURLError as e:
        blocked = str(e)
    if blocked:
        error = f"Blocked: {blocked}"
    else:
        for delay in _RETRY_DELAYS:
            if delay:
                await asyncio.sleep(delay)
            attempts += 1
            try:
                resp = await _post(partner["webhook_url"], body, headers)
                code = resp.status_code
                if 200 <= resp.status_code < 300:
                    status, error = "success", None
                    break
                error = f"HTTP {resp.status_code}"
            except Exception as e:  # noqa: BLE001
                error = str(e)[:300]
    await db.partner_webhook_deliveries.insert_one({
        "id": delivery_id, "partner_id": partner["id"], "charge_id": charge["id"],
        "event": "charge.paid", "url": partner["webhook_url"], "status": status,
        "status_code": code, "attempts": attempts, "error": error,
        "payload": payload, "created_at": now_iso(),
    })
    await db.partner_charges.update_one(
        {"id": charge["id"]},
        {"$set": {"notified": status == "success", "last_delivery_status": status,
                  "last_delivery_at": now_iso()}})


async def _settle(charge: dict, *, deliver: bool = True) -> dict:
    """Verify with Mayar; on first confirmation flip to paid and notify the partner."""
    if charge.get("status") == "paid":
        return charge
    paid = await verify_paid_record(charge)
    if not paid:
        return charge
    claimed = await db.partner_charges.find_one_and_update(
        {"id": charge["id"], "status": {"$ne": "paid"}},
        {"$set": {"status": "paid", "paid_at": now_iso()}})
    if not claimed:
        return await db.partner_charges.find_one({"id": charge["id"]}, {"_id": 0})
    fresh = await db.partner_charges.find_one({"id": charge["id"]}, {"_id": 0})
    logger.info("partner charge paid id=%s partner=%s ref=%s amount=%s",
                fresh["id"], fresh["partner_id"], fresh.get("reference_id"), fresh.get("amount"))
    if deliver:
        partner = await db.partners.find_one({"id": fresh["partner_id"]}, {"_id": 0})
        if partner:
            asyncio.create_task(_deliver_charge_paid(partner, fresh))
    return fresh


async def handle_mayar_event(event: str | None, data: dict) -> bool:
    """Called by the shared Mayar webhook when a top-up match isn't found."""
    if event and event != "payment.received":
        return False
    extra = data.get("extraData") or {}
    charge = None
    if extra.get("charge_id"):
        charge = await db.partner_charges.find_one({"id": extra["charge_id"]}, {"_id": 0})
    if not charge:
        cand = [c for c in (data.get("id"), data.get("transactionId"),
                            data.get("paymentLinkId"), data.get("paymentLinkTransactionId")) if c]
        if cand:
            charge = await db.partner_charges.find_one(
                {"$or": [{"mayar_invoice_id": {"$in": cand}},
                         {"mayar_transaction_id": {"$in": cand}}]}, {"_id": 0})
    if not charge:
        return False
    await _settle(charge)
    return True


async def handle_klik_event(order_id: str, payload: dict) -> bool:
    """Called by the KlikQRIS webhook when a top-up match isn't found."""
    charge = await db.partner_charges.find_one({"klik_order_id": order_id}, {"_id": 0})
    if not charge:
        return False
    if charge.get("klik_signature") and payload.get("signature") \
            and charge["klik_signature"] != payload.get("signature"):
        logger.warning("KlikQRIS partner webhook signature mismatch order=%s", order_id)
    await _settle(charge)
    return True


# --------------------------- partner-facing API -------------------------- #
class Customer(BaseModel):
    name: str | None = None
    email: str | None = None
    mobile: str | None = None


class ChargeCreate(BaseModel):
    amount: int = Field(gt=0)
    reference_id: str = Field(min_length=1, max_length=120)
    customer: Customer = Field(default_factory=Customer)
    description: str | None = Field(default=None, max_length=200)
    redirect_url: str | None = None


@router.get("/ping")
async def ping(partner=Depends(get_partner)):
    """Lightweight key check for a partner's 'Test Connection' button."""
    return {"ok": True, "partner": partner["name"],
            "min_amount": MIN_AMOUNT, "max_amount": MAX_AMOUNT, "currency": "IDR"}


@router.post("/charges")
async def create_charge(payload: ChargeCreate, partner=Depends(get_partner)):
    amount = int(payload.amount)
    if amount < MIN_AMOUNT:
        raise HTTPException(status_code=400, detail=f"Minimum amount is Rp{MIN_AMOUNT:,}")
    if amount > MAX_AMOUNT:
        raise HTTPException(status_code=400, detail=f"Maximum QRIS amount is Rp{MAX_AMOUNT:,}")

    existing = await db.partner_charges.find_one(
        {"partner_id": partner["id"], "reference_id": payload.reference_id}, {"_id": 0})
    if existing:
        if existing.get("status") == "pending":
            existing = await _settle(existing)
        return _charge_public(existing)

    charge_id = str(uuid.uuid4())
    cust = payload.customer
    email = (cust.email or "").strip() or "noreply@midnightlink.link"
    name = (cust.name or "").strip()
    if len(name) < 3:
        name = "Customer"
    mobile = "".join(ch for ch in (cust.mobile or "") if ch.isdigit())
    if len(mobile) < 10:
        mobile = "081200000000"
    callback_url = f"{settings.FRONTEND_URL}/api/wallet/klikqris/webhook"
    try:
        pay = await create_gateway_payment(
            order_id=charge_id, amount=amount,
            description=payload.description or f"{partner['name']} payment {payload.reference_id}",
            name=name, email=email, mobile=mobile,
            redirect_url=payload.redirect_url or "https://midnightlink.link",
            callback_url=callback_url,
            extra_data={"charge_id": charge_id, "partner_id": partner["id"],
                        "reference_id": payload.reference_id,
                        "source": partner.get("source_tag") or partner["name"]},
        )
    except (mayar.MayarError, klikqris.KlikqrisError) as e:
        logger.error("charge create failed partner=%s: %s", partner["id"], e)
        raise HTTPException(status_code=502, detail="Could not create payment. Please try again.")

    expires_at = _ms_to_iso(pay["expires_at"]) if pay["gateway"] == "mayar" else pay["expires_at"]
    charge = {
        "id": charge_id, "partner_id": partner["id"], "reference_id": payload.reference_id,
        "amount": amount, "currency": "IDR", "status": "pending",
        "description": payload.description, "gateway": pay["gateway"],
        "customer": {"name": cust.name, "email": cust.email, "mobile": cust.mobile},
        "mayar_invoice_id": pay["provider_ref"] if pay["gateway"] == "mayar" else None,
        "mayar_transaction_id": pay["provider_txn_id"],
        "klik_order_id": pay["provider_ref"] if pay["gateway"] == "klikqris" else None,
        "klik_signature": pay["signature"],
        "checkout_url": pay["checkout_url"], "qris_url": pay["qris_url"],
        "qris_image": pay.get("qris_image"),
        "pay_amount": pay["pay_amount"], "expires_at": expires_at,
        "notified": False, "created_at": now_iso(), "paid_at": None,
    }
    await db.partner_charges.insert_one({**charge})
    return _charge_public(charge, include_qr=True)


@router.get("/charges/{charge_id}")
async def get_charge(charge_id: str, partner=Depends(get_partner)):
    charge = await db.partner_charges.find_one(
        {"id": charge_id, "partner_id": partner["id"]}, {"_id": 0})
    if not charge:
        raise HTTPException(status_code=404, detail="Charge not found")
    if charge.get("status") == "pending":
        charge = await _settle(charge)
        charge = await _expire_if_stale(charge)
    return _charge_public(charge, include_qr=True)


# --------------------------- admin management ---------------------------- #
class PartnerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    webhook_url: str | None = None
    source_tag: str | None = Field(default=None, max_length=40)


class PartnerUpdate(BaseModel):
    webhook_url: str | None = None
    active: bool | None = None
    name: str | None = None


def _partner_public(p: dict) -> dict:
    return {
        "id": p["id"], "name": p["name"], "active": p.get("active", True),
        "webhook_url": p.get("webhook_url"), "source_tag": p.get("source_tag"),
        "key_prefix": p.get("key_prefix"), "key_last4": p.get("key_last4"),
        "created_at": p.get("created_at"),
    }


def _validate_hook(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return validate_public_url(url)
    except UnsafeURLError as e:
        raise HTTPException(status_code=400, detail=str(e))


async def _partner_stats(partner_id: str) -> dict:
    rows = await db.partner_charges.aggregate([
        {"$match": {"partner_id": partner_id}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}, "amount": {"$sum": "$amount"}}},
    ]).to_list(20)
    paid = next((r for r in rows if r["_id"] == "paid"), {})
    total = sum(r["count"] for r in rows)
    return {"charges": total, "paid_count": int(paid.get("count", 0)),
            "paid_amount": int(paid.get("amount", 0))}


@admin_router.get("")
async def list_partners(admin=Depends(require_admin)):
    rows = await db.partners.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    items = []
    for p in rows:
        items.append({**_partner_public(p), **await _partner_stats(p["id"])})
    return {"items": items}


@admin_router.post("")
async def create_partner(payload: PartnerCreate, admin=Depends(require_admin)):
    url = _validate_hook(payload.webhook_url)
    key, secret = _gen_key(), _gen_secret()
    doc = {
        "id": str(uuid.uuid4()), "name": payload.name.strip(),
        "source_tag": (payload.source_tag or payload.name).strip().lower().replace(" ", "-")[:40],
        "webhook_url": url, "webhook_secret": secret,
        "key_hash": _hash(key), "key_prefix": key[:16], "key_last4": key[-4:],
        "active": True, "created_at": now_iso(), "created_by": admin["email"],
    }
    await db.partners.insert_one({**doc})
    # Full key + secret are shown exactly once.
    return {**_partner_public(doc), "api_key": key, "webhook_secret": secret}


@admin_router.get("/{partner_id}")
async def partner_detail(partner_id: str, admin=Depends(require_admin)):
    p = await db.partners.find_one({"id": partner_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Partner not found")
    await _sweep_expired(partner_id)
    return {"partner": {**_partner_public(p), "webhook_secret_set": bool(p.get("webhook_secret"))},
            "stats": await _partner_stats(partner_id)}


async def _paginate(coll, flt, page, limit, projection=None):
    page = max(1, int(page))
    limit = min(max(1, int(limit)), 100)
    total = await coll.count_documents(flt)
    items = await coll.find(flt, projection or {"_id": 0}).sort("created_at", -1) \
        .skip((page - 1) * limit).limit(limit).to_list(limit)
    return {"items": items, "total": total, "page": page,
            "pages": max(1, (total + limit - 1) // limit)}


@admin_router.get("/{partner_id}/charges")
async def partner_charges(partner_id: str, admin=Depends(require_admin),
                          status: str | None = Query(None), q: str | None = Query(None),
                          page: int = Query(1), limit: int = Query(20)):
    await _sweep_expired(partner_id)
    flt = {"partner_id": partner_id}
    if status in ("paid", "pending", "expired"):
        flt["status"] = status
    if q and q.strip():
        rx = {"$regex": re.escape(q.strip()[:120]), "$options": "i"}
        flt["$or"] = [{"reference_id": rx}, {"customer.name": rx},
                      {"customer.email": rx}, {"customer.mobile": rx},
                      {"id": rx}, {"klik_order_id": rx}, {"mayar_invoice_id": rx}]
    res = await _paginate(db.partner_charges, flt, page, limit)
    res["items"] = [_charge_public(c) | {
        "notified": c.get("notified", False),
        "customer": c.get("customer") or {},
        "gateway_order_id": c.get("klik_order_id") or c.get("mayar_invoice_id") or c.get("id"),
        "manual_settle": c.get("manual_settle"),
    } for c in res["items"]]
    return res


@admin_router.get("/{partner_id}/deliveries")
async def partner_deliveries(partner_id: str, admin=Depends(require_admin),
                             status: str | None = Query(None),
                             page: int = Query(1), limit: int = Query(20)):
    flt = {"partner_id": partner_id}
    if status in ("success", "failed"):
        flt["status"] = status
    return await _paginate(db.partner_webhook_deliveries, flt, page, limit,
                           projection={"_id": 0, "payload": 0})


@admin_router.patch("/{partner_id}")
async def update_partner(partner_id: str, payload: PartnerUpdate, admin=Depends(require_admin)):
    p = await db.partners.find_one({"id": partner_id}, {"_id": 0, "id": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Partner not found")
    updates = {"updated_at": now_iso()}
    data = payload.model_dump(exclude_unset=True)
    if "webhook_url" in data:
        updates["webhook_url"] = _validate_hook(data["webhook_url"])
    if "active" in data and data["active"] is not None:
        updates["active"] = bool(data["active"])
    if data.get("name"):
        updates["name"] = data["name"].strip()
    await db.partners.update_one({"id": partner_id}, {"$set": updates})
    return _partner_public(await db.partners.find_one({"id": partner_id}, {"_id": 0}))


@admin_router.post("/{partner_id}/rotate-key")
async def rotate_key(partner_id: str, admin=Depends(require_admin)):
    p = await db.partners.find_one({"id": partner_id}, {"_id": 0, "id": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Partner not found")
    key = _gen_key()
    await db.partners.update_one({"id": partner_id}, {"$set": {
        "key_hash": _hash(key), "key_prefix": key[:16], "key_last4": key[-4:], "updated_at": now_iso()}})
    return {"api_key": key}


@admin_router.post("/{partner_id}/rotate-secret")
async def rotate_secret(partner_id: str, admin=Depends(require_admin)):
    p = await db.partners.find_one({"id": partner_id}, {"_id": 0, "id": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Partner not found")
    secret = _gen_secret()
    await db.partners.update_one({"id": partner_id}, {"$set": {"webhook_secret": secret, "updated_at": now_iso()}})
    return {"webhook_secret": secret}


@admin_router.post("/{partner_id}/charges/{charge_id}/resend")
async def resend_webhook(partner_id: str, charge_id: str, admin=Depends(require_admin)):
    p = await db.partners.find_one({"id": partner_id}, {"_id": 0})
    charge = await db.partner_charges.find_one(
        {"id": charge_id, "partner_id": partner_id}, {"_id": 0})
    if not p or not charge:
        raise HTTPException(status_code=404, detail="Not found")
    if charge.get("status") != "paid":
        raise HTTPException(status_code=400, detail="Only paid charges can be resent")
    await _deliver_charge_paid(p, charge)
    return {"ok": True}


@admin_router.post("/{partner_id}/charges/{charge_id}/recheck")
async def recheck_charge(partner_id: str, charge_id: str, admin=Depends(require_admin)):
    """Re-verify a pending OR expired charge against the gateway (KlikQRIS/Mayar) right now.
    If the gateway finally reports paid, it auto-settles + fires the charge.paid webhook
    (so a late-but-valid payment on an already-expired charge is still recoverable)."""
    charge = await db.partner_charges.find_one(
        {"id": charge_id, "partner_id": partner_id}, {"_id": 0})
    if not charge:
        raise HTTPException(status_code=404, detail="Charge not found")
    before = charge.get("status")
    if before in ("pending", "expired"):
        charge = await _settle(charge)
    became_paid = charge.get("status") == "paid" and before != "paid"
    return {"status": charge.get("status"), "became_paid": became_paid,
            "charge": _charge_public(charge)}


class MarkPaid(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


@admin_router.post("/{partner_id}/charges/{charge_id}/mark-paid")
async def mark_charge_paid(partner_id: str, charge_id: str, payload: MarkPaid,
                           admin=Depends(require_admin)):
    """MANUAL override: flip a charge to paid and deliver the signed charge.paid webhook.
    Use only after confirming the funds actually settled (e.g. gateway marked EXPIRED
    but the customer paid). Requires a reason and is logged."""
    partner = await db.partners.find_one({"id": partner_id}, {"_id": 0})
    charge = await db.partner_charges.find_one(
        {"id": charge_id, "partner_id": partner_id}, {"_id": 0})
    if not partner or not charge:
        raise HTTPException(status_code=404, detail="Not found")
    if charge.get("status") == "paid":
        raise HTTPException(status_code=400, detail="Charge is already paid")
    reason = payload.reason.strip()
    claimed = await db.partner_charges.find_one_and_update(
        {"id": charge_id, "status": {"$ne": "paid"}},
        {"$set": {"status": "paid", "paid_at": now_iso(),
                  "manual_settle": {"by": admin["email"], "reason": reason, "at": now_iso()}}})
    fresh = await db.partner_charges.find_one({"id": charge_id}, {"_id": 0})
    if not claimed:
        return _charge_public(fresh)
    logger.warning("partner charge MANUAL mark-paid id=%s partner=%s by=%s reason=%r",
                   charge_id, partner_id, admin["email"], reason)
    asyncio.create_task(_deliver_charge_paid(partner, fresh))
    return _charge_public(fresh)


@admin_router.delete("/{partner_id}")
async def delete_partner(partner_id: str, admin=Depends(require_admin)):
    res = await db.partners.delete_one({"id": partner_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Partner not found")
    await db.partner_charges.delete_many({"partner_id": partner_id})
    await db.partner_webhook_deliveries.delete_many({"partner_id": partner_id})
    return {"ok": True}



# --------------------------- reconciliation ----------------------------- #
_RECONCILE_INTERVAL_S = 60


async def reconcile_pending(limit: int = 40) -> dict:
    """Safety-net reconciliation: actively re-verify recent pending (and briefly-expired)
    partner charges + wallet top-ups against the gateway status API and settle the paid ones.
    Covers webhooks that were blocked, missed, or delivered before the gateway had synced —
    so operators no longer need to press Re-check manually. Uses the same verified settle path."""
    now = datetime.now(timezone.utc)
    pend_cut = (now - timedelta(hours=6)).isoformat()
    exp_cut = (now - timedelta(minutes=60)).isoformat()
    q = {"$or": [
        {"status": "pending", "created_at": {"$gte": pend_cut}},
        {"status": "expired", "created_at": {"$gte": exp_cut}},
    ]}
    charges = await db.partner_charges.find(q, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    settled = 0
    for c in charges:
        before = c.get("status")
        try:
            res = await _settle(c)
            if res.get("status") == "paid" and before != "paid":
                settled += 1
        except Exception as e:  # noqa: BLE001
            logger.warning("reconcile charge %s failed: %s", c.get("id"), e)
    topups = 0
    try:
        from .wallet import reconcile_topups
        topups = await reconcile_topups(limit=limit)
    except Exception as e:  # noqa: BLE001
        logger.warning("reconcile topups failed: %s", e)
    if settled or topups:
        logger.info("reconciler settled %d partner charge(s), %d top-up(s)", settled, topups)
    return {"partner_settled": settled, "topups_settled": topups, "checked": len(charges)}


async def run_reconciler(interval: int = _RECONCILE_INTERVAL_S):
    """Background loop started on app startup."""
    logger.info("payment reconciler started (every %ss)", interval)
    while True:
        try:
            await reconcile_pending()
        except Exception as e:  # noqa: BLE001
            logger.warning("reconciler cycle error: %s", e)
        await asyncio.sleep(interval)
