"""
merge_llm_corrections.py - turn Claude's answers into "wrong -> correct" training pairs.

Reads : data/grammar/llm/selected.jsonl           (written by prepare_correction_batches.py)
        data/grammar/llm/answers/batch_XXX.txt    (Claude's answers, one file per batch)
Writes: data/grammar/train/train_pairs_llm.jsonl
        data/grammar/train/val_pairs_llm.jsonl    (about 10% of the REPORTS, so train and val never share a report)
        data/grammar/llm/check_sample.csv         (random changed pairs to review by eye)

Safety filters:
  - answers are matched by sentence NUMBER, so a missing or extra line cannot shift the alignment
  - pairs where Claude rewrote the sentence heavily (low word similarity or very different length) are dropped
  - unchanged answers are kept as "already correct" pairs

Run (inside brain/ml), as many times as you like while you collect answers:
    python3 merge_llm_corrections.py
"""
import argparse
import csv
import json
import random
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

LINE = re.compile(r"^\s*(\d+)\s*[.)\t:]\s*(.*\S)\s*$")


def parse_answer(path):
    """{number: corrected sentence}. Lines that do not start with a number (code fences, notes) are ignored."""
    out = {}
    for line in open(path, encoding="utf-8"):
        m = LINE.match(line)
        if m:
            out[int(m.group(1))] = " ".join(m.group(2).split())
    return out


def dump(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/grammar")
    ap.add_argument("--min_ratio", type=float, default=0.7, help="min word-level similarity between source and correction")
    ap.add_argument("--val_frac", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=5)
    args = ap.parse_args()

    d = Path(args.dir)
    rng = random.Random(args.seed)
    sel = [json.loads(line) for line in open(d / "llm" / "selected.jsonl", encoding="utf-8")]
    by_batch = {}
    for r in sel:
        by_batch.setdefault(r["batch"], {})[r["num"]] = r

    stats, pairs = Counter(), []
    for b, items in sorted(by_batch.items()):
        ans_path = d / "llm" / "answers" / f"batch_{b:03d}.txt"
        if not ans_path.exists():
            stats["batches without answer yet"] += 1
            continue
        stats["batches with answer"] += 1
        ans = parse_answer(ans_path)
        for num, r in items.items():
            tgt = ans.get(num)
            if tgt is None:
                stats["missing answer line"] += 1
                continue
            src = " ".join(r["text"].split())
            s_words, t_words = src.split(), tgt.split()
            ratio = SequenceMatcher(None, s_words, t_words).ratio()
            len_ratio = len(t_words) / max(1, len(s_words))
            if ratio < args.min_ratio or not (0.7 <= len_ratio <= 1.4):
                stats["dropped (heavy rewrite)"] += 1
                continue
            changed = tgt != src
            pairs.append({"src": src, "tgt": tgt, "errors": ["llm"] if changed else [], "report": r["report"]})
            stats["changed"] += changed
            stats["unchanged"] += not changed

    reports = sorted({p["report"] for p in pairs}, key=str)
    n_val = max(1, round(len(reports) * args.val_frac)) if len(reports) >= 5 else 0
    val_reports = set(rng.sample(reports, n_val)) if n_val else set()
    train = [{k: p[k] for k in ("src", "tgt", "errors")} for p in pairs if p["report"] not in val_reports]
    val = [{k: p[k] for k in ("src", "tgt", "errors")} for p in pairs if p["report"] in val_reports]
    rng.shuffle(train)

    out = d / "train"
    out.mkdir(exist_ok=True)
    dump(out / "train_pairs_llm.jsonl", train)
    dump(out / "val_pairs_llm.jsonl", val)

    changed_pairs = [p for p in train if p["errors"]]
    sample = rng.sample(changed_pairs, min(100, len(changed_pairs)))
    with open(d / "llm" / "check_sample.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["src", "tgt", "ok? (y/n)"])
        for p in sample:
            w.writerow([p["src"], p["tgt"], ""])

    print("stats:", dict(stats))
    print(f"train pairs: {len(train)} | val pairs: {len(val)} (val reports: {len(val_reports)} of {len(reports)})")
    print("\n8 examples of changed pairs:")
    for p in rng.sample(changed_pairs, min(8, len(changed_pairs))):
        print(f"  SRC: {p['src'][:130]}\n  TGT: {p['tgt'][:130]}\n")
    print(f"review {d / 'llm' / 'check_sample.csv'} by eye before training on it")


if __name__ == "__main__":
    main()