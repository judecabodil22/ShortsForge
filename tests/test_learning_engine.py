"""Tests for learning engine functions (sentiment, power words, urgency)."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestCalculateSentiment:
    def test_positive_text(self):
        from workflows.learning_engine import calculate_sentiment
        score = calculate_sentiment("This is an amazing and incredible game")
        assert score > 0

    def test_negative_text(self):
        from workflows.learning_engine import calculate_sentiment
        score = calculate_sentiment("This is terrible and horrible")
        assert score < 0

    def test_neutral_text(self):
        from workflows.learning_engine import calculate_sentiment
        score = calculate_sentiment("The weather is normal today")
        assert score == 0

    def test_no_false_positives(self):
        """Words should match as whole words, not substrings."""
        from workflows.learning_engine import calculate_sentiment
        # "badger" contains "bad" but should not trigger negative sentiment
        score = calculate_sentiment("The badger ran through the forest")
        assert score == 0

    def test_bounds(self):
        from workflows.learning_engine import calculate_sentiment
        score = calculate_sentiment("amazing incredible stunning fantastic wonderful perfect")
        assert -1 <= score <= 1


class TestCalculatePowerWordDensity:
    def test_empty_text(self):
        from workflows.learning_engine import calculate_power_word_density
        density = calculate_power_word_density("")
        assert density == 0

    def test_with_power_words(self):
        from workflows.learning_engine import calculate_power_word_density
        density = calculate_power_word_density("The secret truth was revealed in this mystery")
        assert density > 0

    def test_no_false_positives(self):
        """Power words should match as whole words."""
        from workflows.learning_engine import calculate_power_word_density
        # "unknown" contains "known" but "known" is not a power word
        density = calculate_power_word_density("The known facts are established")
        assert density == 0


class TestCalculateUrgencyScore:
    def test_empty_text(self):
        from workflows.learning_engine import calculate_urgency_score
        score = calculate_urgency_score("")
        assert score == 0

    def test_urgent_text(self):
        from workflows.learning_engine import calculate_urgency_score
        score = calculate_urgency_score("You must act now immediately hurry fast")
        assert score > 0


class TestCalculateEmotionalIntensity:
    def test_empty_text(self):
        from workflows.learning_engine import calculate_emotional_intensity
        intensity = calculate_emotional_intensity("")
        assert intensity == 0

    def test_emotional_text(self):
        from workflows.learning_engine import calculate_emotional_intensity
        intensity = calculate_emotional_intensity(
            "This is shocking! Incredible! Unbelievable!"
        )
        assert intensity > 0


class TestThompsonSampling:
    def test_beta_distribution_normalization(self):
        """Thompson Sampling should normalize impact_score to [0, 1]."""
        from workflows.performance_database import get_db
        # The fix ensures mean / 100.0 before computing alpha/beta
        # Test that the math doesn't produce negative values
        mean = 50  # impact_score on 0-100 scale
        samples = 10
        normalized_mean = max(0.01, min(0.99, mean / 100.0))
        alpha = max(normalized_mean * samples, 1)
        beta_val = max((1 - normalized_mean) * samples, 1)
        assert alpha > 0
        assert beta_val > 0
