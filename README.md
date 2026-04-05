# ShortsForge

**Automated YouTube Shorts Pipeline for Game Streams**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux-purple.svg)](https://archlinux.org/)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)

ShortsForge is an automated pipeline that transforms long-form YouTube game streams into ready-to-edit YouTube Shorts. It handles downloading, transcription, AI-powered script generation, clip extraction, and TTS narration — all with minimal setup.

---

## Table of Contents

1. [What is ShortsForge?](#what-is-shortsforge)
2. [Features](#features)
3. [How It Works](#how-it-works)
4. [Quick Start](#quick-start)
5. [Installation](#installation)
6. [Configuration](#configuration)
7. [Telegram Commands](#telegram-commands)
8. [Content Studio](#content-studio)
9. [Project Structure](#project-structure)
10. [Tech Stack](#tech-stack)
11. [Troubleshooting](#troubleshooting)
12. [License](#license)

---

## What is ShortsForge?

ShortsForge takes a YouTube playlist of game streams and automatically produces:

- **Downloaded videos** from YouTube
- **Transcripts** with timestamps (JSON + SRT)
- **AI-generated scripts** using Gemini AI
- **Video clips** segmented by topic/scene
- **TTS audio narration** with matching subtitles

Each phase runs independently and can be skipped. The pipeline saves progress — if you restart, it picks up where you left off.

---

## Features

### Pipeline (5 Phases)

| Phase | Feature | Description |
|-------|---------|-------------|
| **1** | Download | Downloads videos from YouTube playlist |
| **2** | Transcribe | Converts video audio to text with timestamps |
| **3** | Scripts | Generates AI-powered narration scripts |
| **4** | Clip | Extracts video clips based on scene detection |
| **5** | TTS | Creates AI voice narration with subtitle files |

### Content Studio

- Generate additional content from existing transcripts
- Analyze multiple transcripts for deeper context
- Create custom scripts with AI assistance
- Generate TTS from custom scripts

### Integrations

- **YouTube**: Playlist-based video downloading
- **Telegram**: Bot commands for full control
- **Google Gemini**: AI-powered script generation
- **Faster-Whisper**: High-quality speech-to-text
- **FFmpeg**: Video processing and clip extraction

---

## How It Works

```
YouTube Playlist → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5
   (URL)         (DL)      (Trans)   (Scripts) (Clips)    (TTS)
                      ↓           ↓         ↓        ↓
                   .json      .txt      .mp4     .wav + .srt
                 (Transcript) (Script)  (Clip)   (Audio) (Subtitles)
```

**Flow:**
1. Provide a YouTube playlist URL
2. Pipeline downloads videos (or skips if already downloaded)
3. Faster-Whisper transcribes audio with timestamps
4. Gemini AI generates narration scripts from transcripts
5. FFmpeg extracts clips based on scene changes
6. Gemini TTS creates voice narration with SRT subtitles

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/judecabodil22/ShortsForge.git
cd ShortsForge

# 2. Copy environment template
cp .env.example .env

# 3. Edit .env with your API keys
nano .env

# 4. Set up virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Run onboarding wizard
python workflows/shortsforge.py onboard

# 6. Start Telegram listener
python workflows/shortsforge.py listen
```

Then control everything via Telegram!

---

## Installation

### Prerequisites

- **Python 3.10+**
- **FFmpeg** (for video processing)
- **Git**
- **YouTube API key** (for downloading)
- **Gemini API key** (for AI scripts + TTS)
- **Telegram Bot Token** (optional, for bot control)

### Step-by-Step

#### 1. Clone the Repository

```bash
git clone https://github.com/judecabodil22/ShortsForge.git
cd ShortsForge
```

#### 2. Install System Dependencies

**Arch Linux:**
```bash
sudo pacman -S ffmpeg python python-pip git
```

**Ubuntu/Debian:**
```bash
sudo apt install ffmpeg python3 python3-pip git
```

#### 3. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 4. Configure Environment

```bash
cp .env.example .env
nano .env
```

#### 5. Run Onboarding (Recommended)

```bash
python workflows/shortsforge.py onboard
```

This interactive wizard helps you:
- Set up API keys
- Configure Telegram bot
- Test your setup

#### 6. Start the Listener

```bash
python workflows/shortsforge.py listen
```

The listener runs in the background and responds to Telegram commands.

---

## Configuration

All configuration is in the `.env` file:

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `PLAYLIST_URL` | YouTube playlist URL | `https://youtube.com/playlist?list=...` |
| `GEMINI_API_KEY` | Google Gemini API key | `AIzaSy...` |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `TTS_VOICE` | `Vindemiatrix` | Gemini TTS voice name |
| `GAME_TITLE` | (none) | Game title for context in scripts |
| `CLIPS_PER_HOUR` | `5` | Number of clips to extract per hour |
| `SRT_MAX_WORDS` | `10` | Max words per subtitle line (Phase 5) |
| `PLAYLIST_INDEX` | `1` | Which video to download from playlist |
| `TELEGRAM_BOT_TOKEN` | (none) | Telegram bot token for commands |
| `TELEGRAM_CHAT_ID` | (none) | Your Telegram chat ID for notifications |

### Getting Your API Keys

**Google Gemini API Key:**
1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Copy to `.env`

**YouTube Data API:**
- Uses yt-dlp with browser cookies (see docs)

**Telegram Bot:**
1. Open @BotFather on Telegram
2. Create a new bot with `/newbot`
3. Copy the token to `.env`
4. Get your chat ID: start a chat with @userinfobot

---

## Telegram Commands

### Pipeline Control

| Command | Description |
|---------|-------------|
| `/start` | Start the pipeline |
| `/run` | Run full pipeline (all phases) |
| `/run_phase 1,2,3` | Run specific phases |
| `/skip_phase 3` | Skip a specific phase |
| `/status` | Show current pipeline status |
| `/stop_pipeline` | Stop running pipeline |

### Configuration

| Command | Description |
|---------|-------------|
| `/set_voice Puck` | Change TTS voice |
| `/voices` | List available voices |
| `/set_style Your style...` | Set TTS style prefix |
| `/set_clips 10` | Set clips per hour (1-20) |
| `/set_srt_words 10` | Set max words per subtitle (3-20) |
| `/set_game Game Title` | Set game title for scripts |
| `/config` | Show current settings |

### Tools

| Command | Description |
|---------|-------------|
| `/menu` | Show interactive menu |
| `/cs` | Open Content Studio |
| `/status` | Show listener + pipeline status |
| `/debug` | Show recent log entries |
| `/version` | Show current version |
| `/delete_partial` | Delete incomplete files |
| `/cleanup` | Delete all generated files |
| `/help` | Show all commands |

---

## Content Studio

Content Studio lets you generate additional content from existing transcripts.

### Access

Send `/cs` to your Telegram bot.

### Features

1. **Import Pipeline Data** — Copy transcripts from main pipeline
2. **Generate Script** — Create scripts from multiple transcripts with AI context
3. **Generate TTS** — Create TTS audio from generated scripts
4. **Clear All** — Reset content studio files

### Context Memory

Content Studio maintains context across runs:
- Character names extracted from transcripts
- Key terms and locations
- Relationships between characters

Use `/cs_context` to view/edit stored context.

---

## Project Structure

```
ShortsForge/
├── workflows/           # Main pipeline code
│   ├── shortsforge.py  # Main application
│   ├── keychain_manager.py
│   └── update_manager.py
├── content_studio/      # Content Studio feature
│   ├── context.json    # Stored context
│   ├── scripts/        # Generated scripts
│   ├── transcripts/   # Imported transcripts
│   └── tts/           # Generated TTS
├── docs/               # Documentation
├── .env.example       # Configuration template
├── install.sh         # Installation script
├── requirements.txt   # Python dependencies
├── VERSION           # Version file
└── README.md         # This file
```

### Generated Output

| Directory | Contents |
|-----------|----------|
| `streams/` | Downloaded YouTube videos |
| `transcripts/` | JSON + SRT transcripts |
| `scripts/` | AI-generated narration scripts |
| `shorts/` | Extracted video clips |
| `tts/` | TTS audio + subtitle files |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| **Language** | Python 3.10+ |
| **Video Processing** | FFmpeg |
| **Speech-to-Text** | Faster-Whisper |
| **AI Scripts** | Google Gemini API |
| **AI TTS** | Google Gemini TTS |
| **Video Download** | yt-dlp |
| **Bot Interface** | Telegram Bot API |
| **Storage** | JSON files |

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
- Ensure `TTS_VOICE` is valid (see `/voices` command)
- Check API key has TTS quota

**Q: Telegram bot not responding**
- Verify `TELEGRAM_BOT_TOKEN` in `.env`
- Check bot was started with `/start`

### Debug Mode

```bash
# View recent logs
python workflows/shortsforge.py debug

# Check pipeline status
python workflows/shortsforge.py status
```

---

## License

This project is licensed under the MIT License.

See [LICENSE](./LICENSE) for full details.

---

**ShortsForge** — Turn your game streams into YouTube Shorts automatically.