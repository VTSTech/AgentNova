"""
⚛️ AgentNova — Tool Parsing
Extract tool calls from model output (native and ReAct formats).

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional
from .models import ToolCall


class ToolParser:
    """
    Parse tool calls from model output.

    Supports multiple formats:
    - Native function calling (JSON)
    - ReAct format: Action: tool_name\nAction Input: {...}
    - XML format: <tool>name</tool><args>{...}</args>
    - Markdown code blocks with JSON
    """

    # ReAct patterns
    REACT_ACTION_PATTERN = re.compile(
        r"(?:Action|Tool):\s*(\w+)\s*(?:\n|$)",
        re.IGNORECASE
    )
    REACT_INPUT_PATTERN = re.compile(
        r"(?:Action Input|Tool Input|Parameters|Args):\s*([\s\S]*?)(?=(?:Action|Tool|Thought|Final Answer|$))",
        re.IGNORECASE
    )

    # XML patterns
    XML_TOOL_PATTERN = re.compile(
        r"<tool>\s*(\w+)\s*</tool>",
        re.IGNORECASE
    )
    XML_ARGS_PATTERN = re.compile(
        r"<(?:args|arguments|params)>\s*([\s\S]*?)\s*</(?:args|arguments|params)>",
        re.IGNORECASE
    )

    # JSON patterns
    JSON_TOOL_PATTERN = re.compile(
        r'\{\s*"(?:name|tool|function)"\s*:\s*"(\w+)"',
        re.IGNORECASE
    )

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
        # Handle various JSON formats
        name = None
        args = {}

        # Format: {"name": "tool", "arguments": {...}}
        if "name" in data:
            name = data["name"]
            args = data.get("arguments", data.get("parameters", {}))

        # Format: {"function": {"name": "tool", "arguments": {...}}}
        elif "function" in data:
            func = data["function"]
            name = func.get("name")
            args = func.get("arguments", func.get("parameters", {}))

        # Format: {"tool": "tool_name", "args": {...}}
        elif "tool" in data:
            name = data["tool"]
            args = data.get("args", data.get("arguments", {}))

        if name:
            # Normalize name with fuzzy matching
            name = self._fuzzy_match_tool(name)

            return ToolCall(
                name=name,
                arguments=args if isinstance(args, dict) else {},
                raw=str(data),
            )

        return None

    def _parse_react(self, text: str) -> list[ToolCall]:
        """Parse ReAct format tool calls."""
        calls = []

        # Find all Action/Input pairs
        actions = list(self.REACT_ACTION_PATTERN.finditer(text))
        inputs = list(self.REACT_INPUT_PATTERN.finditer(text))

        for i, action_match in enumerate(actions):
            name = action_match.group(1).strip()
            name = self._fuzzy_match_tool(name)

            # Try to get corresponding input
            args = {}
            if i < len(inputs):
                input_text = inputs[i].group(1).strip()

                # Try to parse as JSON
                try:
                    args = json.loads(input_text)
                    if not isinstance(args, dict):
                        args = {"input": args}
                except json.JSONDecodeError:
                    # Try key:value format
                    args = self._parse_kv_pairs(input_text)

            calls.append(ToolCall(
                name=name,
                arguments=args,
                raw=action_match.group(0),
                confidence=0.9 if name in self.tool_names else 0.7,
            ))

        return calls

    def _parse_xml(self, text: str) -> list[ToolCall]:
        """Parse XML format tool calls."""
        calls = []

        tools = list(self.XML_TOOL_PATTERN.finditer(text))
        args_matches = list(self.XML_ARGS_PATTERN.finditer(text))

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

    def _parse_kv_pairs(self, text: str) -> dict:
        """Parse key:value or key=value pairs."""
        result = {}

        # Try key=value format
        kv_pattern = re.compile(r"(\w+)\s*[=:]\s*([^,\n]+)")
        for match in kv_pattern.finditer(text):
            key = match.group(1).strip()
            value = match.group(2).strip().strip("\"'")
            result[key] = value

        # If no pairs found, treat as single input
        if not result and text.strip():
            result["input"] = text.strip()

        return result

    def _fuzzy_match_tool(self, name: str) -> str:
        """
        Fuzzy match tool name against known tools.
        Helps with small models that hallucinate tool names.
        """
        if not self.tool_names:
            return name

        name_lower = name.lower().replace("_", "").replace("-", "")

        # Exact match (case insensitive)
        for tool in self.tool_names:
            if tool.lower() == name.lower():
                return tool

        # Fuzzy match (ignoring underscores/hyphens)
        for tool in self.tool_names:
            tool_normalized = tool.lower().replace("_", "").replace("-", "")
            if tool_normalized == name_lower:
                return tool

        # Partial match
        for tool in self.tool_names:
            if name_lower in tool.lower() or tool.lower() in name_lower:
                return tool

        # No match found, return original
        return name

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
