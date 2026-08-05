"""Offline eval harness for title uniqueness / variety."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from workflows.title_variety import (
    detect_structure,
    is_too_similar,
    load_historical_titles,
    looks_generic,
    normalize_title,
)


def score_titles(titles: list[str], historical: list[str] | None = None) -> dict:
    historical = historical if historical is not None else load_historical_titles(60)
    results = []
    seen = list(historical)
    structures = {}
    for t in titles:
        norm = normalize_title(t)
        similar = is_too_similar(norm, seen)
        generic = looks_generic(norm)
        struct = detect_structure(t)
        structures[struct] = structures.get(struct, 0) + 1
        score = 1.0
        if similar:
            score -= 0.5
        if generic:
            score -= 0.3
        results.append(
            {
                "title": t,
                "normalized": norm,
                "structure": struct,
                "too_similar": similar,
                "generic": generic,
                "score": round(max(0.0, score), 2),
            }
        )
        seen.append(norm)
    avg = sum(r["score"] for r in results) / len(results) if results else 0.0
    return {
        "count": len(results),
        "avg_score": round(avg, 3),
        "structure_counts": structures,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate title variety")
    parser.add_argument("titles", nargs="*", help="Titles to score")
    parser.add_argument("--file", help="JSON file with list of titles")
    parser.add_argument("--scripts-dir", help="Scan scripts/*.txt for TITLE: lines")
    args = parser.parse_args()

    titles = list(args.titles or [])
    if args.file:
        data = json.loads(Path(args.file).read_text())
        titles.extend(data if isinstance(data, list) else data.get("titles", []))
    if args.scripts_dir:
        import re

        for p in Path(args.scripts_dir).glob("*.txt"):
            m = re.search(r"^TITLE:\s*(.+)$", p.read_text(), re.M)
            if m:
                titles.append(m.group(1).strip())

    if not titles:
        print("No titles provided", file=sys.stderr)
        sys.exit(1)

    report = score_titles(titles)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
