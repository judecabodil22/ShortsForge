# Cogitator Improvement Plan

**Version:** 2.4.0 → 2.5.0 (Implemented) → 3.0.0 Roadmap  
**Date:** 2026-08-02  
**Status:** Implementation Complete (v2.5.0)  
**Constraint:** Local-only, single-user, free API keys only, no cloud hosting

---

## Executive Summary

This document outlines a comprehensive improvement plan for Cogitator across all feature categories. The plan is organized into phases:

1. **Phase 1: Foundation** (Immediate) — Bug fixes, deduplication, cleanup, remove Telegram
2. **Phase 2: Enhancement** (Short-term) — Feature improvements, UX polish, learning system
3. **Phase 3: Innovation** (Medium-term) — New capabilities, local AI improvements, plugin system

### Design Principles

- **Local-first**: All processing runs on user's hardware. No cloud hosting.
- **Single-user**: No multi-user, no collaboration, no logins.
- **Free APIs only**: Use free-tier models (Groq, Gemini free tier, Kokoro offline).
- **Self-learning**: Project learns from its own output via A/B testing, not from community.
- **No community features**: No AI assistants, no marketplaces, no social features.
- **Hardware-aware**: Detect and adapt to user's hardware capabilities.
- **Kokoro-primary TTS**: Use offline Kokoro as primary, Gemini as fallback only.

---

## 1. Pipeline Orchestration

### Current State
7-phase pipeline with checkpoint/resume, stop handling, WebSocket updates: Download → Transcribe → Context → Script → Clip → TTS → Assembly.

### Improvements

| Priority | Change                     | Type    | Description                                                                                                                                               |
| -------- | -------------------------- | ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P0 | Fix phase naming | Remap | Document 7 phases correctly: Download → Transcribe → Context → Script → Clip → TTS → Assembly |
| P0       | Remove Telegram & CLI    | Remove  | Remove ALL Telegram code (~500 lines in `cogitator.py`: `tg_api()`, `process_cmd()`, listener, onboarding). Remove CLI commands (`listen`, `stop`). Keep only Web UI interface. Remove `pyproject.toml` entry point. |
| P1       | Phase progress granularity | Enhance | Each phase reports sub-progress (e.g., "Transcribing: 45% of segments") not just phase start/end                                                          |
| P1       | Parallel phase execution   | Enhance | Run independent phases concurrently (e.g., TTS + Clip extraction can overlap)                                                                             |
| P1       | Pipeline templates         | New     | Save/load pipeline configurations as named templates (e.g., "Quick YouTube Short", "Long-form Analysis")                                                  |
| P2       | Dry-run mode               | New     | Run pipeline without API calls — validates config, checks dependencies, simulates flow                                                                    |
| P2       | Pipeline rollback          | New     | Undo last pipeline run (delete generated files, restore previous state)                                                                                   |
| P2       | Conditional phases         | New     | Skip phases based on conditions (e.g., skip download if video exists, skip TTS if script unchanged)                                                       |
| P3       | Distributed pipeline       | New     | Split pipeline across multiple machines for large batch processing                                                                                        |
| P3       | Pipeline versioning        | New     | Tag pipeline runs with versions; compare outputs across versions                                                                                          |

### Files to Modify
- `workflows/pipeline/pipeline_runner.py` — Phase granularity, parallel execution
- `workflows/cogitator.py` — Remove dead code, add dry-run
- `workflows/core/pipeline_context.py` — Template support, rollback state

---

## 2. Context Management

### Current State
Two-tier verified context, Obsidian markdown, MemPalace integration, franchise mapping.

### Improvements

| Priority | Change                         | Type    | Description                                                                               |
| -------- | ------------------------------ | ------- | ----------------------------------------------------------------------------------------- |
| P0       | Dedup learned_constraints.json | Fix     | Already done (22K → 339). Add monitoring to prevent re-duplication                        |
| P0       | Fix false-positive corrections | Fix     | Already done. Verify edge cases with empty extractions                                    |
| P1       | Context diff visualization     | New     | Show before/after comparison when context changes (like git diff)                         |
| P1       | Context versioning             | New     | Tag context snapshots with versions; compare across pipeline runs                         |
| P1       | Bulk context operations        | Enhance | Select multiple entities and batch edit/delete                                            |
| P1       | Context validation rules       | New     | User-defined rules (e.g., "No characters named X", "Maximum 20 characters")               |
| P2       | Context auto-tagging           | New     | AI automatically tags entities with categories (protagonist, antagonist, location type)   |
| P2       | Context relationship types     | New     | Beyond "friends/enemies" — add "mentor", "rival", "family", "ally" with confidence scores |
| P2       | Context export formats         | New     | Export to JSON, CSV, Obsidian markdown, Notion, or custom format                          |
| P2       | Context import from URL        | New     | Import context from public wikis (Fandom, Wikipedia)                                      |
| P3       | Context collaboration          | New     | Multi-user context editing with conflict resolution                                       |
| P3       | Context AI assistant           | New     | Chat interface to query context ("Who is Tyler's sister?")                                |
| P3       | Context auto-discovery         | New     | Automatically discover related games and merge relevant context                           |

### Files to Modify
- `workflows/context_manager.py` — Diff visualization, versioning, validation rules
- `workflows/context_manager_v2.py` — Bulk operations, auto-tagging, relationship types
- `workflows/context_extractor.py` — Auto-discovery, wiki import

---

## 3. Knowledge Graph

### Current State
Force-directed graph, 6 visual themes (with physics presets), implicit edges, franchise merging.

### Improvements

| Priority | Change | Type | Description |
|----------|--------|------|-------------|
| P1 | Graph search | New | Search for entities/relationships within the graph |
| P1 | Graph filtering | Enhance | Filter by entity type, relationship type, confidence score |
| P1 | Graph statistics | Enhance | Show centrality scores, clustering coefficients, path lengths |
| P2 | Graph animation | New | Animate entity creation over time (timeline slider) |
| P2 | Graph export | New | Export as SVG, PNG, JSON, or Mermaid diagram |
| P2 | Graph comparison | New | Compare two graphs (before/after, game A vs game B) |
| P2 | Graph layout presets | New | Save/load custom physics configurations |
| P3 | Graph AI insights | New | "Most connected character", "Isolation clusters", "Key relationship paths" |
| P3 | Graph 3D mode | New | 3D force-directed graph for large datasets |
| P3 | Graph embedding | New | Embed graph in external pages (Obsidian, Notion) |

### Files to Modify
- `frontend/src/pages/Graph.tsx` — Search, filtering, statistics, animation
- `workflows/graph_builder.py` — Export, comparison, AI insights
- `frontend/src/lib/graphSettings.ts` — Layout presets

---

## 4. Script Generation

### Current State
10 variants (mystery_recap, breakdown, timeline, lesson, narrative, news_report, documentary, true_crime, character_pov, true_story), learning-weighted selection, context-injected prompts, Jinja2 templates.

### Improvements

| Priority | Change                      | Type | Description                                                                      |
| -------- | --------------------------- | ---- | -------------------------------------------------------------------------------- |
| P0       | Remove deleted variant refs | Fix  | Ensure no references to deleted variants exist                                   |
| P1       | Custom variant creation     | New  | Users create their own script variants with custom prompts                       |
| P1       | Script versioning           | New  | Keep history of all generated scripts; compare versions                          |
| P1       | Script collaboration        | New  | Comment on scripts, suggest edits, approve/reject                                |
| P1       | Script A/B testing          | New  | Generate two versions and track which performs better                            |
| P2       | Script Templates Library    | New  | Pre-built templates for common scenarios (game review, character analysis, etc.) |
| P2       | Script translation          | New  | Translate scripts to other languages while preserving style                      |
| P2       | Script audio preview        | New  | Quick TTS preview without full pipeline run                                      |
| P2       | Script analytics            | New  | Read time, word density, emotional tone analysis                                 |
| P3       | Script AI co-writer         | New  | Chat interface to iteratively refine scripts                                     |
| P3       | Script style transfer       | New  | Convert one variant to another (mystery → documentary)                           |
| P3       | Script plagiarism check     | New  | Check against published content for originality                                  |

### Files to Modify
- `workflows/cogitator.py` — Custom variants, versioning, translation
- `workflows/script_validation.py` — Analytics, plagiarism check
- `prompts/content_studio.j2` — Template library

---

## 5. Script Validation

### Current State
spaCy NER, RapidFuzz validation, factuality checking, engagement scoring.

### Improvements

| Priority | Change                       | Type | Description                                           |
| -------- | ---------------------------- | ---- | ----------------------------------------------------- |
| P1       | Validation rules editor      | New  | Web UI to define custom validation rules              |
| P1       | Validation confidence scores | New  | Show confidence level for each validation check       |
| P1       | Validation history           | New  | Track validation results over time to identify trends |
| P2       | Custom NER models | New | Train custom NER models for game-specific entities (local, no API) |
| P2       | Semantic validation | New | Check semantic consistency using local sentence-transformers |
| P2       | Sentiment analysis | New | Detect emotional tone using local models |

### Files to Modify
- `workflows/script_validation.py` — Confidence scores, history, semantic validation

---

## 6. Text-to-Speech

### Current State
Kokoro (offline, primary), Gemini (API, fallback), Edge (free cloud), 30+ voices, style presets, word-level subtitles.

### Improvements

| Priority | Change                | Type    | Description                                             |
| -------- | --------------------- | ------- | ------------------------------------------------------- |
| P0       | Kokoro-primary default | Remap | Set `TTS_PROVIDER=kokoro` as default; Gemini only as fallback when Kokoro fails |
| P0       | Voice quality audit   | Enhance | Test all voice mappings; fix poor Kokoro equivalents    |
| P1       | Voice emotion control | New     | Adjust emotional tone (happy, sad, excited, calm) using Kokoro styles |
| P1       | Voice speed control   | New     | Adjustable speech rate per voice/style                  |
| P1       | Multi-voice dialogue  | New     | Different voices for different characters in script     |
| P2       | Voice effects         | New     | Reverb, echo, whisper, radio filter effects via pydub/sox (local) |
| P2       | Voice comparison      | New     | Compare same text across different voices (local only, no API) |
| P2       | Voice learning        | New     | Track which voices perform best per content type        |

### Files to Modify
- `workflows/pipeline/phase_tts.py` — Make Gemini fallback-only, add fallback logic
- `workflows/pipeline/phase_tts_kokoro.py` — Quality audit, effects, emotion control

---

## 7. Audio/Video Analysis

### Current State
PySceneDetect, motion scoring, audio analysis.

### Improvements

| Priority | Change | Type | Description |
|----------|--------|------|-------------|
| P1 | Scene detection tuning | Enhance | Expose PySceneDetect parameters (threshold, min_scene_len) |
| P1 | Audio classification | New | Detect speech, music, silence, noise using librosa (local, no API) |
| P1 | Beat detection | New | Detect musical beats using librosa for rhythmic editing |
| P2 | Visual quality analysis | New | Detect blur, lighting issues using OpenCV (local, no API) |
| P2 | Audio quality analysis | New | Detect clipping, background noise using librosa (local) |
| P2 | Emotion detection | New | Analyze audio energy/tempo for emotional content (local heuristic) |
| P2 | Speaker diarization | New | Identify different speakers using pyannote.audio (local model) |
| P3 | Scene classification | New | "Action scene", "Dialogue scene", "Cutscene" using audio/visual heuristics (local) |

### Files to Modify
- `workflows/audio_analysis.py` — Classification, beat detection, quality analysis (all local, no API calls)

---

## 8. Performance Database & Learning

### Current State
SQLite database, Thompson sampling, XGBoost predictor, channel baselines.

### Core Learning Philosophy

The project learns from **its own output** through A/B testing, not from community data. Here's how:

1. **Self-generated A/B testing**: When generating clips, the system creates multiple variants (Test A, Test B) from the same source material
2. **Performance tracking**: Each variant's performance is tracked (views, engagement, retention)
3. **Pattern recognition**: The system identifies what works (hook types, content types, voices, styles) based on its own results
4. **Adaptive selection**: Thompson sampling selects future parameters based on observed performance
5. **No external data needed**: All learning comes from the project's own YouTube channel performance

### Learning from Other Channels

Since we're local-only with free API keys, learning from other channels works through **public YouTube data**:

| Method | How It Works | Data Source |
|--------|--------------|-------------|
| **Trending Analysis** | Fetch trending gaming videos via YouTube Data API (free tier) to identify what content types are popular | YouTube Data API v3 (free) |
| **Category Benchmarking** | Compare our performance against public averages for gaming Shorts in our region | YouTube Data API (views/likes from public videos) |
| **Competitor Tracking** | Manually add competitor channel IDs; system fetches their public metrics periodically | YouTube Data API (public data only) |
| **Topic Discovery** | Analyze titles/descriptions of trending videos to identify popular games/topics | YouTube Data API + local NLP |
| **Hook Pattern Mining** | Extract opening patterns from high-performing public videos (titles, first 3 seconds) | YouTube Data API + local analysis |

**Important**: All learning from other channels uses **public data only** via free API tiers. No scraping, no paid APIs, no community features.

### Improvements

| Priority | Change | Type | Description |
|----------|--------|------|-------------|
| P0 | Fix store_learning average | Fix | Already done. Verify edge cases with zero samples |
| P0 | Fix TTS learning key | Fix | Already done. Verify (voice, style, content_type) uniqueness |
| P1 | Learning dashboard | New | Visualize learning data (what's working, what's not) |
| P1 | A/B test framework | New | Generate Test A and Test B clips from same source; track performance independently |
| P1 | Learning export/import | New | Export learning data for backup or transfer |
| P2 | Multi-armed bandit | New | More sophisticated exploration strategies (UCB, Thompson with context) |
| P2 | Trending analysis | New | Fetch trending gaming videos via YouTube Data API (free) to identify popular content types |
| P2 | Competitor benchmarking | New | Track public metrics of competitor channels; compare our performance |
| P2 | Hook pattern mining | New | Extract successful hook patterns from high-performing public videos |

### Files to Modify
- `workflows/performance_database.py` — Dashboard, export/import, trending analysis
- `workflows/learning_engine.py` — A/B testing, competitor benchmarking, hook mining

---

## 9. YouTube Integration

### Current State
Download, metrics fetch, OAuth, auto-matching.

### Status: ON SHELF

> **Decision**: YouTube Integration improvements are deferred. Current metrics and data from the API are sufficient for now. Focus on learning system and core pipeline improvements first.

### Deferred Improvements (Future Consideration)

| Change | Type | Description |
|--------|------|-------------|
| YouTube Analytics API | New | Deeper insights (watch time, retention) |
| Auto-publishing | New | Publish directly to YouTube from pipeline |
| Thumbnail generation | New | AI-generated thumbnails for videos |
| SEO optimization | New | Optimize titles, descriptions, tags |
| Comment analysis | New | Analyze comments for feedback |
| Multi-platform | New | Support TikTok, Instagram Reels, Twitter/X |

---

## 10. Video Assembly

### Current State
FFmpeg assembly, content-type templates, subtitle styling, audio ducking.

### Design Principle
The project must detect the user's hardware and adapt encoding settings accordingly. No background music, no watermark, no real-time preview. Transitions are automatically chosen based on scene content.

### Improvements

| Priority | Change | Type | Description |
|----------|--------|------|-------------|
| P0 | Hardware detection | New | Auto-detect CPU cores, RAM, GPU (NVENC/VA-API) and set encoding params accordingly |
| P0 | Auto transition selection | New | Automatically choose transition type based on scene content (fade for calm, cut for action) |
| P1 | GPU acceleration | Enhance | Use NVENC/VA-API for faster encoding when GPU detected |
| P1 | Adaptive encoding | New | Scale quality/threads based on available hardware resources |
| P1 | Color grading | New | Apply color filters for consistent look (local FFmpeg filters) |
| P2 | Aspect ratio conversion | New | Auto-convert to 9:16, 16:9, 1:1 based on target platform |
| P2 | Batch assembly | New | Assemble multiple videos in parallel (respecting hardware limits) |

### Files to Modify
- `workflows/pipeline/phase_assemble.py` — Hardware detection, auto transitions, adaptive encoding

---

## 11. Configuration & Settings

### Current State
JSON config, subtitle settings, pipeline settings.

### Improvements

| Priority | Change | Type | Description |
|----------|--------|------|-------------|
| P1 | Config validation | New | Validate all config values on save (range, type, dependencies) |
| P1 | Config profiles | New | Save/load multiple config profiles (e.g., "Dev", "Prod", "Test") |
| P1 | Config search | New | Search across all config options |
| P2 | Config history | New | Track config changes with rollback |
| P2 | Config import/export | New | Export config as JSON/YAML for sharing |
| P2 | Config wizard | New | Interactive setup wizard for new installations |
| P3 | Config API | New | External API to manage config from other tools |
| P3 | Config UI builder | New | Drag-and-drop interface builder for settings |

### Files to Modify
- `backend/main.py` — Validation, profiles, history
- `frontend/src/pages/Settings.tsx` — Search, wizard, UI builder

---

## 12. Security & Authentication

### Current State
API key auth, keychain storage, .env fallback.

### Design Principle
Local-only, single-user. No login, no 2FA, no RBAC. Focus on protecting API keys and securing local data.

### Improvements

| Priority | Change | Type | Description |
|----------|--------|------|-------------|
| P0 | API key protection | Enhance | Ensure API keys never exposed in logs, error messages, or frontend |
| P0 | .env security | Enhance | Validate .env permissions (600), warn if world-readable |
| P1 | Rate limiting per endpoint | Enhance | Different limits for different endpoints (prevent abuse) |
| P1 | CORS hardening | Enhance | Restrict CORS to localhost only |
| P1 | Input validation | Enhance | Schema validation for all API inputs (prevent injection) |
| P1 | Audit logging | New | Log all config changes and pipeline runs for debugging |
| P2 | Key rotation | New | Automated API key rotation with multiple keys |

### Files to Modify
- `backend/main.py` — Rate limiting, CORS, validation, audit logging
- `workflows/keychain_manager.py` — Key rotation

---

## 13. Web UI Pages

### Current State
Dashboard, Graph, Scripts, Metrics, Context, Settings, Prompt Editor.

### Improvements

| Priority | Change | Type | Description |
|----------|--------|------|-------------|
| P1 | Responsive design | Enhance | Mobile-friendly layout |
| P1 | Keyboard shortcuts | New | Global keyboard shortcuts for all actions |
| P1 | Dark/light mode | New | System-aware theme switching |
| P1 | Undo/redo | New | Undo/redo for all changes |
| P2 | Customizable dashboard | New | Drag-and-drop widget arrangement |
| P2 | Data tables | Enhance | Sortable, filterable, paginated tables |
| P2 | Charts library | Enhance | More chart types (pie, scatter, heatmap) |
| P2 | Notification center | New | In-app notification history |
| P3 | Offline mode | New | Work offline with sync when online |
| P3 | Progressive Web App | New | Install as PWA, work offline |
| P3 | Multi-language | New | i18n support for UI |

### Files to Modify
- `frontend/src/pages/` — All pages
- `frontend/src/components/` — All components
- `frontend/src/App.tsx` — Routing, undo/redo

---

## 14. Web UI Components

### Current State
Pipeline progress, command palette, toasts, animated counters.

### Improvements

| Priority | Change | Type | Description |
|----------|--------|------|-------------|
| P1 | Component library | Enhance | Extract reusable components to shared library |
| P1 | Accessibility | Enhance | ARIA labels, keyboard navigation, screen reader support |
| P1 | Loading states | Enhance | Skeleton loaders, progress indicators |
| P2 | Drag-and-drop | New | Drag-and-drop for lists, reordering |
| P2 | Rich text editor | New | WYSIWYG editor for scripts/prompts |
| P2 | Code editor | New | Syntax-highlighted editor for config/templates |
| P2 | Data visualization | New | Charts, graphs, sparklines in components |
| P3 | Component marketplace | New | Share custom components |

### Files to Modify
- `frontend/src/components/` — All components

---

## 15. Web UI Themes

### Current State
5 Warhammer 40K themes.

### Improvements

| Priority | Change | Type | Description |
|----------|--------|------|-------------|
| P1 | Custom theme creator | New | Visual theme editor (colors, fonts, spacing) |
| P1 | Theme import/export | New | Share themes as JSON |
| P1 | Theme preview | New | Preview theme before applying |
| P2 | More themes | New | Sci-fi, Minimalist, Classic, Neon, Pastel |
| P2 | Theme scheduling | New | Auto-switch themes based on time of day |
| P2 | High contrast mode | New | Accessibility-focused high contrast theme |
| P3 | Theme marketplace | New | Community-shared themes |

### Files to Modify
- `frontend/src/contexts/ThemeContext.tsx` — Creator, import/export, scheduling
- `frontend/src/index.css` — New themes

---

## 16. Backend API

### Current State
41 REST endpoints, WebSocket, API key auth.

### Improvements

| Priority | Change | Type | Description |
|----------|--------|------|-------------|
| P1 | API documentation | New | OpenAPI/Swagger auto-generated docs |
| P1 | API versioning | New | /api/v1/ prefix for backward compatibility |
| P1 | Request validation | New | Pydantic models for all request/response |
| P1 | Error handling | Enhance | Consistent error format with codes |
| P2 | GraphQL | New | GraphQL endpoint for flexible queries |
| P2 | Batch endpoints | New | Process multiple items in one request |
| P2 | Webhooks | New | Push notifications for events |
| P3 | gRPC | New | High-performance internal API |
| P3 | Event sourcing | New | Event log for all state changes |

### Files to Modify
- `backend/main.py` — Documentation, versioning, validation, GraphQL

---

## 17. Telegram Integration

### Status: REMOVED

> **Decision**: Telegram integration has been completely removed. The project uses Web UI only. All Telegram code (~500 lines in `cogitator.py`) and CLI commands (`listen`, `stop`) have been removed.

### Removal Tasks

| Priority | Task | Description |
|----------|------|-------------|
| P0 | Remove Telegram code | Delete `tg_api()`, `process_cmd()`, listener, onboarding setup from `cogitator.py` |
| P0 | Remove CLI commands | Delete `listen`, `stop` commands from CLI |
| P0 | Remove Telegram env vars | Remove `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` from .env.example |
| P0 | Remove pyproject.toml entry | Remove `cogitator-listener` entry point |

---

## 18. System Management

### Current State
Auto-update, backup rotation, file cleanup.

### Design Principle
Local-only deployment. No Docker, no Kubernetes, no cloud. Focus on local system health and updates.

### Improvements

| Priority | Change | Type | Description |
|----------|--------|------|-------------|
| P1 | Update notifications | New | Notify user when updates available via Web UI |
| P1 | Backup management | New | View, restore, delete backups via UI |
| P1 | System monitoring | New | CPU, memory, disk usage dashboard (local, using psutil) |
| P2 | Log management | New | Log rotation, compression, archival |
| P2 | Hardware profiling | New | Auto-detect CPU, RAM, GPU for encoding settings |

### Files to Modify
- `workflows/update_manager.py` — Notifications, backup management
- `backend/main.py` — System monitoring endpoint

---

## 19. Utilities & Constants

### Current State
Fuzzy dedup, alias resolution, parsing, scoring functions.

### Improvements

| Priority | Change | Type | Description |
|----------|--------|------|-------------|
| P1 | Configurable thresholds | Enhance | Expose all hardcoded thresholds as config options |
| P1 | Performance profiling | New | Profile utility functions for bottlenecks |
| P2 | Caching layer | New | Cache expensive computations (syllable counting, etc.) |
| P2 | Parallel utilities | New | Process large lists in parallel |
| P2 | Utility library | New | Extract to standalone package for reuse |
| P3 | C extensions | New | Rewrite critical paths in C for speed |

### Files to Modify
- `workflows/constants.py` — Configurable thresholds, caching

---

## Implementation Priority Matrix

### Phase 1: Foundation (Weeks 1-4)
| Task | Effort | Impact |
|------|--------|--------|
| Remove dead code (Telegram stubs, generators, content_studio) | Low | High |
| Fix phase naming inconsistency | Low | Medium |
| Config validation | Medium | High |
| API documentation (OpenAPI) | Medium | High |
| Rate limiting per endpoint | Low | High |
| Learning dashboard | Medium | High |
| Voice quality audit | Medium | Medium |
| Responsive design (mobile) | High | High |

### Phase 2: Enhancement (Weeks 5-12)
| Task | Effort | Impact |
|------|--------|--------|
| Context diff visualization | Medium | High |
| Graph search/filtering | Medium | High |
| Custom variant creation | High | High |
| Validation rules editor | Medium | High |
| Voice emotion/speed control | High | High |
| Scene detection tuning | Low | Medium |
| A/B test framework | High | High |
| YouTube Analytics API | Medium | High |
| GPU acceleration | Medium | High |
| Config profiles | Medium | Medium |
| Keyboard shortcuts | Medium | High |
| Undo/redo | High | High |

### Phase 3: Innovation (Weeks 13-24)
| Task | Effort | Impact |
|------|--------|--------|
| Voice emotion/speed control | High | High |
| Multi-voice dialogue | High | High |
| Voice effects (pydub/sox) | Medium | Medium |
| Context diff visualization | Medium | High |
| Graph search/filtering | Medium | High |
| A/B test framework | High | High |
| Customizable dashboard | High | Medium |
| Custom theme creator | Medium | Medium |
| 3D graph visualization | High | Low |
| Plugin system | Very High | High |

---

## Technical Debt to Address

| Debt | Location | Priority |
|------|----------|----------|
| Telegram legacy code (~500 lines) | `cogitator.py` (inline: `tg_api()`, `process_cmd()`, listener, onboarding) | P0 |
| Missing ASSEMBLY_DIR import | `pipeline_runner.py` line 73 references `ASSEMBLY_DIR` but it's not imported (would cause NameError) | P0 |
| Dead phase_lore reference | `pipeline/__init__.py` line 8 references `phase_lore` which doesn't exist | P1 |
| Backend/pipeline phase count mismatch | Backend has 6 phases (1-6) but pipeline_runner has 7 phases (1-7 including Assembly) | P1 |
| Deleted module references in docs | Various .md files | P0 (done) |
| Hardcoded thresholds | `constants.py`, `cogitator.py` | P1 |
| Global state in some modules | `cogitator.py` | P1 |
| Inconsistent error handling | All Python files | P1 |
| Missing type hints | All Python files | P2 |
| No test suite | Entire codebase | P2 |
| No CI/CD pipeline | Repository | P2 |
| No linting in CI | Repository | P2 |
| No documentation generation | Repository | P3 |

---

## Architecture Recommendations

### Current Architecture Issues
1. **Monolithic cogitator.py** — 6800+ lines, handles everything
2. **No dependency injection** — Hard to test, hard to mock
3. **No plugin system** — Adding new features requires modifying core files
4. **No event system** — Components are tightly coupled

### Proposed Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Cogitator 3.0                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────┐  ┌──────────┐                            │
│  │ Web UI   │  │ API      │                            │
│  └────┬─────┘  └────┬─────┘                            │
│       │              │                                  │
│       └──────────────┼──────────────┘                   │
│                      │                                  │
│              ┌───────▼───────┐                          │
│              │  Core Engine  │                          │
│              │  (Event Bus)  │                          │
│              └───────┬───────┘                          │
│                      │                                  │
│  ┌──────────┬────────┼────────┬──────────┐            │
│  │          │        │        │          │            │
│  ▼          ▼        ▼        ▼          ▼            │
│ Context   Script   TTS    Assembly   Learning        │
│ Service   Service  Service Service   Service          │
│                                                         │
│  ┌─────────────────────────────────────────────────┐  │
│  │              Plugin System                       │  │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐          │  │
│  │  │YouTube│ │Custom│ │ ...  │ │ ...  │          │  │
│  │  └──────┘ └──────┘ └──────┘ └──────┘          │  │
│  └─────────────────────────────────────────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Key Changes
1. **Event Bus** — Decouple components via publish/subscribe
2. **Service Layer** — Each domain gets its own service class
3. **Plugin System** — New platforms/features as plugins
4. **Dependency Injection** — Services receive dependencies via constructor
5. **Interface Contracts** — Define interfaces for all services

---

## Migration Strategy

### From 2.4.0 to 3.0.0

1. **Phase 1: Preparation**
   - Create comprehensive test suite
   - Set up CI/CD pipeline
   - Document current architecture

2. **Phase 2: Core Refactor**
   - Extract services from cogitator.py
   - Implement event bus
   - Add dependency injection

3. **Phase 3: Feature Parity**
   - Ensure all existing features work
   - Migrate data formats if needed
   - Update all documentation

4. **Phase 4: New Features**
   - Implement Phase 2 improvements
   - Add plugin system
   - Launch new web UI

5. **Phase 5: Deprecation**
   - Mark old APIs as deprecated
   - Provide migration guides
   - Remove old code after transition period

---

## Success Metrics

| Metric | Current | Target (3.0) |
|--------|---------|--------------|
| Pipeline reliability | ~85% | 99% |
| Average pipeline time | ~30 min | ~15 min |
| API response time | ~500ms | ~100ms |
| Test coverage | 0% | 80% |
| Documentation coverage | ~40% | 90% |
| User satisfaction | Unknown | Survey-based |

---

## Prerequisites & Dependencies

### Python Packages (NEW)

```
# Phase 1 — Foundation
pyyaml>=6.0                    # Pipeline templates, config import/export
loguru>=0.7                     # Structured logging, log rotation
psutil>=5.9                     # System monitoring dashboard
cachetools>=5.3                 # Caching layer for expensive computations

# Phase 2 — Enhancement
httpx>=0.25                     # Async URL context import, faster HTTP
beautifulsoup4>=4.12            # Context import from wikis (Fandom, Wikipedia)
pydub>=0.25                     # Voice effects, background music ducking
Pillow>=10.0                    # Thumbnail generation, watermark overlay
textstat>=0.7                   # Script analytics (readability, word density)
networkx>=3.0                   # Graph statistics (centrality, clustering)
sentence-transformers>=2.2      # Semantic validation beyond entity matching

# Phase 3 — Innovation
coqui-tts>=0.22                 # Custom voice creation, self-hosted TTS
librosa>=0.10                   # Audio classification, beat detection, emotion
pyannote.audio>=3.1             # Speaker diarization
python-jose[cryptography]>=3.3  # JWT tokens for OAuth2
passlib[bcrypt]>=1.7            # Password hashing for RBAC
pyotp>=2.9                      # Two-factor authentication (TOTP)
cryptography>=41.0              # Encryption at rest
strawberry-graphql[fastapi]>=0.214  # GraphQL endpoint

# Phase 4 — Scale
grpcio>=1.60                    # gRPC high-performance API
grpcio-tools>=1.60              # gRPC protobuf compilation
redis>=5.0                      # Caching, message broker, distributed pipeline
aiosqlite>=0.19                 # Async database for multi-user
python-telegram-bot>=20.0       # Modern Telegram bot (if keeping)
```

### Python Dev/Test Packages

```
pytest>=8.0                     # Unit testing
pytest-asyncio>=0.23            # Async test support
pytest-cov>=4.1                 # Test coverage reporting
pytest-mock>=3.12               # Mocking for unit tests
ruff>=0.3                       # Fast Python linter + formatter
mypy>=1.8                       # Static type checking
pre-commit>=3.6                 # Git hooks for linting on commit
line_profiler>=4.1              # Performance profiling
memory_profiler>=0.61           # Memory profiling
sphinx>=7.0                     # API documentation generation
sphinx-rtd-theme>=2.0           # Documentation theme
```

### JavaScript Packages (NEW)

```
# Phase 2 — Enhancement
react-diff-viewer-continued ^3.4    # Context diff visualization
@tanstack/react-table ^8.11         # Sortable, filterable data tables
@radix-ui/react-slider ^1.1         # Voice speed, scene detection tuning
@radix-ui/react-select ^2.0         # Config profiles, settings UI

# Phase 3 — Innovation
react-force-graph-3d ^1.24          # 3D graph mode
three ^0.162                        # 3D rendering
@react-three/fiber ^8.15            # React Three.js integration
html2canvas ^1.4                    # Graph export as PNG
react-i18next ^14.0                 # Multi-language i18n
i18next ^23.8                       # i18n core
vite-plugin-pwa ^0.19               # Progressive Web App
workbox-window ^7.0                 # PWA offline caching
idb ^8.0                            # IndexedDB for offline storage
diff ^5.1                           # Text diff for script versioning

# UI Components
@radix-ui/react-progress ^1.0       # Enhanced pipeline progress
@radix-ui/react-popover ^1.0        # Theme preview, config wizard
@radix-ui/react-accordion ^1.1      # Config sections
@radix-ui/react-toggle ^1.0         # Theme creator toggles
@radix-ui/react-separator ^1.0      # UI layout separator
@radix-ui/react-alert-dialog ^1.0   # Confirmation dialogs
@radix-ui/react-context-menu ^2.1   # Right-click menus
@radix-ui/react-scroll-area ^1.0    # Scrollable panels
@radix-ui/react-switch ^1.0         # Dark/light mode toggle
react-hotkeys-hook ^4.5             # Global keyboard shortcuts
react-grid-layout ^1.4              # Customizable dashboard
immer ^10.0                         # Undo/redo state management
@dnd-kit/core ^6.1                  # Drag-and-drop
@tiptap/react ^2.2                  # Rich text editor
@tiptap/starter-kit ^2.2            # Rich text starter extensions
@uiw/react-codemirror ^4.21         # Code editor wrapper
@codemirror/lang-json ^6.0          # JSON syntax highlighting
d3 ^7.9                             # Data visualization
```

### JavaScript Dev/Test Packages

```
vitest ^1.2                          # Frontend unit testing
@testing-library/react ^14.1         # React component testing
@testing-library/jest-dom ^6.1       # DOM assertion matchers
jsdom ^24.0                          # DOM environment for Vitest
eslint ^8.56                         # JS/TS linting
@typescript-eslint/eslint-plugin ^7.0
@typescript-eslint/parser ^7.0
eslint-plugin-react-hooks ^4.6
prettier ^3.2                        # Code formatting
eslint-config-prettier ^9.1
@axe-core/react ^4.8                 # Accessibility testing
playwright ^1.41                     # End-to-end testing
msw ^2.1                             # API mocking for tests
```

### System Packages (apt/pacman)

```
# Audio/Video Processing
ffmpeg                              # Video processing (ensure NVENC/VA-API support)
libva-dev                           # VA-API hardware acceleration (AMD/Intel)
portaudio19-dev                     # Audio I/O for real-time TTS
libsndfile1                         # Audio file I/O for librosa/pydub
libsndfile1-dev                     # Audio processing development headers
sox                                 # Audio effects (reverb, echo)
libsox-dev                          # Sox development headers

# Security
libssl-dev                          # TLS support for OAuth2/SSO
libffi-dev                          # Required by cryptography library

# GPU (Optional — for acceleration)
nvidia-cuda-toolkit                 # GPU acceleration for NVENC, deep learning

# Infrastructure
redis-server                        # Caching, message broker
docker.io                           # Containerized deployment (Phase 4)
docker-compose                      # Multi-container orchestration (Phase 4)

# Development
python3.11-dev                      # Development headers for C extensions
build-essential                     # C compiler for Cython/C extensions
```

### API Keys & Services (NEW)

| Service | Purpose | New Env Var |
|---------|---------|-------------|
| YouTube Analytics API | Deeper insights (watch time, retention) | `YOUTUBE_ANALYTICS_CREDENTIALS` |
| YouTube Data API v3 (write) | Auto-publishing | New OAuth scope |
| Google Fact Check Tools API | Fact verification | `FACT_CHECK_API_KEY` |
| HuggingFace Hub | Custom NER, emotion detection, diarization | `HUGGINGFACE_API_TOKEN` |
| Google/GitHub SSO | Web UI authentication | `GOOGLE_CLIENT_ID`, `GITHUB_CLIENT_ID` |
| TikTok API | Multi-platform publishing | `TIKTOK_API_KEY`, `TIKTOK_API_SECRET` |
| Instagram Graph API | Multi-platform publishing | `INSTAGRAM_API_KEY` |
| Twitter/X API v2 | Multi-platform publishing | `TWITTER_API_KEY`, `TWITTER_BEARER_TOKEN` |
| Coqui TTS Server | Custom voice creation | `TTS_SERVER_URL` |
| Wikidata/Fandom/Wikipedia APIs | Context import (free, no key) | — |

### Environment Variables (NEW)

```bash
# Pipeline
MAX_PARALLEL_PHASES=3
REDIS_URL=redis://localhost:6379/0
PIPELINE_TEMPLATES_DIR=~/.cogitator/templates
DRY_RUN=false

# Context
CONTEXT_VERSIONING=true
CONTEXT_MAX_VERSIONS=50
WIKI_IMPORT_ENABLED=true

# TTS
TTS_EMOTION=default
TTS_SPEED=1.0
TTS_SERVER_URL=http://localhost:5002
VOICE_CLONE_ENABLED=false

# Audio Analysis
SCENE_DETECTION_THRESHOLD=27.0
SCENE_MIN_LENGTH=150
SPEAKER_DIARIZATION_ENABLED=false

# YouTube
YOUTUBE_ANALYTICS_CREDENTIALS=~/.cogitator/youtube_analytics.json
AUTO_PUBLISH_ENABLED=false
AUTO_PUBLISH_PRIVACY=private

# Security
JWT_SECRET_KEY=
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
TWO_FACTOR_ENABLED=false
ENCRYPTION_KEY=
DATABASE_ENCRYPTION_ENABLED=false

# System
SYSTEM_MONITOR_ENABLED=true
LOG_LEVEL=INFO
LOG_ROTATION_SIZE_MB=10
UPDATE_CHANNEL=stable
CACHE_ENABLED=true
CACHE_TTL_SECONDS=300
```

### Infrastructure

| Item | Phase | Purpose |
|------|-------|---------|
| Redis | 1+ | Caching, session store, distributed pipeline |
| PostgreSQL | 2+ | Multi-user collaboration, audit logs (SQLite remains default) |
| Docker | 4 | Containerized deployment |
| Kubernetes | 4 | Scalable deployment |
| Cloud (AWS/GCP/Azure) | 4 | Hosting, storage, CDN |

### Dependencies by Phase

| Phase | Python | JS | System | APIs | Infra |
|-------|--------|-----|--------|------|-------|
| **1. Foundation** | pyyaml, loguru, psutil, cachetools | react-hotkeys-hook, immer, @radix-ui/* | redis-server | — | Redis |
| **2. Enhancement** | httpx, beautifulsoup4, pydub, Pillow, textstat, networkx, sentence-transformers | react-diff-viewer, @tanstack/react-table, @dnd-kit, @tiptap, @uiw/react-codemirror | ffmpeg (upgraded), portaudio19-dev, libsndfile1 | YouTube Analytics, Fact Check API | — |
| **3. Innovation** | coqui-tts, librosa, pyannote.audio, python-jose, passlib, pyotp, cryptography, strawberry-graphql | react-force-graph-3d, three, @react-three/fiber, html2canvas, react-i18next, vite-plugin-pwa | nvidia-cuda-toolkit, libva-dev | HuggingFace, Google/GitHub SSO | PostgreSQL |
| **4. Scale** | grpcio, redis, aiosqlite, python-telegram-bot | msw, playwright | docker.io, docker-compose, helm | TikTok, Instagram, Twitter/X APIs | Docker, K8s, Cloud |

---

## Open Questions

1. **Should we keep Telegram?** — User said "no use" but it's still optional
2. **Plugin system scope** — How extensible should we go?
3. **Cloud deployment** — Is self-hosting sufficient or do we need cloud?
4. **Multi-user** — Is this a single-user tool or collaborative?
5. **Pricing model** — Free forever or freemium?

---

## Next Steps

1. Review this plan with stakeholders
2. Prioritize Phase 1 tasks
3. Create detailed tickets for each task
4. Set up project board
5. Begin implementation

---

**Document Version:** 1.0  
**Created:** 2026-08-01  
**Status:** Draft — Ready for Review
