"""
⚛️ AgentNova — Orchestrator
Multi-agent orchestration for complex tasks.

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

from .agent import Agent
from .tools import ToolRegistry


class OrchestratorMode(Enum):
    """Orchestration mode."""
    ROUTER = auto()      # Route tasks to specialized agents
    PIPELINE = auto()    # Chain agents in sequence
    PARALLEL = auto()    # Run agents in parallel


@dataclass
class AgentCard:
    """Card describing an agent's capabilities."""
    name: str
    description: str
    capabilities: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    model: str | None = None
    agent: Agent | None = None

    def matches(self, task: str) -> bool:
        """Check if this agent matches a task."""
        task_lower = task.lower()

        for cap in self.capabilities:
            if cap.lower() in task_lower:
                return True

        return False


class Orchestrator:
    """
    Multi-agent orchestrator.

    Supports three modes:
    - Router: Route tasks to specialized agents
    - Pipeline: Chain agents in sequence
    - Parallel: Run agents in parallel

    Example:
        orchestrator = Orchestrator(mode="router")

        # Register specialized agents
        orchestrator.register(AgentCard(
            name="math_agent",
            description="Handles mathematical calculations",
            capabilities=["calculate", "math", "compute"],
            tools=["calculator"],
        ))

        result = orchestrator.run("Calculate 15 * 8")
    """

    def __init__(
        self,
        mode: str = "router",
        default_model: str = "qwen2.5:0.5b",
        default_tools: list[str] | None = None,
    ):
        """
        Initialize Orchestrator.

        Args:
            mode: Orchestration mode ("router", "pipeline", "parallel")
            default_model: Default model for agents
            default_tools: Default tools for agents
        """
        self.mode = OrchestratorMode[mode.upper()]
        self.default_model = default_model
        self.default_tools = default_tools or []

        self._agents: dict[str, AgentCard] = {}
        self._results: list[dict] = []

    def register(self, card: AgentCard) -> None:
        """Register an agent."""
        # Create agent if not provided
        if card.agent is None:
            tools = ToolRegistry()
            if card.tools:
                from .tools import make_builtin_registry
                builtin = make_builtin_registry()
                tools = builtin.subset(card.tools)

            card.agent = Agent(
                model=card.model or self.default_model,
                tools=tools,
            )

        self._agents[card.name] = card

    def run(self, task: str) -> dict:
        """
        Run orchestration on a task.

        Args:
            task: Task to process

        Returns:
            Result dict with outputs
        """
        self._results = []

        if self.mode == OrchestratorMode.ROUTER:
            return self._run_router(task)
        elif self.mode == OrchestratorMode.PIPELINE:
            return self._run_pipeline(task)
        elif self.mode == OrchestratorMode.PARALLEL:
            return self._run_parallel(task)

        raise ValueError(f"Unknown mode: {self.mode}")

    def _run_router(self, task: str) -> dict:
        """Route task to best matching agent."""
        # Find best agent
        best_agent = None
        best_score = 0

        for card in self._agents.values():
            if card.matches(task):
                # Calculate match score
                score = sum(1 for cap in card.capabilities if cap.lower() in task.lower())
                if score > best_score:
                    best_score = score
                    best_agent = card

        if best_agent is None:
            # Use first agent as fallback
            best_agent = next(iter(self._agents.values()), None)

        if best_agent is None:
            return {"error": "No agents registered"}

        result = best_agent.agent.run(task)

        return {
            "agent": best_agent.name,
            "result": result.final_answer,
            "steps": result.steps,
        }

    def _run_pipeline(self, task: str) -> dict:
        """Run agents in sequence."""
        results = []

        for card in self._agents.values():
            result = card.agent.run(task)
            results.append({
                "agent": card.name,
                "result": result.final_answer,
            })
            # Pass result to next agent
            task = result.final_answer

        return {
            "pipeline": results,
            "final_result": results[-1]["result"] if results else "",
        }

    def _run_parallel(self, task: str) -> dict:
        """Run agents in parallel."""
        # Note: True parallel would use threading/async
        # This is a simplified sequential version
        results = []

        for card in self._agents.values():
            result = card.agent.run(task)
            results.append({
                "agent": card.name,
                "result": result.final_answer,
            })

        return {
            "parallel": results,
            "results": [r["result"] for r in results],
        }

    def list_agents(self) -> list[dict]:
        """List registered agents."""
        return [
            {
                "name": card.name,
                "description": card.description,
                "capabilities": card.capabilities,
            }
            for card in self._agents.values()
        ]

    def __repr__(self) -> str:
        return f"Orchestrator(mode={self.mode.name}, agents={len(self._agents)})"
