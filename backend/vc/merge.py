"""Assemble merged documents and run post-merge analysis."""

from __future__ import annotations

import datetime
import json
import os
import re
import shutil
from typing import Any, Dict, List, Optional, Tuple

from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

from database import get_db
from template_logic.templates import get_template_by_id

UPLOAD_DIR = "uploads"

# "[image:12]" on its own line in a section's text = "put image 12 here".
_IMAGE_MARKER_LINE_RE = re.compile(r"^[ \t]*\[image:(\d+)\][ \t]*$", re.MULTILINE)
_IMAGE_TOKEN_RE = re.compile(r"^\[\[IMG(\d+)\]\]$")


def _user_org_id(user_id: int) -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT org_id FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row and "org_id" in row.keys() and row["org_id"] is not None:
        return int(row["org_id"])
    return 1


def _documents_has_org_id(cursor) -> bool:
    cursor.execute("PRAGMA table_info(documents)")
    return "org_id" in {row[1] for row in cursor.fetchall()}


def _apply_heading_style(para, level: int) -> None:
    level = max(1, min(4, level))
    try:
        para.style = f"Heading {level}"
    except Exception:
        para.style = "Heading 1"
    for run in para.runs:
        run.bold = True
        if level == 1:
            run.font.size = Pt(16)
        elif level == 2:
            run.font.size = Pt(14)
        else:
            run.font.size = Pt(12)


def _normalize_images(items: Optional[List[Any]]) -> List[Tuple[Optional[int], str]]:
    """
    Accepts, per section, a list whose items are any of:
      - "path/to/file.png"                       (old format, no id)
      - {"id": 12, "path": "path/to/file.png"}   (new format, enables markers)
      - (12, "path/to/file.png")
    Returns [(image_id_or_None, path), ...].
    """
    out: List[Tuple[Optional[int], str]] = []
    for it in items or []:
        if isinstance(it, dict):
            iid, path = it.get("id"), it.get("path") or it.get("file_path")
        elif isinstance(it, (tuple, list)) and len(it) == 2:
            iid, path = it
        else:
            iid, path = None, it
        try:
            iid = int(iid) if iid is not None else None
        except (TypeError, ValueError):
            iid = None
        out.append((iid, str(path) if path else ""))
    return out


def _add_picture(doc, img_path: str) -> None:
    if img_path and os.path.exists(img_path):
        try:
            doc.add_picture(img_path, width=Inches(5))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            return
        except Exception:
            pass
    doc.add_paragraph(f"[Image: {os.path.basename(img_path or 'missing')}]")




def assemble_merged_docx(
    sections: List[Dict[str, Any]],
    section_content: Dict[str, str],
    output_path: str,
    template_id: int,
    section_images: Optional[Dict[str, List[Any]]] = None,
) -> str:
    """
    Build a DOCX in strict template section order.
    Template order is master — upload/edit order is ignored.

    Images are placed where the author put an "[image:ID]" marker in the
    section text. Images that have no marker are appended at the end of the
    section (old behaviour). Markers whose image no longer exists are dropped
    silently, so the raw marker text never appears in the document.
    """
    print("IMG MAP:", section_images)
    print("CONTENT:", {k: v[:300] for k, v in section_content.items()})
    tmpl = get_template_by_id(template_id) or {}
    body_font = (tmpl.get("formatting_rules") or {}).get("body_font", "Times New Roman")

    doc = DocxDocument()
    ordered = sorted(sections, key=lambda s: s["template_order"])

    for sec in ordered:
        sid = sec["section_id"]
        title = sec["section_name"]
        level = int(sec.get("heading_level") or 1)
        content = (section_content.get(sid) or "").strip()

        images = _normalize_images((section_images or {}).get(sid))
        by_id = {iid: path for iid, path in images if iid is not None}
        used_ids = set()

        heading_para = doc.add_paragraph(title)
        _apply_heading_style(heading_para, level)

        if content:
            # Give every marker line its own block.
            prepared = _IMAGE_MARKER_LINE_RE.sub(
                lambda m: f"\n\n[[IMG{m.group(1)}]]\n\n", content
            )
            for block in prepared.split("\n\n"):
                block = block.strip()
                if not block:
                    continue

                token = _IMAGE_TOKEN_RE.match(block)
                if token:
                    iid = int(token.group(1))
                    if iid in by_id and iid not in used_ids:
                        used_ids.add(iid)
                        _add_picture(doc, by_id[iid])
                    continue

                if block.startswith(("•", "-", "*", "–", "·")):
                    for line in block.split("\n"):
                        line = line.strip()
                        if line:
                            doc.add_paragraph(line, style="List Bullet")
                else:
                    para = doc.add_paragraph(block)
                    for run in para.runs:
                        run.font.name = body_font
                        run.font.size = Pt(12)
        else:
            placeholder = doc.add_paragraph("[Section content not provided]")
            for run in placeholder.runs:
                run.italic = True

        # Images without a marker go at the end of the section.
        for iid, path in images:
            if iid is not None and iid in used_ids:
                continue
            _add_picture(doc, path)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    doc.save(output_path)
    return output_path


def resolve_section_content_map(
    sections: List[Dict[str, Any]],
    latest_by_section: Dict[str, str],
    conflicts: List[Dict[str, Any]],
) -> Dict[str, str]:
    """Pick final content per section, preferring manual resolutions."""
    final: Dict[str, str] = dict(latest_by_section)

    for conflict in conflicts:
        if conflict.get("status") != "resolved":
            continue
        resolution = (conflict.get("resolution_content") or "").strip()
        if not resolution:
            continue

        ctype = conflict["conflict_type"]
        sid = conflict.get("section_id")
        if ctype in ("multi_author", "section_mismatch") and sid:
            final[sid] = resolution
        elif ctype == "duplicate_content" and sid:
            final[sid] = resolution
            related = conflict.get("related_section_id")
            if related and related in final:
                details = conflict.get("details") or {}
                if isinstance(details, str):
                    details = json.loads(details)
                keep = details.get("keep_section_id")
                if keep and keep != sid:
                    final[sid] = latest_by_section.get(sid, "")

    return final


def register_uploaded_document(
    user_id: int,
    template_id: int,
    source_path: str,
    original_filename: str,
    status: str = "pending",
) -> Tuple[int, str]:
    """
    Copy an uploaded file into the main uploads directory and create a
    documents record so it appears in My Reports for analysis/download.
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = os.path.basename(original_filename or "document.docx")
    if not safe_name.lower().endswith(".docx"):
        safe_name = f"{safe_name}.docx"
    stored_filename = f"{timestamp}_{safe_name}"
    dest_path = os.path.join(UPLOAD_DIR, stored_filename)
    shutil.copy2(source_path, dest_path)

    conn = get_db()
    cursor = conn.cursor()
    if _documents_has_org_id(cursor):
        cursor.execute(
            """
            INSERT INTO documents (user_id, template_id, filename, file_path, status, org_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, template_id, safe_name, dest_path, status, _user_org_id(user_id)),
        )
    else:
        cursor.execute(
            """
            INSERT INTO documents (user_id, template_id, filename, file_path, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, template_id, safe_name, dest_path, status),
        )
    document_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return document_id, dest_path


def create_merged_document_record(
    project_id: int,
    user_id: int,
    template_id: int,
    file_path: str,
    project_name: str,
) -> int:
    conn = get_db()
    cursor = conn.cursor()
    filename = f"{project_name}_merged.docx"
    if _documents_has_org_id(cursor):
        cursor.execute(
            """
            INSERT INTO documents (user_id, template_id, filename, file_path, status, org_id)
            VALUES (?, ?, ?, ?, 'completed', ?)
            """,
            (user_id, template_id, filename, file_path, _user_org_id(user_id)),
        )
    else:
        cursor.execute(
            """
            INSERT INTO documents (user_id, template_id, filename, file_path, status)
            VALUES (?, ?, ?, ?, 'completed')
            """,
            (user_id, template_id, filename, file_path),
        )
    document_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return document_id


def update_merge_completed(
    merge_id: int,
    project_id: int,
    merged_path: str,
    document_id: int,
    analysis_report: Optional[Dict[str, Any]] = None,
) -> None:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE project_merges
        SET status = 'completed', merged_file_path = ?, document_id = ?,
            analysis_report = ?, completed_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            merged_path,
            document_id,
            json.dumps(analysis_report) if analysis_report else None,
            merge_id,
        ),
    )
    cursor.execute(
        """
        UPDATE collaboration_projects
        SET status = 'merged', merged_document_id = ?, merged_file_path = ?,
            last_merge_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (document_id, merged_path, project_id),
    )
    conn.commit()
    conn.close()