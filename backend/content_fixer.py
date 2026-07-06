"""
content_fixer.py — Apply text-level and heading fixes to DOCX working copies.
"""

from __future__ import annotations

import os
import re
import shutil
from typing import Any, Dict, List, Tuple


def _para_index(paragraph_id: str) -> int | None:
    match = re.match(r"p(\d+)", str(paragraph_id or ""))
    return int(match.group(1)) if match else None


_INSTRUCTION_RE = re.compile(
    r"^(move|relocate|transfer|apply|use|add|remove|delete|insert|reorder|place)\s+",
    re.IGNORECASE,
)


def _is_instruction_suggestion(text: str) -> bool:
    """True if suggestion is a structural instruction, not corrected prose."""
    s = (text or "").strip()
    if not s:
        return False
    if _INSTRUCTION_RE.match(s):
        return True
    lowered = s.lower()
    return any(
        phrase in lowered
        for phrase in (
            "move this paragraph",
            "apply heading",
            "section order",
            "to the ",
            "under the ",
            "wrong section",
        )
    )


def _replace_in_paragraph(para, original: str, suggestion: str) -> bool:
    """Replace text inside runs without destroying paragraph XML structure."""
    orig = original.strip()
    sugg = suggestion.strip()
    if not sugg:
        return False

    if orig:
        for run in para.runs:
            if orig in run.text:
                run.text = run.text.replace(orig, sugg, 1)
                return True
        full = para.text
        if orig in full:
            if para.runs:
                para.runs[0].text = full.replace(orig, sugg, 1)
                for run in para.runs[1:]:
                    run.text = ""
                return True
            return False
        # Case-insensitive fallback
        lower_full = full.lower()
        lower_orig = orig.lower()
        if lower_orig in lower_full:
            idx = lower_full.index(lower_orig)
            new_text = full[:idx] + sugg + full[idx + len(orig):]
            if para.runs:
                para.runs[0].text = new_text
                for run in para.runs[1:]:
                    run.text = ""
                return True
        # Full-sentence grammar correction only (never instructions)
        if (
            not _is_instruction_suggestion(sugg)
            and len(sugg) > 20
            and len(full) > 10
            and orig[:20].lower() in full.lower()
        ):
            if para.runs:
                para.runs[0].text = sugg
                for run in para.runs[1:]:
                    run.text = ""
                return True
    elif para.runs:
        para.runs[0].text = sugg
        for run in para.runs[1:]:
            run.text = ""
        return True

    return False


def apply_text_fix(
    file_path: str,
    paragraph_id: str,
    original: str,
    suggestion: str,
) -> Tuple[bool, str]:
    """Replace paragraph text when original matches; returns (success, message)."""
    if not file_path.endswith(".docx"):
        return False, "Text fixes are only supported for DOCX files."

    if not os.path.exists(file_path):
        return False, "Working document not found."

    from docx import Document as DocxDoc

    idx = _para_index(paragraph_id)
    if idx is None:
        return False, f"Invalid paragraph_id: {paragraph_id}"

    doc = DocxDoc(file_path)
    if idx >= len(doc.paragraphs):
        return False, f"Paragraph index {idx} out of range."

    para = doc.paragraphs[idx]

    if _is_instruction_suggestion(suggestion):
        return False, "Suggestion is a formatting instruction, not text to insert. Use heading or template fix instead."

    if _replace_in_paragraph(para, original, suggestion):
        doc.save(file_path)
        return True, "Fix applied."

    # Never overwrite entire paragraph unless original matched partially
    if suggestion.strip() and original.strip() and len(original.strip()) >= 3:
        return False, "Could not locate original text in paragraph."

    return False, "Could not locate original text in paragraph."


def apply_heading_fix(
    file_path: str,
    paragraph_id: str,
    heading_level: int = 1,
) -> Tuple[bool, str]:
    """Apply Word built-in Heading N style to a paragraph."""
    if not file_path.endswith(".docx"):
        return False, "Heading fixes are only supported for DOCX files."

    if not os.path.exists(file_path):
        return False, "Working document not found."

    from docx import Document as DocxDoc
    from docx.shared import Pt
    from docx.oxml.ns import qn
    from docx_styles import force_heading_style

    idx = _para_index(paragraph_id)
    if idx is None:
        return False, f"Invalid paragraph_id: {paragraph_id}"

    doc = DocxDoc(file_path)
    if idx >= len(doc.paragraphs):
        return False, f"Paragraph index {idx} out of range."

    level = max(1, min(4, int(heading_level)))
    para = doc.paragraphs[idx]
    style_name = force_heading_style(para, doc, level)

    # Template font reinforcement without breaking the Word style link
    for run in para.runs:
        if level == 1:
            run.font.size = Pt(16)
        elif level == 2:
            run.font.size = Pt(14)
        elif level == 3:
            run.font.size = Pt(12)
        r_pr = run._element.get_or_add_rPr()
        r_fonts = r_pr.get_or_add_rFonts()
        r_fonts.set(qn("w:ascii"), "Times New Roman")
        r_fonts.set(qn("w:hAnsi"), "Times New Roman")

    pf = para.paragraph_format
    pf.first_line_indent = None
    pf.left_indent = None

    doc.save(file_path)
    return True, f"Applied {style_name}."


def apply_all_text_fixes(
    file_path: str,
    fixes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Apply a batch of text fixes. Each fix needs paragraph_id + suggestion."""
    applied = 0
    skipped = 0
    errors: List[str] = []

    for fix in fixes:
        fix_type = fix.get("fix_type", "text")
        if fix_type == "heading":
            ok, msg = apply_heading_fix(
                file_path,
                fix.get("paragraph_id", ""),
                int(fix.get("heading_level", 1) or 1),
            )
        else:
            ok, msg = apply_text_fix(
                file_path,
                fix.get("paragraph_id", ""),
                fix.get("original", ""),
                fix.get("suggestion", ""),
            )
        if ok:
            applied += 1
        else:
            skipped += 1
            errors.append(msg)

    return {"applied": applied, "skipped": skipped, "errors": errors}


def apply_template_reformat(
    file_path: str,
    formatting_rules: Dict[str, Any],
    required_sections: List[Dict[str, Any]],
) -> Tuple[bool, str]:
    """Re-apply admin template styles to an existing working DOCX in place."""
    if not file_path.endswith(".docx"):
        return False, "Template reformat is only supported for DOCX files."

    if not os.path.exists(file_path):
        return False, "Working document not found."

    from models import AnalysisReport
    from reformatter import reformat_document

    tmp_path = f"{file_path}.reformat.tmp.docx"
    report = AnalysisReport(issues=[], stats={})
    try:
        reformat_document(
            file_path,
            tmp_path,
            report,
            formatting_rules,
            required_sections or [],
        )
        shutil.move(tmp_path, file_path)
        return True, "Template formatting applied."
    except Exception as exc:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        return False, str(exc)
