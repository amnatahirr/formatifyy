"""
Bullet Formatter Service — applies real Word OOXML bullet/numbering to DOCX.

Detection strategy (in priority order):
  1. Already List Paragraph style → always bullet
  2. Numbered section heading (1. 2. 3.) → never bullet
  3. Title-case subheading (≤4 words, all caps) → never bullet
  4. Starts with a plain-text bullet char → bullet (upgrade to OOXML)
  5. Label-prefix pattern "Label: desc" or "Label - desc" → bullet
  6. Ordinal step ("First step...", "Final step...") → bullet
  7. Long prose without label (> 8 words, ends with . ? !) → never bullet
     UNLESS prev paragraph is already bulleted (continuation signal)
  8. Context: prev ends ":" or has list keyword → bullet
  9. Continuation: prev is bulleted AND current is short (≤12 words, no punct)
  10. Document-level forward scan: finds runs of consecutive Normal paragraphs
      under a Heading and marks them as list items (catches "Moreover..." style items)

FIX (2026-05-02):
  - _scan_list_regions: replaced the single start_k=1 intro-skip with a
    per-item check so that label-prefix paragraphs are never skipped,
    regardless of their word count or position in the section.
  - _scan_list_regions: label-pattern fallback at the bottom of the loop
    now applies to any non-heading style, not just "normal".
"""

from copy import deepcopy
import random
import re
from docx import Document as DocxDocument
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from typing import Dict, Any, List, Optional, Set
from enum import Enum


class BulletStyle(Enum):
    FILLED_CIRCLE = "filled_circle"
    EMPTY_CIRCLE  = "empty_circle"
    SQUARE        = "square"
    DASH          = "dash"
    ARROW         = "arrow"
    DECIMAL       = "decimal"
    LOWER_LETTER  = "lower_letter"
    UPPER_LETTER  = "upper_letter"
    LOWER_ROMAN   = "lower_roman"


_STYLE_DEFS: Dict[str, tuple] = {
    "filled_circle": ("\u2022", "Symbol",      "bullet"),
    "empty_circle":  ("\u006F", "Courier New", "bullet"),
    "square":        ("\u25A0", "Wingdings",   "bullet"),
    "dash":          ("\u2013", "Calibri",     "bullet"),
    "arrow":         ("\u27A2", "Wingdings",   "bullet"),
    "decimal":       ("%1.",    None,           "decimal"),
    "lower_letter":  ("%1.",    None,           "lowerLetter"),
    "upper_letter":  ("%1.",    None,           "upperLetter"),
    "lower_roman":   ("%1.",    None,           "lowerRoman"),
}

_LIST_CONTEXT_KEYWORDS = [
    'following', 'below', 'includes', 'consists of', 'contains',
    'such as', 'examples', 'list', 'steps', 'requirements',
    'features', 'benefits', 'include:', 'followed by:', 'as follows:'
]

_BULLET_CHARS  = ('•', '○', '■', '-', '*', '→', '»')
_LABEL_PATTERN = re.compile(r'^[A-Za-z][A-Za-z0-9 ,/\-\(\)\.]{1,60}[:\-]\s+\S')
_STEP_PATTERN  = re.compile(
    r'^(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|'
    r'final|last|next|then|another)\s+(step|item|point|stage|phase|task)',
    re.IGNORECASE
)
_NUM_HEADING   = re.compile(r'^\d+[\.\)]\s+[A-Z]')
_SMALL_WORDS   = {'a','an','the','in','of','for','and','or','but','to','with','by'}


class BulletFormatterService:

    def __init__(self):
        self.style_map = {s.value: s for s in BulletStyle}

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def apply_bullet_formatting(
        self,
        docx_path: str,
        output_path: str,
        formatting_rules: Optional[Dict[str, Any]] = None,
        bullet_mapping: Optional[Dict[int, BulletStyle]] = None,
    ) -> bool:
        try:
            doc    = DocxDocument(docx_path)
            cfg    = self._parse_formatting_rules(formatting_rules)

            # Step 1: split <w:br/> soft-break paragraphs
            self._expand_soft_breaks(doc)

            # Step 2: document-level pre-scan to find list regions
            list_indices = self._scan_list_regions(doc)

            # Step 3: register one numbering definition
            style_key = cfg.get("bullet_style", "filled_circle")
            num_id    = self._add_list_definition(doc, style_key)

            # Step 4: apply to paragraphs
            paragraphs = doc.paragraphs
            for i, paragraph in enumerate(paragraphs):
                should_bullet = False

                if bullet_mapping and i in bullet_mapping:
                    should_bullet = True
                elif cfg.get("auto_apply_bullets", True):
                    should_bullet = (
                        i in list_indices or
                        self._should_be_bullet(paragraph, paragraphs, i)
                    )

                if should_bullet:
                    self._strip_plain_bullet_char(paragraph)
                    self._apply_ooxml_numbering(paragraph, num_id, level=0)

            doc.save(output_path)
            return True

        except Exception as e:
            import traceback
            print(f"[BulletFormatterService] Error: {e}\n{traceback.format_exc()}")
            return False

    def create_bullet_mapping(
        self,
        detected_bullets: List[Dict[str, Any]],
        default_style: BulletStyle = BulletStyle.FILLED_CIRCLE,
    ) -> Dict[int, BulletStyle]:
        return {b.get("index", 0): default_style for b in detected_bullets}

    # ──────────────────────────────────────────────────────────────────────────
    # Document-level list-region scanner
    # ──────────────────────────────────────────────────────────────────────────

    def _scan_list_regions(self, doc) -> Set[int]:

        paras     = doc.paragraphs
        n         = len(paras)
        list_idxs: Set[int] = set()

        i = 0
        while i < n:
            p          = paras[i]
            text       = p.text.strip()
            style_name = (p.style.name or "").lower()

            # Already List Paragraph → always bullet
            if "list" in style_name and text:
                list_idxs.add(i)
                i += 1
                continue

            if "heading" in style_name:
                # Collect all non-empty Normal paragraphs until next heading
                section: List[tuple] = []
                j = i + 1
                while j < n:
                    nxt_style = (paras[j].style.name or "").lower()
                    if "heading" in nxt_style:
                        break
                    if paras[j].text.strip():
                        section.append((j, paras[j]))
                    elif "list" in nxt_style and paras[j].text.strip():
                        section.append((j, paras[j]))
                    j += 1

                if not section:
                    i = j
                    continue

                # Heading ends with ':' → entire section is a list
                if text.endswith(':'):
                    for idx, _ in section:
                        list_idxs.add(idx)
                    i = j
                    continue

                # ── FIX 1 ────────────────────────────────────────────────────
                # 3+ paragraphs: check every item individually.
                # Only skip a paragraph when it is long prose with NO label
                # prefix (genuine intro/outro narrative). Label-prefix items
                # are bullet candidates regardless of their word count.
                if len(section) >= 3:
                    for idx, sp in section:
                        sp_text  = sp.text.strip()
                        sp_words = len(sp_text.split())
                        # Long paragraph with NO label prefix → intro prose, skip
                        if sp_words > 60 and not _LABEL_PATTERN.match(sp_text):
                            continue
                        list_idxs.add(idx)
                # ── END FIX 1 ────────────────────────────────────────────────
                else:
                    # 1-2 paragraphs → only label-prefix ones
                    for idx, sp in section:
                        if "list" in (sp.style.name or "").lower():
                            list_idxs.add(idx)
                        elif _LABEL_PATTERN.match(sp.text.strip()):
                            list_idxs.add(idx)

                i = j
                continue

            # ── FIX 2 ────────────────────────────────────────────────────────
            # Normal paragraph outside a heading block with label prefix.
            # Previously guarded by `style_name == "normal"` which missed
            # paragraphs whose style differed (e.g. Body Text, No Spacing).
            # Now accepts any non-heading style so label-prefix items are
            # always caught regardless of which paragraph style is applied.
            if text and _LABEL_PATTERN.match(text) and "heading" not in style_name:
                list_idxs.add(i)
            # ── END FIX 2 ────────────────────────────────────────────────────

            i += 1

        return list_idxs

    # ──────────────────────────────────────────────────────────────────────────
    # Per-paragraph detection
    # ──────────────────────────────────────────────────────────────────────────

    def _should_be_bullet(self, paragraph, all_paragraphs, index: int) -> bool:
        """
        Per-paragraph heuristic. Complements _scan_list_regions.
        Handles cases the scan missed (e.g. context-keyword triggered lists).
        """
        text = paragraph.text.strip()
        if not text or len(text) < 3:
            return False

        style_name = (paragraph.style.name if paragraph.style else "").lower()

        if "heading" in style_name:
            return False
        if "list" in style_name:
            return True

        # Numbered section heading
        if _NUM_HEADING.match(text):
            return False

        words         = len(text.split())
        ends_sentence = text.endswith(('.', '?', '!'))
        has_label     = bool(_LABEL_PATTERN.match(text))

        # Title-case subheading (≤4 words, all capitalised, no label, no punct)
        if not ends_sentence and not has_label and words <= 4:
            cap_count = sum(
                1 for w in text.split()
                if w and (w[0].isupper() or w.lower() in _SMALL_WORDS)
            )
            if cap_count == words:
                return False

        # Plain-text bullet char → upgrade
        if any(text.startswith(ch) for ch in _BULLET_CHARS):
            return True

        # Label-prefix → always a list item
        if has_label:
            return True

        # Ordinal step
        if _STEP_PATTERN.match(text):
            return True

        if index == 0:
            return False

        prev       = all_paragraphs[index - 1]
        prev_text  = prev.text.strip()
        prev_style = (prev.style.name if prev.style else "").lower()

        # Numbered section headings ("3. Steps for Writing...") must not act as
        # list-context triggers even if they contain keywords like "steps"
        prev_is_num_heading = bool(_NUM_HEADING.match(prev_text))

        prev_text_lower = prev_text.lower()

        # Previous line ends with colon
        if not prev_is_num_heading and prev_text_lower.rstrip().endswith(':'):
            return True

        # Previous line contains a list-context keyword
        if not prev_is_num_heading:
            for kw in _LIST_CONTEXT_KEYWORDS:
                if kw in prev_text_lower:
                    return True

        # Previous paragraph is already bulleted → continue list
        # Only for short non-sentence items
        prev_pPr = prev._element.find(qn('w:pPr'))
        prev_has_numPr = (
            prev_pPr is not None and
            prev_pPr.find(qn('w:numPr')) is not None
        )
        if prev_has_numPr:
            if not ends_sentence and words <= 12:
                return True
            # Even for longer items, if prev is bulleted and this looks like
            # a continuation (label or step), bullet it
            if has_label or _STEP_PATTERN.match(text):
                return True

        return False

    # ──────────────────────────────────────────────────────────────────────────
    # OOXML Numbering
    # ──────────────────────────────────────────────────────────────────────────

    def _add_list_definition(self, doc, style_key: str) -> int:
        lvl_text, font_name, num_fmt = _STYLE_DEFS.get(
            style_key, ("\u2022", "Symbol", "bullet")
        )
        numbering_elem   = doc.part.numbering_part.numbering_definitions._numbering
        existing_abstract = numbering_elem.findall(qn('w:abstractNum'))
        existing_num      = numbering_elem.findall(qn('w:num'))
        next_abstract_id  = len(existing_abstract)
        next_num_id       = len(existing_num) + 1

        abstract  = self._build_abstract_num(next_abstract_id, num_fmt, lvl_text, font_name)
        first_num = numbering_elem.find(qn('w:num'))
        if first_num is not None:
            first_num.addprevious(abstract)
        else:
            numbering_elem.append(abstract)

        num_elem = OxmlElement('w:num')
        num_elem.set(qn('w:numId'), str(next_num_id))
        an = OxmlElement('w:abstractNumId')
        an.set(qn('w:val'), str(next_abstract_id))
        num_elem.append(an)
        numbering_elem.append(num_elem)
        return next_num_id

    def _build_abstract_num(self, abstract_num_id, num_fmt, lvl_text,
                             font_name=None, indent_left=360, hanging=180):
        nsid_val = ''.join(random.choices('0123456789ABCDEF', k=8))
        tmpl_val = ''.join(random.choices('0123456789ABCDEF', k=8))

        abstractNum = OxmlElement('w:abstractNum')
        abstractNum.set(qn('w:abstractNumId'), str(abstract_num_id))

        nsid = OxmlElement('w:nsid');          nsid.set(qn('w:val'), nsid_val)
        ml   = OxmlElement('w:multiLevelType'); ml.set(qn('w:val'), 'singleLevel')
        tmpl = OxmlElement('w:tmpl');           tmpl.set(qn('w:val'), tmpl_val)
        abstractNum.extend([nsid, ml, tmpl])

        lvl    = OxmlElement('w:lvl');     lvl.set(qn('w:ilvl'), '0')
        start  = OxmlElement('w:start');   start.set(qn('w:val'), '1')
        nFmt   = OxmlElement('w:numFmt');  nFmt.set(qn('w:val'), num_fmt)
        lvlTxt = OxmlElement('w:lvlText'); lvlTxt.set(qn('w:val'), lvl_text)
        lvlJc  = OxmlElement('w:lvlJc');   lvlJc.set(qn('w:val'), 'left')

        pPr  = OxmlElement('w:pPr')
        tabs = OxmlElement('w:tabs')
        tab  = OxmlElement('w:tab')
        tab.set(qn('w:val'), 'num'); tab.set(qn('w:pos'), str(indent_left))
        tabs.append(tab); pPr.append(tabs)
        ind = OxmlElement('w:ind')
        ind.set(qn('w:left'), str(indent_left))
        ind.set(qn('w:hanging'), str(hanging))
        pPr.append(ind)
        lvl.extend([start, nFmt, lvlTxt, lvlJc, pPr])

        if font_name:
            rPr    = OxmlElement('w:rPr')
            rFonts = OxmlElement('w:rFonts')
            rFonts.set(qn('w:ascii'),  font_name)
            rFonts.set(qn('w:hAnsi'),  font_name)
            rFonts.set(qn('w:hint'),   'default')
            rPr.append(rFonts); lvl.append(rPr)

        abstractNum.append(lvl)
        return abstractNum

    def _apply_ooxml_numbering(self, paragraph, num_id: int, level: int = 0) -> None:
        pPr = paragraph._element.get_or_add_pPr()

        existing = pPr.find(qn('w:numPr'))
        if existing is not None:
            pPr.remove(existing)

        ind = pPr.find(qn('w:ind'))
        if ind is not None:
            pPr.remove(ind)

        numPr   = OxmlElement('w:numPr')
        ilvl    = OxmlElement('w:ilvl');  ilvl.set(qn('w:val'), str(level))
        numId_e = OxmlElement('w:numId'); numId_e.set(qn('w:val'), str(num_id))
        numPr.extend([ilvl, numId_e])
        pPr.insert(0, numPr)

        pStyle = pPr.find(qn('w:pStyle'))
        if pStyle is None:
            pStyle = OxmlElement('w:pStyle')
            pPr.insert(0, pStyle)
        pStyle.set(qn('w:val'), 'ListParagraph')

    # ──────────────────────────────────────────────────────────────────────────
    # Soft-break expansion
    # ──────────────────────────────────────────────────────────────────────────

    def _expand_soft_breaks(self, doc) -> None:
        W       = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        br_tag  = f"{{{W}}}br"
        t_tag   = f"{{{W}}}t"
        r_tag   = f"{{{W}}}r"
        p_tag   = f"{{{W}}}p"
        pPr_tag = f"{{{W}}}pPr"
        XML_NS  = "http://www.w3.org/XML/1998/namespace"

        body = doc.element.body
        for p_elem in list(body.iter(p_tag)):
            if not p_elem.findall(f".//{br_tag}"):
                continue
            pPr   = p_elem.find(pPr_tag)
            lines: List[List[tuple]] = [[]]
            for r_elem in p_elem.findall(r_tag):
                rPr = r_elem.find(f"{{{W}}}rPr")
                for child in list(r_elem):
                    if child.tag == t_tag:
                        lines[-1].append((rPr, child.text or ""))
                    elif child.tag == br_tag:
                        lines.append([])
            while lines and not any(t.strip() for _, t in lines[-1]):
                lines.pop()
            if len(lines) <= 1:
                continue
            parent = p_elem.getparent()
            pos    = list(parent).index(p_elem)
            new_paras = []
            for fragments in lines:
                line_text = "".join(t for _, t in fragments).strip()
                if not line_text:
                    continue
                new_p = OxmlElement("w:p")
                if pPr is not None:
                    new_p.append(deepcopy(pPr))
                new_r   = OxmlElement("w:r")
                rPr_src = next((rp for rp, _ in fragments if rp is not None), None)
                if rPr_src is not None:
                    new_r.append(deepcopy(rPr_src))
                new_t = OxmlElement("w:t")
                new_t.text = line_text
                new_t.set(f"{{{XML_NS}}}space", "preserve")
                new_r.append(new_t)
                new_p.append(new_r)
                new_paras.append(new_p)
            for offset, new_p in enumerate(new_paras):
                parent.insert(pos + offset, new_p)
            parent.remove(p_elem)

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _strip_plain_bullet_char(self, paragraph) -> None:
        for run in paragraph.runs:
            text = run.text
            if text and text[0] in _BULLET_CHARS:
                run.text = text.lstrip(''.join(_BULLET_CHARS)).lstrip()
                break

    def _parse_formatting_rules(self, rules: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        cfg = {"bullet_style": "filled_circle", "auto_apply_bullets": True}
        if not rules:
            return cfg
        if "list_bullet_style" in rules:
            raw = rules["list_bullet_style"].lower().replace(" ", "_")
            cfg["bullet_style"] = raw if raw in _STYLE_DEFS else "filled_circle"
        if "list_numbering_format" in rules:
            fmt = rules["list_numbering_format"]
            if fmt in _STYLE_DEFS:
                cfg["bullet_style"] = fmt
        if "auto_apply_bullets" in rules:
            cfg["auto_apply_bullets"] = bool(rules["auto_apply_bullets"])
        return cfg