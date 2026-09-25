#!/usr/bin/env python3
"""
Regression test suite for Midnight Link backend after adding single-flight reconciler lock
(partner_pay.py: _acquire_reconciler_lock + run_reconciler now acquires MongoDB lock before each 60s cycle).

Tests:
1. GET /api/health -> 200 {status:ok, service:core-api}
2. POST /api/auth/login (admin) -> 200 + token; GET /api/auth/me -> 200 role=admin
3. GET /api/wallet/summary (auth) -> 200 with balance, rupiah_per_credit, bonus_percent, min_topup
4. GET /api/admin/overview (auth) -> 200 stats
5. Webhook fast-ack: POST /api/wallet/klikqris/webhook -> 200 {ok:true,queued:true} in <2s
6. Webhook fast-ack: POST /api/wallet/mayar/webhook -> 200 {ok:true,queued:true} in <2s
"""
import os
import sys
import time
import json
import requests
from typing import Dict, Any

# Backend URL from frontend/.env
BACKEND_URL = os.getenv("REACT_APP_BACKEND_URL", "https://dev-continue-44.preview.emergentagent.com")
API_BASE = f"{BACKEND_URL}/api"

# Admin credentials from test_credentials.md
ADMIN_EMAIL = "admin@midgate.co"
ADMIN_PASSWORD = "Admin123!"

# Test results
results = []
session = requests.Session()


def log_test(name: str, passed: bool, details: str = "", response_time: float = 0):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    results.append({
        "name": name,
        "passed": passed,
        "details": details,
        "response_time": response_time
    })
    print(f"{status} | {name}")
    if details:
        print(f"    {details}")
    if response_time > 0:
        print(f"    Response time: {response_time:.3f}s")
    print()


def test_health():
    """Test 1: GET /api/health -> 200 {status:ok, service:core-api}"""
    try:
        start = time.time()
        resp = session.get(f"{API_BASE}/health", timeout=10)
        elapsed = time.time() - start
        
        if resp.status_code != 200:
            log_test("Health Check", False, f"Expected 200, got {resp.status_code}", elapsed)
            return False
        
        data = resp.json()
        if data.get("status") != "ok" or data.get("service") != "core-api":
            log_test("Health Check", False, f"Unexpected response: {data}", elapsed)
            return False
        
        log_test("Health Check", True, f"Response: {data}", elapsed)
        return True
    except Exception as e:
        log_test("Health Check", False, f"Exception: {e}")
        return False


def test_admin_auth():
    """Test 2: POST /api/auth/login (admin) -> 200 + token; GET /api/auth/me -> 200 role=admin"""
    try:
        # Login
        start = time.time()
        resp = session.post(
            f"{API_BASE}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        elapsed = time.time() - start
        
        if resp.status_code != 200:
            log_test("Admin Login", False, f"Login failed: {resp.status_code} - {resp.text}", elapsed)
            return False
        
        data = resp.json()
        if not data.get("user") or data["user"].get("role") != "admin":
            log_test("Admin Login", False, f"Expected admin role, got: {data}", elapsed)
            return False
        
        log_test("Admin Login", True, f"Logged in as {data['user'].get('email')}", elapsed)
        
        # Verify /me endpoint
        start = time.time()
        resp = session.get(f"{API_BASE}/auth/me", timeout=10)
        elapsed = time.time() - start
        
        if resp.status_code != 200:
            log_test("Admin /me Check", False, f"Expected 200, got {resp.status_code}", elapsed)
            return False
        
        data = resp.json()
        user = data.get("user", {})
        if user.get("role") != "admin":
            log_test("Admin /me Check", False, f"Expected role=admin, got: {data}", elapsed)
            return False
        
        log_test("Admin /me Check", True, f"Role: {user.get('role')}, Email: {user.get('email')}", elapsed)
        return True
    except Exception as e:
        log_test("Admin Auth", False, f"Exception: {e}")
        return False


def test_wallet_summary():
    """Test 3: GET /api/wallet/summary (auth) -> 200 with balance, rupiah_per_credit, bonus_percent, min_topup"""
    try:
        start = time.time()
        resp = session.get(f"{API_BASE}/wallet/summary", timeout=10)
        elapsed = time.time() - start
        
        if resp.status_code != 200:
            log_test("Wallet Summary", False, f"Expected 200, got {resp.status_code} - {resp.text}", elapsed)
            return False
        
        data = resp.json()
        required_fields = ["balance", "rupiah_per_credit", "bonus_percent", "min_topup"]
        missing = [f for f in required_fields if f not in data]
        
        if missing:
            log_test("Wallet Summary", False, f"Missing fields: {missing}. Response: {data}", elapsed)
            return False
        
        log_test("Wallet Summary", True, 
                f"balance={data['balance']}, rupiah_per_credit={data['rupiah_per_credit']}, "
                f"bonus_percent={data['bonus_percent']}, min_topup={data['min_topup']}", elapsed)
        return True
    except Exception as e:
        log_test("Wallet Summary", False, f"Exception: {e}")
        return False


def test_admin_overview():
    """Test 4: GET /api/admin/overview (auth) -> 200 stats"""
    try:
        start = time.time()
        resp = session.get(f"{API_BASE}/admin/overview", timeout=10)
        elapsed = time.time() - start
        
        if resp.status_code != 200:
            log_test("Admin Overview", False, f"Expected 200, got {resp.status_code} - {resp.text}", elapsed)
            return False
        
        data = resp.json()
        # Just verify it returns some stats structure
        if not isinstance(data, dict):
            log_test("Admin Overview", False, f"Expected dict, got: {type(data)}", elapsed)
            return False
        
        log_test("Admin Overview", True, f"Stats returned: {len(data)} fields", elapsed)
        return True
    except Exception as e:
        log_test("Admin Overview", False, f"Exception: {e}")
        return False


def test_klikqris_webhook_fast_ack():
    """Test 5: POST /api/wallet/klikqris/webhook -> 200 {ok:true,queued:true} in <2s"""
    try:
        payload = {
            "order_id": "lock-regress-1",
            "status": "PAID"
        }
        
        start = time.time()
        resp = session.post(
            f"{API_BASE}/wallet/klikqris/webhook",
            json=payload,
            timeout=10
        )
        elapsed = time.time() - start
        
        if resp.status_code != 200:
            log_test("KlikQRIS Webhook Fast-Ack", False, 
                    f"Expected 200, got {resp.status_code} - {resp.text}", elapsed)
            return False
        
        data = resp.json()
        if not (data.get("ok") is True and data.get("queued") is True):
            log_test("KlikQRIS Webhook Fast-Ack", False, 
                    f"Expected {{ok:true,queued:true}}, got: {data}", elapsed)
            return False
        
        if elapsed >= 2.0:
            log_test("KlikQRIS Webhook Fast-Ack", False, 
                    f"Response took {elapsed:.3f}s (>= 2s requirement)", elapsed)
            return False
        
        log_test("KlikQRIS Webhook Fast-Ack", True, 
                f"Response: {data}, Time: {elapsed:.3f}s (< 2s ✓)", elapsed)
        return True
    except Exception as e:
        log_test("KlikQRIS Webhook Fast-Ack", False, f"Exception: {e}")
        return False


def test_mayar_webhook_fast_ack():
    """Test 6: POST /api/wallet/mayar/webhook -> 200 {ok:true,queued:true} in <2s"""
    try:
        payload = {
            "event": "payment.received",
            "data": {
                "id": "lock-regress-2"
            }
        }
        
        start = time.time()
        resp = session.post(
            f"{API_BASE}/wallet/mayar/webhook",
            json=payload,
            timeout=10
        )
        elapsed = time.time() - start
        
        if resp.status_code != 200:
            log_test("Mayar Webhook Fast-Ack", False, 
                    f"Expected 200, got {resp.status_code} - {resp.text}", elapsed)
            return False
        
        data = resp.json()
        if not (data.get("ok") is True and data.get("queued") is True):
            log_test("Mayar Webhook Fast-Ack", False, 
                    f"Expected {{ok:true,queued:true}}, got: {data}", elapsed)
            return False
        
        if elapsed >= 2.0:
            log_test("Mayar Webhook Fast-Ack", False, 
                    f"Response took {elapsed:.3f}s (>= 2s requirement)", elapsed)
            return False
        
        log_test("Mayar Webhook Fast-Ack", True, 
                f"Response: {data}, Time: {elapsed:.3f}s (< 2s ✓)", elapsed)
        return True
    except Exception as e:
        log_test("Mayar Webhook Fast-Ack", False, f"Exception: {e}")
        return False


def main():
    print("=" * 80)
    print("MIDNIGHT LINK BACKEND REGRESSION TEST")
    print("Testing single-flight reconciler lock (multi-worker dedupe)")
    print("=" * 80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"API Base: {API_BASE}")
    print(f"Admin: {ADMIN_EMAIL}")
    print("=" * 80)
    print()
    
    # Run all tests
    test_health()
    test_admin_auth()
    test_wallet_summary()
    test_admin_overview()
    test_klikqris_webhook_fast_ack()
    test_mayar_webhook_fast_ack()
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed
    
    print(f"Total: {len(results)} tests")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print()
    
    if failed > 0:
        print("FAILED TESTS:")
        for r in results:
            if not r["passed"]:
                print(f"  - {r['name']}: {r['details']}")
        print()
    
    print("=" * 80)
    
    # Exit code
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
