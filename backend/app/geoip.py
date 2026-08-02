"""Offline IP -> country resolution via geoip2fast.

Fully self-hosted: the country database ships bundled with the package, so
there is no API key and no external call at request time. Behind a tiny
wrapper so a paid provider can be swapped in later without touching callers.
"""
import logging

logger = logging.getLogger("midgate.geoip")

_geo = None
_BAD = {"", "--", "XX", "T1", "UNKNOWN", "PRIVATE NETWORK", "RESERVED"}


def _reader():
    global _geo
    if _geo is None:
        from geoip2fast import GeoIP2Fast
        _geo = GeoIP2Fast(verbose=False)
        logger.info("GeoIP2Fast loaded (offline country DB)")
    return _geo


def warm() -> None:
    try:
        _reader()
    except Exception as e:  # pragma: no cover - never block startup
        logger.warning("GeoIP warm failed: %s", e)


def country_of(ip: str) -> str:
    """Return ISO-2 country code for an IP, or 'Unknown' when unresolved."""
    try:
        res = _reader().lookup(ip)
        cc = (res.country_code or "").strip().upper()
        if cc and cc not in _BAD:
            return cc
    except Exception:
        pass
    return "Unknown"
