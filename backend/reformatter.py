"""
reformatter.py — Document reformatter for Formatify.

After analysis, this module programmatically modifies the document using
python-docx to fix formatting issues identified by Claude. It does NOT ask
Claude to rewrite anything — Python code applies the fixes directly.

Supports:
  - Heading style correction (font, size, bold, spacing)
  - Body text style normalisation
  - Section ordering awareness
  - Downloadable DOCX output
  - Optional PDF export (if LibreOffice is available)
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

from models import AnalysisReport
from docx_styles import force_heading_style


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPLATE STYLE SPECS — extracted from template markdown_rules
# ═══════════════════════════════════════════════════════════════════════════════

# Default style specs used when template parsing doesn't find a specific value
_DEFAULT_STYLES = {
    "heading1": {
        "font": "Times New Roman", "size": 16, "bold": True, "italic": False,
        "alignment": "left", "space_before": 24, "space_after": 12, "line_spacing": 1.5,
    },
    "heading2": {
        "font": "Times New Roman", "size": 14, "bold": True, "italic": False,
        "alignment": "left", "space_before": 18, "space_after": 8, "line_spacing": 1.5,
    },
    "heading3": {
        "font": "Times New Roman", "size": 12, "bold": True, "italic": True,
        "alignment": "left", "space_before": 12, "space_after": 6, "line_spacing": 1.5,
    },
    "body": {
        "font": "Times New Roman", "size": 12, "bold": False, "italic": False,
        "alignment": "justify", "space_before": 0, "space_after": 0, "line_spacing": 2.0,
        "first_line_indent": 0.5,
    },
    "margins": {
        "top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0
    }
}


def _normalize_margin_inches(value: float, unit: str = "mm") -> float:
    """Convert stored margin/length values to inches."""
    v = float(value)
    if unit == "mm":
        return round(v / 25.4, 4)
    if v > 3.0:
        return round(v / 25.4, 4)
    return v


def _normalize_length_inches(value: float, unit: str = "mm") -> float:
    """Convert indent/length fields to inches."""
    return _normalize_margin_inches(value, unit)


def _parse_section_map(required_sections: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Build lookup: normalized section name → section config."""
    mapping: Dict[str, Dict[str, Any]] = {}
    for idx, sec in enumerate(required_sections or []):
        if isinstance(sec, str):
            name = sec.strip()
            mapping[name.lower()] = {"name": name, "order": idx + 1, "heading_level": 1}
        elif isinstance(sec, dict):
            name = (sec.get("name") or "").strip()
            if name:
                entry = dict(sec)
                entry.setdefault("order", idx + 1)
                entry.setdefault("heading_level", sec.get("headingLevel", 1))
                if "heading_level" in sec:
                    entry["heading_level"] = sec["heading_level"]
                mapping[name.lower()] = entry
    return mapping


def _strip_heading_number_prefix(text: str) -> str:
    """Strip existing decimal heading prefixes (e.g. '1.2.3 Title' → 'Title')."""
    cleaned = text.strip().rstrip(":").strip()
    return re.sub(r"^[\d]+(?:\.[\d]+)*\.?\s+", "", cleaned).strip()


def _normalize_section_title(text: str) -> str:
    """Strip numbering/colons for section title comparison."""
    return _strip_heading_number_prefix(text).lower()


class _HeadingNumberTracker:
    """Track hierarchical heading counters (1 → 1.1 → 1.2 → 2 → 2.1 …)."""

    _MAX_LEVEL = 4

    def __init__(self) -> None:
        self._counters = [0] * self._MAX_LEVEL

    def next_number(self, level: int) -> str:
        level = max(1, min(self._MAX_LEVEL, level))
        self._counters[level - 1] += 1
        for idx in range(level, self._MAX_LEVEL):
            self._counters[idx] = 0
        return ".".join(str(self._counters[idx]) for idx in range(level))


def _detect_heading_level(
    para,
    text: str,
    section_map: Dict[str, Dict[str, Any]],
    classified: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """
    Return heading level (1-4) if paragraph is a heading, else None.

    Prefers Pass A/B classification when available; falls back to admin-list
    soft match and existing Word Heading styles.
    """
    if classified and classified.get("level"):
        return max(1, min(4, int(classified["level"])))

    matched = _match_required_section(text, section_map)
    if matched:
        level = int(matched.get("heading_level", 1) or 1)
        return max(1, min(4, level))

    style_name = (para.style.name or "").lower()
    for lvl in (1, 2, 3, 4):
        if f"heading {lvl}" in style_name or style_name == f"heading{lvl}":
            return lvl
    return None


def _format_numbered_heading(text: str, number: str) -> str:
    """Build heading text with hierarchical number prefix."""
    title = _strip_heading_number_prefix(text)
    return f"{number}. {title}" if title else f"{number}."


_META_LIST_HEADING_TITLES = frozenset({
    "table of contents",
    "contents",
    "list of tables",
    "list of figures",
})


def _is_meta_list_section_title(text: str) -> bool:
    """Return True for front-matter list headings that must not receive section numbers."""
    normalized = _normalize_section_title(text)
    if normalized in _META_LIST_HEADING_TITLES:
        return True
    return any(
        normalized == title or normalized.startswith(f"{title} ")
        for title in _META_LIST_HEADING_TITLES
    )


def _match_required_section(text: str, section_map: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    PASS A soft lookup — exact, numbered, substring, and abbreviated forms
    (e.g. document "Problem" ↔ template "Problem Statement").
    """
    normalized = _normalize_section_title(text)
    if not normalized:
        return None
    if normalized in section_map:
        return section_map[normalized]

    text_tokens = {t for t in normalized.split() if t}
    best: Optional[Dict[str, Any]] = None
    best_score = 0.0

    for key, sec in section_map.items():
        order = sec.get("order")
        if order:
            numbered = f"{order}. {key}"
            if normalized == numbered or normalized == f"{order} {key}":
                return sec
        if normalized == key or normalized.endswith(f" {key}"):
            return sec
        if key in normalized and len(normalized) <= len(key) + 8:
            return sec

        # Abbreviation: doc tokens ⊆ template tokens ("problem" ⊆ "problem statement")
        # Require coverage >= 0.5 OR a single primary content word (not "main"/"the").
        key_tokens = {t for t in key.split() if t and t not in {"the", "a", "an", "and", "of", "for"}}
        content_tokens = {t for t in text_tokens if t not in {"the", "a", "an", "and", "of", "for", "main"}}
        if content_tokens and key_tokens and content_tokens.issubset(key_tokens):
            coverage = len(content_tokens) / max(1, len(key_tokens))
            if coverage >= 0.5 or len(content_tokens) == 1:
                score = 0.82 if coverage >= 0.5 else 0.72
                if score > best_score:
                    best_score = score
                    best = sec
        elif key_tokens and key_tokens.issubset(text_tokens) and len(normalized) <= len(key) + 12:
            if 0.75 > best_score:
                best_score = 0.75
                best = sec

    if best is not None and best_score >= 0.72:
        return best
    return None


def _apply_word_heading(doc, para, level: int, spec: dict, align_map: dict) -> None:
    """Assign built-in Word Heading style plus template font specs."""
    level = max(1, min(4, level))
    force_heading_style(para, doc, level)
    _apply_style(para, spec, align_map)

    from docx.oxml.ns import qn

    # Headings must never carry list bullets / numbering properties
    p_pr = para._element.get_or_add_pPr()
    for tag in (qn("w:numPr"),):
        existing = p_pr.find(tag)
        if existing is not None:
            p_pr.remove(existing)

    # Strip a stray leading bullet glyph left in the visible text
    text = para.text or ""
    cleaned = re.sub(r"^\s*[•*○■▪\-–—→»·]\s+", "", text)
    if cleaned != text and cleaned.strip():
        _set_paragraph_text_preserve_style(para, cleaned.strip())

    pf = para.paragraph_format
    pf.first_line_indent = None
    pf.left_indent = None
    try:
        pf.keep_with_next = True
    except Exception:
        pass


def parse_template_styles(rules_input: str | Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Parse the template markdown rules or mapping dictionary to extract heading, margin, and body styles.
    Falls back to defaults for any value not explicitly specified.
    """
    styles = {k: dict(v) for k, v in _DEFAULT_STYLES.items()}

    if isinstance(rules_input, dict):
        unit = rules_input.get("spacing_unit", "mm")
        # Read from dictionary directly
        for lvl in (1, 2, 3):
            prefix = f"heading{lvl}"
            if f"{prefix}_font" in rules_input:
                styles[prefix]["font"] = str(rules_input[f"{prefix}_font"])
            if f"{prefix}_size" in rules_input:
                styles[prefix]["size"] = int(rules_input[f"{prefix}_size"])
            if f"{prefix}_bold" in rules_input:
                styles[prefix]["bold"] = bool(rules_input[f"{prefix}_bold"])
            if f"{prefix}_italic" in rules_input:
                styles[prefix]["italic"] = bool(rules_input[f"{prefix}_italic"])
            if f"{prefix}_line_spacing" in rules_input:
                styles[prefix]["line_spacing"] = float(rules_input[f"{prefix}_line_spacing"])
            if f"{prefix}_space_before" in rules_input:
                styles[prefix]["space_before"] = float(rules_input[f"{prefix}_space_before"])
            if f"{prefix}_space_after" in rules_input:
                styles[prefix]["space_after"] = float(rules_input[f"{prefix}_space_after"])

        # Body
        if "body_font" in rules_input:
            styles["body"]["font"] = str(rules_input["body_font"])
        if "body_size" in rules_input:
            styles["body"]["size"] = int(rules_input["body_size"])
        if "body_line_spacing" in rules_input:
            styles["body"]["line_spacing"] = float(rules_input["body_line_spacing"])
        if "body_space_before" in rules_input:
            styles["body"]["space_before"] = float(rules_input["body_space_before"])
        if "body_space_after" in rules_input:
            styles["body"]["space_after"] = float(rules_input["body_space_after"])
        if "first_line_indent" in rules_input:
            styles["body"]["first_line_indent"] = _normalize_length_inches(
                rules_input["first_line_indent"], unit
            )

        # Margins (stored as mm in admin UI)
        for side in ("top", "bottom", "left", "right"):
            key = f"margin_{side}"
            if key in rules_input:
                styles["margins"][side] = _normalize_margin_inches(rules_input[key], unit)

        styles["_spacing_unit"] = unit
        styles["_heading_numbering"] = rules_input.get("heading_numbering_style", "none")
        return styles

    # If it is a string containing markdown_rules
    markdown_rules = rules_input

    # Try to extract Heading 1 font and size
    h1_match = re.search(
        r"\*\*Heading 1[^*]*\*\*[:\s]*([^,]+),\s*(\d+)pt", markdown_rules
    )
    if h1_match:
        styles["heading1"]["font"] = h1_match.group(1).strip()
        styles["heading1"]["size"] = int(h1_match.group(2))

    h2_match = re.search(
        r"\*\*Heading 2[^*]*\*\*[:\s]*([^,]+),\s*(\d+)pt", markdown_rules
    )
    if h2_match:
        styles["heading2"]["font"] = h2_match.group(1).strip()
        styles["heading2"]["size"] = int(h2_match.group(2))

    h3_match = re.search(
        r"\*\*Heading 3[^*]*\*\*[:\s]*([^,]+),\s*(\d+)pt", markdown_rules
    )
    if h3_match:
        styles["heading3"]["font"] = h3_match.group(1).strip()
        styles["heading3"]["size"] = int(h3_match.group(2))

    # Body font
    body_match = re.search(
        r"(?:Body|body)\s*(?:Text|text)?[:\s]*Font[:\s]*([^,]+),\s*(\d+)pt",
        markdown_rules,
    )
    if body_match:
        styles["body"]["font"] = body_match.group(1).strip()
        styles["body"]["size"] = int(body_match.group(2))
    else:
        # Alternative pattern: "- Font: Arial, 11pt"
        alt_match = re.search(r"Font:\s*([^,]+),\s*(\d+)pt", markdown_rules)
        if alt_match:
            styles["body"]["font"] = alt_match.group(1).strip()
            styles["body"]["size"] = int(alt_match.group(2))

    # Line spacing
    spacing_match = re.search(r"Line Spacing:\s*([\d.]+)", markdown_rules)
    if spacing_match:
        styles["body"]["line_spacing"] = float(spacing_match.group(1))

    # Alignment
    if "Justified" in markdown_rules or "justified" in markdown_rules:
        styles["body"]["alignment"] = "justify"
    elif "Left-aligned" in markdown_rules or "left-aligned" in markdown_rules:
        styles["body"]["alignment"] = "left"

    # Margins parsing from text (e.g. Margins: Top 1.0 inch, Bottom 1.0 inch, Left 1.0 inch, Right 1.0 inch)
    margin_match = re.search(r"Margins?:\s*([^\n]+)", markdown_rules)
    if margin_match:
        margin_text = margin_match.group(1)
        inch_values = re.findall(r"([\d.]+)\s*inch", margin_text, re.IGNORECASE)
        if len(inch_values) >= 4:
            styles["margins"]["top"] = float(inch_values[0])
            styles["margins"]["bottom"] = float(inch_values[1])
            styles["margins"]["left"] = float(inch_values[2])
            styles["margins"]["right"] = float(inch_values[3])
        elif len(inch_values) >= 1:
            val = float(inch_values[0])
            styles["margins"]["top"] = val
            styles["margins"]["bottom"] = val
            styles["margins"]["left"] = val
            styles["margins"]["right"] = val

    return styles


# ═══════════════════════════════════════════════════════════════════════════════
# REFORMAT DOCUMENT
# ═══════════════════════════════════════════════════════════════════════════════

def reformat_document(
    input_path: str,
    output_path: str,
    report: AnalysisReport,
    rules_input: str | Dict[str, Any],
    required_sections: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Apply formatting corrections to a DOCX file based on the analysis report
    and template rules. Returns the path to the reformatted file.

    For non-DOCX inputs (PDF/TXT), creates a new DOCX from scratch.
    """
    ext = os.path.splitext(input_path)[1].lower()

    if ext == ".docx":
        return _reformat_docx(input_path, output_path, report, rules_input, required_sections)
    else:
        # For PDF/TXT → create a basic formatted DOCX
        return _create_formatted_docx(input_path, output_path, report, rules_input)


def _reformat_docx(
    input_path: str,
    output_path: str,
    report: AnalysisReport,
    rules_input: str | Dict[str, Any],
    required_sections: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Reformat an existing DOCX — copy first, then apply styles without altering text."""
    import shutil
    from docx import Document
    from docx.shared import Pt, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    shutil.copy2(input_path, output_path)

    ALIGN_MAP = {
        "left": WD_ALIGN_PARAGRAPH.LEFT,
        "center": WD_ALIGN_PARAGRAPH.CENTER,
        "right": WD_ALIGN_PARAGRAPH.RIGHT,
        "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
    }

    styles = parse_template_styles(rules_input)
    numbering_style = str(styles.pop("_heading_numbering", "none"))
    styles.pop("_spacing_unit", None)
    section_map = _parse_section_map(required_sections or [])
    doc = Document(output_path)

    # Cover / info pages (before Formatify body bookmark) must stay as uploaded
    body_start = None
    try:
        from docx_fields import (
            find_formatify_body_start_element,
            _paragraph_is_before_body_start,
        )
        body_start = find_formatify_body_start_element(doc)
    except Exception as exc:
        print(f"[reformatter] body-start lookup skipped: {exc}")

    # Pass A/B classification so inferred headings (e.g. "Specific Objectives")
    # receive Word Heading styles — not just admin-list lookups.
    heading_map: Dict[int, Dict[str, Any]] = {}
    try:
        from heading_analysis import classify_paragraphs_for_reformat
        heading_map = classify_paragraphs_for_reformat(
            list(doc.paragraphs),
            required_sections or [],
        )
        matched_n = sum(1 for v in heading_map.values() if v.get("source") == "matched")
        inferred_n = sum(1 for v in heading_map.values() if v.get("source") == "inferred")
        print(
            f"[reformatter] heading classification: "
            f"{matched_n} matched, {inferred_n} inferred, "
            f"{len(heading_map)} total"
        )
    except Exception as exc:
        print(f"[reformatter] heading classification fallback (non-fatal): {exc}")

    prev_was_heading = False
    number_tracker = _HeadingNumberTracker() if numbering_style == "decimal" else None

    # ── Apply page margins (skip when cover/info present — preserve their sections) ──
    margins = styles["margins"]
    if body_start is None:
        for section in doc.sections:
            section.top_margin = Inches(margins["top"])
            section.bottom_margin = Inches(margins["bottom"])
            section.left_margin = Inches(margins["left"])
            section.right_margin = Inches(margins["right"])
    else:
        # Only touch the last section (report body); leave cover/info section(s) alone
        try:
            section = doc.sections[-1]
            section.top_margin = Inches(margins["top"])
            section.bottom_margin = Inches(margins["bottom"])
            section.left_margin = Inches(margins["left"])
            section.right_margin = Inches(margins["right"])
        except Exception as exc:
            print(f"[reformatter] body section margin skip: {exc}")

    # ── Apply styles to paragraphs (never rewrite paragraph text) ────────────
    for para_idx, para in enumerate(doc.paragraphs):
        if body_start is not None and _paragraph_is_before_body_start(doc, para, body_start):
            prev_was_heading = False
            continue

        text = para.text.strip()
        if not text:
            prev_was_heading = False
            continue

        classified = heading_map.get(para_idx)
        level = _detect_heading_level(para, text, section_map, classified)
        is_heading = level is not None

        if is_heading:
            spec = styles.get(f"heading{min(level, 3)}", styles["heading1"])
            # Number Heading 1–3 only. Heading 4 gets style alone (no 3.2.1.1.).
            if level >= 4:
                cleaned = _strip_heading_number_prefix(text)
                # Also drop a depth-4 auto-number if present (e.g. "3.2.1.1. Title")
                if cleaned != text and cleaned:
                    _set_paragraph_text_preserve_style(para, cleaned)
                    text = cleaned
            elif (
                number_tracker is not None
                and not _is_meta_list_section_title(text)
            ):
                number = number_tracker.next_number(level)
                desired = _format_numbered_heading(text, number)
                if text != desired:
                    _set_paragraph_text_preserve_style(para, desired)
            _apply_word_heading(doc, para, level, spec, ALIGN_MAP)
        else:
            spec = dict(styles["body"])
            if prev_was_heading:
                spec["first_line_indent"] = 0
            _apply_style(para, spec, ALIGN_MAP)

        prev_was_heading = is_heading

    doc.save(output_path)
    return output_path


def _create_formatted_docx(
    input_path: str,
    output_path: str,
    report: AnalysisReport,
    rules_input: str | Dict[str, Any],
) -> str:
    """Create a new DOCX from a non-DOCX source (PDF/TXT)."""
    from docx import Document
    from docx.shared import Pt, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    ALIGN_MAP = {
        "left": WD_ALIGN_PARAGRAPH.LEFT,
        "center": WD_ALIGN_PARAGRAPH.CENTER,
        "right": WD_ALIGN_PARAGRAPH.RIGHT,
        "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
    }

    styles = parse_template_styles(rules_input)
    doc = Document()

    # Apply page margins
    margins = styles["margins"]
    for section in doc.sections:
        section.top_margin = Inches(margins["top"])
        section.bottom_margin = Inches(margins["bottom"])
        section.left_margin = Inches(margins["left"])
        section.right_margin = Inches(margins["right"])

    # Read source text
    ext = os.path.splitext(input_path)[1].lower()
    if ext == ".txt":
        with open(input_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    elif ext == ".pdf":
        import fitz
        pdf = fitz.open(input_path)
        lines = []
        for page in pdf:
            lines.extend(page.get_text().split("\n"))
        pdf.close()
    else:
        lines = []

    for line in lines:
        text = line.strip()
        if not text:
            continue

        word_count = len(text.split())
        ends_sentence = text.endswith((".", "?", "!"))

        if word_count <= 10 and text.isupper():
            spec = styles["heading1"]
            para = doc.add_paragraph()
        elif word_count <= 10 and text.istitle() and not ends_sentence:
            spec = styles["heading2"]
            para = doc.add_paragraph()
        else:
            spec = styles["body"]
            para = doc.add_paragraph()

        run = para.add_run(text)
        _apply_style(para, spec, ALIGN_MAP)

    doc.save(output_path)
    return output_path


def _set_paragraph_text_preserve_style(para, new_text: str) -> None:
    """Set paragraph text without splitting across runs unnecessarily."""
    if para.runs:
        para.runs[0].text = new_text
        for run in para.runs[1:]:
            run.text = ""
    else:
        para.add_run(new_text)


def _apply_style(para, spec: dict, align_map: dict) -> None:
    """Apply a style specification to a paragraph and its runs — text is never replaced."""
    from docx.shared import Pt, Inches
    from docx.oxml.ns import qn

    if not para.runs:
        return

    for run in para.runs:
        if not run.text:
            continue
        if spec.get("font"):
            run.font.name = spec["font"]
            r_pr = run._element.get_or_add_rPr()
            r_fonts = r_pr.get_or_add_rFonts()
            r_fonts.set(qn("w:ascii"), spec["font"])
            r_fonts.set(qn("w:hAnsi"), spec["font"])
        if spec.get("size"):
            run.font.size = Pt(spec["size"])
        if "bold" in spec:
            run.font.bold = spec["bold"]
        if "italic" in spec:
            run.font.italic = spec["italic"]

    pf = para.paragraph_format
    if spec.get("line_spacing") is not None:
        pf.line_spacing = spec["line_spacing"]
    if spec.get("space_before") is not None:
        pf.space_before = Pt(spec["space_before"])
    if spec.get("space_after") is not None:
        pf.space_after = Pt(spec["space_after"])
    if spec.get("alignment") in align_map:
        pf.alignment = align_map[spec["alignment"]]
    if spec.get("first_line_indent") is not None:
        indent = float(spec["first_line_indent"])
        if indent > 0:
            pf.first_line_indent = Inches(indent)
        else:
            pf.first_line_indent = None


# ═══════════════════════════════════════════════════════════════════════════════
# PDF EXPORT (optional — requires LibreOffice)
# ═══════════════════════════════════════════════════════════════════════════════

def convert_docx_to_pdf(docx_path: str) -> Optional[str]:
    """
    Convert a DOCX to PDF using LibreOffice's headless mode.
    Returns the PDF path on success, None if LibreOffice is not available.
    """
    try:
        output_dir = os.path.dirname(docx_path)
        subprocess.run(
            [
                "soffice",
                "--headless",
                "--convert-to", "pdf",
                "--outdir", output_dir,
                docx_path,
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
        base = os.path.splitext(os.path.basename(docx_path))[0]
        pdf_path = os.path.join(output_dir, f"{base}.pdf")
        if os.path.exists(pdf_path):
            return pdf_path
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"[reformatter] PDF conversion failed (LibreOffice may not be installed): {exc}")
    return None
