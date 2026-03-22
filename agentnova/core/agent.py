"""
⚛️ AgentNova R02.4 — Refactored Agent

A cleaner implementation with separate handlers for each tool support level.

Supports:
  • Native Ollama tool-calling (for models that expose it)
  • Text-based ReAct fallback (for models without native tool support)
  • BitNet backend (via AGENTNOVA_BACKEND=bitnet environment variable)
  • Pure reasoning mode (for models without tool support)

This is a work-in-progress refactor of agent.py. Once tested and verified,
it will replace the original implementation.
"""

from __future__ import annotations

import json
import os as _os
import platform as _platform
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Literal

from .ollama_client import OllamaClient
from .memory import Memory
from .tools import ToolRegistry
from .model_family_config import (
    get_family_config,
    get_no_tools_system_prompt,
    get_react_system_suffix,
    get_native_tool_hints,
    should_use_few_shot,
    get_few_shot_style,
)

# ------------------------------------------------------------------ #
#  Backend selection (Ollama vs BitNet)                               #
# ------------------------------------------------------------------ #
_AGENTNOVA_BACKEND = _os.environ.get("AGENTNOVA_BACKEND", "ollama").lower()

# Try to import BitNet client if needed
if _AGENTNOVA_BACKEND == "bitnet":
    try:
        from ..bitnet_client import BitnetClient
        _BITNET_AVAILABLE = True
    except ImportError:
        _BITNET_AVAILABLE = False
else:
    _BITNET_AVAILABLE = False

# ------------------------------------------------------------------ #
#  Platform detection for cross-platform shell commands               #
# ------------------------------------------------------------------ #
_IS_WINDOWS = _platform.system() == "Windows"
_PLATFORM_DIR_CMD = "cd" if _IS_WINDOWS else "pwd"
_PLATFORM_LIST_CMD = "dir" if _IS_WINDOWS else "ls"


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class StepResult:
    """A single step in an agent run."""
    type: str  # "thought", "tool_call", "tool_result", "final"
    content: str
    tool_name: str | None = None
    tool_args: dict | None = None
    elapsed_ms: float = 0.0


@dataclass
class AgentRun:
    """Result of an agent run."""
    final_answer: str = ""
    steps: list[StepResult] = field(default_factory=list)
    total_ms: float = 0.0
    success: bool = True
    error: str | None = None


# ============================================================
# HELPER FUNCTIONS (shared across modes)
# ============================================================

def _strip_tool_prefix(result: str) -> str:
    """Strip 'tool_name → ' prefix from result."""
    if " → " in result:
        return result.split(" → ", 1)[1]
    return result


def _get_numeric_result(results: list[str]) -> str | None:
    """Get numeric result from tool results if available."""
    if not results:
        return None
    
    last_result = _strip_tool_prefix(results[-1])
    try:
        float(last_result)  # Check if it's numeric
        return last_result
    except (ValueError, TypeError):
        return None


def _synthesize_result(results: list[str], content: str) -> str:
    """Synthesize final answer from results."""
    if not results:
        return content
    
    # Try numeric first
    numeric = _get_numeric_result(results)
    if numeric:
        return numeric
    
    # Return last result
    return _strip_tool_prefix(results[-1])


# Word mappings for fuzzy tool name matching
# Maps keyword → list of acceptable tools (in priority order)
_TOOL_WORD_MAPPINGS = {
    # Calculator-related
    "calculate": ["calculator", "python_repl"],
    "calc": ["calculator", "python_repl"],
    "math": ["calculator", "python_repl"],
    "compute": ["calculator", "python_repl"],
    "sqrt": ["calculator", "python_repl"],
    "square": ["calculator", "python_repl"],
    "root": ["calculator", "python_repl"],
    "power": ["calculator", "python_repl"],
    "multiply": ["calculator", "python_repl"],
    "divide": ["calculator", "python_repl"],
    "add": ["calculator", "python_repl"],
    "subtract": ["calculator", "python_repl"],
    "calculator": ["calculator"],
    
    # Shell-related
    "shell": ["shell"],
    "bash": ["shell"],
    "cmd": ["shell"],
    "command": ["shell"],
    "ls": ["shell"],
    "dir": ["shell"],
    "cat": ["shell"],
    "echo": ["shell"],
    "pwd": ["shell"],
    "grep": ["shell"],
    
    # Python
    "python": ["python_repl", "shell"],
    "repl": ["python_repl", "shell"],
    "code": ["python_repl", "shell"],
    "exec": ["python_repl", "shell"],
    
    # File I/O
    "read": ["read_file"],
    "write": ["write_file"],
    "file": ["read_file", "write_file"],
}


def _fuzzy_match_tool_name(hallucinated_name: str, tools: ToolRegistry) -> str | None:
    """
    Try to match a hallucinated tool name to a real tool.
    
    Small models often call tools by wrong names:
        "ls" → shell
        "echo" → shell
        "sqrt" → calculator
    
    Returns the matched tool name or None if no match found.
    """
    # First, try exact match
    if tools.get(hallucinated_name):
        return hallucinated_name
    
    real_names = [t.name for t in tools.all()]
    lower_hall = hallucinated_name.lower().replace("_", "")
    
    # Strategy 1: Check if any real tool name is a substring
    for real_name in real_names:
        lower_real = real_name.lower().replace("_", "")
        if lower_real in lower_hall or lower_hall in lower_real:
            return real_name
    
    # Strategy 2: Word mappings
    for keyword, tool_hints in _TOOL_WORD_MAPPINGS.items():
        if keyword in lower_hall:
            for tool_hint in tool_hints:
                for real_name in real_names:
                    if tool_hint in real_name or real_name == tool_hint:
                        return real_name
    
    # Strategy 3: First 4 chars match
    for real_name in real_names:
        lower_real = real_name.lower()
        if len(lower_real) >= 4 and len(lower_hall) >= 4:
            if lower_real[:4] == lower_hall[:4]:
                return real_name
    
    return None


# ============================================================
# REFACTORED AGENT CLASS
# ============================================================

class Agent:
    """
    A single autonomous agent backed by a local LLM.
    
    Supports multiple backends:
    - Ollama (default): Full native tool-calling support
    - BitNet: Via AGENTNOVA_BACKEND=bitnet environment variable
    
    Supports three tool support levels:
    - "native": Uses Ollama's built-in tool calling API
    - "react": Uses text-based ReAct prompting
    - "none": Pure reasoning without tools
    """
    
    def __init__(
        self,
        model: str,
        tools: ToolRegistry | None = None,
        system_prompt: str = "You are a helpful assistant.",
        max_steps: int = 10,
        client: OllamaClient | None = None,
        force_react: bool = False,
        on_step: Callable[[StepResult], None] | None = None,
        model_options: dict | None = None,
        memory_max_turns: int = 20,
        debug: bool = False,
        model_family: str | None = None,
    ):
        self.model = model
        self.tools = tools or ToolRegistry()
        self.max_steps = max_steps
        self.debug = debug
        self.on_step = on_step
        
        # Backend-aware client selection
        if client is not None:
            self.client = client
        elif _AGENTNOVA_BACKEND == "bitnet" and _BITNET_AVAILABLE:
            from ..bitnet_client import BitnetClient
            from ..config import BITNET_BASE_URL
            self.client = BitnetClient(base_url=BITNET_BASE_URL)
        else:
            self.client = OllamaClient()
        
        # Get model family from client API (if available)
        if hasattr(self.client, 'get_model_family'):
            self._model_family = self.client.get_model_family(model) or "unknown"
        else:
            self._model_family = "unknown"
        self._model_family_config = get_family_config(self._model_family)
        
        # Extract config fields for easy access
        config = self._model_family_config
        self._needs_no_think = config.needs_think_directive
        self._stop_tokens = config.stop_tokens
        self._has_schema_dump_issue = config.has_schema_dump_issue
        self._truncate_json_args = config.truncate_json_args
        self._system_prompt_style = config.system_prompt_style
        self._prefers_few_shot = config.prefers_few_shot
        self._few_shot_style = config.few_shot_style
        self._reasoning_hints = config.reasoning_hints
        
        # Apply preferred_temperature if not specified
        self.model_options = model_options or {}
        if "temperature" not in self.model_options:
            self.model_options["temperature"] = config.preferred_temperature
        
        # Determine tool support level
        if force_react:
            self._tool_support = "react"
        else:
            try:
                from ..cli import get_tool_support
                self._tool_support = get_tool_support(model, self.client)
            except ImportError:
                # Fallback for BitNet or when CLI not available
                self._tool_support = "react"
        
        self._native_tools = (self._tool_support == "native")
        self._no_tools = (self._tool_support == "none")
        
        # Build system prompt based on tool support and family config
        final_system_prompt = self._build_system_prompt(system_prompt)
        
        self.memory = Memory(system_prompt=final_system_prompt, max_turns=memory_max_turns)
        
        if debug:
            print(f"Agent initialized: model={model}, tool_support={self._tool_support}, "
                  f"family={self._model_family}, temp={self.model_options.get('temperature')}")
    
    def _build_system_prompt(self, base_prompt: str) -> str:
        """Build the appropriate system prompt based on tool support and family config."""
        config = self._model_family_config
        
        # Pure reasoning mode - use family-specific no-tools prompt
        if self._no_tools:
            family_prompt = get_no_tools_system_prompt(self._model_family)
            return family_prompt or base_prompt
        
        # Native tools mode - add tool usage hints
        if self._native_tools:
            hints = get_native_tool_hints(self._model_family)
            if hints:
                return f"{base_prompt}\n\n{hints}"
            return base_prompt
        
        # ReAct mode - add ReAct format instructions
        react_suffix = get_react_system_suffix(self._model_family)
        
        # Add reasoning hints if configured
        if self._reasoning_hints:
            hints_text = "\n".join(f"- {h}" for h in self._reasoning_hints)
            base_prompt = f"{base_prompt}\n\nReasoning approach:\n{hints_text}"
        
        return f"{base_prompt}\n\n{react_suffix}"
    
    def _get_chat_options(self) -> dict:
        """Get model options including stop tokens from family config."""
        options = dict(self.model_options)
        if self._stop_tokens:
            # Merge with any existing stop tokens
            existing_stop = options.get("stop", [])
            if isinstance(existing_stop, str):
                existing_stop = [existing_stop]
            options["stop"] = list(set(existing_stop + self._stop_tokens))
        return options
    
    def run(self, user_input: str) -> AgentRun:
        """
        Run the agent on a user message.
        
        Dispatches to the appropriate handler based on tool support level.
        """
        self.memory.add_user(user_input)
        
        if self._no_tools:
            return self._run_pure_reasoning(user_input)
        elif self._native_tools:
            return self._run_native_tools(user_input)
        else:
            return self._run_react_mode(user_input)
    
    def chat(self, user_input: str) -> str:
        """Convenience wrapper — returns just the final answer string."""
        return self.run(user_input).final_answer
    
    def reset(self):
        """Clear conversation history."""
        self.memory.clear()
    
    # ============================================================
    # MODE HANDLERS
    # ============================================================
    
    def _run_pure_reasoning(self, user_input: str) -> AgentRun:
        """Handle models with no tool support - pure reasoning mode."""
        run = AgentRun()
        t0 = time.perf_counter()
        
        step_t0 = time.perf_counter()
        response = self.client.chat(
            model=self.model,
            messages=self.memory.to_messages(),
            tools=None,
            options=self.model_options,
            think=False if self._needs_no_think else None,
        )
        elapsed = (time.perf_counter() - step_t0) * 1000
        
        content = response.get("message", {}).get("content", "")
        
        if self.debug:
            print(f"\n  🔍 DEBUG: Pure reasoning mode")
            print(f"    content[:100]={content[:100]!r}")
        
        self.memory.add_assistant(content)
        run.final_answer = content
        run.steps.append(StepResult(type="final", content=content, elapsed_ms=elapsed))
        
        if self.on_step:
            self.on_step(run.steps[-1])
        
        run.total_ms = (time.perf_counter() - t0) * 1000
        return run
    
    def _run_native_tools(self, user_input: str) -> AgentRun:
        """Handle models with Ollama native tool calling."""
        run = AgentRun()
        t0 = time.perf_counter()
        
        # State tracking
        tool_call_counts: dict[str, int] = {}
        successful_results: list[str] = []
        max_calls_per_tool = 2
        max_total_tool_calls = 4
        
        for step_num in range(self.max_steps):
            step_t0 = time.perf_counter()
            
            response = self.client.chat(
                model=self.model,
                messages=self.memory.to_messages(),
                tools=self.tools.schemas() if self.tools.all() else None,
                options=self.model_options,
                think=False if self._needs_no_think else None,
            )
            
            elapsed = (time.perf_counter() - step_t0) * 1000
            msg = response.get("message", {})
            content = msg.get("content", "")
            tool_calls_raw = msg.get("tool_calls", [])
            
            if self.debug:
                print(f"\n  🔍 DEBUG: Native tools response")
                print(f"    tool_calls={len(tool_calls_raw)}")
                print(f"    content[:100]={content[:100]!r}")
            
            # No tool calls - check if done
            if not tool_calls_raw:
                # Synthesize final answer from results
                run.final_answer = _synthesize_result(successful_results, content)
                
                self.memory.add_assistant(content)
                run.steps.append(StepResult(type="final", content=run.final_answer, elapsed_ms=elapsed))
                if self.on_step:
                    self.on_step(run.steps[-1])
                break
            
            # Process tool calls
            for tc in tool_calls_raw:
                fn = tc.get("function", {})
                t_name = fn.get("name", "")
                t_args = fn.get("arguments", {})
                
                if isinstance(t_args, str):
                    try:
                        t_args = json.loads(t_args)
                    except json.JSONDecodeError:
                        t_args = {}
                
                # Check limits
                tool_call_counts[t_name] = tool_call_counts.get(t_name, 0) + 1
                total_calls = sum(tool_call_counts.values())
                if tool_call_counts[t_name] > max_calls_per_tool or total_calls > max_total_tool_calls:
                    if self.debug:
                        print(f"    Max calls reached for {t_name}")
                    run.final_answer = _synthesize_result(successful_results, content)
                    run.steps.append(StepResult(type="final", content=run.final_answer, elapsed_ms=elapsed))
                    if self.on_step:
                        self.on_step(run.steps[-1])
                    return run
                
                # Execute tool
                if self.tools.get(t_name):
                    if self.debug:
                        args_str = ", ".join(f"{k}={v}" for k, v in t_args.items())
                        print(f"    🔧 {t_name}({args_str})")
                    
                    run.steps.append(StepResult(
                        type="tool_call",
                        content="",
                        tool_name=t_name,
                        tool_args=t_args,
                        elapsed_ms=elapsed,
                    ))
                    if self.on_step:
                        self.on_step(run.steps[-1])
                    
                    result = str(self.tools.invoke(t_name, t_args))
                    
                    if self.debug:
                        preview = result[:60] + "..." if len(result) > 60 else result
                        print(f"    📦 → {preview}")
                    
                    run.steps.append(StepResult(type="tool_result", content=result, tool_name=t_name))
                    if self.on_step:
                        self.on_step(run.steps[-1])
                    
                    if not result.startswith(("[Tool error]", "[Calculator error]")):
                        successful_results.append(f"{t_name} → {result}")
                    
                    # Add observation to memory
                    self.memory.add_assistant(content)
                    self.memory.add_user(f"Observation: {result}")
            
            # Check if we should synthesize after tool execution
            if successful_results and _is_simple_query(user_input):
                final = _synthesize_result(successful_results, content)
                if final:
                    run.final_answer = final
                    run.steps.append(StepResult(type="final", content=final, elapsed_ms=elapsed))
                    if self.on_step:
                        self.on_step(run.steps[-1])
                    break
        
        run.total_ms = (time.perf_counter() - t0) * 1000
        return run
    
    def _run_react_mode(self, user_input: str) -> AgentRun:
        """Handle models using text-based ReAct prompting."""
        run = AgentRun()
        t0 = time.perf_counter()
        
        # State tracking
        tool_call_counts: dict[str, int] = {}
        successful_results: list[str] = []
        max_calls_per_tool = 2
        max_total_tool_calls = 4
        format_reminder_sent = False
        
        # ReAct patterns (including same-line variant for small models)
        thought_re = re.compile(r"Thought:\s*(.*?)(?=Action:|Final Answer:|$)", re.DOTALL | re.IGNORECASE)
        action_re = re.compile(
            r"Action:\s*[`\"']?(\w+)[`\"']?\s*\n?\s*Action Input:\s*(.*?)(?=\n\s*(?:Observation:|Thought:|Final Answer:|Action:)|$)",
            re.DOTALL | re.IGNORECASE
        )
        action_same_line_re = re.compile(
            r"Action:\s*[`\"']?(\w+)[`\"']?\s+Action Input:\s*(.*?)(?=\n\s*(?:Observation:|Thought:|Final Answer:|Action:)|$)",
            re.DOTALL | re.IGNORECASE
        )
        final_re = re.compile(r"Final Answer:\s*(.*?)$", re.DOTALL | re.IGNORECASE)
        
        for step_num in range(self.max_steps):
            step_t0 = time.perf_counter()
            
            response = self.client.chat(
                model=self.model,
                messages=self.memory.to_messages(),
                tools=None,
                options=self.model_options,
                think=False if self._needs_no_think else None,
            )
            
            elapsed = (time.perf_counter() - step_t0) * 1000
            content = response.get("message", {}).get("content", "")
            
            if self.debug:
                print(f"\n  🔍 DEBUG: ReAct response")
                print(f"    content[:200]={content[:200]!r}")
            
            # Parse ReAct format
            thought_match = thought_re.search(content)
            thought = thought_match.group(1).strip() if thought_match else None
            
            # Try multiline action first, then same-line format (for small models)
            action_match = action_re.search(content)
            if not action_match:
                action_match = action_same_line_re.search(content)
            
            t_name = action_match.group(1).strip() if action_match else None
            raw_args = action_match.group(2).strip() if action_match else None
            
            final_match = final_re.search(content)
            final_answer = final_match.group(1).strip() if final_match else None
            
            if self.debug:
                print(f"    thought={thought!r}")
                print(f"    t_name={t_name!r}")
                print(f"    final_answer={final_answer!r}")
            
            # IMPORTANT: Check for tool call FIRST, before final_answer
            # Models may hallucinate Observation and Final Answer in the same response
            # We must execute the actual tool call, not trust the hallucinated answer
            
            # Handle thought
            if thought:
                run.steps.append(StepResult(type="thought", content=thought, elapsed_ms=elapsed))
                if self.on_step:
                    self.on_step(run.steps[-1])
            
            # Handle tool call - PRIORITIZE OVER FINAL ANSWER
            if t_name and raw_args:
                # Parse args
                if raw_args.startswith('{'):
                    try:
                        t_args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        t_args = {"expression": raw_args}
                else:
                    t_args = {"expression": raw_args}
                
                # Check limits
                tool_call_counts[t_name] = tool_call_counts.get(t_name, 0) + 1
                total_calls = sum(tool_call_counts.values())
                if tool_call_counts[t_name] > max_calls_per_tool or total_calls > max_total_tool_calls:
                    if self.debug:
                        print(f"    Max calls for {t_name}")
                    run.final_answer = _synthesize_result(successful_results, content)
                    run.steps.append(StepResult(type="final", content=run.final_answer, elapsed_ms=elapsed))
                    if self.on_step:
                        self.on_step(run.steps[-1])
                    return run
                
                # Check if tool exists, try fuzzy matching if not
                original_t_name = t_name
                if not self.tools.get(t_name):
                    fuzzy_name = _fuzzy_match_tool_name(t_name, self.tools)
                    if self.debug:
                        print(f"    fuzzy_match({t_name!r}) -> {fuzzy_name!r}")
                    if fuzzy_name:
                        # Handle special cases for shell commands
                        if fuzzy_name == "shell" and original_t_name.lower() in ("ls", "dir", "pwd", "echo", "cat", "grep"):
                            # Model called a command as a tool name - synthesize proper command
                            if original_t_name.lower() == "ls":
                                t_args = {"command": "ls"}
                            elif original_t_name.lower() == "dir":
                                t_args = {"command": "dir"}
                            elif original_t_name.lower() == "pwd":
                                t_args = {"command": "pwd"}
                            elif original_t_name.lower() == "echo":
                                text_val = t_args.get("text") or t_args.get("message") or t_args.get("input") or ""
                                t_args = {"command": f"echo {text_val}" if text_val else "echo"}
                            elif original_t_name.lower() == "cat":
                                path = t_args.get("path") or t_args.get("file") or t_args.get("input") or ""
                                t_args = {"command": f"cat {path}" if path else "cat"}
                            elif original_t_name.lower() == "grep":
                                pattern = t_args.get("pattern") or t_args.get("text") or t_args.get("input") or ""
                                t_args = {"command": f"grep {pattern}" if pattern else "grep"}
                        t_name = fuzzy_name
                    else:
                        if self.debug:
                            print(f"    Unknown tool: {original_t_name}")
                        self.memory.add_assistant(content)
                        self.memory.add_user(f"Tool '{original_t_name}' not found. Available: {[t.name for t in self.tools.all()]}")
                        continue
                
                # Execute tool
                if self.tools.get(t_name):
                    if self.debug:
                        args_str = ", ".join(f"{k}={v}" for k, v in t_args.items())
                        print(f"    🔧 {t_name}({args_str})")
                    
                    run.steps.append(StepResult(
                        type="tool_call",
                        content="",
                        tool_name=t_name,
                        tool_args=t_args,
                        elapsed_ms=elapsed,
                    ))
                    if self.on_step:
                        self.on_step(run.steps[-1])
                    
                    result = str(self.tools.invoke(t_name, t_args))
                    
                    if self.debug:
                        preview = result[:60] + "..." if len(result) > 60 else result
                        print(f"    📦 → {preview}")
                    
                    run.steps.append(StepResult(type="tool_result", content=result, tool_name=t_name))
                    if self.on_step:
                        self.on_step(run.steps[-1])
                    
                    if not result.startswith(("[Tool error]", "[Calculator error]")):
                        successful_results.append(f"{t_name} → {result}")
                    
                    # Add observation (as user for model to respond)
                    self.memory.add_assistant(content)
                    self.memory.add_user(f"Observation: {result}\n\nNow provide your Final Answer:")
            
            # No tool call but we have final_answer - accept it
            elif not t_name and final_answer:
                run.final_answer = final_answer
                run.steps.append(StepResult(type="final", content=final_answer, elapsed_ms=elapsed))
                if self.on_step:
                    self.on_step(run.steps[-1])
                self.memory.add_assistant(content)
                break
            
            # No action, no final - check if we have results
            elif not t_name and successful_results:
                # Check for incomplete ReAct output
                content_stripped = content.strip()
                if content_stripped.startswith("Thought:") and "Final Answer:" not in content_stripped:
                    numeric = _get_numeric_result(successful_results)
                    if numeric:
                        if self.debug:
                            print(f"    Using numeric result: {numeric}")
                        run.final_answer = numeric
                        run.steps.append(StepResult(type="final", content=numeric, elapsed_ms=elapsed))
                        if self.on_step:
                            self.on_step(run.steps[-1])
                        break
                
                run.final_answer = content
                run.steps.append(StepResult(type="final", content=content, elapsed_ms=elapsed))
                if self.on_step:
                    self.on_step(run.steps[-1])
                self.memory.add_assistant(content)
                break
            
            # Format reminder
            elif not t_name and not successful_results and not format_reminder_sent:
                format_reminder_sent = True
                if self.debug:
                    print(f"    Sending format reminder")
                tool_names = [t.name for t in self.tools.all()]
                self.memory.add_assistant(content)
                self.memory.add_user(
                    f"Use ReAct format:\n"
                    f"Action: {tool_names[0]}\n"
                    f"Action Input: {{\"expression\": \"<calc>\"}}"
                )
                continue
            
            else:
                # Return content as-is
                run.final_answer = content
                run.steps.append(StepResult(type="final", content=content, elapsed_ms=elapsed))
                if self.on_step:
                    self.on_step(run.steps[-1])
                self.memory.add_assistant(content)
                break
        
        run.total_ms = (time.perf_counter() - t0) * 1000
        return run


def _is_simple_query(text: str) -> bool:
    """Check if the query is simple enough for immediate synthesis."""
    lower = text.lower()
    # Keywords that indicate a simple math/query task
    simple_keywords = [
        "what is", "calculate", "compute", "sqrt", 
        "date", "time", "how many", "how much",
        "use the calculator", "use calculator"
    ]
    # Check for any keyword (no length limit - word problems can be verbose)
    return any(kw in lower for kw in simple_keywords)