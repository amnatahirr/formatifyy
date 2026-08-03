"""
Central model configuration — change ANALYSIS_MODEL here for production.

Note: image_ethics + image_relevance run fully locally (BLIP + CLIP) and do
NOT use ANALYSIS_MODEL / any LLM vision API. VISION_* constants document the
Hugging Face checkpoints loaded by functions/local_vision.py.
"""

import os
from dotenv import load_dotenv

load_dotenv()

ANALYSIS_MODEL = "claude-haiku-4-5-20251001"

# Local open-source vision checkpoints (downloaded once, then offline)
VISION_CAPTION_MODEL = "Salesforce/blip-image-captioning-base"
VISION_CLIP_MODEL = "openai/clip-vit-base-patch32"
VISION_MODEL = VISION_CLIP_MODEL  # backward-compatible alias


class Settings:
    """Runtime settings used by Google Drive / OAuth integrations."""

    API_URL: str = os.getenv("API_URL", "http://localhost:8000")
    UPLOAD_FOLDER: str = os.getenv("UPLOAD_FOLDER", "uploads")

    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_DRIVE_CLIENT_ID: str = os.getenv(
        "GOOGLE_DRIVE_CLIENT_ID",
        os.getenv("GOOGLE_CLIENT_ID", ""),
    )
    GOOGLE_DRIVE_CLIENT_SECRET: str = os.getenv(
        "GOOGLE_DRIVE_CLIENT_SECRET",
        os.getenv("GOOGLE_CLIENT_SECRET", ""),
    )


settings = Settings()
os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
