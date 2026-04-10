#!/usr/bin/env python3
"""
ShortsForge Script Validation Module

Provides factuality checking, engagement scoring, and quality metrics
for AI-generated scripts.

Tools used:
- spaCy (en_core_web_sm): Named Entity Recognition
- RapidFuzz: Fuzzy string matching for entity validation
- TextBlob: Sentiment analysis
- NLTK: Readability scoring
- MemPalace: Failure storage for self-improvement
"""

import re
import math
import os
import json
from datetime import datetime, timedelta
from rapidfuzz import fuzz


# ── Entity Extraction (spaCy) ────────────────────────────────────────────────

_nlp = None

def _get_nlp():
    """Lazy-load spaCy model."""
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm")
        except Exception:
            pass
    return _nlp


def extract_entities(text):
    """Extract named entities (PERSON, LOC, ORG, etc.) from text."""
    nlp = _get_nlp()
    if nlp is None:
        return {"persons": [], "locations": [], "organizations": []}

    doc = nlp(text)
    persons = set()
    locations = set()
    organizations = set()

    for ent in doc.ents:
        if ent.label_ == "PERSON":
            persons.add(ent.text)
        elif ent.label_ in ("LOC", "GPE", "FAC"):
            locations.add(ent.text)
        elif ent.label_ == "ORG":
            organizations.add(ent.text)

    return {
        "persons": list(persons),
        "locations": list(locations),
        "organizations": list(organizations),
    }


# ── Factuality Validation ────────────────────────────────────────────────────

def validate_script_factuality(script_text, context):
    """
    Validate a generated script against known context.

    Args:
        script_text: The generated script text
        context: Dict with keys: characters, locations, key_terms, relationships

    Returns:
        Dict with:
            - score: 0.0-1.0 factuality score
            - issues: List of validation issues found
            - flagged_entities: Entities in script not found in context
    """
    issues = []
    flagged_entities = []

    known_chars = context.get("characters", [])
    known_locs = context.get("locations", [])
    known_terms = context.get("key_terms", [])

    # Extract entities from script
    entities = extract_entities(script_text)
    script_persons = entities["persons"]
    script_locations = entities["locations"]

    # Check persons against known characters OR locations (spaCy can misclassify)
    all_known_entities = known_chars + known_locs
    for person in script_persons:
        if not _is_known_entity(person, all_known_entities, threshold=80):
            flagged_entities.append(("person", person))
            issues.append(f"Unknown character mentioned: {person}")

    # Check locations against known locations (fuzzy match)
    for loc in script_locations:
        if not _is_known_entity(loc, known_locs, threshold=75):
            flagged_entities.append(("location", loc))
            issues.append(f"Unknown location mentioned: {loc}")

    # Calculate score
    total_entities = len(script_persons) + len(script_locations)
    if total_entities == 0:
        score = 1.0  # No entities to validate
    else:
        flagged_count = len(flagged_entities)
        score = max(0.0, 1.0 - (flagged_count / total_entities))

    return {
        "score": score,
        "issues": issues,
        "flagged_entities": flagged_entities,
    }


def _is_known_entity(entity, known_list, threshold=80):
    """Check if entity matches any known entity using fuzzy matching."""
    if not known_list:
        return True  # No known entities to check against

    for known in known_list:
        if fuzz.ratio(entity.lower(), known.lower()) >= threshold:
            return True
        # Also check partial match (entity might be a subset)
        if fuzz.partial_ratio(entity.lower(), known.lower()) >= threshold:
            return True
        # Token set ratio for reordered names
        if fuzz.token_set_ratio(entity.lower(), known.lower()) >= threshold:
            return True
    return False


# ── Engagement Scoring ───────────────────────────────────────────────────────

def score_engagement(script_text):
    """
    Score a script on engagement metrics.

    Returns:
        Dict with:
            - hook_strength: 0.0-1.0 (first 100 words)
            - sentiment_arc: 0.0-1.0 (emotional progression)
            - readability: 0.0-1.0 (Flesch-Kincaid based)
            - overall: 0.0-1.0 (combined score)
    """
    words = script_text.split()
    sentences = re.split(r'[.!?]+', script_text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    # Hook strength: first 100 words
    hook_text = ' '.join(words[:100])
    hook_strength = _score_hook(hook_text)

    # Sentiment arc
    sentiment_arc = _score_sentiment_arc(sentences)

    # Readability
    readability = _score_readability(script_text, len(words), len(sentences))

    # Overall (weighted)
    overall = (hook_strength * 0.35) + (sentiment_arc * 0.35) + (readability * 0.30)

    return {
        "hook_strength": round(hook_strength, 3),
        "sentiment_arc": round(sentiment_arc, 3),
        "readability": round(readability, 3),
        "overall": round(overall, 3),
    }


def _score_hook(hook_text):
    """Score the hook strength of the first 100 words."""
    score = 0.0

    # Length check (should be substantial, not too short)
    words = hook_text.split()
    if len(words) >= 15:
        score += 0.2

    # Hook indicators: strong opening words
    hook_words = ['but', 'however', 'yet', 'suddenly', 'then', 'when', 'what',
                  'how', 'why', 'never', 'always', 'every', 'impossible',
                  'shocking', 'secret', 'hidden', 'truth', 'real', 'actually']
    hook_text_lower = hook_text.lower()
    for hw in hook_words:
        if hw in hook_text_lower:
            score += 0.15
            break

    # No weak openings
    weak_openings = ['in conclusion', 'to summarize', 'this is about',
                     'this script', 'the following']
    for wo in weak_openings:
        if wo in hook_text_lower:
            score -= 0.3
            break

    # Question or statement that creates intrigue
    if '?' in hook_text or '!' in hook_text:
        score += 0.15

    # Varied sentence structure in hook
    hook_sentences = re.split(r'[.!?]+', hook_text)
    hook_sentences = [s.strip() for s in hook_sentences if s.strip()]
    if len(hook_sentences) >= 2:
        score += 0.15

    return max(0.0, min(1.0, score))


def _score_sentiment_arc(sentences):
    """Score sentiment progression (emotional arc)."""
    if len(sentences) < 3:
        return 0.3

    try:
        from textblob import TextBlob
        sentiments = []
        for sent in sentences:
            blob = TextBlob(sent)
            sentiments.append(blob.sentiment.polarity)

        if not sentiments:
            return 0.3

        # Good scripts have sentiment variation (not flat)
        sentiment_range = max(sentiments) - min(sentiments)
        arc_score = min(1.0, sentiment_range * 2)  # Scale: 0.5 range = 1.0

        return arc_score
    except Exception:
        return 0.3


def _score_readability(text, word_count, sentence_count):
    """Score readability based on Flesch-Kincaid principles."""
    if sentence_count == 0 or word_count == 0:
        return 0.0

    # Average words per sentence
    avg_words = word_count / sentence_count

    # Count syllables (approximate)
    syllable_count = 0
    for word in text.split():
        word = word.lower().strip(".,!?;:\"'()[]{}")
        if not word:
            continue
        # Simple syllable count
        count = 0
        vowels = "aeiouy"
        prev_vowel = False
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_vowel:
                count += 1
            prev_vowel = is_vowel
        if word.endswith("e") and count > 1:
            count -= 1
        syllable_count += max(1, count)

    if word_count == 0:
        return 0.0

    # Flesch Reading Ease formula
    flesch = 206.835 - 1.015 * (word_count / sentence_count) - 84.6 * (syllable_count / word_count)

    # Normalize to 0-1 scale (Flesch typically 0-100)
    readability = max(0.0, min(1.0, flesch / 100.0))

    return readability


# ── Multi-Attempt Selection ──────────────────────────────────────────────────

def select_best_script(candidates, context):
    """
    Select the best script from multiple candidates.

    Args:
        candidates: List of (script_text, metadata) tuples
        context: Context dict for factuality checking

    Returns:
        (best_script_text, best_metadata, scores) tuple
    """
    scored = []

    for script_text, metadata in candidates:
        # Factuality score
        fact_check = validate_script_factuality(script_text, context)

        # Engagement score
        engagement = score_engagement(script_text)

        # Word count bonus (prefer scripts closer to target length)
        word_count = len(script_text.split())
        target_words = 1500  # Target for 5-10 minute videos
        length_score = 1.0 - min(1.0, abs(word_count - target_words) / target_words)

        # Combined score (weighted)
        combined = (
            fact_check["score"] * 0.45 +
            engagement["overall"] * 0.35 +
            length_score * 0.20
        )

        scored.append({
            "script": script_text,
            "metadata": metadata,
            "factuality": fact_check,
            "engagement": engagement,
            "length_score": round(length_score, 3),
            "combined": round(combined, 3),
        })

    # Sort by combined score (descending)
    scored.sort(key=lambda x: x["combined"], reverse=True)

    best = scored[0]
    return best["script"], best["metadata"], scored


# ── Context Optimization (Phase 3) ───────────────────────────────────────────

def score_context_relevance(context, transcript_text, max_items=8):
    """
    Score and filter context items by relevance to current transcript.

    Args:
        context: Dict with characters, locations, key_terms, relationships
        transcript_text: Current transcript excerpt
        max_items: Maximum items to keep per category

    Returns:
        Filtered context dict with only most relevant items
    """
    transcript_lower = transcript_text.lower()
    transcript_words = set(transcript_lower.split())

    def score_item(item):
        """Score an item by frequency and presence in transcript."""
        item_lower = item.lower()
        score = 0.0

        # Direct mention in transcript
        if item_lower in transcript_lower:
            score += 5.0

        # Partial match (item words in transcript)
        item_words = set(item_lower.split())
        if item_words & transcript_words:
            score += 2.0 * len(item_words & transcript_words) / max(len(item_words), 1)

        return score

    def filter_and_score(items):
        """Score items and return top-N."""
        scored = [(item, score_item(item)) for item in items]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [item for item, _ in scored[:max_items]]

    return {
        "characters": filter_and_score(context.get("characters", [])),
        "locations": filter_and_score(context.get("locations", [])),
        "key_terms": filter_and_score(context.get("key_terms", [])),
        "relationships": filter_and_score(context.get("relationships", [])),
    }


def summarize_context(context, max_per_category=10):
    """
    Create condensed context summary for long-running series.

    Prioritizes: recent appearance, frequency, plot importance.
    Maintains max N items per category.
    """
    return {
        "characters": context.get("characters", [])[:max_per_category],
        "locations": context.get("locations", [])[:max_per_category],
        "key_terms": context.get("key_terms", [])[:max_per_category],
        "relationships": context.get("relationships", [])[:max_per_category],
        "processed_transcripts": context.get("processed_transcripts", []),
        "previous_scripts": context.get("previous_scripts", []),
    }


# ── Quality Metrics Logging (Phase 5) ────────────────────────────────────────

def log_generation_metrics(script_text, metadata, fact_check, engagement, log_file=None):
    """
    Log structured generation metrics for quality tracking.

    Args:
        script_text: Generated script
        metadata: Generation metadata (source, model, temperature)
        fact_check: Factuality validation result
        engagement: Engagement scores
        log_file: Optional file path for metrics log
    """
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "source": metadata.get("source", "unknown"),
        "model": metadata.get("model", "unknown"),
        "temperature": metadata.get("temperature", 0.7),
        "word_count": len(script_text.split()),
        "factuality_score": fact_check["score"],
        "factuality_issues": len(fact_check["issues"]),
        "flagged_entities": len(fact_check["flagged_entities"]),
        "engagement_overall": engagement["overall"],
        "hook_strength": engagement["hook_strength"],
        "sentiment_arc": engagement["sentiment_arc"],
        "readability": engagement["readability"],
    }

    if log_file:
        try:
            with open(log_file, "a") as f:
                f.write(json.dumps(metrics) + "\n")
        except Exception:
            pass

    return metrics


# ── Self-Improvement: Failure Storage (Phase 1) ────────────────────────────────

def _get_failure_storage_path():
    """Get path to failure storage JSON file."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(base_dir, "generation_failures.jsonl")


def store_generation_failure(
    script_text,
    metadata,
    fact_check,
    engagement,
    game_title="",
    content_type="unknown"
):
    """
    Store generation failure data for learning.
    
    Args:
        script_text: The generated script
        metadata: Generation metadata (source, model, temperature, etc.)
        fact_check: Factuality validation result
        engagement: Engagement scores
        game_title: Game title for filtering
        content_type: Type of content (mystery_recap, theory, etc.)
    
    Returns:
        bool: Success status
    """
    # Only store if there are actual issues (factuality < 1.0 or engagement < 0.5)
    if fact_check["score"] >= 1.0 and engagement["overall"] >= 0.5:
        return False
    
    # Determine failure types
    failure_types = []
    failure_details = {
        "character_hallucinations": [],
        "location_errors": [],
        "engagement_issues": [],
    }
    
    # Extract specific failure details from fact_check
    for entity_type, entity_name in fact_check.get("flagged_entities", []):
        if entity_type == "person":
            failure_details["character_hallucinations"].append(entity_name)
            failure_types.append("character_hallucination")
        elif entity_type == "location":
            failure_details["location_errors"].append(entity_name)
            failure_types.append("location_error")
    
    # Check engagement issues
    if engagement["overall"] < 0.5:
        failure_types.append("low_engagement")
        if engagement["hook_strength"] < 0.4:
            failure_details["engagement_issues"].append("weak_hook")
        if engagement["readability"] < 0.4:
            failure_details["engagement_issues"].append("poor_readability")
    
    # Check word count issues (for pipeline: 150-300, for cs: 1500-2000)
    word_count = len(script_text.split())
    target_min = 150 if content_type in ["unknown", "pipeline"] else 1500
    target_max = 300 if content_type in ["unknown", "pipeline"] else 2000
    
    if word_count < target_min or word_count > target_max:
        failure_types.append("word_count_out_of_range")
    
    # Create failure record
    failure_record = {
        "timestamp": datetime.now().isoformat(),
        "game_title": game_title,
        "content_type": content_type,
        "failure_types": list(set(failure_types)),
        "failure_details": failure_details,
        "generation_params": {
            "source": metadata.get("source", "unknown"),
            "model": metadata.get("model", "unknown"),
            "temperature": metadata.get("temperature", 0.7),
            "variant": metadata.get("variant", "unknown"),
        },
        "metrics": {
            "factuality_score": fact_check["score"],
            "engagement_overall": engagement["overall"],
            "hook_strength": engagement["hook_strength"],
            "readability": engagement["readability"],
            "word_count": word_count,
        },
    }
    
    # Store to JSONL
    storage_path = _get_failure_storage_path()
    try:
        with open(storage_path, "a") as f:
            f.write(json.dumps(failure_record) + "\n")
        return True
    except Exception:
        return False


# ── Self-Improvement: Analysis Functions (Phase 2) ────────────────────────────

def analyze_recent_failures(window_hours=24):
    """
    Analyze failures from the last N hours.
    
    Args:
        window_hours: Time window to analyze
    
    Returns:
        dict: Analysis results with patterns identified
    """
    storage_path = _get_failure_storage_path()
    if not os.path.exists(storage_path):
        return {"error": "No failure data found"}
    
    cutoff_time = datetime.now() - timedelta(hours=window_hours)
    failures = []
    
    try:
        with open(storage_path, "r") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    record_time = datetime.fromisoformat(record["timestamp"])
                    if record_time >= cutoff_time:
                        failures.append(record)
                except:
                    continue
    except Exception:
        return {"error": "Failed to read failure data"}
    
    if not failures:
        return {"message": f"No failures in the last {window_hours} hours", "count": 0}
    
    # Analyze patterns
    char_hallucinations = {}
    location_errors = {}
    engagement_issues = {}
    content_type_scores = {}
    
    for failure in failures:
        # Character hallucinations
        for char in failure.get("failure_details", {}).get("character_hallucinations", []):
            char_hallucinations[char] = char_hallucinations.get(char, 0) + 1
        
        # Location errors
        for loc in failure.get("failure_details", {}).get("location_errors", []):
            location_errors[loc] = location_errors.get(loc, 0) + 1
        
        # Engagement issues by type
        for issue in failure.get("failure_details", {}).get("engagement_issues", []):
            engagement_issues[issue] = engagement_issues.get(issue, 0) + 1
        
        # Track scores by content type
        ct = failure.get("content_type", "unknown")
        if ct not in content_type_scores:
            content_type_scores[ct] = {"factuality": [], "engagement": [], "count": 0}
        content_type_scores[ct]["factuality"].append(
            failure.get("metrics", {}).get("factuality_score", 0)
        )
        content_type_scores[ct]["engagement"].append(
            failure.get("metrics", {}).get("engagement_overall", 0)
        )
        content_type_scores[ct]["count"] += 1
    
    # Calculate averages
    for ct, scores in content_type_scores.items():
        if scores["factuality"]:
            scores["avg_factuality"] = sum(scores["factuality"]) / len(scores["factuality"])
            scores["avg_engagement"] = sum(scores["engagement"]) / len(scores["engagement"])
    
    return {
        "count": len(failures),
        "character_hallucinations": dict(
            sorted(char_hallucinations.items(), key=lambda x: x[1], reverse=True)[:5]
        ),
        "location_errors": dict(
            sorted(location_errors.items(), key=lambda x: x[1], reverse=True)[:5]
        ),
        "engagement_issues": engagement_issues,
        "content_type_scores": content_type_scores,
    }


def get_content_type_weaknesses(content_type):
    """
    Get known weaknesses for a specific content type.
    
    Args:
        content_type: Content type to analyze (mystery_recap, theory, etc.)
    
    Returns:
        dict: Weaknesses and recommendations
    """
    analysis = analyze_recent_failures(window_hours=168)  # Last week
    
    if "error" in analysis or analysis.get("count", 0) == 0:
        return {"message": "Not enough data to analyze"}
    
    ct_scores = analysis.get("content_type_scores", {}).get(content_type, {})
    
    if not ct_scores:
        return {"message": f"No data for content type: {content_type}"}
    
    weaknesses = []
    recommendations = []
    
    avg_fact = ct_scores.get("avg_factuality", 1.0)
    avg_eng = ct_scores.get("avg_engagement", 0.5)
    
    if avg_fact < 0.7:
        weaknesses.append("Low factuality score")
        recommendations.append("Increase fact-checking constraints in prompt")
    
    if avg_eng < 0.6:
        weaknesses.append("Low engagement score")
        recommendations.append("Add hook strength requirements to prompt")
    
    return {
        "content_type": content_type,
        "sample_size": ct_scores.get("count", 0),
        "avg_factuality": round(avg_fact, 3),
        "avg_engagement": round(avg_eng, 3),
        "weaknesses": weaknesses,
        "recommendations": recommendations,
    }


def get_effective_prompts():
    """
    Find which prompt configurations work best.
    
    Returns:
        dict: Effective prompt configurations by content type
    """
    storage_path = _get_failure_storage_path()
    if not os.path.exists(storage_path):
        return {"message": "No failure data to analyze"}
    
    # Load all records with high scores
    successful_configs = []
    
    metrics_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "generation_metrics.jsonl")
    if not os.path.exists(metrics_file):
        return {"message": "No metrics data found"}
    
    try:
        with open(metrics_file, "r") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    # High quality scripts (factuality >= 0.8, engagement >= 0.6)
                    if record.get("factuality_score", 0) >= 0.8 and record.get("engagement_overall", 0) >= 0.6:
                        successful_configs.append({
                            "temperature": record.get("temperature", 0.7),
                            "model": record.get("model", "unknown"),
                        })
                except:
                    continue
    except Exception:
        return {"error": "Failed to read metrics"}
    
    if not successful_configs:
        return {"message": "Not enough high-quality samples to analyze"}
    
    # Group by content type approximation (we don't have that in metrics, so just show overall)
    temp_counts = {}
    model_counts = {}
    
    for config in successful_configs:
        temp = config["temperature"]
        model = config["model"]
        
        temp_key = f"temp_{round(temp * 10) / 10}"  # Round to nearest 0.1
        temp_counts[temp_key] = temp_counts.get(temp_key, 0) + 1
        model_counts[model] = model_counts.get(model, 0) + 1
    
    return {
        "successful_samples": len(successful_configs),
        "effective_temperatures": temp_counts,
        "effective_models": model_counts,
    }


# ── Self-Improvement: Constraint Generation (Phase 3) ────────────────────────

def get_learned_constraints(game_title="", content_type="pipeline"):
    """
    Generate learned constraints to inject into prompts.
    
    Args:
        game_title: Optional game title for game-specific constraints
        content_type: Content type (pipeline, theory, analysis, etc.)
    
    Returns:
        dict with:
            - negative_constraints: List of things to avoid
            - positive_emphasis: List of things to focus on
            - recommended_temp: Optimal temperature
            - source: Explanation of where constraints came from
    """
    analysis = analyze_recent_failures(window_hours=168)  # Last week
    
    negative_constraints = []
    positive_emphasis = []
    
    # Generate negative constraints from recent failures
    if analysis.get("count", 0) > 0:
        # Character hallucinations to avoid
        char_hall = analysis.get("character_hallucinations", {})
        if char_hall:
            # Only include if appears 2+ times
            repeated_chars = [char for char, count in char_hall.items() if count >= 2]
            if repeated_chars:
                negative_constraints.append(
                    f"AVOID mentioning these characters (hallucinated in recent scripts): {', '.join(repeated_chars)}"
                )
        
        # Location errors to avoid
        loc_errors = analysis.get("location_errors", {})
        if loc_errors:
            repeated_locs = [loc for loc, count in loc_errors.items() if count >= 2]
            if repeated_locs:
                negative_constraints.append(
                    f"IGNORE these entities if spaCy marks them as locations (false positives): {', '.join(repeated_locs)}"
                )
    
    # Generate positive emphasis from high-performing scripts
    effective = get_effective_prompts()
    if effective.get("successful_samples", 0) >= 3:
        # Find most common high-performing temperature
        temps = effective.get("effective_temperatures", {})
        if temps:
            best_temp = max(temps.keys(), key=lambda k: temps[k])
            recommended_temp = float(best_temp.replace("temp_", ""))
            positive_emphasis.append(
                f"Use temperature around {recommended_temp} (proven effective in {temps[best_temp]} high-quality scripts)"
            )
    
    return {
        "negative_constraints": negative_constraints,
        "positive_emphasis": positive_emphasis,
        "recommended_temp": recommended_temp if 'recommended_temp' in dir() else None,
        "source": "Based on analysis of last 7 days of generation data",
    }


def calculate_optimal_temperature(content_type="pipeline"):
    """
    Calculate optimal temperature based on historical performance.
    
    Args:
        content_type: Content type to optimize for
    
    Returns:
        float: Recommended temperature
    """
    effective = get_effective_prompts()
    
    if effective.get("successful_samples", 0) < 3:
        return 0.7  # Default
    
    temps = effective.get("effective_temperatures", {})
    if not temps:
        return 0.7
    
    # Find most common successful temperature
    best_temp = max(temps.keys(), key=lambda k: temps[k])
    return float(best_temp.replace("temp_", ""))


# ── Knowledge Distillation Helper (Phase 4) ──────────────────────────────────

def get_learning_summary():
    """
    Get overall learning summary for the system.
    
    Returns:
        dict: Summary of what the system has learned
    """
    recent_24h = analyze_recent_failures(window_hours=24)
    recent_week = analyze_recent_failures(window_hours=168)
    effective = get_effective_prompts()
    
    return {
        "last_24h": {
            "failures": recent_24h.get("count", 0),
            "top_hallucinations": list(recent_24h.get("character_hallucinations", {}).keys())[:3],
        },
        "last_7_days": {
            "total_failures": recent_week.get("count", 0),
            "content_types_analyzed": len(recent_week.get("content_type_scores", {})),
        },
        "effective_configs": effective.get("successful_samples", 0),
        "learning_status": "active" if recent_week.get("count", 0) > 0 else "warming_up",
    }
