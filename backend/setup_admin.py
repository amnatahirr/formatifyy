#!/usr/bin/env python3
"""
Setup script for Admin Panel and Template Management System.
Run this to:
1. Initialize database with updated schema
2. Create default university
3. Create admin user
"""

import sqlite3
import bcrypt
from datetime import datetime

DATABASE_URL = "formatify.db"

def create_admin_user(conn, username, email, password, university_id):
    """Create an admin user"""
    cursor = conn.cursor()
    
    # Hash password
    hashed_password = bcrypt.hashpw(
        password.encode('utf-8'), 
        bcrypt.gensalt()
    ).decode('utf-8')
    
    try:
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, university_id, role)
            VALUES (?, ?, ?, ?, ?)
        """, (username, email, hashed_password, university_id, "admin"))
        conn.commit()
        print(f"✓ Admin user created: {email}")
        return cursor.lastrowid
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed: users.email" in str(e):
            print(f"⚠ Admin user already exists: {email}")
            return None
        raise

def create_university(conn, name, country):
    """Create a university"""
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO universities (name, country)
            VALUES (?, ?)
        """, (name, country))
        conn.commit()
        print(f"✓ University created: {name}")
        return cursor.lastrowid
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed: universities.name" in str(e):
            # Get existing university ID
            result = cursor.execute(
                "SELECT id FROM universities WHERE name = ?", 
                (name,)
            ).fetchone()
            print(f"⚠ University already exists: {name}")
            return result[0] if result else None
        raise

def create_sample_template(conn, university_id, admin_id):
    """Create a sample template"""
    cursor = conn.cursor()
    
    import json
    
    template_data = {
        "name": "COMSATS Standard Report Format",
        "required_sections": ["Abstract", "Introduction", "Methodology", "Results", "Conclusion", "References"],
        "formatting_rules": {
            "heading1_font": "Times New Roman",
            "heading1_size": 18,
            "heading1_bold": True,
            "heading1_line_spacing": 1.5,
            "heading1_space_before": 12.0,
            "heading1_space_after": 6.0,
            
            "heading2_font": "Times New Roman",
            "heading2_size": 16,
            "heading2_bold": True,
            "heading2_line_spacing": 1.5,
            "heading2_space_before": 10.0,
            "heading2_space_after": 5.0,
            
            "heading3_font": "Times New Roman",
            "heading3_size": 14,
            "heading3_bold": True,
            "heading3_line_spacing": 1.5,
            "heading3_space_before": 8.0,
            "heading3_space_after": 4.0,
            
            "body_font": "Times New Roman",
            "body_size": 12,
            "body_line_spacing": 1.5,
            "body_space_before": 0.0,
            "body_space_after": 0.0,
            
            "bullet_font": "Times New Roman",
            "bullet_size": 12,
            "bullet_line_spacing": 1.5,
            "bullet_indent": 0.5,
            "bullet_space_before": 0.0,
            "bullet_space_after": 0.0,
            
            "margin_top": 1.0,
            "margin_bottom": 1.0,
            "margin_left": 1.0,
            "margin_right": 1.0,
            
            "page_size": "A4",
            "line_number_enabled": False,
            "first_line_indent": 0.5
        }
    }
    
    try:
        cursor.execute("""
            INSERT INTO templates (
                university_id, name, required_sections, 
                formatting_rules, created_by
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            university_id,
            template_data["name"],
            json.dumps(template_data["required_sections"]),
            json.dumps(template_data["formatting_rules"]),
            admin_id
        ))
        conn.commit()
        print(f"✓ Sample template created: {template_data['name']}")
        return cursor.lastrowid
    except Exception as e:
        print(f"⚠ Could not create sample template: {e}")
        return None

def init_db():
    """Initialize database with updated schema"""
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("Initializing database...")
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'student',
            university_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("✓ Users table ready")
    
    # Universities table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS universities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            country TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("✓ Universities table ready")
    
    # Templates table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            university_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            required_sections TEXT,
            formatting_rules TEXT,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (university_id) REFERENCES universities(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    print("✓ Templates table ready")
    
    # Documents table
    cursor.execute('''
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
    ''')
    print("✓ Documents table ready")
    
    # Image analysis table
    cursor.execute('''
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
    ''')
    print("✓ Image analysis table ready")
    
    conn.commit()
    return conn

def main():
    """Main setup function"""
    print("\n" + "="*60)
    print("FORMATIFY Admin Panel Setup")
    print("="*60 + "\n")
    
    # Initialize database
    conn = init_db()
    
    # Create default university
    print("\nCreating default university...")
    university_id = create_university(conn, "COMSATS University Islamabad", "Pakistan")
    
    # Create admin user
    print("\nCreating admin user...")
    admin_id = create_admin_user(
        conn,
        username="admin",
        email="admin@comsats.edu.pk",
        password="admin123",  # Change this!
        university_id=university_id
    )
    
    # Create sample template
    if admin_id:
        print("\nCreating sample template...")
        create_sample_template(conn, university_id, admin_id)
    
    conn.close()
    
    print("\n" + "="*60)
    print("✓ Setup Complete!")
    print("="*60)
    print("\nLogin Credentials:")
    print(f"  Email: admin@comsats.edu.pk")
    print(f"  Password: admin123")
    print("\n⚠ IMPORTANT: Change the admin password in production!")
    print("\nNext steps:")
    print("  1. Start backend: python main.py")
    print("  2. Start Flutter: flutter run")
    print("  3. Login with admin credentials")
    print("  4. Create your own templates\n")

if __name__ == "__main__":
    main()
