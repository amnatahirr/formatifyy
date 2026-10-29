"""
frontmatter_generator.py — Render cover / project-info templates and prepend to a report.

Uses docxtpl (Jinja2-style DOCX) for rendering and docxcompose.Composer to merge
while preserving styles. Optional pages are skipped when already present.
"""

from __future__ import annotations

import io
import os
import re
from copy import deepcopy
from typing import BinaryIO, Dict, List, Optional, Tuple, Union

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Mm
from docxtpl import DocxTemplate, InlineImage

from models import FrontmatterContext

# Word ASK / FILLIN fields left in admin cover templates show as raw
# ``ASK ReportTitle "…" \* MERGEFORMAT`` in many viewers. Collapse them to
# plain text filled from FrontmatterContext (or the field's existing result).
_ASK_FILLIN_RE = re.compile(
    r"^\s*(?:ASK|FILLIN)\s+([A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)

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


def _ask_values_from_context(ctx: Optional[FrontmatterContext]) -> Dict[str, str]:
    """Map common Word ASK bookmark names → FrontmatterContext values."""
    if ctx is None:
        return {}
    members = ", ".join(
        (m.name or "").strip()
        for m in (ctx.members or [])
        if (m.name or "").strip()
    )
    title = (ctx.project_title or "").strip()
    return {
        "reporttitle": title,
        "title": title,
        "projecttitle": title,
        "project_title": title,
        "reportauthor": members,
        "author": members,
        "name": members,
        "fullname": members,
        "studentname": members,
        "degree": "",
        "degreeclassification": "",
    }


def _run_fld_char_type(run_el) -> Optional[str]:
    for fc in run_el.findall(qn("w:fldChar")):
        return fc.get(qn("w:fldCharType"))
    return None


def _run_instr_text(run_el) -> str:
    return "".join((el.text or "") for el in run_el.findall(qn("w:instrText")))


def _run_visible_text(run_el) -> str:
    return "".join((el.text or "") for el in run_el.findall(qn("w:t")))


def _collapse_ask_fields_in_paragraph(
    p_el,
    values: Dict[str, str],
    *,
    keep_result: bool = True,
) -> int:
    """
    Replace ASK/FILLIN complex fields in one paragraph with plain text.

    Returns the number of fields collapsed.
    """
    children = list(p_el)
    collapsed = 0
    i = 0
    while i < len(children):
        child = children[i]
        if child.tag != qn("w:r") or _run_fld_char_type(child) != "begin":
            i += 1
            continue

        begin_idx = i
        instr_parts: List[str] = []
        result_parts: List[str] = []
        result_rpr = None
        sep_seen = False
        end_idx = None
        j = i + 1
        while j < len(children):
            node = children[j]
            if node.tag != qn("w:r"):
                j += 1
                continue
            fld_type = _run_fld_char_type(node)
            if not sep_seen:
                instr_parts.append(_run_instr_text(node))
                if fld_type == "separate":
                    sep_seen = True
                elif fld_type == "end":
                    break
            else:
                if fld_type == "end":
                    end_idx = j
                    break
                if fld_type == "begin":
                    end_idx = None
                    break
                txt = _run_visible_text(node)
                if txt:
                    result_parts.append(txt)
                if result_rpr is None:
                    rpr = node.find(qn("w:rPr"))
                    if rpr is not None:
                        result_rpr = deepcopy(rpr)
            j += 1

        if end_idx is None:
            i += 1
            continue

        instruction = "".join(instr_parts)
        match = _ASK_FILLIN_RE.match(instruction)
        if not match:
            i = end_idx + 1
            continue

        existing_result = "".join(result_parts).strip()
        key = match.group(1).strip().lower()
        filled = (values.get(key) or "").strip()
        # Cover pages: drop ASK chrome + leftover RESULT placeholders so only
        # the admin's static runs remain (e.g. "FORMATIFY"). Info pages keep
        # RESULT when context does not supply a value.
        if filled:
            replacement = filled
        elif keep_result:
            replacement = existing_result
        else:
            replacement = ""

        # Remove the field entirely when there is nothing to show — keeps
        # adjacent static runs (e.g. FORMATIFY) and avoids blank RESULT text.
        if not replacement:
            for node in children[begin_idx : end_idx + 1]:
                try:
                    p_el.remove(node)
                except ValueError:
                    pass
            collapsed += 1
            children = list(p_el)
            i = begin_idx
            continue

        new_run = OxmlElement("w:r")
        if result_rpr is not None:
            new_run.append(result_rpr)
        else:
            for k in range(begin_idx, end_idx + 1):
                if children[k].tag != qn("w:r"):
                    continue
                rpr = children[k].find(qn("w:rPr"))
                if rpr is not None:
                    new_run.append(deepcopy(rpr))
                    break
        text_el = OxmlElement("w:t")
        text_el.set(qn("xml:space"), "preserve")
        text_el.text = replacement
        new_run.append(text_el)

        anchor = children[begin_idx]
        p_el.insert(list(p_el).index(anchor), new_run)
        for node in children[begin_idx : end_idx + 1]:
            try:
                p_el.remove(node)
            except ValueError:
                pass

        collapsed += 1
        children = list(p_el)
        try:
            i = children.index(new_run) + 1
        except ValueError:
            i = begin_idx + 1

    return collapsed


def resolve_ask_fields_in_document(
    doc: Document,
    ctx: Optional[FrontmatterContext] = None,
    *,
    keep_result: bool = True,
) -> int:
    """
    Collapse every ASK/FILLIN field in ``doc`` to plain visible text.

    Safe to call repeatedly. Non-ASK fields (TOC, PAGEREF, SEQ, …) are left alone.
    When ``keep_result`` is False (cover pages), leftover RESULT placeholders
    are discarded so only static template text remains.
    """
    values = _ask_values_from_context(ctx)
    total = 0
    for para in doc.paragraphs:
        total += _collapse_ask_fields_in_paragraph(
            para._element, values, keep_result=keep_result
        )
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    total += _collapse_ask_fields_in_paragraph(
                        para._element, values, keep_result=keep_result
                    )
    if total:
        print(f"[frontmatter_generator] collapsed {total} ASK/FILLIN field(s)")
    return total


def resolve_ask_fields_in_docx_path(
    docx_path: str,
    ctx: Optional[FrontmatterContext] = None,
    *,
    keep_result: bool = True,
) -> int:
    """Load → collapse ASK/FILLIN → save in place. Returns fields collapsed."""
    if not docx_path or not os.path.isfile(docx_path):
        return 0
    if not str(docx_path).lower().endswith(".docx"):
        return 0
    try:
        doc = Document(docx_path)
        count = resolve_ask_fields_in_document(doc, ctx, keep_result=keep_result)
        if count:
            doc.save(docx_path)
        return count
    except Exception as exc:
        print(f"[frontmatter_generator] ASK field resolve skipped: {exc}")
        return 0


def _document_to_bytes(doc: Document) -> bytes:
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def render_template_to_bytes(
    template_path: str,
    ctx: FrontmatterContext,
    *,
    fill_ask_from_context: bool = True,
    keep_ask_result: bool = True,
) -> bytes:
    """
    Render one template into an in-memory DOCX byte buffer.

    - If the uploaded template has no Jinja markers, load it and collapse
      Word ASK/FILLIN fields (optionally fill from context; optionally keep
      the template RESULT text).
    - If Jinja markers exist, fill them via docxtpl; on render failure fall
      back to the uploaded file (with ASK fields resolved).
    """
    if not os.path.exists(template_path):
        scaffold_templates()

    ask_ctx = ctx if fill_ask_from_context else None

    def _load_and_resolve(path: str) -> bytes:
        doc = Document(path)
        resolve_ask_fields_in_document(
            doc, ask_ctx, keep_result=keep_ask_result
        )
        _strip_paragraph_numbering(doc)
        return _document_to_bytes(doc)

    if not _docx_has_jinja_markers(template_path):
        return _load_and_resolve(template_path)

    try:
        tpl = DocxTemplate(template_path)
        tpl.render(_tpl_context(ctx, tpl))
        buf = io.BytesIO()
        tpl.save(buf)
        doc = Document(io.BytesIO(buf.getvalue()))
        resolve_ask_fields_in_document(
            doc, ask_ctx, keep_result=keep_ask_result
        )
        _strip_paragraph_numbering(doc)
        return _document_to_bytes(doc)
    except Exception as exc:
        print(
            f"[frontmatter_generator] Jinja render failed for "
            f"{os.path.basename(template_path)} — using exact upload: {exc}"
        )
        return _load_and_resolve(template_path)


def _strip_paragraph_numbering(doc: Document) -> None:
    """Remove Word list/outline numbering so cover titles never show as '1. …'."""
    for para in doc.paragraphs:
        p_pr = para._element.find(qn("w:pPr"))
        if p_pr is None:
            continue
        num_pr = p_pr.find(qn("w:numPr"))
        if num_pr is not None:
            p_pr.remove(num_pr)


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
    """
    Admin cover page as uploaded.

    ASK/FILLIN fields are stripped (not filled from project context, and not
    kept as leftover RESULT placeholders). Static runs outside those fields
    — e.g. branding like ``FORMATIFY`` — remain exactly as in the upload.
    Jinja placeholders are still filled when the admin used them.
    """
    scaffold_templates()
    return render_template_to_bytes(
        COVER_TEMPLATE,
        ctx,
        fill_ask_from_context=False,
        keep_ask_result=False,
    )


def render_info_page(ctx: FrontmatterContext) -> bytes:
    scaffold_templates()
    return render_template_to_bytes(
        INFO_TEMPLATE,
        ctx,
        fill_ask_from_context=True,
    )


def _strip_leading_cover_page(doc: Document) -> bool:
    """
    Remove the first page of ``doc`` (content through the first page break).

    Returns True if a leading page was removed.
    """
    from docx_tools.docx_fields import _paragraph_has_page_break

    body = doc.element.body
    to_remove: List = []
    found_break = False
    for child in list(body):
        if child.tag == qn("w:sectPr"):
            break
        to_remove.append(child)
        if child.tag == qn("w:p") and _paragraph_has_page_break(child):
            found_break = True
            break
    if not found_break or not to_remove:
        return False
    for el in to_remove:
        try:
            body.remove(el)
        except ValueError:
            pass
    return True


def refresh_leading_cover_from_template(docx_path: str) -> bool:
    """
    Replace the leading cover page in ``docx_path`` with a freshly rendered
    admin cover template (exact RESULT text, no context injection).

    Preserves everything after the first page break (info / TOC / body).
    """
    if not docx_path or not os.path.isfile(docx_path):
        return False
    if not os.path.isfile(COVER_TEMPLATE):
        return False
    try:
        from docxcompose.composer import Composer

        # Minimal context — cover ASK fields are stripped, not filled.
        cover_bytes = render_cover_page(FrontmatterContext())
        cover_doc = _bytes_to_document(cover_bytes)
        _strip_trailing_empty_paragraphs(cover_doc)
        _strip_trailing_page_breaks(cover_doc)
        _strip_paragraph_numbering(cover_doc)
        _add_page_break(cover_doc)

        main_doc = Document(docx_path)
        if not _strip_leading_cover_page(main_doc):
            print("[frontmatter_generator] cover refresh skipped: no leading page break")
            return False

        composer = Composer(cover_doc)
        composer.append(main_doc)
        try:
            from docx_tools.docx_fields import remove_blank_interstitial_pages
            remove_blank_interstitial_pages(composer.doc)
        except Exception:
            pass
        composer.doc.save(docx_path)
        print(
            f"[frontmatter_generator] refreshed cover from admin template -> {docx_path}"
        )
        return True
    except Exception as exc:
        print(f"[frontmatter_generator] cover refresh failed: {exc}")
        return False


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
    from docx_tools.docx_fields import ensure_formatify_body_start_bookmark

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
        _strip_paragraph_numbering(cover_doc)
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
        from docx_tools.docx_fields import remove_blank_interstitial_pages
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
