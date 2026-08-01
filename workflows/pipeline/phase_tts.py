import base64, json, os, time, urllib.error, urllib.request
from workflows.hardware_detect import get_whisper_device

# Voice customization constants
EMOTION_STYLES = {
    'default': '',
    'happy': '[happy]',
    'sad': '[sad]',
    'excited': '[excited]',
    'calm': '[calm]',
    'angry': '[angry]',
    'fearful': '[fearful]',
    'whisper': '[whisper]',
}

def _get_voice_emotion():
    """Get the voice emotion from environment."""
    return os.environ.get('TTS_EMOTION', 'default').strip().lower()

def _get_voice_speed():
    """Get the voice speed from environment."""
    try:
        speed = float(os.environ.get('TTS_SPEED', '1.0'))
        return max(0.5, min(2.0, speed))  # Clamp between 0.5x and 2.0x
    except (ValueError, TypeError):
        return 1.0


def _get_cogitator():
    from workflows.cogitator import (
        log, log_error, set_status, set_progress, env, notify,
        SCRIPTS_DIR, TTS_DIR, run,
        PERFORMANCE_DB_AVAILABLE,
        _init_round_robin,
        _rr_get_state, get_next_voice_style,
    )
    return {
        'log': log, 'log_error': log_error,
        'set_status': set_status, 'set_progress': set_progress,
        'env': env, 'notify': notify,
        'SCRIPTS_DIR': SCRIPTS_DIR, 'TTS_DIR': TTS_DIR, 'run': run,
        'PERFORMANCE_DB_AVAILABLE': PERFORMANCE_DB_AVAILABLE,
        '_init_round_robin': _init_round_robin,
        '_rr_get_state': _rr_get_state,
        'get_next_voice_style': get_next_voice_style,
    }


def _load_api_keys():
    from workflows.keychain_manager import get_gemini_keys
    return get_gemini_keys()


def _tts_api_gemini(text, out_pcm, voice, style, retries=3, delay=60):
    c = _get_cogitator()
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
        api_keys = [c['env']("GEMINI_API_KEY")]

    time.sleep(2)

    for key in api_keys:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent"
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "X-Goog-Api-Key": key})

        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    r = json.loads(resp.read())
                    candidate = r.get("candidates", [{}])[0]
                    if "content" not in candidate:
                        reason = candidate.get("finishReason", "unknown")
                        c['log'](f"   Gemini blocked TTS: {reason}")
                        break
                    audio = candidate["content"]["parts"][0]["inlineData"]["data"]
                    with open(out_pcm, "wb") as f:
                        f.write(base64.b64decode(audio))
                    return True
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < retries - 1:
                    wait = delay * (2 ** attempt)
                    c['log'](f"   Key ...{key[-6:]} rate limited, waiting {wait}s...")
                    time.sleep(wait)
                else:
                    c['log'](f"   Key ...{key[-6:]} failed: {e.code}")
                    break
            except (KeyError, IndexError, json.JSONDecodeError) as e:
                c['log'](f"   TTS API response malformed: {e}")
                break
        c['log'](f"   Switching to next API key...")

    return False


def _tts_api_edge(text, out_wav, voice, style):
    c = _get_cogitator()
    try:
        import edge_tts
    except ImportError:
        c['log_error']("   Edge TTS not installed. Run: pip install edge-tts")
        return False

    edge_voice_map = {
        "Vindemiatrix": "en-US-JennyNeural", "Aoede": "en-US-AriaNeural",
        "Callirrhoe": "en-GB-SoniaNeural", "Gacrux": "en-US-GuyNeural",
        "Leda": "en-GB-LibbyNeural", "Kore": "en-US-CoraNeural",
        "Zephyr": "en-US-ChristopherNeural", "Puck": "en-US-EricNeural",
        "Fenrir": "en-US-DavisNeural", "Charon": "en-GB-RyanNeural",
        "Orus": "en-US-TonyNeural", "Umbriel": "en-US-JaneNeural",
        "Sulafat": "en-US-JennyNeural", "Alnilam": "en-US-ChristopherNeural",
        "Schedar": "en-GB-RyanNeural", "Algieba": "en-US-CoraNeural",
        "Rasalgethi": "en-US-DavisNeural", "Sadachbia": "en-GB-SoniaNeural",
        "Enceladus": "en-US-AriaNeural", "Autonoe": "en-US-JaneNeural",
        "Iapetus": "en-US-EricNeural",
    }

    edge_voice = edge_voice_map.get(voice, "en-US-JennyNeural")
    tts_text = f"{style} {text}" if style else text

    try:
        import asyncio
        async def _do_tts():
            communicate = edge_tts.Communicate(tts_text, edge_voice)
            await communicate.save(out_wav)
        asyncio.run(_do_tts())
        return os.path.exists(out_wav) and os.path.getsize(out_wav) > 0
    except Exception as e:
        c['log_error'](f"   Edge TTS failed: {e}")
        return False


def _tts_api_kokoro(text, out_wav, voice, style):
    c = _get_cogitator()
    try:
        from workflows.pipeline.phase_tts_kokoro import generate_tts_file
    except ImportError:
        c['log_error']("   Kokoro TTS module not found")
        return False
    
    # Apply emotion and speed settings
    emotion = _get_voice_emotion()
    speed = _get_voice_speed()
    
    # Build style with emotion
    emotion_tag = EMOTION_STYLES.get(emotion, '')
    full_style = f"{emotion_tag} {style}" if style else emotion_tag
    
    return generate_tts_file(text, out_wav, voice, full_style, speed=speed)


def _strip_title(script_text):
    lines = script_text.strip().split("\n")
    if lines and lines[0].startswith("TITLE:"):
        return "\n".join(lines[1:]).strip()
    return script_text.strip()


def _get_voice_id(voice_name):
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
    c = _get_cogitator()

    video_basename = os.path.splitext(os.path.basename(video))[0] if video else "tts"
    voice = c['env']("TTS_VOICE", "Vindemiatrix")
    if not voice:
        c['log_error']("Phase 6 Failed: TTS_VOICE not configured")
        c['notify']("Phase 6 Failed: TTS voice not set")
        c['set_status']("Phase 6 FAILED")
        raise RuntimeError("TTS_VOICE not configured")

    provider = c['env']("TTS_PROVIDER", "gemini").strip().lower()
    c['log'](f"   TTS provider: {provider}")

    if provider == "gemini":
        api_key = c['env']("GEMINI_API_KEY")
        if not api_key:
            c['log_error']("Phase 6 Failed: GEMINI_API_KEY not configured")
            c['notify']("Phase 6 Failed: No API key configured")
            c['set_status']("Phase 6 FAILED")
            raise RuntimeError("GEMINI_API_KEY not configured")
    elif provider not in ("kokoro", "edge"):
        c['log_error'](f"Phase 6 Failed: Unknown TTS_PROVIDER '{provider}'. Use 'gemini', 'kokoro', or 'edge'")
        c['notify']("Phase 6 Failed: Invalid TTS provider")
        c['set_status']("Phase 6 FAILED")
        raise RuntimeError(f"Unknown TTS_PROVIDER: {provider}")

    if c['_rr_get_state']()['voices'] == 0:
        c['_init_round_robin'](num_hours)

    c['set_status'](f"Phase 6: Generating TTS ({provider})...")
    c['log'](f"Phase 6: Generating TTS with provider '{provider}'...")
    c['notify'](f"Phase 6 Started: Generating TTS ({provider})...")
    delay = int(c['env']("TTS_DELAY", "120"))

    tts_generated = 0
    for i in range(1, num_hours + 1):
        pct = int(((i - 1) / num_hours) * 100)
        c['set_progress'](5, pct, f"Generating TTS ({i}/{num_hours})")

        padded = f"{i:03d}"
        wav = os.path.join(c['TTS_DIR'], f"{video_basename}-TTS{padded}.wav")
        srt = os.path.join(c['TTS_DIR'], f"{video_basename}-TTS{padded}.srt")
        script_file = os.path.join(c['SCRIPTS_DIR'], f"{video_basename}-Script{padded}.txt")

        if os.path.exists(wav) and os.path.getsize(wav) > 0:
            c['log'](f"   TTS {i} WAV exists, skipping")
            tts_generated += 1
        elif not os.path.exists(script_file):
            c['log'](f"   Warning: Script {i} not found, skipping TTS")
            continue
        else:
            try:
                with open(script_file) as f:
                    txt = f.read()
                if not txt.strip():
                    c['log_error'](f"   Warning: Script {i} is empty, skipping")
                    continue

                tts_text = _strip_title(txt)
                rr_voice, rr_style = c['get_next_voice_style']()
                c['log'](f"   Using voice: {rr_voice}, style: {rr_style[:40] if rr_style else 'none'}...")

                if provider == "gemini":
                    pcm = os.path.join(c['TTS_DIR'], f"tts_{padded}.pcm")
                    _tts_api_gemini(tts_text, pcm, rr_voice, rr_style)
                    if not os.path.exists(pcm):
                        c['log_error'](f"   Gemini TTS failed for script {i}")
                        continue
                    r = c['run'](["ffmpeg", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1",
                                  "-i", pcm, "-ar", "44100", "-ac", "2", wav], check=False)
                    if r.returncode != 0:
                        c['log_error'](f"   ffmpeg failed for script {i}: {r.stderr[-200:] if r.stderr else 'Unknown'}")
                        if os.path.exists(pcm):
                            os.remove(pcm)
                        continue
                    if os.path.exists(pcm):
                        os.remove(pcm)
                elif provider == "edge":
                    ok = _tts_api_edge(tts_text, wav, rr_voice, rr_style)
                    if not ok:
                        c['log_error'](f"   Edge TTS failed for script {i}")
                        continue
                elif provider == "kokoro":
                    ok = _tts_api_kokoro(tts_text, wav, rr_voice, rr_style)
                    if not ok:
                        c['log_error'](f"   Kokoro TTS failed for script {i}")
                        continue

                c['log'](f"   tts_{padded}.wav created")
                tts_generated += 1

                if c['PERFORMANCE_DB_AVAILABLE']:
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
                                existing_features['tts_provider'] = provider
                                cur.execute("UPDATE clips SET features = ? WHERE id = ?",
                                            (json.dumps(existing_features), row['id']))
                                conn.commit()
                                c['log'](f"   TTS learning: voice '{rr_voice}', provider '{provider}' recorded for clip")
                        finally:
                            conn.close()
                    except Exception:
                        pass
                c['set_status'](f"Phase 6: TTS {i}/{num_hours} generated")
                c['notify'](f"TTS {i}/{num_hours} generated")
            except Exception as e:
                c['log_error'](f"   Error generating TTS for script {i}: {e}")
                continue

        if not os.path.exists(srt):
            if not os.path.exists(wav):
                c['log'](f"   Warning: Cannot generate SRT, WAV not found for script {i}")
            else:
                c['log'](f"   Generating SRT + word timestamps for tts_{padded}.wav...")
                srt_out = os.path.splitext(wav)[0] + ".srt"
                words_json_out = os.path.splitext(wav)[0] + "_words.json"
                try:
                    from faster_whisper import WhisperModel
                    from workflows.pipeline.srt_utils import extract_words_from_segments, words_to_srt, save_words_json
                    whisper_device = get_whisper_device()
                    model = WhisperModel(c['env']("WHISPER_MODEL", "medium"), device=whisper_device, compute_type="int8")
                    segments, _ = model.transcribe(wav, language="en", vad_filter=True, word_timestamps=True)

                    all_words = extract_words_from_segments(segments)
                    save_words_json(all_words, words_json_out, transcription_text=tts_text)

                    srt_content = words_to_srt(all_words, max_words=int(c['env']("SRT_MAX_WORDS", "10")))
                    if srt_content:
                        with open(srt_out, "w") as f:
                            f.write(srt_content)

                    c['log'](f"   tts_{padded}.srt + _words.json created (faster-whisper word-level)")
                except Exception as e:
                    c['log_error'](f"   SRT failed for tts_{padded}: {e}")
        else:
            c['log'](f"   tts_{padded}.srt exists, skipping")

        if i < num_hours and provider == "gemini":
            c['log'](f"   Waiting {delay}s")
            time.sleep(delay)

    if tts_generated == 0:
        c['log_error']("Phase 6 Failed: No TTS files were generated")
        c['notify']("Phase 6 Failed: No TTS generated")
        c['set_status']("Phase 6 FAILED")
        raise RuntimeError("No TTS generated")

    c['set_status']("Phase 6 Complete")
    c['notify'](f"Phase 6 Complete: {tts_generated} TTS files generated")
