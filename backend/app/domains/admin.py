import ipaddress
import uuid

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from ..db import db
from ..utils import now_iso
from ..security import get_current_user
from ..intel import feeds_state, refresh_tor
from .security import invalidate_global

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def require_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


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
    return {
        "users": users, "workspaces": workspaces, "links": links, "qr": qr,
        "events": events, "blocked": blocked, "challenged": challenged,
        "api_checks": api_checks, "api_keys": api_keys, "paid_invoices": paid,
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
    rows = await db.users.find(flt, {"_id": 1, "name": 1, "email": 1, "role": 1, "created_at": 1}).sort("created_at", -1).limit(limit).to_list(limit)
    for r in rows:
        r["id"] = str(r.pop("_id"))
    return {"items": rows}


@router.get("/workspaces")
async def workspaces(admin=Depends(require_admin), limit: int = Query(50, le=200)):
    rows = await db.workspaces.find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    for w in rows:
        w["link_count"] = await db.links.count_documents({"workspace_id": w["id"]})
        w["member_count"] = await db.workspace_members.count_documents({"workspace_id": w["id"]})
    return {"items": rows}


@router.get("/api-usage")
async def api_usage(admin=Depends(require_admin)):
    rows = await db.api_keys.find({}, {"_id": 0, "key_hash": 0}).sort("request_count", -1).limit(50).to_list(50)
    return {"items": rows}
