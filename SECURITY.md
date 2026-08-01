# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.4.x   | :white_check_mark: |
| < 2.4   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability within Cogitator, please send an email to the maintainers. All security vulnerabilities will be promptly addressed.

Please include the following information:
- Type of vulnerability
- Full paths of source file(s) related to the vulnerability
- Location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it

## Security Best Practices

### API Key Management

Cogitator uses multiple API keys for its functionality:

1. **Gemini API Key** - For AI script generation and TTS
2. **YouTube API Key** - For fetching video metrics
3. **YouTube OAuth** - For YouTube API access
4. **Telegram Bot Token** - Optional, for Telegram bot functionality (legacy)

#### Secure Storage

Cogitator supports storing API keys securely in your system's keychain:

- **Linux**: Uses `dbus` keyring (e.g., GNOME Keyring, KWallet)
- **macOS**: Uses Keychain Access
- **Windows**: Uses Credential Manager

For headless environments (e.g., systemd services), you can use a `.env` file:

```bash
# Create .env file in Cogitator root
cp .env.example .env
# Edit .env with your actual API keys
```

**Important**: Never commit `.env` or `client_secret.json` to version control!

### Web Interface Security

The web backend (`backend/main.py`) includes:

- **API Key Authentication**: Sensitive endpoints require `X-API-Key` header
- **Rate Limiting**: Prevents abuse of API endpoints
- **Security Headers**: X-Frame-Options, X-XSS-Protection, HSTS, etc.
- **Input Sanitization**: Prevents injection attacks

#### API Key for Web Interface

The API key is auto-generated on first run and stored in:
```
~/.cogitator/api_key
```

When making requests to protected endpoints, include the header:
```
X-API-Key: sf_xxxxxxxxxxxxxxxxxxxxx
```

#### Protected Endpoints

The following endpoints require API key authentication:
- `POST /api/config` - Update configuration
- `POST /api/system/cleanup` - Cleanup files
- `POST /api/context/import` - Import context
- `POST /api/context/clear` - Clear context
- `POST /api/pipeline/download` - Download from URL

### Production Deployment

When deploying Cogitator in production:

1. **Use HTTPS**: Never run the web interface over HTTP
2. **Restrict CORS**: Update CORS settings to your actual domain
3. **Rotate API Keys**: Periodically rotate all API keys
4. **Firewall**: Restrict access to port 8000
5. **Monitor Logs**: Watch for unusual activity
6. **Backups**: Regular backup of SQLite database and settings

### Environment Variables

Required environment variables (see `.env.example`):

```
GEMINI_API_KEY=your_gemini_key
GAME_TITLE=your_game_title
TTS_VOICE=your_preferred_voice
```

Optional:
```
GROQ_API_KEY=your_groq_key
TELEGRAM_BOT_TOKEN=your_telegram_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Telegram Security

> **Note**: Telegram bot functionality is optional. The web interface provides full pipeline control.

- Keep your `TELEGRAM_CHAT_ID` private
- Don't share bot tokens publicly
- Use bot with appropriate privacy settings

## Vulnerability Disclosure Timeline

- Initial response: Within 48 hours
- Status update: Within 7 days
- Fix released: Based on severity (critical: 7 days, high: 30 days, medium: 90 days)

## Security Updates

Security updates will be released as patch versions and documented in CHANGELOG.md.

## Third-Party Dependencies

Cogitator uses the following key dependencies:
- FastAPI (web framework)
- Google Gemini API (AI)
- YouTube Data API (metrics)
- FFmpeg (video processing)

Ensure you keep these dependencies updated for security patches.

## Data Storage

- **SQLite Database**: Stores performance metrics and learnings
- **Context Files**: Stored in `Context/` directory
- **Media Files**: Temporary storage in `media/`, `shorts/`, `tts/`, `transcripts/`

Ensure these directories are properly secured and not exposed publicly.