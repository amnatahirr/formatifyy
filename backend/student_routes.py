"""Student-facing read APIs (meeting notes, etc.)."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from database import get_db

router = APIRouter(prefix="/api/student", tags=["Student"])
logger = logging.getLogger(__name__)


def _row_to_dict(row) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def _require_student(user_id: int | None) -> dict[str, Any]:
    if user_id is None:
        raise HTTPException(status_code=401, detail="Student login required.")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, role, username FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access required.")
    return _row_to_dict(user)


def _serialize_note(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "group_id": row["group_id"],
        "meeting_date": (row["meeting_date"] or "")[:10] if row["meeting_date"] else "",
        "topic": row["topic"] or "",
        "action_items": row["action_items"] or "",
        "created_at": row["created_at"] or "",
        "group_title": row["group_title"] or "",
        "project_title": row["project_title"] or "",
        "supervisor_name": row["supervisor_name"] or "",
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
