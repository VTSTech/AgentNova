"""
⚛️ AgentNova
A minimal, hackable agentic framework engineered for local inference.

Features:
  • Zero dependencies — uses Python stdlib only
  • Ollama + BitNet backends — switch with --backend flag
  • Three-tier tool support — native, ReAct, or none (auto-detected)
  • Small model optimized — fuzzy matching, argument normalization
  • Built-in security — path validation, command blocklist, SSRF protection

Status: Alpha

Written by VTSTech — https://www.vts-tech.org

Example Usage:
    from agentnova import Agent
    from agentnova.tools import make_builtin_registry

    tools = make_builtin_registry().subset(["calculator", "shell"])
    agent = Agent(model="qwen2.5:0.5b", tools=tools)

    result = agent.run("What is 15 * 8?")
    print(result.final_answer)
"""

__version__ = "0.3.0-alpha"
__author__ = "VTSTech"
__status__ = "Alpha"

from .agent import Agent
from .agent_mode import AgentMode, AgentState, TaskPlan
from .orchestrator import Orchestrator, AgentCard
from .core.models import StepResult, AgentRun, Tool, ToolParam
from .core.types import StepResultType, ToolSupportLevel, BackendType
from .tools import ToolRegistry, make_builtin_registry, BUILTIN_REGISTRY
from .backends import (
    BaseBackend, OllamaBackend, BitNetBackend,
    get_default_backend, get_backend,
)
from .config import Config, get_config
from .model_discovery import (
    get_models, get_available_models, pick_best_model,
    pick_models_for_benchmark, model_exists, get_client,
)
from .shared_args import SharedConfig, add_shared_args, parse_shared_args

# Optional ACP plugin (graceful import)
try:
    from .acp_plugin import ACPPlugin
except ImportError:
    ACPPlugin = None  # type: ignore

__all__ = [
    # Version
    "__version__",
    "__author__",
    "__status__",
    # Agent
    "Agent",
    "AgentMode",
    "AgentState",
    "TaskPlan",
    # Orchestrator
    "Orchestrator",
    "AgentCard",
    # Models
    "StepResult",
    "AgentRun",
    "Tool",
    "ToolParam",
    # Types
    "StepResultType",
    "ToolSupportLevel",
    "BackendType",
    # Tools
    "ToolRegistry",
    "make_builtin_registry",
    "BUILTIN_REGISTRY",
    # Backends
    "BaseBackend",
    "OllamaBackend",
    "BitNetBackend",
    "get_default_backend",
    "get_backend",
    # Config
    "Config",
    "get_config",
    # Model Discovery
    "get_models",
    "get_available_models",
    "pick_best_model",
    "pick_models_for_benchmark",
    "model_exists",
    "get_client",
    # Shared Args
    "SharedConfig",
    "add_shared_args",
    "parse_shared_args",
    # ACP Plugin
    "ACPPlugin",
]
