"""
Unit tests for validate_upload in backend/utils/file_validation.py.
"""

from io import BytesIO
import pytest
from docx import Document
from pypdf import PdfWriter

from utils.file_validation import CorruptedFileError, validate_upload


def _create_valid_docx() -> bytes:
    doc = Document()
    doc.add_paragraph("Valid Document Content")
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _create_encrypted_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt("secret_password")
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_empty_file():
    with pytest.raises(CorruptedFileError) as exc_info:
        validate_upload("test.docx", b"")
    assert "empty" in str(exc_info.value).lower()


def test_txt_renamed_to_docx():
    bad_data = b"This is just plain text content pretending to be docx."
    with pytest.raises(CorruptedFileError) as exc_info:
        validate_upload("fake.docx", bad_data)
    assert "not a valid document" in str(exc_info.value) or "corrupted" in str(exc_info.value).lower()


def test_truncated_docx():
    valid = _create_valid_docx()
    truncated = valid[:80]  # truncate midway through zip header/content
    with pytest.raises(CorruptedFileError):
        validate_upload("truncated.docx", truncated)


def test_legacy_doc_renamed_to_docx():
    # OLE compound file header: D0 CF 11 E0
    ole_header = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 500
    with pytest.raises(CorruptedFileError) as exc_info:
        validate_upload("legacy.docx", ole_header)
    msg = str(exc_info.value).lower()
    assert "legacy .doc" in msg or "re-save" in msg or "save as" in msg


def test_non_pdf_renamed_to_pdf():
    bad_data = b"This is not a pdf file at all."
    with pytest.raises(CorruptedFileError) as exc_info:
        validate_upload("fake.pdf", bad_data)
    assert "not appear to be a valid pdf" in str(exc_info.value).lower() or "damaged" in str(exc_info.value).lower()


def test_encrypted_pdf():
    encrypted = _create_encrypted_pdf()
    with pytest.raises(CorruptedFileError) as exc_info:
        validate_upload("protected.pdf", encrypted)
    msg = str(exc_info.value).lower()
    assert "password" in msg


def test_valid_docx():
    valid = _create_valid_docx()
    # Should not raise any exception
    validate_upload("valid_document.docx", valid)
