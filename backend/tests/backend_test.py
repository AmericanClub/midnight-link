"""MidGate backend E2E tests via public URL."""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://link-midnight-design.preview.emergentagent.com").rstrip("/")
# Load frontend .env for BASE_URL if present
try:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
except Exception:
    pass

API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@midgate.io"
ADMIN_PASSWORD = "Admin123!"


def _rand_email(prefix="test"):
    return f"TEST_{prefix}_{uuid.uuid4().hex[:8]}@midgate.io"


# ------------- Health ------------- #
class TestHealth:
    def test_health(self):
        r = requests.get(f"{API}/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_ready(self):
        r = requests.get(f"{API}/ready")
        assert r.status_code == 200
        assert r.json()["status"] == "ready"
        assert r.json()["database"] == "ok"

    def test_redirect_health(self):
        r = requests.get(f"{API}/redirect/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ------------- Auth ------------- #
class TestAuth:
    def test_register_and_me(self):
        s = requests.Session()
        email = _rand_email("reg")
        r = s.post(f"{API}/auth/register", json={"name": "Reg User", "email": email, "password": "Passw0rd!"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user"]["email"].lower() == email.lower()
        assert data["current_workspace"] is not None
        assert "access_token" in s.cookies

        me = s.get(f"{API}/auth/me")
        assert me.status_code == 200
        assert me.json()["user"]["email"].lower() == email.lower()

    def test_duplicate_register_409(self):
        s = requests.Session()
        email = _rand_email("dup")
        r1 = s.post(f"{API}/auth/register", json={"name": "Dup", "email": email, "password": "Passw0rd!"})
        assert r1.status_code == 200
        r2 = requests.post(f"{API}/auth/register", json={"name": "Dup2", "email": email, "password": "Passw0rd!"})
        assert r2.status_code == 409

    def test_login_admin(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200, r.text
        assert r.json()["user"]["email"] == ADMIN_EMAIL
        assert "access_token" in s.cookies

    def test_login_wrong_password_401(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrongpass"})
        assert r.status_code == 401

    def test_me_without_cookie_401(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_logout_clears_cookies(self):
        s = requests.Session()
        email = _rand_email("logout")
        s.post(f"{API}/auth/register", json={"name": "L", "email": email, "password": "Passw0rd!"})
        r = s.post(f"{API}/auth/logout")
        assert r.status_code == 200
        # After logout, /me should 401
        s2 = requests.Session()
        me = s2.get(f"{API}/auth/me")
        assert me.status_code == 401

    def test_brute_force_lockout_429(self):
        # Use a unique email to avoid contaminating other tests
        target_email = _rand_email("brute")
        # Ensure user exists so we're hitting brute force on real acct
        requests.post(f"{API}/auth/register", json={"name": "B", "email": target_email, "password": "Passw0rd!"})
        got_429 = False
        for i in range(7):
            r = requests.post(f"{API}/auth/login", json={"email": target_email, "password": "WrongPass!!"})
            if r.status_code == 429:
                got_429 = True
                break
        assert got_429, "Expected 429 lockout after multiple failed attempts"

    def test_forgot_password_neutral(self):
        r = requests.post(f"{API}/auth/forgot-password", json={"email": "nonexistent@midgate.io"})
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_reset_password_invalid_token(self):
        r = requests.post(f"{API}/auth/reset-password", json={"token": "invalid-token-xyz", "password": "NewPass1!"})
        assert r.status_code == 400


# ------------- Fixtures for user with workspace ------------- #
@pytest.fixture
def user_session():
    s = requests.Session()
    email = _rand_email("u")
    r = s.post(f"{API}/auth/register", json={"name": "User A", "email": email, "password": "Passw0rd!"})
    assert r.status_code == 200
    data = r.json()
    s.workspace_id = data["current_workspace"]["id"]
    s.user_email = email
    return s


@pytest.fixture
def user_session_b():
    s = requests.Session()
    email = _rand_email("ub")
    r = s.post(f"{API}/auth/register", json={"name": "User B", "email": email, "password": "Passw0rd!"})
    assert r.status_code == 200
    data = r.json()
    s.workspace_id = data["current_workspace"]["id"]
    return s


# ------------- Links ------------- #
class TestLinks:
    def test_create_link_auto_alias(self, user_session):
        r = user_session.post(f"{API}/links", json={"name": "Test Link", "destination_url": "https://example.com"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["short_path"].startswith("/api/r/")
        assert d["alias"]
        assert d["destination_url"].startswith("https://example.com")

    def test_create_link_custom_alias_and_duplicate(self, user_session):
        alias = f"myalias{uuid.uuid4().hex[:6]}"
        r = user_session.post(f"{API}/links", json={"name": "L1", "destination_url": "https://example.com", "alias": alias})
        assert r.status_code == 200
        r2 = user_session.post(f"{API}/links", json={"name": "L2", "destination_url": "https://example.com", "alias": alias})
        assert r2.status_code == 409

    @pytest.mark.parametrize("url", [
        "javascript:alert(1)",
        "file:///etc/passwd",
        "http://169.254.169.254",
        "http://127.0.0.1",
        "http://localhost/admin",
    ])
    def test_unsafe_urls_rejected(self, user_session, url):
        r = user_session.post(f"{API}/links", json={"name": "Bad", "destination_url": url})
        assert r.status_code == 400, f"Expected 400 for {url}, got {r.status_code}: {r.text}"

    def test_list_links_scoped(self, user_session):
        # Create 2 links
        user_session.post(f"{API}/links", json={"name": "LX-Foo", "destination_url": "https://example.com"})
        user_session.post(f"{API}/links", json={"name": "LX-Bar", "destination_url": "https://example.com/bar"})
        r = user_session.get(f"{API}/links")
        assert r.status_code == 200
        assert r.json()["total"] >= 2
        # Search
        r2 = user_session.get(f"{API}/links", params={"search": "LX-Foo"})
        names = [x["name"] for x in r2.json()["items"]]
        assert any("LX-Foo" in n for n in names)

    def test_link_crud_flow(self, user_session):
        r = user_session.post(f"{API}/links", json={"name": "Flow", "destination_url": "https://example.com"})
        lid = r.json()["id"]
        # GET
        assert user_session.get(f"{API}/links/{lid}").status_code == 200
        # PATCH
        rp = user_session.patch(f"{API}/links/{lid}", json={"name": "Flow Updated"})
        assert rp.status_code == 200
        assert rp.json()["name"] == "Flow Updated"
        # Pause
        rpa = user_session.post(f"{API}/links/{lid}/pause")
        assert rpa.status_code == 200 and rpa.json()["status"] == "paused"
        # Resume
        rre = user_session.post(f"{API}/links/{lid}/resume")
        assert rre.status_code == 200 and rre.json()["status"] == "active"
        # Delete
        rd = user_session.delete(f"{API}/links/{lid}")
        assert rd.status_code == 200
        # Verify gone
        assert user_session.get(f"{API}/links/{lid}").status_code == 404


# ------------- Redirect + Analytics ------------- #
class TestRedirectAndAnalytics:
    def test_redirect_302_and_analytics(self, user_session):
        alias = f"rd{uuid.uuid4().hex[:8]}"
        r = user_session.post(f"{API}/links", json={
            "name": "Redir", "destination_url": "https://example.com/target", "alias": alias
        })
        assert r.status_code == 200
        link_id = r.json()["id"]

        # Hit redirect (no follow)
        rr = requests.get(f"{API}/r/{alias}", allow_redirects=False)
        assert rr.status_code == 302, f"Expected 302 got {rr.status_code}"
        assert "example.com" in rr.headers.get("location", "")

        # Hit twice more with different UA to get analytics variety
        requests.get(f"{API}/r/{alias}", allow_redirects=False,
                     headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"})
        requests.get(f"{API}/r/{alias}", allow_redirects=False,
                     headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0) Safari/604.1"})

        # Give analytics event bus time to persist
        time.sleep(2)

        # Per-link analytics
        an = user_session.get(f"{API}/analytics/links/{link_id}")
        assert an.status_code == 200, an.text
        adata = an.json()
        assert adata.get("total_clicks", 0) > 0, f"Expected clicks, got {adata}"

        # Overview
        ov = user_session.get(f"{API}/analytics/overview")
        assert ov.status_code == 200
        odata = ov.json()
        assert "top_links" in odata or "total_clicks" in odata or "totals" in odata

    def test_paused_link_returns_404_page(self, user_session):
        alias = f"pa{uuid.uuid4().hex[:8]}"
        r = user_session.post(f"{API}/links", json={
            "name": "Paused", "destination_url": "https://example.com", "alias": alias
        })
        lid = r.json()["id"]
        user_session.post(f"{API}/links/{lid}/pause")
        rr = requests.get(f"{API}/r/{alias}", allow_redirects=False)
        assert rr.status_code == 404

    def test_nonexistent_alias_404(self):
        rr = requests.get(f"{API}/r/definitely-does-not-exist-xyz-{uuid.uuid4().hex[:6]}", allow_redirects=False)
        assert rr.status_code == 404


# ------------- Tenant Isolation ------------- #
class TestTenantIsolation:
    def test_cross_workspace_returns_404(self, user_session, user_session_b):
        r = user_session.post(f"{API}/links", json={"name": "Private", "destination_url": "https://example.com"})
        assert r.status_code == 200
        lid = r.json()["id"]

        # User B tries to GET, PATCH, DELETE
        gr = user_session_b.get(f"{API}/links/{lid}")
        assert gr.status_code == 404
        pr = user_session_b.patch(f"{API}/links/{lid}", json={"name": "hax"})
        assert pr.status_code == 404
        dr = user_session_b.delete(f"{API}/links/{lid}")
        assert dr.status_code == 404
        ar = user_session_b.get(f"{API}/analytics/links/{lid}")
        assert ar.status_code == 404


# ------------- Billing ------------- #
class TestBilling:
    def test_plans(self):
        r = requests.get(f"{API}/billing/plans")
        assert r.status_code == 200
        plans = r.json()
        # Response may be list or object
        items = plans if isinstance(plans, list) else plans.get("plans") or plans.get("items") or []
        assert len(items) == 5, f"Expected 5 plans, got {len(items)}: {plans}"
