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


# ============================================================================
# Argument Synthesis for Small Models
# ============================================================================

# Op word to symbol mapping for expression extraction
_OP_MAP = {
    'plus': '+', 'add': '+', 'and': '+',
    'minus': '-', 'subtract': '-', 'less': '-',
    'times': '*', 'multiplied': '*', 'multiply': '*',
    'divided': '/', 'divide': '/',
}


def extract_calc_expression(user_input: str) -> str | None:
    """
    Extract a mathematical expression from user input.
    Helps small models that can't properly extract expressions.
    """
    q = user_input.strip()
    q_lower = q.lower()
    
    # ---- Multi-step patterns (try first!) ----
    
    # Pattern: "X times Y, then subtract/add Z" or "X times Y then minus Z"
    multi_step = re.search(
        r'(\d+(?:\.\d+)?)\s*(?:times|multiplied?\s*by|\*)\s*(\d+(?:\.\d+)?)[,\s]*(?:then\s+)?(?:subtract|minus|add|plus)?\s*(\d+(?:\.\d+)?)',
        q_lower
    )
    if multi_step:
        nums = multi_step.groups()
        # Determine second operator from context
        after_second = q_lower[q_lower.find(nums[1])+len(nums[1]):] if nums[1] in q_lower else ""
        if 'subtract' in after_second or 'minus' in after_second:
            return f"{nums[0]} * {nums[1]} - {nums[2]}"
        elif 'add' in after_second or 'plus' in after_second:
            return f"{nums[0]} * {nums[1]} + {nums[2]}"
        else:
            # Default: look for the word after the second number
            if 'subtract' in q_lower or 'minus' in q_lower:
                return f"{nums[0]} * {nums[1]} - {nums[2]}"
            # Check for "times X minus Y" pattern
            if 'times' in q_lower and ('minus' in q_lower or 'subtract' in q_lower):
                return f"{nums[0]} * {nums[1]} - {nums[2]}"
    
    # Pattern: "X minus Y plus Z" or "X minus Y, then add Z"
    chain_pattern = re.search(
        r'(\d+(?:\.\d+)?)\s*(?:minus|subtract)\s*(\d+(?:\.\d+)?)[,\s]*(?:then\s+)?(?:plus|add)?\s*(\d+(?:\.\d+)?)',
        q_lower
    )
    if chain_pattern:
        nums = chain_pattern.groups()
        return f"{nums[0]} - {nums[1]} + {nums[2]}"
    
    # ---- Explicit math expressions in prompt ----
    
    # Pattern: "compute X minus Y plus Z" (explicit instruction)
    explicit_expr = re.search(
        r'(?:compute|calculate)\s+(\d+(?:\.\d+)?)\s*(minus|plus|times|divided)\s*(\d+(?:\.\d+)?)(?:\s*(plus|minus|times|divided)\s*(\d+(?:\.\d+)?))?',
        q_lower
    )
    if explicit_expr:
        parts = explicit_expr.groups()
        expr = f"{parts[0]} {_OP_MAP.get(parts[1], parts[1])} {parts[2]}"
        if parts[3] and parts[4]:
            expr += f" {_OP_MAP.get(parts[3], parts[3])} {parts[4]}"
        return expr
    
    # ---- Word problem patterns ----
    
    # Pattern: "has X ... sell/sold A ... and B" → X - A - B
    word_sold = re.search(
        r'(?:has|had|with)\s*(\d+).*?(?:sell|sold|lost|gave|used|spent)\s*(\d+).*?and\s*(\d+)',
        q_lower
    )
    if word_sold:
        return f"{word_sold.group(1)} - {word_sold.group(2)} - {word_sold.group(3)}"
    
    # Pattern: "left" after numbers suggests subtraction
    if 'left' in q_lower and 'how many' in q_lower:
        numbers = re.findall(r'\d+', q)
        if len(numbers) >= 3:
            # First number is usually the starting amount
            return f"{numbers[0]} - {numbers[1]} - {numbers[2]}"
        elif len(numbers) >= 2:
            return f"{numbers[0]} - {numbers[1]}"
    
    # ---- Time/duration patterns ----
    
    # Pattern: "opens at X and closes at Y" → (Y - X) mod 12 or Y - X + 12 if Y < X
    time_pattern = re.search(
        r'(?:opens?|starts?)\s*(?:at\s+)?(\d+)(?:\s*(?:am|pm))?[^.]+(?:closes?|ends?)\s*(?:at\s+)?(\d+)(?:\s*(?:am|pm))?',
        q_lower
    )
    if time_pattern:
        start = int(time_pattern.group(1))
        end = int(time_pattern.group(2))
        if end <= start:
            # PM to PM or AM to PM crossing
            return f"{end + 12 - start}"
        else:
            return f"{end - start}"
    
    # ---- Single operations (fallback) ----
    
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
    
    # Fallback: Find numbers and operators
    numbers = re.findall(r'\d+\.?\d*', q)
    operators = re.findall(r'[+\-*/^]', q)
    
    if numbers and operators:
        expr_parts = []
        for i, num in enumerate(numbers):
            expr_parts.append(num)
            if i < len(operators):
                expr_parts.append(operators[i])
        return " ".join(expr_parts)
    
    if numbers:
        return numbers[0]
    
    return None


def synthesize_tool_args(tool_name: str, args: dict, user_input: str) -> dict:
    """
    Synthesize missing or incorrect tool arguments from context.
    Helps small models that provide incomplete arguments.
    """
    args = dict(args)
    
    if tool_name == "calculator":
        expr = args.get("expression", "")
        
        # If expression is a dict or other non-string, extract it
        if isinstance(expr, dict):
            # Model gave a schema instead of a value
            expr = ""
        elif not isinstance(expr, str):
            expr = str(expr) if expr else ""
        
        # Extract what the expression should be from the user input
        extracted = extract_calc_expression(user_input)
        
        # Check if the model's expression is incomplete or wrong
        if extracted:
            # Compare: if extracted has more operators, use it
            model_ops = len(re.findall(r'[+\-*/^]', expr))
            extracted_ops = len(re.findall(r'[+\-*/^]', extracted))
            
            # If extracted has more operations, use it
            if extracted_ops > model_ops:
                if isinstance(args.get("expression"), dict):
                    args = {"expression": extracted}
                else:
                    args["expression"] = extracted
                return args
            
            # Special case: compare actual results
            if model_ops > 0 and extracted_ops == 0:
                try:
                    # Evaluate model's expression
                    model_result = float(eval(expr, {"__builtins__": {}}, {}))
                    extracted_num = float(extracted)
                    
                    # If model result is negative but extracted is positive
                    # (common for time calculations with AM/PM)
                    if model_result < 0 and extracted_num > 0:
                        args["expression"] = extracted
                        return args
                    
                    # If results differ significantly, use extracted
                    if abs(model_result - extracted_num) > 0.5:
                        args["expression"] = extracted
                        return args
                except:
                    pass
        
        # Check if expression is just an operator or very short
        if len(expr) <= 2 or expr in ["+", "-", "*", "/", "^", "**"]:
            if extracted:
                args["expression"] = extracted
                args = {"expression": extracted}
        
        # Check if expression is just a number but question implies operation
        elif expr and re.match(r'^\d+\.?\d*$', str(expr).strip()):
            q_lower = user_input.lower()
            if "sqrt" in q_lower or "square root" in q_lower:
                args["expression"] = f"sqrt({expr})"
    
    return args


# ============================================================================
# Additional Helper Functions for Small Models
# ============================================================================

def strip_tool_prefix(result: str) -> str:
    """Strip the 'tool_name → ' prefix added to successful results entries."""
    return result.split("→")[-1].strip() if "→" in result else result.strip()


def is_simple_answered_query(user_input: str, successful_results: list[str]) -> bool:
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


def is_greeting_or_simple(text: str) -> bool:
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


def is_small_model(model: str) -> bool:
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


# Repetition detection pattern - catches "Final Answer: X" repeated multiple times
_REPETITION_RE = re.compile(r'(Final Answer:\s*[^\n]+)(\s*\1){2,}', re.IGNORECASE)


def detect_and_fix_repetition(text: str) -> str:
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
