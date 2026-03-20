#!/usr/bin/env python3
"""
AgentNova + ACP Integration Test
================================

Tests sub-agent orchestration with ACP monitoring.

Uses centralized config from agentnova/config.py

Written for VTSTech AgentNova R00 + ACP v1.0.2
"""

import sys
import os

# Add AgentNova to path (parent directory)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import urllib.request
import urllib.error
import json
import time

# Import centralized config
from agentnova import OLLAMA_BASE_URL, ACP_BASE_URL, DEFAULT_MODEL

# ═══════════════════════════════════════════════════════════════════════════════
# ACP HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def acp_request(endpoint, method="GET", data=None):
    """Make authenticated request to ACP."""
    url = f"{ACP_BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"} if data else {}
    
    if data:
        req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method=method)
    else:
        req = urllib.request.Request(url, method=method)
    
    # Add basic auth
    import base64
    from agentnova import ACP_USER, ACP_PASS
    credentials = base64.b64encode(f"{ACP_USER}:{ACP_PASS}".encode()).decode()
    req.add_header("Authorization", f"Basic {credentials}")
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}

def acp_log_action(action, target, details="", priority="medium", metadata=None):
    """Log action to ACP before executing."""
    payload = {
        "action": action,
        "target": target,
        "details": details,
        "priority": priority,
        "metadata": metadata or {"agent_name": "AgentNova-Test"}
    }
    return acp_request("/api/action", "POST", payload)

def acp_complete_activity(activity_id, result, content_size=0):
    """Complete activity in ACP."""
    payload = {
        "activity_id": activity_id,
        "result": result,
        "content_size": content_size
    }
    return acp_request("/api/complete", "POST", payload)

def acp_get_status():
    """Get ACP status."""
    return acp_request("/api/status")

# ═══════════════════════════════════════════════════════════════════════════════
# AGENTNOVA TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def test_basic_agent():
    """Test 1: Basic agent chat."""
    print("\n" + "="*60)
    print("TEST 1: Basic Agent Chat")
    print("="*60)
    
    result = acp_log_action("SKILL", "AgentNova basic agent test", f"Testing basic chat with {DEFAULT_MODEL}", "high")
    activity_id = result.get("activity_id")
    print(f"ACP: Logged action {activity_id}")
    
    try:
        from agentnova import Agent
        
        agent = Agent(
            model=DEFAULT_MODEL,
            system_prompt="You are a helpful coding assistant. Be concise.",
            model_options={"num_ctx": 2048, "num_predict": 128}
        )
        
        print("\nSending: 'What is 2+2?'")
        start = time.time()
        response = agent.chat("What is 2+2?")
        elapsed = time.time() - start
        
        print(f"Response ({elapsed:.1f}s): {response}")
        
        acp_complete_activity(activity_id, f"Success: {response[:100]}")
        # Test passed
        
    except Exception as e:
        print(f"ERROR: {e}")
        acp_complete_activity(activity_id, f"Error: {str(e)[:100]}")
        raise

def test_tool_agent():
    """Test 2: Agent with tools."""
    print("\n" + "="*60)
    print("TEST 2: Agent with Tools")
    print("="*60)
    
    result = acp_log_action("SKILL", "AgentNova tool agent test", "Testing calculator tool", "high")
    activity_id = result.get("activity_id")
    print(f"ACP: Logged action {activity_id}")
    
    try:
        from agentnova import Agent, ToolRegistry
        
        registry = ToolRegistry()
        
        @registry.tool(description="Calculate mathematical expressions")
        def calculator(expression: str) -> str:
            """Evaluate a mathematical expression."""
            try:
                result = eval(expression)
                return str(result)
            except:
                return "Error evaluating expression"
        
        agent = Agent(
            model=DEFAULT_MODEL,
            tools=registry,
            system_prompt="You are a calculator assistant. Use the calculator tool for math.",
            max_steps=5,
            model_options={"num_ctx": 2048}
        )
        
        print("\nSending: 'What is 123 * 456?'")
        start = time.time()
        run = agent.run("What is 123 * 456?")
        elapsed = time.time() - start
        
        print(f"Answer ({elapsed:.1f}s): {run.final_answer}")
        run.print_trace()
        
        acp_complete_activity(activity_id, f"Success: {run.final_answer[:100]}")
        # Test passed
        
    except Exception as e:
        print(f"ERROR: {e}")
        acp_complete_activity(activity_id, f"Error: {str(e)[:100]}")
        raise

def test_orchestrator_router():
    """Test 3: Multi-agent orchestrator with router."""
    print("\n" + "="*60)
    print("TEST 3: Multi-Agent Orchestrator (Router Mode)")
    print("="*60)
    
    result = acp_log_action("SKILL", "AgentNova orchestrator test", "Testing multi-agent routing", "high")
    activity_id = result.get("activity_id")
    print(f"ACP: Logged action {activity_id}")
    
    try:
        from agentnova import Agent, Orchestrator, AgentCard
        
        coder = Agent(
            model=DEFAULT_MODEL,
            system_prompt="You are a Python coding expert. Write clean, simple code.",
            model_options={"num_ctx": 2048, "num_predict": 256}
        )
        
        explainer = Agent(
            model=DEFAULT_MODEL, 
            system_prompt="You explain concepts clearly and simply.",
            model_options={"num_ctx": 2048, "num_predict": 256}
        )
        
        orch = Orchestrator(
            agents=[
                AgentCard("coder", coder, "Writing and modifying code"),
                AgentCard("explainer", explainer, "Explaining concepts and answering questions"),
            ],
            router_model=DEFAULT_MODEL,
            mode="router"
        )
        
        print("\nSending: 'Write a Python function to check if a number is prime'")
        start = time.time()
        result = orch.run("Write a Python function to check if a number is prime")
        elapsed = time.time() - start
        
        print(f"\nChosen Agent: {result.chosen_agent}")
        print(f"Time: {elapsed:.1f}s")
        print(f"Answer:\n{result.final_answer}")
        
        acp_complete_activity(activity_id, f"Routed to {result.chosen_agent}: {result.final_answer[:100]}")
        # Test passed
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        acp_complete_activity(activity_id, f"Error: {str(e)[:100]}")
        raise

def test_builtin_tools():
    """Test 4: Built-in tools."""
    print("\n" + "="*60)
    print("TEST 4: Built-in Tools")
    print("="*60)
    
    result = acp_log_action("SKILL", "AgentNova builtin tools test", "Testing python_repl tool", "high")
    activity_id = result.get("activity_id")
    print(f"ACP: Logged action {activity_id}")
    
    try:
        from agentnova import Agent
        from agentnova.tools.builtins import BUILTIN_REGISTRY
        
        tools = BUILTIN_REGISTRY.subset(["calculator", "python_repl"])
        
        agent = Agent(
            model=DEFAULT_MODEL,
            tools=tools,
            system_prompt="You have calculator and python_repl tools. Use them when needed.",
            max_steps=8,
            model_options={"num_ctx": 2048}
        )
        
        print("\nSending: 'Calculate the fibonacci of 10 using Python'")
        start = time.time()
        run = agent.run("Calculate the fibonacci of 10 using Python. Use the python_repl tool.")
        elapsed = time.time() - start
        
        print(f"Answer ({elapsed:.1f}s): {run.final_answer}")
        run.print_trace()
        
        acp_complete_activity(activity_id, f"Success: {run.final_answer[:100]}")
        # Test passed
        
    except Exception as e:
        print(f"ERROR: {e}")
        acp_complete_activity(activity_id, f"Error: {str(e)[:100]}")
        raise

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print(f"""
╔═══════════════════════════════════════════════════════════════════╗
║     ⚛️ AgentNova R00 + ACP Integration Test                        ║
╠═══════════════════════════════════════════════════════════════════╣
║  Ollama: {OLLAMA_BASE_URL[8:48]:<48} ║
║  ACP:    {ACP_BASE_URL[8:48]:<48} ║
║  Model:  {DEFAULT_MODEL:<48} ║
╚═══════════════════════════════════════════════════════════════════╝
""")
    
    print("Checking ACP connection...")
    status = acp_get_status()
    if "error" in status:
        print(f"WARNING: ACP not reachable: {status['error']}")
    else:
        print(f"ACP Status: {status.get('session_tokens', 0)} tokens used")
    
    results = []
    
    for name, test_func in [
        ("Basic Agent", test_basic_agent),
        ("Tool Agent", test_tool_agent),
        ("Orchestrator Router", test_orchestrator_router),
        ("Built-in Tools", test_builtin_tools),
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
    
    status = acp_get_status()
    if "error" not in status:
        print(f"\nFinal ACP Token Usage: {status.get('session_tokens', 0):,} / {status.get('context_window', 0):,}")

if __name__ == "__main__":
    main()
