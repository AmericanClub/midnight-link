import uuid

from fastapi import APIRouter, Request, HTTPException, Depends

from ..db import db
from ..security import get_current_user
from ..utils import now_iso

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


async def create_default_workspace(user_id: str, owner_name: str) -> dict:
    ws_id = str(uuid.uuid4())
    slug = f"ws-{ws_id[:8]}"
    workspace = {
        "id": ws_id,
        "name": f"{owner_name}'s Workspace",
        "slug": slug,
        "owner_id": user_id,
        "plan": "free",
        "created_at": now_iso(),
    }
    await db.workspaces.insert_one({**workspace})
    await db.workspace_members.insert_one({
        "id": str(uuid.uuid4()),
        "workspace_id": ws_id,
        "user_id": user_id,
        "role": "owner",
        "created_at": now_iso(),
    })
    return workspace


async def list_user_workspaces(user_id: str) -> list:
    members = await db.workspace_members.find({"user_id": user_id}).to_list(100)
    ws_ids = [m["workspace_id"] for m in members]
    role_map = {m["workspace_id"]: m["role"] for m in members}
    workspaces = await db.workspaces.find({"id": {"$in": ws_ids}}, {"_id": 0}).to_list(100)
    primaries = await db.custom_domains.find(
        {"workspace_id": {"$in": ws_ids}, "is_primary": True, "status": "verified"},
        {"_id": 0, "workspace_id": 1, "domain": 1},
    ).to_list(100)
    primary_map = {p["workspace_id"]: p["domain"] for p in primaries}
    for w in workspaces:
        w["role"] = role_map.get(w["id"], "member")
        w["primary_domain"] = primary_map.get(w["id"])
    return workspaces


async def assert_member(user_id: str, workspace_id: str) -> dict:
    member = await db.workspace_members.find_one({"user_id": user_id, "workspace_id": workspace_id})
    if not member:
        # 404 so resource existence is never leaked cross-tenant
        raise HTTPException(status_code=404, detail="Not found")
    return member


async def get_current_workspace(request: Request, user=Depends(get_current_user)) -> dict:
    ws_id = request.headers.get("X-Workspace-Id")
    if ws_id:
        await assert_member(user["id"], ws_id)
        ws = await db.workspaces.find_one({"id": ws_id}, {"_id": 0})
        if not ws:
            raise HTTPException(status_code=404, detail="Not found")
        return ws
    workspaces = await list_user_workspaces(user["id"])
    if not workspaces:
        raise HTTPException(status_code=404, detail="No workspace")
    return workspaces[0]


@router.get("")
async def list_workspaces(user=Depends(get_current_user)):
    return await list_user_workspaces(user["id"])


@router.get("/current")
async def current(ws=Depends(get_current_workspace)):
    return ws
