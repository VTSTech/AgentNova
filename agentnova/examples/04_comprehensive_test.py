"""
examples/04_comprehensive_test.py
---------------------------------
Comprehensive test suite for AgentNova with detailed output.
Tests multiple capabilities: Q&A, reasoning, tools, code generation.

Use --acp or AGENTNOVA_ACP=1 for ACP integration.
Use --use-mf-sys or AGENTNOVA_USE_MF_SYS=1 for Modelfile system prompts.

Run from the project root:   python examples/04_comprehensive_test.py
Or from the examples folder: python 04_comprehensive_test.py

With CLI:
  agentnova test 04
  agentnova test 04 --acp --debug
  agentnova test 04 --use-mf-sys --model qwen2.5-coder:0.5b

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

import sys
import os
import time
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentnova import (
    Agent,
    get_default_client,
    get_available_models,
    get_system_prompt,
    get_tool_support,  # Tool support detection
    AGENTNOVA_BACKEND,
    StepResult,
)
from agentnova.tools.builtins import make_builtin_registry
from agentnova.model_discovery import pick_best_model, get_available_models
from agentnova.shared_args import add_shared_args, parse_shared_args

# Parse CLI args (with env var fallbacks)
parser = argparse.ArgumentParser(description="AgentNova Comprehensive Test")
add_shared_args(parser)
args = parser.parse_args()
config = parse_shared_args(args)

# Check for flags from config
USE_ACP = config.acp
DEBUG = config.debug
USE_MF_SYS = config.use_modelfile_system

# Import ACP if needed
if USE_ACP:
    try:
        from agentnova import ACPPlugin
    except ImportError:
        print("⚠️ ACP requested but ACPPlugin not available")
        USE_ACP = False

BACKEND_NAME = AGENTNOVA_BACKEND.upper()


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Model to test (discovered dynamically or set via config)
preferred = config.model
MODEL = None  # Will be set in run_tests()

# Test categories
TESTS = {
    "basic": [
        {
            "name": "Simple Addition",
            "prompt": "What is 2 + 2? Answer with just the number.",
            "check": lambda r: "4" in r,
        },
        {
            "name": "Multiplication",
            "prompt": "What is 7 times 8? Answer with just the number.",
            "check": lambda r: "56" in r,
        },
        {
            "name": "Capital City",
            "prompt": "What is the capital of Japan? Answer in one word.",
            "check": lambda r: "tokyo" in r.lower(),
        },
    ],
    "reasoning": [
        {
            "name": "Simple Reasoning",
            "prompt": "I have 10 apples. I eat 3 and give 2 to a friend. How many do I have left? Just the number.",
            "check": lambda r: "5" in r,
        },
        {
            "name": "Age Problem",
            "prompt": "Tom is 5 years older than Mary. Mary is 12. How old is Tom? Just the number.",
            "check": lambda r: "17" in r,
        },
    ],
    "code": [
        {
            "name": "Even Function",
            "prompt": "Write a Python function called is_even that takes a number and returns True if it's even.",
            "check": lambda r: "def is_even" in r and "return" in r,
        },
        {
            "name": "Add Function",
            "prompt": "Write a Python function called add that takes two numbers and returns their sum.",
            "check": lambda r: "def add" in r and "return" in r,
        },
    ],
}


def make_step_printer(acp=None):
    """Create a step printer function that optionally forwards to ACP."""
    def print_step(step: StepResult):
        if step.type == "tool_call":
            args = ", ".join(f"{k}={v}" for k, v in (step.tool_args or {}).items())
            print(f"    🔧 Tool: {step.tool_name}({args})")
        elif step.type == "tool_result":
            preview = step.content[:80] + "..." if len(step.content) > 80 else step.content
            print(f"    📦 Result: {preview}")
        
        # Forward to ACP if enabled
        if acp:
            acp.on_step(step)
    
    return print_step


def run_tests():
    """Run all test categories."""
    global MODEL
    client = get_default_client()
    
    if not client.is_running():
        print(f"❌ {BACKEND_NAME} is not running.")
        if AGENTNOVA_BACKEND == "bitnet":
            print("   Start llama-server from bitnet.cpp directory")
        else:
            print("   Start it with: ollama serve")
        return
    
    # Pick best model dynamically
    MODEL = pick_best_model(preferred=preferred, client=client)
    if not MODEL:
        models = get_available_models(client)
        MODEL = models[0] if models else None
    
    if not MODEL:
        print(f"❌ No models available in {BACKEND_NAME}.")
        return
    
    # Initialize ACP if enabled
    acp = None
    if USE_ACP:
        acp = ACPPlugin(
            agent_name="AgentNova-ComprehensiveTest",
            model_name=MODEL,
            debug=DEBUG,
        )
        print(f"   ACP URL: {acp.base_url}")
        bootstrap = acp.bootstrap(claim_primary=False)
        if bootstrap.get("stop_flag"):
            print(f"   ⚠️ ACP STOP flag is set: {bootstrap.get('stop_reason')}")
        print(f"   ACP Status: {'connected' if bootstrap.get('status') else 'unavailable'}")
    
    print(f"\n{'='*60}")
    print(f"🧪 AgentNova Comprehensive Test Suite")
    print(f"   Model: {MODEL}")
    print(f"   Backend: {BACKEND_NAME}")
    print(f"   Tool support: {get_tool_support(MODEL, client)}")
    if USE_MF_SYS:
        print(f"   Using Modelfile system prompt: YES")
    if DEBUG:
        print(f"   Debug: enabled")
    print(f"{'='*60}")
    
    total_passed = 0
    total_tests = 0
    total_time = 0
    
    for category, tests in TESTS.items():
        print(f"\n📋 {category.upper()} TESTS")
        print("-" * 40)
        
        # Create agent for this category
        agent = Agent(
            model=MODEL,
            client=client,
            system_prompt=get_system_prompt(
                MODEL,
                client=client,
                default_prompt="You are a helpful assistant. Be concise and accurate.",
            ),
            max_steps=6,
            on_step=make_step_printer(acp),
            debug=DEBUG,
            model_options={
                "temperature": 0.0,     # Deterministic for tests
                "num_ctx": 1024,        # Moderate context
                "num_predict": 128,     # Short test answers
            },
        )
        
        for test in tests:
            total_tests += 1
            print(f"\n  🔮 {test['name']}")
            
            t0 = time.time()
            try:
                if acp:
                    acp.log_user_message(test["prompt"])
                
                response = agent.chat(test["prompt"])
                elapsed = time.time() - t0
                total_time += elapsed
                
                passed = test["check"](response)
                total_passed += int(passed)
                
                status = "✅ PASS" if passed else "❌ FAIL"
                preview = response[:60].replace("\n", " ")
                print(f"  {status} ({elapsed:.1f}s): {preview}...")
                
                if acp:
                    acp.log_assistant_message(response)
                
                if not passed:
                    print(f"       Full response: {response}")
            except Exception as e:
                total_time += 60
                print(f"  ❌ ERROR: {e}")
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 SUMMARY")
    print(f"{'='*60}")
    pass_rate = total_passed / total_tests * 100 if total_tests > 0 else 0
    print(f"  Tests: {total_passed}/{total_tests} passed ({pass_rate:.0f}%)")
    print(f"  Time: {total_time:.1f}s total, {total_time/total_tests:.1f}s avg")
    
    if pass_rate >= 70:
        print(f"\n✅ Model '{MODEL}' is working well!")
    elif pass_rate >= 50:
        print(f"\n⚠️  Model '{MODEL}' has some issues but usable.")
    else:
        print(f"\n❌ Model '{MODEL}' needs improvement or replacement.")
    
    if acp:
        tokens = acp.get_session_tokens()
        print(f"   ACP Session tokens: {tokens}")


if __name__ == "__main__":
    run_tests()
