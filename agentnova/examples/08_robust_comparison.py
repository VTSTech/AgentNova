"""
examples/08_robust_comparison.py
--------------------------------
Robust model comparison that saves progress incrementally.
Starts fresh each run - clears old results.

Run: python examples/08_robust_comparison.py

With CLI:
  agentnova test 08
  agentnova test 08 --acp
  agentnova test 08 --use-mf-sys --model qwen2.5-coder:0.5b

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

import sys
import os
import time
import json
import re
import unicodedata
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentnova import Agent, get_default_client, get_tool_support, AGENTNOVA_BACKEND, StepResult
from agentnova.tools.builtins import make_builtin_registry
from agentnova.model_discovery import get_available_models
from agentnova.shared_args import add_shared_args, parse_shared_args

# Parse CLI args (with env var fallbacks)
parser = argparse.ArgumentParser(description="AgentNova Robust Comparison")
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


# System prompts for different test types
SYSTEM_PROMPT_NO_TOOLS = """You are a helpful assistant. Follow these rules:
- Answer directly and concisely
- For math questions, provide only the numerical answer
- For knowledge questions, provide one-word answers when asked
- For reasoning, think step-by-step but give the final answer clearly
- For code requests, write clean, working Python functions"""

SYSTEM_PROMPT_WITH_TOOLS = """You are a helpful assistant with access to tools.
- Use tools when they can help answer the question
- For calculator requests, pass the complete mathematical expression to the calculator tool
- After using tools, report the results clearly and concisely
- Always execute tools rather than describing how to use them"""

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


# Models discovered dynamically at runtime
# Filter for small models (indicators: 0.5b, 1b, 1.5b, 2b, 270m, 135m, 0.6b, etc.)
SMALL_MODEL_INDICATORS = ["0.5b", "270m", "135m", "350m", "0.6b", "1b", "1.5b", "2b", "tiny", "mini", "micro", "small", "moe", "bitnet"]


def get_small_models(client) -> list[str]:
    """Get list of small models, or all available if none match."""
    available = get_available_models(client)
    small_models = []
    for model in available:
        model_lower = model.lower()
        if any(ind in model_lower for ind in SMALL_MODEL_INDICATORS):
            small_models.append(model)
    
    # If no small models found by indicators, use all available
    if not small_models:
        print("   ⚠️ No small models found by indicators, using all available")
        small_models = available
    
    return small_models


MODELS = []  # Will be populated dynamically in main()

# Verbosity level: 0=minimal, 1=show failures, 2=show all responses
VERBOSITY = 2

# 15 tests: 3 per category
# Fair prompts without answer spoilers
TESTS = [
    # Math - basic arithmetic
    ('Math', 'Multiply', 'What is 7 times 8? Answer with just the number.', None, '56'),
    ('Math', 'Add', 'What is 25 plus 17? Answer with just the number.', None, '42'),
    ('Math', 'Divide', 'What is 144 divided by 12? Answer with just the number.', None, '12'),
    # Reasoning - multi-step thinking
    ('Reason', 'Apples', 'I have 10 apples. I give 3 to Bob and 2 to Alice. How many apples do I have left? Answer with just the number.', None, '5'),
    ('Reason', 'Sequence', 'What comes next in this sequence: 2, 4, 6, 8, ? Answer with just the number.', None, '10'),
    ('Reason', 'Logic', 'All cats are animals. Fluffy is a cat. What category does Fluffy belong to? Answer with one word.', None, 'animal'),
    # Knowledge - world facts
    ('Know', 'Japan', 'What is the capital of Japan? Answer with one word.', None, 'tokyo'),
    ('Know', 'France', 'What is the capital of France? Answer with one word.', None, 'paris'),
    ('Know', 'Brazil', 'What is the capital of Brazil? Answer with one word.', None, 'brasilia'),
    # Calc (with tools) - tool usage
    ('Calc', 'Multiply', 'Use the calculator tool to compute 15 times 8.', ['calculator'], '120'),
    ('Calc', 'Divide', 'Use the calculator tool to compute 100 divided by 4.', ['calculator'], '25'),
    ('Calc', 'Power', 'Use the calculator tool to compute 2 to the power of 10.', ['calculator'], '1024'),
    # Code - code generation
    ('Code', 'is_even', 'Write a Python function called is_even(n) that returns True if n is even.', None, 'def'),
    ('Code', 'reverse', 'Write a Python function called reverse_string(s) that returns the reversed string.', None, 'def'),
    ('Code', 'max_num', 'Write a Python function called find_max(numbers) that returns the largest number in a list.', None, 'def'),
]

RESULTS_FILE = os.path.join(os.path.dirname(__file__), 'robust_comparison_results.json')


def save_results(results):
    """Save results to JSON."""
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)


def test_model(client, model: str, results: dict, force_react: bool = False, main_acp=None) -> dict:
    """Test a single model, saving progress after each test with optional ACP logging."""
    
    # Create model-specific ACP instance if ACP is enabled
    model_acp = None
    if USE_ACP and main_acp is None:
        if '/' in model:
            model_short = model.split('/')[0]
        else:
            model_short = model.split(':')[0]
        model_short = model_short[:25]
        model_acp = ACPPlugin(
            agent_name="AgentNova",
            model_name=model,
            debug=DEBUG,
        )
        model_acp.bootstrap(claim_primary=False)
    elif main_acp:
        model_acp = main_acp
    
    if model not in results:
        results[model] = {
            'model': model,
            'tests': {},
            'total': len(TESTS),
            'time': 0
        }

    model_results = results[model]

    for cat, test_name, prompt, tools, expected in TESTS:
        full_name = f"{cat}:{test_name}"

        # Skip already tested
        if full_name in model_results['tests']:
            continue

        print(f"  Testing {full_name}...", end=' ', flush=True)
        
        # Log test start to ACP
        if model_acp:
            model_acp.log_user_message(f"Test: {full_name}")

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
            response_norm = normalize_text(response)
            expected_norm = normalize_text(expected)
            passed = expected_norm in response_norm
            
            # Check if tools were actually used (for Calc tests)
            tool_used = None
            if tools and "calculator" in tools:
                tool_used = check_tool_used(run, "calculator")
            
            # Check for near-misses (e.g., correct number but with extra text)
            near_miss = False
            if not passed:
                # Extract numbers from response for math/calc tests
                numbers = re.findall(r'-?\d+\.?\d*', response_norm)
                if numbers and expected_norm.replace('.', '').replace('-', '').isdigit():
                    near_miss = expected_norm in numbers
            
            model_results['tests'][full_name] = {
                'passed': passed,
                'near_miss': near_miss,
                'time': elapsed,
                'response': response,  # Full response for analysis
                'response_norm': response_norm,
                'expected': expected,
                'expected_norm': expected_norm,
                'steps': len(run.steps),  # Track step count
                'tool_used': tool_used,  # Track tool usage
            }

            model_results['time'] += elapsed
            
            # Log test result to ACP
            if model_acp:
                result_status = "PASS" if passed else ("NEAR-MISS" if near_miss else "FAIL")
                model_acp.log_assistant_message(f"[{result_status}] {full_name}")

            if passed:
                print(f"✅ ({elapsed:.1f}s)")
                if VERBOSITY >= 2:
                    print(f"    📝 Found '{expected}' in: {response[:150]}")
                if tool_used is not None:
                    print(f"    ⏱️ {len(run.steps)} steps, tool_used={tool_used}")
            elif near_miss:
                print(f"⚠️ NEAR-MISS ({elapsed:.1f}s)")
                print(f"    ⚠️ Expected '{expected}' found in numbers: {numbers}")
                print(f"    📝 RESPONSE: {response}")
                if tool_used is not None:
                    print(f"    ⏱️ {len(run.steps)} steps, tool_used={tool_used}")
            else:
                print(f"❌ ({elapsed:.1f}s)")
                if tool_used is not None and not tool_used:
                    print(f"    ⚠️ WARNING: Calculator tool was NOT called - model may have hallucinated!")
                if VERBOSITY >= 1:
                    print(f"    ❌ EXPECTED: '{expected}' (norm: '{expected_norm}')")
                    print(f"    📝 RESPONSE: {response}")
                    print(f"    📝 NORMALIZED: '{response_norm}'")
                    # Show if expected is a substring almost found
                    if expected_norm[:3] in response_norm:
                        idx = response_norm.find(expected_norm[:3])
                        print(f"    🔍 Partial match at pos {idx}: '...{response_norm[max(0,idx-5):idx+10]}...'")
                if tool_used is not None:
                    print(f"    ⏱️ {len(run.steps)} steps, tool_used={tool_used}")

        except Exception as e:
            model_results['tests'][full_name] = {
                'passed': False,
                'error': str(e)[:100]
            }
            model_results['time'] += 30  # Penalty
            if model_acp:
                model_acp.log_assistant_message(f"[ERROR] {full_name}: {str(e)[:30]}")
            print(f"❌ ERROR: {str(e)[:50]}")

        # Save after each test
        save_results(results)

    # Calculate final score
    model_results['total'] = len(TESTS)
    return model_results


def main():
    # Get force_react from config
    force_react = config.force_react
    
    # Create main ACP instance for session tracking
    main_acp = None
    if USE_ACP:
        main_acp = ACPPlugin(
            agent_name="AgentNova",
            model_name="robust-comparison",
            debug=DEBUG,
        )
        bootstrap = main_acp.bootstrap(claim_primary=False)
        acp_connected = bootstrap.get("status") is not None
    else:
        acp_connected = False
    
    client = get_default_client()

    if not client.is_running():
        print(f"❌ {BACKEND_NAME} is not running.")
        if AGENTNOVA_BACKEND == "bitnet":
            print("   Start llama-server from bitnet.cpp directory")
        else:
            print("   Start it with: ollama serve")
        return

    available = get_available_models(client)
    print(f"⚛️ AgentNova Robust Model Comparison")
    print(f"   Backend: {BACKEND_NAME}")
    print(f"   Available: {', '.join(available)}")
    if USE_ACP:
        print(f"   ACP: {'connected' if acp_connected else 'unavailable'}")
    if force_react:
        print(f"   Force ReAct: YES (all models will use text-based tool calling)")

    # Load existing results for resumability (don't delete!)
    results = {}
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, encoding='utf-8') as f:
                results = json.load(f)
            completed_models = list(results.keys())
            print(f"   📁 Loaded existing results: {len(completed_models)} models already tested")
            print(f"   Resuming from where we left off...")
        except Exception as e:
            print(f"   ⚠️ Could not load existing results: {e}")
            results = {}

    # Get small models dynamically
    models_to_test = get_small_models(client)
    
    # Fallback: if no small models found, use all available
    if not models_to_test:
        print(f"   ⚠️ No small models found by name indicators, using all available")
        models_to_test = available
    
    print(f"   Models to test: {', '.join(models_to_test)}")
    
    if acp_connected and main_acp:
        main_acp.log_chat("system", f"Benchmark started: {len(models_to_test)} models", complete=True)

    for model in models_to_test:
        print(f"\n{'='*50}")
        print(f"🧪 Testing: {model}")
        print(f"{'='*50}")

        test_model(client, model, results, force_react=force_react, main_acp=main_acp)

    # Print rankings
    print(f"\n{'='*50}")
    print("🏆 RANKINGS")
    print(f"{'='*50}")

    # Calculate passed count from tests dict
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
        
        # Count near-misses
        near_misses = sum(1 for t in r.get('tests', {}).values() if t.get('near_miss', False))
        nm_str = f" (+{near_misses}⚠️)" if near_misses else ""
        
        print(f"{medal} {r['model']:<40} {passed}/{total} ({rate:.0f}%) - {r.get('time', 0):.1f}s{nm_str}")

    # Print category breakdown
    print(f"\n{'='*50}")
    print("📊 CATEGORY BREAKDOWN")
    print(f"{'='*50}")
    
    categories = ['Math', 'Reason', 'Know', 'Calc', 'Code']
    cat_labels = {'Math': 'Math', 'Reason': 'Reasoning', 'Know': 'Knowledge', 'Calc': 'Calc', 'Code': 'Code'}
    
    for cat in categories:
        print(f"\n  {cat_labels[cat]}:")
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

    # Print near-miss summary
    total_near_misses = sum(
        sum(1 for t in r.get('tests', {}).values() if t.get('near_miss', False))
        for r in results.values()
    )
    if total_near_misses > 0:
        print(f"\n⚠️  NEAR-MISS ANALYSIS")
        print(f"   {total_near_misses} test(s) had the correct answer but with extra text")
        print(f"   These are counted as failures but may indicate partial success")

    print(f"\n📄 Results saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    main()
