import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse

from ..db import db
from ..utils import now_iso, parse_user_agent, client_ip, client_country, visitor_hash
from ..providers import event_bus

router = APIRouter(tags=["redirect"])

# ---- lightweight cache layer (represents Redis cache + PG fallback) ------- #
_CACHE: dict[str, tuple[float, dict]] = {}
_TTL = 30.0


def _cache_get(alias: str):
    entry = _CACHE.get(alias)
    if entry and entry[0] > time.time():
        return entry[1]
    _CACHE.pop(alias, None)
    return None


def _cache_set(alias: str, link: dict):
    _CACHE[alias] = (time.time() + _TTL, link)


def _cache_invalidate(alias: str):
    _CACHE.pop(alias, None)


async def _resolve(alias: str):
    cached = _cache_get(alias)
    if cached is not None:
        return cached
    link = await db.links.find_one({"alias": alias}, {"_id": 0})
    if link:
        _cache_set(alias, link)
    return link


def _unavailable(message: str) -> HTMLResponse:
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>MidGate</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{{font-family:system-ui,sans-serif;background:#FAFAFA;color:#0A0A0A;display:flex;
align-items:center;justify-content:center;height:100vh;margin:0}}
.card{{text-align:center;max-width:420px;padding:40px}}
.b{{display:inline-block;font-weight:800;letter-spacing:-.02em;color:#4338CA;font-size:22px;margin-bottom:16px}}
p{{color:#475569;line-height:1.6}}</style></head>
<body><div class="card"><div class="b">MidGate</div>
<h2>Link unavailable</h2><p>{message}</p></div></body></html>"""
    return HTMLResponse(content=html, status_code=404)


@router.get("/api/redirect/health")
async def redirect_health():
    return {"status": "ok", "service": "redirect", "cache_size": len(_CACHE)}


@router.get("/api/r/{alias}")
async def redirect(alias: str, request: Request):
    link = await _resolve(alias)
    if not link:
        return _unavailable("This link does not exist.")

    if link.get("status") != "active":
        fb = link.get("fallback_url")
        return RedirectResponse(fb, status_code=302) if fb else _unavailable("This link is currently paused.")

    # expiry
    expires_at = link.get("expires_at")
    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < datetime.now(timezone.utc):
                fb = link.get("fallback_url")
                return RedirectResponse(fb, status_code=302) if fb else _unavailable("This link has expired.")
        except ValueError:
            pass

    # click limit
    max_clicks = link.get("max_clicks")
    if max_clicks and link.get("click_count", 0) >= max_clicks:
        fb = link.get("fallback_url")
        return RedirectResponse(fb, status_code=302) if fb else _unavailable("This link reached its click limit.")

    # atomic click counter
    await db.links.update_one({"id": link["id"]}, {"$inc": {"click_count": 1}})

    # build analytics event (never blocks redirect)
    ua = request.headers.get("user-agent", "")
    parsed = parse_user_agent(ua)
    ip = client_ip(request)
    event = {
        "id": str(uuid.uuid4()),
        "event_type": "click",
        "workspace_id": link["workspace_id"],
        "link_id": link["id"],
        "alias": alias,
        "occurred_at": now_iso(),
        "country": client_country(request),
        "device": parsed["device"],
        "browser": parsed["browser"],
        "os": parsed["os"],
        "referrer": (request.headers.get("referer") or "Direct").split("?")[0][:200],
        "is_bot": parsed["is_bot"],
        "bot_category": "automation" if parsed["is_bot"] else "human",
        "risk_score": 0,
        "decision": "allow",
        "visitor_id": visitor_hash(ip, ua),
    }
    await event_bus.publish("link.clicked", event)

    return RedirectResponse(link["destination_url"], status_code=link.get("redirect_type", 302))
