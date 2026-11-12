from __future__ import annotations
from services.notification_service import NotificationType
import json
import logging
from datetime import date, datetime, timedelta
from typing import Annotated, Any
from services.notification_service import NotificationType
from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import FileResponse

from database import get_db

router = APIRouter(prefix="/api/supervisor", tags=["Supervisor"])
logger = logging.getLogger(__name__)


def _row_to_dict(row) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def _supervisor_org_id(supervisor: dict[str, Any]) -> int:
    return int(supervisor.get("org_id") or 1)


def _parse_member_names(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    text = str(raw).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass
    return [part.strip() for part in text.split(",") if part.strip()]


def _email_from_member_label(label: str) -> str | None:
    """Extract email from 'Name <email@x.com>' or a bare email string."""
    import re

    text = (label or "").strip()
    if not text:
        return None
    match = re.search(r"<([^>]+@[^>]+)>", text)
    if match:
        return match.group(1).strip().lower()
    if "@" in text and " " not in text:
        return text.lower()
    # trailing email without angle brackets: "Name email@x.com"
    match = re.search(r"([^\s<>]+@[^\s<>]+)", text)
    if match:
        return match.group(1).strip().lower()
    return None


def _display_name_from_member_label(label: str) -> str:
    """Best-effort display name from 'Name <email>' or bare label."""
    text = (label or "").strip()
    if not text:
        return "A member"
    if "<" in text:
        return text.split("<", 1)[0].strip() or text
    email = _email_from_member_label(text)
    if email and text.lower() == email:
        return email
    return text


def _lookup_user_profile_by_email(
    cursor, email: str | None, org_id: int
) -> dict[str, Any] | None:
    """Return users.department_id / current_semester / username for an email, if any."""
    cleaned = (email or "").strip().lower()
    if not cleaned or "@" not in cleaned:
        return None
    cursor.execute(
        """
        SELECT id, username, email, department_id, current_semester, org_id
        FROM users
        WHERE LOWER(TRIM(email)) = ?
          AND role = 'student'
          AND COALESCE(org_id, 1) = ?
        LIMIT 1
        """,
        (cleaned, org_id),
    )
    row = cursor.fetchone()
    return _row_to_dict(row) if row else None


def _collect_member_profile_mismatches(
    cursor,
    *,
    leader_email: str | None,
    leader_department_id: int | None,
    leader_semester: int | None,
    member_labels: list[str],
    org_id: int,
) -> list[dict[str, Any]]:
    """
    Informational only: compare resolvable member profiles to the leader.
    Members are resolvable only when member_names includes an email
    (e.g. 'Name <email@x.com>') that matches a users row.
    Name-only entries are skipped.
    """
    warnings: list[dict[str, Any]] = []
    leader_norm = (leader_email or "").strip().lower()
    seen_emails: set[str] = set()
    if leader_norm:
        seen_emails.add(leader_norm)

    for label in member_labels:
        email = _email_from_member_label(label)
        if not email or email in seen_emails:
            continue
        seen_emails.add(email)
        profile = _lookup_user_profile_by_email(cursor, email, org_id)
        if not profile:
            continue

        mem_dept = profile.get("department_id")
        mem_sem = profile.get("current_semester")
        # Only flag when the member profile actually has a value that differs.
        dept_mismatch = (
            mem_dept is not None
            and leader_department_id is not None
            and int(mem_dept) != int(leader_department_id)
        )
        sem_mismatch = (
            mem_sem is not None
            and leader_semester is not None
            and int(mem_sem) != int(leader_semester)
        )
        if not dept_mismatch and not sem_mismatch:
            continue

        name = _display_name_from_member_label(label)
        if not name or name == "A member":
            name = (profile.get("username") or email).strip() or "A member"
        warnings.append(
            {
                "member_label": label,
                "member_name": name,
                "member_email": email,
                "member_department_id": mem_dept,
                "member_current_semester": mem_sem,
                "message": (
                    f"Note: {name}'s profile shows a different department/semester "
                    "than the group leader — you may want to verify with the group."
                ),
            }
        )
    return warnings


def _get_group_notify_emails(cursor, group_id: int, supervisor_id: int | None = None) -> list[str]:
    """All group emails that should receive supervisor comment notifications."""
    emails: list[str] = []
    seen: set[str] = set()

    def _add(raw: str | None) -> None:
        email = (raw or "").strip().lower()
        if email and "@" in email and email not in seen:
            seen.add(email)
            emails.append(email)

    cursor.execute(
        """
        SELECT student_contact_email, member_names
        FROM fyp_groups
        WHERE id = ?
        """,
        (group_id,),
    )
    row = cursor.fetchone()
    if row:
        _add(row["student_contact_email"])
        for member in _parse_member_names(row["member_names"]):
            _add(_email_from_member_label(member))

    # Fallback: assignment request leader + members if group fields empty
    if not emails:
        leader = _get_group_student_email(cursor, group_id, supervisor_id)
        _add(leader)
        cursor.execute(
            """
            SELECT member_names, student_leader_email
            FROM assignment_requests
            WHERE fyp_group_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (group_id,),
        )
        req = cursor.fetchone()
        if req:
            _add(req["student_leader_email"])
            for member in _parse_member_names(req["member_names"]):
                _add(_email_from_member_label(member))

    return emails


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        try:
            return datetime.fromisoformat(text).date()
        except ValueError:
            return None


def _format_deadline(value: Any) -> str:
    parsed = _parse_date(value)
    return parsed.isoformat() if parsed else ""


def _is_group_behind(deadline_value: Any, progress: float) -> bool:
    deadline = _parse_date(deadline_value)
    if deadline is None:
        return False
    return deadline < date.today() and progress < 100


def _resolve_default_deadline(cursor, department_id: int | None, org_id: int) -> str:
    """Pick nearest upcoming department/global deadline, else +45 days."""
    params: list[Any] = [org_id]
    query = """
        SELECT due_date
        FROM deadlines
        WHERE date(due_date) >= date('now')
          AND COALESCE(org_id, 1) = ?
    """
    if department_id is not None:
        query += " AND (applies_to_all = 1 OR department_id = ?)"
        params.append(department_id)
    else:
        query += " AND applies_to_all = 1"
    query += " ORDER BY date(due_date) ASC LIMIT 1"
    cursor.execute(query, params)
    row = cursor.fetchone()
    if row and row["due_date"]:
        return str(row["due_date"])[:10]
    return (date.today() + timedelta(days=45)).isoformat()


def _require_supervisor(user_id: int | None) -> dict[str, Any]:
    """Validate the logged-in user is a supervisor and resolve their supervisors row."""
    if user_id is None:
        raise HTTPException(status_code=401, detail="Supervisor login required.")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, email, role, username, org_id FROM users WHERE id = ?",
        (user_id,),
    )
    user = cursor.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")
    if user["role"] != "supervisor":
        conn.close()
        raise HTTPException(status_code=403, detail="Supervisor access required.")

    user_org = int(user["org_id"] or 1)
    cursor.execute(
        """
        SELECT s.*, d.name AS department_name, d.code AS department_code
        FROM supervisors s
        LEFT JOIN departments d ON d.id = s.department_id
        WHERE LOWER(s.email) = LOWER(?)
          AND COALESCE(s.org_id, 1) = ?
        """,
        (user["email"], user_org),
    )
    supervisor = cursor.fetchone()
    conn.close()
    if not supervisor:
        raise HTTPException(
            status_code=404,
            detail="Supervisor profile not found. Ask an admin to add your account.",
        )
    data = _row_to_dict(supervisor)
    data["org_id"] = int(data.get("org_id") or user_org)
    data["user_id"] = int(user["id"])
    return data


def _create_notification(
    cursor,
    *,
    recipient_email: str | None,
    title: str,
    message: str,
    notification_type: str,
    related_type: str,
    related_id: int,
    org_id: int,
) -> None:
    """Legacy wrapper - now uses the unified notification service."""
    from services.notification_service import notify, NotificationType
    
    email = (recipient_email or "").strip().lower()
    if not email:
        return

    cursor.execute(
        "SELECT id, org_id FROM users WHERE LOWER(email) = LOWER(?) AND COALESCE(org_id, 1) = ?",
        (email, org_id),
    )
    user_row = cursor.fetchone()
    user_id = user_row["id"] if user_row else None
    recipient_org_id = int(user_row["org_id"] if user_row and user_row["org_id"] else org_id)

    # Map legacy types to new constants
    type_map = {
        "assignment_request": NotificationType.NEW_ASSIGNMENT_REQUEST,
        "assignment_accepted": NotificationType.ASSIGNMENT_ACCEPTED,
        "assignment_rejected": NotificationType.ASSIGNMENT_REJECTED,
        "final_submission": NotificationType.STUDENT_SUBMITTED,
        "student_reply": NotificationType.STUDENT_REPLY,
        "meeting_note": NotificationType.MEETING_NOTE,
        "submission_approved": NotificationType.SUBMISSION_APPROVED,
        "submission_revision": NotificationType.SUBMISSION_REVISION_REQUESTED,
        "submission_rejected": NotificationType.SUBMISSION_REJECTED,
        "document_comment": NotificationType.SUPERVISOR_COMMENT,
        "plagiarism_flag": NotificationType.PLAGIARISM_HIGH,
    }
    new_type = type_map.get(notification_type, notification_type)

    notify(
        org_id=recipient_org_id,
        user_id=user_id,
        type=new_type,
        title=title,
        body=message,
        entity_type=related_type,
        entity_id=related_id,
        payload={"screen": _get_screen_for_type(new_type), "entity_id": related_id},
    )
    logger.info("Notification queued for %s (org_id=%s): %s", email, recipient_org_id, title)


def _get_screen_for_type(notification_type: str) -> str:
    """Map notification type to frontend screen route."""
    screen_map = {
        NotificationType.NEW_ASSIGNMENT_REQUEST: "assignment_requests",
        NotificationType.ASSIGNMENT_ACCEPTED: "assignment_requests",
        NotificationType.ASSIGNMENT_REJECTED: "assignment_requests",
        NotificationType.STUDENT_SUBMITTED: "submissions",
        NotificationType.STUDENT_REPLY: "comments",
        NotificationType.MEETING_NOTE: "meeting_notes",
        NotificationType.SUBMISSION_APPROVED: "submissions",
        NotificationType.SUBMISSION_REVISION_REQUESTED: "submissions",
        NotificationType.SUBMISSION_REJECTED: "submissions",
        NotificationType.SUPERVISOR_COMMENT: "analyze",
        NotificationType.PLAGIARISM_HIGH: "analyze",
    }
    return screen_map.get(notification_type, "notifications")


def _serialize_assignment_request(row) -> dict[str, Any]:
    members = _parse_member_names(row["member_names"])
    if not members and row["student_leader_name"]:
        members = [row["student_leader_name"]]
    keys = set(row.keys()) if hasattr(row, "keys") else set()
    cosupervisor = ""
    if "cosupervisor_name" in keys and row["cosupervisor_name"]:
        cosupervisor = str(row["cosupervisor_name"]).strip()
    return {
        "id": row["id"],
        "group_name": row["group_name"],
        "project_title": row["project_title"] or "",
        "topic": row["project_title"] or "",
        "student_leader_name": row["student_leader_name"] or "",
        "student_leader_email": row["student_leader_email"] or "",
        "member_names": members,
        "cosupervisor_name": cosupervisor,
        "department_id": row["department_id"],
        "department_name": row["department_name"] or "",
        "department_code": row["department_code"] or "",
        "status": row["status"],
        "rejection_reason": row["rejection_reason"] or "",
        "fyp_group_id": row["fyp_group_id"],
        "created_at": row["created_at"],
        "resolved_at": row["resolved_at"],
    }


def _normalize_document_status(raw: Any) -> str:
    status = str(raw or "pending").strip().lower()
    if status in {"pending_review", "pending"}:
        return "pending"
    if status in {"needs_changes", "revision", "changes_requested"}:
        return "revision"
    if status in {"approved", "accepted", "completed"}:
        return "approved"
    return status or "pending"


def _ensure_group_milestones(cursor, group_id: int, progress: float = 0) -> list[dict[str, Any]]:
    defaults = [
        ("Proposal", 1, progress >= 30),
        ("Literature Review", 2, progress >= 60),
        ("Final Doc", 3, progress >= 100),
    ]
    cursor.execute("SELECT COUNT(*) FROM group_milestones WHERE group_id = ?", (group_id,))
    if cursor.fetchone()[0] == 0:
        for name, order, done in defaults:
            cursor.execute(
                """
                INSERT INTO group_milestones
                    (group_id, name, sort_order, is_completed, completed_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    group_id,
                    name,
                    order,
                    1 if done else 0,
                    datetime.utcnow().isoformat(sep=" ", timespec="seconds") if done else None,
                ),
            )

    cursor.execute(
        """
        SELECT id, name, sort_order, is_completed, completed_at
        FROM group_milestones
        WHERE group_id = ?
        ORDER BY sort_order ASC, id ASC
        """,
        (group_id,),
    )
    rows = cursor.fetchall()
    # Guarantee the three canonical milestones exist even if DB was partially seeded
    existing_names = {str(row["name"]).strip().lower() for row in rows}
    for name, order, done in defaults:
        if name.lower() not in existing_names:
            cursor.execute(
                """
                INSERT INTO group_milestones
                    (group_id, name, sort_order, is_completed, completed_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (group_id, name, order, 0, None),
            )
    cursor.execute(
        """
        SELECT id, name, sort_order, is_completed, completed_at
        FROM group_milestones
        WHERE group_id = ?
        ORDER BY sort_order ASC, id ASC
        """,
        (group_id,),
    )
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "sort_order": row["sort_order"],
            "is_completed": bool(row["is_completed"]),
            "completed_at": row["completed_at"],
        }
        for row in cursor.fetchall()
    ]


def _serialize_group(row) -> dict[str, Any]:
    progress = float(row["progress"] or 0)
    if progress < 0:
        progress = 0.0
    if progress > 100:
        progress = 100.0
    keys = row.keys()
    deadline = _format_deadline(row["deadline_date"] if "deadline_date" in keys else None)
    behind = _is_group_behind(deadline, progress)
    members = _parse_member_names(row["member_names"] if "member_names" in keys else None)
    return {
        "id": row["id"],
        "title": row["title"],
        "project_title": row["project_title"] or "",
        "status": row["status"],
        "progress": progress,
        "member_names": members,
        "deadline_date": deadline,
        "is_behind": behind,
        "track_status": "behind" if behind else "on_track",
        "created_at": row["created_at"],
        "department_id": row["department_id"] if "department_id" in keys else None,
        "current_semester": row["current_semester"] if "current_semester" in keys else None,
        "student_contact_email": (
            row["student_contact_email"] if "student_contact_email" in keys else ""
        ) or "",
    }


@router.get("/home")
def get_supervisor_home(user_id: Annotated[int | None, Query()] = None):
    """Dashboard counts + accepted groups for the logged-in supervisor."""
    supervisor = _require_supervisor(user_id)
    supervisor_id = supervisor["id"]

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*) FROM assignment_requests
        WHERE supervisor_id = ? AND status = 'pending'
        """,
        (supervisor_id,),
    )
    pending_assignment_requests = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*) FROM final_submissions
        WHERE supervisor_id = ? AND status = 'pending'
        """,
        (supervisor_id,),
    )
    documents_to_review = cursor.fetchone()[0]

    supervisor_email = (supervisor.get("email") or "").strip().lower()
    sup_user_id = supervisor.get("user_id")
    sup_org_id = _supervisor_org_id(supervisor)
    cursor.execute(
        """
        SELECT COUNT(*) FROM notifications
        WHERE ((user_id = ?) OR (user_id IS NULL AND LOWER(TRIM(recipient_email)) = LOWER(?)))
          AND COALESCE(org_id, 1) = ? AND is_read = 0
        """,
        (sup_user_id, supervisor_email, sup_org_id),
    )
    unread_replies = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT id, title, project_title, status, progress, member_names, deadline_date, created_at
        FROM fyp_groups
        WHERE supervisor_id = ? AND status = 'accepted'
          AND COALESCE(org_id, 1) = ?
        ORDER BY created_at DESC, id DESC
        """,
        (supervisor_id, _supervisor_org_id(supervisor)),
    )
    groups = [_serialize_group(row) for row in cursor.fetchall()]

    conn.close()
    return {
        "supervisor_id": supervisor_id,
        "supervisor_name": supervisor.get("name") or "",
        "pending_assignment_requests": pending_assignment_requests,
        "documents_to_review": documents_to_review,
        "unread_replies": unread_replies,
        "groups": groups,
    }


@router.get("/groups")
def list_my_groups(
    user_id: Annotated[int | None, Query()] = None,
    filter: Annotated[str, Query()] = "all",
):
    """Accepted groups for the supervisor, with behind-deadline groups first."""
    supervisor = _require_supervisor(user_id)
    supervisor_id = supervisor["id"]
    filter_key = (filter or "all").strip().lower().replace("-", "_").replace(" ", "_")
    if filter_key in {"ontrack"}:
        filter_key = "on_track"
    if filter_key not in {"all", "on_track", "behind"}:
        raise HTTPException(status_code=400, detail="Filter must be all, on_track, or behind.")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, title, project_title, status, progress, member_names, deadline_date, created_at
        FROM fyp_groups
        WHERE supervisor_id = ? AND status = 'accepted'
          AND COALESCE(org_id, 1) = ?
        """,
        (supervisor_id, _supervisor_org_id(supervisor)),
    )
    all_groups = [_serialize_group(row) for row in cursor.fetchall()]
    conn.close()

    def sort_key(item: dict[str, Any]):
        deadline = _parse_date(item.get("deadline_date")) or date.max
        return (0 if item.get("is_behind") else 1, deadline, (item.get("title") or "").lower())

    all_groups.sort(key=sort_key)
    behind_count = sum(1 for g in all_groups if g["is_behind"])

    if filter_key == "behind":
        groups = [g for g in all_groups if g["is_behind"]]
    elif filter_key == "on_track":
        groups = [g for g in all_groups if not g["is_behind"]]
    else:
        groups = all_groups

    return {
        "groups": groups,
        "count": len(groups),
        "filter": filter_key,
        "behind_count": behind_count,
        "total_count": len(all_groups),
    }


@router.get("/groups/{group_id}")
def get_group_detail(
    group_id: int,
    user_id: Annotated[int | None, Query()] = None,
):
    """Group detail: milestones + latest submitted document."""
    supervisor = _require_supervisor(user_id)
    supervisor_id = supervisor["id"]

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, title, project_title, status, progress, member_names, deadline_date, created_at
            FROM fyp_groups
            WHERE id = ? AND supervisor_id = ? AND status = 'accepted'
            """,
            (group_id, supervisor_id),
        )
        group_row = cursor.fetchone()
        if not group_row:
            raise HTTPException(status_code=404, detail="Group not found.")

        group = _serialize_group(group_row)
        milestones = _ensure_group_milestones(cursor, group_id, progress=float(group_row["progress"] or 0))
        conn.commit()

        cursor.execute(
            """
            SELECT id, title, filename, status, submitted_at
            FROM group_documents
            WHERE group_id = ? AND supervisor_id = ?
            ORDER BY datetime(submitted_at) DESC, id DESC
            LIMIT 1
            """,
            (group_id, supervisor_id),
        )
        doc_row = cursor.fetchone()
        latest_document = None
        if doc_row:
            latest_document = {
                "id": doc_row["id"],
                "title": doc_row["title"],
                "filename": doc_row["filename"] or "",
                "status": _normalize_document_status(doc_row["status"]),
                "submitted_at": doc_row["submitted_at"],
            }

        return {
            "group": group,
            "milestones": milestones,
            "latest_document": latest_document,
        }
    except HTTPException:
        raise
    finally:
        conn.close()


def _sync_supervisor_current_groups(cursor, supervisor_id: int) -> int:
    """Keep supervisors.current_groups aligned with accepted fyp_groups count."""
    cursor.execute(
        """
        SELECT COUNT(*) FROM fyp_groups
        WHERE supervisor_id = ? AND status = 'accepted'
        """,
        (supervisor_id,),
    )
    count = int(cursor.fetchone()[0] or 0)
    cursor.execute(
        "UPDATE supervisors SET current_groups = ? WHERE id = ?",
        (count, supervisor_id),
    )
    return count


@router.post("/groups/{group_id}/discard")
def discard_group(
    group_id: int,
    user_id: Annotated[int | None, Query()] = None,
    payload: dict[str, Any] = Body(default_factory=dict),
):
    """
    Discard an accepted group so it leaves My Groups and frees a supervision slot.
    Soft-deletes via status='discarded' (history kept; no longer listed as accepted).
    """
    supervisor = _require_supervisor(user_id)
    supervisor_id = supervisor["id"]
    reason = (payload.get("reason") or payload.get("note") or "").strip()

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, title, project_title, status, student_contact_email, member_names
            FROM fyp_groups
            WHERE id = ? AND supervisor_id = ?
              AND COALESCE(org_id, 1) = ?
            """,
            (group_id, supervisor_id, _supervisor_org_id(supervisor)),
        )
        group = cursor.fetchone()
        if not group:
            raise HTTPException(status_code=404, detail="Group not found.")
        if (group["status"] or "").strip().lower() != "accepted":
            raise HTTPException(
                status_code=409,
                detail="Only accepted groups can be discarded.",
            )

        # Collect notify emails before unlinking assignment_requests
        student_emails = _get_group_notify_emails(cursor, group_id, supervisor_id)
        if not student_emails:
            contact = (group["student_contact_email"] or "").strip().lower()
            if contact:
                student_emails = [contact]
            for member in _parse_member_names(group["member_names"]):
                email = _email_from_member_label(member)
                if email and email not in student_emails:
                    student_emails.append(email)

        cursor.execute(
            "UPDATE fyp_groups SET status = 'discarded' WHERE id = ?",
            (group_id,),
        )
        # Linked assignment request no longer maps to an active group
        cursor.execute(
            """
            UPDATE assignment_requests
            SET fyp_group_id = NULL
            WHERE fyp_group_id = ? AND supervisor_id = ?
            """,
            (group_id, supervisor_id),
        )

        slots_used = _sync_supervisor_current_groups(cursor, supervisor_id)

        supervisor_name = supervisor.get("name") or "Your supervisor"
        group_title = group["title"] or "your group"
        note_suffix = f" Reason: {reason}" if reason else ""
        for student_email in student_emails:
            _create_notification(
                cursor,
                recipient_email=student_email,
                title="Group discarded by supervisor",
                message=(
                    f"{supervisor_name} discarded group '{group_title}'. "
                    f"This frees their supervision slot.{note_suffix}"
                ),
                notification_type="group_discarded",
                related_type="fyp_group",
                related_id=group_id,
                org_id=_supervisor_org_id(supervisor),
            )

        conn.commit()
        return {
            "success": True,
            "message": f"Group '{group_title}' discarded. Slot freed.",
            "group_id": group_id,
            "slots_used": slots_used,
            "max_groups": int(supervisor.get("max_groups") or 6),
            "notified_emails": student_emails,
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Failed to discard group %s", group_id)
        raise HTTPException(status_code=500, detail="Could not discard group.")
    finally:
        conn.close()


@router.get("/assignment-requests")
def list_assignment_requests(
    user_id: Annotated[int | None, Query()] = None,
    status: Annotated[str, Query()] = "pending",
):
    """List assignment requests for the logged-in supervisor."""
    supervisor = _require_supervisor(user_id)
    supervisor_id = supervisor["id"]
    status_filter = (status or "pending").strip().lower()

    conn = get_db()
    cursor = conn.cursor()
    query = """
        SELECT ar.*, d.name AS department_name, d.code AS department_code
        FROM assignment_requests ar
        LEFT JOIN departments d ON d.id = ar.department_id
        WHERE ar.supervisor_id = ?
    """
    params: list[Any] = [supervisor_id]
    if status_filter and status_filter != "all":
        query += " AND ar.status = ?"
        params.append(status_filter)
    query += " ORDER BY ar.created_at DESC, ar.id DESC"

    cursor.execute(query, params)
    rows = []
    for row in cursor.fetchall():
        item = _serialize_assignment_request(row)
        if not item["department_name"] and supervisor.get("department_name"):
            item["department_name"] = supervisor.get("department_name") or ""
            item["department_code"] = supervisor.get("department_code") or ""
            item["department_id"] = item["department_id"] or supervisor.get("department_id")
        rows.append(item)
    conn.close()
    return {"requests": rows, "count": len(rows)}


@router.post("/assignment-requests/{request_id}/accept")
def accept_assignment_request(
    request_id: int,
    user_id: Annotated[int | None, Query()] = None,
):
    """Accept a pending request and add the group to the supervisor's groups."""
    supervisor = _require_supervisor(user_id)
    supervisor_id = supervisor["id"]

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT ar.*, d.name AS department_name, d.code AS department_code
            FROM assignment_requests ar
            JOIN supervisors s ON s.id = ar.supervisor_id
            LEFT JOIN departments d ON d.id = ar.department_id
            WHERE ar.id = ? AND ar.supervisor_id = ?
              AND COALESCE(s.org_id, 1) = ?
            """,
            (request_id, supervisor_id, _supervisor_org_id(supervisor)),
        )
        request_row = cursor.fetchone()
        if not request_row:
            raise HTTPException(status_code=404, detail="Assignment request not found.")
        if request_row["status"] != "pending":
            raise HTTPException(status_code=409, detail="This request has already been resolved.")

        max_groups = int(supervisor.get("max_groups") or 6)
        current_groups = int(supervisor.get("current_groups") or 0)
        if current_groups >= max_groups:
            raise HTTPException(
                status_code=400,
                detail=f"You have reached your max group limit ({max_groups}).",
            )

        department_id = request_row["department_id"] or supervisor.get("department_id")
        members = request_row["member_names"]
        if not members and request_row["student_leader_name"]:
            members = json.dumps([request_row["student_leader_name"]])
        member_labels = _parse_member_names(members)
        leader_email = (request_row["student_leader_email"] or "").strip() or None
        org_id = _supervisor_org_id(supervisor)

        # Prefill group department/semester from the LEADER's user profile.
        leader_profile = _lookup_user_profile_by_email(cursor, leader_email, org_id)
        leader_department_id = None
        leader_semester = None
        if leader_profile:
            if leader_profile.get("department_id") is not None:
                try:
                    leader_department_id = int(leader_profile["department_id"])
                except (TypeError, ValueError):
                    leader_department_id = None
            if leader_profile.get("current_semester") is not None:
                try:
                    leader_semester = int(leader_profile["current_semester"])
                except (TypeError, ValueError):
                    leader_semester = None

        if leader_department_id is not None:
            department_id = leader_department_id
        current_semester = leader_semester if leader_semester in (6, 7) else 6

        # Informational only — never blocks accept.
        profile_mismatch_warnings = _collect_member_profile_mismatches(
            cursor,
            leader_email=leader_email,
            leader_department_id=department_id if department_id is not None else leader_department_id,
            leader_semester=current_semester,
            member_labels=member_labels,
            org_id=org_id,
        )

        deadline = _resolve_default_deadline(cursor, department_id, org_id)
        req_keys = set(request_row.keys()) if hasattr(request_row, "keys") else set()
        cosupervisor_name = (
            str(request_row["cosupervisor_name"]).strip()
            if "cosupervisor_name" in req_keys and request_row["cosupervisor_name"]
            else None
        )

        cursor.execute(
            """
            INSERT INTO fyp_groups
                (supervisor_id, title, project_title, status, progress, member_names,
                 deadline_date, department_id, student_contact_email, cosupervisor_name,
                 current_semester, org_id)
            VALUES (?, ?, ?, 'accepted', 0, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                supervisor_id,
                request_row["group_name"],
                request_row["project_title"] or "",
                members,
                deadline,
                department_id,
                leader_email,
                cosupervisor_name,
                current_semester,
                org_id,
            ),
        )
        group_id = cursor.lastrowid

        _ensure_group_milestones(cursor, group_id, progress=0)

        resolved_at = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
        cursor.execute(
            """
            UPDATE assignment_requests
            SET status = 'accepted', fyp_group_id = ?, resolved_at = ?, rejection_reason = NULL
            WHERE id = ?
            """,
            (group_id, resolved_at, request_id),
        )
        _sync_supervisor_current_groups(cursor, supervisor_id)

        supervisor_name = supervisor.get("name") or "Your supervisor"
        topic = request_row["project_title"] or request_row["group_name"]
        _create_notification(
            cursor,
            recipient_email=request_row["student_leader_email"],
            title="Assignment request accepted",
            message=(
                f"{supervisor_name} accepted your group '{request_row['group_name']}' "
                f"for topic '{topic}'."
            ),
            notification_type="assignment_accepted",
            related_type="assignment_request",
            related_id=request_id,
            org_id=_supervisor_org_id(supervisor),
        )

        conn.commit()
        cursor.execute(
            """
            SELECT ar.*, d.name AS department_name, d.code AS department_code
            FROM assignment_requests ar
            LEFT JOIN departments d ON d.id = ar.department_id
            WHERE ar.id = ?
            """,
            (request_id,),
        )
        updated = cursor.fetchone()
        cursor.execute(
            """
            SELECT id, title, project_title, status, progress, member_names, deadline_date,
                   created_at, department_id, current_semester, student_contact_email
            FROM fyp_groups WHERE id = ?
            """,
            (group_id,),
        )
        group_row = cursor.fetchone()
        return {
            "success": True,
            "message": "Request accepted. Group added to My Groups.",
            "request": _serialize_assignment_request(updated),
            "group": _serialize_group(group_row),
            "profile_mismatch_warnings": profile_mismatch_warnings,
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Failed to accept assignment request %s", request_id)
        raise HTTPException(status_code=500, detail="Could not accept assignment request.")
    finally:
        conn.close()


@router.post("/assignment-requests/{request_id}/reject")
def reject_assignment_request(
    request_id: int,
    user_id: Annotated[int | None, Query()] = None,
    payload: dict[str, Any] = Body(default_factory=dict),
):
    """Reject a pending request with a required reason and notify the student."""
    supervisor = _require_supervisor(user_id)
    supervisor_id = supervisor["id"]
    reason = (payload.get("reason") or payload.get("rejection_reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="A rejection reason is required.")

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT ar.*, d.name AS department_name, d.code AS department_code
            FROM assignment_requests ar
            JOIN supervisors s ON s.id = ar.supervisor_id
            LEFT JOIN departments d ON d.id = ar.department_id
            WHERE ar.id = ? AND ar.supervisor_id = ?
              AND COALESCE(s.org_id, 1) = ?
            """,
            (request_id, supervisor_id, _supervisor_org_id(supervisor)),
        )
        request_row = cursor.fetchone()
        if not request_row:
            raise HTTPException(status_code=404, detail="Assignment request not found.")
        if request_row["status"] != "pending":
            raise HTTPException(status_code=409, detail="This request has already been resolved.")

        resolved_at = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
        cursor.execute(
            """
            UPDATE assignment_requests
            SET status = 'rejected', rejection_reason = ?, resolved_at = ?
            WHERE id = ?
            """,
            (reason, resolved_at, request_id),
        )

        supervisor_name = supervisor.get("name") or "Your supervisor"
        _create_notification(
            cursor,
            recipient_email=request_row["student_leader_email"],
            title="Assignment request rejected",
            message=(
                f"{supervisor_name} rejected your group '{request_row['group_name']}'. "
                f"Reason: {reason}"
            ),
            notification_type="assignment_rejected",
            related_type="assignment_request",
            related_id=request_id,
            org_id=_supervisor_org_id(supervisor),
        )

        conn.commit()
        cursor.execute(
            """
            SELECT ar.*, d.name AS department_name, d.code AS department_code
            FROM assignment_requests ar
            LEFT JOIN departments d ON d.id = ar.department_id
            WHERE ar.id = ?
            """,
            (request_id,),
        )
        updated = cursor.fetchone()
        return {
            "success": True,
            "message": "Request rejected. The student has been notified.",
            "request": _serialize_assignment_request(updated),
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Failed to reject assignment request %s", request_id)
        raise HTTPException(status_code=500, detail="Could not reject assignment request.")
    finally:
        conn.close()


def _get_group_student_email(cursor, group_id: int, supervisor_id: int | None = None) -> str | None:
    cursor.execute(
        """
        SELECT student_contact_email
        FROM fyp_groups
        WHERE id = ? AND student_contact_email IS NOT NULL AND TRIM(student_contact_email) != ''
        """,
        (group_id,),
    )
    row = cursor.fetchone()
    if row and row["student_contact_email"]:
        return str(row["student_contact_email"]).strip()

    cursor.execute(
        """
        SELECT student_leader_email
        FROM assignment_requests
        WHERE fyp_group_id = ? AND student_leader_email IS NOT NULL AND TRIM(student_leader_email) != ''
        ORDER BY id DESC
        LIMIT 1
        """,
        (group_id,),
    )
    row = cursor.fetchone()
    if row and row["student_leader_email"]:
        return str(row["student_leader_email"]).strip()

    cursor.execute("SELECT title FROM fyp_groups WHERE id = ?", (group_id,))
    group = cursor.fetchone()
    if group and group["title"]:
        params: list[Any] = [group["title"]]
        query = """
            SELECT student_leader_email
            FROM assignment_requests
            WHERE LOWER(group_name) = LOWER(?)
              AND student_leader_email IS NOT NULL
              AND TRIM(student_leader_email) != ''
        """
        if supervisor_id is not None:
            query += " AND supervisor_id = ?"
            params.append(supervisor_id)
        query += " ORDER BY id DESC LIMIT 1"
        cursor.execute(query, params)
        row = cursor.fetchone()
        if row and row["student_leader_email"]:
            return str(row["student_leader_email"]).strip()
    return None


def _require_group_document(cursor, *, group_id: int, document_id: int, supervisor_id: int):
    cursor.execute(
        """
        SELECT gd.*, fg.title AS group_title
        FROM group_documents gd
        JOIN fyp_groups fg ON fg.id = gd.group_id
        WHERE gd.id = ? AND gd.group_id = ? AND gd.supervisor_id = ? AND fg.supervisor_id = ?
        """,
        (document_id, group_id, supervisor_id, supervisor_id),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found for this group.")
    return row


def _resolve_group_document_path(cursor, document_id: int, file_path: str | None = None) -> str | None:
    import os

    path = file_path
    source_id = None
    if not path:
        cursor.execute(
            "SELECT file_url, source_document_id FROM group_documents WHERE id = ?",
            (document_id,),
        )
        row = cursor.fetchone()
        if row:
            path = row["file_url"]
            source_id = row["source_document_id"]
            if (not path or not str(path).strip()) and source_id:
                cursor.execute(
                    "SELECT file_path FROM documents WHERE id = ?",
                    (source_id,),
                )
                src = cursor.fetchone()
                if src:
                    path = src["file_path"]
    else:
        cursor.execute(
            "SELECT source_document_id FROM group_documents WHERE id = ?",
            (document_id,),
        )
        row = cursor.fetchone()
        if row:
            source_id = row["source_document_id"]

    if source_id is not None:
        working = os.path.join("uploads", "working", f"doc_{source_id}_working.docx")
        if os.path.exists(working):
            path = working

    if path and os.path.exists(str(path)):
        return str(path)
    return None


def _ensure_meta_column(cursor) -> None:
    """document_paragraphs.meta_json holds tables, images, fonts, runs ... (idempotent)."""
    cursor.execute("PRAGMA table_info(document_paragraphs)")
    if "meta_json" not in {row[1] for row in cursor.fetchall()}:
        cursor.execute("ALTER TABLE document_paragraphs ADD COLUMN meta_json TEXT")


def _row_meta_version(row) -> int:
    try:
        raw = row["meta_json"]
        return int((json.loads(raw) or {}).get("v", 0)) if raw else 0
    except (TypeError, ValueError, KeyError, IndexError):
        return 0


def _review_file_signature(path: str) -> str:
    import os

    st = os.stat(path)
    return f"{int(st.st_mtime)}:{st.st_size}"


def _stored_source_file_sig(rows) -> str | None:
    for row in rows:
        try:
            raw = row["meta_json"]
            if not raw:
                continue
            sig = (json.loads(raw) or {}).get("source_file_sig")
            if sig:
                return str(sig)
        except (TypeError, ValueError, KeyError):
            continue
    return None


def _block_to_meta(block: dict[str, Any], *, source_file_sig: str | None = None) -> dict[str, Any]:
    from docx_tools.review_blocks import EXTRACT_VERSION

    meta = {
        k: v
        for k, v in block.items()
        if k not in ("text", "block_type", "skipped")
        and v is not None
        and v != ""
        and v != []
    }
    meta["v"] = EXTRACT_VERSION
    if source_file_sig:
        meta["source_file_sig"] = source_file_sig
    return meta


def _sync_paragraphs_from_extract(
    cursor,
    document_id: int,
    existing: list,
    blocks: list[dict[str, Any]],
    source_file_sig: str | None,
) -> None:
    """Refresh text / types / formatting in place so comment paragraph_ids stay valid."""
    from docx_tools.review_blocks import BLOCK_PARAGRAPH

    ordered = sorted(existing, key=lambda r: (r["sort_order"], r["id"]))
    for idx, row in enumerate(ordered):
        if idx >= len(blocks):
            break
        block = blocks[idx]
        meta = _block_to_meta(block, source_file_sig=source_file_sig)
        cursor.execute(
            """
            UPDATE document_paragraphs
            SET text = ?, block_type = ?, meta_json = ?, sort_order = ?
            WHERE id = ?
            """,
            (
                block["text"],
                block.get("block_type") or BLOCK_PARAGRAPH,
                json.dumps(meta),
                idx + 1,
                row["id"],
            ),
        )


def _ensure_document_paragraphs(
    cursor,
    document_id: int,
    document_title: str = "",
    file_path: str | None = None,
) -> None:
    """
    Ensure classified body blocks exist for Document Review.
    - Empty → extract (skip front-matter, label heading/paragraph/line/bullet)
    - Legacy rows without useful block_type → re-extract if no comments,
      else reclassify in place and hide front-matter rows.
    """
    from docx_tools.review_blocks import (
        BLOCK_FRONTMATTER,
        BLOCK_PARAGRAPH,
        EXTRACT_VERSION,
        classify_block_text,
        extract_review_blocks,
        frontmatter_text_set,
    )

    _ensure_meta_column(cursor)
    cursor.execute(
        "SELECT id, text, block_type, meta_json FROM document_paragraphs WHERE document_id = ?",
        (document_id,),
    )
    existing = cursor.fetchall()
    path = _resolve_group_document_path(cursor, document_id, file_path)

    file_sig = _review_file_signature(path) if path else None

    def _insert_blocks(blocks: list[dict[str, Any]]) -> None:
        for order, block in enumerate(blocks, start=1):
            meta = _block_to_meta(block, source_file_sig=file_sig)
            cursor.execute(
                """
                INSERT INTO document_paragraphs
                    (document_id, sort_order, text, block_type, meta_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    order,
                    block["text"],
                    block.get("block_type") or BLOCK_PARAGRAPH,
                    json.dumps(meta),
                ),
            )

    placeholder_blocks = [
        {
            "text": (
                f"{document_title}: Document submitted for supervisor review."
                if document_title
                else "Document submitted for supervisor review."
            ),
            "block_type": BLOCK_PARAGRAPH,
        },
        {
            "text": "Download the original file for full layout; use comments on sections below.",
            "block_type": "line",
        },
    ]

    if not existing:
        blocks = extract_review_blocks(path or "") if path else []
        _insert_blocks(blocks or placeholder_blocks)
        return

    types = [
        ((row["block_type"] if "block_type" in row.keys() else None) or "").strip().lower()
        for row in existing
    ]
    frontmatter_count = sum(1 for t in types if t == BLOCK_FRONTMATTER)
    # All-default paragraphs, OR everything wrongly marked frontmatter → rebuild/repair
    needs_upgrade = all(t in ("", "paragraph") for t in types) or (
        len(types) > 0 and frontmatter_count >= len(types)
    )
    # Rows saved by an older extractor (no tables / images / fonts) are refreshed,
    # but only when the document has no comments, so comment anchors stay intact.
    stale_meta = (
        not needs_upgrade
        and max((_row_meta_version(row) for row in existing), default=0) < EXTRACT_VERSION
    )
    stored_sig = _stored_source_file_sig(existing)
    stale_file = bool(path and file_sig and stored_sig and file_sig != stored_sig)
    needs_file_resync = bool(path and file_sig and not stored_sig)
    if not needs_upgrade and not stale_meta and not stale_file and not needs_file_resync:
        return

    cursor.execute(
        "SELECT COUNT(*) FROM document_comments WHERE document_id = ?",
        (document_id,),
    )
    comment_count = int(cursor.fetchone()[0] or 0)

    if path:
        blocks = extract_review_blocks(path)
    else:
        blocks = []

    if comment_count == 0 and path:
        cursor.execute(
            "DELETE FROM document_paragraphs WHERE document_id = ?",
            (document_id,),
        )
        _insert_blocks(blocks or placeholder_blocks)
        return

    if path and blocks and (
        needs_upgrade or stale_meta or stale_file or needs_file_resync
    ):
        _sync_paragraphs_from_extract(
            cursor, document_id, list(existing), blocks, file_sig
        )
        return

    # Preserve comment anchors: reclassify text in place; mark only true front-matter
    fm_texts = frontmatter_text_set(path) if path else set()
    # Safety: never hide the whole document as front-matter
    if fm_texts and len(fm_texts) >= max(1, int(len(existing) * 0.8)):
        fm_texts = set()
    for row in existing:
        text = (row["text"] or "").strip()
        if not text:
            continue
        if text in fm_texts:
            new_type = BLOCK_FRONTMATTER
        else:
            new_type = classify_block_text(text) or BLOCK_PARAGRAPH
        cursor.execute(
            "UPDATE document_paragraphs SET block_type = ? WHERE id = ?",
            (new_type, row["id"]),
        )


def _serialize_review_paragraphs(cursor, document_id: int) -> list[dict[str, Any]]:
    from docx_tools.review_blocks import BLOCK_FRONTMATTER, display_label_for_block_type

    _ensure_meta_column(cursor)
    cursor.execute(
        """
        SELECT id, sort_order, text, block_type, meta_json
        FROM document_paragraphs
        WHERE document_id = ?
        ORDER BY sort_order ASC, id ASC
        """,
        (document_id,),
    )
    paragraphs = []
    display_index = 0
    for row in cursor.fetchall():
        keys = set(row.keys()) if hasattr(row, "keys") else set()
        block_type = (
            (row["block_type"] if "block_type" in keys else None) or "paragraph"
        ).strip().lower()
        if block_type == BLOCK_FRONTMATTER:
            continue
        try:
            meta = json.loads(row["meta_json"]) if row["meta_json"] else {}
        except (TypeError, ValueError):
            meta = {}
        if not isinstance(meta, dict):
            meta = {}
        has_rich = bool(meta.get("table_rows") or meta.get("images"))
        # Skip empty lines if any slipped through (tables / images may carry no text)
        if not (row["text"] or "").strip() and not has_rich:
            continue

        display_index += 1
        cursor.execute(
            """
            SELECT id, comment_text, is_resolved, created_at, resolved_at,
                   supervisor_id, parent_comment_id
            FROM document_comments
            WHERE paragraph_id = ?
            ORDER BY datetime(created_at) ASC, id ASC
            """,
            (row["id"],),
        )
        comments = []
        has_unresolved = False
        has_resolved = False
        for comment in cursor.fetchall():
            resolved = bool(comment["is_resolved"])
            ckeys = comment.keys()
            parent_id = (
                comment["parent_comment_id"]
                if "parent_comment_id" in ckeys
                else None
            )
            # Only top-level supervisor comments drive yellow/gray highlight
            if parent_id is None:
                if resolved:
                    has_resolved = True
                else:
                    has_unresolved = True
            comments.append(
                {
                    "id": comment["id"],
                    "comment_text": comment["comment_text"],
                    "is_resolved": resolved,
                    "created_at": comment["created_at"],
                    "resolved_at": comment["resolved_at"],
                    "supervisor_id": comment["supervisor_id"],
                    "parent_comment_id": parent_id,
                }
            )
        # Highlight priority: unresolved (yellow) > resolved-only (gray) > none
        if has_unresolved:
            highlight = "unresolved"
        elif has_resolved:
            highlight = "resolved"
        else:
            highlight = "none"
        item = {
            "id": row["id"],
            "sort_order": row["sort_order"],
            "display_index": display_index,
            "text": row["text"],
            "block_type": block_type,
            "block_label": display_label_for_block_type(block_type),
            "highlight": highlight,
            "has_unresolved_comments": has_unresolved,
            "comments": comments,
        }
        # formatting / rich content: style_name, font_*, is_bold, runs, table_rows,
        # images, page_number ... (never overrides the core fields above)
        item.update({k: v for k, v in meta.items() if k not in item and k != "v"})
        paragraphs.append(item)
    return paragraphs


@router.get("/groups/{group_id}/documents/{document_id}/review")
def get_document_review(
    group_id: int,
    document_id: int,
    user_id: Annotated[int | None, Query()] = None,
):
    """Paragraph-level document review payload for a group submission."""
    supervisor = _require_supervisor(user_id)
    supervisor_id = supervisor["id"]

    conn = get_db()
    cursor = conn.cursor()
    try:
        doc = _require_group_document(
            cursor,
            group_id=group_id,
            document_id=document_id,
            supervisor_id=supervisor_id,
        )
        _ensure_document_paragraphs(cursor, document_id, document_title=doc["title"] or "")
        conn.commit()
        paragraphs = _serialize_review_paragraphs(cursor, document_id)
        return {
            "group_id": group_id,
            "group_title": doc["group_title"] or "",
            "document": {
                "id": doc["id"],
                "title": doc["title"],
                "filename": doc["filename"] or "",
                "status": _normalize_document_status(doc["status"]),
                "submitted_at": doc["submitted_at"],
            },
            "paragraphs": paragraphs,
        }
    finally:
        conn.close()


@router.post("/groups/{group_id}/documents/{document_id}/paragraphs/{paragraph_id}/comments")
def add_document_comment(
    group_id: int,
    document_id: int,
    paragraph_id: int,
    user_id: Annotated[int | None, Query()] = None,
    payload: dict[str, Any] = Body(default_factory=dict),
):
    """Add a comment on a paragraph and notify all group members."""
    supervisor = _require_supervisor(user_id)
    supervisor_id = supervisor["id"]
    comment_text = (payload.get("comment_text") or payload.get("comment") or "").strip()
    if not comment_text:
        raise HTTPException(status_code=400, detail="Comment text is required.")

    conn = get_db()
    cursor = conn.cursor()
    try:
        doc = _require_group_document(
            cursor,
            group_id=group_id,
            document_id=document_id,
            supervisor_id=supervisor_id,
        )
        cursor.execute(
            """
            SELECT id, text FROM document_paragraphs
            WHERE id = ? AND document_id = ?
            """,
            (paragraph_id, document_id),
        )
        paragraph = cursor.fetchone()
        if not paragraph:
            raise HTTPException(status_code=404, detail="Paragraph not found.")

        cursor.execute(
            """
            INSERT INTO document_comments
                (paragraph_id, document_id, supervisor_id, comment_text, is_resolved)
            VALUES (?, ?, ?, ?, 0)
            """,
            (paragraph_id, document_id, supervisor_id, comment_text),
        )
        comment_id = cursor.lastrowid

        student_emails = _get_group_notify_emails(cursor, group_id, supervisor_id)
        supervisor_name = supervisor.get("name") or "Your supervisor"
        snippet = paragraph["text"][:80] + ("…" if len(paragraph["text"] or "") > 80 else "")
        for student_email in student_emails:
            _create_notification(
                cursor,
                recipient_email=student_email,
                title="New document comment",
                message=(
                    f"{supervisor_name} commented on '{doc['title']}': {comment_text} "
                    f"(paragraph: {snippet})"
                ),
                notification_type="document_comment",
                related_type="document_comment",
                related_id=comment_id,
                org_id=_supervisor_org_id(supervisor),
            )

        # Mark document + linked final submission as needing revision so Status Tracker updates
        cursor.execute(
            "UPDATE group_documents SET status = 'revision' WHERE id = ?",
            (document_id,),
        )
        cursor.execute(
            """
            UPDATE final_submissions
            SET status = 'revision',
                decision_note = COALESCE(
                    NULLIF(TRIM(decision_note), ''),
                    'Supervisor left paragraph comments — open document feedback to resolve.'
                )
            WHERE group_document_id = ?
              AND status IN ('pending', 'pending_review', 'revision')
            """,
            (document_id,),
        )

        conn.commit()
        paragraphs = _serialize_review_paragraphs(cursor, document_id)
        return {
            "success": True,
            "message": (
                f"Comment added. Notified {len(student_emails)} group member"
                f"{'' if len(student_emails) == 1 else 's'}."
            ),
            "comment_id": comment_id,
            "paragraphs": paragraphs,
            "notified_email": student_emails[0] if student_emails else "",
            "notified_emails": student_emails,
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Failed to add document comment")
        raise HTTPException(status_code=500, detail="Could not add comment.")
    finally:
        conn.close()


@router.post("/groups/{group_id}/documents/{document_id}/paragraphs/{paragraph_id}/resolve")
def resolve_paragraph_comments(
    group_id: int,
    document_id: int,
    paragraph_id: int,
    user_id: Annotated[int | None, Query()] = None,
):
    """Mark all unresolved comments on a paragraph as resolved (gray highlight)."""
    supervisor = _require_supervisor(user_id)
    supervisor_id = supervisor["id"]

    conn = get_db()
    cursor = conn.cursor()
    try:
        _require_group_document(
            cursor,
            group_id=group_id,
            document_id=document_id,
            supervisor_id=supervisor_id,
        )
        cursor.execute(
            "SELECT id FROM document_paragraphs WHERE id = ? AND document_id = ?",
            (paragraph_id, document_id),
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Paragraph not found.")

        resolved_at = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
        cursor.execute(
            """
            UPDATE document_comments
            SET is_resolved = 1, resolved_at = ?
            WHERE paragraph_id = ? AND document_id = ? AND is_resolved = 0
            """,
            (resolved_at, paragraph_id, document_id),
        )
        conn.commit()
        return {
            "success": True,
            "message": "Comments marked as resolved.",
            "paragraphs": _serialize_review_paragraphs(cursor, document_id),
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Failed to resolve paragraph comments")
        raise HTTPException(status_code=500, detail="Could not resolve comments.")
    finally:
        conn.close()


def _parse_analysis_report(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    text = str(raw).strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _analysis_summary(report: dict[str, Any]) -> dict[str, Any]:
    stats = report.get("stats") if isinstance(report.get("stats"), dict) else {}
    structure = report.get("structure") if isinstance(report.get("structure"), dict) else {}
    summary = structure.get("summary") if isinstance(structure.get("summary"), dict) else {}
    issues = report.get("issues") if isinstance(report.get("issues"), list) else []
    grammar_issues = int(stats.get("grammar_issues") or summary.get("grammar") or 0)
    plagiarism_issues = int(stats.get("plagiarism_issues") or summary.get("plagiarism") or 0)
    plagiarism_score = float(stats.get("avg_plagiarism_risk") or 0)
    # Prefer 0–100 risk; if values look like 0–1, scale up
    if 0 < plagiarism_score <= 1:
        plagiarism_score = round(plagiarism_score * 100, 1)
    compliance = float(report.get("compliance_score") or structure.get("score") or stats.get("avg_formatting_compliance") or 0)
    return {
        "grammar_issues": grammar_issues,
        "plagiarism_issues": plagiarism_issues,
        "plagiarism_score": plagiarism_score,
        "total_issues": int(stats.get("total_issues") or len(issues) or 0),
        "major_issues": int(stats.get("major_issues") or 0),
        "minor_issues": int(stats.get("minor_issues") or 0),
        "compliance_score": compliance,
        "structure_status": str(structure.get("status") or ""),
    }


def _serialize_final_submission(row, *, include_report: bool = False) -> dict[str, Any]:
    report = _parse_analysis_report(row["analysis_report"] if "analysis_report" in row.keys() else None)
    summary = _analysis_summary(report)
    keys = set(row.keys()) if hasattr(row, "keys") else set()
    payload = {
        "id": row["id"],
        "group_id": row["group_id"],
        "group_title": row["group_title"] if "group_title" in keys else "",
        "project_title": row["project_title"] if "project_title" in keys else "",
        "title": row["title"],
        "filename": row["filename"] or "",
        "status": row["status"],
        "submitted_at": row["submitted_at"],
        "resolved_at": row["resolved_at"],
        "decision_note": row["decision_note"] or "",
        "student_contact_email": row["student_contact_email"] or "",
        "source_document_id": row["source_document_id"] if "source_document_id" in keys else None,
        "group_document_id": row["group_document_id"] if "group_document_id" in keys else None,
        "analysis_summary": summary,
    }
    if include_report:
        payload["analysis_report"] = report
        # Surface grammar / plagiarism issue subsets for the UI (same shape as student analyze)
        issues = report.get("issues") if isinstance(report.get("issues"), list) else []
        payload["grammar_issues"] = [i for i in issues if str(i.get("function") or "").lower() == "grammar"]
        payload["plagiarism_issues"] = [i for i in issues if str(i.get("function") or "").lower() == "plagiarism"]
    return payload


def _load_submission_row(cursor, submission_id: int, supervisor_id: int):
    cursor.execute(
        """
        SELECT fs.*, fg.title AS group_title, fg.project_title AS project_title
        FROM final_submissions fs
        JOIN fyp_groups fg ON fg.id = fs.group_id
        WHERE fs.id = ? AND fs.supervisor_id = ?
        """,
        (submission_id, supervisor_id),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Submission not found.")
    return row


@router.get("/submissions")
def list_final_submissions(
    user_id: Annotated[int | None, Query()] = None,
    status: Annotated[str, Query()] = "pending",
):
    """List final submissions for the supervisor (default: pending review)."""
    supervisor = _require_supervisor(user_id)
    supervisor_id = supervisor["id"]
    status_filter = (status or "pending").strip().lower()

    conn = get_db()
    cursor = conn.cursor()
    query = """
        SELECT fs.*, fg.title AS group_title, fg.project_title AS project_title
        FROM final_submissions fs
        JOIN fyp_groups fg ON fg.id = fs.group_id
        WHERE fs.supervisor_id = ?
    """
    params: list[Any] = [supervisor_id]
    if status_filter and status_filter != "all":
        query += " AND fs.status = ?"
        params.append(status_filter)
    query += " ORDER BY datetime(fs.submitted_at) DESC, fs.id DESC"
    cursor.execute(query, params)
    rows = [_serialize_final_submission(row) for row in cursor.fetchall()]
    conn.close()
    return {"submissions": rows, "count": len(rows)}


@router.get("/submissions/{submission_id}")
def get_final_submission(
    submission_id: int,
    user_id: Annotated[int | None, Query()] = None,
):
    """Submission detail including Formatify AI analysis snapshot."""
    supervisor = _require_supervisor(user_id)
    conn = get_db()
    cursor = conn.cursor()
    try:
        row = _load_submission_row(cursor, submission_id, supervisor["id"])
        return _serialize_final_submission(row, include_report=True)
    finally:
        conn.close()


def _resolve_submission_file_path(cursor, row) -> tuple[str, str]:
    """Return (absolute_or_relative_path, download_filename) for a submission row."""
    import os

    keys = set(row.keys()) if hasattr(row, "keys") else set()
    filename = (row["filename"] or "submission.docx") if "filename" in keys else "submission.docx"
    path = None

    # Prefer linked group_document.file_url
    if "group_document_id" in keys and row["group_document_id"]:
        cursor.execute(
            "SELECT file_url, filename, source_document_id FROM group_documents WHERE id = ?",
            (row["group_document_id"],),
        )
        gd = cursor.fetchone()
        if gd:
            path = gd["file_url"]
            if gd["filename"]:
                filename = gd["filename"]
            if (not path or not os.path.exists(str(path))) and gd["source_document_id"]:
                cursor.execute(
                    "SELECT file_path, filename FROM documents WHERE id = ?",
                    (gd["source_document_id"],),
                )
                src = cursor.fetchone()
                if src:
                    path = src["file_path"]
                    if src["filename"]:
                        filename = src["filename"]

    if (not path or not os.path.exists(str(path))) and "source_document_id" in keys and row["source_document_id"]:
        sid = row["source_document_id"]
        working = os.path.join("uploads", "working", f"doc_{sid}_working.docx")
        if os.path.exists(working):
            path = working
        else:
            cursor.execute(
                "SELECT file_path, filename FROM documents WHERE id = ?",
                (sid,),
            )
            src = cursor.fetchone()
            if src:
                path = src["file_path"]
                if src["filename"]:
                    filename = src["filename"]

    if not path or not os.path.exists(str(path)):
        raise HTTPException(status_code=404, detail="Submitted file not found on server.")
    return str(path), str(filename)


@router.get("/submissions/{submission_id}/download")
def download_final_submission(
    submission_id: int,
    user_id: Annotated[int | None, Query()] = None,
):
    """Download the original submitted DOCX/PDF for supervisor review."""
    supervisor = _require_supervisor(user_id)
    conn = get_db()
    cursor = conn.cursor()
    try:
        row = _load_submission_row(cursor, submission_id, supervisor["id"])
        path, filename = _resolve_submission_file_path(cursor, row)
        return FileResponse(
            path=path,
            filename=filename,
            media_type="application/octet-stream",
        )
    finally:
        conn.close()


@router.get("/groups/{group_id}/documents/{document_id}/download")
def download_group_document(
    group_id: int,
    document_id: int,
    user_id: Annotated[int | None, Query()] = None,
):
    """Download a group document file under review."""
    import os

    supervisor = _require_supervisor(user_id)
    conn = get_db()
    cursor = conn.cursor()
    try:
        doc = _require_group_document(
            cursor,
            group_id=group_id,
            document_id=document_id,
            supervisor_id=supervisor["id"],
        )
        path = doc["file_url"] if "file_url" in doc.keys() else None
        filename = doc["filename"] or "document.docx"
        source_id = doc["source_document_id"] if "source_document_id" in doc.keys() else None
        if (not path or not os.path.exists(str(path))) and source_id:
            working = os.path.join("uploads", "working", f"doc_{source_id}_working.docx")
            if os.path.exists(working):
                path = working
            else:
                cursor.execute(
                    "SELECT file_path, filename FROM documents WHERE id = ?",
                    (source_id,),
                )
                src = cursor.fetchone()
                if src:
                    path = src["file_path"]
                    if src["filename"]:
                        filename = src["filename"]
        if not path or not os.path.exists(str(path)):
            raise HTTPException(status_code=404, detail="Document file not found on server.")
        return FileResponse(
            path=str(path),
            filename=str(filename),
            media_type="application/octet-stream",
        )
    finally:
        conn.close()


def _decide_submission(
    *,
    submission_id: int,
    user_id: int | None,
    new_status: str,
    note: str,
    notify_title: str,
    notify_message: str,
):
    supervisor = _require_supervisor(user_id)
    supervisor_id = supervisor["id"]
    conn = get_db()
    cursor = conn.cursor()
    try:
        row = _load_submission_row(cursor, submission_id, supervisor_id)
        if row["status"] != "pending":
            raise HTTPException(status_code=409, detail="This submission has already been decided.")

        resolved_at = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
        cursor.execute(
            """
            UPDATE final_submissions
            SET status = ?, decision_note = ?, resolved_at = ?
            WHERE id = ?
            """,
            (new_status, note or None, resolved_at, submission_id),
        )

        student_emails = _get_group_notify_emails(cursor, row["group_id"], supervisor_id)
        if not student_emails:
            fallback = (row["student_contact_email"] or "").strip() or _get_group_student_email(
                cursor, row["group_id"], supervisor_id
            )
            if fallback:
                student_emails = [fallback]

        for student_email in student_emails:
            _create_notification(
                cursor,
                recipient_email=student_email,
                title=notify_title,
                message=notify_message,
                notification_type=f"submission_{new_status}",
                related_type="final_submission",
                related_id=submission_id,
                org_id=_supervisor_org_id(supervisor),
            )

        group_doc_id = row["group_document_id"] if "group_document_id" in row.keys() else None
        if new_status == "approved":
            if group_doc_id:
                cursor.execute(
                    "UPDATE group_documents SET status = 'approved' WHERE id = ?",
                    (group_doc_id,),
                )
            else:
                cursor.execute(
                    """
                    UPDATE group_documents
                    SET status = 'approved'
                    WHERE group_id = ? AND supervisor_id = ?
                      AND status IN ('pending', 'pending_review', 'revision')
                    """,
                    (row["group_id"], supervisor_id),
                )
            cursor.execute(
                """
                UPDATE group_milestones
                SET is_completed = 1, completed_at = ?
                WHERE group_id = ? AND LOWER(name) = 'final doc'
                """,
                (resolved_at, row["group_id"]),
            )
        elif new_status == "revision":
            if group_doc_id:
                cursor.execute(
                    "UPDATE group_documents SET status = 'revision' WHERE id = ?",
                    (group_doc_id,),
                )
            else:
                cursor.execute(
                    """
                    UPDATE group_documents
                    SET status = 'revision'
                    WHERE group_id = ? AND supervisor_id = ?
                      AND status IN ('pending', 'pending_review')
                    """,
                    (row["group_id"], supervisor_id),
                )

        conn.commit()
        updated = _load_submission_row(cursor, submission_id, supervisor_id)
        return {
            "success": True,
            "message": notify_title,
            "submission": _serialize_final_submission(updated, include_report=True),
            "notified_email": student_emails[0] if student_emails else "",
            "notified_emails": student_emails,
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Failed to decide submission %s", submission_id)
        raise HTTPException(status_code=500, detail="Could not update submission.")
    finally:
        conn.close()


@router.post("/submissions/{submission_id}/approve")
def approve_final_submission(
    submission_id: int,
    user_id: Annotated[int | None, Query()] = None,
    payload: dict[str, Any] = Body(default_factory=dict),
):
    note = (payload.get("note") or "").strip()
    return _decide_submission(
        submission_id=submission_id,
        user_id=user_id,
        new_status="approved",
        note=note,
        notify_title="Final submission approved",
        notify_message=(
            "Your supervisor approved your final submission."
            + (f" Note: {note}" if note else "")
        ),
    )


@router.post("/submissions/{submission_id}/request-revision")
def request_revision_final_submission(
    submission_id: int,
    user_id: Annotated[int | None, Query()] = None,
    payload: dict[str, Any] = Body(default_factory=dict),
):
    note = (payload.get("note") or payload.get("reason") or "").strip()
    if not note:
        raise HTTPException(status_code=400, detail="A revision note is required.")
    return _decide_submission(
        submission_id=submission_id,
        user_id=user_id,
        new_status="revision",
        note=note,
        notify_title="Revision requested",
        notify_message=f"Your supervisor requested revisions on your final submission. Note: {note}",
    )


@router.post("/submissions/{submission_id}/reject")
def reject_final_submission(
    submission_id: int,
    user_id: Annotated[int | None, Query()] = None,
    payload: dict[str, Any] = Body(default_factory=dict),
):
    note = (payload.get("note") or payload.get("reason") or "").strip()
    if not note:
        raise HTTPException(status_code=400, detail="A rejection reason is required.")
    return _decide_submission(
        submission_id=submission_id,
        user_id=user_id,
        new_status="rejected",
        note=note,
        notify_title="Final submission rejected",
        notify_message=f"Your supervisor rejected your final submission. Reason: {note}",
    )


def _plagiarism_risk_level(score: float) -> str:
    if score >= 60:
        return "high"
    if score >= 30:
        return "some"
    return "safe"


def _matches_from_plagiarism_issues(issues: list[Any]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        if str(issue.get("function") or "").lower() != "plagiarism":
            continue
        similarity = issue.get("similarity")
        try:
            sim = float(similarity) if similarity is not None else 0.0
        except (TypeError, ValueError):
            sim = 0.0
        if 0 < sim <= 1:
            sim_pct = round(sim * 100, 1)
        else:
            sim_pct = round(sim, 1)
        risk = issue.get("_risk_score")
        if risk is not None:
            try:
                sim_pct = float(risk)
            except (TypeError, ValueError):
                pass
        source = (
            issue.get("surrounding_text")
            or issue.get("matched_corpus_source")
            or issue.get("source")
            or issue.get("matched_source")
        )
        if not source:
            match_type = str(issue.get("type") or "").strip()
            if match_type:
                source = f"Detected match ({match_type})"
            else:
                source = "Unknown source"
        matches.append(
            {
                "source": str(source),
                "similarity": sim_pct,
                "sentence": str(issue.get("original") or issue.get("text_preview") or ""),
                "match_type": str(issue.get("type") or ""),
                "severity": str(issue.get("severity") or "minor"),
                "reason": str(issue.get("reason") or ""),
            }
        )
    matches.sort(key=lambda m: float(m.get("similarity") or 0), reverse=True)
    return matches


async def _run_live_plagiarism_on_texts(texts: list[str], document_id: str) -> dict[str, Any]:
    """Call Formatify plagiarism detector on paragraph texts; never raises."""
    cleaned = [t.strip() for t in texts if t and str(t).strip()]
    if not cleaned:
        return {"score": 0.0, "matches": [], "source": "none"}
    try:
        from plagiarism.detector import detect_plagiarism
        from plagiarism.pipeline import corpus_plagiarism_enabled, get_or_build_corpus_index, report_to_issues

        if not corpus_plagiarism_enabled():
            return {"score": 0.0, "matches": [], "source": "disabled"}

        corpus = get_or_build_corpus_index()
        chunks = [{"text": text, "chunk_id": f"p{i}"} for i, text in enumerate(cleaned)]
        meta = {
            f"p{i}": {"paragraph_id": f"p{i}", "page": 1, "heading_context": ""}
            for i in range(len(cleaned))
        }
        report = await detect_plagiarism(
            chunks,
            document_id=document_id,
            corpus=corpus,
            enable_web_verify=False,
        )
        overall = float(report.get("overall_plagiarism_score") or 0.0)
        score = round(overall * 100, 1) if overall <= 1 else round(overall, 1)
        issues = report_to_issues(report, meta)
        return {
            "score": score,
            "matches": _matches_from_plagiarism_issues(issues),
            "source": "plagiarism_module",
            "raw_report": report,
        }
    except Exception as exc:  # noqa: BLE001
        logger.info("Live plagiarism check unavailable for %s: %s", document_id, exc)
        return {"score": 0.0, "matches": [], "source": "unavailable", "error": str(exc)}


async def _plagiarism_for_group(cursor, group_id: int, supervisor_id: int) -> dict[str, Any]:
    """Prefer stored Formatify analysis snapshot; otherwise call plagiarism module."""
    cursor.execute(
        """
        SELECT analysis_report
        FROM final_submissions
        WHERE group_id = ? AND supervisor_id = ?
        ORDER BY datetime(submitted_at) DESC, id DESC
        LIMIT 1
        """,
        (group_id, supervisor_id),
    )
    sub = cursor.fetchone()
    if sub and sub["analysis_report"]:
        report = _parse_analysis_report(sub["analysis_report"])
        summary = _analysis_summary(report)
        issues = report.get("issues") if isinstance(report.get("issues"), list) else []
        matches = _matches_from_plagiarism_issues(issues)
        score = float(summary.get("plagiarism_score") or 0)
        return {
            "plagiarism_score": score,
            "risk_level": _plagiarism_risk_level(score),
            "matches": matches,
            "match_count": len(matches),
            "data_source": "analysis_report",
        }

    cursor.execute(
        """
        SELECT dp.text
        FROM document_paragraphs dp
        JOIN group_documents gd ON gd.id = dp.document_id
        WHERE gd.group_id = ? AND gd.supervisor_id = ?
        ORDER BY gd.id DESC, dp.sort_order ASC
        LIMIT 40
        """,
        (group_id, supervisor_id),
    )
    texts = [row["text"] for row in cursor.fetchall() if row["text"]]
    live = await _run_live_plagiarism_on_texts(texts, document_id=f"group-{group_id}")
    score = float(live.get("score") or 0)
    return {
        "plagiarism_score": score,
        "risk_level": _plagiarism_risk_level(score),
        "matches": live.get("matches") or [],
        "match_count": len(live.get("matches") or []),
        "data_source": live.get("source") or "plagiarism_module",
    }


@router.get("/plagiarism-monitor")
async def list_plagiarism_monitor(user_id: Annotated[int | None, Query()] = None):
    """All accepted groups with plagiarism score + risk color band."""
    supervisor = _require_supervisor(user_id)
    supervisor_id = supervisor["id"]

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, title, project_title, progress, student_contact_email
        FROM fyp_groups
        WHERE supervisor_id = ? AND status = 'accepted'
        ORDER BY title ASC
        """,
        (supervisor_id,),
    )
    rows = [dict(r) for r in cursor.fetchall()]
    groups = []
    for row in rows:
        plag = await _plagiarism_for_group(cursor, row["id"], supervisor_id)
        groups.append(
            {
                "group_id": row["id"],
                "title": row["title"],
                "project_title": row["project_title"] or "",
                "progress": float(row["progress"] or 0),
                "plagiarism_score": plag["plagiarism_score"],
                "risk_level": plag["risk_level"],
                "match_count": plag["match_count"],
                "data_source": plag["data_source"],
            }
        )
    order = {"high": 0, "some": 1, "safe": 2}
    groups.sort(key=lambda g: (order.get(g["risk_level"], 9), -float(g["plagiarism_score"])))
    conn.close()
    return {
        "groups": groups,
        "count": len(groups),
        "legend": {
            "safe": "Green — safe (under 30%)",
            "some": "Yellow — some risk (30–59%)",
            "high": "Red — high risk (60%+)",
        },
    }


@router.get("/plagiarism-monitor/{group_id}")
async def get_plagiarism_monitor_detail(
    group_id: int,
    user_id: Annotated[int | None, Query()] = None,
):
    """Group plagiarism detail: score, risk, matched sources."""
    supervisor = _require_supervisor(user_id)
    supervisor_id = supervisor["id"]

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, title, project_title, progress, student_contact_email, member_names,
               plagiarism_flagged, plagiarism_flag_reason, plagiarism_flagged_at
        FROM fyp_groups
        WHERE id = ? AND supervisor_id = ? AND status = 'accepted'
        """,
        (group_id, supervisor_id),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Group not found.")

    plag = await _plagiarism_for_group(cursor, group_id, supervisor_id)
    payload = {
        "group_id": row["id"],
        "title": row["title"],
        "project_title": row["project_title"] or "",
        "progress": float(row["progress"] or 0),
        "member_names": _parse_member_names(row["member_names"]),
        "student_contact_email": row["student_contact_email"] or "",
        "plagiarism_score": plag["plagiarism_score"],
        "risk_level": plag["risk_level"],
        "match_count": plag["match_count"],
        "matches": plag["matches"],
        "data_source": plag["data_source"],
        "flagged": bool(row["plagiarism_flagged"]) if "plagiarism_flagged" in row.keys() else False,
        "flag_reason": (row["plagiarism_flag_reason"] or "") if "plagiarism_flag_reason" in row.keys() else "",
        "flagged_at": (row["plagiarism_flagged_at"] or "") if "plagiarism_flagged_at" in row.keys() else "",
    }
    conn.close()
    return payload


@router.post("/plagiarism-monitor/{group_id}/flag")
async def flag_group_plagiarism(
    group_id: int,
    user_id: Annotated[int | None, Query()] = None,
    payload: dict[str, Any] = Body(default_factory=dict),
):
    """Persist plagiarism flag on fyp_groups and notify the student contact."""
    supervisor = _require_supervisor(user_id)
    supervisor_id = supervisor["id"]
    note = (payload.get("note") or payload.get("message") or "").strip()

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, title, student_contact_email
            FROM fyp_groups
            WHERE id = ? AND supervisor_id = ? AND status = 'accepted'
            """,
            (group_id, supervisor_id),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Group not found.")

        plag = await _plagiarism_for_group(cursor, group_id, supervisor_id)
        student_email = (row["student_contact_email"] or "").strip() or _get_group_student_email(
            cursor, group_id, supervisor_id
        )
        supervisor_name = supervisor.get("name") or "Your supervisor"
        score = plag["plagiarism_score"]
        message = (
            f"{supervisor_name} flagged your group '{row['title']}' for plagiarism risk "
            f"({score}%). "
        )
        if note:
            message += f"Note: {note}"
        else:
            message += "Please review matched sources and revise before final submission."

        flagged_at = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
        cursor.execute(
            """
            UPDATE fyp_groups
            SET plagiarism_flagged = 1,
                plagiarism_flag_reason = ?,
                plagiarism_flagged_at = ?
            WHERE id = ?
            """,
            (note or message, flagged_at, group_id),
        )

        _create_notification(
            cursor,
            recipient_email=student_email,
            title="Plagiarism warning",
            message=message,
            notification_type="plagiarism_flag",
            related_type="fyp_group",
            related_id=group_id,
            org_id=_supervisor_org_id(supervisor),
        )
        conn.commit()
        return {
            "success": True,
            "message": "Warning notification sent to the student.",
            "notified_email": student_email or "",
            "plagiarism_score": score,
            "risk_level": plag["risk_level"],
            "flagged": True,
            "flag_reason": note or message,
            "flagged_at": flagged_at,
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Failed to flag plagiarism for group %s", group_id)
        raise HTTPException(status_code=500, detail="Could not send plagiarism flag.")
    finally:
        conn.close()


def _serialize_meeting_note(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "group_id": row["group_id"],
        "supervisor_id": row["supervisor_id"],
        "meeting_date": _format_deadline(row["meeting_date"]),
        "topic": row["topic"] or "",
        "action_items": row["action_items"] or "",
        "created_at": row["created_at"] or "",
        "group_title": row["group_title"] if "group_title" in row.keys() else "",
        "project_title": row["project_title"] if "project_title" in row.keys() else "",
    }


def _require_accepted_group(
    cursor, group_id: int, supervisor_id: int, org_id: int | None = None
):
    cursor.execute(
        """
        SELECT id, title, project_title, student_contact_email
        FROM fyp_groups
        WHERE id = ? AND supervisor_id = ? AND status = 'accepted'
          AND (? IS NULL OR COALESCE(org_id, 1) = ?)
        """,
        (group_id, supervisor_id, org_id, org_id),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Group not found.")
    return row


@router.get("/groups/{group_id}/meeting-notes")
def list_meeting_notes(
    group_id: int,
    user_id: Annotated[int | None, Query()] = None,
):
    """Per-group meeting log — latest notes first."""
    supervisor = _require_supervisor(user_id)
    supervisor_id = supervisor["id"]

    conn = get_db()
    cursor = conn.cursor()
    try:
        group = _require_accepted_group(
            cursor, group_id, supervisor_id, org_id=_supervisor_org_id(supervisor)
        )
        cursor.execute(
            """
            SELECT mn.*, g.title AS group_title, g.project_title AS project_title
            FROM meeting_notes mn
            JOIN fyp_groups g ON g.id = mn.group_id
            WHERE mn.group_id = ? AND mn.supervisor_id = ?
            ORDER BY date(mn.meeting_date) DESC, datetime(mn.created_at) DESC, mn.id DESC
            """,
            (group_id, supervisor_id),
        )
        notes = [_serialize_meeting_note(row) for row in cursor.fetchall()]
        return {
            "group_id": group["id"],
            "group_title": group["title"],
            "project_title": group["project_title"] or "",
            "notes": notes,
            "count": len(notes),
        }
    finally:
        conn.close()


@router.post("/groups/{group_id}/meeting-notes")
def create_meeting_note(
    group_id: int,
    user_id: Annotated[int | None, Query()] = None,
    payload: dict[str, Any] = Body(default_factory=dict),
):
    """Add a meeting note (date, topic, action items) linked to the group."""
    supervisor = _require_supervisor(user_id)
    supervisor_id = supervisor["id"]

    topic = (payload.get("topic") or "").strip()
    action_items = (payload.get("action_items") or payload.get("actionItems") or "").strip()
    meeting_date_raw = payload.get("meeting_date") or payload.get("date") or date.today().isoformat()
    meeting_day = _parse_date(meeting_date_raw) or date.today()

    if not topic:
        raise HTTPException(status_code=400, detail="Topic is required.")

    conn = get_db()
    cursor = conn.cursor()
    try:
        group = _require_accepted_group(
            cursor, group_id, supervisor_id, org_id=_supervisor_org_id(supervisor)
        )
        cursor.execute(
            """
            INSERT INTO meeting_notes
                (group_id, supervisor_id, meeting_date, topic, action_items)
            VALUES (?, ?, ?, ?, ?)
            """,
            (group_id, supervisor_id, meeting_day.isoformat(), topic, action_items),
        )
        note_id = cursor.lastrowid

        student_email = (group["student_contact_email"] or "").strip() or _get_group_student_email(
            cursor, group_id, supervisor_id
        )
        _create_notification(
            cursor,
            recipient_email=student_email,
            title="New meeting note",
            message=(
                f"Your supervisor added a meeting note for '{group['title']}' "
                f"({meeting_day.isoformat()}): {topic}"
            ),
            notification_type="meeting_note",
            related_type="meeting_note",
            related_id=note_id,
            org_id=_supervisor_org_id(supervisor),
        )
        conn.commit()

        cursor.execute(
            """
            SELECT mn.*, g.title AS group_title, g.project_title AS project_title
            FROM meeting_notes mn
            JOIN fyp_groups g ON g.id = mn.group_id
            WHERE mn.id = ?
            """,
            (note_id,),
        )
        row = cursor.fetchone()
        return {
            "success": True,
            "message": "Meeting note saved.",
            "note": _serialize_meeting_note(row),
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Failed to create meeting note for group %s", group_id)
        raise HTTPException(status_code=500, detail="Could not save meeting note.")
    finally:
        conn.close()


@router.get("/notifications")
def list_supervisor_notifications(
    user_id: Annotated[int | None, Query()] = None,
    unread_only: Annotated[bool, Query()] = False,
):
    """
    Inbox for supervisor mobile/desktop: submissions, student replies, etc.
    Wrapper over unified notification table for backward compatibility.
    """
    supervisor = _require_supervisor(user_id)
    email = (supervisor.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Supervisor account has no email.")

    sup_user_id = supervisor.get("user_id") or (int(user_id) if user_id is not None else None)
    sup_org_id = _supervisor_org_id(supervisor)

    conn = get_db()
    cursor = conn.cursor()
    try:
        sql = """
            SELECT id, user_id, recipient_email, title, message, type, is_read,
                   related_type, related_id, created_at, org_id
            FROM notifications
            WHERE ((user_id = ?) OR (user_id IS NULL AND LOWER(TRIM(recipient_email)) = LOWER(?)))
              AND COALESCE(org_id, 1) = ?
        """
        params: list[Any] = [sup_user_id, email, sup_org_id]
        if unread_only:
            sql += " AND is_read = 0"
        sql += " ORDER BY datetime(created_at) DESC, id DESC LIMIT 100"
        cursor.execute(sql, params)
        rows = [_serialize_supervisor_notification(r, cursor) for r in cursor.fetchall()]
        unread = sum(1 for r in rows if not r["is_read"])
        return {
            "notifications": rows,
            "count": len(rows),
            "unread_count": unread,
            "recipient_email": email,
        }
    finally:
        conn.close()


@router.post("/notifications/{notification_id}/read")
def mark_supervisor_notification_read(
    notification_id: int,
    user_id: Annotated[int | None, Query()] = None,
):
    supervisor = _require_supervisor(user_id)
    email = (supervisor.get("email") or "").strip().lower()
    sup_user_id = supervisor.get("user_id") or (int(user_id) if user_id is not None else None)
    sup_org_id = _supervisor_org_id(supervisor)

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id FROM notifications
            WHERE id = ?
              AND ((user_id = ?) OR (user_id IS NULL AND LOWER(TRIM(recipient_email)) = LOWER(?)))
              AND COALESCE(org_id, 1) = ?
            """,
            (notification_id, sup_user_id, email, sup_org_id),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Notification not found.")
        cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
        conn.commit()
        return {"success": True, "id": notification_id, "is_read": True}
    except HTTPException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _serialize_supervisor_notification(row, cursor=None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": row["id"],
        "user_id": row["user_id"] if "user_id" in row.keys() else None,
        "recipient_email": row["recipient_email"] or "",
        "title": row["title"] or "",
        "message": row["message"] or "",
        "type": row["type"] or "info",
        "is_read": bool(row["is_read"]),
        "related_type": row["related_type"] or "",
        "related_id": row["related_id"],
        "created_at": row["created_at"] or "",
        "org_id": row["org_id"] if "org_id" in row.keys() else 1,
    }
    related_type = (result["related_type"] or "").strip().lower()
    related_id = result["related_id"]
    if cursor is None or related_id is None:
        return result

    if related_type == "document_comment":
        cursor.execute(
            """
            SELECT dc.id AS comment_id, dc.document_id, gd.group_id, gd.title AS document_title
            FROM document_comments dc
            JOIN group_documents gd ON gd.id = dc.document_id
            WHERE dc.id = ?
            """,
            (related_id,),
        )
        link = cursor.fetchone()
        if link:
            result["comment_id"] = link["comment_id"]
            result["document_id"] = link["document_id"]
            result["group_id"] = link["group_id"]
            result["document_title"] = link["document_title"] or ""
    elif related_type == "final_submission":
        cursor.execute(
            """
            SELECT id, group_id, title, group_document_id
            FROM final_submissions WHERE id = ?
            """,
            (related_id,),
        )
        link = cursor.fetchone()
        if link:
            result["submission_id"] = link["id"]
            result["group_id"] = link["group_id"]
            result["document_id"] = link["group_document_id"]
            result["submission_title"] = link["title"] or ""
    return result