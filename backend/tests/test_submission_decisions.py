"""
Regression tests: decided / superseded final submissions must leave the
supervisor pending queue immediately.

Root cause covered here: create_final_submission inserts a NEW pending row per
submission and never closes earlier pending rows for the same group, so the
pending list (GET /supervisor/submissions?status=pending) and the
/supervisor/home "documents_to_review" counter kept counting stale rows —
identical filenames made decided work look undecided.

Fix under test:
- pending list returns only the newest submission per group that is still
  pending (older pending rows stay reachable via status=all / decided filters).
- status=revision_requested is accepted as an alias for stored 'revision'.
- decisions stay idempotent (409 on second decision) and still notify.

Uses a temp SQLite DB (tests/conftest.py); never touches formatify.db.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

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
    tmp = tmp_path_factory.mktemp("sub_decisions")
    db_path = tmp / "decisions.db"

    import database

    database.DATABASE_URL = str(db_path)
    database.init_db()

    import main as main_mod  # noqa: F401

    conn = database.get_db()
    cur = conn.cursor()

    stu_email = f"{_uniq('dec_stu')}@example.com"
    sup_email = f"{_uniq('dec_sup')}@example.com"

    cur.execute(
        "INSERT INTO users (username, email, password_hash, role, org_id)"
        " VALUES (?, ?, 'hash', 'student', 1)",
        (_uniq("dec_student"), stu_email),
    )
    student_id = int(cur.lastrowid)
    cur.execute(
        "INSERT INTO users (username, email, password_hash, role, org_id)"
        " VALUES (?, ?, 'hash', 'supervisor', 1)",
        (_uniq("dec_supervisor"), sup_email),
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
        " VALUES ('Dec Sup', ?, ?, 6, 0, 1, 1)",
        (sup_email, dept_id),
    )
    supervisor_id = int(cur.lastrowid)

    group_ids = []
    for i in range(3):
        cur.execute(
            """
            INSERT INTO fyp_groups
                (supervisor_id, title, project_title, status, progress,
                 student_contact_email, member_names, org_id)
            VALUES (?, ?, ?, 'accepted', 0, ?, ?, 1)
            """,
            (
                supervisor_id,
                f"Dec Group {i}",
                f"Topic {i}",
                stu_email,
                f'["Student <{stu_email}>"]',
            ),
        )
        group_ids.append(int(cur.lastrowid))

    conn.commit()
    conn.close()

    return SimpleNamespace(
        database=database,
        student_id=student_id,
        supervisor_user_id=supervisor_user_id,
        supervisor_id=supervisor_id,
        group_ids=group_ids,
        student_email=stu_email,
    )


def _make_group(env, index: int) -> int:
    conn = env.database.get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO fyp_groups
            (supervisor_id, title, project_title, status, progress,
             student_contact_email, member_names, org_id)
        VALUES (?, ?, ?, 'accepted', 0, ?, ?, 1)
        """,
        (
            env.supervisor_id,
            f"Extra Group {index}",
            f"Extra Topic {index}",
            env.student_email,
            f'["Student <{env.student_email}>"]',
        ),
    )
    gid = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return gid


def _insert_submission(env, group_id: int, title: str = "FORMATIFY.docx") -> int:
    conn = env.database.get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO final_submissions
            (group_id, supervisor_id, title, filename, status,
             student_contact_email, org_id)
        VALUES (?, ?, ?, ?, 'pending', ?, 1)
        """,
        (group_id, env.supervisor_id, title, title, env.student_email),
    )
    sid = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return sid


def _pending_ids(env, status: str = "pending") -> list[int]:
    import routes.supervisor_routes as sup

    result = sup.list_final_submissions(
        user_id=env.supervisor_user_id, status=status
    )
    return [s["id"] for s in result["submissions"]]


def _notifications_for(env, user_id: int, ntype: str):
    conn = env.database.get_db()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? AND type = ? ORDER BY id",
        (user_id, ntype),
    ).fetchall()
    conn.close()
    return rows


def test_pending_lists_only_newest_per_group(env):
    """Two pending submissions in one group: only the newest awaits review."""
    import routes.supervisor_routes as sup

    gid = env.group_ids[0]
    old = _insert_submission(env, gid, "old.docx")
    new = _insert_submission(env, gid, "new.docx")

    ids = _pending_ids(env)
    assert new in ids
    assert old not in ids, "stale pending row must not await decision"

    home = sup.get_supervisor_home(user_id=env.supervisor_user_id)
    # group0 contributes 1 (newest only); groups 1 and 2 have no submissions yet
    assert home["documents_to_review"] == 1


def test_decisions_remove_submissions_from_pending(env):
    import routes.supervisor_routes as sup

    # One group per decision so each pending row is the newest of its group.
    gid_a = _make_group(env, "a")
    gid_b = _make_group(env, "b")
    gid_c = _make_group(env, "c")
    s_approve = _insert_submission(env, gid_a, "approve.docx")
    s_revision = _insert_submission(env, gid_b, "revision.docx")
    s_reject = _insert_submission(env, gid_c, "reject.docx")

    before = set(_pending_ids(env))
    assert {s_approve, s_revision, s_reject} <= before

    sup.approve_final_submission(
        s_approve, user_id=env.supervisor_user_id, payload={"note": "ok"}
    )
    sup.request_revision_final_submission(
        s_revision, user_id=env.supervisor_user_id, payload={"note": "fix"}
    )
    sup.reject_final_submission(
        s_reject, user_id=env.supervisor_user_id, payload={"note": "no"}
    )

    after = _pending_ids(env)
    assert s_approve not in after
    assert s_revision not in after
    assert s_reject not in after
    # group0's `new` pending row from the previous test may still be listed.
    assert set(after) <= {s for s in after if s not in {s_approve, s_revision, s_reject}}

    # History filters still return the decided rows.
    assert _pending_ids(env, "approved") == [s_approve]
    assert _pending_ids(env, "revision_requested") == [s_revision]
    assert _pending_ids(env, "revision") == [s_revision]
    assert _pending_ids(env, "rejected") == [s_reject]
    all_ids = set(_pending_ids(env, "all"))
    assert {s_approve, s_revision, s_reject} <= all_ids

    # Count the pending rows the list actually returns — must match.
    home = sup.get_supervisor_home(user_id=env.supervisor_user_id)
    assert home["documents_to_review"] == len(after)


def test_decision_is_idempotent_and_notifies(env):
    import routes.supervisor_routes as sup

    gid = env.group_ids[0]
    sid = _insert_submission(env, gid, "once.docx")
    sup.approve_final_submission(
        sid, user_id=env.supervisor_user_id, payload={}
    )

    with pytest.raises(HTTPException) as exc:
        sup.approve_final_submission(
            sid, user_id=env.supervisor_user_id, payload={}
        )
    assert exc.value.status_code == 409

    with pytest.raises(HTTPException) as exc2:
        sup.reject_final_submission(
            sid, user_id=env.supervisor_user_id, payload={"note": "x"}
        )
    assert exc2.value.status_code == 409

    rows = _notifications_for(env, env.student_id, "submission_approved")
    assert rows and rows[-1]["related_id"] == sid
