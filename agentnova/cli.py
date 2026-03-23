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

    # Version command
    subparsers.add_parser("version", help="Show version information")

    # Config command
    config_parser = subparsers.add_parser("config", help="Show current configuration")
    config_parser.add_argument("--urls", action="store_true", help="Show only URLs")

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

    print(f"\n⚛️ AgentNova Chat — {model}")
    print(f"Backend: {backend_name} ({backend.base_url})")
    print("Status: Alpha")
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
            print("👋 Goodbye!")
            break

        if user_input == "/help":
            print("Commands: /quit, /help, /clear, /status")
            continue

        if user_input == "/clear":
            agent.clear_memory()
            print("Memory cleared.")
            continue

        if user_input == "/status":
            print(f"Model: {agent.model}")
            print(f"Tool support: {agent._tool_support}")
            print(f"Memory turns: {len(agent.memory)}")
            continue

        result = agent.run(user_input)
        print(f"\nAssistant: {result.final_answer}\n")

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

    print(f"\n⚛️ AgentNova Agent Mode — {model}")
    print(f"Backend: {backend_name} ({backend.base_url})")
    print("Status: Alpha")
    print("Give the agent a goal to accomplish autonomously.")
    print("Commands: /status, /pause, /resume, /stop, /quit\n")

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
                print("👋 Goodbye!")
                break
            elif cmd == "/status":
                status = agent_mode.get_status()
                print(f"State: {status['state']}")
                if "goal" in status and status["goal"]:
                    print(f"Goal: {status['goal']}")
                    if "progress_percent" in status:
                        print(f"Progress: {status['progress_percent']:.0f}%")
                continue
            elif cmd == "/pause":
                success, msg = agent_mode.pause()
                print(msg)
                continue
            elif cmd == "/resume":
                success, msg = agent_mode.resume()
                print(msg)
                continue
            elif cmd == "/stop":
                success, msg = agent_mode.stop(rollback=True)
                print(msg)
                continue

        success, result = agent_mode.run_task(user_input)
        print(f"\n{'✅' if success else '❌'} {result}\n")

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
    print(f"\n⚛️ AgentNova - Available Models ({backend.base_url})")
    print("-" * 92)
    print(f"  {'Name':<36} {'Size':>8}  {'Context':>8}  {'Tools':>10}  {'Family':<12}")
    print("-" * 92)

    for m in models:
        name = m.get("name", "unknown")
        size = m.get("size", 0)
        size_gb = size / (1024**3) if size else 0
        family = m.get("details", {}).get("family", "unknown")
        
        # Get context size
        ctx_size = backend.get_model_context_size(name)
        
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
            
            if args.tool_support or cached is None:
                # Test and cache
                support = backend.test_tool_support(name)
                cache[name] = {
                    "support": support.value,
                    "tested_at": time.time(),
                    "family": family,
                }
                cache_updated = True
                status = support.value
            else:
                status = cached.get("support", "untested")
            
            # Format tool status with icon
            if status == "native":
                tool_icon = "✓ native"
            elif status == "react":
                tool_icon = "○ react"
            elif status == "none":
                tool_icon = "○ none"
            else:
                tool_icon = "? untested"
            
            print(f"  {name:<36} {size_gb:>6.2f} GB  {ctx_str:>8}  {tool_icon:>10}  ({family})")
        else:
            print(f"  {name:<36} {size_gb:>6.2f} GB  {ctx_str:>8}  {'? n/a':>10}  ({family})")

    print("-" * 92)
    print(f"Total: {len(models)} models")
    
    # Save cache if updated
    if cache_updated:
        _save_tool_cache(cache)
    
    # Show legend
    print("\nLegend: ✓ native (API tools) | ○ react (text parsing) | ? untested")

    return 0


def cmd_tools(args: argparse.Namespace) -> int:
    """Execute the tools command."""
    tools = make_builtin_registry()

    print("\n⚛️ AgentNova - Available Tools")
    print("-" * 60)

    for tool in tools.all():
        params = ", ".join(p.name for p in tool.params)
        print(f"  {tool.name:<20} {tool.description[:40]}")
        if params:
            print(f"    Parameters: {params}")

    print("-" * 60)
    print(f"Total: {len(tools.all())} tools")

    return 0


def cmd_version(args: argparse.Namespace) -> int:
    """Show version information."""
    from . import __version__, __status__, __author__

    print(f"\n⚛️ AgentNova")
    print(f"   Version: {__version__}")
    print(f"   Status: {__status__}")
    print(f"   Author: {__author__}")
    print(f"   Repository: https://github.com/VTSTech/AgentNova")
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
        print("\n⚛️ AgentNova - Configuration")
        print("-" * 40)
        print(f"  Backend: {AGENTNOVA_BACKEND}")
        print(f"  Default Model: {DEFAULT_MODEL}")
        print()
        print("  URLs:")
        print(f"    Ollama: {OLLAMA_BASE_URL}")
        print(f"    BitNet: {BITNET_BASE_URL}")
        print(f"    ACP:    {ACP_BASE_URL}")
        print("-" * 40)
        print("\nEnvironment variables:")
        print("  OLLAMA_BASE_URL    - Ollama server URL")
        print("  BITNET_BASE_URL    - BitNet server URL")
        print("  BITNET_TUNNEL      - BitNet tunnel URL")
        print("  ACP_BASE_URL       - ACP server URL")
        print("  AGENTNOVA_BACKEND  - Default backend (ollama/bitnet)")
        print("  AGENTNOVA_MODEL    - Default model")

    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "run": cmd_run,
        "chat": cmd_chat,
        "agent": cmd_agent,
        "models": cmd_models,
        "tools": cmd_tools,
        "version": cmd_version,
        "config": cmd_config,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
