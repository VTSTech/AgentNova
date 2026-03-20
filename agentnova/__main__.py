#!/usr/bin/env python3
"""
⚛️ AgentNova R00 — Command Line Interface

Entry point for: python -m agentnova [command] [options]

Commands:
  run     Run the agent on a single prompt and exit
  chat    Interactive multi-turn conversation with memory
  models  List models available in Ollama
  tools   List available built-in tools
  skills  List available Agent Skills

Examples:
  python -m agentnova run "What is the capital of France?"
  python -m agentnova chat --model llama3.1:8b --tools calculator,shell
  python -m agentnova models
  python -m agentnova tools
  python -m agentnova skills

Written by VTSTech · https://www.vts-tech.org · https://github.com/VTSTech/AgentNova
"""

from agentnova.cli import main

if __name__ == "__main__":
    main()
