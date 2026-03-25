#!/usr/bin/env python3
"""
examples/07_logical_deduction.py
--------------------------------
Logical deduction tests (from BIG-bench).

Tests logical reasoning abilities:
  • Syllogisms and deductive reasoning
  • Conditional reasoning
  • Quantifiers and set logic

Usage:
  python examples/07_logical_deduction.py
  python examples/07_logical_deduction.py --model qwen2.5:0.5b --debug
  agentnova test 07

Environment Variables:
  OLLAMA_BASE_URL     - Ollama server URL
  AGENTNOVA_MODEL     - Default model

Written by VTSTech — https://www.vts-tech.org
"""

import sys
import os
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentnova import Agent, get_config
from agentnova.backends import get_default_backend


def parse_args():
    parser = argparse.ArgumentParser(description="AgentNova Logical Deduction Tests")
    parser.add_argument("-m", "--model", default=None, help="Model to test")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--backend", choices=["ollama", "bitnet"], default=None)
    return parser.parse_args()


# Logical deduction tests (inspired by BIG-bench)
TESTS = [
    # Simple syllogisms
    {
        "category": "Syllogisms",
        "prompt": "All cats are animals. All animals need water. Does a cat need water? Answer yes or no.",
        "expected": "yes",
        "type": "exact",
    },
    {
        "category": "Syllogisms",
        "prompt": "All dogs are mammals. All mammals are warm-blooded. Are dogs warm-blooded? Answer yes or no.",
        "expected": "yes",
        "type": "exact",
    },
    {
        "category": "Syllogisms",
        "prompt": "All birds have feathers. All eagles are birds. Do eagles have feathers? Answer yes or no.",
        "expected": "yes",
        "type": "exact",
    },
    {
        "category": "Syllogisms",
        "prompt": "All roses are flowers. Some flowers are red. Can we conclude that some roses are red? Answer yes, no, or uncertain.",
        "expected": "uncertain",
        "type": "exact",
    },
    {
        "category": "Syllogisms",
        "prompt": "All students study. Some students are lazy. Can we conclude that some lazy people study? Answer yes or no.",
        "expected": "yes",
        "type": "exact",
    },
    
    # Conditional reasoning
    {
        "category": "Conditionals",
        "prompt": "If it rains, the ground gets wet. It is raining. Is the ground wet? Answer yes or no.",
        "expected": "yes",
        "type": "exact",
    },
    {
        "category": "Conditionals",
        "prompt": "If it rains, the ground gets wet. The ground is wet. Did it definitely rain? Answer yes or no.",
        "expected": "no",
        "type": "exact",
    },
    {
        "category": "Conditionals",
        "prompt": "If you study, you will pass. You did not pass. Did you study? Answer yes or no.",
        "expected": "no",
        "type": "exact",
    },
    {
        "category": "Conditionals",
        "prompt": "If the light is on, someone is home. The light is off. Is anyone definitely not home? Answer yes or no.",
        "expected": "no",
        "type": "exact",
    },
    {
        "category": "Conditionals",
        "prompt": "If it snows, schools close. Schools are closed. Did it snow? Answer yes, no, or uncertain.",
        "expected": "uncertain",
        "type": "exact",
    },
    
    # Transitive reasoning
    {
        "category": "Transitive",
        "prompt": "John is taller than Mary. Mary is taller than Sue. Is John taller than Sue? Answer yes or no.",
        "expected": "yes",
        "type": "exact",
    },
    {
        "category": "Transitive",
        "prompt": "A is bigger than B. B is bigger than C. C is bigger than D. Is A bigger than D? Answer yes or no.",
        "expected": "yes",
        "type": "exact",
    },
    {
        "category": "Transitive",
        "prompt": "X is older than Y. Y is older than Z. Is Z older than X? Answer yes or no.",
        "expected": "no",
        "type": "exact",
    },
    {
        "category": "Transitive",
        "prompt": "Team A beat Team B. Team B beat Team C. Can we conclude that Team A would beat Team C? Answer yes or no.",
        "expected": "no",
        "type": "exact",
    },
    {
        "category": "Transitive",
        "prompt": "Alice arrived before Bob. Bob arrived before Carol. Who arrived last? Answer with one name.",
        "expected": "carol",
        "type": "exact",
    },
    
    # Quantifiers
    {
        "category": "Quantifiers",
        "prompt": "All apples are fruits. Is every apple a fruit? Answer yes or no.",
        "expected": "yes",
        "type": "exact",
    },
    {
        "category": "Quantifiers",
        "prompt": "Some birds cannot fly. Does this mean all birds can fly? Answer yes or no.",
        "expected": "no",
        "type": "exact",
    },
    {
        "category": "Quantifiers",
        "prompt": "No fish are mammals. Are any fish mammals? Answer yes or no.",
        "expected": "no",
        "type": "exact",
    },
    {
        "category": "Quantifiers",
        "prompt": "Every student passed. Did all students pass? Answer yes or no.",
        "expected": "yes",
        "type": "exact",
    },
    {
        "category": "Quantifiers",
        "prompt": "Not all cars are red. Are some cars not red? Answer yes or no.",
        "expected": "yes",
        "type": "exact",
    },
    
    # Counter-intuitive logic
    {
        "category": "Counter-intuitive",
        "prompt": "A bat and ball cost $1.10 total. The bat costs $1 more than the ball. How much does the ball cost in cents? Just give the number.",
        "expected": "5",
        "type": "number",
    },
    {
        "category": "Counter-intuitive",
        "prompt": "It takes 10 machines 10 minutes to make 10 widgets. How many minutes would it take 100 machines to make 100 widgets? Just give the number.",
        "expected": "10",
        "type": "number",
    },
    {
        "category": "Counter-intuitive",
        "prompt": "In a lake, there is a patch of lily pads. Every day, the patch doubles in size. If it takes 48 days for the patch to cover the entire lake, how many days would it take to cover half the lake? Just give the number.",
        "expected": "47",
        "type": "number",
    },
    {
        "category": "Counter-intuitive",
        "prompt": "A snail climbs up a 10-foot pole. Each day it climbs 3 feet, but each night it slides down 2 feet. How many days does it take to reach the top? Just give the number.",
        "expected": "8",
        "type": "number",
    },
    {
        "category": "Counter-intuitive",
        "prompt": "If you have 3 socks in a drawer (black, white, black), what is the minimum number you must pull out to guarantee a matching pair? Just give the number.",
        "expected": "3",
        "type": "number",
    },
]


def extract_number(response: str) -> str:
    """Extract number from text."""
    import re
    match = re.search(r'-?\d+\.?\d*', response.replace(',', ''))
    return match.group(0) if match else ""


def check_answer(response: str, expected: str, check_type: str) -> bool:
    """Check if response matches expected answer."""
    response_lower = response.lower()
    expected_lower = expected.lower()
    
    if check_type == "exact":
        return expected_lower in response_lower
    
    elif check_type == "number":
        resp_num = extract_number(response_lower)
        exp_num = extract_number(expected_lower)
        if resp_num and exp_num:
            try:
                return abs(float(resp_num) - float(exp_num)) < 0.01
            except ValueError:
                return False
        return False
    
    return False


def run_tests(model: str, backend, debug: bool = False) -> dict:
    """Run logical deduction tests for a model."""
    print(f"\n{'='*60}")
    print(f"?  Logical Deduction Tests: {model}")
    print(f"{'='*60}")
    
    results = {"model": model, "passed": 0, "total": len(TESTS), "time": 0, "categories": {}}
    
    agent = Agent(
        model=model,
        backend=backend,
        max_steps=1,
        debug=debug,
    )
    
    for test in TESTS:
        category = test["category"]
        prompt = test["prompt"]
        expected = test["expected"]
        check_type = test["type"]
        
        print(f"\n?  [{category}] {prompt[:55]}...")
        
        t0 = time.time()
        run = agent.run(prompt)
        elapsed = time.time() - t0
        results["time"] += elapsed
        
        response = run.final_answer
        passed = check_answer(response, expected, check_type)
        
        if category not in results["categories"]:
            results["categories"][category] = {"passed": 0, "total": 0}
        results["categories"][category]["total"] += 1
        if passed:
            results["categories"][category]["passed"] += 1
        
        results["passed"] += int(passed)
        
        status = "?" if passed else "?"
        print(f"  {status} Expected: {expected} | Got: {response[:50]}")
        print(f"     {elapsed:.1f}s")
    
    return results


def main():
    args = parse_args()
    config = get_config()
    
    model = args.model or config.default_model
    backend_name = args.backend or config.backend
    backend = get_default_backend(backend_name)
    
    if not backend.is_running():
        print(f"? {backend_name.capitalize()} not running at {backend.base_url}")
        return {"passed": 0, "total": len(TESTS), "time": 0, "exit_code": 1}
    
    print(f"\n?? AgentNova Logical Deduction Tests ({len(TESTS)} questions)")
    print(f"   Backend: {backend_name} ({backend.base_url})")
    print(f"   Model: {model}")
    
    result = run_tests(model, backend, args.debug)
    
    print(f"\n{'='*60}")
    print("?  Results by Category")
    print(f"{'='*60}")
    
    for category, stats in result["categories"].items():
        pct = stats["passed"] / stats["total"] * 100
        bar = "?" * stats["passed"] + "?" * (stats["total"] - stats["passed"])
        print(f"  {category:<18} {bar} {stats['passed']}/{stats['total']} ({pct:.0f}%)")
    
    pass_rate = result["passed"] / result["total"] * 100
    print(f"\n?  Overall: {result['passed']}/{result['total']} ({pass_rate:.0f}%) in {result['time']:.1f}s")
    print(f"{'='*60}")
    
    result["exit_code"] = 0 if result["passed"] == result["total"] else 1
    return result


if __name__ == "__main__":
    result = main()
    sys.exit(result.get("exit_code", 0))