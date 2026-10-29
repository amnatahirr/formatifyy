"""
review_format.py — Word formatting + layout helpers for supervisor Document Review.

* FormatResolver
    Resolves the *effective* formatting of a paragraph / run the way Word does:
    direct formatting -> character style -> paragraph style chain -> document
    defaults (incl. theme fonts and theme colours). The review screen can then
    show the real font, size, bold/italic, colour, alignment and indent instead
    of guessing from the style name.

* apply_real_toc_pages
    A TOC written by a generator usually carries *stale cached* page numbers
    (Word only refreshes them when the field is updated, which is why Word shows
    7, 8, 8, 9 while the file text still says 1, 2, 2, 3). When that is detected
    the document is laid out with LibreOffice (if installed) and the real page of
    every heading is written back into the TOC entries.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import signal
import subprocess
import tempfile
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from docx.oxml.ns import qn

logger = logging.getLogger(__name__)

# auto   -> recompute only when the TOC looks stale (updateFields / dirty fields)
# always -> always lay the document out and use those page numbers
# never  -> keep whatever page numbers are cached in the file
TOC_PAGE_MODE = os.getenv("REVIEW_TOC_PAGE_MODE", "auto").strip().lower()
LAYOUT_TIMEOUT_S = int(os.getenv("REVIEW_LAYOUT_TIMEOUT", "90"))

_HEX6 = re.compile(r"^[0-9A-Fa-f]{6}$")
_A_NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
_THEME_ALIAS = {
    "text1": "dk1",
    "dark1": "dk1",
    "background1": "lt1",
    "light1": "lt1",
    "text2": "dk2",
    "dark2": "dk2",
    "background2": "lt2",
    "light2": "lt2",
}
_HIGHLIGHTS = {
    "yellow": "FFFF00",
    "green": "00FF00",
    "cyan": "00FFFF",
    "magenta": "FF00FF",
    "blue": "0000FF",
    "red": "FF0000",
    "darkBlue": "000080",
    "darkCyan": "008080",
    "darkGreen": "008000",
    "darkMagenta": "800080",
    "darkRed": "800000",
    "darkYellow": "808000",
    "darkGray": "808080",
    "lightGray": "C0C0C0",
    "black": "000000",
    "white": "FFFFFF",
}
_JC = {
    "left": "left",
    "start": "left",
    "center": "center",
    "right": "right",
    "end": "right",
    "both": "justify",
    "distribute": "justify",
}


# ─────────────────────────────────────────────────────────────────────────────
# Text helpers (shared with review_blocks)
# ─────────────────────────────────────────────────────────────────────────────

def in_textbox(node, root) -> bool:
    """True when [node] sits inside a text box (those paragraphs are duplicated
    by Word's fallback markup, so they are skipped)."""
    parent = node.getparent()
    while parent is not None and parent is not root:
        if parent.tag == qn("w:txbxContent"):
            return True
        parent = parent.getparent()
    return False


def run_text(run) -> str:
    """Text of one w:r. Tabs stay "\\t" so "Introduction\\t1" can be split."""
    out: List[str] = []
    for node in run:
        tag = node.tag
        if tag == qn("w:t"):
            out.append(node.text or "")
        elif tag == qn("w:tab"):
            out.append("\t")
        elif tag in (qn("w:br"), qn("w:cr")):
            if node.get(qn("w:type")) != "page":
                out.append("\n")
        elif tag == qn("w:noBreakHyphen"):
            out.append("-")
    return "".join(out)


# ─────────────────────────────────────────────────────────────────────────────
# Effective formatting
# ─────────────────────────────────────────────────────────────────────────────

def _on(el) -> bool:
    return (el.get(qn("w:val")) or "true").lower() not in ("0", "false", "off", "none")


def _flag(rpr, tag: str) -> Optional[bool]:
    el = rpr.find(qn(tag))
    return None if el is None else _on(el)


def _g_size(rpr) -> Optional[float]:
    el = rpr.find(qn("w:sz"))
    if el is None:
        return None
    try:
        return int(el.get(qn("w:val"))) / 2.0
    except (TypeError, ValueError):
        return None


def _g_underline(rpr) -> Optional[bool]:
    el = rpr.find(qn("w:u"))
    if el is None:
        return None
    return (el.get(qn("w:val")) or "single").lower() != "none"


def _g_highlight(rpr) -> Optional[str]:
    el = rpr.find(qn("w:highlight"))
    if el is None:
        return None
    return _HIGHLIGHTS.get(el.get(qn("w:val")) or "", "")


def _apply_tint_shade(hex6: str, tint: Optional[str], shade: Optional[str]) -> str:
    try:
        r, g, b = (int(hex6[i : i + 2], 16) for i in (0, 2, 4))
        if shade:
            f = int(shade, 16) / 255.0
            r, g, b = (int(c * f) for c in (r, g, b))
        if tint:
            f = int(tint, 16) / 255.0
            r, g, b = (int(c * f + 255 * (1 - f)) for c in (r, g, b))
        return f"{r:02X}{g:02X}{b:02X}"
    except (TypeError, ValueError):
        return hex6.upper()


def _read_theme(doc) -> Tuple[Dict[str, str], Dict[str, str]]:
    """(fonts{major,minor}, colours{dk1,lt1,accent1,...}) from the theme part."""
    fonts: Dict[str, str] = {}
    colors: Dict[str, str] = {}
    try:
        from lxml import etree

        for part in doc.part.package.iter_parts():
            if not str(part.partname).endswith("/theme/theme1.xml"):
                continue
            root = etree.fromstring(part.blob)
            for key, tag in (("major", "majorFont"), ("minor", "minorFont")):
                el = root.find(".//a:%s/a:latin" % tag, _A_NS)
                if el is not None and el.get("typeface"):
                    fonts[key] = el.get("typeface")
            scheme = root.find(".//a:clrScheme", _A_NS)
            if scheme is not None:
                for child in scheme:
                    name = etree.QName(child).localname
                    if not len(child):
                        continue
                    clr = child[0]
                    local = etree.QName(clr).localname
                    val = clr.get("val") if local == "srgbClr" else clr.get("lastClr")
                    if val:
                        colors[name] = val.upper()
            break
    except Exception:  # theme is optional
        logger.debug("review_format: theme not readable", exc_info=True)
    return fonts, colors


_FMT_KEYS = ("font_name", "font_size", "bold", "italic", "underline", "strike", "color", "highlight")
# internal key -> key sent to the app inside a run
_RUN_OUT = {
    "font_name": "font_name",
    "font_size": "font_size",
    "bold": "bold",
    "italic": "italic",
    "underline": "underline",
    "strike": "strike",
    "color": "color_hex",
    "highlight": "highlight_hex",
}


def _fmt_key(fmt: Dict[str, Any]) -> tuple:
    return tuple(fmt.get(k) for k in _FMT_KEYS)


class FormatResolver:
    """Effective paragraph / run formatting for one python-docx Document."""

    def __init__(self, doc) -> None:
        self.styles: Dict[str, Any] = {}
        self.default_paragraph_style: Optional[str] = None
        root = doc.styles.element
        for style in root.iterchildren(qn("w:style")):
            sid = style.get(qn("w:styleId"))
            if sid:
                self.styles[sid] = style
            if style.get(qn("w:type")) == "paragraph" and (
                style.get(qn("w:default")) or ""
            ).lower() in ("1", "true"):
                self.default_paragraph_style = sid
        self.default_rpr = None
        self.default_ppr = None
        defaults = root.find(qn("w:docDefaults"))
        if defaults is not None:
            r_def = defaults.find(qn("w:rPrDefault"))
            p_def = defaults.find(qn("w:pPrDefault"))
            self.default_rpr = r_def.find(qn("w:rPr")) if r_def is not None else None
            self.default_ppr = p_def.find(qn("w:pPr")) if p_def is not None else None
        self.theme_fonts, self.theme_colors = _read_theme(doc)
        self._chains: Dict[Optional[str], List[Any]] = {}

    # -- style chains -------------------------------------------------------
    def _chain(self, style_id: Optional[str]) -> List[Any]:
        if style_id in self._chains:
            return self._chains[style_id]
        out: List[Any] = []
        seen = set()
        sid = style_id
        while sid and sid in self.styles and sid not in seen:
            seen.add(sid)
            el = self.styles[sid]
            out.append(el)
            based = el.find(qn("w:basedOn"))
            sid = based.get(qn("w:val")) if based is not None else None
        self._chains[style_id] = out
        return out

    def _paragraph_style_id(self, p_el) -> Optional[str]:
        p_pr = p_el.find(qn("w:pPr"))
        if p_pr is not None:
            p_style = p_pr.find(qn("w:pStyle"))
            if p_style is not None and p_style.get(qn("w:val")):
                return p_style.get(qn("w:val"))
        return self.default_paragraph_style

    def _rpr_sources(self, p_el, run_el, use_char_style: bool) -> List[Any]:
        """rPr elements, most specific first."""
        out: List[Any] = []
        if run_el is not None:
            r_pr = run_el.find(qn("w:rPr"))
            if r_pr is not None:
                out.append(r_pr)
                if use_char_style:
                    r_style = r_pr.find(qn("w:rStyle"))
                    if r_style is not None:
                        for st in self._chain(r_style.get(qn("w:val"))):
                            x = st.find(qn("w:rPr"))
                            if x is not None:
                                out.append(x)
        for st in self._chain(self._paragraph_style_id(p_el)):
            x = st.find(qn("w:rPr"))
            if x is not None:
                out.append(x)
        if self.default_rpr is not None:
            out.append(self.default_rpr)
        return out

    def _ppr_sources(self, p_el) -> List[Any]:
        out: List[Any] = []
        p_pr = p_el.find(qn("w:pPr"))
        if p_pr is not None:
            out.append(p_pr)
        for st in self._chain(self._paragraph_style_id(p_el)):
            x = st.find(qn("w:pPr"))
            if x is not None:
                out.append(x)
        if self.default_ppr is not None:
            out.append(self.default_ppr)
        return out

    @staticmethod
    def _first(sources: Sequence[Any], getter: Callable[[Any], Any]) -> Any:
        for src in sources:
            value = getter(src)
            if value is not None:
                return value
        return None

    # -- property getters needing theme data --------------------------------
    def _g_font(self, rpr) -> Optional[str]:
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is None:
            return None
        theme = fonts.get(qn("w:asciiTheme")) or fonts.get(qn("w:hAnsiTheme"))
        if theme:
            name = self.theme_fonts.get("major" if theme.lower().startswith("major") else "minor")
            if name:
                return name
        return fonts.get(qn("w:ascii")) or fonts.get(qn("w:hAnsi"))

    def _g_color(self, rpr) -> Optional[str]:
        el = rpr.find(qn("w:color"))
        if el is None:
            return None
        theme = el.get(qn("w:themeColor"))
        val = el.get(qn("w:val"))
        if theme:
            base = self.theme_colors.get(_THEME_ALIAS.get(theme, theme))
            if base:
                return _apply_tint_shade(base, el.get(qn("w:themeTint")), el.get(qn("w:themeShade")))
        if val and _HEX6.match(val):
            return val.upper()
        if (val or "").lower() == "auto":
            return "000000"
        return None

    # -- public API ----------------------------------------------------------
    def run_format(self, p_el, run_el, use_char_style: bool = True) -> Dict[str, Any]:
        src = self._rpr_sources(p_el, run_el, use_char_style)
        size = self._first(src, _g_size)
        return {
            "font_name": self._first(src, self._g_font),
            "font_size": size if size is not None else 10.0,  # Word's default is 10 pt
            "bold": bool(self._first(src, lambda r: _flag(r, "w:b"))),
            "italic": bool(self._first(src, lambda r: _flag(r, "w:i"))),
            "underline": bool(self._first(src, _g_underline)),
            "strike": bool(self._first(src, lambda r: _flag(r, "w:strike"))),
            "color": self._first(src, self._g_color) or "000000",
            "highlight": self._first(src, _g_highlight) or "",
        }

    @staticmethod
    def _props(fmt: Dict[str, Any]) -> Dict[str, Any]:
        props: Dict[str, Any] = {
            "font_size": fmt["font_size"],
            "is_bold": fmt["bold"],
            "is_italic": fmt["italic"],
            "is_underline": fmt["underline"],
            "color_hex": fmt["color"],
        }
        if fmt["font_name"]:
            props["font_name"] = fmt["font_name"]
        return props

    def paragraph_format(
        self, p_el, style_only: bool = False
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        (paragraph-level props, runs).
        Props use the formatting that covers most of the text; `runs` is only
        filled when the paragraph really mixes formats, and then only carries the
        properties that differ from the paragraph-level ones.
        `style_only=True` ignores direct/character formatting (used for TOC
        lines: Word shows them in the TOC style, not as blue hyperlinks).
        """
        if style_only:
            return self._props(self.run_format(p_el, None)), []

        pieces: List[Tuple[str, Dict[str, Any]]] = []
        for run in p_el.iter(qn("w:r")):
            if in_textbox(run, p_el):
                continue
            text = run_text(run)
            if text:
                pieces.append((text, self.run_format(p_el, run)))
        if not pieces:
            return self._props(self.run_format(p_el, None)), []

        weights: Dict[tuple, int] = {}
        for text, fmt in pieces:
            key = _fmt_key(fmt)
            weights[key] = weights.get(key, 0) + len(text.strip())
        dominant_key = max(weights, key=lambda k: weights[k])
        dominant = next(f for _, f in pieces if _fmt_key(f) == dominant_key)
        props = self._props(dominant)

        mixed = any(_fmt_key(f) != dominant_key and t.strip() for t, f in pieces)
        runs: List[Dict[str, Any]] = []
        if mixed:
            merged: List[List[Any]] = []
            for text, fmt in pieces:
                if merged and _fmt_key(merged[-1][1]) == _fmt_key(fmt):
                    merged[-1][0] += text
                else:
                    merged.append([text, fmt])
            for text, fmt in merged:
                run: Dict[str, Any] = {"text": text}
                for key, out_key in _RUN_OUT.items():
                    value = fmt[key]
                    if value != dominant[key] and value is not None and value != "":
                        run[out_key] = value
                runs.append(run)
        return props, runs

    def alignment(self, p_el) -> Optional[str]:
        def getter(ppr):
            jc = ppr.find(qn("w:jc"))
            return jc.get(qn("w:val")) if jc is not None else None

        return _JC.get((self._first(self._ppr_sources(p_el), getter) or "").lower())

    def indent_level(self, p_el) -> Optional[float]:
        """Left indent as 'levels' of 0.29 in (the review screen uses 28 px)."""

        def getter(ppr):
            ind = ppr.find(qn("w:ind"))
            if ind is None:
                return None
            raw = ind.get(qn("w:left")) or ind.get(qn("w:start"))
            try:
                return int(raw) if raw is not None else None
            except ValueError:
                return None

        left = self._first(self._ppr_sources(p_el), getter)
        return round(left / 420.0, 2) if left and left > 0 else None


# ─────────────────────────────────────────────────────────────────────────────
# Real TOC page numbers (LibreOffice layout)
# ─────────────────────────────────────────────────────────────────────────────

_LEADER_TAIL = re.compile(r"(?:\.{3,}|(?:\.\s){3,})\s*\d+\s*$")
_TOC_SPLIT = re.compile(
    r"^(.*?)(?:\t+|\s*\.{2,}\s*|\s{3,})(\d+|[ivxlcdm]+)\s*$", re.IGNORECASE
)
_LEADING_NUMBER = re.compile(r"^\s*(?:chapter\s+)?\d+(?:\.\d+)*\.?\s+", re.IGNORECASE)


def toc_pages_look_stale(doc) -> bool:
    """True when Word is told to refresh fields on open, i.e. the cached TOC page
    numbers in the file are not the ones Word will display."""
    try:
        update = doc.settings.element.find(qn("w:updateFields"))
        if update is not None and _on(update):
            return True
    except Exception:
        pass
    body = doc.element.body
    for tag in ("w:fldChar", "w:fldSimple"):
        for el in body.iter(qn(tag)):
            if (el.get(qn("w:dirty")) or "").lower() in ("1", "true", "on"):
                return True
    return False


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace(" ", " ").replace("\t", " ")).strip().lower()


def _strip_number(text: str) -> str:
    return _LEADING_NUMBER.sub("", text, count=1).strip()


def _split_toc_text(text: str) -> Tuple[str, str]:
    clean = (text or "").replace("\r", "").strip()
    m = _TOC_SPLIT.match(clean)
    if m:
        return m.group(1).strip(), m.group(2)
    return clean, ""


def _docx_to_pdf(file_path: str, out_dir: str) -> Optional[str]:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    profile = os.path.join(out_dir, "lo_profile")
    cmd = [
        soffice,
        f"-env:UserInstallation=file://{profile}",
        "--headless",
        "--norestore",
        "--convert-to",
        "pdf",
        "--outdir",
        out_dir,
        file_path,
    ]
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True
    )
    try:
        proc.communicate(timeout=LAYOUT_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            proc.kill()
        proc.communicate()
        logger.warning("review_format: layout timed out for %s", file_path)
        return None
    pdf = os.path.join(out_dir, os.path.splitext(os.path.basename(file_path))[0] + ".pdf")
    return pdf if os.path.exists(pdf) else None


def _pdf_pages(pdf_path: str) -> List[List[str]]:
    """Non-empty text lines per page."""
    pages: List[str]
    if shutil.which("pdftotext"):
        raw = subprocess.run(
            ["pdftotext", "-layout", pdf_path, "-"], capture_output=True, timeout=60
        ).stdout.decode("utf-8", "ignore")
        pages = raw.split("\f")
        if pages and not pages[-1].strip():
            pages.pop()
    else:
        from pypdf import PdfReader

        pages = [(p.extract_text() or "") for p in PdfReader(pdf_path).pages]
    return [[ln.strip() for ln in pg.splitlines() if ln.strip()] for pg in pages]


def _find_page(norm_pages: List[List[str]], title: str, start: int) -> Optional[int]:
    """First page >= start with a *heading line* for [title]. TOC lines never
    match: they end in a page number, a heading line does not."""
    n = len(norm_pages)
    for i in range(start, n):
        if title in norm_pages[i]:
            return i
    prefix = title[:28]
    if len(prefix) >= 8:
        for i in range(start, n):
            for line in norm_pages[i]:
                if line.startswith(prefix) and not _LEADER_TAIL.search(line):
                    return i
    core = _strip_number(title)
    if len(core) >= 4:
        for i in range(start, n):
            for line in norm_pages[i]:
                if not _LEADER_TAIL.search(line) and _strip_number(line) == core:
                    return i
    return None


def apply_real_toc_pages(file_path: str, doc, blocks: List[Dict[str, Any]]) -> int:
    """Rewrite TOC page numbers in [blocks] from a real layout. Returns how many
    entries were updated (0 = untouched; never raises)."""
    try:
        if TOC_PAGE_MODE == "never":
            return 0
        toc_blocks = [b for b in blocks if b.get("block_type") == "toc"]
        if not toc_blocks:
            return 0
        if TOC_PAGE_MODE != "always" and not toc_pages_look_stale(doc):
            return 0

        tmp = tempfile.mkdtemp(prefix="review_layout_")
        try:
            pdf = _docx_to_pdf(file_path, tmp)
            pages = _pdf_pages(pdf) if pdf else []
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if not pages:
            return 0

        norm_pages = [[_norm(line) for line in pg] for pg in pages]
        toc_end = max(
            (
                i
                for i, pg in enumerate(norm_pages)
                if sum(1 for line in pg if _LEADER_TAIL.search(line)) >= 3
            ),
            default=-1,
        )
        cursor_page = toc_end + 1
        found: Dict[int, int] = {}
        for idx, block in enumerate(toc_blocks):
            title = _norm(_split_toc_text(block["text"])[0])
            if not title:
                continue
            page = _find_page(norm_pages, title, cursor_page)
            if page is not None:
                cursor_page = page
            else:  # e.g. an abstract placed before the TOC
                page = _find_page(norm_pages, title, 0)
            if page is not None:
                found[idx] = page + 1

        if len(found) < max(1, int(len(toc_blocks) * 0.6)):
            logger.info(
                "review_format: only %s/%s TOC entries located; keeping cached page numbers",
                len(found),
                len(toc_blocks),
            )
            return 0
        for idx, number in found.items():
            block = toc_blocks[idx]
            title = _split_toc_text(block["text"])[0]
            block["text"] = f"{title}\t{number}"
            block["page_number"] = number
        logger.info("review_format: refreshed %s TOC page numbers from layout", len(found))
        return len(found)
    except Exception:
        logger.exception("review_format: TOC page refresh failed")
        return 0