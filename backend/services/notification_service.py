"""
services/notification_service.py — Unified in-app notification system.

Provides a fail-safe notify() function that never raises, so notification
failures can never break the main action flow.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from database import get_db

logger = logging.getLogger(__name__)


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
    
    # Supervisor notifications
    NEW_ASSIGNMENT_REQUEST = "new_assignment_request"
    STUDENT_SUBMITTED = "student_submitted"
    STUDENT_RESUBMITTED = "student_resubmitted"
    PLAGIARISM_HIGH = "plagiarism_high"
    STUDENT_REPLY = "student_reply"
    
    # Org admin notifications
    SUPERVISOR_CREATED = "supervisor_created"
    NEW_USER_SIGNUP = "new_user_signup"
    
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
) -> Optional[int]:
    """
    Create a notification. Never raises; logs errors and continues.
    
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
    
    Returns:
        Notification ID if successful, None otherwise
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check for duplicate if dedupe_key provided
        if dedupe_key:
            cursor.execute(
                """
                SELECT id FROM notifications
                WHERE org_id = ? AND type = ? AND related_id = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (org_id, type, entity_id),
            )
            if cursor.fetchone():
                logger.debug("Deduped notification: org_id=%s type=%s entity_id=%s", org_id, type, entity_id)
                conn.close()
                return None
        
        payload_json = json.dumps(payload) if payload else None
        
        cursor.execute(
            """
            INSERT INTO notifications
                (user_id, recipient_email, title, message, type, is_read, related_type, related_id,
                 org_id, body, entity_type, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                user_id,
                "",  # recipient_email is deprecated but kept for schema compat (empty string instead of NULL)
                title,
                body,
                type,
                entity_type,
                entity_id,
                org_id,
                body,
                entity_type,
                payload_json,
            ),
        )
        notification_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info("Notification created: id=%s org_id=%s user_id=%s type=%s", 
                   notification_id, org_id, user_id, type)
        return notification_id
        
    except Exception as exc:
        logger.exception("Failed to create notification: org_id=%s user_id=%s type=%s", 
                       org_id, user_id, type)
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
        )
        results.append(result)
    return results
