"""
Regression tests for the "database is locked" notification loss.

Root cause: notify() opens its own sqlite connection. When a request handler
still holds an uncommitted write transaction, the notification INSERT fails
with sqlite3.OperationalError: database is locked and the row is silently
dropped (notify() never raises).

Fix under test:
- Callers collect notification kwargs inside the transaction and send them
  AFTER conn.commit() (supervisor_routes._create_notification +
  _flush_notifications; student_routes pending_notifications lists).
- notify() retries on lock errors and accepts an optional caller conn.

Uses a temp SQLite DB (tests/conftest.py redirects DATABASE_URL); never
touches the shared formatify.db.
"""
from __future__ import annotations

import os
import sys
import time
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
    tmp = tmp_path_factory.mktemp("notif_lock")
    db_path = tmp / "lock.db"

    import database

    database.DATABASE_URL = str(db_path)
    database.init_db()

    import main as main_mod  # noqa: F401  (ensures app modules import cleanly)

    conn = database.get_db()
    cur = conn.cursor()

    stu_email = f"{_uniq('lock_stu')}@example.com"
    sup_email = f"{_uniq('lock_sup')}@example.com"

    cur.execute(
        "INSERT INTO users (username, email, password_hash, role, org_id)"
        " VALUES (?, ?, 'hash', 'student', 1)",
        (_uniq("lock_student"), stu_email),
    )
    student_id = int(cur.lastrowid)
    cur.execute(
        "INSERT INTO users (username, email, password_hash, role, org_id)"
        " VALUES (?, ?, 'hash', 'supervisor', 1)",
        (_uniq("lock_supervisor"), sup_email),
    )
    supervisor_user_id = int(cur.lastrowid)

    cur.execute("SELECT id FROM departments ORDER BY id LIMIT 1")
    dept = cur.fetchone()
    if dept:
        dept_id = int(dept["id"])
    else:
        cur.execute(
            "INSERT INTO departments (name, code, org_id) VALUES ('CS', 'CS', 1)"
        )
        dept_id = int(cur.lastrowid)

    cur.execute(
        "INSERT INTO supervisors (name, email, department_id, max_groups,"
        " current_groups, is_active, org_id)"
        " VALUES ('Lock Sup', ?, ?, 6, 0, 1, 1)",
        (sup_email, dept_id),
    )
    supervisor_id = int(cur.lastrowid)

    cur.execute(
        """
        INSERT INTO fyp_groups
            (supervisor_id, title, project_title, status, progress,
             student_contact_email, member_names, org_id)
        VALUES (?, 'Lock Group', 'Lock Topic', 'accepted', 0, ?, ?, 1)
        """,
        (supervisor_id, stu_email, f'["Student <{stu_email}>"]'),
    )
    group_id = int(cur.lastrowid)

    conn.commit()
    conn.close()

    return SimpleNamespace(
        database=database,
        student_id=student_id,
        supervisor_user_id=supervisor_user_id,
        supervisor_id=supervisor_id,
        group_id=group_id,
        student_email=stu_email,
        supervisor_email=sup_email,
    )


def _notifications_for(user_id: int, ntype: str):
    conn = env_db.get_db()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? AND type = ? ORDER BY id",
        (user_id, ntype),
    ).fetchall()
    conn.close()
    return rows


# Module-level alias so helpers above stay short; set in each test via fixture.
env_db = None


@pytest.fixture(autouse=True)
def _bind_env(env):
    global env_db
    env_db = env.database
    yield


def test_collect_then_flush_after_commit_no_lock(env):
    """Simulate a handler holding an open write transaction: collect kwargs
    via _create_notification inside the txn, commit, then flush — the row
    must exist and the whole path must finish well under a lock timeout."""
    import routes.supervisor_routes as sup

    conn = env.database.get_db()
    cur = conn.cursor()
    # Open write transaction (uncommitted) — this is what used to break notify().
    cur.execute(
        "UPDATE users SET username = username WHERE id = ?",
        (env.student_id,),
    )

    start = time.monotonic()
    kwargs = sup._create_notification(
        cur,
        recipient_email=env.student_email,
        title="Simulated",
        message="sent after commit",
        notification_type="meeting_note",
        related_type="meeting_note",
        related_id=env.group_id,
        org_id=1,
    )
    assert kwargs is not None
    assert kwargs["user_id"] == env.student_id

    conn.commit()  # release the write lock BEFORE notify() runs
    sup._flush_notifications([kwargs])
    elapsed = time.monotonic() - start
    conn.close()

    assert elapsed < 2.0, f"notify path took {elapsed:.2f}s (lock timeout?)"
    rows = _notifications_for(env.student_id, "meeting_note")
    assert rows, "notification row missing after deferred flush"
    assert rows[-1]["body"] == "sent after commit"


def test_notify_with_caller_conn_writes_in_same_txn(env):
    """notify(conn=...) writes on the caller's connection without committing."""
    from services.notification_service import notify

    conn = env.database.get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET username = username WHERE id = ?",
        (env.student_id,),
    )
    nid = notify(
        org_id=1,
        user_id=env.student_id,
        type="conn_param_test",
        title="T",
        body="B",
        conn=conn,
    )
    assert nid is not None
    # visible on the caller's cursor before commit
    row = cur.execute(
        "SELECT type FROM notifications WHERE id = ?", (nid,)
    ).fetchone()
    assert row is not None and row["type"] == "conn_param_test"
    conn.commit()
    conn.close()

    rows = _notifications_for(env.student_id, "conn_param_test")
    assert rows


def test_notify_retries_through_brief_lock(env):
    """A short write lock held by another connection must not lose the row:
    busy timeout / retries carry notify() through within 2 seconds."""
    import threading

    from services.notification_service import notify

    blocker = env.database.get_db()
    blocker.execute(
        "UPDATE users SET username = username WHERE id = ?",
        (env.student_id,),
    )

    def _release():
        time.sleep(0.3)
        blocker.commit()
        blocker.close()

    t = threading.Thread(target=_release)
    t.start()
    try:
        start = time.monotonic()
        nid = notify(
            org_id=1,
            user_id=env.student_id,
            type="brief_lock_test",
            title="T",
            body="B",
        )
        elapsed = time.monotonic() - start
    finally:
        t.join()

    assert nid is not None, "notify() lost the row under a brief lock"
    assert elapsed < 2.0
    rows = _notifications_for(env.student_id, "brief_lock_test")
    assert rows


def test_student_final_submission_notifies_supervisor(env):
    """Full path: create_final_submission -> STUDENT_SUBMITTED row for the
    supervisor's user account (previously lost to 'database is locked')."""
    import routes.student_routes as stu

    result = stu.create_final_submission(
        request=None,
        user_id=env.student_id,
        payload={
            "group_id": env.group_id,
            "title": "Lock Test Final",
            "filename": "final.docx",
        },
    )
    assert result["success"] is True
    submission_id = result["submission"]["id"]

    rows = _notifications_for(env.supervisor_user_id, "student_submitted")
    assert rows, "supervisor got no student_submitted notification"
    row = rows[-1]
    assert row["related_id"] == submission_id
    assert row["entity_type"] == "final_submission"
    import json as _json

    assert _json.loads(row["payload_json"])["screen"] == "submissions"


def _make_pending_submission(env) -> int:
    conn = env.database.get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO final_submissions
            (group_id, supervisor_id, title, filename, status,
             student_contact_email, org_id)
        VALUES (?, ?, 'Pending Sub', 'p.docx', 'pending', ?, 1)
        """,
        (env.group_id, env.supervisor_id, env.student_email),
    )
    sid = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return sid


def test_supervisor_decisions_notify_student(env):
    """approve / request-revision / reject each notify the student."""
    import routes.supervisor_routes as sup

    expected = {
        "approved": "submission_approved",
        "revision": "submission_revision_requested",
        "rejected": "submission_rejected",
    }
    for new_status, ntype in expected.items():
        sid = _make_pending_submission(env)
        if new_status == "approved":
            sup.approve_final_submission(sid, user_id=env.supervisor_user_id, payload={})
        elif new_status == "revision":
            sup.request_revision_final_submission(
                sid, user_id=env.supervisor_user_id, payload={"note": "fix it"}
            )
        else:
            sup.reject_final_submission(
                sid, user_id=env.supervisor_user_id, payload={"note": "no"}
            )

        rows = _notifications_for(env.student_id, ntype)
        assert rows, f"student got no {ntype} notification"
        row = rows[-1]
        assert row["related_id"] == sid
        assert row["entity_type"] == "final_submission"
