"""Inference API used later by engine.py / the app.
    from image_relevance_local import LocalImageRelevance
    r = LocalImageRelevance()                       # loads trained bundle once
    r.score(image_path, heading, caption="", chapter="", section_text="")
    -> {"score":0..1, "relevant":bool, "confidence":0.5..1, "needs_claude":bool}
needs_claude is True when the score lies inside the uncertainty band chosen on validation data."""
import pandas as pd, joblib, hashlib
from . import config
from .backends import get_backend, ImageEmbCache, md5_file
from .s2_features import build, FEATS


class LocalImageRelevance:
    def __init__(self, model_path=None, backend=None, use_ocr=None, use_blip=None):
        self.b = joblib.load(model_path or config.MODEL_PATH)
        fm = self.b["feature_meta"]
        kind = backend or fm.get("backend", "real")
        self.be = get_backend(kind, fm.get("clip") if kind == "real" else None)
        self.ocr = fm.get("ocr", False) if use_ocr is None else use_ocr
        self.blip = fm.get("blip", False) if use_blip is None else use_blip
        assert self.b["features"] == FEATS, "feature list changed since training: retrain"

    def score_many(self, items):
        """items: list of dicts(image_path, heading, caption, chapter, section_text)."""
        from PIL import Image
        rows = []
        for i, it in enumerate(items):
            with Image.open(it["image_path"]) as im:
                w, h = im.size
            rows.append({"pair_id": f"q{i}", "split": "q", "report": "", "img_uid": f"q{i}", "image_path": str(it["image_path"]),
                         "img_hash": md5_file(it["image_path"]), "w": w, "h": h, "caption": it.get("caption") or "",
                         "has_caption": int(bool(it.get("caption"))), "heading": it["heading"], "chapter": it.get("chapter") or "",
                         "section_text": it.get("section_text") or "", "sec_id": 0, "label": 0, "neg_type": "q"})
        X = build(pd.DataFrame(rows), self.be, self.ocr, self.blip)[FEATS]
        p = self.b["model"].predict_proba(X)[:, 1]
        t, w = self.b["t_dec"], self.b["band_half_width"]
        out = []
        for s in p:
            review = bool(t - w <= s <= t + w)
            # needs_review: uncertain, ask the student to check (no API needed).
            # needs_claude is kept as an alias so older code still works.
            out.append({"score": float(s), "relevant": bool(s >= t), "confidence": float(max(s, 1 - s)),
                        "needs_review": review, "needs_claude": review})
        return out

    def score(self, image_path, heading, caption="", chapter="", section_text=""):
        return self.score_many([{"image_path": image_path, "heading": heading, "caption": caption,
                                 "chapter": chapter, "section_text": section_text}])[0]
