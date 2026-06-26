import json
import os
import time
from typing import List, Any, Optional
from fastapi import WebSocket

_SF_DIR = os.path.expanduser("~/.cogitator")
os.makedirs(_SF_DIR, exist_ok=True)
PIPELINE_LOG_PATH = os.path.join(_SF_DIR, "pipeline.log")


# Pipeline status storage (shared state)
pipeline_status = {
    "running": False,
    "current_phase": None,
    "progress": 0,
    "message": "Idle",
    "last_run": None,
    "error": None
}


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.log_tailer = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # Start log tailer for this connection if pipeline is running
        if pipeline_status.get("running"):
            self._start_log_tailer()

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if not self.active_connections and self.log_tailer:
            self.log_tailer = None

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass  # Connection likely closed; will be cleaned up on disconnect

    def _start_log_tailer(self):
        """Start background task to tail pipeline log and broadcast over WebSocket."""
        import threading

        if self.log_tailer:
            return

        def tail_log():
            log_file = PIPELINE_LOG_PATH
            if not os.path.exists(log_file):
                self.log_tailer = None
                return

            try:
                with open(log_file, "r") as f:
                    f.seek(0, 2)
                    while self.active_connections and pipeline_status.get("running"):
                        line = f.readline()
                        if line:
                            import asyncio
                            try:
                                asyncio.get_event_loop().run_until_complete(
                                    self.broadcast({"type": "log", "data": line.strip()})
                                )
                            except Exception:
                                pass  # Broadcast failure is non-fatal
                        else:
                            time.sleep(0.5)
            except OSError:
                pass
            self.log_tailer = None

        self.log_tailer = threading.Thread(target=tail_log, daemon=True)
        self.log_tailer.start()


manager = ConnectionManager()
