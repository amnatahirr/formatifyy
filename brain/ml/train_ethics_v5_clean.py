"""Ethics head v5_clean: backend mein yahi model chal raha hai.

Recipe (data/split ki tafseel ethics_split.py mein):
  frozen CLIP ViT-B/32 embeddings -> LogisticRegression (linear probing)
  dedup (cos > 0.98) + leakage-free test + medical hard negatives (100/class)

Ye script do kaam karti hai:
  1. 6 seeds par evaluation -> brain/ml/results/ethics_v5_clean_metrics.csv
  2. Saare saaf data par final model -> brain/ml/models/ethics_head_v5_clean.joblib
     (is final model par alag metrics nahi nikalte, kyunke usne test data bhi dekha hai)

Defense ki tables/tasveerein: python brain/ml/evaluate_ethics.py

Repo root se: python brain/ml/train_ethics_v5_clean.py
"""
import os, joblib
import pandas as pd
from sklearn.metrics import accuracy_score

from ethics_split import (SEEDS, final_training_set, fit_head, load_clean_data,
                          p_unsafe, seed_split)

d = load_clean_data()

rows = []
for seed in SEEDS:
    Xtr, ytr, Xte, yte, _ = seed_split(d, seed)
    clf = fit_head(Xtr, ytr)
    p, unsafe = p_unsafe(clf, Xte), yte != "safe"
    pred = clf.predict(Xte)
    pm = p_unsafe(clf, d["med_te"])
    rows.append(dict(
        seed=seed, n_test=len(yte),
        acc=accuracy_score(yte, pred),
        wv_recall=(pred[yte == "weapons_violence"] == "weapons_violence").mean(),
        recall_04=(p[unsafe] >= 0.4).mean(), fa_04=(p[~unsafe] >= 0.4).mean(),
        recall_06=(p[unsafe] >= 0.6).mean(), fa_06=(p[~unsafe] >= 0.6).mean(),
        med_fa_06=(pm >= 0.6).mean(),
        borderline=((p >= 0.4) & (p < 0.6)).mean()))

df = pd.DataFrame(rows).round(4)
print(df.to_string(index=False))
print("\nMean:\n", df.drop(columns="seed").mean().round(4).to_string())
print("\nStd:\n", df.drop(columns="seed").std().round(4).to_string())
os.makedirs("brain/ml/results", exist_ok=True)
df.to_csv("brain/ml/results/ethics_v5_clean_metrics.csv", index=False)

Xall, yall = final_training_set(d)
final = fit_head(Xall, yall)
os.makedirs("brain/ml/models", exist_ok=True)
joblib.dump(final, "brain/ml/models/ethics_head_v5_clean.joblib")
print("\nSaved: brain/ml/models/ethics_head_v5_clean.joblib | classes:", list(final.classes_))
