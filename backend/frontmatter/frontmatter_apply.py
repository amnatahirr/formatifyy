"""
frontmatter_apply.py — Ensure cover / project-info pages are on a formatted DOCX.

Called from the student export / working-copy path so downloaded reports include
the admin-uploaded templates without requiring a separate Flutter generate step.
"""

from __future__ import annotations

import io
import json
import os
from typing import Any, Dict, Optional

from database import get_db
from frontmatter.frontmatter_data import build_frontmatter_context
from frontmatter.frontmatter_detector import detect_frontmatter_heuristic
from frontmatter.frontmatter_generator import (
    generate_frontmatter_docx,
    refresh_leading_cover_from_template,
    render_cover_page,
    resolve_ask_fields_in_docx_path,
    scaffold_templates,
)
from models import DetectionResult, FrontmatterContext

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"


def _working_copy_path(document_id: int) -> str:
    return os.path.join(UPLOAD_DIR, "working", f"doc_{document_id}_working.docx")


def _export_copy_path(document_id: int) -> str:
    return os.path.join(OUTPUT_DIR, f"export_{document_id}.docx")


def _marker_path(document_id: int) -> str:
    return os.path.join(UPLOAD_DIR, "working", f"doc_{document_id}_frontmatter.flag")


def clear_frontmatter_marker(document_id: int) -> None:
    """Call when the working copy is rebuilt from the original upload."""
    path = _marker_path(document_id)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError as exc:
            print(f"[frontmatter_apply] marker clear failed: {exc}")


def _write_marker(document_id: int, payload: Dict[str, Any]) -> None:
    path = _marker_path(document_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def _document_starts_with_admin_cover(docx_path: str) -> bool:
    """
    True when the leading page matches the admin cover template.

    Used to recover working copies whose marker lost ``generated_cover`` but
    still begin with the Formatify-prepended cover (so we can refresh it).
    """
    try:
        from docx import Document

        cover = Document(io.BytesIO(render_cover_page(FrontmatterContext())))
        cover_lines = [
            (p.text or "").strip()
            for p in cover.paragraphs
            if (p.text or "").strip()
        ]
        # Skip the title line — older builds may have overwritten it.
        probes = [ln for ln in cover_lines[1:6] if len(ln) >= 8]
        if len(probes) < 2:
            return False
        doc = Document(docx_path)
        doc_lines = [
            (p.text or "").strip()
            for p in doc.paragraphs[:25]
            if (p.text or "").strip()
        ]
        hits = sum(1 for ln in probes if any(ln == d or ln in d or d in ln for d in doc_lines))
        return hits >= 2
    except Exception:
        return False


def _save_detection(document_id: int, result: DetectionResult, extra: Optional[Dict[str, Any]] = None) -> None:
    payload = result.model_dump()
    if extra:
        payload.update(extra)
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE documents
            SET frontmatter_detection = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (json.dumps(payload), document_id),
        )
        conn.commit()
    finally:
        conn.close()


def ensure_frontmatter_pages(document_id: int, docx_path: str) -> Dict[str, Any]:
    """
    If the DOCX is missing a cover and/or project-info page, prepend the admin
    templates (rendered when they contain Jinja placeholders, otherwise used
    exactly as uploaded).

    Uses a per-document flag file so export does not re-prepend on every download.
    Clears automatically when ``clear_frontmatter_marker`` is called after a
    full working-copy rebuild.

    After pages exist, repairs body-start bookmark and re-orders TOC/LOT/LOF so
    the document is always: Cover → Info → TOC/lists → Body.
    """
    status: Dict[str, Any] = {
        "applied": False,
        "generated_cover": False,
        "generated_info": False,
        "reason": "",
    }

    if not docx_path or not os.path.isfile(docx_path):
        status["reason"] = "docx_path missing"
        return status
    if not str(docx_path).lower().endswith(".docx"):
        status["reason"] = "not a docx"
        return status

    marker = _marker_path(document_id)
    already_marked = os.path.exists(marker)
    marker_payload: Dict[str, Any] = {}
    if already_marked:
        try:
            with open(marker, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                marker_payload = loaded
        except Exception:
            marker_payload = {}

    if not already_marked:
        try:
            detection, _pages = detect_frontmatter_heuristic(docx_path)
        except Exception as exc:
            print(f"[frontmatter_apply] detection failed (non-fatal): {exc}")
            status["reason"] = f"detection failed: {exc}"
            return status

        insert_cover = not detection.cover_page_present
        insert_info = not detection.info_page_present

        if insert_cover or insert_info:
            try:
                scaffold_templates()
                ctx = build_frontmatter_context(document_id)
                merged = generate_frontmatter_docx(
                    docx_path,
                    ctx,
                    insert_cover=insert_cover,
                    insert_info=insert_info,
                )
            except Exception as exc:
                print(f"[frontmatter_apply] generate/merge failed (non-fatal): {exc}")
                status["reason"] = f"generate failed: {exc}"
                return status

            try:
                working = _working_copy_path(document_id)
                export_path = _export_copy_path(document_id)
                os.makedirs(os.path.dirname(working), exist_ok=True)
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                with open(docx_path, "wb") as f:
                    f.write(merged)
                with open(working, "wb") as f:
                    f.write(merged)
                with open(export_path, "wb") as f:
                    f.write(merged)
            except Exception as exc:
                print(f"[frontmatter_apply] write failed (non-fatal): {exc}")
                status["reason"] = f"write failed: {exc}"
                return status

            status.update(
                {
                    "applied": True,
                    "generated_cover": insert_cover,
                    "generated_info": insert_info,
                    "project_title": getattr(ctx, "project_title", "") or "",
                }
            )
            marker_payload = {
                "applied": True,
                "generated_cover": insert_cover,
                "generated_info": insert_info,
            }
        else:
            status["reason"] = "cover and info already present"

    # If Formatify prepended the admin cover, refresh it from the current
    # admin template on every export/save so it stays exact (and so older
    # working copies that had project-title / member injection are repaired).
    generated_cover = bool(
        status.get("generated_cover")
        or marker_payload.get("generated_cover")
        or _document_starts_with_admin_cover(docx_path)
    )
    if generated_cover:
        try:
            # Build real context so the Jinja cover template renders with
            # actual university, members, supervisor, etc.
            try:
                _refresh_ctx = build_frontmatter_context(document_id)
            except Exception:
                _refresh_ctx = None
            if refresh_leading_cover_from_template(docx_path, ctx=_refresh_ctx):
                status["cover_refreshed"] = True
                status["applied"] = True
                status["generated_cover"] = True
                marker_payload["generated_cover"] = True
        except Exception as exc:
            print(f"[frontmatter_apply] cover refresh skipped: {exc}")
            status["cover_refresh_error"] = str(exc)

    # Always normalize order: Cover/Info → TOC/LOF/LOT → Body
    try:
        order_fix = fix_frontmatter_and_lists_order(docx_path)
        status["order_fix"] = order_fix
    except Exception as exc:
        print(f"[frontmatter_apply] order fix skipped: {exc}")
        status["order_fix_error"] = str(exc)

    # Collapse leftover ASK/FILLIN codes without injecting project context.
    # When Formatify owns the cover, also drop leftover RESULT placeholders so
    # static branding (e.g. FORMATIFY) matches the admin template preview.
    try:
        ask_count = resolve_ask_fields_in_docx_path(
            docx_path,
            ctx=None,
            keep_result=not bool(status.get("generated_cover")),
        )
        status["ask_fields_resolved"] = ask_count
        if ask_count:
            status["applied"] = True
    except Exception as exc:
        print(f"[frontmatter_apply] ASK field resolve skipped: {exc}")
        status["ask_fields_error"] = str(exc)

    try:
        from frontmatter.frontmatter_detector import detect_frontmatter_heuristic as _detect
        refreshed, _ = _detect(docx_path if os.path.isfile(docx_path) else _working_copy_path(document_id))
        _save_detection(
            document_id,
            refreshed,
            extra={
                "auto_applied": True,
                "applied_cover": status.get("generated_cover", False),
                "applied_info": status.get("generated_info", False),
            },
        )
        _write_marker(
            document_id,
            {
                "applied": True,
                "generated_cover": bool(
                    status.get("generated_cover")
                    or marker_payload.get("generated_cover")
                ),
                "generated_info": bool(
                    status.get("generated_info")
                    or marker_payload.get("generated_info")
                ),
            },
        )
        # Keep working/export synced after order fix
        working = _working_copy_path(document_id)
        export_path = _export_copy_path(document_id)
        if os.path.isfile(docx_path):
            os.makedirs(os.path.dirname(working), exist_ok=True)
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            if os.path.abspath(docx_path) != os.path.abspath(working):
                with open(docx_path, "rb") as src, open(working, "wb") as dst:
                    dst.write(src.read())
            with open(working, "rb") as src, open(export_path, "wb") as dst:
                dst.write(src.read())
    except Exception as exc:
        print(f"[frontmatter_apply] post-detect/marker skipped: {exc}")

    if status.get("applied") or status.get("order_fix"):
        status["reason"] = status.get("reason") or "ok"
    print(
        f"[frontmatter_apply] doc={document_id} "
        f"cover={status.get('generated_cover')} info={status.get('generated_info')} "
        f"order={status.get('order_fix')}"
    )
    return status


def fix_frontmatter_and_lists_order(docx_path: str) -> Dict[str, Any]:
    """
    Ensure document order is Cover → Info → TOC/LOF/LOT → Body.

    - Repairs ``_FormatifyBodyStart`` bookmark after leading page breaks
    - Re-arranges TOC/LOT/LOF blocks to sit just before the body bookmark
    - Rebuilds TOC entries so cover/info headings are not listed
    """
    from docx import Document

    from docx_tools.docx_fields import (
        arrange_front_matter_lists,
        document_has_lof,
        document_has_lot,
        document_has_toc,
        find_formatify_body_start_element,
        insert_toc_field,
        normalize_bookmarks,
        repair_formatify_body_start_bookmark,
        remove_blank_interstitial_pages,
        _prepare_toc_entries,
        _remove_toc_field_block,
        _find_section_heading_paragraph,
        _TOC_HEADING_RE,
    )

    doc = Document(docx_path)
    try:
        result_norm_start = normalize_bookmarks(doc)
    except Exception as exc:
        print(f"[frontmatter_apply] bookmark normalize (start) skipped: {exc}")
        result_norm_start = {"error": str(exc)}
    result: Dict[str, Any] = {
        "bookmark_repaired": False,
        "lists_rearranged": False,
        "toc_rebuilt": False,
        "blank_pages_removed": {},
        "bookmarks_normalized_start": result_norm_start,
    }

    # Always strip blank interstitial pages (cover/info merge artifact)
    try:
        result["blank_pages_removed"] = remove_blank_interstitial_pages(doc)
    except Exception as exc:
        print(f"[frontmatter_apply] blank page cleanup skipped: {exc}")
        result["blank_pages_error"] = str(exc)

    # How many leading page-breaks? cover-only → 1, cover+info → 2
    breaks = 0
    for child in list(doc.element.body)[:40]:
        from docx_tools.docx_fields import _is_page_break_only_paragraph
        from docx.oxml.ns import qn
        if child.tag == qn("w:p") and _is_page_break_only_paragraph(child):
            breaks += 1
        elif breaks > 0 and child.tag == qn("w:p"):
            # stop counting once we hit non-break after starting
            pass
    expected_breaks = 2 if breaks >= 2 else (1 if breaks == 1 else 2)

    if find_formatify_body_start_element(doc) is None:
        result["bookmark_repaired"] = repair_formatify_body_start_bookmark(
            doc, expected_leading_page_breaks=max(1, min(expected_breaks, 2))
        )

    has_toc = document_has_toc(doc)
    has_lot = document_has_lot(doc)
    has_lof = document_has_lof(doc)

    if has_toc:
        # Rebuild TOC so entries exclude cover/info headings
        try:
            entries = _prepare_toc_entries(doc, "1-3")
            _remove_toc_field_block(doc)
            toc_heading = _find_section_heading_paragraph(doc, _TOC_HEADING_RE)
            insert_toc_field(doc, levels="1-3", heading_para=toc_heading, entries=entries)
            result["toc_rebuilt"] = True
            result["toc_entry_count"] = len(entries)
        except Exception as exc:
            print(f"[frontmatter_apply] TOC rebuild skipped: {exc}")
            result["toc_rebuild_error"] = str(exc)

    if has_toc or has_lot or has_lof:
        layout = arrange_front_matter_lists(
            doc,
            include_toc=has_toc,
            include_lot=has_lot,
            include_lof=has_lof,
        )
        result["lists_rearranged"] = True
        result["layout"] = layout

    # Final cleanup after TOC/list rearrangement
    try:
        final_clean = remove_blank_interstitial_pages(doc)
        result["blank_pages_removed_final"] = final_clean
    except Exception as exc:
        print(f"[frontmatter_apply] final blank cleanup skipped: {exc}")

    # GC stale/malformed managed bookmarks as the last mutation before save
    try:
        result["bookmarks_normalized_end"] = normalize_bookmarks(doc)
    except Exception as exc:
        print(f"[frontmatter_apply] bookmark normalize (end) skipped: {exc}")

    doc.save(docx_path)
    return result
