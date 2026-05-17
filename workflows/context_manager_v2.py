#!/usr/bin/env python3
"""
ShortsForge Context Management System v2
Advanced context management with editor, search, and analytics.
"""
import os
import json
import uuid
import glob
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Callable
from functools import lru_cache

WORKSPACE = os.path.expanduser("~/ShortsForge")
CONTEXT_DIR = os.path.join(WORKSPACE, "Context")
VERIFIED_CONTEXT_FILE = os.path.join(CONTEXT_DIR, "verified_context.json")
HISTORY_DIR = os.path.join(CONTEXT_DIR, "history")
SCHEMA_FILE = os.path.join(CONTEXT_DIR, "schema.json")


class ContextItem:
    """Represents a single context item (character, location, term, relationship)."""
    
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
            "metadata": self.metadata
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
        return item
    
    def update(self, **kwargs):
        """Update fields and timestamp."""
        for key, value in kwargs.items():
            if key == "metadata":
                self.metadata.update(value)
            elif hasattr(self, key):
                setattr(self, key, value)
        self.metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    def validate(self) -> List[str]:
        """Validate the item and return list of errors."""
        errors = []
        if not self.name.strip():
            errors.append("Name is required")
        if self.type not in ["character", "location", "term", "relationship"]:
            errors.append(f"Invalid type: {self.type}")
        return errors


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
        """Get history entries, optionally filtered by item_id."""
        if not os.path.exists(self.history_file):
            return []
        
        entries = []
        try:
            with open(self.history_file, "r") as f:
                for line in f:
                    entry = json.loads(line.strip())
                    if item_id is None or entry.get("item_id") == item_id:
                        entries.append(entry)
                    if len(entries) >= limit:
                        break
        except Exception:
            pass
        return entries


class ContextManagerV2:
    """Main context management class with editor, search, and analytics."""
    
    def __init__(self):
        self.contexts: Dict[str, Dict[str, ContextItem]] = {}  # game_key -> {type -> [items]}
        self.load_all_contexts()
    
    def load_all_contexts(self):
        """Load all games' contexts from verified_context.json."""
        if not os.path.exists(VERIFIED_CONTEXT_FILE):
            return
        
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
                    self.contexts[game_key]["character"].append(item)
                
                for loc in ctx.get("locations", []):
                    if isinstance(loc, dict):
                        item = ContextItem.from_dict(loc)
                        item.game_key = game_key
                        item.type = "location"
                    else:
                        item = ContextItem(game_key, "location", str(loc))
                    self.contexts[game_key]["location"].append(item)
                
                for term in ctx.get("key_terms", []):
                    if isinstance(term, dict):
                        item = ContextItem.from_dict(term)
                        item.game_key = game_key
                        item.type = "term"
                    else:
                        item = ContextItem(game_key, "term", str(term))
                    self.contexts[game_key]["term"].append(item)
                
                for rel in ctx.get("relationships", []):
                    if isinstance(rel, dict) and "name" in rel:
                        item = ContextItem.from_dict(rel)
                        item.game_key = game_key
                        item.type = "relationship"
                    elif isinstance(rel, dict):
                        item = ContextItem(
                            game_key, "relationship",
                            f"{rel.get('from', '')} ↔ {rel.get('to', '')}",
                            category=rel.get("relationship", "")
                        )
                    else:
                        item = ContextItem(game_key, "relationship", str(rel))
                    self.contexts[game_key]["relationship"].append(item)
        except Exception as e:
            print(f"Error loading contexts: {e}")
    
    def get_games(self) -> List[str]:
        """Get list of all game keys."""
        return list(self.contexts.keys())
    
    def get_context_items(self, game_key: str, item_type: str = None) -> List[ContextItem]:
        """Get all context items for a game, optionally filtered by type."""
        if game_key not in self.contexts:
            return []
        if item_type:
            return self.contexts.get(game_key, {}).get(item_type, [])
        all_items = []
        for items in self.contexts.get(game_key, {}).values():
            all_items.extend(items)
        return all_items
    
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
        
        history = ContextHistory(game_key)
        history.add_entry(item_id, "delete", before=before)
        
        self.save_context(game_key)
        return True
    
    def save_context(self, game_key: str):
        """Save context to verified_context.json."""
        if game_key not in self.contexts:
            return
        
        all_data = {}
        if os.path.exists(VERIFIED_CONTEXT_FILE):
            try:
                with open(VERIFIED_CONTEXT_FILE, "r") as f:
                    all_data = json.load(f)
            except:
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
        with open(VERIFIED_CONTEXT_FILE, "w") as f:
            json.dump(all_data, f, indent=2)
    
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
            game_stats = {"characters": 0, "locations": 0, "terms": 0, "relationships": 0}
            
            for item_type, items in self.contexts.get(gk, {}).items():
                count = len(items)
                game_stats[item_type] = count
                analytics["total_items"] += count
                analytics["by_type"][item_type] = analytics["by_type"].get(item_type, 0) + count
                
                source = item.metadata.get("source", "manual")
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


# Global instance
_context_manager = None

def get_context_manager() -> ContextManagerV2:
    """Get or create the global context manager instance."""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManagerV2()
    return _context_manager


# Convenience functions
def list_games() -> List[str]:
    return get_context_manager().get_games()

def get_items(game_key: str, item_type: str = None) -> List[ContextItem]:
    return get_context_manager().get_context_items(game_key, item_type)

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