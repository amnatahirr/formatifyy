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
import numpy as np
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
    image = Image.open(io.BytesIO(data))
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        _bg = Image.new("RGBA", image.size, (255, 255, 255, 255))
        _bg.alpha_composite(image)
        image = _bg
    image = image.convert("RGB")
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

def _normalize_clip_features(feats) -> torch.Tensor:
    """
    Newer transformers may return BaseModelOutputWithPooling from
    get_image_features / get_text_features instead of a raw tensor.
    """
    if torch.is_tensor(feats):
        t = feats
    elif getattr(feats, "pooler_output", None) is not None:
        t = feats.pooler_output
    elif getattr(feats, "image_embeds", None) is not None:
        t = feats.image_embeds
    elif getattr(feats, "text_embeds", None) is not None:
        t = feats.text_embeds
    elif getattr(feats, "last_hidden_state", None) is not None:
        t = feats.last_hidden_state[:, 0, :]
    elif isinstance(feats, (tuple, list)) and feats:
        t = feats[0]
    else:
        raise TypeError(f"Unexpected CLIP feature type: {type(feats)!r}")

    if not torch.is_tensor(t):
        raise TypeError(f"CLIP features did not resolve to a tensor: {type(t)!r}")
    return t / t.norm(dim=-1, keepdim=True)


@torch.inference_mode()
def clip_image_embedding(image: Image.Image) -> torch.Tensor:
    processor, model = _load_clip()
    inputs = processor(images=image, return_tensors="pt").to(_device)
    feats = model.get_image_features(**inputs)
    return _normalize_clip_features(feats)


@torch.inference_mode()
def clip_text_embedding(text: str) -> torch.Tensor:
    processor, model = _load_clip()
    safe = (text or "")[:350].strip() or "empty"
    inputs = processor(text=[safe], return_tensors="pt", padding=True, truncation=True).to(_device)
    feats = model.get_text_features(**inputs)
    return _normalize_clip_features(feats)


def clip_cosine_similarity(image: Image.Image, text: str) -> float:
    """Cosine similarity clamped to [0, 1]."""
    img_emb = clip_image_embedding(image)
    txt_emb = clip_text_embedding(text)
    raw = float((img_emb @ txt_emb.T).squeeze().item())
    return float(max(0.0, min(1.0, raw)))


def clip_similarity_from_b64(b64: str, text: str) -> float:
    image = decode_base64_image(b64, for_inference=True)
    return clip_cosine_similarity(image, text)


@torch.inference_mode()
def clip_text_text_similarity(text_a: str, text_b: str) -> float:
    """Cosine similarity between two text strings via CLIP text encoder."""
    a = (text_a or "").strip()
    b = (text_b or "").strip()
    if not a or not b:
        return 0.0
    emb_a = clip_text_embedding(a)
    emb_b = clip_text_embedding(b)
    raw = float((emb_a @ emb_b.T).squeeze().item())
    return float(max(0.0, min(1.0, raw)))



# ── Diagram detection ─────────────────────────────────────────────────────────

_DIAGRAM_PROMPTS = [
    "a UML use case diagram with actors and ovals",
    "a UML class diagram",
    "a UML sequence diagram",
    "an entity relationship diagram",
    "a data flow diagram",
    "a flowchart with boxes and arrows",
    "a system architecture diagram",
    "a block diagram",
    "a software engineering diagram",
]
_PHOTO_PROMPTS = [
    "a photograph of a person",
    "a photograph of an animal",
    "a photograph of a landscape",
    "a photograph of a building",
    "a photograph of food",
    "a photograph of an object",
    "a cartoon or meme",
]
_DIAGRAM_CLIP_THRESHOLD = 0.60


def _flat_colour_stats(image: Image.Image) -> Tuple[float, float]:
    """(background_share, top10_share) on a coarse 16-level-per-channel palette."""
    small = image.convert("RGB").resize((256, 256), Image.Resampling.BOX)
    arr = np.asarray(small, dtype=np.uint8) >> 4
    keys = (
        (arr[..., 0].astype(np.int32) << 8)
        | (arr[..., 1].astype(np.int32) << 4)
        | arr[..., 2].astype(np.int32)
    )
    counts = np.sort(np.bincount(keys.ravel(), minlength=4096))[::-1]
    total = float(keys.size)
    return counts[0] / total, counts[:10].sum() / total


@torch.inference_mode()
def clip_diagram_probability(image: Image.Image) -> float:
    """CLIP zero-shot: probability mass on 'diagram' prompts vs 'photo' prompts."""
    processor, model = _load_clip()
    texts = _DIAGRAM_PROMPTS + _PHOTO_PROMPTS
    inputs = processor(
        text=texts, images=image, return_tensors="pt", padding=True, truncation=True
    ).to(_device)
    probs = model(**inputs).logits_per_image.softmax(dim=-1).squeeze(0)
    return float(probs[: len(_DIAGRAM_PROMPTS)].sum().item())


def is_diagram_like_from_b64(b64: str) -> bool:
    """
    Two-stage check:
      1) Flat-colour heuristic: one dominant background colour + very few
         other colours (works for white OR coloured/off-white backgrounds).
      2) CLIP zero-shot 'diagram vs photo' as fallback when (1) misses.
    """
    try:
        image = decode_base64_image(b64, for_inference=True)

        bg_share, top10 = _flat_colour_stats(image)
        if bg_share >= 0.45 and top10 >= 0.85:
            print(f"[local_vision] diagram check: flat colours "
                  f"(bg={bg_share:.2f}, top10={top10:.2f}) -> True")
            return True

        p_diagram = clip_diagram_probability(image)
        result = p_diagram >= _DIAGRAM_CLIP_THRESHOLD
        print(f"[local_vision] diagram check: bg={bg_share:.2f} top10={top10:.2f} "
              f"clip_diagram={p_diagram:.2f} -> {result}")
        return result
    except Exception as exc:
        print(f"[local_vision] diagram heuristic failed: {exc}")
        return False