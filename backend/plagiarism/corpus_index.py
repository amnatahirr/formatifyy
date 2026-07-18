"""
plagiarism/corpus_index.py — Build, cache, and load the local reference corpus indexes.

Why this exists (FYP):
  Stage 1 of plagiarism detection must be fully local, deterministic, and cheap.
  Precomputing MinHashLSH (near-exact) and FAISS (semantic) indexes once means
  every subsequent document check is a fast query against disk-cached artefacts
  instead of re-embedding / re-hashing the entire corpus on every run.
"""

from __future__ import annotations

import hashlib
import pickle
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import faiss
import numpy as np
from datasketch import MinHash, MinHashLSH

from plagiarism import config
from plagiarism.text_extract import extract_text_from_file, iter_corpus_files


# ── Text helpers (pure, unit-testable) ───────────────────────────────────────

_WORD_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?", re.IGNORECASE)


def tokenize(text: str) -> List[str]:
    """Lowercase word tokens suitable for shingling and Jaccard."""
    return [m.group(0).lower() for m in _WORD_RE.finditer(text or "")]


def make_shingles(words: Sequence[str], size: int = config.SHINGLE_SIZE) -> List[str]:
    """
    Build contiguous word n-grams (shingles).

    Shorter texts than `size` yield a single joined shingle so MinHash still
    has at least one feature.
    """
    if not words:
        return []
    if len(words) < size:
        return [" ".join(words)]
    return [" ".join(words[i : i + size]) for i in range(len(words) - size + 1)]


def text_to_minhash(
    text: str,
    num_perm: int = config.MINHASH_NUM_PERM,
    shingle_size: int = config.SHINGLE_SIZE,
) -> MinHash:
    """Create a MinHash signature from word shingles of `text`."""
    mh = MinHash(num_perm=num_perm)
    words = tokenize(text)
    shingles = make_shingles(words, shingle_size)
    if not shingles:
        # Empty signature — Jaccard vs anything will be ~0.
        return mh
    for shingle in shingles:
        mh.update(shingle.encode("utf-8"))
    return mh


def jaccard_from_minhash(a: MinHash, b: MinHash) -> float:
    """Estimated Jaccard similarity between two MinHash signatures."""
    return float(a.jaccard(b))


def split_into_sentences(text: str) -> List[str]:
    """
    Lightweight sentence splitter for corpus documents and input chunks.

    Not a full NLP sentence segmenter — good enough for plagiarism chunking and
    keeps the module free of heavy NLP downloads beyond sentence-transformers.
    """
    if not text or not text.strip():
        return []
    # Split on punctuation followed by whitespace / end, keep abbreviations crude.
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def corpus_fingerprint(corpus_dir: Path) -> str:
    """
    Hash of corpus file names + mtimes + sizes so we can invalidate stale caches.
    """
    h = hashlib.sha256()
    if not corpus_dir.exists():
        return h.hexdigest()
    for path in iter_corpus_files(corpus_dir):
        stat = path.stat()
        h.update(path.name.encode("utf-8"))
        h.update(str(stat.st_mtime_ns).encode("utf-8"))
        h.update(str(stat.st_size).encode("utf-8"))
    return h.hexdigest()


# ── Corpus data structures ───────────────────────────────────────────────────

@dataclass
class CorpusDocument:
    """One reference document from the local .txt corpus folder."""
    doc_id: str
    filename: str
    text: str
    sentences: List[str] = field(default_factory=list)


@dataclass
class CorpusIndex:
    """
    In-memory handle to both Stage-1 indexes plus aligned metadata.

    `sentence_sources[i]` is the corpus doc_id / filename for FAISS vector i.
    `sentence_texts[i]` is the exact corpus sentence for vector i.
    `minhash_keys` maps LSH key → (doc_id, sentence_text, MinHash).
    """
    documents: List[CorpusDocument]
    lsh: MinHashLSH
    minhash_by_key: Dict[str, Tuple[str, str, MinHash]]
    faiss_index: Any  # faiss.Index
    sentence_texts: List[str]
    sentence_sources: List[str]
    embedding_dim: int
    fingerprint: str

    @property
    def size(self) -> int:
        """Number of corpus documents (not sentences)."""
        return len(self.documents)

    @property
    def sentence_count(self) -> int:
        return len(self.sentence_texts)


# ── Loading corpus text ──────────────────────────────────────────────────────

def load_corpus_documents(corpus_dir: Path) -> List[CorpusDocument]:
    """
    Load every supported reference file under `corpus_dir` as a CorpusDocument.

    Accepts ``.txt``, ``.docx``, and ``.pdf``. Prefer ingesting to ``.txt`` via
    ``python -m plagiarism.ingest_corpus`` for faster reloads.

    Raises ValueError with a clear message if the folder is missing or empty.
    """
    corpus_dir = Path(corpus_dir)
    if not corpus_dir.exists():
        raise ValueError(
            f"Corpus directory does not exist: {corpus_dir}. "
            "Create plagiarism/fyp_corpus (or set PLAGIARISM_CORPUS_DIR) and add "
            "FYP reports, or run: python -m plagiarism.ingest_corpus"
        )
    paths = iter_corpus_files(corpus_dir)
    if not paths:
        raise ValueError(
            f"Corpus directory is empty (no .txt/.docx/.pdf files): {corpus_dir}. "
            "Copy reports into plagiarism/fyp_reports_raw and run "
            "`python -m plagiarism.ingest_corpus`, or place .txt files here directly."
        )

    documents: List[CorpusDocument] = []
    for path in paths:
        try:
            text = extract_text_from_file(path)
        except Exception as exc:
            print(f"[plagiarism.corpus_index] skip {path.name}: {exc}")
            continue
        if not text:
            continue
        doc_id = path.stem
        documents.append(
            CorpusDocument(
                doc_id=doc_id,
                filename=path.name,
                text=text,
                sentences=split_into_sentences(text),
            )
        )

    if not documents:
        raise ValueError(
            f"All corpus files in {corpus_dir} were empty or unreadable. "
            "Corpus must contain non-empty reference text."
        )
    return documents


# ── Embedding model (lazy singleton) ─────────────────────────────────────────

_embedding_model = None


def get_embedding_model(model_name: str = config.EMBEDDING_MODEL_NAME):
    """
    Lazy-load sentence-transformers model once per process.

    Kept local — no LLM / remote embedding APIs.
    """
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        _embedding_model = SentenceTransformer(model_name)
    return _embedding_model


def embed_texts(texts: Sequence[str], normalize: bool = True) -> np.ndarray:
    """
    Embed a batch of strings → float32 matrix (N, D).

    When `normalize=True`, L2-normalises rows so IndexFlatIP ≈ cosine similarity.
    """
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    model = get_embedding_model()
    vectors = model.encode(
        list(texts),
        convert_to_numpy=True,
        show_progress_bar=False,
        normalize_embeddings=normalize,
    )
    return np.asarray(vectors, dtype=np.float32)


# ── Build indexes ────────────────────────────────────────────────────────────

def _build_minhash_lsh(
    documents: Sequence[CorpusDocument],
) -> Tuple[MinHashLSH, Dict[str, Tuple[str, str, MinHash]]]:
    """Index every sufficiently long corpus sentence under MinHashLSH."""
    lsh = MinHashLSH(threshold=config.LSH_THRESHOLD, num_perm=config.MINHASH_NUM_PERM)
    minhash_by_key: Dict[str, Tuple[str, str, MinHash]] = {}

    for doc in documents:
        for idx, sentence in enumerate(doc.sentences):
            words = tokenize(sentence)
            if len(words) < config.MIN_SENTENCE_WORDS:
                continue
            key = f"{doc.doc_id}::{idx}"
            mh = text_to_minhash(sentence)
            # Skip duplicate keys if LSH already has them (re-insert would error).
            if key in minhash_by_key:
                continue
            lsh.insert(key, mh)
            minhash_by_key[key] = (doc.filename, sentence, mh)

    return lsh, minhash_by_key


def _build_faiss_index(
    documents: Sequence[CorpusDocument],
) -> Tuple[Any, List[str], List[str], int]:
    """
    Embed corpus sentences and build a FAISS IndexFlatIP (cosine via L2-norm).
    """
    sentence_texts: List[str] = []
    sentence_sources: List[str] = []

    for doc in documents:
        for sentence in doc.sentences:
            if len(tokenize(sentence)) < config.MIN_SENTENCE_WORDS:
                continue
            sentence_texts.append(sentence)
            sentence_sources.append(doc.filename)

    if not sentence_texts:
        raise ValueError(
            "No corpus sentences met MIN_SENTENCE_WORDS; cannot build FAISS index."
        )

    embeddings = embed_texts(sentence_texts, normalize=True)
    dim = int(embeddings.shape[1])
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    return index, sentence_texts, sentence_sources, dim


def build_corpus_index(
    corpus_dir: Optional[Path] = None,
    cache_dir: Optional[Path] = None,
    force_rebuild: bool = False,
) -> CorpusIndex:
    """
    Build (or load from cache) MinHashLSH + FAISS indexes for the local corpus.

    Caches are invalidated automatically when any corpus ``.txt`` file changes
    (name / mtime / size fingerprint).

    Args:
        corpus_dir: Folder of reference files (.txt/.docx/.pdf). Defaults to config.CORPUS_DIR.
        cache_dir: Where to write pickle / FAISS artefacts. Defaults to config.INDEX_CACHE_DIR.
        force_rebuild: Ignore existing cache and recompute.

    Returns:
        CorpusIndex ready for Stage-1 queries.
    """
    corpus_dir = Path(corpus_dir or config.CORPUS_DIR)
    cache_dir = Path(cache_dir or config.INDEX_CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)

    fingerprint = corpus_fingerprint(corpus_dir)

    if not force_rebuild:
        loaded = _try_load_cached(cache_dir, fingerprint)
        if loaded is not None:
            return loaded

    documents = load_corpus_documents(corpus_dir)
    lsh, minhash_by_key = _build_minhash_lsh(documents)
    faiss_index, sentence_texts, sentence_sources, dim = _build_faiss_index(documents)

    index = CorpusIndex(
        documents=documents,
        lsh=lsh,
        minhash_by_key=minhash_by_key,
        faiss_index=faiss_index,
        sentence_texts=sentence_texts,
        sentence_sources=sentence_sources,
        embedding_dim=dim,
        fingerprint=fingerprint,
    )
    save_corpus_index(index, cache_dir)
    return index


def save_corpus_index(index: CorpusIndex, cache_dir: Optional[Path] = None) -> None:
    """Persist MinHashLSH, FAISS, and aligned metadata to disk."""
    cache_dir = Path(cache_dir or config.INDEX_CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)

    with open(cache_dir / config.MINHASH_INDEX_FILE.name, "wb") as f:
        pickle.dump(
            {
                "lsh": index.lsh,
                "minhash_by_key": index.minhash_by_key,
            },
            f,
        )

    faiss.write_index(index.faiss_index, str(cache_dir / config.FAISS_INDEX_FILE.name))

    with open(cache_dir / config.FAISS_META_FILE.name, "wb") as f:
        pickle.dump(
            {
                "sentence_texts": index.sentence_texts,
                "sentence_sources": index.sentence_sources,
                "embedding_dim": index.embedding_dim,
            },
            f,
        )

    with open(cache_dir / config.CORPUS_META_FILE.name, "wb") as f:
        pickle.dump(
            {
                "fingerprint": index.fingerprint,
                "documents": [
                    {
                        "doc_id": d.doc_id,
                        "filename": d.filename,
                        "text": d.text,
                        "sentences": d.sentences,
                    }
                    for d in index.documents
                ],
            },
            f,
        )


def load_corpus_index(cache_dir: Optional[Path] = None) -> CorpusIndex:
    """
    Load a previously saved corpus index from disk.

    Raises FileNotFoundError / ValueError if cache is incomplete.
    """
    cache_dir = Path(cache_dir or config.INDEX_CACHE_DIR)
    loaded = _try_load_cached(cache_dir, expected_fingerprint=None)
    if loaded is None:
        raise FileNotFoundError(
            f"No valid plagiarism corpus cache found in {cache_dir}. "
            "Call build_corpus_index() first."
        )
    return loaded


def _try_load_cached(
    cache_dir: Path,
    expected_fingerprint: Optional[str],
) -> Optional[CorpusIndex]:
    """Return CorpusIndex if all cache files exist and fingerprint matches."""
    minhash_path = cache_dir / config.MINHASH_INDEX_FILE.name
    faiss_path = cache_dir / config.FAISS_INDEX_FILE.name
    faiss_meta_path = cache_dir / config.FAISS_META_FILE.name
    corpus_meta_path = cache_dir / config.CORPUS_META_FILE.name

    if not all(p.exists() for p in (minhash_path, faiss_path, faiss_meta_path, corpus_meta_path)):
        return None

    try:
        with open(corpus_meta_path, "rb") as f:
            corpus_meta = pickle.load(f)
        if expected_fingerprint is not None and corpus_meta.get("fingerprint") != expected_fingerprint:
            return None

        with open(minhash_path, "rb") as f:
            mh_payload = pickle.load(f)
        with open(faiss_meta_path, "rb") as f:
            faiss_meta = pickle.load(f)

        faiss_index = faiss.read_index(str(faiss_path))
        documents = [
            CorpusDocument(
                doc_id=d["doc_id"],
                filename=d["filename"],
                text=d["text"],
                sentences=d.get("sentences", []),
            )
            for d in corpus_meta["documents"]
        ]
        return CorpusIndex(
            documents=documents,
            lsh=mh_payload["lsh"],
            minhash_by_key=mh_payload["minhash_by_key"],
            faiss_index=faiss_index,
            sentence_texts=faiss_meta["sentence_texts"],
            sentence_sources=faiss_meta["sentence_sources"],
            embedding_dim=faiss_meta["embedding_dim"],
            fingerprint=corpus_meta["fingerprint"],
        )
    except Exception as exc:
        print(f"[plagiarism.corpus_index] cache load failed, will rebuild: {exc}")
        return None
