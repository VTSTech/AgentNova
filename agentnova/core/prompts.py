"""
⚛️ AgentNova — Prompts
Few-shot prompts, argument aliases, and platform constants for small model support.

Written by VTSTech — https://www.vts-tech.org
"""

import platform as _platform

# ------------------------------------------------------------------ #
#  Platform detection                                                  #
# ------------------------------------------------------------------ #

_IS_WINDOWS = _platform.system() == "Windows"
PLATFORM_DIR_CMD = "cd" if _IS_WINDOWS else "pwd"
PLATFORM_LIST_CMD = "dir" if _IS_WINDOWS else "ls"

# ------------------------------------------------------------------ #
#  Tool-specific argument aliases (for small model hallucinations)    #
# ------------------------------------------------------------------ #
# Small models often hallucinate argument names. This mapping helps
# convert common hallucinations to the correct argument names.

TOOL_ARG_ALIASES = {
    "calculator": {
        # Common hallucinations for expression
        "a": "expression", "b": "expression", "x": "expression", "y": "expression",
        "num": "expression", "number": "expression", "value": "expression",
        "input": "expression", "formula": "expression", "math": "expression",
        "expr": "expression", "calc": "expression", "result": "expression",
        # Power operations - combine into expression
        "base": "_combine_power", "exponent": "_combine_power", "power": "_combine_power",
        "n": "_combine_power", "p": "_combine_power", "exp": "_combine_power",
    },
    "python_repl": {
        "code": "code",  # correct
        "script": "code", "cmd": "code", "command": "code",
        "python": "code", "py": "code", "exec": "code", "execute": "code",
        "expression": "code", "expr": "code", "statement": "code",
        "program": "code", "source": "code", "input": "code",
    },
    "write_file": {
        "path": "file_path",  # actual param name is file_path
        "filepath": "file_path", "file_path": "file_path", "filename": "file_path",
        "file": "file_path", "dest": "file_path", "destination": "file_path",
        "output_path": "file_path", "outputfile": "file_path", "location": "file_path",
        "content": "content",  # correct
        "data": "content", "text": "content", "body": "content",
        "output": "content", "string": "content", "value": "content",
        "write": "content", "output_data": "content",
    },
    "read_file": {
        "path": "file_path",  # actual param name is file_path
        "filepath": "file_path", "file_path": "file_path", "filename": "file_path",
        "file": "file_path", "input": "file_path", "source": "file_path", "location": "file_path",
    },
    "shell": {
        "command": "command",  # correct
        "cmd": "command", "exec": "command", "shell_cmd": "command",
        "bash": "command", "script": "command", "instruction": "command",
        "run": "command", "execute": "command", "op": "command",
        "text": "command", "input": "command", "arg": "command",
        "args": "command", "str": "command", "value": "command",
    },
    "web-search": {
        "query": "query",  # correct
        "search": "query", "q": "query", "term": "query", "search_query": "query",
        "keywords": "query", "text": "query", "input": "query",
    },
    "get_weather": {
        "city": "city",  # correct
        "location": "city", "place": "city", "town": "city",
        "where": "city", "area": "city", "region": "city",
    },
    "convert_currency": {
        "amount": "amount",  # correct
        "from_currency": "from_currency",  # correct
        "to_currency": "to_currency",  # correct
        # Common variations
        "from": "from_currency", "to": "to_currency",
        "source_currency": "from_currency", "target_currency": "to_currency",
        "money": "amount", "value": "amount", "price": "amount",
    },
}

# ------------------------------------------------------------------ #
#  Few-shot prompting suffix for small models                         #
# ------------------------------------------------------------------ #
# Added to system prompt when using models < 2B parameters

FEW_SHOT_SUFFIX = """

═══════════════════════════════════════════════════════════════
TOOL USAGE EXAMPLES - Follow this EXACT format:
═══════════════════════════════════════════════════════════════

Example 1 - Multiplication:
Thought: I need to multiply 15 times 8
Action: calculator
Action Input: {"expression": "15 * 8"}

Example 2 - Power:
Thought: I need to calculate 2 to the power of 20
Action: calculator
Action Input: {"expression": "2 ** 20"}

Example 3 - Echo text:
Thought: User wants to print some text
Action: shell
Action Input: {"command": "echo Hello World"}

Example 4 - Run Python code:
Thought: I need to compute something in Python
Action: python_repl
Action Input: {"code": "print(2 ** 10)"}

Example 5 - Write to file:
Thought: User wants to save text to a file
Action: write_file
Action Input: {"path": "/tmp/test.txt", "content": "Hello World"}

Example 6 - Read a file:
Thought: User wants to see file contents
Action: read_file
Action Input: {"path": "/tmp/test.txt"}

CRITICAL RULES:
1. Action line: just the tool name (no backticks, no quotes)
2. Action Input: valid JSON with correct argument names for THAT tool
3. ARGUMENT NAMES BY TOOL:
   - calculator: {"expression": "15 * 8"}
   - shell: {"command": "echo Hello"}
   - python_repl: {"code": "print(result)"}
   - write_file: {"path": "/path/file.txt", "content": "text to write"}
   - read_file: {"path": "/path/file.txt"}
4. MATH OPERATORS: * (multiply), ** (power), / (divide), + (add), - (subtract)
═══════════════════════════════════════════════════════════════
"""

# Compact version for models that need minimal prompting
FEW_SHOT_COMPACT = """
TOOL EXAMPLES (ReAct format):
Calculator: {"expression": "15 * 8"}
Shell: {"command": "echo Hello World"}
Python: {"code": "print(result)"}
Write file: {"path": "/tmp/file.txt", "content": "Hello"}
Read file: {"path": "/tmp/file.txt"}

ARGUMENT NAMES: expression (calculator), command (shell), code (python_repl), path+content (write_file), path (read_file)
MATH: * = multiply, ** = power, / = divide
"""

# Few-shot for native tool models - focuses on WHEN to call tools
# Platform-aware: use python_repl for date/time since shell commands vary
NATIVE_TOOL_HINTS = """
TOOL USAGE RULES - YOU MUST CALL TOOLS:

1. MATH QUESTIONS: Always call calculator tool
   - "times/multiplied" → calculator(expression="A * B")
   - "power of/to the power" → calculator(expression="A ** B")
   - "square root" → calculator(expression="sqrt(N)")
   - "divided by" → calculator(expression="A / B")
   - Parentheses matter: "(10 + 5) times 3" → calculator(expression="(10 + 5) * 3")

2. SHELL QUESTIONS: Always call shell tool
   - "echo" something → shell(command="echo YourText")

3. FILE OPERATIONS: Use write_file and read_file
   - Write to file → write_file(path="/path/file.txt", content="text to write")
   - Read a file → read_file(path="/path/file.txt")

4. DATE/TIME: Use python_repl (works on all platforms)
   - "date/today" → python_repl(code="from datetime import datetime; print(datetime.now())")

5. PYTHON: Use python_repl with correct syntax
   - Power is ** not ^ : python_repl(code="print(2 ** 20)")

NEVER respond with empty content. ALWAYS call a tool when asked to compute or execute.
"""

REACT_SYSTEM_SUFFIX = """
You have access to tools. Use the following format EXACTLY:

Thought: <your reasoning about what to do next>
Action: <tool_name>
Action Input: <JSON object with tool arguments>
Observation: <the result will appear here>
... (repeat Thought/Action/Action Input/Observation as needed)
Thought: I now have enough information.
Final Answer: <your final response to the user>

IMPORTANT: Action Input must be valid JSON. Only use tools listed below.
"""


# ------------------------------------------------------------------ #
#  Base System Prompts                                                 #
# ------------------------------------------------------------------ #

BASE_SYSTEM_PROMPT = "You are a helpful AI assistant."

NO_TOOLS_SYSTEM_PROMPT = """Answer questions directly. For math, show work then give answer.

Examples:
Q: What is 7 * 8?
A: 7 * 8 = 56

Q: What is 15 plus 27?
A: 15 + 27 = 42

Q: What is 17 divided by 4?
A: 17 / 4 = 4.25

Q: I have 10 apples. I give 3 to Bob and 2 to Alice. How many left?
A: 10 - 3 - 2 = 5

Keep answers brief. Show calculation first, then the final number."""


# ------------------------------------------------------------------ #
#  Prompt Construction Functions                                       #
# ------------------------------------------------------------------ #

def get_system_prompt(
    model_name: str,
    tool_support: str = "react",
    tools: list | None = None,
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
    from .model_family_config import (
        get_family_config, get_react_system_suffix, get_native_tool_hints,
        get_no_tools_system_prompt, should_use_few_shot, get_few_shot_style,
    )
    
    # Detect model family
    family = None
    name_lower = model_name.lower()
    families = [
        "qwen2.5", "qwen2", "qwen", "qwen3",
        "llama3.3", "llama3.2", "llama3.1", "llama3", "llama",
        "mistral", "mixtral",
        "gemma3", "gemma2", "gemma",
        "granitemoe", "granite",
        "phi3", "phi",
        "codellama",
        "command-r", "command",
        "deepseek",
        "dolphin",
    ]
    for f in families:
        if f in name_lower:
            family = f
            break
    
    # Get family config
    config = get_family_config(family) if family else None
    
    # Base prompt
    base_prompt = BASE_SYSTEM_PROMPT
    
    # No tools - use simple prompt
    if tool_support == "none":
        no_tools_prompt = get_no_tools_system_prompt(family or "")
        if no_tools_prompt:
            return no_tools_prompt
        return NO_TOOLS_SYSTEM_PROMPT
    
    # Native tool support: tools are passed via API, only add hints (not descriptions)
    if tool_support == "native":
        hints = get_native_tool_hints(family or "")
        if hints:
            return f"{base_prompt}\n\n{hints}"
        return base_prompt
    
    # ReAct mode: add tool descriptions + format instructions
    if tools and tool_support == "react":
        tool_prompt = get_tool_prompt(tools, tool_support, family)
        return f"{base_prompt}\n\n{tool_prompt}"
    
    return base_prompt


def get_tool_prompt(tools: list, tool_support: str = "react", family: str | None = None) -> str:
    """
    Generate tool description prompt.

    Args:
        tools: List of available tools
        tool_support: Tool support level
        family: Model family for family-specific hints

    Returns:
        Tool description string
    """
    from .model_family_config import (
        get_react_system_suffix, get_native_tool_hints,
        should_use_few_shot, get_few_shot_style,
    )
    
    if not tools:
        return ""

    lines = ["Available tools:"]

    for tool in tools:
        # Get tool name and description
        name = getattr(tool, 'name', str(tool))
        desc = getattr(tool, 'description', '')
        params = getattr(tool, 'params', [])
        
        params_str = ""
        if params:
            param_list = []
            for p in params:
                p_name = getattr(p, 'name', str(p))
                p_desc = getattr(p, 'description', '')
                p_req = getattr(p, 'required', True)
                req = "" if p_req else " (optional)"
                param_list.append(f"{p_name}{req}: {p_desc}")
            params_str = f" - Parameters: {', '.join(param_list)}"

        lines.append(f"  - {name}: {desc}{params_str}")

    # Add format instructions based on tool support
    if tool_support == "react":
        lines.append("")
        lines.append(get_react_system_suffix(family or ""))
        
        # CRITICAL: ALL ReAct models need few-shot examples
        # This was causing regression when family config had prefers_few_shot=False
        # ReAct models MUST have examples to learn the format
        style = get_few_shot_style(family or "")
        if style == "compact":
            lines.append(FEW_SHOT_COMPACT)
        else:
            lines.append(FEW_SHOT_SUFFIX)
    
    elif tool_support == "native":
        hints = get_native_tool_hints(family or "")
        if hints:
            lines.append("")
            lines.append(hints)

    return "\n".join(lines)


def get_react_prompt(
    question: str,
    tools: list | None = None,
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

    prompt = f"""{REACT_SYSTEM_SUFFIX}

{tool_desc}

Question: {question}
"""

    if scratchpad:
        prompt += f"\n{scratchpad}\n"

    return prompt


__all__ = [
    "PLATFORM_DIR_CMD",
    "PLATFORM_LIST_CMD",
    "TOOL_ARG_ALIASES",
    "FEW_SHOT_SUFFIX",
    "FEW_SHOT_COMPACT",
    "NATIVE_TOOL_HINTS",
    "REACT_SYSTEM_SUFFIX",
    "BASE_SYSTEM_PROMPT",
    "NO_TOOLS_SYSTEM_PROMPT",
    "get_system_prompt",
    "get_tool_prompt",
    "get_react_prompt",
]