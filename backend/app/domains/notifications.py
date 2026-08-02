"""Notification Center — workspace-scoped in-app alerts.

A shared feed per workspace (visible to all members) with unread tracking.
Producers: blocked traffic (throttled), failed webhook deliveries (throttled),
new members joined, custom domains verified. Decoupled via the EventBus for
traffic events; called directly for the rest.
"""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..db import db
from ..utils import now_iso
from .workspace import get_current_workspace

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

LEVELS = {"info", "success", "warning", "error"}
_MAX_KEEP = 200


async def create_notification(workspace_id: str, ntype: str, title: str, body: str,
                              level: str = "info", meta: dict | None = None) -> dict:
    doc = {
        "id": str(uuid.uuid4()), "workspace_id": workspace_id, "type": ntype,
        "title": title, "body": body, "level": level if level in LEVELS else "info",
        "meta": meta or {}, "read": False, "created_at": now_iso(),
    }
    await db.notifications.insert_one({**doc})
    count = await db.notifications.count_documents({"workspace_id": workspace_id})
    if count > _MAX_KEEP:
        old = await db.notifications.find(
            {"workspace_id": workspace_id}, {"id": 1, "_id": 0}
        ).sort("created_at", 1).to_list(count - _MAX_KEEP)
        ids = [o["id"] for o in old]
        if ids:
            await db.notifications.delete_many({"id": {"$in": ids}})
    return doc


async def notify_throttled(workspace_id: str, ntype: str, dedupe: str, window_seconds: int,
                           title: str, body: str, level: str = "info", meta: dict | None = None):
    since = (datetime.now(timezone.utc) - timedelta(seconds=window_seconds)).isoformat()
    existing = await db.notifications.find_one({
        "workspace_id": workspace_id, "type": ntype,
        "meta.dedupe": dedupe, "created_at": {"$gte": since},
    })
    if existing:
        return None
    return await create_notification(workspace_id, ntype, title, body, level, {**(meta or {}), "dedupe": dedupe})


def wire_notifications():
    """Emit a throttled alert whenever traffic is blocked on a link."""
    from ..providers import event_bus

    async def on_click(event):
        if event.get("decision") != "block":
            return
        ws = event.get("workspace_id")
        if not ws:
            return
        alias = event.get("alias") or "link"
        reasons = event.get("risk_reasons") or []
        reason = ", ".join(reasons) if reasons else (event.get("bot_category") or "policy")
        await notify_throttled(
            ws, "traffic_blocked", f"blk:{event.get('link_id') or alias}", 3600,
            title="Blocked suspicious traffic",
            body=f"A visitor to /{alias} was blocked ({reason}).",
            level="warning",
            meta={"alias": alias, "link_id": event.get("link_id"), "country": event.get("country")},
        )

    event_bus.subscribe("link.clicked", on_click)


@router.get("")
async def list_notifications(unread_only: bool = False, ws=Depends(get_current_workspace)):
    q = {"workspace_id": ws["id"]}
    if unread_only:
        q["read"] = False
    items = await db.notifications.find(q, {"_id": 0}).sort("created_at", -1).to_list(50)
    unread = await db.notifications.count_documents({"workspace_id": ws["id"], "read": False})
    return {"items": items, "unread_count": unread}


@router.get("/unread-count")
async def unread_count(ws=Depends(get_current_workspace)):
    return {"count": await db.notifications.count_documents({"workspace_id": ws["id"], "read": False})}


@router.post("/{notification_id}/read")
async def mark_read(notification_id: str, ws=Depends(get_current_workspace)):
    await db.notifications.update_one(
        {"id": notification_id, "workspace_id": ws["id"]}, {"$set": {"read": True}})
    return {"ok": True}


@router.post("/read-all")
async def mark_all_read(ws=Depends(get_current_workspace)):
    res = await db.notifications.update_many(
        {"workspace_id": ws["id"], "read": False}, {"$set": {"read": True}})
    return {"ok": True, "updated": res.modified_count}


@router.delete("/{notification_id}")
async def dismiss(notification_id: str, ws=Depends(get_current_workspace)):
    await db.notifications.delete_one({"id": notification_id, "workspace_id": ws["id"]})
    return {"ok": True}
