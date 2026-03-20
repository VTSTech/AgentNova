"""
🦞 AgentNova R04 — Central Configuration

Single source of truth for Ollama and ACP server URLs.
Change these values once to update all tests and examples.

Written by VTSTech — https://www.vts-tech.org
"""

import os

# ═══════════════════════════════════════════════════════════════════════════════
# OLLAMA CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
# Uncomment ONE of the following to switch between local and remote Ollama:

# LOCAL OLLAMA:
OLLAMA_BASE_URL = "http://localhost:11434"

# REMOTE OLLAMA (cloudflare tunnel):
# OLLAMA_BASE_URL = "https://ooo.trycloudflare.com/"

# Override via environment variable (takes precedence if set)
_ollama_env = os.environ.get("OLLAMA_BASE_URL")
if _ollama_env:
    OLLAMA_BASE_URL = _ollama_env

# ═══════════════════════════════════════════════════════════════════════════════
# BITNET CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
# Default for local bitnet.cpp llama-server
BITNET_BASE_URL = "http://localhost:8765"

# Override via environment variable (useful for Colab/ngrok)
_bitnet_env = os.environ.get("BITNET_BASE_URL")
if _bitnet_env:
    BITNET_BASE_URL = _bitnet_env

# Remote BitNet tunnel (cloudflare)
_remote_bitnet = os.environ.get("BITNET_TUNNEL")
if _remote_bitnet:
    BITNET_BASE_URL = _remote_bitnet
    
# ═══════════════════════════════════════════════════════════════════════════════
# ACP CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
# Uncomment ONE of the following to switch between local and remote ACP:

# LOCAL ACP:
ACP_BASE_URL = "http://localhost:8766"

# REMOTE ACP (cloudflare tunnel):
# ACP_BASE_URL = "https://aaa.trycloudflare.com/"

# Override via environment variable (takes precedence if set)
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
# Can be overridden via environment variable
# BitNet default: bitnet-b1.58-2b-4t
# Ollama default: qwen2.5-coder:0.5b-instruct-q4_k_m
if AGENTNOVA_BACKEND == "bitnet":
    DEFAULT_MODEL = os.environ.get("AGENTNOVA_MODEL", "bitnet-b1.58-2b-4t")
else:
    DEFAULT_MODEL = os.environ.get("AGENTNOVA_MODEL", "qwen2.5-coder:0.5b-instruct-q4_k_m")


# ═══════════════════════════════════════════════════════════════════════════════
# TUNNEL URL REFERENCE (for documentation/comments)
# ═══════════════════════════════════════════════════════════════════════════════
# Current tunnels:
#   Ollama Colab: https://ooo.trycloudflare.com
#   ACP Tunnel:    https://aaa.trycloudflare.com
#
# To update: Just change OLLAMA_BASE_URL and ACP_BASE_URL above
# ═══════════════════════════════════════════════════════════════════════════════
