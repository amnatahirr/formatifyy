"""
Layer 1 — Document Block Extractor
====================================
Converts any supported file (.docx, .pdf, .txt) into a clean list of
typed JSON blocks that all higher layers (heading matching, structure
check, style check) consume.

Output block shape
------------------
{
    "type":     "heading" | "paragraph" | "table" | "list_item" | "image",
    "text":     str,
    "level":    int | None,   # 1/2/3 for headings, None otherwise
    "index":    int,          # position in document (0-based)
    "metadata": {
        "style":      str,    # original Word style name or "pdf-inferred"
        "is_bold":    bool,
        "is_italic":  bool,
        "is_underline": bool,
        "font_size":  float | None,
        "font_name":  str | None,
        "alignment":  str | None,   # "LEFT" | "CENTER" | "RIGHT" | "JUSTIFY"
        "list_level": int,          # 0 = not a list item
        "page":       int | None,   # PDF page number, None for docx/txt
    }
}
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def extract_blocks(file_path: str) -> List[Dict[str, Any]]:
    """
    Main entry point.  Detects file type and delegates to the right parser.
    Returns a list of block dicts (see module docstring for shape).
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".docx":
        return _extract_from_docx(file_path)
    if ext == ".pdf":
        return _extract_from_pdf(file_path)
    if ext == ".txt":
        return _extract_from_txt(file_path)
    raise ValueError(f"Unsupported file type: {ext!r}. Supported: .docx, .pdf, .txt")


# ──────────────────────────────────────────────────────────────────────────────
# DOCX extractor
# ──────────────────────────────────────────────────────────────────────────────

def _extract_from_docx(file_path: str) -> List[Dict[str, Any]]:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc    = Document(file_path)
    blocks: List[Dict[str, Any]] = []
    index  = 0

    in_references = False

    # ── paragraphs ──────────────────────────────────────────────────────────
    print(f"[extractor] processing {len(doc.paragraphs)} paragraphs")
    for i, para in enumerate(doc.paragraphs):
        try:
            text = para.text.strip()
            try:
                _style_name_dbg = para.style.name if para.style else "Normal"
                print(f"[extractor] para {i}: style='{_style_name_dbg}' text='{text[:30]}'")
            except Exception as _dbg_e:
                print(f"[extractor] SKIP para {i}: {_dbg_e}")
                continue

            # IMPORTANT: do NOT substring-scan XML for "graphic"/"drawing".
            # Namespace declarations can contain those words even when there is no image,
            # causing every paragraph to be classified as a figure.
            has_image = False
            try:
                has_image = bool(
                    para._element.xpath(
                        ".//w:drawing",
                        namespaces={
                            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
                        },
                    )
                ) or bool(
                    para._element.xpath(
                        ".//a:blip",
                        namespaces={
                            "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
                        },
                    )
                )
            except Exception:
                para_xml = str(para._element.xml)
                has_image = ("<w:drawing" in para_xml) or ("<a:blip" in para_xml)
            if not text and not has_image:
                continue

            style_name = para.style.name if para.style else "Normal"

            # Collect per-run formatting (take first non-None value)
            is_bold = _first_true(r.bold for r in para.runs)
            is_italic = _first_true(r.italic for r in para.runs)
            is_underline = _first_true(r.underline for r in para.runs)
            font_size = _get_para_font_size_pt(para)
            font_name = _first_value(r.font.name for r in para.runs)

            # Alignment (EnumValue .name is not consistent across python-docx versions)
            alignment = None
            if para.paragraph_format.alignment is not None:
                a = para.paragraph_format.alignment
                alignment = getattr(a, "name", str(a))

            # List detection
            is_list_item, list_level = _docx_list_info(para)

            # Block type + heading level
            block_type, level = _classify_docx_para(
                style_name,
                bool(is_bold),
                bool(is_italic),
                bool(is_underline),
                font_size,
                text,
                is_list_item,
            )

            if block_type == "heading":
                lowered = text.lower()
                in_references = lowered.startswith("references") or lowered.startswith("bibliography")

            if has_image:
                block_type, level = "figure", None
                if not text:
                    text = f"Figure {index + 1}"
            elif _is_caption_text(text, style_name):
                block_type, level = "caption", None
            elif in_references and _is_reference_text(text):
                block_type, level = "reference", None

            blocks.append(
                _make_block(
                    btype=block_type,
                    text=text,
                    level=level,
                    index=index,
                    style=style_name,
                    is_bold=bool(is_bold),
                    is_italic=bool(is_italic),
                    is_underline=bool(is_underline),
                    font_size=font_size,
                    font_name=font_name,
                    alignment=alignment,
                    list_level=list_level,
                    page=None,
                )
            )
            index += 1
        except Exception as e:
            print(f"[extract_blocks] skipping paragraph due to error: {e}")
            continue

    # ── tables ──────────────────────────────────────────────────────────────
    for table in doc.tables:
        rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
        flat_text = " | ".join(
            " , ".join(cell for cell in row if cell)
            for row in rows if any(row)
        )
        if flat_text:
            blocks.append(_make_block(
                btype="table", text=flat_text, level=None, index=index,
                style="Table", is_bold=False, is_italic=False,
                is_underline=False, font_size=None, font_name=None,
                alignment=None, list_level=0, page=None,
            ))
            index += 1

    return blocks


def _get_para_font_size_pt(para) -> "Optional[float]":
    """
    CRITICAL FIX: Read actual font size in points directly from paragraph XML.

    python-docx run.font.size.pt returns the document default (e.g. 12pt)
    when font size is stored in w:pPr/w:rPr/w:sz in half-points, which is
    exactly how COMSATS FYP documents (and many others) store heading sizes.

    Reading order (first hit wins):
      1. w:pPr/w:rPr/w:sz  — paragraph-level run properties (most common)
      2. first w:r/w:rPr/w:sz — run-level override
      3. run.font.size.pt  — python-docx API fallback
    """
    from docx.oxml.ns import qn as _qn
    # Method 1
    pPr = para._element.find(_qn("w:pPr"))
    if pPr is not None:
        rPr = pPr.find(_qn("w:rPr"))
        if rPr is not None:
            sz = rPr.find(_qn("w:sz"))
            if sz is not None:
                val = sz.get(_qn("w:val"))
                if val:
                    return int(val) / 2.0   # half-points → points
    # Method 2
    for r_el in para._element.findall(_qn("w:r")):
        rPr = r_el.find(_qn("w:rPr"))
        if rPr is not None:
            sz = rPr.find(_qn("w:sz"))
            if sz is not None:
                val = sz.get(_qn("w:val"))
                if val:
                    return int(val) / 2.0
    # Method 3
    for run in para.runs:
        if run.font.size:
            return run.font.size.pt
    return None


def _classify_docx_para(
    style_name: str,
    is_bold: bool,
    is_italic: bool,
    is_underline: bool,
    font_size: Optional[float],
    text: str,
    is_list_item: bool,
) -> tuple[str, Optional[int]]:
    """Return (block_type, heading_level).

    Detection priority:
      1. Explicit Word Heading styles  (style name contains "Heading N")
      2. Font size >= 14pt from XML    (primary signal in Normal-styled docs)
      3. ALL CAPS short line
      4. Bold + short + no terminal punctuation
      5. Underline + short
      6. Numbered outline prefix       (e.g. "1.2 Background")

    NOTE: font_size here comes from _get_para_font_size_pt() which reads
    w:pPr/w:rPr/w:sz directly — reliable even when run.font.size.pt returns 12.
    """
    sl = style_name.lower()

    # 1. Explicit Word heading styles
    for lvl in (1, 2, 3, 4, 5, 6):
        if f"heading {lvl}" in sl or f"heading{lvl}" in sl:
            return "heading", lvl

    # List items
    if is_list_item:
        return "list_item", None

    word_count = len(text.split())
    ends_sentence = text.endswith((".", "?", "!"))

    # 2. Font-size-based detection (reads from XML, not run.font.size.pt)
    if font_size is not None:
        if font_size >= 18 and word_count <= 15 and not ends_sentence:
            return "heading", 1
        if font_size >= 14 and word_count <= 15 and not ends_sentence:
            return "heading", 2

    # 3. ALL CAPS short line
    if text.isupper() and 1 <= word_count <= 8:
        return "heading", 2

    # 4. Bold + short + no terminal punctuation
    if is_bold and word_count <= 10 and not ends_sentence:
        if font_size and font_size >= 14:
            return "heading", 2
        return "heading", 3

    # 5. Underline + short
    if is_underline and word_count <= 10 and not ends_sentence:
        return "heading", 3

    # 6. Numbered outline prefix
    if re.match(r"^\d+(\.\d+)*\.?\s+[A-Z]", text) and word_count <= 12:
        dots = text.split()[0].count(".")
        return "heading", min(dots + 1, 3)

    return "paragraph", None


def _docx_list_info(para) -> tuple[bool, int]:
    """Return (is_list_item, list_level)."""
    style_name = (para.style.name or "").lower()
    if "list" in style_name or "bullet" in style_name:
        level = 0
        try:
            indent = para.paragraph_format.left_indent
            if indent:
                level = max(0, int(indent.inches / 0.5))
        except Exception:
            pass
        return True, level

    text = para.text.strip()
    if text and text[0] in ("-", "*", "•", "–", "▪"):
        return True, 0
    if re.match(r"^\d+[.)]\s", text):
        return True, 0

    return False, 0


# ──────────────────────────────────────────────────────────────────────────────
# PDF extractor
# ──────────────────────────────────────────────────────────────────────────────

def _extract_from_pdf(file_path: str) -> List[Dict[str, Any]]:
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber is required for PDF parsing. Run: pip install pdfplumber")

    blocks: List[Dict[str, Any]] = []
    index  = 0

    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            # Use extract_words for per-word font info when available
            words = page.extract_words(extra_attrs=["fontname", "size"]) or []

            # Group words into lines by their top-coordinate (rounded to 2pt)
            line_map: Dict[int, List[dict]] = {}
            for word in words:
                key = round(word.get("top", 0) / 2) * 2
                line_map.setdefault(key, []).append(word)

            # Sort lines top-to-bottom
            for top_key in sorted(line_map.keys()):
                line_words = sorted(line_map[top_key], key=lambda w: w.get("x0", 0))
                text = " ".join(w["text"] for w in line_words).strip()
                if not text:
                    continue

                # Font info from majority of words on the line
                sizes     = [w.get("size", 12) for w in line_words if w.get("size")]
                fontnames = [w.get("fontname", "") for w in line_words if w.get("fontname")]
                avg_size  = (sum(sizes) / len(sizes)) if sizes else 12.0
                font_name = fontnames[0] if fontnames else None
                is_bold   = any("Bold" in (f or "") for f in fontnames)
                is_italic = any("Italic" in (f or "") or "Oblique" in (f or "") for f in fontnames)

                block_type, level = _classify_pdf_line(text, avg_size, is_bold)

                blocks.append(_make_block(
                    btype    = block_type,
                    text     = text,
                    level    = level,
                    index    = index,
                    style    = "pdf-inferred",
                    is_bold  = is_bold,
                    is_italic= is_italic,
                    is_underline = False,
                    font_size= round(avg_size, 1),
                    font_name= font_name,
                    alignment= None,
                    list_level= 1 if block_type == "list_item" else 0,
                    page     = page_num,
                ))
                index += 1

    # Merge consecutive paragraphs that are continuation lines
    return _merge_pdf_paragraphs(blocks)


def _classify_pdf_line(text: str, font_size: float, is_bold: bool) -> tuple[str, Optional[int]]:
    stripped = text.strip()

    if _is_caption_text(stripped, "pdf-inferred"):
        return "caption", None
    if _is_reference_text(stripped):
        return "reference", None

    # List item detection
    if re.match(r"^(\d+[.)]\s|[•\-\*▪–]\s)", stripped):
        return "list_item", None

    # All-caps short → heading
    if stripped.isupper() and 1 <= len(stripped.split()) <= 8:
        return "heading", 2

    # Large font → heading
    if font_size >= 16:
        return "heading", 1
    if font_size >= 13 and is_bold:
        return "heading", 2
    if font_size >= 11 and is_bold and len(stripped.split()) <= 10:
        return "heading", 3

    return "paragraph", None


def _merge_pdf_paragraphs(blocks: List[Dict]) -> List[Dict]:
    """
    Merge consecutive paragraph blocks that are soft-wrapped PDF lines
    into single logical paragraphs.
    """
    if not blocks:
        return blocks

    merged: List[Dict] = []
    current = blocks[0]

    for nxt in blocks[1:]:
        if (
            current["type"] == "paragraph"
            and nxt["type"] == "paragraph"
            and current["metadata"]["page"] == nxt["metadata"]["page"]
            and _should_merge(current["text"], nxt["text"])
        ):
            current["text"] += " " + nxt["text"]
        else:
            merged.append(current)
            current = nxt

    merged.append(current)

    # Re-index
    for i, b in enumerate(merged):
        b["index"] = i

    return merged


def _should_merge(current: str, nxt: str) -> bool:
    """True if nxt is likely a continuation of current."""
    if not current or not nxt:
        return False
    if current.endswith((".", "!", "?")):
        return False        # sentence is complete
    if nxt[0].islower():
        return True         # continuation mid-sentence
    if current.endswith((",", "-", "–")):
        return True
    return False


# ──────────────────────────────────────────────────────────────────────────────
# TXT extractor
# ──────────────────────────────────────────────────────────────────────────────

def _extract_from_txt(file_path: str) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    index  = 0

    with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
        raw = fh.read()

    # Split on blank lines → logical paragraphs
    chunks = re.split(r"\n{2,}", raw)

    for chunk in chunks:
        text = " ".join(chunk.split())   # collapse internal whitespace
        if not text:
            continue

        is_bold = False
        is_list = re.match(r"^(\d+[.)]\s|[•\-\*▪–]\s)", text) is not None
        block_type, level = _classify_txt_line(text, is_list)

        blocks.append(_make_block(
            btype    = block_type,
            text     = text,
            level    = level,
            index    = index,
            style    = "txt-inferred",
            is_bold  = False,
            is_italic= False,
            is_underline = False,
            font_size= None,
            font_name= None,
            alignment= None,
            list_level= 1 if is_list else 0,
            page     = None,
        ))
        index += 1

    return blocks


def _classify_txt_line(text: str, is_list: bool) -> tuple[str, Optional[int]]:
    if _is_caption_text(text, "txt-inferred"):
        return "caption", None
    if _is_reference_text(text):
        return "reference", None

    if is_list:
        return "list_item", None

    # Numbered heading like "1. Introduction" or "1.2 Background"
    if re.match(r"^\d+(\.\d+)*\.?\s+[A-Z]", text) and len(text.split()) <= 10:
        dots = text.split()[0].count(".")
        level = min(dots + 1, 3)
        return "heading", level

    if text.isupper() and 1 <= len(text.split()) <= 8:
        return "heading", 2

    if len(text.split()) <= 8 and not text.endswith("."):
        return "heading", 3

    return "paragraph", None


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_block(
    btype: str,
    text: str,
    level: Optional[int],
    index: int,
    style: str,
    is_bold: bool,
    is_italic: bool,
    is_underline: bool,
    font_size: Optional[float],
    font_name: Optional[str],
    alignment: Optional[str],
    list_level: int,
    page: Optional[int],
) -> Dict[str, Any]:
    return {
        "type":  btype,
        "text":  text,
        "level": level,
        "index": index,
        "metadata": {
            "style":       style,
            "is_bold":     is_bold,
            "is_italic":   is_italic,
            "is_underline":is_underline,
            "font_size":   font_size,
            "font_name":   font_name,
            "alignment":   alignment,
            "list_level":  list_level,
            "page":        page,
        },
    }


def _is_caption_text(text: str, style_name: str) -> bool:
    lowered = text.lower().strip()
    style_lower = (style_name or "").lower()
    if "caption" in style_lower:
        return True
    return bool(re.match(r"^(figure|fig\.|table)\s*\d+[\.:]?\s+", lowered))


def _is_reference_text(text: str) -> bool:
    s = text.strip()
    if not s:
        return False
    if re.match(r"^\[\d+\]\s+", s):
        return True
    if re.match(r"^\d+\.\s+[A-Z]", s):
        return True
    if "doi:" in s.lower() or "et al." in s.lower():
        return True
    return False


def _first_true(iterable) -> bool:
    for v in iterable:
        if v:
            return True
    return False


def _first_value(iterable):
    for v in iterable:
        if v is not None:
            return v
    return None