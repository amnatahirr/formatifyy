"""
train_headings_v3.py  -  v3 heading model: TEXT and CONTEXT only.

Same labels as v2 (auto labels from formatting, 'Unsure' -> Body), but the model
never sees font size, bold or style. That simulates the real, flat input.

  - Context (previous / next line) is built per report in reading order,
    skipping Noise / TOC / Front lines (page numbers, footers, table of
    contents, title page). Word files in the app have none of these between
    paragraphs, so the context then looks like the app's context.
  - Train on train split, choose depth + class-weight scheme on val.
  - Gold sheet is NEVER opened here.

Run (inside brain/ml, venv active, DYLD_FALLBACK_LIBRARY_PATH set):
    python train_headings_v3.py
"""
import argparse
import csv
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, f1_score
from xgboost import XGBClassifier

from train_headings import HERE, make_weights, threshold_table  # also adds backend/ to sys.path
from functions.heading_local import LABELS  # noqa: E402
from functions.heading_text import FEATURES_V3, text_context_features  # noqa: E402

SKIP_IN_CONTEXT = {"Noise", "TOC", "Front"}


def load_sequences(labels_path: Path, parsed_dir: Path):
    """{report: {"split", "group", "rows": [(idx, text, label)]}} in reading order, skipped lines removed."""
    text_of = {}
    for f in sorted(parsed_dir.glob("*.jsonl")):
        for l in open(f, encoding="utf-8"):
            r = json.loads(l)
            text_of[(f.stem, r["idx"])] = r["text"]
    reports = defaultdict(lambda: {"rows": []})
    for line in open(labels_path, encoding="utf-8"):
        rec = json.loads(line)
        if rec["auto_label"] in SKIP_IN_CONTEXT:
            continue
        lab = "Body" if rec["auto_label"] == "Unsure" else rec["auto_label"]
        rep = reports[rec["report"]]
        rep["split"], rep["group"] = rec["split"], rec["group"]
        rep["rows"].append((rec["idx"], text_of[(rec["report"], rec["idx"])], lab))
    for rep in reports.values():
        rep["rows"].sort()
    return reports


def build_xy(reports, split):
    X, y = [], []
    for rep in reports.values():
        if rep["split"] != split or not rep["rows"]:
            continue
        X += text_context_features([t for _, t, _ in rep["rows"]])
        y += [LABELS.index(lab) for _, _, lab in rep["rows"]]
    return np.asarray(X, dtype=float), np.asarray(y)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default=str(HERE / "data/labels/headings_auto.jsonl"))
    ap.add_argument("--parsed", default=str(HERE / "data/parsed"))
    ap.add_argument("--models", default=str(HERE / "models"))
    ap.add_argument("--results", default=str(HERE / "results/headings_v3"))
    args = ap.parse_args()
    models_dir, results_dir = Path(args.models), Path(args.results)
    models_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    reports = load_sequences(Path(args.labels), Path(args.parsed))
    (Xtr, ytr), (Xva, yva) = build_xy(reports, "train"), build_xy(reports, "val")
    print(f"Loaded in {time.time() - t0:.0f}s, {len(FEATURES_V3)} text+context features")
    for s, y in (("train", ytr), ("val", yva)):
        print(f"  {s:5s} {len(y):7d} rows  {dict(Counter(LABELS[k] for k in y))}")
    groups = {s: {r['group'] for r in reports.values() if r['split'] == s} for s in ("train", "val", "test")}
    assert not (groups["train"] & groups["val"] or groups["train"] & groups["test"] or groups["val"] & groups["test"])

    best = None
    for depth in (4, 6, 8):
        for scheme in ("balanced", "sqrt"):
            m = XGBClassifier(
                n_estimators=800, max_depth=depth, learning_rate=0.1,
                subsample=0.9, colsample_bytree=0.9, tree_method="hist",
                objective="multi:softprob", eval_metric="mlogloss",
                early_stopping_rounds=30, n_jobs=-1, random_state=42,
            )
            m.fit(Xtr, ytr, sample_weight=make_weights(ytr, scheme), eval_set=[(Xva, yva)], verbose=False)
            pred = m.predict(Xva)
            f1, acc = f1_score(yva, pred, average="macro"), accuracy_score(yva, pred)
            print(f"  depth={depth} weights={scheme:8s} trees={m.best_iteration + 1:3d}  val macro-F1={f1:.4f}  acc={acc:.4f}")
            if best is None or f1 > best[0]:
                best = (f1, acc, depth, scheme, m)

    f1, acc, depth, scheme, model = best
    print(f"\nChosen: depth={depth}, weights={scheme}  (val macro-F1 {f1:.4f}, acc {acc:.4f})")
    pred = model.predict(Xva)
    per = f1_score(yva, pred, average=None, labels=range(len(LABELS)))
    print("  val per-class F1:", {lab: round(float(v), 3) for lab, v in zip(LABELS, per)})

    model.save_model(str(models_dir / "headings_xgb_v3.json"))
    imp = dict(sorted(zip(FEATURES_V3, map(float, model.feature_importances_)), key=lambda kv: -kv[1]))
    (models_dir / "headings_xgb_v3_meta.json").write_text(json.dumps({
        "labels": LABELS, "features": FEATURES_V3,
        "params": {"max_depth": depth, "weights": scheme, "n_estimators": int(model.best_iteration + 1)},
        "val": {"macro_f1": round(float(f1), 4), "accuracy": round(float(acc), 4),
                "per_class_f1": {lab: round(float(v), 4) for lab, v in zip(LABELS, per)}},
        "feature_importance": {k: round(v, 4) for k, v in imp.items()},
        "trained_on": "train split, auto labels ('Unsure' -> Body), text+context features only",
    }, indent=2))

    table = threshold_table(model.predict_proba(Xva), yva)
    with open(results_dir / "threshold_table_val.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    print("\nVAL threshold table (vs auto labels):")
    for r in table:
        print(f"  {r['threshold']:.2f} | {r['sent_to_claude_pct']:6.2f}% to Claude | acc rest {r['accuracy_on_kept']:.4f} "
              f"| macro-F1 rest {r['macro_f1_on_kept']:.4f}")
    print("\nTop features:", ", ".join(f"{k} {v:.3f}" for k, v in list(imp.items())[:8]))
    print(f"Saved {models_dir/'headings_xgb_v3.json'} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
