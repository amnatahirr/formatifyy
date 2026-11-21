"""Trained ethics head (CLIP embedding -> safe / sexual / weapons_violence).
v3 = v2 + medical hard negatives (brain/ml/train_ethics_v3.py)."""
import os
import threading

import joblib
import torch

from functions.local_vision import _load_clip, _device, decode_base64_image

_HEAD_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "ml_weights", "ethics_head_v3.joblib",
)
_head = None
_lock = threading.Lock()


def _get_head():
    global _head
    if _head is None:
        with _lock:
            if _head is None:
                _head = joblib.load(_HEAD_PATH)
    return _head


@torch.inference_mode()
def clip_embedding_512(image):
    """Same embedding recipe as training: projected, 512-d, L2-normalised."""
    processor, model = _load_clip()
    inputs = processor(images=image, return_tensors="pt").to(_device)
    out = model.get_image_features(**inputs)
    if not torch.is_tensor(out):
        out = out.pooler_output
    if out.shape[-1] != 512:
        out = model.visual_projection(out)
    out = out / out.norm(dim=-1, keepdim=True)
    return out.cpu().numpy()


def predict_unsafe(b64: str) -> dict:
    head = _get_head()
    emb = clip_embedding_512(decode_base64_image(b64, for_inference=True))
    probs = dict(zip([str(c) for c in head.classes_], head.predict_proba(emb)[0]))
    unsafe = {k: float(v) for k, v in probs.items() if k != "safe"}
    return {
        "p_unsafe": float(1.0 - probs["safe"]),
        "top_class": max(unsafe, key=unsafe.get),
        "probs": {k: float(v) for k, v in probs.items()},
    }