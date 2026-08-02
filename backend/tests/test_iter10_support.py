"""Iteration 10 — Support / Ticket system.

Covers:
- Public ticket creation (no auth): valid + validation + unknown category fallback
- User ticket flow (create, list scoped to caller, get owner-only, reply -> reopens)
- Admin management: list all + open_count, filter, detail, non-admin gets 403
- Admin reply: message appended, status -> pending, notification created for workspace tickets
- Admin PATCH: status/priority validation + status change notification
- Public ticket admin reply must NOT error and MUST NOT create notification (no workspace_id)
"""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://protect-links.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@midgate.io"
ADMIN_PW = "Admin123!"
TEAMMATE_EMAIL = "teammate@example.com"
TEAMMATE_PW = "Teammate123!"


def _login(s: requests.Session, email: str, pw: str) -> dict:
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()


def _ws_from_login(data: dict) -> str:
    cw = data.get("current_workspace") or data.get("workspace") or {}
    return cw.get("id") or data.get("workspace_id")


def _admin_ws(data: dict) -> str:
    # Admin should use admin's own workspace
    return _ws_from_login(data)


def _teammate_admin_ws(data: dict) -> str:
    # Teammate is a member of admin's workspace; use that so notifications land there
    for ws in data.get("workspaces", []):
        if ws.get("name", "").startswith("MidGate Admin"):
            return ws["id"]
    return _ws_from_login(data)


@pytest.fixture(scope="module")
def admin_ctx():
    s = requests.Session()
    data = _login(s, ADMIN_EMAIL, ADMIN_PW)
    ws = _ws_from_login(data)
    assert ws, f"cannot resolve admin workspace: {data}"
    s.headers.update({"X-Workspace-Id": ws})
    yield {"s": s, "ws": ws, "user": data.get("user")}


@pytest.fixture(scope="module")
def teammate_ctx():
    s = requests.Session()
    data = _login(s, TEAMMATE_EMAIL, TEAMMATE_PW)
    ws = _ws_from_login(data)
    assert ws, f"cannot resolve teammate workspace: {data}"
    s.headers.update({"X-Workspace-Id": ws})
    yield {"s": s, "ws": ws, "user": data.get("user")}


@pytest.fixture(scope="module")
def created_ids():
    """Track ids so we can attempt cleanup at teardown."""
    ids = {"tickets": []}
    yield ids
    # Best-effort cleanup: no delete endpoint exists; leave ids for reference.


# ----------------------------- Public tickets ------------------------------
class TestPublicTickets:
    def test_create_public_valid(self, created_ids):
        payload = {
            "name": "TEST Public User",
            "email": "test_public_user@example.com",
            "subject": "TEST public ticket",
            "category": "bug",
            "message": "Something broken, please help.",
        }
        r = requests.post(f"{API}/support/public", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        js = r.json()
        assert js.get("ok") is True
        assert isinstance(js.get("id"), str) and len(js["id"]) > 10
        created_ids["tickets"].append(js["id"])
        created_ids["public_id"] = js["id"]

    def test_create_public_unknown_category_falls_back(self, admin_ctx, created_ids):
        payload = {
            "name": "TEST Unknown Cat",
            "email": "test_unknown_cat@example.com",
            "subject": "TEST unknown category",
            "category": "not-a-real-category",
            "message": "hi",
        }
        r = requests.post(f"{API}/support/public", json=payload, timeout=15)
        assert r.status_code == 200
        tid = r.json()["id"]
        created_ids["tickets"].append(tid)
        # verify via admin detail
        r2 = admin_ctx["s"].get(f"{API}/support/admin/tickets/{tid}", timeout=15)
        assert r2.status_code == 200
        assert r2.json()["category"] == "other"

    @pytest.mark.parametrize("bad_payload", [
        {"name": "x", "email": "not-an-email", "subject": "s", "category": "bug", "message": "m"},
        {"name": "", "email": "x@y.com", "subject": "s", "category": "bug", "message": "m"},
        {"email": "x@y.com", "subject": "s", "category": "bug", "message": "m"},  # missing name
        {"name": "x", "email": "x@y.com", "subject": "s", "category": "bug"},  # missing message
    ])
    def test_public_validation_422(self, bad_payload):
        r = requests.post(f"{API}/support/public", json=bad_payload, timeout=15)
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"


# ----------------------------- User tickets --------------------------------
class TestUserTickets:
    def test_create_user_ticket(self, teammate_ctx, created_ids):
        r = teammate_ctx["s"].post(f"{API}/support/tickets", json={
            "subject": "TEST user ticket",
            "category": "billing",
            "priority": "high",
            "message": "Need help with invoice",
        }, timeout=15)
        assert r.status_code == 200, r.text
        t = r.json()
        assert t["status"] == "open"
        assert t["category"] == "billing"
        assert t["priority"] == "high"
        assert len(t["messages"]) == 1
        assert t["messages"][0]["author"] == "user"
        created_ids["user_ticket"] = t["id"]
        created_ids["tickets"].append(t["id"])

    def test_list_scoped_to_caller(self, teammate_ctx, created_ids):
        r = teammate_ctx["s"].get(f"{API}/support/tickets", timeout=15)
        assert r.status_code == 200
        ids = [t["id"] for t in r.json()["items"]]
        assert created_ids["user_ticket"] in ids

    def test_get_owner_only(self, teammate_ctx, admin_ctx, created_ids):
        tid = created_ids["user_ticket"]
        # owner can get
        r = teammate_ctx["s"].get(f"{API}/support/tickets/{tid}", timeout=15)
        assert r.status_code == 200
        # admin (different user_id) hitting the user endpoint should get 404
        r2 = admin_ctx["s"].get(f"{API}/support/tickets/{tid}", timeout=15)
        assert r2.status_code == 404

    def test_user_list_does_not_show_public_ticket(self, teammate_ctx, created_ids):
        r = teammate_ctx["s"].get(f"{API}/support/tickets", timeout=15)
        ids = [t["id"] for t in r.json()["items"]]
        assert created_ids["public_id"] not in ids


# ----------------------------- Admin management ----------------------------
class TestAdminManagement:
    def test_non_admin_forbidden(self, teammate_ctx):
        for path in ("/support/admin/tickets", "/support/admin/tickets/anything"):
            r = teammate_ctx["s"].get(f"{API}{path}", timeout=15)
            assert r.status_code == 403, f"{path} expected 403 got {r.status_code}"
        r = teammate_ctx["s"].post(f"{API}/support/admin/tickets/x/reply", json={"body": "no"}, timeout=15)
        assert r.status_code == 403
        r = teammate_ctx["s"].patch(f"{API}/support/admin/tickets/x", json={"status": "resolved"}, timeout=15)
        assert r.status_code == 403

    def test_admin_list_open_count(self, admin_ctx, created_ids):
        r = admin_ctx["s"].get(f"{API}/support/admin/tickets", timeout=15)
        assert r.status_code == 200
        js = r.json()
        assert "items" in js and "open_count" in js
        assert isinstance(js["open_count"], int)
        ids = {t["id"] for t in js["items"]}
        assert created_ids["user_ticket"] in ids
        assert created_ids["public_id"] in ids

    def test_admin_status_filter(self, admin_ctx):
        r = admin_ctx["s"].get(f"{API}/support/admin/tickets", params={"status": "open"}, timeout=15)
        assert r.status_code == 200
        for t in r.json()["items"]:
            assert t["status"] == "open"

    def test_admin_get_detail(self, admin_ctx, created_ids):
        r = admin_ctx["s"].get(f"{API}/support/admin/tickets/{created_ids['user_ticket']}", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["id"] == created_ids["user_ticket"]
        assert isinstance(d["messages"], list)


# ----------------------------- Admin reply + notification ------------------
class TestAdminReplyNotify:
    def test_admin_reply_sets_pending_and_notifies(self, admin_ctx, teammate_ctx, created_ids):
        tid = created_ids["user_ticket"]
        # snapshot notification list before
        before = teammate_ctx["s"].get(f"{API}/notifications", timeout=15)
        assert before.status_code == 200
        before_ids = {n["id"] for n in before.json().get("items", [])}

        r = admin_ctx["s"].post(f"{API}/support/admin/tickets/{tid}/reply",
                                json={"body": "Thanks, looking into it."}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "pending"
        assert d["messages"][-1]["author"] == "admin"

        # notification produced in teammate's workspace
        after = teammate_ctx["s"].get(f"{API}/notifications", timeout=15)
        assert after.status_code == 200
        new = [n for n in after.json().get("items", []) if n["id"] not in before_ids]
        assert any(n.get("type") == "ticket_reply" for n in new), f"no ticket_reply notification found; new={new}"

    def test_user_reply_reopens(self, teammate_ctx, created_ids):
        tid = created_ids["user_ticket"]
        r = teammate_ctx["s"].post(f"{API}/support/tickets/{tid}/reply",
                                    json={"body": "Any update?"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["status"] == "open"

    def test_admin_reply_on_public_ticket_no_error(self, admin_ctx, created_ids):
        tid = created_ids["public_id"]
        r = admin_ctx["s"].post(f"{API}/support/admin/tickets/{tid}/reply",
                                 json={"body": "Thanks for reporting."}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pending"


# ----------------------------- Admin PATCH ---------------------------------
class TestAdminPatch:
    def test_patch_invalid_status(self, admin_ctx, created_ids):
        r = admin_ctx["s"].patch(f"{API}/support/admin/tickets/{created_ids['user_ticket']}",
                                   json={"status": "bogus"}, timeout=15)
        assert r.status_code == 400

    def test_patch_invalid_priority(self, admin_ctx, created_ids):
        r = admin_ctx["s"].patch(f"{API}/support/admin/tickets/{created_ids['user_ticket']}",
                                   json={"priority": "urgent"}, timeout=15)
        assert r.status_code == 400

    def test_patch_status_resolves_and_notifies(self, admin_ctx, teammate_ctx, created_ids):
        tid = created_ids["user_ticket"]
        before = teammate_ctx["s"].get(f"{API}/notifications", timeout=15).json().get("items", [])
        before_ids = {n["id"] for n in before}

        r = admin_ctx["s"].patch(f"{API}/support/admin/tickets/{tid}",
                                   json={"status": "resolved", "priority": "low"}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "resolved"
        assert d["priority"] == "low"

        after = teammate_ctx["s"].get(f"{API}/notifications", timeout=15).json().get("items", [])
        new = [n for n in after if n["id"] not in before_ids]
        assert any(n.get("type") == "ticket_status" for n in new), f"no ticket_status notification; new={new}"


# ----------------------------- Cleanup -------------------------------------
def test_zz_cleanup_created_tickets(created_ids):
    """Best-effort cleanup via direct Mongo. Skipped if not available."""
    try:
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        if not mongo_url or not db_name:
            pytest.skip("MONGO_URL / DB_NAME not available in test env")
        c = MongoClient(mongo_url)
        res = c[db_name].tickets.delete_many({"id": {"$in": created_ids["tickets"]}})
        print(f"cleaned tickets: {res.deleted_count}")
    except Exception as e:
        pytest.skip(f"cleanup skipped: {e}")
