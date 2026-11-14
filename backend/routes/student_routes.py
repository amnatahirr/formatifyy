"""Student-facing APIs (meeting notes, choose supervisor, etc.)."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Query, Request

from database import get_db
from middleware.org_middleware import resolve_organization_from_request

router = APIRouter(prefix="/api/student", tags=["Student"])
logger = logging.getLogger(__name__)


def _row_to_dict(row) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def _table_has_column(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def _request_org_id(request: Request | None) -> int | None:
    if request is None:
        return None
    org_id = getattr(request.state, "org_id", None)
    if org_id is not None:
        return int(org_id)
    org = getattr(request.state, "org", None)
    if isinstance(org, dict) and org.get("id"):
        return int(org["id"])
    try:
        return int(resolve_organization_from_request(request)["id"])
    except Exception:
        return None


def _user_org_id(cursor, user_id: int) -> int:
    cursor.execute("SELECT org_id FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    return int(row["org_id"] or 1) if row else 1


def _resolve_student_org_id(
    cursor,
    user_id: int,
    request: Request | None = None,
    *,
    prefer_user: bool = True,
) -> int:
    """
    Tenant for student routes.
    Prefer users.org_id; optionally cross-check request.state.org_id when explicitly sent.
    """
    user_org = _user_org_id(cursor, user_id)
    if request is not None:
        has_explicit_jwt = bool(getattr(request.state, "jwt_claims", None))
        has_explicit_header = bool(
            request.headers.get("X-Org-Code")
            or request.headers.get("x-org-code")
            or request.headers.get("Authorization")
            or request.headers.get("authorization")
            or request.query_params.get("org_code")
        )
        if has_explicit_jwt or has_explicit_header:
            req_org = _request_org_id(request)
            if req_org is not None and int(req_org) != user_org:
                raise HTTPException(
                    status_code=403,
                    detail="Your account does not belong to this organization.",
                )
    return user_org



def _require_student(user_id: int | None) -> dict[str, Any]:
    if user_id is None:
        raise HTTPException(status_code=401, detail="Student login required.")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, email, role, username, org_id FROM users WHERE id = ?",
        (user_id,),
    )
    user = cursor.fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access required.")
    data = _row_to_dict(user)
    data["org_id"] = int(data.get("org_id") or 1)
    return data


def _parse_member_names(raw: Any) -> list[str]:
    """Same format as supervisor_routes: JSON list text, or comma-separated fallback."""
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
    import re

    text = (label or "").strip()
    if not text:
        return None
    match = re.search(r"<([^>]+@[^>]+)>", text)
    if match:
        return match.group(1).strip().lower()
    if "@" in text and " " not in text:
        return text.lower()
    match = re.search(r"([^\s<>]+@[^\s<>]+)", text)
    if match:
        return match.group(1).strip().lower()
    return None


def _extract_docx_paragraphs(file_path: str, limit: int = 250) -> list[str]:
    """Pull body paragraph texts for review (front-matter skipped). Legacy helper."""
    from docx_tools.review_blocks import extract_review_blocks

    try:
        return [b["text"] for b in extract_review_blocks(file_path, limit=limit)]
    except Exception as exc:
        logger.warning("Failed to extract paragraphs from %s: %s", file_path, exc)
        return []


def _create_group_document_for_submission(
    cursor,
    *,
    group_id: int,
    supervisor_id: int,
    title: str,
    filename: str | None,
    source_document_id: int | None,
    contact_email: str,
) -> int:
    """
    Create a group_documents row + classified body blocks so supervisor can preview/comment
    and students can resolve issues in DocumentFeedbackScreen.
    """
    import os

    from docx_tools.review_blocks import BLOCK_LINE, BLOCK_PARAGRAPH, extract_review_blocks

    file_path = None
    if source_document_id is not None:
        cursor.execute(
            "SELECT file_path, filename FROM documents WHERE id = ?",
            (source_document_id,),
        )
        doc_row = cursor.fetchone()
        if doc_row:
            file_path = doc_row["file_path"]
            if not filename:
                filename = doc_row["filename"]

    # Prefer working copy if present
    if source_document_id is not None:
        working = os.path.join("uploads", "working", f"doc_{source_document_id}_working.docx")
        if os.path.exists(working):
            file_path = working

    cursor.execute(
        """
        INSERT INTO group_documents
            (group_id, supervisor_id, title, filename, file_url, status,
             source_document_id, version_number)
        VALUES (?, ?, ?, ?, ?, 'pending', ?, 1)
        """,
        (
            group_id,
            supervisor_id,
            title,
            filename,
            file_path,
            source_document_id,
        ),
    )
    group_document_id = cursor.lastrowid

    blocks = extract_review_blocks(file_path or "")
    if not blocks:
        blocks = [
            {
                "text": f"{title}: Document submitted for supervisor review.",
                "block_type": BLOCK_PARAGRAPH,
            },
            {
                "text": "Open the downloaded file for full formatting; comment on sections below.",
                "block_type": BLOCK_LINE,
            },
        ]
    for order, block in enumerate(blocks, start=1):
        cursor.execute(
            """
            INSERT INTO document_paragraphs (document_id, sort_order, text, block_type)
            VALUES (?, ?, ?, ?)
            """,
            (
                group_document_id,
                order,
                block["text"],
                block.get("block_type") or BLOCK_PARAGRAPH,
            ),
        )
    return int(group_document_id)


def _student_in_accepted_group(
    cursor,
    group_id: int,
    student_email: str,
    org_id: int | None = None,
):
    """Return group row if [student_email] is leader or listed member of an accepted group."""
    email = (student_email or "").strip().lower()
    if org_id is not None and _table_has_column(cursor, "fyp_groups", "org_id"):
        cursor.execute(
            """
            SELECT id, title, project_title, supervisor_id, student_contact_email,
                   member_names, status, current_semester, org_id
            FROM fyp_groups
            WHERE id = ? AND status = 'accepted' AND COALESCE(org_id, 1) = ?
            """,
            (group_id, org_id),
        )
    else:
        cursor.execute(
            """
            SELECT id, title, project_title, supervisor_id, student_contact_email,
                   member_names, status, current_semester
            FROM fyp_groups
            WHERE id = ? AND status = 'accepted'
            """,
            (group_id,),
        )
    group = cursor.fetchone()
    if not group or not email:
        return None

    # Defensive: if org_id known and group has org_id, require match
    if org_id is not None:
        keys = set(group.keys()) if hasattr(group, "keys") else set()
        if "org_id" in keys and int(group["org_id"] or 1) != int(org_id):
            return None

    contact = (group["student_contact_email"] or "").strip().lower()
    if contact and contact == email:
        return group

    for member in _parse_member_names(group["member_names"]):
        member_email = _email_from_member_label(member)
        if member_email and member_email == email:
            return group

    # Fallback: assignment request leader / members linked to this group
    cursor.execute(
        """
        SELECT ar.student_leader_email, ar.member_names
        FROM assignment_requests ar
        JOIN supervisors s ON s.id = ar.supervisor_id
        WHERE ar.fyp_group_id = ? AND LOWER(TRIM(ar.status)) = 'accepted'
          AND (? IS NULL OR COALESCE(s.org_id, 1) = ?)
        ORDER BY ar.id DESC
        LIMIT 1
        """,
        (group_id, org_id, org_id),
    )
    req = cursor.fetchone()
    if req:
        leader = (req["student_leader_email"] or "").strip().lower()
        if leader and leader == email:
            return group
        for member in _parse_member_names(req["member_names"]):
            member_email = _email_from_member_label(member)
            if member_email and member_email == email:
                return group

    return None


def _serialize_assignment_request(row) -> dict[str, Any]:
    """Match supervisor GET /assignment-requests response shape."""
    data = _row_to_dict(row)
    members = _parse_member_names(data.get("member_names"))
    if not members and data.get("student_leader_name"):
        members = [str(data["student_leader_name"])]
    return {
        "id": data.get("id"),
        "group_name": data.get("group_name") or "",
        "project_title": data.get("project_title") or "",
        "topic": data.get("project_title") or "",
        "student_leader_name": data.get("student_leader_name") or "",
        "student_leader_email": data.get("student_leader_email") or "",
        "member_names": members,
        "cosupervisor_name": (data.get("cosupervisor_name") or "").strip(),
        "department_id": data.get("department_id"),
        "department_name": data.get("department_name") or "",
        "department_code": data.get("department_code") or "",
        "status": data.get("status") or "pending",
        "rejection_reason": data.get("rejection_reason") or "",
        "fyp_group_id": data.get("fyp_group_id"),
        "created_at": data.get("created_at"),
        "resolved_at": data.get("resolved_at"),
        "supervisor_id": data.get("supervisor_id"),
        "supervisor_name": data.get("supervisor_name") or "",
    }


def _serialize_note(row) -> dict[str, Any]:
    keys = set(row.keys()) if hasattr(row, "keys") else set()
    return {
        "id": row["id"],
        "group_id": row["group_id"],
        "supervisor_id": row["supervisor_id"] if "supervisor_id" in keys else None,
        "meeting_date": (row["meeting_date"] or "")[:10] if row["meeting_date"] else "",
        "topic": row["topic"] or "",
        "action_items": row["action_items"] or "",
        "created_at": row["created_at"] or "",
        "group_title": (row["group_title"] or "") if "group_title" in keys else "",
        "project_title": (row["project_title"] or "") if "project_title" in keys else "",
        "supervisor_name": (row["supervisor_name"] or "") if "supervisor_name" in keys else "",
    }


@router.get("/meeting-notes")
def list_student_meeting_notes(user_id: Annotated[int | None, Query()] = None):
    """
    Read-only meeting notes for groups where this student is the contact email.
    Latest notes first.
    """
    student = _require_student(user_id)
    email = (student.get("email") or "").strip().lower()
    if not email:
        return {"notes": [], "groups": [], "count": 0}

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT
                g.id AS group_id,
                g.title AS group_title,
                g.project_title AS project_title,
                COALESCE(s.name, '') AS supervisor_name
            FROM fyp_groups g
            LEFT JOIN supervisors s ON s.id = g.supervisor_id
            WHERE g.status = 'accepted'
              AND LOWER(TRIM(g.student_contact_email)) = LOWER(?)
            ORDER BY g.title ASC
            """,
            (email,),
        )
        groups = [
            {
                "group_id": row["group_id"],
                "group_title": row["group_title"],
                "project_title": row["project_title"] or "",
                "supervisor_name": row["supervisor_name"] or "",
            }
            for row in cursor.fetchall()
        ]
        if not groups:
            return {"notes": [], "groups": [], "count": 0}

        group_ids = [g["group_id"] for g in groups]
        placeholders = ",".join("?" for _ in group_ids)
        cursor.execute(
            f"""
            SELECT
                mn.id,
                mn.group_id,
                mn.supervisor_id,
                mn.meeting_date,
                mn.topic,
                mn.action_items,
                mn.created_at,
                g.title AS group_title,
                g.project_title AS project_title,
                COALESCE(s.name, '') AS supervisor_name
            FROM meeting_notes mn
            JOIN fyp_groups g ON g.id = mn.group_id
            LEFT JOIN supervisors s ON s.id = mn.supervisor_id
            WHERE mn.group_id IN ({placeholders})
            ORDER BY date(mn.meeting_date) DESC, datetime(mn.created_at) DESC, mn.id DESC
            """,
            group_ids,
        )
        notes = [_serialize_note(row) for row in cursor.fetchall()]
        return {"notes": notes, "groups": groups, "count": len(notes)}
    finally:
        conn.close()


@router.get("/groups/{group_id}/meeting-notes")
def list_student_group_meeting_notes(
    group_id: int,
    user_id: Annotated[int | None, Query()] = None,
):
    """Read-only meeting notes for one group the student belongs to."""
    student = _require_student(user_id)
    email = (student.get("email") or "").strip().lower()

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT
                g.id,
                g.title,
                g.project_title,
                COALESCE(s.name, '') AS supervisor_name
            FROM fyp_groups g
            LEFT JOIN supervisors s ON s.id = g.supervisor_id
            WHERE g.id = ?
              AND g.status = 'accepted'
              AND LOWER(TRIM(g.student_contact_email)) = LOWER(?)
            """,
            (group_id, email),
        )
        group = cursor.fetchone()
        if not group:
            raise HTTPException(status_code=404, detail="Group not found for this student.")

        cursor.execute(
            """
            SELECT
                mn.id,
                mn.group_id,
                mn.supervisor_id,
                mn.meeting_date,
                mn.topic,
                mn.action_items,
                mn.created_at,
                g.title AS group_title,
                g.project_title AS project_title,
                COALESCE(s.name, '') AS supervisor_name
            FROM meeting_notes mn
            JOIN fyp_groups g ON g.id = mn.group_id
            LEFT JOIN supervisors s ON s.id = mn.supervisor_id
            WHERE mn.group_id = ?
            ORDER BY date(mn.meeting_date) DESC, datetime(mn.created_at) DESC, mn.id DESC
            """,
            (group_id,),
        )
        notes = [_serialize_note(row) for row in cursor.fetchall()]
        return {
            "group_id": group["id"],
            "group_title": group["title"],
            "project_title": group["project_title"] or "",
            "supervisor_name": group["supervisor_name"] or "",
            "notes": notes,
            "count": len(notes),
        }
    finally:
        conn.close()


def _list_group_milestones(cursor, group_id: int, progress: float = 0) -> list[dict[str, Any]]:
    """
    Same shape as supervisor _ensure_group_milestones:
    {id, name, sort_order, is_completed, completed_at} ordered by sort_order.
    Seeds the three canonical rows if missing so student/supervisor views match.
    """
    from datetime import datetime

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
    existing_names = {str(row["name"]).strip().lower() for row in rows}
    for name, order, _done in defaults:
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


@router.get("/groups/{group_id}/milestones")
def list_student_group_milestones(
    group_id: int,
    user_id: Annotated[int | None, Query()] = None,
):
    """
    Read-only milestones for a group the student belongs to (email match).
    Field names match supervisor GET /groups/{group_id} → milestones[].
    """
    student = _require_student(user_id)
    email = (student.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Your account has no email address.")

    conn = get_db()
    cursor = conn.cursor()
    try:
        org_id = int(student.get("org_id") or 1)
        group = _student_in_accepted_group(cursor, group_id, email, org_id=org_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found for this student.")
        cursor.execute(
            """
            SELECT id, title, project_title, progress, status
            FROM fyp_groups
            WHERE id = ? AND status = 'accepted' AND COALESCE(org_id, 1) = ?
            """,
            (group_id, org_id),
        )
        group = cursor.fetchone()
        if not group:
            raise HTTPException(status_code=404, detail="Group not found for this student.")

        milestones = _list_group_milestones(
            cursor, group_id, progress=float(group["progress"] or 0)
        )
        conn.commit()
        return {
            "group_id": group["id"],
            "group_title": group["title"] or "",
            "project_title": group["project_title"] or "",
            "milestones": milestones,
            "count": len(milestones),
        }
    finally:
        conn.close()


@router.get("/supervisors")
def list_student_supervisors(
    request: Request,
    user_id: Annotated[int | None, Query()] = None,
):
    """
    List active supervisors for the Choose Supervisor form.
    Admin GET /admin/supervisors requires admin auth — this is the student-facing equivalent.
    Also returns departments for the form dropdown.
    Scoped to the student's org_id (fallback: request org).
    """
    student = _require_student(user_id)
    conn = get_db()
    cursor = conn.cursor()
    try:
        org_id = _resolve_student_org_id(
            cursor, int(student["id"]), request, prefer_user=True
        )
        cursor.execute(
            """
            SELECT
                s.id,
                s.name,
                s.email,
                s.department_id,
                s.max_groups,
                s.current_groups,
                s.is_active,
                d.name AS department_name,
                d.code AS department_code
            FROM supervisors s
            LEFT JOIN departments d ON d.id = s.department_id
            WHERE COALESCE(s.is_active, 1) = 1
              AND COALESCE(s.org_id, 1) = ?
            ORDER BY s.name ASC
            """,
            (org_id,),
        )
        supervisors = []
        for row in cursor.fetchall():
            item = _row_to_dict(row)
            max_groups = int(item.get("max_groups") or 6)
            current = int(item.get("current_groups") or 0)
            item["slots_available"] = max(0, max_groups - current)
            item["is_full"] = current >= max_groups
            supervisors.append(item)

        if _table_has_column(cursor, "departments", "org_id"):
            cursor.execute(
                """
                SELECT id, name, code
                FROM departments
                WHERE COALESCE(org_id, 1) = ?
                ORDER BY name ASC
                """,
                (org_id,),
            )
        else:
            cursor.execute(
                """
                SELECT id, name, code
                FROM departments
                ORDER BY name ASC
                """
            )
        departments = [_row_to_dict(row) for row in cursor.fetchall()]
        return {
            "supervisors": supervisors,
            "departments": departments,
            "count": len(supervisors),
        }
    finally:
        conn.close()


def _find_accepted_group_for_email(cursor, email: str, org_id: int | None = None):
    """Find an accepted fyp_groups row where email is contact or member."""
    email = (email or "").strip().lower()
    if not email:
        return None
    if org_id is not None and _table_has_column(cursor, "fyp_groups", "org_id"):
        cursor.execute(
            """
            SELECT id, title, project_title, supervisor_id, student_contact_email,
                   member_names, status, deadline_date, department_id, current_semester, org_id
            FROM fyp_groups
            WHERE status = 'accepted' AND COALESCE(org_id, 1) = ?
            ORDER BY id DESC
            """,
            (org_id,),
        )
    else:
        cursor.execute(
            """
            SELECT id, title, project_title, supervisor_id, student_contact_email,
                   member_names, status, deadline_date, department_id, current_semester
            FROM fyp_groups
            WHERE status = 'accepted'
            ORDER BY id DESC
            """
        )
    for group in cursor.fetchall():
        if _student_in_accepted_group(cursor, int(group["id"]), email, org_id=org_id):
            return group
    return None


@router.get("/assignment-requests/status")
def get_assignment_request_status(
    email: Annotated[str | None, Query()] = None,
    user_id: Annotated[int | None, Query()] = None,
):
    """
    Latest assignment_requests row for this student (by student_leader_email),
    with fallback to accepted group membership (contact or listed member email).
    """
    student = _require_student(user_id)
    account_email = (student.get("email") or "").strip().lower()
    lookup_email = (email or "").strip().lower() or account_email
    if not lookup_email:
        return {"found": False, "status": None}

    # Students may only query their own email (AuthProvider.userEmail)
    if account_email and lookup_email != account_email:
        raise HTTPException(
            status_code=403,
            detail="You can only look up assignment status for your own email.",
        )

    conn = get_db()
    cursor = conn.cursor()
    try:
        org_id = int(student.get("org_id") or 1)
        cursor.execute(
            """
            SELECT
                ar.id,
                ar.status,
                ar.rejection_reason,
                ar.fyp_group_id,
                ar.group_name,
                ar.project_title,
                ar.supervisor_id,
                ar.department_id,
                ar.created_at,
                ar.resolved_at,
                ar.student_leader_email,
                COALESCE(s.name, '') AS supervisor_name,
                COALESCE(s.email, '') AS supervisor_email,
                COALESCE(d.name, '') AS department_name,
                COALESCE(d.code, '') AS department_code,
                g.title AS group_title,
                g.project_title AS group_project_title,
                g.status AS group_status,
                g.deadline_date AS group_deadline_date
            FROM assignment_requests ar
            JOIN supervisors s ON s.id = ar.supervisor_id
            LEFT JOIN departments d ON d.id = COALESCE(ar.department_id, s.department_id)
            LEFT JOIN fyp_groups g ON g.id = ar.fyp_group_id
            WHERE LOWER(TRIM(ar.student_leader_email)) = LOWER(?)
              AND COALESCE(s.org_id, 1) = ?
            ORDER BY datetime(ar.created_at) DESC, ar.id DESC
            LIMIT 1
            """,
            (lookup_email, org_id),
        )
        row = cursor.fetchone()

        # Member students: resolve via accepted group membership when not the leader
        if not row:
            group = _find_accepted_group_for_email(cursor, lookup_email, org_id=org_id)
            if not group:
                return {"found": False, "status": None, "email": lookup_email}
            cursor.execute(
                """
                SELECT
                    ar.id,
                    ar.status,
                    ar.rejection_reason,
                    ar.fyp_group_id,
                    ar.group_name,
                    ar.project_title,
                    ar.supervisor_id,
                    ar.department_id,
                    ar.created_at,
                    ar.resolved_at,
                    ar.student_leader_email,
                    COALESCE(s.name, '') AS supervisor_name,
                    COALESCE(s.email, '') AS supervisor_email,
                    COALESCE(d.name, '') AS department_name,
                    COALESCE(d.code, '') AS department_code,
                    g.title AS group_title,
                    g.project_title AS group_project_title,
                    g.status AS group_status,
                    g.deadline_date AS group_deadline_date
                FROM fyp_groups g
                LEFT JOIN assignment_requests ar ON ar.fyp_group_id = g.id
                LEFT JOIN supervisors s ON s.id = g.supervisor_id
                LEFT JOIN departments d ON d.id = COALESCE(ar.department_id, g.department_id, s.department_id)
                WHERE g.id = ?
                ORDER BY ar.id DESC
                LIMIT 1
                """,
                (group["id"],),
            )
            row = cursor.fetchone()
            if not row:
                return {
                    "found": True,
                    "email": lookup_email,
                    "status": "accepted",
                    "fyp_group_id": group["id"],
                    "group_name": group["title"] or "",
                    "project_title": group["project_title"] or "",
                    "supervisor_id": group["supervisor_id"],
                    "group": {
                        "id": group["id"],
                        "title": group["title"] or "",
                        "project_title": group["project_title"] or "",
                        "status": "accepted",
                        "deadline_date": group["deadline_date"],
                    },
                }

        data = _row_to_dict(row)
        status = (data.get("status") or "").strip().lower() or "accepted"
        # If request row is missing status but group exists, treat as accepted
        if not status and data.get("fyp_group_id"):
            status = "accepted"
        result: dict[str, Any] = {
            "found": True,
            "email": lookup_email,
            "id": data.get("id"),
            "status": status,
            "rejection_reason": data.get("rejection_reason") or "",
            "fyp_group_id": data.get("fyp_group_id"),
            "group_name": data.get("group_name") or data.get("group_title") or "",
            "project_title": data.get("project_title") or data.get("group_project_title") or "",
            "supervisor_id": data.get("supervisor_id"),
            "department_id": data.get("department_id"),
            "created_at": data.get("created_at"),
            "resolved_at": data.get("resolved_at"),
        }
        if status == "accepted":
            result["supervisor"] = {
                "id": data.get("supervisor_id"),
                "name": data.get("supervisor_name") or "",
                "email": data.get("supervisor_email") or "",
                "department_name": data.get("department_name") or "",
                "department_code": data.get("department_code") or "",
            }
            result["group"] = {
                "id": data.get("fyp_group_id"),
                "title": data.get("group_title") or data.get("group_name") or "",
                "project_title": data.get("group_project_title")
                or data.get("project_title")
                or "",
                "status": data.get("group_status") or "accepted",
                "deadline_date": data.get("group_deadline_date"),
            }
        return result
    finally:
        conn.close()


@router.get("/assignment-requests")
def list_student_assignment_requests(user_id: Annotated[int | None, Query()] = None):
    """List this student's assignment requests (matched by student_leader_email)."""
    student = _require_student(user_id)
    email = (student.get("email") or "").strip().lower()
    if not email:
        return {"requests": [], "count": 0}

    conn = get_db()
    cursor = conn.cursor()
    try:
        org_id = int(student.get("org_id") or 1)
        cursor.execute(
            """
            SELECT
                ar.*,
                d.name AS department_name,
                d.code AS department_code,
                COALESCE(s.name, '') AS supervisor_name
            FROM assignment_requests ar
            JOIN supervisors s ON s.id = ar.supervisor_id
            LEFT JOIN departments d ON d.id = ar.department_id
            WHERE LOWER(TRIM(ar.student_leader_email)) = LOWER(?)
              AND COALESCE(s.org_id, 1) = ?
            ORDER BY ar.created_at DESC, ar.id DESC
            """,
            (email, org_id),
        )
        rows = [_serialize_assignment_request(row) for row in cursor.fetchall()]
        return {"requests": rows, "count": len(rows)}
    finally:
        conn.close()


@router.post("/assignment-requests")
def create_assignment_request(
    request: Request,
    payload: dict[str, Any] = Body(...),
    user_id: Annotated[int | None, Query()] = None,
):
    """
    Create a pending assignment request.
    fyp_group_id stays null until the supervisor accepts
    (see POST /api/supervisor/assignment-requests/{id}/accept).
    """
    student = _require_student(user_id)
    student_email = (student.get("email") or "").strip().lower()
    if not student_email:
        raise HTTPException(status_code=400, detail="Your account has no email address.")

    try:
        supervisor_id = int(payload.get("supervisor_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="supervisor_id is required.") from None

    group_name = str(payload.get("group_name") or "").strip()
    if not group_name:
        raise HTTPException(status_code=400, detail="group_name is required.")

    project_title = str(payload.get("project_title") or "").strip()
    student_leader_name = str(
        payload.get("student_leader_name") or student.get("username") or ""
    ).strip()
    # Identity is email-based — always store the logged-in student's email
    student_leader_email = student_email
    body_email = str(payload.get("student_leader_email") or "").strip().lower()
    if body_email and body_email != student_email:
        raise HTTPException(
            status_code=400,
            detail="student_leader_email must match your logged-in account email.",
        )

    department_id = payload.get("department_id")
    if department_id is not None and department_id != "":
        try:
            department_id = int(department_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid department_id.") from None
    else:
        department_id = None

    members = _parse_member_names(payload.get("member_names"))
    if student_leader_name and student_leader_name not in members:
        members = [student_leader_name, *[m for m in members if m != student_leader_name]]
    member_names_json = json.dumps(members)
    cosupervisor_name = str(payload.get("cosupervisor_name") or "").strip()

    conn = get_db()
    cursor = conn.cursor()
    try:
        org_id = _resolve_student_org_id(
            cursor, int(student["id"]), request, prefer_user=True
        )
        cursor.execute(
            """
            SELECT id, name, max_groups, current_groups, is_active, department_id, org_id
            FROM supervisors
            WHERE id = ? AND COALESCE(org_id, 1) = ?
            """,
            (supervisor_id, org_id),
        )
        supervisor = cursor.fetchone()
        if not supervisor:
            raise HTTPException(status_code=404, detail="Supervisor not found.")
        if int(supervisor["is_active"] or 0) != 1:
            raise HTTPException(status_code=400, detail="This supervisor is not accepting groups.")
        max_groups = int(supervisor["max_groups"] or 6)
        current = int(supervisor["current_groups"] or 0)
        if current >= max_groups:
            raise HTTPException(
                status_code=400,
                detail=f"This supervisor has reached their max group limit ({max_groups}).",
            )

        if department_id is None:
            department_id = supervisor["department_id"]

        # Avoid duplicate pending requests to the same supervisor from this student
        cursor.execute(
            """
            SELECT ar.id
            FROM assignment_requests ar
            JOIN supervisors s ON s.id = ar.supervisor_id
            WHERE ar.supervisor_id = ?
              AND LOWER(TRIM(ar.student_leader_email)) = LOWER(?)
              AND ar.status = 'pending'
              AND COALESCE(s.org_id, 1) = ?
            """,
            (supervisor_id, student_email, org_id),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=409,
                detail="You already have a pending request with this supervisor.",
            )

        has_ar_org = _table_has_column(cursor, "assignment_requests", "org_id")
        if has_ar_org:
            cursor.execute(
                """
                INSERT INTO assignment_requests
                    (supervisor_id, group_name, project_title, student_leader_name,
                     student_leader_email, member_names, cosupervisor_name,
                     department_id, status, fyp_group_id, org_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', NULL, ?)
                """,
                (
                    supervisor_id,
                    group_name,
                    project_title,
                    student_leader_name,
                    student_leader_email,
                    member_names_json,
                    cosupervisor_name or None,
                    department_id,
                    org_id,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO assignment_requests
                    (supervisor_id, group_name, project_title, student_leader_name,
                     student_leader_email, member_names, cosupervisor_name,
                     department_id, status, fyp_group_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', NULL)
                """,
                (
                    supervisor_id,
                    group_name,
                    project_title,
                    student_leader_name,
                    student_leader_email,
                    member_names_json,
                    cosupervisor_name or None,
                    department_id,
                ),
            )
        request_id = cursor.lastrowid
        conn.commit()

        # Notify the supervisor of the new assignment request
        try:
            cursor.execute(
                "SELECT email, name FROM supervisors WHERE id = ? AND COALESCE(org_id, 1) = ?",
                (supervisor_id, org_id),
            )
            sup_row = cursor.fetchone()
            if sup_row and sup_row["email"]:
                sup_email = sup_row["email"]
                cursor.execute(
                    "SELECT id, org_id FROM users WHERE LOWER(email) = LOWER(?) AND COALESCE(org_id, 1) = ?",
                    (sup_email, org_id),
                )
                user_row = cursor.fetchone()
                notify_user_id = user_row["id"] if user_row else None
                notify_org_id = int(user_row["org_id"] if user_row and user_row["org_id"] else org_id)

                student_name = student_leader_name or (student.get("username") or "A student").strip()
                if project_title:
                    message_text = f"{student_name} requested supervision for '{project_title}'."
                else:
                    message_text = f"{student_name} submitted a supervision request for group '{group_name}'."

                from services.notification_service import notify, NotificationType
                notify(
                    org_id=notify_org_id,
                    user_id=notify_user_id,
                    type=NotificationType.NEW_ASSIGNMENT_REQUEST,
                    title="New supervision request",
                    body=message_text,
                    entity_type="assignment_request",
                    entity_id=request_id,
                    payload={"screen": "assignment_requests", "request_id": request_id},
                )
                conn.commit()
        except Exception:
            logger.exception("Failed to send assignment request notification for request_id=%s", request_id)

        cursor.execute(
            """
            SELECT
                ar.*,
                d.name AS department_name,
                d.code AS department_code,
                COALESCE(s.name, '') AS supervisor_name
            FROM assignment_requests ar
            LEFT JOIN departments d ON d.id = ar.department_id
            LEFT JOIN supervisors s ON s.id = ar.supervisor_id
            WHERE ar.id = ?
            """,
            (request_id,),
        )
        row = cursor.fetchone()
        return {
            "success": True,
            "request": _serialize_assignment_request(row),
        }
    finally:
        conn.close()


def _serialize_student_final_submission(row) -> dict[str, Any]:
    """Match supervisor GET /submissions list fields (without full report by default)."""
    keys = set(row.keys()) if hasattr(row, "keys") else set()
    return {
        "id": row["id"],
        "group_id": row["group_id"],
        "group_title": row["group_title"] if "group_title" in keys else "",
        "title": row["title"],
        "filename": row["filename"] or "",
        "status": row["status"],
        "submitted_at": row["submitted_at"],
        "resolved_at": row["resolved_at"],
        "decision_note": row["decision_note"] or "",
        "student_contact_email": row["student_contact_email"] or "",
        "source_document_id": row["source_document_id"] if "source_document_id" in keys else None,
        "group_document_id": row["group_document_id"] if "group_document_id" in keys else None,
        "analysis_summary": _analysis_summary_from_report_row(row),
    }


@router.get("/semester-deadline")
def get_student_semester_deadline(
    request: Request,
    user_id: Annotated[int | None, Query()] = None,
):
    """
    Global admin deadline for this student's semester.
    Prefer fyp_groups.current_semester when an accepted group exists;
    otherwise fall back to users.current_semester (set at signup).
    Empty/null state (not an error) when semester unset or no deadline row yet.
    """
    student = _require_student(user_id)
    email = (student.get("email") or "").strip().lower()
    if not email:
        return {
            "found": False,
            "semester": None,
            "deadline_date": None,
            "days_remaining": None,
            "is_passed": False,
            "reason": "no_email",
        }

    conn = get_db()
    cursor = conn.cursor()
    try:
        org_id = _resolve_student_org_id(
            cursor, int(student["id"]), request, prefer_user=True
        )
        group = _find_accepted_group_for_email(cursor, email, org_id=org_id)
        group_id = None
        raw_sem = None
        source = None

        if group:
            group_id = group["id"]
            keys = group.keys() if hasattr(group, "keys") else []
            raw_sem = group["current_semester"] if "current_semester" in keys else None
            if raw_sem is None:
                cursor.execute(
                    "SELECT current_semester FROM fyp_groups WHERE id = ?",
                    (group_id,),
                )
                row = cursor.fetchone()
                raw_sem = row["current_semester"] if row else None
            source = "group"

        if raw_sem is None:
            # No accepted group yet, or group semester unset — use signup profile.
            cursor.execute(
                "SELECT current_semester, department_id FROM users WHERE id = ?",
                (user_id,),
            )
            profile = cursor.fetchone()
            raw_sem = profile["current_semester"] if profile else None
            source = "profile" if raw_sem is not None else source

        if raw_sem is None:
            return {
                "found": False,
                "group_id": group_id,
                "semester": None,
                "deadline_date": None,
                "days_remaining": None,
                "is_passed": False,
                "reason": "semester_unset" if group_id else "no_group",
            }

        try:
            semester = int(raw_sem)
        except (TypeError, ValueError):
            return {
                "found": False,
                "group_id": group_id,
                "semester": None,
                "deadline_date": None,
                "days_remaining": None,
                "is_passed": False,
                "reason": "semester_unset",
            }

        if _table_has_column(cursor, "semester_deadlines", "org_id"):
            cursor.execute(
                """
                SELECT id, semester, deadline_date
                FROM semester_deadlines
                WHERE semester = ? AND COALESCE(org_id, 1) = ?
                """,
                (semester, org_id),
            )
        else:
            cursor.execute(
                """
                SELECT id, semester, deadline_date
                FROM semester_deadlines
                WHERE semester = ?
                """,
                (semester,),
            )
        dl = cursor.fetchone()
        if not dl or not dl["deadline_date"]:
            return {
                "found": False,
                "group_id": group_id,
                "semester": semester,
                "deadline_date": None,
                "days_remaining": None,
                "is_passed": False,
                "reason": "no_deadline_configured",
                "source": source,
            }

        try:
            deadline = date.fromisoformat(str(dl["deadline_date"])[:10])
        except ValueError:
            return {
                "found": False,
                "group_id": group_id,
                "semester": semester,
                "deadline_date": None,
                "days_remaining": None,
                "is_passed": False,
                "reason": "no_deadline_configured",
                "source": source,
            }

        today = date.today()
        days_remaining = (deadline - today).days
        return {
            "found": True,
            "group_id": group_id,
            "semester": semester,
            "deadline_date": deadline.isoformat(),
            "days_remaining": days_remaining,
            "is_passed": days_remaining < 0,
            "reason": None,
            "source": source,
        }
    finally:
        conn.close()


@router.post("/final-submissions")
def create_final_submission(
    request: Request,
    user_id: Annotated[int | None, Query()] = None,
    payload: dict[str, Any] = Body(default_factory=dict),
):
    """
    Student submits a document into final_submissions (status=pending).
    Appears on supervisor GET /submissions. No milestone column on this table —
    milestones live on group_milestones / group_documents.milestone.
    """
    student = _require_student(user_id)
    student_email = (student.get("email") or "").strip().lower()
    if not student_email:
        raise HTTPException(status_code=400, detail="Your account has no email address.")

    try:
        group_id = int(payload.get("group_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="group_id is required.")

    title = (payload.get("title") or "").strip()
    filename = (payload.get("filename") or "").strip() or None
    contact_email = (payload.get("student_contact_email") or student_email).strip().lower()
    if not title:
        raise HTTPException(status_code=400, detail="title is required.")

    source_document_id = payload.get("source_document_id")
    if source_document_id is not None:
        try:
            source_document_id = int(source_document_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="source_document_id must be an integer.")

    analysis_report = payload.get("analysis_report")
    if analysis_report is not None and not isinstance(analysis_report, dict):
        raise HTTPException(status_code=400, detail="analysis_report must be an object.")

    # Slim snapshot matching supervisor seed / detail parser shape
    report_json = None
    if analysis_report:
        slim = {
            "stats": analysis_report.get("stats") or {},
            "structure": analysis_report.get("structure") or {},
            "compliance_score": analysis_report.get("compliance_score"),
            "issues": analysis_report.get("issues") or [],
        }
        report_json = json.dumps(slim)

    conn = get_db()
    cursor = conn.cursor()
    pending_notifications: list = []
    try:
        org_id = _resolve_student_org_id(
            cursor, int(student["id"]), request, prefer_user=True
        )
        group = _student_in_accepted_group(cursor, group_id, student_email, org_id=org_id)
        if not group:
            raise HTTPException(
                status_code=404,
                detail="No accepted FYP group found for this student.",
            )

        # Prefer group's org_id when present
        group_keys = set(group.keys()) if hasattr(group, "keys") else set()
        if "org_id" in group_keys and group["org_id"] is not None:
            org_id = int(group["org_id"] or org_id)

        # Hard block after admin-managed semester deadline (if configured).
        semester = group["current_semester"] if "current_semester" in group_keys else None
        if semester is not None:
            try:
                semester_int = int(semester)
            except (TypeError, ValueError):
                semester_int = None
            if semester_int in (6, 7):
                if _table_has_column(cursor, "semester_deadlines", "org_id"):
                    cursor.execute(
                        """
                        SELECT deadline_date FROM semester_deadlines
                        WHERE semester = ? AND COALESCE(org_id, 1) = ?
                        """,
                        (semester_int, org_id),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT deadline_date FROM semester_deadlines
                        WHERE semester = ?
                        """,
                        (semester_int,),
                    )
                dl_row = cursor.fetchone()
                if dl_row and dl_row["deadline_date"]:
                    try:
                        deadline = date.fromisoformat(str(dl_row["deadline_date"])[:10])
                    except ValueError:
                        deadline = None
                    if deadline is not None and date.today() > deadline:
                        pretty = deadline.strftime("%d %b %Y")
                        raise HTTPException(
                            status_code=403,
                            detail={
                                "code": "deadline_passed",
                                "message": (
                                    f"The Semester {semester_int} deadline ({pretty}) "
                                    "has passed — submissions are closed."
                                ),
                                "semester": semester_int,
                                "deadline_date": deadline.isoformat(),
                            },
                        )

        supervisor_id = group["supervisor_id"]
        if source_document_id is not None:
            cursor.execute(
                "SELECT id FROM documents WHERE id = ? AND user_id = ?",
                (source_document_id, user_id),
            )
            if not cursor.fetchone():
                raise HTTPException(
                    status_code=404,
                    detail="source_document_id not found for this student.",
                )

        has_fs_org = _table_has_column(cursor, "final_submissions", "org_id")
        if has_fs_org:
            cursor.execute(
                """
                INSERT INTO final_submissions
                    (group_id, supervisor_id, title, filename, status, analysis_report,
                     source_document_id, student_contact_email, group_document_id, org_id)
                VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)
                """,
                (
                    group_id,
                    supervisor_id,
                    title,
                    filename,
                    report_json,
                    source_document_id,
                    contact_email,
                    None,
                    org_id,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO final_submissions
                    (group_id, supervisor_id, title, filename, status, analysis_report,
                     source_document_id, student_contact_email, group_document_id)
                VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?)
                """,
                (
                    group_id,
                    supervisor_id,
                    title,
                    filename,
                    report_json,
                    source_document_id,
                    contact_email,
                    None,
                ),
            )
        submission_id = cursor.lastrowid

        group_document_id = _create_group_document_for_submission(
            cursor,
            group_id=group_id,
            supervisor_id=supervisor_id,
            title=title,
            filename=filename,
            source_document_id=source_document_id,
            contact_email=contact_email,
        )
        cursor.execute(
            "UPDATE final_submissions SET group_document_id = ? WHERE id = ?",
            (group_document_id, submission_id),
        )

        cursor.execute(
            "SELECT email, name FROM supervisors WHERE id = ? AND COALESCE(org_id, 1) = ?",
            (supervisor_id, org_id),
        )
        supervisor = cursor.fetchone()
        if supervisor and supervisor["email"]:
            cursor.execute(
                "SELECT id, org_id FROM users WHERE LOWER(email) = LOWER(?) AND COALESCE(org_id, 1) = ?",
                (supervisor["email"], org_id),
            )
            user_row = cursor.fetchone()
            notify_user_id = user_row["id"] if user_row else None
            notify_org_id = int(user_row["org_id"] if user_row and user_row["org_id"] else org_id)

            from services.notification_service import NotificationType
            pending_notifications.append({
                "org_id": notify_org_id,
                "user_id": notify_user_id,
                "type": NotificationType.STUDENT_SUBMITTED,
                "title": "New final submission",
                "body": f"{group['title']} submitted '{title}' for review.",
                "entity_type": "final_submission",
                "entity_id": submission_id,
                "payload": {"screen": "submissions", "submission_id": submission_id},
            })

            # Check plagiarism score and notify if high
            try:
                report = json.loads(report_json) if report_json else {}
                stats = report.get("stats", {})
                plagiarism_score = float(stats.get("avg_plagiarism_risk") or 0)
                if 0 < plagiarism_score <= 1:
                    plagiarism_score = round(plagiarism_score * 100, 1)
                if plagiarism_score > 30:  # Threshold for high plagiarism
                    pending_notifications.append({
                        "org_id": notify_org_id,
                        "user_id": notify_user_id,
                        "type": NotificationType.PLAGIARISM_HIGH,
                        "title": "High plagiarism score detected",
                        "body": f"Submission '{title}' has {plagiarism_score}% plagiarism score.",
                        "entity_type": "final_submission",
                        "entity_id": submission_id,
                        "payload": {"screen": "submissions", "submission_id": submission_id},
                    })
            except Exception as exc:
                logger.exception("Failed to check plagiarism for notification: %s", exc)

        conn.commit()

        # Send notifications only after the write transaction commits —
        # notify() uses its own connection and would hit "database is locked".
        from services.notification_service import notify
        for _n in pending_notifications:
            notify(**_n)

        cursor.execute(
            """
            SELECT fs.*, fg.title AS group_title, fg.project_title AS project_title
            FROM final_submissions fs
            JOIN fyp_groups fg ON fg.id = fs.group_id
            WHERE fs.id = ?
              AND COALESCE(fg.org_id, 1) = ?
            """,
            (submission_id, org_id),
        )
        row = cursor.fetchone()

        # Email the assigned supervisor (background thread; never blocks
        # or fails the request). Runs after commit + notification flush.
        try:
            import submission_mail

            sup_email = (supervisor["email"] if supervisor else "") or ""
            sup_name = (supervisor["name"] if supervisor else "") or ""
            report = _parse_analysis_report_blob(row["analysis_report"] if row else None)
            stats = report.get("stats") if isinstance(report.get("stats"), dict) else {}
            issues = report.get("issues") if isinstance(report.get("issues"), list) else []
            plag_raw = stats.get("avg_plagiarism_risk")
            try:
                plag_score = float(plag_raw) if plag_raw is not None else None
                if plag_score is not None and 0 < plag_score <= 1:
                    plag_score = round(plag_score * 100, 1)
            except (TypeError, ValueError):
                plag_score = None
            grammar_count = sum(
                1 for i in issues
                if isinstance(i, dict) and str(i.get("function") or "").lower() == "grammar"
            ) or int(stats.get("grammar_issues") or 0) or None
            comp_raw = report.get("compliance_score")
            try:
                comp_score = float(comp_raw) if comp_raw is not None else None
            except (TypeError, ValueError):
                comp_score = None

            submission_mail.queue_submission_received_email(
                submission_id=submission_id,
                org_id=org_id,
                supervisor_name=sup_name,
                supervisor_email=sup_email,
                student_name=student.get("username") or "",
                group_name=(row["group_title"] if row else "") or "",
                project_title=(row["project_title"] if row else "") or "",
                file_name=(row["filename"] if row and row["filename"] else (row["title"] if row else "")) or "",
                submitted_at=str(row["submitted_at"]) if row and row["submitted_at"] else "",
                plagiarism_score=plag_score,
                compliance_score=comp_score,
                grammar_count=grammar_count,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to queue submission email")

        return {
            "success": True,
            "message": "Submitted for supervisor review.",
            "submission": _serialize_student_final_submission(row),
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Failed to create final submission")
        raise HTTPException(status_code=500, detail="Could not create final submission.")
    finally:
        conn.close()


def _parse_analysis_report_blob(raw: Any) -> dict[str, Any]:
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


def _plagiarism_risk_level(score: float) -> str:
    if score >= 60:
        return "high"
    if score >= 30:
        return "some"
    return "safe"


def _matches_from_plagiarism_issues(issues: list[Any]) -> list[dict[str, Any]]:
    """Same match shape as supervisor plagiarism-monitor detail."""
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
            source = f"Detected match ({match_type})" if match_type else "Unknown source"
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


def _plagiarism_payload_from_report(
    report: dict[str, Any],
    *,
    group_row,
    submission_id: int | None,
) -> dict[str, Any]:
    stats = report.get("stats") if isinstance(report.get("stats"), dict) else {}
    structure = report.get("structure") if isinstance(report.get("structure"), dict) else {}
    summary = structure.get("summary") if isinstance(structure.get("summary"), dict) else {}
    issues = report.get("issues") if isinstance(report.get("issues"), list) else []
    matches = _matches_from_plagiarism_issues(issues)

    score = float(stats.get("avg_plagiarism_risk") or 0)
    if 0 < score <= 1:
        score = round(score * 100, 1)

    keys = group_row.keys() if hasattr(group_row, "keys") else []
    flagged = bool(group_row["plagiarism_flagged"]) if "plagiarism_flagged" in keys else False
    flag_reason = (
        (group_row["plagiarism_flag_reason"] or "")
        if "plagiarism_flag_reason" in keys
        else ""
    )
    flagged_at = (
        (group_row["plagiarism_flagged_at"] or "")
        if "plagiarism_flagged_at" in keys
        else ""
    )

    return {
        "group_id": group_row["id"],
        "group_title": group_row["title"] or "",
        "project_title": group_row["project_title"] or "",
        "submission_id": submission_id,
        "plagiarism_score": score,
        "risk_level": _plagiarism_risk_level(score),
        "match_count": len(matches),
        "matches": matches,
        "data_source": "final_submissions.analysis_report" if submission_id else "none",
        "flagged": flagged,
        "flag_reason": flag_reason,
        "flagged_at": flagged_at,
        "plagiarism_issues": int(
            stats.get("plagiarism_issues") or summary.get("plagiarism") or len(matches)
        ),
    }


def _require_student_group(cursor, group_id: int, email: str, org_id: int | None = None):
    """Accept contact leader or any listed group member (same as submit path)."""
    group = _student_in_accepted_group(cursor, group_id, email, org_id=org_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found for this student.")
    # Load full row used by plagiarism / status helpers
    if org_id is not None and _table_has_column(cursor, "fyp_groups", "org_id"):
        cursor.execute(
            """
            SELECT id, title, project_title, plagiarism_flagged, plagiarism_flag_reason,
                   plagiarism_flagged_at, student_contact_email, status, supervisor_id,
                   member_names, org_id
            FROM fyp_groups
            WHERE id = ? AND status = 'accepted' AND COALESCE(org_id, 1) = ?
            """,
            (group_id, org_id),
        )
    else:
        cursor.execute(
            """
            SELECT id, title, project_title, plagiarism_flagged, plagiarism_flag_reason,
                   plagiarism_flagged_at, student_contact_email, status, supervisor_id,
                   member_names
            FROM fyp_groups
            WHERE id = ? AND status = 'accepted'
            """,
            (group_id,),
        )
    full = cursor.fetchone()
    if not full:
        raise HTTPException(status_code=404, detail="Group not found for this student.")
    return full


@router.get("/final-submissions/{submission_id}/plagiarism")
def get_final_submission_plagiarism(
    submission_id: int,
    user_id: Annotated[int | None, Query()] = None,
):
    """
    Read-only plagiarism snapshot from final_submissions.analysis_report (no recompute).
    Flagged state comes from fyp_groups.plagiarism_flagged / plagiarism_flag_reason.
    """
    student = _require_student(user_id)
    email = (student.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Your account has no email address.")

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT fs.id, fs.group_id, fs.analysis_report, fs.title, fs.filename, fs.status
            FROM final_submissions fs
            JOIN fyp_groups fg ON fg.id = fs.group_id
            WHERE fs.id = ?
              AND fg.status = 'accepted'
            """,
            (submission_id,),
        )
        sub = cursor.fetchone()
        if not sub:
            raise HTTPException(status_code=404, detail="Submission not found.")

        group = _require_student_group(
            cursor, sub["group_id"], email, org_id=int(student.get("org_id") or 1)
        )
        report = _parse_analysis_report_blob(sub["analysis_report"])
        payload = _plagiarism_payload_from_report(
            report, group_row=group, submission_id=sub["id"]
        )
        payload["submission_title"] = sub["title"] or ""
        payload["filename"] = sub["filename"] or ""
        payload["submission_status"] = sub["status"] or ""
        return payload
    finally:
        conn.close()


@router.get("/groups/{group_id}/plagiarism")
def get_group_plagiarism_report(
    group_id: int,
    user_id: Annotated[int | None, Query()] = None,
):
    """
    Latest final_submissions.analysis_report for the group (AI Tools snapshot from screen 4).
    Includes supervisor plagiarism flag from fyp_groups — no recompute.
    """
    student = _require_student(user_id)
    email = (student.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Your account has no email address.")

    conn = get_db()
    cursor = conn.cursor()
    try:
        group = _require_student_group(
            cursor, group_id, email, org_id=int(student.get("org_id") or 1)
        )
        cursor.execute(
            """
            SELECT id, analysis_report, title, filename, status
            FROM final_submissions
            WHERE group_id = ?
            ORDER BY datetime(submitted_at) DESC, id DESC
            LIMIT 1
            """,
            (group_id,),
        )
        sub = cursor.fetchone()
        if not sub:
            return _plagiarism_payload_from_report(
                {}, group_row=group, submission_id=None
            )

        report = _parse_analysis_report_blob(sub["analysis_report"])
        payload = _plagiarism_payload_from_report(
            report, group_row=group, submission_id=sub["id"]
        )
        payload["submission_title"] = sub["title"] or ""
        payload["filename"] = sub["filename"] or ""
        payload["submission_status"] = sub["status"] or ""
        return payload
    finally:
        conn.close()


def _submission_stage(status: str | None) -> dict[str, Any]:
    """
    Map final_submissions.status exactly as supervisor_routes writes:
      approve → "approved"
      request-revision → "revision"
      reject → "rejected"
      default insert → "pending"
    """
    raw = (status or "pending").strip().lower()
    if raw == "approved":
        return {
            "status": "approved",
            "stage": "Approved",
            "stage_index": 3,
            "stage_count": 3,
            "needs_resubmit": False,
        }
    if raw == "revision":
        return {
            "status": "revision",
            "stage": "Revisions Needed",
            "stage_index": 2,
            "stage_count": 3,
            "needs_resubmit": True,
        }
    if raw == "rejected":
        return {
            "status": "rejected",
            "stage": "Rejected",
            "stage_index": 3,
            "stage_count": 3,
            "needs_resubmit": False,
        }
    return {
        "status": "pending" if raw == "pending" else raw,
        "stage": "Under Review",
        "stage_index": 1,
        "stage_count": 3,
        "needs_resubmit": False,
    }


def _analysis_summary_from_report_row(row) -> dict[str, Any]:
    """Same analysis_report fields as _serialize_student_final_submission."""
    report_raw = row["analysis_report"] if "analysis_report" in row.keys() else None
    report: dict[str, Any] = {}
    if isinstance(report_raw, dict):
        report = report_raw
    elif report_raw:
        try:
            parsed = json.loads(str(report_raw))
            if isinstance(parsed, dict):
                report = parsed
        except json.JSONDecodeError:
            report = {}

    stats = report.get("stats") if isinstance(report.get("stats"), dict) else {}
    structure = report.get("structure") if isinstance(report.get("structure"), dict) else {}
    summary = structure.get("summary") if isinstance(structure.get("summary"), dict) else {}
    issues = report.get("issues") if isinstance(report.get("issues"), list) else []
    plagiarism_score = float(stats.get("avg_plagiarism_risk") or 0)
    if 0 < plagiarism_score <= 1:
        plagiarism_score = round(plagiarism_score * 100, 1)

    return {
        "grammar_issues": int(stats.get("grammar_issues") or summary.get("grammar") or 0),
        "plagiarism_issues": int(stats.get("plagiarism_issues") or summary.get("plagiarism") or 0),
        "plagiarism_score": plagiarism_score,
        "total_issues": int(stats.get("total_issues") or len(issues) or 0),
        "major_issues": int(stats.get("major_issues") or 0),
        "minor_issues": int(stats.get("minor_issues") or 0),
        "compliance_score": float(
            report.get("compliance_score")
            or structure.get("score")
            or stats.get("avg_formatting_compliance")
            or 0
        ),
        "structure_status": str(structure.get("status") or ""),
    }


def _serialize_status_tracker_submission(row) -> dict[str, Any]:
    stage = _submission_stage(row["status"] if "status" in row.keys() else None)
    keys = set(row.keys()) if hasattr(row, "keys") else set()
    return {
        "id": row["id"],
        "group_id": row["group_id"],
        "title": row["title"] or "",
        "filename": row["filename"] or "",
        "status": stage["status"],
        "stage": stage["stage"],
        "stage_index": stage["stage_index"],
        "stage_count": stage["stage_count"],
        "needs_resubmit": stage["needs_resubmit"],
        "decision_note": row["decision_note"] or "",
        "submitted_at": row["submitted_at"],
        "resolved_at": row["resolved_at"],
        "source_document_id": row["source_document_id"],
        "group_document_id": row["group_document_id"] if "group_document_id" in keys else None,
        "student_contact_email": row["student_contact_email"] or "",
        # Formatting % / issues — same analysis_report fields as supervisor list
        "analysis_summary": _analysis_summary_from_report_row(row),
    }


@router.get("/groups/{group_id}/submissions")
def list_group_final_submissions(
    group_id: int,
    user_id: Annotated[int | None, Query()] = None,
):
    """
    Status Tracker: final_submissions for this group (not remarks).
    Status strings match supervisor approve/request-revision/reject writers.
    """
    student = _require_student(user_id)
    email = (student.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Your account has no email address.")

    conn = get_db()
    cursor = conn.cursor()
    try:
        _require_student_group(
            cursor, group_id, email, org_id=int(student.get("org_id") or 1)
        )
        cursor.execute(
            """
            SELECT id, group_id, title, filename, status, decision_note,
                   submitted_at, resolved_at, source_document_id, group_document_id,
                   student_contact_email, analysis_report
            FROM final_submissions
            WHERE group_id = ?
            ORDER BY datetime(submitted_at) DESC, id DESC
            """,
            (group_id,),
        )
        rows = [_serialize_status_tracker_submission(r) for r in cursor.fetchall()]
        latest = rows[0] if rows else None
        return {
            "group_id": group_id,
            "submissions": rows,
            "count": len(rows),
            "latest": latest,
        }
    finally:
        conn.close()


def _serialize_notification(row, cursor=None) -> dict[str, Any]:
    """
    Student notification payload.

    Supervisor comment inserts already set:
      related_type = "document_comment"
      related_id   = document_comments.id  (the new comment row)

    When related_type is document_comment, enrich with group_id / document_id
    so the mobile inbox can open DocumentFeedbackScreen without a second lookup.
    """
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
    if (
        cursor is not None
        and related_type == "document_comment"
        and related_id is not None
    ):
        cursor.execute(
            """
            SELECT dc.id AS comment_id, dc.document_id, gd.group_id
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

    return result


def _serialize_student_review_paragraphs(cursor, document_id: int) -> list[dict[str, Any]]:
    """Match supervisor `_serialize_review_paragraphs` shape (incl. parent_comment_id)."""
    from docx_tools.review_blocks import BLOCK_FRONTMATTER, display_label_for_block_type

    cursor.execute(
        """
        SELECT id, sort_order, text, block_type
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
        if not (row["text"] or "").strip():
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
                comment["parent_comment_id"] if "parent_comment_id" in ckeys else None
            )
            # Highlight only from supervisor top-level comments (not student replies)
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
        if has_unresolved:
            highlight = "unresolved"
        elif has_resolved:
            highlight = "resolved"
        else:
            highlight = "none"
        paragraphs.append(
            {
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
        )
    return paragraphs


def _require_student_group_document(
    cursor, group_id: int, document_id: int, email: str, org_id: int | None = None
):
    """Any accepted-group member may open the review document for feedback."""
    _require_student_group(cursor, group_id, email, org_id=org_id)
    cursor.execute(
        """
        SELECT gd.id, gd.title, gd.filename, gd.status, gd.submitted_at,
               gd.group_id, fg.title AS group_title
        FROM group_documents gd
        JOIN fyp_groups fg ON fg.id = gd.group_id
        WHERE gd.id = ?
          AND gd.group_id = ?
          AND fg.status = 'accepted'
          AND (? IS NULL OR COALESCE(fg.org_id, 1) = ?)
        """,
        (document_id, group_id, org_id, org_id),
    )
    doc = cursor.fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found for this student.")
    return doc


def _require_student_comment(cursor, comment_id: int, email: str, org_id: int | None = None):
    """Any accepted-group member may resolve/reply to comments on their document."""
    cursor.execute(
        """
        SELECT dc.id, dc.paragraph_id, dc.document_id, dc.supervisor_id,
               dc.comment_text, dc.is_resolved, dc.parent_comment_id,
               gd.group_id
        FROM document_comments dc
        JOIN group_documents gd ON gd.id = dc.document_id
        JOIN fyp_groups fg ON fg.id = gd.group_id
        WHERE dc.id = ?
          AND fg.status = 'accepted'
          AND (? IS NULL OR COALESCE(fg.org_id, 1) = ?)
        """,
        (comment_id, org_id, org_id),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Comment not found.")
    _require_student_group(cursor, int(row["group_id"]), email, org_id=org_id)
    return row


@router.get("/groups/{group_id}/documents/{document_id}/comments")
def get_student_document_comments(
    group_id: int,
    document_id: int,
    user_id: Annotated[int | None, Query()] = None,
):
    """
    Paragraph + comments for student feedback UI.
    Response shape matches supervisor GET .../review (paragraphs[].comments[]).
    """
    student = _require_student(user_id)
    email = (student.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Your account has no email address.")

    conn = get_db()
    cursor = conn.cursor()
    try:
        doc = _require_student_group_document(
            cursor, group_id, document_id, email, org_id=int(student.get("org_id") or 1)
        )
        # Backfill paragraphs for older submissions (same helper supervisor review uses)
        from routes.supervisor_routes import _ensure_document_paragraphs

        _ensure_document_paragraphs(
            cursor, document_id, document_title=doc["title"] or ""
        )
        conn.commit()
        paragraphs = _serialize_student_review_paragraphs(cursor, document_id)
        return {
            "group_id": group_id,
            "group_title": doc["group_title"] or "",
            "document": {
                "id": doc["id"],
                "title": doc["title"],
                "filename": doc["filename"] or "",
                "status": doc["status"] or "",
                "submitted_at": doc["submitted_at"],
            },
            "paragraphs": paragraphs,
        }
    finally:
        conn.close()


@router.post("/comments/{comment_id}/resolve")
def resolve_student_comment(
    comment_id: int,
    user_id: Annotated[int | None, Query()] = None,
):
    """Student marks a single document_comments row resolved (is_resolved = true)."""
    student = _require_student(user_id)
    email = (student.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Your account has no email address.")

    from datetime import datetime

    conn = get_db()
    cursor = conn.cursor()
    try:
        comment = _require_student_comment(
            cursor, comment_id, email, org_id=int(student.get("org_id") or 1)
        )
        if bool(comment["is_resolved"]):
            return {
                "success": True,
                "message": "Comment already resolved.",
                "comment_id": comment_id,
                "group_id": comment["group_id"],
                "document_id": comment["document_id"],
            }

        resolved_at = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
        cursor.execute(
            """
            UPDATE document_comments
            SET is_resolved = 1, resolved_at = ?
            WHERE id = ?
            """,
            (resolved_at, comment_id),
        )
        conn.commit()
        return {
            "success": True,
            "message": "Comment marked as resolved.",
            "comment_id": comment_id,
            "group_id": comment["group_id"],
            "document_id": comment["document_id"],
            "resolved_at": resolved_at,
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Failed to resolve student comment")
        raise HTTPException(status_code=500, detail="Could not resolve comment.")
    finally:
        conn.close()


@router.post("/comments/{comment_id}/reply")
def reply_to_student_comment(
    comment_id: int,
    user_id: Annotated[int | None, Query()] = None,
    payload: dict[str, Any] = Body(default_factory=dict),
):
    """
    Student reply under an existing supervisor comment.
    Inserts a new document_comments row with parent_comment_id set (same paragraph).
    Note: supervisor Document Review lists comments flat (multi per paragraph) —
    replies appear as additional peer comments, not nested threads.
    """
    student = _require_student(user_id)
    email = (student.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Your account has no email address.")

    reply_text = (payload.get("reply_text") or payload.get("comment_text") or "").strip()
    if not reply_text:
        raise HTTPException(status_code=400, detail="reply_text is required.")

    conn = get_db()
    cursor = conn.cursor()
    pending_notifications: list = []
    try:
        parent = _require_student_comment(
            cursor, comment_id, email, org_id=int(student.get("org_id") or 1)
        )
        if parent["parent_comment_id"] is not None:
            raise HTTPException(
                status_code=400,
                detail="Replies can only be added to supervisor comments.",
            )
        # Replies reuse supervisor_id for FK; mark resolved so they don't look like open feedback.
        cursor.execute(
            """
            INSERT INTO document_comments
                (paragraph_id, document_id, supervisor_id, comment_text,
                 is_resolved, parent_comment_id)
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (
                parent["paragraph_id"],
                parent["document_id"],
                parent["supervisor_id"],
                reply_text,
                comment_id,
            ),
        )
        reply_id = cursor.lastrowid

        # Notify supervisor so they can open review from their mobile inbox
        org_id = int(student.get("org_id") or 1)
        cursor.execute(
            "SELECT email, name FROM supervisors WHERE id = ? AND COALESCE(org_id, 1) = ?",
            (parent["supervisor_id"], org_id),
        )
        supervisor = cursor.fetchone()
        student_name = (student.get("username") or student.get("name") or "Student").strip()
        if supervisor and supervisor["email"]:
            snippet = reply_text[:120] + ("…" if len(reply_text) > 120 else "")
            cursor.execute(
                "SELECT id, org_id FROM users WHERE LOWER(email) = LOWER(?) AND COALESCE(org_id, 1) = ?",
                (supervisor["email"], org_id),
            )
            user_row = cursor.fetchone()
            notify_user_id = user_row["id"] if user_row else None
            notify_org_id = int(user_row["org_id"] if user_row and user_row["org_id"] else org_id)

            from services.notification_service import NotificationType
            pending_notifications.append({
                "org_id": notify_org_id,
                "user_id": notify_user_id,
                "type": NotificationType.STUDENT_REPLY,
                "title": "Student replied to your comment",
                "body": f"{student_name}: {snippet}",
                "entity_type": "document_comment",
                "entity_id": reply_id,
                "payload": {"screen": "comments", "comment_id": reply_id},
            })

        conn.commit()

        from services.notification_service import notify
        for _n in pending_notifications:
            notify(**_n)
        paragraphs = _serialize_student_review_paragraphs(cursor, parent["document_id"])
        return {
            "success": True,
            "message": "Reply added.",
            "comment_id": reply_id,
            "parent_comment_id": comment_id,
            "group_id": parent["group_id"],
            "document_id": parent["document_id"],
            "paragraphs": paragraphs,
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Failed to add student reply")
        raise HTTPException(status_code=500, detail="Could not add reply.")
    finally:
        conn.close()


@router.get("/notifications")
def list_student_notifications(
    email: Annotated[str | None, Query()] = None,
    user_id: Annotated[int | None, Query()] = None,
    unread_only: Annotated[bool, Query()] = False,
):
    """
    List notifications for a student by user_id AND org_id (falling back to recipient_email if user_id is NULL).
    Requires student login; email query must match the account email when provided.
    Wrapper over unified notification table for backward compatibility.
    """
    student = _require_student(user_id)
    account_email = (student.get("email") or "").strip().lower()
    if not account_email:
        raise HTTPException(status_code=400, detail="Your account has no email address.")

    query_email = (email or "").strip().lower() or account_email
    if query_email != account_email:
        raise HTTPException(
            status_code=403,
            detail="email must match the logged-in student account.",
        )

    student_id = int(student["id"])
    student_org_id = int(student.get("org_id") or 1)

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
        params: list[Any] = [student_id, query_email, student_org_id]
        if unread_only:
            sql += " AND is_read = 0"
        sql += " ORDER BY datetime(created_at) DESC, id DESC"
        cursor.execute(sql, params)
        rows = [_serialize_notification(r, cursor) for r in cursor.fetchall()]
        unread = sum(1 for r in rows if not r["is_read"])
        return {
            "notifications": rows,
            "count": len(rows),
            "unread_count": unread,
            "recipient_email": query_email,
        }
    finally:
        conn.close()


@router.patch("/notifications/{notification_id}/read")
def mark_student_notification_read(
    notification_id: int,
    email: Annotated[str | None, Query()] = None,
    user_id: Annotated[int | None, Query()] = None,
):
    """Mark a notification as read — filtered by user_id AND org_id (fallback to recipient_email if user_id is NULL)."""
    student = _require_student(user_id)
    account_email = (student.get("email") or "").strip().lower()
    if not account_email:
        raise HTTPException(status_code=400, detail="Your account has no email address.")

    query_email = (email or "").strip().lower() or account_email
    if query_email != account_email:
        raise HTTPException(
            status_code=403,
            detail="email must match the logged-in student account.",
        )

    student_id = int(student["id"])
    student_org_id = int(student.get("org_id") or 1)

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, user_id, recipient_email, title, message, type, is_read,
                   related_type, related_id, created_at, org_id
            FROM notifications
            WHERE id = ?
              AND ((user_id = ?) OR (user_id IS NULL AND LOWER(TRIM(recipient_email)) = LOWER(?)))
              AND COALESCE(org_id, 1) = ?
            """,
            (notification_id, student_id, query_email, student_org_id),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Notification not found.")

        cursor.execute(
            "UPDATE notifications SET is_read = 1 WHERE id = ?",
            (notification_id,),
        )
        conn.commit()
        cursor.execute(
            """
            SELECT id, user_id, recipient_email, title, message, type, is_read,
                   related_type, related_id, created_at, org_id
            FROM notifications
            WHERE id = ?
            """,
            (notification_id,),
        )
        updated = cursor.fetchone()
        return {
            "success": True,
            "notification": _serialize_notification(updated, cursor),
        }
    except HTTPException:
        conn.rollback()
        raise
    finally:
        conn.close()
