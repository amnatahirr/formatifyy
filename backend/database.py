import sqlite3
import json
from datetime import datetime
import os

DATABASE_URL = "formatify.db"

def get_db():
    conn = sqlite3.connect(
        DATABASE_URL,
        check_same_thread=False,
        timeout=30
    )
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
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
    
    # Universities table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS universities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            country TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
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
    
    # Google Drive Integration table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS google_drive_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            access_token TEXT NOT NULL,
            refresh_token TEXT,
            token_expiry TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # File Sync Status table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS file_sync_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            source TEXT,
            sync_status TEXT DEFAULT 'pending',
            google_drive_id TEXT,
            local_path TEXT,
            last_synced TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # QR Download Sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS qr_downloads (
            id TEXT PRIMARY KEY,
            document_id INTEGER NOT NULL,
            file_type TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        )
    ''')
    
    # QR Upload Sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS qr_upload_sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            template_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            uploaded_file_path TEXT,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (template_id) REFERENCES templates(id)
        )
    ''')
    
    # Document Images table (for storing extracted images)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS document_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            image_path TEXT NOT NULL,
            image_filename TEXT NOT NULL,
            line_number INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()
    print("All database tables initialized successfully")


# Function to initialize just the image table (if needed separately)
def init_image_table():
    """Initialize the document_images table if it doesn't exist"""
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS document_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                image_path TEXT NOT NULL,
                image_filename TEXT NOT NULL,
                line_number INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            )
        """)
        conn.commit()
        print("Document images table initialized successfully")
    except Exception as e:
        print(f"Error initializing document_images table: {e}")
    finally:
        conn.close()