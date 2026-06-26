#!/usr/bin/env python3
"""
Cogitator Centralized Constants & Shared Utilities

Single source of truth for:
- TTS voices and styles
- Performance score calculation
- Readability scoring (Flesch)
- Hook strength calculation
- Duration parsing
- Groq key rotation
"""
import re

# ─── Fuzzy Dedup & Alias Resolution ──────────────────────────────────────────

try:
    from rapidfuzz import fuzz
    _RAPIDFUZZ_AVAILABLE = True
except ImportError:
    _RAPIDFUZZ_AVAILABLE = False

def dedupe_entity_list(items: list[str], threshold: int = 80) -> tuple[list[str], dict[str, str]]:
    """
    Deduplicate a list of entity names using fuzzy matching.
    Returns (deduplicated_list, alias_map) where alias_map maps short forms to canonical names.
    """
    if not items or not _RAPIDFUZZ_AVAILABLE:
        return items, {}

    canonical = []
    alias_map = {}

    for item in items:
        item_lower = item.lower().strip()
        matched = False

        for existing in canonical:
            existing_lower = existing.lower()
            if item_lower == existing_lower:
                matched = True
                break
            ratio = fuzz.token_sort_ratio(item_lower, existing_lower)
            if ratio >= threshold:
                # Shorter name is alias of longer canonical name
                if len(item) < len(existing):
                    alias_map[item] = existing
                else:
                    alias_map[existing] = item
                    canonical.remove(existing)
                    canonical.append(item)
                matched = True
                break

        if not matched:
            canonical.append(item)

    return canonical, alias_map

def fuzzy_dedup_against_list(item: str, existing_list: list[str], threshold: int = 80) -> tuple[bool, str | None]:
    """
    Check if item fuzzy-matches any entry in existing_list.
    Returns (is_duplicate, canonical_form_or_None).
    """
    if not existing_list or not _RAPIDFUZZ_AVAILABLE:
        return False, None

    item_lower = item.lower().strip()
    for existing in existing_list:
        existing_lower = existing.lower()
        if item_lower == existing_lower:
            return True, existing
        ratio = fuzz.token_sort_ratio(item_lower, existing_lower)
        if ratio >= threshold:
            # Use the longer form as canonical
            canonical = existing if len(existing) >= len(item) else item
            return True, canonical

    return False, None

# ─── TTS Voices ──────────────────────────────────────────────────────────────

TTS_VOICES = [
    "Vindemiatrix", "Aoede", "Callirrhoe", "Gacrux", "Sulafat", "Leda",
    "Kore", "Enceladus", "Erinome", "Despina", "Alnilam", "Laomedeia",
    "Achernar", "Pulcherrima", "Zephyr", "Puck", "Charon", "Fenrir",
    "Orus", "Iapetus", "Umbriel", "Algieba", "Rasalgethi", "Schedar",
    "Sadachbia", "Sadaltager", "Achird", "Zubenelgenubi", "Algenib", "Autonoe"
]

# ─── TTS Style Options ───────────────────────────────────────────────────────

TTS_STYLE_OPTIONS = [
    "Speak with intrigue and mystery. Drop hints naturally through sentences, not mysterious fragments.",
    "Speak confidently and authoritatively. Explain causes and effects clearly, like an expert.",
    "Speak with urgency and forward momentum. Keep the story moving, build to the climax naturally.",
    "Speak thoughtfully and reflectively. Like sharing wisdom with a friend, measured and genuine.",
    "Speak naturally like telling a story to a friend. Conversational, engaging, keep the flow moving.",
    "Speak like a professional news reporter. Clear, factual, objective. Present information in order.",
    "Speak like a documentary host. Informed, warm, educational. Add context naturally.",
    "Speak with investigative intensity. Build tension through the story, pause for effect naturally.",
    "Speak as if you ARE the character. Personal, emotional, raw. First person, genuine.",
    "Speak like sharing an incredible story with a friend. Conversational, engaging, hook them early.",
]

# ─── Groq Key Rotation ───────────────────────────────────────────────────────

_GROQ_KEY_INDEX = 0

def get_groq_keys():
    """Get list of Groq API keys from keychain (preferred) or environment."""
    try:
        from keychain_manager import get_groq_keys as _kc_get_keys
        kc_keys = _kc_get_keys()
        if kc_keys:
            return kc_keys
    except ImportError:
        pass
    import os
    keys = []
    primary = os.environ.get("GROQ_API_KEY", "")
    if primary:
        keys.append(primary)
    for i in range(1, 10):
        key = os.environ.get(f"GROQ_API_KEY_{i}", "")
        if key:
            keys.append(key)
    return keys

def get_next_groq_key():
    """Get next Groq API key with round-robin rotation."""
    global _GROQ_KEY_INDEX
    keys = get_groq_keys()
    if not keys:
        return ""
    key = keys[_GROQ_KEY_INDEX % len(keys)]
    _GROQ_KEY_INDEX = (_GROQ_KEY_INDEX + 1) % len(keys)
    return key

# ─── Performance Score ───────────────────────────────────────────────────────

def calculate_performance_score(views: int, engagement_ratio: float, duration: int = None) -> float:
    """Calculate a combined performance score (0-100)."""
    if views == 0:
        return 0.0

    views_score = min(views / 100, 100) * 0.4
    engagement_score = min(engagement_ratio * 10, 100) * 0.6

    score = views_score + engagement_score

    if duration:
        optimal_duration = 45
        duration_factor = 1.0 - abs(duration - optimal_duration) / 120
        duration_factor = max(0.5, min(1.0, duration_factor))
        score = score * (0.7 + 0.3 * duration_factor)

    return min(score, 100)

# ─── Duration Parsing ────────────────────────────────────────────────────────

def parse_duration(duration_str: str) -> int:
    """Parse ISO 8601 duration string to seconds."""
    import re
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds

# ─── Readability (Flesch Reading Ease) ───────────────────────────────────────

def _count_syllables(word: str) -> int:
    """Count syllables in a word."""
    word = word.lower()
    if len(word) <= 3:
        return 1
    vowels = 'aeiouy'
    count = 0
    prev_vowel = False
    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    if word.endswith('e') and count > 1:
        count -= 1
    return max(1, count)

def calculate_readability(text: str) -> float:
    """Calculate readability score (Flesch Reading Ease, 0-100)."""
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    words = text.split()

    if not sentences or not words:
        return 0

    num_sentences = len(sentences)
    num_words = len(words)
    num_syllables = sum(_count_syllables(word) for word in words)

    avg_sentence_length = num_words / num_sentences
    avg_syllables_per_word = num_syllables / num_words

    score = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
    return max(0, min(100, score))

# ─── Hook Strength ───────────────────────────────────────────────────────────

def calculate_hook_strength(script_text: str) -> float:
    """Calculate hook strength based on opening line analysis."""
    lines = script_text.strip().split('\n')
    if not lines:
        return 0

    first_line = lines[0].lower()
    strength = 0

    hook_starters = [
        'what nobody tells you', 'secret', 'truth about', 'never realized',
        "here's why", 'the reality is', 'you need to know', 'did you know',
        'discover', 'uncover', 'revealed', 'shocking', 'amazing'
    ]

    for starter in hook_starters:
        if starter in first_line:
            strength += 0.3

    if first_line.startswith("i'm ") or first_line.startswith('i '):
        strength += 0.1

    if any(word in first_line for word in ['never', 'always', 'everyone', 'nobody']):
        strength += 0.2

    if re.search(r'\d+', first_line):
        strength += 0.15

    if '?' in first_line:
        strength += 0.2

    return min(strength, 1.0)
