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
from typing import Optional, Any
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
from workflows.context_manager import SERIES_MAPPING

# ============================================================================
# SECURITY CONFIGURATION
# ============================================================================

SECRET_KEY_FILE = "/home/alph4r1us/ShortsForge/.shortsforge/api_key"

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
            except Exception:
                pass

manager = ConnectionManager()

# Pipeline status storage
pipeline_status = {
    "running": False,
    "current_phase": None,
    "progress": 0,
    "message": "Idle",
    "last_run": None,
    "error": None
}

# Pipeline settings storage
SETTINGS_FILE = os.path.expanduser("~/ShortsForge/.shortsforge/web_settings.json")

def load_pipeline_settings():
    """Load pipeline settings from file"""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        import logging
        logging.warning(f"Failed to load settings: {e}")
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
    except Exception as e:
        import logging
        logging.warning(f"Failed to save settings: {e}")


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
    env_file = os.path.join(WORKSPACE, ".env")
    game_title = "Not set"
    parent_franchise = ""
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.strip().split("=", 1)
                    if k == "GAME_TITLE":
                        game_title = v.strip('"\'')
                    elif k == "PARENT_FRANCHISE":
                        parent_franchise = v.strip('"\'')
    return {
        "pipeline": pipeline_status,
        "oauth_configured": is_oauth_configured(),
        "workspace": WORKSPACE,
        "game_title": game_title,
        "parent_franchise": parent_franchise
    }


# ---------------------------------------------------------------------------
# Pipeline Endpoints
# ---------------------------------------------------------------------------

import subprocess
import threading

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
    except Exception as e:
        import logging
        logging.warning(f"Failed to read status file: {e}")
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
    except Exception:
        pass
    
    # Clear status file before starting
    try:
        if os.path.exists(STATUS_FILE):
            os.remove(STATUS_FILE)
    except Exception:
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
        while pipeline_process is not None and pipeline_process.poll() is None:
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
        elif pipeline_process is None:
            # Distinguish between never run and stopped/finished
            if not status_text:
                pipeline_status["current_phase"] = "Idle"
                pipeline_status["message"] = "Ready to run"
            else:
                pipeline_status["current_phase"] = "Stopped"
                pipeline_status["message"] = "Pipeline stopped by user"
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
        
        # Auto-sync YouTube metrics after pipeline completes
        try:
            from workflows.metrics_fetcher import get_recent_uploads
            from workflows.performance_database import auto_match_and_fetch
            videos = get_recent_uploads(days=7, max_results=50)
            result = auto_match_and_fetch(videos)
            print(f"[METRICS] Auto-sync completed: {result.get('new_metrics', 0)} metrics updated")
        except Exception as e:
            print(f"[METRICS] Auto-sync failed: {e}")
        
        # Ensure log file is closed
        if log_file:
            try:
                log_file.close()
            except Exception:
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
        except Exception:
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
        except Exception:
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
    """Get all game contexts with franchise structure.

    Returns franchise keys with their child games listed.
    """
    cm = get_context_manager()
    games = cm.get_games()

    # Also check for games in the Context directory
    context_dir = os.path.join(WORKSPACE, "Context")
    if os.path.exists(context_dir):
        for item in os.listdir(context_dir):
            if os.path.isdir(os.path.join(context_dir, item)) and not item.startswith("."):
                if item not in games:
                    games.append(item)

    # Build franchise structure
    # Reverse SERIES_MAPPING: series_name -> [game_keys]
    series_to_games = {}
    for game_key, series_name in SERIES_MAPPING.items():
        if series_name not in series_to_games:
            series_to_games[series_name] = []
        series_to_games[series_name].append(game_key)

    # Also scan Context directory for franchise keys
    verified_file = os.path.join(context_dir, "verified_context.json")
    if os.path.exists(verified_file):
        try:
            with open(verified_file, "r") as f:
                all_context = json.load(f)
            # Check for keys that look like franchise keys (series names from mapping)
            for key in all_context.keys():
                if key not in series_to_games:
                    # Check if this key has a 'games' array indicating it's a franchise
                    ctx_data = all_context[key].get("context", {})
                    if isinstance(ctx_data, dict) and "games" in ctx_data:
                        games_list = ctx_data.get("games", [])
                        if games_list:
                            series_to_games[key] = [g.lower().replace(" ", "_") for g in games_list]
        except Exception:
            pass

    # Build response with franchise structure
    result = []
    seen_franchises = set()

    for game in games:
        game_lower = game.lower().replace(" ", "_")
        if game_lower in series_to_games:
            # This is a franchise or belongs to one
            series_name = series_to_games[game_lower] if game_lower in series_to_games else game
            if isinstance(series_name, list):
                # It's a franchise key
                series_key = game_lower
                child_games = series_name
                if series_key not in seen_franchises:
                    result.append({
                        "name": series_key,
                        "is_series": True,
                        "display_name": " ".join(series_key.split("_")).title(),
                        "children": [g.replace("_", " ").title() for g in child_games]
                    })
                    seen_franchises.add(series_key)
        else:
            # Check if this game belongs to a known series
            series_name = SERIES_MAPPING.get(game_lower)
            if series_name and series_name in seen_franchises:
                continue  # Skip, already added as franchise
            # Regular game (no franchise)
            result.append({
                "name": game,
                "is_series": False,
                "display_name": game.replace("_", " ").title(),
                "children": []
            })

    return {"games": result}


@app.get("/api/context/{game}")
async def get_game_context(game: str):
    """Get all context items for a game or franchise.

    If game is a franchise key, returns franchise context.
    If game is a child game of a franchise, returns the FRANCHISE context (not individual game).
    """
    game_title = sanitize_input(game, max_length=100)
    game_key = game_title.lower().replace(" ", "_").strip()
    cm = get_context_manager()

    # Check if this is a franchise key or child game
    is_franchise = game_key in SERIES_MAPPING.values()
    series_name = None

    if not is_franchise:
        series_name = SERIES_MAPPING.get(game_key)
        if series_name:
            # This is a child game - redirect to franchise context
            game_key = series_name

    # Now load context for game_key (which may be franchise)
    verified_file = os.path.join(WORKSPACE, "Context", "verified_context.json")
    all_context = {}
    if os.path.exists(verified_file):
        try:
            with open(verified_file, "r") as f:
                all_context = json.load(f)
        except Exception:
            pass

    context_data = all_context.get(game_key, {}).get("context", {})

    # If this is a franchise, also merge in context from child games
    if is_franchise or series_name:
        child_contexts = []
        for child_key, series_val in SERIES_MAPPING.items():
            if series_val == game_key:
                child_ctx = all_context.get(child_key, {}).get("context", {})
                if child_ctx:
                    child_contexts.append(child_ctx)

        # Merge child contexts into franchise context
        merged = {
            "characters": set(),
            "locations": set(),
            "key_terms": set(),
            "relationships": []
        }

        def add_to_set(target_set, items, name_key="name"):
            for item in items:
                if isinstance(item, dict):
                    target_set.add(item.get(name_key, ""))
                elif isinstance(item, str):
                    target_set.add(item)
                else:
                    target_set.add(str(item))

        if context_data:
            add_to_set(merged["characters"], context_data.get("characters", []))
            add_to_set(merged["locations"], context_data.get("locations", []))
            add_to_set(merged["key_terms"], context_data.get("key_terms", []))
            for rel in context_data.get("relationships", []):
                if isinstance(rel, dict):
                    merged["relationships"].append(rel)

        for child_ctx in child_contexts:
            add_to_set(merged["characters"], child_ctx.get("characters", []))
            add_to_set(merged["locations"], child_ctx.get("locations", []))
            add_to_set(merged["key_terms"], child_ctx.get("key_terms", []))
            for rel in child_ctx.get("relationships", []):
                if isinstance(rel, dict):
                    is_dup = any(
                        r.get("from") == rel.get("from") and r.get("to") == rel.get("to")
                        for r in merged["relationships"]
                    )
                    if not is_dup:
                        merged["relationships"].append(rel)

        context_data = {
            "characters": [{"name": c} for c in sorted(merged["characters"])],
            "locations": [{"name": l} for l in sorted(merged["locations"])],
            "key_terms": [{"name": t} for t in sorted(merged["key_terms"])],
            "relationships": merged["relationships"]
        }

    return {
        "characters": context_data.get("characters", []),
        "locations": context_data.get("locations", []),
        "terms": context_data.get("key_terms", []),
        "relationships": context_data.get("relationships", []),
        "games": context_data.get("games", []),
        "is_franchise": is_franchise or series_name is not None,
        "franchise_name": game_key if (is_franchise or series_name) else None
    }


def analyze_transcript_cooccurrence(game_key: str) -> Dict[str, Any]:
    """Analyze transcripts for entity co-occurrence to generate implicit graph edges.
    
    Returns dict with:
    - edges: list of implicit edges with {source_id, target_id, type, weight, label}
    - entity_segments: {entity_name: [segment_indices]} for reference
    """
    import re
    from collections import defaultdict
    
    # Get entities from context manager
    cm = get_context_manager()
    entities = {
        'character': [],
        'location': [],
        'term': []
    }
    
    for etype in entities:
        for item in cm.get_context_items(game_key, etype):
            entities[etype].append({
                'id': item.id,
                'name': item.name.lower(),
                'original': item.name,
                'type': etype
            })
    
    # Build entity name to ID map (include variations)
    name_to_id = {}
    for etype, items in entities.items():
        for item in items:
            name_to_id[item['name']] = item['id']
            # Also add lowercase version
            name_to_id[item['name'].lower()] = item['id']
    
    # Find and parse transcript files
    transcripts_dir = os.path.join(WORKSPACE, "transcripts")
    if not os.path.exists(transcripts_dir):
        return {"edges": [], "entity_segments": {}}
    
    # Find transcripts related to this game/franchise
    transcript_files = []
    for fname in os.listdir(transcripts_dir):
        if fname.endswith('.json'):
            transcript_files.append(os.path.join(transcripts_dir, fname))
    
    if not transcript_files:
        return {"edges": [], "entity_segments": {}}
    
    # Entity patterns for matching (case-insensitive)
    entity_patterns = {}
    for etype, items in entities.items():
        for item in items:
            entity_patterns[item['name']] = {
                'id': item['id'],
                'type': etype,
                'original': item['original']
            }
            # Also add lowercase
            entity_patterns[item['name'].lower()] = entity_patterns[item['name']]
    
    # Co-occurrence tracking
    cooccurrence = defaultdict(int)  # (name1, name2) -> count
    entity_segments = defaultdict(set)  # name -> set of segment indices
    entity_contexts = defaultdict(list)  # name -> list of {segment_idx, nearby_entities}
    
    # Process each transcript
    for tfile in transcript_files:
        try:
            with open(tfile, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            segments = data.get('segments', [])
            
            # Process each segment
            for seg_idx, segment in enumerate(segments):
                text = segment.get('text', '')
                if not text:
                    continue
                
                text_lower = text.lower()
                
                # Find all entities mentioned in this segment
                mentioned = []
                for entity_name in entity_patterns:
                    # Use word boundary matching
                    pattern = r'\b' + re.escape(entity_name) + r'\b'
                    if re.search(pattern, text_lower):
                        mentioned.append(entity_name)
                        entity_segments[entity_name].add(seg_idx)
                
                # Record co-occurrences (entities in same segment)
                for i, name1 in enumerate(mentioned):
                    for name2 in mentioned[i+1:]:
                        # Store sorted pair to avoid duplicates
                        pair = tuple(sorted([name1, name2]))
                        cooccurrence[pair] += 1
                        
                        # Also track which other entities were nearby
                        for other in mentioned:
                            if other != name1:
                                entity_contexts[name1].append({
                                    'segment': seg_idx,
                                    'nearby': other,
                                    'text_preview': text[:100]
                                })
        except Exception as e:
            print(f"Error processing transcript {tfile}: {e}")
            continue
    
    # Generate implicit edges from co-occurrences
    implicit_edges = []
    edge_id = 0
    
    # Threshold: at least 2 co-occurrences to create an edge
    min_cooccurrence = 2
    
    for (name1, name2), count in cooccurrence.items():
        if count >= min_cooccurrence:
            id1 = name_to_id.get(name1)
            id2 = name_to_id.get(name2)
            
            if id1 and id2 and id1 != id2:
                # Determine edge type based on entity types
                type1 = entity_patterns.get(name1, {}).get('type', 'unknown')
                type2 = entity_patterns.get(name2, {}).get('type', 'unknown')
                
                # Edge type logic
                if type1 == 'character' and type2 == 'location':
                    edge_type = 'located_at'
                    edge_label = f"found in {entity_patterns.get(name2, {}).get('original', name2)}"
                elif type2 == 'character' and type1 == 'location':
                    edge_type = 'located_at'
                    edge_label = f"visited by {entity_patterns.get(name1, {}).get('original', name1)}"
                elif type1 == 'term' or type2 == 'term':
                    edge_type = 'related_to'
                    edge_label = f"connected ({count}x)"
                else:
                    edge_type = 'co_occurs'
                    edge_label = f"mentioned together ({count}x)"
                
                implicit_edges.append({
                    'source': id1,
                    'target': id2,
                    'type': edge_type,
                    'weight': count,
                    'label': edge_label,
                    'implicit': True
                })
                edge_id += 1
    
    # Also create edges between entities that share many contexts
    # (entities frequently mentioned in same segments)
    shared_contexts = defaultdict(int)
    for name, contexts in entity_contexts.items():
        nearby_counts = defaultdict(int)
        for ctx in contexts:
            nearby_counts[ctx['nearby']] += 1
        
        for other_name, cnt in nearby_counts.items():
            if cnt >= 3:  # At least 3 shared contexts
                pair = tuple(sorted([name, other_name]))
                if pair not in cooccurrence or cooccurrence[pair] < cnt:
                    shared_contexts[pair] = cnt
    
    # Add shared context edges
    for (name1, name2), count in shared_contexts.items():
        if count >= 3:
            id1 = name_to_id.get(name1)
            id2 = name_to_id.get(name2)
            
            if id1 and id2 and id1 != id2:
                # Check if edge already exists
                exists = any(
                    (e['source'] == id1 and e['target'] == id2) or
                    (e['source'] == id2 and e['target'] == id1)
                    for e in implicit_edges
                )
                
                if not exists:
                    type1 = entity_patterns.get(name1, {}).get('type', 'unknown')
                    type2 = entity_patterns.get(name2, {}).get('type', 'unknown')
                    
                    edge_type = 'mentioned_with' if 'character' in [type1, type2] else 'contextually_linked'
                    
                    implicit_edges.append({
                        'source': id1,
                        'target': id2,
                        'type': edge_type,
                        'weight': count,
                        'label': f"frequently together ({count}x)",
                        'implicit': True
                    })
    
    return {
        "edges": implicit_edges,
        "entity_segments": {k: list(v) for k, v in entity_segments.items()},
        "total_transcripts": len(transcript_files),
        "total_cooccurrences": sum(cooccurrence.values())
    }


@app.get("/api/context/{game}/graph")
async def get_graph_data(game: str):
    """Get graph data in Cytoscape.js format"""
    # Sanitize game name
    game_title = sanitize_input(game, max_length=100)
    game_key = game_title.lower().replace(" ", "_").strip()
    cm = get_context_manager()
    
    nodes = []
    edges = []
    node_id_map = {}
    
    # Add nodes for characters (cyan)
    for item in cm.get_context_items(game_key, "character"):
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
    for item in cm.get_context_items(game_key, "location"):
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
    for item in cm.get_context_items(game_key, "term"):
        nodes.append({
            "data": {
                "id": item.id,
                "label": item.name,
                "type": "term",
                "description": item.description
            }
        })
        node_id_map[item.name.lower()] = item.id
    
    # Add nodes for games (gold)
    for item in cm.get_context_items(game_key, "game"):
        nodes.append({
            "data": {
                "id": item.id,
                "label": item.name,
                "type": "game",
                "description": item.description
            }
        })
        node_id_map[item.name.lower()] = item.id
    
    # Add nodes for relationships (magenta) and edges
    rel_id = 0
    entity_pairs = []  # Track direct connections between entities
    
    for item in cm.get_context_items(game_key, "relationship"):
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
                
                # Track direct entity-to-entity connection
                if from_name in node_id_map and to_name in node_id_map:
                    entity_pairs.append((node_id_map[from_name], node_id_map[to_name], item.category))
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
    
    # Add direct edges between entities that share relationships
    added_pairs = set()
    for source_id, target_id, category in entity_pairs:
        pair_key = tuple(sorted([source_id, target_id]))
        if pair_key not in added_pairs:
            edges.append({
                "data": {
                    "id": f"direct_{source_id[:8]}_{target_id[:8]}",
                    "source": source_id,
                    "target": target_id,
                    "label": category,
                    "type": "related_to",
                    "implicit": False,
                    "is_direct": True
                }
            })
            added_pairs.add(pair_key)
    
    # Generate implicit edges from transcript co-occurrence analysis
    try:
        cooccurrence_data = analyze_transcript_cooccurrence(game_key)
        implicit_edges_data = cooccurrence_data.get("edges", [])
        
        # Add implicit edges to the graph
        for ie in implicit_edges_data:
            edges.append({
                "data": {
                    "id": f"implicit_{ie['source']}_{ie['target']}",
                    "source": ie["source"],
                    "target": ie["target"],
                    "label": ie.get("label", ""),
                    "type": ie.get("type", "co_occurs"),
                    "implicit": True,
                    "weight": ie.get("weight", 1)
                }
            })
    except Exception as e:
        print(f"Error generating implicit edges: {e}")
    
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
    game_title = sanitize_input(game, max_length=100)
    game_key = game_title.lower().replace(" ", "_").strip()
    item_id = sanitize_input(item_id, max_length=100)
    from workflows.context_manager_v2 import update_item
    result = update_item(game_key, item_id, **data)
    if result:
        return {"status": "updated", "item": result.to_dict()}
    return {"error": "Item not found"}, 404


@app.delete("/api/context/{game}/{item_type}/{item_id}")
@limiter.limit("5/minute")
async def delete_context_item(request: Request, game: str, item_type: str, item_id: str, _: bool = Depends(verify_api_key)):
    """Delete a context item"""
    # Sanitize inputs
    game_title = sanitize_input(game, max_length=100)
    game_key = game_title.lower().replace(" ", "_").strip()
    item_id = sanitize_input(item_id, max_length=100)
    from workflows.context_manager_v2 import delete_item
    result = delete_item(game_key, item_id)
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
    config = {"GAME_TITLE": "", "TTS_VOICE": "", "CLIPS_PER_HOUR": "", "PARENT_FRANCHISE": ""}
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
    PARENT_FRANCHISE: Optional[str] = None

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
    game_title = sanitize_input(req.game, max_length=100)
    game_key = game_title.lower().replace(" ", "_").strip()
    ctx_dir = os.path.join(WORKSPACE, "Context", game_key)
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
            save_verified_context(game_key, context)
            
            # Update memory
            cm = get_context_manager()
            if game_key in cm.contexts:
                # This ensures the new context items are loaded from file the next time
                del cm.contexts[game_key]
                
            return {"status": "imported", "stats": {k: len(v) for k,v in context.items()}}
        except Exception as e:
            return {"error": str(e)}
    return {"status": "no data"}

class CreateGameRequest(BaseModel):
    game: str

@app.post("/api/context/create_game")
@limiter.limit("3/minute")
async def create_game(request: Request, req: CreateGameRequest, _: bool = Depends(verify_api_key)):
    """Create a blank franchise or game context"""
    game_title = sanitize_input(req.game, max_length=100)
    game_key = game_title.lower().replace(" ", "_").strip()
    cm = get_context_manager()
    cm.contexts[game_key] = {"character": [], "location": [], "term": [], "relationship": []}
    cm.save_context(game_key)
    
    # Auto-set PARENT_FRANCHISE in .env if this is the first franchise
    if game_key in SERIES_MAPPING.values():
        env_file = os.path.join(WORKSPACE, ".env")
        parent_franchise = os.environ.get("PARENT_FRANCHISE", "")
        if not parent_franchise:
            # Set PARENT_FRANCHISE to this franchise
            lines = []
            if os.path.exists(env_file):
                with open(env_file, "r") as f:
                    lines = f.readlines()
            
            found = False
            for i, line in enumerate(lines):
                if line.startswith("PARENT_FRANCHISE="):
                    lines[i] = f"PARENT_FRANCHISE={game_key}\n"
                    found = True
                    break
            
            if not found:
                lines.append(f"PARENT_FRANCHISE={game_key}\n")
            
            with open(env_file, "w") as f:
                f.writelines(lines)
    
    return {"status": "created", "game": game_key}

class MergeContextRequest(BaseModel):
    target_game: str
    source_game: str

@app.post("/api/context/merge")
@limiter.limit("3/minute")
async def merge_context(request: Request, req: MergeContextRequest, _: bool = Depends(verify_api_key)):
    """Merge context from source_game to target_game"""
    target_title = sanitize_input(req.target_game, max_length=100)
    target_key = target_title.lower().replace(" ", "_").strip()
    source_title = sanitize_input(req.source_game, max_length=100)
    source_key = source_title.lower().replace(" ", "_").strip()
    
    cm = get_context_manager()
    if source_key not in cm.contexts:
        return {"error": "Source game context not found"}
        
    source_items = cm.export_items(source_key)
    if not source_items:
        return {"error": "Source context is empty"}
        
    # Import into target
    result = cm.import_items(target_key, source_items)
    
    # Check if this source_title already exists as a game
    existing_games = [item.name.lower() for item in cm.get_context_items(target_key, "game")]
    if source_title.lower() not in existing_games:
        cm.create_item(target_key, "game", name=source_title, source="merge")
        
    return {"status": "merged", "result": result}

@app.post("/api/context/clear")
@limiter.limit("2/minute")
async def clear_context(request: Request, req: ImportRequest, _: bool = Depends(verify_api_key)):
    """Clear context - requires API key"""
    # Sanitize game name
    game_title = sanitize_input(req.game, max_length=100)
    game_key = game_title.lower().replace(" ", "_").strip()
    try:
        from workflows.context_manager import clear_all_context_for_game
        result = clear_all_context_for_game(game_key)
        
        # Clear from memory so it's not rewritten
        cm = get_context_manager()
        if game_key in cm.contexts:
            del cm.contexts[game_key]
            
        return {"status": "cleared", "result": result}
    except Exception as e:
        return {"error": str(e)}

@app.delete("/api/context/{game}")
@limiter.limit("5/minute")
async def delete_game_context(request: Request, game: str, _: bool = Depends(verify_api_key)):
    """Delete entire game context - requires API key"""
    from workflows.context_manager import clear_all_context_for_game
    
    # Sanitize game name
    game_title = sanitize_input(game, max_length=100)
    game_key = game_title.lower().replace(" ", "_").strip()
    
    try:
        # Clear all context for the game
        result = clear_all_context_for_game(game_key)
        
        # Clear from memory so it doesn't reappear
        cm = get_context_manager()
        if game_key in cm.contexts:
            del cm.contexts[game_key]
        
        # Also delete the game directory if it exists
        context_dir = os.path.join(WORKSPACE, "Context", game_key)
        if os.path.exists(context_dir):
            import shutil
            shutil.rmtree(context_dir)
        
        return {"status": "deleted", "game": game_key, "result": result}
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