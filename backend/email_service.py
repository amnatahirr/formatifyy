"""SMTP email helper with professional HTML templates."""
from __future__ import annotations

import logging
import os
import smtplib
import threading
from datetime import datetime
from email.message import EmailMessage
from html import escape

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # pip install python-dotenv

logger = logging.getLogger(__name__)

BRAND_NAME = "Formatify"
BRAND_COLOR = "#4F46E5"


# ── SMTP ─────────────────────────────────────────────────────────────────────
def _config() -> dict:
    user = os.getenv("SMTP_USER", "").strip()
    return {
        "host": os.getenv("SMTP_HOST", "").strip(),
        "port": int(os.getenv("SMTP_PORT", "587") or 587),
        "user": user,
        "password": os.getenv("SMTP_PASSWORD", "").replace(" ", "").strip(),
        "sender": os.getenv("SMTP_FROM", user or "noreply@formatify.local").strip(),
    }


def _connect(cfg: dict):
    if cfg["port"] == 465:
        server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=20)
    else:
        server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=20)
        server.ehlo()
        server.starttls()
        server.ehlo()
    if cfg["user"]:
        server.login(cfg["user"], cfg["password"])
    return server


def _build_message(cfg: dict, to_email: str, subject: str, text: str, html: str | None) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{BRAND_NAME} <{cfg['sender']}>"
    msg["To"] = to_email
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


def send_emails(messages: list[tuple]) -> int:
    """messages = [(to, subject, text_body[, html_body]), ...]"""
    if not messages:
        return 0
    cfg = _config()
    if not cfg["host"]:
        logger.warning("SMTP_HOST is empty; %s email(s) skipped.", len(messages))
        print("[EMAIL] SMTP_HOST is empty, emails skipped")
        return 0

    sent = 0
    try:
        server = _connect(cfg)
        try:
            for item in messages:
                to_email, subject, text = item[0], item[1], item[2]
                html = item[3] if len(item) > 3 else None
                if not to_email:
                    continue
                try:
                    server.send_message(_build_message(cfg, to_email, subject, text, html))
                    sent += 1
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Email failed for %s", to_email)
                    print(f"[EMAIL] failed for {to_email}: {exc}")
        finally:
            try:
                server.quit()
            except Exception:  # noqa: BLE001
                pass
    except Exception as exc:  # noqa: BLE001
        logger.exception("SMTP connection/login failed")
        print(f"[EMAIL] SMTP connection/login failed: {exc}")
    print(f"[EMAIL] sent {sent}/{len(messages)}")
    return sent


def send_emails_async(messages: list[tuple]) -> None:
    if not messages:
        return
    threading.Thread(target=send_emails, args=(messages,), daemon=True).start()


# ── HTML templates ───────────────────────────────────────────────────────────
def _pretty_date(raw: str) -> str:
    try:
        return datetime.strptime(str(raw)[:10], "%Y-%m-%d").strftime("%A, %d %B %Y")
    except ValueError:
        return str(raw)


def _wrap_html(*, accent: str, badge: str, heading: str, greeting: str,
               intro: str, title: str, due: str, description: str, closing: str) -> str:
    desc_block = ""
    if description:
        desc_block = (
            '<tr><td style="padding-top:14px;font-size:14px;line-height:22px;color:#4B5563;">'
            f'{escape(description)}</td></tr>'
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;padding:0;background-color:#F3F4F6;font-family:Segoe UI,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#F3F4F6;padding:24px 12px;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background-color:#FFFFFF;border-radius:14px;overflow:hidden;">
        <tr>
          <td style="background-color:{BRAND_COLOR};padding:24px 32px;">
            <span style="font-size:22px;font-weight:700;color:#FFFFFF;letter-spacing:0.5px;">{BRAND_NAME}</span>
            <span style="font-size:13px;color:#C7D2FE;margin-left:8px;">Academic Project Portal</span>
          </td>
        </tr>
        <tr>
          <td style="padding:32px;">
            <span style="display:inline-block;background-color:{accent};color:#FFFFFF;font-size:12px;font-weight:700;letter-spacing:0.8px;padding:5px 12px;border-radius:20px;">{escape(badge)}</span>
            <h1 style="margin:16px 0 8px 0;font-size:22px;line-height:30px;color:#111827;">{escape(heading)}</h1>
            <p style="margin:0 0 20px 0;font-size:15px;line-height:24px;color:#374151;">{escape(greeting)}<br>{escape(intro)}</p>
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#F9FAFB;border:1px solid #E5E7EB;border-left:5px solid {accent};border-radius:8px;">
              <tr><td style="padding:18px 20px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                  <tr><td style="font-size:12px;color:#6B7280;text-transform:uppercase;letter-spacing:0.8px;">Deadline</td></tr>
                  <tr><td style="font-size:18px;font-weight:700;color:#111827;padding-top:4px;">{escape(title)}</td></tr>
                  <tr><td style="padding-top:14px;font-size:12px;color:#6B7280;text-transform:uppercase;letter-spacing:0.8px;">Due date</td></tr>
                  <tr><td style="font-size:16px;font-weight:600;color:{accent};padding-top:4px;">{escape(due)}</td></tr>
                  {desc_block}
                </table>
              </td></tr>
            </table>
            <p style="margin:24px 0 0 0;font-size:14px;line-height:22px;color:#374151;">{escape(closing)}</p>
          </td>
        </tr>
        <tr>
          <td style="background-color:#F9FAFB;border-top:1px solid #E5E7EB;padding:18px 32px;font-size:12px;line-height:18px;color:#9CA3AF;">
            This is an automated message from {BRAND_NAME}. Please do not reply to this email.<br>
            You are receiving this because you are registered as a student on the platform.
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def build_deadline_email(
    *,
    title: str,
    due_date: str,
    description: str = "",
    name: str = "",
    days_left: int | None = None,
) -> tuple[str, str, str]:
    """Returns (subject, text_body, html_body).

    days_left=None  -> "new deadline" email (sent when admin creates it)
    days_left=int   -> reminder (<=0 today, 1 tomorrow, else N days)
    """
    due = _pretty_date(due_date)
    greeting = f"Dear {name}," if name else "Dear Student,"
    description = (description or "").strip()

    if days_left is None:
        accent, badge = "#2563EB", "NEW DEADLINE"
        subject = f"New Deadline: {title}"
        heading = "A new deadline has been scheduled"
        intro = "A new submission deadline has been added for you. Please find the details below."
        closing = "Please plan your work in advance and make sure you submit before the due date."
    else:
        if days_left <= 0:
            accent, badge, when = "#DC2626", "DUE TODAY", "is due today"
            subject = f"Due Today: {title}"
        elif days_left == 1:
            accent, badge, when = "#EA580C", "DUE TOMORROW", "is due tomorrow"
            subject = f"Due Tomorrow: {title}"
        else:
            accent, badge, when = "#D97706", f"{days_left} DAYS LEFT", f"is due in {days_left} days"
            subject = f"Reminder: {title} is due in {days_left} days"
        heading = "Deadline reminder"
        intro = f'This is a friendly reminder that "{title}" {when}.'
        closing = "Please make sure your submission is completed on time to avoid any penalties."

    text = (
        f"{greeting}\n\n{intro}\n\n"
        f"Deadline : {title}\n"
        f"Due date : {due}\n"
        + (f"Details  : {description}\n" if description else "")
        + f"\n{closing}\n\n— {BRAND_NAME}\n"
    )
    html = _wrap_html(
        accent=accent, badge=badge, heading=heading, greeting=greeting,
        intro=intro, title=title, due=due, description=description, closing=closing,
    )
    return subject, text, html


# ── Test email ───────────────────────────────────────────────────────────────
def send_test_email(to_email: str) -> dict:
    cfg = _config()
    info = {
        "host": cfg["host"], "port": cfg["port"], "user": cfg["user"],
        "password_set": bool(cfg["password"]), "from": cfg["sender"],
    }
    if not cfg["host"]:
        return {"ok": False, "error": "SMTP_HOST is empty (.env not loaded)", "config": info}
    try:
        subject, text, html = build_deadline_email(
            title="Sample Deadline (Test Email)",
            due_date=datetime.now().strftime("%Y-%m-%d"),
            description="If you can see this email, your email setup is working correctly.",
            name="Student",
            days_left=1,
        )
        server = _connect(cfg)
        server.send_message(_build_message(cfg, to_email, subject, text, html))
        server.quit()
        return {"ok": True, "config": info}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "config": info}