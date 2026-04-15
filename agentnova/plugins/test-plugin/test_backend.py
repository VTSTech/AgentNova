"""
Test backend — minimal implementation for validating plugin backend registration.

This backend does NOT connect to any real server. It returns canned responses
for testing the plugin system's backend discovery and selection.
"""

from __future__ import annotations

from agentnova.backends.base import BaseBackend, BackendConfig


class TestBackend(BaseBackend):
    """A fake backend that returns a fixed response for plugin testing."""

    def __init__(self, config: BackendConfig | None = None):
        super().__init__(config or BackendConfig())

    def generate(
        self,
        model: str = "test-model",
        messages: list[dict] | None = None,
        tools: list | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: float = 1.0,
        **kwargs,
    ) -> dict:
        return {
            "content": "[test-backend] Plugin system validation response",
            "tool_calls": [],
            "usage": {"total_tokens": 13, "prompt_tokens": 8, "completion_tokens": 5},
            "finish_reason": "stop",
        }

    def generate_stream(self, *args, **kwargs):
        raise NotImplementedError("TestBackend does not support streaming")

    def list_models(self) -> list[str]:
        return ["test-model"]
