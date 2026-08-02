"""MidGate iteration 2 tests: Dynamic QR, Traffic Protection, Analytics filters."""
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
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


def _rand_email(p="u"):
    return f"TEST_{p}_{uuid.uuid4().hex[:8]}@midgate.io"


@pytest.fixture
def sess():
    s = requests.Session()
    email = _rand_email("it2")
    r = s.post(f"{API}/auth/register", json={"name": "It2 U", "email": email, "password": "Passw0rd!"})
    assert r.status_code == 200, r.text
    s.workspace_id = r.json()["current_workspace"]["id"]
    return s


@pytest.fixture
def sess_other():
    s = requests.Session()
    email = _rand_email("it2b")
    r = s.post(f"{API}/auth/register", json={"name": "It2 U B", "email": email, "password": "Passw0rd!"})
    assert r.status_code == 200
    s.workspace_id = r.json()["current_workspace"]["id"]
    return s


# -------------------- Dynamic QR -------------------- #
class TestQR:
    def test_qr_create_list_and_hidden_from_links(self, sess):
        alias = f"qr{uuid.uuid4().hex[:8]}"
        payload = {
            "name": "MyQR", "destination_url": "https://example.com/a",
            "alias": alias,
            "style": {"fg_color": "#FF0000", "bg_color": "#FFFFFF", "dots_style": "dots",
                      "corners_style": "extra-rounded", "logo_url": "", "margin": 8,
                      "error_correction": "H"},
        }
        r = sess.post(f"{API}/qr", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["is_qr"] is True
        assert d["short_path"] == f"/api/r/{alias}"
        assert d["style"]["fg_color"] == "#FF0000"
        qr_id = d["id"]

        # list QR contains
        lst = sess.get(f"{API}/qr").json()
        ids = [x["id"] for x in lst["items"]]
        assert qr_id in ids

        # links list does NOT contain QR
        links = sess.get(f"{API}/links").json()
        link_ids = [x["id"] for x in links.get("items", [])]
        assert qr_id not in link_ids

    def test_qr_unsafe_url_400(self, sess):
        r = sess.post(f"{API}/qr", json={"name": "Bad", "destination_url": "javascript:alert(1)"})
        assert r.status_code == 400
        r2 = sess.post(f"{API}/qr", json={"name": "Bad2", "destination_url": "http://127.0.0.1"})
        assert r2.status_code == 400

    def test_qr_dynamic_update_and_versions(self, sess):
        alias = f"qd{uuid.uuid4().hex[:8]}"
        r = sess.post(f"{API}/qr", json={"name": "Dyn", "destination_url": "https://example.com/v1", "alias": alias})
        qr = r.json()
        qr_id = qr["id"]

        # Update dest
        r2 = sess.patch(f"{API}/qr/{qr_id}", json={"destination_url": "https://example.com/v2"})
        assert r2.status_code == 200
        assert r2.json()["destination_url"].startswith("https://example.com/v2")
        assert r2.json()["alias"] == alias  # same alias

        # Versions endpoint
        v = sess.get(f"{API}/qr/{qr_id}/versions").json()
        assert len(v["items"]) >= 1
        assert v["items"][0]["new_destination"].startswith("https://example.com/v2")
        assert v["items"][0]["previous_destination"].startswith("https://example.com/v1")

        # Redirect uses new destination (use real UA to bypass default risk block)
        rr = requests.get(f"{API}/r/{alias}", allow_redirects=False,
                          headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"})
        assert rr.status_code == 302
        assert "v2" in rr.headers.get("location", "")

    def test_qr_pause_resume_delete(self, sess):
        r = sess.post(f"{API}/qr", json={"name": "Pd", "destination_url": "https://example.com"})
        qid = r.json()["id"]
        assert sess.post(f"{API}/qr/{qid}/pause").status_code == 200
        assert sess.post(f"{API}/qr/{qid}/resume").status_code == 200
        assert sess.delete(f"{API}/qr/{qid}").status_code == 200
        assert sess.get(f"{API}/qr/{qid}").status_code == 404


# -------------------- Traffic Protection -------------------- #
class TestSecurity:
    def test_rules_crud(self, sess):
        # create
        r = sess.post(f"{API}/security/rules", json={
            "name": "TEST_rule_1", "action": "block", "priority": 10,
            "conditions": [{"field": "country", "operator": "equals", "value": "XX"}],
        })
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        # list
        lst = sess.get(f"{API}/security/rules").json()
        assert any(x["id"] == rid for x in lst["items"])
        # patch
        rp = sess.patch(f"{API}/security/rules/{rid}", json={
            "name": "TEST_rule_1u", "action": "challenge", "priority": 20, "enabled": False,
            "conditions": [{"field": "country", "operator": "equals", "value": "XX"}],
        })
        assert rp.status_code == 200 and rp.json()["action"] == "challenge"
        # delete
        rd = sess.delete(f"{API}/security/rules/{rid}")
        assert rd.status_code == 200

    def test_simulate(self, sess):
        r = sess.post(f"{API}/security/simulate", json={"is_bot": True})
        assert r.status_code == 200
        d = r.json()
        assert "risk_score" in d and "decision" in d and "reasons" in d
        assert d["risk_score"] > 0

    def test_bot_rule_blocks_redirect(self, sess):
        alias = f"bt{uuid.uuid4().hex[:8]}"
        sess.post(f"{API}/links", json={"name": "Bot Test", "destination_url": "https://example.com", "alias": alias})
        # Create block-bot rule
        sess.post(f"{API}/security/rules", json={
            "name": "TEST_block_bots", "action": "block", "priority": 1,
            "conditions": [{"field": "is_bot", "operator": "equals", "value": True}],
        })
        time.sleep(16)  # bypass 15s rules cache

        # Bot UA -> 403
        rr = requests.get(f"{API}/r/{alias}", allow_redirects=False,
                          headers={"User-Agent": "Googlebot/2.1"})
        assert rr.status_code == 403, f"expected 403 for bot, got {rr.status_code}"

        # Human UA -> 302
        rh = requests.get(f"{API}/r/{alias}", allow_redirects=False,
                          headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"})
        assert rh.status_code == 302, f"expected 302 for human, got {rh.status_code}"

    def test_challenge_flow(self, sess):
        alias = f"ch{uuid.uuid4().hex[:8]}"
        sess.post(f"{API}/links", json={"name": "Ch Test", "destination_url": "https://example.com/dest", "alias": alias})
        sess.post(f"{API}/security/rules", json={
            "name": "TEST_challenge_bots", "action": "challenge", "priority": 1,
            "conditions": [{"field": "is_bot", "operator": "equals", "value": True}],
        })
        time.sleep(16)

        r1 = requests.get(f"{API}/r/{alias}", allow_redirects=False,
                          headers={"User-Agent": "Googlebot/2.1"})
        assert r1.status_code == 200
        assert "mg_ch" in r1.text
        # extract token
        import re
        m = re.search(r"mg_ch=([a-f0-9]+)", r1.text)
        assert m, "challenge token not found in interstitial"
        token = m.group(1)
        r2 = requests.get(f"{API}/r/{alias}?mg_ch={token}", allow_redirects=False,
                          headers={"User-Agent": "Googlebot/2.1"})
        assert r2.status_code == 302
        assert "example.com/dest" in r2.headers.get("location", "")


# -------------------- Analytics filters -------------------- #
class TestAnalyticsFilters:
    def test_overview_with_range_and_compare(self, sess):
        today = datetime.now(timezone.utc).date()
        start = (today - timedelta(days=6)).isoformat()
        end = today.isoformat()
        r = sess.get(f"{API}/analytics/overview", params={"start": start, "end": end, "compare": "true"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert "total_clicks" in d
        assert "previous" in d
        assert "total_clicks" in d["previous"]

    def test_link_analytics_range_and_compare(self, sess):
        alias = f"an{uuid.uuid4().hex[:8]}"
        r = sess.post(f"{API}/links", json={"name": "A", "destination_url": "https://example.com", "alias": alias})
        lid = r.json()["id"]
        requests.get(f"{API}/r/{alias}", allow_redirects=False,
                     headers={"User-Agent": "Mozilla/5.0 Chrome/120"})
        time.sleep(2)
        today = datetime.now(timezone.utc).date()
        start = (today - timedelta(days=6)).isoformat()
        end = today.isoformat()
        ra = sess.get(f"{API}/analytics/links/{lid}", params={"start": start, "end": end, "compare": "true"})
        assert ra.status_code == 200
        d = ra.json()
        assert d["total_clicks"] >= 1
        assert "previous" in d

    def test_export_csv_ok(self, sess):
        alias = f"ex{uuid.uuid4().hex[:8]}"
        r = sess.post(f"{API}/links", json={"name": "E", "destination_url": "https://example.com", "alias": alias})
        lid = r.json()["id"]
        requests.get(f"{API}/r/{alias}", allow_redirects=False,
                     headers={"User-Agent": "Mozilla/5.0 Chrome/120"})
        time.sleep(2)
        # Note: server-side generates CSV; use plain session with cookies (no ws header needed)
        rc = sess.get(f"{API}/analytics/links/{lid}/export.csv")
        assert rc.status_code == 200
        assert "text/csv" in rc.headers.get("content-type", "")
        body = rc.text
        assert body.startswith("occurred_at,country,device,browser,os,referrer,is_bot,risk_score,decision,challenge_result,visitor_id")

    def test_export_csv_non_member_404(self, sess, sess_other):
        alias = f"exn{uuid.uuid4().hex[:8]}"
        r = sess.post(f"{API}/links", json={"name": "E", "destination_url": "https://example.com", "alias": alias})
        lid = r.json()["id"]
        rc = sess_other.get(f"{API}/analytics/links/{lid}/export.csv")
        assert rc.status_code == 404
