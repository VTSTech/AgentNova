"""
⚛️ AgentNova — CLI
Command-line interface for AgentNova.

Status: Alpha

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

from .agent import Agent
from .agent_mode import AgentMode
from .orchestrator import Orchestrator, AgentCard
from .tools import make_builtin_registry
from .backends import get_backend, get_default_backend, OllamaBackend
from .config import get_config, AGENTNOVA_BACKEND, OLLAMA_BASE_URL, BITNET_BASE_URL
from .model_discovery import match_models, get_models


# ============================================================================
# Colors & Styling
# ============================================================================

class Color:
    """ANSI color codes for terminal output."""
    # Reset
    RESET = "\033[0m"
    
    # Basic colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Bright colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    
    # Styles
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    
    @classmethod
    def supports_color(cls) -> bool:
        """Check if terminal supports color."""
        # Check for NO_COLOR env var
        if os.environ.get("NO_COLOR"):
            return False
        # Check if stdout is a terminal
        if not sys.stdout.isatty():
            return False
        # Windows check
        if os.name == "nt":
            return os.environ.get("ANSICON") or "WT_SESSION" in os.environ or True
        return True


# Global color enabled flag
_COLOR_ENABLED = Color.supports_color()


def c(text: str, *colors: str) -> str:
    """Apply colors to text if color is enabled."""
    if not _COLOR_ENABLED or not colors:
        return text
    return "".join(colors) + text + Color.RESET


def dim(text: str) -> str:
    """Dim text."""
    return c(text, Color.DIM)


def bold(text: str) -> str:
    """Bold text."""
    return c(text, Color.BOLD)


def cyan(text: str) -> str:
    """Cyan text."""
    return c(text, Color.CYAN)


def green(text: str) -> str:
    """Green text."""
    return c(text, Color.GREEN)


def yellow(text: str) -> str:
    """Yellow text."""
    return c(text, Color.YELLOW)


def red(text: str) -> str:
    """Red text."""
    return c(text, Color.RED)


def magenta(text: str) -> str:
    """Magenta text."""
    return c(text, Color.MAGENTA)


def blue(text: str) -> str:
    """Blue text."""
    return c(text, Color.BLUE)


def bright_cyan(text: str) -> str:
    """Bright cyan text."""
    return c(text, Color.BRIGHT_CYAN)


def bright_green(text: str) -> str:
    """Bright green text."""
    return c(text, Color.BRIGHT_GREEN)


def bright_yellow(text: str) -> str:
    """Bright yellow text."""
    return c(text, Color.BRIGHT_YELLOW)


def bright_magenta(text: str) -> str:
    """Bright magenta text."""
    return c(text, Color.BRIGHT_MAGENTA)


def bright_red(text: str) -> str:
    """Bright red text."""
    return c(text, Color.BRIGHT_RED)


# ANSI escape code pattern for stripping
_ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m')


def visible_len(text: str) -> int:
    """Get the visible length of text (excluding ANSI codes)."""
    return len(_ANSI_ESCAPE.sub('', text))


def pad_colored(text: str, width: int, align: str = 'left') -> str:
    """Pad colored text to a given visible width.
    
    Args:
        text: Text that may contain ANSI color codes
        width: Target visible width
        align: 'left', 'right', or 'center'
    
    Returns:
        Text padded with spaces to reach the target visible width
    """
    visible = visible_len(text)
    padding = width - visible
    
    if padding <= 0:
        return text
    
    if align == 'left':
        return text + ' ' * padding
    elif align == 'right':
        return ' ' * padding + text
    else:  # center
        left = padding // 2
        right = padding - left
        return ' ' * left + text + ' ' * right


# ============================================================================
# ASCII Banner
# ============================================================================

BANNER_ATOM_BRAILLE = """
\x1b[96m⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⠿⠛⢷⣦⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\x1b[0m  \x1b[95;1mAgentNova\x1b[0m
\x1b[96m⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⡿⠃⠀⠀⠀⠙⣷⡀⠀⠀⢀⣀⠀⠀⠀⠀⠀\x1b[0m  \x1b[2mAutonomous Agents with Local LLMs\x1b[0m
\x1b[96m⠀⠀⠀⣀⣀⣀⣀⣀⠀⢀⣿⠃⠀⠀⠀⠀⠀⠸⣷⠀⣰⣿⣿⣿⣆⣀⠀⠀\x1b[0m
\x1b[96m⠀⣰⡿⠛⠉⠉⠉⠛⠻⣿⣷⣤⣀⠀⠀⠀⣀⣤⣿⡿⠿⣿⣿⣿⠏⠛⣷⡄\x1b[0m  \x1b[2mStatus:\x1b[0m \x1b[33mAlpha\x1b[0m
\x1b[96m⠀⣿⣇⣀⠀⠀⠀⠀⢀⣿⠅⠉⢛⣿⣶⣿⡋⠉⠘⣿⠀⠀⠉⠀⠀⠀⢸⡇\x1b[0m  \x1b[2mhttps://www.vts-tech.org\x1b[0m
\x1b[96m⢸⣿⣿⣿⣧⠀⠀⠀⢸⣟⣠⣾⠟⠋⠀⠙⠻⣶⣄⣿⡄⠀⠀⠀⠀⢀⣾⠃\x1b[0m
\x1b[96m⠘⢿⣿⣿⣏⠀⠀⢀⣼⡿⠋⣠⣶⣿⣿⣿⣦⡌⠙⣿⣧⡀⠀⠀⣠⣾⠋⠀\x1b[0m
\x1b[96m⠀⠀⠀⠈⢻⣦⣴⠟⣹⡇⢰⣿⣿⣿⣿⣿⣿⣿⡄⢸⡟⠻⣦⣴⠟⠁⠀⠀\x1b[0m
\x1b[96m⠀⠀⠀⢀⣴⡟⢿⣦⣿⡗⠸⣿⣿⣿⣿⣿⣿⣿⠃⢸⣇⣴⡿⢿⣦⡀⠀⠀\x1b[0m
\x1b[96m⠀⠀⢠⣾⠋⠀⠀⠙⢿⣧⣄⠙⢿⣿⣿⣿⠿⠃⣠⣿⡟⠁⠀⠀⠙⣷⡄⠀\x1b[0m
\x1b[96m⠀⢠⣿⠁⠀⠀⠀⠀⢸⣯⠛⢷⣦⣀⠀⣠⣴⡿⠋⣿⠃⠀⠀⠀⠀⠘⣿⡄\x1b[0m
\x1b[96m⠀⣾⡇⠀⠀⠀⠀⠀⠈⣿⠀⢀⣩⣿⣿⣿⣅⡀⢠⣿⠀⠀⠀⠀⠀⠀⢸⡇\x1b[0m
\x1b[96m⠀⠹⣷⣄⣀⣀⣀⣠⣤⣿⡿⠟⠋⠁⠀⠈⠙⠻⣿⣷⣤⣄⣀⣀⣀⣠⣾⠇\x1b[0m
\x1b[96m⠀⠀⠈⠉⠛⠛⠛⠉⠉⠘⣿⡀⠀⠀⠀⢀⣴⣶⣿⣄⠈⠉⠙⠛⠛⠋⠁⠀\x1b[0m
\x1b[96m⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣷⡀⠀⠀⢸⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀\x1b[0m
\x1b[96m⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⠿⣦⣤⣶⠟⠛⠛⠁⠀⠀⠀⠀⠀⠀⠀⠀\x1b[0m
"""

BANNER_ATOM_PLAIN = """
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⠿⠛⢷⣦⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀  AgentNova
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⡿⠃⠀⠀⠀⠙⣷⡀⠀⠀⢀⣀⠀⠀⠀⠀⠀  Autonomous Agents with Local LLMs
⠀⠀⠀⣀⣀⣀⣀⣀⠀⢀⣿⠃⠀⠀⠀⠀⠀⠸⣷⠀⣰⣿⣿⣿⣆⣀⠀⠀
⠀⣰⡿⠛⠉⠉⠉⠛⠻⣿⣷⣤⣀⠀⠀⠀⣀⣤⣿⡿⠿⣿⣿⣿⠏⠛⣷⡄  Status: Alpha
⠀⣿⣇⣀⠀⠀⠀⠀⢀⣿⠅⠉⢛⣿⣶⣿⡋⠉⠘⣿⠀⠀⠉⠀⠀⠀⢸⡇  https://www.vts-tech.org
⢸⣿⣿⣿⣧⠀⠀⠀⢸⣟⣠⣾⠟⠋⠀⠙⠻⣶⣄⣿⡄⠀⠀⠀⠀⢀⣾⠃
⠘⢿⣿⣿⣏⠀⠀⢀⣼⡿⠋⣠⣶⣿⣿⣿⣦⡌⠙⣿⣧⡀⠀⠀⣠⣾⠋⠀
⠀⠀⠀⠈⢻⣦⣴⠟⣹⡇⢰⣿⣿⣿⣿⣿⣿⣿⡄⢸⡟⠻⣦⣴⠟⠁⠀⠀
⠀⠀⠀⢀⣴⡟⢿⣦⣿⡗⠸⣿⣿⣿⣿⣿⣿⣿⠃⢸⣇⣴⡿⢿⣦⡀⠀⠀
⠀⠀⢠⣾⠋⠀⠀⠙⢿⣧⣄⠙⢿⣿⣿⣿⠿⠃⣠⣿⡟⠁⠀⠀⠙⣷⡄⠀
⠀⢠⣿⠁⠀⠀⠀⠀⢸⣯⠛⢷⣦⣀⠀⣠⣴⡿⠋⣿⠃⠀⠀⠀⠀⠘⣿⡄
⠀⣾⡇⠀⠀⠀⠀⠀⠈⣿⠀⢀⣩⣿⣿⣿⣅⡀⢠⣿⠀⠀⠀⠀⠀⠀⢸⡇
⠀⠹⣷⣄⣀⣀⣀⣠⣤⣿⡿⠟⠋⠁⠀⠈⠙⠻⣿⣷⣤⣄⣀⣀⣀⣠⣾⠇
⠀⠀⠈⠉⠛⠛⠛⠉⠉⠘⣿⡀⠀⠀⠀⢀⣴⣶⣿⣄⠈⠉⠙⠛⠛⠋⠁⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣷⡀⠀⠀⢸⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⠿⣦⣤⣶⠟⠛⠛⠁⠀⠀⠀⠀⠀⠀⠀⠀
"""


def print_banner() -> None:
    """Print the AgentNova ASCII banner."""
    if _COLOR_ENABLED:
        print(BANNER_ATOM_BRAILLE)
    else:
        print(BANNER_ATOM_PLAIN)


# ============================================================================
# Model Matching
# ============================================================================

def resolve_model_pattern(
    pattern: str,
    backend_name: str = "ollama",
    allow_multiple: bool = False,
) -> str | list[str]:
    """
    Resolve a model pattern to actual model name(s).
    
    Shows helpful output when multiple models match.
    
    Parameters
    ----------
    pattern : str
        Model name or pattern (e.g., "qwen", "g", ":0.5b")
    backend_name : str
        Backend to use for model discovery
    allow_multiple : bool
        If True, return all matches; if False, return first match
    
    Returns
    -------
    str or list[str]
        Resolved model name(s), or empty list if no matches
    """
    backend = get_backend(backend_name)
    matches = match_models(pattern, backend=backend)
    
    if not matches:
        print(f"{red('Error:')} No models found matching '{pattern}'")
        available = get_models(client=backend)
        if available:
            print(f"\n{dim('Available models:')}")
            for m in sorted(available)[:10]:
                print(f"  {cyan(m)}")
            if len(available) > 10:
                print(f"  {dim(f'... and {len(available) - 10} more')}")
        return [] if allow_multiple else ""
    
    # If allow_multiple, always return a list
    if allow_multiple:
        return matches
    
    # Single match - return as string
    if len(matches) == 1:
        return matches[0]
    
    # Multiple matches - show and use first
    print(f"{yellow('Multiple models match')} '{pattern}':")
    for i, m in enumerate(matches[:5]):
        marker = green("→") if i == 0 else " "
        print(f"  {marker} {cyan(m)}")
    if len(matches) > 5:
        print(f"    {dim(f'... and {len(matches) - 5} more')}")
    print(f"{dim('Using first match:')} {cyan(matches[0])}")
    return matches[0]


# ============================================================================
# CLI Commands
# ============================================================================


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="agentnova",
        description="⚛️ AgentNova - Autonomous agents with local LLMs (Alpha)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a single prompt")
    run_parser.add_argument("prompt", help="The prompt to process")
    run_parser.add_argument("-m", "--model", default=None, help="Model to use")
    run_parser.add_argument("--tools", default="calculator", help="Comma-separated tool list")
    run_parser.add_argument("--backend", choices=["ollama", "bitnet"], default=None, help="Backend to use")
    run_parser.add_argument("--stream", action="store_true", help="Stream output")
    run_parser.add_argument("--debug", action="store_true", help="Enable debug output")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    run_parser.add_argument("--soul", default=None, help="Path to Soul Spec package (disabled by default)")
    run_parser.add_argument("--soul-level", type=int, default=2, choices=[1, 2, 3],
                           help="Soul progressive disclosure level (1=quick, 2=full, 3=deep)")
    run_parser.add_argument("--num-ctx", type=int, default=None, dest="num_ctx",
                           help="Context window size in tokens (Ollama default is 2048)")
    run_parser.add_argument("--timeout", type=int, default=None,
                           help="Request timeout in seconds (default: 120)")
    run_parser.add_argument("--force-react", action="store_true", help="Force ReAct mode for tool calling")
    run_parser.add_argument("--acp", action="store_true", help="Enable ACP logging to Agent Control Panel")
    run_parser.add_argument("--acp-url", default=None, help="ACP server URL (default: from config)")

    # Chat command
    chat_parser = subparsers.add_parser("chat", help="Interactive chat mode")
    chat_parser.add_argument("-m", "--model", default=None, help="Model to use")
    chat_parser.add_argument("--tools", default="", help="Comma-separated tool list")
    chat_parser.add_argument("--backend", choices=["ollama", "bitnet"], default=None, help="Backend to use")
    chat_parser.add_argument("--debug", action="store_true", help="Enable debug output")
    chat_parser.add_argument("--force-react", action="store_true", help="Force ReAct mode")
    chat_parser.add_argument("--soul", default=None, help="Path to Soul Spec package (disabled by default)")
    chat_parser.add_argument("--soul-level", type=int, default=2, choices=[1, 2, 3],
                           help="Soul progressive disclosure level (1=quick, 2=full, 3=deep)")
    chat_parser.add_argument("--num-ctx", type=int, default=None, dest="num_ctx",
                           help="Context window size in tokens (Ollama default is 2048)")
    chat_parser.add_argument("--timeout", type=int, default=None,
                           help="Request timeout in seconds (default: 120)")
    chat_parser.add_argument("--acp", action="store_true", help="Enable ACP logging to Agent Control Panel")
    chat_parser.add_argument("--acp-url", default=None, help="ACP server URL (default: from config)")

    # Agent command
    agent_parser = subparsers.add_parser("agent", help="Autonomous agent mode")
    agent_parser.add_argument("-m", "--model", default=None, help="Model to use")
    agent_parser.add_argument("--tools", default="calculator,shell,write_file", help="Comma-separated tool list")
    agent_parser.add_argument("--backend", choices=["ollama", "bitnet"], default=None, help="Backend to use")
    agent_parser.add_argument("--debug", action="store_true", help="Enable debug output")
    agent_parser.add_argument("--force-react", action="store_true", help="Force ReAct mode for tool calling")
    agent_parser.add_argument("--soul", default=None, help="Path to Soul Spec package (disabled by default)")
    agent_parser.add_argument("--soul-level", type=int, default=2, choices=[1, 2, 3],
                           help="Soul progressive disclosure level (1=quick, 2=full, 3=deep)")
    agent_parser.add_argument("--num-ctx", type=int, default=None, dest="num_ctx",
                           help="Context window size in tokens (Ollama default is 2048)")
    agent_parser.add_argument("--timeout", type=int, default=None,
                           help="Request timeout in seconds (default: 120)")
    agent_parser.add_argument("--acp", action="store_true", help="Enable ACP logging to Agent Control Panel")
    agent_parser.add_argument("--acp-url", default=None, help="ACP server URL (default: from config)")

    # Models command
    models_parser = subparsers.add_parser("models", help="List available models")
    models_parser.add_argument("--backend", choices=["ollama", "bitnet"], default=None, help="Backend to use")
    models_parser.add_argument("--tool-support", action="store_true", help="Force re-test tool calling support")
    models_parser.add_argument("--no-cache", action="store_true", help="Ignore cached tool support results")

    # Tools command
    subparsers.add_parser("tools", help="List available tools")

    # Test command
    test_parser = subparsers.add_parser("test", help="Run diagnostic tests")
    test_parser.add_argument("test_id", nargs="?", default="all", 
                             help="Test to run: 00, 01, 02, ... 11, or 'all' (default: all)")
    test_parser.add_argument("-m", "--model", default=None, 
                             help="Model to test (supports patterns: 'qwen', 'g', ':0.5b')")
    test_parser.add_argument("--backend", choices=["ollama", "bitnet"], default=None, help="Backend to use")
    test_parser.add_argument("--debug", action="store_true", help="Enable debug output")
    test_parser.add_argument("--list", action="store_true", help="List available tests")
    test_parser.add_argument("--acp", action="store_true", help="Enable ACP logging to Agent Control Panel")
    test_parser.add_argument("--acp-url", default=None, help="ACP server URL (default: http://localhost:8766)")
    test_parser.add_argument("--use-mf-sys", action="store_true", dest="use_modelfile_system",
                             help="Use the model's Modelfile system prompt instead of custom test prompts")
    test_parser.add_argument("--num-ctx", type=int, default=None, dest="num_ctx",
                           help="Context window size in tokens (Ollama default is 2048)")
    test_parser.add_argument("--timeout", type=int, default=None,
                           help="Request timeout in seconds (default: 120)")
    test_parser.add_argument("--force-react", action="store_true", help="Force ReAct mode for tool calling")

    # Version command
    subparsers.add_parser("version", help="Show version information")

    # Config command
    config_parser = subparsers.add_parser("config", help="Show current configuration")
    config_parser.add_argument("--urls", action="store_true", help="Show only URLs")

    # Modelfile command
    modelfile_parser = subparsers.add_parser("modelfile", help="Show model's Modelfile info")
    modelfile_parser.add_argument("-m", "--model", default=None, help="Model to inspect")
    modelfile_parser.add_argument("--backend", choices=["ollama", "bitnet"], default=None, help="Backend to use")

    # Skills command
    subparsers.add_parser("skills", help="List available skills")
    
    # Soul command
    soul_parser = subparsers.add_parser("soul", help="Inspect a Soul Spec package")
    soul_parser.add_argument("path", help="Path to soul package directory or soul.json")
    soul_parser.add_argument("--level", type=int, default=2, choices=[1, 2, 3],
                            help="Progressive disclosure level (1=quick, 2=full, 3=deep)")
    soul_parser.add_argument("--validate", action="store_true", help="Run validation checks")
    soul_parser.add_argument("--prompt", action="store_true", help="Show generated system prompt")

    return parser


def _init_acp(args: argparse.Namespace, config, agent_name: str = "AgentNova") -> tuple:
    """
    Initialize ACP plugin if requested.
    
    Returns:
        tuple: (acp_plugin or None, should_stop bool)
    """
    if not getattr(args, 'acp', False):
        return None, False
    
    try:
        from .acp_plugin import ACPPlugin
        acp_url = getattr(args, 'acp_url', None) or config.acp_base_url
        acp = ACPPlugin(
            base_url=acp_url,
            agent_name=agent_name,
            model_name=getattr(args, 'model', None) or config.default_model,
            debug=getattr(args, 'debug', False),
        )
        # Bootstrap ACP connection
        bootstrap_result = acp.bootstrap()
        if bootstrap_result.get("stop_flag"):
            print(f"{red('Error:')} ACP STOP flag is set: {bootstrap_result.get('warnings')}")
            return None, True
        return acp, False
    except ImportError:
        print(f"{yellow('Warning:')} ACP plugin not available, continuing without ACP logging")
        return None, False
    except Exception as e:
        print(f"{yellow('Warning:')} Failed to connect to ACP: {e}")
        return None, False


def cmd_run(args: argparse.Namespace) -> int:
    """Execute the run command."""
    config = get_config()
    model = args.model or config.default_model
    backend_name = args.backend or config.backend

    # Initialize ACP if requested
    acp, should_stop = _init_acp(args, config, "AgentNova-Run")
    if should_stop:
        return 1

    timeout = getattr(args, 'timeout', None)
    backend = get_backend(backend_name, timeout=timeout)

    # Build tools
    if args.tools:
        all_tools = make_builtin_registry()
        tool_names = [t.strip() for t in args.tools.split(",")]
        tools = all_tools.subset(tool_names)
    else:
        tools = None

    agent = Agent(
        model=model,
        tools=tools,
        backend=backend,
        debug=args.debug,
        soul=getattr(args, 'soul', None),
        soul_level=getattr(args, 'soul_level', 2),
        num_ctx=getattr(args, 'num_ctx', None) or config.num_ctx,
    )

    # Log to ACP
    if acp:
        acp.log_chat("user", args.prompt)

    result = agent.run(args.prompt)
    print(result.final_answer)

    # Log result to ACP
    if acp:
        acp.log_chat("assistant", result.final_answer)
        acp.a2a_unregister()

    if args.verbose:
        print(f"\n⏱️ Completed in {result.total_ms:.0f}ms")
        print(f"📊 Tokens: {result.total_tokens}, Steps: {result.iterations}")

    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    """Execute the chat command."""
    config = get_config()
    model = args.model or config.default_model
    backend_name = args.backend or config.backend

    # Initialize ACP if requested
    acp, should_stop = _init_acp(args, config, "AgentNova-Chat")
    if should_stop:
        return 1

    timeout = getattr(args, 'timeout', None)
    backend = get_backend(backend_name, timeout=timeout)

    if args.tools:
        all_tools = make_builtin_registry()
        tool_names = [t.strip() for t in args.tools.split(",")]
        tools = all_tools.subset(tool_names)
    else:
        tools = None

    agent = Agent(
        model=model,
        tools=tools,
        backend=backend,
        force_react=args.force_react,
        debug=args.debug,
        soul=getattr(args, 'soul', None),
        soul_level=getattr(args, 'soul_level', 2),
        num_ctx=getattr(args, 'num_ctx', None) or config.num_ctx,
    )

    print_banner()
    print(f"{bright_magenta('Chat Mode')} — {cyan(model)}")
    print(f"{dim('Backend:')} {backend_name} ({dim(backend.base_url)})")
    if agent.soul:
        print(f"{dim('Soul:')} {green(agent.soul.display_name)} v{agent.soul.version}")
    if agent.num_ctx:
        ctx_display = f"{agent.num_ctx // 1024}K" if agent.num_ctx >= 1024 else str(agent.num_ctx)
        print(f"{dim('Context:')} {yellow(ctx_display)}")
    if timeout:
        print(f"{dim('Timeout:')} {yellow(str(timeout) + 's')}")
    if acp:
        print(f"{dim('ACP:')} {green('✓ Connected')} ({acp.base_url})")
    print(f"{dim('Status:')} {yellow('Alpha')}")
    print("Type '/quit' to exit, '/help' for commands\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            if acp:
                acp.log_chat("user", "/quit")
                acp.a2a_unregister()
            print(bright_cyan("👋 Goodbye!"))
            break

        if user_input == "/help":
            print(f"Commands: {cyan('/quit')}, {cyan('/help')}, {cyan('/clear')}, {cyan('/status')}")
            continue

        if user_input == "/clear":
            agent.clear_memory()
            print(green("Memory cleared."))
            continue

        if user_input == "/status":
            print(f"Model: {cyan(agent.model)}")
            print(f"Tool support: {green(agent._tool_support.value) if hasattr(agent._tool_support, 'value') else agent._tool_support}")
            print(f"Memory turns: {yellow(str(len(agent.memory)))}")
            continue

        # Log user message to ACP
        if acp:
            acp.log_chat("user", user_input)

        result = agent.run(user_input)
        print(f"\n{bright_magenta('Assistant')}: {result.final_answer}\n")

        # Log assistant response to ACP
        if acp:
            acp.log_chat("assistant", result.final_answer)

    return 0


def cmd_agent(args: argparse.Namespace) -> int:
    """Execute the agent command."""
    config = get_config()
    model = args.model or config.default_model
    backend_name = args.backend or config.backend

    # Initialize ACP if requested
    acp, should_stop = _init_acp(args, config, "AgentNova-Agent")
    if should_stop:
        return 1

    timeout = getattr(args, 'timeout', None)
    backend = get_backend(backend_name, timeout=timeout)

    if args.tools:
        all_tools = make_builtin_registry()
        tool_names = [t.strip() for t in args.tools.split(",")]
        tools = all_tools.subset(tool_names)
    else:
        tools = None

    agent = Agent(
        model=model,
        tools=tools,
        backend=backend,
        debug=args.debug,
        soul=getattr(args, 'soul', None),
        soul_level=getattr(args, 'soul_level', 2),
        num_ctx=getattr(args, 'num_ctx', None) or config.num_ctx,
    )

    agent_mode = AgentMode(agent, verbose=True)

    print_banner()
    print(f"{bright_magenta('Agent Mode')} — {cyan(model)}")
    print(f"{dim('Backend:')} {backend_name} ({dim(backend.base_url)})")
    if agent.soul:
        print(f"{dim('Soul:')} {green(agent.soul.display_name)} v{agent.soul.version}")
    if agent.num_ctx:
        ctx_display = f"{agent.num_ctx // 1024}K" if agent.num_ctx >= 1024 else str(agent.num_ctx)
        print(f"{dim('Context:')} {yellow(ctx_display)}")
    if timeout:
        print(f"{dim('Timeout:')} {yellow(str(timeout) + 's')}")
    if acp:
        print(f"{dim('ACP:')} {green('✓ Connected')} ({acp.base_url})")
    print(f"{dim('Status:')} {yellow('Alpha')}")
    print("Give the agent a goal to accomplish autonomously.")
    print(f"Commands: {cyan('/status')}, {cyan('/pause')}, {cyan('/resume')}, {cyan('/stop')}, {cyan('/quit')}\n")

    while True:
        try:
            user_input = input("Goal: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            cmd = user_input.split()[0]

            if cmd == "/quit":
                if acp:
                    acp.log_chat("user", "/quit")
                    acp.a2a_unregister()
                print(bright_cyan("👋 Goodbye!"))
                break
            elif cmd == "/status":
                status = agent_mode.get_status()
                print(f"State: {cyan(status['state'])}")
                if "goal" in status and status["goal"]:
                    print(f"Goal: {bright_yellow(status['goal'])}")
                    if "progress_percent" in status:
                        pct = status['progress_percent']
                        pct_str = green(f"{pct:.0f}%") if pct >= 50 else yellow(f"{pct:.0f}%")
                        print(f"Progress: {pct_str}")
                continue
            elif cmd == "/pause":
                success, msg = agent_mode.pause()
                print(yellow(msg) if success else red(msg))
                continue
            elif cmd == "/resume":
                success, msg = agent_mode.resume()
                print(green(msg) if success else red(msg))
                continue
            elif cmd == "/stop":
                success, msg = agent_mode.stop(rollback=True)
                print(red(msg))
                continue

        # Log goal to ACP
        if acp:
            acp.log_chat("user", f"Goal: {user_input}")

        success, result = agent_mode.run_task(user_input)
        icon = bright_green("✅") if success else bright_red("❌")
        print(f"\n{icon} {result}\n")

        # Log result to ACP
        if acp:
            acp.log_chat("assistant", f"Result: {result}")

    return 0


def _get_cache_dir() -> Path:
    """Get the cache directory for AgentNova."""
    # Use platform-appropriate cache directory
    if os.name == "nt":
        # Windows: %LOCALAPPDATA%\agentnova\cache
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        cache_dir = Path(base) / "agentnova" / "cache"
    else:
        # Unix: ~/.cache/agentnova
        base = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
        cache_dir = Path(base) / "agentnova"
    
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _load_tool_cache() -> dict:
    """Load cached tool support results."""
    cache_file = _get_cache_dir() / "tool_support.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
                # Validate it's a dict
                if isinstance(data, dict):
                    return data
                # Corrupted - not a dict
                if os.environ.get("AGENTNOVA_DEBUG"):
                    print(f"Warning: Cache file corrupted (not a dict), ignoring", file=sys.stderr)
                return {}
        except json.JSONDecodeError as e:
            # Corrupted JSON - warn in debug mode
            if os.environ.get("AGENTNOVA_DEBUG"):
                print(f"Warning: Cache file has invalid JSON: {e}", file=sys.stderr)
            # Try to remove corrupted file
            try:
                cache_file.unlink()
            except Exception:
                pass
            return {}
        except IOError as e:
            if os.environ.get("AGENTNOVA_DEBUG"):
                print(f"Warning: Could not read cache file: {e}", file=sys.stderr)
    return {}


def _save_tool_cache(cache: dict) -> None:
    """Save tool support results to cache using atomic writes."""
    import tempfile
    
    cache_dir = _get_cache_dir()
    cache_file = cache_dir / "tool_support.json"
    
    try:
        # Write to a temp file first, then rename for atomicity
        # This prevents partial writes if the process is interrupted
        fd, temp_path = tempfile.mkstemp(
            dir=str(cache_dir),
            prefix=".tool_support_",
            suffix=".json.tmp"
        )
        
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(cache, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            
            # Atomic rename (on POSIX systems)
            os.replace(temp_path, str(cache_file))
        except Exception:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
            
    except IOError as e:
        # Log the error but don't fail - cache is optional
        print(f"Warning: Could not save tool cache: {e}", file=sys.stderr)


def cmd_models(args: argparse.Namespace) -> int:
    """Execute the models command."""
    config = get_config()
    backend_name = args.backend or config.backend

    backend = get_backend(backend_name)

    if not isinstance(backend, OllamaBackend):
        print(f"Models command works best with Ollama backend (current: {backend_name})")

    if not backend.is_running():
        print(f"❌ {backend_name.capitalize()} is not running at {backend.base_url}")
        if backend_name == "ollama":
            print("   Start with: ollama serve")
            print(f"   Or set OLLAMA_BASE_URL to your remote server")
        return 1

    models = backend.list_models()

    if not models:
        print("No models found.")
        if backend_name == "ollama":
            print("Pull one with: ollama pull qwen2.5:0.5b")
        return 0

    # Load tool support cache
    cache = {} if args.no_cache else _load_tool_cache()
    cache_updated = False
    
    # Column widths
    NAME_W = 36
    SIZE_W = 8
    CTX_W = 12  # Wider for "2K/32K" format
    TOOLS_W = 10
    FAMILY_W = 12
    
    print()
    print(f"{bright_cyan('⚛ AgentNova')} - Available Models")
    print(dim(f"  Backend: {backend.base_url}"))
    print(dim("-" * (4 + NAME_W + SIZE_W + CTX_W + TOOLS_W + FAMILY_W + 8)))
    print(f"  {'Name':<{NAME_W}} {'Size':>{SIZE_W}}  {'Context':>{CTX_W}}  {'Tools':>{TOOLS_W}}  {'Family':<{FAMILY_W}}")
    print(dim("-" * (4 + NAME_W + SIZE_W + CTX_W + TOOLS_W + FAMILY_W + 8)))

    for m in models:
        name = m.get("name", "unknown")
        size = m.get("size", 0)
        size_gb = size / (1024**3) if size else 0
        family = m.get("details", {}).get("family", "unknown")
        
        # Get both runtime and max context
        runtime_ctx = backend.get_model_runtime_context(name)
        max_ctx = backend.get_model_max_context(name, family=family)
        
        # Format context size: "2K/32K" format
        def format_ctx(n):
            if n >= 1000000:
                return f"{n // 1000}K"
            elif n >= 1000:
                return f"{n // 1000}K"
            return str(n)
        
        if runtime_ctx == max_ctx:
            # Runtime matches max (explicitly set or same)
            ctx_str = format_ctx(runtime_ctx)
        elif runtime_ctx == 2048:
            # Using Ollama default - show "2K / 32K max"
            ctx_str = f"{format_ctx(runtime_ctx)}/{format_ctx(max_ctx)}"
        else:
            # Custom runtime setting
            ctx_str = f"{format_ctx(runtime_ctx)}/{format_ctx(max_ctx)}"
        
        # Get tool support level (from cache or test)
        if isinstance(backend, OllamaBackend):
            cached = cache.get(name)
            
            if args.tool_support:
                # Force test: actually call the model to test tool support
                print(f"  {dim('Testing:')} {cyan(name)}...", end="", flush=True)
                try:
                    support = backend.test_tool_support(name, family=family, force_test=True)
                    cache[name] = {
                        "support": support.value,
                        "tested_at": time.time(),
                        "family": family,
                    }
                    cache_updated = True
                    status = support.value
                except Exception as e:
                    # If test fails, still cache as unknown to avoid re-testing
                    cache[name] = {
                        "support": "error",
                        "tested_at": time.time(),
                        "family": family,
                        "error": str(e)[:100],
                    }
                    cache_updated = True
                    status = "error"
                
                # Overwrite the "Testing..." line
                name_col = pad_colored(cyan(name), NAME_W)
                size_col = f"{size_gb:>6.2f} GB"
                ctx_col = pad_colored(yellow(ctx_str) if runtime_ctx == 2048 else dim(ctx_str), CTX_W, 'right')
                print(f"\r  {name_col} {size_col}  {ctx_col}  ", end="")
                if status == "native":
                    tool_col = pad_colored(bright_green("✓ native"), TOOLS_W, 'right')
                elif status == "error":
                    tool_col = pad_colored(red("✗ error"), TOOLS_W, 'right')
                else:
                    tool_col = pad_colored(yellow("○ react"), TOOLS_W, 'right')
                print(f"{tool_col}  {dim('(' + family + ')')}")
                
                # Save cache incrementally after each test (in case of interruption)
                _save_tool_cache(cache)
            elif cached:
                # Use cached value
                status = cached.get("support", "untested")
                if status == "native":
                    tool_col = pad_colored(bright_green("✓ native"), TOOLS_W, 'right')
                elif status == "react":
                    tool_col = pad_colored(yellow("○ react"), TOOLS_W, 'right')
                elif status == "none":
                    tool_col = pad_colored(red("✗ none"), TOOLS_W, 'right')
                elif status == "error":
                    tool_col = pad_colored(red("✗ error"), TOOLS_W, 'right')
                else:
                    tool_col = pad_colored(dim("? untested"), TOOLS_W, 'right')
                name_col = pad_colored(cyan(name), NAME_W)
                size_col = f"{size_gb:>6.2f} GB"
                ctx_col = pad_colored(yellow(ctx_str) if runtime_ctx == 2048 else dim(ctx_str), CTX_W, 'right')
                print(f"  {name_col} {size_col}  {ctx_col}  {tool_col}  {dim('(' + family + ')')}")
            else:
                # No cache entry - show as untested
                name_col = pad_colored(cyan(name), NAME_W)
                size_col = f"{size_gb:>6.2f} GB"
                ctx_col = pad_colored(yellow(ctx_str) if runtime_ctx == 2048 else dim(ctx_str), CTX_W, 'right')
                tool_col = pad_colored(dim("? untested"), TOOLS_W, 'right')
                print(f"  {name_col} {size_col}  {ctx_col}  {tool_col}  {dim('(' + family + ')')}")
        else:
            name_col = pad_colored(cyan(name), NAME_W)
            size_col = f"{size_gb:>6.2f} GB"
            ctx_col = pad_colored(dim(ctx_str), CTX_W, 'right')
            tool_col = pad_colored(dim("? n/a"), TOOLS_W, 'right')
            print(f"  {name_col} {size_col}  {ctx_col}  {tool_col}  {dim('(' + family + ')')}")

    print(dim("-" * (4 + NAME_W + SIZE_W + CTX_W + TOOLS_W + FAMILY_W + 8)))
    print(f"Total: {bright_green(str(len(models)))} models")
    
    # Save cache if updated
    if cache_updated:
        _save_tool_cache(cache)
    
    # Show legend
    print(f"\n{dim('Legend:')} {bright_green('✓ native')} (API tools) | {yellow('○ react')} (text parsing) | {red('✗ none')} (no tools) | {dim('? untested')}")
    print(f"{dim('Context:')} {yellow('2K/32K')} = runtime/max (Ollama defaults to 2K unless num_ctx is set)")
    print(f"{dim('Tool support depends on model template, not family. Use')} {cyan('--tool-support')} {dim('to test each model.')}")

    return 0


def cmd_tools(args: argparse.Namespace) -> int:
    """Execute the tools command."""
    tools = make_builtin_registry()

    print()
    print(f"{bright_cyan('⚛ AgentNova')} - Available Tools")
    print(dim("-" * 60))

    for tool in tools.all():
        params = ", ".join(p.name for p in tool.params)
        print(f"  {cyan(tool.name):<29} {tool.description[:40]}")
        if params:
            print(f"    {dim('Parameters:')} {yellow(params)}")

    print(dim("-" * 60))
    print(f"Total: {bright_green(str(len(tools.all())))} tools")

    return 0


def cmd_test(args: argparse.Namespace) -> int:
    """Execute the test command."""
    # Available tests
    TESTS = {
        "00": {
            "name": "Basic Agent",
            "desc": "Simple conversation without tools",
            "module": "agentnova.examples.00_basic_agent",
        },
        "01": {
            "name": "Quick Diagnostic",
            "desc": "5-question math reasoning test",
            "module": "agentnova.examples.01_quick_diagnostic",
        },
        "02": {
            "name": "Tool Tests",
            "desc": "Calculator, shell, datetime tools",
            "module": "agentnova.examples.02_tool_test",
        },
        "03": {
            "name": "Reasoning Test",
            "desc": "Multi-step reasoning challenges",
            "module": "agentnova.examples.03_reasoning_test",
        },
        "04": {
            "name": "GSM8K Benchmark",
            "desc": "Grade school math problems",
            "module": "agentnova.examples.04_gsm8k_benchmark",
        },
        "05": {
            "name": "Common Sense",
            "desc": "Everyday knowledge and reasoning (25 questions)",
            "module": "agentnova.examples.05_common_sense",
        },
        "06": {
            "name": "Causal Reasoning",
            "desc": "Cause and effect understanding (25 questions)",
            "module": "agentnova.examples.06_causal_reasoning",
        },
        "07": {
            "name": "Logical Deduction",
            "desc": "Syllogisms and logic puzzles (25 questions)",
            "module": "agentnova.examples.07_logical_deduction",
        },
        "08": {
            "name": "Reading Comprehension",
            "desc": "Text understanding and inference (25 questions)",
            "module": "agentnova.examples.08_reading_comprehension",
        },
        "09": {
            "name": "General Knowledge",
            "desc": "Geography, science, and facts (25 questions)",
            "module": "agentnova.examples.09_general_knowledge",
        },
        "10": {
            "name": "Implicit Reasoning",
            "desc": "Understanding implied meanings (25 questions)",
            "module": "agentnova.examples.10_implicit_reasoning",
        },
        "11": {
            "name": "Analogical Reasoning",
            "desc": "Pattern and relationship mapping (25 questions)",
            "module": "agentnova.examples.11_analogical_reasoning",
        },
    }
    
    # List tests
    if args.list:
        print(f"\n{bright_cyan('⚛ AgentNova')} - Available Tests")
        print(dim("-" * 50))
        for tid, info in TESTS.items():
            print(f"  {cyan(tid)}  {info['name']:<20} {dim(info['desc'])}")
        print(dim("-" * 50))
        print(f"\n  Usage: {cyan('agentnova test 01')} or {cyan('agentnova test all')}")
        return 0
    
    # Determine which tests to run
    test_id = args.test_id.lower()
    if test_id == "all":
        tests_to_run = list(TESTS.keys())
    elif test_id in TESTS:
        tests_to_run = [test_id]
    else:
        print(f"{red('Error:')} Unknown test '{test_id}'")
        print(f"  Run {cyan('agentnova test --list')} to see available tests")
        return 1
    
    # Check backend
    config = get_config()
    backend_name = args.backend or config.backend
    timeout = getattr(args, 'timeout', None)
    backend = get_backend(backend_name, timeout=timeout)
    
    if not backend.is_running():
        print(f"{red('Error:')} {backend_name.capitalize()} not running at {backend.base_url}")
        if backend_name == "ollama":
            print(f"  Start with: {cyan('ollama serve')}")
            print(f"  Or set OLLAMA_BASE_URL to your remote server")
        return 1
    
    # Initialize ACP plugin if requested
    acp = None
    if args.acp:
        try:
            from .acp_plugin import ACPPlugin
            acp_url = args.acp_url or config.acp_base_url
            acp = ACPPlugin(
                base_url=acp_url,
                agent_name="AgentNova-Test",
                model_name=args.model or config.default_model,
                debug=args.debug,
            )
            # Bootstrap ACP connection
            bootstrap_result = acp.bootstrap()
            if bootstrap_result.get("stop_flag"):
                print(f"{red('Error:')} ACP STOP flag is set: {bootstrap_result.get('warnings')}")
                return 1
            acp_enabled = True
        except ImportError:
            print(f"{yellow('Warning:')} ACP plugin not available, continuing without ACP logging")
            acp = None
        except Exception as e:
            print(f"{yellow('Warning:')} Failed to connect to ACP: {e}")
            acp = None
    
    # Set environment for tests
    if args.debug:
        os.environ["AGENTNOVA_DEBUG"] = "1"
    if args.backend:
        os.environ["AGENTNOVA_BACKEND"] = args.backend
    if getattr(args, 'num_ctx', None):
        os.environ["AGENTNOVA_NUM_CTX"] = str(args.num_ctx)
    
    # Resolve model pattern to actual model(s)
    model_pattern = args.model
    if model_pattern:
        models_to_test = resolve_model_pattern(model_pattern, backend_name, allow_multiple=True)
        if not models_to_test:
            return 1  # Error already printed
    else:
        models_to_test = [config.default_model]
    
    # Run tests
    print_banner()
    print(f"{bright_magenta('Test Runner')} — {len(tests_to_run)} test(s), {len(models_to_test)} model(s)")
    print(f"{dim('Backend:')} {backend_name} ({backend.base_url})")
    if len(models_to_test) == 1:
        print(f"{dim('Model:')} {cyan(models_to_test[0])}")
    else:
        print(f"{dim('Models:')} {cyan(str(len(models_to_test)))} matching '{model_pattern}'")
    num_ctx_val = getattr(args, 'num_ctx', None) or config.num_ctx
    if num_ctx_val:
        ctx_display = f"{num_ctx_val // 1024}K" if num_ctx_val >= 1024 else str(num_ctx_val)
        print(f"{dim('Context:')} {yellow(ctx_display)}")
    if acp:
        print(f"{dim('ACP:')} {green('✓ Connected')} ({acp.base_url})")
    print()
    
    # Track results per model
    all_results = {}  # model -> {test_id -> result}
    
    for model in models_to_test:
        model_results = {}
        print(f"\n{dim('═' * 50)}")
        print(f"{bright_magenta('Model:')} {cyan(model)}")
        print(dim("═" * 50))
        
        # Set model env var for this run
        os.environ["AGENTNOVA_MODEL"] = model
        
        for tid in tests_to_run:
            info = TESTS[tid]
            print(f"\n{dim('─' * 50)}")
            print(f"{cyan(f'[{tid}]')} {bright_magenta(info['name'])}")
            print(f"{dim(info['desc'])}")
            print(dim("─" * 50))
            
            # Log test start to ACP
            if acp:
                acp.log_chat("user", f"[{model}] Starting test: {info['name']}")
            
            try:
                # Import and run the test module
                import importlib
                module = importlib.import_module(info["module"])
                
                # Build argv for test modules (they have their own argparse)
                test_argv = ["-m", model]
                if args.debug:
                    test_argv.append("--debug")
                if args.backend:
                    test_argv.extend(["--backend", args.backend])
                if getattr(args, 'use_modelfile_system', False):
                    test_argv.append("--use-mf-sys")
                
                # Override sys.argv for the test module's argparse
                old_argv = sys.argv
                sys.argv = ["test"] + test_argv
                
                try:
                    result = module.main()
                finally:
                    sys.argv = old_argv
                
                # Handle both old-style exit code and new-style result dict
                if isinstance(result, dict):
                    # New-style: granular results
                    passed = result.get("passed", 0)
                    total = result.get("total", 1)
                    time_s = result.get("time", 0)
                    exit_code = result.get("exit_code", 0)
                    model_results[tid] = {
                        "passed": exit_code == 0,
                        "exit_code": exit_code,
                        "granular": f"{passed}/{total}",
                        "time": time_s,
                    }
                else:
                    # Old-style: just exit code
                    exit_code = result if result is not None else 1
                    model_results[tid] = {"passed": exit_code == 0, "exit_code": exit_code}
                
                # Log test result to ACP
                if acp:
                    status = "passed" if exit_code == 0 else "failed"
                    granular = model_results[tid].get("granular", "")
                    acp.log_chat("assistant", f"[{model}] Test {info['name']}: {status} {granular}")
                
            except ImportError as e:
                print(f"{red('Error:')} Could not import test module: {e}")
                model_results[tid] = {"passed": False, "error": str(e)}
                if acp:
                    acp.log_chat("assistant", f"[{model}] Test {info['name']}: import error - {e}")
            except Exception as e:
                print(f"{red('Error:')} {e}")
                model_results[tid] = {"passed": False, "error": str(e)}
                if acp:
                    acp.log_chat("assistant", f"[{model}] Test {info['name']}: error - {e}")
        
        all_results[model] = model_results
    
    # Summary
    print(f"\n{dim('=' * 50)}")
    print(f"{bright_magenta('Test Summary')}")
    print(dim("=" * 50))
    
    # If multiple models, show per-model summary
    if len(models_to_test) > 1:
        print(f"\n{bright_magenta('Results by Model:')}")
        for model in models_to_test:
            model_results = all_results.get(model, {})
            passed = sum(1 for r in model_results.values() if r.get("passed"))
            total = len(model_results)
            granular_sum = ""
            # Sum up granular scores if available
            total_score = 0
            total_possible = 0
            total_time = 0
            for r in model_results.values():
                if "granular" in r:
                    try:
                        parts = r["granular"].split("/")
                        total_score += int(parts[0])
                        total_possible += int(parts[1])
                    except (ValueError, IndexError):
                        pass
                total_time += r.get("time", 0)
            
            if total_possible > 0:
                granular_sum = f"  {cyan(f'{total_score}/{total_possible}')}"
            time_str = f"  {dim(f'({total_time:.1f}s)')}" if total_time else ""
            status = bright_green("✓") if passed == total else red("✗")
            print(f"  {status} {cyan(model):<30} {passed}/{total}{granular_sum}{time_str}")
    else:
        # Single model - show per-test breakdown
        model = models_to_test[0]
        model_results = all_results.get(model, {})
        
        for tid, result in model_results.items():
            status = bright_green("✓ PASS") if result.get("passed") else red("✗ FAIL")
            granular = result.get("granular", "")
            time_s = result.get("time", 0)
            
            # Show granular results if available
            if granular:
                time_str = f" ({time_s:.1f}s)" if time_s else ""
                print(f"  [{tid}] {TESTS[tid]['name']:<20} {status}  {cyan(granular)}{time_str}")
            else:
                print(f"  [{tid}] {TESTS[tid]['name']:<20} {status}")
        
        print(dim("-" * 50))
        passed = sum(1 for r in model_results.values() if r.get("passed"))
        total = len(model_results)
        pct = 100 * passed // total if total > 0 else 0
        print(f"  {bright_green(str(passed))}/{total} tests passed ({pct}%)")
    
    # Log final summary to ACP and unregister (don't shutdown the server!)
    if acp:
        total_passed = sum(
            1 for model_results in all_results.values() 
            for r in model_results.values() if r.get("passed")
        )
        total_tests = sum(len(mr) for mr in all_results.values())
        acp.log_chat("assistant", f"All tests complete: {total_passed}/{total_tests} passed")
        # Only unregister from A2A, don't shutdown the ACP server
        acp.a2a_unregister()
        acp._log("Test complete, unregistered from A2A (ACP server remains running)")
    
    # Return success only if all tests passed
    total_passed = sum(
        1 for model_results in all_results.values() 
        for r in model_results.values() if r.get("passed")
    )
    total_tests = sum(len(mr) for mr in all_results.values())
    return 0 if total_passed == total_tests else 1


def cmd_version(args: argparse.Namespace) -> int:
    """Show version information."""
    from . import __version__, __status__, __author__

    print_banner()
    print(f"   {dim('Version:')} {bright_green(__version__)}")
    print(f"   {dim('Status:')}  {yellow(__status__)}")
    print(f"   {dim('Author:')}  {cyan(__author__)}")
    print(f"   {dim('Repo:')}    {dim('https://github.com/VTSTech/AgentNova')}")
    print()

    return 0


def cmd_config(args: argparse.Namespace) -> int:
    """Show current configuration."""
    from .config import (
        OLLAMA_BASE_URL, BITNET_BASE_URL, ACP_BASE_URL,
        AGENTNOVA_BACKEND, DEFAULT_MODEL, NUM_CTX,
    )

    if args.urls:
        print(f"OLLAMA_BASE_URL={OLLAMA_BASE_URL}")
        print(f"BITNET_BASE_URL={BITNET_BASE_URL}")
        print(f"ACP_BASE_URL={ACP_BASE_URL}")
    else:
        print()
        print(f"{bright_cyan('⚛ AgentNova')} - Configuration")
        print(dim("-" * 40))
        print(f"  {dim('Backend:')}       {green(AGENTNOVA_BACKEND)}")
        print(f"  {dim('Default Model:')} {cyan(DEFAULT_MODEL)}")
        if NUM_CTX and NUM_CTX > 0:
            ctx_display = f"{NUM_CTX // 1024}K" if NUM_CTX >= 1024 else str(NUM_CTX)
            print(f"  {dim('Context Window:')} {yellow(ctx_display)} (num_ctx)")
        print()
        print(f"  {yellow('URLs:')}")
        print(f"    {dim('Ollama:')} {OLLAMA_BASE_URL}")
        print(f"    {dim('BitNet:')} {BITNET_BASE_URL}")
        print(f"    {dim('ACP:')}    {ACP_BASE_URL}")
        print(dim("-" * 40))
        print(f"\n{yellow('Environment variables:')}")
        print(f"  {dim('OLLAMA_BASE_URL')}    - Ollama server URL")
        print(f"  {dim('BITNET_BASE_URL')}    - BitNet server URL")
        print(f"  {dim('BITNET_TUNNEL')}      - BitNet tunnel URL")
        print(f"  {dim('ACP_BASE_URL')}       - ACP server URL")
        print(f"  {dim('AGENTNOVA_BACKEND')}  - Default backend (ollama/bitnet)")
        print(f"  {dim('AGENTNOVA_MODEL')}    - Default model")
        print(f"  {dim('OLLAMA_NUM_CTX')}     - Context window size (default: 2048)")

    return 0


def cmd_modelfile(args: argparse.Namespace) -> int:
    """Show model's Modelfile system prompt and other info."""
    from .backends import OllamaBackend

    config = get_config()
    backend_name = args.backend or config.backend
    backend = get_backend(backend_name)

    if not isinstance(backend, OllamaBackend):
        print(f"{red('Error:')} Modelfile command requires Ollama backend")
        return 1

    if not backend.is_running():
        print(f"{red('✗')}  Ollama is not running. Start it with: {cyan('ollama serve')}")
        return 1

    model = args.model or config.default_model
    print(bold(f"\n⚛️ AgentNova Modelfile") + dim(" · Written by VTSTech · https://www.vts-tech.org"))
    print()

    try:
        info = backend.get_model_info(model)
    except Exception as e:
        print(f"{red('✗')}  Could not get info for model '{model}': {e}")
        return 1

    # Display model information
    print(bold(f"Model: {model}"))
    print(dim("─" * 70))
    print()

    # System prompt from Modelfile
    system_prompt = info.get("system")
    if system_prompt:
        print(cyan("SYSTEM PROMPT (from Modelfile):"))
        print()
        print(system_prompt)
        print()
    else:
        print(dim("(No SYSTEM prompt defined in Modelfile)"))
        print()

    # Template
    template = info.get("template")
    if template:
        print(cyan("TEMPLATE:"))
        print()
        print(template)
        print()

    # Parameters
    params = info.get("parameters", "")
    if params:
        print(cyan("PARAMETERS:"))
        print()
        for line in params.strip().split("\n"):
            if line.strip():
                print(dim(f"  {line.strip()}"))
        print()

    # Details
    details = info.get("details", {})
    if details:
        print(cyan("DETAILS:"))
        print()
        for key, value in details.items():
            print(dim(f"  {key}: {value}"))
        print()

    return 0


def cmd_skills(args: argparse.Namespace) -> int:
    """List available skills."""
    from .skills import SkillLoader

    loader = SkillLoader()
    skills = loader.list_skills()

    print(bold(f"\n⚛️ AgentNova Skills") + dim(" · Written by VTSTech · https://www.vts-tech.org"))

    if not skills:
        print(yellow("  No skills found."))
        print(dim("  Skills are loaded from agentnova/skills/*/SKILL.md"))
        return 0

    print(bold(f"{'Skill':<20} Description"))
    print(dim("─" * 70))

    for name in skills:
        try:
            skill = loader.load(name)
            desc = skill.description[:60] + "..." if len(skill.description) > 60 else skill.description
            print(f"  {magenta(name):<26} {desc}")

            # Show resources
            resources = []
            if skill.scripts_dir:
                scripts = list(skill.scripts_dir.glob("*.py"))
                if scripts:
                    resources.append(f"{len(scripts)} scripts")
            if skill.references_dir:
                refs = list(skill.references_dir.glob("*.md"))
                if refs:
                    resources.append(f"{len(refs)} refs")
            if resources:
                print(f"  {'':<26} {dim('Has: ' + ', '.join(resources))}")
        except Exception as e:
            print(f"  {magenta(name):<26} {red(f'Error: {e}')}")

    print()
    print(dim(f"  Use with: --skills {','.join(skills[:2])}"))
    print(dim("  Skills provide knowledge/instructions to the agent."))
    print()

    return 0


def cmd_soul(args: argparse.Namespace) -> int:
    """Inspect a Soul Spec package."""
    try:
        from .soul import load_soul, build_system_prompt, SoulLoader
    except ImportError:
        print(f"{red('Error:')} Soul module not available")
        return 1
    
    path = args.path
    level = args.level
    
    try:
        loader = SoulLoader()
        soul = loader.load(path, level=level)
    except FileNotFoundError as e:
        print(f"{red('Error:')} Soul package not found: {e}")
        return 1
    except Exception as e:
        print(f"{red('Error:')} Failed to load soul: {e}")
        return 1
    
    # Display soul info
    print()
    print(bold(f"👻 Soul Spec Package") + dim(" · ClawSouls v0.5"))
    print(dim("─" * 70))
    print()
    
    # Basic info
    print(f"  {cyan('Name:')}        {soul.display_name} ({dim(soul.name)})")
    print(f"  {cyan('Version:')}     {soul.version}")
    print(f"  {cyan('Spec:')}        v{soul.spec_version}")
    print(f"  {cyan('Author:')}      {soul.author.name}" + (f" ({soul.author.github})" if soul.author.github else ""))
    print(f"  {cyan('License:')}     {soul.license}")
    print()
    
    print(f"  {cyan('Description:')}")
    print(f"    {soul.description}")
    print()
    
    # Disclosure summary
    if soul.disclosure and soul.disclosure.summary:
        print(f"  {cyan('Summary:')}")
        print(f"    {soul.disclosure.summary}")
        print()
    
    # Tags and category
    if soul.tags:
        print(f"  {cyan('Tags:')}       {', '.join(soul.tags)}")
    print(f"  {cyan('Category:')}   {soul.category}")
    print()
    
    # Environment
    if soul.environment.value != "virtual":
        print(f"  {yellow('Environment:')} {soul.environment.value}")
        print(f"  {yellow('Interaction:')} {soul.interaction_mode.value}")
        if soul.hardware_constraints:
            hc = soul.hardware_constraints
            caps = []
            if hc.has_display: caps.append("display")
            if hc.has_speaker: caps.append("speaker")
            if hc.has_microphone: caps.append("microphone")
            if hc.has_camera: caps.append("camera")
            if caps:
                print(f"  {yellow('Hardware:')}   {', '.join(caps)}")
        if soul.safety and soul.safety.physical:
            print(f"  {yellow('Safety:')}     {soul.safety.physical.contact_policy.value}")
        print()
    
    # Allowed tools
    if soul.allowed_tools:
        print(f"  {cyan('Allowed Tools:')} {', '.join(soul.allowed_tools)}")
    
    # Recommended skills
    if soul.recommended_skills:
        required = [s.name for s in soul.recommended_skills if s.required]
        optional = [s.name for s in soul.recommended_skills if not s.required]
        if required:
            print(f"  {cyan('Required Skills:')} {', '.join(required)}")
        if optional:
            print(f"  {cyan('Optional Skills:')} {', '.join(optional)}")
    
    # Compatibility
    if soul.compatibility.frameworks:
        print(f"  {cyan('Frameworks:')}   {', '.join(soul.compatibility.frameworks)}")
    if soul.compatibility.models:
        print(f"  {cyan('Models:')}       {', '.join(soul.compatibility.models)}")
    
    print()
    
    # Validation
    if args.validate:
        issues = soul.validate()
        if issues:
            print(f"  {red('Validation Issues:')}")
            for issue in issues:
                print(f"    {red('✗')} {issue}")
        else:
            print(f"  {green('✓')} Validation passed")
        print()
    
    # Loaded content
    if level >= 2:
        print(dim("─" * 70))
        if soul.soul_content:
            print(f"\n  {cyan('SOUL.md:')}")
            lines = soul.soul_content.split("\n")
            for line in lines[:10]:
                print(f"    {line}")
            if len(lines) > 10:
                remaining = len(lines) - 10
                print(f"    {dim('...')} ({remaining} more lines)")
        
        if soul.identity_content:
            print(f"\n  {cyan('IDENTITY.md:')}")
            lines = soul.identity_content.split("\n")
            for line in lines[:10]:
                print(f"    {line}")
            if len(lines) > 10:
                remaining = len(lines) - 10
                print(f"    {dim('...')} ({remaining} more lines)")
    
    # Show generated system prompt
    if args.prompt:
        prompt = loader.build_system_prompt(soul, level=level)
        print()
        print(dim("─" * 70))
        print(f"\n  {cyan('Generated System Prompt:')}")
        print(dim("─" * 70))
        print(prompt)
    
    print()
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        print_banner()
        parser.print_help()
        return 0

    commands = {
        "run": cmd_run,
        "chat": cmd_chat,
        "agent": cmd_agent,
        "models": cmd_models,
        "tools": cmd_tools,
        "test": cmd_test,
        "version": cmd_version,
        "config": cmd_config,
        "modelfile": cmd_modelfile,
        "skills": cmd_skills,
        "soul": cmd_soul,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())