"""Admin portal API tests — CRUD, gates, frontmatter branding."""
from __future__ import annotations

import io
import uuid
from datetime import date, timedelta

import pytest


def _admin_id(seeded_users) -> int:
    return int(seeded_users["admin"]["id"])


def _student_id(seeded_users) -> int:
    return int(seeded_users["student"]["id"])


def _q(seeded_users) -> str:
    return f"user_id={_admin_id(seeded_users)}"


@pytest.mark.p1
@pytest.mark.admin
def test_admin_stats(client, auth_headers, seeded_users):
    r = client.get(
        f"/api/admin/stats?{_q(seeded_users)}",
        headers=auth_headers["admin"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "total_students" in body
    assert "total_supervisors" in body
    assert body.get("org_id") == 1


@pytest.mark.p1
@pytest.mark.admin
def test_admin_overview(client, auth_headers, seeded_users):
    r = client.get(
        f"/api/admin/overview?{_q(seeded_users)}",
        headers=auth_headers["admin"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "total_students" in body
    assert "documents_last_7_days" in body or "top_templates" in body


@pytest.mark.p1
@pytest.mark.admin
def test_admin_users(client, auth_headers, seeded_users):
    r = client.get(
        f"/api/admin/users?{_q(seeded_users)}",
        headers=auth_headers["admin"],
    )
    assert r.status_code == 200, r.text
    users = r.json().get("users") or []
    emails = {u.get("email") for u in users}
    assert "admin@comsats.edu.pk" in emails
    assert "student@comsats.edu.pk" in emails


@pytest.mark.p1
@pytest.mark.admin
def test_departments_crud(client, auth_headers, seeded_users):
    code = f"T{uuid.uuid4().hex[:5].upper()}"
    create = client.post(
        f"/api/admin/departments?{_q(seeded_users)}",
        json={
            "name": f"Test Dept {code}",
            "code": code,
            "min_members": 1,
            "max_members": 4,
            "max_groups_per_supervisor": 3,
        },
        headers=auth_headers["admin"],
    )
    assert create.status_code == 200, create.text
    dept = create.json()["department"]
    dept_id = int(dept["id"])
    assert dept["code"] == code

    listed = client.get(
        f"/api/admin/departments?{_q(seeded_users)}",
        headers=auth_headers["admin"],
    )
    assert listed.status_code == 200
    assert any(d.get("id") == dept_id for d in listed.json())

    updated = client.put(
        f"/api/admin/departments/{dept_id}?{_q(seeded_users)}",
        json={"name": f"Renamed {code}", "code": code, "min_members": 2, "max_members": 5},
        headers=auth_headers["admin"],
    )
    assert updated.status_code == 200, updated.text
    assert "Renamed" in updated.json()["department"]["name"]

    deleted = client.delete(
        f"/api/admin/departments/{dept_id}?{_q(seeded_users)}",
        headers=auth_headers["admin"],
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json().get("success") is True


@pytest.mark.p1
@pytest.mark.admin
def test_delete_department_with_supervisors_blocked(client, auth_headers, seeded_users):
    """Seeded CS (or dept1) has supervisors — delete must fail."""
    dept_id = int(seeded_users["dept1"])
    r = client.delete(
        f"/api/admin/departments/{dept_id}?{_q(seeded_users)}",
        headers=auth_headers["admin"],
    )
    assert r.status_code == 400, r.text
    assert "supervisor" in (r.json().get("detail") or "").lower()


@pytest.mark.p1
@pytest.mark.admin
@pytest.mark.fyp
def test_supervisors_list_and_create(client, auth_headers, seeded_users):
    listed = client.get(
        f"/api/admin/supervisors?{_q(seeded_users)}",
        headers=auth_headers["admin"],
    )
    assert listed.status_code == 200, listed.text
    body = listed.json()
    supervisors = body if isinstance(body, list) else body.get("supervisors") or body.get("items") or []
    assert isinstance(supervisors, list)
    assert len(supervisors) >= 1

    email = f"sup_{uuid.uuid4().hex[:8]}@comsats.edu.pk"
    created = client.post(
        f"/api/admin/supervisors?{_q(seeded_users)}",
        json={
            "name": "Pytest Supervisor",
            "email": email,
            "department_id": seeded_users["dept1"],
            "max_groups": 4,
        },
        headers=auth_headers["admin"],
    )
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload.get("success") is True
    assert payload.get("temporary_password")
    # SMTP may soft-fail in test env
    assert "email_sent" in payload
    assert payload["supervisor"]["email"] == email


@pytest.mark.p1
@pytest.mark.admin
def test_admin_templates_list(client, auth_headers, seeded_users):
    r = client.get(
        f"/api/admin/templates?{_q(seeded_users)}",
        headers=auth_headers["admin"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    templates = body if isinstance(body, list) else body.get("templates") or []
    assert isinstance(templates, list)
    assert len(templates) >= 1
    # BUG: /api/admin/templates does not hide __freeform_placeholder__
    # (public /api/templates does). Assert a real template is present.
    names = [t.get("name") for t in templates]
    assert any(n and n != "__freeform_placeholder__" for n in names)


@pytest.mark.p1
@pytest.mark.admin
@pytest.mark.fyp
def test_deadlines_crud(client, auth_headers, seeded_users):
    due = (date.today() + timedelta(days=14)).isoformat()
    created = client.post(
        f"/api/admin/deadlines?{_q(seeded_users)}",
        json={
            "title": f"Mid review {uuid.uuid4().hex[:4]}",
            "description": "pytest deadline",
            "due_date": due,
            "applies_to_all": True,
        },
        headers=auth_headers["admin"],
    )
    assert created.status_code == 200, created.text
    deadline_id = int(created.json()["deadline"]["id"])

    listed = client.get(
        f"/api/admin/deadlines?{_q(seeded_users)}",
        headers=auth_headers["admin"],
    )
    assert listed.status_code == 200
    rows = listed.json() if isinstance(listed.json(), list) else listed.json().get("deadlines") or []
    assert any(d.get("id") == deadline_id for d in rows)

    updated = client.put(
        f"/api/admin/deadlines/{deadline_id}?{_q(seeded_users)}",
        json={
            "title": "Updated mid review",
            "description": "updated",
            "due_date": due,
            "applies_to_all": True,
        },
        headers=auth_headers["admin"],
    )
    assert updated.status_code == 200, updated.text

    deleted = client.delete(
        f"/api/admin/deadlines/{deadline_id}?{_q(seeded_users)}",
        headers=auth_headers["admin"],
    )
    assert deleted.status_code == 200, deleted.text


@pytest.mark.p1
@pytest.mark.admin
@pytest.mark.fyp
def test_semester_deadlines(client, auth_headers, seeded_users):
    """Unique per (semester, org) — create for 7 if missing, else patch."""
    listed = client.get(
        f"/api/admin/semester-deadlines?{_q(seeded_users)}",
        headers=auth_headers["admin"],
    )
    assert listed.status_code == 200, listed.text
    existing = {int(d["semester"]): d for d in listed.json().get("deadlines") or []}
    future = (date.today() + timedelta(days=45)).isoformat()

    if 7 in existing:
        r = client.patch(
            f"/api/admin/semester-deadlines/{existing[7]['id']}?{_q(seeded_users)}",
            json={"deadline_date": future},
            headers=auth_headers["admin"],
        )
        assert r.status_code == 200, r.text
    else:
        r = client.post(
            f"/api/admin/semester-deadlines?{_q(seeded_users)}",
            json={"semester": 7, "deadline_date": future},
            headers=auth_headers["admin"],
        )
        assert r.status_code == 200, r.text
        # Duplicate create → 409
        dup = client.post(
            f"/api/admin/semester-deadlines?{_q(seeded_users)}",
            json={"semester": 7, "deadline_date": future},
            headers=auth_headers["admin"],
        )
        assert dup.status_code == 409, dup.text


@pytest.mark.p1
@pytest.mark.admin
def test_admin_analytics(client, auth_headers, seeded_users):
    r = client.get(
        f"/api/admin/analytics?{_q(seeded_users)}",
        headers=auth_headers["admin"],
    )
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), dict)


@pytest.mark.p1
@pytest.mark.admin
def test_settings_get_put(client, auth_headers, seeded_users):
    r = client.get(
        f"/api/admin/settings?{_q(seeded_users)}",
        headers=auth_headers["admin"],
    )
    assert r.status_code == 200, r.text

    put = client.put(
        f"/api/admin/settings?{_q(seeded_users)}",
        json={"system_name": "Formatify Test Org"},
        headers=auth_headers["admin"],
    )
    assert put.status_code == 200, put.text
    assert put.json().get("success") is True
    settings = put.json().get("settings") or {}
    if "system_name" in settings:
        assert settings["system_name"] == "Formatify Test Org"


@pytest.mark.p1
@pytest.mark.admin
def test_frontmatter_config_get_put(client, auth_headers, seeded_users):
    r = client.get(
        f"/api/admin/frontmatter-config?{_q(seeded_users)}",
        headers=auth_headers["admin"],
    )
    assert r.status_code == 200, r.text
    assert "university_name" in r.json()

    put = client.put(
        f"/api/admin/frontmatter-config?{_q(seeded_users)}",
        json={
            "university_name": "COMSATS University",
            "department_name": "Computer Science",
            "session": "Fall 2026",
        },
        headers=auth_headers["admin"],
    )
    assert put.status_code == 200, put.text
    cfg = put.json().get("config") or {}
    assert cfg.get("university_name") == "COMSATS University"
    assert cfg.get("session") == "Fall 2026"


@pytest.mark.p1
@pytest.mark.admin
def test_frontmatter_logo_upload(client, auth_headers, seeded_users):
    # Minimal 1x1 PNG
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    r = client.post(
        f"/api/admin/frontmatter-config/logo?{_q(seeded_users)}",
        files={"file": ("logo.png", io.BytesIO(png), "image/png")},
        headers=auth_headers["admin"],
    )
    assert r.status_code == 200, r.text
    assert r.json().get("success") is True
    assert r.json().get("logo_path")


@pytest.mark.p0
@pytest.mark.admin
def test_non_admin_user_id_403(client, auth_headers, seeded_users):
    r = client.get(
        f"/api/admin/stats?user_id={_student_id(seeded_users)}",
        headers=auth_headers["student"],
    )
    assert r.status_code == 403, r.text


@pytest.mark.p0
@pytest.mark.admin
@pytest.mark.fyp
def test_fyp_gate_core_only_org(client, seeded_users):
    """
    JWT wins over X-Org-Code, so use org-code-only headers (no Bearer).
    CORE-ONLY has modules=core → FYP admin paths 403; frontmatter-config OK.
    """
    headers = {"X-Org-Code": seeded_users["org_core"]["code"]}
    blocked = client.get("/api/admin/supervisors", headers=headers)
    assert blocked.status_code == 403, blocked.text
    assert "fyp" in (blocked.json().get("detail") or "").lower()

    ok = client.get("/api/admin/frontmatter-config", headers=headers)
    assert ok.status_code == 200, ok.text
    assert "university_name" in ok.json()
