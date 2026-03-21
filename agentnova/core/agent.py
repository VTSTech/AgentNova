"""
⚛️ AgentNova R00 — Agent
Core ReAct agent that drives the think → act → observe loop.

Supports:
  • Native Ollama tool-calling (for models that expose it)
  • Text-based ReAct fallback (for models without native tool support)
  • Streaming output
  • Hooks for custom logging / UI
  • Enhanced argument normalization for small models
  • Few-shot prompting for improved accuracy
  • Pre-call argument synthesis

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Literal

from .ollama_client import OllamaClient
from .memory import Memory
from .tools import ToolRegistry

# Import config for backend selection (avoids circular import)
import os as _os
_AGENTNOVA_BACKEND = _os.environ.get("AGENTNOVA_BACKEND", "ollama").lower()

# Try to import BitNet client if needed
if _AGENTNOVA_BACKEND == "bitnet":
    try:
        from ..bitnet_client import BitnetClient
        _BITNET_AVAILABLE = True
    except ImportError:
        _BITNET_AVAILABLE = False
else:
    _BITNET_AVAILABLE = False


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

Example 3 - Get current date:
Thought: User wants to know today's date
Action: shell
Action Input: {"command": "date"}

Example 4 - Echo text:
Thought: User wants to print some text
Action: shell
Action Input: {"command": "echo Hello World"}

Example 5 - Run Python code:
Thought: I need to compute something in Python
Action: python_repl
Action Input: {"code": "print(2 ** 10)"}

Example 6 - Write to file:
Thought: Save the result to a file
Action: write_file
Action Input: {"path": "/tmp/result.txt", "content": "Hello World"}

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
Shell: {"command": "date"}
Python: {"code": "print(result)"}

MATH OPERATORS: * = multiply, ** = power, / = divide
Remember: Action = tool name, Action Input = JSON with correct arg names.
"""

# Few-shot for native tool models - focuses on WHEN to call tools
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
   - "current directory/pwd" → shell(command="pwd")
   - "date/today" → shell(command="date")

3. PYTHON: Use python_repl with correct syntax
   - Power is ** not ^ : python_repl(code="print(2 ** 20)")

NEVER respond with empty content. ALWAYS call a tool when asked to compute or execute.
"""


# ------------------------------------------------------------------ #
#  Shared tiny helpers                                                 #
# ------------------------------------------------------------------ #

def _strip_tool_prefix(result: str) -> str:
    """Strip the 'tool_name → ' prefix added to _successful_results entries."""
    return result.split("→")[-1].strip() if "→" in result else result.strip()


def _extract_calc_expression(prompt: str) -> str | None:
    """
    Extract a calculator expression from a natural language prompt.
    Returns a Python math expression or None if no pattern matches.
    
    Handles:
    - "What is X times Y?" → "X * Y"
    - "What is X divided by Y?" → "X / Y"
    - "What is X to the power of Y?" → "X ** Y"
    - "What is the square root of X?" → "sqrt(X)"
    - "What is (X + Y) times Z?" → "(X + Y) * Z"
    """
    import re
    q = prompt.strip()
    q_lower = q.lower()
    
    # Pattern: "square root of X" or "sqrt of X"
    sqrt_match = re.search(r'square\s*root\s*of\s*(\d+(?:\.\d+)?)', q_lower)
    if not sqrt_match:
        sqrt_match = re.search(r'sqrt\s*of\s*(\d+(?:\.\d+)?)', q_lower)
    if sqrt_match:
        return f"sqrt({sqrt_match.group(1)})"
    
    # Pattern: "X to the power of Y" or "X raised to Y"
    power_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:to\s*the\s*power\s*of|raised\s*to|to\s*the\s*\d*(?:th|st|nd|rd)?\s*power|\*\*|\^)\s*(\d+(?:\.\d+)?)', q_lower)
    if power_match:
        return f"{power_match.group(1)} ** {power_match.group(2)}"
    
    # Pattern: "(X + Y) times Z" - complex expression with parentheses
    complex_times = re.search(r'\(([^)]+)\)\s*(?:times|multiplied\s*by|\*)\s*(\d+(?:\.\d+)?)', q_lower)
    if complex_times:
        inner = complex_times.group(1).replace('plus', '+').replace('minus', '-').replace(' ', ' ')
        # Clean up the inner expression
        inner = re.sub(r'\s+', '', inner)
        return f"({inner}) * {complex_times.group(2)}"
    
    # Pattern: "X times Y" or "X multiplied by Y"
    times_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:times|multiplied\s*by|\*)\s*(\d+(?:\.\d+)?)', q_lower)
    if times_match:
        return f"{times_match.group(1)} * {times_match.group(2)}"
    
    # Pattern: "X divided by Y"
    div_match = re.search(r'(\d+(?:\.\d+)?)\s*divided\s*by\s*(\d+(?:\.\d+)?)', q_lower)
    if div_match:
        return f"{div_match.group(1)} / {div_match.group(2)}"
    
    # Pattern: "X plus Y" or "X minus Y"
    plus_match = re.search(r'(\d+(?:\.\d+)?)\s*plus\s*(\d+(?:\.\d+)?)', q_lower)
    if plus_match:
        return f"{plus_match.group(1)} + {plus_match.group(2)}"
    
    minus_match = re.search(r'(\d+(?:\.\d+)?)\s*minus\s*(\d+(?:\.\d+)?)', q_lower)
    if minus_match:
        return f"{minus_match.group(1)} - {minus_match.group(2)}"
    
    return None


def _extract_echo_text(prompt: str) -> str | None:
    """
    Extract text to echo from a prompt like "Echo the text 'Hello'" or "Print Hello World".
    Returns the text to echo or None.
    """
    import re
    q = prompt.strip()
    
    # Pattern: echo 'text' or echo "text" or echo text
    quoted_match = re.search(r"echo\s*['\"]([^'\"]+)['\"]", q, re.IGNORECASE)
    if quoted_match:
        return quoted_match.group(1)
    
    # Pattern: "echo the text 'X'" or "echo text 'X'"
    text_match = re.search(r"echo\s*(?:the\s*)?text\s*['\"]([^'\"]+)['\"]", q, re.IGNORECASE)
    if text_match:
        return text_match.group(1)
    
    # Pattern: "print 'X'" or "print X"
    print_match = re.search(r"print\s*['\"]?([^'\"]+)['\"]?", q, re.IGNORECASE)
    if print_match:
        return print_match.group(1).strip()
    
    # Pattern: "echo X" at end of prompt
    echo_match = re.search(r"echo\s+['\"]?([^'\"]+)['\"]?$", q, re.IGNORECASE)
    if echo_match:
        text = echo_match.group(1).strip()
        # Don't return if it looks like a command flag
        if not text.startswith('-'):
            return text
    
    return None


# ------------------------------------------------------------------ #
#  Argument key normalizer                                             #
# ------------------------------------------------------------------ #

def _normalize_args(args: dict, tool, tool_name: str = None) -> dict:
    """
    Small models often hallucinate argument keys. This function normalizes
    them using multiple strategies:
    
    1. Tool-specific alias mapping (TOOL_ARG_ALIASES)
    2. Exact match to real params
    3. Prefix/substring matching
    4. Type coercion (string -> int/float)
    
    Also handles special cases like power operations where multiple args
    (base, exponent) need to be combined into a single expression.
    """
    # Guard: ensure args is a dict
    if not isinstance(args, dict):
        if args is None:
            return {}
        # If it's a string, try to parse as JSON or wrap it
        if isinstance(args, str):
            # For simple string args, wrap in a generic 'input' key
            return {"input": args}
        return {}
    
    if tool is None:
        return args

    real_params = [p for p in tool.params]
    if not real_params:
        return args

    param_map = {p.name: p for p in real_params}
    normalized = {}
    power_parts = {}  # For combining base/exponent into expression
    
    # Get tool-specific aliases
    tool_aliases = TOOL_ARG_ALIASES.get(tool_name, {}) if tool_name else {}
    
    for key, val in args.items():
        key_lower = key.lower().replace("-", "_")
        target_param = None
        target_pname = None
        
        # Strategy 1: Tool-specific alias lookup
        if key_lower in tool_aliases:
            alias_target = tool_aliases[key_lower]
            if alias_target == "_combine_power":
                # Special handling for power operations
                power_parts[key_lower] = val
                continue  # Don't add to normalized yet
            elif alias_target in param_map:
                target_param = param_map[alias_target]
                target_pname = alias_target
        
        # Strategy 2: Exact match
        if target_param is None and key in param_map:
            target_param = param_map[key]
            target_pname = key
        
        # Strategy 3: Prefix/substring matching
        if target_param is None:
            for p in real_params:
                if p.name in key_lower or key_lower.startswith(p.name):
                    target_param = p
                    target_pname = p.name
                    break
        
        # If still no match, keep original key
        if target_pname is None:
            target_pname = key
        
        # Coerce string numbers to the declared type
        if target_param and isinstance(val, str):
            if target_param.type in ("number", "float"):
                try:
                    val = float(val)
                except ValueError:
                    pass
            elif target_param.type == "integer":
                try:
                    val = int(val)
                except ValueError:
                    pass
        
        if target_pname not in normalized:
            normalized[target_pname] = val
        elif target_pname in normalized and isinstance(normalized[target_pname], str):
            # Collision with existing value - try to combine intelligently
            # For expressions, we might want to concatenate
            pass
    
    # Handle power operation combination
    if power_parts and "expression" in param_map:
        base = power_parts.get("base") or power_parts.get("value") or power_parts.get("x")
        exp = power_parts.get("exponent") or power_parts.get("power") or power_parts.get("n") or power_parts.get("p") or power_parts.get("exp")
        
        if base is not None and exp is not None:
            normalized["expression"] = f"{base} ** {exp}"
        elif base is not None:
            normalized["expression"] = str(base)
    
    # Handle nested 'tool_args' that contains actual arguments
    if "tool_args" in normalized and isinstance(normalized["tool_args"], dict):
        nested = normalized.pop("tool_args")
        if isinstance(nested, dict):
            for k, v in nested.items():
                if k in param_map and k not in normalized:
                    normalized[k] = v

    return normalized


def _fix_calculator_args(t_name: str, t_args: dict, user_input: str, prior_results: list[str]) -> dict:
    """
    Detect when a model passes a plain number as a calculator expression
    (e.g. expression='83521') when the question implies a further operation
    like sqrt. Rewrites the expression to the correct form.
    
    Also handles cases where the model uses alternative argument names
    like 'base'/'exponent' instead of 'expression'.
    
    Also detects REDUNDANT calls where expression is just a prior result
    and marks them with _skip=True to avoid unnecessary tool calls.
    """
    if t_name != "calculator":
        return t_args
    
    t_args = dict(t_args)  # Make a copy
    
    # Handle alternative argument formats for power/exponent operations
    if "expression" not in t_args:
        base = t_args.get("base") or t_args.get("number") or t_args.get("x") or t_args.get("value")
        exp = t_args.get("exponent") or t_args.get("power") or t_args.get("n") or t_args.get("p")
        
        if base is not None:
            if exp is not None:
                # Power operation: base ** exp
                t_args["expression"] = f"{base} ** {exp}"
            else:
                # Just a single value - maybe needs sqrt or other operation?
                t_args["expression"] = str(base)
    
    expr = t_args.get("expression", "")
    
    # Check if expression is just a plain number
    try:
        num_val = float(expr)
    except (ValueError, TypeError):
        return t_args  # already a real expression, leave it alone

    # Check for redundant call: expression is a plain number that appears in prior results
    # This means the model is just re-calling with the result it already got
    for result in prior_results:
        # Match patterns like "calculator → 120" or just "120"
        result_clean = _strip_tool_prefix(result)
        try:
            result_num = float(result_clean)
            # Check if this is the same number (or close for floats)
            if abs(num_val - result_num) < 0.001:
                # REDUNDANT: Model is calling calculator with a result it already has
                # Mark for synthesis instead of executing
                t_args["_redundant"] = True
                t_args["_prior_result"] = result_clean
                return t_args
        except (ValueError, TypeError):
            continue

    # Not redundant - check if question implies further operation
    q = user_input.lower()
    if "sqrt" in q or "square root" in q:
        t_args["expression"] = f"sqrt({expr})"
    return t_args


def _fuzzy_match_tool_name(hallucinated_name: str, tools_registry) -> str | None:
    """
    Small models often hallucinate tool names. This function attempts to
    match a hallucinated name to a real tool name using various heuristics.
    
    Examples:
        "calculate_expression" -> "calculator"
        "get_weather_info" -> "get_weather"
        "currency_convert" -> "convert_currency"
    
    Returns the matched tool name or None if no match found.
    """
    # First, try exact match
    if tools_registry.get(hallucinated_name):
        return hallucinated_name
    
    real_names = [t.name for t in tools_registry.all()]
    lower_hallucinated = hallucinated_name.lower().replace("_", "")
    
    # Strategy 1: Check if any real tool name is a substring of the hallucinated name
    for real_name in real_names:
        lower_real = real_name.lower().replace("_", "")
        if lower_real in lower_hallucinated or lower_hallucinated in lower_real:
            return real_name
    
    # Strategy 2: Word mappings for common hallucinations
    # Maps keyword → list of acceptable tools (in priority order)
    word_mappings = {
        # Calculator-related - can also use python_repl
        "calculate": ["calculator", "python_repl"],
        "calc": ["calculator", "python_repl"],
        "math": ["calculator", "python_repl"],
        "compute": ["calculator", "python_repl"],
        "eval": ["calculator", "python_repl"],
        "expression": ["calculator", "python_repl"],
        "power": ["calculator", "python_repl"],
        "pow": ["calculator", "python_repl"],
        "square": ["calculator", "python_repl"],
        "sqrt": ["calculator", "python_repl"],
        "root": ["calculator", "python_repl"],
        "add": ["calculator", "python_repl"],
        "subtract": ["calculator", "python_repl"],
        "multiply": ["calculator", "python_repl"],
        "divide": ["calculator", "python_repl"],
        "calculator": ["calculator", "python_repl"],
        
        # Python REPL - can fallback to shell for many operations
        "python": ["python_repl", "shell"],
        "repl": ["python_repl", "shell"],
        "code": ["python_repl", "shell"],
        "print": ["python_repl", "shell"],
        "execute": ["python_repl", "shell"],
        "run": ["python_repl", "shell"],
        "exec": ["python_repl", "shell"],
        
        # Date/time - can use python_repl OR shell
        "today": ["python_repl", "shell"],
        "date": ["python_repl", "shell"],
        "time": ["python_repl", "shell"],
        "datetime": ["python_repl", "shell"],
        "now": ["python_repl", "shell"],
        "current": ["python_repl", "shell"],
        "get_date": ["python_repl", "shell"],
        "get_time": ["python_repl", "shell"],
        
        # Shell - explicit shell commands
        "shell": ["shell"],
        "bash": ["shell"],
        "cmd": ["shell"],
        "command": ["shell"],
        "ls": ["shell"],
        "dir": ["shell"],
        "cat": ["shell"],
        "echo": ["shell"],
        "grep": ["shell"],
        "find": ["shell"],
        "pwd": ["shell"],
        "mkdir": ["shell"],
        "rm": ["shell"],
        "cp": ["shell"],
        "mv": ["shell"],
        
        # File I/O
        "read": ["read_file"],
        "write": ["write_file"],
        "file": ["read_file"],
        "load": ["read_file"],
        "save": ["write_file"],
        
        # Weather (example custom tool)
        "weather": ["get_weather"],
        
        # Currency (example custom tool)
        "currency": ["convert_currency"],
        "convert": ["convert_currency"],
        "money": ["convert_currency"],
    }
    
    for keyword, tool_hints in word_mappings.items():
        if keyword in lower_hallucinated:
            # Try each hint in priority order
            for tool_hint in tool_hints:
                for real_name in real_names:
                    if tool_hint in real_name or real_name == tool_hint:
                        return real_name
    
    # Strategy 3: Levenshtein-like similarity (first 4+ chars match)
    for real_name in real_names:
        lower_real = real_name.lower()
        if len(lower_real) >= 4 and len(lower_hallucinated) >= 4:
            if lower_real[:4] == lower_hallucinated[:4]:
                return real_name
    
    return None


def _looks_like_tool_schema(text: str) -> bool:
    """
    Returns True if the text looks like the model outputting a JSON
    function-call schema rather than a real answer. Catches patterns like:
      {"name": "...", "parameters": {...}}
      {"name": "...", "arguments": {...}}
    even when no tools were defined.
    """
    stripped = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1:
        return False
    try:
        obj = json.loads(stripped[start:end + 1])
        return (
            isinstance(obj, dict)
            and "name" in obj
            and any(k in obj for k in ("parameters", "arguments", "args"))
        )
    except json.JSONDecodeError:
        return False


def _looks_like_tool_schema_dump(text: str) -> bool:
    """
    Detect when a model dumps the entire tool schema as text instead of
    using it properly. This happens with some models like granite3.1-moe.
    
    Pattern example:
      ოC[{"function <nil> {calculator Evaluate a mathematical expression...
    
    This is different from _looks_like_tool_schema which detects when a model
    outputs a single tool call as JSON. This detects when the model outputs
    the entire schema definition.
    """
    if not text:
        return False
    
    # Signs that the model dumped the tool schema
    dump_indicators = [
        # Schema dump pattern from granite models
        '{"function <nil>',
        # Multiple tool definitions in one output
        '"type":"function"',
        '"parameters":{"type":"object"',
        # Ollama-style schema dump
        '[{"type":',
        # Contains schema definition keywords
        '"required":',
        '"properties":',
        # Tool description in name field
        'Search the web using DuckDuckGo',
        'Evaluate a mathematical expression',
        'Execute Python code',
        '{object <nil>',
    ]
    
    text_lower = text.lower()
    matches = sum(1 for indicator in dump_indicators if indicator.lower() in text_lower)
    
    # If 2+ indicators match, it's likely a schema dump
    return matches >= 2


def _is_simple_answered_query(user_input: str, successful_results: list[str]) -> bool:
    """
    Return True when a single successful tool result is sufficient to answer
    the user's question and the agent should synthesize immediately.

    Targets the most common small-model looping patterns:
      - Date/time queries ("what is the date", "what time is it")
      - Simple arithmetic ("what is 2+2", "sqrt of 144")
      - Single-file reads ("show me file.py")
      - Single directory listings

    Deliberately conservative — returns False for anything that might
    genuinely need multiple tool calls (multi-step tasks, comparisons, etc.)
    """
    if not successful_results:
        return False

    lower = user_input.lower().strip()

    # Date/time patterns
    date_time_keywords = [
        "date", "time", "day", "today", "now", "current date",
        "what day", "what time", "year", "month",
    ]
    if any(kw in lower for kw in date_time_keywords):
        return True

    # Simple arithmetic / single calculation
    math_keywords = ["what is", "calculate", "compute", "sqrt", "square root",
                     "result of", "value of", "evaluate"]
    math_ops = ["+", "-", "*", "/", "^", "**", "%"]
    if any(kw in lower for kw in math_keywords) and len(lower) < 60:
        return True
    if sum(1 for op in math_ops if op in lower) >= 1 and len(lower) < 40:
        return True

    # Single file read / single dir listing
    single_file_keywords = ["read", "show", "display", "print", "list", "ls"]
    if any(kw in lower for kw in single_file_keywords) and len(lower.split()) <= 6:
        return True

    return False


def _is_greeting_or_simple(text: str) -> bool:
    """
    Check if the user input is a simple greeting or short message
    that shouldn't require tool usage.
    """
    lower = text.lower().strip()
    greetings = [
        "hi", "hello", "hey", "hola", "howdy", "greetings",
        "good morning", "good afternoon", "good evening",
        "what's up", "whats up", "sup", "yo",
        "thanks", "thank you", "ok", "okay", "yes", "no", "sure",
        "bye", "goodbye", "see you", "cya",
    ]
    
    # Check for exact match or greeting at start
    if lower in greetings:
        return True
    for g in greetings:
        if lower.startswith(g + " "):
            return True
    
    # Very short messages (< 10 chars) are likely simple
    if len(lower) < 10 and not any(c in lower for c in "0123456789+-*/=><"):
        return True
    
    return False


def _convert_to_pystrftime(format_str: str) -> str:
    """
    Convert common date format patterns to Python strftime format.
    
    Handles formats like:
    - YYYY-MM-DD -> %Y-%m-%d
    - DD/MM/YYYY -> %d/%m/%Y
    - MM-DD-YYYY -> %m-%d-%Y
    - ISO -> %Y-%m-%d
    """
    # Map common patterns to strftime
    replacements = [
        ("YYYY", "%Y"),
        ("YY", "%y"),
        ("MM", "%m"),
        ("DD", "%d"),
        ("HH", "%H"),
        ("mm", "%M"),
        ("ss", "%S"),
        ("ISO", "%Y-%m-%d"),
        ("iso", "%Y-%m-%d"),
    ]
    
    result = format_str
    for pattern, strftime in replacements:
        result = result.replace(pattern, strftime)
    
    # If nothing was replaced, use the format as-is
    # (might already be in strftime format)
    if result == format_str:
        # Common strftime characters that indicate it's already formatted
        if "%" in format_str:
            return format_str
        # Default to ISO format
        return "%Y-%m-%d"
    
    return result


def _generate_helpful_error_message(tool_name: str, tool, provided_args: dict, error_msg: str) -> str:
    """
    Generate a helpful error message that shows the correct usage format
    when a tool call fails due to incorrect arguments.
    """
    if tool is None:
        return f"[Tool error] {error_msg}"
    
    # Get expected parameters
    params_desc = []
    for p in tool.params:
        req_marker = "*" if p.required else ""
        params_desc.append(f"{p.name}{req_marker}: {p.type}")
    
    # Get usage examples based on tool name
    examples = {
        "calculator": 'calculator(expression="15 * 8")',
        "write_file": 'write_file(path="/tmp/file.txt", content="Hello")',
        "read_file": 'read_file(path="/tmp/file.txt")',
        "python_repl": 'python_repl(code="print(2**10)")',
        "shell": 'shell(command="date")',
        "web_search": 'web_search(query="capital of France")',
        "get_weather": 'get_weather(city="Tokyo")',
        "convert_currency": 'convert_currency(amount=100, from_currency="USD", to_currency="EUR")',
    }
    
    example = examples.get(tool_name, f"{tool_name}(appropriate_arguments)")
    
    # Show what was provided vs expected
    provided_str = ", ".join(f"{k}={v!r}" for k, v in provided_args.items()) if provided_args else "nothing"
    expected_str = ", ".join(params_desc)
    
    return (
        f"[Tool error] Incorrect arguments for {tool_name}.\n"
        f"  Expected: {expected_str}\n"
        f"  You provided: {provided_str}\n"
        f"  Correct example: {example}\n"
        f"  Please retry with the correct argument names."
    )


def _synthesize_missing_args(tool_name: str, args: dict, user_input: str, prior_results: list[str], tools_registry) -> dict:
    """
    Try to fill in missing required arguments from context.
    This helps small models that call tools with incomplete arguments.
    """
    tool = tools_registry.get(tool_name) if tools_registry else None
    if tool is None:
        return args
    
    args = dict(args)  # Make a copy
    required_params = {p.name for p in tool.params if p.required}
    missing = required_params - set(args.keys())
    
    if not missing:
        return args  # Nothing to synthesize
    
    q_lower = user_input.lower()
    
    # Tool-specific synthesis
    if tool_name == "calculator" and "expression" in missing:
        # Try to extract numbers and operators from user input
        numbers = re.findall(r'\d+\.?\d*', user_input)
        operators = re.findall(r'[+\-*/^]', user_input)
        
        # Check for specific operation types
        if "sqrt" in q_lower or "square root" in q_lower:
            if numbers:
                args["expression"] = f"sqrt({numbers[-1]})"
        elif "power" in q_lower or "^" in user_input:
            if len(numbers) >= 2:
                args["expression"] = f"{numbers[0]} ** {numbers[1]}"
        elif "times" in q_lower or "multiply" in q_lower or "multiplied" in q_lower:
            if len(numbers) >= 2:
                args["expression"] = f"{numbers[0]} * {numbers[1]}"
        elif "divided" in q_lower or "divide" in q_lower:
            if len(numbers) >= 2:
                args["expression"] = f"{numbers[0]} / {numbers[1]}"
        elif "plus" in q_lower or "add" in q_lower or "sum" in q_lower:
            if len(numbers) >= 2:
                args["expression"] = f"{numbers[0]} + {numbers[1]}"
        elif "minus" in q_lower or "subtract" in q_lower:
            if len(numbers) >= 2:
                args["expression"] = f"{numbers[0]} - {numbers[1]}"
        elif numbers and operators:
            # Construct expression from found elements
            expr_parts = []
            for i, num in enumerate(numbers):
                expr_parts.append(num)
                if i < len(operators):
                    expr_parts.append(operators[i])
            args["expression"] = " ".join(expr_parts)
        elif numbers:
            # Just numbers, default to the first one
            args["expression"] = numbers[0]
    
    elif tool_name == "python_repl" and "code" in missing:
        # Synthesize Python code for common queries
        if "date" in q_lower and "time" in q_lower:
            args["code"] = "from datetime import datetime\nprint(datetime.now().strftime('Today is %A, %B %d, %Y and the time is %I:%M %p.'))"
        elif "date" in q_lower:
            # Check if a format was provided
            provided_format = args.get("format", args.get("date_format", ""))
            if provided_format:
                # Convert common format patterns to Python strftime
                py_format = _convert_to_pystrftime(provided_format)
                args["code"] = f"from datetime import datetime\nprint(datetime.now().strftime('{py_format}'))"
            else:
                args["code"] = "from datetime import datetime\nprint(datetime.now().strftime('Today is %A, %B %d, %Y.'))"
        elif "time" in q_lower:
            args["code"] = "from datetime import datetime\nprint(datetime.now().strftime('The current time is %I:%M %p.'))"
        else:
            # Generic - just return current datetime
            args["code"] = "from datetime import datetime\nprint(datetime.now())"
    
    elif tool_name == "shell" and "command" in missing:
        # Synthesize shell commands for common queries
        if "date" in q_lower:
            args["command"] = "date"
        elif "time" in q_lower:
            args["command"] = "date +%T"
        elif "directory" in q_lower or "folder" in q_lower:
            args["command"] = "pwd"
        elif "files" in q_lower and "list" in q_lower:
            args["command"] = "ls -la"
    
    elif tool_name == "write_file" and prior_results:
        # If we have prior results, maybe the model wants to write them
        if "content" in missing and "path" in args:
            # Use the last tool result as content
            args["content"] = _strip_tool_prefix(prior_results[-1])
    
    return args


def _is_small_model(model: str) -> bool:
    """
    Heuristic to detect if a model is small (< 2B parameters).
    Small models benefit from few-shot prompting.
    """
    model_lower = model.lower()
    
    # Check for size indicators in model name
    small_indicators = [
        ":0.5b", ":0.6b", ":1b", ":1.5b", ":1.8b",
        "0.5b", "0.6b", "1b", "1.5b",
        "270m", "135m", "350m", "500m", "800m",
        "tiny", "mini", "micro", "small"
    ]
    
    for indicator in small_indicators:
        if indicator in model_lower:
            return True
    
    # Check parameter count after common model names
    import re
    param_match = re.search(r'(\d+(?:\.\d+)?)[bm]', model_lower)
    if param_match:
        size_str = param_match.group(1)
        try:
            size = float(size_str)
            if 'm' in model_lower[param_match.end()-1:param_match.end()]:
                return True  # Any million-parameter model is small
            if size < 2:
                return True  # Less than 2 billion
        except ValueError:
            pass
    
    return False


# ------------------------------------------------------------------ #
#  Agent result                                                         #
# ------------------------------------------------------------------ #

@dataclass
class StepResult:
    type: Literal["thought", "tool_call", "tool_result", "final"]
    content: str
    tool_name: str | None = None
    tool_args: dict | None = None
    elapsed_ms: float = 0.0

    def __str__(self):
        if self.type == "tool_call":
            return f"[CALL] {self.tool_name}({self.tool_args})"
        if self.type == "tool_result":
            return f"[RESULT] {self.tool_name} → {self.content}"
        if self.type == "thought":
            return f"[THOUGHT] {self.content}"
        return f"[FINAL] {self.content}"


@dataclass
class AgentRun:
    steps: list[StepResult] = field(default_factory=list)
    final_answer: str = ""
    total_ms: float = 0.0
    success: bool = True
    error: str = ""

    def print_trace(self):
        for step in self.steps:
            print(step)
        print(f"\n✓ Done in {self.total_ms:.0f}ms")


# ------------------------------------------------------------------ #
#  ReAct text parser                                                   #
# ------------------------------------------------------------------ #

# Enhanced regex patterns to handle common small model output variations:
# - Backticks around tool names: Action: `shell`
# - Same-line format: Action: shell Action Input: {...}
# - Quotes around tool names: Action: "shell"
# - Extra whitespace
# - Stop at next Action, Example, Observation, Thought, Final Answer, or end
_THOUGHT_RE = re.compile(r"Thought:\s*(.*?)(?=Action:|Final Answer:|$)", re.DOTALL | re.IGNORECASE)
_ACTION_RE  = re.compile(
    r"Action:\s*[`\"']?(\w+)[`\"']?\s*\n?\s*Action Input:\s*(.*?)(?=\n\s*(?:Observation:|Thought:|Final Answer:|Action:|Example)|$)",
    re.DOTALL | re.IGNORECASE
)
# Alternative pattern for same-line format: Action: tool_name Action Input: {...}
_ACTION_RE_SAMELINE = re.compile(
    r"Action:\s*[`\"']?(\w+)[`\"']?\s+Action Input:\s*(.*?)(?=\n\s*(?:Observation:|Thought:|Final Answer:|Action:|Example)|$)",
    re.DOTALL | re.IGNORECASE
)
_FINAL_RE   = re.compile(r"Final Answer:\s*(.*?)$", re.DOTALL | re.IGNORECASE)
_PYTHON_CODE_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)

# Repetition detection pattern - catches "Final Answer: X" repeated multiple times
_REPETITION_RE = re.compile(r'(Final Answer:\s*[^\n]+)(\s*\1){2,}', re.IGNORECASE)


def _detect_and_fix_repetition(text: str) -> str:
    """
    Detect and fix repetitive output from small models.
    
    Some models (like qwen3:0.6b) get stuck in loops repeating the same phrase:
        "Final Answer: 120\nFinal Answer: 120\nFinal Answer: 120..."
    
    This function detects such patterns and returns the text with only one instance.
    Also handles general repetition of any phrase 3+ times.
    """
    if not text:
        return text
    
    # Fix "Final Answer:" repetition specifically
    match = _REPETITION_RE.search(text)
    if match:
        # Keep only one instance of the repeated phrase
        text = _REPETITION_RE.sub(r'\1', text)
    
    # Also detect and fix any line repeated 3+ times at the end
    lines = text.split('\n')
    if len(lines) >= 3:
        # Check if the last 3+ lines are identical
        last_line = lines[-1].strip()
        if last_line:
            repeat_count = 1
            for i in range(len(lines) - 2, -1, -1):
                if lines[i].strip() == last_line:
                    repeat_count += 1
                else:
                    break
            
            if repeat_count >= 3:
                # Keep only one instance
                text = '\n'.join(lines[:-repeat_count + 1])
    
    return text

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


def _sanitize_model_json(text: str) -> str:
    """
    Fix common JSON mistakes made by small (0.5b-3b) models before parsing.

    1. Python bool/None literals to JSON equivalents:
       True -> true,  False -> false,  None -> null

    2. Python string concatenation in values - keep only the string literal:
       "Today: " + datetime.now().strftime(...)  becomes  "Today: "
       This is the most common failure mode with 0.5b models.

    3. Trailing commas before } or ] (technically invalid JSON)
    """
    # 1. Python booleans / None - simple word replacement
    # Using explicit replace chains to avoid regex escaping issues
    # Only replace as whole words preceded by : or [ or space
    import re as _re
    text = _re.sub(r':\s*True',  ': true',  text)
    text = _re.sub(r':\s*False', ': false', text)
    text = _re.sub(r':\s*None',  ': null',  text)
    text = _re.sub(r'\[\s*True',  '[true',  text)
    text = _re.sub(r'\[\s*False', '[false', text)
    text = _re.sub(r'\[\s*None',  '[null',  text)

    # 2. Python string concatenation: "literal" + anything -> "literal"
    # Match a JSON string followed by + and non-JSON content up to , } ] or newline
    text = _re.sub(r'("(?:[^"\\]|\\.)*")\s*\+\s*[^,\'"}\]\n]+', r'\1', text)

    # 3. Trailing commas before } or ]
    text = _re.sub(r',\s*([}\]])', r'\1', text)

    return text


def _parse_json_tool_call(text: str, debug: bool = False) -> tuple[str | None, dict | None]:
    """
    Fallback for models that output tool calls as JSON text instead of
    using the native tool_calls API field. Handles patterns like:

        ```json
        {"name": "calculator", "arguments": {"expression": "2+2"}}
        ```

    Also handles bare argument objects (qwen2.5-coder style):

        ```json
        {"expression": "15 * 8"}
        ```

    Returns (tool_name, tool_args) or (None, None) if not found.

    Also handles cases where the model puts code in the 'name' field:
        {"name": "print(2 ** 20)", "arguments": {"code": "2 ** 20"}}
    """
    # Check for tool schema dump first - don't try to parse it
    if _looks_like_tool_schema_dump(text):
        if debug:
            print(f"    _parse_json_tool_call: skipping - looks like schema dump")
        return None, None

    # First, try to extract JSON from markdown code blocks (most reliable)
    # Find ALL code blocks and try each one as JSON
    # Pattern: ```json followed by newline, then content, then closing ```
    # Use [^\n]* to handle optional whitespace after ```json before newline
    # Don't require newline before closing fence
    code_block_pattern = re.compile(r'```(?:json)?[^\n]*\n(.*?)```', re.DOTALL)
    code_blocks = code_block_pattern.findall(text)
    if debug and code_blocks:
        print(f"    _parse_json_tool_call: found {len(code_blocks)} code blocks")
    for block in code_blocks:
        block = block.strip()
        if debug:
            print(f"    _parse_json_tool_call: checking block (starts with '{block[0] if block else ''}'): {block[:60]}...")
        if block.startswith('{'):
            if debug:
                print(f"    _parse_json_tool_call: found JSON code block: {block[:80]}...")
            json_str = _sanitize_model_json(block)
            try:
                obj = json.loads(json_str)
                result = _extract_tool_from_json(obj, debug)
                if result[0]:  # Found valid tool
                    return result
            except json.JSONDecodeError as e:
                if debug:
                    print(f"    _parse_json_tool_call: code block JSON parse error: {e}")
                continue

    # Fallback: Strip all markdown and find first JSON object
    cleaned = re.sub(r"```(?:json|python)?", "", text).strip().rstrip("`").strip()
    
    # Find the outermost JSON object - be more careful about matching braces
    start = cleaned.find("{")
    if start == -1:
        if debug:
            print(f"    _parse_json_tool_call: no JSON object found")
        return None, None
    
    # Find matching closing brace
    depth = 0
    end = -1
    for i, ch in enumerate(cleaned[start:], start):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end = i
                break
    
    if end == -1:
        if debug:
            print(f"    _parse_json_tool_call: no matching closing brace")
        return None, None

    json_str = cleaned[start:end + 1]
    if debug:
        print(f"    _parse_json_tool_call: extracted JSON: {json_str[:100]}...")

    # Sanitize common small-model JSON mistakes
    json_str = _sanitize_model_json(json_str)

    try:
        obj = json.loads(json_str)
    except json.JSONDecodeError as e:
        if debug:
            print(f"    _parse_json_tool_call: JSON parse error: {e}")
        return None, None

    return _extract_tool_from_json(obj, debug)


def _extract_tool_from_json(obj: dict, debug: bool = False) -> tuple[str | None, dict | None]:
    """Extract tool name and args from a parsed JSON object."""
    # Support {"name": ..., "arguments": ...} and {"name": ..., "parameters": ...}
    name = obj.get("name") or obj.get("function")
    args = obj.get("arguments") or obj.get("parameters") or obj.get("args") or {}

    # Handle bare argument objects: {"expression": "..."} without name wrapper
    # Infer tool name from known argument keys
    if not name and isinstance(obj, dict):
        # Map known argument keys to tool names
        arg_to_tool = {
            "expression": "calculator",
            "command": "shell",
            "code": "python_repl",
            "path": "read_file",
            "content": "write_file",
            "query": "web_search",
            "url": "http_get",
        }
        for key in obj.keys():
            if key in arg_to_tool:
                name = arg_to_tool[key]
                args = obj
                break

    if not name or not isinstance(args, dict):
        if debug:
            print(f"    _extract_tool_from_json: no name or args (name={name!r}, args type={type(args).__name__})")
        return None, None

    # Detect if the 'name' field contains code instead of a tool name.
    code_indicators = ["(", ")", "+", "-", "*", "/", "=", "[", "]", "print", "def ", "return"]
    if any(indicator in name for indicator in code_indicators):
        return name, args

    return name, args


def _extract_python_code(text: str) -> str | None:
    """
    Extract Python code from markdown code blocks.
    Returns the code content or None if no code block found.
    """
    match = _PYTHON_CODE_RE.search(text)
    if match:
        return match.group(1).strip()
    return None


def _try_extract_tool_from_malformed(text: str, available_tools: list[str]) -> tuple[str | None, dict | None]:
    """
    Try to extract a tool call from malformed model output.
    
    Handles cases like:
    - Model puts code in "name" field: {"name": "datetime.now()..."}
    - Model puts schema description in "name" field: {"name": "web_search.Search the web..."}
    - Model outputs partial JSON
    """
    text_lower = text.lower()
    
    # Try to find any available tool name in the text
    for tool_name in available_tools:
        if tool_name.lower() in text_lower:
            # Found a tool name, try to extract arguments
            # Look for common argument patterns
            args = {}
            
            # For python_repl, try to extract code
            if tool_name == "python_repl":
                code = _extract_python_code(text)
                if code:
                    return tool_name, {"code": code}
                # Try to find Python code patterns
                if "datetime" in text_lower or "strftime" in text_lower:
                    # It's a datetime query
                    return tool_name, {}
            
            # For web_search, try to extract query
            if tool_name == "web_search":
                # Look for quoted strings that might be a query
                query_match = re.search(r'"query":\s*"([^"]+)"', text)
                if query_match:
                    return tool_name, {"query": query_match.group(1)}
                # Or just return with empty args - agent will synthesize
                return tool_name, {}
            
            # For calculator, try to extract expression
            if tool_name == "calculator":
                expr_match = re.search(r'"expression":\s*"([^"]+)"', text)
                if expr_match:
                    return tool_name, {"expression": expr_match.group(1)}
                return tool_name, {}
            
            # Default: return with empty args
            return tool_name, args
    
    return None, None


def _parse_react(text: str) -> tuple[str | None, str | None, dict | None, str | None]:
    """
    Returns (thought, tool_name, tool_args, final_answer).
    Any field may be None if not present.
    
    Handles multiple format variations from small models:
    - Standard ReAct format with newline separation
    - Same-line format: Action: tool Action Input: {...}
    - Backticks around tool names: Action: `tool`
    - Quotes around tool names: Action: "tool"
    - Repetitive output loops (e.g., "Final Answer: X" repeated 100 times)
    """
    # Fix repetitive output before parsing
    text = _detect_and_fix_repetition(text)
    
    thought = None
    tool_name = None
    tool_args = None
    final_answer = None

    # Extract thought
    m = _THOUGHT_RE.search(text)
    if m:
        thought = m.group(1).strip()

    # Try to extract action - try multiple patterns
    m = _ACTION_RE.search(text)
    if not m:
        m = _ACTION_RE_SAMELINE.search(text)
    
    if m:
        tool_name = m.group(1).strip()
        raw_args = m.group(2).strip()
        
        # Strip any trailing backticks or quotes from tool name
        tool_name = tool_name.strip('`"\'')
        
        # Try to parse JSON args
        try:
            tool_args = json.loads(raw_args)
        except json.JSONDecodeError:
            # Try sanitizing first
            sanitized = _sanitize_model_json(raw_args)
            try:
                tool_args = json.loads(sanitized)
            except json.JSONDecodeError:
                # Try to salvage key=value style or wrapped content
                # Handle cases like `{command="echo", arguments={...}}`
                if raw_args.startswith('{') and '=' in raw_args and 'arguments' not in raw_args.lower():
                    # Likely malformed JSON, try to extract values
                    tool_args = {"input": raw_args}
                else:
                    tool_args = {"input": raw_args}

    # Extract final answer
    fa_match = _FINAL_RE.search(text)
    if fa_match:
        final_answer = fa_match.group(1).strip()

    return thought, tool_name, tool_args, final_answer


# ------------------------------------------------------------------ #
#  Agent                                                               #
# ------------------------------------------------------------------ #

class Agent:
    """
    A single autonomous agent backed by a local Ollama model.

    Parameters
    ----------
    model : str
        Ollama model tag, e.g. "llama3.1:8b" or "qwen2.5:14b".
    tools : ToolRegistry | None
        Tools this agent may call.
    system_prompt : str
        Base instructions for the agent.
    max_steps : int
        Safety ceiling on tool-call iterations per run.
    client : OllamaClient | None
        Shared client (creates one if not provided).
    force_react : bool
        If True, always use text-based ReAct even if the model supports native tools.
    on_step : Callable[[StepResult], None] | None
        Called after each step — useful for live UI updates.
    model_options : dict | None
        Passed through to Ollama (temperature, num_ctx, etc.).
    model_family : str | None
        Model family (e.g., "llama", "qwen2", "gemma3"). If None, auto-detected from Ollama API.
        Useful for family-specific handling in subclasses or custom logic.
    few_shot : bool | None
        If True, add few-shot examples for small models. If None, auto-detect based on model size.
    use_compact_prompt : bool
        If True, use compact few-shot prompt (less tokens).
    """

    def __init__(
        self,
        model: str,
        tools: ToolRegistry | None = None,
        system_prompt: str = "You are a helpful assistant.",
        max_steps: int = 10,
        client: OllamaClient | None = None,
        force_react: bool = False,
        on_step: Callable[[StepResult], None] | None = None,
        model_options: dict | None = None,
        memory_max_turns: int = 20,
        debug: bool = False,
        few_shot: bool | None = None,
        use_compact_prompt: bool = False,
        model_family: str | None = None,
    ):
        self.model = model
        self.tools = tools or ToolRegistry()
        self.max_steps = max_steps
        # Backend-aware client selection
        if client is not None:
            self.client = client
        elif _AGENTNOVA_BACKEND == "bitnet" and _BITNET_AVAILABLE:
            from ..bitnet_client import BitnetClient
            from ..config import BITNET_BASE_URL
            self.client = BitnetClient(base_url=BITNET_BASE_URL)
        else:
            self.client = OllamaClient()
        self.force_react = force_react
        self.on_step = on_step
        self.model_options = model_options or {}
        self.debug = debug
        self.use_compact_prompt = use_compact_prompt

        # Determine model family (auto-detect if not provided)
        if model_family is not None:
            self.model_family = model_family
        elif hasattr(self.client, 'get_model_family'):
            self.model_family = self.client.get_model_family(model)
        else:
            self.model_family = None

        # Determine tool support level: "native", "react", "none", or "untested"
        # Priority: force_react > tested_models.json
        # "untested" defaults to "react" (safest default)
        if force_react:
            self._tool_support = "react"
        else:
            # Try to import get_tool_support from cli
            try:
                from ..cli import get_tool_support
                self._tool_support = get_tool_support(model, self.client)
            except ImportError:
                self._tool_support = "untested"
        
        # Treat "untested" as "react" (safest default)
        if self._tool_support == "untested":
            self._tool_support = "react"
        
        # Determine if native tools should be used
        # "native" = pass tools to API, let model handle
        # "react" = use text-based ReAct parsing
        # "none" = don't use tools at all
        self._native_tools = (self._tool_support == "native")
        self._no_tools = (self._tool_support == "none")
        
        # Add stop tokens for ReAct mode to prevent runaway generation
        # Models sometimes loop "Final Answer: X\nFinal Answer: X..."
        if self._tool_support == "react" and self.tools.all():
            # Get family-specific stop tokens
            family_stops = get_stop_tokens(self.model_family or "")
            # Add ReAct-specific stop tokens
            react_stops = ["\nFinal Answer:", "\nThought:", "\nAction:"]
            # Merge with existing stop tokens from model_options
            existing_stops = self.model_options.get("stop", [])
            if isinstance(existing_stops, str):
                existing_stops = [existing_stops]
            all_stops = list(set(existing_stops + family_stops + react_stops))
            self.model_options["stop"] = all_stops
        
        # Get family-specific configuration
        from .model_family_config import (
            get_family_config, should_use_few_shot, get_few_shot_style,
            get_react_system_suffix, get_native_tool_hints, has_known_issues
        )
        self._family_config = get_family_config(self.model_family)
        self._family_issues = has_known_issues(self.model_family)
        
        # Determine if we should use few-shot prompting
        self._is_small_model = _is_small_model(model)
        if few_shot is not None:
            self._use_few_shot = few_shot
        else:
            # Use family config + model size to decide
            self._use_few_shot = should_use_few_shot(self.model_family or "", model)
        
        # Get family-specific few-shot style
        self._few_shot_style = get_few_shot_style(self.model_family or "")

        # Build system prompt based on tool support level AND family
        base_sys = system_prompt
        
        # For "react" level: add tool descriptions and family-specific ReAct format
        if self._tool_support == "react" and self.tools.all():
            tool_descriptions = "\n".join(
                f"- {t.name}: {t.description}" for t in self.tools.all()
            )
            # Use family-specific ReAct suffix
            react_suffix = get_react_system_suffix(self.model_family or "")
            base_sys = base_sys + f"\n\nAvailable tools:\n{tool_descriptions}\n{react_suffix}"
        
        # For "native" level: add family-specific tool hints
        elif self._tool_support == "native" and self.tools.all():
            native_hints = get_native_tool_hints(self.model_family or "")
            if native_hints:
                base_sys = base_sys + "\n\n" + native_hints
        
        # For "none" level: don't add any tool-related prompts
        # Model should use its Modelfile system prompt as-is
        
        # Add few-shot examples based on family preference
        # For react mode: always add if enabled
        # For native mode: add for small models that need guidance on WHEN to call tools
        add_few_shot = False
        if self._use_few_shot and self.tools.all():
            if self._tool_support == "react":
                add_few_shot = True
            elif self._tool_support == "native" and self._is_small_model:
                # Small native models benefit from examples showing WHEN to call tools
                add_few_shot = True
        
        if add_few_shot:
            # Use compact for families that prefer it or small models
            use_compact = use_compact_prompt or self._few_shot_style == "compact"
            few_shot_suffix = FEW_SHOT_COMPACT if use_compact else FEW_SHOT_SUFFIX
            
            # For families with truncate_json issue, use extra compact
            if self._family_issues.get("truncate_json"):
                few_shot_suffix = FEW_SHOT_COMPACT
            
            base_sys = base_sys + few_shot_suffix

        # Debug: Show prompt construction
        if debug:
            print(f"\n  🔍 DEBUG: System prompt construction")
            print(f"    _tool_support={self._tool_support}")
            print(f"    _use_few_shot={self._use_few_shot}")
            print(f"    _few_shot_style={self._few_shot_style}")
            print(f"    _is_small_model={self._is_small_model}")
            print(f"    model_family={self.model_family}")
            print(f"    _family_issues={self._family_issues}")
            print(f"    System prompt length: {len(base_sys)} chars")

        self.memory = Memory(
            system_prompt=base_sys,
            max_turns=memory_max_turns,
        )

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def run(self, user_input: str) -> AgentRun:
        """
        Run the agent on a user message and return a complete AgentRun.
        """
        run = AgentRun()
        t0 = time.perf_counter()
        self.memory.add_user(user_input)

        # Short-circuit for models with no tool support
        # Just get a response and return it directly
        if self._no_tools:
            step_t0 = time.perf_counter()
            response = self.client.chat(
                model=self.model,
                messages=self.memory.to_messages(),
                tools=None,  # Don't pass tools
                options=self.model_options,
            )
            elapsed = (time.perf_counter() - step_t0) * 1000
            msg = response.get("message", {})
            content = msg.get("content", "")
            
            if self.debug:
                print(f"\n  🔍 DEBUG: No tool support mode")
                print(f"    _tool_support={self._tool_support}")
                print(f"    content[:100]={content[:100]!r}")
            
            # Store and return the response
            self.memory.add_assistant(content)
            run.final_answer = content
            run.total_ms = elapsed
            run.steps.append(StepResult(type="final", content=content, elapsed_ms=elapsed))
            return run

        # Loop guards
        _tool_call_counts: dict[str, int] = {}  # per-tool call counter
        _successful_results: list[str] = []      # accumulate good results for synthesis
        _successful_tools: set[str] = set()      # track which tools have returned good results
        _last_tool_args: dict[str, dict] = {}    # last args per tool to detect identical repeat calls
        _max_calls_per_tool = 2
        _max_total_tool_calls = 4               # hard ceiling across all tools

        for _ in range(self.max_steps):
            step_t0 = time.perf_counter()

            response = self.client.chat(
                model=self.model,
                messages=self.memory.to_messages(),
                tools=self.tools.schemas() if self._native_tools else None,
                options=self.model_options,
            )

            elapsed = (time.perf_counter() - step_t0) * 1000
            msg = response.get("message", {})
            content = msg.get("content", "")
            tool_calls_raw = msg.get("tool_calls", [])

            # Debug output
            if self.debug:
                print(f"\n  🔍 DEBUG: Response received")
                print(f"    _tool_support={self._tool_support}")
                print(f"    _native_tools={self._native_tools}")
                print(f"    tool_calls_raw={tool_calls_raw!r}")
                print(f"    content (FULL): {content!r}")

            # ---- Greeting short-circuit (shared by both tool paths) ------- #
            # If the user sent a simple greeting and tools are registered, the model
            # may still try to invoke tools. Intercept early and return clean text.
            if self._native_tools and self.tools.all() and _is_greeting_or_simple(user_input):
                greeting_reply = content if content and not _looks_like_tool_schema(content) \
                    else "Hello! How can I help you today?"
                final_step = StepResult(type="final", content=greeting_reply, elapsed_ms=elapsed)
                run.steps.append(final_step)
                self._emit(final_step)
                run.final_answer = greeting_reply
                self.memory.add_assistant(greeting_reply)
                break

            # ---- Native tool calling --------------------------------- #
            if self._native_tools and tool_calls_raw:

                # Process each tool call, applying intercepts before writing to memory
                for tc in tool_calls_raw:
                    fn = tc.get("function", {})
                    t_name = fn.get("name", "")
                    t_args = fn.get("arguments", {})
                    if isinstance(t_args, str):
                        try:
                            t_args = json.loads(t_args)
                        except json.JSONDecodeError:
                            t_args = {}

                    # Detect code-in-name hallucination: model puts an expression
                    # like "sqrt(144)" or "print(...)" in the name field instead of
                    # a real tool name. Try to recover the intended tool via fuzzy match.
                    code_indicators = ["(", ")", "+", "-", "*", "/", "=", "[", "]", " "]
                    if t_name and any(c in t_name for c in code_indicators):
                        if self.debug:
                            print(f"    code-in-name detected: {t_name!r}, attempting recovery")
                        fuzzy = _fuzzy_match_tool_name(t_name, self.tools)
                        if fuzzy:
                            # If the name looks like a math expression (e.g. "sqrt(144)"),
                            # use it directly as the calculator expression — it's more
                            # complete than whatever the model put in the arguments.
                            if fuzzy == "calculator":
                                t_args = {"expression": t_name}
                            elif fuzzy == "python_repl" and not t_args.get("code"):
                                t_args = {"code": t_name}
                            t_name = fuzzy
                        else:
                            if self.debug:
                                print(f"    could not recover tool name, skipping")
                            continue

                    # If the tool name isn't in the registry, try fuzzy matching
                    if t_name and not self.tools.get(t_name):
                        original_t_name = t_name
                        fuzzy = _fuzzy_match_tool_name(t_name, self.tools)
                        if self.debug:
                            print(f"    native fuzzy_match({t_name!r}) -> {fuzzy!r}")
                        if fuzzy:
                            # Handle echo -> shell: synthesize proper command
                            if fuzzy == "shell" and original_t_name.lower() in ("echo", "print", "say"):
                                text_val = (
                                    t_args.get("text") or t_args.get("value") or
                                    t_args.get("message") or t_args.get("content") or
                                    t_args.get("input") or t_args.get("arg") or ""
                                )
                                if text_val:
                                    t_args = {"command": f"echo {text_val}"}
                                    if self.debug:
                                        print(f"    shell: synthesized 'echo' command from text={text_val!r}")
                            t_name = fuzzy
                        else:
                            if self.debug:
                                print(f"    unknown tool {t_name!r}, skipping")
                            continue

                    # Normalize arguments with tool-specific aliases
                    t_args = _normalize_args(t_args, self.tools.get(t_name), t_name)
                    
                    # Try to synthesize missing required arguments
                    t_args = _synthesize_missing_args(t_name, t_args, user_input, _successful_results, self.tools)

                    # If the tool resolved to python_repl but 'code' arg is missing,
                    # try to reconstruct it from common alternative arg names the model
                    # may have used (value, expression, script, command, query).
                    if t_name == "python_repl" and not t_args.get("code"):
                        candidate = (
                            t_args.get("value") or t_args.get("expression") or
                            t_args.get("script") or t_args.get("command") or
                            t_args.get("query") or ""
                        )
                        if candidate:
                            # Wrap bare expressions so they produce visible output
                            code = candidate if "\n" in candidate or candidate.strip().startswith("print") \
                                else f"print({candidate})"
                            t_args = {"code": code}
                            if self.debug:
                                print(f"    python_repl code reconstructed: {code!r}")
                        else:
                            if self.debug:
                                print(f"    python_repl with no recoverable code, skipping")
                            continue
                    
                    # If python_repl code is provided but is a bare expression without print(),
                    # wrap it so we get visible output
                    if t_name == "python_repl" and t_args.get("code"):
                        code = t_args["code"]
                        # Check if it's a bare expression (single line, no print, no assignment)
                        if (
                            "\n" not in code.strip()
                            and not code.strip().startswith("print(")
                            and not "=" in code  # not an assignment
                            and not code.strip().startswith("import")  # not an import
                            and not code.strip().startswith("from")  # not a from import
                            and not code.strip().startswith("def ")  # not a function def
                            and not code.strip().startswith("class ")  # not a class def
                        ):
                            wrapped_code = f"print({code.strip()})"
                            t_args["code"] = wrapped_code
                            if self.debug:
                                print(f"    python_repl: wrapped bare expression: {code!r} -> {wrapped_code!r}")

                    t_args = _fix_calculator_args(t_name, t_args, user_input, _successful_results)
                    # Redirect to calculator with the correct expression.
                    if (
                        t_name != "calculator"
                        and self.tools.get("calculator")
                        and _successful_results
                    ):
                        q_lower = user_input.lower()
                        last_result = _strip_tool_prefix(_successful_results[-1])
                        try:
                            last_num = float(last_result)
                            redirect_expr = None
                            if "sqrt" in q_lower or "square root" in q_lower:
                                redirect_expr = f"sqrt({last_num:.0f})"
                            if redirect_expr:
                                if self.debug:
                                    print(f"    redirecting wrong tool {t_name!r} → calculator({redirect_expr!r})")
                                t_name = "calculator"
                                t_args = {"expression": redirect_expr}
                        except (ValueError, TypeError):
                            pass

                    # If _fix_calculator_args flagged this as redundant, skip the call
                    if t_args.pop("_redundant", False):
                        prior = t_args.pop("_prior_result", "")
                        if self.debug:
                            print(f"    skipping redundant {t_name} call (prior={prior!r})")
                        # Record the assistant turn with the original raw calls before feeding result
                        self.memory.add_assistant(content or "", tool_calls=tool_calls_raw)
                        self.memory.add_tool_result(t_name, prior)
                        _successful_results.append(f"{t_name} → {prior}")
                        continue

                    # Strip any internal bookkeeping keys before invoking
                    t_args.pop("_prior_result", None)

                    # Skip if tool name is empty or whitespace only
                    if not t_name or not t_name.strip():
                        continue

                    _tool_call_counts[t_name] = _tool_call_counts.get(t_name, 0) + 1

                    # Enforce the same hard ceilings as the JSON-fallback path
                    total_calls = sum(_tool_call_counts.values())
                    if _tool_call_counts[t_name] > _max_calls_per_tool or total_calls > _max_total_tool_calls:
                        final_answer = self._synthesize(user_input, _successful_results)
                        final_step = StepResult(type="final", content=final_answer, elapsed_ms=elapsed)
                        run.steps.append(final_step)
                        self._emit(final_step)
                        run.final_answer = final_answer
                        break

                    # Build a corrected tool_calls entry reflecting the (possibly redirected) tool
                    corrected_tc = {"function": {"name": t_name, "arguments": t_args}}
                    self.memory.add_assistant(content or "", tool_calls=[corrected_tc])

                    call_step = StepResult(
                        type="tool_call",
                        content=f"{t_name}({t_args})",
                        tool_name=t_name,
                        tool_args=t_args,
                        elapsed_ms=elapsed,
                    )
                    run.steps.append(call_step)
                    self._emit(call_step)

                    result = self.tools.invoke(t_name, t_args)
                    result_str = str(result)

                    result_step = StepResult(type="tool_result", content=result_str, tool_name=t_name)
                    run.steps.append(result_step)
                    self._emit(result_step)
                    self.memory.add_tool_result(t_name, result_str)

                    if not result_str.startswith("[Tool error]"):
                        _successful_results.append(f"{t_name} → {result_str}")
                        _successful_tools.add(t_name)

                continue  # back to top of while loop after processing all tool calls

            # ── Immediate synthesize after successful tool result ───────────── #
            # Prevents small models re-invoking tools when the answer is in hand.
            # Triggered when: a tool succeeded AND the query is simple (date, math, etc.)
            if _successful_results and _is_simple_answered_query(user_input, _successful_results):
                final_answer = self._synthesize(user_input, _successful_results)
                final_step = StepResult(type="final", content=final_answer, elapsed_ms=elapsed)
                run.steps.append(final_step)
                self._emit(final_step)
                run.final_answer = final_answer
                break

            # Some models (e.g. llama3.2:1b) output JSON in the message body
            # instead of using the tool_calls field.
            # Skip tool parsing for simple greetings to avoid false positives
            if self._native_tools and not tool_calls_raw and self.tools.all() and content:
                # Debug output
                if self.debug:
                    print(f"\n  🔍 DEBUG: JSON fallback triggered")
                    print(f"    content[:100]: {content[:100]!r}")

                t_name, t_args = _parse_json_tool_call(content, debug=self.debug)
                
                if self.debug:
                    print(f"    parsed JSON: name={t_name!r}, args={t_args!r}")
                
                # If JSON parsing failed or gave malformed output, try to extract from malformed content
                if t_name is None or not self.tools.get(t_name):
                    # Check if this looks like a schema dump
                    if _looks_like_tool_schema_dump(content):
                        if self.debug:
                            print(f"    detected schema dump, trying to extract tool...")
                        available_tools = [t.name for t in self.tools.all()]
                        extracted_name, extracted_args = _try_extract_tool_from_malformed(content, available_tools)
                        if extracted_name:
                            t_name = extracted_name
                            t_args = extracted_args or {}
                            if self.debug:
                                print(f"    extracted from malformed: name={t_name!r}")
                
                # If no JSON tool call found, check for Python code block
                # This handles when model outputs code directly instead of JSON
                if t_name is None and "python_repl" in [t.name for t in self.tools.all()]:
                    extracted_code = _extract_python_code(content)
                    if extracted_code:
                        if self.debug:
                            print(f"    extracted Python code block ({len(extracted_code)} chars)")
                        t_name = "python_repl"
                        t_args = {"code": extracted_code}
                
                # Skip if tool name is empty or whitespace only
                if not t_name or not t_name.strip():
                    t_name = None
                    
                # Try fuzzy matching if exact tool name doesn't exist
                if t_name and t_args is not None and not self.tools.get(t_name):
                    original_t_name = t_name
                    fuzzy_name = _fuzzy_match_tool_name(t_name, self.tools)
                    if self.debug:
                        print(f"    fuzzy_match({t_name!r}) -> {fuzzy_name!r}")
                    if fuzzy_name:
                        # If the original name looked like a math expression (e.g. "sqrt(144)"),
                        # use it directly as the calculator expression — it's more complete
                        # than whatever the model placed in the arguments field.
                        code_indicators = ["(", ")", "+", "-", "*", "/"]
                        if fuzzy_name == "calculator" and any(c in original_t_name for c in code_indicators):
                            t_args = {"expression": original_t_name}
                        elif fuzzy_name == "calculator" and original_t_name.lower() in ("sqrt", "square", "root", "squareroot"):
                            # Model called "sqrt" as a tool - synthesize calculator expression
                            val = (
                                t_args.get("value") or t_args.get("number") or
                                t_args.get("n") or t_args.get("x") or
                                t_args.get("input") or t_args.get("arg") or
                                t_args.get("expression") or ""
                            )
                            if val:
                                t_args = {"expression": f"sqrt({val})"}
                                if self.debug:
                                    print(f"    calculator: synthesized sqrt expression from value={val!r}")
                        elif fuzzy_name == "python_repl" and any(c in original_t_name for c in code_indicators):
                            if not t_args.get("code"):
                                code = original_t_name if original_t_name.strip().startswith("print") \
                                    else f"print({original_t_name})"
                                t_args = {"code": code}
                        # Handle echo -> shell: synthesize proper command
                        elif fuzzy_name == "shell" and original_t_name.lower() in ("echo", "print", "say"):
                            # Model called "echo" as a tool - synthesize shell command
                            text_val = (
                                t_args.get("text") or t_args.get("value") or
                                t_args.get("message") or t_args.get("content") or
                                t_args.get("input") or t_args.get("arg") or
                                t_args.get("string") or ""
                            )
                            if text_val:
                                t_args = {"command": f"echo {text_val}"}
                                if self.debug:
                                    print(f"    shell: synthesized 'echo' command from text={text_val!r}")
                        t_name = fuzzy_name

                # If python_repl was resolved but 'code' is missing, recover from alt arg names
                if t_name == "python_repl" and t_args is not None and not t_args.get("code"):
                    candidate = (
                        t_args.get("value") or t_args.get("expression") or
                        t_args.get("script") or t_args.get("command") or
                        t_args.get("query") or ""
                    )
                    if candidate:
                        code = candidate if "\n" in candidate or candidate.strip().startswith("print") \
                            else f"print({candidate})"
                        t_args = {"code": code}
                        if self.debug:
                            print(f"    python_repl code reconstructed from alt arg: {code!r}")
                
                if self.debug:
                    print(f"    final: name={t_name!r}, tool_exists={self.tools.get(t_name) is not None}")
                
                if t_name and t_args is not None and self.tools.get(t_name):
                    # Normalize arguments with tool-specific aliases
                    t_args = _normalize_args(t_args, self.tools.get(t_name), t_name)
                    
                    # Try to synthesize missing required arguments
                    t_args = _synthesize_missing_args(t_name, t_args, user_input, _successful_results, self.tools)
                    
                    # Handle empty args for python_repl - provide default code for date/time queries ONLY
                    if t_name == "python_repl" and not t_args.get("code"):
                        q_lower = user_input.lower()
                        # Only synthesize for actual date/time queries
                        if "date" in q_lower or "time" in q_lower or "today" in q_lower or "now" in q_lower:
                            if self.debug:
                                print(f"    python_repl with empty code for date/time query, synthesizing...")
                            if "date" in q_lower and "time" in q_lower:
                                t_args["code"] = "from datetime import datetime\nnow = datetime.now()\nprint(f\"Today is {now.strftime('%A, %B %d, %Y')} and the time is {now.strftime('%I:%M %p')}.\")"
                            elif "date" in q_lower or "today" in q_lower:
                                t_args["code"] = "from datetime import datetime\nprint(datetime.now().strftime('Today is %A, %B %d, %Y.'))"
                            elif "time" in q_lower:
                                t_args["code"] = "from datetime import datetime\nprint(datetime.now().strftime('The current time is %I:%M %p.'))"
                            else:
                                t_args["code"] = "from datetime import datetime\nprint(datetime.now())"
                            if self.debug:
                                print(f"    synthesized code: {t_args['code'][:50]}...")
                        else:
                            # For non-datetime queries, skip this tool call - let model provide proper args
                            if self.debug:
                                print(f"    python_repl with empty code but not a date/time query, skipping...")
                            continue

                    # Intercept repeat calls only when args are identical — the model is
                    # truly stuck. Different args = legitimate chained call (e.g. sqrt after **).
                    already_succeeded = t_name in _successful_tools
                    same_args = _last_tool_args.get(t_name) == t_args
                    if already_succeeded and same_args:
                        pending = [
                            t.name for t in self.tools.all()
                            if t.name not in _successful_tools
                        ]
                        if pending:
                            self.memory.add_user(
                                f"You already have the result for {t_name} with those arguments. "
                                f"Please call {pending[0]} next to complete the answer."
                            )
                        else:
                            # All tools done — synthesize now
                            final_answer = self._synthesize(user_input, _successful_results)
                            final_step = StepResult(type="final", content=final_answer, elapsed_ms=elapsed)
                            run.steps.append(final_step)
                            self._emit(final_step)
                            run.final_answer = final_answer
                            break
                        continue

                    _last_tool_args[t_name] = t_args

                    t_args = _fix_calculator_args(t_name, t_args, user_input, _successful_results)

                    # If _fix_calculator_args flagged this as redundant, skip the call
                    if t_args.pop("_redundant", False):
                        prior = t_args.pop("_prior_result", "")
                        if self.debug:
                            print(f"    skipping redundant {t_name} call (prior={prior!r})")
                        self.memory.add_tool_result(t_name, prior)
                        _successful_results.append(f"{t_name} → {prior}")
                        _successful_tools.add(t_name)
                        continue

                    # Strip any internal bookkeeping keys before invoking
                    t_args.pop("_prior_result", None)

                    _tool_call_counts[t_name] = _tool_call_counts.get(t_name, 0) + 1

                    # Hard ceiling — synthesize from what we already have
                    total_calls = sum(_tool_call_counts.values())
                    if _tool_call_counts[t_name] > _max_calls_per_tool or total_calls > _max_total_tool_calls:
                        final_answer = self._synthesize(user_input, _successful_results)
                        final_step = StepResult(type="final", content=final_answer, elapsed_ms=elapsed)
                        run.steps.append(final_step)
                        self._emit(final_step)
                        run.final_answer = final_answer
                        break

                    self.memory.add_assistant(content)

                    call_step = StepResult(
                        type="tool_call",
                        content=f"{t_name}({t_args})",
                        tool_name=t_name,
                        tool_args=t_args,
                        elapsed_ms=elapsed,
                    )
                    run.steps.append(call_step)
                    self._emit(call_step)

                    result = self.tools.invoke(t_name, t_args)
                    result_str = str(result)

                    result_step = StepResult(type="tool_result", content=result_str, tool_name=t_name)
                    run.steps.append(result_step)
                    self._emit(result_step)

                    if result_str.startswith("[Tool error]"):
                        # Feed rich error back so the model can self-correct
                        tool_obj = self.tools.get(t_name)
                        helpful_error = _generate_helpful_error_message(t_name, tool_obj, t_args, result_str)
                        self.memory.add_tool_result(t_name, helpful_error)
                    else:
                        _successful_results.append(f"{t_name} → {result_str}")
                        _successful_tools.add(t_name)
                        self.memory.add_tool_result(t_name, result_str)

                    # Nudge the model to answer once 2+ distinct tools have succeeded.
                    # Don't fire on repeats — those are intercepted above.
                    if not result_str.startswith("[Tool error]") and len(_successful_tools) >= 2:
                        results_so_far = "\n".join(f"- {r}" for r in _successful_results)
                        self.memory.add_user(
                            f"You have already gathered the following information:\n{results_so_far}\n\n"
                            f"Please now answer the original question in plain text using these results.\n"
                            f"Original question: {user_input}\n"
                            "Do NOT call any more tools."
                        )
                        nudge_response = self.client.chat(
                            model=self.model,
                            messages=self.memory.to_messages(),
                            options=self.model_options,
                        )
                        nudge_content = nudge_response.get("message", {}).get("content", "").strip()
                        # Only accept it if it doesn't look like another tool call
                        _, check_args = _parse_json_tool_call(nudge_content, debug=False)
                        if nudge_content and check_args is None:
                            final_step = StepResult(type="final", content=nudge_content, elapsed_ms=elapsed)
                            run.steps.append(final_step)
                            self._emit(final_step)
                            run.final_answer = nudge_content
                            self.memory.add_assistant(nudge_content)
                            break
                        else:
                            # Model still wants to use tools — remove nudge from memory and let it
                            self.memory._history.pop()
                    continue

            # ---- Native tool empty response retry ----------------------- #
            # When native tool model returns empty content with no tool calls,
            # send a direct instruction to use the appropriate tool
            if self._native_tools and not tool_calls_raw and not content and self.tools.all():
                retry_count = getattr(self, '_empty_retry_count', 0)
                
                # First retry: send a specific hint
                if retry_count == 0:
                    self._empty_retry_count = 1
                    if self.debug:
                        print(f"\n  🔍 DEBUG: Native tool returned empty, retrying with direct instruction")
                    
                    # Pick the most relevant tool based on the question
                    q_lower = user_input.lower()
                    tool_hint = ""
                    available_tools = [t.name for t in self.tools.all()]
                    
                    # Determine best tool and hint based on question keywords
                    # Use extracted expressions for more specific hints
                    if "calculator" in available_tools and any(kw in q_lower for kw in 
                        ["times", "multiply", "plus", "minus", "divided", "power", "sqrt", 
                         "square root", "what is", "calculate", "compute", " * ", " + ", " - ", " / "]):
                        # Try to extract the actual expression from the prompt
                        extracted_expr = _extract_calc_expression(user_input)
                        if extracted_expr:
                            tool_hint = f"You must call the calculator tool NOW. Use it with {{\"expression\": \"{extracted_expr}\"}}."
                            if self.debug:
                                print(f"    extracted expression: {extracted_expr}")
                        else:
                            tool_hint = "You must call the calculator tool. Use it with an expression like {\"expression\": \"15 * 8\"}."
                    elif "shell" in available_tools and any(kw in q_lower for kw in 
                        ["echo", "print", "directory", "pwd", "folder", "date", "time", "today"]):
                        if "echo" in q_lower or "print" in q_lower:
                            # Try to extract the actual text to echo
                            echo_text = _extract_echo_text(user_input)
                            if echo_text:
                                tool_hint = f"You must call the shell tool NOW. Use it with {{\"command\": \"echo {echo_text}\"}}."
                                if self.debug:
                                    print(f"    extracted echo text: {echo_text}")
                            else:
                                tool_hint = "You must call the shell tool. Use it with {\"command\": \"echo YourText\"}."
                        elif "directory" in q_lower or "pwd" in q_lower or "folder" in q_lower:
                            tool_hint = "You must call the shell tool. Use it with {\"command\": \"pwd\"}."
                        elif "date" in q_lower or "time" in q_lower or "today" in q_lower:
                            tool_hint = "You must call the shell tool. Use it with {\"command\": \"date\"}."
                        else:
                            tool_hint = "You must call the shell tool to answer this question."
                    elif "python_repl" in available_tools and any(kw in q_lower for kw in 
                        ["python", "code", "execute", "run"]):
                        tool_hint = "You must call the python_repl tool with the code to execute."
                    else:
                        # Generic hint - pick first available tool
                        first_tool = available_tools[0] if available_tools else ""
                        tool_hint = f"You must call the {first_tool} tool to answer this question."
                    
                    if tool_hint:
                        self.memory.add_assistant("")
                        self.memory.add_user(f"{tool_hint}\n\nOriginal question: {user_input}")
                        continue
                
                # Second retry: SYNTHESIZE the tool call directly
                # The model is too confused - we'll do it ourselves
                elif retry_count == 1:
                    self._empty_retry_count = 2
                    if self.debug:
                        print(f"\n  🔍 DEBUG: Second empty response, synthesizing tool call directly")
                    
                    q_lower = user_input.lower()
                    synthesized_tool = None
                    synthesized_args = {}
                    available_tools = [t.name for t in self.tools.all()]
                    
                    # Calculator synthesis
                    if "calculator" in available_tools:
                        expr = _extract_calc_expression(user_input)
                        if expr:
                            synthesized_tool = "calculator"
                            synthesized_args = {"expression": expr}
                            if self.debug:
                                print(f"    synthesized: calculator({expr})")
                    
                    # Shell synthesis
                    if not synthesized_tool and "shell" in available_tools:
                        if "echo" in q_lower or "print" in q_lower:
                            echo_text = _extract_echo_text(user_input)
                            if echo_text:
                                synthesized_tool = "shell"
                                synthesized_args = {"command": f"echo {echo_text}"}
                                if self.debug:
                                    print(f"    synthesized: shell(echo {echo_text})")
                        elif "directory" in q_lower or "pwd" in q_lower or "folder" in q_lower:
                            synthesized_tool = "shell"
                            synthesized_args = {"command": "pwd"}
                        elif "date" in q_lower or "time" in q_lower or "today" in q_lower:
                            synthesized_tool = "shell"
                            synthesized_args = {"command": "date"}
                    
                    # If we synthesized a tool call, execute it
                    if synthesized_tool and synthesized_args:
                        t_name = synthesized_tool
                        t_args = synthesized_args
                        
                        # Record the synthesized call
                        call_step = StepResult(
                            type="tool_call",
                            content=f"{t_name}({t_args})",
                            tool_name=t_name,
                            tool_args=t_args,
                            elapsed_ms=elapsed,
                        )
                        run.steps.append(call_step)
                        self._emit(call_step)
                        
                        # Execute the tool
                        result = self.tools.invoke(t_name, t_args)
                        result_str = str(result)
                        
                        result_step = StepResult(type="tool_result", content=result_str, tool_name=t_name)
                        run.steps.append(result_step)
                        self._emit(result_step)
                        
                        _successful_results.append(f"{t_name} → {result_str}")
                        _successful_tools.add(t_name)
                        
                        # Synthesize the final answer
                        final_answer = self._synthesize(user_input, _successful_results)
                        final_step = StepResult(type="final", content=final_answer, elapsed_ms=elapsed)
                        run.steps.append(final_step)
                        self._emit(final_step)
                        run.final_answer = final_answer
                        break
                    
                    # If we couldn't synthesize, give up gracefully
                    if self.debug:
                        print(f"    could not synthesize tool call, giving up")
                    run.final_answer = ""
                    break

            # ---- ReAct text parsing ---------------------------------- #
            if not self._native_tools and self.tools.all():
                thought, t_name, t_args, final_answer = _parse_react(content)
                
                # Debug: show what ReAct parsing extracted
                if self.debug:
                    print(f"\n  🔍 DEBUG: ReAct parsing result")
                    print(f"    thought={thought!r}")
                    print(f"    t_name={t_name!r}")
                    print(f"    t_args={t_args!r}")
                    print(f"    final_answer={final_answer!r}")

                # Also try JSON tool call format (BitNet, some small models)
                # Models may output {"name": "tool", "arguments": {...}} instead of ReAct format
                if not t_name and not final_answer:
                    json_name, json_args = _parse_json_tool_call(content, debug=self.debug)
                    if json_name:
                        t_name = json_name
                        t_args = json_args
                        if self.debug:
                            print(f"    ReAct path: parsed JSON tool call: name={t_name!r}, args={t_args!r}")

                # Try Python code block detection (code-focused models like qwen2.5-coder)
                # If model writes ```python code blocks, execute them via python_repl
                if not t_name and not final_answer:
                    python_code = _extract_python_code(content)
                    if python_code and self.tools.get("python_repl"):
                        t_name = "python_repl"
                        t_args = {"code": python_code}
                        if self.debug:
                            print(f"    ReAct path: detected Python code block, using python_repl")

                # Format reminder: if model didn't use ReAct format, remind it once
                # This helps code-focused models like qwen2.5-coder that default to Python blocks
                # Only send on FIRST response (before any tool calls) to avoid confusion
                if not t_name and not final_answer and not thought:
                    # Only send reminder if no tools have been called yet
                    if not _successful_results and not hasattr(self, '_format_reminder_sent'):
                        self._format_reminder_sent = True
                        if self.debug:
                            print(f"\n  🔍 DEBUG: Model didn't use ReAct format, sending reminder")
                        # Re-prompt with format reminder - SHORT and DIRECT
                        self.memory.add_assistant(content)
                        tool_names = [t.name for t in self.tools.all()]
                        # Get tool-specific arg name hint
                        first_tool = self.tools.all()[0] if self.tools.all() else None
                        arg_hint = "input"
                        if first_tool and first_tool.params:
                            arg_hint = first_tool.params[0].name  # params is list[ToolParam]
                        # Include the ORIGINAL question to prevent model from using example values
                        reminder = (
                            f"Answer this question: {user_input}\n\n"
                            f"Use this format:\n"
                            f"Action: {tool_names[0]}\n"
                            f"Action Input: {{\"{arg_hint}\": \"<your calculation>\"}}"
                        )
                        self.memory.add_user(reminder)
                        continue  # Let the model try again

                if thought:
                    step = StepResult(type="thought", content=thought, elapsed_ms=elapsed)
                    run.steps.append(step)
                    self._emit(step)

                if t_name and t_name.strip() and t_args is not None:
                    # Check if tool exists, try fuzzy matching if not
                    if not self.tools.get(t_name):
                        original_t_name = t_name
                        fuzzy_name = _fuzzy_match_tool_name(t_name, self.tools)
                        if self.debug:
                            print(f"    ReAct fuzzy_match({t_name!r}) -> {fuzzy_name!r}")
                        if fuzzy_name:
                            # Handle sqrt -> calculator: synthesize proper expression
                            if fuzzy_name == "calculator" and original_t_name.lower() in ("sqrt", "square", "root", "squareroot"):
                                val = (
                                    t_args.get("value") or t_args.get("number") or
                                    t_args.get("n") or t_args.get("x") or
                                    t_args.get("input") or t_args.get("arg") or
                                    t_args.get("expression") or ""
                                )
                                if val:
                                    t_args = {"expression": f"sqrt({val})"}
                                    if self.debug:
                                        print(f"    calculator: synthesized sqrt expression from value={val!r}")
                            # Handle echo -> shell: synthesize proper command
                            elif fuzzy_name == "shell" and original_t_name.lower() in ("echo", "print", "say"):
                                text_val = (
                                    t_args.get("text") or t_args.get("value") or
                                    t_args.get("message") or t_args.get("content") or
                                    t_args.get("input") or t_args.get("arg") or ""
                                )
                                if text_val:
                                    t_args = {"command": f"echo {text_val}"}
                                    if self.debug:
                                        print(f"    shell: synthesized 'echo' command from text={text_val!r}")
                            t_name = fuzzy_name
                        else:
                            if self.debug:
                                print(f"    Unknown tool {t_name!r}, skipping")
                            t_name = None
                    
                    if t_name:
                        t_args = _normalize_args(t_args, self.tools.get(t_name), t_name)
                        
                        # Try to synthesize missing required arguments
                        t_args = _synthesize_missing_args(t_name, t_args, user_input, _successful_results, self.tools)
                        
                        _tool_call_counts[t_name] = _tool_call_counts.get(t_name, 0) + 1

                        call_step = StepResult(
                            type="tool_call",
                            content=content,
                            tool_name=t_name,
                            tool_args=t_args,
                            elapsed_ms=elapsed,
                        )
                        run.steps.append(call_step)
                        self._emit(call_step)

                        result = self.tools.invoke(t_name, t_args)
                        result_str = str(result)

                        result_step = StepResult(type="tool_result", content=result_str, tool_name=t_name)
                        run.steps.append(result_step)
                        self._emit(result_step)

                        if not result_str.startswith("[Tool error]"):
                            _successful_results.append(f"{t_name} → {result_str}")

                        observation = content + f"\nObservation: {result_str}\n"
                        self.memory.add_assistant(observation)
                        continue

                if final_answer:
                    final_step = StepResult(type="final", content=final_answer, elapsed_ms=elapsed)
                    run.steps.append(final_step)
                    self._emit(final_step)
                    run.final_answer = final_answer
                    self.memory.add_assistant(content)
                    break

            # ---- Plain response (no tools or tool loop ended) -------- #
            # Native tool model answered in plain text after only 1 tool call.
            # If the original question likely needs more steps, nudge it to
            # call the next tool rather than guessing from memory.
            total_calls = sum(_tool_call_counts.values())
            if (
                self._native_tools
                and self.tools.all()
                and _successful_results
                and total_calls == 1
                and not tool_calls_raw
            ):
                results_so_far = "\n".join(f"- {r}" for r in _successful_results)

                # Build a more specific hint when the prior result is a number and
                # the user question implies a chained calculation (e.g. sqrt after **).
                extra_hint = ""
                q_lower = user_input.lower()
                last_result = _strip_tool_prefix(_successful_results[-1])
                try:
                    last_num = float(last_result)
                    if "sqrt" in q_lower or "square root" in q_lower:
                        extra_hint = (
                            f"\nThe user asked for the square root of the previous result. "
                            f"Call calculator with expression=\"sqrt({last_num:.0f if last_num == int(last_num) else last_num})\". "
                            f"Do NOT call any other tool."
                        )
                except (ValueError, TypeError):
                    pass

                self.memory.add_assistant(content)
                self.memory.add_user(
                    f"You have gathered so far:\n{results_so_far}\n\n"
                    f"The original question was: {user_input}\n\n"
                    "If the question requires further calculation, call the correct tool with the "
                    "correct next expression using the result above as input (do NOT pass "
                    "the raw result as the expression — compute something new with it). "
                    "Otherwise give your final answer in plain text."
                    + extra_hint
                )
                continue

            # Detect: model output looks like a JSON tool schema even though
            # no tools are defined. Re-prompt once asking for plain text.
            # Also handle case where we have successful results but model output JSON.
            if _looks_like_tool_schema(content):
                if _successful_results:
                    # We have tool results - use them instead of the JSON
                    clean_results = [_strip_tool_prefix(r) for r in _successful_results]
                    content = clean_results[0] if len(clean_results) == 1 else "\n".join(f"- {r}" for r in clean_results)
                    if self.debug:
                        print(f"    using tool result as final answer: {content[:50]}...")
                elif not self.tools.all():
                    self.memory.add_assistant(content)
                    self.memory.add_user(
                        "Please answer in plain text only. "
                        "Do not output JSON or function call syntax."
                    )
                    retry = self.client.chat(
                        model=self.model,
                        messages=self.memory.to_messages(),
                        options=self.model_options,
                    )
                    content = retry.get("message", {}).get("content", "").strip() or content
                    self.memory._history.pop()   # remove the nudge from memory
                    self.memory._history.pop()   # remove the bad assistant turn

            # ---- Hallucinated tool mention fallback ---- #
            # Model mentions a tool in its response but didn't actually call it.
            # E.g., "To calculate the division of 100 by 4, we can use the calculator tool..."
            # This is common with small native-tool models that talk about tools but don't call them.
            if (
                self._native_tools
                and self.tools.all()
                and not _successful_results
                and not tool_calls_raw
                and content
            ):
                content_lower = content.lower()
                available_tools = [t.name for t in self.tools.all()]
                synthesized_tool = None
                synthesized_args = {}
                
                # Check if content mentions a tool but didn't call it
                mentions_calculator = "calculator" in content_lower and "calculator" in available_tools
                mentions_shell = "shell" in content_lower and "shell" in available_tools
                
                if mentions_calculator or mentions_shell:
                    if self.debug:
                        print(f"\n  🔍 DEBUG: Model mentions tool but didn't call it, synthesizing...")
                    
                    # Calculator synthesis
                    if mentions_calculator:
                        expr = _extract_calc_expression(user_input)
                        if expr:
                            synthesized_tool = "calculator"
                            synthesized_args = {"expression": expr}
                            if self.debug:
                                print(f"    synthesized: calculator({expr})")
                    
                    # Shell synthesis
                    if not synthesized_tool and mentions_shell:
                        q_lower = user_input.lower()
                        if "echo" in q_lower or "print" in q_lower:
                            echo_text = _extract_echo_text(user_input)
                            if echo_text:
                                synthesized_tool = "shell"
                                synthesized_args = {"command": f"echo {echo_text}"}
                                if self.debug:
                                    print(f"    synthesized: shell(echo {echo_text})")
                        elif "directory" in q_lower or "pwd" in q_lower or "folder" in q_lower:
                            synthesized_tool = "shell"
                            synthesized_args = {"command": "pwd"}
                        elif "date" in q_lower or "time" in q_lower or "today" in q_lower:
                            synthesized_tool = "shell"
                            synthesized_args = {"command": "date"}
                    
                    # Execute synthesized tool call
                    if synthesized_tool and synthesized_args:
                        t_name = synthesized_tool
                        t_args = synthesized_args
                        
                        call_step = StepResult(
                            type="tool_call",
                            content=f"{t_name}({t_args})",
                            tool_name=t_name,
                            tool_args=t_args,
                            elapsed_ms=elapsed,
                        )
                        run.steps.append(call_step)
                        self._emit(call_step)
                        
                        result = self.tools.invoke(t_name, t_args)
                        result_str = str(result)
                        
                        result_step = StepResult(type="tool_result", content=result_str, tool_name=t_name)
                        run.steps.append(result_step)
                        self._emit(result_step)
                        
                        _successful_results.append(f"{t_name} → {result_str}")
                        _successful_tools.add(t_name)
                        
                        # Synthesize the final answer from the result
                        final_answer = self._synthesize(user_input, _successful_results)
                        final_step = StepResult(type="final", content=final_answer, elapsed_ms=elapsed)
                        run.steps.append(final_step)
                        self._emit(final_step)
                        run.final_answer = final_answer
                        break

            # Clean JSON from final answer if needed
            # Use successful tool results as fallback if available
            if _successful_results:
                clean_results = [_strip_tool_prefix(r) for r in _successful_results]
                fallback_text = clean_results[0] if len(clean_results) == 1 else "\n".join(f"- {r}" for r in clean_results)
            else:
                fallback_text = content
            
            if self.debug:
                print(f"\n  🔍 DEBUG: Final answer processing")
                print(f"    content (before clean)={content!r}")
                print(f"    fallback_text={fallback_text!r}")
            
            content = self._clean_json_from_response(content, fallback_text)
            
            if self.debug:
                print(f"    content (after clean)={content!r}")

            final_step = StepResult(type="final", content=content, elapsed_ms=elapsed)
            run.steps.append(final_step)
            self._emit(final_step)
            run.final_answer = content
            self.memory.add_assistant(content)
            break

        else:
            # max_steps hit — try to salvage with synthesis
            run.success = False
            run.error = f"Exceeded max_steps ({self.max_steps})"
            if _successful_results:
                run.final_answer = self._synthesize(user_input, _successful_results)

        run.total_ms = (time.perf_counter() - t0) * 1000
        return run

    def _synthesize(self, user_input: str, results: list[str]) -> str:
        """
        Called when the model is stuck in a tool loop but we have good results.
        Makes one clean LLM call asking it to summarize what was found.
        """
        if not results:
            return "I was unable to complete this task with the available tools."

        results_text = "\n".join(f"- {r}" for r in results)
        
        # For simple numeric results, use directly without LLM synthesis
        # This prevents the model from repeating its pre-tool-call wrong answer
        if len(results) == 1:
            r_clean = _strip_tool_prefix(results[0])
            if self.debug:
                print(f"    synthesize: checking if numeric: '{r_clean}'")
            # Check if result is just a number (possibly with decimal)
            try:
                num = float(r_clean)
                # It's a number - construct a simple answer
                if self.debug:
                    print(f"    synthesize: using numeric result directly: {num}")
                # Return just the number as string - test expects this
                return r_clean
            except (ValueError, TypeError) as e:
                if self.debug:
                    print(f"    synthesize: not numeric: {e}")
                pass
        
        # Check if any result already looks like a complete answer
        # (starts with common answer patterns and is reasonably short)
        for r in results:
            r_clean = _strip_tool_prefix(r)
            answer_patterns = (
                r_clean.startswith("Today is ") or
                r_clean.startswith("The current time is ") or
                r_clean.startswith("The answer is ") or
                r_clean.startswith("Result: ")
            )
            if answer_patterns and len(r_clean) < 200:
                # This result is already a good answer, use it directly
                if self.debug:
                    print(f"    synthesize: using direct result: {r_clean[:50]}...")
                return r_clean

        if self.debug:
            print(f"    synthesize: making LLM call to summarize {len(results)} results...")
        
        # For synthesis, don't include the model's potentially wrong pre-tool responses
        # Just use the system prompt and the synthesis request
        synthesis_messages = [
            {"role": "system", "content": self.memory.system_prompt},
            {"role": "user", "content": (
                f"You have already gathered the following information using your tools:\n"
                f"{results_text}\n\n"
                f"Please now answer the original question directly using these results. "
                f"Do not call any more tools. Original question: {user_input}"
            )},
        ]
        try:
            response = self.client.chat(
                model=self.model,
                messages=synthesis_messages,
                options=self.model_options,
            )
            content = response.get("message", {}).get("content", "").strip()
            # Clean up any JSON tool schemas from the response
            content = self._clean_json_from_response(content, results_text)
            return content or results_text
        except Exception:
            return results_text

    def _clean_json_from_response(self, content: str, fallback: str = "") -> str:
        """
        Remove JSON tool-call schemas from a response.
        Small models sometimes output tool schemas instead of plain text answers.
        Returns the fallback if the content is just a tool schema or clearly malformed.
        """
        if not content:
            return fallback
        
        # Check for clearly malformed/too-short responses
        # Just backticks, empty after stripping, or very short garbage
        stripped = content.strip()
        if len(stripped) < 3:
            return fallback if fallback else content
        if stripped in ("```", "``", "`", "```json", "```python"):
            return fallback if fallback else content
        # Just markdown fence with nothing inside
        if stripped.startswith("```") and stripped.endswith("```") and len(stripped) < 10:
            return fallback if fallback else content
        
        # Check if this looks like a tool schema JSON
        if not _looks_like_tool_schema(content):
            return content
        
        # If the entire response is just a tool schema, use the fallback
        # (which should contain actual results)
        try:
            cleaned = re.sub(r"```(?:json)?", "", content).strip().rstrip("`").strip()
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                obj = json.loads(cleaned[start:end + 1])
                # If it's a tool call schema (has name + arguments/parameters)
                if "name" in obj and ("arguments" in obj or "parameters" in obj):
                    # This is just a tool call, not an answer - use fallback
                    return fallback if fallback else content
        except (json.JSONDecodeError, TypeError):
            pass
        
        return content

    def chat(self, user_input: str) -> str:
        """Convenience wrapper — returns just the final answer string."""
        return self.run(user_input).final_answer

    def reset(self):
        """Clear conversation history (preserves system prompt)."""
        self.memory.clear()

    # ------------------------------------------------------------------ #
    #  Streaming                                                           #
    # ------------------------------------------------------------------ #

    def stream(self, user_input: str) -> Iterator[str]:
        """
        Yield text tokens as they arrive (no tool use in streaming mode).
        Suitable for simple Q&A agents where you want live output.

        Note: Tools registered on this agent are NOT invoked during streaming.
        Use agent.run() for full tool-calling support.
        """
        if self.tools.all() and self.debug:
            print(
                f"  ⚠ stream() called but {len(self.tools.all())} tool(s) are registered. "
                "Tools are not invoked in streaming mode — use agent.run() instead."
            )
        self.memory.add_user(user_input)
        chunks = self.client.chat(
            model=self.model,
            messages=self.memory.to_messages(),
            stream=True,
            options=self.model_options,
        )
        full = ""
        for chunk in chunks:
            # Handle both Ollama (dict) and BitNet (string) streaming formats
            if isinstance(chunk, dict):
                token = chunk.get("message", {}).get("content", "")
            elif isinstance(chunk, str):
                token = chunk
            else:
                token = str(chunk) if chunk else ""
            full += token
            yield token
        self.memory.add_assistant(full)

    # ------------------------------------------------------------------ #
    #  Internal                                                            #
    # ------------------------------------------------------------------ #

    def _emit(self, step: StepResult):
        if self.on_step:
            self.on_step(step)