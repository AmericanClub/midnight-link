from fastapi import APIRouter

router = APIRouter(prefix="/api/billing", tags=["billing"])

# Plan catalog. Billing/QRIS flow is prepared via PaymentProvider abstraction;
# no real gateway is wired yet.
PLANS = [
    {"id": "free", "name": "Free", "price": 0, "currency": "IDR", "cycle": "month",
     "limits": {"smart_links": 10, "dynamic_qr": 3, "monthly_events": 1000, "retention_days": 7,
                "members": 1, "custom_domains": 0}, "branding": True},
    {"id": "starter", "name": "Starter", "price": 149000, "currency": "IDR", "cycle": "month",
     "limits": {"smart_links": 100, "dynamic_qr": 25, "monthly_events": 50000, "retention_days": 90,
                "members": 2, "custom_domains": 1}, "branding": True},
    {"id": "pro", "name": "Pro", "price": 499000, "currency": "IDR", "cycle": "month",
     "limits": {"smart_links": 1000, "dynamic_qr": 250, "monthly_events": 500000, "retention_days": 365,
                "members": 10, "custom_domains": 5}, "branding": False},
    {"id": "business", "name": "Business", "price": 1499000, "currency": "IDR", "cycle": "month",
     "limits": {"smart_links": 10000, "dynamic_qr": 2500, "monthly_events": 5000000, "retention_days": 730,
                "members": 50, "custom_domains": 25}, "branding": False},
    {"id": "enterprise", "name": "Enterprise", "price": None, "currency": "IDR", "cycle": "custom",
     "limits": {"smart_links": None, "dynamic_qr": None, "monthly_events": None, "retention_days": None,
                "members": None, "custom_domains": None}, "branding": False},
]


@router.get("/plans")
async def get_plans():
    return {"plans": PLANS}
