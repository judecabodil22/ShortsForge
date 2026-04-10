#!/usr/bin/env python3
"""
ShortsForge Timeout Utilities

Calculate dynamic timeouts based on workload estimates.
Use this to set appropriate pipeline timeouts.

Usage:
    import timeout_utils
    timeout = timeout_utils.calculate_pipeline_timeout(
        num_scripts=2,
        num_clips_per_script=5,
        num_tts_segments=2
    )
"""

import os
import json
import math

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "games.json")


def load_config():
    """Load timeout configuration."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {
        "timeout_estimates": {
            "phase_3_per_script_seconds": 30,
            "phase_4_per_clip_minutes": 2,
            "phase_5_per_segment_seconds": 60,
            "buffer_percentage": 30
        }
    }


def calculate_phase_3_timeout(num_scripts: int) -> int:
    """Calculate Phase 3 (Script Generation) timeout in seconds."""
    config = load_config()
    estimate = config.get("timeout_estimates", {}).get("phase_3_per_script_seconds", 30)
    return num_scripts * estimate


def calculate_phase_4_timeout(num_clips: int) -> int:
    """Calculate Phase 4 (Clip Generation) timeout in minutes."""
    config = load_config()
    estimate = config.get("timeout_estimates", {}).get("phase_4_per_clip_minutes", 2)
    return num_clips * estimate


def calculate_phase_5_timeout(num_segments: int) -> int:
    """Calculate Phase 5 (TTS) timeout in seconds."""
    config = load_config()
    estimate = config.get("timeout_estimates", {}).get("phase_5_per_segment_seconds", 60)
    return num_segments * estimate


def calculate_pipeline_timeout(
    num_scripts: int = 1,
    num_clips_per_script: int = 5,
    num_tts_segments: int = 1
) -> int:
    """
    Calculate total pipeline timeout in seconds.
    
    Args:
        num_scripts: Number of scripts to generate
        num_clips_per_script: Number of clips per script
        num_tts_segments: Number of TTS segments to generate
    
    Returns:
        Total timeout in seconds (with 30% buffer)
    """
    config = load_config()
    buffer_pct = config.get("timeout_estimates", {}).get("buffer_percentage", 30) / 100
    
    phase_3 = calculate_phase_3_timeout(num_scripts)
    phase_4 = calculate_phase_4_timeout(num_clips_per_script * num_scripts) * 60
    phase_5 = calculate_phase_5_timeout(num_tts_segments)
    
    total = phase_3 + phase_4 + phase_5
    total_with_buffer = int(total * (1 + buffer_pct))
    
    return total_with_buffer


if __name__ == "__main__":
    print("ShortsForge Timeout Calculator")
    print("=" * 40)
    
    test_cases = [
        (1, 5, 1),
        (2, 10, 2),
        (3, 15, 3),
    ]
    
    for scripts, clips, segments in test_cases:
        timeout = calculate_pipeline_timeout(scripts, clips, segments)
        print(f"\nScripts: {scripts}, Clips: {clips}, TTS Segments: {segments}")
        print(f"  Estimated timeout: {timeout} seconds ({timeout/60:.1f} minutes)")
    
    print("\n" + "=" * 40)
    print("RECOMMENDED TIMEOUTS:")
    for scripts, clips, segments in test_cases:
        timeout = calculate_pipeline_timeout(scripts, clips, segments)
        print(f"  {scripts} script(s): {timeout}s ({timeout/60:.0f} min)")