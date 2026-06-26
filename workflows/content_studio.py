#!/usr/bin/env python3
"""
Cogitator Content Studio — DEPRECATED

All functionality moved to cogitator.py as _cs_* private functions.
This file is kept for reference; no code imports from this file.
for creating additional content outside the main pipeline.
"""
import os
import re
import json
import glob
import shutil
from typing import Dict, List, Optional, Tuple, Any

# These imports resolve at runtime when called from cogitator.py context
# where WORKSPACE, TRANSCRIPTS_DIR, SHORTS_DIR, etc. are defined.


def get_cs_dirs():
    """Get Content Studio directory paths."""
    from workflows.cogitator import WORKSPACE, CONTENT_STUDIO_DIR, CS_TRANSCRIPTS_DIR, CS_SHORTS_DIR, CS_SCRIPTS_DIR, CS_TTS_DIR
    return {
        'base': CONTENT_STUDIO_DIR,
        'transcripts': CS_TRANSCRIPTS_DIR,
        'shorts': CS_SHORTS_DIR,
        'scripts': CS_SCRIPTS_DIR,
        'tts': CS_TTS_DIR,
    }


def cs_import_data() -> Tuple[int, int]:
    """Import transcripts and shorts from pipeline to Content Studio."""
    from workflows.cogitator import CONTENT_STUDIO_DIR, CS_TRANSCRIPTS_DIR, CS_SHORTS_DIR, TRANSCRIPTS_DIR, SHORTS_DIR
    
    for d in (CONTENT_STUDIO_DIR, CS_TRANSCRIPTS_DIR, CS_SHORTS_DIR):
        os.makedirs(d, exist_ok=True)
    
    transcript_count = 0
    for f in glob.glob(os.path.join(TRANSCRIPTS_DIR, "*.json")):
        dst = os.path.join(CS_TRANSCRIPTS_DIR, os.path.basename(f))
        if not os.path.exists(dst):
            shutil.move(f, dst)
            transcript_count += 1
    
    short_count = 0
    for f in glob.glob(os.path.join(SHORTS_DIR, "*.mp4")):
        dst = os.path.join(CS_SHORTS_DIR, os.path.basename(f))
        if not os.path.exists(dst):
            shutil.move(f, dst)
            short_count += 1
    
    return transcript_count, short_count


def cs_clear_data() -> int:
    """Clear all files from Content Studio."""
    from workflows.cogitator import CS_TRANSCRIPTS_DIR, CS_SHORTS_DIR, CS_SCRIPTS_DIR, CS_TTS_DIR
    
    count = 0
    for d in (CS_TRANSCRIPTS_DIR, CS_SHORTS_DIR, CS_SCRIPTS_DIR, CS_TTS_DIR):
        if os.path.exists(d):
            for f in glob.glob(os.path.join(d, "*")):
                try:
                    os.remove(f)
                    count += 1
                except OSError:
                    pass
    return count


def cs_find_all_transcripts() -> List[str]:
    """Find all transcripts in Content Studio (including Next folder)."""
    from workflows.cogitator import CS_TRANSCRIPTS_DIR
    
    patterns = [
        os.path.join(CS_TRANSCRIPTS_DIR, "*.json"),
        os.path.join(CS_TRANSCRIPTS_DIR, "Next", "*.json")
    ]
    all_transcripts = []
    for pattern in patterns:
        all_transcripts.extend(glob.glob(pattern))
    
    def get_chapter_num(path):
        match = re.search(r'Chapter\s*(\d+)', os.path.basename(path), re.IGNORECASE)
        return int(match.group(1)) if match else 999
    
    return sorted(all_transcripts, key=get_chapter_num)


def cs_read_transcript(transcript_path: str) -> Optional[str]:
    """Read a single transcript and return text."""
    from workflows.cogitator import log
    
    try:
        with open(transcript_path) as f:
            data = json.load(f)
            text = ""
            for seg in data.get("segments", []):
                t = re.sub(r"<[^>]*>", "", seg.get("text", ""))
                if t.strip():
                    text += t + " "
            return text
    except Exception as e:
        log(f"Error reading {transcript_path}: {e}")
        return None


def cs_read_all_transcripts() -> Optional[str]:
    """Read all transcripts and combine text."""
    from workflows.cogitator import log
    
    transcripts = cs_find_all_transcripts()
    if not transcripts:
        return None
    
    all_text = ""
    for path in transcripts:
        try:
            with open(path) as f:
                data = json.load(f)
                for seg in data.get("segments", []):
                    text = re.sub(r"<[^>]*>", "", seg.get("text", ""))
                    if text.strip():
                        all_text += text + " "
        except Exception as e:
            log(f"Error reading {path}: {e}")
    
    return all_text if all_text else None


def cs_count_files(directory: str, pattern: str = "*") -> int:
    """Count files in a directory matching pattern."""
    return len(glob.glob(os.path.join(directory, pattern)))
