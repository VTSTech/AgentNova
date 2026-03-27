"""
⚛️ AgentNova — Error Recovery Module

Implements error recovery state tracking to prevent infinite loops when tools
repeatedly fail, and provides tool-specific observation hints for common errors.

Key Features:
1. ErrorRecoveryTracker - Tracks consecutive failures per tool
2. Tool-specific hints for common error patterns
3. Smart recovery strategies (alternative tools, guidance, early termination)

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional


# ============================================================================
# Configuration
# ============================================================================

# Maximum consecutive failures per tool before suggesting alternatives
DEFAULT_MAX_CONSECUTIVE_FAILURES = 3

# Maximum total failures before terminating the loop
DEFAULT_MAX_TOTAL_FAILURES = 5


# ============================================================================
# Tool-Specific Error Hints
# ============================================================================

# Error pattern -> (hint, suggestion) mappings per tool
TOOL_ERROR_HINTS = {
    "calculator": {
        "syntax": (
            "Use Python syntax for math expressions.",
            "Examples: 2**10 (power), sqrt(144) (root), 15 * 8 (multiply)"
        ),
        "division by zero": (
            "Division by zero is not allowed.",
            "Check your expression for zero divisors."
        ),
        "name .* is not defined": (
            "Unknown function or variable name.",
            "Available: sqrt, sin, cos, tan, log, log10, exp, pi, e, floor, ceil"
        ),
        "exponent.*exceeds": (
            "Exponent too large.",
            "Use a smaller exponent (max 10,000)."
        ),
        "NaN": (
            "Result is not a number (NaN).",
            "Check for invalid operations like sqrt(-1) or log(0)."
        ),
        "infinite": (
            "Result is infinite.",
            "Check for division by very small numbers or overflow."
        ),
    },
    
    "shell": {
        "command not found": (
            "Command not found on this system.",
            "Try: which <command> to find installed tools, or use an alternative."
        ),
        "permission denied": (
            "Permission denied for this operation.",
            "Try a different approach or check if you need different arguments."
        ),
        "no such file or directory": (
            "Path does not exist.",
            "Check the path with 'ls' first, or use absolute paths."
        ),
        "blocked": (
            "This command is blocked for security.",
            "Try an alternative command that is allowed."
        ),
        "injection": (
            "Potential injection pattern detected.",
            "Use simple commands without chaining, pipes, or redirections."
        ),
        "security": (
            "Security restriction prevented execution.",
            "Review the command for blocked patterns."
        ),
        "timed out": (
            "Command took too long.",
            "Try a simpler command or reduce the operation scope."
        ),
    },
    
    "read_file": {
        "not found": (
            "File not found.",
            "Check the path with list_directory, or verify the file exists."
        ),
        "permission denied": (
            "Permission denied to read this file.",
            "Try a different file or check the path."
        ),
        "is a directory": (
            "Path is a directory, not a file.",
            "Use list_directory to see contents, or specify a file path."
        ),
        "security": (
            "Path access denied for security.",
            "Use paths in allowed directories: /tmp, ./output, ./data"
        ),
        "truncated": (
            "File was too large and truncated.",
            "Read specific sections or use a more targeted approach."
        ),
    },
    
    "write_file": {
        "permission denied": (
            "Permission denied to write to this location.",
            "Try writing to /tmp, ./output, or another allowed directory."
        ),
        "security": (
            "Path access denied for security.",
            "Use paths in allowed directories: /tmp, ./output, ./data"
        ),
        "no such file or directory": (
            "Parent directory does not exist.",
            "The parent directory will be created automatically. Try again."
        ),
    },
    
    "list_directory": {
        "not a directory": (
            "Path is a file, not a directory.",
            "Use read_file to read file contents, or specify a directory path."
        ),
        "not found": (
            "Directory not found.",
            "Check the parent path with list_directory on a parent directory."
        ),
        "permission denied": (
            "Permission denied to list this directory.",
            "Try a different directory path."
        ),
        "security": (
            "Path access denied for security.",
            "Use paths in allowed directories."
        ),
    },
    
    "http_get": {
        "connection": (
            "Could not connect to the URL.",
            "Check if the URL is correct and the server is accessible."
        ),
        "http error 4": (
            "Client error (4xx).",
            "Check the URL and parameters. The resource may not exist."
        ),
        "http error 5": (
            "Server error (5xx).",
            "The server encountered an error. Try again later."
        ),
        "ssrf": (
            "URL blocked for security (SSRF protection).",
            "Only external public URLs are allowed."
        ),
        "timeout": (
            "Request timed out.",
            "The server took too long to respond. Try a simpler request."
        ),
        "too large": (
            "Response too large and was truncated.",
            "Use a more specific URL or query to get smaller responses."
        ),
    },
    
    "python_repl": {
        "syntaxerror": (
            "Python syntax error.",
            "Check for missing quotes, parentheses, or incorrect indentation."
        ),
        "nameerror": (
            "Undefined variable or function.",
            "Available: math, json, re, datetime, collections, itertools"
        ),
        "importerror": (
            "Module not available in sandbox.",
            "Only safe modules are allowed: math, json, re, datetime, collections, itertools"
        ),
        "timeout": (
            "Code execution timed out.",
            "Simplify the code or reduce iterations."
        ),
        "permission": (
            "File/network access blocked in sandbox.",
            "The Python REPL is sandboxed. No file or network operations."
        ),
    },
    
    "get_time": {
        "unknown timezone": (
            "Unknown timezone identifier.",
            "Use IANA timezone names like 'UTC', 'America/New_York', 'Europe/London'"
        ),
    },
    
    "parse_json": {
        "expecting": (
            "Invalid JSON format.",
            "Check for missing quotes, commas, or brackets."
        ),
        "unterminated": (
            "JSON string not properly closed.",
            "Ensure all strings have matching quotes."
        ),
    },
}

# Generic hints that apply to any tool
GENERIC_ERROR_HINTS = {
    "error": (
        "An error occurred.",
        "Try a different approach or check the arguments."
    ),
    "unknown tool": (
        "Tool not found.",
        "Check available tools and use the exact tool name."
    ),
    "missing": (
        "Missing required argument.",
        "Check the tool's required parameters."
    ),
}


# ============================================================================
# Tool Alternatives Mapping
# ============================================================================

# When a tool fails, suggest these alternatives
TOOL_ALTERNATIVES = {
    "calculator": ["python_repl"],
    "shell": ["python_repl"],
    "read_file": ["shell"],  # Can use cat via shell
    "write_file": ["shell"],  # Can use echo via shell
    "http_get": [],  # No direct alternative
    "python_repl": ["calculator"],
    "get_time": ["python_repl"],  # datetime in Python
    "get_date": ["python_repl"],
    "list_directory": ["shell"],
}


# ============================================================================
# Error Recovery State
# ============================================================================

@dataclass
class ToolFailureRecord:
    """Record of a single tool failure."""
    tool_name: str
    error_message: str
    step: int
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorRecoveryTracker:
    """
    Tracks error recovery state to prevent infinite loops.
    
    Tracks:
    - Consecutive failures per tool
    - Total failures across all tools
    - Failure history for analysis
    
    Features:
    - Suggests alternative tools after repeated failures
    - Provides tool-specific hints for common errors
    - Terminates loop when failure threshold exceeded
    """
    
    # Maximum consecutive failures for same tool before suggesting alternatives
    max_consecutive_failures: int = DEFAULT_MAX_CONSECUTIVE_FAILURES
    
    # Maximum total failures before suggesting loop termination
    max_total_failures: int = DEFAULT_MAX_TOTAL_FAILURES
    
    # Track consecutive failures per tool: tool_name -> count
    consecutive_failures: dict[str, int] = field(default_factory=dict)
    
    # Track all failure records
    failure_history: list[ToolFailureRecord] = field(default_factory=list)
    
    # Track total failures in current run
    total_failures: int = 0
    
    # Track total successes (for resetting consecutive failures)
    last_success_tool: str | None = None
    
    def record_failure(
        self, 
        tool_name: str, 
        error_message: str, 
        step: int,
        arguments: dict[str, Any] | None = None
    ) -> None:
        """
        Record a tool failure.
        
        Args:
            tool_name: Name of the tool that failed
            error_message: Error message from the tool
            step: Current step number
            arguments: Arguments passed to the tool (optional)
        """
        # Increment consecutive failures for this tool
        self.consecutive_failures[tool_name] = self.consecutive_failures.get(tool_name, 0) + 1
        self.total_failures += 1
        
        # Record in history
        self.failure_history.append(ToolFailureRecord(
            tool_name=tool_name,
            error_message=error_message,
            step=step,
            arguments=arguments or {}
        ))
    
    def record_success(self, tool_name: str) -> None:
        """
        Record a tool success (resets consecutive failures for that tool).
        
        Args:
            tool_name: Name of the tool that succeeded
        """
        # Reset consecutive failures for this tool
        if tool_name in self.consecutive_failures:
            del self.consecutive_failures[tool_name]
        self.last_success_tool = tool_name
    
    def get_consecutive_failures(self, tool_name: str) -> int:
        """Get the number of consecutive failures for a tool."""
        return self.consecutive_failures.get(tool_name, 0)
    
    def should_suggest_alternative(self, tool_name: str) -> bool:
        """Check if we should suggest an alternative tool."""
        return self.get_consecutive_failures(tool_name) >= self.max_consecutive_failures
    
    def should_terminate(self) -> bool:
        """Check if we've exceeded failure thresholds."""
        return self.total_failures >= self.max_total_failures
    
    def get_alternative_tools(self, tool_name: str) -> list[str]:
        """Get suggested alternative tools for a failing tool."""
        return TOOL_ALTERNATIVES.get(tool_name, [])
    
    def get_error_hint(self, tool_name: str, error_message: str) -> tuple[str, str] | None:
        """
        Get a tool-specific hint for an error.
        
        Args:
            tool_name: Name of the tool
            error_message: Error message from the tool
            
        Returns:
            Tuple of (hint, suggestion) or None if no specific hint
        """
        error_lower = error_message.lower()
        
        # Check tool-specific hints
        tool_hints = TOOL_ERROR_HINTS.get(tool_name, {})
        for pattern, (hint, suggestion) in tool_hints.items():
            if re.search(pattern, error_lower):
                return (hint, suggestion)
        
        # Check generic hints
        for pattern, (hint, suggestion) in GENERIC_ERROR_HINTS.items():
            if pattern in error_lower:
                return (hint, suggestion)
        
        return None
    
    def build_recovery_message(
        self, 
        tool_name: str, 
        error_message: str,
        available_tools: list[str]
    ) -> str:
        """
        Build a comprehensive recovery message for a tool failure.
        
        Args:
            tool_name: Name of the failing tool
            error_message: Error message from the tool
            available_tools: List of available tool names
            
        Returns:
            Formatted recovery message for the model
        """
        parts = []
        
        # Get consecutive failure count
        consecutive = self.get_consecutive_failures(tool_name)
        
        # Get tool-specific hint
        hint = self.get_error_hint(tool_name, error_message)
        
        # Build the message
        if consecutive >= self.max_consecutive_failures:
            # Suggest alternatives
            alternatives = self.get_alternative_tools(tool_name)
            available_alternatives = [t for t in alternatives if t in available_tools]
            
            parts.append(f"⚠️ Tool '{tool_name}' has failed {consecutive} times in a row.")
            
            if available_alternatives:
                parts.append(f"Consider using an alternative: {', '.join(available_alternatives)}")
            
            if hint:
                hint_text, suggestion = hint
                parts.append(f"Hint: {hint_text}")
                parts.append(f"Suggestion: {suggestion}")
            else:
                parts.append("Try a different approach or check the tool arguments.")
                
        elif consecutive >= 2:
            # Warning about repeated failures
            parts.append(f"⚠️ Tool '{tool_name}' has failed {consecutive} times.")
            
            if hint:
                hint_text, suggestion = hint
                parts.append(f"Hint: {hint_text}")
                parts.append(f"Suggestion: {suggestion}")
        else:
            # First failure - just provide hint
            if hint:
                hint_text, suggestion = hint
                parts.append(f"Hint: {hint_text}")
                parts.append(f"Suggestion: {suggestion}")
        
        return "\n".join(parts)
    
    def reset(self) -> None:
        """Reset all tracking state."""
        self.consecutive_failures.clear()
        self.failure_history.clear()
        self.total_failures = 0
        self.last_success_tool = None


# ============================================================================
# Observation Enhancement
# ============================================================================

def build_enhanced_observation(
    tool_name: str,
    result: str,
    tracker: ErrorRecoveryTracker,
    available_tools: list[str],
    is_error: bool = False
) -> str:
    """
    Build an enhanced observation message with tool-specific hints.
    
    Args:
        tool_name: Name of the tool that was executed
        result: Result string from the tool
        tracker: Error recovery tracker instance
        available_tools: List of available tool names
        is_error: Whether the result is an error
        
    Returns:
        Enhanced observation message with contextual guidance
    """
    # Start with the result
    if is_error:
        observation = f"Observation: {result}"
    else:
        observation = f"Observation: {result}"
    
    # Add guidance based on result type
    if is_error or result.lower().startswith("error"):
        # Record failure and build recovery message
        recovery_msg = tracker.build_recovery_message(
            tool_name, 
            result, 
            available_tools
        )
        
        if recovery_msg:
            observation = f"{observation}\n\n{recovery_msg}"
        else:
            # Generic error recovery
            observation = f"{observation}\n\nNote: Try a different approach. Check the tool arguments and try again."
    else:
        # Success - record it and prompt for Final Answer
        tracker.record_success(tool_name)
        
        # Check if this looks like a simple result that should end the loop
        if _is_simple_result(result, tool_name):
            observation = f"{observation}\n\nNow output: Final Answer: <the result>"
        else:
            # Complex result - model may need to process further
            observation = f"{observation}\n\nIf you have the answer, output: Final Answer: <your answer>\nIf you need more information, use another tool."
    
    return observation


def _is_simple_result(result: str, tool_name: str) -> bool:
    """
    Determine if a result is simple enough to immediately prompt for Final Answer.
    
    Simple results are:
    - Short numeric values
    - Date/time strings
    - Single-line results under 100 chars
    
    Complex results are:
    - File contents
    - Directory listings
    - Long outputs
    """
    # Simple tools that typically produce direct answers
    simple_tools = {"calculator", "get_time", "get_date", "count_words", "count_chars"}
    if tool_name in simple_tools:
        return True
    
    # Check result length
    if len(result) > 200:
        return False
    
    # Check if result is a simple value (number, short string)
    result_stripped = result.strip()
    
    # Numeric result
    if re.match(r'^-?\d+\.?\d*$', result_stripped):
        return True
    
    # Date/time format
    if re.match(r'^\d{4}-\d{2}-\d{2}', result_stripped):
        return True
    
    # Time format
    if re.match(r'^\d{2}:\d{2}', result_stripped):
        return True
    
    # Short single-line result
    if '\n' not in result_stripped and len(result_stripped) < 100:
        return True
    
    return False


# ============================================================================
# Utility Functions
# ============================================================================

def is_error_result(result: str) -> bool:
    """Check if a tool result indicates an error."""
    if not result:
        return True
    result_lower = result.lower()
    return (
        result_lower.startswith("error") or
        result_lower.startswith("security error") or
        result_lower.startswith("failed") or
        "error:" in result_lower or
        "exception" in result_lower or
        result_lower.startswith("blocked")
    )


def extract_error_type(error_message: str) -> str:
    """Extract a normalized error type from an error message."""
    error_lower = error_message.lower()
    
    # Common error patterns
    patterns = [
        (r"syntax", "syntax_error"),
        (r"not found", "not_found"),
        (r"permission denied", "permission_denied"),
        (r"timeout", "timeout"),
        (r"connection", "connection_error"),
        (r"blocked", "blocked"),
        (r"security", "security_error"),
        (r"invalid", "invalid_input"),
        (r"missing", "missing_argument"),
    ]
    
    for pattern, error_type in patterns:
        if re.search(pattern, error_lower):
            return error_type
    
    return "unknown_error"


__all__ = [
    "ErrorRecoveryTracker",
    "ToolFailureRecord",
    "build_enhanced_observation",
    "is_error_result",
    "extract_error_type",
    "TOOL_ERROR_HINTS",
    "TOOL_ALTERNATIVES",
    "DEFAULT_MAX_CONSECUTIVE_FAILURES",
    "DEFAULT_MAX_TOTAL_FAILURES",
]