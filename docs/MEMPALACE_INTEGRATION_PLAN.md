# MemPalace Integration Implementation Plan

**ShortsForge** — AI-Powered YouTube Shorts Pipeline  
**Integration:** MemPalace (Local AI Memory System)  
**Date:** 2026-04-09  
**Status:** Plan (Not Yet Implemented)

---

## 1. Executive Summary

### Purpose
Integrate **MemPalace** (local AI memory system with 96.6% LongMemEval recall) into ShortsForge to provide persistent game-specific memory across pipeline runs.

### Goals
1. **Persistent Memory** — Character, relationship, and location data persists across all runs (pipeline + Content Studio)
2. **Dynamic Game Focus** — System uses only the game set via `GAME_TITLE` environment variable. **Each game gets its own MemPalace wing**, ensuring Tell Me Why memory is completely isolated from other games. No cross-contamination.
3. **Quality Tracking** — Remember which prompts generate best scripts per game
4. **Coexist with Manual Editing** — Preserve ability to edit context via Obsidian/markdown

### Non-Goals
- No hardcoded cross-game blocking (system dynamically uses whatever game is set)
- MCP server not included in initial implementation
- Does NOT replace existing `content_studio/context/*.md` system — complements it

---

## 2. Architecture Overview

### Current vs. Proposed

#### Current System (Without MemPalace)
```
Video → Transcript → Context Extraction (per-run) → Markdown Files → Script Generation
         ↓
    Context lost after each run
```

#### Proposed System (With MemPalace)
```
Video → Transcript → Context Extraction
         ↓                        ↓
   MemPalace Memory          Markdown Files
   (Semantic Search)        (Manual Control)
         ↓                        ↓
   Script Generation ←←←←←←←←←←←←←←←←←
```

### Data Flow Diagram
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PIPELINE RUN                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Phase 1: Download                                                          │
│     ↓                                                                        │
│  Phase 2: Transcribe                                                        │
│     ↓                                                                        │
│     ├→ mine_transcript() ──→ MemPalace (ChromaDB)                           │
│     │     • Extract entities: characters, locations                         │
│     │     • Store relationships in Knowledge Graph (SQLite)                 │
│     │     • Classify into rooms                                             │
│     ↓                                                                        │
│  Phase 3: Generate Scripts                                                  │
│     ↓                                                                        │
│     ├→ get_game_memory(GAME_TITLE)                                         │
│     │     • Retrieve character list                                          │
│     │     • Retrieve relationship facts                                     │
│     │     • Get forbidden characters list                                   │
│     ↓                                                                        │
│     ├→ Inject into context for prompt                                       │
│     ↓                                                                        │
│     ├→ Generate script                                                      │
│     ↓                                                                        │
│     ├→ validate (cross-reference memory)                                    │
│     ↓                                                                        │
│     ├→ add_quality_metric() ──→ Log script quality                           │
│     ↓                                                                        │
│  Phase 4: Generate Clips                                                   │
│  Phase 5: Generate TTS                                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Directory Structure

### New Files to Create

```
/home/alph4r1us/ShortsForge/
├── game_data/
│   └── mempalace/
│       ├── __init__.py
│       ├── mempalace_manager.py      # Main wrapper class
│       ├── config.py                 # Configuration
│       └── wings/                    # Game-specific configurations
│           └── tell_me_why.json      # Tell Me Why wing config
├── memory/                           # MemPalace data (ChromaDB + SQLite)
│   ├── chroma.db
│   ├── knowledge_graph.db
│   └── config.json
└── docs/
    └── MEMPALACE_INTEGRATION.md       # This document
```

### Existing Files Modified

| File | Changes |
|------|---------|
| `workflows/shortsforge.py` | Add MemPalace calls at 3 integration points |
| `content_studio/context/*.md` | No changes — continues working as before |

---

## 4. Implementation Phases

### Phase 1: Setup (Estimated: 30 minutes)

#### Tasks
1. **Install MemPalace**
   ```bash
   pip3 install mempalace
   ```

2. **Create memory directory**
   ```bash
   mkdir -p /home/alph4r1us/ShortsForge/memory
   ```

3. **Initialize MemPalace**
   ```bash
   cd /home/alph4r1us/ShortsForge
   mempalace init memory --name ShortsForge
   ```

4. **Create Tell Me Why wing**
   ```bash
   mempalace init memory --wing tell_me_why --type project
   ```

#### Deliverables
- MemPalace installed
- `memory/` directory created and initialized
- Tell Me Why wing configured
- **Security/Permissions**: Ensure the user running the pipeline has read/write access to `/home/alph4r1us/ShortsForge/memory/` directory

---

### Phase 2: Wrapper Module (Estimated: 1 hour)

#### File: `game_data/mempalace/mempalace_manager.py`

```python
class MemPalaceManager:
    """Wrapper for MemPalace operations in ShortsForge"""
    
    def __init__(self, palace_path: str = None):
        """Initialize with memory path"""
    
    def mine_transcript(self, json_file: str, game_title: str):
        """Mine transcript after Phase 2 completes"""
    
    def get_game_memory(self, game_title: str) -> dict:
        """Retrieve all memory for a game"""
    
    def get_character_list(self, game_title: str) -> list:
        """Get verified character names for game"""
    
    def get_relationships(self, game_title: str) -> list:
        """Get relationship facts: (character, relationship, target)"""
    
    def get_forbidden_characters(self, game_title: str) -> list:
        """Get characters to avoid (game-specific)"""
    
    def check_script_characters(self, script_text: str, game_title: str) -> dict:
        """Validate script against memory"""
    
    def add_quality_metric(self, game_title: str, metric: dict):
        """Log script generation quality"""
    
    def get_best_prompts(self, game_title: str, top_n: int = 5) -> list:
        """Get historically best prompts for game"""
    
    def get_entity(self, entity_name: str, game_title: str = None) -> list:
        """Query knowledge graph for entity"""
    
    def invalidate_fact(self, entity: str, relationship: str, target: str):
        """Mark a fact as no longer valid"""
```

#### Methods Detail

**mine_transcript(json_file, game_title)**
- Reads transcript JSON
- Extracts: characters, locations, key terms
- Mines to MemPalace via `mempalace mine` or direct API
- Classifies into rooms: `characters`, `locations`, `relationships`, `plot_points`
- Stores in knowledge graph

**get_game_memory(game_title)**
- Returns dict with:
  - `characters`: List of verified characters
  - `relationships`: List of relationship facts
  - `locations`: List of locations
  - `forbidden`: Game-specific forbidden list (if any)
  - `recent_sessions`: Last N scripts generated

**check_script_characters(script_text, game_title)**
- Parses script for character names
- Cross-references with memory
- Returns: `{valid: [], invalid: [], warnings: []}`

---

### Phase 3: Pipeline Integration (Estimated: 1 hour)

#### Integration Point 1: After Transcription (Line ~2521)

**Location:** `workflows/shortsforge.py`, function `run_pipeline()`

**Current code (around line 2600):**
```python
if transcript_text:
    game_title = env("GAME_TITLE", "Unknown Game")
    extracted = _cs_extract_context_from_transcript(transcript_text[:10000], game_title)
    if extracted:
        transcript_name = os.path.basename(json_file)
        _cs_update_context(extracted, transcript_name)
        log(f"Context extracted: {len(extracted.get('characters', []))} characters")
```

**Add after:**
```python
# NEW: Also mine to MemPalace for persistent memory
if env("MEMORY_ENABLED", "true").lower() != "true":
    log("MemPalace: Disabled via MEMORY_ENABLED=false, skipping")
else:
    try:
        mempalace_manager.mine_transcript(json_file, game_title)
        log(f"MemPalace: Mined transcript for {game_title}")
    except Exception as e:
        log(f"MemPalace: Mining failed - {e}, falling back to markdown-only")
```

#### Integration Point 2: Before Script Generation (Line ~2035)

**Location:** `workflows/shortsforge.py`, function `phase_scripts()`

**Current code (around line 2036):**
```python
# Phase 3: Optimize context relevance for this specific transcript
relevant_ctx = score_context_relevance(ctx, transcript_text, max_items=8)
```

**Add before:**
```python
# NEW: Inject MemPalace memory into context
game_title = env("GAME_TITLE", "")

# Validate game_title exists in MemPalace before attempting recall
if not game_title:
    log("MemPalace: No GAME_TITLE set, skipping memory injection")
else:
    try:
        game_memory = mempalace_manager.get_game_memory(game_title)
        if game_memory and game_memory.get('characters'):
            # Add verified characters to context
            for char in game_memory['characters']:
                if char not in ctx['characters']:
                    ctx['characters'].append(char)
            
            # Add relationships for reference
            ctx['_mempalace_relationships'] = game_memory.get('relationships', [])
            
            log(f"MemPalace: Injected {len(game_memory.get('characters', []))} characters from {game_title} memory")
        else:
            log(f"MemPalace: No existing memory for {game_title}, starting fresh")
    except Exception as e:
        log(f"MemPalace: Memory injection failed - {e}, using markdown-only context")
```

#### Integration Point 3: After Script Validation (Line ~2074)

**Location:** `workflows/shortsforge.py`, function `phase_scripts()`

**Current code (around line 2074):**
```python
# Log quality metrics (Phase 5)
if best_script and best_metadata.get("source") != "raw_transcript":
    log_generation_metrics(best_script, best_metadata, scores[0] if scores else {})
```

**Add after:**
```python
# NEW: Also log to MemPalace for quality tracking
if env("MEMORY_ENABLED", "true").lower() != "true":
    log("MemPalace: Disabled, skipping quality logging")
else:
    try:
        metric = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'hour': i,
            'source': best_metadata.get('source'),
            'model': best_metadata.get('model'),
            'word_count': len(best_script.split()),
            'factuality': scores[0].get('factuality', {}).get('score', 0) if scores else 0,
            'engagement': scores[0].get('engagement', {}).get('overall', 0) if scores else 0,
            'variant': variant_key,
            'perspective': perspective
        }
        mempalace_manager.add_quality_metric(game_title, metric)
        log(f"MemPalace: Logged quality metric for script {i}")
    except Exception as e:
        log(f"MemPalace: Quality logging failed - {e}")
```

#### Performance Consideration
> **Note:** Transcript mining adds time to Phase 2. Initial benchmark estimates:
> - 1-hour video transcript: ~30-60 seconds additional
> - 2-hour video transcript: ~60-120 seconds additional
>
> If performance becomes an issue, consider:
> - Async mining (non-blocking after transcript is saved)
> - Batching multiple transcripts
> - Caching recent entity extractions

---

### Phase 4: Quality Tracking Features (Estimated: 30 minutes)

#### Features to Implement

1. **Script History** — Store all generated scripts with metadata
2. **Best Prompt Recall** — Find which variant/perspective combinations work best
3. **Failure Pattern Detection** — Track what causes low factuality/engagement

#### Implementation
- Use MemPalace's `hall_facts` for quality metrics
- Store in `quality_metrics` room per game wing

---

## 5. Configuration

### File: `game_data/mempalace/config.py`

```python
MEMPALACE_CONFIG = {
    'palace_path': '/home/alph4r1us/ShortsForge/memory',
    'default_wing': 'tell_me_why',
    'auto_mine': True,           # Automatically mine transcripts
    'auto_recall': True,         # Automatically recall before generation
    'log_quality': True,         # Log quality metrics
    'max_memory_chars': 2000,   # Max characters to include in context
    'rooms': {
        'characters': 'Character names from game',
        'locations': 'Places in game world',
        'relationships': 'Character relationship facts',
        'plot_points': 'Key story elements',
        'quality_metrics': 'Script generation quality data'
    }
}
```

### Environment Variable Support
- `MEMORY_ENABLED=true/false` — Toggle MemPalace integration
- `MEMORY_PATH` — Override default memory directory

---

## 6. Coexistence with Existing System

### How It Works Together

| Aspect | Markdown System | MemPalace |
|--------|-----------------|-----------|
| **Storage** | `content_studio/context/*.md` | `memory/` (ChromaDB + SQLite) |
| **Manual Edit** | ✅ Yes — edit directly | ⚠️ Not directly — via API |
| **Auto-Update** | From transcript extraction | From transcript mining |
| **Query Method** | File-based loading | Semantic search |
| **Persistence** | Files persist, but not semantic | Semantic, searchable |

### Key Points
1. **Both systems active** — MemPalace does NOT disable markdown files
2. **Markdown still primary** — Current script generation reads from markdown
3. **MemPalace enhances** — Provides semantic recall and quality tracking
4. **You can disable** — Set `MEMORY_ENABLED=false` to skip MemPalace entirely

---

## 7. Rollback Plan

If MemPalace integration causes issues:

1. **Disable via config**
   ```bash
   # In .env or via command
   MEMORY_ENABLED=false
   ```

2. **What happens**
   - MemPalace calls are skipped
   - Falls back to existing markdown-based context system
   - No data loss — MemPalace data remains in `memory/` directory

3. **Re-enable anytime**
   ```bash
   MEMORY_ENABLED=true
   ```

---

## 8. Testing Plan

### Phase 1: Unit Tests

| Test | Description | Pass Criteria |
|------|-------------|----------------|
| `test_mine_transcript` | Verify transcript mining works | Transcript JSON processed without errors, entities extracted |
| `test_get_game_memory` | Verify memory retrieval | Returns dict with characters, relationships, locations |
| `test_check_character` | Verify character validation | Returns valid/invalid/warnings lists |

### Phase 2: Integration Tests

| Test | Description | Pass Criteria |
|------|-------------|----------------|
| `test_mine_then_recall` | Mine a transcript, then recall — verify data persists | Mined character appears in recall with 95%+ accuracy |
| `test_quality_logging` | Generate script, verify quality logged | Metric appears in MemPalace with correct fields |
| `test_wing_isolation` | Verify Tell Me Why data doesn't leak to other game | Searching other game returns no Tell Me Why characters |

### Phase 3: End-to-End Tests

| Test | Description | Pass Criteria |
|------|-------------|----------------|
| `test_full_pipeline` | Run pipeline with MemPalace enabled | All phases complete, memory populated |
| `test_persistence` | Run pipeline twice — verify memory persists between runs | Second run sees characters from first run |
| `test_graceful_degradation` | Run with MEMORY_ENABLED=false | Pipeline runs without MemPalace, uses markdown-only |

---

## 9. Implementation Order

```
Week 1: Setup + Wrapper Module
├── Day 1: Install MemPalace, create directories
├── Day 2: Create mempalace_manager.py
├── Day 3: Test wrapper functions in isolation

Week 2: Pipeline Integration  
├── Day 4: Integration Point 1 (after transcription)
├── Day 5: Integration Point 2 (before generation)
├── Day 6: Integration Point 3 (quality logging)

Week 3: Testing + Polish
├── Day 7: Run full pipeline with MemPalace
├── Day 8: Verify persistence between runs
└── Day 9: Document any issues, finalize
```

---

## 10. Estimated Time

| Phase | Time |
|-------|------|
| Phase 1: Setup | 30 minutes |
| Phase 2: Wrapper Module | 1 hour |
| Phase 3: Pipeline Integration | 1 hour |
| Phase 4: Quality Tracking | 30 minutes |
| **Total** | **~3 hours** |

---

## 11. Open Questions (Resolved)

The following questions have been addressed in this updated version:

1. **Where should this document live?**
   - **Decision**: `docs/MEMPALACE_INTEGRATION_PLAN.md` (implementation-focused, fits alongside other docs)

2. **Should we track Content Studio separately?**
   - **Decision**: Same memory for pipeline + Content Studio initially. Can split later if needed.

3. **Initial character data?**
   - **Decision**: Start fresh for Tell Me Why. The existing `game_data/tell_me_why/characters.json` is used only as reference for creating the initial wing, but MemPalace builds its own index from actual transcripts. This ensures accuracy — we trust what the AI extracts from real transcripts over static JSON.

---

## 12. Appendix: MemPalace Commands Reference

```bash
# Setup
mempalace init <path>                       # Initialize palace
mempalace init <path> --wing <name>         # Create wing

# Mining
mempalace mine <dir>                        # Mine files
mempalace mine <dir> --mode convos          # Mine conversations

# Search
mempalace search "query"                    # Search all
mempalace search "query" --wing <name>       # Search wing

# Status
mempalace status                            # Palace overview

# Split (for large transcripts)
mempalace split <dir>                      # Split into sessions
```

---

**Document Version:** 1.0  
**Created:** 2026-04-09  
**Status:** Ready for Review