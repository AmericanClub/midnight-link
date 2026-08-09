"""proxycheck.io IP intelligence integration (VPN/Proxy/Tor + risk + ASN).

- API key entered by a platform admin, encrypted at rest (Fernet) in
  db.platform_settings (_id="proxycheck"). Never returned in plaintext.
- Per-IP in-memory TTL cache to protect the free-tier quota (1K/day).
- Fails OPEN: when disabled, unconfigured, or on any error the lookup returns
  {"available": False} so traffic is never blocked by an outage.

Docs: https://proxycheck.io/api/
"""
import base64
import hashlib
import ipaddress
import logging
import time
from datetime import datetime, timezone

import httpx
from cryptography.fernet import Fernet, InvalidToken

from .config import settings
from .db import db
from .utils import now_iso

logger = logging.getLogger("midgate.ipintel")

_SETTINGS_ID = "proxycheck"
_CACHE_TTL = 86400.0  # 24h per IP


def _build_fernet(secret: str) -> Fernet:
    """Build a Fernet from IPINTEL_SECRET.

    Accepts an already-valid Fernet key as-is (keeps existing encrypted data
    working). Any other string is deterministically normalized into a valid
    32-byte url-safe base64 key, so the app never 500s on a misconfigured secret.
    """
    raw = (secret or "").strip()
    try:
        return Fernet(raw.encode())
    except Exception:
        digest = hashlib.sha256(raw.encode()).digest()
        return Fernet(base64.urlsafe_b64encode(digest))


_fernet = _build_fernet(settings.IPINTEL_SECRET)

# in-memory config cache (reloaded from DB on change / TTL)
_cfg: dict = {"loaded_at": 0.0, "enabled": False, "key": None, "has_key": False,
              "updated_at": None, "updated_by": None}
_CFG_TTL = 15.0

# in-memory per-IP result cache + runtime stats
_ip_cache: dict[str, tuple[float, dict]] = {}
_stats = {"queries": 0, "cache_hits": 0, "errors": 0,
          "last_query_at": None, "last_error": None, "last_test": None}


def _encrypt(raw: str) -> str:
    return _fernet.encrypt(raw.strip().encode()).decode()


def _decrypt(token: str) -> str | None:
    try:
        return _fernet.decrypt(token.encode()).decode()
    except (InvalidToken, Exception):
        return None


async def _load_cfg(force: bool = False) -> dict:
    if not force and _cfg["loaded_at"] > time.time() - _CFG_TTL:
        return _cfg
    doc = await db.platform_settings.find_one({"_id": _SETTINGS_ID})
    _cfg["loaded_at"] = time.time()
    if not doc:
        _cfg.update({"enabled": False, "key": None, "has_key": False,
                     "updated_at": None, "updated_by": None, "options": {}})
        return _cfg
    key = _decrypt(doc["encrypted_api_key"]) if doc.get("encrypted_api_key") else None
    _cfg.update({
        "enabled": bool(doc.get("enabled")),
        "key": key,
        "has_key": bool(doc.get("encrypted_api_key")),
        "updated_at": doc.get("updated_at"),
        "updated_by": doc.get("updated_by"),
        "options": doc.get("options", {}),
    })
    return _cfg


def _invalidate_cfg():
    _cfg["loaded_at"] = 0.0


def _is_public_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (addr.is_private or addr.is_loopback or addr.is_link_local
                or addr.is_multicast or addr.is_reserved or addr.is_unspecified)


_VPN_TYPES = {"VPN", "Public Proxy", "Web Proxy", "Tor", "Compromised Server", "Anonymizing VPN"}


def _normalize(ip: str, row: dict) -> dict:
    proxy = row.get("proxy")
    typ = row.get("type")
    return {
        "available": True,
        "ip": ip,
        "is_proxy": proxy == "yes",
        "is_vpn": (row.get("vpn") == "yes") or (typ in _VPN_TYPES),
        "type": typ,
        "risk": row.get("risk"),
        "asn": row.get("asn"),
        "provider": row.get("provider") or row.get("organisation"),
        "country": row.get("country"),
        "country_iso": row.get("isocode") or row.get("country_code"),
    }


async def _call_proxycheck(ip: str, key: str) -> dict:
    params = {"key": key, "vpn": 1, "asn": 1, "risk": 1}
    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=2.0)) as client:
        resp = await client.get(f"https://proxycheck.io/v2/{ip}", params=params)
    try:
        body = resp.json()
    except ValueError:
        raise RuntimeError("proxycheck.io returned non-JSON")
    status = body.get("status")
    if resp.status_code != 200 or status in {"denied", "error"}:
        raise RuntimeError(body.get("message") or f"proxycheck status={status}")
    row = body.get(ip)
    if not isinstance(row, dict):
        raise RuntimeError("IP result missing from response")
    return _normalize(ip, row)


async def check_ip(ip: str) -> dict:
    """Return normalized intelligence for an IP. Fails open with available=False."""
    cfg = await _load_cfg()
    if not cfg["enabled"] or not cfg["key"]:
        return {"available": False, "reason": "not_configured"}
    if not _is_public_ip(ip):
        return {"available": False, "reason": "non_public_ip"}

    entry = _ip_cache.get(ip)
    if entry and entry[0] > time.time():
        _stats["cache_hits"] += 1
        return {**entry[1], "cached": True}

    try:
        result = await _call_proxycheck(ip, cfg["key"])
        _stats["queries"] += 1
        _stats["last_query_at"] = now_iso()
        if len(_ip_cache) < 50000:
            _ip_cache[ip] = (time.time() + _CACHE_TTL, result)
        return result
    except Exception as exc:
        _stats["errors"] += 1
        _stats["last_error"] = str(exc)[:200]
        logger.warning("proxycheck lookup failed for %s: %s", ip, exc)
        if entry:  # serve stale on failure
            return {**entry[1], "cached": True, "degraded": True}
        return {"available": False, "reason": "unavailable"}


async def test_connection() -> dict:
    cfg = await _load_cfg(force=True)
    if not cfg["key"]:
        res = {"ok": False, "message": "No API key configured"}
    else:
        try:
            r = await _call_proxycheck("8.8.8.8", cfg["key"])
            res = {"ok": True, "message": f"Connected — sample {r['ip']} resolved",
                   "sample": {"country": r.get("country"), "provider": r.get("provider")}}
        except Exception as exc:
            res = {"ok": False, "message": str(exc)[:200]}
    _stats["last_test"] = {**res, "at": now_iso()}
    return res


async def save_config(*, api_key: str | None, enabled: bool | None,
                      admin_email: str) -> None:
    updates: dict = {"updated_at": now_iso(), "updated_by": admin_email}
    if api_key is not None and api_key.strip():
        updates["encrypted_api_key"] = _encrypt(api_key)
    if enabled is not None:
        updates["enabled"] = enabled
    await db.platform_settings.update_one(
        {"_id": _SETTINGS_ID}, {"$set": updates}, upsert=True)
    _invalidate_cfg()


async def remove_key() -> None:
    await db.platform_settings.update_one(
        {"_id": _SETTINGS_ID},
        {"$set": {"enabled": False, "updated_at": now_iso()},
         "$unset": {"encrypted_api_key": ""}}, upsert=True)
    _invalidate_cfg()


def _mask(key: str | None) -> str | None:
    if not key:
        return None
    if len(key) <= 8:
        return "•" * len(key)
    return f"{key[:4]}…{key[-4:]}"


async def get_status() -> dict:
    cfg = await _load_cfg(force=True)
    return {
        "provider": "proxycheck.io",
        "enabled": cfg["enabled"],
        "configured": cfg["has_key"],
        "key_masked": _mask(cfg["key"]) if cfg["has_key"] else None,
        "updated_at": cfg.get("updated_at"),
        "updated_by": cfg.get("updated_by"),
        "stats": {
            "queries": _stats["queries"],
            "cache_hits": _stats["cache_hits"],
            "errors": _stats["errors"],
            "cached_ips": len(_ip_cache),
            "last_query_at": _stats["last_query_at"],
            "last_error": _stats["last_error"],
        },
        "last_test": _stats["last_test"],
    }
