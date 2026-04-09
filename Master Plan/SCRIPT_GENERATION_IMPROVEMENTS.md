# Script Generation Improvement Plan
## For ShortsForge Pipeline and Content Studio

## Executive Summary
This document outlines a comprehensive plan to improve script generation quality, eliminate hallucinations, and create human-like, engaging scripts that maintain factual accuracy while maximizing viewer engagement.

## Current State Analysis
The existing script generation in `_cs_generate_script()` function has a solid foundation with:
- Good context utilization (characters, locations, relationships)
- Strong anti-hallucination restrictions
- Content-type specific prompting
- Series continuity handling
- Proper API key management

However, several enhancements can significantly improve quality.

## Improvement Roadmap

### Phase 1: Prompt Engineering Enhancements (Immediate)

#### 1.1 Advanced Prompt Structure
- Implement few-shot learning with 2-3 high-quality examples
- Add chain-of-thought reasoning steps
- Specify output format more explicitly
- Add self-verification mechanisms

#### 1.2 Example Enhancement
```python
# Enhanced prompt structure
enhanced_prompt = f"""
You are an expert video script writer for gaming content. Your task is to create an engaging, accurate 1500-word script.

STEP 1 - ANALYSIS:
First, analyze the verified context:
- Characters mentioned: {stored_chars}
- Key plot points: {plot_points_str}
- Content angle: {angle}

STEP 2 - PLANNING:
Create a script outline with:
- Hook (first 15 seconds): Grab attention with surprising fact or question
- Body: Develop 3-4 main points with smooth transitions
- Conclusion: Call to action and teaser for next content

STEP 3 - GENERATION WITH CONSTRAINTS:
Generate the script following these RULES:
1. ONLY use characters from: {allowed_chars}
2. ONLY reference events from: {plot_points_str}
3. NEVER invent character names, abilities, or plot points
4. If uncertain, use generic terms like "a character" or "someone"
5. Maintain {content_type} tone throughout

EXAMPLES OF GOOD SCRIPTS:
[Example 1: Theory video about Life is Strange]
[Example 2: Analysis video about character motivations]

NOW WRITE THE COMPLETE SCRIPT:
"""
```

### Phase 2: Quality Assurance System (Short-term)

#### 2.1 Post-Generation Validation
```python
def validate_script_factuality(script, transcript, verified_context):
    """Check script for hallucinations against source material."""
    # Extract mentioned characters from script
    # Compare against verified character list
    # Flag any invented names or details
    # Return validation score and issues
    pass

def calculate_engagement_score(script):
    """Score script on engagement factors."""
    # Hook strength in first 100 words
    # Pacing and variation
    # Call to action effectiveness
    # Return engagement score
    pass
```

#### 2.1 Multiple Attempt Selection
```python
def generate_best_script(transcript_text, content_type, subject, angle, real_characters, key_plot_points, num_attempts=3):
    """Generate multiple scripts and select the best."""
    scripts = []
    scores = []
    
    for attempt in range(num_attempts):
        # Vary temperature slightly for diversity
        temp = 0.7 + (attempt * 0.1)
        script = _generate_single_script(transcript_text, content_type, subject, angle, real_characters, key_plot_points, temperature=temp)
        
        # Validate and score
        validation = validate_script_factuality(script, transcript, verified_context)
        engagement = calculate_engagement_score(script)
        combined_score = validation['accuracy'] * 0.6 + engagement * 0.4
        
        scripts.append(script)
        scores.append(combined_score)
    
    # Return highest scoring script
    best_index = scores.index(max(scores))
    return scripts[best_index], validation_results[best_index]
```

### Phase 3: Advanced Context Management (Mid-term)

#### 3.1 Context Relevance Scoring
```python
def score_context_relevance(transcript_segment, context_item, context_type):
    """Score how relevant a context item is to the current transcript."""
    # Character relevance: frequency in recent segments
    # Location relevance: proximity to events
    # Relationship relevance: connection to current focus
    # Return relevance score 0-1
    pass

def filter_relevant_context(full_context, transcript_segment, threshold=0.7):
    """Filter context to only highly relevant items."""
    relevant_chars = [c for c in full_context['characters'] 
                     if score_context_relevance(transcript_segment, c, 'character') > threshold]
    # Similar for locations, relationships
    return filtered_context
```

#### 3.2 Context Summarization for Long Series
```python
def create_context_summary(full_context, max_items=10):
    """Create a summary of context for long-running series."""
    # Prioritize by:
    # 1. Recent appearance (last 3 transcripts)
    # 2. Frequency of mention
    # 3. Importance to plot
    # Return top items for each category
    pass
```

### Phase 4: Model Optimization (Mid-term)

#### 4.1 Dynamic Model Selection
```python
def select_optimal_model(content_type, script_length, complexity_indicators):
    """Select the best model for the task."""
    # Simple analysis/factual content: Gemini 2.5 Flash Lite (fast, cheap)
    # Complex theory/creative content: Gemini 2.5 Flash (more capable)
    # Very long/specialized: Consider other models if available
    pass

def get_optimal_temperature(content_type):
    """Get optimal temperature for content type."""
    temperatures = {
        "Theory": 0.9,      # More creative for speculation
        "Analysis": 0.6,    # More factual for analysis
        "Review": 0.7,      # Balanced for opinion
        "Mystery": 0.8,     # Engaging for reveals
        "Lore": 0.7,        # Educational but engaging
        "Documentary": 0.5  # Most factual
    }
    return temperatures.get(content_type, 0.7)
```

### Phase 5: Feedback & Learning System (Long-term)

#### 5.1 Quality Metrics Tracking
```python
def log_script_quality(script_id, metrics):
    """Log quality metrics for continuous improvement."""
    # Accuracy score (from validation)
    # Engagement score 
    # Length compliance
    # Readability scores
    # Store for analysis and improvement
    pass

def get_improvement_suggestions():
    """Analyze logged metrics to suggest prompt/model improvements."""
    # Analyze which content types have lowest accuracy
    # Identify common hallucination patterns
    # Suggest specific prompt adjustments
    pass
```

## Implementation Priority

### Immediate (Week 1):
1. Enhanced prompt with few-shot examples
2. Basic validation system
3. Multiple attempt selection (2-3 attempts)

### Short-term (Weeks 2-3):
1. Context relevance scoring
2. Dynamic model/temperature selection
3. Basic quality metrics logging

### Mid-term (Weeks 4-6):
1. Advanced context summarization
2. Ensemble generation approaches
3. Feedback integration system
4. A/B testing framework for prompts

## Open Source Tools for Implementation

### 1. Text Quality Assessment
- **LanguageTool**: Grammar and style checking
- **TextBlob**: Sentiment analysis and POS tagging
- **spaCy**: Advanced NLP for entity recognition
- **NLTK**: Text processing and readability scores

### 2. Fact Checking & Validation
- **ClaimBuster**: Automated claim detection
- **FEVER**: Fact extraction and verification
- **Hugging Face Transformers**: For custom validation models

### 3. Prompt Engineering
- **PromptHub**: Community for sharing and testing prompts
- **LangChain**: For building prompt chains and agents
- **Guardrails AI**: For adding validation and guards to LLM outputs

### 4. Testing & Evaluation
- **DeepEval**: LLM unit testing framework
- **Ragas**: Retrieval-augmented generation evaluation
- **AuditLLM**: LLM output auditing and monitoring

## Human-Like Script Characteristics to Emulate

Based on analysis of high-quality gaming video scripts:

### 1. Opening Patterns
- Start with a provocative question or surprising fact
- Use "You won't believe..." or "What if I told you..."
- Reference recent events or trends in the game
- Create immediate curiosity gap

### 2. Flow Characteristics
- Conversational but polished (like explaining to a friend)
- Varied sentence length and structure
- Natural transitions ("Speaking of...", "This reminds me of...")
- Appropriate pacing with buildup and release

### 3. Engagement Techniques
- Rhetorical questions
- "Imagine if..." scenarios
- References to shared community experiences
- Callbacks to earlier points in the video
- Clear signposting ("First..., Second..., Finally...")

### 4. Closing Patterns
- Strong call to action (like/subscribe)
- Teaser for next content
- Community engagement prompt (comment question)
- Gratitude and sign-off

## Testing Methodology

### A/B Testing Framework
```
Group A: Current script generation
Group B: Improved script generation
Metrics to track:
- Viewer retention rate
- Like/dislike ratio
- Comment engagement
- Watch time completion
- Factual accuracy (expert review)
```

### Validation Dataset
Create a test set of:
- 10 transcripts with known good scripts
- Hallucination test cases (transcripts with deliberate omissions)
- Edge cases (minimal transcripts, complex narratives)
- Cross-game consistency tests

## Success Metrics

### Quality Targets:
- Hallucination rate: < 2% (expert review)
- Factual accuracy: > 95%
- Viewer retention (first 30 seconds): > 70%
- Average view duration: > 65% of video length
- Engagement rate (likes/views): > 8%

## Implementation Steps

1. **Document current baseline** - Measure existing script quality
2. **Implement Phase 1 enhancements** - Better prompts and validation
3. **Test and measure improvements** - Compare against baseline
4. **Iterate based on results** - Refine based on metrics
5. **Progress to next phase** - Continue improvements
6. **Establish monitoring** - Ongoing quality assurance