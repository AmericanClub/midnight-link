"""Iteration 17 — Partner Payment Gateway backend tests.

Covers admin partner CRUD, partner-facing charges API (auth, validation,
idempotency, real Mayar invoice creation), RBAC, and Mayar webhook
re-verification safety.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://protect-links.preview.emergentagent.com"

ADMIN_EMAIL = "admin@midgate.co"
ADMIN_PASS = "Admin123!"
TEAM_EMAIL = "teammate@example.com"
TEAM_PASS = "Teammate123!"


# ------------------------ session fixtures ------------------------------- #
def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def teammate():
    return _login(TEAM_EMAIL, TEAM_PASS)


@pytest.fixture(scope="module")
def partner(admin):
    """Create a fresh partner for the whole module; delete at teardown."""
    r = admin.post(f"{BASE_URL}/api/admin/partners", json={
        "name": f"qa-partner-{uuid.uuid4().hex[:6]}",
        "webhook_url": "https://httpbin.org/post",
        "source_tag": "qa",
    }, timeout=30)
    assert r.status_code == 200, f"create partner failed: {r.status_code} {r.text}"
    data = r.json()
    yield data
    try:
        admin.delete(f"{BASE_URL}/api/admin/partners/{data['id']}", timeout=15)
    except Exception:
        pass


# ------------------------ admin partner CRUD ----------------------------- #
class TestPartnerCRUD:
    def test_create_returns_key_and_secret_once(self, partner):
        assert partner["api_key"].startswith("mgpay_live_"), partner
        assert partner["webhook_secret"].startswith("mgwhsec_"), partner
        assert partner["key_prefix"] == partner["api_key"][:16]
        assert partner["key_last4"] == partner["api_key"][-4:]
        assert partner["active"] is True

    def test_list_includes_partner(self, admin, partner):
        r = admin.get(f"{BASE_URL}/api/admin/partners", timeout=15)
        assert r.status_code == 200
        items = r.json()["items"]
        assert any(p["id"] == partner["id"] for p in items)
        # api_key must NOT be in list responses
        p = next(p for p in items if p["id"] == partner["id"])
        assert "api_key" not in p

    def test_detail_returns_partner_and_stats(self, admin, partner):
        # Redesign (iter 18): detail returns {partner, stats} only; charges/deliveries
        # moved to dedicated paginated sub-endpoints.
        r = admin.get(f"{BASE_URL}/api/admin/partners/{partner['id']}", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["partner"]["id"] == partner["id"]
        assert "stats" in d and "charges" in d["stats"]
        assert "charges" not in d and "deliveries" not in d

    def test_patch_webhook_url(self, admin, partner):
        r = admin.patch(f"{BASE_URL}/api/admin/partners/{partner['id']}",
                        json={"webhook_url": "https://httpbin.org/anything"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["webhook_url"] == "https://httpbin.org/anything"

    def test_rotate_key_returns_new_key(self, admin, partner):
        r = admin.post(f"{BASE_URL}/api/admin/partners/{partner['id']}/rotate-key", timeout=15)
        assert r.status_code == 200
        new_key = r.json()["api_key"]
        assert new_key.startswith("mgpay_live_")
        assert new_key != partner["api_key"]
        # Update fixture in-place so downstream tests use the new key
        partner["api_key"] = new_key

    def test_rotate_secret_returns_new_secret(self, admin, partner):
        r = admin.post(f"{BASE_URL}/api/admin/partners/{partner['id']}/rotate-secret", timeout=15)
        assert r.status_code == 200
        s = r.json()["webhook_secret"]
        assert s.startswith("mgwhsec_") and s != partner["webhook_secret"]

    def test_deactivate_then_reactivate(self, admin, partner):
        r1 = admin.patch(f"{BASE_URL}/api/admin/partners/{partner['id']}",
                         json={"active": False}, timeout=15)
        assert r1.status_code == 200 and r1.json()["active"] is False
        # while deactivated, key should be rejected
        r_pay = requests.post(f"{BASE_URL}/api/pay/charges",
                              headers={"Authorization": f"Bearer {partner['api_key']}"},
                              json={"amount": 50000, "reference_id": "qa-inactive"}, timeout=15)
        assert r_pay.status_code == 401
        r2 = admin.patch(f"{BASE_URL}/api/admin/partners/{partner['id']}",
                         json={"active": True}, timeout=15)
        assert r2.status_code == 200 and r2.json()["active"] is True


# ------------------------ partner-facing API ----------------------------- #
class TestChargesAPI:
    def _hdr(self, partner):
        return {"Authorization": f"Bearer {partner['api_key']}"}

    def test_create_charge_returns_real_mayar_link(self, partner):
        ref = f"qa-001-{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{BASE_URL}/api/pay/charges", headers=self._hdr(partner),
                          json={"amount": 50000, "reference_id": ref,
                                "customer": {"name": "Alice QA", "email": "a@b.com", "mobile": "081200000000"}},
                          timeout=45)
        assert r.status_code == 200, r.text
        c = r.json()
        assert c["status"] == "pending"
        assert c["checkout_url"] and "myr.id" in c["checkout_url"]
        assert c["expires_at"]
        # stash for subsequent tests
        partner.setdefault("_charges", {})[ref] = c

    def test_get_charge_returns_pending(self, partner):
        ref, c = next(iter(partner["_charges"].items()))
        r = requests.get(f"{BASE_URL}/api/pay/charges/{c['id']}", headers=self._hdr(partner), timeout=30)
        assert r.status_code == 200 and r.json()["status"] == "pending"

    def test_idempotent_same_reference(self, partner):
        ref, c = next(iter(partner["_charges"].items()))
        r = requests.post(f"{BASE_URL}/api/pay/charges", headers=self._hdr(partner),
                          json={"amount": 50000, "reference_id": ref}, timeout=45)
        assert r.status_code == 200
        assert r.json()["id"] == c["id"], "idempotency violated"

    def test_amount_below_min(self, partner):
        r = requests.post(f"{BASE_URL}/api/pay/charges", headers=self._hdr(partner),
                          json={"amount": 5000, "reference_id": f"qa-lo-{uuid.uuid4().hex[:6]}"}, timeout=15)
        assert r.status_code == 400, r.text

    def test_amount_above_max(self, partner):
        r = requests.post(f"{BASE_URL}/api/pay/charges", headers=self._hdr(partner),
                          json={"amount": 20_000_000, "reference_id": f"qa-hi-{uuid.uuid4().hex[:6]}"}, timeout=15)
        assert r.status_code == 400, r.text

    def test_missing_reference_id(self, partner):
        r = requests.post(f"{BASE_URL}/api/pay/charges", headers=self._hdr(partner),
                          json={"amount": 50000}, timeout=15)
        assert r.status_code in (400, 422)

    def test_blank_reference_id(self, partner):
        r = requests.post(f"{BASE_URL}/api/pay/charges", headers=self._hdr(partner),
                          json={"amount": 50000, "reference_id": ""}, timeout=15)
        assert r.status_code in (400, 422)


# ------------------------ auth on partner API ---------------------------- #
class TestPartnerAuth:
    def test_no_auth_header(self):
        r = requests.post(f"{BASE_URL}/api/pay/charges",
                          json={"amount": 50000, "reference_id": "x"}, timeout=15)
        assert r.status_code == 401

    def test_bad_key(self):
        r = requests.post(f"{BASE_URL}/api/pay/charges",
                          headers={"Authorization": "Bearer mgpay_live_bad"},
                          json={"amount": 50000, "reference_id": "x"}, timeout=15)
        assert r.status_code == 401


# ------------------------ RBAC ------------------------------------------- #
class TestRBAC:
    def test_teammate_cannot_list_admin_partners(self, teammate):
        r = teammate.get(f"{BASE_URL}/api/admin/partners", timeout=15)
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"


# ------------------------ webhook re-verify safety ----------------------- #
class TestWebhookSafety:
    def test_public_mayar_webhook_does_not_mark_paid(self, partner):
        ref, c = next(iter(partner["_charges"].items()))
        # spoof a payment.received event correlated to this charge
        r = requests.post(f"{BASE_URL}/api/wallet/mayar/webhook",
                          json={"event": "payment.received",
                                "data": {"extraData": {"charge_id": c["id"]}}}, timeout=30)
        # server should respond ok but MUST NOT mark paid (verify_paid says no)
        assert r.status_code in (200, 202), r.text
        # give the async task a beat
        time.sleep(1)
        chk = requests.get(f"{BASE_URL}/api/pay/charges/{c['id']}",
                           headers={"Authorization": f"Bearer {partner['api_key']}"}, timeout=30)
        assert chk.status_code == 200
        assert chk.json()["status"] == "pending", "spoofed webhook incorrectly marked charge paid"


# ------------------------ cleanup ---------------------------------------- #
class TestCleanup:
    def test_delete_partner_cascades(self, admin, partner):
        pid = partner["id"]
        r = admin.delete(f"{BASE_URL}/api/admin/partners/{pid}", timeout=15)
        assert r.status_code == 200
        lst = admin.get(f"{BASE_URL}/api/admin/partners", timeout=15).json()["items"]
        assert not any(p["id"] == pid for p in lst)
        # fixture teardown is safe (delete is idempotent-ish; 404 is fine)
