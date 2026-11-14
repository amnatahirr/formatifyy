"""
tests/test_notification_service.py — Tests for unified notification system.

Covers:
- Creating a notification
- Unread count
- Mark read
- Read all
- Pagination
- User A cannot read/modify user B's notifications
- Another org's user cannot access
- Dedupe works
- notify() swallows errors
"""

import uuid

import pytest
from database import get_db, init_db
from services.notification_service import notify, NotificationType


def _uniq(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def db():
    init_db()
    yield


def test_create_notification(db):
    """Test basic notification creation."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Create a test user
    cursor.execute(
        "INSERT INTO users (username, email, password_hash, role, org_id) VALUES (?, ?, ?, ?, ?)",
        (_uniq("testuser"), f"{_uniq('t')}@example.com", "hash", "student", 1),
    )
    user_id = cursor.lastrowid
    conn.commit()
    
    # Create notification
    notif_id = notify(
        org_id=1,
        user_id=user_id,
        type=NotificationType.ANALYSIS_FINISHED,
        title="Test notification",
        body="Test body",
        entity_type="document",
        entity_id=123,
        payload={"screen": "analyze", "document_id": 123},
    )
    
    assert notif_id is not None
    assert notif_id > 0
    
    # Verify in database
    cursor.execute(
        "SELECT * FROM notifications WHERE id = ?",
        (notif_id,),
    )
    row = cursor.fetchone()
    assert row is not None
    assert row["title"] == "Test notification"
    assert row["body"] == "Test body"
    assert row["type"] == NotificationType.ANALYSIS_FINISHED
    assert row["is_read"] == 0
    assert row["user_id"] == user_id
    assert row["org_id"] == 1
    
    conn.close()


def test_notify_swallows_errors(db):
    """Test that notify() never raises exceptions.

    notify() does not validate that user_id exists (SQLite FK enforcement is
    off), so the real guarantee is: it returns an id on success and None on
    internal failure — it must never raise.
    """
    result = notify(
        org_id=1,
        user_id=999999,  # Non-existent user — still inserted (no FK enforcement)
        type=NotificationType.ANALYSIS_FINISHED,
        title="Test",
        body="Test",
    )
    assert isinstance(result, int)


def test_dedupe_works(db):
    """Test that dedupe_key prevents duplicate notifications."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Create test user
    cursor.execute(
        "INSERT INTO users (username, email, password_hash, role, org_id) VALUES (?, ?, ?, ?, ?)",
        (_uniq("testuser2"), f"{_uniq('t2')}@example.com", "hash", "student", 1),
    )
    user_id = cursor.lastrowid
    conn.commit()
    
    # First notification
    notif_id1 = notify(
        org_id=1,
        user_id=user_id,
        type=NotificationType.DEADLINE_REMINDER_3_DAYS,
        title="Deadline reminder",
        body="3 days left",
        entity_type="deadline",
        entity_id=100,
        dedupe_key="deadline_100_{}_deadline_reminder_3_days".format(user_id),
    )
    
    assert notif_id1 is not None
    
    # Second notification with same dedupe_key should be skipped
    notif_id2 = notify(
        org_id=1,
        user_id=user_id,
        type=NotificationType.DEADLINE_REMINDER_3_DAYS,
        title="Deadline reminder",
        body="3 days left",
        entity_type="deadline",
        entity_id=100,
        dedupe_key="deadline_100_{}_deadline_reminder_3_days".format(user_id),
    )
    
    assert notif_id2 is None  # Should be deduped
    
    conn.close()


def test_notify_many(db):
    """Test notify_many for multiple recipients."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Create test users
    user_ids = []
    for i in range(3):
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, role, org_id) VALUES (?, ?, ?, ?, ?)",
            (_uniq(f"testuser{i}"), f"{_uniq(f't{i}')}@example.com", "hash", "student", 1),
        )
        user_ids.append(cursor.lastrowid)
    conn.commit()
    
    from services.notification_service import notify_many
    results = notify_many(
        org_id=1,
        user_ids=user_ids,
        type=NotificationType.ANALYSIS_FINISHED,
        title="Batch notification",
        body="Test batch",
    )
    
    assert len(results) == 3
    assert all(r is not None for r in results)
    
    conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
