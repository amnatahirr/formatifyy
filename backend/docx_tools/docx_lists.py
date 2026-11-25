"""
docx_lists.py — create REAL Word bullet lists (numPr + hanging indent).

Why: a bullet typed as text ("• To develop...") or a list paragraph whose indent
was overwritten by body first-line-indent looks broken. Word's own bullets use:
  1. <w:numPr> on the paragraph (numId + ilvl)
  2. a numbering definition whose level carries the hanging indent (w:ind)
  3. NO direct first-line / left indent on the paragraph itself
"""
from __future__ import annotations
import re
from copy import deepcopy
from typing import Optional

from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

_GLYPH_RE = re.compile(r"^\s*[•●○◦▪■□‣⁃*\-–—→»·]\s*[\t ]*")
_BULLET_FONTS = [("\uf0b7", "Symbol"), ("o", "Courier New"), ("\uf0a7", "Wingdings")]
_CACHE_ATTR = "_formatify_bullet_numid"


def _numbering_root(doc):
    return doc.part.numbering_part.element


_ABS_NAME = "FormatifyBullets"


def _find_existing_bullet_num(root) -> Optional[int]:
    """numId of a bullet definition we created earlier (found by its abstractNum name).
    Works across save/reopen and needs no attribute on the Document object."""
    abs_ids = set()
    for a in root.findall(qn("w:abstractNum")):
        nm = a.find(qn("w:name"))
        if nm is not None and nm.get(qn("w:val")) == _ABS_NAME:
            abs_ids.add(a.get(qn("w:abstractNumId")))
    if not abs_ids:
        return None
    for n in root.findall(qn("w:num")):
        ref = n.find(qn("w:abstractNumId"))
        if ref is not None and ref.get(qn("w:val")) in abs_ids:
            return int(n.get(qn("w:numId")))
    return None


def ensure_bullet_numbering(doc) -> int:
    """Create (once per document) a multilevel bullet definition; return its numId."""
    try:
        cached = getattr(doc, _CACHE_ATTR, None)
    except Exception:
        cached = None
    if cached:
        return cached

    root = _numbering_root(doc)
    existing = _find_existing_bullet_num(root)
    if existing:
        try:
            setattr(doc, _CACHE_ATTR, existing)
        except Exception:
            pass
        return existing

    abs_ids = [int(a.get(qn("w:abstractNumId"))) for a in root.findall(qn("w:abstractNum"))]
    num_ids = [int(n.get(qn("w:numId"))) for n in root.findall(qn("w:num"))]
    abs_id = (max(abs_ids) + 1) if abs_ids else 1
    num_id = (max(num_ids) + 1) if num_ids else 1

    lvls = []
    for i in range(9):
        char, font = _BULLET_FONTS[i % 3]
        left = 720 * (i + 1)
        lvls.append(
            f'<w:lvl w:ilvl="{i}"><w:start w:val="1"/><w:numFmt w:val="bullet"/>'
            f'<w:lvlText w:val="{char}"/><w:lvlJc w:val="left"/>'
            f'<w:pPr><w:ind w:left="{left}" w:hanging="360"/></w:pPr>'
            f'<w:rPr><w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:hint="default"/></w:rPr></w:lvl>'
        )
    abstract = parse_xml(
        f'<w:abstractNum {nsdecls("w")} w:abstractNumId="{abs_id}">'
        f'<w:multiLevelType w:val="hybridMultilevel"/><w:name w:val="{_ABS_NAME}"/>{"".join(lvls)}</w:abstractNum>'
    )
    num = parse_xml(
        f'<w:num {nsdecls("w")} w:numId="{num_id}"><w:abstractNumId w:val="{abs_id}"/></w:num>'
    )

    # Schema order: all abstractNum elements must precede all num elements.
    first_num = root.find(qn("w:num"))
    if first_num is not None:
        first_num.addprevious(abstract)
    else:
        root.append(abstract)
    root.append(num)

    try:
        setattr(doc, _CACHE_ATTR, num_id)
    except Exception:
        pass   # caching is optional; _find_existing_bullet_num finds it next time
    return num_id


def has_numbering(para) -> bool:
    """True if the paragraph is already a real Word list item."""
    p_pr = para._element.pPr
    if p_pr is not None and p_pr.numPr is not None:
        return True
    try:
        name = (para.style.name or "").lower()
    except Exception:
        name = ""
    return name.startswith("list bullet") or name.startswith("list number")


def strip_literal_glyph(para) -> bool:
    """Remove a typed bullet glyph (+ following tab/spaces) from the first text run."""
    for run in para.runs:
        if not run.text:
            continue
        new = _GLYPH_RE.sub("", run.text, count=1)
        if new != run.text:
            run.text = new
            return True
        return False
    return False


def make_bullet(doc, para, level: int = 0) -> None:
    """Turn `para` into a real Word bullet item at `level` (0-8). Text is untouched
    apart from removing a typed bullet glyph."""
    level = max(0, min(8, level))
    num_id = ensure_bullet_numbering(doc)
    strip_literal_glyph(para)

    p_pr = para._element.get_or_add_pPr()
    old = p_pr.find(qn("w:numPr"))
    if old is not None:
        p_pr.remove(old)
    ind = p_pr.find(qn("w:ind"))            # drop direct indents: the list level owns them
    if ind is not None:
        p_pr.remove(ind)

    num_pr = OxmlElement("w:numPr")
    ilvl = OxmlElement("w:ilvl"); ilvl.set(qn("w:val"), str(level))
    nid = OxmlElement("w:numId"); nid.set(qn("w:val"), str(num_id))
    num_pr.append(ilvl); num_pr.append(nid)

    # numPr must come after pStyle/keepNext/keepLines/pageBreakBefore/... and before spacing/ind/jc
    anchor = None
    for tag in ("w:spacing", "w:ind", "w:contextualSpacing", "w:jc", "w:rPr"):
        anchor = p_pr.find(qn(tag))
        if anchor is not None:
            break
    if anchor is not None:
        anchor.addprevious(num_pr)
    else:
        p_pr.append(num_pr)

    try:
        para.style = para.part.document.styles["List Paragraph"]
    except Exception:
        # No List Paragraph style in this document: at least never leave a list
        # item on a Heading style (it would keep heading font + outline numbering).
        try:
            if (para.style.name or "").lower().startswith(("heading", "title")):
                para.style = para.part.document.styles["Normal"]
        except Exception:
            pass


def apply_bullets_to_indices(doc, indices, level: int = 0, skip_headings: bool = True) -> int:
    """
    Apply real Word bullets to doc.paragraphs[i] for each i in `indices`.
    Idempotent (safe to run twice). Returns how many paragraphs were converted.
    Headings are never bulleted.
    """
    paras = doc.paragraphs
    done = 0
    for i in indices:
        if not isinstance(i, int) or i < 0 or i >= len(paras):
            continue
        p = paras[i]
        if not (p.text or "").strip():
            continue
        try:
            style_name = (p.style.name or "") if p.style is not None else ""
        except Exception:
            style_name = ""
        if skip_headings and style_name.lower().startswith(("heading", "title")):
            continue
        make_bullet(doc, p, level)
        done += 1
    return done