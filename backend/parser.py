"""
parser.py — Ingestion layer for Formatify.

Converts uploaded .docx, .pdf, .txt files (or pasted text) into a structured
DocumentModel with typed paragraph and image blocks.
"""

from __future__ import annotations

import base64
import io
import os
import re
from typing import List, Tuple

from models import DocumentModel, ParagraphBlock, ImageBlock


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def parse_file(file_path: str, filename: str) -> DocumentModel:
    """
    Detect file type by extension and delegate to the appropriate parser.
    Returns a fully populated DocumentModel.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".docx":
        return _parse_docx(file_path, filename)
    elif ext == ".pdf":
        return _parse_pdf(file_path, filename)
    elif ext == ".txt":
        return _parse_txt(file_path, filename)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def parse_text(text: str, title: str = "pasted_text.txt") -> DocumentModel:
    """Parse raw pasted text into a DocumentModel (single page, no images)."""
    lines = text.split("\n")
    paragraphs: List[ParagraphBlock] = []
    heading_context = ""
    para_idx = 0

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        prev_blank = idx == 0 or not lines[idx - 1].strip()
        next_blank = idx == len(lines) - 1 or not lines[idx + 1].strip()

        style = _guess_style(stripped)
        prefix, _ = _extract_numbering_prefix(stripped)
        if style.startswith("Heading"):
            heading_context = stripped

        paragraphs.append(
            ParagraphBlock(
                paragraph_id=f"p{para_idx}",
                page_number=1,
                heading_context=heading_context,
                style=style,
                text=stripped,
                style_name=style,
                numbering_prefix=prefix,
                prev_blank=prev_blank,
                next_blank=next_blank,
            )
        )
        para_idx += 1

    return DocumentModel(
        filename=title,
        total_pages=1,
        paragraphs=paragraphs,
        images=[],
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DOCX PARSER
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_docx(file_path: str, filename: str) -> DocumentModel:
    from docx import Document as DocxDocument
    from lxml import etree
    from PIL import Image as PILImage

    doc = DocxDocument(file_path)
    paragraphs: List[ParagraphBlock] = []
    images: List[ImageBlock] = []

    # ── Extract images keyed by relationship ID ──────────────────────────────
    rel_images: dict[str, bytes] = {}
    for rel_id, rel in doc.part.rels.items():
        if "image" in (rel.target_ref or ""):
            try:
                rel_images[rel_id] = rel.target_part.blob
            except Exception:
                continue

    # ── Estimate page breaks ─────────────────────────────────────────────────
    # python-docx does not expose page numbers directly; we track explicit
    # page-break elements as a best-effort heuristic.
    page = 1
    heading_context = ""
    img_counter = 0

    for para_idx, para in enumerate(doc.paragraphs):
        # Detect explicit page breaks in the XML
        xml_str = etree.tostring(para._element, encoding="unicode")
        page_breaks = xml_str.count('w:br') and 'w:type="page"' in xml_str
        if page_breaks:
            page += 1

        # Detect section page breaks
        sect_pr = para._element.findall(
            ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sectPr"
        )
        if sect_pr:
            page += 1

        text = para.text.strip()
        style_name = (para.style.name or "Normal") if para.style else "Normal"
        font_size, is_bold = _extract_run_format(para)
        prefix, _ = _extract_numbering_prefix(text)

        # Map Word style → our normalised style
        style = _normalise_docx_style(style_name, text)
        if style.startswith("Heading"):
            heading_context = text

        prev_blank = para_idx == 0 or not doc.paragraphs[para_idx - 1].text.strip()
        next_blank = (
            para_idx == len(doc.paragraphs) - 1
            or not doc.paragraphs[para_idx + 1].text.strip()
        )

        # ── Check for embedded images ────────────────────────────────────────
        r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        blip_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
        for blip in para._element.iter(f"{{{blip_ns}}}blip"):
            embed = blip.get(f"{{{r_ns}}}embed")
            if embed and embed in rel_images:
                try:
                    img_bytes = rel_images[embed]
                    b64 = base64.b64encode(img_bytes).decode("utf-8")
                    print("=" * 60)
                    print(f"Image extracted: img{img_counter}")
                    print(f"Length: {len(b64)}")
                    print(f"Starts with: {b64[:50]}")
                    print("=" * 60)
                    # Infer a caption from the next text run or leave empty
                    caption = _extract_caption_near(doc.paragraphs, para_idx)
                    images.append(
                        ImageBlock(
                            image_id=f"img{img_counter}",
                            page_number=page,
                            base64=b64,
                            caption=caption,
                            paragraph_id=f"p{para_idx}",
                        )
                    )
                    img_counter += 1
                except Exception:
                    continue

        # Always keep paragraphs that contain images, even if text is empty,
        # so image paragraph_id anchors resolve during analysis.
        has_image = any(
            True
            for blip in para._element.iter(f"{{{blip_ns}}}blip")
            if blip.get(f"{{{r_ns}}}embed") in rel_images
        )

        if text or has_image:
            paragraphs.append(
                ParagraphBlock(
                    paragraph_id=f"p{para_idx}",
                    page_number=page,
                    heading_context=heading_context,
                    style=style,
                    text=text,
                    font_size=font_size,
                    bold=is_bold,
                    style_name=style_name,
                    numbering_prefix=prefix,
                    prev_blank=prev_blank,
                    next_blank=next_blank,
                )
            )

    total_pages = page if paragraphs else 1
    return DocumentModel(
        filename=filename,
        total_pages=total_pages,
        paragraphs=paragraphs,
        images=images,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PDF PARSER  (PyMuPDF when available, pypdf fallback)
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_pdf(file_path: str, filename: str) -> DocumentModel:
    from pdf_io import extract_pdf, merge_pdf_lines_to_paragraphs, looks_like_heading_line

    result = extract_pdf(file_path)
    paragraphs: List[ParagraphBlock] = []
    images: List[ImageBlock] = []
    heading_context = ""
    para_counter = 0
    img_counter = 0

    # Merge visual wrap lines into real paragraphs (same as PDF→DOCX path).
    raw_lines: List[str] = []
    line_page: List[int] = []
    for page in result.pages:
        if raw_lines:
            raw_lines.append("")
            line_page.append(page.page_number)
        for text, _, _ in page.lines:
            if text.strip():
                raw_lines.append(text)
                line_page.append(page.page_number)

    merged = merge_pdf_lines_to_paragraphs(raw_lines)
    # Approximate page number: use first page that contributed (fallback 1)
    page_guess = result.pages[0].page_number if result.pages else 1
    for text in merged:
        is_head = looks_like_heading_line(text)
        style = "Heading 1" if is_head else _guess_style_from_font(text, 12.0, False)
        if is_head or style.startswith("Heading"):
            heading_context = text
            style = style if style.startswith("Heading") else "Heading 1"
        prefix, _ = _extract_numbering_prefix(text)
        paragraphs.append(
            ParagraphBlock(
                paragraph_id=f"p{para_counter}",
                page_number=page_guess,
                heading_context=heading_context,
                style=style,
                text=text,
                font_size=16.0 if style.startswith("Heading") else 12.0,
                bold=style.startswith("Heading"),
                style_name=style,
                numbering_prefix=prefix,
            )
        )
        para_counter += 1

    for page in result.pages:
        for b64 in page.images_b64:
            images.append(
                ImageBlock(
                    image_id=f"img{img_counter}",
                    page_number=page.page_number,
                    base64=b64,
                    caption="",
                )
            )
            img_counter += 1

    print(
        f"[parser] PDF via {result.backend}: "
        f"{len(paragraphs)} paras (merged), {len(images)} images"
    )
    return DocumentModel(
        filename=filename,
        total_pages=result.total_pages,
        paragraphs=paragraphs,
        images=images,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TXT PARSER
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_txt(file_path: str, filename: str) -> DocumentModel:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return parse_text(content, title=filename)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_numbering_prefix(text: str) -> tuple[str | None, str]:
    match = re.match(r"^(\d+(?:\.\d+)*)\.?\s+(.+)$", (text or "").strip())
    if not match:
        return None, (text or "").strip()
    return match.group(1), match.group(2).strip()


def _extract_run_format(para) -> tuple[float | None, bool | None]:
    """Best-effort font size and bold flag from the first non-empty run."""
    font_size = None
    is_bold = None
    for run in para.runs:
        if not run.text.strip():
            continue
        if run.bold is not None:
            is_bold = bool(run.bold)
        if run.font.size is not None:
            font_size = round(run.font.size.pt, 1)
        break
    return font_size, is_bold


def _normalise_docx_style(style_name: str, text: str) -> str:
    """Map a Word style name to a normalised label."""
    low = style_name.lower()
    for lvl in (1, 2, 3, 4):
        if f"heading {lvl}" in low or f"heading{lvl}" in low:
            return f"Heading {lvl}"
    if "title" in low:
        return "Heading 1"
    if "subtitle" in low:
        return "Heading 2"
    if "list" in low:
        return "List"
    return "Normal"


def _guess_style(text: str) -> str:
    """Heuristic style detection for plain text / TXT files."""
    words = text.split()
    if not words:
        return "Normal"
    if len(words) <= 10 and text.isupper():
        return "Heading 1"
    if len(words) <= 10 and text.istitle() and not text.endswith((".", "?", "!")):
        return "Heading 2"
    if text.startswith(("•", "-", "*", "–", "·")):
        return "List"
    if re.match(r"^\d+[\.\)]\s", text):
        return "List"
    return "Normal"


def _guess_style_from_font(text: str, font_size: float, is_bold: bool) -> str:
    """Heuristic style detection using PDF font metadata."""
    word_count = len(text.split())
    ends_sentence = text.rstrip().endswith((".", "?", "!"))
    if font_size >= 18 and word_count <= 12 and not ends_sentence:
        return "Heading 1"
    if font_size >= 14 and word_count <= 12 and not ends_sentence:
        return "Heading 2"
    if is_bold and word_count <= 10 and not ends_sentence:
        return "Heading 3"
    if text.isupper() and 1 <= word_count <= 8:
        return "Heading 2"
    return "Normal"


def _extract_caption_near(paragraphs: list, current_idx: int) -> str:
    """Look at the paragraph immediately after the image for a caption."""
    caption_patterns = re.compile(
        r"^(figure|fig\.?|image|table|chart|diagram)\s*\d*", re.IGNORECASE
    )
    for offset in (1, 2):
        idx = current_idx + offset
        if idx < len(paragraphs):
            candidate = paragraphs[idx].text.strip()
            if candidate and caption_patterns.match(candidate):
                return candidate
    return ""
