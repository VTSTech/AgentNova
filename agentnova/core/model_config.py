"""
⚛️ AgentNova — Model Family Configuration
Configuration for different model families' prompting strategies.

NOTE: Tool support is NOT determined by family. Each model must be tested
individually via backend.test_tool_support() or use cached results from
the tool_cache module.

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelFamilyConfig:
    """Configuration for a model family's behavior.
    
    NOTE: Tool support is NOT determined by family. It depends on the model's
    template, which can vary within the same family. Use runtime detection via
    backend.test_tool_support() or check the cache via tool_cache module.
    """
    name: str

    # Prompting settings
    system_prompt_style: str = "default"  # default, react, minimal, xml
    think_tag: str | None = None  # e.g., <think/> for DeepSeek
    use_system_role: bool = True  # Some models prefer user role for system

    # Tool calling settings (format for ReAct prompts, NOT detection)
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
# These control prompting style, NOT tool support detection.
# Tool support is determined at runtime by testing each model.
MODEL_CONFIGS: dict[str, ModelFamilyConfig] = {

    # Qwen family
    "qwen2.5": ModelFamilyConfig(
        name="qwen2.5",
        system_prompt_style="default",
        tool_format="json",
        default_temperature=0.6,
    ),

    "qwen2": ModelFamilyConfig(
        name="qwen2",
        system_prompt_style="react",
        tool_format="react",
        default_temperature=0.7,
    ),

    "qwen3": ModelFamilyConfig(
        name="qwen3",
        system_prompt_style="default",
        tool_format="json",
        default_temperature=0.6,
    ),

    # Llama 3 family
    "llama3.3": ModelFamilyConfig(
        name="llama3.3",
        system_prompt_style="default",
        tool_format="json",
        default_temperature=0.7,
    ),

    "llama3.2": ModelFamilyConfig(
        name="llama3.2",
        system_prompt_style="default",
        tool_format="json",
        default_temperature=0.7,
        supports_vision=True,
    ),

    "llama3.1": ModelFamilyConfig(
        name="llama3.1",
        system_prompt_style="default",
        tool_format="json",
        default_temperature=0.7,
    ),

    "llama3": ModelFamilyConfig(
        name="llama3",
        system_prompt_style="react",
        tool_format="react",
        default_temperature=0.7,
    ),

    # Mistral family
    "mistral": ModelFamilyConfig(
        name="mistral",
        system_prompt_style="default",
        tool_format="json",
        default_temperature=0.7,
    ),

    "mixtral": ModelFamilyConfig(
        name="mixtral",
        system_prompt_style="default",
        tool_format="json",
        default_temperature=0.7,
    ),

    # Gemma family
    "gemma3": ModelFamilyConfig(
        name="gemma3",
        system_prompt_style="minimal",
        tool_format="react",
        default_temperature=0.7,
        needs_empty_system=True,
        stop_sequences=["<end_of_turn>"],
    ),

    "gemma2": ModelFamilyConfig(
        name="gemma2",
        system_prompt_style="minimal",
        tool_format="react",
        default_temperature=0.7,
        needs_empty_system=True,
        stop_sequences=["<end_of_turn>"],
    ),

    "gemma": ModelFamilyConfig(
        name="gemma",
        system_prompt_style="minimal",
        tool_format="react",
        default_temperature=0.7,
        needs_empty_system=True,
    ),

    # Granite family - IBM models
    "granite": ModelFamilyConfig(
        name="granite",
        system_prompt_style="default",
        tool_format="json",
        default_temperature=0.7,
    ),

    "granitemoe": ModelFamilyConfig(
        name="granitemoe",
        system_prompt_style="default",
        tool_format="json",
        default_temperature=0.7,
    ),

    # Phi-3 family
    "phi3": ModelFamilyConfig(
        name="phi3",
        system_prompt_style="default",
        tool_format="json",
        default_temperature=0.7,
    ),

    # CodeLlama
    "codellama": ModelFamilyConfig(
        name="codellama",
        system_prompt_style="default",
        tool_format="react",
        default_temperature=0.3,  # Lower for code
    ),

    # Command-R - Excellent for tools
    "command-r": ModelFamilyConfig(
        name="command-r",
        system_prompt_style="default",
        tool_format="json",
        default_temperature=0.7,
    ),

    # DeepSeek - Has <think/> tags
    "deepseek": ModelFamilyConfig(
        name="deepseek",
        system_prompt_style="default",
        tool_format="json",
        think_tag="think",
        strip_think_tags=True,
        default_temperature=0.7,
    ),

    # Default configuration
    "default": ModelFamilyConfig(
        name="default",
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
