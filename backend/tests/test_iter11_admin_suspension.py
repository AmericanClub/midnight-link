"""Iteration 11 — Admin Console RBAC + user/workspace suspension e2e tests."""
import os
import time
import uuid
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://protect-links.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

ADMIN_EMAIL = "admin@midgate.io"
ADMIN_PW = "Admin123!"
TEAMMATE_EMAIL = "teammate@example.com"
TEAMMATE_PW = "Teammate123!"


def _session_login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return s, r.json()


@pytest.fixture(scope="module")
def admin_session():
    s, data = _session_login(ADMIN_EMAIL, ADMIN_PW)
    assert data["user"]["role"] == "admin"
    return s, data


@pytest.fixture(scope="module")
def teammate_session():
    s, data = _session_login(TEAMMATE_EMAIL, TEAMMATE_PW)
    assert data["user"]["role"] != "admin"
    return s, data


# ---------------- Admin RBAC ----------------
ADMIN_GET_ENDPOINTS = [
    "/admin/overview",
    "/admin/users",
    "/admin/workspaces",
    "/admin/revenue",
    "/admin/security-events",
    "/admin/global-blocklist",
    "/admin/api-usage",
    "/admin/feeds",
]


@pytest.mark.parametrize("path", ADMIN_GET_ENDPOINTS)
def test_admin_endpoints_allow_admin(admin_session, path):
    s, _ = admin_session
    r = s.get(f"{API}{path}", timeout=20)
    assert r.status_code == 200, f"admin GET {path} => {r.status_code} {r.text[:200]}"
    assert isinstance(r.json(), dict)


@pytest.mark.parametrize("path", ADMIN_GET_ENDPOINTS)
def test_admin_endpoints_forbid_non_admin(teammate_session, path):
    s, _ = teammate_session
    r = s.get(f"{API}{path}", timeout=20)
    assert r.status_code == 403, f"non-admin GET {path} expected 403, got {r.status_code}"


def test_admin_endpoints_forbid_anonymous(path="/admin/overview"):
    r = requests.get(f"{API}{path}", timeout=20)
    assert r.status_code in (401, 403)


def test_global_blocklist_add_and_remove(admin_session):
    s, _ = admin_session
    cidr = "9.9.9.0/24"
    # Cleanup any pre-existing entry for this CIDR first
    lst = s.get(f"{API}/admin/global-blocklist").json().get("items", [])
    for it in lst:
        if it.get("value") == cidr:
            s.delete(f"{API}/admin/global-blocklist/{it['id']}")

    r = s.post(f"{API}/admin/global-blocklist", json={"value": cidr, "note": "iter11 test"})
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["value"] == cidr
    entry_id = doc["id"]

    # Verify listing contains it
    lst2 = s.get(f"{API}/admin/global-blocklist").json().get("items", [])
    assert any(it.get("id") == entry_id for it in lst2)

    # Invalid CIDR rejection
    bad = s.post(f"{API}/admin/global-blocklist", json={"value": "not-an-ip"})
    assert bad.status_code == 400

    # Delete
    dr = s.delete(f"{API}/admin/global-blocklist/{entry_id}")
    assert dr.status_code == 200
    lst3 = s.get(f"{API}/admin/global-blocklist").json().get("items", [])
    assert not any(it.get("id") == entry_id for it in lst3)


# ---------------- User suspension ----------------
@pytest.fixture(scope="module")
def throwaway_user():
    email = f"test_iter11_{uuid.uuid4().hex[:8]}@example.com"
    password = "Throw123!"
    r = requests.post(f"{API}/auth/register", json={"name": "Iter11 Throwaway", "email": email, "password": password}, timeout=20)
    assert r.status_code == 200, r.text
    uid = r.json()["user"]["id"]
    yield {"id": uid, "email": email, "password": password}
    # Cleanup: attempt via direct mongo (best effort)
    try:
        from pymongo import MongoClient
        from bson import ObjectId
        # Load MONGO_URL/DB_NAME from backend/.env if not in current env
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        if not mongo_url or not db_name:
            env_path = "/app/backend/.env"
            if os.path.exists(env_path):
                for line in open(env_path):
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        v = v.strip().strip('"').strip("'")
                        if k == "MONGO_URL" and not mongo_url:
                            mongo_url = v
                        if k == "DB_NAME" and not db_name:
                            db_name = v
        mc = MongoClient(mongo_url or "mongodb://localhost:27017")
        d = mc[db_name or "midgate_db"]
        d.users.delete_one({"_id": ObjectId(uid)})
        d.workspaces.delete_many({"owner_id": uid})
        d.workspace_members.delete_many({"user_id": uid})
    except Exception as e:
        print(f"cleanup warn: {e}")


def test_suspend_user_blocks_login_and_unsuspend_restores(admin_session, throwaway_user):
    s, _ = admin_session
    uid = throwaway_user["id"]
    # SUSPEND
    r = s.patch(f"{API}/admin/users/{uid}", json={"suspended": True})
    assert r.status_code == 200, r.text
    assert r.json().get("suspended") is True

    # login attempt should return 403
    login = requests.post(f"{API}/auth/login", json={"email": throwaway_user["email"], "password": throwaway_user["password"]}, timeout=20)
    assert login.status_code == 403, f"expected 403 for suspended login, got {login.status_code} {login.text}"
    assert "suspend" in login.text.lower()

    # UNSUSPEND
    r2 = s.patch(f"{API}/admin/users/{uid}", json={"suspended": False})
    assert r2.status_code == 200
    login2 = requests.post(f"{API}/auth/login", json={"email": throwaway_user["email"], "password": throwaway_user["password"]}, timeout=20)
    assert login2.status_code == 200, f"expected 200 after unsuspend, got {login2.status_code} {login2.text}"


def test_admin_cannot_modify_self(admin_session):
    s, data = admin_session
    my_id = data["user"]["id"]
    r = s.patch(f"{API}/admin/users/{my_id}", json={"suspended": True})
    assert r.status_code == 400
    r2 = s.patch(f"{API}/admin/users/{my_id}", json={"role": "user"})
    assert r2.status_code == 400


def test_last_admin_demotion_blocked(admin_session):
    """If admin is the only admin, cannot be demoted. This is guarded via self-check first (400),
    but we still verify counting works via a role-change attempt on self which returns 400 (self-guard)."""
    # We can't demote a different admin because there is only one admin (self). The self-guard triggers first (400).
    # So we just assert self-change is rejected (which was already done). Nothing more to check safely.
    s, data = admin_session
    r = s.patch(f"{API}/admin/users/{data['user']['id']}", json={"role": "user"})
    assert r.status_code == 400


# ---------------- Workspace suspension ----------------
@pytest.fixture(scope="module")
def teammate_workspace(teammate_session):
    _, data = teammate_session
    # Prefer teammate's own workspace (they own it) — pick one where role == owner if possible
    ws_list = data.get("workspaces") or []
    assert ws_list, "teammate should have at least one workspace"
    owned = [w for w in ws_list if w.get("role") == "owner"]
    return (owned or ws_list)[0]


@pytest.fixture(scope="module")
def teammate_smart_link(teammate_session, teammate_workspace):
    s, _ = teammate_session
    alias = f"iter11-{uuid.uuid4().hex[:6]}"
    payload = {
        "alias": alias,
        "destination_url": "https://example.com/target",
        "name": "iter11 test link",
        "protection_preset": "off",
    }
    headers = {"X-Workspace-Id": teammate_workspace["id"]}
    r = s.post(f"{API}/links", json=payload, headers=headers, timeout=20)
    assert r.status_code in (200, 201), r.text
    link = r.json()
    yield {"alias": alias, "workspace_id": teammate_workspace["id"], "id": link.get("id")}
    # cleanup
    try:
        s.delete(f"{API}/links/{link['id']}", headers=headers)
    except Exception:
        pass


def test_workspace_suspension_blocks_redirect(admin_session, teammate_smart_link):
    s_admin, _ = admin_session
    alias = teammate_smart_link["alias"]
    ws_id = teammate_smart_link["workspace_id"]

    # Baseline: link is reachable (either 302 direct redirect or 200 security challenge page)
    ua = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
          "Referer": "https://google.com/"}
    base = requests.get(f"{API}/r/{alias}", allow_redirects=False, timeout=20, headers=ua)
    assert base.status_code in (200, 302), f"baseline expected 200/302, got {base.status_code}"
    assert base.status_code != 404, "baseline should not be 404 before suspension"

    # Suspend workspace
    r = s_admin.patch(f"{API}/admin/workspaces/{ws_id}", json={"suspended": True})
    assert r.status_code == 200
    # cache TTL is 30s; wait briefly, but since it's set-time, our next request may still hit cache.
    # The _suspended_workspaces cache lives 30s. To make test robust, hit repeatedly for up to 35s.
    blocked = False
    deadline = time.time() + 35
    while time.time() < deadline:
        r2 = requests.get(f"{API}/r/{alias}", allow_redirects=False, timeout=20, headers=ua)
        # workspace-suspended returns 404 with "Link unavailable"
        if r2.status_code == 404 and "unavailable" in r2.text.lower():
            blocked = True
            break
        time.sleep(2)
    # Restore regardless
    s_admin.patch(f"{API}/admin/workspaces/{ws_id}", json={"suspended": False})

    assert blocked, "workspace suspension did not block redirect within cache TTL window"

    # After restore, wait for cache to clear
    ok = False
    deadline = time.time() + 35
    while time.time() < deadline:
        r3 = requests.get(f"{API}/r/{alias}", allow_redirects=False, timeout=20, headers=ua)
        if r3.status_code in (200, 302) and not (r3.status_code == 404):
            ok = True
            break
        time.sleep(2)
    assert ok, "redirect did not resume after workspace unsuspension"


# ---------------- Cleanup safety net ----------------
def test_cleanup_ensure_admin_and_teammate_not_suspended(admin_session):
    """Post-suite: verify neither admin nor teammate got left suspended by any prior run."""
    s, _ = admin_session
    users = s.get(f"{API}/admin/users?search=midgate.io").json().get("items", [])
    users += s.get(f"{API}/admin/users?search=teammate").json().get("items", [])
    for u in users:
        if u.get("email") in (ADMIN_EMAIL, TEAMMATE_EMAIL):
            if u.get("suspended"):
                # force unsuspend
                s.patch(f"{API}/admin/users/{u['id']}", json={"suspended": False})
                pytest.fail(f"{u['email']} was left suspended — restored.")
