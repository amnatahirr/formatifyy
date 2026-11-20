"""
evaluate_headings.py  -  Task 1, Step 3: compare Rules vs XGBoost (vs Claude later).

Two views:
  A. TEST split vs AUTO labels (39 projects, many rows).
     Warning: auto labels were MADE by the rules, so Rules score ~100% here by
     construction. This view only shows how closely XGBoost copies the rules.
  B. GOLD set (396 hand-labelled lines from test projects).  <- the real score.
     This is the ONLY place in the project where gold_label is read.

Before scoring, it checks that no gold project is in the train or val split.

Outputs (results/headings/):
  metrics.json             all numbers
  per_class.csv            precision / recall / F1 per class, per model, per view
  confusion_matrix.png     GOLD set: Rules vs XGBoost side by side
  confusion_matrix_test_auto.png   view A

Optional: --claude_preds file.csv (columns report,idx,label) adds a Claude column.

Run (inside brain/ml):
    ../../.venv/bin/python evaluate_headings.py
"""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "backend"))
from functions.heading_local import (  # noqa: E402
    LABELS, block_features, body_font_size, load_model, predict_rows, rule_label,
)

HEADINGS = {"H1", "H2", "H3"}


def score(y_true, y_pred):
    """Accuracy, macro-F1, heading-vs-not F1, per-class numbers, confusion matrix."""
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=LABELS, zero_division=0)
    is_h_true = [t in HEADINGS for t in y_true]
    is_h_pred = [t in HEADINGS for t in y_pred]
    return {
        "n": len(y_true),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "macro_f1": round(float(f1_score(y_true, y_pred, labels=LABELS, average="macro", zero_division=0)), 4),
        "heading_vs_not_f1": round(float(f1_score(is_h_true, is_h_pred, zero_division=0)), 4),
        "per_class": {lab: {"precision": round(float(p[i]), 4), "recall": round(float(r[i]), 4),
                            "f1": round(float(f[i]), 4), "support": int(s[i])} for i, lab in enumerate(LABELS)},
        "confusion_matrix": {"labels": LABELS,
                             "matrix": confusion_matrix(y_true, y_pred, labels=LABELS).tolist()},
    }


def bootstrap_ci(y_true, y_pred, n=1000, seed=0):
    """95% range for accuracy and macro-F1 (resampling the lines). Small sets are noisy."""
    rng = np.random.default_rng(seed)
    yt, yp = np.array(y_true), np.array(y_pred)
    accs, f1s = [], []
    for _ in range(n):
        i = rng.integers(0, len(yt), len(yt))
        accs.append(accuracy_score(yt[i], yp[i]))
        f1s.append(f1_score(yt[i], yp[i], labels=LABELS, average="macro", zero_division=0))
    q = lambda v: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]
    return {"accuracy_95ci": q(accs), "macro_f1_95ci": q(f1s)}


def plot_side_by_side(results, title, path):
    fig, axes = plt.subplots(1, len(results), figsize=(5.2 * len(results), 4.6))
    axes = np.atleast_1d(axes)
    for ax, (name, res) in zip(axes, results.items()):
        m = np.array(res["confusion_matrix"]["matrix"])
        ax.imshow(m, cmap="Blues")
        for i in range(len(LABELS)):
            for j in range(len(LABELS)):
                ax.text(j, i, m[i, j], ha="center", va="center",
                        color="white" if m[i, j] > m.max() / 2 else "black", fontsize=9)
        ax.set_xticks(range(len(LABELS)), LABELS)
        ax.set_yticks(range(len(LABELS)), LABELS)
        ax.set_xlabel("Predicted")
        ax.set_ylabel("True")
        ax.set_title(f"{name}\nacc {res['accuracy']:.3f} | macro-F1 {res['macro_f1']:.3f}", fontsize=10)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default=str(HERE / "data/labels/headings_auto.jsonl"))
    ap.add_argument("--parsed", default=str(HERE / "data/parsed"))
    ap.add_argument("--gold", default=str(HERE / "data/labels/to_review.csv"))
    ap.add_argument("--results", default=str(HERE / "results/headings"))
    ap.add_argument("--threshold", type=float, default=0.70)
    ap.add_argument("--claude_preds", default=None, help="optional CSV: report,idx,label")
    ap.add_argument("--model", default=str(HERE / "models/headings_xgb.json"))
    ap.add_argument("--version", default="v1 (before any gold-informed fix)")
    args = ap.parse_args()
    out = Path(args.results)
    out.mkdir(parents=True, exist_ok=True)

    # ---- raw blocks + body font per report ----
    raw, body_of = {}, {}
    for f in sorted(Path(args.parsed).glob("*.jsonl")):
        rows = [json.loads(l) for l in open(f, encoding="utf-8")]
        body_of[f.stem] = body_font_size((r["text"], r.get("font_size")) for r in rows)
        for r in rows:
            raw[(f.stem, r["idx"])] = r

    def run_models(keys):
        """Rules + XGBoost predictions for a list of (report, idx)."""
        rules, feats = [], []
        for rep, idx in keys:
            r, body = raw[(rep, idx)], body_of[rep]
            rules.append(rule_label(r["text"], r.get("font_size"), r.get("bold"), r.get("style"), body))
            feats.append(block_features(r["text"], r.get("font_size"), r.get("bold"), r.get("style"), body))
        xgb = predict_rows(feats, model)
        return rules, [l for l, _ in xgb], np.array([c for _, c in xgb])

    model = load_model(Path(args.model))
    split_of_group, group_of_report, view_a = {}, {}, []
    for line in open(args.labels, encoding="utf-8"):
        rec = json.loads(line)
        split_of_group[rec["group"]] = rec["split"]
        group_of_report[rec["report"]] = rec["group"]
        if rec["split"] == "test" and rec["auto_label"] in LABELS:
            view_a.append(((rec["report"], rec["idx"]), rec["auto_label"]))

    metrics = {"version": args.version, "model": Path(args.model).name, "threshold": args.threshold}
    print(f"=== {args.version} | model {Path(args.model).name} ===")

    # ================= View A: test split vs auto labels =================
    keys, y = [k for k, _ in view_a], [lab for _, lab in view_a]
    rules, xgb, conf = run_models(keys)
    keep = conf >= args.threshold
    view = {"Rules": score(y, rules), "XGBoost": score(y, xgb)}
    metrics["A_test_vs_auto_labels"] = {
        "note": "Auto labels come from the rules, so Rules ~1.0 here by construction. Not the real score.",
        "models": view,
        "xgb_confident_only": {"kept_pct": round(100 * keep.mean(), 2),
                               "accuracy": round(float(accuracy_score(np.array(y)[keep], np.array(xgb)[keep])), 4)},
    }
    plot_side_by_side(view, "Test split vs AUTO labels (rule-made, noisy)", out / "confusion_matrix_test_auto.png")

    # ================= View B: gold set =================
    gold_rows = list(csv.DictReader(open(args.gold, newline="", encoding="utf-8")))

    # Leakage check: every gold project must be a test project.
    gold_groups = {group_of_report[r["report"]] for r in gold_rows}
    bad = {g: split_of_group[g] for g in gold_groups if split_of_group[g] != "test"}
    train_val_reports = {rep for rep, g in group_of_report.items() if split_of_group[g] != "test"}
    assert not bad, f"LEAK: gold projects found in train/val: {bad}"
    assert not ({r["report"] for r in gold_rows} & train_val_reports), "LEAK: gold report in train/val"

    # Sanity check: gold row (report, idx) points to the same text in parsed data.
    mismatched = [r for r in gold_rows
                  if raw[(r["report"], int(r["idx"]))]["text"][:200].strip() != r["text"].strip()]

    excluded = Counter(r["gold_label"].strip() for r in gold_rows if r["gold_label"].strip() not in LABELS)
    gold = [r for r in gold_rows if r["gold_label"].strip() in LABELS]
    keys = [(r["report"], int(r["idx"])) for r in gold]
    y = [r["gold_label"].strip() for r in gold]
    rules, xgb, conf = run_models(keys)
    keep = conf >= args.threshold

    view = {"Rules": score(y, rules), "XGBoost": score(y, xgb)}
    for name, pred in (("Rules", rules), ("XGBoost", xgb)):
        view[name].update(bootstrap_ci(y, pred))
    if args.claude_preds:
        cp = {(r["report"], int(r["idx"])): r["label"] for r in csv.DictReader(open(args.claude_preds))}
        claude = [cp.get(k, "Body") for k in keys]
        view["Claude"] = {**score(y, claude), **bootstrap_ci(y, claude)}
    # Explain errors: accuracy grouped by the auto label the line was sampled from.
    by_auto = {}
    for lab in sorted({r["auto_label"] for r in gold}):
        idx = [i for i, r in enumerate(gold) if r["auto_label"] == lab]
        by_auto[lab] = {"n": len(idx),
                        "Rules_acc": round(sum(rules[i] == y[i] for i in idx) / len(idx), 4),
                        "XGBoost_acc": round(sum(xgb[i] == y[i] for i in idx) / len(idx), 4)}
    yk, xk = np.array(y)[keep], np.array(xgb)[keep]
    metrics["B_gold"] = {
        "note": "Hand-labelled lines from test projects only. THIS is the score to report.",
        "leakage_check": {"gold_projects": len(gold_groups), "in_train_or_val": 0, "passed": True},
        "text_alignment_mismatches": len(mismatched),
        "rows_used": len(gold), "rows_excluded_by_gold_label": dict(excluded),
        "gold_label_counts": dict(Counter(y)),
        "models": view,
        "Claude": view.get("Claude", "not run yet (pass --claude_preds)"),
        "accuracy_by_sampled_auto_label": by_auto,
        "text_mismatch_examples": [(r["report"], r["idx"]) for r in mismatched],
        "xgb_with_threshold": {
            "would_go_to_claude_pct": round(100 * (1 - keep.mean()), 2),
            "accuracy_on_confident": round(float(accuracy_score(yk, xk)), 4) if keep.any() else None,
            "accuracy_on_unsure": round(float(accuracy_score(np.array(y)[~keep], np.array(xgb)[~keep])), 4)
            if (~keep).any() else None,
        },
    }
    plot_side_by_side({k: v for k, v in view.items()}, "GOLD set (hand labels): the real comparison",
                      out / "confusion_matrix.png")

    # ---- save ----
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    with open(out / "per_class.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["view", "model", "class", "precision", "recall", "f1", "support"])
        for vname, vkey in (("gold", "B_gold"), ("test_auto", "A_test_vs_auto_labels")):
            for mname, res in metrics[vkey]["models"].items():
                for lab, d in res["per_class"].items():
                    w.writerow([vname, mname, lab, d["precision"], d["recall"], d["f1"], d["support"]])

    # ---- print ----
    a = metrics["A_test_vs_auto_labels"]["models"]
    print(f"View A  test vs AUTO labels ({a['Rules']['n']} rows) - rule-made labels, not the real score")
    for name, res in a.items():
        print(f"  {name:8s} acc {res['accuracy']:.4f}  macro-F1 {res['macro_f1']:.4f}")
    b = metrics["B_gold"]
    print(f"\nView B  GOLD set ({b['rows_used']} rows used, excluded {b['rows_excluded_by_gold_label']}, "
          f"text mismatches {b['text_alignment_mismatches']}) - leakage check passed")
    print(f"  {'model':8s} {'acc':>7} {'macro-F1':>9} {'head-F1':>8}   95% CI macro-F1")
    for name, res in b["models"].items():
        print(f"  {name:8s} {res['accuracy']:7.4f} {res['macro_f1']:9.4f} {res['heading_vs_not_f1']:8.4f}   "
              f"{res['macro_f1_95ci']}")
    print("\n  Per-class F1 (gold):  " + "  ".join(f"{lab:>7}" for lab in LABELS))
    for name, res in b["models"].items():
        print(f"  {name:20s} " + "  ".join(f"{res['per_class'][lab]['f1']:7.3f}" for lab in LABELS))
    print("\n  Accuracy by the auto label each gold line was sampled from:")
    for lab, d in b["accuracy_by_sampled_auto_label"].items():
        print(f"    {lab:8s} n={d['n']:3d}  Rules {d['Rules_acc']:.3f}  XGBoost {d['XGBoost_acc']:.3f}")
    t = b["xgb_with_threshold"]
    print(f"\n  At threshold {args.threshold}: {t['would_go_to_claude_pct']}% of gold lines would go to Claude; "
          f"XGBoost acc on confident {t['accuracy_on_confident']}, on unsure {t['accuracy_on_unsure']}")
    print(f"\nSaved -> {out}/metrics.json, per_class.csv, confusion_matrix.png, confusion_matrix_test_auto.png")


if __name__ == "__main__":
    main()
