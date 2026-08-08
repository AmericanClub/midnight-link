"""Support tickets — customer reporting with threaded replies.

Anyone (public visitor or signed-in user) can open a ticket; the PLATFORM
admin (role == 'admin', the Midnight Link site owner) manages every ticket from the
Admin panel: reply, change status/priority. Replies notify the requester via
the in-app notification bell (when the ticket belongs to a workspace).
"""
import uuid

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr, Field

from ..db import db
from ..utils import now_iso
from ..security import get_current_user
from ..intel import rate_limiter
from .notifications import create_notification

router = APIRouter(prefix="/api/support", tags=["support"])

STATUSES = {"open", "pending", "resolved", "closed"}
CATEGORIES = {"bug", "abuse", "billing", "other"}
PRIORITIES = {"low", "medium", "high"}


async def require_platform_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def _message(m: dict) -> dict:
    return {k: m.get(k) for k in ("id", "author", "author_name", "body", "created_at")}


def _summary(t: dict) -> dict:
    msgs = t.get("messages", [])
    return {
        "id": t["id"], "subject": t["subject"], "category": t["category"],
        "priority": t["priority"], "status": t["status"],
        "requester_name": t.get("requester_name"), "requester_email": t.get("requester_email"),
        "is_public": t.get("is_public", False), "message_count": len(msgs),
        "last_message": (msgs[-1]["body"][:140] if msgs else ""),
        "created_at": t["created_at"], "updated_at": t.get("updated_at"),
        "last_reply_at": t.get("last_reply_at"),
    }


def _detail(t: dict) -> dict:
    return {**_summary(t), "workspace_id": t.get("workspace_id"),
            "messages": [_message(m) for m in t.get("messages", [])]}


def _new_message(author: str, name: str, body: str) -> dict:
    return {"id": str(uuid.uuid4()), "author": author, "author_name": name,
            "body": body.strip(), "created_at": now_iso()}


async def _get(ticket_id: str) -> dict:
    t = await db.tickets.find_one({"id": ticket_id})
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return t


# ------------------------------ public ----------------------------------- #
class PublicTicket(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    subject: str = Field(min_length=1, max_length=160)
    category: str = "other"
    message: str = Field(min_length=1, max_length=5000)


@router.post("/public")
async def create_public_ticket(payload: PublicTicket, request: Request):
    ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()
          or (request.client.host if request.client else "unknown"))
    if not rate_limiter.allow(f"contact:{ip}", 5):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again in a minute.")
    category = payload.category if payload.category in CATEGORIES else "other"
    doc = {
        "id": str(uuid.uuid4()), "subject": payload.subject.strip(), "category": category,
        "priority": "medium", "status": "open", "user_id": None, "workspace_id": None,
        "requester_name": payload.name.strip(), "requester_email": payload.email.lower().strip(),
        "is_public": True,
        "messages": [_new_message("user", payload.name.strip(), payload.message)],
        "created_at": now_iso(), "updated_at": now_iso(), "last_reply_at": now_iso(),
    }
    await db.tickets.insert_one({**doc})
    return {"ok": True, "id": doc["id"]}


# --------------------------- authenticated user -------------------------- #
class NewTicket(BaseModel):
    subject: str = Field(min_length=1, max_length=160)
    category: str = "other"
    priority: str = "medium"
    message: str = Field(min_length=1, max_length=5000)


class ReplyInput(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


@router.post("/tickets")
async def create_ticket(payload: NewTicket, request: Request, user=Depends(get_current_user)):
    category = payload.category if payload.category in CATEGORIES else "other"
    priority = payload.priority if payload.priority in PRIORITIES else "medium"
    doc = {
        "id": str(uuid.uuid4()), "subject": payload.subject.strip(), "category": category,
        "priority": priority, "status": "open", "user_id": user["id"],
        "workspace_id": request.headers.get("X-Workspace-Id"), "is_public": False,
        "requester_name": user.get("name"), "requester_email": user["email"],
        "messages": [_new_message("user", user.get("name") or user["email"], payload.message)],
        "created_at": now_iso(), "updated_at": now_iso(), "last_reply_at": now_iso(),
    }
    await db.tickets.insert_one({**doc})
    return _detail(doc)


@router.get("/tickets")
async def my_tickets(user=Depends(get_current_user)):
    rows = await db.tickets.find({"user_id": user["id"]}).sort("updated_at", -1).to_list(100)
    return {"items": [_summary(t) for t in rows]}


@router.get("/tickets/{ticket_id}")
async def my_ticket(ticket_id: str, user=Depends(get_current_user)):
    t = await db.tickets.find_one({"id": ticket_id, "user_id": user["id"]})
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return _detail(t)


@router.post("/tickets/{ticket_id}/reply")
async def user_reply(ticket_id: str, payload: ReplyInput, user=Depends(get_current_user)):
    t = await db.tickets.find_one({"id": ticket_id, "user_id": user["id"]})
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    msg = _new_message("user", user.get("name") or user["email"], payload.body)
    await db.tickets.update_one({"id": ticket_id}, {
        "$push": {"messages": msg},
        "$set": {"status": "open", "updated_at": now_iso(), "last_reply_at": now_iso()},
    })
    return _detail(await _get(ticket_id))


# ------------------------------ platform admin --------------------------- #
@router.get("/admin/tickets")
async def admin_list(status: str | None = None, admin=Depends(require_platform_admin)):
    flt = {}
    if status and status in STATUSES:
        flt["status"] = status
    rows = await db.tickets.find(flt).sort("last_reply_at", -1).to_list(200)
    open_count = await db.tickets.count_documents({"status": {"$in": ["open", "pending"]}})
    return {"items": [_summary(t) for t in rows], "open_count": open_count}


@router.get("/admin/tickets/{ticket_id}")
async def admin_get(ticket_id: str, admin=Depends(require_platform_admin)):
    return _detail(await _get(ticket_id))


@router.post("/admin/tickets/{ticket_id}/reply")
async def admin_reply(ticket_id: str, payload: ReplyInput, admin=Depends(require_platform_admin)):
    t = await _get(ticket_id)
    msg = _new_message("admin", admin.get("name") or "Support", payload.body)
    await db.tickets.update_one({"id": ticket_id}, {
        "$push": {"messages": msg},
        "$set": {"status": "pending", "updated_at": now_iso(), "last_reply_at": now_iso()},
    })
    if t.get("workspace_id"):
        await create_notification(
            t["workspace_id"], "ticket_reply", "Support replied to your ticket",
            f"Re: {t['subject']}", "info", {"ticket_id": ticket_id})
    return _detail(await _get(ticket_id))


class TicketUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None


@router.patch("/admin/tickets/{ticket_id}")
async def admin_update(ticket_id: str, payload: TicketUpdate, admin=Depends(require_platform_admin)):
    t = await _get(ticket_id)
    updates = {"updated_at": now_iso()}
    if payload.status is not None:
        if payload.status not in STATUSES:
            raise HTTPException(status_code=400, detail=f"status must be one of {sorted(STATUSES)}")
        updates["status"] = payload.status
    if payload.priority is not None:
        if payload.priority not in PRIORITIES:
            raise HTTPException(status_code=400, detail=f"priority must be one of {sorted(PRIORITIES)}")
        updates["priority"] = payload.priority
    await db.tickets.update_one({"id": ticket_id}, {"$set": updates})
    if "status" in updates and t.get("workspace_id"):
        await create_notification(
            t["workspace_id"], "ticket_status", f"Ticket {updates['status']}",
            f"“{t['subject']}” was marked {updates['status']}.", "info", {"ticket_id": ticket_id})
    return _detail(await _get(ticket_id))
