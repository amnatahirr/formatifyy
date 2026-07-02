# FORMATIFY — Project Context File
> Place this file in the ROOT of your repo. At the start of every Cursor session, 
> reference it with: `@FORMATIFY_CONTEXT.md` so Claude has full project context.

---

## What is FORMATIFY?
An AI-powered desktop application that automatically formats academic reports 
according to institution-specific templates. Students upload raw documents, 
select their university template, and FORMATIFY does all formatting automatically.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Desktop Frontend | Flutter |
| Mobile App | Flutter (companion app) |
| Backend | Python — FastAPI or Django |
| Database | PostgreSQL |
| NLP / Classification | Hugging Face Transformers + spaCy |
| Image Ethics Detection | CNN (ResNet/EfficientNet) + OpenAI CLIP |
| Voice Interface | OpenAI Whisper + NLP intent classifier |
| Document Parsing | python-docx, PyMuPDF |
| Export | python-docx (.docx), ReportLab/WeasyPrint (.pdf), LaTeX |

---

## Core Modules

### 1. File Parsing Module
- Accepts: Word (.docx), PDF, plain text
- Extracts: text blocks, images, tables
- Key file: `backend/services/document_block_extractor.py`
- Produces typed blocks: heading, paragraph, table, list_item, image

### 2. AI Content Classification Module ← CURRENT PRIORITY
- Classifies every document element using Transformers + spaCy
- Labels: `heading_h1`, `heading_h2`, `heading_h3`, `paragraph`, `table`, `figure`, `caption`, `reference`
- Key files: `backend/services/detector.py`, `backend/services/classifier.py`
- STATUS: Currently rule/regex-based — needs real Transformer integration

### 3. Formatting Engine
- Applies university template rules to every classified element
- Sets: fonts, margins, heading styles, spacing, table borders, caption formats, reference styles
- Key files: `backend/services/smart_formatter.py`, `backend/routers/format_document.py`
- STATUS: Built but NOT mounted in `backend/main.py` — needs wiring

### 4. AI Image Processing Module (Dual-stage)
- Stage 1 — Ethical Detection: CNN + CLIP checks if image is appropriate/relevant for academic use
- Stage 2 — Intelligent Formatting: auto-corrects image size, position, caption, figure numbering
- Key file: `backend/services/image_relevance.py`

### 5. Voice-to-Command Interface
- Student speaks a command → Whisper transcribes → NLP classifies intent → formatting action executes
- Example commands: "make this a Heading 2", "insert table of contents"

### 6. Version Control & Collaboration Module
- Multiple students upload/edit/merge sections in one shared document
- Complete revision history + one-click rollback

### 7. Mobile Companion App
- QR code pairing with desktop session
- Upload documents/images from phone camera or gallery
- Download final formatted report to phone

### 8. Admin Panel
- Universities upload and manage custom formatting templates
- Templates stored in DB as `templates.formatting_rules`

### 9. Multi-format Export
- Word (.docx), PDF, LaTeX — zero formatting loss
- Key files: `backend/routers/export.py`, `backend/services/docx_generator.py`

---

## Current Pipeline Flow (Target)
```
User uploads Word/PDF
        ↓
File Parsing Module (document_block_extractor.py)
        ↓
AI Content Classification (Transformers + spaCy)
  → labels: heading_h1/h2/h3, paragraph, table, figure, caption, reference
        ↓
Formatting Engine (smart_formatter.py)
  → applies university template rules to each element
        ↓
Export as formatted .docx / PDF / LaTeX
        ↓
User downloads formatted document
```

---

## Known Issues & Status (from last codebase scan)

### ❌ Critical Bugs to Fix
1. `backend/routers/format_document.py` — NOT mounted in `backend/main.py` (new pipeline inactive)
2. `backend/routers/uploads.py` — SQL alias bug: `ORDER BY d.created_at` without alias
3. `backend/routers/qr.py` — Malformed double-protocol URL construction
4. Formatting paths — `eval(...)` used instead of safe `json.loads()`
5. `frontend/lib/main.dart` — Route `/new-report` not registered
6. `backend/auth_utils.py` — Hardcoded JWT secret (security issue)
7. `frontend/lib/screens/multi_upload_screen.dart` — Tab count/content mismatch

### ⚠️ Partially Done
- New smart formatting pipeline exists (`format_document.py`, `detector.py`, `classifier.py`, `smart_formatter.py`) but NOT wired
- AI classification is rule/regex-based — Transformers/spaCy not yet driving main element classification
- `figure`, `caption`, `reference` are not first-class block types yet
- Frontend still uses legacy endpoints (`documents/analyze`, `export/document`)
- Admin area mostly static/stubbed

### ✅ Already Working
- Auth system (JWT + Google/GitHub OAuth)
- Document upload, save, list, analyze, export (legacy path)
- Template configuration (admin screens + DB)
- Image formatter flow
- Table processing
- Student flow: login → upload → analyze → export

---

## Development Priority Order

### Phase 1 — Fix & Wire (Do First)
1. Mount `format_document.py` router in `backend/main.py`
2. Fix SQL alias bug in `uploads.py`
3. Fix QR double-protocol URL bug in `qr.py`
4. Replace `eval()` with `json.loads()` in formatting paths
5. Register `/new-report` route in `frontend/lib/main.dart`
6. Fix JWT secret — move to environment variable

### Phase 2 — Consolidate Pipeline
1. Make `format_document.py` the primary backend path
2. Add `figure`, `caption`, `reference` as first-class block types in extractor
3. Wire frontend to use new endpoints instead of legacy ones
4. Link figure blocks to captions with metadata (`figure_id`, `caption_for`)

### Phase 3 — Real AI Classification
1. Replace `detector.py` + `classifier.py` with Hugging Face Transformer classifier
2. Add spaCy for citation patterns, sentence boundaries, caption detection
3. Add confidence scores + fallback to heuristics
4. Preload model at app startup (like ContentChecker)

### Phase 4 — Polish & Export
1. Map all new labels to template style keys
2. Ensure exporter handles figure/caption/reference natively
3. Test round-trip fidelity for images/tables/captions
4. Full export to .docx, PDF, LaTeX with zero formatting loss

---

## API Contract (Target — Single Canonical Flow)
```
POST /api/upload          → upload raw document
POST /api/classify        → classify + style all elements  
POST /api/format          → apply template rules
GET  /api/export/docx     → download formatted .docx
GET  /api/export/pdf      → download formatted .pdf
GET  /api/export/latex    → download formatted .tex
```

---

## Key Decisions & Constraints
- English-language documents only (current version)
- All AI processing runs on desktop — mobile app is upload/download only
- No Turnitin integration (API licensing cost)
- No cloud deployment or LMS integration in current scope
- Flutter desktop app is cross-platform
- PostgreSQL for all data storage
- JWT authentication for all protected endpoints

---


```