"""
Central model configuration — change ANALYSIS_MODEL here for production.

Note: image_ethics + image_relevance run fully locally (BLIP + CLIP) and do
NOT use ANALYSIS_MODEL / any LLM vision API. VISION_* constants document the
Hugging Face checkpoints loaded by functions/local_vision.py.
"""

ANALYSIS_MODEL = "claude-haiku-4-5-20251001"

# Local open-source vision checkpoints (downloaded once, then offline)
VISION_CAPTION_MODEL = "Salesforce/blip-image-captioning-base"
VISION_CLIP_MODEL = "openai/clip-vit-base-patch32"
VISION_MODEL = VISION_CLIP_MODEL  # backward-compatible alias
