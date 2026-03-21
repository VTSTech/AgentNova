"""
examples/05_tool_tests.py
-------------------------
Test suite focused on tool usage with calculator, shell, and Python REPL.

The prompts ask questions - models must figure out which tools to use
and how to call them. Content is NOT provided in prompts.

Use --acp or AGENTNOVA_ACP=1 for ACP integration.
Use --use-mf-sys or AGENTNOVA_USE_MF_SYS=1 for Modelfile system prompts.

Run from the project root:   python examples/05_tool_tests.py
Or from the examples folder: python 05_tool_tests.py

With CLI:
  agentnova test 05
  agentnova test 05 --acp --debug
  agentnova test 05 --use-mf-sys --model qwen2.5-coder:0.5b

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

import sys
import os
import time
import re
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
parser = argparse.ArgumentParser(description="AgentNova Tool Tests")
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
        from agentnova.acp_plugin import ACPPlugin
    except ImportError:
        print("⚠️ ACP requested but ACPPlugin not available")
        USE_ACP = False

BACKEND_NAME = AGENTNOVA_BACKEND.upper()


# Model to test (discovered dynamically or set via config)
preferred = config.model
MODEL = None  # Will be set in main()
VERBOSE = os.environ.get("AGENTNOVA_VERBOSE", "1") == "1"
TIMEOUT = int(os.environ.get("AGENTNOVA_TIMEOUT", "120"))  # seconds per test

# ACP instance (global for step callback)
acp = None


def make_step_callback(verbose: bool, acp_instance=None):
    """Create a combined step callback for verbose output and ACP logging."""
    def on_step(step: StepResult):
        if verbose:
            print_step(step)
        if acp_instance:
            acp_instance.on_step(step)
    return on_step


def print_step(step: StepResult):
    """Print step information."""
    if step.type == "tool_call":
        args = ", ".join(f"{k}={v}" for k, v in (step.tool_args or {}).items())
        print(f"    🔧 {step.tool_name}({args})")
    elif step.type == "tool_result":
        preview = step.content[:80] + "..." if len(step.content) > 80 else step.content
        print(f"    📦 → {preview}")


def check_tool_used(run, tool_name: str) -> bool:
    """Verify that a specific tool was actually called during the run."""
    for step in run.steps:
        if step.type == "tool_call" and step.tool_name == tool_name:
            return True
    return False


def normalize_number(text: str) -> str:
    """Extract first number from text for comparison."""
    match = re.search(r'-?\d+\.?\d*', text.replace(',', ''))
    return match.group(0) if match else ""


def run_test(agent, prompt: str, timeout: int = TIMEOUT):
    """Run agent with timeout and return (run, error)."""
    import signal
    
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Test timed out after {timeout}s")
    
    # Set alarm for timeout (Unix only)
    old_handler = None
    try:
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)
    except (AttributeError, ValueError):
        pass  # Windows doesn't have SIGALRM
    
    try:
        run = agent.run(prompt)
        try:
            signal.alarm(0)
            if old_handler:
                signal.signal(signal.SIGALRM, old_handler)
        except:
            pass
        return run, None
    except TimeoutError as e:
        return None, str(e)
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:100]}"


def test_calculator():
    """Test calculator tool - models must figure out how to use it."""
    global MODEL, acp
    client = get_default_client()
    
    if not client.is_running():
        print(f"❌ {BACKEND_NAME} is not running.")
        return 0, 0
    
    # Pick best model dynamically
    MODEL = pick_best_model(preferred=preferred, client=client)
    if not MODEL:
        models = get_available_models(client)
        MODEL = models[0] if models else None
    
    if not MODEL:
        print(f"❌ No models available in {BACKEND_NAME}.")
        return 0, 0
    
    # Create ACP instance for this test if enabled
    test_acp = None
    if USE_ACP:
        model_short = MODEL.split(':')[0]
        test_acp = ACPPlugin(
            agent_name="AgentNova",
            model_name=model_short,
            debug=DEBUG,
        )
    
    print(f"\n{'='*60}")
    print(f"🧮 Calculator Tool Tests")
    print(f"   Model: {MODEL}")
    print(f"   Tool support: {get_tool_support(MODEL, client)}")
    print(f"   Timeout: {TIMEOUT}s per test")
    if USE_ACP:
        print(f"   ACP: enabled")
    print(f"{'='*60}")
    
    tools = make_builtin_registry().subset(["calculator"])
    
    # Ask questions - model must use calculator tool
    tests = [
        ("Basic multiplication", "What is 15 times 8?", "120"),
        ("Power", "What is 2 to the power of 10?", "1024"),
        ("Square root", "What is the square root of 144?", "12"),
        ("Complex expression", "What is (10 + 5) times 3?", "45"),
        ("Division", "What is 100 divided by 4?", "25"),
    ]
    
    results = []
    
    for name, prompt, expected in tests:
        print(f"\n📋 {name}")
        print(f"   Prompt: {prompt}")
        
        agent = Agent(
            model=MODEL,
            client=client,
            tools=tools,
            system_prompt="Answer math questions using the calculator tool. Call the calculator with the expression.",
            max_steps=5,
            on_step=make_step_callback(VERBOSE, test_acp),
            debug=DEBUG,
            model_options={
                "temperature": 0.0,      # Deterministic
                "num_ctx": 1024,         # Enough for tool definitions + prompt
                "num_predict": 128,      # Short answers
            },
        )
        
        t0 = time.time()
        run, error = run_test(agent, prompt)
        elapsed = time.time() - t0
        
        if error:
            results.append(False)
            print(f"  ❌ Error: {error}")
            continue
        
        # Log to ACP
        if test_acp:
            test_acp.log_user_message(prompt)
            test_acp.log_assistant_message(run.final_answer)
        
        # Check if tool was actually used
        tool_used = check_tool_used(run, "calculator")
        if not tool_used:
            print(f"  ⚠️ WARNING: Calculator tool was NOT called - model may have hallucinated!")
        
        # Check answer - use normalized number matching
        expected_num = normalize_number(expected)
        actual_num = normalize_number(run.final_answer)
        passed = expected_num == actual_num and expected_num != ""
        
        if not passed and expected in run.final_answer:
            passed = True  # Fallback to string match
        
        results.append(passed)
        
        status = "✅" if passed else "❌"
        print(f"  {status} Expected '{expected}' (normalized: {expected_num})")
        print(f"  📝 Got: {actual_num} | Answer: {run.final_answer[:80].replace(chr(10), ' ')}...")
        print(f"  ⏱️  {elapsed:.1f}s, {len(run.steps)} steps, tool_used={tool_used}")
    
    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\n{'='*60}")
    print(f"📊 Calculator: {passed}/{total} tests passed ({100*passed//total}%)")
    print(f"{'='*60}")
    return passed, total


def test_shell():
    """Test shell tool - models must figure out how to use it."""
    global acp
    client = get_default_client()
    
    # Create ACP instance for this test if enabled
    test_acp = None
    if USE_ACP:
        test_acp = ACPPlugin(
            agent_name="AgentNova",
            model_name=f"{MODEL.split(':')[0]}_shell",
            debug=DEBUG,
        )
    
    print(f"\n{'='*60}")
    print(f"🖥️  Shell Tool Tests")
    print(f"   Model: {MODEL}")
    if USE_ACP:
        print(f"   ACP: enabled")
    print(f"{'='*60}")
    
    tools = make_builtin_registry().subset(["shell"])
    
    # Ask questions - model must use shell tool
    tests = [
        ("Echo test", "Use shell to echo the text 'Hello AgentNova'", "Hello AgentNova", "shell"),
        ("Current directory", "What is the current working directory?", None, "shell"),
        ("Date", "What is today's date? Use shell to find out.", None, "shell"),
    ]
    
    results = []
    
    for name, prompt, expected, required_tool in tests:
        print(f"\n📋 {name}")
        print(f"   Prompt: {prompt}")
        
        agent = Agent(
            model=MODEL,
            client=client,
            tools=tools,
            system_prompt="Use the shell tool to run commands when asked.",
            max_steps=5,
            on_step=make_step_callback(VERBOSE, test_acp),
            debug=DEBUG,
            model_options={
                "temperature": 0.0,      # Deterministic
                "num_ctx": 1024,         # Enough for tool definitions + prompt
                "num_predict": 128,      # Short answers
            },
        )
        
        t0 = time.time()
        run, error = run_test(agent, prompt)
        elapsed = time.time() - t0
        
        if error:
            results.append(False)
            print(f"  ❌ Error: {error}")
            continue
        
        # Log to ACP
        if test_acp:
            test_acp.log_user_message(prompt)
            test_acp.log_assistant_message(run.final_answer)
        
        # Verify tool was used
        tool_used = check_tool_used(run, required_tool)
        if not tool_used:
            print(f"  ⚠️ WARNING: Shell tool was NOT called!")
            results.append(False)
            print(f"  ❌ FAILED: Tool not used")
            print(f"  📝 Answer: {run.final_answer[:100].replace(chr(10), ' ')}...")
            continue
        
        # Check expected value if provided
        if expected:
            passed = expected.lower() in run.final_answer.lower()
            results.append(passed)
            status = "✅" if passed else "❌"
            print(f"  {status} Expected '{expected}' in response")
        else:
            # No expected value - just verify tool was used
            results.append(True)
            print(f"  ✅ Tool was used correctly")
        
        print(f"  📝 Answer: {run.final_answer[:100].replace(chr(10), ' ')}...")
        print(f"  ⏱️  {elapsed:.1f}s, {len(run.steps)} steps")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 Shell: {passed}/{total} tests passed ({100*passed//total}%)")
    return passed, total


def test_python_repl():
    """Test Python REPL tool - models must figure out how to use it."""
    global acp
    client = get_default_client()
    
    # Create ACP instance for this test if enabled
    test_acp = None
    if USE_ACP:
        test_acp = ACPPlugin(
            agent_name="AgentNova",
            model_name=f"{MODEL.split(':')[0]}_python",
            debug=DEBUG,
        )
    
    print(f"\n{'='*60}")
    print(f"🐍 Python REPL Tool Tests")
    print(f"   Model: {MODEL}")
    if USE_ACP:
        print(f"   ACP: enabled")
    print(f"{'='*60}")
    
    tools = make_builtin_registry().subset(["python_repl"])
    
    # Ask questions - model must use Python REPL
    tests = [
        ("Power calculation", "What is 2 to the power of 20?", "1048576", "python_repl"),
        ("List squares", "Generate a list of squares from 1 to 5. What are they?", "1, 4, 9, 16, 25", "python_repl"),
        ("String repeat", "What is 'Hello' repeated 3 times?", "HelloHelloHello", "python_repl"),
    ]
    
    results = []
    
    for name, prompt, expected, required_tool in tests:
        print(f"\n📋 {name}")
        print(f"   Prompt: {prompt}")
        
        agent = Agent(
            model=MODEL,
            client=client,
            tools=tools,
            system_prompt="Use Python REPL for calculations. Use print() to show results in your code.",
            max_steps=5,
            on_step=make_step_callback(VERBOSE, test_acp),
            debug=DEBUG,
            model_options={
                "temperature": 0.0,      # Deterministic
                "num_ctx": 1024,         # Enough for tool definitions + prompt
                "num_predict": 128,      # Short answers
            },
        )
        
        t0 = time.time()
        run, error = run_test(agent, prompt)
        elapsed = time.time() - t0
        
        if error:
            results.append(False)
            print(f"  ❌ Error: {error}")
            continue
        
        # Log to ACP
        if test_acp:
            test_acp.log_user_message(prompt)
            test_acp.log_assistant_message(run.final_answer)
        
        # Verify tool was used
        tool_used = check_tool_used(run, required_tool)
        if not tool_used:
            print(f"  ⚠️ WARNING: Python REPL tool was NOT called!")
            results.append(False)
            print(f"  ❌ FAILED: Tool not used")
            print(f"  📝 Answer: {run.final_answer[:100].replace(chr(10), ' ')}...")
            continue
        
        # Check answer with flexible matching
        passed = False
        if expected in run.final_answer:
            passed = True
        else:
            # Try normalized number matching (handles comma formatting like 1,048,576)
            expected_num = normalize_number(expected)
            actual_num = normalize_number(run.final_answer)
            if expected_num and expected_num == actual_num:
                passed = True
            else:
                # Normalize and compare (handles different list formats)
                expected_clean = expected.replace("[", "").replace("]", "").replace(" ", "").replace(",", "")
                answer_clean = run.final_answer.replace("[", "").replace("]", "").replace(" ", "").replace(",", "")
                if expected_clean in answer_clean:
                    passed = True
        
        results.append(passed)
        status = "✅" if passed else "❌"
        print(f"  {status} Expected '{expected}' in response")
        print(f"  📝 Answer: {run.final_answer[:100].replace(chr(10), ' ')}...")
        print(f"  ⏱️  {elapsed:.1f}s, {len(run.steps)} steps, tool_used={tool_used}")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 Python REPL: {passed}/{total} tests passed ({100*passed//total}%)")
    return passed, total


def main():
    global MODEL
    print(f"\n{'='*60}")
    print(f"🔧 AgentNova Tool Tests")
    print(f"   Backend: {BACKEND_NAME}")
    print(f"   Verbose: {VERBOSE}")
    print(f"   Timeout: {TIMEOUT}s")
    if USE_ACP:
        print(f"   ACP: enabled")
    print(f"{'='*60}")
    
    total_passed = 0
    total_tests = 0
    
    p, t = test_calculator()
    total_passed += p
    total_tests += t
    
    p, t = test_shell()
    total_passed += p
    total_tests += t
    
    p, t = test_python_repl()
    total_passed += p
    total_tests += t
    
    print(f"\n{'='*60}")
    print(f"📊 TOTAL: {total_passed}/{total_tests} tests passed ({100*total_passed//total_tests}%)")
    print(f"{'='*60}\n")
    
    return total_passed == total_tests


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
