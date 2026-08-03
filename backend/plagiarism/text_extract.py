"""
plagiarism/text_extract.py — Extract plain text from corpus files (TXT / DOCX / PDF).
"""

from __future__ import annotations

from pathlib import Path
from typing import List

SUPPORTED_EXTENSIONS = {".txt", ".docx", ".pdf"}


def extract_text_from_file(path: Path) -> str:
    """
    Extract UTF-8 plain text from a single corpus / report file.

    Raises ValueError for unsupported types or unreadable content.
    """
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".txt":
        return path.read_text(encoding="utf-8", errors="replace").strip()
    if ext == ".docx":
        return _extract_docx(path)
    if ext == ".pdf":
        return _extract_pdf(path)
    raise ValueError(
        f"Unsupported corpus file type '{ext}' for {path.name}. "
        f"Use one of: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
    )


def iter_corpus_files(corpus_dir: Path) -> List[Path]:
    """Return sorted supported files under corpus_dir (non-recursive)."""
    corpus_dir = Path(corpus_dir)
    if not corpus_dir.exists():
        return []
    return sorted(
        p for p in corpus_dir.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def _extract_docx(path: Path) -> str:
    from docx import Document

    doc = Document(str(path))
    parts: List[str] = []
    for para in doc.paragraphs:
        text = (para.text or "").strip()
        if text:
            parts.append(text)
    # Tables often hold abstract / methodology text in FYP reports.
    for table in doc.tables:
        for row in table.rows:
            cells = [(c.text or "").strip() for c in row.cells]
            row_text = " | ".join(c for c in cells if c)
            if row_text:
                parts.append(row_text)
    return "\n".join(parts).strip()


def _extract_pdf(path: Path) -> str:
    from pdf_io import extract_pdf_plain_text

    text = extract_pdf_plain_text(str(path))
    if not text:
        raise ValueError(f"No extractable text in PDF: {path.name}")
    return text
