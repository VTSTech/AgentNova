"""
⚛️ AgentNova R02.6 — Types
Type aliases for the agent system.

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

from typing import Literal

# Step result types
StepResultType = Literal["thought", "tool_call", "tool_result", "final"]
