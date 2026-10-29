"""
Phase 1 verification for image formatting services.
Run from backend/:  python test_image_formatting_phase1.py
"""

from __future__ import annotations

import os
import sys
import tempfile

from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

# Ensure backend root on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.image_formatting_service import run_image_formatting_pipeline
from services.image_caption_service import detect_captions_for_document
from services.image_numbering_service import assign_figure_numbers
from services.image_reference_validator import validate_figure_references


def _tiny_png_bytes() -> bytes:
    # 1x1 PNG
    import base64

    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def _add_image_para(doc: Document, png_path: str, caption: str | None = None):
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.add_run()
    run.add_picture(png_path, width=Inches(1.5))
    if caption:
        doc.add_paragraph(caption)


def build_sample_docx(path: str) -> None:
    doc = Document()
    png = os.path.join(os.path.dirname(path), "_t.png")
    with open(png, "wb") as f:
        f.write(_tiny_png_bytes())

    doc.add_heading("1 Introduction", level=1)
    doc.add_paragraph("As shown in Figure 1, the architecture is modular.")
    _add_image_para(doc, png, "fig 1: System overview")

    doc.add_heading("2 Methods", level=1)
    doc.add_paragraph("See Figure 2.1 for the pipeline.")
    _add_image_para(doc, png, "Figure 2: Pipeline diagram")
    _add_image_para(doc, png)  # missing caption

    doc.add_paragraph("Broken ref to Figure 99 should be flagged.")
    doc.save(path)


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="fmt_img_")
    src = os.path.join(tmp, "sample.docx")
    out1 = os.path.join(tmp, "out1.docx")
    out2 = os.path.join(tmp, "out2.docx")
    build_sample_docx(src)

    rules_global = {
        "numbering_scheme": "global",
        "caption_format_pattern": "Figure {n}: {caption}",
        "caption_position": "below",
        "include_lof": True,
        "max_image_width_percent": 80,
    }

    r1 = run_image_formatting_pipeline(src, out1, rules_global)
    assert r1["status"] in ("success", "no_images"), r1
    assert r1["total_images"] == 3, r1
    assert r1["caption_missing_count"] >= 1, r1["captions"]

    nums1 = [a["n"] for a in r1["numbering"]]
    assert nums1 == [1, 2, 3], nums1

    # Idempotent: second run same numbers
    r2 = run_image_formatting_pipeline(out1, out2, rules_global)
    nums2 = [a["n"] for a in r2["numbering"]]
    assert nums2 == nums1, (nums1, nums2)

    refs = r1["references"]
    broken_nums = {b["number"] for b in refs["broken_references"]}
    assert "99" in broken_nums, refs

    # Chapter scheme
    rules_ch = dict(rules_global)
    rules_ch["numbering_scheme"] = "chapter"
    rules_ch["caption_format_pattern"] = "Figure {chapter}.{n}: {caption}"
    out3 = os.path.join(tmp, "out3.docx")
    r3 = run_image_formatting_pipeline(src, out3, rules_ch)
    chapters = [(a["chapter"], a["n"]) for a in r3["numbering"]]
    assert chapters[0][0] == 1 and chapters[0][1] == 1, chapters
    assert chapters[1][0] == 2, chapters

    print("PASS: Phase 1 image formatting checks")
    print(f"  tmp={tmp}")
    print(f"  global_numbers={nums1}")
    print(f"  chapter_pairs={chapters}")
    print(f"  missing_captions={r1['caption_missing_count']}")
    print(f"  broken_refs={broken_nums}")
    print(f"  lof={r1.get('list_of_figures')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
