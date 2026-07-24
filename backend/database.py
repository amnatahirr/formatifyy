"""
database.py — SQLite database utility layer for Formatify.

Defines connections, table initializations, and handles auto-seeding of the
default university, admin/student user, and 3 predefined templates.
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
    conn.row_factory = sqlite3.Row
    return conn


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
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

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
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES group_documents(id)
        )
    """)

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
            student_contact_email TEXT,
            submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved_at DATETIME,
            decision_note TEXT,
            FOREIGN KEY (group_id) REFERENCES fyp_groups(id),
            FOREIGN KEY (supervisor_id) REFERENCES supervisors(id),
            FOREIGN KEY (source_document_id) REFERENCES documents(id)
        )
    """)

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

    # C. Seed default templates
    cursor.execute("SELECT COUNT(*) FROM templates")
    if cursor.fetchone()[0] == 0:
        # 1. Academic Research Paper Rules
        academic_rules = {
            "heading1_font": "Times New Roman",
            "heading1_size": 16,
            "heading1_bold": True,
            "heading1_italic": False,
            "heading1_line_spacing": 1.5,
            "heading1_space_before": 24.0,
            "heading1_space_after": 12.0,
            "heading2_font": "Times New Roman",
            "heading2_size": 14,
            "heading2_bold": True,
            "heading2_italic": False,
            "heading2_line_spacing": 1.5,
            "heading2_space_before": 18.0,
            "heading2_space_after": 8.0,
            "heading3_font": "Times New Roman",
            "heading3_size": 12,
            "heading3_bold": True,
            "heading3_italic": True,
            "heading3_line_spacing": 1.5,
            "heading3_space_before": 12.0,
            "heading3_space_after": 6.0,
            "body_font": "Times New Roman",
            "body_size": 12,
            "body_line_spacing": 2.0,
            "body_space_before": 0.0,
            "body_space_after": 0.0,
            "margin_top": 1.0,
            "margin_bottom": 1.0,
            "margin_left": 1.0,
            "margin_right": 1.0,
            "page_size": "A4",
            "line_number_enabled": False,
            "first_line_indent": 0.5
        }
        cursor.execute(
            """
            INSERT INTO templates (id, university_id, name, description, required_sections, formatting_rules, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1, 1, "Academic Research Paper",
                "Standard academic research formats (Times New Roman, 12pt, double spaced, justified alignment).",
                json.dumps(["Title Page", "Abstract", "Introduction", "Literature Review", "Methodology", "Results", "Discussion", "Conclusion", "References"]),
                json.dumps(academic_rules),
                1
            )
        )

        # 2. Business Report Rules
        business_rules = {
            "heading1_font": "Arial",
            "heading1_size": 18,
            "heading1_bold": True,
            "heading1_italic": False,
            "heading1_line_spacing": 1.15,
            "heading1_space_before": 24.0,
            "heading1_space_after": 12.0,
            "heading2_font": "Arial",
            "heading2_size": 14,
            "heading2_bold": True,
            "heading2_italic": False,
            "heading2_line_spacing": 1.15,
            "heading2_space_before": 18.0,
            "heading2_space_after": 8.0,
            "heading3_font": "Arial",
            "heading3_size": 12,
            "heading3_bold": True,
            "heading3_italic": False,
            "heading3_line_spacing": 1.15,
            "heading3_space_before": 12.0,
            "heading3_space_after": 6.0,
            "body_font": "Arial",
            "body_size": 11,
            "body_line_spacing": 1.15,
            "body_space_before": 0.0,
            "body_space_after": 6.0,
            "margin_top": 1.0,
            "margin_bottom": 1.0,
            "margin_left": 1.25,
            "margin_right": 1.0,
            "page_size": "Letter",
            "line_number_enabled": False,
            "first_line_indent": 0.0
        }
        cursor.execute(
            """
            INSERT INTO templates (id, university_id, name, description, required_sections, formatting_rules, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                2, 1, "Business Report",
                "Professional business reports (Arial, 11pt, 1.15 line spacing, left aligned).",
                json.dumps(["Title Page", "Executive Summary", "Introduction", "Background", "Analysis", "Recommendations", "Conclusion", "References"]),
                json.dumps(business_rules),
                1
            )
        )

        # 3. University Thesis Rules
        thesis_rules = {
            "heading1_font": "Times New Roman",
            "heading1_size": 18,
            "heading1_bold": True,
            "heading1_italic": False,
            "heading1_line_spacing": 1.5,
            "heading1_space_before": 36.0,
            "heading1_space_after": 18.0,
            "heading2_font": "Times New Roman",
            "heading2_size": 14,
            "heading2_bold": True,
            "heading2_italic": False,
            "heading2_line_spacing": 1.5,
            "heading2_space_before": 24.0,
            "heading2_space_after": 12.0,
            "heading3_font": "Times New Roman",
            "heading3_size": 12,
            "heading3_bold": True,
            "heading3_italic": False,
            "heading3_line_spacing": 1.5,
            "heading3_space_before": 12.0,
            "heading3_space_after": 6.0,
            "body_font": "Times New Roman",
            "body_size": 12,
            "body_line_spacing": 1.5,
            "body_space_before": 0.0,
            "body_space_after": 0.0,
            "margin_top": 1.0,
            "margin_bottom": 1.0,
            "margin_left": 1.5,
            "margin_right": 1.0,
            "page_size": "A4",
            "line_number_enabled": False,
            "first_line_indent": 0.5
        }
        cursor.execute(
            """
            INSERT INTO templates (id, university_id, name, description, required_sections, formatting_rules, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                3, 1, "University Thesis",
                "Formal academic dissertation layout (Times New Roman, 1.5 spacing, 1.5-inch left margin for binding).",
                json.dumps(["Title Page", "Declaration", "Acknowledgements", "Abstract", "Table of Contents", "Introduction", "Literature Review", "Methodology", "Results", "Conclusion", "References"]),
                json.dumps(thesis_rules),
                1
            )
        )

        conn.commit()

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

    # F. Seed demo supervisor account + sample home-dashboard data (idempotent)
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
        cursor.execute("SELECT COUNT(*) FROM fyp_groups WHERE supervisor_id = ?", (supervisor_id,))
        if cursor.fetchone()[0] == 0:
            from datetime import date, timedelta

            today = date.today()
            sample_groups = [
                (
                    "Alpha Team",
                    "Smart Campus Navigation",
                    72.0,
                    json.dumps(["Ayesha Khan", "Bilal Raza", "Sana Iqbal"]),
                    (today - timedelta(days=5)).isoformat(),
                ),
                (
                    "Beta Squad",
                    "AI Document Formatter",
                    45.0,
                    json.dumps(["Hassan Ali", "Fatima Zahra"]),
                    (today + timedelta(days=25)).isoformat(),
                ),
                (
                    "Gamma Group",
                    "IoT Attendance System",
                    18.0,
                    json.dumps(["Sara Ahmed", "Usman Tariq", "Hira Noor"]),
                    (today - timedelta(days=12)).isoformat(),
                ),
            ]
            for title, project_title, progress, members, deadline in sample_groups:
                cursor.execute(
                    """
                    INSERT INTO fyp_groups
                        (supervisor_id, title, project_title, status, progress,
                         member_names, deadline_date, department_id)
                    VALUES (?, ?, ?, 'accepted', ?, ?, ?, ?)
                    """,
                    (supervisor_id, title, project_title, progress, members, deadline, dept_id),
                )
            cursor.execute(
                "UPDATE supervisors SET current_groups = ? WHERE id = ?",
                (len(sample_groups), supervisor_id),
            )
            conn.commit()

            cursor.execute(
                "SELECT id, title FROM fyp_groups WHERE supervisor_id = ? ORDER BY id ASC",
                (supervisor_id,),
            )
            groups = cursor.fetchall()

            cursor.execute(
                "SELECT COUNT(*) FROM assignment_requests WHERE supervisor_id = ?",
                (supervisor_id,),
            )
            if cursor.fetchone()[0] == 0:
                cursor.executemany(
                    """
                    INSERT INTO assignment_requests
                        (supervisor_id, group_name, project_title, student_leader_name,
                         student_leader_email, member_names, department_id, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
                    """,
                    [
                        (
                            supervisor_id,
                            "Delta Crew",
                            "Blockchain Transcripts",
                            "Ayesha Khan",
                            "ayesha@student.edu",
                            json.dumps(["Ayesha Khan", "Omar Farooq", "Nina Malik"]),
                            dept_id,
                        ),
                        (
                            supervisor_id,
                            "Epsilon Lab",
                            "AR Lab Manual",
                            "Hassan Ali",
                            "hassan@student.edu",
                            json.dumps(["Hassan Ali", "Fatima Zahra"]),
                            dept_id,
                        ),
                        (
                            supervisor_id,
                            "Zeta Unit",
                            "Healthcare Chatbot",
                            "Sara Ahmed",
                            "sara@student.edu",
                            json.dumps(["Sara Ahmed", "Usman Tariq", "Hira Noor"]),
                            dept_id,
                        ),
                    ],
                )

            if groups:
                cursor.execute(
                    "SELECT COUNT(*) FROM group_documents WHERE supervisor_id = ?",
                    (supervisor_id,),
                )
                if cursor.fetchone()[0] == 0:
                    cursor.executemany(
                        """
                        INSERT INTO group_documents (group_id, supervisor_id, title, filename, status)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        [
                            (groups[0]["id"], supervisor_id, "Chapter 1 Draft", "chapter1.docx", "pending"),
                            (groups[1]["id"], supervisor_id, "Proposal Revision", "proposal_v2.pdf", "revision"),
                            (groups[2]["id"], supervisor_id, "Literature Survey", "lit_review.docx", "approved"),
                        ],
                    )

                # Default milestones for seeded groups
                from datetime import datetime as _dt

                for group in groups:
                    cursor.execute(
                        "SELECT COUNT(*) FROM group_milestones WHERE group_id = ?",
                        (group["id"],),
                    )
                    if cursor.fetchone()[0] == 0:
                        cursor.execute("SELECT progress FROM fyp_groups WHERE id = ?", (group["id"],))
                        progress_row = cursor.fetchone()
                        progress = float(progress_row["progress"] or 0) if progress_row else 0
                        milestone_defs = [
                            ("Proposal", 1, progress >= 30),
                            ("Literature Review", 2, progress >= 60),
                            ("Final Doc", 3, progress >= 100),
                        ]
                        for name, order, done in milestone_defs:
                            cursor.execute(
                                """
                                INSERT INTO group_milestones
                                    (group_id, name, sort_order, is_completed, completed_at)
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                (
                                    group["id"],
                                    name,
                                    order,
                                    1 if done else 0,
                                    _dt.utcnow().isoformat(sep=" ", timespec="seconds") if done else None,
                                ),
                            )

                cursor.execute(
                    "SELECT COUNT(*) FROM group_replies WHERE supervisor_id = ?",
                    (supervisor_id,),
                )
                if cursor.fetchone()[0] == 0:
                    cursor.executemany(
                        """
                        INSERT INTO group_replies (group_id, supervisor_id, sender_name, message, is_read)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        [
                            (groups[0]["id"], supervisor_id, "Ayesha Khan", "Updated the methodology section as requested.", 0),
                            (groups[0]["id"], supervisor_id, "Bilal Raza", "Please review the new figures.", 0),
                            (groups[1]["id"], supervisor_id, "Hassan Ali", "Attached the revised proposal.", 0),
                            (groups[2]["id"], supervisor_id, "Sara Ahmed", "Can we schedule a meeting?", 1),
                        ],
                    )
            conn.commit()

        # Backfill member/department on older demo assignment requests
        cursor.execute(
            """
            SELECT id, group_name, student_leader_name, member_names, department_id
            FROM assignment_requests
            WHERE supervisor_id = ? AND status = 'pending'
            """,
            (supervisor_id,),
        )
        for req in cursor.fetchall():
            updates = []
            values: list[Any] = []
            if not req["member_names"]:
                leader = req["student_leader_name"] or "Student"
                extras = {
                    "Delta Crew": ["Omar Farooq", "Nina Malik"],
                    "Epsilon Lab": ["Fatima Zahra"],
                    "Zeta Unit": ["Usman Tariq", "Hira Noor"],
                }.get(req["group_name"], [])
                updates.append("member_names = ?")
                values.append(json.dumps([leader, *extras]))
            if req["department_id"] is None and dept_id is not None:
                updates.append("department_id = ?")
                values.append(dept_id)
            if updates:
                values.append(req["id"])
                cursor.execute(
                    f"UPDATE assignment_requests SET {', '.join(updates)} WHERE id = ?",
                    values,
                )
        conn.commit()

        # Backfill member names / deadlines on existing accepted groups
        from datetime import date, timedelta

        today = date.today()
        group_defaults = {
            "Alpha Team": (
                json.dumps(["Ayesha Khan", "Bilal Raza", "Sana Iqbal"]),
                (today - timedelta(days=5)).isoformat(),
            ),
            "Beta Squad": (
                json.dumps(["Hassan Ali", "Fatima Zahra"]),
                (today + timedelta(days=25)).isoformat(),
            ),
            "Gamma Group": (
                json.dumps(["Sara Ahmed", "Usman Tariq", "Hira Noor"]),
                (today - timedelta(days=12)).isoformat(),
            ),
            "Zeta Unit": (
                json.dumps(["Sara Ahmed", "Usman Tariq", "Hira Noor"]),
                (today + timedelta(days=40)).isoformat(),
            ),
        }
        cursor.execute(
            """
            SELECT id, title, member_names, deadline_date
            FROM fyp_groups
            WHERE supervisor_id = ? AND status = 'accepted'
            """,
            (supervisor_id,),
        )
        existing_groups = [dict(row) for row in cursor.fetchall()]
        for group in existing_groups:
            updates = []
            values: list[Any] = []
            defaults = group_defaults.get(group["title"])
            if not group["member_names"]:
                members = defaults[0] if defaults else json.dumps([group["title"]])
                cursor.execute(
                    """
                    SELECT member_names, student_leader_name
                    FROM assignment_requests
                    WHERE fyp_group_id = ?
                    LIMIT 1
                    """,
                    (group["id"],),
                )
                linked = cursor.fetchone()
                if linked and linked["member_names"]:
                    members = linked["member_names"]
                elif linked and linked["student_leader_name"]:
                    members = json.dumps([linked["student_leader_name"]])
                updates.append("member_names = ?")
                values.append(members)
            if not group["deadline_date"]:
                deadline = defaults[1] if defaults else (today + timedelta(days=45)).isoformat()
                updates.append("deadline_date = ?")
                values.append(deadline)
            if updates:
                values.append(group["id"])
                cursor.execute(
                    f"UPDATE fyp_groups SET {', '.join(updates)} WHERE id = ?",
                    values,
                )
        conn.commit()

        # Backfill milestones + normalize document statuses for accepted groups
        from datetime import datetime as _dt

        DEFAULT_MILESTONES = ("Proposal", "Literature Review", "Final Doc")
        cursor.execute(
            """
            SELECT id, progress FROM fyp_groups
            WHERE supervisor_id = ? AND status = 'accepted'
            """,
            (supervisor_id,),
        )
        for group in [dict(r) for r in cursor.fetchall()]:
            cursor.execute(
                "SELECT COUNT(*) FROM group_milestones WHERE group_id = ?",
                (group["id"],),
            )
            if cursor.fetchone()[0] == 0:
                progress = float(group["progress"] or 0)
                flags = [progress >= 30, progress >= 60, progress >= 100]
                for index, name in enumerate(DEFAULT_MILESTONES, start=1):
                    done = flags[index - 1]
                    cursor.execute(
                        """
                        INSERT INTO group_milestones
                            (group_id, name, sort_order, is_completed, completed_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            group["id"],
                            name,
                            index,
                            1 if done else 0,
                            _dt.utcnow().isoformat(sep=" ", timespec="seconds") if done else None,
                        ),
                    )

        # Normalize legacy document statuses used by the home "to review" count
        cursor.execute(
            """
            UPDATE group_documents
            SET status = 'pending'
            WHERE supervisor_id = ? AND status = 'pending_review'
            """,
            (supervisor_id,),
        )
        cursor.execute(
            """
            UPDATE group_documents
            SET status = 'revision'
            WHERE supervisor_id = ? AND status = 'needs_changes'
            """,
            (supervisor_id,),
        )
        conn.commit()

        # Backfill demo paragraphs for documents that have none
        sample_paragraphs = [
            "This chapter introduces the motivation behind the proposed system and outlines the research problem.",
            "Existing solutions fail to address formatting consistency across multi-author academic reports.",
            "The objectives of this project include automated structure detection and supervisor review workflows.",
            "We evaluate the approach using real FYP reports collected from the Computer Science department.",
            "Finally, the chapter summarizes contributions and previews the remaining document structure.",
        ]
        cursor.execute(
            "SELECT id, title FROM group_documents WHERE supervisor_id = ?",
            (supervisor_id,),
        )
        for doc in [dict(r) for r in cursor.fetchall()]:
            cursor.execute(
                "SELECT COUNT(*) FROM document_paragraphs WHERE document_id = ?",
                (doc["id"],),
            )
            if cursor.fetchone()[0] == 0:
                for order, text in enumerate(sample_paragraphs, start=1):
                    para_text = text
                    if order == 1:
                        para_text = f"{doc['title']}: {text}"
                    cursor.execute(
                        """
                        INSERT INTO document_paragraphs (document_id, sort_order, text)
                        VALUES (?, ?, ?)
                        """,
                        (doc["id"], order, para_text),
                    )
        conn.commit()

        # Backfill student contact emails on accepted groups (for comment notifications)
        email_defaults = {
            "Alpha Team": "ayesha@student.edu",
            "Beta Squad": "hassan@student.edu",
            "Gamma Group": "student@comsats.edu.pk",
            "Zeta Unit": "sara@student.edu",
            "Omega Team": "ali@student.edu",
            "Nova Cell": "zainab@student.edu",
        }
        cursor.execute(
            """
            SELECT id, title, student_contact_email
            FROM fyp_groups
            WHERE supervisor_id = ? AND status = 'accepted'
            """,
            (supervisor_id,),
        )
        for group in [dict(r) for r in cursor.fetchall()]:
            if group.get("student_contact_email"):
                continue
            email = email_defaults.get(group["title"])
            if not email:
                cursor.execute(
                    """
                    SELECT student_leader_email
                    FROM assignment_requests
                    WHERE fyp_group_id = ? OR LOWER(group_name) = LOWER(?)
                    ORDER BY id DESC LIMIT 1
                    """,
                    (group["id"], group["title"]),
                )
                linked = cursor.fetchone()
                email = linked["student_leader_email"] if linked else None
            if email:
                cursor.execute(
                    "UPDATE fyp_groups SET student_contact_email = ? WHERE id = ?",
                    (email, group["id"]),
                )
        conn.commit()

        # Seed demo final submissions with Formatify-style analysis snapshots
        cursor.execute(
            """
            SELECT COUNT(*) FROM final_submissions
            WHERE supervisor_id = ? AND status = 'pending'
            """,
            (supervisor_id,),
        )
        pending_subs = cursor.fetchone()[0]
        if pending_subs < 2:
            cursor.execute(
                """
                SELECT id, title, student_contact_email
                FROM fyp_groups
                WHERE supervisor_id = ? AND status = 'accepted'
                ORDER BY id ASC
                """,
                (supervisor_id,),
            )
            groups_for_subs = [dict(r) for r in cursor.fetchall()]
            demo_reports = [
                {
                    "stats": {
                        "total_issues": 11,
                        "grammar_issues": 5,
                        "plagiarism_issues": 2,
                        "formatting_issues": 4,
                        "major_issues": 3,
                        "minor_issues": 8,
                        "avg_formatting_compliance": 84.0,
                        "avg_plagiarism_risk": 68.0,
                    },
                    "structure": {
                        "score": 76.0,
                        "status": "needs_work",
                        "summary": {"grammar": 5, "plagiarism": 2, "content_issues": 7, "style_issues": 4},
                    },
                    "compliance_score": 76.0,
                    "issues": [
                        {
                            "function": "grammar",
                            "category": "Grammar",
                            "type": "grammar",
                            "severity": "minor",
                            "reason": "Subject-verb agreement error.",
                            "original": "The results shows improvement",
                            "suggestion": "The results show improvement",
                            "paragraph_id": "p2",
                        },
                        {
                            "function": "plagiarism",
                            "category": "Plagiarism",
                            "type": "corpus_semantic_match",
                            "severity": "major",
                            "reason": "High similarity with prior FYP corpus sentence.",
                            "original": "Deep learning models have revolutionized image classification.",
                            "suggestion": "Rewrite in your own words and cite the source.",
                            "similarity": 0.86,
                            "paragraph_id": "p4",
                            "source": "Prior FYP corpus — Image Classification Survey",
                        },
                    ],
                },
                {
                    "stats": {
                        "total_issues": 4,
                        "grammar_issues": 1,
                        "plagiarism_issues": 0,
                        "formatting_issues": 3,
                        "major_issues": 0,
                        "minor_issues": 4,
                        "avg_formatting_compliance": 92.0,
                        "avg_plagiarism_risk": 42.5,
                    },
                    "structure": {
                        "score": 91.0,
                        "status": "good",
                        "summary": {"grammar": 1, "plagiarism": 0, "content_issues": 1, "style_issues": 3},
                    },
                    "compliance_score": 91.0,
                    "issues": [
                        {
                            "function": "grammar",
                            "category": "Grammar",
                            "type": "grammar",
                            "severity": "minor",
                            "reason": "Missing article before noun.",
                            "original": "System uses transformer model",
                            "suggestion": "The system uses a transformer model",
                            "paragraph_id": "p1",
                        },
                    ],
                },
            ]
            needed = 2 - pending_subs
            for index, group in enumerate(groups_for_subs[:needed]):
                report = demo_reports[index % len(demo_reports)]
                title = f"{group['title']} — Final Document"
                filename = f"{group['title'].lower().replace(' ', '_')}_final.docx"
                cursor.execute(
                    """
                    INSERT INTO final_submissions
                        (group_id, supervisor_id, title, filename, status, analysis_report, student_contact_email)
                    VALUES (?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (
                        group["id"],
                        supervisor_id,
                        title,
                        filename,
                        json.dumps(report),
                        group.get("student_contact_email"),
                    ),
                )
                submission_id = cursor.lastrowid
                cursor.execute("SELECT email FROM supervisors WHERE id = ?", (supervisor_id,))
                sup = cursor.fetchone()
                if sup:
                    cursor.execute(
                        """
                        INSERT INTO notifications
                            (user_id, recipient_email, title, message, type, is_read, related_type, related_id)
                        VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                        """,
                        (
                            None,
                            sup["email"],
                            "New final submission",
                            f"{group['title']} submitted '{title}' for review.",
                            "final_submission",
                            "final_submission",
                            submission_id,
                        ),
                    )
            conn.commit()

        # Ensure demo student account can read meeting notes for at least one group
        cursor.execute(
            """
            SELECT COUNT(*) FROM fyp_groups
            WHERE supervisor_id = ? AND LOWER(TRIM(student_contact_email)) = LOWER(?)
            """,
            (supervisor_id, "student@comsats.edu.pk"),
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                """
                UPDATE fyp_groups
                SET student_contact_email = ?
                WHERE supervisor_id = ? AND title = 'Gamma Group'
                """,
                ("student@comsats.edu.pk", supervisor_id),
            )
            conn.commit()

        # Seed demo meeting notes (ensure each of first 3 groups has at least one)
        cursor.execute(
            """
            SELECT id, title FROM fyp_groups
            WHERE supervisor_id = ? AND status = 'accepted'
            ORDER BY id ASC
            """,
            (supervisor_id,),
        )
        note_groups = [dict(r) for r in cursor.fetchall()]
        from datetime import date, timedelta

        today = date.today()
        demo_notes = [
            (
                "Progress checkpoint - proposal scope",
                "1. Finalize problem statement\n2. Share literature list by Friday\n3. Book next meeting",
                today - timedelta(days=2),
            ),
            (
                "Literature review feedback",
                "1. Expand related-work section\n2. Cite at least 8 peer-reviewed sources\n3. Bring draft outline next week",
                today - timedelta(days=9),
            ),
            (
                "Kickoff and timeline",
                "1. Confirm milestones\n2. Share draft outline\n3. Set next meeting date",
                today - timedelta(days=1),
            ),
        ]
        inserted_notes = False
        for index, group in enumerate(note_groups[:3]):
            cursor.execute(
                "SELECT COUNT(*) FROM meeting_notes WHERE group_id = ?",
                (group["id"],),
            )
            if cursor.fetchone()[0] > 0:
                continue
            topic, actions, meeting_day = demo_notes[index % len(demo_notes)]
            cursor.execute(
                """
                INSERT INTO meeting_notes
                    (group_id, supervisor_id, meeting_date, topic, action_items)
                VALUES (?, ?, ?, ?, ?)
                """,
                (group["id"], supervisor_id, meeting_day.isoformat(), topic, actions),
            )
            inserted_notes = True
        if inserted_notes:
            conn.commit()

    conn.close()
    print("Database tables initialized and seeded successfully.")

    from vc.database import init_vc_tables
    init_vc_tables()
