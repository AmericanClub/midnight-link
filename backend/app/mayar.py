"""Mayar.id payment gateway client (production).

Credentials resolve from the DB (platform_settings _id="gateway", set by an admin in
the Payments console) and fall back to environment/.env values. Business logic calls
these helpers only. Auth: `Authorization: Bearer <API_KEY>`. Base: https://api.mayar.id/hl/v1
"""
import logging
from datetime import datetime, timezone, timedelta

import httpx

from .config import settings
from .db import db

logger = logging.getLogger("midgate.mayar")

_CREDS_CACHE = None  # cached dict of resolved credentials


class MayarError(Exception):
    pass


async def _load_creds() -> dict:
    global _CREDS_CACHE
    doc = await db.platform_settings.find_one({"_id": "gateway"}) or {}
    api_key = (doc.get("api_key") or settings.MAYAR_API_KEY or "").strip()
    _CREDS_CACHE = {
        "api_key": api_key,
        "base_url": (doc.get("base_url") or settings.MAYAR_BASE_URL
                     or "https://api.mayar.id/hl/v1").strip(),
        "webhook_token": (doc.get("webhook_token") or settings.MAYAR_WEBHOOK_TOKEN or "").strip(),
        "source": "db" if doc.get("api_key") else ("env" if api_key else "none"),
        "updated_at": doc.get("updated_at"),
        "updated_by": doc.get("updated_by"),
    }
    return _CREDS_CACHE


async def _creds() -> dict:
    if _CREDS_CACHE is None:
        return await _load_creds()
    return _CREDS_CACHE


def invalidate_creds():
    """Force the next call to reload credentials from the DB (used after admin updates)."""
    global _CREDS_CACHE
    _CREDS_CACHE = None


async def configured() -> bool:
    return bool((await _creds())["api_key"])


async def webhook_token() -> str:
    return (await _creds())["webhook_token"]


async def gateway_status() -> dict:
    c = await _creds()
    key = c["api_key"]
    return {
        "provider": "mayar",
        "base_url": c["base_url"],
        "api_key_set": bool(key),
        "api_key_masked": (("•••• " + key[-4:]) if len(key) >= 4 else ("••••" if key else "")),
        "webhook_token_set": bool(c["webhook_token"]),
        "source": c["source"],
        "updated_at": c.get("updated_at"),
        "updated_by": c.get("updated_by"),
    }


async def _request(method: str, path: str, **kwargs) -> dict:
    c = await _creds()
    if not c["api_key"]:
        raise MayarError("Mayar API key is not configured")
    url = c["base_url"].rstrip("/") + path
    headers = {
        "Authorization": f"Bearer {c['api_key']}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.request(method, url, headers=headers, **kwargs)
    except httpx.HTTPError as e:
        logger.error("Mayar transport error %s %s: %s", method, path, e)
        raise MayarError("Payment provider is unreachable")
    if r.status_code >= 400:
        logger.error("Mayar %s %s -> %s %s", method, path, r.status_code, r.text[:300])
        raise MayarError(f"Mayar API error {r.status_code}")
    body = r.json()
    if int(body.get("statusCode", 200)) >= 400:
        raise MayarError(str(body.get("messages", "Mayar API error")))
    return body


async def create_invoice(*, name: str, email: str, mobile: str, amount: int,
                         description: str, redirect_url: str, extra_data: dict) -> dict:
    expired_at = (datetime.now(timezone.utc) + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    payload = {
        "name": name,
        "email": email,
        "mobile": mobile,
        "redirectUrl": redirect_url,
        "description": description,
        "expiredAt": expired_at,
        "items": [{"quantity": 1, "rate": int(amount), "description": description}],
        "extraData": extra_data,
    }
    body = await _request("POST", "/invoice/create", json=payload)
    return body.get("data", {}) or {}


async def get_invoice(invoice_id: str) -> dict:
    body = await _request("GET", f"/invoice/{invoice_id}")
    return body.get("data", {}) or {}


async def list_transactions(page: int = 1, page_size: int = 25) -> list:
    body = await _request("GET", f"/transactions?page={page}&pageSize={page_size}")
    return body.get("data", []) or []


async def register_webhook(url: str) -> dict:
    return await _request("POST", "/webhook/register", json={"urlHook": url})
