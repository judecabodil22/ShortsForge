#!/usr/bin/env python3
"""
ShortsForge Context Manager Module

Handles verified context storage, comparison, and learning.

Key features:
- Two-tier context: extracted (AI) vs verified (user-approved)
- "Latest wins" logic for discrepancies between transcripts
- Context correction tracking for learning
- Significance detection for confirmation triggers
"""

import os
import json
import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any


# Paths
def _get_workspace():
    """Get workspace path."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WORKSPACE = _get_workspace()
CONTEXT_DIR = os.path.join(WORKSPACE, "Context")

VERIFIED_CONTEXT_FILE = os.path.join(CONTEXT_DIR, "verified_context.json")
CONTEXT_CORRECTIONS_FILE = os.path.join(CONTEXT_DIR, "context_corrections.jsonl")
CONTEXT_HISTORY_DIR = os.path.join(CONTEXT_DIR, "history")


# ── Verified Context Storage ─────────────────────────────────────────────────

def load_verified_context(game_title: str) -> Dict[str, Any]:
    """Load verified context for a game."""
    if not os.path.exists(VERIFIED_CONTEXT_FILE):
        return {}
    
    try:
        with open(VERIFIED_CONTEXT_FILE, "r") as f:
            all_context = json.load(f)
        game_key = game_title.lower().strip()
        return all_context.get(game_key, {})
    except Exception:
        return {}


def save_verified_context(game_title: str, context: Dict[str, Any]):
    """Save verified context for a game."""
    all_context = {}
    
    if os.path.exists(VERIFIED_CONTEXT_FILE):
        try:
            with open(VERIFIED_CONTEXT_FILE, "r") as f:
                all_context = json.load(f)
        except Exception:
            pass
    
    game_key = game_title.lower().strip()
    all_context[game_key] = {
        "context": context,
        "verified_at": datetime.now().isoformat(),
        "source": "user_approved"
    }
    
    try:
        with open(VERIFIED_CONTEXT_FILE, "w") as f:
            json.dump(all_context, f, indent=2)
    except Exception:
        pass


def is_first_run(game_title: str) -> bool:
    """Check if this is first run for a game (no verified context)."""
    return load_verified_context(game_title) == {}


def clear_verified_context(game_title: str):
    """Clear verified context for a game (reset)."""
    if not os.path.exists(VERIFIED_CONTEXT_FILE):
        return
    
    try:
        with open(VERIFIED_CONTEXT_FILE, "r") as f:
            all_context = json.load(f)
        game_key = game_title.lower().strip()
        all_context.pop(game_key, None)
        with open(VERIFIED_CONTEXT_FILE, "w") as f:
            json.dump(all_context, f, indent=2)
    except Exception:
        pass


# ── Context Comparison with "Latest Wins" Logic ─────────────────────────────

def compare_context_with_history(
    extracted: Dict[str, Any],
    verified: Dict[str, Any],
    transcript_order: List[str] = None
) -> Dict[str, Any]:
    """
    Compare extracted context with verified context, using "latest wins" logic.
    
    If verified has conflicting info from earlier transcripts, and extracted
    has clarified/updated info from later transcripts, the latest info wins.
    
    Args:
        extracted: Newly extracted context from current transcript
        verified: Previously verified context
        transcript_order: List of transcript filenames in chronological order
    
    Returns:
        Dict with:
        - has_significant_change: bool
        - changes: dict of what changed
        - discrepancies: list of conflicts found and resolved
        - resolved_context: context with "latest wins" applied
    """
    if not verified:
        return {
            "has_significant_change": True,
            "reason": "first_run",
            "changes": {},
            "discrepancies": [],
            "resolved_context": extracted,
            "needs_confirmation": True
        }
    
    changes = {
        "characters_added": [],
        "characters_removed": [],
        "locations_added": [],
        "locations_removed": [],
        "relationships_changed": [],
        "relationships_added": [],
    }
    
    discrepancies = []
    resolved = verified.get("context", {}).copy()
    
    verified_ctx = verified.get("context", {})
    extracted_chars = set(extracted.get("characters", []))
    verified_chars = set(verified_ctx.get("characters", []))
    
    new_chars = extracted_chars - verified_chars
    removed_chars = verified_chars - extracted_chars
    
    if new_chars:
        changes["characters_added"] = list(new_chars)
    if removed_chars:
        changes["characters_removed"] = list(removed_chars)
    
    extracted_locs = set(extracted.get("locations", []))
    verified_locs = set(verified_ctx.get("locations", []))
    
    new_locs = extracted_locs - verified_locs
    removed_locs = verified_locs - extracted_locs
    
    if new_locs:
        changes["locations_added"] = list(new_locs)
    if removed_locs:
        changes["locations_removed"] = list(removed_locs)
    
    extracted_rels = extracted.get("relationships", [])
    verified_rels = verified_ctx.get("relationships", [])
    
    verified_rels_dict = {}
    for rel in verified_rels:
        if isinstance(rel, dict):
            key = (rel.get("from", ""), rel.get("to", ""))
            verified_rels_dict[key] = rel.get("relationship", "")
        elif isinstance(rel, str):
            parts = rel.split(" are ")
            if len(parts) == 2:
                key = (parts[0].strip(), parts[1].strip().split(" and ")[0].strip())
                verified_rels_dict[key] = parts[1].strip()
    
    resolved_rels = []
    for rel in extracted_rels:
        if isinstance(rel, dict):
            key = (rel.get("from", ""), rel.get("to", ""))
            new_rel = rel.get("relationship", "")
        elif isinstance(rel, str):
            parts = rel.split(" are ")
            if len(parts) == 2:
                key = (parts[0].strip(), parts[1].strip().split(" and ")[0].strip())
                new_rel = parts[1].strip()
            else:
                continue
        else:
            continue
        
        old_rel = verified_rels_dict.get(key, "")
        
        if old_rel and old_rel != new_rel:
            discrepancies.append({
                "characters": list(key),
                "old_relationship": old_rel,
                "new_relationship": new_rel,
                "resolution": "newer_wins"
            })
            changes["relationships_changed"].append({
                "from": key[0],
                "to": key[1],
                "was": old_rel,
                "now": new_rel
            })
        
        if isinstance(rel, dict):
            resolved_rels.append(rel)
        else:
            resolved_rels.append(rel)
    
    for rel in verified_rels:
        if isinstance(rel, dict):
            key = (rel.get("from", ""), rel.get("to", ""))
            if key not in [(r.get("from", ""), r.get("to", "")) for r in extracted_rels]:
                if isinstance(rel, dict):
                    pass
        elif isinstance(rel, str):
            parts = rel.split(" are ")
            if len(parts) == 2:
                key = (parts[0].strip(), parts[1].strip().split(" and ")[0].strip())
                if key not in [(p.split(" are ")[0].strip(), p.split(" are ")[1].strip().split(" and ")[0].strip()) for p in extracted_rels if " are " in p]:
                    changes["relationships_removed"] = changes.get("relationships_removed", [])
    
    resolved["relationships"] = resolved_rels
    
    total_changes = (
        len(changes["characters_added"]) +
        len(changes["characters_removed"]) +
        len(changes["locations_added"]) +
        len(changes["locations_removed"]) +
        len(changes["relationships_changed"]) +
        len(changes["relationships_added"])
    )
    
    has_significant = total_changes >= 2 or len(discrepancies) > 0
    
    return {
        "has_significant_change": has_significant,
        "changes": changes,
        "discrepancies": discrepancies,
        "resolved_context": resolved,
        "needs_confirmation": has_significant,
        "reason": "discrepancy_found" if discrepancies else "multiple_changes"
    }


def calculate_significance(changes: Dict[str, Any]) -> float:
    """Calculate significance score from changes."""
    score = 0.0
    
    score += len(changes.get("characters_added", [])) * 0.15
    score += len(changes.get("characters_removed", [])) * 0.10
    score += len(changes.get("locations_added", [])) * 0.10
    score += len(changes.get("locations_removed", [])) * 0.08
    score += len(changes.get("relationships_changed", [])) * 0.25
    score += len(changes.get("relationships_added", [])) * 0.15
    
    return score


# ── Context Corrections Tracking ────────────────────────────────────────────

def log_context_correction(
    game_title: str,
    field: str,
    old_value: str,
    new_value: str,
    source: str = "obsidian"
):
    """Log a context correction for learning."""
    record = {
        "timestamp": datetime.now().isoformat(),
        "game_title": game_title,
        "field": field,
        "old_value": old_value,
        "new_value": new_value,
        "source": source
    }
    
    try:
        with open(CONTEXT_CORRECTIONS_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


def get_learned_corrections(game_title: str) -> Dict[str, List[Dict]]:
    """Get learned corrections for a game."""
    corrections = {
        "characters": [],
        "relationships": [],
        "locations": []
    }
    
    if not os.path.exists(CONTEXT_CORRECTIONS_FILE):
        return corrections
    
    try:
        with open(CONTEXT_CORRECTIONS_FILE, "r") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    if record.get("game_title", "").lower() == game_title.lower():
                        field = record.get("field", "")
                        if field in corrections:
                            corrections[field].append({
                                "old": record.get("old_value", ""),
                                "new": record.get("new_value", ""),
                                "count": corrections[field].count({"old": record.get("old_value", ""), "new": record.get("new_value", "")}) + 1
                            })
                except:
                    continue
    except Exception:
        pass
    
    return corrections


# ── Context History (Per Transcript) ─────────────────────────────────────────

def save_context_snapshot(game_title: str, transcript_name: str, context: Dict[str, Any]):
    """Save context snapshot for a specific transcript."""
    history_dir = os.path.join(CONTEXT_HISTORY_DIR, game_title.lower().replace(" ", "_"))
    os.makedirs(history_dir, exist_ok=True)
    
    snapshot_file = os.path.join(history_dir, f"{transcript_name}.json")
    
    try:
        with open(snapshot_file, "w") as f:
            json.dump({
                "context": context,
                "timestamp": datetime.now().isoformat(),
                "transcript": transcript_name
            }, f, indent=2)
    except Exception:
        pass


def load_context_history(game_title: str) -> List[Dict[str, Any]]:
    """Load all context snapshots for a game in chronological order."""
    history_dir = os.path.join(CONTEXT_HISTORY_DIR, game_title.lower().replace(" ", "_"))
    
    if not os.path.exists(history_dir):
        return []
    
    snapshots = []
    for filename in os.listdir(history_dir):
        if filename.endswith(".json"):
            try:
                with open(os.path.join(history_dir, filename), "r") as f:
                    data = json.load(f)
                    data["filename"] = filename
                    snapshots.append(data)
            except:
                continue
    
    snapshots.sort(key=lambda x: x.get("timestamp", ""))
    return snapshots


# ── Helper Functions ────────────────────────────────────────────────────────

def format_context_for_confirmation(
    extracted: Dict[str, Any],
    verified: Dict[str, Any],
    comparison: Dict[str, Any]
) -> str:
    """Format context for Telegram/CLI confirmation message."""
    lines = []
    
    chars = extracted.get("characters", [])
    lines.append(f"📝 Characters ({len(chars)}): {', '.join(chars[:8])}" + ("..." if len(chars) > 8 else ""))
    
    locs = extracted.get("locations", [])
    lines.append(f"📍 Locations ({len(locs)}): {', '.join(locs[:5])}" + ("..." if len(locs) > 5 else ""))
    
    rels = extracted.get("relationships", [])
    lines.append(f"👥 Relationships ({len(rels)}):")
    for rel in rels[:5]:
        if isinstance(rel, dict):
            lines.append(f"  - {rel.get('from', '')} ↔ {rel.get('to', '')}: {rel.get('relationship', '')}")
        elif isinstance(rel, str):
            lines.append(f"  - {rel}")
    if len(rels) > 5:
        lines.append(f"  ... and {len(rels) - 5} more")
    
    changes = comparison.get("changes", {})
    discrepancies = comparison.get("discrepancies", [])
    
    if discrepancies:
        lines.append("\n⚠️ Discrepancies resolved (latest wins):")
        for d in discrepancies[:3]:
            lines.append(f"  - {d['characters'][0]} ↔ {d['characters'][1]}: {d['old_relationship']} → {d['new_relationship']}")
    
    if changes.get("characters_added"):
        lines.append(f"\n➕ New characters: {', '.join(changes['characters_added'][:3])}")
    if changes.get("relationships_changed"):
        lines.append(f"🔄 Modified relationships: {len(changes['relationships_changed'])}")
    
    return "\n".join(lines)


def get_verified_context_for_validation(game_title: str) -> Dict[str, Any]:
    """Get context for validation - prefers verified, falls back to extracted."""
    verified = load_verified_context(game_title)
    if verified:
        return verified.get("context", {})
    
    return {}


# ── Clear All ────────────────────────────────────────────────────────────────

def clear_all_verified_context():
    """Clear all verified context (for testing)."""
    if os.path.exists(VERIFIED_CONTEXT_FILE):
        os.remove(VERIFIED_CONTEXT_FILE)
    
    if os.path.exists(CONTEXT_CORRECTIONS_FILE):
        os.remove(CONTEXT_CORRECTIONS_FILE)
    
    if os.path.exists(CONTEXT_HISTORY_DIR):
        import shutil
        shutil.rmtree(CONTEXT_HISTORY_DIR)


# Module test
if __name__ == "__main__":
    print("ShortsForge Context Manager")
    print(f"Workspace: {WORKSPACE}")
    print(f"Verified context file: {VERIFIED_CONTEXT_FILE}")
    print(f"Corrections file: {CONTEXT_CORRECTIONS_FILE}")