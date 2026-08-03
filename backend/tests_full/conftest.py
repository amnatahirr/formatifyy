"""
Shared fixtures for Formatify backend/tests_full.

Isolates SQLite to a temp DB, stubs vision preload, and seeds helpers for
org/users/templates/sample documents.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Generator, Iterator
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap — tests_full lives under backend/
# ---------------------------------------------------------------------------
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("SUPER_ADMIN_KEY", "super_secret_master_key_here")
os.environ.setdefault("JWT_SECRET", "formatify_dev_jwt_secret_change_me")
# Keep plagiarism/web/LLM optional for unit suite speed
os.environ.setdefault("PLAGIARISM_ENABLE_WEB", "false")
os.environ.setdefault("PLAGIARISM_LLM_PATTERNS", "false")

RESULTS_DIR = Path(__file__).resolve().parent / "metrics" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Session-scoped scratch for uploaded artifacts created during tests
_SESSION_UPLOADS: Path | None = None


def _bootstrap_templates_with_org_id(database) -> None:
    """
    Work around BUG in database.init_db seed order:
    freeform placeholder INSERT references templates.org_id before the
    organizations migration adds that column on a brand-new SQLite file.
    """
    conn = database.get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS universities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            country TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'student',
            university_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (university_id) REFERENCES universities(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            university_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            required_sections TEXT,
            formatting_rules TEXT,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            org_id INTEGER DEFAULT 1,
            FOREIGN KEY (university_id) REFERENCES universities(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
        """
    )
    conn.commit()
    conn.close()


def _git_commit() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(BACKEND_ROOT.parent),
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except Exception:
        return "unknown"


@pytest.fixture(scope="session")
def git_commit() -> str:
    return _git_commit()


@pytest.fixture(scope="session")
def test_db_path(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("formatify_db") / "test_formatify.db"


@pytest.fixture(scope="session")
def upload_root(tmp_path_factory) -> Path:
    global _SESSION_UPLOADS
    root = tmp_path_factory.mktemp("uploads")
    (root / "working").mkdir(parents=True, exist_ok=True)
    (root / "branding").mkdir(parents=True, exist_ok=True)
    (root / "images").mkdir(parents=True, exist_ok=True)
    _SESSION_UPLOADS = root
    return root


@pytest.fixture(scope="session")
def app_and_db(test_db_path: Path, upload_root: Path):
    """
    Patch DATABASE_URL + UPLOAD_DIR, init a fresh DB, import app once.
    Vision preload is stubbed so TestClient startup stays fast.
    """
    import database

    database.DATABASE_URL = str(test_db_path)

    # BUG: database.init_db() inserts __freeform_placeholder__ with org_id
    # before _ensure_organizations_schema() adds the column. Pre-create
    # templates with org_id so CREATE TABLE IF NOT EXISTS keeps our schema.
    _bootstrap_templates_with_org_id(database)

    database.init_db()

    # Import after DB path is patched so subsequent get_db() hits the test DB.
    import main as main_mod

    main_mod.UPLOAD_DIR = str(upload_root)
    os.makedirs(main_mod.UPLOAD_DIR, exist_ok=True)
    os.makedirs(os.path.join(main_mod.UPLOAD_DIR, "working"), exist_ok=True)
    # Point outputs at temp too
    if hasattr(main_mod, "OUTPUT_DIR"):
        out = upload_root / "outputs"
        out.mkdir(exist_ok=True)
        main_mod.OUTPUT_DIR = str(out)

    # Ensure DB URL still points at test DB after imports that may re-bind
    database.DATABASE_URL = str(test_db_path)

    with patch("functions.local_vision.preload_models", return_value=None):
        yield main_mod.app, database

    # Cleanup handled by tmp_path_factory


@pytest.fixture(scope="session")
def client(app_and_db) -> Iterator[Any]:
    from fastapi.testclient import TestClient

    app, _db = app_and_db
    with patch("functions.local_vision.preload_models", return_value=None):
        with TestClient(app) as c:
            yield c


@pytest.fixture(scope="session")
def db(app_and_db):
    _app, database = app_and_db
    return database


# ---------------------------------------------------------------------------
# Seeded identity helpers (from init_db seeds + extras)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def seeded_users(db) -> Dict[str, Any]:
    """Resolve seeded COMSATS users + create a second-org for isolation tests."""
    conn = db.get_db()
    cur = conn.cursor()

    def _user(email: str) -> dict:
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        assert row, f"missing seed user {email}"
        return dict(row)

    admin = _user("admin@comsats.edu.pk")
    student = _user("student@comsats.edu.pk")
    supervisor = _user("supervisor@comsats.edu.pk")

    # Second org for multi-tenancy tests (idempotent)
    cur.execute("SELECT id FROM organizations WHERE code = ?", ("TEST-ORG-B",))
    row = cur.fetchone()
    if not row:
        cur.execute(
            """
            INSERT INTO organizations
            (name, code, type, api_key, plan, modules, documents_used, documents_limit, is_active, primary_color)
            VALUES (?, ?, ?, ?, ?, ?, 0, 999999, 1, ?)
            """,
            (
                "Test Org B",
                "TEST-ORG-B",
                "university",
                "fmt_live_test_org_b",
                "university",
                "core,fyp",
                "#336699",
            ),
        )
        conn.commit()
        org_b_id = int(cur.lastrowid)
    else:
        org_b_id = int(row["id"])

    # Core-only org (no FYP) for module gating
    cur.execute("SELECT id FROM organizations WHERE code = ?", ("CORE-ONLY",))
    row = cur.fetchone()
    if not row:
        cur.execute(
            """
            INSERT INTO organizations
            (name, code, type, api_key, plan, modules, documents_used, documents_limit, is_active, primary_color)
            VALUES (?, ?, ?, ?, ?, ?, 0, 100, 1, ?)
            """,
            (
                "Core Only Org",
                "CORE-ONLY",
                "company",
                "fmt_live_core_only",
                "starter",
                "core",
                "#112233",
            ),
        )
        conn.commit()
        core_org_id = int(cur.lastrowid)
    else:
        core_org_id = int(row["id"])

    # Inactive org
    cur.execute("SELECT id FROM organizations WHERE code = ?", ("INACTIVE-ORG",))
    row = cur.fetchone()
    if not row:
        cur.execute(
            """
            INSERT INTO organizations
            (name, code, type, api_key, plan, modules, documents_used, documents_limit, is_active, primary_color)
            VALUES (?, ?, ?, ?, ?, ?, 0, 999999, 0, ?)
            """,
            (
                "Inactive Org",
                "INACTIVE-ORG",
                "university",
                "fmt_live_inactive",
                "university",
                "core,fyp",
                "#000000",
            ),
        )
        conn.commit()
        inactive_org_id = int(cur.lastrowid)
    else:
        inactive_org_id = int(row["id"])

    # Limited org (documents_limit already used)
    cur.execute("SELECT id FROM organizations WHERE code = ?", ("LIMIT-ORG",))
    row = cur.fetchone()
    if not row:
        cur.execute(
            """
            INSERT INTO organizations
            (name, code, type, api_key, plan, modules, documents_used, documents_limit, is_active, primary_color)
            VALUES (?, ?, ?, ?, ?, ?, 5, 5, 1, ?)
            """,
            (
                "Limit Org",
                "LIMIT-ORG",
                "university",
                "fmt_live_limit",
                "university",
                "core,fyp",
                "#aa0000",
            ),
        )
        conn.commit()
        limit_org_id = int(cur.lastrowid)
    else:
        limit_org_id = int(row["id"])
        cur.execute(
            "UPDATE organizations SET documents_used = 5, documents_limit = 5 WHERE id = ?",
            (limit_org_id,),
        )
        conn.commit()

    # Ensure org B has a department + student
    cur.execute(
        "SELECT id FROM departments WHERE org_id = ? LIMIT 1", (org_b_id,)
    )
    drow = cur.fetchone()
    if not drow:
        cur.execute(
            """
            INSERT INTO departments (name, code, min_members, max_members, max_groups_per_supervisor, org_id)
            VALUES ('CS-B', 'CSB', 1, 4, 5, ?)
            """,
            (org_b_id,),
        )
        conn.commit()
        dept_b = int(cur.lastrowid)
    else:
        dept_b = int(drow["id"])

    cur.execute(
        "SELECT id FROM users WHERE email = ? AND org_id = ?",
        ("student_b@test.org", org_b_id),
    )
    urow = cur.fetchone()
    if not urow:
        cur.execute(
            """
            INSERT INTO users (username, email, password_hash, role, university_id, department_id, org_id, current_semester)
            VALUES (?, ?, ?, 'student', 1, ?, ?, 6)
            """,
            (
                "student_b",
                "student_b@test.org",
                db.hash_password("student123"),
                dept_b,
                org_b_id,
            ),
        )
        conn.commit()
        student_b_id = int(cur.lastrowid)
    else:
        student_b_id = int(urow["id"])

    # Template in default org (non-freeform)
    cur.execute(
        """
        SELECT id FROM templates
        WHERE org_id = 1 AND name != '__freeform_placeholder__'
        ORDER BY id LIMIT 1
        """
    )
    trow = cur.fetchone()
    template_id = int(trow["id"]) if trow else None
    if template_id is None:
        cur.execute(
            """
            INSERT INTO templates
            (university_id, department_id, name, description, required_sections, formatting_rules, created_by, org_id)
            VALUES (1, NULL, 'Test Template', 'for tests', ?, ?, ?, 1)
            """,
            (
                json.dumps(["Introduction", "Conclusion"]),
                json.dumps({"fonts": {"body": "Times New Roman"}, "margins": {}}),
                admin["id"],
            ),
        )
        conn.commit()
        template_id = int(cur.lastrowid)

    cur.execute("SELECT * FROM organizations WHERE id = 1")
    org1 = dict(cur.fetchone())
    cur.execute("SELECT * FROM organizations WHERE id = ?", (org_b_id,))
    org_b = dict(cur.fetchone())
    cur.execute("SELECT * FROM organizations WHERE id = ?", (core_org_id,))
    org_core = dict(cur.fetchone())

    cur.execute("SELECT id FROM departments WHERE org_id = 1 ORDER BY id LIMIT 1")
    dept1 = int(cur.fetchone()["id"])

    cur.execute("SELECT id FROM supervisors WHERE org_id = 1 ORDER BY id LIMIT 1")
    srow = cur.fetchone()
    supervisor_row_id = int(srow["id"]) if srow else None

    conn.close()
    return {
        "admin": admin,
        "student": student,
        "supervisor": supervisor,
        "supervisor_row_id": supervisor_row_id,
        "student_b_id": student_b_id,
        "org1": org1,
        "org_b": org_b,
        "org_core": org_core,
        "org_b_id": org_b_id,
        "core_org_id": core_org_id,
        "inactive_org_id": inactive_org_id,
        "limit_org_id": limit_org_id,
        "dept1": dept1,
        "dept_b": dept_b,
        "template_id": template_id,
        "super_admin_key": os.environ["SUPER_ADMIN_KEY"],
    }


@pytest.fixture
def auth_headers(seeded_users, client) -> Dict[str, Dict[str, str]]:
    """Login each seeded role and return Authorization header maps."""
    from auth_jwt import create_access_token

    def _hdr(user: dict, org: dict) -> Dict[str, str]:
        token = create_access_token(
            user_id=int(user["id"]),
            org_id=int(org["id"]),
            role=user["role"],
            email=user["email"],
            org_code=org["code"],
        )
        return {
            "Authorization": f"Bearer {token}",
            "X-Org-Code": org["code"],
        }

    return {
        "admin": _hdr(seeded_users["admin"], seeded_users["org1"]),
        "student": _hdr(seeded_users["student"], seeded_users["org1"]),
        "supervisor": _hdr(seeded_users["supervisor"], seeded_users["org1"]),
        "org_code": {"X-Org-Code": seeded_users["org1"]["code"]},
        "super_admin": {"X-Super-Admin-Key": seeded_users["super_admin_key"]},
    }


# ---------------------------------------------------------------------------
# Sample file fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_txt_bytes() -> bytes:
    return (
        b"Introduction\n\n"
        b"This is a sample document for Formatify automated tests.\n\n"
        b"Methodology\n\n"
        b"We used a controlled laboratory setting.\n\n"
        b"Conclusion\n\n"
        b"Results confirm the hypothesis.\n"
    )


@pytest.fixture
def sample_txt_file(sample_txt_bytes) -> tuple[str, io.BytesIO, str]:
    return ("sample.txt", io.BytesIO(sample_txt_bytes), "text/plain")


@pytest.fixture
def sample_docx_bytes() -> bytes:
    """Minimal DOCX with headings for TOC / analyze flows."""
    from docx import Document

    buf = io.BytesIO()
    doc = Document()
    doc.add_heading("Introduction", level=1)
    doc.add_paragraph(
        "This paragraph discusses the background of the research project in detail."
    )
    doc.add_heading("Methodology", level=1)
    doc.add_paragraph("First step of the approach.")
    doc.add_paragraph("Second step of the approach.")
    doc.add_paragraph("Third step of the approach.")
    doc.add_heading("Conclusion", level=1)
    doc.add_paragraph("The study concludes with promising outcomes.")
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture
def sample_docx_file(sample_docx_bytes) -> tuple[str, io.BytesIO, str]:
    return (
        "sample.docx",
        io.BytesIO(sample_docx_bytes),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@pytest.fixture
def grammar_error_txt() -> bytes:
    """Planted grammar/spelling errors for accuracy fixtures."""
    return (
        b"Introduction\n\n"
        b"This sentense has a mispelled word and bad grammar are present.\n\n"
        b"He go to the lab yesterday and collect data.\n"
    )


# ---------------------------------------------------------------------------
# Performance / accuracy result helpers
# ---------------------------------------------------------------------------

_SESSION_PERF_ROWS: list[dict] = []
_SESSION_ACC_ROWS: list[dict] = []


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Also maintain a rolling JSON array file for convenience
    history_path = path
    history: list = []
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
            if not isinstance(history, list):
                history = []
        except Exception:
            history = []
    history.append(record)
    history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")


def record_performance(row: dict) -> None:
    row = {**row, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "git_commit": _git_commit()}
    _SESSION_PERF_ROWS.append(row)
    append_jsonl(RESULTS_DIR / "performance_report.json", row)


def record_accuracy(row: dict) -> None:
    row = {**row, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "git_commit": _git_commit()}
    _SESSION_ACC_ROWS.append(row)
    append_jsonl(RESULTS_DIR / "accuracy_report.json", row)


@pytest.fixture
def perf_recorder():
    return record_performance


@pytest.fixture
def acc_recorder():
    return record_accuracy


@pytest.fixture
def measure_resources():
    """Context-manager factory: peak RSS delta + CPU% around a callable."""
    import tracemalloc

    import psutil

    def _wrap(fn, *args, **kwargs):
        proc = psutil.Process(os.getpid())
        # Prime cpu_percent
        proc.cpu_percent(interval=None)
        tracemalloc.start()
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        elapsed = time.perf_counter() - t0
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        cpu = proc.cpu_percent(interval=0.05)
        mem_mb = peak / (1024 * 1024)
        return result, {
            "elapsed_s": elapsed,
            "peak_memory_mb": round(mem_mb, 3),
            "cpu_percent": cpu,
        }

    return _wrap


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print combined Accuracy + Performance summary when those markers ran."""
    if not _SESSION_ACC_ROWS and not _SESSION_PERF_ROWS:
        return
    tr = terminalreporter
    tr.write_sep("=", "Accuracy + Performance Summary")
    if _SESSION_ACC_ROWS:
        tr.write_line("Accuracy runs this session:")
        for row in _SESSION_ACC_ROWS:
            tr.write_line(
                f"  {row.get('feature','?'):20s}  F1={row.get('f1',0):.3f}  "
                f"P={row.get('precision',0):.3f}  R={row.get('recall',0):.3f}  "
                f"TP={row.get('tp')} FP={row.get('fp')} FN={row.get('fn')}"
            )
    if _SESSION_PERF_ROWS:
        tr.write_line("Performance runs this session:")
        for row in _SESSION_PERF_ROWS:
            tr.write_line(
                f"  {row.get('test','?'):40s}  mean={row.get('mean_s','n/a')}s  "
                f"p95={row.get('p95_s','n/a')}s  mem={row.get('peak_memory_mb','n/a')}MB  "
                f"cpu={row.get('cpu_percent','n/a')}%"
            )
    tr.write_line(f"Reports: {RESULTS_DIR}")


# Trivial sanity so collection works even if markers unused
def pytest_configure(config):
    # markers already in pytest.ini; nothing else required
    pass
