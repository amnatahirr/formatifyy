# ml/train.py

import os
import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

# -------------------------------
# Dataset Path
# -------------------------------
BASE_DIR = os.path.dirname(__file__)
DATASET_PATH = os.path.join(BASE_DIR, "../dataset.csv")
MODEL_PATH = os.path.join(BASE_DIR, "structure_model.pkl")

# -------------------------------
# Load Dataset
# -------------------------------
if not os.path.exists(DATASET_PATH):
    print(f"❌ Dataset not found at: {DATASET_PATH}")
    exit()

data = pd.read_csv(DATASET_PATH)

print("✅ Dataset loaded successfully")
print("\nClass Distribution:")
print(data["label"].value_counts())

# -------------------------------
# Clean Dataset
# -------------------------------
data["text"] = data["text"].fillna("")
data["label"] = data["label"].fillna("paragraph")

# -------------------------------
# Features & Labels
# -------------------------------
X = data["text"]
y = data["label"]

# -------------------------------
# Train/Test Split
# -------------------------------
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

# -------------------------------
# Pipeline (ONLY NLP FEATURES)
# -------------------------------
model = Pipeline([
    ("tfidf", TfidfVectorizer(
        analyzer="char_wb",     # 🔥 IMPORTANT
        ngram_range=(3, 5),
        max_features=40000
    )),
    ("clf", LogisticRegression(
        max_iter=2000,
        class_weight="balanced"
    ))
])

# -------------------------------
# Training
# -------------------------------
print("\n🔹 Training NLP Structure Detection Model...")
model.fit(X_train, y_train)

# -------------------------------
# Evaluation
# -------------------------------
y_pred = model.predict(X_test)

print("\n📊 Classification Report:")
print(classification_report(y_test, y_pred))

# -------------------------------
# Save Model
# -------------------------------
joblib.dump(model, MODEL_PATH)
print(f"\n✅ Model saved at: {MODEL_PATH}")