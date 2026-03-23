"""
⚛️ AgentNova — Helper Functions
Utility functions for fuzzy matching, argument normalization, and security.

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

import os
import re
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlparse


# ============================================================================
# Fuzzy Matching
# ============================================================================

def fuzzy_match(query: str, candidates: list[str], threshold: float = 0.4) -> str | None:
    """
    Find the best fuzzy match for a query among candidates.

    Args:
        query: String to match
        candidates: List of candidate strings
        threshold: Minimum similarity ratio (0-1)

    Returns:
        Best matching candidate or None if below threshold
    """
    if not candidates:
        return None

    # Normalize query
    query_normalized = query.lower().replace("_", "").replace("-", "").replace(" ", "")

    best_match = None
    best_score = 0

    for candidate in candidates:
        # Normalize candidate
        candidate_normalized = candidate.lower().replace("_", "").replace("-", "").replace(" ", "")

        # Exact match
        if candidate_normalized == query_normalized:
            return candidate

        # Check if query is prefix of candidate (strong match)
        if candidate_normalized.startswith(query_normalized):
            return candidate

        # Check if candidate contains query
        if query_normalized in candidate_normalized:
            return candidate

        # Calculate similarity
        score = SequenceMatcher(None, query_normalized, candidate_normalized).ratio()

        if score > best_score:
            best_score = score
            best_match = candidate

    if best_score >= threshold:
        return best_match

    return None


# ============================================================================
# Argument Normalization
# ============================================================================

# Common argument name aliases
ARG_ALIASES = {
    # Calculator
    "expression": ["expr", "exp", "formula", "calculation", "math"],
    "equation": ["expr", "expression", "formula"],

    # File operations
    "file_path": ["path", "filepath", "file", "filename", "location"],
    "content": ["text", "data", "body", "value"],
    "output_path": ["output", "destination", "save_path", "save_to"],

    # Shell
    "command": ["cmd", "shell", "script", "exec"],
    "timeout": ["time_limit", "max_time", "seconds"],

    # Web
    "url": ["uri", "link", "endpoint", "address"],
    "query": ["search", "term", "keywords", "q"],
    "headers": ["header", "http_headers"],

    # General
    "input": ["value", "arg", "parameter"],
    "output": ["result", "return_value"],
}


def normalize_args(args: dict[str, Any], expected_params: list[str]) -> dict[str, Any]:
    """
    Normalize argument names to match expected parameters.

    Small models often use alternative argument names. This function
    maps common aliases to the canonical parameter names.

    Args:
        args: Dictionary of provided arguments
        expected_params: List of expected parameter names

    Returns:
        Dictionary with normalized argument names
    """
    if not args:
        return {}

    normalized = {}
    expected_set = set(expected_params)

    for key, value in args.items():
        key_lower = key.lower().replace("-", "_")

        # Direct match
        if key in expected_set:
            normalized[key] = value
            continue

        # Check if key_lower matches any expected param (case insensitive)
        for param in expected_params:
            if param.lower() == key_lower:
                normalized[param] = value
                break
        else:
            # Check aliases
            found = False
            for canonical, aliases in ARG_ALIASES.items():
                if key_lower in aliases or key_lower == canonical.lower():
                    if canonical in expected_set:
                        normalized[canonical] = value
                        found = True
                        break

            # Keep original if no mapping found
            if not found:
                normalized[key] = value

    return normalized


# ============================================================================
# Security Utilities
# ============================================================================

# Blocked shell commands for security
BLOCKED_COMMANDS = {
    # System modification
    "rm", "rmdir", "del", "format", "fdisk", "mkfs",
    "dd", "shred", "wipe", "srm",

    # Privilege escalation
    "sudo", "su", "doas", "pkexec", "gksudo", "kdesu",

    # Network attacks
    "nmap", "nc", "netcat", "telnet", "wget", "curl",
    "ssh", "scp", "sftp", "rsync",

    # Package management (could install malware)
    "apt", "apt-get", "yum", "dnf", "pacman", "pip", "npm", "yarn", "cargo",

    # Process control
    "kill", "killall", "pkill", "xkill", "systemctl", "service",

    # User management
    "useradd", "userdel", "usermod", "passwd", "adduser", "deluser",

    # Dangerous shell features
    "exec", "eval", "source", ".", "alias",

    # Filesystem
    "mount", "umount", "chown", "chmod", "chattr", "lsattr",

    # Shell escapes
    "vi", "vim", "nano", "emacs", "less", "more", "man",
}

# Dangerous URL patterns
BLOCKED_URL_PATTERNS = {
    # Local network
    "localhost", "127.0.0.1", "0.0.0.0", "::1",
    "10.", "192.168.", "172.16.", "172.17.", "172.18.",
    "172.19.", "172.20.", "172.21.", "172.22.", "172.23.",
    "172.24.", "172.25.", "172.26.", "172.27.", "172.28.",
    "172.29.", "172.30.", "172.31.",

    # Cloud metadata endpoints
    "169.254.169.254",  # AWS/GCP/Azure metadata

    # Internal services
    "internal.", "local.", "private.", "intranet.",
}

# Allowed file paths (whitelist approach)
ALLOWED_PATH_PATTERNS = {
    "/tmp", "/temp",
    "./output", "./data", "./files",
    "~/tmp", "~/temp",
}


def validate_path(path: str, allowed_dirs: list[str] | None = None) -> tuple[bool, str]:
    """
    Validate a file path for security.

    Args:
        path: Path to validate
        allowed_dirs: List of allowed directories (if None, uses defaults)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not path:
        return False, "Path cannot be empty"

    # Normalize path
    try:
        normalized = os.path.normpath(path)
    except Exception as e:
        return False, f"Invalid path format: {e}"

    # Check for path traversal (going up directories)
    if "../" in path or "..\\" in path:
        return False, "Path traversal detected: parent directory access not allowed"

    # Check for UNC paths (Windows network paths)
    if path.startswith("\\\\"):
        return False, "UNC paths not allowed"

    # Relative paths are generally allowed if they don't traverse
    if not os.path.isabs(path):
        return True, ""

    # For absolute paths, check against sensitive system directories
    # These are the truly dangerous ones
    critical_system_dirs = ["/etc", "/root", "/var", "/usr", "/bin", "/sbin", "/boot", "/dev", "/proc", "/sys"]
    for critical in critical_system_dirs:
        if normalized.startswith(critical):
            return False, f"Access to system directory denied: {critical}"

    # Allow /tmp and /home for file operations
    if normalized.startswith("/tmp") or normalized.startswith("/var/tmp"):
        return True, ""

    # Check against allowed directories
    allowed = allowed_dirs or list(ALLOWED_PATH_PATTERNS)
    for allowed_dir in allowed:
        if normalized.startswith(os.path.abspath(allowed_dir)):
            return True, ""

    return False, f"Path not in allowed directories: {path}"


def is_safe_url(url: str, block_ssrf: bool = True) -> tuple[bool, str]:
    """
    Validate a URL for SSRF protection.

    Args:
        url: URL to validate
        block_ssrf: Whether to block SSRF targets (local networks)

    Returns:
        Tuple of (is_safe, error_message)
    """
    if not url:
        return False, "URL cannot be empty"

    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Invalid URL format: {e}"

    # Check scheme
    allowed_schemes = {"http", "https"}
    if parsed.scheme.lower() not in allowed_schemes:
        return False, f"URL scheme not allowed: {parsed.scheme}"

    if not parsed.netloc:
        return False, "URL must have a network location"

    hostname = parsed.netloc.split(":")[0].lower()

    # Check for blocked patterns
    if block_ssrf:
        for pattern in BLOCKED_URL_PATTERNS:
            if pattern in hostname:
                return False, f"SSRF protection: blocked hostname pattern '{pattern}'"

    return True, ""


def sanitize_command(command: str) -> tuple[bool, str, str]:
    """
    Sanitize and validate a shell command.

    Args:
        command: Command to validate

    Returns:
        Tuple of (is_safe, error_message, sanitized_command)
    """
    if not command:
        return False, "Command cannot be empty", ""

    # Parse the command to get the base command
    parts = command.strip().split()
    if not parts:
        return False, "Command cannot be empty", ""

    base_cmd = parts[0].lower()

    # Remove common path prefixes
    if "/" in base_cmd:
        base_cmd = base_cmd.split("/")[-1]
    if "\\" in base_cmd:
        base_cmd = base_cmd.split("\\")[-1]

    # Check against blocked commands
    for blocked in BLOCKED_COMMANDS:
        if base_cmd == blocked:
            return False, f"Blocked command: {blocked}", ""

    # Check for shell injection attempts
    injection_patterns = [
        r";\s*\w+",  # Command chaining
        r"\|\s*\w+",  # Piping to another command
        r"&&\s*\w+",  # AND chaining
        r"\|\|\s*\w+",  # OR chaining
        r"`[^`]+`",  # Command substitution (backticks)
        r"\$\([^)]+\)",  # Command substitution ($())
        r"\$\{[^}]+\}",  # Variable expansion
        r">\s*\S+",  # Output redirection
        r"<\s*\S+",  # Input redirection
    ]

    for pattern in injection_patterns:
        if re.search(pattern, command):
            return False, f"Potential injection pattern detected: {pattern}", ""

    return True, "", command


# ============================================================================
# String Utilities
# ============================================================================

def truncate(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """Truncate text to max length with suffix."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def strip_code_blocks(text: str) -> str:
    """Remove markdown code block markers from text."""
    # Remove code block markers
    text = re.sub(r"```\w*\n?", "", text)
    text = re.sub(r"```\s*$", "", text)
    return text.strip()
