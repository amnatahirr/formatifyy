"""
qr_routes.py — QR endpoints for Formatify.

Mounted WITHOUT the /api prefix, matching the Flutter services:
  POST /qr/generate          JSON  {document_id, file_type, host}
                             -> QR that opens a phone download link
  GET  /qr/download/{token}  phone hits this after scanning (no login needed)

  POST /qr/upload/generate   form  user_id, template_id, host
                             -> QR that opens a phone upload page
  GET  /qr/upload/{token}    simple mobile upload page
  POST /qr/upload/{token}    receives the file, creates the document row
  GET  /qr/upload/status/{token}  Flutter polls this to get document_id

Requires:  pip install "qrcode[pil]"
"""

from __future__ import annotations

import base64
import datetime
import io
import os
import re
import secrets
import shutil
import time
from html import escape
from typing import Any, Dict, Optional

import qrcode
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from database import get_db
from template_logic.templates import get_template_by_id

import tempfile
from starlette.background import BackgroundTask
from crypto_utils import read_file_bytes

router = APIRouter(tags=["QR"])

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
ALLOWED_UPLOAD_EXTS = {".docx", ".pdf", ".txt"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
TOKEN_TTL_SECONDS = 15 * 60

_HOST_RE = re.compile(r"^[A-Za-z0-9.\-]+(:\d{1,5})?$")

# token -> session data (in memory; cleared on server restart)
_download_tokens: Dict[str, Dict[str, Any]] = {}
_upload_tokens: Dict[str, Dict[str, Any]] = {}


# ── helpers ──────────────────────────────────────────────────────────────────

def _purge_expired() -> None:
    now = time.time()
    for store in (_download_tokens, _upload_tokens):
        for tok in [t for t, d in store.items() if d["expires"] < now]:
            store.pop(tok, None)


def _clean_host(host: Optional[str], request: Request) -> str:
    h = (host or "").strip()
    if not h or not _HOST_RE.match(h):
        h = request.url.netloc
    return h


def _qr_base64(url: str) -> str:
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _get_doc(document_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
    row = cur.fetchone()
    conn.close()
    return row


def _best_docx_for_document(doc) -> Optional[str]:
    """Most up-to-date formatted DOCX we have for this document."""
    doc_id = doc["id"]
    candidates = []
    try:
        candidates.append(doc["formatted_file_path"])
    except (KeyError, IndexError, TypeError):
        pass
    candidates += [
        os.path.join(OUTPUT_DIR, f"export_{doc_id}.docx"),
        os.path.join(UPLOAD_DIR, "working", f"doc_{doc_id}_working.docx"),
        os.path.join(UPLOAD_DIR, "formatted", f"doc_{doc_id}_formatted.docx"),
    ]
    for p in candidates:
        if p and os.path.exists(str(p)):
            return str(p)
    return None


# ── 1) Download QR ───────────────────────────────────────────────────────────

class QRGenerateRequest(BaseModel):
    document_id: int
    file_type: str = "pdf"
    host: Optional[str] = None


@router.post("/qr/generate")
async def qr_generate(payload: QRGenerateRequest, request: Request):
    file_type = (payload.file_type or "pdf").strip().lower()
    if file_type not in ("pdf", "docx"):
        raise HTTPException(status_code=400, detail="file_type must be 'pdf' or 'docx'.")

    doc = _get_doc(payload.document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    if not _best_docx_for_document(doc) and not (
        doc["file_path"] and os.path.exists(doc["file_path"])
    ):
        raise HTTPException(status_code=404, detail="No file available for this document.")

    _purge_expired()
    token = secrets.token_urlsafe(16)
    _download_tokens[token] = {
        "document_id": payload.document_id,
        "file_type": file_type,
        "expires": time.time() + TOKEN_TTL_SECONDS,
    }

    host = _clean_host(payload.host, request)
    url = f"http://{host}/qr/download/{token}"
    return {
        "qr_base64": _qr_base64(url),
        "url": url,
        "token": token,
        "expires_in": TOKEN_TTL_SECONDS,
    }


def _rm(*paths) -> None:
    for p in paths:
        if not p:
            continue
        try:
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            elif os.path.exists(p):
                os.remove(p)
        except OSError:
            pass


@router.get("/qr/download/{token}")
async def qr_download(token: str):
    _purge_expired()
    data = _download_tokens.get(token)
    if not data:
        raise HTTPException(status_code=404, detail="Link expired or invalid.")

    doc = _get_doc(data["document_id"])
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    stem = os.path.splitext(doc["filename"] or "document")[0]
    docx_path = _best_docx_for_document(doc)

    # Decrypt into a temp folder (works for encrypted and old plaintext files)
    work = None
    if docx_path:
        work = tempfile.mkdtemp(prefix="qr_")
        plain = os.path.join(work, os.path.basename(docx_path))
        try:
            with open(plain, "wb") as fh:
                fh.write(read_file_bytes(docx_path))
        except Exception:
            _rm(work)
            raise
        docx_path = plain

    if data["file_type"] == "pdf":
        from docx_tools.reformatter import convert_docx_to_pdf

        source = docx_path or doc["file_path"]
        generated_pdf = None
        try:
            if source and source.lower().endswith(".pdf"):
                pdf_path = source
            else:
                pdf_path = convert_docx_to_pdf(source) if source else None
                generated_pdf = pdf_path
        except Exception:
            _rm(work)
            raise
        if not pdf_path or not os.path.exists(pdf_path):
            _rm(work, generated_pdf)
            raise HTTPException(status_code=500, detail="Could not create PDF.")
        return FileResponse(
            pdf_path,
            filename=f"formatted_{stem}.pdf",
            media_type="application/pdf",
            background=BackgroundTask(_rm, work, generated_pdf),
        )

    if not docx_path:
        raise HTTPException(status_code=404, detail="No DOCX available for this document.")
    return FileResponse(
        docx_path,
        filename=f"formatted_{stem}.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        background=BackgroundTask(_rm, work),
    )

# ── 2) Upload QR ─────────────────────────────────────────────────────────────

@router.post("/qr/upload/generate")
async def qr_upload_generate(
    request: Request,
    user_id: int = Form(...),
    template_id: int = Form(...),
    host: Optional[str] = Form(None),
):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, org_id FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    org_id = user["org_id"] if user["org_id"] is not None else 1
    if not get_template_by_id(template_id, org_id=int(org_id)):
        raise HTTPException(status_code=400, detail="Template not found.")

    _purge_expired()
    token = secrets.token_urlsafe(16)
    _upload_tokens[token] = {
        "user_id": user_id,
        "template_id": template_id,
        "document_id": None,
        "filename": None,
        "expires": time.time() + TOKEN_TTL_SECONDS,
    }

    h = _clean_host(host, request)
    url = f"http://{h}/qr/upload/{token}"
    return {
        "qr_base64": _qr_base64(url),
        "url": url,
        "token": token,
        "expires_in": TOKEN_TTL_SECONDS,
    }


_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Formatify Upload</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:24px;background:#f5f6fa;color:#222}}
.card{{max-width:420px;margin:40px auto;background:#fff;border-radius:14px;padding:24px;box-shadow:0 2px 12px rgba(0,0,0,.08)}}
h2{{margin-top:0}} input[type=file]{{width:100%;margin:16px 0}}
button{{width:100%;padding:14px;border:0;border-radius:10px;background:#4f46e5;color:#fff;font-size:16px}}
.ok{{color:#15803d}} .err{{color:#b91c1c}}
</style></head><body><div class="card">{body}</div></body></html>"""


@router.get("/qr/upload/status/{token}")
async def qr_upload_status(token: str):
    data = _upload_tokens.get(token)
    if not data:
        raise HTTPException(status_code=404, detail="Session expired or invalid.")
    return {
        "uploaded": data["document_id"] is not None,
        "document_id": data["document_id"],
        "filename": data["filename"],
    }


@router.get("/qr/upload/{token}", response_class=HTMLResponse)
async def qr_upload_page(token: str):
    _purge_expired()
    if token not in _upload_tokens:
        return HTMLResponse(
            _PAGE.format(body='<h2 class="err">Link expired</h2><p>Generate a new QR code in the app.</p>'),
            status_code=404,
        )
    body = (
        "<h2>Upload your document</h2>"
        "<p>Choose a .docx, .pdf or .txt file.</p>"
        f'<form method="post" action="/qr/upload/{escape(token)}" enctype="multipart/form-data">'
        '<input type="file" name="file" accept=".docx,.pdf,.txt" required>'
        "<button type=\"submit\">Upload</button></form>"
    )
    return HTMLResponse(_PAGE.format(body=body))


@router.post("/qr/upload/{token}", response_class=HTMLResponse)
async def qr_upload_receive(token: str, file: UploadFile = File(...)):
    _purge_expired()
    data = _upload_tokens.get(token)
    if not data:
        return HTMLResponse(
            _PAGE.format(body='<h2 class="err">Link expired</h2>'), status_code=404
        )
    if data["document_id"] is not None:
        return HTMLResponse(
            _PAGE.format(body='<h2 class="ok">Already uploaded ✓</h2><p>Return to the app.</p>')
        )

    original_name = os.path.basename(file.filename or "upload")
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTS:
        return HTMLResponse(
            _PAGE.format(body=f'<h2 class="err">Unsupported file type</h2><p>{escape(ext or "unknown")}</p>'),
            status_code=400,
        )

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", original_name)
    file_path = os.path.join(UPLOAD_DIR, f"{stamp}_{safe_name}")
    with open(file_path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)

    if os.path.getsize(file_path) > MAX_UPLOAD_BYTES:
        os.remove(file_path)
        return HTMLResponse(
            _PAGE.format(body='<h2 class="err">File too large (max 25 MB)</h2>'),
            status_code=400,
        )

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO documents (user_id, template_id, filename, file_path, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (data["user_id"], data["template_id"], original_name, file_path, "pending"),
    )
    conn.commit()
    doc_id = cur.lastrowid
    conn.close()

    data["document_id"] = doc_id
    data["filename"] = original_name
    return HTMLResponse(
        _PAGE.format(
            body='<h2 class="ok">Uploaded ✓</h2><p>You can close this page and return to the app.</p>'
        )
    )