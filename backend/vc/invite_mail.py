"""SMTP helpers for collaboration invite emails (HTML + plain-text)."""

from __future__ import annotations

import html
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Always load backend/.env (safe if already loaded by main.py)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _smtp_settings() -> dict:
    host = (os.getenv("SMTP_HOST") or "smtp.gmail.com").strip()
    port_raw = (os.getenv("SMTP_PORT") or "587").strip()
    user = (os.getenv("SMTP_USER") or "").strip()
    password = (os.getenv("SMTP_PASSWORD") or "").strip()
    from_addr = (os.getenv("SMTP_FROM") or user).strip()

    try:
        port = int(port_raw)
    except ValueError as exc:
        raise RuntimeError(f"Invalid SMTP_PORT: {port_raw!r}") from exc

    if not user or not password:
        raise RuntimeError(
            "SMTP is not configured. Set SMTP_USER and SMTP_PASSWORD in backend/.env"
        )
    if not from_addr:
        raise RuntimeError("SMTP_FROM (or SMTP_USER) must be set in backend/.env")

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "from_addr": from_addr,
    }


def smtp_missing_vars() -> list[str]:
    """Names of required SMTP env vars that are unset/empty (never values)."""
    missing = []
    for var in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"):
        if not (os.getenv(var) or "").strip():
            missing.append(var)
    return missing


def build_invite_email_text(
    *,
    inviter_name: str,
    project_name: str,
    invite_code: str,
    role: str | None = None,
) -> str:
    """Plain-text fallback for clients that don't render HTML."""
    role_line = f"Your role: {role}\n\n" if role else ""
    return (
        "Formatify\n\n"
        "You're invited to collaborate\n\n"
        f"{inviter_name} invited you to join the project\n"
        f'"{project_name}"\n\n'
        f"{role_line}"
        "Your invite code:\n"
        f"  {invite_code}\n\n"
        "How to join:\n"
        "1. Open Formatify\n"
        "2. Go to Collaboration → Join Project\n"
        "3. Enter the invite code above\n\n"
        "Don't have an account? Sign up first, then use this code.\n\n"
        "— The Formatify Team\n"
    )


def build_invite_email_html(
    *,
    inviter_name: str,
    project_name: str,
    invite_code: str,
    role: str | None = None,
) -> str:
    """Approved light-theme HTML invite layout (inline CSS for email clients)."""
    safe_inviter = html.escape(inviter_name)
    safe_project = html.escape(project_name)
    safe_code = html.escape(invite_code)
    role_block = ""
    if role:
        role_block = f"""
              <p style="margin:12px 0 0 0;font-size:14px;color:#475569;">
                Your role: <strong style="color:#0f172a;">{html.escape(role)}</strong>
              </p>"""

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>You're invited to collaborate</title>
</head>
<body style="margin:0;padding:0;background:#f4f6f8;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f8;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;">
          <tr>
            <td style="padding:28px 32px 12px 32px;">
              <div style="font-size:20px;font-weight:700;letter-spacing:-0.02em;color:#4f46e5;">
                Formatify
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 32px 0 32px;">
              <h1 style="margin:0;font-size:24px;line-height:1.3;font-weight:700;color:#0f172a;">
                You're invited to collaborate
              </h1>
            </td>
          </tr>
          <tr>
            <td style="padding:16px 32px 0 32px;color:#334155;font-size:15px;line-height:1.6;">
              <p style="margin:0 0 12px 0;">
                <strong style="color:#0f172a;">{safe_inviter}</strong>
                invited you to join the project
              </p>
              <p style="margin:0;font-size:17px;font-weight:600;color:#0f172a;">
                {safe_project}
              </p>{role_block}
            </td>
          </tr>
          <tr>
            <td style="padding:24px 32px 8px 32px;">
              <div style="font-size:12px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;color:#64748b;margin-bottom:10px;">
                Your invite code
              </div>
              <div style="background:#f1f5f9;border:1px solid #cbd5e1;border-radius:10px;padding:18px 16px;text-align:center;">
                <span style="font-family:Consolas,'Courier New',monospace;font-size:28px;font-weight:700;letter-spacing:0.12em;color:#0f172a;">
                  {safe_code}
                </span>
              </div>
              <div style="margin-top:10px;font-size:12px;color:#64748b;text-align:center;">
                Copy and paste this code exactly as shown
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding:24px 32px 8px 32px;color:#334155;font-size:15px;line-height:1.6;">
              <div style="font-size:14px;font-weight:700;color:#0f172a;margin-bottom:12px;">
                How to join
              </div>
              <ol style="margin:0;padding-left:20px;">
                <li style="margin:0 0 10px 0;">Open Formatify</li>
                <li style="margin:0 0 10px 0;">Go to Collaboration → Join Project</li>
                <li style="margin:0;">Enter the invite code above</li>
              </ol>
              <p style="margin:18px 0 0 0;color:#475569;font-size:14px;">
                Don't have an account? Sign up first, then use this code.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:28px 32px 32px 32px;border-top:1px solid #e2e8f0;">
              <div style="font-size:13px;color:#64748b;">
                — The Formatify Team
              </div>
            </td>
          </tr>
        </table>
        <div style="max-width:560px;margin:16px auto 0;font-size:11px;color:#94a3b8;text-align:center;">
          You received this because someone invited you to a Formatify project.
        </div>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def build_invite_message(
    *,
    to_email: str,
    inviter_name: str,
    project_name: str,
    invite_code: str,
    role: str | None = None,
) -> EmailMessage:
    """Build the full invite EmailMessage (subject + text + HTML)."""
    settings = _smtp_settings()
    subject = f'You\'re invited to collaborate on "{project_name}" in Formatify'
    text_body = build_invite_email_text(
        inviter_name=inviter_name,
        project_name=project_name,
        invite_code=invite_code,
        role=role,
    )
    html_body = build_invite_email_html(
        inviter_name=inviter_name,
        project_name=project_name,
        invite_code=invite_code,
        role=role,
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings["from_addr"]
    msg["To"] = to_email
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    return msg


def _deliver(msg: EmailMessage) -> None:
    """Send a built message via SMTP. Raises on failure."""
    settings = _smtp_settings()
    context = ssl.create_default_context()
    with smtplib.SMTP(settings["host"], settings["port"], timeout=30) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(settings["user"], settings["password"])
        server.send_message(msg)


def send_project_invite(
    *,
    to_email: str,
    inviter_name: str,
    project_name: str,
    invite_code: str,
    role: str = "editor",
) -> dict:
    """Single invite-email path for every UI entry point.

    Sends synchronously and reports the real outcome — never raises.
    Returns {"email_sent": bool, "reason": str}.
    """
    try:
        msg = build_invite_message(
            to_email=to_email,
            inviter_name=inviter_name,
            project_name=project_name,
            invite_code=invite_code,
            role=role,
        )
    except RuntimeError as exc:
        reason = "SMTP not configured" if "not configured" in str(exc) else f"send failed: {type(exc).__name__}"
        logger.warning("Project invite email not sent to %s: %s", to_email, reason)
        return {"email_sent": False, "reason": reason}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to build project invite email for %s", to_email)
        return {"email_sent": False, "reason": f"send failed: {type(exc).__name__}"}

    try:
        _deliver(msg)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to send project invite email to %s", to_email)
        reason = (
            "SMTP not configured"
            if isinstance(exc, RuntimeError) and "not configured" in str(exc)
            else f"send failed: {type(exc).__name__}"
        )
        return {"email_sent": False, "reason": reason}

    return {"email_sent": True, "reason": ""}


def send_invite_email(
    *,
    to_email: str,
    inviter_name: str,
    project_name: str,
    invite_code: str,
) -> None:
    """Send a project invite-code email via configured SMTP (Gmail App Password).

    Legacy raising variant kept for backwards compatibility — new code should
    use send_project_invite() which reports {email_sent, reason}.
    """
    msg = build_invite_message(
        to_email=to_email,
        inviter_name=inviter_name,
        project_name=project_name,
        invite_code=invite_code,
    )
    _deliver(msg)


def smtp_configured() -> bool:
    """True when minimum credentials appear to be present."""
    user = (os.getenv("SMTP_USER") or "").strip()
    password = (os.getenv("SMTP_PASSWORD") or "").strip()
    return bool(user and password)
