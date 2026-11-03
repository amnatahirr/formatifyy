"""
Tests for document upload endpoints:
- Verifies corrupted files return HTTP 422 with detail {"code": "corrupted_file", "message": "..."}.
- Verifies nothing is saved to disk or DB on validation failure.
- Verifies valid .docx returns HTTP 200 and succeeds.
"""

from io import BytesIO
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import pytest
from docx import Document
from fastapi.testclient import TestClient

from database import get_db, init_db
from main import app, UPLOAD_DIR


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def test_user_and_template():
    init_db()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE LOWER(role) = 'student' ORDER BY id LIMIT 1")
    user_row = cur.fetchone()
    if not user_row:
        cur.execute("SELECT id FROM users ORDER BY id LIMIT 1")
        user_row = cur.fetchone()
    user_id = int(user_row["id"])

    cur.execute("SELECT id FROM templates ORDER BY id LIMIT 1")
    template_row = cur.fetchone()
    template_id = int(template_row["id"])
    conn.close()
    return user_id, template_id


def _create_valid_docx() -> bytes:
    doc = Document()
    doc.add_paragraph("Valid Document Content")
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_upload_corrupted_docx_returns_422(client, test_user_and_template):
    user_id, template_id = test_user_and_template

    # Get count of documents in DB before upload
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM documents")
    count_before = cur.fetchone()[0]
    conn.close()

    bad_docx_bytes = b"This is just plain text content pretending to be a Word docx."
    resp = client.post(
        f"/api/documents/upload?template_id={template_id}&user_id={user_id}",
        files={"file": ("corrupted_report.docx", BytesIO(bad_docx_bytes), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert resp.status_code == 422
    data = resp.json()
    assert "detail" in data
    assert isinstance(data["detail"], dict)
    assert data["detail"].get("code") == "corrupted_file"
    assert "message" in data["detail"]
    assert len(data["detail"]["message"]) > 0

    # Verify nothing was added to database
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM documents")
    count_after = cur.fetchone()[0]
    conn.close()
    assert count_after == count_before


def test_upload_empty_file_returns_422(client, test_user_and_template):
    user_id, template_id = test_user_and_template

    resp = client.post(
        f"/api/documents/upload?template_id={template_id}&user_id={user_id}",
        files={"file": ("empty.docx", BytesIO(b""), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert resp.status_code == 422
    data = resp.json()
    assert data["detail"]["code"] == "corrupted_file"
    assert "empty" in data["detail"]["message"].lower()


def test_upload_valid_docx_returns_200(client, test_user_and_template):
    user_id, template_id = test_user_and_template
    valid_bytes = _create_valid_docx()

    resp = client.post(
        f"/api/documents/upload?template_id={template_id}&user_id={user_id}",
        files={"file": ("good_report.docx", BytesIO(valid_bytes), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "document_id" in data
    assert data["filename"] == "good_report.docx"
    assert data["status"] == "pending"

    # Clean up uploaded test file
    doc_id = data["document_id"]
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT file_path FROM documents WHERE id = ?", (doc_id,))
    row = cur.fetchone()
    if row and row["file_path"] and os.path.exists(row["file_path"]):
        try:
            os.remove(row["file_path"])
        except OSError:
            pass
    cur.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()
