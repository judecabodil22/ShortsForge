import os
import re
from typing import Any, Dict, List

from workflows.constants import WORKSPACE, CONTEXT_DIR

try:
    from rapidfuzz import fuzz as _fuzz
except ImportError:
    _fuzz = None


def _game_title_from_env() -> str:
    game_title = "default"
    env_path = os.path.join(WORKSPACE, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if line.strip().startswith("GAME_TITLE="):
                    game_title = line.strip().split("=", 1)[1].strip().strip('"')
                    break
    return game_title or "default"


def _item_name(item: Any) -> str:
    if isinstance(item, dict):
        return (
            item.get("name")
            or item.get("term")
            or item.get("from")
            or str(item.get("id", ""))
        ).strip()
    return str(item).strip()


def _relationship_text(rel: Any) -> Any:
    if isinstance(rel, dict):
        # Prefer structured form for downstream consumers
        if rel.get("from") and rel.get("to"):
            return {
                "from": rel.get("from"),
                "to": rel.get("to"),
                "relationship": rel.get("relationship")
                or rel.get("category")
                or "related",
            }
        name = rel.get("name") or ""
        if name:
            return name
    return rel


def _cs_load_context():
    """Load context from verified_context.json only (no Obsidian markdown)."""
    ctx = {
        "characters": [],
        "locations": [],
        "key_terms": [],
        "relationships": [],
        "processed_transcripts": [],
        "previous_scripts": [],
        "character_aliases": {},
        "location_aliases": {},
        "lore": {},
        "title": "",
    }

    game_title = _game_title_from_env()
    try:
        from workflows.context_manager_v2 import load_verified_context

        verified = load_verified_context(game_title)
        if not isinstance(verified, dict):
            return ctx

        # load_verified_context returns item dicts; also accept nested "context"
        source = verified.get("context") if isinstance(verified.get("context"), dict) else verified

        for key in ("characters", "locations", "key_terms"):
            names = []
            for item in source.get(key, []) or []:
                name = _item_name(item)
                if name and name not in names:
                    names.append(name)
            ctx[key] = names

        rels = []
        for rel in source.get("relationships", []) or []:
            parsed = _relationship_text(rel)
            if parsed and parsed not in rels:
                # Skip self-referential relationships
                if isinstance(parsed, dict):
                    a = (parsed.get("from") or "").strip().lower()
                    b = (parsed.get("to") or "").strip().lower()
                    if a and b and a == b:
                        continue
                rels.append(parsed)
        ctx["relationships"] = rels

        # Aliases / lore may live on the raw verified file
        try:
            import json

            path = os.path.join(CONTEXT_DIR, "verified_context.json")
            if os.path.exists(path):
                with open(path) as f:
                    raw = json.load(f)
                game_key = game_title.lower().replace(" ", "_").strip()
                entry = raw.get(game_key, {}) if isinstance(raw, dict) else {}
                if isinstance(entry, dict):
                    ctx["character_aliases"] = entry.get("character_aliases", {}) or {}
                    ctx["location_aliases"] = entry.get("location_aliases", {}) or {}
                    ctx["lore"] = entry.get("lore", {}) or {}
                    ctx["title"] = entry.get("title", "") or ""
                    ctx["processed_transcripts"] = entry.get("processed_transcripts", []) or []
                    ctx["previous_scripts"] = entry.get("previous_scripts", []) or []
        except Exception:
            pass

        if verified.get("character_aliases"):
            ctx["character_aliases"] = verified["character_aliases"]
        if verified.get("location_aliases"):
            ctx["location_aliases"] = verified["location_aliases"]
        if verified.get("lore"):
            ctx["lore"] = verified["lore"]

    except Exception:
        pass

    return ctx


def _relationship_key(rel: Any) -> tuple:
    if isinstance(rel, dict):
        return (rel.get("from", "").strip().lower(), rel.get("to", "").strip().lower())
    if isinstance(rel, str) and " are " in rel:
        parts = rel.split(" are ", 1)
        return (parts[0].strip().lower(), parts[1].strip().lower())
    return ("", "")


def _fuzzy_in(item: str, existing: list[str], threshold: int = 80) -> tuple[bool, str | None]:
    """Check if item fuzzy-matches any entry in existing list."""
    if not existing or not _fuzz:
        return False, None
    item_lower = item.lower().strip()
    for entry in existing:
        entry_lower = entry.lower()
        if item_lower == entry_lower:
            return True, entry
        ratio = _fuzz.token_sort_ratio(item_lower, entry_lower)
        if ratio >= threshold:
            canonical = entry if len(entry) >= len(item) else item
            return True, canonical
    return False, None


def merge_context_dicts(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """Union list fields and relationships; overlay wins on relationship conflicts."""
    out = dict(base or {})
    for key in ("characters", "locations", "key_terms", "processed_transcripts", "previous_scripts"):
        merged = []
        for item in list(base.get(key, []) or []) + list(overlay.get(key, []) or []):
            if not item:
                continue
            name = _item_name(item) if not isinstance(item, str) else item
            is_dup, _ = _fuzzy_in(str(name), [str(x) if isinstance(x, str) else _item_name(x) for x in merged])
            if not is_dup:
                merged.append(item)
        out[key] = merged

    rel_map: Dict[tuple, Any] = {}
    for rel in list(base.get("relationships", []) or []):
        key = _relationship_key(rel)
        if key[0] and key[1] and key[0] != key[1]:
            rel_map[key] = rel
    for rel in list(overlay.get("relationships", []) or []):
        key = _relationship_key(rel)
        if key[0] and key[1] and key[0] != key[1]:
            rel_map[key] = rel
    out["relationships"] = list(rel_map.values())

    overlay_title = (overlay.get("title") or "").strip()
    if overlay_title:
        out["title"] = overlay_title
    elif base.get("title"):
        out["title"] = base.get("title")

    for alias_key in ("character_aliases", "location_aliases"):
        merged_aliases = dict(base.get(alias_key) or {})
        merged_aliases.update(overlay.get(alias_key) or {})
        if merged_aliases:
            out[alias_key] = merged_aliases

    if overlay.get("lore"):
        out["lore"] = overlay["lore"]
    elif base.get("lore"):
        out["lore"] = base["lore"]

    return out
