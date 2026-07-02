from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Form
from fastapi.responses import FileResponse, JSONResponse
import os
import shutil
from datetime import datetime
from database import get_db
from config import settings
from services.google_drive_service import GoogleDriveService
import json
import requests
from io import BytesIO
from fastapi import Request

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(settings.SYNC_FOLDER, exist_ok=True)


# ========================================
# LOCAL FILE UPLOAD
# ========================================

@router.post("/local-upload")
async def upload_local_file(
    file: UploadFile = File(...),
    user_id: int = Query(...),
    template_id: int = Query(...),
    session_id: str = Query(None)
):
    """Upload file from local storage"""
    try:
        # Validate user
        conn = get_db()
        user = conn.execute(
            "SELECT id FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        
        if not user:
            conn.close()
            raise HTTPException(status_code=401, detail="User not found")
        
        # Validate template
        template = conn.execute(
            "SELECT id FROM templates WHERE id = ?",
            (template_id,)
        ).fetchone()
        
        if not template:
            conn.close()
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Save file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stored_filename = f"local_{timestamp}_{file.filename}"
        file_path = os.path.join(settings.UPLOAD_FOLDER, stored_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Create document record
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO documents (user_id, template_id, filename, file_path, status)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, template_id, file.filename, file_path, "pending"))
        
        conn.commit()
        document_id = cursor.lastrowid
        
        # Create sync status record
        cursor.execute("""
            INSERT INTO file_sync_status (document_id, user_id, source, sync_status, local_path)
            VALUES (?, ?, ?, ?, ?)
        """, (document_id, user_id, "local", "synced", file_path))
        
        conn.commit()
        conn.close()
        
        print(f"[v0] Local file uploaded: {file.filename} (doc_id: {document_id})")
        
        # Mark session as complete if provided
        if session_id:
            QRCodeService.mark_session_complete(session_id)
        
        return {
            "success": True,
            "document_id": document_id,
            "filename": file.filename,
            "source": "local",
            "status": "pending"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[v0] Local upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# GOOGLE DRIVE INTEGRATION
# ========================================

@router.post("/google-drive/auth/init")
async def initialize_google_drive_auth(user_id: int = Query(...)):
    """Check if Google Drive tokens exist for user"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get user's email from users table
        user = cursor.execute(
            "SELECT email FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        
        if not user:
            conn.close()
            raise HTTPException(status_code=404, detail="User not found")
        
        user_email = user["email"]
        
        # Check if Google Drive tokens exist
        token_record = cursor.execute(
            "SELECT access_token FROM google_drive_tokens WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        
        is_authorized = token_record is not None
        
        print(f"[v0] Google Drive check for user {user_id} ({user_email}). Has tokens: {is_authorized}")
        
        conn.close()
        
        if not is_authorized:
            raise HTTPException(status_code=401, detail="Google Drive not authorized. Please connect via OAuth.")
        
        return {
            "success": True,
            "user_id": user_id,
            "email": user_email,
            "authorized": is_authorized,
            "message": f"Google Drive authorized for {user_email}"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[v0] Google Drive check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/google-drive/authorize")
async def authorize_google_drive(user_id: int = Query(...)):
    """Get Google Drive OAuth URL for user"""
    try:
        from urllib.parse import urlencode
        
        client_id = settings.GOOGLE_DRIVE_CLIENT_ID
        redirect_uri = f"{settings.API_URL}/api/uploads/google-drive/callback?user_id={user_id}"
        
        scope = "https://www.googleapis.com/auth/drive"
        
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"response_type=code&"
            f"scope={scope}&"
            f"access_type=offline&"
        )
        
        return {
            "success": True,
            "auth_url": auth_url,
            "user_id": user_id
        }
    except Exception as e:
        print(f"[v0] Google Drive auth error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/google-drive/callback")
async def google_drive_callback(code: str = Query(...), user_id: int = Query(...)):
    """Handle Google Drive OAuth callback"""
    try:
        from google.oauth2.service_account import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        import requests
        
        # Exchange authorization code for tokens
        token_endpoint = "https://oauth2.googleapis.com/token"
        
        payload = {
            "client_id": settings.GOOGLE_DRIVE_CLIENT_ID,
            "client_secret": settings.GOOGLE_DRIVE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": f"{settings.API_URL}/api/uploads/google-drive/callback?user_id={user_id}"
        }
        
        response = requests.post(token_endpoint, data=payload)
        
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Failed to authenticate with Google")
        
        tokens = response.json()
        
        # Save tokens to database
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO google_drive_tokens 
            (user_id, access_token, refresh_token, token_expiry, created_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            user_id,
            tokens.get('access_token'),
            tokens.get('refresh_token'),
            None  # Can be calculated from expires_in
        ))
        
        conn.commit()
        conn.close()
        
        print(f"[v0] Google Drive OAuth successful for user {user_id}")
        
        # Redirect to app with success message
        return {
            "success": True,
            "message": "Google Drive connected successfully!",
            "user_id": user_id
        }
        
    except Exception as e:
        print(f"[v0] Google Drive callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# FIXED: Google Drive Files List Endpoint
# ========================================

@router.get("/google-drive/files")
async def list_google_drive_files(
    user_id: int = Query(...),  # FIXED: Accept user_id as query parameter instead of session cookie
    query: str = Query(None)
):
    """List files from user's Google Drive"""
    try:
        # Validate user exists
        conn = get_db()
        user = conn.execute(
            "SELECT id FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        
        if not user:
            conn.close()
            raise HTTPException(status_code=401, detail="User not found")
        
        conn.close()

        # Initialize Google Drive service with user_id
        service = GoogleDriveService(user_id)

        if not service.initialize_service():
            raise HTTPException(
                status_code=401,
                detail="Google Drive not authorized. Please authorize first."
            )

        files = service.list_files(query=query)
        
        print(f"[v0] Listed {len(files)} files from Google Drive for user {user_id}")

        return {"success": True, "files": files}

    except HTTPException:
        raise
    except Exception as e:
        print(f"[v0] Google Drive list error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/google-drive/import")
async def import_from_google_drive(
    user_id: int = Query(...),
    file_id: str = Query(...),
    template_id: int = Query(...),
    session_id: str = Query(None)
):
    """Import a file from Google Drive"""
    try:
        # Validate user and template
        conn = get_db()
        user = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        template = conn.execute("SELECT id FROM templates WHERE id = ?", (template_id,)).fetchone()
        
        if not user or not template:
            conn.close()
            raise HTTPException(status_code=404, detail="User or template not found")
        
        # Download from Google Drive
        service = GoogleDriveService(user_id)
        
        
        # Get file metadata
        if not service.initialize_service():
            raise HTTPException(status_code=401, detail="Google Drive not authorized")
        
        try:
            file_metadata = service.service.files().get(
                fileId=file_id,
                fields='name'
            ).execute()
            filename = file_metadata.get('name', f'gdrive_{file_id}')
        except:
            filename = f'gdrive_{file_id}'
        
        # Download file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stored_filename = f"gdrive_{timestamp}_{filename}"
        file_path = os.path.join(settings.UPLOAD_FOLDER, stored_filename)
        
        if not service.download_file(file_id, file_path):
            conn.close()
            raise HTTPException(status_code=500, detail="Failed to download file")
        
        # Create document record
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO documents (user_id, template_id, filename, file_path, status)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, template_id, filename, file_path, "pending"))
        
        conn.commit()
        document_id = cursor.lastrowid
        
        # Create sync status record
        cursor.execute("""
            INSERT INTO file_sync_status (document_id, user_id, source, sync_status, google_drive_id)
            VALUES (?, ?, ?, ?, ?)
        """, (document_id, user_id, "google_drive", "synced", file_id))
        
        conn.commit()
        conn.close()
        
        print(f"[v0] File imported from Google Drive: {filename} (doc_id: {document_id})")
        
        # Mark session as complete if provided
        if session_id:
            QRCodeService.mark_session_complete(session_id)
        
        return {
            "success": True,
            "document_id": document_id,
            "filename": filename,
            "source": "google_drive",
            "google_drive_id": file_id,
            "status": "pending"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[v0] Google Drive import error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/google-drive/export")
async def export_to_google_drive(
    user_id: int = Query(...),
    document_id: int = Query(...),
    folder_id: str = Query(None)
):
    """Export a formatted document to Google Drive"""
    try:
        conn = get_db()
        
        # Validate document
        doc = conn.execute(
            "SELECT file_path, filename FROM documents WHERE id = ? AND user_id = ?",
            (document_id, user_id)
        ).fetchone()
        
        if not doc:
            conn.close()
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Upload to Google Drive
        service = GoogleDriveService(user_id)
        
        if not service.initialize_service():
            conn.close()
            raise HTTPException(status_code=401, detail="Google Drive not authorized")
        
        uploaded_file = service.upload_file(
            doc['file_path'],
            f"Formatted_{doc['filename']}",
            folder_id or settings.GOOGLE_DRIVE_FOLDER_ID
        )
        
        if not uploaded_file:
            conn.close()
            raise HTTPException(status_code=500, detail="Failed to upload to Google Drive")
        
        # Update sync status
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE file_sync_status 
            SET google_drive_id = ?, sync_status = 'synced', last_synced = CURRENT_TIMESTAMP
            WHERE document_id = ?
        """, (uploaded_file.get('id'), document_id))
        
        conn.commit()
        conn.close()
        
        print(f"[v0] Document exported to Google Drive: {uploaded_file.get('id')}")
        
        return {
            "success": True,
            "document_id": document_id,
            "google_drive_id": uploaded_file.get('id'),
            "web_view_link": uploaded_file.get('webViewLink'),
            "source": "google_drive"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[v0] Google Drive export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ========================================
# REAL-TIME SYNC STATUS
# ========================================

@router.get("/sync-status/{document_id}")
async def get_sync_status(document_id: int, user_id: int = Query(...)):
    """Get real-time sync status for a document"""
    try:
        conn = get_db()
        
        sync_status = conn.execute("""
            SELECT sync_status, source, google_drive_id, last_synced
            FROM file_sync_status
            WHERE document_id = ? AND user_id = ?
        """, (document_id, user_id)).fetchone()
        
        if not sync_status:
            conn.close()
            return {
                "document_id": document_id,
                "sync_status": "unknown",
                "source": None
            }
        
        # Also get document status
        doc = conn.execute(
            "SELECT status FROM documents WHERE id = ?",
            (document_id,)
        ).fetchone()
        
        conn.close()
        
        return {
            "document_id": document_id,
            "sync_status": sync_status['sync_status'],
            "source": sync_status['source'],
            "document_status": doc['status'] if doc else "unknown",
            "google_drive_id": sync_status['google_drive_id'],
            "last_synced": sync_status['last_synced']
        }
    except Exception as e:
        print(f"[v0] Sync status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user-documents")
async def get_user_documents(
    user_id: int = Query(...),
    include_sync_status: bool = Query(False)
):
    """Get all documents for a user with optional sync status"""
    try:
        conn = get_db()
        
        if include_sync_status:
            documents = conn.execute("""
                SELECT d.id, d.filename, d.status, d.created_at,
                       fs.source, fs.sync_status, fs.google_drive_id, fs.last_synced
                FROM documents d
                LEFT JOIN file_sync_status fs ON d.id = fs.document_id
                WHERE d.user_id = ?
                ORDER BY d.created_at DESC
            """, (user_id,)).fetchall()
        else:
            documents = conn.execute("""
                SELECT id, filename, status, created_at
                FROM documents
                WHERE user_id = ?
                ORDER BY created_at DESC
            """, (user_id,)).fetchall()
        
        conn.close()
        
        return {
            "success": True,
            "documents": [dict(doc) for doc in documents]
        }
    except Exception as e:
        print(f"[v0] Get documents error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/download-from-google-drive")
async def download_from_google_drive(
    user_id: int = Query(...),
    file_id: str = Query(...),
    filename: str = Query(...),
    template_id: int = Query(...)
):
    """Download a file from Google Drive and save it to documents"""
    try:
        print(f"[v0] Downloading file {file_id} from Google Drive for user {user_id}")
        
        # Get user's Google Drive tokens
        conn = get_db()
        cursor = conn.cursor()
        
        token_row = cursor.execute(
            "SELECT access_token, refresh_token FROM google_drive_tokens WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        
        if not token_row:
            conn.close()
            raise HTTPException(status_code=401, detail="Google Drive not authorized")
        
        access_token = token_row["access_token"]
        
        # Download file from Google Drive
        download_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        response = requests.get(download_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"[v0] Failed to download file from Drive: {response.status_code}")
            conn.close()
            raise HTTPException(status_code=500, detail="Failed to download file from Google Drive")
        
        # Save file to upload folder
        file_content = response.content
        file_extension = os.path.splitext(filename)[1].lower()
        
        # Validate file type
        if file_extension not in ['.pdf', '.docx', '.doc']:
            conn.close()
            raise HTTPException(status_code=400, detail="Only .pdf and .docx files are supported")
        
        # Create unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(settings.UPLOAD_FOLDER, safe_filename)
        
        # Save file
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        print(f"[v0] File saved to {file_path} ({len(file_content)} bytes)")
        
        # Create document record
        cursor.execute("""
            INSERT INTO documents (user_id, template_id, filename, file_path, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'uploaded', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (user_id, template_id, filename, file_path))
        
        document_id = cursor.lastrowid
        
        # Record sync status
        cursor.execute("""
            INSERT INTO file_sync_status (document_id, user_id, source, sync_status, google_drive_id, last_synced, created_at)
            VALUES (?, ?, 'google_drive', 'synced', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (document_id, user_id, file_id))
        
        conn.commit()
        conn.close()
        
        print(f"[v0] Document created with ID {document_id} from Google Drive file {file_id}")
        
        return {
            "success": True,
            "document_id": document_id,
            "filename": filename,
            "file_path": file_path,
            "source": "google_drive"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[v0] Download from Google Drive error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
