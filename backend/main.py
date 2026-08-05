#!/usr/bin/env python3
"""
Cogitator Web Backend
FastAPI server for the cyberpunk web UI
"""
import os
import sys
import json
import time
import secrets
import re
import asyncio
import tempfile
from datetime import datetime
from typing import Optional, Any, Tuple, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from workflows.constants import WORKSPACE

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Depends, Body, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

# Import existing Cogitator modules
from workflows.performance_database import (
    get_performance_stats, get_all_videos_with_metrics, get_successful_scripts,
    get_learnings, get_tts_learning_data, get_thompson_sampling_weights,
    get_variant_performance_stats, get_channel_baseline, select_content_type_70_30
)
from workflows.metrics_fetcher import get_recent_uploads, is_oauth_configured
from workflows.learning_engine import extract_script_features, get_virality_predictor
from workflows.context_manager_v2 import ContextManagerV2, get_context_manager
from workflows.mempalace_integration import get_full_series_mapping, add_to_franchise
from workflows.constants import TTS_VOICES
from workflows.ws_manager import ConnectionManager, manager as ws_manager, pipeline_status, update_pipeline_status, get_pipeline_status
from backend.routers import create_routers

# ============================================================================
# SECURITY CONFIGURATION
# ============================================================================

SECRET_KEY_FILE = os.path.join(os.path.expanduser("~/.cogitator"), "api_key")

def load_or_create_api_key():
    """Load existing API key or create a new one"""
    os.makedirs(os.path.dirname(SECRET_KEY_FILE), exist_ok=True)
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
    # Block path traversal: remove ".." sequences and leading slashes
    text = text.replace("..", "")
    # Only strip leading slashes (path traversal), preserve internal slashes for URLs
    text = text.lstrip("/").lstrip("\\")
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

app = FastAPI(title="Cogitator API", version="2.0.0")
_main_loop = None

@app.on_event("startup")
async def _store_event_loop():
    global _main_loop
    _main_loop = asyncio.get_event_loop()

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

# WebSocket manager and pipeline status imported from workflows.ws_manager

# Pipeline settings storage
SETTINGS_FILE = os.path.join(WORKSPACE, ".cogitator/web_settings.json")

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
            {"id": "p3", "name": "Context", "enabled": True},
            {"id": "p4", "name": "Scripts", "enabled": True},
            {"id": "p5", "name": "Clips", "enabled": True},
            {"id": "p6", "name": "TTS", "enabled": True},
            {"id": "p7", "name": "Assemble", "enabled": True},
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

# Mount extracted routers (thumbnails, mempalace, publish, review, tiktok auto-import)
for _router in create_routers(verify_api_key, limiter):
    app.include_router(_router)

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/auth/key")
@limiter.limit("10/minute")
async def get_api_key(request: Request):
    """Return the API key for frontend bootstrapping.
    
    Only accessible from localhost for security.
    """
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1", "localhost"):
        return JSONResponse(status_code=403, content={"detail": "Forbidden"})
    return {"api_key": API_KEY}


@app.get("/api/status")
async def get_status(_: bool = Depends(verify_api_key)):
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
        "pipeline": get_pipeline_status(),
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
_pipeline_lock = threading.Lock()

# Phase ranges matching desktop UI
PHASE_RANGES = {
    1: (0, 10),
    2: (10, 25),
    3: (25, 40),
    4: (40, 60),
    5: (60, 80),
    6: (80, 90),
    7: (90, 100),
}
PHASE_LABELS = {
    1: "Download",
    2: "Transcribe",
    3: "Context",
    4: "Scripts",
    5: "Clips",
    6: "TTS",
    7: "Assemble",
}

async def broadcast_status():
    """Broadcast current pipeline status to all connected clients"""
    await ws_manager.broadcast({
        "type": "pipeline:status",
        "data": get_pipeline_status()
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

_SF_DIR = os.path.expanduser("~/.cogitator")
os.makedirs(_SF_DIR, exist_ok=True)
PIPELINE_LOG = os.path.join(_SF_DIR, "pipeline.log")
STATUS_FILE = os.path.join(_SF_DIR, "pipeline_status")
PENDING_DOWNLOAD_FILE = os.path.join(_SF_DIR, "pending_download.txt")

def run_pipeline_async(source: str = "youtube", video_url: str = ""):
    """Run pipeline in background thread"""
    global pipeline_process
    
    # Clear previous log
    try:
        if os.path.exists(PIPELINE_LOG):
            os.remove(PIPELINE_LOG)
    except OSError:
        pass
    
    # Clear status file before starting
    try:
        if os.path.exists(STATUS_FILE):
            os.remove(STATUS_FILE)
    except OSError:
        pass
    
    # Write pending download URL if provided
    phase_args = []
    if phases:
        phase_str = ",".join(str(int(p)) for p in phases if str(p).isdigit() or isinstance(p, int))
        if phase_str:
            phase_args = ["-phase", phase_str]

    if video_url:
        with open(PENDING_DOWNLOAD_FILE, "w") as f:
            f.write(video_url.strip())
        cmd = [sys.executable, "workflows/cogitator.py", "run"] + phase_args
        update_pipeline_status(message="Downloading from URL...")
    elif source == "local":
        cmd = [sys.executable, "workflows/cogitator.py", "run_local", "media"]
        update_pipeline_status(message="Processing local media...")
    else:
        cmd = [sys.executable, "workflows/cogitator.py", "run"] + phase_args
        update_pipeline_status(message="Downloading from YouTube..." if not phase_args else f"Running phases {phase_args[1]}...")
    
    update_pipeline_status(running=True, current_phase="Starting", progress=0, logs=[], error=None)

    # Open log file for pipeline output
    log_file = open(PIPELINE_LOG, "w")

    # Set up environment with PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = WORKSPACE

    try:
        with _pipeline_lock:
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

        # Poll status file and tail logs while process runs
        last_status = ""
        log_pos = 0
        while True:
            with _pipeline_lock:
                proc = pipeline_process
            if proc is None or proc.poll() is not None:
                break

            # Broadcast new log lines via WebSocket
            try:
                if os.path.exists(PIPELINE_LOG):
                    with open(PIPELINE_LOG, "r") as lf:
                        lf.seek(log_pos)
                        for line in lf:
                            line = line.rstrip("\n\r")
                            if line and _main_loop and _main_loop.is_running():
                                asyncio.run_coroutine_threadsafe(
                                    ws_manager.broadcast({
                                        "type": "log",
                                        "log": line,
                                        "timestamp": datetime.now().isoformat()
                                    }),
                                    _main_loop
                                )
                        log_pos = lf.tell()
            except OSError:
                pass

            # Read status from file
            status_text = read_status_file()

            if status_text != last_status:
                last_status = status_text
                parsed, progress = parse_status(status_text)

                if parsed:
                    update_pipeline_status(current_phase=parsed["label"], progress=progress, message=parsed["raw"])

            time.sleep(0.5)
        
        # Close log file
        log_file.close()
        log_file = None
        
        # Read final status
        status_text = read_status_file()
        parsed, progress = parse_status(status_text)
        
        # Check for errors in status
        if status_text and ("failed" in status_text.lower() or "error" in status_text.lower()):
            update_pipeline_status(error=status_text, current_phase="Error", progress=0)
        elif proc is None:
            # Distinguish between never run and stopped/finished
            if not status_text:
                update_pipeline_status(current_phase="Idle", message="Ready to run")
            else:
                update_pipeline_status(current_phase="Stopped", message="Pipeline stopped by user")
        elif proc.returncode == 0:
            update_pipeline_status(current_phase="Complete", progress=100, message="Pipeline completed successfully")
        else:
            update_pipeline_status(error=f"Pipeline exited with code {proc.returncode}", current_phase="Failed")
            
    except Exception as e:
        update_pipeline_status(error=str(e), message=f"Error: {str(e)}", current_phase="Error")
        if log_file:
            log_file.close()
            log_file = None
    finally:
        update_pipeline_status(running=False)
        with _pipeline_lock:
            pipeline_process = None
        
        # Auto-sync YouTube metrics after pipeline completes
        try:
            from workflows.performance_database import sync_youtube_metrics
            result = sync_youtube_metrics()
            print(f"[METRICS] Auto-sync completed: {result.get('new_metrics', 0)} metrics updated")
        except Exception as e:
            print(f"[METRICS] Auto-sync failed: {e}")
        
        # Ensure log file is closed
        if log_file:
            try:
                log_file.close()
            except OSError:
                pass
        
        # Clean up pending download file
        try:
            if os.path.exists(PENDING_DOWNLOAD_FILE):
                os.remove(PENDING_DOWNLOAD_FILE)
        except OSError:
            pass


@app.post("/api/pipeline/run")
@limiter.limit("5/minute")
async def run_pipeline(request: Request, _: bool = Depends(verify_api_key)):
    """Trigger pipeline run - accepts JSON body with optional video_url and phases"""
    if get_pipeline_status()["running"]:
        return {"status": "already_running", "message": "Pipeline is already running"}
    
    try:
        body = await request.json()
    except Exception:
        body = {}
    video_url = (body.get("video_url") or "").strip()
    source = body.get("source", "youtube" if not video_url else "url")
    phases = body.get("phases")  # e.g. [4] or [3,4]
    
    thread = threading.Thread(target=run_pipeline_async, args=(source, video_url, phases))
    thread.daemon = True
    thread.start()
    
    return {"status": "started", "source": source, "video_url": video_url, "phases": phases}


@app.post("/api/pipeline/stop")
@limiter.limit("10/minute")
async def stop_pipeline(request: Request, _: bool = Depends(verify_api_key)):
    """Stop pipeline"""
    global pipeline_process
    
    with _pipeline_lock:
        proc = pipeline_process
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
            pipeline_process = None
    
    update_pipeline_status(running=False, message="Stopped")
    
    await ws_manager.broadcast({
        "type": "pipeline:status",
        "data": get_pipeline_status()
    })
    
    return {"status": "stopped"}


@app.get("/api/pipeline/settings")
async def get_pipeline_settings(_: bool = Depends(verify_api_key)):
    """Get pipeline settings"""
    return load_pipeline_settings()


@app.post("/api/pipeline/settings")
async def save_pipeline_settings_endpoint(settings: dict, _: bool = Depends(verify_api_key)):
    """Save pipeline settings"""
    save_pipeline_settings(settings)
    return {"status": "saved"}


@app.get("/api/pipeline/logs")
async def get_pipeline_logs(_: bool = Depends(verify_api_key)):
    """Get pipeline execution logs"""
    try:
        if os.path.exists(PIPELINE_LOG):
            with open(PIPELINE_LOG, "r") as f:
                logs = f.read()
            return {"logs": logs, "exists": True}
        return {"logs": "", "exists": False}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ---------------------------------------------------------------------------
# Metrics Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/metrics/summary")
async def get_metrics_summary(_: bool = Depends(verify_api_key)):
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
async def get_video_metrics(_: bool = Depends(verify_api_key)):
    """Get all videos with metrics"""
    videos = get_all_videos_with_metrics()
    return {"videos": videos}


@app.get("/api/metrics/content-performance")
async def get_content_performance(_: bool = Depends(verify_api_key)):
    """Get content type performance stats"""
    return get_variant_performance_stats()


@app.post("/api/metrics/sync")
@limiter.limit("1/minute")
async def sync_youtube_metrics(request: Request, _: bool = Depends(verify_api_key)):
    """Trigger YouTube metrics sync - rate limited"""
    try:
        from workflows.performance_database import sync_youtube_metrics
        result = sync_youtube_metrics(days=7, max_results=50)
        
        await ws_manager.broadcast({
            "type": "metrics:updated",
            "data": result
        })
        
        return {"status": "synced", "result": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


# ---------------------------------------------------------------------------
# TikTok Analytics Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/metrics/tiktok/summary")
async def get_tiktok_summary(_: bool = Depends(verify_api_key)):
    """Aggregated TikTok stats"""
    from workflows.tiktok_analytics import get_tiktok_summary as _get_summary
    return _get_summary()


@app.get("/api/metrics/tiktok/videos")
async def get_tiktok_videos(_: bool = Depends(verify_api_key)):
    """All TikTok videos with metrics"""
    from workflows.tiktok_analytics import get_tiktok_videos as _get_videos
    return {"videos": _get_videos()}


@app.get("/api/metrics/tiktok/daily")
async def get_tiktok_daily(days: int = 30, _: bool = Depends(verify_api_key)):
    """Daily trend data for charts"""
    from workflows.tiktok_analytics import get_tiktok_daily_metrics
    return {"daily": get_tiktok_daily_metrics(days)}


@app.get("/api/metrics/tiktok/games")
async def get_tiktok_games(_: bool = Depends(verify_api_key)):
    """Per-game stats for TikTok videos"""
    from workflows.tiktok_analytics import get_tiktok_game_stats
    return {"games": get_tiktok_game_stats()}


@app.get("/api/metrics/tiktok/comparison")
async def get_cross_platform_comparison(_: bool = Depends(verify_api_key)):
    """Side-by-side YouTube vs TikTok for matched videos"""
    from workflows.tiktok_analytics import get_tiktok_videos
    from workflows.performance_database import get_all_videos_with_metrics

    tiktok_vids = get_tiktok_videos()
    youtube_vids = get_all_videos_with_metrics()

    # Build comparison by matching titles
    matched = []
    for tt in tiktok_vids:
        tt_title = (tt.get('title') or '').lower()
        best_match = None
        best_score = 0

        for yt in youtube_vids:
            yt_title = (yt.get('title') or '').lower()
            if not yt_title:
                continue

            # Simple substring matching
            if tt_title[:20] in yt_title or yt_title[:20] in tt_title:
                score = 80
            else:
                from difflib import SequenceMatcher
                score = int(SequenceMatcher(None, tt_title[:50], yt_title[:50]).ratio() * 100)

            if score > best_score:
                best_score = score
                best_match = yt

        if best_match and best_score >= 50:
            matched.append({
                'tiktok': tt,
                'youtube': best_match,
                'confidence': best_score,
            })

    return {"matched": matched, "total_tiktok": len(tiktok_vids), "total_youtube": len(youtube_vids)}


@app.get("/api/metrics/cross-platform")
async def get_cross_platform_stats(_: bool = Depends(verify_api_key)):
    """Get cross-platform performance statistics for unified dashboard."""
    from workflows.performance_database import get_cross_platform_stats as _get_stats
    try:
        stats = _get_stats()
        return stats
    except Exception as e:
        return {"error": str(e), "youtube": {}, "tiktok": {}, "tiktok_games": []}


EXPECTED_TIKTOK_FILES = {'Content.csv', 'Overview.csv', 'Viewers.csv', 'FollowerHistory.csv', 'FollowerActivity.csv', 'FollowerGender.csv', 'FollowerTopTerritories.csv'}


@app.post("/api/metrics/tiktok/import")
async def import_tiktok_data(
    request: Request,
    _: bool = Depends(verify_api_key),
    files: List[UploadFile] = File(...),
):
    """Import TikTok CSV files uploaded by the user."""
    from workflows.tiktok_analytics import import_tiktok_data as _import

    if not files:
        return JSONResponse(status_code=400, content={"status": "error", "message": "No files uploaded"})

    seen = set()
    for f in files:
        if not f.filename or not f.filename.endswith('.csv'):
            return JSONResponse(status_code=400, content={"status": "error", "message": f"Invalid file: {f.filename} — must be .csv"})
        if f.filename not in EXPECTED_TIKTOK_FILES:
            return JSONResponse(status_code=400, content={"status": "error", "message": f"Unexpected file: {f.filename} — expected one of: {', '.join(sorted(EXPECTED_TIKTOK_FILES))}"})
        if f.filename in seen:
            return JSONResponse(status_code=400, content={"status": "error", "message": f"Duplicate file: {f.filename}"})
        seen.add(f.filename)

    temp_dir = tempfile.mkdtemp()
    try:
        for f in files:
            content = await f.read()
            if len(content) > 10 * 1024 * 1024:
                return JSONResponse(status_code=400, content={"status": "error", "message": f"File too large: {f.filename} — max 10MB"})
            with open(os.path.join(temp_dir, f.filename), 'wb') as out:
                out.write(content)

        result = _import(csv_dir=temp_dir)
        await ws_manager.broadcast({"type": "tiktok:updated", "data": result})
        return {"status": "imported", "result": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.post("/api/metrics/tiktok/match")
@limiter.limit("1/minute")
async def match_tiktok_to_local(request: Request, _: bool = Depends(verify_api_key)):
    """Match TikTok videos to Cogitator clips"""
    from workflows.tiktok_analytics import match_tiktok_to_clips
    try:
        result = match_tiktok_to_clips()
        return {"status": "matched", "result": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


# ---------------------------------------------------------------------------
# Scripts Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/scripts")
async def get_scripts(_: bool = Depends(verify_api_key)):
    """Get all scripts"""
    from workflows.performance_database import get_all_scripts
    scripts = get_all_scripts()
    return {"scripts": scripts}


@app.get("/api/scripts/{script_id}")
async def get_script(script_id: str, _: bool = Depends(verify_api_key)):
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


@app.get("/api/scripts/{script_id}/metadata")
async def get_script_metadata(script_id: str, _: bool = Depends(verify_api_key)):
    """Get script metadata (description, hashtags, tags, review status)"""
    from workflows.performance_database import get_script_by_id

    script = get_script_by_id(script_id)
    result = {
        "title": "",
        "description": "",
        "hashtags": "",
        "tags": "",
        "content_type": "",
        "review_status": "pending",
        "quarantined": False,
    }
    if script:
        result.update({
            "title": script.get("title", ""),
            "description": script.get("description", ""),
            "hashtags": script.get("hashtags", ""),
            "tags": script.get("tags", ""),
            "content_type": script.get("content_type", ""),
        })

    # Overlay .meta.json review / quarantine flags when present
    try:
        scripts_dir = os.path.join(WORKSPACE, "scripts")
        meta_candidates = []
        video = (script or {}).get("video_name") or ""
        if video:
            meta_candidates.extend(
                [os.path.join(scripts_dir, f) for f in os.listdir(scripts_dir)
                 if f.startswith(video) and f.endswith(".meta.json")]
            )
        safe_id = os.path.basename(script_id)
        meta_candidates.append(os.path.join(scripts_dir, f"{safe_id}.meta.json"))
        for path in meta_candidates:
            if os.path.exists(path):
                with open(path) as f:
                    meta = json.load(f)
                for k in ("title", "description", "hashtags", "tags", "review_status",
                          "quarantined", "skip_tts", "factuality_score"):
                    if k in meta and meta[k] not in (None, ""):
                        result[k] = meta[k]
                if isinstance(meta.get("hashtags"), list):
                    result["hashtags"] = ",".join(meta["hashtags"])
                if isinstance(meta.get("tags"), list):
                    result["tags"] = ",".join(meta["tags"])
                break
    except Exception:
        pass

    if not script and not result.get("title"):
        return {"error": "Script not found"}
    return result


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
async def get_all_learnings(_: bool = Depends(verify_api_key)):
    """Get all learnings"""
    learnings = get_learnings()
    return {"learnings": learnings}


@app.get("/api/learnings/weights")
async def get_learning_weights(_: bool = Depends(verify_api_key)):
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
async def get_games(_: bool = Depends(verify_api_key)):
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
    full_mapping = get_full_series_mapping()
    series_to_games = {}
    for game_key, series_name in full_mapping.items():
        if game_key in games or series_name in games:
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

    # First, add all franchises from series_to_games
    for series_key, child_games in series_to_games.items():
        if series_key not in seen_franchises:
            # Only add if there are actual child games
            if child_games:
                result.append({
                    "name": series_key,
                    "is_series": True,
                    "display_name": " ".join(series_key.split("_")).title(),
                    "children": [g.replace("_", " ").title() for g in child_games]
                })
                seen_franchises.add(series_key)

    # Then add individual games that are not part of any franchise
    for game in games:
        game_lower = game.lower().replace(" ", "_")
        # Skip if this is a franchise key
        if game_lower in seen_franchises:
            continue
        # Check if this game belongs to a known series
        series_name = full_mapping.get(game_lower)
        if series_name and series_name in seen_franchises:
            continue  # Skip, already added as part of franchise
        # Regular game (no franchise)
        result.append({
            "name": game,
            "is_series": False,
            "display_name": game.replace("_", " ").title(),
            "children": []
        })

    return {"games": result}


@app.get("/api/context/{game}")
async def get_game_context(game: str, _: bool = Depends(verify_api_key)):
    """Get all context items for a game or franchise.

    If game is a franchise key, returns franchise context.
    If game is a child game of a franchise, returns the FRANCHISE context (not individual game).
    """
    game_title = sanitize_input(game, max_length=100)
    game_key = game_title.lower().replace(" ", "_").strip()
    cm = get_context_manager()

    # Check if this is a franchise key or child game
    full_mapping = get_full_series_mapping()
    is_franchise = game_key in full_mapping.values()
    series_name = None

    if not is_franchise:
        series_name = full_mapping.get(game_key)
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

    # Ensure ContextManagerV2 is loaded (assigns UUIDs to all items)
    cm.load_all_contexts()

    # Use ContextManagerV2 for per-game data so items always have UUIDs
    if not is_franchise and not series_name:
        characters = [c.to_dict() for c in cm.get_context_items(game_key, "character")]
        locations = [l.to_dict() for l in cm.get_context_items(game_key, "location")]
        terms = [t.to_dict() for t in cm.get_context_items(game_key, "term")]
        relationships = [r.to_dict() for r in cm.get_context_items(game_key, "relationship")]
        context_data = {
            "characters": characters,
            "locations": locations,
            "key_terms": terms,
            "relationships": relationships,
        }
    else:
        context_data = all_context.get(game_key, {}).get("context", {})

    # If this is a franchise, also merge in context from child games
    if is_franchise or series_name:
        child_contexts = []
        for child_key, series_val in full_mapping.items():
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
            "characters": [{"name": c} for c in sorted(merged["characters"]) if c],
            "locations": [{"name": l} for l in sorted(merged["locations"]) if l],
            "key_terms": [{"name": t} for t in sorted(merged["key_terms"]) if t],
            "relationships": merged["relationships"]
        }

    # Accept relationships in either old format (from/to) or ContextManagerV2 format (id/name)
    valid_relationships = [
        r for r in context_data.get("relationships", [])
        if isinstance(r, dict) and (r.get("from") or r.get("id"))
    ]

    return {
        "characters": context_data.get("characters", []),
        "locations": context_data.get("locations", []),
        "terms": context_data.get("key_terms", []),
        "relationships": valid_relationships,
        "games": context_data.get("games", []),
        "is_franchise": is_franchise or series_name is not None,
        "franchise_name": game_key if (is_franchise or series_name) else None
    }


@app.get("/api/context/all/graph")
async def get_all_games_graph(_: bool = Depends(verify_api_key)):
    """Get graph data for all games combined."""
    from workflows.graph_builder import build_all_games_graph
    return build_all_games_graph()


@app.get("/api/context/{game}/graph")
async def get_graph_data(game: str, _: bool = Depends(verify_api_key)):
    """Get graph data in Cytoscape.js format for a single game."""
    from workflows.graph_builder import build_single_game_graph, get_graph_cache_key, get_cached_graph, set_cached_graph
    game_title = sanitize_input(game, max_length=100)
    game_key = game_title.lower().replace(" ", "_").strip()
    
    cache_key = get_graph_cache_key()
    cached = get_cached_graph(f"single:{game_key}:{cache_key}")
    if cached:
        return cached

    cm = get_context_manager()
    cm.load_all_contexts()

    graph = build_single_game_graph(game_key, cm)
    graph["stats"].pop("game_key", None)
    set_cached_graph(f"single:{game_key}:{cache_key}", graph)
    return graph


@app.get("/api/context/{game}/graph/search")
async def search_graph(game: str, q: str = "", type: str = "", _: bool = Depends(verify_api_key)):
    """Search for entities in the graph by name or type."""
    from workflows.graph_builder import build_single_game_graph, get_graph_cache_key, get_cached_graph, set_cached_graph
    game_title = sanitize_input(game, max_length=100)
    game_key = game_title.lower().replace(" ", "_").strip()
    
    cache_key = get_graph_cache_key()
    cached = get_cached_graph(f"single:{game_key}:{cache_key}")
    if not cached:
        cm = get_context_manager()
        cm.load_all_contexts()
        cached = build_single_game_graph(game_key, cm)
        cached["stats"].pop("game_key", None)
        set_cached_graph(f"single:{game_key}:{cache_key}", cached)
    
    query = q.strip().lower()
    filter_type = type.strip().lower()
    
    results = []
    for node in cached.get("nodes", []):
        # Filter by type if specified
        if filter_type and node.get("type", "").lower() != filter_type:
            continue
        
        # Search by name (case-insensitive substring match)
        if query and query not in node.get("label", "").lower():
            continue
        
        results.append({
            "id": node.get("id"),
            "label": node.get("label"),
            "type": node.get("type"),
            "game": node.get("game"),
        })
    
    return {"results": results, "total": len(results)}


@app.get("/api/context/{game}/graph/stats")
async def get_graph_statistics(game: str, _: bool = Depends(verify_api_key)):
    """Get detailed graph statistics including centrality and clustering."""
    from workflows.graph_builder import build_single_game_graph, get_graph_cache_key, get_cached_graph, set_cached_graph
    game_title = sanitize_input(game, max_length=100)
    game_key = game_title.lower().replace(" ", "_").strip()
    
    cache_key = get_graph_cache_key()
    cached = get_cached_graph(f"single:{game_key}:{cache_key}")
    if not cached:
        cm = get_context_manager()
        cm.load_all_contexts()
        cached = build_single_game_graph(game_key, cm)
        cached["stats"].pop("game_key", None)
        set_cached_graph(f"single:{game_key}:{cache_key}", cached)
    
    nodes = cached.get("nodes", [])
    edges = cached.get("edges", [])
    
    # Count by type
    type_counts = {}
    for node in nodes:
        ntype = node.get("type", "unknown")
        type_counts[ntype] = type_counts.get(ntype, 0) + 1
    
    # Count by edge type
    edge_type_counts = {}
    for edge in edges:
        etype = edge.get("type", "unknown")
        edge_type_counts[etype] = edge_type_counts.get(etype, 0) + 1
    
    # Calculate degree centrality (top 10 most connected)
    degree_map = {}
    for edge in edges:
        source = edge.get("source", "")
        target = edge.get("target", "")
        if source:
            degree_map[source] = degree_map.get(source, 0) + 1
        if target:
            degree_map[target] = degree_map.get(target, 0) + 1
    
    # Sort by degree and get top 10
    top_central = sorted(degree_map.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "node_types": type_counts,
        "edge_types": edge_type_counts,
        "top_central_nodes": [{"id": n, "degree": d} for n, d in top_central],
        "isolated_nodes": [n.get("id") for n in nodes if n.get("id") not in degree_map],
    }


@app.get("/api/context/{game}/segments")
async def get_segment_references(game: str, _: bool = Depends(verify_api_key)):
    """Get segment references for context nodes"""
    # Sanitize game name
    game = sanitize_input(game, max_length=100)
    SEGMENT_REF_FILE = os.path.join(WORKSPACE, "Context/segment_references.json")
    game_key = game.lower().replace(" ", "_")
    
    try:
        if os.path.exists(SEGMENT_REF_FILE):
            with open(SEGMENT_REF_FILE, "r") as f:
                refs = json.load(f)
            return {"references": refs.get(game_key, {})}
        return {"references": {}}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ---------------------------------------------------------------------------
# Prompt Editor Endpoints
# ---------------------------------------------------------------------------

PROMPT_FILE = os.path.join(WORKSPACE, "prompts", "base.j2")
PROMPT_BACKUP_FILE = os.path.join(WORKSPACE, "prompts", "base.j2.bak")


@app.get("/api/prompts/script")
async def get_script_prompt(_: bool = Depends(verify_api_key)):
    """Get the current script generation prompt template."""
    try:
        if os.path.exists(PROMPT_FILE):
            with open(PROMPT_FILE, "r") as f:
                content = f.read()
            return {"content": content}
        return {"content": "", "error": "Prompt file not found"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.put("/api/prompts/script")
async def save_script_prompt(request: Request, _: bool = Depends(verify_api_key)):
    """Save an edited script generation prompt template."""
    try:
        body = await request.json()
        content = body.get("content", "")

        if not content.strip():
            return JSONResponse(status_code=400, content={"error": "Content cannot be empty"})

        # Validate Jinja2 syntax
        try:
            from jinja2 import Environment
            env = Environment()
            env.parse(content)
        except Exception as e:
            return JSONResponse(status_code=400, content={"error": f"Jinja2 syntax error: {str(e)}"})

        # Backup existing file
        if os.path.exists(PROMPT_FILE):
            import shutil
            shutil.copy2(PROMPT_FILE, PROMPT_BACKUP_FILE)

        # Write new content
        os.makedirs(os.path.dirname(PROMPT_FILE), exist_ok=True)
        with open(PROMPT_FILE, "w") as f:
            f.write(content)

        return {"status": "saved"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.put("/api/context/{game}/{item_type}/{item_id}")
@limiter.limit("10/minute")
async def update_context_item(request: Request, game: str, item_type: str, item_id: str, _: bool = Depends(verify_api_key), data: dict = Body(...)):
    """Update a context item"""
    # Sanitize inputs
    game_title = sanitize_input(game, max_length=100)
    game_key = game_title.lower().replace(" ", "_").strip()
    item_id = sanitize_input(item_id, max_length=100)
    from workflows.context_manager_v2 import update_item, get_items
    result = update_item(game_key, item_id, **data)
    if not result:
        for item in get_items(game_key, item_type):
            if item.name == item_id:
                result = update_item(game_key, item.id, **data)
                break
    if result:
        return {"status": "updated", "item": result.to_dict()}
    return JSONResponse(status_code=404, content={"error": "Item not found"})


@app.delete("/api/context/{game}/{item_type}/{item_id}")
@limiter.limit("5/minute")
async def delete_context_item(request: Request, game: str, item_type: str, item_id: str, _: bool = Depends(verify_api_key)):
    """Delete a context item"""
    # Sanitize inputs
    game_title = sanitize_input(game, max_length=100)
    game_key = game_title.lower().replace(" ", "_").strip()
    item_id = sanitize_input(item_id, max_length=100)
    from workflows.context_manager_v2 import delete_item, get_items
    result = delete_item(game_key, item_id)
    if not result:
        for item in get_items(game_key, item_type):
            if item.name == item_id:
                result = delete_item(game_key, item.id)
                break
    if result:
        return {"status": "deleted"}
    return JSONResponse(status_code=404, content={"error": "Item not found"})


# ---------------------------------------------------------------------------
# TTS Learning Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/tts/voices")
async def get_tts_voices(_: bool = Depends(verify_api_key)):
    """Get available TTS voices (Kokoro primary, with Gemini fallback names)"""
    from workflows.pipeline.phase_tts_kokoro import KOKORO_VOICES
    return {"voices": KOKORO_VOICES, "legacy_voices": TTS_VOICES}


@app.get("/api/tts/learnings")
async def get_tts_learnings(_: bool = Depends(verify_api_key)):
    """Get TTS performance learning data"""
    learnings = get_tts_learning_data()
    return {"learnings": learnings}


@app.get("/api/learning/dashboard")
async def get_learning_dashboard(_: bool = Depends(verify_api_key)):
    """Get learning dashboard data with insights and A/B test status."""
    from workflows.performance_database import (
        get_learning_insights, get_active_ab_tests, get_ab_test_history,
        get_content_type_effectiveness,
    )
    
    insights = get_learning_insights()
    active_tests = get_active_ab_tests()
    test_history = get_ab_test_history()
    content_effectiveness = get_content_type_effectiveness()
    
    return {
        "insights": insights,
        "active_tests": active_tests,
        "test_history": test_history,
        "content_effectiveness": content_effectiveness,
    }


@app.get("/api/learning/tiktok-signals")
async def get_tiktok_learning_signals(_: bool = Depends(verify_api_key)):
    """Get TikTok engagement signals that influence the learning system."""
    from workflows.tiktok_analytics import get_tiktok_engagement_by_game, get_tiktok_retention_signals
    
    engagement_by_game = get_tiktok_engagement_by_game()
    retention_signals = get_tiktok_retention_signals()
    
    # Calculate bonuses/penalties for each game
    game_effects = []
    for signal in retention_signals:
        game = signal['game']
        engagement = signal['engagement_ratio']
        
        if engagement > 3.0:
            bonus = min(5.0, (engagement - 3.0) * 1.0)
            effect = 'bonus'
        elif engagement < 1.0 and engagement > 0:
            penalty = min(3.0, (1.0 - engagement) * 2.0)
            bonus = -penalty
            effect = 'penalty'
        else:
            bonus = 0
            effect = 'neutral'
        
        game_effects.append({
            'game': game,
            'engagement_ratio': engagement,
            'video_count': signal['video_count'],
            'avg_views': signal['avg_views'],
            'total_views': signal['total_views'],
            'score_effect': round(bonus, 1),
            'effect_type': effect,
        })
    
    # Sort by effect (bonuses first, then neutral, then penalties)
    game_effects.sort(key=lambda x: x['score_effect'], reverse=True)
    
    return {
        'games': game_effects,
        'total_games': len(game_effects),
        'bonus_games': len([g for g in game_effects if g['effect_type'] == 'bonus']),
        'penalty_games': len([g for g in game_effects if g['effect_type'] == 'penalty']),
        'neutral_games': len([g for g in game_effects if g['effect_type'] == 'neutral']),
    }


@app.post("/api/learning/ab-test")
async def create_ab_test_endpoint(request: Request, api_key: str = Depends(verify_api_key)):
    """Create a new A/B test."""
    body = await request.json()
    test_name = body.get("test_name", "")
    test_type = body.get("test_type", "")
    variant_a = body.get("variant_a", {})
    variant_b = body.get("variant_b", {})
    from workflows.performance_database import create_ab_test
    test_id = create_ab_test(test_name, test_type, variant_a, variant_b)
    return {"test_id": test_id, "status": "created"}


@app.post("/api/learning/ab-test/{test_id}/result")
async def record_ab_test_result_endpoint(request: Request, test_id: str, api_key: str = Depends(verify_api_key)):
    """Record an A/B test result."""
    body = await request.json()
    variant = body.get("variant", "")
    performance_score = body.get("performance_score", 0)
    from workflows.performance_database import record_ab_test_result
    record_ab_test_result(test_id, variant, performance_score)
    return {"status": "recorded"}


@app.get("/api/learning/ab-test/{test_id}")
async def get_ab_test_result_endpoint(test_id: str, _: bool = Depends(verify_api_key)):
    """Get A/B test results."""
    from workflows.performance_database import get_ab_test_results
    result = get_ab_test_results(test_id)
    if result is None:
        return JSONResponse(status_code=404, content={"error": "Test not found"})
    return result


@app.get("/api/learning/ab-tests")
async def get_ab_tests_list(_: bool = Depends(verify_api_key)):
    """Get all active and completed A/B tests."""
    from workflows.performance_database import get_active_ab_tests, get_ab_test_history
    return {
        "active": get_active_ab_tests(),
        "history": get_ab_test_history(),
    }


@app.get("/api/learning/ab-current")
async def get_current_ab_test(_: bool = Depends(verify_api_key)):
    """Get info about the current active A/B test with variant assignment details."""
    from workflows.performance_database import get_current_ab_test_info
    result = get_current_ab_test_info()
    return result or {"message": "No active A/B test"}


# ---------------------------------------------------------------------------
# System / Desktop Port Endpoints
# ---------------------------------------------------------------------------
from pydantic import BaseModel

@app.get("/api/config")
async def get_config(_: bool = Depends(verify_api_key)):
    env_file = os.path.join(WORKSPACE, ".env")
    config = {"GAME_TITLE": "", "TTS_VOICE": "", "NUM_SHORTS": "0", "CLIPS_PER_INTERVAL": "5", "PARENT_FRANCHISE": "", "SRT_MAX_WORDS": "5", "SRT_FONT_SIZE": "22", "SRT_FONT_COLOR": "", "SRT_MARGIN_V": "60", "SRT_FONT_NAME": "Open Sans", "SRT_FONT_OUTLINE": "2", "SRT_FONT_SHADOW": "1", "SRT_OUTLINE_COLOR": "", "SRT_SUB_GAP": "0.5", "SRT_MIN_DURATION": "1.0", "SRT_MAX_DURATION": "6.0", "SRT_BORDER_STYLE": "outline", "SRT_ALIGNMENT": "center", "CLIP_ORDER": "sequential", "VARIETY_SEED": "42", "TTS_EMOTION": "default", "TTS_SPEED": "1.0"}
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
    NUM_SHORTS: Optional[str] = None
    CLIPS_PER_INTERVAL: Optional[str] = None
    PARENT_FRANCHISE: Optional[str] = None
    SRT_MAX_WORDS: Optional[str] = None
    SRT_FONT_SIZE: Optional[str] = None
    SRT_FONT_COLOR: Optional[str] = None
    SRT_MARGIN_V: Optional[str] = None
    SRT_FONT_NAME: Optional[str] = None
    SRT_FONT_OUTLINE: Optional[str] = None
    SRT_FONT_SHADOW: Optional[str] = None
    SRT_OUTLINE_COLOR: Optional[str] = None
    SRT_SUB_GAP: Optional[str] = None
    SRT_MIN_DURATION: Optional[str] = None
    SRT_MAX_DURATION: Optional[str] = None
    SRT_BORDER_STYLE: Optional[str] = None
    SRT_ALIGNMENT: Optional[str] = None
    CLIP_ORDER: Optional[str] = None
    VARIETY_SEED: Optional[str] = None
    TTS_EMOTION: Optional[str] = None
    TTS_SPEED: Optional[str] = None

@app.post("/api/config")
@limiter.limit("5/minute")
async def update_config(request: Request, updates: ConfigUpdate, _: bool = Depends(verify_api_key)):
    """Update configuration - requires API key"""
    env_file = os.path.join(WORKSPACE, ".env")
    lines = []
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            lines = f.readlines()
    
    update_dict = updates.model_dump(exclude_none=True)
    
    # Validate config values
    errors = []
    for k, v in update_dict.items():
        if k == 'NUM_SHORTS':
            try:
                val = int(v)
                if val < 0 or val > 20:
                    errors.append(f"{k} must be between 0 and 20 (0 = max possible)")
            except ValueError:
                errors.append(f"{k} must be a number")
        elif k == 'CLIPS_PER_INTERVAL':
            try:
                val = int(v)
                if val < 1 or val > 10:
                    errors.append(f"{k} must be between 1 and 10")
            except ValueError:
                errors.append(f"{k} must be a number")
        elif k == 'SRT_MAX_WORDS':
            try:
                val = int(v)
                if val < 3 or val > 20:
                    errors.append(f"{k} must be between 3 and 20")
            except ValueError:
                errors.append(f"{k} must be a number")
        elif k == 'SRT_FONT_SIZE':
            try:
                val = int(v)
                if val < 12 or val > 48:
                    errors.append(f"{k} must be between 12 and 48")
            except ValueError:
                errors.append(f"{k} must be a number")
        elif k == 'SRT_MARGIN_V':
            try:
                val = int(v)
                if val < 0 or val > 200:
                    errors.append(f"{k} must be between 0 and 200")
            except ValueError:
                errors.append(f"{k} must be a number")
        elif k == 'SRT_MIN_DURATION':
            try:
                val = float(v)
                if val < 1.0 or val > 10.0:
                    errors.append(f"{k} must be between 1.0 and 10.0")
            except ValueError:
                errors.append(f"{k} must be a number")
        elif k == 'SRT_MAX_DURATION':
            try:
                val = float(v)
                if val < 1.0 or val > 60.0:
                    errors.append(f"{k} must be between 1.0 and 60.0")
            except ValueError:
                errors.append(f"{k} must be a number")
        elif k == 'SRT_SUB_GAP':
            try:
                val = float(v)
                if val < 0.0 or val > 5.0:
                    errors.append(f"{k} must be between 0.0 and 5.0")
            except ValueError:
                errors.append(f"{k} must be a number")
        elif k == 'TTS_VOICE':
            if v:  # empty = let system handle
                from workflows.pipeline.phase_tts_kokoro import KOKORO_VOICES
                from workflows.constants import TTS_VOICES
                if v not in KOKORO_VOICES and v not in TTS_VOICES:
                    errors.append(f"{k} must be a valid voice name")
        elif k == 'SRT_BORDER_STYLE':
            if v not in ('outline', 'glow', 'box'):
                errors.append(f"{k} must be one of: outline, glow, box")
        elif k == 'SRT_ALIGNMENT':
            if v not in ('center', 'bottom-left', 'bottom-right', 'top-left', 'top-right'):
                errors.append(f"{k} must be one of: center, bottom-left, bottom-right, top-left, top-right")
        elif k == 'CLIP_ORDER':
            if v not in ('sequential', 'shuffle'):
                errors.append(f"{k} must be one of: sequential, shuffle")
        elif k == 'TTS_EMOTION':
            valid_emotions = ['default', 'happy', 'sad', 'excited', 'calm', 'angry', 'fearful', 'whisper']
            if v not in valid_emotions:
                errors.append(f"{k} must be one of: {', '.join(valid_emotions)}")
        elif k == 'TTS_SPEED':
            try:
                val = float(v)
                if val < 0.5 or val > 2.0:
                    errors.append(f"{k} must be between 0.5 and 2.0")
            except ValueError:
                errors.append(f"{k} must be a number")
    
    if errors:
        return JSONResponse(status_code=400, content={"status": "error", "errors": errors})
    
    for k, v in update_dict.items():
        if k in ('SRT_FONT_COLOR', 'SRT_OUTLINE_COLOR') and isinstance(v, str):
            v = v.lstrip('#')
            update_dict[k] = v
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
    
    # If PARENT_FRANCHISE was updated, add game to franchise mapping
    if 'PARENT_FRANCHISE' in update_dict and 'GAME_TITLE' in update_dict:
        franchise_key = update_dict['PARENT_FRANCHISE']
        game_key = update_dict['GAME_TITLE'].lower().replace(" ", "_").strip()
        if franchise_key and game_key:
            add_to_franchise(game_key, franchise_key)
    
    return {"status": "updated", "config": update_dict}

class DownloadRequest(BaseModel):
    url: str

@app.post("/api/pipeline/download")
@limiter.limit("3/minute")
async def download_from_url(request: Request, req: DownloadRequest, _: bool = Depends(verify_api_key)):
    """Download from URL - requires API key"""
    global pipeline_status, pipeline_process
    if get_pipeline_status()["running"]:
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
    
    cmd = [sys.executable, "workflows/cogitator.py", "download", "-url", url]
    update_pipeline_status(message=f"Downloading from {url}...", running=True, current_phase="downloading")
    
    def run_download():
        global pipeline_process
        try:
            with _pipeline_lock:
                pipeline_process = subprocess.Popen(cmd, cwd=WORKSPACE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, bufsize=1)
            for line in pipeline_process.stdout:
                pass
            pipeline_process.wait()
        except Exception as e:
            pass
        finally:
            update_pipeline_status(running=False)
            with _pipeline_lock:
                pipeline_process = None
            
    thread = threading.Thread(target=run_download)
    thread.daemon = True
    thread.start()
    return {"status": "started"}

@app.get("/api/logs")
async def get_logs(_: bool = Depends(verify_api_key), lines: int = 100):
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
        for f in glob.glob(os.path.join(path, "**/*"), recursive=True):
            if os.path.isfile(f):
                try: os.remove(f)
                except OSError: pass
    return {"status": "cleaned"}

@app.post("/api/context/import")
@limiter.limit("3/minute")
async def import_context(request: Request, _: bool = Depends(verify_api_key)):
    """Import verified context from JSON body (Obsidian markdown import removed)."""
    try:
        body = await request.json()
    except Exception:
        return {"error": "JSON body required"}
    game_title = sanitize_input(str(body.get("game") or body.get("game_title") or ""), max_length=100)
    if not game_title:
        return {"error": "game required"}
    game_key = game_title.lower().replace(" ", "_").strip()
    context = body.get("context") or body
    payload = {
        "characters": context.get("characters", []) or [],
        "locations": context.get("locations", []) or [],
        "key_terms": context.get("key_terms", []) or [],
        "relationships": context.get("relationships", []) or [],
    }
    # Drop self-referential relationships
    cleaned_rels = []
    for rel in payload["relationships"]:
        if isinstance(rel, dict):
            a = (rel.get("from") or "").strip().lower()
            b = (rel.get("to") or "").strip().lower()
            if a and b and a != b:
                cleaned_rels.append(rel)
        elif isinstance(rel, str) and rel.strip():
            cleaned_rels.append(rel.strip())
    payload["relationships"] = cleaned_rels
    if not (payload["characters"] or payload["locations"] or payload["key_terms"]):
        return {"status": "no data"}
    try:
        from workflows.context_manager_v2 import save_verified_context
        save_verified_context(game_key, payload, merge=True)
        cm = get_context_manager()
        if game_key in cm.contexts:
            del cm.contexts[game_key]
        return {"status": "imported", "stats": {k: len(v) for k, v in payload.items()}}
    except Exception as e:
        return {"error": str(e)}


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
    full_mapping = get_full_series_mapping()
    if game_key in full_mapping.values():
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
async def clear_context(request: Request, req: CreateGameRequest, _: bool = Depends(verify_api_key)):
    """Clear context - requires API key"""
    # Sanitize game name
    game_title = sanitize_input(req.game, max_length=100)
    game_key = game_title.lower().replace(" ", "_").strip()
    try:
        from workflows.context_manager_v2 import clear_verified_context as clear_all_context_for_game
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
    from workflows.context_manager_v2 import clear_verified_context as clear_all_context_for_game
    
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
    """WebSocket for real-time updates — requires API key via query param"""
    api_key = websocket.query_params.get("api_key")
    if not api_key or api_key != API_KEY:
        await websocket.close(code=4001, reason="Invalid or missing API key")
        return
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue
            
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.now().isoformat()})
                
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ============================================================================
# SERVE FRONTEND
# ============================================================================

FRONTEND_DIST = os.path.join(WORKSPACE, "frontend", "dist")

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """Serve the frontend build in production, or proxy to Vite in development."""
    from fastapi.responses import FileResponse
    # Try to serve from production build first
    if os.path.exists(FRONTEND_DIST):
        resolved = os.path.normpath(os.path.join(FRONTEND_DIST, full_path)) if full_path else os.path.join(FRONTEND_DIST, "index.html")
        if not resolved.startswith(os.path.normpath(FRONTEND_DIST)):
            return HTMLResponse(status_code=404)
        if os.path.isfile(resolved):
            return FileResponse(resolved)
        # SPA fallback: serve index.html for any route
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
    
    # Development fallback: return inline HTML that loads from Vite dev server
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cogitator - Loading...</title>
    </head>
    <body>
        <div id="root">Loading Cogitator Web UI...</div>
        <script type="module" src="/src/main.tsx"></script>
    </body>
    </html>
    """)


if __name__ == "__main__":
    import uvicorn
    print("Starting Cogitator Backend on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)