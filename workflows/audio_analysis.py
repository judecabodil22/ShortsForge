#!/usr/bin/env python3
"""
ShortsForge Audio Analysis
Analyzes audio in video segments for highlight detection.
"""
import os
import subprocess
import tempfile
import re
from typing import Dict, List, Tuple, Optional


def analyze_audio_segment(video_path: str, start: float, end: float) -> Dict:
    """Analyze audio characteristics of a video segment."""
    features = {
        'volume_spike': False,
        'has_silence': False,
        'has_laughter': False,
        'has_excitement': False,
        'has_dialogue': False,
        'volume_peak': 0.0,
        'volume_rms': 0.0,
        'silence_ratio': 0.0,
        'audio_transitions': 0
    }
    
    temp_audio = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_audio = f.name
        
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start),
            '-i', video_path,
            '-t', str(end - start),
            '-vn', '-acodec', 'pcm_s16le',
            '-ar', '16000', '-ac', '1',
            temp_audio
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0:
            return features
        
        vol_features = _analyze_volume_levels(temp_audio)
        features.update(vol_features)
        
        transition_count = _detect_audio_transitions(temp_audio)
        features['audio_transitions'] = transition_count
        
        has_speech = _detect_speech(temp_audio)
        features['has_dialogue'] = has_speech
        
        features['has_laughter'] = _detect_laughter(temp_audio)
        features['has_excitement'] = features['volume_spike'] and features['has_dialogue']
        
    except Exception as e:
        pass
    finally:
        if temp_audio and os.path.exists(temp_audio):
            try:
                os.remove(temp_audio)
            except:
                pass
    
    return features


def _analyze_volume_levels(audio_path: str) -> Dict:
    """Analyze volume levels using ffmpeg's volumedetect."""
    try:
        cmd = [
            'ffmpeg', '-i', audio_path,
            '-af', 'volumedetect',
            '-f', 'null', '-'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stderr
        
        mean_vol_match = re.search(r'mean_volume:\s*([-\d.]+)\s*dB', output)
        max_vol_match = re.search(r'max_volume:\s*([-\d.]+)\s*dB', output)
        
        mean_vol = float(mean_vol_match.group(1)) if mean_vol_match else -30.0
        max_vol = float(max_vol_match.group(1)) if max_vol_match else -10.0
        
        return {
            'volume_peak': max_vol,
            'volume_rms': mean_vol,
            'volume_spike': max_vol > -3.0,
            'has_silence': mean_vol < -40.0
        }
    except:
        return {
            'volume_peak': -10.0,
            'volume_rms': -30.0,
            'volume_spike': False,
            'has_silence': False
        }


def _detect_audio_transitions(audio_path: str) -> int:
    """Detect number of significant audio transitions."""
    try:
        cmd = [
            'ffmpeg', '-i', audio_path,
            '-af', 'astat',
            '-f', 'null', '-'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stderr
        
        var_match = re.search(r'variance:\s*([\d.]+)', output)
        if var_match:
            variance = float(var_match.group(1))
            return min(int(variance / 5), 10)
        
        return 0
    except:
        return 0


def _detect_speech(audio_path: str) -> bool:
    """Detect if audio contains speech (basic energy-based detection)."""
    try:
        cmd = [
            'ffmpeg', '-i', audio_path,
            '-af', 'astat',
            '-f', 'null', '-'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stderr
        
        rms_match = re.search(r'RMS level dB:\s*([-\d.]+)', output)
        if rms_match:
            rms = float(rms_match.group(1))
            return rms > -35.0
        
        return False
    except:
        return False


def _detect_laughter(audio_path: str) -> bool:
    """Detect potential laughter based on audio patterns."""
    try:
        cmd = [
            'ffmpeg', '-i', audio_path,
            '-af', 'silencedetect=n=-40dB:d=0.3',
            '-f', 'null', '-'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stderr
        
        silence_count = output.count('silencedetect')
        return silence_count > 2 and silence_count < 20
        
    except:
        return False


def get_audio_features_for_scenes(video_path: str, scenes: List[Dict]) -> List[Dict]:
    """Analyze audio for all scenes and return enhanced scene data."""
    enhanced_scenes = []
    
    for scene in scenes:
        start = scene.get('start', 0)
        end = scene.get('end', 0)
        
        audio_features = analyze_audio_segment(video_path, start, end)
        
        enhanced_scene = {**scene, **audio_features}
        
        virality_score = _calculate_audio_virality_score(audio_features, scene)
        enhanced_scene['audio_virality_score'] = virality_score
        
        enhanced_scenes.append(enhanced_scene)
    
    return enhanced_scenes


def _calculate_audio_virality_score(audio_features: Dict, scene: Dict) -> float:
    """Calculate virality score based on audio features."""
    score = 30.0
    
    if audio_features.get('volume_spike'):
        score += 15
    
    if audio_features.get('has_laughter'):
        score += 12
    
    if audio_features.get('has_dialogue'):
        score += 8
    
    if audio_features.get('has_excitement'):
        score += 10
    
    if audio_features.get('has_silence'):
        score += 5
    
    transition_count = audio_features.get('audio_transitions', 0)
    if transition_count >= 2:
        score += min(transition_count * 2, 10)
    
    duration = scene.get('end', 0) - scene.get('start', 0)
    if 30 <= duration <= 60:
        score += 10
    elif 20 <= duration < 30 or 60 < duration <= 90:
        score += 5
    
    return min(score, 100.0)


def enhance_scene_selection(scenes: List[Dict], video_path: str = None) -> List[Dict]:
    """Enhance scene selection with audio analysis."""
    if not video_path or not os.path.exists(video_path):
        for scene in scenes:
            scene['audio_virality_score'] = scene.get('drama_score', 50)
        return scenes
    
    try:
        return get_audio_features_for_scenes(video_path, scenes)
    except Exception as e:
        for scene in scenes:
            scene['audio_virality_score'] = scene.get('drama_score', 50)
        return scenes


if __name__ == "__main__":
    print("Audio Analysis Module Test")
    print("-" * 40)
    print("Functions available:")
    print("  - analyze_audio_segment(video, start, end)")
    print("  - get_audio_features_for_scenes(video, scenes)")
    print("  - enhance_scene_selection(scenes, video_path)")
    print("  - _calculate_audio_virality_score(audio, scene)")