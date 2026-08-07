import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from workflows.script_validation import (
    validate_script_factuality,
    score_engagement,
    select_best_script,
    score_context_relevance,
    summarize_context,
    _is_known_entity,
    calculate_optimal_temperature,
)


class TestValidateScriptFactuality:
    def test_empty_script_returns_neutral_score(self):
        context = {"characters": [], "locations": [], "key_terms": [], "relationships": []}
        result = validate_script_factuality("", context)
        assert result["score"] == 0.5  # Neutral score for scripts with no entities

    def test_no_context_entities_returns_neutral(self):
        context = {"characters": [], "locations": [], "key_terms": [], "relationships": []}
        result = validate_script_factuality("The weather is nice today.", context)
        # No named entities in this text, so score should be neutral (0.5)
        assert result["score"] == 0.5

    def test_has_issues_structure(self):
        context = {"characters": [], "locations": [], "key_terms": [], "relationships": []}
        result = validate_script_factuality("", context)
        assert "score" in result
        assert "issues" in result
        assert "flagged_entities" in result


class TestScoreEngagement:
    def test_empty_script(self):
        result = score_engagement("")
        assert result["overall"] > 0
        assert result["overall"] <= 1.0
        assert result["hook_strength"] == 0.0

    def test_has_all_keys(self):
        result = score_engagement("This is a test script with multiple sentences. It has some structure. And a hook!")
        assert "hook_strength" in result
        assert "sentiment_arc" in result
        assert "readability" in result
        assert "overall" in result

    def test_scores_in_range(self):
        result = score_engagement("A" * 500)
        assert 0 <= result["hook_strength"] <= 1
        assert 0 <= result["sentiment_arc"] <= 1
        assert 0 <= result["readability"] <= 1
        assert 0 <= result["overall"] <= 1


class TestSelectBestScript:
    def test_single_candidate(self):
        candidates = [("Test script content here.", {"source": "test", "model": "test", "temperature": 0.7})]
        context = {"characters": [], "locations": [], "key_terms": [], "relationships": []}
        script, metadata, scores = select_best_script(candidates, context)
        assert script == "Test script content here."
        assert len(scores) == 1

    def test_multiple_candidates(self):
        candidates = [
            ("Script A content here for testing.", {"source": "test", "model": "test", "temperature": 0.7}),
            ("Script B content here for testing purposes.", {"source": "test", "model": "test", "temperature": 0.8}),
        ]
        context = {"characters": [], "locations": [], "key_terms": [], "relationships": []}
        script, metadata, scores = select_best_script(candidates, context)
        assert script in ("Script A content here for testing.", "Script B content here for testing purposes.")
        assert len(scores) == 2


class TestScoreContextRelevance:
    def test_empty_context(self):
        context = {"characters": [], "locations": [], "key_terms": [], "relationships": []}
        result = score_context_relevance(context, "some transcript text")
        assert result["characters"] == []
        assert result["locations"] == []
        assert result["key_terms"] == []

    def test_relevant_items_scored_higher(self):
        context = {
            "characters": ["Alice", "Bob", "Charlie"],
            "locations": ["Forest", "Castle"],
            "key_terms": ["magic", "sword"],
            "relationships": ["Alice-Bob"],
        }
        result = score_context_relevance(context, "Alice walked through the Forest with her magic sword.")
        assert "Alice" in result["characters"]
        assert "Forest" in result["locations"]
        assert "magic" in result["key_terms"]


class TestSummarizeContext:
    def test_respects_max_per_category(self):
        context = {
            "characters": list(range(20)),
            "locations": list(range(20)),
            "key_terms": list(range(20)),
            "relationships": list(range(20)),
        }
        result = summarize_context(context, max_per_category=5)
        assert len(result["characters"]) == 5
        assert len(result["locations"]) == 5
        assert len(result["key_terms"]) == 5
        assert len(result["relationships"]) == 5

    def test_returns_all_keys(self):
        context = {"characters": [], "locations": [], "key_terms": [], "relationships": []}
        result = summarize_context(context)
        assert "processed_transcripts" in result
        assert "previous_scripts" in result


class TestIsKnownEntity:
    def test_empty_known_list_returns_false(self):
        assert _is_known_entity("Alice", []) is False

    def test_exact_match(self):
        assert _is_known_entity("Alice", ["Alice", "Bob"]) is True

    def test_no_match(self):
        assert _is_known_entity("Xyzzzzz", ["Alice", "Bob"]) is False


class TestCalculateOptimalTemperature:
    def test_returns_default_with_no_data(self, monkeypatch):
        monkeypatch.setattr(
            "workflows.script_validation.get_effective_prompts",
            lambda: {"successful_samples": 0},
        )
        temp = calculate_optimal_temperature("pipeline")
        assert temp == 0.7

    def test_returns_float(self):
        temp = calculate_optimal_temperature("pipeline")
        assert isinstance(temp, float)
