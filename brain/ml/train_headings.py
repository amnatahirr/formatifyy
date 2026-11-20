"""
train_headings.py  -  Task 1, Step 2: train the local heading model (XGBoost).

What it does, in order:
  1. Loads auto labels + split from data/labels/headings_auto.jsonl and the raw
     blocks (text, font_size, bold, style) from data/parsed/*.jsonl.
  2. Builds features with backend/functions/heading_local.block_features()
     (the SAME function the live app uses).
  3. Trains on the TRAIN split only. Picks settings (tree depth, class-weight
     scheme) by macro-F1 on the VAL split. The test split is not used here.
  4. Prints and saves a VAL table: threshold -> % sent to Claude -> accuracy on the rest.
  5. Saves models/headings_xgb.json and models/headings_xgb_meta.json.

The gold sheet (data/labels/to_review.csv) is NEVER opened here.

Run (inside brain/ml):
    ../../.venv/bin/python train_headings.py
"""
import argparse
import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, f1_score
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "backend"))
from functions.heading_local import FEATURES, LABELS, block_features, body_font_size  # noqa: E402

THRESHOLDS = [0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 0.99]


def load_dataset(labels_path: Path, parsed_dir: Path):
    """Return {split: (X, y, rows)} for rows whose auto label is one of LABELS."""
    raw = {}           # (report, idx) -> raw block
    body_of = {}       # report -> body font size
    for f in sorted(parsed_dir.glob("*.jsonl")):
        rows = [json.loads(l) for l in open(f, encoding="utf-8")]
        body_of[f.stem] = body_font_size((r["text"], r.get("font_size")) for r in rows)
        for r in rows:
            raw[(f.stem, r["idx"])] = r

    data = defaultdict(lambda: ([], [], []))
    skipped = Counter()
    for line in open(labels_path, encoding="utf-8"):
        rec = json.loads(line)
        lab = rec["auto_label"]
        if lab not in LABELS:                    # Noise / TOC / Front / Unsure are not trained on
            skipped[lab] += 1
            continue
        r = raw[(rec["report"], rec["idx"])]
        X, y, meta = data[rec["split"]]
        X.append(block_features(r["text"], r.get("font_size"), r.get("bold"), r.get("style"), body_of[rec["report"]]))
        y.append(LABELS.index(lab))
        meta.append({"report": rec["report"], "group": rec["group"]})
    out = {s: (np.asarray(X, dtype=float), np.asarray(y), m) for s, (X, y, m) in data.items()}
    return out, skipped


def make_weights(y, scheme):
    """Class imbalance fix: rare classes (H1) get a bigger weight than Body.
    'balanced' = full inverse frequency, 'sqrt' = a softer version of it."""
    w = compute_sample_weight("balanced", y)
    return np.sqrt(w) if scheme == "sqrt" else w


def threshold_table(proba, y):
    conf = proba.max(axis=1)
    pred = proba.argmax(axis=1)
    table = []
    for t in THRESHOLDS:
        keep = conf >= t
        table.append({
            "threshold": t,
            "sent_to_claude_pct": round(100 * (1 - keep.mean()), 2),
            "kept_lines": int(keep.sum()),
            "accuracy_on_kept": round(float(accuracy_score(y[keep], pred[keep])), 4) if keep.any() else None,
            "macro_f1_on_kept": round(float(f1_score(y[keep], pred[keep], average="macro",
                                                     labels=range(len(LABELS)), zero_division=0)), 4) if keep.any() else None,
        })
    return table


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default=str(HERE / "data/labels/headings_auto.jsonl"))
    ap.add_argument("--parsed", default=str(HERE / "data/parsed"))
    ap.add_argument("--models", default=str(HERE / "models"))
    ap.add_argument("--results", default=str(HERE / "results/headings"))
    args = ap.parse_args()
    models_dir, results_dir = Path(args.models), Path(args.results)
    models_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    data, skipped = load_dataset(Path(args.labels), Path(args.parsed))
    (Xtr, ytr, mtr), (Xva, yva, mva) = data["train"], data["val"]
    print(f"Loaded in {time.time() - t0:.0f}s. Not trained on: {dict(skipped)}")
    for s in ("train", "val", "test"):
        c = Counter(LABELS[k] for k in data[s][1])
        print(f"  {s:5s} {len(data[s][1]):7d} rows  {dict(c)}")

    # Safety check: no project may be in two splits.
    gtr, gva, gte = ({m["group"] for m in data[s][2]} for s in ("train", "val", "test"))
    assert not (gtr & gva or gtr & gte or gva & gte), "Project leakage between splits!"
    print(f"  projects: train {len(gtr)} | val {len(gva)} | test {len(gte)} (no overlap)")

    # Small grid, chosen on VAL macro-F1.
    best = None
    for depth in (4, 6, 8):
        for scheme in ("balanced", "sqrt"):
            m = XGBClassifier(
                n_estimators=600, max_depth=depth, learning_rate=0.1,
                subsample=0.9, colsample_bytree=0.9, tree_method="hist",
                objective="multi:softprob", eval_metric="mlogloss",
                early_stopping_rounds=30, n_jobs=-1, random_state=42,
            )
            m.fit(Xtr, ytr, sample_weight=make_weights(ytr, scheme),
                  eval_set=[(Xva, yva)], verbose=False)
            pred = m.predict(Xva)
            f1 = f1_score(yva, pred, average="macro")
            acc = accuracy_score(yva, pred)
            print(f"  depth={depth} weights={scheme:8s} trees={m.best_iteration + 1:3d}  "
                  f"val macro-F1={f1:.4f}  acc={acc:.4f}")
            if best is None or f1 > best[0]:
                best = (f1, acc, depth, scheme, m)

    f1, acc, depth, scheme, model = best
    print(f"\nChosen: depth={depth}, weights={scheme}  (val macro-F1 {f1:.4f}, acc {acc:.4f})")

    model.save_model(str(models_dir / "headings_xgb.json"))
    importance = dict(sorted(zip(FEATURES, map(float, model.feature_importances_)), key=lambda kv: -kv[1]))
    meta = {
        "labels": LABELS, "features": FEATURES,
        "params": {"max_depth": depth, "weights": scheme, "learning_rate": 0.1,
                   "n_estimators": int(model.best_iteration + 1)},
        "val": {"macro_f1": round(float(f1), 4), "accuracy": round(float(acc), 4)},
        "feature_importance": {k: round(v, 4) for k, v in importance.items()},
        "trained_on": "train split only, auto labels (noisy)",
    }
    (models_dir / "headings_xgb_meta.json").write_text(json.dumps(meta, indent=2))

    # Threshold table on VAL (to choose the fallback threshold).
    table = threshold_table(model.predict_proba(Xva), yva)
    with open(results_dir / "threshold_table_val.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    print("\nVAL threshold table (accuracy vs auto labels):")
    print(f"  {'threshold':>9} | {'% to Claude':>11} | {'acc on rest':>11} | {'macro-F1 rest':>13}")
    for r in table:
        print(f"  {r['threshold']:>9.2f} | {r['sent_to_claude_pct']:>10.2f}% | "
              f"{r['accuracy_on_kept']:>11.4f} | {r['macro_f1_on_kept']:>13.4f}")
    print("\nTop features:", ", ".join(f"{k} {v:.3f}" for k, v in list(importance.items())[:6]))
    print(f"\nSaved model -> {models_dir/'headings_xgb.json'}  ({time.time() - t0:.0f}s total)")


if __name__ == "__main__":
    main()
