"""Iteration 18 — Payment Partners redesign regression.

Covers the new admin API shape (detail = partner + stats only), the new
paginated /charges and /deliveries endpoints (status filter, reference search,
page/limit), the sanitization fix (short customer.name / short mobile no
longer 502) and the classic partner-facing charge flow. Bulk pagination data
is seeded directly into MongoDB to avoid hammering real Mayar 16+ times.
"""
import os
import re
import time
import uuid
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "midgate_db")

ADMIN_EMAIL = "admin@midgate.co"
ADMIN_PASS = "Admin123!"
TEAM_EMAIL = "teammate@example.com"
TEAM_PASS = "Teammate123!"


# ------------- fixtures ---------------------------------------------------- #
def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def teammate():
    return _login(TEAM_EMAIL, TEAM_PASS)


@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


@pytest.fixture(scope="module")
def partner(admin):
    r = admin.post(f"{BASE_URL}/api/admin/partners", json={
        "name": f"qa18-{uuid.uuid4().hex[:6]}",
        "webhook_url": "https://httpbin.org/post",
        "source_tag": "qa",
    }, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    yield data
    try:
        admin.delete(f"{BASE_URL}/api/admin/partners/{data['id']}", timeout=15)
    except Exception:
        pass


# ------------- new endpoint shape (detail = partner + stats only) --------- #
class TestPartnerDetailShape:
    def test_detail_returns_only_partner_and_stats(self, admin, partner):
        r = admin.get(f"{BASE_URL}/api/admin/partners/{partner['id']}", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert set(d.keys()) == {"partner", "stats"}, f"unexpected keys: {list(d.keys())}"
        assert "charges" not in d and "deliveries" not in d
        assert d["partner"]["id"] == partner["id"]
        assert isinstance(d["stats"], dict)
        for k in ("charges", "paid_count", "paid_amount"):
            assert k in d["stats"]

    def test_ping_returns_partner_and_bounds(self, partner):
        r = requests.get(f"{BASE_URL}/api/pay/ping",
                         headers={"Authorization": f"Bearer {partner['api_key']}"}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True and d["partner"] == partner["name"]
        assert d["min_amount"] == 10000 and d["max_amount"] == 10000000
        assert d["currency"] == "IDR"


# ------------- paginated charges endpoint --------------------------------- #
class TestPaginatedCharges:
    @pytest.fixture(scope="class")
    def seeded(self, db, partner):
        """Seed 18 charges directly for pagination tests (15/page → 2 pages)."""
        pid = partner["id"]
        now = datetime.now(timezone.utc)
        docs = []
        for i in range(18):
            status = "paid" if i < 5 else ("expired" if i < 8 else "pending")
            docs.append({
                "id": f"qa-seed-{pid[:6]}-{i:02d}",
                "partner_id": pid,
                "reference_id": f"QA-REF-{i:03d}",
                "amount": 25000 + i * 1000,
                "currency": "IDR",
                "status": status,
                "checkout_url": "https://myr.id/checkout/mock",
                "description": None,
                "customer": {"name": "Seeded", "email": "s@x.co", "mobile": "081200000000"},
                "notified": status == "paid",
                "created_at": now.isoformat().replace("+00:00", f".{i:03d}Z"),
                "paid_at": now.isoformat() if status == "paid" else None,
                "expires_at": None,
            })
        db.partner_charges.insert_many(docs)
        yield {"count": 18, "paid": 5, "expired": 3, "pending": 10}
        db.partner_charges.delete_many({"partner_id": pid, "id": {"$regex": "^qa-seed-"}})

    def test_page1_shape_and_limit(self, admin, partner, seeded):
        r = admin.get(f"{BASE_URL}/api/admin/partners/{partner['id']}/charges",
                      params={"page": 1, "limit": 15}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert set(["items", "total", "page", "pages"]) <= set(d.keys())
        assert d["total"] >= 18
        assert d["page"] == 1
        assert len(d["items"]) == 15
        assert d["pages"] >= 2

    def test_page2_returns_remainder(self, admin, partner, seeded):
        r = admin.get(f"{BASE_URL}/api/admin/partners/{partner['id']}/charges",
                      params={"page": 2, "limit": 15}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["page"] == 2 and len(d["items"]) >= 3

    def test_filter_by_status_paid(self, admin, partner, seeded):
        r = admin.get(f"{BASE_URL}/api/admin/partners/{partner['id']}/charges",
                      params={"status": "paid", "limit": 50}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["total"] >= 5
        assert all(c["status"] == "paid" for c in d["items"])

    def test_filter_by_status_expired(self, admin, partner, seeded):
        r = admin.get(f"{BASE_URL}/api/admin/partners/{partner['id']}/charges",
                      params={"status": "expired", "limit": 50}, timeout=15)
        assert r.status_code == 200
        assert all(c["status"] == "expired" for c in r.json()["items"])

    def test_search_by_reference(self, admin, partner, seeded):
        r = admin.get(f"{BASE_URL}/api/admin/partners/{partner['id']}/charges",
                      params={"q": "QA-REF-00", "limit": 50}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        # QA-REF-000..009 = 10 seeded charges
        assert d["total"] >= 10
        assert all("qa-ref-00" in c["reference_id"].lower() for c in d["items"])

    def test_search_regex_escaped(self, admin, partner, seeded):
        # regex special chars must be escaped by the backend (no 500)
        r = admin.get(f"{BASE_URL}/api/admin/partners/{partner['id']}/charges",
                      params={"q": ".*"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["total"] == 0  # literal ".*" doesn't match "QA-REF-###"


# ------------- paginated deliveries endpoint ------------------------------ #
class TestPaginatedDeliveries:
    @pytest.fixture(scope="class")
    def seeded_deliveries(self, db, partner):
        pid = partner["id"]
        now = datetime.now(timezone.utc).isoformat()
        docs = []
        for i in range(17):
            status = "success" if i % 3 else "failed"
            docs.append({
                "id": f"qa-dlv-{pid[:6]}-{i:02d}",
                "partner_id": pid,
                "charge_id": f"qa-seed-{pid[:6]}-{i:02d}",
                "event": "charge.paid",
                "url": "https://httpbin.org/post",
                "status": status,
                "status_code": 200 if status == "success" else 500,
                "attempts": 1 if status == "success" else 3,
                "error": None if status == "success" else "HTTP 500",
                "payload": {"stub": True},
                "created_at": now,
            })
        db.partner_webhook_deliveries.insert_many(docs)
        yield {"count": 17}
        db.partner_webhook_deliveries.delete_many({"partner_id": pid, "id": {"$regex": "^qa-dlv-"}})

    def test_deliveries_paginated_shape(self, admin, partner, seeded_deliveries):
        r = admin.get(f"{BASE_URL}/api/admin/partners/{partner['id']}/deliveries",
                      params={"page": 1, "limit": 15}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert set(["items", "total", "page", "pages"]) <= set(d.keys())
        assert d["total"] >= 17
        assert len(d["items"]) == 15
        # payload should be projected out
        assert all("payload" not in it for it in d["items"])

    def test_deliveries_status_filter(self, admin, partner, seeded_deliveries):
        r = admin.get(f"{BASE_URL}/api/admin/partners/{partner['id']}/deliveries",
                      params={"status": "failed", "limit": 50}, timeout=15)
        assert r.status_code == 200
        assert all(it["status"] == "failed" for it in r.json()["items"])

    def test_deliveries_empty_state_for_unknown_partner(self, admin):
        # unknown partner id must not 500 — should return empty page
        r = admin.get(f"{BASE_URL}/api/admin/partners/does-not-exist/deliveries", timeout=15)
        assert r.status_code == 200
        assert r.json()["total"] == 0


# ------------- charge sanitization regression (iter 17 minor fix) --------- #
class TestSanitizationFix:
    def test_short_name_and_mobile_no_longer_502(self, partner):
        """Iter-17 minor bug: short name/mobile bubbled up as 502.
        After fix, they should be padded and the charge should succeed."""
        ref = f"qa-sanitize-{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{BASE_URL}/api/pay/charges",
                          headers={"Authorization": f"Bearer {partner['api_key']}"},
                          json={"amount": 25000, "reference_id": ref,
                                "customer": {"name": "A", "email": "a@b.co", "mobile": "0812"}},
                          timeout=45)
        assert r.status_code == 200, f"expected 200 after sanitize fix, got {r.status_code}: {r.text[:300]}"
        assert r.json()["status"] == "pending"
        assert "myr.id" in (r.json().get("checkout_url") or "")


# ------------- classic partner API regression ----------------------------- #
class TestChargesAPI:
    def _hdr(self, partner):
        return {"Authorization": f"Bearer {partner['api_key']}"}

    def test_create_charge_returns_real_mayar_link(self, partner):
        ref = f"qa18-001-{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{BASE_URL}/api/pay/charges", headers=self._hdr(partner),
                          json={"amount": 50000, "reference_id": ref,
                                "customer": {"name": "Alice QA", "email": "a@b.com", "mobile": "081200000000"}},
                          timeout=45)
        assert r.status_code == 200, r.text
        c = r.json()
        assert c["status"] == "pending" and "myr.id" in c["checkout_url"]
        partner.setdefault("_charges", {})[ref] = c

    def test_idempotent_same_reference(self, partner):
        ref, c = next(iter(partner["_charges"].items()))
        r = requests.post(f"{BASE_URL}/api/pay/charges", headers=self._hdr(partner),
                          json={"amount": 50000, "reference_id": ref}, timeout=45)
        assert r.status_code == 200 and r.json()["id"] == c["id"]

    def test_amount_min_max(self, partner):
        r1 = requests.post(f"{BASE_URL}/api/pay/charges", headers=self._hdr(partner),
                           json={"amount": 5000, "reference_id": f"qa-lo-{uuid.uuid4().hex[:6]}"}, timeout=15)
        r2 = requests.post(f"{BASE_URL}/api/pay/charges", headers=self._hdr(partner),
                           json={"amount": 20_000_000, "reference_id": f"qa-hi-{uuid.uuid4().hex[:6]}"}, timeout=15)
        assert r1.status_code == 400 and r2.status_code == 400

    def test_missing_and_blank_reference(self, partner):
        r1 = requests.post(f"{BASE_URL}/api/pay/charges", headers=self._hdr(partner),
                           json={"amount": 50000}, timeout=15)
        r2 = requests.post(f"{BASE_URL}/api/pay/charges", headers=self._hdr(partner),
                           json={"amount": 50000, "reference_id": ""}, timeout=15)
        assert r1.status_code in (400, 422) and r2.status_code in (400, 422)

    def test_get_charge_reverifies(self, partner):
        ref, c = next(iter(partner["_charges"].items()))
        r = requests.get(f"{BASE_URL}/api/pay/charges/{c['id']}", headers=self._hdr(partner), timeout=30)
        assert r.status_code == 200 and r.json()["status"] == "pending"


# ------------- auth / RBAC ----------------------------------------------- #
class TestAuthAndRBAC:
    def test_no_auth_header(self):
        r = requests.post(f"{BASE_URL}/api/pay/charges", json={"amount": 50000, "reference_id": "x"}, timeout=15)
        assert r.status_code == 401

    def test_bad_key(self):
        r = requests.post(f"{BASE_URL}/api/pay/charges",
                          headers={"Authorization": "Bearer mgpay_live_bad"},
                          json={"amount": 50000, "reference_id": "x"}, timeout=15)
        assert r.status_code == 401

    def test_inactive_partner_key_rejected(self, admin, partner):
        admin.patch(f"{BASE_URL}/api/admin/partners/{partner['id']}", json={"active": False}, timeout=15)
        r = requests.post(f"{BASE_URL}/api/pay/charges",
                          headers={"Authorization": f"Bearer {partner['api_key']}"},
                          json={"amount": 50000, "reference_id": "qa-inactive"}, timeout=15)
        admin.patch(f"{BASE_URL}/api/admin/partners/{partner['id']}", json={"active": True}, timeout=15)
        assert r.status_code == 401

    def test_teammate_forbidden_on_admin_partners(self, teammate):
        r = teammate.get(f"{BASE_URL}/api/admin/partners", timeout=15)
        assert r.status_code == 403


# ------------- webhook re-verify safety ---------------------------------- #
class TestWebhookSafety:
    def test_public_mayar_webhook_does_not_mark_paid(self, partner):
        # self-sufficient: create a fresh charge so this works under xdist too
        ref = f"qa-spoof-{uuid.uuid4().hex[:6]}"
        cr = requests.post(f"{BASE_URL}/api/pay/charges",
                           headers={"Authorization": f"Bearer {partner['api_key']}"},
                           json={"amount": 30000, "reference_id": ref}, timeout=45)
        assert cr.status_code == 200, cr.text
        c = cr.json()
        r = requests.post(f"{BASE_URL}/api/wallet/mayar/webhook",
                          json={"event": "payment.received",
                                "data": {"extraData": {"charge_id": c["id"]}}}, timeout=30)
        assert r.status_code in (200, 202)
        time.sleep(1)
        chk = requests.get(f"{BASE_URL}/api/pay/charges/{c['id']}",
                           headers={"Authorization": f"Bearer {partner['api_key']}"}, timeout=30)
        assert chk.status_code == 200 and chk.json()["status"] == "pending"


# ------------- settings mutations (rotate / toggle / delete cascade) ----- #
class TestSettingsMutations:
    def test_rotate_key_and_secret(self, admin, partner):
        r1 = admin.post(f"{BASE_URL}/api/admin/partners/{partner['id']}/rotate-key", timeout=15)
        r2 = admin.post(f"{BASE_URL}/api/admin/partners/{partner['id']}/rotate-secret", timeout=15)
        assert r1.status_code == 200 and r1.json()["api_key"].startswith("mgpay_live_")
        assert r2.status_code == 200 and r2.json()["webhook_secret"].startswith("mgwhsec_")
        partner["api_key"] = r1.json()["api_key"]

    def test_patch_webhook_url(self, admin, partner):
        r = admin.patch(f"{BASE_URL}/api/admin/partners/{partner['id']}",
                        json={"webhook_url": "https://httpbin.org/anything"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["webhook_url"] == "https://httpbin.org/anything"
