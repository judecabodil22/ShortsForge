#!/usr/bin/env python3
"""
ShortsForge Web Backend
FastAPI server for the cyberpunk web UI
"""
import os
import sys
import json
import asyncio
import time
import secrets
import re
from datetime import datetime
from typing import Optional
from pathlib import Path
from functools import wraps

# Add parent directory to path for imports
WORKSPACE = os.path.expanduser("~/ShortsForge")
sys.path.insert(0, WORKSPACE)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

# Import existing ShortsForge modules
from workflows.performance_database import (
    get_performance_stats, get_all_videos_with_metrics, get_successful_scripts,
    get_learnings, get_tts_learning_data, get_thompson_sampling_weights,
    get_variant_performance_stats, get_channel_baseline, select_content_type_70_30
)
from workflows.metrics_fetcher import get_recent_uploads, is_oauth_configured
from workflows.learning_engine import extract_script_features, get_virality_predictor
from workflows.context_manager_v2 import ContextManagerV2, get_context_manager

# ============================================================================
# SECURITY CONFIGURATION
# ============================================================================

SECRET_KEY_FILE = os.path.expanduser("~/ShortsForge/.shortsforge/api_key")

def load_or_create_api_key():
    """Load existing API key or create a new one"""
    os.makedirs(os.path.expanduser("~/ShortsForge/.shortsforge"), exist_ok=True)
    key_file = SECRET_KEY_FILE
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            return f.read().strip()
    # Generate new API key
    api_key = f"sf_{secrets.token_urlsafe(32)}"
    with open(key_file, "w") as f:
        f.write(api_key)
    os.chmod(key_file, 0o600)
    return api_key

API_KEY = load_or_create_api_key()

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

# Input sanitization
def sanitize_input(text: str, max_length: int = 10000) -> str:
    """Sanitize user input to prevent injection attacks"""
    if not text:
        return ""
    # Remove null bytes
    text = text.replace("\x00", "")
    # Trim to max length
    if len(text) > max_length:
        text = text[:max_length]
    return text

# API Key dependency
async def verify_api_key(request: Request):
    """Verify API key from header - always required for security"""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return True

from fastapi.responses import JSONResponse

app = FastAPI(title="ShortsForge API", version="2.0.0")

# Exception handler for rate limiting
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."}
    )

# Add security middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add rate limiter
app.state.limiter = limiter

# CORS - tightened for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["X-API-Key", "Content-Type", "Authorization"],
)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# Pipeline status storage
pipeline_status = {
    "running": False,
    "current_phase": None,
    "progress": 0,
    "message": "Idle",
    "last_run": None
}

# Pipeline settings storage
SETTINGS_FILE = os.path.expanduser("~/ShortsForge/.shortsforge/web_settings.json")

def load_pipeline_settings():
    """Load pipeline settings from file"""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return {
        "phases": [
            {"id": "p1", "name": "Download", "enabled": True, "video_source": "youtube"},
            {"id": "p2", "name": "Transcribe", "enabled": True},
            {"id": "p3", "name": "Scripts", "enabled": True},
            {"id": "p4", "name": "Clip", "enabled": True},
            {"id": "p5", "name": "TTS", "enabled": True},
        ]
    }

def save_pipeline_settings(settings):
    """Save pipeline settings to file"""
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f)
    except:
        pass


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/api/auth/key")
async def get_api_key():
    """Get API key for frontend authentication"""
    return {"api_key": API_KEY}


@app.get("/api/status")
async def get_status():
    """Get overall system status"""
    return {
        "pipeline": pipeline_status,
        "oauth_configured": is_oauth_configured(),
        "workspace": WORKSPACE
    }


# ---------------------------------------------------------------------------
# Pipeline Endpoints
# ---------------------------------------------------------------------------

import subprocess
import threading
import asyncio
import re

pipeline_process = None

# Phase ranges matching desktop UI
PHASE_RANGES = {
    1: (0, 10),
    2: (10, 25),
    3: (25, 40),
    4: (40, 60),
    5: (60, 80),
    6: (80, 95),
}
PHASE_LABELS = {
    1: "Download",
    2: "Transcribe",
    3: "Context",
    4: "Scripts",
    5: "Clips",
    6: "TTS",
}

STATUS_FILE = "/tmp/pipeline_status"

async def broadcast_status():
    """Broadcast current pipeline status to all connected clients"""
    await manager.broadcast({
        "type": "pipeline:status",
        "data": pipeline_status
    })

def read_status_file():
    """Read pipeline status from status file"""
    try:
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r") as f:
                return f.read().strip()
    except:
        pass
    return ""

def parse_status(status_text):
    """Parse status file to extract phase and progress"""
    if not status_text:
        return None, 0
    
    # Match pattern: "Phase X: Label (Y%)"
    phase_match = re.search(r'Phase (\d+):', status_text)
    percent_match = re.search(r'\((\d+)%\)', status_text)
    
    if phase_match and percent_match:
        phase_num = int(phase_match.group(1))
        phase_percent = int(percent_match.group(1))
        
        low, high = PHASE_RANGES.get(phase_num, (0, 100))
        overall = low + int((phase_percent / 100) * (high - low))
        
        return {
            "phase": phase_num,
            "label": PHASE_LABELS.get(phase_num, f"Phase {phase_num}"),
            "phase_percent": phase_percent,
            "overall": overall,
            "raw": status_text
        }, overall
    
    return None, 0

PIPELINE_LOG = "/tmp/pipeline.log"

def run_pipeline_async(source: str = "youtube"):
    """Run pipeline in background thread"""
    global pipeline_process
    
    WORKSPACE = os.path.expanduser("~/ShortsForge")
    
    # Clear previous log
    try:
        if os.path.exists(PIPELINE_LOG):
            os.remove(PIPELINE_LOG)
    except:
        pass
    
    # Clear status file before starting
    try:
        if os.path.exists(STATUS_FILE):
            os.remove(STATUS_FILE)
    except:
        pass
    
    if source == "local":
        cmd = [sys.executable, "workflows/shortsforge.py", "run_local", "media"]
        pipeline_status["message"] = "Processing local media..."
    else:
        cmd = [sys.executable, "workflows/shortsforge.py", "run"]
        pipeline_status["message"] = "Downloading from YouTube..."
    
    pipeline_status["running"] = True
    pipeline_status["current_phase"] = "Starting"
    pipeline_status["progress"] = 0
    pipeline_status["logs"] = []
    pipeline_status["error"] = None

    # Open log file for pipeline output
    log_file = open(PIPELINE_LOG, "w")

    # Set up environment with PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = WORKSPACE

    try:
        pipeline_process = subprocess.Popen(
            cmd,
            cwd=WORKSPACE,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=env
        )

        # Poll status file while process runs
        last_status = ""
        while pipeline_process.poll() is None:
            # Read status from file
            status_text = read_status_file()

            if status_text != last_status:
                last_status = status_text
                parsed, progress = parse_status(status_text)

                if parsed:
                    pipeline_status["current_phase"] = parsed["label"]
                    pipeline_status["progress"] = progress
                    pipeline_status["message"] = parsed["raw"]

            time.sleep(0.5)
        
        # Close log file
        log_file.close()
        log_file = None
        
        # Read final status
        status_text = read_status_file()
        parsed, progress = parse_status(status_text)
        
        # Check for errors in status
        if status_text and ("failed" in status_text.lower() or "error" in status_text.lower()):
            pipeline_status["error"] = status_text
            pipeline_status["current_phase"] = "Error"
            pipeline_status["progress"] = 0
        elif pipeline_process.returncode == 0:
            pipeline_status["current_phase"] = "Complete"
            pipeline_status["progress"] = 100
            pipeline_status["message"] = "Pipeline completed successfully"
        else:
            pipeline_status["error"] = f"Pipeline exited with code {pipeline_process.returncode}"
            pipeline_status["current_phase"] = "Failed"
            
    except Exception as e:
        pipeline_status["error"] = str(e)
        pipeline_status["message"] = f"Error: {str(e)}"
        pipeline_status["current_phase"] = "Error"
        if log_file:
            log_file.close()
            log_file = None
    finally:
        pipeline_status["running"] = False
        pipeline_process = None
        # Ensure log file is closed
        if log_file:
            try:
                log_file.close()
            except:
                pass


@app.post("/api/pipeline/run")
@limiter.limit("5/minute")
async def run_pipeline(request: Request, source: str = "youtube", _: bool = Depends(verify_api_key)):
    """Trigger pipeline run - source: 'youtube' or 'local'"""
    global pipeline_status
    
    if pipeline_status["running"]:
        return {"status": "already_running", "message": "Pipeline is already running"}
    
    thread = threading.Thread(target=run_pipeline_async, args=(source,))
    thread.daemon = True
    thread.start()
    
    return {"status": "started", "source": source}


@app.post("/api/pipeline/stop")
@limiter.limit("10/minute")
async def stop_pipeline(request: Request, _: bool = Depends(verify_api_key)):
    """Stop pipeline"""
    global pipeline_process
    
    if pipeline_process:
        pipeline_process.terminate()
        try:
            pipeline_process.wait(timeout=5)
        except:
            pipeline_process.kill()
        pipeline_process = None
    
    pipeline_status["running"] = False
    pipeline_status["message"] = "Stopped"
    
    await manager.broadcast({
        "type": "pipeline:status",
        "data": pipeline_status
    })
    
    return {"status": "stopped"}


@app.get("/api/pipeline/settings")
async def get_pipeline_settings():
    """Get pipeline settings"""
    return load_pipeline_settings()


@app.post("/api/pipeline/settings")
async def save_pipeline_settings_endpoint(settings: dict, _: bool = Depends(verify_api_key)):
    """Save pipeline settings"""
    save_pipeline_settings(settings)
    return {"status": "saved"}


@app.get("/api/pipeline/logs")
async def get_pipeline_logs():
    """Get pipeline execution logs"""
    try:
        if os.path.exists(PIPELINE_LOG):
            with open(PIPELINE_LOG, "r") as f:
                logs = f.read()
            return {"logs": logs, "exists": True}
        return {"logs": "", "exists": False}
    except Exception as e:
        return {"error": str(e)}, 500


# ---------------------------------------------------------------------------
# Metrics Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/metrics/summary")
async def get_metrics_summary():
    """Get performance summary"""
    stats = get_performance_stats()
    baseline = get_channel_baseline()
    
    return {
        "total_videos": stats.get("total_videos", 0),
        "total_scripts": stats.get("total_scripts", 0),
        "baseline": baseline,
        "learnings_count": stats.get("learnings_count", 0)
    }


@app.get("/api/metrics/videos")
async def get_video_metrics():
    """Get all videos with metrics"""
    videos = get_all_videos_with_metrics()
    return {"videos": videos}


@app.get("/api/metrics/content-performance")
async def get_content_performance():
    """Get content type performance stats"""
    return get_variant_performance_stats()


@app.post("/api/metrics/sync")
@limiter.limit("1/minute")
async def sync_youtube_metrics(request: Request, _: bool = Depends(verify_api_key)):
    """Trigger YouTube metrics sync - rate limited"""
    try:
        videos = get_recent_uploads(days=7, max_results=50)
        
        from workflows.performance_database import auto_match_and_fetch
        result = auto_match_and_fetch(videos)
        
        await manager.broadcast({
            "type": "metrics:updated",
            "data": result
        })
        
        return {"status": "synced", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Scripts Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/scripts")
async def get_scripts():
    """Get all scripts"""
    from workflows.performance_database import get_all_scripts
    scripts = get_all_scripts()
    return {"scripts": scripts}


@app.get("/api/scripts/{script_id}")
async def get_script(script_id: str):
    """Get single script details with NLP features"""
    from workflows.performance_database import get_script_by_id
    
    script = get_script_by_id(script_id)
    if not script:
        return {"error": "Script not found"}
    
    # Extract features
    features = script.get("features", "{}")
    if isinstance(features, str):
        try:
            features = json.loads(features)
        except:
            features = {}
    
    return {
        "script": script,
        "features": features
    }


@app.post("/api/scripts/{script_id}/analyze")
async def analyze_script(script_id: str, _: bool = Depends(verify_api_key)):
    """Analyze script with NLP features"""
    from workflows.performance_database import get_script_by_id
    
    script = get_script_by_id(script_id)
    if not script:
        return {"error": "Script not found"}
    
    script_text = script.get("script_text", "")
    content_type = script.get("content_type")
    
    # Extract NLP features
    features = extract_script_features(script_text, content_type)
    
    # Get virality prediction
    predictor = get_virality_predictor()
    prediction = predictor.predict(features) if predictor.is_trained else 50.0
    
    return {
        "features": features,
        "virality_prediction": prediction
    }


# ---------------------------------------------------------------------------
# Learnings Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/learnings")
async def get_all_learnings():
    """Get all learnings"""
    learnings = get_learnings()
    return {"learnings": learnings}


@app.get("/api/learnings/weights")
async def get_learning_weights():
    """Get content type selection weights (70/30)"""
    result = get_thompson_sampling_weights(explore_ratio=0.3)
    selected = select_content_type_70_30()
    
    return {
        "weights": result.get("weights", {}),
        "selected": selected,
        "sampled_scores": result.get("sampled_scores", {})
    }


# ---------------------------------------------------------------------------
# Context/Graph Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/context/games")
async def get_games():
    """Get all game contexts"""
    cm = get_context_manager()
    games = cm.get_games()
    
    # Also check for games in the Context directory
    context_dir = os.path.join(WORKSPACE, "Context")
    if os.path.exists(context_dir):
        for item in os.listdir(context_dir):
            if os.path.isdir(os.path.join(context_dir, item)) and not item.startswith("."):
                if item not in games:
                    games.append(item)
    
    return {"games": games}


@app.get("/api/context/{game}")
async def get_game_context(game: str):
    """Get all context items for a game"""
    # Sanitize game name
    game = sanitize_input(game, max_length=100)
    cm = get_context_manager()
    
    return {
        "characters": [item.to_dict() for item in cm.get_context_items(game, "character")],
        "locations": [item.to_dict() for item in cm.get_context_items(game, "location")],
        "terms": [item.to_dict() for item in cm.get_context_items(game, "term")],
        "relationships": [item.to_dict() for item in cm.get_context_items(game, "relationship")]
    }


@app.get("/api/context/{game}/graph")
async def get_graph_data(game: str):
    """Get graph data in Cytoscape.js format"""
    # Sanitize game name
    game = sanitize_input(game, max_length=100)
    cm = get_context_manager()
    
    nodes = []
    edges = []
    node_id_map = {}
    
    # Add nodes for characters (cyan)
    for item in cm.get_context_items(game, "character"):
        nodes.append({
            "data": {
                "id": item.id,
                "label": item.name,
                "type": "character",
                "description": item.description
            }
        })
        node_id_map[item.name.lower()] = item.id
    
    # Add nodes for locations (green)
    for item in cm.get_context_items(game, "location"):
        nodes.append({
            "data": {
                "id": item.id,
                "label": item.name,
                "type": "location",
                "description": item.description
            }
        })
        node_id_map[item.name.lower()] = item.id
    
    # Add nodes for terms (yellow)
    for item in cm.get_context_items(game, "term"):
        nodes.append({
            "data": {
                "id": item.id,
                "label": item.name,
                "type": "term",
                "description": item.description
            }
        })
        node_id_map[item.name.lower()] = item.id
    
    # Add nodes for relationships (magenta) and edges
    rel_id = 0
    for item in cm.get_context_items(game, "relationship"):
        # Relationship as a node
        nodes.append({
            "data": {
                "id": item.id,
                "label": item.name,
                "type": "relationship",
                "category": item.category
            }
        })
        
        # Try to connect to characters involved
        mentioned_entities = []
        rel_text = item.name.lower()
        
        if "↔" in item.name:
            parts = item.name.split(" ↔ ")
            if len(parts) == 2:
                from_name = parts[0].strip().lower()
                to_name = parts[1].strip().lower()
                if from_name in node_id_map:
                    mentioned_entities.append(node_id_map[from_name])
                if to_name in node_id_map:
                    mentioned_entities.append(node_id_map[to_name])
        else:
            # Extract entities from natural language text
            for name_lower, ent_id in node_id_map.items():
                if len(name_lower) < 2:
                    if name_lower == rel_text:
                        mentioned_entities.append(ent_id)
                    continue
                    
                # Use word boundary to match exactly
                pattern = r'\b' + re.escape(name_lower) + r'\b'
                if re.search(pattern, rel_text):
                    mentioned_entities.append(ent_id)
        
        # Connect the relationship node to all mentioned entities
        for ent_id in set(mentioned_entities):
            edges.append({
                "data": {
                    "id": f"e{rel_id}",
                    "source": item.id,
                    "target": ent_id,
                    "label": item.category or "involves"
                }
            })
            rel_id += 1
    
    return {"nodes": nodes, "edges": edges}


@app.get("/api/context/{game}/segments")
async def get_segment_references(game: str):
    """Get segment references for context nodes"""
    # Sanitize game name
    game = sanitize_input(game, max_length=100)
    import os
    SEGMENT_REF_FILE = os.path.expanduser("~/ShortsForge/Context/segment_references.json")
    game_key = game.lower().replace(" ", "_")
    
    try:
        if os.path.exists(SEGMENT_REF_FILE):
            with open(SEGMENT_REF_FILE, "r") as f:
                refs = json.load(f)
            return {"references": refs.get(game_key, {})}
        return {"references": {}}
    except Exception as e:
        return {"error": str(e)}, 500


@app.put("/api/context/{game}/{item_type}/{item_id}")
@limiter.limit("10/minute")
async def update_context_item(request: Request, game: str, item_type: str, item_id: str, data: dict, _: bool = Depends(verify_api_key)):
    """Update a context item"""
    # Sanitize inputs
    game = sanitize_input(game, max_length=100)
    item_id = sanitize_input(item_id, max_length=100)
    from workflows.context_manager_v2 import update_item
    result = update_item(game, item_id, **data)
    if result:
        return {"status": "updated", "item": result.to_dict()}
    return {"error": "Item not found"}, 404


@app.delete("/api/context/{game}/{item_type}/{item_id}")
@limiter.limit("5/minute")
async def delete_context_item(request: Request, game: str, item_type: str, item_id: str, _: bool = Depends(verify_api_key)):
    """Delete a context item"""
    # Sanitize inputs
    game = sanitize_input(game, max_length=100)
    item_id = sanitize_input(item_id, max_length=100)
    from workflows.context_manager_v2 import delete_item
    result = delete_item(game, item_id)
    if result:
        return {"status": "deleted"}
    return {"error": "Item not found"}, 404


# ---------------------------------------------------------------------------
# TTS Learning Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/tts/voices")
async def get_tts_voices():
    """Get available TTS voices"""
    voices = [
        "Vindemiatrix", "Aoede", "Callirrhoe", "Gacrux", "Sulafat", "Leda",
        "Kore", "Enceladus", "Erinome", "Despina", "Alnilam", "Laomedeia",
        "Achernar", "Pulcherrima", "Zephyr", "Puck", "Charon", "Fenrir"
    ]
    return {"voices": voices}


@app.get("/api/tts/learnings")
async def get_tts_learnings():
    """Get TTS performance learning data"""
    learnings = get_tts_learning_data()
    return {"learnings": learnings}

# ---------------------------------------------------------------------------
# System / Desktop Port Endpoints
# ---------------------------------------------------------------------------
from pydantic import BaseModel

@app.get("/api/config")
async def get_config():
    env_file = os.path.join(WORKSPACE, ".env")
    config = {"GAME_TITLE": "", "TTS_VOICE": "", "CLIPS_PER_HOUR": ""}
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.strip().split("=", 1)
                    if k in config:
                        config[k] = v.strip('"\'')
    return config

class ConfigUpdate(BaseModel):
    GAME_TITLE: Optional[str] = None
    TTS_VOICE: Optional[str] = None
    CLIPS_PER_HOUR: Optional[str] = None

@app.post("/api/config")
@limiter.limit("5/minute")
async def update_config(request: Request, updates: ConfigUpdate, _: bool = Depends(verify_api_key)):
    """Update configuration - requires API key"""
    env_file = os.path.join(WORKSPACE, ".env")
    lines = []
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            lines = f.readlines()
    
    update_dict = updates.dict(exclude_none=True)
    for k, v in update_dict.items():
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{k}="):
                lines[i] = f"{k}={v}\n"
                found = True
                break
        if not found:
            lines.append(f"{k}={v}\n")
            
    with open(env_file, "w") as f:
        f.writelines(lines)
    return {"status": "updated", "config": update_dict}

class DownloadRequest(BaseModel):
    url: str

@app.post("/api/pipeline/download")
@limiter.limit("3/minute")
async def download_from_url(request: Request, req: DownloadRequest, _: bool = Depends(verify_api_key)):
    """Download from URL - requires API key"""
    global pipeline_status, pipeline_process
    if pipeline_status["running"]:
        return {"status": "error", "message": "Pipeline already running"}
    
    # Validate and sanitize URL
    url = sanitize_input(req.url, max_length=2000)
    if not url.startswith(("http://", "https://")):
        return {"status": "error", "message": "Invalid URL scheme"}
    
    import socket
    import ipaddress
    from urllib.parse import urlparse
    
    try:
        parsed = urlparse(url)
        if not parsed.hostname:
            return {"status": "error", "message": "Invalid URL"}
        ip = socket.gethostbyname(parsed.hostname)
        ip_obj = ipaddress.ip_address(ip)
        if ip_obj.is_private or ip_obj.is_loopback:
            return {"status": "error", "message": "Access to internal IPs is forbidden"}
    except Exception as e:
        return {"status": "error", "message": "Invalid hostname"}
    
    cmd = [sys.executable, "workflows/shortsforge.py", "download", "-url", url]
    pipeline_status["message"] = f"Downloading from {url}..."
    pipeline_status["running"] = True
    pipeline_status["current_phase"] = "downloading"
    
    def run_download():
        global pipeline_process
        try:
            pipeline_process = subprocess.Popen(cmd, cwd=WORKSPACE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, bufsize=1)
            for line in pipeline_process.stdout:
                pass
            pipeline_process.wait()
        except Exception as e:
            pass
        finally:
            pipeline_status["running"] = False
            pipeline_process = None
            
    thread = threading.Thread(target=run_download)
    thread.daemon = True
    thread.start()
    return {"status": "started"}

@app.get("/api/logs")
async def get_logs(lines: int = 100):
    """Get pipeline logs"""
    # Validate lines parameter
    if lines < 1:
        lines = 1
    if lines > 1000:
        lines = 1000
    
    log_file = os.path.join(WORKSPACE, "pipeline.log")
    if not os.path.exists(log_file):
        return {"logs": []}
    
    import collections
    with open(log_file, "r", encoding="utf-8") as f:
        tail = collections.deque(f, lines)
    return {"logs": list(tail)}

@app.post("/api/system/cleanup")
@limiter.limit("2/minute")
async def cleanup_files(request: Request, _: bool = Depends(verify_api_key)):
    """Cleanup files - requires API key"""
    import glob
    for d in ["media", "shorts", "tts", "transcripts"]:
        path = os.path.join(WORKSPACE, d)
        for f in glob.glob(os.path.join(path, "*")):
            if os.path.isfile(f):
                try: os.remove(f)
                except: pass
    return {"status": "cleaned"}

@app.post("/api/system/restart-listener")
@limiter.limit("2/minute")
async def restart_listener(request: Request, _: bool = Depends(verify_api_key)):
    """Restart Telegram listener - requires API key"""
    subprocess.run([sys.executable, "workflows/shortsforge.py", "stop"], cwd=WORKSPACE, capture_output=True)
    subprocess.Popen([sys.executable, "workflows/shortsforge.py", "listen"], cwd=WORKSPACE, stdin=subprocess.DEVNULL)
    return {"status": "restarted"}

class ImportRequest(BaseModel):
    game: str

@app.post("/api/context/import")
@limiter.limit("3/minute")
async def import_context(request: Request, req: ImportRequest, _: bool = Depends(verify_api_key)):
    """Import context - requires API key"""
    # Sanitize game name
    game = sanitize_input(req.game, max_length=100)
    ctx_dir = os.path.join(WORKSPACE, "Context", game)
    if not os.path.exists(ctx_dir):
        return {"error": "Game folder not found"}
        
    context = {"characters": [], "locations": [], "key_terms": [], "relationships": []}
    md_files = ["characters.md", "locations.md", "key_terms.md", "relationships.md"]
    
    for md_file in md_files:
        md_path = os.path.join(ctx_dir, md_file)
        if not os.path.exists(md_path): continue
        with open(md_path, "r") as f:
            content = f.read()
        items = []
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("|") and "--" not in line and "|" in line[1:]:
                parts = line.split("|")
                if len(parts) >= 2:
                    name = parts[1].strip()
                    if name and not name.startswith("-") and name != "Name":
                        name = name.replace("[[", "").replace("]]", "")
                        if name: items.append(name)
        
        key = md_file.replace(".md", "")
        if key == "characters": context["characters"] = [{"name": i, "status": "imported"} for i in items]
        elif key == "locations": context["locations"] = [{"name": i, "status": "imported"} for i in items]
        elif key == "key_terms": context["key_terms"] = [{"term": i} for i in items]
        elif key == "relationships": context["relationships"] = [{"from": i} for i in items]
        
    if context["characters"] or context["locations"]:
        try:
            from workflows.context_manager import save_verified_context
            save_verified_context(game, context)
            return {"status": "imported", "stats": {k: len(v) for k,v in context.items()}}
        except Exception as e:
            return {"error": str(e)}
    return {"status": "no data"}

@app.post("/api/context/clear")
@limiter.limit("2/minute")
async def clear_context(request: Request, req: ImportRequest, _: bool = Depends(verify_api_key)):
    """Clear context - requires API key"""
    # Sanitize game name
    game = sanitize_input(req.game, max_length=100)
    try:
        from workflows.context_manager import clear_all_context_for_game
        result = clear_all_context_for_game(game)
        return {"status": "cleared", "result": result}
    except Exception as e:
        return {"error": str(e)}

# ============================================================================
# WEBSOCKET
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates"""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages if needed
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.now().isoformat()})
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ============================================================================
# SERVE FRONTEND
# ============================================================================

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """Serve the frontend build"""
    # In development, this would be handled by Vite
    # In production, would serve from frontend/dist
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ShortsForge - Loading...</title>
    </head>
    <body>
        <div id="root">Loading ShortsForge Web UI...</div>
        <script type="module" src="/src/main.tsx"></script>
    </body>
    </html>
    """)


if __name__ == "__main__":
    import uvicorn
    print("Starting ShortsForge Backend on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)