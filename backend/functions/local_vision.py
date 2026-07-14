"""
Shared local vision utilities for Formatify image analysis.

Models (all open-source, runs fully offline after first download):
  - Salesforce/blip-image-captioning-base  → ethics captions
  - openai/clip-vit-base-patch32          → image–text similarity

Optimisations:
  - Images are downscaled before inference (max 384px)
  - Captions are cached per image fingerprint
  - Models load once (lazy or via preload_models at startup)
"""

from __future__ import annotations

import base64
import hashlib
import io
import threading
from typing import Tuple

import torch
from PIL import Image

# ── Device & lazy singleton state ─────────────────────────────────────────────

_device = "cuda" if torch.cuda.is_available() else "cpu"
_lock = threading.Lock()

_blip_processor = None
_blip_model = None
_clip_processor = None
_clip_model = None

# Caption cache: fingerprint → caption text
_caption_cache: dict[str, str] = {}
_caption_lock = threading.Lock()

# Max edge length for inference (CLIP/BLIP don't need multi-megapixel inputs)
MAX_INFERENCE_SIDE = 384


def get_device() -> str:
    return _device


def preload_models() -> None:
    """Load BLIP + CLIP at server startup so the first analysis isn't blocked."""
    print(f"[local_vision] Preloading models on {_device} …")
    _load_blip()
    _load_clip()
    print("[local_vision] All vision models ready.")


def _load_blip() -> Tuple[object, object]:
    global _blip_processor, _blip_model
    if _blip_model is not None:
        return _blip_processor, _blip_model
    with _lock:
        if _blip_model is not None:
            return _blip_processor, _blip_model
        from transformers import BlipForConditionalGeneration, BlipProcessor

        name = "Salesforce/blip-image-captioning-base"
        print(f"[local_vision] Loading BLIP ({name}) on {_device} …")
        _blip_processor = BlipProcessor.from_pretrained(name)
        _blip_model = BlipForConditionalGeneration.from_pretrained(name).to(_device)
        _blip_model.eval()
        print("[local_vision] BLIP ready.")
        return _blip_processor, _blip_model


def _load_clip() -> Tuple[object, object]:
    global _clip_processor, _clip_model
    if _clip_model is not None:
        return _clip_processor, _clip_model
    with _lock:
        if _clip_model is not None:
            return _clip_processor, _clip_model
        from transformers import CLIPModel, CLIPProcessor

        name = "openai/clip-vit-base-patch32"
        print(f"[local_vision] Loading CLIP ({name}) on {_device} …")
        _clip_processor = CLIPProcessor.from_pretrained(name)
        _clip_model = CLIPModel.from_pretrained(name).to(_device)
        _clip_model.eval()
        print("[local_vision] CLIP ready.")
        return _clip_processor, _clip_model


# ── Image helpers ─────────────────────────────────────────────────────────────

def resize_for_inference(image: Image.Image, max_side: int = MAX_INFERENCE_SIDE) -> Image.Image:
    """Downscale large images — keeps quality for BLIP/CLIP, cuts CPU time a lot."""
    w, h = image.size
    longest = max(w, h)
    if longest <= max_side:
        return image
    scale = max_side / float(longest)
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    return image.resize(new_size, Image.Resampling.BILINEAR)


def decode_base64_image(b64: str, for_inference: bool = True) -> Image.Image:
    """Decode a raw or data-URI base64 string into an RGB PIL image."""
    if not b64:
        raise ValueError("Empty base64 image data")
    raw = b64.split(",", 1)[-1] if b64.startswith("data:") else b64
    data = base64.b64decode(raw)
    image = Image.open(io.BytesIO(data)).convert("RGB")
    if for_inference:
        image = resize_for_inference(image)
    return image


def image_fingerprint(b64: str) -> str:
    """Stable short key for caption caching (avoids hashing multi-MB strings fully)."""
    raw = b64.split(",", 1)[-1] if b64.startswith("data:") else b64
    head = raw[:2048].encode("utf-8", errors="ignore")
    return hashlib.sha1(head + str(len(raw)).encode()).hexdigest()


def load_image(source: str, for_inference: bool = True) -> Image.Image:
    if not source:
        raise ValueError("Empty image source")
    if ("/" in source or "\\" in source) and len(source) < 512:
        image = Image.open(source).convert("RGB")
        return resize_for_inference(image) if for_inference else image
    try:
        return decode_base64_image(source, for_inference=for_inference)
    except Exception:
        image = Image.open(source).convert("RGB")
        return resize_for_inference(image) if for_inference else image


# ── BLIP captioning (cached) ──────────────────────────────────────────────────

@torch.inference_mode()
def generate_caption(image: Image.Image, max_new_tokens: int = 30) -> str:
    """Generate a natural-language caption with BLIP (local)."""
    processor, model = _load_blip()
    inputs = processor(images=image, return_tensors="pt").to(_device)
    out = model.generate(**inputs, max_new_tokens=max_new_tokens)
    return processor.decode(out[0], skip_special_tokens=True).strip()


def generate_caption_from_b64(b64: str, cache_key: str | None = None) -> str:
    """Caption with optional cache so ethics + relevance share one BLIP pass."""
    key = cache_key or image_fingerprint(b64)
    with _caption_lock:
        cached = _caption_cache.get(key)
    if cached is not None:
        return cached

    image = decode_base64_image(b64, for_inference=True)
    caption = generate_caption(image)
    with _caption_lock:
        _caption_cache[key] = caption
        # Bound memory for long-running servers
        if len(_caption_cache) > 256:
            # drop oldest half
            for old in list(_caption_cache.keys())[:128]:
                _caption_cache.pop(old, None)
    return caption


# ── CLIP embeddings & similarity ──────────────────────────────────────────────

@torch.inference_mode()
def clip_image_embedding(image: Image.Image) -> torch.Tensor:
    processor, model = _load_clip()
    inputs = processor(images=image, return_tensors="pt").to(_device)
    feats = model.get_image_features(**inputs)
    return feats / feats.norm(dim=-1, keepdim=True)


@torch.inference_mode()
def clip_text_embedding(text: str) -> torch.Tensor:
    processor, model = _load_clip()
    safe = (text or "")[:350].strip() or "empty"
    inputs = processor(text=[safe], return_tensors="pt", padding=True, truncation=True).to(_device)
    feats = model.get_text_features(**inputs)
    return feats / feats.norm(dim=-1, keepdim=True)


def clip_cosine_similarity(image: Image.Image, text: str) -> float:
    """Cosine similarity clamped to [0, 1]."""
    img_emb = clip_image_embedding(image)
    txt_emb = clip_text_embedding(text)
    raw = float((img_emb @ txt_emb.T).squeeze().item())
    return float(max(0.0, min(1.0, raw)))


def clip_similarity_from_b64(b64: str, text: str) -> float:
    image = decode_base64_image(b64, for_inference=True)
    return clip_cosine_similarity(image, text)
