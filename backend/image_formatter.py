"""
image_formatter.py — Auto-format images in DOCX: resize, center, add AI captions.
"""

from __future__ import annotations

import base64
import os
import re
import shutil
from typing import Any, Dict, List, Optional, Tuple

from config import ANALYSIS_MODEL

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
    from docx_fields import paragraph_has_image
    return paragraph_has_image(para)


def _remove_floating_figure_captions(doc) -> int:
    """Remove figure captions trapped in text boxes / floating drawings."""
    removed = 0
    body = doc.element.body
    txbx_tag = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}txbxContent"

    for txbx in list(body.iter(txbx_tag)):
        texts = [t.text or "" for t in txbx.iter(W_T)]
        combined = "".join(texts).strip()
        if not FIGURE_CAPTION_RE.match(combined):
            continue
        parent = txbx
        for _ in range(12):
            parent = parent.getparent()
            if parent is None:
                break
            if parent.tag == W_P:
                gp = parent.getparent()
                if gp is not None:
                    gp.remove(parent)
                    removed += 1
                break

    for p_el in list(body.iter(W_P)):
        texts = [t.text or "" for t in p_el.iter(W_T)]
        combined = "".join(texts).strip()
        if not FIGURE_CAPTION_RE.match(combined):
            continue
        if p_el.findall(f".//{W_DRAWING}") and not p_el.findall(f".//{BLIP_TAG}"):
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
    from docx_fields import rebuild_caption_with_seq

    paragraphs = doc.paragraphs
    if img_idx < 0 or img_idx >= len(paragraphs):
        return

    img_para = paragraphs[img_idx]
    img_para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    try:
        img_para.paragraph_format.keep_with_next = True
    except Exception:
        pass

    cap_para = None
    if img_idx + 1 < len(paragraphs):
        nxt = paragraphs[img_idx + 1]
        if FIGURE_CAPTION_RE.match(nxt.text.strip()) and not _paragraph_has_image(nxt):
            cap_para = nxt

    label, description = _parse_figure_caption(caption)

    if cap_para is None:
        cap_para = _insert_paragraph_after(img_para, "")
        rebuild_caption_with_seq(cap_para, label, description)
    else:
        rebuild_caption_with_seq(cap_para, label, description)

    cap_para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Remove duplicate figure captions elsewhere in the document
    fig_match = FIGURE_CAPTION_RE.match(caption.strip())
    fig_num = fig_match.group(1) if fig_match else None
    for idx, para in enumerate(doc.paragraphs):
        if idx in (img_idx, img_idx + 1):
            continue
        if not FIGURE_CAPTION_RE.match(para.text.strip()):
            continue
        if fig_num and f"Figure {fig_num}" not in para.text[:20]:
            continue
        if _paragraph_has_image(para):
            continue
        p_el = para._element
        parent = p_el.getparent()
        if parent is not None:
            parent.remove(p_el)


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

    image_indices = [i for i, p in enumerate(doc.paragraphs) if _paragraph_has_image(p)]
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

        surrounding = _surrounding_text(doc.paragraphs, img_idx)
        if client:
            caption = await _generate_caption(client, b64, fig_num, surrounding)
        else:
            nxt_text = ""
            if img_idx + 1 < len(doc.paragraphs):
                nxt_text = doc.paragraphs[img_idx + 1].text.strip()
            if FIGURE_CAPTION_RE.match(nxt_text):
                caption = nxt_text
            else:
                caption = f"Figure {fig_num}: Illustration related to the document content."

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

    fig_num = 0
    results: List[Dict[str, Any]] = []
    captions_added = 0

    image_indices = [i for i, p in enumerate(doc.paragraphs) if _paragraph_has_image(p)]
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

        surrounding = _surrounding_text(doc.paragraphs, img_idx)
        caption = await _generate_caption(client, b64, fig_num, surrounding)
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


async def _generate_caption(client, b64: str, fig_num: int, surrounding: str) -> str:
    default = f"Figure {fig_num}: Illustration related to the document content."
    if not b64 or client is None:
        return default

    media_type = "image/jpeg" if b64.startswith("/9j/") else "image/png"
    prompt = f"""Generate a concise academic figure caption for this image.
Surrounding document text:
\"\"\"{surrounding[:800]}\"\"\"

Return ONLY valid JSON:
{{"caption": "Figure {fig_num}: <short descriptive caption under 20 words>"}}"""

    try:
        response = await client.messages.create(
            model=ANALYSIS_MODEL,
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        raw = response.content[0].text
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`")
        import json
        parsed = json.loads(cleaned)
        cap = parsed.get("caption", default)
        if not cap.lower().startswith("figure"):
            cap = f"Figure {fig_num}: {cap}"
        return cap
    except Exception as exc:
        print(f"[image_formatter] caption error: {exc}")
        return default
