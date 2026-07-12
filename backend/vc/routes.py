"""FastAPI routes for the Version Control & Collaboration module."""

from __future__ import annotations

import os
import shutil
import uuid
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from vc.models import (
    CommitRequest,
    InviteMemberRequest,
    JoinProjectRequest,
    ResolveConflictRequest,
    RollbackRequest,
)
from vc.service import (
    complete_merge,
    create_commit,
    create_project_with_document,
    delete_section_image,
    get_merge_status,
    get_project_detail,
    get_project_history,
    get_section_history,
    get_section_image_path,
    invite_member_by_email,
    join_project_by_invite,
    list_section_images,
    list_user_projects,
    resolve_conflict,
    resolve_project_download,
    rollback_section,
    start_merge,
    upload_project_document,
    upload_section_image,
    VC_UPLOAD_DIR,
)
from vc.websocket import vc_manager

router = APIRouter(prefix="/api/vc", tags=["Version Control"])

_analysis_runner: Optional[Callable] = None


def set_analysis_runner(fn: Callable) -> None:
    global _analysis_runner
    _analysis_runner = fn


@router.post("/projects")
async def api_create_project(
    user_id: int = Query(...),
    name: str = Form(...),
    description: str = Form(""),
    template_id: int = Form(...),
    file: UploadFile = File(None),
):
    """Create a project with optional base .docx upload."""
    docx_path = None
    if file and file.filename:
        if not file.filename.lower().endswith(".docx"):
            raise HTTPException(status_code=400, detail="Only .docx files are supported")
        temp_dir = os.path.join(VC_UPLOAD_DIR, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        docx_path = os.path.join(temp_dir, f"upload_{uuid.uuid4().hex[:8]}.docx")
        with open(docx_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

    return create_project_with_document(
        user_id,
        name,
        description,
        template_id,
        docx_path=docx_path,
        original_filename=file.filename if file and file.filename else None,
    )


@router.get("/projects")
async def api_list_projects(user_id: int = Query(...)):
    return {"projects": list_user_projects(user_id)}


@router.get("/projects/{project_id}")
async def api_get_project(project_id: int, user_id: int = Query(...)):
    return get_project_detail(project_id, user_id)


@router.post("/projects/{project_id}/document")
async def api_upload_project_document(
    project_id: int,
    user_id: int = Query(...),
    file: UploadFile = File(...),
):
    """Upload or re-upload a project .docx as new versioned section commits."""
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")

    temp_dir = os.path.join(VC_UPLOAD_DIR, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    docx_path = os.path.join(temp_dir, f"upload_{uuid.uuid4().hex[:8]}.docx")
    with open(docx_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        return upload_project_document(
            project_id,
            user_id,
            docx_path,
            file.filename,
        )
    finally:
        if os.path.exists(docx_path):
            try:
                os.remove(docx_path)
            except OSError:
                pass


@router.post("/projects/join")
async def api_join_project(body: JoinProjectRequest, user_id: int = Query(...)):
    return join_project_by_invite(user_id, body.invite_code)


@router.post("/projects/{project_id}/invite")
async def api_invite_member(
    project_id: int,
    body: InviteMemberRequest,
    user_id: int = Query(...),
):
    return invite_member_by_email(project_id, user_id, body.email)


@router.get("/projects/{project_id}/history")
async def api_project_history(project_id: int, user_id: int = Query(...)):
    return {"history": get_project_history(project_id, user_id)}


@router.get("/projects/{project_id}/sections/{section_id}/images")
async def api_list_section_images(
    project_id: int, section_id: str, user_id: int = Query(...)
):
    return {"images": list_section_images(project_id, section_id, user_id)}


@router.post("/projects/{project_id}/sections/{section_id}/images")
async def api_upload_section_image(
    project_id: int,
    section_id: str,
    user_id: int = Query(...),
    file: UploadFile = File(...),
):
    image = upload_section_image(project_id, section_id, user_id, file)
    return image


@router.delete("/projects/{project_id}/sections/{section_id}/images/{image_id}")
async def api_delete_section_image(
    project_id: int,
    section_id: str,
    image_id: int,
    user_id: int = Query(...),
):
    delete_section_image(project_id, section_id, image_id, user_id)
    return {"status": "deleted", "image_id": image_id}


@router.get("/projects/{project_id}/sections/{section_id}/images/{image_id}")
async def api_get_section_image(
    project_id: int,
    section_id: str,
    image_id: int,
    user_id: int = Query(...),
):
    path = get_section_image_path(project_id, section_id, image_id, user_id)
    return FileResponse(path, filename=os.path.basename(path))


@router.get("/projects/{project_id}/sections")
async def api_list_sections(project_id: int, user_id: int = Query(...)):
    from vc.service import get_sections_with_latest

    return {"sections": get_sections_with_latest(project_id)}


@router.get("/projects/{project_id}/sections/{section_id}")
async def api_get_section(project_id: int, section_id: str, user_id: int = Query(...)):
    from vc.service import get_sections_with_latest

    sections = get_sections_with_latest(project_id)
    match = next((s for s in sections if s["section_id"] == section_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Section not found")
    return match


@router.post("/projects/{project_id}/sections/{section_id}/commit")
async def api_commit_section(
    project_id: int,
    section_id: str,
    body: CommitRequest,
    user_id: int = Query(...),
):
    commit = create_commit(project_id, section_id, user_id, body.content, body.message)
    await vc_manager.broadcast(project_id, {
        "type": "section_updated",
        "project_id": project_id,
        "section_id": commit["section_id"],
        "author_id": commit["author_id"],
        "author_name": commit["author_name"],
        "version_number": commit["version_number"],
        "commit_type": commit.get("commit_type", "save"),
        "timestamp": commit.get("created_at"),
        "message": commit.get("message", ""),
    })
    return commit


@router.get("/projects/{project_id}/sections/{section_id}/history")
async def api_section_history(project_id: int, section_id: str, user_id: int = Query(...)):
    return {"history": get_section_history(project_id, section_id, user_id)}


@router.post("/projects/{project_id}/sections/{section_id}/rollback")
async def api_rollback_section(
    project_id: int,
    section_id: str,
    body: RollbackRequest,
    user_id: int = Query(...),
):
    commit = rollback_section(project_id, section_id, user_id, body.commit_id)
    await vc_manager.broadcast(project_id, {
        "type": "section_updated",
        "project_id": project_id,
        "section_id": commit["section_id"],
        "author_id": commit["author_id"],
        "author_name": commit["author_name"],
        "version_number": commit["version_number"],
        "commit_type": "rollback",
        "timestamp": commit.get("created_at"),
        "message": commit.get("message", ""),
    })
    return commit


@router.post("/projects/{project_id}/merge")
async def api_start_merge(project_id: int, user_id: int = Query(...)):
    return start_merge(project_id, user_id)


@router.get("/projects/{project_id}/merge/{merge_id}")
async def api_merge_status(project_id: int, merge_id: int, user_id: int = Query(...)):
    return get_merge_status(project_id, merge_id, user_id)


@router.post("/projects/{project_id}/merge/{merge_id}/resolve/{conflict_id}")
async def api_resolve_conflict(
    project_id: int,
    merge_id: int,
    conflict_id: int,
    body: ResolveConflictRequest,
    user_id: int = Query(...),
):
    return resolve_conflict(project_id, merge_id, conflict_id, user_id, body.resolution_content)


@router.post("/projects/{project_id}/merge/{merge_id}/complete")
async def api_complete_merge(
    project_id: int,
    merge_id: int,
    user_id: int = Query(...),
):
    if _analysis_runner is None:
        raise HTTPException(status_code=500, detail="Analysis pipeline not configured")
    return await complete_merge(project_id, merge_id, user_id, _analysis_runner)


@router.get("/projects/{project_id}/download")
async def api_download_merged(
    project_id: int,
    user_id: int = Query(...),
    merge_id: int = Query(None),
):
    resolved = resolve_project_download(project_id, user_id, merge_id)
    return FileResponse(
        resolved["path"],
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=resolved["filename"],
    )


@router.websocket("/ws/projects/{project_id}")
async def vc_websocket(websocket: WebSocket, project_id: int, user_id: int = Query(...)):
    from vc.service import _require_member

    try:
        _require_member(project_id, user_id)
    except HTTPException:
        await websocket.close(code=4003)
        return

    await vc_manager.connect(websocket, project_id, user_id)
    online = sorted(vc_manager.online_user_ids(project_id))
    await vc_manager.broadcast(project_id, {
        "type": "member_joined",
        "project_id": project_id,
        "user_id": user_id,
        "online_count": len(online),
        "online_user_ids": online,
    })

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        vc_manager.disconnect(websocket)
        online = sorted(vc_manager.online_user_ids(project_id))
        await vc_manager.broadcast(project_id, {
            "type": "member_left",
            "project_id": project_id,
            "user_id": user_id,
            "online_count": len(online),
            "online_user_ids": online,
        })
