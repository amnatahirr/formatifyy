import os
import io
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from database import get_db
from config import settings

SCOPES = ["https://www.googleapis.com/auth/drive"]

class GoogleDriveService:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.service = None
        self.credentials = None

    # ==============================
    # CREDENTIAL HANDLING
    # ==============================

    def _load_tokens_from_db(self):
        conn = get_db()
        token = conn.execute(
            """
            SELECT access_token, refresh_token, token_expiry
            FROM google_drive_tokens
            WHERE user_id = ?
            """,
            (self.user_id,)
        ).fetchone()
        conn.close()
        return token

    def _save_tokens_to_db(self, credentials: Credentials):
        conn = get_db()
        conn.execute(
            """
            INSERT OR REPLACE INTO google_drive_tokens
            (user_id, access_token, refresh_token, token_expiry, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                self.user_id,
                credentials.token,
                credentials.refresh_token,
                credentials.expiry.isoformat() if credentials.expiry else None
            )
        )
        conn.commit()
        conn.close()

    def _parse_token_expiry(self, token_expiry):
        """Parse token expiry from various formats"""
        if token_expiry is None:
            return None
        
        # Already a datetime object
        if isinstance(token_expiry, datetime):
            return token_expiry
        
        # String format - try parsing
        if isinstance(token_expiry, str):
            # Try ISO format first (e.g., "2024-01-27T12:34:56")
            try:
                return datetime.fromisoformat(token_expiry)
            except ValueError:
                pass
            
            # Try SQLite datetime format (e.g., "2024-01-27 12:34:56")
            try:
                return datetime.strptime(token_expiry, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
            
            # Try with microseconds
            try:
                return datetime.strptime(token_expiry, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                pass
        
        # Integer/float timestamp
        if isinstance(token_expiry, (int, float)):
            try:
                return datetime.fromtimestamp(token_expiry)
            except (ValueError, OSError):
                pass
        
        print(f"[v0] Warning: Could not parse token_expiry: {token_expiry} (type: {type(token_expiry)})")
        return None

    def get_credentials(self):
        token = self._load_tokens_from_db()
        if not token:
            print(f"[v0] No tokens found in DB for user {self.user_id}")
            return None

        access_token = token["access_token"]
        refresh_token = token["refresh_token"]
        token_expiry_raw = token["token_expiry"]
        
        print(f"[v0] Loaded tokens for user {self.user_id}")
        print(f"[v0] Token expiry raw value: {token_expiry_raw} (type: {type(token_expiry_raw)})")

        credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_DRIVE_CLIENT_ID,
            client_secret=settings.GOOGLE_DRIVE_CLIENT_SECRET,
            scopes=SCOPES,
        )

        # Parse token expiry with type handling
        token_expiry = self._parse_token_expiry(token_expiry_raw)
        if token_expiry:
            credentials.expiry = token_expiry

        if credentials.expired and refresh_token:
            print(f"[v0] Token expired, refreshing...")
            credentials.refresh(Request())
            self._save_tokens_to_db(credentials)
            print(f"[v0] Token refreshed successfully")

        return credentials

    # ==============================
    # SERVICE INITIALIZATION
    # ==============================

    def initialize_service(self) -> bool:
        credentials = self.get_credentials()
        if not credentials:
            return False

        self.credentials = credentials
        self.service = build("drive", "v3", credentials=credentials)
        return True

    def list_files(self, query: str = None, page_size: int = 20):
        if not self.initialize_service():
            return None

        q = query or "trashed = false and mimeType != 'application/vnd.google-apps.folder'"

        results = self.service.files().list(
            q=q,
            pageSize=page_size,
            fields="files(id, name, mimeType, size, webViewLink, modifiedTime)"
        ).execute()

        return results.get("files", [])

    def upload_file(self, file_path: str, name: str, folder_id: str = None):
        if not self.initialize_service():
            return None

        file_metadata = {"name": name}
        if folder_id:
            file_metadata["parents"] = [folder_id]

        media = MediaFileUpload(file_path, resumable=True)

        return self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, webViewLink"
        ).execute()

    def delete_file(self, file_id: str) -> bool:
        if not self.initialize_service():
            return False

        self.service.files().delete(fileId=file_id).execute()
        return True
