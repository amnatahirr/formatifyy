"""
docx_styles.py — Reliable Word built-in heading style assignment.
"""

from __future__ import annotations

from docx.oxml import OxmlElement
from docx.oxml.ns import qn

_HEADING_STYLE_IDS = {1: "Heading1", 2: "Heading2", 3: "Heading3", 4: "Heading4"}


def resolve_heading_style_id(doc, level: int) -> str:
    """Return the document's styleId for Heading N."""
    level = max(1, min(4, int(level)))
    target_name = f"Heading {level}"
    target_id = _HEADING_STYLE_IDS[level]
    try:
        for style in doc.styles:
            if style.name == target_name or getattr(style, "style_id", None) == target_id:
                return getattr(style, "style_id", None) or target_id
    except Exception:
        pass
    return target_id


def force_heading_style(para, doc, level: int) -> str:
    """
    Force Word built-in Heading N on a paragraph via API + OOXML pStyle.
    Returns the style name applied (e.g. 'Heading 2').
    """
    level = max(1, min(4, int(level)))
    style_name = f"Heading {level}"
    style_id = resolve_heading_style_id(doc, level)

    for candidate in (style_name, style_id):
        try:
            para.style = doc.styles[candidate]
            break
        except Exception:
            continue

    p_pr = para._element.get_or_add_pPr()
    for child in list(p_pr):
        if child.tag == qn("w:pStyle"):
            p_pr.remove(child)

    p_style = OxmlElement("w:pStyle")
    p_style.set(qn("w:val"), style_id)
    p_pr.insert(0, p_style)

    outline_val = str(level - 1)
    outline = p_pr.find(qn("w:outlineLvl"))
    if outline is None:
        outline = OxmlElement("w:outlineLvl")
        p_pr.append(outline)
    outline.set(qn("w:val"), outline_val)

    return style_name
