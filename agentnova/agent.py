"""
⚛️ AgentNova — Agent
Main agent class implementing the ReAct loop.

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

import time
from typing import Any, Generator, Optional

from .core.models import AgentRun, StepResult, Tool, ToolParam, ToolCall
from .core.types import StepResultType, ToolSupportLevel
from .core.memory import Memory, MemoryConfig
from .core.tool_parse import ToolParser
from .core.prompts import get_system_prompt
from .core.model_config import get_model_config
from .tools import ToolRegistry, make_builtin_registry
from .backends import BaseBackend, get_default_backend


class Agent:
    """
    AgentNova Agent - ReAct loop implementation.

    Features:
    - Three-tier tool support (native, ReAct, none)
    - Auto-detects model capabilities
    - Sliding window memory
    - Streaming support
    - Debug mode
    - Soul Spec v0.5 support (disabled by default, enable with soul=)

    Example:
        agent = Agent(model="qwen2.5:0.5b", tools=["calculator", "shell"])
        result = agent.run("What is 15 * 8?")
        print(result.final_answer)
        
        # With Soul Spec (disabled by default)
        agent = Agent(model="qwen2.5:0.5b", soul="/path/to/soul/package")
    """

    def __init__(
        self,
        model: str,
        tools: ToolRegistry | list[str] | list[Tool] | None = None,
        backend: BaseBackend | str | None = None,
        max_steps: int = 10,
        memory_config: MemoryConfig | None = None,
        force_react: bool = False,
        debug: bool = False,
        system_prompt: str | None = None,
        soul: str | None = None,
        soul_level: int = 2,
        num_ctx: int | None = None,
        **kwargs,
    ):
        """
        Initialize an Agent.

        Args:
            model: Model name (e.g., "qwen2.5:0.5b")
            tools: ToolRegistry, list of tool names, or list of Tool objects
            backend: Backend instance or name ("ollama", "bitnet")
            max_steps: Maximum reasoning steps
            memory_config: Memory configuration
            force_react: Force ReAct mode even for native-capable models
            debug: Enable debug output
            system_prompt: Custom system prompt (if None, uses default)
            soul: Path to Soul Spec package (disabled by default)
            soul_level: Progressive disclosure level for soul (1-3)
            num_ctx: Context window size in tokens (Ollama default is 2048)
            **kwargs: Additional configuration
        """
        self.model = model
        self.max_steps = max_steps
        self.debug = debug
        self.force_react = force_react
        self.num_ctx = num_ctx

        # Initialize backend
        if backend is None:
            self.backend = get_default_backend()
        elif isinstance(backend, str):
            self.backend = get_default_backend(backend)
        else:
            self.backend = backend

        # Initialize tools
        if tools is None:
            self.tools = ToolRegistry()
        elif isinstance(tools, ToolRegistry):
            self.tools = tools
        elif isinstance(tools, list):
            if all(isinstance(t, str) for t in tools):
                # List of tool names
                self.tools = make_builtin_registry().subset(tools)
            elif all(isinstance(t, Tool) for t in tools):
                # List of Tool objects
                self.tools = ToolRegistry(tools)
            else:
                raise ValueError("tools must be a list of strings or Tool objects")
        else:
            raise ValueError("tools must be ToolRegistry, list[str], or list[Tool]")

        # Initialize memory
        self.memory = Memory(memory_config or MemoryConfig())

        # Get model configuration
        self.model_config = get_model_config(model)

        # Detect model family
        from .core.model_family_config import detect_family
        self.model_family = detect_family(model)

        # Load Soul Spec package (disabled by default, enable with soul=)
        self.soul = None
        self._soul_level = soul_level
        if soul is not None:
            try:
                from .soul import load_soul, build_system_prompt as build_soul_prompt
                self.soul = load_soul(soul, level=soul_level)
                
                # Filter tools based on soul.allowed_tools
                if self.soul.allowed_tools and len(self.soul.allowed_tools) > 0:
                    allowed = set(self.soul.allowed_tools)
                    current_tools = set(self.tools.names())
                    # Keep only allowed tools that exist
                    filtered = current_tools.intersection(allowed)
                    if filtered != current_tools:
                        if debug:
                            print(f"[Soul] Filtering tools: {current_tools} -> {filtered}")
                        self.tools = self.tools.subset(list(filtered))
                
                # Generate system prompt from soul if not provided
                if system_prompt is None:
                    system_prompt = build_soul_prompt(self.soul, level=soul_level)
                    if debug:
                        print(f"[Soul] Loaded: {self.soul.display_name} v{self.soul.version}")
            except ImportError:
                if debug:
                    print("[Soul] Soul module not available, ignoring soul parameter")
            except FileNotFoundError as e:
                if debug:
                    print(f"[Soul] Soul package not found: {e}")
            except Exception as e:
                if debug:
                    print(f"[Soul] Error loading soul: {e}")

        # Determine tool support level
        if force_react:
            self._tool_support = ToolSupportLevel.REACT
        elif not self.tools or len(self.tools) == 0:
            self._tool_support = ToolSupportLevel.NONE
        else:
            self._tool_support = self._detect_tool_support()

        # Initialize tool parser
        self._parser = ToolParser(self.tools.names())

        # Store custom system prompt (if provided)
        self._custom_system_prompt = system_prompt

        # Add system prompt
        self._add_system_prompt()

        # Store kwargs
        self._kwargs = kwargs

    def _detect_tool_support(self) -> ToolSupportLevel:
        """Detect the tool support level for the model.
        
        Checks cache only. Run `agentnova models --tool_support` to test.
        Untested models default to REACT for reliability.
        """
        # Check cache first
        import json
        from pathlib import Path
        
        cache_dir = Path.home() / ".cache" / "agentnova"
        cache_file = cache_dir / "tool_support.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    cache = json.load(f)
                cached = cache.get(self.model)
                if cached:
                    support = cached.get("support", "react")
                    if support == "native":
                        return ToolSupportLevel.NATIVE
                    elif support == "react":
                        return ToolSupportLevel.REACT
                    elif support == "none":
                        return ToolSupportLevel.NONE
            except (json.JSONDecodeError, IOError):
                pass
        
        # Not cached - default to REACT (don't auto-test)
        # User can run `agentnova models --tool_support` to test and cache
        return ToolSupportLevel.REACT

    def _add_system_prompt(self) -> None:
        """Add the system prompt to memory."""
        if self._custom_system_prompt:
            # Use custom system prompt if provided (e.g., from Soul Spec)
            system_prompt = self._custom_system_prompt
            
            # IMPORTANT: Append tool descriptions and format instructions if tools exist
            # Souls define personality but may not include tool usage instructions
            if self.tools and len(self.tools) > 0 and self._tool_support != ToolSupportLevel.NONE:
                from .core.prompts import get_tool_prompt
                tool_prompt = get_tool_prompt(
                    self.tools.all(),
                    tool_support=self._tool_support.value,
                    family=None
                )
                if tool_prompt:
                    system_prompt = f"{system_prompt}\n\n{tool_prompt}"
        else:
            # Use default generated system prompt
            system_prompt = get_system_prompt(
                model_name=self.model,
                tool_support=self._tool_support.value,
                tools=self.tools.all() if self.tools else None,
            )
        self.memory.add("system", system_prompt)

    def run(self, prompt: str, stream: bool = False) -> AgentRun:
        """
        Run the agent on a prompt.

        Args:
            prompt: User prompt
            stream: Whether to stream output

        Returns:
            AgentRun with final answer and execution details
        """
        start_time = time.time()
        steps = []
        total_tokens = 0
        tool_calls = 0
        successful_results = []
        empty_retry_count = 0
        native_retry_count = 0

        # Add user prompt to memory
        self.memory.add("user", prompt)

        if self.debug:
            print(f"\n[AgentNova] Model: {self.model}")
            print(f"[AgentNova] Backend: {self.backend.base_url}")
            print(f"[AgentNova] Tool support: {self._tool_support.value}")
            print(f"[AgentNova] Tools: {self.tools.names()}")
            print(f"[AgentNova] Prompt: {prompt}\n")

        # ---- Greeting short-circuit ----
        # For simple greetings, skip tool calling and respond directly
        from .core.helpers import is_greeting_or_simple
        if self._tool_support == ToolSupportLevel.NATIVE and is_greeting_or_simple(prompt):
            # Just get a simple response without tools
            try:
                response = self.backend.generate(
                    model=self.model,
                    messages=self.memory.get_messages(),
                    tools=None,  # No tools for greetings
                    temperature=self.model_config.default_temperature,
                    max_tokens=100,
                )
                content = response.get("content", "")
                if content and not self._looks_like_tool_schema(content):
                    if self.debug:
                        print(f"  Greeting detected, responding directly")
                    steps.append(StepResult(
                        type=StepResultType.FINAL_ANSWER,
                        content=content,
                        tokens_used=response.get("usage", {}).get("total_tokens", 0),
                    ))
                    self.memory.add("assistant", content)
                    total_ms = (time.time() - start_time) * 1000
                    return AgentRun(
                        final_answer=content,
                        steps=steps,
                        total_tokens=total_tokens,
                        total_ms=total_ms,
                        tool_calls=0,
                        success=True,
                    )
            except Exception:
                pass  # Fall through to normal processing

        # ReAct loop
        for step_num in range(self.max_steps):
            if self.debug:
                print(f"[Step {step_num + 1}]")

            # Generate response
            try:
                response = self._generate()
            except Exception as e:
                if self.debug:
                    print(f"  ERROR: {e}")
                steps.append(StepResult(
                    type=StepResultType.ERROR,
                    error=str(e),
                ))
                break

            content = response.get("content", "")
            native_tool_calls = response.get("tool_calls", [])
            tokens = response.get("usage", {}).get("total_tokens", 0)
            total_tokens += tokens

            if self.debug:
                print(f"  Content: {content[:200] if content else '(empty)'}...")
                print(f"  Native tool calls: {native_tool_calls}")

            # ---- Native tool calling ----
            if self._tool_support == ToolSupportLevel.NATIVE and native_tool_calls:
                native_retry_count = 0  # Reset retry counter on success
                
                # Add assistant message with all tool calls (do this ONCE, not per tool)
                self.memory.add_tool_call("assistant", content, native_tool_calls)
                
                for tc in native_tool_calls:
                    tool_name = tc.get("name", "")
                    tool_args = tc.get("arguments", {})
                    tool_call_id = tc.get("id", "")  # Get the actual ID from Ollama

                    # Fuzzy match tool name
                    tool_name = self._parser._fuzzy_match_tool(tool_name)

                    result = self._execute_tool(tool_name, tool_args, prompt)
                    tool_calls += 1

                    # Add tool result with correct ID
                    self.memory.add_tool_result(
                        tool_call_id=tool_call_id,
                        name=tool_name,
                        content=str(result),
                    )

                    if not str(result).startswith("Error"):
                        successful_results.append(f"{tool_name}: {result}")

                    steps.append(StepResult(
                        type=StepResultType.TOOL_CALL,
                        content=content,
                        tool_call=ToolCall(name=tool_name, arguments=tool_args),
                        tool_result=result,
                        tokens_used=tokens,
                    ))

                    if self.debug:
                        print(f"  Tool: {tool_name}({tool_args})")
                        print(f"  Result: {str(result)[:200]}...")

                # Continue to next step after processing all tool calls
                continue

            # ---- Native tool fallback: empty response retry ----
            if self._tool_support == ToolSupportLevel.NATIVE and not native_tool_calls and not content and self.tools.names():
                if empty_retry_count < 2:
                    empty_retry_count += 1
                    if self.debug:
                        print(f"  Empty native response, retrying with hint ({empty_retry_count}/2)")

                    # Add direct tool hint
                    tool_hint = self._get_tool_hint(prompt)
                    self.memory.add("assistant", "")
                    self.memory.add("user", f"{tool_hint}\n\nOriginal question: {prompt}")
                    continue

            # ---- Native tool fallback: parse text for tool calls ----
            if self._tool_support == ToolSupportLevel.NATIVE and not native_tool_calls and content and self.tools.names():
                parsed_from_text = self._parser.parse(content)
                if parsed_from_text:
                    if self.debug:
                        print(f"  Parsed tool call from text: {parsed_from_text[0].name}")
                    
                    call = parsed_from_text[0]
                    tool_name = call.name
                    tool_args = call.arguments

                    result = self._execute_tool(tool_name, tool_args, prompt)
                    tool_calls += 1

                    self.memory.add("assistant", content)
                    self.memory.add("user", f"Observation: {result}")

                    if not str(result).startswith("Error"):
                        successful_results.append(f"{tool_name}: {result}")

                    steps.append(StepResult(
                        type=StepResultType.TOOL_CALL,
                        content=content,
                        tool_call=call,
                        tool_result=result,
                        tokens_used=tokens,
                    ))

                    if self.debug:
                        print(f"  Tool: {tool_name}({tool_args})")
                        print(f"  Result: {str(result)[:200]}...")

                    # For small models: if result is a simple numeric answer, accept it
                    result_str = str(result).strip()
                    if result_str and not result_str.startswith("Error"):
                        # Check if result is a simple number or short answer
                        try:
                            float(result_str)  # Is it a number?
                            # It's a number - accept as final answer for simple queries
                            if self.debug:
                                print(f"  Accepting tool result as final answer: {result_str}")
                            steps.append(StepResult(
                                type=StepResultType.FINAL_ANSWER,
                                content=result_str,
                                tokens_used=tokens,
                            ))
                            break
                        except (ValueError, TypeError):
                            pass  # Not a simple number, continue

                    continue

            # ---- Native tool fallback: text response after tool success ----
            if self._tool_support == ToolSupportLevel.NATIVE and not native_tool_calls and content and successful_results:
                # For small models: trust tool result over model's interpretation
                # Check if we have a simple numeric result from the last tool call
                last_result = successful_results[-1] if successful_results else ""
                if "→" in last_result:
                    last_result = last_result.split("→")[-1].strip()
                elif ":" in last_result:
                    last_result = last_result.split(":")[-1].strip()
                
                # If tool result is a simple number, use it as final answer
                try:
                    tool_result_num = float(last_result)
                    # Tool returned a number - use it directly for simple queries
                    from .core.helpers import is_simple_answered_query
                    if is_simple_answered_query(prompt, successful_results):
                        if self.debug:
                            print(f"  Native mode: using tool result {tool_result_num} as final answer (overriding model text)")
                        steps.append(StepResult(
                            type=StepResultType.FINAL_ANSWER,
                            content=str(tool_result_num),
                            tokens_used=tokens,
                        ))
                        self.memory.add("assistant", str(tool_result_num))
                        break
                except (ValueError, TypeError):
                    pass
                
                if self.debug:
                    print(f"  Native mode: text response after tool success -> final answer")
                steps.append(StepResult(
                    type=StepResultType.FINAL_ANSWER,
                    content=content,
                    tokens_used=tokens,
                ))
                self.memory.add("assistant", content)
                break

            # ---- Native tool fallback: try direct tool hint ----
            if self._tool_support == ToolSupportLevel.NATIVE and not native_tool_calls and content and self.tools.names() and not successful_results:
                if native_retry_count < 1:
                    native_retry_count += 1
                    if self.debug:
                        print(f"  Native mode: no tool calls, trying direct hint")

                    # Check if content looks like it's trying to answer
                    looks_like_answer = any(kw in content.lower() for kw in 
                        ["answer is", "result is", "therefore", "the answer", "equals"])
                    
                    if not looks_like_answer:
                        # Synthesize a tool call based on the prompt
                        from .core.helpers import extract_calc_expression, is_small_model
                        
                        if "calculator" in self.tools.names():
                            expr = extract_calc_expression(prompt)
                            if expr:
                                if self.debug:
                                    print(f"  Auto-synthesizing calculator call: {expr}")
                                result = self._execute_tool("calculator", {"expression": expr}, prompt)
                                tool_calls += 1
                                
                                self.memory.add("assistant", content)
                                self.memory.add("user", f"Observation: {result}")
                                
                                if not str(result).startswith("Error"):
                                    successful_results.append(f"calculator: {result}")
                                
                                steps.append(StepResult(
                                    type=StepResultType.TOOL_CALL,
                                    content=f"[Auto-synthesized] calculator({expr})",
                                    tool_result=result,
                                    tokens_used=tokens,
                                ))
                                
                                result_str = str(result).strip()
                                if result_str:
                                    try:
                                        float(result_str)
                                        if self.debug:
                                            print(f"  Accepting synthesized result as final answer: {result_str}")
                                        steps.append(StepResult(
                                            type=StepResultType.FINAL_ANSWER,
                                            content=result_str,
                                            tokens_used=tokens,
                                        ))
                                        break
                                    except (ValueError, TypeError):
                                        pass
                                continue
                        
                        tool_hint = self._get_tool_hint(prompt)
                        self.memory.add("assistant", content)
                        self.memory.add("user", f"You must use the tool to answer this.\n{tool_hint}")
                        continue

            # ---- ReAct tool calling ----
            if self._tool_support == ToolSupportLevel.REACT:
                parsed_calls = self._parser.parse(content)

                if parsed_calls:
                    call = parsed_calls[0]
                    tool_name = call.name
                    tool_args = call.arguments

                    result = self._execute_tool(tool_name, tool_args, prompt)
                    tool_calls += 1

                    self.memory.add("assistant", content)
                    self.memory.add("user", f"Observation: {result}")

                    if not str(result).startswith("Error"):
                        successful_results.append(f"{tool_name}: {result}")

                    steps.append(StepResult(
                        type=StepResultType.TOOL_CALL,
                        content=content,
                        tool_call=call,
                        tool_result=result,
                        tokens_used=tokens,
                    ))

                    if self.debug:
                        print(f"  Tool: {tool_name}({tool_args})")
                        print(f"  Result: {str(result)[:200]}...")

                    # For small models: if result is a simple numeric answer, accept it as final
                    result_str = str(result).strip()
                    if result_str and not result_str.startswith("Error"):
                        try:
                            float(result_str)  # Is it a number?
                            # It's a number - accept as final answer for simple queries
                            from .core.helpers import is_simple_answered_query
                            if is_simple_answered_query(prompt, successful_results):
                                if self.debug:
                                    print(f"  Accepting tool result as final answer: {result_str}")
                                steps.append(StepResult(
                                    type=StepResultType.FINAL_ANSWER,
                                    content=result_str,
                                    tokens_used=tokens,
                                ))
                                self.memory.add("assistant", f"Final Answer: {result_str}")
                                break
                        except (ValueError, TypeError):
                            pass  # Not a simple number, continue loop

                    continue

            # Check for final answer
            # IMPORTANT: For ReAct models without successful tool calls, prioritize fallback synthesis
            # over accepting "Final Answer" - small models often give wrong answers without tools
            if self._parser.is_final_answer(content):
                # For ReAct models without results, try fallback synthesis first
                if self._tool_support == ToolSupportLevel.REACT and not successful_results:
                    if self.debug:
                        print(f"  ReAct model gave Final Answer without tool use, trying fallback synthesis first")
                    
                    from .core.helpers import extract_calc_expression
                    expr = extract_calc_expression(prompt)
                    
                    if expr and "calculator" in self.tools.names():
                        if self.debug:
                            print(f"  Auto-synthesizing calculator call: {expr}")
                        
                        result = self._execute_tool("calculator", {"expression": expr}, prompt)
                        tool_calls += 1
                        
                        self.memory.add("assistant", content)
                        self.memory.add("user", f"Observation: {result}")
                        
                        if not str(result).startswith("Error"):
                            successful_results.append(f"calculator: {result}")
                        
                        steps.append(StepResult(
                            type=StepResultType.TOOL_CALL,
                            content=f"[Auto-synthesized] calculator({expr})",
                            tool_result=result,
                            tokens_used=tokens,
                        ))
                        
                        # For simple numeric results, accept as final answer
                        result_str = str(result).strip()
                        if result_str and not result_str.startswith("Error"):
                            try:
                                float(result_str)
                                if self.debug:
                                    print(f"  Accepting synthesized result as final answer: {result_str}")
                                steps.append(StepResult(
                                    type=StepResultType.FINAL_ANSWER,
                                    content=result_str,
                                    tokens_used=tokens,
                                ))
                                break
                            except (ValueError, TypeError):
                                pass
                        continue
                
                # Accept final answer for native models or ReAct models with successful results
                answer = self._parser.extract_final_answer(content)

                steps.append(StepResult(
                    type=StepResultType.FINAL_ANSWER,
                    content=answer,
                    tokens_used=tokens,
                ))

                if self.debug:
                    print(f"  Final answer: {answer}")

                break

            # ---- Soul mode: accept conversational responses ----
            # If a soul is loaded (chat mode with personality), accept the model's response
            # as a final answer even if it doesn't follow ReAct format
            if self.soul is not None and content and not native_tool_calls:
                if self.debug:
                    print(f"  Soul mode: accepting conversational response as final answer")
                
                steps.append(StepResult(
                    type=StepResultType.FINAL_ANSWER,
                    content=content,
                    tokens_used=tokens,
                ))
                break

            # ---- ReAct format reminder for small models ----
            # If model didn't use ReAct format and we haven't succeeded yet, send a reminder
            # BUT skip this if a soul is loaded - chat mode should allow natural conversation
            if self._tool_support == ToolSupportLevel.REACT and not successful_results and self.soul is None:
                if not hasattr(self, '_format_reminder_sent'):
                    self._format_reminder_sent = True
                    if self.debug:
                        print(f"  Model didn't use ReAct format, sending reminder")
                    
                    self.memory.add("assistant", content)
                    tool_names = self.tools.names()
                    first_tool = self.tools.all()[0] if self.tools.all() else None
                    arg_hint = "input"
                    if first_tool and hasattr(first_tool, 'params') and first_tool.params:
                        arg_hint = first_tool.params[0].name
                    
                    # Try to extract expression from prompt for better example
                    from .core.helpers import extract_calc_expression
                    expr_example = extract_calc_expression(prompt) or "8 * 7 - 5"
                    
                    reminder = (
                        f"Answer this question: {prompt}\n\n"
                        f"Use this EXACT format:\n"
                        f"Action: {tool_names[0]}\n"
                        f"Action Input: {{\"{arg_hint}\": \"{expr_example}\"}}"
                    )
                    self.memory.add("user", reminder)
                    continue

            # ---- ReAct fallback: synthesize tool call after reminder failed ----
            # If reminder was sent but model still didn't output tool call, try to synthesize one
            # BUT skip this if a soul is loaded - chat mode should allow natural conversation
            if self._tool_support == ToolSupportLevel.REACT and not successful_results and hasattr(self, '_format_reminder_sent') and self.soul is None:
                if self.debug:
                    print(f"  ReAct fallback: attempting to synthesize tool call")
                
                from .core.helpers import extract_calc_expression
                expr = extract_calc_expression(prompt)
                
                if expr and "calculator" in self.tools.names():
                    if self.debug:
                        print(f"  Auto-synthesizing calculator call: {expr}")
                    
                    result = self._execute_tool("calculator", {"expression": expr}, prompt)
                    tool_calls += 1
                    
                    self.memory.add("assistant", content)
                    self.memory.add("user", f"Observation: {result}")
                    
                    if not str(result).startswith("Error"):
                        successful_results.append(f"calculator: {result}")
                    
                    steps.append(StepResult(
                        type=StepResultType.TOOL_CALL,
                        content=f"[Auto-synthesized] calculator({expr})",
                        tool_result=result,
                        tokens_used=tokens,
                    ))
                    
                    # For simple numeric results, accept as final answer
                    result_str = str(result).strip()
                    if result_str and not result_str.startswith("Error"):
                        try:
                            float(result_str)
                            if self.debug:
                                print(f"  Accepting synthesized result as final answer: {result_str}")
                            steps.append(StepResult(
                                type=StepResultType.FINAL_ANSWER,
                                content=result_str,
                                tokens_used=tokens,
                            ))
                            break
                        except (ValueError, TypeError):
                            pass
                    continue

            # ---- Native tool fallback: synthesize after empty retries exhausted ----
            # If we've exhausted retries and still no tool call, synthesize one
            if self._tool_support == ToolSupportLevel.NATIVE and not native_tool_calls and not successful_results and self.tools.names():
                if self.debug:
                    print(f"  Native fallback: synthesizing tool call after empty retries")
                
                from .core.helpers import extract_calc_expression
                expr = extract_calc_expression(prompt)
                
                if expr and "calculator" in self.tools.names():
                    if self.debug:
                        print(f"  Auto-synthesizing calculator call: {expr}")
                    
                    result = self._execute_tool("calculator", {"expression": expr}, prompt)
                    tool_calls += 1
                    
                    self.memory.add("assistant", content or "")
                    self.memory.add("user", f"Observation: {result}")
                    
                    if not str(result).startswith("Error"):
                        successful_results.append(f"calculator: {result}")
                    
                    steps.append(StepResult(
                        type=StepResultType.TOOL_CALL,
                        content=f"[Auto-synthesized] calculator({expr})",
                        tool_result=result,
                        tokens_used=tokens,
                    ))
                    
                    # For simple numeric results, accept as final answer
                    result_str = str(result).strip()
                    if result_str and not result_str.startswith("Error"):
                        try:
                            float(result_str)
                            if self.debug:
                                print(f"  Accepting synthesized result as final answer: {result_str}")
                            steps.append(StepResult(
                                type=StepResultType.FINAL_ANSWER,
                                content=result_str,
                                tokens_used=tokens,
                            ))
                            break
                        except (ValueError, TypeError):
                            pass
                    continue

            # No tool call or final answer - treat as response
            if self.debug:
                print(f"  No tool calls detected, treating as final answer")
            steps.append(StepResult(
                type=StepResultType.FINAL_ANSWER,
                content=content,
                tokens_used=tokens,
            ))
            self.memory.add("assistant", content)
            break

        else:
            # Max steps reached
            steps.append(StepResult(
                type=StepResultType.MAX_STEPS,
                content="Maximum steps reached without final answer",
            ))

        total_ms = (time.time() - start_time) * 1000

        # Get final answer
        final_answer = ""
        for step in reversed(steps):
            if step.type == StepResultType.FINAL_ANSWER:
                final_answer = step.content or ""
                break

        return AgentRun(
            final_answer=final_answer,
            steps=steps,
            total_tokens=total_tokens,
            total_ms=total_ms,
            tool_calls=tool_calls,
            success=bool(final_answer),
        )

    def _get_tool_hint(self, prompt: str) -> str:
        """Generate a tool hint for the prompt."""
        available_tools = self.tools.names()
        prompt_lower = prompt.lower()
        
        if "calculator" in available_tools and any(kw in prompt_lower for kw in 
            ["times", "multiply", "plus", "minus", "divided", "calculate", "what is",
             "how many", "hours", "apples", "left", " * ", " + ", " - ", " / "]):
            # Try to extract math expression
            import re
            # Look for numbers and operators
            numbers = re.findall(r'\d+', prompt)
            if numbers:
                return "Use the calculator tool with the appropriate mathematical expression."
            return "Use the calculator tool to solve this math problem."
        
        if "shell" in available_tools and any(kw in prompt_lower for kw in 
            ["echo", "print", "directory", "pwd", "folder"]):
            return "Use the shell tool to execute the appropriate command."
        
        if "python_repl" in available_tools and any(kw in prompt_lower for kw in 
            ["python", "code", "execute", "run"]):
            return "Use the python_repl tool to execute Python code."
        
        if available_tools:
            return f"Use the {available_tools[0]} tool to answer this question."
        
        return ""

    def _generate(self) -> dict:
        """Generate a response from the backend."""
        messages = self.memory.get_messages()

        if self.debug:
            print(f"  [DEBUG] Sending {len(messages)} messages")
            for i, msg in enumerate(messages):
                role = msg.get('role', '?')
                content = msg.get('content', '')
                tc = msg.get('tool_calls', [])
                content_preview = content[:2048] if content else '(empty)'
                print(f"  [MSG {i}] role={role}, content={content_preview!r}{' [has tool_calls]' if tc else ''}")
            print(f"  [DEBUG] Tools: {[t.name for t in self.tools.all()] if self.tools else None}")

        # Check if model needs thinking disabled (qwen3, deepseek-r1, etc.)
        think = None
        if self.model_family:
            from .core.model_family_config import needs_no_think_directive
            if needs_no_think_directive(self.model_family):
                think = False

        # Build kwargs for backend
        backend_kwargs = {"think": think}
        if self.num_ctx is not None:
            backend_kwargs["num_ctx"] = self.num_ctx
            if self.debug:
                print(f"  [DEBUG] num_ctx: {self.num_ctx}")

        response = self.backend.generate(
            model=self.model,
            messages=messages,
            tools=self.tools.all() if self._tool_support == ToolSupportLevel.NATIVE else None,
            temperature=self.model_config.default_temperature,
            max_tokens=self.model_config.default_max_tokens,
            **backend_kwargs,
        )

        if self.debug:
            print(f"  [DEBUG] Response keys: {list(response.keys())}")
            print(f"  [DEBUG] Content: {response.get('content', '')[:100]}...")
            print(f"  [DEBUG] Tool calls: {response.get('tool_calls', [])}")

        return response

    def _execute_tool(self, name: str, args: dict, user_prompt: str = "") -> Any:
        """Execute a tool by name with arguments."""
        # First try fuzzy matching from tool_parse
        from .core.tool_parse import _fuzzy_match_tool_name
        matched_name = _fuzzy_match_tool_name(name, self.tools.names())
        if matched_name:
            name = matched_name
        
        # Get tool (with fuzzy matching)
        tool = self.tools.get_fuzzy(name)

        if tool is None:
            return f"Error: Unknown tool '{name}'. Available tools: {self.tools.names()}"

        # Normalize arguments with tool-specific aliases
        expected_params = [p.name for p in tool.params]
        
        from .core.helpers import normalize_args, synthesize_tool_args
        normalized_args = normalize_args(args, expected_params, tool_name=name)
        
        # Synthesize missing/incomplete arguments for small models
        synthesized_args = synthesize_tool_args(name, normalized_args, user_prompt)
        if synthesized_args.get("expression") != normalized_args.get("expression") and self.debug:
            print(f"  [SYNTHESIZED] Expression: {synthesized_args.get('expression')}")
        normalized_args = synthesized_args

        try:
            return tool.execute(**normalized_args)

        except TypeError as e:
            # Missing required argument
            return f"Error: {e}"

        except Exception as e:
            return f"Error executing tool: {e}"

    def chat(self, message: str) -> str:
        """
        Send a message in chat mode (maintains conversation).

        Args:
            message: User message

        Returns:
            Agent response
        """
        result = self.run(message)
        return result.final_answer

    def clear_memory(self) -> None:
        """Clear conversation memory."""
        self.memory.clear()
        self._add_system_prompt()

    def add_tool(self, tool: Tool) -> None:
        """Add a tool to the registry."""
        self.tools.register_tool(tool)
        self._parser = ToolParser(self.tools.names())

    def __repr__(self) -> str:
        return f"Agent(model={self.model}, tools={len(self.tools)}, support={self._tool_support.value})"
    
    def _looks_like_tool_schema(self, text: str) -> bool:
        """Check if text looks like a tool schema dump instead of actual content."""
        if not text:
            return False
        
        text_lower = text.lower()
        schema_indicators = [
            '"type":', '"properties":', '"required":',
            '"function"', '"parameters"', '"description"',
            '"json_schema"', '```json', '```python',
        ]
        
        # If multiple schema indicators are present, likely a schema dump
        count = sum(1 for ind in schema_indicators if ind in text_lower)
        return count >= 3
    
    def _synthesize(self, user_input: str, successful_results: list[str]) -> str:
        """
        Synthesize a final answer from successful tool results.
        Called when we have enough results but the model hasn't given a final answer.
        """
        if not successful_results:
            return "I was unable to complete the task."
        
        # For single result, use it directly
        if len(successful_results) == 1:
            result = successful_results[0]
            # Strip tool prefix if present
            if "→" in result:
                result = result.split("→")[-1].strip()
            return result
        
        # For multiple results, summarize
        from .core.helpers import strip_tool_prefix
        results_str = "\n".join(f"- {strip_tool_prefix(r)}" for r in successful_results)
        
        # Simple synthesis
        return f"Based on the results:\n{results_str}"