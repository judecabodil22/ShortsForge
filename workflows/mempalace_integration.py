#!/usr/bin/env python3
"""
MemPalace Integration Module for Cogitator

Enhanced MemPalace features:
- Cross-game entity merging (franchise-wide entity recognition)
- Timeline-aware scripting (chronology tracking)
- Correction memory (permanent learning from user fixes)
- Context-aware prompts (semantic memory retrieval)
- Relationship inference (auto-discover connections)
"""

import json
import os
import re
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from workflows.constants import WORKSPACE, CONTEXT_DIR

CUSTOM_FRANCHISES_FILE = os.path.join(CONTEXT_DIR, "custom_franchises.json")

def _load_custom_franchises() -> Dict[str, str]:
    """Load custom franchise mappings from JSON."""
    if os.path.exists(CUSTOM_FRANCHISES_FILE):
        try:
            with open(CUSTOM_FRANCHISES_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_custom_franchises(mapping: Dict[str, str]) -> None:
    """Save custom franchise mappings to JSON file."""
    os.makedirs(CONTEXT_DIR, exist_ok=True)
    with open(CUSTOM_FRANCHISES_FILE, "w") as f:
        json.dump(mapping, f, indent=2)

def add_to_franchise(game_key: str, franchise_key: str) -> bool:
    """Add a game to a franchise dynamically."""
    custom = _load_custom_franchises()
    custom[game_key] = franchise_key
    _save_custom_franchises(custom)
    return True

def get_full_series_mapping() -> Dict[str, str]:
    """Get the full series mapping (hardcoded + custom)."""
    custom = _load_custom_franchises()
    full_mapping = dict(SERIES_MAPPING)
    full_mapping.update(custom)
    return full_mapping

SERIES_MAPPING = {
    "the_shadow_of_the_tomb_raider": "tomb_raider_series",
    "shadow_of_the_tomb_raider": "tomb_raider_series",
    "rise_of_the_tomb_raider": "tomb_raider_series",
    "tomb_raider": "tomb_raider_series",
    "tomb_raider_(2013)": "tomb_raider_series",
    "tomb_raider_definitive_edition": "tomb_raider_series",
    "star_wars:_jedi_survivor": "star_wars_series",
    "star_wars_jedi_fallen_order": "star_wars_series",
}

MEMPALACE_GAME_KEYWORDS = {
    "tomb_raider_series": [
        "tomb raider", "lara croft", "trinity", "shadow of the tomb", "rise of the tomb",
        "peruvian jungle", "cozumel", "jonah",
    ],
    "star_wars_series": [
        "star wars", "jedi", "cal kestis", "bd-1", "empire", "rebel", "force",
        "lightsaber", "coruscant", "tanalorr", "jedha",
    ],
    "star_wars": [
        "star wars", "jedi", "cal kestis", "bd-1", "empire", "rebel", "force",
        "lightsaber", "coruscant", "tanalorr", "jedha",
    ],
    "star_wars:_jedi_survivor": [
        "star wars", "jedi", "cal kestis", "bd-1", "empire", "rebel", "force",
        "lightsaber", "coruscant", "tanalorr", "jedha",
    ],
    "cyberpunk_2077": ["cyberpunk", "night city", "johnny silverhand", "arasaka"],
    "tell_me_why": ["tell me why", "goblin", "allison", "tyler"],
}

MEMPALACE_CHROMA_DB = os.path.expanduser("~/.mempalace/palace/chroma.sqlite3")

# Lazy imports for optional dependencies
_mempalace_manager = None
_MEMPALACE_AVAILABLE = False

try:
    from game_data.mempalace import get_mempalace_manager
    _mempalace_manager = get_mempalace_manager()
    _MEMPALACE_AVAILABLE = True
except ImportError:
    pass


def _get_manager():
    """Get MemPalace manager if available."""
    global _mempalace_manager
    if _mempalace_manager is None and _MEMPALACE_AVAILABLE:
        try:
            from game_data.mempalace import get_mempalace_manager
            _mempalace_manager = get_mempalace_manager()
        except ImportError:
            pass
    return _mempalace_manager


def _get_franchise_key(game_title: str) -> Optional[str]:
    """Get the franchise key for a game."""
    game_key = game_title.lower().replace(" ", "_").strip()
    full_mapping = get_full_series_mapping()
    return full_mapping.get(game_key)


def _get_franchise_games(franchise_key: str) -> List[str]:
    """Get all games in a franchise."""
    full_mapping = get_full_series_mapping()
    games = []
    for game, franchise in full_mapping.items():
        if franchise == franchise_key:
            games.append(game)
    return games


# ─── Cross-Game Entity Merging ──────────────────────────────────────────────

def merge_entities_across_franchise(game_title: str) -> Dict[str, Any]:
    """
    Merge entities from all games in a franchise.
    
    Returns a unified entity database with cross-game references.
    """
    manager = _get_manager()
    if not manager:
        return {"merged": False, "reason": "MemPalace not available"}
    
    franchise_key = _get_franchise_key(game_title)
    if not franchise_key:
        return {"merged": False, "reason": "Game not in a franchise"}
    
    franchise_games = _get_franchise_games(franchise_key)
    
    # Collect entities from all games in the franchise
    all_entities = {
        "characters": defaultdict(lambda: {"games": [], "mentions": 0, "descriptions": []}),
        "locations": defaultdict(lambda: {"games": [], "mentions": 0, "descriptions": []}),
        "key_terms": defaultdict(lambda: {"games": [], "mentions": 0, "descriptions": []}),
    }
    
    for game in franchise_games:
        wing = manager._game_wing(game)
        memories = manager._query(wing, n=50)
        
        for memory in memories:
            text = memory.get("text", "")
            metadata = memory.get("metadata", {})
            
            # Extract entities from memory text
            entities = _extract_entities_from_text(text)
            
            for entity_type, entity_list in entities.items():
                if entity_type in all_entities:
                    for entity_name in entity_list:
                        normalized = entity_name.lower().strip()
                        all_entities[entity_type][normalized]["games"].append(game)
                        all_entities[entity_type][normalized]["mentions"] += 1
                        if text not in all_entities[entity_type][normalized]["descriptions"]:
                            all_entities[entity_type][normalized]["descriptions"].append(text[:200])
    
    # Convert to serializable format
    result = {}
    for entity_type, entities in all_entities.items():
        result[entity_type] = {
            name: {
                "games": list(set(data["games"])),
                "mentions": data["mentions"],
                "descriptions": data["descriptions"][:3],  # Limit descriptions
                "cross_game": len(set(data["games"])) > 1
            }
            for name, data in entities.items()
            if data["mentions"] >= 2  # Only entities mentioned multiple times
        }
    
    return {
        "merged": True,
        "franchise": franchise_key,
        "games": franchise_games,
        "entities": result,
        "stats": {
            "characters": len(result.get("characters", {})),
            "locations": len(result.get("locations", {})),
            "key_terms": len(result.get("key_terms", {})),
            "cross_game_characters": sum(1 for c in result.get("characters", {}).values() if c["cross_game"]),
        }
    }


def get_unified_entity_context(game_title: str) -> str:
    """
    Get a unified entity context string for script generation.
    Includes entities from all games in the franchise.
    """
    merged = merge_entities_across_franchise(game_title)
    if not merged.get("merged"):
        return ""
    
    lines = []
    
    # Cross-game characters
    cross_game_chars = [
        (name, data) for name, data in merged.get("entities", {}).get("characters", {}).items()
        if data["cross_game"]
    ]
    
    if cross_game_chars:
        lines.append("UNIFIED FRANCHISE CHARACTERS (appear across multiple games):")
        for name, data in cross_game_chars[:10]:  # Limit to top 10
            games = ", ".join(data["games"][:3])
            lines.append(f"- {name.title()}: appears in {games}")
    
    # Cross-game locations
    cross_game_locs = [
        (name, data) for name, data in merged.get("entities", {}).get("locations", {}).items()
        if data["cross_game"]
    ]
    
    if cross_game_locs:
        lines.append("\nUNIFIED FRANCHISE LOCATIONS:")
        for name, data in cross_game_locs[:5]:
            games = ", ".join(data["games"][:3])
            lines.append(f"- {name.title()}: appears in {games}")
    
    return "\n".join(lines)


def _extract_entities_from_text(text: str) -> Dict[str, List[str]]:
    """Extract entity names from text using simple heuristics."""
    entities = {"characters": [], "locations": [], "key_terms": []}
    
    # Look for capitalized words (potential character names)
    char_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
    chars = re.findall(char_pattern, text)
    
    # Common location indicators
    loc_indicators = ["city", "village", "temple", "ruins", "forest", "mountain", "cave", "palace", "fortress"]
    
    text_lower = text.lower()
    
    for word in chars:
        if len(word) > 2:
            # Check if a location indicator is near this word (within 50 chars)
            word_pos = text_lower.find(word.lower())
            is_location = False
            if word_pos >= 0:
                for ind in loc_indicators:
                    # Search in a window around the word
                    start = max(0, word_pos - 50)
                    end = min(len(text_lower), word_pos + len(word) + 50)
                    if ind in text_lower[start:end]:
                        is_location = True
                        break
            if is_location:
                entities["locations"].append(word)
            else:
                entities["characters"].append(word)
    
    return entities


# ─── Timeline-Aware Scripting ───────────────────────────────────────────────

def build_game_timeline(game_title: str) -> Dict[str, Any]:
    """
    Build a timeline of events from MemPalace memories.
    
    Returns a chronological list of events for timeline-aware scripting.
    """
    manager = _get_manager()
    if not manager:
        return {"timeline": [], "reason": "MemPalace not available"}
    
    wing = manager._game_wing(game_title)
    memories = manager._query(wing, "transcripts", n=100)
    
    events = []
    for i, memory in enumerate(memories):
        text = memory.get("text", "")
        metadata = memory.get("metadata", {})
        
        # Extract temporal markers
        temporal_markers = _extract_temporal_markers(text)
        
        events.append({
            "index": i,
            "text_preview": text[:150],
            "temporal_markers": temporal_markers,
            "source": metadata.get("source_file", "unknown"),
        })
    
    # Sort by temporal markers if possible
    events.sort(key=lambda x: x.get("temporal_markers", {}).get("order", 0))
    
    return {
        "timeline": events,
        "total_events": len(events),
        "has_temporal_data": any(e["temporal_markers"] for e in events),
    }


def _extract_temporal_markers(text: str) -> Dict[str, Any]:
    """Extract temporal markers from text."""
    markers = {}
    
    # Common temporal patterns
    patterns = {
        "beginning": r"\b(first|beginning|start|initially|at first)\b",
        "middle": r"\b(then|next|after|later|subsequently|meanwhile)\b",
        "end": r"\b(finally|last|end|conclude|eventually|in the end)\b",
        "flashback": r"\b(remember|recall|back then|previously|earlier)\b",
    }
    
    for marker_type, pattern in patterns.items():
        if re.search(pattern, text.lower()):
            markers[marker_type] = True
    
    # Assign order based on markers
    if "beginning" in markers:
        markers["order"] = 1
    elif "middle" in markers:
        markers["order"] = 2
    elif "end" in markers:
        markers["order"] = 3
    elif "flashback" in markers:
        markers["order"] = 0.5  # Before beginning
    else:
        markers["order"] = 2  # Default to middle
    
    return markers


def get_timeline_context(game_title: str, current_segment: str = "") -> str:
    """
    Get timeline context for script generation.
    
    Helps prevent chronology errors by providing temporal context.
    """
    timeline = build_game_timeline(game_title)
    if not timeline.get("timeline"):
        return ""
    
    lines = ["GAME TIMELINE (for chronological accuracy):"]
    
    # Summarize key events
    for i, event in enumerate(timeline["timeline"][:10]):
        markers = event.get("temporal_markers", {})
        phase = "Unknown"
        if "beginning" in markers:
            phase = "Early"
        elif "middle" in markers:
            phase = "Mid"
        elif "end" in markers:
            phase = "Late"
        elif "flashback" in markers:
            phase = "Flashback"
        
        lines.append(f"{i+1}. [{phase}] {event['text_preview'][:80]}...")
    
    lines.append("\nIMPORTANT: Maintain chronological accuracy. Don't reference events out of order.")
    
    return "\n".join(lines)


# ─── Correction Memory ──────────────────────────────────────────────────────

def store_correction_to_mempalace(game_title: str, correction: Dict[str, Any]) -> bool:
    """
    Store a user correction to MemPalace for permanent learning.
    
    This ensures corrections persist across database resets and pipeline runs.
    """
    manager = _get_manager()
    if not manager:
        return False
    
    wing = manager._game_wing(game_title)
    
    correction_text = f"""
CORRECTION LEARNED:
Type: {correction.get('type', 'unknown')}
Original: {correction.get('original', 'N/A')}
Corrected: {correction.get('corrected', 'N/A')}
Reason: {correction.get('reason', 'User corrected')}
Timestamp: {datetime.now().isoformat()}
AVOID: Do not use '{correction.get('original', '')}' again.
USE INSTEAD: '{correction.get('corrected', '')}'
"""
    
    count = manager._add(wing, "corrections", correction_text, f"correction_{datetime.now().isoformat()}")
    return count > 0


def get_learned_corrections(game_title: str) -> List[Dict[str, Any]]:
    """
    Retrieve all learned corrections for a game.
    
    These are injected into prompts to prevent repeating mistakes.
    """
    manager = _get_manager()
    if not manager:
        return []
    
    wing = manager._game_wing(game_title)
    memories = manager._query(wing, "corrections", n=50)
    
    corrections = []
    for memory in memories:
        text = memory.get("text", "")
        if "CORRECTION LEARNED:" in text:
            correction = {
                "original": _extract_field(text, "Original:"),
                "corrected": _extract_field(text, "Corrected:"),
                "reason": _extract_field(text, "Reason:"),
                "avoid": _extract_field(text, "AVOID:"),
                "use_instead": _extract_field(text, "USE INSTEAD:"),
            }
            if correction["original"] or correction["corrected"]:
                corrections.append(correction)
    
    return corrections


def get_corrections_context(game_title: str) -> str:
    """
    Get corrections context string for script generation.
    
    Injects learned corrections into prompts to prevent repeating mistakes.
    """
    corrections = get_learned_corrections(game_title)
    if not corrections:
        return ""
    
    lines = ["LEARNED CORRECTIONS (AVOID these mistakes):"]
    for c in corrections[:10]:  # Limit to 10 most recent
        if c["avoid"] and c["use_instead"]:
            lines.append(f"- AVOID: {c['avoid']} → USE: {c['use_instead']}")
        elif c["original"] and c["corrected"]:
            lines.append(f"- AVOID: {c['original']} → USE: {c['corrected']}")
    
    return "\n".join(lines)


def _extract_field(text: str, field_name: str) -> str:
    """Extract a field value from correction text."""
    pattern = rf"{re.escape(field_name)}\s*(.+?)(?:\n|$)"
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""


# ─── Context-Aware Prompts ──────────────────────────────────────────────────

def get_context_aware_memory(game_title: str, transcript_segment: str = "", n: int = 5) -> str:
    """
    Retrieve contextually relevant memories for script generation.
    
    Uses semantic search to find memories relevant to the current transcript.
    """
    manager = _get_manager()
    if not manager:
        return ""
    
    wing = manager._game_wing(game_title)
    
    # Try semantic search if we have a transcript segment
    if transcript_segment:
        try:
            from mempalace.searcher import search_memories
            result = search_memories(
                query=transcript_segment[:500],  # Limit query length
                palace_path=manager.palace_path,
                wing=wing,
                room="transcripts",
                n_results=n,
            )
            if "error" not in result:
                memories = result.get("results", [])
                return _format_memories_for_prompt(memories, game_title)
        except Exception:
            pass
    
    # Fallback to general memory retrieval
    memories = manager._query(wing, n=n)
    return _format_memories_for_prompt(memories, game_title)


def _format_memories_for_prompt(memories: List[Dict], game_title: str) -> str:
    """Format memories for injection into prompts."""
    if not memories:
        return ""
    
    lines = [f"RELEVANT MEMORIES FROM {game_title.upper()}:"
]
    for i, memory in enumerate(memories[:5]):
        text = memory.get("text", "")[:200]
        if text:
            lines.append(f"{i+1}. {text}")
    
    return "\n".join(lines)


def get_enhanced_prompt_hints(game_title: str, transcript_segment: str = "") -> str:
    """
    Get enhanced prompt hints combining all MemPalace features.
    
    Replaces the broken _get_mempalace_prompt_hints function.
    """
    hints = []
    
    # 1. Cross-game entity context
    entity_context = get_unified_entity_context(game_title)
    if entity_context:
        hints.append(entity_context)
    
    # 2. Timeline context
    timeline_context = get_timeline_context(game_title, transcript_segment)
    if timeline_context:
        hints.append(timeline_context)
    
    # 3. Learned corrections
    corrections_context = get_corrections_context(game_title)
    if corrections_context:
        hints.append(corrections_context)
    
    # 4. Context-aware memories
    if transcript_segment:
        memory_context = get_context_aware_memory(game_title, transcript_segment)
        if memory_context:
            hints.append(memory_context)
    
    return "\n\n".join(hints)


# ─── Relationship Inference ─────────────────────────────────────────────────

def infer_relationships_from_memories(game_title: str) -> List[Dict[str, Any]]:
    """
    Infer implicit relationships from MemPalace memories.
    
    Analyzes co-occurrence patterns to discover relationships.
    """
    manager = _get_manager()
    if not manager:
        return []
    
    wing = manager._game_wing(game_title)
    memories = manager._query(wing, "transcripts", n=100)
    
    # Build co-occurrence matrix
    co_occurrences = defaultdict(lambda: defaultdict(int))
    entity_mentions = defaultdict(int)
    
    for memory in memories:
        text = memory.get("text", "")
        entities = _extract_entities_from_text(text)
        
        # Get all character names from this memory
        chars = entities.get("characters", [])
        for char in chars:
            entity_mentions[char] += 1
        
        # Record co-occurrences
        for i, char1 in enumerate(chars):
            for char2 in chars[i+1:]:
                co_occurrences[char1][char2] += 1
                co_occurrences[char2][char1] += 1
    
    # Infer relationships from strong co-occurrences
    inferred = []
    threshold = 3  # Minimum co-occurrences to infer relationship
    
    for char1, neighbors in co_occurrences.items():
        for char2, count in neighbors.items():
            if count >= threshold and entity_mentions[char1] >= 2 and entity_mentions[char2] >= 2:
                # Determine relationship type based on context
                rel_type = _infer_relationship_type(char1, char2, memories)
                
                inferred.append({
                    "entity1": char1,
                    "entity2": char2,
                    "type": rel_type,
                    "strength": count,
                    "confidence": min(count / 10, 1.0),  # Normalize to 0-1
                    "source": "inference",
                })
    
    # Deduplicate and sort by strength
    seen = set()
    unique_inferred = []
    for rel in sorted(inferred, key=lambda x: x["strength"], reverse=True):
        key = tuple(sorted([rel["entity1"], rel["entity2"]]))
        if key not in seen:
            seen.add(key)
            unique_inferred.append(rel)
    
    return unique_inferred[:20]  # Limit to top 20


def _infer_relationship_type(char1: str, char2: str, memories: List[Dict]) -> str:
    """Infer relationship type from context."""
    # Simple heuristic based on common patterns
    friend_indicators = ["friend", "ally", "companion", "partner", "together"]
    enemy_indicators = ["enemy", "rival", "opponent", "fight", "battle", "against"]
    family_indicators = ["father", "mother", "brother", "sister", "son", "daughter", "family"]
    
    # Check memories for relationship indicators
    for memory in memories:
        text = memory.get("text", "").lower()
        if char1.lower() in text and char2.lower() in text:
            if any(ind in text for ind in family_indicators):
                return "family"
            if any(ind in text for ind in enemy_indicators):
                return "enemy"
            if any(ind in text for ind in friend_indicators):
                return "ally"
    
    return "associated"


def get_inferred_relationships_context(game_title: str) -> str:
    """
    Get inferred relationships context for script generation.
    """
    inferred = infer_relationships_from_memories(game_title)
    if not inferred:
        return ""
    
    lines = ["INFERRED RELATIONSHIPS (from transcript analysis):"]
    for rel in inferred[:10]:
        lines.append(
            f"- {rel['entity1'].title()} ↔ {rel['entity2'].title()}: "
            f"{rel['type']} (confidence: {rel['confidence']:.0%})"
        )
    
    return "\n".join(lines)


# ─── Public API ─────────────────────────────────────────────────────────────

def get_all_mempalace_context(game_title: str, transcript_segment: str = "") -> str:
    """
    Get all MemPalace context for script generation.
    
    Combines all features into a single context string.
    """
    if not _MEMPALACE_AVAILABLE:
        return ""
    
    parts = []
    
    # Cross-game entity merging
    entity_context = get_unified_entity_context(game_title)
    if entity_context:
        parts.append(entity_context)
    
    # Timeline context
    timeline_context = get_timeline_context(game_title, transcript_segment)
    if timeline_context:
        parts.append(timeline_context)
    
    # Learned corrections
    corrections_context = get_corrections_context(game_title)
    if corrections_context:
        parts.append(corrections_context)
    
    # Inferred relationships
    relationships_context = get_inferred_relationships_context(game_title)
    if relationships_context:
        parts.append(relationships_context)
    
    # Context-aware memories
    if transcript_segment:
        memory_context = get_context_aware_memory(game_title, transcript_segment)
        if memory_context:
            parts.append(memory_context)

    # Closed-loop quality: inject best-performing prompt patterns
    try:
        from game_data.mempalace import get_mempalace_manager

        mgr = get_mempalace_manager()
        if mgr and hasattr(mgr, "get_best_prompts"):
            best = mgr.get_best_prompts(game_title) or []
            if best:
                lines = ["[TOP QUALITY PATTERNS FROM PAST SCRIPTS]"]
                for item in best[:5]:
                    if isinstance(item, dict):
                        variant = item.get("variant") or item.get("source") or "unknown"
                        fact = item.get("factuality", item.get("score", ""))
                        eng = item.get("engagement", "")
                        lines.append(f"- variant={variant} factuality={fact} engagement={eng}")
                    else:
                        lines.append(f"- {item}")
                parts.append("\n".join(lines))
    except Exception:
        pass

    if not parts:
        return ""
    
    return "\n\n---\n\n".join(parts)


def sync_correction_to_mempalace(game_title: str, original: str, corrected: str, reason: str = "") -> bool:
    """
    Sync a user correction to MemPalace.
    
    This is called when the user corrects a context entity.
    """
    correction = {
        "type": "entity_correction",
        "original": original,
        "corrected": corrected,
        "reason": reason or "User corrected",
        "timestamp": datetime.now().isoformat(),
    }
    
    return store_correction_to_mempalace(game_title, correction)


def get_mempalace_status() -> Dict[str, Any]:
    """Get MemPalace integration status."""
    manager = _get_manager()
    if not manager:
        return {
            "available": False,
            "reason": "MemPalace not installed or import failed",
        }
    
    status = manager.status()
    return {
        "available": True,
        "total_drawers": status.get("total_drawers", 0),
        "games": status.get("games", {}),
    }


def get_mempalace_text_chunks(game_key: str) -> List[str]:
    """Return MemPalace narrative chunks relevant to a franchise (from ChromaDB)."""
    import os
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

