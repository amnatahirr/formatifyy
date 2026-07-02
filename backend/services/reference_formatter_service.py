

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from docx import Document
from docx.enum.text import WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from docx.text.paragraph import Paragraph as DocxParagraph


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ReferenceRules:
    """
    Mirrors the reference_rules sub-object stored in the template.
    All fields have safe defaults so the service works even when the admin
    has not explicitly configured every field.
    """
    style: str = "APA"                # "APA" | "IEEE" | "MLA"
    font_name: str = "Times New Roman"
    font_size: float = 12.0
    line_spacing: float = 1.5         # multiplier  (1.0, 1.5, 2.0)
    hanging_indent: float = 0.5       # inches
    space_before: float = 0.0         # pt
    space_after: float = 6.0          # pt
    bold: bool = False
    italic: bool = False
    color: str = "#000000"            # hex
    sort_alphabetically: bool = True
    remove_duplicates: bool = True
    make_urls_clickable: bool = True
    mark_incomplete: bool = True
    numbering_style: str = "numeric" 

    @classmethod
    def from_dict(cls, d: dict) -> "ReferenceRules":
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)


@dataclass
class ParsedReference:
    raw_text: str
    authors: str = ""
    year: str = ""
    title: str = ""
    source: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    doi: str = ""
    url: str = ""
    is_complete: bool = True
    formatted_text: str = ""
    warnings: list = field(default_factory=list)


@dataclass
class FormatResult:
    success: bool
    references_found: int
    duplicates_removed: int
    incomplete_count: int
    urls_linked: int
    message: str
    details: list = field(default_factory=list)


_RE_YEAR = re.compile(
    r'\((\d{4}[a-z]?)(?:,\s*[A-Za-z]+(?:\s+\d{1,2})?)?\)\.?'
)

_RE_DOI         = re.compile(r'(?:https?://doi\.org/|doi:\s*)(\S+)', re.I)
_RE_URL         = re.compile(r'https?://[^\s,)>\]]+', re.I)
_RE_PAGES       = re.compile(r'(\d+)\s*[–\-]\s*(\d+)')
_RE_VOL_ISSUE   = re.compile(r'(\d+)\s*\((\d+)\)')
_RE_EXTRA_SPACE = re.compile(r'  +')

# BUG FIX: Strip leading numbered-list prefixes like "11 ", "22 ", "1. ", "[1] "
# These appear when Word auto-numbers reference lists or users manually prefix them
_RE_LEADING_NUM = re.compile(r'^\s*(?:\[?\d+\]?\.?\s+)')

# Headings that start a reference section (lower-cased, punctuation stripped)
_REF_HEADINGS = {
    "references", "bibliography", "works cited",
    "reference list", "sources", "literature cited",
    "list of references", "cited works", "citations",
}

# Indicators of an incomplete reference
_INCOMPLETE_SIGNALS = [
    r'\bn\.d\.',
    r'\bno date\b',
    r'\bn\.p\.',
    r'_+',
    r'\[author\]',
    r'\[title\]',
    r'\[journal\]',
    r'\[year\]',
    r'^\s*-\s*$',
]
_RE_INCOMPLETE = re.compile('|'.join(_INCOMPLETE_SIGNALS), re.I)



class ReferenceFormatterService:
    def format_references(
        self,
        docx_path: str,
        reference_rules: "dict | ReferenceRules",
    ) -> FormatResult:
       
        if isinstance(reference_rules, dict):
            rules = ReferenceRules.from_dict(reference_rules)
        else:
            rules = reference_rules

        doc = Document(docx_path)

        # 1. Locate the reference section heading
        heading_idx = self._find_heading_index(doc)
        if heading_idx is None:
            return FormatResult(
                success=False,
                references_found=0,
                duplicates_removed=0,
                incomplete_count=0,
                urls_linked=0,
                message="No References / Bibliography section found in document.",
            )

        # 2. Collect all reference paragraphs after the heading
        ref_paragraphs = self._collect_ref_paragraphs(doc, heading_idx)
        if not ref_paragraphs:
            return FormatResult(
                success=False,
                references_found=0,
                duplicates_removed=0,
                incomplete_count=0,
                urls_linked=0,
                message="References heading found but no reference paragraphs detected.",
            )

        # 3. Extract and clean raw text from paragraphs
        raw_texts = self._extract_and_clean([p.text for p in ref_paragraphs])

        # 4. Remove exact duplicates
        original_count = len(raw_texts)
        if rules.remove_duplicates:
            raw_texts = self._remove_duplicates(raw_texts)
        duplicates_removed = original_count - len(raw_texts)

        # 5. Parse each reference
        parsed = [self._parse_reference(t, rules.style) for t in raw_texts]

        # 6. Sort alphabetically (by first author last name)
        if rules.sort_alphabetically:
            parsed = self._sort_references(parsed)

        # 7. Format text according to citation style
        for ref in parsed:
            ref.formatted_text = self._format_citation(ref, rules.style)

        # 8. Mark incomplete references
        incomplete_count = 0
        if rules.mark_incomplete:
            for ref in parsed:
                if not ref.is_complete or _RE_INCOMPLETE.search(ref.raw_text):
                    ref.is_complete = False
                    if "[MANUAL CHECK REQUIRED]" not in ref.formatted_text:
                        ref.formatted_text += "  [MANUAL CHECK REQUIRED]"
                    incomplete_count += 1

        # 9. Rewrite the reference paragraphs in the document
        urls_linked = self._rewrite_paragraphs(doc, ref_paragraphs, parsed, rules)

        doc.save(docx_path)
        print(f"[ReferenceFormatter] Saved -> {docx_path}")

        return FormatResult(
            success=True,
            references_found=len(parsed),
            duplicates_removed=duplicates_removed,
            incomplete_count=incomplete_count,
            urls_linked=urls_linked,
            message=(
                f"Formatted {len(parsed)} references "
                f"({duplicates_removed} duplicates removed, "
                f"{incomplete_count} marked for manual check)."
            ),
            details=[r.formatted_text for r in parsed],
        )

    # ── Step 1 — find heading ─────────────────────────────────────────────────

    def _find_heading_index(self, doc: Document) -> Optional[int]:
        for i, para in enumerate(doc.paragraphs):
            raw_text = para.text.strip()
            # Normalise: lowercase + strip trailing punctuation
            norm_text = raw_text.lower().rstrip(":.,;! ")
            style = (para.style.name or "").lower()
            is_heading_style = "heading" in style

            if norm_text in _REF_HEADINGS:
                if is_heading_style:
                    print(f"[ReferenceFormatter] Found heading at para {i}: "
                          f"{raw_text!r} style={para.style.name!r}")
                    return i
                # Accept bold paragraphs used as manual headings
                if para.runs and all(r.bold for r in para.runs):
                    print(f"[ReferenceFormatter] Found bold heading at para {i}: "
                          f"{raw_text!r}")
                    return i
                if para.runs and any(r.bold for r in para.runs):
                    print(f"[ReferenceFormatter] Found partially-bold heading "
                          f"at para {i}: {raw_text!r}")
                    return i
                # Plain paragraph — accept anyway (catches plain-text templates)
                print(f"[ReferenceFormatter] Found plain heading at para {i}: "
                      f"{raw_text!r}")
                return i

        print("[ReferenceFormatter] No reference heading found.")
        return None

    # ── Step 2 — collect paragraphs ───────────────────────────────────────────

    def _collect_ref_paragraphs(self, doc: Document, heading_idx: int) -> list:
        paras = []
        for para in doc.paragraphs[heading_idx + 1:]:
            txt = para.text.strip()
            style = (para.style.name or "").lower()
            norm = txt.lower().rstrip(":.,;! ")

            # Stop at the next major heading that is NOT a references heading
            if "heading 1" in style and txt and norm not in _REF_HEADINGS:
                break
            if "heading 2" in style and txt and norm not in _REF_HEADINGS:
                break

            # Skip truly empty paragraphs only
            if not txt:
                continue

            paras.append(para)
        return paras

    # ── Step 3 — extract and clean text ──────────────────────────────────────

    def _extract_and_clean(self, texts: list[str]) -> list[str]:
      
        cleaned: list[str] = []
        for txt in texts:
            # Unicode normalisation — converts NBSP to space, fixes dashes
            txt = unicodedata.normalize("NFKC", txt)
            # Strip leading numbering e.g. "11 Xu" -> "Xu", "1. Smith" -> "Smith"
            txt = _RE_LEADING_NUM.sub("", txt)
            # Collapse multiple spaces
            txt = _RE_EXTRA_SPACE.sub(" ", txt).strip()
            if not txt:
                continue
            cleaned.append(txt)

        # Merge continuation lines. A continuation does NOT start with an
        # author-like pattern (Lastname, F.) or a bracketed number [N].
        merged: list[str] = []
        for txt in cleaned:
            is_new_ref = self._looks_like_new_reference(txt)
            if merged and not is_new_ref:
                merged[-1] = merged[-1].rstrip() + " " + txt
            else:
                merged.append(txt)
        return merged

    def _looks_like_new_reference(self, txt: str) -> bool:
      
        if re.match(r'^[A-Z][a-z]+,\s+[A-Z]', txt):
            return True
        # IEEE bracketed: [1], [12]
        if re.match(r'^\[\d+\]', txt):
            return True
        # Org name or any line starting with a capital (be inclusive)
        if re.match(r'^[A-Z]', txt):
            return True
        return False

    # ── Step 4 — remove duplicates ────────────────────────────────────────────

    def _remove_duplicates(self, texts: list[str]) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for t in texts:
            key = re.sub(r'\s+', ' ', t.lower().strip())
            if key not in seen:
                seen.add(key)
                unique.append(t)
        return unique

    # ── Step 5 — parse reference ──────────────────────────────────────────────

    def _parse_reference(self, text: str, style: str) -> ParsedReference:
        ref = ParsedReference(raw_text=text)

        # Extract DOI first (so we don't confuse it with a plain URL)
        doi_match = _RE_DOI.search(text)
        if doi_match:
            ref.doi = doi_match.group(0).strip()

        # Extract plain URL (only if no DOI found)
        url_match = _RE_URL.search(text)
        if url_match and not ref.doi:
            ref.url = url_match.group(0).strip()

        # BUG FIX: Use the extended year regex that handles "(2021, September)"
        year_match = _RE_YEAR.search(text)
        if year_match:
            ref.year = year_match.group(1)   # only the 4-digit year (+ optional letter)

        if year_match:
            before_year = text[:year_match.start()].strip().rstrip(",")
            # Strip trailing period from authors section — will be re-added during formatting
            before_year = before_year.rstrip(".")
            after_year  = text[year_match.end():].strip()
            ref.authors = before_year

            # Remove DOI / URL from the after_year chunk before splitting into title/source
            after_clean = after_year
            if ref.doi:
                after_clean = after_clean.replace(ref.doi, "").strip()
            elif ref.url:
                after_clean = after_clean.replace(ref.url, "").strip()

            sentences = re.split(r'(?<=[.!?"])\s+', after_clean)
            raw_title = sentences[0].strip().rstrip(".") if sentences else ""
            # Strip surrounding quotes from title (e.g. "Title." -> Title)
            raw_title = raw_title.strip('"').strip("'").strip()
            ref.title  = raw_title
            ref.source = " ".join(sentences[1:]).strip() if len(sentences) > 1 else ""
        else:
            # No parenthesised year — could be a website / org with no date.
            # Try to extract author + title from "Org Name. "Title." URL" pattern.
            no_date_match = re.match(
                r'^(.+?)\.\s+"([^"]+)"', text
            )
            if no_date_match:
                ref.authors = no_date_match.group(1).strip()
                ref.title   = no_date_match.group(2).strip()
                # year stays "" → will produce (n.d.) in APA format which is correct
                ref.is_complete = False   # still flag for manual check (no year)
            else:
                # IEEE / numbered — best-effort
                ref.authors = text
                ref.is_complete = False

        # Vol/Issue
        vi_match = _RE_VOL_ISSUE.search(ref.source)
        if vi_match:
            ref.volume = vi_match.group(1)
            ref.issue  = vi_match.group(2)

        # Pages
        pg_match = _RE_PAGES.search(ref.source)
        if pg_match:
            ref.pages = f"{pg_match.group(1)}-{pg_match.group(2)}"

        # Completeness check
        if not all([ref.authors, ref.year, ref.title]):
            ref.is_complete = False
            ref.warnings.append("Missing one or more required fields (author/year/title).")

        return ref

    # ── Step 6 — sort ─────────────────────────────────────────────────────────

    def _sort_references(self, refs: list[ParsedReference]) -> list[ParsedReference]:
        def sort_key(r: ParsedReference) -> str:
            first_author = (
                r.authors.split(",")[0].strip().lower()
                if r.authors else r.raw_text[:20].lower()
            )
            return first_author
        return sorted(refs, key=sort_key)

    # ── Step 7 — format citation text ─────────────────────────────────────────

    def _format_citation(self, ref: ParsedReference, style: str) -> str:
        style = style.upper()
        if style == "APA":
            return self._format_apa(ref)
        elif style == "IEEE":
            return self._format_ieee(ref)
        elif style == "MLA":
            return self._format_mla(ref)
        return self._format_apa(ref)

    def _format_apa(self, ref: ParsedReference) -> str:
       
        parts: list[str] = []

        # Authors — ensure trailing period
        authors = self._normalise_authors_apa(ref.authors)
        if authors:
            if not authors.endswith("."):
                authors += "."
            parts.append(authors)

        # Year — BUG FIX: only add (n.d.) when year is genuinely absent
        if ref.year:
            parts.append(f"({ref.year}).")
        else:
            parts.append("(n.d.).")

        # Title in smart sentence case (preserves proper nouns / acronyms)
        if ref.title:
            title = self._sentence_case_smart(ref.title)
            if not title.endswith("."):
                title += "."
            parts.append(title)

        # Source (journal/book) — keep original capitalisation, just clean whitespace
        if ref.source:
            source_clean = self._clean_source(ref.source)
            if source_clean:
                parts.append(source_clean)

        # DOI / URL
        if ref.doi:
            parts.append(ref.doi)
        elif ref.url:
            parts.append(ref.url)

        return " ".join(parts)

    def _format_ieee(self, ref: ParsedReference) -> str:
        """
        IEEE:
        A. Author, "Title of paper," Journal Name, vol. X, no. Y, pp. Z-W, Year.
        """
        parts: list[str] = []

        authors = self._normalise_authors_ieee(ref.authors)
        if authors:
            parts.append(authors + ",")

        if ref.title:
            parts.append(f'"{ref.title},"')

        if ref.source:
            parts.append(self._clean_source(ref.source) + ",")

        if ref.volume:
            parts.append(f"vol. {ref.volume},")
        if ref.issue:
            parts.append(f"no. {ref.issue},")
        if ref.pages:
            parts.append(f"pp. {ref.pages},")
        if ref.year:
            parts.append(ref.year + ".")

        if ref.doi:
            parts.append(ref.doi)

        return " ".join(parts)

    def _format_mla(self, ref: ParsedReference) -> str:
        """
        MLA 9th edition:
        Last, First. "Title of Source." Container, Publisher, Date, Location.
        """
        parts: list[str] = []

        authors = self._normalise_authors_mla(ref.authors)
        if authors:
            parts.append(authors + ".")

        if ref.title:
            parts.append(f'"{self._title_case(ref.title)}."')

        if ref.source:
            parts.append(self._title_case(self._clean_source(ref.source)) + ",")

        if ref.year:
            parts.append(ref.year + ".")

        if ref.doi:
            parts.append(ref.doi)
        elif ref.url:
            parts.append(ref.url)

        return " ".join(parts)

    # ── Step 8 — rewrite Word paragraphs ─────────────────────────────────────

    def _rewrite_paragraphs(
        self,
        doc: Document,
        ref_paragraphs: list,
        parsed: list[ParsedReference],
        rules: ReferenceRules,
    ) -> int:
        """
        Clears and rewrites each reference paragraph with proper formatting.
        Adds new paragraphs if *parsed* has more entries than *ref_paragraphs*.
        Returns the number of URLs/DOIs turned into hyperlinks.
        """
        urls_linked = 0
        existing = list(ref_paragraphs)
        color = self._hex_to_rgb(rules.color)

        for i, ref in enumerate(parsed):
            if i < len(existing):
                para = existing[i]
                self._clear_paragraph(para)
            else:
                last_para = existing[-1] if existing else doc.paragraphs[-1]
                para = self._insert_paragraph_after(doc, last_para)
                existing.append(para)

            # Apply paragraph formatting
            pf = para.paragraph_format
            pf.left_indent        = Inches(rules.hanging_indent)
            pf.first_line_indent  = Inches(-rules.hanging_indent)
            pf.space_before       = Pt(rules.space_before)
            pf.space_after        = Pt(rules.space_after)
            pf.line_spacing_rule  = WD_LINE_SPACING.MULTIPLE
            pf.line_spacing       = rules.line_spacing

            if rules.numbering_style == "bracket":
                prefix = f"[{i + 1}] "
            elif rules.numbering_style == "numeric":
                prefix = f"{i + 1}.\t"
            else:
                prefix = ""
                
            text = ref.formatted_text
           
            # Detect URL/DOI for hyperlinking
            doi_match = _RE_DOI.search(text)
            url_match = _RE_URL.search(text)
            link_match = doi_match or url_match

            if rules.make_urls_clickable and link_match:
                link_text = link_match.group(0)
                before = text[:link_match.start()]
                after  = text[link_match.end():]
                
                run = para.add_run( prefix + before)
                self._style_run(run, rules, color)

                

                self._add_hyperlink(para, link_text, link_text)
                urls_linked += 1

                if after:
                    run = para.add_run(after)
                    self._style_run(run, rules, color)
            else:
                run = para.add_run( prefix+text)
                self._style_run(run, rules, color)

        # Remove leftover original paragraphs beyond the parsed count
        for extra_para in existing[len(parsed):]:
            self._delete_paragraph(extra_para)

        return urls_linked

    # ── Helpers — author normalisation ────────────────────────────────────────

    def _normalise_authors_apa(self, raw: str) -> str:
        """
        Ensure APA author format: Last, F. M., & Last, F. M.
        Best-effort: if already formatted, clean up; otherwise keep as-is.
        """
        if not raw:
            return ""
        raw = raw.strip().rstrip(",.")
        raw = raw.replace(";", ",")
        return raw

    def _normalise_authors_ieee(self, raw: str) -> str:
        """Convert 'Smith, J. A.' -> 'J. A. Smith' for IEEE style."""
        if not raw:
            return ""
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        result = []
        i = 0
        while i < len(parts):
            last = parts[i]
            if i + 1 < len(parts) and re.match(r'^[A-Z]\.', parts[i + 1]):
                initials = parts[i + 1]
                result.append(f"{initials} {last}")
                i += 2
            else:
                result.append(last)
                i += 1
        return ", ".join(result)

    def _normalise_authors_mla(self, raw: str) -> str:
        if not raw:
            return ""
        return raw.strip().rstrip(",.")

    # ── Helpers — text case ───────────────────────────────────────────────────

    def _sentence_case_smart(self, text: str) -> str:
        """
        Sentence case that PRESERVES:
        - ALL-CAPS tokens of 2+ chars (acronyms: NLP, AI, HTTP)
        - Tokens with internal capitals (proper nouns: DocBank, LayoutLM, GitHub)
        - Tokens after a colon ':' (subtitle start — capitalised in APA)

        BUG FIX: Previous _sentence_case() called text[1:].lower() which
        destroyed acronyms ("NLP" -> "nLP") and proper nouns ("LayoutLM" -> "Layoutlm").
        """
        if not text:
            return text
        text = text.strip()
        words = text.split()
        result = []
        capitalise_next = True  # first word always capitalised

        for w in words:
            ends_with_colon = w.endswith(":")

            if capitalise_next:
                result.append(w[0].upper() + w[1:])
                capitalise_next = False
            elif self._is_preserved_token(w):
                result.append(w)          # keep as-is
            else:
                result.append(w.lower())

            if ends_with_colon:
                capitalise_next = True  # capitalise word after colon (APA subtitle)

        return " ".join(result)

    def _is_preserved_token(self, token: str) -> bool:
        """Return True if *token* should NOT be lower-cased."""
        bare = token.rstrip(".,;:!?()")
        if not bare:
            return False
        # All-caps acronym of 2+ chars: NLP, AI, ACM, DOI, IEEE
        if bare.isupper() and len(bare) >= 2:
            return True
        # Mixed internal caps — proper nouns: DocBank, LayoutLM, GitHub, KDD
        if bare != bare.lower() and bare != bare.upper() and not bare.istitle():
            return True
        # Single capital letter (initial): always preserve
        if len(bare) == 1 and bare.isupper():
            return True
        return False

    def _title_case(self, text: str) -> str:
        """Proper title case for MLA / journal names."""
        if not text:
            return text
        SMALL = {"a", "an", "the", "and", "but", "or", "for", "nor",
                  "on", "at", "to", "by", "in", "of", "up", "as"}
        words = text.split()
        result = []
        for j, w in enumerate(words):
            if j == 0 or w.lower() not in SMALL:
                result.append(w.capitalize())
            else:
                result.append(w.lower())
        return " ".join(result)

    def _clean_source(self, source: str) -> str:
        source = source.strip().rstrip(".,")
        source = _RE_EXTRA_SPACE.sub(" ", source)
        return source

    def _hex_to_rgb(self, hex_color: str) -> RGBColor:
        hex_color = hex_color.lstrip("#")
        if len(hex_color) != 6:
            return RGBColor(0, 0, 0)
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return RGBColor(r, g, b)

    # ── Helpers — Word XML manipulation ──────────────────────────────────────

    def _style_run(self, run, rules: ReferenceRules, color: RGBColor):
        run.font.name      = rules.font_name
        run.font.size      = Pt(rules.font_size)
        run.font.bold      = rules.bold
        run.font.italic    = rules.italic
        run.font.color.rgb = color

    def _clear_paragraph(self, para):
        """Remove all runs and hyperlinks from a paragraph element."""
        p = para._element
        for r in p.findall(qn("w:r")):
            p.remove(r)
        for h in p.findall(qn("w:hyperlink")):
            p.remove(h)

    def _delete_paragraph(self, para):
        p = para._element
        parent = p.getparent()
        if parent is not None:
            parent.remove(p)

    def _insert_paragraph_after(self, doc: Document, ref_para) -> DocxParagraph:
        """Insert a new blank paragraph immediately after *ref_para*."""
        new_p = OxmlElement("w:p")
        ref_para._element.addnext(new_p)
        return DocxParagraph(new_p, doc._element.body)

    def _add_hyperlink(self, para, text: str, url: str):
        """
        Insert a clickable hyperlink run into *para*.
        Adds the relationship to the document part and builds the
        w:hyperlink XML element manually (python-docx has no native helper).
        """
        part = para.part
        r_id = part.relate_to(
            url,
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
            is_external=True,
        )

        hyperlink = OxmlElement("w:hyperlink")
        hyperlink.set(qn("r:id"), r_id)

        new_run = OxmlElement("w:r")

        rPr = OxmlElement("w:rPr")
        rStyle = OxmlElement("w:rStyle")
        rStyle.set(qn("w:val"), "Hyperlink")
        rPr.append(rStyle)
        new_run.append(rPr)

        t = OxmlElement("w:t")
        t.text = text
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        new_run.append(t)

        hyperlink.append(new_run)
        para._element.append(hyperlink)