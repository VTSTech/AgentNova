"""
⚛️ AgentNova R01 — Model Family Configuration

Family-specific configurations for prompts, stop tokens, formatting, and tool handling.
Each model family has unique characteristics that affect how we construct prompts
and handle responses.

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ModelFamilyConfig:
    """Configuration for a specific model family."""
    family: str
    start_tokens: dict = field(default_factory=dict)
    stop_tokens: list[str] = field(default_factory=list)
    tool_format: Literal["native", "xml", "json", "none"] = "native"
    tool_call_start: str = ""
    tool_call_end: str = ""
    supports_native_tools: bool = True
    system_prompt_style: Literal["separate", "first_user", "template"] = "separate"
    preferred_temperature: float = 0.7
    needs_think_directive: bool = False
    prefers_few_shot: bool = True
    few_shot_style: Literal["react", "native", "compact"] = "react"
    reasoning_hints: list[str] = field(default_factory=list)
    # Special behaviors
    has_schema_dump_issue: bool = False  # Some models dump tool schema as text
    truncate_json_args: bool = False  # Some models truncate JSON in ReAct


# ═══════════════════════════════════════════════════════════════════════════════
# FAMILY CONFIGURATIONS
# ═══════════════════════════════════════════════════════════════════════════════

FAMILY_CONFIGS: dict[str, ModelFamilyConfig] = {
    
    # GEMMA3 - Google's Gemma models (270m doesn't support tools)
    "gemma3": ModelFamilyConfig(
        family="gemma3",
        start_tokens={"user": "<start_of_turn>user", "assistant": "<start_of_turn>model"},
        stop_tokens=["<end_of_turn>"],
        tool_format="none",
        supports_native_tools=False,
        system_prompt_style="first_user",
        preferred_temperature=0.7,
        prefers_few_shot=False,
        few_shot_style="compact",
        reasoning_hints=["Think step by step", "Show your work"],
    ),
    
    # GRANITE - IBM's Granite 4.x models (native tool support with XML format)
    "granite": ModelFamilyConfig(
        family="granite",
        start_tokens={
            "system": "<|start_of_role|>system<|end_of_role|>",
            "user": "<|start_of_role|>user<|end_of_role|>",
            "assistant": "<|start_of_role|>assistant<|end_of_role|>",
        },
        stop_tokens=["<|end_of_text|>"],
        tool_format="xml",
        tool_call_start="<tool_call>\n",
        tool_call_end="\n</tool_call>",
        supports_native_tools=True,
        system_prompt_style="separate",
        preferred_temperature=0.7,
        prefers_few_shot=False,  # Native tools don't need few-shot
        few_shot_style="native",
    ),
    
    # GRANITEMOE - IBM's Granite MoE models (different tool format than granite4)
    "granitemoe": ModelFamilyConfig(
        family="granitemoe",
        start_tokens={
            "system": "<|start_of_role|>system<|end_of_role|>",
            "user": "<|start_of_role|>user<|end_of_role|>",
            "assistant": "<|start_of_role|>assistant<|end_of_role|>",
        },
        stop_tokens=["<|end_of_text|>"],
        tool_format="xml",
        tool_call_start="<|tool_call|>\n",  # granite3.1-moe uses <|tool_call|> not <tool_call>
        tool_call_end="",  # No closing tag for granite3.1-moe
        supports_native_tools=True,
        system_prompt_style="separate",
        preferred_temperature=0.6,
        prefers_few_shot=True,  # MoE benefits from examples
        few_shot_style="react",  # Use ReAct for better tool handling
        has_schema_dump_issue=True,  # Known to dump schema as text
        truncate_json_args=True,  # May truncate JSON in ReAct format
    ),
    
    # QWEN2 - Alibaba's Qwen 2.x models (ChatML format, native tools)
    "qwen2": ModelFamilyConfig(
        family="qwen2",
        start_tokens={
            "system": "<|im_start|>system",
            "user": "<|im_start|>user",
            "assistant": "<|im_start|>assistant",
        },
        stop_tokens=["<|im_end|>"],
        tool_format="xml",
        tool_call_start="<tool_call>\n",
        tool_call_end="\n</tool_call>",
        supports_native_tools=True,
        system_prompt_style="separate",
        preferred_temperature=0.7,
        prefers_few_shot=True,
        few_shot_style="react",  # ReAct works well for small qwen2
    ),
    
    # QWEN3 - Alibaba's Qwen 3.x models (ChatML + thinking directives)
    "qwen3": ModelFamilyConfig(
        family="qwen3",
        start_tokens={
            "system": "<|im_start|>system",
            "user": "<|im_start|>user",
            "assistant": "<|im_start|>assistant",
        },
        stop_tokens=["<|im_start|>", "<|im_end|>"],
        tool_format="xml",
        tool_call_start="<tool_call>\n",
        tool_call_end="\n</tool_call>",
        supports_native_tools=True,
        system_prompt_style="separate",
        preferred_temperature=0.6,  # Qwen3 recommends lower temp
        needs_think_directive=True,  # Supports /think /no_think
        prefers_few_shot=True,
        few_shot_style="react",
    ),
    
    # LLAMA - Meta's Llama models (varies by fine-tune)
    "llama": ModelFamilyConfig(
        family="llama",
        start_tokens={
            "system": "<|start_header_id|>system<|end_header_id|>\n\n",
            "user": "<|start_header_id|>user<|end_header_id|>\n\n",
            "assistant": "<|start_header_id|>assistant<|end_header_id|>\n\n",
        },
        stop_tokens=["<|eot_id|>", "<|end_of_text|>"],
        tool_format="native",
        tool_call_start="",  # Llama uses raw JSON without wrapper
        tool_call_end="",
        supports_native_tools=True,
        system_prompt_style="separate",
        preferred_temperature=0.7,
        prefers_few_shot=True,
        few_shot_style="react",
    ),
    
    # DOLPHIN - Dolphin fine-tunes (ChatML format, varies by base)
    "dolphin": ModelFamilyConfig(
        family="dolphin",
        start_tokens={
            "system": "<|im_start|>system",
            "user": "<|im_start|>user", 
            "assistant": "<|im_start|>assistant",
        },
        stop_tokens=["<|im_end|>", "<|im_start|>", "<|eot_id|>"],
        tool_format="native",  # Depends on base model
        supports_native_tools=True,
        system_prompt_style="separate",
        preferred_temperature=0.7,
        prefers_few_shot=True,
        few_shot_style="react",
        reasoning_hints=["Be direct and helpful", "Follow instructions precisely"],
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_family_config(family: str) -> ModelFamilyConfig:
    """
    Get configuration for a model family.
    
    Parameters
    ----------
    family : str
        Family name (e.g., "qwen2", "granite", "gemma3")
    
    Returns
    -------
    ModelFamilyConfig
        Configuration for the family, or default config if not found
    """
    family_lower = family.lower() if family else ""
    
    # Direct match
    if family_lower in FAMILY_CONFIGS:
        return FAMILY_CONFIGS[family_lower]
    
    # Partial match (e.g., "granitemoe" matches "granite")
    for key in FAMILY_CONFIGS:
        if key in family_lower or family_lower in key:
            return FAMILY_CONFIGS[key]
    
    # Default config
    return ModelFamilyConfig(family=family or "unknown")


def get_stop_tokens(family: str) -> list[str]:
    """Get stop tokens for a family."""
    return get_family_config(family).stop_tokens


def supports_tools(family: str) -> bool:
    """Check if family supports native tools."""
    return get_family_config(family).supports_native_tools


def get_tool_format(family: str) -> str:
    """Get tool format for a family."""
    return get_family_config(family).tool_format


def get_preferred_temperature(family: str) -> float:
    """Get preferred temperature for a family."""
    return get_family_config(family).preferred_temperature


def should_use_few_shot(family: str, model_size_hint: str = "") -> bool:
    """
    Determine if few-shot prompting should be used.
    
    Parameters
    ----------
    family : str
        Model family
    model_size_hint : str
        Size indicator from model name (e.g., "0.5b", "1b")
    
    Returns
    -------
    bool
        True if few-shot should be used
    """
    config = get_family_config(family)
    
    # If family explicitly prefers/dislikes few-shot, respect that
    if not config.prefers_few_shot:
        return False
    
    # For small models, always use few-shot
    small_indicators = ["270m", "350m", "500m", "0.5b", "0.6b", "1b"]
    if model_size_hint and any(ind in model_size_hint.lower() for ind in small_indicators):
        return True
    
    return config.prefers_few_shot


def get_few_shot_style(family: str) -> str:
    """Get preferred few-shot style for a family."""
    return get_family_config(family).few_shot_style


def has_known_issues(family: str) -> dict:
    """
    Get known issues for a family.
    
    Returns
    -------
    dict
        Dictionary of issue flags
    """
    config = get_family_config(family)
    return {
        "schema_dump": config.has_schema_dump_issue,
        "truncate_json": config.truncate_json_args,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# FAMILY-SPECIFIC PROMPT MODIFIERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_react_system_suffix(family: str) -> str:
    """
    Get family-specific ReAct format instructions.
    
    Different families may need slightly different formatting hints.
    """
    config = get_family_config(family)
    
    base_suffix = """You have access to tools. Use the following format:

Thought: <your reasoning>
Action: <tool_name>
Action Input: <JSON with arguments>
Observation: <result>
... (repeat as needed)
Thought: I have the answer.
Final Answer: <your response>"""
    
    # Family-specific modifications
    if family == "granitemoe":
        # granite3.1-moe has issues with JSON truncation
        return base_suffix + """

CRITICAL: Keep Action Input JSON SHORT. Use compact format:
{"expression": "2**10"}  <- GOOD
{"expression": "calculate 2 to the power of 10"}  <- BAD, too long"""
    
    elif family == "qwen2":
        # qwen2.5 works well with ReAct
        return base_suffix
    
    elif family == "qwen3":
        # qwen3 supports thinking mode
        return base_suffix
    
    elif family in ("gemma3", "dolphin"):
        return base_suffix
    
    return base_suffix


def get_native_tool_hints(family: str) -> str:
    """
    Get hints for models using native tool calling.
    
    These are added when the model uses native Ollama tool API
    but may need guidance on WHEN to call tools.
    """
    config = get_family_config(family)
    
    if not config.supports_native_tools:
        return ""
    
    hints = """TOOL USAGE RULES - YOU MUST CALL TOOLS:

1. MATH QUESTIONS: Always call calculator tool
   - "times/multiplied" → expression="A * B"
   - "power of" → expression="A ** B"
   - "square root" → expression="sqrt(N)"
   - "divided by" → expression="A / B"

2. SHELL/DATE: Use shell tool
   - "echo X" → command="echo X"
   - "current date" → command="date"

3. PYTHON: Use python_repl
   - Power is ** not ^

NEVER respond with empty content. ALWAYS call a tool when asked to compute."""
    
    # Family-specific additions
    if family == "granite":
        return hints + "\n\nFor tool calls, use XML format: <tool_calljson</tool_call"
    
    elif family == "qwen2":
        return hints  # qwen2.5 handles this well
    
    return hints


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "ModelFamilyConfig",
    "FAMILY_CONFIGS",
    "get_family_config",
    "get_stop_tokens",
    "supports_tools",
    "get_tool_format",
    "get_preferred_temperature",
    "should_use_few_shot",
    "get_few_shot_style",
    "has_known_issues",
    "get_react_system_suffix",
    "get_native_tool_hints",
]
