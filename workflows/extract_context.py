#!/usr/bin/env python3
"""Extract context from existing transcript files."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from context_manager import (
    load_verified_context,
    save_verified_context,
    compute_and_save_implicit_relationships,
    merge_context_dicts,
)

TRANSCRIPTS_DIR = os.path.expanduser("~/ShortsForge/transcripts")
GAME_TITLE = "Shadow of the Tomb Raider"

def extract_from_transcript(json_path):
    """Load and extract text from transcript JSON."""
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    # Extract text from different transcript formats
    text = ""
    if isinstance(data, dict):
        if 'text' in data:
            text = data['text']
        elif 'transcription' in data:
            text = data['transcription']
        elif 'segments' in data:
            for seg in data.get('segments', []):
                if 'text' in seg:
                    text += seg['text'] + " "
    return text.strip()

def main():
    # Find all transcript files
    transcript_files = [f for f in os.listdir(TRANSCRIPTS_DIR) if f.endswith('.json')]
    
    if not transcript_files:
        print("No transcript files found")
        return
    
    print(f"Found {len(transcript_files)} transcript files")
    
    # Load existing context
    verified = load_verified_context(GAME_TITLE)
    existing_context = verified.get("context", {}) if verified else {}
    
    print(f"Existing context: {len(existing_context.get('characters', []))} chars, {len(existing_context.get('relationships', []))} rels")
    
    # Process each transcript
    for fname in transcript_files:
        fpath = os.path.join(TRANSCRIPTS_DIR, fname)
        print(f"\nProcessing: {fname}")
        
        text = extract_from_transcript(fpath)
        if not text:
            print(f"  No text extracted")
            continue
        
        print(f"  Extracted {len(text)} chars")
        
        # Extract context using the function from shortsforge
        from shortsforge import _cs_extract_context_from_transcript
        extracted = _cs_extract_context_from_transcript(text[:15000], GAME_TITLE)
        
        if extracted:
            # Merge with existing
            merged = merge_context_dicts(existing_context, extracted)
            
            # Save context
            save_verified_context(GAME_TITLE, merged)
            
            # Compute and save implicit relationships
            compute_and_save_implicit_relationships(GAME_TITLE, text)
            
            existing_context = merged
            print(f"  Merged: {len(merged.get('characters', []))} chars, {len(merged.get('relationships', []))} rels")
        else:
            print(f"  No context extracted")
    
    # Final summary
    verified = load_verified_context(GAME_TITLE)
    final_context = verified.get("context", {}) if verified else {}
    implicit = verified.get("implicit_relationships", []) if verified else []
    
    print(f"\n=== Final ===")
    print(f"Characters: {len(final_context.get('characters', []))}")
    print(f"Locations: {len(final_context.get('locations', []))}")
    print(f"Relationships: {len(final_context.get('relationships', []))}")
    print(f"Implicit relationships: {len(implicit)}")

if __name__ == "__main__":
    main()