from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
import uuid
import qrcode
import base64
from io import BytesIO
from database import get_db
import os
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("LOCALHOST", "172.20.10.2:8000") 

router = APIRouter(prefix="/qr", tags=["QR Download"])

@router.post("/generate")
def generate_qr(data: dict):
    """
    Expected body:
    {
        "document_id": 1,
        "file_type": "pdf"
    }
    """
    document_id = data.get("document_id")
    file_type = data.get("file_type")
    host = data.get("host") or BASE_URL

    if file_type not in ["pdf", "docx"]:
        raise HTTPException(status_code=400, detail="Invalid file type")

    conn = get_db()
    cursor = conn.cursor()

    # Get document file path
    cursor.execute(
        "SELECT file_path FROM documents WHERE id = ?",
        (document_id,)
    )
    doc = cursor.fetchone()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Generate QR code pointing to download endpoint
    qr_id = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(minutes=5)

    # Insert into qr_downloads table
    cursor.execute(
        """
        INSERT INTO qr_downloads (id, document_id, file_type, expires_at, used)
        VALUES (?, ?, ?, ?, 0)
        """,
        (qr_id, document_id, file_type, expires_at)
    )
    conn.commit()
    conn.close()

    # QR deep link that opens the Formatify mobile app
    qr_data = f"formatify://qr-download?id={qr_id}&host={host}"

    # Generate QR image
    qr = qrcode.QRCode(box_size=8, border=4)
    qr.add_data(qr_data)

    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")


    # Convert to base64
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode()
    print("QR generated for doc:", document_id, "Length:", len(qr_base64))

    return {
        "qr_base64": qr_base64,
        "qr_id": qr_id,
        "deep_link": qr_data,
        "expires_at": expires_at.isoformat()
    }
    




@router.get("/download/{qr_id}")
def download_via_qr(qr_id: str):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT q.used, q.expires_at, d.file_path
        FROM qr_downloads q
        JOIN documents d ON q.document_id = d.id
        WHERE q.id = ?
        """,
        (qr_id,)
    )
    row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Invalid QR")

    if row["used"]:
        raise HTTPException(status_code=410, detail="QR already used")

    if datetime.fromisoformat(row["expires_at"]) < datetime.utcnow():
        raise HTTPException(status_code=410, detail="QR expired")

    file_path = row["file_path"]

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    # Mark QR as used
    cursor.execute(
        "UPDATE qr_downloads SET used = 1 WHERE id = ?",
        (qr_id,)
    )
    conn.commit()
    conn.close()

    return FileResponse(
        path=file_path,
        filename=os.path.basename(file_path),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{os.path.basename(file_path)}"'
        }
    )
