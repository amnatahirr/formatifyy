"""
main.py — FastAPI application for Formatify (Dynamic Template Edition).

Base URL served:   http://localhost:8000
/api prefix routes:
  Auth:
    POST /api/auth/signup      → register a new student account
    POST /api/auth/login       → login and return user profile
    GET  /api/auth/me          → validate restored session by user_id
    GET  /api/auth/departments → public department list for signup
    GET  /api/auth/google/authorize      → start Google Drive OAuth
    GET  /api/auth/google/callback       → OAuth redirect handler
    GET  /api/auth/google/status         → poll OAuth completion
    GET  /api/auth/google/debug/tokens   → check stored Drive tokens
    GET  /api/uploads/google-drive/files → list Drive files
    POST /api/uploads/google-drive/import
    POST /api/uploads/download-from-google-drive

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
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Query, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from aggregator import aggregate
from admin_routes import router as admin_router
from supervisor_routes import router as supervisor_router
from student_routes import router as student_router
from batcher import create_batches
from database import get_db, hash_password, init_db, verify_password
from middleware.org_middleware import (
    resolve_organization_from_request,
    resolve_org_id_for_user_action,
    lookup_organization,
    public_org_payload,
)
from auth_jwt import create_access_token


def _resolve_org_for_auth(org_code: str | None, request: Request) -> dict:
    """Login/signup: prefer explicit org_code body field over headers."""
    code = (org_code or "").strip().upper()
    if code:
        org = lookup_organization(org_code=code)
        if (org.get("code") or "").upper() != code:
            raise HTTPException(status_code=404, detail="Organization code not found.")
        if not org.get("is_active", True):
            raise HTTPException(status_code=403, detail="Organization is inactive.")
        return org
    return resolve_organization_from_request(request)

from dispatcher import dispatch_all, dispatch_freeform
from models import AnalysisReport, UserLoginRequest, UserSignupRequest, TemplateCreateRequest, TemplateUpdateRequest, ChangePasswordRequest
from parser import parse_file, parse_text
from reformatter import reformat_document, convert_docx_to_pdf
from issue_utils import (
    build_document_blocks,
    normalize_issues,
    save_document_images,
)
from image_formatter import format_document_images, fix_image_captions
from services.image_formatting_service import run_image_formatting_pipeline
from services.table_formatting_service import run_table_formatting_pipeline
from services.image_config import DEFAULT_IMAGE_FORMAT_RULES
from services.table_config import (
    DEFAULT_TABLE_FORMAT_RULES,
    normalize_formatting_rules_table_section,
    validate_table_format_rules,
)
from docx_fields import (
    analyze_document_lists,
    apply_toc_heading_styles,
    collect_headings,
    document_has_toc,
    generate_document_lists,
    insert_lof_field,
    insert_lot_field,
    insert_toc_field,
)
from table_processor import (
    detect_tables,
    format_tables_in_document,
    fill_table_cell,
    normalize_table_fonts,
)
from content_fixer import (
    apply_text_fix,
    apply_all_text_fixes,
    apply_heading_fix,
    apply_template_reformat,
    demote_heading_to_body,
    renumber_heading_prefixes,
    _is_instruction_suggestion,
)
from heading_analysis import (
    analyze_document_headings,
    analyze_document_headings_with_claude,
    analyze_headings,
    blocks_from_dicts,
    enrich_matches_with_fix_status,
    heading_matches_to_issues,
)
from templates import (
    delete_template as delete_template_record,
    get_all_templates,
    get_freeform_placeholder_template_id,
    get_template_by_id,
    get_templates_by_university,
    get_templates_by_user,
    update_template,
)
from vc.routes import router as vc_router, set_analysis_runner
from vc.reports_sync import sync_analysis_to_project_members

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

# Load backend/.env even if the process cwd is the repo root
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
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

# Multi-tenancy: resolve org (default id=1) + gate FYP routes only
from middleware.org_middleware import OrganizationMiddleware, get_organization
from template_sample_preview import router as template_sample_router
app.include_router(template_sample_router)
app.add_middleware(OrganizationMiddleware)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
from qr_routes import router as qr_router
app.include_router(qr_router)
# In-memory job store: job_id → {report, output_path, filename}
_jobs: Dict[str, Dict] = {}


@app.on_event("startup")
async def _preload_local_vision_models() -> None:
    """Warm BLIP + CLIP so the first analyze request doesn't download/load mid-flight."""
    def _warm() -> None:
        try:
            from functions.local_vision import preload_models
            preload_models()
        except Exception as exc:
            print(f"[startup] Vision model preload skipped: {exc}")

    # Run in a thread so startup HTTP isn't blocked longer than needed
    await asyncio.to_thread(_warm)


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


@app.get("/api/plagiarism/corpus-status", tags=["Plagiarism"])
async def plagiarism_corpus_status(rebuild: bool = Query(False)):
    """
    Report whether the local FYP plagiarism corpus is ready.

    Query ``rebuild=true`` to force a MinHash/FAISS rebuild (slow for ~210 reports).
    """
    from plagiarism import config as plag_config
    from plagiarism.pipeline import corpus_plagiarism_enabled, get_or_build_corpus_index
    from plagiarism.text_extract import iter_corpus_files

    corpus_dir = plag_config.CORPUS_DIR
    files = iter_corpus_files(corpus_dir)
    payload = {
        "enabled": corpus_plagiarism_enabled(),
        "corpus_dir": str(corpus_dir),
        "index_dir": str(plag_config.INDEX_CACHE_DIR),
        "files_on_disk": len(files),
        "ready": False,
        "document_count": 0,
        "sentence_count": 0,
        "error": None,
    }
    if not files:
        payload["error"] = (
            "No corpus files found. Copy FYP reports into "
            "backend/plagiarism/fyp_reports_raw/ and run "
            "`python -m plagiarism.ingest_corpus --rebuild-index`."
        )
        return payload
    try:
        index = get_or_build_corpus_index(force_rebuild=rebuild)
        payload["ready"] = True
        payload["document_count"] = index.size
        payload["sentence_count"] = index.sentence_count
    except Exception as exc:
        payload["error"] = str(exc)
    return payload


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/auth/signup", tags=["Auth"])
async def signup(payload: UserSignupRequest, request: Request):
    """
    Register a new student account for an organization (org_code in body).
    Returns profile + JWT access_token.
    """
    org = _resolve_org_for_auth(payload.org_code, request)
    org_id = int(org["id"])
    plan = (org.get("plan") or "university").lower()
    org_type = (org.get("type") or "university").lower()
    modules = [
        m.strip()
        for m in (org.get("modules") or "core").split(",")
        if m.strip()
    ]
    has_fyp = "fyp" in modules
    # Semester is an FYP field — only university tenants with the fyp module.
    is_university_org = (
        has_fyp
        and org_type != "company"
        and plan not in ("starter", "enterprise")
        and (plan == "university" or org_type == "university")
    )
    # University FYP signup needs semester 6/7; starter/company skip it.
    if is_university_org:
        if payload.current_semester not in (6, 7):
            raise HTTPException(
                status_code=400,
                detail="current_semester must be 6 or 7.",
            )
    elif payload.current_semester is not None and payload.current_semester not in (6, 7):
        raise HTTPException(
            status_code=400,
            detail="current_semester must be 6 or 7 when provided.",
        )

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM users WHERE LOWER(email) = LOWER(?) AND org_id = ?",
        (payload.email, org_id),
    )
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail="Email is already registered.")

    cursor.execute(
        "SELECT id FROM users WHERE LOWER(username) = LOWER(?) AND org_id = ?",
        (payload.username, org_id),
    )
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail="Username is already taken.")

    cursor.execute(
        "SELECT id FROM departments WHERE id = ? AND org_id = ?",
        (payload.department_id, org_id),
    )
    if not cursor.fetchone():
        # fallback if org_id column missing on very old DBs
        cursor.execute("PRAGMA table_info(departments)")
        cols = {r[1] for r in cursor.fetchall()}
        if "org_id" in cols:
            conn.close()
            raise HTTPException(status_code=400, detail="Invalid department_id.")
        cursor.execute("SELECT id FROM departments WHERE id = ?", (payload.department_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="Invalid department_id.")

    university_id = payload.university_id or 1
    cursor.execute("SELECT id FROM universities WHERE id = ?", (university_id,))
    if not cursor.fetchone():
        university_id = 1

    pw_hash = hash_password(payload.password)
    cursor.execute(
        """
        INSERT INTO users (
            username, email, password_hash, role, university_id,
            department_id, current_semester, org_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.username,
            payload.email,
            pw_hash,
            "student",
            university_id,
            payload.department_id,
            payload.current_semester,
            org_id,
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid
    cursor.execute("SELECT * FROM users WHERE id = ?", (new_id,))
    user = cursor.fetchone()
    conn.close()

    token = create_access_token(
        user_id=int(user["id"]),
        org_id=org_id,
        role=user["role"],
        email=user["email"],
        org_code=org.get("code") or "",
    )
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "university_id": user["university_id"],
        "department_id": user["department_id"],
        "current_semester": user["current_semester"],
        "org_id": org_id,
        "org_code": org.get("code"),
        "access_token": token,
        "token_type": "bearer",
        "message": "User registered successfully.",
    }


@app.get("/api/auth/departments", tags=["Auth"])
async def list_signup_departments(
    request: Request,
    org_code: str | None = Query(default=None),
):
    """
    Public department list for student signup (org_code query — no JWT yet).
    """
    org = _resolve_org_for_auth(org_code, request)
    org_id = int(org["id"])
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(departments)")
    dept_cols = {row[1] for row in cursor.fetchall()}
    if "org_id" in dept_cols:
        cursor.execute(
            """
            SELECT id, name, code
            FROM departments
            WHERE org_id = ?
            ORDER BY name ASC
            """,
            (org_id,),
        )
    else:
        cursor.execute(
            """
            SELECT id, name, code
            FROM departments
            ORDER BY name ASC
            """
        )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"departments": rows, "count": len(rows), "org_code": org.get("code")}


@app.post("/api/auth/login", tags=["Auth"])
async def login(payload: UserLoginRequest, request: Request):
    """
    Login with org_code + email + password.
    Returns profile + JWT (org_id, user_id, role encoded).
    """
    org = _resolve_org_for_auth(payload.org_code, request)
    org_id = int(org["id"])

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM users WHERE LOWER(email) = LOWER(?) AND org_id = ?",
        (payload.email, org_id),
    )
    user = cursor.fetchone()
    conn.close()

    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_access_token(
        user_id=int(user["id"]),
        org_id=org_id,
        role=user["role"],
        email=user["email"],
        org_code=org.get("code") or "",
    )
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "university_id": user["university_id"],
        "org_id": org_id,
        "org_code": org.get("code"),
        "access_token": token,
        "token_type": "bearer",
        "message": "Login successful.",
    }


@app.get("/api/auth/me", tags=["Auth"])
async def get_current_user(request: Request, user_id: int = Query(...)):
    """
    Validate a restored client session (no JWT in this app — callers pass user_id).
    Returns the same profile shape as login when the user still exists.
    """
    org_id = int(resolve_organization_from_request(request)["id"])
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, email, role, university_id, org_id FROM users WHERE id = ?",
        (user_id,),
    )
    user = cursor.fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="Session invalid or user not found.")

    user_org = int(user["org_id"]) if "org_id" in user.keys() and user["org_id"] is not None else 1
    if user_org != org_id:
        raise HTTPException(status_code=403, detail="User does not belong to this organization.")

    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "university_id": user["university_id"],
        "org_id": user_org,
    }


@app.post("/api/auth/change-password", tags=["Auth"])
async def change_password(payload: ChangePasswordRequest, request: Request):
    """Change password for the logged-in user."""
    if len(payload.new_password.strip()) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters.")

    org_id = int(resolve_organization_from_request(request)["id"])
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (payload.user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")

    user_org = int(user["org_id"]) if "org_id" in user.keys() and user["org_id"] is not None else 1
    if user_org != org_id:
        conn.close()
        raise HTTPException(status_code=403, detail="User does not belong to this organization.")

    if not verify_password(payload.current_password, user["password_hash"]):
        conn.close()
        raise HTTPException(status_code=401, detail="Current password is incorrect.")

    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (hash_password(payload.new_password.strip()), payload.user_id),
    )
    conn.commit()
    conn.close()
    return {"success": True, "message": "Password updated successfully."}


# Google Drive token debug lives on google_drive_routes (auth_router).


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPLATE ENDPOINTS (public — read only)
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/templates", tags=["Templates"])
async def list_all_templates(request: Request):
    """Return all formatting templates from the database for the current org."""
    org_id = int(resolve_organization_from_request(request)["id"])
    return get_all_templates(org_id=org_id)


# Alias without /api prefix so existing Flutter calls still work
@app.get("/templates", tags=["Templates"])
async def list_templates_alias(request: Request):
    org_id = int(resolve_organization_from_request(request)["id"])
    return get_all_templates(org_id=org_id)


@app.get("/api/templates/user/{user_id}", tags=["Templates"])
async def list_templates_for_user(user_id: int):
    """Return templates configured for the user's university and org."""
    templates = get_templates_by_user(user_id)
    if templates is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return templates


@app.get("/api/templates/university/{university_id}", tags=["Templates"])
async def list_templates_for_university(university_id: int, request: Request):
    """Return all templates configured for a specific university in this org."""
    org_id = int(resolve_organization_from_request(request)["id"])
    return get_templates_by_university(university_id, org_id=org_id)


@app.get("/api/templates/{template_id}", tags=["Templates"])
async def get_template(template_id: int, request: Request):
    """Return a single template by ID (org-scoped)."""
    org_id = int(resolve_organization_from_request(request)["id"])
    tmpl = get_template_by_id(template_id, org_id=org_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found.")
    return tmpl


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN TEMPLATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/admin/templates", tags=["Admin"])
async def create_template(
    payload: TemplateCreateRequest,
    request: Request,
    created_by: int | None = None,
    user_id: int | None = None,
    university_id: int = 1,
    department_id: int | None = None,
):
    """
    Admin: create a new formatting template.
    Query params: created_by / user_id (admin), university_id, department_id.
    """
    admin_id = created_by or user_id or 1
    org_id = resolve_org_id_for_user_action(request, admin_id)
    conn = get_db()
    cursor = conn.cursor()

    # Validate university
    cursor.execute("SELECT id FROM universities WHERE id = ?", (university_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="University not found.")

    # Validate admin user
    cursor.execute(
        "SELECT id, role, org_id FROM users WHERE id = ? AND org_id = ?",
        (admin_id, org_id),
    )
    admin = cursor.fetchone()
    if not admin:
        conn.close()
        raise HTTPException(status_code=404, detail="Admin user not found.")

    if department_id is not None:
        cursor.execute(
            "SELECT id FROM departments WHERE id = ? AND org_id = ?",
            (department_id, org_id),
        )
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(
                status_code=400,
                detail="Department not found in your organization.",
            )

    formatting_rules = _normalize_template_formatting_rules(payload.formatting_rules)

    cursor.execute(
        """
        INSERT INTO templates
            (university_id, department_id, name, description, required_sections,
             formatting_rules, created_by, org_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            university_id,
            department_id,
            payload.name,
            payload.description or "",
            json.dumps(payload.required_sections),
            json.dumps(formatting_rules),
            admin_id,
            org_id,
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    tmpl = get_template_by_id(new_id, org_id=org_id)
    return {"success": True, "template": tmpl}


@app.put("/api/admin/templates/{template_id}", tags=["Admin"])
async def edit_template(
    template_id: int,
    payload: TemplateUpdateRequest,
    request: Request,
    user_id: int = 1,
    department_id: int | None = None,
):
    """Admin: update an existing formatting template."""
    org_id = resolve_org_id_for_user_action(request, user_id)
    updates = payload.model_dump(exclude_unset=True)
    if department_id is not None:
        updates["department_id"] = department_id
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")

    if "formatting_rules" in updates and updates["formatting_rules"] is not None:
        updates["formatting_rules"] = _normalize_template_formatting_rules(
            updates["formatting_rules"]
        )

    tmpl = update_template(template_id, updates, org_id=org_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found.")

    return {"success": True, "template": tmpl}


@app.delete("/api/admin/templates/{template_id}", tags=["Admin"])
async def delete_template(template_id: int, request: Request, user_id: int = 1):
    """
    Admin: delete a formatting template by ID.
    Prevents deletion of the 3 built-in templates (id 1, 2, 3).
    """
    if template_id in (1, 2, 3):
        raise HTTPException(
            status_code=403,
            detail="Built-in templates cannot be deleted. Add a new template or modify existing ones."
        )

    org_id = resolve_org_id_for_user_action(request, user_id)
    if not delete_template_record(template_id, org_id=org_id):
        raise HTTPException(status_code=404, detail="Template not found.")

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
            norm_filename = _filename_for_parse(saved_path, filename)
            doc_model = parse_file(saved_path, norm_filename)
        else:
            doc_model = parse_text(text or "", title="pasted_text.txt")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse document: {exc}")

    # Skip cover / info / TOC / LOF / LOT (list of images) pages for scoring.
    # Reformat still uses the original file path below — front-matter untouched.
    try:
        from review_blocks import strip_frontmatter_from_document
        doc_model = strip_frontmatter_from_document(doc_model)
    except Exception as exc:
        print(f"[analysis] frontmatter skip failed (non-fatal): {exc}")

    # ── Step 2: Batch ─────────────────────────────────────────────────────────
    batches = create_batches(doc_model)

    # ── Step 3+4: Dispatch + Aggregate ────────────────────────────────────────
    if GEMINI_API_KEY:
        from gemini_adapter import GeminiClientAdapter
        client = GeminiClientAdapter(api_key=GEMINI_API_KEY)
    else:
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    # Pass the full template dict so formatting gets required_sections +
    # structured rules (not just the markdown string).
    # Corpus plagiarism runs once on the full document (parallel with batch checks).
    from plagiarism.pipeline import check_document_against_fyp_corpus

    dispatch_task = asyncio.create_task(dispatch_all(client, batches, tmpl))
    corpus_task = asyncio.create_task(
        check_document_against_fyp_corpus(doc_model, document_id=job_id)
    )
    raw_issues, corpus_issues = await asyncio.gather(dispatch_task, corpus_task)
    if corpus_issues:
        raw_issues.extend(corpus_issues)
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
        reformat_document(
            source_path, output_path, report,
            tmpl["formatting_rules"], tmpl.get("required_sections", []),
        )
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


set_analysis_runner(_run_analysis)
app.include_router(vc_router)
app.include_router(admin_router)
app.include_router(supervisor_router)
app.include_router(student_router)

# Additive: draft-template extraction from prose guideline DOCX (does not alter create/update)
from template_extract_routes import router as template_extract_router
app.include_router(template_extract_router)

# Frontmatter: cover / project-info detect + generate
from frontmatter_routes import router as frontmatter_router
app.include_router(frontmatter_router)

# Super Admin — manage organizations (X-Super-Admin-Key)
from super_admin_routes import router as super_admin_router
app.include_router(super_admin_router)

# Google Drive OAuth + import (auth + uploads)
from services.google_drive_routes import auth_router as google_auth_router
from services.google_drive_routes import uploads_router as google_uploads_router
app.include_router(google_auth_router)
app.include_router(google_uploads_router)

# Voice-enabled template patch (Whisper STT → GPT-4o-mini → JSON patch)
from voice_template import router as voice_template_router
app.include_router(voice_template_router)


@app.get("/api/org/resolve", tags=["Organization"])
@app.get("/org/resolve", tags=["Organization"])
async def org_resolve(code: str = Query(..., min_length=1)):
    """
    Public login gate: look up org by code.
    Never returns api_key — clients only need org_code (+ later JWT).
    """
    code_clean = code.strip().upper()
    org = lookup_organization(org_code=code_clean)
    if (org.get("code") or "").upper() != code_clean:
        raise HTTPException(status_code=404, detail="Organization code not found.")
    if not org.get("is_active", True):
        raise HTTPException(status_code=403, detail="Organization is inactive.")
    return public_org_payload(org)


@app.get("/api/org/info", tags=["Organization"])
@app.get("/org/info", tags=["Organization"])
async def org_info(request: Request):
    """
    Org profile for feature flags / branding.
    Prefer Authorization: Bearer <jwt> after login.
    """
    org = await get_organization(request)
    return public_org_payload(org)


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
# WORKING DOCUMENT — formatted copy that accumulates all applied fixes
# ═══════════════════════════════════════════════════════════════════════════════

def _working_copy_path(document_id: int) -> str:
    return os.path.join(UPLOAD_DIR, "working", f"doc_{document_id}_working.docx")


_FIXABLE_SOURCE_EXTS = {".docx", ".pdf", ".txt"}


def _source_ext(path: str) -> str:
    return os.path.splitext(str(path or ""))[1].lower()


def _is_fixable_source(path: str) -> bool:
    """True when we can build a DOCX working copy (DOCX / PDF / TXT)."""
    return _source_ext(path) in _FIXABLE_SOURCE_EXTS


def _filename_for_parse(path: str, display_name: Optional[str] = None) -> str:
    """
    Stem from the user-facing name, extension from the real file on disk.
    Prevents parse_file from treating a .docx working copy as PDF because
    documents.filename still ends in .pdf.
    """
    ext = _source_ext(path) or ".docx"
    stem = os.path.splitext(display_name or os.path.basename(path) or "document")[0]
    stem = stem.strip() or "document"
    return f"{stem}{ext}"


def _heading_decisions_path(document_id: int) -> str:
    return os.path.join(UPLOAD_DIR, "working", f"doc_{document_id}_heading_decisions.json")


def _load_heading_decisions(document_id: int) -> Dict[str, str]:
    path = _heading_decisions_path(document_id)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            decisions = data.get("decisions", data)
            if isinstance(decisions, dict):
                return {
                    str(k): str(v).lower()
                    for k, v in decisions.items()
                    if str(v).lower() in ("keep", "discard")
                }
    except Exception as exc:
        print(f"[heading_decisions] load error (non-fatal): {exc}")
    return {}


def _save_heading_decision(document_id: int, paragraph_id: str, decision: str) -> Dict[str, str]:
    decisions = _load_heading_decisions(document_id)
    decisions[str(paragraph_id)] = decision
    path = _heading_decisions_path(document_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"decisions": decisions}, f, indent=2)
    return decisions


def _export_copy_path(document_id: int) -> str:
    return os.path.join(OUTPUT_DIR, f"export_{document_id}.docx")


def _saved_formatted_path(document_id: int) -> str:
    """Durable on-disk path for a student-saved formatted DOCX (My Reports)."""
    return os.path.join(UPLOAD_DIR, "formatted", f"doc_{document_id}_formatted.docx")


def _prepare_formatted_docx(doc: Any, document_id: int) -> str:
    """
    Build / refresh the export DOCX from the working copy (same source Export uses).

    Returns the path to ``outputs/export_{id}.docx``. Does not mutate the original
    upload at ``documents.file_path``.
    """
    working_copy = _working_copy_path(document_id)
    output_path = _export_copy_path(document_id)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    tmpl = None
    try:
        tmpl = get_template_by_id(doc["template_id"])
    except Exception:
        tmpl = None

    if os.path.exists(working_copy):
        shutil.copy2(working_copy, output_path)
    elif tmpl and _is_fixable_source(doc["file_path"]):
        report = AnalysisReport(issues=[], stats={})
        reformat_document(
            doc["file_path"],
            output_path,
            report,
            tmpl["formatting_rules"],
            tmpl.get("required_sections", []),
        )
        os.makedirs(os.path.dirname(working_copy), exist_ok=True)
        shutil.copy2(output_path, working_copy)
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                "No formatted document is available yet. "
                "Run Analysis first, then try again."
            ),
        )

    # Prepend admin cover / project-info templates when those pages are missing
    try:
        from frontmatter_apply import ensure_frontmatter_pages
        fm = ensure_frontmatter_pages(document_id, working_copy)
        if fm.get("applied"):
            shutil.copy2(working_copy, output_path)
            print(f"[formatted] frontmatter applied for doc {document_id}: {fm}")
    except Exception as exc:
        print(f"[formatted] frontmatter apply error (non-fatal): {exc}")

    if not os.path.exists(output_path):
        raise HTTPException(
            status_code=500,
            detail="Failed to prepare the formatted document.",
        )
    return output_path


def _guess_media_type(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext == ".pdf":
        return "application/pdf"
    if ext == ".txt":
        return "text/plain"
    if ext == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if ext == ".doc":
        return "application/msword"
    return "application/octet-stream"


def _ensure_formatted_working_copy(
    doc: Any,
    tmpl: Dict[str, Any],
    *,
    force_rebuild: bool = False,
) -> str:
    """
    Return the working DOCX path, creating it from the original upload if needed.

    Accepts DOCX, PDF, and TXT uploads. PDF/TXT are converted into a DOCX
    working copy (same path as DOCX uploads) so apply-all / heading / bullet
    fixes can run.

    Rebuilds when missing, when force_rebuild=True, or when the original upload
    is newer than the working copy (so Analysis sees the latest upload, not a
    stale pre-fixed working file).
    """
    original = str(doc["file_path"] or "")
    if not _is_fixable_source(original):
        raise HTTPException(
            status_code=400,
            detail=(
                "Working fixes require a DOCX, PDF, or TXT document "
                f"(got {_source_ext(original) or 'unknown'})."
            ),
        )

    working_copy = _working_copy_path(doc["id"])
    os.makedirs(os.path.dirname(working_copy), exist_ok=True)

    needs_rebuild = force_rebuild or not os.path.exists(working_copy)
    if (
        not needs_rebuild
        and original
        and os.path.exists(original)
        and os.path.exists(working_copy)
    ):
        try:
            # Rebuild when upload is newer (re-upload / replace without new doc id,
            # or analyze after a fresher source file landed).
            if os.path.getmtime(original) > os.path.getmtime(working_copy) + 1.0:
                needs_rebuild = True
                print(
                    f"[working_copy] original newer than working — rebuilding "
                    f"doc={doc['id']}"
                )
        except OSError:
            pass

    if needs_rebuild:
        if os.path.exists(working_copy):
            try:
                os.remove(working_copy)
            except OSError as exc:
                print(f"[working_copy] could not remove stale copy: {exc}")
        report = AnalysisReport(issues=[], stats={})
        reformat_document(
            original,
            working_copy,
            report,
            tmpl["formatting_rules"],
            tmpl.get("required_sections", []),
        )
        print(
            f"[working_copy] built doc={doc['id']} "
            f"from {_source_ext(original)} → docx"
        )
        try:
            from frontmatter_apply import clear_frontmatter_marker, ensure_frontmatter_pages
            clear_frontmatter_marker(int(doc["id"]))
            ensure_frontmatter_pages(int(doc["id"]), working_copy)
        except Exception as exc:
            print(f"[working_copy] frontmatter apply skipped: {exc}")
    else:
        # Existing copies: collapse duplicate page breaks + strip empty body gaps.
        try:
            from docx import Document as DocxDoc
            from docx_fields import _collapse_consecutive_page_breaks
            from reformatter import remove_empty_body_paragraph_gaps

            d = DocxDoc(working_copy)
            removed = _collapse_consecutive_page_breaks(d)
            removed_gaps = remove_empty_body_paragraph_gaps(d)
            if removed or removed_gaps:
                d.save(working_copy)
                print(
                    f"[working_copy] cleaned doc={doc['id']}: "
                    f"page_breaks={removed}, empty_gaps={removed_gaps}"
                )
        except Exception as exc:
            print(f"[working_copy] cleanup skipped: {exc}")
    return working_copy


def _commit_working_document(document_id: int, working_copy: str, doc: Any) -> Dict[str, Any]:
    """Sync export file and rebuild preview blocks from the working document."""
    export_path = _export_copy_path(document_id)
    shutil.copy2(working_copy, export_path)

    document_blocks: List[Dict[str, Any]] = []
    try:
        norm_filename = _filename_for_parse(working_copy, doc["filename"])
        doc_model = parse_file(working_copy, norm_filename)
        image_paths = save_document_images(doc_model, document_id, UPLOAD_DIR)
        document_blocks = build_document_blocks(doc_model, image_paths)
    except Exception as exc:
        print(f"[commit_working] preview refresh error: {exc}")

    try:
        sync_analysis_to_project_members(document_id, working_copy)
    except Exception as exc:
        print(f"[commit_working] project sync error (non-fatal): {exc}")

    return {
        "document_blocks": document_blocks,
        "export_path": export_path,
        "working_copy": working_copy,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DOCUMENT MANIPULATION & BULLET HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _detect_missing_bullet_issues(docx_path: str) -> list:
    """
    Search docx for paragraphs that look like bullet lists but missing w:numPr.

    Uses the deterministic list_detection pre-pass:
      a) Label: description
      b) Parallel infinitive / gerund / marker openings
      c) Trigger lines ("are:", "include:", "as follows:")
    Plus Abstract-section short-line heuristic as a fallback.
    """
    try:
        from docx import Document as DocxDoc
        from docx.oxml.ns import qn
        from list_detection import detect_list_groups, list_groups_to_issues
        from review_blocks import frontmatter_text_set

        docx = DocxDoc(docx_path)
        fm_texts = frontmatter_text_set(docx_path)

        blocks = []
        for idx, p in enumerate(docx.paragraphs):
            text = p.text.strip()
            if not text:
                continue
            # Do not flag cover / TOC / list-of-* pages as missing bullets
            if text in fm_texts:
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
                "style": style_name,
                "has_numpr": has_numpr,
                "paragraph_id": f"p{idx}",
            })

        groups = detect_list_groups(blocks)
        issues = list_groups_to_issues(groups, issue_prefix="missing_bullets")

        # Keep only the grouped missing_bullets issues for the apply-fix UI
        # (list_formatting per-item variants are useful for LLM path).
        grouped = [i for i in issues if i.get("type") == "missing_bullets"]

        # Implicit lists under Abstract (short consecutive lines) — supplemental
        import re
        label_pattern = re.compile(r"^[A-Z][A-Za-z0-9\s/&()-]{1,50}:")
        in_abstract = False
        abstract_group: list = []
        covered = {idx for g in groups for idx in g.indices}

        def _flush_abstract():
            nonlocal abstract_group
            if len(abstract_group) >= 2:
                para_indices = [g["index"] for g in abstract_group]
                if any(i in covered for i in para_indices):
                    abstract_group = []
                    return
                preview_items = [g["text"][:60] for g in abstract_group[:3]]
                first_idx = para_indices[0]
                grouped.append({
                    "issue_id": f"missing_bullets_abstract_{first_idx}",
                    "paragraph_id": f"p{first_idx}",
                    "function": "formatting",
                    "category": "Formatting",
                    "type": "missing_bullets",
                    "code": "MISSING_BULLETS",
                    "severity": "minor",
                    "reason": f"List items starting with '{preview_items[0]}' need Word bullet styling.",
                    "description": f"List items starting with '{preview_items[0]}' appear to be missing formal Word bullet styling.",
                    "message": f"List items starting with '{preview_items[0]}' appear to be missing formal Word bullet styling.",
                    "heading": "List formatting",
                    "para_indices": para_indices,
                    "para_index": first_idx,
                    "preview_items": preview_items,
                    "suggestion": "Apply Word bullet list formatting",
                    "fix_type": "apply_section_bullets",
                    "fix_details": {"para_indices": para_indices},
                    "source": "list_detection_prepass",
                    "list_detection": "abstract_short_lines",
                })
            abstract_group = []

        for block in blocks:
            if block["type"] == "heading" and "abstract" in block["text"].lower():
                _flush_abstract()
                in_abstract = True
                continue
            if in_abstract:
                if block["type"] == "heading":
                    _flush_abstract()
                    in_abstract = False
                    continue
                text = block["text"]
                if (
                    block["type"] == "paragraph"
                    and not block["has_numpr"]
                    and 3 <= len(text.split()) <= 30
                    and not text.endswith(".")
                ) or label_pattern.match(text):
                    abstract_group.append(block)
                else:
                    _flush_abstract()
        _flush_abstract()

        print(
            f"[BulletCheck] detected {len(grouped)} list group(s) "
            f"via deterministic pre-pass"
        )
        return grouped
    except Exception as exc:
        print("[BulletCheck] error:", exc)
        return []


def apply_section_bullets_to_file(docx_path: str, para_indices: list[int]):
    from docx import Document as DocxDoc
    from docx.oxml import OxmlElement as _OE
    from docx.oxml.ns import qn
    import random
    from list_detection import is_heading_paragraph
    
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
                # Copy paragraph props but never inherit outline/list numbering
                _pPr_copy = _dc2(_pPr)
                for _bad in list(_pPr_copy.findall(qn("w:numPr"))):
                    _pPr_copy.remove(_bad)
                _np.append(_pPr_copy)
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
    _LEADING_MARKER = re.compile(r'^\s*(?:[•○■▪\-–→»*]|\(?\d+[.)](?!\d)|\(?[A-Za-z][.)]|\(?[ivxlcdmIVXLCDM]+[.)])\s+')
    
    for idx in para_indices:
        if idx < 0 or idx >= len(paras):
            skipped.append(idx)
            continue
        p = paras[idx]
        text = (p.text or "").strip()
        if not text:
            skipped.append(idx)
            continue

        style_name = (p.style.name or "") if p.style is not None else ""
        # NEVER bullet a heading (e.g. "3.2. Proposed Solution")
        if is_heading_paragraph(text, style_name):
            print(f"[bullets] skip heading-like paragraph p{idx}: {text[:60]}")
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
               d.file_path, d.formatted_file_path, t.name as template_name
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

        formatted_path = r["formatted_file_path"] if "formatted_file_path" in r.keys() else None
        has_formatted = bool(formatted_path and os.path.exists(str(formatted_path)))
            
        result.append({
            "id": r["id"],
            "filename": r["filename"],
            "status": r["status"],
            "created_at": r["created_at"],
            "template_id": r["template_id"],
            "template_name": r["template_name"] or "None",
            "file_size": round(file_size, 2),
            "has_formatted": has_formatted,
        })
    return result


@app.post("/api/documents/upload", tags=["Documents"])
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    template_id: int = Query(...),
    user_id: int = Query(...),
):
    """Upload a document file and record in SQLite."""
    org_id = resolve_org_id_for_user_action(request, user_id)
    tmpl = get_template_by_id(template_id, org_id=org_id)
    if not tmpl:
        raise HTTPException(status_code=400, detail="Template not found for this organization.")

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
    request: Request,
    payload: Dict[str, Any] = Body(...),
    template_id: int = Query(...),
    user_id: int = Query(...),
):
    """Save raw pasted text content as a .txt document and record in SQLite."""
    return await _save_pasted_text_document(
        request=request,
        payload=payload,
        template_id=template_id,
        user_id=user_id,
    )


@app.post("/api/documents/create-report", tags=["Documents"])
async def create_report_from_paste(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    user_id: int = Query(...),
    template_id: Optional[int] = Query(None),
):
    """
    Alias used by New Report → Paste Content.
    Same behavior as upload-text; template_id may come from query or JSON body.
    """
    resolved_template = template_id
    if resolved_template is None:
        raw = payload.get("template_id")
        try:
            resolved_template = int(raw) if raw is not None else None
        except (TypeError, ValueError):
            resolved_template = None
    if not resolved_template:
        raise HTTPException(status_code=400, detail="template_id is required.")
    return await _save_pasted_text_document(
        request=request,
        payload=payload,
        template_id=int(resolved_template),
        user_id=user_id,
    )


async def _save_pasted_text_document(
    *,
    request: Request,
    payload: Dict[str, Any],
    template_id: int,
    user_id: int,
) -> Dict[str, Any]:
    org_id = resolve_org_id_for_user_action(request, user_id)
    tmpl = get_template_by_id(template_id, org_id=org_id)
    if not tmpl:
        raise HTTPException(status_code=400, detail="Template not found for this organization.")

    content = str(payload.get("content") or "")
    if not content.strip():
        raise HTTPException(status_code=400, detail="Paste some content before creating a report.")

    display_name = str(payload.get("title") or "").strip() or "Pasted Content"
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
        (user_id, template_id, display_name, file_path, "pending"),
    )
    conn.commit()
    doc_id = cursor.lastrowid
    conn.close()

    return {
        "document_id": doc_id,
        "filename": display_name,
        "status": "pending",
    }


def _require_non_student_for_freeform(user_id: int) -> None:
    """
    Block student (and any non-admin/non-supervisor) from freeform routes.
    Mirrors AuthProvider.isStudent / allows only roles that see the UI button:
    admin and supervisor. Same DB role lookup pattern as admin_routes._require_admin.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="User not found.")
    role = (row["role"] or "").strip().lower()
    if role not in ("admin", "supervisor"):
        raise HTTPException(
            status_code=403,
            detail="Freeform analysis is not available for student accounts.",
        )


@app.post("/api/documents/upload-freeform", tags=["Documents"])
async def upload_document_freeform(
    request: Request,
    file: UploadFile = File(...),
    user_id: int = Query(...),
):
    """
    Upload a document for template-free (AI general) analysis.
    Does not require a real org template — uses an internal placeholder id
    plus is_freeform=1 so the normal analyze path is not used.
    Students are blocked (403) — same role gate as AuthProvider.isStudent.
    """
    _require_non_student_for_freeform(user_id)
    resolve_org_id_for_user_action(request, user_id)
    placeholder_id = get_freeform_placeholder_template_id()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    stored_filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, stored_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO documents (user_id, template_id, filename, file_path, status, is_freeform)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (user_id, placeholder_id, file.filename, file_path, "pending"),
    )
    conn.commit()
    doc_id = cursor.lastrowid
    conn.close()

    return {
        "document_id": doc_id,
        "filename": file.filename,
        "status": "pending",
        "is_freeform": True,
    }


@app.post("/api/documents/upload-text-freeform", tags=["Documents"])
async def upload_text_freeform(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    user_id: int = Query(...),
):
    """Save pasted text for template-free analysis. Students blocked (403)."""
    _require_non_student_for_freeform(user_id)
    resolve_org_id_for_user_action(request, user_id)
    placeholder_id = get_freeform_placeholder_template_id()

    content = payload.get("content", "")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    stored_filename = f"{timestamp}_pasted_content_freeform.txt"
    file_path = os.path.join(UPLOAD_DIR, stored_filename)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO documents (user_id, template_id, filename, file_path, status, is_freeform)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (user_id, placeholder_id, "Pasted Content", file_path, "pending"),
    )
    conn.commit()
    doc_id = cursor.lastrowid
    conn.close()

    return {
        "document_id": doc_id,
        "filename": "Pasted Content",
        "status": "pending",
        "is_freeform": True,
    }


async def _run_analysis_freeform(
    saved_path: Optional[str],
    text: Optional[str],
    filename: str,
    job_id: str,
) -> Dict[str, Any]:
    """Template-free analysis: parse → batch → dispatch_freeform → aggregate."""
    if not ANTHROPIC_API_KEY and not GEMINI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Neither ANTHROPIC_API_KEY nor GEMINI_API_KEY is configured. Set one in backend/.env.",
        )

    try:
        if saved_path:
            norm_filename = _filename_for_parse(saved_path, filename)
            doc_model = parse_file(saved_path, norm_filename)
        else:
            doc_model = parse_text(text or "", title="pasted_text.txt")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse document: {exc}")

    try:
        from review_blocks import strip_frontmatter_from_document
        doc_model = strip_frontmatter_from_document(doc_model)
    except Exception as exc:
        print(f"[analysis-freeform] frontmatter skip failed (non-fatal): {exc}")

    batches = create_batches(doc_model)

    if GEMINI_API_KEY:
        from gemini_adapter import GeminiClientAdapter
        client = GeminiClientAdapter(api_key=GEMINI_API_KEY)
    else:
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    from plagiarism.pipeline import check_document_against_fyp_corpus

    dispatch_task = asyncio.create_task(dispatch_freeform(client, batches))
    corpus_task = asyncio.create_task(
        check_document_against_fyp_corpus(doc_model, document_id=job_id)
    )
    raw_issues, corpus_issues = await asyncio.gather(dispatch_task, corpus_task)
    if corpus_issues:
        raw_issues.extend(corpus_issues)

    # Pull freeform metadata off issue payloads before aggregate
    suggested_fixes: List[Dict[str, Any]] = []
    manual_notes: List[Dict[str, Any]] = []
    freeform_summary = ""
    for iss in raw_issues:
        if not isinstance(iss, dict):
            continue
        fixes = iss.pop("_suggested_fixes", None)
        notes = iss.pop("_suggested_manual_notes", None)
        summary = iss.pop("_freeform_summary", None)
        if fixes:
            suggested_fixes.extend(fixes)
        if notes:
            manual_notes.extend(notes)
        if summary:
            freeform_summary = str(summary)

    report = aggregate(raw_issues, doc_model, total_batches=len(batches))
    response = report.model_dump()
    response["job_id"] = job_id
    response["is_freeform"] = True
    response["analysis_mode"] = "ai_general"
    response["suggested_fixes"] = suggested_fixes
    response["suggested_manual_notes"] = manual_notes
    response["freeform_summary"] = freeform_summary
    # Do not silently reformat on analyze — export is a separate confirmed step.
    response["output_path"] = ""
    return response


@app.get("/api/documents/analyze-freeform/{document_id}", tags=["Documents"])
async def analyze_document_freeform_endpoint(document_id: int, user_id: int = Query(...)):
    """
    Analyze a freeform (no-template) document.
    Owner check + non-student role gate (403 for students).
    """
    _require_non_student_for_freeform(user_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM documents WHERE id = ? AND user_id = ?",
        (document_id, user_id),
    )
    doc = cursor.fetchone()
    conn.close()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    is_freeform = False
    try:
        is_freeform = bool(doc["is_freeform"])
    except (KeyError, IndexError, TypeError):
        is_freeform = False
    if not is_freeform:
        raise HTTPException(
            status_code=400,
            detail="Document was not uploaded for freeform analysis. Use /documents/analyze/{id}.",
        )

    working_copy = _working_copy_path(document_id)
    file_path = working_copy if os.path.exists(working_copy) else doc["file_path"]

    job_id = str(document_id)
    report_dict = await _run_analysis_freeform(
        saved_path=file_path,
        text=None,
        filename=doc["filename"],
        job_id=job_id,
    )

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE documents SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (document_id,),
    )
    conn.commit()
    conn.close()

    doc_model = None
    document_blocks: List[Dict[str, Any]] = []
    image_paths: Dict[str, str] = {}
    try:
        norm_filename = _filename_for_parse(file_path, doc["filename"])
        doc_model = parse_file(file_path, norm_filename)
        image_paths = save_document_images(doc_model, document_id, UPLOAD_DIR)
        document_blocks = build_document_blocks(doc_model, image_paths)
    except Exception as exc:
        print(f"[analyze-freeform] block build error (non-fatal): {exc}")

    raw_issues = report_dict.get("issues", [])
    normalized_issues = normalize_issues(raw_issues, image_paths)
    stats = report_dict.get("stats", {})

    content_issues = []
    style_issues = []
    for issue in normalized_issues:
        func = (issue.get("function") or "").lower()
        if func in ("grammar", "para_relevance", "plagiarism"):
            content_issues.append(issue)
        elif func == "formatting":
            style_issues.append(issue)

    major_count = len([i for i in normalized_issues if (i.get("severity") or "").lower() == "major"])
    minor_count = len([i for i in normalized_issues if (i.get("severity") or "").lower() == "minor"])

    score = stats.get("avg_formatting_compliance", 100.0)
    if score is None:
        score = 100.0

    paragraphs = [b["text"] for b in document_blocks if b.get("type") != "image" and b.get("text")]

    return {
        "document_id": document_id,
        "filename": doc["filename"],
        "status": "completed",
        "is_freeform": True,
        "analysis_mode": "ai_general",
        "label": "AI general analysis — no template applied",
        "score": score,
        "stats": stats,
        "issues": normalized_issues,
        "content_issues": content_issues,
        "style_issues": style_issues,
        "major_count": major_count,
        "minor_count": minor_count,
        "document_blocks": document_blocks,
        "paragraphs": paragraphs,
        "suggested_fixes": report_dict.get("suggested_fixes", []),
        "suggested_manual_notes": report_dict.get("suggested_manual_notes", []),
        "freeform_summary": report_dict.get("freeform_summary", ""),
        "template_heading_matches": [],  # skipped for freeform
        "structure": {"score": score},
    }


@app.delete("/api/documents/{document_id}", tags=["Documents"])
def delete_document(document_id: int, user_id: int = Query(...)):
    """Delete a document record and its physical files."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT file_path, formatted_file_path FROM documents WHERE id = ? AND user_id = ?",
        (document_id, user_id),
    )
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

    formatted_path = None
    try:
        formatted_path = doc["formatted_file_path"]
    except (KeyError, IndexError, TypeError):
        formatted_path = None
    for path in (
        formatted_path,
        _saved_formatted_path(document_id),
        _export_copy_path(document_id),
    ):
        if path and os.path.exists(str(path)):
            try:
                os.remove(str(path))
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

    try:
        if bool(doc["is_freeform"]):
            raise HTTPException(
                status_code=400,
                detail="This document uses freeform analysis. Call /documents/analyze-freeform/{id}.",
            )
    except (KeyError, IndexError, TypeError):
        pass

    tmpl = get_template_by_id(doc["template_id"])
    if tmpl and _is_fixable_source(doc["file_path"]):
        # Always rebuild from the upload on Analyze so Tables / style issues
        # reflect the source document, not a previously fixed working copy.
        # PDF/TXT are converted to a DOCX working copy (same as DOCX path).
        file_path = _ensure_formatted_working_copy(doc, tmpl, force_rebuild=True)
    else:
        working_copy = _working_copy_path(document_id)
        file_path = working_copy if os.path.exists(working_copy) else doc["file_path"]
    
    job_id = str(document_id)
    report_dict = await _run_analysis(
        template_id=str(doc["template_id"]),
        saved_path=file_path,
        text=None,
        filename=_filename_for_parse(file_path, doc["filename"]),
        job_id=job_id
    )
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE documents SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (document_id,))
    conn.commit()
    conn.close()

    if file_path.endswith(".docx") and os.path.exists(file_path):
        try:
            sync_analysis_to_project_members(document_id, file_path)
        except Exception as exc:
            print(f"[analyze] project sync error (non-fatal): {exc}")

    # Build structured blocks + normalized issues for the Flutter preview UI
    doc_model = None
    document_blocks: List[Dict[str, Any]] = []
    image_paths: Dict[str, str] = {}
    try:
        norm_filename = _filename_for_parse(file_path, doc["filename"])
        doc_model = parse_file(file_path, norm_filename)
        image_paths = save_document_images(doc_model, document_id, UPLOAD_DIR)
        document_blocks = build_document_blocks(doc_model, image_paths)
    except Exception as exc:
        print(f"[analyze] block build error (non-fatal): {exc}")

    raw_issues = report_dict.get("issues", [])
    normalized_issues = normalize_issues(raw_issues, image_paths)
    stats = report_dict.get("stats", {})
        
    content_issues = []
    style_issues = []
    
    for issue in normalized_issues:
        func = (issue.get("function") or "").lower()
        if func in ("grammar", "para_relevance", "plagiarism"):
            content_issues.append(issue)
        elif func == "formatting":
            style_issues.append(issue)
            
    if file_path.endswith(".docx"):
        bullets = _detect_missing_bullet_issues(file_path)
        for b in bullets:
            b["category"] = "Formatting"
            b["function"] = "formatting"
        style_issues.extend(bullets)
        normalized_issues.extend(bullets)

    major_count = len([i for i in normalized_issues if (i.get("severity") or "").lower() == "major"])
    minor_count = len([i for i in normalized_issues if (i.get("severity") or "").lower() == "minor"])
    critical_count = len([i for i in normalized_issues if (i.get("severity") or "").upper() == "CRITICAL"])
    warning_count = len([i for i in normalized_issues if (i.get("severity") or "").upper() in ("WARNING", "MINOR")])
        
    score = stats.get("avg_formatting_compliance", 100.0)
    if score is None:
        score = 100.0

    # Legacy flat paragraph list for backward compatibility
    paragraphs = [b["text"] for b in document_blocks if b.get("type") != "image" and b.get("text")]
    if not paragraphs:
        try:
            if file_path.endswith(".docx"):
                from docx import Document as DocxDoc
                paragraphs = [p.text for p in DocxDoc(file_path).paragraphs]
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    paragraphs = f.read().splitlines()
        except Exception:
            pass

    # Heading analysis — Claude-first detection, then template/rule cross-check
    # (body pages only — same front-matter skip as the AI analysis pipeline)
    template_heading_matches: List[Dict[str, Any]] = []
    if doc_model and tmpl:
        try:
            from review_blocks import strip_frontmatter_from_document
            heading_doc = strip_frontmatter_from_document(doc_model)
            decisions = _load_heading_decisions(document_id)
            client = None
            try:
                client = await _get_ai_client()
            except Exception as exc:
                print(f"[analyze] AI client unavailable for heading detect: {exc}")

            if client is not None:
                template_heading_matches = await analyze_document_headings_with_claude(
                    heading_doc,
                    tmpl,
                    client,
                    user_decisions=decisions,
                )
            else:
                template_heading_matches = analyze_document_headings(
                    heading_doc,
                    tmpl,
                    user_decisions=decisions,
                )

            template_heading_matches = enrich_matches_with_fix_status(
                template_heading_matches,
                document_blocks,
            )
            heading_issues = heading_matches_to_issues(template_heading_matches)
            if heading_issues:
                normalized_heading_issues = normalize_issues(heading_issues, image_paths)
                style_issues.extend(normalized_heading_issues)
                normalized_issues.extend(normalized_heading_issues)
        except Exception as exc:
            print(f"[analyze] heading analysis error (non-fatal): {exc}")
        
    return {
        "document_id": document_id,
        "filename": doc["filename"],
        "document_content": paragraphs,
        "document_blocks": document_blocks,
        "issues": normalized_issues,
        "content_issues": content_issues,
        "style_issues": style_issues,
        "stats": stats,
        "structure": {
            "score": score,
            "status": "good" if score >= 80 else "needs_work" if score >= 50 else "poor",
            "sections": [],
            "issues": [],
            "summary": {
                "missing": stats.get("formatting_issues", 0),
                "content_issues": len(content_issues),
                "style_issues": len(style_issues),
                "grammar": stats.get("grammar_issues", 0),
                "plagiarism": stats.get("plagiarism_issues", 0),
                "image_ethics": stats.get("image_ethics_issues", 0),
                "image_relevance": stats.get("image_relevance_issues", 0),
            },
        },
        "content_checker_mode": "ensemble_with_learning",
        "content_checker_version": "perfect",
        "template_heading_matches": template_heading_matches,
        "compliance_score": score,
        "total_issues": len(normalized_issues),
        "major_issues": major_count,
        "minor_issues": minor_count,
        "critical_issues": critical_count,
        "warning_issues": warning_count,
    }


class HeadingAnalysisRequest(BaseModel):
    template: Dict[str, Any]
    blocks: List[Dict[str, Any]]


@app.post("/api/heading-analysis", tags=["Analysis"])
async def heading_analysis_endpoint(body: HeadingAnalysisRequest = Body(...)):
    """
    Run deterministic heading detection, template matching, and level assignment.

    Accepts a template outline (required_sections) and a list of text blocks with
    optional formatting metadata (font_size, bold, style_name, numbering_prefix).
    """
    blocks = blocks_from_dicts(body.blocks)
    return analyze_headings(blocks, body.template)


class HeadingDecisionRequest(BaseModel):
    paragraph_id: str
    decision: str  # "keep" | "discard"
    heading_level: Optional[int] = None
    apply_style: bool = True


@app.post("/api/documents/heading-decision/{document_id}", tags=["Documents"])
async def heading_decision_endpoint(
    document_id: int,
    user_id: int = Query(...),
    body: HeadingDecisionRequest = Body(...),
):
    """
    Keep or discard a Claude-detected heading that is not in the template.

    Keep → persist decision and optionally apply Word Heading style.
    Discard → persist decision; paragraph is treated as body text.
    """
    decision = (body.decision or "").strip().lower()
    if decision not in ("keep", "discard"):
        raise HTTPException(status_code=400, detail='decision must be "keep" or "discard"')
    pid = (body.paragraph_id or "").strip()
    if not pid:
        raise HTTPException(status_code=400, detail="paragraph_id is required")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
    doc = cursor.fetchone()
    conn.close()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    decisions = _save_heading_decision(document_id, pid, decision)
    result: Dict[str, Any] = {
        "success": True,
        "paragraph_id": pid,
        "decision": decision,
        "decisions": decisions,
        "style_applied": False,
        "message": (
            "Heading kept."
            if decision == "keep"
            else "Heading discarded — treated as body text."
        ),
    }

    if decision == "keep" and body.apply_style:
        tmpl = get_template_by_id(doc["template_id"])
        if not tmpl:
            raise HTTPException(status_code=400, detail="Template not found")
        try:
            working_copy = _ensure_formatted_working_copy(doc, tmpl)
            level = max(1, min(4, int(body.heading_level or 1)))
            ok, msg = apply_heading_fix(working_copy, pid, level)
            if not ok:
                result["message"] = f"Decision saved, but style apply failed: {msg}"
            else:
                committed = _commit_working_document(document_id, working_copy, doc)
                result.update(committed)
                result["style_applied"] = True
                result["message"] = f"Heading kept and Heading {level} style applied."
        except Exception as exc:
            result["message"] = f"Decision saved, but style apply failed: {exc}"
    elif decision == "discard":
        tmpl = get_template_by_id(doc["template_id"])
        if tmpl and _is_fixable_source(doc["file_path"]):
            try:
                working_copy = _ensure_formatted_working_copy(doc, tmpl)
                ok, msg = demote_heading_to_body(working_copy, pid)
                if ok:
                    committed = _commit_working_document(document_id, working_copy, doc)
                    result.update(committed)
                    result["style_applied"] = True
                    result["message"] = "Heading discarded and demoted to body text."
                else:
                    result["message"] = f"Decision saved ({msg})."
            except Exception as exc:
                result["message"] = f"Decision saved, but demote failed: {exc}"

    return result


async def _get_ai_client():
    if GEMINI_API_KEY:
        from gemini_adapter import GeminiClientAdapter
        return GeminiClientAdapter(api_key=GEMINI_API_KEY)
    return anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


@app.post("/api/format-images/{document_id}", tags=["Documents"])
async def format_images_endpoint(document_id: int, user_id: int = Query(...)):
    """
    Phase 1 image formatting: caption detect/standardize, numbering,
    in-text reference validation, and List of Figures refresh.
    (Legacy AI caption/resize lives behind ?legacy=1.)
    """
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

    working_copy = os.path.join(UPLOAD_DIR, "working", f"doc_{document_id}_working.docx")
    file_path = working_copy if os.path.exists(working_copy) else doc["file_path"]
    if not file_path.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only DOCX files support image formatting.")

    output_path = os.path.join(OUTPUT_DIR, f"images_formatted_{document_id}.docx")
    rules = tmpl.get("formatting_rules", {}) or {}

    result = run_image_formatting_pipeline(file_path, output_path, rules)
    os.makedirs(os.path.dirname(working_copy) or ".", exist_ok=True)
    shutil.copy2(output_path, working_copy)
    result["download_url"] = f"/api/format-images/download/{document_id}"
    return result


@app.post("/api/format-images/{document_id}/legacy", tags=["Documents"])
async def format_images_legacy_endpoint(document_id: int, user_id: int = Query(...)):
    """Legacy auto-format: center, resize, AI captions."""
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

    working_copy = os.path.join(UPLOAD_DIR, "working", f"doc_{document_id}_working.docx")
    file_path = working_copy if os.path.exists(working_copy) else doc["file_path"]
    if not file_path.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only DOCX files support image formatting.")

    output_path = os.path.join(OUTPUT_DIR, f"images_formatted_{document_id}.docx")
    client = await _get_ai_client()
    result = await format_document_images(
        file_path, output_path, client, tmpl.get("formatting_rules", {}),
    )
    os.makedirs(os.path.dirname(working_copy) or ".", exist_ok=True)
    shutil.copy2(output_path, working_copy)
    result["download_url"] = f"/api/format-images/download/{document_id}"
    return result


@app.get("/api/templates/image-format-defaults", tags=["Templates"])
async def image_format_defaults():
    """Default image/caption formatting_rules keys for admin UI."""
    return {"defaults": DEFAULT_IMAGE_FORMAT_RULES}


@app.get("/api/templates/table-format-defaults", tags=["Templates"])
async def table_format_defaults():
    """Default table formatting_rules keys (flat + table_style) for admin UI."""
    return {"defaults": DEFAULT_TABLE_FORMAT_RULES}


def _normalize_template_formatting_rules(rules: Dict[str, Any] | None) -> Dict[str, Any]:
    """Validate + normalize table section; preserve all other keys."""
    data = dict(rules or {})
    errors = validate_table_format_rules(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    # Also lightly validate figure caption enums if present
    if "numbering_scheme" in data and data["numbering_scheme"] is not None:
        raw = str(data["numbering_scheme"]).strip().lower()
        if raw not in ("global", "chapter", "chapter-wise", "chapter_wise"):
            raise HTTPException(
                status_code=400,
                detail="numbering_scheme must be 'global' or 'chapter'",
            )
    if "caption_position" in data and data["caption_position"] is not None:
        pos = str(data["caption_position"]).strip().lower()
        if pos not in ("above", "below"):
            raise HTTPException(
                status_code=400,
                detail="caption_position must be 'above' or 'below'",
            )
    if "max_image_width_percent" in data and data["max_image_width_percent"] is not None:
        try:
            pct = int(data["max_image_width_percent"])
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400, detail="max_image_width_percent must be an integer"
            )
        if pct < 0 or pct > 100:
            raise HTTPException(
                status_code=400,
                detail="max_image_width_percent must be between 0 and 100",
            )
    return normalize_formatting_rules_table_section(data)


@app.get("/api/format-images/download/{document_id}", tags=["Documents"])
async def download_formatted_images(document_id: int, user_id: int = Query(...), file: str = Query(None)):
    """Download image-formatted document."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
    doc = cursor.fetchone()
    conn.close()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    path = os.path.join(OUTPUT_DIR, f"images_formatted_{document_id}.docx")
    working_copy = os.path.join(UPLOAD_DIR, "working", f"doc_{document_id}_working.docx")
    if os.path.exists(working_copy):
        path = working_copy
    elif not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Formatted file not found. Run image formatting first.")

    return FileResponse(
        path=path,
        filename=f"formatted_images_{doc['filename']}",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


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
def export_formatted_document(
    document_id: int,
    user_id: int = Query(...),
    format: str = Query(default="docx"),
):
    """Download the formatted document as DOCX or PDF."""
    export_format = (format or "docx").strip().lower()
    if export_format not in {"docx", "pdf"}:
        raise HTTPException(status_code=400, detail="format must be 'docx' or 'pdf'")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
    doc = cursor.fetchone()
    conn.close()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Template still required for cold rebuild when no working copy exists yet.
    tmpl = get_template_by_id(doc["template_id"])
    if not tmpl and not os.path.exists(_working_copy_path(document_id)):
        raise HTTPException(status_code=400, detail="Document has no valid template assigned.")

    output_path = _prepare_formatted_docx(doc, document_id)
    base_name = f"formatted_{os.path.splitext(doc['filename'] or 'document')[0]}"

    if export_format == "pdf":
        pdf_path = convert_docx_to_pdf(output_path)
        if not pdf_path or not os.path.exists(pdf_path):
            raise HTTPException(
                status_code=500,
                detail="Could not convert document to PDF. Try Word (.docx) instead.",
            )
        return FileResponse(
            path=pdf_path,
            filename=f"{base_name}.pdf",
            media_type="application/pdf",
        )

    download_name = f"{base_name}.docx"
    return FileResponse(
        path=output_path,
        filename=download_name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.post("/api/documents/{document_id}/save-formatted", tags=["Documents"])
def save_formatted_document(document_id: int, user_id: int = Query(...)):
    """
    Persist the current formatted working document for My Reports.

    Copies the same DOCX that Export would download into a durable
    ``uploads/formatted/`` path and stores it on the document row.
    The original upload (``file_path``) is never overwritten.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM documents WHERE id = ? AND user_id = ?",
        (document_id, user_id),
    )
    doc = cursor.fetchone()
    if not doc:
        conn.close()
        raise HTTPException(status_code=404, detail="Document not found")

    export_path = _prepare_formatted_docx(doc, document_id)
    saved_path = _saved_formatted_path(document_id)
    os.makedirs(os.path.dirname(saved_path), exist_ok=True)
    shutil.copy2(export_path, saved_path)

    cursor.execute(
        """
        UPDATE documents
        SET formatted_file_path = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
        """,
        (saved_path, document_id, user_id),
    )
    conn.commit()
    conn.close()

    stem = os.path.splitext(doc["filename"] or "document")[0]
    print(f"[save-formatted] doc={document_id} saved -> {saved_path}")
    return {
        "success": True,
        "document_id": document_id,
        "has_formatted": True,
        "formatted_filename": f"formatted_{stem}.docx",
        "message": "Formatted document saved. Open My Reports to access Unformatted and Formatted versions.",
    }


@app.get("/api/documents/{document_id}/download-original", tags=["Documents"])
def download_original_document(document_id: int, user_id: int = Query(...)):
    """Download the student's original (unformatted) uploaded file."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT filename, file_path FROM documents WHERE id = ? AND user_id = ?",
        (document_id, user_id),
    )
    doc = cursor.fetchone()
    conn.close()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = doc["file_path"]
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Original file is missing on the server.")

    download_name = doc["filename"] or os.path.basename(file_path) or "document"
    return FileResponse(
        path=file_path,
        filename=download_name,
        media_type=_guess_media_type(download_name),
    )


@app.get("/api/documents/{document_id}/download-formatted", tags=["Documents"])
def download_saved_formatted_document(
    document_id: int,
    user_id: int = Query(...),
    format: str = Query(default="docx"),
):
    """
    Download a previously saved formatted document from My Reports.

    Requires ``POST /save-formatted`` first. Does not fall back to a live
    reformat — that keeps Unformatted vs Formatted clearly distinct.
    """
    export_format = (format or "docx").strip().lower()
    if export_format not in {"docx", "pdf"}:
        raise HTTPException(status_code=400, detail="format must be 'docx' or 'pdf'")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT filename, formatted_file_path FROM documents WHERE id = ? AND user_id = ?",
        (document_id, user_id),
    )
    doc = cursor.fetchone()
    conn.close()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    formatted_path = None
    try:
        formatted_path = doc["formatted_file_path"]
    except (KeyError, IndexError, TypeError):
        formatted_path = None

    if not formatted_path or not os.path.exists(str(formatted_path)):
        # Fall back to the conventional saved path if the column is empty but file exists
        fallback = _saved_formatted_path(document_id)
        if os.path.exists(fallback):
            formatted_path = fallback
        else:
            raise HTTPException(
                status_code=404,
                detail=(
                    "No saved formatted document yet. "
                    "Open Analysis and tap Save Formatted Document first."
                ),
            )

    stem = os.path.splitext(doc["filename"] or "document")[0]
    base_name = f"formatted_{stem}"

    if export_format == "pdf":
        pdf_path = convert_docx_to_pdf(str(formatted_path))
        if not pdf_path or not os.path.exists(pdf_path):
            raise HTTPException(
                status_code=500,
                detail="Could not convert document to PDF. Try Word (.docx) instead.",
            )
        return FileResponse(
            path=pdf_path,
            filename=f"{base_name}.pdf",
            media_type="application/pdf",
        )

    return FileResponse(
        path=str(formatted_path),
        filename=f"{base_name}.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
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
    
    reformat_document(
        file_path, working_copy, report,
        tmpl["formatting_rules"], tmpl.get("required_sections", []),
    )

    try:
        from frontmatter_apply import clear_frontmatter_marker, ensure_frontmatter_pages
        clear_frontmatter_marker(document_id)
        ensure_frontmatter_pages(document_id, working_copy)
    except Exception as exc:
        print(f"[apply-all-style-fixes] frontmatter apply skipped: {exc}")
    
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

    tmpl = get_template_by_id(doc["template_id"])
    if not tmpl:
        raise HTTPException(status_code=400, detail="Template not found")

    working_copy = _ensure_formatted_working_copy(doc, tmpl)

    para_indices = payload.get("para_indices", [])
    if not para_indices and "para_index" in payload:
        para_indices = [payload["para_index"]]

    if fix_type == "apply_section_bullets":
        applied, skipped = apply_section_bullets_to_file(working_copy, para_indices)
        commit = _commit_working_document(document_id, working_copy, doc)
        return {"status": "success", "applied": applied, "skipped": skipped, **commit}
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported fix_type: {fix_type}")


@app.post("/api/documents/apply-content-fix/{document_id}", tags=["Documents"])
async def apply_content_fix(
    document_id: int,
    user_id: int = Query(...),
    payload: Dict[str, Any] = Body(...),
):
    """Apply a single fix to the template-formatted working document and sync export."""
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

    working_copy = _ensure_formatted_working_copy(doc, tmpl)

    fix_type = payload.get("fix_type", "text")
    if fix_type == "heading":
        level = int(payload.get("heading_level", 1) or 1)
        ok, msg = apply_heading_fix(working_copy, payload.get("paragraph_id", ""), level)
        if ok:
            apply_template_reformat(
                working_copy,
                tmpl["formatting_rules"],
                tmpl.get("required_sections", []),
            )
    elif fix_type in ("bullets", "apply_section_bullets"):
        para_indices = payload.get("para_indices", [])
        if not para_indices and payload.get("paragraph_id"):
            m = re.match(r"p(\d+)", str(payload.get("paragraph_id", "")))
            if m:
                para_indices = [int(m.group(1))]
        if payload.get("fix_details") and isinstance(payload["fix_details"], dict):
            para_indices = payload["fix_details"].get("para_indices", para_indices)
        applied, skipped = apply_section_bullets_to_file(working_copy, para_indices)
        ok = len(applied) > 0
        msg = f"Bullets applied to {len(applied)} paragraph(s)." if ok else "No bullets applied."
    elif fix_type == "formatting":
        ok, msg = apply_template_reformat(
            working_copy,
            tmpl["formatting_rules"],
            tmpl.get("required_sections", []),
        )
    else:
        suggestion = payload.get("suggestion", "")
        if _is_instruction_suggestion(suggestion):
            raise HTTPException(
                status_code=400,
                detail="This issue requires a structural fix (heading/style), not text replacement.",
            )
        ok, msg = apply_text_fix(
            working_copy,
            payload.get("paragraph_id", ""),
            payload.get("original", ""),
            suggestion,
        )

    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    commit = _commit_working_document(document_id, working_copy, doc)
    return {
        "status": "success",
        "message": msg,
        **commit,
    }


# @app.post("/api/documents/apply-all-fixes/{document_id}", tags=["Documents"])
# async def apply_all_fixes(
#     document_id: int,
#     user_id: int = Query(...),
#     payload: Dict[str, Any] = Body(default={}),
# ):
#     """
#     Apply ALL fixes on the working document:
#       - heading style fixes
#       - grammar/text fixes
#       - missing bullet / list_formatting groups (deterministic detection)
#       - template reformatting (H1–H3 numbering only; H4 style-only)
#       - image formatting + TOC/LOT/LOF when configured
#     """
#     conn = get_db()
#     cursor = conn.cursor()
#     cursor.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
#     doc = cursor.fetchone()
#     conn.close()

#     if not doc:
#         raise HTTPException(status_code=404, detail="Document not found")

#     tmpl = get_template_by_id(doc["template_id"])
#     if not tmpl:
#         raise HTTPException(status_code=400, detail="Template not found")

#     working_copy = _ensure_formatted_working_copy(doc, tmpl)

#     text_result = {"applied": 0, "skipped": 0, "errors": []}
#     bullet_result = {"applied": [], "skipped": [], "groups": 0}
#     fixes = payload.get("fixes", [])

#     # Split payload fixes into heading / bullets / text
#     heading_fixes = []
#     bullet_fix_indices: list = []
#     text_fixes = []
#     for fix in fixes:
#         ftype = (fix.get("fix_type") or "text").lower()
#         itype = (fix.get("type") or "").lower()
#         if ftype in ("heading", "heading_style") or itype == "heading_style":
#             heading_fixes.append(fix)
#         elif ftype in ("bullets", "apply_section_bullets", "list_formatting") or itype in (
#             "missing_bullets", "list_formatting",
#         ):
#             indices = fix.get("para_indices") or []
#             if not indices and isinstance(fix.get("fix_details"), dict):
#                 indices = fix["fix_details"].get("para_indices") or []
#             if not indices and fix.get("paragraph_id"):
#                 m = re.match(r"p(\d+)", str(fix.get("paragraph_id", "")))
#                 if m:
#                     indices = [int(m.group(1))]
#             bullet_fix_indices.extend(int(i) for i in indices)
#         else:
#             text_fixes.append(fix)

#     if working_copy.endswith(".docx"):
#         # 1) Heading fixes first (also strips any mistaken bullets on those paras)
#         for fix in heading_fixes:
#             ok, msg = apply_heading_fix(
#                 working_copy,
#                 fix.get("paragraph_id", ""),
#                 int(fix.get("heading_level", 1) or 1),
#                 renumber=False,
#             )
#             if ok:
#                 text_result["applied"] += 1
#             else:
#                 text_result["skipped"] += 1
#                 text_result["errors"].append(msg)
#         if heading_fixes:
#             renumber_heading_prefixes(working_copy)

#         # 2) Grammar/text fixes
#         if text_fixes:
#             tr = apply_all_text_fixes(working_copy, text_fixes)
#             text_result["applied"] += tr.get("applied", 0)
#             text_result["skipped"] += tr.get("skipped", 0)
#             text_result["errors"].extend(tr.get("errors") or [])

#         # 3) Deterministic list detection — apply high-confidence groups
#         #    (infinitives / markers / trigger lines) so "To develop…" lists
#         #    are covered. Ambiguous Label:colon groups only apply when the
#         #    formatting agent confirmed them in the payload fixes.
#         try:
#             from docx import Document as DocxDoc
#             from docx.oxml.ns import qn
#             from list_detection import detect_list_groups, groups_needing_numpr

#             _SAFE_APPLY_DETECTIONS = {
#                 "infinitive",
#                 "gerund",
#                 "trigger_line",
#                 "trigger_follower",
#                 "marker",
#                 "bullet_marker",
#             }

#             docx = DocxDoc(working_copy)
#             blocks = []
#             for idx, p in enumerate(docx.paragraphs):
#                 text = (p.text or "").strip()
#                 if not text:
#                     continue
#                 style_name = (p.style.name or "").lower() if p.style else ""
#                 has_numpr = p._element.find(f".//{qn('w:numPr')}") is not None
#                 btype = "paragraph"
#                 if has_numpr or "list" in style_name:
#                     btype = "list_item"
#                 elif "heading" in style_name:
#                     btype = "heading"
#                 blocks.append({
#                     "index": idx,
#                     "type": btype,
#                     "text": text,
#                     "style": style_name,
#                     "has_numpr": has_numpr,
#                     "paragraph_id": f"p{idx}",
#                 })
#             groups = groups_needing_numpr(detect_list_groups(blocks))
#             safe_indices = {
#                 i
#                 for g in groups
#                 if (g.detection or "").lower() in _SAFE_APPLY_DETECTIONS
#                 for i in g.indices
#             }
#             all_indices = sorted(safe_indices | set(bullet_fix_indices))
#             if all_indices:
#                 applied, skipped = apply_section_bullets_to_file(working_copy, all_indices)
#                 bullet_result = {
#                     "applied": applied,
#                     "skipped": skipped,
#                     "groups": len(groups),
#                 }
#                 print(
#                     f"[apply-all] bullets: {len(applied)} applied, "
#                     f"{len(skipped)} skipped across {len(groups)} groups"
#                 )
#         except Exception as exc:
#             print(f"[apply-all] bullet detection error (non-fatal): {exc}")
#             bullet_result = {"applied": [], "skipped": [], "groups": 0, "error": str(exc)}

#         # 4) Strip bullets from any remaining heading paragraphs
#         try:
#             _strip_bullets_from_headings(working_copy)
#         except Exception as exc:
#             print(f"[apply-all] strip heading bullets error (non-fatal): {exc}")

#     apply_template_reformat(
#         working_copy,
#         tmpl["formatting_rules"],
#         tmpl.get("required_sections", []),
#     )

#     # After reformat, headings may reappear with leftover bullets — clean again
#     if working_copy.endswith(".docx"):
#         try:
#             _strip_bullets_from_headings(working_copy)
#         except Exception:
#             pass

#     image_result = {"status": "skipped"}
#     if working_copy.endswith(".docx"):
#         try:
#             client = await _get_ai_client()
#             output_path = os.path.join(OUTPUT_DIR, f"images_formatted_{document_id}.docx")
#             image_result = await format_document_images(
#                 working_copy, output_path, client, tmpl.get("formatting_rules", {}),
#             )
#             shutil.copy2(output_path, working_copy)
#         except Exception as exc:
#             image_result = {"status": "error", "message": str(exc)}

#     lists_result = {"status": "skipped"}
#     if working_copy.endswith(".docx"):
#         try:
#             rules = tmpl.get("formatting_rules", {})
#             # Prefer explicit UI toggles from payload; fall back to template rules
#             include_toc = payload.get("include_toc", rules.get("include_toc", True))
#             include_lot = payload.get("include_lot", rules.get("include_lot", True))
#             include_lof = payload.get("include_lof", rules.get("include_lof", True))
#             lists_result = generate_document_lists(
#                 working_copy,
#                 rules,
#                 tmpl.get("required_sections", []),
#                 include_toc=bool(include_toc),
#                 include_lot=bool(include_lot),
#                 include_lof=bool(include_lof),
#                 toc_levels=str(
#                     payload.get("toc_levels") or rules.get("toc_levels", "1-3")
#                 ),
#             )
#         except Exception as exc:
#             lists_result = {"status": "error", "message": str(exc)}

#     commit = _commit_working_document(document_id, working_copy, doc)

#     return {
#         "status": "success",
#         "message": "All fixes applied to formatted working document",
#         "text_fixes": text_result,
#         "bullet_fixes": bullet_result,
#         "image_formatting": image_result,
#         "document_lists": lists_result,
#         **commit,
#     }


@app.post("/api/documents/apply-all-fixes/{document_id}", tags=["Documents"])
async def apply_all_fixes(
    document_id: int,
    user_id: int = Query(...),
    payload: Dict[str, Any] = Body(default={}),
):
    """
    Apply ALL fixes on the working document:
      - heading style fixes
      - grammar/text fixes
      - missing bullet / list_formatting groups (deterministic detection)
      - template reformatting (H1–H3 numbering only; H4 style-only)
      - table formatting (captions, fonts, header style)
      - image formatting + TOC/LOT/LOF when configured

    The response lists which issue_ids were actually resolved so the UI can
    clear them from every tab without re-running the (expensive) AI analysis.
    """
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

    working_copy = _ensure_formatted_working_copy(doc, tmpl)

    text_result = {"applied": 0, "skipped": 0, "errors": []}
    bullet_result = {"applied": [], "skipped": [], "groups": 0}
    fixes = payload.get("fixes", [])

    # What the UI may clear after this call
    resolved_issue_ids: List[str] = []
    resolved_heading_pids: List[str] = []
    bullet_fix_meta: List[tuple] = []  # (issue_id, [para indices])
    template_reformat_applied = False
    table_result: Dict[str, Any] = {"status": "skipped"}

    # Split payload fixes into heading / bullets / text
    heading_fixes = []
    bullet_fix_indices: list = []
    text_fixes = []
    for fix in fixes:
        ftype = (fix.get("fix_type") or "text").lower()
        itype = (fix.get("type") or "").lower()
        if ftype in ("heading", "heading_style") or itype == "heading_style":
            heading_fixes.append(fix)
        elif ftype in ("bullets", "apply_section_bullets", "list_formatting") or itype in (
            "missing_bullets", "list_formatting",
        ):
            indices = fix.get("para_indices") or []
            if not indices and isinstance(fix.get("fix_details"), dict):
                indices = fix["fix_details"].get("para_indices") or []
            if not indices and fix.get("paragraph_id"):
                m = re.match(r"p(\d+)", str(fix.get("paragraph_id", "")))
                if m:
                    indices = [int(m.group(1))]
            int_indices = [int(i) for i in indices]
            bullet_fix_indices.extend(int_indices)
            bullet_fix_meta.append((str(fix.get("issue_id") or ""), int_indices))
        else:
            text_fixes.append(fix)

    if working_copy.endswith(".docx"):
        # 1) Heading fixes first (also strips any mistaken bullets on those paras)
        for fix in heading_fixes:
            ok, msg = apply_heading_fix(
                working_copy,
                fix.get("paragraph_id", ""),
                int(fix.get("heading_level", 1) or 1),
                renumber=False,
            )
            if ok:
                text_result["applied"] += 1
                resolved_heading_pids.append(str(fix.get("paragraph_id", "")))
                if fix.get("issue_id"):
                    resolved_issue_ids.append(str(fix["issue_id"]))
            else:
                text_result["skipped"] += 1
                text_result["errors"].append(msg)
        if heading_fixes:
            renumber_heading_prefixes(working_copy)

        # 2) Grammar/text fixes
        if text_fixes:
            tr = apply_all_text_fixes(working_copy, text_fixes)
            text_result["applied"] += tr.get("applied", 0)
            text_result["skipped"] += tr.get("skipped", 0)
            text_result["errors"].extend(tr.get("errors") or [])
            resolved_issue_ids.extend(tr.get("applied_ids") or [])

        # 3) Deterministic list detection — apply high-confidence groups
        try:
            from docx import Document as DocxDoc
            from docx.oxml.ns import qn
            from list_detection import detect_list_groups, groups_needing_numpr

            _SAFE_APPLY_DETECTIONS = {
                "infinitive",
                "gerund",
                "trigger_line",
                "trigger_follower",
                "marker",
                "bullet_marker",
            }

            docx = DocxDoc(working_copy)
            blocks = []
            for idx, p in enumerate(docx.paragraphs):
                text = (p.text or "").strip()
                if not text:
                    continue
                style_name = (p.style.name or "").lower() if p.style else ""
                has_numpr = p._element.find(f".//{qn('w:numPr')}") is not None
                btype = "paragraph"
                if has_numpr or "list" in style_name:
                    btype = "list_item"
                elif "heading" in style_name:
                    btype = "heading"
                blocks.append({
                    "index": idx,
                    "type": btype,
                    "text": text,
                    "style": style_name,
                    "has_numpr": has_numpr,
                    "paragraph_id": f"p{idx}",
                })
            groups = groups_needing_numpr(detect_list_groups(blocks))
            safe_indices = {
                i
                for g in groups
                if (g.detection or "").lower() in _SAFE_APPLY_DETECTIONS
                for i in g.indices
            }
            all_indices = sorted(safe_indices | set(bullet_fix_indices))
            if all_indices:
                applied, skipped = apply_section_bullets_to_file(working_copy, all_indices)
                bullet_result = {
                    "applied": applied,
                    "skipped": skipped,
                    "groups": len(groups),
                }
                applied_set = set(applied)
                for iid, idxs in bullet_fix_meta:
                    if iid and applied_set.intersection(idxs):
                        resolved_issue_ids.append(iid)
                print(
                    f"[apply-all] bullets: {len(applied)} applied, "
                    f"{len(skipped)} skipped across {len(groups)} groups"
                )
        except Exception as exc:
            print(f"[apply-all] bullet detection error (non-fatal): {exc}")
            bullet_result = {"applied": [], "skipped": [], "groups": 0, "error": str(exc)}

        # 4) Strip bullets from any remaining heading paragraphs
        try:
            _strip_bullets_from_headings(working_copy)
        except Exception as exc:
            print(f"[apply-all] strip heading bullets error (non-fatal): {exc}")

    template_reformat_applied, _reformat_msg = apply_template_reformat(
        working_copy,
        tmpl["formatting_rules"],
        tmpl.get("required_sections", []),
    )

    # After reformat, headings may reappear with leftover bullets — clean again
    if working_copy.endswith(".docx"):
        try:
            _strip_bullets_from_headings(working_copy)
        except Exception:
            pass

    # Table formatting (captions, fonts, header style) — same pipeline the
    # Tables tab uses, so Tables issues clear after Apply All.
    if working_copy.endswith(".docx"):
        try:
            tables_out = os.path.join(OUTPUT_DIR, f"tables_formatted_{document_id}.docx")
            table_result = run_table_formatting_pipeline(
                working_copy,
                tables_out,
                tmpl.get("formatting_rules", {}) or {},
            )
            shutil.copy2(tables_out, working_copy)
        except Exception as exc:
            print(f"[apply-all] table formatting error (non-fatal): {exc}")
            table_result = {"status": "error", "message": str(exc)}

    image_result = {"status": "skipped"}
    if working_copy.endswith(".docx"):
        try:
            client = await _get_ai_client()
            output_path = os.path.join(OUTPUT_DIR, f"images_formatted_{document_id}.docx")
            image_result = await format_document_images(
                working_copy, output_path, client, tmpl.get("formatting_rules", {}),
            )
            shutil.copy2(output_path, working_copy)
        except Exception as exc:
            image_result = {"status": "error", "message": str(exc)}

    lists_result = {"status": "skipped"}
    if working_copy.endswith(".docx"):
        try:
            rules = tmpl.get("formatting_rules", {})
            include_toc = payload.get("include_toc", rules.get("include_toc", True))
            include_lot = payload.get("include_lot", rules.get("include_lot", True))
            include_lof = payload.get("include_lof", rules.get("include_lof", True))
            lists_result = generate_document_lists(
                working_copy,
                rules,
                tmpl.get("required_sections", []),
                include_toc=bool(include_toc),
                include_lot=bool(include_lot),
                include_lof=bool(include_lof),
                toc_levels=str(
                    payload.get("toc_levels") or rules.get("toc_levels", "1-3")
                ),
            )
        except Exception as exc:
            lists_result = {"status": "error", "message": str(exc)}

    commit = _commit_working_document(document_id, working_copy, doc)

    return {
        "status": "success",
        "message": "All fixes applied to formatted working document",
        "text_fixes": text_result,
        "bullet_fixes": bullet_result,
        "image_formatting": image_result,
        "document_lists": lists_result,
        "table_formatting": table_result,
        "resolved_issue_ids": resolved_issue_ids,
        "resolved_heading_pids": resolved_heading_pids,
        "template_reformat_applied": bool(template_reformat_applied),
        **commit,
    }



def _strip_bullets_from_headings(docx_path: str) -> int:
    """Remove Word list numbering / bullet glyphs from heading paragraphs."""
    from docx import Document as DocxDoc
    from docx.oxml.ns import qn
    from list_detection import is_heading_paragraph

    docx = DocxDoc(docx_path)
    cleaned = 0
    for p in docx.paragraphs:
        text = (p.text or "").strip()
        if not text:
            continue
        style_name = (p.style.name or "") if p.style is not None else ""
        if not is_heading_paragraph(text, style_name) and "heading" not in style_name.lower():
            continue
        pPr = p._element.get_or_add_pPr()
        numPr = pPr.find(qn("w:numPr"))
        if numPr is not None:
            pPr.remove(numPr)
            cleaned += 1
        # Drop visible bullet glyphs
        new_text = re.sub(r"^\s*[•*○■▪\-–—→»·]\s+", "", text)
        if new_text != text and new_text:
            text_runs = []
            for run in p.runs:
                el = run._element
                has_drawing = bool(
                    list(el.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing"))
                    or list(el.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pict"))
                    or list(el.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}blip"))
                )
                if not has_drawing:
                    text_runs.append(run)
            if text_runs:
                text_runs[0].text = new_text
                for run in text_runs[1:]:
                    run.text = ""
                cleaned += 1
            # else: image-only / mixed without clear text run — skip rewriting
    if cleaned:
        docx.save(docx_path)
        print(f"[apply-all] stripped bullets from {cleaned} heading paragraph(s)")
    return cleaned


@app.post("/api/documents/recheck-image/{document_id}", tags=["Documents"])
async def recheck_image_endpoint(
    document_id: int,
    user_id: int = Query(...),
    payload: Dict[str, Any] = Body(...),
):
    """Re-run ethics + relevance on a single image after user replacement."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
    doc = cursor.fetchone()
    conn.close()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    b64 = payload.get("image_base64", "")
    image_id = payload.get("image_id", "")
    surrounding = payload.get("surrounding_text", "")

    if not b64:
        raise HTTPException(status_code=400, detail="image_base64 is required")

    try:
        from functions.image_relevance import recheck_image
        client = await _get_ai_client()
        result = await recheck_image(client, b64, surrounding, image_id)
        return {"status": "success", **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/documents/{document_id}/replace-image", tags=["Documents"])
async def replace_image(
    document_id: int,
    image_index: int = Form(...),
    file: UploadFile = File(...),
    user_id: int = Query(None),
):
    """Replace an image in the working DOCX, validate relevance, return preview path."""
    conn = get_db()
    cursor = conn.cursor()
    if user_id:
        cursor.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
    else:
        cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
    doc = cursor.fetchone()
    conn.close()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not _is_fixable_source(doc["file_path"]):
        raise HTTPException(status_code=400, detail="Image replacement is only supported for DOCX/PDF/TXT files.")

    img_dir = os.path.join(UPLOAD_DIR, "images", f"doc_{document_id}")
    os.makedirs(img_dir, exist_ok=True)

    ext = os.path.splitext(file.filename or "")[1].lower() or ".png"
    image_id = f"img{image_index}"
    rel_path = f"images/doc_{document_id}/{image_id}{ext}"
    full_path = os.path.join(UPLOAD_DIR, rel_path)

    content = await file.read()
    with open(full_path, "wb") as f:
        f.write(content)

    tmpl = get_template_by_id(doc["template_id"])
    if not tmpl:
        raise HTTPException(status_code=400, detail="Template not found")

    working_copy = _ensure_formatted_working_copy(doc, tmpl)

    surrounding_text = ""
    validation = {"is_relevant": True, "confidence": 0.8, "verdict": "relevant", "reason": ""}
    commit: Dict[str, Any] = {}

    try:
        import base64 as b64mod
        from docx import Document as DocxDoc
        from functions.image_relevance import evaluate_image_relevance

        docx = DocxDoc(working_copy)
        blip_ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
        r_ns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
        found = 0
        img_para_idx = None
        for pi, para in enumerate(docx.paragraphs):
            blips = list(para._element.iter(blip_ns))
            if not blips:
                continue
            if found == image_index:
                img_para_idx = pi
                embed = blips[0].get(r_ns)
                if embed and embed in docx.part.related_parts:
                    part = docx.part.related_parts[embed]
                    part._blob = content
                break
            found += 1

        if img_para_idx is not None:
            before_parts = []
            after_parts = []
            for j in range(max(0, img_para_idx - 4), img_para_idx):
                t = docx.paragraphs[j].text.strip()
                if t and not t.lower().startswith(("figure", "fig.", "image")):
                    before_parts.append(t)
            for j in range(img_para_idx + 1, min(len(docx.paragraphs), img_para_idx + 5)):
                t = docx.paragraphs[j].text.strip()
                if not t:
                    continue
                if t.lower().startswith(("figure", "fig.", "image")):
                    continue
                after_parts.append(t)
            surrounding_text = "\n".join(before_parts[-4:] + after_parts[:4])

        docx.save(working_copy)

        try:
            client = await _get_ai_client()
            await fix_image_captions(working_copy, client, {})
            from functions.image_relevance import recheck_image
            recheck = await recheck_image(
                client,
                b64mod.b64encode(content).decode("utf-8"),
                surrounding_text or doc["filename"],
                image_id,
            )
            validation = {
                "is_relevant": recheck.get("is_relevant", True),
                "is_ethical": recheck.get("is_ethical", True),
                "confidence": recheck.get("confidence", 0.8),
                "verdict": recheck.get("relevance", {}).get("verdict", "relevant"),
                "reason": recheck.get("relevance", {}).get("reason", ""),
                "cleared": recheck.get("cleared", False),
                "ethics": recheck.get("ethics", {}),
                "relevance": recheck.get("relevance", {}),
            }
        except Exception as cap_exc:
            print(f"[replace-image] validation/caption warning: {cap_exc}")

        # Refresh extracted preview image from working document
        try:
            from parser import parse_file
            from issue_utils import save_document_images
            doc_model = parse_file(working_copy, _filename_for_parse(working_copy, doc["filename"]))
            save_document_images(doc_model, document_id, UPLOAD_DIR)
        except Exception as img_exc:
            print(f"[replace-image] preview refresh warning: {img_exc}")

        commit = _commit_working_document(document_id, working_copy, doc)

    except Exception as exc:
        print(f"[replace-image] docx update warning: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to update document image: {exc}")

    is_relevant = bool(validation.get("is_relevant", True))
    is_ethical = bool(validation.get("is_ethical", True))
    cleared = bool(validation.get("cleared", is_relevant and is_ethical))
    confidence = float(validation.get("confidence", 0.8) or 0.8)

    return {
        "success": True,
        "status": "success",
        "cleared": cleared,
        "is_relevant": is_relevant,
        "is_ethical": is_ethical,
        "confidence": confidence,
        "image_id": image_id,
        "image_index": image_index,
        "image_path": rel_path,
        "message": "Image replaced and validated successfully" if is_relevant else "Image replaced but may still be irrelevant",
        "analysis_details": {
            "verdict": validation.get("verdict", "relevant"),
            "reason": validation.get("reason", ""),
            "recommendation": validation.get("reason", ""),
        },
        "document_blocks": commit.get("document_blocks", []),
    }


@app.post("/api/documents/{document_id}/remove-image", tags=["Documents"])
async def remove_image(
    document_id: int,
    image_index: int = Form(...),
    user_id: int = Query(None),
):
    """Remove an image (and nearby figure caption) from the working DOCX."""
    import re
    from docx import Document as DocxDoc
    from docx.oxml.ns import qn

    conn = get_db()
    cursor = conn.cursor()
    if user_id:
        cursor.execute(
            "SELECT * FROM documents WHERE id = ? AND user_id = ?",
            (document_id, user_id),
        )
    else:
        cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
    doc = cursor.fetchone()
    conn.close()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not _is_fixable_source(doc["file_path"]):
        raise HTTPException(
            status_code=400,
            detail="Image removal is only supported for DOCX/PDF/TXT files.",
        )

    tmpl = get_template_by_id(doc["template_id"])
    if not tmpl:
        raise HTTPException(status_code=400, detail="Template not found")

    working_copy = _ensure_formatted_working_copy(doc, tmpl)
    image_id = f"img{image_index}"
    removed_caption = False
    commit: Dict[str, Any] = {}

    blip_ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
    drawing_tag = qn("w:drawing")
    pict_tag = qn("w:pict")
    caption_re = re.compile(
        r"^(figure|fig\.?|image)\s*\d*\s*[:.\-–—]?",
        re.IGNORECASE,
    )

    try:
        docx = DocxDoc(working_copy)
        found = 0
        target_para = None
        for para in docx.paragraphs:
            if not list(para._element.iter(blip_ns)):
                continue
            if found == image_index:
                target_para = para
                break
            found += 1

        if target_para is None:
            raise HTTPException(
                status_code=404,
                detail=f"Image at index {image_index} not found in document",
            )

        para_el = target_para._element
        next_el = para_el.getnext()

        for tag in (drawing_tag, pict_tag):
            for node in list(para_el.iter(tag)):
                parent = node.getparent()
                if parent is not None:
                    parent.remove(node)

        remaining_text = "".join(
            (t.text or "") for t in para_el.iter(qn("w:t"))
        ).strip()
        still_has_image = bool(list(para_el.iter(blip_ns)))
        removed_caption = False

        if not remaining_text and not still_has_image:
            parent = para_el.getparent()
            if parent is not None:
                parent.remove(para_el)

        # Remove immediate following figure caption paragraph (if image-free)
        if next_el is not None and next_el.tag == qn("w:p"):
            next_text = "".join(
                (t.text or "") for t in next_el.iter(qn("w:t"))
            ).strip()
            next_has_image = bool(list(next_el.iter(blip_ns)))
            if (
                next_text
                and not next_has_image
                and caption_re.match(next_text)
            ):
                parent = next_el.getparent()
                if parent is not None:
                    parent.remove(next_el)
                    removed_caption = True

        docx.save(working_copy)
        commit = _commit_working_document(document_id, working_copy, doc)

    except HTTPException:
        raise
    except Exception as exc:
        print(f"[remove-image] error: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to remove document image: {exc}",
        )

    return {
        "success": True,
        "status": "success",
        "removed": True,
        "cleared": True,
        "image_id": image_id,
        "image_index": image_index,
        "removed_caption": removed_caption,
        "message": "Image removed from document",
        "document_blocks": commit.get("document_blocks", []),
    }


def _get_user_document(document_id: int, user_id: int):
    """Load document row and template; raise HTTPException if missing."""
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
    return doc, tmpl


# ═══════════════════════════════════════════════════════════════════════════════
# TOC / LOT / LOF — Word field generation
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/toc-check/{document_id}", tags=["Documents"])
def toc_check(document_id: int, user_id: int = Query(...)):
    """Analyze heading hierarchy and TOC/LOT/LOF field status."""
    from docx import Document as DocxDocument

    doc_row, tmpl = _get_user_document(document_id, user_id)
    working_copy = _ensure_formatted_working_copy(doc_row, tmpl)
    doc = DocxDocument(working_copy)
    status = analyze_document_lists(doc)
    status["status"] = "success"
    status["document_id"] = document_id
    return status


@app.post("/api/add-toc/{document_id}", tags=["Documents"])
def add_toc(document_id: int, user_id: int = Query(...)):
    """Insert a dynamic Word TOC field after headings have been styled."""
    doc_row, tmpl = _get_user_document(document_id, user_id)
    working_copy = _ensure_formatted_working_copy(doc_row, tmpl)

    from docx import Document as DocxDocument

    from docx_fields import _toc_field_is_unpopulated

    doc = DocxDocument(working_copy)
    if document_has_toc(doc) and not _toc_field_is_unpopulated(doc):
        raise HTTPException(status_code=409, detail={"message": "TOC already exists in document"})

    headings = collect_headings(doc)
    if not headings:
        raise HTTPException(
            status_code=422,
            detail={"message": "No headings found to build TOC"},
        )

    rules = tmpl.get("formatting_rules", {})
    toc_levels = str(rules.get("toc_levels", "1-3"))
    result = generate_document_lists(
        working_copy,
        rules,
        tmpl.get("required_sections", []),
        include_toc=True,
        include_lot=False,
        include_lof=False,
        toc_levels=toc_levels,
    )
    commit = _commit_working_document(document_id, working_copy, doc_row)
    return {
        "status": "success",
        "message": "TOC field inserted",
        "entry_count": result.get("entry_count", len(headings)),
        **result,
        **commit,
    }


@app.post("/api/apply-toc-style/{document_id}", tags=["Documents"])
def apply_toc_style(document_id: int, user_id: int = Query(...)):
    """Apply heading styles to TOC/LOT/LOF section titles."""
    from docx import Document as DocxDocument

    doc_row, tmpl = _get_user_document(document_id, user_id)
    working_copy = _ensure_formatted_working_copy(doc_row, tmpl)
    doc = DocxDocument(working_copy)

    if not document_has_toc(doc):
        raise HTTPException(status_code=409, detail={"message": "No TOC field found in document"})

    styled = apply_toc_heading_styles(doc)
    doc.save(working_copy)
    commit = _commit_working_document(document_id, working_copy, doc_row)
    return {
        "status": "success",
        "message": f"Applied styles to {styled} list heading(s)",
        "styled_headings": styled,
        **commit,
    }


@app.post("/api/add-lot/{document_id}", tags=["Documents"])
def add_lot(document_id: int, user_id: int = Query(...)):
    """Insert a dynamic List of Tables field (requires table captions)."""
    from docx import Document as DocxDocument

    from docx_fields import document_has_lot
    from table_processor import ensure_table_captions

    doc_row, tmpl = _get_user_document(document_id, user_id)
    working_copy = _ensure_formatted_working_copy(doc_row, tmpl)
    doc = DocxDocument(working_copy)

    if not doc.tables:
        raise HTTPException(status_code=422, detail={"message": "No tables found in document"})

    if document_has_lot(doc):
        raise HTTPException(status_code=409, detail={"message": "List of Tables already exists"})

    ensure_table_captions(doc)
    doc.save(working_copy)

    result = generate_document_lists(
        working_copy,
        tmpl.get("formatting_rules", {}),
        tmpl.get("required_sections", []),
        include_toc=False,
        include_lot=True,
        include_lof=False,
    )
    commit = _commit_working_document(document_id, working_copy, doc_row)
    return {"status": "success", "message": "List of Tables field inserted", **result, **commit}


@app.post("/api/add-lof/{document_id}", tags=["Documents"])
def add_lof(document_id: int, user_id: int = Query(...)):
    """Insert a dynamic List of Figures field (requires figure captions)."""
    from docx import Document as DocxDocument

    from docx_fields import count_figures, document_has_lof

    doc_row, tmpl = _get_user_document(document_id, user_id)
    working_copy = _ensure_formatted_working_copy(doc_row, tmpl)
    doc = DocxDocument(working_copy)

    if count_figures(doc) == 0:
        raise HTTPException(status_code=422, detail={"message": "No figures found in document"})

    if document_has_lof(doc):
        raise HTTPException(status_code=409, detail={"message": "List of Figures already exists"})

    result = generate_document_lists(
        working_copy,
        tmpl.get("formatting_rules", {}),
        tmpl.get("required_sections", []),
        include_toc=False,
        include_lot=False,
        include_lof=True,
    )
    commit = _commit_working_document(document_id, working_copy, doc_row)
    return {"status": "success", "message": "List of Figures field inserted", **result, **commit}


@app.post("/api/generate-document-lists/{document_id}", tags=["Documents"])
def generate_all_document_lists(
    document_id: int,
    user_id: int = Query(...),
    payload: Dict[str, Any] = Body(default={}),
):
    """Generate TOC, LOT, and/or LOF fields based on user-selected options."""
    doc_row, tmpl = _get_user_document(document_id, user_id)
    working_copy = _ensure_formatted_working_copy(doc_row, tmpl)
    rules = tmpl.get("formatting_rules", {})
    toc_levels = str(payload.get("toc_levels") or rules.get("toc_levels", "1-3"))

    include_toc = payload.get("include_toc", rules.get("include_toc", True))
    include_lot = payload.get("include_lot", rules.get("include_lot", True))
    include_lof = payload.get("include_lof", rules.get("include_lof", True))

    result = generate_document_lists(
        working_copy,
        rules,
        tmpl.get("required_sections", []),
        include_toc=bool(include_toc),
        include_lot=bool(include_lot),
        include_lof=bool(include_lof),
        toc_levels=toc_levels,
    )
    commit = _commit_working_document(document_id, working_copy, doc_row)
    return {
        "status": "success",
        "message": "Document lists generated",
        **result,
        **commit,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE DETECTION & FORMATTING
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/tables/detect/{document_id}", tags=["Documents"])
def tables_detect(document_id: int, user_id: int = Query(...)):
    """Detect tables and caption issues in the working document."""
    from docx import Document as DocxDocument

    doc_row, tmpl = _get_user_document(document_id, user_id)
    working_copy = _ensure_formatted_working_copy(doc_row, tmpl)
    doc = DocxDocument(working_copy)
    rules = tmpl.get("formatting_rules", {}) or {}
    tables = detect_tables(doc, rules)
    return {
        "status": "success",
        "document_id": document_id,
        "table_count": len(tables),
        "issue_count": sum(len(t.get("issues") or []) for t in tables),
        "tables": tables,
    }


@app.post("/api/tables/fill-cell/{document_id}", tags=["Documents"])
def tables_fill_cell(
    document_id: int,
    user_id: int = Query(...),
    payload: Dict[str, Any] = Body(default={}),
):
    """Fill a specific empty table cell with user-provided text."""
    from docx import Document as DocxDocument
    from services.table_config import get_table_format_config

    table_index = payload.get("table_index")
    row = payload.get("row")
    col = payload.get("col")
    text = payload.get("text")

    if table_index is None or row is None or col is None:
        raise HTTPException(
            status_code=400,
            detail="table_index, row, and col are required",
        )
    if text is None or not str(text).strip():
        raise HTTPException(status_code=400, detail="text must be a non-empty string")

    doc_row, tmpl = _get_user_document(document_id, user_id)
    working_copy = _ensure_formatted_working_copy(doc_row, tmpl)
    doc = DocxDocument(working_copy)
    style = get_table_format_config(tmpl.get("formatting_rules") or {}).get(
        "table_style", {}
    )

    try:
        result = fill_table_cell(
            doc,
            table_index=int(table_index),
            row=int(row),
            col=int(col),
            text=str(text),
            font_name=str(style.get("font_name") or "Times New Roman"),
            font_size=int(style.get("font_size") or 12),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    doc.save(working_copy)
    commit = _commit_working_document(document_id, working_copy, doc_row)
    return {
        "status": "success",
        "message": f"Filled cell at row {int(row) + 1}, column {int(col) + 1}",
        **result,
        **commit,
    }


@app.post("/api/tables/normalize-fonts/{document_id}", tags=["Documents"])
def tables_normalize_fonts(
    document_id: int,
    user_id: int = Query(...),
    payload: Dict[str, Any] = Body(default={}),
):
    """
    Normalize inconsistent cell fonts in a table to the template font
    (or to the dominant font of that table).
    """
    from docx import Document as DocxDocument
    from services.table_config import get_table_format_config

    table_index = payload.get("table_index")
    if table_index is None:
        raise HTTPException(status_code=400, detail="table_index is required")

    doc_row, tmpl = _get_user_document(document_id, user_id)
    working_copy = _ensure_formatted_working_copy(doc_row, tmpl)
    doc = DocxDocument(working_copy)
    idx = int(table_index)
    if idx < 0 or idx >= len(doc.tables):
        raise HTTPException(status_code=400, detail="table_index out of range")

    style = get_table_format_config(tmpl.get("formatting_rules") or {}).get(
        "table_style", {}
    )
    result = normalize_table_fonts(
        doc.tables[idx],
        font_name=str(
            payload.get("font_name")
            or style.get("font_name")
            or "Times New Roman"
        ),
        font_size=int(payload.get("font_size") or style.get("font_size") or 12),
        header_bold=bool(
            payload["header_bold"]
            if "header_bold" in payload
            else style.get("header_bold", False)
        ),
    )
    doc.save(working_copy)
    commit = _commit_working_document(document_id, working_copy, doc_row)
    return {
        "status": "success",
        "message": f"Normalized fonts in table {idx + 1}",
        "table_index": idx,
        **result,
        **commit,
    }


@app.post("/api/tables/format/{document_id}", tags=["Documents"])
def tables_format(
    document_id: int,
    user_id: int = Query(...),
    payload: Dict[str, Any] = Body(default={}),
):
    """Format selected tables using a preset and optional custom rules."""
    from docx import Document as DocxDocument

    doc_row, tmpl = _get_user_document(document_id, user_id)
    working_copy = _ensure_formatted_working_copy(doc_row, tmpl)
    doc = DocxDocument(working_copy)

    selected = set(payload.get("selected_indices", []))
    if not selected:
        raise HTTPException(status_code=400, detail="No tables selected")

    result = format_tables_in_document(
        doc,
        selected,
        preset=str(payload.get("preset", "academic")),
        custom_rules=payload.get("custom_rules"),
        add_captions=True,
        formatting_rules=tmpl.get("formatting_rules"),
    )
    doc.save(working_copy)
    commit = _commit_working_document(document_id, working_copy, doc_row)
    return {
        "status": "success",
        "formatted_tables": result.get("formatted_tables", []),
        **result,
        **commit,
    }


@app.post("/api/tables/format-with-template/{document_id}", tags=["Documents"])
def tables_format_with_template(
    document_id: int,
    user_id: int = Query(...),
    payload: Dict[str, Any] = Body(default={}),
):
    """
    Format selected (or all) tables using the full admin template rules:
    captions, numbering, references, visual styles, and List of Tables.
    """
    doc_row, tmpl = _get_user_document(document_id, user_id)
    working_copy = _ensure_formatted_working_copy(doc_row, tmpl)
    rules = tmpl.get("formatting_rules", {}) or {}

    selected_raw = payload.get("selected_indices")
    selected = set(selected_raw) if selected_raw else None

    output_path = os.path.join(OUTPUT_DIR, f"tables_formatted_{document_id}.docx")
    result = run_table_formatting_pipeline(
        working_copy,
        output_path,
        rules,
        selected_indices=selected,
    )
    os.makedirs(os.path.dirname(working_copy) or ".", exist_ok=True)
    shutil.copy2(output_path, working_copy)
    commit = _commit_working_document(document_id, working_copy, doc_row)
    return {
        "status": result.get("status", "success"),
        "template_name": tmpl.get("name", ""),
        "download_url": f"/api/format-tables/download/{document_id}",
        **result,
        **commit,
    }


@app.post("/api/format-tables/{document_id}", tags=["Documents"])
def format_tables_endpoint(document_id: int, user_id: int = Query(...)):
    """
    Full template-driven table pipeline for all body tables:
    captions, numbering, in-text refs, visual styles, List of Tables.
    """
    doc_row, tmpl = _get_user_document(document_id, user_id)
    working_copy = _ensure_formatted_working_copy(doc_row, tmpl)
    if not working_copy.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only DOCX files support table formatting.")

    rules = tmpl.get("formatting_rules", {}) or {}
    output_path = os.path.join(OUTPUT_DIR, f"tables_formatted_{document_id}.docx")
    result = run_table_formatting_pipeline(working_copy, output_path, rules)
    os.makedirs(os.path.dirname(working_copy) or ".", exist_ok=True)
    shutil.copy2(output_path, working_copy)
    commit = _commit_working_document(document_id, working_copy, doc_row)
    result["download_url"] = f"/api/format-tables/download/{document_id}"
    return {**result, **commit}


@app.get("/api/format-tables/download/{document_id}", tags=["Documents"])
def download_formatted_tables(document_id: int, user_id: int = Query(...)):
    """Download the last tables-formatted working document."""
    doc_row, _tmpl = _get_user_document(document_id, user_id)
    working_copy = os.path.join(UPLOAD_DIR, "working", f"doc_{document_id}_working.docx")
    path = working_copy if os.path.exists(working_copy) else doc_row["file_path"]
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Formatted document not found")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"tables_formatted_{document_id}.docx",
    )


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