import re
import uuid

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from ..db import db
from ..security import get_current_user
from ..utils import now_iso, gen_alias
from ..url_safety import validate_destination, UnsafeURLError
from .workspace import get_current_workspace

router = APIRouter(prefix="/api/links", tags=["links"])

ALIAS_RE = re.compile(r"^[a-zA-Z0-9_-]{3,50}$")
VALID_REDIRECT = {302, 307, 308}


class LinkCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    destination_url: str
    alias: str | None = None
    description: str | None = Field(default=None, max_length=500)
    tags: list[str] = Field(default_factory=list)
    redirect_type: int = 302
    expires_at: str | None = None
    max_clicks: int | None = None
    fallback_url: str | None = None


class LinkUpdate(BaseModel):
    name: str | None = None
    destination_url: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    redirect_type: int | None = None
    expires_at: str | None = None
    max_clicks: int | None = None
    fallback_url: str | None = None


def _clean(link: dict) -> dict:
    link.pop("_id", None)
    link["short_path"] = f"/api/r/{link['alias']}"
    return link


async def _unique_alias(alias: str):
    if await db.links.find_one({"alias": alias}):
        raise HTTPException(status_code=409, detail="This alias is already taken")


# ------------------------------ handlers ---------------------------------- #
@router.post("")
async def create_link(payload: LinkCreate, ws=Depends(get_current_workspace), user=Depends(get_current_user)):
    try:
        destination = validate_destination(payload.destination_url)
    except UnsafeURLError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if payload.redirect_type not in VALID_REDIRECT:
        raise HTTPException(status_code=400, detail="Redirect type must be 302, 307 or 308")

    if payload.alias:
        alias = payload.alias.strip()
        if not ALIAS_RE.match(alias):
            raise HTTPException(status_code=400, detail="Alias must be 3-50 chars: letters, numbers, - or _")
        await _unique_alias(alias)
    else:
        alias = gen_alias()
        while await db.links.find_one({"alias": alias}):
            alias = gen_alias()

    fallback = None
    if payload.fallback_url:
        try:
            fallback = validate_destination(payload.fallback_url)
        except UnsafeURLError as e:
            raise HTTPException(status_code=400, detail=f"Fallback: {e}")

    link = {
        "id": str(uuid.uuid4()),
        "workspace_id": ws["id"],
        "name": payload.name.strip(),
        "destination_url": destination,
        "alias": alias,
        "description": payload.description,
        "tags": payload.tags,
        "status": "active",
        "redirect_type": payload.redirect_type,
        "expires_at": payload.expires_at,
        "max_clicks": payload.max_clicks,
        "fallback_url": fallback,
        "click_count": 0,
        "created_by": user["id"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.links.insert_one({**link})
    return _clean(link)


@router.get("")
async def list_links(ws=Depends(get_current_workspace), search: str | None = Query(None),
                     status: str | None = Query(None), limit: int = Query(50, le=200), skip: int = 0):
    flt = {"workspace_id": ws["id"]}
    if status:
        flt["status"] = status
    if search:
        flt["$or"] = [{"name": {"$regex": search, "$options": "i"}},
                      {"alias": {"$regex": search, "$options": "i"}},
                      {"destination_url": {"$regex": search, "$options": "i"}}]
    total = await db.links.count_documents(flt)
    cur = db.links.find(flt).sort("created_at", -1).skip(skip).limit(limit)
    items = [_clean(x) async for x in cur]
    return {"items": items, "total": total}


async def _get_owned(link_id: str, ws: dict) -> dict:
    link = await db.links.find_one({"id": link_id, "workspace_id": ws["id"]})
    if not link:
        raise HTTPException(status_code=404, detail="Not found")
    return link


@router.get("/{link_id}")
async def get_link(link_id: str, ws=Depends(get_current_workspace)):
    return _clean(await _get_owned(link_id, ws))


@router.patch("/{link_id}")
async def update_link(link_id: str, payload: LinkUpdate, ws=Depends(get_current_workspace)):
    await _get_owned(link_id, ws)
    updates = {}
    data = payload.model_dump(exclude_unset=True)
    if "destination_url" in data and data["destination_url"]:
        try:
            updates["destination_url"] = validate_destination(data["destination_url"])
        except UnsafeURLError as e:
            raise HTTPException(status_code=400, detail=str(e))
    if "fallback_url" in data and data["fallback_url"]:
        try:
            updates["fallback_url"] = validate_destination(data["fallback_url"])
        except UnsafeURLError as e:
            raise HTTPException(status_code=400, detail=f"Fallback: {e}")
    if "redirect_type" in data and data["redirect_type"] is not None:
        if data["redirect_type"] not in VALID_REDIRECT:
            raise HTTPException(status_code=400, detail="Redirect type must be 302, 307 or 308")
        updates["redirect_type"] = data["redirect_type"]
    for f in ["name", "description", "tags", "expires_at", "max_clicks"]:
        if f in data:
            updates[f] = data[f]
    updates["updated_at"] = now_iso()
    await db.links.update_one({"id": link_id}, {"$set": updates})
    return _clean(await db.links.find_one({"id": link_id}))


@router.post("/{link_id}/pause")
async def pause_link(link_id: str, ws=Depends(get_current_workspace)):
    await _get_owned(link_id, ws)
    await db.links.update_one({"id": link_id}, {"$set": {"status": "paused", "updated_at": now_iso()}})
    return _clean(await db.links.find_one({"id": link_id}))


@router.post("/{link_id}/resume")
async def resume_link(link_id: str, ws=Depends(get_current_workspace)):
    await _get_owned(link_id, ws)
    await db.links.update_one({"id": link_id}, {"$set": {"status": "active", "updated_at": now_iso()}})
    return _clean(await db.links.find_one({"id": link_id}))


@router.delete("/{link_id}")
async def delete_link(link_id: str, ws=Depends(get_current_workspace)):
    await _get_owned(link_id, ws)
    await db.links.delete_one({"id": link_id})
    await db.analytics_events.delete_many({"link_id": link_id})
    return {"ok": True}
