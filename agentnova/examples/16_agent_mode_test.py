#!/usr/bin/env python3
"""
examples/16_agent_mode_test.py
-------------------------------
Test suite for Agent Mode - goal-driven autonomous task execution.

Tests multi-step planning, tool orchestration, and task completion.
Unlike Test 07 (single-turn Q&A), this tests autonomous execution.

Usage:
  agentnova test 16 --model qwen2.5-coder:0.5b
  agentnova test 16 --model all

Test Categories:
  - File Operations: Create, read, write files
  - Shell Tasks: Execute commands, capture output
  - Multi-Step: Tasks requiring 2+ actions
  - Planning: Complex tasks requiring decomposition

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

import sys
import os
import time
import re
import json
import argparse
import tempfile
import shutil
import unicodedata

# Add project root to path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _project_root)

from agentnova import Agent, get_default_client, get_tool_support, StepResult, AgentMode
from agentnova.tools.builtins import make_builtin_registry
from agentnova.model_discovery import get_available_models
from agentnova.shared_args import add_shared_args, parse_shared_args, SharedConfig

# Parse CLI args
parser = argparse.ArgumentParser(description="AgentNova Agent Mode Test")
add_shared_args(parser)
args = parser.parse_args()
config = parse_shared_args(args)

DEBUG = config.debug
TIMEOUT = int(os.environ.get("AGENTNOVA_TIMEOUT", "120"))

# Check for optional ACP support
USE_ACP = config.acp
if USE_ACP:
    try:
        from agentnova.acp_plugin import ACPPlugin
    except ImportError:
        print("⚠️ ACP requested but ACPPlugin not available")
        USE_ACP = False


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    normalized = unicodedata.normalize('NFD', text.lower())
    without_accents = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    return without_accents.strip()


def print_step(step: StepResult):
    """Print step information for debug output."""
    if step.type == "tool_call":
        args = ", ".join(f"{k}={v}" for k, v in (step.tool_args or {}).items())
        print(f"      🔧 {step.tool_name}({args})")
    elif step.type == "tool_result":
        preview = step.content[:60] + "..." if len(step.content) > 60 else step.content
        print(f"      📦 → {preview}")


def make_step_callback(verbose: bool = True):
    def on_step(step: StepResult):
        if verbose:
            print_step(step)
    return on_step


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT MODE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

# Each test: (name, goal, tools, verification_fn)
# verification_fn takes (final_response, temp_dir) and returns (passed, message)

TESTS = []

def verify_file_exists(final_response: str, temp_dir: str, filename: str, content_contains: str = None) -> tuple[bool, str]:
    """Verify a file was created with optional content check."""
    filepath = os.path.join(temp_dir, filename)
    if not os.path.exists(filepath):
        return False, f"File '{filename}' not created"
    if content_contains:
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            if content_contains.lower() not in content.lower():
                return False, f"File exists but doesn't contain '{content_contains}'"
        except Exception as e:
            return False, f"Error reading file: {e}"
    return True, f"File '{filename}' created successfully"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

def test_calculator_chain(client, model: str, config: SharedConfig, temp_dir: str) -> tuple[bool, str, float]:
    """Test multi-step calculator usage."""
    print(f"\n  📐 Calculator Chain")
    print(f"     Goal: Calculate 15 * 8, then add 42 to the result")
    
    tools = make_builtin_registry().subset(["calculator"])
    tool_support = get_tool_support(model, client)
    
    # For models without tool support, skip
    if tool_support == "none":
        print(f"     ⚠️ Skipped: Model has no tool support")
        return True, "SKIPPED", 0.0
    
    system_prompt = "You are a helpful assistant. Use the calculator tool for all math operations."
    
    agent = Agent(
        model=model,
        client=client,
        tools=tools,
        system_prompt=system_prompt,
        max_steps=10,
        model_options={"temperature": 0.0, "num_ctx": 1024, "num_predict": 256},
        on_step=make_step_callback(DEBUG),
        debug=DEBUG,
    )
    
    goal = "Calculate 15 times 8, then add 42 to that result. Tell me the final number."
    
    t0 = time.time()
    try:
        run = agent.run(goal)
        elapsed = time.time() - t0
        response = run.final_answer
        
        # Expected: 15 * 8 = 120, 120 + 42 = 162
        expected = "162"
        response_norm = normalize_text(response)
        
        # Check if 162 is in the response
        passed = expected in response_norm or expected in response
        
        if passed:
            print(f"     ✅ PASS: Found '{expected}' in response")
        else:
            print(f"     ❌ FAIL: Expected '{expected}', got: {response[:80]}")
        
        return passed, response[:100], elapsed
        
    except Exception as e:
        elapsed = time.time() - t0
        print(f"     ❌ ERROR: {str(e)[:60]}")
        return False, str(e)[:60], elapsed


def test_file_write(client, model: str, config: SharedConfig, temp_dir: str) -> tuple[bool, str, float]:
    """Test file creation and writing."""
    print(f"\n  📝 File Write")
    print(f"     Goal: Create a file with specific content")
    
    tools = make_builtin_registry().subset(["write_file", "read_file"])
    tool_support = get_tool_support(model, client)
    
    # For models without tool support, test pure reasoning
    if tool_support == "none":
        print(f"     ⚠️ Skipped: Model has no tool support")
        return True, "SKIPPED", 0.0
    
    system_prompt = f"You are a helpful assistant with file access. Write files to {temp_dir}"
    
    agent = Agent(
        model=model,
        client=client,
        tools=tools,
        system_prompt=system_prompt,
        max_steps=5,
        model_options={"temperature": 0.0, "num_ctx": 1024, "num_predict": 256},
        on_step=make_step_callback(DEBUG),
        debug=DEBUG,
    )
    
    test_file = os.path.join(temp_dir, "test_output.txt")
    goal = f"Write 'Hello from AgentNova!' to the file {test_file}"
    
    t0 = time.time()
    try:
        run = agent.run(goal)
        elapsed = time.time() - t0
        response = run.final_answer
        
        # Check if file was created
        if os.path.exists(test_file):
            with open(test_file, 'r') as f:
                content = f.read()
            if "hello" in content.lower() and "agentnova" in content.lower():
                print(f"     ✅ PASS: File created with correct content")
                return True, content[:50], elapsed
            else:
                print(f"     ❌ FAIL: File created but wrong content: {content[:50]}")
                return False, f"Wrong content: {content[:50]}", elapsed
        else:
            print(f"     ❌ FAIL: File not created")
            return False, "File not created", elapsed
            
    except Exception as e:
        elapsed = time.time() - t0
        print(f"     ❌ ERROR: {str(e)[:60]}")
        return False, str(e)[:60], elapsed


def test_shell_echo(client, model: str, config: SharedConfig, temp_dir: str) -> tuple[bool, str, float]:
    """Test shell command execution."""
    print(f"\n  🖥️ Shell Echo")
    print(f"     Goal: Use shell to echo a message")
    
    tools = make_builtin_registry().subset(["shell"])
    tool_support = get_tool_support(model, client)
    
    if tool_support == "none":
        print(f"     ⚠️ Skipped: Model has no tool support")
        return True, "SKIPPED", 0.0
    
    system_prompt = "You are a helpful assistant with shell access. Execute shell commands when asked."
    
    agent = Agent(
        model=model,
        client=client,
        tools=tools,
        system_prompt=system_prompt,
        max_steps=5,
        model_options={"temperature": 0.0, "num_ctx": 1024, "num_predict": 256},
        on_step=make_step_callback(DEBUG),
        debug=DEBUG,
    )
    
    goal = "Use the shell to echo 'AgentNova was here'"
    
    t0 = time.time()
    try:
        run = agent.run(goal)
        elapsed = time.time() - t0
        response = run.final_answer
        response_norm = normalize_text(response)
        
        # Check if the echoed message appears in response
        passed = "agentnova was here" in response_norm
        
        if passed:
            print(f"     ✅ PASS: Echo message found in response")
        else:
            print(f"     ❌ FAIL: Expected echo message, got: {response[:80]}")
        
        return passed, response[:80], elapsed
        
    except Exception as e:
        elapsed = time.time() - t0
        print(f"     ❌ ERROR: {str(e)[:60]}")
        return False, str(e)[:60], elapsed


def test_python_calc(client, model: str, config: SharedConfig, temp_dir: str) -> tuple[bool, str, float]:
    """Test Python REPL for calculation."""
    print(f"\n  🐍 Python REPL")
    print(f"     Goal: Use Python to calculate 2^20")
    
    tools = make_builtin_registry().subset(["python_repl"])
    tool_support = get_tool_support(model, client)
    
    if tool_support == "none":
        print(f"     ⚠️ Skipped: Model has no tool support")
        return True, "SKIPPED", 0.0
    
    system_prompt = "You are a helpful assistant with Python access. Use python_repl for calculations."
    
    agent = Agent(
        model=model,
        client=client,
        tools=tools,
        system_prompt=system_prompt,
        max_steps=5,
        model_options={"temperature": 0.0, "num_ctx": 1024, "num_predict": 256},
        on_step=make_step_callback(DEBUG),
        debug=DEBUG,
    )
    
    goal = "Use Python to calculate 2 to the power of 20. Tell me the result."
    
    t0 = time.time()
    try:
        run = agent.run(goal)
        elapsed = time.time() - t0
        response = run.final_answer
        response_norm = normalize_text(response)
        
        # Expected: 1048576
        expected = "1048576"
        passed = expected in response_norm or expected in response
        
        if passed:
            print(f"     ✅ PASS: Found correct result '{expected}'")
        else:
            print(f"     ❌ FAIL: Expected '{expected}', got: {response[:80]}")
        
        return passed, response[:80], elapsed
        
    except Exception as e:
        elapsed = time.time() - t0
        print(f"     ❌ ERROR: {str(e)[:60]}")
        return False, str(e)[:60], elapsed


def test_multi_tool(client, model: str, config: SharedConfig, temp_dir: str) -> tuple[bool, str, float]:
    """Test using multiple tools in sequence."""
    print(f"\n  🔧 Multi-Tool")
    print(f"     Goal: Calculate, then write result to file")
    
    tools = make_builtin_registry().subset(["calculator", "write_file"])
    tool_support = get_tool_support(model, client)
    
    if tool_support == "none":
        print(f"     ⚠️ Skipped: Model has no tool support")
        return True, "SKIPPED", 0.0
    
    system_prompt = f"You are a helpful assistant. Use calculator for math, write_file to save. Write to {temp_dir}"
    
    agent = Agent(
        model=model,
        client=client,
        tools=tools,
        system_prompt=system_prompt,
        max_steps=10,
        model_options={"temperature": 0.0, "num_ctx": 2048, "num_predict": 512},
        on_step=make_step_callback(DEBUG),
        debug=DEBUG,
    )
    
    result_file = os.path.join(temp_dir, "calc_result.txt")
    goal = f"Calculate 25 * 4, then write the result to {result_file}"
    
    t0 = time.time()
    try:
        run = agent.run(goal)
        elapsed = time.time() - t0
        response = run.final_answer
        
        # Check: file exists with correct content
        if os.path.exists(result_file):
            with open(result_file, 'r') as f:
                content = f.read()
            if "100" in content:
                print(f"     ✅ PASS: File created with correct result (100)")
                return True, content[:50], elapsed
            else:
                print(f"     ❌ FAIL: File created but wrong content: {content}")
                return False, f"Wrong content: {content[:50]}", elapsed
        else:
            print(f"     ❌ FAIL: File not created")
            return False, "File not created", elapsed
            
    except Exception as e:
        elapsed = time.time() - t0
        print(f"     ❌ ERROR: {str(e)[:60]}")
        return False, str(e)[:60], elapsed


def test_simple_reasoning(client, model: str, config: SharedConfig, temp_dir: str) -> tuple[bool, str, float]:
    """Test pure reasoning without tools - works for all models."""
    print(f"\n  🧠 Simple Reasoning")
    print(f"     Goal: Solve a logic puzzle")
    
    # No tools - pure reasoning
    agent = Agent(
        model=model,
        client=client,
        tools=None,
        max_steps=3,
        model_options={"temperature": 0.0, "num_ctx": 512, "num_predict": 128},
        on_step=make_step_callback(DEBUG),
        debug=DEBUG,
    )
    
    goal = "I have 5 apples. I eat 2 and give 1 to a friend. How many apples do I have left? Answer with just the number."
    
    t0 = time.time()
    try:
        run = agent.run(goal)
        elapsed = time.time() - t0
        response = run.final_answer
        response_norm = normalize_text(response)
        
        # Expected: 2
        passed = "2" in response_norm and ("left" in response_norm or "have" in response_norm or len(response) < 10)
        
        # More lenient: just check if 2 is the main number
        if not passed:
            numbers = re.findall(r'\b\d+\b', response)
            if numbers and numbers[0] == "2":
                passed = True
        
        if passed:
            print(f"     ✅ PASS: Correct answer (2)")
        else:
            print(f"     ❌ FAIL: Expected '2', got: {response[:80]}")
        
        return passed, response[:80], elapsed
        
    except Exception as e:
        elapsed = time.time() - t0
        print(f"     ❌ ERROR: {str(e)[:60]}")
        return False, str(e)[:60], elapsed


def test_knowledge_recall(client, model: str, config: SharedConfig, temp_dir: str) -> tuple[bool, str, float]:
    """Test knowledge recall without tools."""
    print(f"\n  📚 Knowledge Recall")
    print(f"     Goal: Answer a factual question")
    
    agent = Agent(
        model=model,
        client=client,
        tools=None,
        max_steps=3,
        model_options={"temperature": 0.0, "num_ctx": 512, "num_predict": 64},
        on_step=make_step_callback(DEBUG),
        debug=DEBUG,
    )
    
    goal = "What is the capital of France? Answer with just the city name."
    
    t0 = time.time()
    try:
        run = agent.run(goal)
        elapsed = time.time() - t0
        response = run.final_answer
        response_norm = normalize_text(response)
        
        passed = "paris" in response_norm
        
        if passed:
            print(f"     ✅ PASS: Correct answer (Paris)")
        else:
            print(f"     ❌ FAIL: Expected 'Paris', got: {response[:80]}")
        
        return passed, response[:80], elapsed
        
    except Exception as e:
        elapsed = time.time() - t0
        print(f"     ❌ ERROR: {str(e)[:60]}")
        return False, str(e)[:60], elapsed


def test_model(client, model: str, config: SharedConfig, acp=None) -> dict:
    """Test a single model on all agent mode tests."""
    print(f"\n{'='*60}")
    print(f"🤖 Agent Mode Test: {model}")
    print(f"   Tool support: {get_tool_support(model, client)}")
    print(f"{'='*60}")
    
    if acp:
        acp.log_chat("system", f"Agent Mode Test started for {model}", complete=True)
    
    # Create temp directory for file tests
    temp_dir = tempfile.mkdtemp(prefix="agentnova_test_")
    
    results = {
        "model": model,
        "tool_support": get_tool_support(model, client),
        "passed": 0,
        "total": 0,
        "skipped": 0,
        "time": 0,
        "tests": {}
    }
    
    # Define tests
    tests = [
        ("Simple Reasoning", test_simple_reasoning),
        ("Knowledge Recall", test_knowledge_recall),
        ("Calculator Chain", test_calculator_chain),
        ("File Write", test_file_write),
        ("Shell Echo", test_shell_echo),
        ("Python REPL", test_python_calc),
        ("Multi-Tool", test_multi_tool),
    ]
    
    for test_name, test_fn in tests:
        try:
            passed, msg, elapsed = test_fn(client, model, config, temp_dir)
            results["time"] += elapsed
            results["total"] += 1
            
            if msg == "SKIPPED":
                results["skipped"] += 1
            elif passed:
                results["passed"] += 1
            
            results["tests"][test_name] = {
                "passed": passed,
                "message": msg,
                "time": elapsed
            }
        except Exception as e:
            results["total"] += 1
            results["tests"][test_name] = {
                "passed": False,
                "message": str(e)[:60],
                "time": 0
            }
    
    # Cleanup temp directory
    shutil.rmtree(temp_dir, ignore_errors=True)
    
    # Summary
    if results["total"] > results["skipped"]:
        pass_rate = results["passed"] / (results["total"] - results["skipped"]) * 100
    else:
        pass_rate = 0
    
    print(f"\n  📊 Result: {results['passed']}/{results['total'] - results['skipped']} ({pass_rate:.0f}%)")
    print(f"     Skipped: {results['skipped']} (no tool support)")
    print(f"     Time: {results['time']:.1f}s")
    
    if acp:
        acp.log_chat("system", f"{model}: {results['passed']}/{results['total'] - results['skipped']} ({pass_rate:.0f}%) in {results['time']:.1f}s", complete=True)
    
    return results


def main():
    client = get_default_client()
    
    if not client.is_running():
        print("❌ Ollama is not running. Start it with: ollama serve")
        return
    
    available = list(dict.fromkeys(get_available_models(client)))
    
    # Setup ACP if requested
    main_acp = None
    acp_connected = False
    if USE_ACP:
        try:
            main_acp = ACPPlugin(
                agent_name="AgentNova",
                model_name="agent-mode-test",
                debug=DEBUG,
            )
            bootstrap = main_acp.bootstrap(claim_primary=False)
            acp_connected = bootstrap.get("status") is not None
        except Exception as e:
            print(f"   ⚠️ ACP connection failed: {e}")
            acp_connected = False
    
    print(f"\n⚛️ AgentNova Agent Mode Test")
    print(f"   Testing autonomous task execution capabilities")
    print(f"   Available models: {', '.join(available[:5])}{'...' if len(available) > 5 else ''}")
    if USE_ACP:
        print(f"   ACP: {'connected' if acp_connected else 'unavailable'}")
    
    # Determine which models to test
    if config.model:
        if config.model == "all":
            models_to_test = available
        else:
            models_to_test = [m for m in available if config.model in m]
            if not models_to_test and config.model in available:
                models_to_test = [config.model]
    else:
        models_to_test = available[:1]
    
    if not models_to_test:
        print(f"   ⚠️ No models match '{config.model}'")
        return
    
    print(f"   Testing: {', '.join(models_to_test)}")
    
    all_results = []
    for model in models_to_test:
        # Create per-model ACP instance if enabled
        model_acp = None
        if USE_ACP and acp_connected:
            try:
                model_acp = ACPPlugin(
                    agent_name="AgentNova",
                    model_name=model.split(':')[0][:25],
                    debug=DEBUG,
                )
                model_acp.bootstrap(claim_primary=False)
            except Exception as e:
                print(f"      ⚠️ ACP for {model} failed: {e}")
                model_acp = None
        
        result = test_model(client, model, config, acp=model_acp)
        all_results.append(result)
    
    # Rankings
    if len(all_results) > 1:
        print(f"\n{'='*60}")
        print("🏆 RANKINGS")
        print(f"{'='*60}")
        
        sorted_results = sorted(all_results, key=lambda x: (-x["passed"], x["time"]))
        
        for i, r in enumerate(sorted_results, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
            total_run = r["total"] - r["skipped"]
            if total_run > 0:
                rate = r["passed"] / total_run * 100
            else:
                rate = 0
            print(f"{medal} {r['model']:<35} {r['passed']}/{total_run} ({rate:.0f}%) - {r['time']:.1f}s")
            if r["skipped"] > 0:
                print(f"   ⚠️ {r['skipped']} tests skipped (no tool support)")
        
        # Log final summary to ACP
        if main_acp and acp_connected:
            winner = sorted_results[0]
            summary = f"🏆 Winner: {winner['model']} - {winner['passed']}/{winner['total'] - winner['skipped']} in {winner['time']:.1f}s"
            main_acp.log_chat("system", summary, complete=True)


if __name__ == "__main__":
    main()