#!/usr/bin/env python3
"""
Graph builder for Cogitator
Extracts entity-relationship graphs from context manager data.
"""
import os
import json
import time
import re
from datetime import datetime
from typing import Optional, Any, Tuple, Dict, List
from collections import defaultdict

from workflows.performance_database import get_performance_stats
from workflows.context_manager_v2 import ContextManagerV2, get_context_manager
from workflows.mempalace_integration import (
    get_mempalace_text_chunks,
    get_full_series_mapping,
)
from workflows.context_manager_v2 import (
    load_implicit_relationships,
    save_implicit_relationships,
    get_context_sources_summary,
)

from workflows.constants import WORKSPACE

# Graph data cache
_graph_cache: dict = {}
_graph_cache_time: float = 0
_GRAPH_CACHE_TTL = 60


def analyze_transcript_cooccurrence(game_key: str) -> Dict[str, Any]:
    """Analyze transcripts for entity co-occurrence to generate implicit graph edges.

    Returns dict with:
    - edges: list of implicit edges with {source_id, target_id, type, weight, label}
    - entity_segments: {entity_name: [segment_indices]} for reference
    """
    import re
    from collections import defaultdict

    # Get entities from context manager
    cm = get_context_manager()

    # Determine game keys to load entities from — if franchise, include child games
    full_mapping = get_full_series_mapping()
    game_keys_for_entities = [game_key]
    if game_key in full_mapping.values():
        children = [
            child_key
            for child_key, series_val in full_mapping.items()
            if series_val == game_key
        ]
        game_keys_for_entities = [game_key] + children

    entities = {
        'character': [],
        'location': [],
        'term': []
    }

    for gk in game_keys_for_entities:
        for etype in entities:
            for item in cm.get_context_items(gk, etype):
                entities[etype].append({
                    'id': item.id,
                    'name': item.name.lower(),
                    'original': item.name,
                    'type': etype
                })

    # Build entity name to ID map (always lowercase key)
    name_to_id = {}
    for etype, items in entities.items():
        for item in items:
            name_to_id[item['name'].lower()] = item['id']

    # Find and parse transcript files
    transcripts_dir = os.path.join(WORKSPACE, "transcripts")
    if not os.path.exists(transcripts_dir):
        return {"edges": [], "entity_segments": {}}

    # Find transcripts related to this game/franchise
    transcript_files = []
    for fname in os.listdir(transcripts_dir):
        if fname.endswith('.json'):
            transcript_files.append(os.path.join(transcripts_dir, fname))

    if not transcript_files:
        return {"edges": [], "entity_segments": {}}

    # Entity patterns for matching (case-insensitive)
    entity_patterns = {}
    for etype, items in entities.items():
        for item in items:
            entity_patterns[item['name']] = {
                'id': item['id'],
                'type': etype,
                'original': item['original']
            }
            # Also add lowercase
            entity_patterns[item['name'].lower()] = entity_patterns[item['name']]

    # Co-occurrence tracking
    cooccurrence = defaultdict(int)  # (name1, name2) -> count
    entity_segments = defaultdict(set)  # name -> set of segment indices
    entity_contexts = defaultdict(list)  # name -> list of {segment_idx, nearby_entities}

    def _process_text_segment(text: str, seg_idx: int):
        if not text:
            return
        text_lower = text.lower()
        mentioned = []
        for entity_name in entity_patterns:
            pattern = r'\b' + re.escape(entity_name) + r'\b'
            if re.search(pattern, text_lower):
                mentioned.append(entity_name)
                entity_segments[entity_name].add(seg_idx)
        for i, name1 in enumerate(mentioned):
            for name2 in mentioned[i + 1:]:
                pair = tuple(sorted([name1, name2]))
                cooccurrence[pair] += 1
                for other in mentioned:
                    if other != name1:
                        entity_contexts[name1].append({
                            'segment': seg_idx,
                            'nearby': other,
                            'text_preview': text[:100],
                        })

    # Process each transcript JSON on disk
    seg_offset = 0
    for tfile in transcript_files:
        try:
            with open(tfile, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for seg_idx, segment in enumerate(data.get('segments', [])):
                _process_text_segment(segment.get('text', ''), seg_offset + seg_idx)
            seg_offset += len(data.get('segments', []))
        except Exception as e:
            print(f"Error processing transcript {tfile}: {e}")
            continue

    # MemPalace: split narrative chunks into sentence-like segments for co-occurrence
    for gk in game_keys_for_entities:
        mempalace_chunks = get_mempalace_text_chunks(gk)
        for chunk_idx, chunk in enumerate(mempalace_chunks):
            for part_idx, part in enumerate(re.split(r'[.!?\n]+', chunk)):
                part = part.strip()
                if len(part) > 20:
                    _process_text_segment(part, seg_offset + chunk_idx * 1000 + part_idx)

    # Generate implicit edges from co-occurrences
    implicit_edges = []
    edge_id = 0

    # Threshold: at least 2 co-occurrences to create an edge
    min_cooccurrence = 1

    for (name1, name2), count in cooccurrence.items():
        if count >= min_cooccurrence:
            id1 = name_to_id.get(name1)
            id2 = name_to_id.get(name2)

            if id1 and id2 and id1 != id2:
                # Determine edge type based on entity types
                type1 = entity_patterns.get(name1, {}).get('type', 'unknown')
                type2 = entity_patterns.get(name2, {}).get('type', 'unknown')

                # Edge type logic
                if type1 == 'character' and type2 == 'location':
                    edge_type = 'located_at'
                    edge_label = f"found in {entity_patterns.get(name2, {}).get('original', name2)}"
                elif type2 == 'character' and type1 == 'location':
                    edge_type = 'located_at'
                    edge_label = f"visited by {entity_patterns.get(name1, {}).get('original', name1)}"
                elif type1 == 'term' or type2 == 'term':
                    edge_type = 'related_to'
                    edge_label = f"connected ({count}x)"
                else:
                    edge_type = 'co_occurs'
                    edge_label = f"mentioned together ({count}x)"

                implicit_edges.append({
                    'source': id1,
                    'target': id2,
                    'type': edge_type,
                    'weight': count,
                    'label': edge_label,
                    'implicit': True
                })
                edge_id += 1

    # Also create edges between entities that share many contexts
    # (entities frequently mentioned in same segments)
    shared_contexts = defaultdict(int)
    for name, contexts in entity_contexts.items():
        nearby_counts = defaultdict(int)
        for ctx in contexts:
            nearby_counts[ctx['nearby']] += 1

        for other_name, cnt in nearby_counts.items():
            if cnt >= 3:  # At least 3 shared contexts
                pair = tuple(sorted([name, other_name]))
                if pair not in cooccurrence or cooccurrence[pair] < cnt:
                    shared_contexts[pair] = cnt

    # Add shared context edges
    for (name1, name2), count in shared_contexts.items():
        if count >= 3:
            id1 = name_to_id.get(name1)
            id2 = name_to_id.get(name2)

            if id1 and id2 and id1 != id2:
                # Check if edge already exists
                exists = any(
                    (e['source'] == id1 and e['target'] == id2) or
                    (e['source'] == id2 and e['target'] == id1)
                    for e in implicit_edges
                )

                if not exists:
                    type1 = entity_patterns.get(name1, {}).get('type', 'unknown')
                    type2 = entity_patterns.get(name2, {}).get('type', 'unknown')

                    edge_type = 'mentioned_with' if 'character' in [type1, type2] else 'contextually_linked'

                    implicit_edges.append({
                        'source': id1,
                        'target': id2,
                        'type': edge_type,
                        'weight': count,
                        'label': f"frequently together ({count}x)",
                        'implicit': True
                    })

    return {
        "edges": implicit_edges,
        "entity_segments": {k: list(v) for k, v in entity_segments.items()},
        "total_transcripts": len(transcript_files),
        "total_cooccurrences": sum(cooccurrence.values())
    }


def _normalize_entity_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").lower().strip())


def _resolve_graph_game_key(game_key: str) -> str:
    """Map child game keys to franchise context when applicable."""
    full_mapping = get_full_series_mapping()
    if game_key in full_mapping:
        return full_mapping[game_key]
    return game_key


def _register_graph_node(item, nodes: list, node_id_map: dict, alias_map: dict) -> None:
    """Register an entity node and all name aliases for edge resolution.
    First registration wins for name collisions (character > location > term)."""
    norm = _normalize_entity_name(item.name)
    if not norm:
        return
    nodes.append({
        "data": {
            "id": item.id,
            "label": item.name,
            "type": item.type,
            "description": item.description,
            "category": getattr(item, "category", "") or "",
        }
    })
    if norm not in node_id_map:
        node_id_map[norm] = item.id
    for alias in getattr(item, "aliases", []) or []:
        alias_norm = _normalize_entity_name(alias if isinstance(alias, str) else str(alias))
        if alias_norm:
            alias_map[alias_norm] = item.id


def _resolve_entity_id(name: str, node_id_map: dict, alias_map: dict) -> Optional[str]:
    """Resolve a context name to a graph node id."""
    norm = _normalize_entity_name(name)
    if not norm:
        return None
    if norm in node_id_map:
        return node_id_map[norm]
    if norm in alias_map:
        return alias_map[norm]
    # Substring match for minor spelling differences (longest keys first)
    for key, ent_id in sorted(node_id_map.items(), key=lambda kv: -len(kv[0])):
        if len(norm) >= 3 and len(key) >= 3 and (norm in key or key in norm):
            return ent_id
    return None


def _parse_relationship_endpoints(item) -> Tuple[Optional[str], Optional[str], str]:
    """Extract from/to entity names and relationship label from a context item.
    
    Prefers the item name (which reflects user edits) over metadata.
    Falls back to metadata.from/metadata.to for legacy items.
    """
    meta = getattr(item, "metadata", None) or {}
    rel_label = (meta.get("relationship") or item.category or "").strip()

    name = item.name or ""
    if "\u2194" in name:
        parts = name.split("\u2194", 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip(), rel_label or "related"

    from_name = (meta.get("from") or "").strip()
    to_name = (meta.get("to") or "").strip()
    if from_name and to_name:
        return from_name, to_name, rel_label

    return None, None, rel_label


def _iter_context_relationships(game_key: str, cm) -> list:
    """Yield relationship dicts from manager items and verified_context.json."""
    seen: set[str] = set()
    for item in cm.get_context_items(game_key, "relationship"):
        from_n, to_n, label = _parse_relationship_endpoints(item)
        if from_n and to_n:
            key = f"{_normalize_entity_name(from_n)}|{_normalize_entity_name(to_n)}|{label}"
            if key not in seen:
                seen.add(key)
                yield {"from": from_n, "to": to_n, "relationship": label}

    verified_file = os.path.join(WORKSPACE, "Context", "verified_context.json")
    if os.path.exists(verified_file):
        try:
            with open(verified_file, "r") as f:
                all_ctx = json.load(f)
            rels = all_ctx.get(game_key, {}).get("context", {}).get("relationships", [])
            for rel in rels:
                if not isinstance(rel, dict):
                    continue
                from_n = (rel.get("from") or "").strip()
                to_n = (rel.get("to") or "").strip()
                if not from_n or not to_n:
                    continue
                label = (rel.get("relationship") or rel.get("type") or "related").strip()
                key = f"{_normalize_entity_name(from_n)}|{_normalize_entity_name(to_n)}|{label}"
                if key not in seen:
                    seen.add(key)
                    yield {"from": from_n, "to": to_n, "relationship": label}
        except Exception:
            pass


def _build_single_game_graph(
    game_key: str,
    cm,
    shared_node_id_map: dict | None = None,
    shared_alias_map: dict | None = None,
    shared_valid_ids: set | None = None,
) -> dict:
    """Build graph for one game. Optionally merge into shared maps for cross-game views.
    If game_key is a franchise key, child game data is merged in automatically."""
    nodes = []
    edges = []
    node_id_map = {} if shared_node_id_map is None else shared_node_id_map
    alias_map = {} if shared_alias_map is None else shared_alias_map
    valid_node_ids: set[str] = shared_valid_ids if shared_valid_ids is not None else set()

    # Determine which game keys to process — if franchise, include child games
    # Only merge child data in individual mode (no shared maps), not in all-games mode
    full_mapping = get_full_series_mapping()
    game_keys_to_process = [game_key]
    if shared_node_id_map is None and shared_valid_ids is None:
        is_franchise = game_key in full_mapping.values()
        if is_franchise:
            children = [
                child_key
                for child_key, series_val in full_mapping.items()
                if series_val == game_key
            ]
            game_keys_to_process = [game_key] + children

    for current_game_key in game_keys_to_process:
        for item_type in ("character", "location", "term", "game"):
            for item in cm.get_context_items(current_game_key, item_type):
                _register_graph_node(item, nodes, node_id_map, alias_map)
                valid_node_ids.add(item.id)

    context_rel_count = 0
    added_pairs: set[tuple[str, str]] = set()
    for current_game_key in game_keys_to_process:
        for rel in _iter_context_relationships(current_game_key, cm):
            source_id = _resolve_entity_id(rel["from"], node_id_map, alias_map)
            target_id = _resolve_entity_id(rel["to"], node_id_map, alias_map)

            # Auto-create placeholder nodes for entities that don't exist as nodes
            if not source_id:
                placeholder_id = f"ph_{_normalize_entity_name(rel['from'])}_{current_game_key[:8]}"
                norm_from = _normalize_entity_name(rel["from"])
                nodes.append({
                    "data": {
                        "id": placeholder_id,
                        "label": rel["from"],
                        "type": "character",
                        "description": "",
                        "category": "",
                    }
                })
                node_id_map[norm_from] = placeholder_id
                valid_node_ids.add(placeholder_id)
                source_id = placeholder_id

            if not target_id:
                placeholder_id = f"ph_{_normalize_entity_name(rel['to'])}_{current_game_key[:8]}"
                norm_to = _normalize_entity_name(rel["to"])
                nodes.append({
                    "data": {
                        "id": placeholder_id,
                        "label": rel["to"],
                        "type": "character",
                        "description": "",
                        "category": "",
                    }
                })
                node_id_map[norm_to] = placeholder_id
                valid_node_ids.add(placeholder_id)
                target_id = placeholder_id

            if source_id == target_id:
                continue
            pair_key = tuple(sorted([source_id, target_id]))
            if pair_key in added_pairs:
                continue
            added_pairs.add(pair_key)
            context_rel_count += 1
            edges.append({
                "data": {
                    "id": f"ctx_{source_id[:8]}_{target_id[:8]}_{context_rel_count}",
                    "source": source_id,
                    "target": target_id,
                    "label": rel.get("relationship") or "related",
                    "type": "context_relationship",
                    "implicit": False,
                    "is_direct": True,
                    "is_context": True,
                    "game_key": current_game_key,
                }
            })

    try:
        stored_implicit = load_implicit_relationships(game_key)
        cooccurrence_data = analyze_transcript_cooccurrence(game_key)
        fresh_edges = cooccurrence_data.get("edges", [])

        if fresh_edges:
            # Only save if there are actual edges — never overwrite stored data with empty
            save_implicit_relationships(game_key, fresh_edges)
            implicit_edges_data = fresh_edges
        elif stored_implicit:
            # Preserve previously stored implicit edges when transcripts are missing
            implicit_edges_data = stored_implicit
        else:
            implicit_edges_data = []

        for ie in implicit_edges_data:
            source_val = ie.get('source', '')
            target_val = ie.get('target', '')
            source_id = source_val if source_val in valid_node_ids else _resolve_entity_id(source_val, node_id_map, alias_map)
            target_id = target_val if target_val in valid_node_ids else _resolve_entity_id(target_val, node_id_map, alias_map)
            if not source_id or not target_id or source_id == target_id:
                continue
            edges.append({
                "data": {
                    "id": f"implicit_{source_id[:8]}_{target_id[:8]}",
                    "source": source_id,
                    "target": target_id,
                    "label": ie.get("label", ""),
                    "type": ie.get("type", "co_occurs"),
                    "implicit": True,
                    "weight": ie.get("weight", 1),
                    "game_key": game_key,
                }
            })
    except Exception as e:
        print(f"Error generating implicit edges: {e}")

    sources = get_context_sources_summary(game_key)
    context_edges = sum(1 for e in edges if e.get("data", {}).get("is_context"))
    implicit_edges = sum(1 for e in edges if e.get("data", {}).get("implicit"))

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "nodes": len(nodes),
            "context_edges": context_edges,
            "implicit_edges": implicit_edges,
            "sources": sources,
            "game_key": game_key,
        },
    }


def _get_graph_cache_key() -> str:
    """Generate cache key based on context file mtimes."""
    context_dir = os.path.join(WORKSPACE, "Context")
    if not os.path.exists(context_dir):
        return "no_context"
    mtimes = []
    for root, dirs, files in os.walk(context_dir):
        for f in files:
            if f.endswith(('.json', '.md')):
                mtimes.append(str(os.path.getmtime(os.path.join(root, f))))
    return "|".join(sorted(mtimes))


def _get_cached_graph(cache_key: str) -> dict | None:
    """Get cached graph data if still valid."""
    global _graph_cache_time
    if _graph_cache and (time.time() - _graph_cache_time < _GRAPH_CACHE_TTL):
        return _graph_cache.get(cache_key)
    return None


def _set_cached_graph(cache_key: str, data: dict) -> None:
    """Cache graph data with current timestamp."""
    global _graph_cache, _graph_cache_time
    _graph_cache[cache_key] = data
    _graph_cache_time = time.time()


# Public wrappers for backend API
def build_single_game_graph(game_key: str, cm=None):
    """Public wrapper for _build_single_game_graph."""
    if cm is None:
        from workflows.context_manager_v2 import get_context_manager
        cm = get_context_manager()
    return _build_single_game_graph(game_key, cm)


def get_graph_cache_key() -> str:
    """Public wrapper for _get_graph_cache_key."""
    return _get_graph_cache_key()


def get_cached_graph(cache_key: str) -> dict | None:
    """Public wrapper for _get_cached_graph."""
    return _get_cached_graph(cache_key)


def set_cached_graph(cache_key: str, data: dict) -> None:
    """Public wrapper for _set_cached_graph."""
    return _set_cached_graph(cache_key, data)


def build_all_games_graph() -> dict:
    """Build a combined graph for all games."""
    cm = get_context_manager()
    cm.load_all_contexts()

    all_games = cm.get_games()
    if not all_games:
        return {"nodes": [], "edges": [], "stats": {"total_nodes": 0, "per_game": {}}}

    all_nodes: list = []
    all_edges: list = []
    per_game_stats: dict = {}
    shared_node_id_map: dict = {}
    shared_alias_map: dict = {}
    shared_valid_ids: set = set()

    for game_key in all_games:
        game_graph = _build_single_game_graph(
            game_key, cm,
            shared_node_id_map=shared_node_id_map,
            shared_alias_map=shared_alias_map,
            shared_valid_ids=shared_valid_ids,
        )

        game_nodes = game_graph.get("nodes", [])
        game_stats = game_graph.get("stats", {})

        if not game_nodes:
            continue

        display_name = game_key.replace("_", " ").title()
        hub_id = f"hub_{game_key}"
        all_nodes.append({
            "data": {
                "id": hub_id,
                "label": display_name,
                "type": "game",
                "description": f"{len(game_nodes)} entities in {display_name}",
            }
        })

        for node in game_nodes:
            node["data"]["game_key"] = game_key
            node["data"]["_hub_id"] = hub_id
            all_nodes.append(node)
            all_edges.append({
                "data": {
                    "id": f"hub_link_{node['data']['id']}",
                    "source": hub_id,
                    "target": node["data"]["id"],
                    "label": "belongs to",
                    "type": "hub",
                    "implicit": False,
                    "is_context": False,
                    "game_key": game_key,
                }
            })

        for edge in game_graph.get("edges", []):
            edge["data"]["game_key"] = game_key
            all_edges.append(edge)

        per_game_stats[game_key] = {
            "nodes": game_stats.get("nodes", 0),
            "context_edges": game_stats.get("context_edges", 0),
            "implicit_edges": game_stats.get("implicit_edges", 0),
        }

    return {
        "nodes": all_nodes,
        "edges": all_edges,
        "stats": {
            "total_nodes": len(all_nodes),
            "total_edges": len(all_edges),
            "per_game": per_game_stats,
        },
    }
