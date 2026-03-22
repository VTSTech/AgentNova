"""
AgentNova R02.4 — Agent Mode Helpers

Shared data classes, regex patterns, and helper functions for agent execution.
This module contains all the small-model handling logic extracted from agent.py.

Used by:
- agent.py: Main Agent class
- cli.py: Step callbacks
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable, Any

from .tools import ToolRegistry, Tool, ToolParam
from .memory import Memory


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class StepResult:
    """A single step in an agent run."""
    type: str  # "thought", "tool_call", "tool_result", "final"
    content: str
    tool_name: str | None = None
    tool_args: dict | None = None
    elapsed_ms: float = 0.0


@dataclass
class AgentRun:
    """Result of an agent run."""
    final_answer: str = ""
    steps: list[StepResult] = field(default_factory=list)
    total_ms: float = 0.0
    success: bool = True
    error: str | None = None


# ============================================================
# TOOL ARGUMENT ALIASES
# ============================================================
# Small models often hallucinate argument names. This maps common
# hallucinations to the correct parameter names.

TOOL_ARG_ALIASES = {
    "calculator": {
        "a": "expression", "b": "expression", "x": "expression", "y": "expression",
        "num": "expression", "number": "expression", "value": "expression",
        "input": "expression", "formula": "expression", "math": "expression",
        "expr": "expression", "calc": "expression", "result": "expression",
        "base": "_combine_power", "exponent": "_combine_power", "power": "_combine_power",
        "n": "_combine_power", "p": "_combine_power", "exp": "_combine_power",
    },
    "python_repl": {
        "code": "code",
        "script": "code", "cmd": "code", "command": "code",
        "python": "code", "py": "code", "exec": "code", "execute": "code",
        "expression": "code", "expr": "code", "statement": "code",
        "program": "code", "source": "code", "input": "code",
    },
    "write_file": {
        "path": "path",
        "filepath": "path", "file_path": "path", "filename": "path",
        "file": "path", "dest": "path", "destination": "path",
        "output_path": "path", "outputfile": "path", "location": "path",
        "content": "content",
        "data": "content", "text": "content", "body": "content",
        "output": "content", "string": "content", "value": "content",
        "write": "content", "output_data": "content",
    },
    "read_file": {
        "path": "path",
        "filepath": "path", "file_path": "path", "filename": "path",
        "file": "path", "input": "path", "source": "path", "location": "path",
    },
    "shell": {
        "command": "command",
        "cmd": "command", "exec": "command", "shell_cmd": "command",
        "bash": "command", "script": "command", "instruction": "command",
        "run": "command", "execute": "command", "op": "command",
        "text": "command", "input": "command", "arg": "command",
        "args": "command", "str": "command", "value": "command",
    },
    "web_search": {
        "query": "query",
        "search": "query", "q": "query", "term": "query", "search_query": "query",
        "keywords": "query", "text": "query", "input": "query",
    },
}


# ============================================================
# COMPILED REGEX PATTERNS
# ============================================================

_THOUGHT_RE = re.compile(r"Thought:\s*(.*?)(?=Action:|Final Answer:|$)", re.DOTALL | re.IGNORECASE)
_ACTION_RE = re.compile(
    r"Action:\s*[`\"']?(\w+)[`\"']?\s*\n?\s*Action Input:\s*(.*?)(?=\n\s*(?:Observation:|Thought:|Final Answer:|Action:|Example)|$)",
    re.DOTALL | re.IGNORECASE
)
_ACTION_SAME_LINE_RE = re.compile(
    r"Action:\s*[`\"']?(\w+)[`\"']?\s+Action Input:\s*(.*?)(?=\n\s*(?:Observation:|Thought:|Final Answer:|Action:|Example)|$)",
    re.DOTALL | re.IGNORECASE
)
_FINAL_RE = re.compile(r"Final Answer:\s*(.*?)$", re.DOTALL | re.IGNORECASE)
_PYTHON_CODE_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_REPETITION_RE = re.compile(r'(Final Answer:\s*[^\n]+)(\s*\1){2,}', re.IGNORECASE)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _strip_tool_prefix(result: str) -> str:
    """Strip 'tool_name → ' prefix from result."""
    if " → " in result:
        return result.split(" → ", 1)[1]
    return result


def _get_numeric_result(results: list[str]) -> str | None:
    """Get numeric result from tool results if available."""
    if not results:
        return None
    
    last_result = _strip_tool_prefix(results[-1])
    try:
        float(last_result)  # Check if it's numeric
        return last_result
    except (ValueError, TypeError):
        return None


def _synthesize_result(results: list[str], content: str) -> str:
    """Synthesize a final answer from tool results."""
    if not results:
        return content
    
    numeric = _get_numeric_result(results)
    if numeric:
        return numeric
    
    # Return last result stripped of prefix
    return _strip_tool_prefix(results[-1])


def _detect_and_fix_repetition(text: str) -> str:
    """
    Detect and fix repetitive output from small models.
    
    Some models get stuck in loops repeating the same phrase:
        "Final Answer: 120\nFinal Answer: 120\nFinal Answer: 120..."
    """
    if not text:
        return text
    
    # Fix "Final Answer:" repetition specifically
    match = _REPETITION_RE.search(text)
    if match:
        text = _REPETITION_RE.sub(r'\1', text)
    
    # Also detect and fix any line repeated 3+ times at the end
    lines = text.split('\n')
    if len(lines) >= 3:
        last_line = lines[-1].strip()
        if last_line:
            repeat_count = 1
            for i in range(len(lines) - 2, -1, -1):
                if lines[i].strip() == last_line:
                    repeat_count += 1
                else:
                    break
            
            if repeat_count >= 3:
                text = '\n'.join(lines[:-repeat_count + 1])
    
    return text


def _sanitize_model_json(text: str) -> str:
    """
    Fix common JSON mistakes made by small models before parsing.
    
    1. Python bool/None literals to JSON equivalents
    2. Python string concatenation in values
    3. Trailing commas before } or ]
    """
    # Python booleans / None
    text = re.sub(r':\s*True\b', ': true', text)
    text = re.sub(r':\s*False\b', ': false', text)
    text = re.sub(r':\s*None\b', ': null', text)
    text = re.sub(r'\[\s*True\b', '[true', text)
    text = re.sub(r'\[\s*False\b', '[false', text)
    text = re.sub(r'\[\s*None\b', '[null', text)
    
    # Python string concatenation: "literal" + anything -> "literal"
    text = re.sub(r'("(?:[^"\\]|\\.)*")\s*\+\s*[^,\'"}\]\n]+', r'\1', text)
    
    # Trailing commas before } or ]
    text = re.sub(r',\s*([}\]])', r'\1', text)
    
    return text


def _looks_like_tool_schema_dump(text: str) -> bool:
    """Detect when a model dumps the entire tool schema as text."""
    if not text:
        return False
    
    dump_indicators = [
        '{"function <nil>',
        '"type":"function"',
        '"parameters":{"type":"object"',
        '[{"type":',
        '"required":',
        '"properties":',
        'Search the web using DuckDuckGo',
        'Evaluate a mathematical expression',
        'Execute Python code',
        '{object <nil>',
    ]
    
    text_lower = text.lower()
    matches = sum(1 for indicator in dump_indicators if indicator.lower() in text_lower)
    
    return matches >= 2


def _extract_tool_from_json(obj: dict, debug: bool = False) -> tuple[str | None, dict | None]:
    """Extract tool name and args from a parsed JSON object."""
    name = obj.get("name") or obj.get("function")
    args = obj.get("arguments") or obj.get("parameters") or obj.get("args") or {}
    
    # Handle bare argument objects: {"expression": "..."} without name wrapper
    if not name and isinstance(obj, dict):
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
        return None, None
    
    return name, args


def _parse_json_tool_call(text: str, debug: bool = False) -> tuple[str | None, dict | None]:
    """
    Fallback for models that output tool calls as JSON text instead of ReAct format.
    
    Handles:
        ```json
        {"name": "calculator", "arguments": {"expression": "2+2"}}
        ```
    
    Also handles bare argument objects:
        ```json
        {"expression": "15 * 8"}
        ```
    """
    if _looks_like_tool_schema_dump(text):
        return None, None
    
    # Try to extract JSON from markdown code blocks
    code_block_pattern = re.compile(r'```(?:json)?[^\n]*\n(.*?)```', re.DOTALL)
    code_blocks = code_block_pattern.findall(text)
    
    for block in code_blocks:
        block = block.strip()
        if block.startswith('{'):
            json_str = _sanitize_model_json(block)
            try:
                obj = json.loads(json_str)
                result = _extract_tool_from_json(obj, debug)
                if result[0]:
                    return result
            except json.JSONDecodeError:
                continue
    
    # Fallback: find first JSON object
    start = text.find("{")
    if start == -1:
        return None, None
    
    depth = 0
    end = -1
    for i, ch in enumerate(text[start:], start):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end = i
                break
    
    if end == -1:
        return None, None
    
    json_str = _sanitize_model_json(text[start:end + 1])
    
    try:
        obj = json.loads(json_str)
    except json.JSONDecodeError:
        return None, None
    
    return _extract_tool_from_json(obj, debug)


def _extract_python_code(text: str) -> str | None:
    """Extract Python code from markdown code blocks."""
    match = _PYTHON_CODE_RE.search(text)
    if match:
        return match.group(1).strip()
    return None


def _parse_react(text: str) -> tuple[str | None, str | None, dict | None, str | None]:
    """
    Parse ReAct format text.
    
    Returns:
        (thought, tool_name, tool_args, final_answer)
    """
    text = _detect_and_fix_repetition(text)
    
    thought = None
    tool_name = None
    tool_args = None
    final_answer = None
    
    # Extract thought
    thought_match = _THOUGHT_RE.search(text)
    if thought_match:
        thought = thought_match.group(1).strip()
    
    # Extract action (try multiline first, then same-line format)
    action_match = _ACTION_RE.search(text)
    if not action_match:
        action_match = _ACTION_SAME_LINE_RE.search(text)
    
    if action_match:
        tool_name = action_match.group(1).strip()
        raw_args = action_match.group(2).strip()
        
        # Parse arguments
        if raw_args.startswith('{'):
            try:
                tool_args = json.loads(raw_args)
            except json.JSONDecodeError:
                # Try sanitizing first
                sanitized = _sanitize_model_json(raw_args)
                try:
                    tool_args = json.loads(sanitized)
                except json.JSONDecodeError:
                    tool_args = {"input": raw_args}
        else:
            tool_args = {"input": raw_args}
    
    # Extract final answer
    final_match = _FINAL_RE.search(text)
    if final_match:
        final_answer = final_match.group(1).strip()
    
    return thought, tool_name, tool_args, final_answer


def _normalize_args(args: dict, tool, tool_name: str = None) -> dict:
    """
    Normalize argument names using TOOL_ARG_ALIASES and type coercion.
    
    Small models often hallucinate argument keys. This function normalizes
    them using multiple strategies:
    1. Tool-specific alias mapping
    2. Exact match to real params
    3. Prefix/substring matching
    4. Type coercion (string -> int/float)
    """
    if not isinstance(args, dict):
        if args is None:
            return {}
        if isinstance(args, str):
            return {"input": args}
        return {}
    
    if tool is None:
        return args
    
    real_params = [p for p in tool.params]
    if not real_params:
        return args
    
    param_map = {p.name: p for p in real_params}
    normalized = {}
    power_parts = {}
    
    tool_aliases = TOOL_ARG_ALIASES.get(tool_name, {}) if tool_name else {}
    
    for key, val in args.items():
        key_lower = key.lower().replace("-", "_")
        target_param = None
        target_pname = None
        
        # Strategy 1: Tool-specific alias lookup
        if key_lower in tool_aliases:
            alias_target = tool_aliases[key_lower]
            if alias_target == "_combine_power":
                power_parts[key_lower] = val
                continue
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
        
        if target_pname is None:
            target_pname = key
        
        # Type coercion
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
    
    # Handle power operation combination
    if power_parts and "expression" in param_map:
        base = power_parts.get("base") or power_parts.get("value") or power_parts.get("x")
        exp = power_parts.get("exponent") or power_parts.get("power") or power_parts.get("n")
        
        if base is not None and exp is not None:
            normalized["expression"] = f"{base} ** {exp}"
        elif base is not None:
            normalized["expression"] = str(base)
    
    return normalized


def _synthesize_missing_args(tool_name: str, args: dict, user_input: str, prior_results: list[str], tools_registry) -> dict:
    """
    Try to fill in missing required arguments from context.
    Helps small models that call tools with incomplete arguments.
    """
    tool = tools_registry.get(tool_name) if tools_registry else None
    if tool is None:
        return args
    
    args = dict(args)
    required_params = {p.name for p in tool.params if p.required}
    missing = required_params - set(args.keys())
    
    if not missing:
        return args
    
    q_lower = user_input.lower()
    
    # Tool-specific synthesis
    if tool_name == "calculator" and "expression" in missing:
        numbers = re.findall(r'\d+\.?\d*', user_input)
        operators = re.findall(r'[+\-*/^]', user_input)
        
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
            expr_parts = []
            for i, num in enumerate(numbers):
                expr_parts.append(num)
                if i < len(operators):
                    expr_parts.append(operators[i])
            args["expression"] = " ".join(expr_parts)
        elif numbers:
            args["expression"] = numbers[0]
    
    elif tool_name == "python_repl" and "code" in missing:
        if "date" in q_lower and "time" in q_lower:
            args["code"] = "from datetime import datetime\nprint(datetime.now().strftime('Today is %A, %B %d, %Y and the time is %I:%M %p.'))"
        elif "date" in q_lower:
            args["code"] = "from datetime import datetime\nprint(datetime.now().strftime('Today is %A, %B %d, %Y.'))"
        elif "time" in q_lower:
            args["code"] = "from datetime import datetime\nprint(datetime.now().strftime('The current time is %I:%M %p.'))"
    
    elif tool_name == "shell" and "command" in missing:
        if "directory" in q_lower or "folder" in q_lower:
            args["command"] = "pwd"
        elif "files" in q_lower and "list" in q_lower:
            args["command"] = "ls"
    
    return args


# Word mappings for fuzzy tool name matching
_TOOL_WORD_MAPPINGS = {
    # Calculator-related
    "calculate": ["calculator", "python_repl"],
    "calc": ["calculator", "python_repl"],
    "math": ["calculator", "python_repl"],
    "compute": ["calculator", "python_repl"],
    "sqrt": ["calculator"],
    "power": ["calculator"],
    "multiply": ["calculator"],
    "divide": ["calculator"],
    "add": ["calculator"],
    "subtract": ["calculator"],
    "calculator": ["calculator"],
    
    # Shell-related
    "shell": ["shell"],
    "bash": ["shell"],
    "cmd": ["shell"],
    "command": ["shell"],
    "ls": ["shell"],
    "dir": ["shell"],
    "cat": ["shell"],
    "echo": ["shell"],
    "pwd": ["shell"],
    "grep": ["shell"],
    
    # Python
    "python": ["python_repl", "shell"],
    "repl": ["python_repl", "shell"],
    "code": ["python_repl", "shell"],
    "exec": ["python_repl", "shell"],
    
    # File I/O
    "read": ["read_file"],
    "write": ["write_file"],
    "file": ["read_file", "write_file"],
}


def _fuzzy_match_tool_name(hallucinated_name: str, tools_registry) -> str | None:
    """
    Match a hallucinated tool name to a real tool name.
    
    Examples:
        "calculate_expression" -> "calculator"
        "ls" -> "shell"
    """
    if tools_registry.get(hallucinated_name):
        return hallucinated_name
    
    real_names = [t.name for t in tools_registry.all()]
    lower_hallucinated = hallucinated_name.lower().replace("_", "")
    
    # Strategy 1: Substring match
    for real_name in real_names:
        lower_real = real_name.lower().replace("_", "")
        if lower_real in lower_hallucinated or lower_hallucinated in lower_real:
            return real_name
    
    # Strategy 2: Word mappings
    for keyword, tool_hints in _TOOL_WORD_MAPPINGS.items():
        if keyword in lower_hallucinated:
            for tool_hint in tool_hints:
                for real_name in real_names:
                    if tool_hint in real_name or real_name == tool_hint:
                        return real_name
    
    # Strategy 3: First 4 chars match
    for real_name in real_names:
        lower_real = real_name.lower()
        if len(lower_real) >= 4 and len(lower_hallucinated) >= 4:
            if lower_real[:4] == lower_hallucinated[:4]:
                return real_name
    
    return None


def _is_simple_query(text: str) -> bool:
    """Check if the query is simple enough for immediate synthesis."""
    lower = text.lower()
    simple_keywords = ["what is", "calculate", "compute", "sqrt", "date", "time"]
    return any(kw in lower for kw in simple_keywords) and len(text) < 60


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Data classes
    "StepResult",
    "AgentRun",
    # Constants
    "TOOL_ARG_ALIASES",
    # Parsing functions
    "_parse_react",
    "_parse_json_tool_call",
    "_extract_python_code",
    "_detect_and_fix_repetition",
    "_sanitize_model_json",
    # Helper functions
    "_strip_tool_prefix",
    "_get_numeric_result",
    "_synthesize_result",
    "_normalize_args",
    "_synthesize_missing_args",
    "_fuzzy_match_tool_name",
    "_is_simple_query",
    # Regex patterns (for direct use if needed)
    "_THOUGHT_RE",
    "_ACTION_RE",
    "_ACTION_SAME_LINE_RE",
    "_FINAL_RE",
    "_PYTHON_CODE_RE",
]