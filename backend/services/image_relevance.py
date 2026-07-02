import torch
import numpy as np
import re
import cv2
import pytesseract
from PIL import Image
import spacy
import io
import uuid
from docx import Document

from transformers import BlipProcessor, BlipForConditionalGeneration
from sentence_transformers import SentenceTransformer, CrossEncoder, util
import clip

# =====================================================
# LOAD MODELS (LOAD ONLY ONCE)
# =====================================================

device = "cuda" if torch.cuda.is_available() else "cpu"

blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
blip_model = BlipForConditionalGeneration.from_pretrained(
    "Salesforce/blip-image-captioning-base"
).to(device)

sbert_model = SentenceTransformer("all-mpnet-base-v2", device=device)
cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device=device)
clip_model, clip_preprocess = clip.load("ViT-B/32", device=device)
nlp = spacy.load("en_core_web_sm")


# =====================================================
# IMAGE EXTRACTION FROM DOCX
# =====================================================

def extract_images_with_full_context(docx_path):
    """
    Extracts images from a .docx file along with rich surrounding context:
      - Full heading breadcrumb (H1 > H2 > H3) rather than just the nearest heading
      - Last 5 paragraphs BEFORE the image (was 2)
      - Next 3 paragraphs AFTER  the image (was 1)
    These wider windows give SBERT / cross-encoder / CLIP enough signal to score
    relevance accurately, while staying tight enough to avoid dilution from
    unrelated neighbouring sections.
    """
    doc = Document(docx_path)

    results = []
    paragraphs = doc.paragraphs

    # Track full heading hierarchy instead of just the most-recent heading
    heading_h1 = ""
    heading_h2 = ""
    heading_h3 = ""

    image_index = 0  # global counter used by is_special_image for logo detection

    for i, para in enumerate(paragraphs):

        # -- Detect and track heading hierarchy --
        style = para.style.name
        if style == "Heading 1":
            heading_h1 = para.text.strip()
            heading_h2 = ""          # reset lower levels when a new H1 starts
            heading_h3 = ""
        elif style == "Heading 2":
            heading_h2 = para.text.strip()
            heading_h3 = ""
        elif style == "Heading 3":
            heading_h3 = para.text.strip()
        elif style.startswith("Heading"):
            # Heading 4+ treated as H3-level for breadcrumb purposes
            heading_h3 = para.text.strip()

        # Build full breadcrumb, e.g. "Chapter 2 > Machine Learning > CNN Architecture"
        last_heading = " > ".join(filter(None, [heading_h1, heading_h2, heading_h3]))

        # -- Detect image in paragraph --
        has_image = False
        for run in para.runs:
            if "graphic" in run._element.xml:
                has_image = True
                break

        if has_image:

            # -- Last 5 paragraphs BEFORE the image (skip empty ones) --
            before_paragraphs = []
            for j in range(max(0, i - 5), i):
                text = paragraphs[j].text.strip()
                if text:
                    before_paragraphs.append(text)
            before_text = " ".join(before_paragraphs)

            # -- Next 3 paragraphs AFTER the image (skip empty ones) --
            after_paragraphs = []
            for j in range(i + 1, min(len(paragraphs), i + 4)):
                text = paragraphs[j].text.strip()
                if text:
                    after_paragraphs.append(text)
            after_text = " ".join(after_paragraphs)

            # -- Extract actual image file --
            for rel in doc.part.rels.values():
                if "image" in rel.target_ref:
                    img_bytes = rel.target_part.blob
                    filename = f"uploads/{uuid.uuid4()}.png"
                    Image.open(io.BytesIO(img_bytes)).save(filename)

                    results.append({
                        "image_path":   filename,
                        "heading":      last_heading,
                        "before_text":  before_text,
                        "after_text":   after_text,
                        "image_index":  image_index,   # passed to logo detector
                    })

                    image_index += 1

    return results



# =====================================================
# CAPTION
# =====================================================

def generate_caption(image_path):
    image = Image.open(image_path).convert("RGB")
    inputs = blip_processor(image, return_tensors="pt").to(device)
    out = blip_model.generate(**inputs, max_new_tokens=50)
    return blip_processor.decode(out[0], skip_special_tokens=True)


# =====================================================
# OCR — MULTI-STRATEGY + NOISE CLEANING
# =====================================================

def clean_ocr_text(raw_text):
    """
    Remove OCR noise: isolated punctuation, single chars, garbled tokens.
    Keep real words only (3+ alphanumeric chars, or known short words).
    """
    # Replace newlines/tabs with spaces
    text = re.sub(r'[\n\r\t]+', ' ', raw_text)
    # Remove non-ASCII garbage
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    # Extract all word-like tokens (letters+digits, length >= 2)
    tokens = re.findall(r'\b[a-zA-Z]{2,}\b', text)
    cleaned = ' '.join(tokens)
    return cleaned.strip()


def extract_ocr_text(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return ""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    results = []

    # Strategy 1: Adaptive threshold (good for diagrams with varied lighting)
    thresh1 = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    results.append(pytesseract.image_to_string(thresh1, config='--psm 11'))

    # Strategy 2: Otsu (good for clean black/white diagrams)
    _, thresh2 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    results.append(pytesseract.image_to_string(thresh2, config='--psm 11'))

    # Strategy 3: Upscaled (helps catch small text in diagrams)
    scale = 2
    upscaled = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    _, thresh3 = cv2.threshold(upscaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    results.append(pytesseract.image_to_string(thresh3, config='--psm 11'))

    # Clean all results and pick the one with most real words
    cleaned_results = [clean_ocr_text(r) for r in results]
    best = max(cleaned_results, key=lambda t: len(t.split()))

    return best


# =====================================================
# SIMILARITY — FIXED CROSS ENCODER NORMALIZATION
# =====================================================

def sbert_similarity(text1, text2):
    """Returns cosine similarity in [0, 1]."""
    if not text1.strip() or not text2.strip():
        return 0.0
    e1 = sbert_model.encode(text1, convert_to_tensor=True)
    e2 = sbert_model.encode(text2, convert_to_tensor=True)
    score = util.cos_sim(e1, e2).item()
    return float(max(0.0, score))


def cross_encoder_similarity(text1, text2):
    """
    CRITICAL FIX: Cross-encoder returns raw logits (e.g. -10 to +10),
    NOT a 0-1 probability. We normalize via sigmoid so it's safe to
    use in a weighted ensemble with other 0-1 scores.
    """
    if not text1.strip() or not text2.strip():
        return 0.0
    raw_score = cross_encoder.predict([(text1, text2)])[0]
    # Sigmoid maps any real number to (0, 1)
    normalized = float(1 / (1 + np.exp(-raw_score)))
    return normalized


def clip_similarity(image_path, text):
    """Returns cosine similarity in [0, 1]."""
    text = text[:300]  # CLIP token limit safety
    image = clip_preprocess(Image.open(image_path)).unsqueeze(0).to(device)
    text_tokens = clip.tokenize([text], truncate=True).to(device)
    with torch.no_grad():
        img_feat = clip_model.encode_image(image)
        txt_feat = clip_model.encode_text(text_tokens)
        img_feat /= img_feat.norm(dim=-1, keepdim=True)
        txt_feat /= txt_feat.norm(dim=-1, keepdim=True)
        score = (img_feat @ txt_feat.T).item()
    return float(max(0.0, score))


# =====================================================
# KEYWORD MATCHING (NOISE-TOLERANT)
# =====================================================

def extract_keywords(text):
    """Extract meaningful words: nouns, proper nouns, non-stop words."""
    doc = nlp(text)
    keywords = set()
    for token in doc:
        if token.pos_ in ["NOUN", "PROPN"] and not token.is_stop and len(token.text) > 2:
            keywords.add(token.lemma_.lower())
    return keywords


def raw_word_overlap_score(text1, text2):
    """
    What fraction of words in text2 also appear in text1.
    Recall-focused: catches 'processor' in OCR → heading.
    """
    words1 = set(re.findall(r'\b[a-zA-Z]{3,}\b', text1.lower()))
    words2 = set(re.findall(r'\b[a-zA-Z]{3,}\b', text2.lower()))
    if not words1 or not words2:
        return 0.0
    overlap = words1 & words2
    # Recall: how many of the context's words appear in image text?
    return len(overlap) / len(words2)


def keyword_overlap_score(text1, text2):
    """Lemmatized noun overlap (Jaccard)."""
    kw1 = extract_keywords(text1)
    kw2 = extract_keywords(text2)
    if not kw1 or not kw2:
        return 0.0
    overlap = kw1 & kw2
    return len(overlap) / max(len(kw1), len(kw2))

def any_exact_keyword_match(image_text, heading, before_text, after_text):
    
    print("DEBUG heading received:", heading)

    image_words = set(
        word.lower()
        for word in re.findall(r'\w+', image_text)
        if len(word) >= 3
    )

    context_words_raw = set(
        word.lower()
        for word in re.findall(r'\w+', heading + " " + before_text + " " + after_text)
        if len(word) >= 3
    )

    print("DEBUG context_words_raw:", context_words_raw)

    # Generic words that appear in almost ANY technical document and therefore
    # carry no discriminating power for relevance matching.
    # Rule of thumb: if the word could appear in a hospital diagram AND an
    # AI formatter diagram without surprise, it belongs here.
    stopwords = {
        # Standard English stopwords
        'the','and','for','with','this','that','from','are','was','has',
        'have','its','into','also','below','above','following','shows',
        'shown','figure','image','diagram','block','each','used','uses',
        'using','based','which','their','they','them','then','than',
        'when','where','how','all','any','can','may','will','two','one',
        # Generic tech/document words (appear in virtually every report)
        'data','system','network','process','server','user','unit',
        'local','model','output','input','module','layer','component',
        'application','service','api','call','calls','request','response',
        'flow','pipeline','connection','interface','management','control',
        'result','results','report','format','high','quality','version',
        'backup','sync','synchronization','failsafe','external','internal',
        # Generic action/descriptor words
        'processing','generation','interaction','integration','description',
        'architecture','methodology','successful','optional','different',
        'scalable','achieves','achieve','satisfies','exports','holds',
    }

    context_words = context_words_raw - stopwords

    print("DEBUG context_words_clean:", context_words)

    matches = image_words.intersection(context_words)

    return matches
# =====================================================
# MAIN ANALYZER
# =====================================================
def is_special_image(ocr_text, caption, image_path, image_index=0, clip_score=None):
    """
    Returns True ONLY if the image is clearly a university logo, letterhead,
    or author signature. Uses strict multi-signal logic to avoid false positives
    like cars, diagrams, or photos being mis-classified as logos.

    Signals used (ALL must be consistent — no single weak signal overrides):
      1. OCR or caption contains explicit logo/university keywords  → strong, sufficient alone
      2. Filename hint (logo, letterhead in path)                  → strong, sufficient alone
      3. CLIP logo probe score is HIGH (>= 0.24)                   → strong visual confirmation
         AND CLIP negative probes all score LOW                     → rules out cars/photos/etc.
      4. Early position is used as a weak SUPPORTING signal only,
         never as a trigger by itself.
    """
    ocr_lower = ocr_text.lower()
    caption_lower = caption.lower()
    combined_text = ocr_lower + " " + caption_lower

    # ── Signal 1: Explicit text keyword match (OCR or caption) ────────────────
    # These words are specific enough that a match is near-certain evidence.
    logo_keywords = [
        "university", "college", "institute", "logo", "department",
        "faculty", "school of", "established", "est.", "letterhead",
        "crest", "emblem", "seal"
    ]
    signature_keywords = ["signature", "signed by", "supervisor"]

    if any(k in combined_text for k in logo_keywords + signature_keywords):
        print("🏫 Special override reason: OCR/caption keyword match")
        return True

    # ── Signal 2: Filename hint ───────────────────────────────────────────────
    path_lower = image_path.lower()
    if any(k in path_lower for k in ["signature", "logo", "letterhead", "header"]):
        print("🏫 Special override reason: filename hint")
        return True

    # ── Signal 3: CLIP visual probe — strict positive + negative gating ───────
    # The logo probe must score HIGH, AND all negative probes must score LOW.
    # This prevents a car (which scores low on logo probe AND low on content)
    # from slipping through just because it's at position 0.
    try:
        logo_clip = clip_similarity(image_path, LOGO_PROBE_POSITIVE)
        print(f"🏫 Logo CLIP probe score: {logo_clip:.4f}")

        if logo_clip >= 0.24:
            # Also verify it doesn't match any "not a logo" category
            max_negative = max(
                clip_similarity(image_path, neg) for neg in LOGO_PROBE_NEGATIVE
            )
            print(f"🏫 Max negative probe score: {max_negative:.4f}")

            if max_negative < logo_clip:
                # Logo probe wins over every negative → it really looks like a logo
                print("🏫 Special override reason: CLIP logo probe dominant")
                return True
            else:
                print(f"🏫 Logo probe blocked — negative probe matched more strongly")
    except Exception as e:
        print(f"🏫 CLIP probe failed: {e}")

    # ── Early position: informational only, never a trigger ──────────────────
    # (Removed: early position + low CLIP was the bug causing cars to be
    #  marked as logos. Low CLIP score = irrelevant, not = logo.)

    return False




def analyze_image_relevance(image_path, heading, before_text, after_text, image_index=0):

    print(f"\n🔎 Analyzing: {image_path}")

    # ── 1. Extract signals ────────────────────────────────────────────────────

    caption = generate_caption(image_path)
    print(f"📌 Caption: {caption}")

    ocr_text = extract_ocr_text(image_path)
    print(f"📌 OCR cleaned ({len(ocr_text.split())} words): {ocr_text[:150]}")

    # Combined image text representation
    image_text = caption
    if len(ocr_text.split()) >= 2:
        image_text = caption + " " + ocr_text

    full_context = heading + " " + before_text + " " + after_text

    # ── 2. Hard keyword match check ───────────────────────────────────────────
    # If OCR words directly overlap with heading/context keywords → strong signal
    exact_matches = any_exact_keyword_match(image_text, heading, before_text, after_text)
    caption_matches = set()
    all_matches = exact_matches | caption_matches

    has_direct_keyword_hit = len(all_matches) >= 1
    keyword_hit_strength = min(len(all_matches) / 2.0, 1.0)  # Normalize to 0-1

    print(f"🔑 Keyword matches: {all_matches}")

    # ── 3. Semantic scores ────────────────────────────────────────────────────

    # OCR vs context (separate heading and body for finer signal)
    ocr_vs_heading = sbert_similarity(ocr_text, heading) if ocr_text else 0.0
    ocr_vs_body = sbert_similarity(ocr_text, before_text + " " + after_text) if ocr_text else 0.0
    ocr_sbert = max(ocr_vs_heading, ocr_vs_body)

    # Caption vs context
    cap_vs_heading = sbert_similarity(caption, heading)
    cap_vs_body = sbert_similarity(caption, before_text + " " + after_text)
    cap_sbert = max(cap_vs_heading, cap_vs_body)
    def semantic_similarity_full_context(image_text, heading, before_text, after_text):
        context_parts = []
        if heading.strip():
            context_parts.append(heading)
        if before_text.strip():
            context_parts.append(before_text)
        if after_text.strip():
            context_parts.append(after_text)
        full_context = " ".join(context_parts)
        return sbert_similarity(image_text, full_context)

    # Combined image text vs full context
    combined_sbert = semantic_similarity_full_context(
    image_text,
    heading,
    before_text,
    after_text
)

    # Cross encoder — normalized via sigmoid (CRITICAL FIX)
    cross_score = cross_encoder_similarity(image_text, full_context)

    # CLIP visual-semantic
    clip_score = clip_similarity(image_path, full_context)

    # Keyword overlaps
    ocr_word_overlap = raw_word_overlap_score(ocr_text, heading + " " + before_text + " " + after_text)
    cap_word_overlap = raw_word_overlap_score(caption, full_context)
    kw_overlap = max(ocr_word_overlap, cap_word_overlap)

    noun_overlap = keyword_overlap_score(image_text, full_context)

    # ── 4. Ensemble scoring ───────────────────────────────────────────────────
    #
    # Weights reflect reliability:
    #   - SBERT on combined text: best general semantic signal
    #   - Cross encoder (sigmoid-normalized): precise relevance, now trustworthy
    #   - CLIP: visual bridge
    #   - Keyword overlap: catches exact term matches (processor, CPU, etc.)
    #   - Noun overlap: lemmatized, handles variants

    base_score = (
        0.35 * clip_score +        # MOST IMPORTANT
    0.25 * combined_sbert +
    0.20 * cross_score +
    0.10 * kw_overlap +
    0.05 * ocr_sbert +
    0.05 * cap_sbert
    )

    # ── 5. Keyword hit boost ──────────────────────────────────────────────────
    # If OCR or caption words directly match context keywords, apply a bonus.
    # This is the core fix for your case: "processor" in OCR + "processor" in
    # heading should guarantee relevance regardless of other scores.
    keyword_bonus = keyword_hit_strength * 0.20  # Up to +0.20 bonus

    final_score = min(base_score + keyword_bonus, 1.0)

    # ── 6. Decision ───────────────────────────────────────────────────────────
    # Standard threshold. With keyword bonus the processor-diagram case
    # will score well above this.
    threshold = 0.35

    # Hard override: if 2+ meaningful keywords match directly → relevant
    # (covers edge cases where all models score low but terms are identical)
    hard_relevant = len(all_matches) >= 2

    relevant = final_score >= threshold or hard_relevant
    special_override = is_special_image(ocr_text, caption, image_path, image_index=image_index, clip_score=clip_score)
    if special_override:
        print("⚡ Special override: detected logo/signature → automatically relevant")
        relevant = True
        final_score = max(final_score, 0.9)

    # ── 7. Result ─────────────────────────────────────────────────────────────

    result = {
        "caption": caption,
        "ocr_text": ocr_text,

        # Score breakdown
        "combined_sbert":    round(combined_sbert, 4),
        "cross_score":       round(cross_score, 4),   # sigmoid-normalized
        "clip_score":        round(clip_score, 4),
        "ocr_sbert":         round(ocr_sbert, 4),
        "caption_sbert":     round(cap_sbert, 4),
        "keyword_overlap":   round(kw_overlap, 4),
        "noun_overlap":      round(noun_overlap, 4),

        # Keyword evidence
        "matching_keywords":     list(all_matches),
        "keyword_hit_strength":  round(keyword_hit_strength, 4),
        "keyword_bonus_applied": round(keyword_bonus, 4),
        "hard_override":         hard_relevant,

        # Final
        "base_score":   round(base_score, 4),
        "final_score":  round(final_score, 4),
        "threshold":    threshold,
        "relevant":     relevant,
    }

    print(f"\n{'✅ RELEVANT' if relevant else '❌ NOT RELEVANT'} "
          f"(score={final_score:.4f}, threshold={threshold}, "
          f"keywords={list(all_matches)}, hard_override={hard_relevant})")

    return result


# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":

    image_path = "test_image.jpg"

    heading = "Architecture Diagram of processor"
    before_text = "Below is the image."
    after_text = ""

    result = analyze_image_relevance(image_path, heading, before_text, after_text)

    print("\n===== FULL RESULT =====")
    for k, v in result.items():
        print(f"  {k}: {v}")