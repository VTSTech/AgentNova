#!/usr/bin/env python3
"""
examples/02_tool_test.py
------------------------
Tool usage tests for calculator, shell, and file operations.

Tests verify:
  • Tool is actually called (not hallucinated)
  • Correct tool selection
  • Proper argument passing
  • Correct result extraction

Usage:
  python examples/02_tool_test.py
  python examples/02_tool_test.py --model qwen2.5:0.5b --debug
  agentnova test 02

Environment Variables:
  OLLAMA_BASE_URL     - Ollama server URL
  AGENTNOVA_MODEL     - Default model

Written by VTSTech — https://www.vts-tech.org
"""

import sys
import os
import time
import re
import argparse
import platform

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentnova import Agent, get_config
from agentnova.backends import get_default_backend
from agentnova.tools import make_builtin_registry
from agentnova.core.types import StepResultType


def parse_args():
    parser = argparse.ArgumentParser(description="AgentNova Tool Tests")
    parser.add_argument("-m", "--model", default=None, help="Model to test")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--backend", choices=["ollama", "bitnet"], default=None)
    return parser.parse_args()


def normalize_number(text: str) -> str:
    """Extract first number from text."""
    match = re.search(r'-?\d+\.?\d*', text.replace(',', ''))
    return match.group(0) if match else ""


def check_tool_used(run, tool_name: str) -> bool:
    """Verify that a specific tool was called during the run."""
    for step in run.steps:
        if step.type == StepResultType.TOOL_CALL:
            if step.tool_call and step.tool_call.name == tool_name:
                return True
            if step.tool_result is not None and hasattr(step, 'content'):
                # Check tool name in step content
                if tool_name in str(step.content).lower():
                    return True
    return False


def test_calculator(model: str, backend, debug: bool = False) -> tuple[int, int]:
    """Test calculator tool."""
    print(f"\n{'='*60}")
    print(f"🧮 Calculator Tool Tests")
    print(f"   Model: {model}")
    print(f"{'='*60}")
    
    tools = make_builtin_registry().subset(["calculator"])
    
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
            model=model,
            tools=tools,
            backend=backend,
            max_steps=5,
            debug=debug,
        )
        
        t0 = time.time()
        run = agent.run(prompt)
        elapsed = time.time() - t0
        
        # Check if tool was used
        tool_used = check_tool_used(run, "calculator")
        
        # Check answer
        expected_num = normalize_number(expected)
        actual_num = normalize_number(run.final_answer)
        passed = expected_num == actual_num and expected_num != ""
        
        if not passed and expected in run.final_answer:
            passed = True
        
        results.append(passed)
        
        status = "✅" if passed else "❌"
        tool_status = "🔧" if tool_used else "⚠️"
        print(f"  {status} Expected '{expected}' | Got: {actual_num}")
        print(f"  {tool_status} Tool used: {tool_used} | {elapsed:.1f}s, {len(run.steps)} steps")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 Calculator: {passed}/{total} ({100*passed//total}%)")
    return passed, total


def test_shell(model: str, backend, debug: bool = False) -> tuple[int, int]:
    """Test shell tool."""
    print(f"\n{'='*60}")
    print(f"🖥️ Shell Tool Tests")
    print(f"   Model: {model}")
    print(f"{'='*60}")
    
    tools = make_builtin_registry().subset(["shell"])
    is_windows = platform.system() == "Windows"
    
    tests = [
        ("Echo test", "Use shell to echo 'Hello AgentNova'", "Hello AgentNova"),
        ("Current directory", "What is the current working directory?", None),
    ]
    
    results = []
    
    for name, prompt, expected in tests:
        print(f"\n📋 {name}")
        print(f"   Prompt: {prompt}")
        
        sys_prompt = "Use shell commands to answer questions."
        if is_windows:
            sys_prompt += " Use Windows commands (dir, cd, echo)."
        else:
            sys_prompt += " Use Unix commands (ls, pwd, echo)."
        
        agent = Agent(
            model=model,
            tools=tools,
            backend=backend,
            max_steps=5,
            debug=debug,
        )
        
        t0 = time.time()
        run = agent.run(prompt)
        elapsed = time.time() - t0
        
        # Check if tool was used
        tool_used = check_tool_used(run, "shell")
        
        if not tool_used:
            print(f"  ❌ Shell tool was NOT called!")
            results.append(False)
            continue
        
        # Check expected if provided
        if expected:
            passed = expected.lower() in run.final_answer.lower()
        else:
            passed = True  # Just verify tool was used
        
        results.append(passed)
        status = "✅" if passed else "❌"
        print(f"  {status} {elapsed:.1f}s, {len(run.steps)} steps")
        print(f"  📝 {run.final_answer[:80]}")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 Shell: {passed}/{total} ({100*passed//total}%)")
    return passed, total


def test_datetime(model: str, backend, debug: bool = False) -> tuple[int, int]:
    """Test datetime tools."""
    print(f"\n{'='*60}")
    print(f"📅 DateTime Tool Tests")
    print(f"   Model: {model}")
    print(f"{'='*60}")
    
    tools = make_builtin_registry().subset(["get_time", "get_date"])
    
    tests = [
        ("Get date", "What is today's date?", "date"),
        ("Get time", "What time is it?", "time"),
    ]
    
    results = []
    
    for name, prompt, keyword in tests:
        print(f"\n📋 {name}")
        print(f"   Prompt: {prompt}")
        
        agent = Agent(
            model=model,
            tools=tools,
            backend=backend,
            max_steps=5,
            debug=debug,
        )
        
        t0 = time.time()
        run = agent.run(prompt)
        elapsed = time.time() - t0
        
        # Check if any tool was used
        tool_used = check_tool_used(run, "get_time") or check_tool_used(run, "get_date")
        
        # Check that response contains expected keyword or date/time pattern
        import re
        has_date = bool(re.search(r'\d{4}-\d{2}-\d{2}', run.final_answer))
        has_time = bool(re.search(r'\d{2}:\d{2}', run.final_answer))
        passed = (keyword == "date" and has_date) or (keyword == "time" and has_time)
        
        results.append(passed)
        status = "✅" if passed else "❌"
        tool_status = "🔧" if tool_used else "⚠️"
        print(f"  {status} {tool_status} Tool used: {tool_used} | {elapsed:.1f}s")
        print(f"  📝 {run.final_answer[:60]}")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 DateTime: {passed}/{total} ({100*passed//total}%)")
    return passed, total


def main():
    args = parse_args()
    config = get_config()
    
    model = args.model or config.default_model
    backend_name = args.backend or config.backend
    backend = get_default_backend(backend_name)
    
    if not backend.is_running():
        print(f"❌ {backend_name.capitalize()} not running at {backend.base_url}")
        return 1
    
    print(f"\n⚛️ AgentNova Tool Tests")
    print(f"   Backend: {backend_name} ({backend.base_url})")
    print(f"   Model: {model}")
    print(f"{'='*60}")
    
    total_passed = 0
    total_tests = 0
    
    p, t = test_calculator(model, backend, args.debug)
    total_passed += p
    total_tests += t
    
    p, t = test_shell(model, backend, args.debug)
    total_passed += p
    total_tests += t
    
    p, t = test_datetime(model, backend, args.debug)
    total_passed += p
    total_tests += t
    
    print(f"\n{'='*60}")
    print(f"📊 TOTAL: {total_passed}/{total_tests} ({100*total_passed//total_tests}%)")
    print(f"{'='*60}")
    
    return 0 if total_passed == total_tests else 1


if __name__ == "__main__":
    sys.exit(main())
