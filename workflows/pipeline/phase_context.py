import glob, json, os, re

from workflows.cogitator import (
    log, log_error, set_status, set_progress, env,
    TRANSCRIPTS_DIR, notify,
    _cs_extract_context_from_transcript, _cs_update_context,
    load_verified_context, merge_context_dicts,
    save_verified_context, compute_and_save_implicit_relationships,
    compare_context_with_history,
)


def phase_context():
    """Extract or update context from existing transcript - no transcription needed."""
    json_file = None

    if os.path.exists(TRANSCRIPTS_DIR):
        transcripts = sorted(glob.glob(os.path.join(TRANSCRIPTS_DIR, "*.json")),
                            key=os.path.getmtime, reverse=True)
        if transcripts:
            json_file = transcripts[0]

    if not json_file:
        log_error("Phase 3 Failed: No transcript found")
        notify("Phase 3 Failed: No transcript. Run Phase 2 first.")
        set_status("Phase 3 FAILED")
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
        log_error(f"Phase 3 Failed: Could not read transcript: {e}")
        notify(f"Phase 3 Failed: {e}")
        set_status("Phase 3 FAILED")
        return

    if not transcript_text:
        log_error("Phase 3 Failed: Empty transcript")
        notify("Phase 3 Failed: Transcript is empty")
        set_status("Phase 3 FAILED")
        return

    game_title = env("GAME_TITLE", "Unknown Game")
    set_status("Phase 3: Extracting context...")
    log("Phase 3: Extracting context from transcript...")
    notify("Phase 3: Extracting context...")

    try:
        extracted = _cs_extract_context_from_transcript(transcript_text[:10000], game_title)
    except Exception as e:
        log_error(f"Phase 3 Failed: Context extraction error: {e}")
        notify(f"Phase 3 Failed: API error - {e}")
        set_status("Phase 3 FAILED")
        return

    if not extracted:
        log_error("Phase 3 Failed: Context extraction failed")
        notify("Phase 3 Failed: Could not extract context (empty response)")
        set_status("Phase 3 FAILED")
        return

    transcript_name = os.path.basename(json_file)
    ctx = _cs_update_context(extracted, transcript_name)
    verified = load_verified_context(game_title)
    final = merge_context_dicts(verified.get("context", {}) if verified else {}, ctx)
    save_verified_context(game_title, final)
    compute_and_save_implicit_relationships(game_title, transcript_text)

    if not verified:
        log(f"First run for {game_title} - context auto-saved")
    else:
        comparison = compare_context_with_history(extracted, verified)
        if comparison.get("needs_confirmation"):
            log(f"Context changes detected for {game_title} - merged and saved")
        else:
            log(f"Context verified (merged with existing)")

    set_status("Phase 3 Complete")
    log(f"Context extracted: {len(final.get('characters', []))} chars, {len(final.get('locations', []))} locs, {len(final.get('relationships', []))} rels")
    notify(f"\u2705 Phase 3 Complete: Context extracted\n\U0001f4dd {len(final.get('characters', []))} chars\n\U0001f4cd {len(final.get('locations', []))} locs\n\U0001f465 {len(final.get('relationships', []))} rels")
    set_status("Phase 3 Complete")
