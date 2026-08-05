"""Title variety helpers for script generation.

Keeps the existing script pipeline intact while enforcing diverse titles
across a run (and against historical titles from the performance DB).
"""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence, Tuple


TITLE_STRUCTURES = (
    "question",  # What Made X Impossible?
    "statement",  # The One Rule That Broke Y
    "contrast",  # X Was Simple. Then Z Happened.
    "number",  # 3 Seconds That Ruined Everything
    "reveal",  # Why X Never Told Y the Truth
)

_GENERIC_PATTERNS = (
    re.compile(r"^the .+ of .+$", re.I),
    re.compile(r"^a (story|tale|journey) (of|about) .+$", re.I),
    re.compile(r"^everything you (need to )?know", re.I),
    re.compile(r"^top \d+", re.I),
)


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").lower().strip())


def word_overlap_ratio(a: str, b: str) -> float:
    wa = set(normalize_title(a).split())
    wb = set(normalize_title(b).split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


def is_too_similar(title: str, recent: Sequence[str], threshold: float = 0.55) -> bool:
    norm = normalize_title(title)
    for prev in recent:
        if word_overlap_ratio(norm, prev) >= threshold:
            return True
    return False


def looks_generic(title: str) -> bool:
    t = normalize_title(title)
    if len(t.split()) < 4 or len(t.split()) > 14:
        return True
    return any(p.search(t) for p in _GENERIC_PATTERNS)


def detect_structure(title: str) -> str:
    t = (title or "").strip()
    if t.endswith("?") or t.lower().startswith(("what ", "why ", "how ", "when ", "who ")):
        return "question"
    if re.search(r"\b\d+\b", t):
        return "number"
    if "." in t or " then " in t.lower() or " until " in t.lower():
        return "contrast"
    if t.lower().startswith(("why ", "the reason", "the secret")):
        return "reveal"
    return "statement"


def next_preferred_structure(used: Sequence[str]) -> str:
    counts = {s: 0 for s in TITLE_STRUCTURES}
    for u in used:
        counts[u] = counts.get(u, 0) + 1
    return min(TITLE_STRUCTURES, key=lambda s: counts.get(s, 0))


def load_historical_titles(limit: int = 40) -> List[str]:
    titles: List[str] = []
    try:
        from workflows.performance_database import get_connection

        conn = get_connection()
        rows = conn.execute(
            "SELECT title FROM scripts WHERE title IS NOT NULL AND title != '' "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        titles = [normalize_title(r[0] if not isinstance(r, dict) else r["title"]) for r in rows]
        conn.close()
    except Exception:
        pass
    return [t for t in titles if t]


def build_title_guidance(
    recent_titles: Sequence[str],
    used_structures: Sequence[str],
    historical: Optional[Sequence[str]] = None,
) -> str:
    """Structure-only guidance. Ban lists belong in the RECENT TITLES block."""
    preferred = next_preferred_structure(used_structures)
    lines = [
        f"TITLE STRUCTURE THIS ROUND: prefer a {preferred} title.",
        f"Available structures: {', '.join(TITLE_STRUCTURES)}.",
        "Rotate structures across scripts — do not reuse the same pattern back-to-back.",
        "Must reference a SPECIFIC detail from THIS transcript segment.",
    ]
    # historical/recent_titles kept in signature for callers; bans are passed separately
    _ = recent_titles, historical
    return "\n".join(lines)


def enforce_title_variety(
    script: str,
    recent_titles: Sequence[str],
    used_structures: Optional[List[str]] = None,
) -> Tuple[str, str, str]:
    """Return (script, title, structure). May rewrite TITLE line if too similar/generic."""
    used_structures = used_structures if used_structures is not None else []
    m = re.search(r"^TITLE:\s*(.+)$", script or "", re.MULTILINE)
    title = m.group(1).strip() if m else ""
    structure = detect_structure(title) if title else next_preferred_structure(used_structures)

    if title and (is_too_similar(title, recent_titles) or looks_generic(title)):
        # Soft rewrite: append a distinguishing marker from preferred structure
        preferred = next_preferred_structure(used_structures)
        if preferred == "question" and not title.endswith("?"):
            title = f"What Happened When {title.rstrip('.!?')}?"
        elif preferred == "contrast":
            title = f"{title.rstrip('.!?')}. Then Everything Changed"
        elif preferred == "number":
            title = f"The Moment That Changed Everything"
        elif preferred == "reveal":
            title = f"Why {title.rstrip('.!?')}"
        else:
            title = title.rstrip(".!?")
        structure = detect_structure(title)
        if m:
            script = script[: m.start()] + f"TITLE: {title}" + script[m.end() :]
        else:
            script = f"TITLE: {title}\n\n{script}"

    used_structures.append(structure)
    return script, title, structure


def format_recent_for_prompt(titles: Iterable[str]) -> str:
    return "\n".join(t for t in titles if t)
