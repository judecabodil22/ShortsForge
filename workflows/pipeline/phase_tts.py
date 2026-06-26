import base64, json, os, time, urllib.error, urllib.request

from workflows.cogitator import (
    log, log_error, set_status, set_progress, env, notify,
    SCRIPTS_DIR, TTS_DIR, run,
    PERFORMANCE_DB_AVAILABLE,
    _init_round_robin,
    _rr_get_state, get_next_voice_style,
)


def _load_api_keys():
    """Load API keys from keychain (fallback to empty list)."""
    from workflows.keychain_manager import get_gemini_keys
    return get_gemini_keys()


def _tts_api(text, out_pcm, voice, style, retries=3, delay=60):
    if style:
        text = f"{style} {text}"
    body = json.dumps({
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}
        }
    }).encode()

    api_keys = _load_api_keys()
    if not api_keys:
        api_keys = [env("GEMINI_API_KEY")]

    time.sleep(2)

    for key in api_keys:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={key}"
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})

        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    r = json.loads(resp.read())
                    audio = r["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
                    with open(out_pcm, "wb") as f:
                        f.write(base64.b64decode(audio))
                    return True
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < retries - 1:
                    wait = delay * (2 ** attempt)
                    log(f"   Key ...{key[-6:]} rate limited, waiting {wait}s...")
                    time.sleep(wait)
                else:
                    log(f"   Key ...{key[-6:]} failed: {e.code}")
                    break
        log(f"   Switching to next API key...")

    return False


def _strip_title(script_text):
    lines = script_text.strip().split("\n")
    if lines and lines[0].startswith("TITLE:"):
        return "\n".join(lines[1:]).strip()
    return script_text.strip()


def _get_voice_id(voice_name):
    """Get Gemini TTS voice ID."""
    voices = {
        "Aoede": "Aoede", "Callirrhoe": "Callirrhoe", "Gacrux": "Gacrux",
        "Kore": "Kore", "Leda": "Leda", "Puck": "Puck",
        "Sao": "Sao", "Zephyr": "Zephyr", "Fenrir": "Fenrir",
        "Charon": "Charon", "Orus": "Orus", "Umbriel": "Umbriel",
        "Vindemiatrix": "Vindemiatrix", "Alnilam": "Alnilam", "Schedar": "Schedar",
        "Sadachbia": "Sadachbia", "Rasalgethi": "Rasalgethi", "Algieba": "Algieba"
    }
    return voices.get(voice_name)


def phase_tts(duration, num_hours, video=None):
    video_basename = os.path.splitext(os.path.basename(video))[0] if video else "tts"
    voice = env("TTS_VOICE", "Vindemiatrix")
    if not voice:
        log_error("Phase 6 Failed: TTS_VOICE not configured")
        notify("Phase 6 Failed: TTS voice not set")
        set_status("Phase 6 FAILED")
        raise RuntimeError("TTS_VOICE not configured")

    api_key = env("GEMINI_API_KEY")
    if not api_key:
        log_error("Phase 6 Failed: GEMINI_API_KEY not configured")
        notify("Phase 6 Failed: No API key configured")
        set_status("Phase 6 FAILED")
        raise RuntimeError("GEMINI_API_KEY not configured")

    if _rr_get_state()['voices'] == 0:
        _init_round_robin(num_hours)

    set_status("Phase 6: Generating TTS...")
    log("Phase 6: Generating TTS...")
    notify("Phase 6 Started: Generating TTS...")
    delay = int(env("TTS_DELAY", "120"))

    tts_generated = 0
    for i in range(1, num_hours + 1):
        pct = int(((i - 1) / num_hours) * 100)
        set_progress(5, pct, f"Generating TTS ({i}/{num_hours})")

        padded = f"{i:03d}"
        wav = os.path.join(TTS_DIR, f"{video_basename}-TTS{padded}.wav")
        srt = os.path.join(TTS_DIR, f"{video_basename}-TTS{padded}.srt")
        script_file = os.path.join(SCRIPTS_DIR, f"{video_basename}-Script{padded}.txt")

        if not os.path.exists(wav):
            if not os.path.exists(script_file):
                log(f"   Warning: Script {i} not found, skipping TTS")
                continue
            log(f"   Generating TTS for script {i}...")
            try:
                with open(script_file) as f:
                    txt = f.read()
                if not txt.strip():
                    log_error(f"   Warning: Script {i} is empty, skipping")
                    continue

                pcm = os.path.join(TTS_DIR, f"tts_{padded}.pcm")
                tts_text = _strip_title(txt)

                rr_voice, rr_style = get_next_voice_style()
                log(f"   Using voice: {rr_voice}, style: {rr_style[:40]}...")

                _tts_api(tts_text, pcm, rr_voice, rr_style)

                if not os.path.exists(pcm):
                    log_error(f"   TTS API call failed for script {i}")
                    continue

                r = run(["ffmpeg", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1",
                         "-i", pcm, "-ar", "44100", "-ac", "2", wav], check=False)
                if r.returncode != 0:
                    log_error(f"   ffmpeg failed for script {i}: {r.stderr[-200:] if r.stderr else 'Unknown'}")
                    continue

                if os.path.exists(pcm):
                    os.remove(pcm)
                log(f"   tts_{padded}.wav created")
                tts_generated += 1

                if PERFORMANCE_DB_AVAILABLE:
                    try:
                        clip_pattern = f"{video_basename}-Short{padded}.mp4"
                        import performance_database as pdb
                        conn = pdb.get_db()
                        try:
                            cur = conn.cursor()
                            cur.execute("""
                                SELECT c.id, c.features FROM clips c
                                WHERE c.source_file LIKE ?
                                ORDER BY c.created_at DESC LIMIT 1
                            """, (f"%{clip_pattern}%",))
                            row = cur.fetchone()
                            if row:
                                existing_features = json.loads(row['features'] or '{}') if row['features'] else {}
                                existing_features['voice'] = rr_voice
                                existing_features['style'] = rr_style
                                cur.execute("UPDATE clips SET features = ? WHERE id = ?",
                                            (json.dumps(existing_features), row['id']))
                                conn.commit()
                                log(f"   TTS learning: voice '{rr_voice}' recorded for clip")
                        finally:
                            conn.close()
                    except Exception:
                        pass
                set_status(f"Phase 6: TTS {i}/{num_hours} generated")
                notify(f"TTS {i}/{num_hours} generated")
            except Exception as e:
                log_error(f"   Error generating TTS for script {i}: {e}")
                continue
        else:
            log(f"   TTS {i} WAV exists, skipping")

        if not os.path.exists(srt):
            if not os.path.exists(wav):
                log(f"   Warning: Cannot generate SRT, WAV not found for script {i}")
            else:
                log(f"   Generating SRT for tts_{padded}.wav...")
                srt_out = os.path.splitext(wav)[0] + ".srt"
                srt_max_words = int(env("SRT_MAX_WORDS", "10"))
                try:
                    from faster_whisper import WhisperModel
                    model = WhisperModel(env("WHISPER_MODEL", "medium"), device="cpu", compute_type="int8")
                    segments, _ = model.transcribe(wav, language="en", vad_filter=True)
                    with open(srt_out, "w") as f:
                        idx = 1
                        for seg in segments:
                            start, end, text = seg.start, seg.end, seg.text.strip()
                            if text:
                                words = text.split()
                                if len(words) <= srt_max_words:
                                    f.write(f"{idx}\n")
                                    f.write(f"{int(start//3600):02d}:{int((start%3600)//60):02d}:{int(start%60):02d},000 --> {int(end//3600):02d}:{int((end%3600)//60):02d}:{int(end%60):02d},000\n")
                                    f.write(f"{text}\n\n")
                                    idx += 1
                                else:
                                    chunk_duration = (end - start) / ((len(words) + srt_max_words - 1) // srt_max_words)
                                    for chunk_idx in range(0, len(words), srt_max_words):
                                        chunk_words = words[chunk_idx:chunk_idx + srt_max_words]
                                        chunk_text = ' '.join(chunk_words)
                                        chunk_start = start + (chunk_idx // srt_max_words) * chunk_duration
                                        chunk_end = chunk_start + chunk_duration
                                        f.write(f"{idx}\n")
                                        f.write(f"{int(chunk_start//3600):02d}:{int((chunk_start%3600)//60):02d}:{int(chunk_start%60):02d},000 --> {int(chunk_end//3600):02d}:{int((chunk_end%3600)//60):02d}:{int(chunk_end%60):02d},000\n")
                                        f.write(f"{chunk_text}\n\n")
                                        idx += 1
                    log(f"   tts_{padded}.srt created (faster-whisper)")
                except Exception as e:
                    log_error(f"   SRT failed for tts_{padded}: {e}")
        else:
            log(f"   tts_{padded}.srt exists, skipping")

        if i < num_hours:
            log(f"   Waiting {delay}s")
            time.sleep(delay)

    if tts_generated == 0:
        log_error("Phase 6 Failed: No TTS files were generated")
        notify("Phase 6 Failed: No TTS generated")
        set_status("Phase 6 FAILED")
        raise RuntimeError("No TTS generated")

    set_status("Phase 6 Complete")
    notify(f"Phase 6 Complete: {tts_generated} TTS files generated")
