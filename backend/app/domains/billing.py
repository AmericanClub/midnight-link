import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ..db import db
from ..utils import now_iso
from ..providers import payment_provider, event_bus
from .workspace import get_current_workspace

router = APIRouter(prefix="/api/billing", tags=["billing"])

# Plan catalog. Billing/QRIS flow uses the PaymentProvider abstraction.
# Payment confirmation is server-side only (never trusted from the frontend).
PLANS = [
    {"id": "free", "name": "Free", "price": 0, "currency": "IDR", "cycle": "month",
     "limits": {"smart_links": 10, "dynamic_qr": 3, "monthly_events": 1000, "retention_days": 7,
                "members": 1, "custom_domains": 0}, "branding": True},
    {"id": "starter", "name": "Starter", "price": 149000, "currency": "IDR", "cycle": "month",
     "limits": {"smart_links": 100, "dynamic_qr": 25, "monthly_events": 50000, "retention_days": 90,
                "members": 2, "custom_domains": 1}, "branding": True},
    {"id": "pro", "name": "Pro", "price": 499000, "currency": "IDR", "cycle": "month",
     "limits": {"smart_links": 1000, "dynamic_qr": 250, "monthly_events": 500000, "retention_days": 365,
                "members": 10, "custom_domains": 5}, "branding": False},
    {"id": "business", "name": "Business", "price": 1499000, "currency": "IDR", "cycle": "month",
     "limits": {"smart_links": 10000, "dynamic_qr": 2500, "monthly_events": 5000000, "retention_days": 730,
                "members": 50, "custom_domains": 25}, "branding": False},
    {"id": "enterprise", "name": "Enterprise", "price": None, "currency": "IDR", "cycle": "custom",
     "limits": {"smart_links": None, "dynamic_qr": None, "monthly_events": None, "retention_days": None,
                "members": None, "custom_domains": None}, "branding": False},
]
PLAN_MAP = {p["id"]: p for p in PLANS}


class CheckoutInput(BaseModel):
    plan_id: str


def _clean(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


@router.get("/plans")
async def get_plans():
    return {"plans": PLANS}


@router.get("/subscription")
async def get_subscription(ws=Depends(get_current_workspace)):
    sub = await db.subscriptions.find_one({"workspace_id": ws["id"]}, {"_id": 0})
    plan_id = ws.get("plan", "free")
    return {"plan": PLAN_MAP.get(plan_id, PLAN_MAP["free"]), "subscription": sub}


@router.get("/invoices")
async def list_invoices(ws=Depends(get_current_workspace)):
    rows = await db.invoices.find({"workspace_id": ws["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"items": rows}


@router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str, ws=Depends(get_current_workspace)):
    inv = await db.invoices.find_one({"id": invoice_id, "workspace_id": ws["id"]}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Not found")
    return inv


@router.post("/checkout")
async def checkout(payload: CheckoutInput, ws=Depends(get_current_workspace)):
    plan = PLAN_MAP.get(payload.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Unknown plan")
    if plan["id"] == "free":
        raise HTTPException(status_code=400, detail="Free plan does not require payment")
    if plan["price"] is None:
        raise HTTPException(status_code=400, detail="Enterprise plans are handled by sales")

    # backend owns the price snapshot — frontend never sets the amount
    invoice = {
        "id": str(uuid.uuid4()),
        "workspace_id": ws["id"],
        "plan_id": plan["id"],
        "plan_name": plan["name"],
        "amount": plan["price"],
        "currency": plan["currency"],
        "status": "pending",
        "created_at": now_iso(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
    }
    charge = await payment_provider.create_charge(invoice)
    invoice["qris_string"] = charge["qris_string"]
    invoice["provider"] = charge["provider"]
    await db.invoices.insert_one({**invoice})
    return _clean(invoice)


async def _activate(invoice: dict):
    """Server-side subscription activation (represents a verified provider webhook)."""
    plan = PLAN_MAP[invoice["plan_id"]]
    now = now_iso()
    period_end = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    await db.subscriptions.update_one(
        {"workspace_id": invoice["workspace_id"]},
        {"$set": {
            "id": str(uuid.uuid4()),
            "workspace_id": invoice["workspace_id"],
            "plan_id": plan["id"],
            "status": "active",
            "limits": plan["limits"],
            "current_period_end": period_end,
            "updated_at": now,
        }},
        upsert=True,
    )
    await db.workspaces.update_one({"id": invoice["workspace_id"]}, {"$set": {"plan": plan["id"]}})
    await db.invoices.update_one({"id": invoice["id"]}, {"$set": {"status": "paid", "paid_at": now}})
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "workspace_id": invoice["workspace_id"],
        "action": "subscription.activated",
        "target": invoice["id"],
        "before": {"status": invoice["status"]},
        "after": {"status": "paid", "plan": plan["id"]},
        "at": now,
    })
    await event_bus.publish("subscription.activated", {"workspace_id": invoice["workspace_id"], "plan": plan["id"]})


@router.post("/invoices/{invoice_id}/simulate-payment")
async def simulate_payment(invoice_id: str, ws=Depends(get_current_workspace)):
    """DEMO ONLY — stands in for a signed QRIS provider webhook. Idempotent.
    In production this activation happens only after verifying the provider's
    signed webhook (signature, timestamp, amount, currency, reference)."""
    inv = await db.invoices.find_one({"id": invoice_id, "workspace_id": ws["id"]})
    if not inv:
        raise HTTPException(status_code=404, detail="Not found")
    if inv["status"] == "paid":
        return {"status": "paid", "already": True}
    if inv["status"] not in ("pending", "draft"):
        raise HTTPException(status_code=400, detail=f"Invoice is {inv['status']}")
    await _activate(inv)
    return {"status": "paid", "plan": inv["plan_id"]}
