"""
localclaw CLI - Compatibility shim that forwards to agentnova CLI

This redirects 'python -m localclaw' to the agentnova CLI.
"""

import sys

# Show deprecation notice
print()
print("╔══════════════════════════════════════════════════════════════╗")
print("║  'localclaw' has been renamed to 'agentnova'                 ║")
print("║                                                              ║")
print("║  Please use the new command:                                 ║")
print("║      agentnova " + " ".join(sys.argv[1:]).ljust(46) + "║")
print("╚══════════════════════════════════════════════════════════════╝")
print()

# Forward to agentnova CLI
from agentnova.cli import main

if __name__ == "__main__":
    main()
