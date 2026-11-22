"""
extract_grammar_sentences.py  -  Grammar Step 2.

data/labels/headings_auto.jsonl se sirf saaf Body text ke sentences nikaalta hai,
splits.csv ke mutabiq train/val/test mein baantta hai.

Run (brain/ml ke andar):
    python3 extract_grammar_sentences.py

Output (data/grammar/):
    sentences_train.jsonl, sentences_val.jsonl, sentences_test.jsonl
    har line: {"report":..., "idx":..., "text":...}
"""
import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

URL = re.compile(r"https?://|www\.|\S+@\S+\.\S+", re.I)
CODE = re.compile(r"[{}]|\(\)\s*;|=>|\bdef \w+\(|\bfrom \w+ import |\bimport \w+\.\w+|\bclass \w+\s*[(:]|</?\w+>|::|==|\bself\.")
REQ_ID = re.compile(r"^(?:[A-Z]{2,4}[-\s]?\d+(?:[.\-]\d+)*[:.]?)\s+(?=[A-Z])")   # "FR18-03 The system..." -> "The system..."
BIB = re.compile(r"^[A-Z][\w\-]+(?: [A-Z]\.)?,\s+[\u201c\"]|\bpp\.\s*\d|\bvol\.\s*\d|\bProc\.\s|\bet al\.,\s*[\u201c\"]")  # reference-list lines
ABBR = ["e.g.", "i.e.", "etc.", "et al.", "vs.", "Fig.", "fig.", "No.", "no.", "Dr.", "Mr.", "Ms.", "Prof.", "approx."]
SPLIT = re.compile(r'(?<=[.!?])\s+(?=["“(\[]?[A-Z0-9])')


def clean(t: str) -> str:
    t = t.replace(chr(173), "").replace(chr(160), " ")   # soft hyphen, nbsp
    t = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", t)      # PDF line-break hyphenation
    t = re.sub(r"\s+", " ", t).strip()
    return t


def split_sentences(t: str):
    for i, a in enumerate(ABBR):
        t = t.replace(a, a.replace(".", f"<DOT{i}>"))
    parts = SPLIT.split(t)
    for p in parts:
        for i, a in enumerate(ABBR):
            p = p.replace(a.replace(".", f"<DOT{i}>"), a)
        yield p.strip()


def good_sentence(s: str, min_w: int, max_w: int) -> bool:
    w = s.split()
    if not (min_w <= len(w) <= max_w):
        return False
    if not s[0].isupper() or s[-1] not in ".!?":
        return False
    if URL.search(s) or CODE.search(s):
        return False
    letters = sum(c.isalpha() for c in s)
    if letters / len(s) < 0.75:                      # numbers/symbols heavy
        return False
    if s.count(",") > 8 or s.count("|") or s.count("_") > 1:
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default="data/labels/headings_auto.jsonl")
    ap.add_argument("--splits", default="data/labels/splits.csv")
    ap.add_argument("--out", default="data/grammar")
    ap.add_argument("--min_words", type=int, default=6)
    ap.add_argument("--max_words", type=int, default=60)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    split_of, group_of = {}, {}
    with open(args.splits, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            split_of[r["report"]] = r["split"]
            group_of[r["report"]] = r["group"]

    rows = defaultdict(list)                         # report -> body rows
    is_docx = {}                                     # report -> True agar page nahi
    for line in open(args.labels, encoding="utf-8"):
        r = json.loads(line)
        rep = r["report"]
        is_docx.setdefault(rep, True)
        if r.get("page") is not None:
            is_docx[rep] = False
        if r["ocr_candidate"]:
            continue                                 # scanned PDF: text kharab
        if r["auto_label"] == "Body" and r["label_reason"] == "default":
            rows[rep].append(r)

    # har project (group) ki sirf ek file: DOCX ko tarjeeh
    best = {}
    for rep in rows:
        g = group_of.get(rep)
        if g is None:
            continue
        if g not in best or (is_docx[rep] and not is_docx[best[g]]):
            best[g] = rep
    chosen = set(best.values())

    data = {"train": [], "val": [], "test": []}
    stats = Counter()
    for rep in sorted(chosen):
        sp = split_of[rep]
        seen_in_report = set()
        for r in rows[rep]:
            for s in split_sentences(clean(r["text"])):
                s = REQ_ID.sub("", s)
                if BIB.search(s):
                    stats["dropped_reference"] += 1
                    continue
                if not good_sentence(s, args.min_words, args.max_words):
                    stats["dropped_bad"] += 1
                    continue
                key = s.lower()
                if key in seen_in_report:
                    stats["dropped_dup_in_report"] += 1
                    continue
                seen_in_report.add(key)
                data[sp].append({"report": rep, "idx": r["idx"], "text": s})

    # leakage guard: val/test mein jo sentence aaye wo train mein nahi rahega; val vs test bhi alag
    test_keys = {d["text"].lower() for d in data["test"]}
    val_keys = {d["text"].lower() for d in data["val"]} - test_keys
    data["val"] = [d for d in data["val"] if d["text"].lower() not in test_keys]
    before = len(data["train"])
    data["train"] = [d for d in data["train"] if d["text"].lower() not in test_keys | val_keys]
    stats["train_removed_leak"] = before - len(data["train"])

    for sp, items in data.items():
        with open(out / f"sentences_{sp}.jsonl", "w", encoding="utf-8") as fh:
            for it in items:
                fh.write(json.dumps(it, ensure_ascii=False) + "\n")

    print(f"projects used: {len(chosen)} (1 file per project, DOCX preferred)")
    for sp in ("train", "val", "test"):
        reps = len({d['report'] for d in data[sp]})
        print(f"  {sp:5s}: {len(data[sp]):7d} sentences from {reps} reports")
    print("dropped:", dict(stats))
    print(f"saved in {out}/")


if __name__ == "__main__":
    main()