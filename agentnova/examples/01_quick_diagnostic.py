#!/usr/bin/env python3
"""
examples/01_quick_diagnostic.py
-------------------------------
Quick 5-question diagnostic for rapid iteration and debugging.

Tests common failure modes:
  Q1: Simple math (basic calculator tool usage)
  Q2: Multi-step reasoning (observation handling)
  Q3: Division with fraction (precision)
  Q4: Word problem (natural language → expression)
  Q5: Time calculation (practical reasoning)

Usage:
  python examples/01_quick_diagnostic.py
  python examples/01_quick_diagnostic.py --model qwen2.5:0.5b --debug
  agentnova test 01

Environment Variables:
  OLLAMA_BASE_URL     - Ollama server URL
  AGENTNOVA_MODEL     - Default model
  AGENTNOVA_BACKEND   - Backend to use (ollama/bitnet)

Written by VTSTech — https://www.vts-tech.org
"""

import sys
import os
import time
import re
import unicodedata
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentnova import Agent, get_config
from agentnova.backends import get_default_backend
from agentnova.tools import make_builtin_registry


def parse_args():
    parser = argparse.ArgumentParser(description="AgentNova Quick Diagnostic")
    parser.add_argument("-m", "--model", default=None, help="Model to test")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--backend", choices=["ollama", "bitnet"], default=None)
    parser.add_argument("--force-react", action="store_true", help="Force ReAct mode for tool calling")
    return parser.parse_args()


# Quick 5-question diagnostic
TESTS = [
    # Q1: Simple math - basic calculator tool usage
    ("Q1: Simple Math", "What is 15 plus 27? Use the calculator tool.", ["calculator"], "42"),
    
    # Q2: Multi-step reasoning (8*7-5=51)
    ("Q2: Multi-step", "Calculate 8 times 7 minus 5. Use the calculator.", ["calculator"], "51"),
    
    # Q3: Division with fraction - precision test
    ("Q3: Division", "What is 17 divided by 4? Use the calculator.", ["calculator"], "4.25"),
    
    # Q4: Word problem (24-8-6=10)
    ("Q4: Word Problem", "A store has 24 apples. They sell 8 in the morning and 6 in the afternoon. How many apples are left?", ["calculator"], "10"),
    
    # Q5: Time calculation (5-9+12=8)
    ("Q5: Time Calc", "A store opens at 9 AM and closes at 5 PM. How many hours is it open?", ["calculator"], "8"),
]


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    normalized = unicodedata.normalize('NFD', text.lower())
    without_accents = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    return without_accents.strip()


def extract_number(text: str) -> str | None:
    """Extract the first number from text."""
    match = re.search(r'-?\d+\.?\d*', text)
    return match.group(0) if match else None


def run_diagnostic(model: str, backend, debug: bool = False, force_react: bool = False) -> dict:
    """Run diagnostic tests for a model."""
    print(f"\n{'='*60}")
    print(f"🧪 Quick Diagnostic: {model}")
    print(f"{'='*60}")
    
    results = {"model": model, "passed": 0, "total": len(TESTS), "time": 0, "tests": {}}
    
    # System prompt that instructs the model to use the calculator
    system_prompt = """You are a helpful assistant with access to a calculator tool.
When asked to calculate something, ALWAYS use the calculator tool.
Pass the mathematical expression to the calculator (e.g., "15 + 27" or "8 * 7 - 5").
After getting the result, provide the final answer as a number."""
    
    for i, (test_name, prompt, tools, expected) in enumerate(TESTS):
        print(f"  {test_name}...", end=" ", flush=True)
        
        try:
            # Build tools
            tool_registry = make_builtin_registry().subset(tools) if tools else None
            
            agent = Agent(
                model=model,
                tools=tool_registry,
                backend=backend,
                max_steps=5,
                debug=debug,
                force_react=force_react,
                system_prompt=system_prompt,
            )
            
            t0 = time.time()
            run = agent.run(prompt)
            elapsed = time.time() - t0
            results["time"] += elapsed
            
            response = run.final_answer
            response_norm = normalize_text(response)
            expected_norm = normalize_text(expected)
            
            # Try exact match first
            passed = expected_norm in response_norm
            
            # If not found, try extracting numbers
            if not passed:
                resp_num = extract_number(response_norm)
                exp_num = extract_number(expected_norm)
                if resp_num and exp_num:
                    try:
                        passed = abs(float(resp_num) - float(exp_num)) < 0.01
                    except ValueError:
                        pass
            
            results["passed"] += int(passed)
            results["tests"][test_name] = {
                "passed": passed,
                "time": elapsed,
                "response": response[:100],
                "expected": expected,
            }
            
            if passed:
                print(f"✅ ({elapsed:.1f}s)")
            else:
                print(f"❌ ({elapsed:.1f}s)")
                print(f"      Expected: {expected}, Got: {response[:80]}")
            
        except Exception as e:
            results["tests"][test_name] = {"passed": False, "error": str(e)[:100]}
            print(f"❌ ERROR: {str(e)[:50]}")
    
    pass_rate = results["passed"] / results["total"] * 100
    print(f"\n  📊 Result: {results['passed']}/{results['total']} ({pass_rate:.0f}%) in {results['time']:.1f}s")
    
    return results


def main():
    args = parse_args()
    config = get_config()
    
    # Enable debug output
    if args.debug:
        os.environ["AGENTNOVA_DEBUG"] = "1"
    
    # Get model
    model = args.model or config.default_model
    
    # Get backend
    backend_name = args.backend or config.backend
    backend = get_default_backend(backend_name)
    
    # Check if running
    if not backend.is_running():
        print(f"❌ {backend_name.capitalize()} not running at {backend.base_url}")
        if backend_name == "ollama":
            print("   Start with: ollama serve")
            print("   Or set OLLAMA_BASE_URL to your remote server")
        return {"passed": 0, "total": 1, "time": 0, "exit_code": 1}
    
    print(f"\n⚛️ AgentNova Quick Diagnostic (5 questions)")
    print(f"   Backend: {backend_name} ({backend.base_url})")
    print(f"   Model: {model}")
    if args.force_react:
        print(f"   Force ReAct: True")
    
    result = run_diagnostic(model, backend, debug=args.debug, force_react=args.force_react)
    
    # Return granular results for test runner, exit_code for direct execution
    result["exit_code"] = 0 if result["passed"] == result["total"] else 1
    return result


if __name__ == "__main__":
    result = main()
    sys.exit(result.get("exit_code", 0))