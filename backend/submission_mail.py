"""Submission review emails: new submission -> supervisor, decision -> students.

Builds branded HTML + plain-text messages and sends them via the shared
SMTP config in email_service. Every public entry point is fail-safe:
email problems are logged and reported, never raised into the request path.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from html import escape

import email_service

logger = logging.getLogger(__name__)

BRAND_NAME = email_service.BRAND_NAME
BRAND_COLOR = email_service.BRAND_COLOR

_DECISION_META = {
    "approved": {
        "label": "APPROVED",
        "accent": "#16A34A",
        "subject": "Your submission was approved: {file}",
        "next_step": "No action is needed — your supervisor approved this submission.",
    },
    "revision_requested": {
        "label": "REVISION REQUESTED",
        "accent": "#D97706",
        "subject": "Revision requested on your submission: {file}",
        "next_step": "Please revise the document and submit it again.",
    },
    "rejected": {
        "label": "REJECTED",
        "accent": "#DC2626",
        "subject": "Your submission was rejected: {file}",
        "next_step": "Please contact your supervisor for guidance on the next steps.",
    },
}


def _decision_key(decision: str) -> str:
    key = (decision or "").strip().lower()
    if key == "revision":
        return "revision_requested"
    return key if key in _DECISION_META else "rejected"


def _shell(*, accent: str, badge: str, heading: str, body_rows: str,
           closing: str, footer_note: str) -> str:
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
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#F9FAFB;border:1px solid #E5E7EB;border-left:5px solid {accent};border-radius:8px;">
              <tr><td style="padding:18px 20px;">{body_rows}</td></tr>
            </table>
            <p style="margin:24px 0 0 0;font-size:14px;line-height:22px;color:#374151;">{escape(closing)}</p>
          </td>
        </tr>
        <tr>
          <td style="background-color:#F9FAFB;border-top:1px solid #E5E7EB;padding:18px 32px;font-size:12px;line-height:18px;color:#9CA3AF;">
            This is an automated message from {BRAND_NAME}. Please do not reply to this email.<br>
            {escape(footer_note)}
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _row(label: str, value: str, *, strong: bool = False, accent: str | None = None) -> str:
    weight = "font-weight:700;" if strong else "font-weight:600;"
    color = accent or "#111827"
    return (
        '<tr>'
        f'<td style="padding-top:10px;font-size:12px;color:#6B7280;text-transform:uppercase;letter-spacing:0.8px;">{escape(label)}</td>'
        '</tr>'
        f'<tr><td style="padding-top:2px;font-size:{"16px" if strong else "14px"};{weight}color:{color};">{escape(value)}</td></tr>'
    )


def build_submission_email(
    *,
    supervisor_name: str,
    student_name: str,
    group_name: str,
    project_title: str,
    file_name: str,
    submitted_at: str = "",
    plagiarism_score: float | None = None,
    compliance_score: float | None = None,
    grammar_count: int | None = None,
) -> tuple[str, str, str]:
    """Returns (subject, text_body, html_body) for a new-submission alert."""
    file_name = file_name or "submission"
    group_name = group_name or "your group"
    greeting_name = (supervisor_name or "").strip() or "Supervisor"
    student_label = (student_name or "").strip() or "A student"
    subject = f"New submission to review: {file_name} ({group_name})"

    score_lines = []
    if plagiarism_score is not None:
        score_lines.append(f"Plagiarism risk : {plagiarism_score:g}%")
    if compliance_score is not None:
        score_lines.append(f"Compliance     : {compliance_score:g}%")
    if grammar_count is not None:
        score_lines.append(f"Grammar issues : {grammar_count}")
    scores_text = ("\n".join(score_lines) + "\n") if score_lines else ""

    text = (
        f"Dear {greeting_name},\n\n"
        f"{student_label} submitted a document for your review.\n\n"
        f"File      : {file_name}\n"
        f"Group     : {group_name}\n"
        + (f"Project   : {project_title}\n" if project_title else "")
        + (f"Submitted : {submitted_at}\n" if submitted_at else "")
        + scores_text
        + "\n"
        "Next step: open Formatify -> Submissions to review it.\n\n"
        f"— {BRAND_NAME}\n"
    )

    score_rows = ""
    if plagiarism_score is not None:
        score_rows += _row("Plagiarism risk", f"{plagiarism_score:g}%", accent="#D97706")
    if compliance_score is not None:
        score_rows += _row("Compliance", f"{compliance_score:g}%", accent="#16A34A")
    if grammar_count is not None:
        score_rows += _row("Grammar issues", str(grammar_count))

    body_rows = (
        _row("Submitted by", student_label)
        + _row("File", file_name, strong=True)
        + _row("Group", group_name)
        + (_row("Project", project_title) if project_title else "")
        + (_row("Submitted", submitted_at) if submitted_at else "")
        + score_rows
    )
    html_body = _shell(
        accent="#4F46E5",
        badge="NEW SUBMISSION",
        heading="A document is waiting for your review",
        body_rows=body_rows,
        closing="Open Formatify → Submissions to review the document and record your decision.",
        footer_note="You received this because you are the assigned supervisor for this group.",
    )
    return subject, text, html_body


def build_decision_email(
    *,
    student_name: str,
    supervisor_name: str,
    file_name: str,
    decision: str,
    note: str = "",
    decided_at: str = "",
) -> tuple[str, str, str]:
    """Returns (subject, text_body, html_body) for a supervisor decision."""
    meta = _DECISION_META[_decision_key(decision)]
    file_name = file_name or "submission"
    note = (note or "").strip() or "No comment provided"
    student_label = (student_name or "").strip() or "Student"
    sup_label = (supervisor_name or "").strip() or "Your supervisor"
    subject = meta["subject"].format(file=file_name)

    text = (
        f"Dear {student_label},\n\n"
        f"{sup_label} reviewed your submission and the decision is: {meta['label']}.\n\n"
        f"File    : {file_name}\n"
        + (f"Decided : {decided_at}\n" if decided_at else "")
        + f"\nSupervisor's note:\n{note}\n\n"
        f"Next step: {meta['next_step']}\n\n"
        f"— {BRAND_NAME}\n"
    )

    body_rows = (
        _row("File", file_name, strong=True)
        + (_row("Decided", decided_at) if decided_at else "")
        + _row("Decision", meta["label"], strong=True, accent=meta["accent"])
        + '<tr><td style="padding-top:14px;font-size:12px;color:#6B7280;text-transform:uppercase;letter-spacing:0.8px;">Supervisor\'s note</td></tr>'
        f'<tr><td style="padding-top:4px;font-size:14px;line-height:22px;color:#111827;white-space:pre-wrap;">{escape(note)}</td></tr>'
    )
    heading = {
        "approved": "Your submission was approved",
        "revision_requested": "Revision requested on your submission",
        "rejected": "Your submission was rejected",
    }[_decision_key(decision)]
    html_body = _shell(
        accent=meta["accent"],
        badge=meta["label"],
        heading=heading,
        body_rows=body_rows,
        closing=meta["next_step"],
        footer_note="You received this because you are a member of the group that made this submission.",
    )
    return subject, text, html_body


def send_email_safe(to_email: str, subject: str, text: str, html: str) -> dict:
    """Send one email via the shared SMTP config. Never raises.

    Returns {"email_sent": bool, "reason": str}.
    """
    try:
        cfg = email_service._config()
        if not cfg["host"] or not cfg["user"] or not cfg["password"]:
            logger.info("Submission email skipped (SMTP not configured)")
            return {"email_sent": False, "reason": "SMTP not configured"}
        msg = email_service._build_message(cfg, to_email, subject, text, html)
        server = email_service._connect(cfg)
        try:
            server.send_message(msg)
        finally:
            try:
                server.quit()
            except Exception:  # noqa: BLE001
                pass
        return {"email_sent": True, "reason": ""}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Submission email send failed")
        return {"email_sent": False, "reason": f"send failed: {type(exc).__name__}"}


def _email_notifications_enabled(org_id: int) -> bool:
    """Org-level admin_settings.email_notifications switch (default: on)."""
    try:
        import database

        conn = database.get_db()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT value FROM admin_settings WHERE key = ?",
                (f"org:{int(org_id)}:email_notifications",),
            )
            row = cur.fetchone()
        finally:
            conn.close()
        if row is None:
            return True
        return str(row["value"] or "").strip().lower() in {"1", "true", "yes", "on"}
    except Exception:  # noqa: BLE001
        logger.exception("Could not read email_notifications setting; defaulting to on")
        return True


def _log_result(event: str, role: str, submission_id: int, result: dict) -> None:
    outcome = "sent" if result.get("email_sent") else f"skipped:{result.get('reason') or 'unknown'}"
    logger.info(
        "submission_email event=%s role=%s submission_id=%s result=%s",
        event, role, submission_id, outcome,
    )


def queue_submission_received_email(
    *,
    submission_id: int,
    org_id: int,
    supervisor_name: str,
    supervisor_email: str,
    student_name: str,
    group_name: str,
    project_title: str,
    file_name: str,
    submitted_at: str = "",
    plagiarism_score: float | None = None,
    compliance_score: float | None = None,
    grammar_count: int | None = None,
) -> None:
    """Email the supervisor about a new submission (background thread)."""
    if not (supervisor_email or "").strip():
        logger.info(
            "submission_email event=submission_received role=supervisor submission_id=%s result=skipped:no supervisor email",
            submission_id,
        )
        return

    def _work() -> None:
        try:
            if not _email_notifications_enabled(org_id):
                _log_result("submission_received", "supervisor", submission_id,
                            {"email_sent": False, "reason": "email_notifications disabled"})
                return
            subject, text, html_body = build_submission_email(
                supervisor_name=supervisor_name,
                student_name=student_name,
                group_name=group_name,
                project_title=project_title,
                file_name=file_name,
                submitted_at=submitted_at,
                plagiarism_score=plagiarism_score,
                compliance_score=compliance_score,
                grammar_count=grammar_count,
            )
            result = send_email_safe(supervisor_email.strip(), subject, text, html_body)
            _log_result("submission_received", "supervisor", submission_id, result)
        except Exception:  # noqa: BLE001
            logger.exception("submission_received email worker failed")

    threading.Thread(target=_work, daemon=True).start()


def queue_decision_emails(
    *,
    submission_id: int,
    org_id: int,
    decision: str,
    supervisor_name: str,
    file_name: str,
    note: str,
    decided_at: str,
    student_emails: list[str],
) -> None:
    """Email every notified student about a supervisor decision (background)."""
    recipients = [e.strip() for e in student_emails if (e or "").strip()]
    if not recipients:
        logger.info(
            "submission_email event=decision role=student submission_id=%s result=skipped:no recipients",
            submission_id,
        )
        return

    def _work() -> None:
        try:
            if not _email_notifications_enabled(org_id):
                for email in recipients:
                    _log_result("decision", "student", submission_id,
                                {"email_sent": False, "reason": "email_notifications disabled"})
                return
            for email in recipients:
                try:
                    subject, text, html_body = build_decision_email(
                        student_name="",
                        supervisor_name=supervisor_name,
                        file_name=file_name,
                        decision=decision,
                        note=note,
                        decided_at=decided_at,
                    )
                    result = send_email_safe(email, subject, text, html_body)
                    _log_result("decision", "student", submission_id, result)
                except Exception:  # noqa: BLE001
                    logger.exception("decision email worker failed for one recipient")
        except Exception:  # noqa: BLE001
            logger.exception("decision email worker failed")

    threading.Thread(target=_work, daemon=True).start()
