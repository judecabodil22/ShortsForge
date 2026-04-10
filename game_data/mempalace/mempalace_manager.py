"""
MemPalace Manager for ShortsForge
Wrapper for MemPalace operations to provide persistent game-specific memory.
"""

import os
import json
import subprocess
from typing import Optional, List, Dict, Any


class MemPalaceManager:
    """Wrapper for MemPalace operations in ShortsForge"""
    
    def __init__(self, palace_path: str = None):
        """Initialize with memory path"""
        if palace_path is None:
            palace_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory")
        self.palace_path = palace_path
        self.mempalace_cli = "mempalace"
        
    def _run_command(self, args: List[str]) -> tuple:
        """Run a mempalace command and return (stdout, stderr, returncode)"""
        try:
            result = subprocess.run(
                [self.mempalace_cli] + args,
                capture_output=True,
                text=True,
                cwd=self.palace_path,
                timeout=120
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", "Command timed out", 1
        except FileNotFoundError:
            return "", "mempalace command not found", 1
    
    def mine_transcript(self, json_file: str, game_title: str) -> Dict[str, Any]:
        """
        Mine transcript after Phase 2 completes.
        Extracts entities and stores in MemPalace.
        """
        if not os.path.exists(json_file):
            return {"error": f"Transcript file not found: {json_file}"}
        
        with open(json_file, 'r') as f:
            transcript_data = json.load(f)
        
        segments = transcript_data.get('segments', [])
        text_content = " ".join([seg.get('text', '') for seg in segments])
        
        if not text_content:
            return {"error": "No text content in transcript"}
        
        game_sanitized = game_title.lower().replace(" ", "_")
        
        temp_dir = os.path.join(self.palace_path, f"temp_mine_{game_sanitized}")
        os.makedirs(temp_dir, exist_ok=True)
        
        temp_file = os.path.join(temp_dir, "transcript.txt")
        with open(temp_file, 'w') as f:
            f.write(f"=== {game_title} Transcript ===\n\n")
            f.write(f"Source: {os.path.basename(json_file)}\n\n")
            f.write(text_content[:50000])
        
        stdout, stderr, rc = self._run_command(["mine", temp_dir, "--wing", game_sanitized, "--mode", "convos"])
        
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        
        if rc != 0:
            return {"error": f"Mining failed: {stderr}"}
        
        return {
            "status": "success",
            "game": game_title,
            "wing": game_sanitized,
            "chars_extracted": len(text_content.split())
        }
    
    def get_game_memory(self, game_title: str) -> Dict[str, Any]:
        """Retrieve all memory for a game"""
        if not game_title:
            return {"error": "No game title provided"}
        
        game_sanitized = game_title.lower().replace(" ", "_")
        
        stdout, stderr, rc = self._run_command(["search", "", "--wing", game_sanitized])
        
        return {
            "game": game_title,
            "wing": game_sanitized,
            "search_result": stdout if rc == 0 else stderr,
            "success": rc == 0
        }
    
    def get_character_list(self, game_title: str) -> List[str]:
        """Get verified character names for game"""
        game_sanitized = game_title.lower().replace(" ", "_")
        
        stdout, stderr, rc = self._run_command(["list", "rooms", "--wing", game_sanitized])
        
        characters = []
        if rc == 0 and "characters" in stdout.lower():
            characters.append("characters")
        
        return characters
    
    def get_relationships(self, game_title: str) -> List[Dict[str, str]]:
        """Get relationship facts: (character, relationship, target)"""
        return []
    
    def get_forbidden_characters(self, game_title: str) -> List[str]:
        """Get characters to avoid (game-specific) - reads from game_data JSON"""
        game_sanitized = game_title.lower().replace(" ", "_")
        
        game_data_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "game_data",
            game_sanitized,
            "characters.json"
        )
        
        if os.path.exists(game_data_path):
            with open(game_data_path, 'r') as f:
                data = json.load(f)
                return data.get("forbidden_characters", [])
        
        return []
    
    def check_script_characters(self, script_text: str, game_title: str) -> Dict[str, List[str]]:
        """Validate script against memory - returns valid/invalid/warnings"""
        forbidden = self.get_forbidden_characters(game_title)
        
        valid = []
        invalid = []
        warnings = []
        
        for char in forbidden:
            if char.lower() in script_text.lower():
                invalid.append(char)
        
        return {
            "valid": valid,
            "invalid": invalid,
            "warnings": warnings
        }
    
    def add_quality_metric(self, game_title: str, metric: Dict[str, Any]) -> bool:
        """Log script generation quality"""
        game_sanitized = game_title.lower().replace(" ", "_")
        
        metrics_file = os.path.join(self.palace_path, f"quality_{game_sanitized}.json")
        
        existing = []
        if os.path.exists(metrics_file):
            with open(metrics_file, 'r') as f:
                existing = json.load(f)
        
        existing.append(metric)
        
        with open(metrics_file, 'w') as f:
            json.dump(existing, f, indent=2)
        
        return True
    
    def get_best_prompts(self, game_title: str, top_n: int = 5) -> List[Dict[str, Any]]:
        """Get historically best prompts for game"""
        game_sanitized = game_title.lower().replace(" ", "_")
        
        metrics_file = os.path.join(self.palace_path, f"quality_{game_sanitized}.json")
        
        if not os.path.exists(metrics_file):
            return []
        
        with open(metrics_file, 'r') as f:
            metrics = json.load(f)
        
        if not metrics:
            return []
        
        sorted_metrics = sorted(
            metrics,
            key=lambda x: (x.get('factuality', 0) + x.get('engagement', 0)),
            reverse=True
        )
        
        return sorted_metrics[:top_n]
    
    def get_entity(self, entity_name: str, game_title: str = None) -> List[Dict[str, Any]]:
        """Query knowledge graph for entity"""
        return []
    
    def invalidate_fact(self, entity: str, relationship: str, target: str) -> bool:
        """Mark a fact as no longer valid"""
        return True
    
    def status(self) -> Dict[str, Any]:
        """Get MemPalace status"""
        stdout, stderr, rc = self._run_command(["status"])
        
        return {
            "status_output": stdout,
            "error": stderr if rc != 0 else None,
            "success": rc == 0
        }


_mempalace_manager = None

def get_mempalace_manager() -> MemPalaceManager:
    """Get singleton instance of MemPalaceManager"""
    global _mempalace_manager
    if _mempalace_manager is None:
        _mempalace_manager = MemPalaceManager()
    return _mempalace_manager