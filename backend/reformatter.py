"""
reformatter.py — Document reformatter for Formatify.

After analysis, this module programmatically modifies the document using
python-docx to fix formatting issues identified by Claude. It does NOT ask
Claude to rewrite anything — Python code applies the fixes directly.

Supports:
  - Heading style correction (font, size, bold, spacing)
  - Body text style normalisation
  - Section ordering awareness
  - Generic pagination rules (heading -> intro -> figure/table -> caption
    stay together; tables never split rows; oversized images are scaled)
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


_UNNUMBERED_FRONTMATTER_TITLES = frozenset({
    "abstract",
    "acknowledgement", "acknowledgements", "acknowledgment", "acknowledgments",
    "dedication",
    "declaration",
    "certificate",
    "preface",
    "executive summary",
    "list of abbreviations",
    "list of acronyms",
    "list of symbols",
    "abbreviations",
})


def _is_unnumbered_frontmatter_title(text: str) -> bool:
    """Front-matter headings (Abstract etc.) that must never get a section number."""
    return _normalize_section_title(text) in _UNNUMBERED_FRONTMATTER_TITLES


class _HeadingNumberTracker:
    """Track hierarchical heading counters (1 → 1.1 → 1.2 → 2 → 2.1 …)."""

    _MAX_LEVEL = 4

    def __init__(self) -> None:
        self._counters = [0] * self._MAX_LEVEL

    def next_number(self, level: int) -> str:
        level = max(1, min(self._MAX_LEVEL, level))
        # Never emit 0.x — if a subsection appears before any chapter, start at 1.
        for idx in range(level - 1):
            if self._counters[idx] == 0:
                self._counters[idx] = 1
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
        pf.keep_together = True
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
# PAGINATION RULES (generic, content-agnostic)
#
# Goal: heading -> intro paragraph -> figure/table -> caption behave as ONE
# unbreakable unit. If the unit does not fit on the current page, Word /
# LibreOffice moves the WHOLE unit to the next page.
#
# This runs AFTER all style work so nothing overwrites the keep flags.
# ═══════════════════════════════════════════════════════════════════════════════

_CAPTION_RE = re.compile(r"^\s*(figure|fig\.?|table|chart|diagram)\s*\d+", re.IGNORECASE)

# An image taller than this share of the usable page height is scaled down so
# heading + intro + image + caption can still fit on a single page.
_MAX_IMAGE_HEIGHT_RATIO = 0.55
_MIN_IMAGE_SCALE = 0.5          # never shrink below 50% of original size
_SHORT_TABLE_MAX_ROWS = 12      # tables up to this size are kept on one page
_MAX_INTRO_PARAS_PULLED = 3     # how many paragraphs above a figure join its chain


def _w_tag(name: str) -> str:
    from docx.oxml.ns import qn
    return qn(f"w:{name}")


def _para_has_drawing(para) -> bool:
    """True if the paragraph holds an inline image / drawing."""
    try:
        return any(_run_contains_drawing(r) for r in para.runs)
    except Exception:
        return False


def _is_heading_style(para) -> bool:
    try:
        name = (para.style.name or "").lower() if para.style is not None else ""
    except Exception:
        return False
    return name.startswith("heading") or name == "title"


def _is_caption_para(para) -> bool:
    text = (para.text or "").strip()
    try:
        style_name = (para.style.name or "").lower() if para.style is not None else ""
    except Exception:
        style_name = ""
    return "caption" in style_name or bool(_CAPTION_RE.match(text))


def _set_keep(para, with_next: Optional[bool] = None, together: Optional[bool] = None) -> None:
    pf = para.paragraph_format
    try:
        if with_next is not None:
            pf.keep_with_next = with_next
        if together is not None:
            pf.keep_together = together
    except Exception:
        pass


def _usable_page_height_inches(doc) -> float:
    """Usable body height (page height minus top/bottom margins) of the last section."""
    try:
        sec = doc.sections[-1]
        page_h = sec.page_height.inches if sec.page_height else 11.69
        top = sec.top_margin.inches if sec.top_margin else 1.0
        bottom = sec.bottom_margin.inches if sec.bottom_margin else 1.0
        return max(3.0, page_h - top - bottom)
    except Exception:
        return 9.0


def _limit_oversized_images(doc, body_start=None) -> int:
    """
    Scale down any inline image taller than _MAX_IMAGE_HEIGHT_RATIO of the
    usable page height (aspect ratio preserved, never below _MIN_IMAGE_SCALE).
    Returns the number of images scaled.
    """
    max_h = _usable_page_height_inches(doc) * _MAX_IMAGE_HEIGHT_RATIO
    scaled = 0
    try:
        shapes = list(doc.inline_shapes)
    except Exception:
        return 0

    for shape in shapes:
        try:
            h_in = shape.height.inches
            w_in = shape.width.inches
            if h_in <= max_h or h_in <= 0:
                continue
            ratio = max(_MIN_IMAGE_SCALE, max_h / h_in)
            shape.width = int(shape.width * ratio)
            shape.height = int(shape.height * ratio)
            scaled += 1
        except Exception:
            continue
    return scaled


def _make_table_pagination_safe(table) -> None:
    """Rows never split, header repeats, short tables stay together, captions stay attached."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.text.paragraph import Paragraph

    n_rows = len(table.rows)
    for r_idx, row in enumerate(table.rows):
        try:
            tr_pr = row._tr.get_or_add_trPr()
            if tr_pr.find(qn("w:cantSplit")) is None:
                tr_pr.append(OxmlElement("w:cantSplit"))
            if r_idx == 0 and tr_pr.find(qn("w:tblHeader")) is None:
                tr_pr.append(OxmlElement("w:tblHeader"))
        except Exception:
            pass

        # Header row always stays with the next row; short tables chain every row.
        chain_row = (r_idx == 0 and n_rows > 1) or (
            n_rows <= _SHORT_TABLE_MAX_ROWS and r_idx < n_rows - 1
        )
        if chain_row:
            for cell in row.cells:
                for p in cell.paragraphs:
                    _set_keep(p, with_next=True)

    # Caption BELOW the table: last row must stay with it.
    try:
        nxt = table._tbl.getnext()
        if nxt is not None and nxt.tag == _w_tag("p"):
            nxt_para = Paragraph(nxt, table._parent)
            if _is_caption_para(nxt_para):
                for cell in table.rows[-1].cells:
                    for p in cell.paragraphs:
                        _set_keep(p, with_next=True)
                _set_keep(nxt_para, together=True)
    except Exception:
        pass


def _apply_pagination_rules(doc, body_start=None) -> None:
    """
    Generic keep-with-next chains.

      heading          -> keep_with_next + keep_together
      image paragraph  -> keep_with_next (stays with its caption below)
      intro paragraphs directly above an image (up to 3) and their heading
                       -> keep_with_next (chain: heading -> intro -> image -> caption)
      caption          -> keep_together; keep_with_next only when it sits ABOVE
                          an image or table
      tables           -> rows can't split, header repeats, caption attached
      oversized images -> scaled down so the whole chain can fit one page
    """
    skip_before_body = None
    if body_start is not None:
        try:
            from docx_fields import _paragraph_is_before_body_start
            skip_before_body = _paragraph_is_before_body_start
        except Exception:
            skip_before_body = None

    def _in_cover(p) -> bool:
        if skip_before_body is None or body_start is None:
            return False
        try:
            return bool(skip_before_body(doc, p, body_start))
        except Exception:
            return False

    try:
        n_scaled = _limit_oversized_images(doc, body_start)
        if n_scaled:
            print(f"[reformatter] pagination: scaled down {n_scaled} oversized image(s)")
    except Exception as exc:
        print(f"[reformatter] image scaling skipped: {exc}")

    paras = list(doc.paragraphs)
    n = len(paras)

    for i, para in enumerate(paras):
        if _in_cover(para):
            continue

        has_img = _para_has_drawing(para)
        is_caption = _is_caption_para(para)

        # Headings always keep with next (reinforces _apply_word_heading).
        if _is_heading_style(para):
            _set_keep(para, with_next=True, together=True)

        if has_img:
            _set_keep(para, with_next=True, together=True)

            # Pull the intro paragraph(s) and the heading above into the chain.
            j = i - 1
            pulled = 0
            while j >= 0 and pulled < _MAX_INTRO_PARAS_PULLED:
                prev = paras[j]
                prev_text = (prev.text or "").strip()

                if _para_has_drawing(prev):
                    break                                   # another figure — stop

                if not prev_text:                           # empty spacer paragraph
                    _set_keep(prev, with_next=True)
                    j -= 1
                    continue

                if _is_caption_para(prev):
                    # Caption BELOW the previous image belongs to that figure -> stop.
                    # Caption ABOVE this image belongs to this figure -> keep chaining.
                    below_prev_image = j - 1 >= 0 and _para_has_drawing(paras[j - 1])
                    if below_prev_image:
                        break

                _set_keep(prev, with_next=True, together=True)
                pulled += 1
                if _is_heading_style(prev):
                    break                                   # heading reached — chain complete
                j -= 1

        elif is_caption:
            _set_keep(para, together=True)

            # Caption ABOVE an image or table must stay with it.
            above_media = False
            nxt_el = para._element.getnext()
            if nxt_el is not None and nxt_el.tag == _w_tag("tbl"):
                above_media = True
            elif i + 1 < n and _para_has_drawing(paras[i + 1]):
                above_media = True

            if above_media:
                _set_keep(para, with_next=True)
                # Intro/heading above a table caption join the chain too.
                if nxt_el is not None and nxt_el.tag == _w_tag("tbl"):
                    j = i - 1
                    pulled = 0
                    while j >= 0 and pulled < _MAX_INTRO_PARAS_PULLED:
                        prev = paras[j]
                        if not (prev.text or "").strip():
                            _set_keep(prev, with_next=True)
                            j -= 1
                            continue
                        if _para_has_drawing(prev) or _is_caption_para(prev):
                            break
                        _set_keep(prev, with_next=True, together=True)
                        pulled += 1
                        if _is_heading_style(prev):
                            break
                        j -= 1
            else:
                # Caption below its media: do NOT chain it to the next block.
                _set_keep(para, with_next=False)

    # Tables: rows must not split, header repeats, captions stay attached.
    for tbl in doc.tables:
        try:
            _make_table_pagination_safe(tbl)
        except Exception as exc:
            print(f"[reformatter] table pagination skipped: {exc}")


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
            clear_numbering_from_heading_styles,
            find_formatify_body_start_element,
            strip_accidental_body_outline_numbering,
            _paragraph_is_before_body_start,
        )
        body_start = find_formatify_body_start_element(doc)
        clear_numbering_from_heading_styles(doc)
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
    # Even when decimal numbering is off, rewrite broken 0.x prefixes (e.g. "0.1 Abstract").
    zero_fix_tracker: Optional[_HeadingNumberTracker] = None

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
            if _is_unnumbered_frontmatter_title(text):
                # Abstract etc.: strip any number, never touch the tracker
                cleaned = _strip_heading_number_prefix(text)
                if cleaned and cleaned != text:
                    _set_paragraph_text_preserve_style(para, cleaned)
                    text = cleaned
            elif level >= 4:
                cleaned = _strip_heading_number_prefix(text)
                # Also drop a depth-4 auto-number if present (e.g. "3.2.1.1. Title")
                if cleaned != text and cleaned:
                    _set_paragraph_text_preserve_style(para, cleaned)
                    text = cleaned
            elif not _is_meta_list_section_title(text):
                prefix_match = re.match(r"^(\d+(?:\.\d+)*)\.?\s+", text)
                prefix = prefix_match.group(1) if prefix_match else None
                zero_based = bool(prefix and str(prefix).split(".", 1)[0] == "0")
                tracker = number_tracker
                if tracker is None and zero_based:
                    if zero_fix_tracker is None:
                        zero_fix_tracker = _HeadingNumberTracker()
                    tracker = zero_fix_tracker
                if tracker is not None:
                    number = tracker.next_number(level)
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

    try:
        from docx_fields import strip_accidental_body_outline_numbering
        strip_accidental_body_outline_numbering(doc)
    except Exception as exc:
        print(f"[reformatter] outline cleanup skipped: {exc}")

    # NEW: generic pagination rules (heading -> intro -> image/table -> caption).
    # Must run AFTER all style work so the keep flags are not overwritten.
    try:
        _apply_pagination_rules(doc, body_start)
    except Exception as exc:
        print(f"[reformatter] pagination rules skipped (non-fatal): {exc}")

    doc.save(output_path)
    return output_path


def _create_formatted_docx(
    input_path: str,
    output_path: str,
    report: AnalysisReport,
    rules_input: str | Dict[str, Any],
) -> str:
    """Create a new DOCX from a non-DOCX source (PDF/TXT).

    PDF path preserves tables and images in reading order (not text-only).
    """
    from io import BytesIO

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

    margins = styles["margins"]
    for section in doc.sections:
        section.top_margin = Inches(margins["top"])
        section.bottom_margin = Inches(margins["bottom"])
        section.left_margin = Inches(margins["left"])
        section.right_margin = Inches(margins["right"])

    usable_width_in = max(
        4.0,
        8.27 - float(margins.get("left", 1.0)) - float(margins.get("right", 1.0)),
    )

    ext = os.path.splitext(input_path)[1].lower()
    if ext == ".txt":
        from pdf_io import PdfFlowBlock

        blocks = [
            PdfFlowBlock(kind="paragraph", page_number=1, top=float(i), text=ln.strip())
            for i, ln in enumerate(open(input_path, "r", encoding="utf-8", errors="replace"))
            if ln.strip()
        ]
    elif ext == ".pdf":
        from pdf_io import extract_pdf_flow_blocks

        blocks = extract_pdf_flow_blocks(input_path)
    else:
        blocks = []

    prev_was_heading = False
    from pdf_io import looks_like_heading_line

    n_para = n_table = n_image = 0

    for block in blocks:
        if block.kind == "table" and block.table:
            rows = block.table
            n_rows = len(rows)
            n_cols = max(len(r) for r in rows) if rows else 0
            if n_rows < 1 or n_cols < 1:
                continue
            table = doc.add_table(rows=n_rows, cols=n_cols)
            try:
                table.style = "Table Grid"
            except Exception:
                pass
            for r_idx, row in enumerate(rows):
                for c_idx in range(n_cols):
                    cell_text = row[c_idx] if c_idx < len(row) else ""
                    cell = table.rows[r_idx].cells[c_idx]
                    cell.text = cell_text
                    for para in cell.paragraphs:
                        for run in para.runs:
                            run.font.name = styles["body"].get("font", "Times New Roman")
                            try:
                                run.font.size = Pt(float(styles["body"].get("size", 11)))
                            except Exception:
                                pass
            # Spacer after table
            if getattr(block, "caption", None):
                cap = doc.add_paragraph()
                cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cap.paragraph_format.keep_together = True          # NEW
                run = cap.add_run(block.caption)
                run.italic = True
                try:
                    run.font.name = styles["body"].get("font", "Times New Roman")
                    run.font.size = Pt(10)
                except Exception:
                    pass
            else:
                doc.add_paragraph()
            n_table += 1
            prev_was_heading = False
            continue

        if block.kind == "image" and block.image_bytes:
            try:
                para = doc.add_paragraph()
                para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                para.paragraph_format.keep_with_next = True        # NEW: image stays with caption
                para.paragraph_format.keep_together = True         # NEW
                run = para.add_run()
                width_in = usable_width_in * 0.85
                if block.width_pt and block.width_pt > 0:
                    width_in = min(usable_width_in * 0.92, max(1.5, block.width_pt / 72.0))
                run.add_picture(BytesIO(block.image_bytes), width=Inches(width_in))
                # Caption must sit immediately below the image
                caption_text = (getattr(block, "caption", None) or "").strip()
                if caption_text:
                    cap = doc.add_paragraph()
                    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    cap.paragraph_format.keep_together = True      # NEW
                    try:
                        cap.style = doc.styles["Caption"]
                    except Exception:
                        pass
                    cr = cap.add_run(caption_text)
                    cr.italic = True
                    try:
                        cr.font.name = styles["body"].get("font", "Times New Roman")
                        cr.font.size = Pt(10)
                    except Exception:
                        pass
                n_image += 1
                prev_was_heading = False
            except Exception as exc:
                print(f"[reformatter] skip embedding image: {exc}")
            continue

        text = (block.text or "").strip()
        if not text:
            continue

        word_count = len(text.split())
        ends_sentence = text.endswith((".", "?", "!"))
        heading_level = 0
        is_list = bool(getattr(block, "is_list_item", False))
        from pdf_io import (
            looks_like_bullet_marker_line,
            looks_like_caption_line,
            strip_list_marker,
        )
        if looks_like_caption_line(text):
            # Orphan caption (no image bound) — still center it
            para = doc.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            para.paragraph_format.keep_together = True             # NEW
            run = para.add_run(text)
            run.italic = True
            n_para += 1
            prev_was_heading = False
            continue
        # PDF→DOCX: only auto-bullet EXPLICIT markers. Label:colon rows stay
        # Normal so the formatting agent can confirm true lists.
        if is_list and not looks_like_bullet_marker_line(text):
            is_list = False
        if not is_list:
            is_list = looks_like_bullet_marker_line(text)

        if is_list:
            body_text = strip_list_marker(text) or text
            para = doc.add_paragraph()
            para.add_run(body_text)
            try:
                para.style = doc.styles["List Bullet"]
            except Exception:
                try:
                    para.style = "List Bullet"
                except Exception:
                    pass
            # Soft body font on list items
            spec = dict(styles["body"])
            spec["first_line_indent"] = 0
            _apply_style(para, spec, ALIGN_MAP)
            n_para += 1
            prev_was_heading = False
            continue

        if looks_like_heading_line(text) or (word_count <= 10 and text.isupper()):
            if text.isupper() or re.match(
                r"(?i)^(abstract|introduction|conclusion|references|methodology)\b",
                text,
            ):
                heading_level = 1
                spec = styles["heading1"]
            else:
                heading_level = 2
                spec = styles.get("heading2", styles["heading1"])
        elif word_count <= 10 and text.istitle() and not ends_sentence:
            heading_level = 2
            spec = styles.get("heading2", styles["heading1"])
        else:
            spec = dict(styles["body"])
            if prev_was_heading:
                spec["first_line_indent"] = 0

        para = doc.add_paragraph()
        para.add_run(text)
        _apply_style(para, spec, ALIGN_MAP)
        if heading_level:
            try:
                force_heading_style(para, doc, heading_level)
            except Exception:
                pass
            _set_keep(para, with_next=True, together=True)         # NEW
        prev_was_heading = heading_level > 0
        n_para += 1

    print(
        f"[reformatter] PDF→DOCX: {n_para} paragraphs, "
        f"{n_table} tables, {n_image} images"
    )

    # NEW: generic pagination rules (heading -> intro -> image/table -> caption)
    try:
        _apply_pagination_rules(doc)
    except Exception as exc:
        print(f"[reformatter] pagination rules skipped (non-fatal): {exc}")

    doc.save(output_path)
    return output_path


def _run_contains_drawing(run) -> bool:
    """True when a run holds a picture/drawing — clearing run.text would delete it."""
    try:
        el = run._element
    except Exception:
        return False
    drawing = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing"
    pict = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pict"
    blip = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
    if list(el.iter(drawing)) or list(el.iter(pict)) or list(el.iter(blip)):
        return True
    return False


def _set_paragraph_text_preserve_style(para, new_text: str) -> None:
    """Set paragraph text without destroying image runs."""
    if not para.runs:
        para.add_run(new_text)
        return

    text_runs = [r for r in para.runs if not _run_contains_drawing(r)]
    if not text_runs:
        # Paragraph is image-only — do not wipe drawings
        return

    text_runs[0].text = new_text
    for run in text_runs[1:]:
        run.text = ""


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
    Falls back to a text-based PyMuPDF render if LibreOffice is unavailable.
    Returns the PDF path on success, None on failure.
    """
    output_dir = os.path.dirname(docx_path)
    base = os.path.splitext(os.path.basename(docx_path))[0]
    pdf_path = os.path.join(output_dir, f"{base}.pdf")

    try:
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
        if os.path.exists(pdf_path):
            return pdf_path
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"[reformatter] LibreOffice PDF conversion unavailable: {exc}")

    # Fallback: extract text from DOCX and write a simple multi-page PDF.
    try:
        import fitz  # PyMuPDF
        from docx import Document as DocxDocument

        doc = DocxDocument(docx_path)
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
        if not paragraphs:
            paragraphs = ["(Empty document)"]

        pdf = fitz.open()
        page = pdf.new_page(width=595, height=842)  # A4
        margin = 50
        y = margin
        font_size = 11
        line_height = font_size + 6
        max_width = 595 - (margin * 2)

        for para in paragraphs:
            # Soft-wrap long lines
            words = para.split()
            lines: list[str] = []
            current = ""
            for word in words:
                trial = f"{current} {word}".strip()
                # Approx wrap width without relying on get_text_length API variants.
                approx_width = len(trial) * (font_size * 0.55)
                if approx_width <= max_width:
                    current = trial
                else:
                    if current:
                        lines.append(current)
                    current = word
            if current:
                lines.append(current)
            if not lines:
                lines = [""]

            for line in lines:
                if y + line_height > 842 - margin:
                    page = pdf.new_page(width=595, height=842)
                    y = margin
                page.insert_text(
                    (margin, y),
                    line,
                    fontsize=font_size,
                    fontname="helv",
                    color=(0, 0, 0),
                )
                y += line_height
            y += 8  # paragraph gap

        pdf.save(pdf_path)
        pdf.close()
        if os.path.exists(pdf_path):
            return pdf_path
    except Exception as exc:
        print(f"[reformatter] PyMuPDF PDF fallback failed: {exc}")

    return None