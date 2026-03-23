"""
⚛️ AgentNova R02.3 — Agent
Core ReAct agent that drives the think → act → observe loop.

Supports:
  • Native Ollama tool-calling (for models that expose it)
  • Text-based ReAct fallback (for models without native tool support)
  • Streaming output
  • Hooks for custom logging / UI
  • Enhanced argument normalization for small models
  • Few-shot prompting for improved accuracy
  • Pre-call argument synthesis

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Callable, Iterator

from .ollama_client import OllamaClient
from .memory import Memory
from .tools import ToolRegistry
from .types import StepResultType
from .models import StepResult, AgentRun
from .prompts import (
    TOOL_ARG_ALIASES, FEW_SHOT_SUFFIX, FEW_SHOT_COMPACT,
    NATIVE_TOOL_HINTS, REACT_SYSTEM_SUFFIX,
    PLATFORM_DIR_CMD, PLATFORM_LIST_CMD
)
from .helpers import (
    _strip_tool_prefix, _extract_calc_expression, _extract_echo_text,
    _is_simple_answered_query, _is_greeting_or_simple, _is_small_model,
    _detect_and_fix_repetition
)
from .args_normal import (
    _normalize_args, _fix_calculator_args, _synthesize_missing_args,
    _generate_helpful_error_message
)
from .tool_parse import (
    _parse_react, _parse_json_tool_call, _fuzzy_match_tool_name,
    _looks_like_tool_schema, _looks_like_tool_schema_dump,
    _extract_python_code, _try_extract_tool_from_malformed
)

# Import config for backend selection (avoids circular import)
import os as _os
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
#  Agent                                                               #
# ------------------------------------------------------------------ #

class Agent:
    """
    A single autonomous agent backed by a local Ollama model.

    Parameters
    ----------
    model : str
        Ollama model tag, e.g. "llama3.1:8b" or "qwen2.5:14b".
    tools : ToolRegistry | None
        Tools this agent may call.
    system_prompt : str
        Base instructions for the agent.
    max_steps : int
        Safety ceiling on tool-call iterations per run.
    client : OllamaClient | None
        Shared client (creates one if not provided).
    force_react : bool
        If True, always use text-based ReAct even if the model supports native tools.
    on_step : Callable[[StepResult], None] | None
        Called after each step — useful for live UI updates.
    model_options : dict | None
        Passed through to Ollama (temperature, num_ctx, etc.).
    model_family : str | None
        Model family (e.g., "llama", "qwen2", "gemma3"). If None, auto-detected from Ollama API.
        Useful for family-specific handling in subclasses or custom logic.
    few_shot : bool | None
        If True, add few-shot examples for small models. If None, auto-detect based on model size.
    use_compact_prompt : bool
        If True, use compact few-shot prompt (less tokens).
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
        few_shot: bool | None = None,
        use_compact_prompt: bool = False,
        model_family: str | None = None,
    ):
        self.model = model
        self.tools = tools or ToolRegistry()
        self.max_steps = max_steps
        # Backend-aware client selection
        if client is not None:
            self.client = client
        elif _AGENTNOVA_BACKEND == "bitnet" and _BITNET_AVAILABLE:
            from ..bitnet_client import BitnetClient
            from ..config import BITNET_BASE_URL
            self.client = BitnetClient(base_url=BITNET_BASE_URL)
        else:
            self.client = OllamaClient()
        self.force_react = force_react
        self.on_step = on_step
        self.model_options = model_options or {}
        self.debug = debug
        self.use_compact_prompt = use_compact_prompt

        # Determine model family (auto-detect if not provided)
        if model_family is not None:
            self.model_family = model_family
        elif hasattr(self.client, 'get_model_family'):
            self.model_family = self.client.get_model_family(model)
        else:
            self.model_family = None

        # Determine tool support level: "native", "react", "none", or "untested"
        if force_react:
            self._tool_support = "react"
        else:
            try:
                from ..cli import get_tool_support
                self._tool_support = get_tool_support(model, self.client)
            except ImportError:
                self._tool_support = "untested"
        
        if self._tool_support == "untested":
            self._tool_support = "react"
        
        self._native_tools = (self._tool_support == "native")
        self._no_tools = (self._tool_support == "none")
        
        # Get family-specific configuration
        from .model_family_config import (
            get_family_config, should_use_few_shot, get_few_shot_style,
            get_react_system_suffix, get_native_tool_hints, has_known_issues,
            get_stop_tokens, needs_no_think_directive, get_no_tools_system_prompt
        )
        self._family_config = get_family_config(self.model_family)
        self._family_issues = has_known_issues(self.model_family)
        self._needs_no_think = needs_no_think_directive(self.model_family)
        
        # Add stop tokens for ReAct mode
        if self._tool_support == "react" and self.tools.all():
            family_stops = get_stop_tokens(self.model_family or "")
            react_stops = ["\nFinal Answer:"]
            existing_stops = self.model_options.get("stop", [])
            if isinstance(existing_stops, str):
                existing_stops = [existing_stops]
            all_stops = list(set(existing_stops + family_stops + react_stops))
            self.model_options["stop"] = all_stops
        
        # Determine if we should use few-shot prompting
        self._is_small_model = _is_small_model(model)
        if few_shot is not None:
            self._use_few_shot = few_shot
        else:
            self._use_few_shot = should_use_few_shot(self.model_family or "", model)
        
        # ReAct models ALWAYS need few-shot examples
        if self._tool_support == "react" and self.tools.all():
            self._use_few_shot = True
        
        self._few_shot_style = get_few_shot_style(self.model_family or "")

        # Build system prompt
        base_sys = system_prompt
        
        if self._tool_support == "react" and self.tools.all():
            tool_descriptions = "\n".join(
                f"- {t.name}: {t.description}" for t in self.tools.all()
            )
            react_suffix = get_react_system_suffix(self.model_family or "")
            base_sys = base_sys + f"\n\nAvailable tools:\n{tool_descriptions}\n{react_suffix}"
        
        elif self._tool_support == "native" and self.tools.all():
            native_hints = get_native_tool_hints(self.model_family or "")
            if native_hints:
                base_sys = base_sys + "\n\n" + native_hints
        
        elif self._tool_support == "none":
            family_override = get_no_tools_system_prompt(self.model_family or "")
            if family_override:
                base_sys = family_override
        
        # Add few-shot examples
        add_few_shot = False
        if self._use_few_shot and self.tools.all():
            if self._tool_support == "react":
                add_few_shot = True
        
        if add_few_shot:
            use_compact = use_compact_prompt or self._few_shot_style == "compact"
            few_shot_suffix = FEW_SHOT_COMPACT if use_compact else FEW_SHOT_SUFFIX
            
            if self._family_issues.get("truncate_json"):
                few_shot_suffix = FEW_SHOT_COMPACT
            
            base_sys = base_sys + few_shot_suffix

        # Debug: Show prompt construction
        if debug:
            print(f"\n  🔍 DEBUG: System prompt construction")
            print(f"    _tool_support={self._tool_support}")
            print(f"    _use_few_shot={self._use_few_shot}")
            print(f"    _few_shot_style={self._few_shot_style}")
            print(f"    _is_small_model={self._is_small_model}")
            print(f"    model_family={self.model_family}")
            print(f"    _family_issues={self._family_issues}")
            print(f"    System prompt length: {len(base_sys)} chars")

        self.memory = Memory(
            system_prompt=base_sys,
            max_turns=memory_max_turns,
        )

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def run(self, user_input: str) -> AgentRun:
        """
        Run the agent on a user message and return a complete AgentRun.
        """
        run = AgentRun()
        t0 = time.perf_counter()
        self.memory.add_user(user_input)

        # Short-circuit for models with no tool support
        if self._no_tools:
            step_t0 = time.perf_counter()
            response = self.client.chat(
                model=self.model,
                messages=self.memory.to_messages(),
                tools=None,
                options=self.model_options,
                think=False if self._needs_no_think else None,
            )
            elapsed = (time.perf_counter() - step_t0) * 1000
            msg = response.get("message", {})
            content = msg.get("content", "")
            
            if self.debug:
                print(f"\n  🔍 DEBUG: No tool support mode")
                print(f"    _tool_support={self._tool_support}")
                print(f"    content[:100]={content[:100]!r}")
            
            self.memory.add_assistant(content)
            run.final_answer = content
            run.total_ms = elapsed
            run.steps.append(StepResult(type="final", content=content, elapsed_ms=elapsed))
            return run

        # Loop guards
        _tool_call_counts: dict[str, int] = {}
        _successful_results: list[str] = []
        _successful_tools: set[str] = set()
        _last_tool_args: dict[str, dict] = {}
        _max_calls_per_tool = 2
        _max_total_tool_calls = 4

        for _ in range(self.max_steps):
            step_t0 = time.perf_counter()

            response = self.client.chat(
                model=self.model,
                messages=self.memory.to_messages(),
                tools=self.tools.schemas() if self._native_tools else None,
                options=self.model_options,
                think=False if self._needs_no_think else None,
            )

            elapsed = (time.perf_counter() - step_t0) * 1000
            msg = response.get("message", {})
            content = msg.get("content", "")
            tool_calls_raw = msg.get("tool_calls", [])

            # Debug output
            if self.debug:
                print(f"\n  🔍 DEBUG: Response received")
                print(f"    _tool_support={self._tool_support}")
                print(f"    _native_tools={self._native_tools}")
                print(f"    tool_calls_raw={tool_calls_raw!r}")
                print(f"    content (FULL): {content!r}")

            # ---- Greeting short-circuit ---- #
            if self._native_tools and self.tools.all() and _is_greeting_or_simple(user_input):
                greeting_reply = content if content and not _looks_like_tool_schema(content) \
                    else "Hello! How can I help you today?"
                final_step = StepResult(type="final", content=greeting_reply, elapsed_ms=elapsed)
                run.steps.append(final_step)
                self._emit(final_step)
                run.final_answer = greeting_reply
                self.memory.add_assistant(greeting_reply)
                break

            # ---- Native tool calling ---- #
            if self._native_tools and tool_calls_raw:
                for tc in tool_calls_raw:
                    fn = tc.get("function", {})
                    t_name = fn.get("name", "")
                    t_args = fn.get("arguments", {})
                    if isinstance(t_args, str):
                        try:
                            t_args = json.loads(t_args)
                        except json.JSONDecodeError:
                            t_args = {}

                    # Code-in-name detection
                    code_indicators = ["(", ")", "+", "-", "*", "/", "=", "[", "]", " "]
                    if t_name and any(c in t_name for c in code_indicators):
                        if self.debug:
                            print(f"    code-in-name detected: {t_name!r}, attempting recovery")
                        fuzzy = _fuzzy_match_tool_name(t_name, self.tools)
                        if fuzzy:
                            if fuzzy == "calculator":
                                t_args = {"expression": t_name}
                            elif fuzzy == "python_repl" and not t_args.get("code"):
                                t_args = {"code": t_name}
                            t_name = fuzzy
                        else:
                            if self.debug:
                                print(f"    could not recover tool name, skipping")
                            continue

                    # Fuzzy match for unknown tools
                    if t_name and not self.tools.get(t_name):
                        original_t_name = t_name
                        fuzzy = _fuzzy_match_tool_name(t_name, self.tools)
                        if self.debug:
                            print(f"    native fuzzy_match({t_name!r}) -> {fuzzy!r}")
                        if fuzzy:
                            if fuzzy == "shell" and original_t_name.lower() in ("echo", "print", "say"):
                                text_val = (
                                    t_args.get("text") or t_args.get("value") or
                                    t_args.get("message") or t_args.get("content") or
                                    t_args.get("input") or t_args.get("arg") or ""
                                )
                                if text_val:
                                    t_args = {"command": f"echo {text_val}"}
                                    if self.debug:
                                        print(f"    shell: synthesized 'echo' command from text={text_val!r}")
                            t_name = fuzzy
                        else:
                            if self.debug:
                                print(f"    unknown tool {t_name!r}, skipping")
                            continue

                    # Normalize arguments
                    t_args = _normalize_args(t_args, self.tools.get(t_name), t_name)
                    t_args = _synthesize_missing_args(t_name, t_args, user_input, _successful_results, self.tools)

                    # Python REPL code reconstruction
                    if t_name == "python_repl" and not t_args.get("code"):
                        candidate = (
                            t_args.get("value") or t_args.get("expression") or
                            t_args.get("script") or t_args.get("command") or
                            t_args.get("query") or ""
                        )
                        if candidate:
                            code = candidate if "\n" in candidate or candidate.strip().startswith("print") \
                                else f"print({candidate})"
                            t_args = {"code": code}
                            if self.debug:
                                print(f"    python_repl code reconstructed: {code!r}")
                        else:
                            if self.debug:
                                print(f"    python_repl with no recoverable code, skipping")
                            continue
                    
                    # Wrap bare expressions
                    if t_name == "python_repl" and t_args.get("code"):
                        code = t_args["code"]
                        if (
                            "\n" not in code.strip()
                            and not code.strip().startswith("print(")
                            and not "=" in code
                            and not code.strip().startswith("import")
                            and not code.strip().startswith("from")
                            and not code.strip().startswith("def ")
                            and not code.strip().startswith("class ")
                        ):
                            wrapped_code = f"print({code.strip()})"
                            t_args["code"] = wrapped_code
                            if self.debug:
                                print(f"    python_repl: wrapped bare expression: {code!r} -> {wrapped_code!r}")

                    t_args = _fix_calculator_args(t_name, t_args, user_input, _successful_results)
                    
                    # Redirect wrong tool to calculator
                    if (
                        t_name != "calculator"
                        and self.tools.get("calculator")
                        and _successful_results
                    ):
                        q_lower = user_input.lower()
                        last_result = _strip_tool_prefix(_successful_results[-1])
                        try:
                            last_num = float(last_result)
                            redirect_expr = None
                            if "sqrt" in q_lower or "square root" in q_lower:
                                redirect_expr = f"sqrt({last_num:.0f})"
                            if redirect_expr:
                                if self.debug:
                                    print(f"    redirecting wrong tool {t_name!r} → calculator({redirect_expr!r})")
                                t_name = "calculator"
                                t_args = {"expression": redirect_expr}
                        except (ValueError, TypeError):
                            pass

                    # Skip redundant calls
                    if t_args.pop("_redundant", False):
                        prior = t_args.pop("_prior_result", "")
                        if self.debug:
                            print(f"    skipping redundant {t_name} call (prior={prior!r})")
                        self.memory.add_assistant(content or "", tool_calls=tool_calls_raw)
                        self.memory.add_tool_result(t_name, prior)
                        _successful_results.append(f"{t_name} → {prior}")
                        continue

                    t_args.pop("_prior_result", None)

                    if not t_name or not t_name.strip():
                        continue

                    _tool_call_counts[t_name] = _tool_call_counts.get(t_name, 0) + 1

                    total_calls = sum(_tool_call_counts.values())
                    if _tool_call_counts[t_name] > _max_calls_per_tool or total_calls > _max_total_tool_calls:
                        final_answer = self._synthesize(user_input, _successful_results)
                        final_step = StepResult(type="final", content=final_answer, elapsed_ms=elapsed)
                        run.steps.append(final_step)
                        self._emit(final_step)
                        run.final_answer = final_answer
                        break

                    corrected_tc = {"function": {"name": t_name, "arguments": t_args}}
                    self.memory.add_assistant(content or "", tool_calls=[corrected_tc])

                    call_step = StepResult(
                        type="tool_call",
                        content=f"{t_name}({t_args})",
                        tool_name=t_name,
                        tool_args=t_args,
                        elapsed_ms=elapsed,
                    )
                    run.steps.append(call_step)
                    self._emit(call_step)

                    result = self.tools.invoke(t_name, t_args)
                    result_str = str(result)

                    result_step = StepResult(type="tool_result", content=result_str, tool_name=t_name)
                    run.steps.append(result_step)
                    self._emit(result_step)
                    self.memory.add_tool_result(t_name, result_str)

                    if not result_str.startswith("[Tool error]"):
                        _successful_results.append(f"{t_name} → {result_str}")
                        _successful_tools.add(t_name)

                continue

            # ---- Immediate synthesize after successful tool result ---- #
            if _successful_results and _is_simple_answered_query(user_input, _successful_results) and self._native_tools:
                final_answer = self._synthesize(user_input, _successful_results)
                final_step = StepResult(type="final", content=final_answer, elapsed_ms=elapsed)
                run.steps.append(final_step)
                self._emit(final_step)
                run.final_answer = final_answer
                break

            # ---- JSON fallback for native tools ---- #
            if self._native_tools and not tool_calls_raw and self.tools.all() and content:
                if self.debug:
                    print(f"\n  🔍 DEBUG: JSON fallback triggered")
                    print(f"    content[:100]: {content[:100]!r}")

                t_name, t_args = _parse_json_tool_call(content, debug=self.debug)
                
                if self.debug:
                    print(f"    parsed JSON: name={t_name!r}, args={t_args!r}")
                
                if t_name is None or not self.tools.get(t_name):
                    if _looks_like_tool_schema_dump(content):
                        if self.debug:
                            print(f"    detected schema dump, trying to extract tool...")
                        available_tools = [t.name for t in self.tools.all()]
                        extracted_name, extracted_args = _try_extract_tool_from_malformed(content, available_tools)
                        if extracted_name:
                            t_name = extracted_name
                            t_args = extracted_args or {}
                            if self.debug:
                                print(f"    extracted from malformed: name={t_name!r}")
                
                if t_name is None and "python_repl" in [t.name for t in self.tools.all()]:
                    extracted_code = _extract_python_code(content)
                    if extracted_code:
                        if self.debug:
                            print(f"    extracted Python code block ({len(extracted_code)} chars)")
                        t_name = "python_repl"
                        t_args = {"code": extracted_code}
                
                if not t_name or not t_name.strip():
                    t_name = None
                    
                if t_name and t_args is not None and not self.tools.get(t_name):
                    original_t_name = t_name
                    fuzzy_name = _fuzzy_match_tool_name(t_name, self.tools)
                    if self.debug:
                        print(f"    fuzzy_match({t_name!r}) -> {fuzzy_name!r}")
                    if fuzzy_name:
                        code_indicators = ["(", ")", "+", "-", "*", "/"]
                        if fuzzy_name == "calculator" and any(c in original_t_name for c in code_indicators):
                            t_args = {"expression": original_t_name}
                        elif fuzzy_name == "calculator" and original_t_name.lower() in ("sqrt", "square", "root", "squareroot"):
                            val = (
                                t_args.get("value") or t_args.get("number") or
                                t_args.get("n") or t_args.get("x") or
                                t_args.get("input") or t_args.get("arg") or
                                t_args.get("expression") or ""
                            )
                            if val:
                                t_args = {"expression": f"sqrt({val})"}
                                if self.debug:
                                    print(f"    calculator: synthesized sqrt expression from value={val!r}")
                        elif fuzzy_name == "python_repl" and any(c in original_t_name for c in code_indicators):
                            if not t_args.get("code"):
                                code = original_t_name if original_t_name.strip().startswith("print") \
                                    else f"print({original_t_name})"
                                t_args = {"code": code}
                        elif fuzzy_name == "shell" and original_t_name.lower() in ("echo", "print", "say"):
                            text_val = (
                                t_args.get("text") or t_args.get("value") or
                                t_args.get("message") or t_args.get("content") or
                                t_args.get("input") or t_args.get("arg") or
                                t_args.get("string") or ""
                            )
                            if text_val:
                                t_args = {"command": f"echo {text_val}"}
                                if self.debug:
                                    print(f"    shell: synthesized 'echo' command from text={text_val!r}")
                        t_name = fuzzy_name

                if t_name == "python_repl" and t_args is not None and not t_args.get("code"):
                    candidate = (
                        t_args.get("value") or t_args.get("expression") or
                        t_args.get("script") or t_args.get("command") or
                        t_args.get("query") or ""
                    )
                    if candidate:
                        code = candidate if "\n" in candidate or candidate.strip().startswith("print") \
                            else f"print({candidate})"
                        t_args = {"code": code}
                        if self.debug:
                            print(f"    python_repl code reconstructed from alt arg: {code!r}")
                
                if self.debug:
                    print(f"    final: name={t_name!r}, tool_exists={self.tools.get(t_name) is not None}")
                
                if t_name and t_args is not None and self.tools.get(t_name):
                    t_args = _normalize_args(t_args, self.tools.get(t_name), t_name)
                    t_args = _synthesize_missing_args(t_name, t_args, user_input, _successful_results, self.tools)
                    
                    if t_name == "python_repl" and not t_args.get("code"):
                        q_lower = user_input.lower()
                        if "date" in q_lower or "time" in q_lower or "today" in q_lower or "now" in q_lower:
                            if self.debug:
                                print(f"    python_repl with empty code for date/time query, synthesizing...")
                            if "date" in q_lower and "time" in q_lower:
                                t_args["code"] = "from datetime import datetime\nnow = datetime.now()\nprint(f\"Today is {now.strftime('%A, %B %d, %Y')} and the time is {now.strftime('%I:%M %p')}.\")"
                            elif "date" in q_lower or "today" in q_lower:
                                t_args["code"] = "from datetime import datetime\nprint(datetime.now().strftime('Today is %A, %B %d, %Y.'))"
                            elif "time" in q_lower:
                                t_args["code"] = "from datetime import datetime\nprint(datetime.now().strftime('The current time is %I:%M %p.'))"
                            else:
                                t_args["code"] = "from datetime import datetime\nprint(datetime.now())"
                            if self.debug:
                                print(f"    synthesized code: {t_args['code'][:50]}...")
                        else:
                            if self.debug:
                                print(f"    python_repl with empty code but not a date/time query, skipping...")
                            continue

                    already_succeeded = t_name in _successful_tools
                    same_args = _last_tool_args.get(t_name) == t_args
                    if already_succeeded and same_args:
                        pending = [
                            t.name for t in self.tools.all()
                            if t.name not in _successful_tools
                        ]
                        if pending:
                            self.memory.add_user(
                                f"You already have the result for {t_name} with those arguments. "
                                f"Please call {pending[0]} next to complete the answer."
                            )
                        else:
                            final_answer = self._synthesize(user_input, _successful_results)
                            final_step = StepResult(type="final", content=final_answer, elapsed_ms=elapsed)
                            run.steps.append(final_step)
                            self._emit(final_step)
                            run.final_answer = final_answer
                            break
                        continue

                    _last_tool_args[t_name] = t_args

                    t_args = _fix_calculator_args(t_name, t_args, user_input, _successful_results)

                    if t_args.pop("_redundant", False):
                        prior = t_args.pop("_prior_result", "")
                        if self.debug:
                            print(f"    skipping redundant {t_name} call (prior={prior!r})")
                        self.memory.add_tool_result(t_name, prior)
                        _successful_results.append(f"{t_name} → {prior}")
                        _successful_tools.add(t_name)
                        continue

                    t_args.pop("_prior_result", None)

                    _tool_call_counts[t_name] = _tool_call_counts.get(t_name, 0) + 1

                    total_calls = sum(_tool_call_counts.values())
                    if _tool_call_counts[t_name] > _max_calls_per_tool or total_calls > _max_total_tool_calls:
                        final_answer = self._synthesize(user_input, _successful_results)
                        final_step = StepResult(type="final", content=final_answer, elapsed_ms=elapsed)
                        run.steps.append(final_step)
                        self._emit(final_step)
                        run.final_answer = final_answer
                        break

                    self.memory.add_assistant(content)

                    call_step = StepResult(
                        type="tool_call",
                        content=f"{t_name}({t_args})",
                        tool_name=t_name,
                        tool_args=t_args,
                        elapsed_ms=elapsed,
                    )
                    run.steps.append(call_step)
                    self._emit(call_step)

                    result = self.tools.invoke(t_name, t_args)
                    result_str = str(result)

                    result_step = StepResult(type="tool_result", content=result_str, tool_name=t_name)
                    run.steps.append(result_step)
                    self._emit(result_step)

                    if result_str.startswith("[Tool error]"):
                        tool_obj = self.tools.get(t_name)
                        helpful_error = _generate_helpful_error_message(t_name, tool_obj, t_args, result_str)
                        self.memory.add_tool_result(t_name, helpful_error)
                    else:
                        _successful_results.append(f"{t_name} → {result_str}")
                        _successful_tools.add(t_name)
                        self.memory.add_tool_result(t_name, result_str)

                    if not result_str.startswith("[Tool error]") and len(_successful_tools) >= 2:
                        results_so_far = "\n".join(f"- {r}" for r in _successful_results)
                        self.memory.add_user(
                            f"You have already gathered the following information:\n{results_so_far}\n\n"
                            f"Please now answer the original question in plain text using these results.\n"
                            f"Original question: {user_input}\n"
                            "Do NOT call any more tools."
                        )
                        nudge_response = self.client.chat(
                            model=self.model,
                            messages=self.memory.to_messages(),
                            options=self.model_options,
                            think=False if self._needs_no_think else None,
                        )
                        nudge_content = nudge_response.get("message", {}).get("content", "").strip()
                        _, check_args = _parse_json_tool_call(nudge_content, debug=False)
                        if nudge_content and check_args is None:
                            final_step = StepResult(type="final", content=nudge_content, elapsed_ms=elapsed)
                            run.steps.append(final_step)
                            self._emit(final_step)
                            run.final_answer = nudge_content
                            self.memory.add_assistant(nudge_content)
                            break
                        else:
                            self.memory._history.pop()
                    continue

            # ---- Native tool empty response retry ---- #
            if self._native_tools and not tool_calls_raw and not content and self.tools.all():
                retry_count = getattr(self, '_empty_retry_count', 0)
                
                if retry_count == 0:
                    self._empty_retry_count = 1
                    if self.debug:
                        print(f"\n  🔍 DEBUG: Native tool returned empty, retrying with direct instruction")
                    
                    q_lower = user_input.lower()
                    tool_hint = ""
                    available_tools = [t.name for t in self.tools.all()]
                    
                    if "calculator" in available_tools and any(kw in q_lower for kw in 
                        ["times", "multiply", "plus", "minus", "divided", "power", "sqrt", 
                         "square root", "what is", "calculate", "compute", " * ", " + ", " - ", " / "]):
                        extracted_expr = _extract_calc_expression(user_input)
                        if extracted_expr:
                            tool_hint = f"You must call the calculator tool NOW. Use it with {{\"expression\": \"{extracted_expr}\"}}."
                            if self.debug:
                                print(f"    extracted expression: {extracted_expr}")
                        else:
                            tool_hint = "You must call the calculator tool. Use it with an expression like {\"expression\": \"15 * 8\"}."
                    elif "shell" in available_tools and any(kw in q_lower for kw in 
                        ["echo", "print", "directory", "pwd", "folder", "date", "time", "today"]):
                        if "echo" in q_lower or "print" in q_lower:
                            echo_text = _extract_echo_text(user_input)
                            if echo_text:
                                tool_hint = f"You must call the shell tool NOW. Use it with {{\"command\": \"echo {echo_text}\"}}."
                                if self.debug:
                                    print(f"    extracted echo text: {echo_text}")
                            else:
                                tool_hint = "You must call the shell tool. Use it with {\"command\": \"echo YourText\"}."
                        elif "directory" in q_lower or "pwd" in q_lower or "folder" in q_lower:
                            tool_hint = f"You must call the shell tool. Use it with {{\"command\": \"{PLATFORM_DIR_CMD}\"}}."
                        elif "date" in q_lower or "time" in q_lower or "today" in q_lower:
                            if "python_repl" in available_tools:
                                tool_hint = "You must call python_repl with code to get the date. Use: from datetime import datetime; print(datetime.now())"
                            else:
                                tool_hint = "You must call a tool to get the date/time. Use python_repl if available."
                        else:
                            tool_hint = "You must call the shell tool to answer this question."
                    elif "python_repl" in available_tools and any(kw in q_lower for kw in 
                        ["python", "code", "execute", "run"]):
                        tool_hint = "You must call the python_repl tool with the code to execute."
                    else:
                        first_tool = available_tools[0] if available_tools else ""
                        tool_hint = f"You must call the {first_tool} tool to answer this question."
                    
                    if tool_hint:
                        self.memory.add_assistant("")
                        self.memory.add_user(f"{tool_hint}\n\nOriginal question: {user_input}")
                        continue
                
                elif retry_count == 1:
                    self._empty_retry_count = 2
                    if self.debug:
                        print(f"\n  🔍 DEBUG: Second empty response, synthesizing tool call directly")
                    
                    q_lower = user_input.lower()
                    synthesized_tool = None
                    synthesized_args = {}
                    available_tools = [t.name for t in self.tools.all()]
                    
                    if "calculator" in available_tools:
                        expr = _extract_calc_expression(user_input)
                        if expr:
                            synthesized_tool = "calculator"
                            synthesized_args = {"expression": expr}
                            if self.debug:
                                print(f"    synthesized: calculator({expr})")
                    
                    if not synthesized_tool and "shell" in available_tools:
                        if "echo" in q_lower or "print" in q_lower:
                            echo_text = _extract_echo_text(user_input)
                            if echo_text:
                                synthesized_tool = "shell"
                                synthesized_args = {"command": f"echo {echo_text}"}
                                if self.debug:
                                    print(f"    synthesized: shell(echo {echo_text})")
                        elif "directory" in q_lower or "pwd" in q_lower or "folder" in q_lower:
                            synthesized_tool = "shell"
                            synthesized_args = {"command": PLATFORM_DIR_CMD}
                        elif "date" in q_lower or "time" in q_lower or "today" in q_lower:
                            if "python_repl" in available_tools:
                                synthesized_tool = "python_repl"
                                synthesized_args = {"code": "from datetime import datetime; print(datetime.now())"}
                    
                    if synthesized_tool and synthesized_args:
                        t_name = synthesized_tool
                        t_args = synthesized_args
                        
                        call_step = StepResult(
                            type="tool_call",
                            content=f"{t_name}({t_args})",
                            tool_name=t_name,
                            tool_args=t_args,
                            elapsed_ms=elapsed,
                        )
                        run.steps.append(call_step)
                        self._emit(call_step)
                        
                        result = self.tools.invoke(t_name, t_args)
                        result_str = str(result)
                        
                        result_step = StepResult(type="tool_result", content=result_str, tool_name=t_name)
                        run.steps.append(result_step)
                        self._emit(result_step)
                        
                        _successful_results.append(f"{t_name} → {result_str}")
                        _successful_tools.add(t_name)
                        
                        final_answer = self._synthesize(user_input, _successful_results)
                        final_step = StepResult(type="final", content=final_answer, elapsed_ms=elapsed)
                        run.steps.append(final_step)
                        self._emit(final_step)
                        run.final_answer = final_answer
                        break
                    
                    if self.debug:
                        print(f"    could not synthesize tool call, giving up")
                    run.final_answer = ""
                    break

            # ---- ReAct text parsing ---- #
            if not self._native_tools and self.tools.all():
                thought, t_name, t_args, final_answer = _parse_react(content)
                
                if self.debug:
                    print(f"\n  🔍 DEBUG: ReAct parsing result")
                    print(f"    thought={thought!r}")
                    print(f"    t_name={t_name!r}")
                    print(f"    t_args={t_args!r}")
                    print(f"    final_answer={final_answer!r}")

                if not t_name and not final_answer:
                    json_name, json_args = _parse_json_tool_call(content, debug=self.debug)
                    if json_name:
                        t_name = json_name
                        t_args = json_args
                        if self.debug:
                            print(f"    ReAct path: parsed JSON tool call: name={t_name!r}, args={t_args!r}")

                if not t_name and not final_answer:
                    python_code = _extract_python_code(content)
                    if python_code and self.tools.get("python_repl"):
                        t_name = "python_repl"
                        t_args = {"code": python_code}
                        if self.debug:
                            print(f"    ReAct path: detected Python code block, using python_repl")

                if not t_name and not final_answer and not thought:
                    if not _successful_results and not hasattr(self, '_format_reminder_sent'):
                        self._format_reminder_sent = True
                        if self.debug:
                            print(f"\n  🔍 DEBUG: Model didn't use ReAct format, sending reminder")
                        self.memory.add_assistant(content)
                        tool_names = [t.name for t in self.tools.all()]
                        first_tool = self.tools.all()[0] if self.tools.all() else None
                        arg_hint = "input"
                        if first_tool and first_tool.params:
                            arg_hint = first_tool.params[0].name
                        reminder = (
                            f"Answer this question: {user_input}\n\n"
                            f"Use this format:\n"
                            f"Action: {tool_names[0]}\n"
                            f"Action Input: {{\"{arg_hint}\": \"<your calculation>\"}}"
                        )
                        self.memory.add_user(reminder)
                        continue

                if thought:
                    step = StepResult(type="thought", content=thought, elapsed_ms=elapsed)
                    run.steps.append(step)
                    self._emit(step)

                if t_name and t_name.strip() and t_args is not None:
                    if not self.tools.get(t_name):
                        original_t_name = t_name
                        fuzzy_name = _fuzzy_match_tool_name(t_name, self.tools)
                        if self.debug:
                            print(f"    ReAct fuzzy_match({t_name!r}) -> {fuzzy_name!r}")
                        if fuzzy_name:
                            if fuzzy_name == "calculator" and original_t_name.lower() in ("sqrt", "square", "root", "squareroot"):
                                val = (
                                    t_args.get("value") or t_args.get("number") or
                                    t_args.get("n") or t_args.get("x") or
                                    t_args.get("input") or t_args.get("arg") or
                                    t_args.get("expression") or ""
                                )
                                if val:
                                    t_args = {"expression": f"sqrt({val})"}
                                    if self.debug:
                                        print(f"    calculator: synthesized sqrt expression from value={val!r}")
                            elif fuzzy_name == "shell" and original_t_name.lower() in ("echo", "print", "say"):
                                text_val = (
                                    t_args.get("text") or t_args.get("value") or
                                    t_args.get("message") or t_args.get("content") or
                                    t_args.get("input") or t_args.get("arg") or ""
                                )
                                if text_val:
                                    t_args = {"command": f"echo {text_val}"}
                                    if self.debug:
                                        print(f"    shell: synthesized 'echo' command from text={text_val!r}")
                            t_name = fuzzy_name
                        else:
                            if self.debug:
                                print(f"    Unknown tool {t_name!r}, skipping")
                            t_name = None
                    
                    if t_name:
                        t_args = _normalize_args(t_args, self.tools.get(t_name), t_name)
                        t_args = _synthesize_missing_args(t_name, t_args, user_input, _successful_results, self.tools)
                        
                        _tool_call_counts[t_name] = _tool_call_counts.get(t_name, 0) + 1
                        
                        total_calls = sum(_tool_call_counts.values())
                        if _tool_call_counts[t_name] > _max_calls_per_tool or total_calls > _max_total_tool_calls:
                            final_answer = self._synthesize(user_input, _successful_results)
                            final_step = StepResult(type="final", content=final_answer, elapsed_ms=elapsed)
                            run.steps.append(final_step)
                            self._emit(final_step)
                            run.final_answer = final_answer
                            break

                        call_step = StepResult(
                            type="tool_call",
                            content=content,
                            tool_name=t_name,
                            tool_args=t_args,
                            elapsed_ms=elapsed,
                        )
                        run.steps.append(call_step)
                        self._emit(call_step)

                        result = self.tools.invoke(t_name, t_args)
                        result_str = str(result)

                        result_step = StepResult(type="tool_result", content=result_str, tool_name=t_name)
                        run.steps.append(result_step)
                        self._emit(result_step)

                        if not result_str.startswith("[Tool error]"):
                            _successful_results.append(f"{t_name} → {result_str}")

                        observation = content + f"\nObservation: {result_str}\n"
                        self.memory.add_user(observation)
                        continue

                if final_answer:
                    final_step = StepResult(type="final", content=final_answer, elapsed_ms=elapsed)
                    run.steps.append(final_step)
                    self._emit(final_step)
                    run.final_answer = final_answer
                    self.memory.add_assistant(content)
                    break

            # ---- Plain response (no tools or tool loop ended) ---- #
            total_calls = sum(_tool_call_counts.values())
            if (
                self._native_tools
                and self.tools.all()
                and _successful_results
                and total_calls == 1
                and not tool_calls_raw
            ):
                results_so_far = "\n".join(f"- {r}" for r in _successful_results)

                extra_hint = ""
                q_lower = user_input.lower()
                last_result = _strip_tool_prefix(_successful_results[-1])
                try:
                    last_num = float(last_result)
                    if "sqrt" in q_lower or "square root" in q_lower:
                        extra_hint = (
                            f"\nThe user asked for the square root of the previous result. "
                            f"Call calculator with expression=\"sqrt({last_num:.0f if last_num == int(last_num) else last_num})\". "
                            f"Do NOT call any other tool."
                        )
                except (ValueError, TypeError):
                    pass

                self.memory.add_assistant(content)
                self.memory.add_user(
                    f"You have gathered so far:\n{results_so_far}\n\n"
                    f"The original question was: {user_input}\n\n"
                    "If the question requires further calculation, call the correct tool with the "
                    "correct next expression using the result above as input (do NOT pass "
                    "the raw result as the expression — compute something new with it). "
                    "Otherwise give your final answer in plain text."
                    + extra_hint
                )
                continue

            if _looks_like_tool_schema(content):
                if _successful_results:
                    clean_results = [_strip_tool_prefix(r) for r in _successful_results]
                    content = clean_results[0] if len(clean_results) == 1 else "\n".join(f"- {r}" for r in clean_results)
                    if self.debug:
                        print(f"    using tool result as final answer: {content[:50]}...")
                elif not self.tools.all():
                    self.memory.add_assistant(content)
                    self.memory.add_user(
                        "Please answer in plain text only. "
                        "Do not output JSON or function call syntax."
                    )
                    retry = self.client.chat(
                        model=self.model,
                        messages=self.memory.to_messages(),
                        options=self.model_options,
                        think=False if self._needs_no_think else None,
                    )
                    content = retry.get("message", {}).get("content", "").strip() or content
                    self.memory._history.pop()
                    self.memory._history.pop()

            # ---- Hallucinated tool mention fallback ---- #
            if (
                self._native_tools
                and self.tools.all()
                and not _successful_results
                and not tool_calls_raw
                and content
            ):
                content_lower = content.lower()
                available_tools = [t.name for t in self.tools.all()]
                synthesized_tool = None
                synthesized_args = {}
                
                mentions_calculator = "calculator" in content_lower and "calculator" in available_tools
                mentions_shell = "shell" in content_lower and "shell" in available_tools
                
                if mentions_calculator or mentions_shell:
                    if self.debug:
                        print(f"\n  🔍 DEBUG: Model mentions tool but didn't call it, synthesizing...")
                    
                    if mentions_calculator:
                        expr = _extract_calc_expression(user_input)
                        if expr:
                            synthesized_tool = "calculator"
                            synthesized_args = {"expression": expr}
                            if self.debug:
                                print(f"    synthesized: calculator({expr})")
                    
                    if not synthesized_tool and mentions_shell:
                        q_lower = user_input.lower()
                        if "echo" in q_lower or "print" in q_lower:
                            echo_text = _extract_echo_text(user_input)
                            if echo_text:
                                synthesized_tool = "shell"
                                synthesized_args = {"command": f"echo {echo_text}"}
                                if self.debug:
                                    print(f"    synthesized: shell(echo {echo_text})")
                        elif "directory" in q_lower or "pwd" in q_lower or "folder" in q_lower:
                            synthesized_tool = "shell"
                            synthesized_args = {"command": PLATFORM_DIR_CMD}
                        elif "date" in q_lower or "time" in q_lower or "today" in q_lower:
                            if "python_repl" in available_tools:
                                synthesized_tool = "python_repl"
                                synthesized_args = {"code": "from datetime import datetime; print(datetime.now())"}
                    
                    if synthesized_tool and synthesized_args:
                        t_name = synthesized_tool
                        t_args = synthesized_args
                        
                        call_step = StepResult(
                            type="tool_call",
                            content=f"{t_name}({t_args})",
                            tool_name=t_name,
                            tool_args=t_args,
                            elapsed_ms=elapsed,
                        )
                        run.steps.append(call_step)
                        self._emit(call_step)
                        
                        result = self.tools.invoke(t_name, t_args)
                        result_str = str(result)
                        
                        result_step = StepResult(type="tool_result", content=result_str, tool_name=t_name)
                        run.steps.append(result_step)
                        self._emit(result_step)
                        
                        _successful_results.append(f"{t_name} → {result_str}")
                        _successful_tools.add(t_name)
                        
                        final_answer = self._synthesize(user_input, _successful_results)
                        final_step = StepResult(type="final", content=final_answer, elapsed_ms=elapsed)
                        run.steps.append(final_step)
                        self._emit(final_step)
                        run.final_answer = final_answer
                        break

            if _successful_results:
                clean_results = [_strip_tool_prefix(r) for r in _successful_results]
                fallback_text = clean_results[0] if len(clean_results) == 1 else "\n".join(f"- {r}" for r in clean_results)
            else:
                fallback_text = content
            
            if not self._native_tools and _successful_results:
                content_stripped = content.strip()
                if content_stripped.startswith("Thought:") and "Final Answer:" not in content_stripped:
                    try:
                        fallback_num = float(fallback_text)
                        if self.debug:
                            print(f"\n  🔍 DEBUG: ReAct thought without Final Answer, using numeric result: {fallback_num}")
                        content = fallback_text
                    except (ValueError, TypeError):
                        pass
            
            if self.debug:
                print(f"\n  🔍 DEBUG: Final answer processing")
                print(f"    content (before clean)={content!r}")
                print(f"    fallback_text={fallback_text!r}")
            
            content = self._clean_json_from_response(content, fallback_text)
            
            if self.debug:
                print(f"    content (after clean)={content!r}")

            final_step = StepResult(type="final", content=content, elapsed_ms=elapsed)
            run.steps.append(final_step)
            self._emit(final_step)
            run.final_answer = content
            self.memory.add_assistant(content)
            break

        else:
            run.success = False
            run.error = f"Exceeded max_steps ({self.max_steps})"
            if _successful_results:
                run.final_answer = self._synthesize(user_input, _successful_results)

        run.total_ms = (time.perf_counter() - t0) * 1000
        return run

    def _synthesize(self, user_input: str, results: list[str]) -> str:
        """
        Called when the model is stuck in a tool loop but we have good results.
        """
        if not results:
            return "I was unable to complete this task with the available tools."

        results_text = "\n".join(f"- {r}" for r in results)

        r_clean = _strip_tool_prefix(results[-1])
        if self.debug:
            print(f"    synthesize: checking if numeric: '{r_clean}'")
        try:
            num = float(r_clean)
            if self.debug:
                print(f"    synthesize: using numeric result directly: {num}")
            return r_clean
        except (ValueError, TypeError):
            if self.debug:
                print(f"    synthesize: not numeric: could not convert string to float: '{r_clean}'")
            pass
        
        for r in results:
            r_clean = _strip_tool_prefix(r)
            answer_patterns = (
                r_clean.startswith("Today is ") or
                r_clean.startswith("The current time is ") or
                r_clean.startswith("The answer is ") or
                r_clean.startswith("Result: ")
            )
            if answer_patterns and len(r_clean) < 200:
                if self.debug:
                    print(f"    synthesize: using direct result: {r_clean[:50]}...")
                return r_clean

        if self.debug:
            print(f"    synthesize: making LLM call to summarize {len(results)} results...")

        synthesis_messages = [
            {"role": "system", "content": self.memory.system_prompt},
            {"role": "user", "content": (
                f"You have already gathered the following information using your tools:\n"
                f"{results_text}\n\n"
                f"Please now answer the original question directly using these results. "
                f"Do not call any more tools. Original question: {user_input}"
            )},
        ]
        try:
            response = self.client.chat(
                model=self.model,
                messages=synthesis_messages,
                options=self.model_options,
                think=False if self._needs_no_think else None,
            )
            content = response.get("message", {}).get("content", "").strip()
            content = self._clean_json_from_response(content, results_text)
            return content or results_text
        except Exception:
            return results_text

    def _clean_json_from_response(self, content: str, fallback: str = "") -> str:
        """
        Remove JSON tool-call schemas from a response.
        """
        if not content:
            return fallback
        
        stripped = content.strip()
        if len(stripped) < 3:
            return fallback if fallback else content
        if stripped in ("```", "``", "`", "```json", "```python"):
            return fallback if fallback else content
        if stripped.startswith("```") and stripped.endswith("```") and len(stripped) < 10:
            return fallback if fallback else content
        
        if not _looks_like_tool_schema(content):
            return content
        
        try:
            cleaned = re.sub(r"```(?:json)?", "", content).strip().rstrip("`").strip()
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                obj = json.loads(cleaned[start:end + 1])
                if "name" in obj and ("arguments" in obj or "parameters" in obj):
                    return fallback if fallback else content
        except (json.JSONDecodeError, TypeError):
            pass
        
        return content

    def chat(self, user_input: str) -> str:
        """Convenience wrapper — returns just the final answer string."""
        return self.run(user_input).final_answer

    def reset(self):
        """Clear conversation history (preserves system prompt)."""
        self.memory.clear()

    # ------------------------------------------------------------------ #
    #  Streaming                                                           #
    # ------------------------------------------------------------------ #

    def stream(self, user_input: str) -> Iterator[str]:
        """
        Yield text tokens as they arrive (no tool use in streaming mode).
        """
        if self.tools.all() and self.debug:
            print(
                f"  ⚠ stream() called but {len(self.tools.all())} tool(s) are registered. "
                "Tools are not invoked in streaming mode — use agent.run() instead."
            )
        self.memory.add_user(user_input)
        chunks = self.client.chat(
            model=self.model,
            messages=self.memory.to_messages(),
            stream=True,
            options=self.model_options,
            think=False if self._needs_no_think else None,
        )
        full = ""
        for chunk in chunks:
            if isinstance(chunk, dict):
                token = chunk.get("message", {}).get("content", "")
            elif isinstance(chunk, str):
                token = chunk
            else:
                token = str(chunk) if chunk else ""
            full += token
            yield token
        self.memory.add_assistant(full)

    # ------------------------------------------------------------------ #
    #  Internal                                                            #
    # ------------------------------------------------------------------ #

    def _emit(self, step: StepResult):
        if self.on_step:
            self.on_step(step)