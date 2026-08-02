"""Outgoing webhooks — HMAC-signed delivery of link events to customer URLs.

Events flow through the in-memory EventBus (link.clicked). This module maps
each click into subscribable webhook event types and delivers a signed JSON
payload with retry + a persisted delivery log. Never leaks visitor PII.
"""
import asyncio
import hashlib
import hmac
import json
import secrets
import time
import uuid

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ..db import db
from ..utils import now_iso
from ..url_safety import validate_destination, UnsafeURLError
from .workspace import get_current_workspace

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

EVENT_TYPES = ["click.recorded", "click.blocked", "click.challenged"]
_RETRY_DELAYS = (0, 2, 5)  # 3 attempts with backoff
_EVENT_FIELDS = ["alias", "link_id", "event_type", "country", "device", "browser", "os",
                 "referrer", "is_bot", "bot_category", "risk_score", "decision",
                 "risk_reasons", "matched_rule_id", "occurred_at"]


# --------------------------- signing + delivery -------------------------- #
def sign(secret: str, timestamp: str, body: bytes) -> str:
    msg = f"{timestamp}.".encode() + body
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


async def _post(url: str, body: bytes, headers: dict):
    import requests

    def _do():
        return requests.post(url, data=body, headers=headers, timeout=8)

    return await asyncio.to_thread(_do)


async def deliver(webhook: dict, event_type: str, data: dict) -> dict:
    delivery_id = str(uuid.uuid4())
    payload = {"id": delivery_id, "type": event_type, "created_at": now_iso(), "data": data}
    body = json.dumps(payload, separators=(",", ":")).encode()
    ts = str(int(time.time()))
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "MidGate-Webhooks/1.0",
        "X-MidGate-Event": event_type,
        "X-MidGate-Delivery": delivery_id,
        "X-MidGate-Signature": f"t={ts},v1={sign(webhook['secret'], ts, body)}",
    }
    attempts, status, status_code, error = 0, "failed", None, None
    for delay in _RETRY_DELAYS:
        if delay:
            await asyncio.sleep(delay)
        attempts += 1
        try:
            resp = await _post(webhook["url"], body, headers)
            status_code = resp.status_code
            if 200 <= resp.status_code < 300:
                status, error = "success", None
                break
            error = f"HTTP {resp.status_code}"
        except Exception as e:
            error = str(e)[:300]

    record = {
        "id": delivery_id, "webhook_id": webhook["id"], "workspace_id": webhook["workspace_id"],
        "event_type": event_type, "status": status, "status_code": status_code,
        "attempts": attempts, "error": error, "data": data, "created_at": now_iso(),
    }
    await db.webhook_deliveries.insert_one({**record})
    inc = {"success_count" if status == "success" else "failure_count": 1}
    await db.webhooks.update_one({"id": webhook["id"]},
                                 {"$set": {"last_delivery_at": now_iso()}, "$inc": inc})
    if status == "failed":
        from .notifications import notify_throttled
        await notify_throttled(
            webhook["workspace_id"], "webhook_failed", f"wh:{webhook['id']}", 1800,
            title="Webhook delivery failed",
            body=f"Delivery to {webhook['url']} failed after {attempts} attempt(s) ({error or 'no response'}).",
            level="error", meta={"webhook_id": webhook["id"], "event_type": event_type})
    return record


async def dispatch(workspace_id: str, event_type: str, data: dict):
    hooks = await db.webhooks.find(
        {"workspace_id": workspace_id, "enabled": True, "events": event_type}
    ).to_list(100)
    for h in hooks:
        asyncio.create_task(deliver(h, event_type, data))


def wire_webhooks():
    """Subscribe webhook dispatch to the click event stream."""
    from ..providers import event_bus

    async def on_click(event):
        ws = event.get("workspace_id")
        if not ws:
            return
        data = {k: event.get(k) for k in _EVENT_FIELDS}
        await dispatch(ws, "click.recorded", data)
        decision = event.get("decision")
        if decision == "block":
            await dispatch(ws, "click.blocked", data)
        elif decision == "challenge":
            await dispatch(ws, "click.challenged", data)

    event_bus.subscribe("link.clicked", on_click)


# --------------------------- CRUD ---------------------------------------- #
def _public(w: dict) -> dict:
    return {
        "id": w["id"], "url": w["url"], "description": w.get("description"),
        "events": w.get("events", []), "enabled": w.get("enabled", True),
        "secret_prefix": (w.get("secret", "")[:11] + "…") if w.get("secret") else "",
        "success_count": w.get("success_count", 0), "failure_count": w.get("failure_count", 0),
        "last_delivery_at": w.get("last_delivery_at"), "created_at": w["created_at"],
    }


class WebhookCreate(BaseModel):
    url: str
    description: str | None = Field(default=None, max_length=200)
    events: list[str] = Field(default_factory=lambda: list(EVENT_TYPES))


class WebhookUpdate(BaseModel):
    url: str | None = None
    description: str | None = None
    events: list[str] | None = None
    enabled: bool | None = None


def _validate_events(events: list[str]):
    if not events:
        raise HTTPException(status_code=400, detail="Select at least one event")
    bad = [e for e in events if e not in EVENT_TYPES]
    if bad:
        raise HTTPException(status_code=400, detail=f"Unknown event(s): {', '.join(bad)}")


def _validate_url(url: str) -> str:
    try:
        return validate_destination(url)
    except UnsafeURLError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/events")
async def list_event_types(ws=Depends(get_current_workspace)):
    return {"events": EVENT_TYPES}


@router.get("")
async def list_webhooks(ws=Depends(get_current_workspace)):
    rows = await db.webhooks.find({"workspace_id": ws["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"items": [_public(r) for r in rows]}


@router.post("")
async def create_webhook(payload: WebhookCreate, ws=Depends(get_current_workspace)):
    url = _validate_url(payload.url)
    _validate_events(payload.events)
    secret = "whsec_" + secrets.token_hex(24)
    doc = {
        "id": str(uuid.uuid4()), "workspace_id": ws["id"], "url": url,
        "description": payload.description, "events": payload.events, "secret": secret,
        "enabled": True, "success_count": 0, "failure_count": 0,
        "last_delivery_at": None, "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.webhooks.insert_one({**doc})
    return {**_public(doc), "secret": secret}


async def _owned(webhook_id: str, ws: dict) -> dict:
    w = await db.webhooks.find_one({"id": webhook_id, "workspace_id": ws["id"]})
    if not w:
        raise HTTPException(status_code=404, detail="Not found")
    return w


@router.patch("/{webhook_id}")
async def update_webhook(webhook_id: str, payload: WebhookUpdate, ws=Depends(get_current_workspace)):
    await _owned(webhook_id, ws)
    updates = {"updated_at": now_iso()}
    data = payload.model_dump(exclude_unset=True)
    if "url" in data and data["url"] is not None:
        updates["url"] = _validate_url(data["url"])
    if "events" in data and data["events"] is not None:
        _validate_events(data["events"])
        updates["events"] = data["events"]
    if "description" in data:
        updates["description"] = data["description"]
    if "enabled" in data and data["enabled"] is not None:
        updates["enabled"] = data["enabled"]
    await db.webhooks.update_one({"id": webhook_id}, {"$set": updates})
    return _public(await db.webhooks.find_one({"id": webhook_id}, {"_id": 0}))


@router.post("/{webhook_id}/rotate-secret")
async def rotate_secret(webhook_id: str, ws=Depends(get_current_workspace)):
    await _owned(webhook_id, ws)
    secret = "whsec_" + secrets.token_hex(24)
    await db.webhooks.update_one({"id": webhook_id}, {"$set": {"secret": secret, "updated_at": now_iso()}})
    return {"secret": secret}


@router.post("/{webhook_id}/test")
async def test_webhook(webhook_id: str, ws=Depends(get_current_workspace)):
    w = await _owned(webhook_id, ws)
    result = await deliver(w, "ping", {
        "message": "This is a test event from MidGate.",
        "workspace_id": ws["id"], "sample": True,
    })
    return {"delivery": result}


@router.get("/{webhook_id}/deliveries")
async def list_deliveries(webhook_id: str, ws=Depends(get_current_workspace)):
    await _owned(webhook_id, ws)
    rows = await db.webhook_deliveries.find(
        {"webhook_id": webhook_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return {"items": rows}


@router.post("/{webhook_id}/deliveries/{delivery_id}/retry")
async def retry_delivery(webhook_id: str, delivery_id: str, ws=Depends(get_current_workspace)):
    w = await _owned(webhook_id, ws)
    d = await db.webhook_deliveries.find_one(
        {"id": delivery_id, "webhook_id": webhook_id, "workspace_id": ws["id"]})
    if not d:
        raise HTTPException(status_code=404, detail="Not found")
    result = await deliver(w, d["event_type"], d.get("data") or {})
    return {"delivery": result}


@router.delete("/{webhook_id}")
async def delete_webhook(webhook_id: str, ws=Depends(get_current_workspace)):
    res = await db.webhooks.delete_one({"id": webhook_id, "workspace_id": ws["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await db.webhook_deliveries.delete_many({"webhook_id": webhook_id})
    return {"ok": True}
