"""Tests for title variety helpers."""
from workflows.title_variety import (
    detect_structure,
    is_too_similar,
    looks_generic,
    normalize_title,
    next_preferred_structure,
    word_overlap_ratio,
)


def test_normalize_title():
    assert normalize_title("  Hello   World  ") == "hello world"


def test_overlap_and_similarity():
    assert word_overlap_ratio("the secret of the night", "the secret of the night") == 1.0
    assert is_too_similar("The Secret Of The Night", ["the secret of the night"])
    assert not is_too_similar("Cal completely lost his cool", ["the secret of the night"])


def test_generic_detection():
    assert looks_generic("The Story of Everything")
    assert not looks_generic("Cal Never Told Bode the Truth")


def test_structure_rotation():
    assert detect_structure("What Made Cal Impossible?") == "question"
    preferred = next_preferred_structure(["question", "question", "statement"])
    assert preferred in ("contrast", "number", "reveal", "statement")
