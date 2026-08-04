import json
import os
import time
import threading
from typing import List, Any, Optional
from fastapi import WebSocket

_SF_DIR = os.path.expanduser("~/.cogitator")
os.makedirs(_SF_DIR, exist_ok=True)

_lock = threading.Lock()

# Pipeline status storage (shared state)
pipeline_status = {
    "running": False,
    "current_phase": None,
    "progress": 0,
    "message": "Idle",
    "last_run": None,
    "error": None
}


def update_pipeline_status(**kwargs):
    """Thread-safe pipeline status update."""
    with _lock:
        pipeline_status.update(kwargs)


def get_pipeline_status() -> dict:
    """Thread-safe pipeline status read."""
    with _lock:
        return dict(pipeline_status)


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass  # Connection likely closed; will be cleaned up on disconnect


manager = ConnectionManager()
