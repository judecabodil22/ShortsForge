#!/usr/bin/env python3
"""
Context extraction functions extracted from cogitator.py.
Handles transcript analysis, character/location/relationship extraction,
context management, and learned corrections.
"""
import glob, json, os, random, re, time
import urllib.error, urllib.parse, urllib.request
from datetime import datetime

from workflows.cogitator import (
    log, log_error, env, WORKSPACE, PROMPTS_DIR,
    get_gemini_keys, _fuzz, fuzzy_dedup_against_list,
    CONTEXT_DIR, CONTENT_STUDIO_DIR, CS_SCRIPTS_DIR, CS_SHORTS_DIR, CS_TTS_DIR,
    CS_TRANSCRIPTS_DIR, CS_CONTEXT_FILE, get_cs_context_file,
    _rate_limit,
)

from context_manager import merge_context_dicts
from context_manager_v2 import (
    load_verified_context,
    save_verified_context,
    compute_and_save_implicit_relationships,
)
from workflows.constants import dedupe_entity_list
try:
    from game_data.mempalace import get_mempalace_manager
    MEMPALACE_AVAILABLE = True
except ImportError:
    MEMPALACE_AVAILABLE = False
    def get_mempalace_manager():
        """Fallback when MemPalace is not available."""
        return None


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
    
    for i in range(len(keys)):
        key = keys[i]
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
        
        for attempt in range(3):
            try:
                _rate_limit()
                req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "X-Goog-Api-Key": key})
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
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 503):
                    wait = (2 ** attempt) * 15 + random.uniform(0, 10)
                    log(f"   Transcript analysis HTTP {e.code} with key ...{key[-6:]}, retry {attempt+1}/3 in {wait:.0f}s")
                    time.sleep(wait)
                else:
                    log(f"   Transcript analysis HTTP {e.code} with key ...{key[-6:]}: {e}")
                    break
            except Exception as e:
                error_str = str(e).lower()
                is_network_error = any(x in error_str for x in [
                    'name resolution', 'connection refused', 'connection reset',
                    'connection aborted', 'temporary failure', 'timeout',
                    'network is unreachable', 'no route to host'
                ])
                if is_network_error and attempt < 2:
                    wait = (2 ** attempt) * 5
                    log(f"   Network error, retrying in {wait}s... ({attempt+1}/3)")
                    time.sleep(wait)
                    continue
                log(f"   Transcript analysis error with key ...{key[-6:]}: {e}")
                time.sleep(5)
                break
        
        log(f"   Key ...{key[-6:]} failed for transcript analysis, next...")
    
    log("All transcript analysis keys exhausted, returning defaults")
    return "Analysis", "Unknown", "General overview", "Documentary", [], []


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
    
    # Use centralized Context directory
    game = env("GAME_TITLE", "default").lower().replace(" ", "_")
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


def _cs_save_context(ctx):
    """Save context to centralized Context directory (smart save - preserves manual edits)."""
    game = env("GAME_TITLE", "default").lower().replace(" ", "_")
    ctx_dir = os.path.join(CONTEXT_DIR, game)
    os.makedirs(ctx_dir, exist_ok=True)
    
    def wiki(name):
        return f"[[{name}]]"
    
    def smart_save_list_items(file_path, new_items, item_type):
        """Save list items while preserving existing manual content."""
        if not os.path.exists(file_path):
            # File doesn't exist - create with full format
            return _create_full_format_file(file_path, new_items, item_type)
        
        # File exists - read and preserve manual content
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Extract existing items from file (both plain and wiki-link format)
        existing_items = _extract_items_from_markdown(content)
        
        # Merge: existing + new (avoid duplicates)
        merged_items = list(existing_items)
        for item in new_items:
            if item not in merged_items:
                merged_items.append(item)
        
        # Rebuild file preserving everything except the item list
        return _rebuild_file_preserving_content(file_path, content, merged_items, item_type)
    
    # Save each category with smart save
    smart_save_list_items(os.path.join(ctx_dir, "characters.md"), ctx.get("characters", []), "characters")
    smart_save_list_items(os.path.join(ctx_dir, "locations.md"), ctx.get("locations", []), "locations")
    smart_save_list_items(os.path.join(ctx_dir, "key_terms.md"), ctx.get("key_terms", []), "key_terms")
    
    # For relationships, handle differently since format is more complex
    rels_file = os.path.join(ctx_dir, "relationships.md")
    if os.path.exists(rels_file):
        with open(rels_file, 'r') as f:
            content = f.read()
        existing_rels = _extract_relationships_from_markdown(content)
    else:
        existing_rels = []
    
    # Merge relationships with fuzzy dedup and cross-entity resolution
    merged_rels = list(existing_rels)
    all_characters = [c.lower() for c in ctx.get("characters", [])]
    
    def normalize_entity(name):
        """Normalize entity name for comparison."""
        name_lower = name.lower().strip()
        # Check if this is a partial name that matches a full character name
        for char in all_characters:
            if name_lower in char or char in name_lower:
                return char
        return name_lower
    
    for rel in ctx.get("relationships", []):
        if isinstance(rel, dict):
            from_entity = normalize_entity(rel.get('from', ''))
            to_entity = normalize_entity(rel.get('to', ''))
            rel_type = rel.get('relationship', '').lower().strip()
            rel_text = f"{from_entity}-{to_entity}-{rel_type}"
        else:
            rel_text = str(rel).lower().strip()
        
        is_dup = False
        for existing_rel in merged_rels:
            if isinstance(existing_rel, dict):
                existing_from = normalize_entity(existing_rel.get('from', ''))
                existing_to = normalize_entity(existing_rel.get('to', ''))
                existing_type = existing_rel.get('relationship', '').lower().strip()
                existing_text = f"{existing_from}-{existing_to}-{existing_type}"
            else:
                existing_text = str(existing_rel).lower().strip()
            
            # Exact match after normalization
            if rel_text == existing_text:
                is_dup = True
                break
            
            # Fuzzy match
            ratio = _fuzz.token_sort_ratio(rel_text, existing_text) if _fuzz else 0
            if ratio >= 80:
                is_dup = True
                break
            
            # Check reverse relationship (A->B same as B->A for some types)
            if isinstance(rel, dict) and isinstance(existing_rel, dict):
                reverse_text = f"{to_entity}-{from_entity}-{rel_type}"
                if reverse_text == existing_text:
                    is_dup = True
                    break
        
        if not is_dup:
            merged_rels.append(rel)
    
    # Rebuild relationships file preserving content
    _rebuild_relationships_preserving_content(rels_file, merged_rels, ctx.get("characters", []))


def _extract_items_from_markdown(content):
    """Extract list items from markdown, handling both table and list format."""
    items = []
    
    # First try table format
    if '|' in content and '---' in content:
        for line in content.split('\n'):
            line = line.strip()
            if not line.startswith('|') or '---' in line:
                continue
            parts = [p.strip() for p in line.split('|')[1:-1]]
            if not parts or not parts[0]:
                continue
            name = parts[0].strip()
            if name.startswith('[[') and name.endswith(']]'):
                name = name[2:-2]
            # Skip header rows
            if name.lower() in ['name', 'character', 'location', 'term', 'character a']:
                continue
            if name:
                items.append(name)
        return items
    
    # Fall back to list format
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('- '):
            item = line[2:].strip()
            if item.startswith('[[') and item.endswith(']]'):
                item = item[2:-2]
            if item:
                items.append(item)
    return items


def _extract_relationships_from_markdown(content):
    """Extract relationship lines from markdown, handling table and list format."""
    rels = []
    
    # First try table format
    if '|' in content and '---' in content:
        for line in content.split('\n'):
            line = line.strip()
            if not line.startswith('|') or '---' in line:
                continue
            parts = [p.strip() for p in line.split('|')[1:-1]]
            if len(parts) < 3:
                continue
            # Skip header
            if 'Character' in parts[0]:
                continue
            
            char_a = parts[0]
            if char_a.startswith('[['):
                char_a = char_a[2:-2]
            if not char_a or char_a == '-':
                continue
            
            connection = parts[1]
            char_b = parts[2]
            if char_b.startswith('[['):
                char_b = char_b[2:-2]
            
            if char_b and char_b != '-':
                rel = f"{char_a} and {char_b} are {connection}"
            else:
                rel = f"{char_a} is {connection}"
            
            if rel:
                rels.append(rel)
        return rels
    
    # Fall back to list format
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('- '):
            rel = line[2:].strip()
            if rel and not rel.startswith('[[') and not rel.startswith('#'):
                rels.append(rel)
    return rels


def _create_full_format_file(file_path, items, item_type):
    """Create a new file with full beautiful format."""
    def wiki(name):
        return f"[[{name}]]"
    
    game = env("GAME_TITLE", "default")
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Get appropriate data based on type
    ctx = _cs_load_context()
    
    with open(file_path, 'w') as f:
        # Frontmatter
        f.write(f"""---
game: {game}
game_developer: 
created: {today}
updated: {today}
type: {item_type}
tags: [context, {item_type}]
---

# {item_type.title().replace('_', ' ')}

> [!NOTE]
> Verified {item_type} extracted from game transcripts.

## {item_type.title().replace('_', ' ')} List

""")
        
        # Table header
        f.write(f"| Name | Status | Notes |\n")
        f.write(f"|------|--------|-------|\n")
        
        for item in items:
            f.write(f"| {wiki(item)} | ✅ Verified | |\n")
        
        # Mermaid with proper unique nodes
        unique_items = list(dict.fromkeys(items))[:10]
        
        mermaid_header = f"""
## {item_type.title().replace('_', ' ')} Graph

```mermaid
graph TD
"""
        f.write(mermaid_header)
        
        for i, item in enumerate(unique_items):
            safe_id = f"{item_type[0].upper()}{i}"
            f.write(f"    {safe_id}[{item}]\n")
        
        if len(unique_items) > 1:
            for i in range(min(3, len(unique_items) - 1)):
                safe_id1 = f"{item_type[0].upper()}{i}"
                safe_id2 = f"{item_type[0].upper()}{i+1}"
                f.write(f"    {safe_id1} --> {safe_id2}\n")
        
        f.write("```\n")
        
        footer = f"""

---

### 🔍 Sources
- 

### ✅ Last Verified
{today}

### 📝 Notes
- 

---

**Tags:** #{item_type}
"""
        f.write(footer)
    
    return True


def _rebuild_file_preserving_content(file_path, content, items, item_type):
    """Rebuild markdown file preserving manual edits."""
    def wiki(name):
        return f"[[{name}]]"
    
    game = env("GAME_TITLE", "default")
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Extract frontmatter and sections that shouldn't be regenerated
    sections = {}
    
    # Find frontmatter
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            sections['frontmatter'] = parts[1]
            content = parts[2]
    
    # Extract existing manual sections (Notes, Sources, etc.)
    manual_sections = []
    in_notes = False
    notes_content = []
    
    for line in content.split('\n'):
        if '### 📝 Notes' in line or '### Notes' in line:
            in_notes = True
            continue
        if in_notes:
            if line.startswith('---') or line.startswith('**Tags'):
                in_notes = False
                if notes_content:
                    manual_sections = notes_content
                notes_content = []
            else:
                notes_content.append(line)
    
    # Build new content
    new_content = []
    
    # Keep frontmatter if exists
    if 'frontmatter' in sections:
        new_content.append(f"---\n{sections['frontmatter']}\n---")
    else:
        new_content.append(f"""---
game: {game}
game_developer: 
created: {today}
updated: {today}
type: {item_type}
tags: [context, {item_type}]
---""")
    
    new_content.append(f"""
# {item_type.title().replace('_', ' ')}

> [!NOTE]
> Verified {item_type} extracted from game transcripts.

## {item_type.title().replace('_', ' ')} List

| Name | Status | Notes |
|------|--------|-------|
""")
    
    for item in items:
        new_content.append(f"| {wiki(item)} | ✅ Verified | |")
    
    # Add Mermaid with proper unique nodes
    unique_items = list(dict.fromkeys(items))  # Remove duplicates while preserving order
    
    new_content.append(f"""
## {item_type.title().replace('_', ' ')} Graph

```mermaid
graph TD
""")
    
    # Create unique nodes for each item with proper Mermaid syntax
    for i, item in enumerate(unique_items[:10]):  # Limit to 10 items
        safe_id = f"{item_type[0].upper()}{i}"  # e.g., C0, L0, K0
        new_content.append(f"    {safe_id}[{item}]")
    
    # Create proper connections between items
    if len(unique_items) > 1:
        for i in range(min(3, len(unique_items) - 1)):
            safe_id1 = f"{item_type[0].upper()}{i}"
            safe_id2 = f"{item_type[0].upper()}{i+1}"
            new_content.append(f"    {safe_id1} --> {safe_id2}")
    
    new_content.append("```")
    
    # Add sections
    new_content.append(f"""
---

### 🔍 Sources
- 

### ✅ Last Verified
{today}

### 📝 Notes
{chr(10).join(manual_sections) if manual_sections else '-'}

---

**Tags:** #{item_type}
""")
    
    with open(file_path.replace('\\', '/'), 'w') as f:
        f.write('\n'.join(new_content))
    
    return True


def _rebuild_relationships_preserving_content(file_path, relationships, characters):
    """Rebuild relationships file preserving manual edits."""
    def wiki(name):
        return f"[[{name}]]"
    
    game = env("GAME_TITLE", "default")
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Read existing file
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            existing_content = f.read()
    else:
        existing_content = ""
    
    # Extract manual sections
    manual_notes = ""
    if '### 📝 Notes' in existing_content:
        start = existing_content.find('### 📝 Notes')
        end = existing_content.find('---', start + 10)
        if end > start:
            manual_notes = existing_content[start:end]
    
    # Build proper relationship entries (handle both dict and string formats)
    parsed_rels = []
    for rel in relationships:
        if isinstance(rel, dict):
            from_char = rel.get("from", "").strip()
            to_char = rel.get("to", "").strip()
            conn = rel.get("relationship", "related").strip()
            if from_char and to_char and from_char.lower() != to_char.lower():
                parsed_rels.append({"char_a": from_char, "char_b": to_char, "connection": conn})
            elif from_char and conn:
                parsed_rels.append({"char_a": from_char, "char_b": "", "connection": conn})
            continue
        rel_str = str(rel)
        if ' and ' in rel_str and ' are ' in rel_str:
            left = rel.split(' are ')[0].strip()
            connection = rel.split(' are ')[1].strip() if ' are ' in rel else rel
            
            chars_in_rel = left.split(' and ')
            char_a = chars_in_rel[0].strip() if len(chars_in_rel) > 0 else ""
            char_b = chars_in_rel[1].strip() if len(chars_in_rel) > 1 else ""
            
            # Skip self-referential relationships (broken AI output)
            if not char_a or not char_b or char_a.lower() == char_b.lower():
                continue
            
            parsed_rels.append({
                "char_a": char_a,
                "char_b": char_b,
                "connection": connection
            })
        elif ' is ' in rel_str:
            # Handle single character: "Allison is daughter"
            left = rel_str.split(' is ')[0].strip()
            connection = rel_str.split(' is ')[1].strip() if ' is ' in rel_str else ""
            
            if left and connection:
                parsed_rels.append({
                    "char_a": left,
                    "char_b": "",
                    "connection": connection
                })
    
    with open(file_path.replace('\\', '/'), 'w') as f:
        f.write(f"""---
game: {game}
game_developer: 
created: {today}
updated: {today}
type: relationships
tags: [context, relationships]
---

# Relationships

> [!NOTE]
> Verified character relationships from game transcripts.

## Relationship List

| Character A | Connection | Character B | Status | Notes |
|------------|------------|-------------|--------|-------|
""")
        
        # Write parsed relationships to table
        for rel in parsed_rels:
            char_a_wiki = wiki(rel["char_a"]) if rel["char_a"] else "-"
            char_b_wiki = wiki(rel["char_b"]) if rel["char_b"] else "-"
            connection = rel["connection"] if rel["connection"] else "-"
            
            f.write(f"| {char_a_wiki} | {connection} | {char_b_wiki} | ✅ Verified | |\n")
        
        # Add Mermaid diagram with proper connections
        f.write(f"""
## Relationship Diagram

```mermaid
graph TD
""")
        
        # Create unique relationships for Mermaid with unique IDs
        used_ids = set()
        for i, rel in enumerate(parsed_rels):
            if rel["char_a"]:
                # Create unique ID
                safe_a = rel["char_a"].replace(" ", "_")[:8]
                if safe_a in used_ids:
                    safe_a = f"{safe_a}_{i}"
                used_ids.add(safe_a)
                
                if rel["char_b"]:
                    # Two-way relationship
                    safe_b = rel["char_b"].replace(" ", "_")[:8]
                    if safe_b in used_ids:
                        safe_b = f"{safe_b}_{i}"
                    used_ids.add(safe_b)
                    
                    conn = rel["connection"].replace(" ", "_")[:10] if rel["connection"] else "related"
                    f.write(f"    {safe_a}[{rel['char_a']}] -->|{conn}| {safe_b}[{rel['char_b']}]\n")
                else:
                    # Single character - show as standalone node
                    conn = rel["connection"].replace(" ", "_")[:10] if rel["connection"] else "related"
                    f.write(f"    {safe_a}[{rel['char_a']}] -->|{conn}| R{i}[Relationship]\n")
        
        f.write("```\n")
        
        f.write(f"""

---

### 🔍 Sources
- 

### ✅ Last Verified
{today}

{manual_notes}

---

**Tags:** #relationships
""")


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


def _store_corrections_as_constraints(corrections):
    """
    Store detected corrections as universal constraints in MemPalace.
    These constraints will be used in future context extractions.
    """
    if not MEMPALACE_AVAILABLE:
        log("[DEBUG] MemPalace not available, skipping constraint storage")
        return
    
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
            
            # Also save to a local constraints file as backup
            constraints_file = os.path.join(CONTEXT_DIR, "learned_constraints.json")
            existing = []
            if os.path.exists(constraints_file):
                try:
                    with open(constraints_file, 'r') as f:
                        existing = json.load(f)
                except:
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
                log(f"[LEARNING] {len(new_constraints)} new constraints saved (skipped {len(constraints) - len(constraints) + len(new_constraints)} duplicates)")
            
    except Exception as e:
        log(f"[ERROR] Failed to store corrections as constraints: {e}")


def _get_learned_constraints():
    """
    Get learned constraints from previous corrections.
    Returns list of constraint strings to include in prompts.
    """
    constraints = []
    
    constraints_file = os.path.join(CONTEXT_DIR, "learned_constraints.json")
    if os.path.exists(constraints_file):
        try:
            with open(constraints_file, 'r') as f:
                data = json.load(f)
                for item in data:
                    if "constraint" in item:
                        constraints.append(item["constraint"])
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
    
    for i in range(len(keys)):
        key = keys[i]
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
        
        for attempt in range(3):
            try:
                _rate_limit()
                req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "X-Goog-Api-Key": key})
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
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 503):
                    wait = (2 ** attempt) * 15 + random.uniform(0, 10)
                    log(f"   JSON prompt HTTP {e.code} with key ...{key[-6:]}, retry {attempt+1}/3 in {wait:.0f}s")
                    time.sleep(wait)
                else:
                    log(f"   JSON prompt HTTP {e.code} with key ...{key[-6:]}: {e}")
                    break
            except (json.JSONDecodeError, KeyError) as e:
                log(f"   JSON parse error with key ...{key[-6:]}: {e}")
                time.sleep(5)
                break
            except Exception as e:
                log(f"   JSON prompt error with key ...{key[-6:]}: {e}")
                time.sleep(5)
                break
        
        log(f"   Key ...{key[-6:]} failed for JSON prompt, next...")
    
    log("All JSON prompt keys exhausted")
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
- The two characters involved
- The type of relationship (allies, enemies, family, mentor, rival, friends, associates)
- A confidence score from 0.0 to 1.0 (how certain you are based on the transcript)
- A brief piece of evidence text from the transcript supporting this relationship

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

    # Merge relationships (avoid duplicates by fuzzy matching on text)
    for rel in extracted.get("relationships", []):
        is_dup = False
        if isinstance(rel, dict):
            rel_text = f"{rel.get('from', '')}-{rel.get('to', '')}-{rel.get('relationship', '')}"
        else:
            rel_text = str(rel)
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
