"""
plagiarism/test_detector.py — Unit-style tests for the hybrid plagiarism module.

Run from the backend directory:

    python -m plagiarism.test_detector

Uses the package sample_corpus only (no Google API required; Stage 2 is mocked
or disabled). Embedding model download happens on first run.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from plagiarism import config
from plagiarism.corpus_index import (
    build_corpus_index,
    make_shingles,
    split_into_sentences,
    text_to_minhash,
    tokenize,
    jaccard_from_minhash,
)
from plagiarism.detector import (
    detect_plagiarism_sync,
    filter_checkable_sentences,
    normalize_chunks,
    overall_plagiarism_score,
    select_web_candidates,
)
from plagiarism.local_check import combine_local_scores
from plagiarism.local_check import ExactMatchResult, SemanticMatchResult
from plagiarism.web_verify import textual_overlap, truncate_words, word_jaccard


SAMPLE_CORPUS = Path(__file__).resolve().parent / "sample_corpus"


class TestTextHelpers(unittest.TestCase):
    def test_tokenize_lowercases(self):
        self.assertEqual(tokenize("Hello, World!"), ["hello", "world"])

    def test_shingles_size_five(self):
        words = ["a", "b", "c", "d", "e", "f"]
        shingles = make_shingles(words, size=5)
        self.assertEqual(shingles, ["a b c d e", "b c d e f"])

    def test_short_text_single_shingle(self):
        self.assertEqual(make_shingles(["only", "three", "words"], size=5), ["only three words"])

    def test_split_into_sentences(self):
        text = "First sentence. Second sentence! Third?"
        self.assertEqual(len(split_into_sentences(text)), 3)

    def test_identical_minhash_jaccard_one(self):
        text = "Machine learning is a subset of artificial intelligence that enables systems"
        a = text_to_minhash(text)
        b = text_to_minhash(text)
        self.assertGreaterEqual(jaccard_from_minhash(a, b), 0.99)


class TestWebHelpers(unittest.TestCase):
    def test_truncate_words(self):
        words = " ".join(f"w{i}" for i in range(40))
        truncated = truncate_words(words, max_words=30)
        self.assertEqual(len(truncated.split()), 30)

    def test_word_jaccard_identical(self):
        self.assertEqual(word_jaccard("alpha beta gamma", "alpha beta gamma"), 1.0)

    def test_textual_overlap_substring(self):
        sentence = (
            "Machine learning is a subset of artificial intelligence that enables "
            "systems to learn and improve from experience without being explicitly programmed"
        )
        snippet = (
            "Machine learning is a subset of artificial intelligence that enables systems"
        )
        self.assertGreaterEqual(textual_overlap(sentence, snippet), 0.45)


class TestCombineScores(unittest.TestCase):
    def test_max_of_both_signals(self):
        exact = ExactMatchResult(score=0.9, matched_source="a.txt", matched_text="x")
        semantic = SemanticMatchResult(score=0.4, matched_source="b.txt", matched_text="y")
        score, match_type, source = combine_local_scores(exact, semantic)
        self.assertAlmostEqual(score, 0.9)
        self.assertEqual(source, "a.txt")
        self.assertIn(match_type, ("exact", "both", "semantic"))

    def test_both_when_both_hit(self):
        exact = ExactMatchResult(score=0.8, matched_source="a.txt", matched_text="x")
        semantic = SemanticMatchResult(
            score=0.9, matched_source="a.txt", matched_text="x", flagged=True
        )
        score, match_type, _ = combine_local_scores(exact, semantic)
        self.assertAlmostEqual(score, 0.9)
        self.assertEqual(match_type, "both")


class TestNormalize(unittest.TestCase):
    def test_empty_document_chunks(self):
        self.assertEqual(normalize_chunks(""), [])
        self.assertEqual(normalize_chunks([]), [])

    def test_dict_chunks(self):
        chunks = normalize_chunks(
            [{"text": "hello world this is long enough now truly", "paragraph_id": "p1"}]
        )
        self.assertEqual(chunks[0]["chunk_id"], "p1")

    def test_filter_short(self):
        kept = filter_checkable_sentences(
            [
                {"text": "too short", "chunk_id": "a"},
                {
                    "text": "this sentence clearly has more than eight distinct words inside it",
                    "chunk_id": "b",
                },
            ]
        )
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["chunk_id"], "b")


class TestEmptyGuards(unittest.TestCase):
    def test_empty_document_raises(self):
        with self.assertRaises(ValueError) as ctx:
            detect_plagiarism_sync("", document_id="empty", enable_web_verify=False)
        self.assertIn("Empty document", str(ctx.exception))

    def test_empty_corpus_dir_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as ctx:
                detect_plagiarism_sync(
                    "This is a long enough sentence that would normally be checked for plagiarism risk assessment.",
                    document_id="doc",
                    corpus_dir=Path(tmp),
                    force_rebuild_index=True,
                    enable_web_verify=False,
                )
            self.assertIn("empty", str(ctx.exception).lower())


class TestEndToEndLocal(unittest.TestCase):
    """Requires sentence-transformers + faiss + datasketch (first run downloads model)."""

    @classmethod
    def setUpClass(cls):
        cls.cache_dir = Path(tempfile.mkdtemp(prefix="plagiarism_test_cache_"))
        # Point index cache at temp so we don't pollute package cache during CI.
        cls._orig_cache = config.INDEX_CACHE_DIR
        config.INDEX_CACHE_DIR = cls.cache_dir

    @classmethod
    def tearDownClass(cls):
        config.INDEX_CACHE_DIR = cls._orig_cache

    def test_build_and_detect_exact_overlap(self):
        index = build_corpus_index(
            corpus_dir=SAMPLE_CORPUS,
            cache_dir=self.cache_dir,
            force_rebuild=True,
        )
        self.assertGreaterEqual(index.size, 2)
        self.assertGreater(index.sentence_count, 0)

        document = [
            {
                "text": (
                    "Machine learning is a subset of artificial intelligence that enables "
                    "systems to learn and improve from experience without being explicitly programmed."
                ),
                "chunk_id": "p_exact",
            },
            {
                "text": (
                    "Deep learning models use multiple layers of neural networks to extract "
                    "hierarchical features from raw data."
                ),
                "chunk_id": "p_exact2",
            },
            {
                "text": (
                    "My neighbours grow tomatoes on the balcony every summer despite the wind."
                ),
                "chunk_id": "p_clean",
            },
        ]

        report = detect_plagiarism_sync(
            document,
            document_id="test_doc_1",
            corpus=index,
            enable_web_verify=False,
        )

        self.assertEqual(report["document_id"], "test_doc_1")
        self.assertEqual(report["corpus_size"], index.size)
        self.assertEqual(report["web_checks_performed"], 0)
        self.assertGreaterEqual(report["sentences_checked"], 2)
        self.assertGreater(report["overall_plagiarism_score"], 0.0)

        flagged_ids = {f["chunk_id"] for f in report["flagged_sentences"]}
        self.assertIn("p_exact", flagged_ids)
        # Clean gardening sentence should usually not be flagged highly.
        clean = [f for f in report["flagged_sentences"] if f["chunk_id"] == "p_clean"]
        if clean:
            self.assertLess(clean[0]["local_suspicion_score"], 0.85)

    def test_stage2_skipped_when_below_threshold(self):
        index = build_corpus_index(
            corpus_dir=SAMPLE_CORPUS,
            cache_dir=self.cache_dir,
            force_rebuild=False,
        )
        # Use only a clearly unique sentence — Stage 2 should perform 0 calls
        # even with web enabled, because local score stays low.
        document = (
            "Zebras painted purple umbrellas underneath quivering jelly lanterns yesterday afternoon."
        )
        report = detect_plagiarism_sync(
            document,
            document_id="unique_doc",
            corpus=index,
            enable_web_verify=True,
        )
        self.assertEqual(report["web_checks_performed"], 0)

    def test_select_web_candidates_respects_threshold(self):
        from plagiarism.local_check import LocalSentenceResult

        low = LocalSentenceResult(
            sentence="x",
            chunk_id="low",
            exact=ExactMatchResult(0.2, None, None),
            semantic=SemanticMatchResult(0.2, None, None),
            local_suspicion_score=0.2,
            match_type="none",
            matched_corpus_source=None,
        )
        high = LocalSentenceResult(
            sentence="y",
            chunk_id="high",
            exact=ExactMatchResult(0.9, "a.txt", "y"),
            semantic=SemanticMatchResult(0.5, None, None),
            local_suspicion_score=0.9,
            match_type="exact",
            matched_corpus_source="a.txt",
        )
        chosen = select_web_candidates([low, high], score_threshold=0.6, top_k=5)
        self.assertEqual(len(chosen), 1)
        self.assertEqual(chosen[0].chunk_id, "high")

    def test_overall_score_empty(self):
        self.assertEqual(overall_plagiarism_score([]), 0.0)

    def test_web_verify_handles_missing_credentials(self):
        from plagiarism.web_verify import verify_sentence_on_web

        with patch.object(config, "GOOGLE_SEARCH_API_KEY", ""):
            with patch.object(config, "GOOGLE_SEARCH_ENGINE_ID", ""):
                result = verify_sentence_on_web(
                    "Machine learning is a subset of artificial intelligence that enables systems"
                )
                self.assertIsNone(result.web_verified)
                self.assertIn("not configured", result.note or "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
