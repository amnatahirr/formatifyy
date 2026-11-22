# Formatify — Exhaustive Functional Summary for Test Case Writing

**Generated for:** test-case design  
**Repo:** `formatify-new`  
**Stack:** FastAPI + SQLite backend · Flutter + Provider frontend  
**API base:** `http://localhost:8000` (Swagger: `/docs`)  
**DB file:** `backend/formatify.db`

This document inventories every distinct feature across backend and frontend. For each item it covers: location, purpose, trigger, inputs, outputs, dependencies, business logic, errors, auth, and suggested test scenarios.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Backend APIs / Endpoints](#2-backend-apis--endpoints)
3. [Frontend Components / Pages](#3-frontend-components--pages)
4. [Database Models / Schemas](#4-database-models--schemas)
5. [Background Jobs / Scheduled Tasks](#5-background-jobs--scheduled-tasks)
6. [Third-party Integrations](#6-third-party-integrations)
7. [Utility / Helper Functions](#7-utility--helper-functions)
8. [State Management](#8-state-management)
9. [Analysis Pipeline Internals](#9-analysis-pipeline-internals)
10. [Cross-cutting Auth & Multi-tenancy](#10-cross-cutting-auth--multi-tenancy)
11. [Priority Test Matrix](#11-priority-test-matrix)

---

## 1. System Overview

Formatify is a multi-tenant academic document formatting and FYP collaboration platform.

| Module | Capability |
|--------|------------|
| **Core** | Upload DOCX/PDF/TXT, AI analysis (grammar, formatting, images, relevance, plagiarism), apply fixes, TOC/LOT/LOF, tables, frontmatter, export |
| **FYP** | Student–supervisor assignment, milestones, final submissions, document review comments, plagiarism monitor, meeting notes, semester deadlines |
| **Collaboration (VC)** | Multi-author section projects, commits, WebSocket presence, merge/conflicts, invite email |
| **Admin** | Departments, supervisors, templates, deadlines, analytics, frontmatter branding, verify uploads |
| **Super Admin** | Organizations CRUD, plans/modules, document limits, API key reset |

**Roles:** `student` · `admin` · `supervisor` · platform super-admin (header key)  
**Org modules:** `core`, `fyp` (comma-separated on `organizations.modules`)

**Seeded defaults (dev):**
- Org: `COMSATS-LHR`, api_key `fmt_live_comsats_default`, modules `core,fyp`
- Users: `admin@comsats.edu.pk`/`admin123`, `student@…`/`student123`, `supervisor@…`/`supervisor123`
- University: COMSATS (id=1); Departments: CS, EE, SE, MBA

---

## 2. Backend APIs / Endpoints

**Auth legend used below:**
- **Public** — no login
- **Org** — org resolved via JWT / `X-Org-Code` / legacy API key / default org 1
- **user_id** — query `user_id` + ownership/role checks (many routes do **not** cryptographically bind JWT to `user_id`)
- **Admin / Supervisor / Student** — role helpers
- **SuperAdmin** — `X-Super-Admin-Key`
- **FYP** — org must include `fyp` module (middleware gate)

---

### 2.1 App bootstrap — `backend/main.py`

| Item | Detail |
|------|--------|
| App | `FastAPI(title="FORMATIFY API", version="3.0.0")` |
| CORS | `allow_origins=["*"]`, all methods/headers/credentials |
| Middleware | `OrganizationMiddleware` |
| Static | `/uploads` → `UPLOAD_DIR` |
| Startup | `init_db()`; preload BLIP+CLIP vision models in thread |
| In-memory | `_jobs: Dict` (analyze job_id → report/path); lost on restart |
| AI client | Prefer `GEMINI_API_KEY` → `GeminiClientAdapter`; else Anthropic Claude (`ANALYSIS_MODEL`) |

**Routers mounted:**

| Prefix | Source |
|--------|--------|
| `/api/vc` | `vc/routes.py` |
| `/api/admin` | `admin_routes.py` |
| `/api/supervisor` | `supervisor_routes.py` |
| `/api/student` | `student_routes.py` |
| `/api/admin/templates` | `template_extract_routes.py` |
| `/api/documents` | `frontmatter_routes.py` |
| `/api/super-admin` | `super_admin_routes.py` |
| `/api/auth` | Google Drive auth (`google_drive_routes.auth_router`) |
| `/api/uploads` | Google Drive uploads (`google_drive_routes.uploads_router`) |

---

### 2.2 Health / Org / Universities

#### Feature: Health check
1. **Location:** `main.py` — `health_check`
2. **Purpose:** Liveness probe
3. **Trigger:** `GET /health`, `GET /api/health`
4. **Inputs:** none
5. **Outputs:** `{status, version}`
6. **Dependencies:** none
7. **Business logic:** static response
8. **Errors:** none expected
9. **Auth:** Public
10. **Suggested tests:** (1) 200 + version. (2) Works without auth. (3) Both path aliases return same. (4) Survives after DB init.

#### Feature: Plagiarism corpus status
1. **Location:** `main.py`
2. **Purpose:** Inspect/rebuild FYP plagiarism index readiness
3. **Trigger:** `GET /api/plagiarism/corpus-status?rebuild=bool`
4. **Inputs:** `rebuild` (bool, optional, default false)
5. **Outputs:** enabled, dirs, document/hash counts, ready/error
6. **Dependencies:** `plagiarism.corpus_index`, env `PLAGIARISM_*`
7. **Business logic:** if `rebuild=true`, rebuild MinHash/FAISS
8. **Errors:** returns error field if index missing/corrupt
9. **Auth:** Public
10. **Suggested tests:** (1) Status when corpus empty. (2) Status when indexed. (3) Rebuild succeeds. (4) Rebuild with missing dir.

#### Feature: Resolve organization
1. **Location:** `main.py` — org resolve handlers; `middleware/org_middleware.py` — `public_org_payload`
2. **Purpose:** Login gate — validate org code before auth UI
3. **Trigger:** `GET /api/org/resolve?code=` (alias `/org/resolve`)
4. **Inputs:** `code` (string, required)
5. **Outputs:** public org payload (name, code, plan, modules, branding) — **never** `api_key`
6. **Dependencies:** `organizations` table
7. **Business logic:** case-insensitive code lookup; inactive → 403
8. **Errors:** 404 unknown; 403 inactive
9. **Auth:** Public
10. **Suggested tests:** (1) Valid code. (2) Invalid code 404. (3) Inactive org 403. (4) Response has no `api_key`.

#### Feature: Org info (authenticated context)
1. **Location:** `main.py`
2. **Trigger:** `GET /api/org/info` (alias `/org/info`)
3. **Inputs:** org from middleware (JWT / headers)
4. **Outputs:** branding + modules for current tenant
5. **Auth:** Org-scoped
6. **Suggested tests:** (1) JWT returns correct org. (2) `X-Org-Code` works. (3) Default org when bare.

#### Feature: Universities list / get
1. **Location:** `main.py`
2. **Trigger:** `GET /api/universities`, `GET /api/universities/{id}`
3. **Inputs:** path `university_id` for get
4. **Outputs:** list or single `{id, name, country, …}`
5. **Errors:** 404 for missing id
6. **Auth:** Public
7. **Suggested tests:** (1) Seeded COMSATS present. (2) Unknown id 404. (3) List non-empty after init.

---

### 2.3 Auth — `backend/main.py` + `auth_jwt.py`

#### Feature: Signup
1. **Location:** `main.py` — signup; models `UserSignupRequest`
2. **Purpose:** Self-register student in an org
3. **Trigger:** `POST /api/auth/signup`
4. **Inputs (JSON):**
   | Field | Type | Required | Notes |
   |-------|------|----------|-------|
   | username | str | yes | unique per org |
   | email | str | yes | unique per org |
   | password | str | yes | hashed SHA256+fixed salt |
   | university_id | int | no | default 1 |
   | department_id | int | yes | must exist in org |
   | current_semester | int? | conditional | required for university+FYP plans (6 or 7) |
   | org_code | str? | no | resolves tenant |
5. **Outputs:** user profile + `access_token` (JWT); inserts `users` role=`student`
6. **Dependencies:** `hash_password`, `create_access_token`, org middleware
7. **Business logic:** semester validation; uniqueness scoped by `org_id`
8. **Errors:** 400 bad semester/dept; 409 email/username taken
9. **Auth:** Public + org resolve
10. **Suggested tests:** (1) Happy signup → JWT. (2) Duplicate email same org 409. (3) Same email different org allowed. (4) University FYP without semester 400.

#### Feature: List departments (signup)
1. **Trigger:** `GET /api/auth/departments?org_code=`
2. **Outputs:** `{departments: [...], count}`
3. **Suggested tests:** (1) Default org depts. (2) Org-specific depts. (3) Unknown org falls back/handles.

#### Feature: Login
1. **Trigger:** `POST /api/auth/login`
2. **Inputs:** `{email, password, org_code?}`
3. **Outputs:** profile fields + JWT (`sub`, `user_id`, `org_id`, `role`, `email`, `org_code`, 7-day exp)
4. **Errors:** 401 invalid credentials / wrong org
5. **Auth:** Public + org
6. **Suggested tests:** (1) Valid credentials. (2) Wrong password. (3) User from other org with wrong org_code. (4) JWT claims match user.

#### Feature: Me / Change password
1. **Triggers:** `GET /api/auth/me?user_id=`; `POST /api/auth/change-password`
2. **Change password inputs:** `user_id`, `current_password`, `new_password` (≥6 chars)
3. **Errors:** 401/403/404
4. **Suggested tests:** (1) Me returns profile for matching org. (2) Wrong org user_id 403. (3) Change password success then login. (4) New password too short rejected.

#### Feature: JWT helpers — `auth_jwt.py`
| Function | Behavior |
|----------|----------|
| `create_access_token` | HS256; 7 days default |
| `decode_access_token` | 401 expired/invalid |
| `bearer_token_from_header` | Parse `Authorization: Bearer` |
| `looks_like_jwt` | Rejects `fmt_live_*` API keys |

Secret order: `JWT_SECRET` → `SUPER_ADMIN_KEY` → hard-coded dev string.

---

### 2.4 Templates

#### Feature: List / get templates
1. **Location:** `main.py`, `templates.py`
2. **Triggers:**
   - `GET /api/templates` (org-scoped; hides `__freeform_placeholder__`)
   - `GET /api/templates/user/{user_id}`
   - `GET /api/templates/university/{university_id}`
   - `GET /api/templates/{template_id}`
3. **Outputs:** template rows with `required_sections` JSON, `formatting_rules` JSON
4. **Errors:** 404
5. **Suggested tests:** (1) List excludes freeform placeholder. (2) Get by id. (3) Org isolation. (4) University filter.

#### Feature: Image / table format defaults
1. **Triggers:** `GET /api/templates/image-format-defaults`, `…/table-format-defaults`
2. **Outputs:** `DEFAULT_IMAGE_FORMAT_RULES` / `DEFAULT_TABLE_FORMAT_RULES`
3. **Auth:** Public
4. **Suggested tests:** (1) Schema keys present. (2) Stable defaults used by template form.

#### Feature: Admin create / update / delete template
1. **Triggers:** `POST /api/admin/templates`, `PUT /api/admin/templates/{id}`, `DELETE /api/admin/templates/{id}`
2. **Create body:** `TemplateCreateRequest` — `name`, `description?`, `required_sections[]`, `formatting_rules{}`
3. **Query:** `created_by`/`user_id`, `university_id`, `department_id`
4. **Business logic:** validates table rules; delete blocked for template ids 1–3
5. **Errors:** 403 protected ids; 404; validation errors
6. **Suggested tests:** (1) Create with sections+rules. (2) Update rules. (3) Delete custom OK. (4) Delete id 1–3 → 403.

#### Feature: Extract template from document
1. **Location:** `template_extract_routes.py`, `template_extract.py`
2. **Trigger:** `POST /api/admin/templates/extract-from-document` (multipart DOCX)
3. **Outputs:** draft template JSON — **does not persist**
4. **Dependencies:** Anthropic Claude (`ANTHROPIC_API_KEY` required)
5. **Errors:** 400 bad file; 503 no key; 502 LLM failure
6. **Auth:** Weak/public-ish (optional admin)
7. **Suggested tests:** (1) Valid guideline DOCX → draft. (2) Non-DOCX 400. (3) Missing API key 503. (4) Draft not in DB until save.

---

### 2.5 One-shot analyze / download (stateless jobs)

#### Feature: Analyze (multipart)
1. **Location:** `main.py` — analyze + `_run_analysis`
2. **Purpose:** Quick analyze without persisting a `documents` row (stores `_jobs`)
3. **Trigger:** `POST /api/analyze` (alias `/analyze`)
4. **Inputs:** multipart `template` (name/id), `file?` OR `text?`
5. **Outputs:** `AnalysisReport` + `job_id`
6. **Side effects:** save upload; run pipeline; write `outputs/formatted_{job_id}.docx`
7. **Pipeline:** parse → strip frontmatter → batch → dispatch agents ∥ corpus plagiarism → aggregate → reformat
8. **Errors:** 400 no content/bad ext/unknown template; 500 no AI key
9. **Auth:** Public
10. **Suggested tests:** (1) DOCX → issues+job_id. (2) Text-only. (3) Bad extension. (4) Download via job_id.

#### Feature: Download formatted by job_id
1. **Trigger:** `GET /api/download/{job_id}`
2. **Outputs:** DOCX `FileResponse`
3. **Errors:** 404 if job expired/missing (in-memory)
4. **Suggested tests:** (1) After analyze. (2) Unknown job 404. (3) After process restart 404.

---

### 2.6 Documents lifecycle — `backend/main.py`

#### Feature: List documents
1. **Trigger:** `GET /api/documents/?user_id=`
2. **Outputs:** id, filename, status, template, file_size, …
3. **Auth:** user_id ownership
4. **Suggested tests:** (1) Empty list. (2) After uploads. (3) Other user’s docs not returned.

#### Feature: Upload file document
1. **Trigger:** `POST /api/documents/upload`
2. **Inputs:** multipart `file`, `template_id`, `user_id`; org from middleware
3. **Outputs:** `{document_id, status: "pending"}`
4. **Side effects:** file under `uploads/`; `documents` row; org document usage may apply via middleware gate
5. **Errors:** 400 bad template/org mismatch; file errors
6. **Suggested tests:** (1) Happy upload. (2) Template from other org rejected. (3) Unsupported type. (4) Document limit 403.

#### Feature: Upload text / create report
1. **Triggers:** `POST /api/documents/upload-text`, `POST /api/documents/create-report`
2. **Inputs:** body content/title; `template_id`
3. **Errors:** 400 empty content
4. **Suggested tests:** (1) Paste creates doc. (2) Empty content 400. (3) create-report alias behaves same.

#### Feature: Freeform upload (admin/supervisor only)
1. **Triggers:** `POST /api/documents/upload-freeform`, `…/upload-text-freeform`
2. **Business logic:** `is_freeform=1`; **students → 403**
3. **Analyze:** `GET /api/documents/analyze-freeform/{id}` — no template, no silent reformat; uses `dispatch_freeform`
4. **Mutual exclusion:** templated analyze on freeform doc → 400 and vice versa
5. **Suggested tests:** (1) Admin freeform OK. (2) Student 403. (3) analyze-freeform returns suggested fixes. (4) Calling templated analyze on freeform → 400.

#### Feature: Analyze document (templated)
1. **Trigger:** `GET /api/documents/analyze/{document_id}?user_id=`
2. **Outputs:** full report, content/style issues, heading matches, bullets, document blocks
3. **Side effects:** rebuilds working copy under `uploads/working/`; may sync VC reports
4. **Errors:** 404; 400 if freeform; ownership 403/404
5. **Suggested tests:** (1) Pending → analyzed with issues. (2) Owner-only. (3) Freeform doc rejected. (4) Working copy exists after.

#### Feature: Delete document
1. **Trigger:** `DELETE /api/documents/{id}?user_id=`
2. **Side effects:** DB row + file + working copy removed
3. **Suggested tests:** (1) Delete own. (2) Delete other user’s 404. (3) Files gone from disk.

---

### 2.7 Heading / style / content fixes

#### Feature: Heading analysis (stateless)
1. **Trigger:** `POST /api/heading-analysis` body `{template, blocks}`
2. **Outputs:** deterministic heading matches / issues
3. **Location:** `heading_analysis.py`
4. **Suggested tests:** (1) Matching headings. (2) Missing required section. (3) Inferred heading flagged needs_review.

#### Feature: Heading decision
1. **Trigger:** `POST /api/documents/heading-decision/{id}`
2. **Body:** `{paragraph_id, decision: "keep"|"discard", heading_level?, apply_style?}`
3. **Side effects:** decisions JSON file; apply Heading style or demote to body; renumber prefixes
4. **Deps:** `content_fixer.py`, `docx_styles.py`
5. **Suggested tests:** (1) Keep → becomes Heading N. (2) Discard → Normal. (3) Invalid paragraph_id. (4) Persist decision across reload.

#### Feature: Apply all style fixes
1. **Trigger:** `POST /api/documents/apply-all-style-fixes/{id}`
2. **Effects:** reformat working copy + frontmatter pages
3. **Suggested tests:** (1) Margins/fonts applied. (2) Owner required. (3) Idempotent re-run.

#### Feature: Apply list / content / all fixes
1. **Triggers:**
   - `POST …/apply-fix/{id}?fix_type=apply_section_bullets` body `{para_indices}`
   - `POST …/apply-content-fix/{id}` — fix_type heading/bullets/formatting/text + fields
   - `POST …/apply-all-fixes/{id}` body `{fixes[], include_toc?, include_lot?, include_lof?, toc_levels?}`
2. **Side effects:** mutate working DOCX; commit; optional TOC/LOT/LOF generation
3. **Business logic:** list fixes are safety-gated (skip unsafe groups — see `list_detection.py` / tests)
4. **Suggested tests:** (1) Single text fix. (2) Apply-all with mixed fixes. (3) Unsafe list group skipped. (4) TOC flags generate lists.

---

### 2.8 Images

#### Feature: Format images pipeline
1. **Location:** `services/image_formatting_service.py` + caption/numbering/ref/LOF services
2. **Trigger:** `POST /api/format-images/{id}` (legacy: `…/legacy` uses AI captions+resize)
3. **Outputs:** formatted working doc; download via `GET /api/format-images/download/{id}`
4. **Suggested tests:** (1) Captions numbered sequentially. (2) Broken in-text refs flagged. (3) LOF regenerated. (4) Legacy path still works.

#### Feature: Analyze bullets
1. **Trigger:** `GET /api/documents/analyze-bullets/{id}`
2. **Outputs:** list style groups / conversion candidates
3. **Suggested tests:** (1) Parallel dashes detected. (2) Already-list paragraphs skipped. (3) Empty doc.

#### Feature: Recheck / replace / remove image
1. **Triggers:**
   - `POST …/recheck-image/{id}` `{image_base64, image_id, surrounding_text}`
   - `POST …/{id}/replace-image` Form: `image_index`, `file`
   - `POST …/{id}/remove-image` Form: `image_index`
2. **Business logic:** replace validates ethics (BLIP keywords) + CLIP relevance; remove drops adjacent caption
3. **Deps:** `functions/image_ethics.py`, `image_relevance.py`, `local_vision.py`
4. **Suggested tests:** (1) Relevant replace accepted. (2) Unsafe image rejected/flagged. (3) Remove clears caption. (4) Bad index error.

---

### 2.9 Preview / export / TOC / LOT / LOF / tables

#### Feature: Preview elements
1. **Trigger:** `GET /api/format-document/from-document/{id}?user_id=`
2. **Outputs:** ordered text+type elements for UI preview

#### Feature: Export document
1. **Trigger:** `GET /api/format-document/export/{id}?format=docx|pdf&user_id=`
2. **Side effects:** applies frontmatter pages; PDF via LibreOffice if available
3. **Suggested tests:** (1) DOCX export. (2) PDF when LibreOffice present. (3) PDF graceful fail without LO. (4) Frontmatter included when generated.

#### Feature: TOC / LOT / LOF
| Endpoint | Behavior | Key errors |
|----------|----------|------------|
| `GET /api/toc-check/{id}` | Heading/list field status | — |
| `POST /api/add-toc/{id}` | Insert TOC field | 409 exists; 422 no headings |
| `POST /api/apply-toc-style/{id}` | Style existing TOC | 409 no TOC |
| `POST /api/add-lot/{id}` | List of tables | 422 no tables |
| `POST /api/add-lof/{id}` | List of figures | 422 no figures |
| `POST /api/generate-document-lists/{id}` | Body toggles toc/lot/lof | combined |

**Location:** `docx_fields.py`, `list_of_*_service.py`  
**Suggested tests:** (1) Add TOC when headings exist. (2) Duplicate TOC 409. (3) LOT without tables 422. (4) Combined generate respects flags.

#### Feature: Tables
| Endpoint | Purpose |
|----------|---------|
| `GET /api/tables/detect/{id}` | Detect tables + issues |
| `POST /api/tables/fill-cell/{id}` | `{table_index, row, col, text}` |
| `POST /api/tables/normalize-fonts/{id}` | `{table_index, font?}` |
| `POST /api/tables/format/{id}` | `{selected_indices, preset}` |
| `POST /api/tables/format-with-template/{id}` | Full template pipeline |
| `POST /api/format-tables/{id}` | Format all body tables |
| `GET /api/format-tables/download/{id}` | Download result |

**Location:** `table_processor.py`, `services/table_*`  
**Suggested tests:** (1) Detect N tables. (2) Fill cell persists. (3) Format-with-template captions+LOT. (4) Invalid table_index.

---

### 2.10 Frontmatter — `frontmatter_routes.py`

#### Feature: Analyze frontmatter
1. **Trigger:** `POST /api/documents/{id}/frontmatter/analyze?user_id=`
2. **Outputs:** `DetectionResult` persisted on document (`frontmatter_detection`)
3. **Deps:** `frontmatter_detector.py`, optional LLM `frontmatter_classify.py`
4. **Suggested tests:** (1) Cover+info present. (2) Missing pages low confidence. (3) Persisted for generate.

#### Feature: Generate frontmatter
1. **Trigger:** `POST /api/documents/{id}/frontmatter/generate`
2. **Body (`FrontmatterGenerateRequest`):** `group_id?`, `domains?`, `signature_path?`, `generate_cover?`, `generate_info?`
3. **Side effects:** merge cover/info pages into working+export DOCX; uses admin branding templates/logo
4. **Business logic:** auto-analyze if no detection; partial generation by flags or missing pages only
5. **Errors:** needs DOCX working/upload
6. **Suggested tests:** (1) Generate both pages. (2) Generate cover only. (3) Pulls FYP group members when `group_id` set. (4) Uses admin logo/session config.

---

### 2.11 Admin API — `admin_routes.py` (`/api/admin`)

Auth: optional `user_id` → `_require_admin` when provided. Org from middleware. FYP-prefixed paths gated by module.

| Method | Path | Purpose | Key inputs |
|--------|------|---------|------------|
| GET | `/stats` | Counts | — |
| GET | `/overview` | Dashboard aggregates | — |
| GET | `/users` | Org users | — |
| GET/POST/PUT/DELETE | `/departments[/{id}]` | Dept CRUD | name, code, min/max_members, max_groups_per_supervisor |
| GET | `/supervisors` | List | department_id?, search? |
| POST | `/supervisors` | Create + link user | name, email, department_id, max_groups; **SMTP email** with temp password |
| POST | `/supervisors/{id}/send-credentials` | Reset+email | temporary_password? |
| PUT/PATCH/DELETE | `/supervisors/{id}` | Update / toggle / delete | org-scoped |
| GET | `/templates` | Admin template list | department_id? |
| GET/POST/PUT/DELETE | `/deadlines[/{id}]` | Dept deadlines | title, due_date, department_id, applies_to_all |
| GET/POST/PATCH | `/semester-deadlines[/{id}]` | Sem 6\|7 cutoffs | semester, deadline_date |
| GET | `/analytics` | Docs/7d, top templates, issues, dept scores | — |
| GET | `/universities` | List | — |
| GET/PUT | `/settings` | Org settings | system_name, notifications, rate limits… (keys `org:{id}:{key}`) |
| GET/PUT | `/frontmatter-config` | Branding text | university_name, department_name, session |
| POST | `/frontmatter-config/logo` | Logo image | multipart → `uploads/branding/` |
| POST | `/frontmatter-config/templates/{kind}` | kind=`cover`\|`info` DOCX | overwrites generator templates |

**Business rules:**
- Delete department blocked if supervisors exist
- Supervisor create creates/links `users.role=supervisor`
- Frontmatter-config is **core** (not FYP-gated); supervisors/deadlines/semester-deadlines **are** FYP-gated

**Suggested tests:**
1. Create department → list includes it.
2. Create supervisor → user can login + email attempted.
3. Delete dept with supervisors → blocked.
4. Org without `fyp` → `/supervisors` 403 but `/frontmatter-config` OK.
5. Semester deadline unique per (semester, org).
6. Non-admin `user_id` → 403.

---

### 2.12 Student FYP API — `student_routes.py` (`/api/student`)

Auth: `_require_student(user_id)` + FYP module.

| Method | Path | Purpose / validation |
|--------|------|----------------------|
| GET | `/meeting-notes` | All notes for student’s groups |
| GET | `/groups/{id}/meeting-notes` | Membership-checked |
| GET | `/groups/{id}/milestones` | Checklist + progress |
| GET | `/supervisors` | Active supervisors (+ depts) in org |
| GET | `/assignment-requests/status` | email or user_id → pending/accepted |
| GET | `/assignment-requests` | Student’s requests |
| POST | `/assignment-requests` | supervisor_id, group_name, project_title?, member_names, cosupervisor?, department_id?; blocks inactive/full/duplicate pending; email must match login |
| GET | `/semester-deadline` | From group semester or `user.current_semester` |
| POST | `/final-submissions` | group_id, title, filename?, source_document_id?, analysis_report?; **403 `deadline_passed`**; creates group_document + paragraphs |
| GET | `/final-submissions/{id}/plagiarism` | Plagiarism from report |
| GET | `/groups/{id}/plagiarism` | Group plagiarism view |
| GET | `/groups/{id}/submissions` | Status tracker |
| GET | `/groups/{id}/documents/{doc_id}/comments` | Review comments |
| POST | `/comments/{id}/resolve` | Student resolve |
| POST | `/comments/{id}/reply` | Reply thread |
| GET | `/notifications` | Inbox |
| PATCH | `/notifications/{id}/read` | Mark read |

**Suggested tests:**
1. Assignment request happy path.
2. Duplicate pending request blocked.
3. Full supervisor capacity blocked.
4. Final submit after deadline → 403 `deadline_passed`.
5. Non-member cannot read group meeting notes.
6. Mark notification read only for owner.

---

### 2.13 Supervisor FYP API — `supervisor_routes.py` (`/api/supervisor`)

Auth: `_require_supervisor` resolves `supervisors` row by user email. FYP module required.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/home` | Dashboard cards |
| GET | `/groups` | filter=`all\|on_track\|behind` |
| GET | `/groups/{id}` | Detail + docs/milestones |
| POST | `/groups/{id}/discard` | Soft discard + notify students |
| GET | `/assignment-requests` | status filter (default pending) |
| POST | `/assignment-requests/{id}/accept` | Creates `fyp_group` + default milestones + notification; profile mismatch warnings |
| POST | `/assignment-requests/{id}/reject` | Body reason **required** |
| GET | `…/documents/{d}/review` | Paragraphs + comments |
| POST | `…/paragraphs/{p}/comments` | `{comment_text}` |
| POST | `…/paragraphs/{p}/resolve` | Resolve comments |
| GET | `/submissions` | Final submissions by status |
| GET | `/submissions/{id}` | Detail + analysis_report |
| GET | `/submissions/{id}/download` | File |
| GET | `/groups/{g}/documents/{d}/download` | File |
| POST | `/submissions/{id}/approve` | note optional |
| POST | `/submissions/{id}/request-revision` | note **required** |
| POST | `/submissions/{id}/reject` | reason **required** |
| GET | `/plagiarism-monitor` | Flagged/risk groups |
| GET/POST | `/plagiarism-monitor/{group_id}[/flag]` | Detail / flag reason |
| GET/POST | `/groups/{id}/meeting-notes` | List / create (`meeting_date`, `topic`, `action_items`) |
| GET | `/notifications` | Inbox |
| POST | `/notifications/{id}/read` | Mark read |

**Suggested tests:**
1. Accept request → group + milestones + student notification.
2. Reject without reason → 400.
3. Comment on paragraph → student sees in comments API.
4. Approve / revision / reject status transitions.
5. Discard group notifies members.
6. Student cannot call supervisor endpoints (403).

---

### 2.14 Super Admin — `super_admin_routes.py` (`/api/super-admin`)

Auth: header `X-Super-Admin-Key` == `SUPER_ADMIN_KEY`.

| Method | Path | Body highlights | Effects |
|--------|------|-----------------|---------|
| GET | `/organizations` | — | List (no api_key in payload) |
| GET | `/admins` | — | All admin users |
| POST | `/organizations` | name, code, type, plan, modules, documents_limit, admin_* | Org + optional admin; password returned **once** |
| PUT | `/organizations/{id}` | fields | Update + sync `organization_modules` |
| PATCH | `/organizations/{id}/toggle` | — | Flip `is_active` |
| DELETE | `/organizations/{id}` | — | Purge tenant data; **cannot delete id=1** |
| GET | `/organizations/{id}/stats` | — | Counts |
| GET | `/stats` | — | Platform rollup + revenue_estimate |
| POST | `/organizations/{id}/reset-key` | — | Regen `fmt_live_*` |

**Suggested tests:**
1. Wrong key → 401.
2. Create university+fyp org + admin login works with org code.
3. Toggle inactive → org resolve 403.
4. Delete org 1 → rejected.
5. Delete custom org purges users/docs.
6. Reset key invalidates old API key.

---

### 2.15 Version Control — `vc/routes.py` (`/api/vc`)

Auth: `user_id` + membership checks in `vc/service.py`.

| Method | Path | Body | Effects |
|--------|------|------|---------|
| POST | `/projects` | Form: name, description, template_id, file? | Create; optional DOCX section seed |
| GET | `/projects` | — | List for user |
| GET | `/projects/{id}` | — | Detail |
| POST | `/projects/{id}/document` | DOCX | Re-extract sections as commits |
| POST | `/projects/join` | `{invite_code}` | Join |
| POST | `/projects/{id}/invite` | `{email}` | Invite + SMTP (`vc/invite_mail.py`) |
| GET | `/projects/{id}/history` | — | Project history |
| CRUD | `/projects/{id}/sections/{sid}/images[/{image_id}]` | file | List/upload/delete/get |
| GET | `/projects/{id}/sections[/{sid}]` | — | Section state |
| POST | `…/sections/{sid}/commit` | `{content, message?}` | Commit + **WS broadcast** |
| GET | `…/history` | — | Section history |
| POST | `…/rollback` | `{commit_id}` | Rollback + WS |
| POST | `/projects/{id}/merge` | — | Detect conflicts |
| GET | `/projects/{id}/merge/{mid}` | — | Status |
| POST | `…/resolve/{cid}` | `{resolution_content}` | Resolve conflict |
| POST | `…/complete` | — | Assemble DOCX + run analysis |
| GET | `/projects/{id}/download` | merge_id? | FileResponse |
| WS | `/ws/projects/{id}?user_id=` | ping→pong | Presence; close **4003** if not member |

**Internals:** `vc/docx_import.py`, `conflicts.py`, `merge.py`, `reports_sync.py`, `websocket.py`, `utils.py`

**Suggested tests:**
1. Create with template + file → sections populated.
2. Join via invite code.
3. Commit broadcasts to other WS client.
4. Non-member WS → 4003.
5. Merge with conflict → resolve → complete → download.
6. Invite email when SMTP configured (or graceful skip).

---

### 2.16 Google Drive — `services/google_drive_routes.py` + `google_drive_service.py`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/auth/google/authorize` | OAuth URL (`link_to_user_id?`) |
| GET | `/api/auth/google/callback` | Store tokens; may create user org1 if not linking |
| GET | `/api/auth/google/status` | Pop first authenticated session (in-memory, racey) |
| GET | `/api/auth/google/debug/tokens` | Token meta for user_id |
| GET | `/api/auth/google/drive-picker` | Picker URL |
| POST | `/api/uploads/google-drive/auth/init` | Check authorized |
| GET | `/api/uploads/google-drive/files` | List (`query?`) |
| POST | `/api/uploads/google-drive/import` | `file_id`, `template_id` → create document + sync status |
| POST | `/api/uploads/download-from-google-drive` | Same import path |

**Allowed types:** PDF/DOCX/DOC/TXT + Google Docs export. **Rejects** Sheets/Slides.

**Suggested tests:**
1. Authorize URL contains client_id.
2. Import Google Doc → documents row.
3. Sheets/Slides rejected.
4. Unauthenticated list → 401.
5. Token refresh on expiry.

---

## 3. Frontend Components / Pages

**Stack:** Flutter · Provider (`ChangeNotifier`) · `http`  
**~133 Dart files** under `frontend/lib/`  
**Auth:** JWT Bearer (`AuthTokenStore`) + org code (`DevUserConfig`)  
**Deep links:** `formatify://qr-upload?session=&host=`, `formatify://qr-download?id=&host=` (ignored if logged out)

**Named routes (`main.dart`):** `/login`, `/student-dashboard`, `/admin-dashboard`, `/supervisor-dashboard`, `/super-admin`, `/new-report`, `/collaboration`, `/collaboration/project`

---

### 3.1 App bootstrap — `lib/main.dart`

| Feature | Detail |
|---------|--------|
| Entry | `MyApp` → `AuthCheck` |
| Cold start | `AuthProvider.ensureCleanLaunch` clears session (restore exists but unused) |
| Role routing | student → `StudentDashboard`; admin → `AdminDashboard`; supervisor → `SupervisorDashboard` |
| Dev bootstrap | `--dart-define=USER_ID=member1|member2` + `ENABLE_DEV_BOOTSTRAP=true` |

**Suggested tests:** (1) Cold start → login. (2) Each role → correct shell. (3) Deep link logged out ignored. (4) Theme binds per user.

---

### 3.2 Config — `lib/config/`

| File | Purpose |
|------|---------|
| `api_config.dart` | `baseUrl` / `imageBaseUrl`, Bearer headers, WS URL |
| `dev_user_config.dart` | Tenant flags, modules, university vs company signup, `hasFypModule` / `hasCoreModule`, super-admin key |

**Caveat:** Hardcoded LAN IPs (`ApiConfig`, QR services) — devices must match network.

**Suggested tests:** (1) Headers include Bearer when token set. (2) FYP module false hides FYP nav. (3) University vs company signup field differences.

---

### 3.3 Auth & login — `lib/screens/login_screen.dart`

1. **Feature:** Multi-step org gate → login / signup  
2. **Purpose:** Tenant selection + authentication  
3. **Trigger:** App start when logged out; logout  
4. **Inputs:** Org code; email/password; signup: name, dept, optional semester 6/7; Remember me  
5. **Outputs:** JWT + profile; navigate via `AuthCheck`  
6. **Deps:** `AuthProvider`, `SuperAdminApiService.resolveOrganization`, `LoginCredentialsStore`  
7. **Edges:** Invalid org; signup hidden if `allowSelfSignup` false; Forgot password is no-op; Super Admin link → `/super-admin`  
8. **Errors:** Snackbars on timeout/401  
9. **Auth:** Public  

**Suggested tests:** (1) Resolve valid/invalid org. (2) Login success/fail. (3) University signup requires semester. (4) Saved credentials autocomplete.

---

### 3.4 Student shell — `lib/screens/student_dashboard.dart`

**Tabs (sidebar):** Dashboard, New Report, My Reports, Collaboration, Templates, FYP tabs (Choose/My Supervisor, Milestones, Meeting Notes, Plagiarism, Status Tracker), Settings, Notifications  

| Behavior | Detail |
|----------|--------|
| FYP gating | Tabs 6–11 require `hasFypModule` |
| Polling | Documents every 10s |
| After supervisor chosen | Choose Supervisor tab redirects to My Supervisor |
| Index 4 | Removed — bounces to 0 |

**Suggested tests:** (1) Core-only hides FYP. (2) Supervisor accepted → tab 6→7. (3) Open collab project embeds detail. (4) Logout confirm clears session.

---

### 3.5 Document pipeline (student core)

#### New Report — `new_report_screen.dart`
- **Purpose:** Upload file / paste / Drive / QR / freeform → analyze  
- **Inputs:** Template (templated path), `.doc/.docx/.pdf/.txt`, title+content  
- **Outputs:** navigate `AnalyzeScreen`; may mark pending supervisor submit  
- **Suggested tests:** (1) File → Analyze. (2) Paste without title fails. (3) Freeform path. (4) Final submit surfaces `deadline_passed`.

#### Analyze — `analyze_screen.dart` (~large)
- **Purpose:** 9-tab analysis UI: structure, styles, headings, paragraphs, TOC/lists, content, tables, images/ethics, bullets; apply fixes; export  
- **Inputs:** `documentId`, `templateId`, `freeformAnalysis`  
- **Widgets used:** `DocumentPreviewPanel`, `ExportDialog`, `AnalyzeProgressPanel`, `ImageIssueCardEnhanced`, `ImageReplacementDialog`, `FreeformAnalyzeDialogs`, …  
- **Suggested tests:** (1) Load issues. (2) Apply heading fix updates UI. (3) Download DOCX. (4) Freeform accept/decline suggested fixes.

#### Upload / download related screens
| Screen | Path | Notes |
|--------|------|-------|
| `MultiUploadScreen` | `screens/multi_upload_screen.dart` | Local / Drive / Mobile / My Uploads |
| `MobileCompanionScreen` | `screens/mobile_companion_screen.dart` | Scan QR, camera, gallery |
| `MobileQrUploadScreen` | `screens/mobile_qr_upload_screen.dart` | States: validating/ready/uploading/success/error/expired |
| `MobileQrDownloadScreen` | `screens/mobile_qr_download_screen.dart` | Fetch by QR id |
| ` image_formatter_screen.dart` | **leading space in filename** | Image format results |
| `qr_upload_service.dart` | Generate upload QR (hardcoded LAN IP) |

**Suggested tests:** (1) Expired QR session. (2) Upload success updates desktop. (3) Deep link requires auth. (4) Export DOCX/PDF/TXT + QR.

---

### 3.6 Collaboration — `lib/screens/collaboration/`

| Screen / widget | Class | Purpose |
|-----------------|-------|---------|
| `project_dashboard_screen.dart` | `ProjectDashboardScreen` | Create/Join hub |
| `project_detail_screen.dart` | `ProjectDetailScreen` | Document / Members / History / Activity + WS |
| `section_editor_screen.dart` | `SectionEditorScreen` | Edit, commit, section images |
| `merge_conflict_screen.dart` | `MergeConflictScreen` | Resolve → complete |
| `project_download_screen.dart` | `ProjectDownloadScreen` | Download merged doc |
| `version_history_screen.dart` | `VersionHistoryScreen` | Rollback UI |
| Dialogs | Create / Join / Invite | Forms |
| `widgets/collaboration/project_card.dart` | Card | List item |

**Deps:** `CollaborationProvider`, `CollaborationSocket`  
**Suggested tests:** (1) Create with template. (2) Join invite code. (3) Save section → other client snackbar. (4) Resolve conflicts then download.

---

### 3.7 Student FYP screens — `lib/screens/student/` + meeting notes

| Screen | Purpose |
|--------|---------|
| `SupervisorSelectionScreen` | Request supervisor (Form validation) |
| `MySupervisorScreen` | Assignment status |
| `FypMilestonesScreen` | Milestone checklist |
| `PlagiarismReportScreen` | Group plagiarism |
| `StatusTrackerScreen` | Final submission stages; resubmit → New Report |
| `DocumentFeedbackScreen` | Supervisor comments |
| `StudentMeetingNotesScreen` | Read notes |
| Widgets | `DesktopSemesterDeadlineCard`, `MobileStatusSummaryCard`, `StudentNotificationsPage` |

**Suggested tests:** (1) Submit assignment request. (2) Pending hides Choose Supervisor. (3) Revision → resubmit flow. (4) Notifications mark-read.

---

### 3.8 Supervisor — `supervisor_dashboard.dart` + `supervisor/`

**Tabs:** Home, Assignment Requests, My Groups, Submissions, Plagiarism, Profile, More, Notifications (nested `Navigator` per tab)

| Screen | Interactions |
|--------|--------------|
| `SupervisorHomeScreen` | Stats → groups |
| `AssignmentRequestsScreen` | Accept / reject (+ reason) |
| `MyGroupsScreen` | List → detail; discard |
| `GroupDetailScreen` | Docs, milestones, notes, review |
| `DocumentReviewScreen` | Paragraph comments / resolve |
| `SubmissionReviewScreen` / `SubmissionDetailScreen` | Approve / revision / reject; download |
| `PlagiarismMonitorScreen` / Detail | Flag |
| `MeetingNotesScreen` | Add notes |
| `SupervisorNotificationsScreen` | Deep-link related screens |
| `SupervisorMoreScreen` | Mobile overflow |

**Suggested tests:** (1) Accept creates group. (2) Comment on paragraph. (3) Approve vs revision vs reject. (4) Flag plagiarism + download.

---

### 3.9 Admin — `admin_dashboard.dart` + admin screens

**Nav (FYP-gated \*):** Overview, Department Manager, Supervisors\*, Template Manager, Deadlines\*, Semester Deadlines\*, Users, Universities\*, Analytics, Verify Files, Settings

| Screen | CRUD / actions |
|--------|----------------|
| `AdminOverviewScreen` | Metrics |
| `DepartmentManagerScreen` | Dept CRUD |
| `SupervisorManagementScreen` / List | Create/toggle/delete; send credentials |
| `TemplateManagerScreen` / List | Templates; form via `template_form_widget` + `template_config/*` |
| `DeadlinesScreen` / `SemesterDeadlinesScreen` | Deadline CRUD |
| `AdminUsersScreen` / Universities / Analytics | Lists & charts |
| `AdminVerifyScreen` | Upload + template → Analyze |
| `AdminSettingsScreen` / `AdminReferenceSettingsScreen` | Org + frontmatter branding |

**Note:** `template_configuration_screen.dart` is largely commented-out legacy.

**Suggested tests:** (1) Create department. (2) Create supervisor. (3) Create template with required sections. (4) Verify file → Analyze. (5) Core-only hides FYP admin items.

---

### 3.10 Super Admin — `lib/screens/super_admin/super_admin_screen.dart`

- **Gate:** Master key unlock (`DevUserConfig.superAdminKey`)  
- **Nav:** Overview, Organizations, Admins, Billing, Activity, Settings  
- **Actions:** Create org (plan, modules, admin user), toggle/delete, reset API key  
- **Suggested tests:** (1) Wrong key fails. (2) Create university+fyp. (3) Starter/enterprise without FYP UI. (4) Toggle inactive.

---

### 3.11 Services (API clients) — `lib/services/`

| Service | Key coverage |
|---------|--------------|
| `AuthTokenStore` | Secure/prefs JWT |
| `LoginCredentialsStore` | Remembered emails/passwords |
| `AdminApiService` | Overview, depts, users, supervisors, templates, deadlines, analytics, settings, frontmatter |
| `SupervisorApiService` | Home, groups, accept/reject, review, submissions, plagiarism, notes, downloads |
| `StudentApiService` | Meeting notes, notifications, comments reply/resolve |
| `SuperAdminApiService` | Orgs CRUD, admins, stats, resolve org |
| `TemplateExtractApi` | Extract rules from uploaded doc |
| `ImageReplacementService` | Replace / remove / recheck |

**Error handling:** HTTP status → detail string / `Exception`; timeouts on auth.

---

### 3.12 Forms & validation inventory

| Form | Location | Rules |
|------|----------|-------|
| Org resolve | Login | Non-empty code |
| Login | Login | Email + password |
| Signup | Login | Name, email, password, department; semester if university FYP |
| Supervisor request | `SupervisorSelectionScreen` | FormState; supervisor ≠ co-supervisor |
| Create/Join project | Dialogs | Name+template / invite code |
| Invite member | Dialog | Email |
| Change password | Settings/profile | Current + new |
| Admin CRUD | Various | Required fields; confirm delete |
| Super Admin create org | SuperAdmin | Name, code, plan, modules, admin |
| Section save | SectionEditor | Content + commit message |
| Merge resolve | MergeConflict | Non-empty resolution |
| Meeting note | Supervisor | Date, topic, actions |

---

## 4. Database Models / Schemas

**Engine:** SQLite · `backend/database.py` · `check_same_thread=False`, timeout 30  
**Password:** SHA256 + fixed salt `formatify_salt_token_2026` (not per-user)

### 4.1 Core tables

| Table | Key fields | Constraints / relationships |
|-------|------------|-----------------------------|
| `universities` | id, name UNIQUE, country | ← users, templates |
| `users` | username, email, password_hash, role, university_id, department_id, current_semester, org_id | UNIQUE(email,org), UNIQUE(username,org) |
| `templates` | university_id, department_id, name, description, required_sections JSON, formatting_rules JSON, created_by, org_id | ← documents |
| `documents` | user_id, template_id, filename, file_path, status, detected/missing sections, group_id, frontmatter_*, signature_path, is_freeform, org_id | ← image_analysis, VC |
| `google_drive_tokens` | user_id PK, access/refresh, token_expiry | users |
| `file_sync_status` | document_id, user_id, source, sync_status, google_drive_id | |
| `image_analysis` | document_id, image_path, is_safe, confidence, analysis_result | |
| `departments` | name, code, min/max_members, max_groups_per_supervisor, org_id | |
| `supervisors` | name, email, department_id, max/current_groups, is_active, org_id | UNIQUE(email,org) |
| `deadlines` | title, description, due_date, department_id, applies_to_all, org_id | |
| `semester_deadlines` | semester (6/7), deadline_date, created_by, org_id | UNIQUE(semester,org) |
| `admin_settings` | key PK, value | org-prefixed keys `org:{id}:{key}` |
| `fyp_groups` | supervisor_id, title, project_title, status, progress, member_names, deadline, student_contact_email, department_id, plagiarism_*, cosupervisor_name, current_semester, org_id | |
| `assignment_requests` | supervisor_id, group_name, project_title, leader, members, department_id, status, rejection_reason, fyp_group_id, cosupervisor_name, org_id | |
| `notifications` | user_id, recipient_email, title, message, type, is_read, related_type/id | |
| `group_documents` | group_id, supervisor_id, title, filename, file_url, milestone, version, plagiarism_score, grammar_report_ref, status, source_document_id | |
| `group_replies` | group_id, supervisor_id, sender_name, message, is_read | |
| `group_milestones` | group_id, name, sort_order, is_completed | |
| `document_paragraphs` | document_id→group_documents, sort_order, text, block_type | |
| `document_comments` | paragraph_id, document_id, supervisor_id, comment_text, is_resolved, parent_comment_id | |
| `final_submissions` | group_id, supervisor_id, title, filename, status, analysis_report JSON, source_document_id, group_document_id, student_contact_email, decision_note | |
| `meeting_notes` | group_id, supervisor_id, meeting_date, topic, action_items | |
| `remarks` | group_id, document_id, verdict, remark_text, created_by | |
| `organizations` | name, code UNIQUE, type, api_key UNIQUE, plan, modules, documents_used/limit, is_active, primary_color, logo_url | |
| `organization_modules` | org_id, module_name, is_enabled | |

### 4.2 VC tables — `vc/database.py`

| Table | Purpose |
|-------|---------|
| `collaboration_projects` | name, template_id, invite_code, status, merged_*, base_document_*, shared_snapshot_path, org_id |
| `project_members` | project_id + user_id UNIQUE, role |
| `project_sections` | section_id, section_name, template_order, heading_level |
| `section_commits` | versioned content per section |
| `project_merges` | status, merged_file_path, analysis_report |
| `merge_conflicts` | conflict_type, details JSON, resolution |
| `section_images` | per-section image files |
| `project_member_documents` | maps project member → `documents.id` |

### 4.3 Pydantic API contracts — `models.py`

| Model | Role |
|-------|------|
| `ParagraphBlock`, `ImageBlock`, `DocumentModel` | Parser output |
| `Batch` | Batched pages for agents |
| `Issue` | Unified issue (function, type, severity, paragraph/image ids, suggestions, ethics/CLIP fields, heading provenance) |
| `Stats`, `DocumentInfo`, `AnalysisReport` | Analyze response |
| `UserSignupRequest`, `UserLoginRequest`, `ChangePasswordRequest` | Auth |
| `TemplateCreateRequest`, `TemplateUpdateRequest` | Template CRUD |
| `FrontmatterMember`, `DetectionResult`, `FrontmatterContext`, `FrontmatterGenerateRequest` | Frontmatter |

**Suggested DB tests:** (1) Unique email per org. (2) Same email two orgs. (3) FK delete behaviors. (4) semester_deadlines unique. (5) Seed data present after `init_db`.

---

## 5. Background Jobs / Scheduled Tasks

| Job | Mechanism | Notes |
|-----|-----------|-------|
| Vision model preload | `@app.on_event("startup")` → `asyncio.to_thread(preload_models)` | BLIP + CLIP |
| Analyze dispatch | `asyncio.gather` per batch agents ∥ corpus plagiarism | Failures → empty list (`return_exceptions=True`) |
| In-memory analyze jobs | `_jobs` dict | Lost on restart |
| VC merge complete | Awaits analysis runner | Async |
| OAuth sessions | In-memory `oauth_sessions` | Racey multi-worker |
| **Celery/RQ/cron** | **None** | No scheduled jobs found |

**CLI (manual):** `python -m plagiarism.ingest_corpus --rebuild-index`

**Suggested tests:** (1) Startup completes without vision crash (or soft-fails). (2) Job download fails after restart. (3) Agent exception does not abort whole analyze. (4) Corpus ingest rebuilds index.

---

## 6. Third-party Integrations

| Integration | Where | Purpose | Env / config |
|-------------|-------|---------|--------------|
| **Google Gemini** | `gemini_adapter.py` | Preferred LLM (`gemini-2.5-flash`) | `GEMINI_API_KEY` |
| **Anthropic Claude** | dispatcher agents, template extract | Fallback LLM; extract requires Anthropic | `ANTHROPIC_API_KEY`, `ANALYSIS_MODEL` |
| **Hugging Face local** | `functions/local_vision.py` | BLIP caption + CLIP relevance | `VISION_*` in `config.py` |
| **sentence-transformers + FAISS + datasketch** | `plagiarism/` | Local corpus plagiarism | `PLAGIARISM_*` |
| **Google Custom Search** | `plagiarism/web_verify.py` | Optional web plagiarism | `PLAGIARISM_ENABLE_WEB`, search keys |
| **Google Drive OAuth + API** | `google_drive_service.py` | Connect, list, import | `GOOGLE_CLIENT_*` / `GOOGLE_DRIVE_CLIENT_*` |
| **SMTP (Gmail)** | `admin_routes` credentials; `vc/invite_mail.py` | Emails | `SMTP_*` |
| **LibreOffice** | `reformatter.convert_docx_to_pdf` | PDF export | System install |
| **PyMuPDF / pdfplumber / pypdf** | `parser.py`, `pdf_io.py` | PDF parse | — |

**Suggested tests:** (1) Gemini-only env path. (2) Anthropic-only path. (3) No AI key → analyze 500. (4) SMTP missing → supervisor create still succeeds / soft-fail email. (5) Web plagiarism off by default.

---

## 7. Utility / Helper Functions

Skip pure boilerplate; focus on non-trivial logic.

### 7.1 Analysis pipeline

| Path | Functions / role |
|------|------------------|
| `parser.py` | `parse_file` / `parse_text` — DOCX/PDF/TXT → DocumentModel |
| `batcher.py` | `create_batches(doc, batch_size=4, overlap=1)` |
| `dispatcher.py` | `dispatch_all` / `dispatch_freeform` — parallel agents |
| `aggregator.py` | Dedup issues; list validation; Stats |
| `reformatter.py` | Apply styles/margins/numbering; PDF convert |
| `review_blocks.py` | Strip frontmatter from analysis scope |

### 7.2 Content / headings / lists / fields

| Path | Role |
|------|------|
| `content_fixer.py` | Text/heading/list fixes; demote; renumber; template reformat |
| `heading_analysis.py` | Rule/Claude heading match |
| `list_detection.py` | Detect parallel list groups for bullet conversion |
| `docx_fields.py` | TOC/LOT/LOF field insert; heading collect |
| `docx_styles.py` | Force heading styles |
| `issue_utils.py` | Normalize issues; build blocks; save images |
| `table_processor.py` | Detect/format/fill/normalize tables |
| `image_formatter.py` | Legacy AI image format |

### 7.3 Frontmatter stack

| Path | Role |
|------|------|
| `frontmatter_detector.py` | Hybrid cover/info detection |
| `frontmatter_generator.py` | Build cover/info DOCX from templates |
| `frontmatter_apply.py` | Merge pages into document |
| `frontmatter_data.py` | Assemble `FrontmatterContext` from group/admin settings |
| `functions/frontmatter_classify.py` | LLM assist |

### 7.4 Analysis agents — `functions/`

| Module | Entry | Behavior |
|--------|-------|----------|
| `grammar.py` | `check_grammar` | Local grammar suggestions (pyspellchecker + fine-tuned T5, `grammar_local.py`) |
| `formatting.py` | `check_formatting` | Template rules + sections |
| `formatting_freeform.py` | `check_formatting_freeform` | General style + `_suggested_fixes` |
| `para_relevance.py` | `check_para_relevance` | Relevance to heading |
| `plagiarism.py` | `check_plagiarism` | Optional LLM patterns (`PLAGIARISM_LLM_PATTERNS`) |
| `image_ethics.py` | `check_image_ethics`, `score_caption_ethics` | BLIP keyword ethics |
| `image_relevance.py` | `check_images_combined`, `recheck_image` | CLIP + context |
| `local_vision.py` | `preload_models`, caption/CLIP helpers | Offline torch |
| `heading_detect.py` | `detect_headings_with_claude` | LLM heading detect |

### 7.5 Formatting services — `services/`

| Service | Role |
|---------|------|
| `image_formatting_service` | Captions, numbering, refs, LOF pipeline |
| `image_caption_service` / `image_numbering_service` / `image_reference_validator` / `image_config` | Figure pieces |
| `table_formatting_service` | Captions, style, LOT |
| `table_caption_service` / `table_numbering_service` / `table_reference_validator` / `table_config` | Table pieces |
| `list_of_figures_service` / `list_of_tables_service` | Regenerate lists |
| `captioned_element_config` | Shared caption/numbering helpers |

### 7.6 Plagiarism — `plagiarism/`

| File | Role |
|------|------|
| `config.py` | Paths, thresholds, CSE keys |
| `corpus_index.py` | MinHash LSH + FAISS + embeddings |
| `local_check.py` | Jaccard + cosine |
| `web_verify.py` | Selective Google CSE |
| `detector.py` | `detect_plagiarism` / CLI |
| `pipeline.py` | `check_document_against_fyp_corpus` → Issue dicts |
| `text_extract.py` | DOCX/PDF/TXT extract |
| `ingest_corpus.py` | CLI ingest + rebuild |

### 7.7 Modules / middleware

| Path | Role |
|------|------|
| `modules/module_checker.py` | `has_module`, `require_module`, `require_fyp_from_request` |
| `modules/fyp_module.py` / `core_module.py` | Access helpers |
| `middleware/org_middleware.py` | Tenant resolve, inactive/limit gates, FYP path gates |

### 7.8 VC helpers

| Path | Role |
|------|------|
| `vc/service.py` | Project CRUD, commits, merge lifecycle |
| `vc/docx_import.py` | Template-aligned section split |
| `vc/conflicts.py` | Multi-author / duplicate / mismatch |
| `vc/merge.py` | Assemble merged DOCX; register document |
| `vc/reports_sync.py` | Sync analyzed DOCX to members’ Reports |
| `vc/utils.py` | Section slug, overlap ratio, content_matches_section |

**Suggested utility tests:** (1) Batcher page windows + overlap. (2) Aggregator dedup. (3) List detection safety skip. (4) Caption numbering sequential. (5) Plagiarism Jaccard above threshold. (6) TOC 422 without headings. (7) Org middleware FYP gate.

---

## 8. State Management

**Library:** Provider only (no Riverpod/Bloc/GetX)

### 8.1 Global providers (`main.dart` MultiProvider)

| Provider | File | Key state / actions |
|----------|------|---------------------|
| `AuthProvider` | `providers/auth_provider.dart` | login/signup/logout, OAuth/Drive connect, changePassword, role flags, session clear/restore |
| `DocumentProvider` | `providers/document_provider.dart` | fetch/upload file|text|freeform, Drive import, download/export, final submission, re-analyze, analysis cache, pending supervisor submit / resubmit |
| `TemplateProvider` | `providers/template_provider.dart` | Load/select/create templates |
| `UploadProvider` | `providers/upload_provider.dart` | Local + Drive upload/export, sync monitoring |
| `ImageFormatterProvider` | `providers/image_formatter_provider.dart` | Format images, download |
| `CollaborationProvider` | `providers/collaboration_provider.dart` | Projects, sections, merge, history, invites |
| `FypProvider` | `providers/fyp_provider.dart` | Supervisors, assignment, milestones, plagiarism, submissions, semester deadline |
| `ThemeProvider` | `theme/app_theme.dart` | Dark/light per user |

### 8.2 Local / helper (not always global)

| Provider / helper | Role |
|-------------------|------|
| `TableProvider` | Table detect/format (local to analyze) |
| `ImageEthicsProvider` | Image ethics/relevance checks |
| `CollaborationSocket` | WS `/api/vc/ws/projects/{id}` — ping/pong, section_updated |
| `QRService` | Generate download QR |

### 8.3 Persistence

| Store | What |
|-------|------|
| `AuthTokenStore` | JWT |
| `LoginCredentialsStore` | Remembered emails/passwords |
| SharedPreferences | Username/email/role; theme; `DevUserConfig` org |

**Suggested state tests:** (1) Login sets role + token. (2) Logout clears JWT and providers. (3) DocumentProvider caches analysis. (4) FypProvider sets `fypGroupId` on accepted status. (5) CollaborationSocket reconnect after drop. (6) Cold start clears session despite Remember me.

---

## 9. Analysis Pipeline Internals

```
Upload/Parse → DocumentModel
     → review_blocks (strip frontmatter)
     → batcher (4-page windows, overlap 1)
     → dispatcher (parallel):
         grammar | formatting|formatting_freeform | images_combined
         | para_relevance | optional LLM plagiarism
         ∥ corpus plagiarism pipeline
     → aggregator (dedup + list validation + Stats)
     → (template path) reformatter → working/output DOCX
     → AnalysisReport JSON to client
```

**Issue severity:** typically `major` | `minor`  
**Freeform differences:** no template formatting agent; no LLM plagiarism; suggested_fixes metadata; no silent reformat on analyze

**Suggested pipeline tests:** (1) DOCX with known grammar error → grammar issue. (2) Missing required section → formatting issue. (3) Duplicate issues collapsed. (4) Freeform vs template mutual exclusion. (5) Frontmatter text not scored as body.

---

## 10. Cross-cutting Auth & Multi-tenancy

### Org resolution order (`resolve_organization_from_request`)
1. JWT Bearer → org by `claims.org_id`
2. `X-Org-Code` / `org_code` query
3. Legacy `fmt_live_*` Bearer API key
4. Default org id=1

### Gates
| Gate | Result |
|------|--------|
| Inactive org | 403 |
| `documents_used >= documents_limit` | 403 |
| FYP path prefixes without `fyp` module | 403 (`/api/supervisor`, `/api/student`, admin supervisors/deadlines/semester-deadlines) |
| Cover/frontmatter-config | **Not** FYP-gated |

### Security notes for testers
- Many document APIs trust **`user_id` query** without binding to JWT subject.
- Password hashing uses a **fixed salt**.
- Google callback can create users into **org_id=1** when not linking.
- `_jobs` and `oauth_sessions` are process-local.
- Super-admin / JWT secrets have insecure defaults if env unset.
- Template extract and some admin endpoints have weak/optional role enforcement.

---

## 11. Priority Test Matrix

| Priority | Area | Scenarios |
|----------|------|-----------|
| P0 | Multi-tenant | Signup/login with org_code; same email different orgs; inactive 403; document limit 403 |
| P0 | Module gate | Org without `fyp` → student/supervisor APIs 403; frontmatter-config OK |
| P0 | Roles | Student blocked from freeform; admin CRUD; supervisor accept/reject |
| P0 | Document happy path | Template → upload → analyze → fix → export DOCX |
| P1 | Freeform | Admin upload → analyze-freeform → confirm fixes → download |
| P1 | FYP lifecycle | Request → accept → milestones → final submit → approve/revise; deadline block |
| P1 | Collaboration | Create/join → commit → WS → merge/conflict → download |
| P1 | Plagiarism | Corpus status; plagiarized text → monitor/flag |
| P2 | Google Drive | Authorize → import Doc as document |
| P2 | QR | Desktop QR upload/download same LAN; expired session |
| P2 | Super Admin | Unlock; create org; cannot delete org 1; wrong key |
| P2 | Tables/Images/TOC | Detect/format; replace image ethics; TOC 409/422 |
| P3 | Errors | Backend down timeouts; 403 deadline_passed; invalid invite; non-member WS 4003 |

---

## Appendix A — Existing automated tests (backend)

These already encode intended behavior — extend rather than contradict:

| File | Focus |
|------|-------|
| `test_freeform_student_403.py` | Student freeform blocked |
| `test_heading_and_list_detection.py` | Heading/list detection |
| `test_list_cleanup_safety.py` | Unsafe list skip |
| `test_document_lists.py` | TOC/LOT/LOF generation |
| `test_lof_lot_frontmatter.py` | Lists + frontmatter interaction |
| `test_blank_pages.py` | Blank page handling |
| `test_toc_pages_and_outline.py` | TOC pages/outline |
| `test_frontmatter_detector.py` | Cover/info detection |
| `test_table_format_config.py` / `test_table_formatting_pipeline.py` | Table rules/pipeline |
| `test_image_formatting_phase1.py` / `test_image_relevance_context.py` | Image pipeline |
| `test_gemini.py` | Gemini adapter |
| `plagiarism/test_detector.py` | Plagiarism detector |

---

## Appendix B — Repo layout map

```
formatify-new/
├── backend/                 # FastAPI API + analysis + FYP + VC
│   ├── main.py              # App + document/analyze routes
│   ├── admin_routes.py
│   ├── student_routes.py
│   ├── supervisor_routes.py
│   ├── super_admin_routes.py
│   ├── frontmatter_routes.py
│   ├── template_extract_routes.py
│   ├── database.py / models.py / config.py / auth_jwt.py
│   ├── middleware/org_middleware.py
│   ├── functions/           # AI/local analysis agents
│   ├── services/            # Image/table/Drive pipelines
│   ├── plagiarism/          # Corpus plagiarism
│   ├── vc/                  # Collaboration
│   └── modules/             # core/fyp gating
├── frontend/
│   └── lib/
│       ├── main.dart
│       ├── config/ / providers/ / services/ / models/
│       ├── screens/         # role shells + feature screens
│       └── widgets/         # shared UI + template_config
└── FUNCTIONAL_TEST_SUMMARY.md  # this file
```

---

*End of functional summary. Use section 11 for sprint prioritization; expand each feature’s “Suggested tests” into formal Given/When/Then cases as needed.*
