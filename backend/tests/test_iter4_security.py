"""MidGate iteration 4 tests: Threat intel, IP lists, per-link protection,
Blocker API, and Admin panel."""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
try:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
except Exception:
    pass
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@midgate.io"
ADMIN_PASS = "Admin123!"
HUMAN_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"
BOT_UA = "curl/8.0"
DC_IP = "3.5.1.1"        # AWS range
HUMAN_IP = "24.48.10.10" # residential


def _rand_email(p="u"):
    return f"TEST_it4_{p}_{uuid.uuid4().hex[:8]}@midgate.io"


@pytest.fixture
def sess():
    s = requests.Session()
    email = _rand_email("u")
    r = s.post(f"{API}/auth/register", json={"name": "It4 U", "email": email, "password": "Passw0rd!"})
    assert r.status_code == 200, r.text
    s.workspace_id = r.json()["current_workspace"]["id"]
    s.email = email
    return s


@pytest.fixture
def admin_sess():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, r.text
    return s


# --------------------- Threat Feeds --------------------- #
class TestFeeds:
    def test_feeds(self, sess):
        r = sess.get(f"{API}/security/feeds")
        assert r.status_code == 200
        d = r.json()
        assert "tor_count" in d and "datacenter_ranges" in d
        assert d["datacenter_ranges"] > 0
        assert "last_refresh" in d


# --------------------- IP Lists --------------------- #
class TestIPLists:
    def test_ip_rule_crud_and_validation(self, sess):
        # bad value
        rb = sess.post(f"{API}/security/ip-rules", json={"list_type": "block", "value": "not-an-ip"})
        assert rb.status_code == 400
        # good CIDR
        r = sess.post(f"{API}/security/ip-rules", json={"list_type": "block", "value": "10.0.0.0/24", "note": "TEST"})
        assert r.status_code == 200
        rid = r.json()["id"]
        lst = sess.get(f"{API}/security/ip-rules").json()
        assert any(x["id"] == rid for x in lst["items"])
        # delete
        rd = sess.delete(f"{API}/security/ip-rules/{rid}")
        assert rd.status_code == 200

    def test_blocklist_blocks_redirect(self, sess):
        alias = f"ipb{uuid.uuid4().hex[:8]}"
        sess.post(f"{API}/links", json={"name": "IPB", "destination_url": "https://example.com", "alias": alias})
        # blocklist specific IP
        sess.post(f"{API}/security/ip-rules", json={"list_type": "block", "value": "5.5.5.5"})
        time.sleep(16)
        rr = requests.get(f"{API}/r/{alias}", allow_redirects=False,
                          headers={"User-Agent": HUMAN_UA, "X-Forwarded-For": "5.5.5.5"})
        assert rr.status_code == 403, f"expected 403, got {rr.status_code}: {rr.text[:200]}"

    def test_allowlist_overrides(self, sess):
        alias = f"ipa{uuid.uuid4().hex[:8]}"
        sess.post(f"{API}/links", json={"name": "IPA", "destination_url": "https://example.com", "alias": alias})
        # allowlist a DC ip and enable block_datacenter — allow should override
        sess.patch(f"{API}/links/{sess.get(f'{API}/links').json()['items'][0]['id']}/protection",
                   json={"enabled": True, "block_datacenter": True})
        sess.post(f"{API}/security/ip-rules", json={"list_type": "allow", "value": DC_IP})
        time.sleep(16)
        rr = requests.get(f"{API}/r/{alias}", allow_redirects=False,
                          headers={"User-Agent": HUMAN_UA, "X-Forwarded-For": DC_IP})
        assert rr.status_code == 302


# --------------------- Per-link Protection --------------------- #
class TestPerLinkProtection:
    def test_defaults_and_patch(self, sess):
        r = sess.post(f"{API}/links", json={"name": "P", "destination_url": "https://example.com"})
        lid = r.json()["id"]
        d = sess.get(f"{API}/links/{lid}/protection").json()
        assert d["enabled"] is False
        assert d["block_action"] == "fallback"

        p = sess.patch(f"{API}/links/{lid}/protection", json={
            "enabled": True, "block_datacenter": True, "block_action": "fallback",
            "block_redirect_url": "https://safe.example.com/fallback",
        })
        assert p.status_code == 200
        assert p.json()["enabled"] is True
        assert p.json()["block_datacenter"] is True

    def test_bad_block_action(self, sess):
        r = sess.post(f"{API}/links", json={"name": "P2", "destination_url": "https://example.com"})
        lid = r.json()["id"]
        p = sess.patch(f"{API}/links/{lid}/protection", json={"block_action": "bogus"})
        assert p.status_code == 400

    def test_datacenter_fallback_302(self, sess):
        alias = f"dc{uuid.uuid4().hex[:8]}"
        r = sess.post(f"{API}/links", json={"name": "DC", "destination_url": "https://real.example.com", "alias": alias})
        lid = r.json()["id"]
        sess.patch(f"{API}/links/{lid}/protection", json={
            "enabled": True, "block_datacenter": True, "block_action": "fallback",
            "block_redirect_url": "https://safe.example.com/fallback",
        })
        # DC IP -> fallback
        rr = requests.get(f"{API}/r/{alias}", allow_redirects=False,
                          headers={"User-Agent": HUMAN_UA, "X-Forwarded-For": DC_IP})
        assert rr.status_code == 302
        assert "safe.example.com" in rr.headers.get("location", "")
        # normal IP -> real
        rh = requests.get(f"{API}/r/{alias}", allow_redirects=False,
                          headers={"User-Agent": HUMAN_UA, "X-Forwarded-For": HUMAN_IP})
        assert rh.status_code == 302
        assert "real.example.com" in rh.headers.get("location", "")


# --------------------- Simulator + new signal fields --------------------- #
class TestSimulator:
    def test_simulate_bot_and_dc(self, sess):
        r = sess.post(f"{API}/security/simulate", json={"ip": DC_IP, "ua": BOT_UA, "country": "US"})
        assert r.status_code == 200
        d = r.json()
        assert d["signals"]["is_bot"] is True
        assert d["signals"]["is_datacenter"] is True
        assert d["risk_score"] >= 50

    def test_is_tor_rule(self, sess):
        r = sess.post(f"{API}/security/rules", json={
            "name": "TEST_tor", "action": "block", "priority": 5,
            "conditions": [{"field": "is_tor", "operator": "equals", "value": True}],
        })
        assert r.status_code == 200


# --------------------- Blocker API --------------------- #
class TestBlockerAPI:
    def _mkkey(self, sess):
        r = sess.post(f"{API}/apikeys", json={"name": "TEST_k"})
        assert r.status_code == 200
        return r.json()

    def test_invalid_apikey(self):
        r = requests.get(f"{API}/v1/blocker", params={"apikey": "bogus", "ip": HUMAN_IP, "ua": HUMAN_UA})
        assert r.status_code == 401

    def test_v1_dc_blocks(self, sess):
        k = self._mkkey(sess)
        raw = k["key"]
        r = requests.get(f"{API}/v1/blocker", params={"apikey": raw, "ip": DC_IP, "ua": HUMAN_UA})
        assert r.status_code == 200
        d = r.json()
        assert d["block"] is True
        assert d["is_datacenter"] is True

    def test_v1_human_pass(self, sess):
        k = self._mkkey(sess)
        r = requests.get(f"{API}/v1/blocker", params={"apikey": k["key"], "ip": HUMAN_IP, "ua": HUMAN_UA})
        assert r.status_code == 200
        assert r.json()["block"] is False

    def test_v2_echoes(self, sess):
        k = self._mkkey(sess)
        r = requests.get(f"{API}/v2/blocker", params={
            "apikey": k["key"], "ip": HUMAN_IP, "ua": HUMAN_UA,
            "url": "https://foo.example/x", "reff": "https://ref.example",
        })
        assert r.status_code == 200
        d = r.json()
        assert d["url"] == "https://foo.example/x"
        assert d["reff"] == "https://ref.example"

    def test_request_count_increments(self, sess):
        k = self._mkkey(sess)
        for _ in range(3):
            requests.get(f"{API}/v1/blocker", params={"apikey": k["key"], "ip": HUMAN_IP, "ua": HUMAN_UA})
        lst = sess.get(f"{API}/apikeys").json()["items"]
        row = next(x for x in lst if x["id"] == k["id"])
        assert row["request_count"] >= 3


# --------------------- Admin panel --------------------- #
class TestAdmin:
    def test_non_admin_forbidden(self, sess):
        for path in ["overview", "security-events", "users", "workspaces", "api-usage", "global-blocklist"]:
            r = sess.get(f"{API}/admin/{path}")
            assert r.status_code == 403, f"{path} -> {r.status_code}"

    def test_overview(self, admin_sess):
        r = admin_sess.get(f"{API}/admin/overview")
        assert r.status_code == 200
        d = r.json()
        for k in ["users", "workspaces", "links", "qr", "events", "feeds"]:
            assert k in d

    def test_lists(self, admin_sess):
        for p in ["security-events", "users", "workspaces", "api-usage"]:
            r = admin_sess.get(f"{API}/admin/{p}")
            assert r.status_code == 200, f"{p} {r.status_code}"
            assert "items" in r.json()

    def test_global_blocklist_crud(self, admin_sess):
        # bad
        rb = admin_sess.post(f"{API}/admin/global-blocklist", json={"value": "nope"})
        assert rb.status_code == 400
        # good
        r = admin_sess.post(f"{API}/admin/global-blocklist", json={"value": "9.9.9.9", "note": "TEST"})
        assert r.status_code == 200
        entry_id = r.json()["id"]
        lst = admin_sess.get(f"{API}/admin/global-blocklist").json()
        assert any(x["id"] == entry_id for x in lst["items"])
        rd = admin_sess.delete(f"{API}/admin/global-blocklist/{entry_id}")
        assert rd.status_code == 200


# --------------------- Regression: default bot challenge --------------------- #
class TestRegressionChallenge:
    def test_bot_challenge_default(self, sess):
        alias = f"chd{uuid.uuid4().hex[:8]}"
        sess.post(f"{API}/links", json={"name": "chd", "destination_url": "https://example.com/dest", "alias": alias})
        r = requests.get(f"{API}/r/{alias}", allow_redirects=False,
                         headers={"User-Agent": BOT_UA, "X-Forwarded-For": HUMAN_IP})
        # Bot UA yields is_bot true (risk 50) -> challenge default
        assert r.status_code == 200
        assert "mg_ch" in r.text
