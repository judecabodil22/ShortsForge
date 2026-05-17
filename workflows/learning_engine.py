#!/usr/bin/env python3
"""
ShortsForge Learning Engine
Analyzes performance patterns and optimizes generation parameters.
"""
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple

WORKSPACE = os.path.expanduser("~/ShortsForge")


def analyze_performance_patterns(
    successful_scripts: List[Dict],
    all_metrics: List[Dict]
) -> Dict[str, Any]:
    """Analyze patterns in successful scripts."""
    if not successful_scripts or len(successful_scripts) < 3:
        return {
            'insights': [],
            'recommendations': {},
            'confidence': 0.0,
            'sample_count': len(successful_scripts) if successful_scripts else 0
        }
    
    insights = []
    
    content_type_performance = _analyze_content_types(successful_scripts)
    if content_type_performance:
        insights.append(content_type_performance)
    
    engagement_patterns = _analyze_engagement_patterns(successful_scripts)
    if engagement_patterns:
        insights.append(engagement_patterns)
    
    script_features = _analyze_script_features(successful_scripts)
    if script_features:
        insights.append(script_features)
    
    temporal_patterns = _analyze_temporal_patterns(successful_scripts)
    if temporal_patterns:
        insights.append(temporal_patterns)
    
    recommendations = _generate_recommendations(insights)
    
    confidence = min(len(successful_scripts) / 20, 1.0)
    
    return {
        'insights': insights,
        'recommendations': recommendations,
        'confidence': confidence,
        'sample_count': len(successful_scripts),
        'analyzed_at': datetime.now(timezone.utc).isoformat()
    }


def _analyze_content_types(scripts: List[Dict]) -> Optional[Dict]:
    """Analyze which content types perform best."""
    type_performance = defaultdict(lambda: {'views': [], 'engagement': [], 'scores': []})
    
    for script in scripts:
        content_type = script.get('content_type', 'unknown')
        views = script.get('views', 0)
        engagement = script.get('engagement_ratio', 0)
        score = script.get('performance_score', 0)
        
        if views > 0:
            type_performance[content_type]['views'].append(views)
            type_performance[content_type]['engagement'].append(engagement)
            type_performance[content_type]['scores'].append(score)
    
    if not type_performance:
        return None
    
    type_analysis = {}
    for content_type, data in type_performance.items():
        avg_views = sum(data['views']) / len(data['views']) if data['views'] else 0
        avg_engagement = sum(data['engagement']) / len(data['engagement']) if data['engagement'] else 0
        avg_score = sum(data['scores']) / len(data['scores']) if data['scores'] else 0
        
        type_analysis[content_type] = {
            'avg_views': avg_views,
            'avg_engagement': avg_engagement,
            'avg_score': avg_score,
            'sample_count': len(data['views'])
        }
    
    best_type = max(type_analysis.items(), key=lambda x: x[1]['avg_score'])
    
    return {
        'type': 'content_type',
        'analysis': type_analysis,
        'best_type': best_type[0],
        'best_performance': best_type[1],
        'recommendation': f"Content type '{best_type[0]}' performs best. Consider using it more."
    }


def _analyze_engagement_patterns(scripts: List[Dict]) -> Optional[Dict]:
    """Analyze engagement ratio patterns."""
    high_engagement = []
    low_engagement = []
    
    for script in scripts:
        engagement = script.get('engagement_ratio', 0)
        if engagement >= 3.0:
            high_engagement.append(script)
        elif engagement >= 1.0:
            low_engagement.append(script)
    
    if not high_engagement:
        return None
    
    patterns = {
        'high_engagement_hooks': _extract_common_hooks(high_engagement),
        'low_engagement_hooks': _extract_common_hooks(low_engagement)
    }
    
    best_hooks = patterns.get('high_engagement_hooks', [])
    
    return {
        'type': 'engagement',
        'patterns': patterns,
        'best_hooks': best_hooks[:5],
        'recommendation': f"High engagement videos often start with: {', '.join(best_hooks[:3])}" if best_hooks else "No clear hook pattern yet."
    }


def _analyze_script_features(scripts: List[Dict]) -> Optional[Dict]:
    """Analyze script feature patterns."""
    features_data = defaultdict(list)
    
    for script in scripts:
        features_str = script.get('features', '{}')
        if isinstance(features_str, str):
            try:
                features = json.loads(features_str)
            except:
                features = {}
        else:
            features = features_str or {}
        
        for key, value in features.items():
            features_data[key].append(value)
    
    feature_importance = {}
    for feature, values in features_data.items():
        if len(values) >= 3:
            if all(isinstance(v, (int, float)) for v in values):
                avg = sum(values) / len(values)
                feature_importance[feature] = {'avg': avg, 'count': len(values)}
    
    return {
        'type': 'script_features',
        'importance': feature_importance,
        'recommendation': "Script features analyzed. Optimal parameters being learned."
    }


def _analyze_temporal_patterns(scripts: List[Dict]) -> Optional[Dict]:
    """Analyze temporal patterns (duration, time of generation, etc.)."""
    durations = []
    
    for script in scripts:
        features_str = script.get('features', '{}')
        if isinstance(features_str, str):
            try:
                features = json.loads(features_str)
            except:
                features = {}
        else:
            features = features_str or {}
        
        duration = features.get('duration', 0) or features.get('clip_duration', 0)
        if duration > 0:
            durations.append(duration)
    
    if not durations:
        return None
    
    avg_duration = sum(durations) / len(durations)
    
    optimal_duration = 45
    duration_diff = abs(avg_duration - optimal_duration)
    
    recommendation = f"Average clip duration: {avg_duration:.0f}s. "
    if duration_diff > 15:
        recommendation += f"Consider targeting ~45s for optimal performance."
    else:
        recommendation += "Duration is within optimal range."
    
    return {
        'type': 'temporal',
        'avg_duration': avg_duration,
        'optimal_range': (30, 60),
        'recommendation': recommendation
    }


def _extract_common_hooks(scripts: List[Dict]) -> List[str]:
    """Extract common opening phrases from scripts."""
    hooks = []
    
    for script in scripts:
        script_text = script.get('script_text', '')
        if not script_text:
            continue
        
        lines = script_text.strip().split('\n')
        if lines:
            first_line = lines[0].strip()
            if len(first_line) > 10 and len(first_line) < 100:
                first_word = first_line.split()[0] if first_line.split() else ''
                if first_word and not first_word.isdigit():
                    hooks.append(first_line[:80])
    
    hook_counts = defaultdict(int)
    for hook in hooks:
        normalized = hook.lower().strip()
        hook_counts[normalized] += 1
    
    sorted_hooks = sorted(hook_counts.items(), key=lambda x: x[1], reverse=True)
    return [hook for hook, count in sorted_hooks if count >= 1]


def _generate_recommendations(insights: List[Dict]) -> Dict[str, Any]:
    """Generate actionable recommendations from insights."""
    recommendations = {
        'content_type': None,
        'optimal_duration': None,
        'script_patterns': [],
        'generation_params': {}
    }
    
    for insight in insights:
        if insight['type'] == 'content_type' and 'best_type' in insight:
            recommendations['content_type'] = insight['best_type']
            recommendations['generation_params']['content_type_weight'] = insight['best_performance']
        
        if insight['type'] == 'temporal':
            recommendations['optimal_duration'] = insight.get('avg_duration', 45)
        
        if insight['type'] == 'engagement' and 'best_hooks' in insight:
            recommendations['script_patterns'] = insight['best_hooks'][:5]
    
    return recommendations


def extract_nlp_features(script_text: str) -> Dict[str, Any]:
    """Extract NLP features from script text."""
    features = {}
    text_lower = script_text.lower()
    words = script_text.split()
    word_count = len(words)
    
    features['readability_score'] = calculate_readability(script_text)
    features['sentiment_polarity'] = calculate_sentiment(text_lower)
    features['emotional_intensity'] = calculate_emotional_intensity(text_lower)
    features['hook_strength'] = calculate_hook_strength(script_text)
    features['question_density'] = (script_text.count('?') / word_count * 100) if word_count > 0 else 0
    features['power_word_density'] = calculate_power_word_density(text_lower)
    features['urgency_score'] = calculate_urgency_score(text_lower)
    features['curiosity_score'] = calculate_curiosity_score(text_lower)
    features['dialogue_density'] = calculate_dialogue_density(script_text)
    features['unique_word_ratio'] = len(set(words)) / word_count if word_count > 0 else 0
    
    return features


def calculate_readability(text: str) -> float:
    """Calculate readability score (Flesch Reading Ease approximation)."""
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    words = text.split()
    
    if not sentences or not words:
        return 0
    
    num_sentences = len(sentences)
    num_words = len(words)
    num_syllables = sum(count_syllables(word) for word in words)
    
    if num_sentences == 0 or num_words == 0:
        return 0
    
    avg_sentence_length = num_words / num_sentences
    avg_syllables_per_word = num_syllables / num_words
    
    score = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
    return max(0, min(100, score))


def count_syllables(word: str) -> int:
    """Count syllables in a word."""
    word = word.lower()
    vowels = 'aeiouy'
    count = 0
    prev_was_vowel = False
    
    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_was_vowel:
            count += 1
        prev_was_vowel = is_vowel
    
    if word.endswith('e'):
        count -= 1
    if count <= 0:
        count = 1
    
    return count


def calculate_sentiment(text: str) -> float:
    """Calculate sentiment polarity (-1 to 1)."""
    positive_words = {
        'amazing': 0.8, 'incredible': 0.9, 'stunning': 0.7, 'fantastic': 0.9,
        'beautiful': 0.7, 'love': 0.9, 'great': 0.6, 'wonderful': 0.8,
        'exciting': 0.7, 'thrilling': 0.8, 'awesome': 0.8, 'perfect': 0.9,
        'best': 0.8, 'good': 0.5, 'success': 0.7, 'winning': 0.8,
        'victory': 0.8, 'happy': 0.7, 'joy': 0.8, 'celebrate': 0.7
    }
    negative_words = {
        'terrible': -0.8, 'horrible': -0.9, 'awful': -0.8, 'bad': -0.5,
        'worst': -0.9, 'dark': -0.4, 'fear': -0.6, 'scary': -0.6,
        'dangerous': -0.6, 'death': -0.7, 'destroy': -0.7, 'attack': -0.5,
        'fight': -0.4, 'struggle': -0.4, 'fail': -0.6, 'lost': -0.5,
        'pain': -0.7, 'suffer': -0.7, 'tragedy': -0.7, 'crisis': -0.6
    }
    
    score = 0
    count = 0
    for word, val in positive_words.items():
        if word in text:
            score += val
            count += 1
    for word, val in negative_words.items():
        if word in text:
            score += val
            count += 1
    
    if count == 0:
        return 0
    return score / count


def calculate_emotional_intensity(text: str) -> float:
    """Calculate emotional intensity based on exclamation marks and emotional words."""
    exclamation_density = text.count('!') / max(len(text.split()), 1) * 100
    
    emotional_words = [
        'shocking', 'incredible', 'amazing', 'unbelievable', 'devastating',
        'heartbreaking', 'stunning', 'astonishing', 'terrifying', 'horrifying',
        'epic', 'legendary', 'insane', 'crazy', 'mind-blowing'
    ]
    
    emotional_count = sum(1 for word in emotional_words if word in text)
    word_count = max(len(text.split()), 1)
    emotional_density = (emotional_count / word_count) * 100
    
    intensity = min(1.0, (exclamation_density * 0.3 + emotional_density * 0.7))
    return intensity


def calculate_hook_strength(script_text: str) -> float:
    """Calculate hook strength based on opening line analysis."""
    lines = script_text.strip().split('\n')
    if not lines:
        return 0
    
    first_line = lines[0].lower()
    strength = 0
    
    hook_starters = [
        'what nobody tells you', 'secret', 'truth about', 'never realized',
        'here\'s why', 'the reality is', 'you need to know', 'did you know',
        'discover', 'uncover', 'revealed', 'shocking', 'amazing'
    ]
    
    for starter in hook_starters:
        if starter in first_line:
            strength += 0.3
    
    if first_line.startswith('i\'m ') or first_line.startswith('i '):
        strength += 0.1
    
    if any(word in first_line for word in ['never', 'always', 'everyone', 'nobody']):
        strength += 0.2
    
    if re.search(r'\d+', first_line):
        strength += 0.15
    
    if '?' in first_line:
        strength += 0.2
    
    return min(1.0, strength)


def calculate_power_word_density(text: str) -> float:
    """Calculate density of power words that drive engagement."""
    power_words = {
        'secret': 0.8, 'truth': 0.7, 'revealed': 0.8, 'hidden': 0.6,
        'forgotten': 0.5, 'lost': 0.4, 'unknown': 0.5, 'mystery': 0.6,
        'legend': 0.7, 'ancient': 0.5, 'prophet': 0.6, 'dark': 0.4,
        'dangerous': 0.5, 'powerful': 0.6, 'divine': 0.7, 'source': 0.5,
        'quest': 0.6, 'journey': 0.5, 'fight': 0.4, 'battle': 0.5
    }
    
    word_count = max(len(text.split()), 1)
    score = 0
    
    for word, weight in power_words.items():
        if word in text:
            score += weight
    
    return min(1.0, (score / word_count) * 100)


def calculate_urgency_score(text: str) -> float:
    """Calculate urgency score based on time-sensitive language."""
    urgency_words = [
        'now', 'today', 'immediately', 'fast', 'quick', 'hurry',
        'running out', 'limited', 'last chance', 'deadline', 'urgent',
        'must', 'need to', 'before it\'s', 'don\'t wait', 'ends soon'
    ]
    
    word_count = max(len(text.split()), 1)
    urgency_count = sum(1 for word in urgency_words if word in text.lower())
    
    return min(1.0, (urgency_count / word_count) * 100 * 2)


def calculate_curiosity_score(text: str) -> float:
    """Calculate curiosity score based on question patterns and cliffhangers."""
    score = 0
    
    question_count = text.count('?')
    if question_count > 0:
        score += min(0.3, question_count * 0.1)
    
    curiosity_words = [
        'wonder', 'discover', 'find out', 'learn', 'mystery', 'secret',
        'hidden', 'unknown', 'uncover', 'reveal', 'what if', 'imagine'
    ]
    
    word_count = max(len(text.split()), 1)
    curiosity_count = sum(1 for word in curiosity_words if word in text.lower())
    score += min(0.4, (curiosity_count / word_count) * 100)
    
    if '...' in text:
        score += 0.2
    
    if text.endswith(('and', 'but', 'so', 'however')):
        score += 0.1
    
    return min(1.0, score)


def calculate_dialogue_density(text: str) -> float:
    """Calculate dialogue density (first person perspective)."""
    first_person_pronouns = ['i ', 'i\'m', 'i\'ve', 'i\'ll', 'my ', 'me ', 'we ', 'our ']
    
    word_count = max(len(text.split()), 1)
    fp_count = sum(text.lower().count(pronoun) for pronoun in first_person_pronouns)
    
    return min(1.0, (fp_count / word_count) * 100 / 3)


def extract_script_features(script_text: str, content_type: str = None) -> Dict[str, Any]:
    """Extract features from script text for learning."""
    basic_features = {
        'word_count': len(script_text.split()),
        'char_count': len(script_text),
        'has_question': '?' in script_text,
        'has_exclamation': '!' in script_text,
        'has_numbers': bool(re.search(r'\d+', script_text)),
        'paragraph_count': script_text.count('\n\n') + 1,
        'avg_sentence_length': _calculate_avg_sentence_length(script_text),
        'has_cta': any(phrase in script_text.lower() for phrase in ['subscribe', 'follow', 'like', 'comment', 'share']),
        'has_hook_words': any(word in script_text.lower() for word in ['secret', 'truth', 'revealed', 'never', 'amazing', 'shocking']),
        'capitalization_ratio': _calculate_caps_ratio(script_text)
    }
    
    nlp_features = extract_nlp_features(script_text)
    features = {**basic_features, **nlp_features}
    
    if content_type:
        features['content_type'] = content_type
    
    hooks = script_text.strip().split('\n')[:3]
    features['opening_lines'] = [h.strip()[:100] for h in hooks if h.strip()]
    
    return features


def _calculate_avg_sentence_length(text: str) -> float:
    """Calculate average sentence length."""
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return 0
    return sum(len(s.split()) for s in sentences) / len(sentences)


def _calculate_caps_ratio(text: str) -> float:
    """Calculate ratio of capital letters."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0
    return sum(1 for c in letters if c.isupper()) / len(letters)


def get_optimized_params(learnings: List[Dict], baseline: Dict) -> Dict[str, Any]:
    """Get optimized generation parameters based on learnings."""
    params = {
        'preferred_content_types': [],
        'optimal_duration_range': (30, 60),
        'script_length_range': (75, 150),
        'hook_strength_weight': 1.0,
        'engagement_keywords': []
    }
    
    for learning in learnings:
        if learning.get('confidence', 0) < 0.3:
            continue
        
        feature_name = learning.get('feature_name', '')
        impact = learning.get('impact_score', 0)
        
        if feature_name == 'content_type' and impact > 0:
            params['preferred_content_types'].append(learning.get('feature_value'))
        
        if feature_name == 'duration' and impact > 0.1:
            optimal = float(learning.get('feature_value', 45))
            params['optimal_duration_range'] = (max(20, optimal - 15), min(90, optimal + 15))
        
        if feature_name == 'engagement_ratio' and impact > 0.2:
            params['hook_strength_weight'] = 1.0 + (impact * 0.5)
    
    if params['preferred_content_types']:
        params['preferred_content_types'] = params['preferred_content_types'][:3]
    
    return params


def generate_script_variants(
    base_script: str,
    content_type: str,
    optimization_target: str = 'engagement'
) -> List[Dict]:
    """Generate optimized variants of a script based on learnings."""
    variants = []
    
    variant_1 = _optimize_for_hook_strength(base_script)
    variants.append({
        'type': 'hook_strength',
        'script': variant_1,
        'focus': 'Stronger opening hook'
    })
    
    variant_2 = _optimize_for_pacing(base_script)
    variants.append({
        'type': 'pacing',
        'script': variant_2,
        'focus': 'Better rhythm and tempo'
    })
    
    variant_3 = _optimize_for_engagement(base_script)
    variants.append({
        'type': 'engagement',
        'script': variant_3,
        'focus': 'More interactive and engaging'
    })
    
    return variants


def _optimize_for_hook_strength(script: str) -> str:
    """Optimize script for stronger hooks."""
    lines = script.strip().split('\n')
    if not lines:
        return script
    
    first_line = lines[0]
    
    hook_intensifiers = ['This is ', 'Here\'s ', 'The truth about ', 'What nobody tells you about ']
    
    has_hook_word = any(word in first_line.lower() for word in ['secret', 'truth', 'revealed', 'never', 'amazing'])
    
    if not any(intensifier in first_line for intensifier in hook_intensifiers) and not has_hook_word:
        intensifier = hook_intensifiers[len(first_line) % len(hook_intensifiers)]
        lines[0] = intensifier + first_line[0].lower() + first_line[1:] if len(first_line) > 1 else first_line
    
    return '\n'.join(lines)


def _optimize_for_pacing(script: str) -> str:
    """Optimize script for better pacing."""
    lines = [l.strip() for l in script.strip().split('\n') if l.strip()]
    
    for i, line in enumerate(lines):
        if len(line) > 150 and i < len(lines) - 1:
            mid = len(line) // 2
            for j in range(mid, len(line)):
                if line[j] == ' ':
                    lines[i] = line[:j]
                    lines.insert(i + 1, line[j+1:].strip())
                    break
    
    return '\n'.join(lines)


def _optimize_for_engagement(script: str) -> str:
    """Optimize script for engagement."""
    engagement_phrases = [
        'Can you relate?',
        'Let me know in the comments.',
        'What do you think?',
        'Follow for more.'
    ]
    
    lines = script.strip().split('\n')
    
    has_cta = any('?' in line or any(phrase in line.lower() for phrase in ['subscribe', 'like', 'comment']) for line in lines)
    
    if not has_cta and len(lines) >= 2:
        lines.append(engagement_phrases[len(lines) % len(engagement_phrases)])
    
    return '\n'.join(lines)


def calculate_virality_score(
    clip_features: Dict,
    learned_params: Dict = None
) -> float:
    """Calculate virality score for a clip based on features and learnings."""
    base_score = 50.0
    
    if clip_features.get('volume_spike', False):
        base_score += 15
    
    if clip_features.get('has_dialogue', False):
        base_score += 10
    
    if clip_features.get('has_excitement', False):
        base_score += 12
    
    duration = clip_features.get('duration', 45)
    if 30 <= duration <= 60:
        base_score += 8
    elif 20 <= duration < 30 or 60 < duration <= 90:
        base_score += 4
    
    if clip_features.get('scene_transition_count', 0) >= 3:
        base_score += 5
    
    if clip_features.get('has_laughter', False):
        base_score += 10
    
    if clip_features.get('has_silence', False):
        base_score += 3
    
    if learned_params:
        optimal_range = learned_params.get('optimal_duration_range', (30, 60))
        if optimal_range[0] <= duration <= optimal_range[1]:
            base_score += 10
    
    return min(base_score, 100.0)


def should_regenerate(script_features: Dict, learnings: List[Dict], baseline: Dict) -> Tuple[bool, str]:
    """Determine if a script should be regenerated based on learnings."""
    min_samples = baseline.get('sample_count', 0)
    
    if min_samples < 5:
        return False, "Not enough data for recommendations"
    
    confidence = sum(l.get('confidence', 0) for l in learnings) / max(len(learnings), 1)
    
    if confidence < 0.5:
        return False, f"Learning confidence too low ({confidence:.0%})"
    
    suboptimal_count = 0
    reasons = []
    
    for learning in learnings:
        if learning.get('impact_score', 0) < 0:
            suboptimal_count += 1
            reasons.append(f"{learning.get('feature_name')}: {learning.get('feature_value')}")
    
    if suboptimal_count > 3:
        return True, f"Script has {suboptimal_count} suboptimal features: {', '.join(reasons[:3])}"
    
    return False, "Script parameters within acceptable range"


def update_learning(
    feature_name: str,
    feature_value: str,
    metric_type: str,
    performance_before: float,
    performance_after: float
) -> Dict:
    """Update learning based on new performance data."""
    impact = performance_after - performance_before
    
    sample_increment = 1
    current_confidence = 0.5
    
    confidence = min(current_confidence + (sample_increment * 0.1), 0.95)
    
    return {
        'feature_name': feature_name,
        'feature_value': feature_value,
        'metric_type': metric_type,
        'impact_score': impact,
        'sample_count': sample_increment,
        'confidence': confidence,
        'updated_at': datetime.now(timezone.utc).isoformat()
    }


try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False


class ViralityPredictor:
    """XGBoost-based virality prediction model."""
    
    FEATURE_COLUMNS = [
        'word_count', 'char_count', 'has_question', 'has_exclamation',
        'has_numbers', 'paragraph_count', 'avg_sentence_length',
        'has_cta', 'has_hook_words', 'capitalization_ratio',
        'readability_score', 'sentiment_polarity', 'emotional_intensity',
        'hook_strength', 'question_density', 'power_word_density',
        'urgency_score', 'curiosity_score', 'dialogue_density', 'unique_word_ratio'
    ]
    
    def __init__(self):
        self.model = None
        self.is_trained = False
        self.model_path = os.path.join(WORKSPACE, '.shortsforge', 'virality_model.json')
        self._load_model()
    
    def _load_model(self):
        """Load model if exists."""
        if os.path.exists(self.model_path) and XGBOOST_AVAILABLE:
            try:
                self.model = xgb.XGBRegressor()
                self.model.load_model(self.model_path)
                self.is_trained = True
            except Exception:
                self.is_trained = False
    
    def _extract_features_array(self, features: Dict) -> List:
        """Extract feature values in correct order."""
        return [features.get(col, 0) for col in self.FEATURE_COLUMNS]
    
    def train(self, scripts_data: List[Dict]) -> Dict:
        """Train the virality prediction model.
        
        Args:
            scripts_data: List of dicts with 'features' and 'performance_score' keys
        
        Returns:
            Training results dict
        """
        if not XGBOOST_AVAILABLE:
            return {'success': False, 'error': 'XGBoost not installed'}
        
        valid_data = []
        for item in scripts_data:
            features = item.get('features', {})
            if isinstance(features, str):
                try:
                    features = json.loads(features)
                except:
                    continue
            
            score = item.get('performance_score', 0)
            if score > 0 and features:
                valid_data.append({'features': features, 'target': score})
        
        if len(valid_data) < 5:
            return {'success': False, 'error': f'Need at least 5 samples, got {len(valid_data)}'}
        
        X = [self._extract_features_array(d['features']) for d in valid_data]
        y = [d['target'] for d in valid_data]
        
        self.model = xgb.XGBRegressor(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42
        )
        
        self.model.fit(X, y)
        
        try:
            self.model.save_model(self.model_path)
        except Exception:
            pass
        
        self.is_trained = True
        
        feature_importance = dict(zip(self.FEATURE_COLUMNS, self.model.feature_importances_.tolist()))
        top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'success': True,
            'sample_count': len(valid_data),
            'top_features': top_features,
            'avg_predicted_score': float(sum(y) / len(y))
        }
    
    def predict(self, features: Dict) -> float:
        """Predict virality score for a script.
        
        Args:
            features: Script features dict
        
        Returns:
            Predicted performance score (0-100)
        """
        if not self.is_trained or not self.model:
            return 50.0
        
        try:
            X = [self._extract_features_array(features)]
            prediction = self.model.predict(X)[0]
            return max(0, min(100, prediction))
        except Exception:
            return 50.0
    
    def predict_batch(self, features_list: List[Dict]) -> List[float]:
        """Predict virality scores for multiple scripts."""
        if not self.is_trained or not self.model:
            return [50.0] * len(features_list)
        
        try:
            X = [self._extract_features_array(f) for f in features_list]
            predictions = self.model.predict(X)
            return [max(0, min(100, p)) for p in predictions]
        except Exception:
            return [50.0] * len(features_list)


_virality_predictor = None


def get_virality_predictor() -> ViralityPredictor:
    """Get singleton virality predictor instance."""
    global _virality_predictor
    if _virality_predictor is None:
        _virality_predictor = ViralityPredictor()
    return _virality_predictor


def predict_virality(script_features: Dict) -> float:
    """Predict virality score for a script.
    
    Convenience function using singleton predictor.
    """
    predictor = get_virality_predictor()
    return predictor.predict(script_features)


def train_virality_model(scripts_data: List[Dict]) -> Dict:
    """Train virality model from scripts data.
    
    Args:
        scripts_data: List of {features, performance_score} dicts
    
    Returns:
        Training results
    """
    predictor = get_virality_predictor()
    return predictor.train(scripts_data)