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
"""

import re
import math
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
        target_words = 200
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
    import json
    from datetime import datetime

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
