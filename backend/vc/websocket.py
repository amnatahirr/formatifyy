"""WebSocket connection manager for real-time collaboration updates."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Set

from fastapi import WebSocket


class VCConnectionManager:
    def __init__(self) -> None:
        self._connections: Dict[int, List[WebSocket]] = {}
        self._user_projects: Dict[WebSocket, tuple[int, int]] = {}

    async def connect(self, websocket: WebSocket, project_id: int, user_id: int) -> None:
        await websocket.accept()
        self._connections.setdefault(project_id, []).append(websocket)
        self._user_projects[websocket] = (project_id, user_id)

    def disconnect(self, websocket: WebSocket) -> None:
        meta = self._user_projects.pop(websocket, None)
        if not meta:
            return
        project_id, _ = meta
        conns = self._connections.get(project_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns and project_id in self._connections:
            del self._connections[project_id]

    async def broadcast(self, project_id: int, message: Dict[str, Any]) -> None:
        payload = json.dumps(message)
        dead: List[WebSocket] = []
        for ws in self._connections.get(project_id, []):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def online_user_ids(self, project_id: int) -> Set[int]:
        ids: Set[int] = set()
        for ws in self._connections.get(project_id, []):
            meta = self._user_projects.get(ws)
            if meta:
                ids.add(meta[1])
        return ids


vc_manager = VCConnectionManager()
