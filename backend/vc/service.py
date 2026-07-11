"""Core business logic for the VC module."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, UploadFile

from database import get_db
from templates import get_template_by_id
from vc.conflicts import detect_all_conflicts, store_conflicts
from vc.database import generate_invite_code
from vc.docx_import import extract_sections_from_docx
from vc.merge import (
    assemble_merged_docx,
    create_merged_document_record,
    resolve_section_content_map,
    update_merge_completed,
)
from vc.reports_sync import ensure_project_reports_synced, sync_project_to_member_reports
from vc.utils import parse_template_sections


VC_UPLOAD_DIR = os.path.join("uploads", "vc")
os.makedirs(VC_UPLOAD_DIR, exist_ok=True)


def _row_to_dict(row) -> Dict[str, Any]:
    return dict(row) if row else {}


def _get_user(user_id: int) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return _row_to_dict(row)


def _require_member(project_id: int, user_id: int) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM project_members WHERE project_id = ? AND user_id = ?",
        (project_id, user_id),
    )
    member = cursor.fetchone()
    conn.close()
    if not member:
        raise HTTPException(status_code=403, detail="Not a project member")
    return _row_to_dict(member)


def _get_project(project_id: int) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM collaboration_projects WHERE id = ?", (project_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    return _row_to_dict(row)


def get_project_sections(project_id: int) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM project_sections
        WHERE project_id = ?
        ORDER BY template_order ASC
        """,
        (project_id,),
    )
    rows = [_row_to_dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def create_project(
    user_id: int,
    name: str,
    description: str,
    template_id: int,
    base_document_path: Optional[str] = None,
    base_document_filename: Optional[str] = None,
) -> Dict[str, Any]:
    tmpl = get_template_by_id(template_id)
    if not tmpl:
        raise HTTPException(status_code=400, detail="Template not found")

    user = _get_user(user_id)
    invite_code = generate_invite_code()
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO collaboration_projects
        (name, description, template_id, created_by, invite_code,
         base_document_path, base_document_filename)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name, description, template_id, user_id, invite_code,
            base_document_path, base_document_filename,
        ),
    )
    project_id = cursor.lastrowid

    cursor.execute(
        "INSERT INTO project_members (project_id, user_id, role) VALUES (?, ?, 'owner')",
        (project_id, user_id),
    )

    template_sections = parse_template_sections(tmpl.get("required_sections", []))
    for sec in template_sections:
        cursor.execute(
            """
            INSERT INTO project_sections
            (project_id, section_id, section_name, template_order, heading_level)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                project_id,
                sec["section_id"],
                sec["section_name"],
                sec["template_order"],
                sec["heading_level"],
            ),
        )

    conn.commit()
    conn.close()

    base_document_id: Optional[int] = None
    permanent_doc_path = base_document_path
    reports_sync: Optional[Dict[str, Any]] = None

    if base_document_path and os.path.exists(base_document_path):
        project_dir = os.path.join(VC_UPLOAD_DIR, f"project_{project_id}")
        os.makedirs(project_dir, exist_ok=True)
        permanent_doc_path = os.path.join(
            project_dir, f"base_{uuid.uuid4().hex[:8]}.docx",
        )
        shutil.copy2(base_document_path, permanent_doc_path)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE collaboration_projects
            SET base_document_path = ?, base_document_filename = ?
            WHERE id = ?
            """,
            (permanent_doc_path, base_document_filename, project_id),
        )
        conn.commit()
        conn.close()

        _seed_sections_from_docx(
            project_id, user_id, permanent_doc_path, template_sections,
        )
        reports_sync = sync_project_to_member_reports(project_id)
        if reports_sync and user_id in reports_sync.get("member_documents", {}):
            base_document_id = reports_sync["member_documents"][user_id]

    return {
        "id": project_id,
        "name": name,
        "description": description,
        "template_id": template_id,
        "template_name": tmpl.get("name"),
        "created_by": user_id,
        "owner_name": user.get("username"),
        "invite_code": invite_code,
        "status": "active",
        "base_document_id": base_document_id,
        "base_document_path": permanent_doc_path,
        "reports_sync": reports_sync,
        "sections": get_sections_with_latest(project_id),
    }


def _seed_sections_from_docx(
    project_id: int,
    user_id: int,
    docx_path: str,
    template_sections: List[Dict[str, Any]],
) -> None:
    """Parse uploaded DOCX and create version-1 commits for each section with content."""
    section_contents = extract_sections_from_docx(docx_path, template_sections)
    user = _get_user(user_id)
    author_name = user.get("username") or f"user_{user_id}"

    conn = get_db()
    cursor = conn.cursor()
    for sec in template_sections:
        sid = sec["section_id"]
        content = (section_contents.get(sid) or "").strip()
        if not content:
            continue
        cursor.execute(
            """
            INSERT INTO section_commits
            (project_id, section_id, author_id, author_name, version_number, content,
             commit_type, message)
            VALUES (?, ?, ?, ?, 1, ?, 'import', 'Initial document import')
            """,
            (project_id, sid, user_id, author_name, content),
        )
    conn.commit()
    conn.close()


def create_project_with_document(
    user_id: int,
    name: str,
    description: str,
    template_id: int,
    docx_path: Optional[str] = None,
    original_filename: Optional[str] = None,
) -> Dict[str, Any]:
    return create_project(
        user_id,
        name,
        description,
        template_id,
        base_document_path=docx_path,
        base_document_filename=original_filename,
    )


def get_project_history(project_id: int, user_id: int) -> List[Dict[str, Any]]:
    """All commits across every section, chronological order."""
    _require_member(project_id, user_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT c.*, s.section_name
        FROM section_commits c
        JOIN project_sections s
          ON s.project_id = c.project_id AND s.section_id = c.section_id
        WHERE c.project_id = ?
        ORDER BY c.created_at ASC, c.id ASC
        """,
        (project_id,),
    )
    rows = [_row_to_dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def list_section_images(project_id: int, section_id: str, user_id: int) -> List[Dict[str, Any]]:
    _require_member(project_id, user_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, project_id, section_id, filename, file_path, uploaded_by, created_at
        FROM section_images
        WHERE project_id = ? AND section_id = ?
        ORDER BY created_at ASC
        """,
        (project_id, section_id),
    )
    rows = [_row_to_dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def upload_section_image(
    project_id: int,
    section_id: str,
    user_id: int,
    upload: UploadFile,
) -> Dict[str, Any]:
    _require_member(project_id, user_id)
    sections = get_project_sections(project_id)
    if not any(s["section_id"] == section_id for s in sections):
        raise HTTPException(status_code=404, detail="Section not found")

    filename = upload.filename or "image.png"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported image format")

    img_dir = os.path.join(VC_UPLOAD_DIR, f"project_{project_id}", "images", section_id)
    os.makedirs(img_dir, exist_ok=True)
    dest = os.path.join(img_dir, f"{uuid.uuid4().hex[:8]}{ext}")

    with open(dest, "wb") as f:
        shutil.copyfileobj(upload.file, f)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO section_images (project_id, section_id, filename, file_path, uploaded_by)
        VALUES (?, ?, ?, ?, ?)
        """,
        (project_id, section_id, filename, dest, user_id),
    )
    image_id = cursor.lastrowid
    conn.commit()
    cursor.execute("SELECT * FROM section_images WHERE id = ?", (image_id,))
    row = _row_to_dict(cursor.fetchone())
    conn.close()
    sync_project_to_member_reports(project_id)
    return row


def delete_section_image(project_id: int, section_id: str, image_id: int, user_id: int) -> None:
    _require_member(project_id, user_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM section_images
        WHERE id = ? AND project_id = ? AND section_id = ?
        """,
        (image_id, project_id, section_id),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Image not found")

    file_path = row["file_path"]
    cursor.execute("DELETE FROM section_images WHERE id = ?", (image_id,))
    conn.commit()
    conn.close()

    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass

    sync_project_to_member_reports(project_id)


def get_section_image_path(project_id: int, section_id: str, image_id: int, user_id: int) -> str:
    _require_member(project_id, user_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT file_path FROM section_images
        WHERE id = ? AND project_id = ? AND section_id = ?
        """,
        (image_id, project_id, section_id),
    )
    row = cursor.fetchone()
    conn.close()
    if not row or not row["file_path"] or not os.path.exists(row["file_path"]):
        raise HTTPException(status_code=404, detail="Image not found")
    return row["file_path"]


def get_section_images_map(project_id: int) -> Dict[str, List[str]]:
    """Return section_id -> list of image file paths for merge assembly."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT section_id, file_path FROM section_images
        WHERE project_id = ?
        ORDER BY section_id, created_at ASC
        """,
        (project_id,),
    )
    result: Dict[str, List[str]] = {}
    for row in cursor.fetchall():
        sid = row["section_id"]
        result.setdefault(sid, []).append(row["file_path"])
    conn.close()
    return result


def list_user_projects(user_id: int) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT p.*, t.name AS template_name, u.username AS owner_name,
               (SELECT COUNT(*) FROM project_members pm WHERE pm.project_id = p.id) AS member_count
        FROM collaboration_projects p
        JOIN project_members m ON m.project_id = p.id
        JOIN templates t ON t.id = p.template_id
        JOIN users u ON u.id = p.created_by
        WHERE m.user_id = ?
        ORDER BY p.created_at DESC
        """,
        (user_id,),
    )
    rows = [_row_to_dict(r) for r in cursor.fetchall()]
    conn.close()

    for row in rows:
        ensure_project_reports_synced(int(row["id"]))

    return rows


def get_project_detail(project_id: int, user_id: int) -> Dict[str, Any]:
    _require_member(project_id, user_id)
    ensure_project_reports_synced(project_id)
    project = _get_project(project_id)
    tmpl = get_template_by_id(project["template_id"]) or {}
    project["template_name"] = tmpl.get("name")
    project["sections"] = get_sections_with_latest(project_id)
    project["members"] = list_project_members(project_id)
    return project


def list_project_members(project_id: int) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT m.*, u.username, u.email
        FROM project_members m
        JOIN users u ON u.id = m.user_id
        WHERE m.project_id = ?
        ORDER BY m.role DESC, m.joined_at ASC
        """,
        (project_id,),
    )
    rows = [_row_to_dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def join_project_by_invite(user_id: int, invite_code: str) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM collaboration_projects WHERE UPPER(invite_code) = UPPER(?)",
        (invite_code.strip(),),
    )
    project = cursor.fetchone()
    if not project:
        conn.close()
        raise HTTPException(status_code=404, detail="Invalid invite code")

    project_id = project["id"]
    cursor.execute(
        "SELECT id FROM project_members WHERE project_id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO project_members (project_id, user_id, role) VALUES (?, ?, 'editor')",
            (project_id, user_id),
        )
        conn.commit()

    conn.close()
    sync_project_to_member_reports(project_id)
    return get_project_detail(project_id, user_id)


def invite_member_by_email(project_id: int, inviter_id: int, email: str) -> Dict[str, Any]:
    _require_member(project_id, inviter_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),))
    user = cursor.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found with that email")

    cursor.execute(
        "SELECT id FROM project_members WHERE project_id = ? AND user_id = ?",
        (project_id, user["id"]),
    )
    if cursor.fetchone():
        conn.close()
        return {"status": "already_member", "user_id": user["id"], "username": user["username"]}

    cursor.execute(
        "INSERT INTO project_members (project_id, user_id, role) VALUES (?, ?, 'editor')",
        (project_id, user["id"]),
    )
    conn.commit()
    conn.close()
    sync_project_to_member_reports(project_id)
    return {"status": "invited", "user_id": user["id"], "username": user["username"]}


def _next_version(project_id: int, section_id: str) -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COALESCE(MAX(version_number), 0) FROM section_commits WHERE project_id = ? AND section_id = ?",
        (project_id, section_id),
    )
    current = cursor.fetchone()[0]
    conn.close()
    return int(current) + 1


def create_commit(
    project_id: int,
    section_id: str,
    user_id: int,
    content: str,
    message: str = "",
    commit_type: str = "save",
    parent_commit_id: Optional[int] = None,
) -> Dict[str, Any]:
    _require_member(project_id, user_id)
    user = _get_user(user_id)

    sections = get_project_sections(project_id)
    if not any(s["section_id"] == section_id for s in sections):
        raise HTTPException(status_code=404, detail="Section not found")

    version = _next_version(project_id, section_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO section_commits
        (project_id, section_id, author_id, author_name, version_number, content,
         commit_type, parent_commit_id, message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            section_id,
            user_id,
            user.get("username") or f"user_{user_id}",
            version,
            content,
            commit_type,
            parent_commit_id,
            message,
        ),
    )
    commit_id = cursor.lastrowid
    conn.commit()

    cursor.execute("SELECT * FROM section_commits WHERE id = ?", (commit_id,))
    row = _row_to_dict(cursor.fetchone())
    conn.close()

    sync_project_to_member_reports(project_id)
    return row


def get_section_history(project_id: int, section_id: str, user_id: int) -> List[Dict[str, Any]]:
    _require_member(project_id, user_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM section_commits
        WHERE project_id = ? AND section_id = ?
        ORDER BY version_number DESC, created_at DESC
        """,
        (project_id, section_id),
    )
    rows = [_row_to_dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def rollback_section(project_id: int, section_id: str, user_id: int, commit_id: int) -> Dict[str, Any]:
    _require_member(project_id, user_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM section_commits WHERE id = ? AND project_id = ? AND section_id = ?",
        (commit_id, project_id, section_id),
    )
    target = cursor.fetchone()
    conn.close()
    if not target:
        raise HTTPException(status_code=404, detail="Commit not found")

    return create_commit(
        project_id=project_id,
        section_id=section_id,
        user_id=user_id,
        content=target["content"],
        message=f"Rollback to version {target['version_number']}",
        commit_type="rollback",
        parent_commit_id=commit_id,
    )


def get_latest_content_map(project_id: int) -> Dict[str, Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT c.*, s.section_name, s.template_order, s.heading_level
        FROM section_commits c
        INNER JOIN (
            SELECT section_id, MAX(created_at) AS max_created
            FROM section_commits WHERE project_id = ?
            GROUP BY section_id
        ) latest ON c.section_id = latest.section_id AND c.created_at = latest.max_created
        JOIN project_sections s ON s.project_id = c.project_id AND s.section_id = c.section_id
        WHERE c.project_id = ?
        """,
        (project_id, project_id),
    )
    rows = [_row_to_dict(r) for r in cursor.fetchall()]
    conn.close()

    result: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        result[row["section_id"]] = {
            "section_name": row["section_name"],
            "content": row["content"],
            "author_name": row["author_name"],
            "version_number": row["version_number"],
            "updated_at": row["created_at"],
        }
    return result


def get_sections_with_latest(project_id: int) -> List[Dict[str, Any]]:
    sections = get_project_sections(project_id)
    latest = get_latest_content_map(project_id)
    conn = get_db()
    cursor = conn.cursor()

    enriched: List[Dict[str, Any]] = []
    for sec in sections:
        sid = sec["section_id"]
        lat = latest.get(sid, {})
        cursor.execute(
            "SELECT COUNT(*) FROM section_commits WHERE project_id = ? AND section_id = ?",
            (project_id, sid),
        )
        count = cursor.fetchone()[0]
        enriched.append({
            **sec,
            "latest_content": lat.get("content", ""),
            "latest_version": lat.get("version_number", 0),
            "latest_author": lat.get("author_name", ""),
            "latest_updated_at": lat.get("updated_at"),
            "commit_count": count,
        })

    conn.close()
    return enriched


def start_merge(project_id: int, user_id: int) -> Dict[str, Any]:
    _require_member(project_id, user_id)
    project = _get_project(project_id)
    sections = get_project_sections(project_id)
    latest_map = get_latest_content_map(project_id)

    section_contents = {
        sid: {
            "section_name": data["section_name"],
            "content": data.get("content", ""),
        }
        for sid, data in latest_map.items()
    }
    for sec in sections:
        sid = sec["section_id"]
        section_contents.setdefault(sid, {"section_name": sec["section_name"], "content": ""})

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO project_merges (project_id, initiated_by, status)
        VALUES (?, ?, 'detecting')
        """,
        (project_id, user_id),
    )
    merge_id = cursor.lastrowid
    conn.commit()
    conn.close()

    conflicts = detect_all_conflicts(
        project_id,
        sections,
        section_contents,
        project.get("last_merge_at"),
    )
    stored = store_conflicts(merge_id, conflicts)

    status = "conflicts" if stored else "ready"
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE project_merges SET status = ? WHERE id = ?", (status, merge_id))
    conn.commit()
    conn.close()

    return {
        "merge_id": merge_id,
        "status": status,
        "conflict_count": len(stored),
        "conflicts": [
            {
                "id": c["id"],
                "conflict_type": c["conflict_type"],
                "section_id": c.get("section_id"),
                "section_name": c.get("section_name"),
                "related_section_id": c.get("related_section_id"),
                "related_section_name": c.get("related_section_name"),
                "details": c["details"],
                "status": c["status"],
            }
            for c in stored
        ],
        "sections_preview": [
            {
                "section_id": s["section_id"],
                "section_name": s["section_name"],
                "content": section_contents.get(s["section_id"], {}).get("content", ""),
            }
            for s in sections
        ],
    }


def get_merge_status(project_id: int, merge_id: int, user_id: int) -> Dict[str, Any]:
    _require_member(project_id, user_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM project_merges WHERE id = ? AND project_id = ?",
        (merge_id, project_id),
    )
    merge = cursor.fetchone()
    if not merge:
        conn.close()
        raise HTTPException(status_code=404, detail="Merge not found")

    cursor.execute(
        "SELECT * FROM merge_conflicts WHERE merge_id = ? ORDER BY id ASC",
        (merge_id,),
    )
    conflicts = []
    for row in cursor.fetchall():
        item = _row_to_dict(row)
        item["details"] = json.loads(item.get("details") or "{}")
        conflicts.append(item)

    conn.close()
    pending = sum(1 for c in conflicts if c["status"] == "pending")
    return {
        "merge_id": merge_id,
        "status": merge["status"],
        "conflict_count": len(conflicts),
        "pending_conflicts": pending,
        "conflicts": conflicts,
        "merged_file_path": merge.get("merged_file_path"),
        "document_id": merge.get("document_id"),
        "analysis_report": json.loads(merge["analysis_report"]) if merge.get("analysis_report") else None,
    }


def resolve_conflict(
    project_id: int,
    merge_id: int,
    conflict_id: int,
    user_id: int,
    resolution_content: str,
) -> Dict[str, Any]:
    _require_member(project_id, user_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM merge_conflicts WHERE id = ? AND merge_id = ?",
        (conflict_id, merge_id),
    )
    conflict = cursor.fetchone()
    if not conflict:
        conn.close()
        raise HTTPException(status_code=404, detail="Conflict not found")

    cursor.execute(
        """
        UPDATE merge_conflicts
        SET resolution_content = ?, resolved_by = ?, resolved_at = CURRENT_TIMESTAMP, status = 'resolved'
        WHERE id = ?
        """,
        (resolution_content, user_id, conflict_id),
    )

    cursor.execute(
        "SELECT COUNT(*) FROM merge_conflicts WHERE merge_id = ? AND status = 'pending'",
        (merge_id,),
    )
    pending = cursor.fetchone()[0]
    new_status = "ready" if pending == 0 else "conflicts"
    cursor.execute("UPDATE project_merges SET status = ? WHERE id = ?", (new_status, merge_id))
    conn.commit()
    conn.close()

    return {
        "conflict_id": conflict_id,
        "status": "resolved",
        "merge_status": new_status,
        "pending_conflicts": pending,
    }


async def complete_merge(
    project_id: int,
    merge_id: int,
    user_id: int,
    run_analysis_fn,
) -> Dict[str, Any]:
    _require_member(project_id, user_id)
    merge_status = get_merge_status(project_id, merge_id, user_id)
    if merge_status["pending_conflicts"] > 0:
        raise HTTPException(status_code=400, detail="Resolve all conflicts before completing merge")

    project = _get_project(project_id)
    sections = get_project_sections(project_id)
    latest_map = get_latest_content_map(project_id)
    latest_by_section = {sid: d.get("content", "") for sid, d in latest_map.items()}

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM merge_conflicts WHERE merge_id = ?", (merge_id,))
    conflicts = []
    for row in cursor.fetchall():
        item = _row_to_dict(row)
        item["details"] = json.loads(item.get("details") or "{}")
        conflicts.append(item)
    conn.close()

    final_content = resolve_section_content_map(sections, latest_by_section, conflicts)

    merged_dir = os.path.join(VC_UPLOAD_DIR, f"project_{project_id}")
    os.makedirs(merged_dir, exist_ok=True)
    merged_path = os.path.join(merged_dir, f"merged_{merge_id}.docx")

    section_images = get_section_images_map(project_id)
    assemble_merged_docx(
        sections, final_content, merged_path, project["template_id"], section_images
    )

    document_id = create_merged_document_record(
        project_id,
        user_id,
        project["template_id"],
        merged_path,
        project["name"],
    )

    analysis_report = None
    try:
        analysis_report = await run_analysis_fn(
            template_id=str(project["template_id"]),
            saved_path=merged_path,
            text=None,
            filename=f"{project['name']}_merged.docx",
            job_id=str(document_id),
        )
    except Exception as exc:
        analysis_report = {"error": str(exc)}

    update_merge_completed(merge_id, project_id, merged_path, document_id, analysis_report)

    return {
        "merge_id": merge_id,
        "status": "completed",
        "document_id": document_id,
        "merged_file_path": merged_path,
        "download_url": f"/api/vc/projects/{project_id}/download?merge_id={merge_id}",
        "analysis_report": analysis_report,
    }
