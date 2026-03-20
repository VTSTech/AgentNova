"""
examples/13_shutdown_demo.py
-----------------------------
Demonstrate graceful ACP session shutdown.

Demonstrates:
- shutdown() method
- Session summary export
- Shutdown nudge handling
- Session cleanup

With CLI:
  agentnova test 13 --acp
  agentnova test 13_acp

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

import os
import sys
import time
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentnova import Agent, get_default_client, get_tool_support, AGENTNOVA_BACKEND
from agentnova.shared_args import add_shared_args, parse_shared_args

# Parse CLI args (with env var fallbacks)
parser = argparse.ArgumentParser(description="AgentNova Shutdown Demo")
add_shared_args(parser)
args = parser.parse_args()
config = parse_shared_args(args)

# Check for ACP support
USE_ACP = config.acp
if not USE_ACP:
    print("⚠️ This demo requires ACP. Run with --acp flag or AGENTNOVA_ACP=1")
    print("   Example: agentnova test 13 --acp")
    sys.exit(0)

from agentnova.acp_plugin import ACPPlugin

BACKEND_NAME = AGENTNOVA_BACKEND.upper()
DEBUG = config.debug


def main():
    print("🦞 AgentNova R04 - Shutdown Demo (ACP)")
    print("=" * 60)
    
    # ── Create and bootstrap ACP ─────────────────────────────────
    acp = ACPPlugin(
        agent_name="AgentNova-ShutdownDemo",
        model_name="shutdown-demo",
        debug=DEBUG,
        on_nudge=lambda n: print(f"   📢 Nudge received: {n.get('message', '')[:80]}"),
    )
    
    bootstrap = acp.bootstrap(claim_primary=False)
    acp_connected = bootstrap.get("status") is not None
    print(f"ACP: {'connected' if acp_connected else 'unavailable'}\n")
    
    if not acp_connected:
        print("❌ ACP connection required for this demo")
        return
    
    # ========================================
    # SESSION ACTIVITIES
    # ========================================
    print("📝 Logging some activities...")
    
    for i in range(5):
        acp.log_user_message(f"Task {i+1}: Process data")
        acp.log_assistant_message(f"Task {i+1} completed successfully")
    
    # Add a decision note
    acp.add_note("decision", "Decided to use batch processing for efficiency")
    acp.add_note("context", "Processed 5 tasks in demo session")
    
    # Show session state
    status = acp.get_status()
    print(f"\n📊 Session state before shutdown:")
    print(f"   Session tokens: {status.get('session_tokens', 0)}")
    print(f"   Running activities: {status.get('running_count', 0)}")
    print(f"   Session duration: {status.get('session', {}).get('elapsed_seconds', 0)}s")
    
    # ========================================
    # GRACEFUL SHUTDOWN
    # ========================================
    print("\n" + "=" * 60)
    print("🛑 Initiating graceful shutdown...")
    print("=" * 60)
    
    print("\n   Calling acp.shutdown()...")
    print("   This will:")
    print("   1. Export session summary for context recovery")
    print("   2. Cancel any running activities")
    print("   3. Send shutdown nudge to other agents")
    print("   4. Stop the ACP server after delay")
    
    # Note: This WILL shut down the ACP server!
    # In production, only call this when you're truly done
    response = acp.shutdown(
        reason="Demo session complete - graceful shutdown",
        export_summary=True,
    )
    
    print(f"\n   📤 Shutdown response:")
    print(f"      Success: {response.get('success')}")
    print(f"      Message: {response.get('message')}")
    
    if response.get('summary_exported'):
        print(f"      Summary path: {response.get('summary_path')}")
    
    if response.get('cancelled_activities'):
        print(f"      Cancelled: {response.get('cancelled_activities')} activities")
    
    # ========================================
    # SHUTDOWN NUDGE
    # ========================================
    print("\n" + "=" * 60)
    print("📢 Shutdown Nudge")
    print("=" * 60)
    
    print("""
   When shutdown is called, any connected agents will receive
   a nudge on their next /api/action call:
   
   {
     "nudge": {
       "message": "SESSION ENDING: ...",
       "priority": "urgent",
       "requires_ack": true,
       "type": "shutdown"
     }
   }
   
   Agents should:
   1. Call POST /api/nudge/ack to acknowledge
   2. Wrap up any final thoughts
   3. Inform the user session is ending
   4. Stop further activities
    """)
    
    # ========================================
    # UTILITY: is_shutdown_nudge()
    # ========================================
    print("=" * 60)
    print("🔍 Checking for shutdown nudge")
    print("=" * 60)
    
    # Simulate a nudge check
    test_nudge = {"type": "shutdown", "message": "Session ending"}
    is_shutdown = acp.is_shutdown_nudge(test_nudge)
    print(f"   is_shutdown_nudge({test_nudge}): {is_shutdown}")
    
    test_nudge2 = {"type": "guidance", "message": "Focus on API"}
    is_shutdown2 = acp.is_shutdown_nudge(test_nudge2)
    print(f"   is_shutdown_nudge({test_nudge2}): {is_shutdown2}")
    
    # ========================================
    # SUMMARY
    # ========================================
    print("\n" + "=" * 60)
    print("✅ Shutdown Demo Complete")
    print("=" * 60)
    
    print("""
💡 Key Points:

   1. shutdown() should only be called when session is truly done
   2. It stops the ACP server - affects ALL connected agents
   3. Summary export enables context recovery for future sessions
   4. Shutdown nudge notifies other agents to wrap up

   For AgentNova (secondary agent):
   - Don't call shutdown() if Super Z is still active
   - Just disconnect gracefully, let primary handle shutdown
   - Use is_shutdown_nudge() to detect if you should stop

   Example shutdown flow:
   ────────────────────────
   if received_nudge and acp.is_shutdown_nudge(received_nudge):
       acp.ack_nudge()
       print("Session ending, goodbye!")
       # Clean up and exit
    """)


if __name__ == "__main__":
    main()
