"""
threshold_table_v3.py  -  choose the v3 fallback threshold.

For each threshold: % of lines sent to Claude, accuracy on the lines kept
locally, and % of the local model's errors that would reach Claude.

Data:
  - gold-2 (results/real_docs/gold2_template.csv) once 'my_label' is filled.
    This is the real use case (unformatted Word files).
  - gold STRIPPED until then (formatting removed, so every document is flat
    and the flat-document factor is applied).
NOTE: choosing the threshold from this table is a gold-informed choice.

Run (inside brain/ml):  python threshold_table_v3.py
"""
import contextlib
import csv
import io
import json
import sys
from pathlib import Path

import numpy as np

from evaluate_headings_v3 import HERE, load_all, v3_predictions  # adds backend/ to sys.path
from functions.heading_local import LABELS, ML_DIR  # noqa: E402
from functions.heading_text import is_flat_document, load_model_v3, predict_v3  # noqa: E402
from engine import FLAT_DOC_CONFIDENCE_FACTOR  # noqa: E402

THRESHOLDS = [0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
OUT = HERE / "results/headings_v3"


def table(y, pred, conf):
    y, pred, conf = np.array(y), np.array(pred), np.array(conf)
    wrong = pred != y
    rows = []
    for t in THRESHOLDS:
        keep = conf >= t
        rows.append({
            "threshold": t,
            "sent_to_claude_pct": round(100 * (1 - keep.mean()), 1),
            "accuracy_on_kept": round(float((pred[keep] == y[keep]).mean()), 4) if keep.any() else None,
            "errors_sent_to_claude_pct": round(100 * float((wrong & ~keep).sum() / max(wrong.sum(), 1)), 1),
        })
    return rows


def show(name, rows, n):
    print(f"\n{name}  ({n} lines)")
    print(f"  {'threshold':>9} | {'% to Claude':>11} | {'acc on rest':>11} | {'% of errors caught':>18}")
    for r in rows:
        acc = "-" if r["accuracy_on_kept"] is None else f"{r['accuracy_on_kept']:.4f}"
        print(f"  {r['threshold']:>9.2f} | {r['sent_to_claude_pct']:>10.1f}% | {acc:>11} | "
              f"{r['errors_sent_to_claude_pct']:>17.1f}%")


def gold_stripped():
    raw, _, seq, _, _ = load_all(HERE / "data/labels/headings_auto.jsonl", HERE / "data/parsed")
    gold = [r for r in csv.DictReader(open(HERE / "data/labels/to_review.csv", encoding="utf-8"))
            if r["gold_label"].strip() in LABELS]
    keys = [(r["report"], int(r["idx"])) for r in gold]
    preds = v3_predictions(keys, raw, seq, load_model_v3(ML_DIR / "models/headings_xgb_v3.json"))
    y = [r["gold_label"].strip() for r in gold]
    # stripped = no formatting at all -> always a flat document
    return y, [p for p, _ in preds], [c * FLAT_DOC_CONFIDENCE_FACTOR for _, c in preds]


def gold2(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows or not all(r["my_label"].strip() in LABELS for r in rows):
        return None
    from pipeline.parser import parse_file
    y, pred, conf = [], [], []
    for file in sorted({r["file"] for r in rows}):
        fpath = Path(file) if Path(file).is_absolute() else ML_DIR.parents[1] / "backend" / file
        with contextlib.redirect_stdout(io.StringIO()):
            doc = parse_file(str(fpath), fpath.name)
        blocks = [b for b in doc.paragraphs if (b.text or "").strip()]
        factor = FLAT_DOC_CONFIDENCE_FACTOR if is_flat_document(blocks) else 1.0
        p = predict_v3([b.text for b in blocks])
        for r in (r for r in rows if r["file"] == file):
            lab, c = p[int(r["line_no"])]
            y.append(r["my_label"].strip()); pred.append(lab); conf.append(c * factor)
    return y, pred, conf


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    result = {}
    g2 = gold2(HERE / "results/real_docs/gold2_template.csv")
    if g2:
        result["gold2"] = table(*g2)
        show("GOLD-2 (your unformatted files)", result["gold2"], len(g2[0]))
    else:
        print("gold-2 not filled yet (my_label must be H1/H2/H3/Body/Caption on every row) - using gold stripped.")
    gs = gold_stripped()
    result["gold_stripped"] = table(*gs)
    show(f"GOLD STRIPPED (flat factor x{FLAT_DOC_CONFIDENCE_FACTOR} applied)", result["gold_stripped"], len(gs[0]))
    result["note"] = "Choosing the threshold from this table is a gold-informed choice."
    (OUT / "threshold_table_gold.json").write_text(json.dumps(result, indent=2))
    print(f"\nSaved -> {OUT/'threshold_table_gold.json'}")


if __name__ == "__main__":
    sys.exit(main())
