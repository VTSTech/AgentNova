"""
⚛️ AgentNova — llama-server Backend
Backend for llama.cpp server (e.g., llama-cpp-turboquant fork).

Supports OpenAI Chat Completions API (/v1/chat/completions) and the
native llama.cpp /completion endpoint. Works with any llama.cpp-based
server, including the TurboQuant+ fork for KV cache compression.

Endpoints used:
  - GET  /v1/models              → model discovery
  - POST /v1/chat/completions    → OpenAI Chat Completions (tools, streaming)
  - POST /completion             → llama.cpp native (ReAct mode)
  - GET  /health                 → server health check

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
from ..config import LLAMA_SERVER_BASE_URL, BITNET_BASE_URL


class LlamaServerBackend(OllamaBackend):
    """
    Backend for llama.cpp server (llama-server).

    Inherits the full OpenAI Chat Completions implementation from OllamaBackend
    and overrides server-management endpoints (model discovery, health, model info)
    to use llama-server's API instead of Ollama's.

    Supports llama-server, llama-cpp-turboquant, BitNet, and any other llama.cpp fork
    that exposes the standard OpenAI-compatible endpoints.

    BitNet mode (--backend bitnet):
        When bitnet_mode=True, defaults to OPENRE API mode (BitNet only exposes
        /completion), uses empty stop sequences, hardcoded list_models stub, and
        always returns REACT for tool support. This preserves backward compatibility
        with the former BitNetBackend while eliminating code duplication.

    Usage:
        backend = get_backend("llama-server")
        backend = get_backend("bitnet")  # alias — bitnet_mode=True

    CLI:
        agentnova chat --backend llama-server --base-url http://localhost:8080 --model qwen2.5:7b
        agentnova chat --backend llama-server --api-mode openai  # OpenAI Chat Completions
        agentnova chat --backend llama-server --api-mode openre  # Native /completion (ReAct)
        agentnova chat --backend bitnet                     # BitNet compat mode
    """

    def __init__(
        self,
        base_url: str | None = None,
        host: str | None = None,
        port: int | None = None,
        config: BackendConfig | None = None,
        api_mode: ApiMode | str | None = None,
        bitnet_mode: bool = False,
    ):
        # BitNet mode: default to OPENRE, use BITNET_BASE_URL
        self._bitnet_mode = bitnet_mode

        # Determine base URL - priority: base_url > host/port > env > default
        if base_url:
            self._base_url = base_url.rstrip("/")
        elif host and port:
            self._base_url = f"http://{host}:{port}"
        elif bitnet_mode:
            self._base_url = BITNET_BASE_URL.rstrip("/")
        else:
            self._base_url = LLAMA_SERVER_BASE_URL.rstrip("/")

        if config:
            super(OllamaBackend, self).__init__(config)
        else:
            super(OllamaBackend, self).__init__(BackendConfig())

        # Set API mode
        if api_mode is None:
            api_mode = ApiMode.OPENRE if bitnet_mode else ApiMode.OPENAI
        if isinstance(api_mode, str):
            api_mode = ApiMode(api_mode.lower())
        self._api_mode = api_mode

        # Set environment variable so other components know the API mode
        os.environ["AGENTNOVA_API_MODE"] = api_mode.value

    @property
    def backend_type(self) -> BackendType:
        return BackendType.BITNET if self._bitnet_mode else BackendType.CUSTOM

    # ─────────────────────────────────────────────────────────────────────
    # Server Management — llama-server endpoints (not Ollama)
    # ─────────────────────────────────────────────────────────────────────

    def is_running(self) -> bool:
        """Check if llama-server is running via /health endpoint."""
        try:
            import urllib.request
            import urllib.error

            url = f"{self._base_url}/health"
            req = urllib.request.Request(url, method="GET")

            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status == 200

        except Exception:
            # Fallback: try root URL
            try:
                import urllib.request
                import urllib.error

                req = urllib.request.Request(self._base_url, method="GET")
                with urllib.request.urlopen(req, timeout=3) as response:
                    return response.status < 500
            except Exception:
                return False

    def list_models(self) -> list[dict]:
        """
        List available models.

        BitNet mode: returns a hardcoded stub (BitNet serves a single model
        with no /v1/models endpoint).

        llama-server mode: queries /v1/models for OpenAI-compatible listing.
        """
        if self._bitnet_mode:
            return [{
                "name": "bitnet",
                "size": 0,
                "details": {"family": "bitnet", "backend": "bitnet"},
            }]

        import urllib.request
        import urllib.error

        url = f"{self._base_url}/v1/models"

        try:
            req = urllib.request.Request(url, method="GET")

            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))

            models = []
            for m in result.get("data", []):
                models.append({
                    "name": m.get("id", "unknown"),
                    "size": 0,
                    "details": {
                        "family": "llama-server",
                        "backend": "llama-cpp",
                    },
                })

            return models if models else [{
                "name": "default",
                "size": 0,
                "details": {"family": "llama-server", "backend": "llama-cpp"},
            }]

        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            if os.environ.get("AGENTNOVA_DEBUG"):
                print(f"  [llama-server] list_models failed: {e}")
            return [{
                "name": "default",
                "size": 0,
                "details": {"family": "llama-server", "backend": "llama-cpp"},
            }]

    def get_model_info(self, model: str) -> dict | None:
        """
        Get model information from llama-server.

        llama-server doesn't have an equivalent of Ollama's /api/show,
        so we return basic info from /v1/models if available.
        """
        models = self.list_models()
        for m in models:
            if m.get("name") == model or model == "default":
                return m
        return None

    # ─────────────────────────────────────────────────────────────────────
    # OpenRE mode — llama.cpp native /completion endpoint
    # ─────────────────────────────────────────────────────────────────────

    def generate(self, model: str, messages: list[dict], tools: list[Tool] | None = None,
                 temperature: float = 0.7, max_tokens: int = 2048,
                 think: bool | None = None, **kwargs) -> dict:
        """
        Generate a response from llama-server.

        Dispatches based on api_mode:
        - openai: uses /v1/chat/completions (full: tools, streaming, etc.)
        - openre: uses /completion (llama.cpp native, ReAct mode only)
        """
        if self._api_mode == ApiMode.OPENRE:
            return self._generate_completion(model, messages, tools, temperature, max_tokens, **kwargs)

        # OpenAI mode — use the inherited OllamaBackend implementation
        # which talks to /v1/chat/completions
        return super().generate(model, messages, tools, temperature, max_tokens, think=think, **kwargs)

    def generate_stream(self, model: str, messages: list[dict], tools: list[Tool] | None = None,
                        temperature: float = 0.7, max_tokens: int = 2048, **kwargs) -> Generator[str, None, None]:
        """
        Stream generated text from llama-server.

        Dispatches based on api_mode:
        - openai: uses /v1/chat/completions (streaming SSE)
        - openre: uses /completion (streaming)
        """
        if self._api_mode == ApiMode.OPENRE:
            return self._stream_completion(model, messages, tools, temperature, max_tokens, **kwargs)

        return super().generate_stream(model, messages, tools, temperature, max_tokens, **kwargs)

    def _generate_completion(
        self,
        model: str,
        messages: list[dict],
        tools: list[Tool] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> dict:
        """
        Generate via llama.cpp native /completion endpoint (OpenRE/ReAct mode).

        This endpoint mirrors BitNet's /completion API. Tools are embedded in the
        prompt as ReAct instructions — no native tool calling support.
        """
        import urllib.request
        import urllib.error

        url = f"{self._base_url}/completion"

        # Convert messages to a single prompt (same logic as BitNet)
        prompt = self._messages_to_prompt(messages, tools)

        body = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "stop": kwargs.get("stop", [] if self._bitnet_mode else ["</s>", "User:", "\nUser:"]),
        }

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
            label = "bitnet" if self._bitnet_mode else "llama-server"
            raise RuntimeError(f"{label} HTTP error {e.code}: {error_body}")

        except (urllib.error.URLError, ConnectionError, OSError) as e:
            label = "bitnet" if self._bitnet_mode else "llama-server"
            reason = getattr(e, 'reason', str(e))
            raise RuntimeError(f"{label} connection error: {reason}")

        latency_ms = (time.time() - start_time) * 1000

        content = result.get("content", "")

        return {
            "content": content,
            "tool_calls": [],  # No native tools in /completion mode
            "usage": {
                "prompt_tokens": result.get("tokens_evaluated", 0),
                "completion_tokens": result.get("tokens_predicted", 0),
                "total_tokens": result.get("tokens_evaluated", 0) + result.get("tokens_predicted", 0),
            },
            "latency_ms": latency_ms,
            "raw": result,
        }

    def _stream_completion(
        self,
        model: str,
        messages: list[dict],
        tools: list[Tool] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> Generator[str, None, None]:
        """
        Stream via llama.cpp native /completion endpoint (OpenRE/ReAct mode).
        """
        import urllib.request
        import urllib.error

        url = f"{self._base_url}/completion"

        prompt = self._messages_to_prompt(messages, tools)

        body = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "stream": True,
            "stop": kwargs.get("stop", [] if self._bitnet_mode else ["</s>", "User:", "\nUser:"]),
        }

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
                        content = chunk.get("content", "")
                        if content:
                            yield content

                        if chunk.get("stop"):
                            break

                    except json.JSONDecodeError:
                        continue

        except urllib.error.HTTPError as e:
            label = "bitnet" if self._bitnet_mode else "llama-server"
            raise RuntimeError(f"{label} HTTP error {e.code}")

        except (urllib.error.URLError, ConnectionError, OSError) as e:
            label = "bitnet" if self._bitnet_mode else "llama-server"
            reason = getattr(e, 'reason', str(e))
            raise RuntimeError(f"{label} connection error: {reason}")

    def _messages_to_prompt(
        self,
        messages: list[dict],
        tools: list[Tool] | None = None,
    ) -> str:
        """
        Convert messages to a single prompt string for /completion endpoint.

        Same format as BitNet backend — ReAct tool instructions embedded in prompt.
        """
        parts = []

        # Add system message
        for msg in messages:
            if msg["role"] == "system":
                parts.append(msg["content"])
                break

        # Add tool descriptions
        if tools:
            parts.append("\n\nAvailable tools:")
            for tool in tools:
                parts.append(f"- {tool.name}: {tool.description}")
            parts.append("\nUse ReAct format for tool calls:")
            parts.append('Action: tool_name')
            parts.append('Action Input: {"param": "value"}')

        # Add conversation
        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                continue  # Already added
            elif role == "user":
                parts.append(f"\nUser: {content}")
            elif role == "assistant":
                parts.append(f"\nAssistant: {content}")
            elif role == "tool":
                parts.append(f"\nTool Result: {content}")

        parts.append("\nAssistant:")

        return "\n".join(parts)

    # ─────────────────────────────────────────────────────────────────────
    # Tool Support Testing — live test via OpenAI endpoint
    # ─────────────────────────────────────────────────────────────────────

    def test_tool_support(self, model: str, family: str | None = None, force_test: bool = False) -> ToolSupportLevel:
        """
        Test model's tool support capability.

        BitNet mode: always returns REACT (no native tool support).

        llama-server mode: live test via /v1/chat/completions.
        """
        if self._bitnet_mode:
            return ToolSupportLevel.REACT

        from ..core.tool_cache import get_cached_tool_support, cache_tool_support

        api_mode = "openai"  # Always test via OpenAI endpoint

        if not force_test:
            cached = get_cached_tool_support(model, api_mode=api_mode)
            if cached is not None:
                return cached
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
            import urllib.request
            import urllib.error

            # Use /v1/chat/completions directly
            url = f"{self._base_url}/v1/chat/completions"

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

            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))

            choices = result.get("choices", [])
            if not choices:
                support = ToolSupportLevel.REACT
                cache_tool_support(model, support, family=family or "unknown", api_mode=api_mode)
                return support

            message = choices[0].get("message", {})
            content = message.get("content", "")
            tool_calls = message.get("tool_calls", [])

            # Native tool calls in the response → NATIVE support
            if tool_calls:
                if os.environ.get("AGENTNOVA_DEBUG"):
                    print(f"  [llama-server] Tool support: NATIVE (tool_calls={len(tool_calls)})")
                cache_tool_support(model, ToolSupportLevel.NATIVE, family=family or "unknown", api_mode=api_mode)
                return ToolSupportLevel.NATIVE

            # Check if content contains ReAct-style tool call pattern
            if content and any(kw in content.lower() for kw in ["action:", "action input:", "final answer:"]):
                if os.environ.get("AGENTNOVA_DEBUG"):
                    print(f"  [llama-server] Tool support: REACT (text-based tool pattern)")
                cache_tool_support(model, ToolSupportLevel.REACT, family=family or "unknown", api_mode=api_mode)
                return ToolSupportLevel.REACT

            # API accepted tools but model didn't use them — still REACT-capable
            if os.environ.get("AGENTNOVA_DEBUG"):
                print(f"  [llama-server] Tool support: REACT (tools accepted, no tool calls)")
            cache_tool_support(model, ToolSupportLevel.REACT, family=family or "unknown", api_mode=api_mode)
            return ToolSupportLevel.REACT

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            error_msg = error_body.lower()

            # If the server doesn't support the tools parameter, fall back to REACT
            if "does not support" in error_msg or "invalid" in error_msg:
                if os.environ.get("AGENTNOVA_DEBUG"):
                    print(f"  [llama-server] Tool support: REACT (server rejected tools param)")
                cache_tool_support(model, ToolSupportLevel.REACT, family=family or "unknown",
                                   error=str(e), api_mode=api_mode)
                return ToolSupportLevel.REACT

            # Other errors — assume REACT
            if os.environ.get("AGENTNOVA_DEBUG"):
                print(f"  [llama-server] Tool support: REACT (HTTP {e.code})")
            cache_tool_support(model, ToolSupportLevel.REACT, family=family or "unknown",
                               error=str(e), api_mode=api_mode)
            return ToolSupportLevel.REACT

        except Exception as e:
            if os.environ.get("AGENTNOVA_DEBUG"):
                print(f"  [llama-server] Tool support test failed: {e}")
            cache_tool_support(model, ToolSupportLevel.REACT, family=family or "unknown",
                               error=str(e), api_mode=api_mode)
            return ToolSupportLevel.REACT

    # ─────────────────────────────────────────────────────────────────────
    # Context size — llama-server doesn't expose this via API
    # ─────────────────────────────────────────────────────────────────────

    def get_model_runtime_context(self, model: str) -> int:
        """
        Get the runtime context window size.

        llama-server doesn't expose num_ctx via API. Returns the configured
        context or falls back to 4096 (typical llama.cpp default).
        """
        # Check if user set num_ctx via env var
        from ..config import NUM_CTX
        if NUM_CTX and NUM_CTX > 0:
            return NUM_CTX

        return 4096

    def get_model_max_context(self, model: str, family: str | None = None) -> int:
        """
        Get the model's maximum trained context window size.

        llama-server doesn't expose model metadata. Uses family heuristics
        from OllamaBackend if a family hint is available, otherwise 4096.
        """
        if family:
            ctx = self.get_context_by_family(family)
            if ctx:
                return ctx

        return 4096

    def __repr__(self) -> str:
        return f"LlamaServerBackend(url={self._base_url}, mode={self._api_mode.value})"
