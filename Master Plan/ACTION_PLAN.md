# ShortsForge Script Generation Improvement Action Plan

## GOAL: Achieve human-quality, hallucination-free script generation

## CURRENT STATE
- Strong foundation with context-based restrictions
- Good API key management
- Basic anti-hallucination measures in place
- Room for quality improvement

## PHASE 1: PROMPT ENGINEERING (Days 1-3)
### Tasks:
1. Enhance `_cs_generate_script()` prompt with:
   - Expert role definition
   - Chain-of-thought reasoning steps
   - 2-3 few-shot examples of excellent scripts
   - Explicit output format requirements
   - Self-verification instructions

### Success Criteria:
- Generated scripts show improved structure
- Better adherence to verified facts
- More engaging openings and closings

## PHASE 2: VALIDATION SYSTEM (Days 4-7)
### Tasks:
1. Implement `validate_script_factuality()` function:
   - Check for invented character names
   - Verify all plot points come from transcript
   - Flag hallucinations for regeneration
2. Implement multiple attempt selection (2-3 variants)
3. Add basic engagement scoring

### Success Criteria:
- Hallucination rate reduced by 50%+
- Script selection based on quality metrics
- Fallback to best variant when issues detected

## PHASE 3: CONTEXT OPTIMIZATION (Days 8-10)
### Tasks:
1. Implement context relevance scoring:
   - Weight recent transcripts higher
   - Score by frequency and importance
2. Add context filtering (top 10 most relevant items)
3. Implement context summarization for long series

### Success Criteria:
- More focused, relevant context
- Reduced noise in prompt
- Better utilization of limited context window

## PHASE 4: MODEL OPTIMIZATION (Days 11-14)
### Tasks:
1. Implement dynamic model selection:
   - Gemini 2.5 Flash Lite for factual content
   - Gemini 2.5 Flash for creative/complex content
2. Add adaptive temperature settings by content type
3. Optimize token usage based on needs

### Success Criteria:
- Better quality/efficiency ratio
- Appropriate creativity levels per content type
- Reduced API costs where possible

## PHASE 5: FEEDBACK SYSTEM (Days 15-21)
### Tasks:
1. Implement quality metrics logging
2. Create A/B testing framework for prompts
3. Add continuous improvement pipeline
4. Establish baseline measurements

### Success Criteria:
- Data-driven improvement decisions
- Measurable quality improvements over time
- Ability to track progress against goals

## METRICS TO TRACK
- Hallucination rate (target: < 2%)
- Factual accuracy (target: > 95%)
- Viewer retention (first 30s: target > 70%)
- Engagement rate (likes/views: target > 8%)
- Average view duration (target: > 65%)

## OPEN SOURCE TOOLS TO LEVERAGE
- LanguageTool: Grammar/style checking
- spaCy: Entity recognition for validation
- TextBlob: Sentiment analysis
- Hugging Face Transformers: Custom validation
- DeepEval: LLM testing framework
- LangChain: Prompt chaining
- Guardrails AI: Output validation

## RISK MITIGATION
- A/B test all changes
- Maintain rollback capability
- Monitor metrics closely
- Keep backup of working implementation

## DELIVERABLES
1. Improved `_cs_generate_script()` function
2. Validation and selection system
3. Context optimization functions
4. Quality metrics tracking
5. Documentation of changes
6. Before/after quality comparison report

This plan will transform script generation from functional to exceptional while maintaining the strong anti-hallucination foundation.