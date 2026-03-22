"""
⚛️ AgentNova R02.3 — Agent Mode Handlers

Separate handlers for each tool support level:
- _run_pure_reasoning: Models with no tool support (tool_support=none)
- _run_native_tools: Models with Ollama API tool calling (tool_support=native)
- _run_react_mode: Models needing text-based ReAct parsing (tool_support=react)

This module provides cleaner separation of concerns compared to the monolithic
run() method in agent.py.
"""

import json
import re
import time
from typing import Callable, Any

from .tools import ToolRegistry, Tool, ToolParam
from .memory import Memory
from .ollama_client import OllamaClient
from .model_family_config import get_model_config, ModelFamilyConfig


class StepResult:
    """A single step in an agent run."""
    type: str  # "thought", "tool_call", "tool_result", "final"
    content: str
    tool_name: str | None = None
    tool_args: dict | None = None
    elapsed_ms: float = 0.0

    def __init__(self, type: str, content: str, tool_name: str = None,
                 tool_args: dict = None, elapsed_ms: float = 0.0):
        self.type = type
        self.content = content
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.elapsed_ms = elapsed_ms


class AgentRun:
    """Result of an agent run."""
    final_answer: str = ""
    steps: list[StepResult]
    total_ms: float = 0.0
    success: bool = True
    error: str | None = None

    def __init__(self):
        self.steps = []


# ============================================================
# PURE REASONING MODE (tool_support=none)
# ============================================================

def run_pure_reasoning(
    client: OllamaClient,
    model: str,
    memory: Memory,
    model_options: dict,
    needs_no_think: bool,
    debug: bool,
    on_step: Callable[[StepResult], None] | None = None,
) -> AgentRun:
    """
    Run agent in pure reasoning mode (no tools).
    
    Used for models that don't support tool calling at all.
    Simply sends the prompt to the LLM and returns the response.
    
    Args:
        client: OllamaClient instance
        model: Model name
        memory: Conversation memory with system prompt and history
        model_options: Model options (temperature, num_ctx, etc.)
        needs_no_think: Whether to disable thinking mode
        debug: Enable debug output
        on_step: Optional callback for step events
    
    Returns:
        AgentRun with the final answer
    """
    run = AgentRun()
    t0 = time.perf_counter()
    
    step_t0 = time.perf_counter()
    response = client.chat(
        model=model,
        messages=memory.to_messages(),
        tools=None,  # Don't pass tools
        options=model_options,
        think=False if needs_no_think else None,
    )
    elapsed = (time.perf_counter() - step_t0) * 1000
    
    msg = response.get("message", {})
    content = msg.get("content", "")
    
    if debug:
        print(f"\n  🔍 DEBUG: Pure reasoning mode")
        print(f"    content[:100]={content[:100]!r}")
    
    # Store and return the response
    memory.add_assistant(content)
    run.final_answer = content
    run.total_ms = elapsed
    run.steps.append(StepResult(type="final", content=content, elapsed_ms=elapsed))
    
    if on_step:
        on_step(run.steps[-1])
    
    run.total_ms = (time.perf_counter() - t0) * 1000
    return run


# ============================================================
# NATIVE TOOLS MODE (tool_support=native)
# ============================================================

def run_native_tools(
    client: OllamaClient,
    model: str,
    memory: Memory,
    tools: ToolRegistry,
    model_options: dict,
    max_steps: int,
    needs_no_think: bool,
    debug: bool,
    on_step: Callable[[StepResult], None] | None = None,
) -> AgentRun:
    """
    Run agent using Ollama's native tool calling API.
    
    Used for models that support the tools parameter in the Ollama API.
    The model returns structured tool_calls that we execute directly.
    
    Args:
        client: OllamaClient instance
        model: Model name
        memory: Conversation memory
        tools: Tool registry with available tools
        model_options: Model options
        max_steps: Maximum iterations
        needs_no_think: Whether to disable thinking mode
        debug: Enable debug output
        on_step: Optional callback for step events
    
    Returns:
        AgentRun with steps and final answer
    """
    run = AgentRun()
    t0 = time.perf_counter()
    
    # Loop guards
    tool_call_counts: dict[str, int] = {}
    successful_results: list[str] = []
    max_calls_per_tool = 2
    max_total_tool_calls = 4
    
    for step_num in range(max_steps):
        step_t0 = time.perf_counter()
        
        response = client.chat(
            model=model,
            messages=memory.to_messages(),
            tools=tools.schemas(),
            options=model_options,
            think=False if needs_no_think else None,
        )
        
        elapsed = (time.perf_counter() - step_t0) * 1000
        msg = response.get("message", {})
        content = msg.get("content", "")
        tool_calls_raw = msg.get("tool_calls", [])
        
        if debug:
            print(f"\n  🔍 DEBUG: Native tools response")
            print(f"    tool_calls_raw={tool_calls_raw!r}")
            print(f"    content (FULL): {content!r}")
        
        # No tool calls - we're done
        if not tool_calls_raw:
            # Check if we have numeric results to return
            if successful_results:
                final_answer = _get_numeric_result(successful_results)
                if final_answer:
                    run.final_answer = final_answer
                    run.steps.append(StepResult(type="final", content=final_answer, elapsed_ms=elapsed))
                    if on_step:
                        on_step(run.steps[-1])
                    break
            
            # Return content as-is
            memory.add_assistant(content)
            run.final_answer = content
            run.steps.append(StepResult(type="final", content=content, elapsed_ms=elapsed))
            if on_step:
                on_step(run.steps[-1])
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
            
            # Check tool call limits
            tool_call_counts[t_name] = tool_call_counts.get(t_name, 0) + 1
            total_calls = sum(tool_call_counts.values())
            
            if tool_call_counts[t_name] > max_calls_per_tool or total_calls > max_total_tool_calls:
                # Hit limits - synthesize from what we have
                final_answer = _synthesize_result(successful_results, content)
                run.final_answer = final_answer
                run.steps.append(StepResult(type="final", content=final_answer, elapsed_ms=elapsed))
                if on_step:
                    on_step(run.steps[-1])
                break
            
            # Execute tool
            if tools.get(t_name):
                # Normalize args
                t_args = _normalize_args(t_args, tools.get(t_name))
                
                if debug:
                    print(f"    🔧 {t_name}({t_args})")
                
                run.steps.append(StepResult(
                    type="tool_call",
                    content="",
                    tool_name=t_name,
                    tool_args=t_args,
                    elapsed_ms=elapsed,
                ))
                if on_step:
                    on_step(run.steps[-1])
                
                result = tools.invoke(t_name, t_args)
                result_str = str(result)
                
                if debug:
                    preview = result_str[:60] + "..." if len(result_str) > 60 else result_str
                    print(f"    📦 → {preview}")
                
                run.steps.append(StepResult(type="tool_result", content=result_str, tool_name=t_name))
                if on_step:
                    on_step(run.steps[-1])
                
                if not result_str.startswith("[Tool error]"):
                    successful_results.append(f"{t_name} → {result_str}")
                
                # Add observation to memory
                memory.add_assistant(content)
                memory.add_user(f"Observation: {result_str}")
            else:
                if debug:
                    print(f"    ⚠️ Unknown tool: {t_name}")
        
        # Check if we should synthesize after tool calls
        if successful_results and _is_simple_query(memory):
            final_answer = _get_numeric_result(successful_results)
            if final_answer:
                run.final_answer = final_answer
                run.steps.append(StepResult(type="final", content=final_answer, elapsed_ms=elapsed))
                if on_step:
                    on_step(run.steps[-1])
                break
    
    run.total_ms = (time.perf_counter() - t0) * 1000
    return run


# ============================================================
# REACT MODE (tool_support=react)
# ============================================================

# ReAct parsing regex patterns
_THOUGHT_RE = re.compile(r"Thought:\s*(.*?)(?=Action:|Final Answer:|$)", re.DOTALL | re.IGNORECASE)
_ACTION_RE = re.compile(
    r"Action:\s*[`\"']?(\w+)[`\"']?\s*\n?\s*Action Input:\s*(.*?)(?=\n\s*(?:Observation:|Thought:|Final Answer:|Action:|Example)|$)",
    re.DOTALL | re.IGNORECASE
)
_ACTION_SAME_LINE_RE = re.compile(
    r"Action:\s*[`\"']?(\w+)[`\"']?\s+Action Input:\s*(.*?)(?=\n\s*(?:Observation:|Thought:|Final Answer:|Action:|Example)|$)",
    re.DOTALL | re.IGNORECASE
)
_FINAL_RE = re.compile(r"Final Answer:\s*(.*?)$", re.DOTALL | re.IGNORECASE)


def _parse_react(text: str) -> tuple[str | None, str | None, dict | None, str | None]:
    """
    Parse ReAct format text.
    
    Returns:
        (thought, tool_name, tool_args, final_answer)
    """
    thought = None
    tool_name = None
    tool_args = None
    final_answer = None
    
    # Extract thought
    thought_match = _THOUGHT_RE.search(text)
    if thought_match:
        thought = thought_match.group(1).strip()
    
    # Extract action (try multiline first, then same-line format)
    action_match = _ACTION_RE.search(text)
    if not action_match:
        action_match = _ACTION_SAME_LINE_RE.search(text)
    
    if action_match:
        tool_name = action_match.group(1).strip()
        raw_args = action_match.group(2).strip()
        
        # Parse arguments
        if raw_args.startswith('{'):
            try:
                tool_args = json.loads(raw_args)
            except json.JSONDecodeError:
                # Try to fix common issues
                tool_args = {"input": raw_args}
        else:
            tool_args = {"input": raw_args}
    
    # Extract final answer
    final_match = _FINAL_RE.search(text)
    if final_match:
        final_answer = final_match.group(1).strip()
    
    return thought, tool_name, tool_args, final_answer


def run_react_mode(
    client: OllamaClient,
    model: str,
    memory: Memory,
    tools: ToolRegistry,
    model_options: dict,
    max_steps: int,
    needs_no_think: bool,
    debug: bool,
    on_step: Callable[[StepResult], None] | None = None,
) -> AgentRun:
    """
    Run agent using text-based ReAct prompting.
    
    Used for models that accept tools but need text-based prompting
    instead of Ollama's native tool calling API.
    
    The model outputs:
        Thought: I need to...
        Action: calculator
        Action Input: {"expression": "8 * 7"}
        Observation: 56
        Final Answer: 56
    
    Args:
        client: OllamaClient instance
        model: Model name
        memory: Conversation memory
        tools: Tool registry
        model_options: Model options
        max_steps: Maximum iterations
        needs_no_think: Whether to disable thinking mode
        debug: Enable debug output
        on_step: Optional callback for step events
    
    Returns:
        AgentRun with steps and final answer
    """
    run = AgentRun()
    t0 = time.perf_counter()
    
    # Loop guards
    tool_call_counts: dict[str, int] = {}
    successful_results: list[str] = []
    max_calls_per_tool = 2
    max_total_tool_calls = 4
    format_reminder_sent = False
    
    for step_num in range(max_steps):
        step_t0 = time.perf_counter()
        
        response = client.chat(
            model=model,
            messages=memory.to_messages(),
            tools=None,  # Don't pass tools in ReAct mode
            options=model_options,
            think=False if needs_no_think else None,
        )
        
        elapsed = (time.perf_counter() - step_t0) * 1000
        msg = response.get("message", {})
        content = msg.get("content", "")
        
        if debug:
            print(f"\n  🔍 DEBUG: ReAct response")
            print(f"    content (FULL): {content!r}")
        
        # Parse ReAct format
        thought, t_name, t_args, final_answer = _parse_react(content)
        
        if debug:
            print(f"    thought={thought!r}")
            print(f"    t_name={t_name!r}")
            print(f"    t_args={t_args!r}")
            print(f"    final_answer={final_answer!r}")
        
        # Handle final answer
        if final_answer:
            run.final_answer = final_answer
            run.steps.append(StepResult(type="final", content=final_answer, elapsed_ms=elapsed))
            if on_step:
                on_step(run.steps[-1])
            memory.add_assistant(content)
            break
        
        # Handle thought
        if thought:
            run.steps.append(StepResult(type="thought", content=thought, elapsed_ms=elapsed))
            if on_step:
                on_step(run.steps[-1])
        
        # Handle tool call
        if t_name and t_args is not None:
            # Check tool limits
            tool_call_counts[t_name] = tool_call_counts.get(t_name, 0) + 1
            total_calls = sum(tool_call_counts.values())
            
            if tool_call_counts[t_name] > max_calls_per_tool or total_calls > max_total_tool_calls:
                # Hit limits - synthesize from what we have
                final = _get_numeric_result(successful_results) or _synthesize_result(successful_results, content)
                run.final_answer = final
                run.steps.append(StepResult(type="final", content=final, elapsed_ms=elapsed))
                if on_step:
                    on_step(run.steps[-1])
                break
            
            # Check if tool exists
            if tools.get(t_name):
                if debug:
                    args_str = ", ".join(f"{k}={v}" for k, v in t_args.items())
                    print(f"    🔧 {t_name}({args_str})")
                
                run.steps.append(StepResult(
                    type="tool_call",
                    content="",
                    tool_name=t_name,
                    tool_args=t_args,
                    elapsed_ms=elapsed,
                ))
                if on_step:
                    on_step(run.steps[-1])
                
                result = tools.invoke(t_name, t_args)
                result_str = str(result)
                
                if debug:
                    preview = result_str[:60] + "..." if len(result_str) > 60 else result_str
                    print(f"    📦 → {preview}")
                
                run.steps.append(StepResult(type="tool_result", content=result_str, tool_name=t_name))
                if on_step:
                    on_step(run.steps[-1])
                
                if not result_str.startswith("[Tool error]"):
                    successful_results.append(f"{t_name} → {result_str}")
                
                # Add observation to memory (as user role for model to respond)
                memory.add_assistant(content)
                memory.add_user(f"Observation: {result_str}\n\nNow provide your Final Answer:")
            else:
                if debug:
                    print(f"    ⚠️ Unknown tool: {t_name}")
                memory.add_assistant(content)
                memory.add_user(f"Tool '{t_name}' not found. Available tools: {[t.name for t in tools.all()]}")
        
        # No tool call and no final answer - might need format reminder
        elif not t_name and not final_answer and not successful_results and not format_reminder_sent:
            format_reminder_sent = True
            if debug:
                print(f"    Sending format reminder...")
            tool_names = [t.name for t in tools.all()]
            memory.add_assistant(content)
            memory.add_user(
                f"Please use the ReAct format:\n"
                f"Action: {tool_names[0]}\n"
                f"Action Input: {{\"expression\": \"<your calculation>\"}}\n"
                f"Final Answer: <result>"
            )
            continue
        
        # No action but we have results - try to get final answer
        elif not t_name and successful_results:
            # Check if content looks incomplete
            content_stripped = content.strip()
            if content_stripped.startswith("Thought:") and "Final Answer:" not in content_stripped:
                # Use numeric result directly
                final = _get_numeric_result(successful_results)
                if final:
                    run.final_answer = final
                    run.steps.append(StepResult(type="final", content=final, elapsed_ms=elapsed))
                    if on_step:
                        on_step(run.steps[-1])
                    break
            
            # Fall back to content
            run.final_answer = content
            run.steps.append(StepResult(type="final", content=content, elapsed_ms=elapsed))
            if on_step:
                on_step(run.steps[-1])
            memory.add_assistant(content)
            break
        
        else:
            # No action, no results - return content
            run.final_answer = content
            run.steps.append(StepResult(type="final", content=content, elapsed_ms=elapsed))
            if on_step:
                on_step(run.steps[-1])
            memory.add_assistant(content)
            break
    
    run.total_ms = (time.perf_counter() - t0) * 1000
    return run


# ============================================================
# HELPER FUNCTIONS
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


def _normalize_args(args: dict, tool: Tool) -> dict:
    """Normalize argument names to match tool's expected parameters."""
    if not tool or not tool.params:
        return args
    
    normalized = {}
    for param in tool.params:
        # Check various aliases
        aliases = [param.name] + (param.aliases or [])
        for alias in aliases:
            if alias in args:
                normalized[param.name] = args[alias]
                break
    
    return normalized if normalized else args


def _is_simple_query(memory: Memory) -> bool:
    """Check if the query is simple enough for immediate synthesis."""
    # Get the first user message
    for msg in memory._history:
        if msg.role == "user":
            text = msg.content.lower()
            # Simple math/date queries
            simple_keywords = ["what is", "calculate", "compute", "sqrt", "date", "time"]
            if any(kw in text for kw in simple_keywords) and len(text) < 60:
                return True
            break
    return False