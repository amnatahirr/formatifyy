from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Body
from fastapi.responses import FileResponse, StreamingResponse
import os
import shutil
from datetime import datetime
from database import get_db
from docx import Document as DocxDocument
from pypdf import PdfReader
import io
import subprocess
import tempfile
from pydantic import BaseModel
import json
from docx.oxml.ns import qn
from lxml import etree
import re

import uuid
from services.image_relevance import analyze_image_relevance
from services.image_detector import image_detector
from docx import Document as DocxDocument
from PIL import Image as PILImage
from routers.format_document import build_formatted_elements_for_document, export_elements_to_docx
from services.document_block_extractor import extract_blocks as extract_blocks_layer1
from formatter.docx_formatter import apply_template_headings

# Bullet detection imports
from services.bullet_detection_service import BulletDetectionService
from services.bullet_formatter_service import BulletFormatterService
from services.bullet_sequence_detector import BulletSequenceDetector
from formatter.paragraph_formatter import paragraph_formatter

# ── Layer-3 checker imports ───────────────────────────────────────────────────
# checker/ lives at the project root (one level above backend/).
# Dynamically add the project root to sys.path so imports resolve correctly
# whether the server is launched from backend/ or from the project root.
import sys as _sys
import pathlib as _pathlib

# documents.py lives at:  …/backend/routers/documents.py
# checker/ lives at:      …/backend/checker/
# So we need .parent (routers/) → .parent (backend/) to reach checker/
_ROUTERS_DIR  = _pathlib.Path(__file__).resolve().parent          # …/backend/routers/
_BACKEND_DIR  = _ROUTERS_DIR.parent                               # …/backend/
_PROJECT_ROOT = _BACKEND_DIR.parent                               # …/ (project root)

for _p in [str(_BACKEND_DIR), str(_PROJECT_ROOT), str(_ROUTERS_DIR)]:
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

# Import each checker independently so one missing module doesn't disable the others
ContentChecker  = None
check_structure = None
StyleChecker    = None
PerfectContentChecker = None  # NEW: Import the perfect checker

try:
    from checker.content_checker import ContentChecker
    print("[documents] ✓ ContentChecker loaded")
except Exception as _e:
    print(f"[documents] ✗ ContentChecker import failed: {_e}")

try:
    from checker.perfect_content_checker import PerfectContentChecker, create_perfect_checker  # NEW
    print("[documents] ✓ PerfectContentChecker loaded")
except Exception as _e:
    print(f"[documents] ✗ PerfectContentChecker import failed: {_e}")

try:
    from services.structure_checker import check_structure
    print("[documents] ✓ structure_checker loaded")
except Exception as _e:
    print(f"[documents] ✗ structure_checker import failed: {_e}")

try:
    from checker.style_checker import StyleChecker
    print("[documents] ✓ StyleChecker loaded")
except Exception as _e:
    print(f"[documents] ✗ StyleChecker import failed: {_e}")

# _CHECKERS_AVAILABLE = True as long as at least ContentChecker loaded
_CHECKERS_AVAILABLE = ContentChecker is not None
print(f"[documents] _CHECKERS_AVAILABLE={_CHECKERS_AVAILABLE}  "
      f"content={ContentChecker is not None}  "
      f"structure={check_structure is not None}  "
      f"style={StyleChecker is not None}  "
      f"perfect={PerfectContentChecker is not None}")

# Singleton instances — loaded once at startup, not per request
try:
    _content_checker = ContentChecker() if ContentChecker is not None else None
except Exception as _e:
    print(f"[documents] ✗ ContentChecker() instantiation failed: {_e}")
    _content_checker = None

# NEW: Initialize Perfect Content Checker
try:
    _perfect_content_checker = create_perfect_checker() if PerfectContentChecker is not None else None
    if _perfect_content_checker:
        print("[documents] ✓ PerfectContentChecker instantiated successfully")
except Exception as _e:
    print(f"[documents] ✗ PerfectContentChecker() instantiation failed: {_e}")
    _perfect_content_checker = None

try:
    _style_checker = StyleChecker() if StyleChecker is not None else None
except Exception as _e:
    print(f"[documents] ✗ StyleChecker() instantiation failed: {_e}")
    _style_checker = None

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Initialize bullet detection services
bullet_detection_service = BulletDetectionService()
bullet_formatter_service = BulletFormatterService()
bullet_sequence_detector = BulletSequenceDetector()

UPLOAD_FOLDER   = "uploads"
WORKING_FOLDER  = "uploads/working"          # per-document working copies
os.makedirs(UPLOAD_FOLDER,  exist_ok=True)
os.makedirs(WORKING_FOLDER, exist_ok=True)


def _working_copy_path(document_id: int) -> str:
    """
    Returns the path to the per-document working copy.
    This file accumulates incremental fixes (e.g. apply-fix calls)
    without ever touching the original uploaded file.
    """
    return os.path.join(WORKING_FOLDER, f"doc_{document_id}_working.docx")


def _get_effective_path(document_id: int, original_path: str) -> str:
    """
    Returns the working copy path if one exists, otherwise the original path.
    All read operations should use this so they see previous fixes.
    """
    wc = _working_copy_path(document_id)
    return wc if os.path.exists(wc) else original_path


def _apply_template_styles_to_docx(
    input_path: str,
    output_path: str,
    formatting_rules: dict,
) -> None:
    """
    KEY FIX — Bug 3: Apply template heading and paragraph styles to every
    paragraph in the document.

    This function was completely missing from the download pipeline.
    The template rules (font, size, bold, spacing, alignment) were loaded
    from the database but never written back into the document, so the
    downloaded file always looked identical to the upload.

    Heading level is detected by:
      1. Word 'Heading N' style name  (explicit)
      2. Font size >= 18pt            → H1
      3. Font size >= 14pt            → H2
      4. ALL CAPS short line          → H2
      5. Bold + short + no period     → H3
    Everything else is treated as a body paragraph.
    """
    from docx import Document as _Document
    from docx.shared import Pt as _Pt, RGBColor as _RGBColor, Inches as _Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH as _WD

    _ALIGN = {
        "left":    _WD.LEFT,
        "center":  _WD.CENTER,
        "right":   _WD.RIGHT,
        "justify": _WD.JUSTIFY,
    }

    def _heading_lvl_from_style(sname: str):
        low = (sname or "").lower()
        for lv in (1, 2, 3, 4):
            if f"heading {lv}" in low or f"heading{lv}" in low:
                return lv
        return None

    def _detect_level(para):
        lvl = _heading_lvl_from_style(para.style.name)
        if lvl:
            return lvl
        txt = para.text.strip()
        wc  = len(txt.split())
        if not txt or wc == 0:
            return None
        ends_sent = txt.endswith((".", "?", "!"))
        fsize = next((r.font.size.pt for r in para.runs if r.font.size), None)
        if fsize and fsize >= 18 and wc <= 12 and not ends_sent:
            return 1
        if fsize and fsize >= 14 and wc <= 12 and not ends_sent:
            return 2
        if txt.isupper() and 1 <= wc <= 8:
            return 2
        is_bold = any(r.bold for r in para.runs if r.text.strip())
        if is_bold and wc <= 10 and not ends_sent:
            return 3
        return None

    def _hex_to_rgb(value: str):
        try:
            hex_value = (value or "#000000").lstrip("#")
            if len(hex_value) != 6:
                return _RGBColor(0, 0, 0)
            return _RGBColor(
                int(hex_value[0:2], 16),
                int(hex_value[2:4], 16),
                int(hex_value[4:6], 16),
            )
        except Exception:
            return _RGBColor(0, 0, 0)

    def _apply(para, spec: dict):
        # Ensure at least one run exists
        if not para.runs and para.text.strip():
            run = para.add_run(para.text)
            for child in list(para._element):
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == "t":
                    child.getparent().remove(child)
        for run in para.runs:
            if spec.get("font_name"):
                run.font.name = spec["font_name"]
            if spec.get("font_size"):
                run.font.size = _Pt(spec["font_size"])
            if "bold" in spec:
                run.font.bold = bool(spec["bold"])
            if "italic" in spec:
                run.font.italic = bool(spec["italic"])
            if "underline" in spec:
                run.font.underline = bool(spec["underline"])
            if spec.get("color"):
                run.font.color.rgb = _hex_to_rgb(spec["color"])
        pf = para.paragraph_format
        if spec.get("line_spacing") is not None:
            pf.line_spacing = spec["line_spacing"]
        if spec.get("space_before") is not None:
            pf.space_before = _Pt(spec["space_before"])
        if spec.get("space_after") is not None:
            pf.space_after = _Pt(spec["space_after"])
        if spec.get("alignment") in _ALIGN:
            pf.alignment = _ALIGN[spec["alignment"]]
        if spec.get("first_line_indent_in") is not None:
            pf.first_line_indent = _Inches(spec["first_line_indent_in"])
        if spec.get("left_indent_in") is not None:
            pf.left_indent = _Inches(spec["left_indent_in"])

    # Build style specs from rules (with sensible defaults)
    r = formatting_rules or {}
    spacing_unit = r.get("spacing_unit", "in")

    def _to_points(value, default_value):
        raw = value if value is not None else default_value
        try:
            numeric = float(raw)
        except (TypeError, ValueError):
            numeric = float(default_value)
        unit = (spacing_unit or "in").lower()
        if unit in ("in", "inch", "inches"):
            return numeric * 72.0
        if unit == "cm":
            return numeric * 28.3464567
        if unit == "mm":
            return numeric * 2.83464567
        return numeric
    heading_specs = {
        1: {
            "font_name":    r.get("heading1_font",         r.get("body_font", "Times New Roman")),
            "font_size":    r.get("heading1_size",         16),
            "bold":         r.get("heading1_bold",         True),
            "italic":       r.get("heading1_italic",       False),
            "underline":    r.get("heading1_underline",    False),
            "color":        r.get("heading1_color",        "#000000"),
            "line_spacing": r.get("heading1_line_spacing", 1.5),
            "space_before": _to_points(r.get("heading1_space_before"), 12),
            "space_after":  _to_points(r.get("heading1_space_after"),  6),
            "alignment":    r.get("heading1_alignment",    "left"),
        },
        2: {
            "font_name":    r.get("heading2_font",         r.get("body_font", "Times New Roman")),
            "font_size":    r.get("heading2_size",         14),
            "bold":         r.get("heading2_bold",         True),
            "italic":       r.get("heading2_italic",       False),
            "underline":    r.get("heading2_underline",    False),
            "color":        r.get("heading2_color",        "#000000"),
            "line_spacing": r.get("heading2_line_spacing", 1.5),
            "space_before": _to_points(r.get("heading2_space_before"), 10),
            "space_after":  _to_points(r.get("heading2_space_after"),  5),
            "alignment":    r.get("heading2_alignment",    "left"),
        },
        3: {
            "font_name":    r.get("heading3_font",         r.get("body_font", "Times New Roman")),
            "font_size":    r.get("heading3_size",         13),
            "bold":         r.get("heading3_bold",         True),
            "italic":       r.get("heading3_italic",       False),
            "underline":    r.get("heading3_underline",    False),
            "color":        r.get("heading3_color",        "#000000"),
            "line_spacing": r.get("heading3_line_spacing", 1.5),
            "space_before": _to_points(r.get("heading3_space_before"), 8),
            "space_after":  _to_points(r.get("heading3_space_after"),  4),
            "alignment":    r.get("heading3_alignment",    "left"),
        },
        4: {
            "font_name":    r.get("heading4_font",         r.get("body_font", "Times New Roman")),
            "font_size":    r.get("heading4_size",         12),
            "bold":         r.get("heading4_bold",         False),
            "italic":       r.get("heading4_italic",       False),
            "underline":    r.get("heading4_underline",    False),
            "color":        r.get("heading4_color",        "#000000"),
            "line_spacing": r.get("heading4_line_spacing", 1.5),
            "space_before": _to_points(r.get("heading4_space_before"), 6),
            "space_after":  _to_points(r.get("heading4_space_after"),  3),
            "alignment":    r.get("heading4_alignment",    "left"),
        },
    }
    body_spec = {
        "font_name":    r.get("body_font",          "Times New Roman"),
        "font_size":    r.get("body_size",          11),
        "bold":         False,
        "italic":       False,
        "underline":    False,
        "color":        r.get("body_color",         "#000000"),
        "line_spacing": r.get("body_line_spacing",  1.0),
        # Paragraph spacing is always stored/interpreted in points (pt).
        "space_before": r.get("body_space_before",  0),
        "space_after":  r.get("body_space_after",   6),
        "alignment":    r.get("body_alignment",     "justify"),
        "first_line_indent_in": paragraph_formatter._to_inches(
            r.get("first_line_indent", 0.5), r.get("spacing_unit", "in")
        ),
    }
    bullet_spec = {
        "font_name":    r.get("bullet_font",          body_spec["font_name"]),
        "font_size":    r.get("bullet_size",          body_spec["font_size"]),
        "bold":         False,
        "italic":       False,
        "underline":    False,
        "color":        r.get("bullet_color",         body_spec["color"]),
        "line_spacing": r.get("bullet_line_spacing",  body_spec["line_spacing"]),
        "space_before": _to_points(r.get("bullet_space_before"),  r.get("body_space_before", 0)),
        "space_after":  _to_points(r.get("bullet_space_after"),   r.get("body_space_after", 6)),
        "alignment":    "left",
        "left_indent_in": paragraph_formatter._to_inches(
            r.get("bullet_indent", 0.25), r.get("spacing_unit", "in")
        ),
    }
    numbered_spec = {
        "font_name":    r.get("numbered_font",         body_spec["font_name"]),
        "font_size":    r.get("numbered_size",         body_spec["font_size"]),
        "bold":         False,
        "italic":       False,
        "underline":    False,
        "color":        r.get("numbered_color",        body_spec["color"]),
        "line_spacing": r.get("numbered_line_spacing", body_spec["line_spacing"]),
        "space_before": _to_points(r.get("numbered_space_before"), r.get("body_space_before", 0)),
        "space_after":  _to_points(r.get("numbered_space_after"),  r.get("body_space_after", 6)),
        "alignment":    "left",
        "left_indent_in": paragraph_formatter._to_inches(
            r.get("numbered_indent", r.get("bullet_indent", 0.25)),
            r.get("spacing_unit", "in"),
        ),
    }

    heading_numbering_style = (r.get("heading_numbering_style", "none") or "none").lower()

    def _to_roman(value: int) -> str:
        vals = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
                (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
                (5, "V"), (4, "IV"), (1, "I")]
        out = []
        n = max(1, int(value))
        for v, sym in vals:
            while n >= v:
                out.append(sym)
                n -= v
        return "".join(out)

    def _to_alpha(value: int, upper: bool = True) -> str:
        n = max(1, int(value))
        out = ""
        while n > 0:
            n -= 1
            out = chr(ord("A") + (n % 26)) + out
            n //= 26
        return out if upper else out.lower()

    def _heading_prefix(counters: dict, level: int) -> str:
        if heading_numbering_style == "decimal":
            return ".".join(str(counters[i]) for i in range(1, level + 1)) + " "
        if heading_numbering_style == "roman":
            if level == 1:
                return f"{_to_roman(counters[1])}. "
            if level == 2:
                return f"{_to_alpha(counters[2], upper=True)}. "
            return f"{counters[level]}. "
        if heading_numbering_style == "alpha":
            if level == 1:
                return f"{_to_alpha(counters[1], upper=True)}. "
            if level == 2:
                return f"{counters[2]}. "
            return f"{_to_alpha(counters[3], upper=False)}. "
        return ""

    def _strip_existing_heading_numbering(text: str) -> str:
        """
        Remove ONLY true outline prefixes like:
          - 1. / 1) / 1.2 / 1.2.3
          - A. / a) / IV. / iv)
          - bare digits followed by a space (e.g. "4 Motivation ...")
        Never remove normal words like "Motivation".
        """
        t = (text or "").strip()
        if not t:
            return t

        # 1) Decimal outline prefix: 1, 1., 1.2, 1.2.3, optionally ending with ) or .
        t2 = re.sub(r"^\s*\d+(?:\.\d+)*[.)]?\s+", "", t)
        if t2 != t:
            return t2.strip()

        # 2) Single alpha marker: A. / a)
        t2 = re.sub(r"^\s*[A-Za-z][.)]\s+", "", t)
        if t2 != t:
            return t2.strip()

        # 3) Roman numeral marker: IV. / iv)
        t2 = re.sub(r"^\s*[IVXLCDMivxlcdm]+[.)]\s+", "", t)
        if t2 != t:
            return t2.strip()

        # 4) Bare leading digits + space (common in messy headings): "4 Motivation ..."
        # Guard with lookahead to avoid stripping years inside sentences.
        t2 = re.sub(r"^\s*\d+\s+(?=[A-Z])", "", t)
        if t2 != t:
            return t2.strip()

        return t

    doc = _Document(input_path)
    # Apply page margins from template
    try:
        margin_top = paragraph_formatter._to_inches(r.get("margin_top", 1.0), spacing_unit)
        margin_bottom = paragraph_formatter._to_inches(r.get("margin_bottom", 1.0), spacing_unit)
        margin_left = paragraph_formatter._to_inches(r.get("margin_left", 1.0), spacing_unit)
        margin_right = paragraph_formatter._to_inches(r.get("margin_right", 1.0), spacing_unit)
        for section in doc.sections:
            section.top_margin = _Inches(margin_top)
            section.bottom_margin = _Inches(margin_bottom)
            section.left_margin = _Inches(margin_left)
            section.right_margin = _Inches(margin_right)
    except Exception as _e:
        print(f"[template-style] margin apply warning: {_e}")

    heading_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for para in doc.paragraphs:
        if not para.text.strip():
            continue
        style_name = (para.style.name or "").lower()
        is_list_bullet = "list bullet" in style_name or "bullet" in style_name
        is_list_number = "list number" in style_name or "number" in style_name
        lvl = _detect_level(para)
        if lvl is not None:
            if heading_numbering_style != "none":
                heading_counts[lvl] += 1
                for reset_lvl in range(lvl + 1, 5):
                    heading_counts[reset_lvl] = 0
                text = para.text.strip()
                text = _strip_existing_heading_numbering(text)
                para.text = f"{_heading_prefix(heading_counts, lvl)}{text}".strip()
            spec = heading_specs.get(lvl, heading_specs[3])
            _apply(para, spec)
            # Also assign Word built-in heading style so TOC / navigation works
            try:
                para.style = doc.styles[f"Heading {lvl}"]
            except Exception:
                pass
        elif is_list_bullet:
            _apply(para, bullet_spec)
        elif is_list_number:
            _apply(para, numbered_spec)
        else:
            _apply(para, body_spec)

    doc.save(output_path)


class TextContentRequest(BaseModel):
    content: str


# -------------------------------
# LibreOffice DOCX → PDF Converter
# -------------------------------
def convert_docx_to_pdf_libreoffice(input_path: str) -> str:
    output_dir = tempfile.mkdtemp()

    subprocess.run(
        [
            "soffice",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            output_dir,
            input_path,
        ],
        check=True,
    )

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.join(output_dir, f"{base_name}.pdf")


# ══════════════════════════════════════════════════════════════════════
# IMAGE EXTRACTION HELPER — FIXED
# ══════════════════════════════════════════════════════════════════════

def _extract_rel_id(element) -> str | None:
    """
    Extract r:embed rId from any XML element using 3 approaches.
    Works regardless of how the docx was generated.
    """
    r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

    # Approach 1: lxml namespace-aware iter (most reliable)
    try:
        for elem in element.iter():
            embed = elem.get(f"{{{r_ns}}}embed")
            if embed and embed.startswith("rId"):
                return embed
    except Exception:
        pass

    # Approach 2: regex on raw XML string (fallback)
    try:
        raw_xml = etree.tostring(element, encoding="unicode")
        match = re.search(r':embed="(rId\d+)"', raw_xml)
        if match:
            return match.group(1)
    except Exception:
        pass

    # Approach 3: XPath on blip element
    try:
        blip_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
        for blip in element.findall(f".//{{{blip_ns}}}blip"):
            embed = blip.get(f"{{{r_ns}}}embed")
            if embed:
                return embed
    except Exception:
        pass

    return None


def _extract_all_images(docx, docx_path: str) -> dict:
    """
    Step 1: Save ALL unique images from docx rels to disk.
    Returns { rId: saved_path }
    """
    saved = {}
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    for rel_id, rel in docx.part.rels.items():
        if "image" in rel.target_ref:
            try:
                img_bytes = rel.target_part.blob
                save_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.png")
                
                # Make sure to close the image properly
                with PILImage.open(io.BytesIO(img_bytes)) as img:
                    img.save(save_path)
                    
                saved[rel_id] = save_path
                print(f"Saved image {rel_id} to {save_path}")
            except Exception as e:
                print(f"Error saving image {rel_id}: {str(e)}")
                continue
                
    return saved

def _build_document_lines_with_images(docx, saved_images: dict) -> list:
    """
    Step 2: Walk all paragraphs in order.
    - Text paragraphs → {"line": N, "text": "..."}
    - Image paragraphs → {"line": N, "text": "[IMAGE]", "image_path": "uploads/x.png"}

    Uses rId matching so each image appears exactly ONCE.
    """
    document_lines = []
    used_rel_ids = set()   # ← prevents same image appearing multiple times
    para_idx = 0

    all_paras = list(docx.paragraphs)

    # Also collect table cell paragraphs
    for table in docx.tables:
        for row in table.rows:
            for cell in row.cells:
                all_paras.extend(cell.paragraphs)

    for para in all_paras:
        para_idx += 1
        xml_str = etree.tostring(para._element, encoding="unicode")
        has_image = any(k in xml_str for k in ["graphic", "drawing", "blipFill"])

        if has_image:
            rel_id = _extract_rel_id(para._element)
       

            if rel_id and rel_id in saved_images and rel_id not in used_rel_ids:
                used_rel_ids.add(rel_id)
                document_lines.append({
                    "line": para_idx,
                    "text": "[IMAGE]",
                    "image_path": saved_images[rel_id],
                })
                # Don't continue — para might also have text

        if para.text.strip():
            document_lines.append({
                "line": para_idx,
                "text": para.text.strip(),
            })

  
         
    return document_lines


# ─────────────────────────────────────────────────────────────────────────────
# Helper – classify a raw {line, text} item into a proper block dict
# ─────────────────────────────────────────────────────────────────────────────
def _enrich_block(item: dict, predictor=None) -> dict:
    text = item.get("text", "").strip()
    if not text or text == "[IMAGE]":
        return {**item, "type": "paragraph", "level": None}

    if predictor:
        try:
            label, _ = predictor(text)
            if label in ("heading1",):
                return {**item, "type": "heading", "level": 1}
            elif label in ("heading2",):
                return {**item, "type": "heading", "level": 2}
            elif label in ("heading3",):
                return {**item, "type": "heading", "level": 3}
            elif label in ("bullet", "list_item"):
                return {**item, "type": "list_item", "level": None}
            else:
                return {**item, "type": "paragraph", "level": None}
        except Exception:
            pass

    word_count = len(text.split())
    is_short   = word_count <= 10
    is_upper   = text.isupper()
    ends_punct = text.endswith((".", "?", "!"))
    starts_bullet = text.startswith(("•", "-", "*", "–", "·"))

    if starts_bullet:
        return {**item, "type": "list_item", "level": None}
    if is_short and not ends_punct and (is_upper or text.istitle()):
        return {**item, "type": "heading", "level": 1}
    return {**item, "type": "paragraph", "level": None}


# -------------------------------
# Upload Document
# -------------------------------
@router.post("/create-report")
async def create_report_from_text(
    user_id: int = Query(...),
    request: dict = Body(...)
):
    try:
        title = request.get("title")
        content = request.get("content")
        template_id = request.get("template_id")

        if not title or not content or not template_id:
            raise HTTPException(status_code=400, detail="Missing required fields")

        conn = get_db()
        user = conn.execute(
            "SELECT id FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stored_filename = f"{timestamp}_{title.replace(' ', '_')}.txt"
        file_path = os.path.join(UPLOAD_FOLDER, stored_filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO documents
            (user_id, template_id, filename, file_path, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, template_id, title, file_path, "completed")
        )

        conn.commit()
        document_id = cursor.lastrowid
        conn.close()

        return {
            "document_id": document_id,
            "filename": title,
            "status": "completed",
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    template_id: int = Query(...),
    user_id: int = Query(...)
):
    try:
        conn = get_db()
        user = conn.execute(
            "SELECT id FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stored_filename = f"{timestamp}_{file.filename}"
        file_path = os.path.join(UPLOAD_FOLDER, stored_filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO documents
            (user_id, template_id, filename, file_path, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, template_id, file.filename, file_path, "completed")
        )

        conn.commit()
        document_id = cursor.lastrowid
        conn.close()

        return {
            "document_id": document_id,
            "filename": file.filename,
            "status": "completed",
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload-text")
async def upload_text_document(
    template_id: int = Query(...),
    user_id: int = Query(...),
    request: dict = Body(...)
):
    try:
        content = request.get("content")

        if not content:
            raise HTTPException(status_code=400, detail="Content is required")

        conn = get_db()
        user = conn.execute(
            "SELECT id FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stored_filename = f"{timestamp}_pasted_content.txt"
        file_path = os.path.join(UPLOAD_FOLDER, stored_filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO documents
            (user_id, template_id, filename, file_path, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, template_id, "Pasted Content", file_path, "completed")
        )

        conn.commit()
        document_id = cursor.lastrowid
        conn.close()

        return {
            "document_id": document_id,
            "filename": "Pasted Content",
            "status": "completed",
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{document_id}/save")
def save_document_content(
    document_id: int,
    request: TextContentRequest,
    user_id: int = Query(...),
):
    """Save edited document content and update formatted document"""
    try:
        conn = get_db()

        doc = conn.execute(
            "SELECT * FROM documents WHERE id = ? AND user_id = ?",
            (document_id, user_id)
        ).fetchone()

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        template_rules = None
        if doc["template_id"]:
            template = conn.execute(
                "SELECT formatting_rules FROM templates WHERE id = ?",
                (doc["template_id"],)
            ).fetchone()
            if template and template["formatting_rules"]:
                template_rules = json.loads(template["formatting_rules"])

        from ML.predictor import predict_line_type
        from services.docx_generator import generate_docx
        from services.pdf_generator import generate_pdf

        lines = request.content.split("\n")
        parsed_lines = []
        prev_type = None

        for line in lines:
            if line.strip():
                label, confidence = predict_line_type(line)
                parsed_lines.append({
                    "text": line.strip(),
                    "type": label,
                    "confidence": confidence
                })
                prev_type = label

        if doc["file_path"]:
            file_ext = os.path.splitext(doc["file_path"])[1].lower()

            if file_ext == ".pdf":
                generate_pdf(parsed_lines, doc["file_path"], template_rules=template_rules)
            elif file_ext == ".docx":
                generate_docx(parsed_lines, doc["file_path"], template_rules=template_rules)
            elif file_ext == ".txt":
                with open(doc["file_path"], "w", encoding="utf-8") as f:
                    f.write(request.content)
            else:
                generate_docx(parsed_lines, doc["file_path"], template_rules=template_rules)

        conn.close()

        return {"document_id": document_id, "message": "Document saved successfully"}

    except Exception as e:
        import traceback
        print(f"Save error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------
# Download Document
# -------------------------------
@router.get("/download/{document_id}")
def download_document(
    document_id: int,
    user_id: int = Query(...),
    format: str = Query(default="docx")
):
    try:
        conn = get_db()
        doc = conn.execute(
            "SELECT filename, file_path, user_id FROM documents WHERE id = ?",
            (document_id,)
        ).fetchone()
        conn.close()

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        if doc["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized")

        if not os.path.exists(doc["file_path"]):
            raise HTTPException(status_code=404, detail="File not found")

        original_file     = doc["file_path"]
        original_filename = doc["filename"]
        original_ext      = os.path.splitext(original_filename)[1].lower()

        file_base = os.path.basename(original_file)
        if "_" in file_base and file_base[:8].isdigit():
            clean_filename = "_".join(file_base.split("_")[1:])
        else:
            clean_filename = original_filename

        if format.lower() == original_ext.strip("."):
            return FileResponse(
                path=original_file,
                filename=clean_filename,
                media_type="application/octet-stream",
            )

        if format.lower() == "pdf" and original_ext == ".docx":
            try:
                pdf_path   = convert_docx_to_pdf_libreoffice(original_file)
                clean_base = os.path.splitext(clean_filename)[0]
                return FileResponse(
                    path=pdf_path,
                    filename=f"{clean_base}.pdf",
                    media_type="application/pdf",
                )
            except subprocess.CalledProcessError:
                raise HTTPException(
                    status_code=500,
                    detail="LibreOffice PDF conversion failed",
                )

        raise HTTPException(status_code=400, detail="Unsupported format")

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────
# Download with Bullet Formatting Applied
# ─────────────────────────────────────────────────────────────────────────
@router.get("/download-with-bullets/{document_id}")
def download_document_with_bullets(
    document_id: int,
    user_id: int = Query(...),
    template_id: int = Query(None),
    apply_bullets: bool = Query(True)
):
    """
    Download document with bullet formatting applied based on template.
    Automatically detects list-like content and applies bullet styles.
    """
    try:
        conn = get_db()
        doc = conn.execute(
            "SELECT filename, file_path, user_id, template_id FROM documents WHERE id = ?",
            (document_id,)
        ).fetchone()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if doc["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        if not os.path.exists(doc["file_path"]):
            raise HTTPException(status_code=404, detail="File not found")
        
        # Get template formatting rules if available
        formatting_rules = {}
        if template_id or doc.get("template_id"):
            tid = template_id or doc["template_id"]
            template = conn.execute(
                "SELECT formatting_rules FROM templates WHERE id = ?",
                (tid,)
            ).fetchone()
            
            if template and template["formatting_rules"]:
                try:
                    formatting_rules = json.loads(template["formatting_rules"])
                except (json.JSONDecodeError, TypeError):
                    formatting_rules = {}
        
        conn.close()
        
        # Only process .docx files
        if not doc["file_path"].endswith(".docx"):
            return FileResponse(
                path=doc["file_path"],
                filename=doc["filename"],
                media_type="application/octet-stream"
            )
        
        # Apply bullet formatting if requested
        if apply_bullets:
            output_path = os.path.join(
                UPLOAD_FOLDER,
                f"formatted_{uuid.uuid4().hex}.docx"
            )
            
            success = bullet_formatter_service.apply_bullet_formatting(
                doc["file_path"],
                output_path,
                formatting_rules=formatting_rules
            )
            
            if success:
                return FileResponse(
                    path=output_path,
                    filename=doc["filename"],
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
        
        # Fallback: return original
        return FileResponse(
            path=doc["file_path"],
            filename=doc["filename"],
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────
# Download Formatted Document (called by DocumentProvider.downloadFormattedDocument)
# Supports format conversion + optional bullet formatting + auto-detection
# ─────────────────────────────────────────────────────────────────────────
@router.get("/download-formatted/{document_id}")
def download_formatted_document(
    document_id: int,
    user_id: int = Query(...),
    format: str = Query(default="docx"),
    apply_bullets: bool = Query(True),
    auto_detect_bullets: bool = Query(True),
):
    """
    Download document with optional bullet formatting applied from the
    admin-chosen template, then convert to the requested format.
    This is the endpoint called by DocumentProvider.downloadFormattedDocument.
    """
    try:
        # Bridge legacy endpoint to the primary pipeline for DOCX exports.
        if format.lower() == "docx":
            conn = get_db()
            row = conn.execute(
                "SELECT filename FROM documents WHERE id = ?",
                (document_id,),
            ).fetchone()
            conn.close()
            if not row:
                raise HTTPException(status_code=404, detail="Document not found")
            elements = build_formatted_elements_for_document(document_id, user_id)[2]
            output_path = os.path.join(UPLOAD_FOLDER, f"pipeline_{uuid.uuid4().hex}.docx")
            export_elements_to_docx(elements, output_path)
            base = os.path.splitext(row["filename"])[0]
            return FileResponse(
                path=output_path,
                filename=f"{base}.docx",
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

        conn = get_db()
        doc = conn.execute(
            "SELECT filename, file_path, user_id, template_id FROM documents WHERE id = ?",
            (document_id,)
        ).fetchone()

        if not doc:
            conn.close()
            raise HTTPException(status_code=404, detail="Document not found")
        if doc["user_id"] != user_id:
            conn.close()
            raise HTTPException(status_code=403, detail="Unauthorized")
        if not os.path.exists(doc["file_path"]):
            conn.close()
            raise HTTPException(status_code=404, detail="File not found on disk")

        # ── Load template formatting rules ────────────────────────────
        formatting_rules = {}
        if doc["template_id"]:
            tmpl = conn.execute(
                "SELECT formatting_rules FROM templates WHERE id = ?",
                (doc["template_id"],)
            ).fetchone()
            if tmpl and tmpl["formatting_rules"]:
                try:
                    formatting_rules = json.loads(tmpl["formatting_rules"])
                except (json.JSONDecodeError, TypeError):
                    formatting_rules = {}

        conn.close()

        # Use working copy if incremental fixes have been applied,
        # otherwise use the original file.
        file_path  = _get_effective_path(document_id, doc["file_path"])
        clean_name = doc["filename"]
        print(f"[download-formatted] reading from: {file_path}")

        # ── Step 1: Apply bullet formatting to a temp DOCX ───────────
        working_path = file_path  # default: original

        if file_path.endswith(".docx"):
            # ── Step 1a: Apply template heading + paragraph styling ───────────
            # KEY FIX: template font/size/spacing rules were loaded but never
            # applied to the document. This step does that before bullet pass.
            styled_path = os.path.join(
                UPLOAD_FOLDER,
                f"styled_{uuid.uuid4().hex}.docx"
            )
            try:
                _apply_template_styles_to_docx(file_path, styled_path, formatting_rules)
                if os.path.exists(styled_path):
                    working_path = styled_path
                    print("[download-formatted] template styles applied successfully")
            except Exception as style_err:
                print(f"[download-formatted] style application error (non-fatal): {style_err}")
                working_path = file_path

            # ── Step 1b: Apply bullet formatting on top ───────────────────────
            if apply_bullets:
                formatting_rules["auto_apply_bullets"] = auto_detect_bullets

                output_path = os.path.join(
                    UPLOAD_FOLDER,
                    f"bulleted_{uuid.uuid4().hex}.docx"
                )

                bullet_mapping = None
                if auto_detect_bullets:
                    try:
                        docx_tmp = DocxDocument(working_path)
                        blocks = []
                        for para in docx_tmp.paragraphs:
                            if para.text.strip():
                                blocks.append({
                                    "type": "paragraph",
                                    "text": para.text.strip(),
                                })
                        detected = bullet_detection_service.detect_bullets_in_blocks(blocks)
                        bullet_mapping = bullet_formatter_service.create_bullet_mapping(
                            [{"index": b.index} for b in detected]
                        )
                    except Exception as det_err:
                        print(f"[download-formatted] bullet detection error: {det_err}")

                success = bullet_formatter_service.apply_bullet_formatting(
                    working_path,
                    output_path,
                    formatting_rules=formatting_rules,
                    bullet_mapping=bullet_mapping,
                )
                if success and os.path.exists(output_path):
                    working_path = output_path
                else:
                    print("[download-formatted] bullet formatting failed, keeping styled version")

        # ── Step 2: Convert format if needed ─────────────────────────
        fmt = format.lower()
        original_ext = os.path.splitext(working_path)[1].lower().strip(".")

        if fmt == original_ext:
            return FileResponse(
                path=working_path,
                filename=clean_name,
                media_type="application/octet-stream",
            )

        if fmt == "pdf" and original_ext == "docx":
            try:
                pdf_path = convert_docx_to_pdf_libreoffice(working_path)
                base = os.path.splitext(clean_name)[0]
                return FileResponse(
                    path=pdf_path,
                    filename=f"{base}.pdf",
                    media_type="application/pdf",
                )
            except subprocess.CalledProcessError:
                raise HTTPException(status_code=500, detail="PDF conversion failed")

        # Fallback: return the working file as-is
        return FileResponse(
            path=working_path,
            filename=clean_name,
            media_type="application/octet-stream",
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[download-formatted] ERROR: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────
# Analyze Document for Bullets
# ─────────────────────────────────────────────────────────────────────────
@router.get("/analyze-bullets/{document_id}")
async def analyze_bullets_in_document(
    document_id: int,
    user_id: int = Query(...)
):
    """
    Analyze document and return detected bullet points with confidence scores.
    """
    try:
        conn = get_db()
        doc = conn.execute(
            "SELECT filename, file_path, user_id FROM documents WHERE id = ?",
            (document_id,)
        ).fetchone()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if doc["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        if not os.path.exists(doc["file_path"]):
            raise HTTPException(status_code=404, detail="File not found")

        conn.close()

        # Use working copy if one exists (has incremental fixes applied),
        # otherwise fall back to the original uploaded file.
        effective_path = _get_effective_path(document_id, doc["file_path"])
        print(f"[analyze-bullets] reading from: {effective_path}")

        # Extract blocks — expand soft-break blobs first so every item
        # gets its own sequential index matching what apply-fix will see.
        if effective_path.endswith(".docx"):
            docx = DocxDocument(effective_path)

            # ── Expand <w:br/> soft-break paragraphs ─────────────────────
            _W2 = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            from copy import deepcopy as _dc2
            from docx.oxml import OxmlElement as _OE2
            _body2 = docx.element.body
            for _p_el in list(_body2.iter(f"{{{_W2}}}p")):
                if not _p_el.findall(f".//{{{_W2}}}br"):
                    continue
                _pPr = _p_el.find(f"{{{_W2}}}pPr")
                _lines = [[]]
                for _r_el in _p_el.findall(f"{{{_W2}}}r"):
                    _rPr = _r_el.find(f"{{{_W2}}}rPr")
                    for _ch in list(_r_el):
                        if _ch.tag == f"{{{_W2}}}t":
                            _lines[-1].append((_rPr, _ch.text or ""))
                        elif _ch.tag == f"{{{_W2}}}br":
                            _lines.append([])
                while _lines and not any(t.strip() for _, t in _lines[-1]):
                    _lines.pop()
                if len(_lines) <= 1:
                    continue
                _parent = _p_el.getparent()
                _pos    = list(_parent).index(_p_el)
                _new_ps = []
                for _frags in _lines:
                    _lt = "".join(t for _, t in _frags).strip()
                    if not _lt:
                        continue
                    _np = _OE2("w:p")
                    if _pPr is not None:
                        _np.append(_dc2(_pPr))
                    _nr = _OE2("w:r")
                    _rp = next((rp for rp, _ in _frags if rp is not None), None)
                    if _rp is not None:
                        _nr.append(_dc2(_rp))
                    _nt = _OE2("w:t")
                    _nt.text = _lt
                    _nt.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                    _nr.append(_nt); _np.append(_nr)
                    _new_ps.append(_np)
                for _off, _np in enumerate(_new_ps):
                    _parent.insert(_pos + _off, _np)
                _parent.remove(_p_el)

            # ── Build blocks from expanded paragraphs ─────────────────────
            # Mark paragraphs that already have OOXML bullet formatting (w:numPr)
            # so the detection function skips them — they've already been fixed.
            # IMPORTANT: preserve stable paragraph indices.
            # Do NOT skip empty paragraphs here; apply-fix targets docx.paragraphs
            # by index, so analysis must return indices from the same coordinate system.
            blocks = []
            for idx, para in enumerate(docx.paragraphs):
                text = para.text.strip()
                style_name = (para.style.name or "").lower() if para.style else ""
                already_bulleted = (
                    para._element.find(
                        f".//{qn('w:numPr')}"
                    ) is not None
                )
                if already_bulleted:
                    # Already has bullets — mark as list_item so detection skips it
                    block_type = "list_item"
                elif "heading" in style_name:
                    block_type = "heading"
                elif "list" in style_name:
                    block_type = "list_item"
                else:
                    block_type = "paragraph"
                blocks.append({
                    "index": idx,
                    "type": block_type,
                    "text": text,
                    "metadata": {"style": style_name}
                })
            
            # Use section-based group detection for accurate results.
            # This finds list items by scanning between headings rather than
            # per-item scoring, and uses the correct expanded-paragraph indices.
            bullet_groups = _detect_bullet_groups_from_expanded_blocks(blocks)

            # Flatten groups into detected_bullets list for summary/display
            detected_dicts = []
            for group in bullet_groups:
                detected_dicts.extend(group)

            return {
                "document_id": document_id,
                "filename": doc["filename"],
                "total_paragraphs": len(docx.paragraphs),
                "detected_bullets": detected_dicts,
                "bullet_groups": bullet_groups,
                "summary": {
                    "total_detected": len(detected_dicts),
                    "high_confidence": len([d for d in detected_dicts if d.get("confidence", 0) > 0.8]),
                    "medium_confidence": len([d for d in detected_dicts if 0.6 < d.get("confidence", 0) <= 0.8]),
                    "low_confidence": len([d for d in detected_dicts if d.get("confidence", 0) <= 0.6]),
                    "total_groups": len(bullet_groups)
                }
            }
        
        raise HTTPException(status_code=400, detail="Only .docx files supported for analysis")
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────
# Preview Document (Plain Content)
# ─────────────────────────────────────────────────────────────────────────
@router.get("/preview/{document_id}")
def preview_document(document_id: int, user_id: int = Query(...)):
    try:
        conn = get_db()
        doc = conn.execute(
            "SELECT filename, file_path, user_id FROM documents WHERE id = ?",
            (document_id,)
        ).fetchone()
        conn.close()

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        if doc["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized")

        file_ext     = os.path.splitext(doc["file_path"])[1].lower()
        preview_text = ""

        if file_ext == ".docx":
            docx         = DocxDocument(doc["file_path"])
            preview_text = "\n".join(p.text for p in docx.paragraphs)
        elif file_ext == ".pdf":
            reader = PdfReader(doc["file_path"])
            for page in reader.pages:
                preview_text += (page.extract_text() or "") + "\n---PAGE---\n"
        elif file_ext == ".txt":
            with open(doc["file_path"], "r", encoding="utf-8") as f:
                preview_text = f.read()
        else:
            preview_text = "Preview not available"

        return {
            "document_id": document_id,
            "filename":    doc["filename"],
            "preview":     preview_text,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------------------------------
# Preview Document (With Formatting)
# -------------------------------
@router.get("/preview-formatted/{document_id}")
def preview_formatted_document(document_id: int, user_id: int = Query(...)):
    try:
        conn = get_db()
        doc = conn.execute(
            "SELECT filename, file_path, user_id, template_id FROM documents WHERE id = ?",
            (document_id,)
        ).fetchone()

        if not doc:
            conn.close()
            raise HTTPException(status_code=404, detail="Document not found")

        if doc["user_id"] != user_id:
            conn.close()
            raise HTTPException(status_code=403, detail="Unauthorized")

        template_rules = None
        if doc["template_id"]:
            template = conn.execute(
                "SELECT formatting_rules FROM templates WHERE id = ?",
                (doc["template_id"],)
            ).fetchone()
            if template and template["formatting_rules"]:
                try:
                    template_rules = json.loads(template["formatting_rules"])
                except json.JSONDecodeError:
                    pass

        conn.close()

        from services.docx_parser import parse_docx
        from services.pdf_parser  import parse_pdf
        from ML.predictor          import predict_line_type

        file_ext     = os.path.splitext(doc["file_path"])[1].lower()
        parsed_lines = []

        try:
            if file_ext == ".docx":
                for para in parse_docx(doc["file_path"]):
                    label, confidence = predict_line_type(para["text"])
                    parsed_lines.append({
                        "text": para["text"], "type": label,
                        "confidence": confidence
                    })
            elif file_ext == ".pdf":
                for line in parse_pdf(doc["file_path"]):
                    text  = line["text"] if isinstance(line, dict) else str(line)
                    label, confidence = predict_line_type(text)
                    parsed_lines.append({
                        "text": text, "type": label, "confidence": confidence
                    })
            elif file_ext == ".txt":
                with open(doc["file_path"], "r", encoding="utf-8") as f:
                    for para in [p.strip() for p in f.read().split("\n") if p.strip()]:
                        label, confidence = predict_line_type(para)
                        parsed_lines.append({
                            "text": para, "type": label, "confidence": confidence
                        })
            else:
                return {
                    "document_id":      document_id,
                    "filename":         doc["filename"],
                    "formatted_content":"Preview not available for this file type",
                    "formatting_rules": template_rules or {}
                }
        except Exception as parse_error:
            return {
                "document_id":      document_id,
                "filename":         doc["filename"],
                "formatted_content":f"Error parsing document: {str(parse_error)}",
                "formatting_rules": template_rules or {}
            }

        return {
            "document_id":      document_id,
            "filename":         doc["filename"],
            "formatted_content":"\n".join(i["text"] for i in parsed_lines),
            "formatted_lines":  [{"text": i["text"], "type": i.get("type", "paragraph")}
                                  for i in parsed_lines],
            "formatting_rules": template_rules or {}
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview error: {str(e)}")


# -------------------------------
# Delete Document
# -------------------------------
@router.delete("/{document_id}")
def delete_document(document_id: int, user_id: int = Query(...)):
    try:
        conn = get_db()
        doc  = conn.execute(
            "SELECT id, file_path, user_id FROM documents WHERE id = ?",
            (document_id,)
        ).fetchone()

        if not doc:
            conn.close()
            raise HTTPException(status_code=404, detail="Document not found")

        if doc["user_id"] != user_id:
            conn.close()
            raise HTTPException(status_code=403, detail="Unauthorized")

        if doc["file_path"] and os.path.exists(doc["file_path"]):
            try:
                os.remove(doc["file_path"])
            except Exception as e:
                print(f"Warning: Could not delete file: {e}")

        conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        conn.commit()
        conn.close()

        return {"message": "Document deleted successfully", "document_id": document_id}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------------------------------
# List Documents
# -------------------------------
@router.get("/")
def list_documents(user_id: int = Query(...)):
    try:
        conn = get_db()
        docs = conn.execute(
            """
            SELECT d.id, d.filename, d.status, d.created_at, d.template_id,
                   d.file_path, t.name as template_name
            FROM documents d
            LEFT JOIN templates t ON d.template_id = t.id
            WHERE d.user_id = ?
            ORDER BY d.created_at DESC
            """,
            (user_id,)
        ).fetchall()
        conn.close()

        result = []
        for d in docs:
            file_size = 0
            if d["file_path"] and os.path.exists(d["file_path"]):
                file_size = os.path.getsize(d["file_path"]) / (1024 * 1024)
            # Append 'Z' so Flutter parses created_at as UTC and converts to local time
            created_at = d["created_at"]
            if created_at and not str(created_at).endswith('Z') and '+' not in str(created_at):
                created_at = str(created_at).replace(' ', 'T') + 'Z'
            result.append({
                "id":            d["id"],
                "filename":      d["filename"],
                "status":        d["status"],
                "created_at":    created_at,
                "template_id":   d["template_id"],
                "template_name": d["template_name"],
                "file_size":     round(file_size, 2),
            })

        return result

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ══════════════════════════════════════════════════════════════════════
# ANALYZE DOCUMENT
# ══════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# Section-based bullet group detection (used by analyze-bullets endpoint)
# ─────────────────────────────────────────────────────────────────────────────
def _detect_bullet_groups_from_expanded_blocks(blocks: list) -> list:
    """
    Detect list groups using section-based scanning (heading → items).
    Operates on the ALREADY-EXPANDED block list so indices are consistent
    with what apply-fix sees after it expands soft-breaks.

    Returns a list of groups, each group being a list of dicts:
        [{"text": ..., "index": ..., "confidence": ..., "reason": ...}, ...]
    """
    return bullet_sequence_detector.detect_groups(blocks)


# ─────────────────────────────────────────────────────────────────────────────
# Bullet Issue Detection — finds list-like paragraphs with no OOXML numbering
# Returns style_issues entries with fix_type="apply_section_bullets" so the
# Style tab can show them with an "Apply Fix" button.
# ─────────────────────────────────────────────────────────────────────────────

def _detect_missing_bullet_issues(docx_path: str) -> list:
    """
    Scan a DOCX for sections that look like lists but have no OOXML bullets.

    Handles ALL heading styles:
      - Word Heading styles  (style name contains "heading")
      - Bold short Normal paragraphs  (is_bold, ≤10 words, no sentence punct)
      - Numbered inline headings  (^N. Title format)
      - ALL-CAPS short labels  (isupper(), ≤8 words)

    For each detected section, if the section items have no w:numPr,
    emits one style issue with fix_type="apply_section_bullets".
    """
    try:
        docx = DocxDocument(docx_path)
        paras = docx.paragraphs

        blocks = []
        for idx, p in enumerate(paras):
            text = p.text.strip()
            if not text:
                continue
            style_name = (p.style.name or "").lower()
            has_numpr = p._element.find(f".//{qn('w:numPr')}") is not None
            if has_numpr or "list" in style_name:
                btype = "list_item"
            elif "heading" in style_name:
                btype = "heading"
            else:
                btype = "paragraph"
            blocks.append({"index": idx, "type": btype, "text": text, "metadata": {"style": style_name}})

        bullet_groups = bullet_sequence_detector.detect_groups(blocks)
        issues = []
        for group in bullet_groups:
            para_indices = [int(it["index"]) for it in group]
            if not para_indices:
                continue
            # Detector works on non-bulleted items; keep this guard for safety.
            if any(paras[i]._element.find(f".//{qn('w:numPr')}") is not None for i in para_indices if i < len(paras)):
                continue

            preview_items = [str(it.get("text", "")).strip()[:60] for it in group[:3]]
            heading = ""
            start_idx = para_indices[0]
            for back in range(start_idx - 1, -1, -1):
                st = (paras[back].style.name or "").lower() if paras[back].style else ""
                if "heading" in st:
                    heading = paras[back].text.strip()
                    break

            issues.append({
                "type": "missing_bullets",
                "code": "MISSING_BULLETS",
                "severity": "WARNING",
                "message": f'List group "{preview_items[0] if preview_items else ""}" is missing bullet formatting.',
                "heading": heading,
                "para_indices": para_indices,
                "preview_items": preview_items,
                "fix_type": "apply_section_bullets",
                "fix_details": {
                    "heading": heading,
                    "para_indices": para_indices,
                },
            })

        print(f"[BulletCheck] returning {len(issues)} issue(s)")
        return issues

    except Exception as e:
        import traceback
        print(f"[BulletCheck] ERROR: {traceback.format_exc()}")
        return []


import difflib

def detect_headings_from_template(doc_paragraphs, template_id, db):
    """
    Detect headings by fuzzy matching paragraph text against template required_sections.
    Threshold: 0.85. Includes detailed [HeadingDetect] terminal logging.
    """
    if not template_id:
        return []

    tmpl = db.execute(
        "SELECT name, required_sections FROM templates WHERE id = ?",
        (template_id,)
    ).fetchone()
    if not tmpl or not tmpl["required_sections"]:
        return []

    try:
        raw_sections = json.loads(tmpl["required_sections"])
    except Exception:
        return []

    template_name = tmpl["name"] if tmpl["name"] else f"template#{template_id}"
    expected_headings = []
    for sec in raw_sections:
        if isinstance(sec, dict) and "name" in sec:
            expected_headings.append(sec["name"])
        elif isinstance(sec, str):
            expected_headings.append(sec)

    print(f"[HeadingDetect] Template: {template_name} | Sections: {expected_headings}")

    results = []
    claimed_sections = set()   # prevent one section matching multiple paragraphs

    for idx, block in enumerate(doc_paragraphs):
        text = block.get("text", "").strip()
        if not text or len(text.split()) > 15:
            continue

        text_lower = text.lower()
        best_match = None
        best_score = 0.0

        for expected in expected_headings:
            if expected in claimed_sections:
                continue
            expected_lower = expected.lower()
            score = difflib.SequenceMatcher(None, text_lower, expected_lower).ratio()
            print(f"[HeadingDetect] Para {idx}: \"{text[:50]}\" vs \"{expected}\" => score={score:.3f}")
            if score > best_score:
                best_score = score
                best_match = expected

        if best_score >= 0.85 and best_match is not None:
            claimed_sections.add(best_match)
            block["type"] = "heading"
            print(f"[HeadingDetect] MATCH: Para {idx} -> \"{best_match}\" (confidence={best_score:.3f})")
            results.append({
                "para_index": idx,
                "text": text,
                "matched_template_heading": best_match,
                "heading_level": 1,
                "confidence": round(best_score, 4),
            })

    print(f"[HeadingDetect] Summary: {len(results)}/{len(expected_headings)} headings found")
    return results

@router.get("/analyze/{document_id}")
def analyze_document(
    document_id: int, 
    user_id: int = Query(...),
    use_perfect_checker: bool = Query(True)  # NEW: Flag to use perfect checker
):
    try:
        conn = get_db()
        doc = conn.execute(
            "SELECT filename, file_path, user_id, template_id FROM documents WHERE id = ?",
            (document_id,)
        ).fetchone()

        if not doc:
            conn.close()
            raise HTTPException(status_code=404, detail="Document not found")
        if doc["user_id"] != user_id:
            conn.close()
            raise HTTPException(status_code=403, detail="Unauthorized")

        file_ext = os.path.splitext(doc["file_path"])[1].lower()
        document_lines = []
        issues = []

        # ── Load template rules & required sections ───────────────────
        template_rules     = {}
        required_sections  = []
        if doc["template_id"]:
            tmpl = conn.execute(
                "SELECT formatting_rules, required_sections FROM templates WHERE id = ?",
                (doc["template_id"],)
            ).fetchone()
            if tmpl:
                if tmpl["formatting_rules"]:
                    try:
                        template_rules = json.loads(tmpl["formatting_rules"])
                    except Exception:
                        pass
                if tmpl["required_sections"]:
                    try:
                        required_sections = json.loads(tmpl["required_sections"])
                    except Exception:
                        pass

        # ── Build blocks list for Layer-3 checkers ────────────────────
        # blocks = [{"type": "heading"|"paragraph", "text": "...", "level": N}]
        # We build this from document_lines after parsing, so we can run
        # structure + content + style checks using the same data.
        doc_blocks = []
        # Clear old image records for this document before new analysis
        conn.execute("DELETE FROM document_images WHERE document_id = ?", (document_id,))
        conn.commit()

        # ══════════════════════════════════════════════════════════════
        # DOCX PROCESSING
        # ══════════════════════════════════════════════════════════════
        if file_ext == ".docx":
            # Open and process the document
            docx = DocxDocument(doc["file_path"])

            # ── Step 1: Save all unique images keyed by rId ───────────
            saved_images = _extract_all_images(docx, doc["file_path"])

            # ── Step 2: Build document_lines with correct image paths ─
            document_lines = _build_document_lines_with_images(docx, saved_images)

            # ── Step 3: Build proper typed blocks for Layer-3 checkers ─
            # Use the shared Layer-1 extractor (reads paragraph-level XML font sizes),
            # so Normal-style headings are detected reliably.
            try:
                extracted = extract_blocks_layer1(doc["file_path"])
                doc_blocks = [
                    {
                        "type": b["type"],
                        "text": b["text"],
                        "level": b.get("level"),
                        # Preserve extractor signals so StructureChecker can fall back
                        # to BulletCheck-like heading detection when heading types are missing.
                        "style": b.get("style"),
                        "is_bold": b.get("is_bold"),
                    }
                    for b in extracted
                    if b.get("type") in ("heading", "paragraph", "list_item", "table")
                    and b.get("text", "").strip()
                ]
            except Exception as e:
                print(f"[analyze] extract_blocks failed, falling back to legacy walker: {e}")
            print(f"[analyze] extracted {len(doc_blocks)} blocks")
            heading_blocks = [b for b in doc_blocks if b.get("type") == "heading"]
            print(f"[analyze] found {len(heading_blocks)} heading blocks")

            # ── Step 3: Run relevance + ethics check on each [IMAGE] ──
            # ── Step 3: Store image information in database BEFORE analysis ──
            for line_info in document_lines:
                if line_info.get("text") == "[IMAGE]":
                    image_path = line_info.get("image_path")
                    line_number = line_info.get("line")
                    print(f"Storing image at line {line_number}: {image_path}")
                    
                    if image_path and os.path.exists(image_path):
                        # Store in database
                        try:
                            conn.execute(
                                """
                                INSERT INTO document_images 
                                (document_id, image_path, image_filename, line_number) 
                                VALUES (?, ?, ?, ?)
                                """,
                                (document_id, image_path, os.path.basename(image_path), line_number)
                            )
                            conn.commit()
                            print(f"Stored image for document {document_id} at line {line_number}: {image_path}")
                        except Exception as e:
                            print(f"Error storing image in database: {e}")

            # ── Step 4: Run relevance + ethics check on each [IMAGE] ──
            MAX_CHARS = 500

            for idx, line_info in enumerate(document_lines):
                if line_info.get("text") != "[IMAGE]":
                    continue

                image_path = line_info.get("image_path")
                if not image_path or not os.path.exists(image_path):
                    continue

                # Extract context from surrounding lines
                heading = ""
                for i in range(idx - 1, -1, -1):
                    candidate = document_lines[i].get("text", "")
                    if not candidate or candidate == "[IMAGE]":
                        continue
                    if len(candidate.split()) <= 12 and not candidate.endswith("."):
                        heading = candidate
                        break

                before_parts = []
                count = 0
                for i in range(idx - 1, -1, -1):
                    candidate = document_lines[i].get("text", "")
                    if candidate and candidate != "[IMAGE]":
                        before_parts.insert(0, candidate)
                        count += 1
                        if count == 2:
                            break
                before_text = " ".join(before_parts)

                after_text = ""
                for i in range(idx + 1, len(document_lines)):
                    candidate = document_lines[i].get("text", "")
                    if candidate and candidate != "[IMAGE]":
                        after_text = candidate
                        break

                heading     = heading[:MAX_CHARS]
                before_text = before_text[:MAX_CHARS]
                after_text  = after_text[:MAX_CHARS]

                # ── Relevance check ───────────────────────────────────
                res = analyze_image_relevance(
                    image_path=image_path,
                    heading=heading,
                    before_text=before_text,
                    after_text=after_text,
                )

                if not res["relevant"]:
                    issues.append({
                        "type":        "CRITICAL",
                        "category":    "Image Relevance",
                        "line":        line_info["line"],
                        "description": "This image is not relevant to document content. Please replace it.",
                        "current":     os.path.basename(image_path),
                        "suggestion":  "Upload relevant image",
                        "image_path": os.path.basename(image_path),
                        "confidence":  res["final_score"],
                    })

                # ── Ethics check (runs on ALL images) ─────────────────
                ethics_res = image_detector.analyze_image(image_path)
                if not ethics_res["is_safe"]:
                    issues.append({
                        "type":            "CRITICAL",
                        "category":        "Image Ethics",
                        "line":            line_info["line"],
                        "description":     ethics_res["caption"] or "Unethical content detected.",
                        "current":         os.path.basename(image_path),
                        "suggestion":      "Remove or replace this image immediately.",
                        "image_path": os.path.basename(image_path),
                        "ethics_category": ethics_res["category"] or "Unethical Content",
                        "confidence":      ethics_res["confidence_score"],
                    })

            # IMPORTANT: DO NOT DELETE temporary image files here
            # We need them for export, so comment out or remove the deletion code
            # for img_path in saved_images.values():
            #     try:
            #         if os.path.exists(img_path):
            #             os.remove(img_path)
            #             print(f"Deleted temporary image: {img_path}")
            #     except Exception as e:
            #         print(f"Error deleting temp image {img_path}: {str(e)}")

        # ══════════════════════════════════════════════════════════════
        # PDF PROCESSING
        # ══════════════════════════════════════════════════════════════
        elif file_ext == ".pdf":
            reader   = PdfReader(doc["file_path"])
            line_num = 1
            for page in reader.pages:
                text = page.extract_text() or ""
                for paragraph in text.split("\n"):
                    if paragraph.strip():
                        document_lines.append({"line": line_num, "text": paragraph.strip()})
                        line_num += 1
            # Build doc_blocks from PDF lines using heuristic heading detection
            for item in document_lines:
                t  = item.get("text", "").strip()
                wc = len(t.split())
                if t.isupper() and 1 <= wc <= 8:
                    doc_blocks.append({"type": "heading", "text": t, "level": 2})
                elif wc <= 8 and not t.endswith("."):
                    doc_blocks.append({"type": "heading", "text": t, "level": 3})
                else:
                    doc_blocks.append({"type": "paragraph", "text": t, "level": None})

        # ══════════════════════════════════════════════════════════════
        # TXT PROCESSING
        # ══════════════════════════════════════════════════════════════
        elif file_ext == ".txt":
            with open(doc["file_path"], "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    if line.strip():
                        document_lines.append({"line": line_num, "text": line.strip()})
            for item in document_lines:
                t  = item.get("text", "").strip()
                wc = len(t.split())
                if t.isupper() and 1 <= wc <= 8:
                    doc_blocks.append({"type": "heading", "text": t, "level": 2})
                elif wc <= 8 and not t.endswith("."):
                    doc_blocks.append({"type": "heading", "text": t, "level": 3})
                else:
                    doc_blocks.append({"type": "paragraph", "text": t, "level": None})
        else:
            conn.close()
            raise HTTPException(status_code=400, detail="Unsupported file format")

        # ── Text issues detection (capitalization / double spaces) ────
        for line_info in document_lines:
            text     = line_info.get("text", "")
            line_num = line_info.get("line", 0)

            if text == "[IMAGE]":
                continue

            if text and not text[0].isupper() and len(text) > 20:
                issues.append({
                    "type":        "CRITICAL",
                    "category":    "Capitalization Error",
                    "line":        line_num,
                    "description": "Sentence should start with capital letter",
                    "current":     text,
                    "suggestion":  text.capitalize(),
                })

            if "  " in text:
                issues.append({
                    "type":        "WARNING",
                    "category":    "Formatting Issue",
                    "line":        line_num,
                    "description": "Multiple spaces detected",
                    "current":     text,
                    "suggestion":  text.replace("  ", " "),
                })

        # ══════════════════════════════════════════════════════════════
        # STRUCTURE CHECK — text-based, cover-page-guarded
        # ══════════════════════════════════════════════════════════════
        # We do NOT rely on Word paragraph styles (all paragraphs are
        # style='Normal' in uploaded documents) and do NOT mutate
        # doc_blocks with semantic promotion (which was causing cover-page
        # paragraphs to be misidentified as headings).
        #
        # Algorithm:
        #   1. Read raw paragraphs from the docx file.
        #   2. Find the cover-page boundary: the index of the first paragraph
        #      whose stripped text EXACTLY matches any known anchor heading
        #      (case-insensitive, trailing colons/spaces stripped).
        #   3. Collect candidates = paragraphs AFTER the boundary that are
        #      short (< 80 chars) and non-empty.
        #   4. Run HeadingNormalizer on those candidates — same logic as
        #      heading-style-check endpoint.
        #   5. Build structure_result directly from the normalizer output.
        # ══════════════════════════════════════════════════════════════
        template_heading_matches = []
        structure_result = {}

        if doc["template_id"] and required_sections:
            try:
                from services.heading_normalizer import HeadingNormalizer
                import re as _re

                # ── Read raw paragraphs from docx ──────────────────────────
                _file_for_struct = doc["file_path"]
                _wc_path = os.path.join("uploads", "working", f"doc_{document_id}_working.docx")
                if os.path.exists(_wc_path):
                    _file_for_struct = _wc_path

                _raw_paras = []  # list of {idx, text}
                if file_ext == ".docx" and os.path.exists(_file_for_struct):
                    from docx import Document as _DocxDoc
                    _docx_obj = _DocxDoc(_file_for_struct)
                    for _pi, _p in enumerate(_docx_obj.paragraphs):
                        _t = _p.text.strip()
                        if _t:
                            _raw_paras.append({"idx": _pi, "text": _t})
                else:
                    # Fallback: use doc_blocks texts for non-docx
                    for _b in doc_blocks:
                        _t = (_b.get("text") or "").strip()
                        if _t:
                            _raw_paras.append({"idx": _b.get("index", 0), "text": _t})

                # ── Cover-page guard ────────────────────────────────────────
                # Anchor headings: the first one that appears EXACTLY in the
                # document (case-insensitive, strip trailing colons/spaces)
                # defines the end of the cover page. Everything before it is
                # cover-page noise and must NOT be fed to the normalizer.
                _ANCHOR_EXACT = {
                    "abstract", "introduction", "chapter 1", "1. introduction",
                    "1 introduction",
                }

                def _strip_heading(t: str) -> str:
                    return _re.sub(r"[\s:.\-]+$", "", t.strip().lower())

                _cover_end_idx = 0   # raw paragraph index; 0 = no cover page detected
                for _rp in _raw_paras:
                    if _strip_heading(_rp["text"]) in _ANCHOR_EXACT:
                        _cover_end_idx = _rp["idx"]
                        print(f"[StructureCheck] Cover-page boundary: para {_cover_end_idx} "
                              f"'{_rp['text'][:40]}'")
                        break

                # ── Collect candidates (post-cover, short lines) ────────────
                _candidates = []  # list of {idx, text}
                for _rp in _raw_paras:
                    if _rp["idx"] < _cover_end_idx:
                        continue  # skip cover page
                    if len(_rp["text"]) < 80:
                        _candidates.append(_rp)

                print(f"[StructureCheck] {len(_candidates)} candidates after cover-page guard "
                      f"(boundary=para {_cover_end_idx})")

                # ── Run HeadingNormalizer (same as heading-style-check) ─────
                _hn = HeadingNormalizer(fuzzy_threshold=80.0,
                                        semantic_threshold=0.35,
                                        use_semantic=True)
                _required_names = [s["name"] for s in
                                   sorted(required_sections, key=lambda s: s.get("order", 999))]
                _cand_texts = [c["text"] for c in _candidates]
                _hn_report = _hn.match_headings(_cand_texts, _required_names)

                # Build text → candidate mapping for para index lookup
                _text_to_cand = {}
                for _c in _candidates:
                    if _c["text"] not in _text_to_cand:
                        _text_to_cand[_c["text"]] = _c

                # Build match lookup: required_name → MatchResult
                _match_lookup = {m.required: m for m in _hn_report.matches}

                # ── Build section_results ───────────────────────────────────
                _section_results = []
                _issues = []
                _last_para_idx = -1
                _found_count = 0
                _missing_count = 0

                _sorted_template = sorted(required_sections, key=lambda s: s.get("order", 999))
                for _sec in _sorted_template:
                    _sec_name = _sec["name"]
                    _sec_order = _sec.get("order", 0)
                    _sec_req = _sec.get("required", True)
                    _m = _match_lookup.get(_sec_name)

                    if _m is None or _m.status == "missing":
                        _section_results.append({
                            "name": _sec_name,
                            "order": _sec_order,
                            "required": _sec_req,
                            "status": "missing",
                            "matched_heading": None,
                            "match_layer": None,
                            "document_position": None,
                            "paragraph_index": None,
                        })
                        if _sec_req:
                            _missing_count += 1
                            _issues.append({
                                "severity": "error",
                                "code": "MISSING_SECTION",
                                "message": f'Required section "{_sec_name}" is missing from the document.',
                                "details": {"section": _sec_name},
                            })
                        else:
                            _issues.append({
                                "severity": "info",
                                "code": "OPTIONAL_MISSING",
                                "message": f'Optional section "{_sec_name}" is not present.',
                                "details": {"section": _sec_name},
                            })
                        continue

                    _matched_text = _m.matched_heading
                    _cand_obj = _text_to_cand.get(_matched_text, {})
                    _para_idx = _cand_obj.get("idx", -1)

                    # Order check
                    _order_ok = _para_idx >= _last_para_idx
                    if not _order_ok:
                        _issues.append({
                            "severity": "error",
                            "code": "WRONG_ORDER",
                            "message": f'Section "{_sec_name}" appears out of order.',
                            "details": {"section": _sec_name,
                                        "found_at_para": _para_idx,
                                        "expected_after_para": _last_para_idx},
                        })

                    _status = "wrong_order" if not _order_ok else "found"
                    if _status == "found":
                        _found_count += 1

                    if _para_idx >= 0:
                        _last_para_idx = _para_idx

                    _section_results.append({
                        "name": _sec_name,
                        "order": _sec_order,
                        "required": _sec_req,
                        "status": _status,
                        "matched_heading": _matched_text,
                        "match_layer": _m.match_layer,
                        "document_position": _para_idx,  # raw para index
                        "paragraph_index": _para_idx,
                    })

                    print(f"[StructureCheck] {_sec_name} → {_status} "
                          f"('{_matched_text}' @{_para_idx} via {_m.match_layer})")

                # ── Score ───────────────────────────────────────────────────
                _total_req = sum(1 for s in _sorted_template if s.get("required", True))
                _score = max(0, int((_found_count / _total_req) * 100)) if _total_req else 100

                structure_result = {
                    "status": "pass" if _missing_count == 0 else "fail",
                    "score": _score,
                    "issues": _issues,
                    "section_results": _section_results,
                    "summary": {
                        "total_required": _total_req,
                        "found": _found_count,
                        "missing": _missing_count,
                        "wrong_order": sum(1 for r in _section_results if r["status"] == "wrong_order"),
                        "empty": 0,
                        "optional_missing": sum(1 for r in _section_results
                                                if r["status"] == "missing" and not r["required"]),
                        "extra_headings": len(_hn_report.extra_headings),
                        "content_before_heading": False,
                    },
                }
                print(f"[StructureCheck] score={_score} found={_found_count}/{_total_req}")

                # ── Populate template_heading_matches for disk write ────────
                for _sr in _section_results:
                    if _sr["status"] in ("found", "wrong_order") and _sr["paragraph_index"] is not None and _sr["paragraph_index"] >= 0:
                        template_heading_matches.append({
                            "para_index":    _sr["paragraph_index"],
                            "heading_level": 1,
                            "heading":       _sr["name"],
                            "matched_text":  _sr["matched_heading"],
                        })

                # ── Write heading styles to disk (working copy) ─────────────
                if template_heading_matches and file_ext == ".docx":
                    if not os.path.exists(_wc_path):
                        os.makedirs(os.path.dirname(_wc_path), exist_ok=True)
                        import shutil as _shutil
                        _shutil.copy2(doc["file_path"], _wc_path)
                    try:
                        apply_template_headings(
                            docx_path=_wc_path,
                            detected_headings=template_heading_matches,
                            output_path=_wc_path,
                        )
                        print(f"[HeadingApply] Styled {len(template_heading_matches)} headings in working copy")
                    except Exception as _ae:
                        print(f"[HeadingApply] ERROR: {_ae}")

            except Exception as _the:
                import traceback as _tb
                print(f"[StructureCheck] ERROR: {_the}\n{_tb.format_exc()}")

        elif required_sections and _CHECKERS_AVAILABLE:
            # Fallback for non-docx files: use the block-based checker
            try:
                structure_result = check_structure(doc_blocks, required_sections)
            except Exception as e:
                print(f"[StructureCheck] fallback ERROR: {e}")




        # ══════════════════════════════════════════════════════════════
        # LAYER 3 — CONTENT MISMATCH CHECK (UPDATED)
        # ══════════════════════════════════════════════════════════════
        content_issues       = []
        content_checker_mode = "zero_shot"
        content_checker_version = "original"  # NEW: Track which checker was used
        
        # Determine which content checker to use
        if use_perfect_checker and _perfect_content_checker is not None:
            # Use the new Perfect Content Checker
            content_checker_version = "perfect"
            content_checker_mode = "ensemble_with_learning"
            
            
            try:
                # Build sections for checking
                if hasattr(PerfectContentChecker, 'sections_from_blocks'):
                    sections = PerfectContentChecker.sections_from_blocks(doc_blocks)
                else:
                    # Manual section building if methods not available
                    sections = []
                    current_heading = None
                    current_content = []
                    
                    for block in doc_blocks:
                        if block['type'] == 'heading':
                            if current_heading and current_content:
                                sections.append({
                                    'heading': current_heading,
                                    'content': ' '.join(current_content)
                                })
                            current_heading = block['text']
                            current_content = []
                        else:
                            if current_heading:
                                current_content.append(block['text'])
                    
                    if current_heading and current_content:
                        sections.append({
                            'heading': current_heading,
                            'content': ' '.join(current_content)
                        })
                
                print(f"[PerfectContentCheck] sections built: {len(sections)}")
                
                # Check each section with context
                for section in sections:
                    # Add document context for better learning
                    if len(section.get('content', '')) < 50:
                        continue
                    
                    result = _perfect_content_checker.check_section(
                        heading=section['heading'],
                        content=section['content'],
                        context={'document_type': 'fyp_report'}
                    )
                    
                    if result:
                        content_issues.append(result)
                
                print(f"[PerfectContentCheck] issues found: {len(content_issues)}")
                
            except Exception as e:
                import traceback
                print(f"[PerfectContentCheck] ERROR: {traceback.format_exc()}")
                # Fall back to original checker if perfect checker fails
                use_perfect_checker = False
        
        # Fall back to original content checker if needed
        if not use_perfect_checker or content_checker_version == "original":
            if _CHECKERS_AVAILABLE and _content_checker is not None:
                content_checker_mode = "trained_model" if _content_checker._model_available else "zero_shot"
                try:
                    sections = ContentChecker.sections_from_blocks(doc_blocks)
                    print(f"[ContentCheck] sections built: {len(sections)}")
                    for s in sections[:6]:
                        print(f"  heading='{s['heading']}'  content_len={len(s.get('content', ''))}")
                    content_issues = _content_checker.check(sections)
                    print(f"[ContentCheck] issues found: {len(content_issues)}  mode={content_checker_mode}")
                except Exception as e:
                    import traceback
                    print(f"[ContentCheck] ERROR: {traceback.format_exc()}")
            else:
                print(f"[ContentCheck] SKIP — _CHECKERS_AVAILABLE={_CHECKERS_AVAILABLE}  _content_checker={_content_checker}")

        # ── Resolve effective path for style checks ──────────────────────────
        working_path = os.path.join("uploads", "working", f"doc_{document_id}_working.docx")
        style_check_path = working_path if os.path.exists(working_path) else doc["file_path"]

        style_issues = []
        if file_ext == ".docx" and _CHECKERS_AVAILABLE and _style_checker is not None:
            try:
                style_issues = _style_checker.check(
                    style_check_path,
                    template_rules=template_rules or None,
                )
                print(f"[StyleCheck] issues found: {len(style_issues)} in {os.path.basename(style_check_path)}")
            except Exception as e:
                print(f"[StyleCheck] ERROR: {e}")

        # ══════════════════════════════════════════════════════════════
        # BULLET CHECK — detect missing bullets in list-like sections
        # Results appended to style_issues so they appear in Style tab.
        # ══════════════════════════════════════════════════════════════
        if file_ext == ".docx":
            try:
                bullet_issues = _detect_missing_bullet_issues(style_check_path)
                style_issues.extend(bullet_issues)
                print(f"[BulletCheck] issues found: {len(bullet_issues)} in {os.path.basename(style_check_path)}")
            except Exception as e:
                print(f"[BulletCheck] ERROR: {e}")

        conn.close()

        critical_count   = len([i for i in issues if i.get("type") == "CRITICAL"])
        warning_count    = len([i for i in issues if i.get("type") == "WARNING"])
        compliance_score = max(0, 100 - (critical_count * 10 + warning_count * 5))

        return {
            "document_id":           document_id,
            "filename":              doc["filename"],
            "document_content":      document_lines,
            "issues":                issues,
            # ── Layer-3 results (consumed by analyze_screen.dart) ──────
            "content_issues":        content_issues,
            "style_issues":          style_issues,
            "structure":             structure_result,
            "content_checker_mode":  content_checker_mode,
            "content_checker_version": content_checker_version,
            # ── Template heading detection ──────────────────────────────
            "template_heading_matches": template_heading_matches,
            # ── Legacy counts ───────────────────────────────────────────
            "compliance_score":      compliance_score,
            "total_issues":          len(issues) + len(content_issues) + len(style_issues),
            "critical_issues":       critical_count,
            "warning_issues":        warning_count,
        }

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------
# Apply Conformity
# -------------------------------

# ══════════════════════════════════════════════════════════════════════════════
# NEW DEBUG ENDPOINT — test perfect content checker in isolation
# GET /api/documents/debug/perfect-content-check/{document_id}
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/debug/perfect-content-check/{document_id}")
async def debug_perfect_content_check(document_id: int):
    """
    Runs ONLY the perfect content checker on a document and returns full debug info.
    Use this to test perfect_content_checker.py without the full analysis pipeline.
    """
    db = get_db()
    doc = db.execute(
        "SELECT * FROM documents WHERE id = ?", (document_id,)
    ).fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = dict(doc)
    file_ext = os.path.splitext(doc["file_path"])[1].lower()

    # ── Build blocks ──────────────────────────────────────────────────────────
    doc_blocks = []
    try:
        if file_ext == ".docx":
            from docx import Document as _D
            d = _D(doc["file_path"])
            for para in d.paragraphs:
                text = para.text.strip()
                if not text:
                    continue
                style_name = (para.style.name or "").lower()
                is_bold    = any(r.bold for r in para.runs if r.bold is not None)
                font_size  = next((r.font.size.pt for r in para.runs if r.font.size), None)
                word_count = len(text.split())
                block_type = "paragraph"
                level      = None
                for lvl in (1,2,3,4,5,6):
                    if f"heading {lvl}" in style_name or f"heading{lvl}" in style_name:
                        block_type, level = "heading", lvl
                        break
                else:
                    if font_size and font_size >= 14 and is_bold and word_count <= 10:
                        block_type = "heading"
                        level      = 1 if font_size >= 18 else 2
                    elif text.isupper() and 1 <= word_count <= 8:
                        block_type, level = "heading", 2
                    elif is_bold and word_count <= 8 and not text.endswith("."):
                        block_type, level = "heading", 3
                doc_blocks.append({"type": block_type, "text": text, "level": level})
    except Exception as e:
        return {"error": f"Block extraction failed: {e}"}

    # ── Build sections ────────────────────────────────────────────────────────
    if _perfect_content_checker is None:
        return {
            "error": "PerfectContentChecker not available",
            "perfect_checker_loaded": _perfect_content_checker is not None,
        }

    # Build sections manually
    sections = []
    current_heading = None
    current_content = []
    
    for block in doc_blocks:
        if block['type'] == 'heading':
            if current_heading and current_content:
                sections.append({
                    'heading': current_heading,
                    'content': ' '.join(current_content)
                })
            current_heading = block['text']
            current_content = []
        else:
            if current_heading:
                current_content.append(block['text'])
    
    if current_heading and current_content:
        sections.append({
            'heading': current_heading,
            'content': ' '.join(current_content)
        })

    sections_summary = [
        {
            "heading":      s["heading"],
            "content_len":  len(s.get("content", "")),
            "content_preview": s.get("content", "")[:120],
        }
        for s in sections
    ]

    # ── Run perfect checker ───────────────────────────────────────────────────
    import traceback
    issues = []
    checker_error = None
    signatures_info = {}
    
    try:
        # Show current signatures
        signatures_info = {
            heading: {
                'keywords': list(sig.keywords)[:10],
                'tense_pattern': sig.tense_pattern,
                'citation_density': sig.citation_density,
                'code_density': sig.code_density
            }
            for heading, sig in _perfect_content_checker.signatures.items()
        }
        
        # Check each section
        for section in sections:
            result = _perfect_content_checker.check_section(
                heading=section['heading'],
                content=section['content'],
                context={'document_type': 'debug'}
            )
            if result:
                issues.append(result)
                
    except Exception as e:
        checker_error = traceback.format_exc()

    return {
        "document_id":        document_id,
        "file":               os.path.basename(doc["file_path"]),
        "perfect_checker_loaded": _perfect_content_checker is not None,
        "signatures_learned": signatures_info,
        "total_signatures":   len(_perfect_content_checker.signatures),
        "total_blocks":       len(doc_blocks),
        "total_sections":     len(sections),
        "sections_summary":   sections_summary,
        "issues_found":       len(issues),
        "issues":             issues,
        "checker_error":      checker_error,
    }

# ══════════════════════════════════════════════════════════════════════════════
# EXISTING DEBUG ENDPOINT — test old content checker in isolation
# GET /api/documents/debug/content-check/{document_id}
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/debug/content-check/{document_id}")
async def debug_content_check(document_id: int):
    """
    Runs ONLY the content checker on a document and returns full debug info.
    Use this to test content_checker.py without the full analysis pipeline.
    """
    db = get_db()
    doc = db.execute(
        "SELECT * FROM documents WHERE id = ?", (document_id,)
    ).fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = dict(doc)
    file_ext = os.path.splitext(doc["file_path"])[1].lower()

    # ── Build blocks ──────────────────────────────────────────────────────────
    doc_blocks = []
    try:
        if file_ext == ".docx":
            from docx import Document as _D
            d = _D(doc["file_path"])
            for para in d.paragraphs:
                text = para.text.strip()
                if not text:
                    continue
                style_name = (para.style.name or "").lower()
                is_bold    = any(r.bold for r in para.runs if r.bold is not None)
                font_size  = next((r.font.size.pt for r in para.runs if r.font.size), None)
                word_count = len(text.split())
                block_type = "paragraph"
                level      = None
                for lvl in (1,2,3,4,5,6):
                    if f"heading {lvl}" in style_name or f"heading{lvl}" in style_name:
                        block_type, level = "heading", lvl
                        break
                else:
                    if font_size and font_size >= 14 and is_bold and word_count <= 10:
                        block_type = "heading"
                        level      = 1 if font_size >= 18 else 2
                    elif text.isupper() and 1 <= word_count <= 8:
                        block_type, level = "heading", 2
                    elif is_bold and word_count <= 8 and not text.endswith("."):
                        block_type, level = "heading", 3
                doc_blocks.append({"type": block_type, "text": text, "level": level})
    except Exception as e:
        return {"error": f"Block extraction failed: {e}"}

    # ── Build sections ────────────────────────────────────────────────────────
    if not _CHECKERS_AVAILABLE or _content_checker is None:
        return {
            "error": "ContentChecker not available",
            "checkers_available": _CHECKERS_AVAILABLE,
        }

    sections = ContentChecker.sections_from_blocks(doc_blocks)

    sections_summary = [
        {
            "heading":      s["heading"],
            "content_len":  len(s.get("content", "")),
            "content_preview": s.get("content", "")[:120],
        }
        for s in sections
    ]

    # ── Run checker ───────────────────────────────────────────────────────────
    import traceback
    issues = []
    checker_error = None
    try:
        issues = _content_checker.check(sections)
    except Exception as e:
        checker_error = traceback.format_exc()

    return {
        "document_id":        document_id,
        "file":               os.path.basename(doc["file_path"]),
        "checkers_available": _CHECKERS_AVAILABLE,
        "model_available":    getattr(_content_checker, "_model_available", False),
        "embedder_loaded":    _content_checker._embedder is not None,
        "total_blocks":       len(doc_blocks),
        "total_sections":     len(sections),
        "sections_summary":   sections_summary,
        "issues_found":       len(issues),
        "issues":             issues,
        "checker_error":      checker_error,
    }

# NEW: Endpoint to reset/retrain the perfect checker
@router.post("/perfect-checker/reset")
async def reset_perfect_checker(admin_key: str = Query(...)):
    """
    Reset and retrain the perfect content checker.
    Requires admin key for security.
    """
    if admin_key != "your-secure-admin-key":  # Change this to a secure key
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    global _perfect_content_checker
    
    try:
        # Reinitialize the perfect checker
        _perfect_content_checker = create_perfect_checker() if PerfectContentChecker is not None else None
        
        if _perfect_content_checker:
            return {
                "status": "success",
                "message": "Perfect content checker reset successfully",
                "signatures": len(_perfect_content_checker.signatures)
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to reset perfect checker")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/apply-conformity/{document_id}")
def apply_conformity(document_id: int, user_id: int = Query(...)):
    try:
        conn = get_db()
        doc = conn.execute(
            "SELECT filename, file_path, user_id, template_id FROM documents WHERE id = ?",
            (document_id,)
        ).fetchone()

        if not doc:
            conn.close()
            raise HTTPException(status_code=404, detail="Document not found")
        if doc["user_id"] != user_id:
            conn.close()
            raise HTTPException(status_code=403, detail="Unauthorized")

        file_path = doc["file_path"]
        template_id = doc["template_id"]
        formatting_rules = {}

        if template_id:
            template = conn.execute(
                "SELECT formatting_rules FROM templates WHERE id = ?",
                (template_id,)
            ).fetchone()
            if template and template["formatting_rules"]:
                try:
                    formatting_rules = json.loads(template["formatting_rules"])
                except json.JSONDecodeError:
                    pass

        file_ext = os.path.splitext(file_path)[1].lower()

        if file_ext == ".docx":
            # Write to working copy so export/download pick it up
            working_path = os.path.join("uploads", "working", f"doc_{document_id}_working.docx")
            os.makedirs(os.path.dirname(working_path), exist_ok=True)
            shutil.copy2(file_path, working_path)

            docx = DocxDocument(working_path)
            for para in docx.paragraphs:
                if para.text.strip():
                    text = para.text
                    if text and text[0].islower() and not text.startswith("-"):
                        para.text = text[0].upper() + text[1:]
                    para.text = para.text.replace("  ", " ")
            docx.save(working_path)

        elif file_ext == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            formatted_content = re.sub(
                r'([.!?]\s+)([a-z])',
                lambda m: m.group(1) + m.group(2).upper(),
                content
            )
            formatted_content = formatted_content.replace("  ", " ")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(formatted_content)

        conn.close()
        return {
            "document_id": document_id,
            "status": "formatted",
            "message": "Document conformity and formatting applied successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Apply conformity error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to apply conformity: {str(e)}")

# ─────────────────────────────────────────────────────────────────────────────
# Style Fix Helper — applies font/bold/spacing corrections to a DOCX
# ─────────────────────────────────────────────────────────────────────────────

def _apply_style_fix_to_docx(
    docx_path: str,
    fix_type: str,
    details: dict,
    formatting_rules: dict,
) -> int:
    """
    Apply a single style fix to paragraphs in the DOCX.

    Supported fix_type values:
      fix_font_size     — correct font size to match template
      fix_bold          — correct bold setting to match template
      fix_font_name     — correct font family to match template
      fix_line_spacing  — correct line spacing to match template
      fix_alignment     — correct paragraph alignment to match template
      fix_all_style     — apply all fixes in one pass

    details keys (all optional):
      para_index        : int        — fix exactly this one paragraph index
      para_indices      : list[int]  — fix a specific list of paragraph indices
      block_type        : str        — "heading" | "paragraph" — fix all of this type
      heading_level     : int        — 1-4, narrows block_type=="heading" to a level
      expected_font_size    : float  — override template value
      expected_bold         : bool
      expected_font_name    : str
      expected_line_spacing : float

    Returns the number of paragraphs changed.
    """
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    docx_doc = DocxDocument(docx_path)
    paras    = docx_doc.paragraphs
    changed  = 0

    # ── Resolve target paragraph indices ─────────────────────────────────────
    if "para_index" in details:
        target_indices = {int(details["para_index"])}
    elif "para_indices" in details:
        target_indices = set(int(i) for i in details["para_indices"])
    else:
        target_indices = None          # None → apply to all matching block_type

    block_type    = details.get("block_type")    # "heading" | "paragraph" | None
    heading_level = details.get("heading_level") # int 1-4 or None

    def _matches(idx: int, para) -> bool:
        if target_indices is not None:
            return idx in target_indices
        if block_type == "heading":
            sn = (para.style.name or "").lower()
            if "heading" not in sn:
                return False
            if heading_level is not None:
                return f"heading {heading_level}" in sn
            return True
        if block_type == "paragraph":
            sn = (para.style.name or "").lower()
            return "heading" not in sn
        return True   # no filter — apply to everything

    # ── Resolve expected values ───────────────────────────────────────────────
    # Priority: details overrides > level-specific template rule > body rule > default
    level_prefix = None
    if block_type == "heading" and heading_level:
        level_prefix = {1: "heading1", 2: "heading2",
                        3: "heading3", 4: "heading4"}.get(int(heading_level))

    def _rule(suffix, default):
        # 1. Explicit override in details
        key = f"expected_{suffix}"
        if key in details and details[key] is not None:
            return details[key]
        # 2. Level-specific template rule
        if level_prefix:
            v = formatting_rules.get(f"{level_prefix}_{suffix}")
            if v is not None:
                return v
        # 3. Body/generic template rule
        if block_type == "paragraph":
            v = formatting_rules.get(f"body_{suffix}")
            if v is not None:
                return v
        return default

    target_font_size    = float(_rule("font_size",    12))
    target_bold         = bool (_rule("bold",         False))
    target_font_name    = str  (_rule("font_name",    "Times New Roman"))
    target_line_spacing = float(_rule("line_spacing", 1.0))
    target_alignment    = str  (_rule(
        "alignment",
        "justify" if (block_type == "paragraph" or block_type is None) else "left",
    )).lower().strip()

    def _to_wd_alignment(raw: str):
        m = {
            "left": WD_ALIGN_PARAGRAPH.LEFT,
            "center": WD_ALIGN_PARAGRAPH.CENTER,
            "right": WD_ALIGN_PARAGRAPH.RIGHT,
            "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
            "justified": WD_ALIGN_PARAGRAPH.JUSTIFY,
        }
        return m.get(raw, WD_ALIGN_PARAGRAPH.LEFT)

    # ── Walk paragraphs ───────────────────────────────────────────────────────
    for idx, para in enumerate(paras):
        if not para.text.strip():
            continue
        if not _matches(idx, para):
            continue

        para_changed = False

        # Font size, bold, font name — applied per run
        for run in para.runs:
            if fix_type in ("fix_font_size", "fix_all_style"):
                current = run.font.size.pt if run.font.size else None
                if current is None or abs(current - target_font_size) > 0.1:
                    run.font.size = Pt(target_font_size)
                    para_changed  = True

            if fix_type in ("fix_bold", "fix_all_style"):
                if run.bold != target_bold:
                    run.bold     = target_bold
                    para_changed = True

            if fix_type in ("fix_font_name", "fix_all_style"):
                if run.font.name != target_font_name:
                    run.font.name = target_font_name
                    para_changed  = True

        # Line spacing — applied at paragraph level
        if fix_type in ("fix_line_spacing", "fix_all_style"):
            pf = para.paragraph_format
            current_spacing = pf.line_spacing
            current_float   = None
            if current_spacing is not None:
                try:
                    cf = float(current_spacing)
                    # python-docx sometimes stores spacing as EMUs (large int)
                    current_float = cf / 914400 * 72 if cf > 10 else cf
                except (TypeError, ValueError):
                    current_float = None

            if current_float is None or abs(current_float - target_line_spacing) > 0.05:
                pf.line_spacing = target_line_spacing
                para_changed    = True

        # Alignment — paragraph level
        if fix_type in ("fix_alignment", "fix_all_style"):
            desired = _to_wd_alignment(target_alignment)
            if para.alignment != desired:
                para.alignment = desired
                para_changed = True

        if para_changed:
            changed += 1

    docx_doc.save(docx_path)
    print(f"[StyleFix] fix_type={fix_type}  changed={changed} paragraphs")
    return changed


# ─────────────────────────────────────────────────────────────────────────────
# Apply Fix endpoint — called by the Style tab "Apply Fix" buttons
# POST /api/documents/apply-fix/{document_id}?user_id=&fix_type=
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/apply-fix/{document_id}")
def apply_fix(
    document_id: int,
    user_id: int = Query(...),
    fix_type: str = Query(...),
    details: dict = Body(default={}),
):
    """
    Apply a specific fix to a document in-place.

    Supported fix_type values:
      apply_section_bullets — apply OOXML bullet formatting to a specific
                              set of paragraph indices (details.para_indices)
    """
    try:
        print(f"[apply-fix] fix_type={fix_type} details={details}")
        conn = get_db()
        doc  = conn.execute(
            "SELECT filename, file_path, user_id, template_id FROM documents WHERE id = ?",
            (document_id,)
        ).fetchone()

        if not doc:
            conn.close()
            raise HTTPException(status_code=404, detail="Document not found")
        if doc["user_id"] != user_id:
            conn.close()
            raise HTTPException(status_code=403, detail="Unauthorized")

        file_path = doc["file_path"]
        template_id = doc["template_id"]

        # Load template formatting rules for bullet style
        formatting_rules = {}
        if template_id:
            template = conn.execute(
                "SELECT formatting_rules FROM templates WHERE id = ?",
                (template_id,)
            ).fetchone()
            if template and template["formatting_rules"]:
                try:
                    formatting_rules = json.loads(template["formatting_rules"])
                except (json.JSONDecodeError, TypeError):
                    pass

        conn.close()

        if fix_type == "add_heading":
            if not file_path.endswith(".docx"):
                raise HTTPException(status_code=400, detail="Only .docx files supported")

            section = (details.get("section") or "").strip()
            if not section:
                raise HTTPException(status_code=400, detail="details.section is required")

            working_path = _working_copy_path(document_id)
            if not os.path.exists(working_path):
                shutil.copy2(file_path, working_path)
                print(f"[apply-fix] Created working copy: {working_path}")

            try:
                docx_doc = DocxDocument(working_path)
                docx_doc.add_paragraph("")  # ensure spacing before new heading
                docx_doc.add_heading(section, level=1)
                docx_doc.add_paragraph("")
                docx_doc.save(working_path)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to add heading: {e}")

            return {
                "document_id": document_id,
                "status": "fixed",
                "fix_type": fix_type,
                "message": f'Heading "{section}" added (Heading 1).',
                "working_copy": working_path,
            }

        if fix_type == "apply_section_bullets":
            if not file_path.endswith(".docx"):
                raise HTTPException(status_code=400, detail="Only .docx files supported")

            para_indices = details.get("para_indices", [])
            if not para_indices:
                raise HTTPException(status_code=400, detail="para_indices required")

            # ── Work on a per-document copy, never touch the original ─────
            working_path = _working_copy_path(document_id)
            if not os.path.exists(working_path):
                # First fix for this document → copy original as starting point
                shutil.copy2(file_path, working_path)
                print(f"[apply-fix] Created working copy: {working_path}")

            applied, skipped = _apply_bullets_to_paragraphs(
                working_path, para_indices, formatting_rules
            )

            return {
                "document_id": document_id,
                "status":      "fixed",
                "fix_type":    fix_type,
                "requested":   sorted([int(i) for i in para_indices if isinstance(i, int) or (isinstance(i, str) and str(i).isdigit())]),
                "applied":     applied,
                "skipped":     skipped,
                "message":     f"Bullets applied to {len(applied)} paragraph(s).",
                "working_copy": working_path,
            }

        elif fix_type in ("fix_font_size", "fix_bold", "fix_font_name",
                          "fix_line_spacing", "fix_alignment", "fix_all_style"):
            # ── Style fix — font size / bold / font name / line spacing ───────
            if not file_path.endswith(".docx"):
                raise HTTPException(status_code=400, detail="Only .docx files supported")

            working_path = _working_copy_path(document_id)
            if not os.path.exists(working_path):
                shutil.copy2(file_path, working_path)
                print(f"[apply-fix] Created working copy: {working_path}")

            changed = _apply_style_fix_to_docx(
                working_path, fix_type, details, formatting_rules
            )

            return {
                "document_id":        document_id,
                "status":             "fixed",
                "fix_type":           fix_type,
                "paragraphs_changed": changed,
                "message":            f"Style fix '{fix_type}' applied to {changed} paragraph(s).",
                "working_copy":       working_path,
            }

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown fix_type '{fix_type}'"
            )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[apply-fix] ERROR: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Apply ALL style fixes in one call (single save)
# POST /api/documents/apply-all-style-fixes/{document_id}?user_id=
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/apply-all-style-fixes/{document_id}")
def apply_all_style_fixes(
    document_id: int,
    user_id: int = Query(...),
):
    try:
        conn = get_db()
        doc  = conn.execute(
            "SELECT filename, file_path, user_id, template_id FROM documents WHERE id = ?",
            (document_id,)
        ).fetchone()

        if not doc:
            conn.close()
            raise HTTPException(status_code=404, detail="Document not found")
        if doc["user_id"] != user_id:
            conn.close()
            raise HTTPException(status_code=403, detail="Unauthorized")

        file_path = doc["file_path"]
        template_id = doc["template_id"]

        formatting_rules = {}
        if template_id:
            template = conn.execute(
                "SELECT formatting_rules FROM templates WHERE id = ?",
                (template_id,)
            ).fetchone()
            if template and template["formatting_rules"]:
                try:
                    formatting_rules = json.loads(template["formatting_rules"])
                except (json.JSONDecodeError, TypeError):
                    pass

        conn.close()

        if not file_path.endswith(".docx"):
            raise HTTPException(status_code=400, detail="Only .docx files supported")

        working_path = _working_copy_path(document_id)
        if not os.path.exists(working_path):
            shutil.copy2(file_path, working_path)
            print(f"[apply-all-style-fixes] Created working copy: {working_path}")

        # Apply complete template style profile (margins, headings, body, lists, spacing)
        styled_path = working_path.replace(".docx", "_styled.docx")
        _apply_template_styles_to_docx(
            working_path,
            styled_path,
            formatting_rules,
        )
        os.replace(styled_path, working_path)

        changed = len([p for p in DocxDocument(working_path).paragraphs if p.text.strip()])
        print(f"[StyleFix] Applied full template styles to working copy ({changed} non-empty paragraphs)")

        return {
            "document_id": document_id,
            "status": "fixed",
            "fix_type": "fix_all_style",
            "paragraphs_changed": changed,
            "message": "Applied all template style settings (including margins and spacing).",
            "working_copy": working_path,
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[apply-all-style-fixes] ERROR: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


def _apply_bullets_to_paragraphs(
    docx_path: str,
    para_indices: list,
    formatting_rules: dict,
) -> tuple[list, list]:
    """
    Apply real Word OOXML bullet formatting to specific paragraph indices
    in-place (overwrites the original file).
    Uses the same BulletFormatterService logic but only targets the given
    paragraphs, leaving all others untouched.
    """
    import random as _random
    import re as _re

    # Determine bullet style from template rules
    _STYLE_DEFS = {
        "filled_circle": ("\u2022", "Symbol",      "bullet"),
        "empty_circle":  ("\u006F", "Courier New", "bullet"),
        "square":        ("\u25A0", "Wingdings",   "bullet"),
        "dash":          ("\u2013", "Calibri",     "bullet"),
        "arrow":         ("\u27A2", "Wingdings",   "bullet"),
        "decimal":       ("%1.",     None,           "decimal"),
        "lower_letter":  ("%1.",     None,           "lowerLetter"),
        "upper_letter":  ("%1.",     None,           "upperLetter"),
        "lower_roman":   ("%1.",     None,           "lowerRoman"),
    }

    style_key = "filled_circle"
    if "list_bullet_style" in formatting_rules:
        raw = formatting_rules["list_bullet_style"].lower().replace(" ", "_")
        if raw in _STYLE_DEFS:
            style_key = raw
    if "list_numbering_format" in formatting_rules:
        fmt = formatting_rules["list_numbering_format"]
        if fmt in _STYLE_DEFS:
            style_key = fmt

    lvl_text, font_name, num_fmt = _STYLE_DEFS[style_key]

    # Normalize target indices to keep deterministic behavior.
    para_indices = sorted({
        int(i) for i in para_indices
        if isinstance(i, int) or (isinstance(i, str) and i.strip().isdigit())
    })

    docx  = DocxDocument(docx_path)

    # ── Expand soft-break blobs into real paragraphs first ───────────────────
    _W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    from copy import deepcopy as _dc
    from docx.oxml import OxmlElement as _OE2
    body = docx.element.body
    for p_el in list(body.iter(f"{{{_W}}}p")):
        if not p_el.findall(f".//{{{_W}}}br"):
            continue
        pPr_el = p_el.find(f"{{{_W}}}pPr")
        lines  = [[]]
        for r_el in p_el.findall(f"{{{_W}}}r"):
            rPr_el = r_el.find(f"{{{_W}}}rPr")
            for child in list(r_el):
                if child.tag == f"{{{_W}}}t":
                    lines[-1].append((rPr_el, child.text or ""))
                elif child.tag == f"{{{_W}}}br":
                    lines.append([])
        while lines and not any(t.strip() for _, t in lines[-1]):
            lines.pop()
        if len(lines) <= 1:
            continue
        parent = p_el.getparent()
        pos    = list(parent).index(p_el)
        new_ps = []
        for frags in lines:
            lt = "".join(t for _, t in frags).strip()
            if not lt:
                continue
            np_ = _OE2("w:p")
            if pPr_el is not None:
                np_.append(_dc(pPr_el))
            nr_ = _OE2("w:r")
            rp_ = next((rp for rp, _ in frags if rp is not None), None)
            if rp_ is not None:
                nr_.append(_dc(rp_))
            nt_ = _OE2("w:t")
            nt_.text = lt
            nt_.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            nr_.append(nt_); np_.append(nr_)
            new_ps.append(np_)
        for off, np_ in enumerate(new_ps):
            parent.insert(pos + off, np_)
        parent.remove(p_el)

    paras = docx.paragraphs   # re-read after expansion

    # ── Get or create the numbering part ─────────────────────────────────────
    # python-docx raises NotImplementedError on NumberingPart.new() when the
    # document has never had any lists. Build and attach the XML manually.
    from docx.oxml import OxmlElement as _OE
    try:
        num_part      = docx.part.numbering_part.numbering_definitions._numbering
        abstract_id   = len(num_part.findall(qn('w:abstractNum')))
        num_id        = len(num_part.findall(qn('w:num'))) + 1
    except Exception:
        from lxml import etree as _etree
        from docx.opc.part import Part as _OpcPart
        from docx.opc.packuri import PackURI as _PackURI

        _NUM_CT  = ('application/vnd.openxmlformats-officedocument'
                    '.wordprocessingml.numbering+xml')
        _NUM_RT  = ('http://schemas.openxmlformats.org/officeDocument'
                    '/2006/relationships/numbering')
        _num_xml = (
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            b'<w:numbering xmlns:w="http://schemas.openxmlformats.org/'
            b'wordprocessingml/2006/main"/>'
        )
        num_opc = _OpcPart(
            _PackURI('/word/numbering.xml'),
            _NUM_CT,
            _num_xml,
            docx.part.package,
        )
        docx.part.relate_to(num_opc, _NUM_RT)
        num_part    = _etree.fromstring(_num_xml)
        abstract_id = 0
        num_id      = 1

    # ── Build abstractNum + num ───────────────────────────────────────────────
    nsid_val = ''.join(_random.choices('0123456789ABCDEF', k=8))
    tmpl_val = ''.join(_random.choices('0123456789ABCDEF', k=8))

    abstractNum = _OE('w:abstractNum')
    abstractNum.set(qn('w:abstractNumId'), str(abstract_id))
    nsid = _OE('w:nsid'); nsid.set(qn('w:val'), nsid_val)
    ml   = _OE('w:multiLevelType'); ml.set(qn('w:val'), 'singleLevel')
    tmpl = _OE('w:tmpl'); tmpl.set(qn('w:val'), tmpl_val)
    abstractNum.extend([nsid, ml, tmpl])

    lvl    = _OE('w:lvl');     lvl.set(qn('w:ilvl'), '0')
    start  = _OE('w:start');   start.set(qn('w:val'), '1')
    nFmt   = _OE('w:numFmt');  nFmt.set(qn('w:val'), num_fmt)
    lvlTxt = _OE('w:lvlText'); lvlTxt.set(qn('w:val'), lvl_text)
    lvlJc  = _OE('w:lvlJc');   lvlJc.set(qn('w:val'), 'left')
    pPr_abs = _OE('w:pPr')
    # Tighter list indent to avoid huge gap after bullet
    tabs    = _OE('w:tabs'); tab = _OE('w:tab')
    tab.set(qn('w:val'), 'num'); tab.set(qn('w:pos'), '360')
    tabs.append(tab); pPr_abs.append(tabs)
    ind = _OE('w:ind'); ind.set(qn('w:left'), '360'); ind.set(qn('w:hanging'), '180')
    pPr_abs.append(ind)
    lvl.extend([start, nFmt, lvlTxt, lvlJc, pPr_abs])
    if font_name:
        rPr = _OE('w:rPr'); rFonts = _OE('w:rFonts')
        rFonts.set(qn('w:ascii'), font_name); rFonts.set(qn('w:hAnsi'), font_name)
        rFonts.set(qn('w:hint'), 'default'); rPr.append(rFonts); lvl.append(rPr)
    abstractNum.append(lvl)

    first_num_e = num_part.find(qn('w:num'))
    if first_num_e is not None:
        first_num_e.addprevious(abstractNum)
    else:
        num_part.append(abstractNum)

    num_elem = _OE('w:num'); num_elem.set(qn('w:numId'), str(num_id))
    an = _OE('w:abstractNumId'); an.set(qn('w:val'), str(abstract_id))
    num_elem.append(an); num_part.append(num_elem)

    # ── Apply numPr to each targeted paragraph ────────────────────────────────
    _LEADING_MARKER = _re.compile(
        r'^\s*(?:[•○■▪\-*→»–]+|\(?\d+[.)]|\(?[A-Za-z][.)]|\(?[ivxlcdmIVXLCDM]+[.)])\s+'
    )

    _NUM_HEADING = _re.compile(r'^\d+(\.\d+)*[.)]?\s+[A-Z]')
    _SMALL_WORDS = {'a','an','the','in','of','for','and','or','but','to','with','by'}

    def _looks_like_heading(para) -> bool:
        try:
            style_name = (para.style.name or "").lower() if para.style else ""
        except Exception:
            style_name = ""
        text = (para.text or "").strip()
        if not text:
            return False
        if "heading" in style_name:
            return True
        if _NUM_HEADING.match(text):
            return True
        wc = len(text.split())
        if text.isupper() and wc <= 8:
            return True
        if wc <= 6 and not text.endswith(('.', '?', '!', ':')):
            words = text.split()
            if all(w and (w[0].isupper() or w.lower() in _SMALL_WORDS) for w in words):
                return True
        return False

    applied: list[int] = []
    skipped: list[dict] = []

    for idx in para_indices:
        if idx < 0 or idx >= len(paras):
            skipped.append({"index": idx, "reason": "out_of_range"})
            continue
        p   = paras[idx]
        if not (p.text or "").strip():
            skipped.append({"index": idx, "reason": "empty"})
            continue
        if _looks_like_heading(p):
            # Never bullet headings (prevents the "• 7 Outcomes" issue).
            skipped.append({"index": idx, "reason": "heading_like"})
            continue
        # Avoid double bullets like "• • item" after OOXML numbering is applied.
        if p.runs:
            first_run = p.runs[0]
            first_run.text = _LEADING_MARKER.sub("", first_run.text or "", count=1)
        else:
            p.text = _LEADING_MARKER.sub("", p.text or "", count=1)

        # If the paragraph was only a marker/whitespace, stripping will empty it.
        # Never leave an empty paragraph with numPr (it renders as a stray bullet).
        if not (p.text or "").strip():
            pPr = p._element.get_or_add_pPr()
            ex = pPr.find(qn('w:numPr'))
            if ex is not None:
                pPr.remove(ex)
            skipped.append({"index": idx, "reason": "marker_only"})
            continue
        pPr = p._element.get_or_add_pPr()
        for tag in (qn('w:numPr'), qn('w:ind')):
            ex = pPr.find(tag)
            if ex is not None:
                pPr.remove(ex)
        numPr   = _OE('w:numPr')
        ilvl    = _OE('w:ilvl');  ilvl.set(qn('w:val'), '0')
        numId_e = _OE('w:numId'); numId_e.set(qn('w:val'), str(num_id))
        numPr.extend([ilvl, numId_e]); pPr.insert(0, numPr)
        pStyle = pPr.find(qn('w:pStyle'))
        if pStyle is None:
            pStyle = _OE('w:pStyle'); pPr.insert(0, pStyle)
        pStyle.set(qn('w:val'), 'ListParagraph')
        applied.append(idx)

    docx.save(docx_path)
    return applied, skipped