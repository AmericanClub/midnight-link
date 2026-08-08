import ipaddress
import re
import uuid
from datetime import datetime, timezone, timedelta

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from ..db import db
from ..utils import now_iso
from ..security import get_current_user
from ..intel import feeds_state, refresh_tor
from .security import invalidate_global

router = APIRouter(prefix="/api/admin", tags=["admin"])

PLATFORM_ROLES = {"admin", "user"}


async def require_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def _day_buckets(days: int):
    today = datetime.now(timezone.utc).date()
    return [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]


def _to_day(v):
    if isinstance(v, datetime):
        return v.astimezone(timezone.utc).date().isoformat()
    if isinstance(v, str):
        return v[:10]
    return None


@router.get("/overview")
async def overview(admin=Depends(require_admin)):
    users = await db.users.count_documents({})
    workspaces = await db.workspaces.count_documents({})
    links = await db.links.count_documents({"is_qr": {"$ne": True}})
    qr = await db.links.count_documents({"is_qr": True})
    events = await db.analytics_events.count_documents({})
    blocked = await db.analytics_events.count_documents({"decision": "block"})
    challenged = await db.analytics_events.count_documents({"decision": "challenge"})
    api_checks = await db.analytics_events.count_documents({"source": "api"})
    api_keys = await db.api_keys.count_documents({"revoked": {"$ne": True}})
    paid = await db.invoices.count_documents({"status": "paid"})
    pending_invoices = await db.invoices.count_documents({"status": "pending"})
    suspended_users = await db.users.count_documents({"suspended": True})
    suspended_ws = await db.workspaces.count_documents({"suspended": True})
    open_tickets = await db.tickets.count_documents({"status": {"$in": ["open", "pending"]}})

    rev = await db.invoices.aggregate([
        {"$match": {"status": "paid"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]).to_list(1)
    revenue = rev[0]["total"] if rev else 0

    plan_rows = await db.workspaces.aggregate([
        {"$group": {"_id": "$plan", "count": {"$sum": 1}}},
    ]).to_list(50)
    by_plan = {(r["_id"] or "free"): r["count"] for r in plan_rows}

    days = 14
    buckets = _day_buckets(days)
    signup_map = {d: 0 for d in buckets}
    for u in await db.users.find({}, {"_id": 0, "created_at": 1}).to_list(100000):
        d = _to_day(u.get("created_at"))
        if d in signup_map:
            signup_map[d] += 1
    signups_series = [{"date": d, "count": signup_map[d]} for d in buckets]

    since_iso = (datetime.now(timezone.utc) - timedelta(days=days - 1)).strftime("%Y-%m-%dT00:00:00+00:00")
    ev_rows = await db.analytics_events.aggregate([
        {"$match": {"occurred_at": {"$gte": since_iso}}},
        {"$group": {"_id": {"$substr": ["$occurred_at", 0, 10]},
                    "clicks": {"$sum": 1},
                    "blocked": {"$sum": {"$cond": [{"$eq": ["$decision", "block"]}, 1, 0]}}}},
    ]).to_list(1000)
    ev_map = {r["_id"]: r for r in ev_rows}
    events_series = [{"date": d, "clicks": ev_map.get(d, {}).get("clicks", 0),
                      "blocked": ev_map.get(d, {}).get("blocked", 0)} for d in buckets]

    return {
        "users": users, "workspaces": workspaces, "links": links, "qr": qr,
        "events": events, "blocked": blocked, "challenged": challenged,
        "api_checks": api_checks, "api_keys": api_keys, "paid_invoices": paid,
        "pending_invoices": pending_invoices, "suspended_users": suspended_users,
        "suspended_workspaces": suspended_ws, "open_tickets": open_tickets,
        "revenue": revenue, "by_plan": by_plan,
        "signups_series": signups_series, "events_series": events_series,
        "feeds": feeds_state(),
    }


@router.get("/security-events")
async def security_events(admin=Depends(require_admin), limit: int = Query(50, le=200), skip: int = 0):
    flt = {"decision": {"$in": ["block", "challenge"]}}
    total = await db.analytics_events.count_documents(flt)
    rows = await db.analytics_events.find(
        flt, {"_id": 0, "visitor_id": 0}
    ).sort("occurred_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"items": rows, "total": total}


@router.get("/feeds")
async def feeds(admin=Depends(require_admin)):
    return feeds_state()


@router.post("/feeds/refresh")
async def feeds_refresh(admin=Depends(require_admin)):
    count = await refresh_tor()
    return {"ok": True, "tor_count": count, **feeds_state()}


class BlockEntry(BaseModel):
    value: str
    note: str | None = None


@router.get("/global-blocklist")
async def list_global(admin=Depends(require_admin)):
    rows = await db.global_blocklist.find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    return {"items": rows}


@router.post("/global-blocklist")
async def add_global(payload: BlockEntry, admin=Depends(require_admin)):
    value = payload.value.strip()
    try:
        ipaddress.ip_network(value, strict=False) if "/" in value else ipaddress.ip_address(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Enter a valid IP address or CIDR range")
    doc = {"id": str(uuid.uuid4()), "value": value, "note": payload.note,
           "added_by": admin["email"], "created_at": now_iso()}
    await db.global_blocklist.insert_one({**doc})
    invalidate_global()
    return doc


@router.delete("/global-blocklist/{entry_id}")
async def del_global(entry_id: str, admin=Depends(require_admin)):
    res = await db.global_blocklist.delete_one({"id": entry_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    invalidate_global()
    return {"ok": True}


@router.get("/users")
async def users(admin=Depends(require_admin), search: str | None = Query(None), limit: int = Query(50, le=200)):
    flt = {}
    if search:
        esc = re.escape(search.strip()[:100])
        flt = {"$or": [{"email": {"$regex": esc, "$options": "i"}},
                       {"name": {"$regex": esc, "$options": "i"}}]}
    rows = await db.users.find(flt, {"_id": 1, "name": 1, "email": 1, "role": 1, "created_at": 1, "suspended": 1}).sort("created_at", -1).limit(limit).to_list(limit)
    for r in rows:
        r["id"] = str(r.pop("_id"))
        r["suspended"] = bool(r.get("suspended", False))
    return {"items": rows}


class UserUpdate(BaseModel):
    role: str | None = None
    suspended: bool | None = None


@router.patch("/users/{user_id}")
async def update_user(user_id: str, payload: UserUpdate, admin=Depends(require_admin)):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You can't change your own admin account")
    try:
        oid = ObjectId(user_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="User not found")
    target = await db.users.find_one({"_id": oid})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    updates = {}
    if payload.role is not None:
        if payload.role not in PLATFORM_ROLES:
            raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'")
        if target.get("role") == "admin" and payload.role != "admin":
            if await db.users.count_documents({"role": "admin"}) <= 1:
                raise HTTPException(status_code=400, detail="Can't demote the last admin")
        updates["role"] = payload.role
    if payload.suspended is not None:
        updates["suspended"] = payload.suspended
    if not updates:
        raise HTTPException(status_code=400, detail="Nothing to update")
    await db.users.update_one({"_id": oid}, {"$set": updates})
    return {"ok": True, "id": user_id, **updates}


@router.get("/workspaces")
async def workspaces(admin=Depends(require_admin), limit: int = Query(50, le=200)):
    rows = await db.workspaces.find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    for w in rows:
        w["link_count"] = await db.links.count_documents({"workspace_id": w["id"]})
        w["member_count"] = await db.workspace_members.count_documents({"workspace_id": w["id"]})
        w["suspended"] = bool(w.get("suspended", False))
    return {"items": rows}


class WorkspaceUpdate(BaseModel):
    suspended: bool


@router.patch("/workspaces/{workspace_id}")
async def update_workspace(workspace_id: str, payload: WorkspaceUpdate, admin=Depends(require_admin)):
    ws = await db.workspaces.find_one({"id": workspace_id})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await db.workspaces.update_one({"id": workspace_id}, {"$set": {"suspended": payload.suspended}})
    from .redirect import invalidate_suspended_workspaces
    invalidate_suspended_workspaces()
    return {"ok": True, "id": workspace_id, "suspended": payload.suspended}


@router.get("/revenue")
async def revenue(admin=Depends(require_admin)):
    invoices = await db.invoices.find({}, {"_id": 0, "qris_string": 0}).sort("created_at", -1).limit(100).to_list(100)
    ws_ids = list({i["workspace_id"] for i in invoices})
    ws = await db.workspaces.find({"id": {"$in": ws_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)
    name_map = {w["id"]: w["name"] for w in ws}
    for i in invoices:
        i["workspace_name"] = name_map.get(i["workspace_id"], "—")
    paid_agg = await db.invoices.aggregate([{"$match": {"status": "paid"}}, {"$group": {"_id": None, "total": {"$sum": "$amount"}}}]).to_list(1)
    pend_agg = await db.invoices.aggregate([{"$match": {"status": "pending"}}, {"$group": {"_id": None, "total": {"$sum": "$amount"}}}]).to_list(1)
    return {
        "invoices": invoices,
        "paid_total": paid_agg[0]["total"] if paid_agg else 0,
        "pending_total": pend_agg[0]["total"] if pend_agg else 0,
        "paid_count": await db.invoices.count_documents({"status": "paid"}),
        "pending_count": await db.invoices.count_documents({"status": "pending"}),
    }


@router.get("/api-usage")
async def api_usage(admin=Depends(require_admin)):
    rows = await db.api_keys.find({}, {"_id": 0, "key_hash": 0}).sort("request_count", -1).limit(50).to_list(50)
    return {"items": rows}


# --------------------------- IP intelligence (proxycheck.io) -------------- #
class IPIntelUpdate(BaseModel):
    api_key: str | None = None
    enabled: bool | None = None


@router.get("/ip-intel")
async def ip_intel_status(admin=Depends(require_admin)):
    from ..ip_intel import get_status
    return await get_status()


@router.put("/ip-intel")
async def ip_intel_save(payload: IPIntelUpdate, admin=Depends(require_admin)):
    from ..ip_intel import save_config, get_status
    if payload.api_key is not None and payload.api_key.strip():
        k = payload.api_key.strip()
        if len(k) < 8:
            raise HTTPException(status_code=400, detail="API key looks too short")
    await save_config(api_key=payload.api_key, enabled=payload.enabled, admin_email=admin["email"])
    return await get_status()


@router.post("/ip-intel/test")
async def ip_intel_test(admin=Depends(require_admin)):
    from ..ip_intel import test_connection
    return await test_connection()


@router.delete("/ip-intel/key")
async def ip_intel_remove(admin=Depends(require_admin)):
    from ..ip_intel import remove_key, get_status
    await remove_key()
    return await get_status()


# --------------------- payment (top-up) master switch -------------------- #
class PaymentSettingsUpdate(BaseModel):
    topup_enabled: bool | None = None
    topup_disabled_message: str | None = None


@router.get("/payment-settings")
async def payment_settings_get(admin=Depends(require_admin)):
    from .wallet import get_payment_settings
    return await get_payment_settings()


@router.put("/payment-settings")
async def payment_settings_put(payload: PaymentSettingsUpdate, admin=Depends(require_admin)):
    from .wallet import set_payment_settings
    return await set_payment_settings(
        topup_enabled=payload.topup_enabled,
        topup_disabled_message=payload.topup_disabled_message,
        admin_email=admin["email"],
    )


class PaymentConfigUpdate(BaseModel):
    topup_enabled: bool | None = None
    topup_disabled_message: str | None = None
    rupiah_per_credit: int | None = None
    bonus_percent: float | None = None
    min_topup: int | None = None
    mayar_api_key: str | None = None
    mayar_webhook_token: str | None = None
    mayar_base_url: str | None = None


@router.get("/payment-config")
async def payment_config_get(admin=Depends(require_admin)):
    from .wallet import get_payment_settings, get_credit_settings
    from .. import mayar
    return {
        "payments": await get_payment_settings(),
        "credits": await get_credit_settings(),
        "gateway": await mayar.gateway_status(),
    }


@router.put("/payment-config")
async def payment_config_put(payload: PaymentConfigUpdate, admin=Depends(require_admin)):
    from .wallet import set_payment_settings, set_credit_settings, set_gateway_config
    if payload.topup_enabled is not None or payload.topup_disabled_message is not None:
        await set_payment_settings(topup_enabled=payload.topup_enabled,
                                   topup_disabled_message=payload.topup_disabled_message,
                                   admin_email=admin["email"])
    if any(v is not None for v in (payload.rupiah_per_credit, payload.bonus_percent, payload.min_topup)):
        await set_credit_settings(rupiah_per_credit=payload.rupiah_per_credit,
                                  bonus_percent=payload.bonus_percent,
                                  min_topup=payload.min_topup, admin_email=admin["email"])
    if any(v is not None for v in (payload.mayar_api_key, payload.mayar_webhook_token, payload.mayar_base_url)):
        await set_gateway_config(api_key=payload.mayar_api_key,
                                 webhook_token=payload.mayar_webhook_token,
                                 base_url=payload.mayar_base_url, admin_email=admin["email"])
    return await payment_config_get(admin)


@router.post("/payment-config/test")
async def payment_config_test(admin=Depends(require_admin)):
    from .. import mayar
    if not await mayar.configured():
        return {"ok": False, "message": "API key Mayar belum diatur."}
    try:
        await mayar.list_transactions(page=1, page_size=1)
        return {"ok": True, "message": "Koneksi ke Mayar berhasil."}
    except mayar.MayarError as e:
        return {"ok": False, "message": f"Gagal: {e}"}


# --------------------------- wallets (credit) ---------------------------- #
class WalletAdjust(BaseModel):
    amount: int
    reason: str | None = None


@router.get("/wallets")
async def wallets_overview(admin=Depends(require_admin), search: str | None = Query(None),
                           limit: int = Query(100, le=500)):
    if search:
        esc = re.escape(search.strip()[:100])
        workspaces = await db.workspaces.find(
            {"name": {"$regex": esc, "$options": "i"}},
            {"_id": 0, "id": 1, "name": 1, "plan": 1}).limit(limit).to_list(limit)
        ws_ids = [w["id"] for w in workspaces]
        wallets = {x["workspace_id"]: x for x in
                   await db.wallets.find({"workspace_id": {"$in": ws_ids}}, {"_id": 0}).to_list(10000)}
        ws_docs = workspaces
    else:
        # Default: only workspaces that actually have a wallet, highest balance first.
        wallet_rows = await db.wallets.find({}, {"_id": 0}).sort("balance", -1).limit(limit).to_list(limit)
        wallets = {w["workspace_id"]: w for w in wallet_rows}
        ws_ids = list(wallets.keys())
        ws_docs = await db.workspaces.find(
            {"id": {"$in": ws_ids}}, {"_id": 0, "id": 1, "name": 1, "plan": 1}).to_list(10000)
        order = {wid: i for i, wid in enumerate(ws_ids)}
        ws_docs.sort(key=lambda w: order.get(w["id"], 1e9))

    topup_rows = await db.mayar_payments.aggregate([
        {"$match": {"workspace_id": {"$in": ws_ids}, "credited": True}},
        {"$group": {"_id": "$workspace_id", "total": {"$sum": "$credits"}, "count": {"$sum": 1}}},
    ]).to_list(10000)
    topup_map = {r["_id"]: r for r in topup_rows}
    items = []
    for w in ws_docs:
        wal = wallets.get(w["id"], {})
        tp = topup_map.get(w["id"], {})
        items.append({"workspace_id": w["id"], "name": w["name"], "plan": w.get("plan", "free"),
                      "balance": int(wal.get("balance", 0)),
                      "topup_total": int(tp.get("total", 0)), "topup_count": int(tp.get("count", 0))})
    if search:
        items.sort(key=lambda x: (x["balance"], x["topup_total"]), reverse=True)

    tot = await db.wallets.aggregate([{"$group": {"_id": None, "total": {"$sum": "$balance"}}}]).to_list(1)
    tp_all = await db.mayar_payments.aggregate([
        {"$match": {"credited": True}},
        {"$group": {"_id": None, "total": {"$sum": "$credits"}, "count": {"$sum": 1}}}]).to_list(1)
    pending = await db.mayar_payments.count_documents({"credited": {"$ne": True}, "status": "pending"})
    return {"items": items,
            "total_balance": int(tot[0]["total"]) if tot else 0,
            "total_topup": int(tp_all[0]["total"]) if tp_all else 0,
            "total_topup_count": int(tp_all[0]["count"]) if tp_all else 0,
            "pending_topups": pending}


@router.get("/wallets/{workspace_id}")
async def wallet_detail(workspace_id: str, admin=Depends(require_admin)):
    ws = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0, "id": 1, "name": 1, "plan": 1})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    wal = await db.wallets.find_one({"workspace_id": workspace_id}, {"_id": 0})
    ledger = await db.wallet_ledger.find(
        {"workspace_id": workspace_id}, {"_id": 0}).sort("created_at", -1).limit(200).to_list(200)
    topups = await db.mayar_payments.find(
        {"workspace_id": workspace_id}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    return {"workspace": ws, "balance": int((wal or {}).get("balance", 0)),
            "ledger": ledger, "topups": topups}


@router.post("/wallets/{workspace_id}/adjust")
async def wallet_adjust(workspace_id: str, payload: WalletAdjust, admin=Depends(require_admin)):
    from .wallet import _apply, _get_wallet
    if payload.amount == 0:
        raise HTTPException(status_code=400, detail="Amount cannot be zero")
    ws = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0, "id": 1})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    w = await _get_wallet(workspace_id)
    if payload.amount < 0 and int(w.get("balance", 0)) + payload.amount < 0:
        raise HTTPException(status_code=400, detail="Adjustment would make the balance negative")
    ttype = "refund" if payload.amount > 0 else "adjustment"
    default_reason = "Manual credit by admin" if payload.amount > 0 else "Manual adjustment by admin"
    balance_after, entry = await _apply(
        workspace_id, int(payload.amount), ttype, payload.reason or default_reason, actor=admin["email"])
    return {"ok": True, "balance": balance_after, "entry": entry}

