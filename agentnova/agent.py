"""
⚛️ AgentNova — Agent
Main agent class implementing the ReAct loop.

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

import time
from typing import Any, Generator, Optional

from .core.models import AgentRun, StepResult, Tool, ToolParam
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

    Example:
        agent = Agent(model="qwen2.5:0.5b", tools=["calculator", "shell"])
        result = agent.run("What is 15 * 8?")
        print(result.final_answer)
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
            **kwargs: Additional configuration
        """
        self.model = model
        self.max_steps = max_steps
        self.debug = debug
        self.force_react = force_react

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

        # Determine tool support level
        if force_react:
            self._tool_support = ToolSupportLevel.REACT
        elif not self.tools or len(self.tools) == 0:
            self._tool_support = ToolSupportLevel.NONE
        else:
            self._tool_support = self._detect_tool_support()

        # Initialize tool parser
        self._parser = ToolParser(self.tools.names())

        # Add system prompt
        self._add_system_prompt()

        # Store kwargs
        self._kwargs = kwargs

    def _detect_tool_support(self) -> ToolSupportLevel:
        """Detect the tool support level for the model."""
        # First check model config
        config_support = self.model_config.tool_support

        if config_support == "native" and not self.force_react:
            # Verify with backend test
            try:
                tested = self.backend.test_tool_support(self.model)
                if tested == ToolSupportLevel.NATIVE:
                    return ToolSupportLevel.NATIVE
            except Exception:
                pass

        return ToolSupportLevel.REACT

    def _add_system_prompt(self) -> None:
        """Add the system prompt to memory."""
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
                for tc in native_tool_calls:
                    tool_name = tc.get("name", "")
                    tool_args = tc.get("arguments", {})

                    # Fuzzy match tool name
                    tool_name = self._parser._fuzzy_match_tool(tool_name)

                    result = self._execute_tool(tool_name, tool_args, prompt)
                    tool_calls += 1

                    # Add to memory
                    self.memory.add_tool_call("assistant", content, native_tool_calls)
                    self.memory.add_tool_result(
                        tool_call_id=f"call_{tool_calls}",
                        name=tool_name,
                        content=str(result),
                    )

                    if not str(result).startswith("Error"):
                        successful_results.append(f"{tool_name}: {result}")

                    steps.append(StepResult(
                        type=StepResultType.TOOL_CALL,
                        content=content,
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

                    continue

            # Check for final answer
            if self._parser.is_final_answer(content):
                answer = self._parser.extract_final_answer(content)

                steps.append(StepResult(
                    type=StepResultType.FINAL_ANSWER,
                    content=answer,
                    tokens_used=tokens,
                ))

                if self.debug:
                    print(f"  Final answer: {answer}")

                break

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
            print(f"  [DEBUG] Tools: {[t.name for t in self.tools.all()] if self.tools else None}")

        response = self.backend.generate(
            model=self.model,
            messages=messages,
            tools=self.tools.all() if self._tool_support == ToolSupportLevel.NATIVE else None,
            temperature=self.model_config.default_temperature,
            max_tokens=self.model_config.default_max_tokens,
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

        # Normalize arguments
        expected_params = [p.name for p in tool.params]
        
        from .core.helpers import normalize_args, synthesize_tool_args
        normalized_args = normalize_args(args, expected_params)
        
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
