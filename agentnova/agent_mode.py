"""
⚛️ AgentNova — Agent Mode
Autonomous task execution with goal tracking.

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

from .agent import Agent


class AgentState(Enum):
    """State of an autonomous agent."""
    IDLE = auto()
    PLANNING = auto()
    EXECUTING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    FAILED = auto()


@dataclass
class TaskPlan:
    """A plan for completing a task."""
    goal: str
    steps: list[str] = field(default_factory=list)
    current_step: int = 0
    progress: list[dict] = field(default_factory=list)

    def add_step(self, step: str) -> None:
        """Add a step to the plan."""
        self.steps.append(step)

    def complete_step(self, result: str) -> None:
        """Mark current step as complete."""
        if self.current_step < len(self.steps):
            self.progress.append({
                "step": self.steps[self.current_step],
                "result": result,
                "completed_at": time.time(),
            })
            self.current_step += 1

    @property
    def progress_percent(self) -> float:
        """Get progress as percentage."""
        if not self.steps:
            return 0.0
        return (self.current_step / len(self.steps)) * 100

    @property
    def is_complete(self) -> bool:
        """Check if plan is complete."""
        return self.current_step >= len(self.steps)


class AgentMode:
    """
    Autonomous agent mode with goal tracking.

    Features:
    - Goal decomposition
    - Progress tracking
    - Pause/resume/stop controls
    - Rollback on failure

    Example:
        agent = Agent(model="qwen2.5:7b", tools=["calculator", "shell"])
        agent_mode = AgentMode(agent)

        success, result = agent_mode.run_task("Calculate 15 * 8 and save to file")
    """

    def __init__(self, agent: Agent, verbose: bool = False):
        """
        Initialize AgentMode.

        Args:
            agent: Agent instance
            verbose: Print progress messages
        """
        self.agent = agent
        self.verbose = verbose

        self._state = AgentState.IDLE
        self._plan: TaskPlan | None = None
        self._checkpoint: dict | None = None

    @property
    def state(self) -> AgentState:
        """Get current state."""
        return self._state

    def run_task(self, goal: str) -> tuple[bool, str]:
        """
        Run an autonomous task.

        Args:
            goal: Goal to accomplish

        Returns:
            Tuple of (success, result_message)
        """
        self._state = AgentState.PLANNING
        self._plan = TaskPlan(goal=goal)

        if self.verbose:
            print(f"\n[AgentMode] Goal: {goal}")
            print("[AgentMode] Planning...")

        # Decompose goal into steps
        try:
            plan_prompt = f"""Break down this goal into specific steps: {goal}

List the steps as a numbered list. Each step should be a concrete, actionable task.
Format your response as:
1. [step one]
2. [step two]
..."""

            plan_result = self.agent.run(plan_prompt)
            steps = self._parse_steps(plan_result.final_answer)

            if not steps:
                # Try direct execution
                steps = [goal]

            self._plan.steps = steps

            if self.verbose:
                print(f"[AgentMode] Plan ({len(steps)} steps):")
                for i, step in enumerate(steps, 1):
                    print(f"  {i}. {step}")

        except Exception as e:
            self._state = AgentState.FAILED
            return False, f"Planning failed: {e}"

        # Execute steps
        self._state = AgentState.EXECUTING

        for i, step in enumerate(self._plan.steps):
            # Check for pause/stop
            if self._state == AgentState.PAUSED:
                return False, "Task paused by user"

            if self.verbose:
                print(f"\n[AgentMode] Step {i+1}/{len(self._plan.steps)}: {step}")

            try:
                result = self.agent.run(step)

                self._plan.complete_step(result.final_answer)

                if self.verbose:
                    print(f"[AgentMode] Result: {result.final_answer[:200]}...")

            except Exception as e:
                self._state = AgentState.FAILED
                return False, f"Step {i+1} failed: {e}"

        self._state = AgentState.COMPLETED

        if self.verbose:
            print(f"\n[AgentMode] Task completed! Progress: {self._plan.progress_percent:.0f}%")

        return True, f"Task completed successfully. {self._plan.progress_percent:.0f}% of steps completed."

    def pause(self) -> tuple[bool, str]:
        """Pause execution."""
        if self._state not in (AgentState.PLANNING, AgentState.EXECUTING):
            return False, "Cannot pause: not currently running"

        self._state = AgentState.PAUSED
        return True, "Execution paused"

    def resume(self) -> tuple[bool, str]:
        """Resume execution."""
        if self._state != AgentState.PAUSED:
            return False, "Cannot resume: not paused"

        self._state = AgentState.EXECUTING
        return True, "Execution resumed"

    def stop(self, rollback: bool = False) -> tuple[bool, str]:
        """Stop execution."""
        if self._state == AgentState.IDLE:
            return False, "Cannot stop: not running"

        self._state = AgentState.FAILED

        if rollback and self._checkpoint:
            # Restore from checkpoint
            pass  # Implement rollback logic

        return True, "Execution stopped"

    def get_status(self) -> dict:
        """Get current status."""
        status = {
            "state": self._state.name,
        }

        if self._plan:
            status["goal"] = self._plan.goal
            status["total_steps"] = len(self._plan.steps)
            status["current_step"] = self._plan.current_step
            status["progress_percent"] = self._plan.progress_percent

        return status

    def _parse_steps(self, text: str) -> list[str]:
        """Parse numbered steps from text."""
        import re

        steps = []

        # Match numbered list items
        pattern = r"^\s*(\d+)\.\s*(.+)$"
        for line in text.split("\n"):
            match = re.match(pattern, line.strip())
            if match:
                steps.append(match.group(2).strip())

        return steps

    def __repr__(self) -> str:
        return f"AgentMode(state={self._state.name})"
