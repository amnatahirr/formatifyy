from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from routers import documents, templates, admin, formatting, export, auth, paragraph_formatting, uploads
from database import init_db
from config import settings
from fastapi.staticfiles import StaticFiles
from routers import qr
from routers import heading_validation_router
from routers import structure_check_router
from routers import qr_upload
from routers.image_router import router as image_router
from routers import block_extraction_router
from routers import image_replacement_router
from routers.fyp_image_formatter_router import router as formatter_router
from routers.table_router import router as table_router
from routers import references 
from routers.structure_style_toc_router import router as sst_router
from routers.content_check_router import router as content_check_router
from routers.format_document import router as format_document_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan — pre-loads ML models on startup so first request isn't slow
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ───────────────────────────────────────────────────────────────
    logger.info("=" * 55)
    logger.info("FORMATIFY API starting up...")
    logger.info("=" * 55)

    # Pre-load ContentChecker (sentence-transformer + classifier)
    try:
        from checker.content_checker import ContentChecker
        app.state.content_checker = ContentChecker()
        if app.state.content_checker._model_available:
            logger.info("✓  ContentChecker : model ready (content_classifier.pkl)")
        else:
            logger.info("⚠  ContentChecker : model NOT trained yet")
            logger.info("   To train it run:")
            logger.info("     python checker/extract_training_data.py --folder my_sample_docs/")
            logger.info("     python checker/train_content_model.py")
    except Exception as e:
        logger.warning("ContentChecker failed to load (non-fatal): %s", e)
        app.state.content_checker = None

    # Pre-load StyleChecker (lightweight, no ML)
    try:
        from checker.style_checker import StyleChecker
        app.state.style_checker = StyleChecker()
        logger.info("✓  StyleChecker   : ready")
    except Exception as e:
        logger.warning("StyleChecker failed to load (non-fatal): %s", e)
        app.state.style_checker = None

    # Pre-load Transformer element classifier (with spaCy cue engine)
    try:
        from services.ai_element_classifier import ai_element_classifier
        ai_element_classifier.preload()
        app.state.ai_element_classifier = ai_element_classifier
        if ai_element_classifier._model_available:
            logger.info("✓  ElementClassifier : Hugging Face model ready")
        else:
            logger.info("⚠  ElementClassifier : model unavailable, heuristic fallback active")
    except Exception as e:
        logger.warning("ElementClassifier failed to load (non-fatal): %s", e)
        app.state.ai_element_classifier = None

    # Initialize database (was previously called at module level)
    init_db()
    logger.info("✓  Database       : initialized")
    logger.info("✓  Server ready")
    logger.info("=" * 55)

    yield  # ← server runs here

    # ── SHUTDOWN ──────────────────────────────────────────────────────────────
    logger.info("FORMATIFY API shutting down...")


# ─────────────────────────────────────────────────────────────────────────────
# Ensure required directories exist before mounting static files
for d in ["uploads", "uploads/working", "extracted_images", "checker", "outputs", "formatted"]:
    os.makedirs(d, exist_ok=True)

app = FastAPI(
    title="FORMATIFY API",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(qr.router)
app.include_router(structure_check_router.router)
app.include_router(heading_validation_router.router)
app.include_router(block_extraction_router.router)
app.include_router(references.router) 
# ── Static mounts ─────────────────────────────────────────────────────────────
app.mount("/extracted_images", StaticFiles(directory="extracted_images"), name="extracted_images")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(formatter_router, prefix="/api")
app.include_router(image_router)
app.include_router(qr_upload.router)
app.include_router(table_router)
app.include_router(content_check_router, prefix="/api")   # ← FIXED: added prefix="/api"
app.include_router(format_document_router)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Remaining routers ─────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(image_replacement_router.router, prefix="/api")
app.include_router(templates.router)
app.include_router(admin.router)
app.include_router(formatting.router)
app.include_router(paragraph_formatting.router)
app.include_router(export.router)
app.include_router(uploads.router)
app.include_router(sst_router)

# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"message": "FORMATIFY API is running", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    cc = getattr(app.state, "content_checker", None)
    sc = getattr(app.state, "style_checker", None)
    ec = getattr(app.state, "ai_element_classifier", None)
    return {
        "status":        "healthy",
        "content_model": "ready" if (cc and cc._model_available) else "not_trained",
        "style_checker": "ready" if sc else "unavailable",
        "element_classifier": "ready" if (ec and ec._model_available) else "fallback_only",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)