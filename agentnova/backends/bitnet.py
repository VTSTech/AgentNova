"""
⚛️ AgentNova — BitNet Backend
Backend implementation for BitNet inference engine.

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

import json
import time
from typing import Any, Generator

from .base import BaseBackend, BackendConfig
from ..core.types import BackendType, ToolSupportLevel
from ..core.models import Tool
from ..config import BITNET_BASE_URL


class BitNetBackend(BaseBackend):
    """
    Backend for BitNet inference engine.

    BitNet is a 1-bit LLM inference engine optimized
    for CPU inference with extreme efficiency.
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
            self._base_url = base_url
        elif host and port:
            self._base_url = f"http://{host}:{port}"
        else:
            self._base_url = BITNET_BASE_URL

        if config:
            super().__init__(config)
        else:
            super().__init__(BackendConfig())

    @property
    def backend_type(self) -> BackendType:
        return BackendType.BITNET

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
        """Generate a response from BitNet."""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/completion"

        # BitNet uses a simpler API format
        # Convert messages to a single prompt
        prompt = self._messages_to_prompt(messages, tools)

        body = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "stop": kwargs.get("stop", []),
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
            raise RuntimeError(f"BitNet HTTP error {e.code}: {error_body}")

        except urllib.error.URLError as e:
            raise RuntimeError(f"BitNet connection error: {e.reason}")

        latency_ms = (time.time() - start_time) * 1000

        content = result.get("content", "")

        return {
            "content": content,
            "tool_calls": [],  # BitNet doesn't support native tools
            "usage": {
                "prompt_tokens": result.get("tokens_evaluated", 0),
                "completion_tokens": result.get("tokens_predicted", 0),
                "total_tokens": result.get("tokens_evaluated", 0) + result.get("tokens_predicted", 0),
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
        """Stream generated text from BitNet."""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/completion"

        prompt = self._messages_to_prompt(messages, tools)

        body = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "stream": True,
            "stop": kwargs.get("stop", []),
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

                    except json.JSONDecodeError:
                        continue

        except urllib.error.HTTPError as e:
            raise RuntimeError(f"BitNet HTTP error {e.code}")

        except urllib.error.URLError as e:
            raise RuntimeError(f"BitNet connection error: {e.reason}")

    def list_models(self) -> list[dict]:
        """List available models from BitNet."""
        # BitNet typically runs a single model
        # Return basic info
        return [
            {
                "name": "bitnet",
                "size": 0,
                "details": {
                    "family": "bitnet",
                },
            }
        ]

    def test_tool_support(self, model: str) -> ToolSupportLevel:
        """Test model's tool support capability."""
        # BitNet doesn't support native tools
        # Always use ReAct format
        return ToolSupportLevel.REACT

    def _messages_to_prompt(
        self,
        messages: list[dict],
        tools: list[Tool] | None = None,
    ) -> str:
        """Convert messages to a single prompt string."""
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

    def __repr__(self) -> str:
        return f"BitNetBackend(url={self.base_url})"
