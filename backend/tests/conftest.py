"""Shared pytest setup for backend/tests.

Redirects database.DATABASE_URL to a throwaway SQLite file BEFORE any test
module imports `database`/`main`, so the suite never writes to the real
formatify.db. Test modules that need their own isolated DB (e.g.
test_missing_headings.py) re-assign database.DATABASE_URL in their fixtures,
which still wins because fixtures run after this import.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import database  # noqa: E402

_TMP_DB_DIR = Path(tempfile.mkdtemp(prefix="formatify_pytest_"))
database.DATABASE_URL = str(_TMP_DB_DIR / "formatify_test.db")
