"""
⚛️ LocalClaw → AgentNova Redirect

This package has been renamed to AgentNova.
All functionality is now available under the 'agentnova' package.

Status: Alpha

Written by VTSTech — https://www.vts-tech.org

Migration Guide:
    # Old (deprecated)
    from localclaw import Agent
    
    # New (recommended)
    from agentnova import Agent

CLI:
    # Both commands work identically
    localclaw run "What is 2+2?"
    agentnova run "What is 2+2?"
"""

import sys
import warnings

# Issue deprecation warning
warnings.warn(
    "The 'localclaw' package has been renamed to 'agentnova'. "
    "Please update your imports: 'from agentnova import ...' instead of 'from localclaw import ...'",
    DeprecationWarning,
    stacklevel=2
)

# Re-export everything from agentnova
from agentnova import *
from agentnova import __version__, __author__, __status__


def main():
    """Entry point for localclaw CLI command."""
    from agentnova.cli import main as agentnova_main
    return agentnova_main()


__all__ = [
    "__version__",
    "__author__",
    "__status__",
    "main",
]
