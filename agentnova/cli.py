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

    # Chat command
    chat_parser = subparsers.add_parser("chat", help="Interactive chat mode")
    chat_parser.add_argument("-m", "--model", default=None, help="Model to use")
    chat_parser.add_argument("--tools", default="", help="Comma-separated tool list")
    chat_parser.add_argument("--backend", choices=["ollama", "bitnet"], default=None, help="Backend to use")
    chat_parser.add_argument("--debug", action="store_true", help="Enable debug output")
    chat_parser.add_argument("--force-react", action="store_true", help="Force ReAct mode")

    # Agent command
    agent_parser = subparsers.add_parser("agent", help="Autonomous agent mode")
    agent_parser.add_argument("-m", "--model", default=None, help="Model to use")
    agent_parser.add_argument("--tools", default="calculator,shell,write_file", help="Comma-separated tool list")
    agent_parser.add_argument("--backend", choices=["ollama", "bitnet"], default=None, help="Backend to use")
    agent_parser.add_argument("--debug", action="store_true", help="Enable debug output")

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
                             help="Test to run: 00, 01, 02, 03, 04, or 'all' (default: all)")
    test_parser.add_argument("-m", "--model", default=None, help="Model to test")
    test_parser.add_argument("--backend", choices=["ollama", "bitnet"], default=None, help="Backend to use")
    test_parser.add_argument("--debug", action="store_true", help="Enable debug output")
    test_parser.add_argument("--list", action="store_true", help="List available tests")
    test_parser.add_argument("--acp", action="store_true", help="Enable ACP logging to Agent Control Panel")
    test_parser.add_argument("--acp-url", default=None, help="ACP server URL (default: http://localhost:8766)")

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

    return parser


def cmd_run(args: argparse.Namespace) -> int:
    """Execute the run command."""
    config = get_config()
    model = args.model or config.default_model
    backend_name = args.backend or config.backend

    backend = get_backend(backend_name)

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
    )

    result = agent.run(args.prompt)
    print(result.final_answer)

    if args.verbose:
        print(f"\n⏱️ Completed in {result.total_ms:.0f}ms")
        print(f"📊 Tokens: {result.total_tokens}, Steps: {result.iterations}")

    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    """Execute the chat command."""
    config = get_config()
    model = args.model or config.default_model
    backend_name = args.backend or config.backend

    backend = get_backend(backend_name)

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
    )

    print_banner()
    print(f"{bright_magenta('Chat Mode')} — {cyan(model)}")
    print(f"{dim('Backend:')} {backend_name} ({dim(backend.base_url)})")
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

        result = agent.run(user_input)
        print(f"\n{bright_magenta('Assistant')}: {result.final_answer}\n")

    return 0


def cmd_agent(args: argparse.Namespace) -> int:
    """Execute the agent command."""
    config = get_config()
    model = args.model or config.default_model
    backend_name = args.backend or config.backend

    backend = get_backend(backend_name)

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
    )

    agent_mode = AgentMode(agent, verbose=True)

    print_banner()
    print(f"{bright_magenta('Agent Mode')} — {cyan(model)}")
    print(f"{dim('Backend:')} {backend_name} ({dim(backend.base_url)})")
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

        success, result = agent_mode.run_task(user_input)
        icon = bright_green("✅") if success else bright_red("❌")
        print(f"\n{icon} {result}\n")

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
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_tool_cache(cache: dict) -> None:
    """Save tool support results to cache."""
    cache_file = _get_cache_dir() / "tool_support.json"
    try:
        with open(cache_file, "w") as f:
            json.dump(cache, f, indent=2)
    except IOError:
        pass


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
    
    # Always show tools column
    # Column widths
    NAME_W = 36
    SIZE_W = 8
    CTX_W = 8
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
        
        # Get context size (fast path using family)
        ctx_size = backend.get_model_context_size(name, family=family)
        
        # Format context size nicely
        if ctx_size >= 1000000:
            ctx_str = f"{ctx_size // 1000}K"
        elif ctx_size >= 1000:
            ctx_str = f"{ctx_size // 1000}K"
        else:
            ctx_str = str(ctx_size)
        
        # Get tool support level (from cache or test)
        if isinstance(backend, OllamaBackend):
            cached = cache.get(name)
            
            # Check if cache entry matches current family (detects model updates)
            cache_valid = cached and cached.get("family") == family
            
            if args.tool_support:
                # Force test: actually call the model to test tool support
                print(f"  {dim('Testing:')} {cyan(name)}...", end="", flush=True)
                support = backend.test_tool_support(name, family=family, force_test=True)
                cache[name] = {
                    "support": support.value,
                    "tested_at": time.time(),
                    "family": family,
                }
                cache_updated = True
                status = support.value
                # Overwrite the "Testing..." line
                name_col = pad_colored(cyan(name), NAME_W)
                size_col = f"{size_gb:>6.2f} GB"
                ctx_col = pad_colored(dim(ctx_str), CTX_W, 'right')
                print(f"\r  {name_col} {size_col}  {ctx_col}  ", end="")
                if status == "native":
                    tool_col = pad_colored(bright_green("✓ native"), TOOLS_W, 'right')
                else:
                    tool_col = pad_colored(yellow("○ react"), TOOLS_W, 'right')
                print(f"{tool_col}  {dim('(' + family + ')')}")
            elif not cache_valid:
                # No valid cache - show as untested
                name_col = pad_colored(cyan(name), NAME_W)
                size_col = f"{size_gb:>6.2f} GB"
                ctx_col = pad_colored(dim(ctx_str), CTX_W, 'right')
                tool_col = pad_colored(dim("? untested"), TOOLS_W, 'right')
                print(f"  {name_col} {size_col}  {ctx_col}  {tool_col}  {dim('(' + family + ')')}")
            else:
                # Use cached value
                status = cached.get("support", "untested")
                if status == "native":
                    tool_col = pad_colored(bright_green("✓ native"), TOOLS_W, 'right')
                elif status == "react":
                    tool_col = pad_colored(yellow("○ react"), TOOLS_W, 'right')
                else:
                    tool_col = pad_colored(dim("? untested"), TOOLS_W, 'right')
                name_col = pad_colored(cyan(name), NAME_W)
                size_col = f"{size_gb:>6.2f} GB"
                ctx_col = pad_colored(dim(ctx_str), CTX_W, 'right')
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
    print(f"\n{dim('Legend:')} {bright_green('✓ native')} (API tools) | {yellow('○ react')} (text parsing) | {dim('? untested')}")
    print(f"{dim('Use')} {cyan('--tool-support')} {dim('to test models (cached in ~/.cache/agentnova/tool_support.json)')}")

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
    backend = get_backend(backend_name)
    
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
    if args.model:
        os.environ["AGENTNOVA_MODEL"] = args.model
    if args.backend:
        os.environ["AGENTNOVA_BACKEND"] = args.backend
    
    # Build argv for test modules (they have their own argparse)
    test_argv = []
    if args.model:
        test_argv.extend(["-m", args.model])
    if args.debug:
        test_argv.append("--debug")
    if args.backend:
        test_argv.extend(["--backend", args.backend])
    
    # Run tests
    print_banner()
    print(f"{bright_magenta('Test Runner')} — {len(tests_to_run)} test(s)")
    print(f"{dim('Backend:')} {backend_name} ({backend.base_url})")
    print(f"{dim('Model:')} {args.model or config.default_model}")
    if acp:
        print(f"{dim('ACP:')} {green('✓ Connected')} ({acp.base_url})")
    print()
    
    results = {}
    for tid in tests_to_run:
        info = TESTS[tid]
        print(f"\n{dim('─' * 50)}")
        print(f"{cyan(f'[{tid}]')} {bright_magenta(info['name'])}")
        print(f"{dim(info['desc'])}")
        print(dim("─" * 50))
        
        # Log test start to ACP
        if acp:
            acp.log_chat("user", f"Starting test: {info['name']}")
        
        try:
            # Import and run the test module
            import importlib
            module = importlib.import_module(info["module"])
            
            # Override sys.argv for the test module's argparse
            old_argv = sys.argv
            sys.argv = ["test"] + test_argv
            
            try:
                exit_code = module.main()
            finally:
                sys.argv = old_argv
            
            results[tid] = {"passed": exit_code == 0, "exit_code": exit_code}
            
            # Log test result to ACP
            if acp:
                status = "passed" if exit_code == 0 else "failed"
                acp.log_chat("assistant", f"Test {info['name']}: {status}")
            
        except ImportError as e:
            print(f"{red('Error:')} Could not import test module: {e}")
            results[tid] = {"passed": False, "error": str(e)}
            if acp:
                acp.log_chat("assistant", f"Test {info['name']}: import error - {e}")
        except Exception as e:
            print(f"{red('Error:')} {e}")
            results[tid] = {"passed": False, "error": str(e)}
            if acp:
                acp.log_chat("assistant", f"Test {info['name']}: error - {e}")
    
    # Summary
    print(f"\n{dim('=' * 50)}")
    print(f"{bright_magenta('Test Summary')}")
    print(dim("=" * 50))
    
    passed = sum(1 for r in results.values() if r.get("passed"))
    total = len(results)
    
    for tid, result in results.items():
        status = bright_green("✓ PASS") if result.get("passed") else red("✗ FAIL")
        print(f"  [{tid}] {TESTS[tid]['name']:<20} {status}")
    
    print(dim("-" * 50))
    pct = 100 * passed // total if total > 0 else 0
    print(f"  {bright_green(str(passed))}/{total} tests passed ({pct}%)")
    
    # Log final summary to ACP and unregister (don't shutdown the server!)
    if acp:
        acp.log_chat("assistant", f"All tests complete: {passed}/{total} passed ({pct}%)")
        # Only unregister from A2A, don't shutdown the ACP server
        acp.a2a_unregister()
        acp._log("Test complete, unregistered from A2A (ACP server remains running)")
    
    return 0 if passed == total else 1


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
        AGENTNOVA_BACKEND, DEFAULT_MODEL,
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

    # License
    license_info = info.get("license", "")
    if license_info:
        print(cyan("LICENSE:"))
        print(f"  {license_info}")
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
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
