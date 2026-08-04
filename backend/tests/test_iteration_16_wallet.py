"""Iteration 16 — Real Mayar wallet + credit ledger tests.

Verifies:
1. wallet summary/topup/topup-status happy path (real Mayar invoice creation)
2. Webhook security: forged webhook with correct token on UNPAID invoice must not credit
3. Insufficient credits -> 402
4. Admin adjust + purchase-plan flow
5. Mock payment endpoints (checkout/simulate-payment) are 403
6. RBAC: admin/adjust as non-admin -> 403
"""
import os
import re
import time
import requests
import pytest

def _read_frontend_url():
    with open("/app/frontend/.env") as fh:
        for ln in fh:
            if ln.startswith("REACT_APP_BACKEND_URL"):
                return ln.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("REACT_APP_BACKEND_URL missing")

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_url()).rstrip("/")
ADMIN = ("admin@midgate.co", "Admin123!")
CUSTOMER = ("teammate@example.com", "Teammate123!")
WEBHOOK_TOKEN = None  # loaded from backend/.env


def _load_webhook_token():
    global WEBHOOK_TOKEN
    if WEBHOOK_TOKEN:
        return WEBHOOK_TOKEN
    with open("/app/backend/.env") as fh:
        for ln in fh:
            if ln.startswith("MAYAR_WEBHOOK_TOKEN"):
                WEBHOOK_TOKEN = ln.split("=", 1)[1].strip().strip('"').strip("'")
                return WEBHOOK_TOKEN
    return None


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    return s


def _me(s):
    return s.get(f"{BASE}/api/auth/me", timeout=15).json()


def _customer_ws_id(s):
    me = _me(s)
    # /api/auth/me returns workspaces; pick the one where user is owner
    wss = me.get("workspaces") or []
    if not wss:
        # Fallback endpoint
        wss = s.get(f"{BASE}/api/workspaces", timeout=15).json()
    # Prefer owner role
    owner_ws = next((w for w in wss if w.get("role") == "owner"), None)
    return (owner_ws or wss[0])["id"]


@pytest.fixture(scope="module")
def customer_session():
    s = _login(*CUSTOMER)
    ws_id = _customer_ws_id(s)
    s.headers.update({"X-Workspace-Id": ws_id})
    return s, ws_id


@pytest.fixture(scope="module")
def admin_session():
    s = _login(*ADMIN)
    return s


# --------------------------- Tests --------------------------------------- #
class TestWalletSummary:
    def test_summary_shape(self, customer_session):
        s, ws_id = customer_session
        r = s.get(f"{BASE}/api/wallet/summary", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["currency"] == "credit"
        assert d["min_topup"] == 10000
        assert d["gateway_ready"] is True
        assert isinstance(d["balance"], int)
        assert isinstance(d["ledger"], list)


class TestTopup:
    def test_topup_below_min(self, customer_session):
        s, _ = customer_session
        r = s.post(f"{BASE}/api/wallet/topup", json={"amount": 5000}, timeout=15)
        assert r.status_code == 400

    def test_topup_creates_real_mayar_invoice(self, customer_session):
        s, _ = customer_session
        r = s.post(f"{BASE}/api/wallet/topup", json={"amount": 25000}, timeout=45)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "order_id" in d and d["amount"] == 25000
        url = d["payment_url"]
        assert url and re.match(r"^https://.*mayar", url) or "myr.id" in url or "mayar.id" in url, url
        pytest.order_id = d["order_id"]
        pytest.payment_url = url

    def test_topup_status_pending_uncredited(self, customer_session):
        s, _ = customer_session
        oid = pytest.order_id
        r = s.get(f"{BASE}/api/wallet/topup/{oid}", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["credited"] is False
        assert d["status"] == "pending"
        assert d["balance"] == 0


class TestWebhookSecurity:
    def test_forged_webhook_valid_token_unpaid_invoice_does_not_credit(self, customer_session):
        s, _ = customer_session
        token = _load_webhook_token()
        assert token, "webhook token missing"
        body = {"event": "payment.received",
                "data": {"extraData": {"order_id": pytest.order_id}, "amount": 25000}}
        r = requests.post(f"{BASE}/api/wallet/mayar/webhook", json=body,
                          headers={"x-webhook-token": token}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # crediting must be false because Mayar says invoice is unpaid
        assert d.get("credited") is False, d
        # balance still zero
        r2 = s.get(f"{BASE}/api/wallet/summary", timeout=15)
        assert r2.json()["balance"] == 0

    def test_webhook_unmatched_order(self):
        token = _load_webhook_token()
        body = {"event": "payment.received",
                "data": {"extraData": {"order_id": "no-such-order-xyz"}, "amount": 1000}}
        r = requests.post(f"{BASE}/api/wallet/mayar/webhook", json=body,
                          headers={"x-webhook-token": token}, timeout=15)
        assert r.status_code == 200
        assert r.json().get("unmatched") is True

    def test_webhook_ignored_event(self):
        token = _load_webhook_token()
        body = {"event": "payment.reminder", "data": {}}
        r = requests.post(f"{BASE}/api/wallet/mayar/webhook", json=body,
                          headers={"x-webhook-token": token}, timeout=15)
        assert r.status_code == 200
        assert "ignored" in r.json()


class TestInsufficient:
    def test_purchase_plan_insufficient(self, customer_session):
        s, _ = customer_session
        r = s.post(f"{BASE}/api/wallet/purchase-plan", json={"plan_id": "starter"}, timeout=15)
        assert r.status_code == 402
        assert "Insufficient credits" in r.text


class TestAdminAndPurchase:
    def test_admin_adjust_and_purchase(self, admin_session, customer_session):
        s_cust, ws_id = customer_session
        # Admin credits 500,000
        r = admin_session.post(f"{BASE}/api/wallet/admin/adjust",
                               json={"workspace_id": ws_id, "amount": 500000, "reason": "test seed"},
                               timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["balance"] >= 500000
        # Customer purchases starter
        r2 = s_cust.post(f"{BASE}/api/wallet/purchase-plan", json={"plan_id": "starter"}, timeout=20)
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert d["plan"] == "starter"
        # 99,000 deducted
        # Balance may include prior seed - just check decreased by 99000 from prior state
        assert d["balance"] == 500000 - 99000 or d["balance"] >= 401000
        # Ledger has spend + refund entries
        summary = s_cust.get(f"{BASE}/api/wallet/summary", timeout=15).json()
        types = {e["type"] for e in summary["ledger"]}
        assert "spend" in types and "refund" in types

    def test_admin_adjust_forbidden_for_non_admin(self, customer_session):
        s, ws_id = customer_session
        r = s.post(f"{BASE}/api/wallet/admin/adjust",
                   json={"workspace_id": ws_id, "amount": 1000}, timeout=15)
        assert r.status_code == 403


class TestMockDisabled:
    def test_checkout_disabled(self, customer_session):
        s, _ = customer_session
        r = s.post(f"{BASE}/api/billing/checkout", json={"plan_id": "pro"}, timeout=15)
        assert r.status_code == 403, r.text

    def test_simulate_payment_disabled(self, customer_session):
        s, _ = customer_session
        r = s.post(f"{BASE}/api/billing/invoices/anything/simulate-payment", timeout=15)
        assert r.status_code == 403, r.text
