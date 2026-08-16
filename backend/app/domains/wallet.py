"""Credit wallet + immutable ledger, funded by real Mayar top-ups.

Model: the Rupiah-per-credit rate is admin-configurable (Payments console). Top up the
wallet via Mayar (QRIS/e-wallet/VA) and spend credits on plans; plan Rupiah prices are
converted to credits at the same rate so pricing stays consistent. Credits never expire.
All balance changes append an immutable ledger entry. Payments are only credited after
server-side verification with Mayar (idempotent), so forged webhooks cannot grant credits.
"""
import hmac
import json
import logging
import math
import uuid

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from ..db import db
from ..utils import now_iso
from ..config import settings
from .. import mayar, klikqris
from ..security import get_current_user
from .billing import get_billing_workspace, PLAN_MAP, activate_plan_for_workspace
from .admin import require_admin

router = APIRouter(prefix="/api/wallet", tags=["wallet"])
logger = logging.getLogger("midgate.wallet")

MIN_TOPUP = 10_000            # Rp — default minimum (admin-configurable)
MAX_TOPUP = 100_000_000       # Rp — sane upper bound to catch typos/abuse
DEFAULT_RUPIAH_PER_CREDIT = 1000
DEFAULT_REQ_PER_CREDIT = 333   # overflow: ~Rp3 per request at Rp1000/credit
PAID_STATUSES = {"paid", "settled", "success"}
DEFAULT_TOPUP_DISABLED_MSG = "Payments are temporarily unavailable. Please try again later."


# --------------------- payment (top-up) master switch -------------------- #
async def get_payment_settings() -> dict:
    doc = await db.platform_settings.find_one({"_id": "payments"}) or {}
    return {
        "topup_enabled": doc.get("topup_enabled", True),
        "topup_disabled_message": doc.get("topup_disabled_message") or DEFAULT_TOPUP_DISABLED_MSG,
        "updated_at": doc.get("updated_at"),
        "updated_by": doc.get("updated_by"),
    }


async def set_payment_settings(*, topup_enabled=None, topup_disabled_message=None,
                               admin_email=None) -> dict:
    updates = {"updated_at": now_iso()}
    if topup_enabled is not None:
        updates["topup_enabled"] = bool(topup_enabled)
    if topup_disabled_message is not None:
        updates["topup_disabled_message"] = (topup_disabled_message.strip()[:300]
                                             or DEFAULT_TOPUP_DISABLED_MSG)
    if admin_email:
        updates["updated_by"] = admin_email
    await db.platform_settings.update_one({"_id": "payments"}, {"$set": updates}, upsert=True)
    return await get_payment_settings()


# --------------------- credit conversion settings ------------------------ #
async def get_credit_settings() -> dict:
    doc = await db.platform_settings.find_one({"_id": "credits"}) or {}
    rpc = int(doc.get("rupiah_per_credit") or DEFAULT_RUPIAH_PER_CREDIT)
    if rpc < 1:
        rpc = 1
    return {
        "rupiah_per_credit": rpc,
        "bonus_percent": float(doc.get("bonus_percent") or 0),
        "min_topup": int(doc.get("min_topup") or MIN_TOPUP),
        "requests_per_credit": int(doc.get("requests_per_credit") or DEFAULT_REQ_PER_CREDIT),
        "updated_at": doc.get("updated_at"),
        "updated_by": doc.get("updated_by"),
    }


async def set_credit_settings(*, rupiah_per_credit=None, bonus_percent=None,
                              min_topup=None, requests_per_credit=None, admin_email=None) -> dict:
    updates = {"updated_at": now_iso()}
    if rupiah_per_credit is not None:
        updates["rupiah_per_credit"] = max(1, int(rupiah_per_credit))
    if bonus_percent is not None:
        updates["bonus_percent"] = max(0.0, min(float(bonus_percent), 1000.0))
    if min_topup is not None:
        updates["min_topup"] = max(0, int(min_topup))
    if requests_per_credit is not None:
        updates["requests_per_credit"] = max(1, int(requests_per_credit))
    if admin_email:
        updates["updated_by"] = admin_email
    await db.platform_settings.update_one({"_id": "credits"}, {"$set": updates}, upsert=True)
    return await get_credit_settings()


def credits_for_amount(amount_rp: int, cs: dict):
    """Returns (total_credits, base_credits, bonus_credits) for a top-up amount."""
    base = int(amount_rp) // cs["rupiah_per_credit"]
    bonus = int(base * cs["bonus_percent"] / 100)
    return base + bonus, base, bonus


def credits_for_price(price_rp: int, cs: dict) -> int:
    """Credits needed to buy something priced in Rupiah (rounded up)."""
    return int(math.ceil(int(price_rp) / cs["rupiah_per_credit"]))


# --------------------- request metering (per click) ---------------------- #
async def _mark_quota_exhausted(workspace_id: str, now: str):
    await db.workspaces.update_one(
        {"id": workspace_id, "quota_exhausted": {"$ne": True}},
        {"$set": {"quota_exhausted": True, "quota_exhausted_at": now}},
    )


async def consume_request(workspace_id: str) -> dict:
    """Consume 1 Request for a click. Order: active plan quota -> pre-converted
    overflow -> convert 1 credit into an overflow chunk. Returns protection flag.
    When nothing is left (b1 soft): allow the click but pause protection + flag owner."""
    now = now_iso()
    # 1) active plan quota
    doc = await db.workspaces.find_one_and_update(
        {"id": workspace_id, "pass_expires_at": {"$gt": now},
         "$expr": {"$lt": ["$pass_requests_used", "$pass_requests_included"]}},
        {"$inc": {"pass_requests_used": 1}}, return_document=ReturnDocument.AFTER,
    )
    if doc:
        return {"protection": True, "source": "plan"}
    # 2) pre-converted overflow bucket
    w = await db.wallets.find_one_and_update(
        {"workspace_id": workspace_id, "req_overflow": {"$gte": 1}},
        {"$inc": {"req_overflow": -1}}, return_document=ReturnDocument.AFTER,
    )
    if w:
        return {"protection": True, "source": "credit"}
    # 3) convert 1 credit -> overflow chunk (this click consumes the first of the chunk)
    cs = await get_credit_settings()
    rpc = max(1, int(cs.get("requests_per_credit", DEFAULT_REQ_PER_CREDIT)))
    conv = await db.wallets.find_one_and_update(
        {"workspace_id": workspace_id, "balance": {"$gte": 1}},
        {"$inc": {"balance": -1, "req_overflow": rpc - 1}, "$set": {"updated_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    if conv:
        await db.wallet_ledger.insert_one({
            "id": str(uuid.uuid4()), "workspace_id": workspace_id, "type": "spend",
            "amount": -1, "balance_after": int(conv.get("balance", 0)),
            "description": f"Auto-converted 1 credit → {rpc:,} requests (overflow)",
            "ref": None, "actor": "system", "created_at": now,
        })
        return {"protection": True, "source": "credit"}
    # 4) fully exhausted -> soft pass-through
    await _mark_quota_exhausted(workspace_id, now)
    return {"protection": False, "source": "none"}


# --------------------- payment gateway (Mayar) config -------------------- #
def _clean_base_url(raw, *, mayar: bool = False) -> str:
    """Normalize a pasted API base URL. For Mayar, any non-API host (PayMe link like
    mayar.to/<acct>, the web.mayar.id dashboard, or an account *.myr.id subdomain) is forced
    to the real API host https://api.mayar.id/hl/v1. '' means reset to default."""
    b = str(raw or "").strip()
    if not b:
        return ""
    if "//" in b:
        b = b.split("//", 1)[1]  # drop any (possibly typo'd) scheme prefix
    b = b.strip().strip("/")
    if not b:
        return ""
    if mayar:
        host = b.split("/", 1)[0].lower()
        valid_api_hosts = {"api.mayar.id", "api.mayar.io", "api.mayar.club"}
        if host not in valid_api_hosts:
            return "https://api.mayar.id/hl/v1"  # wrong host (PayMe/dashboard) → force prod API
        if "/hl/v" not in b:
            b = host + "/hl/v1"
        return "https://" + b
    return "https://" + b


async def set_gateway_config(*, api_key=None, webhook_token=None, base_url=None,
                             admin_email=None) -> dict:
    updates = {"updated_at": now_iso(), "provider": "mayar"}
    unset = {}
    if api_key is not None and str(api_key).strip():
        updates["api_key"] = str(api_key).strip()
    if webhook_token is not None and str(webhook_token).strip():
        updates["webhook_token"] = str(webhook_token).strip()
    if base_url is not None:
        cleaned = _clean_base_url(base_url, mayar=True)
        if cleaned:
            updates["base_url"] = cleaned
        else:
            unset["base_url"] = ""  # blank = reset to the production default
    if admin_email:
        updates["updated_by"] = admin_email
    op = {"$set": updates}
    if unset:
        op["$unset"] = unset
    await db.platform_settings.update_one({"_id": "gateway"}, op, upsert=True)
    mayar.invalidate_creds()
    return await mayar.gateway_status()


# --------------------- active gateway (single IDR gateway) --------------- #
async def get_active_gateway() -> str:
    doc = await db.platform_settings.find_one({"_id": "payments"}) or {}
    g = (doc.get("active_gateway") or "mayar").lower()
    return g if g in ("mayar", "klikqris") else "mayar"


async def set_active_gateway(name: str, admin_email: str | None = None) -> str:
    name = (name or "").lower()
    if name not in ("mayar", "klikqris"):
        raise HTTPException(status_code=400, detail="Unknown gateway")
    updates = {"active_gateway": name, "updated_at": now_iso()}
    if admin_email:
        updates["updated_by"] = admin_email
    await db.platform_settings.update_one({"_id": "payments"}, {"$set": updates}, upsert=True)
    return name


async def set_klikqris_config(*, api_key=None, id_merchant=None, base_url=None,
                              admin_email=None) -> dict:
    updates = {"updated_at": now_iso(), "provider": "klikqris"}
    if api_key is not None and str(api_key).strip():
        updates["api_key"] = str(api_key).strip()
    if id_merchant is not None and str(id_merchant).strip():
        updates["id_merchant"] = str(id_merchant).strip()
    if base_url is not None and str(base_url).strip():
        updates["base_url"] = str(base_url).strip()
    if admin_email:
        updates["updated_by"] = admin_email
    await db.platform_settings.update_one({"_id": "klikqris"}, {"$set": updates}, upsert=True)
    klikqris.invalidate_creds()
    return await klikqris.gateway_status()


async def gateway_configured() -> bool:
    g = await get_active_gateway()
    return await (klikqris.configured() if g == "klikqris" else mayar.configured())


async def create_gateway_payment(*, order_id, amount, description, name, email, mobile,
                                 redirect_url, callback_url, extra_data) -> dict:
    """Create a payment on the ACTIVE IDR gateway; returns a normalized dict
    consumed by both wallet top-ups and partner charges."""
    g = await get_active_gateway()
    if g == "klikqris":
        data = await klikqris.create_qris(order_id=order_id, amount=int(amount),
                                          description=description, callback_url=callback_url)
        klik_order = data.get("order_id") or order_id
        pay_amount = int(round(float(data.get("total_amount") or amount)))
        return {"gateway": "klikqris", "provider_ref": klik_order, "provider_txn_id": None,
                "signature": data.get("signature"),
                "payment_url": klikqris.pay_page_url(klik_order),
                "checkout_url": klikqris.pay_page_url(klik_order),
                "qris_image": data.get("qris_image"), "qris_url": data.get("qris_url"),
                "pay_amount": pay_amount, "expires_at": data.get("expired_at")}
    inv = await mayar.create_invoice(name=name, email=email, mobile=mobile, amount=int(amount),
                                     description=description, redirect_url=redirect_url,
                                     extra_data=extra_data)
    return {"gateway": "mayar", "provider_ref": inv.get("id"),
            "provider_txn_id": inv.get("transactionId"), "signature": None,
            "payment_url": inv.get("link"), "checkout_url": inv.get("link"),
            "qris_image": None, "qris_url": None, "pay_amount": int(amount),
            "expires_at": inv.get("expiredAt")}


async def verify_paid_record(rec: dict) -> bool:
    """Authoritative re-verification, dispatched by the record's gateway."""
    if rec.get("gateway") == "klikqris":
        return await klikqris.verify_paid(
            rec.get("klik_order_id") or rec.get("provider_ref") or rec.get("id"))
    return await _verify_paid(rec.get("mayar_invoice_id"), rec.get("mayar_transaction_id"))


async def reconcile_topups(limit: int = 40) -> int:
    """Safety-net: re-verify recent uncredited top-ups against the gateway and credit if paid.
    Idempotent — same guarded path as the webhook, so no double credit."""
    from datetime import datetime, timezone, timedelta
    cut = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    recs = await db.mayar_payments.find(
        {"credited": {"$ne": True}, "created_at": {"$gte": cut}},
        {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    credited = 0
    for rec in recs:
        try:
            res = await _try_credit_topup(rec)
            if res.get("credited"):
                credited += 1
        except Exception as e:  # noqa: BLE001
            logger.warning("reconcile topup %s failed: %s", rec.get("id"), e)
    return credited


# --------------------------- helpers ------------------------------------- #
async def _get_wallet(workspace_id: str) -> dict:
    w = await db.wallets.find_one({"workspace_id": workspace_id}, {"_id": 0})
    if not w:
        w = {"workspace_id": workspace_id, "balance": 0, "currency": "credit",
             "created_at": now_iso(), "updated_at": now_iso()}
        await db.wallets.insert_one({**w})
        w.pop("_id", None)
    return w


async def _apply(workspace_id: str, amount: int, ttype: str, description: str,
                 ref: str | None = None, actor: str | None = None):
    """Atomically change balance and append an immutable ledger entry."""
    doc = await db.wallets.find_one_and_update(
        {"workspace_id": workspace_id},
        {"$inc": {"balance": amount}, "$set": {"updated_at": now_iso()},
         "$setOnInsert": {"currency": "credit", "created_at": now_iso()}},
        upsert=True, return_document=ReturnDocument.AFTER,
    )
    balance_after = int(doc.get("balance", amount))
    entry = {"id": str(uuid.uuid4()), "workspace_id": workspace_id, "type": ttype,
             "amount": int(amount), "balance_after": balance_after, "description": description,
             "ref": ref, "actor": actor, "created_at": now_iso()}
    await db.wallet_ledger.insert_one({**entry})
    entry.pop("_id", None)
    return balance_after, entry


async def _verify_paid(invoice_id: str, transaction_id: str | None) -> bool:
    """Authoritative check against Mayar — never trust webhook/redirect alone."""
    if not invoice_id:
        return False
    try:
        inv = await mayar.get_invoice(invoice_id)
        if str(inv.get("status", "")).lower() in PAID_STATUSES:
            return True
    except mayar.MayarError:
        pass
    try:
        txns = await mayar.list_transactions(page=1, page_size=25)
    except mayar.MayarError:
        txns = []
    for t in txns:
        if str(t.get("status", "")).lower() not in PAID_STATUSES:
            continue
        if t.get("paymentLinkId") == invoice_id or (
            transaction_id and t.get("paymentLinkTransactionId") == transaction_id
        ):
            return True
    return False


async def _try_credit_topup(rec: dict) -> dict:
    if rec.get("credited"):
        return {"status": "paid", "credited": True}
    paid = await verify_paid_record(rec)
    if not paid:
        return {"status": rec.get("status", "pending"), "credited": False}
    # Atomic single-credit claim (protects against webhook + poll racing).
    claimed = await db.mayar_payments.find_one_and_update(
        {"id": rec["id"], "credited": {"$ne": True}},
        {"$set": {"credited": True, "status": "paid", "paid_at": now_iso()}},
    )
    if not claimed:
        return {"status": "paid", "credited": True}
    gw_label = "KlikQRIS" if rec.get("gateway") == "klikqris" else "Mayar"
    await _apply(rec["workspace_id"], int(rec["credits"]), "topup",
                 f"Wallet top-up via {gw_label} ({int(rec['credits']):,} credits)", ref=rec["id"])
    logger.info("wallet top-up credited ws=%s credits=%s order=%s",
                rec["workspace_id"], rec["credits"], rec["id"])
    return {"status": "paid", "credited": True}


async def _verify_webhook_token(request: Request) -> bool:
    token = await mayar.webhook_token()
    if not token:
        return False
    candidates = [
        request.headers.get("x-webhook-token"),
        request.headers.get("x-mayar-token"),
        request.headers.get("x-callback-token"),
    ]
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        candidates.append(auth[7:])
    return any(c and hmac.compare_digest(str(c), token) for c in candidates)


# --------------------------- schemas ------------------------------------- #
class TopupInput(BaseModel):
    amount: int = Field(gt=0)
    return_url: str | None = None


class PurchaseInput(BaseModel):
    plan_id: str


class AdjustInput(BaseModel):
    workspace_id: str
    amount: int
    reason: str | None = None


# --------------------------- endpoints ----------------------------------- #
@router.get("/summary")
async def summary(ws=Depends(get_billing_workspace)):
    w = await _get_wallet(ws["id"])
    ledger = await db.wallet_ledger.find(
        {"workspace_id": ws["id"]}, {"_id": 0}
    ).sort("created_at", -1).limit(20).to_list(20)
    ps = await get_payment_settings()
    cs = await get_credit_settings()
    return {"balance": int(w.get("balance", 0)), "currency": "credit",
            "min_topup": cs["min_topup"], "gateway_ready": await gateway_configured(),
            "active_gateway": await get_active_gateway(),
            "rupiah_per_credit": cs["rupiah_per_credit"], "bonus_percent": cs["bonus_percent"],
            "requests_per_credit": cs["requests_per_credit"],
            "topup_enabled": ps["topup_enabled"],
            "topup_disabled_message": ps["topup_disabled_message"], "ledger": ledger}


@router.get("/ledger")
async def ledger(ws=Depends(get_billing_workspace), limit: int = 100):
    rows = await db.wallet_ledger.find(
        {"workspace_id": ws["id"]}, {"_id": 0}
    ).sort("created_at", -1).limit(min(limit, 500)).to_list(min(limit, 500))
    return {"items": rows}


@router.post("/topup")
async def topup(payload: TopupInput, ws=Depends(get_billing_workspace),
                user=Depends(get_current_user)):
    ps = await get_payment_settings()
    if not ps["topup_enabled"]:
        raise HTTPException(status_code=503, detail=ps["topup_disabled_message"])
    if not await gateway_configured():
        raise HTTPException(status_code=503, detail="Payment gateway is not configured yet.")
    cs = await get_credit_settings()
    amount = int(payload.amount)
    if amount < cs["min_topup"]:
        raise HTTPException(status_code=400, detail=f"Minimum top-up is Rp{cs['min_topup']:,}.")
    if amount > MAX_TOPUP:
        raise HTTPException(status_code=400, detail="Top-up amount is too large.")
    credits, base_credits, bonus_credits = credits_for_amount(amount, cs)
    if credits < 1:
        raise HTTPException(
            status_code=400,
            detail=f"Top-up too small — you need at least Rp{cs['rupiah_per_credit']:,} to earn 1 credit.")

    order_id = str(uuid.uuid4())
    base = payload.return_url if (payload.return_url or "").startswith(("http://", "https://")) \
        else f"{settings.FRONTEND_URL}/app/billing"
    return_url = f"{base}{'&' if '?' in base else '?'}topup={order_id}"
    callback_url = f"{settings.FRONTEND_URL}/api/wallet/klikqris/webhook"

    try:
        pay = await create_gateway_payment(
            order_id=order_id, amount=amount,
            description=f"Midnight Link wallet top-up — {credits:,} credits (Rp{amount:,})",
            name=user.get("name") or "Midnight Link Customer",
            email=user.get("email"), mobile=user.get("mobile") or "081200000000",
            redirect_url=return_url, callback_url=callback_url,
            extra_data={"order_id": order_id, "workspace_id": ws["id"], "kind": "wallet_topup"},
        )
    except (mayar.MayarError, klikqris.KlikqrisError) as e:
        logger.error("topup create failed ws=%s: %s", ws["id"], e)
        raise HTTPException(status_code=502, detail="Could not start payment. Please try again.")

    rec = {"id": order_id, "workspace_id": ws["id"], "kind": "wallet_topup",
           "amount": amount, "credits": credits, "base_credits": base_credits,
           "bonus_credits": bonus_credits, "rupiah_per_credit": cs["rupiah_per_credit"],
           "status": "pending", "credited": False, "gateway": pay["gateway"],
           "mayar_invoice_id": pay["provider_ref"] if pay["gateway"] == "mayar" else None,
           "mayar_transaction_id": pay["provider_txn_id"],
           "klik_order_id": pay["provider_ref"] if pay["gateway"] == "klikqris" else None,
           "klik_signature": pay["signature"], "payment_url": pay["payment_url"],
           "qris_url": pay["qris_url"], "pay_amount": pay["pay_amount"],
           "expires_at": pay["expires_at"], "created_by": user["id"], "created_at": now_iso()}
    await db.mayar_payments.insert_one({**rec})
    return {"order_id": order_id, "gateway": pay["gateway"], "payment_url": pay["payment_url"],
            "qris_image": pay["qris_image"], "qris_url": pay["qris_url"],
            "pay_amount": pay["pay_amount"], "expires_at": pay["expires_at"],
            "amount": amount, "credits": credits}


@router.get("/topup/{order_id}")
async def topup_status(order_id: str, ws=Depends(get_billing_workspace)):
    rec = await db.mayar_payments.find_one({"id": order_id, "workspace_id": ws["id"]}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    result = await _try_credit_topup(rec)
    w = await _get_wallet(ws["id"])
    return {"order_id": order_id, "gateway": rec.get("gateway", "mayar"),
            "status": result["status"], "credited": result["credited"],
            "balance": int(w.get("balance", 0)), "payment_url": rec.get("payment_url"),
            "qris_url": rec.get("qris_url"), "pay_amount": rec.get("pay_amount")}


@router.post("/purchase-plan")
async def purchase_plan(payload: PurchaseInput, ws=Depends(get_billing_workspace)):
    plan = PLAN_MAP.get(payload.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Unknown plan")
    if plan["id"] == "free":
        raise HTTPException(status_code=400, detail="Free plan does not require payment")
    if plan["price"] is None:
        raise HTTPException(status_code=400, detail="Enterprise plans are handled by sales")

    price_rp = int(plan["price"])
    cs = await get_credit_settings()
    price_credits = credits_for_price(price_rp, cs)
    w_doc = await db.workspaces.find_one({"id": ws["id"]}, {"_id": 0, "plan": 1})
    if (w_doc or {}).get("plan") == plan["id"]:
        raise HTTPException(status_code=400, detail=f"You're already on the {plan['name']} plan.")
    w = await _get_wallet(ws["id"])
    balance = int(w.get("balance", 0))
    if balance < price_credits:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits. Top up {price_credits - balance:,} more to activate {plan['name']}.",
        )
    balance_after, entry = await _apply(
        ws["id"], -price_credits, "spend", f"{plan['name']} plan — 1 month", ref=plan["id"])
    period_end = await activate_plan_for_workspace(
        ws["id"], plan["id"], paid_via="wallet_credit", amount=price_rp, ref=entry["id"])
    return {"ok": True, "plan": plan["id"], "balance": balance_after,
            "current_period_end": period_end}


class PurchasePassInput(BaseModel):
    days: int
    requests: int


@router.post("/purchase-pass")
async def purchase_pass(payload: PurchasePassInput, ws=Depends(get_billing_workspace)):
    from .billing import is_valid_pass, pass_price, activate_pass_for_workspace
    if not is_valid_pass(payload.days, payload.requests):
        raise HTTPException(status_code=400, detail="Invalid plan option.")
    price_rp = pass_price(payload.days, payload.requests)
    cs = await get_credit_settings()
    price_credits = credits_for_price(price_rp, cs)
    w = await _get_wallet(ws["id"])
    balance = int(w.get("balance", 0))
    if balance < price_credits:
        short = price_credits - balance
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits. Top up {short:,} more credits (≈Rp{short * cs['rupiah_per_credit']:,}) to activate this plan.",
        )
    balance_after, entry = await _apply(
        ws["id"], -price_credits, "spend",
        f"{payload.days}-day pass · {payload.requests:,} requests", ref=f"pass:{payload.days}:{payload.requests}")
    res = await activate_pass_for_workspace(
        ws["id"], payload.days, payload.requests, paid_via="wallet_credit", amount=price_rp, ref=entry["id"])
    return {"ok": True, "balance": balance_after, "expires_at": res["expires_at"],
            "label": res["label"], "price_rp": price_rp, "price_credits": price_credits}


@router.get("/entitlement")
async def entitlement(ws=Depends(get_billing_workspace)):
    from .billing import pass_state
    st = await pass_state(ws["id"])
    w = await _get_wallet(ws["id"])
    cs = await get_credit_settings()
    rpc = max(1, int(cs.get("requests_per_credit", DEFAULT_REQ_PER_CREDIT)))
    balance = int(w.get("balance", 0))
    overflow = int(w.get("req_overflow", 0))
    credit_requests = balance * rpc + overflow
    return {**st, "credit_balance": balance, "requests_per_credit": rpc,
            "overflow_requests": overflow, "credit_requests_available": credit_requests,
            "total_requests_available": st["requests_remaining"] + credit_requests}


@router.post("/mayar/webhook")
async def mayar_webhook(request: Request):
    """Public callback from Mayar (event `payment.received`). Re-verified against the
    Mayar API before crediting, so authenticity of the request is not solely relied on."""
    raw = await request.body()
    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event = payload.get("event") or payload.get("event.received")
    data = payload.get("data") or {}
    token_ok = await _verify_webhook_token(request)
    logger.info("Mayar webhook event=%s token_ok=%s", event, token_ok)

    if event and event != "payment.received":
        return {"ok": True, "ignored": event}

    extra = data.get("extraData") or {}
    rec = None
    if extra.get("order_id"):
        rec = await db.mayar_payments.find_one({"id": extra["order_id"]}, {"_id": 0})
    if not rec:
        cand = [c for c in (data.get("id"), data.get("transactionId"),
                            data.get("paymentLinkId"), data.get("paymentLinkTransactionId")) if c]
        if cand:
            rec = await db.mayar_payments.find_one(
                {"$or": [{"mayar_invoice_id": {"$in": cand}},
                         {"mayar_transaction_id": {"$in": cand}}]}, {"_id": 0})
    if not rec:
        from .partner_pay import handle_mayar_event
        if await handle_mayar_event(event, data):
            return {"ok": True, "partner": True}
        logger.warning("Mayar webhook: no matching top-up/charge record (event=%s)", event)
        return {"ok": True, "unmatched": True}

    result = await _try_credit_topup(rec)
    return {"ok": True, **result}


@router.post("/klikqris/webhook")
async def klikqris_webhook(request: Request):
    """Public callback from KlikQRIS (status PAID/EXPIRED). The payment is re-verified
    against the KlikQRIS status API before crediting, so a forged webhook cannot grant
    credits. Also routes partner charges when no top-up record matches."""
    raw = await request.body()
    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    order_id = payload.get("order_id")
    status = str(payload.get("status", "")).upper()
    sig = payload.get("signature")
    logger.info("KlikQRIS webhook order=%s status=%s", order_id, status)
    if not order_id:
        return {"ok": True, "ignored": True}

    rec = await db.mayar_payments.find_one({"klik_order_id": order_id}, {"_id": 0})
    if rec:
        if rec.get("klik_signature") and sig and rec["klik_signature"] != sig:
            logger.warning("KlikQRIS webhook signature mismatch order=%s", order_id)
        result = await _try_credit_topup(rec)
        return {"ok": True, **result}

    from .partner_pay import handle_klik_event
    if await handle_klik_event(order_id, payload):
        return {"ok": True, "partner": True}
    logger.warning("KlikQRIS webhook: no matching top-up/charge record (order=%s)", order_id)
    return {"ok": True, "unmatched": True}


@router.post("/admin/adjust")
async def admin_adjust(payload: AdjustInput, admin=Depends(require_admin)):
    """Platform-admin manual credit (refund) or debit adjustment."""
    if payload.amount == 0:
        raise HTTPException(status_code=400, detail="Amount cannot be zero")
    ws = await db.workspaces.find_one({"id": payload.workspace_id}, {"_id": 0, "id": 1})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    w = await _get_wallet(payload.workspace_id)
    if payload.amount < 0 and int(w.get("balance", 0)) + payload.amount < 0:
        raise HTTPException(status_code=400, detail="Adjustment would make the balance negative")
    ttype = "refund" if payload.amount > 0 else "adjustment"
    default_reason = "Manual credit by admin" if payload.amount > 0 else "Manual adjustment by admin"
    balance_after, entry = await _apply(
        payload.workspace_id, int(payload.amount), ttype,
        payload.reason or default_reason, actor=admin["email"])
    return {"ok": True, "balance": balance_after, "entry": entry}
