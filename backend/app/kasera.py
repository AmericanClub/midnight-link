"""Kasera Pay payment gateway client (https://pay.kasera.id/docs/api).

Direct API QRIS: `POST /v1/transactions` with `payment_methods: ["qris"]` returns the raw
EMV payload in `payment.qr_string` (rendered to a PNG server-side so partner apps and our
billing page can show it in-app). Auth: `Authorization: Bearer kp_live_...|kp_test_...` —
the key prefix decides live vs sandbox. Creates are deduplicated ONLY by `Idempotency-Key`.

Confirmation: the `payment.paid` webhook, signed in `Kasera-Signature-V1`
(`t=<unix>,v1=<hex>[,v1=<hex>]`, HMAC-SHA256 over `<t>.<raw body>`, 5-min tolerance, two
`v1` entries during a 24h secret-rotation grace). Without a signing secret we never trust a
webhook and re-verify with `GET /v1/transactions/{id}` (max 1 read/sec/transaction, 300
req/min/key — reads are cached briefly to stay well inside those limits).

Amounts are whole rupiah and `amount = fee + net`: Kasera always deducts its fee from the
amount. "Fee paid by the payer" is therefore done on OUR side by grossing the amount up.

Credentials resolve from the DB (platform_settings _id="kasera", set in the admin Payments
console) and fall back to environment values.
"""
import asyncio
import hashlib
import hmac
import logging
import math
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

from .config import settings
from .db import db

logger = logging.getLogger("midgate.kasera")

DEFAULT_BASE = "https://pay.kasera.id"
DEFAULT_EXPIRY_MIN = 60
MIN_EXPIRY_MIN = 5
MAX_EXPIRY_MIN = 1440           # Kasera: default 60 min, max 24h
PAID_STATUSES = {"succeeded"}
WEBHOOK_TOLERANCE_S = 300
DELIVERY_INFO_ABOVE = 1_000_000  # Kasera needs delivery/buyer info above Rp1.000.000
WIB = timezone(timedelta(hours=7))
FEE_MODES = ("merchant", "payer")

_CREDS_CACHE = None
_FEE_CACHE: dict = {"at": 0.0, "key": None, "fee": None}
_FEE_TTL_S = 600
_STATUS_CACHE: dict[str, tuple[float, dict]] = {}
_STATUS_TTL_S = 8.0

_PLACEHOLDER_EMAILS = {"noreply@midnightlink.link"}
_PLACEHOLDER_PHONES = {"081200000000"}
_PLACEHOLDER_NAMES = {"customer", "midnight link customer"}
_EMAIL_RX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class KaseraError(Exception):
    def __init__(self, message: str, *, status: int | None = None, code: str | None = None,
                 fields: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.fields = fields or {}


# ------------------------------- credentials ------------------------------- #
def clean_base_url(raw) -> str:
    """Normalize a pasted base URL to scheme+host (our paths already include /v1).
    '' means default. A pasted dashboard/docs link on pay.kasera.id maps to the API host."""
    b = str(raw or "").strip()
    if not b:
        return ""
    if "//" not in b:
        b = "https://" + b
    host = (urlparse(b).hostname or "").lower()
    if not host:
        return ""
    if host in ("localhost", "127.0.0.1"):  # local mock server (development/tests only)
        p = urlparse(b)
        return f"{p.scheme}://{p.netloc}"
    return f"https://{host}"


def key_mode(key: str) -> str:
    k = (key or "").strip()
    if k.startswith("kp_test_"):
        return "test"
    if k.startswith("kp_live_"):
        return "live"
    return "unknown" if k else "none"


async def _load_creds() -> dict:
    global _CREDS_CACHE
    doc = await db.platform_settings.find_one({"_id": "kasera"}) or {}
    api_key = (doc.get("api_key") or settings.KASERA_API_KEY or "").strip()
    secret = (doc.get("webhook_secret") or settings.KASERA_WEBHOOK_SECRET or "").strip()
    base = clean_base_url(doc.get("base_url") or settings.KASERA_BASE_URL) or DEFAULT_BASE
    try:
        expiry = int(doc.get("expiry_minutes") or DEFAULT_EXPIRY_MIN)
    except (TypeError, ValueError):
        expiry = DEFAULT_EXPIRY_MIN
    fee_mode = doc.get("fee_mode") if doc.get("fee_mode") in FEE_MODES else "merchant"
    _CREDS_CACHE = {
        "api_key": api_key,
        "webhook_secret": secret,
        "base_url": base,
        "expiry_minutes": max(MIN_EXPIRY_MIN, min(expiry, MAX_EXPIRY_MIN)),
        "fee_mode": fee_mode,
        "mode": key_mode(api_key),
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
    _FEE_CACHE.update({"at": 0.0, "key": None, "fee": None})


async def configured() -> bool:
    return bool((await _creds())["api_key"])


async def mode() -> str:
    return (await _creds())["mode"]


async def webhook_secret() -> str:
    return (await _creds())["webhook_secret"]


async def fee_mode() -> str:
    return (await _creds())["fee_mode"]


def _mask(v: str) -> str:
    return ("•••• " + v[-4:]) if len(v) >= 4 else ("••••" if v else "")


async def gateway_status() -> dict:
    c = await _creds()
    return {
        "provider": "kasera",
        "base_url": c["base_url"],
        "api_key_set": bool(c["api_key"]),
        "api_key_masked": _mask(c["api_key"]),
        "mode": c["mode"],
        "webhook_secret_set": bool(c["webhook_secret"]),
        "webhook_secret_masked": _mask(c["webhook_secret"]),
        "expiry_minutes": c["expiry_minutes"],
        "fee_mode": c["fee_mode"],
        "source": c["source"],
        "updated_at": c.get("updated_at"),
        "updated_by": c.get("updated_by"),
    }


# --------------------------------- HTTP ------------------------------------ #
async def _request(method: str, path: str, *, json: dict | None = None,
                   idempotency_key: str | None = None) -> dict:
    c = await _creds()
    if not c["api_key"]:
        raise KaseraError("Kasera API key is not configured", code="not_configured")
    headers = {"Authorization": f"Bearer {c['api_key']}", "Accept": "application/json"}
    if json is not None:
        headers["Content-Type"] = "application/json"
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key[:255]
    url = c["base_url"].rstrip("/") + path
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.request(method, url, headers=headers, json=json)
    except httpx.HTTPError as e:
        logger.error("Kasera transport error %s %s: %s", method, path, e)
        raise KaseraError("Payment provider is unreachable", code="unreachable")
    if r.status_code >= 400:
        err = {}
        try:
            err = (r.json() or {}).get("error") or {}
        except ValueError:
            pass
        code = err.get("code")
        logger.error("Kasera %s %s -> %s %s %s (request_id=%s)", method, path, r.status_code,
                     code, (err.get("message") or r.text[:200]), err.get("request_id"))
        raise KaseraError(f"Kasera API error {r.status_code}" + (f" ({code})" if code else ""),
                          status=r.status_code, code=code, fields=err.get("fields"))
    try:
        return r.json()
    except ValueError:
        raise KaseraError("Invalid response from Kasera", code="invalid_response")


def friendly_error(e: Exception) -> str:
    """Readable reason for admins/partners (never leaks secrets)."""
    code = getattr(e, "code", None) or ""
    status = getattr(e, "status", None)
    if code == "unauthorized" or status == 401:
        return "Kasera API key is wrong or revoked."
    if code in ("unverified_count_cap", "unverified_amount_cap"):
        return ("Kasera account is not verified yet (limit: 10 payments / Rp1.000.000 before "
                "verification). Finish verification in the Kasera dashboard.")
    if code == "merchant_suspended":
        return "Kasera account is suspended."
    if code in ("amount_too_small", "amount_too_large"):
        return "Amount is outside Kasera's QRIS limits."
    if code == "payment_method_unavailable":
        return "QRIS is not enabled on this Kasera account."
    if code == "rate_limited" or status == 429:
        return "Kasera is busy (rate limited). Please try again in a moment."
    if code in ("customer_required", "buyer_name_required", "buyer_contact_required"):
        return "Kasera needs the payer's name and email/phone for amounts above Rp1.000.000."
    if code == "not_configured":
        return "Kasera API key is not set."
    return str(e)


# -------------------------------- fees ------------------------------------- #
async def get_qris_method() -> dict | None:
    """QRIS entry from GET /v1/payment_methods (fee, min/max), cached for 10 min."""
    c = await _creds()
    now = time.monotonic()
    if _FEE_CACHE["fee"] is not None and _FEE_CACHE["key"] == c["api_key"] \
            and now - _FEE_CACHE["at"] < _FEE_TTL_S:
        return _FEE_CACHE["fee"]
    body = await _request("GET", "/v1/payment_methods")
    qris = next((m for m in (body.get("data") or []) if str(m.get("code", "")).lower() == "qris"), None)
    _FEE_CACHE.update({"at": now, "key": c["api_key"], "fee": qris})
    return qris


def fee_for(gross: int, fee: dict) -> int:
    bps = int((fee or {}).get("percent_bps") or 0)
    flat = int((fee or {}).get("flat") or 0)
    return int(math.ceil(gross * bps / 10_000)) + flat


def gross_up(net: int, fee: dict) -> int:
    """Smallest gross amount whose Kasera fee still leaves at least `net` for us."""
    net = int(net)
    bps = int((fee or {}).get("percent_bps") or 0)
    flat = int((fee or {}).get("flat") or 0)
    if bps <= 0 and flat <= 0:
        return net
    gross = int(math.ceil((net + flat) / (1 - bps / 10_000)))
    while gross - fee_for(gross, fee) < net:
        gross += 1
    return gross


# ------------------------------ transactions ------------------------------- #
def _real_customer(name=None, email=None, phone=None) -> dict:
    """Only real buyer data — never send our placeholders to the gateway."""
    out = {}
    n = (name or "").strip()
    if n and n.lower() not in _PLACEHOLDER_NAMES:
        out["name"] = n[:120]
    e = (email or "").strip()
    if e and e.lower() not in _PLACEHOLDER_EMAILS and _EMAIL_RX.match(e):
        out["email"] = e[:254]
    p = "".join(ch for ch in str(phone or "") if ch.isdigit() or ch == "+")
    if p and p not in _PLACEHOLDER_PHONES and len(re.sub(r"\D", "", p)) >= 9:
        out["phone"] = p[:32]
    return out


async def create_qris(*, order_id: str, amount: int, description: str | None = None,
                      customer: dict | None = None, return_url: str | None = None,
                      merchant_ref: str | None = None) -> dict:
    """Create a QRIS payment request (Direct API). Returns the Kasera Transaction object,
    re-read briefly if the QR payload was not issued yet (it is never a placeholder)."""
    c = await _creds()
    amount = int(amount)
    desc = (description or "Midnight Link payment").strip()[:255]
    body = {
        "amount": amount,
        "description": desc,
        "external_id": str(order_id)[:64],
        "payment_methods": ["qris"],
        "expires_in_minutes": c["expiry_minutes"],
    }
    if merchant_ref:
        body["merchant_ref"] = str(merchant_ref)[:64]
    ru = (return_url or "").strip()
    if ru.startswith("https://") or (c["mode"] == "test" and ru.startswith("http://")):
        body["return_url"] = ru[:2048]
    cust = _real_customer(**(customer or {}))
    if cust:
        body["customer"] = cust
    if amount > DELIVERY_INFO_ABOVE:
        # Credits / partner top-ups are delivered instantly after payment (shown to the buyer).
        if len(desc) < 10:
            body["description"] = (desc + " — Midnight Link payment")[:255]
        body["delivery_date"] = datetime.now(WIB).date().isoformat()
        body["delivery_terms_shown"] = True
    data = await _request("POST", "/v1/transactions", json=body,
                          idempotency_key=f"midnightlink:{order_id}")
    tries = 0
    while not ((data.get("payment") or {}).get("qr_string")) and data.get("id") and tries < 3:
        tries += 1
        await asyncio.sleep(1.2)  # GET is paced at 1 read/sec/transaction
        try:
            data = await _request("GET", f"/v1/transactions/{data['id']}")
        except KaseraError as e:
            logger.warning("Kasera re-read %s failed: %s", data.get("id"), e)
    return data


async def get_transaction(txn_id: str, *, max_age: float = _STATUS_TTL_S) -> dict:
    now = time.monotonic()
    hit = _STATUS_CACHE.get(txn_id)
    if hit and now - hit[0] < max_age:
        return hit[1]
    data = await _request("GET", f"/v1/transactions/{txn_id}")
    _STATUS_CACHE[txn_id] = (now, data)
    if len(_STATUS_CACHE) > 3000:
        for k, (t, _) in list(_STATUS_CACHE.items()):
            if now - t > 60:
                _STATUS_CACHE.pop(k, None)
    return data


async def verify_paid(txn_id: str | None, *, fresh: bool = False, retries: int = 0) -> bool:
    """Authoritative check against Kasera (status == succeeded).
    `fresh=True` bypasses the short read cache (used right after a webhook says something
    changed); `retries` re-reads after a short pause (rate limit is 1 read/sec/transaction)."""
    if not txn_id:
        return False
    for attempt in range(retries + 1):
        try:
            data = await get_transaction(txn_id, max_age=0 if fresh else _STATUS_TTL_S)
            if str(data.get("status", "")).lower() in PAID_STATUSES:
                return True
        except KaseraError as e:
            logger.info("Kasera verify %s not possible now: %s", txn_id, e)
        if attempt < retries:
            await asyncio.sleep(1.5)
    return False


# -------------------------------- webhooks --------------------------------- #
def verify_signature(raw: bytes, header: str | None, secret: str,
                     tolerance: int = WEBHOOK_TOLERANCE_S, now: float | None = None) -> bool:
    """Kasera-Signature-V1: t=<unix>,v1=<hex>[,v1=<hex>] over `<t>.<raw body>`."""
    if not header or not secret:
        return False
    parts = [p.strip() for p in str(header).split(",") if p.strip()]
    if not parts or not parts[0].startswith("t="):
        return False
    try:
        t = int(parts[0][2:])
    except ValueError:
        return False
    if abs((now if now is not None else time.time()) - t) > tolerance:
        return False
    expected = hmac.new(secret.encode(), f"{t}.".encode() + raw, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(p[3:], expected) for p in parts[1:] if p.startswith("v1="))


# -------------------------------- sandbox ---------------------------------- #
def checkout_token(checkout_url: str | None) -> str | None:
    if not checkout_url or "/p/" not in checkout_url:
        return None
    tok = checkout_url.split("/p/", 1)[1].split("?", 1)[0].split("#", 1)[0].strip("/")
    return tok or None


async def simulate_payment(checkout_url: str, outcome: str = "succeeded") -> dict:
    """SANDBOX ONLY: settle a test payment (Kasera answers 404 for live payments)."""
    c = await _creds()
    tok = checkout_token(checkout_url)
    if not tok:
        raise KaseraError("No checkout token on this payment", code="no_token")
    url = f"{c['base_url'].rstrip('/')}/api/v1/checkout/{tok}/simulate-payment"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(url, json={"outcome": outcome})
    except httpx.HTTPError as e:
        raise KaseraError(f"Payment provider is unreachable: {e}", code="unreachable")
    if r.status_code >= 400:
        raise KaseraError(f"Kasera simulate failed ({r.status_code})", status=r.status_code)
    _STATUS_CACHE.clear()
    try:
        return r.json()
    except ValueError:
        return {"ok": True}


async def probe() -> dict:
    """Admin 'Test connection': reads the account's payment methods (no payment created)."""
    c = await _creds()
    if not c["api_key"]:
        return {"ok": False, "message": "Kasera API key is not set."}
    try:
        _FEE_CACHE.update({"at": 0.0, "fee": None})
        qris = await get_qris_method()
    except KaseraError as e:
        return {"ok": False, "message": f"Failed: {friendly_error(e)}"}
    label = "Sandbox (test)" if c["mode"] == "test" else ("Live" if c["mode"] == "live" else "Unknown mode")
    if not qris:
        return {"ok": False, "message": f"Connected ({label}), but QRIS is not enabled on this Kasera account."}
    fee = (qris.get("fee") or {}).get("label") or "—"
    lo = f"Rp{int(qris.get('min_amount') or 0):,}".replace(",", ".")
    hi = f"Rp{int(qris.get('max_amount') or 0):,}".replace(",", ".")
    warn = "" if c["webhook_secret"] else " ⚠ Webhook signing secret not set."
    return {"ok": True, "message": f"Kasera connected — {label}. QRIS fee {fee}, {lo}–{hi}.{warn}"}
