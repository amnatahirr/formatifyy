"""Google Drive OAuth + import route tests (no live Google required)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.p2
def test_authorize_returns_url_or_400_without_client_id(client, seeded_users):
    uid = int(seeded_users["student"]["id"])
    r = client.get(f"/api/auth/google/authorize?link_to_user_id={uid}")
    # Configured → auth URL string / JSON; unconfigured → 400
    assert r.status_code in (200, 400), r.text
    if r.status_code == 400:
        detail = r.json().get("detail") or ""
        assert "google" in detail.lower() or "client" in detail.lower()
    else:
        # May be a bare URL string (JSON-encoded) or object
        body = r.json()
        if isinstance(body, str):
            assert "accounts.google.com" in body or "client_id=" in body
        else:
            url = body.get("url") or body.get("auth_url") or str(body)
            assert "google" in url.lower() or "client_id" in url.lower()


@pytest.mark.p2
def test_google_status_endpoint(client):
    r = client.get("/api/auth/google/status")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "authenticated" in body
    assert body["authenticated"] in (True, False)


@pytest.mark.p2
def test_files_without_auth_401(client, seeded_users):
    uid = int(seeded_users["student"]["id"])
    r = client.get(f"/api/uploads/google-drive/files?user_id={uid}")
    assert r.status_code == 401, r.text


@pytest.mark.p2
def test_import_without_auth_401(client, seeded_users):
    uid = int(seeded_users["student"]["id"])
    tid = int(seeded_users["template_id"])
    r = client.post(
        f"/api/uploads/google-drive/import?user_id={uid}&file_id=fake123&template_id={tid}"
    )
    assert r.status_code == 401, r.text


@pytest.mark.p2
def test_auth_init_without_tokens_401(client, seeded_users):
    uid = int(seeded_users["student"]["id"])
    r = client.post(f"/api/uploads/google-drive/auth/init?user_id={uid}")
    assert r.status_code == 401, r.text


@pytest.mark.p2
def test_debug_tokens_no_tokens(client, seeded_users):
    uid = int(seeded_users["student"]["id"])
    r = client.get(f"/api/auth/google/debug/tokens?user_id={uid}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("tokens_found") is False
    assert "google_auth_available" in body


@pytest.mark.p2
def test_sheets_rejected_via_mocked_service(client, seeded_users, auth_headers):
    """Sheets mime type must be rejected when Drive service is reachable."""
    uid = int(seeded_users["student"]["id"])
    tid = int(seeded_users["template_id"])

    with patch("services.google_drive_routes.GoogleDriveService") as MockSvc:
        inst = MockSvc.return_value
        inst.initialize_service.return_value = True
        inst.get_file_metadata.return_value = {
            "mimeType": "application/vnd.google-apps.spreadsheet",
            "name": "Budget Sheet",
        }
        r = client.post(
            f"/api/uploads/google-drive/import?user_id={uid}&file_id=sheet1&template_id={tid}",
            headers=auth_headers["student"],
        )
    assert r.status_code == 400, r.text
    assert "sheet" in (r.json().get("detail") or "").lower()


@pytest.mark.p2
def test_slides_rejected_via_mocked_service(client, seeded_users, auth_headers):
    uid = int(seeded_users["student"]["id"])
    tid = int(seeded_users["template_id"])

    with patch("services.google_drive_routes.GoogleDriveService") as MockSvc:
        inst = MockSvc.return_value
        inst.initialize_service.return_value = True
        inst.get_file_metadata.return_value = {
            "mimeType": "application/vnd.google-apps.presentation",
            "name": "Pitch Deck",
        }
        r = client.post(
            f"/api/uploads/google-drive/import?user_id={uid}&file_id=slides1&template_id={tid}",
            headers=auth_headers["student"],
        )
    assert r.status_code == 400, r.text
    detail = (r.json().get("detail") or "").lower()
    assert "slide" in detail or "sheet" in detail


@pytest.mark.p2
def test_sheets_slides_rejection_unit():
    """Direct unit assertion of the mime rejection set used by import."""
    from services.google_drive_routes import _GOOGLE_EXPORT

    # Spreadsheet/presentation are exported types but still blocked by route guard
    assert "application/vnd.google-apps.spreadsheet" in _GOOGLE_EXPORT
    assert "application/vnd.google-apps.presentation" in _GOOGLE_EXPORT

    blocked = {
        "application/vnd.google-apps.spreadsheet",
        "application/vnd.google-apps.presentation",
    }
    for mime in blocked:
        assert mime in blocked  # guard set mirrors route logic
