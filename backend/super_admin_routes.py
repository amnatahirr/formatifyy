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
        cursor.execute("SELECT id FROM organizations WHERE id = ?", (org_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Organization not found.")
        cursor.execute("DELETE FROM organization_modules WHERE org_id = ?", (org_id,))
        cursor.execute("DELETE FROM organizations WHERE id = ?", (org_id,))
        conn.commit()
        return {"success": True, "deleted_id": org_id}
    finally:
        conn.close()


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
