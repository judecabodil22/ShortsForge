#!/usr/bin/env python3
"""
Cogitator Configuration Manager

Handles .env file reading/writing, environment variable access,
and keychain integration for API keys.
"""
import os
from typing import Optional

WORKSPACE = os.path.expanduser("~/Cogitator")
ENV_FILE = os.path.join(WORKSPACE, ".env")

# ─── .env File Management ────────────────────────────────────────────────────

def load_env(env_file: str = None) -> dict:
    """Load environment variables from .env file."""
    env_file = env_file or ENV_FILE
    env = {}
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k] = v.strip('"').strip("'")
    return env


def update_env_var(key: str, value: str, env_file: str = None) -> bool:
    """Update or add a key-value pair in .env file."""
    env_file = env_file or ENV_FILE
    env = load_env(env_file)
    env[key] = value

    try:
        with open(env_file, "w") as f:
            for k, v in env.items():
                f.write(f"{k}={v}\n")
        return True
    except OSError:
        return False


def delete_env_var(key: str, env_file: str = None) -> bool:
    """Remove a key from .env file."""
    env_file = env_file or ENV_FILE
    env = load_env(env_file)
    if key not in env:
        return False
    del env[key]

    try:
        with open(env_file, "w") as f:
            for k, v in env.items():
                f.write(f"{k}={v}\n")
        return True
    except OSError:
        return False


def get_all_env(env_file: str = None) -> dict:
    """Get all environment variables from .env file."""
    return load_env(env_file or ENV_FILE)
