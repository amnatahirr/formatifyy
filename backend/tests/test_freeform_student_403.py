"""
Quick 403 check: student role must be rejected on freeform routes.
Uses FastAPI TestClient — no live server required.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from database import get_db, init_db  # noqa: E402
from main import app  # noqa: E402


def _student_user_id() -> int:
    init_db()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE LOWER(role) = 'student' ORDER BY id LIMIT 1")
    row = cur.fetchone()
    if not row:
        cur.execute(
            """
            INSERT INTO users (username, email, password_hash, role, university_id, org_id)
            VALUES ('freeform_student_test', 'freeform_student_test@example.com', 'x', 'student', 1, 1)
            """
        )
        conn.commit()
        uid = int(cur.lastrowid)
    else:
        uid = int(row["id"])
    conn.close()
    return uid


def main() -> None:
    student_id = _student_user_id()
    client = TestClient(app)
    failures: list[str] = []

    # 1) upload-text-freeform
    r1 = client.post(
        f"/api/documents/upload-text-freeform?user_id={student_id}",
        json={"content": "student should not freeform"},
    )
    if r1.status_code != 403:
        failures.append(f"upload-text-freeform got {r1.status_code}: {r1.text}")
    else:
        print(f"OK upload-text-freeform -> 403 ({r1.json()})")

    # 2) upload-freeform (multipart)
    r2 = client.post(
        f"/api/documents/upload-freeform?user_id={student_id}",
        files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    if r2.status_code != 403:
        failures.append(f"upload-freeform got {r2.status_code}: {r2.text}")
    else:
        print(f"OK upload-freeform -> 403 ({r2.json()})")

    # 3) analyze-freeform (doc need not exist — role check runs first)
    r3 = client.get(f"/api/documents/analyze-freeform/1?user_id={student_id}")
    if r3.status_code != 403:
        failures.append(f"analyze-freeform got {r3.status_code}: {r3.text}")
    else:
        print(f"OK analyze-freeform -> 403 ({r3.json()})")

    if failures:
        print("FAILED:")
        for f in failures:
            print(" -", f)
        sys.exit(1)
    print(f"All three freeform routes returned 403 for student user_id={student_id}")


if __name__ == "__main__":
    main()
