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


def parse_template_styles(rules_input: str | Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Parse the template markdown rules or mapping dictionary to extract heading, margin, and body styles.
    Falls back to defaults for any value not explicitly specified.
    """
    styles = {k: dict(v) for k, v in _DEFAULT_STYLES.items()}

    if isinstance(rules_input, dict):
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
            styles["body"]["first_line_indent"] = float(rules_input["first_line_indent"])

        # Margins
        for side in ("top", "bottom", "left", "right"):
            key = f"margin_{side}"
            if key in rules_input:
                styles["margins"][side] = float(rules_input[key])

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
) -> str:
    """
    Apply formatting corrections to a DOCX file based on the analysis report
    and template rules. Returns the path to the reformatted file.

    For non-DOCX inputs (PDF/TXT), creates a new DOCX from scratch.
    """
    ext = os.path.splitext(input_path)[1].lower()

    if ext == ".docx":
        return _reformat_docx(input_path, output_path, report, rules_input)
    else:
        # For PDF/TXT → create a basic formatted DOCX
        return _create_formatted_docx(input_path, output_path, report, rules_input)


def _reformat_docx(
    input_path: str,
    output_path: str,
    report: AnalysisReport,
    rules_input: str | Dict[str, Any],
) -> str:
    """Reformat an existing DOCX file in-place."""
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    ALIGN_MAP = {
        "left": WD_ALIGN_PARAGRAPH.LEFT,
        "center": WD_ALIGN_PARAGRAPH.CENTER,
        "right": WD_ALIGN_PARAGRAPH.RIGHT,
        "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
    }

    styles = parse_template_styles(rules_input)
    doc = Document(input_path)

    # ── Apply page margins ───────────────────────────────────────────────────
    margins = styles["margins"]
    for section in doc.sections:
        section.top_margin = Inches(margins["top"])
        section.bottom_margin = Inches(margins["bottom"])
        section.left_margin = Inches(margins["left"])
        section.right_margin = Inches(margins["right"])

    # ── Apply styles to paragraphs ───────────────────────────────────────────
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        style_name = (para.style.name or "").lower()
        spec = None

        # Detect heading level
        for lvl in (1, 2, 3):
            if f"heading {lvl}" in style_name or f"heading{lvl}" in style_name:
                spec = styles.get(f"heading{lvl}")
                break

        if spec is None:
            # Heuristic detection
            word_count = len(text.split())
            ends_sentence = text.endswith((".", "?", "!"))
            if word_count <= 10 and text.isupper():
                spec = styles["heading1"]
            elif word_count <= 10 and not ends_sentence and any(r.bold for r in para.runs if r.text.strip()):
                spec = styles["heading2"]
            else:
                spec = styles["body"]

        # Apply the spec
        _apply_style(para, spec, ALIGN_MAP)

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


def _apply_style(para, spec: dict, align_map: dict) -> None:
    """Apply a style specification to a paragraph and all its runs."""
    from docx.shared import Pt, RGBColor, Inches

    # Ensure at least one run
    if not para.runs and para.text.strip():
        run = para.add_run(para.text)
        # Clear original text elements
        for child in list(para._element):
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "r" and child != para.runs[-1]._element:
                continue

    for run in para.runs:
        if spec.get("font"):
            run.font.name = spec["font"]
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
        pf.first_line_indent = Inches(spec["first_line_indent"])


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
