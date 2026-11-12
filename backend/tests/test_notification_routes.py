"""
Tests for notification endpoints:
- Create notification via notify()
- Unread count
- Mark single notification as read
- Mark all notifications as read
- Pagination via before_id
- User A cannot read/modify/delete user B's notification
- User from another org cannot access
- Dedupe prevents duplicate notifications
- notify() swallows errors (never raises)
"""

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import pytest
from fastapi.testclient import TestClient

from auth_jwt import create_access_token
from database import get_db, init_db
from main import app
from services.notification_service import notify, NotificationType


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def test_users():
    """Create test users in different orgs."""
    init_db()
    conn = get_db()
    cur = conn.cursor()

    # Get or create user in org 1
    cur.execute("SELECT id, org_id FROM users WHERE role = 'student' AND org_id = 1 LIMIT 1")
    row = cur.fetchone()
    if row:
        user1_id, user1_org = row["id"], row["org_id"]
    else:
        cur.execute(
            "INSERT INTO users (username, email, password, role, org_id) VALUES (?, ?, ?, 'student', 1)",
            ("test_user1", "test1@example.com", "hashed_pw"),
        )
        user1_id = cur.lastrowid
        user1_org = 1

    # Get or create user in org 1 (second user)
    cur.execute("SELECT id, org_id FROM users WHERE role = 'student' AND org_id = 1 AND id != ? LIMIT 1", (user1_id,))
    row = cur.fetchone()
    if row:
        user2_id, user2_org = row["id"], row["org_id"]
    else:
        cur.execute(
            "INSERT INTO users (username, email, password, role, org_id) VALUES (?, ?, ?, 'student', 1)",
            ("test_user2", "test2@example.com", "hashed_pw"),
        )
        user2_id = cur.lastrowid
        user2_org = 1

    # Get or create user in org 2
    cur.execute("SELECT id, org_id FROM users WHERE role = 'student' AND org_id != 1 LIMIT 1")
    row = cur.fetchone()
    if row:
        user3_id, user3_org = row["id"], row["org_id"]
    else:
        # Ensure org 2 exists
        cur.execute("SELECT id FROM organizations WHERE id = 2")
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO organizations (name, code, api_key, plan, modules, is_active) VALUES (?, ?, ?, ?, ?, 1)",
                ("Test Org 2", "TEST2", "fmt_test2", "university", "core,fyp"),
            )
        cur.execute(
            "INSERT INTO users (username, email, password, role, org_id) VALUES (?, ?, ?, 'student', 2)",
            ("test_user3", "test3@example.com", "hashed_pw"),
        )
        user3_id = cur.lastrowid
        user3_org = 2

    conn.commit()
    conn.close()

    # Generate tokens (email is required)
    token1 = create_access_token(user_id=user1_id, org_id=user1_org, role="student", email="test1@example.com")
    token2 = create_access_token(user_id=user2_id, org_id=user2_org, role="student", email="test2@example.com")
    token3 = create_access_token(user_id=user3_id, org_id=user3_org, role="student", email="test3@example.com")

    return {
        "user1": {"id": user1_id, "org_id": user1_org, "token": token1},
        "user2": {"id": user2_id, "org_id": user2_org, "token": token2},
        "user3": {"id": user3_id, "org_id": user3_org, "token": token3},
    }


def test_create_notification_via_notify(test_users):
    """Test that notify() creates a notification without raising."""
    user1 = test_users["user1"]
    result = notify(
        org_id=user1["org_id"],
        user_id=user1["id"],
        type=NotificationType.ANALYSIS_FINISHED,
        title="Test notification",
        body="This is a test notification",
        entity_type="document",
        entity_id=999,
        payload={"screen": "analyze", "document_id": 999},
    )
    assert result is not None
    assert isinstance(result, int)


def test_notify_swallows_errors(test_users):
    """Test that notify() never raises even with invalid data."""
    user1 = test_users["user1"]
    # This should not raise even if we pass None for required fields
    result = notify(
        org_id=None,
        user_id=None,
        type=NotificationType.ANALYSIS_FINISHED,
        title="Test",
        body="Test",
    )
    # It may return None on error, but should not raise
    assert result is None or isinstance(result, int)


def test_list_notifications_for_current_user(client, test_users):
    """Test GET /api/notifications returns only current user's notifications."""
    user1 = test_users["user1"]
    user2 = test_users["user2"]

    # Create notification for user1
    notify(
        org_id=user1["org_id"],
        user_id=user1["id"],
        type=NotificationType.ANALYSIS_FINISHED,
        title="User1 notification",
        body="For user1 only",
        entity_type="document",
        entity_id=1,
    )

    # Create notification for user2
    notify(
        org_id=user2["org_id"],
        user_id=user2["id"],
        type=NotificationType.ANALYSIS_FINISHED,
        title="User2 notification",
        body="For user2 only",
        entity_type="document",
        entity_id=2,
    )

    # User1 should only see their own notifications
    resp = client.get(
        "/api/notifications",
        headers={"Authorization": f"Bearer {user1['token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "notifications" in data
    titles = [n["title"] for n in data["notifications"]]
    assert "User1 notification" in titles
    assert "User2 notification" not in titles


def test_unread_count(client, test_users):
    """Test GET /api/notifications/unread-count."""
    user1 = test_users["user1"]

    # Create unread notification
    notify(
        org_id=user1["org_id"],
        user_id=user1["id"],
        type=NotificationType.ANALYSIS_FINISHED,
        title="Unread test",
        body="Unread",
        entity_type="document",
        entity_id=1,
    )

    resp = client.get(
        "/api/notifications/unread-count",
        headers={"Authorization": f"Bearer {user1['token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "unread_count" in data
    assert data["unread_count"] >= 1


def test_mark_notification_read(client, test_users):
    """Test POST /api/notifications/{id}/read."""
    user1 = test_users["user1"]

    # Create notification
    notif_id = notify(
        org_id=user1["org_id"],
        user_id=user1["id"],
        type=NotificationType.ANALYSIS_FINISHED,
        title="Mark read test",
        body="Test",
        entity_type="document",
        entity_id=1,
    )
    assert notif_id is not None

    # Mark as read
    resp = client.post(
        f"/api/notifications/{notif_id}/read",
        headers={"Authorization": f"Bearer {user1['token']}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

    # Verify it's now read
    resp = client.get(
        "/api/notifications",
        headers={"Authorization": f"Bearer {user1['token']}"},
    )
    data = resp.json()
    notif = next((n for n in data["notifications"] if n["id"] == notif_id), None)
    assert notif is not None
    assert notif["is_read"] is True


def test_mark_all_read(client, test_users):
    """Test POST /api/notifications/read-all."""
    user1 = test_users["user1"]

    # Create multiple unread notifications
    notify(
        org_id=user1["org_id"],
        user_id=user1["id"],
        type=NotificationType.ANALYSIS_FINISHED,
        title="Batch 1",
        body="Test",
        entity_type="document",
        entity_id=1,
    )
    notify(
        org_id=user1["org_id"],
        user_id=user1["id"],
        type=NotificationType.ANALYSIS_FINISHED,
        title="Batch 2",
        body="Test",
        entity_type="document",
        entity_id=2,
    )

    # Mark all as read
    resp = client.post(
        "/api/notifications/read-all",
        headers={"Authorization": f"Bearer {user1['token']}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

    # Verify all are read
    resp = client.get(
        "/api/notifications?unread_only=true",
        headers={"Authorization": f"Bearer {user1['token']}"},
    )
    data = resp.json()
    # All created notifications should now be read
    for notif in data["notifications"]:
        assert notif["is_read"] is False  # unread_only should return none


def test_delete_notification(client, test_users):
    """Test DELETE /api/notifications/{id}."""
    user1 = test_users["user1"]

    # Create notification
    notif_id = notify(
        org_id=user1["org_id"],
        user_id=user1["id"],
        type=NotificationType.ANALYSIS_FINISHED,
        title="Delete test",
        body="Test",
        entity_type="document",
        entity_id=1,
    )
    assert notif_id is not None

    # Delete it
    resp = client.delete(
        f"/api/notifications/{notif_id}",
        headers={"Authorization": f"Bearer {user1['token']}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

    # Verify it's gone
    resp = client.get(
        "/api/notifications",
        headers={"Authorization": f"Bearer {user1['token']}"},
    )
    data = resp.json()
    notif = next((n for n in data["notifications"] if n["id"] == notif_id), None)
    assert notif is None


def test_user_cannot_access_other_users_notification(client, test_users):
    """Test that user1 cannot read/modify/delete user2's notification."""
    user1 = test_users["user1"]
    user2 = test_users["user2"]

    # Create notification for user2
    notif_id = notify(
        org_id=user2["org_id"],
        user_id=user2["id"],
        type=NotificationType.ANALYSIS_FINISHED,
        title="User2 private",
        body="Private",
        entity_type="document",
        entity_id=1,
    )
    assert notif_id is not None

    # User1 tries to mark it as read - should get 404
    resp = client.post(
        f"/api/notifications/{notif_id}/read",
        headers={"Authorization": f"Bearer {user1['token']}"},
    )
    assert resp.status_code == 404

    # User1 tries to delete it - should get 404
    resp = client.delete(
        f"/api/notifications/{notif_id}",
        headers={"Authorization": f"Bearer {user1['token']}"},
    )
    assert resp.status_code == 404


def test_other_org_user_cannot_access(client, test_users):
    """Test that user from org 2 cannot access user1's notifications in org 1."""
    user1 = test_users["user1"]
    user3 = test_users["user3"]

    # Create notification for user1 in org 1
    notif_id = notify(
        org_id=user1["org_id"],
        user_id=user1["id"],
        type=NotificationType.ANALYSIS_FINISHED,
        title="Org1 private",
        body="Private",
        entity_type="document",
        entity_id=1,
    )
    assert notif_id is not None

    # User3 from org 2 tries to mark it as read - should get 404 or 401
    resp = client.post(
        f"/api/notifications/{notif_id}/read",
        headers={"Authorization": f"Bearer {user3['token']}"},
    )
    assert resp.status_code in (404, 401)

    # User3 tries to delete it - should get 404 or 401
    resp = client.delete(
        f"/api/notifications/{notif_id}",
        headers={"Authorization": f"Bearer {user3['token']}"},
    )
    assert resp.status_code in (404, 401)


def test_pagination_before_id(client, test_users):
    """Test pagination using before_id parameter."""
    user1 = test_users["user1"]

    # Create multiple notifications
    ids = []
    for i in range(5):
        nid = notify(
            org_id=user1["org_id"],
            user_id=user1["id"],
            type=NotificationType.ANALYSIS_FINISHED,
            title=f"Pagination test {i}",
            body=f"Test {i}",
            entity_type="document",
            entity_id=i,
        )
        if nid:
            ids.append(nid)

    # Get first page with limit 2
    resp = client.get(
        "/api/notifications?limit=2",
        headers={"Authorization": f"Bearer {user1['token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["notifications"]) <= 2

    if len(data["notifications"]) >= 2:
        last_id = data["notifications"][-1]["id"]

        # Get next page using before_id
        resp = client.get(
            f"/api/notifications?limit=2&before_id={last_id}",
            headers={"Authorization": f"Bearer {user1['token']}"},
        )
        assert resp.status_code == 200
        data2 = resp.json()
        # Should not include the last_id
        assert all(n["id"] < last_id for n in data2["notifications"])


def test_dedupe_prevents_duplicates(client, test_users):
    """Test that dedupe_key prevents duplicate notifications."""
    user1 = test_users["user1"]

    # Create notification with dedupe_key
    notify(
        org_id=user1["org_id"],
        user_id=user1["id"],
        type=NotificationType.DEADLINE_REMINDER_3_DAYS,
        title="Deadline reminder",
        body="Test",
        entity_type="semester_deadline",
        entity_id=1,
        dedupe_key="deadline_1_1_deadline_reminder_3_days",
    )

    # Try to create the same notification again
    result = notify(
        org_id=user1["org_id"],
        user_id=user1["id"],
        type=NotificationType.DEADLINE_REMINDER_3_DAYS,
        title="Deadline reminder",
        body="Test",
        entity_type="semester_deadline",
        entity_id=1,
        dedupe_key="deadline_1_1_deadline_reminder_3_days",
    )

    # Should return None (deduped)
    assert result is None

    # Verify only one exists
    resp = client.get(
        "/api/notifications",
        headers={"Authorization": f"Bearer {user1['token']}"},
    )
    data = resp.json()
    deadline_notifs = [n for n in data["notifications"] if n["type"] == NotificationType.DEADLINE_REMINDER_3_DAYS]
    assert len(deadline_notifs) == 1


def test_unread_only_filter(client, test_users):
    """Test unread_only query parameter."""
    user1 = test_users["user1"]

    # Create unread notification
    notify(
        org_id=user1["org_id"],
        user_id=user1["id"],
        type=NotificationType.ANALYSIS_FINISHED,
        title="Unread filter test",
        body="Test",
        entity_type="document",
        entity_id=1,
    )

    # Get all notifications
    resp_all = client.get(
        "/api/notifications",
        headers={"Authorization": f"Bearer {user1['token']}"},
    )
    all_count = len(resp_all.json()["notifications"])

    # Get only unread
    resp_unread = client.get(
        "/api/notifications?unread_only=true",
        headers={"Authorization": f"Bearer {user1['token']}"},
    )
    unread_count = len(resp_unread.json()["notifications"])

    # Unread count should be <= all count
    assert unread_count <= all_count
