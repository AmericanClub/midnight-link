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
    await db.wallets.create_index("workspace_id", unique=True)
    await db.wallet_ledger.create_index([("workspace_id", 1), ("created_at", -1)])
    await db.mayar_payments.create_index("id", unique=True)
    await db.mayar_payments.create_index("mayar_invoice_id")
    # High-volume webhook + reconciler lookups (were full collection scans before):
    await db.mayar_payments.create_index("klik_order_id", sparse=True)
    await db.mayar_payments.create_index([("credited", 1), ("created_at", -1)])
    await db.partners.create_index("key_hash", unique=True)
    await db.partner_charges.create_index([("partner_id", 1), ("reference_id", 1)], unique=True)
    await db.partner_charges.create_index("id", unique=True)
    await db.partner_charges.create_index("mayar_invoice_id")
    # KlikQRIS webhook matches partner charges by klik_order_id; reconciler + redelivery
    # sweeps scan by status/created_at and status/notified/paid_at every 60s.
    await db.partner_charges.create_index("klik_order_id", sparse=True)
    await db.partner_charges.create_index([("status", 1), ("created_at", -1)])
    await db.partner_charges.create_index([("status", 1), ("notified", 1), ("paid_at", 1)])
    await db.partner_webhook_deliveries.create_index([("partner_id", 1), ("created_at", -1)])
    await db.partner_webhook_deliveries.create_index("charge_id")
