"""Iteration 14 tests: MidGate moderate vs strict preset gating + blocked_count."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://link-midnight-design.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@midgate.io"
ADMIN_PWD = "Admin123!"

CHROME_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
BOT_UA = "python-requests/2.31"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PWD})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    # try to also set Authorization
    tok = r.json().get("access_token") or r.json().get("token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


def test_moderate_allows_chrome():
    r = requests.get(f"{API}/r/Gn2XuS", headers={"User-Agent": CHROME_UA}, allow_redirects=False)
    print("moderate+chrome:", r.status_code, r.headers.get("location"))
    assert r.status_code in (301, 302, 303, 307, 308), f"expected redirect, got {r.status_code} body={r.text[:200]}"


def test_moderate_blocks_bot():
    r = requests.get(f"{API}/r/Gn2XuS", headers={"User-Agent": BOT_UA}, allow_redirects=False)
    print("moderate+bot:", r.status_code)
    assert r.status_code != 302, f"bot should be blocked, got redirect"


def test_strict_blocks_chrome():
    r = requests.get(f"{API}/r/HP14cx", headers={"User-Agent": CHROME_UA}, allow_redirects=False)
    print("strict+chrome:", r.status_code)
    assert r.status_code != 302, f"strict should still block proxy IP, got redirect"


def test_links_api_blocked_count(admin_session):
    r = admin_session.get(f"{API}/links")
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", data.get("links", []))
    hp = next((x for x in items if x.get("alias") == "HP14cx"), None)
    assert hp is not None, f"HP14cx not found in admin's links. aliases={[x.get('alias') for x in items]}"
    print("HP14cx:", hp)
    assert "blocked_count" in hp, f"blocked_count missing: keys={list(hp.keys())}"
    assert "challenged_count" in hp, f"challenged_count missing: keys={list(hp.keys())}"
    assert hp.get("click_count", 0) == 0, f"click_count expected 0 got {hp.get('click_count')}"
    assert hp.get("blocked_count") == 3, f"blocked_count expected 3 got {hp.get('blocked_count')}"
