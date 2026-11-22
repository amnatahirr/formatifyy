"""
image_formatter.py — Auto-format images in DOCX: resize, center, add figure captions.

Captions are generated locally with BLIP (functions/local_vision.py), the same
caption the Image Ethics / Image Relevance tabs show. No external API is used.
A caption the student already wrote under the image is kept as it is.
"""

from __future__ import annotations

import base64
import os
import re
import shutil
from typing import Any, Dict, List, Optional, Tuple

FIGURE_CAPTION_RE = re.compile(r"^Figure\s+(\d+)\s*:", re.IGNORECASE)
BLIP_TAG = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
EMBED_ATTR = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
W_P = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
W_T = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
W_DRAWING = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing"


def _length_to_inches(value: float, unit: str = "mm") -> float:
    v = float(value)
    if unit == "mm":
        return round(v / 25.4, 4)
    return v


def _paragraph_has_image(para) -> bool:
    from docx_tools.docx_fields import paragraph_has_image
    return paragraph_has_image(para)


def _is_cover_or_info_para(doc, para) -> bool:
    from docx_tools.docx_fields import is_paragraph_in_cover_or_info
    return is_paragraph_in_cover_or_info(doc, para)


def _element_has_real_image(el) -> bool:
    """True when OOXML element contains an actual embedded picture (not caption chrome)."""
    if el is None:
        return False
    if list(el.iter(BLIP_TAG)):
        return True
    vml = "{urn:schemas-microsoft-com:vml}imagedata"
    if list(el.iter(vml)):
        return True
    pict = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pict"
    if list(el.iter(pict)):
        # Legacy WordArt-only pict without imagedata is rare; treat pict as image-ish
        return True
    return False


def _remove_floating_figure_captions(doc) -> int:
    """
    Remove figure captions trapped in text boxes / floating drawings.

    CRITICAL: never delete a paragraph that still holds a real image. Older logic
    walked from txbxContent up to w:p and removed the whole paragraph — that
    deleted pictures when Word stored a caption textbox inside the same drawing.
    """
    removed = 0
    body = doc.element.body
    txbx_tag = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}txbxContent"

    for txbx in list(body.iter(txbx_tag)):
        texts = [t.text or "" for t in txbx.iter(W_T)]
        combined = "".join(texts).strip()
        if not FIGURE_CAPTION_RE.match(combined):
            continue

        # Find enclosing paragraph
        parent = txbx
        para_el = None
        for _ in range(16):
            parent = parent.getparent()
            if parent is None:
                break
            if parent.tag == W_P:
                para_el = parent
                break

        if para_el is not None and _element_has_real_image(para_el):
            # Image lives here — only clear caption text inside the textbox.
            for t_el in txbx.iter(W_T):
                if t_el.text:
                    t_el.text = ""
            removed += 1
            continue

        if para_el is not None:
            gp = para_el.getparent()
            if gp is not None:
                gp.remove(para_el)
                removed += 1

    for p_el in list(body.iter(W_P)):
        if _element_has_real_image(p_el):
            continue
        texts = [t.text or "" for t in p_el.iter(W_T)]
        combined = "".join(texts).strip()
        if not FIGURE_CAPTION_RE.match(combined):
            continue
        # Caption-only floating drawing (no embedded picture)
        if p_el.findall(f".//{W_DRAWING}"):
            parent = p_el.getparent()
            if parent is not None:
                parent.remove(p_el)
                removed += 1
    return removed


def _insert_paragraph_after(ref_para, text: str):
    from docx.oxml import OxmlElement
    from docx.text.paragraph import Paragraph

    new_p = OxmlElement("w:p")
    ref_para._element.addnext(new_p)
    new_para = Paragraph(new_p, ref_para._parent)
    new_para.add_run(text)
    return new_para


def _set_caption_style(para) -> None:
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt

    pf = para.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf.space_before = Pt(2)
    pf.space_after = Pt(6)
    pf.keep_with_next = False
    try:
        para.style = "Caption"
    except Exception:
        pass
    if para.runs:
        run = para.runs[0]
        run.italic = True
        run.font.size = Pt(10)


def _parse_figure_caption(caption: str) -> tuple[str, str]:
    """Split 'Figure N: description' into (label, description)."""
    m = FIGURE_CAPTION_RE.match(caption.strip())
    if m:
        return "Figure", caption.split(":", 1)[1].strip() if ":" in caption else ""
    if ":" in caption:
        return "Figure", caption.split(":", 1)[1].strip()
    return "Figure", caption.strip()


def _ensure_caption_below_image(doc, img_idx: int, caption: str) -> None:
    """Place SEQ-based caption paragraph directly under the image paragraph."""
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx_tools.docx_fields import attach_figure_caption_below_image

    paragraphs = doc.paragraphs
    if img_idx < 0 or img_idx >= len(paragraphs):
        return

    img_para = paragraphs[img_idx]
    img_para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

    label, description = _parse_figure_caption(caption)
    cap_para = attach_figure_caption_below_image(
        doc,
        img_para,
        description=description or "Illustration related to the document content.",
        preferred_caption_text=caption,
    )
    cap_para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    # label kept for API compatibility / future use
    _ = label


async def fix_image_captions(
    file_path: str,
    client: Any = None,
    formatting_rules: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Reposition/create captions directly below each inline image."""
    from docx import Document

    if not file_path.endswith(".docx") or not os.path.exists(file_path):
        return {"status": "skipped", "captions_fixed": 0}

    doc = Document(file_path)
    _remove_floating_figure_captions(doc)

    image_indices = [
        i
        for i, p in enumerate(doc.paragraphs)
        if _paragraph_has_image(p) and not _is_cover_or_info_para(doc, p)
    ]
    fig_map = {idx: n + 1 for n, idx in enumerate(image_indices)}
    fixed = 0

    for img_idx in reversed(image_indices):
        fig_num = fig_map[img_idx]
        para = doc.paragraphs[img_idx]
        embed = None
        blips = list(para._element.iter(BLIP_TAG))
        if blips:
            embed = blips[0].get(EMBED_ATTR)

        b64 = ""
        if embed and embed in doc.part.related_parts:
            try:
                b64 = base64.b64encode(doc.part.related_parts[embed].blob).decode("utf-8")
            except Exception:
                pass

        caption = await _caption_for_image(doc, para, img_idx, b64, fig_num, client)

        _ensure_caption_below_image(doc, img_idx, caption)
        fixed += 1

    doc.save(file_path)
    return {"status": "success", "captions_fixed": fixed}


async def format_document_images(
    file_path: str,
    output_path: str,
    client: Any,
    formatting_rules: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Format all images in a DOCX: center, resize to max width, add Figure N captions.
    Returns summary dict for the Flutter ImageFormatterProvider.
    """
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    if not file_path.endswith(".docx"):
        return {"status": "error", "message": "Only DOCX supported", "total_images": 0, "images": []}

    shutil.copy2(file_path, output_path)
    doc = Document(output_path)

    max_width_in = _length_to_inches(
        formatting_rules.get("image_max_width", 120),
        formatting_rules.get("spacing_unit", "mm"),
    )
    if max_width_in > 6:
        max_width_in = 5.0

    _remove_floating_figure_captions(doc)

    image_indices = [
        i
        for i, p in enumerate(doc.paragraphs)
        if _paragraph_has_image(p) and not _is_cover_or_info_para(doc, p)
    ]
    fig_map = {idx: n + 1 for n, idx in enumerate(image_indices)}
    fig_num = 0
    results: List[Dict[str, Any]] = []
    captions_added = 0

    for img_idx in reversed(image_indices):
        para = doc.paragraphs[img_idx]
        blips = list(para._element.iter(BLIP_TAG))
        if not blips:
            continue

        fig_num = fig_map[img_idx]
        embed = blips[0].get(EMBED_ATTR)
        b64 = ""
        if embed and embed in doc.part.related_parts:
            try:
                blob = doc.part.related_parts[embed].blob
                b64 = base64.b64encode(blob).decode("utf-8")
            except Exception:
                pass

        caption = await _caption_for_image(doc, para, img_idx, b64, fig_num, client)
        captions_added += 1

        para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _ensure_caption_below_image(doc, img_idx, caption)

        results.append({
            "fig_num": fig_num,
            "rId": embed or "",
            "orig_w_in": max_width_in,
            "orig_h_in": max_width_in * 0.75,
            "disp_w_in": max_width_in,
            "disp_h_in": max_width_in * 0.75,
            "resized": True,
            "caption": caption,
        })

    doc.save(output_path)

    return {
        "status": "success" if fig_num else "no_images",
        "message": f"Formatted {fig_num} image(s)" if fig_num else "No images found",
        "total_images": fig_num,
        "captions_added": captions_added,
        "tof_added": False,
        "lof_ready": True,
        "images": results,
        "output_filename": os.path.basename(output_path),
        "manual_items": [],
        "manual_steps": [],
    }


def _surrounding_text(paragraphs, idx: int) -> str:
    parts = []
    for j in range(max(0, idx - 2), min(len(paragraphs), idx + 3)):
        t = paragraphs[j].text.strip()
        if t and not FIGURE_CAPTION_RE.match(t):
            parts.append(t)
    return "\n".join(parts)[:1500]


PLACEHOLDER_DESCRIPTION = "Illustration related to the document content."


def is_placeholder_description(desc: str) -> bool:
    """True for the old auto-filled text, so it gets replaced by a real caption."""
    return (desc or "").strip().rstrip(".").lower() == PLACEHOLDER_DESCRIPTION.rstrip(".").lower()


def _existing_caption_description(doc, img_para) -> str:
    """
    Description of a figure caption the student already wrote under this image
    (before the next image), e.g. 'Use Case Diagram' from 'Figure 3.2: Use Case Diagram'.
    Returns '' when there is none, or when it is only the old placeholder text.
    """
    from docx_tools.docx_fields import (
        CAPTION_TEXT_RE,
        _LOOSE_FIGURE_CAPTION_RE,
        _next_body_paragraphs,
        paragraph_has_image,
        paragraph_is_figure_caption,
    )

    for cand in _next_body_paragraphs(doc, img_para, limit=12):
        if paragraph_has_image(cand):
            break
        if not paragraph_is_figure_caption(cand):
            continue
        text = (cand.text or "").strip()
        desc = ""
        m = _LOOSE_FIGURE_CAPTION_RE.match(text)
        if m and (m.group(2) or "").strip():
            desc = m.group(2).strip()
        else:
            cm = CAPTION_TEXT_RE.match(text)
            if cm and cm.group(3).strip():
                desc = cm.group(3).strip()
        return "" if is_placeholder_description(desc) else desc
    return ""


async def _generate_caption(client, b64: str, fig_num: int, surrounding: str) -> str:
    """
    'Figure N: <description>' from the local BLIP caption of the image.

    Same (cached) BLIP caption the Image Ethics / Relevance tabs use, cleaned with
    tidy_caption. `client` and `surrounding` are kept for signature compatibility
    and are not used (no external API).
    """
    import asyncio
    from functions.local_vision import generate_caption_from_b64, image_fingerprint, tidy_caption

    default = f"Figure {fig_num}: {PLACEHOLDER_DESCRIPTION}"
    if not b64:
        return default
    try:
        raw = await asyncio.to_thread(
            generate_caption_from_b64, b64, image_fingerprint(b64)
        )
        desc = tidy_caption(raw)
        if not desc:
            return default
        print(f"[image_formatter] Figure {fig_num}: BLIP '{raw}' -> '{desc}'")
        return f"Figure {fig_num}: {desc}"
    except Exception as exc:
        print(f"[image_formatter] caption error: {exc}")
        return default


_NUMBERED_HEADING_RE = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s+(\S.*)$")


def _heading_fallback_description(doc, img_idx: int) -> str:
    """
    For drawings with no picture file (Word shapes / SmartArt) BLIP has nothing
    to read: use the nearest heading at or above the drawing, e.g.
    '9.2. Methodology' -> 'Methodology'. Returns '' when none is found.
    """
    paragraphs = doc.paragraphs
    for j in range(img_idx, max(-1, img_idx - 6), -1):
        para = paragraphs[j]
        text = (para.text or "").strip()
        if not text or len(text) > 80 or FIGURE_CAPTION_RE.match(text):
            continue
        style = (getattr(para.style, "name", "") or "").lower()
        m = _NUMBERED_HEADING_RE.match(text)
        if style.startswith("heading") or m:
            return (m.group(1) if m else text).strip().rstrip(".:")
    return ""


async def _caption_for_image(doc, para, img_idx: int, b64: str, fig_num: int, client) -> str:
    """Student's own caption if present, else BLIP caption, else nearest heading."""
    existing = _existing_caption_description(doc, para)
    if existing:
        return f"Figure {fig_num}: {existing}"
    surrounding = _surrounding_text(doc.paragraphs, img_idx)
    caption = await _generate_caption(client, b64, fig_num, surrounding)
    if not b64 and is_placeholder_description(caption.split(":", 1)[-1]):
        heading = _heading_fallback_description(doc, img_idx)
        if heading:
            print(f"[image_formatter] Figure {fig_num}: no picture file (drawing), "
                  f"using heading '{heading}'")
            return f"Figure {fig_num}: {heading}"
    return caption
