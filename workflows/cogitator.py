#!/usr/bin/env python3
"""
Cogitator — YouTube Shorts Pipeline
Combines: cogitator.sh, generate_script.sh, onboard.sh
"""
import argparse, base64, datetime, gc, glob, json, os, random, re, shutil, subprocess, sys, threading, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta

_workflow_dir = os.path.dirname(os.path.abspath(__file__))
_workspace = os.path.dirname(_workflow_dir)
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)
from workflows.context_utils import _cs_load_context
from workflows.title_variety import (
    build_title_guidance,
    enforce_title_variety,
    format_recent_for_prompt,
    load_historical_titles,
    normalize_title,
)

from update_manager import (
    get_local_version,
    get_release_notes,
    check_for_updates,
    perform_update,
    cleanup_old_backups,
)
from workflows.constants import TTS_VOICES, TTS_STYLE_OPTIONS, calculate_performance_score, parse_duration, get_next_groq_key, dedupe_entity_list, fuzzy_dedup_against_list, CONTEXT_DIR
from workflows.core.round_robin import init_round_robin, get_next_variant_perspective, get_next_voice_style, reset as reset_round_robin, get_state as _rr_get_state
from workflows.performance_database import (
    store_script,
    backfill_script_titles,
)
from workflows.keychain_manager import (
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
    # Fallback function when MemPalace is not available
    def get_mempalace_manager():
        """Fallback when MemPalace is not available."""
        return None  # type: ignore
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
    from workflows.performance_database import (
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
    from workflows.learning_engine import (
        extract_script_features,
        calculate_virality_score,
        analyze_performance_patterns,
        get_optimized_params,
        get_learned_hook_examples,
    )
    LEARNING_ENGINE_AVAILABLE = True
except ImportError:
    LEARNING_ENGINE_AVAILABLE = False
    def extract_script_features(*args, **kwargs): return {}
    def calculate_virality_score(*args, **kwargs): return 50.0
    def analyze_performance_patterns(*args, **kwargs): return {}
    def get_optimized_params(*args, **kwargs): return {}
    def get_learned_hook_examples(*args, **kwargs): return []

try:
    from audio_analysis import enhance_scene_selection
    AUDIO_ANALYSIS_AVAILABLE = True
except ImportError:
    AUDIO_ANALYSIS_AVAILABLE = False
    def enhance_scene_selection(*args, **kwargs): return args[0] if args else []

from workflows.context_manager_v2 import (
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
from workflows.context_utils import merge_context_dicts
import requests
from jinja2 import Environment, FileSystemLoader, BaseLoader
try:
    from rapidfuzz import fuzz as _fuzz
except ImportError:
    _fuzz = None

# Groq configuration
GROQ_KEY_INDEX = 0  # Track which Groq key to use next
GEMINI_KEY_INDEX = 0  # Track which Gemini key to use next
GROQ_MODEL = "llama-3.3-70b-versatile"

# Dynamic model selection per content type
GROQ_MODELS_BY_TYPE = {
    "mystery_recap": "llama-3.3-70b-versatile",
    "breakdown": "llama-3.3-70b-versatile",
    "timeline": "llama-3.3-70b-versatile",
    "lesson": "llama-3.3-70b-versatile",
    "narrative": "llama-3.3-70b-versatile",
    "news_report": "llama-3.3-70b-versatile",
    "documentary": "llama-3.3-70b-versatile",
    "true_crime": "llama-3.3-70b-versatile",
    "character_pov": "llama-3.3-70b-versatile",
    "true_story": "llama-3.3-70b-versatile",
}

# Adaptive temperature per content type
TEMPERATURE_BY_TYPE = {
    "mystery_recap": 0.8,
    "breakdown": 0.6,
    "timeline": 0.7,
    "lesson": 0.7,
    "narrative": 0.8,
    "news_report": 0.5,
    "documentary": 0.5,
    "true_crime": 0.8,
    "character_pov": 0.9,
    "true_story": 0.7,
}

LLM_PARAMS_BY_TYPE = {
    "mystery_recap":    {"top_p": 0.90, "repetition_penalty": 1.1},
    "breakdown":        {"top_p": 0.80, "repetition_penalty": 1.2},
    "timeline":         {"top_p": 0.90, "repetition_penalty": 1.0},
    "lesson":           {"top_p": 0.90, "repetition_penalty": 1.1},
    "narrative":        {"top_p": 0.95, "repetition_penalty": 1.0},
    "news_report":      {"top_p": 0.85, "repetition_penalty": 1.3},
    "documentary":      {"top_p": 0.85, "repetition_penalty": 1.2},
    "true_crime":       {"top_p": 0.90, "repetition_penalty": 1.1},
    "character_pov":    {"top_p": 0.95, "repetition_penalty": 1.0},
    "true_story":       {"top_p": 0.90, "repetition_penalty": 1.1},
}

def _get_llm_params(variant_key):
    base = LLM_PARAMS_BY_TYPE.get(variant_key, {})
    return {
        "top_p": base.get("top_p", 0.9),
        "repetition_penalty": base.get("repetition_penalty", 1.1),
    }

# ─── Paths ────────────────────────────────────────────────────────────────────
DEFAULT_WORKSPACE = os.path.expanduser("~/Cogitator")

def _find_workspace():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith("WORKSPACE="):
                    return line.strip().split("=", 1)[1].strip().strip('"')
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WORKSPACE    = _find_workspace()
WORKFLOW_DIR = os.path.join(WORKSPACE, "workflows")
ENV_FILE     = os.path.join(WORKSPACE, ".env")
LOG_FILE     = os.path.join(WORKSPACE, "pipeline.log")
METRICS_FILE = os.path.join(WORKSPACE, "generation_metrics.jsonl")
STATUS_FILE  = os.path.join(os.path.expanduser("~/.cogitator"), "pipeline_status")
LAST_CALL    = os.path.join(os.path.expanduser("~/.cogitator"), "gemini_last_call.txt")


TRANSCRIPTS_DIR  = os.path.join(WORKSPACE, "transcripts")
SCRIPTS_DIR      = os.path.join(WORKSPACE, "scripts")
TTS_DIR          = os.path.join(WORKSPACE, "tts")
SHORTS_DIR       = os.path.join(WORKSPACE, "shorts")
ASSEMBLY_DIR     = os.path.join(WORKSPACE, "assembly")
OUTPUT_DIR       = os.path.join(WORKSPACE, "output")

# Media import directory (for local videos)
MEDIA_DIR        = os.path.join(WORKSPACE, "media")

# Prompt templates directory
PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prompts")
if not os.path.exists(PROMPTS_DIR):
    PROMPTS_DIR = os.path.join(WORKSPACE, "prompts")

# ── ASR Error Corrector ───────────────────────────────────────────────────────
_ASR_CORRECTIONS = {
    # Cyberpunk 2077 specific ASR errors
    "cyber cycle": "cyberpsycho",
    "cyper cycle": "cyberpsycho", 
    "cypre cycle": "cyberpsycho",
    "cycle": "cyberpsycho",
    "cycles": "cyberpsycho",
    # Other common gaming terms
    "n c p d": "NCPD",
    "n cpd": "NCPD",
    "cpd": "NCPD",
}

def _correct_transcript_asr_errors(json_path):
    """Post-process transcript to fix known ASR errors for gaming content."""
    if not os.path.exists(json_path):
        return
    
    try:
        import json, re
        with open(json_path, "r") as f:
            data = json.load(f)

        corrections = dict(_ASR_CORRECTIONS)
        # Inject verified entity names as preferred spellings (glossary)
        try:
            from workflows.context_manager_v2 import load_verified_context
            verified = load_verified_context(env("GAME_TITLE", ""))
            for key in ("characters", "locations", "key_terms"):
                for item in (verified or {}).get(key, []) or []:
                    name = item.get("name") or item.get("term") if isinstance(item, dict) else str(item)
                    if not name or len(name) < 3:
                        continue
                    # Prefer canonical casing when ASR produces lowercase/spaced variants
                    spaced = " ".join(list(name.replace(" ", "")))  # letter-spaced e.g. N C P D
                    if len(name.replace(" ", "")) <= 6 and name.isupper():
                        corrections.setdefault(spaced.lower(), name)
                    corrections.setdefault(name.lower(), name)
            aliases = {}
            # character_aliases from raw file via _cs_load_context
            ctx = _cs_load_context()
            for variant, canonical in (ctx.get("character_aliases") or {}).items():
                if variant and canonical:
                    corrections[str(variant).lower()] = canonical
            for variant, canonical in (ctx.get("location_aliases") or {}).items():
                if variant and canonical:
                    corrections[str(variant).lower()] = canonical
        except Exception:
            pass
        
        corrections_made = 0
        # Apply longer keys first to avoid partial replacements
        ordered = sorted(corrections.items(), key=lambda kv: len(kv[0]), reverse=True)
        for seg in data.get("segments", []):
            original = seg.get("text", "")
            corrected = original
            for wrong, right in ordered:
                corrected = re.sub(rf'\b{re.escape(wrong)}\b', right, corrected, flags=re.IGNORECASE)
            
            if corrected != original:
                seg["text"] = corrected
                corrections_made += 1
        
        if corrections_made > 0:
            with open(json_path, "w") as f:
                json.dump(data, f)
            log(f"   Corrected {corrections_made} ASR errors in transcript")
    except Exception as e:
        log(f"   ASR error correction failed: {e}")

# Jinja2 template environment
_prompt_env = None

def _get_prompt_env():
    """Lazy-load Jinja2 template environment."""
    global _prompt_env
    if _prompt_env is None and os.path.exists(PROMPTS_DIR):
        _prompt_env = Environment(
            loader=FileSystemLoader(PROMPTS_DIR),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _prompt_env

# Content Studio directories
CONTENT_STUDIO_DIR = os.path.join(WORKSPACE, "content_studio")
CS_TRANSCRIPTS_DIR = os.path.join(CONTENT_STUDIO_DIR, "transcripts")
CS_SHORTS_DIR      = os.path.join(CONTENT_STUDIO_DIR, "shorts")
CS_SCRIPTS_DIR     = os.path.join(CONTENT_STUDIO_DIR, "scripts")
CS_TTS_DIR         = os.path.join(CONTENT_STUDIO_DIR, "tts")

# Get game-specific context file based on current game title (called at runtime)
def get_cs_context_file():
    """Get the context file path for current game."""
    game_title = env("GAME_TITLE", "default")
    game_key = game_title.lower().replace(" ", "_")
    game_dir = os.path.join(CONTEXT_DIR, game_key)
    os.makedirs(game_dir, exist_ok=True)
    return os.path.join(game_dir, "context.json")

# CS_CONTEXT_FILE will be set after env() is defined - use a lazy approach
CS_CONTEXT_FILE = None  # Will be set lazily

PIPELINE_RUNNING = False
PIPELINE_STOP_REQUESTED = False  # set True to request pipeline stop
_SCRIPT_ID_MAP = {}
import threading
_pipeline_lock = threading.Lock()
_script_id_map_lock = threading.Lock()

def get_pipeline_stop_requested():
    with _pipeline_lock:
        return PIPELINE_STOP_REQUESTED

def set_pipeline_stop_requested(val):
    global PIPELINE_STOP_REQUESTED
    with _pipeline_lock:
        PIPELINE_STOP_REQUESTED = val

def get_pipeline_running():
    with _pipeline_lock:
        return PIPELINE_RUNNING

def set_pipeline_running(val):
    global PIPELINE_RUNNING
    with _pipeline_lock:
        PIPELINE_RUNNING = val

def set_script_id(idx, script_id):
    with _script_id_map_lock:
        _SCRIPT_ID_MAP[idx] = script_id

def get_script_id_map():
    with _script_id_map_lock:
        return dict(_SCRIPT_ID_MAP)

def clear_script_id_map():
    with _script_id_map_lock:
        _SCRIPT_ID_MAP.clear()
_pipeline_globals_lock = threading.Lock()

# Learning state (refreshed at pipeline start)
_LEARNING_BASELINE = {}
_LEARNING_VARIANT_WEIGHTS = {}
_LEARNING_VARIANT_STATS = {}
_LEARNING_TTS_WEIGHTS = []
_LEARNING_OPTIMIZED_PARAMS = {}

# A/B test state (refreshed at pipeline start)
_CURRENT_AB_TEST = None

# Context editing state
CONTEXT_EDIT_STATE = {}
_ctx_edit_lock = threading.Lock()

# Shared state between phases (used for linking clips to scripts in DB)
clear_script_id_map()  # {script_hour_index: script_id}


def _clear_shared_state():
    """Clear shared state between phase runs."""
    global _SCRIPT_ID_MAP
    clear_script_id_map()
    reset_round_robin()


def _refresh_learning_state():
    """Refresh all learning state from DB at pipeline start.

    This is the feedback loop trigger - it reads YouTube performance data
    and makes it available to all downstream decisions. Also pulls fresh
    metrics from YouTube before reading.
    """
    global _LEARNING_BASELINE, _LEARNING_VARIANT_WEIGHTS, _LEARNING_VARIANT_STATS
    global _LEARNING_TTS_WEIGHTS, _LEARNING_OPTIMIZED_PARAMS, _SCRIPT_ID_MAP
    global _CURRENT_AB_TEST
    _clear_shared_state()

    if not PERFORMANCE_DB_AVAILABLE:
        return

    try:
        oauth_file = os.path.join(WORKSPACE, ".cogitator", "youtube_oauth.json")
        if os.path.exists(oauth_file):
            try:
                from workflows.performance_database import sync_youtube_metrics
                log("[LEARNING] Syncing YouTube metrics...")
                result = sync_youtube_metrics(days=30, max_results=50)
                log(f"[LEARNING] YouTube sync: {result.get('matched_count', 0)} matched, {result.get('new_metrics', 0)} new metrics")
            except Exception as sync_err:
                log(f"[LEARNING] YouTube sync skipped: {sync_err}")

        _LEARNING_BASELINE = get_channel_baseline()
        _LEARNING_VARIANT_WEIGHTS = get_learned_variant_weights(min_samples=3)
        _LEARNING_VARIANT_STATS = get_variant_performance_stats()
        _LEARNING_TTS_WEIGHTS = get_weighted_tts_voices()

        # Initialize A/B test for this pipeline run
        try:
            from workflows.performance_database import get_or_create_ab_test
            _CURRENT_AB_TEST = get_or_create_ab_test()
            if _CURRENT_AB_TEST:
                log(f"[A/B] Active test: {_CURRENT_AB_TEST['test_name']} (ID: {_CURRENT_AB_TEST['test_id'][:8]}...)")
            else:
                log("[A/B] No active test")
        except Exception as ab_err:
            log(f"[A/B] Failed to initialize: {ab_err}")
            _CURRENT_AB_TEST = None

        try:
            from workflows.learning_engine import get_optimized_params, analyze_performance_patterns
            from workflows.performance_database import get_learnings as pdb_get_learnings
            learnings = pdb_get_learnings()
            _LEARNING_OPTIMIZED_PARAMS = get_optimized_params(learnings, _LEARNING_BASELINE)
        except Exception:
            _LEARNING_OPTIMIZED_PARAMS = {}

        # Analyze performance patterns and wire up learning feedback
        try:
            from workflows.performance_database import get_successful_scripts
            successful = get_successful_scripts(limit=20)
            if len(successful) >= 3:
                startup_metrics = getattr(_refresh_learning_state, '_metrics_cache', [])
                analysis = analyze_performance_patterns(successful, startup_metrics)
                if analysis and analysis.get('confidence', 0) >= 0.3:
                    log(f"[LEARNING] Pattern analysis: {analysis.get('sample_count', 0)} scripts, confidence {analysis.get('confidence', 0):.0%}")
        except Exception:
            pass

        # Train virality model if enough samples
        try:
            from workflows.learning_engine import train_virality_model
            from workflows.performance_database import get_successful_scripts as _gss
            all_scripts = _gss(limit=50)
            if len(all_scripts) >= 5:
                result = train_virality_model(all_scripts)
                if result.get('success'):
                    top_features = result.get('top_features', [])
                    if top_features:
                        log(f"[LEARNING] Virality model trained ({result.get('sample_count', 0)} samples). Top features: {top_features[:3]}")
        except Exception:
            pass

        sample_count = _LEARNING_BASELINE.get('sample_count', 0)
        log(f"[LEARNING] Refreshed: {sample_count} samples, {len(_LEARNING_VARIANT_WEIGHTS)} weighted variants, {len(_LEARNING_TTS_WEIGHTS)} TTS combos")
    except Exception as e:
        log(f"[LEARNING] Refresh failed: {e}")


def _get_variant_weight(variant_key):
    """Get the weight multiplier for a variant based on performance."""
    return _LEARNING_VARIANT_WEIGHTS.get(variant_key, 1.0)


def _init_round_robin(num_scripts):
    """Initialize round-robin lists - learning-weighted once per pipeline run."""
    init_round_robin(
        num_scripts=num_scripts,
        variant_keys=list(SCRIPT_VARIANTS.keys()),
        perspectives=list(SCRIPT_PERSPECTIVES),
        variant_weights=_LEARNING_VARIANT_WEIGHTS,
        tts_weights=_LEARNING_TTS_WEIGHTS,
    )
    log(f"[LEARNING] Round-robin: {len(SCRIPT_VARIANTS)} variants, {len(TTS_VOICES)*len(TTS_STYLE_OPTIONS)} TTS combos")

def _get_next_round_robin():
    """Get next round-robin item and advance index."""
    return get_next_variant_perspective(list(SCRIPT_VARIANTS.keys()), list(SCRIPT_PERSPECTIVES))

# ─── Environment ──────────────────────────────────────────────────────────────
def load_env():
    env = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k] = v.strip('"').strip("'")
    return env

ENV = load_env()
os.environ.update({k: v for k, v in ENV.items() if v is not None})

def env(key, default=""):
    keychain_map = {
        "GEMINI_API_KEY": "gemini-api-key",
    }
    if key in keychain_map:
        keychain_key = keychain_map[key]
        keychain_value = get_service_password(keychain_key)
        if keychain_value:
            return keychain_value
    val = ENV.get(key, default)
    return val if val != "" else default

# ─── Logging ──────────────────────────────────────────────────────────────────
def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass

def log_error(msg):
    log(f"ERROR: {msg}")

def set_status(msg):
    try:
        with open(STATUS_FILE, "w") as f:
            f.write(msg)
    except OSError:
        pass

def set_progress(phase_num, percent, label):
    if percent < 0:
        percent = 0
    elif percent > 100:
        percent = 100
    set_status(f"Phase {phase_num}: {label} ({percent}%)")

# ─── Notifications ─────────────────────────────────────────────────────────────
def log_notification(msg):
    """Log a notification message."""
    log(f"[NOTIFICATION] {msg}")

def notify(msg):
    """Send a notification (always logs, no external services)."""
    log_notification(msg)


# ─── Context Confirmation Functions ────────────────────────────────────────────

def send_context_confirmation(game_title, extracted, verified, comparison):
    """Send context confirmation request via Web UI."""
    # Auto-approve without waiting - context syncs to MemPalace for learning
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
            # Show full context
            print("\n--- Full Context ---")
            print(formatted)
            print("--- End ---\n")
        else:
            print("Invalid choice. Please enter a, c, or v")


def handle_context_callback(callback_data, game_title, cb_id):
    """Handle context confirmation callback."""
    from workflows.context_manager_v2 import save_verified_context, load_verified_context, compare_context_with_history
    global CONTEXT_EDIT_STATE
    
    log(f"[DEBUG] handle_context_callback: checking CONTEXT_EDIT_STATE")
    log(f"[DEBUG] handle_context_callback: {callback_data}")
    log(f"[DEBUG] handle_context_callback: CONTEXT_EDIT_STATE = {CONTEXT_EDIT_STATE}")
    
    log(f"[DEBUG] ctx_edit flow - CONTEXT_EDIT_STATE: {CONTEXT_EDIT_STATE}")
    # Edit context - start editing session with inline submenu
    
    if callback_data.startswith("ctx_approve_"):
        # Approve and save verified context
        from workflows.context_manager_v2 import save_verified_context
        from workflows.context_manager_v2 import compare_context_with_history
        
        # Get extracted context from current run
        extracted = _cs_load_context()
        verified = load_verified_context(game_title)
        comparison = compare_context_with_history(game_title, extracted)
        
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
        
        # Store editing state (clear+update to preserve dict reference)
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
        with _ctx_edit_lock:
            state = dict(CONTEXT_EDIT_STATE)
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
        with _ctx_edit_lock:
            state = dict(CONTEXT_EDIT_STATE)
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
        with _ctx_edit_lock:
            state = dict(CONTEXT_EDIT_STATE)
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
                label = f"{rel.get('from', '')} ↔ {rel.get('to', '')}: {rel.get('relationship', '')}"
            else:
                label = str(rel)
            keyboard["inline_keyboard"].append([{"text": f"❌ {label[:30]}", "callback_data": f"ctx_rem_rel_{i}"}])
        
        keyboard["inline_keyboard"].append([{"text": "+ Add Relationship", "callback_data": "ctx_add_rel"}])
        keyboard["inline_keyboard"].append([{"text": "⬅️ Back", "callback_data": "ctx_edit_back"}])
        
        return f"👥 Relationships ({len(rels)}):\n\nSelect to remove:", keyboard
    
    elif callback_data == "ctx_edit_done":
        # Save and proceed
        with _ctx_edit_lock:
            state = dict(CONTEXT_EDIT_STATE)
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
        with _ctx_edit_lock:
            state = dict(CONTEXT_EDIT_STATE)
        if not state or "extracted" not in state:
            return "⚠️ No editing session active."
        
        chars = state.get("extracted", {}).get("characters", [])
        removed = None
        if 0 <= idx < len(chars):
            removed = chars.pop(idx)
            log_notification(f"Removed {removed}")
        
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


# Store pending context for confirmation
PENDING_CONTEXT = {}

def handle_context_edit_input(txt, chat_id):
    """Handle context editing flow via Web UI."""
    global CONTEXT_EDIT_STATE
    
    with _ctx_edit_lock:
        step = CONTEXT_EDIT_STATE.get("step", "")
        state = CONTEXT_EDIT_STATE
    
    if step == "choose_field":
        if txt == "1":
            # Edit characters
            chars = state.get("extracted", {}).get("characters", [])
            with _ctx_edit_lock:
                state["step"] = "edit_characters"
                state["current_items"] = chars
                CONTEXT_EDIT_STATE.update(state)
            
            items = "\n".join([f"{i+1}. {c}" for i, c in enumerate(chars)])
            log_notification(f"📝 Current Characters:\n{items}\n\nEnter the number to remove, or type a name to add:")
            return True
            
        elif txt == "2":
            # Edit locations
            locs = state.get("extracted", {}).get("locations", [])
            with _ctx_edit_lock:
                state["step"] = "edit_locations"
                state["current_items"] = locs
                CONTEXT_EDIT_STATE.update(state)
            
            items = "\n".join([f"{i+1}. {l}" for i, l in enumerate(locs)])
            log_notification(f"📍 Current Locations:\n{items}\n\nEnter the number to remove, or type a name to add:")
            return True
            
        elif txt == "3":
            # Edit relationships
            rels = state.get("extracted", {}).get("relationships", [])
            with _ctx_edit_lock:
                state["step"] = "edit_relationships"
                state["current_items"] = rels
                CONTEXT_EDIT_STATE.update(state)
            
            items = "\n".join([f"{i+1}. {r}" for i, r in enumerate(rels[:10])])
            log_notification(f"👥 Current Relationships:\n{items}\n\nEnter the number to remove, or type in format 'Name1 -> Name2: relationship' to add:")
            return True
        else:
            log_notification("Invalid choice. Reply with 1, 2, or 3")
            return True
            
    elif step == "edit_characters":
        # Check if number (remove) or name (add)
        if txt.isdigit():
            idx = int(txt) - 1
            items = state.get("current_items", [])
            if 0 <= idx < len(items):
                removed = items.pop(idx)
                state["current_items"] = items
                log_notification(f"✅ Removed: {removed}")
            else:
                log_notification("Invalid number")
        else:
            # Add new character
            items = state.get("current_items", [])
            items.append(txt)
            state["current_items"] = items
            log_notification(f"✅ Added: {txt}")
        
        with _ctx_edit_lock:
            state["extracted"]["characters"] = items
            CONTEXT_EDIT_STATE.update(state)
        log_notification("Done editing? Reply 'done' to save, or continue editing.")
        return True
        
    elif step == "edit_locations":
        if txt.isdigit():
            idx = int(txt) - 1
            items = state.get("current_items", [])
            if 0 <= idx < len(items):
                removed = items.pop(idx)
                state["current_items"] = items
                log_notification(f"✅ Removed: {removed}")
            else:
                log_notification("Invalid number")
        else:
            items = state.get("current_items", [])
            items.append(txt)
            state["current_items"] = items
            log_notification(f"✅ Added: {txt}")
        
        with _ctx_edit_lock:
            state["extracted"]["locations"] = items
            CONTEXT_EDIT_STATE.update(state)
        log_notification("Done editing? Reply 'done' to save, or continue editing.")
        return True
        
    elif step == "edit_relationships":
        if txt.isdigit():
            idx = int(txt) - 1
            items = state.get("current_items", [])
            if 0 <= idx < len(items):
                removed = items.pop(idx)
                state["current_items"] = items
                log_notification(f"✅ Removed: {removed}")
            else:
                log_notification("Invalid number")
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
                log_notification(f"✅ Added: {char1} -> {char2}: {rel}")
            except Exception:
                log_notification("Invalid format. Use: Name1 -> Name2: relationship")
        else:
            log_notification("Invalid. Enter number to remove, or 'Name1 -> Name2: relationship' to add")
        
        items = state.get("current_items", [])
        with _ctx_edit_lock:
            state["extracted"]["relationships"] = items
            CONTEXT_EDIT_STATE.update(state)
        log_notification("Done editing? Reply 'done' to save, or continue editing.")
        return True
        
    elif txt.lower() == "done":
        # Save the edited context
        game_title = state.get("game_title", env("GAME_TITLE", ""))
        extracted = state.get("extracted", {})
        
        # Save as verified
        save_verified_context(game_title, extracted)
        
        with _ctx_edit_lock:
            CONTEXT_EDIT_STATE.clear()
        log_notification(f"✅ Context saved for {game_title}!\n\nRun Phase 2 to verify, then Phase 4 for scripts.")
        return True
        
    elif txt.lower() == "cancel":
        with _ctx_edit_lock:
            CONTEXT_EDIT_STATE.clear()
        log_notification("❌ Edit cancelled.")
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
    
    log(f"Context files updated from Web UI edit")


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
    from workflows.context_manager_v2 import load_verified_context
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
    """Deprecated: Obsidian vault removed. Reloads verified JSON context."""
    ctx = _cs_load_context()
    game = env("GAME_TITLE", "Unknown")
    chars = len(ctx.get("characters", []))
    locs = len(ctx.get("locations", []))
    rels = len(ctx.get("relationships", []))
    return f"Verified context for {game}: {chars} chars, {locs} locs, {rels} rels"


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


def _cs_find_all_transcripts():
    """Find all transcripts in Content Studio (including Next folder)."""
    patterns = [
        os.path.join(CS_TRANSCRIPTS_DIR, "*.json"),
        os.path.join(CS_TRANSCRIPTS_DIR, "Next", "*.json")
    ]
    all_transcripts = []
    for pattern in patterns:
        all_transcripts.extend(glob.glob(pattern))
    
    # Sort by chapter number in filename (Chapter 1, 2, 3...)
    def get_chapter_num(path):
        import re
        match = re.search(r'Chapter\s*(\d+)', os.path.basename(path), re.IGNORECASE)
        return int(match.group(1)) if match else 999
    
    return sorted(all_transcripts, key=get_chapter_num)


def _cs_find_newest_transcript():
    """Find the newest transcript not yet processed."""
    all_transcripts = _cs_find_all_transcripts()
    ctx = _cs_load_context()
    processed = ctx.get("processed_transcripts", [])
    
    for transcript in all_transcripts:
        name = os.path.basename(transcript)
        if name not in processed:
            return transcript
    return None


def _cs_read_transcript(transcript_path):
    """Read a single transcript and return text."""
    try:
        with open(transcript_path) as f:
            data = json.load(f)
            text = ""
            for seg in data.get("segments", []):
                t = re.sub(r"<[^>]*>", "", seg.get("text", ""))
                if t.strip():
                    text += t + " "
            return text
    except Exception as e:
        log(f"Error reading {transcript_path}: {e}")
        return None


def _cs_read_all_transcripts():
    """Read all transcripts and combine text."""
    transcripts = _cs_find_all_transcripts()
    if not transcripts:
        return None
    
    all_text = ""
    for path in transcripts:
        try:
            with open(path) as f:
                data = json.load(f)
                for seg in data.get("segments", []):
                    text = re.sub(r"<[^>]*>", "", seg.get("text", ""))
                    if text.strip():
                        all_text += text + " "
        except Exception as e:
            log(f"Error reading {path}: {e}")
    
    # Limit to first 50000 chars to stay safe within context
    return all_text if all_text else None


def _cs_analyze_transcript(transcript_text):
    """Analyze transcript and determine best content type, subject, and angle."""
    keys = get_gemini_keys()
    if not keys:
        raise RuntimeError("No API keys available")
    
    game_title = env("GAME_TITLE", "")
    ctx = _cs_load_context()
    
    stored_chars = ", ".join(ctx.get("characters", [])) if ctx.get("characters") else "None yet"
    stored_locs = ", ".join(ctx.get("locations", [])) if ctx.get("locations") else "None yet"
    stored_rels = "; ".join(ctx.get("relationships", [])) if ctx.get("relationships") else "None yet"
    previous_scripts = ctx.get("previous_scripts", [])
    prev_script_info = ""
    if previous_scripts:
        prev_script_info = "\n\nPREVIOUS SCRIPTS (for continuity):\n" + "\n---\n".join(previous_scripts[-3:])
    
    prompt = f"""Analyze these transcripts from the game "{game_title}" and identify the MOST SIGNIFICANT story elements.

VERIFIED CONTEXT FROM PREVIOUS TRANSCRIPTS:
- Known Characters: {stored_chars}
- Known Locations: {stored_locs}
- Known Relationships: {stored_rels}{prev_script_info}

IMPORTANT PRIORITIES (in order):
1. Character deaths, major plot twists, emotional moments
2. Key character relationships and conflicts
3. Theme/lesson of the story
4. Then minor details

From these, determine:
1. CONTENT_TYPE: What content would be most engaging?
   - Theory (for predictions/speculation)
   - Analysis (for character deep-dive)
   - Review (for opinions/rankings)
   - Mystery (for hidden details/plot twists)
   - Lore (for world-building)
2. SUBJECT: Who or what is the main focus? (be specific: "Safi" not "characters")
3. ANGLE: What specific aspect would captivate viewers? (prioritize major moments)
4. VOICE_STYLE: Match to content type
5. REAL_CHARACTERS: List ONLY the character names that actually appear in the transcript (use verified list above as reference)
6. KEY_PLOT_POINTS: List 3-5 specific plot points, events, or story beats that are actually mentioned in the transcript. Be specific

Respond in this exact format:
CONTENT_TYPE: [type]
SUBJECT: [subject - be specific]
ANGLE: [specific moment or detail - focus on major story beats]
VOICE_STYLE: [style]
REAL_CHARACTERS: [comma-separated list of actual character names from transcript]
KEY_PLOT_POINTS: [semicolon-separated list of specific events mentioned in transcript]

Transcripts:
{transcript_text}"""

    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048}
    }).encode()
    
    key = keys[0]
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
    
    _rate_limit()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "X-Goog-Api-Key": key})
    
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            r = json.loads(resp.read())
            text = r["candidates"][0]["content"]["parts"][0]["text"]
            
            # Parse response
            content_type = "Analysis"
            subject = "Unknown"
            angle = "General overview"
            voice_style = "Documentary"
            real_characters = []
            key_plot_points = []
            
            for line in text.split("\n"):
                if line.startswith("CONTENT_TYPE:"):
                    content_type = line.split(":", 1)[1].strip()
                elif line.startswith("SUBJECT:"):
                    subject = line.split(":", 1)[1].strip()
                elif line.startswith("ANGLE:"):
                    angle = line.split(":", 1)[1].strip()
                elif line.startswith("VOICE_STYLE:"):
                    voice_style = line.split(":", 1)[1].strip()
                elif line.startswith("REAL_CHARACTERS:"):
                    chars = line.split(":", 1)[1].strip()
                    real_characters = [c.strip() for c in chars.split(",") if c.strip()]
                elif line.startswith("KEY_PLOT_POINTS:"):
                    points = line.split(":", 1)[1].strip()
                    key_plot_points = [p.strip() for p in points.split(";") if p.strip()]
            
            return content_type, subject, angle, voice_style, real_characters, key_plot_points
    except Exception as e:
        log(f"Analysis error: {e}")
        return "Analysis", "Unknown", "General overview", "Documentary", [], []


def _summarize_transcript(transcript_text, game_title):
    """Multi-chunk transcript summarization for script generation.

    For transcripts > 20k chars, splits into overlapping chunks,
    summarizes each, then combines into a final structured summary.

    Returns dict with: narrative_summary, key_events, characters_mentioned,
                       themes, emotional_tone, recommended_delivery
    or None on complete failure.
    """
    if not transcript_text or len(transcript_text.strip()) < 100:
        return None

    # Cap input to prevent multi-chunk processing which can cause OOM
    if len(transcript_text) > 18000:
        transcript_text = transcript_text[:18000]

    CHUNK_SIZE = 20000
    OVERLAP = 2000

    def _call_summary_gemini(prompt_text, system_hint="", temperature=0.4):
        """Single Gemini JSON call with retry — returns parsed dict or None."""
        keys = get_gemini_keys()
        if not keys:
            return None
        body = json.dumps({
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 2048,
                "response_mime_type": "application/json"
            }
        }).encode()
        for i in range(len(keys)):
            key = keys[i]
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
            for attempt in range(3):
                try:
                    _rate_limit()
                    req = urllib.request.Request(
                        url, data=body,
                        headers={"Content-Type": "application/json", "X-Goog-Api-Key": key}
                    )
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        r = json.loads(resp.read())
                        text = r["candidates"][0]["content"]["parts"][0]["text"]
                        parsed = json.loads(text)
                        gc.collect()
                        if isinstance(parsed, dict) and "narrative_summary" in parsed:
                            return parsed
                        return parsed
                except urllib.error.HTTPError as e:
                    if e.code in (429, 500, 503):
                        wait = (2 ** attempt) * 15 + random.uniform(0, 10)
                        time.sleep(wait)
                    else:
                        break
                except (json.JSONDecodeError, KeyError):
                    time.sleep(2)
                    break
                except Exception:
                    time.sleep(5)
                    break
        return None

    # Single chunk case
    if len(transcript_text) <= CHUNK_SIZE:
        prompt = f"""Analyze this transcript from the game "{game_title}" and produce a structured narrative summary.

Respond ONLY with a valid JSON object matching this schema:
{{
    "narrative_summary": "2-3 paragraph condensed summary of what happens — focus on the story, key moments, and emotional beats",
    "key_events": ["specific event 1", "specific event 2"],
    "characters_mentioned": ["character 1", "character 2"],
    "themes": ["theme 1", "theme 2"],
    "emotional_tone": "one short phrase describing the overall tone (e.g., tense, dramatic, humorous, action-packed, mysterious)",
    "recommended_delivery": "one sentence describing the narrator delivery style (e.g., energetic and fast-paced, somber and reflective, suspenseful whispers)"
}}

Transcript:
{transcript_text[:18000]}"""
        result = _call_summary_gemini(prompt)
        gc.collect()
        return result

    # Multi-chunk: split into overlapping chunks
    chunks = []
    pos = 0
    while pos < len(transcript_text):
        end = min(pos + CHUNK_SIZE, len(transcript_text))
        chunks.append(transcript_text[pos:end])
        pos = end - OVERLAP
        if pos >= len(transcript_text):
            break

    log(f"   Summarizing transcript ({len(chunks)} chunks, {len(transcript_text)} total chars)...")

    chunk_summaries = []
    for ci, chunk in enumerate(chunks):
        cprompt = f"""Summarize this excerpt from the game "{game_title}". Focus on what happens, key characters, and the emotional tone.

Keep it concise (2-4 sentences). Just describe the narrative content.

Excerpt {ci+1}/{len(chunks)}:
{chunk[:18000]}"""
        result = _call_summary_gemini(cprompt, temperature=0.3)
        if result:
            chunk_summaries.append(result.get("narrative_summary", chunk[:500]))
        else:
            chunk_summaries.append(chunk[:500])

    # Combine chunk summaries into final structured summary
    combined_text = "\n\n".join(f"--- Chunk {i+1} ---\n{s}" for i, s in enumerate(chunk_summaries))
    combine_prompt = f"""You are a narrative analyst. Below are chunk summaries from the game "{game_title}".
Combine them into a single structured analysis of the FULL story.

{combined_text}

Respond ONLY with a valid JSON object matching this schema:
{{
    "narrative_summary": "2-3 paragraph condensed summary of the full story arc — cover the beginning, middle, and end",
    "key_events": ["specific event 1", "specific event 2", "specific event 3"],
    "characters_mentioned": ["character 1", "character 2"],
    "themes": ["theme 1", "theme 2"],
    "emotional_tone": "one short phrase describing the overall tone across the whole story",
    "recommended_delivery": "one sentence describing the narrator delivery style for this content"
}}"""
    result = _call_summary_gemini(combine_prompt, temperature=0.4)
    gc.collect()
    return result


def _cs_generate_script(transcript_text, content_type, subject, angle, real_characters, key_plot_points):
    """Generate a script using Groq primary with Gemini fallback, validation, and context optimization."""
    keys = get_gemini_keys()
    if not keys:
        raise RuntimeError("No API keys available")
    
    game_title = env("GAME_TITLE", "the game")
    ctx = _cs_load_context()
    ctx = summarize_context(ctx, max_per_category=10)
    
    # Get verified context for validation (source of truth)
    verified_ctx = get_verified_context_for_validation(game_title)
    
    # Merge: prefer verified context characters/locations/relationships over extracted
    validation_ctx = {}
    if verified_ctx:
        validation_ctx = {
            "characters": verified_ctx.get("characters", ctx.get("characters", [])),
            "locations": verified_ctx.get("locations", ctx.get("locations", [])),
            "key_terms": ctx.get("key_terms", []),
            "relationships": verified_ctx.get("relationships", ctx.get("relationships", []))
        }
    else:
        validation_ctx = ctx
    
    stored_chars = ", ".join(ctx.get("characters", [])) if ctx.get("characters") else "None yet"
    stored_locs = ", ".join(ctx.get("locations", [])) if ctx.get("locations") else "None yet"
    stored_rels = "; ".join(ctx.get("relationships", [])) if ctx.get("relationships") else "None yet"
    previous_scripts = ctx.get("previous_scripts", [])
    prev_script_info = ""
    if previous_scripts:
        prev_script_info = f"\n\nSERIES CONTINUITY - PREVIOUS SCRIPTS:\n" + "\n---\n".join(previous_scripts[-3:])
        prev_script_info += "\n\nThis is a continuation. Build on previous content naturally without repeating what's already been said."
    
    type_prompts = {
        "Mystery Recap": "Write a mystery recap in complete, natural sentences. Start with a hook that creates curiosity. Tell the story chronologically while hinting at secrets. Target 1500-2000 words.",
        "Breakdown": "Write an analytical breakdown. Start with a hook that states a surprising insight. Explain WHY things happened, not just WHAT. Connect cause and effect. Target 1500-2000 words.",
        "Timeline": "Write a chronological timeline. Hook viewers immediately with a dramatic moment. Tell events in order from beginning to climax. Build momentum. Target 1500-2000 words.",
        "Moral/Lesson": "Write a reflective lesson. Hook with a bold statement about what was learned. Explain what happened and what could have been different. End with a thought-provoking question. Target 1500-2000 words.",
        "Narrative": "Write a first-person narrative as if telling a friend what happened. Hook immediately with something surprising or emotional. Use vivid descriptions. Target 1500-2000 words.",
        "News Report": "Write a professional news report. Lead with the key fact in the first sentence. Add context. Use objective, factual language. Target 1500-2000 words.",
        "Documentary": "Write a documentary-style narration. Start with a hook that reveals something fascinating. Add historical or psychological context. Target 1500-2000 words.",
        "True Crime": "Write a true crime story. Hook with a shocking detail. Build investigation and tension. End with revelation. Target 1500-2000 words.",
        "True Story": "Write a true story narration. Hook with the most unbelievable true detail. Let the facts carry the drama. Target 1500-2000 words.",
        "Character POV": "Write from the main character's perspective. Hook with an immediate emotional moment. Show internal thoughts in first person. Target 1500-2000 words.",
        "Theory": "Create a 'what if' theory video. Speculate about plot possibilities, character motivations, and future story directions. Make it intriguing and engaging.",
        "Analysis": "Create a character analysis video. Deep dive into character motivations, psychology, relationships, and character arcs. Be informative and educational.",
        "Review": "Create an opinion and review video. Share hot takes, rank elements, and give honest opinions about story beats. Be conversational and engaging.",
        "Mystery": "Create a mystery reveal video. Uncover hidden details, plot twists, and missed details that viewers might have overlooked. Build suspense.",
        "Lore": "Create a lore and world-building video. Explore game world details, backstory, history, and hidden lore. Be educational and informative."
    }
    
    type_instruction = type_prompts.get(content_type, type_prompts["Analysis"])
    
    # Get learned constraints for self-improvement
    learned = get_learned_constraints(game_title=game_title, content_type=content_type.lower() if content_type else "unknown")
    learned_constraints_text = ""
    if learned.get("negative_constraints") or learned.get("positive_emphasis"):
        learned_constraints_text = "\n\nLEARNED CONSTRAINTS (from previous generation data - follow these):\n"
        for nc in learned.get("negative_constraints", []):
            learned_constraints_text += f"- {nc}\n"
        for pe in learned.get("positive_emphasis", []):
            learned_constraints_text += f"- {pe}\n"
    
    allowed_chars = ", ".join(real_characters) if real_characters else f"Use these verified characters only: {stored_chars}"
    plot_points_str = "; ".join(key_plot_points) if key_plot_points else "Only use events explicitly mentioned in the transcript"
    
    context_info = f"""VERIFIED CONTEXT (use these to avoid hallucinations):
- Characters: {stored_chars}
- Locations: {stored_locs}
- Relationships: {stored_rels}{prev_script_info}
{learned_constraints_text}

Focus on this angle: {angle}

CRITICAL RESTRICTIONS:
- You MUST only mention these real characters: {allowed_chars}
- DO NOT invent or mention any character names that are NOT in the above list
- DO NOT create fictional characters like "Sarah", "Mark", "David", "Alex" unless they appear in the transcript
- If you need to reference people, use generic terms like "a friend", "a character" or "the victim" instead of made-up names
- ONLY write about these specific plot points from the transcript: {plot_points_str}
- DO NOT include any plot details, character abilities, or story elements that are NOT mentioned in the transcript above
- DO NOT invent relationships between characters - if the transcript doesn't explicitly state a connection between characters, do NOT imply or state that they have a relationship
- DO NOT make up roles for characters (e.g., don't say "Chief Bank is leading the inquiry" unless explicitly stated in transcript)
- Only describe characters and events that are explicitly mentioned in the transcript - do not infer or assume details not directly stated"""

    # Try Jinja2 template first
    try:
        env = _get_prompt_env()
        template = env.get_template("content_studio.j2")
        prompt = template.render(
            game_title=game_title,
            content_type=content_type,
            angle=angle,
            context_info=context_info,
            type_instruction=type_instruction,
            learned_constraints=learned_constraints_text,
            perf_context="",
            recent_titles="",
            lore_info="",
            transcript=transcript_text,
        )
    except Exception as e:
        log(f"   Content Studio Jinja2 template error: {e}, using legacy prompt")
        # Fallback to legacy f-string prompt
        prompt = f"""You are an expert YouTube scriptwriter specializing in gaming content analysis.

Create a 1500-2000-word video script (5-10 minutes) about {subject} from {game_title}.

{type_instruction}

{context_info}

The script should:
- Have a hook at the start to grab attention
- Be conversational and engaging for a 5-10 minute video
- Include natural paragraph flow (NOT bullet points or fragments)
- Have a clear structure with intro, body, and conclusion
- End with a call to action asking viewers to like and subscribe
- Be written in a style suitable for a YouTube video narration
- Stay FACTUALLY accurate to the transcript - do not make up events or details

Before writing, think through:
1. What is the core hook that will grab viewers in 3 seconds?
2. What is the most compelling angle from this transcript?
3. How does the story build from hook to climax to resolution?
4. What emotional response should the viewer have at the end?

Before outputting, verify:
- Does the script use ONLY verified characters and locations?
- Is the script 1500-2000 words?
- Does it flow naturally when read aloud?
- Are there any forbidden elements (invented characters, made-up events)?

Write the complete script now."""

    # Phase 5: Use Groq primary with adaptive temperature
    groq_model = _get_groq_model("narrative")  # Content Studio uses narrative style
    temperature = 0.8  # Content Studio uses slightly higher temperature for creative content
    
    candidates = []
    
    # Attempt 1: Groq (primary)
    try:
        groq_script = _groq_generate(prompt, max_tokens=3072, model=groq_model, temperature=temperature)
        if groq_script:
            candidates.append((groq_script, {"source": "groq", "model": groq_model, "temperature": temperature}))
            log(f"   Content Studio: Groq script generated ({len(groq_script.split())} words)")
    except Exception as e:
        log(f"   Content Studio: Groq generation failed: {e}, falling back to Gemini")

    # Attempt 2: Gemini (fallback)
    if not candidates:
        try:
            body = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": temperature, "maxOutputTokens": 3072}
            }).encode()
            
            for i in range(len(keys)):
                key = keys[i % len(keys)]
                url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
                
                for attempt in range(3):
                    try:
                        _rate_limit()
                        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "X-Goog-Api-Key": key})
                        with urllib.request.urlopen(req, timeout=60) as resp:
                            r = json.loads(resp.read())
                            gemini_script = r["candidates"][0]["content"]["parts"][0]["text"]
                            candidates.append((gemini_script, {"source": "gemini", "model": "gemini-2.5-flash-lite", "temperature": temperature}))
                            log(f"   Content Studio: Gemini script generated ({len(gemini_script.split())} words)")
                            break
                    except urllib.error.HTTPError as e:
                        if e.code == 429:
                            wait = (2 ** attempt) * 15 + random.uniform(0, 10)
                            log(f"Key ...{key[-6:]} rate limited (429), retry {attempt+1}/3 in {wait:.0f}s...")
                            time.sleep(wait)
                        elif e.code in (500, 503):
                            wait = (2 ** attempt) * 10 + random.uniform(0, 5)
                            log(f"Key ...{key[-6:]} server error ({e.code}), retry {attempt+1}/3 in {wait:.0f}s...")
                            time.sleep(wait)
                        elif e.code == 400:
                            log(f"Key ...{key[-6:]} bad request (400): {e.read().decode()[:200]}")
                            break
                        else:
                            log(f"HTTP error {e.code} with key ...{key[-6:]}: {e}")
                            break
                    except Exception as e:
                        log(f"Script generation error with key ...{key[-6:]}: {e}")
                        time.sleep(5)
                        break
                
                if candidates:
                    break
                log(f"Key ...{key[-6:]} failed, trying next...")
        except Exception as e:
            log(f"   Content Studio: Gemini generation failed: {e}")

    if not candidates:
        raise RuntimeError("Script generation failed: All API keys exhausted")

    # Phase 2: Validate and select best script
    best_script, best_metadata, scores = select_best_script(candidates, ctx)
    if scores and len(scores) > 1:
        log(f"   Content Studio: Selected best script from {len(scores)} candidates (score: {scores[0]['combined']})")
    
    # Phase 6: Log quality metrics
    fact_check = validate_script_factuality(best_script, validation_ctx)
    engagement = score_engagement(best_script)
    log(f"   Content Studio quality: factuality={fact_check['score']}, engagement={engagement['overall']}, words={len(best_script.split())}")
    if fact_check["issues"]:
        for issue in fact_check["issues"]:
            log(f"   Content Studio WARNING: {issue}")
    
    log_generation_metrics(best_script, best_metadata, fact_check, engagement, METRICS_FILE)
    
    # Store failure data for self-improvement
    game_title = env("GAME_TITLE", "Content Studio")
    content_type_val = content_type.lower() if content_type else "unknown"
    store_generation_failure(best_script, best_metadata, fact_check, engagement, game_title=game_title, content_type=content_type_val)
    
    return best_script


def _cs_generate_tts(script, voice_style):
    """Generate TTS from script (handles 2 segments for 10 min)."""
    os.makedirs(CS_TTS_DIR, exist_ok=True)
    
    provider = env("TTS_PROVIDER", "gemini").strip().lower()
    
    # Get voice based on style
    voices_by_style = {
        "Mysterious": ["Zephyr", "Charon", "Umbriel"],
        "Conversational": ["Aoede", "Leda", "Kore"],
        "Documentary": ["Vindemiatrix", "Gacrux", "Sadachbia"],
        "Investigative": ["Fenrir", "Orus", "Rasalgethi"],
        "Educational": ["Alnilam", "Algieba", "Schedar"]
    }
    style_voices = voices_by_style.get(voice_style, voices_by_style["Documentary"])
    voice = style_voices[_rr_get_state()['tts_index'] % len(style_voices)]
    
    # Split script into 2 segments (~750 words each)
    words = script.split()
    mid = len(words) // 2
    segments = [(" ".join(words[:mid]), "segment1"), (" ".join(words[mid:]), "segment2")]
    
    audio_files = []
    
    for text_part, name in segments:
        out_wav = os.path.join(CS_TTS_DIR, f"{name}.wav")
        
        if provider == "kokoro":
            try:
                from workflows.pipeline.phase_tts_kokoro import generate_tts_file
                ok = generate_tts_file(text_part, out_wav, voice, None)
                if ok:
                    audio_files.append(out_wav)
                    tts_success = True
                else:
                    tts_success = False
            except Exception as e:
                log(f"Kokoro TTS failed: {e}, falling back to Gemini")
                provider = "gemini"
                tts_success = False
        elif provider == "edge":
            try:
                import edge_tts, asyncio
                edge_voice = "en-US-JennyNeural"
                async def _do():
                    c = edge_tts.Communicate(text_part, edge_voice)
                    await c.save(out_wav)
                asyncio.run(_do())
                if os.path.exists(out_wav) and os.path.getsize(out_wav) > 0:
                    audio_files.append(out_wav)
                    tts_success = True
                else:
                    tts_success = False
            except Exception as e:
                log(f"Edge TTS failed: {e}, falling back to Gemini")
                provider = "gemini"
                tts_success = False
        
        if provider == "gemini" or not tts_success:
            voice_id = _get_voice_id(voice)
            if not voice_id:
                raise RuntimeError(f"Unknown voice: {voice}")
            
            body = json.dumps({
                "contents": [{"parts": [{"text": text_part}]}],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice_id}}}
                }
            }).encode()
            
            keys = get_gemini_keys()
            api_keys = keys if keys else [env("GEMINI_API_KEY")]
            time.sleep(2)
            
            out_pcm = os.path.join(CS_TTS_DIR, f"{name}.pcm")
            tts_success = False
            
            for key in api_keys:
                url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent"
                req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "X-Goog-Api-Key": key})
                
                for attempt in range(3):
                    try:
                        with urllib.request.urlopen(req, timeout=120) as resp:
                            r = json.loads(resp.read())
                            audio = r["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
                            with open(out_pcm, "wb") as f:
                                f.write(base64.b64decode(audio))
                            subprocess.run(["ffmpeg", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", out_pcm, "-ar", "24000", "-ac", "1", out_wav], capture_output=True)
                            os.remove(out_pcm)
                            audio_files.append(out_wav)
                            tts_success = True
                            break
                    except urllib.error.HTTPError as e:
                        if e.code == 429 and attempt < 2:
                            wait = 30 * (2 ** attempt)
                            log(f"Key ...{key[-6:]} rate limited, retry in {wait}s...")
                            time.sleep(wait)
                        else:
                            log(f"TTS error with key ...{key[-6:]}: {e.code}")
                            break
                    except Exception as e:
                        log(f"TTS error with key ...{key[-6:]}: {e}")
                        break
                
                if tts_success:
                    break
        
        if not tts_success:
            raise RuntimeError(f"TTS generation failed for segment: {name}")
    
    # Check we got all segments
    if len(audio_files) != len(segments):
        raise RuntimeError(f"TTS failed: only {len(audio_files)}/{len(segments)} segments generated")
    
    # Concatenate audio files
    final_audio = os.path.join(CS_TTS_DIR, f"content_{int(time.time())}.wav")
    concat_list = os.path.join(CS_TTS_DIR, "concat_list.txt")
    with open(concat_list, "w") as f:
        for af in audio_files:
            f.write(f"file '{af}'\n")
    
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", final_audio], capture_output=True)
    
    # Cleanup
    for af in audio_files:
        os.remove(af)
    os.remove(concat_list)
    
    return final_audio, voice


def _cs_generate_srt(audio_file):
    """Generate SRT from audio file using faster-whisper."""
    # Use faster-whisper to generate transcript with timestamps
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(env("WHISPER_MODEL", "medium"), device="cpu", compute_type="int8")
        segments, info = model.transcribe(audio_file, language="en", word_timestamps=False)
        
        srt_file = audio_file.replace(".wav", ".srt")
        with open(srt_file, "w") as f:
            for i, seg in enumerate(segments, 1):
                start = _format_srt_time(seg.start)
                end = _format_srt_time(seg.end)
                text = seg.text.strip()
                f.write(f"{i}\n{start} --> {end}\n{text}\n\n")
        
        return srt_file
    except Exception as e:
        log(f"SRT generation error: {e}")
        return None


def _format_srt_time(seconds):
    """Format seconds to SRT time format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _wrap_text_for_srt(text, max_words=10):
    """Wrap text to have max words per line for better SRT readability."""
    if not text:
        return text
    words = text.split()
    if len(words) <= max_words:
        return text
    
    lines = []
    for i in range(0, len(words), max_words):
        lines.append(' '.join(words[i:i+max_words]))
    return '\n'.join(lines)


def _get_voice_id(voice_name):
    """Get Gemini TTS voice ID (maps from all 30 TTS_VOICES)."""
    voices = {v: v for v in TTS_VOICES}
    return voices.get(voice_name)


def _cs_generate_script_only():
    """Generate script only (no TTS). Uses newest unprocessed transcript."""
    for d in (CS_SCRIPTS_DIR, CS_TTS_DIR):
        os.makedirs(d, exist_ok=True)
    
    # Find newest unprocessed transcript
    transcript = _cs_find_newest_transcript()
    if not transcript:
        log_notification("✅ No new transcripts. All have scripts generated.")
        ctx = _cs_load_context()
        log_notification(f"Scripts generated: {len(ctx.get('previous_scripts', []))}")
        return
    
    transcript_name = os.path.basename(transcript)
    log_notification(f"📖 Reading transcript: {transcript_name}")
    
    transcript_text = _cs_read_transcript(transcript)
    if not transcript_text:
        log_notification(f"❌ Could not read {transcript_name}")
        return
    
    log_notification(f"📖 Read {len(transcript_text)} characters")
    
    # Extract and update context from transcript
    game_title = env("GAME_TITLE", "Unknown Game")
    game_key = game_title.lower().replace(" ", "_")
    log_notification("🔍 Extracting context from transcript...")
    extracted = _cs_extract_context_from_transcript(transcript_text, game_title)
    ctx = _cs_load_context()
    if extracted:
        ctx = _cs_update_context(extracted, transcript_name)
        _save_segment_references(game_key, transcript_name, extracted, transcript_file=transcript)
        log_notification(f"📚 Context updated: {len(ctx['characters'])} characters, {len(ctx['locations'])} locations")
        
        # NEW: Also mine to MemPalace for persistent memory
        if MEMPALACE_AVAILABLE and env("MEMORY_ENABLED", "true").lower() == "true":
            try:
                mp_manager = get_mempalace_manager()
                if mp_manager and transcript:
                    result = mp_manager.mine_transcript(transcript, game_title)
                    if result.get("status") == "success":
                        log_notification(f"🧠 MemPalace: Mined transcript for {game_title}")
                    else:
                        log_notification(f"🧠 MemPalace: Mining skipped")
            except Exception as mp_err:
                log_notification(f"🧠 MemPalace: Mining failed - {mp_err}")
    else:
        log_notification("⚠️ Could not extract context, using existing")
    
    log_notification("🔍 Analyzing content (this may take a moment)...")
    content_type, subject, angle, voice_style, real_characters, key_plot_points = _cs_analyze_transcript(transcript_text)
    log_notification(f"📝 Detected: {content_type}\n👤 Subject: {subject}\n🎤 Voice: {voice_style}\n📋 Characters: {', '.join(real_characters[:5]) if real_characters else 'None'}\n🔑 Plot: {key_plot_points[0] if key_plot_points else 'None'}")

    log_notification("✍️ Generating script (~1500 words)...")
    
    # NEW: Inject MemPalace memory into context
    if MEMPALACE_AVAILABLE and env("MEMORY_ENABLED", "true").lower() == "true":
        game_title = env("GAME_TITLE", "")
        if game_title and game_title != "Unknown Game":
            try:
                mp_manager = get_mempalace_manager()
                if mp_manager:
                    game_memory = mp_manager.get_game_memory(game_title)
                    if game_memory and game_memory.get("success"):
                        log_notification(f"🧠 MemPalace: Retrieved memory for {game_title}")
            except Exception as mp_err:
                log_notification(f"🧠 MemPalace: Memory retrieval failed - {mp_err}")
    
    try:
        script = _cs_generate_script(transcript_text, content_type, subject, angle, real_characters, key_plot_points)
    except Exception as e:
        log_notification(f"❌ Script generation failed: {e}")
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
                log_notification(f"🧠 MemPalace: Logged quality metric")
        except Exception as mp_err:
            pass  # Don't fail on quality logging
    
    # Create script summary for context
    script_summary = f"Script {len(ctx.get('previous_scripts', [])) + 1}: {subject} - {content_type} - {angle[:50]}..."
    _cs_update_context({}, transcript_name, script_summary)
    
    log_notification(f"✅ Script generated!\n📝 Saved: {os.path.basename(script_file)}")


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
        log_notification("❌ No scripts found. Generate a script first.")
        return
    
    latest_script = scripts[0]
    with open(latest_script) as f:
        original_script = f.read()
    
    script = _cs_clean_script_for_tts(original_script)
    word_count = len(script.split())
    log_notification(f"📄 Found script: {os.path.basename(latest_script)}")
    log_notification(f"🧹 Cleaned script for TTS: {word_count} words")
    log_notification("🎤 Generating TTS audio...")
    
    try:
        audio_file, voice = _cs_generate_tts(script, "Documentary")
    except Exception as e:
        log_notification(f"❌ TTS generation failed: {e}")
        return
    
    log_notification(f"✅ TTS generated!\n🎤 Voice: {voice}\n📁 Saved: {os.path.basename(audio_file)}")


# ── ASR ErrorCorrector ───────────────────────────────────────────────────────────
# (ASR corrector already defined above)





def _cs_save_context(ctx):
    """Persist context to verified_context.json only (no Obsidian markdown vault)."""
    game_title = env("GAME_TITLE", "default")
    try:
        from workflows.context_manager_v2 import load_verified_context, save_verified_context
        existing = load_verified_context(game_title) or {}
        # Normalize list fields to simple names / structured relationships
        payload = {
            "characters": list(ctx.get("characters", []) or []),
            "locations": list(ctx.get("locations", []) or []),
            "key_terms": list(ctx.get("key_terms", []) or []),
            "relationships": [],
            "processed_transcripts": list(ctx.get("processed_transcripts", []) or []),
            "previous_scripts": list(ctx.get("previous_scripts", []) or []),
            "character_aliases": dict(ctx.get("character_aliases", {}) or {}),
            "location_aliases": dict(ctx.get("location_aliases", {}) or {}),
            "title": ctx.get("title", "") or "",
        }
        if ctx.get("lore"):
            payload["lore"] = ctx["lore"]
        for rel in ctx.get("relationships", []) or []:
            if isinstance(rel, dict):
                a = (rel.get("from") or "").strip()
                b = (rel.get("to") or "").strip()
                if a and b and a.lower() != b.lower():
                    payload["relationships"].append({
                        "from": a,
                        "to": b,
                        "relationship": rel.get("relationship") or rel.get("category") or "related",
                    })
            elif isinstance(rel, str) and rel.strip():
                payload["relationships"].append(rel.strip())
        # Preserve lore from existing if not in ctx
        if not payload.get("lore") and isinstance(existing, dict) and existing.get("lore"):
            payload["lore"] = existing["lore"]
        save_verified_context(game_title, payload, merge=True)
    except Exception as e:
        log(f"[CONTEXT] Failed to save verified context: {e}")


def _detect_corrections(old_ctx, new_ctx):
    """
    Detect corrections by comparing old context vs newly extracted context.
    Uses fuzzy matching to avoid false positives from alias variations.
    Returns a dict of corrections found.
    
    NOTE: This only flags items that are in old_ctx but NOT in new_ctx.
    Items that are in new_ctx but NOT in old_ctx are additions, not corrections.
    The caller should decide whether to treat additions as corrections.
    """
    corrections = {
        "removed_characters": [],
        "added_characters": [],
        "removed_locations": [],
        "added_locations": [],
        "removed_terms": [],
        "added_terms": [],
        "removed_relationships": [],
        "added_relationships": []
    }

    def fuzzy_set_diff(old_items, new_items, threshold=80):
        removed = []
        added = []
        for item in old_items:
            is_dup, _ = fuzzy_dedup_against_list(item, new_items, threshold)
            if not is_dup:
                removed.append(item)
        for item in new_items:
            is_dup, _ = fuzzy_dedup_against_list(item, old_items, threshold)
            if not is_dup:
                added.append(item)
        return removed, added

    # Only compare if both contexts have data
    # If new_ctx is empty (extraction failed), don't flag anything as removed
    if new_ctx.get("characters"):
        removed, added = fuzzy_set_diff(
            old_ctx.get("characters", []),
            new_ctx.get("characters", [])
        )
        corrections["removed_characters"] = removed
        corrections["added_characters"] = added

    if new_ctx.get("locations"):
        removed, added = fuzzy_set_diff(
            old_ctx.get("locations", []),
            new_ctx.get("locations", [])
        )
        corrections["removed_locations"] = removed
        corrections["added_locations"] = added

    if new_ctx.get("key_terms"):
        old_terms = set(old_ctx.get("key_terms", []))
        new_terms = set(new_ctx.get("key_terms", []))
        corrections["removed_terms"] = list(old_terms - new_terms)
        corrections["added_terms"] = list(new_terms - old_terms)

    if new_ctx.get("relationships"):
        old_rels_list = old_ctx.get("relationships", [])
        new_rels_list = new_ctx.get("relationships", [])
        corrections["removed_relationships"] = [r for r in old_rels_list if r not in new_rels_list]
        corrections["added_relationships"] = [r for r in new_rels_list if r not in old_rels_list]

    return corrections


def _store_corrections_as_constraints(corrections, game_title=None):
    """
    Store detected corrections as universal constraints in MemPalace.
    These constraints will be used in future context extractions.
    """
    if not MEMPALACE_AVAILABLE:
        log("[DEBUG] MemPalace not available, skipping constraint storage")
        return
    
    # Default to GAME_TITLE if not provided
    if not game_title:
        game_title = env("GAME_TITLE", "")
    
    try:
        mp_manager = get_mempalace_manager()
        if not mp_manager:
            return
        
        constraints = []
        
        for char in corrections.get("removed_characters", []):
            if char:
                constraints.append(f"AVOID: Character '{char}' does not exist in this game (previously extracted but removed)")
        
        for loc in corrections.get("removed_locations", []):
            if loc:
                constraints.append(f"VERIFY: Location '{loc}' - confirm if it actually exists in the transcript")
        
        for rel in corrections.get("removed_relationships", []):
            if rel:
                constraints.append(f"VERIFY: Relationship '{rel}' - confirm if accurate")
        
        if constraints:
            log(f"[LEARNING] Storing {len(constraints)} learned constraints")
            
            # Store in MemPalace as a "constraints" document
            constraints_text = "\n".join(constraints)
            
            # Write to MemPalace for permanent storage
            try:
                wing = mp_manager._game_wing(game_title)
                mp_manager._add(wing, "corrections", constraints_text, "learned_constraints")
                log("[LEARNING] Constraints stored in MemPalace")
            except Exception as mp_err:
                log(f"[WARNING] Failed to store constraints in MemPalace: {mp_err}")
            
            # Also save to a local constraints file as backup
            constraints_file = os.path.join(CONTEXT_DIR, "learned_constraints.json")
            existing = []
            if os.path.exists(constraints_file):
                try:
                    with open(constraints_file, 'r') as f:
                        existing = json.load(f)
                except Exception:
                    pass
            
            # Deduplicate: only add constraints that don't already exist
            existing_constraints = {item.get("constraint") for item in existing if "constraint" in item}
            new_constraints = []
            for c in constraints:
                if c not in existing_constraints:
                    new_constraints.append({"constraint": c, "timestamp": datetime.now().isoformat()})
                    existing_constraints.add(c)
            
            if new_constraints:
                existing.extend(new_constraints)
                with open(constraints_file, 'w') as f:
                    json.dump(existing, f, indent=2)
                log(f"[LEARNING] {len(new_constraints)} new constraints saved")
            
    except Exception as e:
        log(f"[ERROR] Failed to store corrections as constraints: {e}")


def _get_learned_constraints():
    """
    Get learned constraints from previous corrections.
    Returns list of constraint strings to include in prompts.
    Prunes constraints older than 30 days.
    """
    constraints = []
    
    constraints_file = os.path.join(CONTEXT_DIR, "learned_constraints.json")
    if os.path.exists(constraints_file):
        try:
            with open(constraints_file, 'r') as f:
                data = json.load(f)
                
            cutoff = datetime.now() - timedelta(days=30)
            pruned = []
            for item in data:
                if "constraint" in item and "timestamp" in item:
                    try:
                        ts = datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=None)
                        if ts > cutoff:
                            pruned.append(item)
                            constraints.append(item["constraint"])
                    except (ValueError, TypeError):
                        pruned.append(item)
                        constraints.append(item["constraint"])
                elif "constraint" in item:
                    pruned.append(item)
                    constraints.append(item["constraint"])
            
            if len(pruned) < len(data):
                with open(constraints_file, 'w') as f:
                    json.dump(pruned, f, indent=2)
                log(f"[LEARNING] Pruned {len(data) - len(pruned)} old constraints")
                
        except Exception as e:
            log(f"[DEBUG] Could not load learned constraints: {e}")
    
    return constraints


def _gemini_json_prompt(prompt: str, temperature: float = 0.3, max_tokens: int = 2048) -> dict | None:
    """Send a prompt to Gemini and return parsed JSON response."""
    keys = get_gemini_keys()
    if not keys:
        return None
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "response_mime_type": "application/json"
        }
    }).encode()
    key = keys[0]
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
    _rate_limit()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "X-Goog-Api-Key": key})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            r = json.loads(resp.read())
            text = r["candidates"][0]["content"]["parts"][0]["text"]
            text = text.strip()
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            return json.loads(text)
    except (json.JSONDecodeError, KeyError, urllib.error.HTTPError) as e:
        log(f"Gemini JSON prompt failed: {e}")
        return None


def _extract_characters(transcript_text, game_title, constraints_text):
    """Pass 1: Extract character names and aliases from transcript."""
    prompt = f"""Analyze this transcript from "{game_title}" and extract CHARACTER NAMES only.

List every named character mentioned in the transcript. For each character, list their full name and any aliases or nicknames used.

{constraints_text}

Respond ONLY with a valid JSON object matching this schema:
{{
    "characters": [
        {{"name": "Full Character Name", "aliases": ["alias1", "alias2"]}}
    ]
}}

Transcript excerpt:
{transcript_text[:5000]}"""
    return _gemini_json_prompt(prompt, temperature=0.2, max_tokens=1024)


def _extract_locations_and_terms(transcript_text, game_title, constraints_text):
    """Pass 2: Extract locations and key terms from transcript."""
    transcript_mid = transcript_text[2500:7500] or transcript_text[:5000]
    prompt = f"""Analyze this transcript from "{game_title}" and extract:

1. LOCATIONS: Every place mentioned (towns, buildings, regions, rooms, landmarks)
2. KEY_TERMS: Important story elements, themes, concepts, artifacts, or organizations

{constraints_text}

Respond ONLY with a valid JSON object matching this schema:
{{
    "locations": ["location1", "location2"],
    "key_terms": ["term1", "term2"]
}}

Transcript excerpt:
{transcript_mid[:5000]}"""
    return _gemini_json_prompt(prompt, temperature=0.2, max_tokens=1024)


def _extract_relationships(transcript_text, game_title, constraints_text):
    """Pass 3: Extract relationships with confidence scores and evidence."""
    transcript_end = transcript_text[-5000:] if len(transcript_text) > 5000 else transcript_text[:5000]
    prompt = f"""Analyze this transcript from "{game_title}" and extract RELATIONSHIPS between characters.

For every pair of characters that interact or are connected, provide:
- The two characters involved (MUST be two DIFFERENT characters — never the same name twice)
- The type of relationship (allies, enemies, family, mentor, rival, friends, associates)
- A confidence score from 0.0 to 1.0 (how certain you are based on the transcript)
- A brief piece of evidence text from the transcript supporting this relationship

Never output self-referential relationships (from == to). Skip uncertain pairs.

{constraints_text}

Respond ONLY with a valid JSON object matching this schema:
{{
    "relationships": [
        {{
            "from": "Character A",
            "to": "Character B",
            "relationship": "friends",
            "confidence": 0.9,
            "evidence": "brief quote or context from transcript"
        }}
    ]
}}

Transcript excerpt:
{transcript_end[:5000]}"""
    return _gemini_json_prompt(prompt, temperature=0.4, max_tokens=2048)


def _cs_extract_context_from_transcript(transcript_text, game_title):
    """Multi-pass context extraction: 3 specialized passes for characters, locations, and relationships."""
    keys = get_gemini_keys()
    if not keys:
        return None

    constraints = _get_learned_constraints()
    constraints_text = ""
    if constraints:
        constraints_text = f"""
PREVIOUS MISTAKES TO AVOID:
{chr(10).join(f"- {c}" for c in constraints[:10])}

IMPORTANT: The above items are known mistakes from previous extractions. 
Do NOT repeat these errors. Be especially careful not to include characters 
or relationships that were previously flagged as incorrect.
"""

    result = {"title": "", "characters": [], "locations": [], "key_terms": [], "relationships": []}

    # Pass 1: Characters
    char_data = _extract_characters(transcript_text, game_title, constraints_text)
    if char_data:
        # Extract flat character names from the structured format
        raw_chars = []
        alias_map = {}
        for entry in char_data.get("characters", []):
            if isinstance(entry, dict):
                name = entry.get("name", "")
                if name:
                    raw_chars.append(name)
                    for alias in entry.get("aliases", []):
                        if alias and alias != name:
                            alias_map[alias] = name
            elif isinstance(entry, str):
                raw_chars.append(entry)
        result["characters"] = raw_chars
        result["character_aliases"] = alias_map
        result["title"] = char_data.get("title", "")

    # Pass 2: Locations and key terms
    loc_data = _extract_locations_and_terms(transcript_text, game_title, constraints_text)
    if loc_data:
        result["locations"] = loc_data.get("locations", [])
        result["key_terms"] = loc_data.get("key_terms", [])
        if not result["title"]:
            result["title"] = loc_data.get("title", "")

    # Pass 3: Relationships with confidence
    rel_data = _extract_relationships(transcript_text, game_title, constraints_text)
    if rel_data:
        rels = rel_data.get("relationships", [])
        # Filter by confidence threshold
        filtered_rels = []
        for rel in rels:
            if isinstance(rel, dict):
                confidence = rel.get("confidence", 0.5)
                if isinstance(confidence, str):
                    try:
                        confidence = float(confidence)
                    except (ValueError, TypeError):
                        confidence = 0.5
                if confidence >= 0.5:
                    filtered_rels.append(rel)
            else:
                filtered_rels.append(rel)
        result["relationships"] = filtered_rels
        if not result["title"]:
            result["title"] = rel_data.get("title", "")

    return result


def _save_segment_references(game_key, transcript_name, extracted_context, transcript_file=None):
    """Save segment references for context nodes with timestamps."""
    import uuid
    SEGMENT_REF_FILE = os.path.join(WORKSPACE, "Context", "segment_references.json")
    
    try:
        if os.path.exists(SEGMENT_REF_FILE):
            with open(SEGMENT_REF_FILE, "r") as f:
                refs = json.load(f)
        else:
            refs = {}
        
        if game_key not in refs:
            refs[game_key] = {}
        
        transcript_key = transcript_name.replace(".json", "")
        
        # Load transcript segments for timestamp matching
        segments = []
        if transcript_file and os.path.exists(transcript_file):
            try:
                with open(transcript_file) as f:
                    data = json.load(f)
                segments = data.get("segments", [])
            except Exception:
                pass
        
        def find_timestamp_ranges(entity_name, segments):
            """Find start/end timestamps where entity is mentioned."""
            ranges = []
            entity_lower = entity_name.lower()
            for seg in segments:
                text = seg.get("text", "").lower()
                if entity_lower in text:
                    ranges.append({
                        "start": seg.get("start", 0),
                        "end": seg.get("end", 0)
                    })
            return ranges
        
        node_refs = []
        for char in extracted_context.get("characters", []):
            timestamps = find_timestamp_ranges(char, segments)
            ref_entry = {"node": char, "type": "character", "transcript": transcript_key}
            if timestamps:
                ref_entry["timestamps"] = timestamps[:5]  # Keep first 5 mentions
            node_refs.append(ref_entry)
        for loc in extracted_context.get("locations", []):
            timestamps = find_timestamp_ranges(loc, segments)
            ref_entry = {"node": loc, "type": "location", "transcript": transcript_key}
            if timestamps:
                ref_entry["timestamps"] = timestamps[:5]
            node_refs.append(ref_entry)
        for term in extracted_context.get("key_terms", []):
            timestamps = find_timestamp_ranges(term, segments)
            ref_entry = {"node": term, "type": "term", "transcript": transcript_key}
            if timestamps:
                ref_entry["timestamps"] = timestamps[:5]
            node_refs.append(ref_entry)
        for rel in extracted_context.get("relationships", []):
            if isinstance(rel, dict):
                rel_key = f"{rel.get('from')}-{rel.get('to')}-{rel.get('relationship', '')}"
                timestamps = find_timestamp_ranges(rel.get("from", ""), segments)
                timestamps += find_timestamp_ranges(rel.get("to", ""), segments)
                ref_entry = {"node": rel_key, "type": "relationship", "transcript": transcript_key}
                if timestamps:
                    ref_entry["timestamps"] = timestamps[:5]
                node_refs.append(ref_entry)
        
        refs[game_key][transcript_key] = node_refs
        
        with open(SEGMENT_REF_FILE, "w") as f:
            json.dump(refs, f, indent=2)
        
        log(f"[CONTEXT] Saved segment references with timestamps for {transcript_key}")
    except Exception as e:
        log(f"[CONTEXT] Failed to save segment references: {e}")


def _cs_update_context(extracted, transcript_name, script_summary=None):
    """Update context with new extracted data."""
    ctx = _cs_load_context()
    
    # Detect corrections BEFORE updating (compare old vs new)
    corrections = _detect_corrections(ctx, extracted)
    has_corrections = any([
        corrections.get("removed_characters"),
        corrections.get("removed_locations"),
        corrections.get("removed_relationships")
    ])
    
    if has_corrections:
        log(f"[LEARNING] Detected corrections: {corrections}")
        _store_corrections_as_constraints(corrections)

    # Merge title (use the most recent non-empty title)
    extracted_title = extracted.get("title", "").strip()
    if extracted_title and (not ctx.get("title") or len(extracted_title) > len(ctx.get("title", ""))):
        ctx["title"] = extracted_title

    # Merge characters with fuzzy dedup and alias resolution
    for char in extracted.get("characters", []):
        is_dup, canonical = fuzzy_dedup_against_list(char, ctx["characters"])
        if is_dup:
            if canonical and canonical != char:
                if "character_aliases" not in ctx:
                    ctx["character_aliases"] = {}
                ctx["character_aliases"][char] = canonical
        else:
            ctx["characters"].append(char)

    # Merge locations with fuzzy dedup
    for loc in extracted.get("locations", []):
        is_dup, canonical = fuzzy_dedup_against_list(loc, ctx["locations"])
        if is_dup:
            if canonical and canonical != loc:
                if "location_aliases" not in ctx:
                    ctx["location_aliases"] = {}
                ctx["location_aliases"][loc] = canonical
        else:
            ctx["locations"].append(loc)

    # Merge key terms
    for term in extracted.get("key_terms", []):
        if term not in ctx["key_terms"]:
            ctx["key_terms"].append(term)

    # Merge relationships (avoid duplicates by fuzzy matching on text; skip self-refs)
    for rel in extracted.get("relationships", []):
        if isinstance(rel, dict):
            a = (rel.get("from") or "").strip().lower()
            b = (rel.get("to") or "").strip().lower()
            if not a or not b or a == b:
                continue
            rel_text = f"{rel.get('from', '')}-{rel.get('to', '')}-{rel.get('relationship', '')}"
        else:
            rel_text = str(rel)
            if " and " in rel_text:
                # crude self-ref: "X and X are"
                parts = rel_text.split(" and ", 1)
                if len(parts) == 2 and parts[0].strip().lower() == parts[1].split(" are ")[0].strip().lower():
                    continue
        is_dup = False
        for existing_rel in ctx["relationships"]:
            if isinstance(existing_rel, dict):
                existing_text = f"{existing_rel.get('from', '')}-{existing_rel.get('to', '')}-{existing_rel.get('relationship', '')}"
            else:
                existing_text = str(existing_rel)
            ratio = _fuzz.token_sort_ratio(rel_text.lower(), existing_text.lower()) if _fuzz else 0
            if ratio >= 75:
                is_dup = True
                break
        if not is_dup:
            ctx["relationships"].append(rel)
    
    # Add processed transcript
    if transcript_name not in ctx["processed_transcripts"]:
        ctx["processed_transcripts"].append(transcript_name)
    
    # Add script summary if provided
    if script_summary:
        ctx["previous_scripts"].append(script_summary)
        # Keep last 10 scripts
        ctx["previous_scripts"] = ctx["previous_scripts"][-10:]
    
    _cs_save_context(ctx)
    return ctx


def _cs_clear_context():
    """Clear context file."""
    ctx = {
        "characters": [],
        "locations": [],
        "key_terms": [],
        "relationships": [],
        "processed_transcripts": [],
        "previous_scripts": []
    }
    _cs_save_context(ctx)
    return ctx


def _do_update_menu():
    """Perform update and return result."""
    script_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = perform_update(script_root)
    if result.get("success"):
        return f"✅ Updated to v{result.get('version', 'unknown')}. Restart listener to apply."
    return f"❌ Update failed: {result.get('error', 'Unknown error')}"

# ─── Helpers ───────────────────────────────────────────────────────────────────
def update_env_var(key, value):
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

def retry(fn, attempts=3, delay=10, desc=""):
    for i in range(attempts):
        log(f"   Attempt {i+1}/{attempts}: {desc}")
        try:
            fn()
            return True
        except Exception as e:
            if i < attempts - 1:
                log(f"   Failed: {e}, retrying in {delay}s...")
                time.sleep(delay)
                delay *= 2
    return False

def count_files(pattern):
    return len(glob.glob(pattern))

def fmt_dur(seconds):
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    return f"{h}h {m}m"

def delete_partial_files():
    count = 0
    for pattern in ["*.part", "*.part-*.part", "*.ytdl", "*.f*.mp4.part"]:
        for d in [MEDIA_DIR, SCRIPTS_DIR, TTS_DIR, SHORTS_DIR]:
            for f in glob.glob(os.path.join(d, pattern)):
                os.remove(f)
                count += 1
    return count

def cleanup_all_files():
    """Delete generated files but keep scripts and cogitator data for learning."""
    count = 0
    for d in [MEDIA_DIR, TRANSCRIPTS_DIR, TTS_DIR, SHORTS_DIR, ASSEMBLY_DIR]:
        for f in glob.glob(os.path.join(d, "**/*"), recursive=True):
            if os.path.isfile(f):
                try:
                    os.remove(f)
                    count += 1
                except OSError:
                    pass
    log("Cleanup complete (scripts and cogitator data preserved for learning)")
    return count

def run(cmd, check=True):
    return subprocess.run(cmd, capture_output=True, text=True, check=check, env=os.environ.copy())

# ─── Download from URL ───────────────────────────────────────────────────────
def download_from_url(url: str) -> bool:
    """Download video or playlist from a URL."""
    set_status("Downloading from URL...")
    log(f"Downloading from URL: {url}")
    notify(f"Download Started: {url}")
    
    os.makedirs(MEDIA_DIR, exist_ok=True)
    
    def do_dl():
        r = run([
            "yt-dlp",
            "--cookies-from-browser", "chrome",
            "-f", "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
            "--merge-output-format", "mp4",
            "-o", f"{MEDIA_DIR}/%(title)s.%(ext)s",
            "--progress",
            url
        ], check=False)
        return r
    
    result = do_dl()
    
    if result.returncode != 0:
        log_error(f"Download failed: {result.stderr}")
        notify(f"Download Failed: {result.stderr[:200]}")
        set_status("Download FAILED")
        return False
    
    downloaded_files = list(glob.glob(os.path.join(MEDIA_DIR, "*.mp4")))
    downloaded_files += list(glob.glob(os.path.join(MEDIA_DIR, "*.mk4")))
    downloaded_files += list(glob.glob(os.path.join(MEDIA_DIR, "*.webm")))
    
    if downloaded_files:
        latest = max(downloaded_files, key=os.path.getmtime)
        log(f"Download complete: {os.path.basename(latest)}")
        notify(f"Download Complete: {os.path.basename(latest)}")
        set_status("Download Complete")
        return True
    else:
        log_error("Download completed but no video file found")
        notify("Download Failed: No file found")
        set_status("Download FAILED")
        return False

# ─── Phase 1: Download ────────────────────────────────────────────────────────
# ─── Phase 1: Download ─────────────────────────────────────────────────────────

def phase_download():
    set_status("Phase 1: Downloading video...")
    log("Phase 1: Downloading 1440p stream...")
    notify("Phase 1 Started: Downloading video...")

    playlist_url = env("PLAYLIST_URL")
    if not playlist_url:
        log_error("Phase 1 Failed: PLAYLIST_URL not configured")
        notify("Phase 1 Failed: PLAYLIST_URL not set in .env")
        set_status("Phase 1 FAILED")
        raise RuntimeError("PLAYLIST_URL not configured")

    if playlist_url.lstrip().startswith("--"):
        log_error("Phase 1 Failed: PLAYLIST_URL starts with '--' (possible injection)")
        notify("Phase 1 Failed: PLAYLIST_URL is invalid")
        set_status("Phase 1 FAILED")
        raise RuntimeError("PLAYLIST_URL starts with '--'")

    cookies_ok = run(["yt-dlp", "--cookies-from-browser", "chrome", "--dump-single-json", "https://youtube.com"], check=False)
    if cookies_ok.returncode != 0:
        log_error("Phase 1 Failed: Chrome cookies not available. Run 'yt-dlp --cookies-from-browser chrome --dummy https://youtube.com' to create cookies.")
        notify("Phase 1 Failed: Chrome cookies not available")
        set_status("Phase 1 FAILED")
        raise RuntimeError("Chrome cookies not available")

    set_progress(1, 10, "Downloading video")

    # Check for a pending download URL (set by UI/backend)
    pending_file = os.path.join(os.path.expanduser("~/.cogitator"), "pending_download.txt")
    pending_url = ""
    if os.path.exists(pending_file):
        try:
            with open(pending_file) as f:
                pending_url = f.read().strip()
        except OSError:
            pass
        if pending_url:
            log(f"Using pending download URL: {pending_url}")
        else:
            log("Pending download file is empty, ignoring")

    def do_dl():
        if pending_url:
            os.makedirs(MEDIA_DIR, exist_ok=True)
            log(f"Downloading from URL: {pending_url}")
            set_progress(1, 30, "Downloading video")
            r = run(["yt-dlp",
                     "--cookies-from-browser", "chrome",
                     "-f", "bestvideo+bestaudio",
                     "-o", f"{MEDIA_DIR}/%(title)s.%(ext)s",
                     pending_url])
            log(r.stdout[-500:] if r.stdout else "")
            if r.returncode != 0 and r.stderr:
                log_error(f"yt-dlp error: {r.stderr[-300:]}")
            set_progress(1, 80, "Downloading video")
        elif playlist_url:
            raw_index = env("PLAYLIST_INDEX", "1")
            try:
                playlist_index = str(int(raw_index))
            except (ValueError, TypeError):
                log_error(f"Phase 1 Failed: Invalid PLAYLIST_INDEX '{raw_index}'")
                raise RuntimeError("Invalid PLAYLIST_INDEX")
            os.makedirs(MEDIA_DIR, exist_ok=True)
            set_progress(1, 30, "Downloading video")
            r = run(["yt-dlp", "--playlist-items", playlist_index,
                     "--cookies-from-browser", "chrome",
                     "-f", "bestvideo+bestaudio",
                     "-o", f"{MEDIA_DIR}/%(title)s.%(ext)s",
                     playlist_url])
            log(r.stdout[-500:] if r.stdout else "")
            if r.returncode != 0 and r.stderr:
                log_error(f"yt-dlp error: {r.stderr[-300:]}")
            set_progress(1, 80, "Downloading video")
        else:
            log_error("Phase 1 Failed: No URL to download")
            raise RuntimeError("No URL to download")

    if not retry(do_dl, 3, 10, "Download video"):
        log_error("Phase 1 failed after 3 attempts")
        notify("Phase 1 Failed: Download failed after 3 attempts")
        set_status("Phase 1 FAILED")
        raise RuntimeError("Phase 1 failed")

    video = find_video()
    if not video:
        log_error("Phase 1 Failed: No video file found after download")
        notify("Phase 1 Failed: No video downloaded")
        set_status("Phase 1 FAILED")
        raise RuntimeError("No video found after download")

    # Clean up pending download file
    if pending_url:
        try:
            if os.path.exists(pending_file):
                os.remove(pending_file)
        except OSError:
            pass

    set_status("Phase 1 Complete")
    notify("Phase 1 Complete: Video downloaded")

# ─── Phase 2: Transcribe ──────────────────────────────────────────────────────
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
        
        # STILL extract context even if transcript exists
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
                    notify(f"📚 Context extracted: {len(final.get('characters', []))} chars, {len(final.get('locations', []))} locs, {len(final.get('relationships', []))} rels")
                    
                    # Mine to MemPalace
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
        # Optimized settings per research:
        # - beam_size=5: better decoding than default
        # - temperature=0.2: lower = more deterministic
        # - condition_on_previous_text=True: helps with continuity
        # - VAD with 500ms silence: removes non-speech
        segments, info = model.transcribe(
            video,
            language="en",
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            beam_size=5,
            temperature=0.2,
            condition_on_previous_text=True,
            word_timestamps=True,
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
        word_list = []
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
                    for w in (segment.words or []):
                        word_text = w.word.strip() if hasattr(w, 'word') else ''
                        if word_text:
                            word_list.append({"word": word_text, "start": w.start, "end": w.end})
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
            json.dump({"segments": seg_list, "words": word_list}, json_f)
        
        # Post-process: Correct known gaming ASR errors
        _correct_transcript_asr_errors(json_path)
        
        log("faster-whisper transcription complete")
        transcription_success = True

        # Free WhisperModel memory — it can use several GB
        try:
            del model
        except NameError:
            pass
        gc.collect()
        
        # Extract context from transcript after successful transcription
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
                notify(f"📚 Context extracted: {len(final.get('characters', []))} chars, {len(final.get('locations', []))} locs, {len(final.get('relationships', []))} rels")
                
                # Mine to MemPalace
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

# ─── Phase 3: Context Only (Extract/Update Context) ─────────────────────────
def phase_context():
    """Extract or update context from existing transcript - no transcription needed."""
    json_file = None
    
    # Find existing transcript
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
    
    # Extract text from transcript
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
    
    # Extract context
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
        comparison = compare_context_with_history(game_title, extracted)
        if comparison.get("needs_confirmation"):
            log(f"Context changes detected for {game_title} - merged and saved")
        else:
            log(f"Context verified (merged with existing)")

    set_status("Phase 3 Complete")
    log(f"Context extracted: {len(final.get('characters', []))} chars, {len(final.get('locations', []))} locs, {len(final.get('relationships', []))} rels")
    notify(f"✅ Phase 3 Complete: Context extracted\n📝 {len(final.get('characters', []))} chars\n📍 {len(final.get('locations', []))} locs\n👥 {len(final.get('relationships', []))} rels")
    set_status("Phase 3 Complete")

# ─── Phase 4: Scripts ─────────────────────────────────────────────────────────

SCRIPT_PERSPECTIVES = [
    "Focus on the villain's motive — why did they do what they did?",
    "Focus on the hero's fatal mistake — what went wrong and why",
    "Focus on what the player/viewer missed — the hidden detail",
    "Focus on the cost of the outcome — who paid the real price",
    "Focus on the turning point — the one moment everything changed",
    "Focus on the emotional undercurrent — what the characters felt but never said",
    "Focus on the consequence — what happened after the dust settled",
    "Focus on the mystery — what remains unexplained",
    "Focus on the moral dilemma — what choices were made and why",
    "Focus on the ripple effect — how one event changed everything",
]

SCRIPT_VARIANTS = {
    "mystery_recap": {
        "style": "Mystery Recap",
        "voice_style": "Speak with intrigue and mystery. Drop hints naturally through sentences, not mysterious fragments. Build suspense through the story flow.",
        "instruction": """Write a mystery recap in complete, natural sentences. Start with a hook that creates curiosity in the first sentence. Tell the story chronologically while hinting at secrets. Include a mid-way transition that moves the story forward — vary the phrasing each time, never repeat the same transition. End by looping back to your opening. Target 150-300 words.""",
    },
    "breakdown": {
        "style": "Breakdown",
        "voice_style": "Speak confidently and authoritatively. Explain causes and effects clearly, like an expert sharing knowledge.",
        "instruction": """Write an analytical breakdown. Start with a hook that states a surprising insight in the first sentence. Explain WHY things happened, not just WHAT. Connect cause and effect in flowing paragraphs. Use varied mid-script pivots — never the same transition phrase twice. End with a takeaway. Target 150-300 words.""",
    },
    "timeline": {
        "style": "Timeline",
        "voice_style": "Speak with urgency and forward momentum. Keep the story moving, build to the climax naturally.",
        "instruction": """Write a chronological timeline. Hook viewers immediately with a dramatic moment or outcome. Tell events in order from beginning to climax. Each sentence should flow naturally into the next. Build momentum through time progression. Vary your transitional phrases across scripts — never repeat the same pivot. End with resolution. Target 150-300 words.""",
    },
    "lesson": {
        "style": "Moral/Lesson",
        "voice_style": "Speak thoughtfully and reflectively. Like sharing wisdom with a friend, measured and genuine.",
        "instruction": """Write a reflective lesson. Hook with a bold statement about what was learned. Explain what happened and what could have been different. Use complete sentences that flow naturally. Use unique phrasing for each insight pivot — no repeated transition patterns. End with a thought-provoking question. Target 150-300 words.""",
    },
    "narrative": {
        "style": "Narrative",
        "voice_style": "Speak naturally like telling a story to a friend. Conversational, engaging, keep the flow moving.",
        "instruction": """Write a first-person narrative as if telling a friend what happened. Hook immediately with something surprising or emotional. Use vivid but natural descriptions. Flow from one moment to the next. Use fresh, varied pivot phrases — never the same one twice. Loop the ending back to the hook. Target 150-300 words.""",
    },
    "news_report": {
        "style": "News Report",
        "voice_style": "Speak like a professional news reporter. Clear, factual, objective. Present information in order of importance.",
        "instruction": """Write a professional news report. Lead with the key fact or breaking news in the first sentence - no introductions. Add context in flowing paragraphs. Use objective, factual language. Vary your analytical pivot phrases across scripts. End with impact. Target 150-300 words.""",
    },
    "documentary": {
        "style": "Documentary",
        "voice_style": "Speak like a documentary host. Informed, warm, educational. Add context naturally.",
        "instruction": """Write a documentary-style narration. Start with a hook that reveals something fascinating. Add historical or psychological context naturally through flowing paragraphs. Use fresh narrative pivots each time — no repeated phrases. End with a lasting insight. Target 150-300 words.""",
    },
    "true_crime": {
        "style": "True Crime",
        "voice_style": "Speak with investigative intensity. Build tension through the story, pause for effect naturally.",
        "instruction": """Write a true crime story. Hook with a shocking detail or question in the first sentence. Build investigation and tension through natural sentences. Vary your tension-building transitions — never repeat the same pivot. End with revelation. Target 150-300 words.""",
    },
    "character_pov": {
        "style": "Character POV",
        "voice_style": "Speak as if you ARE the character. Personal, emotional, raw. First person, genuine.",
        "instruction": """Write from the main character's perspective. Hook with an immediate emotional moment or realization. Show internal thoughts and feelings in first person. Make it personal and intimate. Use unique emotional pivots each time — no repeated phrasing. End with emotional payoff. Target 150-300 words.""",
    },
    "true_story": {
        "style": "True Story",
        "voice_style": "Speak like sharing an incredible true story. Authentic, amazed, grounded. Let the facts speak for themselves.",
        "instruction": """Write a true story narration. Hook with the most unbelievable true detail from the transcript. Let the facts carry the drama — no embellishment needed. Present events as they happened, with natural amazement at what's real. Use varied transitions between story beats. End with the real outcome that makes it all stranger than fiction. Target 150-300 words.""",
    },
}

HOOK_ARCHETYPES = {
    "mystery_recap": "Curiosity Gap — start with 'What if...' or 'The real reason...'",
    "breakdown": "Bold Statement — start with 'Here is why...' or 'The real reason...'",
    "timeline": "Pattern Interrupt — start with a dramatic moment out of context, then rewind",
    "lesson": "Question Hook — start with 'What if...' or 'Would you...'",
    "narrative": "Emotional Hook — start with a visceral, relatable moment or realization",
    "news_report": "Bold Statement — lead with the most surprising fact from the transcript",
    "documentary": "Curiosity Gap — start with 'Few people know...' or 'What most players miss...'",
    "true_crime": "Question Hook — start with a shocking question or ominous statement",
    "character_pov": "Emotional Hook — start with 'I never expected...' or an intimate realization",
    "true_story": "Curiosity Gap — start with 'This actually happened...' or 'The craziest part is...'",
}


def _get_variant_performance_text(variant_key):
    """Get performance context text for a variant based on historical data."""
    stats = _LEARNING_VARIANT_STATS
    if not stats or variant_key not in stats:
        return ""

    data = stats[variant_key]
    count = data.get('script_count', 0)
    avg_views = data.get('avg_views', 0)
    avg_eng = data.get('avg_engagement', 0)
    avg_score = data.get('avg_score', 0)

    if count < 1:
        return ""

    lines = [
        "",
        "PERFORMANCE CONTEXT (learned from YouTube data):",
        f"- This script style ('{variant_key}') has been used {count} time(s)",
        f"- Average engagement: {avg_eng:.1f}%, Average views: {avg_views:.0f}",
        f"- Performance score: {avg_score:.1f}/100",
    ]

    optimal_range = _LEARNING_OPTIMIZED_PARAMS.get('optimal_duration_range', (30, 60))
    if optimal_range:
        lines.append(f"- Target clip duration: {optimal_range[0]}-{optimal_range[1]}s for best performance")

    hook_weight = _LEARNING_OPTIMIZED_PARAMS.get('hook_strength_weight', 1.0)
    if hook_weight and hook_weight != 1.0:
        lines.append(f"- Hook strength weight: {hook_weight:.1f}x (higher = stronger hooks recommended)")

    return "\n".join(lines) + "\n"


def _get_mempalace_prompt_hints(game_title):
    """Get MemPalace context for injection into prompts.
    
    Uses the enhanced mempalace_integration module for:
    - Cross-game entity merging
    - Timeline-aware scripting
    - Learned corrections
    - Context-aware memory retrieval
    - Relationship inference
    """
    if not game_title:
        return ""

    try:
        from workflows.mempalace_integration import get_all_mempalace_context
        context = get_all_mempalace_context(game_title)
        if context:
            return f"\n[MEMORY CONTEXT]\n{context}\n"
    except ImportError:
        pass

    # Fallback to basic MemPalace if integration module not available
    if not MEMPALACE_AVAILABLE:
        return ""

    hints = []
    try:
        mp_manager = get_mempalace_manager()
        if mp_manager:
            best = mp_manager.get_best_prompts(game_title, top_n=3)
            if best:
                hints.append("\nMEMORY CONTEXT (from learned experience):")
                for item in best[:2]:
                    src = item.get('source', '')
                    if src:
                        hints.append(f"- Past successful prompt patterns detected for '{src}'")

            memory = mp_manager.get_game_memory(game_title)
            # Fix: get_game_memory returns {"success": True, "memories": [...]}
            if memory.get('success') and memory.get('memories'):
                memories = memory['memories'][:3]
                for m in memories:
                    text = m.get('text', '')[:200]
                    if text and len(text) > 20:
                        hints.append(f"- Game memory: {text}...")

    except Exception:
        pass

    return "\n".join(hints) + "\n" if hints else ""


MULTI_VARIANT_DELIMITER = "=====VARIANT BREAK====="


def _parse_multi_variant_response(response):
    """Parse a multi-variant Groq response into separate script texts."""
    if not response:
        return []
    parts = response.split(MULTI_VARIANT_DELIMITER)
    variants = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Must have at least a TITLE: line and some body text to be valid
        if re.search(r'^TITLE:\s*\S', part, re.MULTILINE) and len(part.split()) > 20:
            variants.append(part)
    return variants


def _postprocess_script(script):
    """Clean up script output: strip scratchpad, fix flat format, remove repetitive CTAs."""
    if not script:
        return script

    # Step 1: Strip scratchpad block (and anything before the final output)
    script = re.sub(r'<scratchpad>.*?</scratchpad>\s*', '', script, count=1, flags=re.DOTALL)
    script = script.strip()

    # Step 2: Parse TITLE, DESCRIPTION, TAGS lines
    title_m = re.search(r'^TITLE:\s*(.*)', script, re.MULTILINE)
    desc_m  = re.search(r'^DESCRIPTION:\s*(.*)', script, re.MULTILINE)
    tags_m  = re.search(r'^TAGS:\s*(.*)', script, re.MULTILINE)

    title = title_m.group(1).strip() if title_m else ""
    desc  = desc_m.group(1).strip()  if desc_m else ""
    tags  = tags_m.group(1).strip()  if tags_m else ""

    # Step 3: Find the body. It should be after the TAGS: line (or DESCRIPTION: if no TAGS).
    body = ""
    if tags_m:
        body = script[tags_m.end():].strip()
    elif desc_m:
        body = script[desc_m.end():].strip()
    elif title_m:
        body = script[title_m.end():].strip()

    # Step 4: If body is empty, check if it's embedded in the DESCRIPTION line after TAGS:
    if not body and desc:
        tags_in_desc = re.search(r'\bTAGS:\s*(.*)', desc)
        if tags_in_desc:
            tags_raw = tags_in_desc.group(1).strip()
            desc = desc[:tags_in_desc.start()].strip()
            desc = re.sub(r'\s+#\w+(?:\s+#\w+)*\s*$', '', desc).strip()
            # Tags are comma-separated. Walk from the START to find where body text begins.
            # Body text starts at the first part that reads like narrative prose.
            tag_parts = [p.strip() for p in tags_raw.split(',')]
            body_start_idx = len(tag_parts)
            for idx, part in enumerate(tag_parts):
                words = part.split()
                if len(words) < 5:
                    continue
                # A part is body text if it contains sentence punctuation, a question,
                # or starts with a known narrative sentence word (even after a stray prefix).
                stripped = re.sub(r'^\S+\s+', '', part)
                if (re.match(r'^(What|The|This|That|How|Why|But|And|So|Here|There|It'
                             r'|In|On|At|When|Where|Who|Which|After|Before|During|While'
                             r'|Despite|Although)\b', part, re.IGNORECASE)
                    or re.match(r'^(What|The|This|That|How|Why|But|And|So|Here|There|It'
                                r'|In|On|At|When|Where|Who|Which|After|Before|During|While'
                                r'|Despite|Although)\b', stripped, re.IGNORECASE)
                    or '?' in part
                    or part.endswith(('.', '?', '!'))):
                    body_start_idx = idx
                    break
            if body_start_idx < len(tag_parts):
                body_parts = tag_parts[body_start_idx:]
                body = ' '.join(body_parts)
                # Drop leading stray words before the first narrative sentence word
                _narrative_re = re.compile(
                    r'^(What|The|This|That|How|Why|But|And|So|Here|There|It'
                    r'|In|On|At|When|Where|Who|Which|After|Before|During|While'
                    r'|Despite|Although)\b', re.IGNORECASE
                )
                body_words = body.split()
                for _i, _w in enumerate(body_words):
                    if _narrative_re.match(_w):
                        body = ' '.join(body_words[_i:])
                        break
                tags = ', '.join(tag_parts[:body_start_idx])
            else:
                tags = tags_raw

    # Step 4.5: Strip repetitive CTAs from description too
    _cta_re = re.compile(
        r'\s*(follow for (more|the latest|updates|our).*|'
        r'stay tuned for more|'
        r'subscribe for more|'
        r"that's all for now|"
        r'see you in the next one|'
        r'thanks for watching|'
        r'don\'t forget to (like|subscribe)).*$',
        re.IGNORECASE
    )
    if desc:
        desc = _cta_re.sub('', desc).strip().rstrip(',;:.')

    # Step 5: Strip repetitive CTAs from the end of body
    if body:
        body = _cta_re.sub('', body).strip().rstrip(',;:.')
        if body:
            # Add terminal period if missing
            if not body[-1] in '.!?':
                body += '.'
            # Clean up leading conjunctions and capitalize
            body = re.sub(r'^(and|but|so|or|nor|yet)\s+', '', body, flags=re.IGNORECASE).strip()
            if body and body[0].islower():
                body = body[0].upper() + body[1:]

    # Step 6: Reconstruct in proper format
    result = ""
    if title:
        result += f"TITLE: {title}\n\n"
    if desc:
        result += f"DESCRIPTION: {desc}\n"
    if tags:
        result += f"TAGS: {tags}\n"
    if body:
        if desc or tags:
            result += "\n"
        result += body

    return result.strip()


def _build_script_prompt(variant_key, perspective, game_title, transcript, context=None, recent_titles=None):
    """Build script prompt using Jinja2 templates (Phase 1) with fallback to legacy."""
    variant = SCRIPT_VARIANTS[variant_key]
    env = _get_prompt_env()

    learned = get_learned_constraints(game_title=game_title, content_type="pipeline")
    learned_constraints_text = ""
    if learned.get("negative_constraints") or learned.get("positive_emphasis"):
        learned_constraints_text = "\n\nLEARNED CONSTRAINTS (from previous generation data):\n"
        for nc in learned.get("negative_constraints", []):
            learned_constraints_text += f"- {nc}\n"
        for pe in learned.get("positive_emphasis", []):
            learned_constraints_text += f"- {pe}\n"

    perf_context = _get_variant_performance_text(variant_key)
    
    # Add learning insights from relative performance analysis
    try:
        from workflows.performance_database import get_learning_insights
        learning_insights = get_learning_insights()
        if learning_insights.get('has_insights'):
            perf_context += "\n\nLEARNING INSIGHTS (from channel performance):\n"
            for insight in learning_insights.get('insights', []):
                perf_context += f"- {insight}\n"
    except Exception:
        pass
    
    mempalace_hints = _get_mempalace_prompt_hints(game_title)
    hook_archetype = HOOK_ARCHETYPES.get(variant_key, "Strong Hook — grab attention in the first sentence")

    learned_hooks_text = ""
    try:
        learned_hooks = get_learned_hook_examples()
        if learned_hooks:
            learned_hooks_text = "\n".join(f"- \"{h}\"" for h in learned_hooks)
    except Exception:
        pass

    def _build_lore_info(ctx):
        lore = (ctx or {}).get("lore", {})
        if not lore:
            return ""
        parts = []
        plot = lore.get("plot_summary", "")
        if plot:
            parts.append(f"PLOT SUMMARY: {plot[:500]}")
        factions = lore.get("factions", [])
        if factions:
            faction_lines = [f"  - {f.get('name')} ({f.get('alignment', '?')}): {f.get('description', '')[:120]}" for f in factions]
            parts.append("FACTIONS:\n" + "\n".join(faction_lines))
        events = lore.get("key_events", [])
        if events:
            event_lines = [f"  - {e.get('event')}: {e.get('description', '')[:120]}" for e in events]
            parts.append("KEY EVENTS:\n" + "\n".join(event_lines))
        terms = lore.get("lore_terms", [])
        if terms:
            term_lines = [f"  - {t.get('term')} ({t.get('category', '?')}): {t.get('definition', '')[:120]}" for t in terms]
            parts.append("LORE TERMS:\n" + "\n".join(term_lines))
        return "\n\n".join(parts)

    if env is not None:
        try:
            template = env.get_template("base.j2")
            context_info = ""
            if context:
                chars = context.get("characters", [])
                locs = context.get("locations", [])
                terms = context.get("key_terms", [])
                rels = context.get("relationships", [])
                if chars:
                    context_info += f"Characters: {', '.join(chars)}\n"
                if locs:
                    context_info += f"Locations: {', '.join(locs)}\n"
                if terms:
                    context_info += f"Key Terms: {', '.join(terms)}\n"
                if rels:
                    context_info += f"Relationships: {'; '.join(rels)}\n"
                key_events = context.get("key_events", [])
                if key_events:
                    context_info += f"Key Events: {'; '.join(key_events)}\n"
                themes = context.get("themes", [])
                if themes:
                    context_info += f"Themes: {', '.join(themes)}\n"
                tone = context.get("emotional_tone", "")
                if tone:
                    context_info += f"Emotional Tone: {tone}\n"
                char_aliases = context.get("character_aliases", {})
                if char_aliases:
                    alias_lines = []
                    for variant, canonical in char_aliases.items():
                        alias_lines.append(f"  '{variant}' → use '{canonical}'")
                    context_info += "VERIFIED NAME MAPPINGS (use these canonical names, NOT the variants):\n" + "\n".join(alias_lines) + "\n"
                loc_aliases = context.get("location_aliases", {})
                if loc_aliases:
                    alias_lines = []
                    for variant, canonical in loc_aliases.items():
                        alias_lines.append(f"  '{variant}' → use '{canonical}'")
                    context_info += "VERIFIED LOCATION MAPPINGS:\n" + "\n".join(alias_lines) + "\n"

            lore_info = _build_lore_info(context)

            prompt = template.render(
                game_title=game_title,
                style=variant["style"],
                perspective=perspective,
                hook_archetype=hook_archetype,
                instruction=variant["instruction"],
                context_info=context_info,
                lore_info=lore_info,
                transcript=transcript,
                learned_constraints=learned_constraints_text,
                perf_context=perf_context,
                mempalace_hints=mempalace_hints,
                learned_hooks=learned_hooks_text,
                recent_titles="\n".join(recent_titles) if recent_titles else "",
            )
            return prompt
        except Exception as e:
            log(f"   Jinja2 template error: {e}, using legacy prompt")

    # Fallback to legacy f-string prompt
    game_line = f"This is from the game {game_title}.\n\n" if game_title else ""
    hook_archetype_text = f"Hook Archetype: {hook_archetype}\n"
    context_info = ""
    if context:
        chars = context.get("characters", [])
        locs = context.get("locations", [])
        terms = context.get("key_terms", [])
        rels = context.get("relationships", [])
        if chars:
            context_info += f"Characters: {', '.join(chars)}\n"
        if locs:
            context_info += f"Locations: {', '.join(locs)}\n"
        if terms:
            context_info += f"Key Terms: {', '.join(terms)}\n"
        if rels:
            context_info += f"Relationships: {'; '.join(rels)}\n"
        key_events = context.get("key_events", [])
        if key_events:
            context_info += f"Key Events: {'; '.join(key_events)}\n"
        themes = context.get("themes", [])
        if themes:
            context_info += f"Themes: {', '.join(themes)}\n"
        tone = context.get("emotional_tone", "")
        if tone:
            context_info += f"Emotional Tone: {tone}\n"
        char_aliases = context.get("character_aliases", {})
        if char_aliases:
            alias_lines = []
            for variant, canonical in char_aliases.items():
                alias_lines.append(f"  '{variant}' → use '{canonical}'")
            context_info += "VERIFIED NAME MAPPINGS (use these canonical names, NOT the variants):\n" + "\n".join(alias_lines) + "\n"
        loc_aliases = context.get("location_aliases", {})
        if loc_aliases:
            alias_lines = []
            for variant, canonical in loc_aliases.items():
                alias_lines.append(f"  '{variant}' → use '{canonical}'")
            context_info += "VERIFIED LOCATION MAPPINGS:\n" + "\n".join(alias_lines) + "\n"

    lore_info = _build_lore_info(context)

    return f"""You are an expert YouTube Shorts scriptwriter specializing in gaming content. {game_line}{context_info}
{learned_constraints_text}
{perf_context}
{mempalace_hints}
{hook_archetype_text}
Style: {variant['style']}
Perspective: {perspective}
{variant['instruction']}

{lore_info}

Target 200-250 words for the spoken script. Maximum 300 words. Every word must earn its place.

STYLE:
- Write in complete, natural sentences. No fragments.
- Narrated speech is allowed: "She told him the truth", "He revealed his plan".
- NO direct quotes with quotation marks.
- NO parentheses, stage directions, or audio annotations.
- NO markdown formatting — plain text only.
- NO creator intros: "Hey guys", "Welcome back", "Today we are looking at".
- NO filler transitions: "In conclusion", "To summarize".
- Prefer active voice over passive. Short sentences (10-15 words average).

FACTUAL ACCURACY:
- NEVER invent character names, stats, dates, or game mechanics.
- NEVER invent background lore not in the transcript.
- ONLY use facts explicitly provided in the source material.

TITLES (6-10 words):
- Must reference a specific detail from the transcript.
- Question marks and exclamation points are allowed.
- Vary title structure: question, statement, contrast, etc.
- Avoid "The [Noun] of [Noun]" structure.
- No all-caps words.

OUTPUT FORMAT:
TITLE: [Your title]
DESCRIPTION: [2-3 sentences summarizing hook, with hashtags at end]
TAGS: [comma-separated keywords]

[Script body starting with the hook. 200-250 words.]

Transcript:
{transcript}"""


def _get_temperature(variant_key):
    """Get adaptive temperature for content type (Phase 5) with learned optimization."""
    base_temp = TEMPERATURE_BY_TYPE.get(variant_key, 0.7)
    
    # Try to get learned optimal temperature
    try:
        learned_temp = calculate_optimal_temperature(content_type=variant_key)
        if learned_temp:
            # Blend learned with base (70% learned, 30% base)
            return round(learned_temp * 0.7 + base_temp * 0.3, 1)
    except Exception:
        pass
    
    return base_temp


def _get_groq_model(variant_key):
    """Get Groq model for content type (Phase 5)."""
    return GROQ_MODELS_BY_TYPE.get(variant_key, GROQ_MODEL)

def _rate_limit():
    now = time.time()
    last = 0
    try:
        with open(LAST_CALL) as f:
            last = float(f.read().strip())
    except (FileNotFoundError, ValueError):
        pass
    wait = 6 - (now - last)
    if wait > 0:
        time.sleep(wait)
    with open(LAST_CALL, "w") as f:
        f.write(str(time.time()))

def _retry_with_backoff(func, max_retries=3, base_delay=2, max_delay=30):
    """Retry a function with exponential backoff for network and HTTP errors."""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            error_str = str(e).lower()
            is_network_error = any(x in error_str for x in [
                'name resolution', 'connection refused', 'connection reset',
                'connection aborted', 'temporary failure', 'timeout',
                'network is unreachable', 'no route to host'
            ])
            is_rate_limit = '429' in error_str or 'rate limit' in error_str
            is_server_error = any(x in error_str for x in ['500', '502', '503', '504'])
            
            if is_rate_limit:
                delay = min(base_delay * (2 ** attempt) * 3, max_delay)
                log(f"   Rate limited, waiting {delay}s before retry...")
                time.sleep(delay)
                continue
            
            if (is_network_error or is_server_error) and attempt < max_retries - 1:
                delay = min(base_delay * (2 ** attempt), max_delay)
                log(f"   Network/server error, retrying in {delay}s... ({attempt+1}/{max_retries})")
                time.sleep(delay)
                continue
            
            raise

def _groq_generate(prompt, max_tokens=500, model=None, temperature=0.7, top_p=None, repetition_penalty=None):
    """Generate text using Groq API with key rotation and adaptive model/temperature."""
    global GROQ_KEY_INDEX
    
    groq_keys = get_groq_keys()
    
    if not groq_keys:
        raise RuntimeError("No Groq API keys configured")
    
    groq_model = model or GROQ_MODEL
    start_key = GROQ_KEY_INDEX
    for i in range(len(groq_keys)):
        key_index = (start_key + i) % len(groq_keys)
        api_key = groq_keys[key_index]
        
        log(f"   Trying Groq key ...{api_key[-6:]} (model: {groq_model}, temp: {temperature})")
        
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": groq_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if top_p is not None:
            data["top_p"] = top_p
        if repetition_penalty is not None:
            data["frequency_penalty"] = (repetition_penalty - 1.0) * 2  # map 1.0-1.3 → 0.0-0.6
        
        def _make_request():
            return requests.post(url, json=data, headers=headers, timeout=60)
        
        try:
            response = _retry_with_backoff(_make_request, max_retries=2, base_delay=3)
            if response.status_code == 200:
                GROQ_KEY_INDEX = key_index
                result = response.json()
                log(f"   Using Groq key ...{api_key[-6:]}")
                return result["choices"][0]["message"]["content"]
            elif response.status_code == 429:
                log(f"   Groq key ...{api_key[-6:]} rate limited, trying next...")
                continue
            else:
                log(f"   Groq key ...{api_key[-6:]} error {response.status_code}")
                continue
        except Exception as e:
            log(f"   Groq key ...{api_key[-6:]} failed: {e}")
            continue
    
    raise RuntimeError("All Groq API keys failed")

def _gemini_script(text, script_num, context=None, recent_titles=None):
    """Generate script using Gemini API with key rotation, context, and validation (Phase 1-2)."""
    keys = get_gemini_keys()
    if not keys:
        raise RuntimeError("No API keys in keychain")

    variant_key, perspective = _get_next_round_robin()
    game_title = env("GAME_TITLE", "")
    temperature = _get_temperature(variant_key)
    llm_params = _get_llm_params(variant_key)
    prompt = _build_script_prompt(variant_key, perspective, game_title, text[:3000], context, recent_titles=recent_titles)
    log(f"   Variant: {SCRIPT_VARIANTS[variant_key]['style']}, Perspective: {perspective[:50]}...")
    log(f"   Temperature: {temperature}, top_p: {llm_params['top_p']}, Context entities: {len(context.get('characters', [])) if context else 0} characters")
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "topP": llm_params['top_p'], "maxOutputTokens": 3072}
    }).encode()

    start = (script_num - 1) % len(keys)
    for i in range(len(keys)):
        key = keys[(start + i) % len(keys)]
        log(f"   Trying key ...{key[-6:]}")
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
        for attempt in range(3):
            try:
                _rate_limit()
                req = urllib.request.Request(url, data=body,
                                             headers={"Content-Type": "application/json", "X-Goog-Api-Key": key})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    r = json.loads(resp.read())
                    return r["candidates"][0]["content"]["parts"][0]["text"]
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 503):
                    wait = (2 ** attempt) * 15 + random.uniform(0, 10)
                    log(f"   HTTP {e.code} with key ...{key[-6:]}, retry {attempt+1}/3 in {wait:.0f}s")
                    time.sleep(wait)
                else:
                    log(f"   HTTP {e.code} with key ...{key[-6:]}")
                    break
            except Exception as e:
                log(f"   Error: {e}")
                time.sleep(5)
                break
        log(f"   Key ...{key[-6:]} failed, next...")
    return None

def _extract_hour(json_file, start, end):
    with open(json_file) as f:
        data = json.load(f)
    parts = []
    for seg in data.get("segments", []):
        if seg["start"] >= start and seg["end"] <= end:
            t = re.sub(r"<[^>]*>", "", seg["text"]).strip()
            if t and len(t.split()) >= 3:
                parts.append(t)
    return "\n".join(parts)

def phase_scripts(json_file, duration, selected, video=None):
    _RECENT_TITLES = load_historical_titles(limit=30)
    _USED_TITLE_STRUCTURES = []
    _TITLE_GUIDANCE = build_title_guidance(_RECENT_TITLES, _USED_TITLE_STRUCTURES, historical=_RECENT_TITLES)
    video_basename = os.path.splitext(os.path.basename(video))[0] if video else "script"
    if not json_file or not os.path.exists(json_file):
        log_error("Phase 4 Failed: Transcript file not found")
        notify("Phase 4 Failed: No transcript available")
        set_status("Phase 4 FAILED")
        raise RuntimeError("Transcript file not found")

    keys = get_gemini_keys()
    if not keys:
        log_error("Phase 4 Failed: No API keys in keychain")
        notify("Phase 4 Failed: No API keys configured")
        set_status("Phase 4 FAILED")
        raise RuntimeError("No API keys available")

    num_hours = len(selected)
    _init_round_robin(num_hours)
    
    # Load and optimize context for script generation (Phase 4)
    ctx = _cs_load_context()
    # Preserve alias maps before summarize_context strips them
    _char_aliases = ctx.get("character_aliases", {})
    _loc_aliases = ctx.get("location_aliases", {})
    ctx = summarize_context(ctx, max_per_category=10)
    ctx["character_aliases"] = _char_aliases
    ctx["location_aliases"] = _loc_aliases
    log(f"   Context loaded: {len(ctx.get('characters', []))} chars, {len(ctx.get('locations', []))} locs, {len(ctx.get('key_terms', []))} terms")
    
    # Get verified context for validation
    game_title = env("GAME_TITLE", "")
    verified_ctx = get_verified_context_for_validation(game_title)
    
    # Merge lore from verified context into working context
    if verified_ctx and verified_ctx.get("lore"):
        ctx["lore"] = verified_ctx["lore"]
        log(f"   Game lore loaded: {len(ctx['lore'].get('characters', []))} chars, {len(ctx['lore'].get('factions', []))} factions")

    # Merge: prefer verified context for validation
    validation_ctx = {}
    if verified_ctx:
        validation_ctx = {
            "characters": verified_ctx.get("characters", ctx.get("characters", [])),
            "locations": verified_ctx.get("locations", ctx.get("locations", [])),
            "key_terms": ctx.get("key_terms", []),
            "relationships": verified_ctx.get("relationships", ctx.get("relationships", []))
        }
    else:
        validation_ctx = ctx
    
    set_status("Phase 4: Generating scripts...")
    log("Phase 4: Generating scripts (one per hour, Groq primary, Gemini fallback)...")
    notify(f"Phase 4 Started: Generating {num_hours} scripts...")
    delay = int(env("SCRIPT_DELAY", "300"))

    scripts_generated = 0
    for slot, interval in enumerate(selected, 1):
        i = interval['index'] + 1
        pct = int(((slot - 1) / num_hours) * 100)
        set_progress(4, pct, f"Generating scripts ({slot}/{num_hours})")
        
        padded = f"{slot:03d}"
        h_start = interval['start']
        h_end = interval['end']
        out     = os.path.join(SCRIPTS_DIR, f"{video_basename}-Script{padded}.txt")

        if os.path.exists(out):
            log(f"   Skipping script {i} (exists)")
            scripts_generated += 1
            continue

        try:
            log(f"   Processing hour {i}: {h_start}s - {h_end}s")
            text = _extract_hour(json_file, h_start, h_end)
            if not text:
                log(f"   Warning: No transcript for hour {i}, skipping")
                continue

            transcript_text = text[:3000]
            variant_key, perspective = _get_next_round_robin()
            groq_model = _get_groq_model(variant_key)
            temperature = _get_temperature(variant_key)
            llm_params = _get_llm_params(variant_key)

            # Phase 4: Optimize context relevance for this specific transcript
            relevant_ctx = score_context_relevance(ctx, transcript_text, max_items=8)
            # Preserve alias maps through relevance scoring
            relevant_ctx["character_aliases"] = ctx.get("character_aliases", {})
            relevant_ctx["location_aliases"] = ctx.get("location_aliases", {})

            # Structured transcript summarization — replaces raw truncated text with a
            # condensed narrative summary, also providing key_events, themes, tone
            script_summary = None
            if len(text) > 500:
                log(f"   Summarizing transcript ({len(text)} chars)...")
                try:
                    script_summary = _summarize_transcript(text, env("GAME_TITLE", ""))
                    if script_summary:
                        narrative = script_summary.get("narrative_summary", "")
                        if narrative and len(narrative) > 100:
                            transcript_text = narrative
                            log(f"   Using narrative summary ({len(narrative)} chars)")
                            # Inject structured summary fields into context for the prompt builder
                            ke = script_summary.get("key_events", [])
                            if ke:
                                relevant_ctx["key_events"] = ke
                            th = script_summary.get("themes", [])
                            if th:
                                relevant_ctx["themes"] = th
                            tone = script_summary.get("emotional_tone", "")
                            if tone:
                                relevant_ctx["emotional_tone"] = tone
                        else:
                            log(f"   Summary too short, falling back to raw transcript")
                            script_summary = None
                except Exception as sum_err:
                    log(f"   Transcript summarization failed: {sum_err}")
                    script_summary = None

                finally:
                    gc.collect()

            # Inject MemPalace memory into context
            if MEMPALACE_AVAILABLE and env("MEMORY_ENABLED", "true").lower() == "true":
                game_title = env("GAME_TITLE", "")
                if game_title and game_title != "Unknown Game":
                    try:
                        mp_manager = get_mempalace_manager()
                        if mp_manager:
                            game_memory = mp_manager.get_game_memory(game_title)
                            if game_memory and game_memory.get("success"):
                                log(f"MemPalace: Retrieved memory for {game_title}")
                    except Exception as mp_err:
                        log(f"MemPalace: Memory injection failed - {mp_err}")

            best_script = None
            best_metadata = None
            candidates = []
            fact_check = {"score": 1.0, "issues": []}

            title_prompt_lines = []
            if _TITLE_GUIDANCE:
                title_prompt_lines.extend(_TITLE_GUIDANCE.splitlines())
            title_prompt_lines.extend(_RECENT_TITLES[-20:])
            prompt = _build_script_prompt(variant_key, perspective, env("GAME_TITLE", ""), transcript_text, relevant_ctx, recent_titles=title_prompt_lines)

            # Primary: Groq multi-variant (1 call, 2 variants)
            multi_prompt = prompt + """

Generate TWO complete variants of this script separated by the exact delimiter:
=====VARIANT BREAK=====

Each variant must have its own TITLE, DESCRIPTION, TAGS, and body following the same format."""
            try:
                groq_response = _groq_generate(multi_prompt, max_tokens=1500, model=groq_model, temperature=temperature, top_p=llm_params['top_p'], repetition_penalty=llm_params['repetition_penalty'])
                if groq_response:
                    variants = _parse_multi_variant_response(groq_response)
                    if variants:
                        for idx, v in enumerate(variants):
                            candidates.append((v, {"source": "groq", "model": groq_model, "temperature": temperature, "variant": idx + 1}))
                            log(f"   Groq variant {idx + 1} generated ({len(v.split())} words)")
                    else:
                        candidates.append((groq_response, {"source": "groq", "model": groq_model, "temperature": temperature}))
                        log(f"   Groq script generated ({len(groq_response.split())} words)")
            except Exception as e:
                log(f"   Groq generation failed: {e}, trying Gemini")

            # Fallback: Gemini (single script) if Groq produced nothing
            if not candidates:
                gemini_script = _gemini_script(transcript_text, slot, relevant_ctx, recent_titles=_RECENT_TITLES)
                if gemini_script:
                    candidates.append((gemini_script, {"source": "gemini", "model": "gemini-2.5-flash-lite", "temperature": temperature}))
                    log(f"   Gemini script generated ({len(gemini_script.split())} words)")

            if candidates:
                best_script, best_metadata, scores = select_best_script(candidates, ctx)
                if scores and len(scores) > 1:
                    log(f"   Selected best script from {len(scores)} candidates (score: {scores[0]['combined']})")
                    for idx, s in enumerate(scores):
                        log(f"   Candidate {idx+1}: factuality={s['factuality']['score']}, engagement={s['engagement']['overall']}, combined={s['combined']}")
            else:
                log(f"   Warning: All generation failed for hour {i}, using raw transcript")
                best_script = transcript_text
                best_metadata = {"source": "raw_transcript"}

            if best_script and best_metadata.get("source") != "raw_transcript":
                fact_check = validate_script_factuality(best_script, validation_ctx)
                engagement = score_engagement(best_script)
                log(f"   Script {i} quality: factuality={fact_check['score']}, engagement={engagement['overall']}, words={len(best_script.split())}")
                if fact_check["issues"]:
                    for issue in fact_check["issues"]:
                        log(f"   WARNING: {issue}")

                # Retry on low factuality — one regeneration attempt with stricter guidance
                if fact_check["score"] < 0.5 and best_metadata.get("source") in ("groq", "gemini"):
                    log(f"   Retrying script {i} due to low factuality ({fact_check['score']})...")
                    flagged = fact_check.get("flagged_entities", [])
                    flagged_str = ", ".join(str(e) for e in flagged[:10]) if flagged else "unknown entities"
                    retry_prompt = prompt + f"\n\nCRITICAL: The previous script contained factual errors. The following were NOT found in the transcript and must NOT appear: {flagged_str}. ONLY use information from the transcript above."
                    try:
                        retry_script = _groq_generate(retry_prompt, max_tokens=500, model=groq_model, temperature=temperature * 0.8, top_p=llm_params['top_p'], repetition_penalty=llm_params['repetition_penalty'])
                        if retry_script:
                            retry_fact = validate_script_factuality(retry_script, validation_ctx)
                            if retry_fact["score"] > fact_check["score"]:
                                best_script = retry_script
                                fact_check = retry_fact
                                log(f"   Retry improved factuality to {retry_fact['score']}")
                    except Exception as retry_err:
                        log(f"   Retry generation failed: {retry_err}")

                log_generation_metrics(best_script, best_metadata, fact_check, engagement, METRICS_FILE)
                
                game_title = env("GAME_TITLE", "")
                store_generation_failure(best_script, best_metadata, fact_check, engagement, game_title=game_title, content_type=variant_key)
                
                if MEMPALACE_AVAILABLE and env("MEMORY_ENABLED", "true").lower() == "true":
                    try:
                        mp_manager = get_mempalace_manager()
                        if mp_manager:
                            game_title = env("GAME_TITLE", "")
                            metric = {
                                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                                'hour': i,
                                'source': best_metadata.get('source'),
                                'model': best_metadata.get('model'),
                                'word_count': len(best_script.split()),
                                'factuality': fact_check.get('score', 0),
                                'engagement': engagement.get('overall', 0),
                                'variant': variant_key,
                                'perspective': perspective
                            }
                            mp_manager.add_quality_metric(game_title, metric)
                            log(f"MemPalace: Logged quality metric for script {i}")
                    except Exception as mp_err:
                        log(f"MemPalace: Quality logging failed - {mp_err}")

            # Post-process: strip scratchpad, fix flat format, remove repetitive CTAs
            cleaned = _postprocess_script(best_script)
            if cleaned and len(cleaned) > 20:
                best_script = cleaned
                log(f"   Script post-processed ({len(best_script.split())} words)")

            # Title variety enforcement
            best_script, _tv_title, _tv_struct = enforce_title_variety(
                best_script, _RECENT_TITLES, _USED_TITLE_STRUCTURES
            )
            if _tv_title:
                log(f"   Title structure: {_tv_struct} → {_tv_title}")
            _TITLE_GUIDANCE = build_title_guidance(
                _RECENT_TITLES, _USED_TITLE_STRUCTURES, historical=_RECENT_TITLES
            )

            # Word count enforcement — preserve TITLE/DESCRIPTION/TAGS, trim body at sentence boundary
            wc = len(best_script.split())
            if wc > 300:
                log(f"   Script {i} exceeds 300 words ({wc}), trimming...")
                header_end = 0
                for prefix in ('TITLE:', 'DESCRIPTION:', 'TAGS:'):
                    m = re.search(rf'^{prefix}.*$', best_script, re.MULTILINE)
                    if m:
                        header_end = max(header_end, m.end())
                header = best_script[:header_end].strip()
                body = best_script[header_end:].strip()
                if body:
                    body_words = body.split()
                    max_words = 280
                    if len(body_words) > max_words:
                        trimmed = ' '.join(body_words[:max_words])
                        # Find last sentence boundary before max_words
                        for sep in ('. ', '? ', '! ', '.\n', '?\n', '!\n'):
                            idx = trimmed.rfind(sep, 0, len(trimmed))
                            if idx > max_words * 4:
                                trimmed = trimmed[:idx + len(sep.rstrip())]
                                break
                        best_script = header + '\n\n' + trimmed
                    log(f"   Trimmed to {len(best_script.split())} words")

            with open(out, "w") as f:
                f.write(best_script)
            wc = len(best_script.split())
            log(f"   Script {i}: {wc} words (source: {best_metadata.get('source', 'unknown')})")
            scripts_generated += 1
            
            # Extract title for DB storage and validation
            title_match = re.search(r'^TITLE:\s*(.+)$', best_script, re.MULTILINE)
            if not title_match:
                log(f"   WARNING: Script {i} missing TITLE: line — recovering from first line...")
                lines = best_script.strip().split('\n')
                for line in lines:
                    stripped = line.strip()
                    if stripped and not stripped.startswith('#'):
                        recovered = stripped[:80]
                        best_script = f"TITLE: {recovered}\n\n{best_script}"
                        log(f"   Recovered title: {recovered}")
                        with open(out, "w") as f:
                            f.write(best_script)
                        break
            else:
                script_title = title_match.group(1)
                log(f"   Script title: {script_title}")
                normalized = normalize_title(script_title)
                _RECENT_TITLES.append(normalized)

            # ── Metadata extraction (title, description, hashtags, tags) ──
            script_metadata = {"title": "", "description": "", "hashtags": [], "tags": [], "variant": variant_key}
            if title_match:
                script_metadata["title"] = title_match.group(1).strip()
            desc_match = re.search(r'^DESCRIPTION:\s*(.+)$', best_script, re.MULTILINE)
            if desc_match:
                desc_text = desc_match.group(1).strip()
                hashtags = re.findall(r'#\w+', desc_text)
                clean_desc = re.sub(r'#\w+\s*', '', desc_text).strip()
                script_metadata["description"] = clean_desc
                script_metadata["hashtags"] = hashtags
            tags_match = re.search(r'^TAGS:\s*(.+)$', best_script, re.MULTILINE)
            if tags_match:
                raw_tags = tags_match.group(1).strip()
                script_metadata["tags"] = [t.strip() for t in raw_tags.split(",") if t.strip()]
            # Fallback when LLM didn't produce DESCRIPTION/TAGS
            if not script_metadata.get("description") or not script_metadata.get("tags"):
                body = best_script
                for prefix in ["TITLE:", "DESCRIPTION:", "TAGS:"]:
                    body = re.sub(rf'^{prefix}.*$', '', body, flags=re.MULTILINE).strip()
                if not script_metadata.get("description") and len(body) > 20:
                    sentences = re.split(r'(?<=[.!?])\s+', body)
                    desc = " ".join(sentences[:2])
                    script_metadata["description"] = desc[:300]
                if not script_metadata.get("tags"):
                    game_title = env("GAME_TITLE", "")
                    game_words = [w for w in re.sub(r'[^a-zA-Z0-9\s]', '', game_title).split() if w]
                    script_metadata["tags"] = game_words + ["gaming", "shorts", "videogames"]
                if not script_metadata.get("hashtags"):
                    script_metadata["hashtags"] = [w.lower() for w in script_metadata["tags"] if w not in ("gaming", "shorts", "videogames")][:5]
            # Inject transcript summary (if generated) into metadata
            if script_summary:
                for _sf_key in ("narrative_summary", "key_events", "characters_mentioned", "themes", "emotional_tone", "recommended_delivery"):
                    _sf_val = script_summary.get(_sf_key)
                    if _sf_val:
                        script_metadata[_sf_key] = _sf_val
            # Factuality gate — quarantine low-quality scripts before TTS/assemble
            try:
                _fact_score = fact_check.get("score", 1.0) if isinstance(fact_check, dict) else 1.0
            except NameError:
                _fact_score = 1.0
            if _fact_score < 0.4:
                script_metadata["quarantined"] = True
                script_metadata["skip_tts"] = True
                script_metadata["review_status"] = "quarantined"
                script_metadata["factuality_score"] = _fact_score
                log(f"   QUARANTINED script {i}: factuality={_fact_score} < 0.4 (skip TTS/assemble)")
            else:
                script_metadata.setdefault("review_status", "pending")
                script_metadata["factuality_score"] = _fact_score
            # Save .meta.json alongside script
            meta_path = out.replace(".txt", ".meta.json")
            try:
                with open(meta_path, "w") as f:
                    json.dump(script_metadata, f, indent=2)
            except Exception as e:
                log(f"   Failed to save metadata: {e}")

            # Store script in performance database for learning
            if PERFORMANCE_DB_AVAILABLE and LEARNING_ENGINE_AVAILABLE:
                try:
                    features = extract_script_features(best_script, variant_key)
                    
                    # Assign A/B test variant
                    ab_test_id = None
                    ab_variant = None
                    if _CURRENT_AB_TEST:
                        from workflows.performance_database import assign_ab_variant
                        ab_test_id = _CURRENT_AB_TEST['test_id']
                        ab_variant = assign_ab_variant(ab_test_id, i)
                    
                    script_id = store_script(
                        video_name=video_basename,
                        content_type=variant_key,
                        script_text=best_script,
                        features=features,
                        variants=candidates if len(candidates) > 1 else [],
                        description=script_metadata.get("description", ""),
                        hashtags=",".join(script_metadata.get("hashtags", [])),
                        tags=",".join(script_metadata.get("tags", [])),
                        game_key=env("GAME_TITLE", ""),
                        ab_test_id=ab_test_id,
                        ab_variant=ab_variant,
                    )
                    
                    if ab_variant:
                        log(f"Performance: Script stored (ID: {script_id[:8]}...) [A/B: variant {ab_variant.upper()}]")
                    else:
                        log(f"Performance: Script stored (ID: {script_id[:8]}...)")
                    set_script_id(slot, script_id)
                except Exception as perf_err:
                    log(f"Performance DB: Failed to store script - {perf_err}")
            set_status(f"Phase 4: Script {slot}/{num_hours} generated")
            notify(f"Script {slot}/{num_hours} generated ({wc} words)")

            # Update context with script summary (Phase 4)
            if best_script and wc > 50:
                summary = f"Script {i}: {best_script[:100]}..."
                _cs_update_context({"characters": [], "locations": [], "key_terms": [], "relationships": []}, f"script_{padded}", summary)
        except Exception as e:
            log_error(f"   Error generating script {i}: {e}")
            continue

        if slot < num_hours:
            log(f"   Waiting {delay}s")
            time.sleep(delay)

    if scripts_generated == 0:
        log_error("Phase 4 Failed: No scripts were generated")
        notify("Phase 4 Failed: No scripts generated")
        set_status("Phase 4 FAILED")
        raise RuntimeError("No scripts generated")

    set_status("Phase 4 Complete")
    notify(f"Phase 4 Complete: {scripts_generated} scripts generated")

# ─── Phase 5: Clips ──────────────────────────────────────────────────────────
def _score_interval(json_file, start, end, verified_context=None):
    """Score a transcript interval for content richness."""
    score = 0.0
    try:
        with open(json_file) as f:
            data = json.load(f)

        words_total = 0
        drama = 0
        text_all = ""

        for seg in data.get("segments", []):
            if seg["start"] < start or seg["end"] > end:
                continue
            t = re.sub(r"<[^>]*>", "", seg.get("text", "")).strip()
            if len(t.split()) < 3:
                continue
            words = len(t.split())
            words_total += words
            drama += t.count("?") * 2 + t.count("!") * 2
            text_all += " " + t

        if words_total == 0:
            return 0.0

        dur = max(end - start, 1)
        density = words_total / dur

        score = words_total + density * 10 + drama

        if verified_context:
            text_lower = text_all.lower()
            chars = verified_context.get("characters", [])
            for c in chars:
                name = c.get("name", "").lower()
                if name and name in text_lower:
                    score += 5
            terms = verified_context.get("key_terms", [])
            for t in terms:
                term = t.get("name", "").lower()
                if term and term in text_lower:
                    score += 3

    except Exception as e:
        log(f"Warning: interval scoring failed: {e}")
    return score


def _select_best_intervals(json_file, duration, num_shorts):
    """Select the best N 30-min intervals from the transcript."""
    interval = 1800
    windows = []
    i = 0
    while i * interval < duration:
        start = i * interval
        end = min((i + 1) * interval, duration)
        windows.append({"index": i, "start": start, "end": end})
        i += 1

    if not windows:
        return [{"index": 0, "start": 0, "end": duration, "score": 0}]

    game_title = env("GAME_TITLE", "")
    verified = None
    if game_title:
        try:
            verified = load_verified_context(game_title)
        except Exception:
            pass

    for w in windows:
        w["score"] = _score_interval(json_file, w["start"], w["end"], verified)

    windows.sort(key=lambda x: x["score"], reverse=True)
    selected = windows[:num_shorts]
    selected.sort(key=lambda x: x["index"])
    return selected


def _extract_scenes(json_file, h_start, h_end):
    scenes = []
    try:
        max_clips = int(env("CLIPS_PER_INTERVAL", "5"))
        max_clips = max(1, min(10, max_clips))
        min_dur, min_words = 30, 15
        max_gap = 15
        max_group_dur = 600

        with open(json_file) as f:
            data = json.load(f)

        def clean(t):
            return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", t)).strip()

        entries = []
        for seg in data.get("segments", []):
            if seg["start"] < h_start or seg["end"] > h_end:
                continue
            t = clean(seg.get("text", ""))
            if len(t.split()) < 3:
                continue
            entries.append({"start": seg["start"], "end": seg["end"],
                            "text": t, "words": len(t.split())})

        if not entries:
            return scenes

        entries.sort(key=lambda x: x["start"])
        groups = [[entries[0]]]
        for j in range(1, len(entries)):
            gap = entries[j]["start"] - entries[j-1]["end"]
            dur = entries[j]["end"] - groups[-1][0]["start"]
            if gap <= max_gap and dur <= max_group_dur:
                groups[-1].append(entries[j])
            else:
                groups.append([entries[j]])

        for grp in groups:
            words = sum(e["words"] for e in grp)
            dur = grp[-1]["end"] - grp[0]["start"]
            if words < min_words or dur < min_dur:
                continue
            density = words / max(dur, 1)
            txt = " ".join(e["text"] for e in grp)
            drama = txt.count("?") * 2 + txt.count("!") * 2
            score = words + density * 10 + drama

            optimal_range = _LEARNING_OPTIMIZED_PARAMS.get('optimal_duration_range', (30, 60))
            if optimal_range:
                opt_min, opt_max = optimal_range
                if opt_min <= dur <= opt_max:
                    score += 15
                elif 20 <= dur < opt_min or opt_max < dur <= 90:
                    score += 8

            scenes.append({
                "start": max(grp[0]["start"] - 5, h_start),
                "end": min(grp[-1]["end"] + 5, h_end),
                "score": score, "text": txt[:200], "duration": dur, "density": density
            })

        scenes.sort(key=lambda x: x["score"], reverse=True)
    except Exception as e:
        log_error(f"Scene extraction: {e}")
    return scenes[:max_clips]

def phase_clips(video, json_file, duration, selected, script_id_map=None):
    if not video or not os.path.exists(video):
        log_error("Phase 5 Failed: Video file not found")
        notify("Phase 5 Failed: Video file not found")
        set_status("Phase 5 FAILED")
        raise RuntimeError("Video file not found")

    if not json_file or not os.path.exists(json_file):
        log_error("Phase 5 Failed: Transcript file not found")
        notify("Phase 5 Failed: No transcript available")
        set_status("Phase 5 FAILED")
        raise RuntimeError("Transcript file not found")

    num_hours = len(selected)
    set_status("Phase 5: Generating clips...")
    log("Phase 5: Generating clips (scene-based)...")
    notify("Phase 5 Started: Generating clips...")
    vaapi = os.path.exists("/dev/dri/renderD128")
    log(f"   Encoding method: {'VAAPI' if vaapi else 'CPU (libx264)'}")

    v_w = v_h = 0
    try:
        r = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height", "-of", "csv=p=0", video], check=False)
        if r.returncode == 0 and r.stdout.strip():
            parts = r.stdout.strip().split(",")
            v_w, v_h = int(parts[0]), int(parts[1])
            log(f"   Video dimensions: {v_w}x{v_h}")
    except Exception:
        pass

    ffmpeg_check = run(["ffmpeg", "-version"], check=False)
    if ffmpeg_check.returncode != 0:
        log_error("Phase 5 Failed: ffmpeg not available")
        notify("Phase 5 Failed: ffmpeg not installed")
        set_status("Phase 5 FAILED")
        raise RuntimeError("ffmpeg not available")

    clips_generated = 0
    total_clips_estimate = 0
    for slot, interval in enumerate(selected, 1):
        h_start = interval['start']
        h_end = interval['end']
        padded  = f"{slot:03d}"

        scenes = _extract_scenes(json_file, h_start, h_end)
        total_clips_estimate += len(scenes)
    
    clip_counter = 0
    for slot, interval in enumerate(selected, 1):
        i = interval['index'] + 1
        h_start = interval['start']
        h_end = interval['end']
        padded  = f"{slot:03d}"
        video_basename = os.path.splitext(os.path.basename(video))[0]

        scenes = _extract_scenes(json_file, h_start, h_end)
        if not scenes:
            log(f"   Interval {i}: No scenes found")
            continue
        
        if AUDIO_ANALYSIS_AVAILABLE:
            try:
                scenes = enhance_scene_selection(scenes, video)
                log(f"   Audio analysis: enhanced {len(scenes)} scenes")
            except Exception as audio_err:
                log(f"   Audio analysis skipped: {audio_err}")
        
        scenes.sort(key=lambda x: x.get('audio_virality_score', x.get('score', 0)), reverse=True)
        
        for idx, sc in enumerate(scenes, 1):
            clip_counter += 1
            pct = int(((clip_counter - 1) / max(total_clips_estimate, 1)) * 100) if total_clips_estimate > 0 else 0
            set_progress(5, pct, f"Generating clips ({clip_counter}/{total_clips_estimate})")
            
            name = f"{video_basename}-Short{padded}_{idx}.mp4"
            out  = os.path.join(SHORTS_DIR, name)
            if os.path.exists(out) and os.path.getsize(out) > 0:
                log(f"   Skipping {name} (exists)")
                clips_generated += 1
                continue

            try:
                s, e = float(sc["start"]), float(sc["end"])
                dur  = e - s
                if dur <= 0:
                    log_error(f"   Skipping {name}: invalid duration ({dur}s)")
                    continue
                log(f"   Interval {i}, scene {idx}: {s:0.1f}s-{e:0.1f}s ({dur:0.1f}s)")

                portrait = env("PORTRAIT_CLIPS", "true").lower() == "true"
                vf_parts = []

                if portrait and v_w and v_h and v_w >= 1080 and v_h >= 1080:
                    vf_parts += ["crop=1080:1080:(iw-1080)/2:(ih-1080)/2", "scale=1080:1920"]
                elif portrait:
                    vf_parts += [
                        "scale=1080:1920:force_original_aspect_ratio=decrease",
                        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black",
                    ]

                if vaapi:
                    vf_parts = ["format=nv12"] + vf_parts + ["hwupload"]
                    cmd = ["ffmpeg", "-y",
                           "-vaapi_device", "/dev/dri/renderD128",
                           "-ss", f"{s:.3f}", "-i", video, "-t", f"{dur:.3f}",
                           "-vf", ",".join(vf_parts),
                           "-c:v", "h264_vaapi", "-rc_mode", "CQP", "-global_quality", "10",
                           "-compression_level", "1",
                           "-af", "loudnorm",
                           "-c:a", "aac", "-b:a", "192k",
                           out]
                    enc = "VAAPI"
                else:
                    cmd = ["ffmpeg", "-y", "-ss", f"{s:.3f}", "-i", video, "-t", f"{dur:.3f}"]
                    if vf_parts:
                        cmd += ["-vf", ",".join(vf_parts)]
                    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "18",
                            "-profile:v", "high", "-level", "4.2", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "192k", out]
                    enc = "CPU"

                r = run(cmd, check=False)
                if r.returncode != 0 or not os.path.exists(out) or os.path.getsize(out) == 0:
                    log(f"   {enc} failed for {name}, retrying with CPU slow seek...")
                    vf_cpu = []
                    if portrait and v_w and v_h and v_w >= 1080 and v_h >= 1080:
                        vf_cpu += ["crop=1080:1080:(iw-1080)/2:(ih-1080)/2", "scale=1080:1920"]
                    elif portrait:
                        vf_cpu += [
                            "scale=1080:1920:force_original_aspect_ratio=decrease",
                            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black",
                        ]
                    cmd = ["ffmpeg", "-y", "-i", video, "-ss", f"{s:.3f}", "-t", f"{dur:.3f}"]
                    if vf_cpu:
                        cmd += ["-vf", ",".join(vf_cpu)]
                    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "18",
                            "-profile:v", "high", "-level", "4.2", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "192k", out]
                    enc = "CPU (slow seek)"
                    r = run(cmd, check=False)
                if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 0:
                    log(f"   {name} created ({enc})")
                    clips_generated += 1
                    
                    # Store clip in performance database for learning
                    if PERFORMANCE_DB_AVAILABLE and LEARNING_ENGINE_AVAILABLE:
                        try:
                            # Use audio analysis features if available, fallback to text-based
                            clip_features = {
                                'duration': dur,
                                # Audio analysis features (from enhance_scene_selection)
                                'has_dialogue': sc.get('has_dialogue', False),
                                'has_excitement': sc.get('has_excitement', False),
                                'has_laughter': sc.get('has_laughter', False),
                                'volume_spike': sc.get('volume_spike', False),
                                'has_silence': sc.get('has_silence', False),
                                'audio_transitions': sc.get('audio_transitions', 0),
                                'volume_peak': sc.get('volume_peak', 0.0),
                                'volume_rms': sc.get('volume_rms', 0.0),
                                # Scene features
                                'density': sc.get('density', 0),
                                'scene_score': sc.get('score', 0),
                                'audio_virality_score': sc.get('audio_virality_score', 0),
                                # Text features (for context)
                                'text_preview': sc.get('text', '')[:100],
                                'has_question': '?' in sc.get('text', ''),
                                'has_exclamation': '!' in sc.get('text', ''),
                            }
                            virality = calculate_virality_score(clip_features, learned_params=_LEARNING_OPTIMIZED_PARAMS)
                            if script_id_map:
                                linked_script_id = script_id_map.get(slot)
                            else:
                                linked_script_id = None

                            clip_id = store_clip(
                                script_id=linked_script_id,
                                source_file=video_basename,
                                start_time=s,
                                end_time=e,
                                duration=dur,
                                features=clip_features,
                                virality_score=virality
                            )
                            log(f"Performance: Clip stored (score: {virality:.1f})")
                        except Exception as perf_err:
                            log(f"Performance DB: Failed to store clip - {perf_err}")
                else:
                    err_msg = r.stderr[-200:] if r.stderr else "Unknown error"
                    log_error(f"   Failed {name}: {err_msg}")
            except Exception as e:
                log_error(f"   Error creating {name}: {e}")
                continue

    if clips_generated == 0:
        log_error("Phase 5 Failed: No clips were generated")
        notify("Phase 5 Failed: No clips generated")
        set_status("Phase 5 FAILED")
        raise RuntimeError("No clips generated")

    set_status("Phase 5 Complete")
    notify(f"Phase 5 Complete: {clips_generated} clips generated")

# (Phase 6 moved to workflows/pipeline/phase_tts.py — multi-provider, see _get_cogitator() import)

# ─── Find latest video ────────────────────────────────────────────────────────
def find_video():
    for ext in ("*.webm", "*.mp4", "*.mkv"):
        files = sorted(glob.glob(os.path.join(MEDIA_DIR, ext)),
                       key=os.path.getmtime, reverse=True)
        if files:
            return files[0]
    return None

def video_info(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path])
    return int(float(r.stdout.strip()))

# ─── Local Recording Processing ──────────────────────────────────────────────
def run_local_recordings(recording_path):
    """Process local recordings from a directory."""
    global PIPELINE_STOP_REQUESTED, PIPELINE_RUNNING
    set_pipeline_stop_requested(False)
    set_pipeline_running(True)

    def check_stop():
        if get_pipeline_stop_requested():
            log("Pipeline stopped by user")
            set_status("Pipeline Stopped")
            notify("Pipeline stopped by user.")
            return True
        return False

    for d in (MEDIA_DIR, TRANSCRIPTS_DIR, SCRIPTS_DIR, TTS_DIR, SHORTS_DIR, OUTPUT_DIR):
        os.makedirs(d, exist_ok=True)

    _refresh_learning_state()

    if not os.path.exists(recording_path):
        log_error(f"Recording path not found: {recording_path}")
        notify(f"Error: Recording path not found: {recording_path}")
        return

    video_extensions = (".mp4", ".mkv", ".webm", ".avi", ".mov")
    video_files = []
    for f in os.listdir(recording_path):
        if f.lower().endswith(video_extensions):
            video_files.append(os.path.join(recording_path, f))

    if not video_files:
        log_error(f"No video files found in {recording_path}")
        notify(f"No video files found in {recording_path}")
        return

    video_files.sort(key=os.path.getmtime)

    log(f"Found {len(video_files)} local recording(s)")
    notify(f"Processing {len(video_files)} local recording(s)...")

    for i, video_file in enumerate(video_files, 1):
        if check_stop():
            return

        video_name = os.path.basename(video_file)
        log(f"Processing video {i}/{len(video_files)}: {video_name}")

        try:
            duration = video_info(video_file)
            if duration <= 0:
                log_error(f"Invalid video: {video_name}")
                continue

            num_hours = max(1, duration // 3600 + (1 if duration % 3600 > 1800 else 0))
            log(f"Video: {duration}s = {num_hours} hour(s)")

            json_file = phase_transcribe(video_file)
            if check_stop(): return

            phase_context()
            if check_stop(): return

            video_base = os.path.splitext(os.path.basename(video_file))[0]
            json_file = os.path.join(TRANSCRIPTS_DIR, f"{video_base}.json")
            if not os.path.exists(json_file):
                json_file = None

            if json_file:
                interval = 1800
                num_shorts = int(env("NUM_SHORTS", "0"))
                max_shorts = max(1, duration // interval + (1 if duration % interval > interval // 2 else 0))
                if num_shorts <= 0:
                    num_shorts = max_shorts
                num_shorts = min(num_shorts, max_shorts)

                selected = _select_best_intervals(json_file, duration, num_shorts)
                log(f"Selected {len(selected)} intervals from {max_shorts} possible")
                for s in selected:
                    log(f"  Interval {s['index']+1}: {s['start']//60}-{s['end']//60}min (score: {s['score']:.1f})")

                phase_scripts(json_file, duration, selected, video=video_file)
                if check_stop(): return

                phase_clips(video_file, json_file, duration, selected, script_id_map=get_script_id_map())
                if check_stop(): return

                from workflows.pipeline.phase_tts import phase_tts
                phase_tts(duration, len(selected), video=video_file)
                if check_stop(): return

                from workflows.pipeline.phase_assemble import phase_assemble
                phase_assemble(duration, len(selected), video=video_file)
                if check_stop(): return

            log(f"Video {i}/{len(video_files)} complete!")

            # Garbage collect between videos to prevent memory accumulation
            gc.collect()

            if i < len(video_files):
                log("Waiting 300 seconds before next video...")
                time.sleep(300)

        except Exception as e:
            log_error(f"Error processing {video_name}: {e}")
            continue

    log("All local recordings processed!")
    set_status("Pipeline Complete")
    notify(f"Local recording pipeline complete! Processed {len(video_files)} video(s).")

# ─── Pipeline orchestrator ────────────────────────────────────────────────────
def run_pipeline(skip=None):
    """Delegate to the canonical orchestrator (checkpoints + YouTube sync)."""
    from workflows.pipeline.pipeline_runner import run_pipeline as _run
    return _run(skip=skip)


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
        default_voice = existing.get("TTS_VOICE", "Vindemiatrix")
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

        _tts_style_input = ask("TTS_STYLE", "TTS Style prefix (enter '.' to clear)", optional=True)
        config["TTS_STYLE"] = "" if _tts_style_input == "." else _tts_style_input

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
        except Exception as e:
            print(f"  {warn()} Keychain not available: {e}")
            print(f"    Keys saved to files only")

    # Reload env
    global ENV, ENV_FILE, WORKSPACE, WORKFLOW_DIR
    ENV_FILE = env_file
    WORKSPACE = workspace
    WORKFLOW_DIR = wf_dir
    ENV = load_env()

    # Verify
    print(f"\n{B}Verifying connections...{X}")
    all_ok = True

    # Gemini
    sys.stdout.write("  Gemini API ... "); sys.stdout.flush()
    try:
        body = json.dumps({"contents":[{"parts":[{"text":"hi"}]}],
                           "generationConfig":{"maxOutputTokens":5}}).encode()
        req = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent",
            data=body, headers={"Content-Type":"application/json", "X-Goog-Api-Key": env('GEMINI_API_KEY')})
        r = urllib.request.urlopen(req, timeout=15)
        json.loads(r.read())
        print(f"{ok()} OK")
    except Exception:
        print(f"{fail()} Failed")
        all_ok = False

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
        else:
            print(f"  {B}Ready!{X}")
            print(f"    python3 {dst} run")
            print(f"    python3 {dst} run -phase 2,3\n")

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

# ─── CLI ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(prog="COGITATOR", description="Cogitator — YouTube Shorts Pipeline")
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="Run the pipeline")
    p_run.add_argument("-phase", type=str, help="Run only phases (e.g. 2,3)")
    p_run.add_argument("-index", type=int, help="Playlist index to download (default: 1)")
    p_run.add_argument("-skip-phase-1", action="store_true")
    p_run.add_argument("-skip-phase-2", action="store_true")
    p_run.add_argument("-skip-phase-3", action="store_true")
    p_run.add_argument("-skip-phase-4", action="store_true")
    p_run.add_argument("-skip-phase-5", action="store_true")
    p_run.add_argument("-skip-phase-6", action="store_true")
    p_run.add_argument("-skip-phase-7", action="store_true")
    p_run.add_argument("-skip-all", action="store_true")

    p_local = sub.add_parser("run_local", help="Run pipeline on local recordings")
    p_local.add_argument("path", type=str, nargs="?", help="Path to local recordings directory (default: media)")
    
    p_download = sub.add_parser("download", help="Download video from URL")
    p_download.add_argument("-url", type=str, required=True, help="URL to download (video or playlist)")
    
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
            skip = {1, 2, 3, 4, 5, 6, 7}
        else:
            if getattr(args, "skip_phase_1", False): skip.add(1)
            if getattr(args, "skip_phase_2", False): skip.add(2)
            if getattr(args, "skip_phase_3", False): skip.add(3)
            if getattr(args, "skip_phase_4", False): skip.add(4)
            if getattr(args, "skip_phase_5", False): skip.add(5)
            if getattr(args, "skip_phase_6", False): skip.add(6)
            if getattr(args, "skip_phase_7", False): skip.add(7)

        # -phase N,M runs ONLY those phases (skip everything else)
        if getattr(args, "phase", None):
            wanted = {int(p) for p in str(args.phase).split(",") if p.strip().isdigit()}
            wanted = {p for p in wanted if 1 <= p <= 7}
            if wanted:
                skip = set(range(1, 8)) - wanted

        if args.index:
            update_env_var("PLAYLIST_INDEX", str(args.index))

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
