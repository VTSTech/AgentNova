"""
⚛️ localclaw - DEPRECATED - Use agentnova instead

This package has been renamed to 'agentnova'.
Install: pip install agentnova
Import: import agentnova
CLI: agentnova run "prompt"

This skeleton package exists for backward compatibility only.
It simply re-exports everything from agentnova.

Repository: https://github.com/VTSTech/AgentNova
"""

import warnings
import sys

# Show deprecation warning on import
warnings.warn(
    "\n"
    "╔══════════════════════════════════════════════════════════════╗\n"
    "║  'localclaw' has been renamed to 'agentnova'                 ║\n"
    "║                                                              ║\n"
    "║  Please update your imports:                                 ║\n"
    "║      Old: import localclaw                                   ║\n"
    "║      New: import agentnova                                   ║\n"
    "║                                                              ║\n"
    "║  And your CLI commands:                                      ║\n"
    "║      Old: localclaw run \"prompt\"                             ║\n"
    "║      New: agentnova run \"prompt\"                             ║\n"
    "║                                                              ║\n"
    "║  Install: pip install agentnova                              ║\n"
    "║  Repo: https://github.com/VTSTech/AgentNova                  ║\n"
    "╚══════════════════════════════════════════════════════════════╝\n",
    DeprecationWarning,
    stacklevel=2
)

# Re-export everything from agentnova
try:
    from agentnova import *
    from agentnova import __version__, __author__, __author_email__, __url__, __website__
    
    # Re-export version info under localclaw namespace
    __version__ = __version__
    __author__ = __author__
    __author_email__ = __author_email__
    __url__ = __url__
    __website__ = __website__
    
except ImportError:
    raise ImportError(
        "agentnova is not installed. "
        "Please install it with: pip install agentnova"
    )


def main():
    """CLI entry point - redirects to agentnova CLI."""
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  'localclaw' has been renamed to 'agentnova'                 ║")
    print("║                                                              ║")
    print("║  Redirecting to agentnova CLI...                             ║")
    print("║                                                              ║")
    print("║  Please use 'agentnova' command directly in the future.      ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    
    # Import and run agentnova CLI
    from agentnova.cli import main as agentnova_main
    return agentnova_main()


if __name__ == "__main__":
    main()
