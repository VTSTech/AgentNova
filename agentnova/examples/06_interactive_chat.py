"""
examples/06_interactive_chat.py
-------------------------------
Interactive chat with tool support. Good for manual testing.

Tool support levels (detected automatically):
  - "native": Model has native tool-calling (pass tools to API)
  - "react": Model accepts tools but needs text-based prompting
  - "none": Model doesn't support tools at all

Use --acp or AGENTNOVA_ACP=1 for ACP integration.
Use --use-mf-sys or AGENTNOVA_USE_MF_SYS=1 for Modelfile system prompts.
Use --tool-support to test model tool support first.

Run from the project root:   python examples/06_interactive_chat.py
Or from the examples folder: python 06_interactive_chat.py

With CLI:
  agentnova test 06
  agentnova test 06 --acp --debug

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

import sys
import os
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentnova import (
    Agent,
    get_default_client,
    get_available_models,
    get_system_prompt,
    get_tool_support,  # NEW: Tool support detection
    AGENTNOVA_BACKEND,
    StepResult,
)
from agentnova.tools.builtins import make_builtin_registry
from agentnova.model_discovery import pick_best_model, get_available_models
from agentnova.shared_args import add_shared_args, parse_shared_args

# Parse CLI args (with env var fallbacks)
parser = argparse.ArgumentParser(description="AgentNova Interactive Chat")
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

BACKEND_NAME = AGENTNOVA_BACKEND.upper()


# Model to test (discovered dynamically or set via config)
preferred = config.model
MODEL = None  # Will be set in main()
TOOLS = ["calculator", "shell", "python_repl", "read_file", "write_file"]


def make_step_printer(acp=None):
    """Create a step printer function that optionally forwards to ACP."""
    def print_step(step: StepResult):
        if step.type == "tool_call":
            args = ", ".join(f"{k}={v}" for k, v in (step.tool_args or {}).items())
            print(f"\n  \033[33m🔧 {step.tool_name}({args})\033[0m")
        elif step.type == "tool_result":
            preview = step.content[:100].replace("\n", " ")
            if len(step.content) > 100:
                preview += "..."
            print(f"  \033[34m📦 → {preview}\033[0m")
        
        # Forward to ACP if enabled
        if acp:
            acp.on_step(step)
    
    return print_step


def main():
    global MODEL
    client = get_default_client()
    
    if not client.is_running():
        print(f"❌ {BACKEND_NAME} is not running.")
        if AGENTNOVA_BACKEND == "bitnet":
            print("   Start llama-server from bitnet.cpp directory")
        else:
            print("   Start it with: ollama serve")
        return
    
    # Pick best model dynamically
    MODEL = pick_best_model(preferred=preferred, client=client)
    if not MODEL:
        models = get_available_models(client)
        MODEL = models[0] if models else None
    
    if not MODEL:
        print(f"❌ No models available in {BACKEND_NAME}.")
        return
    
    # Detect tool support level
    tool_support = get_tool_support(MODEL, client)
    
    # Initialize ACP if enabled
    acp = None
    if USE_ACP:
        acp = ACPPlugin(
            agent_name="AgentNova-InteractiveChat",
            model_name=MODEL,
            debug=DEBUG,
        )
        print(f"   ACP URL: {acp.base_url}")
        bootstrap = acp.bootstrap(claim_primary=False)
        if bootstrap.get("stop_flag"):
            print(f"   ⚠️ ACP STOP flag is set: {bootstrap.get('stop_reason')}")
        print(f"   ACP Status: {'connected' if bootstrap.get('status') else 'unavailable'}")
        print()
    
    tools = make_builtin_registry().subset(TOOLS)
    
    agent = Agent(
        model=MODEL,
        client=client,
        tools=tools,
        system_prompt=get_system_prompt(
            MODEL,
            client=client,
            default_prompt=(
                "You are a helpful assistant with access to tools. "
                "Use them when needed. Be concise but informative."
            ),
        ),
        max_steps=8,
        on_step=make_step_printer(acp),
        debug=DEBUG,
        model_options={
            "temperature": 0.3,     # Some creativity for chat
            "num_ctx": 2048,        # Larger context for conversation
            "num_predict": 512,     # Longer responses for chat
        },
    )
    
    print(f"\n{'='*60}")
    print(f"💬 AgentNova Interactive Chat")
    print(f"   Backend: {BACKEND_NAME}")
    print(f"   Model: {MODEL}")
    print(f"   Tool support: {agent._tool_support}")
    print(f"   Tools: {', '.join(TOOLS)}")
    if USE_ACP:
        print(f"   ACP: enabled")
    print(f"{'='*60}")
    print("   Commands: /reset, /tools, /quit")
    print(f"{'='*60}\n")
    
    while True:
        try:
            user_input = input("\033[1mYou:\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!")
            break
        
        if not user_input:
            continue
        
        if user_input in ("/quit", "/exit"):
            print("👋 Goodbye!")
            break
        
        if user_input == "/reset":
            agent.reset()
            print("🔄 Conversation reset.\n")
            continue
        
        if user_input == "/tools":
            print(f"🔧 Available tools: {', '.join(t.name for t in tools.all())}\n")
            continue
        
        # Log to ACP if enabled
        if acp:
            acp.log_user_message(user_input)
        
        # Run agent
        print()
        try:
            run = agent.run(user_input)
            print(f"\n\033[32m🤖 Agent:\033[0m {run.final_answer}")
            
            if acp:
                acp.log_assistant_message(run.final_answer)
            
            tool_calls = len([s for s in run.steps if s.type == "tool_call"])
            if tool_calls > 0 or run.total_ms > 5000:
                print(f"\n   \033[90m({tool_calls} tools, {run.total_ms/1000:.1f}s)\033[0m")
        except Exception as e:
            print(f"\n❌ Error: {e}")
    
    # Session summary
    if acp:
        print("\n--- Session complete ---")
        tokens = acp.get_session_tokens()
        print(f"   Session tokens: {tokens}")


if __name__ == "__main__":
    main()
