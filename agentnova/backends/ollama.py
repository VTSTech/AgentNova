"""
⚛️ AgentNova — Ollama Backend
Backend implementation for Ollama inference engine.

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Generator, Optional

from .base import BaseBackend, BackendConfig
from ..core.types import BackendType, ToolSupportLevel
from ..core.models import Tool, ToolParam
from ..config import OLLAMA_BASE_URL


class OllamaBackend(BaseBackend):
    """
    Backend for Ollama inference engine.

    Ollama is a popular local LLM server that supports
    many open-source models with native tool calling.
    """

    def __init__(
        self,
        base_url: str | None = None,
        host: str | None = None,
        port: int | None = None,
        config: BackendConfig | None = None,
    ):
        # Determine base URL - priority: base_url > host/port > env > default
        if base_url:
            self._base_url = base_url.rstrip("/")
        elif host and port:
            self._base_url = f"http://{host}:{port}"
        else:
            self._base_url = OLLAMA_BASE_URL.rstrip("/")

        if config:
            super().__init__(config)
        else:
            super().__init__(BackendConfig())

    @property
    def backend_type(self) -> BackendType:
        return BackendType.OLLAMA

    @property
    def base_url(self) -> str:
        return self._base_url

    def generate(
        self,
        model: str,
        messages: list[dict],
        tools: list[Tool] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> dict:
        """Generate a response from Ollama."""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/api/chat"

        # Build request body
        body = {
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": "1m",  # Keep model loaded briefly but clear KV cache between requests
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        # Add tools if provided
        if tools:
            body["tools"] = [t.to_json_schema() for t in tools]

        # Add any extra options
        for key, value in kwargs.items():
            if key == "stop":
                body["options"]["stop"] = value if isinstance(value, list) else [value]
            elif key not in ("model", "messages", "tools", "stream"):
                body["options"][key] = value

        # Make request
        start_time = time.time()

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=self.config.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            raise RuntimeError(f"Ollama HTTP error {e.code}: {error_body}")

        except urllib.error.URLError as e:
            raise RuntimeError(f"Ollama connection error: {e.reason}")

        latency_ms = (time.time() - start_time) * 1000

        # Parse response
        message = result.get("message", {})
        content = message.get("content", "")
        tool_calls = message.get("tool_calls", [])

        # Debug output
        if os.environ.get("AGENTNOVA_DEBUG"):
            print(f"  [Ollama] Raw result keys: {list(result.keys())}")
            print(f"  [Ollama] Message keys: {list(message.keys())}")
            print(f"  [Ollama] Content: {content[:100] if content else '(empty)'}")
            print(f"  [Ollama] Tool calls: {tool_calls}")

        # Parse tool calls from Ollama format
        parsed_tool_calls = []
        for tc in tool_calls:
            func = tc.get("function", {})
            parsed_tool_calls.append({
                "name": func.get("name", ""),
                "arguments": func.get("arguments", {}),
            })

        return {
            "content": content,
            "tool_calls": parsed_tool_calls,
            "usage": {
                "prompt_tokens": result.get("prompt_eval_count", 0),
                "completion_tokens": result.get("eval_count", 0),
                "total_tokens": result.get("prompt_eval_count", 0) + result.get("eval_count", 0),
            },
            "latency_ms": latency_ms,
            "raw": result,
        }

    def generate_stream(
        self,
        model: str,
        messages: list[dict],
        tools: list[Tool] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> Generator[str, None, None]:
        """Stream generated text from Ollama."""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/api/chat"

        # Build request body
        body = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        if tools:
            body["tools"] = [t.to_json_schema() for t in tools]

        for key, value in kwargs.items():
            if key not in ("model", "messages", "tools", "stream"):
                body["options"][key] = value

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=self.config.timeout) as response:
                for line in response:
                    if not line:
                        continue

                    try:
                        chunk = json.loads(line.decode("utf-8"))
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content

                        if chunk.get("done"):
                            break

                    except json.JSONDecodeError:
                        continue

        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Ollama HTTP error {e.code}")

        except urllib.error.URLError as e:
            raise RuntimeError(f"Ollama connection error: {e.reason}")

    def get_model_info(self, model: str) -> dict | None:
        """
        Get detailed model information from Ollama.
        
        Uses /api/show endpoint which returns:
        - modelfile
        - parameters (including num_ctx)
        - template
        - details (family, parameter count, etc.)
        """
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/api/show"

        body = {"name": model}

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))

        except (urllib.error.HTTPError, urllib.error.URLError):
            return None

    # Known defaults by model family
    FAMILY_CONTEXT_DEFAULTS = {
        "qwen2": 32768,
        "qwen2.5": 32768,
        "qwen3": 32768,
        "llama3": 8192,
        "llama3.1": 131072,
        "llama3.2": 131072,
        "llama3.3": 131072,
        "mistral": 32768,
        "mixtral": 32768,
        "gemma": 8192,
        "gemma2": 8192,
        "gemma3": 8192,
        "phi3": 128000,
        "granite": 8192,
        "granitemoe": 8192,
        "smollm": 4096,
    }

    @classmethod
    def get_context_by_family(cls, family: str) -> int | None:
        """Get default context size for a model family."""
        if not family:
            return None
        family_lower = family.lower()
        for fam, ctx in cls.FAMILY_CONTEXT_DEFAULTS.items():
            if fam in family_lower:
                return ctx
        return None

    def get_model_context_size(self, model: str, family: str | None = None) -> int:
        """
        Get the context window size for a model.
        
        Args:
            model: Model name
            family: Optional family name (uses default if provided)
        
        Returns:
            Context window size in tokens
        """
        # Fast path: use family default
        if family:
            ctx = self.get_context_by_family(family)
            if ctx:
                return ctx
        
        # Slow path: get from API
        info = self.get_model_info(model)
        
        if not info:
            return 4096  # Default context size
        
        # Check parameters string for num_ctx
        parameters = info.get("parameters", "")
        if parameters:
            # Parse num_ctx from parameters string like "num_ctx 8192\nnum_gpu 1"
            for line in parameters.split("\n"):
                if line.strip().startswith("num_ctx"):
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            return int(parts[1])
                        except ValueError:
                            pass
        
        # Check model_info for context_length (some versions expose it here)
        model_info = info.get("model_info", {})
        if "context_length" in model_info:
            return model_info["context_length"]
        
        # Check details for family
        details = info.get("details", {})
        api_family = details.get("family", "").lower()
        
        ctx = self.get_context_by_family(api_family)
        if ctx:
            return ctx
        
        return 4096  # Default fallback

    def list_models(self) -> list[dict]:
        """List available models from Ollama."""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/api/tags"

        try:
            req = urllib.request.Request(url, method="GET")

            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))

            return result.get("models", [])

        except (urllib.error.HTTPError, urllib.error.URLError):
            return []

    # No family-based assumptions - tool support depends on the model's template
    # Each model must be tested individually. Use --tool-support to test.

    def test_tool_support(self, model: str, family: str | None = None, force_test: bool = False) -> ToolSupportLevel:
        """
        Test model's tool support capability.

        IMPORTANT: Tool support is NOT determined by family. It depends on the
        model's template, which can vary within the same family. Each model
        must be tested individually.

        Args:
            model: Model name
            family: Optional family hint (used to check family config for known no-tool models)
            force_test: If True, make a test API call to determine support

        Returns:
            ToolSupportLevel (NATIVE, REACT, NONE, or UNTESTED if force_test=False)
        """
        if not force_test:
            # Without force_test, we don't know - return UNTESTED
            # The caller should use cache or show "untested"
            return ToolSupportLevel.UNTESTED

        # Check family config first for models known to not support tools
        if family:
            from ..core.model_family_config import get_family_config
            config = get_family_config(family)
            if config.tool_format == "none" or not config.supports_native_tools:
                # Family is known to not support tools - verify with test
                # but be prepared to return NONE instead of REACT
                pass

        # Make a real test call with tools
        # IMPORTANT: Test tool must have actual parameters like real tools do!
        # Models behave differently with parameterless tools vs tools with required params.
        try:
            test_tool = Tool(
                name="get_weather",
                description="Get the current weather for a location",
                params=[ToolParam(
                    name="location",
                    type="string",
                    description="The city and country, e.g., 'Paris, France'"
                )],
            )

            response = self.generate(
                model=model,
                messages=[{
                    "role": "user",
                    "content": "What's the weather like in Tokyo?"
                }],
                tools=[test_tool],
                max_tokens=100,
            )

            # Check if model made a tool call (native support)
            if response.get("tool_calls"):
                return ToolSupportLevel.NATIVE

            # Model responded but didn't use tool API
            # Check if family is known to not support tools
            if family:
                from ..core.model_family_config import get_family_config
                config = get_family_config(family)
                if config.tool_format == "none" or not config.supports_native_tools:
                    # Family is known to not support tools - return NONE
                    return ToolSupportLevel.NONE

            # Default to ReAct for unknown families
            return ToolSupportLevel.REACT

        except Exception as e:
            # API error - check family config for fallback
            if family:
                from ..core.model_family_config import get_family_config
                config = get_family_config(family)
                if config.tool_format == "none" or not config.supports_native_tools:
                    return ToolSupportLevel.NONE
            return ToolSupportLevel.REACT

    def pull_model(self, model: str, stream: bool = False) -> dict | Generator:
        """Pull a model from Ollama registry."""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/api/pull"

        body = {
            "name": model,
            "stream": stream,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=300) as response:
            if stream:
                for line in response:
                    yield json.loads(line.decode("utf-8"))
            else:
                return json.loads(response.read().decode("utf-8"))

    def __repr__(self) -> str:
        return f"OllamaBackend(url={self.base_url})"
