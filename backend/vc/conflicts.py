"""Conflict detection at merge time."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from database import get_db
from vc.utils import content_matches_section, word_overlap_ratio


def _since_filter(last_merge_at: Optional[str]) -> Tuple[str, List[Any]]:
    if last_merge_at:
        return "AND created_at > ?", [last_merge_at]
    return "", []


def _latest_per_author(
    project_id: int,
    section_id: str,
    since_clause: str,
    since_params: List[Any],
) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT c.* FROM section_commits c
        INNER JOIN (
            SELECT author_id, MAX(created_at) AS max_created
            FROM section_commits
            WHERE project_id = ? AND section_id = ? {since_clause}
            GROUP BY author_id
        ) latest ON c.author_id = latest.author_id AND c.created_at = latest.max_created
        WHERE c.project_id = ? AND c.section_id = ?
        ORDER BY c.created_at DESC
        """,
        [project_id, section_id, *since_params, project_id, section_id],
    )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def detect_multi_author_conflicts(
    project_id: int,
    sections: List[Dict[str, Any]],
    last_merge_at: Optional[str],
) -> List[Dict[str, Any]]:
    since_clause, since_params = _since_filter(last_merge_at)
    conflicts: List[Dict[str, Any]] = []

    for sec in sections:
        sid = sec["section_id"]
        variants = _latest_per_author(project_id, sid, since_clause, since_params)
        if len(variants) < 2:
            continue

        contents = {v["content"].strip() for v in variants}
        if len(contents) <= 1:
            continue

        conflicts.append({
            "conflict_type": "multi_author",
            "section_id": sid,
            "section_name": sec["section_name"],
            "related_section_id": None,
            "related_section_name": None,
            "details": {
                "description": (
                    f"Section \"{sec['section_name']}\" was edited by "
                    f"{len(variants)} authors since the last merge."
                ),
                "variants": [
                    {
                        "author_id": v["author_id"],
                        "author_name": v["author_name"],
                        "content": v["content"],
                        "commit_id": v["id"],
                        "version_number": v["version_number"],
                        "created_at": v["created_at"],
                    }
                    for v in variants
                ],
            },
        })

    return conflicts


def detect_duplicate_content_conflicts(
    section_contents: Dict[str, Dict[str, Any]],
    threshold: float = 0.30,
) -> List[Dict[str, Any]]:
    conflicts: List[Dict[str, Any]] = []
    items = [
        (sid, data["section_name"], data["content"])
        for sid, data in section_contents.items()
        if (data.get("content") or "").strip()
    ]

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            sid_a, name_a, content_a = items[i]
            sid_b, name_b, content_b = items[j]
            ratio = word_overlap_ratio(content_a, content_b)
            if ratio < threshold:
                continue
            conflicts.append({
                "conflict_type": "duplicate_content",
                "section_id": sid_a,
                "section_name": name_a,
                "related_section_id": sid_b,
                "related_section_name": name_b,
                "details": {
                    "description": (
                        f"Sections \"{name_a}\" and \"{name_b}\" share "
                        f"{round(ratio * 100)}% word overlap."
                    ),
                    "overlap_ratio": round(ratio, 3),
                    "section_a": {"section_id": sid_a, "section_name": name_a, "content": content_a},
                    "section_b": {"section_id": sid_b, "section_name": name_b, "content": content_b},
                },
            })

    return conflicts


def detect_section_mismatch_conflicts(
    section_contents: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    conflicts: List[Dict[str, Any]] = []

    for sid, data in section_contents.items():
        content = (data.get("content") or "").strip()
        if not content:
            continue
        name = data["section_name"]
        matches, score, reason = content_matches_section(name, content)
        if matches and score >= 0.5:
            continue
        conflicts.append({
            "conflict_type": "section_mismatch",
            "section_id": sid,
            "section_name": name,
            "related_section_id": None,
            "related_section_name": None,
            "details": {
                "description": f"Content may not belong in section \"{name}\".",
                "reason": reason,
                "confidence": round(score, 3),
                "content_preview": content[:500],
                "section_name": name,
            },
        })

    return conflicts


def detect_all_conflicts(
    project_id: int,
    sections: List[Dict[str, Any]],
    section_contents: Dict[str, Dict[str, Any]],
    last_merge_at: Optional[str],
) -> List[Dict[str, Any]]:
    conflicts: List[Dict[str, Any]] = []
    conflicts.extend(detect_multi_author_conflicts(project_id, sections, last_merge_at))
    conflicts.extend(detect_duplicate_content_conflicts(section_contents))
    conflicts.extend(detect_section_mismatch_conflicts(section_contents))
    return conflicts


def store_conflicts(merge_id: int, conflicts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    stored: List[Dict[str, Any]] = []

    for conflict in conflicts:
        cursor.execute(
            """
            INSERT INTO merge_conflicts
            (merge_id, conflict_type, section_id, section_name,
             related_section_id, related_section_name, details, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                merge_id,
                conflict["conflict_type"],
                conflict.get("section_id"),
                conflict.get("section_name"),
                conflict.get("related_section_id"),
                conflict.get("related_section_name"),
                json.dumps(conflict["details"]),
            ),
        )
        conflict_id = cursor.lastrowid
        stored.append({
            "id": conflict_id,
            **conflict,
            "status": "pending",
            "resolution_content": None,
        })

    conn.commit()
    conn.close()
    return stored
