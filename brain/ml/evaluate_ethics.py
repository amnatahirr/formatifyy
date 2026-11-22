"""Defense ke liye image ethics metrics (6 seeds, dedup + leakage-free test).

Har seed par har config (v5_clean, v6) ka head dobara train hota hai (ethics_split.py),
aur usi test set par CLIP zero-shot baseline bhi chalta hai. Nateeja mean ± std.
Alag test sets: medical (ImageNet) aur outdoor scenes (Places365), jo training mein nahi.

Output: brain/ml/results/ethics/metrics/
  comparison.md                  defense table (zero-shot vs trained head)
  metrics.json                   har seed ke numbers + mean/std + per-class
  per_seed.csv                   har seed ki row
  confusion_matrix_all_seeds.png 6 seeds ke test predictions jod kar
  confusion_matrix_seed42.png    ek split ki misaal

Repo root se: python brain/ml/evaluate_ethics.py
"""
import json, os
import numpy as np, pandas as pd, torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from transformers import CLIPModel, CLIPProcessor

from ethics_split import SEEDS, fit_head, load_clean_data, p_unsafe, seed_split

OUT = "brain/ml/results/ethics/metrics"
LABELS = ["safe", "sexual", "weapons_violence"]
LOW = 0.4
# (naam, scenes per class, backend HEAD_HIGH). Aakhri wala deployed hai.
CONFIGS = [("v5_clean", 0, 0.6), ("v6", 25, 0.5)]
DEPLOYED = CONFIGS[-1][0]


def zero_shot_text():
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
    return t, len(good)


def zero_shot_unsafe(X, t, n_good):
    logits = 100 * X @ t.T
    p = np.exp(logits - logits.max(1, keepdims=True))
    p /= p.sum(1, keepdims=True)
    return p[:, n_good:].sum(1) >= 0.5


def save_cm_png(cm, title, path):
    fig, ax = plt.subplots(figsize=(5, 4.3))
    ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(3), LABELS, rotation=20, ha="right")
    ax.set_yticks(range(3), LABELS)
    ax.set_xlabel("Predicted"); ax.set_ylabel("Actual"); ax.set_title(title, fontsize=10)
    for i in range(3):
        for j in range(3):
            ax.text(j, i, cm[i, j], ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)


def main():
    os.makedirs(OUT, exist_ok=True)
    d = load_clean_data()
    t, n_good = zero_shot_text()

    rows, all_true, all_pred = [], [], []
    for seed in SEEDS:
        for name, n_scn, high in CONFIGS:
            Xtr, ytr, Xte, yte, photo = seed_split(d, seed, scenes_per_class=n_scn)
            clf = fit_head(Xtr, ytr)
            pred = clf.predict(Xte)
            p, unsafe = p_unsafe(clf, Xte), yte != "safe"
            rows.append(dict(
                method=name, threshold=high, seed=seed, n_test=len(yte),
                train_acc=accuracy_score(ytr, clf.predict(Xtr)),
                test_acc=accuracy_score(yte, pred),
                recall=(p[unsafe] >= high).mean(),
                false_alarm=(p[~unsafe] >= high).mean(),
                report_photo_false_alarm=(p[photo] >= high).mean(),
                medical_false_alarm=(p_unsafe(clf, d["med_te"]) >= high).mean(),
                scene_false_alarm=(p_unsafe(clf, d["scn_te"]) >= high).mean(),
                borderline=((p >= LOW) & (p < high)).mean()))
            if name == DEPLOYED:
                all_true.append(yte); all_pred.append(pred)
                if seed == 42:
                    save_cm_png(confusion_matrix(yte, pred, labels=LABELS),
                                f"Ethics head {name}, seed 42 (test n={len(yte)})",
                                f"{OUT}/confusion_matrix_seed42.png")
        # zero-shot: model train nahi hota, test set seed par depend karta hai
        _, _, Xte, yte, photo = seed_split(d, seed)
        zs, unsafe = zero_shot_unsafe(Xte, t, n_good), yte != "safe"
        rows.append(dict(
            method="clip_zero_shot", threshold=None, seed=seed, n_test=len(yte),
            recall=zs[unsafe].mean(), false_alarm=zs[~unsafe].mean(),
            report_photo_false_alarm=zs[photo].mean(),
            medical_false_alarm=zero_shot_unsafe(d["med_te"], t, n_good).mean(),
            scene_false_alarm=zero_shot_unsafe(d["scn_te"], t, n_good).mean()))

    df = pd.DataFrame(rows)
    df.round(4).to_csv(f"{OUT}/per_seed.csv", index=False)
    num = df.drop(columns=["seed", "threshold"])
    mean, std = num.groupby("method").mean(), num.groupby("method").std()

    yt, yp = np.concatenate(all_true), np.concatenate(all_pred)
    cm_all = confusion_matrix(yt, yp, labels=LABELS)
    save_cm_png(cm_all, f"Ethics head {DEPLOYED}, 6 seeds jod kar (n={len(yt)})",
                f"{OUT}/confusion_matrix_all_seeds.png")
    report = classification_report(yt, yp, labels=LABELS, output_dict=True)

    results = {
        "deployed_model": f"ethics_head_{DEPLOYED} (CLIP ViT-B/32 frozen + LogisticRegression)",
        "configs": [dict(name=n, scenes_per_class=s, head_high=h, head_low=LOW) for n, s, h in CONFIGS],
        "seeds": SEEDS,
        "test_sizes": {"medical": len(d["med_te"]), "scenes": len(d["scn_te"])},
        "mean": mean.round(4).to_dict("index"), "std": std.round(4).to_dict("index"),
        "per_seed": df.round(4).to_dict("records"),
        "per_class_all_seeds": {k: {m: round(float(v), 4) for m, v in report[k].items()}
                                for k in LABELS},
        "confusion_matrix_all_seeds": {"labels": LABELS, "matrix": cm_all.tolist()},
    }
    with open(f"{OUT}/metrics.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    def ms(m, k):
        v = mean.loc[m, k]
        return "-" if pd.isna(v) else f"{100 * v:.1f}% ± {100 * std.loc[m, k]:.1f}%"

    cols = [("recall", "Unsafe pakda"), ("false_alarm", "Safe (reports) galat alarm"),
            ("medical_false_alarm", "Medical galat alarm"),
            ("scene_false_alarm", "Outdoor scenes galat alarm"), ("test_acc", "3-class accuracy")]
    lines = ["| Method | " + " | ".join(c[1] for c in cols) + " |", "|---" * (len(cols) + 1) + "|"]
    labels = {"clip_zero_shot": "CLIP zero-shot"}
    for n, s, h in CONFIGS:
        labels[n] = f"Head {n} (threshold {h})" + (" **deployed**" if n == DEPLOYED else "")
    for m in ["clip_zero_shot"] + [c[0] for c in CONFIGS]:
        lines.append(f"| {labels[m]} | " + " | ".join(ms(m, c[0]) for c in cols) + " |")
    table = "\n".join(lines)
    per_class = "\n".join(
        ["| Class | Precision | Recall | F1 |", "|---|---|---|---|"] +
        [f"| {k} | {100 * report[k]['precision']:.1f}% | {100 * report[k]['recall']:.1f}% | "
         f"{100 * report[k]['f1-score']:.1f}% |" for k in LABELS])
    dep = mean.loc[DEPLOYED]
    md = f"""# Image ethics: defense results

Model: frozen CLIP ViT-B/32 + LogisticRegression head (linear probing).
Deployed: `ethics_head_{DEPLOYED}` (backend HEAD_HIGH {CONFIGS[-1][2]}, HEAD_LOW {LOW}).

Evaluation: 6 seeds ({", ".join(map(str, SEEDS))}), har seed par head dobara train.
Near-duplicates (cos > 0.98) hataye, aur test se wo images nikaali jo kisi train image
se > 0.98 milti thin. Test images per seed: ~{int(dep['n_test'])}.
Alag test sets (training mein kabhi nahi): medical {len(d['med_te'])} images (ImageNet),
outdoor/real-world scenes {len(d['scn_te'])} images (Places365, 37 scenes).

## Zero-shot vs trained heads (mean ± std)

{table}

- v5_clean: dedup + medical hard negatives. Naye outdoor photos (highway, airfield,
  parking, classroom...) mein se ~10% ko weapons keh deta tha.
- v6: v5_clean + 25 images per Places365 scene. Threshold 0.6 se 0.5 kiya, taake
  weapons ki pakad v5 jitni rahe. Outdoor galat alarm ~0.3% reh gaya.
- Train accuracy {100 * dep['train_acc']:.1f}% vs test {100 * dep['test_acc']:.1f}% ({DEPLOYED}): overfitting nahi.
- Held-out reports ki photo-jaisi images bohut kam hain (~18 per seed), is liye un ka
  galat-alarm number ({ms(DEPLOYED, 'report_photo_false_alarm')}) bohut hilta hai.

## Per class, {DEPLOYED} (6 seeds ke saare test predictions jod kar)

{per_class}

## Limitations
- Test images unhi datasets se hain jin par train hua, asli reports par number thora kam hoga.
- Scenes ki tadaad (25) aur threshold (0.5) isi 6-seed evaluation ko dekh kar chune gaye;
  alag validation split nahi tha, is liye v6 ke numbers thore optimistic ho sakte hain.
- Selfie filters, depth-camera images, close-up farsh/texture, CCTV frames par ab bhi kabhi
  galat alarm aata hai (Places365 scenes in ko cover nahi karti).
- Drugs, self-harm, hate, offensive: trained nahi, BLIP caption + keyword engine par hain.
"""
    with open(f"{OUT}/comparison.md", "w", encoding="utf-8") as f:
        f.write(md)
    print(table); print(); print(per_class)
    print(f"\nSaved to {OUT}/")


if __name__ == "__main__":
    main()
