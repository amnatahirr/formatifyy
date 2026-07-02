import re

# =====================================================
# IMPORT SHARED MODELS FROM image_relevance.py
# (BLIP already loaded there — don't reload)
# =====================================================
from services.image_relevance import generate_caption


# ======================================================================
# HOW MATCHING WORKS
# ======================================================================
# Each ETHICS_CATEGORY has TWO trigger lists:
#
#   "phrases" → multi-word strings matched as substrings in caption
#               e.g. "pile of pills" matches "a glass and a pile of pills"
#
#   "words"   → single words matched as WHOLE WORDS only (word boundary)
#               e.g. "gun" matches "a gun on table"
#               but NOT "begun" or "gunner"
#
# SAFE-CONTEXT OVERRIDES (two tiers):
#   SAFE_PHRASES → cancel flag for ANY category (multi-word = high specificity)
#   SAFE_WORDS   → cancel ONLY low-risk categories (weight < 1.0)
#                  High-risk (weight == 1.0) are NEVER cancelled by a single word
# ======================================================================


ETHICS_CATEGORIES = [

    # ══════════════════════════════════════════════════════════════════
    # ❌ CATEGORY 1 — NUDITY / SEXUAL CONTENT
    # Covers: explicit nudity, pornography, sexual acts, sexualized minors
    # ══════════════════════════════════════════════════════════════════
    {
        "id":     "sexual_content",
        "label":  "Nudity / Sexual Content",
        "weight": 1.0,

        "phrases": [
            # Explicit acts
            "sexual act", "sexual intercourse", "intimate act",
            "sex act", "having sex", "making love",
            # Nudity descriptions
            "naked person", "nude person", "naked man", "naked woman",
            "naked body", "nude body", "exposed body", "fully naked",
            "half naked", "semi nude", "partially nude",
            "topless woman", "topless man", "undressed person",
            "body exposed", "clothes removed",
            # Explicit/adult content
            "adult content", "explicit content", "pornographic content",
            "pornographic image", "erotic content", "erotic pose",
            "lingerie pose", "provocative pose", "suggestive pose",
            "sexually explicit", "sexual pose", "seductive pose",
            # Sexualized minors — absolute highest severity
            "naked child", "undressed child", "naked minor",
            "child in sexual", "sexualized child", "child exploitation",
            "minor in explicit", "child undressed", "minor undressed",
            "young child undressed", "child in inappropriate",
        ],

        "words": [
            "nude", "naked", "nudity", "undressed", "topless", "bottomless",
            "explicit", "pornographic", "pornography", "erotic", "erotica",
            "genitals", "genitalia", "penis", "vagina", "breasts", "buttocks",
            "sexual", "sexualized",
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # ❌ CATEGORY 2 — GRAPHIC VIOLENCE
    # Covers: physical assault, blood/gore, graphic injuries, dead bodies
    # ══════════════════════════════════════════════════════════════════
    {
        "id":     "graphic_violence",
        "label":  "Graphic Violence / Gore",
        "weight": 1.0,

        "phrases": [
            # Physical assault
            "beating a person", "punching a person", "kicking a person",
            "attacking a person", "assaulting a person", "hitting a person",
            "stabbing a person", "shooting a person", "strangling a person",
            "choking a person", "fighting in the street", "mob beating",
            "person being attacked", "violent attack",
            # Blood and injury
            "pool of blood", "covered in blood", "blood on the floor",
            "blood on the ground", "blood on their face", "blood on their body",
            "blood dripping", "blood stained", "bleeding from",
            "stab wound", "knife wound", "gunshot wound", "open wound",
            "severe injury", "graphic injury", "deep cut", "bleeding wound",
            "gaping wound", "wound bleeding",
            # Dead bodies (graphic)
            "dead body", "dead person", "dead man", "dead woman",
            "dead on the ground", "lying dead", "body on the floor",
            "pile of bodies", "mass casualties", "dead bodies",
        ],

        "words": [
            "gore", "gory", "decapitated", "decapitation",
            "mutilated", "mutilation", "severed", "dismembered",
            "dismemberment", "corpse", "tortured", "brutalized",
            "massacre", "slaughter", "beheaded", "lynched",
            "bleeding", "wounded",
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # ❌ CATEGORY 3 — HATE CONTENT
    # Covers: racist symbols, religious hate, hate slogans, extremist propaganda
    # ══════════════════════════════════════════════════════════════════
    {
        "id":     "hate_content",
        "label":  "Hate Content / Extremist Symbols",
        "weight": 0.95,

        "phrases": [
            # Racist / white supremacist
            "white supremacy", "white supremacist", "white power symbol",
            "burning cross", "cross burning", "racist symbol",
            "racial slur", "hate symbol", "hate crime",
            # Religious hate symbols
            "religious hate", "anti-semitic symbol",
            "religious extremism", "extremist symbol", "extremist propaganda",
            "terrorist propaganda", "jihadi propaganda",
            # Hate groups / acts
            "neo nazi", "neo-nazi", "far right extremist",
            "nazi salute", "hate gesture", "hate slogan",
            "white power rally", "hate group gathering",
            # Extremist imagery
            "isis flag", "terrorist flag", "extremist flag",
        ],

        "words": [
            "swastika", "nazi", "kkk",
            "antisemitic", "antisemitism",
            "islamophobic", "xenophobic",
            "genocidal", "extremist",
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # ❌ CATEGORY 4 — SELF-HARM / SUICIDE
    # Covers: suicide attempts, cutting/self-harm visuals
    # ══════════════════════════════════════════════════════════════════
    {
        "id":     "self_harm",
        "label":  "Self-Harm / Suicide",
        "weight": 1.0,

        "phrases": [
            # Cutting / self-harm visuals
            "self harm", "self-harm", "cutting wrist", "wrist cuts",
            "wrist scars", "cutting arm", "cutting skin",
            "self inflicted", "harming themselves", "hurting themselves",
            "burning themselves", "self mutilation", "razor on wrist",
            # Suicide attempts
            "hanging themselves", "hanging person", "hanging from a rope",
            "attempting suicide", "suicide attempt",
            "about to jump", "jumping off a bridge", "jumping off a building",
            "about to hang", "noose around neck",
            # Overdose scene
            "lying unconscious after overdose",
            "taking too many pills", "pill overdose", "drug overdose scene",
            "unconscious from drugs",
        ],

        "words": [
            "suicide", "suicidal", "self-mutilation", "noose",
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # ❌ CATEGORY 5 — DRUG ABUSE / ILLEGAL ACTIVITY
    # Covers: drug consumption, illegal weapons usage, criminal acts
    # ══════════════════════════════════════════════════════════════════
    {
        "id":     "drug_abuse_illegal",
        "label":  "Drug Abuse / Illegal Activity",
        "weight": 0.85,

        "phrases": [
            # Drug consumption visuals
            "injecting drugs", "drug injection", "shooting up drugs",
            "snorting cocaine", "snorting drugs", "snorting a line",
            "smoking crack", "smoking meth", "smoking heroin",
            "using drugs", "drug use in action", "drug paraphernalia in use",
            "preparing drugs", "rolling drugs", "lighting a crack pipe",
            # Alcohol + pills (overdose setup)
            "pile of pills", "glass of alcohol next to pills",
            "alcohol and pills", "pills and alcohol",
            "drugs and alcohol", "alcohol next to a pile of pills",
            "alcohol next to pills", "mixing drugs", "drug and alcohol",
            "surrounded by pills", "pills spilled out",
            # Criminal acts in action
            "robbing a person", "robbing a store", "armed robbery",
            "breaking into a building", "committing a crime",
            "criminal act in", "stealing from",
            "holding someone at gunpoint", "mugging a person",
        ],

        "words": [
            "heroin", "cocaine", "methamphetamine", "meth",
            "fentanyl", "narcotics", "overdose",
            "marijuana", "cannabis",
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # ❌ CATEGORY 5b — WEAPONS / DANGEROUS OBJECTS
    # Sub-category under illegal activity — weapons presence or illegal use
    # ══════════════════════════════════════════════════════════════════
    {
        "id":     "weapons",
        "label":  "Weapons / Dangerous Objects",
        "weight": 0.90,

        "phrases": [
            # Threatening / illegal use
            "pointing a gun", "gun pointed at", "aiming at a person",
            "holding a gun to", "at gunpoint", "execution style",
            "threatening with a knife", "weapon aimed at",
            "holding a knife to someone", "knife at throat",
            "armed and threatening",
            # Display / collection (any presence)
            "a bunch of guns", "bunch of guns",
            "guns and a knife", "guns and knives", "knives and guns",
            "pile of guns", "collection of guns",
            "guns on a table", "weapons on a table",
            "table with guns", "table with weapons",
            "table full of guns", "table full of weapons",
            "loaded weapons", "arsenal of weapons",
            "several guns", "multiple guns",
            "row of guns", "display of guns", "display of weapons",
            "firearms laid out", "weapons laid out",
        ],

        "words": [
            "gun", "guns", "firearm", "firearms",
            "pistol", "pistols", "rifle", "rifles",
            "shotgun", "shotguns", "revolver", "revolvers",
            "handgun", "handguns", "weapon", "weapons",
            "knife", "knives", "machete", "grenade", "grenades",
            "ammunition", "bullets", "explosive", "explosives",
            "bomb", "bombs", "dagger", "daggers", "bayonet",
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # ❌ CATEGORY 6 — OFFENSIVE / OBSCENE CONTENT
    # Covers: abusive gestures, explicit adult cartoons, disturbing imagery
    # ══════════════════════════════════════════════════════════════════
    {
        "id":     "offensive_content",
        "label":  "Offensive / Obscene Content",
        "weight": 0.85,

        "phrases": [
            # Abusive gestures
            "middle finger", "obscene gesture", "rude gesture",
            "offensive gesture", "vulgar gesture", "flipping off",
            # Disturbing imagery
            "disturbing image", "deeply disturbing", "shock image",
            "grotesque image", "horrifying image", "deeply offensive",
            "graphic disturbing",
            # Explicit adult cartoons / hentai
            "explicit cartoon", "adult cartoon", "hentai",
            "anime porn", "animated porn", "explicit animation",
            "adult anime", "explicit adult illustration",
            # Animal abuse
            "animal abuse", "animal cruelty",
            "torturing an animal", "killing an animal graphically",
            "graphic animal violence",
        ],

        "words": [
            "obscene", "grotesque", "vulgar",
            "depraved", "hentai", "bestiality",
        ],
    },

]


# ======================================================================
# ✅ SAFE-CONTEXT OVERRIDES
# ======================================================================
# These cover all ETHICAL image types from the specification:
#   Educational diagrams, Professional photographs, Academic charts,
#   Logos, Nature images, Architecture, Business visuals,
#   Non-graphic medical diagrams, Non-violent news images
#
# SAFE_PHRASES → cancel flag for ANY category (high specificity, multi-word)
# SAFE_WORDS   → cancel ONLY low-risk categories (weight < 1.0)
#                weight == 1.0 categories are NEVER word-overridden
# ======================================================================

SAFE_PHRASES = [

    # ── Educational diagrams & academic charts ────────────────────────
    "blood vessels", "blood vessel", "blood flow", "blood cells",
    "blood cell", "blood type", "blood pressure", "blood test",
    "blood circulation", "blood donation", "blood sample",
    "red blood cells", "white blood cells",
    "anatomy diagram", "medical diagram", "anatomical illustration",
    "anatomy chart", "academic chart", "educational diagram",
    "educational chart", "educational illustration", "educational poster",
    "cross section diagram", "labeled diagram",
    "x-ray image", "mri scan", "ct scan", "ultrasound image",
    "surgical diagram", "medical illustration",
    "health infographic", "health chart", "health diagram",
    # Anti-drug / public health awareness (educational, not glorifying)
    "drug statistics", "substance abuse statistics",
    "awareness campaign", "public health campaign",
    "anti-drug campaign", "anti-drug poster",
    "anti-violence campaign", "drug awareness",

    # ── Non-graphic medical diagrams ──────────────────────────────────
    "surgical instrument", "medical instrument", "medical equipment",
    "hospital diagram", "clinical diagram",

    # ── Logos ──────────────────────────────────────────────────────────
    "company logo", "brand logo", "corporate logo",
    "logo design", "logo on white", "logo on background",

    # ── Nature images ─────────────────────────────────────────────────
    "nature photograph", "wildlife photograph", "landscape photograph",
    "nature scene", "wildlife scene", "forest photograph",
    "mountain landscape", "ocean photograph", "sunset photograph",
    "flower photograph", "animal in the wild", "birds in",

    # ── Architecture ──────────────────────────────────────────────────
    "architectural photograph", "building photograph",
    "architecture design", "interior design", "exterior of a building",
    "blueprint schematic", "building blueprint", "floor plan",

    # ── Business-related visuals ──────────────────────────────────────
    "business infographic", "business chart", "business diagram",
    "corporate presentation", "professional photograph",
    "office photograph", "team photograph", "business meeting",
    "bar chart", "pie chart", "line graph", "data visualization",

    # ── Weapons in historical / educational / safe context ────────────
    "historical weapons", "ancient weapons", "medieval weapons",
    "antique weapons", "museum exhibit", "arms museum",
    "historical artifact", "weapons in history", "weapons museum",
    "toy gun", "toy knife", "toy weapon", "nerf gun",
    "water gun", "water pistol", "squirt gun",
    "law enforcement training", "military history exhibit",

    # ── Entertainment / fiction (clearly labelled) ────────────────────
    "video game", "video games", "game screenshot", "computer game",
    "gaming screenshot", "movie poster", "film poster",
    "fictional character", "animated character",
    "comic book", "graphic novel illustration",

    # ── Non-violent news images ───────────────────────────────────────
    "news photograph", "news photo", "press photo",
    "documentary image", "non violent protest",
    "protest march", "peaceful protest",
]

SAFE_WORDS = [
    # ✅ Ethical visual context indicators
    # Only cancel LOW-RISK (weight < 1.0) categories
    # High-risk (nudity, violence, self-harm) are NEVER overridden by these

    # Diagrams / charts / academic
    "diagram", "chart", "graph", "illustration", "infographic",
    "flowchart", "schematic", "blueprint", "map",

    # Medical / educational
    "anatomy", "anatomical", "medical", "educational", "academic",
    "clinical", "scientific",

    # Historical / museum
    "historical", "antique", "vintage", "museum",
    "exhibit", "exhibition", "artifact",

    # Art / culture
    "sculpture", "statue", "monument",
    "painting", "artwork", "mural", "fresco",
    "cartoon", "animated", "animation", "illustrated",

    # Professional / business
    "logo", "icon", "emblem", "badge", "banner", "poster", "flag",
    "professional", "corporate", "business",

    # Nature / architecture
    "landscape", "architecture", "architectural",
    "nature", "wildlife",
]


# ======================================================================
# MATCHING ENGINE
# ======================================================================

def _normalize(text: str) -> str:
    """Lowercase, remove punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _match_phrases(caption_norm: str, phrases: list) -> list:
    """Substring match — all phrases found in caption."""
    return [p for p in phrases if p in caption_norm]


def _match_words(caption_norm: str, words: list) -> list:
    """Whole-word match — avoids partial word matches."""
    return [
        w for w in words
        if re.search(rf"\b{re.escape(w)}\b", caption_norm)
    ]


def _is_safe_context(caption_norm: str, category_weight: float) -> bool:
    """
    Returns True if safe context cancels the unethical flag.

    Rule 1: SAFE_PHRASES always override any category
            (multi-word = very specific = trustworthy)

    Rule 2: SAFE_WORDS only override LOW-RISK categories (weight < 1.0)
            A single word like 'diagram' cannot excuse nudity/violence/self-harm
            because those are weight == 1.0 categories.
    """
    # Rule 1 — phrase match always overrides
    if any(p in caption_norm for p in SAFE_PHRASES):
        return True

    # Rule 2 — word match only for low-risk categories
    if category_weight < 1.0:
        if any(re.search(rf"\b{re.escape(w)}\b", caption_norm) for w in SAFE_WORDS):
            return True

    return False


# ======================================================================
# MAIN SCORER
# ======================================================================

def score_caption_ethics(caption: str) -> dict:
    """
    Score a BLIP caption against the full ethics taxonomy.

    Returns
    -------
    {
        "is_unethical"    : bool,
        "confidence"      : float,      # 0.0 – 1.0
        "category_id"     : str | None,
        "category_label"  : str | None,
        "matched_phrases" : list[str],
        "safe_override"   : bool,
        "caption"         : str,
    }
    """
    caption_norm  = _normalize(caption)
    best_category = None
    best_weight   = 0.0
    all_matches   = []

    for cat in ETHICS_CATEGORIES:
        phrase_hits = _match_phrases(caption_norm, cat.get("phrases", []))
        word_hits   = _match_words(caption_norm,   cat.get("words",   []))
        hits        = phrase_hits + word_hits

        if hits:
            all_matches.extend(hits)
            if cat["weight"] > best_weight:
                best_weight   = cat["weight"]
                best_category = cat

    # ── No trigger hit → ethical ──────────────────────────────────────
    if best_category is None:
        return {
            "is_unethical":    False,
            "confidence":      0.0,
            "category_id":     None,
            "category_label":  None,
            "matched_phrases": [],
            "safe_override":   False,
            "caption":         caption,
        }

    # ── Safe-context override ─────────────────────────────────────────
    if _is_safe_context(caption_norm, best_category["weight"]):
        return {
            "is_unethical":    False,
            "confidence":      0.0,
            "category_id":     best_category["id"],
            "category_label":  best_category["label"],
            "matched_phrases": list(set(all_matches)),
            "safe_override":   True,
            "caption":         caption,
        }

    # ── Confidence score ──────────────────────────────────────────────
    # Base = category weight
    # +0.05 per additional unique match (max +0.25), capped at 1.0
    unique_matches = list(set(all_matches))
    match_bonus    = min(len(unique_matches) - 1, 5) * 0.05
    confidence     = min(best_weight + match_bonus, 1.0)

    return {
        "is_unethical":    True,
        "confidence":      round(confidence, 4),
        "category_id":     best_category["id"],
        "category_label":  best_category["label"],
        "matched_phrases": unique_matches,
        "safe_override":   False,
        "caption":         caption,
    }


# ======================================================================
# MAIN ANALYZER
# ======================================================================

def analyze_image_ethics(image_path: str) -> dict:
    """
    Full ethics analysis for a single image.
    Step 1: Generate BLIP caption.
    Step 2: Score caption against taxonomy.
    """
    print(f"\n🔍 Ethics check: {image_path}")

    caption = generate_caption(image_path)
    print(f"📌 Caption: {caption}")

    ethics = score_caption_ethics(caption)

    result = {
        "caption":         caption,
        "is_unethical":    ethics["is_unethical"],
        "confidence":      ethics["confidence"],
        "category_id":     ethics["category_id"],
        "category_label":  ethics["category_label"],
        "matched_phrases": ethics["matched_phrases"],
        "safe_override":   ethics["safe_override"],
        "image_path":      image_path,
    }

    if result["is_unethical"]:
        print(f"🚨 UNETHICAL — {result['category_label']} | "
              f"confidence: {result['confidence']} | "
              f"matches: {result['matched_phrases']}")
    elif result["safe_override"]:
        print(f"✅ ETHICAL (safe override) — trigger present but context is safe | "
              f"matches: {result['matched_phrases']}")
    else:
        print(f"✅ ETHICAL — no unethical content detected")

    return result


# ======================================================================
# BATCH HELPERS
# ======================================================================

def analyze_all_images_ethics(image_contexts: list) -> list:
    """Run ethics check on all images from extract_images_with_context()."""
    return [analyze_image_ethics(ctx["image_path"]) for ctx in image_contexts]


def get_unethical_images(image_contexts: list) -> list:
    """Return only flagged images from a document's image list."""
    return [r for r in analyze_all_images_ethics(image_contexts) if r["is_unethical"]]


# ======================================================================
# TEST SUITE  —  run: python services/image_ethics.py
# ======================================================================

if __name__ == "__main__":

    tests = [
        # ── caption ──────────────────────────────────────────────── expected

        # ❌ 1. NUDITY / SEXUAL CONTENT
        ("a naked person standing in a room",                      "UNETHICAL"),
        ("a woman in a provocative pose with exposed body",        "UNETHICAL"),
        ("two people in a sexual act on a bed",                    "UNETHICAL"),
        ("a topless woman posing for a photo",                     "UNETHICAL"),
        ("a naked child standing near a pool",                     "UNETHICAL"),

        # ❌ 2. GRAPHIC VIOLENCE
        ("a man bleeding from a stab wound on the ground",         "UNETHICAL"),
        ("a person beating another person on the street",          "UNETHICAL"),
        ("a dead body lying on the floor covered in blood",        "UNETHICAL"),
        ("a decapitated head on the ground",                       "UNETHICAL"),
        ("a pool of blood on the floor",                           "UNETHICAL"),

        # ❌ 3. HATE CONTENT
        ("a swastika symbol painted on a wall",                    "UNETHICAL"),
        ("a person performing a nazi salute",                      "UNETHICAL"),
        ("a white supremacy rally with banners",                   "UNETHICAL"),
        ("a burning cross in a field at night",                    "UNETHICAL"),

        # ❌ 4. SELF-HARM / SUICIDE
        ("a person cutting their wrist with a razor blade",        "UNETHICAL"),
        ("a person hanging from a rope in a room",                 "UNETHICAL"),
        ("a person attempting suicide by jumping off a bridge",    "UNETHICAL"),
        ("wrist cuts and scars visible on a person",               "UNETHICAL"),

        # ❌ 5. DRUG ABUSE / ILLEGAL ACTIVITY
        ("a person injecting drugs into their arm",                "UNETHICAL"),
        ("a glass of alcohol next to a pile of pills",             "UNETHICAL"),
        ("a person snorting cocaine from a table",                 "UNETHICAL"),
        ("a person robbing a store with a weapon",                 "UNETHICAL"),

        # ❌ 5b. WEAPONS
        ("a table with a bunch of guns and a knife",               "UNETHICAL"),
        ("a man holding a gun pointing at someone",                "UNETHICAL"),
        ("several rifles displayed on a rack",                     "UNETHICAL"),
        ("a pistol and a rifle on a wooden surface",               "UNETHICAL"),
        ("a knife lying on a table",                               "UNETHICAL"),

        # ❌ 6. OFFENSIVE / OBSCENE
        ("a person showing the middle finger",                     "UNETHICAL"),
        ("an explicit adult cartoon with nudity",                  "UNETHICAL"),
        ("a hentai illustration with explicit content",            "UNETHICAL"),

        # ✅ ETHICAL — Educational diagrams
        ("a diagram of blood vessels in the human body",           "ETHICAL"),
        ("a medical diagram showing blood flow through the heart", "ETHICAL"),
        ("an anatomy illustration of the human chest",             "ETHICAL"),
        ("an educational diagram of the solar system",             "ETHICAL"),

        # ✅ ETHICAL — Academic charts
        ("a bar chart showing quarterly sales results",            "ETHICAL"),
        ("a pie chart of global energy consumption",               "ETHICAL"),
        ("a chart showing drug usage statistics over time",        "ETHICAL"),
        ("a line graph showing population growth",                 "ETHICAL"),

        # ✅ ETHICAL — Professional photographs
        ("a professional photograph of a business meeting",        "ETHICAL"),
        ("a news photograph of a peaceful protest march",          "ETHICAL"),
        ("a documentary image of a relief camp",                   "ETHICAL"),

        # ✅ ETHICAL — Logos
        ("a company logo on a white background",                   "ETHICAL"),
        ("a brand logo displayed on a product",                    "ETHICAL"),

        # ✅ ETHICAL — Nature images
        ("a nature photograph of a forest at sunrise",             "ETHICAL"),
        ("a wildlife photograph of lions in the savanna",          "ETHICAL"),
        ("a landscape photograph of snow-capped mountains",        "ETHICAL"),

        # ✅ ETHICAL — Architecture
        ("an architectural photograph of a modern building",       "ETHICAL"),
        ("a blueprint schematic of a building layout",             "ETHICAL"),

        # ✅ ETHICAL — Business visuals
        ("a business infographic showing company growth",          "ETHICAL"),
        ("a corporate presentation slide with graphs",             "ETHICAL"),

        # ✅ ETHICAL — Non-graphic medical
        ("an x-ray image of a broken bone",                        "ETHICAL"),
        ("a clinical diagram of the human heart",                  "ETHICAL"),

        # ✅ ETHICAL — Safe weapons context
        ("a historical weapons exhibit in a museum",               "ETHICAL"),
        ("a toy gun lying on a colorful playmat",                  "ETHICAL"),
        ("a painting of an ancient sword on display",              "ETHICAL"),
        ("a cartoon character holding a water gun",                "ETHICAL"),
        ("an anti-drug awareness campaign poster",                 "ETHICAL"),
    ]

    print("\n" + "=" * 72)
    print("   IMAGE ETHICS DETECTION — COMPREHENSIVE TEST SUITE")
    print("=" * 72)

    passed = 0
    failed = 0

    for caption, expected in tests:
        result  = score_caption_ethics(caption)
        actual  = "UNETHICAL" if result["is_unethical"] else "ETHICAL"
        ok      = (actual == expected)
        icon    = "✅" if ok else "❌"
        passed += 1 if ok else 0
        failed += 0 if ok else 1

        print(f"\n  {icon} [{expected:9s}]  {caption}")
        if not ok:
            print(f"       ⚠️  Got      : {actual}")
        if result["matched_phrases"]:
            print(f"       Matches  : {result['matched_phrases']}")
        if result["safe_override"]:
            print(f"       Override : safe context applied")
        if result["is_unethical"]:
            print(f"       Category : {result['category_label']} "
                  f"(confidence {result['confidence']})")

    print("\n" + "=" * 72)
    print(f"   RESULTS :  ✅ {passed} passed   ❌ {failed} failed   "
          f"({len(tests)} total)")
    print("=" * 72)