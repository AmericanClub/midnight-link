import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, Response, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field

from ..db import db
from ..security import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    decode_token, get_current_user, set_auth_cookies, clear_auth_cookies,
)
from ..utils import now_iso, client_ip
from ..providers import email_provider
from .workspace import create_default_workspace, list_user_workspaces
router = APIRouter(prefix="/api/auth", tags=["auth"])

MAX_ATTEMPTS = 5
LOCK_MINUTES = 15


class RegisterInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class ForgotInput(BaseModel):
    email: EmailStr


class ResetInput(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


async def _check_lockout(identifier: str):
    doc = await db.login_attempts.find_one({"identifier": identifier})
    if doc and doc.get("count", 0) >= MAX_ATTEMPTS:
        locked_until = doc.get("locked_until")
        if locked_until and datetime.fromisoformat(locked_until) > datetime.now(timezone.utc):
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")


async def _record_failure(identifier: str):
    locked_until = (datetime.now(timezone.utc) + timedelta(minutes=LOCK_MINUTES)).isoformat()
    await db.login_attempts.update_one(
        {"identifier": identifier},
        {"$inc": {"count": 1}, "$set": {"locked_until": locked_until}},
        upsert=True,
    )


async def _clear_failures(identifier: str):
    await db.login_attempts.delete_one({"identifier": identifier})


def _public_user(user: dict) -> dict:
    return {"id": user["id"], "name": user["name"], "email": user["email"], "role": user.get("role", "user")}


@router.post("/register")
async def register(payload: RegisterInput, response: Response):
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    doc = {
        "name": payload.name.strip(),
        "email": email,
        "password_hash": hash_password(payload.password),
        "role": "user",
        "created_at": now_iso(),
    }
    result = await db.users.insert_one(doc)
    user_id = str(result.inserted_id)
    workspace = await create_default_workspace(user_id, payload.name.strip())
    await email_provider.send(email, "Welcome to MidGate", f"Welcome {payload.name}! Every Click. Protected.")
    set_auth_cookies(response, create_access_token(user_id, email), create_refresh_token(user_id))
    workspaces = await list_user_workspaces(user_id)
    return {"user": {"id": user_id, "name": doc["name"], "email": email, "role": "user"},
            "workspaces": workspaces, "current_workspace": workspaces[0] if workspaces else None}


@router.post("/login")
async def login(payload: LoginInput, request: Request, response: Response):
    email = payload.email.lower().strip()
    identifier = f"{client_ip(request)}:{email}"
    await _check_lockout(identifier)
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        await _record_failure(identifier)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    await _clear_failures(identifier)
    if user.get("suspended"):
        raise HTTPException(status_code=403, detail="Your account has been suspended. Contact support.")
    user_id = str(user["_id"])
    set_auth_cookies(response, create_access_token(user_id, email), create_refresh_token(user_id))
    workspaces = await list_user_workspaces(user_id)
    return {"user": {"id": user_id, "name": user["name"], "email": email, "role": user.get("role", "user")},
            "workspaces": workspaces, "current_workspace": workspaces[0] if workspaces else None}


@router.post("/logout")
async def logout(response: Response, user=Depends(get_current_user)):
    clear_auth_cookies(response)
    return {"ok": True}


@router.get("/me")
async def me(user=Depends(get_current_user)):
    workspaces = await list_user_workspaces(user["id"])
    return {"user": _public_user(user), "workspaces": workspaces,
            "current_workspace": workspaces[0] if workspaces else None}


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user_id = payload["sub"]
    from bson import ObjectId
    from bson.errors import InvalidId
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except InvalidId:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    set_auth_cookies(response, create_access_token(user_id, user["email"]), create_refresh_token(user_id))
    return {"ok": True}


@router.post("/forgot-password")
async def forgot_password(payload: ForgotInput):
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if user:
        token = secrets.token_urlsafe(32)
        await db.password_reset_tokens.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": str(user["_id"]),
            "token": token,
            "used": False,
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        })
        link = f"/reset-password?token={token}"
        await email_provider.send(email, "Reset your MidGate password", f"Reset link: {link}")
    # constant-time-ish neutral response, never reveal existence
    return {"ok": True, "message": "If an account exists, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(payload: ResetInput):
    doc = await db.password_reset_tokens.find_one({"token": payload.token})
    if not doc or doc.get("used"):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    expires = doc["expires_at"]
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    from bson import ObjectId
    from bson.errors import InvalidId
    try:
        await db.users.update_one({"_id": ObjectId(doc["user_id"])},
                                  {"$set": {"password_hash": hash_password(payload.password)}})
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    await db.password_reset_tokens.update_one({"token": payload.token}, {"$set": {"used": True}})
    return {"ok": True, "message": "Password updated successfully"}
