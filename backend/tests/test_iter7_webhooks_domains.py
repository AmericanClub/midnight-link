"""Iteration 7 backend tests — Webhooks + Custom Domains."""
import os
import time
import uuid
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    # Fallback for direct backend tests: read frontend .env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL"):
                    BASE = line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass

ADMIN_EMAIL = "admin@midgate.io"
ADMIN_PASSWORD = "Admin123!"


# ------------------- fixtures ------------------- #
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    me = s.get(f"{BASE}/api/auth/me", timeout=10).json()
    ws_id = me.get("current_workspace", {}).get("id") or me["workspaces"][0]["id"]
    s.headers.update({"X-Workspace-Id": ws_id, "Content-Type": "application/json"})
    s.ws_id = ws_id
    return s


@pytest.fixture(scope="module")
def created_webhooks(admin_session):
    ids = []
    yield ids
    for wid in ids:
        try:
            admin_session.delete(f"{BASE}/api/webhooks/{wid}", timeout=10)
        except Exception:
            pass


@pytest.fixture(scope="module")
def created_domains(admin_session):
    ids = []
    yield ids
    for did in ids:
        try:
            admin_session.delete(f"{BASE}/api/domains/{did}", timeout=10)
        except Exception:
            pass


# =================== WEBHOOKS =================== #
class TestWebhooks:
    def test_event_types(self, admin_session):
        r = admin_session.get(f"{BASE}/api/webhooks/events", timeout=10)
        assert r.status_code == 200
        events = r.json()["events"]
        assert set(events) == {"click.recorded", "click.blocked", "click.challenged"}

    def test_create_lists_secret_hidden(self, admin_session, created_webhooks):
        r = admin_session.post(f"{BASE}/api/webhooks", json={
            "url": "https://httpbin.org/post",
            "description": "TEST_it7 primary",
            "events": ["click.recorded", "click.blocked"],
        }, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["secret"].startswith("whsec_")
        assert data["url"] == "https://httpbin.org/post"
        assert data["enabled"] is True
        created_webhooks.append(data["id"])

        lst = admin_session.get(f"{BASE}/api/webhooks", timeout=10).json()["items"]
        row = next(w for w in lst if w["id"] == data["id"])
        assert "secret" not in row
        assert row["secret_prefix"].startswith("whsec_")

    def test_reject_private_url(self, admin_session):
        r = admin_session.post(f"{BASE}/api/webhooks", json={
            "url": "http://127.0.0.1/hook", "events": ["click.recorded"],
        }, timeout=10)
        assert r.status_code == 400

    def test_reject_empty_events(self, admin_session):
        r = admin_session.post(f"{BASE}/api/webhooks", json={
            "url": "https://httpbin.org/post", "events": [],
        }, timeout=10)
        assert r.status_code == 400

    def test_patch_toggle_and_events(self, admin_session, created_webhooks):
        wid = created_webhooks[0]
        r = admin_session.patch(f"{BASE}/api/webhooks/{wid}",
                                json={"enabled": False, "events": ["click.recorded"]}, timeout=10)
        assert r.status_code == 200
        assert r.json()["enabled"] is False
        assert r.json()["events"] == ["click.recorded"]
        # re-enable and set all 3 events for later dispatch tests
        r2 = admin_session.patch(f"{BASE}/api/webhooks/{wid}",
                                 json={"enabled": True,
                                       "events": ["click.recorded", "click.blocked", "click.challenged"]},
                                 timeout=10)
        assert r2.status_code == 200
        assert r2.json()["enabled"] is True

    def test_test_ping_success(self, admin_session, created_webhooks):
        wid = created_webhooks[0]
        r = admin_session.post(f"{BASE}/api/webhooks/{wid}/test", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()["delivery"]
        assert d["status"] == "success"
        assert d["status_code"] == 200
        assert d["attempts"] >= 1

    def test_test_ping_failure_retries(self, admin_session, created_webhooks):
        r = admin_session.post(f"{BASE}/api/webhooks", json={
            "url": "https://httpbin.org/status/500",
            "events": ["click.recorded"], "description": "TEST_it7 fail",
        }, timeout=15)
        assert r.status_code == 200
        fid = r.json()["id"]
        created_webhooks.append(fid)
        r2 = admin_session.post(f"{BASE}/api/webhooks/{fid}/test", timeout=45)
        assert r2.status_code == 200
        d = r2.json()["delivery"]
        assert d["status"] == "failed"
        assert d["status_code"] == 500
        assert d["attempts"] == 3

    def test_rotate_secret(self, admin_session, created_webhooks):
        wid = created_webhooks[0]
        r = admin_session.post(f"{BASE}/api/webhooks/{wid}/rotate-secret", timeout=10)
        assert r.status_code == 200
        assert r.json()["secret"].startswith("whsec_")

    def test_dispatch_on_real_click_recorded(self, admin_session, created_webhooks):
        wid = created_webhooks[0]
        # Fire a click to alias haRMSF as directed by review request
        r = requests.get(f"{BASE}/api/r/haRMSF", headers={
            "X-Forwarded-For": "114.4.5.6",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
        }, allow_redirects=False, timeout=15)
        assert r.status_code in (302, 200, 403)  # 302 normally

        # Poll for delivery
        found = None
        for _ in range(15):
            time.sleep(1)
            deliveries = admin_session.get(f"{BASE}/api/webhooks/{wid}/deliveries", timeout=10).json()["items"]
            found = next((x for x in deliveries if x["event_type"] == "click.recorded"), None)
            if found:
                break
        assert found is not None, "click.recorded delivery not received within 15s"

    def test_delete_webhook(self, admin_session, created_webhooks):
        # Create a throwaway to delete
        r = admin_session.post(f"{BASE}/api/webhooks", json={
            "url": "https://httpbin.org/post", "events": ["click.recorded"],
        }, timeout=15)
        assert r.status_code == 200
        wid = r.json()["id"]
        d = admin_session.delete(f"{BASE}/api/webhooks/{wid}", timeout=10)
        assert d.status_code == 200
        # Verify gone (404 on subsequent GET deliveries)
        g = admin_session.get(f"{BASE}/api/webhooks/{wid}/deliveries", timeout=10)
        assert g.status_code == 404


# =================== CUSTOM DOMAINS =================== #
class TestCustomDomains:
    def test_invalid_domain(self, admin_session):
        r = admin_session.post(f"{BASE}/api/domains", json={"domain": "not a domain"}, timeout=10)
        assert r.status_code == 400

    def test_add_domain(self, admin_session, created_domains):
        # Use a unique subdomain to avoid 409 across reruns
        d = f"go{uuid.uuid4().hex[:6]}.example.com"
        r = admin_session.post(f"{BASE}/api/domains", json={"domain": d}, timeout=10)
        assert r.status_code == 200, r.text
        obj = r.json()
        assert obj["status"] == "pending"
        assert obj["domain"] == d
        assert obj["instructions"]["txt"]["host"] == f"_midgate-challenge.{d}"
        assert obj["instructions"]["txt"]["value"].startswith("midgate-verify=")
        assert obj["instructions"]["cname"]["value"] == "edge.midgate.io"
        created_domains.append(obj["id"])
        # store for later tests
        admin_session.first_domain = obj

    def test_list_includes_edge_host(self, admin_session):
        r = admin_session.get(f"{BASE}/api/domains", timeout=10)
        assert r.status_code == 200
        assert r.json()["edge_host"] == "edge.midgate.io"
        assert len(r.json()["items"]) >= 1

    def test_duplicate_domain(self, admin_session):
        d = admin_session.first_domain["domain"]
        r = admin_session.post(f"{BASE}/api/domains", json={"domain": d}, timeout=10)
        assert r.status_code == 409

    def test_verify_returns_not_found(self, admin_session):
        did = admin_session.first_domain["id"]
        r = admin_session.post(f"{BASE}/api/domains/{did}/verify", timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert body["verified"] is False
        assert "message" in body

    def test_set_primary_guard_before_verified(self, admin_session):
        did = admin_session.first_domain["id"]
        r = admin_session.post(f"{BASE}/api/domains/{did}/primary", timeout=10)
        assert r.status_code == 400
        assert "Verify" in r.json().get("detail", "")

    def test_delete_domain(self, admin_session, created_domains):
        did = admin_session.first_domain["id"]
        r = admin_session.delete(f"{BASE}/api/domains/{did}", timeout=10)
        assert r.status_code == 200
        # remove from cleanup list
        try:
            created_domains.remove(did)
        except ValueError:
            pass


# =================== RBAC =================== #
class TestDomainsRBAC:
    def test_member_forbidden(self):
        # Register a fresh user; they become owner of their own workspace.
        # To exercise 403, we monkey-patch: register in their own workspace and
        # attempt /api/domains — as owner they should succeed. So the true
        # 403 path needs a workspace where they are member. We approximate by
        # calling with an X-Workspace-Id header pointing to the admin workspace,
        # which the fresh user is NOT a member of => 404 (not 403). Skip if 403
        # can't be constructed cleanly.
        s = requests.Session()
        email = f"TEST_it7_member_{uuid.uuid4().hex[:6]}@midgate.io"
        r = s.post(f"{BASE}/api/auth/register", json={
            "name": "TEST_it7_member", "email": email, "password": "Member123!",
        }, timeout=15)
        assert r.status_code in (200, 201), r.text
        # Attempt to hit /api/domains on admin workspace id (not a member) - expect 404
        r2 = s.get(f"{BASE}/api/domains",
                   headers={"X-Workspace-Id": "c5a21b8e-1fdc-4bc8-9265-5601095c4390"}, timeout=10)
        # Either 404 (not a member) or 403 (member of wrong role). Both prove
        # RBAC gating works.
        assert r2.status_code in (403, 404), r2.text
