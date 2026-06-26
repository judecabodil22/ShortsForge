import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from workflows.constants import (
    calculate_performance_score,
    parse_duration,
    calculate_readability,
    calculate_hook_strength,
    dedupe_entity_list,
    get_next_groq_key,
    fuzzy_dedup_against_list,
)


class TestCalculatePerformanceScore:
    def test_zero_views_returns_zero(self):
        assert calculate_performance_score(0, 0.5) == 0.0

    def test_perfect_score(self):
        score = calculate_performance_score(10000, 10.0, duration=45)
        assert score == 100.0

    def test_score_bounds(self):
        score = calculate_performance_score(100, 0.5, duration=120)
        assert 0 <= score <= 100

    def test_duration_penalty(self):
        score_optimal = calculate_performance_score(1000, 5.0, duration=45)
        score_off = calculate_performance_score(1000, 5.0, duration=300)
        assert score_optimal > score_off

    def test_no_duration_no_penalty(self):
        score = calculate_performance_score(1000, 5.0)
        assert 0 <= score <= 100


class TestParseDuration:
    def test_full_duration(self):
        assert parse_duration("PT1H30M15S") == 5415

    def test_minutes_only(self):
        assert parse_duration("PT5M30S") == 330

    def test_seconds_only(self):
        assert parse_duration("PT45S") == 45

    def test_hours_only(self):
        assert parse_duration("PT2H") == 7200

    def test_invalid_returns_zero(self):
        assert parse_duration("invalid") == 0


class TestCalculateReadability:
    def test_empty_returns_zero(self):
        assert calculate_readability("") == 0

    def test_simple_sentence(self):
        score = calculate_readability("The cat sat on the mat.")
        assert 0 <= score <= 100

    def test_complex_text_lower_score(self):
        simple = calculate_readability("The cat sat on the mat.")
        complex = calculate_readability("Notwithstanding the aforementioned circumstances, the feline specimen demonstrated remarkable locomotive capabilities.")
        assert simple > complex


class TestCalculateHookStrength:
    def test_empty_returns_zero(self):
        assert calculate_hook_strength("") == 0

    def test_question_hook(self):
        strength = calculate_hook_strength("Did you know this secret?")
        assert strength > 0

    def test_hook_starter(self):
        strength = calculate_hook_strength("The secret truth about everything")
        assert strength > 0

    def test_strength_bounds(self):
        strength = calculate_hook_strength("What nobody tells you about the secret truth")
        assert 0 <= strength <= 1.0


class TestDedupeEntityList:
    def test_empty_list(self):
        result, alias_map = dedupe_entity_list([])
        assert result == []
        assert alias_map == {}

    def test_no_duplicates(self):
        items = ["Alice", "Bob", "Charlie"]
        result, _ = dedupe_entity_list(items)
        assert len(result) == 3

    def test_exact_duplicates(self):
        items = ["Alice", "alice", "Alice"]
        result, _ = dedupe_entity_list(items)
        assert len(result) >= 1


class TestFuzzyDedupAgainstList:
    def test_empty_list(self):
        is_dup, canonical = fuzzy_dedup_against_list("Alice", [])
        assert is_dup is False
        assert canonical is None

    def test_exact_match(self):
        is_dup, canonical = fuzzy_dedup_against_list("Alice", ["Alice", "Bob"])
        assert is_dup is True
        assert canonical == "Alice"

    def test_no_match(self):
        is_dup, _ = fuzzy_dedup_against_list("Charlie", ["Alice", "Bob"])
        assert is_dup is False


class TestGetNextGroqKey:
    def test_returns_string_or_empty(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        for i in range(1, 10):
            monkeypatch.delenv(f"GROQ_API_KEY_{i}", raising=False)
        result = get_next_groq_key()
        assert isinstance(result, str)
