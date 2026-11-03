"""
frontmatter_data.py — Assemble FrontmatterContext for cover / info page generation.

Pulls branding from admin_settings, group/supervisor fields from fyp_groups,
and optional domains / signature from the documents row (or request overrides).
Missing / null fields become empty strings — never raises for optional data.
"""

from __future__ import annotations

import json
from typing import Any, List, Optional, Sequence

from database import get_db
from models import FrontmatterContext, FrontmatterMember
from routes.student_routes import _parse_member_names


def _settings_map(cursor) -> dict[str, str]:
    cursor.execute("SELECT key, value FROM admin_settings")
    return {row["key"]: (row["value"] or "") for row in cursor.fetchall()}


def _members_from_names(names: Sequence[str]) -> List[FrontmatterMember]:
    return [
        FrontmatterMember(name=n, reg_no=None, email=None)
        for n in names
        if str(n).strip()
    ]


def _parse_domains(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    text = str(raw).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except json.JSONDecodeError:
        pass
    return [p.strip() for p in text.split(",") if p.strip()]


def build_frontmatter_context(
    document_id: int,
    *,
    group_id: Optional[int] = None,
    domains: Optional[Sequence[str]] = None,
    signature_path: Optional[str] = None,
) -> FrontmatterContext:
    """
    Fetch and assemble all template data for a document.

    Resolution order for group:
      1. Explicit group_id argument
      2. documents.group_id
      3. First accepted fyp_groups row matching the document owner's email
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT d.*, u.email AS user_email, u.university_id
            FROM documents d
            JOIN users u ON u.id = d.user_id
            WHERE d.id = ?
            """,
            (document_id,),
        )
        doc = cursor.fetchone()
        if not doc:
            raise ValueError(f"Document {document_id} not found.")

        settings = _settings_map(cursor)
        university_name = (settings.get("university_name") or "").strip()
        department = (settings.get("department_name") or "").strip()
        session = (settings.get("session") or "").strip()
        logo_path = (settings.get("logo_path") or "").strip() or None

        # Prefer university table name when branding key is empty
        if not university_name and doc["university_id"]:
            cursor.execute(
                "SELECT name FROM universities WHERE id = ?",
                (doc["university_id"],),
            )
            uni = cursor.fetchone()
            if uni and uni["name"]:
                university_name = uni["name"]

        resolved_group_id = group_id if group_id is not None else doc["group_id"]
        group_row = None

        if resolved_group_id is not None:
            cursor.execute(
                """
                SELECT
                    g.id,
                    g.project_title,
                    g.title,
                    g.member_names,
                    g.cosupervisor_name,
                    g.department_id,
                    COALESCE(s.name, '') AS supervisor_name,
                    COALESCE(d.name, '') AS department_name
                FROM fyp_groups g
                LEFT JOIN supervisors s ON s.id = g.supervisor_id
                LEFT JOIN departments d ON d.id = g.department_id
                WHERE g.id = ?
                """,
                (resolved_group_id,),
            )
            group_row = cursor.fetchone()

        if group_row is None:
            email = (doc["user_email"] or "").strip().lower()
            if email:
                cursor.execute(
                    """
                    SELECT
                        g.id,
                        g.project_title,
                        g.title,
                        g.member_names,
                        g.cosupervisor_name,
                        g.department_id,
                        COALESCE(s.name, '') AS supervisor_name,
                        COALESCE(d.name, '') AS department_name
                    FROM fyp_groups g
                    LEFT JOIN supervisors s ON s.id = g.supervisor_id
                    LEFT JOIN departments d ON d.id = g.department_id
                    WHERE g.status = 'accepted'
                      AND (
                        LOWER(TRIM(g.student_contact_email)) = LOWER(?)
                        OR LOWER(g.member_names) LIKE '%' || LOWER(?) || '%'
                      )
                    ORDER BY g.id DESC
                    LIMIT 1
                    """,
                    (email, email),
                )
                group_row = cursor.fetchone()

        project_title = ""
        members: List[FrontmatterMember] = []
        supervisor_name = ""
        cosupervisor_name = ""

        if group_row is not None:
            project_title = (
                (group_row["project_title"] or group_row["title"] or "")
            ).strip()
            members = _members_from_names(_parse_member_names(group_row["member_names"]))
            supervisor_name = (group_row["supervisor_name"] or "").strip()
            try:
                cosupervisor_name = (group_row["cosupervisor_name"] or "").strip()
            except (KeyError, IndexError):
                cosupervisor_name = ""
            if not department and group_row["department_name"]:
                department = group_row["department_name"]

        # Domains / signature: request override → document columns
        resolved_domains = (
            list(domains)
            if domains is not None
            else _parse_domains(doc["frontmatter_domains"] if "frontmatter_domains" in doc.keys() else None)
        )
        if signature_path is not None:
            resolved_sig = signature_path.strip() or None
        else:
            raw_sig = doc["signature_path"] if "signature_path" in doc.keys() else None
            resolved_sig = (raw_sig or "").strip() or None

        return FrontmatterContext(
            project_title=project_title,
            university_name=university_name,
            department=department,
            session=session,
            logo_path=logo_path,
            members=members,
            supervisor_name=supervisor_name,
            cosupervisor_name=cosupervisor_name,
            domains=resolved_domains,
            signature_path=resolved_sig,
        )
    finally:
        conn.close()
