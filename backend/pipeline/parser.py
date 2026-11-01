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
from typing import Dict, List, Tuple

from models import DocumentModel, ParagraphBlock, ImageBlock

# Soft page-budget constants — aligned with docx_fields.estimate_body_page_numbers
# so analysis batching and TOC page estimates stay in the same ballpark.
_CHARS_PER_PAGE = 2100
_IMAGE_CHARS = 900
_MIN_PARA_CHARS = 50


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

def _para_has_hard_page_break(para_el) -> bool:
    """True when the paragraph contains an explicit Word page break."""
    try:
        from docx.oxml.ns import qn

        for br in para_el.findall(".//" + qn("w:br")):
            if br.get(qn("w:type")) == "page":
                return True
    except Exception:
        pass
    return False


def _para_has_last_rendered_page_break(para_el) -> bool:
    """True when Word recorded a soft page start on this paragraph."""
    try:
        from docx.oxml.ns import qn

        return bool(para_el.findall(".//" + qn("w:lastRenderedPageBreak")))
    except Exception:
        return False


def _para_has_section_break(para_el) -> bool:
    """True when the paragraph carries a section property (often a page boundary)."""
    try:
        from docx.oxml.ns import qn

        return bool(para_el.findall(".//" + qn("w:sectPr")))
    except Exception:
        return False


def _para_has_embedded_image(para_el, rel_images: dict) -> bool:
    r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    blip_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
    for blip in para_el.iter(f"{{{blip_ns}}}blip"):
        embed = blip.get(f"{{{r_ns}}}embed")
        if embed and embed in rel_images:
            return True
    return False


def _estimate_docx_page_map(doc, rel_images: dict) -> Tuple[Dict[int, int], dict]:
    """
    Assign a 1-based page number to every paragraph index in ``doc.paragraphs``.

    Strategy (offline, no Word/LibreOffice required):
      1. Honor hard ``w:br type=page`` and section breaks (end current page).
      2. If Word saved ``w:lastRenderedPageBreak`` markers, use those as soft
         page starts (most accurate for docs opened/saved in Word).
      3. Otherwise fall back to a character/image budget (~2100 chars/page),
         matching ``docx_fields.estimate_body_page_numbers``.

    Returns (page_by_para_idx, stats).
    """
    paras = list(doc.paragraphs)
    # Trust Word's lastRenderedPageBreak only when enough markers exist.
    # A single stray marker is common and would otherwise disable the char budget.
    rendered_marker_count = sum(
        1 for p in paras if _para_has_last_rendered_page_break(p._element)
    )
    use_rendered = rendered_marker_count >= 3

    page = 1
    chars_on_page = 0
    page_by_idx: Dict[int, int] = {}
    hard_breaks = 0
    rendered_breaks = 0
    soft_breaks = 0
    # When Word left many rendered markers, still cap runaway pages.
    soft_limit = (_CHARS_PER_PAGE * 2) if use_rendered else _CHARS_PER_PAGE

    for para_idx, para in enumerate(paras):
        el = para._element

        # Word soft page starts appear at the beginning of the new page's para.
        if use_rendered and _para_has_last_rendered_page_break(el) and chars_on_page > 0:
            page += 1
            chars_on_page = 0
            rendered_breaks += 1

        page_by_idx[para_idx] = page

        text = (para.text or "").strip()
        has_image = _para_has_embedded_image(el, rel_images)
        if text or has_image:
            if text:
                chars_on_page += max(_MIN_PARA_CHARS, len(text))
            if has_image:
                chars_on_page += _IMAGE_CHARS

        # Hard / section breaks end the current page AFTER this paragraph.
        # Skip document-final sectPr on an empty trailing paragraph — that is
        # Word's section settings, not a real content page boundary.
        is_hard = _para_has_hard_page_break(el)
        is_sect = _para_has_section_break(el)
        is_trailing_sect = (
            is_sect
            and not is_hard
            and not text
            and not has_image
            and para_idx == len(paras) - 1
        )
        if (is_hard or is_sect) and not is_trailing_sect:
            page += 1
            chars_on_page = 0
            hard_breaks += 1
            continue

        if chars_on_page >= soft_limit:
            page += 1
            chars_on_page = 0
            soft_breaks += 1

    total_pages = max(page_by_idx.values()) if page_by_idx else 1
    stats = {
        "total_pages": total_pages,
        "hard_breaks": hard_breaks,
        "rendered_breaks": rendered_breaks,
        "soft_breaks": soft_breaks,
        "used_rendered": use_rendered,
    }
    return page_by_idx, stats


def _parse_docx(file_path: str, filename: str) -> DocumentModel:
    from docx import Document as DocxDocument

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

    # ── Estimate page numbers (hard breaks + Word markers + char budget) ─────
    page_by_idx, page_stats = _estimate_docx_page_map(doc, rel_images)
    print(
        f"[parser] DOCX page estimate: pages={page_stats['total_pages']} "
        f"hard={page_stats['hard_breaks']} rendered={page_stats['rendered_breaks']} "
        f"soft={page_stats['soft_breaks']} used_rendered={page_stats['used_rendered']}"
    )

    heading_context = ""
    img_counter = 0
    r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    blip_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"

    for para_idx, para in enumerate(doc.paragraphs):
        page = page_by_idx.get(para_idx, 1)
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
        has_image = _para_has_embedded_image(para._element, rel_images)

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

    total_pages = page_stats["total_pages"] if paragraphs else 1
    if paragraphs:
        total_pages = max(total_pages, max(p.page_number for p in paragraphs))
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
    from docx_tools.pdf_io import (
        extract_pdf,
        merge_pdf_lines_to_paragraphs_with_pages,
        looks_like_heading_line,
    )

    result = extract_pdf(file_path)
    paragraphs: List[ParagraphBlock] = []
    images: List[ImageBlock] = []
    heading_context = ""
    para_counter = 0
    img_counter = 0

    # Merge visual wrap lines into real paragraphs (same as PDF→DOCX path),
    # preserving the source page of each merged paragraph for batching.
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

    merged = merge_pdf_lines_to_paragraphs_with_pages(raw_lines, line_page)
    for text, page_num in merged:
        is_head = looks_like_heading_line(text)
        style = "Heading 1" if is_head else _guess_style_from_font(text, 12.0, False)
        if is_head or style.startswith("Heading"):
            heading_context = text
            style = style if style.startswith("Heading") else "Heading 1"
        prefix, _ = _extract_numbering_prefix(text)
        paragraphs.append(
            ParagraphBlock(
                paragraph_id=f"p{para_counter}",
                page_number=int(page_num) if page_num else 1,
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

    para_pages = {p.page_number for p in paragraphs}
    print(
        f"[parser] PDF via {result.backend}: "
        f"{len(paragraphs)} paras (merged), {len(images)} images, "
        f"pages={result.total_pages}, para_page_span={min(para_pages) if para_pages else 0}-"
        f"{max(para_pages) if para_pages else 0}"
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
