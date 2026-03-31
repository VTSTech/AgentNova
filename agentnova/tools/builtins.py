"""
⚛️ AgentNova — Built-in Tools
Pre-built tools for common operations.

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

import math
import os
import subprocess
from typing import Any

from ..core.models import Tool, ToolParam
from ..core.helpers import sanitize_command, validate_path, is_safe_url
from .registry import ToolRegistry


# ============================================================================
# Safety limits
# ============================================================================

# Max bytes read from a file or HTTP response before truncating.
# Prevents OOM / context-window flooding.
MAX_READ_BYTES = 512 * 1024    # 512 KB
MAX_HTTP_BYTES = 256 * 1024    # 256 KB

# Largest exponent allowed in calculator to prevent DoS via 2**9999999.
MAX_EXPONENT = 10_000


# ============================================================================
# Calculator Tool
# ============================================================================

def calculator(expression: str) -> str:
    """
    Evaluate a mathematical expression safely.

    Supports: +, -, *, /, **, %, sqrt, floor, ceil, factorial,
              sin, cos, tan, asin, acos, atan, atan2,
              degrees, radians, log, log10, exp, pi, e

    Args:
        expression: Mathematical expression to evaluate

    Returns:
        Result of the calculation
    """
    import re

    # Guard: block enormous exponents that would exhaust memory/CPU.
    # e.g. 2**9999999 hangs the process before eval() can be interrupted.
    for m in re.finditer(r'\*\*\s*(\d+)', expression):
        exp_val = int(m.group(1))
        if exp_val > MAX_EXPONENT:
            return (
                f"Error: exponent {exp_val} exceeds the maximum allowed "
                f"({MAX_EXPONENT}). Use a smaller exponent."
            )

    safe_dict = {
        # Basic
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "pow": pow,
        # Rounding / integer
        "floor": math.floor,
        "ceil": math.ceil,
        "factorial": math.factorial,
        # Roots / power
        "sqrt": math.sqrt,
        "exp": math.exp,
        # Trig (radians)
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "asin": math.asin,
        "acos": math.acos,
        "atan": math.atan,
        "atan2": math.atan2,
        # Angle conversion
        "degrees": math.degrees,
        "radians": math.radians,
        # Logarithms
        "log": math.log,
        "log10": math.log10,
        "log2": math.log2,
        # Constants
        "pi": math.pi,
        "e": math.e,
        "tau": math.tau,
        "inf": math.inf,
    }

    try:
        result = eval(expression, {"__builtins__": {}}, safe_dict)  # noqa: S307

        # Format numeric results cleanly.
        if isinstance(result, float):
            if math.isnan(result):
                return "Error: result is NaN (not a number)"
            if math.isinf(result):
                return "Error: result is infinite"
            # %.10g: up to 10 significant digits, strips trailing zeros.
            # Turns 0.30000000000000004 into "0.3", keeps 1/3 as "0.3333333333".
            return f"{result:.10g}"
        if isinstance(result, bool):
            # bool subclasses int — return as lowercase string for clarity.
            return str(result).lower()
        return str(result)

    except ZeroDivisionError:
        return "Error: division by zero"
    except ValueError as e:
        return f"Error: {e}"
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
    # Fix for tiny models that add a spurious leading '=' (e.g., ="pwd" instead of "pwd")
    if command.startswith('='):
        command = command[1:].strip()
    
    # sanitize_command validates the command string but returns it unchanged.
    # The third return value is the original command — NOT a sanitised version.
    # The actual security comes from the blocked-command and injection checks
    # inside sanitize_command, not from any transformation of the string.
    is_safe, error_msg, validated_cmd = sanitize_command(command)
    if not is_safe:
        return f"Security error: {error_msg}"

    try:
        # shell=True: the OS shell interprets the full command string.
        # sanitize_command has already rejected injection patterns and
        # blocked dangerous base commands, so this is an informed choice.
        result = subprocess.run(
            validated_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        output = result.stdout.strip()
        if result.returncode != 0:
            if output:
                output += "\n"
            output += f"[Exit code: {result.returncode}]"
            stderr = result.stderr.strip()
            if stderr:
                output += f"\nError: {stderr}"

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
    Read contents of a file (up to 512 KB).

    Args:
        file_path: Path to the file to read

    Returns:
        File contents, a truncation notice, or an error message
    """
    is_valid, error = validate_path(file_path)
    if not is_valid:
        return f"Security error: {error}"

    try:
        with open(file_path, "rb") as f:
            raw = f.read(MAX_READ_BYTES + 1)

        truncated = len(raw) > MAX_READ_BYTES
        content = raw[:MAX_READ_BYTES].decode("utf-8", errors="replace")

        if truncated:
            content += (
                f"\n\n[File truncated — only the first "
                f"{MAX_READ_BYTES // 1024} KB of the file is shown. "
                f"Use a more targeted read if you need a specific section.]"
            )
        return content

    except FileNotFoundError:
        return f"File not found: {file_path}"
    except IsADirectoryError:
        return f"Path is a directory, not a file: {file_path}"
    except PermissionError:
        return f"Permission denied: {file_path}"
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(file_path: str, content: str) -> str:
    """
    Write content to a file, creating parent directories if needed.

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
        parent = os.path.dirname(file_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to {file_path}"

    except PermissionError:
        return f"Permission denied: {file_path}"
    except Exception as e:
        return f"Error writing file: {e}"


# ============================================================================
# Directory Tool
# ============================================================================

def list_directory(path: str = ".") -> str:
    """
    List directory contents with file sizes.

    Args:
        path: Directory path to list (default: current directory)

    Returns:
        Formatted directory listing or error message
    """
    is_valid, error = validate_path(path)
    if not is_valid:
        return f"Security error: {error}"

    try:
        entries = sorted(os.listdir(path))
        if not entries:
            return "(empty directory)"

        lines = []
        for entry in entries:
            full = os.path.join(path, entry)
            try:
                if os.path.isdir(full):
                    lines.append(f"{entry}/")
                else:
                    size = os.path.getsize(full)
                    lines.append(f"{entry}  ({size:,} bytes)")
            except OSError:
                lines.append(f"{entry}  (stat unavailable)")

        return "\n".join(lines)

    except NotADirectoryError:
        return f"Not a directory: {path}"
    except PermissionError:
        return f"Permission denied: {path}"
    except Exception as e:
        return f"Error listing directory: {e}"


# ============================================================================
# HTTP Tool
# ============================================================================

def http_get(url: str, headers: dict | None = None) -> str:
    """
    Make an HTTP GET request (up to 256 KB response).

    Args:
        url: URL to fetch
        headers: Optional headers dict

    Returns:
        Response body (truncated if large) or error message
    """
    import urllib.request
    import urllib.error

    # Validate URL for SSRF
    is_safe, error = is_safe_url(url)
    if not is_safe:
        return f"Security error: {error}"

    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", "AgentNova/1.0")

        if headers:
            for key, value in headers.items():
                # Coerce to str and strip newlines to prevent header injection.
                safe_key = str(key).replace("\r", "").replace("\n", "")
                safe_val = str(value).replace("\r", "").replace("\n", "")
                req.add_header(safe_key, safe_val)

        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read(MAX_HTTP_BYTES + 1)
            truncated = len(raw) > MAX_HTTP_BYTES

            # Detect charset from Content-Type header, fall back to UTF-8.
            content_type = response.headers.get("Content-Type", "")
            charset = "utf-8"
            if "charset=" in content_type.lower():
                try:
                    charset = content_type.lower().split("charset=")[-1].split(";")[0].strip()
                except Exception:
                    charset = "utf-8"

            text = raw[:MAX_HTTP_BYTES].decode(charset, errors="replace")

        if truncated:
            text += (
                f"\n\n[Response truncated — only the first "
                f"{MAX_HTTP_BYTES // 1024} KB is shown.]"
            )
        return text

    except urllib.error.HTTPError as e:
        return f"HTTP error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return f"Connection error: {e.reason}"
    except Exception as e:
        return f"Error fetching URL: {e}"


# ============================================================================
# Python REPL Tool
# ============================================================================

def python_repl(code: str) -> str:
    """
    Execute Python code in a sandboxed subprocess.

    Safe modules available: math, json, re, datetime, collections, itertools.
    File system, network, and subprocess are blocked.

    Args:
        code: Python code to execute

    Returns:
        stdout output, or an error message
    """
    from .sandboxed_repl import sandboxed_exec
    return sandboxed_exec(code)


# ============================================================================
# Time Tools
# ============================================================================

def get_time(timezone: str | None = None) -> str:
    """
    Get current date and time, optionally in a specified timezone.

    Args:
        timezone: IANA timezone name, e.g. 'America/New_York', 'Europe/London'
                  If omitted, returns local system time.

    Returns:
        Current datetime string, or an error if the timezone is unknown
    """
    from datetime import datetime

    if not timezone:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(timezone)
        now = datetime.now(tz)
        # Include %Z so the caller can confirm which timezone was applied.
        return now.strftime("%Y-%m-%d %H:%M:%S %Z")

    except AttributeError:
        # zoneinfo.ZoneInfoNotFoundError may not exist on some builds.
        return (
            f"Error: unknown timezone '{timezone}'. "
            f"Use an IANA name such as 'America/New_York' or 'UTC'."
        )
    except Exception as e:
        err_str = str(e)
        if "No time zone found" in err_str or "ZoneInfoNotFoundError" in err_str or "No such" in err_str:
            return (
                f"Error: unknown timezone '{timezone}'. "
                f"Use an IANA name such as 'America/New_York' or 'UTC'."
            )
        return f"Error getting time for timezone '{timezone}': {e}"


def get_date() -> str:
    """
    Get current local date.

    Returns:
        Current date string (YYYY-MM-DD)
    """
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")


# ============================================================================
# Web Search Tool
# ============================================================================

# Maximum number of search results to return
MAX_SEARCH_RESULTS = 5

# Maximum length per result snippet
MAX_SEARCH_SNIPPET = 300


def web_search(query: str, num_results: int | None = None) -> str:
    """
    Search the web using DuckDuckGo Lite (HTML version, no API key required).

    Args:
        query: Search query string
        num_results: Maximum number of results to return (default: 5, max: 10)

    Returns:
        Formatted search results with titles, URLs, and snippets,
        or an error message if the search fails.
    """
    import urllib.request
    import urllib.error
    import urllib.parse
    import json
    import re

    if num_results is None:
        num_results = MAX_SEARCH_RESULTS
    num_results = max(1, min(num_results, 10))

    try:
        # Use DuckDuckGo Lite — the HTML version that works without JavaScript
        encoded_query = urllib.parse.urlencode({"q": query})
        url = f"https://lite.duckduckgo.com/lite/?{encoded_query}"

        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", "AgentNova/1.0")

        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode("utf-8", errors="replace")

        # DuckDuckGo Lite returns results in <a> tags with class="result-link"
        # and snippets in regular text near each link.
        # Parse the HTML to extract results.
        results = []

        # Pattern 1: DuckDuckGo Lite HTML results
        # Results are in <a class="result-link" href="URL">TITLE</a>
        # followed by a <td class="result-snippet">SNIPPET</td>
        link_pattern = re.compile(
            r'<a[^>]+class="result-link"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        snippet_pattern = re.compile(
            r'<td[^>]+class="result-snippet"[^>]*>(.*?)</td>',
            re.DOTALL | re.IGNORECASE,
        )

        links = link_pattern.findall(html)

        for i, (result_url, title_raw) in enumerate(links):
            if i >= num_results:
                break

            # Clean HTML from title
            title = re.sub(r"<[^>]+>", "", title_raw).strip()
            if not title:
                title = f"Result {i + 1}"

            # Try to find a snippet near this link
            snippet = ""
            # Find the snippet that appears after this link
            link_end = html.find(result_url) + len(result_url)
            remaining = html[link_end:link_end + 2000]
            snippet_match = snippet_pattern.search(remaining)
            if snippet_match:
                snippet = re.sub(r"<[^>]+>", "", snippet_match.group(1)).strip()
                snippet = snippet[:MAX_SEARCH_SNIPPET]
                # Collapse whitespace
                snippet = re.sub(r"\s+", " ", snippet)

            # Skip empty/useless results
            if not snippet and not title:
                continue

            results.append({
                "title": title,
                "url": result_url,
                "snippet": snippet,
            })

        # If no results from Lite, try the regular endpoint
        if not results:
            ddg_url = f"https://html.duckduckgo.com/html/?{encoded_query}"
            req2 = urllib.request.Request(ddg_url, method="GET")
            req2.add_header("User-Agent", "AgentNova/1.0")
            with urllib.request.urlopen(req2, timeout=15) as response:
                html2 = response.read().decode("utf-8", errors="replace")

            # Parse HTML results from regular DDG
            result_blocks = re.split(r'<div class="result results_links results_links_deep web-result', html2)
            for block in result_blocks[1:num_results + 1]:
                title_match = re.search(r'<a[^>]+class="result__a"[^>]*>(.*?)</a>', block, re.DOTALL | re.IGNORECASE)
                url_match = re.search(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"', block)
                snippet_match = re.search(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', block, re.DOTALL | re.IGNORECASE)

                title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip() if title_match else ""
                result_url = url_match.group(1) if url_match else ""
                snippet = re.sub(r"<[^>]+>", "", snippet_match.group(1)).strip() if snippet_match else ""

                if result_url and (title or snippet):
                    results.append({
                        "title": title or "Result",
                        "url": result_url,
                        "snippet": snippet[:MAX_SEARCH_SNIPPET] if snippet else "",
                    })

        if not results:
            return f"No results found for: {query}"

        # Format output
        parts = [f"Web search results for \"{query}\":\n"]
        for i, r in enumerate(results, 1):
            parts.append(f"{i}. {r['title']}")
            parts.append(f"   URL: {r['url']}")
            if r["snippet"]:
                parts.append(f"   {r['snippet']}")
            parts.append("")

        return "\n".join(parts).strip()

    except urllib.error.HTTPError as e:
        return f"HTTP error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return f"Connection error: {e.reason} — web search requires internet access"
    except Exception as e:
        return f"Search error: {e}"


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
    return str(len(text.split()))


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
# Edit File Tool (search-and-replace within files)
# ============================================================================

def edit_file(
    file_path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> str:
    """
    Edit a file by replacing a specific text segment with new content.

    Unlike write_file which overwrites the entire file, this tool performs
    a targeted search-and-replace. The old_string must be an exact match
    within the file. This is safer for making small, precise edits.

    Args:
        file_path: Path to the file to edit
        old_string: The exact text to find and replace
        new_string: The text to replace it with
        replace_all: If True, replace all occurrences (default: False, first only)

    Returns:
        Success message with change summary, or error message
    """
    is_valid, error = validate_path(file_path)
    if not is_valid:
        return f"Security error: {error}"

    if not old_string:
        return "Error: old_string cannot be empty. Provide the exact text to find."

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if old_string not in content:
            return (
                f"Error: old_string not found in {file_path}. "
                f"The text must match EXACTLY (including whitespace and indentation). "
                f"Use read_file first to see the current content."
            )

        # Count occurrences
        count = content.count(old_string)

        if replace_all:
            new_content = content.replace(old_string, new_string)
            replaced = count
        else:
            new_content = content.replace(old_string, new_string, 1)
            replaced = 1

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        lines_added = new_string.count("\n") - old_string.count("\n")
        chars_diff = len(new_string) - len(old_string)
        direction = "+" if chars_diff >= 0 else ""

        return (
            f"Successfully edited {file_path}: "
            f"replaced {replaced} of {count} occurrence(s), "
            f"{direction}{chars_diff} chars ({lines_added:+d} lines)"
        )

    except FileNotFoundError:
        return f"File not found: {file_path}"
    except PermissionError:
        return f"Permission denied: {file_path}"
    except Exception as e:
        return f"Error editing file: {e}"


# ============================================================================
# Todo Tool (in-memory task tracking)
# ============================================================================

# In-memory todo store — persists within a single agent session.
# Each agent instance gets its own store via the closure in make_builtin_registry.
_todo_store: list[dict] = []


def todo_add(content: str, priority: str = "medium") -> str:
    """
    Add a task to the todo list.

    Args:
        content: Description of the task
        priority: Priority level — 'high', 'medium', or 'low' (default: 'medium')

    Returns:
        Confirmation message with the task's position in the list
    """
    if not content or not content.strip():
        return "Error: content cannot be empty"

    priority = priority.lower().strip()
    if priority not in ("high", "medium", "low"):
        priority = "medium"

    import uuid
    task_id = uuid.uuid4().hex[:8]

    _todo_store.append({
        "id": task_id,
        "content": content.strip(),
        "status": "pending",
        "priority": priority,
    })

    return f"Added todo [{task_id}] (priority: {priority}): {content.strip()}"


def todo_list(status: str | None = None) -> str:
    """
    List all todos, optionally filtered by status.

    Args:
        status: Filter by status — 'pending', 'completed', or None for all (default: None)

    Returns:
        Formatted todo list
    """
    if status:
        status = status.lower().strip()
        items = [t for t in _todo_store if t["status"] == status]
    else:
        items = list(_todo_store)

    if not items:
        filter_msg = f" with status '{status}'" if status else ""
        return f"No todos{filter_msg}"

    lines = []
    for i, t in enumerate(items, 1):
        icon = "[ ]" if t["status"] == "pending" else "[x]"
        pri = f" ({t['priority']})" if t.get("priority") != "medium" else ""
        lines.append(f"{i}. {icon} [{t['id']}]{pri} {t['content']}")

    pending = sum(1 for t in _todo_store if t["status"] == "pending")
    completed = sum(1 for t in _todo_store if t["status"] == "completed")
    lines.append(f"")
    lines.append(f"Total: {len(_todo_store)} ({pending} pending, {completed} completed)")

    return "\n".join(lines)


def todo_complete(task_id: str) -> str:
    """
    Mark a todo as completed by its ID.

    Args:
        task_id: The 8-character task ID (from todo_list output)

    Returns:
        Confirmation or error message
    """
    for t in _todo_store:
        if t["id"] == task_id:
            if t["status"] == "completed":
                return f"Todo [{task_id}] is already completed: {t['content']}"
            t["status"] = "completed"
            return f"Completed todo [{task_id}]: {t['content']}"

    return f"Error: todo '{task_id}' not found. Use todo_list to see current tasks."


def todo_remove(task_id: str) -> str:
    """
    Remove a todo by its ID.

    Args:
        task_id: The 8-character task ID (from todo_list output)

    Returns:
        Confirmation or error message
    """
    for i, t in enumerate(_todo_store):
        if t["id"] == task_id:
            removed = _todo_store.pop(i)
            return f"Removed todo [{task_id}]: {removed['content']}"

    return f"Error: todo '{task_id}' not found. Use todo_list to see current tasks."


def todo_clear() -> str:
    """
    Remove all completed todos from the list.

    Returns:
        Summary of how many were cleared
    """
    before = len(_todo_store)
    _todo_store[:] = [t for t in _todo_store if t["status"] != "completed"]
    cleared = before - len(_todo_store)

    if cleared == 0:
        return "No completed todos to clear"

    remaining = len(_todo_store)
    return f"Cleared {cleared} completed todo(s). {remaining} remaining."


# ============================================================================
# Todo Dispatch (unified handler for the todo tool)
# ============================================================================

def _todo_dispatch(
    action: str = "list",
    content: str | None = None,
    task_id: str | None = None,
    priority: str = "medium",
) -> str:
    """Route todo actions to the appropriate handler."""
    action = (action or "list").lower().strip()

    if action == "add":
        if not content:
            return "Error: 'content' is required for the 'add' action"
        return todo_add(content, priority)
    elif action == "list":
        return todo_list(status=None)
    elif action == "complete":
        if not task_id:
            return "Error: 'task_id' is required for the 'complete' action. Use todo list to see task IDs."
        return todo_complete(task_id)
    elif action == "remove":
        if not task_id:
            return "Error: 'task_id' is required for the 'remove' action. Use todo list to see task IDs."
        return todo_remove(task_id)
    elif action == "clear":
        return todo_clear()
    else:
        return (
            f"Error: unknown todo action '{action}'. "
            f"Valid actions: 'add', 'list', 'complete', 'remove', 'clear'"
        )


# ============================================================================
# Build Registry
# ============================================================================

def make_builtin_registry() -> ToolRegistry:
    """Create a registry with all built-in tools."""
    registry = ToolRegistry()

    # Calculator
    registry.register_tool(Tool(
        name="calculator",
        description=(
            "Evaluate mathematical expressions using PYTHON SYNTAX. "
            "CRITICAL: Use ** for power (NOT ^ or 'to the power of'), sqrt() for roots. "
            "Correct examples: '15 * 8', '2**10' (for 2^10), 'sqrt(144)', '144**0.5'. "
            "WRONG: '2 to the power of 10' (causes syntax error). "
            "Supports: +, -, *, /, **, %, sqrt, floor, ceil, factorial, "
            "sin, cos, tan, log, log10, exp, pi, e"
        ),
        params=[ToolParam(
            name="expression",
            type="string",
            description=(
                "Python math expression. Use ** for power, sqrt() for roots. "
                "Examples: '15 * 8', '2**10', 'sqrt(144)', '144**0.5'"
            ),
        )],
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
        description="Read contents of a file (up to 512 KB)",
        params=[ToolParam(name="file_path", type="string", description="Path to the file")],
        handler=read_file,
        category="file",
    ))

    registry.register_tool(Tool(
        name="write_file",
        description="Write content to a file, creating parent directories if needed",
        params=[
            ToolParam(name="file_path", type="string", description="Path to write to"),
            ToolParam(name="content", type="string", description="Content to write"),
        ],
        handler=write_file,
        dangerous=True,
        category="file",
    ))

    registry.register_tool(Tool(
        name="list_directory",
        description="List contents of a directory with file sizes",
        params=[ToolParam(name="path", type="string", description="Directory path to list", required=False, default=".")],
        handler=list_directory,
        category="file",
    ))

    # Edit file — search-and-replace within files
    registry.register_tool(Tool(
        name="edit_file",
        description=(
            "Edit a file by finding and replacing a specific text segment. "
            "Unlike write_file (which overwrites the whole file), this performs "
            "a targeted replacement. The old_string must match EXACTLY. "
            "Use read_file first to see the current content, then use this to "
            "make precise changes. Safer and more token-efficient for small edits."
        ),
        params=[
            ToolParam(name="file_path", type="string", description="Path to the file to edit"),
            ToolParam(name="old_string", type="string", description="The exact text to find and replace (must match exactly, including whitespace)"),
            ToolParam(name="new_string", type="string", description="The replacement text"),
            ToolParam(name="replace_all", type="boolean", description="Replace all occurrences (default: false, first only)", required=False, default=False),
        ],
        handler=edit_file,
        dangerous=True,
        category="file",
    ))

    # Todo — in-memory task tracking
    registry.register_tool(Tool(
        name="todo",
        description=(
            "Manage a task/todo list to track multi-step work. "
            "Actions: 'add' (create task), 'list' (show tasks), 'complete' (mark done), "
            "'remove' (delete task), 'clear' (remove completed). "
            "Use this to plan and track progress on complex tasks."
        ),
        params=[
            ToolParam(name="action", type="string", description="Action to perform: 'add', 'list', 'complete', 'remove', 'clear'"),
            ToolParam(name="content", type="string", description="Task description (for 'add' action)", required=False),
            ToolParam(name="task_id", type="string", description="Task ID from todo list output (for 'complete' and 'remove')", required=False),
            ToolParam(name="priority", type="string", description="Priority: 'high', 'medium', or 'low' (default: 'medium', for 'add')", required=False, default="medium"),
        ],
        handler=_todo_dispatch,
        category="utility",
    ))

    # HTTP
    registry.register_tool(Tool(
        name="http_get",
        description="Make an HTTP GET request to a URL (up to 256 KB response)",
        params=[
            ToolParam(name="url", type="string", description="URL to fetch"),
            ToolParam(name="headers", type="object", description="Optional headers dict", required=False),
        ],
        handler=http_get,
        category="network",
    ))

    # Python REPL
    registry.register_tool(Tool(
        name="python_repl",
        description=(
            "Execute Python code in a sandboxed subprocess. "
            "Safe modules: math, json, re, datetime, collections, itertools. "
            "File system and network access are blocked."
        ),
        params=[ToolParam(name="code", type="string", description="Python code to execute")],
        handler=python_repl,
        category="code",
    ))

    # Time
    registry.register_tool(Tool(
        name="get_time",
        description="Get current date and time, optionally in a specific timezone",
        params=[ToolParam(
            name="timezone",
            type="string",
            description="Optional IANA timezone name, e.g. 'America/New_York'",
            required=False,
        )],
        handler=get_time,
        category="utility",
    ))

    registry.register_tool(Tool(
        name="get_date",
        description="Get current local date (YYYY-MM-DD)",
        params=[],
        handler=get_date,
        category="utility",
    ))

    # JSON
    registry.register_tool(Tool(
        name="parse_json",
        description="Parse and pretty-print a JSON string",
        params=[ToolParam(name="json_string", type="string", description="JSON string to parse")],
        handler=parse_json,
        category="utility",
    ))

    # Web Search
    registry.register_tool(Tool(
        name="web-search",
        description=(
            "Search the web for current information using DuckDuckGo. "
            "Returns titles, URLs, and snippets. Use for news, current events, "
            "real-time data, or any information that may have changed recently."
        ),
        params=[
            ToolParam(name="query", type="string", description="Search query"),
            ToolParam(
                name="num_results",
                type="integer",
                description="Max results to return (1-10, default 5)",
                required=False,
                default=5,
            ),
        ],
        handler=web_search,
        category="network",
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