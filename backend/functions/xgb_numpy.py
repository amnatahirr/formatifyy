"""
functions/xgb_numpy.py — run a saved XGBoost model (JSON) with numpy only.

Why: the app also loads torch (BLIP/CLIP), which brings Intel's OpenMP
(libiomp5). xgboost's native library brings a second OpenMP (libomp). Two
OpenMP runtimes in one process crash it (SIGSEGV in __kmp_* while analysing).
Prediction is just walking trees, so we do it here without xgboost's native
library: same JSON file, same probabilities.

Training (brain/ml/train_headings_v4.py) still uses the real xgboost.

Supports what our heading models use: gbtree, numerical splits,
multi:softprob / multi:softmax, early stopping (best_iteration).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

import numpy as np


class _Tree:
    __slots__ = ("left", "right", "feat", "cond", "default_left", "leaf")

    def __init__(self, t: dict):
        self.left = np.asarray(t["left_children"], dtype=np.int64)
        self.right = np.asarray(t["right_children"], dtype=np.int64)
        self.feat = np.asarray(t["split_indices"], dtype=np.int64)
        # xgboost works in float32: thresholds AND features must be float32,
        # or values that sit exactly on a threshold go the wrong way
        self.cond = np.asarray(t["split_conditions"], dtype=np.float32)  # leaf value on leaves
        self.default_left = np.asarray(t["default_left"], dtype=bool)
        self.leaf = self.left == -1
        if any(t.get("split_type") or []) or t.get("categories"):
            raise ValueError("categorical splits are not supported")

    def predict(self, X: np.ndarray) -> np.ndarray:
        node = np.zeros(len(X), dtype=np.int64)
        rows = np.arange(len(X))
        active = ~self.leaf[node]
        while active.any():
            r, n = rows[active], node[active]
            x = X[r, self.feat[n]]
            # xgboost: go left when x < split; missing (NaN) follows default_left
            go_left = np.where(np.isnan(x), self.default_left[n], x < self.cond[n])
            node[r] = np.where(go_left, self.left[n], self.right[n])
            active = ~self.leaf[node]
        return self.cond[node]


class NumpyXGBClassifier:
    """predict_proba() compatible with xgboost.XGBClassifier for our models."""

    def __init__(self, path: Path | str):
        m = json.loads(Path(path).read_text(encoding="utf-8"))
        learner = m["learner"]
        objective = learner["objective"]["name"]
        if objective not in ("multi:softprob", "multi:softmax"):
            raise ValueError(f"unsupported objective {objective}")
        booster = learner["gradient_booster"]
        if booster["name"] != "gbtree":
            raise ValueError(f"unsupported booster {booster['name']}")
        model = booster["model"]
        self.n_classes = int(learner["learner_model_param"]["num_class"])
        self.n_features = int(learner["learner_model_param"]["num_feature"])

        # Early stopping: XGBClassifier predicts with trees up to best_iteration
        n_trees = len(model["trees"])
        best = (learner.get("attributes") or {}).get("best_iteration")
        indptr = model.get("iteration_indptr")
        if best is not None and indptr:
            n_trees = int(indptr[int(best) + 1])
        self.trees: List[_Tree] = [_Tree(t) for t in model["trees"][:n_trees]]
        self.tree_class = np.asarray(model["tree_info"][:n_trees], dtype=np.int64)
        # base_score is the same for every class, so it cancels out in softmax

    def predict_margin(self, X) -> np.ndarray:
        X = np.asarray(X, dtype=np.float32)
        if X.ndim != 2 or X.shape[1] != self.n_features:
            raise ValueError(f"expected (n, {self.n_features}) features, got {X.shape}")
        out = np.zeros((len(X), self.n_classes))
        for tree, k in zip(self.trees, self.tree_class):
            out[:, k] += tree.predict(X).astype(np.float64)
        return out

    def predict_proba(self, X) -> np.ndarray:
        z = self.predict_margin(X)
        z -= z.max(axis=1, keepdims=True)
        e = np.exp(z)
        return e / e.sum(axis=1, keepdims=True)

    def predict(self, X) -> np.ndarray:
        return self.predict_proba(X).argmax(axis=1)
