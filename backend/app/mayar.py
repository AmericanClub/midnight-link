"""Mayar.id payment gateway client (production).

Business logic calls these helpers only. Secrets come from settings/.env.
Auth: `Authorization: Bearer <API_KEY>`. Base: https://api.mayar.id/hl/v1
Docs verified: invoice/create, invoice/{id} (status), transactions list, webhook/register.
"""
import logging
from datetime import datetime, timezone, timedelta

import httpx

from .config import settings

logger = logging.getLogger("midgate.mayar")


class MayarError(Exception):
    pass


def configured() -> bool:
    return bool(settings.MAYAR_API_KEY)


async def _request(method: str, path: str, **kwargs) -> dict:
    if not configured():
        raise MayarError("Mayar API key is not configured")
    url = settings.MAYAR_BASE_URL.rstrip("/") + path
    headers = {
        "Authorization": f"Bearer {settings.MAYAR_API_KEY}",
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
