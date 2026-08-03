"""Auth signup/login/me/change-password and JWT claim contracts."""
from __future__ import annotations

import uuid

import jwt
import pytest


def _unique(prefix: str = "u") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


@pytest.mark.p0
@pytest.mark.auth
def test_signup_happy_path(client, seeded_users):
    uname = _unique("signup")
    email = f"{uname}@example.com"
    r = client.post(
        "/api/auth/signup",
        json={
            "username": uname,
            "email": email,
            "password": "securepass1",
            "department_id": seeded_users["dept1"],
            "university_id": 1,
            "current_semester": 6,
            "org_code": seeded_users["org1"]["code"],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == email
    assert body["role"] == "student"
    assert body["org_id"] == seeded_users["org1"]["id"]
    assert body["org_code"] == seeded_users["org1"]["code"]
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"].count(".") == 2
    assert body["id"]


@pytest.mark.p0
@pytest.mark.auth
def test_signup_duplicate_email_409(client, seeded_users):
    r = client.post(
        "/api/auth/signup",
        json={
            "username": _unique("dup"),
            "email": "student@comsats.edu.pk",
            "password": "securepass1",
            "department_id": seeded_users["dept1"],
            "current_semester": 6,
            "org_code": "COMSATS-LHR",
        },
    )
    assert r.status_code == 409
    assert "email" in r.json()["detail"].lower()


@pytest.mark.p0
@pytest.mark.auth
def test_signup_duplicate_username_409(client, seeded_users):
    # Seeded student username is typically "student"
    student = seeded_users["student"]
    r = client.post(
        "/api/auth/signup",
        json={
            "username": student["username"],
            "email": f"{_unique('dupmail')}@example.com",
            "password": "securepass1",
            "department_id": seeded_users["dept1"],
            "current_semester": 6,
            "org_code": "COMSATS-LHR",
        },
    )
    assert r.status_code == 409
    assert "username" in r.json()["detail"].lower()


@pytest.mark.p0
@pytest.mark.auth
def test_signup_university_fyp_requires_semester(client, seeded_users):
    r = client.post(
        "/api/auth/signup",
        json={
            "username": _unique("nosem"),
            "email": f"{_unique('nosem')}@example.com",
            "password": "securepass1",
            "department_id": seeded_users["dept1"],
            "org_code": "COMSATS-LHR",
            # current_semester omitted — required for university+FYP
        },
    )
    assert r.status_code == 400
    assert "semester" in r.json()["detail"].lower()


@pytest.mark.p1
@pytest.mark.auth
def test_signup_invalid_semester_value(client, seeded_users):
    r = client.post(
        "/api/auth/signup",
        json={
            "username": _unique("badsem"),
            "email": f"{_unique('badsem')}@example.com",
            "password": "securepass1",
            "department_id": seeded_users["dept1"],
            "current_semester": 5,
            "org_code": "COMSATS-LHR",
        },
    )
    assert r.status_code == 400
    assert "semester" in r.json()["detail"].lower()


@pytest.mark.p1
@pytest.mark.auth
def test_signup_invalid_department_400(client, seeded_users):
    r = client.post(
        "/api/auth/signup",
        json={
            "username": _unique("baddept"),
            "email": f"{_unique('baddept')}@example.com",
            "password": "securepass1",
            "department_id": 999999,
            "current_semester": 6,
            "org_code": "COMSATS-LHR",
        },
    )
    assert r.status_code == 400
    assert "department" in r.json()["detail"].lower()


@pytest.mark.p0
@pytest.mark.auth
def test_list_departments_default_org(client, seeded_users):
    r = client.get(
        "/api/auth/departments",
        params={"org_code": seeded_users["org1"]["code"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert "departments" in body
    assert body["count"] == len(body["departments"])
    assert body["count"] >= 1
    assert all("id" in d and "name" in d for d in body["departments"])
    ids = {d["id"] for d in body["departments"]}
    assert seeded_users["dept1"] in ids


@pytest.mark.p1
@pytest.mark.auth
def test_list_departments_org_b(client, seeded_users):
    r = client.get(
        "/api/auth/departments",
        params={"org_code": seeded_users["org_b"]["code"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    assert body["org_code"] == seeded_users["org_b"]["code"]
    # Org B department should not be confused with org1-only expectation
    assert any(d["id"] == seeded_users["dept_b"] for d in body["departments"])


@pytest.mark.p0
@pytest.mark.auth
def test_login_success(client, seeded_users):
    r = client.post(
        "/api/auth/login",
        json={
            "email": "student@comsats.edu.pk",
            "password": "student123",
            "org_code": "COMSATS-LHR",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == "student@comsats.edu.pk"
    assert body["role"] == "student"
    assert body["id"] == seeded_users["student"]["id"]
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["org_id"] == seeded_users["org1"]["id"]


@pytest.mark.p0
@pytest.mark.auth
def test_login_wrong_password_401(client):
    r = client.post(
        "/api/auth/login",
        json={
            "email": "student@comsats.edu.pk",
            "password": "wrong-password",
            "org_code": "COMSATS-LHR",
        },
    )
    assert r.status_code == 401
    assert "invalid" in r.json()["detail"].lower()


@pytest.mark.p0
@pytest.mark.auth
def test_login_unknown_email_401(client):
    r = client.post(
        "/api/auth/login",
        json={
            "email": "nobody@comsats.edu.pk",
            "password": "student123",
            "org_code": "COMSATS-LHR",
        },
    )
    assert r.status_code == 401


@pytest.mark.p0
@pytest.mark.auth
def test_login_admin_and_supervisor(client, seeded_users):
    for email, password, role, key in (
        ("admin@comsats.edu.pk", "admin123", "admin", "admin"),
        ("supervisor@comsats.edu.pk", "supervisor123", "supervisor", "supervisor"),
    ):
        r = client.post(
            "/api/auth/login",
            json={"email": email, "password": password, "org_code": "COMSATS-LHR"},
        )
        assert r.status_code == 200, email
        body = r.json()
        assert body["role"] == role
        assert body["id"] == seeded_users[key]["id"]


@pytest.mark.p0
@pytest.mark.auth
def test_login_jwt_claims_match_user(client, seeded_users):
    r = client.post(
        "/api/auth/login",
        json={
            "email": "admin@comsats.edu.pk",
            "password": "admin123",
            "org_code": "COMSATS-LHR",
        },
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    # Decode without verifying exp quirks — use app secret
    import os

    secret = os.environ.get("JWT_SECRET", "formatify_dev_jwt_secret_change_me")
    claims = jwt.decode(token, secret, algorithms=["HS256"])
    assert int(claims["user_id"]) == int(seeded_users["admin"]["id"])
    assert str(claims["sub"]) == str(seeded_users["admin"]["id"])
    assert int(claims["org_id"]) == int(seeded_users["org1"]["id"])
    assert claims["role"] == "admin"
    assert claims["email"] == "admin@comsats.edu.pk"
    assert claims.get("org_code", "").upper() == "COMSATS-LHR"
    assert claims.get("typ") == "access"
    assert "exp" in claims and "iat" in claims


@pytest.mark.p0
@pytest.mark.auth
def test_me_returns_profile(client, auth_headers, seeded_users):
    uid = seeded_users["student"]["id"]
    r = client.get(
        "/api/auth/me",
        params={"user_id": uid},
        headers=auth_headers["student"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == uid
    assert body["email"] == "student@comsats.edu.pk"
    assert body["role"] == "student"
    assert body["org_id"] == seeded_users["org1"]["id"]


@pytest.mark.p0
@pytest.mark.auth
def test_me_wrong_org_user_403(client, auth_headers, seeded_users):
    # student_b belongs to org B; querying with org1 JWT/context → 403
    r = client.get(
        "/api/auth/me",
        params={"user_id": seeded_users["student_b_id"]},
        headers=auth_headers["student"],
    )
    assert r.status_code == 403
    assert "organization" in r.json()["detail"].lower()


@pytest.mark.p1
@pytest.mark.auth
def test_me_unknown_user_401(client, auth_headers):
    r = client.get(
        "/api/auth/me",
        params={"user_id": 999999},
        headers=auth_headers["admin"],
    )
    assert r.status_code == 401


@pytest.mark.p0
@pytest.mark.auth
def test_change_password_success_then_login(client, seeded_users):
    uname = _unique("chgpw")
    email = f"{uname}@example.com"
    old_pw = "oldpass99"
    new_pw = "newpass99"
    signup = client.post(
        "/api/auth/signup",
        json={
            "username": uname,
            "email": email,
            "password": old_pw,
            "department_id": seeded_users["dept1"],
            "current_semester": 7,
            "org_code": "COMSATS-LHR",
        },
    )
    assert signup.status_code == 200, signup.text
    uid = signup.json()["id"]
    token = signup.json()["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Org-Code": "COMSATS-LHR",
    }

    r = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={
            "user_id": uid,
            "current_password": old_pw,
            "new_password": new_pw,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True

    fail_old = client.post(
        "/api/auth/login",
        json={"email": email, "password": old_pw, "org_code": "COMSATS-LHR"},
    )
    assert fail_old.status_code == 401

    ok_new = client.post(
        "/api/auth/login",
        json={"email": email, "password": new_pw, "org_code": "COMSATS-LHR"},
    )
    assert ok_new.status_code == 200
    assert ok_new.json()["id"] == uid


@pytest.mark.p0
@pytest.mark.auth
def test_change_password_too_short_rejected(client, auth_headers, seeded_users):
    r = client.post(
        "/api/auth/change-password",
        headers=auth_headers["student"],
        json={
            "user_id": seeded_users["student"]["id"],
            "current_password": "student123",
            "new_password": "12345",
        },
    )
    assert r.status_code == 400
    assert "6" in r.json()["detail"] or "character" in r.json()["detail"].lower()


@pytest.mark.p1
@pytest.mark.auth
def test_change_password_wrong_current_401(client, auth_headers, seeded_users):
    r = client.post(
        "/api/auth/change-password",
        headers=auth_headers["student"],
        json={
            "user_id": seeded_users["student"]["id"],
            "current_password": "definitely-wrong",
            "new_password": "newpass99",
        },
    )
    assert r.status_code == 401
    assert "current" in r.json()["detail"].lower()
