#!/usr/bin/env python3
"""
examples/14_gsm8k_benchmark.py
------------------------------
GSM8K Agent Benchmark - Using AgentNova Agent System

This benchmark uses the full Agent system with:
  • Calculator tool for accurate arithmetic
  • Chain-of-thought prompting
  • Better output parsing
  • Math-specific system prompts
  • Dynamic model discovery (no hardcoded models)
  • Optional ACP integration (use --acp flag)

With CLI:
  agentnova test 14
  agentnova test 14 --acp
  agentnova test 14 --use-mf-sys --model qwen2.5-coder:0.5b

Uses centralized config from agentnova/config.py

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

import json
import time
import sys
import os
import argparse

# Add AgentNova package to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentnova import get_default_client, get_tool_support, AGENTNOVA_BACKEND
from agentnova.core.tools import ToolRegistry
from agentnova.core.agent import Agent
from agentnova.core.math_prompts import (
    MATH_SYSTEM_PROMPT,
    MATH_SYSTEM_PROMPT_NO_TOOLS,
    MATH_SYSTEM_PROMPT_REACT,
    extract_number,
    calculator_tool,
)
from agentnova.model_discovery import get_available_models, pick_models_for_benchmark
from agentnova.shared_args import add_shared_args, parse_shared_args, SharedConfig

# Parse CLI args (with env var fallbacks)
parser = argparse.ArgumentParser(description="GSM8K Agent Benchmark")
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

# Debug mode
DEBUG = config.debug

BACKEND_NAME = AGENTNOVA_BACKEND.upper()

RESULTS_FILE = "./gsm8k_agent_results.jsonl"
LOG_FILE = "./gsm8k_agent_progress.log"

# 50 GSM8K-style questions
QUESTIONS = [
    # Basic arithmetic (1-10)
    ("What is 15 + 27?", "42"),
    ("What is 8 times 7?", "56"),
    ("What is 100 minus 37?", "63"),
    ("What is 144 divided by 12?", "12"),
    ("What is 25 times 4?", "100"),
    ("What is 17 + 18 + 19?", "54"),
    ("What is 200 - 50 - 30?", "120"),
    ("What is 6 times 9?", "54"),
    ("What is 81 divided by 9?", "9"),
    ("What is 35 + 65?", "100"),
    # Word problems basic (11-20)
    ("Janet has 8 apples. She buys 12 more. How many apples does she have now?", "20"),
    ("A book costs $15. If you pay with $20, how much change do you get?", "5"),
    ("There are 24 students in a class. If 6 are absent, how many are present?", "18"),
    ("A pizza has 8 slices. If 3 people share it equally, how many slices does each person get?", "3"),
    ("Tom has 45 marbles. He gives 18 to his friend. How many does he have left?", "27"),
    ("A train travels 60 miles per hour. How far does it travel in 2 hours?", "120"),
    ("What is 999 minus 777?", "222"),
    ("If 5 pens cost $10, how much does 1 pen cost?", "2"),
    ("What is 15% of 80?", "12"),
    ("A rectangle is 8 feet long and 5 feet wide. What is the area in square feet?", "40"),
    # Intermediate arithmetic (21-30)
    ("What is 12 times 11?", "132"),
    ("What is 3 squared plus 4 squared?", "25"),
    ("A store has 156 items. They sell 89. How many remain?", "67"),
    ("What is half of 150?", "75"),
    ("What is 7 times 8?", "56"),
    ("What is 225 divided by 15?", "15"),
    ("What is 33 + 44 + 55?", "132"),
    ("What is 1000 minus 777?", "223"),
    ("What is 9 times 8?", "72"),
    ("What is 18 divided by 3?", "6"),
    # Word problems intermediate (31-40)
    ("Mary reads 12 pages per day. How many pages in 5 days?", "60"),
    ("A box contains 48 eggs. If 12 eggs are broken, how many are good?", "36"),
    ("John earns $15 per hour. How much for 6 hours of work?", "90"),
    ("A cake has 12 slices. If 4 friends share equally, how many slices each?", "3"),
    ("What is 20% of 200?", "40"),
    ("A car travels 50 miles on 2 gallons. How many miles per gallon?", "25"),
    ("A dozen eggs costs $3. How much for 4 dozen?", "12"),
    ("What is 50 minus 17?", "33"),
    ("A garden has 15 rows with 8 plants each. How many plants total?", "120"),
    ("What is 11 times 11?", "121"),
    # Advanced (41-50)
    ("What is 16 times 5?", "80"),
    ("A shirt costs $25. If it is 20% off, how much do you save?", "5"),
    ("What is 360 divided by 6?", "60"),
    ("A pool holds 500 gallons. 125 gallons evaporate. How many remain?", "375"),
    ("What is 14 plus 28 plus 42?", "84"),
    ("A recipe needs 3 cups of flour for 12 cookies. How many cups for 24 cookies?", "6"),
    ("What is 45 minus 19?", "26"),
    ("A train has 8 cars with 15 passengers each. How many passengers total?", "120"),
    ("What is 7 times 9?", "63"),
    ("A store opens at 9am and closes at 5pm. How many hours is it open?", "8"),
]


def log(msg):
    """Write to log file and print"""
    timestamp = time.strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def create_calculator_tool():
    """Create calculator tool for the agent"""
    registry = ToolRegistry()
    
    @registry.tool(
        description="Evaluate a mathematical expression. Use this for ALL arithmetic operations.",
        param_descriptions={"expression": "Math expression to evaluate (e.g., '15 + 27', 'sqrt(144)')"}
    )
    def calculator(expression: str) -> str:
        return calculator_tool(expression)
    
    return registry


def test_model_with_agent(model: str, question: str, expected: str, client, acp=None, force_react: bool = False, model_options: dict = None) -> dict:
    """
    Test a model using the full Agent system with calculator tool.
    
    The Agent internally handles tool support detection via get_tool_support().
    - "native": Uses Ollama's native tool-calling API
    - "react": Uses text-based ReAct parsing
    - "none": No tools at all, pure reasoning
    
    Parameters
    ----------
    model : str
        Model name to test
    question : str
        Math question to ask
    expected : str
        Expected answer
    client : OllamaClient
        Client for API calls
    acp : ACPPlugin, optional
        ACP instance for logging
    force_react : bool
        If True, force all models to use ReAct mode (for testing)
    model_options : dict, optional
        Model options like num_ctx, num_predict
    """
    try:
        # Detect tool support level for prompt selection
        tool_support = get_tool_support(model, client)
        
        # Choose system prompt based on tool support level
        # The Agent will also detect tool support internally for execution logic
        if tool_support == "none":
            # No tool support - use reasoning-only prompt
            system_prompt = MATH_SYSTEM_PROMPT_NO_TOOLS
        elif force_react:
            # Force ReAct mode requested - use ReAct-specific prompt
            system_prompt = MATH_SYSTEM_PROMPT_REACT
        else:
            # Native or ReAct mode - standard math prompt
            # Agent will add ReAct suffix if needed
            system_prompt = MATH_SYSTEM_PROMPT
        
        # Build step callback for ACP if enabled
        on_step = acp.on_step if acp else None
        
        # Build model options
        opts = {"num_predict": 150}  # Default for math questions
        if model_options:
            opts.update(model_options)  # Apply CLI overrides
        
        # Create agent - it handles tool support detection internally
        # Only pass tools if model supports them
        agent_tools = create_calculator_tool() if tool_support != "none" else None
        agent = Agent(
            model=model,
            tools=agent_tools,
            system_prompt=system_prompt,
            max_steps=5,
            client=client,
            model_options=opts,
            on_step=on_step,
            force_react=force_react,  # Agent handles this appropriately
        )
        
        start = time.time()
        result = agent.run(question)
        elapsed = time.time() - start
        
        # Extract answer from agent's final response
        final_answer = result.final_answer or ""
        extracted = extract_number(final_answer)
        
        # Check correctness
        correct = False
        if extracted:
            try:
                correct = abs(float(extracted) - float(expected)) < 0.01
            except ValueError:
                correct = extracted == expected
        
        return {
            "model": model,
            "question": question,
            "expected": expected,
            "response": final_answer[:200],
            "extracted": extracted,
            "correct": correct,
            "time": round(elapsed, 1),
            "steps": len(result.steps) if hasattr(result, 'steps') else 0,
        }
        
    except Exception as e:
        return {
            "model": model,
            "question": question,
            "expected": expected,
            "error": str(e)[:100],
            "correct": False,
            "time": 0,
        }


def main():
    # Clear previous results
    open(RESULTS_FILE, "w").close()
    open(LOG_FILE, "w").close()
    
    # Get force_react from config (CLI arg or env var)
    force_react = config.force_react
    
    # Create main ACP instance if enabled
    main_acp = None
    if USE_ACP:
        main_acp = ACPPlugin(
            agent_name="AgentNova",
            model_name="gsm8k-benchmark",
            debug=DEBUG,
        )
        bootstrap = main_acp.bootstrap(claim_primary=False)
        acp_connected = bootstrap.get("status") is not None
    else:
        acp_connected = False
    
    # Shared client
    client = get_default_client()
    
    # Discover available models dynamically
    log("Discovering available models...")
    MODELS = pick_models_for_benchmark(max_models=6, prefer_small=True, client=client)
    
    # If --model specified, filter to just that model
    if config.model:
        MODELS = [m for m in MODELS if config.model in m]
        if not MODELS:
            # Try exact match
            available = get_available_models(client)
            if config.model in available:
                MODELS = [config.model]
            else:
                log(f"ERROR: Model '{config.model}' not found")
                sys.exit(1)
    
    if not MODELS:
        log(f"ERROR: No models found! Make sure {BACKEND_NAME} is running with models pulled.")
        if AGENTNOVA_BACKEND == "bitnet":
            log("Start llama-server from bitnet.cpp directory")
        else:
            log("Run: ollama pull qwen2.5-coder:0.5b-instruct-q4_k_m")
        sys.exit(1)
    
    log(f"Found {len(MODELS)} models: {MODELS}")
    
    results = []
    total_tests = len(MODELS) * len(QUESTIONS)
    completed = 0
    
    log(f"\n⚛️ GSM8K Agent Benchmark")
    log(f"   Backend: {BACKEND_NAME}")
    log(f"   Models: {len(MODELS)}")
    log(f"   Questions per model: {len(QUESTIONS)}")
    log(f"   Total tests: {total_tests}")
    if USE_ACP:
        log(f"   ACP: {'connected' if acp_connected else 'unavailable'}")
    log(f"   Using: Agent system with calculator tool")
    if force_react:
        log(f"   Force ReAct: YES (all models will use text-based tool calling)")
    log("=" * 50)
    
    if acp_connected and main_acp:
        main_acp.log_chat("system", f"GSM8K Benchmark started: {len(MODELS)} models", complete=True)
    
    overall_start = time.time()
    
    for model in MODELS:
        log(f"\nTesting: {model}")
        correct_count = 0
        model_start = time.time()
        
        # Create model-specific ACP instance if enabled
        model_acp = None
        if USE_ACP:
            model_acp = ACPPlugin(
                agent_name="AgentNova",
                model_name=model.split(':')[0][:25],
                debug=DEBUG,
            )
            model_acp.bootstrap(claim_primary=False)
        
        for i, (question, expected) in enumerate(QUESTIONS):
            result = test_model_with_agent(
                model, question, expected, client, 
                acp=model_acp, 
                force_react=force_react,
                model_options=config.model_options
            )
            results.append(result)
            completed += 1
            
            status = "✓" if result["correct"] else "✗"
            elapsed = result.get("time", 0)
            steps = result.get("steps", 0)
            extracted = result.get("extracted", "?")
            log(f"  Q{i+1:2d}: {status} ({elapsed}s, {steps} steps) - Expected: {expected}, Got: {extracted}")
            
            # Log to ACP
            if model_acp:
                result_status = "PASS" if result["correct"] else "FAIL"
                model_acp.log_assistant_message(f"Q{i+1}: [{result_status}] Expected: {expected}, Got: {extracted}")
            
            if result["correct"]:
                correct_count += 1
            
            # Brief pause between tests
            time.sleep(0.3)
        
        model_time = time.time() - model_start
        accuracy = (correct_count / len(QUESTIONS)) * 100
        log(f"  Score: {correct_count}/{len(QUESTIONS)} = {accuracy:.1f}% (Time: {model_time:.1f}s)")
        
        # Log model result to main ACP
        if main_acp:
            main_acp.add_note("context", f"{model}: {correct_count}/{len(QUESTIONS)} ({accuracy:.1f}%)", 
                        importance="high")
        
        # Save progress after each model
        with open(RESULTS_FILE, "a") as f:
            for r in results:
                f.write(json.dumps(r) + "\n")
            results = []
    
    total_time = time.time() - overall_start
    
    log("\n" + "=" * 50)
    log(f"COMPLETED: {total_tests} tests in {total_time:.1f}s")
    log(f"Results saved to: {RESULTS_FILE}")
    
    if acp_connected and main_acp:
        main_acp.log_chat("system", f"GSM8K Benchmark complete", complete=True)
    
    summarize_results(MODELS)


def summarize_results(models: list[str]):
    """Print final summary"""
    try:
        results = []
        with open(RESULTS_FILE, "r") as f:
            for line in f:
                if line.strip():
                    results.append(json.loads(line))
        
        print("\n" + "=" * 70)
        print("🏆 GSM8K AGENT BENCHMARK RESULTS")
        print("=" * 70)
        print(f"{'Model':<40} | {'Score':^7} | {'Accuracy':^8} | {'Avg Time':^8}")
        print("-" * 70)
        
        for model in models:
            model_results = [r for r in results if r["model"] == model]
            correct = sum(1 for r in model_results if r.get("correct", False))
            total = len(model_results)
            if total > 0:
                pct = (correct / total) * 100
                avg_time = sum(r.get("time", 0) for r in model_results) / total
                print(f"{model:<40} | {correct:2d}/50  | {pct:6.1f}% | {avg_time:.1f}s")
        
        print("=" * 70)
        
    except Exception as e:
        print(f"Error summarizing: {e}")


if __name__ == "__main__":
    main()
