# AgentNova Architecture

Technical documentation for developers contributing to or extending AgentNova.

---

## Quick Context for AI Sessions

> **Last Updated:** 2026-03-21

### Current Project State

**Version:** R02 (Minimal Agentic Framework)

**Benchmark Champion:** `granite3.1-moe:1b` at **93% (14/15)** in **95.7s**

**Key Achievement:** Sub-1B models now competitive with 1B+ models. Both native and ReAct tool support modes now work correctly.

### Recent Changes (R02)

1. **Fixed ReAct Few-Shot Logic** - ReAct models now always receive few-shot examples (critical for correct Action/Action Input format)
2. **Native vs ReAct Prompting** - Clear separation: native models don't get few-shot (causes regression), ReAct models MUST get few-shot
3. **Debug Output Enhancement** - System prompt construction now shows `_use_few_shot`, `_few_shot_style` for easier debugging
4. **Tool Support Detection** - Three-tier system: `native`, `react`, `none` (auto-detected per model)

### Important Patterns

#### Debug Output Pattern (used in all test files and CLI)

```python
from agentnova import Agent, StepResult

def print_step(step: StepResult, prefix=""):
    """Print step information for debugging"""
    if step.type == "tool_call":
        args = ", ".join(f"{k}={v}" for k, v in (step.tool_args or {}).items())
        print(f"      🔧 {step.tool_name}({args})")
    elif step.type == "tool_result":
        preview = step.content[:80] + "..." if len(step.content) > 80 else step.content
        print(f"      📦 → {preview}")

def check_tool_used(run, tool_name: str) -> bool:
    """Verify that a specific tool was actually called during the run"""
    for step in run.steps:
        if step.type == "tool_call" and step.tool_name == tool_name:
            return True
    return False

def make_step_callback(debug: bool = True):
    """Create a callback for step-by-step output"""
    def callback(step: StepResult):
        if debug:
            print_step(step)
    return callback

# Usage in Agent creation:
agent = Agent(
    model=model,
    tools=registry,
    on_step=make_step_callback(DEBUG),  # Debug output for tool calls
    debug=DEBUG,
)
run = agent.run(prompt)  # Use run() to get steps, NOT chat()
```

#### Tool Support Detection

```python
from agentnova import get_tool_support

tool_support = get_tool_support(model, client)
# Returns: "native", "react", "none", or "untested"

# Native: Model supports Ollama tool-calling API
# ReAct: Model accepts tools but needs text-based prompting
# None: Model explicitly rejects tools
# Untested: Run `agentnova models --tool_support` to test
```

### Key Files to Know

| File | Purpose |
|------|---------|
| `cli.py` | CLI entry point, contains `_build_agent()`, `cmd_agent()`, `cmd_chat()` |
| `core/agent.py` | Main Agent class with `run()` and `chat()` methods |
| `core/model_family_config.py` | Family-specific configs for prompting, stop tokens, tool format |
| `agent_mode.py` | Goal-driven autonomous mode (`cmd_agent`) |
| `tools/builtins.py` | Built-in tools: calculator, shell, python_repl, file I/O |
| `examples/07_model_comparison.py` | Main benchmark script (15 tests, 5 categories) |
| `examples/14_gsm8k_benchmark.py` | GSM8K math benchmark (50 questions) |
| `tested_models.json` | Cached tool support detection results |

---

## Directory Structure

```
agentnova/
├── core/
│   ├── ollama_client.py   # Zero-dependency HTTP wrapper (stdlib urllib only)
│   ├── tools.py           # Decorator-based tool registry + JSON schema generation
│   ├── memory.py          # Sliding-window conversation memory with summarization
│   ├── agent.py           # ReAct loop — native tool-call + text-fallback modes
│   ├── orchestrator.py    # Multi-agent routing (router / pipeline / parallel)
│   └── model_family_config.py  # Family-specific prompts, stop tokens, tool format
├── skills/
│   ├── loader.py          # Agent Skills specification loader (progressive disclosure)
│   ├── skill-creator/     # OpenClaw skill-creator for generating new skills
│   ├── acp/               # ACP (Agent Control Panel) skill
│   ├── datetime/          # Datetime utilities skill
│   └── web_search/        # Web search skill
├── tools/
│   └── builtins.py        # Ready-to-use tools: calculator, shell, file I/O, HTTP, REPL
├── examples/              # Example scripts (included in pip package)
│   ├── 01_basic_agent.py           # Simple Q&A demo
│   ├── 02_tool_agent.py            # Tool calling demo
│   ├── 03_orchestrator.py          # Multi-agent routing demo
│   ├── 04_comprehensive_test.py    # Full test suite (supports BitNet)
│   ├── 07_model_comparison.py      # 15-test benchmark (MAIN BENCHMARK)
│   └── ...                         # More examples
├── cli.py                 # CLI entry point (agentnova command)
├── agent_mode.py          # Goal-driven autonomous agent mode
├── config.py              # Central configuration
├── bitnet_client.py       # R00: BitNet backend client (Microsoft 1.58-bit quantization)
├── bitnet_setup.py        # R00: BitNet setup/compilation helper
├── acp_plugin.py          # ACP integration for activity tracking and A2A messaging
├── model_discovery.py     # R00: Dynamic model discovery for both backends
├── tested_models.json     # Cached tool support detection results
└── shared_args.py         # Shared CLI argument parsing for examples
```

---

## Core Design Decisions

| Concern | Approach |
|---|---|
| **HTTP Client** | Zero external dependencies — uses Python stdlib `urllib` only |
| **Backends** | Ollama (default) or BitNet (R00) — switch via `--backend` flag |
| **Tool calling** | Native Ollama tool-call protocol when supported; automatic ReAct text-parsing fallback for other models |
| **Tool Support** | Three-tier detection: `native` (API), `react` (text), `none` (no tools) |
| **Memory** | Sliding window — older turns are archived and optionally compressed via LLM summarization |
| **Tools** | Decorator-based, auto-generates JSON schemas from Python type hints |
| **Orchestration** | Router (LLM picks agent), Pipeline (chain), or Parallel (concurrent + merge) |
| **Streaming** | First-class via generator interface |
| **Error handling** | Automatic retry with exponential backoff for transient network/server errors |
| **Security** | Path validation, command blocklist, SSRF protection (R00) |

---

## Tool Support Tiers

| Tier | Description | Models | Prompt Strategy |
|------|-------------|--------|-----------------|
| `native` | Ollama API tool-calling | llama3.2:1b, qwen2.5:0.5b, granite4:350m | Standard prompt + tools via API |
| `react` | Text-based ReAct parsing | granite3.1-moe:1b, qwen3:0.6b, qwen2.5-coder | Standard prompt + ReAct suffix |
| `none` | No tool support | gemma3:270m, dolphin models, tiny models | `MATH_SYSTEM_PROMPT_NO_TOOLS` (pure reasoning) |

Test tool support with:
```bash
agentnova models --tool_support
```

---

## Prompting Strategy by Tool Support

The Agent class constructs different system prompts based on the model's tool support level. This is critical for correct behavior.

### Few-Shot Examples Logic

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FEW-SHOT DECISION FLOW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. Check family config (model_family_config.py)                            │
│     └── prefers_few_shot: True/False                                        │
│                                                                              │
│  2. Override for ReAct models (CRITICAL!)                                   │
│     └── if tool_support == "react" AND tools exist:                         │
│             use_few_shot = True  # ALWAYS!                                  │
│                                                                              │
│  3. For native models: respect family config                                │
│     └── Adding few-shot to native models DEGRADES performance!              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why ReAct Models Need Few-Shot

ReAct models use **text-based** tool calling (not the Ollama API). They output:

```
Thought: I need to multiply 15 times 8
Action: calculator
Action Input: {"expression": "15 * 8"}
```

**Without few-shot examples**, models output malformed formats:
- ❌ `Action: Use the calculator to perform the multiplication.`
- ❌ `Action Input: {"numerator": 15, "denominator": 8}`
- ❌ `Action: calculator with {"expression": "15*8"}`

**With few-shot examples**, they learn the correct format:
- ✅ `Action: calculator`
- ✅ `Action Input: {"expression": "15 * 8"}`

### Why Native Models DON'T Need Few-Shot

Native models use Ollama's built-in tool-calling API:
1. Tools are passed via `tools` parameter in the API request
2. The model returns structured `tool_calls` in the response
3. Adding text-based few-shot examples CONFUSES them with conflicting instructions

This caused a major regression in R01→R02: `qwen2.5:0.5b` dropped from 90%→58% on GSM8K when few-shot was incorrectly added to native mode.

### System Prompt Construction

| Tool Support | Base Prompt | Tool Descriptions | Format Instructions | Few-Shot |
|--------------|-------------|-------------------|---------------------|----------|
| `native` | User-defined | ❌ (via API) | Native hints only | ❌ Never |
| `react` | User-defined | ✅ Text list | ReAct format | ✅ **Always** |
| `none` | User-defined | ❌ | ❌ | ❌ Never |

### Debug Output Interpretation

When running with `--debug`, check these values:

```python
_tool_support=react      # Tool support level
_use_few_shot=True       # CRITICAL: Must be True for react mode!
_few_shot_style=native   # Style from family config
_is_small_model=True     # Heuristic based on model name
model_family=qwen2       # Detected family
_family_issues={}        # Known issues (truncate_json, schema_dump)
System prompt length: 1782 chars  # Should be >1000 for ReAct mode
```

**Red flags:**
- `_tool_support=react` but `_use_few_shot=False` → **BUG!**
- `System prompt length < 600` for ReAct mode → Missing few-shot examples

### Family Configuration

Family configs are defined in `agentnova/core/model_family_config.py`:

```python
"qwen2": ModelFamilyConfig(
    family="qwen2",
    supports_native_tools=True,    # Can use Ollama tool API
    prefers_few_shot=False,        # Don't add few-shot for NATIVE mode
    few_shot_style="native",       # Style when few-shot IS needed
),

"granitemoe": ModelFamilyConfig(
    family="granitemoe",
    supports_native_tools=True,
    prefers_few_shot=True,         # MoE benefits from examples
    few_shot_style="react",
    has_schema_dump_issue=True,    # Known to dump tool schema as text
    truncate_json_args=True,       # May truncate JSON in ReAct format
),
```

The `prefers_few_shot` setting is for **native mode**. ReAct mode always overrides this to `True`.

---

## Orchestrator Modes

| Mode | Behaviour |
|---|---|
| `router` | A small routing LLM picks the best agent for each request |
| `pipeline` | Agents run sequentially — each receives the previous agent's output |
| `parallel` | All agents run concurrently; results are merged with attribution |

---
## Benchmark Results Summary (R02)

### Test 07 Leaderboard (15-Test Suite)

| Rank | Model | Score | Time | Notes |
|:----:|-------|------:|-----:|-------|
| 🥇 | `granite3.1-moe:1b` | **93% (14/15)** | **95.7s** | Champion! MoE architecture |
| 🥈 | `llama3.2:1b` | 87% (13/15) | 189.3s | Native tools, 128k context |
| 🥉 | `qwen3:0.6b` | 80% (12/15) | 388.9s | Best sub-1B |
| 4 | `qwen2.5:0.5b` | 73% (11/15) | 62.8s | **90% GSM8K** |
| 4 | `granite4:350m` | 73% (11/15) | 49.6s | **78% GSM8K** |
| 4 | `nchapman/dolphin3.0-qwen2.5:0.5b` | 73% (11/15) | 25.7s | Fastest 73% |

### Model Recommendations

| Use Case | Best Model | Why |
|----------|------------|-----|
| **Best Overall** | `granite3.1-moe:1b` | 93% in 95.7s |
| **Best GSM8K Math** | `qwen2.5:0.5b` | 90% - matches 1B at half size |
| **Best Speed** | `nchapman/dolphin3.0-qwen2.5:0.5b` | 25.7s, 73% accuracy |
| **Large Context** | `llama3.2:1b` | 128k context window |

---

## Common CLI Commands

```bash
# Start interactive chat
agentnova chat --model qwen2.5:0.5b --tools calculator,shell

# Start interactive chat with debug output
agentnova chat --debug --model granite3.1-moe:1b --tools calculator

# Start autonomous agent mode
agentnova agent --debug --model granite3.1-moe:1b --tools calculator,shell

# Run a single prompt
agentnova run "What is 15 * 8?" --model qwen2.5:0.5b --tools calculator

# List available models
agentnova models

# Test tool support for all models
agentnova models --tool_support

# List available tools
agentnova tools

# List available skills
agentnova skills

# Run test examples
agentnova test --list          # List all examples
agentnova test quick           # Run quick tests only
agentnova test 07              # Run 15-test benchmark
agentnova test 14              # Run GSM8K benchmark (50 questions)

# Run with BitNet backend
agentnova chat --backend bitnet

# Performance tuning
agentnova chat --fast                           # Fast preset (ctx=2048, predict=256)
agentnova chat --num-ctx 4096 --num-predict 512 # Custom limits
agentnova chat --temperature 0.1                # Lower = more deterministic
```

---

## Notes for Future Sessions

1. **Always use `agent.run()` not `agent.chat()`** when you need step information for debugging or tool verification. `chat()` returns a string, `run()` returns a Run object with steps.

2. **The `--debug` flag** enables enhanced debug output with 🔧📦 emojis for tool calls/results. Use it when diagnosing issues.

3. **Tool support is cached** in `tested_models.json`. If testing a new model, run `agentnova models --tool_support` first.

4. **Sub-1B models are now viable** - `qwen2.5:0.5b` at 90% GSM8K proves this. Don't assume 1B+ is needed for good performance.

5. **The benchmark tests are in `examples/07_model_comparison.py`** - 15 tests across 5 categories: Math, Reasoning, Knowledge, Calc (tool), Code.

6. **When modifying CLI debug output**, also update test files to match the pattern (see `examples/07_model_comparison.py` as reference).

7. **ReAct models ALWAYS need few-shot examples** - This is enforced in `agent.py`. If `_tool_support=react`, then `_use_few_shot` must be `True`. Without examples, models output malformed Action/Action Input lines. See "Prompting Strategy by Tool Support" section for details.

8. **Never add few-shot to native tool models** - This caused a major regression (90%→58% GSM8K) in R01→R02. Native models use Ollama's API for tool calling; text-based few-shot examples confuse them.
