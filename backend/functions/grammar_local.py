"""
functions/grammar_local.py — local hybrid grammar checker (no network, no LLM API).

Two "detectors" look at every sentence:
  1. Spell-checker (pyspellchecker) — flags unknown words, skipping acronyms,
     identifiers, numbers, URLs, proper nouns and whitelisted technical terms.
  2. Fine-tuned flan-t5-base (brain/ml/models/t5_grammar_v3) — rewrites the
     sentence; the difference between input and output becomes word-level edits.
Their findings are merged into one list of SUGGESTIONS (never auto-applied).

Main entry point:
    check(text_or_sentences) -> list of issue dicts
Each issue has: unit_index, sentence_index, char_start, char_end, original,
suggestion, grammar_type ("spelling"|"grammar"|"punctuation"),
source ("spell"|"model"|"both"), reason.

Env vars (all optional):
    GRAMMAR_MODEL_PATH    model folder (default brain/ml/models/t5_grammar_v3)
    GRAMMAR_USE_MODEL     true (default) | false  -> spell-checker only
    GRAMMAR_BEAMS         beam search width (default 1 = greedy; 4 was ~2.6x slower, same quality)
    GRAMMAR_BATCH_SIZE    sentences per model call (default 16; sentences are sorted by length first)
    GRAMMAR_THREADS       torch CPU threads (default 4)
    GRAMMAR_EXTRA_WORDS   user word list (default functions/grammar_extra_words.txt)
The model always runs on CPU (no mps/cuda).
"""

from __future__ import annotations

import difflib
import hashlib
import importlib.util
import json
import os
import re
import threading
import time
import unicodedata
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

ML_DIR = Path(__file__).resolve().parents[2] / "brain" / "ml"
DEFAULT_MODEL_PATH = ML_DIR / "models" / "t5_grammar_v3"
WHITELIST_PATH = ML_DIR / "models" / "grammar_spell_whitelist.json"
DEFAULT_EXTRA_WORDS = Path(__file__).resolve().parent / "grammar_extra_words.txt"

PREFIX = "Fix grammar: "          # must match training exactly
INPUT_MAX_LENGTH = 160
MAX_NEW_TOKENS = 128
DEFAULT_BEAMS = 1
DEFAULT_BATCH_SIZE = 16
DEFAULT_THREADS = 4

MIN_WORDS = 4                     # shorter sentences are skipped
MAX_WORDS = 80
MIN_TOKEN_SIMILARITY = 0.7        # below -> model output is a heavy rewrite, dropped
LENGTH_RATIO = (0.7, 1.4)
MIN_SPELL_WORD_LEN = 3            # "very short tokens" are never spell-checked
CACHE_SIZE = 50_000


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _log(msg: str) -> None:
    # Never log sentence text here — only counts / timings / errors.
    print(f"[grammar] {msg}", flush=True)


def num_beams() -> int:
    return _env_int("GRAMMAR_BEAMS", DEFAULT_BEAMS)


def configure_torch_threads() -> None:
    """torch.set_num_threads(GRAMMAR_THREADS, default 4). Called at server
    startup and again before the model loads (cheap, idempotent)."""
    try:
        import torch
        n = _env_int("GRAMMAR_THREADS", DEFAULT_THREADS)
        if torch.get_num_threads() != n:
            torch.set_num_threads(n)
    except Exception as exc:
        _log(f"could not set torch threads: {exc}")


# ═════════════════════════════════════════════════════════════════════════════
# Sentence splitting — reuses the regexes from brain/ml/extract_grammar_sentences.py
# (the same rules that produced the training sentences), but keeps character
# offsets so issues can point back into the original paragraph.
# ═════════════════════════════════════════════════════════════════════════════

def _load_extract_rules():
    path = ML_DIR / "extract_grammar_sentences.py"
    try:
        spec = importlib.util.spec_from_file_location("_grammar_extract_rules", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # module only defines regexes/functions (main() is guarded)
        return mod.URL, mod.CODE, mod.REQ_ID, mod.BIB, mod.ABBR, mod.SPLIT
    except Exception as exc:  # brain/ml missing → minimal copies so spell-check still works
        _log(f"could not load {path.name} ({exc}); using built-in split rules")
        return (
            re.compile(r"https?://|www\.|\S+@\S+\.\S+", re.I),
            re.compile(r"[{}]|\(\)\s*;|=>|</?\w+>|::|==|\bself\."),
            re.compile(r"^(?:[A-Z]{2,4}[-\s]?\d+(?:[.\-]\d+)*[:.]?)\s+(?=[A-Z])"),
            re.compile(r"\bpp\.\s*\d|\bvol\.\s*\d|\bet al\.,\s*[“\"]"),
            ["e.g.", "i.e.", "etc.", "et al.", "vs.", "Fig.", "fig.", "No.", "no.", "Dr.", "Mr.", "Ms.", "Prof.", "approx."],
            re.compile(r'(?<=[.!?])\s+(?=["“(\[]?[A-Z0-9])'),
        )


URL_RE, CODE_RE, REQ_ID_RE, BIB_RE, ABBR, SPLIT_RE = _load_extract_rules()
URL_TOKEN_RE = re.compile(r"https?://\S+|www\.\S+|\S+@\S+\.\S+", re.I)
TOKEN_RE = re.compile(r"\w+(?:['’]\w+)*|[^\w\s]", re.UNICODE)
HEADING_STYLES = ("heading", "title", "caption", "toc", "subtitle")


def split_sentence_spans(text: str) -> List[Tuple[int, int]]:
    """(start, end) offsets of sentences in `text`; abbreviations like 'e.g.'
    do not end a sentence (same idea as extract_grammar_sentences.split_sentences)."""
    protected = text
    for a in ABBR:
        protected = protected.replace(a, a.replace(".", "\x00"))  # same length → offsets stay valid
    spans: List[Tuple[int, int]] = []
    pos = 0
    for m in SPLIT_RE.finditer(protected):
        spans.append((pos, m.start()))
        pos = m.end()
    spans.append((pos, len(text)))
    out = []
    for s, e in spans:
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        if e > s:
            out.append((s, e))
    return out


def clean_with_map(raw: str) -> Tuple[str, List[int]]:
    """Same cleaning as extract_grammar_sentences.clean (drop soft hyphen, nbsp →
    space, collapse whitespace) but also returns, for each cleaned char, its index
    in `raw`."""
    out_chars: List[str] = []
    idx: List[int] = []
    prev_space = True  # also strips leading whitespace
    for i, ch in enumerate(raw):
        if ch == "­":
            continue
        if ch == " " or ch.isspace():
            if not prev_space:
                out_chars.append(" ")
                idx.append(i)
            prev_space = True
            continue
        out_chars.append(ch)
        idx.append(i)
        prev_space = False
    while out_chars and out_chars[-1] == " ":
        out_chars.pop()
        idx.pop()
    return "".join(out_chars), idx


def is_spell_checkable(sentence: str) -> bool:
    """Looser rule for spell-check only: headings, labels and short lines are
    fine; code, reference-list and number-heavy lines are still skipped."""
    if not sentence.split() or len(sentence.split()) > MAX_WORDS:
        return False
    if CODE_RE.search(sentence) or BIB_RE.search(sentence):
        return False
    masked = URL_TOKEN_RE.sub("link", sentence)
    letters = sum(c.isalpha() for c in masked)
    if letters < 3 or letters / max(len(masked), 1) < 0.6:
        return False
    return "|" not in sentence and sentence.count("_") <= 1


def is_checkable(sentence: str, for_model: bool = True) -> bool:
    """Skip very short sentences, headings/labels, code-like or number-heavy lines.
    Sentences containing a URL/email are spell-checked (URL masked) but not sent
    to the model, which never saw such sentences in training."""
    words = sentence.split()
    if not (MIN_WORDS <= len(words) <= MAX_WORDS):
        return False
    if CODE_RE.search(sentence) or BIB_RE.search(sentence):
        return False
    if URL_RE.search(sentence):
        if for_model:
            return False
        sentence = URL_TOKEN_RE.sub("link", sentence)
    letters = sum(c.isalpha() for c in sentence)
    if letters / max(len(sentence), 1) < 0.75:
        return False
    if sentence.count(",") > 8 or "|" in sentence or sentence.count("_") > 1:
        return False
    # Heading / label: no final punctuation and short ("Post Condition", "Use Case 3 Login")
    if sentence[-1] not in ".!?:;\"”)" and len(words) < 8:
        return False
    return True


# ═════════════════════════════════════════════════════════════════════════════
# Tokens
# ═════════════════════════════════════════════════════════════════════════════

class Tok:
    __slots__ = ("text", "start", "end")

    def __init__(self, text: str, start: int, end: int):
        self.text, self.start, self.end = text, start, end

    @property
    def is_word(self) -> bool:
        return bool(re.match(r"\w", self.text))

    def __repr__(self) -> str:
        return f"Tok({self.text!r},{self.start},{self.end})"


def tokenize(s: str) -> List[Tok]:
    return [Tok(m.group(), m.start(), m.end()) for m in TOKEN_RE.finditer(s)]


_QUOTES = str.maketrans({"’": "'", "‘": "'", "‚": "'", "`": "'", "´": "'",
                         "“": '"', "”": '"', "„": '"', "«": '"', "»": '"'})


def norm_key(t: str) -> str:
    """Comparison key: ligatures/Unicode width (NFKC) and quote characters are ignored."""
    return unicodedata.normalize("NFKC", t).translate(_QUOTES)


# ═════════════════════════════════════════════════════════════════════════════
# Spell-checker
# ═════════════════════════════════════════════════════════════════════════════

_CAMEL_RE = re.compile(r"[a-z][A-Z]|^[A-Z]{2,}[a-z]")


def should_skip_word(word: str, is_sentence_start: bool, whitelist: Iterable[str] = ()) -> bool:
    """True if this token must never be spell-checked."""
    if len(word) < MIN_SPELL_WORD_LEN:
        return True
    if any(c.isdigit() for c in word) or "_" in word:
        return True
    if not all(c.isalpha() or c in "'’" for c in word):  # non-letter symbols
        return True
    if word.isupper():                                   # ALL-CAPS acronym (RFID, CNIC)
        return True
    if _CAMEL_RE.search(word):                           # camelCase / CamelCase identifiers
        return True
    if word[0].isupper() and not is_sentence_start:      # proper noun mid-sentence (Lahore, Kinect)
        return True
    if word.lower().translate(_QUOTES) in whitelist:
        return True
    return False


class SpellService:
    def __init__(self, extra_words_path: Optional[Path] = None):
        from spellchecker import SpellChecker
        self.spell = SpellChecker()
        self.whitelist = set(self._load_whitelist(extra_words_path))
        self._cand_cache: Dict[str, Optional[str]] = {}

    @staticmethod
    def _load_whitelist(extra_words_path: Optional[Path]) -> List[str]:
        words: List[str] = []
        try:
            with open(WHITELIST_PATH, encoding="utf-8") as fh:
                words.extend(json.load(fh).get("words", []))
        except FileNotFoundError:
            _log(f"no whitelist at {WHITELIST_PATH} (run brain/ml/build_spell_whitelist.py)")
        except Exception as exc:
            _log(f"whitelist load failed: {exc}")
        p = extra_words_path or Path(os.getenv("GRAMMAR_EXTRA_WORDS", str(DEFAULT_EXTRA_WORDS)))
        try:
            with open(p, encoding="utf-8") as fh:
                for line in fh:
                    line = line.split("#", 1)[0].strip()
                    if line:
                        words.append(line)
        except FileNotFoundError:
            pass
        return [w.lower().translate(_QUOTES) for w in words]

    def is_known(self, word: str) -> bool:
        w = word.lower().translate(_QUOTES)
        if w in self.whitelist or w in self.spell:
            return True
        for suffix in ("'s", "'"):                       # possessives: system's, users'
            if w.endswith(suffix) and w[: -len(suffix)] in self.spell:
                return True
        return False

    def candidate(self, word: str) -> Optional[str]:
        w = word.lower().translate(_QUOTES)
        if w not in self._cand_cache:
            c = self.spell.correction(w)
            if not c or c == w:
                c = self._squeeze_candidate(w)
            self._cand_cache[w] = c if c and c != w else None
        c = self._cand_cache[w]
        if c and word[:1].isupper():
            c = c[:1].upper() + c[1:]
        return c

    def _squeeze_candidate(self, w: str) -> Optional[str]:
        """Typos with a long run of one letter ("abstractttttttt") are too far
        from any word for the normal edit-distance search; shrink the run."""
        if not re.search(r"(.)\1{2,}", w):
            return None
        for squeezed in (re.sub(r"(.)\1{2,}", r"\1\1", w), re.sub(r"(.)\1{2,}", r"\1", w)):
            if squeezed in self.spell:
                return squeezed
        c = self.spell.correction(re.sub(r"(.)\1{2,}", r"\1\1", w))
        return c

    def check_tokens(self, toks: Sequence[Tok], title_line: bool = False) -> List[Dict[str, Any]]:
        """Spelling issues as {tok_index, word, candidate}. Tokens inside URLs/emails
        are expected to be removed by the caller. In a heading/title line
        (`title_line`) capitalised words are checked too, since every word is
        capitalised there."""
        out = []
        first_word = next((i for i, t in enumerate(toks) if t.is_word), -1)
        for i, t in enumerate(toks):
            if not t.is_word:
                continue
            if should_skip_word(t.text, title_line or i == first_word, self.whitelist):
                continue
            if self.is_known(t.text):
                continue
            cand = self.candidate(t.text)
            if cand:                                      # no candidate → probably a name/term
                out.append({"tok_index": i, "word": t.text, "candidate": cand})
        return out


# ═════════════════════════════════════════════════════════════════════════════
# Model → word-level edits
# ═════════════════════════════════════════════════════════════════════════════

def extract_edits(src: str, out: str) -> Optional[List[Dict[str, Any]]]:
    """Diff model input vs output on tokens.

    Returns None if the output must be discarded (empty / heavy rewrite), else a
    list of edits {i1, i2, j1, j2} (token ranges in src / out). Whitespace,
    quote-character and Unicode-normalisation differences are not edits.
    """
    if not out or not out.strip():
        return None
    a, b = tokenize(src), tokenize(out)
    if not a:
        return None
    ka = [norm_key(t.text) for t in a]
    kb = [norm_key(t.text) for t in b]
    if ka == kb:
        return []
    ratio = len(b) / len(a)
    if not (LENGTH_RATIO[0] <= ratio <= LENGTH_RATIO[1]):
        return None
    sm = difflib.SequenceMatcher(None, ka, kb, autojunk=False)
    if sm.ratio() < MIN_TOKEN_SIMILARITY:
        return None
    edits = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if edits and edits[-1]["i2"] == i1 and edits[-1]["j2"] == j1:  # glue adjacent changes
            edits[-1]["i2"], edits[-1]["j2"] = i2, j2
        else:
            edits.append({"i1": i1, "i2": i2, "j1": j1, "j2": j2})
    return edits


def _is_punct_only(a_toks: Sequence[Tok], b_toks: Sequence[Tok]) -> bool:
    wa = [t.text for t in a_toks if t.is_word]
    wb = [t.text for t in b_toks if t.is_word]
    return wa == wb


def _close_spelling(a: str, b: str) -> bool:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() >= 0.75


def classify(a_toks: Sequence[Tok], b_toks: Sequence[Tok], spell: Optional[SpellService]) -> str:
    """punctuation-only → 'punctuation'; one unknown word replaced by a close
    spelling → 'spelling'; anything else → 'grammar'."""
    if _is_punct_only(a_toks, b_toks):
        return "punctuation"
    wa = [t for t in a_toks if t.is_word]
    wb = [t for t in b_toks if t.is_word]
    if (len(wa) == 1 and len(wb) == 1 and spell is not None
            and not spell.is_known(wa[0].text) and _close_spelling(wa[0].text, wb[0].text)):
        return "spelling"
    return "grammar"


# ═════════════════════════════════════════════════════════════════════════════
# Grammar model (lazy singleton + per-sentence cache)
# ═════════════════════════════════════════════════════════════════════════════

class GrammarModel:
    def __init__(self):
        self._lock = threading.Lock()
        self._tok = None
        self._model = None
        self._device = "cpu"
        self.failed = False
        self.error = ""
        self._cache: "OrderedDict[str, str]" = OrderedDict()

    @property
    def path(self) -> Path:
        p = Path(os.getenv("GRAMMAR_MODEL_PATH", str(DEFAULT_MODEL_PATH)))
        if not p.is_absolute() and not p.exists():
            p = ML_DIR / p
        return p

    def _ensure_loaded(self) -> bool:
        if self._model is not None:
            return True
        if self.failed:
            return False
        try:
            t0 = time.time()
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            path = self.path
            try:
                with open(path / "config.json", encoding="utf-8") as fh:
                    if json.load(fh).get("tie_word_embeddings", False):
                        _log("WARNING: tie_word_embeddings is true in config.json — outputs may be garbage")
            except Exception:
                pass
            configure_torch_threads()
            dev = "cpu"  # CPU only (no Apple GPU on the target Mac; mps not used)
            if os.getenv("GRAMMAR_DEVICE", "cpu").strip().lower() not in ("", "cpu"):
                _log("GRAMMAR_DEVICE is ignored; the grammar model always runs on cpu")
            self._tok = AutoTokenizer.from_pretrained(str(path), local_files_only=True)
            self._model = AutoModelForSeq2SeqLM.from_pretrained(str(path), local_files_only=True).to(dev).eval()
            self._device = dev
            _log(f"model loaded from {path.name} on {dev} ({torch.get_num_threads()} threads, "
                 f"beams={num_beams()}) in {time.time() - t0:.1f}s")
            return True
        except Exception as exc:
            self.failed = True
            self.error = str(exc)
            self._tok = self._model = None
            _log(f"model load FAILED, falling back to spell-checker only: {exc}")
            return False

    @staticmethod
    def _key(s: str) -> str:
        return hashlib.sha1(s.encode("utf-8")).hexdigest()

    def correct(self, sentences: Sequence[str], batch_size: int = DEFAULT_BATCH_SIZE,
                progress: Optional[Callable[[int, int], None]] = None,
                on_batch: Optional[Callable[[List[int], List[str]], None]] = None,
                cancelled: Optional[Callable[[], bool]] = None) -> Optional[List[Optional[str]]]:
        """Corrected sentence per input, in input order (None where generation
        failed). Returns None if the model is unavailable.

        Uncached sentences are sorted by length and run in batches of
        `batch_size` (less padding); results are written back by original index.
        `on_batch(indices, outputs)` is called for cached sentences first, then
        after every batch, so callers can stream results."""
        with self._lock:  # one generate() at a time; torch already uses all cores
            if not self._ensure_loaded():
                return None
            import torch

            beams = num_beams()
            results: List[Optional[str]] = [None] * len(sentences)
            todo: List[int] = []
            for i, s in enumerate(sentences):
                k = self._key(s)
                if k in self._cache:
                    self._cache.move_to_end(k)
                    results[i] = self._cache[k]
                else:
                    todo.append(i)
            todo.sort(key=lambda i: len(sentences[i]))  # stable → equal lengths keep document order
            total = len(sentences)
            cached = [i for i in range(total) if results[i] is not None]
            if cached and on_batch is not None:
                on_batch(cached, [results[i] for i in cached])
            _notify(progress, total - len(todo), total)   # cached sentences are already done
            for b in range(0, len(todo), batch_size):
                if cancelled is not None and cancelled():
                    _log("model pass cancelled (a newer analysis started)")
                    break
                idxs = todo[b: b + batch_size]
                try:
                    enc = self._tok([PREFIX + sentences[i] for i in idxs], return_tensors="pt",
                                    padding=True, truncation=True, max_length=INPUT_MAX_LENGTH).to(self._device)
                    with torch.no_grad():
                        gen = self._model.generate(**enc, num_beams=beams, max_new_tokens=MAX_NEW_TOKENS)
                    outs = self._tok.batch_decode(gen, skip_special_tokens=True)
                except Exception as exc:
                    _log(f"generation failed for a batch of {len(idxs)} (spell-check only there): {exc}")
                    continue
                for i, o in zip(idxs, outs):
                    results[i] = o
                    self._cache[self._key(sentences[i])] = o
                while len(self._cache) > CACHE_SIZE:
                    self._cache.popitem(last=False)
                if on_batch is not None:
                    on_batch(list(idxs), list(outs))
                _notify(progress, total - len(todo) + min(b + batch_size, len(todo)), total)
            return results


def _notify(progress: Optional[Callable[[int, int], None]], done: int, total: int) -> None:
    if progress is None:
        return
    try:
        progress(done, total)
    except Exception:
        pass  # progress reporting must never break grammar


_MODEL = GrammarModel()
_SPELL: Optional[SpellService] = None
_SPELL_LOCK = threading.Lock()


def get_spell() -> Optional[SpellService]:
    global _SPELL
    with _SPELL_LOCK:
        if _SPELL is None:
            try:
                _SPELL = SpellService()
            except Exception as exc:
                _log(f"spell-checker unavailable: {exc}")
                return None
        return _SPELL


# ═════════════════════════════════════════════════════════════════════════════
# Merge
# ═════════════════════════════════════════════════════════════════════════════

def merge_sentence(
    src: str,
    toks: Sequence[Tok],
    spell_hits: Sequence[Dict[str, Any]],
    model_out: Optional[str],
    spell: Optional[SpellService],
) -> List[Dict[str, Any]]:
    """Combine spell-checker hits and model edits for ONE cleaned sentence.

    Returns edits with offsets into `src`:
    {start, end, original, suggestion, grammar_type, source}
    """
    out_toks = tokenize(model_out) if model_out else []
    edits = extract_edits(src, model_out) if model_out is not None else None
    edits = edits or []
    results: List[Dict[str, Any]] = []
    used_spell: set = set()

    def _valid_words(ts: Sequence[Tok]) -> bool:
        return spell is None or all(spell.is_known(t.text) or not t.is_word or
                                    should_skip_word(t.text, True, spell.whitelist) for t in ts)

    for e in edits:
        i1, i2, j1, j2 = e["i1"], e["i2"], e["j1"], e["j2"]
        core_a, core_b = list(toks[i1:i2]), list(out_toks[j1:j2])
        overlapping = [h for h in spell_hits if i1 <= h["tok_index"] < i2]
        source = "model"
        if overlapping:
            if _valid_words(core_b):
                source = "both"
                used_spell.update(h["tok_index"] for h in overlapping)
            else:
                # Model replacement isn't a real word → trust the spell-checker there.
                for h in overlapping:
                    h["source"] = "both"
                continue
        gtype = classify(core_a, core_b, spell)
        # Pure insertion / deletion → widen by one neighbouring (unchanged) token
        # so both "original" and "suggestion" are non-empty and easy to read.
        if i1 == i2 or j1 == j2:
            if i1 > 0 and j1 > 0:
                i1, j1 = i1 - 1, j1 - 1
            elif i2 < len(toks) and j2 < len(out_toks):
                i2, j2 = i2 + 1, j2 + 1
            else:
                continue
        start, end = toks[i1].start, toks[i2 - 1].end
        suggestion = model_out[out_toks[j1].start: out_toks[j2 - 1].end]
        if norm_key(src[start:end]) == norm_key(suggestion):
            continue
        results.append({"start": start, "end": end, "original": src[start:end],
                        "suggestion": suggestion, "grammar_type": gtype, "source": source})

    for h in spell_hits:
        if h["tok_index"] in used_spell:
            continue
        t = toks[h["tok_index"]]
        results.append({"start": t.start, "end": t.end, "original": t.text,
                        "suggestion": h["candidate"], "grammar_type": "spelling",
                        "source": h.get("source", "spell")})
    results.sort(key=lambda r: r["start"])
    return results


def _spell_hits_for(src: str, toks: Sequence[Tok], spell: Optional[SpellService],
                    title_line: bool = False) -> List[Dict[str, Any]]:
    if spell is None:
        return []
    masked = [(m.start(), m.end()) for m in URL_TOKEN_RE.finditer(src)]
    hits = spell.check_tokens(toks, title_line=title_line)
    return [h for h in hits
            if not any(s <= toks[h["tok_index"]].start < e for s, e in masked)]


def _unique_span(text: str, start: int, end: int, suggestion: str, lo: int, hi: int) -> Tuple[int, int, str]:
    """Grow [start,end) by whole words (within [lo,hi)) until text[start:end]
    occurs once in `text`, so 'Apply Fix' replaces the right occurrence."""
    while text.count(text[start:end]) > 1 and (start > lo or end < hi):
        if start > lo:
            ns = start
            while ns > lo and text[ns - 1].isspace():
                ns -= 1
            while ns > lo and not text[ns - 1].isspace():
                ns -= 1
            suggestion = text[ns:start] + suggestion
            start = ns
        else:
            ne = end
            while ne < hi and text[ne].isspace():
                ne += 1
            while ne < hi and not text[ne].isspace():
                ne += 1
            suggestion = suggestion + text[end:ne]
            end = ne
    return start, end, suggestion


# ═════════════════════════════════════════════════════════════════════════════
# Public API
# ═════════════════════════════════════════════════════════════════════════════

_REASONS = {
    "spelling": "Possible spelling mistake.",
    "grammar": "Possible grammar issue — please review the suggestion.",
    "punctuation": "Possible punctuation issue — please review the suggestion.",
}


def check(
    text_or_sentences: Union[str, Sequence[str]],
    *,
    use_model: Optional[bool] = None,
    batch_size: Optional[int] = None,
    progress: Optional[Callable[[int, int], None]] = None,
    spell_only_units: Optional[Iterable[int]] = None,
    on_update: Optional[Callable[[List[Dict[str, Any]], int, int], None]] = None,
    cancelled: Optional[Callable[[], bool]] = None,
) -> List[Dict[str, Any]]:
    """Check one text or a list of texts (sentences or paragraphs).

    Every input item is a "unit"; it is split into sentences internally.
    Offsets (char_start/char_end) are relative to the unit's original text.
    Never raises because of the model — on failure it falls back to spell-check.
    `progress(done, total)` is called as model sentences finish (optional).
    `on_update(issues, done, total)` (optional) receives the full current issue
    list: first the spell-checker results (before the model runs), then again
    after every model batch, with model suggestions merged in for the sentences
    the model has finished. `done`/`total` count model sentences.
    Units in `spell_only_units` (e.g. headings) and short lines/labels are only
    spell-checked; the model never sees them.
    """
    spell_only = set(spell_only_units or ())
    units = [text_or_sentences] if isinstance(text_or_sentences, str) else list(text_or_sentences)
    if use_model is None:
        use_model = _env_bool("GRAMMAR_USE_MODEL", True)
    if batch_size is None:
        batch_size = _env_int("GRAMMAR_BATCH_SIZE", DEFAULT_BATCH_SIZE)

    spell = get_spell()
    # 1) collect checkable sentences
    sents: List[Dict[str, Any]] = []
    sent_counter = 0
    for ui, raw in enumerate(units):
        raw = raw or ""
        for s, e in split_sentence_spans(raw):
            clean, cmap = clean_with_map(raw[s:e])
            if not clean:
                continue
            m = REQ_ID_RE.match(clean)          # "FR18-03 The system ..." → "The system ..."
            off = m.end() if m else 0
            clean, cmap = clean[off:], cmap[off:]
            sidx = sent_counter
            sent_counter += 1
            if not clean:
                continue
            full = ui not in spell_only and is_checkable(clean, for_model=False)
            if not full and not is_spell_checkable(clean):
                continue
            sents.append({"unit": ui, "sentence_index": sidx, "src": clean,
                          "cmap": [s + c for c in cmap], "span": (s, e),
                          "model_ok": full and is_checkable(clean, for_model=True),
                          "title_line": not full})

    # 2) spell-check every sentence now (fast) → first result set, before the model
    for x in sents:
        x["toks"] = tokenize(x["src"])
        x["hits"] = _spell_hits_for(x["src"], x["toks"], spell, title_line=x["title_line"])

    def sentence_issues(x: Dict[str, Any], mo: Optional[str], model_used: bool) -> List[Dict[str, Any]]:
        # merge_sentence may tag hits (source="both"), so give it fresh copies
        hits = [dict(h) for h in x["hits"]]
        out = []
        for ed in merge_sentence(x["src"], x["toks"], hits, mo, spell):
            raw = units[x["unit"]] or ""
            cmap = x["cmap"]
            rs, re_ = cmap[ed["start"]], cmap[ed["end"] - 1] + 1
            # suggestion keeps the raw text's surrounding characters intact
            rs, re_, sugg = _unique_span(raw, rs, re_, ed["suggestion"], *x["span"])
            out.append({
                "unit_index": x["unit"],
                "sentence_index": x["sentence_index"],
                "char_start": rs,
                "char_end": re_,
                "original": raw[rs:re_],
                "suggestion": sugg,
                "grammar_type": ed["grammar_type"],
                "source": ed["source"],
                "reason": _REASONS[ed["grammar_type"]],
                "sentence": raw[x["span"][0]: x["span"][1]],
                "model_used": model_used,
            })
        return out

    per_sentence = [sentence_issues(x, None, False) for x in sents]

    def flat() -> List[Dict[str, Any]]:
        return [iss for lst in per_sentence for iss in lst]

    model_idx = [i for i, x in enumerate(sents) if x["model_ok"]] if use_model else []
    model_done = 0
    if on_update is not None:
        try:
            on_update(flat(), 0, len(model_idx))
        except Exception as exc:
            _log(f"on_update failed: {exc}")

    # 3) model in length-sorted batches (cached per sentence); re-merge each
    #    finished sentence and push the updated list to the caller
    if model_idx:
        def on_batch(idxs: List[int], outs: List[str]) -> None:
            nonlocal model_done
            for j, o in zip(idxs, outs):
                si = model_idx[j]
                per_sentence[si] = sentence_issues(sents[si], o, True)
            model_done += len(idxs)
            if on_update is not None:
                try:
                    on_update(flat(), model_done, len(model_idx))
                except Exception as exc:
                    _log(f"on_update failed: {exc}")

        try:
            _MODEL.correct([sents[i]["src"] for i in model_idx], batch_size=batch_size,
                           progress=progress, on_batch=on_batch, cancelled=cancelled)
        except Exception as exc:  # absolutely never break the report
            _log(f"model crashed, spell-checker only: {exc}")
    return flat()


def model_status() -> Dict[str, Any]:
    return {"loaded": _MODEL._model is not None, "failed": _MODEL.failed,
            "error": _MODEL.error, "path": str(_MODEL.path)}
