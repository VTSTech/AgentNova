"""
examples/02_tool_agent.py
--------------------------
An agent with custom + built-in tools.
Demonstrates the decorator-based tool registry.
Uses dynamic model discovery.
Backend-agnostic (works with Ollama or BitNet).

Tool support levels (detected automatically):
  - "native": Model has native tool-calling (pass tools to API)
  - "react": Model accepts tools but needs text-based prompting
  - "none": Model doesn't support tools at all

Use --acp or AGENTNOVA_ACP=1 for ACP integration.
Use --use-mf-sys or AGENTNOVA_USE_MF_SYS=1 for Modelfile system prompts.
Use --tool-support to test model tool support first.

Run from the project root:   python examples/02_tool_agent.py
Or from the examples folder: python 02_tool_agent.py

With CLI:
  agentnova test 02
  agentnova test 02 --acp --debug
  agentnova test 02 --use-mf-sys --model qwen2.5-coder:0.5b
"""

import sys
import os
import re
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentnova import (
    Agent,
    ToolRegistry,
    StepResult,
    get_default_client,
    get_available_models,
    get_system_prompt,
    get_tool_support,  # NEW: Tool support detection
    DEFAULT_MODEL,
    AGENTNOVA_BACKEND,
)
from agentnova.tools.builtins import BUILTIN_REGISTRY
from agentnova.model_discovery import pick_best_model
from agentnova.shared_args import add_shared_args, parse_shared_args

# Parse CLI args (with env var fallbacks)
parser = argparse.ArgumentParser(description="AgentNova Tool Agent")
add_shared_args(parser)
args = parser.parse_args()
config = parse_shared_args(args)

# Check for flags from config
USE_ACP = config.acp
DEBUG = config.debug
FORCE_REACT = config.force_react

# Import ACP if needed
if USE_ACP:
    try:
        from agentnova import ACPPlugin
    except ImportError:
        print("⚠️ ACP requested but ACPPlugin not available")
        USE_ACP = False

BACKEND_NAME = AGENTNOVA_BACKEND.upper()

# ── 1. Verify backend and pick model ──────────────────────────────────
client = get_default_client()
if not client.is_running():
    print(f"❌  {BACKEND_NAME} is not running.")
    if AGENTNOVA_BACKEND == "bitnet":
        print("   Start llama-server from bitnet.cpp directory")
    else:
        print("   Start it with: ollama serve")
    sys.exit(1)

preferred = config.model
MODEL = pick_best_model(preferred=preferred, client=client)
if not MODEL:
    models = get_available_models(client)
    if models:
        MODEL = models[0]
    else:
        print(f"❌  No models available.")
        sys.exit(1)

print(f"✓  {BACKEND_NAME} is running")
print(f"   Using model: {MODEL}")

# Detect tool support level
tool_support = get_tool_support(MODEL, client)
print(f"   Tool support: {tool_support}")

if FORCE_REACT:
    print(f"   Force ReAct: YES (text-based tool calling)")
elif tool_support == "native":
    print(f"   Mode: Native tool calling (API)")
elif tool_support == "react":
    print(f"   Mode: ReAct text parsing")
elif tool_support == "none":
    print(f"   Mode: No tools (model doesn't support tools)")
else:
    print(f"   Mode: Unknown (will use heuristic)")

if USE_ACP:
    print(f"   ACP: enabled")
if DEBUG:
    print(f"   Debug: enabled")
print()

# ── 2. Initialize ACP if enabled ─────────────────────────────────────
acp = None
if USE_ACP:
    acp = ACPPlugin(
        agent_name="AgentNova-ToolAgent",
        model_name=MODEL,
        debug=DEBUG,
    )
    print(f"   ACP URL: {acp.base_url}")
    bootstrap = acp.bootstrap(claim_primary=False)
    if bootstrap.get("stop_flag"):
        print(f"   ⚠️ ACP STOP flag is set: {bootstrap.get('stop_reason')}")
    print(f"   ACP Status: {'connected' if bootstrap.get('status') else 'unavailable'}")
    print()

# ── 3. Define custom tools ─────────────────────────────────────────
registry = ToolRegistry()

@registry.tool(
    description="Get the current weather for a city (mock data for this example)",
    param_descriptions={
        "city": "City name",
        "unit": "Temperature unit: 'celsius' or 'fahrenheit'",
    },
)
def get_weather(city: str, unit: str = "celsius") -> str:
    """Return mock weather data."""
    mock = {
        "london":   {"temp": 12, "condition": "cloudy"},
        "new york": {"temp": 22, "condition": "sunny"},
        "tokyo":    {"temp": 28, "condition": "humid"},
    }
    data = mock.get(city.lower(), {"temp": 20, "condition": "unknown"})
    temp = data["temp"]
    if unit == "fahrenheit":
        temp = temp * 9 / 5 + 32
    return f"{city}: {temp}°{'C' if unit == 'celsius' else 'F'}, {data['condition']}"


@registry.tool(
    description="Convert currency amounts. Supports USD, EUR, GBP, JPY, CAD.",
    param_descriptions={
        "amount": "The numeric amount to convert",
        "from_currency": "Source currency code: USD, EUR, GBP, JPY, or CAD",
        "to_currency": "Target currency code: USD, EUR, GBP, JPY, or CAD",
    },
)
def convert_currency(amount, from_currency: str = "USD", to_currency: str = "EUR") -> str:
    """Approximate currency conversion."""
    rates_to_usd = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "JPY": 0.0067, "CAD": 0.74}
    
    # Fuzzy handling for amount
    if isinstance(amount, str):
        match = re.match(r'(\d+(?:\.\d+)?)\s*([A-Z]{3})?', amount.upper())
        if match:
            amount = float(match.group(1))
            if match.group(2) and from_currency == "USD":
                from_currency = match.group(2)
        else:
            try:
                amount = float(amount)
            except ValueError:
                return f"Error: Could not parse amount '{amount}'."
    
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return f"Error: Amount must be a number, got '{amount}'"
    
    fc, tc = from_currency.upper(), to_currency.upper()
    
    unknown = []
    if fc not in rates_to_usd:
        unknown.append(fc)
    if tc not in rates_to_usd:
        unknown.append(tc)
    if unknown:
        return f"Unknown currency: {', '.join(unknown)}. Supported: USD, EUR, GBP, JPY, CAD"
    
    usd = amount * rates_to_usd[fc]
    result = usd / rates_to_usd[tc]
    return f"{amount} {fc} ≈ {result:.2f} {tc}"


# ── 4. Also include the built-in calculator ─────────────────────────
for t in BUILTIN_REGISTRY.subset(["calculator"]).all():
    registry.register(t)

# ── 5. Live step hook for a nice trace ─────────────────────────────
def print_step(step: StepResult):
    icons = {"thought": "💭", "tool_call": "🔧", "tool_result": "📦", "final": "✅"}
    icon = icons.get(step.type, "•")
    if step.type == "tool_call":
        print(f"  {icon} Calling {step.tool_name}({step.tool_args})")
    elif step.type == "tool_result":
        print(f"  {icon} Result: {step.content}")
    elif step.type == "thought":
        print(f"  {icon} {step.content[:120]}")
    
    # Forward to ACP if enabled
    if acp:
        acp.on_step(step)


# ── 6. Build the agent ─────────────────────────────────────────────
# Agent automatically detects tool support level via get_tool_support()
# which checks tested_models.json first, then falls back to heuristic.
# 
# Tool support levels:
#   - "native": Pass tools to API, model handles tool calling
#   - "react":  Use text-based ReAct prompting
#   - "none":   Don't use tools at all
#
# Use FORCE_REACT=1 to force text-based mode for testing.

agent = Agent(
    model=MODEL,
    client=client,
    tools=registry,
    system_prompt=get_system_prompt(
        MODEL,
        client=client,
        default_prompt=(
            "You are a helpful assistant with access to tools. "
            "Call tools when needed. Give brief final answers after getting results."
        ),
    ),
    on_step=print_step,
    model_options={
        "temperature": 0.0,
        "num_ctx": 1024,
        "num_predict": 256,
    },
    force_react=FORCE_REACT,  # Only force if explicitly requested
    debug=DEBUG,
)

print(f"=== Multi-tool agent demo ({agent.model}) ===")
print(f"   Agent tool support: {agent._tool_support}")
print(f"   Native tools mode: {agent._native_tools}")
print()

queries = [
    "Convert 500 JPY to EUR",
    "What is 17 to the power of 4?",
]

for q in queries:
    agent.reset()
    print(f"User: {q}")
    if acp:
        acp.log_user_message(q)
    run = agent.run(q)
    print(f"\nFinal: {run.final_answer}")
    print(f"Took {run.total_ms:.0f}ms | {len(run.steps)} steps\n")
    if acp:
        acp.log_assistant_message(run.final_answer)
    print("-" * 60 + "\n")

# ── 7. Session summary ───────────────────────────────────────────
if acp:
    print("\n--- Session complete ---")
    tokens = acp.get_session_tokens()
    print(f"   Session tokens: {tokens}")
