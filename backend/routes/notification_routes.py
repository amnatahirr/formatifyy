"""
routes/notification_routes.py — Unified notification endpoints.

Available to ALL roles, NOT gated by the FYP module.
Endpoints are scoped to the current user's id AND org_id.
"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from auth_jwt import decode_access_token, bearer_token_from_header
from database import get_db

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])
logger = logging.getLogger(__name__)


def _get_current_user_context(request: Request) -> dict[str, Any]:
    """Extract user_id, org_id, role from JWT token."""
    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    token = bearer_token_from_header(auth)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    claims = decode_access_token(token)
    return {
        "user_id": int(claims.get("user_id") or claims.get("sub") or 0),
        "org_id": int(claims.get("org_id") or 1),
        "role": claims.get("role") or "",
    }


class NotificationResponse(BaseModel):
    id: int
    user_id: Optional[int]
    title: str
    body: str
    type: str
    is_read: bool
    entity_type: Optional[str]
    entity_id: Optional[int]
    payload: Optional[dict[str, Any]]
    created_at: str
    read_at: Optional[str]


@router.get("")
def list_notifications(
    request: Request,
    unread_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query()] = 50,
    before_id: Annotated[Optional[int], Query()] = None,
):
    """
    List notifications for the current user, scoped by user_id AND org_id.
    Newest first, paginated.
    """
    ctx = _get_current_user_context(request)
    user_id = ctx["user_id"]
    org_id = ctx["org_id"]
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        sql = """
            SELECT id, user_id, title, body, type, is_read, related_type as entity_type, related_id as entity_id,
                   payload_json, created_at, read_at
            FROM notifications
            WHERE user_id = ? AND COALESCE(org_id, 1) = ?
        """
        params: list[Any] = [user_id, org_id]
        
        if unread_only:
            sql += " AND is_read = 0"
        
        if before_id:
            sql += " AND id < ?"
            params.append(before_id)
        
        sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
        notifications = []
        for row in rows:
            payload = None
            if row["payload_json"]:
                try:
                    payload = json.loads(row["payload_json"])
                except Exception:
                    pass
            
            notifications.append({
                "id": row["id"],
                "user_id": row["user_id"],
                "title": row["title"],
                "body": row["body"],
                "type": row["type"],
                "is_read": bool(row["is_read"]),
                "entity_type": row["entity_type"],
                "entity_id": row["entity_id"],
                "payload": payload,
                "created_at": row["created_at"],
                "read_at": row["read_at"],
            })
        
        return {"notifications": notifications}
        
    finally:
        conn.close()


@router.get("/unread-count")
def unread_count(request: Request):
    """Count unread notifications for the current user."""
    ctx = _get_current_user_context(request)
    user_id = ctx["user_id"]
    org_id = ctx["org_id"]
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT COUNT(*) FROM notifications
            WHERE user_id = ? AND COALESCE(org_id, 1) = ? AND is_read = 0
            """,
            (user_id, org_id),
        )
        count = cursor.fetchone()[0]
        return {"unread_count": count}
    finally:
        conn.close()


@router.post("/{notification_id}/read")
def mark_read(request: Request, notification_id: int):
    """Mark a notification as read. Scoped to current user AND org_id."""
    ctx = _get_current_user_context(request)
    user_id = ctx["user_id"]
    org_id = ctx["org_id"]
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Verify ownership
        cursor.execute(
            """
            SELECT id FROM notifications
            WHERE id = ? AND user_id = ? AND COALESCE(org_id, 1) = ?
            """,
            (notification_id, user_id, org_id),
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Notification not found")
        
        cursor.execute(
            """
            UPDATE notifications
            SET is_read = 1, read_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (notification_id,),
        )
        conn.commit()
        return {"status": "success"}
    finally:
        conn.close()


@router.post("/read-all")
def mark_all_read(request: Request):
    """Mark all notifications as read for the current user."""
    ctx = _get_current_user_context(request)
    user_id = ctx["user_id"]
    org_id = ctx["org_id"]
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE notifications
            SET is_read = 1, read_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND COALESCE(org_id, 1) = ? AND is_read = 0
            """,
            (user_id, org_id),
        )
        conn.commit()
        return {"status": "success"}
    finally:
        conn.close()


@router.delete("/{notification_id}")
def delete_notification(request: Request, notification_id: int):
    """Delete a notification. Scoped to current user AND org_id."""
    ctx = _get_current_user_context(request)
    user_id = ctx["user_id"]
    org_id = ctx["org_id"]
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Verify ownership
        cursor.execute(
            """
            SELECT id FROM notifications
            WHERE id = ? AND user_id = ? AND COALESCE(org_id, 1) = ?
            """,
            (notification_id, user_id, org_id),
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Notification not found")
        
        cursor.execute("DELETE FROM notifications WHERE id = ?", (notification_id,))
        conn.commit()
        return {"status": "success"}
    finally:
        conn.close()
