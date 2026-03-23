"""
examples/09_expanded_benchmark.py
---------------------------------
Expanded benchmark with 25 tests across 8 categories.
Includes multi-step reasoning, comparison, and tool chaining.

Run: python examples/09_expanded_benchmark.py

With CLI:
  agentnova test 09
  agentnova test 09 --acp
  agentnova test 09 --use-mf-sys --model qwen2.5-coder:0.5b

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

import sys
import os
import time
import re
import json
import unicodedata
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentnova import Agent, get_default_client, get_tool_support, AGENTNOVA_BACKEND, StepResult
from agentnova.tools.builtins import make_builtin_registry
from agentnova.model_discovery import get_available_models, pick_best_model
from agentnova.shared_args import add_shared_args, parse_shared_args

# Parse CLI args (with env var fallbacks)
parser = argparse.ArgumentParser(description="AgentNova Expanded Benchmark")
add_shared_args(parser)
args = parser.parse_args()
config = parse_shared_args(args)

# Check for optional ACP support
USE_ACP = config.acp
if USE_ACP:
    try:
        from agentnova.acp_plugin import ACPPlugin
    except ImportError:
        print("⚠️ ACP requested but ACPPlugin not available")
        USE_ACP = False

# Check for debug mode
DEBUG = config.debug

BACKEND_NAME = AGENTNOVA_BACKEND.upper()


def normalize_text(text: str) -> str:
    """Normalize text: lowercase, remove accents."""
    normalized = unicodedata.normalize('NFD', text.lower())
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')


def print_step(step: StepResult):
    """Print step information for debug output."""
    if step.type == "tool_call":
        args = ", ".join(f"{k}={v}" for k, v in (step.tool_args or {}).items())
        print(f"      🔧 {step.tool_name}({args})")
    elif step.type == "tool_result":
        preview = step.content[:80] + "..." if len(step.content) > 80 else step.content
        print(f"      📦 → {preview}")


def check_tool_used(run, tool_name: str) -> bool:
    """Verify that a specific tool was actually called during the run."""
    for step in run.steps:
        if step.type == "tool_call" and step.tool_name == tool_name:
            return True
    return False


def make_step_callback(verbose: bool = True):
    """Create a step callback for debug output."""
    def on_step(step: StepResult):
        if verbose:
            print_step(step)
    return on_step


# System prompts
SYSTEM_PROMPT_NO_TOOLS = """You are a helpful assistant. Answer concisely and directly."""

SYSTEM_PROMPT_WITH_TOOLS = """You are a helpful assistant with access to tools. Use tools when needed."""

# ReAct-specific prompt for text-based tool calling
SYSTEM_PROMPT_REACT = """You are a helpful assistant with access to tools.

When you need to use a tool, follow this EXACT format:

Thought: I need to [what you want to do]
Action: tool_name
Action Input: {"param": "value"}
Observation: [result will appear here]
... (repeat as needed)
Final Answer: [your answer]

IMPORTANT: Always use the calculator tool for arithmetic.

Example:
Question: What is 15 times 8?
Thought: I need to multiply 15 by 8
Action: calculator
Action Input: {"expression": "15 * 8"}
Observation: 120
Final Answer: 120"""


# 25 tests: 8 categories
# Fair prompts without answer spoilers
TESTS = [
    # === MATH (3 tests) - Basic arithmetic ===
    ('Math', 'Multiply', 'What is 7 * 8? Answer with just the number.', None, '56'),
    ('Math', 'Add', 'What is 25 + 17? Answer with just the number.', None, '42'),
    ('Math', 'Divide', 'What is 144 / 12? Answer with just the number.', None, '12'),

    # === REASONING (4 tests) - Multi-step thinking ===
    ('Reason', 'Apples', 'I have 10 apples. I give 3 to Bob and 2 to Alice. How many apples do I have left? Answer with just the number.', None, '5'),
    ('Reason', 'Sequence', 'What comes next in this sequence: 2, 4, 6, 8, ? Answer with just the number.', None, '10'),
    ('Reason', 'Logic', 'All cats are animals. Fluffy is a cat. What category does Fluffy belong to? Answer with one word.', None, 'animal'),
    ('Reason', 'Marbles', 'I have 100 marbles. I remove 20, then remove 15 more. How many marbles do I have left? Answer with just the number.', None, '65'),

    # === KNOWLEDGE (3 tests) - World facts ===
    ('Know', 'Japan', 'What is the capital of Japan? Answer with one word.', None, 'tokyo'),
    ('Know', 'France', 'What is the capital of France? Answer with one word.', None, 'paris'),
    ('Know', 'Brazil', 'What is the capital of Brazil? Answer with one word.', None, 'brasilia'),

    # === CALC TOOL (3 tests) - Calculator tool usage ===
    ('Calc', 'Multiply', 'Use the calculator tool to compute 15 times 8.', ['calculator'], '120'),
    ('Calc', 'Divide', 'Use the calculator tool to compute 100 divided by 4.', ['calculator'], '25'),
    ('Calc', 'Power', 'Use the calculator tool to compute 2 to the power of 10.', ['calculator'], '1024'),

    # === CODE (3 tests) - Python code generation ===
    ('Code', 'is_even', 'Write a Python function called is_even(n) that returns True if n is even.', None, 'def'),
    ('Code', 'reverse', 'Write a Python function called reverse_string(s) that returns the reversed string.', None, 'def'),
    ('Code', 'max_num', 'Write a Python function called find_max(numbers) that returns the largest number in a list.', None, 'def'),

    # === COMPARISON (3 tests) - Compare values ===
    ('Compare', 'Larger', 'Which is larger: 100 or 99? Answer with the larger number.', None, '100'),
    ('Compare', 'Smaller', 'Which is smaller: 5 or 3? Answer with the smaller number.', None, '3'),
    ('Compare', 'Power', 'Which is larger: 2 to the power of 10, or 3 to the power of 5? Answer with the larger number.', None, '1024'),

    # === MULTI-STEP (3 tests) - Requires multiple operations ===
    ('Multi', 'SquareSum', 'Calculate 3 squared plus 4 squared. Answer with just the number.', None, '25'),
    ('Multi', 'Perimeter', 'A rectangle has width 5 and length 8. Calculate the perimeter (2 times width plus 2 times length). Answer with just the number.', None, '26'),
    ('Multi', 'Average', 'Find the average of 10, 20, and 30. Answer with just the number.', None, '20'),

    # === PYTHON REPL (3 tests) - Code execution with tool ===
    ('Repl', 'List', 'Use the python_repl tool to run: print(list(range(5))). What does it print?', ['python_repl'], '0, 1, 2, 3, 4'),
    ('Repl', 'Sum', 'Use the python_repl tool to run: print(sum([1,2,3,4,5])). What does it print?', ['python_repl'], '15'),
    ('Repl', 'Squares', 'Use the python_repl tool to run: print([x**2 for x in range(4)]). What does it print?', ['python_repl'], '0, 1, 4, 9'),
]

RESULTS_FILE = os.path.join(os.path.dirname(__file__), 'expanded_benchmark_results.json')


def save_results(results):
    """Save results to JSON."""
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)


def test_model(client, model: str, results: dict, force_react: bool = False, acp=None) -> dict:
    """Test a single model, saving progress after each test."""
    if model not in results:
        results[model] = {
            'model': model,
            'tests': {},
            'total': len(TESTS),
            'time': 0
        }

    model_results = results[model]
    
    # Create per-model ACP instance if ACP is enabled
    model_acp = None
    if USE_ACP and acp is None:
        model_short = model.split(':')[0]
        model_acp = ACPPlugin(
            agent_name="AgentNova",
            model_name=model_short,
            debug=DEBUG,
        )
    elif acp:
        model_acp = acp

    for cat, test_name, prompt, tools, expected in TESTS:
        full_name = f"{cat}:{test_name}"

        # Skip already tested
        if full_name in model_results['tests']:
            continue

        print(f"  Testing {full_name}...", end=' ', flush=True)

        try:
            registry = make_builtin_registry().subset(tools) if tools else None
            
            # Detect tool support level
            tool_support = get_tool_support(model, client)
            
            # Choose system prompt based on tools and tool support level
            if tools:
                if tool_support == "none":
                    # Model doesn't support tools - use simple prompt
                    system_prompt = SYSTEM_PROMPT_NO_TOOLS
                    use_react = False
                elif tool_support == "native":
                    # Native tool support - use tools via API
                    system_prompt = SYSTEM_PROMPT_WITH_TOOLS
                    use_react = False
                else:
                    # ReAct mode - text-based tool calling
                    system_prompt = SYSTEM_PROMPT_REACT if force_react else SYSTEM_PROMPT_WITH_TOOLS
                    use_react = True
            else:
                system_prompt = SYSTEM_PROMPT_NO_TOOLS
                use_react = False
            
            agent = Agent(
                model=model,
                tools=registry,
                system_prompt=system_prompt,
                max_steps=5,
                client=client,
                model_options={
                    "temperature": 0.0,     # Deterministic
                    "num_ctx": 512,         # Small context for short answers
                    "num_predict": 64,      # Very short answers
                },
                force_react=use_react,
                on_step=make_step_callback(DEBUG),  # Debug output for tool calls
                debug=DEBUG,  # Enable debug mode in agent
            )

            t0 = time.time()
            run = agent.run(prompt)
            elapsed = time.time() - t0
            
            response = run.final_answer
            
            # Log to ACP
            if model_acp:
                model_acp.log_user_message(prompt)
                model_acp.log_assistant_message(response)

            response_norm = normalize_text(response)
            expected_norm = normalize_text(expected)
            passed = expected_norm in response_norm

            # Check if tools were actually used
            tool_used = None
            if tools and "calculator" in tools:
                tool_used = check_tool_used(run, "calculator")

            # Check for near-misses (correct number in response)
            near_miss = False
            if not passed:
                numbers = re.findall(r'-?\d+\.?\d*', response_norm)
                if numbers and expected_norm.replace('.', '').replace('-', '').isdigit():
                    near_miss = expected_norm in numbers

            model_results['tests'][full_name] = {
                'passed': passed,
                'near_miss': near_miss,
                'time': elapsed,
                'response': response,
                'expected': expected,
                'steps': len(run.steps),  # Track step count
                'tool_used': tool_used,  # Track tool usage
            }

            model_results['time'] += elapsed

            if passed:
                print(f"✅ ({elapsed:.1f}s)")
                if tool_used is not None:
                    print(f"    ⏱️ {len(run.steps)} steps, tool_used={tool_used}")
            elif near_miss:
                print(f"⚠️ NEAR-MISS ({elapsed:.1f}s)")
                print(f"    Expected '{expected}' in numbers: {numbers}")
                if tool_used is not None:
                    print(f"    ⏱️ {len(run.steps)} steps, tool_used={tool_used}")
            else:
                print(f"❌ ({elapsed:.1f}s)")
                if tool_used is not None and not tool_used:
                    print(f"    ⚠️ WARNING: Calculator tool was NOT called - model may have hallucinated!")
                print(f"    Expected '{expected}' in: {response[:80]}...")
                if tool_used is not None:
                    print(f"    ⏱️ {len(run.steps)} steps, tool_used={tool_used}")

        except Exception as e:
            model_results['tests'][full_name] = {
                'passed': False,
                'error': str(e)[:100]
            }
            model_results['time'] += 30  # Penalty
            print(f"❌ ERROR: {str(e)[:50]}")

        # Save after each test
        save_results(results)

    # Calculate final score
    model_results['total'] = len(TESTS)
    return model_results


def main():
    # Get force_react from config
    force_react = config.force_react
    
    # Initialize ACP if enabled
    main_acp = None
    if USE_ACP:
        main_acp = ACPPlugin(
            agent_name="AgentNova",
            model_name="expanded_benchmark",
            debug=DEBUG,
        )
    
    client = get_default_client()

    if not client.is_running():
        print(f"❌ {BACKEND_NAME} is not running.")
        if AGENTNOVA_BACKEND == "bitnet":
            print("   Start llama-server from bitnet.cpp directory")
        else:
            print("   Start it with: ollama serve")
        return

    available = get_available_models(client)
    print(f"⚛️ AgentNova Expanded Benchmark (25 tests)")
    print(f"   Backend: {BACKEND_NAME}")
    print(f"   Available: {', '.join(available)}")
    if USE_ACP:
        print(f"   ACP: enabled")
    if force_react:
        print(f"   Force ReAct: YES (all models will use text-based tool calling)")

    # Clear old results
    results = {}
    if os.path.exists(RESULTS_FILE):
        os.remove(RESULTS_FILE)

    # Models to test (dynamically discovered)
    models_to_test = get_available_models(client)
    models_to_test = models_to_test[:5] if models_to_test else []
    print(f"   Testing: {', '.join(models_to_test)}")

    for model in models_to_test:
        exact_name = next((a for a in available if model.split(':')[0] in a), model)

        print(f"\n{'='*50}")
        print(f"🧪 Testing: {exact_name}")
        print(f"{'='*50}")

        test_model(client, exact_name, results, force_react=force_react)

    # Print rankings
    print(f"\n{'='*50}")
    print("🏆 RANKINGS")
    print(f"{'='*50}")

    for model_name, model_data in results.items():
        if 'tests' in model_data:
            model_data['passed'] = sum(1 for t in model_data['tests'].values() if t.get('passed', False))
            model_data['total'] = len(TESTS)

    sorted_results = sorted(
        results.values(),
        key=lambda x: (-x.get('passed', 0), x.get('time', 9999))
    )

    for i, r in enumerate(sorted_results, 1):
        if 'tests' not in r or len(r.get('tests', {})) == 0:
            continue
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        passed = r.get('passed', 0)
        total = r.get('total', len(TESTS))
        rate = passed / total * 100 if total > 0 else 0
        print(f"{medal} {r['model']:<40} {passed}/{total} ({rate:.0f}%) - {r.get('time', 0):.1f}s")

    # Category breakdown
    categories = ['Math', 'Reason', 'Know', 'Calc', 'Code', 'Compare', 'Multi', 'Repl']
    print(f"\n{'='*50}")
    print("📊 CATEGORY BREAKDOWN")
    print(f"{'='*50}")

    for cat in categories:
        print(f"\n  {cat}:")
        cat_results = []
        for model_name, model_data in results.items():
            if 'tests' not in model_data:
                continue
            cat_tests = [t for k, t in model_data['tests'].items() if k.startswith(f"{cat}:")]
            if cat_tests:
                passed = sum(1 for t in cat_tests if t.get('passed', False))
                cat_results.append((model_name, passed, len(cat_tests)))

        cat_results.sort(key=lambda x: (-x[1], x[0]))
        for model, passed, total in cat_results:
            bar = "█" * passed + "░" * (total - passed)
            print(f"    {model:<35} {bar} {passed}/{total}")

    print(f"\n📄 Results saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    main()
