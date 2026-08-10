"""Iteration 20 — KlikQRIS gateway integration + Mayar regression.

Covers:
- Wallet summary exposes active_gateway/gateway_ready
- Mayar top-up still works (routing + pending status)
- Admin payment-config GET returns klikqris block; PUT persists creds masked
- Active gateway switch (mayar<->klikqris, invalid -> 400)
- KlikQRIS routing (topup returns 502 with dummy creds, NOT 503)
- Admin test endpoint graceful for klikqris/mayar
- KlikQRIS webhook unmatched + invalid JSON
- Regression: /api/billing/passes 5 durations x 6 requests
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://link-midnight-design.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@midgate.co"
ADMIN_PASSWORD = "Admin123!"
MEMBER_EMAIL = "member@midnightlink.link"
MEMBER_PASSWORD = "Member123!"


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def member_session():
    return _login(MEMBER_EMAIL, MEMBER_PASSWORD)


@pytest.fixture(scope="module", autouse=True)
def _restore_mayar_after_all():
    """Ensure active gateway is left as 'mayar' even if tests fail."""
    yield
    try:
        s = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
        s.put(f"{BASE_URL}/api/admin/payment-config", json={"active_gateway": "mayar"}, timeout=30)
    except Exception as e:
        print(f"restore failed: {e}")


# ---------- wallet summary ----------
def test_wallet_summary_active_gateway(member_session):
    r = member_session.get(f"{BASE_URL}/api/wallet/summary", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "active_gateway" in data
    assert "gateway_ready" in data
    assert data["active_gateway"] in ("mayar", "klikqris")


# ---------- admin payment-config ----------
def test_payment_config_get(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/admin/payment-config", timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("gateway", "klikqris", "active_gateway", "credits", "payments"):
        assert k in d, f"missing {k}"
    kq = d["klikqris"]
    assert kq["provider"] == "klikqris"
    assert "api_key_set" in kq and "merchant_id_set" in kq and "source" in kq


def test_payment_config_put_klikqris(admin_session):
    r = admin_session.put(
        f"{BASE_URL}/api/admin/payment-config",
        json={"klikqris_api_key": "testkey123", "klikqris_merchant_id": "178628431726"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    kq = d["klikqris"]
    assert kq["api_key_set"] is True
    assert kq["merchant_id_set"] is True
    assert kq["source"] == "db"
    # masked and never plaintext
    masked = kq.get("api_key_masked") or ""
    assert "testkey123" not in masked
    assert masked.endswith("y123")  # last 4
    # ensure full key not leaked anywhere in response
    body = r.text
    assert "testkey123" not in body


def test_active_gateway_invalid(admin_session):
    r = admin_session.put(
        f"{BASE_URL}/api/admin/payment-config", json={"active_gateway": "bogus"}, timeout=30
    )
    assert r.status_code == 400, r.text


def test_active_gateway_switch(admin_session, member_session):
    r = admin_session.put(
        f"{BASE_URL}/api/admin/payment-config", json={"active_gateway": "klikqris"}, timeout=30
    )
    assert r.status_code == 200
    assert r.json()["active_gateway"] == "klikqris"

    r2 = member_session.get(f"{BASE_URL}/api/wallet/summary", timeout=30)
    assert r2.status_code == 200
    assert r2.json()["active_gateway"] == "klikqris"

    # switch back
    r3 = admin_session.put(
        f"{BASE_URL}/api/admin/payment-config", json={"active_gateway": "mayar"}, timeout=30
    )
    assert r3.status_code == 200
    assert r3.json()["active_gateway"] == "mayar"


# ---------- Mayar regression: topup ----------
def test_topup_mayar_regression(admin_session, member_session):
    # ensure mayar is active
    admin_session.put(f"{BASE_URL}/api/admin/payment-config", json={"active_gateway": "mayar"}, timeout=30)
    r = member_session.post(f"{BASE_URL}/api/wallet/topup", json={"amount": 50000}, timeout=45)
    assert r.status_code == 200, f"topup failed: {r.status_code} {r.text[:300]}"
    d = r.json()
    assert d.get("gateway") == "mayar"
    assert d.get("payment_url")
    assert d.get("order_id")
    assert d.get("credits", 0) >= 1

    r2 = member_session.get(f"{BASE_URL}/api/wallet/topup/{d['order_id']}", timeout=30)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2.get("gateway") == "mayar"
    assert d2.get("credited") is False


# ---------- KlikQRIS routing (dummy key => 502, not 503) ----------
def test_topup_klikqris_routing_502(admin_session, member_session):
    # ensure klikqris creds set
    admin_session.put(
        f"{BASE_URL}/api/admin/payment-config",
        json={"klikqris_api_key": "testkey123", "klikqris_merchant_id": "178628431726"},
        timeout=30,
    )
    # switch active gateway
    r0 = admin_session.put(
        f"{BASE_URL}/api/admin/payment-config", json={"active_gateway": "klikqris"}, timeout=30
    )
    assert r0.status_code == 200
    try:
        r = member_session.post(f"{BASE_URL}/api/wallet/topup", json={"amount": 50000}, timeout=60)
        # Dummy key rejected by KlikQRIS -> upstream error mapped to 502
        assert r.status_code == 502, f"expected 502 got {r.status_code}: {r.text[:300]}"
    finally:
        admin_session.put(
            f"{BASE_URL}/api/admin/payment-config", json={"active_gateway": "mayar"}, timeout=30
        )


# ---------- Admin test endpoint ----------
def test_payment_config_test_klikqris(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/admin/payment-config/test?gateway=klikqris", timeout=45)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("gateway") == "klikqris"
    assert d.get("ok") is False
    assert "message" in d


def test_payment_config_test_mayar(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/admin/payment-config/test?gateway=mayar", timeout=45)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("gateway") == "mayar"
    # ok can be true (configured) or false (no key) — but should not crash
    assert "message" in d


# ---------- KlikQRIS webhook ----------
def test_klikqris_webhook_unmatched():
    r = requests.post(
        f"{BASE_URL}/api/wallet/klikqris/webhook",
        json={"order_id": "does-not-exist-xyz-99", "status": "PAID"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("ok") is True
    assert d.get("unmatched") is True


def test_klikqris_webhook_invalid_json():
    r = requests.post(
        f"{BASE_URL}/api/wallet/klikqris/webhook",
        data="not json{{",
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    assert r.status_code == 400


# ---------- Pass system regression ----------
def test_billing_passes_regression(member_session):
    r = member_session.get(f"{BASE_URL}/api/billing/passes", timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    # accept either {"passes":[...]} or {"items":[...]} or list
    passes = d.get("passes") or d.get("items") or d.get("durations") or d
    if isinstance(passes, dict):
        # maybe {days: [options]}
        keys = list(passes.keys())
        assert len(keys) == 5, f"expected 5 durations got {len(keys)}: {keys}"
        for k, v in passes.items():
            assert len(v) == 6, f"duration {k} has {len(v)} options"
    elif isinstance(passes, list):
        assert len(passes) == 5, f"expected 5 durations got {len(passes)}"
        for p in passes:
            opts = p.get("options") or p.get("requests") or p.get("tiers") or []
            assert len(opts) == 6, f"pass {p} has {len(opts)} options"
    else:
        pytest.fail(f"Unexpected shape: {type(passes)}")
