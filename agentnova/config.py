"""
⚛️ AgentNova — Central Configuration

Single source of truth for Ollama, BitNet, and ACP server URLs.
Change these values once to update all tests and examples.

Status: Alpha

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse


# ═══════════════════════════════════════════════════════════════════════════════
# OLLAMA CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
# Default for local Ollama
OLLAMA_BASE_URL = "http://localhost:11434"

# Override via environment variable (takes precedence if set)
_ollama_env = os.environ.get("OLLAMA_BASE_URL")
if _ollama_env:
    OLLAMA_BASE_URL = _ollama_env


# ═══════════════════════════════════════════════════════════════════════════════
# BITNET CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
# Default for local bitnet.cpp llama-server
BITNET_BASE_URL = "http://localhost:8765"

# Override via environment variable
_bitnet_env = os.environ.get("BITNET_BASE_URL")
if _bitnet_env:
    BITNET_BASE_URL = _bitnet_env

# Remote BitNet tunnel
_remote_bitnet = os.environ.get("BITNET_TUNNEL")
if _remote_bitnet:
    BITNET_BASE_URL = _remote_bitnet


# ═══════════════════════════════════════════════════════════════════════════════
# ACP CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
# Default for local ACP
ACP_BASE_URL = "http://localhost:8766"

# Override via environment variable
_acp_env = os.environ.get("ACP_BASE_URL")
if _acp_env:
    ACP_BASE_URL = _acp_env

# ACP Credentials
ACP_USER = os.environ.get("ACP_USER", "admin")
ACP_PASS = os.environ.get("ACP_PASS", "secret")


# ═══════════════════════════════════════════════════════════════════════════════
# BACKEND SELECTION
# ═══════════════════════════════════════════════════════════════════════════════
# Set AGENTNOVA_BACKEND to "bitnet" to use BitNet instead of Ollama
# Default: "ollama"
AGENTNOVA_BACKEND = os.environ.get("AGENTNOVA_BACKEND", "ollama").lower()

# Validate backend value
if AGENTNOVA_BACKEND not in ("ollama", "bitnet"):
    print(f"Warning: Invalid AGENTNOVA_BACKEND '{AGENTNOVA_BACKEND}', defaulting to 'ollama'")
    AGENTNOVA_BACKEND = "ollama"


# ═══════════════════════════════════════════════════════════════════════════════
# DEFAULT MODEL
# ═══════════════════════════════════════════════════════════════════════════════
# Default model for tests and examples
# BitNet default: bitnet-b1.58-2b-4t
# Ollama default: qwen2.5-coder:0.5b-instruct-q4_k_m
if AGENTNOVA_BACKEND == "bitnet":
    DEFAULT_MODEL = os.environ.get("AGENTNOVA_MODEL", "bitnet-b1.58-2b-4t")
else:
    DEFAULT_MODEL = os.environ.get("AGENTNOVA_MODEL", "qwen2.5-coder:0.5b-instruct-q4_k_m")


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════
MAX_STEPS = int(os.environ.get("AGENTNOVA_MAX_STEPS", "10"))
DEBUG = os.environ.get("AGENTNOVA_DEBUG", "").lower() in ("1", "true", "yes")
VERBOSE = os.environ.get("AGENTNOVA_VERBOSE", "").lower() in ("1", "true", "yes")

# Context window size (Ollama default is 2048)
# Set OLLAMA_NUM_CTX or AGENTNOVA_NUM_CTX to override
NUM_CTX = int(os.environ.get("OLLAMA_NUM_CTX") or os.environ.get("AGENTNOVA_NUM_CTX") or "0")
# 0 means use Ollama's default (2048)


@dataclass
class Config:
    """AgentNova configuration."""
    # Backend URLs
    ollama_base_url: str = field(default_factory=lambda: OLLAMA_BASE_URL)
    bitnet_base_url: str = field(default_factory=lambda: BITNET_BASE_URL)
    acp_base_url: str = field(default_factory=lambda: ACP_BASE_URL)

    # ACP Credentials
    acp_user: str = field(default_factory=lambda: ACP_USER)
    acp_pass: str = field(default_factory=lambda: ACP_PASS)

    # Backend selection
    backend: str = field(default_factory=lambda: AGENTNOVA_BACKEND)

    # Default model
    default_model: str = field(default_factory=lambda: DEFAULT_MODEL)

    # Agent settings
    max_steps: int = field(default_factory=lambda: MAX_STEPS)
    temperature: float = 0.1
    max_tokens: int = 8192
    num_ctx: int | None = field(default_factory=lambda: _get_num_ctx())

    # Memory settings
    memory_max_messages: int = 50
    memory_max_tokens: int = 4096

    # Security settings
    allow_shell: bool = True
    allow_network: bool = True
    allowed_paths: list[str] = field(default_factory=lambda: ["./output", "./data", "/tmp"])

    # Debug
    debug: bool = field(default_factory=lambda: DEBUG)
    verbose: bool = field(default_factory=lambda: VERBOSE)

    @property
    def ollama_host(self) -> str:
        """Extract host from Ollama URL."""
        parsed = urlparse(self.ollama_base_url)
        return parsed.hostname or "localhost"

    @property
    def ollama_port(self) -> int:
        """Extract port from Ollama URL."""
        parsed = urlparse(self.ollama_base_url)
        return parsed.port or 11434

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls()

    @classmethod
    def from_file(cls, path: str) -> "Config":
        """Load configuration from a JSON file."""
        import json

        try:
            with open(path, "r") as f:
                data = json.load(f)
            return cls(**data)
        except FileNotFoundError:
            return cls()
        except Exception as e:
            print(f"Warning: Error loading config file: {e}")
            return cls()


def _get_num_ctx() -> int | None:
    """Get num_ctx from environment (reads fresh each time)."""
    val = os.environ.get("OLLAMA_NUM_CTX") or os.environ.get("AGENTNOVA_NUM_CTX") or "0"
    num = int(val) if val else 0
    return num if num > 0 else None


# Global config instance
_config: Config | None = None


def get_config(reload: bool = False) -> Config:
    """Get the global configuration.
    
    Args:
        reload: If True, re-read from environment variables
    """
    global _config
    if _config is None or reload:
        _config = Config.from_env()
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration."""
    global _config
    _config = config
