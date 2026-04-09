# ShortsForge Master Plan

## Project Overview

**ShortsForge** is an automated pipeline that transforms long-form YouTube game streams into ready-to-publish YouTube Shorts. It handles downloading, transcription, AI-powered script generation, clip extraction, and TTS narration — all controllable via Telegram bot.

---

## 1. Architecture

### 1.1 Core Components

| Component | File | Purpose |
|-----------|------|---------|
| **Pipeline Orchestrator** | `workflows/shortsforge.py` | Main application, 5-phase pipeline, Telegram listener, Content Studio |
| **Keychain Manager** | `workflows/keychain_manager.py` | Secure API key storage via system keyring with .env fallback |
| **Update Manager** | `workflows/update_manager.py` | Version checking, backup, and self-update from GitHub |

### 1.2 5-Phase Pipeline

```
YouTube Playlist → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5
   (URL)         (DL)      (Trans)   (Scripts) (Clips)    (TTS)
                       ↓           ↓         ↓        ↓
                    .json      .txt      .mp4     .wav + .srt
                  (Transcript) (Script)  (Clip)   (Audio) (Subtitles)
```

| Phase | Function | Input | Output |
|-------|----------|-------|--------|
| **1 - Download** | `phase_download()` | YouTube playlist URL | Video file in `streams/` |
| **2 - Transcribe** | `phase_transcribe()` | Video file | JSON + SRT transcript in `transcripts/` |
| **3 - Scripts** | `phase_scripts()` | Transcript JSON | AI-generated scripts in `scripts/` |
| **4 - Clips** | `phase_clips()` | Video + transcript | Scene-based clips in `shorts/` |
| **5 - TTS** | `phase_tts()` | Scripts | WAV audio + SRT subtitles in `tts/` |

### 1.3 Content Studio

Standalone content generation system for creating additional content from existing transcripts. Maintains persistent context (characters, locations, relationships) across runs using Obsidian-compatible markdown files in `content_studio/context/`.

### 1.4 Control Interface

- **Telegram Bot**: Full pipeline control via inline keyboard menus and text commands
- **CLI**: Direct execution via `python workflows/shortsforge.py <command>`
- **systemd**: Background listener service (`lambda-cut-listener.service`)

---

## 2. Current State Assessment

### 2.1 Strengths

- **Solid pipeline foundation**: All 5 phases functional with skip/resume capability
- **API key rotation**: Multi-key support with retry logic and rate limiting
- **Context-aware script generation**: Content Studio maintains character/location/relationship context
- **Round-robin diversity**: Script variants, perspectives, voices, and styles rotate automatically
- **Secure key storage**: System keychain with .env fallback for headless environments
- **Self-updating**: GitHub-based update system with automatic backups
- **Scene-based clip extraction**: Intelligent scene detection with scoring (density, drama)
- **Telegram inline menus**: Full interactive keyboard navigation

### 2.2 Weaknesses & Gaps

- **Script quality**: Generated scripts lack human-quality engagement and structure
- **No hallucination validation**: No post-generation factuality checking
- **Single-attempt generation**: No multi-variant selection for best output
- **Context not optimized**: All context loaded without relevance scoring or filtering
- **No quality metrics**: No tracking of script quality, engagement, or accuracy
- **Prompt engineering basic**: No few-shot examples, chain-of-thought, or self-verification
- **Groq model fixed**: Always uses `llama-3.3-70b-versatile` regardless of content complexity
- **No grammar/style checking**: Scripts go through without NLP validation

### 2.3 Script Generation & TTS Architecture

| Component | Primary | Fallback | Notes |
|-----------|---------|----------|-------|
| **Script Generation** | Groq (`llama-3.3-70b-versatile`) | Gemini (`gemini-2.5-flash-lite`) | Groq first, rotates keys, falls back to Gemini on failure |
| **TTS Generation** | Gemini (`gemini-2.5-flash-preview-tts`) | None | Gemini only — no Groq involvement |

### 2.4 Tech Stack

| Layer | Technology |
|-------|------------|
| **Language** | Python 3.10+ |
| **Video Processing** | FFmpeg (VAAPI hardware acceleration) |
| **Speech-to-Text** | Faster-Whisper (primary), stable-whisper (fallback) |
| **AI Scripts** | Groq (primary), Google Gemini (fallback) |
| **AI TTS** | Google Gemini TTS only |
| **Video Download** | yt-dlp with browser cookies |
| **Bot Interface** | Telegram Bot API (raw HTTP, no framework) |
| **Key Storage** | Python keyring (system keychain) |
| **Storage** | JSON files, Obsidian markdown |

---

## 3. Master Plan

### Phase 1: Prompt Engineering Enhancement (Weeks 1-2)

**Goal**: Improve script generation quality through better prompts

#### 1.1 Enhanced Prompt Structure
- Add expert role definition ("You are an expert video script writer for gaming content")
- Implement chain-of-thought reasoning steps (Analysis → Planning → Generation)
- Add 2-3 few-shot examples of excellent scripts per content type
- Specify explicit output format requirements
- Add self-verification instructions

#### 1.2 Content-Type Specific Prompts
- Theory: Speculative, intriguing, "what if" framing
- Analysis: Deep character/plot analysis, educational tone
- Review: Conversational opinions, hot takes
- Mystery: Suspenseful, hidden details focus
- Lore: World-building, historical context

#### 1.3 Jinja2 Template Migration
- Replace f-string prompts with Jinja2 templates
- Enable conditional sections, loops, and reusable components
- Better maintainability for complex prompt structures

**Success Criteria**:
- Generated scripts show improved structure and engagement
- Better adherence to verified facts
- More compelling openings and closings

---

### Phase 2: Validation System (Weeks 3-4)

**Goal**: Eliminate hallucinations and ensure factual accuracy

#### 2.1 Post-Generation Validation
- `validate_script_factuality()`: Check script against verified context
  - Extract mentioned entities using spaCy NER
  - Verify character names against whitelist (fuzzy matching via RapidFuzz)
  - Flag invented plot points, locations, or relationships
  - Return validation score and issues list

#### 2.2 Multiple Attempt Selection
- Generate 2-3 script variants with varying temperature (0.7, 0.8, 0.9)
- Score each variant on factual accuracy and engagement
- Select best variant based on combined score
- Fallback to safest variant if issues detected

#### 2.3 Engagement Scoring
- Hook strength analysis (first 100 words)
- Sentiment progression via TextBlob (emotional arc)
- Readability scores via NLTK (Flesch-Kincaid)
- Call-to-action effectiveness check

**Success Criteria**:
- Hallucination rate reduced by 50%+
- Script selection based on quality metrics
- Measurable improvement in script engagement scores

---

### Phase 3: Context Optimization (Weeks 5-6)

**Goal**: Smarter context management for better script relevance

#### 3.1 Context Relevance Scoring
- Weight recent transcripts higher
- Score context items by frequency and importance
- Filter to top-N most relevant items per generation

#### 3.2 Context Summarization
- For long-running series, create condensed context summaries
- Prioritize: recent appearance, frequency, plot importance
- Maintain max 10 items per category (characters, locations, relationships)

#### 3.3 Cross-Transcript Continuity
- Track character arcs across multiple transcripts
- Maintain relationship evolution timeline
- Avoid repeating previously covered content

**Success Criteria**:
- More focused, relevant context in prompts
- Reduced noise in context window
- Better series continuity across generated scripts

---

### Phase 4: Model Optimization (Weeks 7-8)

**Goal**: Right model for the right job

#### 4.1 Dynamic Groq Model Selection (Script Generation)
- Primary: Groq with model selection based on content type
  - Theory/Mystery: Higher-creativity models
  - Analysis/Lore: More factual/reasoning-focused models
- Fallback: Gemini (`gemini-2.5-flash-lite`) when Groq fails
- Maintain existing Groq key rotation and retry logic

#### 4.2 Adaptive Temperature
- Groq (scripts):
  - Theory: 0.9 (more creative for speculation)
  - Analysis: 0.6 (more factual)
  - Review: 0.7 (balanced)
  - Mystery: 0.8 (engaging reveals)
  - Lore: 0.7 (educational but engaging)
  - Documentary: 0.5 (most factual)
- Gemini (TTS): Temperature remains fixed (TTS does not use temperature)

#### 4.3 Token Optimization
- Dynamic maxOutputTokens based on target script length
- Efficient context window usage
- Rate limit optimization across Groq and Gemini API keys

#### 4.4 TTS — Gemini Only (No Changes to Model Strategy)
- TTS continues using `gemini-2.5-flash-preview-tts` exclusively
- No Groq involvement in TTS generation
- Voice/style rotation and segment concatenation logic preserved

**Success Criteria**:
- Better quality/efficiency ratio for script generation
- Appropriate creativity levels per content type
- TTS remains stable on Gemini-only pipeline

---

### Phase 5: Feedback & Monitoring (Weeks 9-10)

**Goal**: Data-driven continuous improvement

#### 5.1 Quality Metrics Logging
- Track hallucination rate per generation
- Log engagement scores
- Record validation results and selection criteria
- Store before/after comparisons

#### 5.2 Metrics Export
- Prometheus client for metrics export
- Custom metrics: `shortsforge_script_hallucination_rate`, `shortsforge_script_accuracy_score`
- Enhanced structured logging

#### 5.3 A/B Testing Framework
- Compare prompt variations
- Track which content types perform best
- Identify common hallucination patterns

**Success Criteria**:
- Data-driven improvement decisions
- Measurable quality improvements over time
- Ability to track progress against goals

---

## 4. Tool Selection

### Core Validation Tools

| Tool | Purpose | Integration |
|------|---------|-------------|
| **RapidFuzz** | Fuzzy string matching for hallucinated names | Validation function |
| **spaCy** (en_core_web_sm) | Named Entity Recognition (PERSON, LOC) | Entity extraction from scripts |
| **TextBlob** | Sentiment analysis, POS tagging | Engagement scoring |
| **NLTK** (select modules) | Readability scores, stopword analysis | Quality metrics |

### Prompt Engineering

| Tool | Purpose | Integration |
|------|---------|-------------|
| **Jinja2** | Template engine for complex prompts | Replace f-string prompts |
| **string.Template** | Simple safe substitution | Context insertion |

### Testing & Monitoring

| Tool | Purpose | Integration |
|------|---------|-------------|
| **pytest** | Test suite for validation functions | `tests/test_script_validation.py` |
| **Python logging** | Structured generation logging | Enhanced logging in script functions |
| **Prometheus client** | Metrics export | Custom quality metrics |

### Explicitly Deferred (Not Using Initially)

- LangChain, Guardrails AI (overkill for current needs)
- DeepEval, Ragas, AuditLLM (general LLM eval frameworks, too broad)
- ClaimBuster, FEVER (too heavyweight for simple entity verification)

---

## 5. Quality Targets

| Metric | Target |
|--------|--------|
| Hallucination rate | < 2% |
| Factual accuracy | > 95% |
| Viewer retention (first 30s) | > 70% |
| Average view duration | > 65% of video length |
| Engagement rate (likes/views) | > 8% |

---

## 6. Implementation Guidelines

### 6.1 Critical Success Factors

- **Maintain backward compatibility**: All existing pipeline functionality must continue working
- **Preserve API key management**: Keep current keychain + .env fallback system
- **Keep error handling intact**: All existing retry logic and rate limiting preserved
- **Performance**: No significant degradation in pipeline speed

### 6.2 Risk Mitigation

- A/B test all changes before full rollout
- Maintain rollback capability (backup system already in place)
- Monitor metrics closely during each phase rollout
- Keep fallback to current implementation if needed

### 6.3 Testing Methodology

- Create validation dataset: 10 transcripts with known good scripts
- Hallucination test cases: transcripts with deliberate omissions
- Edge cases: minimal transcripts, complex narratives
- Cross-game consistency tests

---

## 7. Deliverables

1. Enhanced `_cs_generate_script()` and `_gemini_script()` functions with improved prompts
2. Validation and multi-attempt selection system
3. Context optimization and summarization functions
4. Dynamic model selection and adaptive temperature
5. Quality metrics logging and monitoring
6. Test suite for validation functions
7. Documentation of all changes
8. Before/after quality comparison report

---

## 8. Timeline Summary

| Phase | Duration | Focus |
|-------|----------|-------|
| **Phase 1** | Weeks 1-2 | Prompt engineering, few-shot examples, Jinja2 templates |
| **Phase 2** | Weeks 3-4 | Validation system, multi-attempt selection, engagement scoring |
| **Phase 3** | Weeks 5-6 | Context relevance scoring, summarization, continuity |
| **Phase 4** | Weeks 7-8 | Dynamic model selection, adaptive temperature, token optimization |
| **Phase 5** | Weeks 9-10 | Quality metrics, A/B testing, continuous improvement |

---

*Master Plan v1.0 — Created 2026-04-07*
