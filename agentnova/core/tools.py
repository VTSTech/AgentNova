"""
⚛️ AgentNova R04 — Tool System
Decorator-based tool registry that auto-generates Ollama-compatible JSON schemas
from Python type hints and docstrings.

Features:
  • Auto-generation of tool schemas from type hints
  • Enhanced fuzzy argument matching for small models
  • Helpful error messages with usage examples
  • Support for argument aliases and normalization

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

import inspect
import json
from typing import Any, Callable, get_type_hints
from dataclasses import dataclass, field


# ------------------------------------------------------------------ #
#  Type → JSON Schema mapping                                          #
# ------------------------------------------------------------------ #

_PY_TO_JSON = {
    int: "integer",
    float: "number",
    str: "string",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _py_type_to_json(t) -> str:
    origin = getattr(t, "__origin__", None)
    if origin is list:
        return "array"
    if origin is dict:
        return "object"
    return _PY_TO_JSON.get(t, "string")


# ------------------------------------------------------------------ #
#  Tool descriptor                                                     #
# ------------------------------------------------------------------ #

@dataclass
class ToolParam:
    name: str
    type: str
    description: str
    required: bool = True
    enum: list | None = None


@dataclass
class Tool:
    name: str
    description: str
    fn: Callable
    params: list[ToolParam] = field(default_factory=list)

    def to_ollama_schema(self) -> dict:
        """Return the tool definition dict Ollama expects."""
        properties = {}
        required = []
        for p in self.params:
            prop: dict[str, Any] = {"type": p.type, "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            properties[p.name] = prop
            if p.required:
                required.append(p.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def __call__(self, **kwargs) -> Any:
        return self.fn(**kwargs)


# ------------------------------------------------------------------ #
#  Registry                                                            #
# ------------------------------------------------------------------ #

class ToolRegistry:
    """
    Central store for all tools.  Agents receive a view into this registry.

    Usage:
        registry = ToolRegistry()

        @registry.tool(description="Add two numbers")
        def add(a: int, b: int) -> int:
            '''Add a and b together.'''
            return a + b
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    # ---- registration ------------------------------------------------ #

    def tool(
        self,
        description: str | None = None,
        name: str | None = None,
        param_descriptions: dict[str, str] | None = None,
    ):
        """Decorator to register a function as a tool."""

        def decorator(fn: Callable) -> Callable:
            tool_name = name or fn.__name__
            tool_desc = description or (inspect.getdoc(fn) or "").split("\n")[0]
            param_descs = param_descriptions or {}

            hints = get_type_hints(fn)
            sig = inspect.signature(fn)

            params = []
            for pname, param in sig.parameters.items():
                if pname == "return":
                    continue
                py_type = hints.get(pname, str)
                json_type = _py_type_to_json(py_type)
                has_default = param.default is not inspect.Parameter.empty
                params.append(
                    ToolParam(
                        name=pname,
                        type=json_type,
                        description=param_descs.get(pname, pname.replace("_", " ")),
                        required=not has_default,
                    )
                )

            t = Tool(name=tool_name, description=tool_desc, fn=fn, params=params)
            self._tools[tool_name] = t
            return fn

        return decorator

    def register(self, tool: Tool):
        """Manually register a pre-built Tool object."""
        self._tools[tool.name] = tool

    # ---- access ------------------------------------------------------ #

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def schemas(self) -> list[dict]:
        return [t.to_ollama_schema() for t in self._tools.values()]

    def invoke(self, name: str, args: dict) -> Any:
        tool = self.get(name)
        if tool is None:
            raise KeyError(f"Tool '{name}' not found in registry.")
        try:
            # Filter args to only include valid parameters for this tool
            valid_params = {p.name for p in tool.params}
            filtered_args = {k: v for k, v in args.items() if k in valid_params}
            dropped = set(args) - valid_params
            
            # Fuzzy argument name matching for small models
            if dropped and len(filtered_args) < len(valid_params):
                fuzzy_mappings = self._fuzzy_match_args(dropped, valid_params, name)
                for wrong_name, correct_name in fuzzy_mappings.items():
                    filtered_args[correct_name] = args[wrong_name]
                    dropped.discard(wrong_name)
            
            if dropped:
                import warnings
                warnings.warn(
                    f"Tool '{name}' received unknown argument(s) {dropped!r} — they will be ignored.",
                    stacklevel=2,
                )
            return tool(**filtered_args)
        except Exception as e:
            return f"[Tool error] {type(e).__name__}: {e}"
    
    def _fuzzy_match_args(self, wrong_names: set, valid_names: set, tool_name: str) -> dict:
        """Map incorrectly named args to correct ones using common patterns."""
        mappings = {}
        
        # Common argument name aliases/mappings - expanded for small models
        arg_aliases = {
            # path variants
            "filepath": "path", "file_path": "path", "filename": "path", "file": "path",
            "output_path": "path", "outputfile": "path", "dest": "path", "destination": "path",
            "location": "path", "source": "path", "input": "path",
            # content variants
            "data": "content", "text": "content", "body": "content", "output": "content",
            "string": "content", "value": "content", "input": "content", 
            "result": "content", "write": "content", "output_data": "content",
            # query variants
            "search": "query", "q": "query", "term": "query", "search_query": "query",
            "keywords": "query", "text": "query",
            # command variants
            "cmd": "command", "shell": "command", "exec": "command",
            "bash": "command", "script": "command", "run": "command",
            "instruction": "command", "execute": "command", "op": "command",
            # expression variants (for calculator)
            "expr": "expression", "formula": "expression", "math": "expression",
            "calc": "expression", "input": "expression", "value": "expression",
            "a": "expression", "b": "expression", "x": "expression", "y": "expression",
            "num": "expression", "number": "expression",
            # code variants (for python_repl)
            "script": "code", "python": "code", "py": "code",
            "exec": "code", "execute": "code", "program": "code", "source": "code",
            "statement": "code",
            # url variants
            "uri": "url", "link": "url", "endpoint": "url",
            # key variants  
            "name": "key", "id": "key", "identifier": "key",
            # timeout variants
            "time": "timeout", "seconds": "timeout", "max_time": "timeout",
            # city variants
            "location": "city", "place": "city", "town": "city",
            "where": "city", "area": "city", "region": "city",
            # currency variants
            "from": "from_currency", "to": "to_currency",
            "source_currency": "from_currency", "target_currency": "to_currency",
            "money": "amount", "price": "amount",
        }
        
        for wrong in wrong_names:
            wrong_lower = wrong.lower().replace("-", "_")
            
            # Direct alias match
            if wrong_lower in arg_aliases:
                target = arg_aliases[wrong_lower]
                if target in valid_names:
                    mappings[wrong] = target
                    continue
            
            # Substring match (e.g., "filePath" contains "path")
            for valid in valid_names:
                if valid in wrong_lower or wrong_lower in valid:
                    mappings[wrong] = valid
                    break
            
            # Handle tool_* patterns (e.g., "tool_args" -> look for first required param)
            if wrong_lower.startswith("tool_") or wrong_lower == "args":
                # Find first required param that's not yet mapped
                for p in self.get(tool_name).params:
                    if p.required and p.name not in mappings.values():
                        mappings[wrong] = p.name
                        break
        
        return mappings

    def subset(self, names: list[str]) -> "ToolRegistry":
        """Return a new registry containing only the named tools."""
        sub = ToolRegistry()
        for name in names:
            if name in self._tools:
                sub._tools[name] = self._tools[name]
        return sub

    def __repr__(self):
        return f"ToolRegistry({list(self._tools.keys())})"