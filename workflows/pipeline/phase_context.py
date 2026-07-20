import glob, json, os, re


def _get_cogitator():
    from workflows.cogitator import (
        log, log_error, set_status, set_progress, env,
        TRANSCRIPTS_DIR, notify,
        _cs_extract_context_from_transcript, _cs_update_context,
        load_verified_context, merge_context_dicts,
        save_verified_context, compute_and_save_implicit_relationships,
        compare_context_with_history,
    )
    return {
        'log': log, 'log_error': log_error,
        'set_status': set_status, 'set_progress': set_progress,
        'env': env, 'TRANSCRIPTS_DIR': TRANSCRIPTS_DIR, 'notify': notify,
        '_cs_extract_context_from_transcript': _cs_extract_context_from_transcript,
        '_cs_update_context': _cs_update_context,
        'load_verified_context': load_verified_context,
        'merge_context_dicts': merge_context_dicts,
        'save_verified_context': save_verified_context,
        'compute_and_save_implicit_relationships': compute_and_save_implicit_relationships,
        'compare_context_with_history': compare_context_with_history,
    }


def phase_context():
    """Extract or update context. Fetches game lore first, then analyses transcript."""
    c = _get_cogitator()

    try:
        from workflows.pipeline.phase_lore import phase_lore
        phase_lore()
    except Exception as e:
        c['log'](f"   Game lore fetch skipped: {e}")

    json_file = None

    if os.path.exists(c['TRANSCRIPTS_DIR']):
        transcripts = sorted(glob.glob(os.path.join(c['TRANSCRIPTS_DIR'], "*.json")),
                            key=os.path.getmtime, reverse=True)
        if transcripts:
            json_file = transcripts[0]

    if not json_file:
        c['log_error']("Phase 3 Failed: No transcript found")
        c['notify']("Phase 3 Failed: No transcript. Run Phase 2 first.")
        c['set_status']("Phase 3 FAILED")
        return

    try:
        with open(json_file) as f:
            data = json.load(f)
        transcript_text = ""
        for seg in data.get("segments", []):
            text = re.sub(r"<[^>]*>", "", seg.get("text", ""))
            if text.strip():
                transcript_text += text + " "
    except Exception as e:
        c['log_error'](f"Phase 3 Failed: Could not read transcript: {e}")
        c['notify'](f"Phase 3 Failed: {e}")
        c['set_status']("Phase 3 FAILED")
        return

    if not transcript_text:
        c['log_error']("Phase 3 Failed: Empty transcript")
        c['notify']("Phase 3 Failed: Transcript is empty")
        c['set_status']("Phase 3 FAILED")
        return

    game_title = c['env']("GAME_TITLE", "Unknown Game")
    c['set_status']("Phase 3: Extracting context from transcript...")
    c['log']("Phase 3: Extracting context from transcript...")
    c['notify']("Phase 3: Extracting context...")

    try:
        extracted = c['_cs_extract_context_from_transcript'](transcript_text[:10000], game_title)
    except Exception as e:
        c['log_error'](f"Phase 3 Failed: Context extraction error: {e}")
        c['notify'](f"Phase 3 Failed: API error - {e}")
        c['set_status']("Phase 3 FAILED")
        return

    if not extracted:
        c['log_error']("Phase 3 Failed: Context extraction failed")
        c['notify']("Phase 3 Failed: Could not extract context (empty response)")
        c['set_status']("Phase 3 FAILED")
        return

    transcript_name = os.path.basename(json_file)
    ctx = c['_cs_update_context'](extracted, transcript_name)
    verified = c['load_verified_context'](game_title)
    final = c['merge_context_dicts'](verified.get("context", {}) if verified else {}, ctx)
    c['save_verified_context'](game_title, final)
    c['compute_and_save_implicit_relationships'](game_title, transcript_text)

    if not verified:
        c['log'](f"First run for {game_title} - context auto-saved")
    else:
        comparison = c['compare_context_with_history'](extracted, verified)
        if comparison.get("needs_confirmation"):
            c['log'](f"Context changes detected for {game_title} - merged and saved")
        else:
            c['log'](f"Context verified (merged with existing)")

    c['set_status']("Phase 3 Complete")
    c['log'](f"Context extracted: {len(final.get('characters', []))} chars, {len(final.get('locations', []))} locs, {len(final.get('relationships', []))} rels")
    c['notify'](f"✅ Phase 3 Complete: Context extracted\n📝 {len(final.get('characters', []))} chars\n📌 {len(final.get('locations', []))} locs\n👥 {len(final.get('relationships', []))} rels")
    c['set_status']("Phase 3 Complete")
