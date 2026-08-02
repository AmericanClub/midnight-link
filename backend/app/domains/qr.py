import uuid

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ..db import db
from ..security import get_current_user
from ..utils import now_iso, gen_alias
from ..url_safety import validate_destination, UnsafeURLError
from .workspace import get_current_workspace
from .links import ALIAS_RE
from .billing import enforce_quota

router = APIRouter(prefix="/api/qr", tags=["qr"])

DEFAULT_STYLE = {
    "fg_color": "#0A0A0A",
    "bg_color": "#FFFFFF",
    "dots_style": "rounded",
    "corners_style": "extra-rounded",
    "logo_url": "",
    "margin": 8,
    "error_correction": "M",
}


class QRStyle(BaseModel):
    fg_color: str = "#0A0A0A"
    bg_color: str = "#FFFFFF"
    dots_style: str = "rounded"
    corners_style: str = "extra-rounded"
    logo_url: str = ""
    margin: int = 8
    error_correction: str = "M"


class QRCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    destination_url: str
    alias: str | None = None
    qr_type: str = "url"
    style: QRStyle = Field(default_factory=QRStyle)


class QRUpdate(BaseModel):
    name: str | None = None
    destination_url: str | None = None
    style: QRStyle | None = None


def _clean(qr: dict) -> dict:
    qr.pop("_id", None)
    qr["short_path"] = f"/api/r/{qr['alias']}"
    return qr


@router.post("")
async def create_qr(payload: QRCreate, ws=Depends(get_current_workspace), user=Depends(get_current_user)):
    await enforce_quota(ws, "dynamic_qr")
    try:
        destination = validate_destination(payload.destination_url)
    except UnsafeURLError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if payload.alias:
        alias = payload.alias.strip()
        if not ALIAS_RE.match(alias):
            raise HTTPException(status_code=400, detail="Alias must be 3-50 chars: letters, numbers, - or _")
        if await db.links.find_one({"alias": alias}):
            raise HTTPException(status_code=409, detail="This alias is already taken")
    else:
        alias = gen_alias()
        while await db.links.find_one({"alias": alias}):
            alias = gen_alias()

    qr = {
        "id": str(uuid.uuid4()),
        "workspace_id": ws["id"],
        "name": payload.name.strip(),
        "destination_url": destination,
        "alias": alias,
        "qr_type": payload.qr_type,
        "style": payload.style.model_dump(),
        "status": "active",
        "redirect_type": 302,
        "is_qr": True,
        "click_count": 0,
        "created_by": user["id"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.links.insert_one({**qr})
    return _clean(qr)


@router.get("")
async def list_qr(ws=Depends(get_current_workspace)):
    cur = db.links.find({"workspace_id": ws["id"], "is_qr": True}).sort("created_at", -1)
    items = [_clean(x) async for x in cur]
    return {"items": items, "total": len(items)}


async def _owned(qr_id: str, ws: dict) -> dict:
    qr = await db.links.find_one({"id": qr_id, "workspace_id": ws["id"], "is_qr": True})
    if not qr:
        raise HTTPException(status_code=404, detail="Not found")
    return qr


@router.get("/{qr_id}")
async def get_qr(qr_id: str, ws=Depends(get_current_workspace)):
    return _clean(await _owned(qr_id, ws))


@router.patch("/{qr_id}")
async def update_qr(qr_id: str, payload: QRUpdate, ws=Depends(get_current_workspace)):
    qr = await _owned(qr_id, ws)
    updates = {"updated_at": now_iso()}
    if payload.name is not None:
        updates["name"] = payload.name.strip()
    if payload.destination_url is not None:
        try:
            new_dest = validate_destination(payload.destination_url)
        except UnsafeURLError as e:
            raise HTTPException(status_code=400, detail=str(e))
        updates["destination_url"] = new_dest
        # dynamic destination change is versioned + rescanned
        await db.qr_versions.insert_one({
            "id": str(uuid.uuid4()), "qr_id": qr_id, "workspace_id": ws["id"],
            "previous_destination": qr["destination_url"], "new_destination": new_dest,
            "changed_at": now_iso(),
        })
    if payload.style is not None:
        updates["style"] = payload.style.model_dump()
    await db.links.update_one({"id": qr_id}, {"$set": updates})
    return _clean(await db.links.find_one({"id": qr_id}))


@router.get("/{qr_id}/versions")
async def qr_versions(qr_id: str, ws=Depends(get_current_workspace)):
    await _owned(qr_id, ws)
    rows = await db.qr_versions.find({"qr_id": qr_id}, {"_id": 0}).sort("changed_at", -1).to_list(100)
    return {"items": rows}


@router.post("/{qr_id}/pause")
async def pause_qr(qr_id: str, ws=Depends(get_current_workspace)):
    await _owned(qr_id, ws)
    await db.links.update_one({"id": qr_id}, {"$set": {"status": "paused", "updated_at": now_iso()}})
    return _clean(await db.links.find_one({"id": qr_id}))


@router.post("/{qr_id}/resume")
async def resume_qr(qr_id: str, ws=Depends(get_current_workspace)):
    await _owned(qr_id, ws)
    await db.links.update_one({"id": qr_id}, {"$set": {"status": "active", "updated_at": now_iso()}})
    return _clean(await db.links.find_one({"id": qr_id}))


@router.delete("/{qr_id}")
async def delete_qr(qr_id: str, ws=Depends(get_current_workspace)):
    await _owned(qr_id, ws)
    await db.links.delete_one({"id": qr_id})
    await db.analytics_events.delete_many({"link_id": qr_id})
    return {"ok": True}
