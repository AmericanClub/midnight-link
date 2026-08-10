"""KlikQRIS payment gateway client (production).

Credentials resolve from the DB (platform_settings _id="klikqris", set by an admin in the
Payments console) and fall back to environment/.env values. Auth headers:
`x-api-key: <API_KEY>` + `id_merchant: <MERCHANT_ID>`. Base: https://klikqris.com/api

KlikQRIS returns a DYNAMIC QRIS (image) to be scanned. The customer pays `total_amount`
(KlikQRIS appends a small unique code for auto-matching). Payment is ALWAYS re-verified via
the status endpoint before crediting — a webhook alone is never trusted.
"""
import logging

import httpx

from .config import settings
from .db import db

logger = logging.getLogger("midgate.klikqris")

_CREDS_CACHE = None
PAID_STATUSES = {"PAID", "SUCCESS"}
PAY_HOST = "https://klikqris.com"


class KlikqrisError(Exception):
    pass


async def _load_creds() -> dict:
    global _CREDS_CACHE
    doc = await db.platform_settings.find_one({"_id": "klikqris"}) or {}
    api_key = (doc.get("api_key") or settings.KLIKQRIS_API_KEY or "").strip()
    id_merchant = (doc.get("id_merchant") or settings.KLIKQRIS_MERCHANT_ID or "").strip()
    _CREDS_CACHE = {
        "api_key": api_key,
        "id_merchant": id_merchant,
        "base_url": (doc.get("base_url") or settings.KLIKQRIS_BASE_URL
                     or "https://klikqris.com/api").strip(),
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
    global _CREDS_CACHE
    _CREDS_CACHE = None


async def configured() -> bool:
    c = await _creds()
    return bool(c["api_key"] and c["id_merchant"])


async def gateway_status() -> dict:
    c = await _creds()
    key = c["api_key"]
    return {
        "provider": "klikqris",
        "base_url": c["base_url"],
        "api_key_set": bool(key),
        "api_key_masked": (("•••• " + key[-4:]) if len(key) >= 4 else ("••••" if key else "")),
        "merchant_id": c["id_merchant"],
        "merchant_id_set": bool(c["id_merchant"]),
        "source": c["source"],
        "updated_at": c.get("updated_at"),
        "updated_by": c.get("updated_by"),
    }


def pay_page_url(order_id: str) -> str:
    """Hosted KlikQRIS payment page (shows the QR + amount)."""
    return f"{PAY_HOST}/payqris/{order_id}"


async def _request(method: str, path: str, **kwargs) -> dict:
    c = await _creds()
    if not (c["api_key"] and c["id_merchant"]):
        raise KlikqrisError("KlikQRIS credentials are not configured")
    url = c["base_url"].rstrip("/") + path
    headers = {
        "x-api-key": c["api_key"],
        "id_merchant": c["id_merchant"],
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.request(method, url, headers=headers, **kwargs)
    except httpx.HTTPError as e:
        logger.error("KlikQRIS transport error %s %s: %s", method, path, e)
        raise KlikqrisError("Payment provider is unreachable")
    if r.status_code >= 400:
        logger.error("KlikQRIS %s %s -> %s %s", method, path, r.status_code, r.text[:300])
        raise KlikqrisError(f"KlikQRIS API error {r.status_code}")
    try:
        return r.json()
    except ValueError:
        raise KlikqrisError("Invalid response from KlikQRIS")


async def create_qris(*, order_id: str, amount: int, description: str | None = None,
                      callback_url: str | None = None) -> dict:
    c = await _creds()
    payload = {"order_id": str(order_id), "amount": int(amount), "id_merchant": c["id_merchant"]}
    if description:
        payload["keterangan"] = str(description)[:190]
    if callback_url:
        payload["callback_url"] = callback_url
    body = await _request("POST", "/qris/create", json=payload)
    if not body.get("status"):
        raise KlikqrisError(str(body.get("message", "KlikQRIS create failed")))
    return body.get("data", {}) or {}


async def get_status(order_id: str) -> dict:
    body = await _request("GET", f"/qris/status/{order_id}")
    return body.get("data", {}) or {}


async def verify_paid(order_id: str) -> bool:
    """Authoritative check against KlikQRIS — never trust the webhook alone."""
    if not order_id:
        return False
    try:
        data = await get_status(order_id)
    except KlikqrisError:
        return False
    return str(data.get("status", "")).upper() in PAID_STATUSES


async def list_history(page: int = 1) -> dict:
    """Used by the admin 'Test connection' button (validates key + merchant)."""
    return await _request("GET", f"/qris/history?page={int(page)}")
