# Partner data cleanup (>30 days) - preview + delete endpoints, isolation, auth, audit log
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = {"email": "admin@midnightlink.link", "password": "Admin123!"}

_env = {}
with open("/app/backend/.env") as f:
    for line in f:
        if "=" in line:
            k, v = line.strip().split("=", 1)
            _env[k] = v.strip('"')
mdb = MongoClient(_env["MONGO_URL"])[_env["DB_NAME"]]

AGES = [(45, "paid", 700000), (40, "expired", 100000), (35, "pending", 50000), (31, "paid", 200000),
        (29, "paid", 300000), (10, "expired", 10000), (1, "pending", 20000)]


def _ago(d):
    return (datetime.now(timezone.utc) - timedelta(days=d)).isoformat()


def _seed(pid):
    for d, st, amt in AGES:
        cid = str(uuid.uuid4())
        mdb.partner_charges.insert_one({"id": cid, "partner_id": pid, "reference_id": f"TEST_{d}d_{st}",
                                        "amount": amt, "status": st, "created_at": _ago(d),
                                        "expires_at": _ago(d - 0.01)})
        mdb.partner_webhook_deliveries.insert_one({"id": str(uuid.uuid4()), "partner_id": pid, "charge_id": cid,
                                                   "status_code": 200, "ok": True, "created_at": _ago(d)})


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=ADMIN)
    if r.status_code != 200:
        pytest.skip(f"admin login failed {r.status_code}")
    return s


@pytest.fixture(scope="module")
def partners(admin):
    made = []
    for n in ("A", "B"):
        r = admin.post(f"{API}/admin/partners", json={"name": f"TEST_cleanup_{n}_{uuid.uuid4().hex[:6]}"})
        assert r.status_code == 200, r.text
        d = r.json()
        _seed(d["id"])
        made.append(d)
    yield made
    for d in made:
        admin.delete(f"{API}/admin/partners/{d['id']}")
        mdb.audit_logs.delete_many({"action": "partner.data_cleanup", "target": d["id"]})


def test_preview_counts(admin, partners):
    pid = partners[0]["id"]
    r = admin.get(f"{API}/admin/partners/{pid}/cleanup-preview", params={"older_than_days": 30})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["charges"] == 4
    assert d["deliveries"] == 4
    assert d["by_status"] == {"paid": 2, "expired": 1, "pending": 1}
    assert d["paid_amount"] == 900000
    assert d["older_than_days"] == 30 and isinstance(d["cutoff"], str)


def test_preview_longer_window(admin, partners):
    r = admin.get(f"{API}/admin/partners/{partners[0]['id']}/cleanup-preview", params={"older_than_days": 38})
    assert r.status_code == 200
    assert r.json()["charges"] == 2 and r.json()["paid_amount"] == 700000


def test_preview_validation_and_404(admin, partners):
    pid = partners[0]["id"]
    assert admin.get(f"{API}/admin/partners/{pid}/cleanup-preview", params={"older_than_days": 29}).status_code == 422
    assert admin.get(f"{API}/admin/partners/{pid}/cleanup-preview", params={"older_than_days": 0}).status_code == 422
    assert admin.get(f"{API}/admin/partners/nope-{uuid.uuid4()}/cleanup-preview").status_code == 404


def test_preview_is_readonly(admin, partners):
    pid = partners[0]["id"]
    admin.get(f"{API}/admin/partners/{pid}/cleanup-preview")
    assert mdb.partner_charges.count_documents({"partner_id": pid}) == 7


def test_cleanup_requires_confirm(admin, partners):
    pid = partners[0]["id"]
    r = admin.post(f"{API}/admin/partners/{pid}/cleanup", json={"older_than_days": 30})
    assert r.status_code == 400
    r = admin.post(f"{API}/admin/partners/{pid}/cleanup", json={"older_than_days": 30, "confirm": False})
    assert r.status_code == 400
    assert mdb.partner_charges.count_documents({"partner_id": pid}) == 7


def test_cleanup_validation(admin, partners):
    pid = partners[0]["id"]
    r = admin.post(f"{API}/admin/partners/{pid}/cleanup", json={"older_than_days": 10, "confirm": True})
    assert r.status_code == 422
    r = admin.post(f"{API}/admin/partners/nope-{uuid.uuid4()}/cleanup", json={"older_than_days": 30, "confirm": True})
    assert r.status_code == 404
    assert mdb.partner_charges.count_documents({"partner_id": pid}) == 7


def test_unauth_and_non_admin_rejected(partners):
    pid = partners[0]["id"]
    anon = requests.Session()
    assert anon.get(f"{API}/admin/partners/{pid}/cleanup-preview").status_code in (401, 403)
    assert anon.post(f"{API}/admin/partners/{pid}/cleanup", json={"confirm": True}).status_code in (401, 403)
    u = requests.Session()
    email = f"test_cleanup_{uuid.uuid4().hex[:8]}@example.com"
    r = u.post(f"{API}/auth/register", json={"name": "TEST_user", "email": email, "password": "Passw0rd!x"})
    try:
        assert r.status_code in (200, 201), r.text
        if not u.cookies:
            tok = r.json().get("token") or r.json().get("access_token")
            if tok:
                u.headers["Authorization"] = f"Bearer {tok}"
        assert u.get(f"{API}/admin/partners/{pid}/cleanup-preview").status_code in (401, 403)
        assert u.post(f"{API}/admin/partners/{pid}/cleanup", json={"confirm": True}).status_code in (401, 403)
        assert mdb.partner_charges.count_documents({"partner_id": pid}) == 7
    finally:
        mdb.users.delete_one({"email": email})


def test_cleanup_executes_and_isolated(admin, partners):
    a, b = partners
    r = admin.post(f"{API}/admin/partners/{a['id']}/cleanup", json={"older_than_days": 30, "confirm": True})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] is True
    assert d["charges_deleted"] == 4 and d["deliveries_deleted"] == 4
    assert d["stats"] == {"charges": 3, "paid_count": 1, "paid_amount": 300000}
    refs = sorted(c["reference_id"] for c in mdb.partner_charges.find({"partner_id": a["id"]}))
    assert refs == sorted(["TEST_29d_paid", "TEST_10d_expired", "TEST_1d_pending"])
    assert mdb.partner_webhook_deliveries.count_documents({"partner_id": a["id"]}) == 3
    # other partner untouched
    assert mdb.partner_charges.count_documents({"partner_id": b["id"]}) == 7
    assert mdb.partner_webhook_deliveries.count_documents({"partner_id": b["id"]}) == 7
    # detail stats agree
    det = admin.get(f"{API}/admin/partners/{a['id']}").json()
    assert det["stats"]["charges"] == 3 and det["stats"]["paid_amount"] == 300000
    # audit log
    log = mdb.audit_logs.find_one({"action": "partner.data_cleanup", "target": a["id"]})
    assert log and log["after"]["charges_deleted"] == 4 and log["after"]["paid_amount"] == 900000
    assert log["actor"] == ADMIN["email"]


def test_partner_and_key_survive(admin, partners):
    a = partners[0]
    assert mdb.partners.find_one({"id": a["id"]}) is not None
    r = requests.get(f"{API}/pay/ping", headers={"Authorization": f"Bearer {a['api_key']}"})
    assert r.status_code == 200, r.text
    lst = admin.get(f"{API}/admin/partners/{a['id']}/charges")
    if lst.status_code == 200:
        body = lst.json()
        items = body.get("items", body) if isinstance(body, dict) else body
        assert len(items) == 3


def test_rerun_is_noop(admin, partners):
    pid = partners[0]["id"]
    p = admin.get(f"{API}/admin/partners/{pid}/cleanup-preview").json()
    assert p["charges"] == 0 and p["deliveries"] == 0 and p["by_status"] == {}
    r = admin.post(f"{API}/admin/partners/{pid}/cleanup", json={"older_than_days": 30, "confirm": True})
    assert r.status_code == 200
    assert r.json()["charges_deleted"] == 0 and r.json()["stats"]["charges"] == 3
