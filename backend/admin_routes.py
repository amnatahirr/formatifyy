from __future__ import annotations

import json
import logging
import os
import secrets
import smtplib
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from typing import Any

from fastapi import APIRouter, Body, File, HTTPException, Query, Request, UploadFile

from database import get_db, hash_password
from middleware.org_middleware import resolve_organization_from_request

router = APIRouter(prefix="/api/admin", tags=["Admin"])
logger = logging.getLogger(__name__)


def _org_id(request: Request) -> int:
    """Current tenant from middleware / headers (default org 1)."""
    org = getattr(request.state, "org", None)
    if isinstance(org, dict) and org.get("id"):
        return int(org["id"])
    return int(resolve_organization_from_request(request)["id"])

DEFAULT_SETTINGS: dict[str, str] = {
    "system_name": "FORMATIFY Admin Panel",
    "version": "3.0.0",
    "environment": "production",
    "email_notifications": "true",
    "system_notifications": "true",
    "maintenance_mode": "false",
    "api_rate_limit": "10000",
    "api_timeout_seconds": "30",
    "max_file_size_mb": "100",
}


def _require_admin(user_id: int | None) -> None:
    if user_id is None:
        return
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Admin user not found.")
    if row["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")


def _row_to_dict(row) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def _format_date(value: str | None) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d")
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            return value


def _as_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _org_setting_key(org_id: int, key: str) -> str:
    return f"org:{org_id}:{key}"


def _load_settings(cursor, org_id: int) -> dict[str, Any]:
    prefix = f"org:{org_id}:"
    cursor.execute(
        "SELECT key, value FROM admin_settings WHERE key LIKE ?",
        (f"{prefix}%",),
    )
    rows: dict[str, str] = {}
    for row in cursor.fetchall():
        raw_key = row["key"] or ""
        if raw_key.startswith(prefix):
            rows[raw_key[len(prefix) :]] = row["value"]
    merged = {**DEFAULT_SETTINGS, **rows}
    return {
        "system_name": merged["system_name"],
        "version": merged["version"],
        "environment": merged["environment"],
        "email_notifications": _as_bool(merged["email_notifications"]),
        "system_notifications": _as_bool(merged["system_notifications"]),
        "maintenance_mode": _as_bool(merged["maintenance_mode"]),
        "api_rate_limit": int(merged["api_rate_limit"]),
        "api_timeout_seconds": int(merged["api_timeout_seconds"]),
        "max_file_size_mb": int(merged["max_file_size_mb"]),
    }


def _save_settings(cursor, payload: dict[str, Any], org_id: int) -> dict[str, Any]:
    mapping = {
        "system_name": str,
        "version": str,
        "environment": str,
        "email_notifications": lambda v: "true" if bool(v) else "false",
        "system_notifications": lambda v: "true" if bool(v) else "false",
        "maintenance_mode": lambda v: "true" if bool(v) else "false",
        "api_rate_limit": str,
        "api_timeout_seconds": str,
        "max_file_size_mb": str,
    }
    for key, caster in mapping.items():
        if key not in payload:
            continue
        value = caster(payload[key])
        cursor.execute(
            """
            INSERT INTO admin_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (_org_setting_key(org_id, key), value),
        )
    return _load_settings(cursor, org_id)


def _documents_last_7_days(cursor, org_id: int) -> list[dict[str, Any]]:
    start_day = date.today() - timedelta(days=6)
    cursor.execute(
        """
        SELECT date(d.created_at) AS day, COUNT(*) AS count
        FROM documents d
        INNER JOIN users u ON u.id = d.user_id
        WHERE u.org_id = ? AND date(d.created_at) >= date(?)
        GROUP BY date(d.created_at)
        ORDER BY day ASC
        """,
        (org_id, start_day.isoformat()),
    )
    counts = {row["day"]: int(row["count"] or 0) for row in cursor.fetchall()}
    days: list[dict[str, Any]] = []
    for offset in range(7):
        current = start_day + timedelta(days=offset)
        label = current.strftime("%a")
        days.append(
            {
                "day": label,
                "date": current.isoformat(),
                "count": counts.get(current.isoformat(), 0),
            }
        )
    return days


def _top_templates(cursor, org_id: int, limit: int = 5) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT t.id, t.name, COUNT(d.id) AS uses
        FROM templates t
        LEFT JOIN documents d ON d.template_id = t.id
        LEFT JOIN users u ON u.id = d.user_id
        WHERE t.org_id = ?
          AND (d.id IS NULL OR u.org_id = ?)
        GROUP BY t.id
        ORDER BY uses DESC, t.name ASC
        LIMIT ?
        """,
        (org_id, org_id, limit),
    )
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "uses": int(row["uses"] or 0),
        }
        for row in cursor.fetchall()
    ]


def _issue_breakdown(cursor, org_id: int) -> list[dict[str, Any]]:
    formatting = grammar = plagiarism = structure = 0
    cursor.execute(
        """
        SELECT pm.analysis_report
        FROM project_merges pm
        INNER JOIN collaboration_projects cp ON cp.id = pm.project_id
        WHERE cp.org_id = ?
          AND pm.analysis_report IS NOT NULL
          AND pm.analysis_report != ''
        """,
        (org_id,),
    )
    for row in cursor.fetchall():
        try:
            report = json.loads(row["analysis_report"])
        except Exception:
            continue
        stats = report.get("stats") or {}
        formatting += int(stats.get("formatting_issues") or 0)
        grammar += int(stats.get("grammar_issues") or 0)
        plagiarism += int(stats.get("plagiarism_issues") or 0)
        for issue in report.get("issues") or []:
            issue_type = str(issue.get("type") or issue.get("function") or "").lower()
            if issue_type in {"heading_style", "section_order", "structure", "missing_sections"}:
                structure += 1

    buckets = [
        ("Formatting", formatting),
        ("Grammar", grammar),
        ("Plagiarism", plagiarism),
        ("Structure", structure),
    ]
    total = sum(count for _, count in buckets)
    if total == 0:
        return [{"label": label, "percentage": 0, "count": 0} for label, _ in buckets]
    return [
        {
            "label": label,
            "count": count,
            "percentage": round((count / total) * 100),
        }
        for label, count in buckets
    ]


def _department_scores(cursor, org_id: int) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT
            d.id,
            d.name,
            COUNT(DISTINCT doc.id) AS document_count,
            SUM(CASE WHEN doc.status = 'completed' THEN 1 ELSE 0 END) AS completed_count
        FROM departments d
        LEFT JOIN templates t ON t.department_id = d.id AND t.org_id = ?
        LEFT JOIN documents doc ON doc.template_id = t.id
        LEFT JOIN users u ON u.id = doc.user_id AND u.org_id = ?
        WHERE d.org_id = ?
          AND (doc.id IS NULL OR u.id IS NOT NULL)
        GROUP BY d.id
        ORDER BY d.name ASC
        """,
        (org_id, org_id, org_id),
    )
    scores: list[dict[str, Any]] = []
    for row in cursor.fetchall():
        document_count = int(row["document_count"] or 0)
        completed_count = int(row["completed_count"] or 0)
        avg_score = round((completed_count / document_count) * 100, 1) if document_count else 0.0
        scores.append(
            {
                "department_id": row["id"],
                "department_name": row["name"],
                "avg_compliance_score": avg_score,
                "documents_analyzed": document_count,
                "completed_documents": completed_count,
            }
        )
    return scores


def _build_analytics(cursor, org_id: int) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT COUNT(*) FROM documents d
        INNER JOIN users u ON u.id = d.user_id
        WHERE u.org_id = ?
        """,
        (org_id,),
    )
    total_documents = int(cursor.fetchone()[0] or 0)

    cursor.execute(
        """
        SELECT COUNT(*) FROM documents d
        INNER JOIN users u ON u.id = d.user_id
        WHERE u.org_id = ? AND d.status = 'completed'
        """,
        (org_id,),
    )
    completed_documents = int(cursor.fetchone()[0] or 0)

    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'student' AND org_id = ?",
        (org_id,),
    )
    total_students = int(cursor.fetchone()[0] or 0)

    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'supervisor' AND org_id = ?",
        (org_id,),
    )
    total_supervisors = int(cursor.fetchone()[0] or 0)

    cursor.execute("SELECT COUNT(*) FROM templates WHERE org_id = ?", (org_id,))
    total_templates = int(cursor.fetchone()[0] or 0)

    cursor.execute("SELECT COUNT(*) FROM departments WHERE org_id = ?", (org_id,))
    total_departments = int(cursor.fetchone()[0] or 0)

    cursor.execute(
        """
        SELECT COUNT(*) FROM documents d
        INNER JOIN users u ON u.id = d.user_id
        WHERE u.org_id = ?
          AND strftime('%Y-%m', d.created_at) = strftime('%Y-%m', 'now')
        """,
        (org_id,),
    )
    documents_this_month = int(cursor.fetchone()[0] or 0)

    success_rate = round((completed_documents / total_documents) * 100, 1) if total_documents else 0.0
    avg_compliance_score = success_rate

    # Always return last 6 calendar months so charts are never empty.
    monthly_map: dict[str, int] = {}
    cursor.execute(
        """
        SELECT strftime('%Y-%m', d.created_at) AS month_key, COUNT(*) AS count
        FROM documents d
        INNER JOIN users u ON u.id = d.user_id
        WHERE u.org_id = ? AND d.created_at IS NOT NULL
        GROUP BY month_key
        """,
        (org_id,),
    )
    for row in cursor.fetchall():
        month_key = row["month_key"]
        if month_key:
            monthly_map[month_key] = int(row["count"] or 0)

    monthly_documents = []
    today = date.today()
    for offset in range(5, -1, -1):
        month_date = date(today.year, today.month, 1)
        # step back `offset` months
        year = month_date.year
        month = month_date.month - offset
        while month <= 0:
            month += 12
            year -= 1
        key = f"{year:04d}-{month:02d}"
        monthly_documents.append(
            {
                "month": date(year, month, 1).strftime("%b %Y"),
                "count": monthly_map.get(key, 0),
            }
        )

    return {
        "total_documents": total_documents,
        "documents_analyzed": total_documents,
        "documents_this_month": documents_this_month,
        "completed_documents": completed_documents,
        "total_students": total_students,
        "total_supervisors": total_supervisors,
        "total_templates": total_templates,
        "total_departments": total_departments,
        "success_rate": success_rate,
        "avg_compliance_score": avg_compliance_score,
        "top_templates": _top_templates(cursor, org_id),
        "documents_last_7_days": _documents_last_7_days(cursor, org_id),
        "issue_breakdown": _issue_breakdown(cursor, org_id),
        "department_scores": _department_scores(cursor, org_id),
        "monthly_documents": monthly_documents,
        "generated_at": datetime.utcnow().isoformat(),
        "today": date.today().isoformat(),
        "org_id": org_id,
    }


@router.get("/stats")
def get_admin_stats(
    request: Request,
    user_id: int | None = Query(default=None),
):
    _require_admin(user_id)
    org_id = _org_id(request)
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM supervisors WHERE org_id = ?", (org_id,))
    total_supervisors = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'student' AND org_id = ?",
        (org_id,),
    )
    total_students = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*) FROM collaboration_projects p
        INNER JOIN users u ON u.id = p.created_by
        WHERE u.org_id = ? AND p.status = 'active'
        """,
        (org_id,),
    )
    total_active_projects = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*) FROM documents d
        INNER JOIN users u ON u.id = d.user_id
        WHERE u.org_id = ? AND d.status = 'completed'
        """,
        (org_id,),
    )
    total_documents_checked = cursor.fetchone()[0]

    conn.close()
    return {
        "total_supervisors": total_supervisors,
        "total_students": total_students,
        "total_active_projects": total_active_projects,
        "total_documents_checked": total_documents_checked,
        "org_id": org_id,
    }


@router.get("/overview")
def get_admin_overview(
    request: Request,
    user_id: int | None = Query(default=None),
):
    _require_admin(user_id)
    org_id = _org_id(request)
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM supervisors WHERE org_id = ?", (org_id,))
    total_supervisors = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'student' AND org_id = ?",
        (org_id,),
    )
    total_students = cursor.fetchone()[0]
    cursor.execute(
        """
        SELECT COUNT(*) FROM collaboration_projects p
        INNER JOIN users u ON u.id = p.created_by
        WHERE u.org_id = ? AND p.status = 'active'
        """,
        (org_id,),
    )
    total_active_projects = cursor.fetchone()[0]
    cursor.execute(
        """
        SELECT COUNT(*) FROM documents d
        INNER JOIN users u ON u.id = d.user_id
        WHERE u.org_id = ? AND d.status = 'completed'
        """,
        (org_id,),
    )
    total_documents_checked = cursor.fetchone()[0]

    analytics = _build_analytics(cursor, org_id)
    conn.close()
    return {
        "total_supervisors": total_supervisors,
        "total_students": total_students,
        "total_active_projects": total_active_projects,
        "total_documents_checked": total_documents_checked,
        "success_rate": analytics["success_rate"],
        "documents_this_month": analytics["documents_this_month"],
        "top_templates": analytics["top_templates"],
        "documents_last_7_days": analytics["documents_last_7_days"],
        "recent_activity": analytics["documents_last_7_days"],
        "org_id": org_id,
    }


@router.get("/users")
def get_admin_users(
    request: Request,
    user_id: int | None = Query(default=None),
):
    _require_admin(user_id)
    org_id = _org_id(request)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT u.id, u.username, u.email, u.role, u.created_at, uni.name AS university_name
        FROM users u
        LEFT JOIN universities uni ON uni.id = u.university_id
        WHERE u.org_id = ?
        ORDER BY u.created_at DESC
        """,
        (org_id,),
    )
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"users": users}


@router.get("/departments")
def get_departments(
    request: Request,
    user_id: int | None = Query(default=None),
):
    _require_admin(user_id)
    org_id = _org_id(request)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            d.*,
            COUNT(DISTINCT s.id) AS supervisor_count,
            COUNT(DISTINCT t.id) AS template_count
        FROM departments d
        LEFT JOIN supervisors s ON s.department_id = d.id AND s.org_id = ?
        LEFT JOIN templates t ON t.department_id = d.id AND t.org_id = ?
        WHERE d.org_id = ?
        GROUP BY d.id
        ORDER BY d.name ASC
        """,
        (org_id, org_id, org_id),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


@router.post("/departments")
def create_department(
    request: Request,
    payload: dict[str, Any] = Body(...),
    user_id: int | None = Query(default=None),
):
    _require_admin(user_id)
    org_id = _org_id(request)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO departments (name, code, min_members, max_members, max_groups_per_supervisor, org_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            payload.get("name"),
            payload.get("code"),
            int(payload.get("min_members", 1) or 1),
            int(payload.get("max_members", 3) or 3),
            int(payload.get("max_groups_per_supervisor", 6) or 6),
            org_id,
        ),
    )
    conn.commit()
    department_id = cursor.lastrowid
    cursor.execute(
        "SELECT * FROM departments WHERE id = ? AND org_id = ?",
        (department_id, org_id),
    )
    department = dict(cursor.fetchone())
    conn.close()
    return {"success": True, "department": department}


@router.put("/departments/{department_id}")
def update_department(
    department_id: int,
    request: Request,
    payload: dict[str, Any] = Body(...),
    user_id: int | None = Query(default=None),
):
    _require_admin(user_id)
    org_id = _org_id(request)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM departments WHERE id = ? AND org_id = ?",
        (department_id, org_id),
    )
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Department not found.")

    cursor.execute(
        """
        UPDATE departments
        SET name = ?, code = ?, min_members = ?, max_members = ?, max_groups_per_supervisor = ?
        WHERE id = ? AND org_id = ?
        """,
        (
            payload.get("name", existing["name"]),
            payload.get("code", existing["code"]),
            int(payload.get("min_members", existing["min_members"]) or 1),
            int(payload.get("max_members", existing["max_members"]) or 3),
            int(payload.get("max_groups_per_supervisor", existing["max_groups_per_supervisor"]) or 6),
            department_id,
            org_id,
        ),
    )
    conn.commit()
    cursor.execute(
        "SELECT * FROM departments WHERE id = ? AND org_id = ?",
        (department_id, org_id),
    )
    department = dict(cursor.fetchone())
    conn.close()
    return {"success": True, "department": department}


@router.delete("/departments/{department_id}")
def delete_department(
    department_id: int,
    request: Request,
    user_id: int | None = Query(default=None),
):
    _require_admin(user_id)
    org_id = _org_id(request)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM departments WHERE id = ? AND org_id = ?",
        (department_id, org_id),
    )
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Department not found.")

    cursor.execute("SELECT COUNT(*) FROM supervisors WHERE department_id = ?", (department_id,))
    if cursor.fetchone()[0] > 0:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Cannot delete a department that still has supervisors. Remove supervisors first.",
        )

    cursor.execute(
        "DELETE FROM departments WHERE id = ? AND org_id = ?",
        (department_id, org_id),
    )
    conn.commit()
    conn.close()
    return {"success": True, "deleted_id": department_id}


@router.get("/supervisors")
def get_supervisors(
    request: Request,
    department_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    user_id: int | None = Query(default=None),
):
    _require_admin(user_id)
    org_id = _org_id(request)
    conn = get_db()
    cursor = conn.cursor()

    clauses: list[str] = ["s.org_id = ?"]
    params: list[Any] = [org_id]
    if department_id is not None:
        clauses.append("s.department_id = ?")
        params.append(department_id)
    if search:
        clauses.append("(LOWER(s.name) LIKE ? OR LOWER(s.email) LIKE ?)")
        token = f"%{search.strip().lower()}%"
        params.extend([token, token])

    where_sql = f"WHERE {' AND '.join(clauses)}"
    cursor.execute(
        f"""
        SELECT s.*, d.name AS department_name, d.code AS department_code
        FROM supervisors s
        INNER JOIN departments d ON d.id = s.department_id
        {where_sql}
        ORDER BY s.name ASC
        """,
        params,
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def _generate_temp_password() -> str:
    return f"FYP@{secrets.token_hex(4).upper()}"


def _send_supervisor_credentials_email(
    *,
    name: str,
    email: str,
    temporary_password: str,
    department_name: str = "",
) -> dict[str, Any]:
    """Send credentials email via SMTP when configured; otherwise log and report queued."""
    subject = "Your Formatify Supervisor Account"
    body = (
        f"Hello {name},\n\n"
        f"An administrator has created a Formatify supervisor account for you"
        f"{f' in {department_name}' if department_name else ''}.\n\n"
        f"Login email: {email}\n"
        f"Temporary password: {temporary_password}\n\n"
        "Please sign in and change this password on first login.\n\n"
        "— Formatify Admin\n"
    )

    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587") or 587)
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "noreply@formatify.local").strip()

    if not smtp_host:
        logger.info(
            "SMTP not configured. Supervisor credentials for %s: %s",
            email,
            temporary_password,
        )
        return {
            "sent": True,
            "simulated": True,
            "message": "Password email queued (SMTP not configured; credentials logged on server).",
        }

    try:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = smtp_from
        message["To"] = email
        message.set_content(body)

        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_password)
            server.send_message(message)
        return {"sent": True, "simulated": False, "message": f"Credentials emailed to {email}."}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to email supervisor credentials to %s", email)
        return {"sent": False, "simulated": False, "message": f"Email failed: {exc}"}


@router.post("/supervisors")
def create_supervisor(
    request: Request,
    payload: dict[str, Any] = Body(...),
    user_id: int | None = Query(default=None),
):
    _require_admin(user_id)
    org_id = _org_id(request)
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    if not name or not email:
        raise HTTPException(status_code=400, detail="Name and email are required.")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM supervisors WHERE LOWER(email) = ? AND org_id = ?",
        (email, org_id),
    )
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail="A supervisor with this email already exists.")

    temporary_password = _generate_temp_password()
    linked_user_id = None

    cursor.execute(
        "SELECT id, role, org_id FROM users WHERE LOWER(email) = ? AND org_id = ?",
        (email, org_id),
    )
    existing_user = cursor.fetchone()
    if existing_user:
        if existing_user["role"] == "admin":
            conn.close()
            raise HTTPException(
                status_code=400,
                detail="This email belongs to an admin account and cannot be converted to a supervisor.",
            )
        linked_user_id = existing_user["id"]
        cursor.execute(
            """
            UPDATE users
            SET password_hash = ?, role = 'supervisor', username = ?, org_id = ?
            WHERE id = ?
            """,
            (hash_password(temporary_password), name, org_id, linked_user_id),
        )
    else:
        cursor.execute(
            """
            INSERT INTO users (username, email, password_hash, role, university_id, org_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, email, hash_password(temporary_password), "supervisor", 1, org_id),
        )
        linked_user_id = cursor.lastrowid

    cursor.execute(
        """
        INSERT INTO supervisors (name, email, department_id, max_groups, current_groups, is_active, org_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            email,
            int(payload.get("department_id")),
            int(payload.get("max_groups", 6) or 6),
            int(payload.get("current_groups", 0) or 0),
            1 if payload.get("is_active", True) else 0,
            org_id,
        ),
    )
    conn.commit()
    supervisor_id = cursor.lastrowid
    cursor.execute(
        """
        SELECT s.*, d.name AS department_name, d.code AS department_code
        FROM supervisors s
        INNER JOIN departments d ON d.id = s.department_id
        WHERE s.id = ?
        """,
        (supervisor_id,),
    )
    supervisor = dict(cursor.fetchone())
    conn.close()

    email_result = _send_supervisor_credentials_email(
        name=name,
        email=email,
        temporary_password=temporary_password,
        department_name=supervisor.get("department_name") or "",
    )

    return {
        "success": True,
        "supervisor": supervisor,
        "temporary_password": temporary_password,
        "user_id": linked_user_id,
        "email_sent": email_result.get("sent", False),
        "email_message": email_result.get("message", ""),
    }


@router.post("/supervisors/{supervisor_id}/send-credentials")
def send_supervisor_credentials(
    supervisor_id: int,
    request: Request,
    payload: dict[str, Any] = Body(default={}),
    user_id: int | None = Query(default=None),
):
    _require_admin(user_id)
    org_id = _org_id(request)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT s.*, d.name AS department_name
        FROM supervisors s
        INNER JOIN departments d ON d.id = s.department_id
        WHERE s.id = ? AND s.org_id = ?
        """,
        (supervisor_id, org_id),
    )
    supervisor = cursor.fetchone()
    if not supervisor:
        conn.close()
        raise HTTPException(status_code=404, detail="Supervisor not found.")

    temporary_password = (payload.get("temporary_password") or "").strip() or _generate_temp_password()
    cursor.execute(
        "SELECT id FROM users WHERE LOWER(email) = ? AND org_id = ?",
        (supervisor["email"].lower(), org_id),
    )
    user_row = cursor.fetchone()
    if user_row:
        cursor.execute(
            "UPDATE users SET password_hash = ? WHERE id = ? AND org_id = ?",
            (hash_password(temporary_password), user_row["id"], org_id),
        )
        conn.commit()
    conn.close()

    email_result = _send_supervisor_credentials_email(
        name=supervisor["name"],
        email=supervisor["email"],
        temporary_password=temporary_password,
        department_name=supervisor["department_name"] or "",
    )
    return {
        "success": bool(email_result.get("sent")),
        "temporary_password": temporary_password,
        "email_sent": email_result.get("sent", False),
        "message": email_result.get("message", ""),
    }


@router.put("/supervisors/{supervisor_id}")
def update_supervisor(
    supervisor_id: int,
    request: Request,
    payload: dict[str, Any] = Body(...),
    user_id: int | None = Query(default=None),
):
    _require_admin(user_id)
    org_id = _org_id(request)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM supervisors WHERE id = ? AND org_id = ?",
        (supervisor_id, org_id),
    )
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Supervisor not found.")

    cursor.execute(
        """
        UPDATE supervisors
        SET name = ?, email = ?, department_id = ?, max_groups = ?, current_groups = ?, is_active = ?
        WHERE id = ? AND org_id = ?
        """,
        (
            payload.get("name", existing["name"]),
            payload.get("email", existing["email"]),
            int(payload.get("department_id", existing["department_id"])),
            int(payload.get("max_groups", existing["max_groups"]) or 6),
            int(payload.get("current_groups", existing["current_groups"]) or 0),
            1 if payload.get("is_active", bool(existing["is_active"])) else 0,
            supervisor_id,
            org_id,
        ),
    )
    conn.commit()
    cursor.execute(
        """
        SELECT s.*, d.name AS department_name, d.code AS department_code
        FROM supervisors s
        INNER JOIN departments d ON d.id = s.department_id
        WHERE s.id = ? AND s.org_id = ?
        """,
        (supervisor_id, org_id),
    )
    supervisor = dict(cursor.fetchone())
    conn.close()
    return {"success": True, "supervisor": supervisor}


@router.patch("/supervisors/{supervisor_id}/toggle")
def toggle_supervisor(
    supervisor_id: int,
    request: Request,
    user_id: int | None = Query(default=None),
):
    _require_admin(user_id)
    org_id = _org_id(request)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM supervisors WHERE id = ? AND org_id = ?",
        (supervisor_id, org_id),
    )
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Supervisor not found.")

    next_state = 0 if existing["is_active"] else 1
    cursor.execute(
        "UPDATE supervisors SET is_active = ? WHERE id = ? AND org_id = ?",
        (next_state, supervisor_id, org_id),
    )
    conn.commit()
    cursor.execute(
        "SELECT * FROM supervisors WHERE id = ? AND org_id = ?",
        (supervisor_id, org_id),
    )
    supervisor = dict(cursor.fetchone())
    conn.close()
    return {"success": True, "supervisor": supervisor}


@router.delete("/supervisors/{supervisor_id}")
def delete_supervisor(
    supervisor_id: int,
    request: Request,
    user_id: int | None = Query(default=None),
):
    _require_admin(user_id)
    org_id = _org_id(request)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM supervisors WHERE id = ? AND org_id = ?",
        (supervisor_id, org_id),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Supervisor not found.")

    email = (row["email"] or "").strip().lower()
    cursor.execute(
        "DELETE FROM supervisors WHERE id = ? AND org_id = ?",
        (supervisor_id, org_id),
    )
    if email:
        cursor.execute(
            "DELETE FROM users WHERE LOWER(email) = ? AND role = 'supervisor' AND org_id = ?",
            (email, org_id),
        )
    conn.commit()
    conn.close()
    return {"success": True, "deleted_id": supervisor_id}


@router.get("/templates")
def get_admin_templates(
    request: Request,
    department_id: int | None = Query(default=None),
    user_id: int | None = Query(default=None),
):
    _require_admin(user_id)
    org_id = _org_id(request)
    conn = get_db()
    cursor = conn.cursor()
    params: list[Any] = [org_id]
    where_sql = "WHERE t.org_id = ?"
    if department_id is not None:
        where_sql += " AND t.department_id = ?"
        params.append(department_id)

    cursor.execute(
        f"""
        SELECT
            t.id,
            t.university_id,
            t.department_id,
            t.name,
            t.description,
            t.required_sections,
            t.formatting_rules,
            t.created_by,
            t.created_at,
            d.name AS department_name,
            d.code AS department_code
        FROM templates t
        LEFT JOIN departments d ON d.id = t.department_id
        {where_sql}
        ORDER BY t.created_at DESC, t.name ASC
        """,
        params,
    )
    rows = []
    for row in cursor.fetchall():
        item = dict(row)
        try:
            item["required_sections"] = json.loads(item.get("required_sections") or "[]")
        except Exception:
            item["required_sections"] = []
        try:
            item["formatting_rules"] = json.loads(item.get("formatting_rules") or "{}")
        except Exception:
            item["formatting_rules"] = {}
        rows.append(item)
    conn.close()
    return rows


@router.get("/deadlines")
def get_deadlines(
    request: Request,
    user_id: int | None = Query(default=None),
):
    _require_admin(user_id)
    org_id = _org_id(request)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT dl.*, d.name AS department_name, d.code AS department_code
        FROM deadlines dl
        LEFT JOIN departments d ON d.id = dl.department_id
        WHERE dl.org_id = ?
        ORDER BY dl.due_date ASC
        """,
        (org_id,),
    )
    deadlines = []
    for row in cursor.fetchall():
        item = dict(row)
        item["due_date"] = _format_date(item.get("due_date"))
        deadlines.append(item)
    conn.close()
    return deadlines


@router.post("/deadlines")
def create_deadline(
    request: Request,
    payload: dict[str, Any] = Body(...),
    user_id: int | None = Query(default=None),
):
    _require_admin(user_id)
    org_id = _org_id(request)
    applies_to_all = bool(payload.get("applies_to_all", not payload.get("department_id")))
    department_id = None if applies_to_all else int(payload.get("department_id"))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO deadlines (title, description, due_date, department_id, applies_to_all, org_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            payload.get("title"),
            payload.get("description"),
            payload.get("due_date"),
            department_id,
            1 if applies_to_all else 0,
            org_id,
        ),
    )
    conn.commit()
    deadline_id = cursor.lastrowid
    cursor.execute(
        """
        SELECT dl.*, d.name AS department_name, d.code AS department_code
        FROM deadlines dl
        LEFT JOIN departments d ON d.id = dl.department_id
        WHERE dl.id = ?
        """,
        (deadline_id,),
    )
    deadline = dict(cursor.fetchone())
    deadline["due_date"] = _format_date(deadline.get("due_date"))
    conn.close()
    return {"success": True, "deadline": deadline}


@router.put("/deadlines/{deadline_id}")
def update_deadline(
    deadline_id: int,
    request: Request,
    payload: dict[str, Any] = Body(...),
    user_id: int | None = Query(default=None),
):
    _require_admin(user_id)
    org_id = _org_id(request)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM deadlines WHERE id = ? AND org_id = ?",
        (deadline_id, org_id),
    )
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Deadline not found.")

    applies_to_all = bool(payload.get("applies_to_all", existing["applies_to_all"]))
    department_id = None if applies_to_all else int(payload.get("department_id", existing["department_id"]))
    cursor.execute(
        """
        UPDATE deadlines
        SET title = ?, description = ?, due_date = ?, department_id = ?, applies_to_all = ?
        WHERE id = ? AND org_id = ?
        """,
        (
            payload.get("title", existing["title"]),
            payload.get("description", existing["description"]),
            payload.get("due_date", existing["due_date"]),
            department_id,
            1 if applies_to_all else 0,
            deadline_id,
            org_id,
        ),
    )
    conn.commit()
    cursor.execute(
        """
        SELECT dl.*, d.name AS department_name, d.code AS department_code
        FROM deadlines dl
        LEFT JOIN departments d ON d.id = dl.department_id
        WHERE dl.id = ? AND dl.org_id = ?
        """,
        (deadline_id, org_id),
    )
    deadline = dict(cursor.fetchone())
    deadline["due_date"] = _format_date(deadline.get("due_date"))
    conn.close()
    return {"success": True, "deadline": deadline}


@router.delete("/deadlines/{deadline_id}")
def delete_deadline(
    deadline_id: int,
    request: Request,
    user_id: int | None = Query(default=None),
):
    _require_admin(user_id)
    org_id = _org_id(request)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM deadlines WHERE id = ? AND org_id = ?",
        (deadline_id, org_id),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Deadline not found.")
    cursor.execute(
        "DELETE FROM deadlines WHERE id = ? AND org_id = ?",
        (deadline_id, org_id),
    )
    conn.commit()
    conn.close()
    return {"success": True, "deleted_id": deadline_id}


def _serialize_semester_deadline(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "semester": int(row["semester"]),
        "deadline_date": _format_date(row["deadline_date"] if "deadline_date" in row.keys() else None),
        "created_by": row["created_by"] if "created_by" in row.keys() else None,
        "created_at": row["created_at"] if "created_at" in row.keys() else None,
        "updated_at": row["updated_at"] if "updated_at" in row.keys() else None,
    }


@router.get("/semester-deadlines")
def list_semester_deadlines(
    request: Request,
    user_id: int | None = Query(default=None),
):
    """Org-scoped Semester 6 / 7 FYP submission deadlines (one row per semester per org)."""
    _require_admin(user_id)
    org_id = _org_id(request)
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, semester, deadline_date, created_by, created_at, updated_at
            FROM semester_deadlines
            WHERE org_id = ?
            ORDER BY semester ASC
            """,
            (org_id,),
        )
        rows = [_serialize_semester_deadline(r) for r in cursor.fetchall()]
        return {"deadlines": rows, "count": len(rows)}
    finally:
        conn.close()


@router.post("/semester-deadlines")
def create_semester_deadline(
    request: Request,
    payload: dict[str, Any] = Body(...),
    user_id: int | None = Query(default=None),
):
    """Create a semester deadline row if that semester does not already exist for this org."""
    _require_admin(user_id)
    org_id = _org_id(request)
    try:
        semester = int(payload.get("semester"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="semester must be 6 or 7.")
    if semester not in (6, 7):
        raise HTTPException(status_code=400, detail="semester must be 6 or 7.")

    deadline_raw = (payload.get("deadline_date") or "").strip()
    if not deadline_raw:
        raise HTTPException(status_code=400, detail="deadline_date is required.")
    try:
        deadline = datetime.strptime(deadline_raw[:10], "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="deadline_date must be YYYY-MM-DD.")

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id FROM semester_deadlines WHERE semester = ? AND org_id = ?",
            (semester, org_id),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=409,
                detail=f"Semester {semester} deadline already exists. Use PATCH to update.",
            )

        now = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
        cursor.execute(
            """
            INSERT INTO semester_deadlines
                (semester, deadline_date, created_by, created_at, updated_at, org_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (semester, deadline.isoformat(), user_id, now, now, org_id),
        )
        conn.commit()
        new_id = cursor.lastrowid
        cursor.execute(
            """
            SELECT id, semester, deadline_date, created_by, created_at, updated_at
            FROM semester_deadlines WHERE id = ? AND org_id = ?
            """,
            (new_id, org_id),
        )
        row = cursor.fetchone()
        return {"success": True, "deadline": _serialize_semester_deadline(row)}
    except HTTPException:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.patch("/semester-deadlines/{deadline_id}")
def update_semester_deadline(
    deadline_id: int,
    request: Request,
    payload: dict[str, Any] = Body(...),
    user_id: int | None = Query(default=None),
):
    """Update deadline_date for an existing semester deadline row."""
    _require_admin(user_id)
    org_id = _org_id(request)
    deadline_raw = (payload.get("deadline_date") or "").strip()
    if not deadline_raw:
        raise HTTPException(status_code=400, detail="deadline_date is required.")
    try:
        deadline = datetime.strptime(deadline_raw[:10], "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="deadline_date must be YYYY-MM-DD.")

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id FROM semester_deadlines WHERE id = ? AND org_id = ?",
            (deadline_id, org_id),
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Semester deadline not found.")

        now = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
        cursor.execute(
            """
            UPDATE semester_deadlines
            SET deadline_date = ?, updated_at = ?
            WHERE id = ? AND org_id = ?
            """,
            (deadline.isoformat(), now, deadline_id, org_id),
        )
        conn.commit()
        cursor.execute(
            """
            SELECT id, semester, deadline_date, created_by, created_at, updated_at
            FROM semester_deadlines WHERE id = ? AND org_id = ?
            """,
            (deadline_id, org_id),
        )
        row = cursor.fetchone()
        return {"success": True, "deadline": _serialize_semester_deadline(row)}
    except HTTPException:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.get("/analytics")
def get_admin_analytics(
    request: Request,
    user_id: int | None = Query(default=None),
):
    _require_admin(user_id)
    org_id = _org_id(request)
    conn = get_db()
    cursor = conn.cursor()
    payload = _build_analytics(cursor, org_id)
    conn.close()
    return payload


@router.get("/universities")
def get_admin_universities(
    request: Request,
    user_id: int | None = Query(default=None),
):
    _require_admin(user_id)
    org_id = _org_id(request)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            u.id,
            u.name,
            u.country,
            u.created_at,
            COUNT(users.id) AS user_count,
            SUM(CASE WHEN users.role = 'student' THEN 1 ELSE 0 END) AS student_count
        FROM universities u
        LEFT JOIN users ON users.university_id = u.id AND users.org_id = ?
        GROUP BY u.id
        ORDER BY u.name ASC
        """,
        (org_id,),
    )
    universities = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return universities


@router.get("/settings")
def get_admin_settings(
    request: Request,
    user_id: int | None = Query(default=None),
):
    _require_admin(user_id)
    org_id = _org_id(request)
    conn = get_db()
    cursor = conn.cursor()
    settings = _load_settings(cursor, org_id)
    conn.close()
    return settings


@router.put("/settings")
def update_admin_settings(
    request: Request,
    payload: dict[str, Any] = Body(...),
    user_id: int | None = Query(default=None),
):
    _require_admin(user_id)
    org_id = _org_id(request)
    conn = get_db()
    cursor = conn.cursor()
    settings = _save_settings(cursor, payload, org_id)
    conn.commit()
    conn.close()
    return {"success": True, "settings": settings}


# ═══════════════════════════════════════════════════════════════════════════════
# FRONTMATTER / COVER PAGE BRANDING
# Stored in existing admin_settings keys (university_name, department_name,
# session, logo_path). Template DOCX files overwrite backend/templates/*.docx
# paths already used by frontmatter_generator — no generator changes.
# ═══════════════════════════════════════════════════════════════════════════════

_LOGO_DIR = os.path.join("uploads", "branding")
_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _upsert_setting(cursor, key: str, value: str, org_id: int) -> None:
    cursor.execute(
        """
        INSERT INTO admin_settings (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = CURRENT_TIMESTAMP
        """,
        (_org_setting_key(org_id, key), value),
    )


def _settings_raw_map(cursor, org_id: int) -> dict[str, str]:
    prefix = f"org:{org_id}:"
    cursor.execute(
        "SELECT key, value FROM admin_settings WHERE key LIKE ?",
        (f"{prefix}%",),
    )
    rows: dict[str, str] = {}
    for row in cursor.fetchall():
        raw_key = row["key"] or ""
        if raw_key.startswith(prefix):
            rows[raw_key[len(prefix) :]] = row["value"] or ""
    return rows


def _template_file_info(path: str, kind: str) -> dict[str, Any]:
    exists = os.path.isfile(path)
    info: dict[str, Any] = {
        "kind": kind,
        "filename": os.path.basename(path),
        "path": path.replace("\\", "/"),
        "exists": exists,
        "size_bytes": os.path.getsize(path) if exists else 0,
        "updated_at": None,
    }
    if exists:
        info["updated_at"] = datetime.utcfromtimestamp(os.path.getmtime(path)).isoformat() + "Z"
    return info


def _logo_public_url(logo_path: str) -> str | None:
    path = (logo_path or "").strip().replace("\\", "/")
    if not path:
        return None
    # Prefer /uploads/... when stored under uploads/
    if path.startswith("uploads/"):
        return "/" + path
    if os.path.isfile(path):
        return "/" + path if path.startswith("uploads/") else None
    return None


def _load_frontmatter_config(cursor, org_id: int) -> dict[str, Any]:
    from frontmatter_generator import COVER_TEMPLATE, INFO_TEMPLATE, scaffold_templates

    scaffold_templates()
    rows = _settings_raw_map(cursor, org_id)
    logo_path = (rows.get("logo_path") or "").strip()
    return {
        "university_name": (rows.get("university_name") or "").strip(),
        "department_name": (rows.get("department_name") or "").strip(),
        "session": (rows.get("session") or "").strip(),
        "logo_path": logo_path,
        "logo_url": _logo_public_url(logo_path),
        "logo_exists": bool(logo_path and os.path.isfile(logo_path)),
        "cover_template": _template_file_info(COVER_TEMPLATE, "cover"),
        "info_template": _template_file_info(INFO_TEMPLATE, "info"),
    }


@router.get("/frontmatter-config")
def get_frontmatter_config(
    request: Request,
    user_id: int | None = Query(default=None),
):
    """Branding + template status for cover / project-info generation."""
    _require_admin(user_id)
    org_id = _org_id(request)
    conn = get_db()
    cursor = conn.cursor()
    try:
        return _load_frontmatter_config(cursor, org_id)
    finally:
        conn.close()


@router.put("/frontmatter-config")
def update_frontmatter_config(
    request: Request,
    payload: dict[str, Any] = Body(...),
    user_id: int | None = Query(default=None),
):
    """Update university_name / department_name / session text fields."""
    _require_admin(user_id)
    org_id = _org_id(request)
    allowed = {"university_name", "department_name", "session"}
    conn = get_db()
    cursor = conn.cursor()
    try:
        for key in allowed:
            if key not in payload:
                continue
            _upsert_setting(cursor, key, str(payload.get(key) or "").strip(), org_id)
        conn.commit()
        return {"success": True, "config": _load_frontmatter_config(cursor, org_id)}
    finally:
        conn.close()


@router.post("/frontmatter-config/logo")
async def upload_frontmatter_logo(
    request: Request,
    file: UploadFile = File(...),
    user_id: int | None = Query(default=None),
):
    """Upload university logo image; stores path in admin_settings.logo_path."""
    _require_admin(user_id)
    org_id = _org_id(request)
    filename = file.filename or "logo.png"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _LOGO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported logo type '{ext}'. Allowed: {', '.join(sorted(_LOGO_EXTENSIONS))}",
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded logo file is empty.")

    os.makedirs(_LOGO_DIR, exist_ok=True)
    stored_name = f"university_logo_org{org_id}{ext}"
    stored_path = os.path.join(_LOGO_DIR, stored_name)
    with open(stored_path, "wb") as out:
        out.write(raw)

    # Normalize to forward-slash relative path for portability
    stored_rel = stored_path.replace("\\", "/")

    conn = get_db()
    cursor = conn.cursor()
    try:
        _upsert_setting(cursor, "logo_path", stored_rel, org_id)
        conn.commit()
        config = _load_frontmatter_config(cursor, org_id)
    finally:
        conn.close()

    return {"success": True, "logo_path": stored_rel, "config": config}


@router.post("/frontmatter-config/templates/{kind}")
async def upload_frontmatter_template(
    kind: str,
    request: Request,
    file: UploadFile = File(...),
    user_id: int | None = Query(default=None),
):
    """
    Replace cover or project-info DOCX template.
    kind: 'cover' | 'info'
    Overwrites the files frontmatter_generator already reads.
    """
    _require_admin(user_id)
    org_id = _org_id(request)
    kind_norm = (kind or "").strip().lower()
    if kind_norm not in {"cover", "info"}:
        raise HTTPException(status_code=400, detail="kind must be 'cover' or 'info'.")

    filename = file.filename or ""
    if not filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx template files are supported.")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded template file is empty.")

    from frontmatter_generator import COVER_TEMPLATE, INFO_TEMPLATE, TEMPLATES_DIR, scaffold_templates

    scaffold_templates()
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    target = COVER_TEMPLATE if kind_norm == "cover" else INFO_TEMPLATE
    with open(target, "wb") as out:
        out.write(raw)

    conn = get_db()
    cursor = conn.cursor()
    try:
        config = _load_frontmatter_config(cursor, org_id)
    finally:
        conn.close()

    return {
        "success": True,
        "kind": kind_norm,
        "filename": os.path.basename(target),
        "path": target.replace("\\", "/"),
        "config": config,
    }
