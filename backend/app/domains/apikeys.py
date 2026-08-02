import hashlib
import secrets
import uuid

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ..db import db
from ..utils import now_iso
from .workspace import get_current_workspace

router = APIRouter(prefix="/api/apikeys", tags=["apikeys"])


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def resolve_key(raw: str) -> dict | None:
    if not raw:
        return None
    doc = await db.api_keys.find_one({"key_hash": hash_key(raw), "revoked": {"$ne": True}})
    return doc


class KeyInput(BaseModel):
    name: str = Field(default="Default key", max_length=80)


def _public(doc: dict) -> dict:
    return {"id": doc["id"], "name": doc["name"], "prefix": doc["prefix"],
            "last_used": doc.get("last_used"), "request_count": doc.get("request_count", 0),
            "revoked": doc.get("revoked", False), "created_at": doc["created_at"]}


@router.get("")
async def list_keys(ws=Depends(get_current_workspace)):
    rows = await db.api_keys.find({"workspace_id": ws["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"items": [_public(r) for r in rows]}


@router.post("")
async def create_key(payload: KeyInput, ws=Depends(get_current_workspace)):
    raw = "mgk_" + secrets.token_hex(24)
    doc = {
        "id": str(uuid.uuid4()),
        "workspace_id": ws["id"],
        "name": payload.name,
        "key_hash": hash_key(raw),
        "prefix": raw[:12] + "…",
        "scopes": ["blocker"],
        "last_used": None,
        "request_count": 0,
        "revoked": False,
        "created_at": now_iso(),
    }
    await db.api_keys.insert_one({**doc})
    # the raw key is returned exactly once
    return {**_public(doc), "key": raw}


@router.delete("/{key_id}")
async def revoke_key(key_id: str, ws=Depends(get_current_workspace)):
    res = await db.api_keys.update_one({"id": key_id, "workspace_id": ws["id"]}, {"$set": {"revoked": True}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}
