# Cogitator

**Automated YouTube Shorts Pipeline for Game Streams**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux-purple.svg)](https://archlinux.org/)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![React](https://img.shields.io/badge/React-18.2-blue)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)](https://fastapi.tiangolo.com)

---

## Table of Contents

1. [Overview](#overview)
2. [What is Cogitator?](#what-is-cogitator)
3. [Features](#features)
4. [Architecture](#architecture)
5. [System Requirements](#system-requirements)
6. [Installation](#installation)
7. [Configuration](#configuration)
 8. [Usage](#usage)
 9. [Web Interface](#web-interface)
 10. [Learning Engine](#learning-engine)
 11. [Metrics & Analytics](#metrics--analytics)
 12. [Project Structure](#project-structure)
 13. [Tech Stack](#tech-stack)
 14. [Security](#security)
 15. [Troubleshooting](#troubleshooting)
 16. [Development](#development)
 17. [License](#license)

---

## Overview

Cogitator is a comprehensive, AI-powered pipeline that transforms long-form YouTube game streams into ready-to-publish YouTube Shorts. It automates the entire content creation workflow from video download to final TTS-narrated clips with subtitles.

The project has evolved from a simple CLI script into a full-stack application with:
- **CLI Pipeline** - Command-line interface for batch processing
- **Web Interface** - React-based dashboard with real-time updates
- **Learning Engine** - ML-based content optimization
- **Performance Database** - SQLite-backed metrics tracking

---

## What is Cogitator?

Cogitator takes a YouTube playlist of game streams and automatically produces:

| Output | Description | Format |
|--------|-------------|--------|
| **Downloaded Videos** | Full videos from YouTube playlist | MP4 |
| **Transcripts** | Speech-to-text with timestamps | JSON + SRT |
| **AI Scripts** | Gemini AI-generated narration | TXT |
| **Video Clips** | Scene-based short segments | MP4 |
| **TTS Audio** | AI voice narration | WAV + SRT |

### Key Capabilities

- **7-Phase Pipeline**: Download → Transcribe → Context → Scripts → Clips → TTS → Assemble
- **Hardware-Accelerated Encoding**: Automatic GPU detection (NVENC/VA-API/QSV) with CPU fallback
- **Voice Customization**: TTS emotion styles and speed control
- **Learning Dashboard**: Insights, content effectiveness, A/B test tracking
- **Resumable**: Each phase saves progress - restart anywhere
- **Skippable Phases**: Run any combination of phases independently
- **WebSocket Log Streaming**: Live pipeline logs in browser
- **Real-time Metrics**: Track YouTube performance via API
- **ML Learning**: Optimize content based on historical performance

---

## Features

### Pipeline (7 Phases)

| Phase | Name | Description | Output |
|-------|------|-------------|--------|
| **1** | Download | Downloads videos from YouTube playlist / URL | `media/` |
| **2** | Transcribe | Faster-Whisper word-level transcription with timestamps | `transcripts/` |
| **3** | Context | Extracts characters, locations, relationships from transcript via LLM → `verified_context.json` + MemPalace | `Context/` |
| **4** | Scripts | Generates AI narration scripts (Groq primary / Gemini fallback) with title variety | `scripts/` |
| **5** | Clip | Scene detection, portrait 9:16 crop, highlight ranking | `shorts/` |
| **6** | TTS | Config-driven voice narration (Kokoro/Edge/Gemini) with subtitles + word-level timing | `tts/` |
| **7** | Assemble | Hardware-accelerated video assembly with subtitle overlay, BGM ducking | `assembly/` |

Orchestration is centralized in `workflows/pipeline/pipeline_runner.py` (checkpoints, resume, post-run YouTube sync + TikTok auto-import). The CLI (`workflows/cogitator.py`) delegates to it. Use `-phase 3,4` to run selected phases only.

Context is **JSON + MemPalace only** — the Obsidian markdown vault has been removed.

### Web Interface

- **Cyberpunk Dashboard**: React-based UI with real-time updates
- **Pipeline Control**: Start/stop/monitor pipeline from browser
- **Real-time Log Streaming**: WebSocket broadcasts live pipeline logs
- **Metrics Visualization**: Charts showing video performance
- **Context Graph**: Interactive knowledge graph with adjustable layout
- **WebSocket Support**: Live updates without refresh
- **Graph Visual Settings**: Configurable link distance, repulsion, collision for easy viewing
- **Graph Visual Themes**: 6 switchable themes (Star Chart, Brain Neurons, Digital Circuits, Hologram, Code Matrix, World Map)
- **Zoom-Based Labels**: Node labels appear only when zoomed in for clarity
- **Pipeline Progress Visualization**: 4 randomly-selected animated viz modules (Cogitator Array, Construction, Phase Timeline, Data Canvas) replaced inline progress bar

### Learning Engine

- **Performance Tracking**: Store and analyze video metrics
- **Feature Extraction**: NLP analysis of script content
- **Story Arc Detection**: Classifies clips into 4 arc types (hook_setup_payload_closer, mystery_reveal, problem_solution, setup_twist)
- **Retention Re-ranking**: Reorders clips by predicted audience retention
- **Curiosity Scoring**: Ranks clips based on narrative curiosity gaps
- **Thompson Sampling**: Optimize content type selection (70/30 explore/exploit)
- **Virality Prediction**: ML model predicting short performance
- **Content Type Analysis**: Compare performance by script style
- **YouTube Analytics Sync**: Auto-fetches metrics and retrains XGBoost model post-pipeline
- **Optimal Parameter Derivation**: Learns best duration, voices, styles from historical performance

### Highlight Ranking

- **LLM-based Virality Scoring**: Transcript segments scored 0-100 by Groq (Llama 3.3 70B) or Gemini
- **Sorted Top Segments**: Returns highest-scoring segments for clip extraction
- **Free-tier LLM**: No-cost inference via Groq with Gemini fallback

### Scene Detection

- **PySceneDetect Integration**: Content-aware scene boundary detection (CPU-based, no GPU needed)
- **Motion Scoring**: FFmpeg-derived action scores for ranking scenes
- **Uniform Fallback**: Even segment distribution when detection fails

### Game Lore

Optional lore may exist inside `verified_context.json` and is injected into script prompts when present. There is no separate live “Phase 3a lore fetch” — transcript extraction is the source of truth for Phase 3.

### Metrics System

- **YouTube API Integration**: Fetch views, likes, comments
- **OAuth Support**: Authenticated access for channel data
- **Auto-matching**: Link YouTube shorts to source scripts by exact title, substring, or word-overlap scoring
- **Auto-sync**: Periodic sync updates metrics for all known Shorts; new Shorts auto-matched to scripts
- **Performance Scores**: Calculate engagement metrics
- **Learning Data**: Store content type performance for optimization

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Cogitator                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│  │   Web UI     │    │   CLI        │    │   Pipeline   │    │
│  │  (React)     │    │   Runner     │    │   Runner     │    │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘    │
│         │                   │                   │             │
│         └───────────────────┴───────────────────┘             │
│                             │                                   │
│                    ┌────────▼────────┐                        │
│                    │   FastAPI       │                        │
│                    │   Backend       │                        │
│                    └────────┬────────┘                        │
│                             │                                   │
│  ┌─────────────────────────┼─────────────────────────────┐   │
│  │                    Workflows                            │   │
│  ├──────────────┬──────────┼──────────┬──────────────┬────┤   │
│  │ cogitator   │ context  │ metrics  │ learning     │ other│
│  │ .py           │ _manager │ _fetcher │ _engine      │ .py │
│  └──────┬────────┴──────────┴──────────┴──────┬──────┘   │
│         │                                       │             │
│         └───────────────┬───────────────────────┘             │
│                         │                                       │
│              ┌──────────▼──────────┐                          │
│              │  SQLite Database    │                          │
│              │  (Performance DB)   │                          │
│              └─────────────────────┘                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Component Descriptions

| Component | Purpose |
|-----------|---------|
| `cogitator.py` | Main pipeline orchestration, CLI |
| `context_manager.py` | Context storage and retrieval for scripts |
| `context_manager_v2.py` | Enhanced context with graph visualization, deterministic entity IDs, and string relationship parsing |
| `metrics_fetcher.py` | YouTube API integration for video metrics |
| `learning_engine.py` | ML-based performance prediction and optimization (includes YouTube analytics sync) |
| `performance_database.py` | SQLite storage for scripts, videos, metrics, learnings |
| `script_validation.py` | Script quality scoring and content type detection |
| `audio_analysis.py` | Audio feature extraction + PySceneDetect scene detection + motion scoring |
| `keychain_manager.py` | Secure API key storage in system keychain |
| `constants.py` | Centralized configuration (voices, styles, scoring, rotation) |
| `pipeline/__init__.py` | Lazy-loaded pipeline phase stubs (import-chain safe) |
| `pipeline/pipeline_runner.py` | Pipeline orchestrator with auto YouTube sync after run |
| `pipeline/phase_tts.py` | Config-driven TTS dispatch (Kokoro / Edge / Gemini) |
| `pipeline/phase_tts_kokoro.py` | Kokoro TTS provider (CPU-based, free, offline) |
| `pipeline/phase_assemble.py` | Video assembly with subtitles and BGM |
| `pipeline/srt_utils.py` | Shared subtitle timing utilities |
| `backend/main.py` | FastAPI web server with REST API |
| `core/round_robin.py` | Shuffled round-robin engine for voice/style/Groq rotation |
| `core/pipeline_context.py` | Shared pipeline state for cross-phase coordination |

---

## System Requirements

### Hardware

- **CPU**: Multi-core (4+ cores recommended)
- **RAM**: 8GB+ (16GB recommended for video processing)
- **Storage**: 50GB+ for video processing
- **GPU**: Optional (for faster video encoding; AMD VA-API supported)

### Software

| Requirement | Version | Purpose |
|-------------|---------|---------|
| **Python** | 3.11+ | Runtime |
| **FFmpeg** | Latest | Video processing |
| **Git** | Latest | Version control |
| **Node.js** | 18+ | Frontend build (optional) |

### API Keys

| Service | Required | Purpose |
|---------|----------|---------|
| **Google Gemini** | Yes | Script generation |
| **Groq** | Recommended | Highlight ranking + Gemini fallback (free tier via Llama 3.3 70B) |
| **YouTube Data API** | Yes | Video metrics |

> **TTS Note**: Gemini API is no longer required for TTS. Set `TTS_PROVIDER=kokoro` (CPU, free, offline) or `TTS_PROVIDER=edge` (free cloud via edge-tts) to avoid TTS API costs.

---

## Installation

You can use the automated `install.sh` script or follow the manual steps below.

### 1. Clone Repository

```bash
git clone https://github.com/judecabodil22/Cogitator.git
cd Cogitator
```

### 2. Install System Dependencies

**Arch Linux:**
```bash
sudo pacman -S ffmpeg python python-pip git
```

**Ubuntu/Debian:**
```bash
sudo apt install ffmpeg python3 python3-pip git
```

### 3. Set Up Python Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
nano .env
```

### 5. Start Using Cogitator

**Option A: Web Interface**
```bash
# Start backend
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Frontend is pre-built in frontend/dist/
# Access at http://localhost:8000
```

**Option B: Direct CLI**
```bash
python workflows/cogitator.py run
python workflows/cogitator.py status
```

---

## Configuration

All configuration is in the `.env` file:

### Required Variables

```bash
# YouTube
PLAYLIST_URL=https://youtube.com/playlist?list=...

# AI
GEMINI_API_KEY=AIzaSy...
```

### Optional Variables

```bash
# AI Fallback (used when Gemini is unavailable, also for highlight ranking)
GROQ_API_KEY=gsk_...

# TTS Provider: "gemini" (API), "kokoro" (CPU/free/offline), or "edge" (free cloud)
# Kokoro recommended — zero API cost, 54 voices, offline after first download
TTS_PROVIDER=kokoro

# Content Settings
GAME_TITLE=Rise of the Tomb Raider
TTS_VOICE=Vindemiatrix
CLIPS_PER_HOUR=5

# Advanced
SRT_MAX_WORDS=10
PLAYLIST_INDEX=1
WHISPER_MODEL=medium
```

### Getting API Keys

**Google Gemini API Key:**
1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Copy to `.env`

**YouTube Data API:**
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create project and enable YouTube Data API v3
3. Create credentials (API Key)
4. For full metrics, set up OAuth 2.0

---

## Usage

### Running the Pipeline

```bash
# Full pipeline (all 7 phases)
python workflows/cogitator.py run

# Specific phases
python workflows/cogitator.py run --phase 3
python workflows/cogitator.py run --phase 1,2,3

# Local video processing
python workflows/cogitator.py run_local media
```

### Pipeline Commands

```bash
python workflows/cogitator.py run         # Run pipeline
python workflows/cogitator.py status      # Show status
python workflows/cogitator.py cleanup     # Clean generated files
python workflows/cogitator.py debug       # Show recent logs
python workflows/cogitator.py onboard     # Interactive setup
```

---

## Web Interface

### Starting the Web Server

```bash
# Backend only
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Or use the script
./start_web.sh
```

### Accessing the UI

Open `http://localhost:8000` in your browser.

### Features

- **Dashboard**: Metrics summary
- **Pipeline Control**: Start, stop, configure pipeline
- **Metrics**: Video performance charts
- **Scripts**: View generated scripts
- **Context**: Interactive knowledge graph visualization
- **Settings**: Configuration management
- **Command Palette**: Global search/navigation (Cmd+K)
- **Real-time Updates**: WebSocket live status and logs

### Knowledge Graph

The Context page features an interactive force-directed graph:

- **Node Types**: Characters (gold), Locations (amber), Key Terms (yellow), Relationships (red), Games (burgundy) - themed by visual style
- **Edge Types**:
  - **Context** (solid): Explicit relationships from `verified_context.json` — parsed from structured `{from, to, relationship}` dicts or legacy `"X and Y are Z"` strings
  - **Implicit** (dashed): Co-occurrence connections derived from MemPalace narrative chunks and transcript files — entities mentioned together in the same text segment
- **Data Sources**:
  - `Context/verified_context.json` — nodes (characters, locations, terms) and direct relationship edges
  - MemPalace ChromaDB (`~/.mempalace/palace/chroma.sqlite3`) — narrative chunks for co-occurrence edge generation
  - `transcripts/*.json` — transcript files for co-occurrence (optional, MemPalace is the primary source)
- **Visual Themes**: Switch between 6 themes via the Settings panel:
  - **Star Chart** (default): Classic gold/red 40k color scheme
  - **Brain Neurons**: Purple gradient circles with neural pulse animations
  - **Digital Circuits**: Green circuit board squares with connection dots
  - **Hologram**: Cyan holographic style with scan line effects
  - **Code Matrix**: Terminal green with cursor blinking animation
  - **World Map**: Map pin style for location entities
- **Theme Physics**: Each theme has unique physics presets (link distance, charge strength, velocity decay)
- **Visual Settings**: Click the gear icon to adjust:
  - **Visual Theme**: Theme selector with preview icons
  - **Link Distance**: How far nodes are pulled together (50-500)
  - **Link Strength**: Edge pull force (0-2)
  - **Repulsion**: Node separation force (-2000 to -50)
  - **Collision Radius**: Minimum node distance (1-150)
  - **Center Force**: How compact the graph is (0-1)
- **Zoom Labels**: Labels only appear when zoomed in past 0.7x for clarity
- **Interactive**: Click nodes for details, drag to rearrange, zoom to explore
- **Persistent Data**: Implicit co-occurrence relationships are stored in `verified_context.json` — deleting transcripts doesn't lose previously computed edges
- **Auto-Placeholder Nodes**: Entities referenced in relationships but missing as graph nodes are auto-created as placeholders
- **Franchise Merging**: Selecting a franchise (e.g. "Star Wars") merges characters and relationships from all child games (e.g. "Jedi Survivor")

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/status` | GET | System status |
| `/api/pipeline/run` | POST | Start pipeline |
| `/api/pipeline/stop` | POST | Stop pipeline |
| `/api/pipeline/settings` | GET/POST | Pipeline settings |
| `/api/pipeline/logs` | GET | Pipeline execution logs |
| `/api/metrics/summary` | GET | Performance summary |
| `/api/metrics/videos` | GET | All videos with metrics |
| `/api/metrics/sync` | POST | Sync YouTube metrics |
| `/api/metrics/content-performance` | GET | Content type performance |
| `/api/scripts` | GET | All scripts |
| `/api/scripts/{id}` | GET | Get script by ID |
| `/api/scripts/{id}/metadata` | GET | Get script metadata |
| `/api/scripts/{id}/analyze` | POST | Analyze script |
| `/api/learnings` | GET | ML learnings |
| `/api/learnings/weights` | GET | Content type weights |
| `/api/context/{game}` | GET | Game context |
| `/api/context/{game}/graph` | GET | Game knowledge graph |
| `/api/context/{game}/segments` | GET | Game segments |
| `/api/context/all/graph` | GET | All games combined graph |
| `/api/context/games` | GET | List all games |
| `/api/context/create_game` | POST | Create new game context |
| `/api/context/merge` | POST | Merge contexts |
| `/api/context/import` | POST | Import context |
| `/api/tts/voices` | GET | List TTS voices |
| `/api/tts/learnings` | GET | TTS learnings |
| `/api/prompts/script` | GET/PUT | Script prompt template |
| `/api/auth/key` | GET | API key status |
| `/api/config` | GET/POST | Configuration |
| `/ws` | WS | WebSocket for real-time updates (status + log streaming) |

---

## Learning Engine

The Learning Engine optimizes content creation based on historical performance.

### Components

**Performance Database (SQLite)**
- Scripts with NLP features
- Video metrics (views, likes, comments)
- Content type performance
- TTS voice effectiveness

**Feature Extraction**
- Script text analysis
- Content type classification
- Engagement prediction
- Word count patterns

**Thompson Sampling**
- 70% exploitation (best performing)
- 30% exploration (new content types)
- Balances optimization with discovery

**Virality Prediction**
- ML model trained on historical data
- Predicts likely performance before publishing
- Feature-based scoring

### Usage

```python
from workflows.learning_engine import extract_script_features, get_virality_predictor

# Extract features from script
features = extract_script_features(script_text, content_type)

# Get prediction
predictor = get_virality_predictor()
prediction = predictor.predict(features)
```

---

## Metrics & Analytics

### YouTube Metrics

Cogitator tracks:
- **Views**: Total video views
- **Likes**: Total likes
- **Comments**: Total comments
- **Engagement Ratio**: (likes + comments) / views * 100

### Auto-Matching

The system matches YouTube shorts to source scripts by:
1. Reading `TITLE:` from script files
2. Comparing with YouTube video titles
3. Scoring word overlap
4. Linking when score >= 0.3

### Performance Analysis

```python
from workflows.performance_database import get_variant_performance_stats

stats = get_variant_performance_stats()
# Returns: {content_type: {views, likes, comments, count, avg_engagement}}
```

---

## Project Structure

```
Cogitator/
├── backend/                    # FastAPI web backend
│   ├── main.py                # API server
│   └── requirements.txt      # Backend dependencies
├── frontend/                   # React web interface
│   ├── src/                   # React source
│   └── dist/                 # Pre-built static files
├── workflows/                  # Core pipeline modules
│   ├── cogitator.py        # Main application
│   ├── constants.py          # Centralized configuration
│   ├── context_manager.py    # Context storage v1
│   ├── context_manager_v2.py # Context storage v2 (graph)
│   ├── metrics_fetcher.py   # YouTube API integration
│   ├── learning_engine.py   # ML optimization
│   ├── performance_database.py # SQLite storage
│   ├── script_validation.py # Script quality scoring
│   ├── audio_analysis.py    # Audio feature extraction
│   ├── context_extractor.py # Context extraction
│   ├── keychain_manager.py  # Secure key storage
│   ├── update_manager.py    # Update checking
│   ├── core/                # Extracted core modules
│   │   ├── round_robin.py  # Round-robin engine
│   │   └── pipeline_context.py # Pipeline state
│   ├── pipeline/            # Pipeline phases
│   │   ├── pipeline_runner.py # Pipeline orchestrator
│   │   ├── phase_tts.py    # TTS dispatch
│   │   ├── phase_tts_kokoro.py # Kokoro TTS provider
│   │   ├── phase_assemble.py # Video assembly
│   │   └── srt_utils.py    # Subtitle utilities
├── prompts/                   # AI prompt templates
│   ├── base.j2               # Base prompt
│   ├── content_studio.j2     # Content Studio prompt
│   └── *.j2                  # Other styles
├── docs/                      # Documentation
├── scripts/                   # Generated scripts
├── shorts/                   # Generated clips
├── tts/                      # Generated TTS audio
├── transcripts/              # Generated transcripts
├── streams/                  # Downloaded videos
├── Context/                  # Game context files
├── assembly/                 # Assembled videos
├── .cogitator/            # App data (OAuth, DB, API key)
├── .env.example             # Configuration template
├── requirements.txt         # Python dependencies
├── VERSION                  # Version file
├── CHANGELOG.md             # Version history
├── SECURITY.md              # Security policy
├── README.md                # This file
└── LICENSE                  # MIT License
```

### Generated Output Directories

| Directory | Contents |
|-----------|----------|
| `streams/` | Downloaded YouTube videos |
| `transcripts/` | JSON + SRT transcripts |
| `scripts/` | AI-generated scripts with TITLE |
| `shorts/` | Extracted video clips |
| `tts/` | TTS audio + SRT subtitles |
| `assembly/` | Assembled videos with subtitles and BGM |

---

## Tech Stack

### Core Technologies

| Component | Technology | Version |
|-----------|------------|---------|
| **Language** | Python | 3.11+ |
| **Web Framework** | FastAPI | 0.109+ |
| **Web Server** | Uvicorn | 0.27+ |
| **Frontend** | React | 18.2.0 |
| **Frontend Build** | Vite | 5.1.0 |
| **UI Components** | Radix UI | Latest |
| **Database** | SQLite | 3.x |
| **Video Processing** | FFmpeg | Latest |

### AI & APIs

| Service | Purpose | Integration |
|---------|---------|-------------|
| **Google Gemini** | Script generation + TTS fallback | API |
| **Groq (Llama 3.3 70B)** | Highlight ranking + Gemini fallback | API (free tier) |
| **Kokoro TTS** | CPU-based voice synthesis (free, offline) | Local model |
| **Edge TTS** | Microsoft cloud voice synthesis (free) | edge-tts |
| **YouTube Data API** | Video metrics | API + OAuth |
| **YouTube Data API** | Video downloading | yt-dlp |

### Speech & Audio

| Technology | Purpose |
|------------|---------|
| **Faster-Whisper** | Speech-to-text |
| **stable-ts** | Alternative STT |
| **Kokoro TTS** | CPU-based TTS (free, offline, 54 voices) |
| **Edge TTS** | Microsoft cloud TTS (free, `edge-tts`) |
| **PySceneDetect** | Content-aware scene boundary detection |

### ML & Data Science

| Technology | Purpose |
|------------|---------|
| **XGBoost** | Virality prediction |
| **Thompson Sampling** | Content selection |

---

## Security

### API Key Management

Cogitator supports secure API key storage via `keychain_manager.py`:

1. **System Keychain** (Recommended)
   - Linux: GNOME Keyring / KWallet
   - macOS: Keychain Access
   - Windows: Credential Manager

2. **Environment Variables** (For servers)
   - `.env` file (gitignored)

### Web Interface Security

- **API Key Authentication**: Protected endpoints require `X-API-Key` header (not URL params)
- **Rate Limiting**: Prevents abuse (5-60 requests/minute depending on endpoint)
- **Security Headers**: X-Frame-Options, X-XSS-Protection, HSTS, Referrer-Policy
- **Input Sanitization**: Prevents injection attacks
- **CORS**: Restricted to localhost

### Protected Endpoints

These endpoints require API key authentication (sent via `X-API-Key` header, not URL params):
- `GET /api/status` - Get system status
- `POST /api/pipeline/run` - Start pipeline
- `POST /api/pipeline/stop` - Stop pipeline
- `GET /api/pipeline/settings` - Get pipeline settings
- `POST /api/pipeline/settings` - Save pipeline settings
- `GET /api/pipeline/logs` - Get pipeline logs
- `GET /api/metrics/summary` - Get performance summary
- `GET /api/metrics/videos` - Get all videos with metrics
- `GET /api/metrics/content-performance` - Get content type performance
- `POST /api/metrics/sync` - Sync YouTube metrics
- `GET /api/metrics/tiktok/summary` - Get TikTok summary
- `GET /api/metrics/tiktok/videos` - Get TikTok videos
- `GET /api/metrics/tiktok/daily` - Get TikTok daily trends
- `GET /api/metrics/tiktok/games` - Get TikTok per-game stats
- `GET /api/metrics/tiktok/comparison` - Get TikTok comparison
- `POST /api/metrics/tiktok/import` - Import TikTok data
- `POST /api/metrics/tiktok/match` - Match TikTok to local
- `GET /api/metrics/cross-platform` - Get cross-platform stats
- `GET /api/scripts` - Get all scripts
- `GET /api/scripts/{script_id}` - Get script details
- `GET /api/scripts/{script_id}/metadata` - Get script metadata
- `POST /api/scripts/{id}/analyze` - Analyze script
- `GET /api/learnings` - Get all learnings
- `GET /api/learnings/weights` - Get content type weights
- `GET /api/context/games` - Get all game contexts
- `GET /api/context/{game}` - Get game context items
- `PUT /api/context/{game}/{item_type}/{item_id}` - Update context item
- `DELETE /api/context/{game}/{item_type}/{item_id}` - Delete context item
- `GET /api/context/all/graph` - Get all-games graph
- `GET /api/context/{game}/graph` - Get single-game graph
- `GET /api/context/{game}/graph/search` - Search graph entities
- `GET /api/context/{game}/graph/stats` - Get graph statistics
- `GET /api/context/{game}/segments` - Get segment references
- `GET /api/prompts/script` - Get script prompt template
- `PUT /api/prompts/script` - Save script prompt
- `GET /api/tts/voices` - Get TTS voices
- `GET /api/tts/learnings` - Get TTS learnings
- `GET /api/learning/dashboard` - Get learning dashboard
- `GET /api/learning/tiktok-signals` - Get TikTok signals
- `POST /api/learning/ab-test` - Create A/B test
- `POST /api/learning/ab-test/{test_id}/result` - Record A/B test result
- `GET /api/learning/ab-test/{test_id}` - Get A/B test results
- `GET /api/learning/ab-tests` - Get all A/B tests
- `GET /api/learning/ab-current` - Get current A/B test
- `GET /api/config` - Get configuration
- `POST /api/config` - Update configuration
- `POST /api/pipeline/download` - Download from URL
- `GET /api/logs` - Get application logs
- `POST /api/system/cleanup` - Cleanup files
- `POST /api/context/import` - Import context
- `POST /api/context/create_game` - Create game context
- `POST /api/context/clear` - Clear context
- `POST /api/context/merge` - Merge context
- `DELETE /api/context/{game}` - Delete game context

Path traversal protections are enforced on all file-related endpoints. Thread-safe locking ensures database integrity during concurrent pipeline operations.

### Best Practices

1. **Never commit secrets** - `.env` and `client_secret.json` are gitignored
2. **Use HTTPS** - In production, use reverse proxy with TLS
3. **Restrict access** - Firewall rules for web interface
4. **Rotate keys** - Periodically update API keys
5. **Review SECURITY.md** - See `SECURITY.md` for full details

---

## Troubleshooting

### Common Issues

**Q: Pipeline won't start**
- Check `.env` has valid `GEMINI_API_KEY`
- Run `python workflows/cogitator.py onboard` to verify

**Q: No videos downloading**
- Verify `PLAYLIST_URL` in `.env`
- Check YouTube playlist is public

**Q: TTS not generating**
- Check `TTS_PROVIDER` is set correctly (kokoro/edge/gemini)
- If `TTS_PROVIDER=kokoro`, first run downloads the model (~500MB) — may take a minute
- If `TTS_PROVIDER=gemini`, ensure `TTS_VOICE` is valid and API key has quota
- If `TTS_PROVIDER=edge`, ensure `edge-tts` is installed (`pip install edge-tts`)

**Q: Metrics sync not working**
- Verify YouTube OAuth is configured (`client_secret.json` in workspace)
- Check video duration (must be < 3 minutes to be treated as Short)
- Ensure the Short exists on YouTube and appears in recent uploads
- Run sync via API: `curl -X POST http://localhost:8000/api/metrics/sync -H "X-API-Key: YOUR_KEY"`
- Check the database: stored YouTube IDs must match actual YouTube video IDs

**Q: Scene detection produces poor cuts**
- PySceneDetect is CPU-based and content-aware — try different content types (videos with clear scene changes work best)
- Falls back to uniform segments if detection fails
- Verify FFmpeg is installed and up to date

### Debug Mode

```bash
# View recent logs
python workflows/cogitator.py debug

# Check pipeline status
python workflows/cogitator.py status

# Verbose output
python workflows/cogitator.py run --verbose
```

---

## Development

### Adding New Features

1. **Script Styles**: Add new `.j2` template in `prompts/`
2. **TTS Voices**: Update voice list in `workflows/constants.py`
3. **API Endpoints**: Add route in `backend/main.py`
4. **Metrics**: Add tracking in `performance_database.py`

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest
```

### Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Run tests
5. Submit pull request

---

## Version History

See [CHANGELOG.md](./CHANGELOG.md) for detailed version history.

Current version: **2.5.1**

---

## License

This project is licensed under the MIT License.

See [LICENSE](./LICENSE) for full details.

---

## Support

- **Issues**: Open a GitHub issue
- **Discussions**: Use GitHub Discussions
- **Documentation**: Check `docs/` folder

---

**Cogitator** — Turn your game streams into YouTube Shorts automatically.

Built with FastAPI, React, Python, and Google Gemini AI.