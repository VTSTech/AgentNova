"""
⚛️ AgentNova — Model Family Configuration
Configuration for different model families' prompting strategies.

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ModelFamilyConfig:
    """Configuration for a model family's behavior."""
    name: str
    tool_support: Literal["native", "react", "none"] = "react"

    # Prompting settings
    system_prompt_style: str = "default"  # default, react, minimal, xml
    think_tag: str | None = None  # e.g., <think/> for DeepSeek
    use_system_role: bool = True  # Some models prefer user role for system

    # Tool calling settings
    tool_format: str = "json"  # json, react, xml, markdown
    supports_streaming: bool = True
    supports_vision: bool = False

    # Generation defaults
    default_temperature: float = 0.1
    default_top_p: float = 0.9
    default_max_tokens: int = 8192

    # Special behaviors
    needs_empty_system: bool = False  # Some models break with empty system
    prefers_user_system: bool = False  # Put system prompt in first user message
    strip_think_tags: bool = False  # Remove <think/> tags from output

    # Stop sequences
    stop_sequences: list[str] = field(default_factory=list)

    def get_stop_sequences(self) -> list[str]:
        """Get stop sequences for this model family."""
        stops = list(self.stop_sequences)
        if self.tool_format == "react":
            stops.extend(["Observation:", "User:"])
        return stops


# Model family configurations
MODEL_CONFIGS: dict[str, ModelFamilyConfig] = {

    # Qwen family - Excellent tool support
    "qwen2.5": ModelFamilyConfig(
        name="qwen2.5",
        tool_support="native",
        system_prompt_style="default",
        tool_format="json",
        default_temperature=0.6,
    ),

    "qwen2": ModelFamilyConfig(
        name="qwen2",
        tool_support="react",
        system_prompt_style="react",
        tool_format="react",
        default_temperature=0.7,
    ),

    # Llama 3 family - Native tool support in 3.1+
    "llama3.3": ModelFamilyConfig(
        name="llama3.3",
        tool_support="native",
        system_prompt_style="default",
        tool_format="json",
        default_temperature=0.7,
    ),

    "llama3.2": ModelFamilyConfig(
        name="llama3.2",
        tool_support="native",
        system_prompt_style="default",
        tool_format="json",
        default_temperature=0.7,
        supports_vision=True,
    ),

    "llama3.1": ModelFamilyConfig(
        name="llama3.1",
        tool_support="native",
        system_prompt_style="default",
        tool_format="json",
        default_temperature=0.7,
    ),

    "llama3": ModelFamilyConfig(
        name="llama3",
        tool_support="react",
        system_prompt_style="react",
        tool_format="react",
        default_temperature=0.7,
    ),

    # Mistral family
    "mistral": ModelFamilyConfig(
        name="mistral",
        tool_support="native",
        system_prompt_style="default",
        tool_format="json",
        default_temperature=0.7,
    ),

    "mixtral": ModelFamilyConfig(
        name="mixtral",
        tool_support="native",
        system_prompt_style="default",
        tool_format="json",
        default_temperature=0.7,
    ),

    # Gemma family - Limited native support
    "gemma3": ModelFamilyConfig(
        name="gemma3",
        tool_support="react",
        system_prompt_style="minimal",
        tool_format="react",
        default_temperature=0.7,
        needs_empty_system=True,
        stop_sequences=["<end_of_turn>"],
    ),

    "gemma2": ModelFamilyConfig(
        name="gemma2",
        tool_support="react",
        system_prompt_style="minimal",
        tool_format="react",
        default_temperature=0.7,
        needs_empty_system=True,
        stop_sequences=["<end_of_turn>"],
    ),

    "gemma": ModelFamilyConfig(
        name="gemma",
        tool_support="react",
        system_prompt_style="minimal",
        tool_format="react",
        default_temperature=0.7,
        needs_empty_system=True,
    ),

    # Granite family - IBM models
    "granite": ModelFamilyConfig(
        name="granite",
        tool_support="native",
        system_prompt_style="default",
        tool_format="json",
        default_temperature=0.7,
    ),

    "granitemoe": ModelFamilyConfig(
        name="granitemoe",
        tool_support="native",
        system_prompt_style="default",
        tool_format="json",
        default_temperature=0.7,
    ),

    # Phi-3 family
    "phi3": ModelFamilyConfig(
        name="phi3",
        tool_support="native",
        system_prompt_style="default",
        tool_format="json",
        default_temperature=0.7,
    ),

    # CodeLlama
    "codellama": ModelFamilyConfig(
        name="codellama",
        tool_support="react",
        system_prompt_style="default",
        tool_format="react",
        default_temperature=0.3,  # Lower for code
    ),

    # Command-R - Excellent for tools
    "command-r": ModelFamilyConfig(
        name="command-r",
        tool_support="native",
        system_prompt_style="default",
        tool_format="json",
        default_temperature=0.7,
    ),

    # DeepSeek - Has <think/> tags
    "deepseek": ModelFamilyConfig(
        name="deepseek",
        tool_support="native",
        system_prompt_style="default",
        tool_format="json",
        think_tag="think",
        strip_think_tags=True,
        default_temperature=0.7,
    ),

    # Default configuration
    "default": ModelFamilyConfig(
        name="default",
        tool_support="react",
        system_prompt_style="react",
        tool_format="react",
        default_temperature=0.7,
    ),
}


def get_model_config(model_name: str) -> ModelFamilyConfig:
    """
    Get configuration for a model.

    Args:
        model_name: Name of the model (e.g., "qwen2.5:7b")

    Returns:
        ModelFamilyConfig for the model
    """
    name_lower = model_name.lower()

    # Check each family
    for family in MODEL_CONFIGS:
        if family in name_lower:
            return MODEL_CONFIGS[family]

    # Return default
    return MODEL_CONFIGS["default"]


def list_supported_families() -> list[str]:
    """List all supported model families."""
    return [k for k in MODEL_CONFIGS.keys() if k != "default"]
