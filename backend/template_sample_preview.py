"""
Sample-document generator for the template preview (optional "Word preview").

Endpoint: POST /admin/templates/preview-sample?user_id=1&fmt=pdf|docx
Body:     the same JSON the Flutter screen sends to /admin/templates
Returns:  a PDF (default) or .docx built from the template's formatting_rules.

Requires: python-docx, and LibreOffice (`soffice`) on the server for PDF output.
Assumes FastAPI - adapt the router part if you use something else.
"""
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Mm, Pt, RGBColor

ALIGN = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}
PAGE_MM = {"A4": (210, 297), "LETTER": (215.9, 279.4), "LEGAL": (215.9, 355.6), "A5": (148, 210)}

LOREM_A = (
    "This is a sample paragraph that shows how body text will look in the final "
    "document. It uses the configured font, size, line spacing, alignment and "
    "first-line indent."
)
LOREM_B = (
    "A second paragraph shows paragraph spacing. Cross references such as "
    "Table 1 and Figure 1 appear in running text like this."
)


# ── small helpers ────────────────────────────────────────────────────────────

def _num(v: Any, default: float) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _to_pt(value: float, unit: str) -> float:
    unit = (unit or "mm").lower()
    if unit == "mm":
        return value * 72 / 25.4
    if unit == "cm":
        return value * 72 / 2.54
    if unit in ("in", "inch", "inches"):
        return value * 72
    return value


def _rgb(hex_str: str, default: str = "000000") -> RGBColor:
    h = (hex_str or default).replace("#", "").strip()
    if len(h) != 6:
        h = default
    try:
        return RGBColor.from_string(h.upper())
    except ValueError:
        return RGBColor.from_string(default)


def _set_style_font(style, name: str, size: float, bold=None, italic=None, color="000000"):
    style.font.name = name
    style.font.size = Pt(size)
    if bold is not None:
        style.font.bold = bold
    if italic is not None:
        style.font.italic = italic
    style.font.color.rgb = _rgb(color)
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(attr), name)
    # Theme fonts would override the explicit name in Word - remove them.
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        rfonts.attrib.pop(qn(attr), None)


def _transform(text: str, mode: str) -> str:
    mode = (mode or "").lower()
    if mode == "uppercase":
        return text.upper()
    if mode == "lowercase":
        return text.lower()
    if mode in ("capitalize", "title case"):
        return text.title()
    return text


def _heading_prefix(style: str, level: int) -> str:
    table = {
        "decimal": ["1", "1.1", "1.1.1", "1.1.1.1"],
        "roman": ["I.", "A.", "1.", "a."],
        "alpha": ["A.", "1.", "a.", "i."],
    }
    return table.get(style, [""] * 4)[level - 1]


def _tblpr_insert(tbl_pr, element):
    """Insert before <w:tblLook> to keep the OOXML child order valid."""
    look = tbl_pr.find(qn("w:tblLook"))
    if look is not None:
        look.addprevious(element)
    else:
        tbl_pr.append(element)


def _shade(cell, fill_hex: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_hex.replace("#", "").upper())
    tc_pr.append(shd)


def _border_el(tag: str, val: str, sz: int, color: str):
    el = OxmlElement(f"w:{tag}")
    el.set(qn("w:val"), val)
    el.set(qn("w:sz"), str(sz))
    el.set(qn("w:space"), "0")
    el.set(qn("w:color"), color.replace("#", "").upper())
    return el


# ── table ────────────────────────────────────────────────────────────────────

def _add_table(doc, rules: Dict[str, Any], ts: Dict[str, Any]):
    headers = ["Variable", "Mean", "SD", "p-value"]
    rows = [["Age (years)", "24.3", "3.1", "0.021"],
            ["Test score", "78.5", "10.4", "0.003"],
            ["Study hours", "5.2", "1.8", "0.147"]]

    font = ts.get("font_name", "Times New Roman")
    size = _num(ts.get("font_size"), 12)
    border_style = ts.get("border_style", "academic_standard")
    use_borders = bool(ts.get("borders", True)) and border_style != "none"
    b_color = ts.get("border_color", "000000")
    b_sz = max(2, int(_num(ts.get("border_size"), 4)))

    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = (WD_TABLE_ALIGNMENT.LEFT
                       if ts.get("alignment_on_page") == "left"
                       else WD_TABLE_ALIGNMENT.CENTER)
    table.autofit = bool(ts.get("auto_fit", True))

    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is not None:
        tbl_w.set(qn("w:type"), "pct")
        tbl_w.set(qn("w:w"), str(int(_num(ts.get("max_width_percent"), 100) * 50)))

    if use_borders:
        borders = OxmlElement("w:tblBorders")
        if border_style == "single_line":
            for t in ("top", "left", "bottom", "right", "insideH", "insideV"):
                borders.append(_border_el(t, "single", b_sz, b_color))
        elif border_style == "double_line":
            for t in ("top", "left", "bottom", "right", "insideH", "insideV"):
                borders.append(_border_el(t, "double", b_sz, b_color))
        else:  # academic: rules at top, bottom (header rule added below)
            borders.append(_border_el("top", "single", b_sz, b_color))
            borders.append(_border_el("bottom", "single", b_sz, b_color))
        _tblpr_insert(tbl_pr, borders)

    mar = OxmlElement("w:tblCellMar")
    for side, key, default in (("top", "cell_padding_top", 60), ("left", "cell_padding_lft", 108),
                               ("bottom", "cell_padding_bot", 60), ("right", "cell_padding_rgt", 108)):
        m = OxmlElement(f"w:{side}")
        m.set(qn("w:w"), str(int(_num(ts.get(key), default))))
        m.set(qn("w:type"), "dxa")
        mar.append(m)
    _tblpr_insert(tbl_pr, mar)

    if ts.get("repeat_header", True):
        tr_pr = table.rows[0]._tr.get_or_add_trPr()
        h = OxmlElement("w:tblHeader")
        h.set(qn("w:val"), "true")
        tr_pr.append(h)

    for r_idx, row in enumerate(table.rows):
        for c_idx, cell in enumerate(row.cells):
            is_header = r_idx == 0
            text = headers[c_idx] if is_header else rows[r_idx - 1][c_idx]
            p = cell.paragraphs[0]
            run = p.add_run(text)
            run.font.name = font
            run.font.size = Pt(size)
            run.bold = bool(ts.get("header_bold")) if is_header else False
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            if is_header:
                align = ts.get("header_align", "center")
            else:
                align = ts.get("text_column_alignment" if c_idx == 0 else "numeric_column_alignment", "left")
            p.alignment = ALIGN.get(str(align).lower(), WD_ALIGN_PARAGRAPH.LEFT)

            if is_header and ts.get("header_row_shading"):
                _shade(cell, ts.get("header_bg", "FFFFFF"))
            elif (not is_header) and ts.get("banded_rows") and r_idx % 2 == 0:
                _shade(cell, ts.get("band_color", "F2F8FC"))
            if is_header and use_borders and border_style == "academic_standard":
                tc_pr = cell._tc.get_or_add_tcPr()
                tcb = OxmlElement("w:tcBorders")
                tcb.append(_border_el("bottom", "single", b_sz, b_color))
                tc_pr.append(tcb)
    return table


def _caption(doc, text: str, size: float, font: str):
    p = doc.add_paragraph(style="Caption")
    run = p.add_run(text)
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = False
    run.font.italic = False
    run.font.color.rgb = RGBColor(0, 0, 0)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return p


# ── document ─────────────────────────────────────────────────────────────────

def build_docx(payload: Dict[str, Any], out_path: str) -> None:
    rules: Dict[str, Any] = payload.get("formatting_rules") or {}
    sections: List[Any] = payload.get("required_sections") or []
    unit = rules.get("spacing_unit", "mm")
    font = rules.get("body_font") or rules.get("heading1_font") or "Times New Roman"
    body_size = _num(rules.get("body_size"), 12)
    body_ls = _num(rules.get("body_line_spacing"), 2.0)

    doc = Document()

    sec = doc.sections[0]
    w_mm, h_mm = PAGE_MM.get(str(rules.get("page_size", "A4")).upper(), PAGE_MM["A4"])
    sec.page_width, sec.page_height = Mm(w_mm), Mm(h_mm)
    sec.top_margin = Pt(_to_pt(_num(rules.get("margin_top"), 25), unit))
    sec.bottom_margin = Pt(_to_pt(_num(rules.get("margin_bottom"), 25), unit))
    sec.left_margin = Pt(_to_pt(_num(rules.get("margin_left"), 30), unit))
    sec.right_margin = Pt(_to_pt(_num(rules.get("margin_right"), 20), unit))

    normal = doc.styles["Normal"]
    _set_style_font(normal, font, body_size)
    pf = normal.paragraph_format
    pf.line_spacing = body_ls
    pf.space_before = Pt(_num(rules.get("body_space_before"), 0))
    pf.space_after = Pt(_num(rules.get("body_space_after"), 0))
    pf.first_line_indent = Inches(_num(rules.get("first_line_indent"), 0.5))
    pf.alignment = (WD_ALIGN_PARAGRAPH.JUSTIFY if rules.get("body_justified", True)
                    else WD_ALIGN_PARAGRAPH.LEFT)

    numbering = rules.get("heading_numbering_style", "none")
    for lvl in range(1, 5):
        st = doc.styles[f"Heading {lvl}"]
        _set_style_font(
            st, rules.get(f"heading{lvl}_font", font), _num(rules.get(f"heading{lvl}_size"), 14),
            bold=bool(rules.get(f"heading{lvl}_bold")), italic=bool(rules.get(f"heading{lvl}_italic")),
            color=str(rules.get(f"heading{lvl}_color", "#000000")),
        )
        hp = st.paragraph_format
        hp.space_before = Pt(_num(rules.get(f"heading{lvl}_space_before"), 12))
        hp.space_after = Pt(_num(rules.get(f"heading{lvl}_space_after"), 6))
        hp.line_spacing = _num(rules.get(f"heading{lvl}_line_spacing"), 1.5)
        hp.first_line_indent = Inches(0)
        hp.keep_with_next = True

    for name in ("List Bullet", "List Number"):
        _set_style_font(doc.styles[name], font, body_size)
        doc.styles[name].paragraph_format.first_line_indent = None
        doc.styles[name].paragraph_format.left_indent = Inches(_num(rules.get("bullet_indent"), 0.5))
    _set_style_font(doc.styles["Caption"], font, max(body_size - 1, 8))

    def heading(level: int, text: str, align: str = "left", transform: str = "none"):
        prefix = _heading_prefix(numbering, level)
        label = _transform(text, transform)
        p = doc.add_heading(f"{prefix}  {label}" if prefix else label, level=level)
        p.alignment = ALIGN.get(align.lower(), WD_ALIGN_PARAGRAPH.LEFT)

    # Required sections as a simple contents list
    names = [s.get("name") or s.get("title") or str(s) if isinstance(s, dict) else str(s)
             for s in sections]
    if names:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.first_line_indent = Inches(0)
        r = p.add_run("TABLE OF CONTENTS")
        r.bold = True
        for i, n in enumerate(names[:12], start=1):
            q = doc.add_paragraph(f"{n}\t{i}")
            q.paragraph_format.first_line_indent = Inches(0)
            q.alignment = WD_ALIGN_PARAGRAPH.LEFT

    heading(1, "Introduction")
    doc.add_paragraph(LOREM_A)
    doc.add_paragraph(LOREM_B)
    heading(2, "Background of the Study")
    doc.add_paragraph(LOREM_A)
    heading(3, "Research Objectives")
    for t in ("To examine the main factors.", "To compare the observed groups.",
              "To recommend practical actions."):
        doc.add_paragraph(t, style="List Bullet")
    heading(4, "Scope and Delimitations")
    for t in ("First numbered item.", "Second numbered item.", "Third numbered item."):
        doc.add_paragraph(t, style="List Number")
    heading(2, "Results")
    doc.add_paragraph("Table 1 summarises the sample, and Figure 1 shows the framework.")

    ts = rules.get("table_style") or {}
    t_pattern = rules.get("table_caption_format_pattern", "Table {n}: {description}")
    t_cap = t_pattern.replace("{n}", "1.1" if rules.get("table_numbering_scheme") == "chapter" else "1") \
                     .replace("{description}", "Descriptive statistics of the sample")
    cap_above = rules.get("table_caption_position", "above") == "above"
    if cap_above:
        _caption(doc, t_cap, max(body_size - 1, 8), font)
    _add_table(doc, rules, ts)
    if not cap_above:
        _caption(doc, t_cap, max(body_size - 1, 8), font)

    f_pattern = rules.get("caption_format_pattern", "Figure {n}: {caption}")
    f_cap = f_pattern.replace("{n}", "1.1" if rules.get("numbering_scheme") == "chapter" else "1") \
                     .replace("{caption}", "Conceptual framework of the study")
    fig_above = rules.get("caption_position", "below") == "above"
    if fig_above:
        _caption(doc, f_cap, max(body_size - 1, 8), font)
    fig = doc.add_paragraph("[ Sample figure ]")
    fig.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fig.paragraph_format.first_line_indent = Inches(0)
    if not fig_above:
        _caption(doc, f_cap, max(body_size - 1, 8), font)

    doc.save(out_path)


def docx_to_pdf(docx_path: str, out_dir: str, timeout: int = 60) -> str:
    """Convert with LibreOffice using a throw-away profile so parallel requests don't collide."""
    profile_dir = Path(tempfile.gettempdir()) / f"lo_{uuid.uuid4().hex}"
    try:
        subprocess.run(
            ["soffice", f"-env:UserInstallation=file://{profile_dir}", "--headless",
             "--convert-to", "pdf", "--outdir", out_dir, docx_path],
            check=True, timeout=timeout, capture_output=True,
        )
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)
    pdf = Path(out_dir) / (Path(docx_path).stem + ".pdf")
    if not pdf.exists():
        raise RuntimeError("PDF conversion produced no output")
    return str(pdf)


# ── FastAPI route (adapt auth to your project) ───────────────────────────────

try:
    from fastapi import APIRouter, HTTPException, Query
    from fastapi.responses import Response

    router = APIRouter()

    @router.post("/admin/templates/preview-sample")
    def preview_sample(payload: Dict[str, Any], user_id: int = Query(...),
                       fmt: str = Query("pdf", pattern="^(pdf|docx)$")):
        # TODO: verify user_id is an admin using your existing dependency.
        with tempfile.TemporaryDirectory() as tmp:
            docx_path = str(Path(tmp) / "sample.docx")
            try:
                build_docx(payload, docx_path)
                if fmt == "docx":
                    return Response(
                        Path(docx_path).read_bytes(),
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                pdf_path = docx_to_pdf(docx_path, tmp)
                return Response(Path(pdf_path).read_bytes(), media_type="application/pdf")
            except subprocess.TimeoutExpired:
                raise HTTPException(504, "Sample generation timed out")
            except Exception as exc:  # keep the message short for the admin UI
                raise HTTPException(500, f"Could not build sample: {exc}")
except ImportError:  # allows importing build_docx without FastAPI (tests/scripts)
    router = None