"""
frontmatter_generator.py — Render cover / project-info templates and prepend to a report.

Uses docxtpl (Jinja2-style DOCX) for rendering and docxcompose.Composer to merge
while preserving styles. Optional pages are skipped when already present.
"""

from __future__ import annotations

import io
import os
from typing import BinaryIO, List, Optional, Tuple, Union

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Mm
from docxtpl import DocxTemplate, InlineImage

from models import FrontmatterContext

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
COVER_TEMPLATE = os.path.join(TEMPLATES_DIR, "cover_page_template.docx")
INFO_TEMPLATE = os.path.join(TEMPLATES_DIR, "project_info_template.docx")

# Known domain options shown on the info page (checked vs blank)
DEFAULT_DOMAIN_OPTIONS = ["AI", "NLP", "Mobile", "Web", "IoT", "SE", "Other"]


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _add_page_break(doc: Document) -> None:
    """
    Append a hard page break WITHOUT creating a blank interstitial page.

    Adding a *new* empty paragraph with a page break after a full page of
    content often lands that paragraph on the next page, and the break then
    advances one more page — leaving a blank sheet. Attach the break to the
    last real content paragraph instead.
    """
    _strip_trailing_empty_paragraphs(doc)

    for para in reversed(list(doc.paragraphs)):
        el = para._element
        has_text = bool((para.text or "").strip())
        has_media = bool(
            list(el.iter(qn("w:drawing")))
            or list(el.iter(qn("w:pict")))
            or list(el.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}blip"))
        )
        if not has_text and not has_media:
            continue
        run = para.add_run()
        run.add_break(WD_BREAK.PAGE)
        return

    # Truly empty document — fall back to a dedicated break paragraph
    para = doc.add_paragraph()
    run = para.add_run()
    run.add_break(WD_BREAK.PAGE)


def _strip_trailing_empty_paragraphs(doc: Document) -> int:
    """Remove trailing empty body paragraphs (keep final sectPr intact)."""
    body = doc.element.body
    removed = 0
    children = list(body)
    i = len(children) - 1
    while i >= 0:
        child = children[i]
        if child.tag == qn("w:sectPr"):
            i -= 1
            continue
        if child.tag != qn("w:p"):
            break
        text = "".join((t.text or "") for t in child.iter(qn("w:t"))).strip()
        has_media = bool(
            list(child.iter(qn("w:drawing")))
            or list(child.iter(qn("w:pict")))
            or list(child.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}blip"))
        )
        has_break = any(
            br.get(qn("w:type")) == "page" for br in child.iter(qn("w:br"))
        )
        # Keep a trailing page-break paragraph for callers that already added one;
        # only strip pure empties.
        if text or has_media or has_break:
            break
        body.remove(child)
        removed += 1
        i -= 1
    return removed


def _strip_trailing_page_breaks(doc: Document) -> int:
    """Remove trailing page-break-only paragraphs so we can add exactly one."""
    body = doc.element.body
    removed = 0
    children = list(body)
    i = len(children) - 1
    while i >= 0:
        child = children[i]
        if child.tag == qn("w:sectPr"):
            i -= 1
            continue
        if child.tag != qn("w:p"):
            break
        text = "".join((t.text or "") for t in child.iter(qn("w:t"))).strip()
        has_media = bool(
            list(child.iter(qn("w:drawing")))
            or list(child.iter(qn("w:pict")))
        )
        has_break = any(
            br.get(qn("w:type")) == "page" for br in child.iter(qn("w:br"))
        )
        if has_break and not text and not has_media:
            body.remove(child)
            removed += 1
            i -= 1
            continue
        if not text and not has_media and not has_break:
            body.remove(child)
            removed += 1
            i -= 1
            continue
        break
    return removed


def _set_section_page_start(section, start: int = 1) -> None:
    """Best-effort: restart page numbering for a section."""
    try:
        sectPr = section._sectPr
        pgNumType = sectPr.find(qn("w:pgNumType"))
        if pgNumType is None:
            pgNumType = OxmlElement("w:pgNumType")
            sectPr.append(pgNumType)
        pgNumType.set(qn("w:start"), str(start))
    except Exception as exc:
        print(f"[frontmatter_generator] page numbering tweak skipped: {exc}")


def scaffold_templates(force: bool = False) -> Tuple[str, str]:
    """
    Create placeholder cover / project-info DOCX templates with Jinja placeholders.
    Safe to call repeatedly; skips existing files unless force=True.

    Note: docxtpl paragraph-loops ({%p for %}) must occupy their own paragraphs.
    """
    _ensure_dir(TEMPLATES_DIR)

    if force or not os.path.exists(COVER_TEMPLATE):
        doc = Document()
        p = doc.add_paragraph("{{ university_name }}")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in p.runs:
            run.bold = True
            run.font.size = Pt(16)

        p = doc.add_paragraph("{{ department }}")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        p = doc.add_paragraph("{{ logo }}")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        p = doc.add_paragraph("{{ project_title }}")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in p.runs:
            run.bold = True
            run.font.size = Pt(20)

        p = doc.add_paragraph("Final Year Project Report")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        p = doc.add_paragraph("Session: {{ session }}")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        p = doc.add_paragraph("Submitted by:")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        # docxtpl: loop tags alone on their paragraphs
        p = doc.add_paragraph("{%p for member in members %}")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p = doc.add_paragraph(
            "{{ member.name }}{% if member.reg_no %} ({{ member.reg_no }}){% endif %}"
        )
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p = doc.add_paragraph("{%p endfor %}")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        p = doc.add_paragraph("Supervisor: {{ supervisor_name }}")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p = doc.add_paragraph(
            "{% if cosupervisor_name %}Co-Supervisor: {{ cosupervisor_name }}{% endif %}"
        )
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.save(COVER_TEMPLATE)

    if force or not os.path.exists(INFO_TEMPLATE):
        doc = Document()
        title = doc.add_paragraph("Project Details")
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in title.runs:
            run.bold = True
            run.font.size = Pt(16)

        doc.add_paragraph("Project Title: {{ project_title }}")
        doc.add_paragraph("University: {{ university_name }}")
        doc.add_paragraph("Department: {{ department }}")
        doc.add_paragraph("Session: {{ session }}")
        doc.add_paragraph("")
        doc.add_paragraph("Group Members:")
        doc.add_paragraph("{%p for member in members %}")
        doc.add_paragraph(
            "- {{ member.name }}"
            "{% if member.reg_no %} | Reg: {{ member.reg_no }}{% endif %}"
            "{% if member.email %} | {{ member.email }}{% endif %}"
        )
        doc.add_paragraph("{%p endfor %}")
        doc.add_paragraph("Supervisor: {{ supervisor_name }}")
        doc.add_paragraph(
            "{% if cosupervisor_name %}Co-Supervisor: {{ cosupervisor_name }}"
            "{% else %}Co-Supervisor: —{% endif %}"
        )
        doc.add_paragraph("")
        doc.add_paragraph("Domain / Area of Interest:")
        doc.add_paragraph(
            "{% for d in domain_flags %}{{ d.mark }} {{ d.name }}   {% endfor %}"
        )
        doc.add_paragraph("")
        doc.add_paragraph("Student Signature: {{ signature }}")
        doc.save(INFO_TEMPLATE)

    return COVER_TEMPLATE, INFO_TEMPLATE


def _domain_flags(selected: List[str]) -> List[dict]:
    selected_norm = {s.strip().lower() for s in selected if s and str(s).strip()}
    flags = []
    for name in DEFAULT_DOMAIN_OPTIONS:
        checked = name.lower() in selected_norm
        flags.append({
            "name": name,
            "checked": checked,
            "mark": "☑" if checked else "☐",
        })
    # Include any custom domains not in the default list
    for s in selected:
        name = str(s).strip()
        if name and name.lower() not in {d.lower() for d in DEFAULT_DOMAIN_OPTIONS}:
            flags.append({"name": name, "checked": True, "mark": "☑"})
    return flags


def _tpl_context(ctx: FrontmatterContext, tpl: DocxTemplate) -> dict:
    members = [
        {
            "name": m.name or "",
            "reg_no": m.reg_no or "",
            "email": m.email or "",
        }
        for m in (ctx.members or [])
    ]
    # Ensure at least one empty row so templates with loops don't look broken
    if not members:
        members = [{"name": "", "reg_no": "", "email": ""}]

    logo = ""
    if ctx.logo_path and os.path.isfile(ctx.logo_path):
        try:
            logo = InlineImage(tpl, ctx.logo_path, width=Mm(30))
        except Exception as exc:
            print(f"[frontmatter_generator] logo InlineImage failed: {exc}")
            logo = ""

    signature = ""
    if ctx.signature_path and os.path.isfile(ctx.signature_path):
        try:
            signature = InlineImage(tpl, ctx.signature_path, width=Mm(40))
        except Exception as exc:
            print(f"[frontmatter_generator] signature InlineImage failed: {exc}")
            signature = ""

    return {
        "project_title": ctx.project_title or "",
        "university_name": ctx.university_name or "",
        "department": ctx.department or "",
        "session": ctx.session or "",
        "members": members,
        "supervisor_name": ctx.supervisor_name or "",
        "cosupervisor_name": ctx.cosupervisor_name or "",
        "domains": list(ctx.domains or []),
        "domain_flags": _domain_flags(list(ctx.domains or [])),
        "logo": logo,
        "signature": signature,
    }


def render_template_to_bytes(template_path: str, ctx: FrontmatterContext) -> bytes:
    """
    Render one template into an in-memory DOCX byte buffer.

    - If the uploaded template has no Jinja markers, return it byte-for-byte
      so the cover/info pages match exactly what the admin uploaded.
    - If Jinja markers exist, fill them via docxtpl; on render failure fall
      back to the exact uploaded file so export never loses the pages.
    """
    if not os.path.exists(template_path):
        scaffold_templates()

    if not _docx_has_jinja_markers(template_path):
        with open(template_path, "rb") as f:
            return f.read()

    try:
        tpl = DocxTemplate(template_path)
        tpl.render(_tpl_context(ctx, tpl))
        buf = io.BytesIO()
        tpl.save(buf)
        return buf.getvalue()
    except Exception as exc:
        print(
            f"[frontmatter_generator] Jinja render failed for "
            f"{os.path.basename(template_path)} — using exact upload: {exc}"
        )
        with open(template_path, "rb") as f:
            return f.read()


def _docx_has_jinja_markers(template_path: str) -> bool:
    """
    True if the template body contains Jinja / docxtpl tags.

    Word often splits ``{{`` across adjacent ``<w:t>`` runs, so we strip XML
    tags before searching for contiguous markers.
    """
    import re
    import zipfile

    try:
        with zipfile.ZipFile(template_path, "r") as zf:
            xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
        # Collapse XML so split runs like >{</w:t><w:t>{ become {{
        plain = re.sub(r"<[^>]+>", "", xml)
        plain = plain.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
        return "{{" in plain or "{%" in plain
    except Exception:
        return False


def render_cover_page(ctx: FrontmatterContext) -> bytes:
    scaffold_templates()
    return render_template_to_bytes(COVER_TEMPLATE, ctx)


def render_info_page(ctx: FrontmatterContext) -> bytes:
    scaffold_templates()
    return render_template_to_bytes(INFO_TEMPLATE, ctx)


def _bytes_to_document(data: bytes) -> Document:
    return Document(io.BytesIO(data))


def merge_frontmatter_into_report(
    original_docx: Union[str, BinaryIO],
    *,
    cover_bytes: Optional[bytes] = None,
    info_bytes: Optional[bytes] = None,
    insert_cover: bool = False,
    insert_info: bool = False,
) -> bytes:
    """
    Prepend generated cover and/or info pages to the original report DOCX.

    Order produced:
      Cover → Info → (existing TOC/LOT/LOF if any) → report body

    Cover/info paragraphs are excluded from Word TOC outline levels. A
    ``_FormatifyBodyStart`` bookmark marks where the original report begins so
    TOC insertion stays after the cover/info pages.
    """
    from docxcompose.composer import Composer
    from docx_fields import ensure_formatify_body_start_bookmark

    if not insert_cover and not insert_info:
        if isinstance(original_docx, str):
            with open(original_docx, "rb") as f:
                return f.read()
        original_docx.seek(0)
        return original_docx.read()

    parts: List[Document] = []
    if insert_cover and cover_bytes:
        # Attach admin cover EXACTLY as uploaded — no style/TOC mutations
        cover_doc = _bytes_to_document(cover_bytes)
        _strip_trailing_empty_paragraphs(cover_doc)
        _strip_trailing_page_breaks(cover_doc)
        _add_page_break(cover_doc)
        parts.append(cover_doc)
    if insert_info and info_bytes:
        # Attach admin info page EXACTLY as uploaded — no style/TOC mutations
        info_doc = _bytes_to_document(info_bytes)
        _strip_trailing_empty_paragraphs(info_doc)
        _strip_trailing_page_breaks(info_doc)
        _add_page_break(info_doc)
        parts.append(info_doc)

    original = Document(original_docx)
    # Avoid leading blank page before original body content
    _strip_trailing_empty_paragraphs(original)  # no-op on leading; strip leading below
    _strip_leading_empty_paragraphs(original)
    # Mark where report body (and TOC/lists) belong — after cover/info
    ensure_formatify_body_start_bookmark(original)
    # Restart numbering on the report body (best-effort)
    if original.sections:
        _set_section_page_start(original.sections[0], start=1)

    if not parts:
        buf = io.BytesIO()
        original.save(buf)
        return buf.getvalue()

    master = parts[0]
    composer = Composer(master)
    for extra in parts[1:]:
        composer.append(extra)
    composer.append(original)

    # Final pass: collapse any blank interstitial pages from merge artifacts
    try:
        from docx_fields import remove_blank_interstitial_pages
        remove_blank_interstitial_pages(composer.doc)
    except Exception as exc:
        print(f"[frontmatter_generator] blank-page cleanup skipped: {exc}")

    out = io.BytesIO()
    composer.save(out)
    return out.getvalue()


def _strip_leading_empty_paragraphs(doc: Document) -> int:
    """Remove leading empty paragraphs so body does not start with a blank page."""
    body = doc.element.body
    removed = 0
    for child in list(body):
        if child.tag == qn("w:sectPr"):
            break
        if child.tag != qn("w:p"):
            break
        text = "".join((t.text or "") for t in child.iter(qn("w:t"))).strip()
        has_media = bool(
            list(child.iter(qn("w:drawing")))
            or list(child.iter(qn("w:pict")))
        )
        has_break = any(
            br.get(qn("w:type")) == "page" for br in child.iter(qn("w:br"))
        )
        if text or has_media:
            break
        if has_break:
            # Leading page-break-only would create a blank first body page
            body.remove(child)
            removed += 1
            continue
        body.remove(child)
        removed += 1
    return removed


def generate_frontmatter_docx(
    original_docx_path: str,
    ctx: FrontmatterContext,
    *,
    insert_cover: bool,
    insert_info: bool,
) -> bytes:
    """
    High-level: render needed pages from FrontmatterContext and merge into the report.
    Returns final DOCX bytes.
    """
    cover_bytes = render_cover_page(ctx) if insert_cover else None
    info_bytes = render_info_page(ctx) if insert_info else None
    return merge_frontmatter_into_report(
        original_docx_path,
        cover_bytes=cover_bytes,
        info_bytes=info_bytes,
        insert_cover=insert_cover,
        insert_info=insert_info,
    )
