"""
evaluate_headings_v3.py  -  Rules vs v2 vs v3 on the GOLD set, in two views.

  (a) normal   : the gold lines with their real formatting (as parsed).
  (b) stripped : formatting removed - every line gets the same font size,
                 no bold, no style. This is what a messy, unformatted input
                 looks like. v3 uses text only, so it is the same in both views.

Context for v3 (previous / next line) is built per report in reading order,
skipping Noise / TOC / Front lines, exactly as in training.
gold_label is read only here, for the final report. No gold-informed change
was made to v3.

Outputs (results/headings_v3/): metrics.json, per_class.csv, comparison.md,
confusion_matrix_normal.png, confusion_matrix_stripped.png

Run (inside brain/ml):  python evaluate_headings_v3.py
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from evaluate_headings import HERE, bootstrap_ci, plot_side_by_side, score  # adds backend/ to sys.path
from functions.heading_local import (  # noqa: E402
    LABELS, ML_DIR, block_features, body_font_size, load_model, predict_rows, rule_label,
)
from functions.heading_text import load_model_v3, predict_v3  # noqa: E402

SKIP_IN_CONTEXT = {"Noise", "TOC", "Front"}
FLAT_SIZE = 12.0   # stripped view: every line has this size


def load_all(labels_path, parsed_dir):
    raw, body_of = {}, {}
    for f in sorted(Path(parsed_dir).glob("*.jsonl")):
        rows = [json.loads(l) for l in open(f, encoding="utf-8")]
        body_of[f.stem] = body_font_size((r["text"], r.get("font_size")) for r in rows)
        for r in rows:
            raw[(f.stem, r["idx"])] = r
    seq = defaultdict(list)                         # report -> idx list used as v3 context
    split_of_group, group_of_report = {}, {}
    for line in open(labels_path, encoding="utf-8"):
        rec = json.loads(line)
        split_of_group[rec["group"]] = rec["split"]
        group_of_report[rec["report"]] = rec["group"]
        if rec["auto_label"] not in SKIP_IN_CONTEXT:
            seq[rec["report"]].append(rec["idx"])
    return raw, body_of, seq, split_of_group, group_of_report


def v3_predictions(keys, raw, seq, model):
    """(label, conf) for each (report, idx), predicting whole reports for context."""
    out = {}
    for rep in {r for r, _ in keys}:
        idxs = sorted(seq[rep])
        for i, p in zip(idxs, predict_v3([raw[(rep, i)]["text"] for i in idxs], model)):
            out[(rep, i)] = p
    return [out[k] for k in keys]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default=str(HERE / "data/labels/headings_auto.jsonl"))
    ap.add_argument("--parsed", default=str(HERE / "data/parsed"))
    ap.add_argument("--gold", default=str(HERE / "data/labels/to_review.csv"))
    ap.add_argument("--results", default=str(HERE / "results/headings_v3"))
    args = ap.parse_args()
    out = Path(args.results)
    out.mkdir(parents=True, exist_ok=True)

    raw, body_of, seq, split_of_group, group_of_report = load_all(args.labels, args.parsed)
    v2 = load_model(ML_DIR / "models/headings_xgb_v2.json")
    v3 = load_model_v3(ML_DIR / "models/headings_xgb_v3.json")

    gold_rows = list(csv.DictReader(open(args.gold, newline="", encoding="utf-8")))
    bad = {group_of_report[r["report"]] for r in gold_rows} - {g for g, s in split_of_group.items() if s == "test"}
    assert not bad, f"LEAK: gold projects outside the test split: {bad}"
    gold = [r for r in gold_rows if r["gold_label"].strip() in LABELS]
    keys = [(r["report"], int(r["idx"])) for r in gold]
    y = [r["gold_label"].strip() for r in gold]
    missing_ctx = sum(k[1] not in set(seq[k[0]]) for k in keys)
    assert missing_ctx == 0, f"{missing_ctx} gold lines are not in the v3 context sequence"

    v3_pred = v3_predictions(keys, raw, seq, v3)
    metrics = {"gold_rows_used": len(gold), "leakage_check": "passed",
               "gold_informed_changes_to_v3": "none", "views": {}}
    for view in ("normal", "stripped"):
        rules, feats = [], []
        for rep, idx in keys:
            r = raw[(rep, idx)]
            if view == "normal":
                fs, b, st, body = r.get("font_size"), r.get("bold"), r.get("style"), body_of[rep]
            else:
                fs, b, st, body = FLAT_SIZE, False, None, FLAT_SIZE
            rules.append(rule_label(r["text"], fs, b, st, body))
            feats.append(block_features(r["text"], fs, b, st, body))
        v2_pred = [l for l, _ in predict_rows(feats, v2)]
        preds = {"Rules": rules, "v2 (format)": v2_pred, "v3 (text+context)": [l for l, _ in v3_pred]}
        res = {name: {**score(y, p), **bootstrap_ci(y, p)} for name, p in preds.items()}
        metrics["views"][view] = res
        plot_side_by_side(res, f"GOLD set - {view} view", out / f"confusion_matrix_{view}.png")

    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    with open(out / "per_class.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["view", "model", "class", "precision", "recall", "f1", "support"])
        for view, res in metrics["views"].items():
            for name, m in res.items():
                for lab, d in m["per_class"].items():
                    w.writerow([view, name, lab, d["precision"], d["recall"], d["f1"], d["support"]])

    head = ["View", "Model", "Accuracy", "Macro-F1 (95% CI)", "Heading-vs-not F1"] + [f"F1 {l}" for l in LABELS]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for view, res in metrics["views"].items():
        for name, m in res.items():
            ci = m["macro_f1_95ci"]
            lines.append("| " + " | ".join([view, name, f"{m['accuracy']:.3f}",
                                             f"{m['macro_f1']:.3f} ({ci[0]:.3f}-{ci[1]:.3f})",
                                             f"{m['heading_vs_not_f1']:.3f}"]
                                            + [f"{m['per_class'][l]['f1']:.3f}" for l in LABELS]) + " |")
    text = ("# Heading detection on GOLD: Rules vs v2 vs v3, normal vs stripped\n\n" + "\n".join(lines) +
            f"\n\nGold: {len(gold)} lines from test projects (leakage check passed). "
            "v3: no gold-informed changes. Stripped = same font size, no bold, no style for every line.\n")
    (out / "comparison.md").write_text(text)
    print(text)
    print("Gold label counts:", dict(Counter(y)))


if __name__ == "__main__":
    main()
