#!/usr/bin/env python3
"""
Cogitator Game Lore Fetcher
Fetches game plot, characters, and lore from LLM before transcript analysis.
Bootstraps context so the first scripts have game knowledge.

Runs as Phase 3a — called at the start of phase_context().
Uses parallel dispatch to Gemini + Groq; whichever responds first wins.
"""

import json, os, re, threading, urllib.request
from typing import Optional, Dict

GAME_LORE_PROMPT = """You are a game lore expert. Given a game title, provide comprehensive lore information.

Game: {game_title}

Return a JSON object with this exact structure:
{{
    "plot_summary": "2-3 paragraph summary of the main story and plot",
    "characters": [
        {{"name": "Character Name", "role": "protagonist/antagonist/supporting", "affiliation": "faction or group", "description": "brief description", "importance": 1-10}}
    ],
    "locations": [
        {{"name": "Location Name", "significance": "why this location matters"}}
    ],
    "factions": [
        {{"name": "Faction Name", "description": "what they want", "alignment": "good/evil/neutral"}}
    ],
    "key_events": [
        {{"event": "Event name", "description": "what happens", "significance": "why it matters to the story"}}
    ],
    "lore_terms": [
        {{"term": "Important Term", "definition": "what it means", "category": "magic/technology/history/culture"}}
    ]
}}

Only include information you are confident about. Set fields to empty arrays if uncertain.
No markdown, no explanation, ONLY valid JSON.
"""


def _get_cogitator():
    from workflows.cogitator import log, log_error, set_status, env, notify
    return {
        'log': log, 'log_error': log_error,
        'set_status': set_status, 'env': env, 'notify': notify,
    }


def _parse_lore_json(text: str) -> Optional[Dict]:
    cleaned = text.strip()
    cleaned = re.sub(r"```json\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"```\s*", "", cleaned).strip()

    brace_start = cleaned.find("{")
    brace_end = cleaned.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        cleaned = cleaned[brace_start:brace_end + 1]

    try:
        data = json.loads(cleaned)
        required = ["plot_summary", "characters", "locations", "factions", "key_events", "lore_terms"]
        for key in required:
            if key not in data:
                data[key] = [] if key != "plot_summary" else ""
        return data
    except (json.JSONDecodeError, TypeError):
        return None


def _call_gemini_lore(game_title: str, api_key: str) -> Optional[Dict]:
    prompt = GAME_LORE_PROMPT.format(game_title=game_title)
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 4096},
    }).encode()
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            r = json.loads(resp.read())
            text = r.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return _parse_lore_json(text)
    except Exception:
        return None


def _call_groq_lore(game_title: str, api_key: str) -> Optional[Dict]:
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        prompt = GAME_LORE_PROMPT.format(game_title=game_title)
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=4096,
        )
        return _parse_lore_json(resp.choices[0].message.content)
    except Exception:
        return None


def _fetch_game_lore(game_title: str) -> Optional[Dict]:
    try:
        from workflows.keychain_manager import get_gemini_keys, get_groq_keys
    except ImportError:
        from keychain_manager import get_gemini_keys, get_groq_keys

    gemini_keys = get_gemini_keys()
    groq_keys = get_groq_keys()
    if not gemini_keys and not groq_keys:
        return None

    results = [None, None]
    threads = []

    if gemini_keys:
        def _gemini():
            results[0] = _call_gemini_lore(game_title, gemini_keys[0])
        t = threading.Thread(target=_gemini)
        t.start()
        threads.append(t)

    if groq_keys:
        def _groq():
            results[1] = _call_groq_lore(game_title, groq_keys[0])
        t = threading.Thread(target=_groq)
        t.start()
        threads.append(t)

    for t in threads:
        t.join(timeout=35)

    return results[0] or results[1]


def _save_game_lore(lore_data: Dict, game_title: str):
    try:
        from workflows.context_manager import save_verified_context, load_verified_context
    except ImportError:
        from context_manager import save_verified_context, load_verified_context

    verified = load_verified_context(game_title)
    existing_context = verified.get("context", {}) if verified else {}
    existing_context["lore"] = lore_data
    save_verified_context(game_title, existing_context, merge=True)

    game_key = game_title.lower().replace(" ", "_")
    lore_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "Context", game_key,
    )
    os.makedirs(lore_dir, exist_ok=True)
    lore_path = os.path.join(lore_dir, "lore.md")

    with open(lore_path, "w") as f:
        f.write(f"# {game_title} - Game Lore\n\n")
        f.write("## Plot Summary\n\n")
        f.write(lore_data.get("plot_summary", "N/A"))
        f.write("\n\n## Characters\n\n")
        for c in lore_data.get("characters", []):
            name = c.get("name", "?")
            role = c.get("role", "?")
            aff = c.get("affiliation", "?")
            desc = c.get("description", "")
            f.write(f"- **{name}** ({role}, {aff}): {desc}\n")
        f.write("\n## Locations\n\n")
        for loc in lore_data.get("locations", []):
            f.write(f"- **{loc.get('name')}**: {loc.get('significance')}\n")
        f.write("\n## Factions\n\n")
        for fac in lore_data.get("factions", []):
            f.write(f"- **{fac.get('name')}** ({fac.get('alignment')}): {fac.get('description')}\n")
        f.write("\n## Key Events\n\n")
        for ev in lore_data.get("key_events", []):
            f.write(f"- **{ev.get('event')}**: {ev.get('description')} ({ev.get('significance')})\n")
        f.write("\n## Lore Terms\n\n")
        for term in lore_data.get("lore_terms", []):
            f.write(f"- **{term.get('term')}** ({term.get('category')}): {term.get('definition')}\n")


def phase_lore():
    c = _get_cogitator()
    game_title = c['env']("GAME_TITLE", "")
    if not game_title:
        c['log']("   Game lore: No GAME_TITLE set, skipping")
        return

    c['set_status']("Phase 3a: Fetching game lore...")
    c['log'](f"   Game lore: Fetching lore for '{game_title}'...")

    lore_data = _fetch_game_lore(game_title)
    if not lore_data:
        c['log_error']("   Game lore: Failed to fetch from LLM")
        return

    _save_game_lore(lore_data, game_title)
    char_count = len(lore_data.get("characters", []))
    loc_count = len(lore_data.get("locations", []))
    faction_count = len(lore_data.get("factions", []))
    c['log'](f"   Game lore: {char_count} characters, {loc_count} locations, {faction_count} factions")
    c['notify'](f"Game lore loaded: {char_count} chars, {loc_count} locs")
