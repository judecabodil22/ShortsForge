import os
import re
from workflows.constants import WORKSPACE, CONTEXT_DIR

try:
    from rapidfuzz import fuzz as _fuzz
except ImportError:
    _fuzz = None

def _cs_load_context():
    """Load context from centralized Context directory (handles both list and table format)."""
    ctx = {
        "characters": [],
        "locations": [],
        "key_terms": [],
        "relationships": [],
        "processed_transcripts": [],
        "previous_scripts": []
    }
    
    # Read GAME_TITLE from .env
    game_title = "default"
    env_path = os.path.join(WORKSPACE, ".env")
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if line.strip().startswith("GAME_TITLE="):
                    game_title = line.strip().split("=", 1)[1].strip().strip('"')
                    break

    game = game_title.lower().replace(" ", "_")
    ctx_dir = os.path.join(CONTEXT_DIR, game)
    os.makedirs(ctx_dir, exist_ok=True)
    
    def extract_from_list(line):
        """Extract name from list item or table cell."""
        name = line.strip()
        if name.startswith('[[') and name.endswith(']]'):
            name = name[2:-2]
        return name
    
    # Helper to extract items from table
    def extract_items_from_table(content, category):
        items = []
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('|') and '---' not in line:
                parts = [p.strip() for p in line.split('|')[1:-1]]
                if parts and parts[0]:
                    item = extract_from_table_cell(parts[0])
                    # Skip header rows
                    if item and item.lower() not in ['name', 'character', 'location', 'term', 'character a'] and item not in items:
                        items.append(item)
        return items
    
    # Load alias maps from verified_context.json for cross-run persistence
    try:
        if game_title:
            from workflows.context_manager_v2 import load_verified_context
            verified = load_verified_context(game_title)
            if isinstance(verified, dict):
                if verified.get("character_aliases"):
                    ctx["character_aliases"] = verified["character_aliases"]
                if verified.get("location_aliases"):
                    ctx["location_aliases"] = verified["location_aliases"]
    except Exception:
        pass

    def extract_from_table_cell(cell):
        """Extract name from table cell."""
        cell = cell.strip()
        if cell.startswith('[[') and cell.endswith(']]'):
            return cell[2:-2]
        return cell
    
    def extract_from_table(line):
        """Extract items from table row."""
        if not line.startswith('|') or '---' in line:
            return []
        parts = [p.strip() for p in line.split('|')[1:-1]]
        if not parts or not parts[0]:
            return []
        # First column contains the name (may have wiki-links)
        name = parts[0].strip()
        if name.startswith('[[') and name.endswith(']]'):
            name = name[2:-2]
        # Skip header rows
        if name.lower() in ['name', 'character', 'location', 'term', 'character a']:
            return []
        return [name] if name else []
    
    # Load characters from markdown (table format)
    chars_file = os.path.join(ctx_dir, "characters.md")
    if os.path.exists(chars_file):
        with open(chars_file, 'r') as f:
            content = f.read()
        for line in content.split('\n'):
            items = extract_from_table(line)
            for item in items:
                if item and item not in ctx["characters"]:
                    ctx["characters"].append(item)
    
    # Load locations from markdown (table format)
    locs_file = os.path.join(ctx_dir, "locations.md")
    if os.path.exists(locs_file):
        with open(locs_file, 'r') as f:
            content = f.read()
        for line in content.split('\n'):
            items = extract_from_table(line)
            for item in items:
                if item and item not in ctx["locations"]:
                    ctx["locations"].append(item)
    
    # Load key_terms from markdown (table format)
    terms_file = os.path.join(ctx_dir, "key_terms.md")
    if os.path.exists(terms_file):
        with open(terms_file, 'r') as f:
            content = f.read()
        for line in content.split('\n'):
            items = extract_from_table(line)
            for item in items:
                if item and item not in ctx["key_terms"]:
                    ctx["key_terms"].append(item)
    
    # Load relationships from markdown
    rels_file = os.path.join(ctx_dir, "relationships.md")
    if os.path.exists(rels_file):
        with open(rels_file, 'r') as f:
            content = f.read()
        
        # For relationships, handle table format: Character A | Connection | Character B
        if '|' in content and '---' in content:
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('|') and '---' not in line:
                    # Skip header
                    if 'Character A' in line or 'Character' in line:
                        continue
                    
                    parts = [p.strip() for p in line.split('|')[1:-1]]
                    if len(parts) >= 3:
                        # Parse: Character A | Connection | Character B
                        char_a = extract_from_table_cell(parts[0])
                        connection = parts[1]
                        char_b = extract_from_table_cell(parts[2])
                        
                        # Skip if Character A is empty or just "-"
                        if not char_a or char_a == '-':
                            continue
                        
                        # Build relationship string
                        if char_b and char_b != '-':
                            rel = f"{char_a} and {char_b} are {connection}"
                        else:
                            # Single character relationship
                            rel = f"{char_a} is {connection}"
                        
                        if rel and rel not in ctx["relationships"]:
                            ctx["relationships"].append(rel)
        else:
            # Fall back to list format
            for line in content.split('\n'):
                line = line.strip()
                if not line or line.startswith('#') or not line.startswith('- '):
                    continue
                rel_line = line.lstrip('- ').strip()
                rel = rel_line
                rel = re.sub(r'\[\[([^\]]+)\]\]', r'\1', rel)
                if rel and rel not in ctx["relationships"]:
                    ctx["relationships"].append(rel)
    
    return ctx


from typing import Dict, Any, List
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

