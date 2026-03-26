"""
⚛️ AgentNova — Agent
Main agent class implementing the ReAct loop with OpenResponses specification.

Implements OpenResponses patterns:
- Items: Atomic units of context (message, function_call, reasoning)
- State Machines: Items have states (in_progress, completed, failed)
- tool_choice: Control tool invocation behavior
- allowed_tools: Restrict which tools can be invoked

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
from .core.openresponses import (
    Response, ResponseStatus, ItemStatus,
    ToolChoice, ToolChoiceType,
    MessageItem, FunctionCallItem, FunctionCallOutputItem,
    OutputText, InputText,
    RequestConfig, Error,
    create_message_item, create_function_call_item, create_function_call_output,
    create_function_call_output_item,
)
from .tools import ToolRegistry, make_builtin_registry
from .backends import BaseBackend, get_default_backend


# Alias for cleaner code (ToolSupportLevel enum)
ToolSupport = ToolSupportLevel


class Agent:
    """
    AgentNova Agent - ReAct loop implementation with OpenResponses compliance.
    
    OpenResponses Features:
    - tool_choice: Control tool invocation (auto, required, none, specific tool)
    - allowed_tools: Restrict which tools can be invoked
    - Response state machine: queued → in_progress → completed/failed
    - Items: Atomic units of context with lifecycle states
    
    Legacy Features (maintained for compatibility):
    - Three-tier tool support (native, ReAct, none)
    - Auto-detects model capabilities
    - Sliding window memory
    - Streaming support
    - Debug mode
    - Soul Spec v0.5 support

    Example:
        agent = Agent(model="qwen2.5:0.5b", tools=["calculator", "shell"])
        result = agent.run("What is 15 * 8?")
        print(result.final_answer)
        
        # With tool_choice
        agent = Agent(model="llama3", tools=["calculator"], tool_choice="required")
        
        # With allowed_tools
        agent = Agent(model="llama3", tools=["calculator", "shell"], allowed_tools=["calculator"])
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
        # OpenResponses parameters
        tool_choice: str | ToolChoice = "auto",
        allowed_tools: list[str] | None = None,
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
            tool_choice: Control tool invocation ("auto", "required", "none", or specific tool name)
            allowed_tools: List of tools the model is allowed to invoke (subset of tools)
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

        # OpenResponses: tool_choice
        if isinstance(tool_choice, ToolChoice):
            self.tool_choice = tool_choice
        else:
            self.tool_choice = ToolChoice(tool_choice)

        # OpenResponses: allowed_tools
        # Filter the tools registry to only include allowed tools
        self._allowed_tools = allowed_tools
        if allowed_tools is not None and len(allowed_tools) > 0:
            allowed_set = set(allowed_tools)
            current_tools = set(self.tools.names())
            filtered = current_tools.intersection(allowed_set)
            if filtered != current_tools:
                if debug:
                    print(f"[OpenResponses] Filtering tools via allowed_tools: {current_tools} -> {filtered}")
                self.tools = self.tools.subset(list(filtered))

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
                
                # Filter tools based on soul.allowed_tools (additional filtering)
                if self.soul.allowed_tools and len(self.soul.allowed_tools) > 0:
                    allowed = set(self.soul.allowed_tools)
                    current_tools = set(self.tools.names())
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
        # OpenResponses: tool_choice="none" overrides tool support
        if self.tool_choice.type == ToolChoiceType.NONE:
            self._tool_support = ToolSupport.NONE
            self._tool_support_source = "tool_choice_none"
        elif force_react:
            self._tool_support = ToolSupport.REACT
            self._tool_support_source = "force_react"
        elif not self.tools or len(self.tools) == 0:
            self._tool_support = ToolSupport.NONE
            self._tool_support_source = "no_tools"
        else:
            self._tool_support = self._detect_tool_support()
            if not hasattr(self, '_tool_support_source'):
                self._tool_support_source = "detected"

        # Initialize tool parser
        self._parser = ToolParser(self.tools.names())

        # Store custom system prompt (if provided)
        self._custom_system_prompt = system_prompt

        # Add system prompt
        self._add_system_prompt()

        # Store kwargs
        self._kwargs = kwargs

        # Response history for previous_response_id support
        self._response_history: dict[str, Response] = {}

    def _detect_tool_support(self) -> ToolSupportLevel:
        """Detect the tool support level for the model.
        
        Checks cache only. Run `agentnova models --tool_support` to test.
        Untested models default to REACT for reliability.
        """
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
                    self._tool_support_source = f"cache({support})"
                    if support == "native":
                        return ToolSupport.NATIVE
                    elif support == "react":
                        return ToolSupport.REACT
                    elif support == "none":
                        return ToolSupport.NONE
            except (json.JSONDecodeError, IOError):
                pass
        
        self._tool_support_source = "default(react)"
        return ToolSupport.REACT

    def _add_system_prompt(self) -> None:
        """Add the system prompt to memory."""
        if self._custom_system_prompt:
            system_prompt = self._custom_system_prompt
            
            if self.tools and len(self.tools) > 0 and self._tool_support != ToolSupport.NONE:
                from .core.prompts import get_tool_prompt
                tool_prompt = get_tool_prompt(
                    self.tools.all(),
                    tool_support=self._tool_support.value,
                    family=None
                )
                if tool_prompt:
                    system_prompt = f"{system_prompt}\n\n{tool_prompt}"
        else:
            system_prompt = get_system_prompt(
                model_name=self.model,
                tool_support=self._tool_support.value,
                tools=self.tools.all() if self.tools else None,
            )
        self.memory.add("system", system_prompt)

    def run(self, prompt: str, stream: bool = False) -> AgentRun:
        """
        Run the agent on a prompt.

        This method implements the agentic loop following OpenResponses specification:
        1. Model samples from input
        2. If tool call: execute tool, return observation, continue
        3. If no tool call: return final output items

        IMPORTANT: No fallbacks that bypass the AI model are used.
        All tool calls must come from the model itself.

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

        # Create OpenResponses Response object
        response = Response(
            model=self.model,
            status=ResponseStatus.QUEUED,
            tool_choice=self.tool_choice,
            allowed_tools=self._allowed_tools or [],
        )
        response.mark_in_progress()

        # Add user prompt to memory
        self.memory.add("user", prompt)

        # Add input item
        user_item = create_message_item("user", prompt)
        response.input.append(user_item)

        if self.debug:
            print(f"\n[AgentNova] Model: {self.model}")
            print(f"[AgentNova] Backend: {self.backend.base_url}")
            print(f"[AgentNova] Tool support: {self._tool_support.value} (source: {getattr(self, '_tool_support_source', 'unknown')})")
            print(f"[AgentNova] tool_choice: {self.tool_choice.type.value}")
            print(f"[AgentNova] Tools: {self.tools.names()}")
            print(f"[AgentNova] Prompt: {prompt}\n")

        # OpenResponses: Agentic Loop
        # The model decides whether to call tools or respond directly.
        # No synthesis or fallback mechanisms are used.
        for step_num in range(self.max_steps):
            if self.debug:
                print(f"[Step {step_num + 1}]")

            # Generate response from model
            try:
                gen_response = self._generate()
            except Exception as e:
                if self.debug:
                    print(f"  ERROR: {e}")
                steps.append(StepResult(
                    type=StepResultType.ERROR,
                    error=str(e),
                ))
                response.mark_failed({"message": str(e), "type": "model_error"})
                break

            content = gen_response.get("content", "")
            native_tool_calls = gen_response.get("tool_calls", [])
            tokens = gen_response.get("usage", {}).get("total_tokens", 0)
            total_tokens += tokens

            if self.debug:
                print(f"  Content: {content[:200] if content else '(empty)'}...")
                print(f"  Native tool calls: {native_tool_calls}")

            # ---- Native tool calling ----
            if self._tool_support == ToolSupport.NATIVE and native_tool_calls:
                self.memory.add_tool_call("assistant", content, native_tool_calls)
                
                for tc in native_tool_calls:
                    tool_name = tc.get("name", "")
                    tool_args = tc.get("arguments", {})
                    tool_call_id = tc.get("id", "")

                    # OpenResponses: Check allowed_tools
                    if self._allowed_tools and tool_name not in self._allowed_tools:
                        error_msg = f"Tool '{tool_name}' not in allowed_tools: {self._allowed_tools}"
                        if self.debug:
                            print(f"  BLOCKED: {error_msg}")
                        self.memory.add_tool_result(
                            tool_call_id=tool_call_id,
                            name=tool_name,
                            content=f"Error: {error_msg}",
                        )
                        continue

                    # Fuzzy match tool name
                    tool_name = self._parser._fuzzy_match_tool(tool_name)

                    # Create FunctionCallItem
                    fc_item = create_function_call_item(tool_name, tool_args, tool_call_id)
                    fc_item.status = ItemStatus.IN_PROGRESS
                    response.add_output_item(fc_item)

                    result = self._execute_tool(tool_name, tool_args, prompt)
                    tool_calls += 1

                    # Update FunctionCallItem status
                    fc_item.status = ItemStatus.COMPLETED

                    # Create FunctionCallOutputItem
                    fco_item = create_function_call_output(tool_call_id, str(result))
                    response.add_output_item(fco_item)

                    # Add tool result to memory
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

                # Continue the agentic loop
                continue

            # ---- ReAct tool calling ----
            if self._tool_support == ToolSupport.REACT:
                parsed_calls = self._parser.parse(content)

                if parsed_calls:
                    call = parsed_calls[0]
                    tool_name = call.name
                    tool_args = call.arguments

                    # OpenResponses: Check allowed_tools
                    if self._allowed_tools and tool_name not in self._allowed_tools:
                        error_msg = f"Tool '{tool_name}' not in allowed_tools: {self._allowed_tools}"
                        if self.debug:
                            print(f"  BLOCKED: {error_msg}")
                        self.memory.add("assistant", content)
                        self.memory.add("user", f"Observation: Error: {error_msg}")
                        continue

                    # Create FunctionCallItem
                    fc_item = create_function_call_item(tool_name, tool_args)
                    fc_item.status = ItemStatus.IN_PROGRESS
                    response.add_output_item(fc_item)

                    result = self._execute_tool(tool_name, tool_args, prompt)
                    tool_calls += 1

                    # Update status
                    fc_item.status = ItemStatus.COMPLETED

                    # Create FunctionCallOutputItem
                    fco_item = create_function_call_output(fc_item.call_id, str(result))
                    response.add_output_item(fco_item)

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

                    continue

            # ---- Check for Final Answer ----
            # The model explicitly signals completion with "Final Answer:"
            if self._parser.is_final_answer(content):
                answer = self._parser.extract_final_answer(content)

                # Create output message item
                msg_item = create_message_item("assistant", answer)
                msg_item.status = ItemStatus.COMPLETED
                response.add_output_item(msg_item)

                steps.append(StepResult(
                    type=StepResultType.FINAL_ANSWER,
                    content=answer,
                    tokens_used=tokens,
                ))

                if self.debug:
                    print(f"  Final answer: {answer}")

                break

            # ---- No tool call, no final answer ----
            # Accept model's response as the final answer
            # This is the model's decision, not a fallback synthesis
            
            # Create output message item
            if content:
                msg_item = create_message_item("assistant", content)
                msg_item.status = ItemStatus.COMPLETED
                response.add_output_item(msg_item)

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
            response.mark_incomplete()
            steps.append(StepResult(
                type=StepResultType.MAX_STEPS,
                content="Maximum steps reached without final answer",
            ))

        total_ms = (time.time() - start_time) * 1000

        # Mark response as completed
        if response.status == ResponseStatus.IN_PROGRESS:
            response.mark_completed()

        # Store response for previous_response_id support
        self._response_history[response.id] = response

        # Get final answer
        final_answer = ""
        for step in reversed(steps):
            if step.type == StepResultType.FINAL_ANSWER:
                final_answer = step.content or ""
                break

        # Update usage in response
        response.usage["total_tokens"] = total_tokens

        return AgentRun(
            final_answer=final_answer,
            steps=steps,
            total_tokens=total_tokens,
            total_ms=total_ms,
            tool_calls=tool_calls,
            success=bool(final_answer),
        )

    def create_response(
        self,
        input_items: list = None,
        previous_response_id: str | None = None,
    ) -> Response:
        """
        Create a new Response following OpenResponses specification.

        This is the primary API for OpenResponses-compliant usage.

        Args:
            input_items: List of input items (messages, function call outputs)
            previous_response_id: ID of previous response to continue from

        Returns:
            Response object with output items
        """
        response = Response(
            model=self.model,
            status=ResponseStatus.QUEUED,
            tool_choice=self.tool_choice,
            allowed_tools=self._allowed_tools or [],
            previous_response_id=previous_response_id,
        )

        # Load previous response context if specified
        if previous_response_id and previous_response_id in self._response_history:
            prev_response = self._response_history[previous_response_id]
            # The previous input and output become part of context
            response.input = list(prev_response.input)
            response.input.extend(prev_response.output)

        # Add new input items
        if input_items:
            response.input.extend(input_items)

        return response

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
                print(f"  [MSG {i}] role={role}, content={content_preview!r}{' as tool_calls]' if tc else ''}")
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

        # Determine if tools should be passed
        # OpenResponses: tool_choice="none" means no tools
        pass_tools = None
        if self._tool_support == ToolSupport.NATIVE and self.tool_choice.type != ToolChoiceType.NONE:
            pass_tools = self.tools.all()

        response = self.backend.generate(
            model=self.model,
            messages=messages,
            tools=pass_tools,
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
        """
        Execute a tool by name with arguments.

        OpenResponses: Tool execution is straightforward - no synthesis.
        Arguments must come from the model.
        """
        from .core.tool_parse import _fuzzy_match_tool_name
        matched_name = _fuzzy_match_tool_name(name, self.tools.names())
        if matched_name:
            name = matched_name
        
        tool = self.tools.get_fuzzy(name)

        if tool is None:
            return f"Error: Unknown tool '{name}'. Available tools: {self.tools.names()}"

        # Normalize arguments with tool-specific aliases
        expected_params = [p.name for p in tool.params]
        
        from .core.helpers import normalize_args
        normalized_args = normalize_args(args, expected_params, tool_name=name)

        try:
            return tool.execute(**normalized_args)

        except TypeError as e:
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

    def get_response(self, response_id: str) -> Response | None:
        """Get a previous response by ID (for previous_response_id support)."""
        return self._response_history.get(response_id)

    def __repr__(self) -> str:
        return f"Agent(model={self.model}, tools={len(self.tools)}, support={self._tool_support.value}, tool_choice={self.tool_choice.type.value})"


__all__ = ["Agent"]