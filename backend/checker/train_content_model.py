"""
checker/train_content_model.py
═══════════════════════════════════════════════════════════════════════════════
STEP 2 OF 3 — Run this AFTER extract_training_data.py

What it does:
    1. Loads checker/training_data.json
    2. Creates positive examples  (heading + correct content   → label 1)
    3. Creates negative examples  (heading + shuffled content  → label 0)
    4. Encodes all pairs with sentence-transformers (all-MiniLM-L6-v2)
    5. Trains a Logistic Regression classifier
    6. Saves the model to checker/content_classifier.pkl

How to run:
    python checker/train_content_model.py

Requirements:
    pip install sentence-transformers scikit-learn
═══════════════════════════════════════════════════════════════════════════════
"""

import json
import os
import random
import pickle
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

TRAINING_DATA_PATH = os.path.join(os.path.dirname(__file__), "training_data.json")
MODEL_PATH         = os.path.join(os.path.dirname(__file__), "content_classifier.pkl")
EMBEDDER_NAME      = "all-MiniLM-L6-v2"
MAX_CONTENT_CHARS  = 512
RANDOM_SEED        = 42


def load_sections():
    if not os.path.exists(TRAINING_DATA_PATH):
        raise FileNotFoundError(
            f"\n❌  Training data not found at: {TRAINING_DATA_PATH}\n"
            f"    Run this first:\n"
            f"    python checker/extract_training_data.py\n"
        )
    with open(TRAINING_DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    data = [s for s in data if s.get("heading") and s.get("content")
            and len(s["content"].strip()) > 20]
    logger.info("Loaded %d valid sections from training_data.json", len(data))
    return data


def build_dataset(sections):
    random.seed(RANDOM_SEED)
    positives = [(s["heading"], s["content"], 1) for s in sections]

    headings          = [s["heading"] for s in sections]
    contents          = [s["content"] for s in sections]
    shuffled_contents = contents.copy()
    random.shuffle(shuffled_contents)

    negatives = []
    for i, heading in enumerate(headings):
        wrong_content = shuffled_contents[i]
        original      = sections[i]["content"]
        if wrong_content.strip()[:80] != original.strip()[:80]:
            negatives.append((heading, wrong_content, 0))

    min_count = min(len(positives), len(negatives))
    positives = random.sample(positives, min_count)
    negatives = random.sample(negatives, min_count)

    all_data = positives + negatives
    random.shuffle(all_data)

    logger.info(
        "Dataset: %d positives + %d negatives = %d total",
        len(positives), len(negatives), len(all_data),
    )
    return all_data


def train():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.error("❌  pip install sentence-transformers")
        return False

    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import classification_report, accuracy_score
    except ImportError:
        logger.error("❌  pip install scikit-learn")
        return False

    sections = load_sections()

    if len(sections) < 10:
        logger.error(
            "❌  Not enough training data (%d sections, need 10+).\n"
            "   Run: python checker/extract_training_data.py", len(sections)
        )
        return False

    if len(sections) < 30:
        logger.warning("⚠  Only %d sections — accuracy may be limited.", len(sections))

    all_data = build_dataset(sections)
    texts    = [
        f"{h} [SEP] {c[:MAX_CONTENT_CHARS]}"
        for h, c, _ in all_data
    ]
    labels = [lbl for _, _, lbl in all_data]

    logger.info("Loading embedding model '%s'...", EMBEDDER_NAME)
    logger.info("(First run downloads ~90MB model — cached after that)")
    t0       = time.time()
    embedder = SentenceTransformer(EMBEDDER_NAME)

    logger.info("Encoding %d pairs... (1-3 minutes)", len(texts))
    embeddings = embedder.encode(
        texts, show_progress_bar=True,
        batch_size=32, convert_to_numpy=True,
    )
    logger.info("Encoding done in %.1fs", time.time() - t0)

    X_train, X_test, y_train, y_test = train_test_split(
        embeddings, labels,
        test_size=0.2, random_state=RANDOM_SEED, stratify=labels,
    )
    logger.info("Train: %d | Test: %d", len(X_train), len(X_test))

    logger.info("Training Logistic Regression...")
    t1  = time.time()
    clf = LogisticRegression(
        max_iter=1000, C=1.0,
        random_state=RANDOM_SEED, class_weight="balanced",
    )
    clf.fit(X_train, y_train)
    logger.info("Training done in %.1fs", time.time() - t1)

    y_pred   = clf.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    logger.info("\n%s\nMODEL EVALUATION\n%s", "═"*60, "═"*60)
    logger.info("Accuracy: %.1f%%", accuracy * 100)
    print(classification_report(y_test, y_pred,
          target_names=["wrong_placement", "correct_placement"]))

    if accuracy < 0.60:
        logger.warning("⚠  Low accuracy — add more documents and retrain.")
    else:
        logger.info("✓  Accuracy %.1f%% — model ready!", accuracy * 100)

    os.makedirs(os.path.dirname(MODEL_PATH) or ".", exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(clf, f)

    logger.info("✓  Model saved → %s", MODEL_PATH)
    logger.info(
        "\nStep 3: Restart your server:\n"
        "  uvicorn main:app --reload\n"
        "\nContent mismatch check is now active!"
    )
    return True


if __name__ == "__main__":
    train()