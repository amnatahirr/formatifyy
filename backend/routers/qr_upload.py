from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
import uuid
import os
from datetime import datetime, timedelta
from database import get_db
from dotenv import load_dotenv
import qrcode
from io import BytesIO
import base64

load_dotenv()

router = APIRouter(prefix="/qr/upload", tags=["QR Uploads"])

LOCALHOST = os.getenv("LOCALHOST")

UPLOAD_DIR = "uploads/phone_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/generate")
def generate_upload_qr(
    user_id: int = Form(...),
    template_id: int = Form(...),
    host: str = Form(None)
):
    session_id = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO qr_upload_sessions (id, user_id, template_id, expires_at)
        VALUES (?, ?, ?, ?)
    """, (session_id, user_id, template_id, expires_at))

    conn.commit()
    conn.close()

    # Use provided host or env fallback
    backend_host = host or LOCALHOST or "172.20.10.2:8000"

    # 🔗 Deep link that opens the Formatify mobile app directly
    deep_link = f"formatify://qr-upload?session={session_id}&host={backend_host}"

    # 🧠 Generate QR image encoding the deep link
    qr = qrcode.make(deep_link)
    buffer = BytesIO()
    # pyrefly: ignore [unexpected-keyword]
    qr.save(buffer, format="PNG")

    qr_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return {
        "session_id": session_id,
        "deep_link": deep_link,
        "qr_base64": qr_base64,
        "expires_at": expires_at.isoformat()
    }

@router.get("/{session_id}")
def upload_page(session_id: str):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM qr_upload_sessions
        WHERE id = ? AND expires_at > CURRENT_TIMESTAMP
    """, (session_id,))
    session = cursor.fetchone()
    conn.close()

    if not session:
        raise HTTPException(status_code=404, detail="QR expired or invalid")

    return {
        "session_id": session_id,
        "user_id": session["user_id"],
        "template_id": session["template_id"],
        "status": "valid"
    }

@router.post("/{session_id}/file")
async def upload_file(session_id: str, file: UploadFile = File(...)):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM qr_upload_sessions
        WHERE id = ? AND expires_at > CURRENT_TIMESTAMP
    """, (session_id,))
    session = cursor.fetchone()

    if not session:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid or expired QR")

    filename = f"{session_id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Create document entry
    cursor.execute("""
        INSERT INTO documents (user_id, template_id, filename, file_path, status)
        VALUES (?, ?, ?, ?, 'uploaded')
    """, (
        session["user_id"],
        session["template_id"],
        file.filename,
        file_path
    ))

    # Update QR session
    cursor.execute("""
        UPDATE qr_upload_sessions
        SET status = 'uploaded', uploaded_file_path = ?
        WHERE id = ?
    """, (file_path, session_id))

    conn.commit()
    conn.close()

    return JSONResponse({
        "message": "File uploaded successfully.",
        "filename": file.filename,
    })
