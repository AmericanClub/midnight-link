"""Self-hosted threat intelligence for Midnight Link Protect.

- Tor exit-node set (refreshed from the public bulk list, with a seed fallback)
- Datacenter / hosting CIDR ranges (curated seed; admin-extendable)
- User-agent classification (search/social/monitoring/automation/headless)
- Simple in-memory sliding-window rate limiter

Designed behind the IPIntelProvider abstraction so an API-key provider
(proxycheck.io / IPQualityScore / IP2Proxy) can be dropped in later without
touching business logic.
"""
import ipaddress
import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

logger = logging.getLogger("midgate.intel")

# --- curated datacenter / hosting ranges (representative, not exhaustive) --- #
DATACENTER_CIDRS = [
    # AWS
    "3.0.0.0/9", "13.32.0.0/15", "15.177.0.0/18", "18.32.0.0/11", "52.0.0.0/11",
    "54.144.0.0/12", "35.152.0.0/13",
    # Google Cloud
    "34.0.0.0/9", "35.184.0.0/13", "104.196.0.0/14", "130.211.0.0/16",
    # Microsoft Azure
    "13.64.0.0/11", "20.0.0.0/8", "40.64.0.0/10", "104.40.0.0/13",
    # DigitalOcean
    "104.131.0.0/16", "138.197.0.0/16", "159.203.0.0/16", "165.227.0.0/16",
    "167.71.0.0/16", "104.248.0.0/16", "68.183.0.0/16",
    # OVH
    "51.68.0.0/16", "51.75.0.0/16", "54.36.0.0/14", "137.74.0.0/16", "141.94.0.0/16",
    # Hetzner
    "5.9.0.0/16", "88.99.0.0/16", "94.130.0.0/16", "116.202.0.0/16", "159.69.0.0/16",
    # Linode
    "45.33.0.0/16", "45.79.0.0/16", "139.144.0.0/16", "172.104.0.0/15", "45.56.0.0/16",
    # Vultr
    "45.32.0.0/16", "45.63.0.0/16", "108.61.0.0/16", "149.28.0.0/16", "66.42.0.0/16",
    # Cloudflare (often proxy/WARP)
    "104.16.0.0/13", "172.64.0.0/13",
]

# Seed a few well-known Tor exit nodes so detection works before first refresh.
TOR_SEED = {"185.220.101.1", "199.87.154.255", "204.13.164.118"}

_datacenter_nets = [ipaddress.ip_network(c) for c in DATACENTER_CIDRS]
_tor_set: set[str] = set(TOR_SEED)
_state = {"tor_count": len(_tor_set), "datacenter_ranges": len(_datacenter_nets), "last_refresh": None}

_lookup_cache: dict[str, dict] = {}


def _parse(ip: str):
    try:
        return ipaddress.ip_address(ip)
    except ValueError:
        return None


def ip_in_cidrs(ip: str, nets) -> bool:
    addr = _parse(ip)
    if addr is None:
        return False
    return any(addr in n for n in nets)


def is_tor(ip: str) -> bool:
    return ip in _tor_set


def is_datacenter(ip: str) -> bool:
    return ip_in_cidrs(ip, _datacenter_nets)


def lookup(ip: str) -> dict:
    if ip in _lookup_cache:
        return _lookup_cache[ip]
    dc = is_datacenter(ip)
    result = {
        "ip": ip,
        "is_tor": is_tor(ip),
        "is_datacenter": dc,
        "is_hosting": dc,
        # free tier can't reliably tell residential proxy/VPN apart; treat
        # datacenter as proxy-ish. A paid provider fills these accurately.
        "is_proxy": dc,
        "is_vpn": False,
        "asn": None,
    }
    if len(_lookup_cache) < 50000:
        _lookup_cache[ip] = result
    return result


def feeds_state() -> dict:
    return dict(_state)


async def refresh_tor() -> int:
    """Fetch the public Tor bulk exit list. Falls back to the seed on failure."""
    import asyncio
    try:
        import requests
        def _fetch():
            r = requests.get("https://check.torproject.org/torbulkexitlist", timeout=8)
            r.raise_for_status()
            return r.text
        text = await asyncio.to_thread(_fetch)
        ips = {line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")}
        if ips:
            global _tor_set
            _tor_set = ips | TOR_SEED
            _lookup_cache.clear()
        _state["tor_count"] = len(_tor_set)
        _state["last_refresh"] = datetime.now(timezone.utc).isoformat()
        logger.info("Tor exit list refreshed: %d nodes", len(_tor_set))
    except Exception as e:  # offline / blocked — keep seed
        _state["last_refresh"] = datetime.now(timezone.utc).isoformat()
        logger.warning("Tor refresh failed (%s); using seed of %d", e, len(_tor_set))
    return _state["tor_count"]


# ------------------------------ UA classification ------------------------- #
SEARCH_BOTS = ["googlebot", "bingbot", "duckduckbot", "yandex", "baiduspider", "sogou", "applebot"]
SOCIAL_BOTS = ["facebookexternalhit", "twitterbot", "linkedinbot", "slackbot", "whatsapp",
               "telegrambot", "discordbot", "pinterest", "redditbot"]
MONITORING_BOTS = ["uptimerobot", "pingdom", "statuscake", "site24x7", "newrelic"]
AUTOMATION = ["curl", "wget", "python-requests", "python-urllib", "go-http-client", "okhttp",
              "java/", "axios", "node-fetch", "libwww", "scrapy", "http_request", "postmanruntime"]
HEADLESS = ["headlesschrome", "phantomjs", "puppeteer", "playwright", "selenium", "electron"]


def classify_ua(ua: str) -> dict:
    ua_l = (ua or "").lower()
    is_headless = any(k in ua_l for k in HEADLESS)
    if not ua_l:
        return {"is_bot": True, "category": "automation", "is_headless": False, "crawler_name": "empty-ua"}
    for name, group, cat in (
        (SEARCH_BOTS, "search_bot", "search_bot"),
        (SOCIAL_BOTS, "social_bot", "social_bot"),
        (MONITORING_BOTS, "monitoring_bot", "monitoring_bot"),
    ):
        for k in name:
            if k in ua_l:
                return {"is_bot": True, "category": group, "is_headless": is_headless, "crawler_name": k}
    for k in AUTOMATION:
        if k in ua_l:
            return {"is_bot": True, "category": "automation", "is_headless": is_headless, "crawler_name": k}
    if is_headless:
        return {"is_bot": True, "category": "headless", "is_headless": True, "crawler_name": "headless"}
    if "bot" in ua_l or "crawler" in ua_l or "spider" in ua_l:
        return {"is_bot": True, "category": "automation", "is_headless": False, "crawler_name": "generic-bot"}
    return {"is_bot": False, "category": "human", "is_headless": False, "crawler_name": None}


# ------------------------------ rate limiter ------------------------------ #
class SlidingWindowLimiter:
    def __init__(self, window: int = 60):
        self.window = window
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str, limit: int) -> bool:
        if not limit or limit <= 0:
            return True
        now = time.time()
        dq = self._hits[key]
        while dq and dq[0] < now - self.window:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        return True


rate_limiter = SlidingWindowLimiter(60)
