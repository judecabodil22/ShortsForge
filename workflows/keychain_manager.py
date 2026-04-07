#!/usr/bin/env python3
"""
ShortsForge Keychain Manager
Handles secure storage and retrieval of API keys using system keychain.
"""
import os
import keyring

SERVICE_NAME = "ShortsForge"


def get_service_password(username):
    """Retrieve password from system keychain."""
    try:
        password = keyring.get_password(SERVICE_NAME, username)
        return password
    except Exception:
        return None


def set_service_password(username, password):
    """Store password in system keychain."""
    try:
        keyring.set_password(SERVICE_NAME, username, password)
        return True
    except Exception:
        return False


def delete_service_password(username):
    """Delete password from system keychain."""
    try:
        keyring.delete_password(SERVICE_NAME, username)
        return True
    except Exception:
        return False


def get_all_keys():
    """Get all stored API keys."""
    keys = {
        "gemini_api_key": get_service_password("gemini-api-key"),
        "telegram_bot_token": get_service_password("telegram-bot-token"),
        "telegram_chat_id": get_service_password("telegram-chat-id"),
    }
    return keys


def set_gemini_keys(keys_list):
    """Store multiple Gemini API keys."""
    for i, key in enumerate(keys_list):
        username = f"gemini-key-{i+1}"
        set_service_password(username, key)


def get_gemini_keys():
    """Retrieve all Gemini API keys.
    
    Tries keychain first, then falls back to .env file for systemd/headless environments.
    """
    keys = []
    i = 1
    while True:
        username = f"gemini-key-{i}"
        key = get_service_password(username)
        if key is None:
            break
        keys.append(key)
        i += 1
    
    # Fallback: if keychain is empty, try reading from .env
    if not keys:
        try:
            env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GEMINI_API_KEY="):
                            key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if key:
                                keys.append(key)
        except Exception:
            pass
    
    return keys


def get_groq_keys():
    """Retrieve all Groq API keys."""
    keys = []
    i = 1
    while True:
        username = f"groq-key-{i}"
        key = get_service_password(username)
        if key is None:
            break
        keys.append(key)
        i += 1
    return keys


def has_keychain_access():
    """Check if keychain is accessible."""
    try:
        keyring.get_password(SERVICE_NAME, "test")
        return True
    except Exception:
        return False


def migrate_from_file(filepath, key_prefix):
    """Migrate keys from a file to keychain (one key per line)."""
    if not os.path.exists(filepath):
        return False
    
    try:
        with open(filepath, "r") as f:
            keys = [line.strip() for line in f if line.strip()]
        
        if not keys:
            return False
        
        for i, key in enumerate(keys):
            username = f"{key_prefix}-{i+1}"
            set_service_password(username, key)
        
        return True
    except Exception:
        return False
