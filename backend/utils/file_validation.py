"""
file_validation.py — Validate uploaded document files before they are
persisted to disk or the database.

Raises CorruptedFileError with a user-friendly message when a file is
empty, corrupted, mis-named, or password-protected.
"""

from __future__ import annotations

import os
import zipfile
from io import BytesIO


class CorruptedFileError(Exception):
    """Raised when an uploaded file is empty, corrupted, or unreadable."""


_ZIP_SIGNATURE = b"PK\x03\x04"
_OLE_SIGNATURE = b"\xd0\xcf\x11\xe0"


def _ext(filename: str) -> str:
    """Return the lower-cased file extension (e.g. '.docx')."""
    return os.path.splitext(filename or "")[-1].lower()


def _validate_docx(data: bytes, filename: str) -> None:
    # Legacy .doc masquerading as .docx
    if data[:4] == _OLE_SIGNATURE:
        raise CorruptedFileError(
            "This file appears to be a legacy .doc document renamed to .docx. "
            "Please open it in Microsoft Word, choose File → Save As, "
            "select the .docx format, and upload the new file."
        )

    # Not a ZIP at all
    if data[:4] != _ZIP_SIGNATURE:
        raise CorruptedFileError(
            "The uploaded .docx file is not a valid document. "
            "It may have been corrupted during transfer or is not actually "
            "a Word document. Please try uploading again."
        )

    # ZIP-level checks
    try:
        zf = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile:
        raise CorruptedFileError(
            "The uploaded .docx file is damaged and cannot be opened. "
            "Please try saving it again in Word and re-uploading."
        )

    # CRC / member integrity
    bad = zf.testzip()
    if bad is not None:
        raise CorruptedFileError(
            f"The uploaded .docx file contains a corrupted component ({bad}). "
            "Please re-save the document in Word and try again."
        )

    # Required internal files
    names = set(zf.namelist())
    if "[Content_Types].xml" not in names:
        raise CorruptedFileError(
            "The uploaded file looks like a ZIP archive but is not a valid "
            ".docx document (missing [Content_Types].xml). "
            "Please make sure you are uploading a Word document."
        )
    if "word/document.xml" not in names:
        raise CorruptedFileError(
            "The uploaded .docx file is incomplete — it is missing the "
            "main document content. Please re-save it in Word and try again."
        )

    # python-docx sanity check
    try:
        from docx import Document
        Document(BytesIO(data))
    except Exception as exc:
        raise CorruptedFileError(
            "The uploaded .docx file could not be read. It may be corrupted "
            "or created by an unsupported tool. Please open it in Microsoft "
            "Word, re-save as .docx, and upload again."
        ) from exc


def _validate_pdf(data: bytes, filename: str) -> None:
    if not data[:5].startswith(b"%PDF"):
        raise CorruptedFileError(
            "The uploaded file does not appear to be a valid PDF. "
            "Please make sure you are uploading the correct file."
        )

    try:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(data))
    except Exception as exc:
        raise CorruptedFileError(
            "The uploaded PDF file is damaged and cannot be opened. "
            "Please try re-exporting it and uploading again."
        ) from exc

    if reader.is_encrypted:
        raise CorruptedFileError(
            "The uploaded PDF is password-protected. Please remove the "
            "password (File → Properties → Security in Adobe Acrobat) "
            "and upload the unprotected file."
        )


def validate_upload(filename: str, data: bytes) -> None:
    """
    Validate raw upload bytes *before* anything is written to disk or database.

    Raises CorruptedFileError with a user-friendly message for:
      • empty files
      • .docx that isn't a valid ZIP (PK\\x03\\x04 signature)
      • .docx that is really a legacy .doc (D0 CF 11 E0)
      • .docx missing required internal files or with bad CRC
      • .docx that python-docx cannot open
      • .pdf that doesn't start with %PDF
      • .pdf that pypdf cannot read or that is encrypted
    """
    if not data:
        raise CorruptedFileError(
            "The file is empty. Please select a valid document and try again."
        )

    ext = _ext(filename)

    if ext == ".docx":
        _validate_docx(data, filename)
    elif ext == ".pdf":
        _validate_pdf(data, filename)
    # .txt files need no binary validation.
