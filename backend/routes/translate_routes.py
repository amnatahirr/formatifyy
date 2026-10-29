import json
import os
import threading
from fastapi import APIRouter
from pydantic import BaseModel
from deep_translator import GoogleTranslator
import subprocess
import sys

router = APIRouter()
WORKER = os.path.join(os.path.dirname(__file__), "translate_worker.py")

CACHE_FILE = os.path.join(os.path.dirname(__file__), "translations_cache.json")
_lock = threading.Lock()
_cache = {}  # "lang|text" -> translation

if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            _cache = json.load(f)
    except Exception:
        _cache = {}


def _save_cache():
    with _lock:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False)


def _translate_many(texts, target):
    # pehle Argos, alag process mein (OpenMP conflict se bachne ke liye)
    try:
        r = subprocess.run(
            [sys.executable, WORKER],
            input=json.dumps({"texts": texts, "target": target}),
            capture_output=True,
            text=True,
            timeout=180,
        )
        if r.returncode == 0:
            out = json.loads(r.stdout)
            if any(o != t for o, t in zip(out, texts)):
                return out
        else:
            print(f"[argos] worker failed: {r.stderr[-300:]}")
    except Exception as e:
        print(f"[argos] failed: {e}")
    # fallback: Google
    return GoogleTranslator(source="en", target=target).translate_batch(texts)


class TranslateReq(BaseModel):
    texts: list[str]
    target: str


@router.post("/translate")
def translate(req: TranslateReq):
    if req.target == "en":
        return {"translated": req.texts}

    missing = []
    for t in req.texts:
        if t.strip() and f"{req.target}|{t}" not in _cache and t not in missing:
            missing.append(t)

    if missing:
        try:
            results = _translate_many(missing, req.target)
            for src, dst in zip(missing, results):
                if dst:
                    _cache[f"{req.target}|{src}"] = dst
            _save_cache()
        except Exception as e:
            print(f"[translate] failed: {e}")

    out = [_cache.get(f"{req.target}|{t}", t) for t in req.texts]
    return {"translated": out}