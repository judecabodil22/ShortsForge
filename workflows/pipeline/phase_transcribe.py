import gc, glob, json, os, re, time

from workflows.cogitator import (
    log, log_error, set_status, set_progress, env, MEDIA_DIR,
    TRANSCRIPTS_DIR, notify,
    MEMPALACE_AVAILABLE, get_mempalace_manager,
    _correct_transcript_asr_errors,
    _cs_extract_context_from_transcript, _cs_update_context,
    load_verified_context, merge_context_dicts,
    save_verified_context, compute_and_save_implicit_relationships,
)


def phase_transcribe(video):
    if not video or not os.path.exists(video):
        log_error("Phase 2 Failed: Video file not found")
        notify("Phase 2 Failed: Video file not found")
        set_status("Phase 2 FAILED")
        raise RuntimeError("Video file not found")

    basename = os.path.splitext(os.path.basename(video))[0]
    json_file = os.path.join(TRANSCRIPTS_DIR, f"{basename}.json")

    if os.path.exists(json_file):
        log("Phase 2: Transcript exists, skipping transcription")
        notify("Phase 2 Skipped (transcript exists)")

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

                    log(f"Context extracted from existing transcript: {len(final.get('characters', []))} chars, {len(final.get('relationships', []))} rels")
                    notify(f"\U0001f4da Context extracted: {len(final.get('characters', []))} chars, {len(final.get('locations', []))} locs, {len(final.get('relationships', []))} rels")

                    if MEMPALACE_AVAILABLE and env("MEMORY_ENABLED", "true").lower() == "true":
                        try:
                            mp_manager = get_mempalace_manager()
                            if mp_manager and json_file:
                                mp_manager.mine_transcript(json_file, game_title)
                                log("MemPalace: Transcript mined")
                        except Exception as mp_err:
                            log(f"MemPalace mining failed: {mp_err}")
        except Exception as ctx_err:
            log(f"Context extraction failed: {ctx_err}")

        return json_file

    set_status("Phase 2: Transcribing...")
    log("Phase 2: Transcribing...")

    transcription_success = False

    try:
        from faster_whisper import WhisperModel
        log("Using faster-whisper for transcription...")

        whisper_model = env("WHISPER_MODEL", "medium")
        log(f"Transcription model: {whisper_model}")

        model = WhisperModel(whisper_model, device="cpu", compute_type="int8")

        log("Optimized transcription settings:")
        segments, info = model.transcribe(
            video,
            language="en",
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            beam_size=5,
            temperature=0.2,
            condition_on_previous_text=True,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
        )
        srt_path = os.path.join(TRANSCRIPTS_DIR, f"{basename}.srt")
        json_path = os.path.join(TRANSCRIPTS_DIR, f"{basename}.json")

        total_duration = info.duration if hasattr(info, 'duration') and info.duration else 0
        last_update = 0

        def fmt_srt_time(seconds):
            hrs = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            ms = int((seconds % 1) * 1000)
            return f"{hrs:02}:{mins:02}:{secs:02},{ms:03}"

        seg_list = []
        transcript_text = ""
        with open(srt_path, "w") as srt_f:
            sidx = 1
            for segment in segments:
                start = segment.start
                end = segment.end
                text = segment.text.strip()
                if text:
                    seg_list.append({"start": start, "end": end, "text": text})
                    transcript_text += text + " "
                    srt_f.write(f"{sidx}\n")
                    srt_f.write(f"{fmt_srt_time(start)} --> {fmt_srt_time(end)}\n")
                    srt_f.write(f"{text}\n\n")
                    sidx += 1

                if total_duration > 0 and end > last_update:
                    pct = int((end / total_duration) * 100)
                    if pct != last_update:
                        set_progress(2, pct, "Transcribing")
                        last_update = pct

        import json
        with open(json_path, "w") as json_f:
            json.dump({"segments": seg_list}, json_f)

        _correct_transcript_asr_errors(json_path)

        log("faster-whisper transcription complete")
        transcription_success = True

        # Free WhisperModel memory — it can use several GB
        try:
            del model
        except NameError:
            pass
        gc.collect()

        if 'transcript_text' in locals() and transcript_text:
            game_title = env("GAME_TITLE", "Unknown Game")
            extracted = _cs_extract_context_from_transcript(transcript_text[:10000], game_title)

            if extracted:
                ctx = _cs_update_context(extracted, os.path.basename(json_path))
                verified = load_verified_context(game_title)
                final = merge_context_dicts(verified.get("context", {}) if verified else {}, ctx)
                save_verified_context(game_title, final)
                compute_and_save_implicit_relationships(game_title, transcript_text)

                log(f"Context extracted from transcript: {len(final.get('characters', []))} chars, {len(final.get('relationships', []))} rels")
                notify(f"\U0001f4da Context extracted: {len(final.get('characters', []))} chars, {len(final.get('locations', []))} locs, {len(final.get('relationships', []))} rels")

                if MEMPALACE_AVAILABLE and env("MEMORY_ENABLED", "true").lower() == "true":
                    try:
                        mp_manager = get_mempalace_manager()
                        if mp_manager and json_path:
                            mp_manager.mine_transcript(json_path, game_title)
                            log("MemPalace: Transcript mined")
                    except Exception as mp_err:
                        log(f"MemPalace mining failed: {mp_err}")
    except Exception as e:
        log(f"faster-whisper failed: {e}")

        if not transcription_success:
            log("Falling back to stable-ts CLI...")
            try:
                log(f"   stable-ts CLI: output_dir={TRANSCRIPTS_DIR}")
                r = run(["stable-ts", "-y", video, "--output_dir", TRANSCRIPTS_DIR,
                         "--output_format", "srt,json", "--word_timestamps", "False",
                         "--vad", "True", "--language", "en"], check=False)
                if r.stdout:
                    log(f"   stable-ts stdout: {r.stdout[-300:]}")
                if r.returncode != 0:
                    log_error(f"stable-ts CLI failed (exit {r.returncode}): {r.stderr[-300:] if r.stderr else 'Unknown error'}")
                else:
                    transcription_success = True
            except Exception as ts_e:
                log_error(f"stable-ts fallback also failed: {ts_e}")

    if not os.path.exists(json_file):
        log_error("Phase 2 Failed: Transcript file not created")
        notify("Phase 2 Failed: Transcription failed")
        set_status("Phase 2 FAILED")
        raise RuntimeError("Transcription failed")

    notify("Phase 2 Complete: Transcript generated")
    set_status("Phase 2 Complete")
    return json_file
