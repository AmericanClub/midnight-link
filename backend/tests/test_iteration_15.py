"""Iteration 15: security hardening + legal/branding regression tests."""
import os
import time
import pytest
import requests
from pathlib import Path

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    env = Path("/app/frontend/.env")
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")

BASE_URL = _load_backend_url()
LOCAL_URL = "http://localhost:8001"

ADMIN = ("admin@midgate.co", "Admin123!")
TEAMMATE = ("teammate@example.com", "Teammate123!")


def _login(email, pwd):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd}, timeout=10)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin_session():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def teammate_session():
    return _login(*TEAMMATE)


# ---------- Favicon / Title ----------
class TestBranding:
    def test_favicon(self):
        r = requests.get(f"{BASE_URL}/favicon.svg", timeout=10)
        assert r.status_code == 200
        assert "svg" in r.headers.get("content-type", "").lower()


# ---------- CORS ----------
class TestCORS:
    def test_evil_origin_local_not_echoed(self):
        r = requests.get(f"{LOCAL_URL}/api/health",
                         headers={"Origin": "https://evil.example.com"}, timeout=10)
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") != "https://evil.example.com"

    def test_trusted_origin_local_echoed(self):
        origin = "https://protect-links.preview.emergentagent.com"
        r = requests.get(f"{LOCAL_URL}/api/health",
                         headers={"Origin": origin}, timeout=10)
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") == origin

    def test_evil_origin_public_info(self):
        # Info-only: edge may add wildcard. Just ensure no crash.
        r = requests.get(f"{BASE_URL}/api/health",
                         headers={"Origin": "https://evil.example.com"}, timeout=10)
        assert r.status_code == 200


# ---------- Webhook SSRF ----------
class TestWebhookSSRF:
    @pytest.mark.parametrize("url", [
        "http://127.0.0.1/hook",
        "http://169.254.169.254/latest",
        "http://localhost/x",
    ])
    def test_reject_private(self, teammate_session, url):
        r = teammate_session.post(f"{BASE_URL}/api/webhooks",
                                  json={"url": url, "events": ["click.recorded"]}, timeout=10)
        assert r.status_code == 400, f"expected 400 for {url}, got {r.status_code} {r.text}"

    def test_accept_public_and_cleanup(self, teammate_session):
        r = teammate_session.post(f"{BASE_URL}/api/webhooks",
                                  json={"url": "https://example.com/webhook",
                                        "events": ["click.recorded"]}, timeout=10)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
        wh_id = r.json().get("id")
        assert wh_id
        # cleanup
        d = teammate_session.delete(f"{BASE_URL}/api/webhooks/{wh_id}", timeout=10)
        assert d.status_code in (200, 204)


# ---------- Contact form + rate limit ----------
class TestContactRateLimit:
    def test_public_ticket_and_rate_limit(self):
        s = requests.Session()
        url = f"{BASE_URL}/api/support/public"
        # First one must succeed
        body = {"name": "TEST User", "email": "test0@example.com",
                "subject": "TEST subj", "message": "TEST message payload"}
        r0 = s.post(url, json=body, timeout=10)
        assert r0.status_code == 200, f"{r0.status_code} {r0.text}"
        assert r0.json().get("ok") is True

        codes = [r0.status_code]
        for i in range(1, 8):
            body["email"] = f"test{i}@example.com"
            body["subject"] = f"TEST subj {i}"
            r = s.post(url, json=body, timeout=10)
            codes.append(r.status_code)
        # After 5 within a minute should return 429
        assert 429 in codes, f"expected 429 among codes: {codes}"


# ---------- Search regressions ----------
class TestSearchRegression:
    def test_links_search(self, teammate_session):
        r = teammate_session.get(f"{BASE_URL}/api/links?search=test", timeout=10)
        assert r.status_code == 200

    @pytest.mark.parametrize("q", [".*", "(a+)+", "["])
    def test_links_search_regex(self, teammate_session, q):
        t0 = time.time()
        r = teammate_session.get(f"{BASE_URL}/api/links", params={"search": q}, timeout=10)
        assert r.status_code == 200
        assert time.time() - t0 < 5

    def test_admin_users_search(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/users?search=admin", timeout=10)
        assert r.status_code == 200

    @pytest.mark.parametrize("q", [".*", "(a+)+"])
    def test_admin_users_search_regex(self, admin_session, q):
        t0 = time.time()
        r = admin_session.get(f"{BASE_URL}/api/admin/users", params={"search": q}, timeout=10)
        assert r.status_code == 200
        assert time.time() - t0 < 5


# ---------- Auth/session regression ----------
class TestAuthRegression:
    def test_admin_login_and_me(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/auth/me", timeout=10)
        assert r.status_code == 200
        assert r.json()["user"]["email"] == "admin@midgate.co"

    def test_teammate_login_and_me(self, teammate_session):
        r = teammate_session.get(f"{BASE_URL}/api/auth/me", timeout=10)
        assert r.status_code == 200
        assert r.json()["user"]["email"] == "teammate@example.com"
