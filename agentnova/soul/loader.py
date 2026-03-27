"""
⚛️ AgentNova R02 - Skills Loader

Implements the Agent Skills specification for loading SKILL.md files.
See: https://agentskills.io/

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, List, Any


# Common SPDX license identifiers (subset for validation)
COMMON_SPDX_LICENSES = {
    # Permissive licenses
    "MIT", "Apache-2.0", "Apache-2.0-only", "Apache-2.0-or-later",
    "BSD-2-Clause", "BSD-3-Clause", "BSD-3-Clause-Clear",
    "ISC", "0BSD", "Unlicense",
    # Creative Commons
    "CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0", "CC-BY-NC-4.0",
    # Copyleft licenses
    "GPL-2.0", "GPL-2.0-only", "GPL-2.0-or-later",
    "GPL-3.0", "GPL-3.0-only", "GPL-3.0-or-later",
    "LGPL-2.1", "LGPL-3.0", "LGPL-3.0-only",
    "MPL-2.0", "EPL-2.0",
    # Proprietary
    "Proprietary", "Commercial",
    # Other common
    "WTFPL", "Zlib", "PostgreSQL",
}


@dataclass
class Skill:
    """
    Represents a loaded skill following the Agent Skills specification.
    
    Attributes:
        name: Skill identifier (1-64 chars, lowercase, hyphens only)
        description: What the skill does and when to use it (1-1024 chars)
        instructions: The Markdown body after frontmatter
        path: Path to the skill directory
        license: Optional license information (SPDX identifier recommended)
        compatibility: Optional environment requirements
        metadata: Optional additional metadata
        allowed_tools: Optional list of pre-approved tools
    """
    name: str
    description: str
    instructions: str
    path: Path
    license: Optional[str] = None
    compatibility: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)
    allowed_tools: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate skill fields after initialization."""
        self._validate_name()
        self._validate_description()
        self._validate_license()
    
    def _validate_name(self):
        """Validate the name field follows Agent Skills spec."""
        if not self.name:
            raise ValueError("Skill name is required")
        if len(self.name) > 64:
            raise ValueError(f"Skill name too long: {len(self.name)} chars (max 64)")
        if not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', self.name):
            raise ValueError(
                f"Invalid skill name '{self.name}': must be lowercase, "
                "alphanumeric with hyphens, no leading/trailing/consecutive hyphens"
            )
    
    def _validate_description(self):
        """Validate the description field follows Agent Skills spec."""
        if not self.description:
            raise ValueError("Skill description is required")
        if len(self.description) > 1024:
            raise ValueError(f"Skill description too long: {len(self.description)} chars (max 1024)")
    
    def _validate_license(self):
        """Validate the license field if present.
        
        Validates against common SPDX license identifiers. Issues a warning
        for non-standard licenses rather than failing, to allow flexibility.
        """
        if self.license is None:
            return  # No license specified, that's okay
        
        # Check if it's a recognized SPDX identifier
        if self.license in COMMON_SPDX_LICENSES:
            return  # Valid SPDX license
        
        # Check for common patterns that are likely valid
        # (e.g., "MIT License", "Apache 2.0", custom licenses)
        license_lower = self.license.lower()
        
        # Allow licenses that contain common keywords
        common_keywords = ["mit", "apache", "bsd", "gpl", "lgpl", "mpl", 
                          "creative commons", "cc0", "cc-by", "proprietary",
                          "commercial", "custom", "private"]
        
        for keyword in common_keywords:
            if keyword in license_lower:
                return  # Likely valid license
        
        # Non-standard license - this is a warning, not an error
        # The skill still loads, but may indicate a typo
        import warnings
        warnings.warn(
            f"Skill '{self.name}' has non-standard license '{self.license}'. "
            f"Consider using a standard SPDX identifier. "
            f"Common licenses: MIT, Apache-2.0, BSD-3-Clause, GPL-3.0, Proprietary"
        )
    
    @property
    def scripts_dir(self) -> Optional[Path]:
        """Path to scripts directory if it exists."""
        scripts = self.path / "scripts"
        return scripts if scripts.is_dir() else None
    
    @property
    def references_dir(self) -> Optional[Path]:
        """Path to references directory if it exists."""
        refs = self.path / "references"
        return refs if refs.is_dir() else None
    
    @property
    def assets_dir(self) -> Optional[Path]:
        """Path to assets directory if it exists."""
        assets = self.path / "assets"
        return assets if assets.is_dir() else None
    
    def get_script(self, script_name: str) -> Optional[Path]:
        """Get path to a specific script file."""
        if self.scripts_dir:
            script = self.scripts_dir / script_name
            return script if script.exists() else None
        return None
    
    def get_reference(self, ref_name: str) -> Optional[Path]:
        """Get path to a specific reference file."""
        if self.references_dir:
            ref = self.references_dir / ref_name
            return ref if ref.exists() else None
        return None
    
    def get_asset(self, asset_name: str) -> Optional[Path]:
        """Get path to a specific asset file."""
        if self.assets_dir:
            asset = self.assets_dir / asset_name
            return asset if asset.exists() else None
        return None
    
    def to_system_prompt(self) -> str:
        """Convert skill instructions to a system prompt addition."""
        return f"\n\n---\n## Skill: {self.name}\n\n{self.instructions}"
    
    def __repr__(self) -> str:
        return f"Skill(name={self.name!r}, description={self.description[:50]}...)"


class SkillLoader:
    """
    Loads skills from directories containing SKILL.md files.
    
    Follows the Agent Skills specification:
    - SKILL.md with YAML frontmatter (name, description required)
    - Optional scripts/, references/, assets/ directories
    
    Usage:
        loader = SkillLoader("/path/to/skills")
        skill = loader.load("my-skill")
        skills = loader.list_skills()  # Get all available skills
    """
    
    def __init__(self, skills_dir: Optional[str] = None):
        """
        Initialize the skill loader.
        
        Args:
            skills_dir: Directory containing skill folders. 
                       If None, uses 'skills' in same directory as this file.
        """
        if skills_dir:
            self.skills_dir = Path(skills_dir)
        else:
            self.skills_dir = Path(__file__).parent
        
        self._cache: Dict[str, Skill] = {}
    
    def _parse_frontmatter(self, content: str) -> tuple[Dict[str, Any], str]:
        """
        Parse YAML frontmatter from SKILL.md content.
        
        Returns:
            Tuple of (frontmatter_dict, body_content)
        """
        # Check for frontmatter
        if not content.startswith("---"):
            raise ValueError("SKILL.md must start with YAML frontmatter (---)")
        
        # Find the closing ---
        end_match = re.search(r'\n---\s*\n', content[3:])
        if not end_match:
            raise ValueError("SKILL.md frontmatter not closed (missing ---)")
        
        frontmatter_text = content[3:end_match.start() + 3]
        body = content[end_match.end() + 3:]
        
        # Parse YAML frontmatter (simple parser for the spec format)
        frontmatter: Dict[str, Any] = {}
        current_key = None
        current_value: Any = None

        for line in frontmatter_text.split('\n'):
            stripped = line.strip()

            if not stripped:
                continue

            # Check for key: value
            if ':' in line and not line.startswith(' '):
                # Save previous key
                if current_key:
                    frontmatter[current_key] = current_value

                key, _, value = line.partition(':')
                current_key = key.strip()
                value = value.strip()

                # Handle different value types
                if value.startswith('"') and value.endswith('"'):
                    current_value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    current_value = value[1:-1]
                elif value == '':
                    current_value = None
                else:
                    current_value = value
            elif line.startswith('  ') and current_key:
                # Multiline value (like metadata)
                if current_key not in frontmatter:
                    frontmatter[current_key] = {}
                
                if ':' in line:
                    sub_key, _, sub_value = line.strip().partition(':')
                    sub_value = sub_value.strip()
                    if sub_value.startswith('"') and sub_value.endswith('"'):
                        sub_value = sub_value[1:-1]
                    frontmatter[current_key][sub_key] = sub_value
        
        # Save last key
        if current_key and current_key not in frontmatter:
            frontmatter[current_key] = current_value
        
        return frontmatter, body
    
    def load(self, skill_name: str, use_cache: bool = True) -> Skill:
        """
        Load a skill by name.
        
        Args:
            skill_name: Name of the skill (directory name)
            use_cache: Whether to use cached skill if available
            
        Returns:
            Skill object
            
        Raises:
            FileNotFoundError: If skill directory or SKILL.md doesn't exist
            ValueError: If SKILL.md is invalid
        """
        if use_cache and skill_name in self._cache:
            return self._cache[skill_name]
        
        skill_path = self.skills_dir / skill_name
        if not skill_path.is_dir():
            raise FileNotFoundError(f"Skill directory not found: {skill_path}")
        
        skill_md_path = skill_path / "SKILL.md"
        if not skill_md_path.exists():
            raise FileNotFoundError(f"SKILL.md not found: {skill_md_path}")
        
        # Read and parse SKILL.md
        content = skill_md_path.read_text(encoding='utf-8')
        frontmatter, instructions = self._parse_frontmatter(content)
        
        # Extract required fields
        name = frontmatter.get('name', skill_name)
        description = frontmatter.get('description', '')
        
        if not description:
            raise ValueError(f"Skill '{skill_name}' missing required 'description' field")
        
        # Create Skill object
        skill = Skill(
            name=name,
            description=description,
            instructions=instructions.strip(),
            path=skill_path,
            license=frontmatter.get('license'),
            compatibility=frontmatter.get('compatibility'),
            metadata=frontmatter.get('metadata', {}),
            allowed_tools=frontmatter.get('allowed-tools', '').split() if frontmatter.get('allowed-tools') else []
        )
        
        # Validate name matches directory
        if skill.name != skill_name:
            print(f"⚠️ Warning: Skill name '{skill.name}' doesn't match directory '{skill_name}'")
        
        self._cache[skill_name] = skill
        return skill
    
    def list_skills(self) -> List[str]:
        """
        List all available skill names.
        
        Returns:
            List of skill names (directory names containing SKILL.md)
        """
        skills = []
        if not self.skills_dir.is_dir():
            return skills
        
        for item in self.skills_dir.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                skills.append(item.name)
        
        return sorted(skills)
    
    def load_all(self) -> Dict[str, Skill]:
        """
        Load all available skills.
        
        Returns:
            Dict mapping skill names to Skill objects
        """
        skills = {}
        for name in self.list_skills():
            try:
                skills[name] = self.load(name)
            except Exception as e:
                print(f"⚠️ Failed to load skill '{name}': {e}")
        
        return skills
    
    def get_skill_descriptions(self) -> Dict[str, str]:
        """
        Get name and description for all skills without loading full instructions.
        Reads only the YAML frontmatter from each SKILL.md for efficiency.

        Returns:
            Dict mapping skill names to their descriptions
        """
        descriptions = {}
        for name in self.list_skills():
            skill_md = self.skills_dir / name / "SKILL.md"
            if not skill_md.exists():
                continue
            # Return from cache if already loaded
            if name in self._cache:
                descriptions[name] = self._cache[name].description
                continue
            try:
                content = skill_md.read_text(encoding='utf-8')
                frontmatter, _ = self._parse_frontmatter(content)
                descriptions[name] = frontmatter.get('description', 'No description')
            except Exception:
                pass
        return descriptions


class SkillRegistry:
    """
    Registry for managing active skills in an agent session.
    
    Usage:
        registry = SkillRegistry()
        registry.add(skill)
        
        # Get combined system prompt
        prompt = registry.get_combined_instructions()
        
        # Check if skill is active
        if registry.has("calculator"):
            ...
    """
    
    def __init__(self):
        self._skills: Dict[str, Skill] = {}
    
    def add(self, skill: Skill) -> None:
        """Add a skill to the registry."""
        self._skills[skill.name] = skill
    
    def remove(self, skill_name: str) -> bool:
        """Remove a skill from the registry. Returns True if removed."""
        if skill_name in self._skills:
            del self._skills[skill_name]
            return True
        return False
    
    def get(self, skill_name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return self._skills.get(skill_name)
    
    def has(self, skill_name: str) -> bool:
        """Check if a skill is in the registry."""
        return skill_name in self._skills
    
    def list(self) -> List[str]:
        """List all active skill names."""
        return list(self._skills.keys())
    
    def get_combined_instructions(self) -> str:
        """Get all skill instructions combined into one string."""
        if not self._skills:
            return ""
        
        parts = []
        for skill in self._skills.values():
            parts.append(f"## Skill: {skill.name}\n\n{skill.instructions}")
        
        return "\n\n---\n\n".join(parts)
    
    def to_system_prompt_addition(self) -> str:
        """Get skills as a system prompt addition."""
        combined = self.get_combined_instructions()
        if combined:
            skill_names = ", ".join(self.list())
            return (
                f"\n\n"
                f"# ⚡ ACTIVE SKILLS\n\n"
                f"You have access to the following skills: {skill_names}\n"
                f"These skills provide specialized knowledge and instructions. "
                f"READ AND FOLLOW the skill instructions below when they are relevant to the user's request.\n\n"
                f"{combined}\n\n"
                f"# Instructions for using skills:\n"
                f"1. When the user's request matches a skill's purpose, follow that skill's instructions.\n"
                f"2. Skills may reference scripts, references, or assets - these are available in the skill directory.\n"
                f"3. Use your available tools (shell, write_file, etc.) to execute the skill's instructions.\n"
            )
        return ""
    
    def get_resource_path(self, skill_name: str, resource_type: str, resource_name: str) -> Optional[Path]:
        """
        Get path to a specific resource within a skill.
        
        Args:
            skill_name: Name of the skill
            resource_type: Type of resource ('scripts', 'references', 'assets')
            resource_name: Name of the resource file
            
        Returns:
            Path to the resource or None if not found
        """
        skill = self._skills.get(skill_name)
        if not skill:
            return None
        
        resource_map = {
            'scripts': skill.scripts_dir,
            'references': skill.references_dir,
            'assets': skill.assets_dir,
        }
        
        resource_dir = resource_map.get(resource_type)
        if resource_dir:
            resource_path = resource_dir / resource_name
            return resource_path if resource_path.exists() else None
        return None
    
    def get_skill_info(self) -> str:
        """Get a formatted string with all skill information for the agent."""
        if not self._skills:
            return "No active skills."
        
        lines = ["Active Skills:"]
        for name, skill in self._skills.items():
            lines.append(f"  - {name}: {skill.description}")
            if skill.scripts_dir:
                scripts = list(skill.scripts_dir.glob("*.py"))
                if scripts:
                    lines.append(f"    Scripts: {', '.join(s.name for s in scripts)}")
            if skill.references_dir:
                refs = list(skill.references_dir.glob("*.md"))
                if refs:
                    lines.append(f"    References: {', '.join(r.name for r in refs)}")
        return "\n".join(lines)
    
    def __len__(self) -> int:
        return len(self._skills)
    
    def __repr__(self) -> str:
        return f"SkillRegistry(skills={list(self._skills.keys())})"


def _build_tool_section(tools: list) -> str:
    """
    Build the dynamic tool section for system prompt.
    
    This function creates a markdown table listing all available tools
    with their descriptions and argument examples for use in the agent's
    system prompt.
    
    Args:
        tools: List of Tool objects from the tool registry
        
    Returns:
        Formatted markdown string with tool reference table
    """
    if not tools:
        return ""
    
    lines = ["### Tool Reference (only use if available)"]
    lines.append("")
    lines.append("| Tool | When to use | Arguments |")
    lines.append("|------|-------------|-----------|")
    
    for tool in tools:
        # Get tool name and description
        name = getattr(tool, 'name', str(tool))
        desc = getattr(tool, 'description', '')
        params = getattr(tool, 'params', [])
        
        # Build arguments example
        if params:
            param_pairs = []
            for p in params:
                p_name = getattr(p, 'name', str(p))
                p_type = getattr(p, 'type', 'string')
                if p_type == 'string':
                    param_pairs.append(f'"{p_name}": "..."')
                elif p_type in ('number', 'integer', 'float'):
                    param_pairs.append(f'"{p_name}": 0')
                else:
                    param_pairs.append(f'"{p_name}": ...')
            args_example = "{" + ", ".join(param_pairs) + "}"
        else:
            args_example = "{}"
        
        # Truncate description if too long for table
        if len(desc) > 80:
            desc = desc[:77] + "..."
        
        lines.append(f"| {name} | {desc} | `{args_example}` |")
    
    # Add critical rule
    lines.append("")
    lines.append("**CRITICAL RULE**: Only use tools that are listed above. If a tool is not in this table, it is NOT available.")
    
    return "\n".join(lines)