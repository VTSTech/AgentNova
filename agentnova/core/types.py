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
    UNTESTED = "untested"  # Not yet tested - each model must be tested individually

    @classmethod
    def detect(cls, model_name: str, capabilities: dict | None = None) -> "ToolSupportLevel":
        """
        Auto-detect tool support level from model capabilities.

        IMPORTANT: Tool support is NOT determined by family name. It depends on
        the model's template, which can vary within the same family. Each model
        must be tested individually.

        Args:
            model_name: Name of the model (ignored, kept for API compatibility)
            capabilities: Optional capabilities dict from backend

        Returns:
            ToolSupportLevel (UNTESTED if capabilities not provided)
        """
        # Check capabilities if provided
        if capabilities:
            if capabilities.get("supports_function_calling"):
                return cls.NATIVE

        # Cannot determine without testing
        return cls.UNTESTED


class BackendType(Enum):
    """Supported backend types."""
    OLLAMA = "ollama"
    BITNET = "bitnet"
    OPENAI = "openai"  # Future support
    CUSTOM = "custom"


class ApiMode(Enum):
    """API mode for backend communication.
    
    - RESPONSES: OpenResponses-style API (Ollama native /api/chat)
    - COMPLETIONS: OpenAI Chat-Completions compatible API (/v1/chat/completions)
    
    Ollama supports both endpoints:
    - /api/chat - Native Ollama format (default)
    - /v1/chat/completions - OpenAI-compatible format
    """
    RESPONSES = "resp"      # OpenResponses / Ollama native format
    COMPLETIONS = "comp"    # OpenAI Chat-Completions compatible format


# Type aliases for clarity
ModelName = str
ToolName = str
MessageRole = Literal["system", "user", "assistant", "tool"]