#!/usr/bin/env python3
"""
ShortsForge Name Normalization Utilities

Normalize character names and fix common misspellings.
Use this to post-process generated scripts.

Usage:
    import name_normalization
    normalized_script = name_normalization.normalize_script(
        script_text, 
        "tell_me_why"
    )
"""

import os
import json
import re

GAME_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "game_data")


def load_game_data(game_id: str) -> dict:
    """Load game-specific character data."""
    char_file = os.path.join(GAME_DATA_DIR, game_id, "characters.json")
    if os.path.exists(char_file):
        with open(char_file) as f:
            return json.load(f)
    return {}


def normalize_name(name: str, game_id: str) -> str:
    """
    Normalize a character name using the game's common misspellings map.
    
    Args:
        name: The name to normalize
        game_id: The game identifier
    
    Returns:
        The normalized name
    """
    game_data = load_game_data(game_id)
    common_misspellings = game_data.get("common_misspellings", {})
    
    name_clean = name.strip()
    if name_clean in common_misspellings:
        return common_misspellings[name_clean]
    
    return name


def normalize_script(script_text: str, game_id: str) -> str:
    """
    Normalize all names in a script.
    
    Args:
        script_text: The generated script text
        game_id: The game identifier
    
    Returns:
        The normalized script text
    """
    game_data = load_game_data(game_id)
    common_misspellings = game_data.get("common_misspellings", {})
    
    normalized = script_text
    for wrong, correct in common_misspellings.items():
        if wrong in normalized:
            print(f"Name Normalization: '{wrong}' -> '{correct}'")
            normalized = normalized.replace(wrong, correct)
    
    return normalized


def check_relationship_errors(script_text: str, game_id: str) -> list:
    """
    Check for relationship errors in a script.
    
    Args:
        script_text: The generated script text
        game_id: The game identifier
    
    Returns:
        List of error dictionaries with 'text', 'expected', 'found' keys
    """
    game_data = load_game_data(game_id)
    characters = game_data.get("characters", [])
    
    errors = []
    script_lower = script_text.lower()
    
    sibling_characters = ["allison", "tyler"]
    forbidden_terms = ["his friend", "her friend", "their friend", "his companion", 
                      "her companion", "their companion", "his buddy", "her buddy",
                      "his best friend", "her best friend"]
    
    for char in characters:
        if char.get("id") in sibling_characters:
            char_name = char.get("name", "")
            for term in forbidden_terms:
                if term in script_lower:
                    errors.append({
                        "character": char_name,
                        "found": term,
                        "expected": "sibling, brother, sister, or twin",
                        "severity": "critical"
                    })
    
    return errors


def check_forbidden_characters(script_text: str, game_id: str) -> list:
    """
    Check for forbidden characters (cross-game contamination).
    
    Args:
        script_text: The generated script text
        game_id: The game identifier
    
    Returns:
        List of forbidden character names found
    """
    game_data = load_game_data(game_id)
    forbidden = game_data.get("forbidden_characters", [])
    
    found = []
    for name in forbidden:
        if name.lower() in script_text.lower():
            found.append(name)
    
    return found


if __name__ == "__main__":
    print("ShortsForge Name Normalization Utility")
    print("=" * 40)
    
    test_script = """
    Allison was Tyler's friend and companion. They were raised by Mary Ann
    in the town of Delos Crossing. Max and Chloe would have never understood
    this relationship the way the twins do.
    """
    
    print("Original Script:")
    print(test_script)
    print("\n" + "-" * 40)
    
    normalized = normalize_script(test_script, "tell_me_why")
    print("Normalized Script:")
    print(normalized)
    print("\n" + "-" * 40)
    
    rel_errors = check_relationship_errors(test_script, "tell_me_why")
    print("Relationship Errors:")
    for err in rel_errors:
        print(f"  - {err}")
    print("\n" + "-" * 40)
    
    forbidden = check_forbidden_characters(test_script, "tell_me_why")
    print(f"Forbidden Characters Found: {forbidden}")