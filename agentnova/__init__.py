"""
⚛️ AgentNova R01 - A minimal, hackable agentic framework for Ollama and BitNet

Written by VTSTech
https://www.vts-tech.org
https://github.com/VTSTech/AgentNova
"""

import os

from .core.agent import Agent, AgentRun, StepResult
from .core.memory import Memory
from .core.tools import Tool, ToolRegistry, ToolParam
from .core.ollama_client import OllamaClient
from .core.orchestrator import Orchestrator, AgentCard
from .skills import SkillLoader, Skill, SkillRegistry
from .acp_plugin import ACPPlugin, create_acp_agent
from .core.model_family_config import (
    ModelFamilyConfig, FAMILY_CONFIGS,
    get_family_config, get_stop_tokens, supports_tools,
    get_tool_format, get_preferred_temperature, should_use_few_shot,
    get_few_shot_style, has_known_issues, get_react_system_suffix,
    get_native_tool_hints,
)

# Config exports
from .config import (
    OLLAMA_BASE_URL,
    BITNET_BASE_URL,
    ACP_BASE_URL,
    ACP_USER,
    ACP_PASS,
    DEFAULT_MODEL,
    AGENTNOVA_BACKEND,
)

# R00: BitNet backend support
try:
    from .bitnet_client import BitnetClient, KNOWN_MODELS
    _BITNET_AVAILABLE = True
except ImportError:
    _BITNET_AVAILABLE = False
    BitnetClient = None
    KNOWN_MODELS = []


def get_default_client():
    """
    Get the default client based on AGENTNOVA_BACKEND setting.
    
    Returns
    -------
    OllamaClient or BitnetClient
        The appropriate client for the configured backend.
    
    Examples
    --------
    >>> # With AGENTNOVA_BACKEND=ollama (default)
    >>> client = get_default_client()  # Returns OllamaClient
    
    >>> # With AGENTNOVA_BACKEND=bitnet
    >>> client = get_default_client()  # Returns BitnetClient
    """
    if AGENTNOVA_BACKEND == "bitnet":
        if not _BITNET_AVAILABLE:
            raise ImportError("BitNet backend requested but bitnet_client not available")
        return BitnetClient()
    else:
        return OllamaClient()


def get_available_models(client=None):
    """
    Get list of available models from the configured backend.
    
    Parameters
    ----------
    client : OllamaClient or BitnetClient, optional
        Client to use. Creates one via get_default_client() if not provided.
    
    Returns
    -------
    list[str]
        List of model names available on the backend.
    """
    if client is None:
        client = get_default_client()
    
    if not client.is_running():
        return []
    
    return client.list_models() or []


def get_system_prompt(model: str, client=None, default_prompt: str = None):
    """
    Get the system prompt based on AGENTNOVA_USE_MF_SYS environment variable.
    
    If AGENTNOVA_USE_MF_SYS=1, returns the Modelfile's system prompt for the model.
    Otherwise returns the provided default_prompt.
    
    Parameters
    ----------
    model : str
        Model name to get system prompt for.
    client : OllamaClient or BitnetClient, optional
        Client to use. Creates one via get_default_client() if not provided.
    default_prompt : str, optional
        Default system prompt to use if AGENTNOVA_USE_MF_SYS is not set.
        If None and AGENTNOVA_USE_MF_SYS=1 but no Modelfile system prompt,
        returns None (agent will use its own default).
    
    Returns
    -------
    str or None
        The system prompt to use, or None.
    
    Examples
    --------
    >>> # Without AGENTNOVA_USE_MF_SYS set
    >>> sys_prompt = get_system_prompt("llama3.2", default_prompt="You are helpful.")
    >>> print(sys_prompt)  # "You are helpful."
    
    >>> # With AGENTNOVA_USE_MF_SYS=1
    >>> sys_prompt = get_system_prompt("qwen2.5-coder", default_prompt="You are helpful.")
    >>> print(sys_prompt)  # Modelfile's system prompt, e.g., "You are Qwen..."
    """
    use_mf_sys = os.environ.get("AGENTNOVA_USE_MF_SYS", "0") == "1"
    
    if use_mf_sys:
        if client is None:
            client = get_default_client()
        
        # Only OllamaClient has get_modelfile_system_prompt
        if hasattr(client, "get_modelfile_system_prompt"):
            mf_sys = client.get_modelfile_system_prompt(model)
            if mf_sys:
                print(f"  📜 Using Modelfile system prompt ({len(mf_sys)} chars)")
                return mf_sys
            else:
                print(f"  ⚠ No SYSTEM prompt in Modelfile for '{model}', using default")
                return default_prompt
    
    return default_prompt

# R00 Enhancements
from .core.orchestrator_enhanced import Orchestrator as EnhancedOrchestrator, AgentCard as EnhancedAgentCard

# Tool support detection
from .cli import get_tool_support

# Shared args for test scripts
from .shared_args import add_shared_args, parse_shared_args, SharedConfig

# R00: Agent Mode
from .agent_mode import (
    AgentMode, AgentState, TaskPlan, Step, Action,
    create_file_write_action, create_file_delete_action,
    create_mkdir_action, create_shell_action,
    format_status, format_progress,
)

__all__ = [
    # Core
    "Agent", "AgentRun", "StepResult",
    "Memory", "Tool", "ToolRegistry", "ToolParam",
    "OllamaClient", "Orchestrator", "AgentCard",
    # Skills
    "SkillLoader", "Skill", "SkillRegistry",
    # R00 Enhancements
    "EnhancedOrchestrator", "EnhancedAgentCard",
    "ACPPlugin",
    # R00: Backend-agnostic helpers
    "get_default_client",
    "get_available_models",
    "get_system_prompt",
    "get_tool_support",  # Tool support detection
    "model_discovery",
    "add_shared_args",   # Shared CLI args for test scripts
    "parse_shared_args",
    "SharedConfig",
    # R00: Agent Mode
    "AgentMode", "AgentState", "TaskPlan", "Step", "Action",
    "create_file_write_action", "create_file_delete_action",
    "create_mkdir_action", "create_shell_action",
    "format_status", "format_progress",
    # R01: Model Family Configuration
    "ModelFamilyConfig", "FAMILY_CONFIGS",
    "get_family_config", "get_stop_tokens", "supports_tools",
    "get_tool_format", "get_preferred_temperature", "should_use_few_shot",
    "get_few_shot_style", "has_known_issues", "get_react_system_suffix",
    "get_native_tool_hints",
    # Config exports
    "OLLAMA_BASE_URL",
    "BITNET_BASE_URL", 
    "ACP_BASE_URL",
    "ACP_USER",
    "ACP_PASS",
    "DEFAULT_MODEL",
    "AGENTNOVA_BACKEND",
]

# Conditionally export BitNet
if _BITNET_AVAILABLE:
    __all__.extend(["BitnetClient", "KNOWN_MODELS"])

__version__ = "0.1"
__author__ = "VTSTech"
__author_email__ = "contact@vts-tech.org"
__url__ = "https://github.com/VTSTech/AgentNova"
__website__ = "https://www.vts-tech.org"