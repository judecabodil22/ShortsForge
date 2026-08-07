"""Description variety helpers for script generation.

Prevents repetitive AI-typical opening verbs in YouTube Shorts descriptions.
"""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence, Tuple


# Verbs to BAN — these are the cliché AI-typical openers
BANNED_OPENERS = {
    "discover", "unveil", "uncover", "delve", "explore", "dive",
    "journey", "embark", "witness", "experience", "reveal", "expose",
    "unravel", "decode", "decode the", "step into", "enter",
    "join", "follow", "watch as", "see how", "find out",
}

# Categorized replacement verbs by tone
VERB_CATEGORIES = {
    "action": [
        "breaks", "shatters", "crashes", "drops", "snaps", "rips",
        "charges", "slashes", "smashes", "blasts", "fires", "hits",
    ],
    "curiosity": [
        "asks", "questions", "wonders", "hints at", "points to",
        "suggests", "implies", "signals", "teases", "whispers",
    ],
    "drama": [
        "changes", "shifts", "turns", "flips", "breaks", "rips",
        "tears", "burns", "bleeds", "cracks", "falls", "rises",
    ],
    "intrigue": [
        "hides", "conceals", "masks", "buries", "cloaks", "shadows",
        "obscures", "veils", "covers", "smothers", "betrays",
    ],
    "emotion": [
        "feels", "aches", "grieves", "fears", "hopes", "trusts",
        "doubts", "regrets", "longs for", "refuses to", "fights for",
    ],
    "factual": [
        "shows", "proves", "confirms", "documents", "records",
        "captures", "reveals the", "explains why", "tracks",
    ],
}


def detect_opener(description: str) -> str:
    """Extract the first 1-2 words (the opening verb/phrase)."""
    if not description:
        return ""
    words = description.strip().split()
    if not words:
        return ""
    # Check for two-word openers like "step into"
    if len(words) >= 2:
        two = f"{words[0].lower()} {words[1].lower()}"
        if two in BANNED_OPENERS:
            return two
    return words[0].lower()


def is_banned_opener(opener: str) -> bool:
    """Check if an opener is in the banned set."""
    return opener.lower().strip(".") in BANNED_OPENERS


def is_repeated(opener: str, recent: Sequence[str], threshold: int = 2) -> bool:
    """Check if opener appeared more than threshold times recently."""
    count = sum(1 for r in recent if r == opener)
    return count >= threshold


def suggest_opener(recent: Sequence[str], preferred_category: Optional[str] = None) -> str:
    """Suggest an opening verb not used recently."""
    # Flatten and shuffle by category priority
    used = set(recent)
    categories = [preferred_category] if preferred_category else list(VERB_CATEGORIES.keys())

    # Try preferred category first, then others
    candidates = []
    for cat in categories:
        if cat in VERB_CATEGORIES:
            candidates.extend(VERB_CATEGORIES[cat])

    # Filter out recently used
    available = [v for v in candidates if v not in used]
    if available:
        return available[0]

    # Fallback: any verb not banned
    all_verbs = [v for cat_verbs in VERB_CATEGORIES.values() for v in cat_verbs]
    available = [v for v in all_verbs if v not in used and v not in BANNED_OPENERS]
    if available:
        return available[0]

    return ""


def build_description_guidance(
    recent_openers: Sequence[str],
    used_categories: Optional[List[str]] = None,
) -> str:
    """Build prompt guidance for description variety."""
    if not recent_openers:
        recent_openers_list = "None yet"
    else:
        recent_openers_list = ", ".join(recent_openers[-5:])

    # Suggest a category to use
    cat_counts = {}
    for cat in VERB_CATEGORIES:
        cat_counts[cat] = 0
    # TODO: could track category usage if needed

    suggested = suggest_opener(recent_openers)
    suggested_text = f" Try starting with: \"{suggested}\"" if suggested else ""

    lines = [
        "DESCRIPTION RULES:",
        f"- Do NOT start with these verbs (used too often): {', '.join(sorted(BANNED_OPENERS))}",
        f"- Recent openers to avoid: {recent_openers_list}",
        "- Pick a verb that feels natural for THIS specific story — not a generic AI opener.",
        "- The first sentence should hook the reader, not describe what the video does.",
        f"- Active verb suggestions: breaks, asks, hides, shows, feels, changes{suggested_text}",
    ]
    return "\n".join(lines)


def enforce_description_variety(
    description: str,
    recent_openers: Sequence[str],
) -> Tuple[str, str]:
    """Validate and fix description opener if banned/repeated.
    Returns (fixed_description, opener_used).
    """
    if not description:
        return description, ""

    opener = detect_opener(description)
    if not is_banned_opener(opener) and not is_repeated(opener, recent_openers):
        return description, opener

    # Replace the opener
    suggested = suggest_opener(recent_openers)
    if not suggested:
        return description, opener

    # Replace first word(s) with suggested verb
    words = description.split()
    if not words:
        return description, ""

    # Check if we have a two-word opener
    if len(words) >= 2 and f"{words[0].lower()} {words[1].lower()}" in BANNED_OPENERS:
        words = words[2:]
    elif words[0].lower().rstrip(".") in BANNED_OPENERS:
        words = words[1:]

    fixed = f"{suggested[0].upper() + suggested[1:]} {' '.join(words)}" if suggested else description
    return fixed, suggested


def format_recent_openers_for_prompt(openers: Iterable[str]) -> str:
    """Format recent openers for the prompt."""
    return "\n".join(o for o in openers if o)
