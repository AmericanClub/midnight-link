"""MidGate Protect — risk scoring + configurable security rules."""
import hashlib
import hmac
import time
import uuid

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ..db import db
from ..config import settings
from ..utils import now_iso
from .workspace import get_current_workspace

router = APIRouter(prefix="/api/security", tags=["security"])

ACTIONS = {"allow", "challenge", "block", "log_only"}
OPERATORS = {"equals", "not_equals", "in", "not_in", "contains", "gt", "lt"}
FIELDS = {"country", "device", "browser", "os", "is_bot", "risk_score", "referrer"}

# default risk thresholds (configurable per spec, defaults here)
THRESHOLDS = [(30, "allow"), (60, "challenge"), (80, "block"), (101, "block")]


# --------------------------- rules cache ---------------------------------- #
_RULES_CACHE: dict[str, tuple[float, list]] = {}
_RULES_TTL = 15.0


def invalidate_rules(workspace_id: str):
    _RULES_CACHE.pop(workspace_id, None)


async def get_rules(workspace_id: str) -> list:
    entry = _RULES_CACHE.get(workspace_id)
    if entry and entry[0] > time.time():
        return entry[1]
    rules = await db.security_rules.find(
        {"workspace_id": workspace_id, "enabled": True}, {"_id": 0}
    ).sort("priority", 1).to_list(200)
    _RULES_CACHE[workspace_id] = (time.time() + _RULES_TTL, rules)
    return rules


# --------------------------- risk scoring --------------------------------- #
def compute_risk(signals: dict) -> tuple[int, list]:
    score = 0
    reasons = []
    if signals.get("is_bot"):
        score += 55
        reasons.append("Automated / bot user-agent detected")
    if not signals.get("user_agent"):
        score += 30
        reasons.append("Missing user-agent header")
    if signals.get("browser") in ("Other", "Unknown"):
        score += 12
        reasons.append("Unrecognized browser")
    if signals.get("os") == "Unknown":
        score += 8
        reasons.append("Unrecognized operating system")
    if signals.get("country") == "Unknown":
        score += 5
        reasons.append("Country could not be resolved")
    return min(score, 100), reasons


def _match_condition(cond: dict, signals: dict) -> bool:
    field = cond.get("field")
    op = cond.get("operator")
    value = cond.get("value")
    actual = signals.get(field)
    try:
        if op == "equals":
            return str(actual).lower() == str(value).lower()
        if op == "not_equals":
            return str(actual).lower() != str(value).lower()
        if op == "in":
            vals = value if isinstance(value, list) else str(value).split(",")
            return str(actual).lower() in [str(v).strip().lower() for v in vals]
        if op == "not_in":
            vals = value if isinstance(value, list) else str(value).split(",")
            return str(actual).lower() not in [str(v).strip().lower() for v in vals]
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
    signals = {**signals, "risk_score": score}
    matched_rule = None
    for rule in rules:
        conds = rule.get("conditions", [])
        if conds and all(_match_condition(c, signals) for c in conds):
            matched_rule = rule
            break
    if matched_rule:
        decision = matched_rule["action"]
        reasons = [f"Matched rule: {matched_rule['name']}"] + reasons
    else:
        decision = default_decision(score)
    return {
        "risk_score": score,
        "decision": decision,
        "reasons": reasons,
        "matched_rule_id": matched_rule["id"] if matched_rule else None,
        "policy_version": 1,
    }


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
    return {"items": rows, "thresholds": THRESHOLDS}


@router.post("/rules")
async def create_rule(payload: RuleInput, ws=Depends(get_current_workspace)):
    _validate_rule(payload)
    rule = {
        "id": str(uuid.uuid4()),
        "workspace_id": ws["id"],
        "name": payload.name,
        "action": payload.action,
        "priority": payload.priority,
        "enabled": payload.enabled,
        "description": payload.description,
        "conditions": [c.model_dump() for c in payload.conditions],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.security_rules.insert_one({**rule})
    invalidate_rules(ws["id"])
    return rule


@router.patch("/rules/{rule_id}")
async def update_rule(rule_id: str, payload: RuleInput, ws=Depends(get_current_workspace)):
    _validate_rule(payload)
    existing = await db.security_rules.find_one({"id": rule_id, "workspace_id": ws["id"]})
    if not existing:
        raise HTTPException(status_code=404, detail="Not found")
    updates = {
        "name": payload.name, "action": payload.action, "priority": payload.priority,
        "enabled": payload.enabled, "description": payload.description,
        "conditions": [c.model_dump() for c in payload.conditions], "updated_at": now_iso(),
    }
    await db.security_rules.update_one({"id": rule_id}, {"$set": updates})
    invalidate_rules(ws["id"])
    return await db.security_rules.find_one({"id": rule_id}, {"_id": 0})


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, ws=Depends(get_current_workspace)):
    res = await db.security_rules.delete_one({"id": rule_id, "workspace_id": ws["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    invalidate_rules(ws["id"])
    return {"ok": True}


class SimulateInput(BaseModel):
    country: str = "Unknown"
    device: str = "Desktop"
    browser: str = "Chrome"
    os: str = "Windows"
    is_bot: bool = False
    referrer: str = "Direct"


@router.post("/simulate")
async def simulate(payload: SimulateInput, ws=Depends(get_current_workspace)):
    rules = await db.security_rules.find(
        {"workspace_id": ws["id"], "enabled": True}, {"_id": 0}
    ).sort("priority", 1).to_list(200)
    signals = {**payload.model_dump(), "user_agent": "simulator"}
    return evaluate(signals, rules)
