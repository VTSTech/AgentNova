"""
⚛️ AgentNova R00 — Model Discovery

Dynamic model discovery for Ollama and BitNet backends.
Discovers available models at runtime instead of hardcoding.

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

from typing import Optional

from .config import AGENTNOVA_BACKEND, DEFAULT_MODEL

# Import clients based on backend
from .core.ollama_client import OllamaClient

# Try to import BitNet client
try:
    from .bitnet_client import BitnetClient, KNOWN_MODELS as BITNET_KNOWN_MODELS
    _BITNET_AVAILABLE = True
except ImportError:
    _BITNET_AVAILABLE = False
    BITNET_KNOWN_MODELS = []


def get_client(backend: Optional[str] = None):
    """
    Get a client for the specified or default backend.
    
    Parameters
    ----------
    backend : str, optional
        "ollama" or "bitnet". Defaults to AGENTNOVA_BACKEND from config.
    
    Returns
    -------
    OllamaClient or BitnetClient
    """
    backend = (backend or AGENTNOVA_BACKEND).lower()
    
    if backend == "bitnet":
        if not _BITNET_AVAILABLE:
            raise ImportError("BitNet backend requested but bitnet_client not available")
        from .config import BITNET_BASE_URL
        return BitnetClient(base_url=BITNET_BASE_URL)
    else:
        return OllamaClient()


def get_ollama_models(client: Optional[OllamaClient] = None) -> list[str]:
    """
    Get list of available models from Ollama.
    
    Parameters
    ----------
    client : OllamaClient, optional
        Client to use. Creates one if not provided.
    
    Returns
    -------
    list[str]
        List of model names available in Ollama
    """
    if client is None:
        client = OllamaClient()
    
    if not client.is_running():
        return []
    
    return client.list_models() or []


def get_bitnet_models(client=None) -> list[str]:
    """
    Get list of available models from BitNet backend.
    
    Parameters
    ----------
    client : BitnetClient, optional
        Client to use. Creates one if not provided.
    
    Returns
    -------
    list[str]
        List of model names available in BitNet
    """
    if not _BITNET_AVAILABLE:
        return []
    
    if client is None:
        from .config import BITNET_BASE_URL
        client = BitnetClient(base_url=BITNET_BASE_URL)
    
    if not client.is_running():
        return []
    
    return client.list_models() or []


def get_models(backend: Optional[str] = None, client=None) -> list[str]:
    """
    Get list of available models from the specified or default backend.
    
    This is the backend-agnostic version that respects AGENTNOVA_BACKEND.
    
    Parameters
    ----------
    backend : str, optional
        "ollama" or "bitnet". Defaults to AGENTNOVA_BACKEND from config.
    client : OllamaClient or BitnetClient, optional
        Client to use. Creates one if not provided.
    
    Returns
    -------
    list[str]
        List of model names available on the backend.
    
    Examples
    --------
    >>> # Use default backend from AGENTNOVA_BACKEND env var
    >>> models = get_models()
    
    >>> # Explicitly use Ollama
    >>> models = get_models(backend="ollama")
    
    >>> # Explicitly use BitNet
    >>> models = get_models(backend="bitnet")
    
    >>> # Pass client positionally (auto-detected)
    >>> models = get_models(my_client)
    """
    # Handle case where client is passed as first positional argument
    if backend is not None and not isinstance(backend, str):
        # backend is actually a client object
        client = backend
        backend = None
    
    backend = (backend or AGENTNOVA_BACKEND).lower()
    
    if backend == "bitnet":
        return get_bitnet_models(client)
    else:
        return get_ollama_models(client)


def pick_best_model(
    preferred: Optional[str] = None,
    fallback_order: Optional[list[str]] = None,
    client: Optional[OllamaClient] = None,
) -> Optional[str]:
    """
    Pick the best available model.
    
    Parameters
    ----------
    preferred : str, optional
        Preferred model name. If available and specified, returns this.
    fallback_order : list[str], optional
        Order of preference for fallback models.
        Default: prioritize small, fast models.
    client : OllamaClient, optional
        Client to use for discovery.
    
    Returns
    -------
    str or None
        Name of the best available model, or None if none available.
    
    Examples
    --------
    >>> model = pick_best_model()
    >>> model = pick_best_model(preferred="llama3.1:8b")
    >>> model = pick_best_model(fallback_order=["qwen2.5-coder:0.5b", "tinyllama"])
    """
    available = get_models(client=client)
    
    if not available:
        return None
    
    # If preferred model is available, use it
    if preferred and preferred in available:
        return preferred
    
    # Default fallback order: small fast models first
    if fallback_order is None:
        fallback_order = [
            # Best small models for tools
            "qwen2.5-coder:0.5b-instruct-q4_k_m",
            "qwen2.5-coder:0.5b",
            "qwen2.5:0.5b",
            "granite3.1-moe:1b",
            "llama3.2:1b",
            "gemma3:270m",
            # Common larger models
            "llama3.1:8b",
            "llama3.2:3b",
            "qwen2.5:7b",
            "mistral:7b",
            # Fallback to any tiny model
            "tinyllama:latest",
            "smollm:135m",
            "granite4:350m",
        ]
    
    # Find first available from fallback order
    for model in fallback_order:
        # Try exact match first
        if model in available:
            return model
        # Try partial match (e.g., "qwen2.5-coder" matches "qwen2.5-coder:0.5b")
        for avail in available:
            if avail.startswith(model.split(":")[0]):
                return avail
    
    # Last resort: return first available model
    if available:
        return available[0]
    
    return None


def pick_models_for_benchmark(
    max_models: int = 6,
    prefer_small: bool = True,
    client: Optional[OllamaClient] = None,
) -> list[str]:
    """
    Pick a set of models suitable for benchmarking.
    
    Parameters
    ----------
    max_models : int
        Maximum number of models to return
    prefer_small : bool
        If True, prefer small models (< 2B params)
    client : OllamaClient, optional
        Client to use for discovery
    
    Returns
    -------
    list[str]
        List of model names for benchmarking
    """
    available = get_models(client=client)
    
    if not available:
        return []
    
    # Categorize models by size
    small_indicators = ["0.5b", "270m", "135m", "350m", "0.6b", "1b", "tiny", "mini", "micro", "small"]
    medium_indicators = ["3b", "7b", "8b"]
    
    small_models = []
    medium_models = []
    large_models = []
    
    for model in available:
        model_lower = model.lower()
        if any(ind in model_lower for ind in small_indicators):
            small_models.append(model)
        elif any(ind in model_lower for ind in medium_indicators):
            medium_models.append(model)
        else:
            large_models.append(model)
    
    # Build result list
    result = []
    
    if prefer_small:
        # Add small models first (up to half of max)
        small_count = max(1, max_models // 2)
        result.extend(small_models[:small_count])
        # Fill with medium/large
        remaining = max_models - len(result)
        result.extend(medium_models[:remaining])
        remaining = max_models - len(result)
        result.extend(large_models[:remaining])
    else:
        # Mix of all sizes
        result.extend(small_models[:2])
        result.extend(medium_models[:2])
        result.extend(large_models[:max_models - len(result)])
    
    # If we still don't have enough, add any remaining
    if len(result) < max_models:
        for model in available:
            if model not in result:
                result.append(model)
                if len(result) >= max_models:
                    break
    
    return result[:max_models]


def model_exists(model: str, client: Optional[OllamaClient] = None) -> bool:
    """
    Check if a specific model is available.
    
    Parameters
    ----------
    model : str
        Model name to check
    client : OllamaClient, optional
        Client to use
    
    Returns
    -------
    bool
        True if model is available
    """
    available = get_models(client=client)
    
    # Exact match
    if model in available:
        return True
    
    # Partial match (e.g., "llama3" matches "llama3.1:8b")
    model_base = model.split(":")[0]
    for avail in available:
        if avail.startswith(model_base):
            return True
    
    return False


# Convenience exports
__all__ = [
    "get_client",
    "get_models",
    "get_available_models",  # Alias for get_models
    "get_ollama_models",
    "get_bitnet_models",
    "pick_best_model",
    "pick_models_for_benchmark",
    "model_exists",
]

# Alias for convenience
get_available_models = get_models
