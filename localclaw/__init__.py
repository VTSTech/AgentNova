"""
⚛️ localclaw - Compatibility shim for AgentNova

This package has been renamed to 'agentnova'.
Please update your imports to use 'agentnova' instead.

    Old: import localclaw
    New: import agentnova

    Old: from localclaw import Agent
    New: from agentnova import Agent

The CLI command has also changed:

    Old: localclaw run "prompt"
    New: agentnova run "prompt"

For more information, see: https://github.com/VTSTech/AgentNova
"""

import warnings

warnings.warn(
    "\n"
    "╔══════════════════════════════════════════════════════════════╗\n"
    "║  'localclaw' has been renamed to 'agentnova'                 ║\n"
    "║                                                              ║\n"
    "║  Please update your imports:                                 ║\n"
    "║      Old: import localclaw                                   ║\n"
    "║      New: import agentnova                                   ║\n"
    "║                                                              ║\n"
    "║  And your CLI commands:                                      ║\n"
    "║      Old: localclaw run \"prompt\"                             ║\n"
    "║      New: agentnova run \"prompt\"                             ║\n"
    "╚══════════════════════════════════════════════════════════════╝\n"
    "\n"
    "See: https://github.com/VTSTech/AgentNova",
    DeprecationWarning,
    stacklevel=2
)

# Re-export everything from agentnova
from agentnova import *

# Re-export version info
from agentnova import __version__, __author__, __author_email__, __url__, __website__

# Backward compatibility: also export LOCALCLAW_* env var aliases
import os
import agentnova.config as _config

# Create backward-compatible env var aliases
# LOCALCLAW_* -> AGENTNOVA_* (for users who haven't updated their env vars)
def _get_backend_compat():
    """Get backend, checking both new and old env vars."""
    return os.environ.get("AGENTNOVA_BACKEND") or os.environ.get("LOCALCLAW_BACKEND", "ollama")

def _get_model_compat():
    """Get model, checking both new and old env vars."""
    return os.environ.get("AGENTNOVA_MODEL") or os.environ.get("LOCALCLAW_MODEL", "qwen2.5-coder:0.5b-instruct-q4_k_m")

def _get_security_mode_compat():
    """Get security mode, checking both new and old env vars."""
    return os.environ.get("AGENTNOVA_SECURITY_MODE") or os.environ.get("LOCALCLAW_SECURITY_MODE", "permissive")

# Export compatibility functions
LOCALCLAW_BACKEND = _get_backend_compat()
LOCALCLAW_MODEL = _get_model_compat()
LOCALCLAW_SECURITY_MODE = _get_security_mode_compat()

__all__ = [
    # Re-exported from agentnova
    "Agent", "AgentRun", "StepResult",
    "Memory", "Tool", "ToolRegistry", "ToolParam",
    "OllamaClient", "Orchestrator", "AgentCard",
    "SkillLoader", "Skill", "SkillRegistry",
    "EnhancedOrchestrator", "EnhancedAgentCard",
    "ACPPlugin",
    "get_default_client",
    "get_available_models",
    "get_system_prompt",
    "get_tool_support",
    "model_discovery",
    "add_shared_args",
    "parse_shared_args",
    "SharedConfig",
    "AgentMode", "AgentState", "TaskPlan", "Step", "Action",
    "create_file_write_action", "create_file_delete_action",
    "create_mkdir_action", "create_shell_action",
    "format_status", "format_progress",
    "OLLAMA_BASE_URL",
    "BITNET_BASE_URL",
    "ACP_BASE_URL",
    "ACP_USER",
    "ACP_PASS",
    "DEFAULT_MODEL",
    "AGENTNOVA_BACKEND",
    # Backward compatibility
    "LOCALCLAW_BACKEND",
    "LOCALCLAW_MODEL",
    "LOCALCLAW_SECURITY_MODE",
    # Version info
    "__version__",
    "__author__",
    "__author_email__",
    "__url__",
    "__website__",
]

# Conditionally export BitNet
try:
    from agentnova import BitnetClient, KNOWN_MODELS
    __all__.extend(["BitnetClient", "KNOWN_MODELS"])
except ImportError:
    pass
