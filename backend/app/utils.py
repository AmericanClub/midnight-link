import hashlib
import secrets
import string
from datetime import datetime, timezone

_ALPHABET = string.ascii_letters + string.digits


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat()


def gen_alias(length: int = 6) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def visitor_hash(ip: str, user_agent: str) -> str:
    """Rotating daily visitor hash. Raw IP never stored."""
    day = now_utc().strftime("%Y-%m-%d")
    raw = f"{ip}|{user_agent}|{day}|midgate-salt"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def parse_user_agent(ua: str) -> dict:
    ua_l = (ua or "").lower()
    # device
    if any(k in ua_l for k in ["ipad", "tablet"]):
        device = "Tablet"
    elif any(k in ua_l for k in ["mobi", "iphone", "android"]):
        device = "Mobile"
    else:
        device = "Desktop"
    # os
    if "windows" in ua_l:
        os_name = "Windows"
    elif "iphone" in ua_l or "ipad" in ua_l or "ios" in ua_l:
        os_name = "iOS"
    elif "mac os" in ua_l or "macintosh" in ua_l:
        os_name = "macOS"
    elif "android" in ua_l:
        os_name = "Android"
    elif "linux" in ua_l:
        os_name = "Linux"
    else:
        os_name = "Unknown"
    # browser
    if "edg" in ua_l:
        browser = "Edge"
    elif "opr" in ua_l or "opera" in ua_l:
        browser = "Opera"
    elif "chrome" in ua_l and "chromium" not in ua_l:
        browser = "Chrome"
    elif "firefox" in ua_l:
        browser = "Firefox"
    elif "safari" in ua_l:
        browser = "Safari"
    elif ua_l == "":
        browser = "Unknown"
    else:
        browser = "Other"
    is_bot = any(k in ua_l for k in ["bot", "crawler", "spider", "curl", "wget", "python-requests", "headless"])
    return {"device": device, "os": os_name, "browser": browser, "is_bot": is_bot}


def client_ip(request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "0.0.0.0"


def client_country(request) -> str:
    for h in ["cf-ipcountry", "x-vercel-ip-country", "x-country-code"]:
        v = request.headers.get(h)
        if v and v.upper() not in ("XX", "T1"):
            return v.upper()
    return "Unknown"
