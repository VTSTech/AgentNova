"""
AgentNova R02.4 — Refactored Agent with Small Model Support

A cleaner implementation with separate handlers for each tool support level.
Includes robust handling for small models that:
- Hallucinate argument names
- Output JSON instead of ReAct format
- Get stuck in repetition loops
- Put code in wrong fields
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Literal

from .ollama_client import OllamaClient
from .memory import Memory
from .tools import ToolRegistry
from .model_family_config import get_family_config, get_no_tools_system_prompt


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
# TOOL ARGUMENT ALIASES
# ============================================================
# Small models often hallucinate argument names. This maps common
# hallucinations to the correct parameter names.

TOOL_ARG_ALIASES = {
    "calculator": {
        "a": "expression", "b": "expression", "x": "expression", "y": "expression",
        "num": "expression", "number": "expression", "value": "expression",
        "input": "expression", "formula": "expression", "math": "expression",
        "expr": "expression", "calc": "expression", "result": "expression",
        "base": "_combine_power", "exponent": "_combine_power", "power": "_combine_power",
        "n": "_combine_power", "p": "_combine_power", "exp": "_combine_power",
    },
    "python_repl": {
        "code": "code",
        "script": "code", "cmd": "code", "command": "code",
        "python": "code", "py": "code", "exec": "code", "execute": "code",
        "expression": "code", "expr": "code", "statement": "code",
        "program": "code", "source": "code", "input": "code",
    },
    "write_file": {
        "path": "path",
        "filepath": "path", "file_path": "path", "filename": "path",
        "file": "path", "dest": "path", "destination": "path",
        "output_path": "path", "outputfile": "path", "location": "path",
        "content": "content",
        "data": "content", "text": "content", "body": "content",
        "output": "content", "string": "content", "value": "content",
        "write": "content", "output_data": "content",
    },
    "read_file": {
        "path": "path",
        "filepath": "path", "file_path": "path", "filename": "path",
        "file": "path", "input": "path", "source": "path", "location": "path",
    },
    "shell": {
        "command": "command",
        "cmd": "command", "exec": "command", "shell_cmd": "command",
        "bash": "command", "script": "command", "instruction": "command",
        "run": "command", "execute": "command", "op": "command",
        "text": "command", "input": "command", "arg": "command",
        "args": "command", "str": "command", "value": "command",
    },
    "web_search": {
        "query": "query",
        "search": "query", "q": "query", "term": "query", "search_query": "query",
        "keywords": "query", "text": "query", "input": "query",
    },
}


# ============================================================
# COMPILED REGEX PATTERNS
# ============================================================

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
_PYTHON_CODE_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_REPETITION_RE = re.compile(r'(Final Answer:\s*[^\n]+)(\s*\1){2,}', re.IGNORECASE)


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
    """Synthesize a final answer from tool results."""
    if not results:
        return content
    
    numeric = _get_numeric_result(results)
    if numeric:
        return numeric
    
    # Return last result stripped of prefix
    return _strip_tool_prefix(results[-1])


def _detect_and_fix_repetition(text: str) -> str:
    """
    Detect and fix repetitive output from small models.
    
    Some models get stuck in loops repeating the same phrase:
        "Final Answer: 120\nFinal Answer: 120\nFinal Answer: 120..."
    """
    if not text:
        return text
    
    # Fix "Final Answer:" repetition specifically
    match = _REPETITION_RE.search(text)
    if match:
        text = _REPETITION_RE.sub(r'\1', text)
    
    # Also detect and fix any line repeated 3+ times at the end
    lines = text.split('\n')
    if len(lines) >= 3:
        last_line = lines[-1].strip()
        if last_line:
            repeat_count = 1
            for i in range(len(lines) - 2, -1, -1):
                if lines[i].strip() == last_line:
                    repeat_count += 1
                else:
                    break
            
            if repeat_count >= 3:
                text = '\n'.join(lines[:-repeat_count + 1])
    
    return text


def _sanitize_model_json(text: str) -> str:
    """
    Fix common JSON mistakes made by small models before parsing.
    
    1. Python bool/None literals to JSON equivalents
    2. Python string concatenation in values
    3. Trailing commas before } or ]
    """
    # Python booleans / None
    text = re.sub(r':\s*True\b', ': true', text)
    text = re.sub(r':\s*False\b', ': false', text)
    text = re.sub(r':\s*None\b', ': null', text)
    text = re.sub(r'\[\s*True\b', '[true', text)
    text = re.sub(r'\[\s*False\b', '[false', text)
    text = re.sub(r'\[\s*None\b', '[null', text)
    
    # Python string concatenation: "literal" + anything -> "literal"
    text = re.sub(r'("(?:[^"\\]|\\.)*")\s*\+\s*[^,\'"}\]\n]+', r'\1', text)
    
    # Trailing commas before } or ]
    text = re.sub(r',\s*([}\]])', r'\1', text)
    
    return text


def _looks_like_tool_schema_dump(text: str) -> bool:
    """Detect when a model dumps the entire tool schema as text."""
    if not text:
        return False
    
    dump_indicators = [
        '{"function <nil>',
        '"type":"function"',
        '"parameters":{"type":"object"',
        '[{"type":',
        '"required":',
        '"properties":',
        'Search the web using DuckDuckGo',
        'Evaluate a mathematical expression',
        'Execute Python code',
        '{object <nil>',
    ]
    
    text_lower = text.lower()
    matches = sum(1 for indicator in dump_indicators if indicator.lower() in text_lower)
    
    return matches >= 2


def _extract_tool_from_json(obj: dict, debug: bool = False) -> tuple[str | None, dict | None]:
    """Extract tool name and args from a parsed JSON object."""
    name = obj.get("name") or obj.get("function")
    args = obj.get("arguments") or obj.get("parameters") or obj.get("args") or {}
    
    # Handle bare argument objects: {"expression": "..."} without name wrapper
    if not name and isinstance(obj, dict):
        arg_to_tool = {
            "expression": "calculator",
            "command": "shell",
            "code": "python_repl",
            "path": "read_file",
            "content": "write_file",
            "query": "web_search",
            "url": "http_get",
        }
        for key in obj.keys():
            if key in arg_to_tool:
                name = arg_to_tool[key]
                args = obj
                break
    
    if not name or not isinstance(args, dict):
        return None, None
    
    return name, args


def _parse_json_tool_call(text: str, debug: bool = False) -> tuple[str | None, dict | None]:
    """
    Fallback for models that output tool calls as JSON text instead of ReAct format.
    
    Handles:
        ```json
        {"name": "calculator", "arguments": {"expression": "2+2"}}
        ```
    
    Also handles bare argument objects:
        ```json
        {"expression": "15 * 8"}
        ```
    """
    if _looks_like_tool_schema_dump(text):
        return None, None
    
    # Try to extract JSON from markdown code blocks
    code_block_pattern = re.compile(r'```(?:json)?[^\n]*\n(.*?)```', re.DOTALL)
    code_blocks = code_block_pattern.findall(text)
    
    for block in code_blocks:
        block = block.strip()
        if block.startswith('{'):
            json_str = _sanitize_model_json(block)
            try:
                obj = json.loads(json_str)
                result = _extract_tool_from_json(obj, debug)
                if result[0]:
                    return result
            except json.JSONDecodeError:
                continue
    
    # Fallback: find first JSON object
    start = text.find("{")
    if start == -1:
        return None, None
    
    depth = 0
    end = -1
    for i, ch in enumerate(text[start:], start):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end = i
                break
    
    if end == -1:
        return None, None
    
    json_str = _sanitize_model_json(text[start:end + 1])
    
    try:
        obj = json.loads(json_str)
    except json.JSONDecodeError:
        return None, None
    
    return _extract_tool_from_json(obj, debug)


def _extract_python_code(text: str) -> str | None:
    """Extract Python code from markdown code blocks."""
    match = _PYTHON_CODE_RE.search(text)
    if match:
        return match.group(1).strip()
    return None


def _normalize_args(args: dict, tool, tool_name: str = None) -> dict:
    """
    Normalize argument names using TOOL_ARG_ALIASES and type coercion.
    
    Small models often hallucinate argument keys. This function normalizes
    them using multiple strategies:
    1. Tool-specific alias mapping
    2. Exact match to real params
    3. Prefix/substring matching
    4. Type coercion (string -> int/float)
    """
    if not isinstance(args, dict):
        if args is None:
            return {}
        if isinstance(args, str):
            return {"input": args}
        return {}
    
    if tool is None:
        return args
    
    real_params = [p for p in tool.params]
    if not real_params:
        return args
    
    param_map = {p.name: p for p in real_params}
    normalized = {}
    power_parts = {}
    
    tool_aliases = TOOL_ARG_ALIASES.get(tool_name, {}) if tool_name else {}
    
    for key, val in args.items():
        key_lower = key.lower().replace("-", "_")
        target_param = None
        target_pname = None
        
        # Strategy 1: Tool-specific alias lookup
        if key_lower in tool_aliases:
            alias_target = tool_aliases[key_lower]
            if alias_target == "_combine_power":
                power_parts[key_lower] = val
                continue
            elif alias_target in param_map:
                target_param = param_map[alias_target]
                target_pname = alias_target
        
        # Strategy 2: Exact match
        if target_param is None and key in param_map:
            target_param = param_map[key]
            target_pname = key
        
        # Strategy 3: Prefix/substring matching
        if target_param is None:
            for p in real_params:
                if p.name in key_lower or key_lower.startswith(p.name):
                    target_param = p
                    target_pname = p.name
                    break
        
        if target_pname is None:
            target_pname = key
        
        # Type coercion
        if target_param and isinstance(val, str):
            if target_param.type in ("number", "float"):
                try:
                    val = float(val)
                except ValueError:
                    pass
            elif target_param.type == "integer":
                try:
                    val = int(val)
                except ValueError:
                    pass
        
        if target_pname not in normalized:
            normalized[target_pname] = val
    
    # Handle power operation combination
    if power_parts and "expression" in param_map:
        base = power_parts.get("base") or power_parts.get("value") or power_parts.get("x")
        exp = power_parts.get("exponent") or power_parts.get("power") or power_parts.get("n")
        
        if base is not None and exp is not None:
            normalized["expression"] = f"{base} ** {exp}"
        elif base is not None:
            normalized["expression"] = str(base)
    
    return normalized


def _synthesize_missing_args(tool_name: str, args: dict, user_input: str, prior_results: list[str], tools_registry) -> dict:
    """
    Try to fill in missing required arguments from context.
    Helps small models that call tools with incomplete arguments.
    """
    tool = tools_registry.get(tool_name) if tools_registry else None
    if tool is None:
        return args
    
    args = dict(args)
    required_params = {p.name for p in tool.params if p.required}
    missing = required_params - set(args.keys())
    
    if not missing:
        return args
    
    q_lower = user_input.lower()
    
    # Tool-specific synthesis
    if tool_name == "calculator" and "expression" in missing:
        numbers = re.findall(r'\d+\.?\d*', user_input)
        operators = re.findall(r'[+\-*/^]', user_input)
        
        if "sqrt" in q_lower or "square root" in q_lower:
            if numbers:
                args["expression"] = f"sqrt({numbers[-1]})"
        elif "power" in q_lower or "^" in user_input:
            if len(numbers) >= 2:
                args["expression"] = f"{numbers[0]} ** {numbers[1]}"
        elif "times" in q_lower or "multiply" in q_lower or "multiplied" in q_lower:
            if len(numbers) >= 2:
                args["expression"] = f"{numbers[0]} * {numbers[1]}"
        elif "divided" in q_lower or "divide" in q_lower:
            if len(numbers) >= 2:
                args["expression"] = f"{numbers[0]} / {numbers[1]}"
        elif "plus" in q_lower or "add" in q_lower or "sum" in q_lower:
            if len(numbers) >= 2:
                args["expression"] = f"{numbers[0]} + {numbers[1]}"
        elif "minus" in q_lower or "subtract" in q_lower:
            if len(numbers) >= 2:
                args["expression"] = f"{numbers[0]} - {numbers[1]}"
        elif numbers and operators:
            expr_parts = []
            for i, num in enumerate(numbers):
                expr_parts.append(num)
                if i < len(operators):
                    expr_parts.append(operators[i])
            args["expression"] = " ".join(expr_parts)
        elif numbers:
            args["expression"] = numbers[0]
    
    elif tool_name == "python_repl" and "code" in missing:
        if "date" in q_lower and "time" in q_lower:
            args["code"] = "from datetime import datetime\nprint(datetime.now().strftime('Today is %A, %B %d, %Y and the time is %I:%M %p.'))"
        elif "date" in q_lower:
            args["code"] = "from datetime import datetime\nprint(datetime.now().strftime('Today is %A, %B %d, %Y.'))"
        elif "time" in q_lower:
            args["code"] = "from datetime import datetime\nprint(datetime.now().strftime('The current time is %I:%M %p.'))"
    
    elif tool_name == "shell" and "command" in missing:
        if "directory" in q_lower or "folder" in q_lower:
            args["command"] = "pwd"
        elif "files" in q_lower and "list" in q_lower:
            args["command"] = "ls"
    
    return args


def _fuzzy_match_tool_name(hallucinated_name: str, tools_registry) -> str | None:
    """
    Match a hallucinated tool name to a real tool name.
    
    Examples:
        "calculate_expression" -> "calculator"
        "ls" -> "shell"
    """
    if tools_registry.get(hallucinated_name):
        return hallucinated_name
    
    real_names = [t.name for t in tools_registry.all()]
    lower_hallucinated = hallucinated_name.lower().replace("_", "")
    
    # Strategy 1: Substring match
    for real_name in real_names:
        lower_real = real_name.lower().replace("_", "")
        if lower_real in lower_hallucinated or lower_hallucinated in lower_real:
            return real_name
    
    # Strategy 2: Word mappings
    word_mappings = {
        "calculate": ["calculator", "python_repl"],
        "calc": ["calculator", "python_repl"],
        "math": ["calculator", "python_repl"],
        "compute": ["calculator", "python_repl"],
        "sqrt": ["calculator"],
        "power": ["calculator"],
        "python": ["python_repl"],
        "repl": ["python_repl"],
        "code": ["python_repl"],
        "date": ["python_repl", "shell"],
        "time": ["python_repl", "shell"],
        "shell": ["shell"],
        "bash": ["shell"],
        "ls": ["shell"],
        "dir": ["shell"],
        "cat": ["shell"],
        "echo": ["shell"],
        "pwd": ["shell"],
        "read": ["read_file"],
        "write": ["write_file"],
    }
    
    for keyword, tool_hints in word_mappings.items():
        if keyword in lower_hallucinated:
            for tool_hint in tool_hints:
                for real_name in real_names:
                    if tool_hint in real_name or real_name == tool_hint:
                        return real_name
    
    # Strategy 3: First 4 chars match
    for real_name in real_names:
        lower_real = real_name.lower()
        if len(lower_real) >= 4 and len(lower_hallucinated) >= 4:
            if lower_real[:4] == lower_hallucinated[:4]:
                return real_name
    
    return None


def _is_simple_query(text: str) -> bool:
    """Check if the query is simple enough for immediate synthesis."""
    lower = text.lower()
    simple_keywords = ["what is", "calculate", "compute", "sqrt", "date", "time"]
    return any(kw in lower for kw in simple_keywords) and len(text) < 60


# ============================================================
# REFACTORED AGENT CLASS
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
            thought_match = _THOUGHT_RE.search(content)
            thought = thought_match.group(1).strip() if thought_match else None
            
            # Try multiline action first, then same-line format
            action_match = _ACTION_RE.search(content)
            if not action_match:
                action_match = _ACTION_SAME_LINE_RE.search(content)
            
            t_name = action_match.group(1).strip() if action_match else None
            raw_args = action_match.group(2).strip() if action_match else None
            
            final_match = _FINAL_RE.search(content)
            final_answer = final_match.group(1).strip() if final_match else None
            
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