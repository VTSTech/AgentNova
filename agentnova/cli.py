#!/usr/bin/env python3
"""
⚛️ AgentNova R02.6 — CLI
Entry point: agentnova <command> [options]

Commands:
  run     Run the agent on a single prompt and exit
  chat    Interactive multi-turn conversation with memory
  agent   Agent mode: autonomous task execution with planning
  models  List models available in Ollama
  tools   List available built-in tools
  skills  List available Agent Skills
  test    Run example/test scripts

Examples:
  agentnova run "What is the capital of France?"
  agentnova run "What is sqrt(144)?" --tools calculator
  agentnova chat --model llama3.1:8b --tools calculator,shell
  agentnova chat --skills skill-creator --tools write_file,shell
  agentnova agent --model llama3.2:1b --tools shell,calculator
  agentnova models
  agentnova tools
  agentnova skills
  agentnova test --list
  agentnova test quick
  agentnova test 01

Written by VTSTech · https://www.vts-tech.org · https://github.com/VTSTech/AgentNova — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import textwrap
import time
from pathlib import Path

from . import Agent, OllamaClient, StepResult
from .config import OLLAMA_BASE_URL, ACP_BASE_URL, BITNET_BASE_URL
from .core.memory import Message
from .tools.builtins import BUILTIN_REGISTRY
from .skills import SkillLoader, SkillRegistry
from .acp_plugin import ACPPlugin
from .agent_mode import AgentMode, AgentState, TaskPlan, Step, Action
try:
    from .bitnet_client import BitnetClient, KNOWN_MODELS
    _BITNET_AVAILABLE = True
except ImportError:
    _BITNET_AVAILABLE = False

# Path to tested models storage
_TESTED_MODELS_FILE = Path(__file__).parent / "tested_models.json"


def _load_tested_models() -> dict:
    """Load tested models from JSON file."""
    try:
        if _TESTED_MODELS_FILE.exists():
            with open(_TESTED_MODELS_FILE, "r") as f:
                data = json.load(f)
                return data.get("models", {})
    except Exception:
        pass
    return {}


def _save_tested_models(models: dict):
    """Save tested models to JSON file."""
    try:
        data = {
            "_comment": "Tool support test results for AgentNova models",
            "_version": "1.0",
            "_updated": datetime.datetime.now().isoformat(),
            "models": models
        }
        with open(_TESTED_MODELS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(yellow(f"  ⚠ Could not save tested models: {e}"))


def get_tool_support(model: str, client=None) -> str:
    """
    Get the tool support level for a model.
    
    Checks tested_models.json only. Run `agentnova models --tool_support` to test.
    
    Parameters
    ----------
    model : str
        Model name to check.
    client : OllamaClient, optional
        Unused (kept for API compatibility).
    
    Returns
    -------
    str
        One of: "native", "react", "none", or "untested"
    
    Levels
    ------
    - "native": Model has native Ollama tool-calling support (passes tools to API)
    - "react": Model accepts tools API but needs text-based ReAct prompting  
    - "none": Model explicitly rejects tools (don't pass tools at all)
    - "untested": Not tested yet - run `agentnova models --tool_support` to test
    
    Examples
    --------
    >>> support = get_tool_support("llama3.1:8b")
    >>> if support == "native":
    ...     # Use native tool calling
    ... elif support == "react":
    ...     # Use ReAct text parsing
    ... elif support == "none":
    ...     # Don't use tools at all
    ... elif support == "untested":
    ...     # Not tested - defaults to ReAct mode
    """
    # Check tested_models.json only
    tested = _load_tested_models()
    if model in tested:
        result = tested[model].get("tool_support")
        if result in ("native", "react", "none"):
            return result
    
    # Not tested
    return "untested"


def _test_model_tool_support(client: OllamaClient, model: str, verbose: bool = False) -> str:
    """
    Test if a model supports native tool calling.
    Uses the model's Modelfile system prompt (no custom prompts).

    Detection logic (v2 - improved accuracy):
    1. HTTP 400 "does not support tools" → none (Ollama's explicit rejection)
    2. Native tool_calls in API response, calling correct function → native
    3. No tool_calls but content has JSON tool call pattern → react (text-based)
    4. No tool_calls, no tool-like JSON, but API accepted tools → react
    5. Model ignored tools entirely, gave normal answer → react (still can try)

    Key insight: "native" requires ACTUAL native tool_calls structure in API response.
    Models that output JSON as text are "react", not "native".

    Returns: "native", "react", "none", or "error"
    """

    # Test tool 1: Weather (simple, commonly supported)
    weather_tool = {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and country, e.g., 'Paris, France'"
                    }
                },
                "required": ["location"]
            }
        }
    }

    test_message = {
        "role": "user",
        "content": "What's the weather like in Tokyo?"
    }

    if verbose:
        print(dim(f"    Testing {model}..."), end=" ", flush=True)

    try:
        # Send request with tools but NO system prompt override
        response = client.chat(
            model=model,
            messages=[test_message],
            tools=[weather_tool],
            options={"num_predict": 100}  # Limit response size
        )

        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])
        content = message.get("content", "")

        # 2. Check for NATIVE tool_calls in API response structure
        # This is the ONLY path to "native" classification
        if tool_calls:
            for tc in tool_calls:
                func = tc.get("function", {})
                func_name = func.get("name", "")
                # Verify it's calling our tool (not hallucinating a different one)
                if func_name == "get_weather":
                    # Check for reasonable arguments
                    args = func.get("arguments", {})
                    if isinstance(args, dict) and ("location" in args or "city" in args or len(args) > 0):
                        if verbose:
                            print(green("✓ native"))
                        return "native"
                # Native tool_calls exist but wrong function - still native capability
                # (model might be confused but HAS native support)
                elif func_name:  # Any function name = native structure
                    if verbose:
                        print(green("✓ native"))
                    return "native"

        # 3. Check for text-based tool calls in content
        # Models that output JSON like {"name": "get_weather", ...} as TEXT
        if _contains_text_tool_call(content):
            if verbose:
                print(yellow("→ ReAct (text JSON)"))
            return "react"

        # 4. API succeeded, no explicit rejection, no native tool_calls
        # Model accepted tools parameter but didn't use native calling
        # This is the "react" case - can still parse text-based tool calls
        if verbose:
            print(yellow("→ ReAct"))
        return "react"

    except Exception as e:
        error_str = str(e)

        # 1. Check for explicit "does not support tools" rejection
        if "does not support tools" in error_str.lower():
            if verbose:
                print(dim("○ none"))
            return "none"

        # Other HTTP errors or connection issues
        if verbose:
            print(red(f"✗ error: {error_str[:60]}"))
        return "error"


def _contains_text_tool_call(content: str) -> bool:
    """
    Check if the response content contains a JSON tool call pattern.
    Models that output tool calls as TEXT (not native API) show this pattern.

    Examples:
      {"name": "get_weather", "arguments": {"location": "Tokyo"}}
      {"tool": "calculator", "arguments": {"expression": "2+2"}}
      ```json
      {"name": "some_function", "parameters": {...}}
      ```
    """
    if not content:
        return False

    # Remove markdown code blocks if present
    cleaned = re.sub(r"```(?:json)?", "", content).strip().rstrip("`").strip()

    # Look for JSON object pattern
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        return False

    try:
        import json
        obj = json.loads(cleaned[start:end + 1])

        # Check for tool call patterns
        if not isinstance(obj, dict):
            return False

        # Pattern 1: {"name": "...", "arguments": {...}}
        if "name" in obj and ("arguments" in obj or "parameters" in obj):
            return True

        # Pattern 2: {"tool": "...", "arguments": {...}}
        if "tool" in obj and "arguments" in obj:
            return True

        # Pattern 3: {"function": "...", "args": {...}}
        if "function" in obj and "args" in obj:
            return True

        return False
    except (json.JSONDecodeError, ValueError):
        return False

# Global reference for A2A processing (set in cmd_chat)
_acp_plugin = None
_tools_registry = None


def _execute_a2a_tool(action: str, payload: dict) -> any:
    """Execute an A2A action using the available tools registry."""
    global _tools_registry
    
    if not _tools_registry:
        return {"error": "No tools available"}
    
    # Map A2A actions to tool names
    action_to_tool = {
        "read_file": "read_file",
        "write_file": "write_file",
        "list_directory": "list_directory",
        "shell": "shell",
        "execute_python": "python_repl",
        "execute_code": "python_repl",
        "python_repl": "python_repl",
    }
    
    tool_name = action_to_tool.get(action, action)
    tool = _tools_registry.get(tool_name)
    
    if not tool:
        return {"error": f"Tool not found: {tool_name} (action: {action})"}
    
    try:
        # Execute the tool with the payload as kwargs
        result = tool.fn(**payload)
        return result
    except Exception as e:
        return {"error": str(e)}


def _on_a2a_message_callback(hints: dict):
    """Callback to process A2A messages automatically when notified."""
    global _acp_plugin
    
    pending_count = hints.get("pending_count", 0)
    senders = hints.get("senders", [])
    
    if pending_count > 0 and _acp_plugin:
        print()
        print(cyan(f"  📨 Processing {pending_count} A2A message(s) from {senders}..."))
        
        # Process the inbox
        results = _acp_plugin.a2a_process_inbox(
            tool_executor=_execute_a2a_tool,
            auto_respond=True
        )
        
        for r in results:
            status = green("✓") if r.get("status") == "processed" else yellow("○")
            action = r.get("action", "unknown")
            from_agent = r.get("from_agent", "unknown")
            result_preview = ""
            if r.get("result"):
                result_str = str(r.get("result"))[:60]
                result_preview = f" → {result_str}"
            elif r.get("error"):
                result_preview = f" ✗ {r.get('error')}"
            print(dim(f"    {status} {action} from {from_agent}{result_preview}"))
        print()


# ------------------------------------------------------------------ #
#  Helper functions                                                    #
# ------------------------------------------------------------------ #

def _count_messages(history) -> dict:
    """Count messages by role in history."""
    return {
        'user': sum(1 for m in history if m.role == 'user'),
        'assistant': sum(1 for m in history if m.role == 'assistant'),
        'tool': sum(1 for m in history if m.role == 'tool'),
        'total': len(history),
    }


def _handle_ollama_command(user_input: str, client, args):
    """
    Handle /ollama commands - an alias for ollama CLI that works via HTTP API.
    Supports both local and remote Ollama instances.

    Commands:
        /ollama                    Show connection status
        /ollama list               List local models
        /ollama pull <model>       Pull/download a model
        /ollama rm <model>         Delete a model
        /ollama show <model>       Show model details
        /ollama ps                 List running models
        /ollama stop <model>       Unload/stop a model
        /ollama cp <src> <dst>     Copy a model
        /ollama set-url <url>      Switch to a different Ollama server
    """
    # Parse the command
    parts = user_input.split(maxsplit=2)
    subcommand = parts[1] if len(parts) > 1 else None
    arg1 = parts[2] if len(parts) > 2 else None

    # No subcommand - show status
    if not subcommand:
        print()
        print(cyan("  Ollama Connection"))
        print(dim("  ─────────────────────────────────────"))
        print(f"  URL:     {client.base_url}")
        print(f"  Status:  {green('✓ Connected') if client.is_running() else red('✗ Not connected')}")
        
        # Show available models count
        try:
            models = client.list_models()
            print(f"  Models:  {len(models)} available")
            if models:
                print(dim(f"           {', '.join(models[:5])}{'...' if len(models) > 5 else ''}"))
        except Exception:
            print(yellow("  Models:  Unable to list (check connection)"))
        print()
        return

    # Handle subcommands
    if subcommand == "list":
        print()
        print(cyan("  Local Models"))
        print(dim("  ─────────────────────────────────────"))
        try:
            models = client.list_models()
            if not models:
                print(dim("  No models found."))
                print(dim("  Use '/ollama pull <model>' to download one."))
            else:
                for m in sorted(models):
                    # Try to get model info for size
                    try:
                        info = client.get_model_info(m)
                        details = info.get("details", {})
                        param_size = details.get("parameter_size", "")
                        family = details.get("family", "")
                        size_str = f" ({param_size})" if param_size else ""
                        fam_str = f" [{family}]" if family else ""
                        print(f"  {cyan(m)}{dim(size_str)}{dim(fam_str)}")
                    except Exception:
                        print(f"  {cyan(m)}")
        except Exception as e:
            print(red(f"  ✗ Error listing models: {e}"))
        print()
        return

    if subcommand == "pull" and arg1:
        print()
        print(cyan(f"  Pulling model: {arg1}"))
        print(dim("  ─────────────────────────────────────"))
        try:
            for progress in client.pull_model(arg1, stream=True):
                status = progress.get("status", "")
                completed = progress.get("completed", 0)
                total = progress.get("total", 0)
                digest = progress.get("digest", "")

                if "pulling" in status.lower() and total > 0:
                    percent = (completed / total) * 100
                    bar_len = 30
                    filled = int(bar_len * completed / total)
                    bar = "█" * filled + "░" * (bar_len - filled)
                    size_mb = total / (1024 * 1024)
                    print(f"\r  {dim(status)} [{bar}] {percent:.1f}% ({size_mb:.0f} MB)", end="", flush=True)
                elif digest:
                    print(f"\r  {dim('digest:')} {digest[:16]}...", end="", flush=True)
                elif status:
                    print(f"\r  {dim(status)}" + " " * 40, end="", flush=True)

                if progress.get("error"):
                    print()
                    print(red(f"  ✗ Error: {progress['error']}"))
                    print()
                    return

            print()
            print(green(f"  ✓ Successfully pulled {arg1}"))
        except Exception as e:
            print()
            print(red(f"  ✗ Error pulling model: {e}"))
        print()
        return

    if subcommand == "rm" and arg1:
        print()
        try:
            client.delete_model(arg1)
            print(green(f"  ✓ Deleted model: {arg1}"))
        except Exception as e:
            print(red(f"  ✗ Error deleting model: {e}"))
        print()
        return

    if subcommand == "show" and arg1:
        print()
        print(cyan(f"  Model: {arg1}"))
        print(dim("  ─────────────────────────────────────"))
        try:
            info = client.get_model_info(arg1)
            
            # Basic info
            details = info.get("details", {})
            if details:
                family = details.get("family", "")
                param_size = details.get("parameter_size", "")
                quantization = details.get("quantization_level", "")
                
                if family:
                    print(f"  Family:       {family}")
                if param_size:
                    print(f"  Parameters:   {param_size}")
                if quantization:
                    print(f"  Quantization: {quantization}")
            
            # System prompt
            system = info.get("system", "")
            if system:
                print()
                print(dim("  System prompt:"))
                system_lines = system.split("\n")
                for line in system_lines[:5]:
                    print(dim(f"    {line[:70]}"))
                if len(system_lines) > 5:
                    more_lines = len(system_lines) - 5
                    print(dim(f"    ... ({more_lines} more lines)"))
            
            # Parameters
            params = info.get("parameters", "")
            if params:
                print()
                print(dim("  Parameters:"))
                for line in params.strip().split("\n")[:5]:
                    if line.strip():
                        print(dim(f"    {line.strip()}"))
            
            # Template
            template = info.get("template", "")
            if template:
                print()
                print(dim(f"  Template: {len(template)} chars"))
                
        except Exception as e:
            print(red(f"  ✗ Error getting model info: {e}"))
        print()
        return

    if subcommand == "ps":
        print()
        print(cyan("  Running Models"))
        print(dim("  ─────────────────────────────────────"))
        try:
            running = client.list_running()
            if not running:
                print(dim("  No models currently running."))
            else:
                for m in running:
                    name = m.get("name", "unknown")
                    size = m.get("size", 0)
                    size_gb = size / (1024 * 1024 * 1024)
                    processor = m.get("details", {}).get("gpu", "unknown")
                    until = m.get("expires_at", "")
                    
                    print(f"  {cyan(name)}")
                    print(dim(f"    Size: {size_gb:.2f} GB  |  Processor: {processor}"))
                    if until:
                        print(dim(f"    Until: {until}"))
        except Exception as e:
            print(red(f"  ✗ Error listing running models: {e}"))
        print()
        return

    if subcommand == "stop" and arg1:
        print()
        try:
            result = client.unload_model(arg1)
            if result.get("status") == "not_running":
                print(yellow(f"  ⚠ Model '{arg1}' is not currently running"))
            else:
                print(green(f"  ✓ Unloaded model: {arg1}"))
        except Exception as e:
            print(red(f"  ✗ Error unloading model: {e}"))
        print()
        return

    if subcommand == "cp" and arg1:
        # Parse source and destination
        cp_parts = arg1.split(maxsplit=1)
        if len(cp_parts) < 2:
            print(yellow("  Usage: /ollama cp <source> <destination>"))
            print()
            return
        source, dest = cp_parts
        try:
            client.copy_model(source, dest)
            print(green(f"  ✓ Copied {source} → {dest}"))
        except Exception as e:
            print(red(f"  ✗ Error copying model: {e}"))
        print()
        return

    if subcommand == "set-url" and arg1:
        # Switch to a different Ollama server
        new_url = arg1.rstrip("/")
        client.base_url = new_url
        print()
        print(green(f"  ✓ Switched to: {new_url}"))
        
        # Test connection
        if client.is_running():
            print(green("  ✓ Connection successful"))
            models = client.list_models()
            print(f"  Models available: {len(models)}")
        else:
            print(yellow("  ⚠ Could not connect to the new URL"))
        print()
        return

    # Unknown subcommand
    print()
    print(yellow(f"  Unknown ollama command: {subcommand}"))
    print(dim("  Available commands: list, pull, rm, show, ps, stop, cp, set-url"))
    print()


# ------------------------------------------------------------------ #
#  Colour helpers                                                     #
# ------------------------------------------------------------------ #

# Disable colors entirely - ANSI codes cause issues in some environments
_NO_COLOR = False

def _c(code: str, text: str) -> str:
    if _NO_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"

def dim(t):    return _c("2", t)
def bold(t):   return _c("1", t)
def green(t):  return _c("32", t)
def yellow(t): return _c("33", t)
def cyan(t):   return _c("36", t)
def red(t):    return _c("31", t)
def blue(t):   return _c("34", t)
def magenta(t): return _c("35", t)


# ------------------------------------------------------------------ #
#  Step callback for --verbose                                        #
# ------------------------------------------------------------------ #

def check_tool_used(run, tool_name: str) -> bool:
    """Check if a specific tool was actually called during the run."""
    for step in run.steps:
        if step.type == "tool_call" and step.tool_name == tool_name:
            return True
    return False


def _make_step_printer(verbose: bool, debug: bool = False):
    """Create a step callback for debug output.
    
    Enhanced version matching test file pattern:
    - Shows tool calls with 🔧 emoji
    - Shows tool results with 📦 emoji
    - Shows thoughts with 💭 emoji
    - Shows debug info with 🔍 emoji
    """
    def on_step(step: StepResult):
        if step.type == "tool_call":
            # Show tool call with arguments
            args_str = ", ".join(f"{k}={v}" for k, v in (step.tool_args or {}).items())
            if debug:
                print(f"  {yellow('🔧')} {bold(step.tool_name)}({args_str})")
            elif verbose:
                print(f"  {yellow('⚙')}  {bold(step.tool_name)}({args_str})")
        elif step.type == "tool_result":
            # Show tool result with preview
            result_preview = step.content[:80] + ("..." if len(step.content) > 80 else "")
            if debug:
                print(f"  {blue('📦')} → {dim(result_preview)}")
            elif verbose:
                result_preview_v = step.content[:120] + ("…" if len(step.content) > 120 else "")
                print(f"  {blue('↳')}  {dim(result_preview_v)}")
        elif step.type == "thought" and verbose:
            wrapped = textwrap.fill(step.content, width=80, initial_indent="     ", subsequent_indent="     ")
            print(f"  {dim('💭')} {dim(wrapped.strip())}")
        if debug and hasattr(step, 'debug_info') and step.debug_info:
            print(f"  {magenta('🔍')} {dim(step.debug_info)}")
    return on_step


def _print_run_summary(run, debug: bool = False):
    """Print a summary of the run after completion.
    
    Shows:
    - Total steps and tool calls
    - Tool usage verification
    - Hallucination warnings if expected tools weren't used
    """
    if not run:
        return
    
    tool_calls = [s for s in run.steps if s.type == "tool_call"]
    tool_names = [s.tool_name for s in tool_calls]
    
    if debug:
        print(dim(f"  ⏱️ {len(run.steps)} steps, {len(tool_calls)} tool calls, {run.total_ms:.0f}ms"))
        if tool_names:
            print(dim(f"  🔧 Tools used: {', '.join(set(tool_names))}"))


# ------------------------------------------------------------------ #
#  Build agent from parsed args                                       #
# ------------------------------------------------------------------ #

def _build_agent(args, client: OllamaClient):
    # Resolve tools
    tools_registry = None
    tool_support = "untested"  # Default
    
    if args.tools:
        names = [t.strip() for t in args.tools.split(",")]
        unknown = [n for n in names if BUILTIN_REGISTRY.get(n) is None]
        if unknown:
            print(red(f"Unknown tools: {', '.join(unknown)}"))
            print(f"Run {bold('agentnova tools')} to see available tools.")
            sys.exit(1)
        tools_registry = BUILTIN_REGISTRY.subset(names)
    elif getattr(args, "force_react", False):
        # Auto-load default tools when --force-react is set but no --tools specified
        # This allows BitNet and other models to use tools they hallucinate
        default_tools = ["shell", "python_repl", "calculator"]
        tools_registry = BUILTIN_REGISTRY.subset(default_tools)
        if getattr(args, "verbose", False):
            print(dim(f"  ⚛️ Auto-loaded tools for ReAct: {', '.join(default_tools)}"))

    # Resolve skills
    skill_registry = SkillRegistry()
    if args.skills:
        loader = SkillLoader()
        names = [s.strip() for s in args.skills.split(",")]
        for name in names:
            try:
                skill = loader.load(name)
                skill_registry.add(skill)
            except Exception as e:
                print(red(f"Failed to load skill '{name}': {e}"))
                print(f"Run {bold('agentnova skills')} to see available skills.")
                sys.exit(1)

    # Check tool support level for the model
    #tool_support = "untested"
    if tools_registry:
        try:
            tool_support = get_tool_support(args.model, client)
        except Exception:
            tool_support = "untested"
        
        # If model has no tool support, clear tools registry
        if tool_support == "none":
            if getattr(args, "verbose", False):
                print(yellow(f"  ⚠ Model '{args.model}' has no tool support - tools will be ignored"))
            # Agent will handle this internally, but we can warn the user
            # Tools are kept for reference but Agent passes tools=None to API

    # Build system prompt — structured for small model reliability
    if getattr(args, "system", None):
        # Explicit override via --system flag
        system_prompt = args.system
    elif getattr(args, "use_modelfile_system", False):
        # Use the Modelfile's system prompt instead of AgentNova's default
        mf_system = client.get_modelfile_system_prompt(args.model)
        if mf_system:
            system_prompt = mf_system
            if getattr(args, "verbose", False):
                print(dim(f"  📜 Using Modelfile system prompt ({len(mf_system)} chars)"))
        else:
            # No system prompt in Modelfile, fall back to default with warning
            print(yellow(f"  ⚠ No SYSTEM prompt found in Modelfile for '{args.model}', using AgentNova default"))
            system_prompt = None  # Will trigger default below
    else:
        system_prompt = None
    
    # If no system prompt set yet, use AgentNova's default
    if system_prompt is None:
        tool_lines = ""
        if tools_registry:
            for t in tools_registry.all():
                params = ", ".join(
                    p.name + ("?" if not p.required else "")
                    for p in t.params
                )
                tool_lines += f"  - {t.name}({params}): {t.description}\n"
        else:
            tool_lines = "  (no tools loaded)\n"
        system_prompt = (
            "You are AgentNova, a helpful AI assistant that can use tools.\n"
            "\n"
            "TOOLS AVAILABLE:\n"
            + tool_lines +
            "\n"
            "RULES:\n"
            "1. To use a tool, reply with ONLY raw JSON on a single line — "
            "no markdown, no explanation before or after:\n"
            '   {"name": "tool_name", "arguments": {"param": "value"}}\n'
            "2. Wait for the tool result before continuing.\n"
            "3. If you do NOT need a tool, reply normally in plain text.\n"
            "4. Never invent tool names. Only use the tools listed above.\n"
            "5. Never wrap JSON in ```json``` fences.\n"
            "\n"
            "EXAMPLE:\n"
            "User: What files are in the current directory?\n"
            'Assistant: {"name": "list_directory", "arguments": {"path": "."}}\n'
            "Tool result: file1.py  file2.txt  README.md\n"
            "Assistant: The directory contains: file1.py, file2.txt, and README.md.\n"
            "\n"
            "Now help the user with their request."
        )
    
    # Add skill instructions if skills are loaded
    if len(skill_registry) > 0:
        system_prompt += "\n\n" + skill_registry.to_system_prompt_addition()

    # Get temperature
    temperature = getattr(args, "temperature", 0.7)
    
    # Create ACP plugin if requested
    acp_plugin = None
    if getattr(args, "acp", False):
        acp_plugin = ACPPlugin(
            agent_name="AgentNova",
            model_name=args.model,
            debug=getattr(args, "debug", False),
            on_a2a_message=_on_a2a_message_callback,  # Auto-process A2A messages
        )
        if getattr(args, "verbose", False):
            print(dim(f"  🔗 ACP enabled: {acp_plugin.base_url}"))

    # Build model options for performance tuning
    model_options = {"temperature": temperature} if temperature else {}
    
    # Apply --fast preset if specified
    if getattr(args, "fast", False):
        model_options["num_ctx"] = 2048
        model_options["num_predict"] = 256
        if getattr(args, "verbose", False):
            print(dim("  🚀 Fast mode: num_ctx=2048, num_predict=256"))
    
    # Apply individual options (override --fast if specified)
    if getattr(args, "num_ctx", None):
        model_options["num_ctx"] = args.num_ctx
    if getattr(args, "num_predict", None):
        model_options["num_predict"] = args.num_predict
    
    # Combine step callbacks: verbose printer + ACP plugin
    def combined_on_step(step):
        # Always call printer first (for verbose output)
        _make_step_printer(getattr(args, "verbose", False), getattr(args, "debug", False))(step)
        # Then call ACP plugin if enabled
        if acp_plugin:
            acp_plugin.on_step(step)

    # Debug output: show startup info
    debug = getattr(args, "debug", False)
    if debug:
        print()
        print(cyan("  🔍 Debug Mode Enabled"))
        print(dim("  ─────────────────────────────────────"))
        print(f"  Model: {args.model}")
        
        # Show tool support level
        if tools_registry:
            tool_list = [t.name for t in tools_registry.all()]
            print(f"  Tools: {', '.join(tool_list)}")
            print(f"  Tool Support: {tool_support}")
            if tool_support == "react":
                print(dim("    → Using ReAct text-based tool calling"))
            elif tool_support == "native":
                print(dim("    → Using native API tool calling"))
            elif tool_support == "none":
                print(yellow("    ⚠ Model doesn't support tools"))
        else:
            print(f"  Tools: none")
        
        # Show system prompt info
        print(f"  System Prompt: {len(system_prompt)} chars")
        sys_preview = system_prompt[:100].replace('\n', ' ')
        print(dim(f"    Preview: {sys_preview}..."))
        
        # Show model options
        if model_options:
            opts_str = ", ".join(f"{k}={v}" for k, v in model_options.items())
            print(f"  Model Options: {opts_str}")
        
        if getattr(args, "force_react", False):
            print(f"  Force ReAct: YES")
        print()
    
    agent = Agent(
        model=args.model,
        tools=tools_registry,
        system_prompt=system_prompt,
        client=client,
        on_step=combined_on_step,
        model_options=model_options,
        force_react=getattr(args, "force_react", False),
        debug=getattr(args, "debug", False),
    )
    
    # Store globals for A2A processing
    global _acp_plugin, _tools_registry
    _acp_plugin = acp_plugin
    _tools_registry = tools_registry
    
    return agent, skill_registry, acp_plugin


# ------------------------------------------------------------------ #
#  Commands                                                           #
# ------------------------------------------------------------------ #

def cmd_models(args):
    backend = getattr(args, "backend", "ollama")
    tool_support = getattr(args, "tool_support", False)
    retest = getattr(args, "retest", False)
    verbose = getattr(args, "verbose", False)
    
    if backend == "bitnet":
        if not _BITNET_AVAILABLE:
            print(red("✗  bitnet_client.py not found. Copy it into agentnova/."))
            sys.exit(1)
            
        print(bold("\n⚛️ AgentNova R02.6 BitNet Model (Remote)"))
        
        # We use the client logic to see what is actually running at the URL
        try:
            client = _build_client(args)
            models = client.list_models() # BitnetClient should return the loaded .gguf info
            
            if models:
                print(bold(f"  {'Model Name':<50} {'Status'}"))
                print(dim("  " + "─" * 60))
                for m in models:
                    print(f"  {cyan(m):<50} {green('ACTIVE')}")
            else:
                print(yellow("  No active model found at the BitNet endpoint."))
        except Exception as e:
            print(red(f"  ✗ Could not connect to BitNet backend: {e}"))
        print()
        return
    client = OllamaClient()
    if not client.is_running():
        print(red("✗  Ollama is not running. Start it with: ollama serve"))
        sys.exit(1)

    models = client.list_models()
    if not models:
        print(yellow("No models found. Pull one with: ollama pull llama3.2:3b"))
        return

    print(bold("\n⚛️ AgentNova R02.6 Models") + dim(" · Written by VTSTech · https://www.vts-tech.org · https://github.com/VTSTech/AgentNova"))
    
    # Load tested models from storage
    tested_models = _load_tested_models()
    
    # If --tool_support flag, test each model
    if tool_support:
        # Count how many need testing (or all if --retest)
        if retest:
            need_testing = sorted(models)
            print(cyan(f"\n  Re-testing all {len(need_testing)} model(s)..."))
            print(dim("  Using Modelfile system prompts (no custom prompts)\n"))
        else:
            need_testing = [m for m in sorted(models) if m not in tested_models or 
                            tested_models[m].get("tool_support") not in ("native", "react", "none")]
            
            if need_testing:
                print(cyan(f"\n  Testing tool support for {len(need_testing)} model(s)..."))
                print(dim("  Using Modelfile system prompts (no custom prompts)"))
                print(dim(f"  Skipping {len(models) - len(need_testing)} already tested\n"))
            else:
                print(green("\n  All models already tested! Use --retest to re-test."))
                print(dim(f"  Results stored in {_TESTED_MODELS_FILE}\n"))
        
        for m in sorted(models):
            # Skip already tested models (unless --retest)
            if not retest and m in tested_models:
                existing = tested_models[m].get("tool_support")
                if existing in ("native", "react", "none"):
                    print(dim(f"  ⊙ {m}: {existing} (already tested, skipping)"))
                    continue
            
            result = _test_model_tool_support(client, m, verbose=True)
            tested_models[m] = {
                "tool_support": result,
                "tested_at": datetime.datetime.now().isoformat()
            }
            # Unload the model to free memory before testing next one
            try:
                client.unload_model(m)
            except Exception:
                pass  # Ignore errors during cleanup
        
        # Save results
        _save_tested_models(tested_models)
        print(dim(f"\n  Results saved to {_TESTED_MODELS_FILE}\n"))
    
    # Collect model info
    model_data = []
    for m in sorted(models):
        try:
            info = client.get_model_info(m)
            details = info.get("details", {})
            family = details.get("family", "-")
            
            # Get parameter size (e.g., "7B", "270M")
            param_size = details.get("parameter_size", "")
            
            # Try to get context length from model_info
            # Different models use different keys (llama.context_length, qwen2.context_length, etc.)
            model_info = info.get("model_info", {})
            ctx_length = None
            
            # Search for any context_length key
            for key, value in model_info.items():
                if "context_length" in key.lower():
                    ctx_length = value
                    break
            
            # Also check for standard key patterns
            if not ctx_length:
                ctx_length = model_info.get("llama.context_length", 
                            model_info.get("qwen2.context_length",
                            model_info.get("gemma.context_length",
                            model_info.get("mistral.context_length",
                            model_info.get("phi3.context_length", None)))))
            
            # Format context size
            if ctx_length:
                if ctx_length >= 1000000:
                    ctx_str = f"{ctx_length // 1000}K"
                elif ctx_length >= 1000:
                    ctx_str = f"{ctx_length // 1000}K"
                else:
                    ctx_str = str(ctx_length)
            elif param_size:
                # Use param size as fallback indicator
                ctx_str = param_size
            else:
                ctx_str = "-"
            
            # Get tool support from tested results, or default to untested
            if m in tested_models:
                tool_support = tested_models[m].get("tool_support", "untested")
            else:
                tool_support = "untested"
            
            model_data.append((m, family, ctx_str, tool_support))
        except Exception:
            # Fallback if we can't get model info
            model_data.append((m, "-", "-", "untested"))
    
    # Print table header
    print(bold(f"  {'Model':<42} {'Family':<12} {'Context':<10} {'Tool Support'}"))
    print(dim("  " + "─" * 78))
    
    for m, family, ctx, tool_support in model_data:
        # Format tool support string
        if tool_support == "native":
            support_str = green("✓ native")
        elif tool_support == "react":
            support_str = yellow("ReAct")
        elif tool_support == "none":
            support_str = red("○ none")
        elif tool_support == "error":
            support_str = red("error")
        elif tool_support == "untested":
            support_str = dim("untested")
        else:
            support_str = dim("untested")
        
        # Truncate long model names
        m_display = m[:40] + ".." if len(m) > 42 else m
        family_display = family[:10] + ".." if len(family) > 12 else family
        # Pad first, then apply color (ANSI codes don't count for width)
        m_padded = f"{m_display:<42}"
        family_padded = f"{family_display:<12}"
        ctx_padded = f"{ctx:<10}"
        print(f"  {cyan(m_padded)} {family_padded} {ctx_padded} {support_str}")
    
    # Show hint about testing
    untested_count = sum(1 for _, _, _, ts in model_data if ts == "untested")
    if untested_count > 0:
        print(dim(f"\n  {untested_count} model(s) untested. Use --tool_support to detect native support."))
    print()


def cmd_tools(args):
    tools = BUILTIN_REGISTRY.all()
    print(bold("\n⚛️ AgentNova R02.6 Tools") + dim(" · Written by VTSTech · https://www.vts-tech.org · https://github.com/VTSTech/AgentNova"))
    print(bold(f"{'Tool':<20} Description"))
    print(dim("─" * 70))
    for t in tools:
        params = ", ".join(
            f"{p.name}: {p.type}" + ("?" if not p.required else "")
            for p in t.params
        )
        print(f"  {cyan(t.name):<26} {t.description}")
        if params:
            print(f"  {'':<26} {dim('Args: ' + params)}")
    print()
    print(dim(f"  Use with: --tools {','.join(t.name for t in tools[:3])},…"))
    print()


def cmd_modelfile(args):
    """Show model's Modelfile system prompt and other info."""
    client = OllamaClient()
    
    if not client.is_running():
        print(red("✗  Ollama is not running. Start it with: ollama serve"))
        sys.exit(1)
    
    model = args.model
    print(bold(f"\n⚛️ AgentNova R02.6 Modelfile") + dim(" · Written by VTSTech · https://www.vts-tech.org · https://github.com/VTSTech/AgentNova"))
    print()
    
    try:
        info = client.get_model_info(model)
    except Exception as e:
        print(red(f"✗  Could not get info for model '{model}': {e}"))
        sys.exit(1)
    
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
        # Pretty print parameters if it's a string
        for line in params.strip().split("\n"):
            if line.strip():
                print(dim(f"  {line.strip()}"))
        print()
    
    # License
    license = info.get("license", "")
    if license:
        print(cyan("LICENSE:"))
        print(f"  {license}")
        print()
    
    # Details
    details = info.get("details", {})
    if details:
        print(cyan("DETAILS:"))
        print()
        for key, value in details.items():
            print(dim(f"  {key}: {value}"))
        print()


def cmd_skills(args):
    loader = SkillLoader()
    skills = loader.list_skills()
    
    print(bold("\n⚛️ AgentNova R02.6 Skills") + dim(" · Written by VTSTech · https://www.vts-tech.org · https://github.com/VTSTech/AgentNova"))
    
    if not skills:
        print(yellow("  No skills found."))
        print(dim("  Skills are loaded from agentnova/skills/*/SKILL.md"))
        return
    
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


def _build_client(args):
    """Return OllamaClient or BitnetClient based on --backend flag."""
    backend = getattr(args, "backend", "ollama")
    if backend == "bitnet":
        from .bitnet_client import BitnetClient
        # No longer passing a directory here, just the URL from config or args
        return BitnetClient(base_url=BITNET_BASE_URL)
        bitnet_dir = getattr(args, "bitnet_dir", None) or os.environ.get("BITNET_DIR")
        if not bitnet_dir:
            for candidate in ["./BitNet", "./bitnet", os.path.expanduser("~/BitNet"), "/content/BitNet"]:
                if os.path.exists(candidate):
                    bitnet_dir = candidate
                    break
        if not bitnet_dir:
            print(red("✗  BitNet directory not found."))
            print(dim("   Pass --bitnet-dir /path/to/BitNet  or  set BITNET_DIR env var"))
            sys.exit(1)
        model = getattr(args, "model", "bitnet-b1.58-2b-4t")
        if _BITNET_AVAILABLE and model not in KNOWN_MODELS and not model.endswith(".gguf"):
            model = "bitnet-b1.58-2b-4t"
        threads = getattr(args, "bitnet_threads", None) or max(1, (os.cpu_count() or 4))
        gpu_layers = getattr(args, "bitnet_gpu_layers", 0)
        return BitnetClient(
            bitnet_dir=bitnet_dir,
            model=model,
            threads=threads,
            gpu_layers=gpu_layers,
            verbose=getattr(args, "verbose", False),
            auto_start=True,
        )
    return OllamaClient()


def cmd_run(args):
    client = _build_client(args)
    if not client.is_running():
        if getattr(args, "backend", "ollama") == "bitnet":
            print(red("✗  BitNet backend failed to start. Check --bitnet-dir."))
        else:
            print(red("✗  Ollama is not running. Start it with: ollama serve"))
        sys.exit(1)

    agent, skill_registry, acp_plugin = _build_agent(args, client)

    # Bootstrap ACP if enabled
    if acp_plugin:
        bootstrap_result = acp_plugin.bootstrap(claim_primary=False)  # AgentNova is secondary

    print(bold("⚛️ AgentNova R02.6") + dim(" · Written by VTSTech · https://www.vts-tech.org · https://github.com/VTSTech/AgentNova"))
    print(f"Prompt: {args.prompt}")

    # Log user message to ACP
    if acp_plugin:
        acp_plugin.log_user_message(args.prompt)

    # Use streaming if requested
    if getattr(args, "stream", False):
        if getattr(args, "verbose", False):
            print()
        print(bold("Agent: "), end="", flush=True)
        full_response = ""
        for token in agent.stream(args.prompt):
            print(token, end="", flush=True)
            full_response += token
        print()  # newline after streaming
        if getattr(args, "verbose", False):
            print(dim(f"\n  [streaming mode]"))
        # Log assistant response to ACP
        if acp_plugin:
            acp_plugin.log_assistant_message(full_response)
    else:
        run = agent.run(args.prompt)

        if getattr(args, "verbose", False):
            print()

        print(run.final_answer)

        # Log assistant response to ACP
        if acp_plugin:
            acp_plugin.log_assistant_message(run.final_answer)

        if getattr(args, "verbose", False):
            tool_steps = [s for s in run.steps if s.type == "tool_call"]
            print(dim(f"\n  {len(run.steps)} steps · {len(tool_steps)} tool calls · {run.total_ms:.0f}ms"))


def cmd_chat(args):
    client = _build_client(args)
    backend = getattr(args, "backend", "ollama")

    if not client.is_running():
        if backend == "bitnet":
            # Accessing the base_url we just added to the Client
            url = getattr(client, "base_url", "http://localhost:8765")
            print(red(f"✗  BitNet backend not found at {url}"))
            print(dim("   Ensure llama-server.exe is running in a separate terminal."))
        else:
            print(red("✗  Ollama is not running. Start it with: ollama serve"))
        sys.exit(1)

    # Warm up model if requested (useful for remote Ollama with cold starts)
    if getattr(args, "warmup", False):
        print(dim("  🔥 Warming up model..."), end=" ", flush=True)
        t0 = time.perf_counter()
        try:
            # Simple warmup request - just generate 1 token
            warmup_response = client.chat(
                model=args.model,
                messages=[{"role": "user", "content": "Hi"}],
                options={"num_predict": 1}
            )
            elapsed = (time.perf_counter() - t0) * 1000
            print(green(f"✓ {elapsed:.0f}ms"))
        except Exception as e:
            print(yellow(f"(warmup failed: {e})"))
        print()

    agent, skill_registry, acp_plugin = _build_agent(args, client)

    # Bootstrap ACP if enabled
    if acp_plugin:
        bootstrap_result = acp_plugin.bootstrap(claim_primary=False)  # AgentNova is secondary
        if getattr(args, "verbose", False):
            if bootstrap_result.get("primary_claimed"):
                print(dim(f"  🔗 ACP: Claimed primary agent"))
            else:
                print(dim(f"  🔗 ACP: Connected as secondary agent"))
            if bootstrap_result.get("warnings"):
                for w in bootstrap_result["warnings"]:
                    print(yellow(f"  ⚠ {w}"))

    # Build status line
    parts = [f"[{args.model}"]
    if args.tools:
        parts.append(f"tools: {args.tools}")
    if args.skills:
        parts.append(f"skills: {args.skills}")
    parts.append("]")
    status = " ".join(parts)
    
    print(bold(f"\n⚛️ AgentNova R02.6 chat") + dim(f"  {status} · Written by VTSTech · https://www.vts-tech.org · https://github.com/VTSTech/AgentNova"))
    print(dim("  Type 'exit', 'quit', or Ctrl+C to quit."))
    print(dim("  Type '/help' to see all available commands."))
    print(dim("  Type '/ollama' to manage Ollama models (works with remote Ollama)."))
    print(dim("  ─────────────────────────────────────"))
    
    # Show loaded skills if verbose
    if getattr(args, "verbose", False) and len(skill_registry) > 0:
        print(cyan("\n  Loaded Skills:"))
        for name in skill_registry.list():
            skill = skill_registry.get(name)
            print(dim(f"    • {name}: {skill.description[:60]}..."))
        print()
    
    print()

    try:
        while True:
            try:
                user_input = input(bold("You: ")).strip()
            except EOFError:
                break

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "/exit", "/quit"):
                print(dim("Goodbye."))
                break

            if user_input == "/reset":
                agent.reset()
                print(dim("  ↺  Conversation history cleared."))
                continue

            if user_input == "/tools":
                if agent.tools.all():
                    names = [t.name for t in agent.tools.all()]
                    print(dim(f"  Active tools: {', '.join(names)}"))
                else:
                    print(dim("  No tools active. Use --tools to add some."))
                continue

            if user_input == "/skills":
                if len(skill_registry) > 0:
                    names = skill_registry.list()
                    for name in names:
                        skill = skill_registry.get(name)
                        desc = skill.description[:50] + "..." if len(skill.description) > 50 else skill.description
                        print(dim(f"  • {name}: {desc}"))
                else:
                    print(dim("  No skills active. Use --skills to add some."))
                continue

            if user_input == "/status":
                # Show current session status
                print()
                print(cyan("  Session Status"))
                print(dim("  ─────────────────────────────────────"))
                print(f"  Model:     {bold(args.model)}")
                # Dynamic Labeling based on backend
                backend_label = "BitNet" if getattr(args, "backend", "ollama") == "bitnet" else "Ollama"
                print(f"  {backend_label}:    {agent.client.base_url}")
                print(f"  Timeout:   {agent.client.timeout}s")
                print(f"  ReAct:     {'forced' if getattr(args, 'force_react', False) else 'auto-detect'}")
                
                # Show performance options
                model_opts = agent.model_options
                if model_opts:
                    perf_opts = []
                    if "num_ctx" in model_opts:
                        perf_opts.append(f"ctx={model_opts['num_ctx']}")
                    if "num_predict" in model_opts:
                        perf_opts.append(f"predict={model_opts['num_predict']}")
                    if "temperature" in model_opts:
                        perf_opts.append(f"temp={model_opts['temperature']}")
                    if perf_opts:
                        print(f"  Perf:      {', '.join(perf_opts)}")
                
                print()
                print(f"  Tools:     {len(agent.tools.all())} active")
                if agent.tools.all():
                    print(dim(f"             {', '.join(t.name for t in agent.tools.all())}"))
                print()
                print(f"  Skills:    {len(skill_registry)} active")
                if len(skill_registry) > 0:
                    print(dim(f"             {', '.join(skill_registry.list())}"))
                print()
                print(f"  Memory:    {len(agent.memory._history)} messages")
                print(f"  Max steps: {agent.max_steps}")
                print()
                if "num_ctx" not in model_opts:
                    print(dim("  💡 Tip: Use --fast for quicker responses, or --num-ctx 2048"))
                print()
                continue

            if user_input == "/context":
                # Show context/memory information
                print()
                print(cyan("  Context Information"))
                print(dim("  ─────────────────────────────────────"))
                
                # System prompt
                sys_prompt = agent.memory.system_prompt or "(none)"
                sys_lines = sys_prompt.split('\n')
                print(f"  System prompt: {len(sys_prompt)} chars, {len(sys_lines)} lines")
                if len(sys_lines) <= 5:
                    print(dim("  ┌─────────────────────────────────────"))
                    for line in sys_lines[:5]:
                        print(dim(f"  │ {line[:50]}{'...' if len(line) > 50 else ''}"))
                    print(dim("  └─────────────────────────────────────"))
                else:
                    print(dim(f"  Preview: {sys_lines[0][:60]}..."))
                
                print()
                
                # Memory history
                history = agent.memory._history
                counts = _count_messages(history)
                print(f"  Conversation history: {counts['total']} messages")
                print(dim(f"    • User messages: {counts['user']}"))
                print(dim(f"    • Assistant messages: {counts['assistant']}"))
                print(dim(f"    • Tool results: {counts['tool']}"))
                
                # Estimate token usage (rough: ~4 chars per token)
                total_chars = sum(len(m.content or '') for m in history)
                total_chars += len(sys_prompt)
                est_tokens = total_chars // 4
                print()
                print(f"  Estimated context: ~{est_tokens:,} tokens ({total_chars:,} chars)")
                
                # Skill context
                if len(skill_registry) > 0:
                    print()
                    print("  Skill context loaded:")
                    for name in skill_registry.list():
                        skill = skill_registry.get(name)
                        instr_len = len(skill.instructions)
                        print(dim(f"    • {name}: {instr_len:,} chars"))
                
                print()
                continue

            if user_input == "/a2a":
                # Process pending A2A messages
                if not acp_plugin:
                    print(yellow("  A2A not enabled. Start with --acp flag."))
                    continue
                
                print()
                print(cyan("  A2A Message Processing"))
                print(dim("  ─────────────────────────────────────"))
                
                # Get pending messages
                messages = acp_plugin.a2a_get_inbox()
                if not messages:
                    print(dim("  No pending A2A messages."))
                    print()
                    continue
                
                print(f"  Processing {len(messages)} message(s)...")
                print()
                
                # Process with tool executor
                results = acp_plugin.a2a_process_inbox(
                    tool_executor=_execute_a2a_tool,
                    auto_respond=True
                )
                
                for r in results:
                    status = green("✓") if r.get("status") == "processed" else yellow("○")
                    action = r.get("action", "unknown")
                    from_agent = r.get("from_agent", "unknown")
                    msg_type = r.get("type", "unknown")
                    
                    print(f"  {status} {bold(action)} from {cyan(from_agent)} ({msg_type})")
                    
                    if r.get("result"):
                        result_str = str(r.get("result"))[:200]
                        print(dim(f"    → {result_str}"))
                    elif r.get("error"):
                        print(red(f"    ✗ {r.get('error')}"))
                
                print()
                continue

            if user_input == "/help":
                print()
                print(cyan("  Available Commands"))
                print(dim("  ─────────────────────────────────────"))
                print("  " + bold("Session Control"))
                print(dim("    exit, quit       End the session"))
                print(dim("    /reset           Clear conversation history"))
                print(dim("    /undo            Remove last exchange"))
                print(dim("    /retry           Retry last request"))
                print()
                print("  " + bold("Information"))
                print(dim("    /status          Show session status"))
                print(dim("    /context         Show context/token info"))
                print(dim("    /tools           List active tools"))
                print(dim("    /skills          List active skills"))
                print(dim("    /stats           Show session statistics"))
                print(dim("    /messages        Show raw message history"))
                print()
                print("  " + bold("Ollama Management"))
                print(dim("    /ollama          Show connection status"))
                print(dim("    /ollama list     List available models"))
                print(dim("    /ollama pull <m> Download a model"))
                print(dim("    /ollama rm <m>   Delete a model"))
                print(dim("    /ollama show <m> Show model details"))
                print(dim("    /ollama ps       List running models"))
                print(dim("    /ollama stop <m> Unload a model"))
                print()
                print("  " + bold("A2A Messaging"))
                print(dim("    /a2a             Process pending A2A messages"))
                print()
                print("  " + bold("Export/Save"))
                print(dim("    /export          Export to markdown file"))
                print(dim("    /save <name>     Save conversation"))
                print(dim("    /load <name>     Load conversation"))
                print()
                print("  " + bold("Configuration"))
                print(dim("    /system          View system prompt"))
                print(dim("    /temp <value>    Change temperature"))
                print()
                continue

            # ═══════════════════════════════════════════════════════════════════
            # OLLAMA CLI ALIAS - Works with local or remote Ollama via HTTP API
            # ═══════════════════════════════════════════════════════════════════
            if user_input == "/ollama" or user_input.startswith("/ollama "):
                _handle_ollama_command(user_input, agent.client, args)
                continue

            if user_input == "/undo":
                # Remove last exchange (user + assistant messages)
                history = agent.memory._history
                if len(history) >= 2:
                    # Remove last assistant and user message
                    removed = []
                    while len(history) > 0 and len(removed) < 2:
                        removed.append(history.pop())
                    print(dim(f"  ↺  Removed {len(removed)} messages from history"))
                elif len(history) == 1:
                    history.pop()
                    print(dim("  ↺  Removed 1 message from history"))
                else:
                    print(dim("  No messages to undo"))
                continue

            if user_input == "/retry":
                # Retry the last user message
                history = agent.memory._history
                last_user_msg = None
                for msg in reversed(history):
                    if msg.role == 'user':
                        last_user_msg = msg.content or ''
                        break
                
                if last_user_msg:
                    # Remove last exchange
                    removed = 0
                    while len(history) > 0:
                        last = history[-1]
                        if last.role == 'user' and removed > 0:
                            break
                        history.pop()
                        removed += 1
                    
                    print(dim(f"  ↻  Retrying: {last_user_msg[:50]}..."))
                    run = agent.run(last_user_msg)
                    print(f"{bold('Agent')}: {run.final_answer}")
                    if getattr(args, "verbose", False) and run.steps:
                        tool_steps = [s for s in run.steps if s.type == "tool_call"]
                        print(dim(f"         [{len(tool_steps)} tool calls · {run.total_ms:.0f}ms]"))
                    print()
                else:
                    print(dim("  No user message to retry"))
                continue

            if user_input == "/stats":
                print()
                print(cyan("  Session Statistics"))
                print(dim("  ─────────────────────────────────────"))
                
                # Message counts
                history = agent.memory._history
                counts = _count_messages(history)
                
                print(f"  Messages: {counts['total']} total")
                print(dim(f"    • User: {counts['user']}"))
                print(dim(f"    • Assistant: {counts['assistant']}"))
                print(dim(f"    • Tool results: {counts['tool']}"))
                print()
                
                # Token estimation
                sys_prompt = agent.memory.system_prompt or ""
                total_chars = sum(len(m.content or '') for m in history)
                total_chars += len(sys_prompt)
                est_tokens = total_chars // 4
                print(f"  Estimated tokens: ~{est_tokens:,}")
                print()
                
                # Model info
                print(f"  Model: {args.model}")
                print(f"  Temperature: {getattr(args, 'temperature', 0.7)}")
                print()
                continue

            if user_input == "/messages":
                print()
                print(cyan("  Message History"))
                print(dim("  ─────────────────────────────────────"))
                
                history = agent.memory._history
                if not history:
                    print(dim("  No messages in history"))
                    print()
                    continue
                
                for i, msg in enumerate(history, 1):
                    role = msg.role
                    content = msg.content or ''
                    
                    # Truncate long content
                    if len(content) > 100:
                        content = content[:100] + "..."
                    
                    role_icon = {"user": "👤", "assistant": "🤖", "tool": "🔧"}.get(role, "❓")
                    print(f"  {role_icon} {bold(role)}:")
                    print(dim(f"    {content[:80]}"))
                    print()
                continue

            if user_input == "/export":
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"conversation_{timestamp}.md"
                filepath = Path(filename)
                
                # Build markdown content
                lines = [
                    f"# AgentNova Conversation",
                    f"",
                    f"**Model**: {args.model}",
                    f"**Date**: {datetime.datetime.now().isoformat()}",
                    f"",
                    "---",
                    "",
                ]
                
                history = agent.memory._history
                for msg in history:
                    role = msg.role
                    content = msg.content or ''
                    
                    if role == 'user':
                        lines.append(f"## User")
                        lines.append(f"")
                        lines.append(content)
                        lines.append(f"")
                    elif role == 'assistant':
                        lines.append(f"## Assistant")
                        lines.append(f"")
                        lines.append(content)
                        lines.append(f"")
                    elif role == 'tool':
                        lines.append(f"### Tool Result")
                        lines.append(f"")
                        lines.append(f"```")
                        lines.append(content[:500])
                        lines.append(f"```")
                        lines.append(f"")
                
                filepath.write_text("\n".join(lines), encoding='utf-8')
                print(green(f"  ✓ Exported to {filename}"))
                continue

            if user_input.startswith("/temp "):
                try:
                    new_temp = float(user_input.split()[1])
                    args.temperature = new_temp
                    agent.model_options = {"temperature": new_temp}
                    print(dim(f"  Temperature set to {new_temp}"))
                except (ValueError, IndexError):
                    print(dim("  Usage: /temp <value> (e.g., /temp 0.5)"))
                continue

            if user_input == "/system":
                print()
                print(cyan("  System Prompt"))
                print(dim("  ─────────────────────────────────────"))
                sys_prompt = agent.memory.system_prompt or "(none)"
                print(f"  Length: {len(sys_prompt)} chars")
                print()
                # Show first 500 chars
                preview = sys_prompt[:500]
                print(dim(preview))
                if len(sys_prompt) > 500:
                    print(dim(f"\n  ... ({len(sys_prompt) - 500} more chars)"))
                print()
                continue

            if user_input.startswith("/save "):
                name = user_input.split()[1]
                filename = f"{name}.json"
                filepath = Path(filename)
                data = agent.memory.snapshot()
                data["model"] = args.model
                data["temperature"] = getattr(args, 'temperature', 0.7)
                filepath.write_text(json.dumps(data, indent=2), encoding='utf-8')
                print(green(f"  ✓ Saved to {filename}"))
                continue

            if user_input.startswith("/load "):
                name = user_input.split()[1]
                filename = f"{name}.json"
                filepath = Path(filename)
                
                if not filepath.exists():
                    print(red(f"  ✗ File not found: {filename}"))
                    continue
                
                data = json.loads(filepath.read_text(encoding='utf-8'))
                # Properly deserialize Message objects from dicts
                agent.memory._history = [Message.from_dict(m) for m in data.get("history", [])]
                agent.memory.system_prompt = data.get("system_prompt", agent.memory.system_prompt)
                agent.memory._archived_summary = data.get("archived_summary", "")
                print(green(f"  ✓ Loaded from {filename} ({len(agent.memory._history)} messages)"))
                continue

            # Use streaming if requested
            if getattr(args, "stream", False):
                # Log user message to ACP
                if acp_plugin:
                    acp_plugin.log_user_message(user_input)
                print(bold("Agent: "), end="", flush=True)
                full_response = ""
                for token in agent.stream(user_input):
                    print(token, end="", flush=True)
                    full_response += token
                print()  # newline after streaming
                if getattr(args, "verbose", False):
                    print(dim("         [streaming mode]"))
                print()
                # Log assistant response to ACP
                if acp_plugin:
                    acp_plugin.log_assistant_message(full_response)
            else:
                # Log user message to ACP
                if acp_plugin:
                    acp_plugin.log_user_message(user_input)

                run = None  # Initialize variable to prevent UnboundLocalError
                try:
                    run = agent.run(user_input)
                    
                    # Check if run was successful before accessing attributes
                    if run and hasattr(run, 'final_answer'):
                        print(f"{bold('Agent')}: {run.final_answer}")
                        
                        # Log assistant response to ACP
                        if acp_plugin:
                            acp_plugin.log_assistant_message(run.final_answer)
                        
                        # Show run summary in verbose or debug mode
                        debug = getattr(args, "debug", False)
                        verbose = getattr(args, "verbose", False)
                        if (debug or verbose) and run.steps:
                            _print_run_summary(run, debug=debug)
                except json.JSONDecodeError as e:
                    print(red(f"\n  ✗ BitNet output malformed JSON: {e}"))
                    print(dim("  Tip: Try lowering --temperature to 0.1 for more stable JSON."))
                except Exception as e:
                    print(red(f"\n  ✗ AgentNova Error: {e}"))
                    print(dim("  Tip: The connection was likely dropped during heavy tool-use prefilling."))
                print()

    except KeyboardInterrupt:
        print(f"\n{dim('Interrupted.')}")


def cmd_agent(args):
    """
    Agent Mode - Goal-driven autonomous task execution.

    Unlike chat mode (which is user-driven), agent mode:
    - Plans and executes multi-step tasks autonomously
    - Queues messages while working, processes after completion
    - Supports rollback of current step on /stop
    - Provides progress tracking via slash commands

    State Machine:
      IDLE → WORKING (task given) → IDLE (task done)
                  ↓
             STOPPING (/stop) → IDLE (with optional rollback)
    """
    import threading
    from .agent_mode import format_status, format_progress

    client = _build_client(args)
    backend = getattr(args, "backend", "ollama")

    if not client.is_running():
        if backend == "bitnet":
            url = getattr(client, "base_url", "http://localhost:8765")
            print(red(f"✗  BitNet backend not found at {url}"))
            print(dim("   Ensure llama-server.exe is running in a separate terminal."))
        else:
            print(red("✗  Ollama is not running. Start it with: ollama serve"))
        sys.exit(1)

    # Warm up model if requested
    if getattr(args, "warmup", False):
        print(dim("  🔥 Warming up model..."), end=" ", flush=True)
        t0 = time.perf_counter()
        try:
            warmup_response = client.chat(
                model=args.model,
                messages=[{"role": "user", "content": "Hi"}],
                options={"num_predict": 1}
            )
            elapsed = (time.perf_counter() - t0) * 1000
            print(green(f"✓ {elapsed:.0f}ms"))
        except Exception as e:
            print(yellow(f"(warmup failed: {e})"))
        print()

    agent, skill_registry, acp_plugin = _build_agent(args, client)

    # Bootstrap ACP if enabled
    if acp_plugin:
        bootstrap_result = acp_plugin.bootstrap(claim_primary=False)
        if getattr(args, "verbose", False):
            if bootstrap_result.get("primary_claimed"):
                print(dim(f"  🔗 ACP: Claimed primary agent"))
            else:
                print(dim(f"  🔗 ACP: Connected as secondary agent"))

    # Create AgentMode session
    agent_mode = AgentMode(agent, verbose=getattr(args, "verbose", False))

    # Build status line
    parts = [f"[{args.model}"]
    if args.tools:
        parts.append(f"tools: {args.tools}")
    if args.skills:
        parts.append(f"skills: {args.skills}")
    parts.append("]")
    status = " ".join(parts)

    print(bold(f"\n⚛️ AgentNova R02.6 agent mode") + dim(f"  {status} · Written by VTSTech · https://www.vts-tech.org · https://github.com/VTSTech/AgentNova"))
    print(dim("  Agent mode: Give tasks and the agent will work autonomously."))
    print(dim("  Type '/help' to see available commands."))
    print(dim("  ─────────────────────────────────────"))
    print()

    # State change callback
    def on_state_change(old_state: AgentState, new_state: AgentState):
        if new_state == AgentState.WORKING:
            print(cyan("  ⚙  Agent is working..."))
            print(dim("     Messages will be queued until task completes."))
            print(dim("     Use /status, /progress, or /stop to interact."))
            print()
        elif new_state == AgentState.PAUSED:
            print(yellow("  ⏸  Agent paused."))
            print(dim("     Use /resume to continue or /stop to abort."))
            print()
        elif new_state == AgentState.IDLE and old_state == AgentState.WORKING:
            print(green("  ✓  Agent is now idle."))
            # Process queued messages
            queued = agent_mode.process_queue()
            if queued:
                print(dim(f"     Processing {len(queued)} queued message(s)..."))
                for msg in queued:
                    print(dim(f"     • {msg[:50]}..."))
                print()

    agent_mode.on_state_change = on_state_change

    # Step completion callback
    def on_step_complete(step: Step):
        if getattr(args, "verbose", False):
            print(green(f"  ✓ Step {agent_mode.plan.current_step_index}/{agent_mode.plan.total_steps}: {step.description}"))
            if step.actions:
                print(dim(f"     {len(step.actions)} action(s) completed"))

    agent_mode.on_step_complete = on_step_complete

    # Task completion callback
    def on_task_complete(plan: TaskPlan):
        print()
        print(bold(green("  🏆 Task Complete!")))
        print(dim(f"     Goal: {plan.goal}"))
        print(dim(f"     Steps completed: {plan.completed_steps}/{plan.total_steps}"))
        
        # Show final response from agent
        if agent_mode.final_response:
            print()
            print(cyan("  📝 Final Response:"))
            response = agent_mode.final_response
            for line in response.split("\n"):
                print(f"     {line}")
        
        # Log final response to ACP
        if acp_plugin and agent_mode.final_response:
            acp_plugin.log_assistant_message(agent_mode.final_response)
        
        # Show queued messages
        queued = agent_mode.process_queue()
        if queued:
            print()
            print(yellow(f"  📬 {len(queued)} message(s) queued during execution:"))
            for i, msg in enumerate(queued, 1):
                print(dim(f"     {i}. {msg[:60]}{'...' if len(msg) > 60 else ''}"))
        print()

    agent_mode.on_task_complete = on_task_complete

    # Background task execution
    _execution_thread = None
    _stop_requested = False

    def run_task_in_background(goal: str):
        """Run task in background thread."""
        nonlocal _stop_requested
        _stop_requested = False
        try:
            success, msg = agent_mode.run_task(goal)
            if not success:
                print(red(f"  ✗ Task failed: {msg}"))
        except Exception as e:
            print(red(f"  ✗ Error: {e}"))

    try:
        while True:
            try:
                # Show appropriate prompt based on state
                if agent_mode.state == AgentState.WORKING:
                    prompt_text = bold(yellow("⚙ Working"))
                elif agent_mode.state == AgentState.PAUSED:
                    prompt_text = bold(yellow("⏸ Paused"))
                else:
                    prompt_text = bold("You")
                user_input = input(f"{prompt_text}: ").strip()
            except EOFError:
                break

            if not user_input:
                continue

            # ═══════════════════════════════════════════════════════════════════
            # Always-available slash commands
            # ═══════════════════════════════════════════════════════════════════

            if user_input.lower() in ("exit", "quit", "/exit", "/quit"):
                if agent_mode.state == AgentState.WORKING:
                    print(yellow("  ⚠ Agent is working. Use /stop first or /stop --rollback"))
                else:
                    print(dim("Goodbye."))
                    break
                continue

            if user_input == "/help":
                print()
                print(cyan("  Agent Mode Commands"))
                print(dim("  ─────────────────────────────────────"))
                print("  " + bold("Task Management"))
                print(dim("    <task>          Give agent a task to work on autonomously"))
                print(dim("    /status         Show current agent status and progress"))
                print(dim("    /progress       Show detailed step-by-step progress"))
                print(dim("    /plan           Show the current task plan"))
                print(dim("    /stop           Stop current task (with rollback prompt)"))
                print(dim("    /stop --force   Stop without rollback confirmation"))
                print()
                print("  " + bold("Pause/Resume"))
                print(dim("    /pause          Pause execution (can resume later)"))
                print(dim("    /resume         Resume from paused state"))
                print()
                print("  " + bold("Rollback"))
                print(dim("    /rollback       Rollback current step (when stopped)"))
                print()
                print("  " + bold("Session"))
                print(dim("    /reset          Clear agent memory and plans"))
                print(dim("    /logs           Show execution logs"))
                print(dim("    /help           Show this help message"))
                print(dim("    exit, quit      End the session"))
                print()
                print("  " + bold("Information"))
                print(dim("    /tools          List active tools"))
                print(dim("    /skills         List active skills"))
                print(dim("    /ollama         Ollama management commands"))
                print()
                continue

            if user_input == "/status":
                status = agent_mode.get_status()
                print()
                print(cyan("  Agent Status"))
                print(dim("  ─────────────────────────────────────"))
                print(format_status(status))
                print()
                continue

            if user_input == "/progress":
                progress = agent_mode.get_progress()
                print()
                if "error" in progress:
                    print(yellow(f"  {progress['error']}"))
                else:
                    print(cyan("  Task Progress"))
                    print(dim("  ─────────────────────────────────────"))
                    print(format_progress(progress))
                print()
                continue

            if user_input == "/plan":
                plan = agent_mode.get_plan()
                print()
                if plan is None:
                    print(dim("  No active task plan."))
                    print(dim("  Give the agent a task to create a plan."))
                else:
                    print(cyan("  Current Task Plan"))
                    print(dim("  ─────────────────────────────────────"))
                    print(f"  Goal: {plan['goal']}")
                    print(f"  Created: {plan['created_at']}")
                    print(f"  Steps: {plan['total_steps']}")
                    print()
                    for i, step in enumerate(plan['steps'], 1):
                        icon = {
                            "pending": "○",
                            "in_progress": "◐",
                            "done": "●",
                            "rolled_back": "↺",
                        }.get(step['status'], "?")
                        print(f"    {icon} {i}. {step['description']} [{step['status']}]")
                print()
                continue

            if user_input == "/pause":
                success, msg = agent_mode.pause()
                if success:
                    print(green(f"  ✓ {msg}"))
                else:
                    print(yellow(f"  ⚠ {msg}"))
                continue

            if user_input == "/resume":
                success, msg = agent_mode.resume()
                if success:
                    print(green(f"  ✓ {msg}"))
                else:
                    print(yellow(f"  ⚠ {msg}"))
                continue

            if user_input.startswith("/stop"):
                # Parse rollback option
                force = "--force" in user_input or "-f" in user_input
                no_rollback = "--no-rollback" in user_input

                if agent_mode.state == AgentState.IDLE:
                    print(dim("  Agent is already idle. No task to stop."))
                    continue

                if not force and not no_rollback:
                    # Ask for rollback confirmation
                    print()
                    print(yellow("  Stop current task?"))
                    current_step = agent_mode.plan.current_step_index + 1 if agent_mode.plan else 0
                    total_steps = agent_mode.plan.total_steps if agent_mode.plan else 0
                    print(dim(f"  Currently at step {current_step}/{total_steps}"))
                    print(dim("  Options:"))
                    print(dim("    • [y] Stop and rollback current step"))
                    print(dim("    • [n] Stop without rollback"))
                    print(dim("    • [c] Cancel (continue task)"))

                    try:
                        confirm = input(bold("  Choice [y/N/c]: ")).strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        print(dim("  Cancelled."))
                        continue

                    if confirm == 'c':
                        print(dim("  Continuing task..."))
                        continue
                    elif confirm == 'y':
                        success, msg = agent_mode.stop(rollback=True)
                    else:
                        success, msg = agent_mode.stop(rollback=False)
                else:
                    success, msg = agent_mode.stop(rollback=not no_rollback)

                print(green(f"  ✓ {msg}") if success else yellow(f"  ⚠ {msg}"))
                continue

            if user_input == "/rollback":
                if agent_mode.state != AgentState.IDLE:
                    print(yellow("  Cannot rollback while agent is active. Use /stop first."))
                    continue
                print(yellow("  No current step to rollback."))
                continue

            if user_input == "/logs":
                logs = agent_mode.get_logs(limit=20)
                print()
                print(cyan("  Execution Logs"))
                print(dim("  ─────────────────────────────────────"))
                if not logs:
                    print(dim("  No logs yet."))
                else:
                    for log in logs:
                        log_type = log.get("type", "unknown")
                        timestamp = log.get("timestamp", "")[:19]
                        if log_type == "task_start":
                            print(f"  ▶ {timestamp}: Task started - {log.get('goal', '')[:50]}")
                        elif log_type == "step_start":
                            print(f"    → {timestamp}: Step - {log.get('step_description', '')[:40]}")
                        elif log_type == "step_failed":
                            print(red(f"    ✗ {timestamp}: Step {log.get('step', '?')} failed"))
                        elif log_type == "task_complete":
                            print(green(f"  ✓ {timestamp}: Task completed"))
                        elif log_type == "stop":
                            print(yellow(f"  ⏹ {timestamp}: Stopped (rollback={log.get('rollback', False)})"))
                print()
                continue

            if user_input == "/reset":
                agent.reset()
                agent_mode = AgentMode(agent, verbose=getattr(args, "verbose", False))
                agent_mode.on_state_change = on_state_change
                agent_mode.on_step_complete = on_step_complete
                agent_mode.on_task_complete = on_task_complete
                print(dim("  ↺  Agent memory and plans cleared."))
                continue

            if user_input == "/tools":
                if agent.tools.all():
                    names = [t.name for t in agent.tools.all()]
                    print(dim(f"  Active tools: {', '.join(names)}"))
                else:
                    print(dim("  No tools active. Use --tools to add some."))
                continue

            if user_input == "/skills":
                if len(skill_registry) > 0:
                    names = skill_registry.list()
                    for name in names:
                        skill = skill_registry.get(name)
                        desc = skill.description[:50] + "..." if len(skill.description) > 50 else skill.description
                        print(dim(f"  • {name}: {desc}"))
                else:
                    print(dim("  No skills active. Use --skills to add some."))
                continue

            # Ollama commands (always available)
            if user_input == "/ollama" or user_input.startswith("/ollama "):
                _handle_ollama_command(user_input, agent.client, args)
                continue

            # ═══════════════════════════════════════════════════════════════════
            # Task handling based on state
            # ═══════════════════════════════════════════════════════════════════

            if agent_mode.state == AgentState.WORKING:
                # Queue message while working
                queue_len = agent_mode.queue_message(user_input)
                print(yellow(f"  📬 Message queued (position {queue_len}). Agent will process after task completes."))
                continue

            if agent_mode.state == AgentState.PAUSED:
                print(yellow("  Agent is paused. Use /resume to continue or /stop to abort."))
                continue

            # Agent is IDLE - start a new task
            # Log user message to ACP
            if acp_plugin:
                acp_plugin.log_user_message(user_input)

            print()
            print(cyan(f"  📋 Starting task: {user_input[:60]}{'...' if len(user_input) > 60 else ''}"))
            print(dim("  Agent will work autonomously. Messages will be queued until completion."))
            print()

            _execution_thread = threading.Thread(
                target=run_task_in_background,
                args=(user_input,),
                daemon=True
            )
            _execution_thread.start()

    except KeyboardInterrupt:
        print(f"\n{dim('Interrupted.')}")
        if agent_mode.state == AgentState.WORKING:
            print(yellow("  Agent was working. Use /stop on restart to rollback if needed."))


def cmd_test(args):
    """Run example/test scripts from the agentnova package."""
    import subprocess
    import importlib.util
    
    # Available examples with descriptions
    EXAMPLES = {
        "01": "Basic agent - simple Q&A without tools",
        "01_acp": "Basic agent with ACP tracking",
        "02": "Tool agent - calculator, shell, file tools",
        "02_acp": "Tool agent with ACP tracking",
        "03": "Orchestrator - multi-agent routing demo",
        "03_acp": "Orchestrator with ACP tracking",
        "04": "Comprehensive test - basic + reasoning + code",
        "04_acp": "Comprehensive test with ACP tracking",
        "05": "Tool tests - individual tool demonstrations",
        "05_acp": "Tool tests with ACP tracking",
        "06": "Interactive chat demo",
        "06_acp": "Interactive chat with ACP tracking",
        "07": "Model comparison - 15 tests across models",
        "07_acp": "Model comparison with ACP tracking",
        "08": "Robust comparison - progress-saving benchmark",
        "08_acp": "Robust comparison with ACP tracking",
        "09": "Expanded benchmark - 25 tests, 8 categories",
        "09_acp": "Expanded benchmark with ACP tracking",
        "10": "Skills demo - Agent Skills system",
        "10_acp": "Skills demo with ACP tracking",
        "11": "Skill creator test - benchmark across models",
        "11_acp": "Skill creator test with ACP tracking",
        "12": "Batch operations - ACP batch API demo",
        "12_acp": "Batch operations with ACP tracking",
        "13": "Shutdown demo - ACP graceful shutdown",
        "13_acp": "Shutdown demo with ACP tracking",
        "14": "GSM8K benchmark - 50 math questions",
        "14_acp": "GSM8K benchmark with ACP tracking",
        "15": "Quick diagnostic - 5 questions, ~30s/model",
        "15_acp": "Quick diagnostic with ACP tracking",
        "16": "Agent Mode test - 7 autonomous task tests",
        "16_acp": "Agent Mode test with ACP tracking",
        "backend": "Backend demo - Ollama/BitNet switching",
    }
    
    # Quick test set (skips long-running benchmarks)
    QUICK_TESTS = ["01", "02", "03", "04", "05", "10", "11", "15", "16"]
    
    if args.list:
        print(bold("\n⚛️ AgentNova Test Examples"))
        print(dim("─" * 70))
        for num, desc in sorted(EXAMPLES.items()):
            marker = green("quick") if num in QUICK_TESTS else dim("full")
            print(f"  {cyan(num):<12} {desc}")
            print(f"              {dim('[')}{marker}{dim(']')}")
        print()
        print(dim("  Use --test quick to run quick tests only"))
        print(dim("  Use --test all to run all tests"))
        print()
        return
    
    # Find examples directory (inside agentnova package)
    agentnova_dir = Path(__file__).parent
    examples_dir = agentnova_dir / "examples"
    
    if not examples_dir.exists():
        print(red("✗  Examples directory not found."))
        print(dim("   Examples are included in the agentnova package."))
        print(dim("   Reinstall with: pip install --upgrade agentnova"))
        sys.exit(1)
    
    # Determine which tests to run
    if args.example == "quick":
        to_run = QUICK_TESTS
    elif args.example == "all":
        to_run = list(EXAMPLES.keys())
    else:
        to_run = [args.example]
    
    # Get CLI flags that apply to all tests
    acp_flag = getattr(args, "acp", False)
    
    print(bold("\n⚛️ AgentNova Test Runner"))
    print(dim(f"  Examples directory: {examples_dir}"))
    print()
    
    passed = 0
    failed = 0
    total = len(to_run)
    
    for i, test_id in enumerate(to_run, 1):
        # Find the example file
        example_file = None
        use_acp = acp_flag  # Start with --acp flag value
        
        # Handle _acp suffix: map to base script and enable ACP via env var
        if test_id.endswith("_acp"):
            base_test_id = test_id[:-4]  # Remove _acp suffix
            use_acp = True  # Auto-enable ACP for _acp tests
            # Look for base script (without _acp)
            patterns = [f"{base_test_id}_*.py", f"0{base_test_id}_*.py", f"{base_test_id}*.py"]
            for pattern in patterns:
                matches = list(examples_dir.glob(pattern))
                # Filter out _acp files - we want the base script
                matches = [m for m in matches if "_acp" not in m.stem]
                if matches:
                    example_file = matches[0]
                    break
        else:
            # Standard pattern matching for non-acp tests
            patterns = [f"{test_id}_*.py", f"0{test_id}_*.py", f"{test_id}*.py"]
            for pattern in patterns:
                matches = list(examples_dir.glob(pattern))
                # Filter out _acp files for non-acp tests
                matches = [m for m in matches if "_acp" not in m.stem]
                if matches:
                    example_file = matches[0]
                    break
        
        if not example_file:
            print(yellow(f"  [{i}/{total}] {test_id}: NOT FOUND"))
            failed += 1
            continue
        
        print(bold(f"  [{i}/{total}] Running: {example_file.name}"))
        print(dim(f"         {example_file}"))
        print()
        
        timeout = getattr(args, "timeout", 300)
        
        # Build CLI args to pass to the subprocess
        cmd_args = [sys.executable, str(example_file)]
        if getattr(args, "force_react", False):
            cmd_args.append("--force-react")
        if getattr(args, "use_modelfile_system", False):
            cmd_args.append("--use-mf-sys")
        if getattr(args, "model", None):
            cmd_args.extend(["--model", args.model])
        if getattr(args, "debug", False):
            cmd_args.append("--debug")
        if use_acp:
            cmd_args.append("--acp")
        if getattr(args, "num_ctx", None):
            cmd_args.extend(["--num-ctx", str(args.num_ctx)])
        if getattr(args, "num_predict", None):
            cmd_args.extend(["--num-predict", str(args.num_predict)])
        if getattr(args, "fast", False):
            cmd_args.append("--fast")
        
        try:
            result = subprocess.run(
                cmd_args,
                cwd=examples_dir,
                capture_output=False,
                text=True,
                timeout=timeout,
            )
            
            if result.returncode == 0:
                passed += 1
                print(green(f"  ✓ PASSED"))
            else:
                failed += 1
                print(red(f"  ✗ FAILED (exit code {result.returncode})"))
                if result.stderr:
                    print(dim(f"    {result.stderr[:200]}"))
        except subprocess.TimeoutExpired:
            failed += 1
            print(red(f"  ✗ TIMEOUT (>{timeout}s)"))
        except Exception as e:
            failed += 1
            print(red(f"  ✗ ERROR: {e}"))
        
        print()
    
    # Summary
    print(dim("─" * 70))
    print(bold("  SUMMARY"))
    print(f"    Total:  {total}")
    print(green(f"    Passed: {passed}"))
    if failed > 0:
        print(red(f"    Failed: {failed}"))
    print()
    
    sys.exit(0 if failed == 0 else 1)


# ------------------------------------------------------------------ #
#  Argument parser                                                    #
# ------------------------------------------------------------------ #

def _default_model(client: OllamaClient) -> str:
    """Pick a sensible default from whatever's available."""
    models = client.list_models()
    preferences = ["llama3.1:8b", "llama3.2:3b", "qwen2.5:7b", "mistral", "qwen3", "qwen35", "qwen2.5-coder", "llama3.2:1b"]
    for pref in preferences:
        for m in models:
            if pref in m.lower():
                return m
    return models[0] if models else "llama3.2:1b"


def build_parser() -> argparse.ArgumentParser:
    client = OllamaClient()
    default_model = _default_model(client) if client.is_running() else "llama3.2:1b"

    parser = argparse.ArgumentParser(
        prog="agentnova",
        description="⚛️ AgentNova R02.6 - local agentic AI powered by Ollama",
    )

    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.required = True

    # ── Shared flags ──────────────────────────────────────────────────
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--model", "-m",
        default=default_model,
        metavar="MODEL",
        help=f"Ollama model (default: {default_model})",
    )
    shared.add_argument(
        "--tools", "-t",
        default=None,
        metavar="TOOLS",
        help="Comma-separated tools, e.g. calculator,shell",
    )
    shared.add_argument(
        "--skills", "-k",
        default=None,
        metavar="SKILLS",
        help="Comma-separated skills, e.g. skill-creator",
    )
    shared.add_argument(
        "--system", "-s",
        default=None,
        metavar="PROMPT",
        help="Override system prompt",
    )
    shared.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show tool calls and timing",
    )
    shared.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        metavar="TEMP",
        help="Temperature (default: 0.7)",
    )
    shared.add_argument(
        "--force-react",
        action="store_true",
        help="Force ReAct text-based tool calling (for models without native tool support)",
    )
    # Performance optimization options
    shared.add_argument(
        "--num-ctx",
        type=int,
        default=None,
        metavar="N",
        help="Context window size (default: model default, try 2048 for speed)",
    )
    shared.add_argument(
        "--num-predict",
        type=int,
        default=None,
        metavar="N",
        help="Max tokens to generate (default: -1 for model default, try 128-256 for speed)",
    )
    shared.add_argument(
        "--fast",
        action="store_true",
        help="Fast mode: reduce context (2048) and output (256) for quicker responses",
    )
    shared.add_argument(
        "--warmup",
        action="store_true",
        help="Warm up model with a dummy request before chat (useful for remote Ollama)",
    )
    shared.add_argument(
        "--debug",
        action="store_true",
        help="Show debug info: parsed tool calls, fuzzy matching, etc.",
    )
    shared.add_argument(
        "--stream",
        action="store_true",
        help="Stream output token-by-token (better UX for slow connections)",
    )
    shared.add_argument(
        "--acp",
        action="store_true",
        help="Enable ACP (Agent Control Panel) integration for activity tracking",
    )
    shared.add_argument(
        "--use-mf-sys",
        action="store_true",
        dest="use_modelfile_system",
        help="Use the system prompt from the model's Modelfile instead of AgentNova's default",
    )
    shared.add_argument(
        "--backend",
        default="ollama",
        choices=["ollama", "bitnet"],
        help="Inference backend: ollama (default) or bitnet (bitnet.cpp llama-server)",
    )
    shared.add_argument(
        "--bitnet-dir",
        default=None,
        metavar="DIR",
        dest="bitnet_dir",
        help="Path to BitNet repo (required when --backend bitnet)",
    )
    shared.add_argument(
        "--bitnet-threads",
        type=int,
        default=None,
        metavar="N",
        dest="bitnet_threads",
        help="CPU threads for llama-server (default: all cores)",
    )
    shared.add_argument(
        "--bitnet-gpu-layers",
        type=int,
        default=0,
        metavar="N",
        dest="bitnet_gpu_layers",
        help="GPU layers to offload in llama-server (default: 0)",
    )

    # ── run ─────────────────────────────────────────────────────────
    p_run = sub.add_parser("run", parents=[shared], help="Run a single prompt")
    p_run.add_argument("prompt", help="The prompt to send")
    p_run.set_defaults(func=cmd_run)

    # ── chat ────────────────────────────────────────────────────────
    p_chat = sub.add_parser("chat", parents=[shared], help="Interactive chat")
    p_chat.set_defaults(func=cmd_chat)

    # ── agent ────────────────────────────────────────────────────────
    p_agent = sub.add_parser("agent", parents=[shared], help="Agent mode: autonomous task execution with planning")
    p_agent.set_defaults(func=cmd_agent)

    # ── models ──────────────────────────────────────────────────────
    p_models = sub.add_parser("models", parents=[shared], help="List available models")
    p_models.add_argument("--tool_support", action="store_true", help="Test each model for native tool support")
    p_models.add_argument("--retest", action="store_true", help="Force re-test all models (use with --tool_support)")
    p_models.set_defaults(func=cmd_models)

    # ── tools ───────────────────────────────────────────────────────
    p_tools = sub.add_parser("tools", parents=[shared], help="List available tools")
    p_tools.set_defaults(func=cmd_tools)

    # ── modelfile ──────────────────────────────────────────────────────
    p_modelfile = sub.add_parser("modelfile", parents=[shared], help="Show model's Modelfile system prompt")
    p_modelfile.set_defaults(func=cmd_modelfile)

    # ── skills ──────────────────────────────────────────────────────
    p_skills = sub.add_parser("skills", parents=[shared], help="List available skills")
    p_skills.set_defaults(func=cmd_skills)

    # ── test ────────────────────────────────────────────────────────
    p_test = sub.add_parser("test", help="Run example/test scripts")
    p_test.add_argument(
        "example",
        nargs="?",
        default="quick",
        metavar="EXAMPLE",
        help="Example to run: 'quick' (default), 'all', or specific ID (e.g., '01', '04_acp')",
    )
    p_test.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all available examples",
    )
    p_test.add_argument(
        "--timeout", "-t",
        type=int,
        default=300,
        metavar="SECONDS",
        help="Timeout per test in seconds (default: 300 = 5 min)",
    )
    p_test.add_argument(
        "--force-react",
        action="store_true",
        help="Force ReAct text-based tool calling for all models",
    )
    p_test.add_argument(
        "--use-mf-sys",
        action="store_true",
        dest="use_modelfile_system",
        help="Use the system prompt from the model's Modelfile instead of AgentNova's default",
    )
    p_test.add_argument(
        "--model", "-m",
        default=None,
        metavar="MODEL",
        help="Model to use for tests (overrides AGENTNOVA_MODEL env var)",
    )
    p_test.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output (parsed tool calls, fuzzy matching, etc.)",
    )
    p_test.add_argument(
        "--acp",
        action="store_true",
        help="Enable ACP (Agent Control Panel) integration for activity tracking",
    )
    p_test.add_argument(
        "--num-ctx",
        type=int,
        default=None,
        metavar="TOKENS",
        help="Context window size (default: model's native context length)",
    )
    p_test.add_argument(
        "--num-predict",
        type=int,
        default=None,
        metavar="TOKENS",
        help="Maximum tokens to generate (default: -1 = infinite)",
    )
    p_test.add_argument(
        "--fast",
        action="store_true",
        help="Fast mode preset: num_ctx=2048, num_predict=256",
    )
    p_test.set_defaults(func=cmd_test)

    return parser


# ------------------------------------------------------------------ #
#  Entry point                                                       #
# ------------------------------------------------------------------ #

def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()