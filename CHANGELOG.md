# ShortsForge Changelog

All notable changes to this project are documented here.

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
  - Located at `/home/alph4r1us/ShortsForge/Context/`
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

ShortsForge v1.1.0 adds persistent context for series continuity and improved script generation accuracy.

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

ShortsForge v1.0.0 is the initial release of an automated YouTube Shorts pipeline for game streams. It handles the complete workflow from YouTube playlist to ready-to-edit shorts with AI-powered narration.

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
ShortsForge/
├── workflows/           # Main pipeline code
│   ├── shortsforge.py  # Main application
│   ├── keychain_manager.py
│   └── update_manager.py
├── content_studio/      # Content Studio
│   └── context.json    # Stored context
├── docs/               # Documentation
├── .env.example       # Configuration template
├── install.sh         # Installation script
├── requirements.txt   # Python dependencies
└── README.md         # Documentation
```

---

### Dependencies

- Python 3.10+
- FFmpeg
- Faster-Whisper
- Google Gemini API
- yt-dlp
- Telegram Bot API
- python-dotenv
- keyring

---

### Known Limitations

- Requires YouTube Data API access for playlist features
- Gemini API key required for script generation and TTS
- Telegram bot optional but recommended for full functionality
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