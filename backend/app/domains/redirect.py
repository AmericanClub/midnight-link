import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse

from ..db import db
from ..utils import now_iso, client_ip, client_country, visitor_hash
from ..providers import event_bus
from .security import evaluate_request, challenge_token, verify_challenge
from .billing import can_record_event

router = APIRouter(tags=["redirect"])

_CACHE: dict[str, tuple[float, dict]] = {}
_TTL = 30.0


def _cache_get(alias):
    entry = _CACHE.get(alias)
    if entry and entry[0] > time.time():
        return entry[1]
    _CACHE.pop(alias, None)
    return None


def invalidate_cache(alias):
    _CACHE.pop(alias, None)


_WS_SUSPENDED: list = [0.0, set()]


def invalidate_suspended_workspaces():
    _WS_SUSPENDED[0] = 0.0


async def _suspended_workspaces() -> set:
    if _WS_SUSPENDED[0] > time.time():
        return _WS_SUSPENDED[1]
    rows = await db.workspaces.find({"suspended": True}, {"_id": 0, "id": 1}).to_list(10000)
    _WS_SUSPENDED[0] = time.time() + 30.0
    _WS_SUSPENDED[1] = {r["id"] for r in rows}
    return _WS_SUSPENDED[1]


async def _resolve(alias):
    cached = _cache_get(alias)
    if cached is not None:
        return cached
    link = await db.links.find_one({"alias": alias}, {"_id": 0})
    if link:
        _CACHE[alias] = (time.time() + _TTL, link)
    return link


def _page(title, message, status, extra=""):
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>MidGate</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{{font-family:system-ui,sans-serif;background:#FAFAFA;color:#0A0A0A;display:flex;
align-items:center;justify-content:center;height:100vh;margin:0}}
.card{{text-align:center;max-width:440px;padding:40px}}
.b{{display:inline-block;font-weight:800;letter-spacing:-.02em;color:#4338CA;font-size:22px;margin-bottom:16px}}
h2{{margin:8px 0}} p{{color:#475569;line-height:1.6}}
a.btn{{display:inline-block;margin-top:20px;background:#4338CA;color:#fff;padding:12px 24px;
border-radius:8px;text-decoration:none;font-weight:600}}</style></head>
<body><div class="card"><div class="b">MidGate</div>
<h2>{title}</h2><p>{message}</p>{extra}</div></body></html>"""
    return HTMLResponse(content=html, status_code=status)


def _apply_block(link, action, block_redirect_url):
    if action == "fallback":
        url = block_redirect_url or link.get("fallback_url")
        return RedirectResponse(url, status_code=302) if url else _page(
            "Access blocked", "This request was blocked by the link's security policy.", 403)
    if action == "redirect" and block_redirect_url:
        return RedirectResponse(block_redirect_url, status_code=302)
    if action == "notfound":
        return _page("Link unavailable", "This link does not exist.", 404)
    return _page("Access blocked", "This request was blocked by the link's security policy.", 403)


@router.get("/api/redirect/health")
async def redirect_health():
    return {"status": "ok", "service": "redirect", "cache_size": len(_CACHE)}


@router.get("/api/r/{alias}")
async def redirect(alias: str, request: Request):
    link = await _resolve(alias)
    if not link:
        return _page("Link unavailable", "This link does not exist.", 404)

    if link.get("workspace_id") in await _suspended_workspaces():
        return _page("Link unavailable", "This link is currently unavailable.", 404)

    if link.get("status") != "active":
        fb = link.get("fallback_url")
        return RedirectResponse(fb, status_code=302) if fb else _page(
            "Link unavailable", "This link is currently paused.", 404)

    expires_at = link.get("expires_at")
    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < datetime.now(timezone.utc):
                fb = link.get("fallback_url")
                return RedirectResponse(fb, status_code=302) if fb else _page(
                    "Link expired", "This link has expired.", 404)
        except ValueError:
            pass

    max_clicks = link.get("max_clicks")
    if max_clicks and link.get("click_count", 0) >= max_clicks:
        fb = link.get("fallback_url")
        return RedirectResponse(fb, status_code=302) if fb else _page(
            "Limit reached", "This link reached its click limit.", 404)

    ua = request.headers.get("user-agent", "")
    ip = client_ip(request)
    visitor_id = visitor_hash(ip, ua)
    country = client_country(request)
    referrer = request.headers.get("referer") or "Direct"

    result = await evaluate_request(link["workspace_id"], link, ip, ua, referrer, country)
    decision = result["decision"]
    signals = result["signals"]
    challenge_result = "n/a"

    if decision == "challenge":
        token = request.query_params.get("mg_ch")
        if verify_challenge(alias, visitor_id, token):
            challenge_result = "passed"
            decision = "allow"
        else:
            await _record(link, alias, signals, result, "issued", visitor_id)
            cont = f"/api/r/{alias}?mg_ch={challenge_token(alias, visitor_id)}"
            extra = f'<a class="btn" href="{cont}" data-testid="challenge-continue">Continue</a>'
            return _page("Quick security check",
                         "We're verifying your request to keep this link safe. Click continue to proceed.",
                         200, extra)

    if decision == "block":
        await _record(link, alias, signals, result, challenge_result, visitor_id)
        return _apply_block(link, result.get("action", "block_page"), result.get("block_redirect_url", ""))

    await db.links.update_one({"id": link["id"]}, {"$inc": {"click_count": 1}})
    await _record(link, alias, signals, result, challenge_result, visitor_id)
    return RedirectResponse(link["destination_url"], status_code=link.get("redirect_type", 302))


async def _record(link, alias, signals, result, challenge_result, visitor_id):
    if not await can_record_event(link["workspace_id"]):
        return
    event = {
        "id": str(uuid.uuid4()),
        "event_type": "scan" if link.get("is_qr") else "click",
        "workspace_id": link["workspace_id"],
        "link_id": link["id"],
        "alias": alias,
        "occurred_at": now_iso(),
        "country": signals["country"],
        "device": signals["device"],
        "browser": signals["browser"],
        "os": signals["os"],
        "referrer": signals["referrer"],
        "is_bot": signals["is_bot"],
        "bot_category": signals["bot_category"],
        "is_tor": signals["is_tor"],
        "is_datacenter": signals["is_datacenter"],
        "is_proxy": signals["is_proxy"],
        "is_vpn": signals.get("is_vpn", False),
        "intel_source": signals.get("intel_source"),
        "risk_score": result["risk_score"],
        "decision": result["decision"],
        "risk_reasons": result["reasons"],
        "matched_rule_id": result.get("matched_rule_id"),
        "challenge_result": challenge_result,
        "visitor_id": visitor_id,
        "source": "redirect",
    }
    await event_bus.publish("link.clicked", event)
