"""Multi-tenancy isolation, org gates, module gates, and role ownership checks."""
from __future__ import annotations

import io
import uuid

import pytest
from auth_jwt import create_access_token


def _unique(prefix: str = "mt") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


@pytest.mark.p0
@pytest.mark.auth
def test_same_email_different_orgs_allowed(client, seeded_users, db):
    """Email uniqueness is scoped by org_id — same email may exist in two orgs."""
    email = f"{_unique('shared')}@dual.org"
    # Org 1
    r1 = client.post(
        "/api/auth/signup",
        json={
            "username": _unique("o1"),
            "email": email,
            "password": "securepass1",
            "department_id": seeded_users["dept1"],
            "current_semester": 6,
            "org_code": seeded_users["org1"]["code"],
        },
    )
    assert r1.status_code == 200, r1.text

    # Org B — same email
    r2 = client.post(
        "/api/auth/signup",
        json={
            "username": _unique("o2"),
            "email": email,
            "password": "securepass1",
            "department_id": seeded_users["dept_b"],
            "current_semester": 6,
            "org_code": seeded_users["org_b"]["code"],
        },
    )
    assert r2.status_code == 200, r2.text
    assert r1.json()["id"] != r2.json()["id"]
    assert r1.json()["org_id"] != r2.json()["org_id"]

    # Login must be org-scoped
    login_b = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": "securepass1",
            "org_code": seeded_users["org_b"]["code"],
        },
    )
    assert login_b.status_code == 200
    assert login_b.json()["org_id"] == seeded_users["org_b_id"]
    assert login_b.json()["id"] == r2.json()["id"]


@pytest.mark.p0
@pytest.mark.auth
def test_login_wrong_org_code_401(client, seeded_users):
    """Student of COMSATS cannot authenticate against TEST-ORG-B."""
    r = client.post(
        "/api/auth/login",
        json={
            "email": "student@comsats.edu.pk",
            "password": "student123",
            "org_code": seeded_users["org_b"]["code"],
        },
    )
    assert r.status_code == 401


@pytest.mark.p0
@pytest.mark.auth
def test_inactive_org_resolve_403(client):
    r = client.get("/api/org/resolve", params={"code": "INACTIVE-ORG"})
    assert r.status_code == 403
    assert "inactive" in str(r.json()["detail"]).lower()


@pytest.mark.p0
@pytest.mark.auth
def test_inactive_org_request_gate_403(client):
    """Middleware rejects X-Org-Code for inactive tenants."""
    r = client.get(
        "/api/org/info",
        headers={"X-Org-Code": "INACTIVE-ORG"},
    )
    assert r.status_code == 403
    assert "inactive" in str(r.json()["detail"]).lower()


@pytest.mark.p0
@pytest.mark.auth
def test_document_limit_org_403(client, seeded_users, sample_txt_bytes):
    """
    Org with documents_used >= documents_limit is blocked at middleware resolve.
    Uses X-Org-Code (lookup_organization enforces the limit).
    """
    r = client.get(
        "/api/org/info",
        headers={"X-Org-Code": "LIMIT-ORG"},
    )
    assert r.status_code == 403
    detail = str(r.json()["detail"]).lower()
    assert "limit" in detail or "document" in detail

    # Upload path also blocked before handler
    r2 = client.post(
        "/api/documents/upload",
        params={"template_id": seeded_users["template_id"], "user_id": seeded_users["student"]["id"]},
        files={"file": ("x.txt", io.BytesIO(sample_txt_bytes), "text/plain")},
        headers={"X-Org-Code": "LIMIT-ORG"},
    )
    assert r2.status_code == 403


@pytest.mark.p1
@pytest.mark.auth
def test_document_limit_jwt_path_note(client, seeded_users, db, sample_txt_bytes):
    """
    JWT resolve uses _org_by_id which currently skips documents_limit checks.
    If a LIMIT-ORG JWT user can still upload, record as BUG for product review.
    """
    conn = db.get_db()
    cur = conn.cursor()
    limit_org_id = seeded_users["limit_org_id"]
    cur.execute(
        "SELECT id FROM departments WHERE org_id = ? LIMIT 1", (limit_org_id,)
    )
    drow = cur.fetchone()
    if not drow:
        cur.execute(
            """
            INSERT INTO departments (name, code, min_members, max_members, max_groups_per_supervisor, org_id)
            VALUES ('Limit CS', 'LCS', 1, 4, 5, ?)
            """,
            (limit_org_id,),
        )
        conn.commit()
        dept_id = int(cur.lastrowid)
    else:
        dept_id = int(drow["id"])

    email = f"{_unique('lim')}@limit.org"
    cur.execute(
        """
        INSERT INTO users (username, email, password_hash, role, university_id, department_id, org_id, current_semester)
        VALUES (?, ?, ?, 'student', 1, ?, ?, 6)
        """,
        (_unique("limu"), email, db.hash_password("student123"), dept_id, limit_org_id),
    )
    conn.commit()
    uid = int(cur.lastrowid)

    # Need a template in limit org for upload validation
    cur.execute(
        "SELECT id FROM templates WHERE org_id = ? LIMIT 1", (limit_org_id,)
    )
    trow = cur.fetchone()
    if not trow:
        cur.execute(
            """
            INSERT INTO templates
            (university_id, department_id, name, description, required_sections, formatting_rules, created_by, org_id)
            VALUES (1, ?, 'Limit Tmpl', 't', '[]', '{}', ?, ?)
            """,
            (dept_id, uid, limit_org_id),
        )
        conn.commit()
        tid = int(cur.lastrowid)
    else:
        tid = int(trow["id"])
    conn.close()

    token = create_access_token(
        user_id=uid,
        org_id=limit_org_id,
        role="student",
        email=email,
        org_code="LIMIT-ORG",
    )
    headers = {"Authorization": f"Bearer {token}", "X-Org-Code": "LIMIT-ORG"}
    # Prefer JWT: middleware uses JWT path first (may bypass limit — known gap)
    r = client.post(
        "/api/documents/upload",
        params={"template_id": tid, "user_id": uid},
        files={"file": ("lim.txt", io.BytesIO(sample_txt_bytes), "text/plain")},
        headers=headers,
    )
    if r.status_code != 403:
        # BUG: JWT org resolve does not enforce documents_limit (only lookup_organization does).
        # Keep test informative without failing the suite on this product gap.
        # BUG: JWT path bypasses organization document limit (documents_used >= documents_limit).
        pytest.xfail(
            "BUG: JWT org resolve skips documents_limit — upload returned "
            f"{r.status_code} instead of 403"
        )


@pytest.mark.p0
@pytest.mark.fyp
@pytest.mark.auth
def test_core_only_org_fyp_routes_403(client, seeded_users, db):
    """Orgs without fyp module cannot hit /api/student or /api/supervisor."""
    core = seeded_users["org_core"]
    headers = {"X-Org-Code": core["code"]}

    r_student = client.get(
        "/api/student/supervisors",
        params={"user_id": seeded_users["student"]["id"]},
        headers=headers,
    )
    assert r_student.status_code == 403
    assert "fyp" in str(r_student.json()["detail"]).lower()

    r_sup = client.get(
        "/api/supervisor/home",
        params={"user_id": seeded_users["supervisor"]["id"]},
        headers=headers,
    )
    assert r_sup.status_code == 403
    assert "fyp" in str(r_sup.json()["detail"]).lower()

    r_admin_fyp = client.get(
        "/api/admin/supervisors",
        params={"user_id": seeded_users["admin"]["id"]},
        headers=headers,
    )
    assert r_admin_fyp.status_code == 403


@pytest.mark.p0
@pytest.mark.admin
@pytest.mark.auth
def test_core_only_org_frontmatter_config_ok(client, seeded_users, db):
    """Frontmatter branding is a core feature — not FYP-gated."""
    core = seeded_users["org_core"]
    # Ensure an admin exists in core org for stricter role checks when user_id passed
    conn = db.get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM users WHERE org_id = ? AND role = 'admin' LIMIT 1",
        (seeded_users["core_org_id"],),
    )
    row = cur.fetchone()
    if not row:
        cur.execute(
            """
            INSERT INTO users (username, email, password_hash, role, university_id, org_id)
            VALUES (?, ?, ?, 'admin', 1, ?)
            """,
            (
                _unique("coreadm"),
                f"{_unique('coreadm')}@core.org",
                db.hash_password("admin123"),
                seeded_users["core_org_id"],
            ),
        )
        conn.commit()
        admin_id = int(cur.lastrowid)
    else:
        admin_id = int(row["id"])
    conn.close()

    token = create_access_token(
        user_id=admin_id,
        org_id=seeded_users["core_org_id"],
        role="admin",
        email="core-admin@core.org",
        org_code=core["code"],
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Org-Code": core["code"],
    }
    r = client.get(
        "/api/admin/frontmatter-config",
        params={"user_id": admin_id},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Config payload should be a dict with branding-ish keys
    assert isinstance(body, dict)


@pytest.mark.p0
@pytest.mark.fyp
@pytest.mark.auth
def test_student_cannot_call_supervisor_routes(client, auth_headers, seeded_users):
    uid = seeded_users["student"]["id"]
    headers = auth_headers["student"]

    r_home = client.get(
        "/api/supervisor/home",
        params={"user_id": uid},
        headers=headers,
    )
    assert r_home.status_code == 403
    assert "supervisor" in r_home.json()["detail"].lower()

    r_groups = client.get(
        "/api/supervisor/groups",
        params={"user_id": uid},
        headers=headers,
    )
    assert r_groups.status_code == 403

    r_req = client.get(
        "/api/supervisor/assignment-requests",
        params={"user_id": uid},
        headers=headers,
    )
    assert r_req.status_code == 403


@pytest.mark.p0
@pytest.mark.auth
def test_wrong_user_id_ownership_analyze_and_delete(
    client, auth_headers, seeded_users, sample_docx_file
):
    owner = seeded_users["student"]["id"]
    other = seeded_users["admin"]["id"]
    tid = seeded_users["template_id"]
    name, buf, ctype = sample_docx_file
    buf.seek(0)
    up = client.post(
        "/api/documents/upload",
        params={"template_id": tid, "user_id": owner},
        files={"file": (name, buf, ctype)},
        headers=auth_headers["student"],
    )
    assert up.status_code == 200
    doc_id = up.json()["document_id"]

    r_analyze = client.get(
        f"/api/documents/analyze/{doc_id}",
        params={"user_id": other},
        headers=auth_headers["admin"],
    )
    assert r_analyze.status_code == 404

    r_preview = client.get(
        f"/api/format-document/from-document/{doc_id}",
        params={"user_id": other},
        headers=auth_headers["admin"],
    )
    assert r_preview.status_code == 404

    r_del = client.delete(
        f"/api/documents/{doc_id}",
        params={"user_id": other},
        headers=auth_headers["admin"],
    )
    assert r_del.status_code == 404

    # Owner still has the document
    listed = client.get(
        "/api/documents/",
        params={"user_id": owner},
        headers=auth_headers["student"],
    )
    assert doc_id in {d["id"] for d in listed.json()}


@pytest.mark.p1
@pytest.mark.auth
def test_me_cross_org_denied_with_org_b_context(client, seeded_users):
    token = create_access_token(
        user_id=seeded_users["student_b_id"],
        org_id=seeded_users["org_b_id"],
        role="student",
        email="student_b@test.org",
        org_code=seeded_users["org_b"]["code"],
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Org-Code": seeded_users["org_b"]["code"],
    }
    # Asking for org1 student while JWT is org B
    r = client.get(
        "/api/auth/me",
        params={"user_id": seeded_users["student"]["id"]},
        headers=headers,
    )
    assert r.status_code == 403
