"""
End-to-end tests for the unified in-app notification flow:

- notify() writes every column (body, entity_type, payload_json, org_id, dedupe_key)
- dedupe_key suppresses duplicates for the SAME user only
- no dedupe_key => no suppression at all
- GET /api/notifications returns real entity_type/payload and never-null body
- limit is capped at 1..100
- a user cannot read/mark/delete another user's notification
- deadline reminders create notify()-style rows (type, org_id, payload) and
  are idempotent across runs
- the analysis worker creates ANALYSIS_FINISHED / ANALYSIS_FAILED rows
- signup notifies org admins (NEW_USER_SIGNUP)

Uses a temp SQLite DB (tests/conftest.py redirects DATABASE_URL); never
touches the shared formatify.db.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("SUPER_ADMIN_KEY", "super_secret_master_key_here")
os.environ.setdefault("JWT_SECRET", "formatify_dev_jwt_secret_change_me")
os.environ.setdefault("PLAGIARISM_ENABLE_WEB", "false")
os.environ.setdefault("PLAGIARISM_LLM_PATTERNS", "false")
if not os.environ.get("FORMATIFY_ENC_KEY"):
    from cryptography.fernet import Fernet

    os.environ["FORMATIFY_ENC_KEY"] = Fernet.generate_key().decode()


def _uniq(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("notif_flow")
    db_path = tmp / "flow.db"

    import database

    database.DATABASE_URL = str(db_path)
    database.init_db()

    import main as main_mod

    main_mod.UPLOAD_DIR = str(tmp / "uploads")
    main_mod.OUTPUT_DIR = str(tmp / "outputs")
    main_mod.ANALYSIS_CACHE_DIR = str(tmp / "uploads" / "analysis")
    os.makedirs(main_mod.ANALYSIS_CACHE_DIR, exist_ok=True)

    # Ensure tenant columns exist on the fresh DB, then seed test users.
    conn = database.get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET org_id = 1 WHERE org_id IS NULL")

    cur.execute(
        "INSERT INTO users (username, email, password_hash, role, org_id) VALUES (?, ?, ?, 'student', 1)",
        (_uniq("flow_student"), f"{_uniq('fs')}@example.com", "hash"),
    )
    student_id = int(cur.lastrowid)
    cur.execute(
        "INSERT INTO users (username, email, password_hash, role, org_id) VALUES (?, ?, ?, 'student', 1)",
        (_uniq("flow_student2"), f"{_uniq('fs2')}@example.com", "hash"),
    )
    student2_id = int(cur.lastrowid)
    cur.execute(
        "INSERT INTO users (username, email, password_hash, role, org_id) VALUES (?, ?, ?, 'admin', 1)",
        (_uniq("flow_admin"), f"{_uniq('fa')}@example.com", "hash"),
    )
    admin_id = int(cur.lastrowid)
    conn.commit()
    conn.close()

    from auth_jwt import create_access_token

    def _token(uid: int, role: str, email: str) -> str:
        return create_access_token(
            user_id=uid, org_id=1, role=role, email=email, org_code="COMSATS-LHR"
        )

    cur = database.get_db().cursor()
    emails = {}
    for uid in (student_id, student2_id, admin_id):
        cur.execute("SELECT email FROM users WHERE id = ?", (uid,))
        emails[uid] = cur.fetchone()["email"]

    return SimpleNamespace(
        main=main_mod,
        database=database,
        tmp=tmp,
        student_id=student_id,
        student2_id=student2_id,
        admin_id=admin_id,
        student_token=_token(student_id, "student", emails[student_id]),
        student2_token=_token(student2_id, "student", emails[student2_id]),
        admin_token=_token(admin_id, "admin", emails[admin_id]),
    )


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── notify() column coverage + dedupe semantics ──────────────────────────────

def test_notify_writes_all_columns(env):
    from services.notification_service import notify, NotificationType

    nid = notify(
        org_id=1,
        user_id=env.student_id,
        type=NotificationType.ANALYSIS_FINISHED,
        title="T",
        body="B",
        entity_type="document",
        entity_id=42,
        payload={"screen": "analyze", "document_id": 42},
        dedupe_key=_uniq("dk"),
    )
    assert nid is not None
    conn = env.database.get_db()
    row = conn.execute("SELECT * FROM notifications WHERE id = ?", (nid,)).fetchone()
    conn.close()
    assert row["body"] == "B"
    assert row["message"] == "B"               # legacy column still written
    assert row["entity_type"] == "document"
    assert row["related_type"] == "document"  # legacy column still written
    assert row["related_id"] == 42            # entity_id lands in related_id
    assert row["org_id"] == 1
    conn2 = env.database.get_db()
    expected_email = conn2.execute(
        "SELECT email FROM users WHERE id = ?", (env.student_id,)
    ).fetchone()["email"]
    conn2.close()
    assert row["recipient_email"] == expected_email
    assert json.loads(row["payload_json"]) == {"screen": "analyze", "document_id": 42}
    assert row["dedupe_key"]


def test_dedupe_key_same_user_only(env):
    from services.notification_service import notify, NotificationType

    key = _uniq("shared")
    first = notify(org_id=1, user_id=env.student_id, type="t", title="a", body="b",
                   dedupe_key=key)
    second = notify(org_id=1, user_id=env.student_id, type="t", title="a", body="b",
                    dedupe_key=key)
    other = notify(org_id=1, user_id=env.student2_id, type="t", title="a", body="b",
                   dedupe_key=key)
    assert first is not None
    assert second is None      # same user + same key -> suppressed
    assert other is not None   # different user -> allowed


def test_no_dedupe_key_means_no_suppression(env):
    from services.notification_service import notify

    a = notify(org_id=1, user_id=env.student_id, type="repeat", title="a", body="b",
               entity_type="document", entity_id=7)
    b = notify(org_id=1, user_id=env.student_id, type="repeat", title="a", body="b",
               entity_type="document", entity_id=7)
    assert a is not None and b is not None and a != b


# ── list endpoint: real columns, non-null body, limit cap ────────────────────

def test_list_returns_entity_type_payload_and_body(env):
    from services.notification_service import notify

    notify(org_id=1, user_id=env.student_id, type="flow_test",
           title="Hello", body="World", entity_type="document", entity_id=55,
           payload={"screen": "analyze", "document_id": 55})

    from fastapi.testclient import TestClient
    client = TestClient(env.main.app)
    r = client.get("/api/notifications?limit=50", headers=_auth(env.student_token))
    assert r.status_code == 200
    items = r.json()["notifications"]
    match = [n for n in items if n["type"] == "flow_test" and n["entity_id"] == 55]
    assert match, "expected notification missing from list"
    n = match[0]
    assert n["entity_type"] == "document"
    assert n["payload"] == {"screen": "analyze", "document_id": 55}
    assert n["body"] == "World"


def test_list_body_never_null_for_legacy_rows(env):
    # Simulate a legacy reminder-style row: message set, body NULL.
    conn = env.database.get_db()
    conn.execute(
        "INSERT INTO notifications (user_id, recipient_email, title, message, type, is_read,"
        " related_type, related_id, org_id) VALUES (?, '', 'Legacy', 'Legacy body', 'deadline', 0,"
        " 'deadline', 1, 1)",
        (env.student_id,),
    )
    conn.commit()
    conn.close()

    from fastapi.testclient import TestClient
    client = TestClient(env.main.app)
    r = client.get("/api/notifications?limit=50", headers=_auth(env.student_token))
    assert r.status_code == 200
    legacy = [n for n in r.json()["notifications"] if n["title"] == "Legacy"]
    assert legacy and legacy[0]["body"] == "Legacy body"


def test_limit_capped(env):
    from fastapi.testclient import TestClient
    client = TestClient(env.main.app)
    for bad in (0, 101, -5):
        r = client.get(f"/api/notifications?limit={bad}", headers=_auth(env.student_token))
        assert r.status_code == 422, f"limit={bad} should be rejected"
    r = client.get("/api/notifications?limit=1", headers=_auth(env.student_token))
    assert r.status_code == 200
    assert len(r.json()["notifications"]) <= 1


# ── isolation: user B cannot touch user A's notifications ────────────────────

def test_cannot_access_other_users_notification(env):
    from services.notification_service import notify
    from fastapi.testclient import TestClient

    nid = notify(org_id=1, user_id=env.student_id, type="private",
                 title="Secret", body="hidden")
    assert nid is not None
    client = TestClient(env.main.app)
    h = _auth(env.student2_token)

    assert client.post(f"/api/notifications/{nid}/read", headers=h).status_code == 404
    assert client.delete(f"/api/notifications/{nid}", headers=h).status_code == 404
    # and it must not appear in user2's list
    items = client.get("/api/notifications?limit=50", headers=h).json()["notifications"]
    assert all(n["id"] != nid for n in items)
    # owner CAN mark it read
    assert client.post(f"/api/notifications/{nid}/read",
                       headers=_auth(env.student_token)).status_code == 200


# ── deadline reminders ────────────────────────────────────────────────────────

def test_reminders_create_rows_and_are_idempotent(env):
    import reminders

    conn = env.database.get_db()
    cur = conn.cursor()
    # Deadline due tomorrow -> stage 1 -> deadline_reminder_1_day
    cur.execute(
        """
        INSERT INTO deadlines (title, description, due_date, applies_to_all, org_id)
        VALUES ('Flow Deadline', 'desc', date('now','localtime','+1 day'), 1, 1)
        """
    )
    deadline_id = int(cur.lastrowid)
    conn.commit()
    conn.close()

    # student needs an email-less account so no SMTP is attempted
    conn = env.database.get_db()
    conn.execute("UPDATE users SET email = '' WHERE id = ?", (env.student_id,))
    conn.commit()
    conn.close()

    r1 = reminders.run_deadline_reminders()
    r2 = reminders.run_deadline_reminders()  # second run must not duplicate

    conn = env.database.get_db()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? AND related_id = ? AND type LIKE 'deadline_reminder%'",
        (env.student_id, deadline_id),
    ).fetchall()
    conn.close()

    assert len(rows) == 1, f"expected exactly 1 reminder row, got {len(rows)}"
    row = rows[0]
    assert row["type"] == "deadline_reminder_1_day"
    assert row["org_id"] == 1
    assert row["entity_type"] == "deadline"
    assert row["related_id"] == deadline_id
    payload = json.loads(row["payload_json"])
    assert payload["screen"] == "deadlines"
    assert payload["deadline_id"] == deadline_id
    assert row["dedupe_key"] == f"deadline_{deadline_id}_{env.student_id}_1"
    assert r1["notifications"] >= 1


# ── analysis worker notifications ────────────────────────────────────────────

def test_analysis_worker_finished_and_failed(env, monkeypatch):
    main_mod = env.main

    # document row so _notify_analysis_result can resolve filename/org
    conn = env.database.get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM templates LIMIT 1")
    tmpl_id = int(cur.fetchone()["id"])
    cur.execute(
        "INSERT INTO documents (user_id, template_id, filename, file_path, status)"
        " VALUES (?, ?, 'flow.docx', 'flow.docx', 'pending')",
        (env.student_id, tmpl_id),
    )
    doc_id = int(cur.lastrowid)
    conn.commit()
    conn.close()

    def _fake_ok(document_id, user_id, freeform):
        return {"issues": [{"id": "i1"}, {"id": "i2"}]}

    monkeypatch.setattr(main_mod, "_analysis_in_thread", _fake_ok)
    main_mod._analysis_jobs[doc_id] = {
        "status": "processing", "error": None,
        "started_at": "t0", "finished_at": None,
    }
    asyncio.run(main_mod._analysis_worker(doc_id, env.student_id, False))

    conn = env.database.get_db()
    row = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? AND type = 'analysis_finished'"
        " AND related_id = ? ORDER BY id DESC LIMIT 1",
        (env.student_id, doc_id),
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["entity_type"] == "document" and row["related_id"] == doc_id
    assert json.loads(row["payload_json"])["screen"] == "analyze"
    assert "2 issue" in row["body"]

    def _fake_fail(document_id, user_id, freeform):
        raise RuntimeError("boom-" + "x" * 300)

    monkeypatch.setattr(main_mod, "_analysis_in_thread", _fake_fail)
    main_mod._analysis_jobs[doc_id] = {
        "status": "processing", "error": None,
        "started_at": "t0", "finished_at": None,
    }
    asyncio.run(main_mod._analysis_worker(doc_id, env.student_id, False))

    conn = env.database.get_db()
    row = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? AND type = 'analysis_failed'"
        " ORDER BY id DESC LIMIT 1",
        (env.student_id,),
    ).fetchone()
    conn.close()
    assert row is not None
    assert len(row["body"]) < 400  # error trimmed to 200 chars inside body
    assert "boom" in row["body"]


# ── signup notifies admins ────────────────────────────────────────────────────

def test_signup_notifies_org_admins(env):
    from fastapi.testclient import TestClient

    client = TestClient(env.main.app)
    payload = {
        "username": _uniq("new_student"),
        "email": f"{_uniq('ns')}@example.com",
        "password": "password123",
        "department_id": 1,
        "current_semester": 6,
        "org_code": "COMSATS-LHR",
    }
    r = client.post("/api/auth/signup", json=payload)
    assert r.status_code == 200, r.text
    new_user_id = r.json()["id"]

    conn = env.database.get_db()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? AND type = 'new_user_signup'",
        (env.admin_id,),
    ).fetchall()
    conn.close()
    assert rows, "admin should have received a signup notification"
    assert json.loads(rows[-1]["payload_json"])["screen"] == "users"
    assert rows[-1]["related_id"] == new_user_id
