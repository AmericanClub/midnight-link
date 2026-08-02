"""MidGate iteration 5 tests: Protection Presets + Country Geo detection."""
import os
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
    return f"TEST_it5_{p}_{uuid.uuid4().hex[:8]}@midgate.io"


@pytest.fixture
def sess():
    s = requests.Session()
    email = _rand_email("u")
    r = s.post(f"{API}/auth/register", json={"name": "It5 U", "email": email, "password": "Passw0rd!"})
    assert r.status_code == 200, r.text
    s.workspace_id = r.json()["current_workspace"]["id"]
    return s


# ------------------------ Presets endpoint ------------------------ #
class TestPresetsEndpoint:
    def test_list_presets(self, sess):
        r = sess.get(f"{API}/security/presets")
        assert r.status_code == 200
        data = r.json()
        assert "presets" in data
        p = data["presets"]
        for k in ("off", "moderate", "strict"):
            assert k in p, f"missing preset {k}"
            assert "label" in p[k]
            assert "description" in p[k]
        # spot-check values
        assert p["strict"]["enabled"] is True
        assert p["strict"]["block_datacenter"] is True
        assert p["strict"]["block_action"] == "block_page"
        assert p["moderate"]["block_datacenter"] is False
        assert p["moderate"]["block_action"] == "fallback"
        assert p["off"]["enabled"] is False


# ------------------------ Create link with preset ------------------------ #
class TestCreateWithPreset:
    def test_strict_preset(self, sess):
        r = sess.post(f"{API}/links", json={
            "name": "TEST_strict", "destination_url": "https://example.com",
            "protection_preset": "strict",
        })
        assert r.status_code == 200, r.text
        lid = r.json()["id"]
        prot = sess.get(f"{API}/links/{lid}/protection").json()
        assert prot["preset"] == "strict"
        assert prot["enabled"] is True
        assert prot["block_bots"] is True
        assert prot["block_tor"] is True
        assert prot["block_datacenter"] is True
        assert prot["block_proxy_vpn"] is True
        assert prot["block_action"] == "block_page"

    def test_moderate_preset(self, sess):
        r = sess.post(f"{API}/links", json={
            "name": "TEST_mod", "destination_url": "https://example.com",
            "protection_preset": "moderate",
        })
        assert r.status_code == 200, r.text
        lid = r.json()["id"]
        prot = sess.get(f"{API}/links/{lid}/protection").json()
        assert prot["preset"] == "moderate"
        assert prot["enabled"] is True
        assert prot["block_datacenter"] is False
        assert prot["block_action"] == "fallback"

    def test_off_preset(self, sess):
        r = sess.post(f"{API}/links", json={
            "name": "TEST_off", "destination_url": "https://example.com",
            "protection_preset": "off",
        })
        assert r.status_code == 200
        lid = r.json()["id"]
        prot = sess.get(f"{API}/links/{lid}/protection").json()
        assert prot["enabled"] is False
        assert prot["preset"] == "off"

    def test_unknown_preset_400(self, sess):
        r = sess.post(f"{API}/links", json={
            "name": "TEST_bad", "destination_url": "https://example.com",
            "protection_preset": "ultra",
        })
        assert r.status_code == 400


# ------------------------ GET protection preset inference ------------------------ #
class TestGetProtectionPreset:
    def test_legacy_off_inferred(self, sess):
        # Create without preset -> stored protection has preset='off' by default
        r = sess.post(f"{API}/links", json={"name": "TEST_leg", "destination_url": "https://example.com"})
        lid = r.json()["id"]
        prot = sess.get(f"{API}/links/{lid}/protection").json()
        assert prot["preset"] == "off"
        assert prot["enabled"] is False


# ------------------------ PATCH preset transitions ------------------------ #
class TestPatchPreset:
    def test_apply_moderate(self, sess):
        r = sess.post(f"{API}/links", json={"name": "TEST_pm", "destination_url": "https://example.com"})
        lid = r.json()["id"]
        p = sess.patch(f"{API}/links/{lid}/protection", json={"preset": "moderate"})
        assert p.status_code == 200
        d = p.json()
        assert d["preset"] == "moderate"
        assert d["enabled"] is True
        assert d["block_tor"] is True
        assert d["block_datacenter"] is False

    def test_custom_with_override(self, sess):
        r = sess.post(f"{API}/links", json={"name": "TEST_pc", "destination_url": "https://example.com"})
        lid = r.json()["id"]
        p = sess.patch(f"{API}/links/{lid}/protection", json={"preset": "custom", "block_datacenter": True})
        assert p.status_code == 200
        d = p.json()
        assert d["preset"] == "custom"
        assert d["block_datacenter"] is True

    def test_manual_field_switches_to_custom(self, sess):
        # start with strict
        r = sess.post(f"{API}/links", json={
            "name": "TEST_ps", "destination_url": "https://example.com",
            "protection_preset": "strict",
        })
        lid = r.json()["id"]
        p = sess.patch(f"{API}/links/{lid}/protection", json={"block_bots": False})
        assert p.status_code == 200
        d = p.json()
        assert d["preset"] == "custom"
        assert d["block_bots"] is False
        # enabled remains true from strict
        assert d["enabled"] is True


# ------------------------ Country Geo detection ------------------------ #
class TestGeoDetection:
    def test_id_ip(self, sess):
        r = sess.post(f"{API}/security/simulate", json={
            "ip": "114.4.5.6", "country": "Unknown",
            "ua": "Mozilla/5.0 Chrome/120",
        })
        assert r.status_code == 200
        assert r.json()["signals"]["country"] == "ID"

    def test_us_ip(self, sess):
        r = sess.post(f"{API}/security/simulate", json={
            "ip": "8.8.8.8", "country": "Unknown",
            "ua": "Mozilla/5.0 Chrome/120",
        })
        assert r.status_code == 200
        assert r.json()["signals"]["country"] == "US"

    def test_au_ip(self, sess):
        r = sess.post(f"{API}/security/simulate", json={
            "ip": "1.1.1.1", "country": "Unknown",
            "ua": "Mozilla/5.0 Chrome/120",
        })
        assert r.status_code == 200
        assert r.json()["signals"]["country"] == "AU"

    def test_explicit_country_preserved(self, sess):
        r = sess.post(f"{API}/security/simulate", json={
            "ip": "8.8.8.8", "country": "MY",
            "ua": "Mozilla/5.0 Chrome/120",
        })
        assert r.status_code == 200
        assert r.json()["signals"]["country"] == "MY"


# ------------------------ Country blocking via simulate ------------------------ #
class TestCountryBlockingSimulate:
    def test_id_blocked_via_workspace_rule(self, sess):
        # Rules can act on signals.country. Add a rule blocking ID.
        rr = sess.post(f"{API}/security/rules", json={
            "name": "TEST_it5_block_id", "action": "block", "priority": 1,
            "conditions": [{"field": "country", "operator": "equals", "value": "ID"}],
        })
        assert rr.status_code == 200, rr.text
        import time
        time.sleep(16)  # bypass 15s rules cache
        r = sess.post(f"{API}/security/simulate", json={
            "ip": "114.4.5.6", "country": "Unknown",
            "ua": "Mozilla/5.0 Chrome/120",
        })
        assert r.status_code == 200
        d = r.json()
        assert d["signals"]["country"] == "ID"
        assert d["decision"] == "block"


# ------------------------ Regression: link CRUD + pause/resume + simulator ------------------------ #
class TestRegression:
    def test_link_crud_pause_resume(self, sess):
        r = sess.post(f"{API}/links", json={"name": "TEST_reg", "destination_url": "https://example.com"})
        assert r.status_code == 200
        lid = r.json()["id"]
        # list
        lst = sess.get(f"{API}/links").json()
        assert any(x["id"] == lid for x in lst["items"])
        # pause
        pr = sess.post(f"{API}/links/{lid}/pause")
        assert pr.status_code == 200
        assert pr.json()["status"] == "paused"
        # resume
        rs = sess.post(f"{API}/links/{lid}/resume")
        assert rs.status_code == 200
        assert rs.json()["status"] == "active"
        # patch name
        up = sess.patch(f"{API}/links/{lid}", json={"name": "TEST_reg2"})
        assert up.status_code == 200
        assert up.json()["name"] == "TEST_reg2"
        # delete
        dl = sess.delete(f"{API}/links/{lid}")
        assert dl.status_code == 200

    def test_simulator_basic(self, sess):
        r = sess.post(f"{API}/security/simulate", json={
            "ip": "3.5.1.1", "country": "US", "ua": "curl/8.0",
        })
        assert r.status_code == 200
        d = r.json()
        assert d["signals"]["is_bot"] is True
        assert d["signals"]["is_datacenter"] is True
