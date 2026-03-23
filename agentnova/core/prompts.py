"""
⚛️ AgentNova R02.5 — Prompts
Few-shot prompts, argument aliases, and platform constants for small model support.

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
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
        "path": "path",  # correct
        "filepath": "path", "file_path": "path", "filename": "path",
        "file": "path", "dest": "path", "destination": "path",
        "output_path": "path", "outputfile": "path", "location": "path",
        "content": "content",  # correct
        "data": "content", "text": "content", "body": "content",
        "output": "content", "string": "content", "value": "content",
        "write": "content", "output_data": "content",
    },
    "read_file": {
        "path": "path",  # correct
        "filepath": "path", "file_path": "path", "filename": "path",
        "file": "path", "input": "path", "source": "path", "location": "path",
    },
    "shell": {
        "command": "command",  # correct
        "cmd": "command", "exec": "command", "shell_cmd": "command",
        "bash": "command", "script": "command", "instruction": "command",
        "run": "command", "execute": "command", "op": "command",
        "text": "command", "input": "command", "arg": "command",
        "args": "command", "str": "command", "value": "command",
    },
    "web_search": {
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

Example 5 - Get current date:
Thought: User wants to know today's date
Action: python_repl
Action Input: {"code": "from datetime import datetime; print(datetime.now())"}

CRITICAL RULES:
1. Action line: just the tool name (no backticks, no quotes)
2. Action Input: valid JSON with correct argument names
3. Use "expression" for calculator, "command" for shell, "code" for python_repl
4. For shell echo: {"command": "echo Your Text Here"} - put the text after echo
5. MATH OPERATORS: * (multiply), ** (power), / (divide), + (add), - (subtract)
═══════════════════════════════════════════════════════════════
"""

# Compact version for models that need minimal prompting
FEW_SHOT_COMPACT = """
TOOL EXAMPLES (ReAct format):
Multiplication: calculator with {"expression": "15 * 8"}
Power: calculator with {"expression": "2 ** 10"}
Division: calculator with {"expression": "100 / 4"}
Shell: {"command": "echo Hello World"}
Python: {"code": "print(result)"}

MATH OPERATORS: * = multiply, ** = power, / = divide
Remember: Action = tool name, Action Input = JSON with correct arg names.
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

3. DATE/TIME: Use python_repl (works on all platforms)
   - "date/today" → python_repl(code="from datetime import datetime; print(datetime.now())")

4. PYTHON: Use python_repl with correct syntax
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
