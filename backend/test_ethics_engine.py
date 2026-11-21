import os, sys, base64
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import functions.image_ethics as ie

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
meta = pd.read_csv(os.path.join(ROOT, "brain", "ml", "results", "ethics", "meta_all_reports.csv"))
rng = np.random.RandomState(7)

# photo_score wali images shamil karne ke liye aadhi photos, aadhi random
photos = meta[meta["photo_score"] > 0.7].sample(6, random_state=7)
others = meta.sample(6, random_state=7)
for _, row in pd.concat([photos, others]).iterrows():
    with open(os.path.join(ROOT, row["path"]), "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    for eng in ("local", "keyword"):
        ie.ETHICS_ENGINE = eng
        r = ie.analyze_image_ethics_sync(b64)
        print(f"   {eng:8s} -> {r['verdict']:9s} {r['category']}")