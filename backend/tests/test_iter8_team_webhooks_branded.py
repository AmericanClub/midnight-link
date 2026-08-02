"""Iteration 8 tests: Team invitations, webhook manual retry, branded link preview."""
import os
import uuid
import time
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@midgate.io"
ADMIN_PASS = "Admin123!"
TEAMMATE_EMAIL = "teammate@example.com"
TEAMMATE_PASS = "Teammate123!"
ADMIN_WS_ID = "c5a21b8e-1fdc-4bc8-9265-5601095c4390"


# ---------------- fixtures ---------------- #
@pytest.fixture(scope="module")
def mongo():
    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    dbname = os.environ.get("DB_NAME", "test_database")
    cli = MongoClient(url)
    yield cli[dbname]
    cli.close()


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    data = r.json()
    cw = data.get("current_workspace")
    if isinstance(cw, dict):
        ws_id = cw.get("id")
    else:
        ws_id = cw or (data.get("workspaces") or [{}])[0].get("id")
    if ws_id:
        s.headers.update({"X-Workspace-Id": ws_id})
    return s, ws_id, data


@pytest.fixture(scope="module")
def admin():
    s, ws, data = _login(ADMIN_EMAIL, ADMIN_PASS)
    # force admin workspace
    s.headers.update({"X-Workspace-Id": ADMIN_WS_ID})
    return s, ADMIN_WS_ID, data


@pytest.fixture(scope="module")
def teammate():
    s, ws, data = _login(TEAMMATE_EMAIL, TEAMMATE_PASS)
    return s, ws, data


# =============== TEAM =============== #
class TestTeamMembers:
    def test_list_members(self, admin):
        s, ws, _ = admin
        r = s.get(f"{API}/team/members")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "members" in data and "invitations" in data and "your_role" in data
        assert data["your_role"] in ("owner", "admin")
        emails = [m["email"] for m in data["members"]]
        assert ADMIN_EMAIL in emails
        owner_row = next(m for m in data["members"] if m["email"] == ADMIN_EMAIL)
        assert owner_row["is_owner"] is True
        assert owner_row["role_label"] == "Owner"

    def test_non_manager_forbidden(self, teammate):
        s, ws, _ = teammate
        # teammate is member of admin ws; try to invite there
        s.headers.update({"X-Workspace-Id": ADMIN_WS_ID})
        r = s.post(f"{API}/team/invitations",
                   json={"email": "x@example.com", "role": "member"})
        assert r.status_code == 403
        # restore header
        s.headers.pop("X-Workspace-Id", None)


class TestInvitations:
    def test_invalid_role(self, admin):
        s, _, _ = admin
        r = s.post(f"{API}/team/invitations",
                   json={"email": f"TEST_{uuid.uuid4().hex[:8]}@ex.com", "role": "superadmin"})
        assert r.status_code == 400

    def test_duplicate_member_409(self, admin):
        s, _, _ = admin
        r = s.post(f"{API}/team/invitations",
                   json={"email": TEAMMATE_EMAIL, "role": "member"})
        assert r.status_code == 409

    def test_lookup_unknown_token_404(self, admin):
        r = requests.get(f"{API}/team/invitations/lookup/does-not-exist-xyz")
        assert r.status_code == 404

    def test_full_invite_accept_flow(self, admin, mongo):
        s, _, _ = admin
        new_email = f"test_invite_{uuid.uuid4().hex[:10]}@example.com"
        # create invite
        r = s.post(f"{API}/team/invitations",
                   json={"email": new_email, "role": "billing_manager"})
        assert r.status_code == 200, r.text
        inv = r.json()
        token = inv["token"]
        assert inv["accept_path"].startswith("/accept-invite?token=")
        assert inv["role"] == "billing_manager"

        # public lookup
        r2 = requests.get(f"{API}/team/invitations/lookup/{token}")
        assert r2.status_code == 200
        look = r2.json()
        assert look["email"] == new_email
        assert look["status"] == "pending"
        assert look["role_label"] == "Billing"

        # register new user
        pw = "TestPass123!"
        rr = requests.post(f"{API}/auth/register",
                           json={"name": "Invited User", "email": new_email, "password": pw})
        assert rr.status_code in (200, 201), rr.text
        ns, nws, nme = _login(new_email, pw)

        # accept while signed in as different email should 403
        wrong = requests.Session()
        wrong.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
        rbad = wrong.post(f"{API}/team/invitations/accept", json={"token": token})
        assert rbad.status_code == 403

        # accept as correct user
        ra = ns.post(f"{API}/team/invitations/accept", json={"token": token})
        assert ra.status_code == 200, ra.text
        body = ra.json()
        assert body["ok"] is True
        assert body["workspace_id"] == ADMIN_WS_ID

        # idempotent
        ra2 = ns.post(f"{API}/team/invitations/accept", json={"token": token})
        assert ra2.status_code == 200
        assert ra2.json().get("already") is True

        # /auth/me shows admin workspace with billing_manager role
        me = ns.get(f"{API}/auth/me")
        assert me.status_code == 200
        wss = me.json().get("workspaces") or []
        found = next((w for w in wss if w["id"] == ADMIN_WS_ID), None)
        assert found is not None
        assert found.get("role") == "billing_manager"

        # cleanup: remove from workspace + delete user + invitation
        mongo.workspace_members.delete_many({"workspace_id": ADMIN_WS_ID,
                                             "user_id": nme["id"] if "id" in nme else (nme.get("user") or {}).get("id")})
        mongo.users.delete_many({"email": new_email})
        mongo.invitations.delete_many({"token": token})


class TestMemberManagementGuards:
    def test_owner_role_change_400(self, admin):
        s, _, me = admin
        owner_id = me.get("id") or (me.get("user") or {}).get("id")
        assert owner_id
        r = s.patch(f"{API}/team/members/{owner_id}", json={"role": "admin"})
        assert r.status_code == 400

    def test_owner_delete_400(self, admin):
        s, _, me = admin
        owner_id = me.get("id") or (me.get("user") or {}).get("id")
        r = s.delete(f"{API}/team/members/{owner_id}")
        assert r.status_code == 400

    def test_change_and_remove_member(self, admin, mongo):
        s, _, _ = admin
        # Create a temporary user + member row directly for isolation
        new_email = f"test_mem_{uuid.uuid4().hex[:8]}@ex.com"
        pw = "TestPass123!"
        rr = requests.post(f"{API}/auth/register",
                           json={"name": "Temp Member", "email": new_email, "password": pw})
        assert rr.status_code in (200, 201)
        u = mongo.users.find_one({"email": new_email})
        assert u
        uid = str(u["_id"])
        mongo.workspace_members.insert_one({
            "id": str(uuid.uuid4()), "workspace_id": ADMIN_WS_ID,
            "user_id": uid, "role": "member", "created_at": "now"})

        # change role
        r = s.patch(f"{API}/team/members/{uid}", json={"role": "billing_manager"})
        assert r.status_code == 200
        assert r.json()["role"] == "billing_manager"

        # invalid role
        r = s.patch(f"{API}/team/members/{uid}", json={"role": "root"})
        assert r.status_code == 400

        # non-manager PATCH 403
        ts, _, _ = _login(TEAMMATE_EMAIL, TEAMMATE_PASS)
        ts.headers.update({"X-Workspace-Id": ADMIN_WS_ID})
        r = ts.patch(f"{API}/team/members/{uid}", json={"role": "member"})
        assert r.status_code == 403

        # remove
        r = s.delete(f"{API}/team/members/{uid}")
        assert r.status_code == 200

        # cleanup
        mongo.users.delete_many({"email": new_email})
        mongo.workspace_members.delete_many({"user_id": uid})


# =============== BRANDED PRIMARY DOMAIN =============== #
class TestBrandedDomain:
    def test_primary_domain_flag(self, admin, mongo):
        s, _, _ = admin
        # baseline: no primary domain
        me1 = s.get(f"{API}/auth/me").json()
        w1 = next((w for w in me1["workspaces"] if w["id"] == ADMIN_WS_ID), {})
        baseline = w1.get("primary_domain")

        doc = {
            "id": str(uuid.uuid4()),
            "workspace_id": ADMIN_WS_ID,
            "domain": "go.midgate.test",
            "status": "verified",
            "is_primary": True,
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        mongo.custom_domains.insert_one(doc)
        try:
            me2 = s.get(f"{API}/auth/me").json()
            w2 = next((w for w in me2["workspaces"] if w["id"] == ADMIN_WS_ID), {})
            assert w2.get("primary_domain") == "go.midgate.test", f"got {w2}"
        finally:
            mongo.custom_domains.delete_one({"id": doc["id"]})
            # verify cleanup restored
            me3 = s.get(f"{API}/auth/me").json()
            w3 = next((w for w in me3["workspaces"] if w["id"] == ADMIN_WS_ID), {})
            assert w3.get("primary_domain") == baseline


# =============== WEBHOOK RETRY =============== #
class TestWebhookRetry:
    def test_create_test_retry_flow(self, admin, mongo):
        s, _, _ = admin
        # Create webhook pointing to failing endpoint
        r = s.post(f"{API}/webhooks",
                   json={"url": "https://httpbin.org/status/500",
                         "events": ["click.recorded", "click.blocked", "click.challenged"],
                         "description": "TEST_retry"})
        assert r.status_code in (200, 201), r.text
        wh = r.json()
        wid = wh["id"]
        try:
            # Trigger test send (async retries — allow time)
            rt = s.post(f"{API}/webhooks/{wid}/test")
            assert rt.status_code in (200, 202), rt.text
            time.sleep(10)  # allow 0/2/5s retries to finish

            # List deliveries
            rd = s.get(f"{API}/webhooks/{wid}/deliveries")
            assert rd.status_code == 200
            items = rd.json().get("items") or []
            assert len(items) > 0, "expected at least one delivery record"
            failed = [d for d in items if d.get("status") != "success"
                      and (d.get("status_code") or 0) >= 400 or d.get("status") == "failed"]
            # fall back — just pick the newest
            target = failed[0] if failed else items[0]
            did = target["id"]
            before_count = len(items)

            # Retry
            rr = s.post(f"{API}/webhooks/{wid}/deliveries/{did}/retry")
            assert rr.status_code == 200, rr.text
            time.sleep(8)

            rd2 = s.get(f"{API}/webhooks/{wid}/deliveries")
            items2 = rd2.json().get("items") or []
            assert len(items2) > before_count, f"retry did not create new delivery: {before_count} vs {len(items2)}"
        finally:
            s.delete(f"{API}/webhooks/{wid}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
