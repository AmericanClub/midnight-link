from motor.motor_asyncio import AsyncIOMotorClient
from .config import settings

client = AsyncIOMotorClient(settings.MONGO_URL)
db = client[settings.DB_NAME]


async def ensure_indexes():
    await db.users.create_index("email", unique=True)
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.login_attempts.create_index("identifier")
    await db.workspaces.create_index("id", unique=True)
    await db.workspace_members.create_index([("workspace_id", 1), ("user_id", 1)], unique=True)
    await db.links.create_index("alias", unique=True)
    await db.links.create_index([("workspace_id", 1), ("created_at", -1)])
    await db.analytics_events.create_index([("link_id", 1), ("occurred_at", -1)])
    await db.analytics_events.create_index([("workspace_id", 1), ("occurred_at", -1)])
