#!/usr/bin/env python3
"""
examples/08_reading_comprehension.py
------------------------------------
Reading comprehension tests.

Tests ability to understand and extract information from text:
  • Factual extraction
  • Inference from text
  • Main idea identification
  • Detail questions

Usage:
  python examples/08_reading_comprehension.py
  python examples/08_reading_comprehension.py --model qwen2.5:0.5b --debug
  agentnova test 08

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
    parser = argparse.ArgumentParser(description="AgentNova Reading Comprehension Tests")
    parser.add_argument("-m", "--model", default=None, help="Model to test")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--backend", choices=["ollama", "bitnet"], default=None)
    return parser.parse_args()


# Reading comprehension tests
TESTS = [
    # Factual extraction
    {
        "category": "Factual",
        "prompt": """Read: "Marie Curie was a physicist and chemist who conducted pioneering research on radioactivity. She was the first woman to win a Nobel Prize and the only person to win Nobel Prizes in two different sciences."
Question: What field did Marie Curie research? Answer with one word.""",
        "expected": "radioactivity",
        "type": "keyword",
    },
    {
        "category": "Factual",
        "prompt": """Read: "The Great Wall of China is over 13,000 miles long and was built over many centuries to protect against invasions."
Question: How long is the Great Wall of China? Answer with a number.""",
        "expected": "13000",
        "type": "number",
    },
    {
        "category": "Factual",
        "prompt": """Read: "Photosynthesis is the process by which plants use sunlight, water, and carbon dioxide to create oxygen and energy in the form of sugar."
Question: What gas do plants produce during photosynthesis? Answer with one word.""",
        "expected": "oxygen",
        "type": "exact",
    },
    {
        "category": "Factual",
        "prompt": """Read: "The Amazon River flows through South America and is approximately 4,000 miles long, making it the second-longest river in the world."
Question: Which continent does the Amazon River flow through? Answer with one word.""",
        "expected": "america",
        "type": "keyword",
    },
    {
        "category": "Factual",
        "prompt": """Read: "The human heart has four chambers: the left and right atria, and the left and right ventricles."
Question: How many chambers does the human heart have? Answer with a number.""",
        "expected": "4",
        "type": "number",
    },
    
    # Inference
    {
        "category": "Inference",
        "prompt": """Read: "Sarah forgot her umbrella at home. When she walked outside, dark clouds filled the sky."
Question: What is likely to happen to Sarah? Answer in a short phrase.""",
        "expected": "wet",
        "type": "keyword",
    },
    {
        "category": "Inference",
        "prompt": """Read: "The restaurant was completely empty at 8 PM on a Saturday. The chef was sleeping in the kitchen."
Question: Is the restaurant popular? Answer yes or no.""",
        "expected": "no",
        "type": "exact",
    },
    {
        "category": "Inference",
        "prompt": """Read: "Tom studied for three weeks straight. He barely slept the night before. When results came out, he smiled."
Question: Did Tom likely pass? Answer yes or no.""",
        "expected": "yes",
        "type": "exact",
    },
    {
        "category": "Inference",
        "prompt": """Read: "The phone kept ringing but no one answered. The lights were off and the mailbox was overflowing."
Question: Are the residents likely home? Answer yes or no.""",
        "expected": "no",
        "type": "exact",
    },
    {
        "category": "Inference",
        "prompt": """Read: "Despite the heavy rain, the soccer game continued. The players were covered in mud by halftime."
Question: Is this an indoor or outdoor game? Answer with one word.""",
        "expected": "outdoor",
        "type": "exact",
    },
    
    # Main idea
    {
        "category": "Main Idea",
        "prompt": """Read: "Honey never spoils. Archaeologists have found 3000-year-old honey in Egyptian tombs that was still perfectly edible. This is because honey has low moisture and is acidic, making it difficult for bacteria to grow."
Question: What is the main idea? Answer in one sentence.""",
        "expected": "spoil",
        "type": "keyword",
    },
    {
        "category": "Main Idea",
        "prompt": """Read: "Many people think goldfish have a three-second memory, but this is a myth. Scientists have proven that goldfish can remember things for months and can even be trained to perform tricks."
Question: What misconception does this passage address? Answer briefly.""",
        "expected": "memory",
        "type": "keyword",
    },
    {
        "category": "Main Idea",
        "prompt": """Read: "Coffee is one of the most traded commodities in the world. It is grown in over 70 countries, with Brazil being the largest producer. Over 2 billion cups of coffee are consumed daily worldwide."
Question: What is this passage mainly about? Answer with one word.""",
        "expected": "coffee",
        "type": "exact",
    },
    {
        "category": "Main Idea",
        "prompt": """Read: "The printing press, invented by Gutenberg around 1440, revolutionized communication. Before it, books were hand-copied and extremely expensive. The printing press made books affordable and knowledge accessible to many more people."
Question: What effect did the printing press have? Answer briefly.""",
        "expected": "accessible",
        "type": "keyword",
    },
    {
        "category": "Main Idea",
        "prompt": """Read: "Dolphins sleep with one eye open. Half of their brain stays awake to watch for predators and control breathing, while the other half rests. This is called unihemispheric sleep."
Question: How do dolphins sleep differently from humans? Answer briefly.""",
        "expected": "eye",
        "type": "keyword",
    },
    
    # Sequencing
    {
        "category": "Sequencing",
        "prompt": """Read: "First, the chef chopped the vegetables. Then he heated the oil in a pan. After that, he added the vegetables and stirred them for five minutes. Finally, he added the sauce."
Question: What happened immediately after heating the oil? Answer briefly.""",
        "expected": "vegetables",
        "type": "keyword",
    },
    {
        "category": "Sequencing",
        "prompt": """Read: "The seed was planted in spring. By summer, it had grown into a small plant. In fall, flowers appeared. By winter, the plant died back."
Question: In which season did the plant flower? Answer with one word.""",
        "expected": "fall",
        "type": "exact",
    },
    {
        "category": "Sequencing",
        "prompt": """Read: "John woke up at 7 AM. He ate breakfast at 7:30. He left for work at 8:15. He arrived at the office at 9:00."
Question: What did John do between breakfast and leaving for work? Answer with a time-based phrase.""",
        "expected": "left",
        "type": "keyword",
    },
    {
        "category": "Sequencing",
        "prompt": """Read: "The match started at 3 PM. The first goal was scored at 3:25. Halftime was at 4:00. The match ended at 5:00."
Question: What happened first? Answer with one phrase.""",
        "expected": "started",
        "type": "keyword",
    },
    {
        "category": "Sequencing",
        "prompt": """Read: "The order was placed on Monday. It shipped on Wednesday. It arrived on Friday. The customer returned it on Saturday."
Question: How many days between placing the order and receiving it? Answer with a number.""",
        "expected": "4",
        "type": "number",
    },
    
    # Vocabulary in context
    {
        "category": "Vocabulary",
        "prompt": """Read: "The ancient artifact was fragile, so the archaeologists handled it with extreme care."
Question: What does fragile mean in this context? Answer with one word.""",
        "expected": "delicate",
        "type": "keyword",
    },
    {
        "category": "Vocabulary",
        "prompt": """Read: "Despite the arduous journey, the explorers finally reached their destination."
Question: What kind of journey was it? Answer with one word.""",
        "expected": "difficult",
        "type": "keyword",
    },
    {
        "category": "Vocabulary",
        "prompt": """Read: "Her meticulous attention to detail made her an excellent proofreader."
Question: Does meticulous mean careful or careless? Answer with one word.""",
        "expected": "careful",
        "type": "exact",
    },
    {
        "category": "Vocabulary",
        "prompt": """Read: "The singer's performance was mediocre at best; the audience was clearly disappointed."
Question: Was the performance excellent or average? Answer with one word.""",
        "expected": "average",
        "type": "keyword",
    },
    {
        "category": "Vocabulary",
        "prompt": """Read: "The abundant harvest meant the farmers would have plenty to sell at market."
Question: Does abundant mean plentiful or scarce? Answer with one word.""",
        "expected": "plentiful",
        "type": "exact",
    },
]


def check_answer(response: str, expected: str, check_type: str) -> bool:
    """Check if response matches expected answer."""
    response_lower = response.lower()
    expected_lower = expected.lower()
    
    if check_type == "exact":
        return expected_lower in response_lower
    
    elif check_type == "keyword":
        keywords = expected_lower.split()
        return any(kw in response_lower for kw in keywords)
    
    elif check_type == "number":
        import re
        resp_nums = re.findall(r'\d+\.?\d*', response_lower.replace(',', ''))
        exp_nums = re.findall(r'\d+\.?\d*', expected_lower)
        if resp_nums and exp_nums:
            try:
                return abs(float(resp_nums[0]) - float(exp_nums[0])) < 0.5
            except ValueError:
                return False
        return False
    
    return False


def run_tests(model: str, backend, debug: bool = False) -> dict:
    """Run reading comprehension tests for a model."""
    print(f"\n{'='*60}")
    print(f"📖 Reading Comprehension Tests: {model}")
    print(f"{'='*60}")
    
    results = {"model": model, "passed": 0, "total": len(TESTS), "time": 0, "categories": {}}
    
    # Note: We create a fresh agent for each test to avoid memory contamination
    
    for test in TESTS:
        category = test["category"]
        prompt = test["prompt"]
        expected = test["expected"]
        check_type = test["type"]
        
        print(f"\n📋 [{category}] {prompt[:50]}...")
        
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
        print(f"❌ {backend_name.capitalize()} not running at {backend.base_url}")
        return {"passed": 0, "total": len(TESTS), "time": 0, "exit_code": 1}
    
    print(f"\n⚛️ AgentNova Reading Comprehension Tests ({len(TESTS)} questions)")
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