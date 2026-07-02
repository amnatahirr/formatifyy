# ML/features.py
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin

class StructureFeatures(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        starts_with_bullet = X.str.strip().str.match(r"^[-•*]").astype(int)
        starts_with_number = X.str.strip().str.match(r"^\d+\.|^[a-zA-Z]\)").astype(int)
        return np.c_[starts_with_bullet, starts_with_number]