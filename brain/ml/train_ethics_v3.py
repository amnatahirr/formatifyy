"""Ethics head v3 = v2 + medical hard negatives (syringe, stethoscope, lab coat,
oxygen mask) in the 'safe' class.

Same recipe as v2 (frozen CLIP ViT-B/32 embeddings -> LogisticRegression,
i.e. linear probing). Same test set as v2 (ethics_split.py), so the numbers
compare directly. Metrics: python brain/ml/evaluate_ethics.py v2 v3

Repo root se: python brain/ml/train_ethics_v3.py
"""
import os
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression

from ethics_split import load_split

import pandas as pd
from ethics_split import MEDICAL_EMB, MEDICAL_META

# Har medical class se sirf 100 train images. Zyada lene se 'safe' class itni bhaari
# ho jati thi ke weapons recall 99.0% se 97.1% gir jata tha (sweep: 100/250/500/all).
MED_PER_CLASS = 100

if not os.path.exists(MEDICAL_EMB):
    raise SystemExit("Medical embeddings nahi mile. Pehle extract_medical_embeddings.py chalao.")
s = load_split(with_medical=False)
mm = pd.read_csv(MEDICAL_META); Xm = np.load(MEDICAL_EMB)
sel = mm[mm["split"] == "train"].groupby("label").sample(n=MED_PER_CLASS, random_state=42).index
Xtr = np.concatenate([s["Xtr"], Xm[sel]])
ytr = np.concatenate([s["ytr"], ["safe"] * len(sel)])

print("Train:", len(Xtr), dict(zip(*np.unique(ytr, return_counts=True))))
clf = LogisticRegression(max_iter=3000, class_weight="balanced").fit(Xtr, ytr)

os.makedirs("brain/ml/models", exist_ok=True)
joblib.dump(clf, "brain/ml/models/ethics_head_v3.joblib")
print("Saved: brain/ml/models/ethics_head_v3.joblib")
