"""Iteration 9 — Notification Center + producers (blocked traffic, webhook_failed, member_joined).

Covers:
- Notifications CRUD (list, unread-count, mark-read, read-all, dismiss) — workspace scoped
- Producer: traffic_blocked via /api/r/{alias} with bot UA + datacenter IP (throttled)
- Producer: member_joined via team invite → register → accept flow
- Producer: webhook_failed via httpbin.org/status/500 test-fire (throttled)
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://protect-links.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@midgate.io"
ADMIN_PW = "Admin123!"


def _login(session: requests.Session, email: str, pw: str) -> dict:
    r = session.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def admin_ctx():
    s = requests.Session()
    data = _login(s, ADMIN_EMAIL, ADMIN_PW)
    # workspace id from login response
    ws = None
    if isinstance(data, dict):
        ws = (data.get("workspace") or {}).get("id") or data.get("workspace_id")
    if not ws:
        # fallback: /api/workspaces/me
        r = s.get(f"{API}/workspaces", timeout=10)
        if r.status_code == 200:
            js = r.json()
            items = js.get("items") if isinstance(js, dict) else js
            if items:
                ws = items[0]["id"]
    assert ws, f"could not resolve workspace id, login body={data}"
    s.headers.update({"X-Workspace-Id": ws})
    yield {"session": s, "ws": ws, "user": data.get("user")}


# ----------------------------- Notifications CRUD ---------------------------
class TestNotificationsCRUD:
    def test_list_endpoint(self, admin_ctx):
        s = admin_ctx["session"]
        r = s.get(f"{API}/notifications", timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data and "unread_count" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["unread_count"], int)

    def test_unread_count(self, admin_ctx):
        s = admin_ctx["session"]
        r = s.get(f"{API}/notifications/unread-count", timeout=10)
        assert r.status_code == 200
        assert "count" in r.json()

    def test_requires_workspace_header(self):
        # A raw session with cookie auth but missing header should still be OK
        # because get_current_workspace falls back to the user's default workspace.
        s = requests.Session()
        _login(s, ADMIN_EMAIL, ADMIN_PW)
        r = s.get(f"{API}/notifications", timeout=10)
        # Either 200 (default ws) or 4xx — we just want no server crash
        assert r.status_code < 500


# --------------------- Producer: traffic_blocked ----------------------------
class TestBlockedTrafficProducer:
    def test_blocked_traffic_creates_notification_and_throttles(self, admin_ctx):
        s = admin_ctx["session"]
        ws = admin_ctx["ws"]

        # Create strict-preset link
        alias = f"iter9blk{uuid.uuid4().hex[:6]}"
        payload = {
            "name": "iter9 blocked test",
            "destination_url": "https://example.com/",
            "alias": alias,
            "protection_preset": "strict",
        }
        r = s.post(f"{API}/links", json=payload, timeout=15)
        assert r.status_code in (200, 201), f"create link: {r.status_code} {r.text}"
        link = r.json()
        link_id = link.get("id")
        assert link_id

        # Baseline unread count
        base = s.get(f"{API}/notifications/unread-count", timeout=10).json()["count"]

        # Hit redirect with bot UA + datacenter IP — 1st bot click
        redirect_headers = {
            "User-Agent": "python-requests/2.31",
            "X-Forwarded-For": "45.83.0.1",
        }
        r1 = requests.get(f"{API}/r/{alias}", headers=redirect_headers,
                          allow_redirects=False, timeout=15)
        assert r1.status_code in (200, 302, 403, 451), f"redirect: {r1.status_code}"

        # Wait for async event bus + notification write
        time.sleep(3.0)

        after1 = s.get(f"{API}/notifications/unread-count", timeout=10).json()["count"]
        assert after1 == base + 1, f"expected +1 traffic_blocked notif; base={base} after1={after1}"

        # Check the notification exists with type=traffic_blocked
        lst = s.get(f"{API}/notifications", timeout=10).json()["items"]
        blk = [n for n in lst if n.get("type") == "traffic_blocked" and n.get("meta", {}).get("alias") == alias]
        assert blk, "no traffic_blocked notification for our alias"
        assert blk[0]["level"] == "warning"
        notif_id = blk[0]["id"]

        # SECOND bot click within the hour → throttled → count stays the same
        r2 = requests.get(f"{API}/r/{alias}", headers=redirect_headers,
                          allow_redirects=False, timeout=15)
        assert r2.status_code in (200, 302, 403, 451)
        time.sleep(2.5)
        after2 = s.get(f"{API}/notifications/unread-count", timeout=10).json()["count"]
        assert after2 == after1, f"throttling failed; after1={after1} after2={after2}"

        # ----- Test mark-read / dismiss + link cleanup -----
        rr = s.post(f"{API}/notifications/{notif_id}/read", timeout=10)
        assert rr.status_code == 200
        after_read = s.get(f"{API}/notifications/unread-count", timeout=10).json()["count"]
        assert after_read == after2 - 1

        dd = s.delete(f"{API}/notifications/{notif_id}", timeout=10)
        assert dd.status_code == 200

        # Cleanup: delete link
        s.delete(f"{API}/links/{link_id}", timeout=10)


# --------------------- Producer: webhook_failed ----------------------------
class TestWebhookFailedProducer:
    def test_failed_webhook_creates_notification(self, admin_ctx):
        s = admin_ctx["session"]

        # Create webhook pointing to httpbin 500
        r = s.post(f"{API}/webhooks", json={
            "url": "https://httpbin.org/status/500",
            "description": "iter9-test",
            "events": ["click.recorded"],
        }, timeout=15)
        assert r.status_code in (200, 201), f"create webhook: {r.status_code} {r.text}"
        wh = r.json()
        wh_id = wh["id"]

        base = s.get(f"{API}/notifications/unread-count", timeout=10).json()["count"]

        # Test-fire (3 attempts w/ 0,2,5s delay ≈ 7s+network)
        r = s.post(f"{API}/webhooks/{wh_id}/test", timeout=30)
        assert r.status_code == 200, r.text
        deliv = r.json().get("delivery", {})
        assert deliv.get("status") == "failed", f"expected failed delivery: {deliv}"

        # Allow a small margin for the notification write
        time.sleep(1.5)
        after = s.get(f"{API}/notifications", timeout=10).json()
        wh_notifs = [n for n in after["items"]
                     if n.get("type") == "webhook_failed" and n.get("meta", {}).get("webhook_id") == wh_id]
        assert wh_notifs, "no webhook_failed notification"
        assert wh_notifs[0]["level"] == "error"

        # Cleanup
        s.delete(f"{API}/webhooks/{wh_id}", timeout=10)
        s.delete(f"{API}/notifications/{wh_notifs[0]['id']}", timeout=10)


# --------------------- Producer: member_joined -----------------------------
class TestMemberJoinedProducer:
    def test_invite_register_accept_produces_notification(self, admin_ctx):
        s = admin_ctx["session"]
        ws = admin_ctx["ws"]

        new_email = f"test_iter9_{uuid.uuid4().hex[:8]}@example.com"
        new_pw = "NewMember123!"

        # Create invitation
        r = s.post(f"{API}/team/invitations", json={"email": new_email, "role": "member"}, timeout=15)
        assert r.status_code in (200, 201), f"invite: {r.status_code} {r.text}"
        inv = r.json()
        token = inv.get("token")
        assert token

        # Register the invited user
        s2 = requests.Session()
        r = s2.post(f"{API}/auth/register",
                    json={"name": "Iter9 Member", "email": new_email, "password": new_pw}, timeout=15)
        assert r.status_code in (200, 201), f"register: {r.status_code} {r.text}"

        # Accept invitation
        r = s2.post(f"{API}/team/invitations/accept", json={"token": token}, timeout=15)
        assert r.status_code == 200, f"accept: {r.status_code} {r.text}"

        time.sleep(1.0)
        lst = s.get(f"{API}/notifications", timeout=10).json()["items"]
        mj = [n for n in lst if n.get("type") == "member_joined"
              and n.get("meta", {}).get("email") == new_email]
        assert mj, f"no member_joined notification; recent={[n['type'] for n in lst[:5]]}"
        assert mj[0]["level"] == "success"

        # Cleanup: dismiss notif + remove member
        s.delete(f"{API}/notifications/{mj[0]['id']}", timeout=10)
        # Find member user id
        members = s.get(f"{API}/team/members", timeout=10).json().get("members", [])
        nm = next((m for m in members if m.get("email") == new_email), None)
        if nm:
            s.delete(f"{API}/team/members/{nm['user_id']}", timeout=10)
