#!/usr/bin/env python3
"""
Cogitator Context Management System v2
Advanced context management with editor, search, and analytics.
"""
import os
import json
import re
import uuid
import hashlib
import tempfile
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

from workflows.constants import WORKSPACE, CONTEXT_DIR
import threading

logger = logging.getLogger(__name__)

# Thread lock for verified context updates
_context_file_lock = threading.Lock()

VERIFIED_CONTEXT_FILE = os.path.join(CONTEXT_DIR, "verified_context.json")
HISTORY_DIR = os.path.join(CONTEXT_DIR, "history")
SCHEMA_FILE = os.path.join(CONTEXT_DIR, "schema.json")
DELETED_ENTITIES_FILE = os.path.join(CONTEXT_DIR, "deleted_entities.json")


def _load_deleted_entities() -> Dict[str, List[str]]:
    """Load the list of deleted entities per game."""
    if not os.path.exists(DELETED_ENTITIES_FILE):
        return {}
    try:
        with open(DELETED_ENTITIES_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_deleted_entities(data: Dict[str, List[str]]) -> None:
    """Save the list of deleted entities per game (atomic write)."""
    os.makedirs(CONTEXT_DIR, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=CONTEXT_DIR, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, DELETED_ENTITIES_FILE)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _add_deleted_entity(game_key: str, item_id: str, item_name: str) -> None:
    """Record a deleted entity so it won't be re-added by pipeline."""
    deleted = _load_deleted_entities()
    if game_key not in deleted:
        deleted[game_key] = []
    entry = f"{item_id}|{item_name}"
    if entry not in deleted[game_key]:
        deleted[game_key].append(entry)
    _save_deleted_entities(deleted)


def _is_entity_deleted(game_key: str, item_id: str = None, item_name: str = None) -> bool:
    """Check if an entity has been manually deleted."""
    deleted = _load_deleted_entities()
    if game_key not in deleted:
        return False
    for entry in deleted[game_key]:
        parts = entry.split("|", 1)
        if len(parts) == 2:
            eid, ename = parts
            if item_id and eid == item_id:
                return True
            if item_name and ename.lower() == item_name.lower():
                return True
    return False


def _deterministic_id(game_key: str, item_type: str, name: str) -> str:
    """Generate a stable, deterministic ID from game_key + type + name."""
    raw = f"{game_key}:{item_type}:{name.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()


class ContextItem:
    """Represents a single context item (character, location, term, relationship)."""
    
    # Minimum transcript appearances before admission
    ADMISSION_THRESHOLD = 2

    def __init__(
        self,
        game_key: str,
        item_type: str,
        name: str,
        category: str = "",
        description: str = "",
        source: str = "manual",
        tags: List[str] = None,
        aliases: List[str] = None,
        metadata: Dict = None
    ):
        self.id = str(uuid.uuid4())
        self.game_key = game_key
        self.type = item_type  # character, location, term, relationship
        self.name = name
        self.category = category
        self.description = description
        self.source = source
        self.tags = tags or []
        self.aliases = aliases or []
        self.metadata = metadata or {}
        self.metadata.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        self.metadata.setdefault("updated_at", datetime.now(timezone.utc).isoformat())
        self.metadata.setdefault("confidence", 1.0)
        self.metadata.setdefault("validation_count", 0)
        self.metadata.setdefault("transcript_mentions", 0)
        self.metadata.setdefault("first_seen_transcript", "")
        self.metadata.setdefault("admission_threshold_met", False)
        self.verified = self.source == "manual"  # manually added items are inherently verified
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "game_key": self.game_key,
            "type": self.type,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "source": self.source,
            "tags": self.tags,
            "aliases": self.aliases,
            "metadata": self.metadata,
            "verified": self.verified,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ContextItem":
        item = cls(
            game_key=data.get("game_key", ""),
            item_type=data.get("type", "character"),
            name=data.get("name", ""),
            category=data.get("category", ""),
            description=data.get("description", ""),
            source=data.get("source", "manual"),
            tags=data.get("tags", []),
            aliases=data.get("aliases", []),
            metadata=data.get("metadata", {})
        )
        item.id = data.get("id", item.id)
        item.verified = data.get("verified", item.source == "manual")
        return item
    
    def update(self, **kwargs):
        """Update fields and timestamp."""
        for key, value in kwargs.items():
            if key == "metadata":
                self.metadata.update(value)
            elif hasattr(self, key):
                setattr(self, key, value)
        self.metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    def record_mention(self, transcript_name: str = ""):
        """Increment transcript mention count and check admission threshold."""
        self.metadata["transcript_mentions"] = self.metadata.get("transcript_mentions", 0) + 1
        if not self.metadata.get("first_seen_transcript") and transcript_name:
            self.metadata["first_seen_transcript"] = transcript_name
        if self.metadata["transcript_mentions"] >= self.ADMISSION_THRESHOLD:
            self.metadata["admission_threshold_met"] = True
            self.metadata["confidence"] = min(1.0, self.metadata.get("confidence", 0.5) + 0.2)
    
    @property
    def is_admitted(self) -> bool:
        """Check if entity meets admission threshold."""
        return self.metadata.get("admission_threshold_met", False) or self.source == "manual"
    
    def validate(self) -> List[str]:
        """Validate the item and return list of errors."""
        errors = []
        if not self.name.strip():
            errors.append("Name is required")
        if self.type not in ["character", "location", "term", "relationship"]:
            errors.append(f"Invalid type: {self.type}")
        return errors


def _filter_deleted_items(game_key: str, items: List[ContextItem]) -> List[ContextItem]:
    """Remove items that have been manually deleted."""
    return [item for item in items if not _is_entity_deleted(game_key, item_id=item.id, item_name=item.name)]


class ContextHistory:
    """Tracks all changes to context items."""
    
    def __init__(self, game_key: str):
        self.game_key = game_key
        self.history_file = os.path.join(HISTORY_DIR, f"{game_key}.jsonl")
        os.makedirs(HISTORY_DIR, exist_ok=True)
    
    def add_entry(self, item_id: str, action: str, before: Dict = None, after: Dict = None, user: str = "manual"):
        """Add a history entry."""
        entry = {
            "id": str(uuid.uuid4()),
            "item_id": item_id,
            "action": action,  # create, update, delete
            "before": before,
            "after": after,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": user
        }
        try:
            with open(self.history_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            print(f"Warning: Could not write history entry: {e}")
    
    def get_history(self, item_id: str = None, limit: int = 100) -> List[Dict]:
        """Get history entries, optionally filtered by item_id. Returns most recent first."""
        if not os.path.exists(self.history_file):
            return []
        
        entries = []
        try:
            with open(self.history_file, "r") as f:
                for line in f:
                    entry = json.loads(line.strip())
                    if item_id is None or entry.get("item_id") == item_id:
                        entries.append(entry)
        except Exception:
            pass
        entries.reverse()
        return entries[:limit]


class ContextManagerV2:
    """Main context management class with editor, search, and analytics."""
    
    def __init__(self):
        self.contexts: Dict[str, Dict[str, ContextItem]] = {}  # game_key -> {type -> [items]}
        self.load_all_contexts()
    
    def load_all_contexts(self):
        """Load all games' contexts from verified_context.json.
        
        Uses file mtime caching to avoid re-reading when the file hasn't changed.
        """
        import time
        if not os.path.exists(VERIFIED_CONTEXT_FILE):
            return
        
        # Check if file has changed since last load
        current_mtime = os.path.getmtime(VERIFIED_CONTEXT_FILE)
        if hasattr(self, '_context_mtime') and self._context_mtime == current_mtime:
            return  # File unchanged, skip reload
        
        try:
            with open(VERIFIED_CONTEXT_FILE, "r") as f:
                data = json.load(f)
            
            for game_key, game_data in data.items():
                ctx = game_data.get("context", {})
                self.contexts[game_key] = {
                    "character": [],
                    "location": [],
                    "term": [],
                    "relationship": []
                }
                
                for char in ctx.get("characters", []):
                    if isinstance(char, dict):
                        item = ContextItem.from_dict(char)
                        item.game_key = game_key
                        item.type = "character"
                    else:
                        item = ContextItem(game_key, "character", str(char))
                        item.id = _deterministic_id(game_key, "character", str(char))
                    self.contexts[game_key]["character"].append(item)
                
                for loc in ctx.get("locations", []):
                    if isinstance(loc, dict):
                        item = ContextItem.from_dict(loc)
                        item.game_key = game_key
                        item.type = "location"
                    else:
                        item = ContextItem(game_key, "location", str(loc))
                        item.id = _deterministic_id(game_key, "location", str(loc))
                    self.contexts[game_key]["location"].append(item)
                
                for term in ctx.get("key_terms", []):
                    if isinstance(term, dict):
                        item = ContextItem.from_dict(term)
                        item.game_key = game_key
                        item.type = "term"
                    else:
                        item = ContextItem(game_key, "term", str(term))
                        item.id = _deterministic_id(game_key, "term", str(term))
                    self.contexts[game_key]["term"].append(item)
                
                for rel in ctx.get("relationships", []):
                    if isinstance(rel, dict) and "name" in rel:
                        item = ContextItem.from_dict(rel)
                        item.game_key = game_key
                        item.type = "relationship"
                    elif isinstance(rel, dict):
                        from_name = (rel.get("from") or "").strip()
                        to_name = (rel.get("to") or "").strip()
                        rel_type = (rel.get("relationship") or rel.get("type") or "").strip()
                        label = f"{from_name} ↔ {to_name}" if from_name and to_name else from_name or to_name or "relationship"
                        item = ContextItem(
                            game_key,
                            "relationship",
                            label,
                            category=rel_type,
                            metadata={
                                "from": from_name,
                                "to": to_name,
                                "relationship": rel_type,
                            },
                        )
                    elif isinstance(rel, str):
                        # Parse legacy string format "X and Y are Z"
                        m = re.match(r"^(.+?)\s+and\s+(.+?)\s+are\s+(.+)$", rel)
                        if m:
                            from_n, to_n, rel_type = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
                            label = f"{from_n} ↔ {to_n}"
                            item = ContextItem(
                                game_key, "relationship", label,
                                category=rel_type,
                                metadata={"from": from_n, "to": to_n, "relationship": rel_type},
                            )
                        else:
                            item = ContextItem(game_key, "relationship", rel)
                            item.id = _deterministic_id(game_key, "relationship", rel)
                    else:
                        item = ContextItem(game_key, "relationship", str(rel))
                        item.id = _deterministic_id(game_key, "relationship", str(rel))
                    self.contexts[game_key]["relationship"].append(item)

            # Track file mtime to skip future reloads if unchanged
            self._context_mtime = current_mtime
        except Exception as e:
            print(f"Error loading contexts: {e}")

    def get_games(self) -> List[str]:
        """Get list of all game keys."""
        return list(self.contexts.keys())
    
    def get_context_items(self, game_key: str, item_type: str = None) -> List[ContextItem]:
        """Get all context items for a game, optionally filtered by type.
        
        Excludes items that have been manually deleted.
        """
        if game_key not in self.contexts:
            return []
        if item_type:
            return _filter_deleted_items(game_key, self.contexts.get(game_key, {}).get(item_type, []))
        all_items = []
        for items in self.contexts.get(game_key, {}).values():
            all_items.extend(items)
        return _filter_deleted_items(game_key, all_items)
    
    def get_item(self, game_key: str, item_id: str) -> Optional[ContextItem]:
        """Get a single context item by ID."""
        for items in self.contexts.get(game_key, {}).values():
            for item in items:
                if item.id == item_id:
                    return item
        return None
    
    def create_item(self, game_key: str, item_type: str, name: str, **kwargs) -> ContextItem:
        """Create a new context item."""
        item = ContextItem(game_key, item_type, name, **kwargs)
        
        if game_key not in self.contexts:
            self.contexts[game_key] = {
                "character": [], "location": [], "term": [], "relationship": []
            }
        
        self.contexts[game_key].setdefault(item_type, []).append(item)
        
        # Add history entry
        history = ContextHistory(game_key)
        history.add_entry(item.id, "create", after=item.to_dict())
        
        self.save_context(game_key)
        return item
    
    def update_item(self, game_key: str, item_id: str, **kwargs) -> Optional[ContextItem]:
        """Update an existing context item."""
        item = self.get_item(game_key, item_id)
        if not item:
            return None
        
        before = item.to_dict()
        item.update(**kwargs)
        
        history = ContextHistory(game_key)
        history.add_entry(item.id, "update", before=before, after=item.to_dict())
        
        self.save_context(game_key)
        return item
    
    def delete_item(self, game_key: str, item_id: str) -> bool:
        """Delete a context item."""
        item = self.get_item(game_key, item_id)
        if not item:
            return False
        
        before = item.to_dict()
        item_type = item.type
        self.contexts[game_key][item_type] = [
            i for i in self.contexts[game_key].get(item_type, [])
            if i.id != item_id
        ]
        
        # Record deletion so pipeline won't re-add this entity
        _add_deleted_entity(game_key, item.id, item.name)
        
        history = ContextHistory(game_key)
        history.add_entry(item_id, "delete", before=before)
        
        self.save_context(game_key)
        return True
    
    def save_context(self, game_key: str):
        """Save context to verified_context.json (atomic write)."""
        if game_key not in self.contexts:
            return
        
        all_data = {}
        if os.path.exists(VERIFIED_CONTEXT_FILE):
            try:
                with open(VERIFIED_CONTEXT_FILE, "r") as f:
                    all_data = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        
        ctx = {
            "characters": [i.to_dict() for i in self.contexts[game_key].get("character", [])],
            "locations": [i.to_dict() for i in self.contexts[game_key].get("location", [])],
            "key_terms": [i.to_dict() for i in self.contexts[game_key].get("term", [])],
            "relationships": [i.to_dict() for i in self.contexts[game_key].get("relationship", [])]
        }
        
        all_data[game_key] = {
            "context": ctx,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "source": "context_manager_v2"
        }
        
        os.makedirs(CONTEXT_DIR, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=CONTEXT_DIR, suffix='.json')
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(all_data, f, indent=2)
            os.replace(tmp_path, VERIFIED_CONTEXT_FILE)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    
    def search(
        self,
        query: str = "",
        game_key: str = None,
        item_type: str = None,
        tags: List[str] = None
    ) -> List[ContextItem]:
        """Search context items with filters."""
        results = []
        
        games = [game_key] if game_key else self.get_games()
        
        for gk in games:
            for item in self.get_context_items(gk, item_type):
                # Filter by query
                if query:
                    q_lower = query.lower()
                    if (q_lower not in item.name.lower() and
                        q_lower not in item.description.lower() and
                        q_lower not in item.category.lower()):
                        continue
                
                # Filter by tags
                if tags and not any(t.lower() in [tag.lower() for tag in item.tags] for t in tags):
                    continue
                
                results.append(item)
        
        return results
    
    def get_analytics(self, game_key: str = None) -> Dict:
        """Get analytics data for context."""
        analytics = {
            "total_items": 0,
            "by_type": {},
            "by_source": {},
            "recent_activity": [],
            "games": []
        }
        
        games = [game_key] if game_key else self.get_games()
        
        for gk in games:
            game_stats = {"character": 0, "location": 0, "term": 0, "relationship": 0}
            
            for item_type, items in self.contexts.get(gk, {}).items():
                count = len(items)
                game_stats[item_type] = count
                analytics["total_items"] += count
                analytics["by_type"][item_type] = analytics["by_type"].get(item_type, 0) + count
                
                for item in items:
                    source = getattr(item, "metadata", {}).get("source", "manual") if hasattr(item, "metadata") else "manual"
                    analytics["by_source"][source] = analytics["by_source"].get(source, 0) + 1
            
            # Get recent history
            history = ContextHistory(gk)
            recent = history.get_history(limit=10)
            
            analytics["games"].append({
                "game_key": gk,
                "stats": game_stats,
                "recent_changes": len(recent)
            })
        
        return analytics
    
    def get_history(self, game_key: str, item_id: str = None, limit: int = 50) -> List[Dict]:
        """Get context history."""
        history = ContextHistory(game_key)
        return history.get_history(item_id, limit)
    
    def import_items(self, game_key: str, items: List[Dict]) -> Dict:
        """Import context items from dict list."""
        created = 0
        errors = []
        
        for item_data in items:
            try:
                item_type = item_data.get("type", "character")
                name = item_data.get("name", "")
                if not name:
                    errors.append("Missing name")
                    continue
                
                self.create_item(
                    game_key,
                    item_type,
                    name,
                    category=item_data.get("category", ""),
                    description=item_data.get("description", ""),
                    tags=item_data.get("tags", []),
                    source="imported"
                )
                created += 1
            except Exception as e:
                errors.append(str(e))
        
        return {"created": created, "errors": errors}
    
    def export_items(self, game_key: str, item_type: str = None) -> List[Dict]:
        """Export context items to dict list."""
        items = self.get_context_items(game_key, item_type)
        return [item.to_dict() for item in items]


# Global instance with thread-safe singleton
_context_manager = None
_context_manager_lock = threading.Lock()

def get_context_manager() -> ContextManagerV2:
    """Get or create the global context manager instance (thread-safe)."""
    global _context_manager
    if _context_manager is None:
        with _context_manager_lock:
            if _context_manager is None:
                _context_manager = ContextManagerV2()
    return _context_manager


# Convenience functions
def list_games() -> List[str]:
    return get_context_manager().get_games()

def get_items(game_key: str, item_type: str = None) -> List[ContextItem]:
    items = get_context_manager().get_context_items(game_key, item_type)
    return _filter_deleted_items(game_key, items)

def create_item(game_key: str, item_type: str, name: str, **kwargs) -> ContextItem:
    return get_context_manager().create_item(game_key, item_type, name, **kwargs)

def update_item(game_key: str, item_id: str, **kwargs) -> Optional[ContextItem]:
    return get_context_manager().update_item(game_key, item_id, **kwargs)

def delete_item(game_key: str, item_id: str) -> bool:
    return get_context_manager().delete_item(game_key, item_id)

def search_context(query: str = "", game_key: str = None, item_type: str = None) -> List[ContextItem]:
    return get_context_manager().search(query, game_key, item_type)

def get_context_analytics(game_key: str = None) -> Dict:
    return get_context_manager().get_analytics(game_key)

def get_item_history(game_key: str, item_id: str = None) -> List[Dict]:
    return get_context_manager().get_history(game_key, item_id)

def import_context(game_key: str, items: List[Dict]) -> Dict:
    return get_context_manager().import_items(game_key, items)

def export_context(game_key: str, item_type: str = None) -> List[Dict]:
    return get_context_manager().export_items(game_key, item_type)


# ─── v1-compatible facade (unified interface for pipeline) ────────────────────

def load_verified_context(game_title: str) -> Dict[str, Any]:
    """Load verified context for a game (v1-compatible)."""
    cm = get_context_manager()
    cm.load_all_contexts()
    game_key = game_title.lower().replace(" ", "_").strip()
    if game_key not in cm.contexts:
        return {}
    ctx = cm.contexts[game_key]
    return {
        "characters": [i.to_dict() for i in ctx.get("character", [])],
        "locations": [i.to_dict() for i in ctx.get("location", [])],
        "key_terms": [i.to_dict() for i in ctx.get("term", [])],
        "relationships": [i.to_dict() for i in ctx.get("relationship", [])],
    }


def save_verified_context(game_title: str, context: Dict[str, Any], merge: bool = False) -> None:
    """Save verified context for a game (v1-compatible).
    
    Stores raw dict format for backward compatibility with v1 consumers.
    Filters out manually deleted entities so they don't reappear after pipeline runs.
    """
    cm = get_context_manager()
    game_key = game_title.lower().replace(" ", "_").strip()
    
    # Filter out deleted entities from the context being saved
    deleted = _load_deleted_entities()
    if game_key in deleted:
        deleted_entries = deleted[game_key]
        deleted_ids = set()
        deleted_names = set()
        for entry in deleted_entries:
            parts = entry.split("|", 1)
            if len(parts) == 2:
                deleted_ids.add(parts[0])
                deleted_names.add(parts[1].lower())
        
        def should_keep(item_list: List[Dict], name_key: str = "name", id_key: str = "id") -> List[Dict]:
            return [
                item for item in item_list
                if item.get(id_key) not in deleted_ids
                and item.get(name_key, "").lower() not in deleted_names
            ]
        
        context["characters"] = should_keep(context.get("characters", []))
        context["locations"] = should_keep(context.get("locations", []))
        context["key_terms"] = should_keep(context.get("key_terms", []))
        context["relationships"] = should_keep(context.get("relationships", []))
    
    if merge:
        cm.load_all_contexts()
        existing = cm.contexts.get(game_key, {})
        from workflows.context_utils import merge_context_dicts
        raw_existing = {
            "characters": [i.to_dict() if hasattr(i, 'to_dict') else i for i in existing.get("character", [])],
            "locations": [i.to_dict() if hasattr(i, 'to_dict') else i for i in existing.get("location", [])],
            "key_terms": [i.to_dict() if hasattr(i, 'to_dict') else i for i in existing.get("term", [])],
            "relationships": [i.to_dict() if hasattr(i, 'to_dict') else i for i in existing.get("relationship", [])],
        }
        context = merge_context_dicts(raw_existing, context)
    
    # Store as raw dict (v1 format) for backward compatibility
    import json
    all_data = {}
    if os.path.exists(VERIFIED_CONTEXT_FILE):
        try:
            with open(VERIFIED_CONTEXT_FILE, "r") as f:
                all_data = json.load(f)
        except Exception as e:
            logger.debug(f"Could not read verified context file: {e}")
            pass
    
    all_data[game_key] = {
        "context": context,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "source": "user_approved"
    }
    
    os.makedirs(CONTEXT_DIR, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=CONTEXT_DIR, suffix='.json')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(all_data, f, indent=2)
        os.replace(tmp_path, VERIFIED_CONTEXT_FILE)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    
    # Invalidate cache so next load picks up changes
    if hasattr(cm, '_context_mtime'):
        del cm._context_mtime


def clear_verified_context(game_title: str) -> None:
    """Clear verified context for a game (v1-compatible)."""
    import json
    game_key = game_title.lower().replace(" ", "_").strip()
    if not os.path.exists(VERIFIED_CONTEXT_FILE):
        return
    try:
        with open(VERIFIED_CONTEXT_FILE, "r") as f:
            all_data = json.load(f)
        if game_key in all_data:
            del all_data[game_key]
            fd, tmp_path = tempfile.mkstemp(dir=CONTEXT_DIR, suffix='.json')
            try:
                with os.fdopen(fd, 'w') as f:
                    json.dump(all_data, f, indent=2)
                os.replace(tmp_path, VERIFIED_CONTEXT_FILE)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
    except Exception:
        pass
    
    cm = get_context_manager()
    if game_key in cm.contexts:
        del cm.contexts[game_key]
    if hasattr(cm, '_context_mtime'):
        del cm._context_mtime


def get_verified_context_for_validation(game_title: str) -> Dict[str, Any]:
    """Get context for validation (v1-compatible)."""
    return load_verified_context(game_title)


def compare_context_with_history(game_title: str, new_context: Dict[str, Any]) -> Dict[str, Any]:
    """Compare new context with history (v1-compatible stub)."""
    return {"changes": [], "game": game_title}


def format_context_for_confirmation(game_title: str, context: Dict[str, Any]) -> str:
    """Format context for confirmation (v1-compatible)."""
    lines = [f"Context for {game_title}:"]
    for key, items in context.items():
        if isinstance(items, list):
            lines.append(f"\n{key}:")
            for item in items:
                if isinstance(item, dict):
                    lines.append(f"  - {item.get('name', str(item))}")
                else:
                    lines.append(f"  - {item}")
    return "\n".join(lines)


def is_first_run(game_title: str) -> bool:
    """Check if this is the first context run for a game (v1-compatible)."""
    game_key = game_title.lower().replace(" ", "_").strip()
    if not os.path.exists(VERIFIED_CONTEXT_FILE):
        return True
    try:
        with open(VERIFIED_CONTEXT_FILE) as f:
            data = json.load(f)
        return game_key not in data
    except (json.JSONDecodeError, OSError):
        return True



def get_context_sources_summary(game_key: str) -> dict:
    """Inventory counts across verified JSON, markdown, MemPalace, and transcripts."""
    from workflows.mempalace_integration import get_mempalace_text_chunks
    import os
    
    verified = load_verified_context(game_key)
    ctx = verified if verified else {}
    mp_chunks = get_mempalace_text_chunks(game_key)
    
    transcripts_dir = os.path.join(WORKSPACE, "transcripts")
    transcript_files = []
    if os.path.isdir(transcripts_dir):
        transcript_files = [f for f in os.listdir(transcripts_dir) if f.endswith(".json")]
        
    return {
        "game_key": game_key,
        "verified": {
            "characters": len(ctx.get("characters", [])),
            "locations": len(ctx.get("locations", [])),
            "key_terms": len(ctx.get("key_terms", [])),
            "relationships": len(ctx.get("relationships", [])),
        },
        "markdown": {
            "characters": 0,
            "locations": 0,
            "key_terms": 0,
            "relationships": 0,
        },
        "mempalace_chunks": len(mp_chunks),
        "transcript_files": transcript_files,
    }

def save_implicit_relationships(game_title: str, implicit_edges: list) -> None:
    """Save implicit co-occurrence relationships to verified_context.json."""
    import os, json
    from datetime import datetime
    game_key = game_title.lower().replace(" ", "_").strip()
    
    with _context_file_lock:
        all_context = {}
        if os.path.exists(VERIFIED_CONTEXT_FILE):
            try:
                with open(VERIFIED_CONTEXT_FILE, "r") as f:
                    all_context = json.load(f)
            except Exception as e:
                logger.debug(f"Could not read verified context file: {e}")
                pass

        if game_key not in all_context:
            all_context[game_key] = {"context": {}, "verified_at": datetime.now().isoformat()}

        all_context[game_key]["implicit_relationships"] = implicit_edges

        try:
            # Atomic write: write to temp file then replace
            fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(VERIFIED_CONTEXT_FILE), suffix=".tmp")
            try:
                with os.fdopen(fd, 'w') as f:
                    json.dump(all_context, f, indent=2)
                os.replace(tmp_path, VERIFIED_CONTEXT_FILE)
            except Exception:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise
        except Exception as e:
            print(f"Failed to save implicit relationships: {e}")

def load_implicit_relationships(game_title: str) -> list:
    """Load stored implicit co-occurrence relationships."""
    import os, json
    game_key = game_title.lower().replace(" ", "_").strip()

    with _context_file_lock:
        if not os.path.exists(VERIFIED_CONTEXT_FILE):
            return []

        try:
            with open(VERIFIED_CONTEXT_FILE, "r") as f:
                all_context = json.load(f)
            return all_context.get(game_key, {}).get("implicit_relationships", [])
        except Exception as e:
            logger.debug(f"Could not read implicit relationships: {e}")
            return []

def compute_and_save_implicit_relationships(game_title: str, transcript_text: str):
    """Compute co-occurrence from transcript text and merge with existing stored data."""
    from collections import defaultdict

    game_key = game_title.lower().replace(" ", "_").strip()

    verified = load_verified_context(game_key)
    context = verified.get("context", {}) if verified else {}

    entities = {}
    for etype in ['characters', 'locations', 'key_terms']:
        for item in context.get(etype, []):
            if isinstance(item, str):
                name = item
                entity_id = item
            else:
                name = item.get('name', item.get('from', ''))
                entity_id = item.get('id', name)
            if name:
                entities[name.lower()] = entity_id

    if not entities:
        return

    entity_occurrences = defaultdict(list)
    text_lower = transcript_text.lower()

    for entity_name, entity_id in entities.items():
        if entity_name in text_lower:
            segment_size = max(1, len(text_lower) // 100)
            pos = text_lower.find(entity_name)
            while pos >= 0:
                segment = pos // segment_size
                entity_occurrences[entity_name].append(segment)
                pos = text_lower.find(entity_name, pos + 1)

    cooccurrence = defaultdict(int)
    entity_names = list(entity_occurrences.keys())

    for i, e1 in enumerate(entity_names):
        for e2 in entity_names[i+1:]:
            segments1 = set(entity_occurrences[e1])
            segments2 = set(entity_occurrences[e2])
            common = segments1 & segments2
            if common:
                pair = tuple(sorted([e1, e2]))
                cooccurrence[pair] = len(common)

    new_edges = []
    for (e1, e2), count in cooccurrence.items():
        if count >= 2:
            new_edges.append({
                'source': entities[e1],
                'target': entities[e2],
                'type': 'co_occurs',
                'weight': count,
                'label': f'appears in {count} segment(s)'
            })

    if not new_edges:
        return

    existing = load_implicit_relationships(game_title)
    existing_map = {}
    for edge in existing:
        key = tuple(sorted([edge.get('source', ''), edge.get('target', '')]))
        existing_map[key] = edge

    for edge in new_edges:
        key = tuple(sorted([edge['source'], edge['target']]))
        if key in existing_map:
            existing_map[key]['weight'] = max(existing_map[key].get('weight', 0), edge['weight'])
        else:
            existing_map[key] = edge

    merged = list(existing_map.values())
    save_implicit_relationships(game_title, merged)
