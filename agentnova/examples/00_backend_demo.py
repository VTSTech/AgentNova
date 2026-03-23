#!/usr/bin/env python3
"""
⚛️ AgentNova R02 — Backend-Agnostic Example

This example works with EITHER Ollama OR BitNet backend.
Set AGENTNOVA_BACKEND environment variable to switch:

    # Use Ollama (default)
    export AGENTNOVA_BACKEND=ollama
    python 00_backend_demo.py

    # Use BitNet
    export AGENTNOVA_BACKEND=bitnet
    export BITNET_BASE_URL=http://localhost:8765
    python 00_backend_demo.py

Use --acp or AGENTNOVA_ACP=1 for ACP integration.
Use --use-mf-sys or AGENTNOVA_USE_MF_SYS=1 for Modelfile system prompts.

Written by VTSTech — https://www.vts-tech.org
"""

import sys
import os
import argparse

# Add AgentNova package to path (parent directory)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentnova import (
    Agent,
    get_default_client,
    get_available_models,
    get_system_prompt,
    get_tool_support,  # Tool support detection
    DEFAULT_MODEL,
    AGENTNOVA_BACKEND,
    OLLAMA_BASE_URL,
    BITNET_BASE_URL,
    StepResult,
)
from agentnova.tools.builtins import make_builtin_registry
from agentnova.shared_args import add_shared_args, parse_shared_args

# Parse CLI args (with env var fallbacks)
parser = argparse.ArgumentParser(description="AgentNova Backend Demo")
add_shared_args(parser)
args = parser.parse_args()
config = parse_shared_args(args)

# Check for flags from config
USE_ACP = config.acp
DEBUG = config.debug
USE_MF_SYS = config.use_modelfile_system

# Import ACP if needed
if USE_ACP:
    try:
        from agentnova import ACPPlugin
    except ImportError:
        print("⚠️ ACP requested but ACPPlugin not available")
        USE_ACP = False


def make_step_printer(acp=None):
    """Create a step printer function that optionally forwards to ACP."""
    def print_step(step: StepResult):
        if step.type == "tool_call":
            args = ", ".join(f"{k}={v}" for k, v in (step.tool_args or {}).items())
            print(f"    🔧 {step.tool_name}({args})")
        elif step.type == "tool_result":
            preview = step.content[:80] + "..." if len(step.content) > 80 else step.content
            print(f"    📦 → {preview}")
        
        # Forward to ACP if enabled
        if acp:
            acp.on_step(step)
    
    return print_step


def main():
    print(f"""
╔═══════════════════════════════════════════════════════════════════╗
║     ⚛️ AgentNova R02 — Backend-Agnostic Demo                      ║
╠═══════════════════════════════════════════════════════════════════╣""")
    
    # Show current configuration
    print(f"║  Backend: {AGENTNOVA_BACKEND:<53} ║")
    print(f"║  Default Model: {DEFAULT_MODEL:<49} ║")
    
    if AGENTNOVA_BACKEND == "bitnet":
        print(f"║  BitNet URL: {BITNET_BASE_URL:<51} ║")
    else:
        print(f"║  Ollama URL: {OLLAMA_BASE_URL:<51} ║")
    
    if USE_ACP:
        print(f"║  ACP: {'enabled':<55} ║")
    if DEBUG:
        print(f"║  Debug: {'enabled':<54} ║")
    
    print(f"╚═══════════════════════════════════════════════════════════════════╝")
    
    # Get client for configured backend
    print("\n📡 Connecting to backend...")
    client = get_default_client()
    
    if not client.is_running():
        print(f"❌ {AGENTNOVA_BACKEND.upper()} is not running!")
        if AGENTNOVA_BACKEND == "bitnet":
            print("   Start llama-server from bitnet.cpp directory")
        else:
            print("   Run: ollama serve")
        sys.exit(1)
    
    print(f"✅ Connected to {AGENTNOVA_BACKEND.upper()}")
    
    # List available models
    print("\n📋 Available models:")
    models = get_available_models(client)
    if models:
        for m in models:
            marker = " ← default" if m == DEFAULT_MODEL or DEFAULT_MODEL in m else ""
            print(f"   • {m}{marker}")
    else:
        print("   (no models found)")
        sys.exit(1)
    
    # Determine which model to use
    model = config.model or DEFAULT_MODEL
    if model not in models:
        # Try partial match
        for m in models:
            if model.split(":")[0] in m or m.split(":")[0] in model:
                model = m
                break
        else:
            # Use first available
            model = models[0]
    
    print(f"\n🤖 Using model: {model}")
    
    # Detect tool support level
    tool_support = get_tool_support(model, client)
    print(f"   Tool support: {tool_support}")
    
    # Initialize ACP if enabled
    acp = None
    if USE_ACP:
        acp = ACPPlugin(
            agent_name="AgentNova-BackendDemo",
            model_name=model,
            debug=DEBUG,
        )
        print(f"   ACP URL: {acp.base_url}")
        bootstrap = acp.bootstrap(claim_primary=False)
        if bootstrap.get("stop_flag"):
            print(f"   ⚠️ ACP STOP flag is set: {bootstrap.get('stop_reason')}")
        print(f"   ACP Status: {'connected' if bootstrap.get('status') else 'unavailable'}")
    
    # Create agent with tools
    # Note: Models with 'none' tool support won't use tools
    # Models with 'react' support will use text-based tool calling
    # Models with 'native' support will use API tool calling
    tools = make_builtin_registry().subset(["calculator"]) if tool_support != "none" else None
    
    agent = Agent(
        model=model,
        tools=tools,
        system_prompt=get_system_prompt(
            model,
            client=client,
            default_prompt="You are a helpful math assistant. Use the calculator tool for arithmetic.",
        ),
        client=client,
        on_step=make_step_printer(acp),
        debug=DEBUG,
    )
    
    print("\n" + "=" * 60)
    print("🧪 Test: Calculate 15 * 8")
    print("=" * 60)
    
    prompt = "What is 15 times 8?"
    if acp:
        acp.log_user_message(prompt)
    
    result = agent.run(prompt)
    print(f"\n📝 Answer: {result.final_answer}")
    
    if acp:
        acp.log_assistant_message(result.final_answer)
    
    if result.steps:
        print("\n📊 Steps:")
        for step in result.steps:
            print(f"   {step}")
    
    # Session summary
    if acp:
        print("\n--- Session complete ---")
        tokens = acp.get_session_tokens()
        print(f"   Session tokens: {tokens}")
    
    print("\n" + "=" * 60)
    print("✅ Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
