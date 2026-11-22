"""
functions/image_ethics.py — Local image ethics / appropriateness detector.

Runs fully offline (no Claude / GPT / Gemini APIs).

Approach (ETHICS_ENGINE="local", default)
-----------------------------------------
1. Trained head (functions/ethics_head.py): frozen CLIP ViT-B/32 image embedding
   -> LogisticRegression trained on our own data (transfer learning / linear
   probing). Classes: safe, sexual, weapons_violence.
   Model: ml_weights/ethics_head_v6.joblib (brain/ml/train_ethics_v6.py),
   metrics: brain/ml/results/ethics/metrics/comparison.md.
2. Keyword engine: BLIP caption scored against an ethics taxonomy (phrases,
   whole words, co-occurrence combos, safe-context overrides). Covers classes
   with no training data: drugs, self-harm, hate, offensive.
3. Decision (_analyze_local):
   - head p_unsafe >= 0.5               -> unsafe (head category)
   - keyword hit outside head's classes -> unsafe (keyword category)
   - 0.4 <= p_unsafe < 0.5 + keyword hit -> unsafe (both agree)
   - otherwise                          -> safe

ETHICS_ENGINE="keyword" runs the older BLIP + taxonomy engine alone (baseline).

Output contract (module API for callers / tests)
------------------------------------------------
{
  "ethical": false,
  "category": "Weapons / Violence",
  "confidence": 0.96
}

Pipeline issue dicts retain Formatify's existing schema for the Flutter UI.
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any, Dict, List

from models import Batch
from functions.local_vision import generate_caption_from_b64, image_fingerprint
from functions.ethics_head import predict_unsafe

# "local"   = trained head + keyword engine (main)
# "keyword" = purana BLIP + taxonomy engine (baseline)
ETHICS_ENGINE = os.getenv("ETHICS_ENGINE", "local")
HEAD_HIGH = 0.5   # is se upar: head ka faisla pakka (v6 ke liye 6-seed eval se chuna)
HEAD_LOW = 0.4    # is se neeche: head kehta hai safe
HEAD_LABELS = {
    "sexual": "Nudity / Sexual Content",
    "weapons_violence": "Weapons / Violence",
}
# jin categories ko head khud sambhalta hai
HEAD_COVERED_IDS = {"sexual_content", "graphic_violence", "weapons"}


# ======================================================================
# ETHICS CATEGORIES
# Each entry has TWO trigger lists:
#   "phrases" → multi-word substring matches in the caption
#   "words"   → whole-word matches only (word boundary)
# ======================================================================

ETHICS_CATEGORIES = [

    {
        "id": "sexual_content",
        "label": "Nudity / Sexual Content",
        "weight": 1.0,
        "phrases": [
            "sexual act", "sexual intercourse", "intimate act",
            "sex act", "having sex", "making love",
            "naked person", "nude person", "naked man", "naked woman",
            "naked body", "nude body", "exposed body", "fully naked",
            "half naked", "semi nude", "partially nude",
            "topless woman", "topless man", "undressed person",
            "body exposed", "clothes removed",
            "adult content", "explicit content", "pornographic content",
            "pornographic image", "erotic content", "erotic pose",
            "lingerie pose", "provocative pose", "suggestive pose",
            "sexually explicit", "sexual pose", "seductive pose",
            "naked child", "undressed child", "naked minor",
            "child in sexual", "sexualized child", "child exploitation",
            "minor in explicit", "child undressed", "minor undressed",
        ],
        "words": [
            "nude", "naked", "nudity", "undressed", "topless", "bottomless",
            "explicit", "pornographic", "pornography", "erotic", "erotica",
            "genitals", "genitalia", "penis", "vagina", "breasts", "buttocks",
            "sexual", "sexualized",
        ],
    },

    {
        "id": "graphic_violence",
        "label": "Violence / Gore",
        "weight": 1.0,
        "phrases": [
            "beating a person", "punching a person", "kicking a person",
            "attacking a person", "assaulting a person", "hitting a person",
            "stabbing a person", "shooting a person", "strangling a person",
            "choking a person", "fighting in the street", "mob beating",
            "person being attacked", "violent attack",
            "pool of blood", "covered in blood", "blood on the floor",
            "blood on the ground", "blood on their face", "blood on their body",
            "blood dripping", "blood stained", "bleeding from",
            "stab wound", "knife wound", "gunshot wound", "open wound",
            "severe injury", "graphic injury", "deep cut", "bleeding wound",
            "gaping wound", "wound bleeding",
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

    {
        "id": "hate_content",
        "label": "Hate / Extremist Symbols",
        "weight": 0.95,
        "phrases": [
            "white supremacy", "white supremacist", "white power symbol",
            "burning cross", "cross burning", "racist symbol",
            "racial slur", "hate symbol", "hate crime",
            "religious hate", "anti-semitic symbol",
            "religious extremism", "extremist symbol", "extremist propaganda",
            "terrorist propaganda", "jihadi propaganda",
            "neo nazi", "neo-nazi", "far right extremist",
            "nazi salute", "hate gesture", "hate slogan",
            "white power rally", "hate group gathering",
            "isis flag", "terrorist flag", "extremist flag",
        ],
        "words": [
            "swastika", "nazi", "kkk",
            "antisemitic", "antisemitism",
            "islamophobic", "xenophobic",
            "genocidal", "extremist",
        ],
    },

    {
        "id": "self_harm",
        "label": "Self-Harm / Suicide",
        "weight": 1.0,
        "phrases": [
            "self harm", "self-harm", "cutting wrist", "wrist cuts",
            "wrist scars", "cutting arm", "cutting skin",
            "self inflicted", "harming themselves", "hurting themselves",
            "burning themselves", "self mutilation", "razor on wrist",
            "hanging themselves", "hanging person", "hanging from a rope",
            "attempting suicide", "suicide attempt",
            "about to jump", "jumping off a bridge", "jumping off a building",
            "about to hang", "noose around neck",
            "lying unconscious after overdose",
            "taking too many pills", "pill overdose", "drug overdose scene",
            "unconscious from drugs",
        ],
        "words": [
            "suicide", "suicidal", "self-mutilation", "noose",
        ],
    },

    {
        "id": "drugs",
        "label": "Drugs",
        "weight": 0.85,
        "phrases": [
            "injecting drugs", "drug injection", "shooting up drugs",
            "snorting cocaine", "snorting drugs", "snorting a line",
            "smoking crack", "smoking meth", "smoking heroin",
            "using drugs", "drug use in action", "drug paraphernalia in use",
            "preparing drugs", "rolling drugs", "lighting a crack pipe",
            "pile of pills", "glass of alcohol next to pills",
            "alcohol and pills", "pills and alcohol",
            "drugs and alcohol", "alcohol next to a pile of pills",
            "alcohol next to pills", "mixing drugs", "drug and alcohol",
            "surrounded by pills", "pills spilled out",
            "alcohol with pills", "pills with alcohol",
        ],
        # co-occurrence: har group ka koi ek lafz caption mein ho (kisi bhi tarteeb mein)
        # e.g. "a glass of alcohol with pills" -> pills + alcohol
        "combos": [
            [["pill", "pills", "tablets", "capsules"],
             ["alcohol", "beer", "wine", "vodka", "whiskey", "liquor", "drink", "drinks"]],
            [["pill", "pills", "tablets", "capsules", "powder", "drugs", "drug"],
             ["syringe", "syringes", "needle", "needles", "spoon", "lighter"]],
            [["white powder", "powder"],
             ["line", "lines", "rolled", "straw", "credit card", "razor"]],
            [["bong", "joint", "joints", "blunt"],
             ["smoking", "smoke", "lighter", "weed"]],
        ],
        "words": [
            "heroin", "cocaine", "methamphetamine", "meth",
            "fentanyl", "narcotics", "overdose",
            "marijuana", "cannabis",
        ],
    },

    {
        "id": "weapons",
        "label": "Weapons",
        "weight": 0.90,
        "phrases": [
            "pointing a gun", "gun pointed at", "aiming at a person",
            "holding a gun to", "at gunpoint", "execution style",
            "threatening with a knife", "weapon aimed at",
            "holding a knife to someone", "knife at throat",
            "armed and threatening",
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

    {
        "id": "offensive_content",
        "label": "Offensive / Obscene Content",
        "weight": 0.85,
        "phrases": [
            "middle finger", "obscene gesture", "rude gesture",
            "offensive gesture", "vulgar gesture", "flipping off",
            "disturbing image", "deeply disturbing", "shock image",
            "grotesque image", "horrifying image", "deeply offensive",
            "graphic disturbing",
            "explicit cartoon", "adult cartoon", "hentai",
            "anime porn", "animated porn", "explicit animation",
            "adult anime", "explicit adult illustration",
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


SAFE_PHRASES = [
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
    "drug statistics", "substance abuse statistics",
    "awareness campaign", "public health campaign",
    "anti-drug campaign", "anti-drug poster",
    "anti-violence campaign", "drug awareness",
    "surgical instrument", "medical instrument", "medical equipment",
    "hospital diagram", "clinical diagram",
    "company logo", "brand logo", "corporate logo",
    "logo design", "logo on white", "logo on background",
    "nature photograph", "wildlife photograph", "landscape photograph",
    "nature scene", "wildlife scene", "forest photograph",
    "mountain landscape", "ocean photograph", "sunset photograph",
    "flower photograph", "animal in the wild", "birds in",
    "architectural photograph", "building photograph",
    "architecture design", "interior design", "exterior of a building",
    "blueprint schematic", "building blueprint", "floor plan",
    "business infographic", "business chart", "business diagram",
    "corporate presentation", "professional photograph",
    "office photograph", "team photograph", "business meeting",
    "bar chart", "pie chart", "line graph", "data visualization",
    "historical weapons", "ancient weapons", "medieval weapons",
    "antique weapons", "museum exhibit", "arms museum",
    "historical artifact", "weapons in history", "weapons museum",
    "toy gun", "toy knife", "toy weapon", "nerf gun",
    "water gun", "water pistol", "squirt gun",
    "law enforcement training", "military history exhibit",
    "video game", "video games", "game screenshot", "computer game",
    "gaming screenshot", "movie poster", "film poster",
    "fictional character", "animated character",
    "comic book", "graphic novel illustration",
    "news photograph", "news photo", "press photo",
    "documentary image", "non violent protest",
    "protest march", "peaceful protest",
]

SAFE_WORDS = [
    "diagram", "chart", "graph", "illustration", "infographic",
    "flowchart", "schematic", "blueprint", "map",
    "anatomy", "anatomical", "medical", "educational", "academic",
    "clinical", "scientific",
    "historical", "antique", "vintage", "museum",
    "exhibit", "exhibition", "artifact",
    "sculpture", "statue", "monument",
    "painting", "artwork", "mural", "fresco",
    "cartoon", "animated", "animation", "illustrated",
    "logo", "icon", "emblem", "badge", "banner", "poster", "flag",
    "professional", "corporate", "business",
    "landscape", "architecture", "architectural",
    "nature", "wildlife",
]


# ======================================================================
# MATCHING ENGINE
# ======================================================================

def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _match_phrases(caption_norm: str, phrases: list) -> list:
    return [p for p in phrases if p in caption_norm]


def _match_words(caption_norm: str, words: list) -> list:
    return [
        w for w in words
        if re.search(rf"\b{re.escape(w)}\b", caption_norm)
    ]


def _match_combos(caption_norm: str, combos: list) -> list:
    """Each combo is a list of word-groups; it fires when every group has a hit."""
    hits = []
    for groups in combos:
        found = []
        for group in groups:
            hit = next((w for w in group
                        if re.search(rf"\b{re.escape(w)}\b", caption_norm)), None)
            if hit is None:
                break
            found.append(hit)
        else:
            hits.append(" + ".join(found))
    return hits


def _is_safe_context(caption_norm: str, category_weight: float) -> bool:
    if any(p in caption_norm for p in SAFE_PHRASES):
        return True
    if category_weight < 1.0:
        if any(re.search(rf"\b{re.escape(w)}\b", caption_norm) for w in SAFE_WORDS):
            return True
    return False


def score_caption_ethics(caption: str) -> dict:
    """
    Score a BLIP caption against the ethics taxonomy.

    Returns internal scoring dict (used by analyze_image_ethics).
    """
    caption_norm = _normalize(caption)
    best_category = None
    best_weight = 0.0
    all_matches: list = []

    for cat in ETHICS_CATEGORIES:
        phrase_hits = _match_phrases(caption_norm, cat.get("phrases", []))
        word_hits = _match_words(caption_norm, cat.get("words", []))
        combo_hits = _match_combos(caption_norm, cat.get("combos", []))
        hits = phrase_hits + word_hits + combo_hits
        if hits:
            all_matches.extend(hits)
            if cat["weight"] > best_weight:
                best_weight = cat["weight"]
                best_category = cat

    if best_category is None:
        return {
            "is_unethical": False,
            "confidence": 0.0,
            "category_id": None,
            "category_label": "Safe",
            "matched_phrases": [],
            "safe_override": False,
            "caption": caption,
        }

    if _is_safe_context(caption_norm, best_category["weight"]):
        return {
            "is_unethical": False,
            "confidence": 0.0,
            "category_id": best_category["id"],
            "category_label": "Safe",
            "matched_phrases": list(set(all_matches)),
            "safe_override": True,
            "caption": caption,
        }

    unique_matches = list(set(all_matches))
    match_bonus = min(len(unique_matches) - 1, 5) * 0.05
    confidence = min(best_weight + match_bonus, 1.0)

    return {
        "is_unethical": True,
        "confidence": round(confidence, 4),
        "category_id": best_category["id"],
        "category_label": best_category["label"],
        "matched_phrases": unique_matches,
        "safe_override": False,
        "caption": caption,
    }


# User ko dikhne wala jumla (frontend ethics card). Technical tafseel debug_reason mein.
_FRIENDLY_REASON = {
    "Nudity / Sexual Content": "This image appears to contain nudity or sexual content.",
    "Weapons / Violence": "This image appears to show weapons or violence.",
    "Weapons": "This image appears to show weapons.",
    "Violence / Gore": "This image appears to show violence or gore.",
    "Drugs": "This image appears to show drugs or drug use.",
    "Self-Harm / Suicide": "This image appears to depict self-harm or suicide.",
    "Hate / Extremist Symbols": "This image appears to contain hate or extremist symbols.",
    "Offensive / Obscene Content": "This image appears to contain offensive or obscene content.",
}


def _friendly_reason(ethical: bool, category: str, confidence: float) -> str:
    if ethical:
        return "No inappropriate content was detected in this image."
    text = _FRIENDLY_REASON.get(category, "This image appears to contain inappropriate content.")
    return (f"{text} Detection confidence: {round(100 * confidence)}%. Images in an "
            f"academic report should be appropriate for all readers; please replace it.")


def _analyze_local(b64: str, caption: str | None = None) -> dict:
    """Trained head decides sexual / weapons / violence; keyword engine covers
    self-harm, drugs, hate, offensive and breaks ties in the borderline band."""
    head = predict_unsafe(b64)
    p = head["p_unsafe"]
    if caption is None:
        caption = generate_caption_from_b64(b64, cache_key=image_fingerprint(b64))
    kw = score_caption_ethics(caption)
    kw_unsafe = kw["is_unethical"]
    kw_covered = kw.get("category_id") in HEAD_COVERED_IDS
    borderline = HEAD_LOW <= p < HEAD_HIGH

    if p >= HEAD_HIGH:
        engine, ethical = "head", False
        category, confidence = HEAD_LABELS[head["top_class"]], p
    elif kw_unsafe and not kw_covered:
        engine, ethical = "keyword", False
        category, confidence = kw["category_label"], float(kw["confidence"])
    elif borderline and kw_unsafe:
        engine, ethical = "head+keyword", False
        category, confidence = kw["category_label"], max(p, float(kw["confidence"]))
    else:
        engine, ethical = "head", True
        category, confidence = "Safe", 1.0 - p

    debug_reason = (f"[{engine}] p_unsafe={p:.2f}, head={head['top_class']}, "
                    f"caption='{caption}', keyword_matches={kw.get('matched_phrases', [])}")
    reason = _friendly_reason(ethical, category, confidence)
    print(f"[image_ethics] {'✅ ETHICAL' if ethical else '🚨 UNETHICAL'} | "
          f"engine={engine} | category={category} | conf={confidence:.2f} | "
          f"borderline={borderline} | {debug_reason}")
    return {
        "ethical": ethical,
        "category": category,
        "confidence": round(float(confidence), 4),
        "caption": caption,
        "is_ethical": ethical,
        "verdict": "ethical" if ethical else "unethical",
        "reason": reason,
        "debug_reason": debug_reason,
        "matched_phrases": kw.get("matched_phrases", []),
        "safe_override": kw.get("safe_override", False),
        "engine": engine,
        "borderline": borderline,
        "p_unsafe": round(p, 4),
    }


def analyze_image_ethics_sync(b64: str, caption: str | None = None) -> dict:
    """
    Full local ethics analysis for one base64 image.

    Returns the public contract:
      { "ethical": bool, "category": str, "confidence": float, ...extras }
    """
    if not b64:
        return {
            "ethical": True,
            "category": "Safe",
            "confidence": 0.0,
            "caption": "",
            "reason": "No image data",
        }

    if ETHICS_ENGINE == "local":
        return _analyze_local(b64, caption)

    # Prefer shared caption (one BLIP pass for ethics + relevance)
    if caption is None:
        caption = generate_caption_from_b64(b64, cache_key=image_fingerprint(b64))
    taxonomy = score_caption_ethics(caption)

    if taxonomy["is_unethical"]:
        ethical = False
        category = taxonomy["category_label"]
        confidence = float(taxonomy["confidence"])
        reason = (
            f"Detected '{category}' from image caption "
            f"('{caption}'); matches={taxonomy['matched_phrases']}"
        )
    else:
        ethical = True
        category = "Safe"
        confidence = 0.9 if taxonomy.get("safe_override") else 0.85
        if taxonomy.get("safe_override"):
            reason = f"Trigger present but safe academic context: '{caption}'"
        else:
            reason = f"No unethical content detected (caption: '{caption}')"

    result = {
        "ethical": ethical,
        "category": category,
        "confidence": round(confidence, 4),
        "caption": caption,
        "is_ethical": ethical,
        "verdict": "ethical" if ethical else "unethical",
        "reason": reason,
        "matched_phrases": taxonomy.get("matched_phrases", []),
        "safe_override": taxonomy.get("safe_override", False),
    }

    if ethical:
        print(f"[image_ethics] ✅ ETHICAL | category=Safe | caption='{caption}'")
    else:
        print(
            f"[image_ethics] 🚨 UNETHICAL | category={category} | "
            f"confidence={confidence:.2f} | caption='{caption}' | "
            f"matches={taxonomy.get('matched_phrases', [])}"
        )
    return result


# ======================================================================
# PIPELINE API (compatible with dispatcher / main.py)
# ======================================================================

async def evaluate_image_ethics(
    client: Any = None,
    b64: str = "",
) -> Dict[str, Any]:
    """
    Single-image ethics check (used after user replaces an image).
    `client` is accepted for signature compatibility but never used.
    """
    result = await asyncio.to_thread(analyze_image_ethics_sync, b64)
    return {
        "verdict": result["verdict"],
        "is_ethical": result["ethical"],
        "ethical": result["ethical"],
        "category": result["category"],
        "confidence": result["confidence"],
        "reason": result["reason"],
        "caption": result.get("caption", ""),
    }


async def check_image_ethics(
    client: Any,
    batch: Batch,
) -> List[Dict[str, Any]]:
    """Evaluate every image in the batch for ethical appropriateness."""
    if not batch.images:
        return []

    results: List[Dict[str, Any]] = []
    for img in batch.images:
        if not img.base64:
            continue
        try:
            issue = await _evaluate_single_image(img.image_id, img.page_number, img.base64)
            if issue:
                results.append(issue)
        except Exception as exc:
            print(f"[image_ethics] error on {img.image_id}: {exc}")
    return results


async def _evaluate_single_image(
    image_id: str,
    page: int,
    b64: str,
) -> Dict[str, Any] | None:
    result = await asyncio.to_thread(analyze_image_ethics_sync, b64)
    if result["ethical"]:
        return None

    conf = result["confidence"]
    # Issue confidence historically was 0–100 for LLM path; keep float 0–1
    # and also provide 0–100 for UI that expects integers.
    conf_pct = int(round(conf * 100)) if conf <= 1.0 else int(conf)

    return {
        "function": "image_ethics",
        "type": "image_ethics",
        "severity": "major",
        "paragraph_id": "",
        "image_id": image_id,
        "page": page,
        "reason": result["reason"],
        "suggestion": "Replace this image with appropriate academic content.",
        "explanation": result["reason"],
        "debug_reason": result.get("debug_reason", ""),
        "original": "",
        "current_heading": "",
        "content_belongs_to": "",
        "text_preview": result.get("caption", "")[:120],
        "verdict": "unethical",
        "ethics_category": result["category"],
        "confidence": conf_pct,
        "ethical": False,
        "_replace_image": True,
    }


# ======================================================================
# TEST SUITE — run: python -m functions.image_ethics  (from backend/)
# ======================================================================

if __name__ == "__main__":
    tests = [
        ("a naked person standing in a room", "UNETHICAL"),
        ("a woman in a provocative pose with exposed body", "UNETHICAL"),
        ("two people in a sexual act on a bed", "UNETHICAL"),
        ("a man bleeding from a stab wound on the ground", "UNETHICAL"),
        ("a dead body lying on the floor covered in blood", "UNETHICAL"),
        ("a swastika symbol painted on a wall", "UNETHICAL"),
        ("a person performing a nazi salute", "UNETHICAL"),
        ("a person injecting drugs into their arm", "UNETHICAL"),
        ("a table with a bunch of guns and a knife", "UNETHICAL"),
        ("a person showing the middle finger", "UNETHICAL"),
        ("a diagram of blood vessels in the human body", "ETHICAL"),
        ("a medical diagram showing blood flow through the heart", "ETHICAL"),
        ("a bar chart showing quarterly sales results", "ETHICAL"),
        ("a company logo on a white background", "ETHICAL"),
        ("a nature photograph of a forest at sunrise", "ETHICAL"),
        ("a historical weapons exhibit in a museum", "ETHICAL"),
        ("a toy gun lying on a colorful playmat", "ETHICAL"),
        ("an anti-drug awareness campaign poster", "ETHICAL"),
    ]

    print("\n" + "=" * 72)
    print("   IMAGE ETHICS DETECTION — CAPTION TAXONOMY TEST SUITE")
    print("=" * 72)

    passed = failed = 0
    for caption, expected in tests:
        result = score_caption_ethics(caption)
        actual = "UNETHICAL" if result["is_unethical"] else "ETHICAL"
        ok = actual == expected
        passed += int(ok)
        failed += int(not ok)
        icon = "OK" if ok else "FAIL"
        print(f"  [{icon}] expected={expected:9s}  {caption}")
        if not ok:
            print(f"         got={actual}  category={result['category_label']}")

    print(f"\nRESULTS: {passed} passed, {failed} failed ({len(tests)} total)")
