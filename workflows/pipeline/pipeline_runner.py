import glob, json, os, re, time


CHECKPOINT_FILE = ".pipeline_state_{video_basename}.json"


def _checkpoint_path(video_basename):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                        CHECKPOINT_FILE.format(video_basename=video_basename))


def _save_checkpoint(video_basename, phase, item=0):
    path = _checkpoint_path(video_basename)
    state = {}
    if os.path.exists(path):
        try:
            with open(path) as f:
                state = json.load(f)
        except Exception:
            pass
    state['video_basename'] = video_basename
    state['last_phase'] = max(state.get('last_phase', 0), phase)
    state['last_item'] = max(state.get('last_item', 0), item)
    state['completed_phases'] = list(set(state.get('completed_phases', []) + [phase]))
    try:
        with open(path, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


def _load_checkpoint(video_basename):
    path = _checkpoint_path(video_basename)
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def _clear_checkpoint(video_basename):
    path = _checkpoint_path(video_basename)
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass


def _get_cogitator():
    from workflows.cogitator import (
        log, log_error, set_status, notify, env,
        MEDIA_DIR, TRANSCRIPTS_DIR, SCRIPTS_DIR, TTS_DIR, SHORTS_DIR, ASSEMBLY_DIR, OUTPUT_DIR,
        PIPELINE_STOP_REQUESTED, PIPELINE_RUNNING,
        _refresh_learning_state, _SCRIPT_ID_MAP,
        _cs_extract_context_from_transcript, _cs_update_context,
        load_verified_context, merge_context_dicts,
        save_verified_context, compute_and_save_implicit_relationships,
        phase_download, phase_transcribe, phase_context,
        phase_scripts, phase_clips,
        run as _sf_run,
    )
    from workflows.pipeline.phase_assemble import phase_assemble
    from workflows.pipeline.phase_tts import phase_tts
    from workflows.learning_engine import load_retention_history
    return {
        'log': log, 'log_error': log_error,
        'set_status': set_status, 'notify': notify, 'env': env,
        'MEDIA_DIR': MEDIA_DIR, 'TRANSCRIPTS_DIR': TRANSCRIPTS_DIR,
        'SCRIPTS_DIR': SCRIPTS_DIR, 'TTS_DIR': TTS_DIR,
        'SHORTS_DIR': SHORTS_DIR, 'ASSEMBLY_DIR': ASSEMBLY_DIR, 'OUTPUT_DIR': OUTPUT_DIR,
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
        'load_retention_history': load_retention_history,
        'phase_download': phase_download, 'phase_transcribe': phase_transcribe,
        'phase_context': phase_context, 'phase_scripts': phase_scripts,
        'phase_clips': phase_clips, 'phase_tts': phase_tts,
        'phase_assemble': phase_assemble,
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
    for d in [c['MEDIA_DIR'], c['TRANSCRIPTS_DIR'], c['TTS_DIR'], c['SHORTS_DIR'], c['ASSEMBLY_DIR']]:
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

    def check_stop():
        # Read directly from cogitator module to get the current value
        from workflows.cogitator import PIPELINE_STOP_REQUESTED as _stop_requested
        if _stop_requested:
            c['log']("Pipeline stopped by user")
            c['set_status']("Pipeline Stopped")
            c['notify']("Pipeline stopped by user.")
            return True
        return False

    for d in (c['MEDIA_DIR'], c['TRANSCRIPTS_DIR'], c['SCRIPTS_DIR'],
              c['TTS_DIR'], c['SHORTS_DIR'], c['OUTPUT_DIR']):
        os.makedirs(d, exist_ok=True)

    c['_refresh_learning_state']()
    c['load_retention_history']()

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

    video_basename = os.path.splitext(os.path.basename(video))[0]

    # Pipeline checkpoint/resume
    checkpoint = _load_checkpoint(video_basename)
    if checkpoint:
        completed = set(checkpoint.get('completed_phases', []))
        if not skip:
            skip = completed
            c['log'](f"Checkpoint found: phases {sorted(completed)} completed, resuming from phase {max(completed)+1}")
        else:
            # Merge explicit skip with checkpoint
            skip = skip | completed
            c['log'](f"Checkpoint merged: skipping phases {sorted(skip)}")

    if 2 not in skip:
        json_file = c['phase_transcribe'](video)
        if check_stop(): return
        _save_checkpoint(video_basename, 2)
    else:
        video_name = os.path.splitext(os.path.basename(video))[0]
        json_file = os.path.join(c['TRANSCRIPTS_DIR'], f"{video_name}.json")
        if not os.path.exists(json_file):
            existing = glob.glob(os.path.join(c['TRANSCRIPTS_DIR'], "*.json"))
            json_file = sorted(existing, key=os.path.getmtime, reverse=True)[0] if existing else None

    if 3 not in skip:
        c['phase_context']()
        if check_stop(): return
        _save_checkpoint(video_basename, 3)
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

    interval = 1800
    num_shorts = int(c['env']("NUM_SHORTS", "0"))
    max_shorts = max(1, duration // interval + (1 if duration % interval > interval // 2 else 0))
    if num_shorts <= 0:
        num_shorts = max_shorts
    num_shorts = min(num_shorts, max_shorts)

    selected = []
    if json_file:
        from workflows.cogitator import _select_best_intervals
        selected = _select_best_intervals(json_file, duration, num_shorts)
        c['log'](f"Selected {len(selected)} intervals from {max_shorts} possible")
        for s in selected:
            c['log'](f"  Interval {s['index']+1}: {s['start']//60}-{s['end']//60}min (score: {s['score']:.1f})")
    else:
        selected = [{"index": i, "start": i * interval, "end": min((i+1) * interval, duration), "score": 0}
                    for i in range(num_shorts)]

    if 4 not in skip and json_file:
        c['phase_scripts'](json_file, duration, selected, video=video)
        if check_stop(): return
        _save_checkpoint(video_basename, 4)
    elif 4 not in skip:
        c['log_error']("No transcript for script generation")

    if 5 not in skip and json_file:
        c['phase_clips'](video, json_file, duration, selected, script_id_map=c['_SCRIPT_ID_MAP'])
        if check_stop(): return
        _save_checkpoint(video_basename, 5)
    elif 5 not in skip:
        c['log_error']("No transcript for clip generation")

    if 6 not in skip:
        c['phase_tts'](duration, len(selected), video=video)
        if check_stop(): return
        _save_checkpoint(video_basename, 6)

    if 7 not in skip:
        c['phase_assemble'](duration, len(selected), video=video)
        if check_stop(): return
        _save_checkpoint(video_basename, 7)

    _clear_checkpoint(video_basename)
    c['log']("Pipeline Complete!")
    c['set_status']("Pipeline Complete")

    sc = count_files(os.path.join(c['SCRIPTS_DIR'], "*.txt"))
    cc = count_files(os.path.join(c['SHORTS_DIR'], "*.mp4"))
    tw = count_files(os.path.join(c['TTS_DIR'], "*.wav"))
    ts = count_files(os.path.join(c['TTS_DIR'], "*.srt"))
    tc = count_files(os.path.join(c['TRANSCRIPTS_DIR'], "*.json"))
    assembly_dir = os.path.join(os.path.dirname(c['SHORTS_DIR']), "assembly",
                                os.path.splitext(os.path.basename(video))[0] if video else "")
    ac = count_files(os.path.join(assembly_dir, "*.mp4"))

    c['notify'](f"""Pipeline Complete!

Video: {os.path.basename(video) if video else "Unknown"}
Duration: {fmt_dur(duration)}

Created Files:
Scripts: {sc}
Clips: {cc}
TTS WAVs: {tw}
TTS SRTs: {ts}
Transcripts: {tc}
Assembled Shorts: {ac}

Total output files: {sc + cc + tw + ts + ac}""")

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
