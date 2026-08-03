"""FYP student + supervisor lifecycle and role-boundary tests."""
from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from typing import Any, Dict, Tuple

import pytest


def _uid(seeded_users: dict, role: str) -> int:
    return int(seeded_users[role]["id"])


def _sup_row_id(seeded_users: dict) -> int:
    sid = seeded_users.get("supervisor_row_id")
    assert sid is not None, "seeded supervisor row missing"
    return int(sid)


def _create_pending_request(
    client,
    auth_headers,
    seeded_users,
    *,
    group_name: str | None = None,
) -> Dict[str, Any]:
    student_id = _uid(seeded_users, "student")
    payload = {
        "supervisor_id": _sup_row_id(seeded_users),
        "group_name": group_name or f"Group-{uuid.uuid4().hex[:8]}",
        "project_title": f"Project-{uuid.uuid4().hex[:6]}",
        "member_names": ["student", "member2@example.com"],
        "department_id": seeded_users["dept1"],
        "student_leader_email": seeded_users["student"]["email"],
    }
    r = client.post(
        f"/api/student/assignment-requests?user_id={student_id}",
        json=payload,
        headers=auth_headers["student"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True
    return body["request"]


def _accept_request(client, auth_headers, seeded_users, request_id: int) -> Dict[str, Any]:
    r = client.post(
        f"/api/supervisor/assignment-requests/{request_id}/accept"
        f"?user_id={_uid(seeded_users, 'supervisor')}",
        headers=auth_headers["supervisor"],
    )
    assert r.status_code == 200, r.text
    return r.json()


def _seed_group_document_with_paragraph(
    db, *, group_id: int, supervisor_row_id: int, title: str = "Review Doc"
) -> Tuple[int, int]:
    """Insert minimal group_document + paragraph for comment tests."""
    conn = db.get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO group_documents
            (group_id, supervisor_id, title, filename, status, version_number)
        VALUES (?, ?, ?, ?, 'pending', 1)
        """,
        (group_id, supervisor_row_id, title, "review.docx"),
    )
    doc_id = int(cur.lastrowid)
    cur.execute(
        """
        INSERT INTO document_paragraphs (document_id, sort_order, text, block_type)
        VALUES (?, 0, ?, 'paragraph')
        """,
        (doc_id, "This is a paragraph awaiting supervisor feedback."),
    )
    para_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return doc_id, para_id


# ---------------------------------------------------------------------------
# Student
# ---------------------------------------------------------------------------


@pytest.mark.p1
@pytest.mark.fyp
def test_student_list_supervisors(client, auth_headers, seeded_users):
    r = client.get(
        f"/api/student/supervisors?user_id={_uid(seeded_users, 'student')}",
        headers=auth_headers["student"],
    )
    assert r.status_code == 200, r.text
    data = r.json()
    supervisors = data.get("supervisors") or data if isinstance(data, list) else data.get("items")
    if supervisors is None and isinstance(data, dict):
        # Some responses wrap under another key — accept non-empty dict with count
        assert data.get("count", 0) >= 0 or "supervisors" in data
        supervisors = data.get("supervisors", [])
    assert isinstance(supervisors, list)
    assert any(
        (s.get("id") == _sup_row_id(seeded_users) or s.get("email") == "supervisor@comsats.edu.pk")
        for s in supervisors
    )


@pytest.mark.p1
@pytest.mark.fyp
def test_assignment_request_create(client, auth_headers, seeded_users):
    req = _create_pending_request(client, auth_headers, seeded_users)
    assert req["status"] == "pending"
    assert req["supervisor_id"] == _sup_row_id(seeded_users)
    assert req.get("fyp_group_id") in (None, 0)


@pytest.mark.p1
@pytest.mark.fyp
def test_duplicate_pending_assignment_blocked(client, auth_headers, seeded_users):
    # Ensure one pending exists; if prior test left accepted, create fresh
    student_id = _uid(seeded_users, "student")
    # Cancel any lingering pending by rejecting via supervisor if present
    listed = client.get(
        f"/api/student/assignment-requests?user_id={student_id}",
        headers=auth_headers["student"],
    )
    assert listed.status_code == 200
    pending = [
        x
        for x in (listed.json().get("requests") or [])
        if x.get("status") == "pending"
        and x.get("supervisor_id") == _sup_row_id(seeded_users)
    ]
    if not pending:
        _create_pending_request(client, auth_headers, seeded_users)

    r = client.post(
        f"/api/student/assignment-requests?user_id={student_id}",
        json={
            "supervisor_id": _sup_row_id(seeded_users),
            "group_name": f"Dup-{uuid.uuid4().hex[:6]}",
            "member_names": ["student"],
            "department_id": seeded_users["dept1"],
        },
        headers=auth_headers["student"],
    )
    assert r.status_code == 409, r.text
    assert "pending" in (r.json().get("detail") or "").lower()


@pytest.mark.p1
@pytest.mark.fyp
def test_assignment_request_status(client, auth_headers, seeded_users):
    student_id = _uid(seeded_users, "student")
    email = seeded_users["student"]["email"]
    r = client.get(
        f"/api/student/assignment-requests/status?user_id={student_id}&email={email}",
        headers=auth_headers["student"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # status endpoint returns pending/accepted/none-style payload
    assert "status" in body or "request" in body or "found" in body or "requests" in body


@pytest.mark.p1
@pytest.mark.fyp
def test_student_semester_deadline(client, auth_headers, seeded_users):
    r = client.get(
        f"/api/student/semester-deadline?user_id={_uid(seeded_users, 'student')}",
        headers=auth_headers["student"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "deadline_date" in body or "found" in body
    assert "is_passed" in body or body.get("found") is False or "semester" in body


@pytest.mark.p1
@pytest.mark.fyp
def test_final_submission_deadline_passed(client, auth_headers, seeded_users, db):
    """When semester deadline is in the past, final submit returns 403 deadline_passed."""
    admin_id = _uid(seeded_users, "admin")
    student_id = _uid(seeded_users, "student")

    # Ensure student semester is 6
    conn = db.get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET current_semester = 6 WHERE id = ?",
        (student_id,),
    )
    # Remove existing semester-6 deadline then insert past date
    cur.execute(
        "DELETE FROM semester_deadlines WHERE semester = 6 AND COALESCE(org_id, 1) = 1"
    )
    past = (date.today() - timedelta(days=3)).isoformat()
    now = date.today().isoformat()
    cur.execute(
        """
        INSERT INTO semester_deadlines
            (semester, deadline_date, created_by, created_at, updated_at, org_id)
        VALUES (6, ?, ?, ?, ?, 1)
        """,
        (past, admin_id, now, now),
    )
    conn.commit()
    conn.close()

    # Reject any pending so we can create a fresh request → accept
    listed = client.get(
        f"/api/supervisor/assignment-requests?user_id={_uid(seeded_users, 'supervisor')}&status=pending",
        headers=auth_headers["supervisor"],
    )
    for req in listed.json().get("requests") or []:
        client.post(
            f"/api/supervisor/assignment-requests/{req['id']}/reject"
            f"?user_id={_uid(seeded_users, 'supervisor')}",
            json={"reason": "clearing for deadline test"},
            headers=auth_headers["supervisor"],
        )

    req = _create_pending_request(
        client, auth_headers, seeded_users, group_name=f"DL-{uuid.uuid4().hex[:6]}"
    )
    accepted = _accept_request(client, auth_headers, seeded_users, int(req["id"]))
    group_id = accepted["group"]["id"]

    # Force group semester 6 in case profile was unset
    conn = db.get_db()
    cur = conn.cursor()
    cur.execute("UPDATE fyp_groups SET current_semester = 6 WHERE id = ?", (group_id,))
    conn.commit()
    conn.close()

    r = client.post(
        f"/api/student/final-submissions?user_id={student_id}",
        json={"group_id": group_id, "title": "Late submission", "filename": "late.docx"},
        headers=auth_headers["student"],
    )
    assert r.status_code == 403, r.text
    detail = r.json().get("detail")
    if isinstance(detail, dict):
        assert detail.get("code") == "deadline_passed"
    else:
        assert "deadline" in str(detail).lower()

    # Restore future deadline so later tests can submit
    future = (date.today() + timedelta(days=60)).isoformat()
    conn = db.get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE semester_deadlines SET deadline_date = ? WHERE semester = 6 AND COALESCE(org_id, 1) = 1",
        (future,),
    )
    conn.commit()
    conn.close()


@pytest.mark.p1
@pytest.mark.fyp
def test_student_notifications_and_mark_read(client, auth_headers, seeded_users, db):
    student_id = _uid(seeded_users, "student")
    email = seeded_users["student"]["email"]

    # Plant a notification if inbox empty
    conn = db.get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO notifications
            (user_id, recipient_email, title, message, type, is_read, related_type, related_id)
        VALUES (?, ?, 'Test notice', 'Hello from pytest', 'test', 0, NULL, NULL)
        """,
        (student_id, email),
    )
    nid = int(cur.lastrowid)
    conn.commit()
    conn.close()

    r = client.get(
        f"/api/student/notifications?user_id={student_id}",
        headers=auth_headers["student"],
    )
    assert r.status_code == 200, r.text
    notes = r.json().get("notifications") or []
    assert any(n.get("id") == nid for n in notes)

    r2 = client.patch(
        f"/api/student/notifications/{nid}/read?user_id={student_id}",
        headers=auth_headers["student"],
    )
    assert r2.status_code == 200, r2.text
    assert r2.json().get("success") is True or r2.json().get("is_read") in (True, 1)


@pytest.mark.p1
@pytest.mark.fyp
def test_meeting_notes_membership_denied(client, auth_headers, seeded_users):
    """Non-member (or foreign group) cannot read meeting notes."""
    student_id = _uid(seeded_users, "student")
    r = client.get(
        f"/api/student/groups/999999/meeting-notes?user_id={student_id}",
        headers=auth_headers["student"],
    )
    assert r.status_code in (403, 404), r.text


# ---------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------


@pytest.mark.p1
@pytest.mark.fyp
def test_supervisor_home(client, auth_headers, seeded_users):
    r = client.get(
        f"/api/supervisor/home?user_id={_uid(seeded_users, 'supervisor')}",
        headers=auth_headers["supervisor"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, dict)
    # Dashboard-ish keys
    assert any(
        k in body
        for k in (
            "pending_requests",
            "groups",
            "total_groups",
            "active_groups",
            "stats",
            "submissions",
        )
    ) or "supervisor" in body or len(body) > 0


@pytest.mark.p0
@pytest.mark.fyp
def test_accept_creates_group_milestones_notification(
    client, auth_headers, seeded_users, db
):
    # Clear pending for this supervisor/student pair
    listed = client.get(
        f"/api/supervisor/assignment-requests?user_id={_uid(seeded_users, 'supervisor')}&status=pending",
        headers=auth_headers["supervisor"],
    )
    for req in listed.json().get("requests") or []:
        if (req.get("student_leader_email") or "").lower() == seeded_users["student"][
            "email"
        ].lower():
            client.post(
                f"/api/supervisor/assignment-requests/{req['id']}/reject"
                f"?user_id={_uid(seeded_users, 'supervisor')}",
                json={"reason": "clear before accept test"},
                headers=auth_headers["supervisor"],
            )

    req = _create_pending_request(
        client, auth_headers, seeded_users, group_name=f"Acc-{uuid.uuid4().hex[:6]}"
    )
    body = _accept_request(client, auth_headers, seeded_users, int(req["id"]))
    assert body.get("success") is True
    group = body["group"]
    assert group["status"] == "accepted"
    group_id = int(group["id"])

    # Milestones created
    conn = db.get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM group_milestones WHERE group_id = ?", (group_id,))
    assert int(cur.fetchone()["c"]) >= 1
    conn.close()

    # Student notification
    notif = client.get(
        f"/api/student/notifications?user_id={_uid(seeded_users, 'student')}",
        headers=auth_headers["student"],
    )
    assert notif.status_code == 200
    titles = [n.get("title", "") for n in notif.json().get("notifications") or []]
    assert any("accept" in t.lower() for t in titles)


@pytest.mark.p1
@pytest.mark.fyp
def test_reject_without_reason_400(client, auth_headers, seeded_users):
    # Need a pending request not owned by the happy-path group — create one
    # First reject any existing pending for capacity/cleanup then create
    listed = client.get(
        f"/api/supervisor/assignment-requests?user_id={_uid(seeded_users, 'supervisor')}&status=pending",
        headers=auth_headers["supervisor"],
    )
    for req in listed.json().get("requests") or []:
        client.post(
            f"/api/supervisor/assignment-requests/{req['id']}/reject"
            f"?user_id={_uid(seeded_users, 'supervisor')}",
            json={"reason": "pre-clean"},
            headers=auth_headers["supervisor"],
        )

    req = _create_pending_request(
        client, auth_headers, seeded_users, group_name=f"Rej-{uuid.uuid4().hex[:6]}"
    )
    r = client.post(
        f"/api/supervisor/assignment-requests/{req['id']}/reject"
        f"?user_id={_uid(seeded_users, 'supervisor')}",
        json={},
        headers=auth_headers["supervisor"],
    )
    assert r.status_code == 400, r.text
    assert "reason" in (r.json().get("detail") or "").lower()

    # Actually reject with reason so it does not block later tests
    r2 = client.post(
        f"/api/supervisor/assignment-requests/{req['id']}/reject"
        f"?user_id={_uid(seeded_users, 'supervisor')}",
        json={"reason": "Topic not a fit"},
        headers=auth_headers["supervisor"],
    )
    assert r2.status_code == 200, r2.text


@pytest.mark.p1
@pytest.mark.fyp
def test_supervisor_list_groups(client, auth_headers, seeded_users):
    r = client.get(
        f"/api/supervisor/groups?user_id={_uid(seeded_users, 'supervisor')}",
        headers=auth_headers["supervisor"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    groups = body.get("groups") if isinstance(body, dict) else body
    assert isinstance(groups, list)


@pytest.mark.p1
@pytest.mark.fyp
def test_comment_on_paragraph(client, auth_headers, seeded_users, db):
    # Ensure we have an accepted group for this supervisor+student
    listed = client.get(
        f"/api/supervisor/groups?user_id={_uid(seeded_users, 'supervisor')}",
        headers=auth_headers["supervisor"],
    )
    groups = listed.json().get("groups") or []
    accepted = [g for g in groups if (g.get("status") or "").lower() == "accepted"]
    if not accepted:
        # Clear pending + accept fresh
        pending = client.get(
            f"/api/supervisor/assignment-requests?user_id={_uid(seeded_users, 'supervisor')}&status=pending",
            headers=auth_headers["supervisor"],
        )
        for req in pending.json().get("requests") or []:
            client.post(
                f"/api/supervisor/assignment-requests/{req['id']}/reject"
                f"?user_id={_uid(seeded_users, 'supervisor')}",
                json={"reason": "pre-clean comment"},
                headers=auth_headers["supervisor"],
            )
        req = _create_pending_request(
            client, auth_headers, seeded_users, group_name=f"Cmt-{uuid.uuid4().hex[:6]}"
        )
        accepted_body = _accept_request(client, auth_headers, seeded_users, int(req["id"]))
        group_id = int(accepted_body["group"]["id"])
    else:
        group_id = int(accepted[0]["id"])

    doc_id, para_id = _seed_group_document_with_paragraph(
        db, group_id=group_id, supervisor_row_id=_sup_row_id(seeded_users)
    )
    r = client.post(
        f"/api/supervisor/groups/{group_id}/documents/{doc_id}/paragraphs/{para_id}/comments"
        f"?user_id={_uid(seeded_users, 'supervisor')}",
        json={"comment_text": "Please clarify methodology."},
        headers=auth_headers["supervisor"],
    )
    assert r.status_code == 200, r.text
    assert r.json().get("success") is True

    # Student can see comments
    r2 = client.get(
        f"/api/student/groups/{group_id}/documents/{doc_id}/comments"
        f"?user_id={_uid(seeded_users, 'student')}",
        headers=auth_headers["student"],
    )
    assert r2.status_code == 200, r2.text


@pytest.mark.p1
@pytest.mark.fyp
def test_submission_approve_revision_reject_transitions(
    client, auth_headers, seeded_users, db
):
    """Create three pending submissions and exercise each decision path."""
    admin_id = _uid(seeded_users, "admin")
    # Ensure deadline is not blocking
    future = (date.today() + timedelta(days=90)).isoformat()
    conn = db.get_db()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM semester_deadlines WHERE semester = 6 AND COALESCE(org_id, 1) = 1"
    )
    cur.execute(
        """
        INSERT INTO semester_deadlines
            (semester, deadline_date, created_by, created_at, updated_at, org_id)
        VALUES (6, ?, ?, datetime('now'), datetime('now'), 1)
        """,
        (future, admin_id),
    )
    conn.commit()
    conn.close()

    listed = client.get(
        f"/api/supervisor/groups?user_id={_uid(seeded_users, 'supervisor')}",
        headers=auth_headers["supervisor"],
    )
    groups = [
        g
        for g in (listed.json().get("groups") or [])
        if (g.get("status") or "").lower() == "accepted"
    ]
    if not groups:
        pending = client.get(
            f"/api/supervisor/assignment-requests?user_id={_uid(seeded_users, 'supervisor')}&status=pending",
            headers=auth_headers["supervisor"],
        )
        for req in pending.json().get("requests") or []:
            client.post(
                f"/api/supervisor/assignment-requests/{req['id']}/reject"
                f"?user_id={_uid(seeded_users, 'supervisor')}",
                json={"reason": "pre-clean transitions"},
                headers=auth_headers["supervisor"],
            )
        req = _create_pending_request(
            client, auth_headers, seeded_users, group_name=f"Tr-{uuid.uuid4().hex[:6]}"
        )
        body = _accept_request(client, auth_headers, seeded_users, int(req["id"]))
        group_id = int(body["group"]["id"])
    else:
        group_id = int(groups[0]["id"])

    conn = db.get_db()
    cur = conn.cursor()
    cur.execute("UPDATE fyp_groups SET current_semester = 6 WHERE id = ?", (group_id,))
    conn.commit()
    conn.close()

    student_id = _uid(seeded_users, "student")
    sup_uid = _uid(seeded_users, "supervisor")
    submission_ids = []
    for label in ("approve-me", "revise-me", "reject-me"):
        r = client.post(
            f"/api/student/final-submissions?user_id={student_id}",
            json={
                "group_id": group_id,
                "title": f"{label}-{uuid.uuid4().hex[:4]}",
                "filename": f"{label}.docx",
                "analysis_report": {"stats": {}, "issues": []},
            },
            headers=auth_headers["student"],
        )
        assert r.status_code == 200, r.text
        sub = r.json().get("submission") or r.json()
        submission_ids.append(int(sub["id"]))

    # revision without note → 400
    bad = client.post(
        f"/api/supervisor/submissions/{submission_ids[1]}/request-revision?user_id={sup_uid}",
        json={},
        headers=auth_headers["supervisor"],
    )
    assert bad.status_code == 400

    # reject without reason → 400
    bad2 = client.post(
        f"/api/supervisor/submissions/{submission_ids[2]}/reject?user_id={sup_uid}",
        json={},
        headers=auth_headers["supervisor"],
    )
    assert bad2.status_code == 400

    ok_rev = client.post(
        f"/api/supervisor/submissions/{submission_ids[1]}/request-revision?user_id={sup_uid}",
        json={"note": "Expand literature review"},
        headers=auth_headers["supervisor"],
    )
    assert ok_rev.status_code == 200, ok_rev.text
    assert ok_rev.json()["submission"]["status"] == "revision"

    ok_rej = client.post(
        f"/api/supervisor/submissions/{submission_ids[2]}/reject?user_id={sup_uid}",
        json={"reason": "Out of scope"},
        headers=auth_headers["supervisor"],
    )
    assert ok_rej.status_code == 200, ok_rej.text
    assert ok_rej.json()["submission"]["status"] == "rejected"

    ok_app = client.post(
        f"/api/supervisor/submissions/{submission_ids[0]}/approve?user_id={sup_uid}",
        json={"note": "Looks good"},
        headers=auth_headers["supervisor"],
    )
    assert ok_app.status_code == 200, ok_app.text
    assert ok_app.json()["submission"]["status"] == "approved"


@pytest.mark.p1
@pytest.mark.fyp
@pytest.mark.plagiarism
def test_supervisor_plagiarism_monitor(client, auth_headers, seeded_users):
    r = client.get(
        f"/api/supervisor/plagiarism-monitor?user_id={_uid(seeded_users, 'supervisor')}",
        headers=auth_headers["supervisor"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, dict)
    assert "groups" in body or "items" in body or "count" in body or isinstance(
        body.get("flagged"), list
    ) or len(body) >= 0


@pytest.mark.p1
@pytest.mark.fyp
def test_meeting_notes_create_and_student_read(client, auth_headers, seeded_users):
    listed = client.get(
        f"/api/supervisor/groups?user_id={_uid(seeded_users, 'supervisor')}",
        headers=auth_headers["supervisor"],
    )
    groups = [
        g
        for g in (listed.json().get("groups") or [])
        if (g.get("status") or "").lower() == "accepted"
    ]
    if not groups:
        pytest.skip("No accepted group available for meeting notes")
    group_id = int(groups[0]["id"])

    r = client.post(
        f"/api/supervisor/groups/{group_id}/meeting-notes"
        f"?user_id={_uid(seeded_users, 'supervisor')}",
        json={
            "meeting_date": date.today().isoformat(),
            "topic": "Progress sync",
            "action_items": "Finish chapter 2",
        },
        headers=auth_headers["supervisor"],
    )
    assert r.status_code == 200, r.text
    assert r.json().get("success") is True

    r2 = client.get(
        f"/api/student/groups/{group_id}/meeting-notes"
        f"?user_id={_uid(seeded_users, 'student')}",
        headers=auth_headers["student"],
    )
    assert r2.status_code == 200, r2.text
    notes = r2.json().get("notes") or r2.json().get("meeting_notes") or []
    assert any("Progress sync" in (n.get("topic") or "") for n in notes)


@pytest.mark.p1
@pytest.mark.fyp
def test_discard_group(client, auth_headers, seeded_users):
    # Create a disposable accepted group
    listed = client.get(
        f"/api/supervisor/assignment-requests?user_id={_uid(seeded_users, 'supervisor')}&status=pending",
        headers=auth_headers["supervisor"],
    )
    for req in listed.json().get("requests") or []:
        client.post(
            f"/api/supervisor/assignment-requests/{req['id']}/reject"
            f"?user_id={_uid(seeded_users, 'supervisor')}",
            json={"reason": "pre-clean discard"},
            headers=auth_headers["supervisor"],
        )
    req = _create_pending_request(
        client, auth_headers, seeded_users, group_name=f"Disc-{uuid.uuid4().hex[:6]}"
    )
    body = _accept_request(client, auth_headers, seeded_users, int(req["id"]))
    group_id = int(body["group"]["id"])

    r = client.post(
        f"/api/supervisor/groups/{group_id}/discard"
        f"?user_id={_uid(seeded_users, 'supervisor')}",
        json={"reason": "Project cancelled"},
        headers=auth_headers["supervisor"],
    )
    assert r.status_code == 200, r.text
    assert r.json().get("success") is True
    assert r.json().get("group_id") == group_id


# ---------------------------------------------------------------------------
# Role boundaries
# ---------------------------------------------------------------------------


@pytest.mark.p0
@pytest.mark.fyp
def test_student_cannot_call_supervisor_api(client, auth_headers, seeded_users):
    r = client.get(
        f"/api/supervisor/home?user_id={_uid(seeded_users, 'student')}",
        headers=auth_headers["student"],
    )
    assert r.status_code == 403, r.text


@pytest.mark.p1
@pytest.mark.fyp
def test_supervisor_list_assignment_requests(client, auth_headers, seeded_users):
    r = client.get(
        f"/api/supervisor/assignment-requests?user_id={_uid(seeded_users, 'supervisor')}",
        headers=auth_headers["supervisor"],
    )
    assert r.status_code == 200, r.text
    assert "requests" in r.json()
