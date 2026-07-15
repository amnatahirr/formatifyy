"""
plagiarism/web_verify.py — Stage 2 selective public-web verification.

Why Stage 2 exists (FYP):
  Local corpus matches prove similarity to *known* references, not that text
  appears on the open web. Google Custom Search is used only for the top-K
  sentences whose Stage-1 local_suspicion_score exceeds a threshold. Keeping
  web calls selective (and hard-capped per document) avoids excessive API
  usage/cost while still allowing external confirmation when it matters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence
from urllib.parse import urlencode

import requests

from plagiarism import config
from plagiarism.corpus_index import tokenize


@dataclass
class WebVerifyResult:
    """Outcome of a single Google Custom Search probe for one sentence."""
    sentence: str
    web_verified: Optional[bool]
    web_source_url: Optional[str]
    note: Optional[str] = None
    best_overlap: float = 0.0


def truncate_words(text: str, max_words: int = config.WEB_QUERY_MAX_WORDS) -> str:
    """Truncate a sentence to ~max_words for the search query."""
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words])


def word_jaccard(a: str, b: str) -> float:
    """Jaccard similarity over word-token sets (pure, unit-testable)."""
    sa = set(tokenize(a))
    sb = set(tokenize(b))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def textual_overlap(sentence: str, snippet: str) -> float:
    """
    Combine substring presence with word Jaccard for robust snippet matching.

    Returns a score in [0, 1]. A clear substring containment of a long-enough
    fragment scores 1.0 immediately.
    """
    if not sentence or not snippet:
        return 0.0

    sent_norm = " ".join(tokenize(sentence))
    snip_norm = " ".join(tokenize(snippet))
    if not sent_norm or not snip_norm:
        return 0.0

    # Contiguous substring of at least half the sentence words → strong hit.
    sent_words = sent_norm.split()
    half = max(4, len(sent_words) // 2)
    probe = " ".join(sent_words[:half])
    if probe and probe in snip_norm:
        return 1.0
    if snip_norm in sent_norm and len(snip_norm.split()) >= 5:
        return 1.0

    return word_jaccard(sentence, snippet)


def _credentials_available() -> bool:
    return bool(config.GOOGLE_SEARCH_API_KEY and config.GOOGLE_SEARCH_ENGINE_ID)


def query_google_cse(
    query: str,
    api_key: Optional[str] = None,
    engine_id: Optional[str] = None,
    num_results: int = config.WEB_SEARCH_NUM_RESULTS,
    timeout: float = 10.0,
) -> List[dict]:
    """
    Call the Google Custom Search JSON API and return result items.

    Raises requests.RequestException / ValueError on failure — callers must
    wrap this so network errors never crash the Formatify pipeline.
    """
    api_key = api_key if api_key is not None else config.GOOGLE_SEARCH_API_KEY
    engine_id = engine_id if engine_id is not None else config.GOOGLE_SEARCH_ENGINE_ID

    if not api_key or not engine_id:
        raise ValueError(
            "GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID must be set "
            "in the environment to run Stage 2 web verification."
        )

    params = {
        "key": api_key,
        "cx": engine_id,
        "q": query,
        "num": max(1, min(num_results, 10)),
    }
    url = f"{config.GOOGLE_CSE_ENDPOINT}?{urlencode(params)}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    return list(payload.get("items") or [])


def verify_sentence_on_web(
    sentence: str,
    overlap_threshold: float = config.WEB_OVERLAP_THRESHOLD,
) -> WebVerifyResult:
    """
    Search the public web for `sentence` and mark web_verified on high overlap.

    On any failure (missing credentials, network, HTTP error), returns
    ``web_verified=None`` with an explanatory note — never raises.
    """
    query = truncate_words(sentence)
    if not query.strip():
        return WebVerifyResult(
            sentence=sentence,
            web_verified=False,
            web_source_url=None,
            note="empty query",
        )

    if not _credentials_available():
        return WebVerifyResult(
            sentence=sentence,
            web_verified=None,
            web_source_url=None,
            note="web verification skipped: GOOGLE_SEARCH_API_KEY / "
            "GOOGLE_SEARCH_ENGINE_ID not configured",
        )

    try:
        items = query_google_cse(query)
    except Exception as exc:
        return WebVerifyResult(
            sentence=sentence,
            web_verified=None,
            web_source_url=None,
            note=f"web verification failed: {exc}",
        )

    best_overlap = 0.0
    best_url: Optional[str] = None

    for item in items:
        snippet = str(item.get("snippet") or item.get("title") or "")
        url = item.get("link")
        overlap = textual_overlap(sentence, snippet)
        if overlap > best_overlap:
            best_overlap = overlap
            best_url = url

    if best_overlap >= overlap_threshold and best_url:
        return WebVerifyResult(
            sentence=sentence,
            web_verified=True,
            web_source_url=best_url,
            note=None,
            best_overlap=best_overlap,
        )

    return WebVerifyResult(
        sentence=sentence,
        web_verified=False,
        web_source_url=None,
        note=None,
        best_overlap=best_overlap,
    )


def verify_sentences_on_web(
    sentences: Sequence[str],
    max_calls: int = config.WEB_VERIFY_MAX_CALLS,
) -> List[WebVerifyResult]:
    """
    Stage 2 over a shortlist of sentences, hard-capped at `max_calls`.
    """
    results: List[WebVerifyResult] = []
    for i, sentence in enumerate(sentences):
        if i >= max_calls:
            results.append(
                WebVerifyResult(
                    sentence=sentence,
                    web_verified=None,
                    web_source_url=None,
                    note=f"skipped: document rate limit ({max_calls} calls)",
                )
            )
            continue
        results.append(verify_sentence_on_web(sentence))
    return results
