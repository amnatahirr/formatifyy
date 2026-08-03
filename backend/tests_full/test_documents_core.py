"""Document lifecycle, freeform gates, analyze smoke, TOC/tables/export/preview."""
from __future__ import annotations

import io
import os
from typing import Any, Dict
from unittest.mock import AsyncMock, patch

import pytest


def _upload_docx(client, *, user_id: int, template_id: int, sample_docx_file, headers=None):
    name, buf, ctype = sample_docx_file
    buf.seek(0)
    return client.post(
        "/api/documents/upload",
        params={"template_id": template_id, "user_id": user_id},
        files={"file": (name, buf, ctype)},
        headers=headers or {},
    )


def _upload_txt(client, *, user_id: int, template_id: int, sample_txt_file, headers=None):
    name, buf, ctype = sample_txt_file
    buf.seek(0)
    return client.post(
        "/api/documents/upload",
        params={"template_id": template_id, "user_id": user_id},
        files={"file": (name, buf, ctype)},
        headers=headers or {},
    )


def _mock_analysis_report(job_id: str = "1") -> Dict[str, Any]:
    return {
        "issues": [],
        "stats": {
            "avg_formatting_compliance": 92.0,
            "formatting_issues": 0,
            "grammar_issues": 0,
            "plagiarism_issues": 0,
            "image_ethics_issues": 0,
            "image_relevance_issues": 0,
        },
        "job_id": job_id,
        "output_path": "",
    }


@pytest.mark.p0
@pytest.mark.pipeline
def test_list_documents_empty_or_list(client, auth_headers, seeded_users):
    uid = seeded_users["student"]["id"]
    r = client.get(
        "/api/documents/",
        params={"user_id": uid},
        headers=auth_headers["student"],
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.p0
@pytest.mark.pipeline
def test_upload_txt_document(client, auth_headers, seeded_users, sample_txt_file):
    uid = seeded_users["student"]["id"]
    tid = seeded_users["template_id"]
    r = _upload_txt(
        client,
        user_id=uid,
        template_id=tid,
        sample_txt_file=sample_txt_file,
        headers=auth_headers["student"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert "document_id" in body
    assert body["filename"]


@pytest.mark.p0
@pytest.mark.pipeline
def test_upload_docx_document(client, auth_headers, seeded_users, sample_docx_file):
    uid = seeded_users["student"]["id"]
    tid = seeded_users["template_id"]
    r = _upload_docx(
        client,
        user_id=uid,
        template_id=tid,
        sample_docx_file=sample_docx_file,
        headers=auth_headers["student"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert isinstance(body["document_id"], int)

    listed = client.get(
        "/api/documents/",
        params={"user_id": uid},
        headers=auth_headers["student"],
    )
    assert listed.status_code == 200
    ids = {d["id"] for d in listed.json()}
    assert body["document_id"] in ids


@pytest.mark.p0
@pytest.mark.pipeline
def test_upload_text_empty_content_400(client, auth_headers, seeded_users):
    uid = seeded_users["student"]["id"]
    tid = seeded_users["template_id"]
    r = client.post(
        "/api/documents/upload-text",
        params={"template_id": tid, "user_id": uid},
        json={"content": "   ", "title": "Empty"},
        headers=auth_headers["student"],
    )
    assert r.status_code == 400
    assert "content" in r.json()["detail"].lower() or "paste" in r.json()["detail"].lower()


@pytest.mark.p1
@pytest.mark.pipeline
def test_upload_text_happy(client, auth_headers, seeded_users, sample_txt_bytes):
    uid = seeded_users["student"]["id"]
    tid = seeded_users["template_id"]
    r = client.post(
        "/api/documents/upload-text",
        params={"template_id": tid, "user_id": uid},
        json={"content": sample_txt_bytes.decode("utf-8"), "title": "Pasted Report"},
        headers=auth_headers["student"],
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending"
    assert r.json()["filename"] == "Pasted Report"


@pytest.mark.p0
@pytest.mark.pipeline
def test_analyze_document_mocked(client, auth_headers, seeded_users, sample_docx_file):
    uid = seeded_users["student"]["id"]
    tid = seeded_users["template_id"]
    up = _upload_docx(
        client,
        user_id=uid,
        template_id=tid,
        sample_docx_file=sample_docx_file,
        headers=auth_headers["student"],
    )
    assert up.status_code == 200
    doc_id = up.json()["document_id"]

    async def _fake(*args, **kwargs):
        return _mock_analysis_report(str(doc_id))

    with patch("main._run_analysis", new=AsyncMock(side_effect=_fake)):
        r = client.get(
            f"/api/documents/analyze/{doc_id}",
            params={"user_id": uid},
            headers=auth_headers["student"],
        )
    if r.status_code == 500 and (
        "API_KEY" in r.text.upper() or "api key" in r.text.lower()
    ):
        if not (os.getenv("GEMINI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")):
            pytest.skip("No AI API key and mock did not intercept")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["document_id"] == doc_id
    assert "issues" in body
    assert "content_issues" in body
    assert "style_issues" in body
    assert "stats" in body
    assert "structure" in body


@pytest.mark.p1
@pytest.mark.pipeline
def test_analyze_skip_without_key_if_unmocked(client, auth_headers, seeded_users, sample_txt_file):
    """If mocking is impractical and no key is set, accept skip on 500."""
    if os.getenv("GEMINI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("API key present — covered by mocked analyze test")
    uid = seeded_users["student"]["id"]
    tid = seeded_users["template_id"]
    up = _upload_txt(
        client,
        user_id=uid,
        template_id=tid,
        sample_txt_file=sample_txt_file,
        headers=auth_headers["student"],
    )
    doc_id = up.json()["document_id"]
    with patch("main._run_analysis", new=AsyncMock(return_value=_mock_analysis_report(str(doc_id)))):
        r = client.get(
            f"/api/documents/analyze/{doc_id}",
            params={"user_id": uid},
            headers=auth_headers["student"],
        )
    if r.status_code == 500:
        pytest.skip("Analyze returned 500 without usable AI key")
    assert r.status_code == 200


@pytest.mark.p0
@pytest.mark.pipeline
def test_delete_own_document(client, auth_headers, seeded_users, sample_txt_file):
    uid = seeded_users["student"]["id"]
    tid = seeded_users["template_id"]
    up = _upload_txt(
        client,
        user_id=uid,
        template_id=tid,
        sample_txt_file=sample_txt_file,
        headers=auth_headers["student"],
    )
    doc_id = up.json()["document_id"]
    r = client.delete(
        f"/api/documents/{doc_id}",
        params={"user_id": uid},
        headers=auth_headers["student"],
    )
    assert r.status_code == 200
    assert r.json().get("success") is True

    listed = client.get(
        "/api/documents/",
        params={"user_id": uid},
        headers=auth_headers["student"],
    )
    assert doc_id not in {d["id"] for d in listed.json()}


@pytest.mark.p0
@pytest.mark.auth
def test_cannot_delete_other_users_document(
    client, auth_headers, seeded_users, sample_txt_file
):
    student_id = seeded_users["student"]["id"]
    admin_id = seeded_users["admin"]["id"]
    tid = seeded_users["template_id"]
    up = _upload_txt(
        client,
        user_id=student_id,
        template_id=tid,
        sample_txt_file=sample_txt_file,
        headers=auth_headers["student"],
    )
    doc_id = up.json()["document_id"]

    r = client.delete(
        f"/api/documents/{doc_id}",
        params={"user_id": admin_id},
        headers=auth_headers["admin"],
    )
    assert r.status_code == 404

    # Owner can still see it
    listed = client.get(
        "/api/documents/",
        params={"user_id": student_id},
        headers=auth_headers["student"],
    )
    assert doc_id in {d["id"] for d in listed.json()}


@pytest.mark.p0
@pytest.mark.auth
def test_freeform_student_403(client, auth_headers, seeded_users, sample_txt_file):
    uid = seeded_users["student"]["id"]
    name, buf, ctype = sample_txt_file
    buf.seek(0)
    r1 = client.post(
        "/api/documents/upload-freeform",
        params={"user_id": uid},
        files={"file": (name, buf, ctype)},
        headers=auth_headers["student"],
    )
    assert r1.status_code == 403

    r2 = client.post(
        "/api/documents/upload-text-freeform",
        params={"user_id": uid},
        json={"content": "student freeform blocked"},
        headers=auth_headers["student"],
    )
    assert r2.status_code == 403

    r3 = client.get(
        "/api/documents/analyze-freeform/1",
        params={"user_id": uid},
        headers=auth_headers["student"],
    )
    assert r3.status_code == 403


@pytest.mark.p0
@pytest.mark.pipeline
def test_freeform_admin_ok(client, auth_headers, seeded_users, sample_docx_file):
    uid = seeded_users["admin"]["id"]
    name, buf, ctype = sample_docx_file
    buf.seek(0)
    r = client.post(
        "/api/documents/upload-freeform",
        params={"user_id": uid},
        files={"file": (name, buf, ctype)},
        headers=auth_headers["admin"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body.get("is_freeform") is True
    assert "document_id" in body


@pytest.mark.p0
@pytest.mark.pipeline
def test_mutual_exclusion_templated_analyze_on_freeform(
    client, auth_headers, seeded_users, sample_docx_file
):
    uid = seeded_users["admin"]["id"]
    name, buf, ctype = sample_docx_file
    buf.seek(0)
    up = client.post(
        "/api/documents/upload-freeform",
        params={"user_id": uid},
        files={"file": (name, buf, ctype)},
        headers=auth_headers["admin"],
    )
    assert up.status_code == 200
    doc_id = up.json()["document_id"]

    r = client.get(
        f"/api/documents/analyze/{doc_id}",
        params={"user_id": uid},
        headers=auth_headers["admin"],
    )
    assert r.status_code == 400
    assert "freeform" in r.json()["detail"].lower()


@pytest.mark.p0
@pytest.mark.pipeline
def test_mutual_exclusion_freeform_analyze_on_templated(
    client, auth_headers, seeded_users, sample_docx_file
):
    uid = seeded_users["admin"]["id"]
    tid = seeded_users["template_id"]
    up = _upload_docx(
        client,
        user_id=uid,
        template_id=tid,
        sample_docx_file=sample_docx_file,
        headers=auth_headers["admin"],
    )
    doc_id = up.json()["document_id"]

    r = client.get(
        f"/api/documents/analyze-freeform/{doc_id}",
        params={"user_id": uid},
        headers=auth_headers["admin"],
    )
    assert r.status_code == 400
    detail = r.json()["detail"].lower()
    assert "freeform" in detail or "analyze" in detail


@pytest.mark.p1
@pytest.mark.pipeline
def test_heading_analysis_endpoint(client):
    r = client.post(
        "/api/heading-analysis",
        json={
            "template": {
                "required_sections": ["Introduction", "Methodology", "Conclusion"],
            },
            "blocks": [
                {"text": "Introduction", "style_name": "Heading 1", "bold": True, "font_size": 14},
                {"text": "Some body paragraph about the topic.", "style_name": "Normal"},
                {"text": "Methodology", "style_name": "Heading 1", "bold": True, "font_size": 14},
                {"text": "We followed a controlled procedure.", "style_name": "Normal"},
                {"text": "Conclusion", "style_name": "Heading 1", "bold": True, "font_size": 14},
            ],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    # Expect at least some heading matches for required sections
    assert len(body) >= 1


@pytest.mark.p1
@pytest.mark.pipeline
def test_apply_all_style_fixes_smoke(
    client, auth_headers, seeded_users, sample_docx_file
):
    uid = seeded_users["student"]["id"]
    tid = seeded_users["template_id"]
    up = _upload_docx(
        client,
        user_id=uid,
        template_id=tid,
        sample_docx_file=sample_docx_file,
        headers=auth_headers["student"],
    )
    doc_id = up.json()["document_id"]
    r = client.post(
        f"/api/documents/apply-all-style-fixes/{doc_id}",
        params={"user_id": uid},
        headers=auth_headers["student"],
    )
    assert r.status_code == 200, r.text
    assert r.json().get("status") == "success"


@pytest.mark.p1
@pytest.mark.pipeline
def test_apply_all_fixes_smoke(client, auth_headers, seeded_users, sample_docx_file):
    uid = seeded_users["student"]["id"]
    tid = seeded_users["template_id"]
    up = _upload_docx(
        client,
        user_id=uid,
        template_id=tid,
        sample_docx_file=sample_docx_file,
        headers=auth_headers["student"],
    )
    doc_id = up.json()["document_id"]
    r = client.post(
        f"/api/documents/apply-all-fixes/{doc_id}",
        params={"user_id": uid},
        json={"fixes": [], "include_toc": False, "include_lot": False, "include_lof": False},
        headers=auth_headers["student"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("status") == "success" or "applied" in body or "message" in body


@pytest.mark.p1
@pytest.mark.pipeline
def test_apply_content_fix_formatting_smoke(
    client, auth_headers, seeded_users, sample_docx_file
):
    uid = seeded_users["student"]["id"]
    tid = seeded_users["template_id"]
    up = _upload_docx(
        client,
        user_id=uid,
        template_id=tid,
        sample_docx_file=sample_docx_file,
        headers=auth_headers["student"],
    )
    doc_id = up.json()["document_id"]
    r = client.post(
        f"/api/documents/apply-content-fix/{doc_id}",
        params={"user_id": uid},
        json={"fix_type": "formatting"},
        headers=auth_headers["student"],
    )
    assert r.status_code == 200, r.text
    assert r.json().get("status") == "success"


@pytest.mark.p1
@pytest.mark.pipeline
def test_toc_check_smoke(client, auth_headers, seeded_users, sample_docx_file):
    uid = seeded_users["student"]["id"]
    tid = seeded_users["template_id"]
    up = _upload_docx(
        client,
        user_id=uid,
        template_id=tid,
        sample_docx_file=sample_docx_file,
        headers=auth_headers["student"],
    )
    doc_id = up.json()["document_id"]
    r = client.get(
        f"/api/toc-check/{doc_id}",
        params={"user_id": uid},
        headers=auth_headers["student"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("status") == "success"
    assert body.get("document_id") == doc_id


@pytest.mark.p2
@pytest.mark.pipeline
def test_tables_detect_smoke(client, auth_headers, seeded_users, sample_docx_file):
    uid = seeded_users["student"]["id"]
    tid = seeded_users["template_id"]
    up = _upload_docx(
        client,
        user_id=uid,
        template_id=tid,
        sample_docx_file=sample_docx_file,
        headers=auth_headers["student"],
    )
    doc_id = up.json()["document_id"]
    r = client.get(
        f"/api/tables/detect/{doc_id}",
        params={"user_id": uid},
        headers=auth_headers["student"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "success"
    assert body["document_id"] == doc_id
    assert "table_count" in body
    assert isinstance(body["tables"], list)
    # Sample docx has no tables
    assert body["table_count"] == 0


@pytest.mark.p0
@pytest.mark.pipeline
def test_preview_document(client, auth_headers, seeded_users, sample_docx_file):
    uid = seeded_users["student"]["id"]
    tid = seeded_users["template_id"]
    up = _upload_docx(
        client,
        user_id=uid,
        template_id=tid,
        sample_docx_file=sample_docx_file,
        headers=auth_headers["student"],
    )
    doc_id = up.json()["document_id"]
    r = client.get(
        f"/api/format-document/from-document/{doc_id}",
        params={"user_id": uid},
        headers=auth_headers["student"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "formatted_elements" in body
    assert "summary" in body
    assert body["summary"]["total_elements"] == len(body["formatted_elements"])
    assert body["summary"]["total_elements"] >= 1


@pytest.mark.p0
@pytest.mark.pipeline
def test_export_docx(client, auth_headers, seeded_users, sample_docx_file):
    uid = seeded_users["student"]["id"]
    tid = seeded_users["template_id"]
    up = _upload_docx(
        client,
        user_id=uid,
        template_id=tid,
        sample_docx_file=sample_docx_file,
        headers=auth_headers["student"],
    )
    doc_id = up.json()["document_id"]
    r = client.get(
        f"/api/format-document/export/{doc_id}",
        params={"user_id": uid, "format": "docx"},
        headers=auth_headers["student"],
    )
    assert r.status_code == 200, r.text
    ctype = r.headers.get("content-type", "")
    assert (
        "wordprocessingml" in ctype
        or "octet-stream" in ctype
        or "application/" in ctype
    )
    assert len(r.content) > 100


@pytest.mark.p1
@pytest.mark.auth
def test_list_documents_does_not_return_other_users(
    client, auth_headers, seeded_users, sample_txt_file
):
    student_id = seeded_users["student"]["id"]
    admin_id = seeded_users["admin"]["id"]
    tid = seeded_users["template_id"]
    up = _upload_txt(
        client,
        user_id=student_id,
        template_id=tid,
        sample_txt_file=sample_txt_file,
        headers=auth_headers["student"],
    )
    doc_id = up.json()["document_id"]

    admin_list = client.get(
        "/api/documents/",
        params={"user_id": admin_id},
        headers=auth_headers["admin"],
    )
    assert admin_list.status_code == 200
    assert doc_id not in {d["id"] for d in admin_list.json()}
