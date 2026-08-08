#!/usr/bin/env python3
"""
Backend API tests for Admin Payments feature (Midnight Link).

CRITICAL SAFETY GUARDRAILS (real money/keys involved):
- DO NOT set/overwrite mayar_api_key via PUT (would clobber real working Mayar key)
- DO NOT POST /api/wallet/topup with valid amount (creates REAL Mayar invoice)
- If changing mayar_base_url, set it back to "https://api.mayar.id/hl/v1" afterwards
- At end, reset credit settings to rupiah_per_credit=1000, bonus_percent=0, min_topup=10000
"""
import os
import sys
import requests
import json
from typing import Dict, Any

# Backend URL from frontend/.env
BACKEND_URL = os.getenv("REACT_APP_BACKEND_URL", "https://link-midnight-design.preview.emergentagent.com")
API_BASE = f"{BACKEND_URL}/api"

# Test credentials
ADMIN_EMAIL = "admin@midgate.co"
ADMIN_PASSWORD = "Admin123!"

# Test state
admin_token = None
normal_user_token = None
normal_user_workspace_id = None
test_user_email = None


def log(msg: str, level="INFO"):
    """Simple logger."""
    print(f"[{level}] {msg}")


def register_user(name: str, email: str, password: str) -> Dict[str, Any]:
    """Register a new user and return response."""
    resp = requests.post(f"{API_BASE}/auth/register", json={
        "name": name,
        "email": email,
        "password": password
    })
    return resp


def login(email: str, password: str) -> Dict[str, Any]:
    """Login and return response."""
    resp = requests.post(f"{API_BASE}/auth/login", json={
        "email": email,
        "password": password
    })
    return resp


def get_headers(token: str) -> Dict[str, str]:
    """Return headers with auth token."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


def test_admin_login():
    """Test 1: Admin login."""
    global admin_token
    log("TEST 1: Admin login")
    resp = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if resp.status_code != 200:
        log(f"FAIL: Admin login failed with {resp.status_code}: {resp.text}", "ERROR")
        sys.exit(1)
    data = resp.json()
    admin_token = resp.cookies.get("access_token")
    if not admin_token:
        log("FAIL: No access_token cookie in response", "ERROR")
        sys.exit(1)
    log(f"PASS: Admin logged in successfully (role={data.get('user', {}).get('role')})")
    return admin_token


def test_get_payment_config():
    """Test 2: GET /api/admin/payment-config (as admin)."""
    log("TEST 2: GET /api/admin/payment-config (as admin)")
    resp = requests.get(f"{API_BASE}/admin/payment-config", cookies={"access_token": admin_token})
    if resp.status_code != 200:
        log(f"FAIL: GET payment-config returned {resp.status_code}: {resp.text}", "ERROR")
        return False
    
    data = resp.json()
    log(f"Response: {json.dumps(data, indent=2)}")
    
    # Verify structure
    required_keys = ["payments", "credits", "gateway"]
    for key in required_keys:
        if key not in data:
            log(f"FAIL: Missing key '{key}' in response", "ERROR")
            return False
    
    # Verify payments keys
    payments = data["payments"]
    if "topup_enabled" not in payments:
        log("FAIL: Missing 'topup_enabled' in payments", "ERROR")
        return False
    
    # Verify credits keys
    credits = data["credits"]
    required_credit_keys = ["rupiah_per_credit", "bonus_percent", "min_topup"]
    for key in required_credit_keys:
        if key not in credits:
            log(f"FAIL: Missing '{key}' in credits", "ERROR")
            return False
    
    # Verify gateway keys
    gateway = data["gateway"]
    required_gateway_keys = ["provider", "base_url", "api_key_set", "api_key_masked", "webhook_token_set", "source"]
    for key in required_gateway_keys:
        if key not in gateway:
            log(f"FAIL: Missing '{key}' in gateway", "ERROR")
            return False
    
    # CRITICAL: Verify API key is masked
    api_key_masked = gateway.get("api_key_masked", "")
    if api_key_masked and not api_key_masked.startswith("••••"):
        log(f"FAIL: API key is NOT masked properly: {api_key_masked}", "ERROR")
        return False
    
    # CRITICAL: Verify full API key is NOT in response
    response_text = resp.text.lower()
    if "api_key" in data.get("gateway", {}) and data["gateway"].get("api_key"):
        log("FAIL: Full API key is present in response (security issue!)", "ERROR")
        return False
    
    log(f"PASS: GET payment-config returned correct structure")
    log(f"  - API key masked: {api_key_masked}")
    log(f"  - Source: {gateway.get('source')}")
    log(f"  - Credits: rupiah_per_credit={credits['rupiah_per_credit']}, bonus_percent={credits['bonus_percent']}, min_topup={credits['min_topup']}")
    return True


def test_non_admin_403():
    """Test 3: Non-admin user gets 403 on GET /api/admin/payment-config."""
    global normal_user_token, test_user_email
    log("TEST 3: Non-admin user gets 403 on GET /api/admin/payment-config")
    
    # Register a normal user
    import time
    test_user_email = f"testuser_{int(time.time())}@example.com"
    resp = register_user("Test User", test_user_email, "TestPass123!")
    if resp.status_code != 200:
        log(f"FAIL: User registration failed with {resp.status_code}: {resp.text}", "ERROR")
        return False
    
    normal_user_token = resp.cookies.get("access_token")
    if not normal_user_token:
        log("FAIL: No access_token cookie after registration", "ERROR")
        return False
    
    log(f"  - Registered normal user: {test_user_email}")
    
    # Try to access admin endpoint
    resp = requests.get(f"{API_BASE}/admin/payment-config", cookies={"access_token": normal_user_token})
    if resp.status_code != 403:
        log(f"FAIL: Expected 403, got {resp.status_code}: {resp.text}", "ERROR")
        return False
    
    log("PASS: Non-admin user correctly gets 403")
    return True


def test_put_credit_settings():
    """Test 4: PUT /api/admin/payment-config with credit settings."""
    log("TEST 4: PUT /api/admin/payment-config with credit settings")
    
    # Set new credit settings
    payload = {
        "rupiah_per_credit": 1000,
        "bonus_percent": 10,
        "min_topup": 20000
    }
    resp = requests.put(f"{API_BASE}/admin/payment-config", 
                       json=payload,
                       cookies={"access_token": admin_token})
    if resp.status_code != 200:
        log(f"FAIL: PUT payment-config returned {resp.status_code}: {resp.text}", "ERROR")
        return False
    
    data = resp.json()
    log(f"  - PUT response: {json.dumps(data.get('credits', {}), indent=2)}")
    
    # Verify GET reflects the changes
    resp = requests.get(f"{API_BASE}/admin/payment-config", cookies={"access_token": admin_token})
    if resp.status_code != 200:
        log(f"FAIL: GET after PUT returned {resp.status_code}", "ERROR")
        return False
    
    data = resp.json()
    credits = data["credits"]
    if credits["rupiah_per_credit"] != 1000:
        log(f"FAIL: rupiah_per_credit not updated (expected 1000, got {credits['rupiah_per_credit']})", "ERROR")
        return False
    if credits["bonus_percent"] != 10:
        log(f"FAIL: bonus_percent not updated (expected 10, got {credits['bonus_percent']})", "ERROR")
        return False
    if credits["min_topup"] != 20000:
        log(f"FAIL: min_topup not updated (expected 20000, got {credits['min_topup']})", "ERROR")
        return False
    
    log("PASS: Credit settings updated and persisted correctly")
    
    # Verify normal user sees these settings in /api/wallet/summary
    log("  - Verifying normal user sees updated settings in /api/wallet/summary")
    resp = requests.get(f"{API_BASE}/wallet/summary", cookies={"access_token": normal_user_token})
    if resp.status_code != 200:
        log(f"FAIL: GET wallet/summary returned {resp.status_code}: {resp.text}", "ERROR")
        return False
    
    wallet_data = resp.json()
    if wallet_data.get("rupiah_per_credit") != 1000:
        log(f"FAIL: wallet/summary rupiah_per_credit mismatch (expected 1000, got {wallet_data.get('rupiah_per_credit')})", "ERROR")
        return False
    if wallet_data.get("bonus_percent") != 10:
        log(f"FAIL: wallet/summary bonus_percent mismatch (expected 10, got {wallet_data.get('bonus_percent')})", "ERROR")
        return False
    if wallet_data.get("min_topup") != 20000:
        log(f"FAIL: wallet/summary min_topup mismatch (expected 20000, got {wallet_data.get('min_topup')})", "ERROR")
        return False
    
    log("PASS: Normal user sees updated credit settings in wallet/summary")
    return True


def test_topup_toggle():
    """Test 5: PUT /api/admin/payment-config with topup_enabled toggle."""
    log("TEST 5: PUT /api/admin/payment-config with topup_enabled toggle")
    
    # Disable topup
    payload = {
        "topup_enabled": False,
        "topup_disabled_message": "Maintenance"
    }
    resp = requests.put(f"{API_BASE}/admin/payment-config",
                       json=payload,
                       cookies={"access_token": admin_token})
    if resp.status_code != 200:
        log(f"FAIL: PUT topup_enabled=false returned {resp.status_code}: {resp.text}", "ERROR")
        return False
    
    # Verify GET reflects the change
    resp = requests.get(f"{API_BASE}/admin/payment-config", cookies={"access_token": admin_token})
    if resp.status_code != 200:
        log(f"FAIL: GET after PUT returned {resp.status_code}", "ERROR")
        return False
    
    data = resp.json()
    payments = data["payments"]
    if payments.get("topup_enabled") != False:
        log(f"FAIL: topup_enabled not disabled (got {payments.get('topup_enabled')})", "ERROR")
        return False
    if payments.get("topup_disabled_message") != "Maintenance":
        log(f"FAIL: topup_disabled_message not updated (got {payments.get('topup_disabled_message')})", "ERROR")
        return False
    
    log("PASS: topup_enabled=false persisted correctly")
    
    # Re-enable topup
    payload = {"topup_enabled": True}
    resp = requests.put(f"{API_BASE}/admin/payment-config",
                       json=payload,
                       cookies={"access_token": admin_token})
    if resp.status_code != 200:
        log(f"FAIL: PUT topup_enabled=true returned {resp.status_code}: {resp.text}", "ERROR")
        return False
    
    log("PASS: topup_enabled=true restored")
    return True


def test_mayar_base_url():
    """Test 6: PUT /api/admin/payment-config with mayar_base_url (SAFE VALUE ONLY)."""
    log("TEST 6: PUT /api/admin/payment-config with mayar_base_url")
    
    # SAFETY: Only set to the default/production URL (no risk)
    safe_url = "https://api.mayar.id/hl/v1"
    payload = {"mayar_base_url": safe_url}
    resp = requests.put(f"{API_BASE}/admin/payment-config",
                       json=payload,
                       cookies={"access_token": admin_token})
    if resp.status_code != 200:
        log(f"FAIL: PUT mayar_base_url returned {resp.status_code}: {resp.text}", "ERROR")
        return False
    
    # Verify GET reflects the change
    resp = requests.get(f"{API_BASE}/admin/payment-config", cookies={"access_token": admin_token})
    if resp.status_code != 200:
        log(f"FAIL: GET after PUT returned {resp.status_code}", "ERROR")
        return False
    
    data = resp.json()
    gateway = data["gateway"]
    if gateway.get("base_url") != safe_url:
        log(f"FAIL: base_url not updated (expected {safe_url}, got {gateway.get('base_url')})", "ERROR")
        return False
    
    log(f"PASS: mayar_base_url updated to {safe_url}")
    return True


def test_payment_config_test_endpoint():
    """Test 7: POST /api/admin/payment-config/test."""
    log("TEST 7: POST /api/admin/payment-config/test")
    
    resp = requests.post(f"{API_BASE}/admin/payment-config/test",
                        cookies={"access_token": admin_token})
    if resp.status_code != 200:
        log(f"FAIL: POST payment-config/test returned {resp.status_code}: {resp.text}", "ERROR")
        return False
    
    data = resp.json()
    log(f"  - Test response: {json.dumps(data, indent=2)}")
    
    # Verify response structure
    if "ok" not in data or "message" not in data:
        log("FAIL: Response missing 'ok' or 'message' fields", "ERROR")
        return False
    
    # It's fine whether ok is true or false (depends on Mayar reachability)
    # The important thing is NO 500 error
    log(f"PASS: Test endpoint returned 200 with ok={data['ok']}, message='{data['message']}'")
    return True


def test_credit_conversion_purchase_plan():
    """Test 8: Credit conversion on purchase-plan."""
    global normal_user_workspace_id
    log("TEST 8: Credit conversion on purchase-plan")
    
    # Get normal user's workspace ID
    resp = requests.get(f"{API_BASE}/auth/me", cookies={"access_token": normal_user_token})
    if resp.status_code != 200:
        log(f"FAIL: GET /api/auth/me returned {resp.status_code}: {resp.text}", "ERROR")
        return False
    
    me_data = resp.json()
    workspaces = me_data.get("workspaces", [])
    if not workspaces:
        log("FAIL: Normal user has no workspaces", "ERROR")
        return False
    
    normal_user_workspace_id = workspaces[0]["id"]
    log(f"  - Normal user workspace ID: {normal_user_workspace_id}")
    
    # As ADMIN, grant 300 credits to the normal user's workspace
    log("  - Granting 300 credits to normal user's workspace (as admin)")
    payload = {
        "workspace_id": normal_user_workspace_id,
        "amount": 300,
        "reason": "test credit conversion"
    }
    resp = requests.post(f"{API_BASE}/wallet/admin/adjust",
                        json=payload,
                        cookies={"access_token": admin_token})
    if resp.status_code != 200:
        log(f"FAIL: POST wallet/admin/adjust returned {resp.status_code}: {resp.text}", "ERROR")
        return False
    
    adjust_data = resp.json()
    if adjust_data.get("balance") != 300:
        log(f"FAIL: Balance after adjustment should be 300, got {adjust_data.get('balance')}", "ERROR")
        return False
    
    log(f"PASS: Granted 300 credits, balance={adjust_data['balance']}")
    
    # Verify rupiah_per_credit=1000, Pro plan price 299000 -> should cost ceil(299000/1000)=299 credits
    log("  - Attempting to purchase Pro plan (299000 Rp -> 299 credits)")
    resp = requests.post(f"{API_BASE}/wallet/purchase-plan",
                        json={"plan_id": "pro"},
                        cookies={"access_token": normal_user_token})
    if resp.status_code != 200:
        log(f"FAIL: POST wallet/purchase-plan returned {resp.status_code}: {resp.text}", "ERROR")
        return False
    
    purchase_data = resp.json()
    log(f"  - Purchase response: {json.dumps(purchase_data, indent=2)}")
    
    # Balance should be 300 - 299 = 1
    if purchase_data.get("balance") != 1:
        log(f"FAIL: Balance after purchase should be 1, got {purchase_data.get('balance')}", "ERROR")
        return False
    
    if purchase_data.get("plan") != "pro":
        log(f"FAIL: Plan should be 'pro', got {purchase_data.get('plan')}", "ERROR")
        return False
    
    log("PASS: Pro plan purchased successfully, balance=1 (300-299)")
    
    # Verify workspace plan is now 'pro'
    resp = requests.get(f"{API_BASE}/auth/me", cookies={"access_token": normal_user_token})
    if resp.status_code != 200:
        log(f"FAIL: GET /api/auth/me returned {resp.status_code}", "ERROR")
        return False
    
    me_data = resp.json()
    workspace = me_data.get("workspaces", [{}])[0]
    if workspace.get("plan") != "pro":
        log(f"FAIL: Workspace plan should be 'pro', got {workspace.get('plan')}", "ERROR")
        return False
    
    log("PASS: Workspace plan is now 'pro'")
    
    # Try purchasing 'business' (999000 -> 999 credits) with balance 1 -> expect 402
    log("  - Attempting to purchase Business plan (999000 Rp -> 999 credits) with balance 1")
    resp = requests.post(f"{API_BASE}/wallet/purchase-plan",
                        json={"plan_id": "business"},
                        cookies={"access_token": normal_user_token})
    if resp.status_code != 402:
        log(f"FAIL: Expected 402 for insufficient credits, got {resp.status_code}: {resp.text}", "ERROR")
        return False
    
    error_data = resp.json()
    error_detail = error_data.get("detail", "")
    log(f"  - Error message: {error_detail}")
    
    # Verify error message references credits (not raw Rupiah)
    if "credit" not in error_detail.lower():
        log(f"FAIL: Error message should reference 'credits', got: {error_detail}", "ERROR")
        return False
    
    # Should mention shortfall (999 - 1 = 998 credits)
    if "998" not in error_detail:
        log(f"FAIL: Error message should mention shortfall of 998 credits, got: {error_detail}", "ERROR")
        return False
    
    log("PASS: Business plan purchase correctly rejected with 402 (insufficient credits)")
    return True


def test_below_min_topup_validation():
    """Test 9: Below-min top-up validation (must NOT call Mayar)."""
    log("TEST 9: Below-min top-up validation")
    
    # Current min_topup is 20000 (set in test 4)
    # Try to top up with 5000 (below minimum)
    log("  - Attempting to top up 5000 Rp (below min_topup=20000)")
    payload = {"amount": 5000}
    resp = requests.post(f"{API_BASE}/wallet/topup",
                        json=payload,
                        cookies={"access_token": normal_user_token})
    
    if resp.status_code != 400:
        log(f"FAIL: Expected 400 for below-min top-up, got {resp.status_code}: {resp.text}", "ERROR")
        return False
    
    error_data = resp.json()
    error_detail = error_data.get("detail", "")
    log(f"  - Error message: {error_detail}")
    
    # Verify error message mentions minimum
    if "minimum" not in error_detail.lower():
        log(f"FAIL: Error message should mention 'minimum', got: {error_detail}", "ERROR")
        return False
    
    log("PASS: Below-min top-up correctly rejected with 400 (no Mayar call)")
    return True


def test_reset_credit_settings():
    """Test 10: Reset credit settings to defaults."""
    log("TEST 10: Reset credit settings to defaults")
    
    payload = {
        "rupiah_per_credit": 1000,
        "bonus_percent": 0,
        "min_topup": 10000,
        "topup_enabled": True
    }
    resp = requests.put(f"{API_BASE}/admin/payment-config",
                       json=payload,
                       cookies={"access_token": admin_token})
    if resp.status_code != 200:
        log(f"FAIL: PUT reset settings returned {resp.status_code}: {resp.text}", "ERROR")
        return False
    
    # Verify GET reflects the reset
    resp = requests.get(f"{API_BASE}/admin/payment-config", cookies={"access_token": admin_token})
    if resp.status_code != 200:
        log(f"FAIL: GET after reset returned {resp.status_code}", "ERROR")
        return False
    
    data = resp.json()
    credits = data["credits"]
    payments = data["payments"]
    
    if credits["rupiah_per_credit"] != 1000:
        log(f"FAIL: rupiah_per_credit not reset (expected 1000, got {credits['rupiah_per_credit']})", "ERROR")
        return False
    if credits["bonus_percent"] != 0:
        log(f"FAIL: bonus_percent not reset (expected 0, got {credits['bonus_percent']})", "ERROR")
        return False
    if credits["min_topup"] != 10000:
        log(f"FAIL: min_topup not reset (expected 10000, got {credits['min_topup']})", "ERROR")
        return False
    if payments.get("topup_enabled") != True:
        log(f"FAIL: topup_enabled not reset (expected True, got {payments.get('topup_enabled')})", "ERROR")
        return False
    
    log("PASS: Credit settings reset to defaults (rupiah_per_credit=1000, bonus_percent=0, min_topup=10000, topup_enabled=true)")
    return True


def main():
    """Run all tests."""
    log("=" * 80)
    log("BACKEND API TESTS: Admin Payments Feature (Midnight Link)")
    log("=" * 80)
    
    tests = [
        ("Admin login", test_admin_login),
        ("GET /api/admin/payment-config (verify masked key)", test_get_payment_config),
        ("Non-admin gets 403", test_non_admin_403),
        ("PUT credit settings (persist & reflect in wallet/summary)", test_put_credit_settings),
        ("PUT topup toggle (disable & re-enable)", test_topup_toggle),
        ("PUT mayar_base_url (safe value)", test_mayar_base_url),
        ("POST /api/admin/payment-config/test", test_payment_config_test_endpoint),
        ("Credit conversion on purchase-plan", test_credit_conversion_purchase_plan),
        ("Below-min top-up validation (no Mayar call)", test_below_min_topup_validation),
        ("Reset credit settings to defaults", test_reset_credit_settings),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            result = test_func()
            if result or result is None:  # None means test passed (e.g., login)
                passed += 1
            else:
                failed += 1
                log(f"TEST FAILED: {name}", "ERROR")
        except Exception as e:
            failed += 1
            log(f"TEST EXCEPTION: {name} - {e}", "ERROR")
            import traceback
            traceback.print_exc()
    
    log("=" * 80)
    log(f"RESULTS: {passed} passed, {failed} failed")
    log("=" * 80)
    
    if failed > 0:
        sys.exit(1)
    else:
        log("ALL TESTS PASSED!", "SUCCESS")
        sys.exit(0)


if __name__ == "__main__":
    main()
