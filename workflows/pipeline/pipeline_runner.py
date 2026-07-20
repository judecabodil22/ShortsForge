import glob, os, re, time


def _get_cogitator():
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
        run as _sf_run,
    )
    return {
        'log': log, 'log_error': log_error,
        'set_status': set_status, 'notify': notify, 'env': env,
        'MEDIA_DIR': MEDIA_DIR, 'TRANSCRIPTS_DIR': TRANSCRIPTS_DIR,
        'SCRIPTS_DIR': SCRIPTS_DIR, 'TTS_DIR': TTS_DIR,
        'SHORTS_DIR': SHORTS_DIR, 'OUTPUT_DIR': OUTPUT_DIR,
        'PIPELINE_STOP_REQUESTED': PIPELINE_STOP_REQUESTED,
        'PIPELINE_RUNNING': PIPELINE_RUNNING,
        '_refresh_learning_state': _refresh_learning_state,
        '_SCRIPT_ID_MAP': _SCRIPT_ID_MAP,
        '_cs_extract_context_from_transcript': _cs_extract_context_from_transcript,
        '_cs_update_context': _cs_update_context,
        'load_verified_context': load_verified_context,
        'merge_context_dicts': merge_context_dicts,
        'save_verified_context': save_verified_context,
        'compute_and_save_implicit_relationships': compute_and_save_implicit_relationships,
        'phase_download': phase_download, 'phase_transcribe': phase_transcribe,
        'phase_context': phase_context, 'phase_scripts': phase_scripts,
        'phase_clips': phase_clips, 'phase_tts': phase_tts,
        'run': _sf_run,
    }


def count_files(pattern):
    return len(glob.glob(pattern))


def fmt_dur(seconds):
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    return f"{h}h {m}m"


def delete_partial_files():
    c = _get_cogitator()
    count = 0
    for pattern in ["*.part", "*.part-*.part", "*.ytdl", "*.f*.mp4.part"]:
        for d in [c['MEDIA_DIR'], c['SCRIPTS_DIR'], c['TTS_DIR'], c['SHORTS_DIR']]:
            for f in glob.glob(os.path.join(d, pattern)):
                os.remove(f)
                count += 1
    return count


def cleanup_all_files():
    c = _get_cogitator()
    count = 0
    for d in [c['MEDIA_DIR'], c['TRANSCRIPTS_DIR'], c['TTS_DIR'], c['SHORTS_DIR']]:
        for f in glob.glob(os.path.join(d, "*")):
            if os.path.isfile(f):
                os.remove(f)
                count += 1
        for f in glob.glob(os.path.join(d, "**/*"), recursive=True):
            if os.path.isfile(f):
                os.remove(f)
                count += 1
    c['log']("Cleanup complete (scripts and cogitator data preserved for learning)")
    return count


def find_video():
    c = _get_cogitator()
    videos = []
    for ext in ("*.mp4", "*.mkv", "*.webm", "*.avi", "*.mov"):
        videos.extend(glob.glob(os.path.join(c['MEDIA_DIR'], ext)))
    if not videos:
        c['log_error']("No video found in media/")
        return None
    video = sorted(videos, key=os.path.getmtime, reverse=True)[0]
    c['log'](f"Found video: {os.path.basename(video)}")
    return video


def video_info(path):
    c = _get_cogitator()
    try:
        r = c['run'](["ffprobe", "-v", "error", "-show_entries", "format=duration",
                       "-of", "csv=p=0", path], check=False, capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return int(float(r.stdout.strip()))
    except Exception:
        pass
    c['log_error']("Could not determine video duration")
    return 0


def run_pipeline(skip=None):
    c = _get_cogitator()
    global PIPELINE_STOP_REQUESTED
    PIPELINE_STOP_REQUESTED = False

    def check_stop():
        if PIPELINE_STOP_REQUESTED:
            c['log']("Pipeline stopped by user")
            c['set_status']("Pipeline Stopped")
            c['notify']("Pipeline stopped by user.")
            return True
        return False

    for d in (c['MEDIA_DIR'], c['TRANSCRIPTS_DIR'], c['SCRIPTS_DIR'],
              c['TTS_DIR'], c['SHORTS_DIR'], c['OUTPUT_DIR']):
        os.makedirs(d, exist_ok=True)

    c['_refresh_learning_state']()

    skip = skip or set()

    if 1 not in skip:
        c['phase_download']()
        if check_stop(): return

    video = find_video()
    if not video:
        c['log_error']("No video found in media/")
        return
    duration = video_info(video)
    c['log'](f"Target: {os.path.basename(video)} ({duration}s)")

    if 2 not in skip:
        json_file = c['phase_transcribe'](video)
        if check_stop(): return
    else:
        video_name = os.path.splitext(os.path.basename(video))[0]
        json_file = os.path.join(c['TRANSCRIPTS_DIR'], f"{video_name}.json")
        if not os.path.exists(json_file):
            existing = glob.glob(os.path.join(c['TRANSCRIPTS_DIR'], "*.json"))
            json_file = sorted(existing, key=os.path.getmtime, reverse=True)[0] if existing else None

    if 3 not in skip:
        c['phase_context']()
        if check_stop(): return
    elif 2 in skip and json_file:
        c['log']("Phase 2 and 3 skipped, extracting context for scripts...")
        try:
            import json as _json
            with open(json_file) as f:
                data = _json.load(f)
            transcript_text = ""
            for seg in data.get("segments", []):
                text = re.sub(r"<[^>]*>", "", seg.get("text", ""))
                if text.strip():
                    transcript_text += text + " "
            if transcript_text:
                game_title = c['env']("GAME_TITLE", "Unknown Game")
                extracted = c['_cs_extract_context_from_transcript'](transcript_text[:10000], game_title)
                if extracted:
                    ctx = c['_cs_update_context'](extracted, os.path.basename(json_file))
                    verified = c['load_verified_context'](game_title)
                    final = c['merge_context_dicts'](verified.get("context", {}) if verified else {}, ctx)
                    c['save_verified_context'](game_title, final)
                    c['compute_and_save_implicit_relationships'](game_title, transcript_text)
                    c['log'](f"Context extracted: {len(final.get('characters', []))} chars, {len(final.get('relationships', []))} rels")
        except Exception as e:
            c['log'](f"Warning: Could not extract context: {e}")

    num_hours = max(1, duration // 3600 + (1 if duration % 3600 > 1800 else 0))
    c['log'](f"Video: {duration}s = {num_hours} hour(s)")

    if 4 not in skip and json_file:
        c['phase_scripts'](json_file, duration, num_hours, video=video)
        if check_stop(): return
    elif 4 not in skip:
        c['log_error']("No transcript for script generation")

    if 5 not in skip and json_file:
        c['phase_clips'](video, json_file, duration, num_hours, script_id_map=c['_SCRIPT_ID_MAP'])
        if check_stop(): return
    elif 5 not in skip:
        c['log_error']("No transcript for clip generation")

    if 6 not in skip:
        c['phase_tts'](duration, num_hours, video=video)
        if check_stop(): return

    c['log']("Pipeline Complete!")
    c['set_status']("Pipeline Complete")

    sc = count_files(os.path.join(c['SCRIPTS_DIR'], "*.txt"))
    cc = count_files(os.path.join(c['SHORTS_DIR'], "*.mp4"))
    tw = count_files(os.path.join(c['TTS_DIR'], "*.wav"))
    ts = count_files(os.path.join(c['TTS_DIR'], "*.srt"))
    tc = count_files(os.path.join(c['TRANSCRIPTS_DIR'], "*.json"))

    c['notify'](f"""Pipeline Complete!

Video: {os.path.basename(video) if video else "Unknown"}
Duration: {fmt_dur(duration)}

Created Files:
Scripts: {sc}
Clips: {cc}
TTS WAVs: {tw}
TTS SRTs: {ts}
Transcripts: {tc}

Total output files: {sc + cc + tw + ts}""")

    try:
        from workflows.learning_engine import sync_and_train_from_youtube
        c['log']("Post-pipeline: Syncing YouTube analytics for model training...")
        result = sync_and_train_from_youtube(days=30, max_results=50)
        sync_r = result.get('sync_result', {})
        train_r = result.get('training_result', {})
        c['log'](f"YouTube sync: {sync_r.get('matched_count', 0)} matched, "
                 f"{sync_r.get('new_metrics', 0)} new metrics")
        if train_r.get('success'):
            c['log'](f"Model trained: {train_r.get('sample_count', 0)} samples, "
                     f"top features: {[f[0] for f in train_r.get('top_features', [])[:3]]}")
        else:
            c['log'](f"Model training skipped: {train_r.get('error', 'unknown')}")
    except Exception as e:
        c['log'](f"Post-pipeline YouTube sync skipped: {e}")
