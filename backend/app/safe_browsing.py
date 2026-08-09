"""Google Safe Browsing (Lookup API v4) — scan destination URLs for phishing,
malware and unwanted software BEFORE a short link / QR is created.

- API key entered by a platform admin, encrypted at rest (Fernet) in
  db.platform_settings (_id="safebrowsing"). Env fallback: SAFE_BROWSING_API_KEY.
- Per-URL in-memory TTL cache to protect the free quota (5k/day default).
- Fails OPEN: when disabled, unconfigured, or on any error the scan returns
  {"status": "unavailable"} (or "disabled") so link creation is never blocked
  by an outage — ONLY an explicit threat match blocks.

Note: Safe Browsing v4 is free but documented by Google as non-commercial;
use Web Risk for fully commercial use.
Docs: https://developers.google.com/safe-browsing/v4/lookup-api
"""
import base64
import hashlib
import logging
import time

import httpx
from cryptography.fernet import Fernet

from .config import settings
from .db import db
from .utils import now_iso

logger = logging.getLogger("midgate.safebrowsing")

_SETTINGS_ID = "safebrowsing"
_CACHE_TTL = 300.0  # per-URL verdict cache
_SB_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
_THREAT_TYPES = ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"]
_THREAT_LABELS = {
    "SOCIAL_ENGINEERING": "phishing / social engineering",
    "MALWARE": "malware",
    "UNWANTED_SOFTWARE": "unwanted software",
    "POTENTIALLY_HARMFUL_APPLICATION": "a potentially harmful application",
}


def _build_fernet(secret: str) -> Fernet:
    raw = (secret or "").strip()
    try:
        return Fernet(raw.encode())
    except Exception:
        return Fernet(base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest()))


_fernet = _build_fernet(settings.IPINTEL_SECRET)

_cfg: dict = {"loaded_at": 0.0, "enabled": False, "key": None, "has_key": False,
              "updated_at": None, "updated_by": None, "source": None}
_CFG_TTL = 15.0

_url_cache: dict[str, tuple[float, dict]] = {}
_stats = {"queries": 0, "cache_hits": 0, "blocked": 0, "errors": 0,
          "last_query_at": None, "last_error": None, "last_test": None}


class UnsafeDestination(Exception):
    def __init__(self, threat_label: str, threat_type: str):
        self.threat_label = threat_label
        self.threat_type = threat_type
        super().__init__(threat_label)


def _encrypt(raw: str) -> str:
    return _fernet.encrypt(raw.strip().encode()).decode()


def _decrypt(token: str) -> str | None:
    try:
        return _fernet.decrypt(token.encode()).decode()
    except Exception:
        return None


async def _load_cfg(force: bool = False) -> dict:
    if not force and _cfg["loaded_at"] > time.time() - _CFG_TTL:
        return _cfg
    doc = await db.platform_settings.find_one({"_id": _SETTINGS_ID})
    _cfg["loaded_at"] = time.time()
    env_key = settings.SAFE_BROWSING_API_KEY or None
    if not doc:
        _cfg.update({"enabled": bool(env_key), "key": env_key, "has_key": bool(env_key),
                     "updated_at": None, "updated_by": None, "source": "env" if env_key else None})
        return _cfg
    db_key = _decrypt(doc["encrypted_api_key"]) if doc.get("encrypted_api_key") else None
    key = db_key or env_key
    _cfg.update({
        "enabled": bool(doc.get("enabled")),
        "key": key,
        "has_key": bool(key),
        "updated_at": doc.get("updated_at"),
        "updated_by": doc.get("updated_by"),
        "source": "db" if db_key else ("env" if env_key else None),
    })
    return _cfg


def _invalidate_cfg():
    _cfg["loaded_at"] = 0.0


async def _call(url: str, key: str) -> list:
    body = {
        "client": {"clientId": "midnight-link", "clientVersion": "1.0.0"},
        "threatInfo": {
            "threatTypes": _THREAT_TYPES,
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=2.0)) as client:
        resp = await client.post(_SB_URL, params={"key": key}, json=body)
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}")
    return resp.json().get("matches", [])


async def scan_url(url: str) -> dict:
    """Return {'status': 'clean'|'blocked'|'unavailable'|'disabled', ...}. Fail-open."""
    cfg = await _load_cfg()
    if not cfg["enabled"] or not cfg["key"]:
        return {"status": "disabled"}
    entry = _url_cache.get(url)
    if entry and entry[0] > time.time():
        _stats["cache_hits"] += 1
        return {**entry[1], "cached": True}
    try:
        matches = await _call(url, cfg["key"])
        _stats["queries"] += 1
        _stats["last_query_at"] = now_iso()
        if matches:
            tt = matches[0].get("threatType", "")
            result = {"status": "blocked", "threat_type": tt,
                      "threat_label": _THREAT_LABELS.get(tt, tt.lower().replace("_", " ") or "a security threat")}
            _stats["blocked"] += 1
        else:
            result = {"status": "clean"}
        if len(_url_cache) < 50000:
            _url_cache[url] = (time.time() + _CACHE_TTL, result)
        return result
    except Exception as exc:
        _stats["errors"] += 1
        _stats["last_error"] = str(exc)[:200]
        logger.warning("safe browsing scan failed for %s: %s", url, exc)
        return {"status": "unavailable"}


async def assert_url_safe(url: str) -> str:
    """Scan a URL and raise UnsafeDestination on an explicit threat match.
    Returns the scan status ('clean'/'unavailable'/'disabled') otherwise."""
    scan = await scan_url(url)
    if scan.get("status") == "blocked":
        raise UnsafeDestination(scan.get("threat_label", "a security threat"), scan.get("threat_type", ""))
    return scan.get("status", "disabled")


async def test_connection() -> dict:
    cfg = await _load_cfg(force=True)
    if not cfg["key"]:
        res = {"ok": False, "message": "No API key configured"}
    else:
        try:
            matches = await _call("https://testsafebrowsing.appspot.com/s/malware.html", cfg["key"])
            if matches:
                res = {"ok": True, "message": "Connected — threat detection working (Google test URL flagged)."}
            else:
                res = {"ok": True, "message": "Connected — API reachable and key valid."}
        except Exception as exc:
            res = {"ok": False, "message": str(exc)[:200]}
    _stats["last_test"] = {**res, "at": now_iso()}
    return res


async def save_config(*, api_key: str | None, enabled: bool | None, admin_email: str) -> None:
    updates: dict = {"updated_at": now_iso(), "updated_by": admin_email}
    if api_key is not None and api_key.strip():
        updates["encrypted_api_key"] = _encrypt(api_key)
    if enabled is not None:
        updates["enabled"] = enabled
    await db.platform_settings.update_one({"_id": _SETTINGS_ID}, {"$set": updates}, upsert=True)
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
        "provider": "Google Safe Browsing",
        "enabled": cfg["enabled"],
        "configured": cfg["has_key"],
        "key_masked": _mask(cfg["key"]) if cfg["has_key"] else None,
        "source": cfg.get("source"),
        "updated_at": cfg.get("updated_at"),
        "updated_by": cfg.get("updated_by"),
        "stats": {
            "queries": _stats["queries"],
            "cache_hits": _stats["cache_hits"],
            "blocked": _stats["blocked"],
            "errors": _stats["errors"],
            "cached_urls": len(_url_cache),
            "last_query_at": _stats["last_query_at"],
            "last_error": _stats["last_error"],
        },
        "last_test": _stats["last_test"],
    }
