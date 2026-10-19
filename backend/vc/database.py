"""
vc/database.py — SQLite tables for the collaboration / version-control module.
"""

from __future__ import annotations

import secrets

from database import get_db


def _ensure_column(cursor, table: str, column: str, ddl: str) -> None:
    """Idempotent ALTER TABLE ADD COLUMN."""
    cursor.execute(f"PRAGMA table_info({table})")
    cols = {row[1] for row in cursor.fetchall()}
    if column not in cols:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_vc_tables() -> None:
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS collaboration_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            template_id INTEGER NOT NULL,
            created_by INTEGER NOT NULL,
            invite_code TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'active',
            merged_document_id INTEGER,
            merged_file_path TEXT,
            last_merge_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (template_id) REFERENCES templates(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT DEFAULT 'editor',
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_id, user_id),
            FOREIGN KEY (project_id) REFERENCES collaboration_projects(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            section_id TEXT NOT NULL,
            section_name TEXT NOT NULL,
            template_order INTEGER NOT NULL,
            heading_level INTEGER DEFAULT 1,
            UNIQUE(project_id, section_id),
            FOREIGN KEY (project_id) REFERENCES collaboration_projects(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS section_commits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            section_id TEXT NOT NULL,
            author_id INTEGER NOT NULL,
            author_name TEXT NOT NULL,
            version_number INTEGER NOT NULL,
            content TEXT NOT NULL,
            commit_type TEXT DEFAULT 'save',
            parent_commit_id INTEGER,
            message TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES collaboration_projects(id),
            FOREIGN KEY (author_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_merges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            initiated_by INTEGER NOT NULL,
            status TEXT DEFAULT 'detecting',
            merged_file_path TEXT,
            document_id INTEGER,
            analysis_report TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES collaboration_projects(id),
            FOREIGN KEY (initiated_by) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS merge_conflicts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merge_id INTEGER NOT NULL,
            conflict_type TEXT NOT NULL,
            section_id TEXT,
            section_name TEXT,
            related_section_id TEXT,
            related_section_name TEXT,
            details TEXT NOT NULL,
            resolution_content TEXT,
            resolved_by INTEGER,
            resolved_at TIMESTAMP,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (merge_id) REFERENCES project_merges(id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_section_commits_lookup
        ON section_commits(project_id, section_id, created_at)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_merge_conflicts_merge
        ON merge_conflicts(merge_id, status)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS section_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            section_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            uploaded_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES collaboration_projects(id),
            FOREIGN KEY (uploaded_by) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_section_images_lookup
        ON section_images(project_id, section_id)
    """)

    # Project-level activity (document uploads / new versions), independent of sections.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            author_name TEXT NOT NULL,
            action TEXT NOT NULL,
            filename TEXT,
            details TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES collaboration_projects(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_project_activity_lookup
        ON project_activity(project_id, created_at)
    """)

    # Add base_document_path column if missing (existing DBs)
    cursor.execute("PRAGMA table_info(collaboration_projects)")
    cols = {row[1] for row in cursor.fetchall()}
    if "base_document_path" not in cols:
        cursor.execute(
            "ALTER TABLE collaboration_projects ADD COLUMN base_document_path TEXT"
        )
    if "base_document_id" not in cols:
        cursor.execute(
            "ALTER TABLE collaboration_projects ADD COLUMN base_document_id INTEGER"
        )
    if "shared_snapshot_path" not in cols:
        cursor.execute(
            "ALTER TABLE collaboration_projects ADD COLUMN shared_snapshot_path TEXT"
        )
    if "base_document_filename" not in cols:
        cursor.execute(
            "ALTER TABLE collaboration_projects ADD COLUMN base_document_filename TEXT"
        )

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_member_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            document_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_id, user_id),
            FOREIGN KEY (project_id) REFERENCES collaboration_projects(id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (document_id) REFERENCES documents(id)
        )
    """)

    _ensure_column(
        cursor,
        "collaboration_projects",
        "org_id",
        "org_id INTEGER DEFAULT 1",
    )
    # Draft column for auto-save (does not create a version/commit)
    _ensure_column(
        cursor,
        "project_sections",
        "draft_content",
        "draft_content TEXT",
    )

    conn.commit()
    conn.close()


def generate_invite_code() -> str:
    return secrets.token_urlsafe(8).upper()[:10]