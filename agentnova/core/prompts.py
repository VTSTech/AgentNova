"""
⚛️ AgentNova — Prompt Templates
Model-specific system prompts and tool prompts.

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

from typing import Optional
from .models import Tool


# Base system prompt
BASE_SYSTEM_PROMPT = """You are AgentNova, a helpful AI assistant with access to tools.

When you need to use a tool, clearly indicate this in your response using one of these formats:

1. ReAct Format:
   Thought: [your reasoning]
   Action: [tool_name]
   Action Input: {"arg1": "value1"}

2. JSON Format:
   {"name": "tool_name", "arguments": {"arg1": "value1"}}

After receiving the tool result, continue reasoning until you can provide a final answer.
When you have the final answer, say:
Final Answer: [your answer]

Be concise but thorough. Use tools when they would help answer the question accurately."""


# ReAct-specific prompt
REACT_SYSTEM_PROMPT = """You are AgentNova, an AI assistant that uses the ReAct (Reasoning and Acting) framework.

Follow this pattern:
1. Thought: Think about what you need to do
2. Action: Choose a tool to use
3. Action Input: Provide arguments as JSON
4. Observation: You'll receive the tool result
5. Repeat until you have the answer
6. Final Answer: Provide your answer

Available tools will be listed separately.

Always format tool calls EXACTLY like this:
Action: tool_name
Action Input: {"arg": "value"}

Do not deviate from this format."""


# Model family specific prompts
MODEL_FAMILY_PROMPTS = {
    "qwen2": """You are AgentNova, a helpful AI assistant.
When using tools, use this exact format:
Action: tool_name
Action Input: {"param": "value"}

Think step by step and use tools when needed.""",

    "qwen2.5": """You are AgentNova, a helpful AI assistant.
Use the available tools when needed to help answer questions.
Format tool calls as:
Action: tool_name
Action Input: {"param": "value"}""",

    "llama3": """You are AgentNova, a helpful AI assistant.
Use the provided tools when they would help answer the question.
After using tools, provide a clear final answer.""",

    "llama3.1": """You are AgentNova, a helpful AI assistant with tool capabilities.
You have access to tools that can help answer questions.
Use tools when appropriate and provide clear final answers.""",

    "llama3.2": """You are AgentNova, a helpful AI assistant.
Think step by step. Use tools when they would help.
Provide clear final answers.""",

    "mistral": """You are AgentNova, a helpful assistant.
Use tools when needed. Be concise and accurate.""",

    "gemma": """You are AgentNova, a helpful AI assistant.
Use available tools to help answer questions accurately.""",

    "gemma2": """You are AgentNova, a helpful AI assistant.
Think carefully and use tools when they would help answer the question.""",

    "gemma3": """You are AgentNova, a helpful AI assistant.
Use tools when appropriate to provide accurate answers.""",

    "granite": """You are AgentNova, a helpful AI assistant.
Use the available tools when needed to complete tasks accurately.""",

    "granitemoe": """You are AgentNova, a helpful AI assistant.
Use tools efficiently to accomplish tasks.""",

    "phi3": """You are AgentNova, a helpful assistant.
Use tools when needed. Think step by step.""",

    "codellama": """You are AgentNova, a helpful coding assistant.
Use tools to execute code and retrieve information when needed.""",

    "command-r": """You are AgentNova, a helpful assistant.
Use the available tools to help answer questions and complete tasks.""",

    "default": BASE_SYSTEM_PROMPT,
}


def get_system_prompt(
    model_name: str,
    tool_support: str = "react",
    tools: list[Tool] | None = None,
) -> str:
    """
    Get the appropriate system prompt for a model.

    Args:
        model_name: Name of the model
        tool_support: Tool support level ("native", "react", "none")
        tools: List of available tools

    Returns:
        System prompt string
    """
    # Detect model family
    family = _detect_model_family(model_name)

    # Get base prompt for family
    base_prompt = MODEL_FAMILY_PROMPTS.get(family, MODEL_FAMILY_PROMPTS["default"])

    # Add tool information if tools available
    if tools and tool_support != "none":
        tool_prompt = get_tool_prompt(tools, tool_support)
        return f"{base_prompt}\n\n{tool_prompt}"

    return base_prompt


def get_tool_prompt(tools: list[Tool], tool_support: str = "react") -> str:
    """
    Generate tool description prompt.

    Args:
        tools: List of available tools
        tool_support: Tool support level

    Returns:
        Tool description string
    """
    if not tools:
        return ""

    lines = ["Available tools:"]

    for tool in tools:
        params_str = ""
        if tool.params:
            params = []
            for p in tool.params:
                req = "" if p.required else " (optional)"
                params.append(f"{p.name}{req}: {p.type}")
            params_str = f" - Parameters: {', '.join(params)}"

        lines.append(f"  - {tool.name}: {tool.description}{params_str}")

    if tool_support == "react":
        lines.append("")
        lines.append("Use this format for tool calls:")
        lines.append('Action: tool_name')
        lines.append('Action Input: {"param": "value"}')

    return "\n".join(lines)


def get_react_prompt(
    question: str,
    tools: list[Tool] | None = None,
    scratchpad: str = "",
) -> str:
    """
    Generate a ReAct prompt for the given question.

    Args:
        question: User question
        tools: Available tools
        scratchpad: Previous reasoning/observations

    Returns:
        Complete ReAct prompt
    """
    tool_desc = get_tool_prompt(tools or [], "react")

    prompt = f"""{REACT_SYSTEM_PROMPT}

{tool_desc}

Question: {question}
"""

    if scratchpad:
        prompt += f"\n{scratchpad}\n"

    return prompt


def _detect_model_family(model_name: str) -> str:
    """Detect model family from model name."""
    name_lower = model_name.lower()

    # Check each family
    families = [
        "qwen2.5", "qwen2", "qwen",
        "llama3.3", "llama3.2", "llama3.1", "llama3", "llama",
        "mistral", "mixtral",
        "gemma3", "gemma2", "gemma",
        "granitemoe", "granite",
        "phi-3", "phi3", "phi",
        "codellama", "code-llama",
        "command-r", "command",
        "deepseek",
    ]

    for family in families:
        if family in name_lower:
            # Normalize family name
            if family.startswith("phi"):
                return "phi3"
            if family.startswith("code"):
                return "codellama"
            return family

    return "default"
