"""
⚛️ AgentNova — Core Types
Enumeration types used throughout the framework.

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Literal


class StepResultType(Enum):
    """Result type of an agent step."""
    TOOL_CALL = auto()
    FINAL_ANSWER = auto()
    ERROR = auto()
    MAX_STEPS = auto()


class ToolSupportLevel(Enum):
    """Level of tool support provided by a model."""
    NATIVE = "native"      # Native function calling support
    REACT = "react"        # Text-based tool use via ReAct prompting
    NONE = "none"          # No tool support (pure reasoning)

    @classmethod
    def detect(cls, model_name: str, capabilities: dict | None = None) -> "ToolSupportLevel":
        """
        Auto-detect tool support level from model name and capabilities.

        Args:
            model_name: Name of the model (e.g., "qwen2.5:7b", "llama3.1:8b")
            capabilities: Optional capabilities dict from backend

        Returns:
            Detected ToolSupportLevel
        """
        name_lower = model_name.lower()

        # Check for known native tool support families
        native_families = [
            "qwen2.5", "qwen2", "llama3.1", "llama3.2", "llama3.3",
            "mistral", "mixtral", "codellama", "command-r",
            "gemma2", "gemma3", "granite", "granitemoe",
            "phi3", "phi-3", "firefunction", "claude",
        ]

        for family in native_families:
            if family in name_lower:
                return cls.NATIVE

        # Check capabilities if provided
        if capabilities:
            if capabilities.get("supports_function_calling"):
                return cls.NATIVE

        # Default to ReAct for unknown models (most can be prompted)
        return cls.REACT


class BackendType(Enum):
    """Supported backend types."""
    OLLAMA = "ollama"
    BITNET = "bitnet"
    OPENAI = "openai"  # Future support
    CUSTOM = "custom"


# Type aliases for clarity
ModelName = str
ToolName = str
MessageRole = Literal["system", "user", "assistant", "tool"]
