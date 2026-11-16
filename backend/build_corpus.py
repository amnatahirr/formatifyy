"""
build_corpus.py

Recursively scans a source folder (can have nested subfolders) for .pdf and
.docx FYP report files, extracts their full text, and saves each as a clean
.txt file inside the plagiarism corpus folder — ready for
`python -m plagiarism.detector --rebuild-index`.

USAGE:
    python build_corpus.py --source "/path/to/fyp_reports" --dest "backend/plagiarism/sample_corpus"

Install requirements first (one time):
    pip install pdfplumber python-docx

Notes:
- Skips files it can't read (corrupted/scanned-image PDFs) and logs them
  at the end instead of crashing the whole batch.
- Cleans filenames (removes spaces/special chars) and avoids overwriting
  duplicates by appending a counter.
- Strips excessive blank lines / whitespace from extracted text.
"""

import argparse
import re
import sys
from pathlib import Path

def clean_text(text: str) -> str:
    # collapse 3+ newlines into 2, strip trailing whitespace per line
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def safe_filename(stem: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9_\-]+", "_", stem)
    stem = re.sub(r"_{2,}", "_", stem).strip("_")
    return stem[:80] if stem else "untitled"

def extract_pdf(path: Path) -> str:
    import pdfplumber
    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n\n".join(text_parts)

def extract_docx(path: Path) -> str:
    import docx
    d = docx.Document(path)
    paragraphs = [p.text for p in d.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Root folder containing FYP report PDFs/DOCXs (subfolders OK)")
    parser.add_argument("--dest", required=True, help="Destination corpus folder (e.g. backend/plagiarism/sample_corpus)")
    parser.add_argument("--min-words", type=int, default=100, help="Skip files with fewer extracted words than this (likely scanned/empty)")
    args = parser.parse_args()

    source = Path(args.source)
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)

    if not source.exists():
        print(f"ERROR: source folder not found: {source}")
        sys.exit(1)

    pdf_files = list(source.rglob("*.pdf"))
    docx_files = list(source.rglob("*.docx"))
    all_files = pdf_files + docx_files

    print(f"Found {len(pdf_files)} PDF files and {len(docx_files)} DOCX files "
          f"(searched recursively under {source})\n")

    used_names = set()
    success, skipped, failed = 0, 0, []

    for i, path in enumerate(all_files, 1):
        print(f"[{i}/{len(all_files)}] {path.name} ... ", end="", flush=True)
        try:
            if path.suffix.lower() == ".pdf":
                text = extract_pdf(path)
            else:
                text = extract_docx(path)

            text = clean_text(text)
            word_count = len(text.split())

            if word_count < args.min_words:
                print(f"SKIPPED (only {word_count} words extracted — likely scanned/empty)")
                skipped += 1
                continue

            base_name = safe_filename(path.stem)
            out_name = f"{base_name}.txt"
            counter = 1
            while out_name in used_names:
                out_name = f"{base_name}_{counter}.txt"
                counter += 1
            used_names.add(out_name)

            (dest / out_name).write_text(text, encoding="utf-8")
            print(f"OK ({word_count} words) -> {out_name}")
            success += 1

        except Exception as e:
            print(f"FAILED ({e})")
            failed.append((str(path), str(e)))

    print("\n--- Summary ---")
    print(f"Converted: {success}")
    print(f"Skipped (too little text): {skipped}")
    print(f"Failed: {len(failed)}")
    if failed:
        print("\nFailed files:")
        for path, err in failed:
            print(f"  - {path}: {err}")

if __name__ == "__main__":
    main()