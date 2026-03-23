# AgentNova Architecture

Technical documentation for developers contributing to or extending AgentNova.

---

## Quick Context for AI Sessions

> **Last Updated:** 2026-03-23

### Current Project State

**Version:** R02.6 (Tool-Calling Optimization)

**Test 15 Champions:** 5 models at **100% (5/5)** - functiongemma:270m, granite4:350m, qwen2.5:0.5b, qwen2.5-coder:0.5b, qwen3:0.6b

**Test 16 Agent Mode:** `qwen2.5:0.5b` and `granite4:350m` at **71% (5/7)** - native tools excel

**Key Achievement:** ALL tool-calling models now score 100% on Quick Diagnostic. Multi-step expression extraction fixed.

### Recent Changes (R02.6 - 2026-03-23)

1. **Multi-step expression extraction** - Handles `8 times 7 minus 5`, word problems, time calculations
2. **ReAct JSON parsing fix** - Clean extraction with brace matching, handles trailing text
3. **Verbose response fallback** - Uses numeric result when model gives long explanation
4. **Test 16 ACP integration** - Now respects `--acp` flag
5. **Python REPL verification** - Strips commas for number matching ("1,048,576" → "1048576")

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
| `core/models.py` | Dataclasses: `StepResult`, `AgentRun` |
| `core/types.py` | Type aliases: `StepResultType` |
| `core/prompts.py` | Few-shot prompts, tool arg aliases, platform constants |
| `core/helpers.py` | Pure utility functions (no dependencies) |
| `core/args_normal.py` | Argument normalization for small model hallucinations |
| `core/tool_parse.py` | ReAct/JSON parsing, fuzzy tool name matching |
| `core/model_family_config.py` | Family-specific configs for prompting, stop tokens, tool format |
| `agent_mode.py` | Goal-driven autonomous mode (`cmd_agent`) |
| `tools/builtins.py` | Built-in tools: calculator, shell, python_repl, file I/O |
| `examples/07_model_comparison.py` | Main benchmark script (15 tests, 5 categories) |
| `examples/14_gsm8k_benchmark.py` | GSM8K math benchmark (50 questions) |
| `examples/16_agent_mode_test.py` | Agent Mode test (7 tests, multi-tool planning) |
| `tested_models.json` | Cached tool support detection results |

---

## Directory Structure

```
agentnova/
├── core/
│   ├── ollama_client.py   # Zero-dependency HTTP wrapper (stdlib urllib only)
│   ├── tools.py           # Decorator-based tool registry + JSON schema generation
│   ├── memory.py          # Sliding-window conversation memory with summarization
│   ├── types.py           # Type aliases (StepResultType)
│   ├── models.py          # Dataclasses (StepResult, AgentRun)
│   ├── prompts.py         # Few-shot prompts, tool arg aliases, platform constants
│   ├── helpers.py         # Pure utility functions (no external dependencies)
│   ├── args_normal.py     # Argument normalization for small model hallucinations
│   ├── tool_parse.py      # ReAct/JSON parsing, fuzzy tool name matching
│   ├── agent.py           # Agent class (imports from modules above)
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

## Module Architecture (R02.5)

The `agent.py` module was refactored into focused submodules for maintainability:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          MODULE DEPENDENCIES                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  types.py        ← (no dependencies)                                    │
│  models.py       ← types                                                │
│  prompts.py      ← (no dependencies)                                    │
│  helpers.py      ← (no dependencies)                                    │
│  args_normal.py  ← prompts, helpers                                     │
│  tool_parse.py   ← helpers                                              │
│  agent.py        ← ALL above + tools, memory, ollama_client             │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

| Module | Lines | Responsibility |
|--------|-------|----------------|
| `types.py` | ~10 | Type aliases only |
| `models.py` | ~40 | Result dataclasses |
| `prompts.py` | ~180 | Constants, few-shot examples |
| `helpers.py` | ~200 | Pure functions (testable in isolation) |
| `args_normal.py` | ~240 | Argument normalization logic |
| `tool_parse.py` | ~370 | ReAct/JSON parsing, fuzzy matching |
| `agent.py` | ~1550 | Agent class orchestration |

All modules remain **zero-dependency** (stdlib only).

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
| **Allowed Paths** | `.` (cwd), `~` (home), `/tmp` (temp) - configurable via `AGENTNOVA_ALLOWED_PATHS` |
| **Module Structure** | Single-responsibility modules with clear dependency graph (R02.3) |

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

## Numeric Result Handling (R02.3)

The synthesis logic now returns numeric results directly without attempting to detect incomplete multi-step calculations.

### Why Simple Is Better

When a model computes an expression like `8 * 7 - 5 = 51`:

```
User: Calculate 8 times 7, then subtract 5 from the result.
Model: calculator(expression=8 * 7 - 5)  ← Full expression in one call
Result: 51  ← Correct!
```

From the result alone, we **cannot tell** whether:
1. The model computed `8 * 7 - 5` (complete), OR
2. The model computed `8 * 7` only (incomplete)

Previous attempts to auto-complete by detecting "then subtract X" patterns caused **double-subtraction errors** when the model had already included the operation.

### Current Behavior

```python
# Simple rule: If result is numeric, return it directly
try:
    num = float(r_clean)
    return r_clean  # Return numeric result directly
except ValueError:
    pass  # Fall through to LLM synthesis for non-numeric results
```

This is safer because:
- **Correct results pass through** unchanged
- **Wrong results** (from incomplete calculations) are still better than double-processed results
- **No hallucination risk** from LLM synthesis trying to interpret partial results

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
## Benchmark Results Summary (R02.6)

### Test 15 Quick Diagnostic (5 Questions)

| Rank | Model | Score | Time | Tool Support |
|:----:|-------|------:|-----:|:------------:|
| 🥇 | **`functiongemma:270m`** | **100% (5/5)** | **19.6s** | native |
| 🥈 | **`granite4:350m`** | **100% (5/5)** | 49.4s | native |
| 🥉 | **`qwen2.5:0.5b`** | **100% (5/5)** | 66.3s | native |
| 4 | **`qwen2.5-coder:0.5b`** | **100% (5/5)** | 116.5s | react |
| 4 | **`qwen3:0.6b`** | **100% (5/5)** | 122.8s | react |
| 6 | `gemma3:270m` | 80% (4/5) | 14.3s | none |
| 6 | `dolphin3.0-qwen2.5:0.5b` | 80% (4/5) | 26.6s | none |
| 8 | `smollm:135m` | 40% (2/5) | 16.1s | none |
| 8 | `qwen:0.5b` | 20% (1/5) | 27.0s | none |

### Test 16 Agent Mode (7 Tasks)

| Rank | Model | Score | Time | Tool Support |
|:----:|-------|------:|-----:|:------------:|
| 🥇 | **`qwen2.5:0.5b`** | **71% (5/7)** | **141.6s** | native |
| 🥈 | **`granite4:350m`** | **71% (5/7)** | 146.6s | native |
| 🥉 | `qwen2.5-coder:0.5b` | 71% (5/7) | 309.8s | react |
| 4 | `functiongemma:270m` | 43% (3/7) | 46.5s | native |
| 5 | `gemma3:270m` | 0% (0/2) | 6.0s | none |

### Model Recommendations

| Use Case | Best Model | Why |
|----------|------------|-----|
| **Best Overall** | `functiongemma:270m` | 100% in 19.6s - fastest perfect! |
| **Best Native Tools** | `qwen2.5:0.5b` | 100% Test 15, 71% Test 16 |
| **Best ReAct Mode** | `qwen2.5-coder:0.5b` | 100% Test 15, code-focused |
| **Best Speed** | `functiongemma:270m` | 19.6s, 270M params |
| **Large Context** | `llama3.2:1b` | 128k context window |

---

## Test 16 Agent Mode (Autonomous Tasks)

Test 16 evaluates autonomous task execution with multi-tool planning. Native tool models outperform ReAct models.

### Test Categories

| Test | Description | Expected | Native Models | ReAct Models |
|------|-------------|----------|---------------|--------------|
| Simple Reasoning | Pure logic puzzle | 2 | ❌ Math error | ❌ Math error |
| Knowledge Recall | Fact retrieval | Paris | ✅ | ✅ |
| Calculator Chain | Multi-step math | 162 | ✅ | ✅ |
| File Write | Create file | File created | ✅ | ✅ (with loops) |
| Shell Echo | Execute command | Message echoed | ✅ | ✅ (with loops) |
| Python REPL | Calculate 2^20 | 1048576 | ✅ | ✅ |
| Multi-Tool | Calculate then write | File with 100 | ❌ Skips write | ❌ Hallucinates |

### Key Findings (R02.6)

1. **Native tools > ReAct** - No hallucinated observations, cleaner execution
2. **Simple Reasoning fails universally** - Small models struggle with pure math (5-2-1=?)
3. **Multi-Tool planning is hard** - Models mention the second action instead of doing it
4. **ReAct loop repetition** - Models repeat same action instead of "Final Answer"
5. **qwen2.5:0.5b fastest native** - 141.6s vs 146.6s for granite4:350m

### Known Issues

| Issue | Description | Impact |
|-------|-------------|--------|
| ReAct loop | Repeats same action after success | Extra API calls, needs synthesis |
| Multi-tool planning | Stops after first tool | Multi-Tool test fails |
| Hallucinated observations | ReAct models imagine tool results | False confidence |
| Empty tool responses | Native models sometimes return empty | Needs retry/synthesis |

### Usage

```bash
# Run Agent Mode test
agentnova test 16 --model qwen2.5:0.5b

# With ACP and debug
agentnova test 16 --model all --debug --acp
```

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
agentnova test 15              # Run quick diagnostic (5 questions)
agentnova test 16              # Run Agent Mode test (7 tasks)

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

9. **Numeric results are returned directly** (R02.3) - The synthesis logic no longer tries to detect incomplete multi-step calculations. Numeric results pass through unchanged. This avoids double-processing errors when models compute full expressions in one calculator call.

10. **Module imports are stable** - `from agentnova import Agent, AgentRun, StepResult` still works. Internal modules (`types`, `models`, `prompts`, `helpers`, `args_normal`, `tool_parse`) can be imported directly for testing or extension.
