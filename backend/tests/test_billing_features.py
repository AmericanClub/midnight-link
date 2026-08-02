"""Iteration 3 billing tests: Plan Limit Enforcement, Invoice Receipts, Billing Roles."""
import os
import uuid
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

BASE_URL = ""
try:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
except Exception:
    pass
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "midgate_db")


def _rand_email(p="u"):
    return f"TEST_{p}_{uuid.uuid4().hex[:8]}@midgate.io"


def _register():
    s = requests.Session()
    email = _rand_email("bill")
    r = s.post(f"{API}/auth/register", json={"name": "Bill U", "email": email, "password": "Passw0rd!"})
    assert r.status_code == 200, r.text
    data = r.json()
    s.workspace_id = data["current_workspace"]["id"]
    s.user_id = data["user"]["id"]
    s.headers.update({"X-Workspace-Id": s.workspace_id})
    return s


@pytest.fixture
def sess():
    return _register()


@pytest.fixture
def sess_other():
    return _register()


# -------------------- Plan Limit Enforcement -------------------- #
class TestQuota:
    def test_qr_limit_on_free_plan(self, sess):
        # Free plan: dynamic_qr = 3
        for i in range(3):
            r = sess.post(f"{API}/qr", json={"name": f"Q{i}", "destination_url": "https://example.com"})
            assert r.status_code == 200, f"QR {i} creation failed: {r.text}"
        # 4th QR must be blocked
        r4 = sess.post(f"{API}/qr", json={"name": "Q4", "destination_url": "https://example.com"})
        assert r4.status_code == 403, f"expected 403, got {r4.status_code}: {r4.text}"
        detail = (r4.json().get("detail") or "").lower()
        assert "limit" in detail
        assert "upgrade" in detail

    def test_smart_link_limit_on_free_plan(self, sess):
        # Free plan: smart_links = 10
        for i in range(10):
            r = sess.post(f"{API}/links", json={"name": f"L{i}", "destination_url": "https://example.com"})
            assert r.status_code == 200, f"link {i} failed: {r.text}"
        r11 = sess.post(f"{API}/links", json={"name": "L11", "destination_url": "https://example.com"})
        assert r11.status_code == 403, f"expected 403, got {r11.status_code}: {r11.text}"
        detail = (r11.json().get("detail") or "").lower()
        assert "limit" in detail and "upgrade" in detail

    def test_upgrade_removes_qr_limit(self, sess):
        # fill 3 QRs
        for i in range(3):
            r = sess.post(f"{API}/qr", json={"name": f"Q{i}", "destination_url": "https://example.com"})
            assert r.status_code == 200
        # 4th blocked on free
        r4 = sess.post(f"{API}/qr", json={"name": "Q4", "destination_url": "https://example.com"})
        assert r4.status_code == 403

        # Upgrade to Pro via checkout + simulate-payment
        co = sess.post(f"{API}/billing/checkout", json={"plan_id": "pro"})
        assert co.status_code == 200, co.text
        inv_id = co.json()["id"]
        sp = sess.post(f"{API}/billing/invoices/{inv_id}/simulate-payment")
        assert sp.status_code == 200, sp.text
        assert sp.json().get("status") == "paid"

        # Now 4th QR succeeds (Pro allows 250)
        r5 = sess.post(f"{API}/qr", json={"name": "Q5", "destination_url": "https://example.com"})
        assert r5.status_code == 200, f"post-upgrade QR failed: {r5.text}"


# -------------------- Invoice Receipts -------------------- #
class TestReceipts:
    def test_receipt_pdf_after_payment(self, sess):
        co = sess.post(f"{API}/billing/checkout", json={"plan_id": "starter"})
        assert co.status_code == 200
        inv_id = co.json()["id"]

        # Before payment: 404
        r_pre = sess.get(f"{API}/billing/invoices/{inv_id}/receipt.pdf")
        assert r_pre.status_code == 404

        sp = sess.post(f"{API}/billing/invoices/{inv_id}/simulate-payment")
        assert sp.status_code == 200

        r = sess.get(f"{API}/billing/invoices/{inv_id}/receipt.pdf")
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 500

    def test_receipt_unknown_invoice_404(self, sess):
        r = sess.get(f"{API}/billing/invoices/nonexistent-id/receipt.pdf")
        assert r.status_code == 404


# -------------------- Billing Roles -------------------- #
class TestBillingRoles:
    def test_plans_is_public(self):
        r = requests.get(f"{API}/billing/plans")
        assert r.status_code == 200
        assert "plans" in r.json()

    def test_owner_gets_role_in_subscription(self, sess):
        r = sess.get(f"{API}/billing/subscription")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("role") in ("owner", "admin", "billing_manager")

    def test_analyst_forbidden_on_billing(self, sess, sess_other):
        # Make sess_other an 'analyst' in sess's workspace via DB insert
        ws_id = sess.workspace_id
        analyst_uid = sess_other.user_id

        async def _add_member():
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            await db.workspace_members.insert_one({
                "id": str(uuid.uuid4()),
                "workspace_id": ws_id,
                "user_id": analyst_uid,
                "role": "analyst",
            })
            client.close()

        asyncio.get_event_loop().run_until_complete(_add_member())

        # Analyst calls billing endpoints with sess's ws id -> 403
        sess_other.headers.update({"X-Workspace-Id": ws_id})
        for path in ("/billing/subscription", "/billing/usage", "/billing/invoices"):
            r = sess_other.get(f"{API}{path}")
            assert r.status_code == 403, f"{path} expected 403 for analyst, got {r.status_code}: {r.text}"

    def test_unauthenticated_billing_blocked(self):
        r = requests.get(f"{API}/billing/subscription")
        assert r.status_code in (401, 403)
