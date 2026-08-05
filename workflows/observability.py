"""Lightweight phase timing / observability helpers."""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Dict, List

_PHASE_TIMINGS: List[Dict] = []


def reset_timings():
    _PHASE_TIMINGS.clear()


def get_timings() -> List[Dict]:
    return list(_PHASE_TIMINGS)


@contextmanager
def phase_timer(phase: int, name: str, log=None):
    start = time.time()
    entry = {"phase": phase, "name": name, "started_at": start, "duration_s": None, "ok": True}
    try:
        yield entry
    except Exception:
        entry["ok"] = False
        raise
    finally:
        entry["duration_s"] = round(time.time() - start, 2)
        _PHASE_TIMINGS.append(entry)
        if log:
            status = "ok" if entry["ok"] else "FAIL"
            log(f"[TIMING] Phase {phase} ({name}): {entry['duration_s']}s [{status}]")
