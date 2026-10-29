"""
pdf_io.py — Robust PDF text/image extraction with PyMuPDF + fallbacks.

System PyMuPDF installs on macOS sometimes miss libmupdf.dylib. When that
happens we fall back to pdfplumber / pypdf so PDF analyze still works like DOCX.

Critical: PDF extractors return *visual lines*, not paragraphs. Treating each
line as a Word paragraph (with first-line indent) destroys layout. Always run
`merge_pdf_lines_to_paragraphs` before writing a DOCX.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple


@dataclass
class PdfPageContent:
    page_number: int
    lines: List[Tuple[str, float, bool]] = field(default_factory=list)
    # (text, font_size, is_bold)
    images_b64: List[str] = field(default_factory=list)


@dataclass
class PdfExtractResult:
    pages: List[PdfPageContent]
    backend: str  # "pymupdf" | "pdfplumber" | "pypdf"

    @property
    def total_pages(self) -> int:
        return max(1, len(self.pages))


_HEADING_LINE_RE = re.compile(
    r"^(?:"
    r"\d+(?:\.\d+)*\.?\s+\S.{0,80}"  # 1. Intro / 1.1 Scope
    r"|abstract|introduction|background|literature\s+review|methodology|"
    r"results|discussion|conclusion|references|acknowledgements?|"
    r"appendix\b.{0,40}|table\s+of\s+contents|list\s+of\s+(?:figures|tables)"
    r")\.?:?$",
    re.IGNORECASE,
)


def pymupdf_usable() -> bool:
    """True if `import fitz` and a trivial open works."""
    try:
        import fitz  # noqa: F401
        from pymupdf import Identity  # noqa: F401
        return True
    except Exception:
        return False


def extract_pdf(file_path: str) -> PdfExtractResult:
    """
    Extract per-page text lines (+ images when available).
    Prefers PyMuPDF → pdfplumber → pypdf.
    """
    errors: List[str] = []

    try:
        return _extract_with_pymupdf(file_path)
    except Exception as exc:
        errors.append(f"pymupdf: {exc}")

    try:
        return _extract_with_pdfplumber(file_path)
    except Exception as exc:
        errors.append(f"pdfplumber: {exc}")

    try:
        return _extract_with_pypdf(file_path)
    except Exception as exc:
        errors.append(f"pypdf: {exc}")
        raise RuntimeError(
            "Could not read PDF. "
            + " | ".join(errors)
            + ". Install a working PDF library: pip install pypdf pdfplumber PyMuPDF"
        ) from exc


def extract_pdf_plain_text(file_path: str) -> str:
    """Plain text for plagiarism / corpus ingest (paragraph-merged)."""
    return "\n\n".join(pdf_to_paragraphs(file_path)).strip()


_CAPTION_LINE_RE = re.compile(
    r"^(?:Figure|Fig\.?|Table)\s*\d+\s*[:.\-–—]\s*\S",
    re.IGNORECASE,
)
# Manual / numbered list markers (single-level only — not "3.2. Heading")
_LIST_ITEM_LINE_RE = re.compile(
    r"^(?:"
    r"[•*○■▪\-–—→»·]"
    r"|\(?[A-Za-z][.)]"
    r"|\(?[ivxlcdmIVXLCDM]+[.)]"
    r"|\(?\d+[.)](?!\d)"
    r")\s+\S"
)
_LIST_MARKER_ONLY_RE = re.compile(
    r"^(?:"
    r"[•*○■▪\-–—→»·]"
    r"|\(?[A-Za-z][.)]"
    r"|\(?[ivxlcdmIVXLCDM]+[.)]"
    r"|\(?\d+[.)](?!\d)"
    r")\s+"
)


def looks_like_caption_line(text: str) -> bool:
    """Figure/Table caption that must sit directly under its image/table."""
    return bool(_CAPTION_LINE_RE.match((text or "").strip()))


def looks_like_bullet_marker_line(text: str) -> bool:
    """True only for explicit bullet/number markers (not Label: colon prose)."""
    t = (text or "").strip()
    if not t or looks_like_caption_line(t):
        return False
    if re.match(r"^\d+\.\d+", t):
        return False
    return bool(_LIST_ITEM_LINE_RE.match(t))


def looks_like_list_item_line(text: str) -> bool:
    """True for bullet / numbered list body lines (not hierarchical headings)."""
    t = (text or "").strip()
    if not t or looks_like_caption_line(t):
        return False
    # Hierarchical section titles stay headings, never list items
    if re.match(r"^\d+\.\d+", t):
        return False
    if looks_like_bullet_marker_line(t):
        return True
    # "Label: description" module-style rows — candidate lists only (agent confirms)
    if re.match(r"^[A-Z][^:]{0,60}:\s+\S.{15,}", t) and len(t.split()) >= 6:
        return True
    return False


def looks_like_heading_line(text: str) -> bool:
    """Heuristic: short title-like line that should stay its own paragraph."""
    t = (text or "").strip()
    if not t or len(t) > 100:
        return False
    if looks_like_caption_line(t):
        return False
    # Long single-level numbered lines are list items, not headings
    if looks_like_list_item_line(t) and len(t.split()) > 6:
        return False
    words = t.split()
    if len(words) > 12:
        return False
    if t.endswith((".", "?", "!")) and len(words) > 4:
        return False
    if _HEADING_LINE_RE.match(t):
        # "1. Introduction" OK; reject if it looks like a long list sentence
        if re.match(r"^\d+\.\s+", t) and not re.match(r"^\d+\.\d+", t) and len(words) > 6:
            return False
        return True
    if t.isupper() and 1 <= len(words) <= 10:
        return True
    core = t.rstrip(":")
    if core.istitle() and 1 <= len(words) <= 8:
        return True
    if re.match(r"^\d+(?:\.\d+)+\.?\s+\S", t) and len(words) <= 12:
        # hierarchical numbering only (1.1, 2.3.1)
        return True
    if re.match(r"^\d+\.\s+\S", t) and len(words) <= 6:
        return True
    return False


def strip_list_marker(text: str) -> str:
    """Remove leading bullet/number marker; keep the item body."""
    t = (text or "").strip()
    return _LIST_MARKER_ONLY_RE.sub("", t, count=1).strip() if _LIST_MARKER_ONLY_RE.match(t) else t


def merge_pdf_lines_to_paragraphs_with_pages(
    lines: Sequence[str],
    line_pages: Sequence[int] | None = None,
) -> List[Tuple[str, int]]:
    """
    Rebuild real paragraphs from PDF visual wrap lines, with a page number
    for each merged paragraph (from the first contributing source line).

    Without this, each ~80-char wrap becomes a Word paragraph and template
    first-line indent makes the page look like a broken two-column layout.
    """
    if line_pages is None:
        pages_src: List[int] = [1] * len(lines)
    else:
        pages_src = list(line_pages)
        if len(pages_src) < len(lines):
            pages_src.extend([pages_src[-1] if pages_src else 1] * (len(lines) - len(pages_src)))

    paragraphs: List[Tuple[str, int]] = []
    buf: List[str] = []
    buf_page = 1

    def flush() -> None:
        nonlocal buf, buf_page
        if not buf:
            return
        text = " ".join(buf)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            paragraphs.append((text, buf_page))
        buf = []

    for idx, raw in enumerate(lines):
        line = (raw or "").strip()
        page_num = int(pages_src[idx]) if idx < len(pages_src) else 1
        if not line:
            flush()
            continue

        if looks_like_heading_line(line) or looks_like_caption_line(line) or looks_like_list_item_line(line):
            flush()
            paragraphs.append((line, page_num))
            continue

        if not buf:
            buf = [line]
            buf_page = page_num
            continue

        prev = buf[-1]
        starts_lower = bool(line[:1].islower())
        prev_ended = prev.endswith((".", "?", "!"))
        if prev_ended and not starts_lower and looks_like_heading_line(line):
            flush()
            paragraphs.append((line, page_num))
            continue
        if prev_ended and line[:1].isupper() and len(line.split()) > 8:
            flush()
            buf = [line]
            buf_page = page_num
            continue

        # Hyphenated wrap: "format-" + "ting" → "formatting"
        if prev.endswith("-") and line[:1].islower():
            buf[-1] = prev[:-1] + line
        else:
            buf.append(line)

    flush()
    return paragraphs


def merge_pdf_lines_to_paragraphs(lines: Sequence[str]) -> List[str]:
    """
    Rebuild real paragraphs from PDF visual wrap lines.

    Without this, each ~80-char wrap becomes a Word paragraph and template
    first-line indent makes the page look like a broken two-column layout.
    """
    return [text for text, _ in merge_pdf_lines_to_paragraphs_with_pages(lines)]


def pdf_to_text_lines(file_path: str) -> List[str]:
    """Flat list of non-empty visual lines (raw extractor output)."""
    result = extract_pdf(file_path)
    lines: List[str] = []
    for page in result.pages:
        if lines and lines[-1] != "":
            lines.append("")
        for text, _, _ in page.lines:
            if text.strip():
                lines.append(text)
    return lines


def pdf_to_paragraphs(file_path: str) -> List[str]:
    """Paragraphs suitable for writing a clean DOCX from a PDF."""
    return merge_pdf_lines_to_paragraphs(pdf_to_text_lines(file_path))


def _extract_with_pymupdf(file_path: str) -> PdfExtractResult:
    import fitz

    pdf = fitz.open(file_path)
    pages: List[PdfPageContent] = []
    try:
        for page_num in range(len(pdf)):
            page = pdf[page_num]
            page_content = PdfPageContent(page_number=page_num + 1)

            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
            for block in blocks:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    if not spans:
                        continue
                    text = "".join(s.get("text", "") for s in spans).strip()
                    if not text:
                        continue
                    font_size = float(spans[0].get("size", 12) or 12)
                    is_bold = "bold" in str(spans[0].get("font", "")).lower()
                    page_content.lines.append((text, font_size, is_bold))

            for img_info in page.get_images(full=True):
                xref = img_info[0]
                try:
                    base_image = pdf.extract_image(xref)
                    img_bytes = base_image.get("image")
                    if img_bytes:
                        page_content.images_b64.append(
                            base64.b64encode(img_bytes).decode("utf-8")
                        )
                except Exception:
                    continue

            pages.append(page_content)
    finally:
        pdf.close()

    return PdfExtractResult(pages=pages, backend="pymupdf")


def _extract_with_pdfplumber(file_path: str) -> PdfExtractResult:
    import pdfplumber

    pages: List[PdfPageContent] = []
    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            page_content = PdfPageContent(page_number=page_num + 1)
            raw = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            for line in raw.splitlines():
                text = line.strip()
                if text:
                    page_content.lines.append((text, 12.0, False))
            pages.append(page_content)

    if not pages:
        pages.append(PdfPageContent(page_number=1))
    return PdfExtractResult(pages=pages, backend="pdfplumber")


def _extract_with_pypdf(file_path: str) -> PdfExtractResult:
    from pypdf import PdfReader

    reader = PdfReader(file_path)
    pages: List[PdfPageContent] = []

    for page_num, page in enumerate(reader.pages):
        page_content = PdfPageContent(page_number=page_num + 1)
        try:
            raw = page.extract_text() or ""
        except Exception:
            raw = ""

        for line in raw.splitlines():
            text = line.strip()
            if not text:
                continue
            page_content.lines.append((text, 12.0, False))

        try:
            page_content.images_b64.extend(_pypdf_page_images(page))
        except Exception:
            pass

        pages.append(page_content)

    if not pages:
        pages.append(PdfPageContent(page_number=1))

    return PdfExtractResult(pages=pages, backend="pypdf")


def _pypdf_page_images(page) -> List[str]:
    """Extract image XObjects from a pypdf page when possible."""
    out: List[str] = []
    try:
        resources = page.get("/Resources")
        if resources is None:
            return out
        if hasattr(resources, "get_object"):
            resources = resources.get_object()
        xobject = resources.get("/XObject") if resources else None
        if xobject is None:
            return out
        if hasattr(xobject, "get_object"):
            xobject = xobject.get_object()

        for _name in xobject:
            obj = xobject[_name]
            if hasattr(obj, "get_object"):
                obj = obj.get_object()
            if obj.get("/Subtype") != "/Image":
                continue
            try:
                data = obj.get_data()
            except Exception:
                continue
            if not data:
                continue
            out.append(base64.b64encode(data).decode("utf-8"))
    except Exception:
        return out
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# Structured flow (paragraphs + tables + images) for PDF → DOCX
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PdfFlowBlock:
    """One document element in reading order."""
    kind: str  # "paragraph" | "table" | "image"
    page_number: int
    top: float
    text: str = ""
    table: Optional[List[List[str]]] = None
    image_bytes: Optional[bytes] = None
    image_ext: str = ".png"
    width_pt: float = 0.0
    bottom: float = 0.0
    caption: str = ""
    is_list_item: bool = False


def extract_pdf_flow_blocks(file_path: str) -> List[PdfFlowBlock]:
    """
    Build a reading-order stream of paragraphs, tables, and images.

    Table cell text is excluded from paragraph extraction so tables are not
    flattened into broken body lines. Images are kept as binary payloads.
    """
    try:
        return _extract_flow_with_pdfplumber(file_path)
    except Exception as exc:
        print(f"[pdf_io] structured pdfplumber flow failed: {exc}")

    # Fallback: paragraphs only + any extractable images appended at end
    blocks: List[PdfFlowBlock] = []
    for i, text in enumerate(pdf_to_paragraphs(file_path)):
        blocks.append(PdfFlowBlock(kind="paragraph", page_number=1, top=float(i), text=text))
    try:
        result = extract_pdf(file_path)
        top = float(len(blocks))
        for page in result.pages:
            for b64 in page.images_b64:
                try:
                    raw = base64.b64decode(b64)
                except Exception:
                    continue
                if len(raw) < 200:
                    continue
                ext = ".jpg" if raw[:3] == b"\xff\xd8\xff" else ".png"
                blocks.append(
                    PdfFlowBlock(
                        kind="image",
                        page_number=page.page_number,
                        top=top,
                        image_bytes=raw,
                        image_ext=ext,
                    )
                )
                top += 1
    except Exception:
        pass
    return blocks


def _bbox_contains(bbox: Tuple[float, float, float, float], x: float, y: float, pad: float = 3.0) -> bool:
    x0, top, x1, bottom = bbox
    return (x0 - pad) <= x <= (x1 + pad) and (top - pad) <= y <= (bottom + pad)


def _normalize_table_cells(raw_table: List[List]) -> List[List[str]]:
    rows: List[List[str]] = []
    for row in raw_table or []:
        if row is None:
            continue
        cells: List[str] = []
        for cell in row:
            if cell is None:
                cells.append("")
            else:
                cells.append(re.sub(r"\s+", " ", str(cell).replace("\n", " ")).strip())
        # Skip completely empty rows
        if any(c for c in cells):
            rows.append(cells)
    if not rows:
        return []
    # Normalize column count
    width = max(len(r) for r in rows)
    return [r + [""] * (width - len(r)) for r in rows]


def _image_bytes_from_plumber(im: dict, page) -> Tuple[Optional[bytes], str]:
    """Return (bytes, ext) for a pdfplumber image dict."""
    from io import BytesIO

    stream = im.get("stream")
    if stream is not None:
        try:
            data = stream.get_data()
        except Exception:
            data = None
        if data:
            if data[:3] == b"\xff\xd8\xff":
                return data, ".jpg"
            if data[:8] == b"\x89PNG\r\n\x1a\n":
                return data, ".png"
            # Raw bitmap → PNG via Pillow when possible
            try:
                from PIL import Image as PILImage

                src = im.get("srcsize") or (int(im.get("width") or 0), int(im.get("height") or 0))
                w, h = int(src[0]), int(src[1])
                if w > 0 and h > 0 and len(data) >= w * h * 3:
                    img = PILImage.frombytes("RGB", (w, h), data[: w * h * 3])
                    buf = BytesIO()
                    img.save(buf, format="PNG")
                    return buf.getvalue(), ".png"
            except Exception:
                pass

    # Render crop fallback
    try:
        from io import BytesIO

        cropped = page.crop((im["x0"], im["top"], im["x1"], im["bottom"]))
        rendered = cropped.to_image(resolution=140)
        buf = BytesIO()
        rendered.original.save(buf, format="PNG")
        return buf.getvalue(), ".png"
    except Exception as exc:
        print(f"[pdf_io] image crop failed: {exc}")
        return None, ".png"


def _extract_flow_with_pdfplumber(file_path: str) -> List[PdfFlowBlock]:
    import pdfplumber

    blocks: List[PdfFlowBlock] = []

    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            page_number = page_num + 1
            page_blocks: List[PdfFlowBlock] = []

            # ── Tables ──────────────────────────────────────────────────────
            table_bboxes: List[Tuple[float, float, float, float]] = []
            try:
                found = list(page.find_tables() or [])
            except Exception:
                found = []
            for ft in found:
                try:
                    bbox = tuple(ft.bbox)  # type: ignore[arg-type]
                    data = _normalize_table_cells(ft.extract() or [])
                except Exception:
                    continue
                if not data or len(data) < 1 or len(data[0]) < 1:
                    continue
                # Require at least 2 cells total to count as a table
                if sum(1 for r in data for c in r if c) < 2:
                    continue
                table_bboxes.append(bbox)  # type: ignore[arg-type]
                page_blocks.append(
                    PdfFlowBlock(
                        kind="table",
                        page_number=page_number,
                        top=float(bbox[1]),
                        bottom=float(bbox[3]),
                        table=data,
                    )
                )

            # ── Images (skip tiny decorative marks) ─────────────────────────
            image_bboxes: List[Tuple[float, float, float, float]] = []
            for im in page.images or []:
                try:
                    w = float(im.get("width") or 0)
                    h = float(im.get("height") or 0)
                    if w < 40 or h < 40 or (w * h) < 2500:
                        continue
                    bbox = (float(im["x0"]), float(im["top"]), float(im["x1"]), float(im["bottom"]))
                    raw, ext = _image_bytes_from_plumber(im, page)
                    if not raw or len(raw) < 200:
                        continue
                    image_bboxes.append(bbox)
                    page_blocks.append(
                        PdfFlowBlock(
                            kind="image",
                            page_number=page_number,
                            top=bbox[1],
                            bottom=bbox[3],
                            image_bytes=raw,
                            image_ext=ext,
                            width_pt=w,
                        )
                    )
                except Exception as exc:
                    print(f"[pdf_io] skip image on p{page_number}: {exc}")

            skip_bboxes = table_bboxes + image_bboxes

            # ── Text lines outside tables/images ────────────────────────────
            try:
                lines = page.extract_text_lines() or []
            except Exception:
                raw = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
                lines = [{"text": ln, "x0": 0, "top": i, "x1": 0, "bottom": i} for i, ln in enumerate(raw.splitlines())]

            kept_lines: List[str] = []
            line_tops: List[float] = []
            for line in lines:
                text = (line.get("text") or "").strip()
                if not text:
                    continue
                mx = (float(line.get("x0") or 0) + float(line.get("x1") or 0)) / 2.0
                my = (float(line.get("top") or 0) + float(line.get("bottom") or 0)) / 2.0
                if any(_bbox_contains(b, mx, my) for b in skip_bboxes):
                    continue
                kept_lines.append(text)
                line_tops.append(float(line.get("top") or 0))

            # Merge into paragraphs; place each paragraph at first contributing line top
            # Walk lines with blank/heading breaks while tracking tops.
            para_bufs: List[Tuple[float, List[str]]] = []
            buf: List[str] = []
            buf_top = 0.0

            def flush_buf() -> None:
                nonlocal buf, buf_top
                if not buf:
                    return
                merged = merge_pdf_lines_to_paragraphs(buf)
                # merge_pdf_lines_to_paragraphs may split further; assign same top
                for p in merged:
                    para_bufs.append((buf_top, [p]))
                buf = []

            for text, top in zip(kept_lines, line_tops):
                # Captions / list markers / headings always start a new block
                if (
                    looks_like_caption_line(text)
                    or looks_like_heading_line(text)
                    or looks_like_list_item_line(text)
                ):
                    flush_buf()
                    para_bufs.append((top, [text]))
                    continue
                if not buf:
                    buf = [text]
                    buf_top = top
                    continue
                prev = buf[-1]
                if prev.endswith((".", "?", "!")) and text[:1].isupper() and len(text.split()) > 8:
                    flush_buf()
                    buf = [text]
                    buf_top = top
                elif prev.endswith("-") and text[:1].islower():
                    buf[-1] = prev[:-1] + text
                else:
                    buf.append(text)
            flush_buf()

            for top, parts in para_bufs:
                for text in parts:
                    if text.strip():
                        page_blocks.append(
                            PdfFlowBlock(
                                kind="paragraph",
                                page_number=page_number,
                                top=top,
                                text=text.strip(),
                                is_list_item=looks_like_bullet_marker_line(text),
                            )
                        )

            # Attach Figure/Table captions to the nearest image/table above them
            _attach_captions_to_media(page_blocks)

            page_blocks.sort(key=lambda b: b.top)
            blocks.extend(page_blocks)

    return _merge_continued_tables(blocks)


def _attach_captions_to_media(page_blocks: List[PdfFlowBlock]) -> None:
    """
    Bind caption paragraphs to the image/table directly above them and remove
    the standalone caption block so DOCX can place caption immediately below.
    """
    captions = [
        b for b in page_blocks
        if b.kind == "paragraph" and looks_like_caption_line(b.text)
    ]
    for cap in captions:
        media = [
            b for b in page_blocks
            if b.kind in ("image", "table") and (b.bottom or b.top) <= cap.top + 2
        ]
        if not media:
            # Fallback: nearest media above by top
            media = [b for b in page_blocks if b.kind in ("image", "table") and b.top < cap.top]
        if not media:
            continue
        target = max(media, key=lambda b: b.bottom or b.top)
        # Must be reasonably close under the media (within ~220pt ≈ 3")
        gap = cap.top - (target.bottom or target.top)
        if gap < -5 or gap > 220:
            continue
        if target.kind == "image":
            target.caption = cap.text.strip()
            try:
                page_blocks.remove(cap)
            except ValueError:
                pass
        elif target.kind == "table" and not target.caption:
            # Keep table captions as a paragraph immediately after table in sort
            # by bumping top to just after table
            cap.top = (target.bottom or target.top) + 0.1
            target.caption = cap.text.strip()
            try:
                page_blocks.remove(cap)
            except ValueError:
                pass


def _merge_continued_tables(blocks: List[PdfFlowBlock]) -> List[PdfFlowBlock]:
    """Merge adjacent tables with the same column count (multi-page tables)."""
    if not blocks:
        return blocks
    out: List[PdfFlowBlock] = []
    for block in blocks:
        if (
            out
            and block.kind == "table"
            and out[-1].kind == "table"
            and out[-1].table
            and block.table
            and len(out[-1].table[0]) == len(block.table[0])
        ):
            # Skip duplicate header row if identical to previous header
            rows = list(block.table)
            if rows and out[-1].table and rows[0] == out[-1].table[0]:
                rows = rows[1:]
            out[-1].table = list(out[-1].table) + rows
            continue
        out.append(block)
    return out
