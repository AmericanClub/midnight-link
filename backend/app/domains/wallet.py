"""Credit wallet + immutable ledger, funded by real Mayar top-ups.

Model (approved): 1 credit = Rp1. Hybrid — top up the wallet via Mayar (QRIS/e-wallet/VA)
and spend credits on plans. Credits never expire. All balance changes append an
immutable ledger entry. Payments are only credited after server-side verification with
Mayar (idempotent), so forged webhooks cannot grant credits.
"""
import hmac
import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from ..db import db
from ..utils import now_iso
from ..config import settings
from .. import mayar
from ..security import get_current_user
from .billing import get_billing_workspace, PLAN_MAP, activate_plan_for_workspace
from .admin import require_admin

router = APIRouter(prefix="/api/wallet", tags=["wallet"])
logger = logging.getLogger("midgate.wallet")

MIN_TOPUP = 10_000            # Rp
MAX_TOPUP = 100_000_000       # Rp — sane upper bound to catch typos/abuse
PAID_STATUSES = {"paid", "settled", "success"}


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
    paid = await _verify_paid(rec.get("mayar_invoice_id"), rec.get("mayar_transaction_id"))
    if not paid:
        return {"status": rec.get("status", "pending"), "credited": False}
    # Atomic single-credit claim (protects against webhook + poll racing).
    claimed = await db.mayar_payments.find_one_and_update(
        {"id": rec["id"], "credited": {"$ne": True}},
        {"$set": {"credited": True, "status": "paid", "paid_at": now_iso()}},
    )
    if not claimed:
        return {"status": "paid", "credited": True}
    await _apply(rec["workspace_id"], int(rec["credits"]), "topup",
                 f"Wallet top-up via Mayar ({int(rec['credits']):,} credits)", ref=rec["id"])
    logger.info("wallet top-up credited ws=%s credits=%s order=%s",
                rec["workspace_id"], rec["credits"], rec["id"])
    return {"status": "paid", "credited": True}


def _verify_webhook_token(request: Request) -> bool:
    token = settings.MAYAR_WEBHOOK_TOKEN
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
    return {"balance": int(w.get("balance", 0)), "currency": "credit",
            "min_topup": MIN_TOPUP, "gateway_ready": mayar.configured(), "ledger": ledger}


@router.get("/ledger")
async def ledger(ws=Depends(get_billing_workspace), limit: int = 100):
    rows = await db.wallet_ledger.find(
        {"workspace_id": ws["id"]}, {"_id": 0}
    ).sort("created_at", -1).limit(min(limit, 500)).to_list(min(limit, 500))
    return {"items": rows}


@router.post("/topup")
async def topup(payload: TopupInput, ws=Depends(get_billing_workspace),
                user=Depends(get_current_user)):
    if not mayar.configured():
        raise HTTPException(status_code=503, detail="Payment gateway is not configured yet.")
    amount = int(payload.amount)
    if amount < MIN_TOPUP:
        raise HTTPException(status_code=400, detail=f"Minimum top-up is Rp{MIN_TOPUP:,}.")
    if amount > MAX_TOPUP:
        raise HTTPException(status_code=400, detail="Top-up amount is too large.")

    order_id = str(uuid.uuid4())
    base = payload.return_url if (payload.return_url or "").startswith(("http://", "https://")) \
        else f"{settings.FRONTEND_URL}/app/billing"
    return_url = f"{base}{'&' if '?' in base else '?'}topup={order_id}"

    try:
        inv = await mayar.create_invoice(
            name=user.get("name") or "MidGate Customer",
            email=user.get("email"),
            mobile=user.get("mobile") or "081200000000",
            amount=amount,
            description=f"MidGate wallet top-up ({amount:,} credits)",
            redirect_url=return_url,
            extra_data={"order_id": order_id, "workspace_id": ws["id"], "kind": "wallet_topup"},
        )
    except mayar.MayarError as e:
        logger.error("topup create failed ws=%s: %s", ws["id"], e)
        raise HTTPException(status_code=502, detail="Could not start payment. Please try again.")

    rec = {"id": order_id, "workspace_id": ws["id"], "kind": "wallet_topup",
           "amount": amount, "credits": amount, "status": "pending", "credited": False,
           "mayar_invoice_id": inv.get("id"), "mayar_transaction_id": inv.get("transactionId"),
           "payment_url": inv.get("link"), "created_by": user["id"], "created_at": now_iso()}
    await db.mayar_payments.insert_one({**rec})
    return {"order_id": order_id, "payment_url": inv.get("link"), "amount": amount}


@router.get("/topup/{order_id}")
async def topup_status(order_id: str, ws=Depends(get_billing_workspace)):
    rec = await db.mayar_payments.find_one({"id": order_id, "workspace_id": ws["id"]}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    result = await _try_credit_topup(rec)
    w = await _get_wallet(ws["id"])
    return {"order_id": order_id, "status": result["status"], "credited": result["credited"],
            "balance": int(w.get("balance", 0)), "payment_url": rec.get("payment_url")}


@router.post("/purchase-plan")
async def purchase_plan(payload: PurchaseInput, ws=Depends(get_billing_workspace)):
    plan = PLAN_MAP.get(payload.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Unknown plan")
    if plan["id"] == "free":
        raise HTTPException(status_code=400, detail="Free plan does not require payment")
    if plan["price"] is None:
        raise HTTPException(status_code=400, detail="Enterprise plans are handled by sales")

    price = int(plan["price"])
    w_doc = await db.workspaces.find_one({"id": ws["id"]}, {"_id": 0, "plan": 1})
    if (w_doc or {}).get("plan") == plan["id"]:
        raise HTTPException(status_code=400, detail=f"You're already on the {plan['name']} plan.")
    w = await _get_wallet(ws["id"])
    balance = int(w.get("balance", 0))
    if balance < price:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits. Top up {price - balance:,} more to activate {plan['name']}.",
        )
    balance_after, entry = await _apply(
        ws["id"], -price, "spend", f"{plan['name']} plan — 1 month", ref=plan["id"])
    period_end = await activate_plan_for_workspace(
        ws["id"], plan["id"], paid_via="wallet_credit", amount=price, ref=entry["id"])
    return {"ok": True, "plan": plan["id"], "balance": balance_after,
            "current_period_end": period_end}


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
    token_ok = _verify_webhook_token(request)
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
