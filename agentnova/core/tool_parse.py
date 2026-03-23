"""
⚛️ AgentNova — Tool Parser
Regex patterns and functions for parsing tool calls from model output.

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ToolCall:
    """Represents a parsed tool call from model output."""
    name: str
    arguments: dict[str, Any]
    raw: str = ""  # Original text that was parsed
    confidence: float = 1.0  # Confidence of parsing (for fuzzy matches)


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
    name = obj.get("name") or obj.get("function") or obj.get("tool")
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


def _fuzzy_match_tool_name(hallucinated_name: str, available_tool_names: list[str]) -> str | None:
    """
    Small models often hallucinate tool names. This function attempts to
    match a hallucinated name to a real tool name using various heuristics.
    
    Returns the matched tool name or None if no match found.
    """
    if hallucinated_name in available_tool_names:
        return hallucinated_name
    
    lower_hallucinated = hallucinated_name.lower().replace("_", "")
    
    # Strategy 1: Substring match
    for real_name in available_tool_names:
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
        "times": ["calculator", "python_repl"],
        "multiplied": ["calculator", "python_repl"],
        "divide": ["calculator", "python_repl"],
        "divided": ["calculator", "python_repl"],
        "calculator": ["calculator", "python_repl"],
        "store": ["calculator", "python_repl"],
        "open": ["calculator", "python_repl"],
        "hours": ["calculator", "python_repl"],
        "hour": ["calculator", "python_repl"],
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
    
    # Check for keywords in the hallucinated name (including slashes)
    for keyword, tool_hints in word_mappings.items():
        if keyword in lower_hallucinated:
            for tool_hint in tool_hints:
                for real_name in available_tool_names:
                    if tool_hint in real_name or real_name == tool_hint:
                        return real_name
    
    # Strategy 3: First 4+ chars match
    for real_name in available_tool_names:
        lower_real = real_name.lower()
        if len(lower_real) >= 4 and len(lower_hallucinated) >= 4:
            if lower_real[:4] == lower_hallucinated[:4]:
                return real_name
    
    return None


# ------------------------------------------------------------------ #
#  ReAct parser                                                       #
# ------------------------------------------------------------------ #

def _parse_react(text: str, tool_names: list[str] | None = None) -> tuple[str | None, str | None, dict | None, str | None]:
    """
    Returns (thought, tool_name, tool_args, final_answer).
    Any field may be None if not present.
    
    Handles multiple format variations from small models.
    """
    # Repetition detection pattern - catches "Final Answer: X" repeated
    rep_re = re.compile(r'(Final Answer:\s*[^\n]+)(\s*\1){2,}', re.IGNORECASE)
    match = rep_re.search(text)
    if match:
        text = rep_re.sub(r'\1', text)
    
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
        
        # Fuzzy match tool name
        if tool_names and tool_name not in tool_names:
            matched = _fuzzy_match_tool_name(tool_name, tool_names)
            if matched:
                tool_name = matched
        
        # Extract just the JSON object from raw_args (handle extra text after)
        json_start = raw_args.find('{')
        if json_start != -1:
            # Find matching closing brace
            depth = 0
            json_end = -1
            for i, ch in enumerate(raw_args[json_start:], json_start):
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        json_end = i
                        break
            if json_end != -1:
                raw_args = raw_args[json_start:json_end + 1]
        
        # Try to parse JSON args
        try:
            tool_args = json.loads(raw_args)
        except json.JSONDecodeError:
            sanitized = _sanitize_model_json(raw_args)
            try:
                tool_args = json.loads(sanitized)
            except json.JSONDecodeError:
                # Last resort: check for known patterns in the raw text
                expr_match = re.search(r'"expression":\s*"([^"]+)"', raw_args)
                if expr_match:
                    tool_args = {"expression": expr_match.group(1)}
                elif raw_args.startswith('{') and '=' in raw_args and 'arguments' not in raw_args.lower():
                    tool_args = {"input": raw_args}
                else:
                    tool_args = {"input": raw_args}

    # Extract final answer
    fa_match = _FINAL_RE.search(text)
    if fa_match:
        final_answer = fa_match.group(1).strip()

    return thought, tool_name, tool_args, final_answer


# ------------------------------------------------------------------ #
#  ToolParser Class                                                   #
# ------------------------------------------------------------------ #

class ToolParser:
    """
    Parse tool calls from model output.

    Supports multiple formats:
    - Native function calling (JSON)
    - ReAct format: Action: tool_name\nAction Input: {...}
    - XML format: <tool>name</tool><args>{...}</args>
    - Markdown code blocks with JSON
    """

    def __init__(self, tool_names: list[str] | None = None):
        """
        Initialize parser with known tool names for fuzzy matching.

        Args:
            tool_names: List of valid tool names
        """
        self.tool_names = set(tool_names or [])

    def parse(self, text: str) -> list[ToolCall]:
        """
        Parse all tool calls from text.

        Tries multiple formats in order:
        1. Native JSON function calls
        2. ReAct format
        3. XML format
        4. Embedded JSON in markdown

        Args:
            text: Model output text

        Returns:
            List of parsed ToolCalls
        """
        calls = []

        # Try native JSON first (for models with function calling)
        calls.extend(self._parse_native_json(text))

        # Try ReAct format
        calls.extend(self._parse_react(text))

        # Try XML format
        calls.extend(self._parse_xml(text))

        # Try embedded JSON in markdown
        if not calls:
            calls.extend(self._parse_markdown_json(text))

        return calls

    def _parse_native_json(self, text: str) -> list[ToolCall]:
        """Parse native JSON function calling format."""
        calls = []

        # Look for tool_calls style JSON
        try:
            # Try parsing entire text as JSON array
            if text.strip().startswith("["):
                items = json.loads(text)
                for item in items:
                    call = self._extract_tool_from_json(item)
                    if call:
                        calls.append(call)

            # Try parsing as single JSON object
            elif text.strip().startswith("{"):
                data = json.loads(text)
                call = self._extract_tool_from_json(data)
                if call:
                    calls.append(call)
        except json.JSONDecodeError:
            pass

        return calls

    def _extract_tool_from_json(self, data: dict) -> ToolCall | None:
        """Extract ToolCall from JSON object."""
        name, args = _extract_tool_from_json(data)
        if name:
            # Normalize name with fuzzy matching
            name = self._fuzzy_match_tool(name)
            
            # If fuzzy matching didn't find a match and we have tool names,
            # try to use the fuzzy matching with the available tools
            if name not in self.tool_names and self.tool_names:
                matched = _fuzzy_match_tool_name(name, list(self.tool_names))
                if matched:
                    name = matched

            return ToolCall(
                name=name,
                arguments=args if isinstance(args, dict) else {},
                raw=str(data),
            )

        return None

    def _parse_react(self, text: str) -> list[ToolCall]:
        """Parse ReAct format tool calls."""
        thought, name, args, final = _parse_react(text, list(self.tool_names))
        
        if name:
            return [ToolCall(
                name=name,
                arguments=args or {},
                raw=f"Action: {name}\nAction Input: {args}",
                confidence=0.9 if name in self.tool_names else 0.7,
            )]
        
        return []

    def _parse_xml(self, text: str) -> list[ToolCall]:
        """Parse XML format tool calls."""
        calls = []

        # XML patterns
        xml_tool_pattern = re.compile(
            r"<tool>\s*(\w+)\s*</tool>",
            re.IGNORECASE
        )
        xml_args_pattern = re.compile(
            r"<(?:args|arguments|params)>\s*([\s\S]*?)\s*</(?:args|arguments|params)>",
            re.IGNORECASE
        )

        tools = list(xml_tool_pattern.finditer(text))
        args_matches = list(xml_args_pattern.finditer(text))

        for i, tool_match in enumerate(tools):
            name = tool_match.group(1).strip()
            name = self._fuzzy_match_tool(name)

            args = {}
            if i < len(args_matches):
                args_text = args_matches[i].group(1).strip()
                try:
                    args = json.loads(args_text)
                except json.JSONDecodeError:
                    args = {"input": args_text}

            calls.append(ToolCall(
                name=name,
                arguments=args if isinstance(args, dict) else {},
                raw=tool_match.group(0),
            ))

        return calls

    def _parse_markdown_json(self, text: str) -> list[ToolCall]:
        """Parse JSON embedded in markdown code blocks."""
        calls = []

        # Find JSON code blocks
        code_block_pattern = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)

        for match in code_block_pattern.finditer(text):
            json_text = match.group(1).strip()
            try:
                data = json.loads(json_text)
                call = self._extract_tool_from_json(data)
                if call:
                    calls.append(call)
            except json.JSONDecodeError:
                continue

        return calls

    def _fuzzy_match_tool(self, name: str) -> str:
        """
        Fuzzy match tool name against known tools.
        Helps with small models that hallucinate tool names.
        """
        if not self.tool_names:
            return name

        return _fuzzy_match_tool_name(name, list(self.tool_names)) or name

    def has_tool_call(self, text: str) -> bool:
        """Check if text contains a tool call."""
        return bool(self.parse(text))

    def is_final_answer(self, text: str) -> bool:
        """Check if text indicates a final answer."""
        patterns = [
            r"Final Answer:",
            r"Answer:",
            r"Result:",
            r"The answer is",
            r"Therefore,?",
            r"In conclusion,?",
        ]

        text_lower = text.lower()
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return False

    def extract_final_answer(self, text: str) -> str:
        """Extract final answer from text."""
        # Try to find explicit answer marker
        patterns = [
            r"(?:Final Answer|Answer|Result):\s*([\s\S]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # Return entire text as answer
        return text.strip()


__all__ = [
    "ToolCall",
    "ToolParser",
    "_parse_json_tool_call",
    "_parse_react",
    "_fuzzy_match_tool_name",
    "_extract_python_code",
    "_sanitize_model_json",
]
