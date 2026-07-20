#!/usr/bin/env python3
"""
Cogitator LLM Highlight Ranker
Uses Groq (free, rate-limited) or Gemini to rank transcript segments
by predicted engagement/virality before clipping.

Returns segments sorted by predicted engagement, enabling
the pipeline to clip the most engaging moments first.
"""

import json
import os
import re
import time
from typing import List, Dict, Optional


def _get_groq_client():
    try:
        from groq import Groq
        return Groq
    except ImportError:
        return None


def _call_groq_rank(segments_text: str, api_key: str) -> Optional[str]:
    Groq = _get_groq_client()
    if Groq is None:
        return None
    try:
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a YouTube Shorts virality analyst. "
                        "Given a transcript split into segments, rank each segment "
                        "by how engaging/viral it would be as a YouTube Shorts clip.\n\n"
                        "Scoring factors:\n"
                        "- Hooks, questions,悬念 (cliffhangers): +high\n"
                        "- Emotional moments (surprise, awe, controversy): +high\n"
                        "- Action descriptions, dramatic reveals: +medium\n"
                        "- Exposition, setup, transitions: +low\n\n"
                        "Return ONLY a JSON array of objects with keys: "
                        '"segment_index", "score" (0-100), "reason" (1 word). '
                        "No markdown, no explanation."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Rank these transcript segments by virality:\n\n{segments_text}",
                },
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        return resp.choices[0].message.content
    except Exception:
        return None


def _call_gemini_rank(segments_text: str, api_key: str) -> Optional[str]:
    import urllib.request

    body = json.dumps({
        "contents": [{
            "parts": [{"text": (
                "You are a YouTube Shorts virality analyst. "
                "Given a transcript split into segments, rank each segment "
                "by how engaging/viral it would be as a YouTube Shorts clip.\n\n"
                "Scoring factors:\n"
                "- Hooks, questions, suspense: +high\n"
                "- Emotional moments (surprise, awe, controversy): +high\n"
                "- Action descriptions, dramatic reveals: +medium\n"
                "- Exposition, setup, transitions: +low\n\n"
                "Return ONLY a JSON array of objects with keys: "
                '"segment_index", "score" (0-100), "reason" (1 word). '
                "No markdown, no explanation."
            )}, {
                "text": f"Rank these transcript segments by virality:\n\n{segments_text}"
            }]
        }],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2000,
        },
    }).encode()

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            r = json.loads(resp.read())
            text = r.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return text
    except Exception:
        return None


def rank_segments(
    segments: List[Dict[str, float]],
    groq_keys: List[str] = None,
    gemini_keys: List[str] = None,
) -> List[Dict[str, float]]:
    if not segments:
        return []

    segment_lines = []
    for i, seg in enumerate(segments):
        txt = seg.get("text", "").replace("\n", " ")[:300]
        segment_lines.append(f"[{i}] {txt}")

    segments_text = "\n".join(segment_lines)
    ranked_text = None

    if groq_keys:
        for key in groq_keys:
            ranked_text = _call_groq_rank(segments_text, key)
            if ranked_text:
                break
            time.sleep(1)

    if not ranked_text and gemini_keys:
        for key in gemini_keys:
            ranked_text = _call_gemini_rank(segments_text, key)
            if ranked_text:
                break
            time.sleep(1)

    if not ranked_text:
        return segments

    try:
        cleaned = re.sub(r"```json\s*", "", ranked_text, flags=re.IGNORECASE)
        cleaned = re.sub(r"```\s*", "", cleaned).strip()
        rankings = json.loads(cleaned)

        score_map = {}
        for item in rankings:
            idx = item.get("segment_index")
            score = item.get("score", 50)
            if isinstance(idx, int) and 0 <= idx < len(segments):
                score_map[idx] = max(0, min(100, score))

        for i, seg in enumerate(segments):
            seg["llm_virality_score"] = score_map.get(i, 50)

        segments.sort(key=lambda x: x.get("llm_virality_score", 0), reverse=True)
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    return segments


def get_api_keys():
    from workflows.keychain_manager import get_groq_keys, get_gemini_keys
    groq_keys = get_groq_keys()
    gemini_keys = get_gemini_keys()
    return groq_keys, gemini_keys


def rank_segments_auto(segments: List[Dict[str, float]]) -> List[Dict[str, float]]:
    groq_keys, gemini_keys = get_api_keys()
    return rank_segments(segments, groq_keys, gemini_keys)
