"""
⚛️ AgentNova — Skill Loader
Load and manage skills from SKILL.md files.

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class Skill:
    """A skill definition."""
    name: str
    description: str
    instructions: str
    tools: list[str] | None = None
    examples: list[str] | None = None
    path: str | None = None


class SkillLoader:
    """
    Load skills from SKILL.md files.

    Skills are defined in markdown files with a specific format:
    - First heading is the skill name
    - Description follows
    - Instructions in the body
    """

    def __init__(self, skills_dir: str | None = None):
        """
        Initialize SkillLoader.

        Args:
            skills_dir: Directory containing skill folders
        """
        self.skills_dir = skills_dir
        self._skills: dict[str, Skill] = {}

        if skills_dir:
            self.load_all(skills_dir)

    def load_all(self, directory: str) -> int:
        """
        Load all skills from a directory.

        Args:
            directory: Directory containing skill folders

        Returns:
            Number of skills loaded
        """
        count = 0

        try:
            for item in os.listdir(directory):
                skill_path = os.path.join(directory, item, "SKILL.md")

                if os.path.isfile(skill_path):
                    skill = self.load(skill_path)
                    if skill:
                        self._skills[skill.name] = skill
                        count += 1

        except FileNotFoundError:
            pass

        return count

    def load(self, path: str) -> Skill | None:
        """
        Load a skill from a SKILL.md file.

        Args:
            path: Path to SKILL.md file

        Returns:
            Skill object or None
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            return self.parse(content, path)

        except Exception as e:
            print(f"Error loading skill from {path}: {e}")
            return None

    def parse(self, content: str, path: str | None = None) -> Skill:
        """
        Parse a SKILL.md content string.

        Args:
            content: SKILL.md content
            path: Optional path to the file

        Returns:
            Skill object
        """
        lines = content.strip().split("\n")

        name = "unnamed"
        description = ""
        instructions = []

        # Parse frontmatter and content
        in_frontmatter = False
        frontmatter = {}

        for line in lines:
            # Check for frontmatter
            if line.strip() == "---":
                in_frontmatter = not in_frontmatter
                continue

            if in_frontmatter:
                # Parse frontmatter key: value
                if ":" in line:
                    key, value = line.split(":", 1)
                    frontmatter[key.strip()] = value.strip()
                continue

            # First heading is the name
            if line.startswith("# ") and name == "unnamed":
                name = line[2:].strip()
                continue

            # Everything else is instructions
            instructions.append(line)

        # Extract description from frontmatter or first paragraph
        description = frontmatter.get("description", "")

        # Instructions are the body
        instructions_text = "\n".join(instructions).strip()

        # Extract tools from frontmatter
        tools = None
        if "tools" in frontmatter:
            tools = [t.strip() for t in frontmatter["tools"].split(",")]

        return Skill(
            name=frontmatter.get("name", name),
            description=description,
            instructions=instructions_text,
            tools=tools,
            path=path,
        )

    def get(self, name: str) -> Skill | None:
        """Get a skill by name."""
        return self._skills.get(name)

    def list(self) -> list[str]:
        """List all loaded skill names."""
        return list(self._skills.keys())

    def all(self) -> list[Skill]:
        """Get all loaded skills."""
        return list(self._skills.values())


def load_skill(path: str) -> Skill | None:
    """
    Convenience function to load a single skill.

    Args:
        path: Path to SKILL.md file

    Returns:
        Skill object or None
    """
    loader = SkillLoader()
    return loader.load(path)
