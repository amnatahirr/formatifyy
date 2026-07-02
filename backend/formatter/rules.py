import re

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
# HELPER FUNCTIONS
# -----------------------------

def is_title_like(words):
    """
    Returns True if most words start with capital letters.
    PDF-safe: supports ALL CAPS words too.
    """
    if not words:
        return False

    capitalized = sum(
        1 for w in words
        if w[0].isupper() or w.isupper()
    )
    return capitalized / len(words) >= 0.6


def normalize_line(line: str) -> str:
    """
    Safe normalization for PDF text.
    Does NOT affect DOCX behavior.
    """
    return re.sub(r"\s+", " ", line).strip()

# -----------------------------
# CORE DETECTOR
# -----------------------------

def detect_line_type(line: str, prev_type: str = None) -> str:
    """
    Detects the structural role of a line in an academic document.
    """

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

    # --------------------------------------------------
    # HEADING 1 — MAIN SECTIONS
    # --------------------------------------------------

    if (
        re.match(r"^chapter\s+\d+", lower_line)
        or re.match(r"^\d+\.\s+[A-Z]", line)
        or (
            is_all_caps
            and 1 <= word_count <= 8
            and not ends_period
        )
    ):
        return "heading1"

    # --------------------------------------------------
    # HEADING 2 — SUB SECTIONS
    # (original logic + PDF tolerance)
    # --------------------------------------------------

    if (
        1 <= word_count <= 6
        and not ends_period
        and prev_type == "heading1"
        and (
            is_title_case
            or is_all_caps
            or is_title_like(words)
        )
    ):
        return "heading2"

    # --------------------------------------------------
    # HEADING 3 — SUB-SUB / LIST INTRO
    # ⚠️ ORDER PRESERVED (VERY IMPORTANT)
    # --------------------------------------------------

    if (
        ends_colon
        or any(ind in lower_line for ind in LIST_INDICATORS)
    ):
        return "heading3"

    if (
        1 <= word_count <= 10
        and not ends_period
        and prev_type in {"heading2", "paragraph"}
        and is_title_like(words)
    ):
        return "heading3"

    # --------------------------------------------------
    # NUMBERED LIST
    # --------------------------------------------------

    if re.match(r"^(\d+|[a-zA-Z])[\)\.]\s+", line):
        return "numbered"

    # --------------------------------------------------
    # BULLET LIST — SYMBOL BASED
    # --------------------------------------------------

    if raw_line.lstrip().startswith(BULLET_SYMBOLS):
        return "bullet"

    # --------------------------------------------------
    # IMPLICIT BULLETS
    # --------------------------------------------------

    if prev_type in {"heading3", "bullet"}:
        first_word = words[0].lower()
        if first_word in IMPLICIT_BULLET_KEYWORDS and word_count <= 12:
            return "bullet"

    # --------------------------------------------------
    # DEFAULT
    # --------------------------------------------------

    return "paragraph"
