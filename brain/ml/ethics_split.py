"""Ethics head ka train/test split, ek hi jagah.

train_ethics_v2.py wala split hi hai (seed 42), taake purane aur naye nateeje
same test set par compare hon. Agar medical embeddings maujood hon to unka
alag split bhi banta hai (safe class ke hard negatives).

Repo root se chalana: python brain/ml/<script>.py
"""
import os
import numpy as np, pandas as pd
from sklearn.model_selection import GroupShuffleSplit, train_test_split

D = "brain/ml/results/ethics"
MEDICAL_EMB = f"{D}/embeddings_medical.npy"
MEDICAL_META = f"{D}/meta_medical.csv"


def _stack(parts):
    parts = [p for p in parts if len(p[0])]
    X = np.concatenate([p[0] for p in parts])
    y = np.concatenate([[p[1]] * len(p[0]) for p in parts])
    return X, y


def load_split(with_medical=True):
    """Returns dict: Xtr, ytr, Xte, yte, and Xmed_te (medical test images, all 'safe')."""
    rng = np.random.RandomState(42)

    Xa = np.load(f"{D}/embeddings_all_reports.npy")
    ma = pd.read_csv(f"{D}/meta_all_reports.csv")
    photo = (ma["photo_score"] > 0.5).values
    rest = rng.choice(np.where(~photo)[0], size=2000, replace=False)
    idx = np.concatenate([np.where(photo)[0], rest])
    X_safe, g_safe = Xa[idx], ma["group"].values[idx]

    Xs = np.load(f"{D}/embeddings.npy"); ms = pd.read_csv(f"{D}/meta.csv")
    X_sex = Xs[(ms["label"] == "sexual").values]

    Xw = np.load(f"{D}/embeddings_weapons.npy"); mw = pd.read_csv(f"{D}/meta_weapons.csv")
    is_val = (mw["group"] == "val").values
    is_wv = mw["label"].isin(["weapons", "violence"]).values
    X_wv_tr, X_wv_te = Xw[is_wv & is_val], Xw[is_wv & ~is_val]
    X_neg7 = Xw[(mw["label"] == "negative").values]

    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
                  .split(X_safe, groups=g_safe))
    sex_tr, sex_te = train_test_split(X_sex, test_size=0.2, random_state=42)

    X_med_tr = X_med_te = np.zeros((0, 512), dtype=np.float32)
    if with_medical and os.path.exists(MEDICAL_EMB):
        Xm = np.load(MEDICAL_EMB); mm = pd.read_csv(MEDICAL_META)
        X_med_tr = Xm[(mm["split"] == "train").values]
        X_med_te = Xm[(mm["split"] == "test").values]

    Xtr, ytr = _stack([(X_safe[tr], "safe"), (X_neg7, "safe"), (X_med_tr, "safe"),
                       (sex_tr, "sexual"), (X_wv_tr, "weapons_violence")])
    Xte, yte = _stack([(X_safe[te], "safe"), (sex_te, "sexual"),
                       (X_wv_te, "weapons_violence")])
    return {"Xtr": Xtr, "ytr": ytr, "Xte": Xte, "yte": yte, "Xmed_te": X_med_te}
