"""Tests for JSON-only context utils (no Obsidian markdown)."""
from workflows.context_utils import merge_context_dicts, _relationship_key


def test_merge_context_dicts_unions_and_skips_self_rels():
    base = {
        "characters": ["Allison"],
        "locations": [],
        "key_terms": [],
        "relationships": [{"from": "Allison", "to": "Tyler", "relationship": "friends"}],
    }
    overlay = {
        "characters": ["Tyler"],
        "locations": ["Delos Crossing"],
        "key_terms": [],
        "relationships": [
            {"from": "Michael", "to": "Michael", "relationship": "friends"},
            {"from": "Allison", "to": "Michael", "relationship": "siblings"},
        ],
    }
    merged = merge_context_dicts(base, overlay)
    assert "Allison" in merged["characters"]
    assert "Tyler" in merged["characters"]
    assert "Delos Crossing" in merged["locations"]
    keys = {_relationship_key(r) for r in merged["relationships"]}
    assert ("michael", "michael") not in keys
    assert ("allison", "tyler") in keys
    assert ("allison", "michael") in keys
