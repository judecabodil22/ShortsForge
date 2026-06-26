#!/usr/bin/env python3
"""
Cogitator Pipeline Context

Shared state object passed between pipeline phases.
Replaces the 40+ global variables that were scattered across cogitator.py.
"""
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from workflows.constants import TTS_VOICES, TTS_STYLE_OPTIONS
from workflows.core.round_robin import init_round_robin, get_next_variant_perspective, get_next_voice_style, reset as reset_round_robin


@dataclass
class PipelineContext:
    """Shared state for a single pipeline run.
    
    Created at pipeline start, passed to each phase.
    Contains learning state, round-robin indices, script mappings, etc.
    """
    # Game info
    game_title: str = ""
    game_key: str = ""
    
    # Learning state (refreshed at pipeline start)
    baseline: Dict[str, Any] = field(default_factory=dict)
    variant_weights: Dict[str, float] = field(default_factory=dict)
    variant_stats: Dict[str, Any] = field(default_factory=dict)
    tts_weights: List[Dict] = field(default_factory=list)
    optimized_params: Dict[str, Any] = field(default_factory=dict)
    
    # Round-robin (managed by core.round_robin)
    num_scripts: int = 0
    
    # Script-to-DB mapping (links clips to scripts)
    script_id_map: Dict[int, str] = field(default_factory=dict)  # {hour_index: script_id}
    
    # Phase results
    video_path: Optional[str] = None
    transcript_path: Optional[str] = None
    duration_seconds: int = 0
    
    # Pipeline control
    stop_requested: bool = False
    
    def clear(self) -> None:
        """Clear state between pipeline runs."""
        self.script_id_map.clear()
        self.video_path = None
        self.transcript_path = None
        self.duration_seconds = 0
        self.stop_requested = False
        reset_round_robin()
    
    def init_round_robin(self) -> None:
        """Initialize round-robin from learning state."""
        init_round_robin(
            num_scripts=self.num_scripts,
            variant_keys=list(self.variant_weights.keys()) if self.variant_weights else [],
            perspectives=["first_person", "third_person", "omniscient"],
            variant_weights=self.variant_weights,
            tts_weights=self.tts_weights,
        )
    
    def get_next_variant_perspective(self) -> tuple:
        """Get next round-robin variant and perspective."""
        return get_next_variant_perspective(
            list(self.variant_weights.keys()) if self.variant_weights else ["default"],
            ["first_person", "third_person", "omniscient"],
        )
    
    def get_next_voice_style(self) -> tuple:
        """Get next round-robin voice and style."""
        return get_next_voice_style()
    
    def get_variant_weight(self, variant_key: str) -> float:
        """Get weight for a variant."""
        return self.variant_weights.get(variant_key, 1.0)


# ─── Global singleton (for backward compat with existing code) ────────────────

_pipeline_ctx: Optional[PipelineContext] = None


def get_pipeline_context() -> PipelineContext:
    """Get the global pipeline context singleton."""
    global _pipeline_ctx
    if _pipeline_ctx is None:
        _pipeline_ctx = PipelineContext()
    return _pipeline_ctx


def reset_pipeline_context() -> None:
    """Reset the global pipeline context."""
    global _pipeline_ctx
    _pipeline_ctx = None


def init_pipeline_context(game_title: str, num_scripts: int) -> PipelineContext:
    """Initialize pipeline context for a new run."""
    global _pipeline_ctx
    _pipeline_ctx = PipelineContext(
        game_title=game_title,
        game_key=game_title.lower().replace(" ", "_"),
        num_scripts=num_scripts,
    )
    return _pipeline_ctx
