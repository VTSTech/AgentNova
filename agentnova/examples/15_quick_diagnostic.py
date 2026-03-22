#!/usr/bin/env python3
"""
examples/15_quick_diagnostic.py
--------------------------------
Quick 5-question diagnostic for rapid iteration and debugging.

Runs in ~30-60 seconds per model instead of 20+ minutes for full GSM8K.

Usage:
  agentnova test 15 --model qwen3:0.6b
  agentnova test 15 --model granite3.1-moe:1b --debug
  agentnova test 15 --model all

Questions are designed to catch common failure modes:
  Q1: Simple math (tests basic calculator tool usage)
  Q2: Multi-step reasoning (tests observation handling)
  Q3: Division with fraction (tests precision)
  Q4: Word problem (tests natural language → expression)
  Q5: Edge case reasoning (tests refusal handling)

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

import sys
import os
import time
import re
import unicodedata
import argparse

# Add project root (parent of agentnova package) to path
# __file__ = .../agentnova/examples/15_quick_diagnostic.py
# dirname(__file__) = .../agentnova/examples
# dirname(dirname(__file__)) = .../agentnova (package dir)
# dirname(dirname(dirname(__file__))) = ... (project root with agentnova package)
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _project_root)

from agentnova import Agent, get_default_client, get_tool_support, StepResult
from agentnova.tools.builtins import make_builtin_registry
from agentnova.shared_args import add_shared_args, parse_shared_args, SharedConfig

# Parse CLI args
parser = argparse.ArgumentParser(description="AgentNova Quick Diagnostic")
add_shared_args(parser)
args = parser.parse_args()
config = parse_shared_args(args)

DEBUG = config.debug

# Quick 5-question diagnostic test
# Each question targets a specific failure mode
TESTS = [
    # Q1: Simple math - basic calculator tool usage
    ("Q1: Simple Math", "What is 15 plus 27? Use the calculator tool.", ["calculator"], "42"),
    
    # Q2: Multi-step reasoning - observation handling
    ("Q2: Multi-step", "Calculate 8 times 7, then subtract 5 from the result. Use calculator for each step.", ["calculator"], "51"),
    
    # Q3: Division with fraction - precision test
    ("Q3: Division", "What is 17 divided by 4? Use the calculator tool.", ["calculator"], "4.25"),
    
    # Q4: Word problem - natural language to expression
    ("Q4: Word Problem", "A store has 24 apples. They sell 8 in the morning and 6 in the afternoon. How many apples are left? Use the calculator.", ["calculator"], "10"),
    
    # Q5: Edge case - should calculate, not refuse
    ("Q5: Edge Case", "A store opens at 9 AM and closes at 5 PM. How many hours is it open? Use the calculator to compute 5 minus 9 plus 12 (to handle the time format).", ["calculator"], "8"),
]


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    normalized = unicodedata.normalize('NFD', text.lower())
    without_accents = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    return without_accents.strip()


def extract_number(text: str) -> str | None:
    """Extract the first number from text, handling decimals."""
    # Try to find a number (integer or decimal)
    match = re.search(r'-?\d+\.?\d*', text)
    if match:
        return match.group(0)
    return None


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


def test_model(client, model: str, config: SharedConfig) -> dict:
    """Test a single model and return results."""
    print(f"\n{'='*60}")
    print(f"🧪 Quick Diagnostic: {model}")
    print(f"{'='*60}")
    
    results = {"model": model, "passed": 0, "total": len(TESTS), "time": 0, "tests": {}}
    
    for i, (test_name, prompt, tools, expected) in enumerate(TESTS):
        print(f"  {test_name}...", end=" ", flush=True)
        
        try:
            registry = make_builtin_registry().subset(tools) if tools else None
            tool_support = get_tool_support(model, client)
            
            # Simple system prompt
            system_prompt = """You are a helpful assistant with access to a calculator tool.
When asked to calculate something, ALWAYS use the calculator tool.
Pass the mathematical expression to the calculator (e.g., "15 + 27" or "8 * 7 - 5").
After getting the result, provide the final answer as a number."""
            
            # Use loop index as seed to break KV cache
            model_opts = {"temperature": 0.0, "num_ctx": 1024, "num_predict": 128, "seed": i}
            model_opts.update(config.model_options)
            
            # Create fresh client for each test to avoid state carryover
            from agentnova import get_default_client
            fresh_client = get_default_client()
            
            agent = Agent(
                model=model,
                tools=registry,
                system_prompt=system_prompt,
                max_steps=5,
                client=fresh_client,
                model_options=model_opts,
                force_react=(tool_support == "react"),
                on_step=make_step_callback(DEBUG),
                debug=DEBUG,
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
                    # Compare as floats for flexibility
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
    client = get_default_client()
    
    if not client.is_running():
        print("❌ Ollama is not running. Start it with: ollama serve")
        return
    
    from agentnova.model_discovery import get_available_models
    available = list(dict.fromkeys(get_available_models(client)))
    
    print(f"\n⚛️ AgentNova Quick Diagnostic (5 questions)")
    print(f"   Available models: {', '.join(available[:5])}{'...' if len(available) > 5 else ''}")
    
    # Determine which models to test
    if config.model:
        if config.model == "all":
            models_to_test = available
        else:
            models_to_test = [m for m in available if config.model in m]
            if not models_to_test and config.model in available:
                models_to_test = [config.model]
    else:
        # Default: test first available model
        models_to_test = available[:1]
    
    if not models_to_test:
        print(f"   ⚠️ No models match '{config.model}'")
        return
    
    print(f"   Testing: {', '.join(models_to_test)}")
    
    all_results = []
    for model in models_to_test:
        result = test_model(client, model, config)
        all_results.append(result)
    
    # Summary
    if len(all_results) > 1:
        print(f"\n{'='*60}")
        print("🏆 RANKINGS")
        print(f"{'='*60}")
        sorted_results = sorted(all_results, key=lambda x: (-x["passed"], x["time"]))
        for i, r in enumerate(sorted_results, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
            rate = r["passed"] / r["total"] * 100
            print(f"{medal} {r['model']:<35} {r['passed']}/{r['total']} ({rate:.0f}%) - {r['time']:.1f}s")


if __name__ == "__main__":
    main()