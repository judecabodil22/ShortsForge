# ShortsForge Self-Improvement Plan

## Executive Summary

This plan outlines a targeted self-improvement system for ShortsForge that leverages existing infrastructure to continuously improve script quality without over-engineering. Rather than implementing complex reflection loops or multi-agent systems, we'll enhance the current pipeline with learning capabilities that build on MemPalace, validation systems, and context tracking.

## Current State Analysis

### What's Working Well
- MemPalace integration for persistent memory
- Validation system with factuality and engagement scoring
- Context tracking from transcripts
- Modular 5-phase pipeline architecture
- Existing metrics logging (pipeline.log, generation_metrics.jsonl)
- CLI and Telegram bot interfaces

### Key Issues to Address
- Repetitive content generation
- Hallucinations (incorrect character/location mentions)
- Suboptimal engagement scores
- Lack of learning from past mistakes

## Recommended Approach: Minimal Viable Learning (MVL)

Instead of a full self-improvement architecture, we'll implement a focused learning system that:

1. **Enhances existing logging** to capture detailed failure patterns
2. **Adds simple pattern analysis** to identify recurring issues
3. **Injects learned constraints** into prompt generation
4. **Periodically distills successful patterns** into reusable guidelines

This approach leverages existing infrastructure while avoiding unnecessary complexity.

## Implementation Phases

### Phase 1: Enhanced Feedback Collection (Weeks 1-2)

**Goal**: Capture detailed failure patterns for learning

**Changes**:
1. Modify `log_generation_metrics()` in `script_validation.py` to store:
   - Specific validation failure types (character hallucination, location error, etc.)
   - Full script + validation feedback + metrics
   - Context: content type, game title, temperature, model used
   - Timestamp for temporal analysis

2. Create MemPalace collection for "generation_failures" with schema:
   ```
   {
     timestamp: ISO string,
     content_type: string,
     game_title: string,
     failure_types: [string],
     failure_details: {
       character_hallucinations: [string],
       location_errors: [string],
       repetition_issues: [string],
       engagement_score: float,
       factuality_score: float
     },
     generation_params: {
       temperature: float,
       model: string,
       prompt_variant: string
     },
     full_script: string
   }
   ```

### Phase 2: Pattern Analysis Functions (Weeks 2-3)

**Goal**: Transform raw failure data into actionable insights

**New Functions** (in `script_validation.py`):
1. `analyze_recent_failures(window_hours=24)` - Identify common mistake patterns
2. `get_content_type_weaknesses(content_type)` - Find problematic areas per content type
3. `get_effective_prompts()` - Find what prompt variations work best
4. `get_learned_constraints(game_title, content_type)` - Generate do/don't lists

**Analysis Examples**:
- "Character hallucinations: Max (4/5), Safi (3/5), Moses (2/5)"
- "Location errors: Tyler misclassified as location (spaCy issue)"
- "Content-type weakness: Mystery scripts have 30% lower engagement"
- "Effective patterns: Temperature 0.7 works best for Analysis content"

### Phase 3: Adaptive Prompt Engineering (Weeks 3-4)

**Goal**: Automatically improve prompts based on learned patterns

**Changes**:
1. Modify `_build_script_prompt()` in `shortsforge.py` to inject:
   - Negative constraints: "Avoid mentioning X (hallucinated in 3/5 recent scripts)"
   - Positive reinforcement: "Focus on Y (elements with >0.8 engagement in past scripts)"
   - Dynamic temperature adjustment based on historical performance

2. Example prompt enhancement:
   ```
   You are creating a Mystery script for [GAME_TITLE].
   
   LEARNED CONSTRAINTS:
   - AVOID mentioning these characters (hallucinated in recent scripts): Max, Safi
   - AVOID these location errors: Tyler (not actually a location)
   - EMPHASIZE these engaging elements: hidden clues, suspicious behavior
   
   [ORIGINAL PROMPT CONTINUES...]
   ```

### Phase 4: Knowledge Distillation (Ongoing)

**Goal**: Convert learnings into permanent system improvements

**Monthly Process**:
1. Review failure patterns in MemPalace
2. Distill successful techniques into reusable guidelines
3. Update system prompts with learned best practices
4. Create game-specific "do/don't" lists in MemPalace
5. Retire ineffective patterns, promote successful techniques

**Output Examples**:
- Game-specific constraint files in `memory/learned_constraints/`
- Updated prompt templates with built-in learned constraints
- Summary reports showing improvement trends

## Implementation Details

### Files to Modify
1. `workflows/shortsforge.py` - Enhanced prompt building and logging
2. `scripts/validation/script_validation.py` - Enhanced metrics logging and analysis functions
3. `memory/` - New directories for learned constraints and failure patterns

### Key Functions to Add
- `store_generation_failure()` - Detailed failure logging to MemPalace
- `get_learned_negative_constraints()` - Generate avoidance lists
- `get_learned_positive_emphasis()` - Generate focus recommendations
- `calculate_optimal_temperature()` - Based on historical performance
- `analyze_failure_patterns()` - Weekly analysis job

### Technologies Leveraged
- **MemPalace**: Already integrated - perfect for storing learning data
- **RapidFuzz**: Already used - good for similarity matching in analysis
- **Jinja2 templates**: Already used - flexible for dynamic prompt generation
- **Existing validation system**: Factuality and engagement scoring

## Success Metrics

1. **Reduction in repeated hallucination patterns** (target: 50% decrease in 4 weeks)
2. **Improvement in average factuality/engagement scores** (target: +0.15 in 8 weeks)
3. **Decrease in validation warnings** for known problematic elements
4. **Increased consistency** in script quality metrics
5. **Reduction in manual intervention** needed for quality control

## Why This Approach Fits ShortsForge

1. **Leverages Existing Infrastructure** - Uses MemPalace you already integrated
2. **Low Complexity** - No need for LLM-as-judge, reflection loops, or multi-agent systems
3. **High ROI** - Directly addresses observed issues (repetition, hallucinations, engagement)
4. **Transparent & Debuggable** - You can see exactly what's being learned and applied
5. **Incremental** - Start with just failure logging, add analysis later
6. **Respects Existing Workflow** - Enhancements happen at the edges, no core changes

## Effort Estimate

- **Phase 1 (Enhanced Logging)**: 2-4 hours
- **Phase 2 (Basic Analysis)**: 3-5 hours
- **Phase 3 (Adaptive Constraints)**: 4-6 hours
- **Phase 4 (Knowledge Distillation)**: 3-5 hours
- **Total**: ~12-20 hours for a meaningful learning system

## What to Avoid (Overkill for Your Needs)

- Full reflection loops (generate → critique → revise)
- LLM-as-judge systems for qualitative feedback
- Multi-agent architectures with specialized roles
- Fine-tuning or retraining models
- Complex reward modeling or reinforcement learning
- New user interface components

## First Steps

1. Enhance `log_generation_metrics()` to store detailed failure information
2. Create `get_learned_constraints()` function that returns learned do/don'ts
3. Modify `_build_script_prompt()` to inject these constraints
4. Create a simple `analyze_weekly_failures()` script to identify patterns

This approach will give you continuous improvement without the complexity overhead. The system will learn to avoid its past mistakes while staying grounded in your specific gaming content domain.

---
*Plan created based on analysis of existing ShortsForge infrastructure and identified improvement opportunities.*