import os
import joblib
import re

# -------------------------------
# MODEL PATH
# -------------------------------
BASE_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(BASE_DIR, "structure_model.pkl")

try:
    model = joblib.load(MODEL_PATH)
    print(f"Loaded model from {MODEL_PATH}")
except:
    model = None
    print("Model not loaded, using rules only.")

# -----------------------------
# CONFIG
# -----------------------------

BULLET_SYMBOLS = ("-", "*", "•")

LIST_INDICATORS = (
    "following are",
    "below are",
    "the following",
    "items:",
    "points:",
    "includes:",
)

IMPLICIT_BULLET_KEYWORDS = {
    "this", "user", "system", "admin",
    "add", "create", "update", "check",
    "define", "set", "enable", "install"
}

# -----------------------------
# HELPERS
# -----------------------------

def is_title_like(words):
    if not words:
        return False
    capitalized = sum(1 for w in words if w[0].isupper() or w.isupper())
    return capitalized / len(words) >= 0.6


def normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()

# -----------------------------
# RULE ENGINE
# -----------------------------

def rule_detect(line: str, prev_type: str = None) -> str:
    raw_line = line
    line = normalize_line(line)

    if not line:
        return "empty"

    words = line.split()
    word_count = len(words)

    lower_line = line.lower()
    ends_colon = line.endswith(":")
    ends_period = line.endswith(".")

    is_all_caps = line.isupper()
    is_title_case = line.istitle()

    # ---------------- HEADING 1 ----------------
    if (
        re.match(r"^chapter\s+\d+", lower_line)
        or re.match(r"^\d+\.\s+[A-Z]", line)
        or (
            is_all_caps and 1 <= word_count <= 8 and not ends_period
        )
    ):
        return "heading1"

    # ---------------- HEADING 2 ----------------
    if (
        1 <= word_count <= 6
        and not ends_period
        and prev_type == "heading1"
        and (
            is_title_case or is_all_caps or is_title_like(words)
        )
    ):
        return "heading2"

    # ---------------- HEADING 3 ----------------
    if ends_colon or any(ind in lower_line for ind in LIST_INDICATORS):
        return "heading3"

    if (
        1 <= word_count <= 10
        and not ends_period
        and prev_type in {"heading2", "paragraph"}
        and is_title_like(words)
    ):
        return "heading3"

    # ---------------- NUMBERED ----------------
    if re.match(r"^(\d+|[a-zA-Z])[\)\.]\s+", line):
        return "numbered"

    # ---------------- BULLET SYMBOL ----------------
    if raw_line.lstrip().startswith(BULLET_SYMBOLS):
        return "bullet"

    # ---------------- IMPLICIT BULLET ----------------
    if prev_type in {"heading3", "bullet"}:
        first_word = words[0].lower()
        if first_word in IMPLICIT_BULLET_KEYWORDS and word_count <= 12:
            return "bullet"

    return None

# -----------------------------
# FINAL PREDICTOR
# -----------------------------

def predict_line_type(text: str, prev_type: str = None):
    text = text.strip()
    if not text:
        return "empty", 1.0

    # 1️⃣ RULES FIRST (STRONG)
    rule_label = rule_detect(text, prev_type)
    if rule_label:
        return rule_label, 1.0

    # 2️⃣ ML FALLBACK
    if model:
        prediction = model.predict([text])[0]
        confidence = max(model.predict_proba([text])[0])

        if prediction == "heading":
            # If ML says heading → decide level by length
            wc = len(text.split())
            if wc <= 4:
                return "heading1", confidence
            elif wc <= 7:
                return "heading2", confidence
            else:
                return "heading3", confidence

        if confidence < 0.6:
            return "paragraph", confidence

        return prediction, confidence

    # 3️⃣ LAST RESORT
    return "paragraph", 0.5


def predict_lines(lines: list[str]):
    results = []
    prev_type = None
    for line in lines:
        label, _ = predict_line_type(line, prev_type)
        results.append(label)
        prev_type = label
    return results