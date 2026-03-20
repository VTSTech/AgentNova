"""
examples/12_batch_operations.py
--------------------------------
Demonstrate ACP batch operations for efficient multi-file processing.

Demonstrates:
- batch_start() for multiple activities
- batch_complete() for completing multiple activities
- batch_action() for mixed operations
- Token savings from batching

With CLI:
  agentnova test 12 --acp
  agentnova test 12_acp

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
parser = argparse.ArgumentParser(description="AgentNova Batch Operations")
add_shared_args(parser)
args = parser.parse_args()
config = parse_shared_args(args)

# Check for ACP support
USE_ACP = config.acp
if not USE_ACP:
    print("⚠️ This demo requires ACP. Run with --acp flag or AGENTNOVA_ACP=1")
    print("   Example: agentnova test 12 --acp")
    sys.exit(0)

from agentnova.acp_plugin import ACPPlugin

BACKEND_NAME = AGENTNOVA_BACKEND.upper()
DEBUG = config.debug


def main():
    print("🦞 AgentNova R04 - Batch Operations Demo (ACP)")
    print("=" * 60)
    
    # ── Create and bootstrap ACP ─────────────────────────────────
    acp = ACPPlugin(
        agent_name="AgentNova-BatchDemo",
        model_name="batch-ops",
        debug=DEBUG,
    )
    
    bootstrap = acp.bootstrap(claim_primary=False)
    acp_connected = bootstrap.get("status") is not None
    print(f"ACP: {'connected' if acp_connected else 'unavailable'}\n")
    
    if not acp_connected:
        print("❌ ACP connection required for this demo")
        return
    
    # ========================================
    # DEMO 1: batch_start - Start multiple activities
    # ========================================
    print("=" * 60)
    print("📦 DEMO 1: batch_start() - Multiple READ activities")
    print("=" * 60)
    
    # Simulate reading multiple files
    files = [
        {"action": "READ", "target": "/project/src/main.py", "content_size": 5000, "details": "Main entry point"},
        {"action": "READ", "target": "/project/src/utils.py", "content_size": 3000, "details": "Utility functions"},
        {"action": "READ", "target": "/project/src/config.py", "content_size": 1500, "details": "Configuration"},
        {"action": "READ", "target": "/project/README.md", "content_size": 2000, "details": "Documentation"},
    ]
    
    print(f"   Starting {len(files)} activities in ONE request...")
    t0 = time.time()
    result = acp.batch_start(files)
    elapsed = (time.time() - t0) * 1000
    
    print(f"   Result: success={result.get('success')}")
    print(f"   Activities started: {len(result.get('results', []))}")
    print(f"   Time: {elapsed:.1f}ms")
    
    # Get activity IDs
    activity_ids = [r.get("activity_id") for r in result.get("results", []) if r.get("success")]
    print(f"   Activity IDs: {activity_ids[:3]}...")
    
    # ========================================
    # DEMO 2: batch_complete - Complete multiple activities
    # ========================================
    print("\n" + "=" * 60)
    print("📦 DEMO 2: batch_complete() - Complete multiple activities")
    print("=" * 60)
    
    completions = [
        {"activity_id": aid, "result": "File read successfully", "content_size": 500}
        for aid in activity_ids
    ]
    
    print(f"   Completing {len(completions)} activities in ONE request...")
    t0 = time.time()
    result = acp.batch_complete(completions)
    elapsed = (time.time() - t0) * 1000
    
    print(f"   Result: success={result.get('success')}")
    print(f"   Time: {elapsed:.1f}ms")
    
    # ========================================
    # DEMO 3: batch_action - Mixed operations
    # ========================================
    print("\n" + "=" * 60)
    print("📦 DEMO 3: batch_action() - Mixed start/complete")
    print("=" * 60)
    
    # Get some new activity IDs first
    start_result = acp.batch_start([
        {"action": "READ", "target": "/file1.py"},
        {"action": "READ", "target": "/file2.py"},
    ])
    ids_to_complete = [r.get("activity_id") for r in start_result.get("results", []) if r.get("success")]
    
    # Mixed batch: complete old + start new
    operations = [
        {"type": "complete", "activity_id": ids_to_complete[0], "result": "Done with file1"},
        {"type": "start", "action": "READ", "target": "/file3.py", "details": "Third file"},
        {"type": "complete", "activity_id": ids_to_complete[1], "result": "Done with file2"},
        {"type": "start", "action": "EDIT", "target": "/output.py", "details": "Writing results"},
    ]
    
    print(f"   Executing {len(operations)} mixed operations...")
    t0 = time.time()
    result = acp.batch_action(operations)
    elapsed = (time.time() - t0) * 1000
    
    print(f"   Result: success={result.get('success')}")
    print(f"   Operations completed: {len(result.get('results', []))}")
    print(f"   Time: {elapsed:.1f}ms")
    
    # Show breakdown
    starts = sum(1 for r in result.get("results", []) if r.get("operation") == "start")
    completes = sum(1 for r in result.get("results", []) if r.get("operation") == "complete")
    print(f"   Breakdown: {starts} starts, {completes} completes")
    
    # ========================================
    # DEMO 4: Compare batch vs individual requests
    # ========================================
    print("\n" + "=" * 60)
    print("📊 DEMO 4: Performance comparison")
    print("=" * 60)
    
    # Individual requests
    print("\n   Individual requests (5 separate calls):")
    t0 = time.time()
    for i in range(5):
        acp._request("/api/action", "POST", {
            "action": "READ",
            "target": f"/individual/file{i}.py",
            "metadata": acp._build_metadata(),
        })
    individual_time = (time.time() - t0) * 1000
    print(f"   Time: {individual_time:.1f}ms")
    
    # Batch request
    print("\n   Batch request (1 call with 5 operations):")
    t0 = time.time()
    acp.batch_start([
        {"action": "READ", "target": f"/batch/file{i}.py"}
        for i in range(5)
    ])
    batch_time = (time.time() - t0) * 1000
    print(f"   Time: {batch_time:.1f}ms")
    
    savings = (1 - batch_time / individual_time) * 100 if individual_time > 0 else 0
    print(f"\n   💡 Batch is {savings:.0f}% faster ({individual_time:.0f}ms → {batch_time:.0f}ms)")
    
    # ========================================
    # SUMMARY
    # ========================================
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    
    status = acp.get_status()
    agent_tokens = acp.get_agent_tokens()
    
    print(f"   Session tokens: {status.get('session_tokens', 0)}")
    print(f"   Agent tokens: {agent_tokens}")
    
    print("""
💡 Batch Operations Benefits:

   1. Fewer HTTP requests → Less overhead
   2. Atomic operations → All succeed or all fail
   3. Consistent timestamps → Better activity tracking
   4. Token tracking → Accurate in single request

   When to use:
   - Reading multiple files at once
   - Completing multiple activities together
   - Mixed operations (complete old + start new)

   API: POST /api/activity/batch
   Max: 50 operations per batch
    """)


if __name__ == "__main__":
    main()
