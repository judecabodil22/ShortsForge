"""LLM provider abstraction — wraps Groq, Gemini, and Gemini TTS API calls."""

import json
import os
import random
import time
import base64
import threading
import urllib.request
import urllib.error
from abc import ABC, abstractmethod

import requests

import workflows.cogitator as _sf
from workflows.cogitator import (
    log, log_error, env, get_gemini_keys, get_groq_keys,
    GROQ_KEY_INDEX, GROQ_MODEL, GROQ_MODELS_BY_TYPE, TEMPERATURE_BY_TYPE, LAST_CALL,
    SCRIPT_VARIANTS, _get_temperature, _get_groq_model,
    _get_next_round_robin, _build_script_prompt,
)


# ─── Rate Limiting ─────────────────────────────────────────────────────────────

_last_call = 0.0
_rate_lock = threading.Lock()

def _rate_limit():
    """Rate-limit Gemini API calls to max ~10 calls per minute (in-memory, thread-safe)."""
    global _last_call
    now = time.time()
    with _rate_lock:
        wait = 6 - (now - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()


# ─── Key Index Reset ──────────────────────────────────────────────────────────

def reset_key_index():
    """Reset the Groq key rotation index to zero."""
    _sf.GROQ_KEY_INDEX = 0


# ─── Base Provider ────────────────────────────────────────────────────────────

class BaseProvider(ABC):
    """Abstract base for all LLM providers."""

    @abstractmethod
    def generate(self, *args, **kwargs):
        """Execute an LLM generation call."""
        ...


# ─── Groq Provider ────────────────────────────────────────────────────────────

class GroqProvider(BaseProvider):
    """Groq API provider with key rotation and retry logic."""

    def generate(self, prompt, max_tokens=500, model=None, temperature=0.7):
        """Generate text via Groq with key rotation. Replicates _groq_generate."""
        groq_keys = get_groq_keys()
        if not groq_keys:
            raise RuntimeError("No Groq API keys configured")

        groq_model = model or GROQ_MODEL
        start_key = _sf.GROQ_KEY_INDEX

        for i in range(len(groq_keys)):
            key_index = (start_key + i) % len(groq_keys)
            api_key = groq_keys[key_index]

            log(f"   Trying Groq key ...{api_key[-6:]} (model: {groq_model}, temp: {temperature})")

            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": groq_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature
            }

            try:
                response = requests.post(url, json=data, headers=headers, timeout=60)
                if response.status_code == 200:
                    _sf.GROQ_KEY_INDEX = key_index
                    result = response.json()
                    log(f"   Using Groq key ...{api_key[-6:]}")
                    return result["choices"][0]["message"]["content"]
                elif response.status_code == 429:
                    log(f"   Groq key ...{api_key[-6:]} rate limited, trying next...")
                    continue
                else:
                    log(f"   Groq key ...{api_key[-6:]} error {response.status_code}")
                    continue
            except Exception as e:
                log(f"   Groq key ...{api_key[-6:]} failed: {e}")
                continue

        raise RuntimeError("All Groq API keys failed")


# ─── Gemini Provider ──────────────────────────────────────────────────────────

class GeminiProvider(BaseProvider):
    """Gemini provider for script generation and JSON prompts."""

    def generate(self, text, script_num, context=None):
        """Generate a script via Gemini with key rotation. Replicates _gemini_script."""
        keys = get_gemini_keys()
        if not keys:
            raise RuntimeError("No API keys in keychain")

        variant_key, perspective = _get_next_round_robin()
        game_title = env("GAME_TITLE", "")
        temperature = _get_temperature(variant_key)
        prompt = _build_script_prompt(variant_key, perspective, game_title, text[:3000], context)

        log(f"   Variant: {SCRIPT_VARIANTS[variant_key]['style']}, Perspective: {perspective[:50]}...")
        log(f"   Temperature: {temperature}, Context entities: {len(context.get('characters', [])) if context else 0} characters")

        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": 3072}
        }).encode()

        start = (script_num - 1) % len(keys)
        for i in range(len(keys)):
            key = keys[(start + i) % len(keys)]
            log(f"   Trying key ...{key[-6:]}")
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"

            for attempt in range(3):
                try:
                    _rate_limit()
                    req = urllib.request.Request(url, data=body,
                                                 headers={"Content-Type": "application/json",
                                                          "X-Goog-Api-Key": key})
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        r = json.loads(resp.read())
                        return r["candidates"][0]["content"]["parts"][0]["text"]
                except urllib.error.HTTPError as e:
                    if e.code in (429, 500, 503):
                        wait = (2 ** attempt) * 15 + random.uniform(0, 10)
                        log(f"   HTTP {e.code} with key ...{key[-6:]}, retry {attempt+1}/3 in {wait:.0f}s")
                        time.sleep(wait)
                    else:
                        log(f"   HTTP {e.code} with key ...{key[-6:]}")
                        break
                except Exception as e:
                    log(f"   Error: {e}")
                    time.sleep(5)
                    break

            log(f"   Key ...{key[-6:]} failed, next...")

        return None

    def generate_json(self, prompt, temperature=0.3, max_tokens=2048):
        """Send a prompt to Gemini and return parsed JSON response with key rotation and retries."""
        keys = get_gemini_keys()
        if not keys:
            return None

        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "response_mime_type": "application/json"
            }
        }).encode()

        _sf.GEMINI_KEY_INDEX = getattr(_sf, 'GEMINI_KEY_INDEX', 0)
        for i in range(len(keys)):
            key = keys[(_sf.GEMINI_KEY_INDEX + i) % len(keys)]
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"

            for attempt in range(3):
                try:
                    _rate_limit()
                    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json",
                                                                           "X-Goog-Api-Key": key})
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        r = json.loads(resp.read())
                        text = r["candidates"][0]["content"]["parts"][0]["text"]
                        _sf.GEMINI_KEY_INDEX = (_sf.GEMINI_KEY_INDEX + i + 1) % len(keys)
                        return json.loads(text)
                except urllib.error.HTTPError as e:
                    if e.code in (429, 500, 503):
                        wait = (2 ** attempt) * 15 + random.uniform(0, 10)
                        log(f"   HTTP {e.code} with key ...{key[-6:]}, retry {attempt+1}/3 in {wait:.0f}s")
                        time.sleep(wait)
                    else:
                        log(f"   HTTP {e.code} with key ...{key[-6:]}")
                        break
                except Exception as e:
                    log(f"   Gemini JSON attempt {attempt + 1} failed: {e}")
                    time.sleep(5)
                    break

            log(f"   Key ...{key[-6:]} failed for JSON, next...")

        _sf.GEMINI_KEY_INDEX = (_sf.GEMINI_KEY_INDEX + len(keys)) % len(keys)
        return None


# ─── Gemini JSON Provider ─────────────────────────────────────────────────────

class GeminiJsonProvider(BaseProvider):
    """Simpler Gemini provider for structured JSON extraction (from _gemini_json_prompt)."""

    def generate(self, prompt, temperature=0.3, max_tokens=2048):
        """Send a prompt to Gemini and return parsed JSON. Replicates _gemini_json_prompt."""
        keys = get_gemini_keys()
        if not keys:
            return None

        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "response_mime_type": "application/json"
            }
        }).encode()

        _sf.GEMINI_KEY_INDEX = getattr(_sf, 'GEMINI_KEY_INDEX', 0)
        key = keys[_sf.GEMINI_KEY_INDEX % len(keys)]
        _sf.GEMINI_KEY_INDEX = (_sf.GEMINI_KEY_INDEX + 1) % len(keys)
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
        _rate_limit()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json",
                                                               "X-Goog-Api-Key": key})

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                r = json.loads(resp.read())
                text = r["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text)
        except (json.JSONDecodeError, KeyError, urllib.error.HTTPError) as e:
            log(f"Gemini JSON prompt failed: {e}")
            return None


# ─── TTS Provider ─────────────────────────────────────────────────────────────

class TtsProvider(BaseProvider):
    """Gemini TTS provider for audio generation (from _tts_api)."""

    def generate(self, text, out_pcm, voice, style="", retries=3, delay=60):
        """Generate TTS audio via Gemini with key rotation. Replicates _tts_api."""
        if style:
            text = f"{style} {text}"

        body = json.dumps({
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}
            }
        }).encode()

        api_keys = get_gemini_keys()
        if not api_keys:
            fallback = env("GEMINI_API_KEY")
            api_keys = [fallback] if fallback else []

        if not api_keys:
            log("TTS: No Gemini API keys available")
            return False

        time.sleep(2)

        for key in api_keys:
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent"
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json",
                                                                   "X-Goog-Api-Key": key})

            for attempt in range(retries):
                try:
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        r = json.loads(resp.read())
                        audio = r["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
                        with open(out_pcm, "wb") as f:
                            f.write(base64.b64decode(audio))
                        return True
                except urllib.error.HTTPError as e:
                    if e.code in (429, 500, 503) and attempt < retries - 1:
                        wait = delay * (2 ** attempt) + random.uniform(0, 15)
                        log(f"   Key {key[:20]}... HTTP {e.code}, retry {attempt+1}/{retries} in {wait:.0f}s...")
                        time.sleep(wait)
                    else:
                        log(f"   Key {key[:20]}... failed: {e.code}")
                        break

            log("   Switching to next API key...")

        return False
