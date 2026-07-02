"""
test_layer2.py  — run from backend/
Tests the 4-layer heading matcher WITHOUT needing a file upload.

Usage:
    python test_layer2.py
    python test_layer2.py path/to/your_doc.docx
"""

import sys
from services.heading_normalizer import HeadingNormalizer

# ── Standard FYP required sections (edit to match YOUR university template) ──
REQUIRED_SECTIONS = [
    "Abstract",
    "Introduction",
    "Problem Statement",
    "Objectives",
    "Scope",
    "Literature Review",
    "Methodology",
    "System Design",
    "Implementation",
    "Results",
    "Evaluation",
    "Conclusion",
    "Future Work",
    "References",
]

# ── Simulated student headings (messy, real-world style) ─────────────────────
STUDENT_HEADINGS_DEMO = [
    "Abstract",                        # exact match
    "Intro",                           # synonym (catches what 0.85 threshold misses)
    "1.2 The Problem",                 # synonym after stripping numbering
    "Project Aims",                    # synonym for Objectives
    "Scope of Work",                   # synonym
    "Lit Review",                      # synonym
    "Methdology",                      # typo → fuzzy layer
    "High Level Design",               # synonym for System Design
    "Technical Implementation",        # synonym
    "Results and Discussion",          # synonym
    "Testing and Evaluation",          # synonym
    "Concluding Remarks",              # synonym
    "Future Recommendations",          # synonym
    # "References" is intentionally missing
    "Appendix A",                      # extra / not required
]


LAYER_COLORS = {
    "exact":    "\033[92m",   # green
    "synonym":  "\033[94m",   # blue
    "fuzzy":    "\033[93m",   # yellow
    "semantic": "\033[95m",   # magenta
    None:       "\033[91m",   # red  (missing)
}
RESET = "\033[0m"


def run_demo(headings, required):
    hn     = HeadingNormalizer(use_semantic=False)   # set True if you have sentence-transformers
    report = hn.match_headings(headings, required)

    print(f"\n{'═'*70}")
    print(f"  LAYER 2 — HEADING VALIDATION REPORT")
    print(f"{'═'*70}")
    print(f"  Required : {report.total_required}   "
          f"Found : {report.total_found}   "
          f"Missing : {len(report.missing)}")
    print(f"{'─'*70}")
    print(f"  {'REQUIRED SECTION':<28} {'STATUS':<10} {'LAYER':<10} {'CONF':>5}  MATCHED AS")
    print(f"{'─'*70}")

    for m in report.matches:
        color  = LAYER_COLORS.get(m.match_layer, LAYER_COLORS[None])
        status = "✓ FOUND" if m.status == "found" else "✗ MISSING"
        layer  = m.match_layer or "—"
        conf   = f"{m.confidence:.2f}" if m.confidence else " —  "
        matched= m.matched_heading or ""
        print(f"  {color}{m.required:<28} {status:<10} {layer:<10} {conf:>5}  {matched}{RESET}")

    if report.extra_headings:
        print(f"\n{'─'*70}")
        print("  EXTRA headings (in document but not in required list):")
        for h in report.extra_headings:
            print(f"    • {h}")

    print(f"{'═'*70}\n")


def run_on_file(path: str):
    from services.document_block_extractor import extract_blocks
    blocks   = extract_blocks(path)
    headings = [b["text"] for b in blocks if b["type"] == "heading"]

    print(f"\nExtracted {len(headings)} headings from {path}:")
    for h in headings:
        print(f"  • {h}")

    run_demo(headings, REQUIRED_SECTIONS)


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        run_on_file(sys.argv[1])
    else:
        print("\n[Running built-in demo with simulated student headings]")
        run_demo(STUDENT_HEADINGS_DEMO, REQUIRED_SECTIONS)