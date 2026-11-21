"""Ethics head ke metrics nikaal kar results/ethics/metrics/ mein save karta hai.

    python brain/ml/evaluate_ethics.py                     # sirf v2
    python brain/ml/evaluate_ethics.py v2 v3               # dono, same test set par

Har model ke liye: classification report, confusion matrix (csv + png),
threshold table, aur CLIP zero-shot baseline. Agar medical test images
maujood hon to unka galat-alarm rate alag se.
"""
import json, os, sys
import numpy as np, pandas as pd, joblib, torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score)
from transformers import CLIPModel, CLIPProcessor

from ethics_split import load_split

OUT = "brain/ml/results/ethics/metrics"
THRESHOLDS = (0.3, 0.4, 0.5, 0.6, 0.7)
DEPLOY_T = 0.6


def zero_shot_unsafe(X):
    good = ["a screenshot of a software application", "a diagram or flowchart",
            "a chart or graph", "a table of data", "a normal photo of people",
            "a normal photograph for a university report"]
    bad = ["a nude or sexually explicit image", "a violent or gory image",
           "a photo of a weapon", "a photo of a gun or a knife"]
    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").eval()
    proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    with torch.no_grad():
        t = model.get_text_features(**proc(text=good + bad, return_tensors="pt", padding=True))
        if not torch.is_tensor(t):
            t = t.pooler_output
        if t.shape[-1] != 512:
            t = model.text_projection(t)
        t = (t / t.norm(dim=-1, keepdim=True)).numpy()
    logits = 100 * X @ t.T
    p = np.exp(logits - logits.max(1, keepdims=True))
    p /= p.sum(1, keepdims=True)
    return p[:, len(good):].sum(1) >= 0.5


def save_cm_png(cm, labels, title, path):
    fig, ax = plt.subplots(figsize=(4.8, 4.2))
    ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(labels)), labels, rotation=30, ha="right")
    ax.set_yticks(range(len(labels)), labels)
    ax.set_xlabel("Predicted"); ax.set_ylabel("Actual"); ax.set_title(title)
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, cm[i, j], ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)


def evaluate(name, s):
    clf = joblib.load(f"brain/ml/models/ethics_head_{name}.joblib")
    Xte, yte, Xmed = s["Xte"], s["yte"], s["Xmed_te"]
    labels = list(clf.classes_)
    pred = clf.predict(Xte)
    cm = confusion_matrix(yte, pred, labels=labels)
    unsafe = yte != "safe"
    p = 1 - clf.predict_proba(Xte)[:, labels.index("safe")]

    m = {
        "model": f"ethics_head_{name}",
        "test_size": int(len(yte)),
        "test_counts": {k: int(v) for k, v in zip(*np.unique(yte, return_counts=True))},
        "accuracy_3class": round(float(accuracy_score(yte, pred)), 4),
        "macro_f1": round(float(f1_score(yte, pred, average="macro")), 4),
        "per_class": {k: {kk: round(float(vv), 4) for kk, vv in v.items()}
                      for k, v in classification_report(yte, pred, output_dict=True).items()
                      if k in labels},
        "confusion_matrix": {"labels": labels, "matrix": cm.tolist()},
        "thresholds": [{"threshold": T,
                        "unsafe_recall": round(float((p >= T)[unsafe].mean()), 4),
                        "safe_false_alarm": round(float((p >= T)[~unsafe].mean()), 4)}
                       for T in THRESHOLDS],
        "borderline_0.4_0.6": round(float(((p >= 0.4) & (p < 0.6)).mean()), 4),
    }
    if len(Xmed):
        pm = 1 - clf.predict_proba(Xmed)[:, labels.index("safe")]
        m["medical_test"] = {
            "n": int(len(Xmed)),
            "false_alarm_at_0.6": round(float((pm >= DEPLOY_T).mean()), 4),
            "borderline_0.4_0.6": round(float(((pm >= 0.4) & (pm < 0.6)).mean()), 4),
            "mean_p_unsafe": round(float(pm.mean()), 4),
        }

    pd.DataFrame(cm, index=labels, columns=labels).to_csv(f"{OUT}/confusion_matrix_{name}.csv")
    save_cm_png(cm, labels, f"Ethics head {name} (test n={len(yte)})",
                f"{OUT}/confusion_matrix_{name}.png")
    return m


def main():
    os.makedirs(OUT, exist_ok=True)
    names = sys.argv[1:] or ["v2"]
    s = load_split(with_medical=True)
    results = {n: evaluate(n, s) for n in names}

    unsafe = s["yte"] != "safe"
    zs = zero_shot_unsafe(s["Xte"])
    zs_row = {"unsafe_recall": round(float(zs[unsafe].mean()), 4),
              "safe_false_alarm": round(float(zs[~unsafe].mean()), 4)}
    if len(s["Xmed_te"]):
        zs_row["medical_false_alarm"] = round(float(zero_shot_unsafe(s["Xmed_te"]).mean()), 4)
    results["clip_zero_shot"] = zs_row

    with open(f"{OUT}/metrics.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # defense ke liye ek chhoti markdown table
    lines = ["| Method | Unsafe pakda | Safe par galat alarm | Medical par galat alarm | 3-class accuracy |",
             "|---|---|---|---|---|"]
    pct = lambda v: f"{100 * v:.1f}%" if v is not None else "-"
    lines.append(f"| CLIP zero-shot | {pct(zs_row['unsafe_recall'])} | "
                 f"{pct(zs_row['safe_false_alarm'])} | {pct(zs_row.get('medical_false_alarm'))} | - |")
    for n in names:
        r = results[n]
        t = next(x for x in r["thresholds"] if x["threshold"] == DEPLOY_T)
        med = r.get("medical_test", {}).get("false_alarm_at_0.6")
        lines.append(f"| Head {n} (threshold {DEPLOY_T}) | {pct(t['unsafe_recall'])} | "
                     f"{pct(t['safe_false_alarm'])} | {pct(med)} | {pct(r['accuracy_3class'])} |")
    table = "\n".join(lines)
    with open(f"{OUT}/comparison.md", "w", encoding="utf-8") as f:
        f.write(f"# Image ethics: test set results\n\nTest set: {results[names[0]]['test_counts']}"
                f" (+ {len(s['Xmed_te'])} medical safe images)\n\n{table}\n")
    print(json.dumps(results, indent=2)); print(); print(table)
    print(f"\nSaved to {OUT}/")


if __name__ == "__main__":
    main()
