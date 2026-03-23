"""
⚛️ AgentNova R02.3 — Models
Data models for agent results and step tracking.

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .types import StepResultType


@dataclass
class StepResult:
    """Result of a single agent step (thought, tool call, tool result, or final answer)."""
    type: StepResultType
    content: str
    tool_name: str | None = None
    tool_args: dict | None = None
    elapsed_ms: float = 0.0

    def __str__(self):
        if self.type == "tool_call":
            return f"[CALL] {self.tool_name}({self.tool_args})"
        if self.type == "tool_result":
            return f"[RESULT] {self.tool_name} → {self.content}"
        if self.type == "thought":
            return f"[THOUGHT] {self.content}"
        return f"[FINAL] {self.content}"


@dataclass
class AgentRun:
    """Complete result of an agent run, including all steps and final answer."""
    steps: list[StepResult] = field(default_factory=list)
    final_answer: str = ""
    total_ms: float = 0.0
    success: bool = True
    error: str = ""

    def print_trace(self):
        for step in self.steps:
            print(step)
        print(f"\n✓ Done in {self.total_ms:.0f}ms")