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

    conn.close()
    print("Database tables initialized and seeded successfully.")
