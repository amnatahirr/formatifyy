"""STAGE 1: build (image, caption, heading) training pairs from parsed reports.
Positive = image + the section it really sits under. Negatives = same image + another section
(hard: same report; easy: other report, same split). Project-level split from splits.csv.
Also: size filter, near-duplicate removal across splits (perceptual hash), ranking candidates.
Run:  python brain/ml/image_rel/s1_build_pairs.py"""
import json, random, collections
import numpy as np, pandas as pd
from PIL import Image
import config
from data_access import *
from backends import md5_file

PRIORITY = {"test": 0, "val": 1, "train": 2}  # duplicates are kept in the strictest split


def dhash(im):
    g = np.asarray(im.convert("L").resize((9, 8), Image.LANCZOS), dtype=np.int16)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def popcount(x):
    return np.unpackbits(x.view(np.uint8).reshape(len(x), 8), axis=1).sum(1)


def cluster(hashes, thr):
    n = len(hashes)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    h = np.array(hashes, dtype=np.uint64)
    for i in range(n - 1):
        d = popcount(h[i] ^ h[i + 1:])
        for j in (np.nonzero(d <= thr)[0] + i + 1):
            parent[find(int(j))] = find(i)
    return [find(i) for i in range(n)]


def has_alpha(s):
    return sum(c.isalpha() for c in s) >= 3


def main():
    rng = random.Random(config.SEED)
    sp = pd.read_csv(config.SPLITS_CSV)
    split_of = dict(zip(sp["report"], sp["split"]))
    S = collections.Counter()
    reports, items = {}, []
    for f in sorted(config.PARSED_DIR.glob("*.jsonl")):
        blocks = read_jsonl(f)
        if not blocks:
            continue
        rep = blocks[0].get("report", f.stem)
        split = split_of.get(rep) or split_of.get(f.stem)
        if split is None:
            S["reports_not_in_splits"] += 1
            continue
        secs, imgs, nopath = parse_report(blocks, rep)
        reports[rep] = {"split": split, "secs": [s for s in secs if not s["skip"] and has_alpha(s["heading"])]}
        S["reports_used"] += 1
        S["img_block_without_path"] += nopath
        for im in imgs:
            S["images_found"] += 1
            if im["path"] is None:
                S["drop_file_missing"] += 1
            elif im["sec_id"] is None:
                S["drop_before_first_heading"] += 1
            elif secs[im["sec_id"]]["skip"] or not has_alpha(secs[im["sec_id"]]["heading"]):
                S["drop_front_or_back_matter"] += 1
            else:
                items.append({"report": rep, "split": split, **im})
    # size / aspect filter + hashes
    kept = []
    for it in items:
        try:
            with Image.open(it["path"]) as im:
                w, h = im.size
                if min(w, h) < config.MIN_SIDE or max(w, h) / max(1, min(w, h)) > config.MAX_ASPECT:
                    S["drop_too_small_or_banner"] += 1
                    continue
                it.update(w=w, h=h, dh=dhash(im), md5=md5_file(it["path"]))
                kept.append(it)
        except Exception:
            S["drop_unreadable"] += 1
    # near-duplicate removal (strictest split wins; one copy per split)
    cl = cluster([k["dh"] for k in kept], config.DHASH_MAX_HAMMING) if kept else []
    best = {}
    for k, c in zip(kept, cl):
        best[c] = min(best.get(c, 9), PRIORITY[k["split"]])
    seen, final = set(), []
    for k, c in sorted(zip(kept, cl), key=lambda x: (x[0]["report"], x[0]["ref"])):
        if PRIORITY[k["split"]] != best[c]:
            S["drop_dup_other_split"] += 1
        elif (c, k["split"]) in seen:
            S["drop_dup_same_split"] += 1
        else:
            seen.add((c, k["split"]))
            final.append(k)
    # pairs
    pool = {s: [(r, t) for r, v in reports.items() if v["split"] == s for t in v["secs"]] for s in PRIORITY}
    pairs = {s: [] for s in PRIORITY}
    rank = {s: [] for s in ("val", "test")}
    for n, im in enumerate(final):
        rep, split = im["report"], im["split"]
        secs = reports[rep]["secs"]
        true = next((t for t in secs if t["sec_id"] == im["sec_id"]), None)
        if true is None:
            continue
        uid = f"{split}-img{n:05d}"

        def row(sec, label, neg_type, kind="pair"):
            return {"pair_id": "", "split": split, "report": rep, "img_uid": uid, "image_path": str(im["path"]),
                    "img_hash": im["md5"], "w": im["w"], "h": im["h"], "caption": im["caption"],
                    "has_caption": int(bool(im["caption"])), "heading": sec["heading"], "chapter": sec["chapter"],
                    "section_text": sec["text"], "sec_id": sec["sec_id"], "label": label, "neg_type": neg_type}

        pairs[split].append(row(true, 1, "pos"))
        hard = [t for t in secs if t["sec_id"] != true["sec_id"] and norm(t["heading"]) != norm(true["heading"])
                and jaccard(t["heading"], true["heading"]) < 0.5]
        strict = [t for t in hard if not true["chapter"] or t["chapter"] != true["chapter"]]
        for t in rng.sample(strict or hard, min(config.N_HARD_NEG, len(strict or hard))):
            pairs[split].append(row(t, 0, "hard"))
        others = [t for r, t in pool[split] if r != rep and jaccard(t["heading"], true["heading"]) < 0.5]
        for t in rng.sample(others, min(config.N_EASY_NEG, len(others))):
            pairs[split].append(row(t, 0, "easy"))
        if split in rank:
            for t in secs:
                if t["sec_id"] != true["sec_id"] and norm(t["heading"]) == norm(true["heading"]):
                    continue  # same-named section is not a fair negative
                rank[split].append(row(t, int(t["sec_id"] == true["sec_id"]), "rank"))
    out = config.WORK_DIR
    summary = {"drops_and_counts": dict(S), "final_images": len(final), "per_split": {}}
    for s, rows in pairs.items():
        for i, r in enumerate(rows):
            r["pair_id"] = f"{s}-{i:06d}"
        with open(out / f"pairs_{s}.jsonl", "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        pos = [r for r in rows if r["label"] == 1]
        summary["per_split"][s] = {"images": len(pos), "pairs": len(rows),
                                   "pos": len(pos), "neg": len(rows) - len(pos),
                                   "caption_pct": round(100 * np.mean([r["has_caption"] for r in pos]), 1) if pos else 0,
                                   "reports": len({r["report"] for r in rows})}
    for s, rows in rank.items():
        for i, r in enumerate(rows):
            r["pair_id"] = f"rank-{s}-{i:06d}"
        with open(out / f"rank_{s}.jsonl", "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    (config.RESULTS_DIR / "build_summary.json").write_text(json.dumps(summary, indent=2))
    # leakage self-check
    tr = {json.loads(l)["img_hash"] for l in open(out / "pairs_train.jsonl")}
    te = {json.loads(l)["img_hash"] for l in open(out / "pairs_test.jsonl")}
    va = {json.loads(l)["img_hash"] for l in open(out / "pairs_val.jsonl")}
    leak = len(tr & te) + len(tr & va) + len(va & te)
    print(json.dumps(summary, indent=2))
    print(f"\n[CHECK] exact-duplicate images shared across splits: {leak} (must be 0)")
    if leak:
        raise SystemExit("LEAKAGE FOUND")


if __name__ == "__main__":
    main()
