"""Watch Tiktok Analytics/ for new CSV exports and import them."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from workflows.constants import WORKSPACE

ANALYTICS_DIR = os.path.join(WORKSPACE, "Tiktok Analytics")
_STATE_FILE = os.path.join(WORKSPACE, ".cogitator", "tiktok_import_state.json")


def _load_state() -> Dict[str, float]:
    import json

    if not os.path.exists(_STATE_FILE):
        return {}
    try:
        with open(_STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(state: Dict[str, float]) -> None:
    import json

    os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
    with open(_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def scan_new_csvs() -> List[Path]:
    if not os.path.isdir(ANALYTICS_DIR):
        return []
    state = _load_state()
    found = []
    for p in Path(ANALYTICS_DIR).glob("*.csv"):
        mtime = p.stat().st_mtime
        key = str(p)
        if state.get(key) != mtime:
            found.append(p)
    return sorted(found, key=lambda x: x.stat().st_mtime)


def auto_import_tiktok() -> Dict[str, Any]:
    """Import any new/changed TikTok analytics CSVs via directory import."""
    new_files = scan_new_csvs()
    if not new_files and not os.path.isdir(ANALYTICS_DIR):
        return {"success": True, "imported": [], "errors": [], "count": 0, "skipped": True}

    try:
        from workflows.tiktok_analytics import import_tiktok_data
    except Exception as e:
        return {"success": False, "error": f"tiktok_analytics unavailable: {e}", "imported": []}

    state = _load_state()
    try:
        result = import_tiktok_data(ANALYTICS_DIR)
        for path in new_files or Path(ANALYTICS_DIR).glob("*.csv"):
            try:
                state[str(path)] = Path(path).stat().st_mtime
            except Exception:
                pass
        _save_state(state)
        return {
            "success": True,
            "imported": [p.name if hasattr(p, "name") else os.path.basename(str(p)) for p in new_files],
            "errors": [],
            "count": len(new_files),
            "result": result,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "imported": [], "errors": [str(e)], "count": 0}
