"""
🦞 AgentNova R04 — Built-in Tools
A curated set of safe, practical tools for local agents.
Import whichever you need and add them to a ToolRegistry.

    from agentnova.tools.builtins import BUILTIN_REGISTRY
    agent = Agent(model="llama3.1:8b", tools=BUILTIN_REGISTRY)

For isolated state per agent (separate REPL sessions and note stores),
use make_builtin_registry() instead:

    from agentnova.tools.builtins import make_builtin_registry
    agent = Agent(model="llama3.1:8b", tools=make_builtin_registry())

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

from __future__ import annotations

import ast
import io
import math
import os
import re
import shlex
import subprocess
import sys
import textwrap
import traceback
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from pathlib import Path
from typing import Any

import urllib.request
import urllib.error
import urllib.parse
import socket
import ipaddress

from ..core.tools import ToolRegistry, Tool, ToolParam


# ================================================================== #
#  Security Configuration                                             #
# ================================================================== #
# These can be overridden via environment variables:
#   AGENTNOVA_ALLOWED_PATHS=/home/user/projects:/tmp/workspace
#   AGENTNOVA_BLOCKED_COMMANDS=rm,sudo,chmod,chown
#   AGENTNOVA_SECURITY_MODE=strict|permissive|disabled

# Default allowed paths (cwd + common safe directories)
_DEFAULT_ALLOWED_PATHS = [
    ".",  # Current working directory
    "~",  # User home (can be restricted)
]

# Sensitive paths that are ALWAYS blocked regardless of allowed_paths
BLOCKED_PATH_PATTERNS = [
    "/etc/shadow",
    "/etc/passwd",
    "/etc/sudoers",
    "/etc/ssh/",
    "/root/.ssh/",
    "/.ssh/",
    "/.gnupg/",
    "/etc/gshadow",
    "/etc/shadow-",
    "/etc/passwd-",
]

# Commands that are blocked by default (destructive or privilege escalation)
DEFAULT_BLOCKED_COMMANDS = [
    # File destruction
    "rm",
    "rmdir",
    "shred",
    "wipe",
    "shred",
    # Privilege escalation
    "sudo",
    "su",
    "doas",
    "pkexec",
    "gksudo",
    "kdesu",
    # System modification
    "chmod",
    "chown",
    "chgrp",
    "mkfs",
    "fdisk",
    "parted",
    "dd",
    "format",
    # Package management (can install malicious packages)
    "apt",
    "apt-get",
    "aptitude",
    "yum",
    "dnf",
    "pacman",
    "pip",
    "pip3",
    "npm",
    "yarn",
    "gem",
    "cargo",
    # Network tunneling/exfiltration
    "nc",
    "ncat",
    "netcat",
    "telnet",
    # Process manipulation
    "kill",
    "killall",
    "pkill",
    # System control
    "systemctl",
    "service",
    "init",
    "reboot",
    "shutdown",
    "poweroff",
    "halt",
    # Cron/at (persistence)
    "crontab",
    "at",
    # Keylogging/snooping
    "xinput",
    "xev",
    "strace",
    "ltrace",
]

# Dangerous command patterns (regex)
DANGEROUS_PATTERNS = [
    r">\s*/dev/",           # Writing to devices
    r"<\s*/dev/",           # Reading from devices
    r"\|\s*bash",           # Piping to bash
    r"\|\s*sh",             # Piping to sh
    r"\$\([^)]+\)",         # Command substitution
    r"`[^`]+`",             # Backtick command substitution
    r"&&\s*rm",             # Chained rm
    r"\|\s*sudo",           # Piping to sudo
    r">\s*/etc/",           # Overwrite
    r";\s*rm\b",                    # Command chaining with rm
    r"\|\s*rm\b",                   # Pipe to rm
    r"\$\([^)]+\)",                 # Command substitution
    r"`[^`]+`",                     # Backtick command substitution
    r">\s*/dev/",                   # Writing to device files
    r">\s*/proc/",                  # Writing to proc
    r">\s*/sys/",                   # Writing to sysfs
]


def _get_allowed_paths() -> list[Path]:
    """Get list of allowed base paths from env or defaults."""
    env_paths = os.environ.get("AGENTNOVA_ALLOWED_PATHS", "")
    if env_paths:
        paths = []
        for p in env_paths.split(":"):
            expanded = Path(p).expanduser().resolve()
            if expanded.exists():
                paths.append(expanded)
        return paths
    # Default: current directory and home
    return [Path(".").resolve(), Path.home()]


def _get_blocked_commands() -> set[str]:
    """Get set of blocked commands from env or defaults."""
    env_blocked = os.environ.get("AGENTNOVA_BLOCKED_COMMANDS", "")
    if env_blocked:
        return set(c.strip().lower() for c in env_blocked.split(",") if c.strip())
    return set(DEFAULT_BLOCKED_COMMANDS)


def _get_security_mode() -> str:
    """Get security mode: strict, permissive, or disabled."""
    return os.environ.get("AGENTNOVA_SECURITY_MODE", "strict").lower()


def _validate_path(path: str, operation: str = "access") -> tuple[bool, str]:
    """
    Validate that a path is within allowed directories and not blocked.
    
    Returns (is_valid, error_message).
    """
    mode = _get_security_mode()
    
    if mode == "disabled":
        return True, ""
    
    try:
        target = Path(path).expanduser().resolve()
    except Exception as e:
        return False, f"Invalid path: {e}"
    
    # Check against always-blocked patterns
    path_str = str(target)
    for blocked in BLOCKED_PATH_PATTERNS:
        if blocked.endswith("/") and path_str.startswith(blocked):
            return False, f"Access denied: '{blocked}*' is a restricted path"
        elif path_str == blocked:
            return False, f"Access denied: '{blocked}' is a restricted file"
    
    # Check if path is within allowed directories
    allowed_paths = _get_allowed_paths()
    in_allowed = any(
        target == allowed or target.is_relative_to(allowed)
        for allowed in allowed_paths
    )
    
    if mode == "strict" and not in_allowed:
        allowed_str = ", ".join(str(p) for p in allowed_paths)
        return False, f"Path '{path}' is outside allowed directories: {allowed_str}"
    
    if mode == "permissive":
        # In permissive mode, just warn but allow
        if not in_allowed:
            pass  # Could log a warning here
    
    return True, ""


def _validate_command(command: str) -> tuple[bool, str]:
    """
    Validate that a shell command doesn't contain blocked commands or patterns.
    
    Returns (is_valid, error_message).
    """
    mode = _get_security_mode()
    
    if mode == "disabled":
        return True, ""
    
    blocked = _get_blocked_commands()
    command_lower = command.lower()
    
    # Extract base command (first word)
    try:
        parts = shlex.split(command)
        if parts:
            base_cmd = parts[0].split("/")[-1].lower()  # Handle /usr/bin/rm
        else:
            return False, "Empty command"
    except ValueError:
        base_cmd = command.split()[0].lower() if command.split() else ""
    
    # Check base command against blocklist
    if base_cmd in blocked:
        return False, f"Command '{base_cmd}' is blocked for security"
    
    # Check for blocked commands anywhere in the command string
    for blocked_cmd in blocked:
        # Match as word boundary to avoid false positives (e.g., "grep" vs "rm")
        pattern = rf'\b{re.escape(blocked_cmd)}\b'
        if re.search(pattern, command_lower):
            return False, f"Command contains blocked command: {blocked_cmd}"
    
    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command_lower):
            return False, f"Command matches dangerous pattern"
    
    return True, ""


def _validate_url(url: str) -> tuple[bool, str]:
    """
    Validate a URL for SSRF protection.
    
    Blocks:
    - Private IP ranges (10.x, 172.16-31.x, 192.168.x, 127.x, 169.254.x)
    - Localhost variations
    - file:// protocol
    - Cloud metadata endpoints
    
    Returns (is_valid, error_message).
    """
    mode = _get_security_mode()
    
    if mode == "disabled":
        return True, ""
    
    try:
        parsed = urllib.parse.urlparse(url)
        
        # Only allow http and https
        if parsed.scheme not in ("http", "https"):
            return False, f"Protocol '{parsed.scheme}' is not allowed (only http/https)"
        
        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid URL: no hostname"
        
        # Block known dangerous hostnames
        blocked_hostnames = {
            "localhost",
            "localhost.localdomain",
            "ip6-localhost",
            "ip6-loopback",
            "metadata.google.internal",
            "metadata",
            "kubernetes.default",
            "kubernetes.default.svc",
        }
        
        if hostname.lower() in blocked_hostnames:
            return False, f"Access to '{hostname}' is blocked"
        
        # Block hostnames that look like IP addresses in private ranges
        # Also resolve the hostname to check for DNS rebinding attacks
        try:
            # Try to parse as IP address directly
            ip = ipaddress.ip_address(hostname)
            if _is_private_ip(ip):
                return False, f"Access to private IP {ip} is blocked"
        except ValueError:
            # Not an IP address, need to resolve
            if mode == "strict":
                try:
                    # Resolve hostname to IP
                    resolved = socket.gethostbyname(hostname)
                    ip = ipaddress.ip_address(resolved)
                    if _is_private_ip(ip):
                        return False, f"Hostname '{hostname}' resolves to private IP {ip}"
                except socket.gaierror:
                    pass  # Can't resolve, let it fail naturally
        
        # Block cloud metadata IP
        if hostname == "169.254.169.254":
            return False, "Access to cloud metadata endpoint is blocked"
        
        return True, ""
        
    except Exception as e:
        return False, f"URL validation error: {e}"


def _is_private_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address is in a private/reserved range."""
    return (
        ip.is_private or
        ip.is_loopback or
        ip.is_link_local or
        ip.is_reserved or
        ip.is_multicast or
        ip.is_unspecified
    )


# ================================================================== #
#  Factory — produces a registry with fully isolated stateful tools    #
# ================================================================== #

def make_builtin_registry() -> ToolRegistry:
    """
    Create a fresh ToolRegistry containing all built-in tools.
    Stateful tools (python_repl, notes) get their own isolated state,
    so multiple agents will never share REPL globals or note stores.
    """
    registry = ToolRegistry()

    # ================================================================== #
    #  Calculator                                                          #
    # ================================================================== #

    @registry.tool(
        description="Evaluate a mathematical expression. Supports +, -, *, /, **, sqrt(), log(), sin(), cos(), and all Python math functions.",
        param_descriptions={"expression": "A Python math expression, e.g. '2 ** 10', 'sqrt(144)', 'math.log(100)'"},
    )
    def calculator(expression: str) -> str:
        """Safe math evaluator using Python's math module."""
        allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
        allowed_names.update({"abs": abs, "round": round, "min": min, "max": max, "sum": sum})
        try:
            tree = ast.parse(expression, mode="eval")
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom, ast.Call)):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id not in allowed_names:
                            return f"[Blocked] Function '{node.func.id}' is not allowed."
            result = eval(compile(tree, "<calc>", "eval"), {"__builtins__": {}}, allowed_names)
            return str(result)
        except Exception as e:
            return f"[Calculator error] {e}"

    # ================================================================== #
    #  Shell                                                               #
    # ================================================================== #

    @registry.tool(
        description="Run a shell command and return its output. Use with caution.",
        param_descriptions={
            "command": "Shell command to execute",
            "timeout": "Maximum seconds to wait (default 30)",
        },
    )
    def shell(command: str, timeout: int = 30) -> str:
        """Execute a shell command via subprocess with security checks."""
        # Validate command against blocklist
        is_valid, error_msg = _validate_command(command)
        if not is_valid:
            return f"[Security] {error_msg}"
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = result.stdout + result.stderr
            return output.strip() or f"[Exit code {result.returncode}]"
        except subprocess.TimeoutExpired:
            return f"[Timeout] Command exceeded {timeout}s"
        except Exception as e:
            return f"[Shell error] {e}"

    # ================================================================== #
    #  File I/O                                                            #
    # ================================================================== #

    @registry.tool(
        description="Read a file from the local filesystem and return its contents.",
        param_descriptions={
            "path": "Absolute or relative file path",
            "max_chars": "Maximum characters to return (default 100000, 0 for unlimited)",
        },
    )
    def read_file(path: str, max_chars: int = 100000) -> str:
        """Read and return file contents as text with path validation."""
        # Validate path
        is_valid, error_msg = _validate_path(path, "read")
        if not is_valid:
            return f"[Security] {error_msg}"
        
        try:
            p = Path(path).expanduser().resolve()
            
            # Check file size before reading
            if p.is_file():
                size = p.stat().st_size
                if size > 10_000_000:  # 10MB limit
                    return f"[File too large] {size:,} bytes (max 10MB)"
            
            content = p.read_text(encoding="utf-8", errors="replace")
            
            # Truncate if needed
            if max_chars > 0 and len(content) > max_chars:
                return content[:max_chars] + f"\n... [truncated, {len(content):,} total chars]"
            
            return content
        except Exception as e:
            return f"[File read error] {e}"

    @registry.tool(
        description="Write text content to a file on the local filesystem.",
        param_descriptions={
            "path": "Absolute or relative file path",
            "content": "Text to write",
            "append": "If true, append instead of overwriting (default false)",
        },
    )
    def write_file(path: str, content: str, append: bool = False) -> str:
        """Write (or append) content to a file with path validation."""
        # Validate path
        is_valid, error_msg = _validate_path(path, "write")
        if not is_valid:
            return f"[Security] {error_msg}"
        
        # Check content size
        if len(content) > 10_000_000:  # 10MB limit
            return f"[Content too large] {len(content):,} chars (max 10MB)"
        
        try:
            p = Path(path).expanduser().resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if append else "w"
            with p.open(mode, encoding="utf-8") as fh:
                fh.write(content)
            action = "Appended" if append else "Written"
            return f"{action} {len(content):,} chars to {path}"
        except Exception as e:
            return f"[File write error] {e}"

    @registry.tool(
        description="List files and directories at the given path.",
        param_descriptions={"path": "Directory path to list (default: current directory)"},
    )
    def list_directory(path: str = ".") -> str:
        """List directory contents with path validation."""
        # Validate path
        is_valid, error_msg = _validate_path(path, "list")
        if not is_valid:
            return f"[Security] {error_msg}"
        
        try:
            p = Path(path).expanduser().resolve()
            entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name))
            lines = []
            for e in entries:
                indicator = "/" if e.is_dir() else ""
                size = f"  ({e.stat().st_size:,}B)" if e.is_file() else ""
                lines.append(f"{e.name}{indicator}{size}")
            return "\n".join(lines) or "[Empty directory]"
        except Exception as e:
            return f"[Directory error] {e}"

    # ================================================================== #
    #  HTTP fetch                                                          #
    # ================================================================== #

    @registry.tool(
        description="Fetch the text content of a URL via HTTP GET.",
        param_descriptions={
            "url": "The URL to fetch",
            "max_chars": "Maximum characters to return (default 3000)",
        },
    )
    def http_get(url: str, max_chars: int = 3000) -> str:
        """Retrieve the text content of a web page or API endpoint with SSRF protection."""
        # Validate URL for SSRF protection
        is_valid, error_msg = _validate_url(url)
        if not is_valid:
            return f"[Security] {error_msg}"
        
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AgentNova-R01/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                text = resp.read().decode("utf-8", errors="replace")
            return text[:max_chars] + ("..." if len(text) > max_chars else "")
        except Exception as e:
            return f"[HTTP error] {e}"

    # ================================================================== #
    #  Web Search                                                          #
    # ================================================================== #

    @registry.tool(
        description="Search the web using DuckDuckGo and return top results. Use for finding current information, news, or answers to questions.",
        param_descriptions={
            "query": "Search query (what to search for)",
            "num_results": "Number of results to return (default 5, max 10)",
        },
    )
    def web_search(query: str, num_results: int = 5) -> str:
        """Search the web via DuckDuckGo HTML (no API key required)."""
        try:
            num_results = min(max(1, num_results), 10)  # Clamp to 1-10
            # DuckDuckGo HTML search endpoint
            search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(
                search_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html",
                }
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            
            # Parse results from HTML
            results = []
            # DuckDuckGo HTML results are in <a class="result__a"> tags
            pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, html)
            
            for url, title in matches[:num_results]:
                # Clean up the URL (DuckDuckGo uses redirects)
                if url.startswith("//"):
                    url = "https:" + url
                # Extract actual URL from DuckDuckGo redirect if present
                if "uddg=" in url:
                    parsed = urllib.parse.urlparse(url)
                    params = urllib.parse.parse_qs(parsed.query)
                    if "uddg" in params:
                        url = params["uddg"][0]
                
                title = re.sub(r'<[^>]+>', '', title).strip()
                results.append(f"• {title}\n  {url}")
            
            if not results:
                return f"[No results found for: {query}]"
            
            return f"Search results for '{query}':\n\n" + "\n\n".join(results)
        except Exception as e:
            return f"[Search error] {e}"


    # ================================================================== #
    #  Python REPL  (stateful — isolated per registry instance)           #
    # ================================================================== #

    _repl_globals: dict = {}  # isolated per registry instance

    @registry.tool(
        description="Execute Python code in a persistent session and return stdout + result.",
        param_descriptions={"code": "Valid Python code to execute"},
    )
    def python_repl(code: str) -> str:
        """Run arbitrary Python code (local execution — no sandboxing)."""
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        try:
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                exec(textwrap.dedent(code), _repl_globals)  # noqa: S102
            output = stdout_buf.getvalue()
            errors = stderr_buf.getvalue()
            return (output + errors).strip() or "[No output]"
        except Exception:
            return traceback.format_exc()

    @registry.tool(
        description="Reset the Python REPL session, clearing all variables.",
    )
    def python_repl_reset() -> str:
        """Clears the REPL global namespace."""
        _repl_globals.clear()
        return "REPL session reset."

    # ================================================================== #
    #  Memory / notes  (stateful — isolated per registry instance)        #
    # ================================================================== #

    _notes: dict[str, str] = {}  # isolated per registry instance

    @registry.tool(
        description="Save a note under a given key for later retrieval.",
        param_descriptions={"key": "Note identifier", "value": "Content to store"},
    )
    def save_note(key: str, value: str) -> str:
        """Persist a key-value note in the agent's scratchpad."""
        _notes[key] = value
        return f"Saved note '{key}'."

    @registry.tool(
        description="Retrieve a previously saved note by key.",
        param_descriptions={"key": "Note identifier to look up"},
    )
    def get_note(key: str) -> str:
        """Retrieve a note from the scratchpad."""
        if key in _notes:
            return _notes[key]
        available = list(_notes.keys())
        return f"[No note found for '{key}'. Available keys: {available}]"

    @registry.tool(description="List all saved note keys.")
    def list_notes() -> str:
        """Return all note keys currently stored."""
        if not _notes:
            return "[No notes saved yet]"
        return "\n".join(f"- {k}" for k in _notes)

    return registry


# ================================================================== #
#  Shared default registry                                             #
#  Fine for single-agent scripts; use make_builtin_registry() for     #
#  multi-agent scenarios to get isolated state per agent.             #
# ================================================================== #

BUILTIN_REGISTRY = make_builtin_registry()