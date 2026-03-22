"""
AgentNova R02.4 — Refactored Agent

A cleaner implementation with the Agent class that delegates helper functions
to agent_modes.py for better separation of concerns.
"""

from __future__ import annotations

import json
import time
from typing import Callable

from .ollama_client import OllamaClient
from .memory import Memory
from .tools import ToolRegistry
from .model_family_config import get_family_config, get_no_tools_system_prompt
from .agent_modes import (
    StepResult, AgentRun,
    _parse_react, _parse_json_tool_call, _extract_python_code,
    _detect_and_fix_repetition,
    _strip_tool_prefix, _get_numeric_result, _synthesize_result,
    _normalize_args, _synthesize_missing_args, _fuzzy_match_tool_name,
    _is_simple_query,
)


# ============================================================
# AGENT CLASS
# ============================================================

class Agent:
    """
    A single autonomous agent backed by a local Ollama model.
    
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
        self.client = client or OllamaClient()
        self.model_options = model_options or {}
        self.debug = debug
        self.on_step = on_step
        
        # Get model family from Ollama API
        self._model_family = self.client.get_model_family(model) or "unknown"
        self._model_family_config = get_family_config(self._model_family)
        self._needs_no_think = getattr(self._model_family_config, 'needs_think_directive', False)
        
        # Determine tool support level
        if force_react:
            self._tool_support = "react"
        else:
            from ..cli import get_tool_support
            self._tool_support = get_tool_support(model, self.client)
        
        self._native_tools = (self._tool_support == "native")
        self._no_tools = (self._tool_support == "none")
        
        # Set up memory with appropriate system prompt
        if self._no_tools:
            family_no_tools_prompt = get_no_tools_system_prompt(self._model_family)
            system_prompt = family_no_tools_prompt or system_prompt
        
        self.memory = Memory(system_prompt=system_prompt, max_turns=memory_max_turns)
        
        if debug:
            print(f"Agent initialized: model={model}, tool_support={self._tool_support}")
    
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
        content = _detect_and_fix_repetition(content)
        
        if self.debug:
            print(f"\n  DEBUG: Pure reasoning mode")
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
                print(f"\n  DEBUG: Native tools response")
                print(f"    tool_calls={len(tool_calls_raw)}")
                print(f"    content[:100]={content[:100]!r}")
            
            # No tool calls - check if done
            if not tool_calls_raw:
                numeric = _get_numeric_result(successful_results)
                if numeric:
                    run.final_answer = numeric
                else:
                    run.final_answer = content
                
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
                
                # Normalize args
                tool = self.tools.get(t_name)
                if tool:
                    t_args = _normalize_args(t_args, tool, t_name)
                    t_args = _synthesize_missing_args(t_name, t_args, user_input, successful_results, self.tools)
                
                # Check limits
                tool_call_counts[t_name] = tool_call_counts.get(t_name, 0) + 1
                if tool_call_counts[t_name] > max_calls_per_tool:
                    if self.debug:
                        print(f"    Max calls reached for {t_name}")
                    continue
                
                total_calls = sum(tool_call_counts.values())
                if total_calls > max_total_tool_calls:
                    run.final_answer = _get_numeric_result(successful_results) or content
                    run.steps.append(StepResult(type="final", content=run.final_answer, elapsed_ms=elapsed))
                    if self.on_step:
                        self.on_step(run.steps[-1])
                    break
                
                # Execute tool
                if self.tools.get(t_name):
                    if self.debug:
                        args_str = ", ".join(f"{k}={v}" for k, v in t_args.items())
                        print(f"     {t_name}({args_str})")
                    
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
                        print(f"     -> {preview}")
                    
                    run.steps.append(StepResult(type="tool_result", content=result, tool_name=t_name))
                    if self.on_step:
                        self.on_step(run.steps[-1])
                    
                    if not result.startswith("[Tool error]"):
                        successful_results.append(f"{t_name}  {result}")
                    
                    # Add observation to memory
                    self.memory.add_assistant(content)
                    self.memory.add_user(f"Observation: {result}")
            
            # Check if we should synthesize after tool execution
            if successful_results and _is_simple_query(user_input):
                numeric = _get_numeric_result(successful_results)
                if numeric:
                    run.final_answer = numeric
                    run.steps.append(StepResult(type="final", content=numeric, elapsed_ms=elapsed))
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
            
            # Fix repetition issues
            content = _detect_and_fix_repetition(content)
            
            if self.debug:
                print(f"\n  DEBUG: ReAct response")
                print(f"    content[:200]={content[:200]!r}")
            
            # Parse ReAct format
            thought, t_name, t_args, final_answer = _parse_react(content)
            
            if self.debug:
                print(f"    thought={thought!r}")
                print(f"    t_name={t_name!r}")
                print(f"    final_answer={final_answer!r}")
            
            # =============================================
            # CRITICAL: Check for tool call BEFORE final_answer
            # Models may hallucinate Observation and Final Answer in the same response
            # We must execute the actual tool call, not trust the hallucinated answer
            # =============================================
            
            # Handle thought
            if thought:
                run.steps.append(StepResult(type="thought", content=thought, elapsed_ms=elapsed))
                if self.on_step:
                    self.on_step(run.steps[-1])
            
            # Handle tool call - PRIORITIZE OVER FINAL ANSWER
            if t_name and t_args is not None:
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
                        t_name = fuzzy_name
                    else:
                        if self.debug:
                            print(f"    Unknown tool: {original_t_name}")
                        self.memory.add_assistant(content)
                        self.memory.add_user(f"Tool '{original_t_name}' not found. Available: {[t.name for t in self.tools.all()]}")
                        continue
                
                # Normalize and synthesize args
                tool = self.tools.get(t_name)
                if tool:
                    t_args = _normalize_args(t_args, tool, t_name)
                    t_args = _synthesize_missing_args(t_name, t_args, user_input, successful_results, self.tools)
                
                # Execute tool
                if self.tools.get(t_name):
                    if self.debug:
                        args_str = ", ".join(f"{k}={v}" for k, v in t_args.items())
                        print(f"     {t_name}({args_str})")
                    
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
                        print(f"     -> {preview}")
                    
                    run.steps.append(StepResult(type="tool_result", content=result, tool_name=t_name))
                    if self.on_step:
                        self.on_step(run.steps[-1])
                    
                    if not result.startswith(("[Tool error]", "[Calculator error]")):
                        successful_results.append(f"{t_name}  {result}")
                    
                    # Add observation (as user for model to respond)
                    self.memory.add_assistant(content)
                    self.memory.add_user(f"Observation: {result}\n\nNow provide your Final Answer:")
                    continue
            
            # No tool call but we have final_answer - accept it
            elif not t_name and final_answer:
                run.final_answer = final_answer
                run.steps.append(StepResult(type="final", content=final_answer, elapsed_ms=elapsed))
                if self.on_step:
                    self.on_step(run.steps[-1])
                self.memory.add_assistant(content)
                break
            
            # Try JSON tool call fallback (for models that don't use ReAct format)
            elif not t_name and not final_answer:
                json_name, json_args = _parse_json_tool_call(content, debug=self.debug)
                if json_name:
                    if self.debug:
                        print(f"    JSON fallback: {json_name}({json_args})")
                    # Check if tool exists
                    if not self.tools.get(json_name):
                        json_name = _fuzzy_match_tool_name(json_name, self.tools) or json_name
                    
                    if self.tools.get(json_name):
                        tool = self.tools.get(json_name)
                        json_args = _normalize_args(json_args, tool, json_name)
                        json_args = _synthesize_missing_args(json_name, json_args, user_input, successful_results, self.tools)
                        
                        # Execute tool
                        result = str(self.tools.invoke(json_name, json_args))
                        if self.debug:
                            print(f"     -> {result[:60]}")
                        
                        run.steps.append(StepResult(type="tool_call", tool_name=json_name, tool_args=json_args, elapsed_ms=elapsed))
                        run.steps.append(StepResult(type="tool_result", content=result, tool_name=json_name))
                        
                        if not result.startswith("[Tool error]"):
                            successful_results.append(f"{json_name}  {result}")
                        
                        self.memory.add_assistant(content)
                        self.memory.add_user(f"Observation: {result}\n\nNow provide your Final Answer:")
                        continue
                
                # Try Python code extraction (for code-focused models)
                python_code = _extract_python_code(content)
                if python_code and self.tools.get("python_repl"):
                    if self.debug:
                        print(f"    Python code detected, using python_repl")
                    result = str(self.tools.invoke("python_repl", {"code": python_code}))
                    run.steps.append(StepResult(type="tool_call", tool_name="python_repl", tool_args={"code": python_code}, elapsed_ms=elapsed))
                    run.steps.append(StepResult(type="tool_result", content=result, tool_name="python_repl"))
                    
                    if not result.startswith("[Tool error]"):
                        successful_results.append(f"python_repl  {result}")
                    
                    self.memory.add_assistant(content)
                    self.memory.add_user(f"Observation: {result}\n\nNow provide your Final Answer:")
                    continue
            
            # No action, no final - check if we have results
            if not t_name and successful_results:
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
                    f"Answer this question: {user_input}\n\n"
                    f"Use ReAct format:\n"
                    f"Action: {tool_names[0]}\n"
                    f"Action Input: {{\"expression\": \"<your calculation>\"}}"
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