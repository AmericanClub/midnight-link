"""MidGate Protect — risk scoring, configurable rules, IP allow/block lists,
threat-intel signals, and the full per-request evaluation pipeline."""
import hashlib
import hmac
import ipaddress
import time
import uuid

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ..db import db
from ..config import settings
from ..utils import now_iso, parse_user_agent
from ..intel import lookup as intel_lookup, classify_ua, feeds_state, refresh_tor, rate_limiter
from ..geoip import country_of
from .workspace import get_current_workspace

router = APIRouter(prefix="/api/security", tags=["security"])

ACTIONS = {"allow", "challenge", "block", "log_only"}
OPERATORS = {"equals", "not_equals", "in", "not_in", "contains", "gt", "lt"}
FIELDS = {"country", "device", "browser", "os", "is_bot", "risk_score", "referrer",
          "is_tor", "is_datacenter", "is_proxy", "is_headless", "bot_category"}
THRESHOLDS = [(30, "allow"), (60, "challenge"), (80, "block"), (101, "block")]

DEFAULT_PROTECTION = {
    "enabled": False,
    "preset": "off",
    "block_bots": True,
    "block_tor": False,
    "block_datacenter": False,
    "block_proxy_vpn": False,
    "allow_countries": [],
    "block_countries": [],
    "block_action": "fallback",   # fallback | block_page | notfound | redirect
    "block_redirect_url": "",
    "rate_limit_per_min": 0,
}

# One-click protection presets. Each preset only sets the fields it cares about;
# everything else falls back to DEFAULT_PROTECTION. "custom" means the user
# hand-tuned the toggles and no preset is active.
PROTECTION_PRESETS = {
    "off": {
        "enabled": False,
    },
    "moderate": {
        "enabled": True,
        "block_bots": True,
        "block_tor": True,
        "block_datacenter": False,
        "block_proxy_vpn": False,
        "block_action": "fallback",
    },
    "strict": {
        "enabled": True,
        "block_bots": True,
        "block_tor": True,
        "block_datacenter": True,
        "block_proxy_vpn": True,
        "block_action": "block_page",
    },
}
PRESET_META = {
    "off": {"label": "Off", "description": "Log only — nothing is blocked."},
    "moderate": {"label": "Moderate", "description": "Block bots and Tor exit nodes; allow normal traffic."},
    "strict": {"label": "Strict", "description": "Block bots, Tor, datacenter IPs and proxy/VPN."},
}

# --------------------------- caches --------------------------------------- #
_RULES_CACHE: dict[str, tuple[float, list]] = {}
_IP_CACHE: dict[str, tuple[float, dict]] = {}
_GLOBAL_CACHE: tuple[float, list] = (0.0, [])
_TTL = 15.0


def invalidate_rules(workspace_id):
    _RULES_CACHE.pop(workspace_id, None)


def invalidate_ip(workspace_id):
    _IP_CACHE.pop(workspace_id, None)


async def get_rules(workspace_id: str) -> list:
    entry = _RULES_CACHE.get(workspace_id)
    if entry and entry[0] > time.time():
        return entry[1]
    rules = await db.security_rules.find(
        {"workspace_id": workspace_id, "enabled": True}, {"_id": 0}
    ).sort("priority", 1).to_list(200)
    _RULES_CACHE[workspace_id] = (time.time() + _TTL, rules)
    return rules


async def get_ip_rules(workspace_id: str) -> dict:
    entry = _IP_CACHE.get(workspace_id)
    if entry and entry[0] > time.time():
        return entry[1]
    rows = await db.ip_rules.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(1000)
    grouped = {"allow": [r["value"] for r in rows if r["list_type"] == "allow"],
               "block": [r["value"] for r in rows if r["list_type"] == "block"]}
    _IP_CACHE[workspace_id] = (time.time() + _TTL, grouped)
    return grouped


async def get_global_blocklist() -> list:
    global _GLOBAL_CACHE
    if _GLOBAL_CACHE[0] > time.time():
        return _GLOBAL_CACHE[1]
    rows = await db.global_blocklist.find({}, {"_id": 0}).to_list(5000)
    values = [r["value"] for r in rows]
    _GLOBAL_CACHE = (time.time() + _TTL, values)
    return values


def invalidate_global():
    global _GLOBAL_CACHE
    _GLOBAL_CACHE = (0.0, [])


def match_ip(ip: str, values: list) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for v in values:
        try:
            if "/" in v:
                if addr in ipaddress.ip_network(v, strict=False):
                    return True
            elif v == ip:
                return True
        except ValueError:
            continue
    return False


# --------------------------- signals + risk ------------------------------- #
def build_signals(ip: str, ua: str, referrer: str = "Direct", country: str = "Unknown") -> dict:
    intel = intel_lookup(ip)
    ua_cls = classify_ua(ua)
    parsed = parse_user_agent(ua)
    if not country or str(country).upper() == "UNKNOWN":
        country = country_of(ip)
    return {
        "ip": ip,
        "country": country,
        "device": parsed["device"],
        "browser": parsed["browser"],
        "os": parsed["os"],
        "referrer": (referrer or "Direct").split("?")[0][:200],
        "user_agent": ua,
        "is_bot": ua_cls["is_bot"],
        "bot_category": ua_cls["category"],
        "is_headless": ua_cls["is_headless"],
        "is_tor": intel["is_tor"],
        "is_datacenter": intel["is_datacenter"],
        "is_proxy": intel["is_proxy"],
        "is_vpn": intel["is_vpn"],
    }


def compute_risk(signals: dict) -> tuple[int, list]:
    score, reasons = 0, []
    if signals.get("is_bot"):
        score += 50
        reasons.append(f"Bot signature ({signals.get('bot_category', 'automation')})")
    if signals.get("is_headless"):
        score += 45
        reasons.append("Headless browser signals")
    if signals.get("is_tor"):
        score += 40
        reasons.append("Tor exit node")
    if signals.get("is_proxy"):
        score += 30
        reasons.append("Proxy / anonymizer")
    if signals.get("is_datacenter"):
        score += 25
        reasons.append("Datacenter / hosting IP")
    intel_risk = signals.get("intel_risk")
    if isinstance(intel_risk, (int, float)):
        if intel_risk >= 66:
            score += 30
            reasons.append(f"High-risk IP ({int(intel_risk)}/100, proxycheck.io)")
        elif intel_risk >= 33:
            score += 15
            reasons.append(f"Elevated-risk IP ({int(intel_risk)}/100, proxycheck.io)")
    if not signals.get("user_agent"):
        score += 25
        reasons.append("Missing user-agent")
    if signals.get("browser") in ("Other", "Unknown"):
        score += 8
    return min(score, 100), reasons


def _match_condition(cond, signals) -> bool:
    field, op, value = cond.get("field"), cond.get("operator"), cond.get("value")
    actual = signals.get(field)
    try:
        if op == "equals":
            return str(actual).lower() == str(value).lower()
        if op == "not_equals":
            return str(actual).lower() != str(value).lower()
        if op in ("in", "not_in"):
            vals = value if isinstance(value, list) else str(value).split(",")
            hit = str(actual).lower() in [str(v).strip().lower() for v in vals]
            return hit if op == "in" else not hit
        if op == "contains":
            return str(value).lower() in str(actual).lower()
        if op == "gt":
            return float(actual) > float(value)
        if op == "lt":
            return float(actual) < float(value)
    except (ValueError, TypeError):
        return False
    return False


def default_decision(score: int) -> str:
    for limit, action in THRESHOLDS:
        if score < limit:
            return action
    return "block"


def evaluate(signals: dict, rules: list) -> dict:
    score, reasons = compute_risk(signals)
    s = {**signals, "risk_score": score}
    matched = None
    for rule in rules:
        conds = rule.get("conditions", [])
        if conds and all(_match_condition(c, s) for c in conds):
            matched = rule
            break
    if matched:
        decision = matched["action"]
        reasons = [f"Matched rule: {matched['name']}"] + reasons
    else:
        decision = default_decision(score)
    return {"risk_score": score, "decision": decision, "reasons": reasons,
            "matched_rule_id": matched["id"] if matched else None, "policy_version": 1}


async def enrich_signals(signals: dict, ip: str) -> dict:
    """Overlay accurate proxycheck.io intelligence onto base signals when configured.

    Fails open: any error leaves the base (offline) signals untouched.
    """
    try:
        from ..ip_intel import check_ip
        pc = await check_ip(ip)
    except Exception:
        return signals
    if not pc.get("available"):
        return signals
    if pc.get("is_proxy"):
        signals["is_proxy"] = True
    if pc.get("is_vpn"):
        signals["is_vpn"] = True
    if pc.get("type") in ("Compromised Server", "Public Proxy", "Web Proxy"):
        signals["is_datacenter"] = True
    if pc.get("asn"):
        signals["asn"] = pc["asn"]
    if pc.get("provider"):
        signals["provider"] = pc["provider"]
    if pc.get("risk") is not None:
        signals["intel_risk"] = pc["risk"]
    if pc.get("country_iso") and str(signals.get("country", "")).upper() in ("", "UNKNOWN"):
        signals["country"] = pc["country_iso"]
    signals["intel_source"] = "proxycheck.io"
    return signals


async def evaluate_request(workspace_id: str, link: dict | None, ip: str, ua: str,
                           referrer: str = "Direct", country: str = "Unknown") -> dict:
    """Full pipeline: whitelist -> blacklist -> per-link protection -> rules -> risk."""
    signals = build_signals(ip, ua, referrer, country)
    await enrich_signals(signals, ip)
    score, _ = compute_risk(signals)
    signals["risk_score"] = score

    ip_rules = await get_ip_rules(workspace_id)
    if match_ip(ip, ip_rules["allow"]):
        return {"decision": "allow", "action": "allow", "risk_score": score,
                "reasons": ["IP allowlisted"], "matched_rule_id": None, "signals": signals,
                "challenge_result": "n/a"}

    if match_ip(ip, ip_rules["block"]) or match_ip(ip, await get_global_blocklist()):
        return {"decision": "block", "action": "block_page", "risk_score": max(score, 90),
                "reasons": ["IP blocklisted"], "matched_rule_id": None, "signals": signals,
                "challenge_result": "n/a"}

    prot = (link or {}).get("protection") or {}
    if prot.get("enabled"):
        reasons = []
        if prot.get("block_bots") and signals["is_bot"]:
            reasons.append("Bot blocked by link policy")
        if prot.get("block_tor") and signals["is_tor"]:
            reasons.append("Tor blocked by link policy")
        if prot.get("block_datacenter") and signals["is_datacenter"]:
            reasons.append("Datacenter IP blocked by link policy")
        if prot.get("block_proxy_vpn") and (signals["is_proxy"] or signals["is_vpn"]):
            reasons.append("Proxy/VPN blocked by link policy")
        bc = [c.upper() for c in prot.get("block_countries", [])]
        ac = [c.upper() for c in prot.get("allow_countries", [])]
        country = signals["country"].upper()
        # only apply country rules when geo is actually resolved
        if country != "UNKNOWN":
            if bc and country in bc:
                reasons.append(f"Country {signals['country']} blocked")
            if ac and country not in ac:
                reasons.append(f"Country {signals['country']} not allowlisted")
        rl = prot.get("rate_limit_per_min", 0)
        if rl and not rate_limiter.allow(f"{link['id']}:{ip}", rl):
            reasons.append("Rate limit exceeded")
        if reasons:
            return {"decision": "block", "action": prot.get("block_action", "fallback"),
                    "block_redirect_url": prot.get("block_redirect_url", ""),
                    "risk_score": max(score, 80), "reasons": reasons, "matched_rule_id": None,
                    "signals": signals, "challenge_result": "n/a"}

    rules = await get_rules(workspace_id)
    res = evaluate(signals, rules)
    action = "block_page" if res["decision"] == "block" else res["decision"]
    return {**res, "action": action, "signals": signals, "challenge_result": "n/a"}


# --------------------------- challenge token ------------------------------ #
def challenge_token(alias: str, visitor_id: str) -> str:
    msg = f"{alias}:{visitor_id}".encode()
    return hmac.new(settings.JWT_SECRET.encode(), msg, hashlib.sha256).hexdigest()[:16]


def verify_challenge(alias: str, visitor_id: str, token: str) -> bool:
    return hmac.compare_digest(challenge_token(alias, visitor_id), token or "")


# --------------------------- rules CRUD ----------------------------------- #
class Condition(BaseModel):
    field: str
    operator: str
    value: object


class RuleInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    action: str
    priority: int = 100
    enabled: bool = True
    description: str | None = None
    conditions: list[Condition] = Field(default_factory=list)


def _validate_rule(payload: RuleInput):
    if payload.action not in ACTIONS:
        raise HTTPException(status_code=400, detail=f"action must be one of {sorted(ACTIONS)}")
    for c in payload.conditions:
        if c.field not in FIELDS:
            raise HTTPException(status_code=400, detail=f"unknown field '{c.field}'")
        if c.operator not in OPERATORS:
            raise HTTPException(status_code=400, detail=f"unknown operator '{c.operator}'")


@router.get("/rules")
async def list_rules(ws=Depends(get_current_workspace)):
    rows = await db.security_rules.find({"workspace_id": ws["id"]}, {"_id": 0}).sort("priority", 1).to_list(200)
    return {"items": rows, "thresholds": THRESHOLDS, "fields": sorted(FIELDS)}


@router.post("/rules")
async def create_rule(payload: RuleInput, ws=Depends(get_current_workspace)):
    _validate_rule(payload)
    rule = {"id": str(uuid.uuid4()), "workspace_id": ws["id"], "name": payload.name,
            "action": payload.action, "priority": payload.priority, "enabled": payload.enabled,
            "description": payload.description, "conditions": [c.model_dump() for c in payload.conditions],
            "created_at": now_iso(), "updated_at": now_iso()}
    await db.security_rules.insert_one({**rule})
    invalidate_rules(ws["id"])
    return rule


@router.patch("/rules/{rule_id}")
async def update_rule(rule_id: str, payload: RuleInput, ws=Depends(get_current_workspace)):
    _validate_rule(payload)
    existing = await db.security_rules.find_one({"id": rule_id, "workspace_id": ws["id"]})
    if not existing:
        raise HTTPException(status_code=404, detail="Not found")
    await db.security_rules.update_one({"id": rule_id}, {"$set": {
        "name": payload.name, "action": payload.action, "priority": payload.priority,
        "enabled": payload.enabled, "description": payload.description,
        "conditions": [c.model_dump() for c in payload.conditions], "updated_at": now_iso()}})
    invalidate_rules(ws["id"])
    return await db.security_rules.find_one({"id": rule_id}, {"_id": 0})


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, ws=Depends(get_current_workspace)):
    res = await db.security_rules.delete_one({"id": rule_id, "workspace_id": ws["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    invalidate_rules(ws["id"])
    return {"ok": True}


# --------------------------- IP allow/block lists ------------------------- #
class IPRuleInput(BaseModel):
    list_type: str  # allow | block
    value: str
    note: str | None = None


def _validate_ip_value(value: str):
    try:
        if "/" in value:
            ipaddress.ip_network(value, strict=False)
        else:
            ipaddress.ip_address(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Enter a valid IP address or CIDR range")


@router.get("/ip-rules")
async def list_ip_rules(ws=Depends(get_current_workspace)):
    rows = await db.ip_rules.find({"workspace_id": ws["id"]}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return {"items": rows}


@router.post("/ip-rules")
async def create_ip_rule(payload: IPRuleInput, ws=Depends(get_current_workspace)):
    if payload.list_type not in ("allow", "block"):
        raise HTTPException(status_code=400, detail="list_type must be allow or block")
    _validate_ip_value(payload.value.strip())
    doc = {"id": str(uuid.uuid4()), "workspace_id": ws["id"], "list_type": payload.list_type,
           "value": payload.value.strip(), "note": payload.note, "created_at": now_iso()}
    await db.ip_rules.insert_one({**doc})
    invalidate_ip(ws["id"])
    return doc


@router.delete("/ip-rules/{rule_id}")
async def delete_ip_rule(rule_id: str, ws=Depends(get_current_workspace)):
    res = await db.ip_rules.delete_one({"id": rule_id, "workspace_id": ws["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    invalidate_ip(ws["id"])
    return {"ok": True}


@router.get("/feeds")
async def feeds(ws=Depends(get_current_workspace)):
    return feeds_state()


@router.get("/presets")
async def list_presets(ws=Depends(get_current_workspace)):
    return {"presets": {k: {**PROTECTION_PRESETS[k], **PRESET_META[k]} for k in PROTECTION_PRESETS}}


# --------------------------- simulator ------------------------------------ #
class SimulateInput(BaseModel):
    ip: str = "8.8.8.8"
    country: str = "US"
    ua: str = "Mozilla/5.0 (Windows NT 10.0; Win64) Chrome/120"
    referrer: str = "Direct"


@router.post("/simulate")
async def simulate(payload: SimulateInput, ws=Depends(get_current_workspace)):
    res = await evaluate_request(ws["id"], None, payload.ip, payload.ua, payload.referrer, payload.country)
    return res
