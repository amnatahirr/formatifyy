"""
frontmatter_detector.py — Detect cover page and project-details page in a DOCX.

Hybrid approach (same spirit as heading_analysis):
  1. Cheap heuristic pre-check on the first two pages (layout + keywords).
  2. If either page is ambiguous (confidence in a mid band), optionally call
     functions.frontmatter_classify LLM JSON classifier.

Pages are split by hard page breaks; if none exist, a soft split uses the
first half of early paragraphs as page 1 and the rest as page 2.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

from models import DetectionResult

# Ambiguity band — outside this we trust heuristics alone
_CONF_LOW = 0.40
_CONF_HIGH = 0.75

_UNIVERSITY_RE = re.compile(
    r"\b(university|institute|college|comsats|nust|fast|ned|bahria|lums)\b",
    re.IGNORECASE,
)
_COVER_TITLE_HINTS = re.compile(
    r"\b(final\s+year\s+project|fyp|project\s+report|thesis|dissertation|"
    r"submitted\s+in\s+partial|bachelor|bs\s*[- ]?cs|degree)\b",
    re.IGNORECASE,
)
_INFO_LABEL_RE = re.compile(
    r"\b(?:group\s*members?|supervisor|co[- ]?supervisor|registration\s*(?:no|number|#)|"
    r"reg\.?\s*no|student\s*name|project\s*title|session|department|"
    r"domain|area\s*of\s*interest|signature)\b",
    re.IGNORECASE,
)
_REG_NO_RE = re.compile(
    r"\b(?:[A-Z]{2,4}[-/]?\d{2}[-/]?\d{3,5}|\d{2}[-/][A-Z]{2,4}[-/]\d{3,5})\b",
    re.IGNORECASE,
)
_CHECKBOX_RE = re.compile(r"[☐☑☒□■✅✓✔\[\s]*[xX✓]\s*\]")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


@dataclass
class ParaLayout:
    """Lightweight layout snapshot for one paragraph."""
    text: str = ""
    style: str = "Normal"
    alignment: str = "left"
    font_size: Optional[float] = None
    bold: bool = False
    has_image: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "style": self.style,
            "alignment": self.alignment,
            "font_size": self.font_size,
            "bold": self.bold,
            "has_image": self.has_image,
        }


@dataclass
class PageSnapshot:
    """Extracted content for one logical page."""
    page_number: int
    paragraphs: List[ParaLayout] = field(default_factory=list)
    table_count: int = 0
    image_count: int = 0

    @property
    def full_text(self) -> str:
        return "\n".join(p.text for p in self.paragraphs if p.text.strip())

    def as_dicts(self) -> List[Dict[str, Any]]:
        return [p.as_dict() for p in self.paragraphs]


@dataclass
class HeuristicScore:
    present: bool
    confidence: float
    signals: List[str] = field(default_factory=list)


def _alignment_name(alignment: Any) -> str:
    if alignment is None:
        return "left"
    try:
        if alignment == WD_ALIGN_PARAGRAPH.CENTER:
            return "center"
        if alignment == WD_ALIGN_PARAGRAPH.RIGHT:
            return "right"
        if alignment == WD_ALIGN_PARAGRAPH.JUSTIFY:
            return "justify"
    except Exception:
        pass
    return "left"


def _para_has_image(paragraph) -> bool:
    try:
        blips = paragraph._element.findall(".//" + qn("a:blip"))
        return bool(blips)
    except Exception:
        return False


def _para_has_page_break(paragraph) -> bool:
    """True if this paragraph contains a hard page break."""
    try:
        for br in paragraph._element.findall(".//" + qn("w:br")):
            if br.get(qn("w:type")) == "page":
                return True
        # Explicit lastRenderedPageBreak (Word sometimes writes these)
        if paragraph._element.findall(".//" + qn("w:lastRenderedPageBreak")):
            return True
    except Exception:
        pass
    return False


def _extract_para_layout(paragraph) -> ParaLayout:
    text = (paragraph.text or "").strip()
    style = "Normal"
    try:
        style = paragraph.style.name if paragraph.style else "Normal"
    except Exception:
        pass

    font_size: Optional[float] = None
    bold = False
    for run in paragraph.runs:
        if run.bold:
            bold = True
        try:
            if run.font.size is not None:
                pt = run.font.size.pt
                if font_size is None or pt > font_size:
                    font_size = float(pt)
        except Exception:
            pass

    return ParaLayout(
        text=text,
        style=style or "Normal",
        alignment=_alignment_name(paragraph.alignment),
        font_size=font_size,
        bold=bold,
        has_image=_para_has_image(paragraph),
    )


def _split_into_pages(doc: Document, max_pages: int = 2) -> List[PageSnapshot]:
    """
    Split body paragraphs into pages using hard page breaks.
    Falls back to a soft split of early paragraphs when no breaks exist.
    """
    pages: List[PageSnapshot] = [PageSnapshot(page_number=1)]
    current = pages[0]

    body_paras = list(doc.paragraphs)
    for para in body_paras:
        layout = _extract_para_layout(para)
        if layout.text or layout.has_image:
            current.paragraphs.append(layout)
            if layout.has_image:
                current.image_count += 1
        if _para_has_page_break(para) and len(pages) < max_pages:
            current = PageSnapshot(page_number=len(pages) + 1)
            pages.append(current)

    # Soft split if we only got one page but enough content for two
    if len(pages) == 1 and len(pages[0].paragraphs) >= 6:
        all_paras = pages[0].paragraphs
        mid = max(3, len(all_paras) // 2)
        # Prefer split near a short centered/title-like para if present
        for i in range(2, min(len(all_paras) - 2, 20)):
            p = all_paras[i]
            if p.alignment == "center" and len(p.text) < 80:
                mid = i + 1
                break
        page1 = PageSnapshot(page_number=1, paragraphs=all_paras[:mid])
        page2 = PageSnapshot(page_number=2, paragraphs=all_paras[mid:])
        page1.image_count = sum(1 for p in page1.paragraphs if p.has_image)
        page2.image_count = sum(1 for p in page2.paragraphs if p.has_image)
        pages = [page1, page2]

    while len(pages) < max_pages:
        pages.append(PageSnapshot(page_number=len(pages) + 1))

    # Count tables whose preceding text still sits on page 1 vs 2 is hard;
    # attribute all early tables to page 1 / later to page 2 by document order.
    tables = list(doc.tables)
    if tables:
        half = max(1, (len(tables) + 1) // 2)
        pages[0].table_count = len(tables[:half]) if len(pages) > 1 else len(tables)
        if len(pages) > 1:
            pages[1].table_count = len(tables[half:]) if len(tables) > 1 else (
                1 if pages[0].table_count == 0 and tables else 0
            )
            # Prefer attributing the first table to page 2 when page 2 looks like info
            if pages[1].table_count == 0 and pages[0].table_count > 0:
                # Keep first table on page 1 for cover+table docs; info page often has table
                pass

    return pages[:max_pages]


def extract_first_pages(docx_path: str, max_pages: int = 2) -> List[PageSnapshot]:
    """Public helper: load DOCX and return layout snapshots for the first pages."""
    doc = Document(docx_path)
    return _split_into_pages(doc, max_pages=max_pages)


def score_cover_page(page: PageSnapshot) -> HeuristicScore:
    """Heuristic: is this page a cover / title page?"""
    signals: List[str] = []
    score = 0.0
    paras = [p for p in page.paragraphs if p.text.strip() or p.has_image]
    text = page.full_text
    word_count = len(text.split())

    centered = [p for p in paras if p.alignment == "center" and p.text.strip()]
    large = [
        p for p in paras
        if (p.font_size or 0) >= 16 or (p.bold and p.alignment == "center")
    ]
    title_style = [
        p for p in paras
        if (p.style or "").lower().startswith("title")
        or (p.style or "").lower().startswith("heading")
    ]

    if centered:
        score += 0.22
        signals.append(f"centered_paragraphs={len(centered)}")
    if large or title_style:
        score += 0.20
        signals.append("large_or_title_text")
    if _UNIVERSITY_RE.search(text):
        score += 0.18
        signals.append("university_name")
    if page.image_count > 0 or any(p.has_image for p in paras):
        score += 0.15
        signals.append("logo_or_image")
    if _COVER_TITLE_HINTS.search(text):
        score += 0.15
        signals.append("cover_phrasing")
    if word_count > 0 and word_count <= 120:
        score += 0.12
        signals.append(f"minimal_body_words={word_count}")
    elif word_count > 250:
        score -= 0.20
        signals.append(f"too_much_body_words={word_count}")

    # Dense body + no cover signals → reject
    if word_count > 180 and not centered and not _UNIVERSITY_RE.search(text):
        score = min(score, 0.25)
        signals.append("looks_like_body")

    score = max(0.0, min(1.0, score))
    present = score >= 0.55
    return HeuristicScore(present=present, confidence=round(score, 3), signals=signals)


def score_info_page(page: PageSnapshot) -> HeuristicScore:
    """Heuristic: is this page a project-details / group-info page?"""
    signals: List[str] = []
    score = 0.0
    text = page.full_text

    label_hits = _INFO_LABEL_RE.findall(text)
    if label_hits:
        score += min(0.35, 0.12 * len(set(h.lower() for h in label_hits)))
        signals.append(f"labels={sorted({h.lower() for h in label_hits})}")

    if page.table_count > 0:
        score += 0.25
        signals.append(f"tables={page.table_count}")

    # Key-value style: short lines with a colon
    kv_lines = 0
    for p in page.paragraphs:
        t = p.text.strip()
        if ":" in t and len(t) < 120:
            left = t.split(":", 1)[0].strip().lower()
            if _INFO_LABEL_RE.search(left) or len(left.split()) <= 4:
                kv_lines += 1
    if kv_lines >= 2:
        score += 0.20
        signals.append(f"key_value_lines={kv_lines}")

    reg_hits = _REG_NO_RE.findall(text)
    if reg_hits:
        score += 0.15
        signals.append(f"reg_numbers={len(reg_hits)}")

    if _CHECKBOX_RE.search(text) or re.search(
        r"\b(AI|NLP|Mobile|Web|IoT|ML|SE)\b.*\b(AI|NLP|Mobile|Web|IoT|ML|SE)\b",
        text,
        re.IGNORECASE,
    ):
        score += 0.10
        signals.append("checkboxes_or_domain_list")

    if _EMAIL_RE.search(text):
        score += 0.05
        signals.append("emails_present")

    # Pure prose chapter start → not info page
    word_count = len(text.split())
    if word_count > 200 and kv_lines < 2 and page.table_count == 0 and not label_hits:
        score = min(score, 0.2)
        signals.append("looks_like_chapter_body")

    score = max(0.0, min(1.0, score))
    present = score >= 0.55
    return HeuristicScore(present=present, confidence=round(score, 3), signals=signals)


def _is_ambiguous(score: HeuristicScore) -> bool:
    return _CONF_LOW <= score.confidence <= _CONF_HIGH


def detect_frontmatter_heuristic(docx_path: str) -> Tuple[DetectionResult, List[PageSnapshot]]:
    """Run heuristic-only detection (no LLM). Also returns page snapshots."""
    pages = extract_first_pages(docx_path, max_pages=2)
    cover = score_cover_page(pages[0])
    info = score_info_page(pages[1] if len(pages) > 1 else PageSnapshot(2))

    overall = round((cover.confidence + info.confidence) / 2.0, 3)
    reasoning = (
        f"Heuristic cover={cover.confidence:.2f} ({', '.join(cover.signals) or 'none'}); "
        f"info={info.confidence:.2f} ({', '.join(info.signals) or 'none'})."
    )
    result = DetectionResult(
        cover_page_present=cover.present,
        info_page_present=info.present,
        cover_confidence=cover.confidence,
        info_confidence=info.confidence,
        confidence=overall,
        reasoning=reasoning,
        used_llm=False,
        cover_signals=cover.signals,
        info_signals=info.signals,
    )
    return result, pages


async def detect_frontmatter(
    docx_path: str,
    client: Any = None,
    force_llm: bool = False,
) -> DetectionResult:
    """
    Hybrid detection entry point.

    Uses heuristics first; if either page is ambiguous (or force_llm=True)
    and a client is provided, consults the LLM classifier and merges results.
    """
    heuristic, pages = detect_frontmatter_heuristic(docx_path)
    cover_score = HeuristicScore(
        present=heuristic.cover_page_present,
        confidence=heuristic.cover_confidence,
        signals=list(heuristic.cover_signals),
    )
    info_score = HeuristicScore(
        present=heuristic.info_page_present,
        confidence=heuristic.info_confidence,
        signals=list(heuristic.info_signals),
    )

    need_llm = force_llm or _is_ambiguous(cover_score) or _is_ambiguous(info_score)
    if not need_llm or client is None:
        if need_llm and client is None:
            heuristic.reasoning += " Ambiguous but no LLM client — heuristic only."
        return heuristic

    from functions.frontmatter_classify import classify_frontmatter_with_llm

    llm = await classify_frontmatter_with_llm(
        client,
        pages[0].as_dicts(),
        pages[1].as_dicts() if len(pages) > 1 else [],
        heuristic_hints={
            "cover_page_present": heuristic.cover_page_present,
            "info_page_present": heuristic.info_page_present,
            "cover_confidence": heuristic.cover_confidence,
            "info_confidence": heuristic.info_confidence,
            "cover_signals": heuristic.cover_signals,
            "info_signals": heuristic.info_signals,
        },
    )
    if llm.get("error"):
        heuristic.reasoning += f" LLM skipped: {llm.get('reasoning', 'error')}."
        return heuristic

    # Prefer LLM boolean flags; blend confidences
    llm_conf = float(llm.get("confidence") or 0.7)
    llm_conf = max(0.0, min(1.0, llm_conf))

    cover_present = bool(llm.get("cover_page_present"))
    info_present = bool(llm.get("info_page_present"))

    # If LLM agrees with heuristic, boost; if disagrees, trust LLM but note it
    cover_conf = llm_conf if cover_present == heuristic.cover_page_present else max(0.55, llm_conf)
    info_conf = llm_conf if info_present == heuristic.info_page_present else max(0.55, llm_conf)

    reasoning = (
        f"Hybrid: heuristic cover={heuristic.cover_confidence:.2f}, "
        f"info={heuristic.info_confidence:.2f}. "
        f"LLM: {llm.get('reasoning') or 'classified'}."
    )
    return DetectionResult(
        cover_page_present=cover_present,
        info_page_present=info_present,
        cover_confidence=round(cover_conf, 3),
        info_confidence=round(info_conf, 3),
        confidence=round((cover_conf + info_conf) / 2.0, 3),
        reasoning=reasoning,
        used_llm=True,
        cover_signals=heuristic.cover_signals,
        info_signals=heuristic.info_signals,
    )
