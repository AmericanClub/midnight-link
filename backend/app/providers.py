"""Provider abstractions for MidGate.

Business logic depends only on these interfaces, never on concrete SDKs.
Initial implementations: InMemoryEventBus, MongoAnalyticsStore, ConsoleEmailProvider,
MockQRISPaymentProvider, BasicIPIntelProvider.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Callable, Awaitable

from .db import db

logger = logging.getLogger("midgate.providers")


# --------------------------------------------------------------------------- #
# EventBus
# --------------------------------------------------------------------------- #
class EventBus(ABC):
    @abstractmethod
    def subscribe(self, topic: str, handler: Callable[[dict], Awaitable[None]]) -> None: ...

    @abstractmethod
    async def publish(self, topic: str, event: dict) -> None: ...


class InMemoryEventBus(EventBus):
    """First implementation. Swappable for Redis Streams / Kafka later."""

    def __init__(self):
        self._subs: dict[str, list] = {}

    def subscribe(self, topic, handler):
        self._subs.setdefault(topic, []).append(handler)

    async def publish(self, topic, event):
        for handler in self._subs.get(topic, []):
            asyncio.create_task(self._safe(handler, event))

    async def _safe(self, handler, event):
        try:
            await handler(event)
        except Exception as e:  # analytics must never break the caller
            logger.error("event handler failed: %s", e)


# --------------------------------------------------------------------------- #
# AnalyticsStore
# --------------------------------------------------------------------------- #
class AnalyticsStore(ABC):
    @abstractmethod
    async def record(self, event: dict) -> None: ...

    @abstractmethod
    async def count(self, flt: dict) -> int: ...

    @abstractmethod
    async def unique_visitors(self, flt: dict) -> int: ...

    @abstractmethod
    async def timeseries(self, flt: dict, days: int) -> list: ...

    @abstractmethod
    async def breakdown(self, flt: dict, field: str, limit: int) -> list: ...

    @abstractmethod
    async def recent(self, flt: dict, limit: int) -> list: ...


class MongoAnalyticsStore(AnalyticsStore):
    """PostgreSQL is the target in the spec; here MongoDB backs the same interface.
    A ClickHouse adapter can be dropped in without touching business logic."""

    async def record(self, event):
        await db.analytics_events.insert_one({**event})

    async def count(self, flt):
        return await db.analytics_events.count_documents(flt)

    async def unique_visitors(self, flt):
        res = await db.analytics_events.distinct("visitor_id", flt)
        return len(res)

    async def timeseries(self, flt, days=30):
        pipeline = [
            {"$match": flt},
            {"$group": {"_id": {"$substr": ["$occurred_at", 0, 10]}, "clicks": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]
        rows = await db.analytics_events.aggregate(pipeline).to_list(1000)
        return [{"date": r["_id"], "clicks": r["clicks"]} for r in rows]

    async def breakdown(self, flt, field, limit=10):
        pipeline = [
            {"$match": flt},
            {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": limit},
        ]
        rows = await db.analytics_events.aggregate(pipeline).to_list(limit)
        return [{"name": r["_id"] or "Unknown", "count": r["count"]} for r in rows]

    async def recent(self, flt, limit=20):
        cur = db.analytics_events.find(flt, {"_id": 0}).sort("occurred_at", -1).limit(limit)
        return await cur.to_list(limit)


# --------------------------------------------------------------------------- #
# EmailProvider
# --------------------------------------------------------------------------- #
class EmailProvider(ABC):
    @abstractmethod
    async def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleEmailProvider(EmailProvider):
    """Local dev provider (Mailpit/Resend swap in later)."""

    async def send(self, to, subject, body):
        logger.info("EMAIL -> %s | %s\n%s", to, subject, body)


# --------------------------------------------------------------------------- #
# IPIntelProvider
# --------------------------------------------------------------------------- #
class IPIntelProvider(ABC):
    @abstractmethod
    async def lookup(self, ip: str) -> dict: ...


class BasicIPIntelProvider(IPIntelProvider):
    async def lookup(self, ip):
        return {"is_proxy": False, "is_vpn": False, "is_tor": False, "is_hosting": False, "asn": None}


# --------------------------------------------------------------------------- #
# PaymentProvider (prepared, not wired to a real gateway yet)
# --------------------------------------------------------------------------- #
class PaymentProvider(ABC):
    @abstractmethod
    async def create_charge(self, invoice: dict) -> dict: ...

    @abstractmethod
    def verify_webhook(self, payload: dict, signature: str) -> bool: ...


class MockQRISPaymentProvider(PaymentProvider):
    """Placeholder. A real QRIS provider is selected during the billing phase."""

    name = "mock-qris"

    async def create_charge(self, invoice):
        return {
            "provider": self.name,
            "qris_string": "00020101...MOCK-QRIS-PAYLOAD",
            "amount": invoice.get("amount"),
            "currency": invoice.get("currency", "IDR"),
            "status": "pending",
        }

    def verify_webhook(self, payload, signature):
        return False  # never trust unsigned mock webhooks


# --------------------------------------------------------------------------- #
# Singletons + wiring
# --------------------------------------------------------------------------- #
event_bus: EventBus = InMemoryEventBus()
analytics_store: AnalyticsStore = MongoAnalyticsStore()
email_provider: EmailProvider = ConsoleEmailProvider()
ip_intel: IPIntelProvider = BasicIPIntelProvider()
payment_provider: PaymentProvider = MockQRISPaymentProvider()


def wire_event_bus():
    async def on_click(event):
        await analytics_store.record(event)

    event_bus.subscribe("link.clicked", on_click)
