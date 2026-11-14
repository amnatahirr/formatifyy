"""
Tests for submission review emails (submission_mail.py).

Covers: builders (subject/text/html, escaping), send_email_safe outcomes,
the create_final_submission -> supervisor email wiring, and the
decision -> student emails wiring. SMTP is always mocked; temp DB only.
"""
from __future__ import annotations

import os
import sys
import threading
import time
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
    tmp = tmp_path_factory.mktemp("sub_mail")
    db_path = tmp / "mail.db"

    import database

    database.DATABASE_URL = str(db_path)
    database.init_db()

    import main as main_mod  # noqa: F401

    conn = database.get_db()
    cur = conn.cursor()

    stu_email = f"{_uniq('mail_stu')}@example.com"
    sup_email = f"{_uniq('mail_sup')}@example.com"
    stu_name = _uniq("mailstudent")

    cur.execute(
        "INSERT INTO users (username, email, password_hash, role, org_id)"
        " VALUES (?, ?, 'hash', 'student', 1)",
        (stu_name, stu_email),
    )
    student_id = int(cur.lastrowid)
    cur.execute(
        "INSERT INTO users (username, email, password_hash, role, org_id)"
        " VALUES (?, ?, 'hash', 'supervisor', 1)",
        (_uniq("mail_supervisor"), sup_email),
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
        " VALUES ('Mail Sup', ?, ?, 6, 0, 1, 1)",
        (sup_email, dept_id),
    )
    supervisor_id = int(cur.lastrowid)

    cur.execute(
        """
        INSERT INTO fyp_groups
            (supervisor_id, title, project_title, status, progress,
             student_contact_email, member_names, org_id)
        VALUES (?, 'Mail Group', 'Mail Topic', 'accepted', 0, ?, ?, 1)
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
        student_name=stu_name,
        supervisor_email=sup_email,
    )


def _insert_submission(env, title: str = "doc.docx") -> int:
    conn = env.database.get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO final_submissions
            (group_id, supervisor_id, title, filename, status,
             student_contact_email, org_id)
        VALUES (?, ?, ?, ?, 'pending', ?, 1)
        """,
        (env.group_id, env.supervisor_id, title, title, env.student_email),
    )
    sid = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return sid


class _FakeSMTP:
    """Captures send_message calls; can be told to raise."""

    def __init__(self, fail: bool = False):
        self.sent: list = []
        self.fail = fail

    def send_message(self, msg):
        if self.fail:
            raise RuntimeError("smtp boom")
        self.sent.append(msg)

    def quit(self):
        pass


@pytest.fixture
def captured_smtp(monkeypatch):
    """Replace email_service._connect with a fake; returns the fake."""
    import email_service

    fake = _FakeSMTP()
    monkeypatch.setattr(email_service, "_connect", lambda cfg: fake)
    # Ensure env looks configured regardless of the developer's .env.
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_USER", "u@test")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    return fake


def _wait_for(predicate, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


# ── Builders ────────────────────────────────────────────────────────────────

def test_build_submission_email_shape():
    import submission_mail

    subject, text, html = submission_mail.build_submission_email(
        supervisor_name="Sup",
        student_name="Stu",
        group_name="G1",
        project_title="Topic",
        file_name="final.docx",
        submitted_at="2026-01-01 10:00:00",
        plagiarism_score=12.5,
        compliance_score=88.0,
        grammar_count=3,
    )
    assert subject == "New submission to review: final.docx (G1)"
    assert "final.docx" in text and "Stu" in text and "12.5%" in text
    assert "final.docx" in html and "NEW SUBMISSION" in html


def test_build_decision_email_subjects_and_escaping():
    import submission_mail

    for decision, expected in [
        ("approved", "Your submission was approved: f.docx"),
        ("revision_requested", "Revision requested on your submission: f.docx"),
        ("revision", "Revision requested on your submission: f.docx"),
        ("rejected", "Your submission was rejected: f.docx"),
    ]:
        subject, text, html = submission_mail.build_decision_email(
            student_name="Stu",
            supervisor_name="Sup",
            file_name="f.docx",
            decision=decision,
            note="fix <script>alert(1)</script> & stuff",
            decided_at="2026-01-02 09:00:00",
        )
        assert subject == expected
        assert "fix <script>alert(1)</script> & stuff" in text
        assert "&lt;script&gt;" in html and "<script>" not in html

    # Empty note -> placeholder in both parts.
    _, text, html = submission_mail.build_decision_email(
        student_name="", supervisor_name="Sup", file_name="f.docx",
        decision="approved", note="", decided_at="",
    )
    assert "No comment provided" in text and "No comment provided" in html


# ── send_email_safe ─────────────────────────────────────────────────────────

def test_send_email_safe_not_configured(monkeypatch):
    import submission_mail

    monkeypatch.setenv("SMTP_HOST", "")
    monkeypatch.setenv("SMTP_USER", "")
    monkeypatch.setenv("SMTP_PASSWORD", "")
    result = submission_mail.send_email_safe("a@b.c", "s", "t", "<p>h</p>")
    assert result == {"email_sent": False, "reason": "SMTP not configured"}


def test_send_email_safe_failure_never_raises(monkeypatch):
    import email_service
    import submission_mail

    def _boom(cfg):
        raise OSError("connection refused")

    monkeypatch.setattr(email_service, "_connect", _boom)
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_USER", "u@test")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    result = submission_mail.send_email_safe("a@b.c", "s", "t", "<p>h</p>")
    assert result["email_sent"] is False
    assert result["reason"].startswith("send failed:")


def test_send_email_safe_success(captured_smtp):
    import submission_mail

    result = submission_mail.send_email_safe("a@b.c", "Subject X", "body", "<p>hi</p>")
    assert result == {"email_sent": True, "reason": ""}
    assert len(captured_smtp.sent) == 1
    msg = captured_smtp.sent[0]
    assert msg["Subject"] == "Subject X"
    assert msg["To"] == "a@b.c"


# ── Wiring: student submission -> supervisor email ──────────────────────────

def test_submission_emails_supervisor(env, captured_smtp):
    import routes.student_routes as stu

    before = len(captured_smtp.sent)
    result = stu.create_final_submission(
        request=None,
        user_id=env.student_id,
        payload={
            "group_id": env.group_id,
            "title": "Mail Test Final",
            "filename": "mail_final.docx",
        },
    )
    assert result["success"] is True

    assert _wait_for(lambda: len(captured_smtp.sent) > before)
    msg = captured_smtp.sent[-1]
    assert msg["To"] == env.supervisor_email
    assert "mail_final.docx" in msg["Subject"]
    assert env.student_name in msg.get_body(("plain",)).get_content()


def test_submission_email_survives_smtp_failure(env, monkeypatch):
    """A failing SMTP must not delay or break the submission response."""
    import email_service
    import routes.student_routes as stu

    def _boom(cfg):
        raise OSError("smtp down")

    monkeypatch.setattr(email_service, "_connect", _boom)
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_USER", "u@test")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")

    start = time.monotonic()
    result = stu.create_final_submission(
        request=None,
        user_id=env.student_id,
        payload={
            "group_id": env.group_id,
            "title": "Failing SMTP Final",
            "filename": "fail.docx",
        },
    )
    elapsed = time.monotonic() - start
    assert result["success"] is True
    assert elapsed < 5.0


# ── Wiring: decision -> student emails ──────────────────────────────────────

def test_decision_emails_students(env, captured_smtp, monkeypatch):
    import routes.supervisor_routes as sup

    sid = _insert_submission(env, "decide_me.docx")
    before = len(captured_smtp.sent)
    sup.approve_final_submission(
        sid, user_id=env.supervisor_user_id,
        payload={"note": "looks good <b>now</b>"},
    )
    assert _wait_for(lambda: len(captured_smtp.sent) > before)
    msg = captured_smtp.sent[-1]
    assert msg["To"] == env.student_email
    assert "Your submission was approved: decide_me.docx" == msg["Subject"]
    body = msg.get_body(("plain",)).get_content()
    assert "looks good <b>now</b>" in body
    html_part = msg.get_body(("html",)).get_content()
    assert "&lt;b&gt;" in html_part


def test_revision_and_reject_email_subjects(env, captured_smtp):
    import routes.supervisor_routes as sup

    sid1 = _insert_submission(env, "rev.docx")
    sup.request_revision_final_submission(
        sid1, user_id=env.supervisor_user_id, payload={"note": "revise"},
    )
    sid2 = _insert_submission(env, "rej.docx")
    sup.reject_final_submission(
        sid2, user_id=env.supervisor_user_id, payload={"note": "nope"},
    )

    def _subjects():
        return [m["Subject"] for m in captured_smtp.sent]

    assert _wait_for(
        lambda: "Revision requested on your submission: rev.docx" in _subjects()
        and "Your submission was rejected: rej.docx" in _subjects()
    )


def test_second_decision_sends_no_email(env, captured_smtp):
    import routes.supervisor_routes as sup

    sid = _insert_submission(env, "once.docx")
    sup.approve_final_submission(sid, user_id=env.supervisor_user_id, payload={})
    time.sleep(0.3)  # let the first email land
    before = len(captured_smtp.sent)

    with pytest.raises(HTTPException) as exc:
        sup.approve_final_submission(
            sid, user_id=env.supervisor_user_id, payload={},
        )
    assert exc.value.status_code == 409
    time.sleep(0.3)
    assert len(captured_smtp.sent) == before


def test_missing_supervisor_email_skips(captured_smtp):
    import submission_mail

    submission_mail.queue_submission_received_email(
        submission_id=1, org_id=1, supervisor_name="", supervisor_email="",
        student_name="s", group_name="g", project_title="p",
        file_name="f.docx",
    )
    time.sleep(0.2)
    assert captured_smtp.sent == []


def test_smtp_not_configured_route_still_succeeds(env, monkeypatch):
    """With SMTP env cleared, send_email_safe reports not-configured and the
    decision endpoint still succeeds."""
    import routes.supervisor_routes as sup

    monkeypatch.setenv("SMTP_HOST", "")
    monkeypatch.setenv("SMTP_USER", "")
    monkeypatch.setenv("SMTP_PASSWORD", "")

    sid = _insert_submission(env, "nocfg.docx")
    result = sup.approve_final_submission(
        sid, user_id=env.supervisor_user_id, payload={},
    )
    assert result["success"] is True
