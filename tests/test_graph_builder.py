"""Tests for graph builder: relationship parsing, entity resolution, graph construction."""
import re
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from workflows.graph_builder import (
    _parse_relationship_endpoints,
    _resolve_entity_id,
    _normalize_entity_name,
    _build_single_game_graph,
)


# ---------------------------------------------------------------------------
# _parse_relationship_endpoints
# ---------------------------------------------------------------------------

class _FakeItem:
    def __init__(self, name="", category="", metadata=None):
        self.name = name
        self.category = category or ""
        self.metadata = metadata or {}


def test_parse_arrow_separator():
    item = _FakeItem(name="Alice ↔ Bob", category="friends")
    fr, to, label = _parse_relationship_endpoints(item)
    assert fr == "Alice"
    assert to == "Bob"
    assert label == "friends"


def test_parse_metadata_from_to():
    item = _FakeItem(metadata={"from": "X", "to": "Y", "relationship": "enemies"})
    fr, to, label = _parse_relationship_endpoints(item)
    assert fr == "X"
    assert to == "Y"
    assert label == "enemies"


def test_parse_string_and_are():
    item = _FakeItem(name="Agent P3 and Charles S. are associates")
    fr, to, label = _parse_relationship_endpoints(item)
    assert fr == "Agent P3"
    assert to == "Charles S."
    assert label == "associates"


def test_parse_string_single_word():
    item = _FakeItem(name="friends")
    fr, to, label = _parse_relationship_endpoints(item)
    assert fr is None
    assert to is None


def test_parse_arrow_takes_precedence_over_metadata():
    item = _FakeItem(name="A ↔ B", metadata={"from": "X", "to": "Y"})
    fr, to, _ = _parse_relationship_endpoints(item)
    assert fr == "A"
    assert to == "B"


def test_parse_string_with_period_in_name():
    item = _FakeItem(name="Mr. Ritter and Initiate are mentor")
    fr, to, label = _parse_relationship_endpoints(item)
    assert fr == "Mr. Ritter"
    assert to == "Initiate"
    assert label == "mentor"


# ---------------------------------------------------------------------------
# _normalize_entity_name
# ---------------------------------------------------------------------------

def test_normalize_entity_name():
    assert _normalize_entity_name("  Alice  ") == "alice"
    assert _normalize_entity_name("Agent P3") == "agent p3"
    assert _normalize_entity_name("") == ""


# ---------------------------------------------------------------------------
# _resolve_entity_id
# ---------------------------------------------------------------------------

def test_resolve_exact_match():
    node_map = {"alice": "id-alice", "bob": "id-bob"}
    alias_map = {}
    assert _resolve_entity_id("Alice", node_map, alias_map) == "id-alice"


def test_resolve_alias():
    node_map = {"alice": "id-alice"}
    alias_map = {"ali": "id-alice"}
    assert _resolve_entity_id("Ali", node_map, alias_map) == "id-alice"


def test_resolve_substring():
    node_map = {"alice wonderland": "id-alice"}
    alias_map = {}
    assert _resolve_entity_id("alice", node_map, alias_map) == "id-alice"


def test_resolve_not_found():
    assert _resolve_entity_id("Zoe", {"alice": "id-alice"}, {}) is None


# ---------------------------------------------------------------------------
# _build_single_game_graph (with mock ContextManager)
# ---------------------------------------------------------------------------

def _make_cm(characters=None, locations=None, terms=None, relationships=None):
    """Build a mock ContextManager with the given entities."""
    cm = MagicMock()
    characters = characters or []
    locations = locations or []
    terms = terms or []
    relationships = relationships or []

    def get_items(game_key, item_type=None):
        mapping = {
            "character": characters,
            "location": locations,
            "term": terms,
            "relationship": relationships,
        }
        if item_type:
            return mapping.get(item_type, [])
        return [i for v in mapping.values() for i in v]

    cm.get_context_items.side_effect = get_items
    return cm


def _make_item(name, item_type, game_key="test_game", category="", metadata=None):
    """Create a simple ContextItem-like object."""
    ns = SimpleNamespace(
        id=f"id-{name.lower().replace(' ', '-')}",
        name=name,
        type=item_type,
        game_key=game_key,
        category=category,
        description="",
        metadata=metadata or {},
    )
    # Mimic aliases attribute
    ns.aliases = getattr(ns, "aliases", []) or []
    return ns


def test_graph_has_nodes_and_edges():
    cm = _make_cm(
        characters=[_make_item("Alice", "character"), _make_item("Bob", "character")],
        relationships=[
            _make_item("Alice ↔ Bob", "relationship", category="friends",
                       metadata={"from": "Alice", "to": "Bob", "relationship": "friends"}),
        ],
    )
    with patch("workflows.graph_builder.get_full_series_mapping", return_value={}):
        with patch("workflows.graph_builder.load_implicit_relationships", return_value=[]):
            with patch("workflows.graph_builder.analyze_transcript_cooccurrence", return_value={"edges": [], "entity_segments": {}, "total_transcripts": 0, "total_cooccurrences": 0}):
                with patch("workflows.graph_builder.get_context_sources_summary", return_value={"mempalace_chunks": 0, "transcript_files": []}):
                    graph = _build_single_game_graph("test_game", cm)

    node_ids = {n["data"]["id"] for n in graph["nodes"]}
    assert "id-alice" in node_ids
    assert "id-bob" in node_ids
    edge_count = len(graph["edges"])
    assert edge_count >= 1


def test_graph_deduplicates_edges():
    cm = _make_cm(
        characters=[_make_item("Alice", "character"), _make_item("Bob", "character")],
        relationships=[
            _make_item("Alice ↔ Bob", "relationship", category="friends",
                       metadata={"from": "Alice", "to": "Bob", "relationship": "friends"}),
            _make_item("Bob ↔ Alice", "relationship", category="friends",
                       metadata={"from": "Bob", "to": "Alice", "relationship": "friends"}),
        ],
    )
    with patch("workflows.graph_builder.get_full_series_mapping", return_value={}):
        with patch("workflows.graph_builder.load_implicit_relationships", return_value=[]):
            with patch("workflows.graph_builder.analyze_transcript_cooccurrence", return_value={"edges": [], "entity_segments": {}, "total_transcripts": 0, "total_cooccurrences": 0}):
                with patch("workflows.graph_builder.get_context_sources_summary", return_value={"mempalace_chunks": 0, "transcript_files": []}):
                    graph = _build_single_game_graph("test_game", cm)

    # Alice-Bob and Bob-Alice should produce only one edge (deduplicated)
    edge_pairs = set()
    for e in graph["edges"]:
        d = e["data"]
        edge_pairs.add((d["source"], d["target"]))
    assert len(edge_pairs) == 1


def test_graph_creates_placeholder_for_unknown_entity():
    cm = _make_cm(
        characters=[_make_item("Alice", "character")],
        relationships=[
            _make_item("Alice ↔ Unknown Entity", "relationship", category="friends",
                       metadata={"from": "Alice", "to": "Unknown Entity", "relationship": "friends"}),
        ],
    )
    with patch("workflows.graph_builder.get_full_series_mapping", return_value={}):
        with patch("workflows.graph_builder.load_implicit_relationships", return_value=[]):
            with patch("workflows.graph_builder.analyze_transcript_cooccurrence", return_value={"edges": [], "entity_segments": {}, "total_transcripts": 0, "total_cooccurrences": 0}):
                with patch("workflows.graph_builder.get_context_sources_summary", return_value={"mempalace_chunks": 0, "transcript_files": []}):
                    graph = _build_single_game_graph("test_game", cm)

    node_labels = {n["data"]["label"] for n in graph["nodes"]}
    assert "Alice" in node_labels
    assert "Unknown Entity" in node_labels  # placeholder created
