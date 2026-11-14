"""
Tests for the unified project-invite email path (Task D).

- Both UI invite paths funnel into vc.service.invite_member_by_email ->
  vc.invite_mail.send_project_invite, so the generated message is identical.
- The email contains the invite code and project name.
- Failures report {"email_sent": False, "reason": ...} truthfully.
- An existing same-org invitee gets a COLLABORATION_INVITE notification.

Uses a temp SQLite DB (tests/conftest.py); SMTP is fully mocked — no real mail.
"""
from __future__ import annotations

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
if not os.environ.get("FORMATIFY_ENC_KEY"):
    from cryptography.fernet import Fernet

    os.environ["FORMATIFY_ENC_KEY"] = Fernet.generate_key().decode()


def _uniq(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


class _FakeSMTP:
    """Captures send_message; never touches the network."""

    sent: list = []
    fail_with: Exception | None = None

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def ehlo(self):
        pass

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        if _FakeSMTP.fail_with is not None:
            raise _FakeSMTP.fail_with
        _FakeSMTP.sent.append(msg)

    def quit(self):
        pass


@pytest.fixture()
def env(tmp_path, monkeypatch):
    import database

    database.DATABASE_URL = str(tmp_path / "invite.db")
    database.init_db()

    # Fake-but-present SMTP config; actual sending is mocked per-test.
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "bot@test.dev")
    monkeypatch.setenv("SMTP_PASSWORD", "fake-password")
    monkeypatch.setenv("SMTP_FROM", "bot@test.dev")

    import vc.invite_mail as invite_mail

    monkeypatch.setattr(invite_mail.smtplib, "SMTP", _FakeSMTP)
    _FakeSMTP.sent = []
    _FakeSMTP.fail_with = None

    conn = database.get_db()
    cur = conn.cursor()

    inviter_email = f"{_uniq('inviter')}@example.com"
    invitee_email = f"{_uniq('invitee')}@example.com"
    stranger_email = f"{_uniq('stranger')}@example.com"

    cur.execute(
        "INSERT INTO users (username, email, password_hash, role, org_id)"
        " VALUES (?, ?, 'hash', 'student', 1)",
        (_uniq("inviter"), inviter_email),
    )
    inviter_id = int(cur.lastrowid)
    cur.execute(
        "INSERT INTO users (username, email, password_hash, role, org_id)"
        " VALUES (?, ?, 'hash', 'student', 1)",
        (_uniq("invitee"), invitee_email),
    )
    invitee_id = int(cur.lastrowid)

    cur.execute("SELECT id FROM templates ORDER BY id LIMIT 1")
    template_id = int(cur.fetchone()["id"])

    cur.execute(
        """
        INSERT INTO collaboration_projects
            (name, description, template_id, created_by, invite_code, org_id)
        VALUES (?, '', ?, ?, ?, 1)
        """,
        ("Invite Test Project", template_id, inviter_id, _uniq("CODE")),
    )
    project_id = int(cur.lastrowid)
    cur.execute(
        "SELECT invite_code FROM collaboration_projects WHERE id = ?",
        (project_id,),
    )
    invite_code = cur.fetchone()["invite_code"]

    cur.execute(
        "INSERT INTO project_members (project_id, user_id, role) VALUES (?, ?, 'owner')",
        (project_id, inviter_id),
    )
    conn.commit()
    conn.close()

    return SimpleNamespace(
        database=database,
        inviter_id=inviter_id,
        invitee_id=invitee_id,
        project_id=project_id,
        invite_code=invite_code,
        inviter_email=inviter_email,
        invitee_email=invitee_email,
        stranger_email=stranger_email,
    )


def _invite(env, email: str):
    import vc.service as vc_service

    return vc_service.invite_member_by_email(env.project_id, env.inviter_id, email)


def test_both_paths_produce_identical_message(env):
    """The service path and a direct send_project_invite build the same email."""
    import vc.invite_mail as invite_mail

    conn = env.database.get_db()
    inviter_name = conn.execute(
        "SELECT username FROM users WHERE id = ?", (env.inviter_id,)
    ).fetchone()["username"]
    conn.close()

    direct = invite_mail.build_invite_message(
        to_email=env.stranger_email,
        inviter_name=inviter_name,
        project_name="Invite Test Project",
        invite_code=env.invite_code,
        role="editor",
    )

    result = _invite(env, env.stranger_email)
    assert result["email_sent"] is True
    assert len(_FakeSMTP.sent) == 1
    via_api = _FakeSMTP.sent[0]

    assert via_api["Subject"] == direct["Subject"]
    assert via_api.get_body(("plain",)).get_content() == direct.get_body(("plain",)).get_content()
    assert via_api.get_body(("html",)).get_content() == direct.get_body(("html",)).get_content()


def test_email_contains_code_and_project_name(env):
    result = _invite(env, env.stranger_email)
    assert result["email_sent"] is True
    msg = _FakeSMTP.sent[-1]
    assert "Invite Test Project" in msg["Subject"]
    body = msg.get_body(("plain",)).get_content()
    assert env.invite_code in body
    assert "Invite Test Project" in body
    html_part = msg.get_body(("html",)).get_content()
    assert env.invite_code in html_part


def test_smtp_not_configured_returns_reason(env, monkeypatch):
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    result = _invite(env, env.stranger_email)
    assert result["email_sent"] is False
    assert result["email_reason"] == "SMTP not configured"
    assert result["status"] == "invite_email_failed"
    assert "email failed" in result["message"]


def test_send_failure_returns_reason(env):
    import smtplib

    _FakeSMTP.fail_with = smtplib.SMTPException("boom")
    result = _invite(env, env.stranger_email)
    assert result["email_sent"] is False
    assert result["email_reason"] == "send failed: SMTPException"
    _FakeSMTP.fail_with = None


def test_existing_user_gets_notification(env):
    result = _invite(env, env.invitee_email)
    assert result["email_sent"] is True
    assert result["account_exists"] is True

    conn = env.database.get_db()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? AND type = 'collaboration_invite'",
        (env.invitee_id,),
    ).fetchall()
    conn.close()
    assert rows, "invitee should have a collaboration_invite notification"
    import json as _json

    payload = _json.loads(rows[-1]["payload_json"])
    assert payload["screen"] == "collaboration"
    assert payload["project_id"] == env.project_id


def test_unknown_email_reports_no_account(env):
    result = _invite(env, env.stranger_email)
    assert result["email_sent"] is True
    assert result["account_exists"] is False
    assert "no account yet" in result["message"]

    conn = env.database.get_db()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE type = 'collaboration_invite'"
        " AND payload_json LIKE ?",
        (f'%"project_id": {env.project_id}%',),
    ).fetchall()
    conn.close()
    # Only the registered invitee (previous test) may have a row for this project.
    assert all(r["user_id"] == env.invitee_id for r in rows)
