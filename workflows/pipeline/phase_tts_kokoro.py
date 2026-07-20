#!/usr/bin/env python3
"""
Cogitator Kokoro TTS Provider
Zero-cost TTS using the Kokoro library (MIT license, runs on CPU).
54 voices, fully offline after first model download.
"""

import json, os, subprocess, tempfile, time, uuid
from typing import Optional

KOKORO_AVAILABLE = False
try:
    from kokoro import KPipeline
    KOKORO_AVAILABLE = True
except ImportError:
    pass

KOKORO_VOICES = [
    "af_bella", "af_sarah", "af_nicole", "af_sky", "af_aoede",
    "am_adam", "am_michael", "am_fenrir", "am_puck", "am_liam",
    "bf_emma", "bf_isabella", "bm_george", "bm_lewis",
    "af_alisha", "af_heart", "af_alloy", "am_echo",
]

KOKORO_LANG_CODES = {
    "a": "a", "b": "b",
}
KOKORO_DEFAULT_VOICE = "af_bella"

def _normalize_voice_name(name: str) -> str:
    name = name.lower().strip()
    gemini_to_kokoro = {
        "vindemiatrix": "af_bella", "aoede": "af_aoede", "callirrhoe": "af_sarah",
        "gacrux": "af_nicole", "leda": "af_sky", "kore": "af_heart",
        "zephyr": "am_adam", "puck": "am_puck", "fenrir": "am_fenrir",
        "charon": "am_michael", "orus": "am_echo", "umbriel": "af_alloy",
        "sulafat": "af_bella", "alnilam": "am_adam", "algieba": "af_sky",
        "rasalgethi": "am_fenrir", "schedar": "am_michael",
        "sadachbia": "af_sarah", "enceladus": "af_nicole",
        "autonoe": "af_heart", "iapetus": "am_liam", "despina": "af_alisha",
        "laomedeia": "af_sky", "pulcherrima": "af_alloy",
        "achernar": "am_puck", "achird": "af_bella",
        "sadaltager": "am_adam", "zubenelgenubi": "af_aoede",
        "algenib": "am_echo", "erinome": "af_heart",
    }
    if name in gemini_to_kokoro:
        return gemini_to_kokoro[name]
    if name in KOKORO_VOICES:
        return name
    return KOKORO_DEFAULT_VOICE


_pipeline: Optional['KPipeline'] = None

def _get_pipeline(voice: str = KOKORO_DEFAULT_VOICE):
    global _pipeline
    if _pipeline is None:
        if not KOKORO_AVAILABLE:
            raise ImportError("kokoro package not installed. Run: pip install kokoro soundfile")
        lang = voice[0] if len(voice) > 0 else "a"
        if lang not in ("a", "b"):
            lang = "a"
        _pipeline = KPipeline(lang_code=lang)
    return _pipeline


def generate_tts(text: str, voice_name: str = KOKORO_DEFAULT_VOICE, style: str = None) -> Optional[bytes]:
    kokoro_voice = _normalize_voice_name(voice_name)
    pipeline = _get_pipeline(kokoro_voice)

    if style:
        styled = f"[{style}] {text}"
    else:
        styled = text

    try:
        generator = pipeline(styled, voice=kokoro_voice, speed=1.0)
        audio_chunks = []
        for i, (gs, ps, audio) in enumerate(generator):
            if audio is not None and len(audio) > 0:
                audio_chunks.append(audio.tobytes())

        if not audio_chunks:
            return None

        raw = b"".join(audio_chunks)
        return raw
    except Exception:
        return None


def generate_tts_file(text: str, output_wav: str, voice_name: str = KOKORO_DEFAULT_VOICE, style: str = None) -> bool:
    try:
        raw_pcm = generate_tts(text, voice_name, style)
        if raw_pcm is None:
            return False

        with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as f:
            tmp_raw = f.name
            f.write(raw_pcm)

        try:
            r = subprocess.run(
                ["ffmpeg", "-y", "-f", "f32le", "-ar", "24000", "-ac", "1",
                 "-i", tmp_raw, "-ar", "44100", "-ac", "2", output_wav],
                capture_output=True, timeout=30,
            )
            if r.returncode != 0:
                return False
            return os.path.exists(output_wav) and os.path.getsize(output_wav) > 0
        finally:
            if os.path.exists(tmp_raw):
                os.remove(tmp_raw)
    except Exception:
        return False


def phase_tts_kokoro(duration, num_hours, video=None):
    from workflows.cogitator import (
        log, log_error, set_status, set_progress, env, notify,
        SCRIPTS_DIR, TTS_DIR, run,
        PERFORMANCE_DB_AVAILABLE,
        _init_round_robin,
        _rr_get_state, get_next_voice_style,
    )

    video_basename = os.path.splitext(os.path.basename(video))[0] if video else "tts"
    voice = env("TTS_VOICE", KOKORO_DEFAULT_VOICE)
    if not voice:
        log_error("Phase 6 Failed: TTS_VOICE not configured")
        notify("Phase 6 Failed: TTS voice not set")
        set_status("Phase 6 FAILED")
        raise RuntimeError("TTS_VOICE not configured")

    if _rr_get_state()['voices'] == 0:
        _init_round_robin(num_hours)

    set_status("Phase 6: Generating TTS (Kokoro)...")
    log("Phase 6: Generating TTS with Kokoro (zero-cost, CPU)...")
    notify("Phase 6 Started: Generating TTS (Kokoro)...")

    kokoro_voice = _normalize_voice_name(voice)
    log(f"   Kokoro voice: {voice} -> {kokoro_voice}")

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

                rr_voice, rr_style = get_next_voice_style()
                log(f"   Using Kokoro voice: {rr_voice}, style: {rr_style[:40] if rr_style else 'none'}...")

                ok = generate_tts_file(txt, wav, rr_voice, rr_style)
                if not ok:
                    log_error(f"   Kokoro TTS failed for script {i}")
                    continue

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

    if tts_generated == 0:
        log_error("Phase 6 Failed: No TTS files were generated")
        notify("Phase 6 Failed: No TTS generated")
        set_status("Phase 6 FAILED")
        raise RuntimeError("No TTS generated")

    set_status("Phase 6 Complete")
    notify(f"Phase 6 Complete: {tts_generated} TTS files generated")
