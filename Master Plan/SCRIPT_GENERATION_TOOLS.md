# Open Source Tools We Will Actually Use
## For ShortsForge Script Generation Improvement

Based on our specific use case in the ShortsForge pipeline, here are the exact open source tools we will implement and integrate:

## 1. CORE VALIDATION TOOLS (We WILL Use These)

### 1.1 FuzzyWuzzy / RapidFuzz
**Purpose**: Fuzzy string matching for detecting hallucinated character names and plot points
**Why We'll Use It**: 
- Lightweight, pure Python, no heavy dependencies
- Perfect for checking if mentioned names/items are close to verified ones
- Will use to catch misspellings or slight variations of real character names
**Integration**: In validation function to check script mentions against verified character/location lists

### 1.2 SpaCy (with en_core_web_sm model)
**Purpose**: Named Entity Recognition (NER) and sentence boundary detection
**Why We'll Use It**:
- Excellent at identifying person names, locations, and organizations in text
- Will extract all mentioned entities from scripts to verify against our verified context
- Lightweight enough for our pipeline
- Already has good English models
**Integration**: Run NER on generated scripts, extract PERSON and LOC entities, verify against verified context

### 1.3 TextBlob
**Purpose**: Sentiment analysis, part-of-speech tagging, noun phrase extraction
**Why We'll Use It**:
- Simple API for assessing script tone and engagement
- Will analyze sentiment progression through script (should have emotional arc)
- Will detect repetitive language patterns
- Very lightweight
**Integration**: In engagement scoring function to assess script quality

### 1.4 NLTK (Specific Modules Only)
**Purpose**: Readability scores and specific text metrics
**Why We'll Use It**:
- Only use: `nltk.corpus.stopwords`, `nltk.tokenize`, `nltk.metrics.distance`
- For: Readability scores (Flesch-Kincaid), stopword removal for keyword analysis
- Avoid downloading full data - just what we need
**Integration**: In engagement and readability scoring

## 2. PROMPT ENGINERING AIDS (We WILL Use These)

### 2.1 Jinja2 Template Engine
**Purpose**: Templating for complex, reusable prompts
**Why We'll Use It**:
- Already likely in our environment (common Python dependency)
- Makes complex prompts with conditionals and loops much cleaner
- Will template our enhanced few-shot prompts
**Integration**: Replace f-string prompts with Jinja2 templates for better maintainability

### 2.2 Python's Built-in string.Template
**Purpose**: Simple, safe template substitution
**Why We'll Use It**:
- No additional dependency needed
- Safer than f-strings for user-provided data
- Good for inserting verified context into prompts
**Integration**: For safely inserting character lists, plot points, etc. into prompts

## 3. TESTING AND VALIDATION (We WILL Use These)

### 3.1 Pytest
**Purpose**: Testing framework for our validation functions
**Why We'll Use It**:
- Already in most Python environments
- Will create test suite for our validation functions
- Will ensure our hallucination detection works correctly
**Integration**: Create `/home/alph4r1us/ShortsForge/tests/test_script_validation.py`

### 3.2 Built-in unittest
**Purpose**: Alternative testing framework
**Why We'll Use It**:
- No additional dependency
- Good for simple unit tests
**Integration**: For quick validation tests during development

## 4. MONITORING AND METRICS (We WILL Use These)

### 4.1 Prometheus Client Python
**Purpose**: Exporting metrics for monitoring
**Why We'll Use It**:
- Lightweight
- Can export quality metrics (hallucination rate, accuracy scores)
- Easy to integrate with existing monitoring
**Integration**: Export custom metrics like `shortsforge_script_hallucination_rate`, `shortsforge_script_accuracy_score`

### 4.2 Python's Built-in logging
**Purpose**: Structured logging of generation attempts
**Why We'll Use It**:
- Already using it extensively
- Will enhance to log generation attempts, validation results, selection criteria
**Integration**: Enhanced logging in script generation functions

## TOOLS WE CONSIDERED BUT WILL NOT USE (For Now)

### Not Using: ClaimBuster, FEVER
**Reason**: Too heavyweight for our needs. Our validation is simpler - we just need to check if entities mentioned are in our verified list, not perform complex fact-checking.

### Not Using: Full NLTK download
**Reason**: Only need specific modules. Will install just what we need via pip if not present.

### Not Using: LangChain, Guardrails AI (Initially)
**Reason**: While powerful, they add complexity. We'll start with simpler, direct implementations and consider these only if we need more sophisticated chaining or validation later.

### Not Using: DeepEval, Ragas, AuditLLM (Initially)
**Reason**: Overkill for our needs. We'll build simpler, targeted validation that fits our specific use case better than general LLM evaluation frameworks.

## SPECIFIC IMPLEMENTATION PLAN FOR EACH TOOL

### Tool 1: RapidFuzz (for fuzzy matching)
```python
# In validation function
from rapidfuzz import fuzz, process

def is_likely_real_name(mentioned_name, verified_names, threshold=80):
    """Check if a mentioned name is likely a real name (with possible misspelling)"""
    if not mentioned_name or not verified_names:
        return False
    
    # Direct match first
    if mentioned_name in verified_names:
        return True
    
    # Fuzzy match against verified names
    match = process.extractOne(mentioned_name, verified_names, scorer=fuzz.WRatio)
    return match is not None and match[1] >= threshold
```

### Tool 2: SpaCy (for NER)
```python
# In validation function  
import spacy

# Load once at module level
nlp = spacy.load("en_core_web_sm")

def extract_entities_from_script(script):
    """Extract all PERSON and LOC entities from script"""
    doc = nlp(script)
    entities = {
        'PERSON': [ent.text for ent in doc.ents if ent.label_ == 'PERSON'],
        'LOC': [ent.text for ent in doc.ents if ent.label_ == 'LOC']
    }
    return entities

# Then verify each extracted entity against verified lists
```

### Tool 3: TextBlob (for engagement scoring)
```python
# In engagement scoring function
from textblob import TextBlob

def calculate_engagement_score(script):
    """Calculate engagement score based on various factors"""
    blob = TextBlob(script)
    
    # Sentiment progression (should vary through script)
    sentences = blob.sentences
    if len(sentences) > 3:
        # Calculate sentiment variance - good scripts have emotional arc
        sentiments = [sentence.sentiment.polarity for sentence in sentences]
        sentiment_variance = np.var(sentiments) if len(sentiments) > 1 else 0
        sentiment_score = min(sentiment_variance * 10, 1.0)  # Normalize
    else:
        sentiment_score = 0.5
    
    # Subjectivity (should be moderately high for engaging content)
    subjectivity = blob.sentiment.subjectivity
    subjectivity_score = min(subjectivity * 1.2, 1.0)  # Optimal around 0.5-0.8
    
    # Combine scores
    return (sentiment_score * 0.4 + subjectivity_score * 0.6)
```

### Tool 4: Jinja2 (for templating prompts)
```python
# Instead of complex f-strings
from jinja2 import Template

script_prompt_template = Template("""
You are an expert video script writer for {{ game_title }} content. 
Your task is to create an engaging, accurate {{ target_length }}-word {{ content_type }} script.

{% if show_analysis %}
STEP 1 - ANALYSIS:
First, analyze the verified context:
- Characters mentioned: {{ stored_chars }}
- Key plot points: {{ plot_points_str }}
- Content angle: {{ angle }}
{% endif %}

{% if show_planning %}
STEP 2 - PLANNING:
Create a script outline with:
- Hook (first {{ hook_duration }} seconds): {{ hook_instruction }}
- Body: Develop {{ num_main_points }} main points with smooth transitions
- Conclusion: {{ conclusion_instruction }}
{% endif %}

STEP 3 - GENERATION WITH CONSTRAINTS:
Generate the script following these RULES:
{% for rule in generation_rules %}
{{ loop.index }}. {{ rule }}
{% endfor %}

{% if show_examples %}
EXAMPLES OF GOOD SCRIPTS:
{% for example in examples %}
{{ example.loop_index }}. {{ example.content }}
{% endfor %}
{% endif %}

NOW WRITE THE COMPLETE SCRIPT:
""")
```

## INTEGRATION APPROACH

We'll integrate these tools gradually:

### Week 1-2: Core Validation
- Add RapidFuzz for fuzzy name matching
- Add SpaCy for entity extraction
- Implement basic validation function
- Add multiple attempt selection (2-3 variants)

### Week 3-4: Engagement & Prompt Enhancement
- Add TextBlob for engagement scoring
- Add Jinja2 for better prompt templating
- Implement few-shot examples in prompts
- Add basic engagement scoring

### Week 5-6: Monitoring & Refinement
- Add Prometheus client for metrics export
- Enhance logging with structured data
- Create test suite with Pytest
- A/B test improvements against baseline

## VERIFICATION THAT TOOLS ARE SUITABLE

All selected tools:
1. Are lightweight and Python-native
2. Have minimal dependencies
3. Are well-maintained and widely used
4. Address our specific needs precisely
5. Can be installed via pip if not present
6. Work in our existing Python 3.14 environment
7. Don't require external services or APIs
8. Have permissive licenses (MIT, BSD, Apache 2.0)

This focused toolset will give us significant improvements in script quality and hallucination prevention without over-engineering the solution.