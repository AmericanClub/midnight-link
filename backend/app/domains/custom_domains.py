"""Custom domains — bring-your-own-domain for branded short links & QR.

Real DNS-based verification via dnspython (TXT challenge), no external API.
Once verified and the DNS points to MidGate's edge, links resolve at
https://your.domain/{alias}. One verified domain per workspace can be primary.
"""
import asyncio
import re
import uuid

import dns.resolver
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from ..db import db
from ..config import settings
from ..utils import now_iso
from ..security import get_current_user
from .workspace import list_user_workspaces

router = APIRouter(prefix="/api/domains", tags=["domains"])

DOMAIN_ROLES = {"owner", "admin"}
DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)([A-Za-z0-9-]{1,63}(?<!-)\.)+[A-Za-z]{2,63}$"
)


async def get_admin_workspace(request: Request, user=Depends(get_current_user)) -> dict:
    ws_id = request.headers.get("X-Workspace-Id")
    workspaces = await list_user_workspaces(user["id"])
    ws = next((w for w in workspaces if w["id"] == ws_id), None) if ws_id else (workspaces[0] if workspaces else None)
    if not ws:
        raise HTTPException(status_code=404, detail="Not found")
    if ws.get("role") not in DOMAIN_ROLES:
        raise HTTPException(status_code=403, detail="Only workspace owners or admins can manage domains")
    return ws


def _txt_name(domain: str) -> str:
    return f"{settings.DOMAIN_VERIFY_PREFIX}.{domain}"


def _expected_txt(token: str) -> str:
    return f"midgate-verify={token}"


def _instructions(d: dict) -> dict:
    return {
        "cname": {"type": "CNAME", "host": d["domain"], "value": settings.EDGE_HOST},
        "txt": {"type": "TXT", "host": _txt_name(d["domain"]), "value": _expected_txt(d["verify_token"])},
    }


def _public(d: dict) -> dict:
    return {
        "id": d["id"], "domain": d["domain"], "status": d.get("status", "pending"),
        "is_primary": d.get("is_primary", False), "created_at": d["created_at"],
        "verified_at": d.get("verified_at"), "instructions": _instructions(d),
    }


def _resolve_txt(name: str) -> list[str]:
    try:
        answers = dns.resolver.resolve(name, "TXT", lifetime=5.0)
    except Exception:
        return []
    out = []
    for r in answers:
        try:
            out.append(b"".join(r.strings).decode("utf-8", "ignore"))
        except Exception:
            out.append(str(r).strip('"'))
    return out


class DomainInput(BaseModel):
    domain: str


def _normalize(raw: str) -> str:
    d = (raw or "").strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = d.split("/")[0].split(":")[0]
    if d.startswith("*."):
        d = d[2:]
    if not DOMAIN_RE.match(d):
        raise HTTPException(status_code=400, detail="Enter a valid domain, e.g. go.yourbrand.com")
    return d


@router.get("")
async def list_domains(ws=Depends(get_admin_workspace)):
    rows = await db.custom_domains.find({"workspace_id": ws["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"items": [_public(r) for r in rows], "edge_host": settings.EDGE_HOST}


@router.post("")
async def add_domain(payload: DomainInput, ws=Depends(get_admin_workspace)):
    domain = _normalize(payload.domain)
    if await db.custom_domains.find_one({"domain": domain}):
        raise HTTPException(status_code=409, detail="This domain is already connected")
    doc = {
        "id": str(uuid.uuid4()), "workspace_id": ws["id"], "domain": domain,
        "status": "pending", "verify_token": uuid.uuid4().hex, "is_primary": False,
        "created_at": now_iso(), "verified_at": None,
    }
    await db.custom_domains.insert_one({**doc})
    return _public(doc)


async def _owned(domain_id: str, ws: dict) -> dict:
    d = await db.custom_domains.find_one({"id": domain_id, "workspace_id": ws["id"]})
    if not d:
        raise HTTPException(status_code=404, detail="Not found")
    return d


@router.post("/{domain_id}/verify")
async def verify_domain(domain_id: str, ws=Depends(get_admin_workspace)):
    d = await _owned(domain_id, ws)
    name = _txt_name(d["domain"])
    txts = await asyncio.to_thread(_resolve_txt, name)
    expected = _expected_txt(d["verify_token"])
    if expected in txts:
        await db.custom_domains.update_one(
            {"id": domain_id}, {"$set": {"status": "verified", "verified_at": now_iso()}})
        d = await db.custom_domains.find_one({"id": domain_id}, {"_id": 0})
        from .notifications import create_notification
        await create_notification(
            ws["id"], "domain_verified", "Domain verified",
            f"{d['domain']} is verified and ready for branded links.",
            "success", {"domain": d["domain"]})
        return {"verified": True, "domain": _public(d)}
    return {
        "verified": False,
        "checked_record": name,
        "expected_value": expected,
        "found_values": txts,
        "message": "TXT record not found yet. DNS changes can take a few minutes to propagate.",
    }


@router.post("/{domain_id}/primary")
async def set_primary(domain_id: str, ws=Depends(get_admin_workspace)):
    d = await _owned(domain_id, ws)
    if d.get("status") != "verified":
        raise HTTPException(status_code=400, detail="Verify the domain before making it primary")
    await db.custom_domains.update_many({"workspace_id": ws["id"]}, {"$set": {"is_primary": False}})
    await db.custom_domains.update_one({"id": domain_id}, {"$set": {"is_primary": True}})
    d = await db.custom_domains.find_one({"id": domain_id}, {"_id": 0})
    return _public(d)


@router.delete("/{domain_id}")
async def delete_domain(domain_id: str, ws=Depends(get_admin_workspace)):
    res = await db.custom_domains.delete_one({"id": domain_id, "workspace_id": ws["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}
