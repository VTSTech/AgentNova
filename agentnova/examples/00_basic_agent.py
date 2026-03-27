#!/usr/bin/env python3
"""
examples/00_basic_agent.py
--------------------------
The simplest possible AgentNova agent — no tools, just conversation.

Usage:
  python examples/00_basic_agent.py
  python examples/00_basic_agent.py --model qwen3:0.6b
  agentnova test 00

Written by VTSTech — https://www.vts-tech.org
"""

import sys
import os
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentnova import Agent, get_config
from agentnova.backends import get_default_backend


def parse_args():
    parser = argparse.ArgumentParser(description="AgentNova Basic Agent")
    parser.add_argument("-m", "--model", default=None, help="Model to use")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--backend", choices=["ollama", "bitnet"], default=None)
    parser.add_argument("--api", choices=["resp", "comp"], default="resp", dest="api_mode",
                       help="API mode: 'resp' (OpenResponses/native) or 'comp' (Chat-Completions)")
    return parser.parse_args()


def main():
    args = parse_args()
    config = get_config()
    
    # Get backend (respects AGENTNOVA_BACKEND env var)
    backend_name = args.backend or config.backend
    api_mode = getattr(args, 'api_mode', 'resp')
    backend = get_default_backend(backend_name, api_mode=api_mode)
    
    # Check if backend is running
    if not backend.is_running():
        print(f"❌ Backend not running at {backend.base_url}")
        if config.backend == "ollama":
            print("   Start with: ollama serve")
            print("   Or set OLLAMA_BASE_URL to your remote server")
        return 1
    
    print(f"✓ Backend running at {backend.base_url}")
    
    # Create a simple agent without tools
    agent = Agent(
        model=args.model or config.default_model,
        backend=backend,
        debug=args.debug or config.debug,
    )
    
    print(f"\n⚛️ AgentNova Basic Agent")
    print(f"   Model: {args.model or config.default_model}")
    print(f"   Backend: {backend_name}")
    if api_mode != 'resp':
        print(f"   API Mode: {api_mode}")
    print("-" * 40)
    
    # Single question
    prompt = "What is the capital of France? Answer in one sentence."
    print(f"\nQ: {prompt}")
    
    result = agent.run(prompt)
    print(f"A: {result.final_answer}")
    
    # Multi-turn conversation (memory is retained)
    print("\n--- Multi-turn conversation ---")
    
    agent.run("My name is Alex.")
    result = agent.run("What's my name?")
    print(f"Agent remembers: {result.final_answer}")
    
    print(f"\n⏱️ Total time: {result.total_ms:.0f}ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())