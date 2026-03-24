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
        think: bool | None = None,
        **kwargs,
    ) -> dict:
        """Generate a response from Ollama.
        
        Args:
            model: Model name
            messages: Chat messages
            tools: List of Tool objects for native tool calling
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            think: For thinking models (qwen3, deepseek-r1): None=auto, False=disable thinking
            **kwargs: Additional options passed to Ollama
        """
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

        # Add think parameter for thinking models (qwen3, deepseek-r1, etc.)
        if think is not None:
            body["think"] = think

        # Add any extra options
        for key, value in kwargs.items():
            if key == "stop":
                body["options"]["stop"] = value if isinstance(value, list) else [value]
            elif key not in ("model", "messages", "tools", "stream", "think"):
                body["options"][key] = value

        # Debug output for request
        if os.environ.get("AGENTNOVA_DEBUG"):
            print(f"  [Ollama] Request: tools={len(tools) if tools else 0}, think={think}")

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
        # IMPORTANT: Preserve the 'id' field - it's required for tool result messages
        parsed_tool_calls = []
        for tc in tool_calls:
            func = tc.get("function", {})
            parsed_tool_calls.append({
                "id": tc.get("id", ""),  # Preserve for tool result correlation
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

        Detection logic (from main branch):
        1. HTTP 400 "does not support tools" → none (Ollama's explicit rejection)
        2. Native tool_calls in API response, calling correct function → native
        3. No tool_calls but content has JSON tool call pattern → react (text-based)
        4. No tool_calls, no tool-like JSON, but API accepted tools → react

        Key insight: "native" requires ACTUAL native tool_calls structure in API response.
        Models that output JSON as text are "react", not "native".

        Args:
            model: Model name
            family: Optional family hint (unused, kept for API compatibility)
            force_test: If True, make a test API call to determine support

        Returns:
            ToolSupportLevel (NATIVE, REACT, NONE, or UNTESTED if force_test=False)
        """
        if not force_test:
            # Without force_test, we don't know - return UNTESTED
            # The caller should use cache or show "untested"
            return ToolSupportLevel.UNTESTED

        # Test tool: Weather (simple, commonly supported)
        test_tool = Tool(
            name="get_weather",
            description="Get the current weather for a location",
            params=[ToolParam(
                name="location",
                type="string",
                description="The city and country, e.g., 'Paris, France'"
            )],
        )

        try:
            # Send request with tools but NO system prompt override
            # Use model's default Modelfile system prompt
            response = self.generate(
                model=model,
                messages=[{
                    "role": "user",
                    "content": "What's the weather like in Tokyo?"
                }],
                tools=[test_tool],
                max_tokens=100,
            )

            message = response.get("message", response)
            tool_calls = message.get("tool_calls", [])
            content = message.get("content", "")

            # 2. Check for NATIVE tool_calls in API response structure
            # This is the ONLY path to "native" classification
            # Note: generate() already parses tool_calls into flat format: {"name": ..., "arguments": ...}
            if tool_calls:
                for tc in tool_calls:
                    # After parsing by generate(), structure is flat
                    func_name = tc.get("name", "")
                    args = tc.get("arguments", {})
                    
                    # Verify it's calling our tool (not hallucinating a different one)
                    if func_name == "get_weather":
                        # Check for reasonable arguments
                        if isinstance(args, dict) and ("location" in args or "city" in args or len(args) > 0):
                            return ToolSupportLevel.NATIVE
                    # Native tool_calls exist but wrong function - still native capability
                    # (model might be confused but HAS native support)
                    elif func_name:  # Any function name = native structure
                        return ToolSupportLevel.NATIVE

            # 3. Check for text-based tool calls in content
            # Models that output JSON like {"name": "get_weather", ...} as TEXT
            if self._contains_text_tool_call(content):
                return ToolSupportLevel.REACT

            # 4. API succeeded, no explicit rejection, no native tool_calls
            # Model accepted tools parameter but didn't use native calling
            # This is the "react" case - can still parse text-based tool calls
            return ToolSupportLevel.REACT

        except Exception as e:
            error_str = str(e)

            # 1. Check for explicit "does not support tools" rejection
            if "does not support tools" in error_str.lower():
                return ToolSupportLevel.NONE

            # Other HTTP errors or connection issues
            return ToolSupportLevel.REACT

        finally:
            # Always unload the model after testing to free memory
            try:
                self.unload_model(model)
            except Exception:
                pass  # Ignore errors during cleanup

    def _contains_text_tool_call(self, content: str) -> bool:
        """
        Check if the response content contains a JSON tool call pattern.
        Models that output tool calls as TEXT (not native API) show this pattern.

        Examples:
          {"name": "get_weather", "arguments": {"location": "Tokyo"}}
          {"tool": "calculator", "arguments": {"expression": "2+2"}}
        """
        if not content:
            return False

        import re

        # Remove markdown code blocks if present
        cleaned = re.sub(r"```(?:json)?", "", content).strip().rstrip("`").strip()

        # Look for JSON object pattern
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            return False

        try:
            import json
            obj = json.loads(cleaned[start:end + 1])

            # Check for tool call patterns
            if not isinstance(obj, dict):
                return False

            # Pattern 1: {"name": "...", "arguments": {...}}
            if "name" in obj and ("arguments" in obj or "parameters" in obj):
                return True

            # Pattern 2: {"tool": "...", "arguments": {...}}
            if "tool" in obj and "arguments" in obj:
                return True

            return False

        except json.JSONDecodeError:
            return False

    def unload_model(self, model: str) -> dict:
        """
        Unload a model from memory (stop keeping it warm).
        Equivalent to: ollama stop <model>

        Args:
            model: Model name to unload

        Returns:
            Response dict from server
        """
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/api/generate"
        body = {"model": model, "keep_alive": 0}

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
            return {"status": "not_running"}

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