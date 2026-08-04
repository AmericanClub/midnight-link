"""MidGate Payment Gateway API for first-party partner apps (e.g. midnight).

A partner app authenticates with a Partner API Key and asks MidGate to collect a
payment. MidGate creates a Mayar invoice (QRIS + e-wallet + VA on the hosted
checkout) and, once the payment is verified against Mayar, sends an HMAC-signed
`charge.paid` webhook back to the partner. The partner then credits its own users.

MidGate never trusts a "paid" claim from the client — every settlement is
re-verified with Mayar. Correlation is by `extraData.charge_id` + Mayar
`paymentLinkId`. All money flows into the operator's single Mayar account
(first-party only).
"""
import asyncio
import hashlib
import json
import logging
import secrets
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, Request, Query
from pydantic import BaseModel, Field

from ..db import db
from ..utils import now_iso
from ..url_safety import validate_public_url, UnsafeURLError
from .. import mayar
from .admin import require_admin
from .webhooks import sign, _post
from .wallet import _verify_paid

logger = logging.getLogger("midgate.partner_pay")

router = APIRouter(prefix="/api/pay", tags=["partner-pay"])
admin_router = APIRouter(prefix="/api/admin/partners", tags=["partner-pay-admin"])

MIN_AMOUNT = 10_000
MAX_AMOUNT = 10_000_000  # QRIS per-transaction ceiling (BI regulation)
_RETRY_DELAYS = (0, 3, 8)


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


def _charge_public(c: dict) -> dict:
    return {
        "id": c["id"], "reference_id": c.get("reference_id"), "amount": int(c.get("amount", 0)),
        "currency": c.get("currency", "IDR"), "status": c.get("status", "pending"),
        "checkout_url": c.get("checkout_url"), "description": c.get("description"),
        "created_at": c.get("created_at"), "paid_at": c.get("paid_at"),
        "expires_at": c.get("expires_at"),
    }


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
        "Content-Type": "application/json", "User-Agent": "MidGate-Pay/1.0",
        "X-MidGate-Event": "charge.paid", "X-MidGate-Delivery": delivery_id,
        "X-MidGate-Signature": f"t={ts},v1={sign(partner['webhook_secret'], ts, body)}",
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
    paid = await _verify_paid(charge.get("mayar_invoice_id"), charge.get("mayar_transaction_id"))
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
    email = (cust.email or "").strip() or "noreply@midgate.co"
    name = (cust.name or "").strip()
    if len(name) < 3:
        name = "Customer"
    mobile = "".join(ch for ch in (cust.mobile or "") if ch.isdigit())
    if len(mobile) < 10:
        mobile = "081200000000"
    try:
        inv = await mayar.create_invoice(
            name=name,
            email=email,
            mobile=mobile,
            amount=amount,
            description=payload.description or f"{partner['name']} payment {payload.reference_id}",
            redirect_url=payload.redirect_url or "https://midgate.co",
            extra_data={"charge_id": charge_id, "partner_id": partner["id"],
                        "reference_id": payload.reference_id,
                        "source": partner.get("source_tag") or partner["name"]},
        )
    except mayar.MayarError as e:
        logger.error("charge create failed partner=%s: %s", partner["id"], e)
        raise HTTPException(status_code=502, detail="Could not create payment. Please try again.")

    charge = {
        "id": charge_id, "partner_id": partner["id"], "reference_id": payload.reference_id,
        "amount": amount, "currency": "IDR", "status": "pending",
        "description": payload.description,
        "customer": {"name": cust.name, "email": cust.email, "mobile": cust.mobile},
        "mayar_invoice_id": inv.get("id"), "mayar_transaction_id": inv.get("transactionId"),
        "checkout_url": inv.get("link"), "expires_at": _ms_to_iso(inv.get("expiredAt")),
        "notified": False, "created_at": now_iso(), "paid_at": None,
    }
    await db.partner_charges.insert_one({**charge})
    return _charge_public(charge)


@router.get("/charges/{charge_id}")
async def get_charge(charge_id: str, partner=Depends(get_partner)):
    charge = await db.partner_charges.find_one(
        {"id": charge_id, "partner_id": partner["id"]}, {"_id": 0})
    if not charge:
        raise HTTPException(status_code=404, detail="Charge not found")
    if charge.get("status") == "pending":
        charge = await _settle(charge)
    return _charge_public(charge)


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
    charges = await db.partner_charges.find(
        {"partner_id": partner_id}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    deliveries = await db.partner_webhook_deliveries.find(
        {"partner_id": partner_id}, {"_id": 0, "payload": 0}).sort("created_at", -1).limit(100).to_list(100)
    return {"partner": {**_partner_public(p), "webhook_secret_set": bool(p.get("webhook_secret"))},
            "stats": await _partner_stats(partner_id),
            "charges": [_charge_public(c) | {"notified": c.get("notified", False)} for c in charges],
            "deliveries": deliveries}


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


@admin_router.delete("/{partner_id}")
async def delete_partner(partner_id: str, admin=Depends(require_admin)):
    res = await db.partners.delete_one({"id": partner_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Partner not found")
    await db.partner_charges.delete_many({"partner_id": partner_id})
    await db.partner_webhook_deliveries.delete_many({"partner_id": partner_id})
    return {"ok": True}
