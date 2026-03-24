"""
⚛️ AgentNova — Built-in Tools
Pre-built tools for common operations.

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

import math
import subprocess
import sys
from typing import Any

from ..core.models import Tool, ToolParam
from ..core.helpers import sanitize_command, validate_path, is_safe_url
from .registry import ToolRegistry


# ============================================================================
# Calculator Tool
# ============================================================================

def calculator(expression: str) -> str:
    """
    Evaluate a mathematical expression safely.

    Supports: +, -, *, /, **, %, sqrt, sin, cos, tan, log, exp, pi, e

    Args:
        expression: Mathematical expression to evaluate

    Returns:
        Result of the calculation
    """
    # Safe math functions
    safe_dict = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "exp": math.exp,
        "pi": math.pi,
        "e": math.e,
        "pow": pow,
    }

    try:
        # Remove dangerous characters
        expression = expression.replace("__", "")

        # Evaluate in safe context
        result = eval(expression, {"__builtins__": {}}, safe_dict)
        return str(result)

    except Exception as e:
        return f"Error evaluating expression: {e}"


# ============================================================================
# Shell Tool
# ============================================================================

def shell(command: str, timeout: int = 30) -> str:
    """
    Execute a shell command (with security restrictions).

    Args:
        command: Shell command to execute
        timeout: Timeout in seconds (default 30)

    Returns:
        Command output or error message
    """
    # Validate command
    is_safe, error_msg, safe_cmd = sanitize_command(command)
    if not is_safe:
        return f"Security error: {error_msg}"

    try:
        result = subprocess.run(
            safe_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        output = result.stdout.strip()
        if result.returncode != 0:
            output += f"\n[Exit code: {result.returncode}]"
            if result.stderr:
                output += f"\nError: {result.stderr}"

        return output or "(no output)"

    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout} seconds"

    except Exception as e:
        return f"Error executing command: {e}"


# ============================================================================
# File Tools
# ============================================================================

def read_file(file_path: str) -> str:
    """
    Read contents of a file.

    Args:
        file_path: Path to the file to read

    Returns:
        File contents or error message
    """
    is_valid, error = validate_path(file_path)
    if not is_valid:
        return f"Security error: {error}"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    except FileNotFoundError:
        return f"File not found: {file_path}"

    except Exception as e:
        return f"Error reading file: {e}"


def write_file(file_path: str, content: str) -> str:
    """
    Write content to a file.

    Args:
        file_path: Path to write to
        content: Content to write

    Returns:
        Success message or error
    """
    is_valid, error = validate_path(file_path)
    if not is_valid:
        return f"Security error: {error}"

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to {file_path}"

    except Exception as e:
        return f"Error writing file: {e}"


# ============================================================================
# HTTP Tool
# ============================================================================

def http_get(url: str, headers: dict | None = None) -> str:
    """
    Make an HTTP GET request.

    Args:
        url: URL to fetch
        headers: Optional headers dict

    Returns:
        Response body or error message
    """
    import urllib.request
    import urllib.error

    # Validate URL for SSRF
    is_safe, error = is_safe_url(url)
    if not is_safe:
        return f"Security error: {error}"

    try:
        req = urllib.request.Request(url, method="GET")

        if headers:
            for key, value in headers.items():
                req.add_header(key, value)

        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read().decode("utf-8")

    except urllib.error.HTTPError as e:
        return f"HTTP error {e.code}: {e.reason}"

    except urllib.error.URLError as e:
        return f"Connection error: {e.reason}"

    except Exception as e:
        return f"Error fetching URL: {e}"


# ============================================================================
# Time Tool
# ============================================================================

def get_time(timezone: str | None = None) -> str:
    """
    Get current date and time.

    Args:
        timezone: Optional timezone (e.g., 'America/New_York')

    Returns:
        Current date and time string
    """
    from datetime import datetime

    now = datetime.now()

    if timezone:
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo(timezone)
            now = datetime.now(tz)
        except Exception:
            pass

    return now.strftime("%Y-%m-%d %H:%M:%S")


def get_date() -> str:
    """
    Get current date.

    Returns:
        Current date string (YYYY-MM-DD)
    """
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")


# ============================================================================
# JSON Tool
# ============================================================================

def parse_json(json_string: str) -> str:
    """
    Parse a JSON string and format it.

    Args:
        json_string: JSON string to parse

    Returns:
        Formatted JSON or error message
    """
    import json

    try:
        data = json.loads(json_string)
        return json.dumps(data, indent=2)

    except json.JSONDecodeError as e:
        return f"JSON parse error: {e}"


# ============================================================================
# Text Tools
# ============================================================================

def count_words(text: str) -> str:
    """
    Count words in text.

    Args:
        text: Text to count words in

    Returns:
        Word count
    """
    words = text.split()
    return str(len(words))


def count_chars(text: str) -> str:
    """
    Count characters in text.

    Args:
        text: Text to count characters in

    Returns:
        Character count
    """
    return str(len(text))


# ============================================================================
# Build Registry
# ============================================================================

def make_builtin_registry() -> ToolRegistry:
    """Create a registry with all built-in tools."""
    registry = ToolRegistry()

    # Calculator
    registry.register_tool(Tool(
        name="calculator",
        description="Evaluate mathematical expressions. Supports +, -, *, /, **, sqrt, sin, cos, tan, log, exp, pi, e",
        params=[ToolParam(name="expression", type="string", description="Mathematical expression to evaluate")],
        handler=calculator,
        category="math",
    ))

    # Shell
    registry.register_tool(Tool(
        name="shell",
        description="Execute shell commands (with security restrictions)",
        params=[
            ToolParam(name="command", type="string", description="Shell command to execute"),
            ToolParam(name="timeout", type="integer", description="Timeout in seconds", required=False, default=30),
        ],
        handler=shell,
        dangerous=True,
        category="system",
    ))

    # File operations
    registry.register_tool(Tool(
        name="read_file",
        description="Read contents of a file",
        params=[ToolParam(name="file_path", type="string", description="Path to the file")],
        handler=read_file,
        category="file",
    ))

    registry.register_tool(Tool(
        name="write_file",
        description="Write content to a file",
        params=[
            ToolParam(name="file_path", type="string", description="Path to write to"),
            ToolParam(name="content", type="string", description="Content to write"),
        ],
        handler=write_file,
        dangerous=True,
        category="file",
    ))

    # HTTP
    registry.register_tool(Tool(
        name="http_get",
        description="Make an HTTP GET request to a URL",
        params=[
            ToolParam(name="url", type="string", description="URL to fetch"),
            ToolParam(name="headers", type="object", description="Optional headers", required=False),
        ],
        handler=http_get,
        category="network",
    ))

    # Time
    registry.register_tool(Tool(
        name="get_time",
        description="Get current date and time",
        params=[ToolParam(name="timezone", type="string", description="Optional timezone", required=False)],
        handler=get_time,
        category="utility",
    ))

    registry.register_tool(Tool(
        name="get_date",
        description="Get current date (YYYY-MM-DD)",
        params=[],
        handler=get_date,
        category="utility",
    ))

    # JSON
    registry.register_tool(Tool(
        name="parse_json",
        description="Parse and format a JSON string",
        params=[ToolParam(name="json_string", type="string", description="JSON string to parse")],
        handler=parse_json,
        category="utility",
    ))

    # Text
    registry.register_tool(Tool(
        name="count_words",
        description="Count words in text",
        params=[ToolParam(name="text", type="string", description="Text to count")],
        handler=count_words,
        category="text",
    ))

    registry.register_tool(Tool(
        name="count_chars",
        description="Count characters in text",
        params=[ToolParam(name="text", type="string", description="Text to count")],
        handler=count_chars,
        category="text",
    ))

    return registry


# Default registry instance
BUILTIN_REGISTRY = make_builtin_registry()
