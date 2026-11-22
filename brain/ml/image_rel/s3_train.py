"""STAGE 3: train the relevance scorer (XGBoost) on features_train.csv, choose threshold and
Claude-fallback band on features_val.csv only. Test set is NOT touched here.
Run:  python brain/ml/image_rel/s3_train.py"""
import json, datetime, os
import numpy as np, pandas as pd, joblib
import config
from s2_features import FEATS
from metrics_util import *

try:
    from xgboost import XGBClassifier
    HAVE_XGB = True
except Exception:
    from sklearn.ensemble import HistGradientBoostingClassifier
    HAVE_XGB = False


def make_model(depth, seed):
    if HAVE_XGB:
        return XGBClassifier(n_estimators=600, learning_rate=0.05, max_depth=depth, subsample=0.9,
                             colsample_bytree=0.9, eval_metric="auc", early_stopping_rounds=40,
                             random_state=seed, n_jobs=2)
    return HistGradientBoostingClassifier(max_depth=depth, learning_rate=0.05, max_iter=300,
                                          early_stopping=True, random_state=seed)


def fit(m, X, y, Xv, yv):
    if HAVE_XGB:
        m.fit(X, y, eval_set=[(Xv, yv)], verbose=False)
    else:
        m.fit(X, y)
    return m


def drop_captions(X, rng):
    """Robustness: randomly hide caption features AND section-text features during training,
    so the scorer still works when the app cannot supply a caption or section text."""
    X = X.copy()
    m = rng.random(len(X)) < config.CAPTION_DROPOUT
    for c in CAP_FEATS:
        X.loc[m, c] = 0
    m2 = rng.random(len(X)) < config.CAPTION_DROPOUT
    for c in ("mini_cap_sec", "has_sec"):
        X.loc[m2, c] = 0
    return X


def clean_positives(tr, va, frac, rng):
    """Noise cleaning: placed images are not always relevant. Score every TRAIN positive with a model
    that never saw its report (5-fold, grouped by report), then drop the `frac` of positives the
    model finds least believable. Only train rows are touched; val/test are never changed."""
    from sklearn.model_selection import GroupKFold
    X, y = tr[FEATS], tr.label.values
    oof = np.zeros(len(tr))
    for a, b in GroupKFold(n_splits=5).split(X, y, groups=tr.report.values):
        m = fit(make_model(4, config.SEED), drop_captions(X.iloc[a], rng), y[a], va[FEATS], va.label.values)
        oof[b] = m.predict_proba(X.iloc[b])[:, 1]
    pos = np.where(y == 1)[0]
    cut = np.quantile(oof[pos], frac)
    drop = pos[oof[pos] <= cut]
    print(f"[clean] dropping {len(drop)} of {len(pos)} train positives (lowest {frac:.0%} by out-of-fold score, cut={cut:.3f})")
    return tr.drop(tr.index[drop]).reset_index(drop=True)


def main():
    rng = np.random.default_rng(config.SEED)
    tr = pd.read_csv(config.WORK_DIR / "features_train.csv")
    va = pd.read_csv(config.WORK_DIR / "features_val.csv")
    frac = float(os.environ.get("IMGREL_CLEAN_FRAC", "0"))
    if frac > 0:
        tr = clean_positives(tr, va, frac, rng)
    Xtr, ytr = drop_captions(tr[FEATS], rng), tr.label.values
    Xva, yva = va[FEATS], va.label.values
    Xva_nc = mask_caption(Xva)
    best = None
    for depth in (3, 4, 6):
        m = fit(make_model(depth, config.SEED), Xtr, ytr, Xva, yva)
        p, pn = m.predict_proba(Xva)[:, 1], m.predict_proba(Xva_nc)[:, 1]
        # model selection on average AUC with and without caption (so it works when caption is missing)
        sel = (roc_auc_score(yva, p) + roc_auc_score(yva, pn)) / 2
        print(f"depth={depth}: val AUC with caption {roc_auc_score(yva,p):.4f}, without {roc_auc_score(yva,pn):.4f}")
        if best is None or sel > best[0]:
            best = (sel, depth, m)
    _, depth, model = best
    s_val = model.predict_proba(Xva)[:, 1]
    t = best_threshold(yva, s_val)
    table = band_table(yva, s_val, t)
    chosen, reached = pick_band(table, config.TARGET_LOCAL_ACC)
    pd.DataFrame(table).to_csv(config.RESULTS_DIR / "threshold_table_val.csv", index=False)
    imp = dict(zip(FEATS, [float(x) for x in getattr(model, "feature_importances_", np.zeros(len(FEATS)))]))
    meta = json.loads((config.WORK_DIR / "feature_meta.json").read_text())
    bundle = {"model": model, "features": FEATS, "t_dec": t, "band_half_width": chosen["half_width"],
              "band_reached_target": reached, "feature_meta": meta, "max_depth": depth,
              "val_metrics": basic(yva, s_val, t), "trained": datetime.datetime.now().isoformat(timespec="seconds")}
    config.MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, config.MODEL_PATH)
    (config.RESULTS_DIR / "train_summary.json").write_text(json.dumps(
        {k: v for k, v in bundle.items() if k != "model"} | {"feature_importance": imp, "band_row": chosen}, indent=2, default=str))
    print(f"\n[OK] model saved: {config.MODEL_PATH}")
    print(f"     threshold t_dec={t:.3f} (chosen on val)  val metrics: {bundle['val_metrics']}")
    print(f"     fallback band ±{chosen['half_width']}: {chosen['pct_to_claude']}% to Claude, local acc {chosen['local_acc']} "
          f"({'target met' if reached else 'TARGET NOT MET - best available'})")
    print("     top features:", sorted(imp.items(), key=lambda x: -x[1])[:5])


if __name__ == "__main__":
    main()
