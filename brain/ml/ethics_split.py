"""Image ethics head: data loading, dedup aur train/test split, ek hi jagah.

Main recipe (v5_clean, jo backend mein chal raha hai):
  1. Har group ke andar near-duplicate images hatao (CLIP cosine > 0.98).
     Reports mein 18,036 mein se 13,663 images duplicates thin.
  2. Test set se wo images nikaalo jo kisi train image se > 0.98 milti hon
     (leakage). Is se test number sacha rehta hai.
  3. Safe class = report images (photo wali + 2000 random) + weapons dataset ke
     negatives + medical hard negatives (100 per class).
  4. 6 alag seeds par evaluate karo, mean ± std report karo.

Use: train_ethics_v5_clean.py, evaluate_ethics.py.
Repo root se chalana: python brain/ml/<script>.py
"""
import os
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit, train_test_split

D = "brain/ml/results/ethics"
MEDICAL_EMB = f"{D}/embeddings_medical.npy"
MEDICAL_META = f"{D}/meta_medical.csv"
SCENE_EMB = f"{D}/embeddings_scenes.npy"
SCENE_META = f"{D}/meta_scenes.csv"
TH_DUP = 0.98
MED_PER_CLASS = 100
SEEDS = [1, 2, 3, 4, 5, 42]


def dedupe(X, groups=None, th=TH_DUP):
    """Boolean mask: har group ke andar sirf pehli copy rakho."""
    groups = np.zeros(len(X)) if groups is None else groups
    keep = np.ones(len(X), bool)
    for g in np.unique(groups):
        ids = np.where(groups == g)[0]
        S = X[ids] @ X[ids].T
        for a in range(len(ids)):
            if keep[ids[a]]:
                for b in np.where(S[a] > th)[0]:
                    if b > a:
                        keep[ids[b]] = False
    return keep


def clean(test, train, th=TH_DUP):
    """Test se wo images hatao jo kisi train image se bohut milti hon (leakage)."""
    if len(test) == 0:
        return test
    return test[(test @ train.T).max(axis=1) <= th]


def stack(parts):
    parts = [p for p in parts if len(p[0])]
    return (np.concatenate([p[0] for p in parts]),
            np.concatenate([[p[1]] * len(p[0]) for p in parts]))


def sample_med(X, labels, seed, n=MED_PER_CLASS):
    r = np.random.RandomState(seed)
    ids = []
    for lab in np.unique(labels):
        pool = np.where(labels == lab)[0]
        ids += list(r.choice(pool, size=min(n, len(pool)), replace=False))
    return X[ids]


def fit_head(X, y):
    return LogisticRegression(max_iter=3000, class_weight="balanced").fit(X, y)


def p_unsafe(clf, X):
    return 1 - clf.predict_proba(X)[:, list(clf.classes_).index("safe")]


def load_clean_data(verbose=True):
    """Saara data, duplicates hata ke. Har class alag array mein."""
    Xa = np.load(f"{D}/embeddings_all_reports.npy")
    ma = pd.read_csv(f"{D}/meta_all_reports.csv")
    k = dedupe(Xa, ma["group"].values)
    n_reports = len(Xa)
    Xa, ma = Xa[k], ma[k].reset_index(drop=True)
    rng = np.random.RandomState(42)
    photo = (ma["photo_score"] > 0.5).values
    rest_ids = np.where(~photo)[0]
    rest = rng.choice(rest_ids, size=min(2000, len(rest_ids)), replace=False)
    idx = np.concatenate([np.where(photo)[0], rest])

    Xs = np.load(f"{D}/embeddings.npy"); ms = pd.read_csv(f"{D}/meta.csv")
    X_sex = Xs[(ms["label"] == "sexual").values]
    X_sex = X_sex[dedupe(X_sex)]

    Xw = np.load(f"{D}/embeddings_weapons.npy"); mw = pd.read_csv(f"{D}/meta_weapons.csv")
    is_val = (mw["group"] == "val").values
    is_wv = mw["label"].isin(["weapons", "violence"]).values
    wv_tr = Xw[is_wv & is_val]; wv_tr = wv_tr[dedupe(wv_tr)]
    wv_te = clean(Xw[is_wv & ~is_val], wv_tr)
    neg7 = Xw[(mw["label"] == "negative").values]

    Xm = np.load(MEDICAL_EMB); mm = pd.read_csv(MEDICAL_META)
    n_med = len(Xm)
    km = dedupe(Xm, mm["label"].values)
    Xm, mm = Xm[km], mm[km].reset_index(drop=True)
    m_tr = (mm["split"] == "train").values

    d = dict(X_safe=Xa[idx], g_safe=ma["group"].values[idx], photo_safe=photo[idx],
             X_sex=X_sex, wv_tr=wv_tr, wv_te=wv_te, neg7=neg7,
             med_tr=Xm[m_tr], lab_tr=mm["label"].values[m_tr],
             med_te=clean(Xm[~m_tr], Xm[m_tr]),
             med_all=Xm, lab_all=mm["label"].values)

    # Places365 scenes (outdoor / real-world hard negatives), agar extract ho chuki hon
    empty = np.zeros((0, 512), dtype=np.float32)
    d.update(scn_tr=empty, scn_lab_tr=np.array([]), scn_te=empty,
             scn_all=empty, scn_lab_all=np.array([]))
    if os.path.exists(SCENE_EMB):
        Xc = np.load(SCENE_EMB); mc = pd.read_csv(SCENE_META)
        kc = dedupe(Xc, mc["label"].values)
        Xc, mc = Xc[kc], mc[kc].reset_index(drop=True)
        c_tr = (mc["split"] == "train").values
        d.update(scn_tr=Xc[c_tr], scn_lab_tr=mc["label"].values[c_tr],
                 scn_te=clean(Xc[~c_tr], Xc[c_tr]),
                 scn_all=Xc, scn_lab_all=mc["label"].values)
    if verbose:
        print(f"Reports: {n_reports} -> {len(Xa)} (dedup) | Safe used: {len(d['X_safe'])}")
        print(f"Medical: {n_med} -> {len(Xm)} (dedup) | medical test (saaf): {len(d['med_te'])}")
        print(f"Scenes: train {len(d['scn_tr'])} | scene test (saaf): {len(d['scn_te'])}")
        print(f"Sexual: {len(X_sex)} | Weapons train: {len(wv_tr)}, test: {len(wv_te)}\n")
    return d


def _clean_mask(test, train, th=TH_DUP):
    if len(test) == 0:
        return np.zeros(0, bool)
    return (test @ train.T).max(axis=1) <= th


def seed_split(d, seed, scenes_per_class=0):
    """Ek seed ka train/test. Safe reports ke hisaab se split (GroupShuffleSplit).

    scenes_per_class: har Places365 scene se kitni train images safe mein daalni hain
    (0 = v5_clean recipe). Returns Xtr, ytr, Xte, yte, photo_te, jahan photo_te
    batata hai ke Xte ki kaunsi row held-out report ki photo-jaisi safe image hai.
    """
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
                  .split(d["X_safe"], groups=d["g_safe"]))
    sex_tr, sex_te = train_test_split(d["X_sex"], test_size=0.2, random_state=seed)
    keep = _clean_mask(d["X_safe"][te], d["X_safe"][tr])
    s_te, s_photo = d["X_safe"][te][keep], d["photo_safe"][te][keep]
    x_te = clean(sex_te, sex_tr)
    parts = [(d["X_safe"][tr], "safe"), (d["neg7"], "safe"),
             (sample_med(d["med_tr"], d["lab_tr"], seed), "safe")]
    if scenes_per_class:
        parts.append((sample_med(d["scn_tr"], d["scn_lab_tr"], seed, n=scenes_per_class), "safe"))
    Xtr, ytr = stack(parts + [(sex_tr, "sexual"), (d["wv_tr"], "weapons_violence")])
    Xte, yte = stack([(s_te, "safe"), (x_te, "sexual"), (d["wv_te"], "weapons_violence")])
    photo_te = np.concatenate([s_photo, np.zeros(len(Xte) - len(s_te), bool)])
    return Xtr, ytr, Xte, yte, photo_te


def final_training_set(d, scenes_per_class=0):
    """Deployment model: saara saaf data. Is par alag se metrics nikaalna jhoot hoga."""
    parts = [(d["X_safe"], "safe"), (d["neg7"], "safe"),
             (sample_med(d["med_all"], d["lab_all"], 42), "safe")]
    if scenes_per_class:
        parts.append((sample_med(d["scn_all"], d["scn_lab_all"], 42, n=scenes_per_class), "safe"))
    return stack(parts + [(d["X_sex"], "sexual"), (d["wv_tr"], "weapons_violence"),
                          (d["wv_te"], "weapons_violence")])


# ---------------------------------------------------------------------------
# Purana (v2/v3) split: bina dedup, sirf seed 42. Sirf train_ethics_v3.py ke liye
# rakha hai. Is ke numbers lucky split + duplicates ki wajah se optimistic the.
# ---------------------------------------------------------------------------
def load_split(with_medical=True):
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

    Xtr, ytr = stack([(X_safe[tr], "safe"), (X_neg7, "safe"), (X_med_tr, "safe"),
                      (sex_tr, "sexual"), (X_wv_tr, "weapons_violence")])
    Xte, yte = stack([(X_safe[te], "safe"), (sex_te, "sexual"),
                      (X_wv_te, "weapons_violence")])
    return {"Xtr": Xtr, "ytr": ytr, "Xte": Xte, "yte": yte, "Xmed_te": X_med_te}
