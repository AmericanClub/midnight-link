"""Team management — members + email invitations with role-based access.

Invitations use opaque secrets.token_urlsafe tokens (like password reset),
stored with expiry. Acceptance is authenticated and requires the invited
email to match the signed-in account, preventing privilege escalation.
Does not touch login/register/JWT internals.
"""
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr

from ..db import db
from ..utils import now_iso
from ..security import get_current_user
from ..providers import email_provider
from .workspace import get_current_workspace, list_user_workspaces

router = APIRouter(prefix="/api/team", tags=["team"])

INVITE_ROLES = {"admin", "member", "billing_manager"}
MANAGE_ROLES = {"owner", "admin"}
INVITE_TTL_DAYS = 14
ROLE_LABELS = {"owner": "Owner", "admin": "Admin", "member": "Member", "billing_manager": "Billing"}


async def get_manage_workspace(request: Request, user=Depends(get_current_user)) -> dict:
    ws_id = request.headers.get("X-Workspace-Id")
    workspaces = await list_user_workspaces(user["id"])
    ws = next((w for w in workspaces if w["id"] == ws_id), None) if ws_id else (workspaces[0] if workspaces else None)
    if not ws:
        raise HTTPException(status_code=404, detail="Not found")
    if ws.get("role") not in MANAGE_ROLES:
        raise HTTPException(status_code=403, detail="Only workspace owners or admins can manage the team")
    return ws


def _oid(user_id: str):
    try:
        return ObjectId(user_id)
    except (InvalidId, TypeError):
        return None


def _invite_public(inv: dict) -> dict:
    return {
        "id": inv["id"], "email": inv["email"], "role": inv["role"],
        "role_label": ROLE_LABELS.get(inv["role"], inv["role"]),
        "status": inv.get("status", "pending"), "created_at": inv["created_at"],
        "expires_at": inv.get("expires_at"),
    }


def _is_expired(inv: dict) -> bool:
    exp = inv.get("expires_at")
    if not exp:
        return False
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp)
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp < datetime.now(timezone.utc)


# ------------------------------ members ---------------------------------- #
@router.get("/members")
async def list_members(ws=Depends(get_current_workspace), user=Depends(get_current_user)):
    members = await db.workspace_members.find({"workspace_id": ws["id"]}).to_list(500)
    oids = [o for o in (_oid(m["user_id"]) for m in members) if o]
    users = await db.users.find({"_id": {"$in": oids}}).to_list(500)
    umap = {str(u["_id"]): u for u in users}
    my_role = next((m["role"] for m in members if m["user_id"] == user["id"]), "member")
    rows = []
    for m in members:
        u = umap.get(m["user_id"])
        rows.append({
            "user_id": m["user_id"],
            "name": (u or {}).get("name", "—"),
            "email": (u or {}).get("email", "—"),
            "role": m["role"],
            "role_label": ROLE_LABELS.get(m["role"], m["role"]),
            "is_owner": m["user_id"] == ws.get("owner_id"),
            "is_you": m["user_id"] == user["id"],
            "joined_at": m.get("created_at"),
        })
    rows.sort(key=lambda r: (not r["is_owner"], r["email"]))
    invites = await db.invitations.find(
        {"workspace_id": ws["id"], "status": "pending"}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    return {"members": rows, "invitations": [_invite_public(i) for i in invites], "your_role": my_role}


class RoleInput(BaseModel):
    role: str


@router.patch("/members/{user_id}")
async def change_role(user_id: str, payload: RoleInput, ws=Depends(get_manage_workspace)):
    if payload.role not in INVITE_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of {sorted(INVITE_ROLES)}")
    if user_id == ws.get("owner_id"):
        raise HTTPException(status_code=400, detail="The workspace owner's role cannot be changed")
    member = await db.workspace_members.find_one({"workspace_id": ws["id"], "user_id": user_id})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    await db.workspace_members.update_one(
        {"workspace_id": ws["id"], "user_id": user_id}, {"$set": {"role": payload.role}})
    return {"ok": True, "role": payload.role}


@router.delete("/members/{user_id}")
async def remove_member(user_id: str, ws=Depends(get_manage_workspace)):
    if user_id == ws.get("owner_id"):
        raise HTTPException(status_code=400, detail="The workspace owner cannot be removed")
    res = await db.workspace_members.delete_one({"workspace_id": ws["id"], "user_id": user_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"ok": True}


# ------------------------------ invitations ------------------------------ #
class InviteInput(BaseModel):
    email: EmailStr
    role: str = "member"


@router.post("/invitations")
async def create_invitation(payload: InviteInput, request: Request, ws=Depends(get_manage_workspace), user=Depends(get_current_user)):
    if payload.role not in INVITE_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of {sorted(INVITE_ROLES)}")
    email = payload.email.lower().strip()

    existing_user = await db.users.find_one({"email": email})
    if existing_user:
        member = await db.workspace_members.find_one(
            {"workspace_id": ws["id"], "user_id": str(existing_user["_id"])})
        if member:
            raise HTTPException(status_code=409, detail="This person is already a member of the workspace")

    await db.invitations.delete_many({"workspace_id": ws["id"], "email": email, "status": "pending"})
    token = secrets.token_urlsafe(32)
    inv = {
        "id": str(uuid.uuid4()), "workspace_id": ws["id"], "workspace_name": ws.get("name"),
        "email": email, "role": payload.role, "token": token, "status": "pending",
        "invited_by": user["id"], "created_at": now_iso(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)).isoformat(),
    }
    await db.invitations.insert_one({**inv})
    accept_path = f"/accept-invite?token={token}"
    await email_provider.send(
        email, f"You're invited to {ws.get('name')} on MidGate",
        f"You've been invited as {ROLE_LABELS.get(payload.role)}. Accept: {accept_path}")
    return {**_invite_public(inv), "token": token, "accept_path": accept_path}


@router.delete("/invitations/{invite_id}")
async def revoke_invitation(invite_id: str, ws=Depends(get_manage_workspace)):
    res = await db.invitations.update_one(
        {"id": invite_id, "workspace_id": ws["id"], "status": "pending"},
        {"$set": {"status": "revoked"}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Invitation not found")
    return {"ok": True}


@router.get("/invitations/lookup/{token}")
async def lookup_invitation(token: str):
    inv = await db.invitations.find_one({"token": token}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found")
    status = inv.get("status", "pending")
    if status == "pending" and _is_expired(inv):
        status = "expired"
    return {"workspace_name": inv.get("workspace_name"), "email": inv["email"],
            "role": inv["role"], "role_label": ROLE_LABELS.get(inv["role"], inv["role"]),
            "status": status}


class AcceptInput(BaseModel):
    token: str


@router.post("/invitations/accept")
async def accept_invitation(payload: AcceptInput, user=Depends(get_current_user)):
    inv = await db.invitations.find_one({"token": payload.token})
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if inv.get("status") == "revoked":
        raise HTTPException(status_code=400, detail="This invitation has been revoked")
    if inv.get("status") == "accepted":
        return {"ok": True, "workspace_id": inv["workspace_id"], "already": True}
    if _is_expired(inv):
        raise HTTPException(status_code=400, detail="This invitation has expired")
    if user["email"].lower().strip() != inv["email"].lower().strip():
        raise HTTPException(status_code=403,
                            detail=f"This invitation is for {inv['email']}. Sign in with that email to accept.")
    existing = await db.workspace_members.find_one(
        {"workspace_id": inv["workspace_id"], "user_id": user["id"]})
    if not existing:
        await db.workspace_members.insert_one({
            "id": str(uuid.uuid4()), "workspace_id": inv["workspace_id"],
            "user_id": user["id"], "role": inv["role"], "created_at": now_iso()})
    await db.invitations.update_one({"token": payload.token},
                                    {"$set": {"status": "accepted", "accepted_at": now_iso()}})
    from .notifications import create_notification
    await create_notification(
        inv["workspace_id"], "member_joined", "New team member",
        f"{user.get('name') or user['email']} joined the workspace as {ROLE_LABELS.get(inv['role'], inv['role'])}.",
        "success", {"email": user["email"], "role": inv["role"]})
    return {"ok": True, "workspace_id": inv["workspace_id"]}
