# checker/clean_and_retrain.py
# Run: python checker/clean_and_retrain.py

import json, os, re, random, pickle, logging, time
from collections import Counter

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)s  %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

CHECKER_DIR   = os.path.dirname(__file__)
INPUT_JSON    = os.path.join(CHECKER_DIR, "training_data.json")
CLEANED_JSON  = os.path.join(CHECKER_DIR, "training_data_cleaned.json")
MODEL_PATH    = os.path.join(CHECKER_DIR, "content_classifier.pkl")
EMBEDDER_NAME = "all-MiniLM-L6-v2"
RANDOM_SEED   = 42

# ── Comsats canonical headings ────────────────────────────────────────────────
COMSATS_HEADINGS = [
    "Abstract", "Introduction", "Problem Statement", "Objectives", "Scope",
    "Background", "Motivation", "Literature Review", "Related Work",
    "Proposed Solution", "Methodology", "System Design", "Architecture",
    "Implementation", "Tools and Technologies", "Functional Requirements",
    "Non-Functional Requirements", "Testing", "Results", "Discussion",
    "Conclusion", "Future Work", "References", "Acknowledgements",
    "Feasibility Study", "Project Plan", "Timeline", "Budget",
    "Team Members", "Risk Assessment", "Expected Outcomes",
]
CANONICAL_SET = {h.lower() for h in COMSATS_HEADINGS}

# ── Synonym map: every variation → canonical name ─────────────────────────────
SYNONYM_MAP = {
    "abstract": "Abstract", "abstract:": "Abstract",
    "abstract no": "Abstract", "summary": "Abstract",
    "executive summary": "Abstract", "project summary": "Abstract",

    "introduction": "Introduction", "1 introduction": "Introduction",
    "1. introduction": "Introduction", "1.1 introduction": "Introduction",
    "overview": "Introduction", "intro": "Introduction",

    "problem statement": "Problem Statement",
    "problem definition": "Problem Statement",
    "problem": "Problem Statement",
    "1.2 problem statement": "Problem Statement",
    "1.3 problem statement": "Problem Statement",
    "1.3 problem statement:": "Problem Statement",
    "problem identification": "Problem Statement",
    "issue statement": "Problem Statement",

    "objectives": "Objectives", "objective": "Objectives",
    "1.2 objectives": "Objectives", "1.3 objectives": "Objectives",
    "goals": "Objectives", "aims and objectives": "Objectives",
    "project objectives": "Objectives", "aim": "Objectives", "aims": "Objectives",

    "scope": "Scope", "project scope": "Scope",
    "1.4 scope": "Scope", "1.5 project scope": "Scope",
    "1.6 project scope": "Scope", "scope of project": "Scope",
    "scope and limitations": "Scope",

    "background": "Background", "project background": "Background",
    "motivation": "Motivation", "rationale": "Motivation",
    "significance": "Motivation",

    "literature review": "Literature Review",
    "2.1 literature review": "Literature Review",
    "2.1 literature review / existing system study": "Literature Review",
    "lit review": "Literature Review", "related work": "Related Work",
    "2.2 related work": "Related Work", "existing system": "Literature Review",
    "existing systems": "Literature Review", "prior work": "Literature Review",
    "review of literature": "Literature Review", "background study": "Literature Review",
    "survey": "Literature Review",

    "proposed solution": "Proposed Solution",
    "proposed system": "Proposed Solution",
    "proposed approach": "Proposed Solution",

    "methodology": "Methodology", "research methodology": "Methodology",
    "development methodology": "Methodology", "method": "Methodology",
    "approach": "Methodology", "methods": "Methodology",

    "system design": "System Design", "design": "System Design",
    "high level design": "System Design", "detailed design": "System Design",
    "database design": "System Design", "3.1 system design": "System Design",

    "architecture": "Architecture", "system architecture": "Architecture",
    "software architecture": "Architecture",
    "3.4 software architecture": "Architecture",
    "3.1 software architecture": "Architecture",

    "implementation": "Implementation", "development": "Implementation",
    "coding": "Implementation", "system implementation": "Implementation",

    "tools and technologies": "Tools and Technologies",
    "tools & technologies": "Tools and Technologies",
    "tools": "Tools and Technologies", "technologies": "Tools and Technologies",
    "tech stack": "Tools and Technologies",
    "technology stack": "Tools and Technologies",
    "frameworks": "Tools and Technologies", "tools used": "Tools and Technologies",

    "functional requirements": "Functional Requirements",
    "functional requirement": "Functional Requirements",
    "2.3.1 functional requirements": "Functional Requirements",
    "non-functional requirements": "Non-Functional Requirements",
    "non functional requirements": "Non-Functional Requirements",
    "2.3.2 non-functional requirements": "Non-Functional Requirements",
    "requirements": "Functional Requirements",
    "2.3 requirements elicitation": "Functional Requirements",

    "testing": "Testing", "4.2 unit testing": "Testing",
    "4.2.1 unit testing": "Testing", "test cases": "Testing",
    "evaluation": "Testing",

    "results": "Results", "findings": "Results",
    "outcomes": "Results", "experimental results": "Results",

    "discussion": "Discussion", "analysis": "Discussion",

    "conclusion": "Conclusion", "concluding remarks": "Conclusion",
    "5.1 problems faced and lessons learned": "Conclusion",
    "summary and conclusion": "Conclusion",

    "future work": "Future Work", "future scope": "Future Work",
    "5.2 future work": "Future Work", "5.3 future work": "Future Work",
    "6.3 future work": "Future Work", "future directions": "Future Work",
    "future enhancements": "Future Work",

    "references": "References", "references:": "References",
    "6 references": "References", "7 references": "References",
    "bibliography": "References", "citations": "References",

    "acknowledgement": "Acknowledgements",
    "acknowledgements": "Acknowledgements",
    "acknowledgment": "Acknowledgements",
    "acknowledgments": "Acknowledgements",
}


def resolve_heading(raw: str):
    lower      = raw.strip().lower()
    if lower in SYNONYM_MAP:
        return SYNONYM_MAP[lower]
    normalized = re.sub(r"^\d+[\.\d]*\s*", "", lower).strip()
    normalized = re.sub(r"[:\-]+$", "", normalized).strip()
    if normalized in SYNONYM_MAP:
        return SYNONYM_MAP[normalized]
    if normalized in CANONICAL_SET:
        for h in COMSATS_HEADINGS:
            if h.lower() == normalized:
                return h
    return None


# ── Step 1: Clean ─────────────────────────────────────────────────────────────
logger.info("Loading %s ...", INPUT_JSON)
with open(INPUT_JSON, "r", encoding="utf-8") as f:
    raw_data = json.load(f)
logger.info("Raw: %d sections", len(raw_data))

cleaned = []
skipped_nomap = skipped_short = 0

for section in raw_data:
    heading = section.get("heading", "").strip()
    content = section.get("content", "").strip()
    if not heading or not content:
        continue
    if len(content) < 50:
        skipped_short += 1
        continue
    canonical = resolve_heading(heading)
    if canonical is None:
        skipped_nomap += 1
        continue
    cleaned.append({"heading": canonical, "original_heading": heading, "content": content})

logger.info("Kept: %d  |  Skipped (unknown heading): %d  |  Skipped (short): %d",
            len(cleaned), skipped_nomap, skipped_short)

dist = Counter(s["heading"] for s in cleaned)
logger.info("\nHeading distribution after cleaning:")
for h, c in sorted(dist.items(), key=lambda x: -x[1]):
    logger.info("  %4d  %s", c, h)

sparse = [(h, c) for h, c in dist.items() if c < 5]
if sparse:
    logger.warning("\n⚠  Headings with < 5 examples (low accuracy for these):")
    for h, c in sorted(sparse, key=lambda x: x[1]):
        logger.warning("     %2d x %s", c, h)

if len(cleaned) < 50:
    logger.error("❌ Only %d sections. Add more proposal documents.", len(cleaned))
    exit(1)

with open(CLEANED_JSON, "w", encoding="utf-8") as f:
    json.dump(cleaned, f, ensure_ascii=False, indent=2)
logger.info("\n✅ Saved cleaned data: %s  (%d sections)", CLEANED_JSON, len(cleaned))

# ── Step 2: Build dataset ─────────────────────────────────────────────────────
logger.info("\n%s\nBUILDING DATASET\n%s", "="*60, "="*60)
random.seed(RANDOM_SEED)

positives = [(s["heading"], s["content"], 1) for s in cleaned]

by_heading = {}
for s in cleaned:
    by_heading.setdefault(s["heading"], []).append(s["content"])
headings_list = list(by_heading.keys())

negatives = []
for s in cleaned:
    others = [h for h in headings_list if h != s["heading"]]
    if not others:
        continue
    wrong_h = random.choice(others)
    wrong_c = random.choice(by_heading[wrong_h])
    negatives.append((s["heading"], wrong_c, 0))

min_count = min(len(positives), len(negatives))
positives = random.sample(positives, min_count)
negatives = random.sample(negatives, min_count)
all_data  = positives + negatives
random.shuffle(all_data)
logger.info("Positives: %d  Negatives: %d  Total: %d",
            len(positives), len(negatives), len(all_data))

# ── Step 3: Train ─────────────────────────────────────────────────────────────
logger.info("\n%s\nTRAINING\n%s", "="*60, "="*60)

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    logger.error("pip install sentence-transformers")
    exit(1)

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import classification_report, accuracy_score
except ImportError:
    logger.error("pip install scikit-learn")
    exit(1)

texts  = [f"{h} [SEP] {c[:512]}" for h, c, _ in all_data]
labels = [lbl for _, _, lbl in all_data]

logger.info("Loading embedder...")
t0 = time.time()
embedder = SentenceTransformer(EMBEDDER_NAME)

logger.info("Encoding %d pairs...", len(texts))
embeddings = embedder.encode(texts, show_progress_bar=True,
                             batch_size=32, convert_to_numpy=True)
logger.info("Done in %.1fs", time.time() - t0)

X_train, X_test, y_train, y_test = train_test_split(
    embeddings, labels, test_size=0.2,
    random_state=RANDOM_SEED, stratify=labels)

clf = LogisticRegression(max_iter=1000, C=1.0,
                         random_state=RANDOM_SEED, class_weight="balanced")
clf.fit(X_train, y_train)

y_pred   = clf.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

logger.info("\n%s\nRESULTS\n%s", "="*60, "="*60)
logger.info("Accuracy: %.1f%%", accuracy * 100)
print(classification_report(y_test, y_pred,
      target_names=["wrong_placement", "correct_placement"]))

cv = cross_val_score(clf, embeddings, labels, cv=5, scoring="f1")
logger.info("5-fold F1: mean=%.3f  std=%.3f", cv.mean(), cv.std())

with open(MODEL_PATH, "wb") as f:
    pickle.dump(clf, f)
logger.info("\n✅ Model saved: %s", MODEL_PATH)

if accuracy >= 0.85:
    logger.info("🎯 Excellent — model ready!")
elif accuracy >= 0.70:
    logger.info("✓  Good accuracy. Add more documents to improve.")
else:
    logger.warning("⚠  Low accuracy. Add more proposal documents to training data.")

logger.info("\nRestart server: uvicorn main:app --reload")
