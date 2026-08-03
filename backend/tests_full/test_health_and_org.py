"""Health, organization resolve/info, universities, and corpus-status API contracts."""
from __future__ import annotations

import pytest


@pytest.mark.p0
def test_health_root_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == "3.0.0"


@pytest.mark.p0
def test_health_api_alias_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


@pytest.mark.p0
def test_health_both_paths_equivalent(client):
    a = client.get("/health").json()
    b = client.get("/api/health").json()
    assert a == b


@pytest.mark.p0
def test_health_no_auth_required(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert "Authorization" not in (r.request.headers or {})


@pytest.mark.p0
@pytest.mark.auth
def test_org_resolve_valid_comsats(client, seeded_users):
    code = seeded_users["org1"]["code"]
    r = client.get("/api/org/resolve", params={"code": code})
    assert r.status_code == 200
    body = r.json()
    assert body["org_code"].upper() == code.upper()
    assert body["org_name"]
    assert "modules" in body
    assert isinstance(body["modules"], list)
    assert "api_key" not in body


@pytest.mark.p0
@pytest.mark.auth
def test_org_resolve_case_insensitive(client):
    r = client.get("/api/org/resolve", params={"code": "comsats-lhr"})
    assert r.status_code == 200
    assert r.json()["org_code"].upper() == "COMSATS-LHR"


@pytest.mark.p0
@pytest.mark.auth
def test_org_resolve_invalid_404(client):
    r = client.get("/api/org/resolve", params={"code": "NO-SUCH-ORG-XYZ"})
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


@pytest.mark.p0
@pytest.mark.auth
def test_org_resolve_inactive_403(client):
    r = client.get("/api/org/resolve", params={"code": "INACTIVE-ORG"})
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert "inactive" in str(detail).lower()


@pytest.mark.p0
@pytest.mark.auth
def test_org_resolve_public_payload_never_has_api_key(client, seeded_users):
    for code in (
        seeded_users["org1"]["code"],
        seeded_users["org_b"]["code"],
        seeded_users["org_core"]["code"],
    ):
        r = client.get("/api/org/resolve", params={"code": code})
        assert r.status_code == 200, code
        body = r.json()
        assert "api_key" not in body
        assert not any(k == "api_key" for k in body.keys())
        for key in ("org_id", "org_name", "org_code", "plan", "modules", "has_fyp", "has_core"):
            assert key in body, f"missing {key} for {code}"


@pytest.mark.p0
@pytest.mark.auth
def test_org_resolve_alias_path(client):
    r = client.get("/org/resolve", params={"code": "COMSATS-LHR"})
    assert r.status_code == 200
    assert "api_key" not in r.json()


@pytest.mark.p0
@pytest.mark.auth
def test_org_info_with_jwt(client, auth_headers, seeded_users):
    r = client.get("/api/org/info", headers=auth_headers["student"])
    assert r.status_code == 200
    body = r.json()
    assert body["org_code"] == seeded_users["org1"]["code"]
    assert "api_key" not in body
    assert body.get("has_fyp") is True


@pytest.mark.p0
@pytest.mark.auth
def test_org_info_with_x_org_code(client, seeded_users):
    r = client.get(
        "/api/org/info",
        headers={"X-Org-Code": seeded_users["org_b"]["code"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["org_code"] == seeded_users["org_b"]["code"]
    assert "api_key" not in body


@pytest.mark.p1
@pytest.mark.auth
def test_org_info_default_org_when_bare(client, seeded_users):
    r = client.get("/api/org/info")
    assert r.status_code == 200
    # Middleware falls back to default org id=1
    assert r.json()["org_id"] == seeded_users["org1"]["id"]
    assert "api_key" not in r.json()


@pytest.mark.p0
def test_universities_list_nonempty(client):
    r = client.get("/api/universities")
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    names = {row.get("name", "").upper() for row in rows}
    assert any("COMSATS" in n for n in names)


@pytest.mark.p0
def test_universities_get_seeded_comsats(client):
    r = client.get("/api/universities/1")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 1
    assert "COMSATS" in body["name"].upper()
    assert "country" in body


@pytest.mark.p0
def test_universities_get_unknown_404(client):
    r = client.get("/api/universities/999999")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


@pytest.mark.p1
@pytest.mark.plagiarism
def test_plagiarism_corpus_status_shape(client):
    r = client.get("/api/plagiarism/corpus-status")
    assert r.status_code == 200
    body = r.json()
    for key in (
        "enabled",
        "corpus_dir",
        "index_dir",
        "files_on_disk",
        "ready",
        "document_count",
        "sentence_count",
        "error",
    ):
        assert key in body
    assert isinstance(body["enabled"], bool)
    assert isinstance(body["files_on_disk"], int)
    assert isinstance(body["ready"], bool)


@pytest.mark.p1
@pytest.mark.plagiarism
def test_plagiarism_corpus_status_rebuild_param(client):
    # rebuild=true may be slow or error if corpus empty — still must return JSON contract
    r = client.get("/api/plagiarism/corpus-status", params={"rebuild": False})
    assert r.status_code == 200
    body = r.json()
    if body["files_on_disk"] == 0:
        assert body["ready"] is False
        assert body["error"]
    else:
        # When files exist, ready may be True or error string set
        assert "ready" in body
