import glob, json, os, re, tempfile
from functools import partial
from workflows.hardware_detect import get_ffmpeg_encoding_settings


TEMPLATES = {
    'mystery_recap': {
        'hook_duration': 12,
        'duck_volume': 0.15,
        'clip_pacing': 'normal',
        'sub_font_size': 24,
        'sub_margin_v': 70,
        'sub_primary_colour': '&H00FFD700&',
        'sub_border_style': 'glow',
        'sub_alignment': 'center',
    },
    'breakdown': {
        'hook_duration': 10,
        'duck_volume': 0.20,
        'clip_pacing': 'fast',
        'sub_font_size': 22,
        'sub_margin_v': 60,
        'sub_primary_colour': '&H00FFFFFF&',
        'sub_border_style': 'box',
        'sub_alignment': 'center',
    },
    'timeline': {
        'hook_duration': 10,
        'duck_volume': 0.18,
        'clip_pacing': 'normal',
        'sub_font_size': 23,
        'sub_margin_v': 65,
        'sub_primary_colour': '&H00FFFFFF&',
        'sub_border_style': 'outline',
        'sub_alignment': 'center',
    },
    'lesson': {
        'hook_duration': 8,
        'duck_volume': 0.10,
        'clip_pacing': 'kinetic',
        'sub_font_size': 26,
        'sub_margin_v': 80,
        'sub_primary_colour': '&H00FF69B4&',
        'sub_border_style': 'glow',
        'sub_alignment': 'center',
    },
    'narrative': {
        'hook_duration': 10,
        'duck_volume': 0.20,
        'clip_pacing': 'fast',
        'sub_font_size': 22,
        'sub_margin_v': 60,
        'sub_primary_colour': '&H00FFFFFF&',
        'sub_border_style': 'outline',
        'sub_alignment': 'center',
    },
    'news_report': {
        'hook_duration': 9,
        'duck_volume': 0.22,
        'clip_pacing': 'fast',
        'sub_font_size': 21,
        'sub_margin_v': 55,
        'sub_primary_colour': '&H00FFFFFF&',
        'sub_border_style': 'box',
        'sub_alignment': 'bottom-left',
    },
    'documentary': {
        'hook_duration': 12,
        'duck_volume': 0.15,
        'clip_pacing': 'normal',
        'sub_font_size': 24,
        'sub_margin_v': 70,
        'sub_primary_colour': '&H00FFD700&',
        'sub_border_style': 'glow',
        'sub_alignment': 'center',
    },
    'true_crime': {
        'hook_duration': 11,
        'duck_volume': 0.12,
        'clip_pacing': 'slow',
        'sub_font_size': 25,
        'sub_margin_v': 75,
        'sub_primary_colour': '&H00FF4444&',
        'sub_border_style': 'outline',
        'sub_alignment': 'center',
    },
    'character_pov': {
        'hook_duration': 8,
        'duck_volume': 0.10,
        'clip_pacing': 'kinetic',
        'sub_font_size': 26,
        'sub_margin_v': 80,
        'sub_primary_colour': '&H00FF69B4&',
        'sub_border_style': 'glow',
        'sub_alignment': 'center',
    },
}


TEMPLATE_LEGACY_MAP = {
    'story_recap': 'mystery_recap',
    'funny_moment': 'character_pov',
    'lore_deep_dive': 'documentary',
}


def _classify_script(script_path):
    if not script_path or not os.path.exists(script_path):
        return 'narrative'
    meta_path = script_path.replace('.txt', '.meta.json')
    if os.path.exists(meta_path):
        try:
            with open(meta_path) as f:
                meta = json.load(f)
            t = meta.get('variant', '') or meta.get('template', '')
            if t in TEMPLATES:
                return t
            if t in TEMPLATE_LEGACY_MAP:
                return TEMPLATE_LEGACY_MAP[t]
            if t:
                # meta.json has an unrecognized variant, default to narrative
                # rather than falling through to filename heuristics
                return 'narrative'
        except Exception:
            pass
    base = os.path.basename(script_path).lower()
    if 'funny' in base or 'humor' in base or 'comedy' in base:
        return 'character_pov'
    if 'lore' in base or 'deep' in base:
        return 'documentary'
    return 'narrative'


def _get_template(script_path):
    name = _classify_script(script_path)
    return name, TEMPLATES.get(name, TEMPLATES['narrative'])


def _build_sub_style(template):
    def _hex(c):
        c = c.lstrip('#')
        if len(c) == 3:
            c = ''.join(d*2 for d in c)
        c = c.ljust(6, 'F')
        return c

    from workflows.cogitator import env as _env

    font_name   = _env("SRT_FONT_NAME", "Open Sans")
    font_size   = int(_env("SRT_FONT_SIZE") or template['sub_font_size'])
    margin_v    = int(_env("SRT_MARGIN_V") or template['sub_margin_v'])
    font_color  = _hex(_env("SRT_FONT_COLOR") or
                         template['sub_primary_colour'].replace('&H00','').replace('&',''))
    font_color  = f"&H00{font_color}&"
    outline     = int(_env("SRT_FONT_OUTLINE") or "2")
    shadow      = int(_env("SRT_FONT_SHADOW") or "1")
    outline_col = _hex(_env("SRT_OUTLINE_COLOR") or "000000")
    outline_col = f"&H00{outline_col}&"
    border_style = _env("SRT_BORDER_STYLE") or template.get('sub_border_style', 'outline')
    alignment    = _env("SRT_ALIGNMENT") or template.get('sub_alignment', 'center')

    ass_border = {'outline': '1', 'box': '3', 'glow': '1'}.get(border_style, '1')
    ass_align  = {'center': '2', 'bottom-left': '1', 'bottom-right': '3', 'top-left': '7', 'top-right': '9', 'middle-left': '4', 'middle-right': '6'}.get(alignment, '2')
    return (
        f"FontName={font_name},FontSize={font_size},"
        f"PrimaryColour={font_color},OutlineColour={outline_col},"
        f"BorderStyle={ass_border},Outline={outline},Shadow={shadow},"
        f"BackColour=&H80000000&,MarginV={margin_v},Alignment={ass_align}"
    )


def _safe_shifted_path(padded):
    """Return a temp path with no special chars for the shifted SRT file."""
    return os.path.join(tempfile.gettempdir(), f"cog_srt_{padded}.srt")


def _get_cogitator():
    from workflows.cogitator import (
        log, log_error, set_status, set_progress, notify, env, run,
        MEDIA_DIR, TRANSCRIPTS_DIR, SCRIPTS_DIR, TTS_DIR, SHORTS_DIR, OUTPUT_DIR,
        PIPELINE_STOP_REQUESTED,
    )
    return {
        'log': log, 'log_error': log_error,
        'set_status': set_status, 'set_progress': set_progress, 'notify': notify, 'env': env, 'run': run,
        'MEDIA_DIR': MEDIA_DIR, 'TRANSCRIPTS_DIR': TRANSCRIPTS_DIR,
        'SCRIPTS_DIR': SCRIPTS_DIR, 'TTS_DIR': TTS_DIR,
        'SHORTS_DIR': SHORTS_DIR, 'OUTPUT_DIR': OUTPUT_DIR,
        'PIPELINE_STOP_REQUESTED': PIPELINE_STOP_REQUESTED,
    }


def _get_audio_duration(path):
    c = _get_cogitator()
    r = c['run'](["ffprobe", "-v", "error", "-show_entries", "format=duration",
                   "-of", "csv=p=0", path], check=False)
    if r.returncode == 0 and r.stdout.strip():
        try:
            return float(r.stdout.strip())
        except ValueError:
            pass
    return 0.0


_RE_TIME = re.compile(r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})')


def _fmt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _shift_srt(in_path, out_path, hook_offset=10):
    from functools import partial

    def _shift_timestamp(m, offset):
        h, mn, s, ms = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        total = h * 3600 + mn * 60 + s + ms / 1000 + offset
        return _fmt_time(total)

    with open(in_path) as f:
        content = f.read()
    shifted = _RE_TIME.sub(partial(_shift_timestamp, offset=hook_offset), content)
    with open(out_path, 'w') as f:
        f.write(shifted)


def _strip_script_metadata(text):
    lines = text.strip().split('\n')
    start = 0
    while start < len(lines):
        line = lines[start].strip()
        if not line or any(line.startswith(k) for k in ('TITLE:', 'DESCRIPTION:', 'TAGS:')):
            start += 1
        else:
            break
    return '\n'.join(lines[start:]).strip()


def _extract_title(script_path):
    try:
        with open(script_path) as f:
            for line in f:
                if line.startswith('TITLE:'):
                    return line[len('TITLE:'):].strip()
    except Exception:
        pass
    return None


def _sanitize_filename(name):
    safe = re.sub(r'[<>:"/\\|?*]', '_', name)
    safe = safe.strip(' .')
    if not safe or safe in ('.', '..'):
        return None
    return safe[:100]


def _script_to_srt(script_path, tts_duration, max_words=10, words_json_path=None):
    with open(script_path) as f:
        text = f.read().strip()
    text = _strip_script_metadata(text)

    words = text.split()
    if not words or tts_duration <= 0:
        return None

    from workflows.cogitator import env as _env
    hook_delay = float(_env("SRT_HOOK_DELAY") or "10.0")
    sub_gap    = float(_env("SRT_SUB_GAP") or "0.3")

    if words_json_path and os.path.exists(words_json_path):
        try:
            from workflows.pipeline.srt_utils import load_words_json
            word_timings = load_words_json(words_json_path)
            if word_timings:
                phrases = [words[i:i + max_words] for i in range(0, len(words), max_words)]

                from difflib import SequenceMatcher
                def _align_script_to_audio(script_words, audio_words):
                    aligned = []
                    aw_idx = 0
                    for sw in script_words:
                        best_match = None
                        best_score = 0.0
                        search_end = min(aw_idx + 5, len(audio_words))
                        for i in range(aw_idx, search_end):
                            score = SequenceMatcher(None, sw.lower(), audio_words[i]['word'].lower()).ratio()
                            if score > best_score:
                                best_score = score
                                best_match = i
                        if best_match is not None and best_score > 0.5:
                            aligned.append(audio_words[best_match])
                            aw_idx = best_match + 1
                        else:
                            aligned.append({"word": sw, "start": audio_words[aw_idx]['start'] if aw_idx < len(audio_words) else 0.0, "end": audio_words[aw_idx]['start'] if aw_idx < len(audio_words) else 0.5})
                            aw_idx = min(aw_idx + 1, len(audio_words))
                    return aligned

                entries = []
                wt_idx = 0
                for idx, phrase in enumerate(phrases):
                    phrase_len = len(phrase)
                    remaining = len(word_timings) - wt_idx
                    take = min(phrase_len, remaining)
                    phrase_words = word_timings[wt_idx:wt_idx + take]
                    if take != phrase_len:
                        phrase_words = _align_script_to_audio(phrase, word_timings[wt_idx:])
                    phrase_start = phrase_words[0]['start'] + hook_delay
                    phrase_end = phrase_words[-1]['end'] + hook_delay
                    entries.append(
                        f"{idx + 1}\n"
                        f"{_fmt_time(phrase_start)} --> {_fmt_time(phrase_end)}\n"
                        f"{' '.join(phrase)}\n"
                    )
                    wt_idx += take
                return '\n'.join(entries)
        except Exception as e:
            from workflows.cogitator import log
            log(f"   Word-timing SRT failed, falling back to proportional: {e}")

    chunks = [words[i:i + max_words] for i in range(0, len(words), max_words)]
    total_chars = sum(len(w) for chunk in chunks for w in chunk)
    time_per_char = tts_duration / total_chars if total_chars > 0 else 0

    min_duration  = float(_env("SRT_MIN_DURATION") or "1.0")
    max_duration  = float(_env("SRT_MAX_DURATION") or "6.0")

    entries = []
    current_time = 0.0
    for idx, chunk in enumerate(chunks):
        raw_dur = sum(len(w) for w in chunk) * time_per_char
        chunk_dur = max(min_duration, min(raw_dur, max_duration))
        start = current_time + (hook_delay if idx == 0 else sub_gap)
        end = start + chunk_dur
        current_time = end
        entries.append(
            f"{idx + 1}\n"
            f"{_fmt_time(start)} --> {_fmt_time(end)}\n"
            f"{' '.join(chunk)}\n"
        )
    return '\n'.join(entries)


def phase_assemble(duration, num_hours, video=None):
    c = _get_cogitator()

    video_basename = os.path.splitext(os.path.basename(video))[0] if video else "assembly"

    c['set_status']("Phase 7: Assembling Shorts...")
    c['log']("Phase 7: Assembling final Shorts...")
    c['notify']("Phase 7 Started: Assembling final Shorts...")

    assembly_dir = os.path.join(os.path.dirname(c['SHORTS_DIR']), "assembly", video_basename)
    os.makedirs(assembly_dir, exist_ok=True)

    ffmpeg_check = c['run'](["ffmpeg", "-version"], check=False)
    if ffmpeg_check.returncode != 0:
        c['log_error']("Phase 7 Failed: ffmpeg not available")
        return 0

    assembled = 0
    for i in range(1, num_hours + 1):
        pct = int(((i - 1) / max(num_hours, 1)) * 100)
        c['set_progress'](7, pct, f"Assembling shorts ({i}/{num_hours})")
        from workflows.cogitator import get_pipeline_stop_requested as _get_stop
        if _get_stop():
            c['log']("Phase 7 stopped by user")
            break

        padded = f"{i:03d}"
        tts_wav = os.path.join(c['TTS_DIR'], f"{video_basename}-TTS{padded}.wav")
        tts_srt = os.path.join(c['TTS_DIR'], f"{video_basename}-TTS{padded}.srt")

        script_path = os.path.join(c['SCRIPTS_DIR'], f"{video_basename}-Script{padded}.txt")
        _meta_p = script_path.replace('.txt', '.meta.json')
        if os.path.exists(_meta_p):
            try:
                import json as _json
                with open(_meta_p) as _mf:
                    _md = _json.load(_mf)
                if _md.get('quarantined') or _md.get('skip_tts'):
                    c['log'](f'   Skipping assemble {i}: quarantined script')
                    continue
            except Exception:
                pass

        title = _extract_title(script_path)
        out_name = _sanitize_filename(title) if title else None
        if not out_name:
            out_name = f"Short{padded}"
        output = os.path.join(assembly_dir, f"{out_name}.mp4")

        # Skip if output already exists from a previous run
        if os.path.exists(output) and os.path.getsize(output) > 0:
            c['log'](f"   {padded}: output already exists, skipping ({os.path.basename(output)})")
            assembled += 1
            continue

        tmpl_name, tmpl = _get_template(script_path)

        has_tts = os.path.exists(tts_wav) and os.path.exists(tts_srt)
        tts_dur = _get_audio_duration(tts_wav) if has_tts else 0
        hook_dur = tmpl['hook_duration']
        target = min(hook_dur + tts_dur, 180) if has_tts and tts_dur > 0 else 60.0

        c['log'](f"   Assembling {padded}: template={tmpl_name}, TTS={tts_dur:.1f}s, target={target:.1f}s → {os.path.basename(output)}")
        c['set_status'](f"Phase 7: Short {i}/{num_hours} — {os.path.basename(output)}")

        shifted_srt = _safe_shifted_path(padded) if has_tts else None
        if has_tts:
            words_json = os.path.join(c['TTS_DIR'], f"{video_basename}-TTS{padded}_words.json")
            # Use script-based SRT (respects SRT_MAX_WORDS), fall back to Whisper SRT
            if os.path.exists(script_path) and tts_dur > 0:
                try:
                    srt_max_words = int(os.environ.get("SRT_MAX_WORDS") or "10")
                    srt_content = _script_to_srt(script_path, tts_dur, max_words=srt_max_words, words_json_path=words_json)
                    if srt_content:
                        with open(shifted_srt, 'w') as f:
                            f.write(srt_content)
                    else:
                        shifted_srt = None
                except Exception as e:
                    c['log_error'](f"   Script SRT generation failed: {e}")
                    shifted_srt = None
            if not shifted_srt and os.path.exists(tts_srt):
                try:
                    shifted_srt = _safe_shifted_path(padded)
                    _shift_srt(tts_srt, shifted_srt, hook_offset=hook_dur)
                except Exception as e:
                    c['log'](f"   Whisper SRT shift failed: {e}")
                    shifted_srt = None

        hour_clips = sorted(
            glob.glob(os.path.join(c['SHORTS_DIR'], f"{video_basename}-Short{padded}_*.mp4")),
            key=lambda x: int(re.search(r'_(\d+)\.mp4$', os.path.basename(x)).group(1))
            if re.search(r'_(\d+)\.mp4$', os.path.basename(x)) else 0,
        )
        if not hour_clips:
            c['log_error'](f"   {padded}: no clips found for this interval, skipping")
            continue

        clips_dur = sum(_get_audio_duration(clip) for clip in hour_clips)
        if clips_dur <= 0:
            c['log_error'](f"   {padded}: could not determine clip durations, skipping")
            continue

        # Use all clips in quality order (clips are already sorted by score from _extract_scenes)
        concat_lines = []
        for clip in hour_clips:
            escaped = clip.replace("'", "'\\''")
            concat_lines.append(f"file '{escaped}'\n")
        c['log'](f"   Using {len(hour_clips)} clips ({clips_dur:.1f}s total)")

        concat_txt = os.path.join(assembly_dir, f"concat_{padded}.txt")
        with open(concat_txt, 'w') as f:
            f.writelines(concat_lines)

        fontsdir = "/run/host/fonts/TTF"
        if not os.path.isdir(fontsdir):
            fontsdir = "/usr/share/fonts"

        sub_style = _build_sub_style(tmpl)
        duck_vol = tmpl['duck_volume']
        hook_dur_ms = hook_dur * 1000

        bgm_path = os.path.join(os.path.dirname(c['SHORTS_DIR']), "bgm.mp3")
        has_bgm = os.path.exists(bgm_path)

        if has_tts and shifted_srt:
            # Smooth duck: volume envelope with 2s linear ramp from 1 → duck_vol
            # BGM: optional third input mixed at 0.05
            escaped_style = sub_style.replace("'", "\\'")
            f_parts = [
                f"[0:v]trim=duration={target},setpts=PTS-STARTPTS[vid_raw]",
                f"[vid_raw]subtitles={shifted_srt}:fontsdir={fontsdir}:force_style='{escaped_style}'[vid_sub]",
                f"[0:a]volume='if(lt(t,{hook_dur}),1,if(lt(t,{hook_dur+2}),1-(1-{duck_vol})*(t-{hook_dur})/2,if(lt(t,{hook_dur+tts_dur}),{duck_vol},if(lt(t,{hook_dur+tts_dur+2}),{duck_vol}+(1-{duck_vol})*(t-{hook_dur+tts_dur})/2,1))))':eval=frame[game_a]",
                f"[1:a]aformat=sample_fmts=s16:channel_layouts=stereo,adelay={hook_dur_ms}|{hook_dur_ms}[tts_a]",
            ]
            if has_bgm:
                f_parts.append(
                    f"[2:a]volume=0.05[bgm_a]"
                )
                amix_inputs = 3
                amix_weights = "'1 1 0.05'"
                inputs = ["-f", "concat", "-safe", "0", "-i", concat_txt, "-i", tts_wav, "-i", bgm_path]
            else:
                amix_inputs = 2
                amix_weights = "'1 1'"
                inputs = ["-f", "concat", "-safe", "0", "-i", concat_txt, "-i", tts_wav]

            f_parts.append(
                f"[game_a][tts_a]{'[bgm_a]' if has_bgm else ''}amix=inputs={amix_inputs}:duration=longest:weights={amix_weights}[out_a]"
            )

            # Get hardware-optimized encoding settings
            hw_settings = get_ffmpeg_encoding_settings()
            video_codec = hw_settings['video_codec']
            preset = hw_settings['preset']
            extra_args = hw_settings['extra_args']

            # For VA-API, insert hwupload after subtitle filter (into GPU memory before hardware encode)
            hw_upload = hw_settings.get('hw_upload_filter')
            if hw_upload:
                f_parts.insert(2, f"[vid_sub]{hw_upload}[vid]")

            # Ensure [vid] label exists for non-VA-API paths (NVENC, QSV, CPU)
            if not hw_upload:
                f_parts.append(f"[vid_sub]null[vid]")

            filter_complex = ";".join(f_parts)

            # Determine video quality flag based on codec
            # libx264 uses -crf, NVENC uses -cq (already in extra_args), VA-API uses -qp (in extra_args)
            if video_codec == 'libx264':
                vq_args = ["-crf", "23"]
            elif video_codec == 'h264_nvenc':
                vq_args = []  # -cq 23 is already in extra_args
            elif video_codec == 'h264_vaapi':
                vq_args = ["-qp", "23"]
            else:
                vq_args = ["-crf", "23"]

            cmd = [
                "ffmpeg", "-y",
                *inputs,
                "-filter_complex", filter_complex,
                "-map", "[vid]", "-map", "[out_a]",
                "-c:v", video_codec, "-preset", preset,
                *vq_args,
                *extra_args,
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                "-t", str(target),
                output,
            ]
        else:
            f_parts = [
                f"[0:v]trim=duration={target},setpts=PTS-STARTPTS[vid_raw]",
            ]
            if has_bgm:
                f_parts.append(
                    f"[0:a]volume=1[game_a];"
                    f"[1:a]volume=0.05[bgm_a];"
                    f"[game_a][bgm_a]amix=inputs=2:duration=longest:weights='1 0.05'[out_a]"
                )
                inputs = ["-f", "concat", "-safe", "0", "-i", concat_txt, "-i", bgm_path]
            else:
                f_parts.append(
                    f"[0:a]aformat=sample_fmts=s16:channel_layouts=stereo,volume=1[out_a]"
                )
                inputs = ["-f", "concat", "-safe", "0", "-i", concat_txt]

            # Get hardware-optimized encoding settings
            hw_settings = get_ffmpeg_encoding_settings()
            video_codec = hw_settings['video_codec']
            preset = hw_settings['preset']
            extra_args = hw_settings['extra_args']

            # For VA-API, insert hwupload into the filtergraph
            hw_upload = hw_settings.get('hw_upload_filter')
            if hw_upload:
                f_parts.insert(1, f"[vid_raw]{hw_upload}[vid]")

            # Ensure [vid] label exists for non-VA-API paths
            if not hw_upload:
                f_parts.append(f"[vid_raw]null[vid]")

            filter_complex = ";".join(f_parts)

            # Determine video quality flag based on codec
            if video_codec == 'libx264':
                vq_args = ["-crf", "23"]
            elif video_codec == 'h264_nvenc':
                vq_args = []  # -cq 23 is already in extra_args
            elif video_codec == 'h264_vaapi':
                vq_args = ["-qp", "23"]
            else:
                vq_args = ["-crf", "23"]

            cmd = [
                "ffmpeg", "-y",
                *inputs,
                "-filter_complex", filter_complex,
                "-map", "[vid]", "-map", "[out_a]",
                "-c:v", video_codec, "-preset", preset,
                *vq_args,
                *extra_args,
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                "-t", str(target),
                output,
            ]

        c['log'](f"   Running ffmpeg for {padded}...")
        r = c['run'](cmd, check=False)

        if r.returncode == 0 and os.path.exists(output) and os.path.getsize(output) > 0:
            size_mb = os.path.getsize(output) / (1024 * 1024)
            c['log'](f"   Created {os.path.basename(output)} ({size_mb:.1f}MB)")
            assembled += 1
        else:
            err = r.stderr[-500:] if r.stderr else "unknown error"
            c['log_error'](f"   Failed {padded}: {err}")

        for f in (concat_txt, shifted_srt):
            if f and os.path.exists(f):
                os.unlink(f)

    c['log'](f"Phase 7: {assembled}/{num_hours} Shorts assembled → {assembly_dir}")
    c['set_status'](f"Phase 7 Complete: {assembled} Shorts")

    if assembled:
        c['notify'](f"Phase 7 Complete: {assembled} Shorts assembled")

    return assembled
