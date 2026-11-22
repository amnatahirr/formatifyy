"""
manual_edit_metrics.py - edit-level (partial credit) scoring for the manual test set.

Exact match gives no credit when a sentence has several errors and the model fixes only some of them.
Here each sentence is turned into a set of word-level edits (input -> gold and input -> model),
and the model's edits are compared with the gold edits:

    TP = edits the model made that are also in the gold
    FP = edits the model made that are not in the gold (wrong or unnecessary change)
    FN = gold edits the model did not make (missed error)
    precision = TP / (TP + FP), recall = TP / (TP + FN), F0.5 weights precision twice as much as recall
    (a grammar checker that makes wrong suggestions annoys users more than one that misses an error).

Input: the CSV files written by show_manual_outputs.py (columns: input, gold, model).

Run (inside brain/ml):
    python3 manual_edit_metrics.py baseline=manual_outputs_baseline.csv v1=manual_outputs_v1.csv v2=manual_outputs_v2.csv
"""
import csv
import re
import sys
import unicodedata
from collections import Counter
from difflib import SequenceMatcher

TOKEN = re.compile(r"\w+|[^\w\s]")


def tokens(text):
    # NFKC turns ligatures such as 'ﬁ' into 'fi', so they do not count as edits
    return TOKEN.findall(unicodedata.normalize("NFKC", text or ""))


def edits(src_tokens, tgt_text):
    """Set of edits (source start, source end, replacement tokens) needed to get from src to tgt."""
    a, b = src_tokens, tokens(tgt_text)
    out = Counter()
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag != "equal":
            out[(i1, i2, tuple(b[j1:j2]))] += 1
    return out


def score(path):
    tp = fp = fn = 0
    n = n_err = n_with_good_edit = n_with_bad_edit = 0
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        src = tokens(r["input"])
        gold, model = edits(src, r["gold"]), edits(src, r["model"])
        good = sum((gold & model).values())
        bad = sum(model.values()) - good
        tp += good
        fp += bad
        fn += sum(gold.values()) - good
        n += 1
        n_err += 1 if gold else 0
        n_with_good_edit += 1 if good else 0
        n_with_bad_edit += 1 if bad else 0
    p = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f05 = 1.25 * p * rec / (0.25 * p + rec) if p + rec else 0.0
    return dict(n=n, n_err=n_err, tp=tp, fp=fp, fn=fn, p=p, r=rec, f05=f05,
                good=n_with_good_edit, bad=n_with_bad_edit)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    print(f"{'system':<10} {'TP':>4} {'FP':>4} {'FN':>4} {'precision':>10} {'recall':>8} {'F0.5':>7} "
          f"{'sents w/ a correct edit':>24} {'sents w/ a wrong edit':>22}")
    for arg in sys.argv[1:]:
        name, path = arg.split("=", 1)
        s = score(path)
        print(f"{name:<10} {s['tp']:>4} {s['fp']:>4} {s['fn']:>4} {s['p']*100:>9.1f}% {s['r']*100:>7.1f}% "
              f"{s['f05']*100:>6.1f}% {s['good']:>20}/{s['n']:<3} {s['bad']:>18}/{s['n']:<3}")


if __name__ == "__main__":
    main()