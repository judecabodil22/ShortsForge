"""
MemPalace wrapper for Cogitator.

Bridges the installed mempalace package (ChromaDB-backed memory) to
Cogitator's expected API for transcript mining, quality metrics,
memory retrieval, and context syncing.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import chromadb
from mempalace.config import MempalaceConfig
from mempalace.miner import add_drawer, chunk_text, get_collection, scan_project
from mempalace.searcher import search_memories

GAME_WING_PREFIX = "cogitator_"


class MemPalaceManager:
    """Manages MemPalace memory operations for Cogitator."""

    def __init__(self):
        self._config = MempalaceConfig()

    @property
    def palace_path(self) -> str:
        return self._config.palace_path

    # ── helpers ──────────────────────────────────────────────────────────

    def _game_wing(self, game_title: str) -> str:
        """Normalise a game title into a valid ChromaDB wing name."""
        safe = re.sub(r"[^a-zA-Z0-9_\- ]", "", game_title).strip().lower().replace(" ", "_")
        return f"{GAME_WING_PREFIX}{safe}" if safe else f"{GAME_WING_PREFIX}unknown"

    def _collection(self):
        return get_collection(self.palace_path)

    def _add(self, wing: str, room: str, content: str, source: str) -> int:
        """Add content as one or more drawers. Returns number added."""
        collection = self._collection()
        chunks = chunk_text(content, source)
        count = 0
        for chunk in chunks:
            if add_drawer(
                collection=collection,
                wing=wing,
                room=room,
                content=chunk["content"],
                source_file=source,
                chunk_index=chunk["chunk_index"],
                agent="cogitator",
            ):
                count += 1
        return count

    def _query(self, wing: str, room: str | None = None, n: int = 10) -> list:
        """Query memories for a wing/room."""
        try:
            result = search_memories(
                query="",
                palace_path=self.palace_path,
                wing=wing,
                room=room,
                n_results=n,
            )
            if "error" not in result:
                return result.get("results", [])
        except Exception:
            pass
        return []

    def _delete_wing(self, wing: str) -> bool:
        """Delete all drawers for a given wing."""
        try:
            collection = self._collection()
            results = collection.get(where={"wing": wing}, limit=100000)
            ids = results.get("ids", [])
            if ids:
                collection.delete(ids=ids)
            return True
        except Exception:
            return False

    # ── public API ────────────────────────────────────────────────────────

    def mine_transcript(self, transcript_or_path: str, game_title: str) -> dict:
        """Store transcript content as game-specific memory drawers."""
        if os.path.isfile(transcript_or_path):
            with open(transcript_or_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            source = transcript_or_path
        else:
            content = transcript_or_path
            source = f"transcript_{game_title}"

        wing = self._game_wing(game_title)
        count = self._add(wing, "transcripts", content, source)
        return {"status": "success", "drawers": count, "game": game_title}

    def get_game_memory(self, game_title: str) -> dict:
        """Retrieve stored memories for a game."""
        wing = self._game_wing(game_title)
        memories = self._query(wing, n=10)
        return {"success": True, "memories": memories}

    def add_quality_metric(self, game_title: str, metric: dict) -> None:
        """Store a quality metric as a drawer."""
        wing = self._game_wing(game_title)
        content = json.dumps(metric, indent=2)
        ts = metric.get("timestamp", datetime.now().isoformat())
        source = f"quality/{game_title}/{ts}"
        self._add(wing, "quality_metrics", content, source)

    def get_best_prompts(self, game_title: str, top_n: int = 3) -> list:
        """Find best-performing prompts from quality metrics."""
        wing = self._game_wing(game_title)
        results = self._query(wing, "quality_metrics", n=top_n * 3)

        items = []
        for r in results:
            try:
                m = json.loads(r["text"])
                if isinstance(m, dict):
                    items.append(m)
            except (json.JSONDecodeError, TypeError, KeyError):
                continue

        items.sort(
            key=lambda x: (x.get("factuality", 0) or 0) + (x.get("engagement", 0) or 0),
            reverse=True,
        )
        return [
            {
                "source": m.get("source", ""),
                "factuality": m.get("factuality", 0),
                "engagement": m.get("engagement", 0),
                "word_count": m.get("word_count", 0),
            }
            for m in items[:top_n]
        ]

    def status(self) -> dict:
        """Get palace status — drawer count per game/room."""
        try:
            client = chromadb.PersistentClient(path=self.palace_path)
            col = client.get_collection("mempalace_drawers")
            r = col.get(limit=100000, include=["metadatas"])
        except Exception as e:
            return {"total_drawers": 0, "games": {}, "error": str(e)}

        games: dict = {}
        for m in r["metadatas"]:
            wing = m.get("wing", "?")
            room = m.get("room", "?")
            game_key = wing.removeprefix(GAME_WING_PREFIX) if wing.startswith(GAME_WING_PREFIX) else wing
            if game_key not in games:
                games[game_key] = {}
            games[game_key][room] = games[game_key].get(room, 0) + 1

        return {"total_drawers": len(r["metadatas"]), "games": games}

    def clear_game_memory(self, game_title: str) -> bool:
        """Delete all drawers for a game."""
        wing = self._game_wing(game_title)
        return self._delete_wing(wing)

    def _run_command(self, args: list) -> tuple:
        """
        Run a mempalace CLI-style command programmatically.
        Returns (stdout, stderr, returncode).
        """
        if not args:
            return "", "No command", 1

        command = args[0]

        if command == "mine":
            dir_path = Path(args[1]).expanduser().resolve() if len(args) > 1 else None
            if not dir_path or not dir_path.is_dir():
                return "", f"Directory not found: {args[1] if len(args) > 1 else ''}", 1

            wing_override = None
            agent = "cogitator"
            limit = 0

            i = 2
            while i < len(args):
                if args[i] == "--wing" and i + 1 < len(args):
                    wing_override = args[i + 1]
                    i += 2
                elif args[i] == "--agent" and i + 1 < len(args):
                    agent = args[i + 1]
                    i += 2
                elif args[i] == "--limit" and i + 1 < len(args):
                    try:
                        limit = int(args[i + 1])
                    except ValueError:
                        pass
                    i += 2
                elif args[i] in ("--dry-run", "--mode", "projects", "docs", "convos"):
                    i += 2 if args[i] in ("--mode",) else 1
                else:
                    i += 1

            files = scan_project(str(dir_path))
            if limit > 0:
                files = files[:limit]

            collection = self._collection()
            rooms = [{"name": "general", "description": "Default room"}]

            total = 0
            from mempalace.miner import process_file

            for fp in files:
                total += process_file(
                    filepath=fp,
                    project_path=dir_path,
                    collection=collection,
                    wing=wing_override or "cogitator_context",
                    rooms=rooms,
                    agent=agent,
                    dry_run=False,
                )

            return f"Mined {total} drawers from {len(files)} files\n", "", 0

        if command == "status":
            s = self.status()
            out = f"MemPalace: {s['total_drawers']} total drawers\n"
            for game, rooms in sorted(s.get("games", {}).items()):
                out += f"  {game}: {rooms}\n"
            return out, "", 0

        # Fallback: run via subprocess
        try:
            result = subprocess.run(
                ["mempalace"] + args,
                capture_output=True,
                text=True,
                timeout=120,
            )
            return result.stdout, result.stderr, result.returncode
        except FileNotFoundError:
            return "", "mempalace: command not found", -1
        except subprocess.TimeoutExpired:
            return "", "mempalace: command timed out", -1


# ── singleton accessor ─────────────────────────────────────────────────────

_manager_instance: MemPalaceManager | None = None


def get_mempalace_manager() -> MemPalaceManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = MemPalaceManager()
    return _manager_instance
