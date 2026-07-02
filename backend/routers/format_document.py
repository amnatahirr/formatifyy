"""
routers/format_document.py
───────────────────────────
POST /api/format-document

Full pipeline:
  Layer 0 — ContentDetector   (detector.py)
  Layer 1 — HeadingClassifier (classifier.py)
  Layer 2 — SmartFormatter    (smart_formatter.py)

Also exposes:
  POST /api/format-document/from-file   — upload a .docx / .pdf / .txt
  GET  /api/format-document/preview/{template_id} — returns style spec only

Integration into main.py
────────────────────────
    from routers.format_document import router as format_router
    app.include_router(format_router)
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from database import get_db

# ── Internal services ─────────────────────────────────────────────────────────
from services.detector       import content_detector
from services.classifier     import heading_classifier
from services.smart_formatter import smart_formatter
from services.ai_element_classifier import ai_element_classifier, LABELS

# Layer-1 block extractor (already exists in your codebase)
from services.document_block_extractor import extract_blocks


router     = APIRouter(prefix="/api/format-document", tags=["Format Document"])
UPLOAD_DIR    = Path("uploads")
WORKING_DIR   = UPLOAD_DIR / "working"
FORMATTED_DIR = Path("formatted")
ALLOWED       = {".docx", ".pdf", ".txt"}

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
WORKING_DIR.mkdir(parents=True, exist_ok=True)
FORMATTED_DIR.mkdir(parents=True, exist_ok=True)


# ── Request / response models ─────────────────────────────────────────────────

class FormatTextRequest(BaseModel):
    """Body for the plain-text endpoint."""
    text:         str
    template_id:  Optional[int]  = None
    template_rules: Optional[Dict[str, Any]] = None  # pass rules directly (optional)


class FormatResponse(BaseModel):
    """Unified response shape."""
    source:             str           # "text" | "file"
    filename:           Optional[str] = None
    template_id:        Optional[int] = None
    total_elements:     int
    formatted_elements: List[Dict[str, Any]]
    summary: Dict[str, Any]


class DebugClassifyRequest(BaseModel):
    text: str
    labels: Optional[List[str]] = None
    threshold: Optional[float] = None


# ── Helper: run full pipeline ─────────────────────────────────────────────────

def _run_pipeline(
    blocks:         List[Dict[str, Any]],
    template_id:    Optional[int],
    template_rules: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Shared pipeline for both text and file inputs.

    1. Enrich blocks via ContentDetector.detect_blocks()
       (adds "type" / "confidence" to pre-parsed blocks, or classifies raw blocks)
    2. Refine heading levels via HeadingClassifier.classify()
    3. Apply template styles via SmartFormatter.format_blocks()
    """
    enriched   = content_detector.detect_blocks(blocks)
    classified = heading_classifier.classify(enriched)
    formatted  = smart_formatter.format_blocks(
        classified,
        template_id    = template_id,
        template_rules = template_rules,
    )
    return formatted


def _build_summary(elements: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Count block types for the response summary."""
    counts: Dict[str, int] = {}
    for el in elements:
        counts[el["type"]] = counts.get(el["type"], 0) + 1

    heading_levels: Dict[str, int] = {}
    for el in elements:
        if el["type"] == "heading" and el.get("level"):
            heading_levels[el["level"]] = heading_levels.get(el["level"], 0) + 1

    return {
        "block_counts":   counts,
        "heading_levels": heading_levels,
        "total":          len(elements),
    }


def build_formatted_elements_for_file(
    file_path: str,
    template_id: Optional[int] = None,
    template_rules: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Primary pipeline: parse blocks -> classify -> template styles."""
    raw_blocks = extract_blocks(file_path)
    return _run_pipeline(raw_blocks, template_id, template_rules)


def build_formatted_elements_for_document(
    document_id: int,
    user_id: Optional[int] = None,
) -> tuple[str, Optional[int], List[Dict[str, Any]]]:
    """Run pipeline on a persisted document id."""
    conn = get_db()
    row = conn.execute(
        "SELECT file_path, filename, template_id, user_id FROM documents WHERE id = ?",
        (document_id,),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    if user_id is not None and row["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    # Prefer working copy if fixes were applied
    working_copy = Path("uploads") / "working" / f"doc_{document_id}_working.docx"
    file_path = str(working_copy) if working_copy.exists() else row["file_path"]
    if not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="Document file not found")
    elements = build_formatted_elements_for_file(file_path, row["template_id"], None)
    return row["filename"], row["template_id"], elements


def export_elements_to_docx(elements: List[Dict[str, Any]], output_path: str) -> None:
    """Write formatted pipeline elements to .docx."""
    doc = Document()
    for el in elements:
        text = str(el.get("text", "")).strip()
        if not text:
            continue
        kind = el.get("type", "paragraph")
        style = el.get("style", {}) or {}

        if kind == "heading":
            level = int(str(el.get("level", "H1")).replace("H", "") or 1)
            para = doc.add_heading(text, level=max(1, min(4, level)))
        elif kind == "list_item":
            para = doc.add_paragraph(text, style="List Bullet")
        elif kind == "table":
            rows = [r.strip() for r in text.split("|") if r.strip()]
            if not rows:
                continue
            parsed_rows = [[c.strip() for c in r.split(",")] for r in rows]
            col_count = max(len(r) for r in parsed_rows)
            table = doc.add_table(rows=len(parsed_rows), cols=col_count)
            for r_idx, row in enumerate(parsed_rows):
                for c_idx, val in enumerate(row):
                    table.cell(r_idx, c_idx).text = val
            continue
        elif kind == "figure":
            para = doc.add_paragraph(f"[Figure] {text}")
        elif kind == "caption":
            para = doc.add_paragraph(text)
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif kind == "reference":
            para = doc.add_paragraph(text)
            para.paragraph_format.left_indent = Inches(0.25)
            para.paragraph_format.first_line_indent = Inches(-0.25)
        else:
            para = doc.add_paragraph(text)

        run = para.runs[0] if para.runs else para.add_run(text)
        if style.get("font_name"):
            run.font.name = style["font_name"]
        if style.get("font_size") is not None:
            run.font.size = Pt(float(style["font_size"]))
        run.font.bold = bool(style.get("bold", False))
        run.font.italic = bool(style.get("italic", False))
        run.font.underline = bool(style.get("underline", False))

        align = str(style.get("alignment", "")).lower()
        if align == "center":
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif align == "right":
            para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        elif align == "justify":
            para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.save(output_path)


# ── Endpoint 1: POST /api/format-document  (plain text) ──────────────────────

@router.post(
    "",
    summary="Format raw document text",
    response_model=FormatResponse,
)
async def format_document_text(body: FormatTextRequest) -> JSONResponse:
    """
    Accepts raw text, runs the full detection + classification + styling
    pipeline, and returns structured formatted elements.

    **Input**
    ```json
    {
        "text": "1. Introduction\\nThis project...",
        "template_id": 3
    }
    ```

    **Output**
    ```json
    {
        "formatted_elements": [
            {
                "index": 0,
                "type": "heading",
                "level": "H1",
                "text": "Introduction",
                "style": { "font_name": "Times New Roman", "font_size": 16, ... }
            },
            ...
        ]
    }
    ```
    """
    if not body.text or not body.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty.")

    # Convert plain text to lightweight block list that the pipeline expects
    raw_blocks = _text_to_raw_blocks(body.text)

    try:
        elements = _run_pipeline(raw_blocks, body.template_id, body.template_rules)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}")

    return JSONResponse(content={
        "source":             "text",
        "filename":           None,
        "template_id":        body.template_id,
        "total_elements":     len(elements),
        "formatted_elements": elements,
        "summary":            _build_summary(elements),
    })


# ── Endpoint 2: POST /api/format-document/from-file ──────────────────────────

@router.post(
    "/from-file",
    summary="Upload a document file and format it",
    response_model=FormatResponse,
)
async def format_document_file(
    file:        UploadFile = File(...),
    template_id: Optional[int] = Form(None),
) -> JSONResponse:
    """
    Upload a `.docx`, `.pdf`, or `.txt` file.
    Uses the existing `extract_blocks()` (Layer 1) so all content types
    (tables, images, etc.) are preserved in the output.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(ALLOWED)}",
        )

    temp_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    try:
        with temp_path.open("wb") as out:
            shutil.copyfileobj(file.file, out)

        # Layer 1: parse into typed blocks (heading / paragraph / table / image …)
        raw_blocks = extract_blocks(str(temp_path))

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"File parsing failed: {exc}")
    finally:
        if temp_path.exists():
            temp_path.unlink()

    try:
        elements = _run_pipeline(raw_blocks, template_id, None)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}")

    return JSONResponse(content={
        "source":             "file",
        "filename":           file.filename,
        "template_id":        template_id,
        "total_elements":     len(elements),
        "formatted_elements": elements,
        "summary":            _build_summary(elements),
    })


@router.get(
    "/from-document/{document_id}",
    summary="Run primary formatting pipeline for a saved document",
    response_model=FormatResponse,
)
async def format_saved_document(
    document_id: int,
    user_id: Optional[int] = Query(default=None),
) -> JSONResponse:
    filename, template_id, elements = build_formatted_elements_for_document(document_id, user_id)
    return JSONResponse(content={
        "source":             "file",
        "filename":           filename,
        "template_id":        template_id,
        "total_elements":     len(elements),
        "formatted_elements": elements,
        "summary":            _build_summary(elements),
    })


@router.get(
    "/export/{document_id}",
    summary="Export the formatted working copy as DOCX/PDF/TXT",
)
async def export_formatted_document(
    document_id: int,
    user_id: Optional[int] = Query(default=None),
    format: str = Query(default="docx"),
) -> FileResponse:
    import shutil as _shutil
    import subprocess
    try:
        print(f"[export] doc={document_id} user={user_id} format={format}")

        working_path = Path(f"uploads/working/doc_{document_id}_working.docx")

        if working_path.exists():
            source = working_path
        else:
            from database import get_db as _get_db
            db = _get_db()
            row = db.execute(
                "SELECT file_path FROM documents WHERE id=?", (document_id,)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Document not found")
            source = Path(row[0])

        if not source.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {source}")

        # ── DOCX (original behaviour) ──────────────────────────────────────
        if format == "docx":
            out_name = f"formatted_{document_id}_{uuid.uuid4().hex[:8]}.docx"
            out_path = FORMATTED_DIR / out_name
            _shutil.copy2(str(source), str(out_path))
            return FileResponse(
                path=str(out_path),
                filename=f"formatted_document_{document_id}.docx",
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

        # ── PDF ────────────────────────────────────────────────────────────
        elif format == "pdf":
            out_name = f"formatted_{document_id}_{uuid.uuid4().hex[:8]}.pdf"
            out_path = FORMATTED_DIR / out_name
            lo_binary = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
            if not Path(lo_binary).exists():
                raise HTTPException(status_code=500, detail="LibreOffice not found at /Applications/LibreOffice.app")
            # Requires LibreOffice installed on the server
            result = subprocess.run(
                [lo_binary, "--headless", "--convert-to", "pdf",
                 "--outdir", str(FORMATTED_DIR), str(source)],
                capture_output=True, timeout=60
            )
            # LibreOffice names the output after the source file
            lo_output = FORMATTED_DIR / (source.stem + ".pdf")
            if lo_output.exists():
                lo_output.rename(out_path)
            else:
                raise HTTPException(status_code=500, detail="PDF conversion failed")
            return FileResponse(
                path=str(out_path),
                filename=f"formatted_document_{document_id}.pdf",
                media_type="application/pdf",
            )

        # ── TXT ────────────────────────────────────────────────────────────
        elif format == "txt":
            from docx import Document as DocxDocument
            out_name = f"formatted_{document_id}_{uuid.uuid4().hex[:8]}.txt"
            out_path = FORMATTED_DIR / out_name
            doc = DocxDocument(str(source))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            out_path.write_text(text, encoding="utf-8")
            return FileResponse(
                path=str(out_path),
                filename=f"formatted_document_{document_id}.txt",
                media_type="text/plain",
            )

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Export failed: {e}")


@router.post(
    "/debug-classify",
    summary="Debug raw AI label + confidence for a text block",
)
async def debug_classify(body: DebugClassifyRequest) -> JSONResponse:
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text must not be empty.")
    labels = body.labels or LABELS
    result = ai_element_classifier.predict(
        text=text,
        labels=labels,
        threshold=body.threshold,
    )
    return JSONResponse(
        content={
            "text": text,
            "labels": labels,
            "model_available": ai_element_classifier._model_available,
            "prediction": result,
        }
    )


# ── Endpoint 3: GET /api/format-document/preview/{template_id} ───────────────

@router.get(
    "/preview/{template_id}",
    summary="Get the style spec for a template (no document needed)",
)
async def preview_template_styles(template_id: int) -> JSONResponse:
    """
    Returns the complete style dictionary for all block types as they
    would be formatted using the given template.  Useful for the Flutter
    preview screen to show font/colour choices before the user uploads.
    """
    # Use SmartFormatter to resolve rules, then build one sample element
    # of each type with those rules.
    sample_blocks = [
        {"index": 0, "type": "heading", "raw_text": "Sample H1 Heading",    "level": 1, "confidence": 1.0},
        {"index": 1, "type": "heading", "raw_text": "Sample H2 Sub-heading","level": 2, "confidence": 1.0},
        {"index": 2, "type": "heading", "raw_text": "Sample H3 Section",    "level": 3, "confidence": 1.0},
        {"index": 3, "type": "heading", "raw_text": "Sample H4 Sub-section","level": 4, "confidence": 1.0},
        {"index": 4, "type": "paragraph", "raw_text": "Sample body paragraph text.", "confidence": 1.0},
        {"index": 5, "type": "list_item","raw_text": "Sample list item",    "confidence": 1.0},
        {"index": 6, "type": "toc",      "raw_text": "Introduction .... 1", "confidence": 1.0},
        {"index": 7, "type": "formula",  "raw_text": "$E = mc^2$",          "confidence": 1.0},
        {"index": 8, "type": "figure",   "raw_text": "Figure 1",             "confidence": 1.0},
        {"index": 9, "type": "caption",  "raw_text": "Figure 1: Sample caption", "confidence": 1.0},
        {"index": 10, "type": "reference","raw_text": "[1] Author, Title, 2024.", "confidence": 1.0},
    ]

    try:
        elements = smart_formatter.format_blocks(sample_blocks, template_id=template_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return JSONResponse(content={
        "template_id": template_id,
        "style_preview": elements,
    })


# ── Helper: convert plain text → raw block list ───────────────────────────────

def _text_to_raw_blocks(text: str) -> List[Dict[str, Any]]:
    """
    Converts a raw text string into the minimal block-dict format that
    the pipeline expects.  Each non-empty line becomes one block;
    type is "paragraph" — detector.py will reclassify everything.
    """
    blocks = []
    for idx, line in enumerate(text.splitlines()):
        stripped = line.strip()
        if stripped:
            blocks.append({
                "index":    idx,
                "type":     "paragraph",   # detector will override
                "text":     stripped,
                "level":    None,
                "metadata": {},
            })
    return blocks