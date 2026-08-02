"""MidGate iteration 6 tests: QR Protection Presets + Country Analytics."""
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


def _rand_email(p="u"):
    return f"TEST_it6_{p}_{uuid.uuid4().hex[:8]}@midgate.io"


@pytest.fixture
def sess():
    s = requests.Session()
    email = _rand_email("u")
    r = s.post(f"{API}/auth/register", json={"name": "It6 U", "email": email, "password": "Passw0rd!"})
    assert r.status_code == 200, r.text
    s.workspace_id = r.json()["current_workspace"]["id"]
    return s


# ------------------------ QR create with preset ------------------------ #
class TestQRCreateWithPreset:
    def test_strict_preset(self, sess):
        r = sess.post(f"{API}/qr", json={
            "name": "TEST_qr_strict", "destination_url": "https://example.com",
            "protection_preset": "strict",
        })
        assert r.status_code == 200, r.text
        qid = r.json()["id"]
        # QR is a link doc: use /links/{id}/protection
        prot = sess.get(f"{API}/links/{qid}/protection")
        assert prot.status_code == 200, prot.text
        d = prot.json()
        assert d["preset"] == "strict"
        assert d["enabled"] is True
        assert d["block_bots"] is True
        assert d["block_tor"] is True
        assert d["block_datacenter"] is True
        assert d["block_proxy_vpn"] is True
        assert d["block_action"] == "block_page"

    def test_moderate_preset(self, sess):
        r = sess.post(f"{API}/qr", json={
            "name": "TEST_qr_mod", "destination_url": "https://example.com",
            "protection_preset": "moderate",
        })
        assert r.status_code == 200, r.text
        qid = r.json()["id"]
        d = sess.get(f"{API}/links/{qid}/protection").json()
        assert d["preset"] == "moderate"
        assert d["enabled"] is True
        assert d["block_datacenter"] is False
        assert d["block_action"] == "fallback"

    def test_off_preset(self, sess):
        r = sess.post(f"{API}/qr", json={
            "name": "TEST_qr_off", "destination_url": "https://example.com",
            "protection_preset": "off",
        })
        assert r.status_code == 200
        qid = r.json()["id"]
        d = sess.get(f"{API}/links/{qid}/protection").json()
        assert d["preset"] == "off"
        assert d["enabled"] is False

    def test_omitted_preset(self, sess):
        r = sess.post(f"{API}/qr", json={
            "name": "TEST_qr_none", "destination_url": "https://example.com",
        })
        assert r.status_code == 200
        qid = r.json()["id"]
        d = sess.get(f"{API}/links/{qid}/protection").json()
        assert d["preset"] == "off"
        assert d["enabled"] is False

    def test_unknown_preset_400(self, sess):
        r = sess.post(f"{API}/qr", json={
            "name": "TEST_qr_bad", "destination_url": "https://example.com",
            "protection_preset": "ultra",
        })
        assert r.status_code == 400


# ------------------------ QR protection PATCH via /links ------------------------ #
class TestQRPatchProtection:
    def test_patch_moderate_on_qr(self, sess):
        r = sess.post(f"{API}/qr", json={
            "name": "TEST_qr_patch", "destination_url": "https://example.com",
        })
        qid = r.json()["id"]
        p = sess.patch(f"{API}/links/{qid}/protection", json={"preset": "moderate"})
        assert p.status_code == 200, p.text
        d = p.json()
        assert d["preset"] == "moderate"
        assert d["enabled"] is True
        assert d["block_datacenter"] is False


# ------------------------ Redirect enforcement ------------------------ #
class TestQRRedirectEnforcement:
    def test_strict_blocks_bot_ua_allows_chrome(self, sess):
        r = sess.post(f"{API}/qr", json={
            "name": "TEST_qr_enf", "destination_url": "https://example.com/dest",
            "protection_preset": "strict",
        })
        assert r.status_code == 200, r.text
        alias = r.json()["alias"]
        # Use a residential Indonesian IP so strict (block_datacenter/proxy_vpn) doesn't
        # reject the Chrome UA case. Bot detection is UA-based only.
        residential_ip = "114.4.5.6"  # ID residential
        # Bot UA -> should NOT 302 to destination
        rb = requests.get(f"{API}/r/{alias}",
                         headers={"User-Agent": "python-requests/2.31.0",
                                  "X-Forwarded-For": residential_ip},
                         allow_redirects=False)
        if rb.status_code in (301, 302, 303, 307, 308):
            loc = rb.headers.get("Location", "")
            assert "example.com/dest" not in loc, f"Bot UA was redirected to destination: {loc}"
        # Also try 'curl' UA
        rb2 = requests.get(f"{API}/r/{alias}",
                          headers={"User-Agent": "curl/8.0.1",
                                   "X-Forwarded-For": residential_ip},
                          allow_redirects=False)
        if rb2.status_code in (301, 302, 303, 307, 308):
            loc = rb2.headers.get("Location", "")
            assert "example.com/dest" not in loc, f"curl UA was redirected to destination: {loc}"
        # Chrome UA from residential IP -> should 302 to destination
        rc = requests.get(f"{API}/r/{alias}",
                          headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                                 "AppleWebKit/537.36 (KHTML, like Gecko) "
                                                 "Chrome/120.0.0.0 Safari/537.36",
                                   "X-Forwarded-For": residential_ip},
                          allow_redirects=False)
        assert rc.status_code in (301, 302, 303, 307, 308), f"Chrome UA got {rc.status_code}"
        assert "example.com" in rc.headers.get("Location", "")


# ------------------------ Country analytics ------------------------ #
class TestCountryAnalytics:
    def test_overview_top_countries_shape(self, sess):
        r = sess.get(f"{API}/analytics/overview")
        assert r.status_code == 200
        d = r.json()
        assert "top_countries" in d
        tc = d["top_countries"]
        assert isinstance(tc, list)
        assert len(tc) <= 8
        for row in tc:
            assert "name" in row
            assert "count" in row
            assert isinstance(row["count"], int)

    def test_geo_end_to_end_id_us(self, sess):
        # Create a smart link (not a QR) to generate clicks
        r = sess.post(f"{API}/links", json={
            "name": "TEST_geo_e2e", "destination_url": "https://example.com",
        })
        assert r.status_code == 200, r.text
        alias = r.json()["alias"]
        chrome_ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/120.0.0.0 Safari/537.36")
        # ID click
        r1 = requests.get(f"{API}/r/{alias}",
                          headers={"User-Agent": chrome_ua, "X-Forwarded-For": "114.4.5.6"},
                          allow_redirects=False)
        assert r1.status_code in (301, 302, 303, 307, 308), r1.status_code
        # US click
        r2 = requests.get(f"{API}/r/{alias}",
                          headers={"User-Agent": chrome_ua, "X-Forwarded-For": "8.8.8.8"},
                          allow_redirects=False)
        assert r2.status_code in (301, 302, 303, 307, 308), r2.status_code
        # give analytics store a beat to persist
        time.sleep(1.5)
        ov = sess.get(f"{API}/analytics/overview").json()
        codes = {row["name"] for row in ov["top_countries"]}
        assert "ID" in codes, f"expected ID in top_countries, got {codes}"
        assert "US" in codes, f"expected US in top_countries, got {codes}"


# ------------------------ QR regression ------------------------ #
class TestQRRegression:
    def test_qr_crud_pause_resume_versioning(self, sess):
        r = sess.post(f"{API}/qr", json={
            "name": "TEST_qr_reg", "destination_url": "https://example.com/a",
        })
        assert r.status_code == 200
        qid = r.json()["id"]
        # list
        lst = sess.get(f"{API}/qr").json()
        assert any(x["id"] == qid for x in lst["items"])
        # pause
        assert sess.post(f"{API}/qr/{qid}/pause").status_code == 200
        # resume
        assert sess.post(f"{API}/qr/{qid}/resume").status_code == 200
        # patch destination -> versioned
        up = sess.patch(f"{API}/qr/{qid}", json={"destination_url": "https://example.com/b"})
        assert up.status_code == 200
        assert up.json()["destination_url"].startswith("https://example.com/b")
        vers = sess.get(f"{API}/qr/{qid}/versions").json()
        assert len(vers["items"]) >= 1
        # delete
        assert sess.delete(f"{API}/qr/{qid}").status_code == 200
