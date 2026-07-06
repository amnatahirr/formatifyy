"""
issue_utils.py — Normalize AI pipeline issues for the Flutter frontend.

Maps backend `function` fields to frontend `category` labels, extracts
paragraph indices, saves document images to disk, and builds structured
document blocks for the side-by-side preview.
"""

from __future__ import annotations

import base64
import os
import re
from typing import Any, Dict, List, Optional

from models import DocumentModel

FUNCTION_TO_CATEGORY = {
    "grammar": "Grammar",
    "formatting": "Formatting",
    "image_ethics": "Image Ethics",
    "image_relevance": "Image Relevance",
    "para_relevance": "Paragraph Relevance",
    "plagiarism": "Plagiarism",
}


def _para_index(paragraph_id: str) -> Optional[int]:
    if not paragraph_id:
        return None
    match = re.match(r"p(\d+)", str(paragraph_id))
    return int(match.group(1)) if match else None


def _image_index(image_id: str) -> int:
    if not image_id:
        return 0
    match = re.match(r"img(\d+)", str(image_id))
    return int(match.group(1)) if match else 0


def _normalize_confidence(value: Any) -> float:
    try:
        conf = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return conf / 100.0 if conf > 1.0 else conf


def save_document_images(doc: DocumentModel, document_id: int, upload_dir: str) -> Dict[str, str]:
    """Persist extracted images; return image_id → path relative to uploads/."""
    img_dir = os.path.join(upload_dir, "images", f"doc_{document_id}")
    os.makedirs(img_dir, exist_ok=True)
    paths: Dict[str, str] = {}

    for img in doc.images:
        if not img.base64:
            continue
        ext = "jpg" if img.base64.startswith("/9j/") else "png"
        rel = f"images/doc_{document_id}/{img.image_id}.{ext}"
        full = os.path.join(upload_dir, rel)
        try:
            with open(full, "wb") as f:
                f.write(base64.b64decode(img.base64))
            paths[img.image_id] = rel
        except Exception as exc:
            print(f"[issue_utils] failed to save {img.image_id}: {exc}")

    return paths


def build_document_blocks(
    doc: DocumentModel,
    image_paths: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Build ordered preview blocks interleaving paragraphs and images."""
    blocks: List[Dict[str, Any]] = []

    for p in doc.paragraphs:
        style = (p.style or "Normal").lower()
        if style.startswith("heading"):
            level_match = re.search(r"(\d+)", style)
            level = int(level_match.group(1)) if level_match else 1
            block_type = "heading"
        elif "list" in style:
            block_type = "list_item"
            level = None
        else:
            block_type = "paragraph"
            level = None

        blocks.append({
            "paragraph_id": p.paragraph_id,
            "type": block_type,
            "text": p.text,
            "page": p.page_number,
            "level": level,
            "heading_context": p.heading_context,
            "style": p.style,
        })

    for img in doc.images:
        rel_path = image_paths.get(img.image_id, "")
        blocks.append({
            "paragraph_id": "",
            "type": "image",
            "text": img.caption or "",
            "page": img.page_number,
            "image_id": img.image_id,
            "image_path": rel_path,
            "image_index": _image_index(img.image_id),
        })

    return blocks


def normalize_issue(
    issue: Dict[str, Any],
    image_paths: Dict[str, str],
    index: int = 0,
) -> Dict[str, Any]:
    """Add frontend-compatible aliases without removing pipeline fields."""
    func = (issue.get("function") or "").lower()
    category = issue.get("category") or FUNCTION_TO_CATEGORY.get(func, func.replace("_", " ").title())
    image_id = issue.get("image_id") or ""
    para_idx = _para_index(issue.get("paragraph_id") or "")

    normalized = dict(issue)
    normalized.update({
        "issue_id": issue.get("issue_id") or f"{func}_{image_id or issue.get('paragraph_id') or index}",
        "category": category,
        "description": issue.get("description") or issue.get("reason") or issue.get("explanation") or "",
        "message": issue.get("message") or issue.get("reason") or "",
        "current": issue.get("current") or issue.get("original") or issue.get("text_preview") or "",
        "confidence": _normalize_confidence(issue.get("confidence")),
        "para_index": para_idx,
        "image_index": _image_index(image_id),
        "image_path": image_paths.get(image_id, ""),
        "replace_image": bool(issue.get("replace_image") or func in ("image_ethics", "image_relevance")),
    })

    if issue.get("content_belongs_to"):
        normalized["correct_heading"] = issue.get("content_belongs_to")

    return normalized


def normalize_issues(
    issues: List[Dict[str, Any]],
    image_paths: Dict[str, str],
) -> List[Dict[str, Any]]:
    return [normalize_issue(iss, image_paths, idx) for idx, iss in enumerate(issues)]


def issues_for_paragraph(issues: List[Dict[str, Any]], paragraph_id: str) -> List[Dict[str, Any]]:
    return [i for i in issues if i.get("paragraph_id") == paragraph_id]


def issues_for_image(issues: List[Dict[str, Any]], image_id: str) -> List[Dict[str, Any]]:
    return [i for i in issues if i.get("image_id") == image_id]
