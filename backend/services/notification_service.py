"""
services/notification_service.py — Unified in-app notification system.

Provides a fail-safe notify() function that never raises, so notification
failures can never break the main action flow.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from database import get_db

logger = logging.getLogger(__name__)

_LOCK_RETRY_DELAYS = (0.2, 0.5, 1.0)


class NotificationType:
    """Constants for all notification type strings."""
    
    # Student notifications
    ANALYSIS_FINISHED = "analysis_finished"
    ANALYSIS_FAILED = "analysis_failed"
    UPLOAD_REJECTED = "upload_rejected"
    ASSIGNMENT_ACCEPTED = "assignment_accepted"
    ASSIGNMENT_REJECTED = "assignment_rejected"
    SUBMISSION_APPROVED = "submission_approved"
    SUBMISSION_REVISION_REQUESTED = "submission_revision_requested"
    SUBMISSION_REJECTED = "submission_rejected"
    SUPERVISOR_COMMENT = "supervisor_comment"
    MEETING_NOTE = "meeting_note"
    COLLABORATION_INVITE = "collaboration_invite"
    MERGE_CONFLICT = "merge_conflict"
    MEMBER_COMMIT = "member_commit"
    NEW_VERSION = "new_version"
    GROUP_DISCARDED = "group_discarded"
    
    # Supervisor notifications
    NEW_ASSIGNMENT_REQUEST = "new_assignment_request"
    STUDENT_SUBMITTED = "student_submitted"
    STUDENT_RESUBMITTED = "student_resubmitted"
    PLAGIARISM_HIGH = "plagiarism_high"
    STUDENT_REPLY = "student_reply"
    
    # Org admin notifications
    SUPERVISOR_CREATED = "supervisor_created"
    NEW_USER_SIGNUP = "new_user_signup"
    TEMPLATE_PUBLISHED = "template_published"
    QR_UPLOAD_RECEIVED = "qr_upload_received"
    TRANSLATION_FINISHED = "translation_finished"
    
    # Deadline reminders
    DEADLINE_REMINDER_3_DAYS = "deadline_reminder_3_days"
    DEADLINE_REMINDER_1_DAY = "deadline_reminder_1_day"
    DEADLINE_TODAY = "deadline_today"


def notify(
    org_id: int,
    user_id: Optional[int],
    type: str,
    title: str,
    body: str,
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    payload: Optional[Dict[str, Any]] = None,
    dedupe_key: Optional[str] = None,
    conn=None,
) -> Optional[int]:
    """
    Create a notification. Never raises; logs errors and continues.

    Retries up to 3 times on "database is locked"/busy errors.

    Args:
        org_id: Organization ID (required for multi-tenancy)
        user_id: Recipient user ID (optional, fallback to recipient_email in legacy)
        type: Notification type string (use NotificationType constants)
        title: Short human-readable title
        body: Full message body
        entity_type: Type of related entity (e.g., 'document', 'group_document')
        entity_id: ID of related entity
        payload: JSON-serializable dict for deep-link/route data
        dedupe_key: Optional key to prevent duplicate notifications (e.g., deadline reminders)
        conn: Optional existing sqlite3 connection. When given, the row is written
            on that connection and is NOT committed or closed here — the caller's
            transaction controls visibility. Prefer calling notify() after the
            caller's conn.commit() instead.

    Returns:
        Notification ID if successful, None otherwise
    """
    for attempt in range(len(_LOCK_RETRY_DELAYS) + 1):
        own_conn = conn is None
        active_conn = None
        try:
            active_conn = conn if conn is not None else get_db()
            cursor = active_conn.cursor()

            # Check for duplicate only when an explicit dedupe_key is provided.
            # Without a key there is NO dedupe — same type/entity may legitimately recur.
            if dedupe_key:
                cursor.execute(
                    """
                    SELECT id FROM notifications
                    WHERE user_id IS ? AND dedupe_key = ?
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (user_id, dedupe_key),
                )
                if cursor.fetchone():
                    logger.debug("Deduped notification: user_id=%s dedupe_key=%s", user_id, dedupe_key)
                    if own_conn:
                        active_conn.close()
                    return None

            # Legacy readers match on recipient_email when user_id IS NULL, so
            # store the recipient's real email when we can resolve it.
            recipient_email = ""
            if user_id is not None:
                cursor.execute(
                    "SELECT email FROM users WHERE id = ?",
                    (user_id,),
                )
                email_row = cursor.fetchone()
                if email_row and email_row["email"]:
                    recipient_email = str(email_row["email"])

            payload_json = json.dumps(payload) if payload else None

            cursor.execute(
                """
                INSERT INTO notifications
                    (user_id, recipient_email, title, message, type, is_read,
                     related_type, related_id, org_id, body, entity_type,
                     payload_json, dedupe_key, created_at)
                VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    user_id,
                    recipient_email,
                    title,
                    body,
                    type,
                    entity_type,
                    entity_id,
                    org_id,
                    body,
                    entity_type,
                    payload_json,
                    dedupe_key,
                ),
            )
            notification_id = cursor.lastrowid
            if own_conn:
                active_conn.commit()
                active_conn.close()

            logger.info("Notification created: id=%s org_id=%s user_id=%s type=%s",
                       notification_id, org_id, user_id, type)
            return notification_id

        except Exception as exc:
            if own_conn and active_conn is not None:
                try:
                    active_conn.close()
                except Exception:
                    pass
            err = str(exc).lower()
            is_lock = "locked" in err or "busy" in err
            if is_lock and attempt < len(_LOCK_RETRY_DELAYS):
                time.sleep(_LOCK_RETRY_DELAYS[attempt])
                continue
            logger.exception(
                "Failed to create notification: org_id=%s user_id=%s type=%s",
                org_id, user_id, type,
            )
            return None
    return None


def notify_many(
    org_id: int,
    user_ids: List[int],
    type: str,
    title: str,
    body: str,
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    payload: Optional[Dict[str, Any]] = None,
    conn=None,
) -> List[Optional[int]]:
    """
    Create notifications for multiple recipients. Never raises.
    
    Returns:
        List of notification IDs (None for failed recipients)
    """
    results = []
    for user_id in user_ids:
        result = notify(
            org_id=org_id,
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            conn=conn,
        )
        results.append(result)
    return results
