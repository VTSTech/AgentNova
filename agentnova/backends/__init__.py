"""
⚛️ AgentNova — Backends Module
Backend implementations for different inference engines.

Written by VTSTech — https://www.vts-tech.org
"""

from .base import BaseBackend
from .ollama import OllamaBackend
from .bitnet import BitNetBackend
from ..config import AGENTNOVA_BACKEND, OLLAMA_BASE_URL, BITNET_BASE_URL


# Backend registry
_BACKENDS: dict[str, type[BaseBackend]] = {
    "ollama": OllamaBackend,
    "bitnet": BitNetBackend,
}


def get_backend(name: str, **kwargs) -> BaseBackend:
    """
    Get a backend instance by name.

    Args:
        name: Backend name ("ollama", "bitnet")
        **kwargs: Backend-specific configuration

    Returns:
        Backend instance
    """
    name_lower = name.lower()

    if name_lower not in _BACKENDS:
        raise ValueError(f"Unknown backend: {name}. Available: {list(_BACKENDS.keys())}")

    backend_class = _BACKENDS[name_lower]

    # Pass appropriate base_url if not provided
    if "base_url" not in kwargs:
        if name_lower == "ollama":
            kwargs["base_url"] = OLLAMA_BASE_URL
        elif name_lower == "bitnet":
            kwargs["base_url"] = BITNET_BASE_URL

    return backend_class(**kwargs)


def get_default_backend(name: str | None = None) -> BaseBackend:
    """
    Get a default backend instance.

    Uses AGENTNOVA_BACKEND env var if name not provided.

    Args:
        name: Backend name (optional, uses env var if not provided)

    Returns:
        Backend instance with default configuration
    """
    backend_name = name or AGENTNOVA_BACKEND
    return get_backend(backend_name)


def register_backend(name: str, backend_class: type[BaseBackend]) -> None:
    """
    Register a custom backend.

    Args:
        name: Backend name
        backend_class: Backend class
    """
    _BACKENDS[name.lower()] = backend_class


__all__ = [
    "BaseBackend",
    "OllamaBackend",
    "BitNetBackend",
    "get_backend",
    "get_default_backend",
    "register_backend",
]
