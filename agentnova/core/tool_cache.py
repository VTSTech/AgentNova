"""
⚛️ AgentNova — Tool Support Cache

Persistent cache for model tool support detection results.
Eliminates the need to re-test models on every run.

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

from .types import ToolSupportLevel


def get_cache_dir() -> Path:
    """Get the cache directory for AgentNova."""
    if os.name == "nt":
        # Windows: %LOCALAPPDATA%\agentnova\cache
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        cache_dir = Path(base) / "agentnova" / "cache"
    else:
        # Unix: ~/.cache/agentnova
        base = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
        cache_dir = Path(base) / "agentnova"
    
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_cache_file() -> Path:
    """Get the tool support cache file path."""
    return get_cache_dir() / "tool_support.json"


def load_tool_cache() -> dict:
    """
    Load cached tool support results.
    
    Returns:
        Dict mapping model names to their cached tool support info:
        {
            "qwen2.5:0.5b": {
                "support": "native",
                "tested_at": 1234567890.0,
                "family": "qwen2"
            },
            ...
        }
    """
    cache_file = get_cache_file()
    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                # Corrupted - not a dict
                if os.environ.get("AGENTNOVA_DEBUG"):
                    print(f"[ToolCache] Warning: Cache file corrupted (not a dict), ignoring")
                return {}
        except json.JSONDecodeError as e:
            if os.environ.get("AGENTNOVA_DEBUG"):
                print(f"[ToolCache] Warning: Cache file has invalid JSON: {e}")
            try:
                cache_file.unlink()
            except Exception:
                pass
            return {}
        except IOError as e:
            if os.environ.get("AGENTNOVA_DEBUG"):
                print(f"[ToolCache] Warning: Could not read cache file: {e}")
    return {}


def save_tool_cache(cache: dict) -> None:
    """
    Save tool support results to cache using atomic writes.
    
    Args:
        cache: Dict mapping model names to their tool support info
    """
    import tempfile
    
    cache_dir = get_cache_dir()
    cache_file = get_cache_file()
    
    try:
        # Write to a temp file first, then rename for atomicity
        fd, temp_path = tempfile.mkstemp(
            dir=str(cache_dir),
            prefix=".tool_support_",
            suffix=".json.tmp"
        )
        
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(cache, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            
            # Atomic rename (on POSIX systems)
            os.replace(temp_path, str(cache_file))
        except Exception:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
            
    except IOError as e:
        # Log the error but don't fail - cache is optional
        print(f"[ToolCache] Warning: Could not save tool cache: {e}", file=__import__('sys').stderr)


def get_cached_tool_support(model: str) -> Optional[ToolSupportLevel]:
    """
    Get cached tool support level for a model.
    
    Args:
        model: Model name (e.g., "qwen2.5:0.5b")
    
    Returns:
        ToolSupportLevel if cached, None if not in cache
    """
    cache = load_tool_cache()
    cached = cache.get(model)
    if cached:
        support_str = cached.get("support", "")
        try:
            return ToolSupportLevel(support_str)
        except ValueError:
            pass
    return None


def cache_tool_support(model: str, support: ToolSupportLevel, family: str = "", error: str = "") -> None:
    """
    Cache tool support result for a model.
    
    Args:
        model: Model name
        support: Detected tool support level
        family: Model family (for reference)
        error: Error message if detection failed
    """
    cache = load_tool_cache()
    cache[model] = {
        "support": support.value,
        "tested_at": time.time(),
        "family": family,
    }
    if error:
        cache[model]["error"] = error[:100]
    save_tool_cache(cache)


def clear_tool_cache() -> None:
    """Clear the tool support cache."""
    cache_file = get_cache_file()
    if cache_file.exists():
        try:
            cache_file.unlink()
        except Exception:
            pass


def list_cached_models() -> list[str]:
    """List all models with cached tool support."""
    cache = load_tool_cache()
    return list(cache.keys())


def get_cache_age(model: str) -> Optional[float]:
    """
    Get age of cached result in seconds.
    
    Returns:
        Age in seconds, or None if not cached
    """
    cache = load_tool_cache()
    cached = cache.get(model)
    if cached and "tested_at" in cached:
        return time.time() - cached["tested_at"]
    return None