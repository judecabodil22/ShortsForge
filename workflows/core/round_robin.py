#!/usr/bin/env python3
"""
Cogitator Round-Robin Engine

Manages learning-weighted rotation of script variants, perspectives,
TTS voices, and styles. Initialized once per pipeline run.
"""
import random
import threading
from typing import List, Tuple, Dict, Any

from workflows.constants import TTS_VOICES, TTS_STYLE_OPTIONS

# ─── State ───────────────────────────────────────────────────────────────────

_rr_lock = threading.Lock()
_rr_variants: List[str] = []
_rr_perspectives: List[str] = []
_rr_voices: List[str] = []
_rr_styles: List[str] = []
_rr_script_index: int = 0
_rr_tts_index: int = 0

# ─── Public API ──────────────────────────────────────────────────────────────

def init_round_robin(
    num_scripts: int,
    variant_keys: List[str],
    perspectives: List[str],
    variant_weights: Dict[str, float],
    tts_weights: List[Dict[str, Any]],
) -> None:
    """Initialize round-robin lists — learning-weighted, once per pipeline run.

    Args:
        num_scripts: Number of scripts to generate
        variant_keys: Available script variant keys
        perspectives: Available script perspectives
        variant_weights: {variant_key: weight} from learning
        tts_weights: [{voice, style, weight}] from learning
    """
    global _rr_variants, _rr_perspectives, _rr_voices, _rr_styles
    global _rr_script_index, _rr_tts_index

    all_voices = list(TTS_VOICES)
    all_styles = list(TTS_STYLE_OPTIONS)

    random.shuffle(perspectives)

    # Weighted variants
    weighted_variants = []
    for variant in variant_keys:
        weight = variant_weights.get(variant, 1.0)
        slots = max(1, round(weight * 2))
        weighted_variants.extend([variant] * slots)
    random.shuffle(weighted_variants)

    with _rr_lock:
        _rr_variants = (weighted_variants * ((num_scripts // max(len(weighted_variants), 1)) + 2))[:num_scripts]
        _rr_perspectives = (perspectives * ((num_scripts // max(len(perspectives), 1)) + 2))[:num_scripts]

        # Weighted TTS voice/style pairs
        if tts_weights:
            weighted_voices = []
            for item in tts_weights:
                slots = max(1, round(item['weight'] * 3))
                weighted_voices.extend([(item['voice'], item['style'])] * slots)
            random.shuffle(weighted_voices)
            voice_style_pairs = weighted_voices
        else:
            voice_style_pairs = [(v, s) for v in all_voices for s in all_styles]
            random.shuffle(voice_style_pairs)

        _rr_voices = [v for v, s in voice_style_pairs]
        _rr_styles = [s for v, s in voice_style_pairs]

        _rr_script_index = 0
        _rr_tts_index = 0


def get_next_variant_perspective(
    variant_keys: List[str],
    perspectives: List[str],
) -> Tuple[str, str]:
    """Get next round-robin variant and perspective, advance index."""
    global _rr_script_index
    with _rr_lock:
        if not _rr_variants:
            return random.choice(variant_keys), random.choice(perspectives)

        idx = _rr_script_index
        variant = _rr_variants[idx % len(_rr_variants)]
        perspective = _rr_perspectives[idx % len(_rr_perspectives)]
        _rr_script_index = idx + 1
    return variant, perspective


def get_next_voice_style() -> Tuple[str, str]:
    """Get next round-robin voice and style, advance index."""
    global _rr_tts_index
    with _rr_lock:
        if not _rr_voices:
            return random.choice(TTS_VOICES), random.choice(TTS_STYLE_OPTIONS)

        idx = _rr_tts_index
        voice = _rr_voices[idx % len(_rr_voices)]
        style = _rr_styles[idx % len(_rr_styles)]
        _rr_tts_index = idx + 1
    return voice, style


def reset() -> None:
    """Reset all round-robin state."""
    global _rr_variants, _rr_perspectives, _rr_voices, _rr_styles
    global _rr_script_index, _rr_tts_index
    with _rr_lock:
        _rr_variants = []
        _rr_perspectives = []
        _rr_voices = []
        _rr_styles = []
        _rr_script_index = 0
        _rr_tts_index = 0


def get_state() -> Dict[str, Any]:
    """Get current round-robin state for debugging."""
    with _rr_lock:
        return {
            'variants': len(_rr_variants),
            'perspectives': len(_rr_perspectives),
            'voices': len(_rr_voices),
            'styles': len(_rr_styles),
            'script_index': _rr_script_index,
            'tts_index': _rr_tts_index,
        }
