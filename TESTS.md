# ⚛️ AgentNova R03.3

## Test 01 Quick Diagnostic (5 Questions)

> **Updated:** 2026-03-27 - R03.3 OpenResponses/ChatCompletions compliance fixes, native tool calling + ReAct fallback

Test 01 is designed for rapid iteration and debugging. 5 targeted questions identify common failure modes quickly.

**Usage:**
```bash
agentnova test 01 --model qwen2.5:0.5b
agentnova test 01 --model qwen    # Fuzzy match: all qwen models
agentnova test 01 --model g       # Fuzzy match: gemma, granite, functiongemma
agentnova test 01 -m gemma3:270m --force-react --soul nova-helper  # With soul persona
agentnova test 01 -m granite4:350m --api comp  # Chat Completions API
agentnova test 01 -m qwen:0.5b --num-ctx 8192  # Custom context window
```

---

### 🎉 R03.3 Compliance Fixes (2026-03-27)

**Critical fixes for OpenResponses and ChatCompletions compliance:**

| Issue | Before | After |
|-------|--------|-------|
| Tools not passed to backend | `tools=None` always | ✅ `tools=tool_list` for native calling |
| Arguments not JSON string | `{"expression": "..."}` object | ✅ `'{"expression": "..."}'` string |
| Models without tool support | ❌ HTTP 400 error | ✅ Automatic ReAct fallback |

**Impact:**
- `granite4:350m`: Error → **100% (5/5)** with native tools
- `gemma3:270m`: Error → **40% (2/5)** with ReAct fallback
- `functiongemma:270m`: Error → **40% (2/5)** with ReAct fallback

---

### Chat Completions Mode Results (R03.3 - comp API Mode)

> Testing with `--api comp` uses OpenAI-compatible Chat Completions API (`/v1/chat/completions`)

#### After Compliance Fixes (2026-03-27)

| Rank | Model | Score | Time | Tool Mode | Q1 | Q2 | Q3 | Q4 | Q5 | Notes |
|:----:|-------|------:|-----:|:---------:|:--:|:--:|:--:|:--:|:--:|-------|
| 🥇 | **`granite4:350m`** | **5/5 (100%)** | 139.8s | **native** | ✅ | ✅ | ✅ | ✅ | ✅ | 🏆 Native tool calling! |
| 🥈 | `qwen2.5:0.5b` | 4/5 (80%) | 103.0s | ReAct | ✅ | ❌ | ✅ | ✅* | ✅ | *Skipped tool, lucky guess |
| 🥉 | `gemma3:270m` | 2/5 (40%) | 380.0s | fallback | ✅ | ❌ 3 | ✅ | ❌ empty | ❌ 120 | ReAct fallback working |
| 4 | `functiongemma:270m` | 2/5 (40%) | 213.2s | fallback | ✅ | ✅ | ❌ echo | ❌ 20 | ❌ refused | ReAct fallback working |
| 5 | `dolphin3.0-qwen2.5:0.5b` | 2/5 (40%) | 105.7s | ReAct | ✅ | ❌ 4 | ✅ | ❌ 12 | ❌ 10 | Reasoning errors |

#### Before Compliance Fixes (Historical)

| Rank | Model | Score | Time | Status |
|:----:|-------|------:|-----:|--------|
| 1 | `granite4:350m` | 4/5 (80%) | 82.1s | ❌ JSON unmarshal error on Q2+ |
| 2 | `qwen2.5:0.5b` | 3/5 (60%) | 70.2s | ReAct only, no native tools |
| 3 | `gemma3:270m` | 0/5 (0%) | - | ❌ "does not support tools" error |
| 4 | `functiongemma:270m` | 0/5 (0%) | - | ❌ "does not support tools" error |

---

### OpenResponses Mode Results (R03.3 - resp API Mode)

> Testing with `--api resp` (default) uses Ollama's native OpenResponses API (`/api/chat`)

| Rank | Model | Score | Time | Tool Support | Soul | Notes |
|:----:|-------|------:|-----:|:------------:|:----:|-------|
| 🥇 | **`functiongemma:270m`** | **5/5 (100%)** | 23.7s | native | - | 🏆 Fastest perfect score! |
| 🥈 | **`granite4:350m`** | **5/5 (100%)** | 44.5s | native | - | 🏆 Perfect with native tools |
| 🥉 | **`qwen2.5-coder:0.5b-instruct-q4_k_m`** | **5/5 (100%)** | 52.2s | react | nova-helper | 🏆 **2x faster** with soul! |
| 4 | **`qwen2.5:0.5b`** | **5/5 (100%)** | 48.7s | native | - | 🏆 Perfect with native tools |
| 5 | **`qwen2:0.5b`** | **5/5 (100%)** | 53.8s | none | nova-helper | 🏆 Fallback synthesis fix! |
| 6 | **`dolphin3.0-qwen2.5:0.5b`** | **5/5 (100%)** | 38.2s | none | nova-helper | 🏆 **+40%** with soul! |
| 7 | **`qwen:0.5b`** | **5/5 (100%)** | 96.0s | react | nova-helper | 🏆 **2.3x faster** with soul! |
| 8 | **`qwen3:0.6b`** | **5/5 (100%)** | 102.3s | react | nova-helper | 🏆 Qwen3 family! |
| 9 | **`gemma3:270m`** | **5/5 (100%)** | 106.5s | react | nova-helper | 🏆 Soul + synthesis fix! |
| 10 | **`qwen3.5:0.8b`** | **5/5 (100%)** | 331.8s | react | nova-helper | 🏆 Qwen3.5 family! |

---

### API Mode Comparison (R03.3 - resp vs comp)

> Comparing OpenResponses (resp) vs ChatCompletions (comp) API modes

| Model | resp (OpenResponses) | comp (ChatCompletions) | Δ Score | Notes |
|-------|---------------------|------------------------|:-------:|-------|
| **`granite4:350m`** | **5/5 (100%)** 82.3s | **5/5 (100%)** 139.8s | = | ✅ Native tools work in both! |
| **`qwen2.5:0.5b`** | **5/5 (100%)** 98.5s | 4/5 (80%) 103.0s | -20% | ReAct parsing differences |
| `gemma3:270m` | **5/5 (100%)** w/soul | 2/5 (40%) 380.0s | -60% | Soul + fallback help in resp |
| `functiongemma:270m` | **5/5 (100%)** | 2/5 (40%) 213.2s | -60% | Native vs fallback mode |

**Key Insight:** Native tool calling now works in both API modes after compliance fixes. OpenResponses (resp) mode has additional fallback synthesis that helps small models.

---

### Tool Mode Comparison (R03.3)

| Tool Mode | Best Score | Best Model | Description |
|-----------|:----------:|------------|-------------|
| **Native** | **100%** | granite4:350m, functiongemma:270m | Model uses API tool_calls directly |
| **ReAct** | **80%** | qwen2.5:0.5b | Parser extracts Action/Action Input from text |
| **Fallback** | **40%** | gemma3:270m, functiongemma:270m | Auto-fallback when model rejects tools |

---

### Test Questions (5 Targeted Tests)

| Q# | Test | Purpose | Expected |
|----|------|---------|----------|
| Q1 | Simple Math | Basic calculator tool usage | 42 |
| Q2 | Multi-step | Observation handling (8×7 then -5) | 51 |
| Q3 | Division | Fraction/precision handling | 4.25 |
| Q4 | Word Problem | Natural language → expression | 10 |
| Q5 | Time Calc | Store hours calculation | 8 |

---

### Key Findings (R03.3)

1. **Native tool calling fixed!** - `granite4:350m` now achieves 100% in comp mode
2. **ReAct fallback working** - Models without native support no longer error out
3. **JSON string arguments** - Fixed "cannot unmarshal object" errors
4. **OpenResponses compliant** - Full spec compliance for tool calling
5. **ChatCompletions compliant** - Full OpenAI API compatibility
6. **10 models achieve 100% in resp mode** - functiongemma, granite4, qwen family, gemma3+soul
7. **Native > ReAct > Fallback** - Native tool calling outperforms text parsing

---

### R03.3 Bug Fixes Summary

| Issue | Before | After |
|-------|--------|-------|
| `--num-ctx` ignored in test command | ❌ Reset to default 4096 | ✅ Properly applies from CLI |
| Config cached before env vars set | ❌ Old config used | ✅ Config reloads after env var set |
| Agent ignored config num_ctx | ❌ Hardcoded 4096 | ✅ Reads from config when not specified |
| Soul mode accepting wrong answers | ❌ Accepted model's guess | ✅ Tries synthesis first |
| Tool support source not visible | ❌ Just showed "none" | ✅ Shows "none (source: cache/detected)" |
| Fallback synthesis only for REACT | ❌ Skipped for NONE mode | ✅ Works for all modes |
| Wrong Final Answer accepted | ❌ Model guess used | ✅ Calculator result overrides |
| **Tools not passed to backend** | ❌ `tools=None` always | ✅ Passed for native calling |
| **Arguments not JSON string** | ❌ Object format | ✅ JSON string format |
| **Models without tool support** | ❌ HTTP 400 error | ✅ Automatic ReAct fallback |

---

### Soul Persona Impact Analysis

> **R03.3:** Soul personas dramatically improve small model performance

| Model | Params | Without Soul | With nova-helper | Improvement |
|-------|-------:|--------------|------------------|:-----------:|
| `qwen2:0.5b` | 500M | ~2/5 (40%) | **5/5 (100%)** | **+60%** ✅ |
| `qwen:0.5b` | 500M | 5/5 (221.7s) | **5/5 (96.0s)** | **2.3x faster** ⚡ |
| `qwen2.5-coder:0.5b` | 494M | 5/5 (93.3s) | **5/5 (52.2s)** | **1.8x faster** ⚡ |
| `qwen3:0.6b` | 600M | ~3/5 (60%) | **5/5 (100%)** | **+40%** ✅ |
| `gemma3:270m` | 270M | 4/5 (80%) | **5/5 (100%)** | **+20%** ✅ |
| `dolphin3.0-qwen2.5:0.5b` | 500M | 3/5 (60%) | **5/5 (100%)** | **+40%** ✅ |
| `qwen3.5:0.8b` | 800M | ~3/5 (60%) | **5/5 (100%)** | **+40%** ✅ |

---

## Test 16 Agent Mode Test (Autonomous Tasks)

> **Updated:** 2026-03-23 - New test suite for autonomous task execution

Test 16 evaluates autonomous task execution capabilities: multi-step planning, tool orchestration, and file operations.

**Usage:**
```bash
agentnova test 16 --model qwen2.5-coder:0.5b
agentnova test 16 --model all --debug
```

### Test 16 Results (R02.5)

| Model | Score | Time | Tool Support | Notes |
|-------|------:|-----:|:------------:|-------|
| `qwen2.5-coder:0.5b` | 5/7 (71%) | 324.1s | react | Multi-tool planning issue |

### Test Categories (7 Tests)

| Test | Purpose | Expected | qwen2.5-coder |
|------|---------|----------|:-------------:|
| **Simple Reasoning** | Pure logic (5-2-1=?) | 2 | ❌ Got 4 |
| **Knowledge Recall** | Fact retrieval | Paris | ✅ |
| **Calculator Chain** | Multi-step math (15×8+42) | 162 | ✅ |
| **File Write** | Create file with content | File created | ✅ |
| **Shell Echo** | Execute shell command | Message echoed | ✅ |
| **Python REPL** | Calculate 2^20 | 1048576 | ✅ |
| **Multi-Tool** | Calculate then write file | File with 100 | ❌ Didn't write |

---

## Test 07 Benchmark Results (15-Test Suite with Debug)

> **Updated:** 2026-03-23 - R02.5 module refactoring verified, updated prompts

Test 07 uses the 15-test benchmark with debug output showing tool support detection, ReAct parsing, and family-specific configuration.

### All Models Combined (R02.5 - Latest)

| Rank | Model | Params | Score | Time | Tool Support | Δ vs R02.2 |
|:----:|-------|-------:|------:|-----:|:-----------:|:--------:|
| 🥇 | **`qwen:0.5b`** | 500M | **14/15 (93%)** | 45.7s | none | **+20%** ✅ |
| 🥈 | **`dolphin3.0-qwen2.5:0.5b`** | 500M | **14/15 (93%)** | 53.0s | none | **+20%** ✅ |
| 🥉 | **`granite3.1-moe:1b`** | 1B MoE | **14/15 (93%)** | 128.6s | react | = |
| 4 | `llama3.2:1b` | 1.2B | 13/15 (87%) | 174.5s | native | = |
| 5 | `qwen2.5:0.5b` | 500M | 11/15 (73%) | 85.7s | native | = |
| 6 | `dolphin3.0-llama3:1b` | 1B | 10/15 (67%) | 70.1s | none | N/A |
| 7 | `granite4:350m` | 350M | 10/15 (67%) | 70.2s | native | -13% |
| 7 | `tinydolphin:1.1b` | 1.1B | 10/15 (67%) | 137.2s | none | +7% |
| 7 | `qwen3:0.6b` | 600M | 10/15 (67%) | 196.1s | react | = |
| 10 | `gemma3:270m` | 270M | 9/15 (60%) | 33.9s | none | = |
| 10 | `qwen2.5-coder:0.5b` | 494M | 9/15 (60%) | 132.2s | react | = |
| 12 | `tinyllama:1.1b` | 1.1B | 8/15 (53%) | 134.9s | none | = |
| 13 | `functiongemma:270m` | 270M | 4/15 (27%) | 52.6s | native | -53% |

---

## Recommendations

| Use Case | Recommended Model | Why |
|----------|-------------------|-----|
| **🏆 BEST OVERALL** | **`granite4:350m`** | **100% in both API modes** - native tools, 350M params! |
| **Best Native Tools** | **`functiongemma:270m`** | **100% in 23.7s** - fastest perfect, native tools! |
| **Best with Soul** | **`qwen2.5-coder:0.5b-instruct-q4_k_m`** + nova-helper | **100% in 52.2s** - 2x faster with soul! |
| **Best Qwen3** | **`qwen3:0.6b`** + nova-helper | **100% in 102.3s** - newest Qwen family! |
| **Best ChatCompletions** | **`granite4:350m`** + `--api comp` | **100% in 139.8s** - native tools work! |
| **Smallest 100%** | `gemma3:270m` + nova-helper | **100%** - 270M params with soul! |
| **Large context** | `llama3.2:1b` | **128k context window**, 87% accuracy |
| **CPU-only** | `BitNet-b1.58-2B-4T` | Efficient ternary weights |

---

## Tool Support Quick Reference

| Tool Support | Description | Prompt Strategy | Best Score |
|--------------|-------------|-----------------|:----------:|
| `native` | Ollama API tool-calling | Standard prompt + tools via API | **100%** |
| `react` | Text-based ReAct parsing | Standard prompt + ReAct suffix | **80%** |
| `fallback` | Auto-fallback when rejected | ReAct mode after error | **40%** |
| `none` | No tool support | Pure reasoning prompt | **40%** |

---

## Soul Persona System

> **R03.3:** Soul personas dramatically improve small model performance
> **R03.3:** Fallback synthesis works in soul mode - catches model errors!

The `--soul` flag loads a focused persona that guides model behavior. The included `nova-helper` soul is optimized for diagnostic testing:

**Usage:**
```bash
agentnova test 01 -m gemma3:270m --force-react --soul nova-helper
agentnova test 01 -m dolphin --soul nova-helper --soul-level 3
```

**nova-helper Soul Features:**
- Focused diagnostic role (not generic assistant)
- Explicit tool usage instructions with examples
- Concise response format (no filler)
- Calculator-first math handling

---

## Running the Examples

```bash
# Make sure Ollama is serving and you have a model pulled
ollama pull qwen2.5:0.5b

# List all available examples
agentnova test --list

# Quick test suite (recommended first run - skips long benchmarks)
agentnova test quick

# Full test suite (all examples)
agentnova test all

# Run GSM8K benchmark (50 math questions)
agentnova test 14 --timeout 6400

# Run with debug output
agentnova test 08 --debug --num-ctx 4096

# Run a specific example
agentnova test 01          # Basic agent demo
agentnova test 02          # Tool agent demo
agentnova test 04_acp      # Comprehensive test with ACP tracking
```

---

## Testing Tool Support Detection

```bash
# Test all models for native tool support
agentnova models --tool_support

# Results are saved to tested_models.json for future reference
```

Example output:
```
⚛️ AgentNova R03.3 Models
  Model                                      Family       Context    Tool Support
  ──────────────────────────────────────────────────────────────────────────────
  gemma3:270m                                gemma3       32K        ○ none
  granite4:350m                              granite      32K        ✓ native
  qwen2.5:0.5b                               qwen2        32K        ✓ native
  qwen3:0.6b                                 qwen3        32K        ReAct
  functiongemma:270m                         gemma3       32K        ✓ native
  dolphin3.0-qwen2.5:0.5b                    qwen2        32K        ○ none
```