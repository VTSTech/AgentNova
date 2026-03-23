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

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentnova import Agent, get_config
from agentnova.backends import get_default_backend


def main():
    config = get_config()
    
    # Get backend (respects AGENTNOVA_BACKEND env var)
    backend = get_default_backend()
    
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
        model=config.default_model,
        backend=backend,
        debug=config.debug,
    )
    
    print(f"\n⚛️ AgentNova Basic Agent")
    print(f"   Model: {config.default_model}")
    print(f"   Backend: {config.backend}")
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
