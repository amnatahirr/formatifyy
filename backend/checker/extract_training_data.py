"""
checker/extract_training_data.py
═══════════════════════════════════════════════════════════════════════════════
STEP 1 OF 3 — Run this FIRST.

What it does:
    Scans your PDF and DOCX files, extracts (heading → content) pairs,
    and saves them to checker/training_data.json

How to run:
    python checker/extract_training_data.py

    # Or point it at a specific folder:
    python checker/extract_training_data.py --folder uploads/
    python checker/extract_training_data.py --folder my_sample_docs/

What you get:
    checker/training_data.json   ← input for train_content_model.py

Requirements:
    pip install python-docx pypdf
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import json
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "training_data.json")

# ── Heading detection heuristics ─────────────────────────────────────────────
# A line is treated as a heading if it matches these rules.
# Tune these if your documents have a different style.
MAX_HEADING_WORDS   = 12    # headings are short
MIN_CONTENT_CHARS   = 30    # skip sections with almost no content


def looks_like_heading(text: str) -> bool:
    """Return True if the text looks like a section heading."""
    text = text.strip()
    if not text:
        return False

    word_count = len(text.split())

    # Too long to be a heading
    if word_count > MAX_HEADING_WORDS:
        return False

    # Ends with sentence punctuation → probably body text
    if text.endswith((".", "?", "!")):
        return False

    # All-caps short lines are headings (e.g. "INTRODUCTION")
    if text.isupper() and word_count <= 8:
        return True

    # Title-case short lines (e.g. "Literature Review")
    if text.istitle() and word_count <= 8:
        return True

    # Numbered headings: "1. Introduction", "2.1 Methodology"
    parts = text.split()
    if parts and parts[0].rstrip(".").replace(".", "").isdigit():
        return True

    return False


# ── DOCX extractor ────────────────────────────────────────────────────────────

def extract_from_docx(file_path: str) -> List[Dict[str, Any]]:
    """Extract (heading, content) pairs from a .docx file."""
    try:
        from docx import Document
    except ImportError:
        logger.error("python-docx not installed: pip install python-docx")
        return []

    try:
        doc = Document(file_path)
    except Exception as e:
        logger.warning("Cannot open %s: %s", file_path, e)
        return []

    sections     = []
    cur_heading  = ""
    cur_content  = []

    for para in doc.paragraphs:
        text       = para.text.strip()
        style_name = para.style.name.lower() if para.style else ""

        if not text:
            continue

        # Detect heading by style OR by heuristic
        is_heading = (
            "heading" in style_name
            or style_name in ("title", "subtitle")
            or looks_like_heading(text)
        )

        if is_heading:
            # Flush previous section
            if cur_heading and cur_content:
                content_str = " ".join(cur_content).strip()
                if len(content_str) >= MIN_CONTENT_CHARS:
                    sections.append({
                        "heading": cur_heading,
                        "content": content_str,
                    })
            cur_heading  = text
            cur_content  = []
        else:
            cur_content.append(text)

    # Flush last section
    if cur_heading and cur_content:
        content_str = " ".join(cur_content).strip()
        if len(content_str) >= MIN_CONTENT_CHARS:
            sections.append({"heading": cur_heading, "content": content_str})

    return sections


# ── PDF extractor ─────────────────────────────────────────────────────────────

def extract_from_pdf(file_path: str) -> List[Dict[str, Any]]:
    """Extract (heading, content) pairs from a .pdf file."""
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader          # older name
        except ImportError:
            logger.error("pypdf not installed: pip install pypdf")
            return []

    try:
        reader = PdfReader(file_path)
    except Exception as e:
        logger.warning("Cannot open %s: %s", file_path, e)
        return []

    # Collect all lines from all pages
    all_lines = []
    for page in reader.pages:
        raw = page.extract_text() or ""
        for line in raw.split("\n"):
            line = line.strip()
            if line:
                all_lines.append(line)

    sections    = []
    cur_heading = ""
    cur_content = []

    for line in all_lines:
        if looks_like_heading(line):
            if cur_heading and cur_content:
                content_str = " ".join(cur_content).strip()
                if len(content_str) >= MIN_CONTENT_CHARS:
                    sections.append({
                        "heading": cur_heading,
                        "content": content_str,
                    })
            cur_heading = line
            cur_content = []
        else:
            cur_content.append(line)

    if cur_heading and cur_content:
        content_str = " ".join(cur_content).strip()
        if len(content_str) >= MIN_CONTENT_CHARS:
            sections.append({"heading": cur_heading, "content": content_str})

    return sections


# ── Main ──────────────────────────────────────────────────────────────────────

def scan_folder(folder: str) -> List[Dict[str, Any]]:
    """Walk a folder and extract sections from every PDF and DOCX."""
    folder_path = Path(folder)
    if not folder_path.exists():
        logger.error("Folder not found: %s", folder)
        return []

    all_sections = []
    files        = list(folder_path.rglob("*.docx")) + list(folder_path.rglob("*.pdf"))

    if not files:
        logger.warning("No PDF or DOCX files found in %s", folder)
        return []

    logger.info("Found %d files in '%s'", len(files), folder)

    for f in files:
        path = str(f)
        ext  = f.suffix.lower()

        if ext == ".docx":
            sections = extract_from_docx(path)
        elif ext == ".pdf":
            sections = extract_from_pdf(path)
        else:
            continue

        logger.info("  %-50s  → %2d sections", f.name[:50], len(sections))
        all_sections.extend(sections)

    return all_sections


def deduplicate(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate (heading, content) pairs."""
    seen  = set()
    clean = []
    for s in sections:
        key = (s["heading"].lower().strip(), s["content"][:80].lower().strip())
        if key not in seen:
            seen.add(key)
            clean.append(s)
    return clean


def save(sections: List[Dict[str, Any]], output_path: str):
    """Merge with existing training_data.json and save."""
    existing = []
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        logger.info("Existing training data: %d sections", len(existing))

    combined = deduplicate(existing + sections)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    new_count = len(combined) - len(existing)
    logger.info(
        "Saved %d total sections (%+d new) → %s",
        len(combined), new_count, output_path,
    )
    return combined


def main():
    parser = argparse.ArgumentParser(
        description="Extract heading→content training pairs from PDF/DOCX files"
    )
    parser.add_argument(
        "--folder",
        default=["uploads"],
        help="Folder to scan (default: uploads/). Can pass multiple: --folder a --folder b",
        action="append",
        dest="folders",
    )
    parser.add_argument(
        "--output",
        default=OUTPUT_PATH,
        help=f"Output JSON path (default: {OUTPUT_PATH})",
    )
    args = parser.parse_args()

    all_sections = []
    for folder in args.folders:
        logger.info("═" * 60)
        logger.info("Scanning: %s", folder)
        logger.info("═" * 60)
        all_sections.extend(scan_folder(folder))

    if not all_sections:
        logger.error(
            "\n❌  No sections extracted.\n"
            "   Check that your folder path is correct and files are readable.\n"
            "   Current working directory: %s",
            os.getcwd(),
        )
        return

    final = save(all_sections, args.output)

    # ── Quality report ────────────────────────────────────────────────────────
    logger.info("\n%s", "═" * 60)
    logger.info("EXTRACTION SUMMARY")
    logger.info("═" * 60)
    logger.info("Total sections in training_data.json : %d", len(final))

    # Count per heading name
    from collections import Counter
    heading_counts = Counter(s["heading"] for s in final)
    logger.info("\nTop 20 most common headings:")
    for heading, count in heading_counts.most_common(20):
        logger.info("  %3d × %s", count, heading)

    if len(final) < 20:
        logger.warning(
            "\n⚠  Only %d sections found. Recommended minimum: 50.\n"
            "   Add more documents to the folder and re-run this script.\n"
            "   The more documents, the better the model accuracy.",
            len(final),
        )
    elif len(final) < 50:
        logger.info(
            "\n⚠  %d sections is enough to train but accuracy may be limited.\n"
            "   Try to get 100+ sections for a reliable model.", len(final)
        )
    else:
        logger.info(
            "\n✓  %d sections — good dataset size. Ready to train!\n"
            "   Next step: python checker/train_content_model.py",
            len(final),
        )


if __name__ == "__main__":
    main()