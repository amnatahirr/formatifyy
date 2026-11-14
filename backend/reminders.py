"""Deadline reminders: 3 din, 1 din aur deadline wale din (notification + email)."""
from __future__ import annotations

import logging
from typing import Any

from database import get_db
from email_service import send_emails_async, build_deadline_email
from services.notification_service import notify, NotificationType

logger = logging.getLogger(__name__)

REMINDER_WINDOW_DAYS = 3  # is se pehle reminder shuru nahi hota


def students_for_deadline(cursor, org_id, department_id, target_semester):
    sql = (
        "SELECT id, email,username, org_id FROM users "
        "WHERE org_id = ? AND role = 'student' AND COALESCE(is_graduated, 0) = 0"
    )
    params: list[Any] = [org_id]
    if target_semester is not None:
        sql += " AND current_semester = ?"
        params.append(target_semester)
    if department_id is not None:
        sql += " AND department_id = ?"
        params.append(department_id)
    cursor.execute(sql, params)
    return cursor.fetchall()


_STAGE_TO_TYPE = {
    3: NotificationType.DEADLINE_REMINDER_3_DAYS,
    1: NotificationType.DEADLINE_REMINDER_1_DAY,
    0: NotificationType.DEADLINE_TODAY,
}


def notify_students(cursor, students, title, message, deadline_id, stage: int = 0) -> int:
    """Insert in-app notifications via the unified service (never raises)."""
    ntype = _STAGE_TO_TYPE.get(stage, NotificationType.DEADLINE_TODAY)
    for s in students:
        notify(
            org_id=int(s["org_id"] or 1),
            user_id=s["id"],
            type=ntype,
            title=title,
            body=message,
            entity_type="deadline",
            entity_id=deadline_id,
            payload={"screen": "deadlines", "deadline_id": deadline_id},
            dedupe_key=f"deadline_{deadline_id}_{s['id']}_{stage}",
        )
    return len(students)


def _stage_for(days_left: int) -> int:
    """3 = 3 din wali, 1 = 1 din wali, 0 = deadline wale din."""
    if days_left <= 0:
        return 0
    if days_left <= 1:
        return 1
    return 3


def _when_text(days_left: int) -> str:
    if days_left <= 0:
        return "TODAY"
    if days_left == 1:
        return "tomorrow"
    return f"in {days_left} days"


def run_deadline_reminders() -> dict[str, int]:
    conn = get_db()
    cur = conn.cursor()
    sent_total = 0
    emails: list[tuple[str, str, str]] = []
    pending_notifications: list[tuple[dict, str, str, int, int]] = []
    try:
        cur.execute(
            f"""
            SELECT id, org_id, title,description, due_date, department_id, applies_to_all, target_semester,
                   CAST(julianday(date(due_date)) - julianday(date('now','localtime')) AS INTEGER) AS days_left
            FROM deadlines
            WHERE date(due_date) BETWEEN date('now','localtime')
                  AND date('now','localtime','+{int(REMINDER_WINDOW_DAYS)} days')
            """
        )
        deadlines = cur.fetchall()

        for dl in deadlines:
            dept = None if dl["applies_to_all"] else dl["department_id"]
            students = students_for_deadline(cur, dl["org_id"] or 1, dept, dl["target_semester"])
            days_left = int(dl["days_left"] or 0)
            stage = _stage_for(days_left)
            when = _when_text(days_left)

            title = f"Reminder: {dl['title']}"
            message = f"'{dl['title']}' is due {when} ({dl['due_date']})."

            for s in students:
                cur.execute(
                    "INSERT OR IGNORE INTO deadline_reminders_sent (deadline_id, user_id, stage) VALUES (?, ?, ?)",
                    (dl["id"], s["id"], stage),
                )
                if cur.rowcount != 1:
                    continue  # is stage ki reminder pehle ja chuki
                # Defer: notify() uses its own connection, so it must run after commit.
                pending_notifications.append((s, title, message, dl["id"], stage))
                if s["email"]:
                    subject, text, html = build_deadline_email(
                        title=dl["title"],
                        due_date=dl["due_date"],
                        description=dl["description"] or "",
                        name=s["username"],
                        days_left=days_left,
                    )
                    emails.append((s["email"], subject, text, html))
                sent_total += 1

        conn.commit()
        # In-app notifications via notify() (own connection) — only after commit
        # so the deadline_reminders_sent write lock is released.
        for s, ntitle, nmessage, deadline_id, nstage in pending_notifications:
            notify_students(cur, [s], ntitle, nmessage, deadline_id, nstage)
        send_emails_async(emails)  # commit ke BAAD, taake DB lock na rahe
        logger.info("Deadline reminders: %s deadlines, %s notifications", len(deadlines), sent_total)
        return {"deadlines": len(deadlines), "notifications": sent_total, "emails_queued": len(emails)}
    except Exception:
        conn.rollback()
        logger.exception("Deadline reminder job failed")
        raise
    finally:
        conn.close()


# ── Scheduler ────────────────────────────────────────────────────────────────
_scheduler = None


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    from apscheduler.schedulers.background import BackgroundScheduler

    _scheduler = BackgroundScheduler(timezone="Asia/Karachi")
    _scheduler.add_job(
        run_deadline_reminders, "cron", hour=9, minute=0,
        id="deadline_reminders", replace_existing=True,
    )
    _scheduler.start()
    logger.info("Reminder scheduler started (daily 09:00 PKT)")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None