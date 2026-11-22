"""Ethics head v6 = v5_clean + outdoor/real-world scene hard negatives.

Masla: v5_clean naye outdoor scene photos (highway, CCTV jaisi sadak, airfield,
parking, classroom...) mein se 10.6% ko 'weapons_violence' keh deta tha (threshold
0.6), kyunke weapons data zyada tar aisi hi asli duniya ki photos hai.
Hal: Places365 ki 37 aam scenes se 25 images per scene 'safe' class mein.

Sweep (6 seeds, scenes per class 0/10/25/50/70, threshold 0.4/0.5/0.55/0.6):
  25/scene + threshold 0.5 -> weapons recall v5 jitna (98.2% vs 98.1%), aur
  scene par galat alarm 10.6% -> 0.3%. Is liye backend HEAD_HIGH 0.6 -> 0.5.

Output:
  brain/ml/results/ethics_v6_metrics.csv   (6-seed evaluation)
  brain/ml/models/ethics_head_v6.joblib    (saare saaf data par final model)
Defense tables: python brain/ml/evaluate_ethics.py

Repo root se: python brain/ml/train_ethics_v6.py
"""
import os, joblib
import pandas as pd
from sklearn.metrics import accuracy_score

from ethics_split import (SEEDS, final_training_set, fit_head, load_clean_data,
                          p_unsafe, seed_split)

SCENES_PER_CLASS = 25
HIGH, LOW = 0.5, 0.4   # backend thresholds (image_ethics.HEAD_HIGH / HEAD_LOW)

d = load_clean_data()
if not len(d["scn_tr"]):
    raise SystemExit("Scene embeddings nahi mile. Pehle extract_scene_embeddings.py chalao.")

rows = []
for seed in SEEDS:
    Xtr, ytr, Xte, yte, photo = seed_split(d, seed, scenes_per_class=SCENES_PER_CLASS)
    clf = fit_head(Xtr, ytr)
    p, unsafe, pred = p_unsafe(clf, Xte), yte != "safe", clf.predict(Xte)
    rows.append(dict(
        seed=seed, n_test=len(yte),
        acc=accuracy_score(yte, pred),
        recall=(p[unsafe] >= HIGH).mean(),
        false_alarm=(p[~unsafe] >= HIGH).mean(),
        report_photo_fa=(p[photo] >= HIGH).mean(),
        medical_fa=(p_unsafe(clf, d["med_te"]) >= HIGH).mean(),
        scene_fa=(p_unsafe(clf, d["scn_te"]) >= HIGH).mean(),
        borderline=((p >= LOW) & (p < HIGH)).mean()))

df = pd.DataFrame(rows).round(4)
print(df.to_string(index=False))
print("\nMean:\n", df.drop(columns="seed").mean().round(4).to_string())
print("\nStd:\n", df.drop(columns="seed").std().round(4).to_string())
os.makedirs("brain/ml/results", exist_ok=True)
df.to_csv("brain/ml/results/ethics_v6_metrics.csv", index=False)

Xall, yall = final_training_set(d, scenes_per_class=SCENES_PER_CLASS)
final = fit_head(Xall, yall)
os.makedirs("brain/ml/models", exist_ok=True)
joblib.dump(final, "brain/ml/models/ethics_head_v6.joblib")
print("\nSaved: brain/ml/models/ethics_head_v6.joblib | classes:", list(final.classes_))
