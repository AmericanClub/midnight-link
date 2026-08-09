import io
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from ..db import db
from ..config import settings
from ..utils import now_iso
from ..security import get_current_user
from ..providers import payment_provider, event_bus, email_provider

router = APIRouter(prefix="/api/billing", tags=["billing"])

BILLING_ROLES = {"owner", "admin", "billing_manager"}

# Plan catalog. Billing/QRIS flow uses the PaymentProvider abstraction.
# Payment confirmation is server-side only (never trusted from the frontend).
PLANS = [
    {"id": "free", "name": "Free", "price": 0, "currency": "IDR", "cycle": "month",
     "limits": {"smart_links": 10, "dynamic_qr": 3, "monthly_events": 1000, "retention_days": 7,
                "members": 1, "custom_domains": 0}, "branding": True},
    {"id": "starter", "name": "Starter", "price": 99000, "currency": "IDR", "cycle": "month",
     "limits": {"smart_links": 100, "dynamic_qr": 25, "monthly_events": 50000, "retention_days": 90,
                "members": 2, "custom_domains": 1}, "branding": True},
    {"id": "pro", "name": "Pro", "price": 299000, "currency": "IDR", "cycle": "month",
     "limits": {"smart_links": 1000, "dynamic_qr": 250, "monthly_events": 500000, "retention_days": 365,
                "members": 10, "custom_domains": 5}, "branding": False},
    {"id": "business", "name": "Business", "price": 999000, "currency": "IDR", "cycle": "month",
     "limits": {"smart_links": 10000, "dynamic_qr": 2500, "monthly_events": 5000000, "retention_days": 730,
                "members": 50, "custom_domains": 25}, "branding": False},
    {"id": "enterprise", "name": "Enterprise", "price": None, "currency": "IDR", "cycle": "custom",
     "limits": {"smart_links": None, "dynamic_qr": None, "monthly_events": None, "retention_days": None,
                "members": None, "custom_domains": None}, "branding": False},
]
PLAN_MAP = {p["id"]: p for p in PLANS}

# ---- Duration passes: all features included; differ only by Requests volume + duration ----
PASS_RATES = {1: 7.5, 3: 6.0, 7: 4.8, 14: 4.0, 30: 3.5}  # Rp per request
PASS_REQUEST_OPTIONS = {
    1:  [1000, 2000, 3000, 4000, 5000],
    3:  [3000, 4000, 5000, 6000, 7000],
    7:  [7000, 10000, 15000, 20000, 25000],
    14: [20000, 30000, 40000, 50000, 60000],
    30: [50000, 75000, 100000, 150000, 200000],
}
PASS_MIN_PRICE = 5000
FREE_LINK_LIMIT = 5
FREE_QR_LIMIT = 2


def pass_price(days: int, requests: int) -> int:
    rate = PASS_RATES.get(int(days))
    if rate is None:
        return 0
    price = int(round(int(requests) * rate / 500.0)) * 500
    return max(PASS_MIN_PRICE, price)


def is_valid_pass(days: int, requests: int) -> bool:
    return int(requests) in PASS_REQUEST_OPTIONS.get(int(days), [])


def list_passes() -> list:
    out = []
    for days in (1, 3, 7, 14, 30):
        options = [{"requests": r, "price": pass_price(days, r)} for r in PASS_REQUEST_OPTIONS[days]]
        out.append({"days": days, "rate_per_request": PASS_RATES[days], "options": options})
    return out


async def pass_state(workspace_id: str) -> dict:
    ws = await db.workspaces.find_one(
        {"id": workspace_id},
        {"_id": 0, "pass_expires_at": 1, "pass_requests_included": 1, "pass_requests_used": 1,
         "pass_days": 1, "pass_label": 1, "quota_exhausted": 1},
    ) or {}
    exp = ws.get("pass_expires_at")
    active = bool(exp) and exp > now_iso()
    included = int(ws.get("pass_requests_included", 0))
    used = int(ws.get("pass_requests_used", 0))
    remaining = max(0, included - used) if active else 0
    return {
        "active": active, "expires_at": exp, "days": ws.get("pass_days"),
        "label": ws.get("pass_label"), "requests_included": included,
        "requests_used": used, "requests_remaining": remaining,
        "quota_exhausted": bool(ws.get("quota_exhausted")),
    }


async def pass_is_active(workspace_id: str) -> bool:
    ws = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0, "pass_expires_at": 1})
    exp = (ws or {}).get("pass_expires_at")
    return bool(exp) and exp > now_iso()


class CheckoutInput(BaseModel):
    plan_id: str


def _clean(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


def plan_limits(plan_id: str) -> dict:
    return PLAN_MAP.get(plan_id, PLAN_MAP["free"])["limits"]


# --------------------------- usage + quota -------------------------------- #
def _month_start_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-01T00:00:00+00:00")


async def get_usage(workspace_id: str) -> dict:
    links = await db.links.count_documents({"workspace_id": workspace_id, "is_qr": {"$ne": True}})
    qr = await db.links.count_documents({"workspace_id": workspace_id, "is_qr": True})
    st = await pass_state(workspace_id)
    included, used = st["requests_included"], st["requests_used"]
    pct = min(100, round((used / included) * 100)) if included else 0
    return {
        "links": {"used": links, "limit": None if st["active"] else FREE_LINK_LIMIT},
        "qr": {"used": qr, "limit": None if st["active"] else FREE_QR_LIMIT},
        "requests": {"included": included, "used": used, "remaining": st["requests_remaining"],
                     "pct": pct, "active": st["active"], "expires_at": st["expires_at"]},
    }


async def enforce_quota(ws: dict, resource: str):
    """Free tier gets a small trial; an active pass unlocks unlimited links/QR."""
    if await pass_is_active(ws["id"]):
        return
    if resource == "dynamic_qr":
        used = await db.links.count_documents({"workspace_id": ws["id"], "is_qr": True})
        limit, label = FREE_QR_LIMIT, "QR code"
    else:
        used = await db.links.count_documents({"workspace_id": ws["id"], "is_qr": {"$ne": True}})
        limit, label = FREE_LINK_LIMIT, "smart link"
    if used >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"Free limit reached ({limit} {label}s). Activate a plan to create unlimited {label}s.",
        )


async def can_record_event(workspace_id: str) -> bool:
    # Request metering now happens in wallet.consume_request; always log analytics.
    return True


# --------------------------- billing access ------------------------------ #
async def get_billing_workspace(request: Request, user=Depends(get_current_user)) -> dict:
    from .workspace import list_user_workspaces
    ws_id = request.headers.get("X-Workspace-Id")
    workspaces = await list_user_workspaces(user["id"])
    ws = next((w for w in workspaces if w["id"] == ws_id), None) if ws_id else (workspaces[0] if workspaces else None)
    if not ws:
        raise HTTPException(status_code=404, detail="Not found")
    if ws.get("role") not in BILLING_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission to manage billing for this workspace")
    return ws


# --------------------------- receipt PDF ---------------------------------- #
def generate_receipt_pdf(invoice: dict, workspace_name: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 40 * mm
    c.setFillColorRGB(0.263, 0.219, 0.792)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(25 * mm, y, "Midnight Link")
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawString(25 * mm, y - 6 * mm, "Every Click. Protected.")
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 16)
    c.drawRightString(w - 25 * mm, y, "PAYMENT RECEIPT")

    y -= 25 * mm
    c.setFont("Helvetica", 11)
    rows = [
        ("Receipt for", workspace_name),
        ("Invoice ID", invoice["id"]),
        ("Plan", invoice.get("plan_name", invoice["plan_id"])),
        ("Date", invoice.get("paid_at", now_iso())[:19].replace("T", " ")),
        ("Status", "PAID"),
    ]
    for label, val in rows:
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawString(25 * mm, y, f"{label}")
        c.setFillColorRGB(0, 0, 0)
        c.drawString(70 * mm, y, str(val))
        y -= 9 * mm

    y -= 6 * mm
    c.line(25 * mm, y, w - 25 * mm, y)
    y -= 12 * mm
    cur = "Rp " if invoice.get("currency") == "IDR" else "$"
    c.setFont("Helvetica-Bold", 14)
    c.drawString(25 * mm, y, "Total paid")
    c.drawRightString(w - 25 * mm, y, f"{cur}{invoice['amount']:,}")

    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawString(25 * mm, 20 * mm, "Thank you for choosing Midnight Link. This is a system-generated receipt.")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()


# --------------------------- endpoints ------------------------------------ #
@router.get("/plans")
async def get_plans():
    return {"plans": PLANS}


@router.get("/passes")
async def get_passes():
    return {"passes": list_passes()}


@router.get("/subscription")
async def get_subscription(ws=Depends(get_billing_workspace)):
    st = await pass_state(ws["id"])
    return {"pass": st, "role": ws.get("role")}


@router.get("/usage")
async def usage(ws=Depends(get_billing_workspace)):
    return await get_usage(ws["id"])


@router.get("/invoices")
async def list_invoices(ws=Depends(get_billing_workspace)):
    rows = await db.invoices.find({"workspace_id": ws["id"]}, {"_id": 0, "qris_string": 0}).sort("created_at", -1).to_list(100)
    return {"items": rows}


@router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str, ws=Depends(get_billing_workspace)):
    inv = await db.invoices.find_one({"id": invoice_id, "workspace_id": ws["id"]}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Not found")
    return inv


@router.get("/invoices/{invoice_id}/receipt.pdf")
async def receipt(invoice_id: str, ws=Depends(get_billing_workspace)):
    inv = await db.invoices.find_one({"id": invoice_id, "workspace_id": ws["id"]})
    if not inv or inv.get("status") != "paid":
        raise HTTPException(status_code=404, detail="Receipt not available")
    pdf = generate_receipt_pdf(inv, ws.get("name", "Workspace"))
    return StreamingResponse(
        iter([pdf]), media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="midnightlink_receipt_{invoice_id[:8]}.pdf"'},
    )


@router.post("/checkout")
async def checkout(payload: CheckoutInput, ws=Depends(get_billing_workspace)):
    if not settings.ALLOW_MOCK_PAYMENTS:
        raise HTTPException(status_code=403,
                            detail="Direct checkout is disabled. Top up your wallet and activate a plan with credits.")
    plan = PLAN_MAP.get(payload.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Unknown plan")
    if plan["id"] == "free":
        raise HTTPException(status_code=400, detail="Free plan does not require payment")
    if plan["price"] is None:
        raise HTTPException(status_code=400, detail="Enterprise plans are handled by sales")

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


async def _activate(invoice: dict, workspace_name: str):
    """Server-side subscription activation (represents a verified provider webhook)."""
    plan = PLAN_MAP[invoice["plan_id"]]
    now = now_iso()
    period_end = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    await db.subscriptions.update_one(
        {"workspace_id": invoice["workspace_id"]},
        {"$set": {
            "id": str(uuid.uuid4()), "workspace_id": invoice["workspace_id"], "plan_id": plan["id"],
            "status": "active", "limits": plan["limits"], "current_period_end": period_end, "updated_at": now,
        }}, upsert=True,
    )
    await db.workspaces.update_one({"id": invoice["workspace_id"]}, {"$set": {"plan": plan["id"]}})
    await db.invoices.update_one({"id": invoice["id"]}, {"$set": {"status": "paid", "paid_at": now}})
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()), "workspace_id": invoice["workspace_id"], "action": "subscription.activated",
        "target": invoice["id"], "before": {"status": invoice["status"]},
        "after": {"status": "paid", "plan": plan["id"]}, "at": now,
    })
    # email a receipt (MOCKED email provider; PDF is downloadable via receipt endpoint)
    await email_provider.send(
        to=f"workspace:{invoice['workspace_id']}",
        subject=f"Your Midnight Link receipt — {plan['name']} plan",
        body=f"Payment received for the {plan['name']} plan. Receipt: /api/billing/invoices/{invoice['id']}/receipt.pdf",
    )
    await event_bus.publish("invoice.paid", {"workspace_id": invoice["workspace_id"], "invoice_id": invoice["id"]})
    await event_bus.publish("subscription.activated", {"workspace_id": invoice["workspace_id"], "plan": plan["id"]})


async def activate_plan_for_workspace(workspace_id: str, plan_id: str, *,
                                      paid_via: str, amount: int, ref: str | None = None) -> str:
    """Activate/extend a subscription for a workspace (used by credit-wallet purchases)."""
    plan = PLAN_MAP[plan_id]
    now = now_iso()
    period_end = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    await db.subscriptions.update_one(
        {"workspace_id": workspace_id},
        {"$set": {
            "id": str(uuid.uuid4()), "workspace_id": workspace_id, "plan_id": plan["id"],
            "status": "active", "limits": plan["limits"], "current_period_end": period_end,
            "paid_via": paid_via, "updated_at": now,
        }}, upsert=True,
    )
    await db.workspaces.update_one({"id": workspace_id}, {"$set": {"plan": plan["id"]}})
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()), "workspace_id": workspace_id, "action": "subscription.activated",
        "target": ref or plan["id"], "before": None,
        "after": {"plan": plan["id"], "paid_via": paid_via, "amount": amount}, "at": now,
    })
    await event_bus.publish("subscription.activated", {"workspace_id": workspace_id, "plan": plan["id"]})
    return period_end


async def activate_pass_for_workspace(workspace_id: str, days: int, requests: int, *,
                                      paid_via: str, amount: int, ref: str | None = None) -> dict:
    """Activate a duration pass: unlocks all features + a Requests quota for the period."""
    now = now_iso()
    expires = (datetime.now(timezone.utc) + timedelta(days=int(days))).isoformat()
    label = f"{int(days)}-day · {int(requests):,} requests"
    await db.workspaces.update_one({"id": workspace_id}, {"$set": {
        "plan": "pass", "pass_expires_at": expires, "pass_days": int(days),
        "pass_requests_included": int(requests), "pass_requests_used": 0,
        "pass_label": label, "quota_exhausted": False, "quota_exhausted_at": None,
    }})
    await db.subscriptions.update_one({"workspace_id": workspace_id}, {"$set": {
        "id": str(uuid.uuid4()), "workspace_id": workspace_id, "plan_id": "pass",
        "status": "active", "current_period_end": expires, "paid_via": paid_via,
        "pass_days": int(days), "pass_requests": int(requests), "updated_at": now,
    }}, upsert=True)
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()), "workspace_id": workspace_id, "action": "pass.activated",
        "target": ref or label, "before": None,
        "after": {"days": int(days), "requests": int(requests), "paid_via": paid_via, "amount": amount}, "at": now,
    })
    await event_bus.publish("subscription.activated", {"workspace_id": workspace_id, "plan": "pass"})
    return {"expires_at": expires, "label": label}


@router.post("/invoices/{invoice_id}/simulate-payment")
async def simulate_payment(invoice_id: str, ws=Depends(get_billing_workspace)):
    """DEMO ONLY — stands in for a signed QRIS provider webhook. Idempotent. Disabled by default."""
    if not settings.ALLOW_MOCK_PAYMENTS:
        raise HTTPException(status_code=403, detail="Mock payments are disabled.")
    inv = await db.invoices.find_one({"id": invoice_id, "workspace_id": ws["id"]})
    if not inv:
        raise HTTPException(status_code=404, detail="Not found")
    if inv["status"] == "paid":
        return {"status": "paid", "already": True}
    if inv["status"] not in ("pending", "draft"):
        raise HTTPException(status_code=400, detail=f"Invoice is {inv['status']}")
    await _activate(inv, ws.get("name", "Workspace"))
    return {"status": "paid", "plan": inv["plan_id"]}
