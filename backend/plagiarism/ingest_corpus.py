"""
plagiarism/ingest_corpus.py — Convert raw FYP reports into the indexed corpus folder.

Usage (from backend/):
  python -m plagiarism.ingest_corpus
  python -m plagiarism.ingest_corpus --raw-dir plagiarism/fyp_reports_raw --out-dir plagiarism/fyp_corpus
  python -m plagiarism.ingest_corpus --rebuild-index
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from plagiarism import config
from plagiarism.text_extract import SUPPORTED_EXTENSIONS, extract_text_from_file


def _safe_stem(path: Path) -> str:
    """Filesystem-safe document id from filename."""
    stem = path.stem.strip() or "document"
    stem = re.sub(r"[^\w.\-]+", "_", stem, flags=re.UNICODE)
    return stem[:180]


def ingest_reports(
    raw_dir: Path,
    out_dir: Path,
    *,
    overwrite: bool = True,
) -> dict:
    """
    Extract text from every supported file in raw_dir → out_dir/*.txt.

    Returns a small summary dict for CLI printing.
    """
    raw_dir = Path(raw_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not raw_dir.exists():
        raise FileNotFoundError(
            f"Raw reports folder not found: {raw_dir}\n"
            "Create it and copy your 210 FYP reports there."
        )

    sources = sorted(
        p for p in raw_dir.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not sources:
        raise ValueError(
            f"No .docx / .pdf / .txt files found in {raw_dir}. "
            "Copy your FYP reports into that folder first."
        )

    written = 0
    skipped = 0
    errors: list[str] = []

    for src in sources:
        out_path = out_dir / f"{_safe_stem(src)}.txt"
        if out_path.exists() and not overwrite:
            skipped += 1
            continue
        try:
            text = extract_text_from_file(src)
            if not text:
                errors.append(f"{src.name}: empty text after extraction")
                continue
            out_path.write_text(text, encoding="utf-8")
            written += 1
            print(f"  [ok] {src.name} → {out_path.name} ({len(text)} chars)")
        except Exception as exc:
            errors.append(f"{src.name}: {exc}")
            print(f"  [err] {src.name}: {exc}")

    return {
        "raw_dir": str(raw_dir),
        "out_dir": str(out_dir),
        "sources_found": len(sources),
        "written": written,
        "skipped": skipped,
        "errors": errors,
    }


def _cli() -> int:
    package_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Ingest raw FYP reports into plagiarism/fyp_corpus as .txt files."
    )
    parser.add_argument(
        "--raw-dir",
        type=str,
        default=str(package_dir / "fyp_reports_raw"),
        help="Folder containing original DOCX/PDF/TXT FYP reports.",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=str(config.CORPUS_DIR),
        help="Destination corpus folder (plain-text .txt files).",
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Skip files that already exist in the corpus folder.",
    )
    parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help="After ingest, rebuild MinHash + FAISS indexes immediately.",
    )
    args = parser.parse_args()

    print(f"Ingesting from: {args.raw_dir}")
    print(f"Writing to:     {args.out_dir}")
    try:
        summary = ingest_reports(
            Path(args.raw_dir),
            Path(args.out_dir),
            overwrite=not args.no_overwrite,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(
        f"\nDone. sources={summary['sources_found']} "
        f"written={summary['written']} skipped={summary['skipped']} "
        f"errors={len(summary['errors'])}"
    )

    if args.rebuild_index:
        print("\nBuilding plagiarism indexes (first run can take several minutes)...")
        from plagiarism.corpus_index import build_corpus_index

        index = build_corpus_index(
            corpus_dir=Path(args.out_dir),
            force_rebuild=True,
        )
        print(
            f"Index ready: {index.size} documents, "
            f"{index.sentence_count} sentences."
        )

    return 0 if not summary["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(_cli())
