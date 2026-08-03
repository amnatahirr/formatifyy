"""Platform super-admin organization management tests."""
from __future__ import annotations

import uuid

import pytest


@pytest.mark.p2
def test_wrong_super_admin_key_401(client):
    r = client.get(
        "/api/super-admin/organizations",
        headers={"X-Super-Admin-Key": "definitely-wrong-key"},
    )
    assert r.status_code == 401, r.text


@pytest.mark.p2
def test_missing_super_admin_key_401(client):
    r = client.get("/api/super-admin/organizations")
    assert r.status_code == 401, r.text


@pytest.mark.p2
def test_list_organizations_no_api_key(client, auth_headers, seeded_users):
    r = client.get(
        "/api/super-admin/organizations",
        headers=auth_headers["super_admin"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    orgs = body.get("organizations") or []
    assert body.get("count", len(orgs)) >= 1
    assert any(o.get("code") == seeded_users["org1"]["code"] for o in orgs)
    for org in orgs:
        assert "api_key" not in org


@pytest.mark.p2
def test_create_org_with_admin(client, auth_headers):
    code = f"PYT{uuid.uuid4().hex[:6].upper()}"
    email = f"admin_{uuid.uuid4().hex[:6]}@pytest.org"
    r = client.post(
        "/api/super-admin/organizations",
        headers=auth_headers["super_admin"],
        json={
            "name": f"Pytest Org {code}",
            "code": code,
            "type": "university",
            "plan": "university",
            "modules": ["core", "fyp"],
            "documents_limit": 500,
            "admin_name": "Pytest Admin",
            "admin_email": email,
            "admin_password": "TestPass99",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True
    org = body["organization"]
    assert org["code"] == code
    assert "api_key" not in org
    assert body.get("admin")
    assert body["admin"]["email"] == email
    assert body["admin"].get("password") == "TestPass99"

    # Admin can login with org code
    login = client.post(
        "/api/auth/login",
        json={"email": email, "password": "TestPass99", "org_code": code},
        headers={"X-Org-Code": code},
    )
    assert login.status_code == 200, login.text
    assert login.json().get("access_token") or login.json().get("token")


@pytest.mark.p2
def test_toggle_inactive_and_org_resolve(client, auth_headers, seeded_users):
    # Use seeded INACTIVE-ORG or create + toggle a disposable org
    code = f"TOG{uuid.uuid4().hex[:6].upper()}"
    created = client.post(
        "/api/super-admin/organizations",
        headers=auth_headers["super_admin"],
        json={
            "name": f"Toggle Org {code}",
            "code": code,
            "type": "company",
            "plan": "starter",
            "modules": "core",
        },
    )
    assert created.status_code == 200, created.text
    org_id = int(created.json()["organization"]["id"])

    toggled = client.patch(
        f"/api/super-admin/organizations/{org_id}/toggle",
        headers=auth_headers["super_admin"],
    )
    assert toggled.status_code == 200, toggled.text
    assert toggled.json()["organization"]["is_active"] is False

    resolve = client.get(f"/api/org/resolve?code={code}")
    assert resolve.status_code == 403, resolve.text

    # Restore active for cleanup friendliness
    client.patch(
        f"/api/super-admin/organizations/{org_id}/toggle",
        headers=auth_headers["super_admin"],
    )


@pytest.mark.p2
def test_cannot_delete_org_id_1(client, auth_headers):
    r = client.delete(
        "/api/super-admin/organizations/1",
        headers=auth_headers["super_admin"],
    )
    assert r.status_code == 400, r.text
    assert "default" in (r.json().get("detail") or "").lower() or "id=1" in (
        r.json().get("detail") or ""
    )


@pytest.mark.p2
def test_delete_custom_org(client, auth_headers):
    code = f"DEL{uuid.uuid4().hex[:6].upper()}"
    created = client.post(
        "/api/super-admin/organizations",
        headers=auth_headers["super_admin"],
        json={
            "name": f"Delete Me {code}",
            "code": code,
            "type": "company",
            "plan": "starter",
            "modules": "core",
            "admin_email": f"del_{uuid.uuid4().hex[:6]}@pytest.org",
            "admin_password": "DelPass99",
        },
    )
    assert created.status_code == 200, created.text
    org_id = int(created.json()["organization"]["id"])
    assert org_id != 1

    deleted = client.delete(
        f"/api/super-admin/organizations/{org_id}",
        headers=auth_headers["super_admin"],
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json().get("success") is True
    assert deleted.json().get("deleted_id") == org_id

    # Gone from list
    listed = client.get(
        "/api/super-admin/organizations",
        headers=auth_headers["super_admin"],
    )
    assert not any(o.get("id") == org_id for o in listed.json().get("organizations") or [])


@pytest.mark.p2
def test_reset_key(client, auth_headers, db):
    code = f"KEY{uuid.uuid4().hex[:6].upper()}"
    created = client.post(
        "/api/super-admin/organizations",
        headers=auth_headers["super_admin"],
        json={
            "name": f"Key Org {code}",
            "code": code,
            "type": "university",
            "plan": "university",
            "modules": "core,fyp",
        },
    )
    assert created.status_code == 200, created.text
    org_id = int(created.json()["organization"]["id"])

    conn = db.get_db()
    cur = conn.cursor()
    cur.execute("SELECT api_key FROM organizations WHERE id = ?", (org_id,))
    old_key = cur.fetchone()["api_key"]
    conn.close()

    reset = client.post(
        f"/api/super-admin/organizations/{org_id}/reset-key",
        headers=auth_headers["super_admin"],
    )
    assert reset.status_code == 200, reset.text
    assert reset.json().get("success") is True
    # Key not exposed in response payload
    assert "api_key" not in (reset.json().get("organization") or {})

    conn = db.get_db()
    cur = conn.cursor()
    cur.execute("SELECT api_key FROM organizations WHERE id = ?", (org_id,))
    new_key = cur.fetchone()["api_key"]
    conn.close()
    assert new_key != old_key
    assert str(new_key).startswith("fmt_live_")

    # Cleanup
    client.delete(
        f"/api/super-admin/organizations/{org_id}",
        headers=auth_headers["super_admin"],
    )


@pytest.mark.p2
def test_platform_stats(client, auth_headers):
    r = client.get(
        "/api/super-admin/stats",
        headers=auth_headers["super_admin"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "total_orgs" in body
    assert "active_orgs" in body
    assert "revenue_estimate_usd" in body or "total_documents" in body


@pytest.mark.p2
def test_list_admins(client, auth_headers, seeded_users):
    r = client.get(
        "/api/super-admin/admins",
        headers=auth_headers["super_admin"],
    )
    assert r.status_code == 200, r.text
    admins = r.json().get("admins") or []
    assert any(a.get("email") == "admin@comsats.edu.pk" for a in admins)
    for a in admins:
        assert (a.get("role") or "").lower() == "admin"


@pytest.mark.p2
def test_organization_stats(client, auth_headers):
    r = client.get(
        "/api/super-admin/organizations/1/stats",
        headers=auth_headers["super_admin"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "organization" in body
    assert "stats" in body
    assert "api_key" not in body["organization"]
