import os
from typing import List
from dotenv import load_dotenv
load_dotenv()

class Settings:
    # Database
    DATABASE_URL: str = "sqlite:///./formatify.db"
    
    # File handling
    UPLOAD_FOLDER: str = "uploads"
    ALLOWED_EXTENSIONS: List[str] = ["docx", "pdf", "doc"]
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    
    # AI/ML Models
    NLP_MODEL: str = "en_core_web_sm"  # spaCy model
    API_URL = "http://127.0.0.1:8000"
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]
    
    # OAuth Configuration
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GITHUB_CLIENT_ID: str = os.getenv("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET: str = os.getenv("GITHUB_CLIENT_SECRET", "")
    
    # OAuth Redirect URI (Flutter app custom scheme)
    OAUTH_CALLBACK_URL: str = "http://localhost:8000/oauth/callback"
    
    # Google Drive API Configuration
    GOOGLE_DRIVE_CLIENT_ID: str = os.getenv("GOOGLE_DRIVE_CLIENT_ID", "")
    GOOGLE_DRIVE_CLIENT_SECRET: str = os.getenv("GOOGLE_DRIVE_CLIENT_SECRET", "")
    GOOGLE_DRIVE_FOLDER_ID: str = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
    

    
    # File Sync Settings
    SYNC_FOLDER: str = "sync_uploads"
    MOBILE_APP_SCHEME: str = "formatify://"

settings = Settings()

# Create upload folders if they don't exist
os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(settings.SYNC_FOLDER, exist_ok=True)