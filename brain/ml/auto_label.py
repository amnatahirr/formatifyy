"""
auto_label_headings.py  -  Step 1 of the FYP report checker.

data/parsed/*.jsonl se:
  1. har block ko rules se auto-label karta hai (H1/H2/H3/Body/Caption, + Noise/Front jo train mein nahi jayenge)
  2. project-level (group) train/val/test split banata hai, taake same project ke PDF+DOCX alag na hon
  3. manual review ke liye ek CSV banata hai (sirf test groups se)
  4. scanned/khali PDFs ki list banata hai (OCR candidates)
  5. duplicate projects ki list banata hai

Run (brain/ml ke andar):
    python3 auto_label_headings.py --parsed data/parsed --out data/labels

Output:
    data/labels/headings_auto.jsonl     <- features + auto_label + split
    data/labels/to_review.csv           <- ~400 lines, 'gold_label' column haath se bharni hai
    data/labels/_ocr_candidates.csv
    data/labels/_duplicate_groups.csv
"""
import argparse
import csv
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

NUM = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s+(?=\S)")
CHAP = re.compile(r"^\s*(chapter|appendix)\s*:?\s*[\dA-Z]+", re.I)
CAP_STRONG = re.compile(r"^\s*(figure|fig\.|table)\s*\d+(\.\d+)*\s*[:.\-–—]", re.I)
CAP_WEAK = re.compile(r"^\s*(figure|fig\.|table)\s*\d+(\.\d+)*\b", re.I)
PAGE_BARE = re.compile(r"^\s*(page\s*)?\d+\s*$", re.I)
PAGE_FOOTER = re.compile(r"^\s*(page\s*\d+|\d+\s+of\s+\d+)\b", re.I)   # "Page 13 of 117 ...", "34 of 73 ..."
TOC_LEADER = re.compile(r"(\.\s*){5,}")                                  # "2. Literature Review ........ 7"

TRAIN_LABELS = ["H1", "H2", "H3", "Body", "Caption"]
REVIEW_LABELS = TRAIN_LABELS + ["Unsure"]   # Unsure = kamzor rule (bold_short), haath se dekhna hai


def num_level(t: str) -> int:
    """'3.2 System Architecture' -> 2, '2.5.1.6 FR 06' -> 4, '2. Intro' -> 1, warna 0.
    Level-1 numbers sirf 1..12 aur agla lafz bara harf (reference list '13 Social media' reject)."""
    m = NUM.match(t)
    if not m:
        return 0
    parts = m.group(1).split(".")
    rest = t[m.end():]
    if not rest or not rest[0].isalpha():
        return 0
    if len(parts) == 1 and not (int(parts[0]) <= 12 and rest[0].isupper()):
        return 0
    return len(parts)


def group_key(report: str) -> str:
    """'SE22_VR SURVIVAL SIMULATION ' -> 'vrsurvivalsimulation' (PDF aur DOCX ek hi group)."""
    s = re.sub(r"^[A-Za-z]{2,3}\s*\d+[\s_\-–]*", "", report)
    key = re.sub(r"[^a-z0-9]", "", s.lower())
    return key or re.sub(r"[^a-z0-9]", "", report.lower())


def body_font_size(rows):
    """Report ka body font = sab se zyada text wala font size."""
    w = Counter()
    for r in rows:
        if r.get("font_size"):
            w[round(r["font_size"], 1)] += len(r["text"])
    return w.most_common(1)[0][0] if w else None


def auto_label(r, body):
    t = r["text"].strip()
    words = len(t.split())
    page = r.get("page")
    style = r.get("style") or ""

    if PAGE_BARE.match(t) or PAGE_FOOTER.match(t):
        return "Noise", "page_number"
    if TOC_LEADER.search(t):
        return "TOC", "dot_leader"               # table of contents / list of figures entries
    if page is not None and page <= 2:
        return "Front", "front_matter"          # title page / certificates / forms
    if CAP_STRONG.match(t) and words <= 40:
        return "Caption", "caption_regex"
    if CAP_WEAK.match(t) and words <= 12 and not t.endswith((".", ",", ";")):
        return "Caption", "caption_weak"
    m = re.match(r"Heading (\d)", style)
    if m:
        return f"H{min(int(m.group(1)), 3)}", "docx_style"
    if style == "Caption":
        return "Caption", "docx_style"

    size = r.get("font_size")
    ratio = size / body if size and body else 1.0
    bold = bool(r.get("bold"))
    short = words <= 15 and not t.endswith((".", ",", ";"))

    if short:
        lvl = num_level(t)
        if lvl == 1 and (words > 8 or not (bold or ratio >= 1.1)):
            return "Body", "list_item"          # "2 Click Add new", "5 Correct password entered"
        if lvl:
            return f"H{min(lvl, 3)}", "numbering"
        if CHAP.match(t):
            return "H1", "numbering"
        if bold and ratio >= 1.3:
            return "H1", "bold_big"
        if bold and ratio >= 1.15:
            return "H2", "bold_medium"
        if bold and words <= 10:
            return "Unsure", "bold_short"        # table labels / form fields bhi hote hain -> train mein nahi
    return "Body", "default"


def features(r, body):
    t = r["text"].strip()
    letters = [c for c in t if c.isalpha()]
    size = r.get("font_size")
    return {
        "font_size": size,
        "size_ratio": round(size / body, 3) if size and body else 1.0,
        "bold": bool(r.get("bold")),
        "n_words": len(t.split()),
        "n_chars": len(t),
        "page": r.get("page"),
        "x0": r.get("x0"),
        "y0": r.get("y0"),
        "has_num_prefix": bool(num_level(t) or CHAP.match(t)),
        "num_level": num_level(t),
        "has_dot_leader": bool(TOC_LEADER.search(t)),
        "ends_period": t.endswith("."),
        "upper_ratio": round(sum(c.isupper() for c in letters) / len(letters), 3) if letters else 0.0,
        "is_title_case": t.istitle(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parsed", default="data/parsed")
    ap.add_argument("--out", default="data/labels")
    ap.add_argument("--review_n", type=int, default=400)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    parsed, out = Path(args.parsed), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    random.seed(args.seed)

    files = sorted(p for p in parsed.glob("*.jsonl"))
    print(f"{len(files)} reports")

    reports = {}          # report -> rows
    for f in files:
        reports[f.stem] = [json.loads(l) for l in open(f, encoding="utf-8")]

    # ---- groups + split (project level) ----
    groups = defaultdict(list)
    for rep in reports:
        groups[group_key(rep)].append(rep)
    keys = sorted(groups)
    random.shuffle(keys)
    n = len(keys)
    split_of = {}
    for i, k in enumerate(keys):
        split_of[k] = "train" if i < 0.70 * n else ("val" if i < 0.85 * n else "test")

    with open(out / "_duplicate_groups.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["group", "n_files", "files"])
        for k, reps in sorted(groups.items()):
            if len(reps) > 1:
                w.writerow([k, len(reps), " | ".join(reps)])

    # ---- OCR candidates ----
    ocr = []
    for rep, rows in reports.items():
        pages = [r["page"] for r in rows if r.get("page")]
        if not pages:
            continue                              # DOCX: page nahi hota, OCR ka masla nahi
        n_pages = max(pages)
        chars = sum(len(r["text"]) for r in rows)
        if chars / n_pages < 400 or len(rows) / n_pages < 4:
            ocr.append((rep, n_pages, len(rows), chars, round(chars / n_pages)))
    with open(out / "_ocr_candidates.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["report", "pages", "blocks", "chars", "chars_per_page"])
        w.writerows(sorted(ocr, key=lambda x: x[4]))
    ocr_set = {o[0] for o in ocr}

    # ---- labels ----
    counts = Counter()
    review_pool = defaultdict(list)
    with open(out / "headings_auto.jsonl", "w", encoding="utf-8") as fh:
        for rep, rows in reports.items():
            body = body_font_size(rows)
            g = group_key(rep)
            for r in rows:
                label, reason = auto_label(r, body)
                rec = {
                    "report": rep, "group": g, "split": split_of[g], "idx": r["idx"],
                    "text": r["text"], "auto_label": label, "label_reason": reason,
                    "ocr_candidate": rep in ocr_set,
                    **features(r, body),
                }
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                counts[label] += 1
                if rec["split"] == "test" and label in REVIEW_LABELS and rep not in ocr_set:
                    review_pool[label].append(rec)

    # ---- manual review sample (test groups only, class-balanced-ish) ----
    per = args.review_n // len(REVIEW_LABELS)
    sample = []
    for lab in REVIEW_LABELS:
        pool = review_pool[lab]
        random.shuffle(pool)
        sample += pool[:per]
    random.shuffle(sample)
    with open(out / "to_review.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["report", "idx", "page", "font_size", "bold", "text", "auto_label", "label_reason", "gold_label"])
        for s in sample:
            w.writerow([s["report"], s["idx"], s["page"], s["font_size"], s["bold"],
                        s["text"][:200], s["auto_label"], s["label_reason"], ""])

    # ---- summary ----
    print("\nAuto-label counts:")
    for lab, c in counts.most_common():
        print(f"  {lab:8s} {c}")
    print(f"\nProjects (groups): {n} | duplicates: {sum(1 for r in groups.values() if len(r) > 1)}")
    print("Split (groups):", Counter(split_of.values()))
    print(f"OCR candidates: {len(ocr)} (data/labels/_ocr_candidates.csv)")
    print(f"Review sample: {len(sample)} lines -> data/labels/to_review.csv")


if __name__ == "__main__":
    main()