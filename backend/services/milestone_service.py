"""
services/milestone_service.py — admin-defined FYP milestones (semester 6/7/8).

Per-group state lives in group_milestones (dept_milestone_id links to the
admin's department_milestones row). Name / semester / deadline are always read
from the admin row, so admin edits show up everywhere automatically.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from database import get_db

logger = logging.getLogger(__name__)

MILESTONE_SEMESTERS = (6, 7, 8)
PHASE_BY_SEMESTER = {6: "Proposal", 7: "FYP-1", 8: "FYP-2"}
DUE_SOON_DAYS = 3
OVERDUE_NOTICE_WINDOW_DAYS = 7

# Pakistan has no DST, so a fixed +05:00 offset is exact (no tzdata needed).
_PKT = timezone(timedelta(hours=5))


def today_pk() -> date:
    return datetime.now(_PKT).date()


def parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


# ── group helpers ────────────────────────────────────────────────────────────

def _group_ctx(cursor, group_id: int) -> Optional[dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, title, org_id, department_id, current_semester,
               COALESCE(is_graduated, 0) AS is_graduated, status
        FROM fyp_groups WHERE id = ?
        """,
        (group_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _dept_has_milestones(cursor, org_id: int, department_id: Any) -> bool:
    if department_id is None:
        return False
    cursor.execute(
        """
        SELECT 1 FROM department_milestones
        WHERE COALESCE(org_id, 1) = ? AND department_id = ?
          AND COALESCE(is_active, 1) = 1
        LIMIT 1
        """,
        (int(org_id or 1), int(department_id)),
    )
    return cursor.fetchone() is not None


def _parse_members(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(i).strip() for i in raw if str(i).strip()]
    text = str(raw).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(i).strip() for i in parsed if str(i).strip()]
    except json.JSONDecodeError:
        pass
    return [p.strip() for p in text.split(",") if p.strip()]


def _email_from_label(label: str) -> Optional[str]:
    text = (label or "").strip()
    if not text:
        return None
    m = re.search(r"<([^>]+@[^>]+)>", text)
    if m:
        return m.group(1).strip().lower()
    if "@" in text and " " not in text:
        return text.lower()
    m = re.search(r"([^\s<>]+@[^\s<>]+)", text)
    if m:
        return m.group(1).strip().lower()
    return None


def group_member_emails(cursor, group_id: int) -> list[str]:
    """Contact email + every member email of a group (lower-cased, de-duplicated)."""
    emails: list[str] = []
    seen: set[str] = set()

    def _add(raw: Optional[str]) -> None:
        e = (raw or "").strip().lower()
        if e and "@" in e and e not in seen:
            seen.add(e)
            emails.append(e)

    cursor.execute(
        "SELECT student_contact_email, member_names FROM fyp_groups WHERE id = ?",
        (group_id,),
    )
    row = cursor.fetchone()
    if row:
        _add(row["student_contact_email"])
        for member in _parse_members(row["member_names"]):
            _add(_email_from_label(member))

    if not emails:
        cursor.execute(
            """
            SELECT student_leader_email, member_names
            FROM assignment_requests
            WHERE fyp_group_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (group_id,),
        )
        req = cursor.fetchone()
        if req:
            _add(req["student_leader_email"])
            for member in _parse_members(req["member_names"]):
                _add(_email_from_label(member))
    return emails


def _user_by_email(cursor, email: str, org_id: int):
    cursor.execute(
        """
        SELECT id, username, org_id FROM users
        WHERE LOWER(email) = LOWER(?) AND COALESCE(org_id, 1) = ?
        LIMIT 1
        """,
        (email, int(org_id or 1)),
    )
    return cursor.fetchone()


# ── sync / list ──────────────────────────────────────────────────────────────

def sync_group_milestones(cursor, group_id: int) -> bool:
    """
    Create missing group_milestones rows for the group's department milestones
    (only semesters >= the group's current semester).
    Returns True when the department uses admin milestones, else False
    (caller then falls back to the legacy static milestones).
    """
    ctx = _group_ctx(cursor, group_id)
    if not ctx:
        return False
    org_id = int(ctx.get("org_id") or 1)
    dept_id = ctx.get("department_id")
    if int(ctx.get("is_graduated") or 0):
        return _dept_has_milestones(cursor, org_id, dept_id)
    if not _dept_has_milestones(cursor, org_id, dept_id):
        return False

    sem = int(ctx.get("current_semester") or 6)
    cursor.execute(
        """
        SELECT id, name, sort_order FROM department_milestones
        WHERE COALESCE(org_id, 1) = ? AND department_id = ?
          AND COALESCE(is_active, 1) = 1 AND semester >= ?
        """,
        (org_id, int(dept_id), sem),
    )
    for dm in cursor.fetchall():
        cursor.execute(
            "SELECT 1 FROM group_milestones WHERE group_id = ? AND dept_milestone_id = ? LIMIT 1",
            (group_id, dm["id"]),
        )
        if cursor.fetchone():
            continue
        cursor.execute(
            """
            INSERT INTO group_milestones
                (group_id, name, sort_order, is_completed, dept_milestone_id)
            VALUES (?, ?, ?, 0, ?)
            """,
            (group_id, dm["name"], int(dm["sort_order"] or 0), dm["id"]),
        )
    return True


def sync_department_groups(cursor, org_id: int, department_id: int) -> None:
    cursor.execute(
        """
        SELECT id FROM fyp_groups
        WHERE status = 'accepted' AND department_id = ? AND COALESCE(org_id, 1) = ?
        """,
        (int(department_id), int(org_id or 1)),
    )
    for row in cursor.fetchall():
        sync_group_milestones(cursor, int(row["id"]))


def compute_status(
    is_completed: bool,
    rework_at: Any,
    deadline: Optional[date],
    today: date,
) -> str:
    if is_completed:
        return "completed"
    if rework_at:
        return "rework"
    if deadline is None:
        return "upcoming"
    days = (deadline - today).days
    if days < 0:
        return "overdue"
    if days <= DUE_SOON_DAYS:
        return "due_soon"
    return "upcoming"


def _serialize(row, position: int, today: date) -> dict[str, Any]:
    completed = bool(row["is_completed"])
    deadline = parse_date(row["deadline_override"]) or parse_date(row["deadline_date"])
    sem = int(row["semester"])
    return {
        "id": row["id"],
        "name": row["name"],
        "sort_order": position,
        "is_completed": completed,
        "completed_at": row["completed_at"],
        "semester": sem,
        "phase": PHASE_BY_SEMESTER.get(sem, ""),
        "deadline_date": deadline.isoformat() if deadline else None,
        "extended": parse_date(row["deadline_override"]) is not None,
        "status": compute_status(completed, row["rework_at"], deadline, today),
        "days_left": (deadline - today).days if deadline else None,
        "rework_note": (row["rework_note"] or ""),
        "rework_at": row["rework_at"],
        "is_managed": True,
    }


def list_group_milestones(cursor, group_id: int) -> Optional[list[dict[str, Any]]]:
    """Admin-managed milestones for a group, or None when the department has none."""
    if not sync_group_milestones(cursor, group_id):
        return None
    ctx = _group_ctx(cursor, group_id) or {}
    graduated = bool(int(ctx.get("is_graduated") or 0))
    today = today_pk()
    cursor.execute(
        """
        SELECT gm.id, gm.is_completed, gm.completed_at, gm.rework_note,
               gm.rework_at, gm.deadline_override,
               dm.name, dm.semester, dm.deadline_date
        FROM group_milestones gm
        JOIN department_milestones dm ON dm.id = gm.dept_milestone_id
        WHERE gm.group_id = ? AND COALESCE(dm.is_active, 1) = 1
        ORDER BY dm.semester ASC, date(dm.deadline_date) ASC, dm.sort_order ASC, gm.id ASC
        """,
        (group_id,),
    )
    items = [_serialize(r, i, today) for i, r in enumerate(cursor.fetchall(), start=1)]
    if graduated:
        for it in items:
            it["is_completed"] = True
            it["status"] = "completed"
    return items

    
# ── supervisor actions ───────────────────────────────────────────────────────

def _sync_member_users(cursor, ctx: dict[str, Any], group_id: int, new_sem: int, graduated: bool) -> None:
    """Keep members' users.current_semester / is_graduated aligned with the group."""
    emails = group_member_emails(cursor, group_id)
    if not emails:
        return
    org_id = int(ctx.get("org_id") or 1)
    marks = ",".join("?" for _ in emails)
    try:
        if graduated:
            cursor.execute(
                f"""
                UPDATE users SET is_graduated = 1
                WHERE role = 'student' AND COALESCE(org_id, 1) = ?
                  AND LOWER(email) IN ({marks})
                """,
                [org_id, *emails],
            )
        else:
            cursor.execute(
                f"""
                UPDATE users SET current_semester = ?
                WHERE role = 'student' AND COALESCE(org_id, 1) = ?
                  AND LOWER(email) IN ({marks})
                  AND (current_semester IS NULL OR current_semester < ?)
                """,
                [new_sem, org_id, *emails, new_sem],
            )
    except Exception:  # noqa: BLE001
        logger.exception("Could not sync member users for group %s", group_id)


def promote_group(cursor, group_id: int) -> dict[str, Any]:
    ctx = _group_ctx(cursor, group_id)
    if not ctx:
        raise LookupError("Group not found.")
    if int(ctx.get("is_graduated") or 0):
        raise ValueError("This group has already graduated.")

    sem = int(ctx.get("current_semester") or 6)
    now = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
    completed = 0
    if sync_group_milestones(cursor, group_id):
        cursor.execute(
            """
            UPDATE group_milestones
            SET is_completed = 1, completed_at = ?, rework_note = NULL, rework_at = NULL
            WHERE group_id = ? AND COALESCE(is_completed, 0) = 0
              AND dept_milestone_id IN (
                  SELECT id FROM department_milestones WHERE semester = ?
              )
            """,
            (now, group_id, sem),
        )
        completed = cursor.rowcount or 0

    graduated = sem >= 8
    if graduated:
        new_sem = sem
        cursor.execute("UPDATE fyp_groups SET is_graduated = 1 WHERE id = ?", (group_id,))
    else:
        new_sem = sem + 1
        cursor.execute(
            "UPDATE fyp_groups SET current_semester = ? WHERE id = ?",
            (new_sem, group_id),
        )
        sync_group_milestones(cursor, group_id)

    _sync_member_users(cursor, ctx, group_id, new_sem, graduated)
    return {
        "from_semester": sem,
        "current_semester": new_sem,
        "graduated": graduated,
        "completed_milestones": completed,
        "from_phase": PHASE_BY_SEMESTER.get(sem, f"Semester {sem}"),
        "to_phase": "Graduated" if graduated else PHASE_BY_SEMESTER.get(new_sem, f"Semester {new_sem}"),
    }


def mark_rework(cursor, group_id: int, note: str) -> int:
    """Flag the current semester's pending milestones for rework. Returns rows flagged."""
    ctx = _group_ctx(cursor, group_id)
    if not ctx:
        raise LookupError("Group not found.")
    if int(ctx.get("is_graduated") or 0):
        raise ValueError("This group has already graduated.")
    if not sync_group_milestones(cursor, group_id):
        return 0
    sem = int(ctx.get("current_semester") or 6)
    now = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
    cursor.execute(
        """
        UPDATE group_milestones
        SET rework_note = ?, rework_at = ?
        WHERE group_id = ? AND COALESCE(is_completed, 0) = 0
          AND dept_milestone_id IN (
              SELECT id FROM department_milestones WHERE semester = ?
          )
        """,
        (note or "", now, group_id, sem),
    )
    return cursor.rowcount or 0


def extend_milestone(cursor, group_id: int, group_milestone_id: int, new_deadline: date) -> bool:
    """New deadline for one group's milestone. Clears its rework flag + reminder history."""
    cursor.execute(
        """
        UPDATE group_milestones
        SET deadline_override = ?, rework_note = NULL, rework_at = NULL
        WHERE id = ? AND group_id = ? AND dept_milestone_id IS NOT NULL
          AND COALESCE(is_completed, 0) = 0
        """,
        (new_deadline.isoformat(), group_milestone_id, group_id),
    )
    if cursor.rowcount != 1:
        return False
    cursor.execute(
        "DELETE FROM milestone_reminders_sent WHERE group_milestone_id = ?",
        (group_milestone_id,),
    )
    return True


# ── reminder job ─────────────────────────────────────────────────────────────

def _stage_for(days_left: int) -> Optional[int]:
    """-1 = overdue notice, 0 = today, 1 = tomorrow, 3 = within 3 days."""
    if days_left < 0:
        return -1 if days_left >= -OVERDUE_NOTICE_WINDOW_DAYS else None
    if days_left == 0:
        return 0
    if days_left <= 1:
        return 1
    if days_left <= DUE_SOON_DAYS:
        return 3
    return None


def _when_text(days_left: int) -> str:
    if days_left < 0:
        n = -days_left
        return f"overdue by {n} day{'s' if n != 1 else ''}"
    if days_left == 0:
        return "due today"
    if days_left == 1:
        return "due tomorrow"
    return f"due in {days_left} days"


def run_milestone_reminders() -> dict[str, Any]:
    """Daily job: milestone deadline emails + in-app notifications. Never raises."""
    from email_service import build_milestone_email, send_emails_async
    from services.notification_service import NotificationType, notify

    conn = get_db()
    cur = conn.cursor()
    today = today_pk()
    emails: list[tuple] = []
    pending: list[dict[str, Any]] = []
    checked = 0
    try:
        cur.execute(
            "SELECT id FROM fyp_groups WHERE status = 'accepted' AND department_id IS NOT NULL"
        )
        for g in cur.fetchall():
            sync_group_milestones(cur, int(g["id"]))
        conn.commit()

        cur.execute(
            """
            SELECT gm.id AS gm_id, gm.group_id, gm.deadline_override,
                   dm.name AS ms_name, dm.semester, dm.deadline_date,
                   g.title AS group_title, g.org_id AS org_id,
                   s.email AS sup_email
            FROM group_milestones gm
            JOIN department_milestones dm ON dm.id = gm.dept_milestone_id
            JOIN fyp_groups g ON g.id = gm.group_id
            LEFT JOIN supervisors s ON s.id = g.supervisor_id
            WHERE g.status = 'accepted' AND COALESCE(g.is_graduated, 0) = 0
              AND COALESCE(gm.is_completed, 0) = 0 AND gm.rework_at IS NULL
              AND COALESCE(dm.is_active, 1) = 1
              AND dm.semester = COALESCE(g.current_semester, 6)
            """
        )
        rows = cur.fetchall()
        for r in rows:
            deadline = parse_date(r["deadline_override"]) or parse_date(r["deadline_date"])
            if deadline is None:
                continue
            days_left = (deadline - today).days
            stage = _stage_for(days_left)
            if stage is None:
                continue
            checked += 1
            org_id = int(r["org_id"] or 1)
            phase = PHASE_BY_SEMESTER.get(int(r["semester"]), "")
            ntype = (
                NotificationType.MILESTONE_OVERDUE
                if stage == -1
                else NotificationType.MILESTONE_REMINDER
            )

            recipients = [(e, "student") for e in group_member_emails(cur, int(r["group_id"]))]
            sup_email = (r["sup_email"] or "").strip().lower()
            if stage == -1 and sup_email and sup_email not in {e for e, _ in recipients}:
                recipients.append((sup_email, "supervisor"))

            for email, audience in recipients:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO milestone_reminders_sent
                        (group_milestone_id, email, stage)
                    VALUES (?, ?, ?)
                    """,
                    (r["gm_id"], email, stage),
                )
                if cur.rowcount != 1:
                    continue  # this stage was already sent
                user = _user_by_email(cur, email, org_id)
                subject, text, html = build_milestone_email(
                    milestone=r["ms_name"],
                    due_date=deadline.isoformat(),
                    phase=phase,
                    group_name=r["group_title"] or "",
                    name=(user["username"] if user else ""),
                    days_left=days_left,
                    audience=audience,
                )
                emails.append((email, subject, text, html))
                if user:
                    pending.append(
                        dict(
                            org_id=int(user["org_id"] or org_id),
                            user_id=int(user["id"]),
                            type=ntype,
                            title=subject,
                            body=f'Milestone "{r["ms_name"]}" is {_when_text(days_left)} ({deadline.isoformat()}).',
                            entity_type="group_milestone",
                            entity_id=int(r["gm_id"]),
                            payload={
                                "screen": "milestones",
                                "group_id": int(r["group_id"]),
                                "milestone_id": int(r["gm_id"]),
                            },
                            dedupe_key=f"milestone_{r['gm_id']}_{user['id']}_{stage}",
                        )
                    )
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        logger.exception("Milestone reminder job failed")
        return {"error": str(exc)}
    finally:
        conn.close()

    # notify() opens its own connection — only after our commit.
    for n in pending:
        notify(**n)
    send_emails_async(emails)
    logger.info(
        "Milestone reminders: %s due, %s emails, %s notifications",
        checked, len(emails), len(pending),
    )
    return {
        "milestones_due": checked,
        "emails_queued": len(emails),
        "notifications": len(pending),
    }