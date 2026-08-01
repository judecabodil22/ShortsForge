# Configuration Guide

## Environment Variables

All configuration is done via the `.env` file.

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GEMINI_API_KEY` | API key from Google AI Studio | `AIza...` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PLAYLIST_URL` | (none) | YouTube playlist to process |
| `GROQ_API_KEY` | (none) | Groq API key for highlight ranking + Gemini fallback (free via console.groq.com) |
| `TTS_PROVIDER` | `kokoro` | TTS backend: `kokoro` (CPU/free/offline), `edge` (free cloud), or `gemini` (API) |
| `TTS_VOICE` | `Vindemiatrix` | TTS voice name (Gemini and Kokoro voice mappings supported) |
| `TTS_STYLE` | (none) | Style instruction for TTS |
| `GAME_TITLE` | (none) | Game title for script context |
| `CLIPS_PER_HOUR` | `5` | Number of clips to generate per hour |
| `PLAYLIST_INDEX` | `1` | Which video to download from playlist |
| `WORKSPACE` | (auto) | Working directory path |
| `RECORDING_PATH` | `~/Videos/Recordings/` | Local recordings folder |
| `WHISPER_MODEL` | `medium` | Whisper model size (`tiny`, `base`, `small`, `medium`, `large`) |
| `TTS_EMOTION` | `default` | TTS emotion (happy, sad, excited, calm, angry, fearful, whisper) |
| `TTS_SPEED` | `1.0` | TTS speed multiplier (0.5–2.0) |
| `TTS_PROVIDER` | `kokoro` | TTS provider (kokoro, gemini, edge) |
| `CLIP_PACING` | `normal` | Clip pacing mode (fast, normal, slow) |

## Telegram Commands

> **DEPRECATED**: Telegram bot functionality has been **removed**. The web interface provides full pipeline control. This section is kept for historical reference only.

### Pipeline Control

| Command | Description |
|---------|-------------|
| `/run_pipeline` | Run full pipeline |
| `/run_local` | Process local recordings |
| `/run_phase N` | Run specific phase |
| `/skip_phase N` | Skip specific phase |
| `/stop_pipeline` | Stop running pipeline |

### Configuration

| Command | Description |
|---------|-------------|
| `/set_voice` | Change TTS voice |
| `/set_style` | Set TTS style |
| `/voices` | List available TTS voices |
| `/set_game` | Set game title for script context |
| `/set_recording_path` | Set recordings folder |
| `/config` | Show current settings |

### Status & Debug

| Command | Description |
|---------|-------------|
| `/status` | Show listener and pipeline status |
| `/debug` | Show recent log entries |

### Updates

| Command | Description |
|---------|-------------|
| `/update` | Check for updates |
| `/restart_listener` | Restart the listener |

## TTS Voices

### Provider Selection

Set `TTS_PROVIDER` in `.env` to choose the backend:

| Provider | Cost | Requirement | Offline | Voices |
|----------|------|-------------|---------|--------|
| `kokoro` | Free | CPU (no GPU needed) | Yes (after first download) | 54 |
| `edge` | Free | Internet | No | 200+ (Microsoft) |
| `gemini` | API quota | Gemini API key + Internet | No | 29 |

### Gemini Voices (used when `TTS_PROVIDER=gemini`)

Default: `Vindemiatrix`.

#### Female Voices

| Voice | Style |
|-------|-------|
| **Aoede** | Breezy and natural |
| **Kore** | Firm and confident |
| **Leda** | Youthful and energetic |
| **Zephyr** | Bright and cheerful |
| **Autonoe** | Bright and optimistic |
| **Callirrhoe** | Easy-going and relaxed |
| **Despina** | Smooth and flowing |
| **Erinome** | Clear and precise |
| **Gacrux** | Mature and experienced |
| **Laomedeia** | Upbeat and lively |
| **Pulcherrima** | Forward and expressive |
| **Sulafat** | Warm and welcoming |
| **Vindemiatrix** | Gentle and kind |
| **Achernar** | Soft and gentle |

#### Male Voices

| Voice | Style |
|-------|-------|
| **Puck** | Upbeat and energetic |
| **Charon** | Informative and clear |
| **Fenrir** | Excitable and dynamic |
| **Orus** | Firm and decisive |
| **Achird** | Friendly and approachable |
| **Algenib** | Gravelly texture |
| **Algieba** | Smooth and pleasant |
| **Alnilam** | Firm and strong |
| **Enceladus** | Breathy and soft |
| **Iapetus** | Clear and articulate |
| **Rasalgethi** | Informative and professional |
| **Sadachbia** | Lively and animated |
| **Sadaltager** | Knowledgeable and authoritative |
| **Schedar** | Even and balanced |
| **Umbriel** | Easy-going and calm |
| **Zubenelgenubi** | Casual and conversational |

### Kokoro Voices (used when `TTS_PROVIDER=kokoro`)

Kokoro uses a mapping layer to match Gemini voice names to Kokoro's built-in voices.
18 voices are mapped including: af_sky, af_bella, af_sarah, am_adam, am_michael, bf_emma, bf_isabella, bm_george, etc.
Set `TTS_VOICE` to a Gemini voice name (e.g. `Puck`, `Vindemiatrix`) and it maps to the closest Kokoro equivalent.

### Style Instructions

You can also set a style instruction to customize how the TTS speaks:

```
/set_style Speak in a thoughtful, soft-spoken manner with genuine warmth
```

Or use bracket tags for quick styling:
```
[thoughtful][soft][genuine]
```

## Directory Structure

```
Cogitator/
├── .env              # Configuration (not in git)
├── workflows/        # Python code
├── streams/         # Downloaded videos
├── transcripts/     # Generated transcripts
├── scripts/         # AI-generated scripts
├── shorts/          # Final video clips
├── tts/            # Generated audio + subtitles
└── assembly/       # Assembled videos with subtitles
```

## API Keys

### Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Create a new API key
3. Add to `.env`: `GEMINI_API_KEY=your_key`

For multiple keys (rate limiting), add them through the onboard process or store them directly in your system keychain using the keychain manager.

### Discord Bot (Removed)

> **Note**: Telegram/Discord bot functionality has been **removed** from Cogitator. The web interface provides full pipeline control. No bot token or chat ID is required.
