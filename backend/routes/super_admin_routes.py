"""
super_admin_routes.py — Platform Super Admin: manage all organizations.

Protected by X-Super-Admin-Key header (SUPER_ADMIN_KEY env / .env).

Real-data additions
-------------------
* GET /stats now also returns: growth series, billing breakdown, plan/module
  catalogs (with live org counts), user/admin totals and the recent activity feed.
* Every mutating action (create / update / toggle / delete / reset-key) is written
  to the `super_admin_activity` table (created automatically; existing orgs are
  back-filled once so the feed is never empty on first run).
* GET /activity returns the audit trail on its own.
* Plan list prices live in PLAN_CATALOG below and can be overridden with env vars
  PLAN_PRICE_UNIVERSITY / PLAN_PRICE_ENTERPRISE / PLAN_PRICE_STARTER.
"""

from __future__ import annotations

import logging
import os
import secrets
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Annotated, Any, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query

from database import get_db, hash_password
from middleware.org_middleware import get_super_admin_key

load_dotenv(Path(__file__).resolve().parent / ".env")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/super-admin", tags=["Super Admin"])

# ---------------------------------------------------------------------------
# Catalogs (server-side source of truth for Billing + Settings screens)
# ---------------------------------------------------------------------------

PLAN_CATALOG: dict[str, dict[str, Any]] = {
    "university": {
        "label": "University",
        "price_usd": 150,
        "description": "Core + FYP modules for universities.",
    },
    "enterprise": {
        "label": "Enterprise (Company)",
        "price_usd": 99,
        "description": "Company tenants with the core module.",
    },
    "starter": {
        "label": "Starter",
        "price_usd": 48,
        "description": "Entry-level plan for small teams.",
    },
}

MODULE_CATALOG: dict[str, dict[str, Any]] = {
    "core": {
        "label": "Core Module",
        "price_usd": 99,
        "description": "Base platform access, document workflows, reporting.",
    },
    "fyp": {
        "label": "FYP Module",
        "price_usd": 51,
        "description": "Final-year project tracking, supervisor allocation, defenses.",
    },
}

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _plan_price(plan: str) -> int:
    key = (plan or "").strip().lower()
    env = os.getenv(f"PLAN_PRICE_{key.upper()}", "").strip()
    if env:
        try:
            return int(float(env))
        except ValueError:
            pass
    return int(PLAN_CATALOG.get(key, {}).get("price_usd", 0))


def _plan_label(plan: str) -> str:
    key = (plan or "").strip().lower()
    if key in PLAN_CATALOG:
        return PLAN_CATALOG[key]["label"]
    return key.capitalize() if key else "—"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_ACTIVITY_READY = False


def _require_super_admin(
    x_super_admin_key: Annotated[Optional[str], Header()] = None,
) -> None:
    expected = get_super_admin_key()
    provided = (x_super_admin_key or "").strip()
    if not provided or not expected or not secrets.compare_digest(
        provided.encode("utf-8"), str(expected).encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Invalid or missing X-Super-Admin-Key.")
    _ensure_activity_table()


# ---------------------------------------------------------------------------
# Activity log
# ---------------------------------------------------------------------------


def _ensure_activity_table() -> None:
    """Create the audit table once per process and back-fill from existing orgs."""
    global _ACTIVITY_READY
    if _ACTIVITY_READY:
        return
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS super_admin_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                text TEXT NOT NULL,
                org_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute("SELECT COUNT(*) FROM super_admin_activity")
        if int(cur.fetchone()[0] or 0) == 0:
            cur.execute("SELECT id, name, plan, created_at FROM organizations ORDER BY id ASC")
            for r in cur.fetchall():
                cur.execute(
                    """
                    INSERT INTO super_admin_activity (kind, text, org_id, created_at)
                    VALUES ('org', ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
                    """,
                    (f"{r['name']} was created on plan {r['plan'] or 'university'}", r["id"], r["created_at"]),
                )
        conn.commit()
        _ACTIVITY_READY = True
    except Exception:  # noqa: BLE001
        logger.exception("Could not prepare super_admin_activity table")
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
    finally:
        conn.close()


def _log_activity(cursor, kind: str, text: str, org_id: Optional[int] = None) -> None:
    """Best-effort audit entry — never breaks the calling request."""
    try:
        cursor.execute(
            "INSERT INTO super_admin_activity (kind, text, org_id) VALUES (?, ?, ?)",
            (kind, text, org_id),
        )
    except Exception:  # noqa: BLE001
        logger.warning("Could not write activity entry: %s", text)


def _iso(raw: Any) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    s = s.replace(" ", "T")
    if not (s.endswith("Z") or "+" in s[10:]):
        s += "Z"
    return s


def _fetch_activity(cursor, limit: int = 50) -> list[dict[str, Any]]:
    try:
        cursor.execute(
            """
            SELECT id, kind, text, org_id, created_at
            FROM super_admin_activity
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        )
        return [
            {
                "id": int(r["id"]),
                "kind": r["kind"] or "org",
                "text": r["text"] or "",
                "org_id": r["org_id"],
                "created_at": _iso(r["created_at"]),
            }
            for r in cursor.fetchall()
        ]
    except Exception:  # noqa: BLE001
        return []


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------


def _send_org_admin_credentials_email(
    *,
    admin_name: str,
    admin_email: str,
    admin_password: str,
    org_name: str,
    org_code: str,
) -> dict[str, Any]:
    """Email org admin login credentials (org code, email, password) via SMTP."""
    display_name = (admin_name or "").strip() or admin_email.split("@")[0]
    subject = f"Your Formatify Admin Account — {org_name}"
    body = (
        f"Hello {display_name},\n\n"
        f"A Formatify organization admin account has been created for you.\n\n"
        f"Organization: {org_name}\n"
        f"Organization code: {org_code}\n"
        f"Login email: {admin_email}\n"
        f"Password: {admin_password}\n\n"
        "How to sign in:\n"
        "1. Open Formatify\n"
        f"2. Enter organization code: {org_code}\n"
        "3. Sign in with the email and password above\n"
        "4. Change your password after first login if prompted\n\n"
        "Keep this email private — it contains your login credentials.\n\n"
        "— Formatify\n"
    )

    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587") or 587)
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "noreply@formatify.local").strip()

    if not smtp_host or not smtp_user or not smtp_password:
        logger.warning(
            "SMTP not configured — org admin credentials for %s (org %s) were not emailed.",
            admin_email,
            org_code,
        )
        return {
            "sent": False,
            "simulated": True,
            "message": (
                "SMTP is not configured on the server. Credentials were not emailed; "
                "share them with the admin manually."
            ),
        }

    try:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = smtp_from
        message["To"] = admin_email
        message.set_content(body)

        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(message)
        logger.info("Org admin credentials emailed to %s for org %s", admin_email, org_code)
        return {
            "sent": True,
            "simulated": False,
            "message": f"Login credentials emailed to {admin_email}.",
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to email org admin credentials to %s", admin_email)
        return {
            "sent": False,
            "simulated": False,
            "message": f"Could not email credentials: {exc}",
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _growth_series(orgs: list[dict[str, Any]], months: int = 6) -> dict[str, list]:
    """Cumulative org count at the end of each of the last `months` months."""
    now = datetime.now(timezone.utc)
    keys: list[tuple[int, int]] = []
    y, m = now.year, now.month
    for _ in range(months):
        keys.append((y, m))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    keys.reverse()

    created: list[int] = []
    for o in orgs:
        raw = str(o.get("created_at") or "")
        try:
            created.append(int(raw[:4]) * 12 + int(raw[5:7]))
        except (ValueError, IndexError):
            created.append(0)  # unknown date → treated as existing before the window

    labels, counts, new_counts = [], [], []
    for (yy, mm) in keys:
        idx = yy * 12 + mm
        labels.append(_MONTHS[mm - 1])
        counts.append(sum(1 for c in created if c <= idx))
        new_counts.append(sum(1 for c in created if c == idx))
    return {"labels": labels, "counts": counts, "new_counts": new_counts}


def _billing_summary(orgs: list[dict[str, Any]]) -> dict[str, Any]:
    """Estimated recurring revenue from plan list prices (suspended orgs excluded)."""
    plan_keys = list(PLAN_CATALOG.keys())
    for o in orgs:
        p = (o["plan"] or "").lower()
        if p and p not in plan_keys:
            plan_keys.append(p)

    by_plan = []
    for key in plan_keys:
        price = _plan_price(key)
        members = [o for o in orgs if (o["plan"] or "").lower() == key]
        active = [o for o in members if o["is_active"]]
        by_plan.append(
            {
                "key": key,
                "label": _plan_label(key),
                "price_usd": price,
                "org_count": len(members),
                "active_count": len(active),
                "monthly_usd": price * len(active),
            }
        )

    rows = []
    for o in orgs:
        price = _plan_price(o["plan"])
        rows.append(
            {
                "org_id": o["id"],
                "name": o["name"],
                "code": o["code"],
                "plan": (o["plan"] or "").lower(),
                "plan_label": _plan_label(o["plan"]),
                "modules": o["modules_list"],
                "is_active": o["is_active"],
                "monthly_usd": price if o["is_active"] else 0,
            }
        )

    return {
        "total_monthly_usd": sum(p["monthly_usd"] for p in by_plan),
        "by_plan": by_plan,
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


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


@router.get("/activity")
def list_activity(
    limit: int = Query(50, ge=1, le=200),
    _: None = Depends(_require_super_admin),
):
    conn = get_db()
    cursor = conn.cursor()
    try:
        items = _fetch_activity(cursor, limit)
        return {"activity": items, "count": len(items)}
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
        _log_activity(cursor, "org", f"{name} was created on plan {plan}", org_id)

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
            _log_activity(cursor, "admin", f"Admin account created for {admin_email} ({name})", org_id)

        conn.commit()
        cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
        org = _org_dict(cursor.fetchone())

        email_result = None
        if admin_payload:
            email_result = _send_org_admin_credentials_email(
                admin_name=admin_name,
                admin_email=admin_email,
                admin_password=admin_password,
                org_name=name,
                org_code=code,
            )
            admin_payload["credentials_email"] = email_result
            if email_result.get("sent"):
                _log_activity(cursor, "admin", f"Login credentials emailed to {admin_email}", org_id)
                conn.commit()

        if admin_payload and email_result and email_result.get("sent"):
            message = (
                "Organization created. Login email and password were sent to the admin."
            )
        elif admin_payload:
            message = (
                "Organization and admin created, but credentials email failed. "
                "Share org code + password with the admin manually."
            )
        else:
            message = "Organization created. Add an admin later or use signup."

        return {
            "success": True,
            "organization": org,
            "org_code": org.get("code"),
            "admin": admin_payload,
            "credentials_email": email_result,
            "message": message,
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

        old_name = row["name"] or ""
        old_plan = (row["plan"] or "").strip()
        old_modules = {m.strip() for m in (row["modules"] or "core").split(",") if m.strip()}

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

        # Audit trail
        display = str(name).strip() or old_name
        new_plan = str(plan).strip()
        new_modules = {m.strip() for m in str(modules).split(",") if m.strip()}
        changed = False
        if new_plan != old_plan:
            _log_activity(cursor, "plan", f"{display} plan changed from {old_plan or '—'} to {new_plan}", org_id)
            changed = True
        if new_modules != old_modules:
            enabled = sorted(new_modules - old_modules)
            disabled = sorted(old_modules - new_modules)
            parts = []
            if enabled:
                parts.append(f"{', '.join(enabled)} enabled")
            if disabled:
                parts.append(f"{', '.join(disabled)} disabled")
            _log_activity(cursor, "module", f"{display}: {'; '.join(parts)}", org_id)
            changed = True
        if not changed:
            _log_activity(cursor, "org", f"{display} details were updated", org_id)

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
        cursor.execute("SELECT id, name, is_active FROM organizations WHERE id = ?", (org_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found.")
        new_val = 0 if row["is_active"] else 1
        cursor.execute("UPDATE organizations SET is_active = ? WHERE id = ?", (new_val, org_id))
        _log_activity(
            cursor,
            "toggle",
            f"{row['name']} was {'reactivated' if new_val else 'suspended'}",
            org_id,
        )
        conn.commit()
        cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
        return {"success": True, "organization": _org_dict(cursor.fetchone())}
    except HTTPException:
        conn.rollback()
        raise
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
        cursor.execute("SELECT id, name, code FROM organizations WHERE id = ?", (org_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found.")

        summary = _purge_organization_data(cursor, org_id)
        cursor.execute("DELETE FROM organizations WHERE id = ?", (org_id,))
        _log_activity(cursor, "delete", f"{row['name']} ({row['code']}) was deleted", None)
        conn.commit()
        return {
            "success": True,
            "deleted_id": org_id,
            "org_code": row["code"],
            "purged": summary,
        }
    except HTTPException:
        conn.rollback()
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
    """Platform-wide metrics. Powers Overview, Billing, Activity and Settings screens."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM organizations ORDER BY documents_used DESC, id ASC")
        orgs = [_org_dict(r) for r in cursor.fetchall()]
        total_orgs = len(orgs)
        active_orgs = sum(1 for o in orgs if o["is_active"])
        total_docs = sum(o["documents_used"] for o in orgs)

        def _count(sql: str) -> int:
            try:
                cursor.execute(sql)
                return int(cursor.fetchone()[0] or 0)
            except Exception:
                return 0

        total_users = _count("SELECT COUNT(*) FROM users")
        total_admins = _count("SELECT COUNT(*) FROM users WHERE LOWER(role) = 'admin'")

        billing = _billing_summary(sorted(orgs, key=lambda o: o["id"]))
        growth = _growth_series(orgs)

        plan_catalog = []
        for key, meta in PLAN_CATALOG.items():
            plan_catalog.append(
                {
                    "key": key,
                    "label": meta["label"],
                    "description": meta["description"],
                    "price_usd": _plan_price(key),
                    "org_count": sum(1 for o in orgs if (o["plan"] or "").lower() == key),
                }
            )

        module_catalog = []
        for key, meta in MODULE_CATALOG.items():
            module_catalog.append(
                {
                    "key": key,
                    "label": meta["label"],
                    "description": meta["description"],
                    "price_usd": meta["price_usd"],
                    "org_count": sum(1 for o in orgs if key in o["modules_list"]),
                }
            )

        return {
            "total_orgs": total_orgs,
            "active_orgs": active_orgs,
            "suspended_orgs": total_orgs - active_orgs,
            "total_documents": total_docs,
            "total_users": total_users,
            "total_admins": total_admins,
            "revenue_estimate_usd": billing["total_monthly_usd"],
            "top_orgs": orgs[:10],
            "growth": growth,
            "billing": billing,
            "plan_catalog": plan_catalog,
            "module_catalog": module_catalog,
            "activity": _fetch_activity(cursor, 50),
        }
    finally:
        conn.close()


@router.post("/organizations/{org_id}/reset-key")
def reset_api_key(org_id: int, _: None = Depends(_require_super_admin)):
    """Regenerate internal org API key (never returned to clients)."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, name FROM organizations WHERE id = ?", (org_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found.")
        api_key = "fmt_live_" + secrets.token_urlsafe(16)
        cursor.execute(
            "UPDATE organizations SET api_key = ? WHERE id = ?",
            (api_key, org_id),
        )
        _log_activity(cursor, "key", f"Internal API key regenerated for {row['name']}", org_id)
        conn.commit()
        cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
        return {
            "success": True,
            "organization": _org_dict(cursor.fetchone()),
            "message": "Internal API key regenerated (not exposed to clients).",
        }
    except HTTPException:
        conn.rollback()
        raise
    finally:
        conn.close()