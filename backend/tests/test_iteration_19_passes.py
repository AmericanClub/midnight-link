"""Iteration 19 - Duration Passes system + admin requests_per_credit setting."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://link-midnight-design.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@midgate.co"
ADMIN_PASSWORD = "Admin123!"
MEMBER_EMAIL = "member@midnightlink.link"
MEMBER_PASSWORD = "Member123!"


def _login(email, pwd):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd}, timeout=15)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    return s


def _wh(ws_id):
    return {"X-Workspace-Id": ws_id}


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def member_session():
    return _login(MEMBER_EMAIL, MEMBER_PASSWORD)


@pytest.fixture(scope="module")
def member_ws(member_session):
    r = member_session.get(f"{BASE_URL}/api/auth/me", timeout=15)
    assert r.status_code == 200
    data = r.json()
    ws_id = (data.get("current_workspace") or {}).get("id") \
        or data.get("workspace_id") \
        or (data.get("workspaces") or [{}])[0].get("id")
    assert ws_id, f"no workspace found: {data}"
    return ws_id


# ------- billing/passes catalog -------
class TestPassCatalog:
    def test_passes_list(self):
        r = requests.get(f"{BASE_URL}/api/billing/passes", timeout=15)
        assert r.status_code == 200
        passes = r.json()["passes"]
        assert len(passes) == 5
        assert [p["days"] for p in passes] == [1, 3, 7, 14, 30]
        for p in passes:
            assert "rate_per_request" in p
            assert isinstance(p["options"], list) and len(p["options"]) == 5

    def test_pass_price_30d_100k(self):
        r = requests.get(f"{BASE_URL}/api/billing/passes", timeout=15)
        p30 = next(p for p in r.json()["passes"] if p["days"] == 30)
        opts = {o["requests"]: o["price"] for o in p30["options"]}
        assert opts.get(100000) == 350000, f"expected 350000, got {opts.get(100000)}"

    def test_pass_price_1d_1000(self):
        r = requests.get(f"{BASE_URL}/api/billing/passes", timeout=15)
        p1 = next(p for p in r.json()["passes"] if p["days"] == 1)
        opts = {o["requests"]: o["price"] for o in p1["options"]}
        assert opts.get(1000) == 7500, f"expected 7500, got {opts.get(1000)}"


# ------- wallet entitlement -------
class TestEntitlement:
    def test_entitlement_shape(self, member_session, member_ws):
        r = member_session.get(f"{BASE_URL}/api/wallet/entitlement",
                               headers=_wh(member_ws), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        required = ["active", "expires_at", "requests_included", "requests_used",
                    "requests_remaining", "quota_exhausted", "credit_balance",
                    "requests_per_credit", "overflow_requests",
                    "credit_requests_available", "total_requests_available"]
        for key in required:
            assert key in d, f"missing {key}: {d}"


# ------- admin credit settings -------
class TestAdminCreditSettings:
    def test_put_and_get_requests_per_credit(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/admin/payment-config",
                              json={"requests_per_credit": 500}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["credits"]["requests_per_credit"] == 500

        r = admin_session.get(f"{BASE_URL}/api/admin/payment-config", timeout=15)
        assert r.status_code == 200
        assert r.json()["credits"]["requests_per_credit"] == 500

    def test_reflected_in_wallet_summary(self, member_session, member_ws):
        r = member_session.get(f"{BASE_URL}/api/wallet/summary",
                               headers=_wh(member_ws), timeout=15)
        assert r.status_code == 200
        assert r.json().get("requests_per_credit") == 500

    def test_reset_to_333(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/admin/payment-config",
                              json={"requests_per_credit": 333}, timeout=15)
        assert r.status_code == 200
        assert r.json()["credits"]["requests_per_credit"] == 333


# ------- purchase pass flow -------
class TestPurchasePass:
    def test_insufficient_returns_402(self, member_session, member_ws):
        # Attempt to purchase a very expensive pass to trigger 402 when balance is low
        # (30d/200k = 700k Rp = 700 credits at rpc=1000)
        r = member_session.get(f"{BASE_URL}/api/wallet/summary",
                               headers=_wh(member_ws), timeout=15)
        bal = r.json().get("balance", 0)
        r = member_session.post(f"{BASE_URL}/api/wallet/purchase-pass",
                                headers=_wh(member_ws),
                                json={"days": 30, "requests": 200000}, timeout=15)
        if bal < 700:
            assert r.status_code == 402, f"expected 402, got {r.status_code}: {r.text}"
        else:
            assert r.status_code in (200, 400, 402)

    def test_credit_and_purchase_success(self, admin_session, member_session, member_ws):
        # Admin credits the member workspace with 50 credits
        r = admin_session.post(f"{BASE_URL}/api/wallet/admin/adjust",
                               json={"workspace_id": member_ws, "amount": 50,
                                     "reason": "TEST_iter19_pass_purchase"}, timeout=15)
        assert r.status_code == 200, r.text

        # Purchase 1-day / 1000 pass (7500 Rp = 8 credits @ rpc=1000 ceil)
        r = member_session.post(f"{BASE_URL}/api/wallet/purchase-pass",
                                headers=_wh(member_ws),
                                json={"days": 1, "requests": 1000}, timeout=20)
        assert r.status_code == 200, f"purchase failed: {r.status_code} {r.text}"
        d = r.json()
        assert d.get("ok") is True
        assert "expires_at" in d
        assert "price_credits" in d

        r = member_session.get(f"{BASE_URL}/api/wallet/entitlement",
                               headers=_wh(member_ws), timeout=15)
        assert r.status_code == 200
        e = r.json()
        assert e["active"] is True
        assert e["requests_included"] == 1000
        assert e["requests_used"] == 0
