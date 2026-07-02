# ml/feature_extractor.py
# List indicators for heading3 detection
LIST_INDICATORS = (
    "following are",
    "below are",
    "the following",
    "items:",
    "points:",
    "includes:",
)

# Keywords for implicit bullets
IMPLICIT_BULLET_KEYWORDS = {
    "this", "user", "system", "admin",
    "add", "create", "update", "check",
    "define", "set", "enable", "install"
}
BULLET_SYMBOLS = ("-", "*", "•")

def extract_features(text, prev_type=None):
    words = text.split()
    word_count = len(words)
    stripped = text.strip()
    lstripped = text.lstrip()
    lower_text = text.lower()

    # Existing features
    f_word_count = word_count
    f_is_all_caps = int(stripped.isupper())
    f_ends_colon = int(stripped.endswith(":"))
    f_ends_period = int(stripped.endswith("."))
    f_starts_bullet = int(lstripped.startswith(("-", "*", "•")))
    f_capital_ratio = sum(1 for w in words if w[0].isupper()) / max(word_count,1)
    
    # New features
    f_is_title_case = int(text.istitle())
    f_ends_list_indicator = int(any(ind in lower_text for ind in LIST_INDICATORS))
    first_word = words[0].lower() if words else ""
    f_starts_keyword = int(first_word in IMPLICIT_BULLET_KEYWORDS)

    # Encode previous line type as numeric
    type_mapping = {
        None: 0,
        "paragraph": 1,
        "heading1": 2,
        "heading2": 3,
        "heading3": 4,
        "bullet": 5,
        "numbered": 6,
        "empty": 7
    }
    f_prev_type = type_mapping.get(prev_type, 0)

    features = [
        f_word_count,
        f_is_all_caps,
        f_ends_colon,
        f_ends_period,
        f_starts_bullet,
        f_capital_ratio,
        f_is_title_case,
        f_ends_list_indicator,
        f_starts_keyword,
        f_prev_type
    ]
    return features