"""
super_admin_routes.py — Platform Super Admin: manage all organizations.

Protected by X-Super-Admin-Key header (SUPER_ADMIN_KEY env / .env).
"""

from __future__ import annotations

import secrets
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query

from database import get_db, hash_password
from middleware.org_middleware import get_super_admin_key

router = APIRouter(prefix="/api/super-admin", tags=["Super Admin"])


def _require_super_admin(
    x_super_admin_key: Annotated[Optional[str], Header()] = None,
) -> None:
    expected = get_super_admin_key()
    if not x_super_admin_key or x_super_admin_key.strip() != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Super-Admin-Key.")


def _org_dict(row) -> dict[str, Any]:
    """Client-facing org dict — api_key stays backend-internal (never returned)."""
    return {
        "id": int(row["id"]),
        "name": row["name"] or "",
        "code": row["code"] or "",
        "type": row["type"] or "university",
        "plan": row["plan"] or "university",
        "modules": row["modules"] or "core",
        "modules_list": [m.strip() for m in (row["modules"] or "core").split(",") if m.strip()],
        "documents_used": int(row["documents_used"] or 0),
        "documents_limit": int(row["documents_limit"] or 999999),
        "is_active": bool(row["is_active"]),
        "primary_color": row["primary_color"] or "#7B61FF",
        "logo_url": row["logo_url"],
        "created_at": row["created_at"] or "",
    }


def _sync_org_modules(cursor, org_id: int, modules_csv: str) -> None:
    cursor.execute("DELETE FROM organization_modules WHERE org_id = ?", (org_id,))
    for mod in [m.strip() for m in modules_csv.split(",") if m.strip()]:
        cursor.execute(
            """
            INSERT INTO organization_modules (org_id, module_name, is_enabled)
            VALUES (?, ?, 1)
            """,
            (org_id, mod),
        )


@router.get("/organizations")
def list_organizations(_: None = Depends(_require_super_admin)):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM organizations ORDER BY id ASC")
        rows = [_org_dict(r) for r in cursor.fetchall()]
        return {"organizations": rows, "count": len(rows)}
    finally:
        conn.close()


@router.get("/admins")
def list_admins(_: None = Depends(_require_super_admin)):
    """
    All org-level admin users across every organization.
    Role filter: users.role = 'admin' only
    (other roles in the schema are 'student' and 'supervisor').
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT
                u.username AS name,
                u.email AS email,
                u.role AS role,
                u.org_id AS org_id,
                o.name AS org_name,
                o.code AS org_code
            FROM users u
            JOIN organizations o ON o.id = u.org_id
            WHERE LOWER(u.role) = 'admin'
            ORDER BY o.name ASC, u.username ASC
            """
        )
        rows = []
        for r in cursor.fetchall():
            rows.append(
                {
                    "name": r["name"] or "",
                    "email": r["email"] or "",
                    "role": r["role"] or "admin",
                    "org_id": int(r["org_id"]) if r["org_id"] is not None else None,
                    "org_name": r["org_name"] or "",
                    "org_code": r["org_code"] or "",
                }
            )
        return {"admins": rows, "count": len(rows)}
    finally:
        conn.close()


@router.post("/organizations")
def create_organization(
    payload: dict[str, Any] = Body(default_factory=dict),
    _: None = Depends(_require_super_admin),
):
    """
    Create organization + optional first Org Admin account.
    Always returns the generated API key on the organization object.
    """
    name = (payload.get("name") or "").strip()
    code = (payload.get("code") or "").strip().upper()
    org_type = (payload.get("type") or "university").strip()
    plan = (payload.get("plan") or "university").strip()
    modules = payload.get("modules") or "core,fyp"
    if isinstance(modules, list):
        modules = ",".join(str(m).strip() for m in modules if str(m).strip())
    modules = str(modules).strip() or "core"
    primary_color = (payload.get("primary_color") or "#7B61FF").strip()
    documents_limit = int(payload.get("documents_limit") or 999999)

    if not name or not code:
        raise HTTPException(status_code=400, detail="name and code are required.")

    admin_name = (payload.get("admin_name") or payload.get("adminName") or "").strip()
    admin_email = (payload.get("admin_email") or payload.get("adminEmail") or "").strip().lower()
    admin_password = (payload.get("admin_password") or payload.get("adminPassword") or "").strip()
    auto_password = False
    if admin_email and not admin_password:
        admin_password = "Fmt@" + secrets.token_hex(4)
        auto_password = True
    if admin_email and not admin_name:
        admin_name = admin_email.split("@")[0]

    api_key = "fmt_live_" + secrets.token_urlsafe(16)

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO organizations
                (name, code, type, api_key, plan, modules, documents_limit, is_active, primary_color)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (name, code, org_type, api_key, plan, modules, documents_limit, primary_color),
        )
        org_id = int(cursor.lastrowid)
        _sync_org_modules(cursor, org_id, modules)

        admin_payload = None
        if admin_email:
            cursor.execute(
                "SELECT id FROM users WHERE LOWER(email) = ? AND org_id = ?",
                (admin_email, org_id),
            )
            if cursor.fetchone():
                raise HTTPException(
                    status_code=409,
                    detail="Admin email already exists for this organization.",
                )
            cursor.execute(
                """
                INSERT INTO users (username, email, password_hash, role, university_id, org_id)
                VALUES (?, ?, ?, 'admin', 1, ?)
                """,
                (admin_name, admin_email, hash_password(admin_password), org_id),
            )
            admin_id = int(cursor.lastrowid)
            admin_payload = {
                "id": admin_id,
                "name": admin_name,
                "email": admin_email,
                "role": "admin",
                "password": admin_password,
                "password_auto_generated": auto_password,
            }

        conn.commit()
        cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
        org = _org_dict(cursor.fetchone())
        return {
            "success": True,
            "organization": org,
            "org_code": org.get("code"),
            "admin": admin_payload,
            "message": (
                "Organization and admin created. Share org_code + admin credentials only."
                if admin_payload
                else "Organization created. Add an admin later or use signup."
            ),
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        if "UNIQUE" in str(exc).upper():
            raise HTTPException(status_code=409, detail="Organization code or API key already exists.")
        raise HTTPException(status_code=500, detail=f"Could not create organization: {exc}")
    finally:
        conn.close()


@router.put("/organizations/{org_id}")
def update_organization(
    org_id: int,
    payload: dict[str, Any] = Body(default_factory=dict),
    _: None = Depends(_require_super_admin),
):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found.")

        name = (payload.get("name") if payload.get("name") is not None else row["name"]) or ""
        code = (payload.get("code") if payload.get("code") is not None else row["code"]) or ""
        org_type = payload.get("type") if payload.get("type") is not None else row["type"]
        plan = payload.get("plan") if payload.get("plan") is not None else row["plan"]
        modules = payload.get("modules") if payload.get("modules") is not None else row["modules"]
        if isinstance(modules, list):
            modules = ",".join(str(m).strip() for m in modules if str(m).strip())
        primary_color = (
            payload.get("primary_color")
            if payload.get("primary_color") is not None
            else row["primary_color"]
        )
        documents_limit = (
            int(payload["documents_limit"])
            if payload.get("documents_limit") is not None
            else int(row["documents_limit"] or 999999)
        )
        logo_url = payload.get("logo_url") if "logo_url" in payload else row["logo_url"]

        cursor.execute(
            """
            UPDATE organizations
            SET name = ?, code = ?, type = ?, plan = ?, modules = ?,
                documents_limit = ?, primary_color = ?, logo_url = ?
            WHERE id = ?
            """,
            (
                str(name).strip(),
                str(code).strip().upper(),
                str(org_type).strip(),
                str(plan).strip(),
                str(modules).strip(),
                documents_limit,
                str(primary_color or "#7B61FF").strip(),
                logo_url,
                org_id,
            ),
        )
        _sync_org_modules(cursor, org_id, str(modules))
        conn.commit()
        cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
        return {"success": True, "organization": _org_dict(cursor.fetchone())}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        if "UNIQUE" in str(exc).upper():
            raise HTTPException(status_code=409, detail="Organization code already exists.")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()


@router.patch("/organizations/{org_id}/toggle")
def toggle_organization(org_id: int, _: None = Depends(_require_super_admin)):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, is_active FROM organizations WHERE id = ?", (org_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found.")
        if org_id == 1 and row["is_active"]:
            # Allow toggle off of default? Safer to allow but warn — user asked for toggle
            pass
        new_val = 0 if row["is_active"] else 1
        cursor.execute("UPDATE organizations SET is_active = ? WHERE id = ?", (new_val, org_id))
        conn.commit()
        cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
        return {"success": True, "organization": _org_dict(cursor.fetchone())}
    finally:
        conn.close()


@router.delete("/organizations/{org_id}")
def delete_organization(org_id: int, _: None = Depends(_require_super_admin)):
    if org_id == 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the default organization (id=1).",
        )
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, code FROM organizations WHERE id = ?", (org_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found.")

        summary = _purge_organization_data(cursor, org_id)
        cursor.execute("DELETE FROM organizations WHERE id = ?", (org_id,))
        conn.commit()
        return {
            "success": True,
            "deleted_id": org_id,
            "org_code": row["code"],
            "purged": summary,
        }
    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete organization and related data: {exc}",
        ) from exc
    finally:
        conn.close()


def _table_exists(cursor, table: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    )
    return cursor.fetchone() is not None


def _table_has_column(cursor, table: str, column: str) -> bool:
    if not _table_exists(cursor, table):
        return False
    cursor.execute(f"PRAGMA table_info({table})")
    return column in {row[1] for row in cursor.fetchall()}


def _safe_ids(cursor, sql: str, params: tuple) -> list[int]:
    try:
        cursor.execute(sql, params)
        return [int(r[0]) for r in cursor.fetchall() if r[0] is not None]
    except Exception:
        return []


def _safe_delete(cursor, sql: str, params: tuple = ()) -> int:
    try:
        cursor.execute(sql, params)
        return int(cursor.rowcount or 0)
    except Exception:
        return 0


def _purge_organization_data(cursor, org_id: int) -> dict[str, int]:
    """
    Hard-delete every tenant-owned row for this org (users, docs, FYP,
    templates, collaboration, settings). Call before deleting organizations.
    """
    summary: dict[str, int] = {}

    user_ids = _safe_ids(cursor, "SELECT id FROM users WHERE org_id = ?", (org_id,))
    user_emails = []
    if user_ids:
        uph = ",".join("?" * len(user_ids))
        try:
            cursor.execute(
                f"SELECT LOWER(email) FROM users WHERE id IN ({uph})",
                tuple(user_ids),
            )
            user_emails = [str(r[0]) for r in cursor.fetchall() if r[0]]
        except Exception:
            user_emails = []

    group_ids = (
        _safe_ids(cursor, "SELECT id FROM fyp_groups WHERE org_id = ?", (org_id,))
        if _table_has_column(cursor, "fyp_groups", "org_id")
        else []
    )

    doc_ids: list[int] = []
    if _table_has_column(cursor, "documents", "org_id"):
        doc_ids.extend(
            _safe_ids(cursor, "SELECT id FROM documents WHERE org_id = ?", (org_id,))
        )
    if user_ids:
        uph = ",".join("?" * len(user_ids))
        doc_ids.extend(
            _safe_ids(
                cursor,
                f"SELECT id FROM documents WHERE user_id IN ({uph})",
                tuple(user_ids),
            )
        )
    doc_ids = list(dict.fromkeys(doc_ids))

    project_ids: list[int] = []
    if _table_has_column(cursor, "collaboration_projects", "org_id"):
        project_ids.extend(
            _safe_ids(
                cursor,
                "SELECT id FROM collaboration_projects WHERE org_id = ?",
                (org_id,),
            )
        )
    if user_ids and _table_exists(cursor, "collaboration_projects"):
        uph = ",".join("?" * len(user_ids))
        project_ids.extend(
            _safe_ids(
                cursor,
                f"SELECT id FROM collaboration_projects WHERE created_by IN ({uph})",
                tuple(user_ids),
            )
        )
    project_ids = list(dict.fromkeys(project_ids))

    # ── Collaboration ──────────────────────────────────────────────────────
    if project_ids:
        pph = ",".join("?" * len(project_ids))
        ppt = tuple(project_ids)
        merge_ids = _safe_ids(
            cursor,
            f"SELECT id FROM project_merges WHERE project_id IN ({pph})",
            ppt,
        )
        if merge_ids:
            mph = ",".join("?" * len(merge_ids))
            summary["merge_conflicts"] = _safe_delete(
                cursor,
                f"DELETE FROM merge_conflicts WHERE merge_id IN ({mph})",
                tuple(merge_ids),
            )
        for table in (
            "project_merges",
            "section_commits",
            "section_images",
            "project_sections",
            "project_members",
            "project_member_documents",
        ):
            summary[table] = _safe_delete(
                cursor, f"DELETE FROM {table} WHERE project_id IN ({pph})", ppt
            )
        summary["collaboration_projects"] = _safe_delete(
            cursor,
            f"DELETE FROM collaboration_projects WHERE id IN ({pph})",
            ppt,
        )

    # ── Upload documents (main documents table) ────────────────────────────
    if doc_ids:
        dph = ",".join("?" * len(doc_ids))
        dpt = tuple(doc_ids)
        summary["image_analysis"] = _safe_delete(
            cursor, f"DELETE FROM image_analysis WHERE document_id IN ({dph})", dpt
        )
        summary["project_member_documents"] = summary.get(
            "project_member_documents", 0
        ) + _safe_delete(
            cursor,
            f"DELETE FROM project_member_documents WHERE document_id IN ({dph})",
            dpt,
        )
        if _table_has_column(cursor, "final_submissions", "source_document_id"):
            summary["final_submissions"] = _safe_delete(
                cursor,
                f"DELETE FROM final_submissions WHERE source_document_id IN ({dph})",
                dpt,
            )
        if _table_has_column(cursor, "group_documents", "source_document_id"):
            # Clean review paragraphs/comments for group docs linked to these uploads
            gd_ids = _safe_ids(
                cursor,
                f"SELECT id FROM group_documents WHERE source_document_id IN ({dph})",
                dpt,
            )
            if gd_ids:
                gdh = ",".join("?" * len(gd_ids))
                gdt = tuple(gd_ids)
                para_ids = _safe_ids(
                    cursor,
                    f"SELECT id FROM document_paragraphs WHERE document_id IN ({gdh})",
                    gdt,
                )
                if para_ids:
                    pah = ",".join("?" * len(para_ids))
                    summary["document_comments"] = _safe_delete(
                        cursor,
                        f"DELETE FROM document_comments WHERE paragraph_id IN ({pah})",
                        tuple(para_ids),
                    )
                summary["document_paragraphs"] = _safe_delete(
                    cursor,
                    f"DELETE FROM document_paragraphs WHERE document_id IN ({gdh})",
                    gdt,
                )
                summary["document_comments"] = summary.get("document_comments", 0) + _safe_delete(
                    cursor,
                    f"DELETE FROM document_comments WHERE document_id IN ({gdh})",
                    gdt,
                )
                summary["group_documents"] = _safe_delete(
                    cursor,
                    f"DELETE FROM group_documents WHERE id IN ({gdh})",
                    gdt,
                )
        summary["documents"] = _safe_delete(
            cursor, f"DELETE FROM documents WHERE id IN ({dph})", dpt
        )

    # ── FYP groups + children ──────────────────────────────────────────────
    if group_ids:
        gph = ",".join("?" * len(group_ids))
        gpt = tuple(group_ids)
        gd_ids = _safe_ids(
            cursor,
            f"SELECT id FROM group_documents WHERE group_id IN ({gph})",
            gpt,
        )
        if gd_ids:
            gdh = ",".join("?" * len(gd_ids))
            gdt = tuple(gd_ids)
            para_ids = _safe_ids(
                cursor,
                f"SELECT id FROM document_paragraphs WHERE document_id IN ({gdh})",
                gdt,
            )
            if para_ids:
                pah = ",".join("?" * len(para_ids))
                summary["document_comments"] = summary.get("document_comments", 0) + _safe_delete(
                    cursor,
                    f"DELETE FROM document_comments WHERE paragraph_id IN ({pah})",
                    tuple(para_ids),
                )
            summary["document_paragraphs"] = summary.get("document_paragraphs", 0) + _safe_delete(
                cursor,
                f"DELETE FROM document_paragraphs WHERE document_id IN ({gdh})",
                gdt,
            )
            summary["document_comments"] = summary.get("document_comments", 0) + _safe_delete(
                cursor,
                f"DELETE FROM document_comments WHERE document_id IN ({gdh})",
                gdt,
            )

        for table, col in (
            ("group_documents", "group_id"),
            ("group_replies", "group_id"),
            ("group_milestones", "group_id"),
            ("meeting_notes", "group_id"),
            ("remarks", "group_id"),
            ("final_submissions", "group_id"),
            ("assignment_requests", "fyp_group_id"),
        ):
            summary[table] = summary.get(table, 0) + _safe_delete(
                cursor, f"DELETE FROM {table} WHERE {col} IN ({gph})", gpt
            )

    # ── Notifications (by user_id or email) ────────────────────────────────
    if user_ids:
        uph = ",".join("?" * len(user_ids))
        summary["notifications"] = _safe_delete(
            cursor,
            f"DELETE FROM notifications WHERE user_id IN ({uph})",
            tuple(user_ids),
        )
    if user_emails and _table_has_column(cursor, "notifications", "recipient_email"):
        eph = ",".join("?" * len(user_emails))
        summary["notifications"] = summary.get("notifications", 0) + _safe_delete(
            cursor,
            f"DELETE FROM notifications WHERE LOWER(recipient_email) IN ({eph})",
            tuple(user_emails),
        )

    # ── Direct org_id tables (catch-all) ────────────────────────────────────
    for table in (
        "organization_modules",
        "assignment_requests",
        "final_submissions",
        "meeting_notes",
        "fyp_groups",
        "deadlines",
        "semester_deadlines",
        "supervisors",
        "templates",
        "departments",
        "documents",
        "collaboration_projects",
        "users",
    ):
        if _table_has_column(cursor, table, "org_id"):
            summary[table] = summary.get(table, 0) + _safe_delete(
                cursor, f"DELETE FROM {table} WHERE org_id = ?", (org_id,)
            )

    # Per-org admin settings: org:{id}:*
    if _table_exists(cursor, "admin_settings"):
        summary["admin_settings"] = _safe_delete(
            cursor,
            "DELETE FROM admin_settings WHERE key LIKE ?",
            (f"org:{org_id}:%",),
        )

    # Keep only non-zero counts for response clarity
    return {k: v for k, v in summary.items() if v}


@router.get("/organizations/{org_id}/stats")
def organization_stats(org_id: int, _: None = Depends(_require_super_admin)):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found.")
        org = _org_dict(row)

        # Soft counts — tables may lack org_id on very old DBs; fall back carefully
        def _count(sql: str, params: tuple = ()) -> int:
            try:
                cursor.execute(sql, params)
                return int(cursor.fetchone()[0] or 0)
            except Exception:
                return 0

        users = _count("SELECT COUNT(*) FROM users WHERE org_id = ?", (org_id,))
        supervisors = _count("SELECT COUNT(*) FROM supervisors WHERE org_id = ?", (org_id,))
        groups = _count("SELECT COUNT(*) FROM fyp_groups WHERE org_id = ?", (org_id,))
        templates = _count("SELECT COUNT(*) FROM templates WHERE org_id = ?", (org_id,))
        submissions = _count(
            "SELECT COUNT(*) FROM final_submissions WHERE org_id = ?", (org_id,)
        )
        # documents table may not have org_id — count via users
        documents = _count(
            """
            SELECT COUNT(*) FROM documents d
            JOIN users u ON u.id = d.user_id
            WHERE u.org_id = ?
            """,
            (org_id,),
        )

        return {
            "organization": org,
            "stats": {
                "users": users,
                "supervisors": supervisors,
                "groups": groups,
                "templates": templates,
                "submissions": submissions,
                "documents": documents,
                "documents_used": org["documents_used"],
                "documents_limit": org["documents_limit"],
            },
        }
    finally:
        conn.close()


@router.get("/stats")
def platform_stats(_: None = Depends(_require_super_admin)):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM organizations ORDER BY documents_used DESC, id ASC")
        orgs = [_org_dict(r) for r in cursor.fetchall()]
        total_orgs = len(orgs)
        active_orgs = sum(1 for o in orgs if o["is_active"])
        total_docs = sum(o["documents_used"] for o in orgs)
        # Rough revenue estimate: university plan ~ $99/mo notionally
        revenue_estimate = active_orgs * 99
        return {
            "total_orgs": total_orgs,
            "active_orgs": active_orgs,
            "total_documents": total_docs,
            "revenue_estimate_usd": revenue_estimate,
            "top_orgs": orgs[:10],
        }
    finally:
        conn.close()


@router.post("/organizations/{org_id}/reset-key")
def reset_api_key(org_id: int, _: None = Depends(_require_super_admin)):
    """Regenerate internal org API key (never returned to clients)."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM organizations WHERE id = ?", (org_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Organization not found.")
        api_key = "fmt_live_" + secrets.token_urlsafe(16)
        cursor.execute(
            "UPDATE organizations SET api_key = ? WHERE id = ?",
            (api_key, org_id),
        )
        conn.commit()
        cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
        return {
            "success": True,
            "organization": _org_dict(cursor.fetchone()),
            "message": "Internal API key regenerated (not exposed to clients).",
        }
    finally:
        conn.close()
