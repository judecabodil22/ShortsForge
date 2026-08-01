"""
Hardware detection for Cogitator.
Detects CPU, RAM, and GPU capabilities to optimize encoding settings.
"""
import os
import subprocess
import json
from functools import lru_cache


@lru_cache(maxsize=1)
def detect_cpu_cores():
    """Detect number of CPU cores."""
    try:
        import multiprocessing
        return multiprocessing.cpu_count()
    except Exception:
        return 4


@lru_cache(maxsize=1)
def detect_ram_gb():
    """Detect available RAM in GB."""
    try:
        with open('/proc/meminfo') as f:
            for line in f:
                if line.startswith('MemTotal'):
                    kb = int(line.split()[1])
                    return kb // (1024 * 1024)
        return 8
    except Exception:
        return 8


@lru_cache(maxsize=1)
def detect_nvidia_gpu():
    """Detect NVIDIA GPU via nvidia-smi."""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(',')
            name = parts[0].strip()
            vram_mb = int(parts[1].strip()) if len(parts) > 1 else 0
            return {'name': name, 'vram_mb': vram_mb, 'nvenc': True}
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass
    return None


@lru_cache(maxsize=1)
def detect_vaapi_device():
    """Detect VA-API device (AMD/Intel)."""
    try:
        result = subprocess.run(
            ['ffmpeg', '-hide_banner', '-hwaccels'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and 'vaapi' in result.stdout.lower():
            # Try to find render node
            for path in ['/dev/dri/renderD128', '/dev/dri/renderD129']:
                if os.path.exists(path):
                    return {'device': path, 'vaapi': True}
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass
    return None


@lru_cache(maxsize=1)
def detect_intel_qsv():
    """Detect Intel Quick Sync Video."""
    try:
        result = subprocess.run(
            ['ffmpeg', '-hide_banner', '-hwaccels'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and 'qsv' in result.stdout.lower():
            return {'qsv': True}
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass
    return None


def get_hardware_info():
    """Get complete hardware information."""
    cpu_cores = detect_cpu_cores()
    ram_gb = detect_ram_gb()
    nvidia = detect_nvidia_gpu()
    vaapi = detect_vaapi_device()
    intel_qsv = detect_intel_qsv()

    return {
        'cpu_cores': cpu_cores,
        'ram_gb': ram_gb,
        'gpu': {
            'nvidia': nvidia,
            'vaapi': vaapi,
            'intel_qsv': intel_qsv,
            'has_gpu': nvidia is not None or vaapi is not None or intel_qsv is not None,
        }
    }


def get_ffmpeg_encoding_settings():
    """
    Get optimal ffmpeg encoding settings based on hardware.
    Returns dict with video_codec, preset, extra_args.
    """
    hw = get_hardware_info()
    gpu = hw['gpu']

    # NVIDIA NVENC - fastest
    if gpu['nvidia'] and gpu['nvidia']['nvenc']:
        vram = gpu['nvidia']['vram_mb']
        # Use faster preset for low VRAM
        preset = 'p4' if vram >= 4096 else 'p2'
        return {
            'video_codec': 'h264_nvenc',
            'preset': preset,
            'extra_args': ['-rc', 'vbr', '-cq', '23'],
            'hw_accel': True,
            'gpu_name': gpu['nvidia']['name'],
        }

    # VA-API (AMD/Intel) - good for Linux
    if gpu['vaapi']:
        return {
            'video_codec': 'h264_vaapi',
            'preset': 'medium',
            'extra_args': [
                '-vaapi_device', gpu['vaapi']['device'],
            ],
            'hw_upload_filter': 'format=nv12,hwupload',
            'hw_accel': True,
            'gpu_name': 'VA-API',
        }

    # Intel QSV - good for Intel CPUs
    if gpu['intel_qsv']:
        return {
            'video_codec': 'h264_qsv',
            'preset': 'medium',
            'extra_args': ['-look_ahead', '1'],
            'hw_accel': True,
            'gpu_name': 'Intel QSV',
        }

    # CPU-only fallback - adapt preset to available cores
    cpu_cores = hw['cpu_cores']
    ram_gb = hw['ram_gb']

    # Choose preset based on CPU cores
    if cpu_cores >= 16:
        preset = 'fast'
    elif cpu_cores >= 8:
        preset = 'medium'
    elif cpu_cores >= 4:
        preset = 'slow'
    else:
        preset = 'veryslow'

    # Adjust threads
    threads = min(cpu_cores, 8)  # Cap at 8 threads for encoding

    return {
        'video_codec': 'libx264',
        'preset': preset,
        'extra_args': ['-threads', str(threads)],
        'hw_accel': False,
        'gpu_name': None,
    }


def get_whisper_device():
    """Get optimal device for Whisper transcription."""
    # Check for CUDA
    try:
        import torch
        if torch.cuda.is_available():
            return 'cuda'
    except ImportError:
        pass

    return 'cpu'


def get_encoding_summary():
    """Get a human-readable summary of hardware capabilities."""
    hw = get_hardware_info()
    settings = get_ffmpeg_encoding_settings()

    lines = [
        f"CPU: {hw['cpu_cores']} cores",
        f"RAM: {hw['ram_gb']} GB",
    ]

    if settings['hw_accel']:
        lines.append(f"GPU: {settings['gpu_name']} (hardware acceleration)")
    else:
        lines.append("GPU: None (CPU-only encoding)")

    lines.append(f"Video codec: {settings['video_codec']}")
    lines.append(f"Encoding preset: {settings['preset']}")

    return '\n'.join(lines)


if __name__ == '__main__':
    print("=== Cogitator Hardware Detection ===\n")
    print(get_encoding_summary())
    print(f"\nWhisper device: {get_whisper_device()}")
