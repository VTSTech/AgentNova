"""
⚛️ AgentNova R00 - Skills Module

Agent Skills support for AgentNova.
Loads skills from SKILL.md files following the Agent Skills specification.

Specification: https://agentskills.io/

Usage:
    from agentnova.skills import SkillLoader, SkillRegistry
    
    loader = SkillLoader()
    skill = loader.load("calculator")
    
    registry = SkillRegistry()
    registry.add(skill)
    system_prompt += registry.to_system_prompt_addition()

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

from .loader import SkillLoader, Skill, SkillRegistry

__all__ = ["SkillLoader", "Skill", "SkillRegistry"]
