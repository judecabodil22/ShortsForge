# Cogitator Changelog

All notable changes to this project are documented here.

---

## 2.5.1 (2026-08-02)

### Bug Fixes

- **phase_assemble.py:417** — Fixed shifted_srt=None: SRT path was overwritten to None causing ffmpeg concat to fail
- **phase_assemble.py:432** — Fixed apostrophes in file paths causing ffmpeg concat to fail (escaped with single quotes)
- **phase_assemble.py:390** — Fixed fontsdir check using `os.path.exists` instead of `os.path.isdir` (returned True for files)
- **phase_assemble.py:426** — Fixed force_style single quotes not escaped for ffmpeg
- **backend/main.py:92** — Fixed `sanitize_input` stripping ALL `/` characters, breaking URLs entirely
- **phase_tts.py:315, phase_tts_kokoro.py:234** — Fixed `compute_type="int8"` incompatible with CUDA (changed to "float16")
- **phase_tts.py:130-139** — Fixed Edge TTS outputting MP3 by default (now converts to WAV via ffmpeg)
- **phase_tts.py:228, phase_tts_kokoro.py:151** — Fixed `set_progress(5, ...)` should be `set_progress(6, ...)` for TTS phase
- **phase_tts.py:285, phase_tts_kokoro.py:195** — Fixed `import performance_database as pdb` → `import workflows.performance_database as pdb`
- **phase_tts_kokoro.py:54-65** — Fixed Kokoro pipeline singleton changed to dict keyed by language code
- **context_extractor.py:103** — Fixed missing `[:50000]` truncation in transcript reading
- **frontend/LearningDashboard.tsx:106** — Fixed recharts `PieChart` used as icon instead of lucide-react icon
- **backend/main.py:1166-1177** — Fixed A/B test endpoints using query params instead of request body, added auth
- **frontend/Settings.tsx:95-97** — Fixed backend validation errors returned as HTTP 200 with `{"status":"error"}` in body
- **hardware_detect.py** — Fixed Intel QSV typo: `'- look_ahead'` → `'-look_ahead'`
- **context_extractor.py:19** — Removed dead import `merge_context_dicts`

### Documentation

- Removed IMPROVEMENT_PLAN.md
- Updated SECURITY.md: removed Telegram references, updated supported versions
- Updated docs/CONFIGURATION.md: replaced Telegram commands with CLI commands

---

## 2.5.0 (2026-08-02)

### Bug Fixes

- **phase_assemble.py:417** — Fixed shifted_srt=None: SRT path was overwritten to None causing ffmpeg concat to fail
- **phase_assemble.py:432** — Fixed apostrophes in file paths causing ffmpeg concat to fail (escaped with single quotes)
- **phase_assemble.py:390** — Fixed fontsdir check using `os.path.exists` instead of `os.path.isdir` (returned True for files)
- **phase_assemble.py:426** — Fixed force_style single quotes not escaped for ffmpeg
- **backend/main.py:92** — Fixed `sanitize_input` stripping ALL `/` characters, breaking URLs entirely
- **phase_tts.py:315, phase_tts_kokoro.py:234** — Fixed `compute_type="int8"` incompatible with CUDA (changed to "float16")
- **phase_tts.py:130-139** — Fixed Edge TTS outputting MP3 by default (now converts to WAV via ffmpeg)
- **phase_tts.py:228, phase_tts_kokoro.py:151** — Fixed `set_progress(5, ...)` should be `set_progress(6, ...)` for TTS phase
- **phase_tts.py:285, phase_tts_kokoro.py:195** — Fixed `import performance_database as pdb` → `import workflows.performance_database as pdb`
- **phase_tts_kokoro.py:54-65** — Fixed Kokoro pipeline singleton changed to dict keyed by language code
- **context_extractor.py:103** — Fixed missing `[:50000]` truncation in transcript reading
- **frontend/LearningDashboard.tsx:106** — Fixed recharts `PieChart` used as icon instead of lucide-react icon
- **backend/main.py:1166-1177** — Fixed A/B test endpoints using query params instead of request body, added auth
- **frontend/Settings.tsx:95-97** — Fixed backend validation errors returned as HTTP 200 with `{"status":"error"}` in body
- **hardware_detect.py** — Fixed Intel QSV typo: `'- look_ahead'` → `'-look_ahead'`
- **context_extractor.py:19** — Removed dead import `merge_context_dicts`

### Hardware-Accelerated Encoding
- **Hardware detection module** (`workflows/hardware_detect.py`): New module detects CPU cores, RAM, NVIDIA NVENC, VA-API, Intel QSV for automatic FFmpeg encoding optimization
- **VA-API encoding** (`phase_assemble.py`): `h264_vaapi` with `format=nv12,hwupload` embedded in complex filtergraph (fixed filtergraph conflict)
- **NVENC encoding**: `h264_nvenc` with adaptive preset based on VRAM
- **Intel QSV encoding**: `h264_qsv` with look-ahead
- **CPU fallback**: `libx264` with adaptive preset based on core count
- **Whisper GPU acceleration**: `get_whisper_device()` detects CUDA for faster-whisper

### Voice Customization
- **TTS emotion styles** (`phase_tts.py`): 8 emotions (happy, sad, excited, calm, angry, fearful, whisper) via `TTS_EMOTION` env var
- **TTS speed control**: Configurable 0.5x–2.0x via `TTS_SPEED` env var
- Applied to both Gemini and Kokoro TTS providers

### Learning Dashboard
- **LearningDashboard page** (`frontend/src/pages/LearningDashboard.tsx`): Insights, content type effectiveness, A/B test tracking
- **A/B test framework** (`performance_database.py`): `ab_tests` table with create/record/query/history functions
- **Graph search/stats endpoints**: `/api/context/{game}/graph/search` and `/api/context/{game}/graph/stats`
- **Backend learning endpoints**: `/api/learning/dashboard`, `/api/learning/ab-test`, `/api/learning/ab-tests`

### Pipeline Resilience
- **Output existence check** (`phase_tts.py`, `phase_tts_kokoro.py`): Existing TTS WAV files counted toward `tts_generated` — no false "No TTS generated" failures
- **Assembly output skip** (`phase_assemble.py`): Existing output MPs4s are detected and skipped with proper counter increment
- **Gemini JSON sanitization** (`cogitator.py`, `context_extractor.py`): Strips markdown code fences and whitespace from API responses before parsing

### Web UI
- **Command Palette** (Cmd+K): Global search/navigation across all pages
- **WebSocket live updates**: Real-time pipeline status, logs, metrics
- **Config validation**: Backend validates all config fields (range, type, enum); frontend displays errors
- **Voice tab in Settings**: Emotion dropdown and speed slider

### Documentation
- All 10 documentation files updated for Telegram removal and new features
- Removed IMPROVEMENT_PLAN.md

---

## 2.4.0 (2026-07-20)

### TTS Overhaul
- **Kokoro TTS Provider** (`workflows/pipeline/phase_tts_kokoro.py`): 18 mapped Gemini→Kokoro voices, zero-cost CPU-based, fully offline after first model download
- **Config-driven TTS dispatch** (`workflows/pipeline/phase_tts.py`): `TTS_PROVIDER=kokoro|edge|gemini` env var selects backend with Gemini fallback
- **Edge TTS backend**: Free Microsoft cloud TTS via `edge-tts` library

### Scene Detection
- **PySceneDetect integration** (`workflows/audio_analysis.py`): Content-aware scene boundary detection + `rank_scenes_by_action()` motion scoring via ffmpeg + uniform segment fallback

### Highlight Ranking
- **LLM Highlight Ranker** (integrated in `workflows/cogitator.py`): Sends transcript segments to Groq (Llama 3.3 70B) or Gemini for virality scoring (0-100), returns sorted top segments

### Analytics Feedback Loop
- **YouTube Analytics sync** (`workflows/learning_engine.py`): `sync_and_train_from_youtube()` fetches YouTube metrics + retrains XGBoost model
- **Optimal param derivation**: `update_optimal_params_from_youtube()` derives optimal duration, voices, and styles from performance data
- **Post-pipeline auto-sync**: `pipeline_runner.py` auto-calls `sync_and_train_from_youtube()` after each pipeline run

### Game Lore Fetch
- **Game Lore Phase** (integrated in `workflows/cogitator.py`): Parallel Gemini+Groq dispatch asking for plot_summary, characters, locations, factions, key_events, lore_terms
- **Phase 3a integration**: `cogitator.py` calls lore extraction before transcript processing
- **`[GAME LORE]` prompt block**: Lore rendered as PLOT SUMMARY, FACTIONS, KEY EVENTS, LORE TERMS in script generation prompts (`prompts/base.j2` + f-string fallback)

### Frontend Pipeline Progress
- **4 visualization modules**: CogitatorArray (SVG gears), Construction (CSS layers), PhaseTimeline (timeline + live logs), DataCanvas (CSS grid fill)
- **Random selection per run**: Orchestrator (`index.tsx`) picks a random viz per pipeline run via `useRef`
- **Shuffle button**: Manual re-roll of active visualization
- **Dashboard integration**: `Dashboard.tsx` now uses `<PipelineProgress>` component replacing inline progress bar

### Import Chain Fixes
- **Lazy imports**: `pipeline/__init__.py` uses `__getattr__`; `pipeline_runner.py`, `phase_tts.py` use function-level lazy imports to avoid import-chain failures
- **`score_context_relevance()` / `summarize_context()`**: Preserve `lore` field through all context processing

### Word-Level Subtitle Timing
- **Faster-Whisper word timestamps** (`phase_tts.py`, `phase_tts_kokoro.py`): `word_timestamps=True` enables per-word timing
- **`_words.json` companion files**: Stores `{word, start, end}` for each word
- **Fuzzy word alignment** (`phase_assemble.py`): Uses `difflib.SequenceMatcher` for TTS-script mismatches
- **Subtitle readability validation** (`srt_utils.py`): `validate_srt_readability()` with 42-char line splitting

### Telegram Removal
- Removed Telegram bot dependencies and commands
- Removed `/api/system/restart-listener` endpoint
- Replaced `tg_send`/`tg_send_menu`/`tg_answer_callback` with logging stubs
- Removed `listen`/`stop` CLI commands

### Quality Fixes
- Added missing `true_story` variant to `SCRIPT_VARIANTS` and `HOOK_ARCHETYPES`
- Fixed `drama_score` → `score` key mismatch in clip selection
- Round-robin index overflow now wraps via modulo
- Implemented `clip_pacing` via `CLIP_PACING` env var
- BGM ducking now unducks after TTS ends
- Removed duplicate `_detect_laughter` function
- Updated Content Studio prompts to include all 15 variants
- Fixed `store_learning()` to use running average for `impact_score`
- TTS learning now keyed on `(voice, style, content_type)`

### Learning System Improvements
- Relative performance tracking: compare videos against channel baseline
- Content type effectiveness analysis
- Learning insights injected into script prompts
- Constraint deduplication in `learned_constraints.json`
- False-positive correction detection fixed
- Constraint pruning for entries older than 30 days

### Web UI Enhancements
- **Command Palette** (Cmd+K): Global search/navigation across all pages
- **Real-time WebSocket**: Live pipeline status, logs, metrics
- **Connection indicator**: Live/Offline status badge

### API Resilience
- **Retry logic**: Exponential backoff for Groq and Gemini API calls
- Handles network errors, rate limits, server errors

### Context/Memory Fixes
- Constraint duplication fixed — deduplicates before extending
- False-positive corrections fixed — only flags removals if new context has data
- Relationship dedup improved — cross-entity resolution and reverse relationship detection

---

## 2.3.0 (2026-06-22)

### Security
- **CRITICAL**: Fixed unauthenticated path traversal in `serve_frontend` — resolved paths are now validated against `FRONTEND_DIST`
- **CRITICAL**: Fixed path traversal via game name in context endpoints (sanitize_input now strips `..`, `/`, `\`)
- **CRITICAL**: Fixed `clear_mempalace_for_game` — `shutil.rmtree` with unsanitized game name could delete arbitrary directories
- **API key URL leak**: All Gemini API key URLs migrated from `?key=` query param to `X-Goog-Api-Key` header across all call sites
- **API key rotation**: Keychain-backed rotation with `GEMINI_KEY_INDEX` tracking
- **In-memory rate limiting**: Replaced file-based rate limiting (race condition / /tmp fragility)
- **Bare except fixes**: `except:` replaced with specific exception types across all modules

### Thread Safety
- Added `_rr_lock` to all round_robin.py functions protecting mutable shared globals
- Added `_pipeline_globals_lock` in cogitator.py (was defined but never used)
- Added `_pipeline_lock` around pipeline_process reads/writes in backend/main.py
- Fixed `PENDING_CONTEXT` split-brain (bot.py redefined the imported dict)
- Double-checked locking singleton for virality predictor
- File locking for all context_manager.py load/save/merge operations

### Bug Fixes
- **AnimatedCounter.tsx**: Stale closure in `useTransform` — `format` prop always used initial render's value
- **Scripts.tsx**: Runtime TypeError when `video_name` or `content_type` is null (`?.toLowerCase().includes()`)
- **round_robin.py**: All global state read/writes now protected by lock
- **backends/main.py**: Relationship import parsing (extracted from/to/label), malformed entity filter, non-recursive glob → recursive
- **context_manager_v2.py**: `is_first_run` file descriptor leak, `get_history` now returns most-recent-first, atomic writes via tempfile+os.replace
- **phase_tts.py**: Fixed double SQLite connection (reused `conn` + try/finally)
- **pyproject.toml**: Fixed invalid `build-backend`
- **pipeline_runner.py**: Added `_pipeline_globals_lock` for pipeline globals
- **performance_database.py**: Fixed indentation error in auto_match_and_fetch, SQL connection leak (try/finally)

### Context Extraction
- Entity provenance tracking (transcript_mentions, first_seen_transcript, admission_threshold)
- Admission gate: new entities need ≥2 transcript mentions before promotion
- Conflict detection: validates generated scripts against known entities

### Script Quality
- Story arc detection: 4 arc types (hook_setup_payload_closer, mystery_reveal, problem_solution, setup_twist)
- Hook strength scoring + arc confidence
- Retention re-ranking (compares current features against historical performers)
- Post-generation word count enforcement (trims to 280 words if >300)
- Title diversity tracking (rolling set of last 10 titles)
- Retry on low factuality (< 0.5) with stricter instruction
- Fixed contradictory word count targets in variant .j2 templates (Jinja2 `{% set instruction %}` was overriding Python kwarg)

### Video Clipping
- Frame-accurate cutting with `{s:.3f}` float timestamps
- PySceneDetect integration for visual scene boundary detection
- Portrait 9:16 crop mode (PORTRAIT_CLIPS env var)
- Caption burn-in (BURN_CAPTIONS env var) via ffmpeg drawtext
- HEVC VAAPI auto-detection (hevc_vaapi/h264_vaapi for AMD GPUs)
- Audio normalization with loudnorm on CPU path
- Single-pass scene extraction (removed duplicate call)

### Pipeline & Workflow
- Removed Pipeline page from web UI (Layout.tsx navigation + App.tsx route)
- Graph.tsx: default showImplicitEdges=false, rAF animation loop switched from state to ref (no React re-renders)
- Consolidated all /tmp/ paths to ~/.cogitator/
- Failure storage threshold lowered from 0.5 to 0.7 engagement
- _is_known_entity returns False on empty list (stricter)
- get_groq_keys tries keychain first before .env

### Documentation
- Updated README.md with current feature set
- Updated .env.example with GROQ_API_KEY, PORTRAIT_CLIPS, BURN_CAPTIONS
- Updated install.sh Python version check (3.10→3.11)

---

## 2.2.0 — 2026-05-22
### Fixed
- **Frontend Blank Page**: Removed `AnimatePresence mode="wait"` causing race conditions in React Router — pages now consistently render on navigation
- **Graph Hidden-Games Filter**: `Graph.tsx` now clears and re-populates `nodesMap` from scratch instead of additive-only update, removing orphaned references to hidden game nodes
- **Graph Entity Name Collision**: `_register_graph_node()` uses first-registration-wins (character > location > term) — prevents "Night City" term from overwriting location node
- **Graph Placeholder Nodes**: Relationships referencing unregistered entities now auto-create placeholder nodes instead of silently dropping edges
- **Graph Franchise Merging**: `_build_single_game_graph()` merges child game context into franchise graphs — Tomb Raider Series went from 38→81 characters, 13→45 context edges
- **Co-occurrence Child Entities**: `analyze_transcript_cooccurrence()` loads entities from child games when resolving franchise keys — implicit edges went from 37→211
- **All Games Route**: Moved `/api/context/all/graph` before parameterized `/api/context/{game}/graph` to fix route capture
- **TTS Voice Style**: Fixed `_get_next_voice_style()` → `get_next_voice_style()` call in `cogitator.py:4425`
- **metrics_fetcher Import**: Added try/except fallback for `workflows.metrics_fetcher` in `performance_database.py:823`
- **Tracker Sync**: `get_recent_uploads()` no longer returns early before fetching duration stats; `get_all_videos_with_metrics()` uses correlated subquery instead of LEFT JOIN to eliminate duplicate metric rows
- **SQLite Concurrency**: Added `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000` for concurrent pipeline + API access
- **MemPalace**: `get_character_list()` now correctly parses room names from MemPalace output

### Added
- **Centralized Constants**: `workflows/constants.py` — single source for TTS voices (30), style options (10), `calculate_performance_score()`, `parse_duration()`, `calculate_readability()`, `calculate_hook_strength()`, `get_next_groq_key()`
- **Unified YouTube Sync**: `sync_youtube_metrics()` in `performance_database.py` replaces 3 duplicated implementations across `cogitator.py` and `backend/main.py`
- **Module Extraction**: Created `workflows/core/round_robin.py`, `workflows/core/pipeline_context.py`
- **WebSocket Log Streaming**: Background log tailer reads `/tmp/pipeline.log` and broadcasts over WebSocket to all connected clients
- **Graph Caching**: Function-level TTL caches for `get_weighted_tts_voices()` (5-min) and graph endpoints (60-sec with file-mtime invalidation)
- **Context v2 Facade**: Added v1-compatible API to `context_manager_v2.py` — `load_verified_context()`, `save_verified_context()`, `clear_verified_context()`, `compare_context_with_history()`, `format_context_for_confirmation()`, `is_first_run()`, `compute_and_save_implicit_relationships()`, `save_implicit_relationships()`
- **Missing Dependencies**: Completed `requirements.txt` with fastapi, uvicorn, slowapi, jinja2, requests, spacy, rapidfuzz, textblob
- **.gitignore**: Added Cursor IDE directory

### Changed
- **Frontend Production Build**: Backend serves `frontend/dist/` via `StaticFiles` with Vite dev server fallback for development
- **Phase Numbering**: Unified to 6 phases (Download, Transcribe, Context, Scripts, Clips, TTS) across `PHASE_LABELS` and `PHASE_MAP`
- **Context Callback Routing**: `handle_context_callback` moved to module top; context callbacks routed directly via `cb_id` instead of `handle_menu_callback`
- **`.env.example`**: Renamed from "Lambda Cut" to "Cogitator"; added `WHISPER_MODEL` option
- **All `docs/`**: Updated "lambda_cut" → "Cogitator" references
- **Pipeline Context**: Import fallback pattern (`try/except ImportError`) for all new modules to support both direct execution and package imports
- **`store_metrics()`**: Changed from insert-only to upsert to prevent stale metric rows on known videos
- **Frontend Metrics**: Deduplicates `videos?.videos` array by `youtube_id` and sorts by `created_at DESC`
- **`.gitignore`**: Rebranded from `Lambda Cut` to `Cogitator`

### Technical
- `backend/main.py`: Graph franchise logic (L1153-1260), co-occurrence child entity loading (L854-940), node registration guard (L1066-1083), placeholder node auto-creation (L1203-1232)
- `workflows/cogitator.py`: 215 lines removed — duplicated sync, context, and constants extracted to dedicated modules
- `workflows/performance_database.py`: Rewritten metrics sync, learning engine queries, and YouTube auto-match
- `workflows/constants.py`: 210 lines — new centralized constants module
- `workflows/core/round_robin.py`: 130 lines — extracted round-robin engine with `get_state()` helper
- `workflows/core/pipeline_context.py`: Shared pipeline state object with try/except imports
- `frontend/src/App.tsx`: Removed `AnimatePresence mode="wait"`, simplified per-route entrance animations
- `frontend/src/pages/Graph.tsx`: Rebuild `nodesMap` from scratch on filter (L231-233)

---

### Added
- **Graph Visual Themes**: 6 switchable visual themes for the knowledge graph
  - Star Chart (default): Classic gold/red 40k color scheme
  - Brain Neurons: Purple gradient circles with pulsing effects
  - Digital Circuits: Green circuit board squares with connection dots
  - Hologram: Cyan holographic style with scan line effects
  - Code Matrix: Terminal green with cursor blinking
  - World Map: Map pin style for location entities
- **Theme-Specific Physics**: Each theme has unique physics presets
  - Different link distance, charge strength, and velocity decay
- **Theme Persistence**: Selected theme saved to localStorage
- **Animated Effects**: Per-theme animations
  - Node pulse (brain), scan lines (hologram), cursor blink (code)
  - Link flow effects, flickering, neural pathway pulses
- **Persistent Co-occurrence Storage**: Implicit relationships stored in verified_context.json
  - Co-occurrence edges computed during transcript import
  - Stored persistently - deleting transcripts doesn't affect graph
  - Graph loads stored data first, only computes from transcripts if none stored

### Changed
- **Graph Data Flow**: Implicit edges now loaded from verified_context.json
  - Previously computed on-the-fly from transcripts (lost when deleted)
  - Now extracted during import and saved to JSON
- **Theme Dropdown**: Added to Graph Settings panel with visual theme buttons

### Technical
- context_manager.py: Added save_implicit_relationships(), load_implicit_relationships(), compute_and_save_implicit_relationships()
- backend/main.py: Updated get_graph_data() to use stored implicit relationships first
- cogitator.py: Auto-calls compute_and_save_implicit_relationships() after transcript import
- frontend Graph.tsx: Added visualTheme state, theme-specific rendering, animation loop
- graphSettings.ts: Added VisualTheme type, THEME_PHYSICS presets, THEME_OPTIONS

---

## 2.0.3 — 2026-05-19
### Added
- **Enhanced Node Details Panel**:
  - Connection and relationship count stats
  - Connected nodes list with icons and types
  - Aliases and tags display
  - Category badges
  - Scrollable lists for better overflow handling

### Changed
- **Modernized Color Palette**: Updated cyberpunk theme for better eye comfort
  - Softer neon colors (GitHub-inspired muted palette)
  - Removed harsh glow effects and scanlines
  - Darker, easier-to-read backgrounds
  - Subtle hover states instead of aggressive glows
  - Graph node colors updated to muted tones

---

## 2.0.2 — 2026-05-19
### Added
- **Graph Visual Settings Panel**: New settings panel accessible via gear icon
  - Link Distance (50-500): Control how far nodes are pulled together by edges
  - Link Force (0-2): Control edge pull force
  - Repel Force (-2000 to -50): Control node separation force
  - Collision Radius (1-150): Minimum distance between nodes
  - Center Force (0-1): How compact the graph is
  - Velocity Decay (0-1): Simulation smoothness
  - Reset to Default button
- **Hover-Based Label Visibility**: Node labels only appear on hover or when selected

### Changed
- **Knowledge Graph Visualization**:
  - Added direct entity-to-entity edges for relationships
  - Entities sharing a relationship are now directly connected
  - Relationship nodes made smaller to reduce visual clutter
  - Updated default settings for better node distribution
  - New toggle buttons for implicit and direct edge visibility
- **Graph Data Backend**: Added direct edges between entities

### Technical
- Frontend: Added zoom tracking state for label visibility
- Frontend: Added `zoomLevel` state and `onZoom` callback
- Graph settings applied via d3 force simulation

---

## 2.0.1 — 2026-05-17
### Security
- **API Key Authentication**: Added API key verification to sensitive endpoints
  - Protected endpoints: `/api/config`, `/api/system/cleanup`, `/api/context/import`, `/api/context/clear`, `/api/pipeline/download`
  - Auto-generated API key stored in `~/.cogitator/api_key`
  - Use `X-API-Key` header for authenticated requests
- **Rate Limiting**: Added rate limiting to prevent API abuse
  - Pipeline endpoints: 5/minute (run), 10/minute (stop)
  - Config/system endpoints: 2-5/minute
  - Metrics sync: 1/minute
- **Security Headers**: Added security middleware
  - X-Content-Type-Options: nosniff
  - X-Frame-Options: DENY
  - X-XSS-Protection: 1; mode=block
  - Strict-Transport-Security (HSTS)
  - Referrer-Policy
- **Input Sanitization**: Added input validation and path sanitization
  - Sanitize user inputs to prevent injection attacks
  - Validate URL schemes for download endpoint
  - Path traversal prevention
- **.gitignore**: Added security files to gitignore
  - `client_secret.json`
  - `.cogitator/youtube_oauth.json`
  - `.cogitator/web_settings.json`

### Added
- **FastAPI Backend** (`backend/`): New web API server
  - REST API endpoints for pipeline control
  - Metrics, scripts, learnings, context endpoints
  - Configuration management endpoints
  - System control endpoints (cleanup)
- **React Web Interface** (`frontend/`): New web UI
  - Cyberpunk-themed dashboard
  - Real-time pipeline status via WebSocket
  - Metrics visualization with charts
  - Context graph visualization
- **WebSocket Support**: Real-time updates for all connected clients
- **Performance Database**: Enhanced SQLite-based metrics storage
  - Video performance tracking
  - Script feature extraction
  - TTS learning data
  - Thompson sampling for content selection
- **Learning Engine**: ML-based virality prediction
  - Content type performance analysis
  - Feature extraction from scripts
  - 70/30 explore/exploit content selection
- **Context Manager V2**: Enhanced context system
  - Graph-based context visualization
  - Character, location, term, relationship tracking
  - Segment reference linking
- **Script Validation**: Enhanced script quality validation
  - Hook, body, call-to-action scoring
  - Content type pattern detection
- **SECURITY.md**: New security policy documentation

### Changed
- **CORS**: Tightened to specific localhost origins
- **API Responses**: Consistent JSON response format

### Technical
- Python dependencies updated with security packages (slowapi, python-dotenv)
- Frontend: React 18.2.0, Vite 5.1.0, TypeScript, Tailwind CSS, Radix UI, Zustand, Framer Motion, Recharts

---

## 2.0.1 — 2026-04-12
### Fixed
- **run_local CLI**: Added `-phase` argument support to run specific phases
- **Local pipeline processing**: Process videos directly from media/ without copying to streams/
- **UI Status display**: Now reads from /tmp/pipeline_status file for actual pipeline state
- **Progress bar**: Shows real-time phase progress based on status file

### Changed
- Phase buttons for local source now use `run_local` command instead of `run`

---

## 2.0.0 — 2026-04-12
### Added
- **Desktop Application (PyQt6)**: Full native desktop UI
  - Side-by-side layout: Buttons panel | Terminal status display
  - Real-time file counts and pipeline status
  - Dark theme matching KDE desktop
  - Run via `./cogitator --ui`
- **Local Recordings Support**: Process local video files
  - Videos from `~/Cogitator/recordings/` directory
  - Supported formats: mp4, mkv, avi, mov, webm
  - Source selection (YouTube Playlist / Local Recordings)
  - Phase 1 for local copies videos to streams/
- **Enhanced Configuration UI**:
  - Set Voice (TTS voice selection)
  - Set Game Title
  - Set Clips per Hour (1-20)
  - Start/Stop Telegram listener
- **New Launcher Script**: `./cogitator` for easy CLI access

### Changed
- Desktop app no longer requires importing broken workflow modules
- Fixed phase buttons to work with both YouTube and local sources
- Added QRadioButton for source selection
- Improved error handling for missing video files
- Added `shutil` import for file operations

### Technical
- Version: 2.0.0
- All v1.6.0 features preserved
- CLI commands: run, cleanup, onboard all functional

---

## 1.6.0 — 2026-04-11
### Added
- **Desktop Application Framework**: New side-by-side button/terminal menu design prepared
  - Button panel for pipeline control and configuration
  - Terminal-style status display for real-time monitoring
  - Ready for PyQt6 implementation
- **Dedicated Context Clear Command**: New `/context_clear` command
  - Clears all pipeline and content studio context
  - Available in both CLI and Telegram

### Changed
- **Telegram Inline Menu Cleanup**:
  - Removed `Stop` button (🛑) from main menu - replaced with help
  - Removed inline `/cs_context clear` - use `/context_clear` instead
  - Removed `/set_game clear` context clearing - only clears game title
  - Removed `clear_verified_context` calls from menus (except viewing context)
  - Removed `ctx_clear_game` callback - consolidated to one clear method
- **Improved Syntax**: Fixed indentation error in `_cs_extract_context_from_transcript()`
  - Lines 2880-2896 had 2-space indent in 4-space indented block

### Technical
- All existing CLI and Telegram commands still work
- Context system issues documented in `CONTEXT_SYSTEM_ISSUES.md`
- MemPalace integration preserved

---

## 1.5.0 — 2026-04-10
### Added
- **Markdown-Based Context**: Context now stored as markdown files in `/Context/{game}/`
  - `characters.md`, `locations.md`, `key_terms.md`, `relationships.md`
  - Editable directly in Obsidian with full graph view support
  - Replaces JSON-based context files
- **Self-Learning Memory System**: Integrated with MemPalace for universal learning
  - `_detect_corrections()` - Compares old vs new context to find corrections
  - `_store_corrections_as_constraints()` - Stores learned mistakes to prevent repetition
  - `_get_learned_constraints()` - Retrieves constraints for next extraction
- **Prompt Integration**: Context extraction now includes learned constraints in AI prompts
  - AI sees: "PREVIOUS MISTAKES TO AVOID" section
  - Prevents repeating same hallucination errors
- **User Visibility**: `/memory` command now shows learned constraints
- **Deleted**: Removed deprecated `content_studio/context/` directory (Obsidian files)

### Changed
- `_cs_load_context()` - Now reads from markdown files instead of JSON
- `_cs_save_context()` - Now writes to markdown files instead of JSON
- `_cs_update_context()` - Now detects corrections and stores constraints automatically
- Updated context menu to check for markdown files instead of JSON
- `/memory` command checks for markdown files in context directories

### Technical
- Universal learning system applies to ALL games (not game-specific)
- Corrections stored in `/Context/learned_constraints.json`
- Backward compatible with existing context structure

---

## 1.4.0 — 2026-04-10
### Added
- **Centralized Context Directory**: New `/Context/` folder for all context files shared between Pipeline and Content Studio
  - Located at `/home/alph4r1us/Cogitator/Context/`
  - Per-game subdirectories with `context.json` and `quality.json`
  - Replaces scattered context files in content_studio/ and root directory
- **Telegram Commands**:
  - `/memory` - Show MemPalace memory status and game list
  - `/games` - Show all games with context/memory status
- **Clear Context Button**: New button in context menu to clear game-specific context
- **Content Studio Script Length Fix**: Increased maxOutputTokens from 500 to 3072 for 5-10 minute scripts (1500-2000 words)
- **Script Validation Target**: Updated word count target from 200 to 1500 words for longer content

### Changed
- **Context Manager**: Updated to use new `/Context/` directory
- **Content Studio**: Now uses centralized context path based on GAME_TITLE
- **Removed Hardcoded Forbidden Characters**: Removed static forbidden list from `game_data/tell_me_why/characters.json`
  - Characters are now dynamically learned from script validation
- **Updated .gitignore**: Now ignores Context/, memory/, game_data/memory/, content_studio/, and metric files

### Removed
- **Deprecated Files**: Removed empty `output/` and `memory/` directories
- **Old Context Files**: Removed `verified_context.json` from root (now in Context/)

---

## 1.3.0 — 2026-04-09
### Added
- **MemPalace Integration**: Persistent memory system for storing conversation history and learned data
- **Script Validation System**: Post-generation factuality and engagement scoring
  - Character hallucination detection using fuzzy matching (RapidFuzz)
  - Location error detection using spaCy NER
  - Engagement scoring (hook strength, readability, sentiment)
- **Self-Improvement Framework**: Foundation for continuous learning from validation failures
- **Content Studio Context Tracking**: Obsidian-style markdown context files for characters, locations, relationships, and key terms
- **Script Validation Script**: Standalone validation module for analyzing script quality
- **Enhanced Metrics Logging**: generation_metrics.jsonl tracks detailed validation scores

### Changed
- Optimized script length for Shorts format (150-300 words target)
- Improved prompt engineering for better script structure
- Enhanced error handling in keychain manager
- Improved context extraction from transcripts

### Fixed
- Resolved spaCy location misclassification (proper nouns like "Tyler" flagged as locations)
- Fixed MemPalace import issues by adding workspace to sys.path
- Fixed script length issues (reduced from 1500 to target 150-300 words)
- Resolved import errors in script validation module

---

## 1.2.0 — 2026-04-07
### Added
- Secure API key management using system keychain (keyring) for all Gemini and Groq keys
- Removed plaintext `gemini_keys.txt` file storage
- Added `get_groq_keys()` function for consistency with `get_gemini_keys()`
- Enhanced keychain manager with bidirectional sync capabilities
- Improved context extraction accuracy with better prompt engineering
- Fixed Context Studio menu flow and data persistence
- Added validation to prevent hallucinated characters in script generation

### Changed
- Migrated all API key storage from files to system keychain
- Updated CONFIGURATION.md documentation to reflect keychain-only approach
- Enhanced error handling and logging throughout the pipeline
- Optimized rate limiting for Gemini API calls
- Improved transcript parsing for more accurate context extraction

### Fixed
- Resolved Gemini API 429 errors through proper key rotation
- Fixed Context Studio context clearing functionality
- Corrected indentation issues in onboard process
- Fixed relationship parsing in context loading
- Resolved import errors in keychain manager
- Ensured all API functions work with keychain-only keys

---

## 1.1.1 — 2026-04-06

### Bug Fixes

- Fixed TTS generation not executing in Content Studio (`/cs` → Generate TTS was stuck)
- Fixed API key rotation to use all available keys

---

## 1.1.0 — 2026-04-06

### Overview

Cogitator v1.1.0 adds persistent context for series continuity and improved script generation accuracy.

---

### New Features

#### Context Persistence
- **Shared Context**: Pipeline and Content Studio now share the same context file
- **Pipeline Integration**: After transcription, pipeline extracts characters/locations/relationships and saves to context
- **Context Clearing**: Context is cleared when `/set_game clear` is executed

#### Content Studio Series Generation
- **Sequential Processing**: Each script generation uses the newest unprocessed transcript
- **Series Continuity**: Previous script summaries included in prompts for natural follow-up
- **First Run**: Uses Chapter 1 transcript, extracts context, generates Script 1
- **Second Run**: Uses Chapter 2 transcript with Script 1 context, generates Script 2
- **Third Run**: Uses Chapter 3 transcript with Scripts 1-2 context, generates Script 3
- **No Rate Limit Blocking**: Wait 10 minutes between runs to avoid API rate limiting

#### Context-Aware Prompts
- AI prompts now include verified characters from previous transcripts
- Includes locations and relationships to prevent hallucination
- Includes previous script summaries for series continuity
- AI can no longer invent characters like "Nathan Prescott" or "Chloe Price"

#### Telegram Commands
- `/cs_context` - Show current context (characters, locations, relationships)
- `/cs_context clear` - Clear stored context

---

### Bug Fixes

- Fixed Content Studio not scanning `Next/` subfolder for transcripts
- Fixed transcripts not being sorted by chapter number
- Added more API keys to keychain (now supports 6 keys)

---

## 1.0.0 — 2026-04-05 (First Release)

### Overview

Cogitator v1.0.0 is the initial release of an automated YouTube Shorts pipeline for game streams. It handles the complete workflow from YouTube playlist to ready-to-edit shorts with AI-powered narration.

---

### Pipeline Features (5 Phases)

#### Phase 1: Download
- Downloads videos from YouTube playlists using yt-dlp
- Supports playlist-based downloading with configurable index
- Automatic skip if videos already exist (checkpointing)
- Supports multiple video formats (webm, mp4, mkv)

#### Phase 2: Transcription
- Uses Faster-Whisper for high-quality speech-to-text
- Generates both JSON (with timestamps) and SRT subtitle files
- Automatic fallback to stable-whisper if Faster-Whisper fails
- Further fallback to stable-ts CLI

#### Phase 3: Script Generation
- Google Gemini AI-powered script generation
- Context-aware prompts using GAME_TITLE setting
- Automatic character and location extraction from transcripts
- Key plot points extraction for accuracy
- Validates script against transcript content
- Prevents hallucination (AI inventing details not in transcript)
- Retry mechanism with feedback on failure

#### Phase 4: Clip Extraction
- FFmpeg-based video clip extraction
- Configurable clips per hour (1-20, default: 5)
- Scene-based segmentation
- Maintains video quality

#### Phase 5: TTS Generation
- Google Gemini TTS for voice narration
- SRT subtitle generation with word wrapping
- Configurable max words per subtitle line (3-20, default: 10)
- Long subtitles split into multiple entries with proportional timing
- Round-robin voice and style rotation for variety

---

### Content Studio Features

- **Import Pipeline Data**: Copy transcripts from main pipeline
- **Generate Script**: Analyze multiple transcripts with AI context memory
- **Generate TTS**: Create TTS audio from custom scripts
- **Clear All**: Reset all content studio files
- **Context Memory**: 
  - Automatic character extraction from transcripts
  - Location and key terms tracking
  - Relationship extraction between characters
  - Persistent context via context.json file

---

### Telegram Bot Commands

> **Note**: Telegram bot functionality is optional. The web interface provides full pipeline control.

#### Pipeline Control
- `/start` - Start pipeline
- `/run` - Run full pipeline
- `/run_phase N` - Run specific phase(s)
- `/skip_phase N` - Skip specific phase
- `/status` - Show pipeline status
- `/stop_pipeline` - Stop running pipeline

#### Configuration
- `/set_voice [voice]` - Change TTS voice
- `/voices` - List available voices
- `/set_style [text]` - Set TTS style prefix
- `/set_clips N` - Set clips per hour (1-20)
- `/set_srt_words N` - Set SRT max words (3-20)
- `/set_game [title]` - Set game title for scripts
- `/config` - Show current settings

#### Content Studio
- `/cs` - Open Content Studio menu
- `/cs_context` - View/edit stored context
- `/status` - Shows Content Studio settings + context

#### Utilities
- `/menu` - Interactive inline menu
- `/debug` - Show recent debug logs
- `/version` - Show version
- `/update` - Check and install updates
- `/restart_listener` - Restart Telegram listener
- `/delete_partial` - Delete incomplete files
- `/cleanup` - Delete all generated files
- `/help` - Show all commands

---

### Integrations

#### YouTube
- Playlist-based video downloading via yt-dlp
- Configurable playlist index
- Supports multiple formats

#### Telegram
- Bot API for command handling
- Inline keyboard menus
- Callback query handling
- Notifications on pipeline events

#### Google Gemini
- Gemini 2.0 Flash for script generation
- Gemini TTS for voice narration
- Multiple API key support with round-robin
- Rate limiting and retry logic

#### Faster-Whisper
- CPU-optimized speech-to-text
- VAD (Voice Activity Detection) filtering
- Automatic fallback to stable-whisper

---

### Technical Implementation

#### Environment Management
- .env file configuration
- Keychain integration for sensitive keys
- update_env_var() for runtime config changes

#### Checkpointing
- Each phase skips if output exists
- Resume from where pipeline left off

#### Context Extraction Logic
- Regex-based capitalized word detection
- Frequency counting for character identification
- Common word filtering
- Location and key term extraction

#### Script Generation Logic
- Full transcript reading (no truncation)
- Key plot points extraction
- Character relationship identification
- Validation against transcript content
- Production note removal before TTS

#### SRT Word Wrapping
- Splits long subtitles into 10-word chunks
- Creates separate SRT entries with proportional timing
- Configurable via SRT_MAX_WORDS (default: 10)

#### Round-Robin System
- Voice rotation for TTS variety
- Style rotation for different narration tones
- Shuffled once per pipeline run

---

### Configuration Options

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| PLAYLIST_URL | Yes | - | YouTube playlist URL |
| GEMINI_API_KEY | Yes | - | Google Gemini API key |
| TTS_VOICE | No | Vindemiatrix | Gemini TTS voice |
| GAME_TITLE | No | (none) | Game title for context |
| CLIPS_PER_HOUR | No | 5 | Clips per hour |
| SRT_MAX_WORDS | No | 10 | Words per subtitle line |
| PLAYLIST_INDEX | No | 1 | Playlist video index |
| TELEGRAM_BOT_TOKEN | No | (none) | Telegram bot token |
| TELEGRAM_CHAT_ID | No | (none) | Telegram chat ID |
| TTS_DELAY | No | 120 | Seconds between TTS |

---

### Available TTS Voices

Aoede, Callirrhoe, Gacrux, Kore, Leda, Puck, Sao, Zephyr, Fenrir, Charon, Orus, Umbriel, Vindemiatrix, Alnilam, Schedar, Sadachbia, Rasalgethi, Algieba

---

### Project Structure

```
Cogitator/
├── workflows/           # Main pipeline code
│   ├── cogitator.py  # Main application
│   ├── keychain_manager.py
│   └── update_manager.py
├── docs/               # Documentation
├── .env.example       # Configuration template
├── install.sh         # Installation script
├── requirements.txt   # Python dependencies
└── README.md         # Documentation
```

---

### Dependencies

- Python 3.11+
- FFmpeg
- Faster-Whisper
- Google Gemini API
- yt-dlp
- python-dotenv
- keyring

---

### Known Limitations

- Requires YouTube Data API access for playlist features
- Gemini API key required for script generation and TTS
- Linux-only (tested on Arch Linux)
- Requires significant disk space for video storage

---

### Upcoming Features (Planned)

- Windows support
- Multiple language support
- Cloud deployment options
- Web UI for non-Telegram users
- Automated video upload to YouTube

---

**End of Changelog**