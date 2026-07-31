"""Sync collaboration project snapshots into each member's My Reports."""

from __future__ import annotations

import os
import shutil
from typing import Any, Dict, List, Optional

from database import get_db

from vc.merge import UPLOAD_DIR, assemble_merged_docx

VC_UPLOAD_DIR = os.path.join("uploads", "vc")
OUTPUT_DIR = "outputs"


def get_project_for_document(document_id: int) -> Optional[int]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT project_id FROM project_member_documents WHERE document_id = ?",
        (document_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return int(row["project_id"]) if row else None


def sync_analysis_to_project_members(
    document_id: int,
    working_copy_path: str,
    *,
    mark_completed: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Copy an analyzed/fixed working document to the shared project snapshot and
    mirror it into every member's My Reports entry (file, working copy, export).
    """
    if not working_copy_path or not os.path.exists(working_copy_path):
        return None

    project_id = get_project_for_document(document_id)
    if not project_id:
        return None

    from vc.service import _get_project

    project = _get_project(project_id)
    if not project:
        return None

    project_dir = os.path.join(VC_UPLOAD_DIR, f"project_{project_id}")
    os.makedirs(project_dir, exist_ok=True)
    snapshot_path = project.get("shared_snapshot_path") or os.path.join(
        project_dir, "collaboration_live.docx"
    )
    shutil.copy2(working_copy_path, snapshot_path)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT document_id FROM project_member_documents
        WHERE project_id = ?
        """,
        (project_id,),
    )
    member_rows = cursor.fetchall()

    status = "completed" if mark_completed else "uploaded"
    member_doc_ids: List[int] = []

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for row in member_rows:
        member_doc_id = int(row["document_id"])
        member_doc_ids.append(member_doc_id)

        cursor.execute(
            """
            UPDATE documents
            SET file_path = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (snapshot_path, status, member_doc_id),
        )

        member_working = os.path.join(
            UPLOAD_DIR, "working", f"doc_{member_doc_id}_working.docx"
        )
        os.makedirs(os.path.dirname(member_working), exist_ok=True)
        shutil.copy2(working_copy_path, member_working)

        export_path = os.path.join(OUTPUT_DIR, f"export_{member_doc_id}.docx")
        shutil.copy2(working_copy_path, export_path)

    cursor.execute(
        """
        UPDATE collaboration_projects
        SET shared_snapshot_path = ?
        WHERE id = ?
        """,
        (snapshot_path, project_id),
    )
    conn.commit()
    conn.close()

    return {
        "project_id": project_id,
        "snapshot_path": snapshot_path,
        "member_document_ids": member_doc_ids,
    }


def _project_members(project_id: int) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id FROM project_members WHERE project_id = ?",
        (project_id,),
    )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def _get_member_document_id(project_id: int, user_id: int) -> Optional[int]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT document_id FROM project_member_documents
        WHERE project_id = ? AND user_id = ?
        """,
        (project_id, user_id),
    )
    row = cursor.fetchone()
    conn.close()
    return int(row["document_id"]) if row else None


def _user_org_id(cursor, user_id: int) -> int:
    cursor.execute("SELECT org_id FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if row and "org_id" in row.keys() and row["org_id"] is not None:
        return int(row["org_id"])
    return 1


def _documents_has_org_id(cursor) -> bool:
    cursor.execute("PRAGMA table_info(documents)")
    return "org_id" in {row[1] for row in cursor.fetchall()}


def _upsert_member_document(
    project_id: int,
    user_id: int,
    template_id: int,
    filename: str,
    file_path: str,
) -> int:
    conn = get_db()
    cursor = conn.cursor()
    existing_id = _get_member_document_id(project_id, user_id)

    if existing_id:
        cursor.execute(
            """
            UPDATE documents
            SET file_path = ?, filename = ?, status = 'uploaded',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (file_path, filename, existing_id, user_id),
        )
        doc_id = existing_id
    else:
        if _documents_has_org_id(cursor):
            cursor.execute(
                """
                INSERT INTO documents (user_id, template_id, filename, file_path, status, org_id)
                VALUES (?, ?, ?, ?, 'uploaded', ?)
                """,
                (user_id, template_id, filename, file_path, _user_org_id(cursor, user_id)),
            )
        else:
            cursor.execute(
                """
                INSERT INTO documents (user_id, template_id, filename, file_path, status)
                VALUES (?, ?, ?, ?, 'uploaded')
                """,
                (user_id, template_id, filename, file_path),
            )
        doc_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO project_member_documents (project_id, user_id, document_id)
            VALUES (?, ?, ?)
            """,
            (project_id, user_id, doc_id),
        )

    conn.commit()
    conn.close()
    return int(doc_id)


def sync_project_to_member_reports(project_id: int) -> Optional[Dict[str, Any]]:
    """
    Build a live DOCX snapshot from current section content and register/update
    a My Reports document for every project member.
    """
    from vc.service import (
        get_latest_content_map,
        get_project_sections,
        get_section_images_map,
        _get_project,
    )

    project = _get_project(project_id)
    sections = get_project_sections(project_id)
    latest_map = get_latest_content_map(project_id)
    latest_by_section = {sid: data.get("content", "") for sid, data in latest_map.items()}

    has_content = any((content or "").strip() for content in latest_by_section.values())
    base_path = project.get("base_document_path")
    has_base = bool(base_path and os.path.exists(base_path))

    if not has_content and not has_base:
        return None

    project_dir = os.path.join(VC_UPLOAD_DIR, f"project_{project_id}")
    os.makedirs(project_dir, exist_ok=True)
    snapshot_path = os.path.join(project_dir, "collaboration_live.docx")

    if has_content:
        section_images = get_section_images_map(project_id)
        assemble_merged_docx(
            sections,
            latest_by_section,
            snapshot_path,
            int(project["template_id"]),
            section_images,
        )
    else:
        shutil.copy2(base_path, snapshot_path)

    raw_name = (project.get("base_document_filename") or "").strip()
    if raw_name:
        display_filename = raw_name if raw_name.lower().endswith(".docx") else f"{raw_name}.docx"
    else:
        display_filename = f"{project['name']} (Collaboration).docx"

    member_docs: Dict[int, int] = {}

    for member in _project_members(project_id):
        uid = int(member["user_id"])
        doc_id = _upsert_member_document(
            project_id=project_id,
            user_id=uid,
            template_id=int(project["template_id"]),
            filename=display_filename,
            file_path=snapshot_path,
        )
        member_docs[uid] = doc_id

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE collaboration_projects
        SET shared_snapshot_path = ?, base_document_path = COALESCE(base_document_path, ?)
        WHERE id = ?
        """,
        (snapshot_path, snapshot_path, project_id),
    )
    conn.commit()
    conn.close()

    return {
        "snapshot_path": snapshot_path,
        "member_documents": member_docs,
        "filename": display_filename,
    }


def ensure_project_reports_synced(project_id: int) -> None:
    """Backfill My Reports entries for any member missing a linked document."""
    members = _project_members(project_id)
    if not members:
        return

    needs_sync = False
    for member in members:
        uid = int(member["user_id"])
        if not _get_member_document_id(project_id, uid):
            needs_sync = True
            break

    if not needs_sync:
        from vc.service import _get_project
        project = _get_project(project_id)
        if not project.get("shared_snapshot_path"):
            needs_sync = True

    if needs_sync:
        sync_project_to_member_reports(project_id)
