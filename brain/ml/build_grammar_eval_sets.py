"""
build_grammar_eval_sets.py  -  Grammar Step 4: test sets banana (training se PEHLE).

Input : data/grammar/sentences_test_clean.jsonl, sentences_test_flagged.jsonl
Output: data/grammar/eval/
    test_synthetic.jsonl   saaf sentence + usmein daali hui ek ghalti (jawab maloom hai)
    test_clean.jsonl       saaf sentences jo bilkul nahi badalne chahiye (galat alarm naapne ke liye)
    manual_label.csv       haath se label karne ke liye (3 doston mein baanta hua)

Run (brain/ml ke andar):
    python3 build_grammar_eval_sets.py
"""
import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from grammar_noise import corrupt


def load(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")]


def spread(items, n, rng, per_report=8):
    """n sentences random lo, lekin ek report se zyada se zyada per_report (taake ek report haavi na ho)."""
    items = items[:]
    rng.shuffle(items)
    taken, cnt = [], Counter()
    for it in items:
        if cnt[it["report"]] < per_report:
            taken.append(it)
            cnt[it["report"]] += 1
        if len(taken) == n:
            break
    return taken


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/grammar")
    ap.add_argument("--n_synth", type=int, default=1000)
    ap.add_argument("--n_clean", type=int, default=1000)
    ap.add_argument("--n_manual_flagged", type=int, default=75)
    ap.add_argument("--n_manual_clean", type=int, default=45)
    ap.add_argument("--annotators", default="A,B,C", help="doston ke naam/letters, comma se")
    ap.add_argument("--seed", type=int, default=123)
    args = ap.parse_args()

    d = Path(args.dir)
    out = d / "eval"
    out.mkdir(exist_ok=True)
    rng = random.Random(args.seed)

    clean = load(d / "sentences_test_clean.jsonl")
    flagged = load(d / "sentences_test_flagged.jsonl")
    # chhote/lambe sentences synthetic test ke liye behtar nahi
    pool = [c for c in clean if 8 <= len(c["text"].split()) <= 40]

    # 1) synthetic: ek ghalti per sentence
    synth, used_ids, types = [], set(), Counter()
    cand = spread(pool, args.n_synth * 2, rng, per_report=20)
    for it in cand:
        res = corrupt(it["text"], rng, n_errors=1)
        if not res:
            continue
        bad, kinds = res
        synth.append({"id": f"syn{len(synth):04d}", "report": it["report"], "idx": it["idx"],
                      "corrupted": bad, "original": it["text"], "error_type": kinds[0]})
        used_ids.add((it["report"], it["idx"], it["text"]))
        types[kinds[0]] += 1
        if len(synth) == args.n_synth:
            break

    # 2) clean (unchanged): synthetic wale sentences se alag
    rest = [c for c in pool if (c["report"], c["idx"], c["text"]) not in used_ids]
    cl = spread(rest, args.n_clean, rng, per_report=20)
    clean_out = [{"id": f"cln{i:04d}", "report": c["report"], "idx": c["idx"], "text": c["text"]}
                 for i, c in enumerate(cl)]

    # 3) manual label: flagged + clean ka mix, aur doston mein barabar baanta hua
    mf = spread([f for f in flagged if 6 <= len(f["text"].split()) <= 45], args.n_manual_flagged, rng, per_report=4)
    mc = spread([c for c in clean if 6 <= len(c["text"].split()) <= 45], args.n_manual_clean, rng, per_report=4)
    manual = [(x, "flagged") for x in mf] + [(x, "clean") for x in mc]
    rng.shuffle(manual)
    names = [a.strip() for a in args.annotators.split(",")]

    def dump(name, rows):
        with open(out / name, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    dump("test_synthetic.jsonl", synth)
    dump("test_clean.jsonl", clean_out)

    with open(out / "manual_label.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "annotator", "report", "text", "has_error", "corrected"])
        for i, (x, src) in enumerate(manual):
            w.writerow([f"man{i:03d}", names[i % len(names)], x["report"], x["text"], "", ""])

    print(f"synthetic : {len(synth)} sentences  | error types: {dict(types)}")
    print(f"clean     : {len(clean_out)} sentences")
    print(f"manual    : {len(manual)} sentences ({len(mf)} flagged + {len(mc)} clean), "
          f"{len(manual)//len(names)} per person ({', '.join(names)})")
    print(f"saved in {out}/")


if __name__ == "__main__":
    main()