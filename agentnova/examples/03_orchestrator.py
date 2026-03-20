"""
examples/03_orchestrator.py
----------------------------
A three-agent team with a router that dispatches tasks.
Backend-agnostic (works with Ollama or BitNet).

Use --acp or AGENTNOVA_ACP=1 for ACP integration.
Use --use-mf-sys or AGENTNOVA_USE_MF_SYS=1 for Modelfile system prompts.

Run from the project root:   python examples/03_orchestrator.py
Or from the examples folder: python 03_orchestrator.py

With CLI:
  agentnova test 03
  agentnova test 03 --acp --debug
  agentnova test 03 --use-mf-sys --model qwen2.5-coder:0.5b
"""

import sys
import os
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentnova import (
    Agent,
    Orchestrator,
    AgentCard,
    get_default_client,
    get_available_models,
    get_system_prompt,
    get_tool_support,  # Tool support detection
    DEFAULT_MODEL,
    AGENTNOVA_BACKEND,
)
from agentnova.tools.builtins import BUILTIN_REGISTRY
from agentnova.shared_args import add_shared_args, parse_shared_args

# Parse CLI args (with env var fallbacks)
parser = argparse.ArgumentParser(description="AgentNova Orchestrator")
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

# ── Verify backend is running ──────────────────────────────────────
client = get_default_client()
if not client.is_running():
    print(f"❌  {BACKEND_NAME} is not running.")
    if AGENTNOVA_BACKEND == "bitnet":
        print("   Start llama-server from bitnet.cpp directory")
    else:
        print("   Start it with: ollama serve")
    sys.exit(1)

models = get_available_models(client)
if not models:
    print(f"❌  No models available.")
    sys.exit(1)

# ── Pick models ────────────────────────────────────────────────────
def _pick(preferences):
    """Pick the best available model from a preference list."""
    for p in preferences:
        for m in models:
            if p in m.lower():
                return m
    return models[0]

# Use config.model if set, otherwise pick best
preferred = config.model

# For BitNet, just use whatever model is available
if AGENTNOVA_BACKEND == "bitnet":
    MAIN_MODEL = preferred or models[0]
    ROUTER_MODEL = models[0]
else:
    MAIN_MODEL = preferred or _pick(["qwen2.5-coder", "llama3.1:8b", "llama3.2:3b", "qwen2.5:7b", "mistral", "qwen3.5:0.8b"])
    ROUTER_MODEL = _pick(["qwen2.5-coder", "llama3.2:3b", "qwen3.5:0.8b", "qwen2.5", MAIN_MODEL])

print(f"✓  {BACKEND_NAME} is running")
print(f"   Using model: {MAIN_MODEL}  |  router: {ROUTER_MODEL}")
print(f"   Tool support: {get_tool_support(MAIN_MODEL, client)}")
if USE_ACP:
    print(f"   ACP: enabled")
if DEBUG:
    print(f"   Debug: enabled")
print()

# ── Initialize ACP if enabled ─────────────────────────────────────
acp = None
if USE_ACP:
    acp = ACPPlugin(
        agent_name="AgentNova-Orchestrator",
        model_name=MAIN_MODEL,
        debug=DEBUG,
    )
    print(f"   ACP URL: {acp.base_url}")
    bootstrap = acp.bootstrap(claim_primary=False)
    if bootstrap.get("stop_flag"):
        print(f"   ⚠️ ACP STOP flag is set: {bootstrap.get('stop_reason')}")
    print(f"   ACP Status: {'connected' if bootstrap.get('status') else 'unavailable'}")
    print()

# ── Build specialist agents ────────────────────────────────────────
# NOTE: Small models (1b/3b) work best WITHOUT tools for generative tasks.
# They tend to output JSON schemas instead of code when tool schemas are present.
# Only give tools to agents that genuinely need to compute something.

coder = Agent(
    model=MAIN_MODEL,
    client=client,
    system_prompt=get_system_prompt(
        MAIN_MODEL,
        client=client,
        default_prompt=(
            "You are an expert software engineer. "
            "When asked to write code, respond with clean, working Python code in a code block. "
            "Include type hints and a brief docstring. Do not output JSON or schemas."
        ),
    ),
    debug=DEBUG,
)

analyst = Agent(
    model=MAIN_MODEL,
    client=client,
    tools=BUILTIN_REGISTRY.subset(["calculator"]),
    system_prompt=get_system_prompt(
        MAIN_MODEL,
        client=client,
        default_prompt=(
            "You are a data analyst and mathematician. "
            "Break down problems step-by-step and show your reasoning. "
            "Use the calculator tool for arithmetic. "
            "After getting a result, state your final answer in plain text."
        ),
    ),
    debug=DEBUG,
)

writer = Agent(
    model=MAIN_MODEL,
    client=client,
    system_prompt=get_system_prompt(
        MAIN_MODEL,
        client=client,
        default_prompt=(
            "You are a skilled writer. Produce clear, well-structured prose. "
            "Adapt tone to context: professional for business, friendly for casual. "
            "Respond in plain text only."
        ),
    ),
    debug=DEBUG,
)

# ── Build the orchestrator ─────────────────────────────────────────

orch = Orchestrator(
    agents=[
        AgentCard("coder",   coder,   "Writing, debugging, and explaining code and programming tasks"),
        AgentCard("analyst", analyst, "Math, arithmetic, financial calculations, statistics, numbers"),
        AgentCard("writer",  writer,  "Writing emails, essays, summaries, and creative or professional prose"),
    ],
    router_model=ROUTER_MODEL,
    mode="router",
)

# ── Run some tasks ─────────────────────────────────────────────────

tasks = [
    "Write a Python function that implements binary search with type hints",
    "If I invest $5000 at 7% annual return compounded monthly, how much will I have after 10 years?",
    "Write a short professional email declining a meeting invitation",
]

for task in tasks:
    print(f"Task: {task}")
    if acp:
        acp.log_user_message(task)
    
    result = orch.run(task)
    
    print(f"Routed to: [{result.chosen_agent}]")
    print(f"Answer:\n{result.final_answer}")
    print(f"\nTime: {result.total_ms:.0f}ms")
    print("=" * 70 + "\n")
    
    if acp:
        acp.log_assistant_message(result.final_answer)

# ── Session summary ───────────────────────────────────────────
if acp:
    print("\n--- Session complete ---")
    tokens = acp.get_session_tokens()
    print(f"   Session tokens: {tokens}")
