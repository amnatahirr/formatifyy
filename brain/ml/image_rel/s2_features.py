"""STAGE 2: turn each (image, caption, heading, section) pair into numeric features.
Image embeddings are cached on disk (by file md5), so re-runs are fast.
Run:  python brain/ml/image_rel/s2_features.py --backend real [--ocr] [--blip] [--clip-model google/siglip-base-patch16-224]
Smoke test without model downloads:  --backend fake"""
import argparse, json, re
import numpy as np, pandas as pd
import config
from data_access import tokens
from backends import get_backend, ImageEmbCache, JsonCache

TYPE_PROMPTS = ["a UML or flow diagram", "a screenshot of a software application", "a chart or graph",
                "a photograph", "a table of data"]
CAP_FEATS = ["clip_img_cap", "mini_cap_head", "mini_cap_sec", "has_caption", "cap_len"]
FEATS = ["clip_img_head", "clip_img_cap", "mini_cap_head", "mini_cap_sec", "has_caption", "cap_len",
         "head_len", "has_sec", "t_diagram", "t_screen", "t_chart", "t_photo", "t_table", "aspect",
         "ocr_overlap", "has_ocr", "blip_head_sim", "has_blip"]


def rowdot(a, b):
    return np.einsum("ij,ij->i", a, b)


def embed_unique(fn, series):
    uniq = list(dict.fromkeys(series.tolist()))
    E = fn(uniq) if uniq else np.zeros((0, 1))
    idx = {s: i for i, s in enumerate(uniq)}
    return E[[idx[s] for s in series]]


def ocr_text(path):
    try:
        import pytesseract
        from PIL import Image
        return pytesseract.image_to_string(Image.open(path).convert("L"))
    except Exception:
        return ""


def build(df, be, use_ocr, use_blip):
    cache = ImageEmbCache(be)
    uniq = df.drop_duplicates("img_hash")
    img_map = dict(zip(uniq.img_hash, cache.get(uniq.img_hash.tolist(), uniq.image_path.tolist())))
    E_img = np.stack([img_map[h] for h in df.img_hash])
    head = df.heading.fillna("")
    cap = df.caption.fillna("")
    sec = df.section_text.fillna("")
    mhead = np.where((df.chapter.fillna("") != "") & (df.chapter != df.heading), df.chapter + ": " + df.heading, df.heading)
    mhead = pd.Series(mhead, index=df.index)
    f = pd.DataFrame(index=df.index)
    f["clip_img_head"] = rowdot(E_img, embed_unique(be.clip_text, head))
    hc = df.has_caption.values.astype(bool)
    f["clip_img_cap"] = np.where(hc, rowdot(E_img, embed_unique(be.clip_text, cap)), 0.0)
    f["mini_cap_head"] = np.where(hc, rowdot(embed_unique(be.mini_text, cap), embed_unique(be.mini_text, mhead)), 0.0)
    hs = (sec.str.len() > 0).values
    f["mini_cap_sec"] = np.where(hc & hs, rowdot(embed_unique(be.mini_text, cap), embed_unique(be.mini_text, sec)), 0.0)
    f["has_caption"] = df.has_caption.values
    f["cap_len"] = cap.str.split().str.len().fillna(0).values
    f["head_len"] = head.str.split().str.len().values
    f["has_sec"] = hs.astype(int)
    T = be.clip_text(TYPE_PROMPTS)
    z = 100.0 * (E_img @ T.T)
    z = np.exp(z - z.max(1, keepdims=True))
    z /= z.sum(1, keepdims=True)
    for i, k in enumerate(["t_diagram", "t_screen", "t_chart", "t_photo", "t_table"]):
        f[k] = z[:, i]
    f["aspect"] = (df.w / df.h).values
    f["ocr_overlap"], f["has_ocr"], f["blip_head_sim"], f["has_blip"] = 0.0, 0, 0.0, 0
    if use_ocr:
        oc = JsonCache("ocr.json")
        for h, p in zip(uniq.img_hash, uniq.image_path):
            if h not in oc.d:
                oc.d[h] = ocr_text(p)
        oc.save()
        ot = df.img_hash.map(oc.d).fillna("")
        otok = ot.map(lambda s: {t for t in tokens(s) if t.isalpha()})
        ctx = (head + " " + sec).map(tokens)
        f["has_ocr"] = (otok.map(len) >= 3).astype(int).values
        f["ocr_overlap"] = [len(a & b) / len(a) if len(a) >= 3 else 0.0 for a, b in zip(otok, ctx)]
    if use_blip:
        bc = JsonCache("blip.json")
        miss = [(h, p) for h, p in zip(uniq.img_hash, uniq.image_path) if h not in bc.d]
        if miss:
            for (h, _), c in zip(miss, be.blip_caption([p for _, p in miss])):
                bc.d[h] = c
            bc.save()
        bl = df.img_hash.map(bc.d).fillna("")
        f["has_blip"] = (bl.str.len() > 0).astype(int).values
        f["blip_head_sim"] = np.where(f["has_blip"] == 1, rowdot(embed_unique(be.mini_text, bl), embed_unique(be.mini_text, mhead)), 0.0)
    meta = df[["pair_id", "split", "report", "img_uid", "img_hash", "label", "neg_type", "sec_id"]]
    return pd.concat([meta, f[FEATS]], axis=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["real", "fake"], default="real")
    ap.add_argument("--clip-model", default=None)
    ap.add_argument("--ocr", action="store_true")
    ap.add_argument("--blip", action="store_true")
    a = ap.parse_args()
    be = get_backend(a.backend, a.clip_model)
    for stem in ["pairs_train", "pairs_val", "pairs_test", "rank_val", "rank_test"]:
        p = config.WORK_DIR / f"{stem}.jsonl"
        if not p.exists():
            continue
        df = pd.read_json(p, lines=True, dtype={"caption": str, "heading": str, "chapter": str, "section_text": str})
        if df.empty:
            continue
        out = build(df, be, a.ocr, a.blip)
        out.to_csv(config.WORK_DIR / f"features_{stem.split('_',1)[1] if stem.startswith('pairs') else stem}.csv", index=False)
        print(f"[OK] {stem}: {len(out)} rows, NaN cells: {int(out[FEATS].isna().sum().sum())}")
    (config.WORK_DIR / "feature_meta.json").write_text(json.dumps(
        {"backend": a.backend, "clip": be.clip_name, "ocr": a.ocr, "blip": a.blip}))


if __name__ == "__main__":
    main()
