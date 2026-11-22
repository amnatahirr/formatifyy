"""Image ethics: saare versions ka comparison (defense documentation ke liye).

Do hisse:
  A. Fair comparison: har version ka tareeqa (recipe) 6 seeds par dobara train,
     sab ek hi saaf test set par (dedup + leakage-free), aur alag medical aur
     outdoor-scene test sets par. Is se pata chalta hai ke har qadam ne kya diya.
  B. Asli misaalein: saved model files (v2, v3, v4, v5, v6) ek document ki images
     par (ye images kisi version ki training mein nahi thin).

Version history ke purane numbers (jo us waqt report hue) results/ ki CSVs se
parhe jaate hain.

Output: brain/ml/results/ethics/metrics/version_comparison.md (+ .csv)

Repo root se:
  python brain/ml/compare_ethics_versions.py [document.docx] [extra_image.png ...]
"""
import io, os, sys, zipfile
import numpy as np, pandas as pd, joblib
from sklearn.metrics import accuracy_score

from ethics_split import SEEDS, fit_head, load_clean_data, p_unsafe, seed_split
from evaluate_ethics import zero_shot_text, zero_shot_unsafe

OUT = "brain/ml/results/ethics/metrics"
R = "brain/ml/results"

# (row label, scenes_per_class, use_medical, threshold, versions jinka ye tareeqa hai)
RECIPES = [
    ("Head only (no hard negatives)", 0, False, 0.6, "v2, v4"),
    ("+ medical hard negatives", 0, True, 0.6, "v3, v5_clean"),
    ("+ outdoor scenes (threshold 0.6)", 25, True, 0.6, "-"),
    ("+ outdoor scenes (threshold 0.5)", 25, True, 0.5, "v6 (deployed)"),
]


def fair_comparison(d):
    t, n_good = zero_shot_text()
    rows = []
    for seed in SEEDS:
        for name, n_scn, med, thr, vers in RECIPES:
            Xtr, ytr, Xte, yte, _ = seed_split(d, seed, scenes_per_class=n_scn, medical=med)
            clf = fit_head(Xtr, ytr)
            p, unsafe = p_unsafe(clf, Xte), yte != "safe"
            rows.append(dict(method=name, versions=vers, threshold=thr, seed=seed, n_test=len(yte),
                             accuracy=accuracy_score(yte, clf.predict(Xte)),
                             recall=(p[unsafe] >= thr).mean(),
                             safe_fa=(p[~unsafe] >= thr).mean(),
                             medical_fa=(p_unsafe(clf, d["med_te"]) >= thr).mean(),
                             scene_fa=(p_unsafe(clf, d["scn_te"]) >= thr).mean()))
        _, _, Xte, yte, _ = seed_split(d, seed)
        zs, unsafe = zero_shot_unsafe(Xte, t, n_good), yte != "safe"
        rows.append(dict(method="CLIP zero-shot (no training)", versions="baseline", n_test=len(yte),
                         threshold=None, seed=seed, accuracy=np.nan,
                         recall=zs[unsafe].mean(), safe_fa=zs[~unsafe].mean(),
                         medical_fa=zero_shot_unsafe(d["med_te"], t, n_good).mean(),
                         scene_fa=zero_shot_unsafe(d["scn_te"], t, n_good).mean()))
    return pd.DataFrame(rows)


def history_table():
    def mstd(path, col):
        if not os.path.exists(path):
            return "-"
        s = pd.read_csv(path)[col]
        return f"{100 * s.mean():.1f}% ± {100 * s.std():.1f}%"
    return "\n".join([
        "| Version | Kya badla | Us waqt ka number | Baad mein kya pata chala |",
        "|---|---|---|---|",
        "| v1 | Pehla head: 4 classes (safe, sexual, weapons, violence) | Sirf 1 split (seed 42) | "
        "Weapons aur violence aapas mein mix ho rahe the, isliye v2 mein merge kiye |",
        "| v2 | 3 classes (weapons + violence = weapons_violence) | Seed 42: accuracy 99.1%, "
        "unsafe recall 99.8%, galat alarm 0.4% | 6 splits par accuracy "
        f"{mstd(f'{R}/ethics_stability.csv', 'test_acc')}, galat alarm "
        f"{mstd(f'{R}/ethics_stability.csv', 'false_alarm')}. 18,036 report images mein se "
        "13,663 duplicates thin (ek report CS03 ki 918 mein se sirf 43 alag), seed 42 lucky tha |",
        "| v3 | v2 + medical hard negatives (syringe, stethoscope, lab coat, oxygen mask) | "
        "Seed 42: accuracy 98.9%, medical galat alarm 21.9% se 2.3% | Duplicates abhi bhi the, "
        "number optimistic tha |",
        "| v4 (dedup) | v2 + duplicates hataye + test se leakage hataya | 6 splits: accuracy "
        f"{mstd(f'{R}/ethics_final_metrics.csv', 'test_acc')}, galat alarm "
        f"{mstd(f'{R}/ethics_final_metrics.csv', 'false_alarm')} (threshold 0.4) | "
        "Pehla imandar number. Medical images par phir bhi galat alarm |",
        "| v5_clean | v4 + medical hard negatives (100 per class) | 6 splits: accuracy "
        f"{mstd(f'{R}/ethics_v5_clean_metrics.csv', 'acc')}, recall "
        f"{mstd(f'{R}/ethics_v5_clean_metrics.csv', 'recall_06')} (threshold 0.6) | "
        "Naye outdoor photos (sadak, airfield, CCTV jaisi) mein se ~10% ko weapons kehta tha |",
        "| **v6** | v5 + 25 photos per Places365 scene (37 scenes), threshold 0.5 | 6 splits: "
        f"accuracy {mstd(f'{R}/ethics_v6_metrics.csv', 'acc')}, recall "
        f"{mstd(f'{R}/ethics_v6_metrics.csv', 'recall')} | **Deployed.** Outdoor galat alarm ~0.3% |",
    ])


def case_studies(docx, extra):
    import base64
    sys.path.insert(0, "backend")
    from PIL import Image
    from functions.ethics_head import clip_embedding_512
    from functions.image_ethics import analyze_image_ethics_sync
    models = {v: f"brain/ml/models/ethics_head_{v}.joblib"
              for v in ("v2", "v3", "v4_dedup", "v5_clean", "v6")}
    models = {v: joblib.load(p) for v, p in models.items() if os.path.exists(p)}
    raw = []  # (label, bytes)
    if docx and os.path.exists(docx):
        z = zipfile.ZipFile(docx)
        raw += [(CASE_LABELS.get(n.split("/")[-1], n.split("/")[-1]), z.read(n))
                for n in sorted(z.namelist()) if n.startswith("word/media/")]
    for arg in extra:  # "path" ya "path=label"
        path, _, label = arg.partition("=")
        raw.append((label or os.path.basename(path), open(path, "rb").read()))
    rows = []
    for label, data in raw:
        e = clip_embedding_512(Image.open(io.BytesIO(data)).convert("RGB"))
        row = {"image": label}
        for v, clf in models.items():
            row[v] = round(float(p_unsafe(clf, e)[0]), 2)
        r = analyze_image_ethics_sync(base64.b64encode(data).decode())
        row["App ka faisla (v6 + keyword)"] = (
            "Safe" if r["ethical"] else f"Unethical: {r['category']} ({r.get('engine', '')})")
        rows.append(row)
    return pd.DataFrame(rows)


# Test document (FORMATIFY PROPOSAL.docx) ki images ke naam
CASE_LABELS = {
    "image1.jpeg": "University logo", "image2.jpeg": "Handgun (weapon)",
    "image3.jpeg": "Sharaab + pills (drugs)", "image4.png": "Flow diagram",
    "image5.jpeg": "Blood draw (medical)", "image6.png": "Graph",
    "image7.png": "Email app screenshot", "image8.png": "Text page screenshot",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    d = load_clean_data()
    df = fair_comparison(d)
    df.round(4).to_csv(f"{OUT}/version_comparison.csv", index=False)
    g = df.drop(columns=["seed", "threshold", "versions"]).groupby("method", sort=False)
    mean, std = g.mean(), g.std()
    vers = df.groupby("method", sort=False)["versions"].first()

    def ms(m, k):
        v = mean.loc[m, k]
        return "-" if pd.isna(v) else f"{100 * v:.1f}% ± {100 * std.loc[m, k]:.1f}%"

    order = ["CLIP zero-shot (no training)"] + [r[0] for r in RECIPES]
    fair = "\n".join(
        ["| Tareeqa | Versions | Unsafe pakda | Safe reports par galat alarm | "
         "Medical par galat alarm | Outdoor photos par galat alarm | 3-class accuracy |",
         "|---|---|---|---|---|---|---|"] +
        [f"| {m} | {vers[m]} | {ms(m, 'recall')} | {ms(m, 'safe_fa')} | {ms(m, 'medical_fa')} | "
         f"{ms(m, 'scene_fa')} | {ms(m, 'accuracy')} |" for m in order])

    docx = sys.argv[1] if len(sys.argv) > 1 else None
    cases = case_studies(docx, sys.argv[2:]) if (docx or len(sys.argv) > 2) else pd.DataFrame()
    case_md = ""
    if len(cases):
        cols = [c for c in cases.columns if c != "image"]
        case_md = "\n".join(
            ["| Image | " + " | ".join(cols) + " |", "|---" * (len(cols) + 1) + "|"] +
            ["| " + " | ".join(str(r[c]) for c in ["image"] + cols) + " |"
             for _, r in cases.iterrows()])

    md = f"""# Image ethics: saare versions ka comparison

Model har version mein ek hi qisam ka hai: frozen CLIP ViT-B/32 image embedding (512 numbers)
ke upar Logistic Regression head (transfer learning / linear probing). Versions mein sirf
**training data** aur **evaluation ka tareeqa** badla.

## 1. Version history (har qadam par kya badla aur kyun)

{history_table()}

## 2. Fair comparison: sab ek hi test set par

Har tareeqa 6 alag splits (seeds {", ".join(map(str, SEEDS))}) par dobara train hua, aur sab
ka test bilkul ek jaisa hai: duplicates hata kar, aur test se wo images nikaal kar jo kisi
train image se milti hon (~{int(mean.loc[RECIPES[0][0], 'n_test'])} images per split).
Saath mein do alag test sets jo kisi training mein nahi gaye: medical {len(d['med_te'])} images
(ImageNet) aur outdoor/real-world scenes {len(d['scn_te'])} images (Places365, 37 scenes).
Har row pichli row mein **sirf ek cheez** jodti hai. Numbers: mean ± std.

{fair}

Is table ko kaise parhein:
- **Zero-shot se trained head:** bina training CLIP medical aur outdoor photos ke bade hisse ko
  unsafe keh deta hai. Hamare data par train kiya head ye galtiyan bohut kam kar deta hai.
- **+ medical:** medical photos (injection, stethoscope) par galat alarm bohut kam hota hai.
- **+ outdoor scenes:** sadak, airfield, classroom jaisi photos par galat alarm ~0.3% reh jaata hai.
  Threshold 0.6 par weapons ki pakad thori girti hai, is liye 0.5 rakha (v6), jahan pakad pehle
  jitni hai.
- v2/v4 aur v3/v5 ka farq sirf duplicates ka tha. Saaf test par dono ka tareeqa ek hi row hai.
  Purane versions ke **zyada numbers** (99%+) duplicates aur lucky split ki wajah se the (table 1).
"""
    if case_md:
        md += f"""
## 3. Asli misaalein (saved model files, p_unsafe)

p_unsafe = model ke hisaab se image ke unsafe hone ka imkaan (0 se 1). v6 ke liye 0.5 se upar
flag hota hai (purane versions mein 0.6). Ye images kisi version ki training mein nahi thin.

{case_md}

- **Blood draw:** bina medical data wale v2 aur v4 is jaiz medical photo ko borderline ya 0.6 se upar le jaate
  the, yaani galti se unethical. Medical hard negatives ke baad (v3, v5, v6) ye saaf Safe hai.
- **Drugs:** head drugs par train nahi hua (data nahi tha), is liye uska number neeche hai.
  App phir bhi isse pakadta hai, kyunke keyword engine BLIP caption ("alcohol with pills") se
  Drugs category nikaalta hai.
- **Handgun:** har version 0.99 se upar, yaani asli unsafe image har version mein pakdi gayi.
"""
    md += """
## Note
- v1 ki model file save nahi thi, is liye wo sirf history table mein hai.
- Purane keyword engine (BLIP caption + keywords) ka number is table mein nahi, kyunke sexual aur
  weapons ki raw images delete ki ja chuki hain (sirf embeddings rakhi), aur caption ke liye raw
  image chahiye.
"""
    with open(f"{OUT}/version_comparison.md", "w", encoding="utf-8") as f:
        f.write(md)
    print(md)


if __name__ == "__main__":
    main()
