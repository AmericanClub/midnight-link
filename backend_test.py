#!/usr/bin/env python3
"""
Backend API tests for Midnight Link async webhook processing + regression.

Tests the fix for payment webhook timeouts: both /api/wallet/mayar/webhook and
/api/wallet/klikqris/webhook now acknowledge immediately (<1s) and process in
background, preventing provider timeout errors.
"""
import time
import requests

# Base URL from frontend/.env REACT_APP_BACKEND_URL
BASE_URL = "https://dev-continue-44.preview.emergentagent.com/api"

# Admin credentials from test_credentials.md
ADMIN_EMAIL = "admin@midgate.co"
ADMIN_PASSWORD = "Admin123!"


def test_klikqris_webhook_valid_order():
    """Test 1: POST /api/wallet/klikqris/webhook with valid payload (non-matching order_id)
    
    Expected: HTTP 200 with {"ok":true,"queued":true}, response time <5s (ideally <1s)
    """
    print("\n=== Test 1: KlikQRIS webhook with valid order_id ===")
    url = f"{BASE_URL}/wallet/klikqris/webhook"
    payload = {"order_id": "regress-test-nomatch-001", "status": "PAID"}
    
    start = time.time()
    resp = requests.post(url, json=payload, timeout=10)
    elapsed = time.time() - start
    
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    print(f"Latency: {elapsed:.3f}s")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data.get("ok") is True, f"Expected ok=true, got {data}"
    assert data.get("queued") is True, f"Expected queued=true, got {data}"
    assert elapsed < 5.0, f"Response too slow: {elapsed:.3f}s (should be <5s)"
    
    if elapsed < 1.0:
        print(f"✅ PASS: Fast response ({elapsed:.3f}s < 1s)")
    else:
        print(f"⚠️  PASS but slow: {elapsed:.3f}s (acceptable but >1s)")
    
    return True


def test_klikqris_webhook_no_order_id():
    """Test 2: POST /api/wallet/klikqris/webhook with empty body (no order_id)
    
    Expected: HTTP 200 with {"ok":true,"ignored":true}
    """
    print("\n=== Test 2: KlikQRIS webhook with no order_id ===")
    url = f"{BASE_URL}/wallet/klikqris/webhook"
    payload = {}
    
    start = time.time()
    resp = requests.post(url, json=payload, timeout=10)
    elapsed = time.time() - start
    
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    print(f"Latency: {elapsed:.3f}s")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data.get("ok") is True, f"Expected ok=true, got {data}"
    assert data.get("ignored") is True, f"Expected ignored=true, got {data}"
    
    print(f"✅ PASS: Correctly ignored empty webhook")
    return True


def test_klikqris_webhook_malformed_json():
    """Test 3: POST /api/wallet/klikqris/webhook with malformed JSON
    
    Expected: HTTP 400 (Invalid JSON)
    """
    print("\n=== Test 3: KlikQRIS webhook with malformed JSON ===")
    url = f"{BASE_URL}/wallet/klikqris/webhook"
    
    start = time.time()
    resp = requests.post(
        url,
        data="notjson",  # raw string, not JSON
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    elapsed = time.time() - start
    
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    print(f"Latency: {elapsed:.3f}s")
    
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
    data = resp.json()
    assert "Invalid JSON" in data.get("detail", ""), f"Expected 'Invalid JSON' error, got {data}"
    
    print(f"✅ PASS: Correctly rejected malformed JSON")
    return True


def test_mayar_webhook_valid_event():
    """Test 4: POST /api/wallet/mayar/webhook with payment.received event
    
    Expected: HTTP 200 with {"ok":true,"queued":true}, response time <5s (ideally <1s)
    """
    print("\n=== Test 4: Mayar webhook with payment.received event ===")
    url = f"{BASE_URL}/wallet/mayar/webhook"
    payload = {
        "event": "payment.received",
        "data": {"id": "regress-test-nomatch-002"}
    }
    
    start = time.time()
    resp = requests.post(url, json=payload, timeout=10)
    elapsed = time.time() - start
    
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    print(f"Latency: {elapsed:.3f}s")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data.get("ok") is True, f"Expected ok=true, got {data}"
    assert data.get("queued") is True, f"Expected queued=true, got {data}"
    assert elapsed < 5.0, f"Response too slow: {elapsed:.3f}s (should be <5s)"
    
    if elapsed < 1.0:
        print(f"✅ PASS: Fast response ({elapsed:.3f}s < 1s)")
    else:
        print(f"⚠️  PASS but slow: {elapsed:.3f}s (acceptable but >1s)")
    
    return True


def test_mayar_webhook_non_payment_event():
    """Test 5: POST /api/wallet/mayar/webhook with non-payment.received event
    
    Expected: HTTP 200 with {"ok":true,"ignored":"invoice.created"}
    """
    print("\n=== Test 5: Mayar webhook with non-payment event ===")
    url = f"{BASE_URL}/wallet/mayar/webhook"
    payload = {
        "event": "invoice.created",
        "data": {}
    }
    
    start = time.time()
    resp = requests.post(url, json=payload, timeout=10)
    elapsed = time.time() - start
    
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    print(f"Latency: {elapsed:.3f}s")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data.get("ok") is True, f"Expected ok=true, got {data}"
    assert data.get("ignored") == "invoice.created", f"Expected ignored='invoice.created', got {data}"
    
    print(f"✅ PASS: Correctly ignored non-payment event")
    return True


def test_health_endpoint():
    """Test 6: GET /api/health
    
    Expected: HTTP 200 with {"status":"ok"}
    """
    print("\n=== Test 6: Health endpoint ===")
    url = f"{BASE_URL}/health"
    
    resp = requests.get(url, timeout=10)
    
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data.get("status") == "ok", f"Expected status=ok, got {data}"
    
    print(f"✅ PASS: Health check OK")
    return True


def test_admin_login():
    """Test 7: POST /api/auth/login with admin credentials
    
    Expected: HTTP 200 with user data and auth cookies
    Returns: (session, user_data)
    """
    print("\n=== Test 7: Admin login ===")
    url = f"{BASE_URL}/auth/login"
    payload = {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    
    # Use a session to persist cookies
    session = requests.Session()
    resp = session.post(url, json=payload, timeout=10)
    
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text[:200]}...")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "user" in data, f"Expected user in response, got {data}"
    
    user = data["user"]
    
    # Verify cookies were set
    cookies = session.cookies.get_dict()
    assert "access_token" in cookies or "refresh_token" in cookies, \
        f"Expected auth cookies, got {cookies}"
    
    print(f"✅ PASS: Admin login successful (role={user.get('role')})")
    return session, user


def test_auth_me(session):
    """Test 8: GET /api/auth/me with admin session
    
    Expected: HTTP 200 with user data, role=admin
    """
    print("\n=== Test 8: Auth /me endpoint ===")
    url = f"{BASE_URL}/auth/me"
    
    resp = session.get(url, timeout=10)
    
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data.get("user", {}).get("role") == "admin", f"Expected role=admin, got {data}"
    
    print(f"✅ PASS: Auth /me returns admin user")
    return True


def test_wallet_summary(session):
    """Test 9: GET /api/wallet/summary with admin session
    
    Expected: HTTP 200 with wallet data including rupiah_per_credit, bonus_percent, min_topup, balance
    """
    print("\n=== Test 9: Wallet summary endpoint ===")
    url = f"{BASE_URL}/wallet/summary"
    
    resp = session.get(url, timeout=10)
    
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    
    # Verify expected fields
    assert "balance" in data, f"Expected balance in response, got {data}"
    assert "rupiah_per_credit" in data, f"Expected rupiah_per_credit in response, got {data}"
    assert "bonus_percent" in data, f"Expected bonus_percent in response, got {data}"
    assert "min_topup" in data, f"Expected min_topup in response, got {data}"
    
    print(f"✅ PASS: Wallet summary OK (balance={data.get('balance')}, rpc={data.get('rupiah_per_credit')})")
    return True


def test_admin_overview(session):
    """Test 10: GET /api/admin/overview with admin session
    
    Expected: HTTP 200 with admin overview data
    """
    print("\n=== Test 10: Admin overview endpoint ===")
    url = f"{BASE_URL}/admin/overview"
    
    resp = session.get(url, timeout=10)
    
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    
    # Just verify it returns data without errors
    print(f"✅ PASS: Admin overview OK")
    return True


def main():
    """Run all tests and report results"""
    print("=" * 80)
    print("ASYNC WEBHOOK PROCESSING + REGRESSION TEST SUITE")
    print("=" * 80)
    
    results = []
    
    # Webhook tests (no auth required)
    try:
        results.append(("KlikQRIS webhook (valid order)", test_klikqris_webhook_valid_order()))
    except Exception as e:
        print(f"❌ FAIL: {e}")
        results.append(("KlikQRIS webhook (valid order)", False))
    
    try:
        results.append(("KlikQRIS webhook (no order_id)", test_klikqris_webhook_no_order_id()))
    except Exception as e:
        print(f"❌ FAIL: {e}")
        results.append(("KlikQRIS webhook (no order_id)", False))
    
    try:
        results.append(("KlikQRIS webhook (malformed JSON)", test_klikqris_webhook_malformed_json()))
    except Exception as e:
        print(f"❌ FAIL: {e}")
        results.append(("KlikQRIS webhook (malformed JSON)", False))
    
    try:
        results.append(("Mayar webhook (payment.received)", test_mayar_webhook_valid_event()))
    except Exception as e:
        print(f"❌ FAIL: {e}")
        results.append(("Mayar webhook (payment.received)", False))
    
    try:
        results.append(("Mayar webhook (non-payment event)", test_mayar_webhook_non_payment_event()))
    except Exception as e:
        print(f"❌ FAIL: {e}")
        results.append(("Mayar webhook (non-payment event)", False))
    
    # Regression tests (require auth)
    try:
        results.append(("Health endpoint", test_health_endpoint()))
    except Exception as e:
        print(f"❌ FAIL: {e}")
        results.append(("Health endpoint", False))
    
    session = None
    try:
        session, user = test_admin_login()
        results.append(("Admin login", True))
    except Exception as e:
        print(f"❌ FAIL: {e}")
        results.append(("Admin login", False))
    
    if session:
        try:
            results.append(("Auth /me", test_auth_me(session)))
        except Exception as e:
            print(f"❌ FAIL: {e}")
            results.append(("Auth /me", False))
        
        try:
            results.append(("Wallet summary", test_wallet_summary(session)))
        except Exception as e:
            print(f"❌ FAIL: {e}")
            results.append(("Wallet summary", False))
        
        try:
            results.append(("Admin overview", test_admin_overview(session)))
        except Exception as e:
            print(f"❌ FAIL: {e}")
            results.append(("Admin overview", False))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())
