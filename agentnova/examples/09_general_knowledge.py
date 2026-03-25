#!/usr/bin/env python3
"""
examples/09_general_knowledge.py
---------------------------------
General knowledge tests (from BIG-bench).

Tests factual knowledge across domains:
  • Geography and capitals
  • Science and nature
  • History and culture
  • Math and measurements

Usage:
  python examples/09_general_knowledge.py
  python examples/09_general_knowledge.py --model qwen2.5:0.5b --debug
  agentnova test 09

Environment Variables:
  OLLAMA_BASE_URL     - Ollama server URL
  AGENTNOVA_MODEL     - Default model

Written by VTSTech — https://www.vts-tech.org
"""

import sys
import os
import time
import argparse
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentnova import Agent, get_config
from agentnova.backends import get_default_backend


def parse_args():
    parser = argparse.ArgumentParser(description="AgentNova General Knowledge Tests")
    parser.add_argument("-m", "--model", default=None, help="Model to test")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--backend", choices=["ollama", "bitnet"], default=None)
    return parser.parse_args()


# General knowledge tests (from BIG-bench general_knowledge)
TESTS = [
    # Geography - Capitals
    {
        "category": "Geography",
        "prompt": "What is the capital of France? Answer with one word.",
        "expected": "paris",
        "type": "exact",
    },
    {
        "category": "Geography",
        "prompt": "What is the capital of Japan? Answer with one word.",
        "expected": "tokyo",
        "type": "exact",
    },
    {
        "category": "Geography",
        "prompt": "What is the capital of Germany? Answer with one word.",
        "expected": "berlin",
        "type": "exact",
    },
    {
        "category": "Geography",
        "prompt": "What is the capital of Australia? Answer with one word.",
        "expected": "canberra",
        "type": "exact",
    },
    {
        "category": "Geography",
        "prompt": "What is the capital of China? Answer with one word.",
        "expected": "beijing",
        "type": "exact",
    },
    
    # Geography - Landmarks
    {
        "category": "Geography",
        "prompt": "What is the largest continent on Earth by area? Answer with one word.",
        "expected": "asia",
        "type": "exact",
    },
    {
        "category": "Geography",
        "prompt": "Which ocean is the largest? Answer with one word.",
        "expected": "pacific",
        "type": "exact",
    },
    {
        "category": "Geography",
        "prompt": "What is the longest river in the world? Answer with one word.",
        "expected": "nile",
        "type": "exact",
    },
    {
        "category": "Geography",
        "prompt": "What is the largest desert in the world? Answer with one word.",
        "expected": "sahara",
        "type": "exact",
    },
    {
        "category": "Geography",
        "prompt": "Which country has the most people? Answer with one word.",
        "expected": "india",
        "type": "exact",
    },
    
    # Science - Astronomy
    {
        "category": "Science",
        "prompt": "What planet in our solar system is closest to the sun? Answer with one word.",
        "expected": "mercury",
        "type": "exact",
    },
    {
        "category": "Science",
        "prompt": "What is the largest planet in our solar system? Answer with one word.",
        "expected": "jupiter",
        "type": "exact",
    },
    {
        "category": "Science",
        "prompt": "What is the second-largest planet in our solar system? Answer with one word.",
        "expected": "saturn",
        "type": "exact",
    },
    {
        "category": "Science",
        "prompt": "How many planets are in our solar system? Answer with a number.",
        "expected": "8",
        "type": "number",
    },
    {
        "category": "Science",
        "prompt": "What is the name of our galaxy? Answer with one or two words.",
        "expected": "milky way",
        "type": "keyword",
    },
    
    # Science - Biology
    {
        "category": "Science",
        "prompt": "What gas do plants absorb from the air for photosynthesis? Answer with one word.",
        "expected": "carbon dioxide",
        "type": "keyword",
    },
    {
        "category": "Science",
        "prompt": "What is the largest organ in the human body? Answer with one word.",
        "expected": "skin",
        "type": "exact",
    },
    {
        "category": "Science",
        "prompt": "How many bones are in the adult human body? Answer with a number.",
        "expected": "206",
        "type": "number",
    },
    {
        "category": "Science",
        "prompt": "What is the hardest substance in the human body? Answer with one word.",
        "expected": "enamel",
        "type": "exact",
    },
    {
        "category": "Science",
        "prompt": "What is the speed of light in a vacuum measured in km per second? Answer with a number.",
        "expected": "300000",
        "type": "number",
    },
    
    # Math and Measurement
    {
        "category": "Math",
        "prompt": "How many sides does a hexagon have? Answer with a number.",
        "expected": "6",
        "type": "number",
    },
    {
        "category": "Math",
        "prompt": "What is the name of a shape with 8 sides? Answer with one word.",
        "expected": "octagon",
        "type": "exact",
    },
    {
        "category": "Math",
        "prompt": "How many degrees are in a circle? Answer with a number.",
        "expected": "360",
        "type": "number",
    },
    {
        "category": "Math",
        "prompt": "What is the value of pi to 2 decimal places? Answer with a number.",
        "expected": "3.14",
        "type": "number",
    },
    {
        "category": "Math",
        "prompt": "How many edges does a cube have? Answer with a number.",
        "expected": "12",
        "type": "number",
    },
]


def check_answer(response: str, expected: str, check_type: str) -> bool:
    """Check if response matches expected answer."""
    response_lower = response.lower()
    expected_lower = expected.lower()
    
    if check_type == "exact":
        # For exact match, check if expected word is in response
        return expected_lower in response_lower
    
    elif check_type == "keyword":
        keywords = expected_lower.split()
        return any(kw in response_lower for kw in keywords)
    
    elif check_type == "number":
        # Extract numbers from both
        resp_nums = re.findall(r'-?\d+\.?\d*', response_lower.replace(',', '').replace(' ', ''))
        exp_nums = re.findall(r'-?\d+\.?\d*', expected_lower)
        
        if resp_nums and exp_nums:
            try:
                resp_val = float(resp_nums[0])
                exp_val = float(exp_nums[0])
                # Allow some tolerance
                if exp_val > 1000:
                    return abs(resp_val - exp_val) < exp_val * 0.1  # 10% tolerance for large numbers
                return abs(resp_val - exp_val) < 1.0
            except ValueError:
                return False
        return False
    
    return False


def run_tests(model: str, backend, debug: bool = False) -> dict:
    """Run general knowledge tests for a model."""
    print(f"\n{'='*60}")
    print(f"🌍 General Knowledge Tests: {model}")
    print(f"{'='*60}")
    
    results = {"model": model, "passed": 0, "total": len(TESTS), "time": 0, "categories": {}}
    
    # Note: We create a fresh agent for each test to avoid memory contamination
    
    for test in TESTS:
        category = test["category"]
        prompt = test["prompt"]
        expected = test["expected"]
        check_type = test["type"]
        
        print(f"\n📋 [{category}] {prompt}...")
        
        # Create fresh agent for each test (isolates memory)
        agent = Agent(
            model=model,
            backend=backend,
            max_steps=1,
            debug=debug,
        )
        
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
        
        status = "✅" if passed else "❌"
        print(f"  {status} Expected: {expected} | Got: {response}")
        print(f"     {elapsed:.1f}s")
    
    return results


def main():
    args = parse_args()
    config = get_config()
    
    model = args.model or config.default_model
    backend_name = args.backend or config.backend
    backend = get_default_backend(backend_name)
    
    if not backend.is_running():
        print(f"❌ {backend_name.capitalize()} not running at {backend.base_url}")
        return {"passed": 0, "total": len(TESTS), "time": 0, "exit_code": 1}
    
    print(f"\n⚛️ AgentNova General Knowledge Tests ({len(TESTS)} questions)")
    print(f"   Backend: {backend_name} ({backend.base_url})")
    print(f"   Model: {model}")
    
    result = run_tests(model, backend, args.debug)
    
    print(f"\n{'='*60}")
    print("📊 Results by Category")
    print(f"{'='*60}")
    
    for category, stats in result["categories"].items():
        pct = stats["passed"] / stats["total"] * 100
        bar = "█" * stats["passed"] + "░" * (stats["total"] - stats["passed"])
        print(f"  {category:<15} {bar} {stats['passed']}/{stats['total']} ({pct:.0f}%)")
    
    pass_rate = result["passed"] / result["total"] * 100
    print(f"\n📊 Overall: {result['passed']}/{result['total']} ({pass_rate:.0f}%) in {result['time']:.1f}s")
    print(f"{'='*60}")
    
    result["exit_code"] = 0 if result["passed"] == result["total"] else 1
    return result


if __name__ == "__main__":
    result = main()
    sys.exit(result.get("exit_code", 0))