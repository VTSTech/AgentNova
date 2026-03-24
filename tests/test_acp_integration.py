#!/usr/bin/env python3
"""
AgentNova R02 + ACP Integration Test
====================================

Tests sub-agent orchestration with ACP monitoring.

Uses centralized config from agentnova/config.py

Written for VTSTech AgentNova R02 + ACP v1.0.2
"""

import sys
import os
import time

# Add AgentNova package to path (parent directory)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentnova import (
    Agent, Orchestrator, AgentCard,
    ACPPlugin,
    DEFAULT_MODEL
)
from agentnova.tools import make_builtin_registry

print(f"""
╔═══════════════════════════════════════════════════════════════════╗
║     ⚛️ AgentNova R02 + ACP Integration Test                        ║
╠═══════════════════════════════════════════════════════════════════╣
║  Using centralized config from agentnova/config.py                ║
║  Model:  {DEFAULT_MODEL:<48} ║
╚═══════════════════════════════════════════════════════════════════╝
""")

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 1: Basic Agent with ACP Plugin
# ═══════════════════════════════════════════════════════════════════════════════

def test_basic_agent():
    print("\n" + "="*60)
    print("TEST 1: Basic Agent with ACP Plugin")
    print("="*60)
    
    # Create ACP plugin (uses config defaults)
    acp = ACPPlugin(debug=True, agent_name="AgentNova-Basic")
    
    status = acp.get_status()
    if "error" in status:
        print(f"WARNING: ACP not reachable: {status['error']}")
        print("Skipping test...")
        return
    
    print(f"ACP Connected: {status.get('session_tokens', 0)} tokens used")
    
    agent = Agent(
        model=DEFAULT_MODEL,
        system_prompt="You are a helpful assistant. Be concise.",
    )
    
    print("\nSending: 'What is 2+2? Answer briefly.'")
    start = time.time()
    
    try:
        result = agent.run("What is 2+2? Answer briefly.")
        elapsed = time.time() - start
        print(f"\nResponse ({elapsed:.1f}s): {result.final_answer}")
        
        status = acp.get_status()
        print(f"ACP Tokens: {status.get('session_tokens', 0):,}")
        # Test passed
        
    except StopIteration as e:
        print(f"STOPPED by ACP: {e}")
        assert False, f"ACP stopped: {e}"
    except Exception as e:
        print(f"ERROR: {e}")
        raise

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 2: Agent with Tools + ACP
# ═══════════════════════════════════════════════════════════════════════════════

def test_tool_agent():
    print("\n" + "="*60)
    print("TEST 2: Agent with Tools + ACP Monitoring")
    print("="*60)
    
    acp = ACPPlugin(debug=True, agent_name="AgentNova-Tool")
    
    status = acp.get_status()
    if "error" in status:
        print(f"WARNING: ACP not reachable: {status['error']}")
        print("Skipping test...")
        return
    
    tools = make_builtin_registry().subset(["calculator"])
    
    agent = Agent(
        model=DEFAULT_MODEL,
        tools=tools,
        system_prompt="You have a calculator tool. Use it for math questions.",
        max_steps=5,
    )
    
    print("\nSending: 'What is 25 times 17? Use the calculator.'")
    start = time.time()
    
    try:
        run = agent.run("What is 25 times 17? Use the calculator.")
        elapsed = time.time() - start
        
        print(f"\nAnswer ({elapsed:.1f}s): {run.final_answer}")
        
        status = acp.get_status()
        print(f"ACP Tokens: {status.get('session_tokens', 0):,}")
        # Test passed
        
    except StopIteration as e:
        print(f"STOPPED by ACP: {e}")
        assert False, f"ACP stopped: {e}"
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 3: Multi-Agent Orchestrator + ACP
# ═══════════════════════════════════════════════════════════════════════════════

def test_orchestrator():
    print("\n" + "="*60)
    print("TEST 3: Multi-Agent Orchestrator + ACP")
    print("="*60)
    
    acp = ACPPlugin(debug=True, agent_name="AgentNova-Orchestrator")
    
    status = acp.get_status()
    if "error" in status:
        print(f"WARNING: ACP not reachable: {status['error']}")
        print("Skipping test...")
        return
    
    coder = Agent(
        model=DEFAULT_MODEL,
        system_prompt="You write Python code. Be concise.",
    )
    
    math_agent = Agent(
        model=DEFAULT_MODEL,
        system_prompt="You solve math problems. Be accurate.",
    )
    
    orch = Orchestrator(
        agents=[
            AgentCard("coder", coder, "Writing Python code"),
            AgentCard("math", math_agent, "Solving math problems"),
        ],
        router_model=DEFAULT_MODEL,
        mode="router"
    )
    
    print("\nSending: 'Write a Python function to check if a number is even'")
    start = time.time()
    
    try:
        result = orch.run("Write a Python function to check if a number is even. Just the code.")
        elapsed = time.time() - start
        
        print(f"\nChosen Agent: {result.chosen_agent}")
        print(f"Time: {elapsed:.1f}s")
        print(f"Answer:\n{result.final_answer}")
        
        acp.add_note("insight", f"Orchestrator routed to {result.chosen_agent} agent")
        
        status = acp.get_status()
        print(f"ACP Tokens: {status.get('session_tokens', 0):,}")
        # Test passed
        
    except StopIteration as e:
        print(f"STOPPED by ACP: {e}")
        assert False, f"ACP stopped: {e}"
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Run tests manually (not via pytest)."""
    results = []
    
    for name, test_func in [
        ("Basic Agent", test_basic_agent),
        ("Tool Agent", test_tool_agent),
        ("Orchestrator", test_orchestrator),
    ]:
        try:
            test_func()
            results.append((name, True))
        except Exception as e:
            print(f"FAILED: {e}")
            results.append((name, False))
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")

if __name__ == "__main__":
    main()