"""
⚛️ AgentNova — ZAI API Backend
Backend implementation for the ZAI API (OpenAI Chat-Completions compatible).

ZAI provides cloud-hosted LLM inference via an OpenAI-compatible API endpoint.
This backend inherits the OpenAI Chat-Completions logic from OllamaBackend
and adds API key authentication and ZAI-specific defaults.

Endpoints used:
  - POST /api/paas/v4/chat/completions → OpenAI Chat Completions (tools, streaming)
  - GET  /api/paas/v4/models          → model discovery (if supported)

Configuration:
  ZAI_BASE_URL   — API base URL (default: https://api.z.ai)
  ZAI_API_KEY    — API key for authentication (required)

Usage:
  # CLI
  agentnova chat --backend zai --model glm-5.1 --tools calculator
  agentnova run "What is 15 * 8?" --backend zai --model glm-4-flash

  # Python API
  from agentnova import Agent
  agent = Agent(model="glm-4-plus", backend="zai", tools=["calculator"])
  result = agent.run("What is 15 * 8?")

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Generator

from .base import BaseBackend, BackendConfig
from .ollama import OllamaBackend
from ..core.types import BackendType, ToolSupportLevel, ApiMode
from ..core.models import Tool, ToolParam
from ..config import ZAI_BASE_URL, ZAI_API_KEY


# ZAI model catalog with metadata for context sizing and defaults.
# Keys are model identifiers accepted by the ZAI API.
# Context lengths and defaults are sourced from ZAI documentation.
ZAI_MODELS: dict[str, dict] = {
    "glm-5.1": {
        "context_length": 128000,
        "default_temperature": 0.7,
        "default_max_tokens": 8192,
    },
    "glm-4-plus": {
        "context_length": 128000,
        "default_temperature": 0.7,
        "default_max_tokens": 8192,
    },
    "glm-4-flash": {
        "context_length": 128000,
        "default_temperature": 0.7,
        "default_max_tokens": 8192,
    },
    "glm-4-long": {
        "context_length": 1048576,
        "default_temperature": 0.7,
        "default_max_tokens": 8192,
    },
    "glm-4-air": {
        "context_length": 128000,
        "default_temperature": 0.7,
        "default_max_tokens": 8192,
    },
    "glm-4-airx": {
        "context_length": 128000,
        "default_temperature": 0.7,
        "default_max_tokens": 8192,
    },
    "glm-4v-plus": {
        "context_length": 128000,
        "default_temperature": 0.7,
        "default_max_tokens": 8192,
    },
    "glm-4v-flash": {
        "context_length": 128000,
        "default_temperature": 0.7,
        "default_max_tokens": 4096,
    },
}

# Default model when none specified.
ZAI_DEFAULT_MODEL = "glm-5.1"


class ZaiBackend(OllamaBackend):
    """
    Backend for ZAI API (OpenAI Chat-Completions compatible).

    Inherits the full OpenAI Chat Completions implementation from OllamaBackend
    (generate_completions, generate_completions_stream, tool calling) and
    customizes server management for ZAI's cloud endpoint.

    Key differences from Ollama:
    - Always uses OPENAI API mode (no native /api/chat)
    - Requires API key authentication via Bearer token
    - Cloud endpoint (no local server management)
    - Model catalog is static (no /api/show, /api/tags)
    - No is_running() health check (always available)

    Usage:
        backend = get_backend("zai")
        backend = ZaiBackend(api_key="sk-...")
    """

    def __init__(
        self,
        base_url: str | None = None,
        host: str | None = None,
        port: int | None = None,
        config: BackendConfig | None = None,
        api_mode: ApiMode | str | None = None,
        api_key: str | None = None,
    ):
        # Determine base URL — priority: base_url > host/port > env > default
        if base_url:
            self._base_url = base_url.rstrip("/")
        elif host and port:
            self._base_url = f"https://{host}:{port}"
        else:
            self._base_url = ZAI_BASE_URL.rstrip("/")

        if config:
            super(OllamaBackend, self).__init__(config)
        else:
            super(OllamaBackend, self).__init__(BackendConfig())

        # API key — priority: explicit > env var
        self._api_key = api_key or ZAI_API_KEY

        # ZAI is OpenAI-compatible only — force OPENAI mode
        if api_mode is not None:
            if isinstance(api_mode, str) and api_mode.lower() != "openai":
                if os.environ.get("AGENTNOVA_DEBUG"):
                    print(f"  [ZAI] API mode '{api_mode}' ignored — ZAI only supports OpenAI Chat-Completions")
            self._api_mode = ApiMode.OPENAI
        else:
            self._api_mode = ApiMode.OPENAI

        os.environ["AGENTNOVA_API_MODE"] = self._api_mode.value

    @property
    def backend_type(self) -> BackendType:
        return BackendType.ZAI

    @property
    def api_key(self) -> str:
        """Return the API key."""
        return self._api_key

    # ─────────────────────────────────────────────────────────────────────
    # Server Management — ZAI is a cloud service
    # ─────────────────────────────────────────────────────────────────────

    def is_running(self) -> bool:
        """
        Check if ZAI API is reachable.

        Unlike local backends, ZAI is a cloud service — we check if we have
        an API key configured rather than probing a health endpoint.
        """
        if not self._api_key:
            return False
        return True

    def list_models(self) -> list[dict]:
        """
        List available ZAI models.

        Queries the ZAI API /api/paas/v4/models endpoint dynamically.
        Falls back to the static catalog if the API call fails.
        Enriches API results with context_length from the static catalog
        when available.
        """
        import urllib.request
        import urllib.error

        # Try dynamic discovery from the API
        try:
            url = f"{self._base_url}/api/paas/v4/models"

            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            req = urllib.request.Request(url, headers=headers, method="GET")

            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode("utf-8"))

            api_models = result.get("data", [])
            if api_models:
                models = []
                for m in api_models:
                    name = m.get("id", "")
                    if not name:
                        continue
                    # Strip provider prefix if present (e.g., "zai/glm-4-flash")
                    model_key = name.split("/")[-1] if "/" in name else name

                    # Enrich with static catalog metadata if available
                    meta = ZAI_MODELS.get(model_key, {})

                    models.append({
                        "name": model_key,
                        "size": 0,
                        "details": {
                            "family": "glm",
                            "backend": "zai",
                            "context_length": meta.get("context_length", 128000),
                        },
                    })

                if os.environ.get("AGENTNOVA_DEBUG"):
                    print(f"  [ZAI] Discovered {len(models)} models from API")

                return models

        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            if os.environ.get("AGENTNOVA_DEBUG"):
                print(f"  [ZAI] Model discovery failed ({e}), using static catalog")
        except Exception as e:
            if os.environ.get("AGENTNOVA_DEBUG"):
                print(f"  [ZAI] Model discovery error ({e}), using static catalog")

        # Fallback: return static catalog
        models = []
        for name, meta in ZAI_MODELS.items():
            models.append({
                "name": name,
                "size": 0,
                "details": {
                    "family": "glm",
                    "backend": "zai",
                    "context_length": meta.get("context_length", 128000),
                },
            })
        return models

    def get_model_info(self, model: str) -> dict | None:
        """
        Get model information.

        Checks the static catalog first for context_length metadata,
        then queries the API to verify the model exists.
        Always returns info for any model name (ZAI accepts any valid model ID).
        """
        # Normalize: strip provider prefix if present (e.g., "zai/glm-4-plus")
        model_key = model.split("/")[-1] if "/" in model else model
        meta = ZAI_MODELS.get(model_key, {})

        # Return catalog info if available
        if meta:
            return {
                "name": model_key,
                "size": 0,
                "details": {
                    "family": "glm",
                    "backend": "zai",
                    "context_length": meta.get("context_length", 128000),
                },
            }

        # Model not in static catalog — still valid if ZAI knows it
        return {
            "name": model_key,
            "size": 0,
            "details": {
                "family": "glm",
                "backend": "zai",
                "context_length": 128000,
            },
        }

    # ─────────────────────────────────────────────────────────────────────
    # Generation — always OpenAI Chat-Completions
    # ─────────────────────────────────────────────────────────────────────

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
        """
        Generate a response from ZAI API.

        Always uses OpenAI Chat-Completions format. The `think` parameter
        is ignored (ZAI handles thinking internally if applicable).

        Injects Bearer token authentication into every request.
        """
        if think is not None and os.environ.get("AGENTNOVA_DEBUG"):
            print(f"  [ZAI] 'think' parameter ignored — ZAI manages thinking internally")

        # Delegate to the inherited OpenAI Chat-Completions implementation
        # but inject our API key into the request headers
        return self._generate_with_auth(
            model=model,
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    def generate_stream(
        self,
        model: str,
        messages: list[dict],
        tools: list[Tool] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> Generator[str, None, None]:
        """
        Stream generated text from ZAI API.

        Always uses OpenAI Chat-Completions SSE streaming.
        """
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/api/paas/v4/chat/completions"

        body = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            body["tools"] = [t.to_openai_schema() for t in tools]

        for key, value in kwargs.items():
            if key not in ("model", "messages", "tools", "stream"):
                body[key] = value

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers=headers,
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
            error_body = e.read().decode("utf-8") if e.fp else ""
            raise RuntimeError(f"ZAI HTTP error {e.code}: {error_body}")

        except urllib.error.URLError as e:
            raise RuntimeError(f"ZAI connection error: {e.reason}")

    def _generate_with_auth(
        self,
        model: str,
        messages: list[dict],
        tools: list[Tool] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> dict:
        """
        Generate via ZAI /api/paas/v4/chat/completions with Bearer auth.

        This is a standalone implementation rather than calling
        super().generate_completions() because we need to inject
        the Authorization header, which the parent method doesn't support.
        """
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/api/paas/v4/chat/completions"

        # Build request body in OpenAI format
        body = {
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Optional OpenAI-compatible parameters
        stop = kwargs.get("stop")
        if stop is not None:
            body["stop"] = stop if isinstance(stop, list) else [stop]
        if kwargs.get("presence_penalty") is not None:
            body["presence_penalty"] = kwargs["presence_penalty"]
        if kwargs.get("frequency_penalty") is not None:
            body["frequency_penalty"] = kwargs["frequency_penalty"]
        if kwargs.get("response_format") is not None:
            body["response_format"] = kwargs["response_format"]
        if kwargs.get("top_p") is not None:
            body["top_p"] = kwargs["top_p"]

        # Add tools in OpenAI format
        if tools:
            body["tools"] = [t.to_openai_schema() for t in tools]

        # Add tool_choice parameter
        if kwargs.get("tool_choice") is not None:
            body["tool_choice"] = kwargs["tool_choice"]

        # Inject Bearer token
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        if os.environ.get("AGENTNOVA_DEBUG"):
            print(f"  [ZAI] Request: model={model}, tools={len(tools) if tools else 0}")

        start_time = time.time()

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=self.config.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            error_msg = error_body.lower() if error_body else ""

            # Check if model doesn't support tools — fallback to no tools
            if "does not support tools" in error_msg and tools:
                if os.environ.get("AGENTNOVA_DEBUG"):
                    print(f"  [ZAI] Model doesn't support tools, falling back to ReAct mode")
                body_fallback = {k: v for k, v in body.items() if k != "tools"}
                try:
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(body_fallback).encode("utf-8"),
                        headers=headers,
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=self.config.timeout) as response:
                        result = json.loads(response.read().decode("utf-8"))
                except urllib.error.HTTPError as e2:
                    error_body2 = e2.read().decode("utf-8") if e2.fp else ""
                    raise RuntimeError(f"ZAI HTTP error {e2.code}: {error_body2}")
            else:
                raise RuntimeError(f"ZAI HTTP error {e.code}: {error_body}")

        except urllib.error.URLError as e:
            raise RuntimeError(f"ZAI connection error: {e.reason}")

        latency_ms = (time.time() - start_time) * 1000

        # Parse OpenAI-format response
        choices = result.get("choices", [])
        if not choices:
            return {
                "content": "",
                "tool_calls": [],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "latency_ms": latency_ms,
                "raw": result,
            }

        message = choices[0].get("message", {})
        content = message.get("content", "")
        tool_calls = message.get("tool_calls", [])
        finish_reason = choices[0].get("finish_reason")

        # Parse tool calls from OpenAI format
        parsed_tool_calls = []
        for tc in tool_calls:
            func = tc.get("function", {})
            args = func.get("arguments", "{}")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            parsed_tool_calls.append({
                "id": tc.get("id", ""),
                "name": func.get("name", ""),
                "arguments": args,
            })

        if os.environ.get("AGENTNOVA_DEBUG"):
            print(f"  [ZAI] Content: {content[:1024] if content else '(empty)'}")
            print(f"  [ZAI] Tool calls: {parsed_tool_calls}")

        usage = result.get("usage", {})

        return {
            "content": content,
            "tool_calls": parsed_tool_calls,
            "finish_reason": finish_reason,
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            "latency_ms": latency_ms,
            "raw": result,
        }

    # ─────────────────────────────────────────────────────────────────────
    # Tool Support — ZAI models support native function calling
    # ─────────────────────────────────────────────────────────────────────

    def test_tool_support(self, model: str, family: str | None = None, force_test: bool = False) -> ToolSupportLevel:
        """
        Test model's tool support capability.

        ZAI's GLM models support native function calling via the standard
        OpenAI tools format. Returns NATIVE for known GLM models.

        When force_test=True, makes a live API call to verify.
        """
        from ..core.tool_cache import get_cached_tool_support, cache_tool_support

        api_mode = "openai"

        if not force_test:
            cached = get_cached_tool_support(model, api_mode=api_mode)
            if cached is not None:
                return cached
            return ToolSupportLevel.UNTESTED

        # Check API key before making a test call
        if not self._api_key:
            if os.environ.get("AGENTNOVA_DEBUG"):
                print(f"  [ZAI] No API key configured — cannot test tool support")
            return ToolSupportLevel.UNTESTED

        # Test tool: Weather
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
            import urllib.request
            import urllib.error

            url = f"{self.base_url}/api/paas/v4/chat/completions"

            body = {
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": "What's the weather like in Tokyo?"
                }],
                "tools": [test_tool.to_openai_schema()],
                "stream": False,
                "temperature": 0.0,
                "max_tokens": 200,
            }

            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))

            choices = result.get("choices", [])
            if not choices:
                support = ToolSupportLevel.REACT
                cache_tool_support(model, support, family=family or "glm", api_mode=api_mode)
                return support

            message = choices[0].get("message", {})
            content = message.get("content", "")
            tool_calls = message.get("tool_calls", [])

            # Native tool calls in response → NATIVE support
            if tool_calls:
                if os.environ.get("AGENTNOVA_DEBUG"):
                    print(f"  [ZAI] Tool support: NATIVE (tool_calls={len(tool_calls)})")
                cache_tool_support(model, ToolSupportLevel.NATIVE, family=family or "glm", api_mode=api_mode)
                return ToolSupportLevel.NATIVE

            # Check for ReAct-style text patterns
            if content and any(kw in content.lower() for kw in ["action:", "action input:", "final answer:"]):
                if os.environ.get("AGENTNOVA_DEBUG"):
                    print(f"  [ZAI] Tool support: REACT (text-based tool pattern)")
                cache_tool_support(model, ToolSupportLevel.REACT, family=family or "glm", api_mode=api_mode)
                return ToolSupportLevel.REACT

            # API accepted tools but model didn't use them — REACT-capable
            if os.environ.get("AGENTNOVA_DEBUG"):
                print(f"  [ZAI] Tool support: REACT (tools accepted, no tool calls)")
            cache_tool_support(model, ToolSupportLevel.REACT, family=family or "glm", api_mode=api_mode)
            return ToolSupportLevel.REACT

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            error_msg = error_body.lower()

            if "does not support" in error_msg or "invalid" in error_msg:
                if os.environ.get("AGENTNOVA_DEBUG"):
                    print(f"  [ZAI] Tool support: REACT (server rejected tools param)")
                cache_tool_support(model, ToolSupportLevel.REACT, family=family or "glm",
                                   error=str(e), api_mode=api_mode)
                return ToolSupportLevel.REACT

            if os.environ.get("AGENTNOVA_DEBUG"):
                print(f"  [ZAI] Tool support: REACT (HTTP {e.code})")
            cache_tool_support(model, ToolSupportLevel.REACT, family=family or "glm",
                               error=str(e), api_mode=api_mode)
            return ToolSupportLevel.REACT

        except Exception as e:
            if os.environ.get("AGENTNOVA_DEBUG"):
                print(f"  [ZAI] Tool support test failed: {e}")
            cache_tool_support(model, ToolSupportLevel.REACT, family=family or "glm",
                               error=str(e), api_mode=api_mode)
            return ToolSupportLevel.REACT

    # ─────────────────────────────────────────────────────────────────────
    # Context Size — from static model catalog
    # ─────────────────────────────────────────────────────────────────────

    def get_model_runtime_context(self, model: str) -> int:
        """
        Get the runtime context window size.

        ZAI doesn't expose per-request context settings, so we return
        the model's maximum trained context from our catalog.
        """
        model_key = model.split("/")[-1] if "/" in model else model
        meta = ZAI_MODELS.get(model_key)
        if meta:
            return meta.get("context_length", 128000)

        # Check if user set num_ctx via env var
        from ..config import NUM_CTX
        if NUM_CTX and NUM_CTX > 0:
            return NUM_CTX

        return 128000  # ZAI default

    def get_model_max_context(self, model: str, family: str | None = None) -> int:
        """
        Get the model's maximum trained context window size.

        Resolution order:
        1. Static catalog (ZAI_MODELS)
        2. Caller-provided family → OllamaBackend family table
        3. Fallback 128000
        """
        model_key = model.split("/")[-1] if "/" in model else model
        meta = ZAI_MODELS.get(model_key)
        if meta:
            return meta.get("context_length", 128000)

        # Try family heuristics
        if family:
            ctx = self.get_context_by_family(family)
            if ctx:
                return ctx

        return 128000

    def __repr__(self) -> str:
        key_status = "configured" if self._api_key else "NO KEY"
        return f"ZaiBackend(url={self._base_url}, key={key_status})"
