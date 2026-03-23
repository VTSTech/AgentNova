"""
⚛️ AgentNova R02.5 — Tool Parser
Regex patterns and functions for parsing tool calls from model output.

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

from __future__ import annotations

import json
import re

from .helpers import _detect_and_fix_repetition


# ------------------------------------------------------------------ #
#  Regex patterns for ReAct parsing                                   #
# ------------------------------------------------------------------ #

_THOUGHT_RE = re.compile(r"Thought:\s*(.*?)(?=Action:|Final Answer:|$)", re.DOTALL | re.IGNORECASE)
_ACTION_RE = re.compile(
    r"Action:\s*[`\"']?(\w+)[`\"']?\s*\n?\s*Action Input:\s*(.*?)(?=\n\s*(?:Observation:|Thought:|Final Answer:|Action:|Example)|$)",
    re.DOTALL | re.IGNORECASE
)
_ACTION_RE_SAMELINE = re.compile(
    r"Action:\s*[`\"']?(\w+)[`\"']?\s+Action Input:\s*(.*?)(?=\n\s*(?:Observation:|Thought:|Final Answer:|Action:|Example)|$)",
    re.DOTALL | re.IGNORECASE
)
_FINAL_RE = re.compile(r"Final Answer:\s*(.*?)$", re.DOTALL | re.IGNORECASE)
_PYTHON_CODE_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


# ------------------------------------------------------------------ #
#  JSON sanitization and extraction                                    #
# ------------------------------------------------------------------ #

def _sanitize_model_json(text: str) -> str:
    """
    Fix common JSON mistakes made by small (0.5b-3b) models before parsing.

    1. Python bool/None literals to JSON equivalents:
       True -> true,  False -> false,  None -> null

    2. Python string concatenation in values - keep only the string literal:
       "Today: " + datetime.now().strftime(...)  becomes  "Today: "

    3. Trailing commas before } or ] (technically invalid JSON)
    """
    text = re.sub(r':\s*True\b', ': true', text)
    text = re.sub(r':\s*False\b', ': false', text)
    text = re.sub(r':\s*None\b', ': null', text)
    text = re.sub(r'\[\s*True\b', '[true', text)
    text = re.sub(r'\[\s*False\b', '[false', text)
    text = re.sub(r'\[\s*None\b', '[null', text)
    text = re.sub(r'("(?:[^"\\]|\\.)*")\s*\+\s*[^,\'"}\]\n]+', r'\1', text)
    text = re.sub(r',\s*([}\]])', r'\1', text)

    return text


def _looks_like_tool_schema(text: str) -> bool:
    """
    Returns True if the text looks like the model outputting a JSON
    function-call schema rather than a real answer.
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
    """
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

    # Handle bare argument objects
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
        if debug:
            print(f"    _extract_tool_from_json: no name or args")
        return None, None

    # Detect if the 'name' field contains code instead of a tool name
    code_indicators = ["(", ")", "+", "-", "*", "/", "=", "[", "]", "print", "def ", "return"]
    if any(indicator in name for indicator in code_indicators):
        return name, args

    return name, args


def _parse_json_tool_call(text: str, debug: bool = False) -> tuple[str | None, dict | None]:
    """
    Fallback for models that output tool calls as JSON text instead of
    using the native tool_calls API field.
    
    Returns (tool_name, tool_args) or (None, None) if not found.
    """
    if _looks_like_tool_schema_dump(text):
        if debug:
            print(f"    _parse_json_tool_call: skipping - looks like schema dump")
        return None, None

    # First, try to extract JSON from markdown code blocks
    code_block_pattern = re.compile(r'```(?:json)?[^\n]*\n(.*?)```', re.DOTALL)
    code_blocks = code_block_pattern.findall(text)
    if debug and code_blocks:
        print(f"    _parse_json_tool_call: found {len(code_blocks)} code blocks")
    for block in code_blocks:
        block = block.strip()
        if debug:
            print(f"    _parse_json_tool_call: checking block: {block[:60]}...")
        if block.startswith('{'):
            if debug:
                print(f"    _parse_json_tool_call: found JSON code block")
            json_str = _sanitize_model_json(block)
            try:
                obj = json.loads(json_str)
                result = _extract_tool_from_json(obj, debug)
                if result[0]:
                    return result
            except json.JSONDecodeError as e:
                if debug:
                    print(f"    _parse_json_tool_call: code block JSON parse error: {e}")
                continue

    # Fallback: Strip all markdown and find first JSON object
    cleaned = re.sub(r"```(?:json|python)?", "", text).strip().rstrip("`").strip()
    
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

    json_str = _sanitize_model_json(json_str)

    try:
        obj = json.loads(json_str)
    except json.JSONDecodeError as e:
        if debug:
            print(f"    _parse_json_tool_call: JSON parse error: {e}")
        return None, None

    return _extract_tool_from_json(obj, debug)


def _extract_python_code(text: str) -> str | None:
    """
    Extract Python code from markdown code blocks.
    """
    match = _PYTHON_CODE_RE.search(text)
    if match:
        return match.group(1).strip()
    return None


def _try_extract_tool_from_malformed(text: str, available_tools: list[str]) -> tuple[str | None, dict | None]:
    """
    Try to extract a tool call from malformed model output.
    """
    text_lower = text.lower()
    
    for tool_name in available_tools:
        if tool_name.lower() in text_lower:
            args = {}
            
            if tool_name == "python_repl":
                code = _extract_python_code(text)
                if code:
                    return tool_name, {"code": code}
                if "datetime" in text_lower or "strftime" in text_lower:
                    return tool_name, {}
            
            if tool_name == "web_search":
                query_match = re.search(r'"query":\s*"([^"]+)"', text)
                if query_match:
                    return tool_name, {"query": query_match.group(1)}
                return tool_name, {}
            
            if tool_name == "calculator":
                expr_match = re.search(r'"expression":\s*"([^"]+)"', text)
                if expr_match:
                    return tool_name, {"expression": expr_match.group(1)}
                return tool_name, {}
            
            return tool_name, args
    
    return None, None


def _fuzzy_match_tool_name(hallucinated_name: str, tools_registry) -> str | None:
    """
    Small models often hallucinate tool names. This function attempts to
    match a hallucinated name to a real tool name using various heuristics.
    
    Returns the matched tool name or None if no match found.
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
    word_mappings = {
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
        "python": ["python_repl", "shell"],
        "repl": ["python_repl", "shell"],
        "code": ["python_repl", "shell"],
        "print": ["python_repl", "shell"],
        "execute": ["python_repl", "shell"],
        "run": ["python_repl", "shell"],
        "exec": ["python_repl", "shell"],
        "today": ["python_repl", "shell"],
        "date": ["python_repl", "shell"],
        "time": ["python_repl", "shell"],
        "datetime": ["python_repl", "shell"],
        "now": ["python_repl", "shell"],
        "current": ["python_repl", "shell"],
        "get_date": ["python_repl", "shell"],
        "get_time": ["python_repl", "shell"],
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
        "read": ["read_file"],
        "write": ["write_file"],
        "file": ["read_file"],
        "load": ["read_file"],
        "save": ["write_file"],
        "weather": ["get_weather"],
        "currency": ["convert_currency"],
        "convert": ["convert_currency"],
        "money": ["convert_currency"],
    }
    
    for keyword, tool_hints in word_mappings.items():
        if keyword in lower_hallucinated:
            for tool_hint in tool_hints:
                for real_name in real_names:
                    if tool_hint in real_name or real_name == tool_hint:
                        return real_name
    
    # Strategy 3: First 4+ chars match
    for real_name in real_names:
        lower_real = real_name.lower()
        if len(lower_real) >= 4 and len(lower_hallucinated) >= 4:
            if lower_real[:4] == lower_hallucinated[:4]:
                return real_name
    
    return None


# ------------------------------------------------------------------ #
#  ReAct parser                                                       #
# ------------------------------------------------------------------ #

def _parse_react(text: str) -> tuple[str | None, str | None, dict | None, str | None]:
    """
    Returns (thought, tool_name, tool_args, final_answer).
    Any field may be None if not present.
    
    Handles multiple format variations from small models.
    """
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
            sanitized = _sanitize_model_json(raw_args)
            try:
                tool_args = json.loads(sanitized)
            except json.JSONDecodeError:
                if raw_args.startswith('{') and '=' in raw_args and 'arguments' not in raw_args.lower():
                    tool_args = {"input": raw_args}
                else:
                    tool_args = {"input": raw_args}

    # Extract final answer
    fa_match = _FINAL_RE.search(text)
    if fa_match:
        final_answer = fa_match.group(1).strip()

    return thought, tool_name, tool_args, final_answer
