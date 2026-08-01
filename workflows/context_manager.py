#!/usr/bin/env python3
"""
Cogitator Context Manager Module

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
import copy
import threading
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

try:
    from rapidfuzz import fuzz as _fuzz
except ImportError:
    _fuzz = None


# Paths
def _get_workspace():
    """Get workspace path."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WORKSPACE = _get_workspace()

# Child game key (normalized) -> franchise context key
SERIES_MAPPING = {
    "the_shadow_of_the_tomb_raider": "tomb_raider_series",
    "shadow_of_the_tomb_raider": "tomb_raider_series",
    "rise_of_the_tomb_raider": "tomb_raider_series",
    "tomb_raider": "tomb_raider_series",
    "tomb_raider_(2013)": "tomb_raider_series",
    "tomb_raider_definitive_edition": "tomb_raider_series",
}

# Keywords to match MemPalace transcript chunks to a franchise graph key
MEMPALACE_GAME_KEYWORDS = {
    "tomb_raider_series": [
        "tomb raider", "lara croft", "trinity", "shadow of the tomb", "rise of the tomb",
        "peruvian jungle", "cozumel", "jonah",
    ],
    "cyberpunk_2077": ["cyberpunk", "night city", "johnny silverhand", "arasaka"],
    "tell_me_why": ["tell me why", "goblin", "allison", "tyler"],
}

MEMPALACE_CHROMA_DB = os.path.expanduser("~/.mempalace/palace/chroma.sqlite3")


# MemPalace integration
def _get_mempalace_manager():
    """Get MemPalace manager if available."""
    try:
        from game_data.mempalace import get_mempalace_manager as get_manager
        return get_manager()
    except ImportError:
        return None


# ── Context → MemPalace Sync ─────────────────────────────────────────────────

def sync_context_to_mempalace(game_title: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sync verified context to MemPalace for learning.
    This ensures MemPalace learns from user corrections.
    
    Uses file-based mining: creates temp file with context, mines it into MemPalace.
    """
    if not game_title or not context:
        return {"error": "Missing game_title or context"}
    
    result = {"synced": 0, "errors": [], "details": {}}
    
    temp_dir = os.path.join(CONTEXT_DIR, ".sync_temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    game_sanitized = game_title.lower().strip().replace(" ", "_")
    temp_file = os.path.join(temp_dir, f"{game_sanitized}_context.md")
    
    try:
        # Format context as markdown
        lines = [f"# {game_title} Context\n"]
        
        # Characters
        chars = context.get("characters", [])
        if chars:
            lines.append("## Characters\n")
            for c in chars:
                name = c.get("name", "") if isinstance(c, dict) else str(c)
                if name:
                    lines.append(f"- **{name}** is a verified character in {game_title}")
            lines.append("")
        
        # Locations
        locs = context.get("locations", [])
        if locs:
            lines.append("## Locations\n")
            for l in locs:
                name = l.get("name", "") if isinstance(l, dict) else str(l)
                if name:
                    lines.append(f"- **{name}** is a verified location in {game_title}")
            lines.append("")
        
        # Key Terms
        terms = context.get("key_terms", [])
        if terms:
            lines.append("## Key Terms\n")
            for t in terms:
                term = t.get("term", "") if isinstance(t, dict) else str(t)
                if term:
                    lines.append(f"- **{term}** is a verified key term in {game_title}")
            lines.append("")
        
        # Relationships
        rels = context.get("relationships", [])
        if rels:
            lines.append("## Relationships\n")
            for r in rels:
                rel = r.get("from", "") if isinstance(r, dict) else str(r)
                if rel:
                    lines.append(f"- **{rel}** is a verified relationship in {game_title}")
            lines.append("")
        
        # Write temp file
        content = "\n".join(lines)
        with open(temp_file, "w") as f:
            f.write(content)
        
        # Mine the file into MemPalace
        mp_manager = _get_mempalace_manager()
        if mp_manager:
            mp_result = mp_manager.mine_transcript(temp_file, game_title)
            result["mempalace_output"] = json.dumps(mp_result)
            result["synced"] = len(chars) + len(locs) + len(terms) + len(rels)
        else:
            result["errors"].append("MemPalace not available")
        
        # Clean up temp file
        try:
            os.remove(temp_file)
        except:
            pass
    
    except Exception as e:
        result["errors"].append(str(e))
    
    return result

CONTEXT_DIR = os.path.join(WORKSPACE, "Context")

VERIFIED_CONTEXT_FILE = os.path.join(CONTEXT_DIR, "verified_context.json")
CONTEXT_CORRECTIONS_FILE = os.path.join(CONTEXT_DIR, "context_corrections.jsonl")
CONTEXT_HISTORY_DIR = os.path.join(CONTEXT_DIR, "history")

_context_file_lock = threading.Lock()


# ── Markdown + MemPalace loaders (used by graph / context manager v2) ────────

def _wiki_name(cell: str) -> str:
    cell = (cell or "").strip()
    if cell.startswith("[[") and cell.endswith("]]"):
        return cell[2:-2]
    return cell


def load_markdown_context(game_key: str) -> Dict[str, Any]:
    """Load characters, locations, terms, relationships from Obsidian markdown tables."""
    ctx_dir = os.path.join(CONTEXT_DIR, game_key)
    if not os.path.isdir(ctx_dir):
        return {"characters": [], "locations": [], "key_terms": [], "relationships": []}

    result = {"characters": [], "locations": [], "key_terms": [], "relationships": []}
    file_map = {
        "characters": "characters.md",
        "locations": "locations.md",
        "key_terms": "key_terms.md",
    }

    for field, fname in file_map.items():
        path = os.path.join(ctx_dir, fname)
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        for line in content.split("\n"):
            line = line.strip()
            if not line.startswith("|") or "---" in line:
                continue
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if not parts or parts[0].lower() in ("name", "character", "location", "term"):
                continue
            name = _wiki_name(parts[0])
            if name and name not in result[field]:
                result[field].append(name)

    rel_path = os.path.join(ctx_dir, "relationships.md")
    if os.path.exists(rel_path):
        with open(rel_path, "r", encoding="utf-8") as f:
            rel_content = f.read()
        if "|" in rel_content and "---" in rel_content:
            for line in rel_content.split("\n"):
                line = line.strip()
                if not line.startswith("|") or "---" in line or "Character A" in line:
                    continue
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) < 3:
                    continue
                char_a = _wiki_name(parts[0])
                connection = parts[1]
                char_b = _wiki_name(parts[2])
                if not char_a or char_a == "-":
                    continue
                if char_b and char_b != "-":
                    rel = {"from": char_a, "to": char_b, "relationship": connection}
                else:
                    rel = {"from": char_a, "to": char_a, "relationship": connection}
                if rel not in result["relationships"]:
                    result["relationships"].append(rel)
    return result


def get_mempalace_text_chunks(game_key: str) -> List[str]:
    """Return MemPalace narrative chunks relevant to a franchise (from ChromaDB)."""
    keywords = MEMPALACE_GAME_KEYWORDS.get(game_key, [])
    if not keywords or not os.path.exists(MEMPALACE_CHROMA_DB):
        return []

    chunks: List[str] = []
    try:
        import sqlite3
        conn = sqlite3.connect(MEMPALACE_CHROMA_DB)
        try:
            cur = conn.cursor()
            cur.execute("SELECT c0 FROM embedding_fulltext_search_content WHERE c0 IS NOT NULL")
            for (text,) in cur.fetchall():
                if not text or len(text.strip()) < 40:
                    continue
                lower = text.lower()
                if any(kw in lower for kw in keywords):
                    chunks.append(text)
        finally:
            conn.close()
    except Exception:
        pass
    return chunks


def get_context_sources_summary(game_key: str) -> Dict[str, Any]:
    """Inventory counts across verified JSON, markdown, MemPalace, and transcripts."""
    md = load_markdown_context(game_key)
    verified = load_verified_context(game_key)
    if not verified:
        verified = {}
    vctx = verified.get("context", {}) if isinstance(verified, dict) else {}
    mp_chunks = get_mempalace_text_chunks(game_key)
    transcripts_dir = os.path.join(WORKSPACE, "transcripts")
    transcript_files = []
    if os.path.isdir(transcripts_dir):
        transcript_files = [f for f in os.listdir(transcripts_dir) if f.endswith(".json")]
    return {
        "game_key": game_key,
        "verified": {
            "characters": len(vctx.get("characters", [])),
            "locations": len(vctx.get("locations", [])),
            "key_terms": len(vctx.get("key_terms", [])),
            "relationships": len(vctx.get("relationships", [])),
        },
        "markdown": {
            "characters": len(md.get("characters", [])),
            "locations": len(md.get("locations", [])),
            "key_terms": len(md.get("key_terms", [])),
            "relationships": len(md.get("relationships", [])),
        },
        "mempalace_chunks": len(mp_chunks),
        "transcript_files": transcript_files,
    }


# ── Verified Context Storage ─────────────────────────────────────────────────

def load_verified_context(game_title: str) -> Dict[str, Any]:
    """Load verified context for a game, with auto-recovery from snapshots on corruption."""
    game_key = game_title.lower().replace(" ", "_").strip()
    
    # Step 1: Try loading from the verified context file
    context_data = {}
    corrupted = False
    with _context_file_lock:
        if os.path.exists(VERIFIED_CONTEXT_FILE):
            try:
                with open(VERIFIED_CONTEXT_FILE, "r") as f:
                    all_context = json.load(f)
                context_data = all_context.get(game_key, {})
                # Validate the context has expected structure
                ctx = context_data.get("context", {})
                if not isinstance(ctx, dict):
                    corrupted = True
            except (json.JSONDecodeError, ValueError, TypeError):
                corrupted = True
    
    if corrupted:
        # Step 2: Attempt recovery from the most recent snapshot
        snapshots = load_context_history(game_title)
        if snapshots:
            latest = snapshots[-1]  # Chronologically sorted
            recovered = latest.get("context", {})
            context_data = {"context": recovered, "verified_at": latest.get("timestamp", ""), "source": "recovered_snapshot"}
            print(f"[CONTEXT] Recovered context for {game_key} from snapshot ({len(snapshots)} available)")
            # Attempt to write recovered context back (with lock)
            with _context_file_lock:
                try:
                    all_context = {}
                    if os.path.exists(VERIFIED_CONTEXT_FILE):
                        try:
                            with open(VERIFIED_CONTEXT_FILE) as f:
                                all_context = json.load(f)
                        except Exception:
                            all_context = {}
                    all_context[game_key] = context_data
                    with open(VERIFIED_CONTEXT_FILE, "w") as f:
                        json.dump(all_context, f, indent=2)
                except Exception:
                    pass
        else:
            print(f"[CONTEXT] Verified context corrupted for {game_key} and no snapshots to recover from")
    
    return context_data


def _relationship_key(rel: Any) -> tuple:
    if isinstance(rel, dict):
        return (rel.get("from", "").strip().lower(), rel.get("to", "").strip().lower())
    if isinstance(rel, str) and " are " in rel:
        parts = rel.split(" are ", 1)
        return (parts[0].strip().lower(), parts[1].strip().lower())
    return ("", "")


def _fuzzy_in(item: str, existing: list[str], threshold: int = 80) -> tuple[bool, str | None]:
    """Check if item fuzzy-matches any entry in existing list."""
    if not existing or not _fuzz:
        return False, None
    item_lower = item.lower().strip()
    for entry in existing:
        entry_lower = entry.lower()
        if item_lower == entry_lower:
            return True, entry
        ratio = _fuzz.token_sort_ratio(item_lower, entry_lower)
        if ratio >= threshold:
            canonical = entry if len(entry) >= len(item) else item
            return True, canonical
    return False, None


def merge_context_dicts(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """Union list fields and relationships; overlay wins on relationship conflicts."""
    out = dict(base or {})
    for key in ("characters", "locations", "key_terms", "processed_transcripts", "previous_scripts"):
        merged = []
        for item in list(base.get(key, []) or []) + list(overlay.get(key, []) or []):
            if not item:
                continue
            is_dup, _ = _fuzzy_in(str(item), merged)
            if not is_dup:
                merged.append(item)
        out[key] = merged

    rel_map: Dict[tuple, Any] = {}
    for rel in list(base.get("relationships", []) or []):
        key = _relationship_key(rel)
        if key[0] and key[1]:
            rel_map[key] = rel
    for rel in list(overlay.get("relationships", []) or []):
        key = _relationship_key(rel)
        if key[0] and key[1]:
            rel_map[key] = rel
    out["relationships"] = list(rel_map.values())

    overlay_title = (overlay.get("title") or "").strip()
    if overlay_title:
        out["title"] = overlay_title
    elif base.get("title"):
        out["title"] = base.get("title")
    return out


def save_verified_context(game_title: str, context: Dict[str, Any], merge: bool = False):
    """Save verified context for a game and sync to MemPalace."""
    game_key = game_title.lower().replace(" ", "_").strip()
    with _context_file_lock:
        all_context = {}
        
        if os.path.exists(VERIFIED_CONTEXT_FILE):
            try:
                with open(VERIFIED_CONTEXT_FILE, "r") as f:
                    all_context = json.load(f)
            except Exception:
                pass
        
        if merge:
            existing = all_context.get(game_key, {}).get("context", {})
            context = merge_context_dicts(existing, context)
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
    
    # Sync to MemPalace for learning (uses existing context param, no re-read needed)
    try:
        sync_result = sync_context_to_mempalace(game_title, context)
        if sync_result.get("synced", 0) > 0:
            pass
    except Exception:
        pass


def save_implicit_relationships(game_title: str, implicit_edges: List[Dict[str, Any]]):
    """Save implicit co-occurrence relationships to verified_context.json."""
    game_key = game_title.lower().replace(" ", "_").strip()
    with _context_file_lock:
        all_context = {}
        
        if os.path.exists(VERIFIED_CONTEXT_FILE):
            try:
                with open(VERIFIED_CONTEXT_FILE, "r") as f:
                    all_context = json.load(f)
            except Exception:
                pass
        
        if game_key not in all_context:
            all_context[game_key] = {"context": {}, "verified_at": datetime.now().isoformat()}
        
        all_context[game_key]["implicit_relationships"] = implicit_edges
        
        try:
            with open(VERIFIED_CONTEXT_FILE, "w") as f:
                json.dump(all_context, f, indent=2)
        except Exception as e:
            print(f"Failed to save implicit relationships: {e}")


def load_implicit_relationships(game_title: str) -> List[Dict[str, Any]]:
    """Load stored implicit co-occurrence relationships."""
    game_key = game_title.lower().replace(" ", "_").strip()
    
    with _context_file_lock:
        if not os.path.exists(VERIFIED_CONTEXT_FILE):
            return []
        
        try:
            with open(VERIFIED_CONTEXT_FILE, "r") as f:
                all_context = json.load(f)
            return all_context.get(game_key, {}).get("implicit_relationships", [])
        except Exception:
            return []


def compute_and_save_implicit_relationships(game_title: str, transcript_text: str):
    """Compute co-occurrence from transcript text and merge with existing stored data."""
    from collections import defaultdict
    
    game_key = game_title.lower().replace(" ", "_").strip()
    
    # Load current context to get entity names
    verified = load_verified_context(game_title)
    context = verified.get("context", {}) if verified else {}
    
    # Build entity list from context
    entities = {}
    for etype in ['characters', 'locations', 'key_terms']:
        for item in context.get(etype, []):
            # Handle both string items and dict items
            if isinstance(item, str):
                name = item
                entity_id = item
            else:
                name = item.get('name', item.get('from', ''))
                entity_id = item.get('id', name)
            if name:
                entities[name.lower()] = entity_id
    
    if not entities:
        return  # No entities to analyze
    
    # Find entity occurrences in transcript
    entity_occurrences = defaultdict(list)
    text_lower = transcript_text.lower()
    
    for entity_name, entity_id in entities.items():
        if entity_name in text_lower:
            # Find approximate position (divide text into segments)
            segment_size = max(1, len(text_lower) // 100)
            pos = text_lower.find(entity_name)
            while pos >= 0:
                segment = pos // segment_size
                entity_occurrences[entity_name].append(segment)
                pos = text_lower.find(entity_name, pos + 1)
    
    # Compute co-occurrences (entities in same segment)
    cooccurrence = defaultdict(int)
    entity_names = list(entity_occurrences.keys())
    
    for i, e1 in enumerate(entity_names):
        for e2 in entity_names[i+1:]:
            segments1 = set(entity_occurrences[e1])
            segments2 = set(entity_occurrences[e2])
            common = segments1 & segments2
            if common:
                pair = tuple(sorted([e1, e2]))
                cooccurrence[pair] = len(common)
    
    # Build new implicit edges
    new_edges = []
    for (e1, e2), count in cooccurrence.items():
        if count >= 1:  # At least 1 co-occurrence
            new_edges.append({
                'source': entities[e1],
                'target': entities[e2],
                'type': 'co_occurs',
                'weight': count,
                'label': f'appears in {count} segment(s)'
            })
    
    if not new_edges:
        return
    
    # Merge with existing stored implicit relationships
    existing = load_implicit_relationships(game_title)
    existing_map = {}
    for edge in existing:
        key = tuple(sorted([edge.get('source', ''), edge.get('target', '')]))
        existing_map[key] = edge
    
    for edge in new_edges:
        key = tuple(sorted([edge['source'], edge['target']]))
        if key in existing_map:
            # Update weight if higher
            existing_map[key]['weight'] = max(existing_map[key].get('weight', 0), edge['weight'])
        else:
            existing_map[key] = edge
    
    # Save merged
    merged = list(existing_map.values())
    save_implicit_relationships(game_title, merged)


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
        game_key = game_title.lower().replace(" ", "_").strip()
        all_context.pop(game_key, None)
        with open(VERIFIED_CONTEXT_FILE, "w") as f:
            json.dump(all_context, f, indent=2)
    except Exception:
        pass


def clear_mempalace_for_game(game_title: str) -> Dict[str, Any]:
    """Clear MemPalace memory for a specific game."""
    result = {"cleared": False, "errors": []}

    if not game_title:
        result["errors"].append("No game title provided")
        return result

    try:
        mp_manager = _get_mempalace_manager()
        if not mp_manager:
            result["errors"].append("MemPalace not available")
            return result

        if mp_manager.clear_game_memory(game_title):
            result["cleared"] = True
            result["message"] = f"Cleared MemPalace memory for {game_title}"
        else:
            result["cleared"] = True
            result["message"] = f"No MemPalace memory found for {game_title}"

    except Exception as e:
        result["errors"].append(str(e))

    return result


def clear_all_context_for_game(game_title: str) -> Dict[str, Any]:
    """Clear both verified context and MemPalace memory for a game."""
    result = {"verified_cleared": False, "mempalace_cleared": False, "errors": []}
    
    if not game_title:
        result["errors"].append("No game title provided")
        return result
    
    # Clear verified context
    try:
        clear_verified_context(game_title)
        result["verified_cleared"] = True
    except Exception as e:
        result["errors"].append(f"Verified context: {e}")
    
    # Clear MemPalace
    try:
        mp_result = clear_mempalace_for_game(game_title)
        result["mempalace_cleared"] = mp_result.get("cleared", False)
        if mp_result.get("errors"):
            result["errors"].extend(mp_result["errors"])
    except Exception as e:
        result["errors"].append(f"MemPalace: {e}")
    
    return result


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
    resolved = copy.deepcopy(verified.get("context", {}))
    
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
    
    extracted_rel_keys = set()
    for rel in extracted_rels:
        key = _relationship_key(rel)
        if key[0] and key[1]:
            extracted_rel_keys.add(key)

    merged_rels = {}
    for rel in verified_rels:
        key = _relationship_key(rel)
        if key[0] and key[1]:
            merged_rels[key] = rel
    for rel in resolved_rels:
        key = _relationship_key(rel)
        if key[0] and key[1]:
            merged_rels[key] = rel
            if key not in extracted_rel_keys:
                changes["relationships_added"] = changes.get("relationships_added", [])
                changes["relationships_added"].append(rel)

    resolved["relationships"] = list(merged_rels.values())
    resolved["characters"] = sorted(extracted_chars | verified_chars)
    resolved["locations"] = sorted(extracted_locs | verified_locs)
    resolved["key_terms"] = sorted(
        set(extracted.get("key_terms", [])) | set(verified_ctx.get("key_terms", []))
    )
    
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
    """Format context for Web UI confirmation message."""
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
    print("Cogitator Context Manager")
    print(f"Workspace: {WORKSPACE}")
    print(f"Verified context file: {VERIFIED_CONTEXT_FILE}")
    print(f"Corrections file: {CONTEXT_CORRECTIONS_FILE}")