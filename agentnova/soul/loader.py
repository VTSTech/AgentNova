"""
⚛️ AgentNova — Soul Loader

Load and parse ClawSouls Soul Spec v0.5 packages.

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Union

from .types import (
    SoulManifest, Author, Compatibility, SoulFiles, SoulExamples,
    Disclosure, RecommendedSkill, HardwareConstraints, PhysicalSafety,
    Safety, Sensor, Actuator, Environment, InteractionMode,
    Mobility, ContactPolicy, parse_legacy_skills,
)


class SoulLoader:
    """
    Load and parse Soul Spec packages.
    
    Supports:
    - soul.json manifest parsing
    - Progressive disclosure (Level 1-3)
    - Persona file loading (SOUL.md, IDENTITY.md, etc.)
    - Legacy v0.3 format backward compatibility
    
    Example:
        loader = SoulLoader()
        soul = loader.load("/path/to/soul/package")
        print(soul.get_summary())
        system_prompt = loader.build_system_prompt(soul, level=2)
    """
    
    def __init__(self, strict: bool = False):
        """
        Initialize the loader.
        
        Args:
            strict: If True, fail on validation errors. If False, warn only.
        """
        self.strict = strict
        self._cache: dict[str, SoulManifest] = {}
    
    def _resolve_soul_path(self, path: Path) -> Optional[Path]:
        """
        Resolve a soul path by searching in multiple locations.
        
        Search order:
        1. Absolute path (as-is)
        2. Relative to current working directory
        3. Relative to agentnova package directory (souls/)
        4. As a built-in soul name (e.g., "nova-helper" -> souls/nova-helper)
        
        Returns:
            Resolved Path or None if not found
        """
        # 1. If absolute path, check if it exists
        if path.is_absolute():
            if path.exists():
                return path
            return None
        
        # 2. Try relative to current working directory
        cwd_path = Path.cwd() / path
        if cwd_path.exists():
            return cwd_path
        
        # 3. Try relative to agentnova package directory
        try:
            import agentnova
            if agentnova.__file__ is not None:
                package_dir = Path(agentnova.__file__).parent
                package_path = package_dir / "souls" / path
                if package_path.exists():
                    return package_path
                # Also try without souls/ prefix if path looks like a soul name
                if "/" not in str(path) and "\\" not in str(path):
                    package_path = package_dir / "souls" / path
                    if package_path.exists():
                        return package_path
            else:
                # Fallback: try importlib.resources for namespace packages (Windows pip install)
                try:
                    import importlib.resources as resources
                    if hasattr(resources, 'files'):
                        package_path = resources.files('agentnova') / 'souls' / path
                        if package_path.is_dir():
                            return Path(str(package_path))
                except (ImportError, TypeError, AttributeError):
                    pass
        except (ImportError, TypeError):
            pass
        
        # 4. Try as soul name in package souls directory
        try:
            import agentnova
            if agentnova.__file__ is not None:
                package_dir = Path(agentnova.__file__).parent
                # Check if it's a simple name (no path separators)
                soul_name = str(path).replace("/", "").replace("\\", "")
                if soul_name == str(path):
                    # It's a simple name, look for it in souls/
                    soul_path = package_dir / "souls" / soul_name
                    if soul_path.exists():
                        return soul_path
                    # Also try with .json extension
                    json_path = package_dir / "souls" / soul_name / "soul.json"
                    if json_path.exists():
                        return soul_path
            else:
                # Fallback: try importlib.resources for namespace packages (Windows pip install)
                try:
                    import importlib.resources as resources
                    soul_name = str(path).replace("/", "").replace("\\", "")
                    if soul_name == str(path) and hasattr(resources, 'files'):
                        soul_path = resources.files('agentnova') / 'souls' / soul_name
                        if soul_path.is_dir():
                            return Path(str(soul_path))
                except (ImportError, TypeError, AttributeError):
                    pass
        except (ImportError, ValueError, TypeError):
            pass
        
        # 5. Final check - does the original path exist?
        if path.exists():
            return path
        
        return None
    
    def load(self, path: Union[str, Path], level: int = 2) -> SoulManifest:
        """
        Load a soul package from a directory or soul.json file.
        
        Args:
            path: Path to soul directory or soul.json file
            level: Progressive disclosure level (1-3)
                1 = Quick Scan (soul.json only)
                2 = Full Read (soul.json + SOUL.md + IDENTITY.md)
                3 = Deep Dive (all files including STYLE.md, examples)
        
        Returns:
            SoulManifest with loaded content
        """
        path = Path(path)
        
        # Try to resolve the path in multiple locations
        resolved_path = self._resolve_soul_path(path)
        if resolved_path is None:
            raise ValueError(f"Not a valid soul path: {path}")
        
        path = resolved_path
        
        # Determine soul directory and manifest path
        if path.is_file() and path.name == "soul.json":
            soul_dir = path.parent
            manifest_path = path
        elif path.is_dir():
            soul_dir = path
            manifest_path = path / "soul.json"
        else:
            raise ValueError(f"Not a valid soul path: {path}")
        
        if not manifest_path.exists():
            raise FileNotFoundError(f"No soul.json found at: {manifest_path}")
        
        # Check cache
        cache_key = f"{soul_dir}:{level}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Parse manifest
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        manifest = self._parse_manifest(data, soul_dir)
        
        # Validate
        issues = manifest.validate()
        if issues and self.strict:
            raise ValueError(f"Validation errors: {issues}")
        
        # Load persona files based on disclosure level
        if level >= 2:
            self._load_level_2(manifest, soul_dir)
        if level >= 3:
            self._load_level_3(manifest, soul_dir)
        
        # Cache and return
        self._cache[cache_key] = manifest
        return manifest
    
    def _parse_manifest(self, data: dict, soul_dir: Path) -> SoulManifest:
        """Parse soul.json into SoulManifest."""
        
        # Parse author
        author_data = data.get("author", {})
        author = Author(
            name=author_data.get("name", "Unknown"),
            github=author_data.get("github"),
            email=author_data.get("email"),
        )
        
        # Parse compatibility
        compat_data = data.get("compatibility", {})
        compatibility = Compatibility(
            openclaw=compat_data.get("openclaw"),
            models=compat_data.get("models", []),
            frameworks=compat_data.get("frameworks", []),
            min_token_context=compat_data.get("minTokenContext"),
        )
        
        # Parse recommended skills (support both formats)
        skills_data = data.get("recommendedSkills", [])
        if not skills_data and "skills" in data:
            # Legacy format
            skills_data = parse_legacy_skills(data["skills"])
            skills_data = [
                {"name": s.name, "required": s.required}
                for s in skills_data
            ]
        
        recommended_skills = []
        for sk in skills_data:
            if isinstance(sk, str):
                recommended_skills.append(RecommendedSkill(name=sk))
            else:
                recommended_skills.append(RecommendedSkill(
                    name=sk.get("name", ""),
                    version=sk.get("version"),
                    required=sk.get("required", False),
                ))
        
        # Parse files
        files_data = data.get("files", {})
        files = SoulFiles(
            soul=files_data.get("soul", "SOUL.md"),
            identity=files_data.get("identity"),
            agents=files_data.get("agents"),
            heartbeat=files_data.get("heartbeat"),
            style=files_data.get("style"),
            user_template=files_data.get("userTemplate"),
            avatar=files_data.get("avatar"),
        )
        
        # Parse examples
        examples = None
        if "examples" in data:
            ex_data = data["examples"]
            examples = SoulExamples(
                good=ex_data.get("good"),
                bad=ex_data.get("bad"),
            )
        
        # Parse disclosure
        disclosure = None
        if "disclosure" in data:
            disc_data = data["disclosure"]
            disclosure = Disclosure(
                summary=disc_data.get("summary"),
            )
        
        # Parse hardware constraints (embodied agents)
        hardware = None
        if "hardwareConstraints" in data:
            hw_data = data["hardwareConstraints"]
            hardware = HardwareConstraints(
                has_display=hw_data.get("hasDisplay", False),
                has_speaker=hw_data.get("hasSpeaker", False),
                has_microphone=hw_data.get("hasMicrophone", False),
                has_camera=hw_data.get("hasCamera", False),
                mobility=Mobility(hw_data.get("mobility", "stationary")),
                manipulator=hw_data.get("manipulator", False),
            )
        
        # Parse safety
        safety = None
        if "safety" in data:
            safety_data = data["safety"]
            physical = None
            if "physical" in safety_data:
                phys_data = safety_data["physical"]
                physical = PhysicalSafety(
                    contact_policy=ContactPolicy(phys_data.get("contactPolicy", "no-contact")),
                    emergency_protocol=phys_data.get("emergencyProtocol", "stop"),
                    operating_zone=phys_data.get("operatingZone", "indoor"),
                    max_speed=phys_data.get("maxSpeed"),
                )
            safety = Safety(physical=physical)
        
        # Parse sensors
        sensors = []
        for name, sensor_data in data.get("sensors", {}).items():
            if isinstance(sensor_data, bool):
                sensors.append(Sensor(name=name))
            else:
                sensors.append(Sensor(
                    name=name,
                    type=sensor_data.get("type"),
                    range=sensor_data.get("range"),
                    fov=sensor_data.get("fov"),
                    resolution=sensor_data.get("resolution"),
                    fps=sensor_data.get("fps"),
                    channels=sensor_data.get("channels"),
                ))
        
        # Parse actuators
        actuators = []
        for name, act_data in data.get("actuators", {}).items():
            actuators.append(Actuator(
                name=name,
                type=act_data.get("type"),
                max_speed=act_data.get("maxSpeed"),
                payload=act_data.get("payload"),
                reach=act_data.get("reach"),
                force=act_data.get("force"),
                dof=act_data.get("dof"),
                resolution=act_data.get("resolution"),
            ))
        
        # Build manifest
        return SoulManifest(
            spec_version=data.get("specVersion", "0.5"),
            name=data.get("name", "unknown"),
            display_name=data.get("displayName", "Unknown"),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=author,
            license=data.get("license", "MIT"),
            tags=data.get("tags", []),
            category=data.get("category", "general"),
            compatibility=compatibility,
            allowed_tools=data.get("allowedTools", []),
            recommended_skills=recommended_skills,
            files=files,
            examples=examples,
            disclosure=disclosure,
            deprecated=data.get("deprecated", False),
            superseded_by=data.get("supersededBy"),
            repository=data.get("repository"),
            environment=Environment(data.get("environment", "virtual")),
            interaction_mode=InteractionMode(data.get("interactionMode", "text")),
            hardware_constraints=hardware,
            safety=safety,
            sensors=sensors,
            actuators=actuators,
        )
    
    def _load_level_2(self, manifest: SoulManifest, soul_dir: Path) -> None:
        """Load Level 2 files: SOUL.md + IDENTITY.md."""
        # Load SOUL.md (required)
        soul_path = soul_dir / manifest.files.soul
        if soul_path.exists():
            manifest.soul_content = soul_path.read_text(encoding="utf-8")
        
        # Load IDENTITY.md (optional)
        if manifest.files.identity:
            identity_path = soul_dir / manifest.files.identity
            if identity_path.exists():
                manifest.identity_content = identity_path.read_text(encoding="utf-8")
    
    def _load_level_3(self, manifest: SoulManifest, soul_dir: Path) -> None:
        """Load Level 3 files: AGENTS.md, STYLE.md, HEARTBEAT.md, examples."""
        # Load AGENTS.md
        if manifest.files.agents:
            agents_path = soul_dir / manifest.files.agents
            if agents_path.exists():
                manifest.agents_content = agents_path.read_text(encoding="utf-8")
        
        # Load STYLE.md
        if manifest.files.style:
            style_path = soul_dir / manifest.files.style
            if style_path.exists():
                manifest.style_content = style_path.read_text(encoding="utf-8")
        
        # Load HEARTBEAT.md
        if manifest.files.heartbeat:
            heartbeat_path = soul_dir / manifest.files.heartbeat
            if heartbeat_path.exists():
                manifest.heartbeat_content = heartbeat_path.read_text(encoding="utf-8")
    
    def build_system_prompt(
        self,
        manifest: SoulManifest,
        level: int = 2,
        include_identity: bool = True,
    ) -> str:
        """
        Build a system prompt from the soul manifest.
        
        Args:
            manifest: Loaded soul manifest
            level: Progressive disclosure level
            include_identity: Whether to include IDENTITY.md content
        
        Returns:
            System prompt string
        """
        parts = []
        
        # Level 1: Basic info
        parts.append(f"# {manifest.display_name}")
        parts.append(f"\n{manifest.description}")
        
        if manifest.disclosure and manifest.disclosure.summary:
            parts.append(f"\n{manifest.disclosure.summary}")
        
        # Level 2: Core persona
        if level >= 2:
            if manifest.soul_content:
                parts.append(f"\n\n## Persona\n\n{manifest.soul_content}")
            
            if include_identity and manifest.identity_content:
                parts.append(f"\n\n## Identity\n\n{manifest.identity_content}")
        
        # Level 3: Extended behavior
        if level >= 3:
            if manifest.style_content:
                parts.append(f"\n\n## Style Guidelines\n\n{manifest.style_content}")
            
            if manifest.agents_content:
                parts.append(f"\n\n## Agent Behavior\n\n{manifest.agents_content}")
            
            if manifest.heartbeat_content:
                parts.append(f"\n\n## Heartbeat\n\n{manifest.heartbeat_content}")
        
        # Add constraints for embodied agents
        if manifest.environment != Environment.VIRTUAL:
            parts.append(f"\n\n## Environment")
            parts.append(f"\nYou are an **{manifest.environment.value}** agent.")
            
            if manifest.interaction_mode != InteractionMode.TEXT:
                parts.append(f"\nPrimary interaction mode: {manifest.interaction_mode.value}")
            
            if manifest.hardware_constraints:
                hc = manifest.hardware_constraints
                capabilities = []
                if hc.has_display:
                    capabilities.append("display")
                if hc.has_speaker:
                    capabilities.append("speaker")
                if hc.has_microphone:
                    capabilities.append("microphone")
                if hc.has_camera:
                    capabilities.append("camera")
                if capabilities:
                    parts.append(f"\nHardware: {', '.join(capabilities)}")
            
            if manifest.safety and manifest.safety.physical:
                ps = manifest.safety.physical
                parts.append(f"\nSafety: {ps.contact_policy.value} contact policy")
        
        return "\n".join(parts)
    
    def get_allowed_tools(self, manifest: SoulManifest) -> list[str]:
        """Get the list of allowed tools for this soul."""
        return manifest.allowed_tools
    
    def get_required_skills(self, manifest: SoulManifest) -> list[str]:
        """Get the list of required skill names."""
        return [s.name for s in manifest.recommended_skills if s.required]
    
    def get_optional_skills(self, manifest: SoulManifest) -> list[str]:
        """Get the list of optional skill names."""
        return [s.name for s in manifest.recommended_skills if not s.required]


# Singleton instance for convenience
_default_loader: Optional[SoulLoader] = None


def get_soul_loader(strict: bool = False) -> SoulLoader:
    """Get the default SoulLoader instance."""
    global _default_loader
    if _default_loader is None:
        _default_loader = SoulLoader(strict=strict)
    return _default_loader


def load_soul(path: Union[str, Path], level: int = 2) -> SoulManifest:
    """Convenience function to load a soul using the default loader."""
    return get_soul_loader().load(path, level=level)


def build_system_prompt(manifest: SoulManifest, level: int = 2) -> str:
    """Convenience function to build system prompt."""
    return get_soul_loader().build_system_prompt(manifest, level=level)


def build_system_prompt_with_tools(
    manifest: SoulManifest,
    tools: list,
    level: int = 3,
) -> str:
    """
    Build a system prompt with dynamic tool injection.
    
    This replaces the static tool reference in the soul with the actual
    available tools at runtime.
    
    Args:
        manifest: Loaded soul manifest
        tools: List of Tool objects available
        level: Progressive disclosure level
    
    Returns:
        System prompt with tools injected
    """
    import re
    
    # Get base prompt
    base_prompt = build_system_prompt(manifest, level=level)
    
    # Build dynamic tool section
    tool_section = _build_tool_section(tools)
    
    # Pattern to match the static tool section in SOUL.md
    # Matches:
    # 1. ### Tool Reference header (with optional parenthetical text)
    # 2. Table header: | Tool | When to use | Arguments |
    # 3. Separator row: |------|-------------|-----------|
    # 4. One or more data rows (3-column table)
    # 5. Blank line
    # 6. **CRITICAL RULE** line
    pattern = (
        r'### Tool Reference[^\n]*\n+'
        r'\| Tool \| When to use \| Arguments \|\n'
        r'\|[-| ]+\|\n'
        r'(?:\|[^|]*\|[^|]*\|[^|]*\|[^\n]*\n)+'
        r'\n'
        r'\*\*CRITICAL RULE\*\*[^\n]*'
    )
    
    if re.search(pattern, base_prompt):
        result = re.sub(pattern, tool_section.rstrip(), base_prompt)
        return result
    else:
        # No existing tool reference, append tools
        return f"{base_prompt}\n\n{tool_section}"


def _build_tool_section(tools: list) -> str:
    """Build the dynamic tool section for system prompt."""
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
        
        # Build "when to use" from description
        short_desc = desc.split('.')[0] if desc else "No description"
        if len(short_desc) > 40:
            short_desc = short_desc[:37] + "..."
        
        lines.append(f"| `{name}` | {short_desc} | `{args_example}` |")
    
    lines.append("")
    lines.append("**CRITICAL RULE**: If a tool is NOT in the available tools list, do NOT try to use it. Respond directly instead.")
    
    return "\n".join(lines)