"""
review_blocks.py — Extract classified body blocks for supervisor Document Review.

Skips front-matter pages (cover, info), ignores empty lines, and labels each
remaining block as:
  heading | subheading | paragraph | line | bullet | toc | table | image

Rich content (NEW):
  * The document body is walked in order, so tables (w:tbl), content controls
    (w:sdt, where Word keeps the TOC) and inline images are no longer lost.
  * Text is read from every w:t, so hyperlink text inside TOC entries is kept
    ("Introduction\\t1" instead of just "1").
  * Table blocks carry "table_rows"  -> [[{text, colSpan, fillHex, bold}, ...], ...]
  * Image blocks / paragraphs carry "images" -> [{base64, width_px, height_px, alt}]
  * Every block also carries "style_name" (and "alignment" when set directly).
"""

from __future__ import annotations

import base64
import logging
import os
import re
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple

try:  # python-docx; extract_review_blocks() returns [] later if it is missing
    from docx.oxml.ns import qn
    from docx.text.paragraph import Paragraph
except Exception:  # pragma: no cover
    qn = None  # type: ignore[assignment]
    Paragraph = None  # type: ignore[assignment]

from docx_tools.review_format import (  # noqa: E402  (needs python-docx, guarded import above)
    FormatResolver,
    apply_real_toc_pages,
    in_textbox,
    run_text,
)

logger = logging.getLogger(__name__)

# Bump whenever the extractor output changes: the router re-parses older rows
# (only for documents without comments, so comment anchors are never lost).
EXTRACT_VERSION = 3

# Block types stored in document_paragraphs.block_type
BLOCK_HEADING = "heading"
BLOCK_SUBHEADING = "subheading"
BLOCK_PARAGRAPH = "paragraph"
BLOCK_LINE = "line"
BLOCK_BULLET = "bullet"
BLOCK_FRONTMATTER = "frontmatter"
BLOCK_TOC = "toc"
BLOCK_TABLE = "table"
BLOCK_IMAGE = "image"

_DISPLAY_LABELS = {
    BLOCK_HEADING: "Heading",
    BLOCK_SUBHEADING: "Subheading",
    BLOCK_PARAGRAPH: "Paragraph",
    BLOCK_LINE: "Line",
    BLOCK_BULLET: "Bullet",
    BLOCK_TOC: "Table of Contents",
    BLOCK_TABLE: "Table",
    BLOCK_IMAGE: "Image",
}

# Which leading pages the supervisor review hides. The TOC / list of figures /
# list of tables pages are now SHOWN (the review screen renders them with dotted
# leaders). Add "toc", "lof", "lot" here to hide them again.
_REVIEW_FRONT_KINDS = frozenset({"cover", "info"})

# Image limits (images are sent inline as base64).
EMU_PER_PX = 9525
MAX_IMAGE_BYTES = 1_500_000          # per image
MAX_TOTAL_IMAGE_BYTES = 12_000_000   # per document
_RENDERABLE_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/gif",
    "image/webp",
    "image/bmp",
}
_VML_NS = "urn:schemas-microsoft-com:vml"
_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

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
# Word often splits one TOC row into two paragraphs ("1." then "Abstract … 7").
_TOC_NUMBER_ONLY_RE = re.compile(r"^\d+(?:\.\d+)*\.?\s*$")
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
            from frontmatter.frontmatter_detector import (
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


# ─────────────────────────────────────────────────────────────────────────────
# Rich content helpers: text, images, tables
# ─────────────────────────────────────────────────────────────────────────────

def _el_text(el) -> str:
    """
    All text of a paragraph element, including text inside hyperlinks, simple
    fields and content controls. python-docx's `paragraph.text` can drop the
    hyperlink part, which is why TOC entries used to come out as just "1", "2".
    Tabs are kept as "\\t" so "Introduction\\t1" can be split by the app.
    """
    return "".join(run_text(r) for r in el.iter(qn("w:r")) if not in_textbox(r, el))


def _has_image(p_el) -> bool:
    for drawing in p_el.iter(qn("w:drawing")):
        if next(drawing.iter(qn("a:blip")), None) is not None:
            return True
        if next(drawing.iter(qn("c:chart")), None) is not None:
            return True
    return next(p_el.iter("{%s}imagedata" % _VML_NS), None) is not None


def _append_image(
    rid: Optional[str],
    doc,
    budget: Dict[str, int],
    images: List[Dict[str, Any]],
    notes: List[str],
    width: Optional[float],
    height: Optional[float],
    alt: Optional[str],
) -> None:
    try:
        part = doc.part.related_parts.get(rid) if rid else None
    except Exception:
        part = None
    if part is None:
        return
    ctype = (getattr(part, "content_type", "") or "").lower()
    if ctype not in _RENDERABLE_IMAGE_TYPES:
        # EMF / WMF / TIFF etc. cannot be drawn by Flutter's Image widget.
        kind = ctype.split("/")[-1] or "unknown"
        notes.append(f"[Image not previewable ({kind}) - open the original file]")
        return
    blob = part.blob
    if len(blob) > MAX_IMAGE_BYTES or budget["bytes"] + len(blob) > MAX_TOTAL_IMAGE_BYTES:
        notes.append("[Image too large to preview]")
        return
    budget["bytes"] += len(blob)
    images.append(
        {
            "base64": base64.b64encode(blob).decode("ascii"),
            "width_px": width,
            "height_px": height,
            "alt": alt or None,
        }
    )


def _paragraph_images(p_el, doc, budget: Dict[str, int]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Returns (images, notes). `notes` are short placeholders for images/charts
    that cannot be sent (unsupported format, too large, native chart)."""
    images: List[Dict[str, Any]] = []
    notes: List[str] = []

    for drawing in p_el.iter(qn("w:drawing")):
        blip = next(drawing.iter(qn("a:blip")), None)
        if blip is None:
            if next(drawing.iter(qn("c:chart")), None) is not None:
                notes.append("[Chart - open the original file to view it]")
            continue
        extent = next(drawing.iter(qn("wp:extent")), None)
        doc_pr = next(drawing.iter(qn("wp:docPr")), None)
        width = height = None
        if extent is not None:
            try:
                width = round(int(extent.get("cx")) / EMU_PER_PX, 1)
                height = round(int(extent.get("cy")) / EMU_PER_PX, 1)
            except (TypeError, ValueError):
                pass
        alt = doc_pr.get("descr") if doc_pr is not None else None
        _append_image(blip.get(qn("r:embed")), doc, budget, images, notes, width, height, alt)

    if not images and not notes:  # legacy VML pictures
        for im in p_el.iter("{%s}imagedata" % _VML_NS):
            _append_image(im.get("{%s}id" % _R_NS), doc, budget, images, notes, None, None, None)

    return images, notes


def _cell_text(tc) -> str:
    parts: List[str] = []
    for child in tc:
        if child.tag == qn("w:p"):
            parts.append(_el_text(child).strip())
        elif child.tag == qn("w:tbl"):  # nested table → flatten
            parts.append(" ".join(_el_text(p).strip() for p in child.iter(qn("w:p"))).strip())
    return "\n".join(p for p in parts if p)


def _cell_is_bold(tc) -> bool:
    runs = [
        r
        for r in tc.iter(qn("w:r"))
        if "".join(t.text or "" for t in r.iter(qn("w:t"))).strip()
    ]
    if not runs:
        return False
    for run in runs:
        r_pr = run.find(qn("w:rPr"))
        bold = r_pr.find(qn("w:b")) if r_pr is not None else None
        if bold is None or bold.get(qn("w:val")) in ("0", "false"):
            return False
    return True


def _table_rows(tbl_el) -> List[List[Dict[str, Any]]]:
    rows: List[List[Dict[str, Any]]] = []
    for tr in tbl_el.iterchildren(qn("w:tr")):
        cells: List[Dict[str, Any]] = []
        for tc in tr.iterchildren(qn("w:tc")):
            span, fill = 1, None
            tc_pr = tc.find(qn("w:tcPr"))
            if tc_pr is not None:
                grid_span = tc_pr.find(qn("w:gridSpan"))
                if grid_span is not None:
                    try:
                        span = max(1, int(grid_span.get(qn("w:val")) or 1))
                    except ValueError:
                        span = 1
                shd = tc_pr.find(qn("w:shd"))
                if shd is not None:
                    fill = shd.get(qn("w:fill"))
            cells.append(
                {
                    "text": _cell_text(tc),
                    "colSpan": span,
                    "fillHex": fill if fill and fill.lower() != "auto" else None,
                    "bold": _cell_is_bold(tc),
                }
            )
        if cells:
            rows.append(cells)
    return rows


def _table_flat_text(rows: List[List[Dict[str, Any]]]) -> str:
    return "\n".join(" | ".join(c["text"] for c in row) for row in rows).strip()


def _iter_body_items(parent) -> Iterator[Tuple[str, Any]]:
    """Body children in document order: ("p", w:p) / ("tbl", w:tbl).
    Content controls (w:sdt — where Word stores the TOC) are entered."""
    for child in parent.iterchildren():
        tag = child.tag
        if tag == qn("w:p"):
            yield "p", child
        elif tag == qn("w:tbl"):
            yield "tbl", child
        elif tag == qn("w:sdt"):
            content = child.find(qn("w:sdtContent"))
            if content is not None:
                yield from _iter_body_items(content)


def _is_toc_entry(p_el, style: str, text: str) -> bool:
    s = (style or "").strip().lower()
    if s.startswith("toc") and "heading" not in s:  # "TOC 1", "toc 2"
        return True
    if s in ("table of figures", "table of authorities"):
        return True
    for link in p_el.iter(qn("w:hyperlink")):
        if (link.get(qn("w:anchor")) or "").startswith("_Toc"):
            return True
    return bool(text and len(text) < 220 and _TOC_LEADER_RE.search(text))


# ─────────────────────────────────────────────────────────────────────────────
# Pages / front-matter detection
# ─────────────────────────────────────────────────────────────────────────────

def _split_docx_pages(doc) -> List[List[Tuple[Any, str, str, bool]]]:
    """
    Split into pages of (item, text, style, is_list).

    `item` is a dict: {"kind": "p", "el", "para", "doc", "has_image"} for a
    paragraph, or {"kind": "tbl", "rows"} for a table. Empty text paragraphs are
    kept only when they hold an image (or as page-break carriers); tables keep
    their flattened text so front-matter detection can still see them.
    """
    pages: List[List[Tuple[Any, str, str, bool]]] = [[]]
    fmt = FormatResolver(doc)
    for kind, el in _iter_body_items(doc.element.body):
        if kind == "p":
            para = Paragraph(el, doc)
            text = _el_text(el).strip()
            style = _para_style_name(para)
            is_list = _para_is_list(para, style)
            has_image = _has_image(el)
            if text or has_image:
                item = {
                    "kind": "p",
                    "el": el,
                    "para": para,
                    "doc": doc,
                    "has_image": has_image,
                    "fmt": fmt,
                }
                pages[-1].append((item, text, style, is_list))
            if _para_has_page_break(para):
                pages.append([])
        else:
            rows = _table_rows(el)
            if rows:
                flat = _table_flat_text(rows)
                pages[-1].append(({"kind": "tbl", "rows": rows}, flat, "Table", False))
    # Drop trailing empty page
    while pages and not pages[-1]:
        pages.pop()
    return pages or [[]]


def _leading_frontmatter_skip_count(
    page_text_lists: Sequence[Sequence[str]],
    front_kinds: Optional[Iterable[str]] = None,
) -> int:
    """How many leading pages to skip. Cap at 5.

    `front_kinds` defaults to cover/info/toc/lof/lot (used by the student
    analysis pipeline); the supervisor review passes a smaller set."""
    pages = list(page_text_lists)
    skip = 0
    kinds = (
        set(front_kinds)
        if front_kinds is not None
        else {"cover", "info", "toc", "lof", "lot"}
    )
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
        if kind in kinds:
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


def _leading_frontmatter_page_count(
    pages: List[List[Tuple[Any, str, str, bool]]],
    front_kinds: Optional[Iterable[str]] = None,
) -> int:
    """How many leading docx pages to skip. Cap at 5."""
    return _leading_frontmatter_skip_count(
        [[t for _, t, _, _ in page] for page in pages], front_kinds
    )


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


# ─────────────────────────────────────────────────────────────────────────────
# Block building
# ─────────────────────────────────────────────────────────────────────────────

def _build_block(
    item: Dict[str, Any],
    text: str,
    style: str,
    is_list: bool,
    budget: Dict[str, int],
) -> Optional[Dict[str, Any]]:
    """One page item → one review block (or None to ignore it)."""
    if item["kind"] == "tbl":
        # text is the flattened table, so older code paths that only read
        # `text` still see something; the app renders `table_rows`.
        return {
            "text": text,
            "block_type": BLOCK_TABLE,
            "style_name": "Table",
            "table_rows": item["rows"],
        }

    el = item["el"]
    fmt: FormatResolver = item["fmt"]
    meta: Dict[str, Any] = {"style_name": style}
    align = fmt.alignment(el)
    if align:
        meta["alignment"] = align

    if text and _style_is_toc_entry(style):
        norm = _normalize_toc_text(text)
        # Full row or the first half Word split onto its own paragraph ("1." / "2. Chapter 1 —").
        if _is_toc_entry(el, style, norm) or _is_toc_prefix_fragment(norm):
            props, _ = fmt.paragraph_format(el, style_only=True)
            return {"text": norm, "block_type": BLOCK_TOC, **meta, **props}

    props, runs = fmt.paragraph_format(el)
    meta.update(props)
    indent = fmt.indent_level(el)
    if indent:
        meta["indent_level"] = indent
    if runs:
        meta["runs"] = runs

    images: List[Dict[str, Any]] = []
    notes: List[str] = []
    if item["has_image"]:
        images, notes = _paragraph_images(item["el"], item["doc"], budget)

    if not text:
        if images:
            return {"text": "[Image]", "block_type": BLOCK_IMAGE, "images": images, **meta}
        if notes:
            return {"text": " ".join(notes), "block_type": BLOCK_LINE, **meta}
        return None

    block_type = classify_block_text(text, style, is_list=is_list)
    if not block_type or block_type == BLOCK_FRONTMATTER:
        return None
    block: Dict[str, Any] = {"text": text, "block_type": block_type, **meta}
    if images:
        block["images"] = images  # picture inside a text paragraph
    return block


def _normalize_toc_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\r", "").replace("\n", " ")).strip()



def _style_is_toc_entry(style: str) -> bool:
    s = (style or "").strip().lower()
    return (s.startswith("toc") and "heading" not in s) or s in (
        "table of figures", "table of authorities")


def _block_is_tocish(block: Dict[str, Any]) -> bool:
    if (block.get("block_type") or "").lower() == BLOCK_TOC:
        return True
    return _style_is_toc_entry(str(block.get("style_name") or ""))


def _is_toc_prefix_fragment(text: str) -> bool:
    """First half of a TOC row split across two Word paragraphs."""
    t = _normalize_toc_text(text)
    if not t or len(t) > 96:
        return False
    if _TOC_LEADER_RE.search(t) or "\t" in t:
        return False
    if _TOC_NUMBER_ONLY_RE.match(t):
        return True
    if re.match(r"^\d+(?:\.\d+)*\.?\s+", t):
        if t.rstrip().endswith(("—", "–", "-")):
            return True
        # "2. Chapter 1 —" or "4.5. Software Development Lifecycle" without page yet
        if _word_count(t) <= 8 and not re.search(r"(?<!\d)\d+\s*$", t):
            return True
    return False


def _toc_tail_has_page(block: Dict[str, Any], text: str) -> bool:
    if block.get("page_number"):
        return True
    if "\t" in text or _TOC_LEADER_RE.search(text):
        return True
    return bool(re.search(r"(?<!\d)\d+\s*$", text))


def _should_merge_toc_pair(
    first: Dict[str, Any], second: Dict[str, Any], t0: str, t1: str
) -> bool:
    if not _block_is_tocish(first) and not _block_is_tocish(second):
        return False
    if not _is_toc_prefix_fragment(t0):
        return False
    if not _toc_tail_has_page(second, t1):
        return False
    return True


def _merge_split_toc_entries(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Join Word's split TOC paragraphs into one row per entry."""
    if not blocks:
        return blocks
    out: List[Dict[str, Any]] = []
    i = 0
    while i < len(blocks):
        cur = blocks[i]
        if i + 1 < len(blocks):
            nxt = blocks[i + 1]
            t0 = _normalize_toc_text(cur.get("text") or "")
            t1 = _normalize_toc_text(nxt.get("text") or "")
            if t0 and t1 and _should_merge_toc_pair(cur, nxt, t0, t1):
                merged: Dict[str, Any] = dict(nxt)
                merged["text"] = f"{t0} {t1}".strip()
                merged["block_type"] = BLOCK_TOC
                merged["style_name"] = merged.get("style_name") or cur.get("style_name")
                if cur.get("page_number") and not merged.get("page_number"):
                    merged["page_number"] = cur["page_number"]
                out.append(merged)
                i += 2
                continue
        if (cur.get("block_type") or "").lower() == BLOCK_TOC:
            cur = {**cur, "text": _normalize_toc_text(cur.get("text") or "")}
        out.append(cur)
        i += 1
    return out


def _collect_blocks(
    pages: Sequence[Sequence[Tuple[Any, str, str, bool]]],
    limit: int,
    budget: Dict[str, int],
) -> List[Dict[str, Any]]:
    body: List[Dict[str, Any]] = []
    for page in pages:
        for item, text, style, is_list in page:
            block = _build_block(item, text, style, is_list, budget)
            if block is None:
                continue
            body.append(block)
            if len(body) >= limit:
                return body
    return body


def extract_review_blocks(
    file_path: str, limit: int | None = None
) -> List[Dict[str, Any]]:
    """
    Extract body blocks for Document Review.

    Returns a list of dicts:
      {"text": str, "block_type": str, "style_name": str,
       optional: "alignment", "table_rows", "images"}
    Empty lines are never returned. Cover / info pages are omitted.
    """
    if limit is None:
        try:
            limit = int(os.getenv("REVIEW_BLOCK_LIMIT", "3500"))
        except ValueError:
            limit = 3500
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
    skip_pages = _leading_frontmatter_page_count(pages, _REVIEW_FRONT_KINDS)

    budget = {"bytes": 0}
    body = _collect_blocks(pages[skip_pages:], limit, budget)
    # If everything was treated as front-matter (mis-detect), fall back to all pages
    if not body and skip_pages:
        budget = {"bytes": 0}
        body = _collect_blocks(pages, limit, budget)
    body = _merge_split_toc_entries(body)
    # Generated TOCs carry stale cached page numbers → use the real layout.
    apply_real_toc_pages(file_path, doc, body)
    return body


def frontmatter_text_set(file_path: str) -> Set[str]:
    """Texts that belong to skipped front-matter pages (for legacy row tagging)."""
    if not file_path or not os.path.exists(file_path):
        return set()
    try:
        from docx import Document as DocxDocument

        doc = DocxDocument(file_path)
        pages = _split_docx_pages(doc)
        skip_pages = _leading_frontmatter_page_count(pages, _REVIEW_FRONT_KINDS)
        texts: Set[str] = set()
        for page_index, page in enumerate(pages):
            if page_index >= skip_pages:
                break
            for _item, text, _s, _l in page:
                if text:
                    texts.add(text)
        return texts
    except Exception:
        return set()