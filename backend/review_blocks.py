"""
review_blocks.py — Extract classified body blocks for supervisor Document Review.

Skips front-matter pages (cover, info, TOC, list of figures, list of tables),
ignores empty lines, and labels each remaining block as:
  heading | subheading | paragraph | line | bullet
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger(__name__)

# Block types stored in document_paragraphs.block_type
BLOCK_HEADING = "heading"
BLOCK_SUBHEADING = "subheading"
BLOCK_PARAGRAPH = "paragraph"
BLOCK_LINE = "line"
BLOCK_BULLET = "bullet"
BLOCK_FRONTMATTER = "frontmatter"

_DISPLAY_LABELS = {
    BLOCK_HEADING: "Heading",
    BLOCK_SUBHEADING: "Subheading",
    BLOCK_PARAGRAPH: "Paragraph",
    BLOCK_LINE: "Line",
    BLOCK_BULLET: "Bullet",
}

_TOC_TITLE_RE = re.compile(
    r"^(table\s+of\s+contents|contents)$",
    re.IGNORECASE,
)
_LOF_TITLE_RE = re.compile(
    r"^(list\s+of\s+(?:figures|images|illustrations)|table\s+of\s+figures)$",
    re.IGNORECASE,
)
_LOT_TITLE_RE = re.compile(
    r"^(list\s+of\s+tables|table\s+of\s+tables)$",
    re.IGNORECASE,
)
_TOC_LEADER_RE = re.compile(r"\.{2,}\s*\d+\s*$")
_CHAPTER_START_RE = re.compile(
    r"^(?:chapter\s+\d+(?:\s*[:.\-–—]\s*.{0,60})?|"
    r"abstract|introduction|acknowledgements?|acknowledgment|"
    r"literature\s+review|methodology|conclusion|references|"
    r"related\s+work|proposed\s+solution)$",
    re.IGNORECASE,
)
_BULLET_MARKER_RE = re.compile(
    r"^(?:"
    r"[•*○■▪\-–—→»·]"
    r"|\(?[A-Za-z][.)]"
    r"|\(?[ivxlcdmIVXLCDM]+[.)]"
    r"|\(?\d+[.)](?!\d)"
    r")\s+"
)
_HEADING_STYLE_RE = re.compile(r"heading\s*(\d+)|title|subtitle", re.IGNORECASE)
_SENTENCE_END_RE = re.compile(r"[.!?]\s*$")
_WORD_RE = re.compile(r"\S+")


def display_label_for_block_type(block_type: str | None) -> str:
    key = (block_type or BLOCK_PARAGRAPH).strip().lower()
    return _DISPLAY_LABELS.get(key, "Paragraph")


def _word_count(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))


def _para_style_name(paragraph) -> str:
    try:
        return (paragraph.style.name if paragraph.style else "Normal") or "Normal"
    except Exception:
        return "Normal"


def _para_has_page_break(paragraph) -> bool:
    try:
        from docx.oxml.ns import qn

        for br in paragraph._element.findall(".//" + qn("w:br")):
            if br.get(qn("w:type")) == "page":
                return True
        if paragraph._element.findall(".//" + qn("w:lastRenderedPageBreak")):
            return True
    except Exception:
        pass
    return False


def _para_is_list(paragraph, style: str) -> bool:
    style_l = (style or "").lower()
    if "list" in style_l or "bullet" in style_l or "number" in style_l:
        return True
    try:
        p_pr = paragraph._element.pPr
        if p_pr is not None and p_pr.numPr is not None:
            return True
    except Exception:
        pass
    return False


def _heading_level_from_style(style: str) -> Optional[int]:
    match = _HEADING_STYLE_RE.search(style or "")
    if not match:
        return None
    if match.group(1):
        try:
            return int(match.group(1))
        except ValueError:
            return 1
    name = (style or "").lower()
    if "subtitle" in name:
        return 2
    if "title" in name:
        return 1
    return 1


def classify_block_text(text: str, style: str = "", *, is_list: bool = False) -> Optional[str]:
    """
    Classify a non-empty text block.
    Returns None for empty / whitespace-only input (caller should ignore).
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return None

    level = _heading_level_from_style(style)

    # Word heading/title styles win over numbered-list heuristics ("1. Introduction")
    if level is not None and not is_list:
        return BLOCK_HEADING if level <= 1 else BLOCK_SUBHEADING

    # Hierarchical outline titles (3.2. Foo) are subheadings, not bullets
    if not is_list and re.match(r"^\d+(?:\.\d+)+\.?\s+\S", cleaned):
        return BLOCK_SUBHEADING

    if _CHAPTER_START_RE.match(cleaned) and not is_list:
        return BLOCK_HEADING

    # ALL-CAPS short titles
    letters = re.sub(r"[^A-Za-z]", "", cleaned)
    if letters and letters.isupper() and 0 < _word_count(cleaned) <= 10 and not is_list:
        return BLOCK_HEADING

    if is_list or _BULLET_MARKER_RE.match(cleaned):
        # "1. Introduction" (short Title Case) → heading; "1. Collect the dataset…" → bullet
        m = re.match(r"^\d+[.)]\s+(.+)$", cleaned)
        if m and not is_list:
            rest = m.group(1).strip()
            words = rest.split()
            title_like = bool(rest) and (
                rest.istitle()
                or rest.isupper()
                or (
                    len(words) <= 4
                    and all(w[:1].isupper() for w in words if w[:1].isalpha())
                )
            )
            if (
                title_like
                and _word_count(rest) <= 6
                and not _SENTENCE_END_RE.search(rest)
                and not re.match(r"^(to|for|with|and|or|collect|improve|build|create)\b", rest, re.I)
            ):
                return BLOCK_HEADING
        return BLOCK_BULLET

    words = _word_count(cleaned)
    sentence_breaks = len(re.findall(r"[.!?][\"')\]]*\s+", cleaned))
    ends_sentence = bool(_SENTENCE_END_RE.search(cleaned))

    # Prose sentence / multi-clause body → paragraph
    if words >= 12 and ends_sentence:
        return BLOCK_PARAGRAPH
    if words >= 20 or sentence_breaks >= 1:
        return BLOCK_PARAGRAPH

    # Short single line without sentence punctuation → line
    if "\n" not in cleaned and words <= 18:
        return BLOCK_LINE

    return BLOCK_PARAGRAPH


def _page_kind(page_texts: Sequence[str]) -> Optional[str]:
    """Return cover|info|toc|lof|lot|body|None for a page's non-empty lines."""
    lines = [t.strip() for t in page_texts if (t or "").strip()]
    if not lines:
        return None
    joined = "\n".join(lines)
    first = lines[0]
    first_few = "\n".join(lines[:5])
    word_count = _word_count(joined)
    leader_hits = sum(1 for x in lines if _TOC_LEADER_RE.search(x))

    # Explicit list-page titles (keep even when short)
    if _TOC_TITLE_RE.match(first) or any(_TOC_TITLE_RE.match(x) for x in lines[:3]):
        return "toc"
    if _LOF_TITLE_RE.match(first) or any(_LOF_TITLE_RE.match(x) for x in lines[:3]):
        return "lof"
    if _LOT_TITLE_RE.match(first) or any(_LOT_TITLE_RE.match(x) for x in lines[:3]):
        return "lot"

    # TOC-like short pages with dotted leaders
    if leader_hits >= 3 and len(lines) >= 4 and word_count < 400:
        if re.search(r"\b(?:figures?|images?|illustrations?)\b", first_few, re.I):
            return "lof"
        if re.search(r"\btables?\b", first_few, re.I) and not re.search(
            r"table\s+of\s+contents", first_few, re.I
        ):
            return "lot"
        return "toc"

    # Substantial chapter/body pages must never be treated as cover/info
    # (FYP body text often mentions "supervisor", "department", etc.)
    for line in lines[:6]:
        if _CHAPTER_START_RE.match(line) or re.match(
            r"^\d+(?:\.\d+)*\.?\s+[A-Z].{1,80}$", line
        ):
            if word_count >= 80 or len(lines) >= 8:
                return "body"
    if word_count >= 180 and leader_hits < 3:
        return "body"
    if len(lines) >= 40:
        return "body"

    # Cover / info heuristics only for short early pages
    if word_count <= 220 and len(lines) <= 30:
        try:
            from frontmatter_detector import (
                PageSnapshot,
                ParaLayout,
                score_cover_page,
                score_info_page,
            )

            snap = PageSnapshot(
                page_number=1,
                paragraphs=[ParaLayout(text=t) for t in lines],
            )
            cover = score_cover_page(snap)
            info = score_info_page(snap)
            if cover.present and cover.confidence >= 0.55:
                return "cover"
            if info.present and info.confidence >= 0.55:
                return "info"
            if cover.confidence >= 0.45 and word_count <= 140:
                return "cover"
            if info.confidence >= 0.50 and word_count <= 180:
                return "info"
        except Exception:
            pass

    return None


def _split_docx_pages(doc) -> List[List[Tuple[Any, str, str, bool]]]:
    """
    Split into pages of (paragraph, text, style, is_list).
    Empty paragraphs are kept only as page-break carriers; text empties ignored later.
    """
    pages: List[List[Tuple[Any, str, str, bool]]] = [[]]
    for para in doc.paragraphs:
        text = (para.text or "").strip()
        style = _para_style_name(para)
        is_list = _para_is_list(para, style)
        if text:
            pages[-1].append((para, text, style, is_list))
        if _para_has_page_break(para):
            pages.append([])
    # Drop trailing empty page
    while pages and not pages[-1]:
        pages.pop()
    return pages or [[]]


def _leading_frontmatter_skip_count(page_text_lists: Sequence[Sequence[str]]) -> int:
    """How many leading pages to skip (cover/info/toc/lof/lot). Cap at 5."""
    pages = list(page_text_lists)
    skip = 0
    front_kinds = {"cover", "info", "toc", "lof", "lot"}
    max_front_pages = min(5, max(0, len(pages) - 1))  # never skip the only/last page wholesale

    for idx, page in enumerate(pages[: max_front_pages + 1]):
        if idx >= max_front_pages:
            break
        texts = [t for t in page if (t or "").strip()]
        words = _word_count(" ".join(texts))
        # Large pages are body — stop skipping
        if words >= 180 or len(texts) >= 40:
            break
        kind = _page_kind(texts)
        if kind == "body":
            break
        if kind in front_kinds:
            skip = idx + 1
            continue
        joined = " ".join(texts).lower()
        soft_keys = (
            "university",
            "final year project",
            "submitted in partial",
            "table of contents",
            "list of figures",
            "list of images",
            "list of illustrations",
            "list of tables",
            "project details",
            "supervisor",
            "registration number",
            "group members",
        )
        # Soft match: first two short pages, or continue after known front-matter
        if kind is None and words < 160 and any(k in joined for k in soft_keys):
            if idx < 2 or skip > 0:
                skip = idx + 1
                continue
        # Unknown page after front-matter → start of body
        if skip > 0:
            break
        break
    return skip


def _leading_frontmatter_page_count(pages: List[List[Tuple[Any, str, str, bool]]]) -> int:
    """How many leading docx pages to skip (cover/info/toc/lof/lot). Cap at 5."""
    return _leading_frontmatter_skip_count([[t for _, t, _, _ in page] for page in pages])


def strip_frontmatter_from_document(doc: Any) -> Any:
    """
    Return a copy of DocumentModel without leading front-matter pages.

    Used by the student analysis pipeline so cover / info / TOC / LOF / LOT
    (and list-of-images) pages are not scored. Original paragraph_id values are
    preserved so issues still map to the full-document preview. Remaining pages
    are renumbered contiguously from 1 for batching.
    """
    try:
        from models import DocumentModel, ImageBlock, ParagraphBlock
    except Exception:
        return doc

    if not isinstance(doc, DocumentModel) or not doc.paragraphs:
        return doc

    by_page: Dict[int, List[str]] = {}
    for p in doc.paragraphs:
        by_page.setdefault(int(p.page_number), []).append(p.text or "")

    ordered_pages = sorted(by_page.keys())
    skip_n = _leading_frontmatter_skip_count([by_page[pn] for pn in ordered_pages])
    if skip_n <= 0:
        return doc

    skip_pages = set(ordered_pages[:skip_n])
    keep_pages = [pn for pn in ordered_pages if pn not in skip_pages]
    if not keep_pages:
        # Mis-detect: would drop entire document — keep original
        return doc

    page_map = {old: idx + 1 for idx, old in enumerate(keep_pages)}
    # Include image-only pages that sit after the front-matter block
    for img in doc.images:
        pn = int(img.page_number)
        if pn in skip_pages or pn in page_map:
            continue
        if ordered_pages and pn > ordered_pages[min(skip_n - 1, len(ordered_pages) - 1)]:
            page_map[pn] = len(page_map) + 1

    new_paras = [
        ParagraphBlock(
            **{
                **p.model_dump(),
                "page_number": page_map[int(p.page_number)],
            }
        )
        for p in doc.paragraphs
        if int(p.page_number) in page_map
    ]
    new_imgs = [
        ImageBlock(
            **{
                **img.model_dump(),
                "page_number": page_map[int(img.page_number)],
            }
        )
        for img in doc.images
        if int(img.page_number) in page_map
    ]
    if not new_paras:
        return doc

    logger.info(
        "analysis frontmatter skip: dropped %s leading page(s) (%s → %s body pages)",
        skip_n,
        doc.total_pages,
        len(keep_pages),
    )
    return DocumentModel(
        filename=doc.filename,
        total_pages=max(page_map.values()) if page_map else len(keep_pages),
        paragraphs=new_paras,
        images=new_imgs,
    )


def extract_review_blocks(file_path: str, limit: int = 400) -> List[Dict[str, Any]]:
    """
    Extract body blocks for Document Review.

    Returns list of {"text": str, "block_type": str}.
    Empty lines are never returned. Front-matter pages are omitted.
    """
    if not file_path or not os.path.exists(file_path):
        return []
    ext = os.path.splitext(file_path)[1].lower()
    if ext != ".docx":
        return []

    try:
        from docx import Document as DocxDocument

        doc = DocxDocument(file_path)
    except Exception as exc:
        logger.warning("review_blocks: failed to open %s: %s", file_path, exc)
        return []

    pages = _split_docx_pages(doc)
    skip_pages = _leading_frontmatter_page_count(pages)

    blocks: List[Dict[str, Any]] = []
    for page_index, page in enumerate(pages):
        for _para, text, style, is_list in page:
            if not text:
                continue
            if page_index < skip_pages:
                # Still classify so callers can mark legacy rows as frontmatter
                blocks.append(
                    {
                        "text": text,
                        "block_type": BLOCK_FRONTMATTER,
                        "skipped": True,
                    }
                )
                continue
            block_type = classify_block_text(text, style, is_list=is_list)
            if not block_type or block_type == BLOCK_FRONTMATTER:
                continue
            blocks.append({"text": text, "block_type": block_type, "skipped": False})
            if len([b for b in blocks if not b.get("skipped")]) >= limit:
                break
        if len([b for b in blocks if not b.get("skipped")]) >= limit:
            break

    body = [b for b in blocks if not b.get("skipped")]
    # If everything was classified frontmatter (mis-detect), fall back to all non-empty
    if not body:
        body = []
        for page in pages:
            for _para, text, style, is_list in page:
                if not text:
                    continue
                bt = classify_block_text(text, style, is_list=is_list) or BLOCK_PARAGRAPH
                if bt == BLOCK_FRONTMATTER:
                    bt = BLOCK_PARAGRAPH
                body.append({"text": text, "block_type": bt})
                if len(body) >= limit:
                    break
            if len(body) >= limit:
                break
    else:
        body = [{"text": b["text"], "block_type": b["block_type"]} for b in body]

    return body


def frontmatter_text_set(file_path: str) -> Set[str]:
    """Texts that belong to skipped front-matter pages (for legacy row tagging)."""
    if not file_path or not os.path.exists(file_path):
        return set()
    try:
        from docx import Document as DocxDocument

        doc = DocxDocument(file_path)
        pages = _split_docx_pages(doc)
        skip_pages = _leading_frontmatter_page_count(pages)
        texts: Set[str] = set()
        for page_index, page in enumerate(pages):
            if page_index >= skip_pages:
                break
            for _p, text, _s, _l in page:
                if text:
                    texts.add(text)
        return texts
    except Exception:
        return set()
