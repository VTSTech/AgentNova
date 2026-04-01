"""
⚛️ AgentNova — Backends Module
Backend implementations for different inference engines.

Written by VTSTech — https://www.vts-tech.org
"""

from .base import BaseBackend
from .ollama import OllamaBackend
from .bitnet import BitNetBackend
from .llama_server import LlamaServerBackend
from ..config import AGENTNOVA_BACKEND, OLLAMA_BASE_URL, BITNET_BASE_URL, LLAMA_SERVER_BASE_URL
from ..core.types import ApiMode


# Backend registry
_BACKENDS: dict[str, type[BaseBackend]] = {
    "ollama": OllamaBackend,
    "llama-server": LlamaServerBackend,
    "llama_server": LlamaServerBackend,  # alias
}

# BitNet is now merged into LlamaServerBackend with bitnet_mode=True
# Kept as a separate class for backward compatibility (import path)
_BITNET_ALIASES = {"bitnet"}


def get_backend(name: str, timeout: int | None = None, api_mode: ApiMode | str | None = None, **kwargs) -> BaseBackend:
    """
    Get a backend instance by name.

    Args:
        name: Backend name ("ollama", "bitnet")
        timeout: Request timeout in seconds (default: 120)
        api_mode: API mode ("openre" for OpenResponses, "openai" for Chat-Completions)
        **kwargs: Backend-specific configuration

    Returns:
        Backend instance
    """
    from .base import BackendConfig
    
    name_lower = name.lower()

    # BitNet alias — route to LlamaServerBackend with bitnet_mode=True
    is_bitnet = name_lower in _BITNET_ALIASES
    if is_bitnet:
        name_lower = "llama-server"

    if name_lower not in _BACKENDS:
        raise ValueError(f"Unknown backend: {name}. Available: {list(_BACKENDS.keys())} + {_BITNET_ALIASES}")

    backend_class = _BACKENDS[name_lower]

    # Pass appropriate base_url if not provided
    if "base_url" not in kwargs:
        if name_lower == "ollama":
            kwargs["base_url"] = OLLAMA_BASE_URL
        elif name_lower == "llama-server" and not is_bitnet:
            kwargs["base_url"] = LLAMA_SERVER_BASE_URL
        elif is_bitnet:
            kwargs["base_url"] = BITNET_BASE_URL
            kwargs["bitnet_mode"] = True

    # Set bitnet_mode for alias
    if is_bitnet and "bitnet_mode" not in kwargs:
        kwargs["bitnet_mode"] = True

    # Create BackendConfig with timeout if specified
    if "config" not in kwargs and timeout is not None:
        kwargs["config"] = BackendConfig(timeout=timeout)

    # Pass api_mode for backends that support it
    if api_mode is not None and "api_mode" not in kwargs:
        kwargs["api_mode"] = api_mode

    return backend_class(**kwargs)


def get_default_backend(name: str | None = None, api_mode: ApiMode | str | None = None, timeout: int | None = None) -> BaseBackend:
    """
    Get a default backend instance.

    Uses AGENTNOVA_BACKEND env var if name not provided.

    Args:
        name: Backend name (optional, uses env var if not provided)
        api_mode: API mode ("openre" for OpenResponses/native, "openai" for Chat-Completions)
        timeout: Request timeout in seconds (default: 120)

    Returns:
        Backend instance with default configuration
    """
    backend_name = name or AGENTNOVA_BACKEND
    return get_backend(backend_name, api_mode=api_mode, timeout=timeout)


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
    "LlamaServerBackend",
    "get_backend",
    "get_default_backend",
    "register_backend",
    "ApiMode",
]