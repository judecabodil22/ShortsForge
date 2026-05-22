# ShortsForge

**Automated YouTube Shorts Pipeline for Game Streams**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux-purple.svg)](https://archlinux.org/)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![React](https://img.shields.io/badge/React-18.2-blue)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)](https://fastapi.tiangolo.com)

---

## Table of Contents

1. [Overview](#overview)
2. [What is ShortsForge?](#what-is-shortsforge)
3. [Features](#features)
4. [Architecture](#architecture)
5. [System Requirements](#system-requirements)
6. [Installation](#installation)
7. [Configuration](#configuration)
8. [Usage](#usage)
9. [Telegram Commands](#telegram-commands)
10. [Web Interface](#web-interface)
11. [Content Studio](#content-studio)
12. [Learning Engine](#learning-engine)
13. [Metrics & Analytics](#metrics--analytics)
14. [Project Structure](#project-structure)
15. [Tech Stack](#tech-stack)
16. [Security](#security)
17. [Troubleshooting](#troubleshooting)
18. [Development](#development)
19. [License](#license)

---

## Overview

ShortsForge is a comprehensive, AI-powered pipeline that transforms long-form YouTube game streams into ready-to-publish YouTube Shorts. It automates the entire content creation workflow from video download to final TTS-narrated clips with subtitles.

The project has evolved from a simple CLI script into a full-stack application with:
- **CLI Pipeline** - Command-line interface for batch processing
- **Telegram Bot** - Interactive bot control and monitoring
- **Web Interface** - React-based dashboard with real-time updates
- **Learning Engine** - ML-based content optimization
- **Performance Database** - SQLite-backed metrics tracking

---

## What is ShortsForge?

ShortsForge takes a YouTube playlist of game streams and automatically produces:

| Output | Description | Format |
|--------|-------------|--------|
| **Downloaded Videos** | Full videos from YouTube playlist | MP4 |
| **Transcripts** | Speech-to-text with timestamps | JSON + SRT |
| **AI Scripts** | Gemini AI-generated narration | TXT |
| **Video Clips** | Scene-based short segments | MP4 |
| **TTS Audio** | AI voice narration | WAV + SRT |

### Key Capabilities

- **6-Phase Pipeline**: Download → Transcribe → Context → Script → Clip → TTS
- **Resumable**: Each phase saves progress - restart anywhere
- **Skippable Phases**: Run any combination of phases independently
- **WebSocket Log Streaming**: Live pipeline logs in browser
- **Content Studio**: Generate additional content from existing transcripts
- **Real-time Metrics**: Track YouTube performance via API
- **ML Learning**: Optimize content based on historical performance

---

## Features

### Pipeline (6 Phases)

| Phase | Name | Description | Output |
|-------|------|-------------|--------|
| **1** | Download | Downloads videos from YouTube playlist | `streams/` |
| **2** | Transcribe | Converts audio to text with timestamps | `transcripts/` |
| **3** | Context | Extracts characters, locations, relationships | `Context/` |
| **4** | Scripts | Generates AI-powered narration scripts | `scripts/` |
| **5** | Clip | Extracts video clips based on scene detection | `shorts/` |
| **6** | TTS | Creates AI voice narration with subtitles | `tts/` |

### Content Studio

- **Import Pipeline Data**: Copy transcripts from main pipeline
- **Generate Scripts**: Create AI scripts with context awareness
- **Generate TTS**: Convert scripts to voice narration
- **Series Continuity**: Context accumulates across runs
- **Context Memory**: Characters, locations, relationships tracked

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

### Learning Engine

- **Performance Tracking**: Store and analyze video metrics
- **Feature Extraction**: NLP analysis of script content
- **Thompson Sampling**: Optimize content type selection (70/30 explore/exploit)
- **Virality Prediction**: ML model predicting short performance
- **Content Type Analysis**: Compare performance by script style

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
│                        ShortsForge                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│  │   Telegram   │    │   Web UI     │    │     CLI      │    │
│  │     Bot       │    │   (React)    │    │   Pipeline   │    │
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
│  │ shortsforge   │ context  │ metrics  │ learning     │ other│
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
| `shortsforge.py` | Main pipeline orchestration, CLI, Telegram bot |
| `context_manager.py` | Context storage and retrieval for scripts |
| `context_manager_v2.py` | Enhanced context with graph visualization |
| `metrics_fetcher.py` | YouTube API integration for video metrics |
| `learning_engine.py` | ML-based performance prediction and optimization |
| `performance_database.py` | SQLite storage for scripts, videos, metrics, learnings |
| `script_validation.py` | Script quality scoring and content type detection |
| `audio_analysis.py` | Audio feature extraction for clip selection |
| `keychain_manager.py` | Secure API key storage in system keychain |
| `constants.py` | Centralized configuration (voices, styles, scoring, rotation) |
| `content_studio.py` | Content Studio orchestration facade |
| `backend/main.py` | FastAPI web server with REST API |
| `core/round_robin.py` | Shuffled round-robin engine for voice/style/Groq rotation |
| `core/config.py` | `.env` file management utilities |
| `core/pipeline_context.py` | Shared pipeline state for cross-phase coordination |

---

## System Requirements

### Hardware

- **CPU**: Multi-core (4+ cores recommended)
- **RAM**: 8GB+ (16GB recommended for video processing)
- **Storage**: 50GB+ for video processing
- **GPU**: Optional (for faster video encoding)

### Software

| Requirement | Version | Purpose |
|-------------|---------|---------|
| **Python** | 3.10+ | Runtime |
| **FFmpeg** | Latest | Video processing |
| **Git** | Latest | Version control |
| **Node.js** | 18+ | Frontend build (optional) |

### API Keys

| Service | Required | Purpose |
|---------|----------|---------|
| **Google Gemini** | Yes | Script generation + TTS |
| **YouTube Data API** | Yes | Video metrics |
| **Telegram Bot** | Optional | Bot control |

---

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/judecabodil22/ShortsForge.git
cd ShortsForge
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

### 5. Start Using ShortsForge

**Option A: Telegram Bot**
```bash
python workflows/shortsforge.py listen
```

**Option B: Web Interface**
```bash
# Start backend
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Frontend is pre-built in frontend/dist/
# Access at http://localhost:8000
```

**Option C: Direct CLI**
```bash
python workflows/shortsforge.py run
python workflows/shortsforge.py status
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
# Telegram Bot
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHAT_ID=123456789

# Content Settings
GAME_TITLE=Rise of the Tomb Raider
TTS_VOICE=Vindemiatrix
CLIPS_PER_HOUR=5

# Advanced
SRT_MAX_WORDS=10
PLAYLIST_INDEX=1
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

**Telegram Bot:**
1. Open @BotFather on Telegram
2. Create new bot with `/newbot`
3. Copy token to `.env`
4. Get chat ID from @userinfobot

---

## Usage

### Running the Pipeline

```bash
# Full pipeline (all 5 phases)
python workflows/shortsforge.py run

# Specific phases
python workflows/shortsforge.py run --phase 3
python workflows/shortsforge.py run --phase 1,2,3

# Local video processing
python workflows/shortsforge.py run_local media
```

### Pipeline Commands

```bash
python workflows/shortsforge.py run         # Run pipeline
python workflows/shortsforge.py listen       # Start Telegram listener
python workflows/shortsforge.py stop        # Stop running pipeline
python workflows/shortsforge.py status      # Show status
python workflows/shortsforge.py cleanup      # Clean generated files
python workflows/shortsforge.py debug       # Show recent logs
python workflows/shortsforge.py onboard     # Interactive setup
```

---

## Telegram Commands

### Pipeline Control

| Command | Description |
|---------|-------------|
| `/start` | Initialize bot |
| `/run` | Run full pipeline |
| `/run_phase N` | Run specific phase |
| `/skip_phase N` | Skip a phase |
| `/stop_pipeline` | Stop running pipeline |
| `/status` | Show current status |

### Configuration

| Command | Description |
|---------|-------------|
| `/set_voice Puck` | Change TTS voice |
| `/voices` | List available voices |
| `/set_clips 10` | Set clips per hour (1-20) |
| `/set_game Game Title` | Set game title |
| `/config` | Show current settings |

### Content Studio

| Command | Description |
|---------|-------------|
| `/cs` | Open Content Studio |
| `/cs_generate` | Generate script |
| `/cs_tts` | Generate TTS |
| `/cs_context` | View context |

### Utilities

| Command | Description |
|---------|-------------|
| `/menu` | Show interactive menu |
| `/debug` | Show recent logs |
| `/version` | Show version |
| `/cleanup` | Delete generated files |
| `/help` | Show help |

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

- **Dashboard**: Pipeline status, metrics summary
- **Pipeline Control**: Start, stop, configure pipeline
- **Metrics**: Video performance charts
- **Scripts**: View generated scripts
- **Context**: Interactive knowledge graph visualization
- **Settings**: Configuration management

### Knowledge Graph

The Context page features an interactive force-directed graph:

- **Node Types**: Characters (gold), Locations (amber), Key Terms (yellow), Relationships (red), Games (burgundy) - themed by visual style
- **Edge Types**:
  - **Explicit** (solid): Direct connections from relationships
  - **Direct** (solid): Entity-to-entity connections from shared relationships
  - **Implicit** (dashed): Co-occurrence connections from transcripts (stored persistently)
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
- **Persistent Data**: Implicit co-occurrence relationships are stored in verified_context.json - deleting transcripts doesn't affect the graph
- **Auto-Placeholder Nodes**: Entities referenced in relationships but missing as graph nodes are auto-created as placeholders
- **Franchise Merging**: Selecting a franchise (e.g. "Tomb Raider Series") merges characters and relationships from all child games

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/status` | GET | System status |
| `/api/pipeline/run` | POST | Start pipeline |
| `/api/pipeline/stop` | POST | Stop pipeline |
| `/api/pipeline/settings` | GET/POST | Pipeline settings |
| `/api/metrics/summary` | GET | Performance summary |
| `/api/metrics/videos` | GET | All videos with metrics |
| `/api/metrics/sync` | POST | Sync YouTube metrics |
| `/api/metrics/content-performance` | GET | Content type performance |
| `/api/scripts` | GET | All scripts |
| `/api/learnings` | GET | ML learnings |
| `/api/context/{game}` | GET | Game context |
| `/api/context/{game}/graph` | GET | Game knowledge graph |
| `/api/context/all/graph` | GET | All games combined graph |
| `/api/config` | GET/POST | Configuration |
| `/ws` | WS | WebSocket for real-time updates (status + log streaming) |

---

## Content Studio

Content Studio generates additional content from existing transcripts.

### Access

Send `/cs` to your Telegram bot.

### Workflow

1. **Import**: Copy transcripts from main pipeline
2. **Analyze**: Extract characters, locations, terms
3. **Generate**: Create scripts with context awareness
4. **TTS**: Convert scripts to voice narration

### Context Memory

Content Studio maintains context across runs:
- Character names and descriptions
- Location names
- Key terms and plot points
- Relationships between entities
- Previous script summaries

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

ShortsForge tracks:
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
ShortsForge/
├── backend/                    # FastAPI web backend
│   ├── main.py                # API server
│   └── requirements.txt      # Backend dependencies
├── frontend/                   # React web interface
│   ├── src/                   # React source
│   └── dist/                 # Pre-built static files
├── workflows/                  # Core pipeline modules
│   ├── shortsforge.py        # Main application
│   ├── constants.py          # Centralized configuration
│   ├── content_studio.py     # Content Studio facade
│   ├── context_manager.py    # Context storage v1
│   ├── context_manager_v2.py # Context storage v2 (graph)
│   ├── metrics_fetcher.py   # YouTube API integration
│   ├── learning_engine.py   # ML optimization
│   ├── performance_database.py # SQLite storage
│   ├── script_validation.py # Script quality scoring
│   ├── audio_analysis.py    # Audio feature extraction
│   ├── keychain_manager.py  # Secure key storage
│   ├── update_manager.py    # Update checking
│   ├── core/                # Extracted core modules
│   │   ├── round_robin.py  # Round-robin engine
│   │   ├── config.py       # Env file management
│   │   └── pipeline_context.py # Pipeline state
│   ├── pipeline/            # Pipeline phase stubs
│   ├── generators/          # Generator stubs
│   └── telegram/            # Telegram bot stubs
├── prompts/                   # AI prompt templates
│   ├── base.j2               # Base prompt
│   ├── character_pov.j2      # Character POV style
│   ├── narrative.j2          # Narrative style
│   └── *.j2                  # Other styles (11 total)
├── docs/                      # Documentation
├── scripts/                   # Generated scripts
├── shorts/                   # Generated clips
├── tts/                      # Generated TTS audio
├── transcripts/              # Generated transcripts
├── streams/                  # Downloaded videos
├── Context/                  # Game context files
├── .shortsforge/            # App data (OAuth, DB, API key)
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

---

## Tech Stack

### Core Technologies

| Component | Technology | Version |
|-----------|------------|---------|
| **Language** | Python | 3.10+ |
| **Web Framework** | FastAPI | 0.109+ |
| **Web Server** | Uvicorn | 0.27+ |
| **Frontend** | React | 18.2.0 |
| **Frontend Build** | Vite | 5.1.0 |
| **UI Components** | Radix UI | Latest |
| **State Management** | Zustand | Latest |
| **Database** | SQLite | 3.x |
| **Video Processing** | FFmpeg | Latest |

### AI & APIs

| Service | Purpose | Integration |
|---------|---------|-------------|
| **Google Gemini** | Script generation | API |
| **Google Gemini TTS** | Voice synthesis | API |
| **YouTube Data API** | Video metrics | API + OAuth |
| **YouTube Data API** | Video downloading | yt-dlp |
| **Telegram Bot** | Interactive control | Bot API |

### Speech & Audio

| Technology | Purpose |
|------------|---------|
| **Faster-Whisper** | Speech-to-text |
| **stable-ts** | Alternative STT |

### ML & Data Science

| Technology | Purpose |
|------------|---------|
| **XGBoost** | Virality prediction |
| **Thompson Sampling** | Content selection |

---

## Security

### API Key Management

ShortsForge supports secure API key storage:

1. **System Keychain** (Recommended)
   - Linux: GNOME Keyring / KWallet
   - macOS: Keychain Access
   - Windows: Credential Manager

2. **Environment Variables** (For servers)
   - `.env` file (gitignored)

### Web Interface Security

- **API Key Authentication**: Protected endpoints require `X-API-Key` header
- **Rate Limiting**: Prevents abuse (5-60 requests/minute depending on endpoint)
- **Security Headers**: X-Frame-Options, X-XSS-Protection, HSTS, Referrer-Policy
- **Input Sanitization**: Prevents injection attacks
- **CORS**: Restricted to localhost

### Protected Endpoints

These endpoints require API key authentication:
- `POST /api/config`
- `POST /api/system/cleanup`
- `POST /api/system/restart-listener`
- `POST /api/context/import`
- `POST /api/context/clear`
- `POST /api/pipeline/download`

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
- Run `python workflows/shortsforge.py onboard` to verify

**Q: No videos downloading**
- Verify `PLAYLIST_URL` in `.env`
- Check YouTube playlist is public

**Q: TTS not generating**
- Ensure `TTS_VOICE` is valid (use `/voices` command)
- Check API key has TTS quota

**Q: Telegram bot not responding**
- Verify `TELEGRAM_BOT_TOKEN` in `.env`
- Check bot was started with `/start`

**Q: Metrics sync not working**
- Verify YouTube OAuth is configured (`client_secret.json` in workspace)
- Check video duration (must be < 3 minutes to be treated as Short)
- Ensure the Short exists on YouTube and appears in recent uploads
- Run sync via API: `curl -X POST http://localhost:8000/api/metrics/sync -H "X-API-Key: YOUR_KEY"`
- Check the database: stored YouTube IDs must match actual YouTube video IDs

### Debug Mode

```bash
# View recent logs
python workflows/shortsforge.py debug

# Check pipeline status
python workflows/shortsforge.py status

# Verbose output
python workflows/shortsforge.py run --verbose
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

Current version: **2.2.0**

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

**ShortsForge** — Turn your game streams into YouTube Shorts automatically.

Built with FastAPI, React, Python, and Google Gemini AI.