import glob, os, re, time

from workflows.cogitator import (
    log, log_error, set_status, notify, env,
    MEDIA_DIR, TRANSCRIPTS_DIR, SCRIPTS_DIR, TTS_DIR, SHORTS_DIR, OUTPUT_DIR,
    PIPELINE_STOP_REQUESTED, PIPELINE_RUNNING,
    _refresh_learning_state, _SCRIPT_ID_MAP,
    _cs_extract_context_from_transcript, _cs_update_context,
    load_verified_context, merge_context_dicts,
    save_verified_context, compute_and_save_implicit_relationships,
    phase_download, phase_transcribe, phase_context,
    phase_scripts, phase_clips, phase_tts,
)
from workflows.cogitator import run as _sf_run


def count_files(pattern):
    return len(glob.glob(pattern))


def fmt_dur(seconds):
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    return f"{h}h {m}m"


def delete_partial_files():
    count = 0
    for pattern in ["*.part", "*.part-*.part", "*.ytdl", "*.f*.mp4.part"]:
        for d in [MEDIA_DIR, SCRIPTS_DIR, TTS_DIR, SHORTS_DIR]:
            for f in glob.glob(os.path.join(d, pattern)):
                os.remove(f)
                count += 1
    return count


def cleanup_all_files():
    """Delete generated files but keep scripts and cogitator data for learning."""
    count = 0
    for d in [MEDIA_DIR, TRANSCRIPTS_DIR, TTS_DIR, SHORTS_DIR]:
        for f in glob.glob(os.path.join(d, "*")):
            if os.path.isfile(f):
                os.remove(f)
                count += 1
        for f in glob.glob(os.path.join(d, "**/*"), recursive=True):
            if os.path.isfile(f):
                os.remove(f)
                count += 1
    log("Cleanup complete (scripts and cogitator data preserved for learning)")
    return count


def find_video():
    for ext in ("*.webm", "*.mp4", "*.mkv"):
        files = sorted(glob.glob(os.path.join(MEDIA_DIR, ext)),
                       key=os.path.getmtime, reverse=True)
        if files:
            return files[0]
    return None


def video_info(path):
    r = _sf_run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path])
    return int(float(r.stdout.strip()))


def run_local_recordings(recording_path):
    """Process local recordings from a directory."""
    global PIPELINE_STOP_REQUESTED, PIPELINE_RUNNING
    PIPELINE_STOP_REQUESTED = False
    PIPELINE_RUNNING = True

    def check_stop():
        if PIPELINE_STOP_REQUESTED:
            log("Pipeline stopped by user")
            set_status("Pipeline Stopped")
            notify("Pipeline stopped by user.")
            return True
        return False

    for d in (MEDIA_DIR, TRANSCRIPTS_DIR, SCRIPTS_DIR, TTS_DIR, SHORTS_DIR, OUTPUT_DIR):
        os.makedirs(d, exist_ok=True)

    _refresh_learning_state()

    if not os.path.exists(recording_path):
        log_error(f"Recording path not found: {recording_path}")
        notify(f"Error: Recording path not found: {recording_path}")
        return

    video_extensions = (".mp4", ".mkv", ".webm", ".avi", ".mov")
    video_files = []
    for f in os.listdir(recording_path):
        if f.lower().endswith(video_extensions):
            video_files.append(os.path.join(recording_path, f))

    if not video_files:
        log_error(f"No video files found in {recording_path}")
        notify(f"No video files found in {recording_path}")
        return

    video_files.sort(key=os.path.getmtime)

    log(f"Found {len(video_files)} local recording(s)")
    notify(f"Processing {len(video_files)} local recording(s)...")

    for i, video_file in enumerate(video_files, 1):
        if check_stop():
            return

        video_name = os.path.basename(video_file)
        log(f"Processing video {i}/{len(video_files)}: {video_name}")

        try:
            duration = video_info(video_file)
            if duration <= 0:
                log_error(f"Invalid video: {video_name}")
                continue

            num_hours = max(1, duration // 3600 + (1 if duration % 3600 > 1800 else 0))
            log(f"Video: {duration}s = {num_hours} hour(s)")

            json_file = phase_transcribe(video_file)
            if check_stop(): return

            phase_context()
            if check_stop(): return

            video_base = os.path.splitext(os.path.basename(video_file))[0]
            json_file = os.path.join(TRANSCRIPTS_DIR, f"{video_base}.json")
            if not os.path.exists(json_file):
                json_file = None

            if json_file:
                phase_scripts(json_file, duration, num_hours, video=video_file)
                if check_stop(): return

                phase_clips(video_file, json_file, duration, num_hours, script_id_map=_SCRIPT_ID_MAP)
                if check_stop(): return

                phase_tts(duration, num_hours, video=video_file)
                if check_stop(): return

            log(f"Video {i}/{len(video_files)} complete!")

            if i < len(video_files):
                log("Waiting 300 seconds before next video...")
                time.sleep(300)

        except Exception as e:
            log_error(f"Error processing {video_name}: {e}")
            continue

    log("All local recordings processed!")
    set_status("Pipeline Complete")
    notify(f"Local recording pipeline complete! Processed {len(video_files)} video(s).")


def run_pipeline(skip=None):
    global PIPELINE_STOP_REQUESTED
    PIPELINE_STOP_REQUESTED = False

    def check_stop():
        if PIPELINE_STOP_REQUESTED:
            log("Pipeline stopped by user")
            set_status("Pipeline Stopped")
            notify("Pipeline stopped by user.")
            return True
        return False

    for d in (MEDIA_DIR, TRANSCRIPTS_DIR, SCRIPTS_DIR, TTS_DIR, SHORTS_DIR, OUTPUT_DIR):
        os.makedirs(d, exist_ok=True)

    _refresh_learning_state()

    skip = skip or set()

    if 1 not in skip:
        phase_download()
        if check_stop(): return

    video = find_video()
    if not video:
        log_error("No video found in media/")
        return
    duration = video_info(video)
    log(f"Target: {os.path.basename(video)} ({duration}s)")

    if 2 not in skip:
        json_file = phase_transcribe(video)
        if check_stop(): return
    else:
        video_name = os.path.splitext(os.path.basename(video))[0]
        json_file = os.path.join(TRANSCRIPTS_DIR, f"{video_name}.json")
        if not os.path.exists(json_file):
            existing = glob.glob(os.path.join(TRANSCRIPTS_DIR, "*.json"))
            json_file = sorted(existing, key=os.path.getmtime, reverse=True)[0] if existing else None

    if 3 not in skip:
        phase_context()
        if check_stop(): return
    elif 2 in skip and json_file:
        log("Phase 2 and 3 skipped, extracting context for scripts...")
        try:
            import json
            with open(json_file) as f:
                data = json.load(f)
            transcript_text = ""
            for seg in data.get("segments", []):
                text = re.sub(r"<[^>]*>", "", seg.get("text", ""))
                if text.strip():
                    transcript_text += text + " "
            if transcript_text:
                game_title = env("GAME_TITLE", "Unknown Game")
                extracted = _cs_extract_context_from_transcript(transcript_text[:10000], game_title)
                if extracted:
                    ctx = _cs_update_context(extracted, os.path.basename(json_file))
                    verified = load_verified_context(game_title)
                    final = merge_context_dicts(verified.get("context", {}) if verified else {}, ctx)
                    save_verified_context(game_title, final)
                    compute_and_save_implicit_relationships(game_title, transcript_text)
                    log(f"Context extracted: {len(final.get('characters', []))} chars, {len(final.get('relationships', []))} rels")
        except Exception as e:
            log(f"Warning: Could not extract context: {e}")

    num_hours = max(1, duration // 3600 + (1 if duration % 3600 > 1800 else 0))
    log(f"Video: {duration}s = {num_hours} hour(s)")

    if 4 not in skip and json_file:
        phase_scripts(json_file, duration, num_hours, video=video)
        if check_stop(): return
    elif 4 not in skip:
        log_error("No transcript for script generation")

    if 5 not in skip and json_file:
        phase_clips(video, json_file, duration, num_hours, script_id_map=_SCRIPT_ID_MAP)
        if check_stop(): return
    elif 5 not in skip:
        log_error("No transcript for clip generation")

    if 6 not in skip:
        phase_tts(duration, num_hours, video=video)
        if check_stop(): return

    log("Pipeline Complete!")
    set_status("Pipeline Complete")

    sc = count_files(os.path.join(SCRIPTS_DIR, "*.txt"))
    cc = count_files(os.path.join(SHORTS_DIR, "*.mp4"))
    tw = count_files(os.path.join(TTS_DIR, "*.wav"))
    ts = count_files(os.path.join(TTS_DIR, "*.srt"))
    tc = count_files(os.path.join(TRANSCRIPTS_DIR, "*.json"))

    notify(f"""Pipeline Complete!

Video: {os.path.basename(video) if video else "Unknown"}
Duration: {fmt_dur(duration)}

Created Files:
Scripts: {sc}
Clips: {cc}
TTS WAVs: {tw}
TTS SRTs: {ts}
Transcripts: {tc}

Total output files: {sc + cc + tw + ts}""")
