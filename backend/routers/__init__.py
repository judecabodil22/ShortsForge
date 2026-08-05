"""Backend routers for Cogitator (extracted from main for hygiene)."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from workflows.constants import WORKSPACE

SCRIPTS_DIR = os.path.join(WORKSPACE, "scripts")
SHORTS_DIR = os.path.join(WORKSPACE, "shorts")
THUMBS_DIR = os.path.join(WORKSPACE, "shorts", "thumbs")
ASSEMBLY_DIR = os.path.join(WORKSPACE, "assembly")


def create_routers(verify_api_key, limiter):
    thumbnails = APIRouter(prefix="/api/thumbnails", tags=["thumbnails"])
    mempalace = APIRouter(prefix="/api/mempalace", tags=["mempalace"])
    publish = APIRouter(prefix="/api/publish", tags=["publish"])
    scripts_review = APIRouter(prefix="/api/scripts", tags=["scripts"])
    metrics_extra = APIRouter(prefix="/api/metrics", tags=["metrics"])

    def _safe_name(name: str) -> str:
        name = os.path.basename(name.strip())
        if not name or ".." in name or "/" in name or "\\" in name:
            raise HTTPException(400, "Invalid filename")
        if not re.match(r"^[\w.\-+=() ]+$", name):
            raise HTTPException(400, "Invalid filename characters")
        return name

    @thumbnails.get("/{filename}")
    @limiter.limit("60/minute")
    async def get_thumbnail(request: Request, filename: str, _: bool = Depends(verify_api_key)):
        filename = _safe_name(filename)
        os.makedirs(THUMBS_DIR, exist_ok=True)
        thumb_path = os.path.join(THUMBS_DIR, filename)
        # Normalize common pattern: video-Short1-thumb.jpg
        if not os.path.exists(thumb_path):
            # Try generate from matching short
            base = filename.replace("-thumb.jpg", "").replace("-thumb.png", "")
            candidates = [
                os.path.join(SHORTS_DIR, f"{base}.mp4"),
                os.path.join(SHORTS_DIR, f"{base}_0.mp4"),
                os.path.join(SHORTS_DIR, f"{base}_1.mp4"),
            ]
            # Also try without -ShortN suffix variants
            for short in Path(SHORTS_DIR).glob(f"{base}*.mp4"):
                candidates.append(str(short))
            src = next((c for c in candidates if os.path.exists(c)), None)
            if src:
                try:
                    subprocess.run(
                        [
                            "ffmpeg",
                            "-y",
                            "-ss",
                            "1",
                            "-i",
                            src,
                            "-frames:v",
                            "1",
                            "-q:v",
                            "3",
                            thumb_path,
                        ],
                        check=False,
                        capture_output=True,
                    )
                except Exception:
                    pass
        if not os.path.exists(thumb_path):
            raise HTTPException(404, "Thumbnail not found")
        # Path traversal guard
        real = os.path.realpath(thumb_path)
        if not real.startswith(os.path.realpath(THUMBS_DIR)):
            raise HTTPException(400, "Invalid path")
        return FileResponse(real, media_type="image/jpeg")

    @mempalace.get("/status")
    @limiter.limit("30/minute")
    async def mempalace_status(request: Request, _: bool = Depends(verify_api_key)):
        try:
            from workflows.mempalace_integration import get_mempalace_status

            return get_mempalace_status()
        except Exception as e:
            return {"available": False, "error": str(e)}

    class ClearReq(BaseModel):
        game: Optional[str] = None

    @mempalace.post("/clear")
    @limiter.limit("3/minute")
    async def mempalace_clear(request: Request, req: ClearReq, _: bool = Depends(verify_api_key)):
        try:
            from game_data.mempalace import get_mempalace_manager

            mgr = get_mempalace_manager()
            if not mgr:
                return {"status": "unavailable"}
            game = (req.game or "").strip()
            if game:
                mgr.clear_game_memory(game)
                return {"status": "cleared", "game": game}
            return {"status": "error", "error": "game required"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @publish.get("/checklist")
    @limiter.limit("30/minute")
    async def publish_checklist(
        request: Request, video: str = "", _: bool = Depends(verify_api_key)
    ):
        video = _safe_name(video) if video else ""
        checks = []

        def add(name, ok, detail=""):
            checks.append({"name": name, "ok": bool(ok), "detail": detail})

        if not video:
            return {"video": "", "ready": False, "checks": [{"name": "video", "ok": False, "detail": "video basename required"}]}

        scripts = list(Path(SCRIPTS_DIR).glob(f"{video}-Script*.txt"))
        metas = list(Path(SCRIPTS_DIR).glob(f"{video}-Script*.meta.json"))
        shorts = list(Path(SHORTS_DIR).glob(f"{video}-Short*.mp4"))
        tts = list(Path(os.path.join(WORKSPACE, "tts")).glob(f"{video}-TTS*.wav"))
        assembled = list(Path(ASSEMBLY_DIR).glob(f"{video}/**/*.mp4")) if os.path.isdir(ASSEMBLY_DIR) else []
        if not assembled:
            assembled = list(Path(ASSEMBLY_DIR).joinpath(video).glob("*.mp4")) if os.path.isdir(os.path.join(ASSEMBLY_DIR, video)) else []

        add("has_scripts", bool(scripts), f"{len(scripts)} scripts")
        add("has_clips", bool(shorts), f"{len(shorts)} clips")
        add("has_tts", bool(tts), f"{len(tts)} wavs")
        add("has_assembled", bool(assembled), f"{len(assembled)} assembled")

        titles_ok = True
        quarantined = 0
        for meta in metas:
            try:
                import json

                data = json.loads(meta.read_text())
                if data.get("quarantined") or data.get("skip_tts"):
                    quarantined += 1
                if not data.get("title"):
                    titles_ok = False
            except Exception:
                titles_ok = False
        add("titles_present", titles_ok and bool(metas), f"{len(metas)} meta files")
        add("not_quarantined", quarantined == 0, f"{quarantined} quarantined")

        # Captions
        srts = list(Path(os.path.join(WORKSPACE, "tts")).glob(f"{video}-TTS*.srt"))
        add("has_captions", bool(srts), f"{len(srts)} srt")

        ready = all(c["ok"] for c in checks)
        return {"video": video, "ready": ready, "checks": checks}

    class ReviewReq(BaseModel):
        status: str  # approved | quarantined | pending

    @scripts_review.post("/{script_id}/review")
    @limiter.limit("30/minute")
    async def review_script(
        request: Request, script_id: str, req: ReviewReq, _: bool = Depends(verify_api_key)
    ):
        status = req.status.strip().lower()
        if status not in ("approved", "quarantined", "pending"):
            raise HTTPException(400, "status must be approved|quarantined|pending")
        script_id = _safe_name(script_id)
        # script_id may be basename without extension
        candidates = [
            os.path.join(SCRIPTS_DIR, f"{script_id}.meta.json"),
            os.path.join(SCRIPTS_DIR, script_id if script_id.endswith(".meta.json") else ""),
            os.path.join(SCRIPTS_DIR, f"{script_id}.txt".replace(".txt.txt", ".txt")).replace(
                ".txt", ".meta.json"
            ),
        ]
        # Also search by partial id
        meta_path = None
        for c in candidates:
            if c and os.path.exists(c):
                meta_path = c
                break
        if not meta_path:
            for p in Path(SCRIPTS_DIR).glob("*.meta.json"):
                if script_id in p.stem or script_id in p.name:
                    meta_path = str(p)
                    break
        if not meta_path:
            # create meta next to matching txt
            txt = None
            for p in Path(SCRIPTS_DIR).glob("*.txt"):
                if script_id in p.stem or script_id == p.stem:
                    txt = p
                    break
            if not txt:
                raise HTTPException(404, "Script not found")
            meta_path = str(txt).replace(".txt", ".meta.json")

        import json

        data = {}
        if os.path.exists(meta_path):
            try:
                data = json.loads(Path(meta_path).read_text())
            except Exception:
                data = {}
        data["review_status"] = status
        if status == "quarantined":
            data["quarantined"] = True
            data["skip_tts"] = True
        elif status == "approved":
            data["quarantined"] = False
            data["skip_tts"] = False
        Path(meta_path).write_text(json.dumps(data, indent=2))
        return {"status": "ok", "review_status": status, "meta": meta_path}

    @metrics_extra.post("/tiktok/auto-import")
    @limiter.limit("5/minute")
    async def tiktok_auto_import(request: Request, _: bool = Depends(verify_api_key)):
        from workflows.tiktok_watcher import auto_import_tiktok

        return auto_import_tiktok()

    return [thumbnails, mempalace, publish, scripts_review, metrics_extra]
