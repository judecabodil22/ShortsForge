#!/usr/bin/env python3
"""
Cogitator — Telegram Bot Module
Extracted Telegram functions from the main cogitator.py monolith.
"""
import argparse, base64, datetime, glob, json, os, random, re, shutil, subprocess, sys, threading, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime

_telegram_dir = os.path.dirname(os.path.abspath(__file__))
_workflow_dir = os.path.dirname(_telegram_dir)
_workspace = os.path.dirname(_workflow_dir)
for _p in (_workflow_dir, _workspace):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from update_manager import (
    get_local_version,
    get_release_notes,
    check_for_updates,
    perform_update,
    cleanup_old_backups,
)
from workflows.constants import TTS_VOICES, TTS_STYLE_OPTIONS, calculate_performance_score, parse_duration, get_next_groq_key, dedupe_entity_list, fuzzy_dedup_against_list
from workflows.core.round_robin import init_round_robin, get_next_variant_perspective, get_next_voice_style, reset as reset_round_robin, get_state as _rr_get_state
from performance_database import (
    store_script,
    backfill_script_titles,
)
from keychain_manager import (
    get_gemini_keys,
    get_groq_keys,
    get_service_password,
    set_gemini_keys,
    set_service_password,
)
try:
    from game_data.mempalace import get_mempalace_manager
    MEMPALACE_AVAILABLE = True
except ImportError as e:
    MEMPALACE_AVAILABLE = False
    print(f"[DEBUG] MemPalace import failed: {e}")
    def get_mempalace_manager():
        """Fallback when MemPalace is not available."""
        return None
from script_validation import (
    validate_script_factuality,
    score_engagement,
    select_best_script,
    score_context_relevance,
    summarize_context,
    log_generation_metrics,
    store_generation_failure,
    get_learned_constraints,
    get_learning_summary,
    calculate_optimal_temperature,
)

try:
    from performance_database import (
        store_script,
        store_clip,
        link_video,
        store_metrics,
        get_channel_baseline,
        get_successful_scripts,
        get_learnings,
        store_learning,
        get_learned_variant_weights,
        get_variant_performance_stats,
        get_weighted_tts_voices,
        update_tts_learning,
        backfill_script_titles,
    )
    PERFORMANCE_DB_AVAILABLE = True
except ImportError:
    PERFORMANCE_DB_AVAILABLE = False
    def store_script(*args, **kwargs): return None
    def store_clip(*args, **kwargs): return None
    def link_video(*args, **kwargs): return None
    def store_metrics(*args, **kwargs): return None
    def get_channel_baseline(): return {}
    def get_successful_scripts(*args, **kwargs): return []
    def get_learnings(*args, **kwargs): return []
    def store_learning(*args, **kwargs): pass
    def get_learned_variant_weights(*args, **kwargs): return {}
    def get_variant_performance_stats(): return {}
    def get_weighted_tts_voices(): return []
    def update_tts_learning(*args, **kwargs): pass
    def backfill_script_titles(*args, **kwargs): return {}

try:
    from learning_engine import (
        extract_script_features,
        calculate_virality_score,
        analyze_performance_patterns,
        get_optimized_params
    )
    LEARNING_ENGINE_AVAILABLE = True
except ImportError:
    LEARNING_ENGINE_AVAILABLE = False
    def extract_script_features(*args, **kwargs): return {}
    def calculate_virality_score(*args, **kwargs): return 50.0
    def analyze_performance_patterns(*args, **kwargs): return {}
    def get_optimized_params(*args, **kwargs): return {}

try:
    from audio_analysis import enhance_scene_selection
    AUDIO_ANALYSIS_AVAILABLE = True
except ImportError:
    AUDIO_ANALYSIS_AVAILABLE = False
    def enhance_scene_selection(*args, **kwargs): return args[0] if args else []

from context_manager_v2 import (
    load_verified_context,
    save_verified_context,
    save_implicit_relationships,
    compute_and_save_implicit_relationships,
    is_first_run,
    compare_context_with_history,
    format_context_for_confirmation,
    get_verified_context_for_validation,
    clear_verified_context,
)
from context_manager import merge_context_dicts

_ctx_edit_lock = threading.Lock()
_env_lock = threading.Lock()
import requests
from jinja2 import Environment, FileSystemLoader, BaseLoader
try:
    from rapidfuzz import fuzz as _fuzz
except ImportError:
    _fuzz = None

from workflows.cogitator import (
    log, log_error, set_status, set_progress, env, WORKSPACE, WORKFLOW_DIR, MEDIA_DIR, DEFAULT_WORKSPACE,
    TRANSCRIPTS_DIR, SCRIPTS_DIR, TTS_DIR, SHORTS_DIR, OUTPUT_DIR, PROMPTS_DIR,
    CONTEXT_DIR, CONTENT_STUDIO_DIR, CS_TRANSCRIPTS_DIR, CS_SHORTS_DIR, CS_SCRIPTS_DIR, CS_TTS_DIR,
    CONTEXT_EDIT_STATE, PIPELINE_RUNNING, LISTENER_RUNNING, LISTENER_RESTART,
    STREAMING, PIPELINE_STOP_REQUESTED, PID_FILE, OFFSET_FILE,
    PENDING_CONTEXT, _SCRIPT_ID_MAP, _LEARNING_BASELINE, _LEARNING_VARIANT_WEIGHTS,
    _LEARNING_VARIANT_STATS, _LEARNING_TTS_WEIGHTS, _LEARNING_OPTIMIZED_PARAMS,
    _refresh_learning_state, _clear_shared_state, _cs_load_context, _cs_save_context,
    _cs_extract_context_from_transcript, _cs_update_context, _cs_clear_context,
    _cs_generate_script, _cs_generate_tts, _cs_generate_srt, _get_voice_id,
    _wrap_text_for_srt, _format_srt_time, _cs_find_newest_transcript, _cs_read_transcript,
    _cs_analyze_transcript, _save_segment_references,
    _groq_generate, _gemini_script, _get_groq_model, _rate_limit,
    find_video, video_info, download_from_url, run, retry, count_files, fmt_dur,
    delete_partial_files, cleanup_all_files, get_gemini_keys, get_groq_keys,
    notify, tg_send, tg_send_menu, tg_answer_callback,
    run_pipeline, run_local_recordings, update_env_var, _do_update_menu,
    _check_configured, _telegram_configured,
    MEMPALACE_AVAILABLE, get_mempalace_manager,
    ENV, load_env, LOG_FILE, METRICS_FILE, STATUS_FILE, LAST_CALL,
    GROQ_KEY_INDEX, GROQ_MODEL, GROQ_MODELS_BY_TYPE, TEMPERATURE_BY_TYPE,
    SCRIPT_VARIANTS, SCRIPT_PERSPECTIVES,
    phase_download, phase_transcribe, phase_context, phase_scripts, phase_clips, phase_tts,
    AUDIO_ANALYSIS_AVAILABLE,
)

# ─── Telegram ─────────────────────────────────────────────────────────────────

def tg_send(msg, parse_mode=None):
    token = env("TELEGRAM_BOT_TOKEN")
    chat  = env("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return
    try:
        params = {"chat_id": chat, "text": msg}
        if parse_mode:
            params["parse_mode"] = parse_mode
        data = urllib.parse.urlencode(params).encode()
        req  = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                      data=data, method="POST")
        urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as e:
        print(f"Telegram send error: {e}")

def tg_send_menu(msg, reply_markup=None):
    token = env("TELEGRAM_BOT_TOKEN")
    chat  = env("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return
    try:
        params = {"chat_id": chat, "text": msg}
        if reply_markup:
            params["reply_markup"] = json.dumps(reply_markup)
        data = urllib.parse.urlencode(params).encode()
        req  = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                      data=data, method="POST")
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Menu send error: {e}")

def tg_answer_callback(callback_id, text=None):
    token = env("TELEGRAM_BOT_TOKEN")
    if not token:
        return
    try:
        params = {"callback_query_id": callback_id}
        if text:
            params["text"] = text
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                                    data=data, method="POST")
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Callback answer error: {e}")
        if isinstance(e, urllib.error.HTTPError):
            try:
                body = e.read().decode()
            except:
                body = "No response body"
            log_error(f"Telegram callback: {e.code} {e.reason} - {body[:200]}")

def notify(msg):
    if STREAMING:
        tg_send(msg)


# ─── Context Confirmation Functions ────────────────────────────────────────────

def send_context_confirmation(game_title, extracted, verified, comparison):
    """Send context confirmation request via Telegram or CLI."""
    log(f"Context auto-approved for {game_title} (sync to MemPalace enabled)")
    return "auto_approved"


def cli_context_confirmation(game_title, formatted):
    """CLI fallback for context confirmation."""
    print(f"\n{'='*60}")
    print(f"🤖 Context Confirmation - {game_title}")
    print(f"{'='*60}")
    print(f"\n{formatted}")
    print(f"\n{'='*60}")
    print("⚠️ Please review and approve to continue.")
    print("Options: (a) Approve | (c) Cancel | (v) View full context")
    print("="*60)

    while True:
        choice = input("Your choice (a/c/v): ").strip().lower()

        if choice == "a":
            return "approved"
        elif choice == "c":
            return "cancelled"
        elif choice == "v":
            print("\n--- Full Context ---")
            print(formatted)
            print("--- End ---\n")
        else:
            print("Invalid choice. Please enter a, c, or v")


def handle_context_callback(callback_data, game_title, cb_id):
    """Handle context confirmation callback."""
    from context_manager import save_verified_context, load_verified_context, compare_context_with_history
    global CONTEXT_EDIT_STATE

    log(f"[DEBUG] handle_context_callback: checking CONTEXT_EDIT_STATE")
    log(f"[DEBUG] handle_context_callback: {callback_data}")
    log(f"[DEBUG] handle_context_callback: CONTEXT_EDIT_STATE = {CONTEXT_EDIT_STATE}")

    log(f"[DEBUG] ctx_edit flow - CONTEXT_EDIT_STATE: {CONTEXT_EDIT_STATE}")
    # Edit context - start editing session with inline submenu

    if callback_data.startswith("ctx_approve_"):
        # Approve and save verified context
        from context_manager import save_verified_context
        from context_manager import compare_context_with_history

        # Get extracted context from current run
        extracted = _cs_load_context()
        verified = load_verified_context(game_title)
        comparison = compare_context_with_history(extracted, verified)

        # Get resolved context (from comparison or extracted)
        resolved = comparison.get("resolved_context", extracted)

        # Save to verified_context.json
        save_verified_context(game_title, resolved)

        log(f"Context saved for {game_title}: {len(resolved.get('characters', []))} chars, {len(resolved.get('locations', []))} locs")

        return "✅ Context verified and saved! Proceeding to script generation...", "proceed_to_scripts"

    elif callback_data.startswith("ctx_edit_"):
        # Edit context - start editing session with inline submenu

        game = callback_data.replace("ctx_edit_", "").replace("_", " ")
        game_title = game if game else env("GAME_TITLE", "Unknown")

        pending = get_pending_context(game_title)
        if pending:
            extracted = pending.get("extracted", {})
        else:
            extracted = _cs_load_context()

        # Store editing state (clear+update to keep shared dict reference)
        with _ctx_edit_lock:
            CONTEXT_EDIT_STATE.clear()
            CONTEXT_EDIT_STATE.update({
                "game_title": game_title,
                "step": "choose_field",
                "extracted": extracted
            })

        chars = extracted.get("characters", [])
        locs = extracted.get("locations", [])
        rels = extracted.get("relationships", [])

        # Build submenu inline keyboard
        keyboard = {
            "inline_keyboard": [
                [{"text": f"📝 Characters ({len(chars)})", "callback_data": "ctx_edit_characters"},
                 {"text": f"📍 Locations ({len(locs)})", "callback_data": "ctx_edit_locations"}],
                [{"text": f"👥 Relationships ({len(rels)})", "callback_data": "ctx_edit_relationships"},
                 {"text": "✅ Done", "callback_data": "ctx_edit_done"}],
                [{"text": "❌ Cancel", "callback_data": "ctx_cancel"}]
            ]
        }

        return None, keyboard

    elif callback_data == "ctx_edit_characters":
        # Edit characters submenu
        state = CONTEXT_EDIT_STATE
        log(f"[DEBUG] ctx_edit_characters - CONTEXT_EDIT_STATE: {state}")
        if not state:
            log("[DEBUG] CONTEXT_EDIT_STATE is empty")
            return "⚠️ No editing session active. Start a new context confirmation first."

        if "extracted" not in state:
            log(f"[DEBUG] 'extracted' not in state, keys: {state.keys()}")
            return "⚠️ No context data. Start a new context confirmation first."

        extracted = state.get("extracted", {})
        chars = extracted.get("characters", [])

        if not chars:
            return "⚠️ No characters in context to edit."

        keyboard = {"inline_keyboard": []}
        for i, char in enumerate(chars[:10]):
            keyboard["inline_keyboard"].append([{"text": f"❌ {char}", "callback_data": f"ctx_rem_char_{i}"}])

        keyboard["inline_keyboard"].append([{"text": "+ Add Character", "callback_data": "ctx_add_char"}])
        keyboard["inline_keyboard"].append([{"text": "⬅️ Back", "callback_data": "ctx_edit_back"}])

        return f"📝 Characters ({len(chars)}):\n\nSelect to remove, or add new:", keyboard

    elif callback_data == "ctx_edit_locations":
        # Edit locations submenu
        state = CONTEXT_EDIT_STATE
        log(f"[DEBUG] ctx_edit_locations called, state: {bool(state)}")
        if not state or "extracted" not in state:
            return "⚠️ No editing session active. Click Edit first to start."

        extracted = state.get("extracted", {})
        locs = extracted.get("locations", [])

        if not locs:
            return "⚠️ No locations in context to edit."

        keyboard = {"inline_keyboard": []}
        for i, loc in enumerate(locs[:10]):
            keyboard["inline_keyboard"].append([{"text": f"❌ {loc}", "callback_data": f"ctx_rem_loc_{i}"}])

        keyboard["inline_keyboard"].append([{"text": "+ Add Location", "callback_data": "ctx_add_loc"}])
        keyboard["inline_keyboard"].append([{"text": "⬅️ Back", "callback_data": "ctx_edit_back"}])

        return f"📍 Locations ({len(locs)}):\n\nSelect to remove, or add new:", keyboard

    elif callback_data == "ctx_edit_relationships":
        # Edit relationships submenu
        state = CONTEXT_EDIT_STATE
        log(f"[DEBUG] ctx_edit_relationships called, state: {bool(state)}")
        if not state or "extracted" not in state:
            return "⚠️ No editing session active. Click Edit first to start."

        extracted = state.get("extracted", {})
        rels = extracted.get("relationships", [])

        if not rels:
            return "⚠️ No relationships in context to edit."

        keyboard = {"inline_keyboard": []}
        for i, rel in enumerate(rels[:10]):
            if isinstance(rel, dict):
                label = f"{rel.get('from', '')} \u2194 {rel.get('to', '')}: {rel.get('relationship', '')}"
            else:
                label = str(rel)
            keyboard["inline_keyboard"].append([{"text": f"❌ {label[:30]}", "callback_data": f"ctx_rem_rel_{i}"}])

        keyboard["inline_keyboard"].append([{"text": "+ Add Relationship", "callback_data": "ctx_add_rel"}])
        keyboard["inline_keyboard"].append([{"text": "⬅️ Back", "callback_data": "ctx_edit_back"}])

        return f"👥 Relationships ({len(rels)}):\n\nSelect to remove:", keyboard

    elif callback_data == "ctx_edit_done":
        # Save and proceed
        state = CONTEXT_EDIT_STATE
        if not state:
            return "⚠️ No editing session active."

        game_title = state.get("game_title", env("GAME_TITLE", ""))
        extracted = state.get("extracted", {})

        if not extracted:
            return "⚠️ No context to save."

        save_verified_context(game_title, extracted)
        with _ctx_edit_lock:
            CONTEXT_EDIT_STATE.clear()

        return "✅ Context saved!", None

    elif callback_data == "ctx_edit_back":
        # Go back to edit menu
        with _ctx_edit_lock:
            state = dict(CONTEXT_EDIT_STATE)
        if not state:
            return "⚠️ No editing session active. Start a new context confirmation first."

        game_title = state.get("game_title", env("GAME_TITLE", ""))
        extracted = state.get("extracted", {})

        chars = extracted.get("characters", [])
        locs = extracted.get("locations", [])
        rels = extracted.get("relationships", [])

        keyboard = {
            "inline_keyboard": [
                [{"text": f"📝 Characters ({len(chars)})", "callback_data": "ctx_edit_characters"},
                 {"text": f"📍 Locations ({len(locs)})", "callback_data": "ctx_edit_locations"}],
                [{"text": f"👥 Relationships ({len(rels)})", "callback_data": "ctx_edit_relationships"},
                 {"text": "✅ Done", "callback_data": "ctx_edit_done"}],
                [{"text": "❌ Cancel", "callback_data": "ctx_cancel"}]
            ]
        }

        return "📝 Edit Context - Main Menu:", keyboard

    elif callback_data.startswith("ctx_rem_char_"):
        idx = int(callback_data.replace("ctx_rem_char_", ""))
        state = CONTEXT_EDIT_STATE
        if not state or "extracted" not in state:
            return "⚠️ No editing session active."

        chars = state.get("extracted", {}).get("characters", [])
        removed = None
        if 0 <= idx < len(chars):
            removed = chars.pop(idx)
            tg_answer_callback(cb_id, f"Removed {removed}")

        # Rebuild keyboard with updated list
        chars = state.get("extracted", {}).get("characters", [])
        keyboard = {"inline_keyboard": []}
        for i, char in enumerate(chars[:10]):
            keyboard["inline_keyboard"].append([{"text": f"❌ {char}", "callback_data": f"ctx_rem_char_{i}"}])
        keyboard["inline_keyboard"].append([{"text": "+ Add Character", "callback_data": "ctx_add_char"}])
        keyboard["inline_keyboard"].append([{"text": "⬅️ Back", "callback_data": "ctx_edit_back"}])

        msg = f"📝 Character removed.\n\nSelect to remove, or add new:" if not removed else f"📝 Character '{removed}' removed.\n\nSelect to remove, or add new:"
        return msg, keyboard

    elif callback_data == "ctx_cancel":
        return "❌ Context confirmation cancelled. Pipeline will stop.", "stop_pipeline"

    # Context menu handlers
    elif callback_data == "ctx_view":
        return _show_context_view()

    # Not a known context callback
    return None, None


# PENDING_CONTEXT is imported from cogitator — shared dict, do not rebind

def handle_context_edit_input(txt, chat_id):
    """Handle context editing flow via Telegram."""
    global CONTEXT_EDIT_STATE

    step = CONTEXT_EDIT_STATE.get("step", "")
    state = CONTEXT_EDIT_STATE

    if step == "choose_field":
        if txt == "1":
            # Edit characters
            chars = state.get("extracted", {}).get("characters", [])
            state["step"] = "edit_characters"
            state["current_items"] = chars
            CONTEXT_EDIT_STATE.update(state)

            items = "\n".join([f"{i+1}. {c}" for i, c in enumerate(chars)])
            tg_send(f"📝 Current Characters:\n{items}\n\nEnter the number to remove, or type a name to add:")
            return True

        elif txt == "2":
            # Edit locations
            locs = state.get("extracted", {}).get("locations", [])
            state["step"] = "edit_locations"
            state["current_items"] = locs
            CONTEXT_EDIT_STATE.update(state)

            items = "\n".join([f"{i+1}. {l}" for i, l in enumerate(locs)])
            tg_send(f"📍 Current Locations:\n{items}\n\nEnter the number to remove, or type a name to add:")
            return True

        elif txt == "3":
            # Edit relationships
            rels = state.get("extracted", {}).get("relationships", [])
            state["step"] = "edit_relationships"
            state["current_items"] = rels
            CONTEXT_EDIT_STATE.update(state)

            items = "\n".join([f"{i+1}. {r}" for i, r in enumerate(rels[:10])])
            tg_send(f"👥 Current Relationships:\n{items}\n\nEnter the number to remove, or type in format 'Name1 -> Name2: relationship' to add:")
            return True
        else:
            tg_send("Invalid choice. Reply with 1, 2, or 3")
            return True

    elif step == "edit_characters":
        # Check if number (remove) or name (add)
        if txt.isdigit():
            idx = int(txt) - 1
            items = state.get("current_items", [])
            if 0 <= idx < len(items):
                removed = items.pop(idx)
                state["current_items"] = items
                tg_send(f"✅ Removed: {removed}")
            else:
                tg_send("Invalid number")
        else:
            # Add new character
            items = state.get("current_items", [])
            items.append(txt)
            state["current_items"] = items
            tg_send(f"✅ Added: {txt}")

        state["extracted"]["characters"] = items
        CONTEXT_EDIT_STATE.update(state)
        tg_send("Done editing? Reply 'done' to save, or continue editing.")
        return True

    elif step == "edit_locations":
        if txt.isdigit():
            idx = int(txt) - 1
            items = state.get("current_items", [])
            if 0 <= idx < len(items):
                removed = items.pop(idx)
                state["current_items"] = items
                tg_send(f"✅ Removed: {removed}")
            else:
                tg_send("Invalid number")
        else:
            items = state.get("current_items", [])
            items.append(txt)
            state["current_items"] = items
            tg_send(f"✅ Added: {txt}")

        state["extracted"]["locations"] = items
        CONTEXT_EDIT_STATE.update(state)
        tg_send("Done editing? Reply 'done' to save, or continue editing.")
        return True

    elif step == "edit_relationships":
        if txt.isdigit():
            idx = int(txt) - 1
            items = state.get("current_items", [])
            if 0 <= idx < len(items):
                removed = items.pop(idx)
                state["current_items"] = items
                tg_send(f"✅ Removed: {removed}")
            else:
                tg_send("Invalid number")
        elif "->" in txt and ":" in txt:
            # Add new relationship: "Name1 -> Name2: relationship"
            try:
                parts = txt.split("->")
                char1 = parts[0].strip()
                rest = parts[1].split(":")
                char2 = rest[0].strip()
                rel = rest[1].strip() if len(rest) > 1 else "unknown"
                items = state.get("current_items", [])
                items.append({"from": char1, "to": char2, "relationship": rel})
                state["current_items"] = items
                tg_send(f"✅ Added: {char1} -> {char2}: {rel}")
            except:
                tg_send("Invalid format. Use: Name1 -> Name2: relationship")
        else:
            tg_send("Invalid. Enter number to remove, or 'Name1 -> Name2: relationship' to add")

        items = state.get("current_items", [])
        state["extracted"]["relationships"] = items
        CONTEXT_EDIT_STATE.update(state)
        tg_send("Done editing? Reply 'done' to save, or continue editing.")
        return True

    elif txt.lower() == "done":
        # Save the edited context
        game_title = state.get("game_title", env("GAME_TITLE", ""))
        extracted = state.get("extracted", {})

        # Save as verified
        save_verified_context(game_title, extracted)

        with _ctx_edit_lock:
            CONTEXT_EDIT_STATE.clear()
        tg_send(f"✅ Context saved for {game_title}!\n\nRun Phase 2 to verify, then Phase 4 for scripts.")
        return True

    elif txt.lower() == "cancel":
        with _ctx_edit_lock:
            CONTEXT_EDIT_STATE.clear()
        tg_send("❌ Edit cancelled.")
        return True

    return False


def _cs_update_context_for_edit(extracted):
    """Update Obsidian markdown files with edited context."""
    obsidian_dir = os.path.join(CONTENT_STUDIO_DIR, "context")
    os.makedirs(obsidian_dir, exist_ok=True)

    # Update characters.md
    chars_file = os.path.join(obsidian_dir, "characters.md")
    with open(chars_file, "w") as f:
        f.write("# Characters\n\n")
        for char in extracted.get("characters", []):
            f.write(f"- [[{char}]]\n")

    # Update locations.md
    locs_file = os.path.join(obsidian_dir, "locations.md")
    with open(locs_file, "w") as f:
        f.write("# Locations\n\n")
        for loc in extracted.get("locations", []):
            f.write(f"- [[{loc}]]\n")

    # Update relationships.md
    rels_file = os.path.join(obsidian_dir, "relationships.md")
    with open(rels_file, "w") as f:
        f.write("# Relationships\n\n")
        f.write("| Character | Connected To | Relationship |\n")
        f.write("| ----------- | --------------- | ------------------------------- |\n")
        for rel in extracted.get("relationships", []):
            if isinstance(rel, dict):
                f.write(f"| [[{rel.get('from', '')}]] | [[{rel.get('to', '')}]] | {rel.get('relationship', '')} |\n")
            elif isinstance(rel, str):
                f.write(f"| {rel} |\n")

    log(f"Context files updated from Telegram edit")


def set_pending_context(game_title, extracted, verified, comparison):
    """Store context pending confirmation."""
    global PENDING_CONTEXT
    PENDING_CONTEXT[game_title] = {
        "extracted": extracted,
        "verified": verified,
        "comparison": comparison,
        "timestamp": datetime.now().isoformat()
    }


def get_pending_context(game_title):
    """Get pending context for a game."""
    return PENDING_CONTEXT.get(game_title)


def clear_pending_context(game_title):
    """Clear pending context after confirmation."""
    global PENDING_CONTEXT
    PENDING_CONTEXT.pop(game_title, None)

def _show_context_view():
    """Show current context in a formatted message."""
    from context_manager import load_verified_context
    ctx = _cs_load_context()
    game = env("GAME_TITLE", "Unknown")
    verified = load_verified_context(game)

    chars = ctx.get("characters", [])
    locs = ctx.get("locations", [])
    rels = ctx.get("relationships", [])

    msg = f"""📝 Context for {game}

📝 Characters ({len(chars)}):
{', '.join(chars[:15])}{'...' if len(chars) > 15 else ''}

📍 Locations ({len(locs)}):
{', '.join(locs[:10])}{'...' if len(locs) > 10 else ''}

👥 Relationships ({len(rels)}):
"""
    for r in rels[:5]:
        if isinstance(r, dict):
            msg += f"• {r.get('from', '')} ↔ {r.get('to', '')}: {r.get('relationship', '')}\n"
        else:
            msg += f"• {r}\n"

    if len(rels) > 5:
        msg += f"... and {len(rels) - 5} more\n"

    if verified:
        msg += f"\n✅ Verified: Yes (saved {verified.get('verified_at', 'unknown')})"
    else:
        msg += "\n❌ Verified: No"

    return msg

def _reload_context_from_obsidian():
    """Reload context from Obsidian markdown files and save as verified."""
    from context_manager import save_verified_context

    ctx = _cs_load_context()
    game = env("GAME_TITLE", "Unknown")

    # Save as verified context
    save_verified_context(game, ctx)

    chars = len(ctx.get("characters", []))
    locs = len(ctx.get("locations", []))
    rels = len(ctx.get("relationships", []))

    return f"✅ Reloaded from Obsidian and saved as verified!\n\n📝 {chars} chars\n📍 {locs} locs\n👥 {rels} rels"

# ─── Inline Menu Functions ───────────────────────────────────────────────────
def get_main_menu():
    """Main menu reorganized by functionality groups."""
    return {
        "inline_keyboard": [
            [{"text": "📊 Status", "callback_data": "menu_status"}],
            [{"text": "▶️ Run Full Pipeline", "callback_data": "run_full"}],
            [{"text": "────────── Tools ──────────", "callback_data": "noop"}],
            [{"text": "🎨 Content Studio", "callback_data": "menu_content_studio"}, {"text": "🗂️ Context", "callback_data": "menu_context"}],
            [{"text": "⚙️ Config", "callback_data": "menu_config"}, {"text": "ℹ️ Help", "callback_data": "menu_help"}]
        ]
    }

def get_run_menu():
    """Run menu - organized pipeline control."""
    return {
        "inline_keyboard": [
            [{"text": "▶️ Run Full Pipeline", "callback_data": "run_full"}],
            [{"text": "────────── Options ──────────", "callback_data": "noop"}],
            [{"text": "⬅️ Back", "callback_data": "menu_back"}]
        ]
    }

def get_context_menu():
    """Context management submenu."""
    game = env("GAME_TITLE", "No game set")
    verified = load_verified_context(game)
    verified_info = "✅ Verified" if verified else "❌ Not verified"

    return {
        "inline_keyboard": [
            [{"text": "📝 View Context", "callback_data": "ctx_view"}],
            [{"text": "🔄 Reload from Obsidian", "callback_data": "ctx_reload"}],
            [{"text": "🗑️ Clear Context", "callback_data": "ctx_clear_verified"}],
            [{"text": "⬅️ Back", "callback_data": "menu_back"}]
        ]
    }

def get_config_menu():
    return {
        "inline_keyboard": [
            [{"text": "🎤 Voice", "callback_data": "config_voice"}, {"text": "📝 Index", "callback_data": "config_index"}],
            [{"text": "🎵 Style", "callback_data": "config_style"}, {"text": "🎮 Game", "callback_data": "config_game"}],
            [{"text": "📁 Source", "callback_data": "config_source"}, {"text": "📂 Files", "callback_data": "files_browse"}],
            [{"text": "⬅️ Back", "callback_data": "menu_back"}]
        ]
    }

def get_help_menu():
    """Help menu with organized information."""
    return {
        "inline_keyboard": [
            [{"text": "📖 Commands", "callback_data": "help_commands"}],
            [{"text": "💬 Pipeline Phases", "callback_data": "help_phases"}],
            [{"text": "🎤 TTS Voices", "callback_data": "help_voices"}],
            [{"text": "📚 Context System", "callback_data": "help_context"}],
            [{"text": "⬅️ Back to Menu", "callback_data": "menu_back"}]
        ]
    }

# ─── Help Content Functions ─────────────────────────────────────────────────

def handle_help_callback(callback_data):
    """Handle help submenu callbacks."""
    if callback_data == "help_commands":
        return """📖 Telegram Commands

📊 Status & Info:
/status - Show listener & pipeline status
/config - Show current settings
/version - Show version info
/debug - Show recent logs
/menu - Show interactive menu

▶️ Pipeline Control:
/run - Run full pipeline
/stop_pipeline - Stop running pipeline

🎨 Content Studio:
/cs - Open Content Studio
/cs_context - View context
/context_clear - Clear all context

🛠️ Tools:
/cleanup - Delete all generated files
/learning_stats - Show AI learning stats
/update - Check for updates"""

    elif callback_data == "help_phases":
        return """💬 Pipeline Phases

Phase 1 (📥) - Download
Downloads videos from YouTube playlist

Phase 2 (📝) - Transcribe + Context
Converts audio to text with timestamps
Extracts context (characters, locations)
🔧 NEW: Pauses for context confirmation!

Phase 4 (📝) - Scripts
Generates AI-powered scripts
Uses verified context for accuracy

Phase 5 (🎬) - Clips
Extracts video clips based on scenes

Phase 6 (🎤) - TTS
Creates AI voice narration
Generates SRT subtitles"""

    elif callback_data == "help_voices":
        return """🎤 Available TTS Voices

Categories:
🧙 Mysterious: Zephyr, Charon, Umbriel
👥 Conversational: Aoede, Leda, Kore
📺 Documentary: Vindemiatrix, Gacrux, Sadachbia
🔥 Intense: Fenrir, Orus, Rasalgethi
📚 Educational: Alnilam, Algieba, Schedar

Change via:
• Menu → Config → Voice
• /set_voice [name]"""

    elif callback_data == "help_context":
        return """📚 Context System

How it works:
1. Phase 2 extracts context from transcript
2. If first run → pauses for confirmation
3. If changes detected → pauses for review
4. You approve → saved as verified

Why verify?
• Validation uses verified context
• Prevents hallucinated characters
• More accurate scripts

Edit via:
• Click Edit on confirmation message
• Edit Obsidian files directly"""

    return None

def get_voice_menu():
    voices = TTS_VOICES
    current = env("TTS_VOICE", "")
    keyboard = []
    for i in range(0, len(voices), 3):
        row = []
        for v in voices[i:i+3]:
            mark = "✓" if v == current else ""
            row.append({"text": f"{v} {mark}".strip(), "callback_data": f"set_voice_{v}"})
        keyboard.append(row)
    keyboard.append([{"text": "⬅️ Back", "callback_data": "menu_config"}])
    return {"inline_keyboard": keyboard}

def get_index_menu():
    keyboard = [
        [{"text": "1", "callback_data": "set_index_1"}, {"text": "2", "callback_data": "set_index_2"}, {"text": "3", "callback_data": "set_index_3"}, {"text": "4", "callback_data": "set_index_4"}, {"text": "5", "callback_data": "set_index_5"}],
        [{"text": "6", "callback_data": "set_index_6"}, {"text": "7", "callback_data": "set_index_7"}, {"text": "8", "callback_data": "set_index_8"}, {"text": "9", "callback_data": "set_index_9"}, {"text": "10", "callback_data": "set_index_10"}],
        [{"text": "⬅️ Back", "callback_data": "menu_config"}]
    ]
    return {"inline_keyboard": keyboard}

def get_style_menu():
    styles = ["Default", "Narrative", "Exciting", "Mysterious", "Funny", "Emotional", "Action", "Horror", "Romance", "Documentary"]
    current = env("TTS_STYLE", "")
    keyboard = []
    for i in range(0, len(styles), 2):
        row = []
        for s in styles[i:i+2]:
            mark = "✓" if s == current else ""
            row.append({"text": f"{s} {mark}".strip(), "callback_data": f"set_style_{s}"})
        keyboard.append(row)
    keyboard.append([{"text": "⬅️ Back", "callback_data": "menu_config"}])
    return {"inline_keyboard": keyboard}

def get_game_menu():
    games = ["Life is Strange", "Before the Storm", "True Colors", "Double Exposure", "Spider-Man", "God of War", "Hogwarts Legacy", "The Last of Us"]
    current = env("GAME_TITLE", "")
    keyboard = []
    for i in range(0, len(games), 2):
        row = []
        for g in games[i:i+2]:
            mark = "✓" if g == current else ""
            row.append({"text": f"{g} {mark}".strip(), "callback_data": f"set_game_{g}"})
        keyboard.append(row)
    keyboard.append([{"text": "🗑️ Clear", "callback_data": "set_game__clear"}])
    keyboard.append([{"text": "⬅️ Back", "callback_data": "menu_config"}])
    return {"inline_keyboard": keyboard}

def get_files_menu():
    sc = count_files(os.path.join(SCRIPTS_DIR, "*.txt"))
    cc = count_files(os.path.join(SHORTS_DIR, "*.mp4"))
    wc = count_files(os.path.join(TTS_DIR, "*.wav"))
    return {
        "inline_keyboard": [
            [{"text": f"📝 Scripts ({sc})", "callback_data": "files_scripts"}, {"text": f"🎬 Clips ({cc})", "callback_data": "files_clips"}],
            [{"text": f"🎤 TTS ({wc})", "callback_data": "files_tts"}],
            [{"text": "🧹 Cleanup All", "callback_data": "cleanup_files"}, {"text": "⬅️ Back", "callback_data": "menu_config"}]
        ]
    }

def get_content_studio_menu():
    tc = count_files(os.path.join(CS_TRANSCRIPTS_DIR, "*.json"))
    sc = count_files(os.path.join(CS_SHORTS_DIR, "*.mp4"))
    cc = count_files(os.path.join(CS_SCRIPTS_DIR, "*.txt"))
    return {
        "inline_keyboard": [
            [{"text": "📥 Import Pipeline Data", "callback_data": "cs_import"}],
            [{"text": "🎬 Generate Script", "callback_data": "cs_generate"}],
            [{"text": "🎤 Generate TTS", "callback_data": "cs_generate_tts"}],
            [{"text": "🗑️ Clear All", "callback_data": "cs_clear"}],
            [{"text": f"📊 {tc} transcripts, {sc} shorts, {cc} scripts", "callback_data": "cs_status"}],
            [{"text": "⬅️ Back", "callback_data": "menu_back"}]
        ]
    }

def handle_menu_callback(callback_data, cb_id=None):
    """Handle menu button callbacks."""
    if callback_data == "menu_status":
        return _get_rich_status()
    elif callback_data == "menu_pipeline":
        return None, get_run_menu()
    elif callback_data == "menu_restart":
        return "🔄 Restarting listener...", "do_restart"
    elif callback_data == "menu_config":
        return None, get_config_menu()
    elif callback_data == "menu_help":
        return None, get_help_menu()
    elif callback_data.startswith("help_"):
        return handle_help_callback(callback_data)
    elif callback_data == "menu_content_studio":
        return None, get_content_studio_menu()
    elif callback_data == "menu_context":
        return None, get_context_menu()
    elif callback_data == "menu_update":
        script_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        update_info = check_for_updates(script_root)
        if update_info.get("update_available"):
            remote_ver = update_info.get("remote_version", "Unknown")
            return f"🔔 Update available: v{remote_ver}\nRun /update to install.", "run_update"
        return "✅ You have the latest version."
    elif callback_data == "menu_stop":
        return "🛑 Stopping pipeline...", "stop_pipeline"
    elif callback_data == "menu_back":
        return None, get_main_menu()
    elif callback_data == "noop":
        return None, None  # Do nothing for separator rows
    elif callback_data == "run_full":
        return "▶️ Running full pipeline...", "run_pipeline"
    elif callback_data == "config_voice":
        return None, get_voice_menu()
    elif callback_data == "config_index":
        return None, get_index_menu()
    elif callback_data == "config_style":
        return None, get_style_menu()
    elif callback_data == "config_game":
        return None, get_game_menu()
    elif callback_data == "config_source":
        return "📁 Recording path: " + env("RECORDING_PATH", "~/Videos/Recordings")
    elif callback_data == "files_browse":
        return None, get_files_menu()
    elif callback_data == "files_scripts":
        return _get_files_list("scripts")
    elif callback_data == "files_clips":
        return _get_files_list("clips")
    elif callback_data == "files_tts":
        return _get_files_list("tts")
    elif callback_data == "files_shorts":
        return _get_files_list("shorts")
    elif callback_data == "quick_stop":
        return "🛑 Stopping pipeline...", "stop_pipeline"
    elif callback_data == "quick_restart":
        return "🔄 Restarting listener...", "do_restart"
    elif callback_data == "quick_status":
        return _get_rich_status()
    elif callback_data == "quick_clean":
        return "🧹 Cleaning up files...", "cleanup_files"
    elif callback_data == "run_update":
        return "🔄 Updating Cogitator...", "do_update"
    elif callback_data == "set_voice_":
        return None, get_voice_menu()
    elif callback_data.startswith("set_voice_"):
        voice = callback_data.replace("set_voice_", "")
        update_env_var("TTS_VOICE", voice)
        return f"✅ Voice set to: {voice}"
    elif callback_data.startswith("set_index_"):
        index = callback_data.replace("set_index_", "")
        update_env_var("PLAYLIST_INDEX", index)
        return f"✅ Playlist index set to: {index}"
    elif callback_data.startswith("set_style_"):
        style = callback_data.replace("set_style_", "")
        update_env_var("TTS_STYLE", style)
        return f"✅ Style set to: {style}"
    elif callback_data.startswith("set_game_"):
        game = callback_data.replace("set_game_", "")
        if game == "_clear":
            update_env_var("GAME_TITLE", "")
            return "✅ Game title cleared"
        update_env_var("GAME_TITLE", game)
        return f"✅ Game set to: {game}"
    elif callback_data == "ctx_view":
        return _show_context_view()
    elif callback_data == "ctx_reload":
        return _reload_context_from_obsidian()
    elif callback_data == "ctx_clear_verified":
        game = env("GAME_TITLE", "")
        clear_verified_context(game)
        return "✅ Context cleared"
    elif callback_data.startswith("ctx_"):
        # Context callbacks are routed directly in the listener with cb_id
        # This path should not be reached for ctx_ callbacks
        return "Use context menu directly"
    elif callback_data == "cleanup_files":
        count = cleanup_all_files()
        return f"🧹 Cleaned up {count} file(s)"
    elif callback_data == "do_update":
        return _do_update_menu()
    elif callback_data == "cs_import":
        return "📥 Importing pipeline data...", "cs_do_import"
    elif callback_data == "cs_generate":
        return "🎬 Analyzing transcripts...", "cs_do_generate"
    elif callback_data == "cs_generate_tts":
        return "🎤 Generating TTS...", "cs_do_generate_tts"
    elif callback_data == "cs_clear":
        return "🗑️ Clearing Content Studio...", "cs_do_clear"
    elif callback_data == "cs_status":
        tc = count_files(os.path.join(CS_TRANSCRIPTS_DIR, "*.json"))
        sc = count_files(os.path.join(CS_SHORTS_DIR, "*.mp4"))
        return f"📊 Content Studio:\n📝 Transcripts: {tc}\n🎬 Shorts: {sc}"
    else:
        return "Unknown action"


def _get_rich_status():
    """Get rich status card with file counts and pipeline info."""
    from context_manager import load_verified_context, get_verified_context_for_validation

    script_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_ver = get_local_version(script_root)

    # File counts
    sc = count_files(os.path.join(SCRIPTS_DIR, "*.txt"))
    cc = count_files(os.path.join(SHORTS_DIR, "*.mp4"))
    wc = count_files(os.path.join(TTS_DIR, "*.wav"))
    tc = count_files(os.path.join(TRANSCRIPTS_DIR, "*.json"))

    # Pipeline status
    s = open(STATUS_FILE).read() if os.path.exists(STATUS_FILE) else ""
    if PIPELINE_RUNNING:
        status_line = f"🔄 Running: {s}"
    elif s:
        status_line = f"💤 Idle — Last: {s}"
    else:
        status_line = "💤 Idle"

    # Voice and style
    voice = env("TTS_VOICE", "Not set")
    style = env("TTS_STYLE", "Default")
    game = env("GAME_TITLE", "Not set")

    # Context status
    game_title = game if game else "No game set"
    verified = load_verified_context(game_title)
    if verified:
        ctx = verified.get("context", {})
        ctx_chars = len(ctx.get("characters", []))
        ctx_locs = len(ctx.get("locations", []))
        ctx_rels = len(ctx.get("relationships", []))
        verified_info = f"✅ Verified ({ctx_chars} chars, {ctx_locs} locs, {ctx_rels} rels)"
    else:
        verified_info = "❌ Not verified"

    status = f"""📊 Cogitator Status — v{local_ver}

🔹 Pipeline: {status_line}

📁 Files:
  📝 Scripts: {sc}
  🎬 Clips: {cc}
  🎤 TTS: {wc}
  📄 Transcripts: {tc}

🎮 Game: {game_title}
🗂️ Context: {verified_info}

⚙️ Config:
  🎤 Voice: {voice}
  🎵 Style: {style[:20]}..."""
    return status


def _get_files_list(folder):
    """Get list of files in a folder."""
    folder_map = {"scripts": SCRIPTS_DIR, "clips": SHORTS_DIR, "tts": TTS_DIR, "shorts": SHORTS_DIR}
    dir_path = folder_map.get(folder)
    if not dir_path:
        return "Unknown folder"

    files = sorted(glob.glob(os.path.join(dir_path, "*")), key=os.path.getmtime, reverse=True)[:10]
    if not files:
        return f"No files in {folder}"

    names = [os.path.basename(f) for f in files]
    return f"📁 {folder.capitalize()} ({len(names)} total):\n" + "\n".join(f"• {n[:40]}" for n in names)


# ─── Content Studio Functions ─────────────────────────────────────────────────
def _cs_import_data():
    """Import transcripts and shorts from pipeline to Content Studio."""
    # Ensure directories exist
    for d in (CONTENT_STUDIO_DIR, CS_TRANSCRIPTS_DIR, CS_SHORTS_DIR):
        os.makedirs(d, exist_ok=True)

    # Import transcripts
    transcript_count = 0
    for f in glob.glob(os.path.join(TRANSCRIPTS_DIR, "*.json")):
        dst = os.path.join(CS_TRANSCRIPTS_DIR, os.path.basename(f))
        if not os.path.exists(dst):
            shutil.move(f, dst)
            transcript_count += 1

    # Import shorts
    short_count = 0
    for f in glob.glob(os.path.join(SHORTS_DIR, "*.mp4")):
        dst = os.path.join(CS_SHORTS_DIR, os.path.basename(f))
        if not os.path.exists(dst):
            shutil.move(f, dst)
            short_count += 1

    return transcript_count, short_count


def _cs_clear_data():
    """Clear all files from Content Studio."""
    count = 0
    for d in (CS_TRANSCRIPTS_DIR, CS_SHORTS_DIR, CS_SCRIPTS_DIR, CS_TTS_DIR):
        if os.path.exists(d):
            for f in glob.glob(os.path.join(d, "*")):
                try:
                    os.remove(f)
                    count += 1
                except OSError:
                    pass
    return count


def _cs_generate_script_only():
    """Generate script only (no TTS). Uses newest unprocessed transcript."""
    for d in (CS_SCRIPTS_DIR, CS_TTS_DIR):
        os.makedirs(d, exist_ok=True)

    # Find newest unprocessed transcript
    transcript = _cs_find_newest_transcript()
    if not transcript:
        tg_send("✅ No new transcripts. All have scripts generated.")
        ctx = _cs_load_context()
        tg_send(f"Scripts generated: {len(ctx.get('previous_scripts', []))}")
        return

    transcript_name = os.path.basename(transcript)
    tg_send(f"📖 Reading transcript: {transcript_name}")

    transcript_text = _cs_read_transcript(transcript)
    if not transcript_text:
        tg_send(f"❌ Could not read {transcript_name}")
        return

    tg_send(f"📖 Read {len(transcript_text)} characters")

    # Extract and update context from transcript
    game_title = env("GAME_TITLE", "Unknown Game")
    game_key = game_title.lower().replace(" ", "_")
    tg_send("🔍 Extracting context from transcript...")
    extracted = _cs_extract_context_from_transcript(transcript_text, game_title)
    ctx = _cs_load_context()
    if extracted:
        ctx = _cs_update_context(extracted, transcript_name)
        _save_segment_references(game_key, transcript_name, extracted, transcript_file=transcript)
        tg_send(f"📚 Context updated: {len(ctx['characters'])} characters, {len(ctx['locations'])} locations")

        # NEW: Also mine to MemPalace for persistent memory
        if MEMPALACE_AVAILABLE and env("MEMORY_ENABLED", "true").lower() == "true":
            try:
                mp_manager = get_mempalace_manager()
                if mp_manager and transcript:
                    result = mp_manager.mine_transcript(transcript, game_title)
                    if result.get("status") == "success":
                        tg_send(f"🧠 MemPalace: Mined transcript for {game_title}")
                    else:
                        tg_send(f"🧠 MemPalace: Mining skipped")
            except Exception as mp_err:
                tg_send(f"🧠 MemPalace: Mining failed - {mp_err}")
    else:
        tg_send("⚠️ Could not extract context, using existing")

    tg_send("🔍 Analyzing content (this may take a moment)...")
    content_type, subject, angle, voice_style, real_characters, key_plot_points = _cs_analyze_transcript(transcript_text)
    tg_send(f"📝 Detected: {content_type}\n👤 Subject: {subject}\n🎤 Voice: {voice_style}\n📋 Characters: {', '.join(real_characters[:5]) if real_characters else 'None'}\n🔑 Plot: {key_plot_points[0] if key_plot_points else 'None'}")

    tg_send("✍️ Generating script (~1500 words)...")

    # NEW: Inject MemPalace memory into context
    if MEMPALACE_AVAILABLE and env("MEMORY_ENABLED", "true").lower() == "true":
        game_title = env("GAME_TITLE", "")
        if game_title and game_title != "Unknown Game":
            try:
                mp_manager = get_mempalace_manager()
                if mp_manager:
                    game_memory = mp_manager.get_game_memory(game_title)
                    if game_memory and game_memory.get("success"):
                        tg_send(f"🧠 MemPalace: Retrieved memory for {game_title}")
            except Exception as mp_err:
                tg_send(f"🧠 MemPalace: Memory retrieval failed - {mp_err}")

    try:
        script = _cs_generate_script(transcript_text, content_type, subject, angle, real_characters, key_plot_points)
    except Exception as e:
        tg_send(f"❌ Script generation failed: {e}")
        return

    script_file = os.path.join(CS_SCRIPTS_DIR, f"content_{content_type.lower()}_{int(time.time())}.txt")
    with open(script_file, "w") as f:
        f.write(script)

    # NEW: Log quality to MemPalace
    if MEMPALACE_AVAILABLE and env("MEMORY_ENABLED", "true").lower() == "true":
        try:
            mp_manager = get_mempalace_manager()
            if mp_manager:
                metric = {
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'source': 'content_studio',
                    'content_type': content_type,
                    'subject': subject,
                    'word_count': len(script.split()),
                }
                mp_manager.add_quality_metric(game_title, metric)
                tg_send(f"🧠 MemPalace: Logged quality metric")
        except Exception as mp_err:
            pass  # Don't fail on quality logging

    # Create script summary for context
    script_summary = f"Script {len(ctx.get('previous_scripts', [])) + 1}: {subject} - {content_type} - {angle[:50]}..."
    _cs_update_context({}, transcript_name, script_summary)

    tg_send(f"✅ Script generated!\n📝 Saved: {os.path.basename(script_file)}")


def _cs_clean_script_for_tts(script):
    """Remove production notes and stage directions from script for TTS."""
    import re

    # Remove everything in parentheses (stage directions, visual cues)
    cleaned = re.sub(r'\([^)]*\)', '', script)

    # Remove markdown bold/italic markers
    cleaned = re.sub(r'\*\*', '', cleaned)
    cleaned = re.sub(r'\*', '', cleaned)

    # Remove lines that are only stage directions or visual cues
    lines = cleaned.split('\n')
    spoken_lines = []
    for line in lines:
        line = line.strip()
        # Skip empty lines and lines that are just visual cues
        if not line:
            continue
        if line.lower().startswith('visual:') or line.lower().startswith('intro') or line.lower().startswith('outro'):
            continue
        spoken_lines.append(line)

    return '\n'.join(spoken_lines)


def _cs_generate_tts_only():
    """Generate TTS from existing scripts."""
    scripts = sorted(glob.glob(os.path.join(CS_SCRIPTS_DIR, "*.txt")), key=os.path.getmtime, reverse=True)
    if not scripts:
        tg_send("❌ No scripts found. Generate a script first.")
        return

    latest_script = scripts[0]
    with open(latest_script) as f:
        original_script = f.read()

    script = _cs_clean_script_for_tts(original_script)
    word_count = len(script.split())
    tg_send(f"📄 Found script: {os.path.basename(latest_script)}")
    tg_send(f"🧹 Cleaned script for TTS: {word_count} words")
    tg_send("🎤 Generating TTS audio...")

    try:
        audio_file, voice = _cs_generate_tts(script, "Documentary")
    except Exception as e:
        tg_send(f"❌ TTS generation failed: {e}")
        return

    tg_send(f"✅ TTS generated!\n🎤 Voice: {voice}\n📁 Saved: {os.path.basename(audio_file)}")


def _do_update_menu():
    """Perform update and return result."""
    script_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = perform_update(script_root)
    if result.get("success"):
        return f"✅ Updated to v{result.get('version', 'unknown')}. Restart listener to apply."
    return f"❌ Update failed: {result.get('message', 'Unknown error')}"

# ─── Helpers ───────────────────────────────────────────────────────────────────
def update_env_var(key, value):
    with _env_lock:
        lines = []
        found = False
        if os.path.exists(ENV_FILE):
            with open(ENV_FILE) as f:
                lines = f.readlines()
        with open(ENV_FILE, "w") as f:
            for line in lines:
                if line.strip().startswith(f"{key}="):
                    f.write(f'{key}="{value}"\n')
                    found = True
                else:
                    f.write(line)
            if not found:
                f.write(f'{key}="{value}"\n')
        ENV[key] = value


# ─── Bot API ──────────────────────────────────────────────────────────────────

def tg_api(method, params=None):
    token = env("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/{method}"
    if params:
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=data, method="POST")
    else:
        req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=35) as resp:
        return json.loads(resp.read())

def process_cmd(text, chat_id):
    parts = text.split(None, 1)
    cmd  = parts[0].split("@", 1)[0]
    args = parts[1] if len(parts) > 1 else ""

    if cmd in ("/run_pipeline", "/runpipeline"):
        if not _check_configured():
            tg_send("Not configured yet. Run onboarding first:\n  python3 cogitator.py onboard")
        else:
            tg_send("Pipeline triggered! Source: YouTube playlist")
            def _run():
                global PIPELINE_RUNNING
                PIPELINE_RUNNING = True
                try:
                    run_pipeline()
                except Exception as e:
                    tg_send(f"Pipeline error: {e}")
                finally:
                    PIPELINE_RUNNING = False
            threading.Thread(target=_run, daemon=True).start()

    elif cmd in ("/run_local", "/runlocal"):
        if not _check_configured():
            tg_send("Not configured yet. Run onboarding first:\n  python3 cogitator.py onboard")
        else:
            recording_path = env("RECORDING_PATH", os.path.expanduser("~/Videos/Recordings"))
            tg_send(f"Current source: YouTube playlist (default)\nProcessing local recordings from: {recording_path}")
            def _run():
                global PIPELINE_RUNNING
                PIPELINE_RUNNING = True
                try:
                    run_local_recordings(recording_path)
                except Exception as e:
                    tg_send(f"Local recording error: {e}")
                finally:
                    PIPELINE_RUNNING = False
            threading.Thread(target=_run, daemon=True).start()

    elif cmd in ("/set_voice", "/setvoice"):
        if not args:
            tg_send("Usage: /set_voice Algenib\nGemini Voices: Zephyr, Puck, Charon, Kore, Fenrir, Leda, Orus, Aoede, Callirrhoe, Autonoe, Enceladus, Iapetus, Umbriel, Algieba, Despina, Erinome, Algenib, Rasalgethi, Schedar, Gacrux, Pulcherrima, Achird, Zubenelgenubi, Vindemiatrix, Sadachbia, Sadaltager, Sulafat, Achernar, Alnilam, Laomedeia")
        else:
            update_env_var("TTS_VOICE", args)
            tg_send(f"Voice set to: {args}")

    elif cmd in ("/voices", "/listvoices"):
        tg_send("""Gemini TTS Voices (Chirp 3):

Female: Vindemiatrix, Aoede, Callirrhoe, Gacrux, Sulafat, Leda, Kore, Enceladus, Erinome, Despina, Alnilam, Laomedeia, Achernar, Pulcherrima, Zephyr
Male: Puck, Charon, Fenrir, Orus, Iapetus, Umbriel, Algieba, Rasalgethi, Schedar, Sadachbia, Sadaltager, Achird, Zubenelgenubi, Algenib, Autonoe

Random voice selection is enabled - voice rotates on each listener restart.
Use /set_voice <name> to select a specific voice.
Example: /set_voice Vindemiatrix""")

    elif cmd in ("/set_style", "/setstyle"):
        if not args:
            update_env_var("TTS_STYLE", "")
            tg_send("Style cleared.")
        else:
            update_env_var("TTS_STYLE", args)
            tg_send(f"Style set to: {args}")

    elif cmd in ("/set_index", "/setindex"):
        if not args:
            update_env_var("PLAYLIST_INDEX", "")
            tg_send("Playlist index reset to default (1).")
        else:
            try:
                idx = int(args)
                if idx < 1:
                    tg_send("Index must be 1 or greater.")
                else:
                    update_env_var("PLAYLIST_INDEX", str(idx))
                    tg_send(f"Playlist index set to: {idx}")
            except ValueError:
                tg_send("Invalid index. Use /set_index 3")

    elif cmd in ("/set_clips", "/setclips"):
        if not args:
            current = env("CLIPS_PER_HOUR", "5")
            tg_send(f"Current clips per hour: {current}\nUsage: /set_clips 10")
        else:
            try:
                clips = int(args)
                if clips < 1 or clips > 20:
                    tg_send("Clips per hour must be between 1 and 20.")
                else:
                    update_env_var("CLIPS_PER_HOUR", str(clips))
                    tg_send(f"Clips per hour set to: {clips}")
            except ValueError:
                tg_send("Invalid number. Use /set_clips 10")

    elif cmd in ("/set_srt_words", "/setsrt"):
        if not args:
            current = env("SRT_MAX_WORDS", "10")
            tg_send(f"Current SRT max words: {current}\nUsage: /set_srt_words 10")
        else:
            try:
                words = int(args)
                if words < 3 or words > 20:
                    tg_send("SRT max words must be between 3 and 20.")
                else:
                    update_env_var("SRT_MAX_WORDS", str(words))
                    tg_send(f"SRT max words set to: {words}")
            except ValueError:
                tg_send("Invalid number. Use /set_srt_words 10")

    elif cmd in ("/set_game", "/setgame"):
        if not args:
            current = env("GAME_TITLE", "")
            if current:
                tg_send(f"Current game: {current}\nUsage: /set_game The Last of Us Part II\nClear with: /set_game clear")
            else:
                tg_send("No game set.\nUsage: /set_game The Last of Us Part II")
        elif args.lower() == "clear":
            update_env_var("GAME_TITLE", "")
            _cs_clear_context()
            tg_send("Game title cleared. Context cleared.")
        else:
            update_env_var("GAME_TITLE", args)
            tg_send(f"Game set to: {args}")

    elif cmd in ("/cs_context", "/context"):
        ctx = _cs_load_context()
        chars = ctx.get("characters", [])
        locs = ctx.get("locations", [])
        terms = ctx.get("key_terms", [])
        rels = ctx.get("relationships", [])
        transcripts = ctx.get("processed_transcripts", [])
        scripts = ctx.get("previous_scripts", [])

        msg = "📚 Content Studio Context:\n\n"
        msg += f"Characters ({len(chars)}): {', '.join(chars) if chars else 'none'}\n"
        msg += f"Locations ({len(locs)}): {', '.join(locs) if locs else 'none'}\n"
        msg += f"Key Terms ({len(terms)}): {', '.join(terms[:10]) if terms else 'none'}\n"
        msg += f"Relationships ({len(rels)}): {', '.join(rels) if rels else 'none'}\n"
        msg += f"\nProcessed Transcripts: {len(transcripts)}\n"
        msg += f"Previous Scripts: {len(scripts)}"

        tg_send(msg)

    elif cmd == "/context_clear":
        _cs_clear_context()
        tg_send("Context cleared.")

    elif cmd in ("/config", "/settings"):
        voice = env("TTS_VOICE", "Vindemiatrix")
        style = env("TTS_STYLE") or "(none)"
        index = env("PLAYLIST_INDEX", "1")
        clips = env("CLIPS_PER_HOUR", "5")
        game = env("GAME_TITLE", "") or "(none)"
        status = "Running" if PIPELINE_RUNNING else "Idle"

        wc = count_files(os.path.join(WORKSPACE, "tts/*.wav"))
        sc = count_files(os.path.join(WORKSPACE, "tts/*.srt"))
        rc = count_files(os.path.join(WORKSPACE, "scripts/*.txt"))
        cc = count_files(os.path.join(WORKSPACE, "shorts/*.mp4"))
        tg_send(f"Config:\nGame: {game}\nVoice: {voice}\nStyle: {style}\nIndex: {index}\nClips/hr: {clips}\nStatus: {status}\n\nFiles:\nScripts: {rc}\nClips: {cc}\nTTS WAVs: {wc}\nTTS SRTs: {sc}")

    elif cmd == "/status":
        listener_status = "No"
        listener_pid = "-"
        listener_dir = "-"
        if os.path.exists(PID_FILE):
            try:
                with open(PID_FILE) as f:
                    pid = int(f.read().strip())
                try:
                    os.kill(pid, 0)
                    listener_status = "Yes"
                    listener_pid = str(pid)
                    listener_dir = os.readlink(f"/proc/{pid}/cwd")
                except (ProcessLookupError, PermissionError):
                    os.remove(PID_FILE)
            except (ValueError, OSError):
                pass

        s = open(STATUS_FILE).read() if os.path.exists(STATUS_FILE) else ""
        pipeline_status = f"Running: {s}" if PIPELINE_RUNNING else f"Idle. Last: {s}" if s else "Idle"

        # Get version and update status
        script_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        local_ver = get_local_version(script_root)
        update_info = check_for_updates(script_root)
        update_status = ""
        if update_info.get("update_available"):
            remote_ver = update_info.get("remote_version", "?")
            update_status = f"\n\nUpdate: v{remote_ver} available ✨"

        tg_send(f"Listener: {listener_status}\nPID: {listener_pid}\nDir: {listener_dir}\nVersion: v{local_ver}\n\nPipeline: {pipeline_status}{update_status}")

    elif cmd == "/debug":
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE) as f:
                lines = f.readlines()[-10:]
            important = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if len(line) > 150:
                    continue
                if "Transcribe:" in line or "transcribing" in line.lower():
                    continue
                important.append(line)
            if important:
                txt = "\n".join(important[-8:])
                tg_send(f"🐛 Recent Log:\n\n{txt}")
            else:
                tg_send("No recent log entries.")
        else:
            tg_send("No logs found.")

    elif cmd == "/memory":
        # Show MemPalace memory status + learned constraints
        try:
            mp_manager = get_mempalace_manager()
            status = mp_manager.status()

            # Get list of all games (from Context directory)
            context_dir = os.path.join(WORKSPACE, "Context")
            games = []
            if os.path.exists(context_dir):
                for item in os.listdir(context_dir):
                    item_path = os.path.join(context_dir, item)
                    if os.path.isdir(item_path) and item != "history":
                        # Check if has markdown context files
                        has_chars = os.path.exists(os.path.join(item_path, "characters.md"))
                        has_context = "✅" if has_chars else "❌"
                        games.append(f"- {item.replace('_', ' ').title()}: Context {has_context}")

            msg = "📚 MemPalace Memory:\n\n"
            if status.get("status_output"):
                msg += status["status_output"]
            else:
                msg += "No memory indexed yet.\n"

            if games:
                msg += "\n🎮 Games in Context:\n"
                msg += "\n".join(games)
            else:
                msg += "\nNo games in Context directory yet."

            # Show learned constraints
            constraints = get_learned_constraints()
            if constraints:
                msg += f"\n\n🧠 Learned Constraints ({len(constraints)}):\n"
                for c in constraints[:5]:
                    msg += f"- {c[:60]}...\n" if len(c) > 60 else f"- {c}\n"
                if len(constraints) > 5:
                    msg += f"  ... and {len(constraints) - 5} more"

            tg_send(msg)
        except Exception as e:
            tg_send(f"Memory check failed: {e}")

    elif cmd == "/games":
        # Show all games with their status
        context_dir = os.path.join(WORKSPACE, "Context")
        game_data_dir = os.path.join(WORKSPACE, "game_data")

        msg = "🎮 Cogitator Games:\n\n"

        # Current game
        current_game = env("GAME_TITLE", "None")
        msg += f"Current: {current_game}\n\n"

        # Games in Context directory
        games = []
        if os.path.exists(context_dir):
            for item in os.listdir(context_dir):
                item_path = os.path.join(context_dir, item)
                if os.path.isdir(item_path) and item != "history":
                    ctx_file = os.path.join(item_path, "context.json")
                    has_context = os.path.exists(ctx_file)
                    games.append((item, has_context))

        if games:
            msg += "📁 Context Directory:\n"
            for game, has_context in sorted(games):
                name = game.replace("_", " ").title()
                status = "✅" if has_context else "❌"
                msg += f"- {name}: Context {status}\n"
        else:
            msg += "No games in Context directory.\n"

        msg += "\nUse /set_game <name> to switch games."
        tg_send(msg)


    elif cmd == "/help":
        tg_send("""Cogitator — YouTube Shorts Pipeline
Converts long-form YouTube videos into shorts with AI scripts and TTS.

Pipeline Phases:
1️⃣ Download  - Download latest video (best quality)
2️⃣ Transcribe - Generate transcript with stable-ts
3️⃣ Scripts   - AI-generated short scripts via Gemini
4️⃣ Clips    - Extract video clips based on scenes
5️⃣ TTS       - Generate narration audio + subtitles

Commands:
/run_pipeline    - Run full pipeline
/run_local       - Run pipeline on local recording

/set_voice Puck    - Change TTS voice
/voices          - List available voices
/set_style Say...  - Set style prefix
/set_style         - Clear style
/set_index 3      - Set playlist index (1=first video)
/set_clips 10     - Set clips per hour (1-20)
/set_srt_words 10 - Set SRT max words per line (default: 10)
/set_game Title   - Set game title for scripts
/set_game clear   - Clear game title
/cs_context       - Show Content Studio context
/context_clear     - Clear all context

/config     - Settings and file counts
/status     - Listener and pipeline status
/debug      - Show recent debug log entries
/learning_stats - Show self-improvement learning stats

/version    - Show current version
/update     - Check for and install updates

/restart_listener - Restart the listener
/stop_pipeline   - Stop running pipeline

/delete_partial  - Delete incomplete files
/cleanup         - Delete all generated files
/clean_backups  - Clean old backup versions

/menu      - Show interactive inline menu
/help - This message""")

    elif cmd == "/menu":
        main_menu = get_main_menu()
        tg_send_menu("📋 Cogitator Menu — Select an action:", main_menu)

    elif cmd in ("/cs", "/content_studio"):
        cs_menu = get_content_studio_menu()
        tg_send_menu("🎨 Content Studio — Select an action:", cs_menu)

    elif cmd in ("/restart_listener", "/restart"):
        tg_send("Restarting listener via systemd...")
        subprocess.run(["systemctl", "--user", "restart", "lambda-cut-listener.service"], capture_output=True)

    elif cmd == "/stop_pipeline":
        if PIPELINE_RUNNING:
            global PIPELINE_STOP_REQUESTED
            PIPELINE_STOP_REQUESTED = True
            tg_send("Pipeline stop requested. Finishing current phase...")
        else:
            tg_send("No pipeline is currently running.")

    elif cmd == "/delete_partial":
        count = delete_partial_files()
        tg_send(f"Deleted {count} partial file(s).")

    elif cmd == "/cleanup":
        count = cleanup_all_files()
        tg_send(f"Deleted {count} file(s) from all output directories.")

    elif cmd == "/clean_backups":
        cleanup_old_backups(WORKSPACE)
        tg_send("Old backups cleaned up.")

    elif cmd == "/version":
        script_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        local_ver = get_local_version(script_root)
        update_info = check_for_updates(script_root)
        remote_ver = update_info.get("remote_version", "Unknown")
        if update_info.get("update_available"):
            tg_send(f"Current version: v{local_ver}\nLatest version: v{remote_ver}\n\nUpdate available! Run /update to install.")
        else:
            tg_send(f"Current version: v{local_ver}\nLatest version: v{remote_ver or 'Unknown'}\n\nYou're up to date!")

    elif cmd == "/learning_stats":
        from script_validation import get_learning_summary, analyze_recent_failures
        try:
            summary = get_learning_summary()
            week_analysis = analyze_recent_failures(window_hours=168)

            status_emoji = "🟢" if summary.get("learning_status") == "active" else "🟡"

            msg = f"""🧠 Cogitator Learning Stats

{status_emoji} Status: {summary.get('learning_status', 'unknown').replace('_', ' ').title()}

📊 Last 24 Hours:
- Failures: {summary.get('last_24h', {}).get('failures', 0)}"""

            if summary.get('last_24h', {}).get('top_hallucinations'):
                msg += f"\n- Top hallucinations: {', '.join(summary['last_24h']['top_hallucinations'])}"

            msg += f"""

📈 Last 7 Days:
- Total failures: {summary.get('last_7_days', {}).get('total_failures', 0)}
- Content types: {summary.get('last_7_days', {}).get('content_types_analyzed', 0)}
- High-quality scripts: {summary.get('effective_configs', 0)}"""

            hall_dict = week_analysis.get("character_hallucinations", {})
            if hall_dict and isinstance(hall_dict, dict):
                top_hall = list(hall_dict.items())[:3]
                if top_hall:
                    msg += f"\n\n⚠️ Top Character Hallucinations:"
                    for char, count in top_hall:
                        msg += f"\n- {char}: {count}x"

            tg_send(msg)
        except Exception as e:
            tg_send(f"Learning stats unavailable: {e}")

    elif cmd == "/update":
        script_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        update_info = check_for_updates(script_root)

        if not update_info.get("update_available"):
            tg_send("No update available. You're on the latest version!")
        else:
            remote_ver = update_info.get("remote_version", "Unknown")
            release_notes = get_release_notes()
            # Truncate release notes if too long
            if len(release_notes) > 500:
                release_notes = release_notes[:500] + "..."

            tg_send(f"""Update Available: v{remote_ver}

Release Notes:
{release_notes[:500]}

This will:
1. Backup current installation (up to 2 backups)
2. Download and install new files
3. Preserve your .env and settings
4. Restart listener

Type /confirm_update to proceed.""")

    elif cmd == "/confirm_update":
        script_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        tg_send("Updating... Please wait.")

        def _update():
            global LISTENER_RESTART
            result = perform_update(script_root)
            if result.get("success"):
                tg_send(f"✅ {result.get('message')}\n\nRestarting listener...")
                time.sleep(1)
                LISTENER_RESTART = True
            else:
                tg_send(f"❌ {result.get('message')}")

        t = threading.Thread(target=_update)
        t.start()
        t.join()  # Wait for update to complete before continuing

    else:
        tg_send("Unknown command. Use /help for available commands.")

def listen():
    global LISTENER_RESTART

    if not _telegram_configured():
        print("Telegram not configured. Run onboard and enable Telegram to use the listener.")
        sys.exit(1)

    script_path = os.path.abspath(__file__)
    workspace = os.path.dirname(os.path.dirname(script_path))

    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                old_pid = int(f.read().strip())
            try:
                os.kill(old_pid, 0)
                os.kill(old_pid, 15)
                time.sleep(1)
                try:
                    os.kill(old_pid, 0)
                    os.kill(old_pid, 9)
                except ProcessLookupError:
                    pass
                print(f"Stopped existing listener (PID {old_pid})")
                tg_send(f"Stopped existing listener (PID {old_pid}). Starting new listener.")
            except ProcessLookupError:
                pass
        except (ValueError, OSError):
            pass
        try:
            os.remove(PID_FILE)
        except OSError:
            pass

    svc_dir = os.path.expanduser("~/.config/systemd/user")
    svc_file = os.path.join(svc_dir, "lambda-cut-listener.service")
    if os.path.exists(svc_file):
        with open(svc_file) as f:
            svc_content = f.read()
        python = sys.executable
        new_svc = f"""[Unit]
Description=Cogitator Telegram Listener
After=network.target

[Service]
Type=simple
ExecStartPre=/bin/sleep 10
ExecStart={python} {script_path} listen
WorkingDirectory={workspace}
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
"""
        if svc_content != new_svc:
            with open(svc_file, "w") as f:
                f.write(new_svc)
            subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
            print(f"Updated systemd service to point to {workspace}")
            tg_send(f"Systemd service updated to point to {workspace}")

    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    env("TELEGRAM_BOT_TOKEN")  # Ensure token is loaded
    chat  = env("TELEGRAM_CHAT_ID")

    global STREAMING
    STREAMING = True

    me = tg_api("getMe")
    print(f"Cogitator Listener — @{me['result']['username']}")

    # Check for updates
    print("Checking for updates...")
    script_root = os.path.dirname(os.path.dirname(script_path))
    update_info = check_for_updates(script_root)
    local_ver = update_info.get("local_version", "Unknown")
    print(f"Version: v{local_ver}")

    if update_info.get("update_available"):
        remote_ver = update_info.get("remote_version", "Unknown")
        print(f"Update available: v{remote_ver}")
        tg_send(f"🔔 Update available: v{remote_ver}\nRun /update to install.")
    else:
        print("No updates available.")

    # Rotate TTS voice on each listener start (all voices - male and female)
    rotated_voice = random.choice(TTS_VOICES)

    # Also rotate TTS style randomly
    rotated_style = random.choice(TTS_STYLE_OPTIONS)
    update_env_var("TTS_VOICE", rotated_voice)
    update_env_var("TTS_STYLE", rotated_style)
    print(f"Voice rotated to: {rotated_voice}")
    print(f"Style rotated to: {rotated_style[:50]}...")

    tg_send(f"Cogitator listener started (v{local_ver}).\nVoice: {rotated_voice}\nStyle: {rotated_style[:50]}...")

    oauth_file = os.path.join(WORKSPACE, ".cogitator", "youtube_oauth.json")
    if os.path.exists(oauth_file):
        print("[BACKGROUND] Syncing YouTube metrics...")
        try:
            from performance_database import sync_youtube_metrics
            print("[BACKGROUND] Syncing YouTube metrics...")
            result = sync_youtube_metrics(days=30, max_results=50)
            synced = result.get('matched_count', 0)
            new_metrics = result.get('new_metrics', 0)
            print(f"[BACKGROUND] YouTube sync: {synced} matched, {new_metrics} new metrics")
            if synced > 0 or new_metrics > 0:
                tg_send(f"📊 YouTube sync complete: {synced} matched, {new_metrics} new metrics")
        except Exception as sync_err:
            print(f"[BACKGROUND] YouTube sync failed: {sync_err}")

    offset = 0
    if os.path.exists(OFFSET_FILE):
        try:
            offset = int(open(OFFSET_FILE).read().strip())
        except (ValueError, OSError):
            pass

    global LISTENER_RUNNING
    while LISTENER_RUNNING:
        try:
            r = tg_api("getUpdates", {"limit": 3, "timeout": 30, "offset": offset})
            if not r.get("ok"):
                time.sleep(5)
                continue
            for upd in r["result"]:
                offset = upd["update_id"] + 1
                with open(OFFSET_FILE, "w") as f:
                    f.write(str(offset))

                # Handle callback_query (menu button clicks)
                cb = upd.get("callback_query", {})
                if cb:
                    cb_id = cb.get("id", "")
                    cb_data = cb.get("data", "")
                    cb_msg = cb.get("message", {})
                    cb_chat = str(cb_msg.get("chat", {}).get("id", ""))

                    if cb_chat == str(chat) and cb_data:
                        print(f"Callback: {cb_data}")

                        # Route to appropriate handler
                        if cb_data.startswith("ctx_"):
                            result = handle_context_callback(cb_data, env("GAME_TITLE", ""), cb_id)
                        else:
                            result = handle_menu_callback(cb_data)

                        if result:
                            if isinstance(result, tuple):
                                response_text, action_or_markup = result
                            else:
                                response_text = result
                                action_or_markup = None

                            # Answer the callback to dismiss loading spinner
                            if response_text:
                                tg_answer_callback(cb_id, response_text[:200])

                            # If there's a keyboard markup to show, update the message
                            if isinstance(action_or_markup, dict):
                                token = env("TELEGRAM_BOT_TOKEN")
                                if token:
                                    msg_id = cb_msg.get("message_id", "")
                                    try:
                                        text = response_text if response_text else "📋 Select option:"
                                        params = {"chat_id": cb_chat, "message_id": msg_id, "text": text, "reply_markup": json.dumps(action_or_markup)}
                                        data = urllib.parse.urlencode(params).encode()
                                        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/editMessageText", data=data, method="POST")
                                        urllib.request.urlopen(req, timeout=10)
                                    except Exception as e:
                                        print(f"Menu update error: {e}")
                            elif action_or_markup == "run_pipeline":
                                tg_send("▶️ Running full pipeline...")
                                def _run():
                                    global PIPELINE_RUNNING
                                    PIPELINE_RUNNING = True
                                    try:
                                        run_pipeline()
                                    except Exception as e:
                                        tg_send(f"Pipeline error: {e}")
                                    finally:
                                        PIPELINE_RUNNING = False
                                threading.Thread(target=_run, daemon=True).start()
                            elif action_or_markup == "restart_listener":
                                tg_answer_callback(cb_id, "Restarting...")
                                tg_send("Restarting listener via systemd...")
                                subprocess.run(["systemctl", "--user", "restart", "lambda-cut-listener.service"], capture_output=True)
                            elif action_or_markup == "do_restart":
                                tg_answer_callback(cb_id, "🔄 Restarting...")
                                subprocess.run(["systemctl", "--user", "restart", "lambda-cut-listener.service"], capture_output=True)
                                sys.exit(0)
                            elif action_or_markup == "stop_pipeline":
                                global PIPELINE_STOP_REQUESTED
                                PIPELINE_STOP_REQUESTED = True
                                tg_answer_callback(cb_id, "Pipeline stop requested")
                                tg_send("Pipeline stop requested. Finishing current phase...")
                            elif action_or_markup == "proceed_to_scripts":
                                tg_answer_callback(cb_id, "✅ Proceeding to Phase 3...")
                                tg_send("▶️ Continuing to Phase 4 (Script Generation)...")
                                def _run_p3():
                                    global PIPELINE_RUNNING; PIPELINE_RUNNING = True
                                    try:
                                        run_pipeline(skip={1, 2})
                                    except Exception as e:
                                        tg_send(f"Pipeline error: {e}")
                                    finally: PIPELINE_RUNNING = False
                                threading.Thread(target=_run_p3, daemon=True).start()
                            elif action_or_markup == "cs_do_import":
                                tg_answer_callback(cb_id, "Importing...")
                                count_t, count_s = _cs_import_data()
                                tg_send(f"✅ Import complete!\n📝 {count_t} transcripts\n🎬 {count_s} shorts")
                            elif action_or_markup == "cs_do_generate":
                                tg_answer_callback(cb_id, "Generating script...")
                                def _run_cs():
                                    _cs_generate_script_only()
                                threading.Thread(target=_run_cs, daemon=True).start()
                            elif action_or_markup == "cs_do_generate_tts":
                                tg_answer_callback(cb_id, "Generating TTS...")
                                def _run_tts():
                                    _cs_generate_tts_only()
                                threading.Thread(target=_run_tts, daemon=True).start()
                            elif action_or_markup == "cs_do_clear":
                                tg_answer_callback(cb_id, "Clearing...")
                                count = _cs_clear_data()
                                tg_send(f"🗑️ Cleared {count} files from Content Studio")
                            elif isinstance(action_or_markup, dict):
                                # It's a new keyboard markup - edit the message
                                token = env("TELEGRAM_BOT_TOKEN")
                                if token and response_text:
                                    msg_id = cb_msg.get("message_id", "")
                                    try:
                                        params = {"chat_id": cb_chat, "message_id": msg_id, "text": response_text, "reply_markup": json.dumps(action_or_markup)}
                                        data = urllib.parse.urlencode(params).encode()
                                        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/editMessageText", data=data, method="POST")
                                        urllib.request.urlopen(req, timeout=10)
                                    except Exception as e:
                                        print(f"Menu update error: {e}")
                        continue

                # Handle regular message commands
                msg = upd.get("message", {})
                cid = str(msg.get("chat", {}).get("id", ""))
                txt = msg.get("text", "")
                if cid == str(chat) and txt:
                    print(f"Received: {txt}")

                    # Handle context editing flow
                    with _ctx_edit_lock:
                        has_edit_session = bool(CONTEXT_EDIT_STATE and "step" in CONTEXT_EDIT_STATE)
                    if has_edit_session:
                        result = handle_context_edit_input(txt, cid)
                        if result:
                            continue

                    process_cmd(txt, cid)
                    if LISTENER_RESTART:
                        LISTENER_RESTART = False
                        tg_send("Restarting listener via systemd...")
                        subprocess.run(["systemctl", "--user", "restart", "lambda-cut-listener.service"], capture_output=True)
                        sys.exit(0)
        except urllib.error.URLError:
            time.sleep(5)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

    tg_send("Cogitator listener stopped.")

# ─── Onboard ──────────────────────────────────────────────────────────────────
def onboard():
    G = "\033[32m"; R = "\033[31m"; Y = "\033[33m"; B = "\033[1m"; X = "\033[0m"
    ok = lambda: f"{G}\u2713{X}"
    fail = lambda: f"{R}\u2717{X}"
    warn = lambda: f"{Y}!{X}"

    print(f"\n{B}{'='*40}")
    print(f" Cogitator — Setup")
    print(f"{'='*40}{X}\n")

    # ── Installation directory ──
    print(f"{B}Installation directory{X}")
    print(f"  Default: {DEFAULT_WORKSPACE}")
    ws = input(f"  Path [{DEFAULT_WORKSPACE}]: ").strip()
    workspace = os.path.expanduser(ws) if ws else DEFAULT_WORKSPACE

    # Create directory structure
    wf_dir = os.path.join(workspace, "workflows")
    for d in (workspace, wf_dir,
              os.path.join(workspace, "streams"),
              os.path.join(workspace, "transcripts"),
              os.path.join(workspace, "scripts"),
              os.path.join(workspace, "tts"),
              os.path.join(workspace, "shorts")):
        os.makedirs(d, exist_ok=True)

    # Copy this script into the workspace
    src = os.path.abspath(__file__)
    dst = os.path.join(wf_dir, "cogitator.py")
    if src != dst:
        shutil.copy2(src, dst)
        os.chmod(dst, 0o755)
    print(f"  {ok()} Workspace: {workspace}")
    print(f"  {ok()} Script:    {dst}")

     # Update paths to use new workspace
    env_file = os.path.join(workspace, ".env")

    print()

    # Dependencies
    print(f"{B}Checking dependencies...{X}")
    missing = False
    for name, cmd in [("python3","python3"),("ffmpeg","ffmpeg"),("ffprobe","ffprobe"),
                       ("yt-dlp","yt-dlp"),("curl","curl")]:
        if shutil.which(cmd):
            try:
                v = subprocess.run([cmd,"--version"], capture_output=True, text=True)
                print(f"  {ok()} {name}  {v.stdout.splitlines()[0]}")
            except Exception:
                print(f"  {ok()} {name}")
        else:
            print(f"  {fail()} {name}  NOT FOUND")
            missing = True

    try:
        import stable_whisper  # noqa: F401
        print(f"  {ok()} stable-ts")
    except ImportError:
        print(f"  {fail()} stable-ts  (pip install stable-ts)")
        missing = True

    if missing:
        print(f"\n  {fail()} Install missing deps first.")
        print("    pip install stable-ts")
        print("    sudo apt install ffmpeg curl python3 yt-dlp")
        sys.exit(1)
    print()

    # Cookies
    print(f"{B}Checking browser cookies...{X}")
    r = subprocess.run(["yt-dlp","--cookies-from-browser","chrome","-j",
                        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
                       capture_output=True)
    if r.returncode == 0:
        print(f"  {ok()} Chrome cookies accessible")
    else:
        print(f"  {warn()} Chrome cookies not accessible.")
        print("    Make sure you're logged into YouTube in Chrome.")
        if input("  Continue? [y/N]: ").strip().lower() != "y":
            sys.exit(1)
    print()

    # Config
    existing = {}
    if os.path.exists(env_file):
        print(f"{warn()} Existing .env found.")
        if input("  Reconfigure? [y/N]: ").strip().lower() == "y":
            with open(env_file) as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        existing[k] = v.strip('"')
        else:
            print(f"  {ok()} Keeping existing .env")
            existing = None

    config = {}
    if existing is not None:
        print(f"\n{B}Configuration{X}\n")

        def ask(key, prompt, validate=None, optional=False):
            d = existing.get(key, "")
            hint = f" [{d}]" if d else ""
            while True:
                v = input(f"  {prompt}{hint}: ").strip()
                v = v or d
                if not v and optional:
                    return ""
                if not v:
                    print(f"  {fail()} Required")
                    continue
                if validate and not validate(v):
                    print(f"  {fail()} Invalid format")
                    hint = ""
                    continue
                print(f"  {ok()}")
                return v

        config["GEMINI_API_KEY"] = ask("GEMINI_API_KEY", "Primary Gemini API Key (used for TTS; more keys added below)",
            lambda v: bool(re.match(r"^AIzaSy[A-Za-z0-9_-]{33}$", v)))
        config["PLAYLIST_URL"] = ask("PLAYLIST_URL", "YouTube Playlist URL",
            lambda v: v.startswith("https://www.youtube.com/playlist?list="))

        voices = TTS_VOICES
        default_voice = existing.get("TTS_VOICE", "Vindemiatrix") or "Vindemiatrix"
        default_idx = voices.index(default_voice) + 1 if default_voice in voices else 24
        print(f"\n  TTS Voice (pick a number):")
        for i, v in enumerate(voices, 1):
            marker = f" ({'current' if v == default_voice else 'default'})" if v == default_voice else ""
            print(f"    {i:2d}. {v}{marker}")
        while True:
            choice = input(f"\n  Choice [{default_idx}]: ").strip()
            if not choice:
                config["TTS_VOICE"] = default_voice
                print(f"  {ok()}")
                break
            if choice.isdigit() and 1 <= int(choice) <= len(voices):
                config["TTS_VOICE"] = voices[int(choice) - 1]
                print(f"  {ok()}")
                break
            print(f"  {fail()} Enter a number 1-{len(voices)}")

        config["TTS_STYLE"] = ask("TTS_STYLE", "TTS Style prefix", optional=True) or existing.get("TTS_STYLE","")

        use_telegram = input(f"  Use Telegram notifications? [y/N]: ").strip().lower() == "y"
        if use_telegram:
            print(f"\n  {B}Telegram Bot Token{X}")
            print("    1. Open Telegram, search for @BotFather")
            print("    2. Send /newbot and follow the prompts")
            print("    3. Copy the token (e.g. 123456:ABC-DEF...)")
            config["TELEGRAM_BOT_TOKEN"] = ask("TELEGRAM_BOT_TOKEN", "Telegram Bot Token",
                lambda v: bool(re.match(r"^[0-9]+:[A-Za-z0-9_-]{35}$", v)))

            print(f"\n  {B}Telegram Chat ID{X}")
            print("    1. Open Telegram, search for @userinfobot")
            print("    2. Send /start")
            print("    3. It will reply with your Chat ID")
            config["TELEGRAM_CHAT_ID"] = ask("TELEGRAM_CHAT_ID", "Telegram Chat ID",
                lambda v: bool(re.match(r"^-?[0-9]+$", v)))

        # Keys
        print(f"\n{B}Gemini keys for script generation{X}")
        keys = []
        # Try to load from keychain first
        try:
            from workflows.keychain_manager import get_gemini_keys
            keys = get_gemini_keys()
        except ImportError:
            pass  # Fall back to empty list

        if config["GEMINI_API_KEY"] not in keys:
            keys.insert(0, config["GEMINI_API_KEY"])
        print(f"  Current: {len(keys)}")
        while True:
            sys.stdout.write("  Add key (Enter to skip): "); sys.stdout.flush()
            k = sys.stdin.readline().strip()
            if not k:
                break
            if re.match(r"^AIzaSy[A-Za-z0-9_-]{33}$", k):
                keys.append(k)
                print(f"  {ok()} Added ({len(keys)} total)")
            else:
                print(f"  {fail()} Invalid format")

        # Write
        print(f"\n{B}Writing configuration...{X}")
        if os.path.exists(env_file):
            shutil.copy2(env_file, env_file + ".bak")

        with open(env_file, "w") as f:
            f.write(f'WORKSPACE={workspace}\n')
            for k in ("GEMINI_API_KEY", "PLAYLIST_URL", "TTS_VOICE"):
                f.write(f'{k}={config[k]}\n')
            if use_telegram:
                for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
                    f.write(f'{k}={config[k]}\n')
            if config["TTS_STYLE"]:
                f.write(f'TTS_STYLE="{config["TTS_STYLE"]}"\n')
        os.chmod(env_file, 0o600)
        print(f"  {ok()} {env_file}")

        print(f"\n{B}Storing keys in system keychain...{X}")
        try:
            set_gemini_keys(keys)
            print(f"  {ok()} Gemini keys stored")
            set_service_password("gemini-api-key", config["GEMINI_API_KEY"])
            print(f"  {ok()} TTS API key stored")
            if use_telegram:
                set_service_password("telegram-bot-token", config["TELEGRAM_BOT_TOKEN"])
                set_service_password("telegram-chat-id", config["TELEGRAM_CHAT_ID"])
                print(f"  {ok()} Telegram keys stored")
        except Exception as e:
            print(f"  {warn()} Keychain not available: {e}")
            print(f"    Keys saved to files only")

    # Reload env — mutate shared ENV in-place to preserve the reference
    # that bot.py imported from cogitator.py (avoids split-brain)
    import workflows.cogitator as _sf
    _new_env = load_env()
    global ENV, ENV_FILE, WORKSPACE, WORKFLOW_DIR
    ENV_FILE = env_file
    WORKSPACE = workspace
    WORKFLOW_DIR = wf_dir
    ENV.clear()
    ENV.update(_new_env)
    _sf.ENV_FILE = env_file
    _sf.WORKSPACE = workspace
    _sf.WORKFLOW_DIR = wf_dir
    _sf.ENV.clear()
    _sf.ENV.update(_new_env)

    # Verify
    print(f"\n{B}Verifying connections...{X}")
    all_ok = True

    # Gemini
    sys.stdout.write("  Gemini API ... "); sys.stdout.flush()
    try:
        api_key = env("GEMINI_API_KEY")
        body = json.dumps({"contents":[{"parts":[{"text":"hi"}]}],
                           "generationConfig":{"maxOutputTokens":5}}).encode()
        req = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent",
            data=body, headers={"Content-Type":"application/json",
                                "X-Goog-Api-Key": api_key})
        r = urllib.request.urlopen(req, timeout=15)
        json.loads(r.read())
        print(f"{ok()} OK")
    except Exception:
        print(f"{fail()} Failed")
        all_ok = False

    # Telegram
    if _telegram_configured():
        sys.stdout.write("  Telegram bot ... "); sys.stdout.flush()
        try:
            r = urllib.request.urlopen(
                f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}/getMe", timeout=10)
            name = json.loads(r.read())["result"]["username"]
            print(f"{ok()} @{name}")
        except Exception:
            print(f"{fail()} Failed")
            all_ok = False

        # Chat
        sys.stdout.write("  Telegram chat ... "); sys.stdout.flush()
        try:
            data = urllib.parse.urlencode({
                "chat_id": env("TELEGRAM_CHAT_ID"),
                "text": "Cogitator configured!"
            }).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}/sendMessage",
                data=data, method="POST")
            urllib.request.urlopen(req, timeout=10)
            print(f"{ok()} Message sent")
        except Exception:
            print(f"{fail()} Cannot send to chat")
            all_ok = False
    else:
        print(f"  {warn()} Telegram not configured (notifications disabled)")

    # Playlist
    sys.stdout.write("  YouTube playlist ... "); sys.stdout.flush()
    r = subprocess.run(["yt-dlp","--flat-playlist","--playlist-items","1","-j",
                        env("PLAYLIST_URL")], capture_output=True)
    if r.returncode == 0:
        try:
            title = json.loads(r.stdout).get("title","?")
            print(f"{ok()} \"{title}\"")
        except Exception:
            print(f"{ok()} Accessible")
    else:
        print(f"{fail()} Cannot access")
        all_ok = False

    # Make scripts executable
    for s in ("cogitator.py",):
        p = os.path.join(WORKFLOW_DIR, s)
        if os.path.exists(p):
            os.chmod(p, 0o755)

    print()
    if all_ok:
        print(f"{B}{'='*40}")
        print(" All checks passed! You're ready.")
        print(f"{'='*40}{X}\n")

        # Optional: systemd service
        svc_dir  = os.path.expanduser("~/.config/systemd/user")
        svc_file = os.path.join(svc_dir, "lambda-cut-listener.service")
        svc_name = "lambda-cut-listener.service"

        if input(f"  Set up Telegram listener as background service? [y/N]: ").strip().lower() == "y":
            os.makedirs(svc_dir, exist_ok=True)
            python = sys.executable
            svc = f"""[Unit]
Description=Cogitator Telegram Listener
After=network.target

[Service]
Type=simple
ExecStartPre=/bin/sleep 10
ExecStart={python} {dst} listen
WorkingDirectory={WORKSPACE}
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
"""
            with open(svc_file, "w") as f:
                f.write(svc)
            run(["systemctl", "--user", "daemon-reload"])
            run(["systemctl", "--user", "enable", svc_name])
            run(["systemctl", "--user", "start", svc_name])
            print(f"  {ok()} Listener running as background service.")
            print(f"    Status:  systemctl --user status {svc_name}")
            print(f"    Stop:    systemctl --user stop {svc_name}")
            print(f"    Disable: systemctl --user disable {svc_name}\n")
        else:
            # Clean up old sophia-listener if present
            old_svc = os.path.join(svc_dir, "sophia-listener.service")
            if os.path.exists(old_svc):
                run(["systemctl", "--user", "stop", "sophia-listener.service"], check=False)
                run(["systemctl", "--user", "disable", "sophia-listener.service"], check=False)
                print(f"  {ok()} Disabled old sophia-listener service.\n")
            print("  Start bot manually when needed:")
            print(f"    python3 {dst} listen\n")

        # Shell alias
        if input("  Set up alias so you can run `COGITATOR` from anywhere? [y/N]: ").strip().lower() == "y":
            alias_line = f"alias COGITATOR='python3 {dst}'"

            # Detect shell rc file
            shell = os.environ.get("SHELL", "")
            rc_candidates = []
            if "zsh" in shell:
                rc_candidates = [os.path.expanduser("~/.zshrc")]
            elif "bash" in shell:
                rc_candidates = [os.path.expanduser("~/.bashrc")]
            else:
                rc_candidates = [os.path.expanduser("~/.bashrc"), os.path.expanduser("~/.zshrc")]

            # Find which rc files exist
            existing_rcs = [rc for rc in rc_candidates if os.path.exists(rc)]
            if not existing_rcs:
                # Create the first candidate
                rc_file = rc_candidates[0]
            elif len(existing_rcs) == 1:
                rc_file = existing_rcs[0]
            else:
                print(f"    Multiple shell configs found:")
                for i, rc in enumerate(existing_rcs, 1):
                    print(f"      {i}. {rc}")
                choice = input("    Which one? [1]: ").strip()
                idx = int(choice) - 1 if choice.isdigit() and 0 < int(choice) <= len(existing_rcs) else 0
                rc_file = existing_rcs[idx]

            # Check if alias already exists
            alias_exists = False
            if os.path.exists(rc_file):
                with open(rc_file) as f:
                    for line in f:
                        if line.strip().startswith("alias COGITATOR="):
                            alias_exists = True
                            break

            if alias_exists:
                print(f"  {warn()} Alias already exists in {rc_file}")
            else:
                with open(rc_file, "a") as f:
                    f.write(f"\n# Cogitator\n{alias_line}\n")
                print(f"  {ok()} Alias added to {rc_file}")
                print(f"    Run: source {rc_file}")
                print(f"    Or open a new terminal.\n")

            print(f"  {B}Ready!{X}")
            print(f"    COGITATOR run")
            print(f"    COGITATOR run -phase 2,3")
            print(f"    COGITATOR listen\n")
        else:
            print(f"  {B}Ready!{X}")
            print(f"    python3 {dst} run")
            print(f"    python3 {dst} run -phase 2,3")
            print(f"    python3 {dst} listen\n")

    else:
        print(f"{B}{'='*40}")
        print(" Some checks failed. Fix and re-run.")
        print(f"{'='*40}{X}\n")

# ─── Config check ─────────────────────────────────────────────────────────────
REQUIRED_KEYS = ("GEMINI_API_KEY", "PLAYLIST_URL")

def _check_configured():
    """Return True if .env exists and all required keys have real values."""
    if not os.path.exists(ENV_FILE):
        return False
    for key in REQUIRED_KEYS:
        val = env(key)
        if not val:
            return False
    return True

def _telegram_configured():
    return bool(env("TELEGRAM_BOT_TOKEN")) and bool(env("TELEGRAM_CHAT_ID"))

# ─── CLI ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(prog="COGITATOR", description="Cogitator — YouTube Shorts Pipeline")
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="Run the pipeline")
    p_run.add_argument("-phase", type=str, help="Run only phases (e.g. 2,3)")
    p_run.add_argument("-index", type=int, help="Playlist index to download (default: 1)")
    p_run.add_argument("-skip-phase-1", action="store_true")
    p_run.add_argument("-skip-phase-2", action="store_true")
    p_run.add_argument("-skip-phase-4", action="store_true")
    p_run.add_argument("-skip-phase-5", action="store_true")
    p_run.add_argument("-skip-phase-6", action="store_true")
    p_run.add_argument("-skip-all", action="store_true")

    p_local = sub.add_parser("run_local", help="Run pipeline on local recordings")
    p_local.add_argument("path", type=str, nargs="?", help="Path to local recordings directory (default: media)")

    p_download = sub.add_parser("download", help="Download video from URL")
    p_download.add_argument("-url", type=str, required=True, help="URL to download (video or playlist)")

    sub.add_parser("listen", help="Start Telegram bot listener")

    p_stop = sub.add_parser("stop", help="Stop the listener")
    p_stop.add_argument("--pipeline", action="store_true", help="Stop the running pipeline instead")

    sub.add_parser("delete-partial", help="Delete incomplete files")
    sub.add_parser("cleanup", help="Delete all generated files")
    sub.add_parser("clear-logs", help="Clear pipeline logs")
    sub.add_parser("onboard", help="Interactive setup wizard")

    args = parser.parse_args()

    if args.command == "run":
        if not _check_configured():
            print("Configuration missing or incomplete.")
            print(f"  .env: {ENV_FILE}")
            print(f"  Run onboarding first:  python3 {__file__} onboard")
            sys.exit(1)

        skip = set()
        if args.skip_all:
            skip = {1,2,3,4,5,6}
        else:
            if args.skip_phase_1: skip.add(1)
            if args.skip_phase_2: skip.add(2)
            if args.skip_phase_4: skip.add(3)
            if args.skip_phase_5: skip.add(4)
            if args.skip_phase_6: skip.add(5)

        playlist_index = None
        if args.index:
            playlist_index = str(args.index)
            update_env_var("PLAYLIST_INDEX", playlist_index)

        run_pipeline(skip=skip)

    elif args.command == "run_local":
        if not _check_configured():
            print("Configuration missing or incomplete.")
            print(f"  .env: {ENV_FILE}")
            print(f"  Run onboarding first:  python3 {__file__} onboard")
            sys.exit(1)

        path = args.path if args.path else MEDIA_DIR
        if not os.path.exists(path):
            print(f"Error: Path does not exist: {path}")
            sys.exit(1)

        run_local_recordings(path)

    elif args.command == "download":
        if not _check_configured():
            print("Configuration missing or incomplete.")
            print(f"  .env: {ENV_FILE}")
            print(f"  Run onboarding first:  python3 {__file__} onboard")
            sys.exit(1)

        url = args.url
        if not url:
            print("Error: No URL provided")
            sys.exit(1)

        success = download_from_url(url)
        sys.exit(0 if success else 1)

    elif args.command == "listen":
        listen()

    elif args.command == "stop":
        if args.pipeline:
            if PIPELINE_RUNNING:
                global PIPELINE_STOP_REQUESTED
                PIPELINE_STOP_REQUESTED = True
                print("Stop requested for pipeline.")
            else:
                print("No pipeline is currently running.")
        else:
            if os.path.exists(PID_FILE):
                with open(PID_FILE) as f:
                    pid = int(f.read().strip())
                try:
                    os.kill(pid, 0)
                    os.kill(pid, 15)
                    print(f"Sent stop signal to listener (PID {pid})")
                    os.remove(PID_FILE)
                except ProcessLookupError:
                    print("Listener not running.")
                    os.remove(PID_FILE)
                except PermissionError:
                    print("Cannot stop listener (permission denied).")
            else:
                print("No listener running (PID file not found).")

    elif args.command == "delete-partial":
        count = delete_partial_files()
        print(f"Deleted {count} partial file(s).")

    elif args.command == "cleanup":
        count = cleanup_all_files()
        print(f"Deleted {count} file(s) from all output directories.")

    elif args.command == "clear-logs":
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "w") as f:
                f.write("")
            print("Pipeline logs cleared.")
        else:
            print("No logs to clear.")

    elif args.command == "onboard":
        onboard()

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
