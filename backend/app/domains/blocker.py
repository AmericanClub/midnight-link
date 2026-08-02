"""Public Blocker API — call from any website/server to gate traffic.

  GET /api/v1/blocker?apikey=...&ip=...&ua=...&url=...&reff=...
  GET /api/v2/blocker?apikey=...&ip=...&ua=...&url=...&reff=...

Returns JSON { block, decision, risk_score, reasons, ip, is_bot, ... }.
Authenticated with a hashed workspace API key. Rate limited per key.
"""
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..db import db
from ..utils import now_iso
from ..intel import rate_limiter
from ..providers import event_bus
from .apikeys import resolve_key
from .security import evaluate_request

router = APIRouter(tags=["blocker"])

RATE_PER_MIN = 1200


async def _blocker(request: Request, version: str) -> JSONResponse:
    q = request.query_params
    apikey = q.get("apikey")
    key = await resolve_key(apikey)
    if not key:
        return JSONResponse(status_code=401, content={"error": "invalid_or_missing_api_key", "block": False})

    if not rate_limiter.allow(f"apikey:{key['id']}", RATE_PER_MIN):
        return JSONResponse(status_code=429, content={"error": "rate_limited", "block": False})

    ip = q.get("ip") or (request.client.host if request.client else "0.0.0.0")
    ua = q.get("ua") or request.headers.get("user-agent", "")
    reff = q.get("reff") or q.get("referrer") or "Direct"

    result = await evaluate_request(key["workspace_id"], None, ip, ua, reff, "Unknown")
    s = result["signals"]
    # a pure API gate has no interstitial, so treat challenge-or-worse as block
    block = result["decision"] in ("block", "challenge")

    # bookkeeping (never blocks the response)
    await db.api_keys.update_one({"id": key["id"]}, {"$set": {"last_used": now_iso()}, "$inc": {"request_count": 1}})
    await event_bus.publish("link.clicked", {
        "id": str(uuid.uuid4()), "event_type": "api_check", "workspace_id": key["workspace_id"],
        "link_id": None, "alias": None, "occurred_at": now_iso(),
        "country": s["country"], "device": s["device"], "browser": s["browser"], "os": s["os"],
        "referrer": s["referrer"], "is_bot": s["is_bot"], "bot_category": s["bot_category"],
        "is_tor": s["is_tor"], "is_datacenter": s["is_datacenter"], "is_proxy": s["is_proxy"],
        "risk_score": result["risk_score"], "decision": result["decision"],
        "risk_reasons": result["reasons"], "visitor_id": None, "source": "api",
    })

    payload = {
        "block": block,
        "decision": result["decision"],
        "risk_score": result["risk_score"],
        "reasons": result["reasons"],
        "ip": ip,
        "is_bot": s["is_bot"],
        "bot_category": s["bot_category"],
        "is_tor": s["is_tor"],
        "is_datacenter": s["is_datacenter"],
        "is_proxy": s["is_proxy"],
        "is_headless": s["is_headless"],
        "country": s["country"],
    }
    if version == "v2":
        payload["url"] = q.get("url")
        payload["reff"] = reff
    return JSONResponse(content=payload)


@router.get("/api/v1/blocker")
async def blocker_v1(request: Request):
    return await _blocker(request, "v1")


@router.get("/api/v2/blocker")
async def blocker_v2(request: Request):
    return await _blocker(request, "v2")
