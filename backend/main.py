"""
main.py — FastAPI application for Formatify (Dynamic Template Edition).

Base URL served:   http://localhost:8000
/api prefix routes:
  Auth:
    POST /api/auth/signup      → register a new student account
    POST /api/auth/login       → login and return user profile
    GET  /api/auth/google/debug/tokens   → mock Google auth debug stub

  Templates (public):
    GET  /api/templates                         → all templates (global)
    GET  /api/templates/user/{user_id}          → templates for user's university
    GET  /api/templates/university/{univ_id}    → templates for a specific university

  Admin template management:
    POST   /api/admin/templates               → create a new template
    DELETE /api/admin/templates/{template_id} → delete a template

  Analysis pipeline:
    POST /api/analyze          → full document analysis
    GET  /api/download/{job_id} → download reformatted document

  Health:
    GET  /api/health           → {"status": "ok"}
    GET  /health               → alias (no prefix) for quick checks
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
import random
import re
import shutil
import uuid
from typing import Any, Dict, List, Optional

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from aggregator import aggregate
from batcher import create_batches
from database import get_db, hash_password, init_db, verify_password

from dispatcher import dispatch_all
from models import AnalysisReport, UserLoginRequest, UserSignupRequest, TemplateCreateRequest
from parser import parse_file, parse_text
from reformatter import reformat_document
from templates import (
    get_all_templates,
    get_template_by_id,
    get_templates_by_university,
    get_templates_by_user,
)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

load_dotenv()
from config import ANALYSIS_MODEL

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
ALLOWED_EXTENSIONS = {".docx", ".pdf", ".txt"}

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Ensure database tables and seed data exist on startup
init_db()

# ═══════════════════════════════════════════════════════════════════════════════
# APP
# ═══════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="FORMATIFY API",
    version="3.0.0",
    description="AI-powered document quality checker — dynamic template edition",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store: job_id → {report, output_path, filename}
_jobs: Dict[str, Dict] = {}


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _user_row_to_dict(row) -> Dict[str, Any]:
    """Convert a sqlite3 Row (users table) to a safe dict for API responses."""
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "role": row["role"],
        "university_id": row["university_id"],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health():
    """Health check — confirms server is running."""
    return {"status": "ok", "version": "3.0.0"}


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/auth/signup", tags=["Auth"])
async def signup(payload: UserSignupRequest):
    """
    Register a new student account.
    Returns: user profile dict on success.
    """
    conn = get_db()
    cursor = conn.cursor()

    # Check email uniqueness
    cursor.execute("SELECT id FROM users WHERE email = ?", (payload.email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail="Email is already registered.")

    # Check username uniqueness
    cursor.execute("SELECT id FROM users WHERE username = ?", (payload.username,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail="Username is already taken.")

    # Validate university
    university_id = payload.university_id or 1
    cursor.execute("SELECT id FROM universities WHERE id = ?", (university_id,))
    if not cursor.fetchone():
        university_id = 1  # Fall back to default

    pw_hash = hash_password(payload.password)
    cursor.execute(
        """
        INSERT INTO users (username, email, password_hash, role, university_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (payload.username, payload.email, pw_hash, "student", university_id),
    )
    conn.commit()
    new_id = cursor.lastrowid

    cursor.execute("SELECT * FROM users WHERE id = ?", (new_id,))
    user = cursor.fetchone()
    conn.close()

    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "university_id": user["university_id"],
        "message": "User registered successfully."
    }


@app.post("/api/auth/login", tags=["Auth"])
async def login(payload: UserLoginRequest):
    """
    Login with email + password.
    Returns: user profile dict on success, 401 on failure.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (payload.email,))
    user = cursor.fetchone()
    conn.close()

    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "university_id": user["university_id"],
        "message": "Login successful."
    }



@app.get("/api/auth/google/debug/tokens", tags=["Auth"])
async def google_debug_tokens():
    """
    Stub endpoint — returns mock Google OAuth token status for debug builds.
    The Flutter frontend calls this to detect Google Auth availability.
    """
    return {
        "google_auth_available": False,
        "message": "Google OAuth is not configured on this server.",
        "fallback": "email_password"
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPLATE ENDPOINTS (public — read only)
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/templates", tags=["Templates"])
async def list_all_templates():
    """Return all formatting templates from the database."""
    return get_all_templates()


# Alias without /api prefix so existing Flutter calls still work
@app.get("/templates", tags=["Templates"])
async def list_templates_alias():
    return get_all_templates()


@app.get("/api/templates/user/{user_id}", tags=["Templates"])
async def list_templates_for_user(user_id: int):
    """Return templates configured for the user's university."""
    templates = get_templates_by_user(user_id)
    if templates is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return templates


@app.get("/api/templates/university/{university_id}", tags=["Templates"])
async def list_templates_for_university(university_id: int):
    """Return all templates configured for a specific university."""
    return get_templates_by_university(university_id)


@app.get("/api/templates/{template_id}", tags=["Templates"])
async def get_template(template_id: int):
    """Return a single template by ID."""
    tmpl = get_template_by_id(template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found.")
    return tmpl


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN TEMPLATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/admin/templates", tags=["Admin"])
async def create_template(payload: TemplateCreateRequest, created_by: int = 1, university_id: int = 1):
    """
    Admin: create a new formatting template.
    Query params: created_by (user_id of admin), university_id.
    """
    conn = get_db()
    cursor = conn.cursor()

    # Validate university
    cursor.execute("SELECT id FROM universities WHERE id = ?", (university_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="University not found.")

    # Validate admin user
    cursor.execute("SELECT id, role FROM users WHERE id = ?", (created_by,))
    admin = cursor.fetchone()
    if not admin:
        conn.close()
        raise HTTPException(status_code=404, detail="Admin user not found.")

    cursor.execute(
        """
        INSERT INTO templates (university_id, name, required_sections, formatting_rules, created_by)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            university_id,
            payload.name,
            json.dumps(payload.required_sections),
            json.dumps(payload.formatting_rules),
            created_by,
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    tmpl = get_template_by_id(new_id)
    return {"success": True, "template": tmpl}


@app.delete("/api/admin/templates/{template_id}", tags=["Admin"])
async def delete_template(template_id: int, user_id: int = 1):
    """
    Admin: delete a formatting template by ID.
    Prevents deletion of the 3 built-in templates (id 1, 2, 3).
    """
    if template_id in (1, 2, 3):
        raise HTTPException(
            status_code=403,
            detail="Built-in templates cannot be deleted. Add a new template or modify existing ones."
        )

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM templates WHERE id = ?", (template_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Template not found.")

    cursor.execute("DELETE FROM templates WHERE id = ?", (template_id,))
    conn.commit()
    conn.close()

    return {"success": True, "deleted_id": template_id}


# ═══════════════════════════════════════════════════════════════════════════════
# ANALYSIS PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

async def _run_analysis(
    template_id: str,
    saved_path: Optional[str],
    text: Optional[str],
    filename: str,
    job_id: str,
):
    """
    Shared helper: ingest → batch → dispatch → aggregate → reformat.
    Stores result in _jobs[job_id] and returns the response dict.
    """
    if not ANTHROPIC_API_KEY and not GEMINI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Neither ANTHROPIC_API_KEY nor GEMINI_API_KEY is configured. Set one in backend/.env.",
        )

    tmpl = get_template_by_id(template_id)
    if not tmpl:
        raise HTTPException(status_code=400, detail=f"Unknown template: {template_id}")

    # ── Step 1: Ingest ────────────────────────────────────────────────────────
    try:
        if saved_path:
            norm_filename = filename
            if not os.path.splitext(norm_filename)[1]:
                norm_filename = os.path.basename(saved_path)
            doc_model = parse_file(saved_path, norm_filename)
        else:
            doc_model = parse_text(text or "", title="pasted_text.txt")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse document: {exc}")


    # ── Step 2: Batch ─────────────────────────────────────────────────────────
    batches = create_batches(doc_model)

    # ── Step 3+4: Dispatch + Aggregate ────────────────────────────────────────
    if GEMINI_API_KEY:
        from gemini_adapter import GeminiClientAdapter
        client = GeminiClientAdapter(api_key=GEMINI_API_KEY)
    else:
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    # Pass the full markdown rules string to the LLM agents
    raw_issues = await dispatch_all(client, batches, tmpl["markdown_rules"])
    report = aggregate(raw_issues, doc_model, total_batches=len(batches))

    # ── Step 5: Reformat ──────────────────────────────────────────────────────
    output_filename = f"formatted_{job_id}.docx"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    try:
        source_path = saved_path
        if not source_path:
            # For pasted text create a temporary .txt file
            tmp_txt = os.path.join(UPLOAD_DIR, f"{job_id}_pasted.txt")
            with open(tmp_txt, "w", encoding="utf-8") as f:
                f.write(text or "")
            source_path = tmp_txt

        # Pass the dict formatting_rules directly for precise control
        reformat_document(source_path, output_path, report, tmpl["formatting_rules"])
    except Exception as exc:
        print(f"[main] reformatter error (non-fatal): {exc}")
        output_path = ""

    # ── Store job ─────────────────────────────────────────────────────────────
    _jobs[job_id] = {
        "report": report,
        "output_path": output_path,
        "filename": filename,
    }

    response = report.model_dump()
    response["job_id"] = job_id
    return response


@app.post("/api/analyze", tags=["Analysis"])
async def analyze_api(
    template: str = Form(...),
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
):
    """
    Full document analysis pipeline (prefixed route for Flutter frontend).
    Accepts a file upload (DOCX/PDF/TXT) or pasted text, plus a template ID.
    """
    if file is None and not text:
        raise HTTPException(
            status_code=400,
            detail="Either a file or text content must be provided.",
        )

    job_id = str(uuid.uuid4())
    saved_path: str | None = None
    filename = "pasted_text.txt"

    if file is not None:
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format: {ext}. Accepted: {', '.join(ALLOWED_EXTENSIONS)}",
            )
        filename = file.filename or f"upload{ext}"
        saved_path = os.path.join(UPLOAD_DIR, f"{job_id}_{filename}")
        with open(saved_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

    return await _run_analysis(template, saved_path, text, filename, job_id)


# Keep the un-prefixed route as a fallback alias
@app.post("/analyze", tags=["Analysis"])
async def analyze_no_prefix(
    template: str = Form(...),
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
):
    """Alias for /api/analyze — kept for backward compatibility."""
    return await analyze_api(template=template, file=file, text=text)


# ═══════════════════════════════════════════════════════════════════════════════
# DOWNLOAD
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/download/{job_id}", tags=["Analysis"])
@app.get("/download/{job_id}", tags=["Analysis"])
async def download(job_id: str):
    """Download the reformatted DOCX for a completed analysis job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired.")

    output_path = job.get("output_path", "")
    if not output_path or not os.path.exists(output_path):
        raise HTTPException(
            status_code=404,
            detail="Formatted document is not available for this job.",
        )

    original = job.get("filename", "document.docx")
    download_name = f"formatted_{os.path.splitext(original)[0]}.docx"

    return FileResponse(
        path=output_path,
        filename=download_name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DOCUMENT MANIPULATION & BULLET HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _detect_missing_bullet_issues(docx_path: str) -> list:
    """
    Search docx for paragraphs that look like bullet lists but missing w:numPr.
    """
    try:
        from docx import Document as DocxDoc
        from docx.oxml.ns import qn
        docx = DocxDoc(docx_path)
        
        # Build paragraph blocks
        blocks = []
        for idx, p in enumerate(docx.paragraphs):
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
            blocks.append({
                "index": idx,
                "type": btype,
                "text": text,
                "style": style_name
            })
            
        bullet_groups = []
        current_group = []
        import re
        
        bullet_pattern = re.compile(r"^[•*○■▪\-–→»*]|\(?\d+[.)]|\(?[A-Za-z][.)]")
        
        for block in blocks:
            btype = block["type"]
            text = block["text"]
            if btype == "heading":
                if current_group:
                    bullet_groups.append(current_group)
                    current_group = []
                continue
                
            is_bullet_like = bullet_pattern.match(text) is not None or "list" in block["style"]
            
            if is_bullet_like:
                current_group.append(block)
            else:
                if current_group:
                    bullet_groups.append(current_group)
                    current_group = []
                    
        if current_group:
            bullet_groups.append(current_group)
            
        issues = []
        for group in bullet_groups:
            para_indices = [g["index"] for g in group]
            preview_items = [g["text"][:60] for g in group[:3]]
            
            issues.append({
                "type": "missing_bullets",
                "code": "MISSING_BULLETS",
                "severity": "WARNING",
                "message": f"List items starting with '{preview_items[0]}' appear to be missing formal Word bullet styling.",
                "heading": "List formatting",
                "para_indices": para_indices,
                "preview_items": preview_items,
                "fix_type": "apply_section_bullets",
                "fix_details": {"para_indices": para_indices}
            })
        return issues
    except Exception as exc:
        print("[BulletCheck] error:", exc)
        return []


def apply_section_bullets_to_file(docx_path: str, para_indices: list[int]):
    from docx import Document as DocxDoc
    from docx.oxml import OxmlElement as _OE
    from docx.oxml.ns import qn
    import random
    
    docx = DocxDoc(docx_path)
    paras = docx.paragraphs
    
    _W2 = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    from copy import deepcopy as _dc2
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
            _np = _OE("w:p")
            if _pPr is not None:
                _np.append(_dc2(_pPr))
            _nr = _OE("w:r")
            _rp = next((rp for rp, _ in _frags if rp is not None), None)
            if _rp is not None:
                _nr.append(_dc2(_rp))
            _nt = _OE("w:t")
            _nt.text = _lt
            _nt.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            _nr.append(_nt); _np.append(_nr)
            _new_ps.append(_np)
        for _off, _np in enumerate(_new_ps):
            _parent.insert(_pos + _off, _np)
        _parent.remove(_p_el)
        
    paras = docx.paragraphs
    
    try:
        num_part = docx.part.numbering_part.numbering_definitions._numbering
        abstract_id = len(num_part.findall(qn('w:abstractNum')))
        num_id = len(num_part.findall(qn('w:num'))) + 1
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
        
    nsid_val = ''.join(random.choices('0123456789ABCDEF', k=8))
    tmpl_val = ''.join(random.choices('0123456789ABCDEF', k=8))

    abstractNum = _OE('w:abstractNum')
    abstractNum.set(qn('w:abstractNumId'), str(abstract_id))
    nsid = _OE('w:nsid'); nsid.set(qn('w:val'), nsid_val)
    ml   = _OE('w:multiLevelType'); ml.set(qn('w:val'), 'singleLevel')
    tmpl = _OE('w:tmpl'); tmpl.set(qn('w:val'), tmpl_val)
    abstractNum.extend([nsid, ml, tmpl])

    lvl    = _OE('w:lvl');     lvl.set(qn('w:ilvl'), '0')
    start  = _OE('w:start');   start.set(qn('w:val'), '1')
    nFmt   = _OE('w:numFmt');  nFmt.set(qn('w:val'), 'bullet')
    lvlTxt = _OE('w:lvlText'); lvlTxt.set(qn('w:val'), '•')
    lvlJc  = _OE('w:lvlJc');   lvlJc.set(qn('w:val'), 'left')
    pPr_abs = _OE('w:pPr')
    tabs    = _OE('w:tabs'); tab = _OE('w:tab')
    tab.set(qn('w:val'), 'num'); tab.set(qn('w:pos'), '360')
    tabs.append(tab); pPr_abs.append(tabs)
    ind = _OE('w:ind'); ind.set(qn('w:left'), '360'); ind.set(qn('w:hanging'), '180')
    pPr_abs.append(ind)
    lvl.extend([start, nFmt, lvlTxt, lvlJc, pPr_abs])
    abstractNum.append(lvl)

    first_num_e = num_part.find(qn('w:num'))
    if first_num_e is not None:
        first_num_e.addprevious(abstractNum)
    else:
        num_part.append(abstractNum)

    num_elem = _OE('w:num'); num_elem.set(qn('w:numId'), str(num_id))
    an = _OE('w:abstractNumId'); an.set(qn('w:val'), str(abstract_id))
    num_elem.append(an); num_part.append(num_elem)

    applied = []
    skipped = []
    import re
    _LEADING_MARKER = re.compile(r'^\s*(?:[•○■▪\-–→»*]|\(?\d+[.)]|\(?[A-Za-z][.)]|\(?[ivxlcdmIVXLCDM]+[.)])\s+')
    
    for idx in para_indices:
        if idx < 0 or idx >= len(paras):
            skipped.append(idx)
            continue
        p = paras[idx]
        if not p.text.strip():
            skipped.append(idx)
            continue
            
        if p.runs:
            p.runs[0].text = _LEADING_MARKER.sub("", p.runs[0].text or "", count=1)
        else:
            p.text = _LEADING_MARKER.sub("", p.text or "", count=1)
            
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


# ═══════════════════════════════════════════════════════════════════════════════
# DOCUMENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/documents/", tags=["Documents"])
def list_documents(user_id: int):
    """List all documents for the specific user."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT d.id, d.filename, d.status, d.created_at, d.template_id,
               d.file_path, t.name as template_name
        FROM documents d
        LEFT JOIN templates t ON d.template_id = t.id
        WHERE d.user_id = ?
        ORDER BY d.created_at DESC
        """,
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        file_size = 0.0
        if r["file_path"] and os.path.exists(r["file_path"]):
            file_size = os.path.getsize(r["file_path"]) / 1024.0
            
        result.append({
            "id": r["id"],
            "filename": r["filename"],
            "status": r["status"],
            "created_at": r["created_at"],
            "template_id": r["template_id"],
            "template_name": r["template_name"] or "None",
            "file_size": round(file_size, 2)
        })
    return result


@app.post("/api/documents/upload", tags=["Documents"])
async def upload_document(
    file: UploadFile = File(...),
    template_id: int = Query(...),
    user_id: int = Query(...),
):
    """Upload a document file and record in SQLite."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    stored_filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, stored_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO documents (user_id, template_id, filename, file_path, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, template_id, file.filename, file_path, "pending")
    )
    conn.commit()
    doc_id = cursor.lastrowid
    conn.close()
    
    return {
        "document_id": doc_id,
        "filename": file.filename,
        "status": "pending"
    }


@app.post("/api/documents/upload-text", tags=["Documents"])
async def upload_text(
    payload: Dict[str, Any] = Body(...),
    template_id: int = Query(...),
    user_id: int = Query(...),
):
    """Save raw pasted text content as a .txt document and record in SQLite."""
    content = payload.get("content", "")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    stored_filename = f"{timestamp}_pasted_content.txt"
    file_path = os.path.join(UPLOAD_DIR, stored_filename)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO documents (user_id, template_id, filename, file_path, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, template_id, "Pasted Content", file_path, "pending")
    )
    conn.commit()
    doc_id = cursor.lastrowid
    conn.close()
    
    return {
        "document_id": doc_id,
        "filename": "Pasted Content",
        "status": "pending"
    }


@app.delete("/api/documents/{document_id}", tags=["Documents"])
def delete_document(document_id: int, user_id: int = Query(...)):
    """Delete a document record and its physical files."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT file_path FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
    doc = cursor.fetchone()
    if not doc:
        conn.close()
        raise HTTPException(status_code=404, detail="Document not found")
        
    file_path = doc["file_path"]
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass
            
    working_copy = os.path.join(UPLOAD_DIR, "working", f"doc_{document_id}_working.docx")
    if os.path.exists(working_copy):
        try:
            os.remove(working_copy)
        except Exception:
            pass
            
    cursor.execute("DELETE FROM documents WHERE id = ?", (document_id,))
    conn.commit()
    conn.close()
    return {"success": True}


@app.get("/api/documents/analyze/{document_id}", tags=["Documents"])
async def analyze_document_endpoint(document_id: int, user_id: int = Query(...)):
    """Analyze a document using parallel AI agents and return detailed reports."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
    doc = cursor.fetchone()
    conn.close()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    working_copy = os.path.join(UPLOAD_DIR, "working", f"doc_{document_id}_working.docx")
    file_path = working_copy if os.path.exists(working_copy) else doc["file_path"]
    
    job_id = str(document_id)
    report_dict = await _run_analysis(
        template_id=str(doc["template_id"]),
        saved_path=file_path,
        text=None,
        filename=doc["filename"],
        job_id=job_id
    )
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE documents SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (document_id,))
    conn.commit()
    conn.close()
    
    paragraphs = []
    try:
        if file_path.endswith(".docx"):
            from docx import Document as DocxDoc
            paragraphs = [p.text for p in DocxDoc(file_path).paragraphs]
        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                paragraphs = f.read().splitlines()
    except Exception:
        pass
        
    content_issues = []
    style_issues = []
    
    for issue in report_dict.get("issues", []):
        func = issue.get("function", "").lower()
        if func in ("grammar", "para_relevance", "plagiarism"):
            content_issues.append(issue)
        else:
            style_issues.append(issue)
            
    if file_path.endswith(".docx"):
        bullets = _detect_missing_bullet_issues(file_path)
        style_issues.extend(bullets)
        
    critical_count = len([i for i in report_dict.get("issues", []) if i.get("severity") == "CRITICAL"])
    warning_count = len([i for i in report_dict.get("issues", []) if i.get("severity") == "WARNING"])
    total_issues = len(report_dict.get("issues", [])) + len(content_issues) + len(style_issues)
    
    score = report_dict.get("stats", {}).get("avg_formatting_compliance", 100.0)
    if score is None:
        score = 100.0
        
    return {
        "document_id": document_id,
        "filename": doc["filename"],
        "document_content": paragraphs,
        "issues": report_dict.get("issues", []),
        "content_issues": content_issues,
        "style_issues": style_issues,
        "structure": {
            "score": score,
            "sections": [],
            "issues": []
        },
        "content_checker_mode": "ensemble_with_learning",
        "content_checker_version": "perfect",
        "template_heading_matches": [],
        "compliance_score": score,
        "total_issues": total_issues,
        "critical_issues": critical_count,
        "warning_issues": warning_count
    }


@app.get("/api/documents/analyze-bullets/{document_id}", tags=["Documents"])
async def analyze_bullets_in_document(document_id: int, user_id: int = Query(...)):
    """Perform bullet list consistency checks."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
    doc = cursor.fetchone()
    conn.close()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    working_copy = os.path.join(UPLOAD_DIR, "working", f"doc_{document_id}_working.docx")
    file_path = working_copy if os.path.exists(working_copy) else doc["file_path"]
    
    if not file_path.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only DOCX files support bullet analysis.")
        
    from docx import Document as DocxDoc
    try:
        docx = DocxDoc(file_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to open DOCX: {exc}")
        
    import re
    bullet_pattern = re.compile(r"^[•*○■▪\-–→»*]|\(?\d+[.)]|\(?[A-Za-z][.)]")
    
    detected_bullets = []
    bullet_groups = []
    current_group = []
    
    for idx, p in enumerate(docx.paragraphs):
        text = p.text.strip()
        if not text:
            continue
        style_name = (p.style.name or "").lower()
        is_heading = "heading" in style_name
        is_bullet_like = bullet_pattern.match(text) is not None or "list" in style_name
        
        if is_heading:
            if current_group:
                bullet_groups.append(current_group)
                current_group = []
            continue
            
        if is_bullet_like:
            item = {
                "text": text,
                "index": idx,
                "confidence": 0.9,
                "reason": "Starts with list indicator or list style name"
            }
            detected_bullets.append(item)
            current_group.append(item)
        else:
            if current_group:
                bullet_groups.append(current_group)
                current_group = []
                
    if current_group:
        bullet_groups.append(current_group)
        
    return {
        "document_id": document_id,
        "filename": doc["filename"],
        "total_paragraphs": len(docx.paragraphs),
        "detected_bullets": detected_bullets,
        "bullet_groups": bullet_groups,
        "summary": {
            "total_detected": len(detected_bullets),
            "high_confidence": len([d for d in detected_bullets if d["confidence"] > 0.8]),
            "medium_confidence": len([d for d in detected_bullets if 0.6 < d["confidence"] <= 0.8]),
            "low_confidence": len([d for d in detected_bullets if d["confidence"] <= 0.6]),
            "total_groups": len(bullet_groups)
        }
    }


@app.get("/api/format-document/from-document/{document_id}", tags=["Documents"])
async def preview_document(document_id: int, user_id: int = Query(...)):
    """Return list of formatted elements (text + paragraph/heading type) for previewing."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
    doc = cursor.fetchone()
    conn.close()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    working_copy = os.path.join(UPLOAD_DIR, "working", f"doc_{document_id}_working.docx")
    file_path = working_copy if os.path.exists(working_copy) else doc["file_path"]
    
    elements = []
    try:
        if file_path.endswith(".docx"):
            from docx import Document as DocxDoc
            docx = DocxDoc(file_path)
            for idx, p in enumerate(docx.paragraphs):
                text = p.text.strip()
                if not text:
                    continue
                style_name = (p.style.name or "").lower()
                btype = "heading" if "heading" in style_name else "paragraph"
                elements.append({
                    "text": p.text,
                    "type": btype
                })
        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.read().splitlines()
                for line in lines:
                    if line.strip():
                        elements.append({
                            "text": line,
                            "type": "paragraph"
                        })
    except Exception:
        pass
        
    return {
        "formatted_elements": elements,
        "summary": {
            "total_elements": len(elements),
            "applied_rules": {}
        }
    }


@app.get("/api/format-document/export/{document_id}", tags=["Documents"])
def export_formatted_document(document_id: int, user_id: int = Query(...)):
    """Export and download a fully reformatted DOCX version of the saved document."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
    doc = cursor.fetchone()
    conn.close()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    tmpl = get_template_by_id(doc["template_id"])
    if not tmpl:
        raise HTTPException(status_code=400, detail="Document has no valid template assigned.")
        
    working_copy = os.path.join(UPLOAD_DIR, "working", f"doc_{document_id}_working.docx")
    file_path = working_copy if os.path.exists(working_copy) else doc["file_path"]
    
    output_filename = f"export_{document_id}.docx"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    
    from models import AnalysisReport
    report = AnalysisReport(issues=[], stats={})
    
    reformat_document(file_path, output_path, report, tmpl["formatting_rules"])
    
    download_name = f"formatted_{doc['filename']}"
    if not download_name.endswith(".docx"):
        download_name += ".docx"
        
    return FileResponse(
        path=output_path,
        filename=download_name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


@app.post("/api/documents/apply-all-style-fixes/{document_id}", tags=["Documents"])
def apply_all_style_fixes(document_id: int, user_id: int = Query(...)):
    """Save design modifications from templates directly into the working document file."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
    doc = cursor.fetchone()
    conn.close()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    tmpl = get_template_by_id(doc["template_id"])
    if not tmpl:
        raise HTTPException(status_code=400, detail="Template not found")
        
    working_dir = os.path.join(UPLOAD_DIR, "working")
    os.makedirs(working_dir, exist_ok=True)
    working_copy = os.path.join(working_dir, f"doc_{document_id}_working.docx")
    
    file_path = doc["file_path"]
    from models import AnalysisReport
    report = AnalysisReport(issues=[], stats={})
    
    reformat_document(file_path, working_copy, report, tmpl["formatting_rules"])
    
    return {"status": "success", "message": "All style fixes applied to working copy"}


@app.post("/api/documents/apply-fix/{document_id}", tags=["Documents"])
async def apply_fix(
    document_id: int,
    user_id: int = Query(...),
    fix_type: str = Query("apply_section_bullets"),
    payload: Dict[str, Any] = Body(...)
):
    """Apply selective list design styling options."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
    doc = cursor.fetchone()
    conn.close()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    working_dir = os.path.join(UPLOAD_DIR, "working")
    os.makedirs(working_dir, exist_ok=True)
    working_copy = os.path.join(working_dir, f"doc_{document_id}_working.docx")
    
    if not os.path.exists(working_copy):
        shutil.copy2(doc["file_path"], working_copy)
        
    para_indices = payload.get("para_indices", [])
    if not para_indices and "para_index" in payload:
        para_indices = [payload["para_index"]]
        
    if fix_type == "apply_section_bullets":
        applied, skipped = apply_section_bullets_to_file(working_copy, para_indices)
        return {"status": "success", "applied": applied, "skipped": skipped}
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported fix_type: {fix_type}")


# ═══════════════════════════════════════════════════════════════════════════════
# UNIVERSITY ENDPOINTS (read-only)
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/universities", tags=["Universities"])
async def list_universities():
    """Return all registered universities."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM universities ORDER BY name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/universities/{university_id}", tags=["Universities"])
async def get_university(university_id: int):
    """Return a single university record."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM universities WHERE id = ?", (university_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="University not found.")
    return dict(row)


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)