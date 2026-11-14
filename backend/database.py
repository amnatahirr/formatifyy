"""
database.py — SQLite database utility layer for Formatify.

Defines connections, table initializations, and handles auto-seeding of the
default university, admin/student user (templates are admin-created only).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any, Dict, List

DATABASE_URL = "formatify.db"


def hash_password(password: str) -> str:
    """Pure-python SHA256 password hashing with a secure default salt."""
    salt = "formatify_salt_token_2026"
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify password by matching the hash."""
    return hash_password(password) == hashed_password


def get_db():
    """Return a sqlite3 connection configured with row factory."""
    conn = sqlite3.connect(
        DATABASE_URL,
        check_same_thread=False,
        timeout=30
    )
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.row_factory = sqlite3.Row
    return conn



def _purge_legacy_demo_fyp_data(cursor, supervisor_id: int) -> None:
    """Remove hardcoded Alpha/Beta/Gamma-style demo groups and related rows."""
    demo_group_titles = (
        "Alpha Team",
        "Beta Squad",
        "Gamma Group",
        "Zeta Unit",
        "Omega Team",
        "Nova Cell",
    )
    demo_request_names = (
        "Alpha Team",
        "Beta Squad",
        "Gamma Group",
        "Delta Crew",
        "Epsilon Lab",
        "Zeta Unit",
        "Omega Team",
        "Nova Cell",
    )
    placeholders = ",".join("?" for _ in demo_group_titles)
    cursor.execute(
        f"""
        SELECT id FROM fyp_groups
        WHERE supervisor_id = ? AND title IN ({placeholders})
        """,
        (supervisor_id, *demo_group_titles),
    )
    group_ids = [int(row["id"]) for row in cursor.fetchall()]
    if group_ids:
        gph = ",".join("?" for _ in group_ids)
        cursor.execute(
            f"SELECT id FROM group_documents WHERE group_id IN ({gph})",
            group_ids,
        )
        doc_ids = [int(row["id"]) for row in cursor.fetchall()]
        if doc_ids:
            dph = ",".join("?" for _ in doc_ids)
            cursor.execute(
                f"SELECT id FROM document_paragraphs WHERE document_id IN ({dph})",
                doc_ids,
            )
            para_ids = [int(row["id"]) for row in cursor.fetchall()]
            if para_ids:
                pph = ",".join("?" for _ in para_ids)
                cursor.execute(
                    f"""
                    DELETE FROM document_comments
                    WHERE paragraph_id IN ({pph}) OR document_id IN ({dph})
                    """,
                    (*para_ids, *doc_ids),
                )
            else:
                cursor.execute(
                    f"DELETE FROM document_comments WHERE document_id IN ({dph})",
                    doc_ids,
                )
            cursor.execute(
                f"DELETE FROM document_paragraphs WHERE document_id IN ({dph})",
                doc_ids,
            )
            cursor.execute(
                f"DELETE FROM remarks WHERE document_id IN ({dph})",
                doc_ids,
            )
        cursor.execute(f"DELETE FROM group_documents WHERE group_id IN ({gph})", group_ids)
        cursor.execute(f"DELETE FROM group_milestones WHERE group_id IN ({gph})", group_ids)
        cursor.execute(f"DELETE FROM group_replies WHERE group_id IN ({gph})", group_ids)
        cursor.execute(f"DELETE FROM meeting_notes WHERE group_id IN ({gph})", group_ids)
        cursor.execute(f"DELETE FROM final_submissions WHERE group_id IN ({gph})", group_ids)
        cursor.execute(f"DELETE FROM remarks WHERE group_id IN ({gph})", group_ids)
        cursor.execute(
            f"""
            UPDATE assignment_requests
            SET fyp_group_id = NULL
            WHERE fyp_group_id IN ({gph})
            """,
            group_ids,
        )
        cursor.execute(f"DELETE FROM fyp_groups WHERE id IN ({gph})", group_ids)

    req_placeholders = ",".join("?" for _ in demo_request_names)
    cursor.execute(
        f"""
        DELETE FROM assignment_requests
        WHERE supervisor_id = ?
          AND group_name IN ({req_placeholders})
        """,
        (supervisor_id, *demo_request_names),
    )

    _purge_legacy_demo_notifications(cursor)


def _purge_legacy_demo_notifications(cursor) -> None:
    """Remove inbox rows that mention hardcoded Alpha/Beta/… demo groups."""
    demo_tokens = (
        "Alpha Team",
        "Beta Squad",
        "Gamma Group",
        "Delta Crew",
        "Epsilon Lab",
        "Zeta Unit",
        "Omega Team",
        "Nova Cell",
        "ayesha@student.edu",
        "hassan@student.edu",
        "sara@student.edu",
        "ali@student.edu",
        "zainab@student.edu",
    )
    # Match title OR message containing any demo token (case-insensitive)
    clauses = []
    params: list = []
    for token in demo_tokens:
        clauses.append("(LOWER(COALESCE(title, '')) LIKE ? OR LOWER(COALESCE(message, '')) LIKE ?)")
        like = f"%{token.lower()}%"
        params.extend([like, like])
    cursor.execute(
        f"DELETE FROM notifications WHERE {' OR '.join(clauses)}",
        params,
    )


def init_db():
    """
    Initialize SQLite tables: users, universities, templates.
    Seeds initial data if empty.
    """
    conn = get_db()
    cursor = conn.cursor()

    # 1. Create Universities table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS universities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            country TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 2. Create Users table
    cursor.execute("""
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
    """)

    # Student profile fields collected at signup (nullable for legacy accounts).
    cursor.execute("PRAGMA table_info(users)")
    user_columns = {row[1] for row in cursor.fetchall()}
    if "department_id" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN department_id INTEGER")
    if "current_semester" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN current_semester INTEGER")

    # 3. Create Templates table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            university_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            required_sections TEXT,
            formatting_rules TEXT,
            created_by INTEGER NOT NULL,
            org_id INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (university_id) REFERENCES universities(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """)

    # 4. Create Documents table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            template_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            detected_sections TEXT,
            missing_sections TEXT,
            formatted_content TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (template_id) REFERENCES templates(id)
        )
    """)

    # 4b. Frontmatter module columns on documents (idempotent)
    cursor.execute("PRAGMA table_info(documents)")
    document_columns = {row[1] for row in cursor.fetchall()}
    if "group_id" not in document_columns:
        cursor.execute("ALTER TABLE documents ADD COLUMN group_id INTEGER")
    if "frontmatter_domains" not in document_columns:
        cursor.execute("ALTER TABLE documents ADD COLUMN frontmatter_domains TEXT")
    if "signature_path" not in document_columns:
        cursor.execute("ALTER TABLE documents ADD COLUMN signature_path TEXT")
    if "frontmatter_detection" not in document_columns:
        cursor.execute("ALTER TABLE documents ADD COLUMN frontmatter_detection TEXT")
    if "is_freeform" not in document_columns:
        cursor.execute("ALTER TABLE documents ADD COLUMN is_freeform INTEGER DEFAULT 0")
    if "formatted_file_path" not in document_columns:
        cursor.execute("ALTER TABLE documents ADD COLUMN formatted_file_path TEXT")
    if "draft_title" not in document_columns:
        cursor.execute("ALTER TABLE documents ADD COLUMN draft_title TEXT")
    if "draft_content" not in document_columns:
        cursor.execute("ALTER TABLE documents ADD COLUMN draft_content TEXT")

    # 4c. Google Drive OAuth tokens + sync status
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS google_drive_tokens (
            user_id INTEGER PRIMARY KEY,
            access_token TEXT NOT NULL,
            refresh_token TEXT,
            token_expiry TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_sync_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            source TEXT,
            sync_status TEXT,
            google_drive_id TEXT,
            last_synced TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # 5. Create Image Analysis table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS image_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            image_path TEXT NOT NULL,
            is_safe BOOLEAN DEFAULT TRUE,
            confidence_score REAL,
            analysis_result TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        )
    """)

    # 6. Create Departments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT NOT NULL,
            min_members INTEGER DEFAULT 1,
            max_members INTEGER DEFAULT 3,
            max_groups_per_supervisor INTEGER DEFAULT 6,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 7. Create Supervisors table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS supervisors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            department_id INTEGER NOT NULL,
            max_groups INTEGER DEFAULT 6,
            current_groups INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments(id)
        )
    """)

    # 8. Create Deadlines table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deadlines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            due_date DATE NOT NULL,
            department_id INTEGER,
            applies_to_all INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments(id)
        )
    """)

    # 9. Ensure templates support department scoping on existing databases
    cursor.execute("PRAGMA table_info(templates)")
    template_columns = {row[1] for row in cursor.fetchall()}
    if "department_id" not in template_columns:
        cursor.execute("ALTER TABLE templates ADD COLUMN department_id INTEGER")

    # 10. Admin settings key-value store
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 11. FYP groups accepted by a supervisor
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fyp_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supervisor_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            project_title TEXT,
            status TEXT DEFAULT 'accepted',
            progress REAL DEFAULT 0,
            member_names TEXT,
            deadline_date DATE,
            student_contact_email TEXT,
            department_id INTEGER,
            plagiarism_flagged INTEGER DEFAULT 0,
            plagiarism_flag_reason TEXT,
            plagiarism_flagged_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (supervisor_id) REFERENCES supervisors(id),
            FOREIGN KEY (department_id) REFERENCES departments(id)
        )
    """)

    # Migrate fyp_groups columns on existing databases
    cursor.execute("PRAGMA table_info(fyp_groups)")
    fyp_group_columns = {row[1] for row in cursor.fetchall()}
    if "member_names" not in fyp_group_columns:
        cursor.execute("ALTER TABLE fyp_groups ADD COLUMN member_names TEXT")
    if "deadline_date" not in fyp_group_columns:
        cursor.execute("ALTER TABLE fyp_groups ADD COLUMN deadline_date DATE")
    if "student_contact_email" not in fyp_group_columns:
        cursor.execute("ALTER TABLE fyp_groups ADD COLUMN student_contact_email TEXT")
    if "plagiarism_flagged" not in fyp_group_columns:
        cursor.execute(
            "ALTER TABLE fyp_groups ADD COLUMN plagiarism_flagged INTEGER DEFAULT 0"
        )
    if "plagiarism_flag_reason" not in fyp_group_columns:
        cursor.execute(
            "ALTER TABLE fyp_groups ADD COLUMN plagiarism_flag_reason TEXT"
        )
    if "plagiarism_flagged_at" not in fyp_group_columns:
        cursor.execute(
            "ALTER TABLE fyp_groups ADD COLUMN plagiarism_flagged_at DATETIME"
        )
    if "cosupervisor_name" not in fyp_group_columns:
        cursor.execute("ALTER TABLE fyp_groups ADD COLUMN cosupervisor_name TEXT")
    if "current_semester" not in fyp_group_columns:
        cursor.execute("ALTER TABLE fyp_groups ADD COLUMN current_semester INTEGER")
    # Backfill accepted groups so existing students resolve against semester deadlines.
    cursor.execute(
        """
        UPDATE fyp_groups
        SET current_semester = 6
        WHERE current_semester IS NULL AND status = 'accepted'
        """
    )

    # Admin-managed global FYP semester deadlines (one row per semester 6/7).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS semester_deadlines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            semester INTEGER NOT NULL UNIQUE,
            deadline_date DATE NOT NULL,
            created_by INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """)

    # 12. Assignment requests awaiting supervisor decision
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assignment_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supervisor_id INTEGER NOT NULL,
            group_name TEXT NOT NULL,
            project_title TEXT,
            student_leader_name TEXT,
            student_leader_email TEXT,
            member_names TEXT,
            department_id INTEGER,
            status TEXT DEFAULT 'pending',
            rejection_reason TEXT,
            fyp_group_id INTEGER,
            resolved_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (supervisor_id) REFERENCES supervisors(id),
            FOREIGN KEY (department_id) REFERENCES departments(id),
            FOREIGN KEY (fyp_group_id) REFERENCES fyp_groups(id)
        )
    """)

    # Migrate assignment_requests columns on existing databases
    cursor.execute("PRAGMA table_info(assignment_requests)")
    assignment_columns = {row[1] for row in cursor.fetchall()}
    if "member_names" not in assignment_columns:
        cursor.execute("ALTER TABLE assignment_requests ADD COLUMN member_names TEXT")
    if "department_id" not in assignment_columns:
        cursor.execute("ALTER TABLE assignment_requests ADD COLUMN department_id INTEGER")
    if "rejection_reason" not in assignment_columns:
        cursor.execute("ALTER TABLE assignment_requests ADD COLUMN rejection_reason TEXT")
    if "fyp_group_id" not in assignment_columns:
        cursor.execute("ALTER TABLE assignment_requests ADD COLUMN fyp_group_id INTEGER")
    if "resolved_at" not in assignment_columns:
        cursor.execute("ALTER TABLE assignment_requests ADD COLUMN resolved_at DATETIME")
    if "cosupervisor_name" not in assignment_columns:
        cursor.execute(
            "ALTER TABLE assignment_requests ADD COLUMN cosupervisor_name TEXT"
        )

    # 12b. In-app notifications (student / supervisor alerts)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            recipient_email TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            type TEXT DEFAULT 'info',
            is_read INTEGER DEFAULT 0,
            related_type TEXT,
            related_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            org_id INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Migrate notifications columns on existing databases
    cursor.execute("PRAGMA table_info(notifications)")
    notification_columns = {row[1] for row in cursor.fetchall()}
    if "org_id" not in notification_columns:
        cursor.execute("ALTER TABLE notifications ADD COLUMN org_id INTEGER DEFAULT 1")
        cursor.execute("UPDATE notifications SET org_id = 1 WHERE org_id IS NULL")
    
    # Extended schema for unified notification system
    if "body" not in notification_columns:
        cursor.execute("ALTER TABLE notifications ADD COLUMN body TEXT")
        cursor.execute("UPDATE notifications SET body = message WHERE body IS NULL")
    if "entity_type" not in notification_columns:
        cursor.execute("ALTER TABLE notifications ADD COLUMN entity_type TEXT")
        cursor.execute("UPDATE notifications SET entity_type = related_type WHERE entity_type IS NULL")
    if "payload_json" not in notification_columns:
        cursor.execute("ALTER TABLE notifications ADD COLUMN payload_json TEXT")
    if "read_at" not in notification_columns:
        cursor.execute("ALTER TABLE notifications ADD COLUMN read_at DATETIME")
    if "dedupe_key" not in notification_columns:
        cursor.execute("ALTER TABLE notifications ADD COLUMN dedupe_key TEXT")

    # Add index for efficient queries
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_notifications_user_read_created'")
    if not cursor.fetchone():
        cursor.execute("CREATE INDEX idx_notifications_user_read_created ON notifications(user_id, is_read, created_at DESC)")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_notifications_user_dedupe'")
    if not cursor.fetchone():
        cursor.execute("CREATE INDEX idx_notifications_user_dedupe ON notifications(user_id, dedupe_key)")

    # 13. Group documents waiting for supervisor review
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            supervisor_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            filename TEXT,
            file_url TEXT,
            milestone TEXT,
            version_number INTEGER DEFAULT 1,
            plagiarism_score REAL,
            grammar_report_ref TEXT,
            status TEXT DEFAULT 'pending_review',
            submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES fyp_groups(id),
            FOREIGN KEY (supervisor_id) REFERENCES supervisors(id)
        )
    """)

    # Migrate group_documents columns on existing databases
    cursor.execute("PRAGMA table_info(group_documents)")
    group_doc_columns = {row[1] for row in cursor.fetchall()}
    if "file_url" not in group_doc_columns:
        cursor.execute("ALTER TABLE group_documents ADD COLUMN file_url TEXT")
    if "milestone" not in group_doc_columns:
        cursor.execute("ALTER TABLE group_documents ADD COLUMN milestone TEXT")
    if "version_number" not in group_doc_columns:
        cursor.execute(
            "ALTER TABLE group_documents ADD COLUMN version_number INTEGER DEFAULT 1"
        )
    if "plagiarism_score" not in group_doc_columns:
        cursor.execute("ALTER TABLE group_documents ADD COLUMN plagiarism_score REAL")
    if "grammar_report_ref" not in group_doc_columns:
        cursor.execute(
            "ALTER TABLE group_documents ADD COLUMN grammar_report_ref TEXT"
        )
    if "source_document_id" not in group_doc_columns:
        cursor.execute(
            "ALTER TABLE group_documents ADD COLUMN source_document_id INTEGER"
        )

    # 14. Replies from group members to the supervisor
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            supervisor_id INTEGER NOT NULL,
            sender_name TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES fyp_groups(id),
            FOREIGN KEY (supervisor_id) REFERENCES supervisors(id)
        )
    """)

    # 15. Group milestones (Proposal → Literature Review → Final Doc)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_milestones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_completed INTEGER DEFAULT 0,
            completed_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES fyp_groups(id)
        )
    """)

    # 16. Paragraphs belonging to a submitted group document
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_paragraphs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            text TEXT NOT NULL,
            block_type TEXT DEFAULT 'paragraph',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES group_documents(id)
        )
    """)

    cursor.execute("PRAGMA table_info(document_paragraphs)")
    document_paragraph_columns = {row[1] for row in cursor.fetchall()}
    if "block_type" not in document_paragraph_columns:
        cursor.execute(
            "ALTER TABLE document_paragraphs ADD COLUMN block_type TEXT DEFAULT 'paragraph'"
        )

    # 17. Supervisor comments linked to a paragraph
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paragraph_id INTEGER NOT NULL,
            document_id INTEGER NOT NULL,
            supervisor_id INTEGER NOT NULL,
            comment_text TEXT NOT NULL,
            is_resolved INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved_at DATETIME,
            parent_comment_id INTEGER,
            FOREIGN KEY (paragraph_id) REFERENCES document_paragraphs(id),
            FOREIGN KEY (document_id) REFERENCES group_documents(id),
            FOREIGN KEY (supervisor_id) REFERENCES supervisors(id),
            FOREIGN KEY (parent_comment_id) REFERENCES document_comments(id)
        )
    """)

    cursor.execute("PRAGMA table_info(document_comments)")
    document_comment_columns = {row[1] for row in cursor.fetchall()}
    if "parent_comment_id" not in document_comment_columns:
        cursor.execute(
            "ALTER TABLE document_comments ADD COLUMN parent_comment_id INTEGER"
        )
    # 18. Final submissions awaiting supervisor decision (with AI analysis snapshot)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS final_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            supervisor_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            filename TEXT,
            status TEXT DEFAULT 'pending',
            analysis_report TEXT,
            source_document_id INTEGER,
            group_document_id INTEGER,
            student_contact_email TEXT,
            submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved_at DATETIME,
            decision_note TEXT,
            FOREIGN KEY (group_id) REFERENCES fyp_groups(id),
            FOREIGN KEY (supervisor_id) REFERENCES supervisors(id),
            FOREIGN KEY (source_document_id) REFERENCES documents(id)
        )
    """)

    cursor.execute("PRAGMA table_info(final_submissions)")
    final_sub_columns = {row[1] for row in cursor.fetchall()}
    if "group_document_id" not in final_sub_columns:
        cursor.execute(
            "ALTER TABLE final_submissions ADD COLUMN group_document_id INTEGER"
        )

    # 19. Supervisor meeting notes per FYP group (visible read-only to students)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meeting_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            supervisor_id INTEGER NOT NULL,
            meeting_date DATE NOT NULL,
            topic TEXT NOT NULL,
            action_items TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES fyp_groups(id),
            FOREIGN KEY (supervisor_id) REFERENCES supervisors(id)
        )
    """)

    # 20. Overall verdict / remarks on a group document (or group-level feedback)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS remarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            document_id INTEGER,
            verdict TEXT NOT NULL,
            remark_text TEXT,
            created_by INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES fyp_groups(id),
            FOREIGN KEY (document_id) REFERENCES group_documents(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """)

    conn.commit()


    # ── Seeding ───────────────────────────────────────────────────────────────
    # A. Seed default university
    cursor.execute("SELECT COUNT(*) FROM universities")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO universities (id, name, country) VALUES (?, ?, ?)",
            (1, "COMSATS University Islamabad", "Pakistan")
        )
        conn.commit()

    # B. Seed default users (admin & student)
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        # Default Admin: admin@comsats.edu.pk / admin123
        cursor.execute(
            """
            INSERT INTO users (id, username, email, password_hash, role, university_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (1, "admin", "admin@comsats.edu.pk", hash_password("admin123"), "admin", 1)
        )
        # Default Student: student@comsats.edu.pk / student123
        cursor.execute(
            """
            INSERT INTO users (id, username, email, password_hash, role, university_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (2, "student", "student@comsats.edu.pk", hash_password("student123"), "student", 1)
        )
        conn.commit()

    # C. Do NOT auto-seed templates — only admin-created templates from DB.
    # Remove legacy demo templates that older installs may still have.
    cursor.executemany(
        "DELETE FROM templates WHERE id = ? AND name = ?",
        [
            (1, "Academic Research Paper"),
            (2, "Business Report"),
            (3, "University Thesis"),
        ],
    )
    conn.commit()

    # System placeholder so freeform docs satisfy template_id NOT NULL.
    # Hidden from template pickers (filtered by name).
    cursor.execute(
        "SELECT id FROM templates WHERE name = ?",
        ("__freeform_placeholder__",),
    )
    if not cursor.fetchone():
        cursor.execute(
            """
            INSERT INTO templates
                (university_id, name, description, required_sections, formatting_rules, created_by, org_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "__freeform_placeholder__",
                "Internal placeholder for analyze-without-template documents",
                "[]",
                json.dumps(
                    {
                        "body_font": "Times New Roman",
                        "body_size": 12,
                        "body_line_spacing": 2.0,
                        "heading1_font": "Times New Roman",
                        "heading1_size": 16,
                        "heading1_bold": True,
                        "heading2_font": "Times New Roman",
                        "heading2_size": 14,
                        "heading2_bold": True,
                        "heading3_font": "Times New Roman",
                        "heading3_size": 12,
                        "heading3_bold": True,
                        "margin_top": 1.0,
                        "margin_bottom": 1.0,
                        "margin_left": 1.0,
                        "margin_right": 1.0,
                        "spacing_unit": "inch",
                        "heading_numbering_style": "none",
                    }
                ),
                1,
                1,
            ),
        )
        conn.commit()
        print("[database] Seeded __freeform_placeholder__ template.")

    # D. Seed default departments
    cursor.execute("SELECT COUNT(*) FROM departments")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            """
            INSERT INTO departments (name, code, min_members, max_members, max_groups_per_supervisor)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("Computer Science", "CS", 1, 3, 6),
                ("Electrical Engineering", "EE", 1, 4, 6),
                ("Software Engineering", "SE", 1, 3, 6),
                ("Master of Business Administration", "MBA", 1, 2, 6),
            ],
        )
        conn.commit()

    # E. Seed default admin settings
    default_settings = {
        "system_name": "FORMATIFY Admin Panel",
        "version": "3.0.0",
        "environment": "production",
        "email_notifications": "true",
        "system_notifications": "true",
        "maintenance_mode": "false",
        "api_rate_limit": "10000",
        "api_timeout_seconds": "30",
        "max_file_size_mb": "100",
        # Frontmatter cover / project-info branding
        "university_name": "Your University Name",
        "department_name": "Your Department",
        "session": "Fall 2025",
        "logo_path": "",
    }
    for key, value in default_settings.items():
        cursor.execute(
            "INSERT OR IGNORE INTO admin_settings (key, value) VALUES (?, ?)",
            (key, value),
        )
    conn.commit()

    # F. Ensure demo supervisor login exists (no hardcoded Alpha/Beta groups).
    cursor.execute(
        "SELECT id FROM users WHERE LOWER(email) = LOWER(?)",
        ("supervisor@comsats.edu.pk",),
    )
    supervisor_user = cursor.fetchone()
    if supervisor_user is None:
        cursor.execute(
            """
            INSERT INTO users (username, email, password_hash, role, university_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "supervisor",
                "supervisor@comsats.edu.pk",
                hash_password("supervisor123"),
                "supervisor",
                1,
            ),
        )
        conn.commit()

    cursor.execute("SELECT id FROM departments ORDER BY id ASC LIMIT 1")
    dept_row = cursor.fetchone()
    dept_id = dept_row["id"] if dept_row else None

    cursor.execute(
        "SELECT id FROM supervisors WHERE LOWER(email) = LOWER(?)",
        ("supervisor@comsats.edu.pk",),
    )
    supervisor_row = cursor.fetchone()
    if supervisor_row is None and dept_id is not None:
        cursor.execute(
            """
            INSERT INTO supervisors (name, email, department_id, max_groups, current_groups, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("Demo Supervisor", "supervisor@comsats.edu.pk", dept_id, 6, 0, 1),
        )
        conn.commit()
        cursor.execute(
            "SELECT id FROM supervisors WHERE LOWER(email) = LOWER(?)",
            ("supervisor@comsats.edu.pk",),
        )
        supervisor_row = cursor.fetchone()

    if supervisor_row is not None:
        supervisor_id = supervisor_row["id"]
        # One-time cleanup of legacy dummy groups that filled supervisor slots
        _purge_legacy_demo_fyp_data(cursor, supervisor_id)
    else:
        _purge_legacy_demo_notifications(cursor)

    # Keep every supervisor's slot counter in sync with accepted groups only
    cursor.execute("SELECT id FROM supervisors")
    for row in cursor.fetchall():
        sid = int(row["id"])
        cursor.execute(
            """
            SELECT COUNT(*) FROM fyp_groups
            WHERE supervisor_id = ? AND status = 'accepted'
            """,
            (sid,),
        )
        accepted_count = int(cursor.fetchone()[0] or 0)
        cursor.execute(
            "UPDATE supervisors SET current_groups = ? WHERE id = ?",
            (accepted_count, sid),
        )
    conn.commit()

    # ── Organizations (multi-tenancy) — additive only ─────────────────────────
    _ensure_organizations_schema(cursor)
    conn.commit()

    conn.close()
    print("Database tables initialized and seeded successfully.")

    from vc.database import init_vc_tables
    init_vc_tables()


def _ensure_column(cursor, table: str, column: str, ddl: str) -> None:
    """Idempotent ALTER TABLE ADD COLUMN."""
    cursor.execute(f"PRAGMA table_info({table})")
    cols = {row[1] for row in cursor.fetchall()}
    if column not in cols:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def _ensure_organizations_schema(cursor) -> None:
    """Create organizations tables, seed default org, add org_id to tenants."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS organizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            type TEXT DEFAULT 'university',
            api_key TEXT UNIQUE NOT NULL,
            plan TEXT DEFAULT 'university',
            modules TEXT DEFAULT 'core,fyp',
            documents_used INTEGER DEFAULT 0,
            documents_limit INTEGER DEFAULT 999999,
            is_active INTEGER DEFAULT 1,
            primary_color TEXT DEFAULT '#7B61FF',
            logo_url TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS organization_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id INTEGER NOT NULL,
            module_name TEXT NOT NULL,
            is_enabled INTEGER DEFAULT 1,
            FOREIGN KEY (org_id) REFERENCES organizations(id)
        )
        """
    )

    cursor.execute("SELECT COUNT(*) AS c FROM organizations")
    if int(cursor.fetchone()[0] or 0) == 0:
        cursor.execute(
            """
            INSERT INTO organizations
                (name, code, type, api_key, plan, modules, documents_used, documents_limit, is_active, primary_color)
            VALUES (?, ?, ?, ?, ?, ?, 0, 999999, 1, ?)
            """,
            (
                "COMSATS University Islamabad",
                "COMSATS-LHR",
                "university",
                "fmt_live_comsats_default",
                "university",
                "core,fyp",
                "#7B61FF",
            ),
        )
        org_id = cursor.lastrowid
        for mod in ("core", "fyp"):
            cursor.execute(
                """
                INSERT INTO organization_modules (org_id, module_name, is_enabled)
                VALUES (?, ?, 1)
                """,
                (org_id, mod),
            )

    # org_id on existing tenant tables (safe defaults → org 1)
    for table in (
        "users",
        "supervisors",
        "fyp_groups",
        "templates",
        "final_submissions",
        "deadlines",
        "departments",
        "assignment_requests",
        "documents",
        "semester_deadlines",
    ):
        try:
            cursor.execute(f"SELECT 1 FROM {table} LIMIT 1")
        except Exception:
            continue
        _ensure_column(cursor, table, "org_id", "org_id INTEGER DEFAULT 1")

    _ensure_users_org_scoped_uniqueness(cursor)
    _ensure_supervisors_org_scoped_uniqueness(cursor)
    _ensure_semester_deadlines_org_scoped(cursor)
    _repair_mislabelled_company_tenants(cursor)
    _ensure_column(cursor, "deadlines", "target_semester", "target_semester INTEGER")
    _ensure_column(cursor, "users", "is_graduated", "is_graduated INTEGER DEFAULT 0")
    cursor.execute("PRAGMA table_info(deadline_reminders_sent)")
    _cols = [r[1] for r in cursor.fetchall()]
    if _cols and "stage" not in _cols:
        cursor.execute("DROP TABLE deadline_reminders_sent")
        _cols = []
    if not _cols:
        cursor.execute("""
    CREATE TABLE IF NOT EXISTS deadline_reminders_sent (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        deadline_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        stage INTEGER NOT NULL DEFAULT 3,
        sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (deadline_id, user_id, stage)
    )
""")

    # Alias: user asked for "groups" / "submissions" — we use fyp_groups / final_submissions
    print("[database] Organizations schema ready (default org_id=1).")


def _repair_mislabelled_company_tenants(cursor) -> None:
    """
    Keep type in sync with plan only.
    Modules (core/fyp) are independent — a university may be core-only, and a
    company/starter may enable fyp. Never infer plan from modules.
    """
    cursor.execute("SELECT id, type, plan FROM organizations")
    repaired = 0
    for row in cursor.fetchall():
        plan = (row["plan"] or "university").strip().lower()
        org_type = (row["type"] or "university").strip().lower()

        if plan in ("starter", "enterprise") and org_type != "company":
            cursor.execute(
                "UPDATE organizations SET type = 'company' WHERE id = ?",
                (row["id"],),
            )
            repaired += 1
        elif plan == "university" and org_type == "company":
            cursor.execute(
                "UPDATE organizations SET type = 'university' WHERE id = ?",
                (row["id"],),
            )
            repaired += 1

    if repaired:
        print(f"[database] Repaired {repaired} org type/plan mismatch(es).")

def _ensure_users_org_scoped_uniqueness(cursor) -> None:
    """
    Allow same email/username across different orgs.
    Rebuilds users table if it still has global UNIQUE on email/username.
    """
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_users_email_org'"
    )
    if cursor.fetchone():
        return

    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")
    row = cursor.fetchone()
    if not row:
        return

    table_sql = row[0] or ""
    needs_rebuild = (
        "email TEXT UNIQUE" in table_sql
        or "username TEXT UNIQUE" in table_sql
        or "email TEXT NOT NULL UNIQUE" in table_sql
        or "username TEXT NOT NULL UNIQUE" in table_sql
    )

    if needs_rebuild:
        cursor.execute("PRAGMA foreign_keys = OFF")
        cursor.execute("DROP TABLE IF EXISTS users__org_scoped")
        cursor.execute(
            """
            CREATE TABLE users__org_scoped (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'student',
                university_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                department_id INTEGER,
                current_semester INTEGER,
                org_id INTEGER DEFAULT 1,
                FOREIGN KEY (university_id) REFERENCES universities(id)
            )
            """
        )
        cursor.execute("PRAGMA table_info(users)")
        existing = {r[1] for r in cursor.fetchall()}
        cols = [
            c
            for c in (
                "id",
                "username",
                "email",
                "password_hash",
                "role",
                "university_id",
                "created_at",
                "department_id",
                "current_semester",
                "org_id",
            )
            if c in existing
        ]
        col_csv = ", ".join(cols)
        cursor.execute(
            f"INSERT INTO users__org_scoped ({col_csv}) SELECT {col_csv} FROM users"
        )
        cursor.execute("DROP TABLE users")
        cursor.execute("ALTER TABLE users__org_scoped RENAME TO users")
        cursor.execute("PRAGMA foreign_keys = ON")
        print("[database] users uniqueness scoped to (email, org_id) / (username, org_id).")

    # Resolve legacy case-insensitive collisions within the same org
    # (e.g. "ayesha" and "Ayesha") before creating unique indexes.
    cursor.execute(
        """
        SELECT LOWER(username) AS uname, org_id, GROUP_CONCAT(id) AS ids
        FROM users
        GROUP BY LOWER(username), org_id
        HAVING COUNT(*) > 1
        """
    )
    for row in cursor.fetchall():
        ids = [int(x) for x in str(row["ids"]).split(",") if x]
        for extra_id in ids[1:]:
            cursor.execute(
                "UPDATE users SET username = username || '_' || CAST(id AS TEXT) WHERE id = ?",
                (extra_id,),
            )

    cursor.execute(
        """
        SELECT LOWER(email) AS em, org_id, GROUP_CONCAT(id) AS ids
        FROM users
        GROUP BY LOWER(email), org_id
        HAVING COUNT(*) > 1
        """
    )
    for row in cursor.fetchall():
        ids = [int(x) for x in str(row["ids"]).split(",") if x]
        for extra_id in ids[1:]:
            cursor.execute(
                "UPDATE users SET email = printf('dup_%s_%s', id, email) WHERE id = ?",
                (extra_id,),
            )

    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_org
        ON users(email COLLATE NOCASE, org_id)
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_org
        ON users(username COLLATE NOCASE, org_id)
        """
    )


def _ensure_supervisors_org_scoped_uniqueness(cursor) -> None:
    """Allow same supervisor email across orgs."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_supervisors_email_org'"
    )
    if cursor.fetchone():
        return

    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='supervisors'")
    row = cursor.fetchone()
    if not row:
        return
    table_sql = row[0] or ""
    needs_rebuild = "email TEXT NOT NULL UNIQUE" in table_sql or "email TEXT UNIQUE" in table_sql

    if needs_rebuild:
        cursor.execute("PRAGMA foreign_keys = OFF")
        cursor.execute("DROP TABLE IF EXISTS supervisors__org_scoped")
        cursor.execute(
            """
            CREATE TABLE supervisors__org_scoped (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                department_id INTEGER NOT NULL,
                max_groups INTEGER DEFAULT 6,
                current_groups INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                org_id INTEGER DEFAULT 1,
                FOREIGN KEY (department_id) REFERENCES departments(id)
            )
            """
        )
        cursor.execute("PRAGMA table_info(supervisors)")
        existing = {r[1] for r in cursor.fetchall()}
        cols = [
            c
            for c in (
                "id",
                "name",
                "email",
                "department_id",
                "max_groups",
                "current_groups",
                "is_active",
                "created_at",
                "org_id",
            )
            if c in existing
        ]
        col_csv = ", ".join(cols)
        cursor.execute(
            f"INSERT INTO supervisors__org_scoped ({col_csv}) SELECT {col_csv} FROM supervisors"
        )
        cursor.execute("DROP TABLE supervisors")
        cursor.execute("ALTER TABLE supervisors__org_scoped RENAME TO supervisors")
        cursor.execute("PRAGMA foreign_keys = ON")
        print("[database] supervisors email uniqueness scoped to (email, org_id).")

    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_supervisors_email_org
        ON supervisors(email COLLATE NOCASE, org_id)
        """
    )


def _ensure_semester_deadlines_org_scoped(cursor) -> None:
    """Allow one deadline per semester per org (not globally)."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_semester_deadlines_org'"
    )
    if cursor.fetchone():
        return

    cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='semester_deadlines'"
    )
    row = cursor.fetchone()
    if not row:
        return
    table_sql = row[0] or ""
    needs_rebuild = "semester INTEGER NOT NULL UNIQUE" in table_sql

    if needs_rebuild:
        cursor.execute("PRAGMA foreign_keys = OFF")
        cursor.execute("DROP TABLE IF EXISTS semester_deadlines__org_scoped")
        cursor.execute(
            """
            CREATE TABLE semester_deadlines__org_scoped (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                semester INTEGER NOT NULL,
                deadline_date DATE NOT NULL,
                created_by INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                org_id INTEGER DEFAULT 1,
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
            """
        )
        cursor.execute("PRAGMA table_info(semester_deadlines)")
        existing = {r[1] for r in cursor.fetchall()}
        cols = [
            c
            for c in (
                "id",
                "semester",
                "deadline_date",
                "created_by",
                "created_at",
                "updated_at",
                "org_id",
            )
            if c in existing
        ]
        col_csv = ", ".join(cols)
        cursor.execute(
            f"INSERT INTO semester_deadlines__org_scoped ({col_csv}) "
            f"SELECT {col_csv} FROM semester_deadlines"
        )
        cursor.execute("DROP TABLE semester_deadlines")
        cursor.execute("ALTER TABLE semester_deadlines__org_scoped RENAME TO semester_deadlines")
        cursor.execute("PRAGMA foreign_keys = ON")
        print("[database] semester_deadlines uniqueness scoped to (semester, org_id).")

    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_semester_deadlines_org
        ON semester_deadlines(semester, org_id)
        """
    )