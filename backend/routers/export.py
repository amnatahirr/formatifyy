from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
import os
import json
from datetime import datetime
import tempfile
import shutil
import subprocess
import io
from docx.shared import Inches
import uuid

from formatter.docx_formatter import format_docx
from formatter.rules import detect_line_type
from database import get_db

from services.docx_parser import parse_docx_with_line_numbers
from services.pdf_parser import parse_pdf
from services.docx_generator import generate_docx
from docx import Document as DocxDocument
from routers.format_document import build_formatted_elements_for_document, export_elements_to_docx
from routers.documents import _apply_template_styles_to_docx

# ── Bullet services ───────────────────────────────────────────────────────────
from services.bullet_formatter_service import BulletFormatterService, BulletStyle

bullet_formatter = BulletFormatterService()

try:
    from docx2pdf import convert as docx2pdf_convert
except ImportError:
    docx2pdf_convert = None
    print("docx2pdf not installed. PDF export may not work properly.")

try:
    import subprocess
    LIBREOFFICE_AVAILABLE = True
except Exception:
    LIBREOFFICE_AVAILABLE = False


# ── Working copy helper (mirrors documents.py convention) ────────────────────
def _get_effective_export_path(document_id: int, original_path: str) -> str:
    """
    Returns the working copy path if incremental fixes (e.g. apply-fix bullets)
    have been applied to this document, otherwise the original path.
    Working copies live at: uploads/working/doc_{id}_working.docx
    """
    working = os.path.join("uploads", "working", f"doc_{document_id}_working.docx")
    return working if os.path.exists(working) else original_path

router = APIRouter(prefix="/api/export", tags=["export"])

UPLOAD_FOLDER   = "uploads"
FORMATTED_FOLDER = "formatted"
os.makedirs(FORMATTED_FOLDER, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers (unchanged from original)
# ─────────────────────────────────────────────────────────────────────────────

def convert_docx_to_pdf_libreoffice(input_path: str, output_path: str) -> bool:
    try:
        output_dir = os.path.dirname(output_path)
        subprocess.run(
            ["soffice", "--headless", "--convert-to", "pdf", "--outdir", output_dir, input_path],
            check=True, capture_output=True,
        )
        expected_pdf = os.path.join(
            output_dir,
            os.path.splitext(os.path.basename(input_path))[0] + ".pdf"
        )
        if os.path.exists(expected_pdf) and expected_pdf != output_path:
            shutil.move(expected_pdf, output_path)
        return True
    except Exception as e:
        print(f"LibreOffice conversion error: {e}")
        return False


def get_document_images_from_db(document_id: int):
    try:
        conn = get_db()
        images = conn.execute(
            "SELECT image_path, image_filename, line_number FROM document_images "
            "WHERE document_id = ? ORDER BY line_number",
            (document_id,)
        ).fetchall()
        conn.close()

        result = []
        for img in images:
            if os.path.exists(img["image_path"]):
                with open(img["image_path"], 'rb') as f:
                    image_data = f.read()
                result.append({
                    'data': image_data,
                    'filename': img["image_filename"],
                    'line_number': img["line_number"]
                })
        print(f"Retrieved {len(result)} images from database for document {document_id}")
        return result
    except Exception as e:
        print(f"Error getting images from database: {e}")
        return []


def create_docx_with_images(parsed_lines, images, output_path, template_rules=None):
    try:
        doc = DocxDocument()
        sorted_images = sorted(images, key=lambda x: x.get('line_number', 0))
        image_map = {}
        for img in sorted_images:
            line_num = img.get('line_number')
            if line_num:
                image_map.setdefault(line_num, []).append(img)

        image_index = 0
        for i, line in enumerate(parsed_lines):
            text     = line.get("text", "")
            line_num = line.get("line", i + 1)

            if line_num in image_map and image_map[line_num]:
                for img in image_map[line_num]:
                    try:
                        img_bytes = io.BytesIO(img['data'])
                        p   = doc.add_paragraph()
                        run = p.add_run()
                        run.add_picture(img_bytes, width=Inches(5))
                        p.paragraph_format.space_after = Inches(0.1)
                        image_index += 1
                    except Exception as e:
                        print(f"Error adding image at line {line_num}: {e}")
                        doc.add_paragraph("[Image could not be embedded]")
                image_map[line_num] = []

            if text and text != "[IMAGE]":
                p          = doc.add_paragraph(text)
                line_type  = line.get("type", "paragraph")
                if line_type == "heading1":
                    p.style = doc.styles['Heading 1']
                elif line_type == "heading2":
                    p.style = doc.styles['Heading 2']
                elif line_type == "heading3":
                    p.style = doc.styles['Heading 3']
                elif line_type == "list_item":
                    p.style = doc.styles['List Paragraph']

        # Any remaining images
        for line_num, imgs in image_map.items():
            for img in imgs:
                try:
                    img_bytes = io.BytesIO(img['data'])
                    p   = doc.add_paragraph()
                    run = p.add_run()
                    run.add_picture(img_bytes, width=Inches(5))
                except Exception as e:
                    print(f"Error adding remaining image: {e}")

        doc.save(output_path)
        print(f"Created DOCX with {image_index} images at {output_path}")
        return image_index > 0
    except Exception as e:
        import traceback
        print(f"Error creating DOCX with images: {e}")
        traceback.print_exc()
        return False


# ─────────────────────────────────────────────────────────────────────────────
# NEW: split soft-break lines and classify them
# ─────────────────────────────────────────────────────────────────────────────

def _expand_and_classify_parsed_lines(parsed_lines):
    """
    Split \\n-joined blobs into individual lines and classify each as
    'list_item' or 'paragraph'.

    Fixes:
      1. Ordinal-step items ("First step is...", "Final step is...") are
         always list_items even though they end with a period.
      2. The all_short check applies to the whole sibling group so items
         without keyword context (e.g. study activity lists) are detected.
      3. Items > 15 words ending with punctuation are never list_items,
         preventing closing-prose sentences from being mistakenly bulleted.
    """
    _LIST_CONTEXT_KEYWORDS = [
        'following', 'below', 'includes', 'consists of', 'contains',
        'such as', 'examples', 'list', 'steps', 'requirements',
        'features', 'benefits', 'include:', 'followed by:', 'as follows:'
    ]
    import re as _re
    _STEP_PATTERN = _re.compile(
        r'^(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|'
        r'final|last|next|then|another)\s+(step|item|point|stage|phase|task)',
        _re.IGNORECASE
    )

    def _looks_like_bullet(item):
        """True if this item belongs in a list."""
        words = len(item.split())
        ends_sentence = item.endswith(('.', '?', '!'))
        is_step = bool(_STEP_PATTERN.match(item))
        # Short items, OR step-pattern items, qualify
        return words <= 15 and (not ends_sentence or is_step)

    result = []
    for line in parsed_lines:
        text     = line.get("text", "")
        line_num = line.get("line", 0)
        ltype    = line.get("type", "paragraph")

        if '\n' not in text:
            result.append(line)
            continue

        items = [t.strip() for t in text.split('\n') if t.strip()]
        if not items:
            result.append(line)
            continue

        # Check context from previous real line
        prev_text = ""
        for prev_line in reversed(result):
            prev_text = prev_line.get("text", "").lower()
            if prev_text:
                break

        keyword_context = (
            prev_text.rstrip().endswith(':') or
            any(kw in prev_text for kw in _LIST_CONTEXT_KEYWORDS)
        )

        # All siblings look like bullets → treat whole group as a list
        all_look_like_bullets = all(_looks_like_bullet(it) for it in items)

        is_list   = keyword_context or all_look_like_bullets
        item_type = "list_item" if is_list else ltype

        for item in items:
            result.append({"text": item, "type": item_type, "line": line_num})

    return result



# ─────────────────────────────────────────────────────────────────────────────
# Main export endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/document/{document_id}")
async def export_document(
    document_id: int,
    user_id: int = Query(...),
    format: str = "docx",
    apply_bullets: bool = Query(True),
    auto_detect_bullets: bool = Query(True),
):
    """
    Export a document using template formatting rules with bullet formatting.
    Supports DOCX → DOCX/PDF/TXT, PDF → DOCX/PDF/TXT, and TXT → DOCX/PDF/TXT.
    """
    export_format = format.lower()
    if export_format not in ["docx", "pdf", "txt"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported export format. Use 'docx', 'pdf', or 'txt'"
        )

    # Primary pipeline for DOCX export: parse -> classify -> template -> docx
    if export_format == "docx":
        filename, _template_id, elements = build_formatted_elements_for_document(document_id, user_id)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = os.path.splitext(filename)[0]
        output_file = os.path.join(FORMATTED_FOLDER, f"{base_filename}_{timestamp}.docx")
        export_elements_to_docx(elements, output_file)
        return FileResponse(
            path=output_file,
            filename=f"{base_filename}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    # ── Fetch document ───────────────────────────────────────────────────────
    conn = get_db()
    doc  = conn.execute(
        "SELECT file_path, template_id, filename, user_id FROM documents WHERE id = ?",
        (document_id,),
    ).fetchone()

    if not doc:
        conn.close()
        raise HTTPException(status_code=404, detail="Document not found")

    if doc["user_id"] != user_id:
        conn.close()
        raise HTTPException(status_code=403, detail="Unauthorized access to document")

    original_filename = doc["filename"]

    # Use working copy if incremental fixes have been applied
    original_file = _get_effective_export_path(document_id, doc["file_path"])
    print(f"[export] reading from: {original_file}")

    if not os.path.exists(original_file):
        conn.close()
        raise HTTPException(status_code=404, detail="Document file not found")

    # ── Load template rules ──────────────────────────────────────────────────
    template_rules = None
    if doc["template_id"]:
        template = conn.execute(
            "SELECT formatting_rules FROM templates WHERE id = ?",
            (doc["template_id"],),
        ).fetchone()
        if template and template["formatting_rules"]:
            try:
                template_rules = json.loads(template["formatting_rules"])
            except (json.JSONDecodeError, TypeError):
                print(f"Failed to parse template rules for template {doc['template_id']}")

    conn.close()

    # ── Load images ──────────────────────────────────────────────────────────
    document_images = get_document_images_from_db(document_id)
    has_images      = len(document_images) > 0
    print(f"Document has {len(document_images)} images in database")

    # ── Derive input extension here (needed for working-copy check below) ──────
    input_ext = original_file.split(".")[-1].lower()

    # ── Check if working copy exists ─────────────────────────────────────────
    # If the user applied selective bullets via the Bullets tab, we have a
    # working copy with exactly those bullets. Export it directly without
    # re-running any auto-detection or bulk formatter — that would overwrite
    # the user's per-group choices.
    working_copy_path = os.path.join("uploads", "working", f"doc_{document_id}_working.docx")
    has_working_copy  = os.path.exists(working_copy_path)

    if has_working_copy and input_ext == "docx":
        print(f"[export] Working copy found: {working_copy_path}")
        timestamp     = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = os.path.splitext(original_filename)[0]

        # ── Apply template styles to the working copy before sending ──────────
        # The working copy preserves incremental fixes (bullets, heading words).
        # We now also stamp every paragraph with the template's font / size /
        # spacing rules so the downloaded file truly reflects the chosen template.
        styled_working_path = working_copy_path  # fallback: no template
        if template_rules:
            try:
                styled_path = os.path.join(
                    FORMATTED_FOLDER, f"{base_filename}_{timestamp}_styled.docx"
                )
                _apply_template_styles_to_docx(
                    working_copy_path, styled_path, template_rules
                )
                styled_working_path = styled_path
                print("[export] Template styles applied to working copy")
            except Exception as _e:
                print(f"[export] Warning: could not apply template styles: {_e}")
        else:
            print("[export] No template rules found — exporting working copy as-is")

        if export_format == "docx":
            output_file = os.path.join(FORMATTED_FOLDER, f"{base_filename}_{timestamp}.docx")
            shutil.copy2(styled_working_path, output_file)
            return FileResponse(
                path=output_file,
                filename=f"{base_filename}.docx",
                media_type="application/vnd.openxmlformats-officedocument"
                           ".wordprocessingml.document",
            )

        elif export_format == "pdf":
            output_file = os.path.join(FORMATTED_FOLDER, f"{base_filename}_{timestamp}.pdf")
            conversion_success = False
            if docx2pdf_convert:
                try:
                    docx2pdf_convert(styled_working_path, output_file)
                    conversion_success = True
                    print("[export] Styled working copy → PDF via docx2pdf")
                except Exception as e:
                    print(f"docx2pdf failed: {e}")
            if not conversion_success:
                try:
                    conversion_success = convert_docx_to_pdf_libreoffice(
                        styled_working_path, output_file
                        )
                    if conversion_success:
                        print("[export] Styled working copy → PDF via LibreOffice")
                except Exception as e:
                    print(f"LibreOffice failed: {e}")
            if not conversion_success:
                raise HTTPException(
                    status_code=500,
                    detail="PDF conversion failed. Ensure docx2pdf or LibreOffice is installed.",
                    )
            return FileResponse(
                path=output_file,
                filename=f"{base_filename}.pdf",
                media_type="application/pdf",
                )

        elif export_format == "txt":
            output_file = os.path.join(FORMATTED_FOLDER, f"{base_filename}_{timestamp}.txt")
            from docx import Document as _WC_Doc
            wc_doc = _WC_Doc(styled_working_path)
            with open(output_file, "w", encoding="utf-8") as f:
                for para in wc_doc.paragraphs:
                    text = para.text.strip()
                    if not text:
                        continue
                    style_name = para.style.name.lower() if para.style else ""
                    if "heading 1" in style_name:
                        f.write(f"\n{'='*60}\n{text.upper()}\n{'='*60}\n\n")
                    elif "heading 2" in style_name:
                        f.write(f"\n{text}\n{'-'*len(text)}\n\n")
                    elif "heading 3" in style_name:
                        f.write(f"\n### {text}\n\n")
                    elif "list" in style_name or "bullet" in style_name:
                        f.write(f"  • {text}\n")
                    else:
                        f.write(f"{text}\n\n")
            return FileResponse(
        path=output_file,
        filename=f"{base_filename}.txt",
        media_type="text/plain",
    )

    # ── No working copy: proceed with normal export pipeline ─────────────────
    parsed_lines = []

    try:
        if input_ext == "docx":
            parsed_paragraphs = parse_docx_with_line_numbers(original_file)
            prev_type = None
            for para in parsed_paragraphs:
                text      = para["text"]
                line_num  = para["line"]
                line_type = detect_line_type(text, prev_type)
                parsed_lines.append({"text": text, "type": line_type, "line": line_num})
                prev_type = line_type

        elif input_ext == "pdf":
            pdf_lines = parse_pdf(original_file)
            prev_type = None
            for i, line in enumerate(pdf_lines):
                text      = line["text"] if isinstance(line, dict) else str(line)
                line_type = detect_line_type(text, prev_type)
                parsed_lines.append({"text": text, "type": line_type, "line": i + 1})
                prev_type = line_type

        elif input_ext == "txt":
            with open(original_file, "r", encoding="utf-8") as f:
                raw_lines = f.readlines()
            prev_type = None
            for i, line in enumerate(raw_lines):
                line = line.strip()
                if line:
                    line_type = detect_line_type(line, prev_type)
                    parsed_lines.append({"text": line, "type": line_type, "line": i + 1})
                    prev_type = line_type

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {input_ext}")

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Parsing failed: {str(e)}")

    if not parsed_lines:
        print("No valid lines found, returning original file")
        return FileResponse(path=original_file, filename=original_filename,
                            media_type="application/octet-stream")

    # ── KEY FIX: expand soft-break lines and classify list items ─────────────
    if apply_bullets and auto_detect_bullets and input_ext == "docx":
        parsed_lines = _expand_and_classify_parsed_lines(parsed_lines)
        list_count = sum(1 for l in parsed_lines if l.get("type") == "list_item")
        print(f"[export] After expansion: {len(parsed_lines)} lines, {list_count} list_items")

    # ── Determine output path ────────────────────────────────────────────────
    timestamp      = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename  = os.path.splitext(original_filename)[0]
    output_file    = os.path.join(
        FORMATTED_FOLDER, f"{base_filename}_{timestamp}.{export_format}"
    )

    # ── Generate formatted output ────────────────────────────────────────────
    try:
        if export_format == "txt":
            with open(output_file, "w", encoding="utf-8") as f:
                for line in parsed_lines:
                    text = line["text"]
                    if text == "[IMAGE]":
                        f.write("[Image]\n\n")
                    else:
                        # Prefix bullet char for list items in plain text
                        prefix = "• " if (apply_bullets and line.get("type") == "list_item") else ""
                        f.write(prefix + text + "\n\n")

        elif export_format == "docx":
            # Step A: generate base DOCX (with list_item style for detected items)
            if has_images:
                print("Creating DOCX with images")
                success = create_docx_with_images(
                    parsed_lines, document_images, output_file, template_rules
                )
                if not success:
                    generate_docx(parsed_lines, output_file, template_rules=template_rules)
            else:
                generate_docx(parsed_lines, output_file, template_rules=template_rules)

            # Step B: apply bullet_formatter_service on top
            # This handles any items still needing bullet chars AND
            # runs _expand_soft_breaks() as a safety net for any
            # <w:br/> that survived into the generated DOCX.
            if apply_bullets and os.path.exists(output_file):
                bulleted_path = output_file.replace(".docx", "_bulleted.docx")
                ok = bullet_formatter.apply_bullet_formatting(
                    output_file,
                    bulleted_path,
                    formatting_rules=template_rules,
                )
                if ok and os.path.exists(bulleted_path):
                    os.replace(bulleted_path, output_file)
                    print("[export] Bullet formatting applied successfully")
                else:
                    print("[export] Bullet formatting step failed — using un-bulleted DOCX")

        elif export_format == "pdf":
            temp_dir      = tempfile.mkdtemp()
            temp_docx     = os.path.join(temp_dir, "temp_formatted.docx")

            if has_images:
                success = create_docx_with_images(
                    parsed_lines, document_images, temp_docx, template_rules
                )
                if not success:
                    generate_docx(parsed_lines, temp_docx, template_rules=template_rules)
            else:
                generate_docx(parsed_lines, temp_docx, template_rules=template_rules)

            # Apply bullet formatting to temp DOCX before PDF conversion
            if apply_bullets and os.path.exists(temp_docx):
                bulleted_temp = os.path.join(temp_dir, "temp_bulleted.docx")
                ok = bullet_formatter.apply_bullet_formatting(
                    temp_docx, bulleted_temp, formatting_rules=template_rules
                )
                if ok and os.path.exists(bulleted_temp):
                    temp_docx = bulleted_temp
                    print("[export] Bullet formatting applied to PDF-source DOCX")

            conversion_success = False
            if docx2pdf_convert:
                try:
                    docx2pdf_convert(temp_docx, output_file)
                    conversion_success = True
                    print("PDF generated using docx2pdf")
                except Exception as e:
                    print(f"docx2pdf failed: {e}")

            if not conversion_success and LIBREOFFICE_AVAILABLE:
                try:
                    conversion_success = convert_docx_to_pdf_libreoffice(temp_docx, output_file)
                    if conversion_success:
                        print("PDF generated using LibreOffice")
                except Exception as e:
                    print(f"LibreOffice failed: {e}")

            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass

            if not conversion_success:
                raise HTTPException(
                    status_code=500,
                    detail="Could not convert to PDF. Ensure docx2pdf or LibreOffice is installed."
                )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

    if not os.path.exists(output_file):
        raise HTTPException(status_code=500, detail="Export failed: output file not created")

    media_types = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf":  "application/pdf",
        "txt":  "text/plain",
    }

    return FileResponse(
        path=output_file,
        filename=f"{base_filename}.{export_format}",
        media_type=media_types[export_format],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Original endpoint (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/document/{document_id}/original")
async def download_original_document(document_id: int, user_id: int = Query(...)):
    """Download the original document without any formatting"""
    try:
        conn = get_db()
        doc  = conn.execute(
            "SELECT file_path, filename, user_id FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()
        conn.close()

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        if doc["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized")
        if not os.path.exists(doc["file_path"]):
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(
            path=doc["file_path"],
            filename=doc["filename"],
            media_type="application/octet-stream"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))