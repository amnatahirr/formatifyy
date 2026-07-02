import os
from typing import List, Dict

# ── Real ethics engine (BLIP caption → taxonomy classifier) ───────────────────
from services.image_ethics import analyze_image_ethics, get_unethical_images


class ImageEthicsDetector:
    """
    Detect unsafe/unethical content in document images.

    Replaces the old MVP stub (file-size heuristic) with the full
    BLIP-caption → ethics-taxonomy pipeline from image_ethics.py.

    Result key mapping
    ------------------
    image_ethics.py          →  this class (frontend-facing keys)
    ─────────────────────────────────────────────────────────────
    is_unethical             →  is_safe        (inverted bool)
    confidence               →  confidence_score
    category_label           →  category       (new key, None if safe)
    matched_phrases          →  warnings       (list of strings)
    safe_override            →  safe_override  (pass-through)
    caption                  →  caption        (pass-through)
    image_path               →  image_path     (pass-through)

    Keeping is_safe / confidence_score / warnings means nothing else in
    your backend needs to change to accommodate the new detection engine.
    """

    def analyze_image(self, image_path: str) -> Dict:
        """
        Analyse a single image for unethical content.

        Parameters
        ----------
        image_path : str
            Real filesystem path to a saved image file (PNG/JPG).
            Must be an actual file — NOT an internal XML ref string like
            'word/media/image1.png'.  document_parser.extract_images_with_context()
            now saves real files and returns proper paths.

        Returns
        -------
        {
            "image_path"      : str,
            "is_safe"         : bool,    # False  → unethical, must fix
            "confidence_score": float,   # 0.0–1.0
            "category"        : str | None,
            "warnings"        : list[str],
            "safe_override"   : bool,
            "caption"         : str,
        }
        """
        if not os.path.exists(image_path):
            return {
                "image_path":       image_path,
                "is_safe":          True,
                "confidence_score": 0.0,
                "category":         None,
                "warnings":         [f"Image file not found: {image_path}"],
                "safe_override":    False,
                "caption":          "",
            }

        # ── Run the real ethics engine ─────────────────────────────────────
        ethics = analyze_image_ethics(image_path)

        return {
            "image_path":       ethics["image_path"],
            "is_safe":          not ethics["is_unethical"],   # invert
            "confidence_score": ethics["confidence"],
            "category":         ethics["category_label"],     # None if safe
            "warnings":         ethics["matched_phrases"],    # list[str]
            "safe_override":    ethics["safe_override"],
            "caption":          ethics["caption"],
        }

    def analyze_document_images(self, document_id: int, image_contexts: List[Dict]) -> List[Dict]:
        """
        Analyse all images extracted from a document.

        Parameters
        ----------
        document_id   : int
            ID of the document being analysed (attached to every result).

        image_contexts : List[Dict]
            Output of document_parser.extract_images_with_context().
            Each dict must contain at least {"image_path": str}.
            (heading / before_text / after_text are used by relevancy checks
            but are not required here — we only need image_path.)

        Returns
        -------
        List of result dicts (same shape as analyze_image()), each with an
        extra "document_id" key.
        """
        results = []

        for ctx in image_contexts:
            result = self.analyze_image(ctx["image_path"])
            result["document_id"] = document_id
            results.append(result)

        return results

    def get_flagged_images(self, document_id: int, image_contexts: List[Dict]) -> List[Dict]:
        """
        Convenience method — returns ONLY the unsafe images.

        Useful for your analysis screen: pass the return value directly to
        the frontend to render the unethical-image error cards.

        Returns
        -------
        Filtered list of result dicts where is_safe == False.
        """
        all_results = self.analyze_document_images(document_id, image_contexts)
        return [r for r in all_results if not r["is_safe"]]


# Singleton instance (mirrors the pattern in your original file)
image_detector = ImageEthicsDetector()