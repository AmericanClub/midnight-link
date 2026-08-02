import ipaddress
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
        flt = {"$or": [{"email": {"$regex": search, "$options": "i"}},
                       {"name": {"$regex": search, "$options": "i"}}]}
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
