import logging

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import db, ensure_indexes
from app.security import hash_password, verify_password
from app.utils import now_iso
from app.providers import wire_event_bus
from app.domains import auth, workspace, links, analytics, redirect, billing, qr, security, apikeys, blocker, admin, webhooks, custom_domains, team, notifications
from app.domains.workspace import create_default_workspace
from app.intel import refresh_tor
from app.geoip import warm as warm_geoip
from app.domains.webhooks import wire_webhooks
from app.domains.notifications import wire_notifications

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("midgate")

app = FastAPI(title="MidGate Core API", version="0.1.0")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "core-api"}


@app.get("/api/ready")
async def ready():
    try:
        await db.command("ping")
        return {"status": "ready", "database": "ok"}
    except Exception as e:
        return {"status": "not_ready", "database": str(e)}


app.include_router(auth.router)
app.include_router(workspace.router)
app.include_router(links.router)
app.include_router(qr.router)
app.include_router(security.router)
app.include_router(apikeys.router)
app.include_router(blocker.router)
app.include_router(admin.router)
app.include_router(analytics.router)
app.include_router(redirect.router)
app.include_router(billing.router)
app.include_router(webhooks.router)
app.include_router(custom_domains.router)
app.include_router(team.router)
app.include_router(notifications.router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=(["*"] if settings.CORS_ORIGINS == "*" else settings.CORS_ORIGINS.split(",")),
    allow_methods=["*"],
    allow_headers=["*"],
)


async def seed_admin():
    existing = await db.users.find_one({"email": settings.ADMIN_EMAIL})
    if existing is None:
        res = await db.users.insert_one({
            "name": "MidGate Admin", "email": settings.ADMIN_EMAIL,
            "password_hash": hash_password(settings.ADMIN_PASSWORD),
            "role": "admin", "created_at": now_iso(),
        })
        await create_default_workspace(str(res.inserted_id), "MidGate Admin")
        logger.info("Seeded admin user %s", settings.ADMIN_EMAIL)
    elif not verify_password(settings.ADMIN_PASSWORD, existing["password_hash"]):
        await db.users.update_one({"email": settings.ADMIN_EMAIL},
                                  {"$set": {"password_hash": hash_password(settings.ADMIN_PASSWORD)}})


@app.on_event("startup")
async def on_startup():
    import asyncio
    await ensure_indexes()
    wire_event_bus()
    wire_webhooks()
    wire_notifications()
    await seed_admin()
    asyncio.create_task(refresh_tor())
    asyncio.create_task(asyncio.to_thread(warm_geoip))
    logger.info("MidGate Core API started")
