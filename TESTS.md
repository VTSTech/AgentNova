# ⚛️ AgentNova R03.6

## Test 01 Quick Diagnostic (5 Questions)

> **Updated:** 2026-03-28 - R03.6 testing in progress

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

### OpenResponses Mode Results (R03.6-dev - resp API Mode)

> Testing with `--api resp` (default) uses Ollama's native OpenResponses API (`/api/chat`)

#### Current Testing (2026-03-28)

> Test params: `--soul nova-helper --timeout 9999 --warmup --num-predict 128 --num-ctx 4096 --temp 0.0`

| Rank | Model | Score | Time | Soul | Tool Mode | Q1 | Q2 | Q3 | Q4 | Q5 | Notes |
|:----:|-------|------:|-----:|:----:|:---------:|:--:|:--:|:--:|:--:|:--:|-------|
| 🥇 | **`granite4:350m`** | **5/5 (100%)** | 136.3s | nova-helper | **native** | ✅ | ✅ | ✅ | ✅ | ✅ | 🏆 Native tools working! |
| 🥇 | **`qwen2.5:0.5b`** | **5/5 (100%)** | 130.2s | nova-helper | **native** | ✅ | ✅ | ✅ | ✅ | ✅ | 🏆 Perfect score! Fastest! |
| 🥇 | **`deepseek-r1:1.5b`** | **5/5 (100%)** | 304.7s | nova-helper | **native** | ✅ | ✅ | ✅ | ✅ | ✅ | 🏆 Perfect score! Reasoning model |
| 🥉 | `qwen2.5-coder:0.5b` | 4/5 (80%) | 120.3s | nova-helper | native | ✅ | ✅ | ✅ | ❌ 5 | ✅ | Q4 reasoning error |
| 🥉 | `qwen3.5:0.8b` | 4/5 (80%) | 625.8s | nova-helper | native | ❌ empty | ✅ | ✅ | ✅ | ✅ | Q1 empty, very slow |
| 5 | `gemma3:270m` | 3/5 (60%) | 374.7s | nova-helper | native | ✅ | ✅ | ✅ | ❌ empty | ❌ 120 | Q4 empty, Q5 reasoning error |
| 5 | `dolphin3.0-qwen2.5:0.5b` | 3/5 (60%) | 114.3s | nova-helper | native | ✅ | ❌ 4 | ✅ | ✅ | ❌ 6 | Q2 reasoning error, Q5 wrong |
| 5 | `qwen2:0.5b` | 3/5 (60%) | 116.8s | nova-helper | native | ✅ | ✅ | ✅ | ❌ code | ❌ 30 | Writes Python instead of calculator |
| 5 | `qwen3:0.6b` | 3/5 (60%) | 231.3s | nova-helper | native | ❌ empty | ❌ 49 | ✅ | ✅ | ✅ | Q1 empty, Q2 reasoning error |
| 5 | `qwen:0.5b` | 3/5 (60%) | 176.6s | nova-helper | native | ✅ | ✅ | ❌ 42.5 | ❌ 16 | ✅ | Q3/Q4 reasoning errors |
| 11 | `functiongemma:270m` | 1/5 (20%) | 237.5s | nova-helper | native | ✅ | ❌ 51 | ❌ 1024 | ❌ refused | ❌ refused | Reasoning errors, Q5 refusal |

**Summary:**
- **3 models achieve 100%**: `granite4:350m`, `qwen2.5:0.5b`, `deepseek-r1:1.5b`
- **2 models at 80%**: `qwen2.5-coder:0.5b`, `qwen3.5:0.8b`
- **5 models at 60%**: `gemma3:270m`, `dolphin3.0-qwen2.5:0.5b`, `qwen2:0.5b`, `qwen3:0.6b`, `qwen:0.5b`
- **1 model at 20%**: `functiongemma:270m`

**deepseek-r1:1.5b Details:**
- Warmup: 16.3s
- Q1 (Simple Math): ✅ 278.9s (first inference after warmup)
- Q2-Q5: ✅ ~6-7s each (subsequent calls much faster)
- Note: Reasoning model with native tool support

**functiongemma:270m Details:**
- Warmup: 2.7s
- Q1 (Simple Math): ✅ 65.9s
- Q2 (Multi-step): ❌ Expected 51, Got: "The calculation was: 8 * 7 - 5"
- Q3 (Division): ❌ Expected 4.25, Got: "The result is 1024"
- Q4 (Word Problem): ❌ Asked for more info instead of calculating
- Q5 (Time Calc): ❌ Refused - claimed inability to assist with business operations

---

### Chat Completions Mode Results (R03.3 - comp API Mode)

> Testing with `--api comp` uses OpenAI-compatible Chat Completions API (`/v1/chat/completions`)

| Rank | Model | Score | Time | Soul | Tool Mode | Q1 | Q2 | Q3 | Q4 | Q5 | Notes |
|:----:|-------|------:|-----:|:----:|:---------:|:--:|:--:|:--:|:--:|:--:|-------|
| 🥇 | **`granite4:350m`** | **5/5 (100%)** | 139.8s | nova-helper | **native** | ✅ | ✅ | ✅ | ✅ | ✅ | 🏆 Native tool calling! |
| 🥇 | **`qwen2.5:0.5b`** | **5/5 (100%)** | 141.7s | nova-helper | native | ✅ | ✅ | ✅ | ✅ | ✅ | 🏆 Perfect score! |
| 🥉 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | 4/5 (80%) | 135.5s | nova-helper | native | ❌ 69 | ✅ | ✅ | ✅ | ✅ | Q1 hallucination |
| 4 | `qwen3:0.6b` | 3/5 (60%) | 476.9s | nova-helper | native | ❌ timeout | ❌ timeout | ✅ | ✅ | ✅ | Q1/Q2 timeouts |
| 4 | `qwen2:0.5b` | 3/5 (60%) | 127.7s | nova-helper | native | ✅ | ✅ | ✅ | ❌ code | ❌ code | Wrote Python instead |
| 6 | `gemma3:270m` | 2/5 (40%) | 380.0s | nova-helper | fallback | ✅ | ❌ 3 | ✅ | ❌ empty | ❌ 120 | ReAct fallback working |
| 6 | `functiongemma:270m` | 2/5 (40%) | 213.2s | nova-helper | fallback | ✅ | ✅ | ❌ echo | ❌ 20 | ❌ refused | ReAct fallback working |
| 6 | `dolphin3.0-qwen2.5:0.5b` | 2/5 (40%) | 105.7s | nova-helper | ReAct | ✅ | ❌ 4 | ✅ | ❌ 12 | ❌ 10 | Reasoning errors |
| 9 | `qwen:0.5b` | 1/5 (20%) | 226.3s | nova-helper | native | ❌ text | ❌ text | ❌ 35 | ❌ 0.43 | ✅ | Explanation text instead of tools |
| 10 | `qwen3.5:0.8b` | 0/5 (0%) | 295.3s | nova-helper | native | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ Memory limit - needs re-test |

---

## Historical Results

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

### 🐛 R03.4 Bug Fix: Ollama Native API Arguments Format (2026-03-27)

**Critical fix for resp mode (native `/api/chat` endpoint):**

| Issue | Before | After |
|-------|--------|-------|
| `tool_calls[].function.arguments` format | JSON **string**: `'{"expression": "..."}'` | **Object**: `{"expression": "..."}` |
| `granite4:350m` resp mode | ❌ HTTP 400 parse error | ✅ **100% (5/5)** |

**Root cause:** OpenAI ChatCompletions API expects `arguments` as a JSON string, but Ollama's native `/api/chat` expects it as an object. The code was sending OpenAI format to both endpoints.

**Fix:** Added `_convert_messages_to_ollama_format()` to parse JSON string arguments back to objects for the native endpoint.

---

### Before Compliance Fixes (Historical)

| Rank | Model | Score | Time | Soul | Status |
|:----:|-------|------:|-----:|:----:|--------|
| 1 | `granite4:350m` | 4/5 (80%) | 82.1s | nova-helper | ❌ JSON unmarshal error on Q2+ |
| 2 | `qwen2.5:0.5b` | 3/5 (60%) | 70.2s | nova-helper | ReAct only, no native tools |
| 3 | `gemma3:270m` | 0/5 (0%) | - | nova-helper | ❌ "does not support tools" error |
| 4 | `functiongemma:270m` | 0/5 (0%) | - | nova-helper | ❌ "does not support tools" error |

---

## Reference

### Tool Mode Comparison (R03.3)

| Tool Mode | Best Score | Best Model | Description |
|-----------|:----------:|------------|-------------|
| **Native** | **100%** | granite4:350m, qwen2.5:0.5b, deepseek-r1:1.5b | Model uses API tool_calls directly |
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

### Key Findings (R03.6-dev)

1. **deepseek-r1:1.5b joins the 100% club!** - Reasoning model with excellent tool usage
2. **3 models now achieve 100%** - granite4:350m, qwen2.5:0.5b, deepseek-r1:1.5b
3. **Native tool calling fully working** - All models with native support can use tools
4. **Soul persona critical** - All tests used nova-helper soul for consistency
5. **resp mode significantly outperforms comp** for qwen family (40-80% gap)
6. **functiongemma:270m struggles** - Reasoning errors and refusals

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

# Run GSM8K benchmark (50 math questions)
agentnova test 04 --timeout 6400

# Run with debug output
agentnova test 08 --debug --num-ctx 4096

# Run with nova-helper SOUL.md, 16k context, ChatCompletions API, Debug Output and 9999 timeout
agentnova test 01 --soul nova-helper --num-ctx 16384 --api comp --timeout 9999 --debug

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
⚛️ AgentNova R03.6-dev Models
  Model                                      Family       Context    Tool Support
  ──────────────────────────────────────────────────────────────────────────────
  gemma3:270m                                gemma3       32K        ○ none
  granite4:350m                              granite      32K        ✓ native
  qwen2.5:0.5b                               qwen2        32K        ✓ native
  qwen3:0.6b                                 qwen3        32K        ReAct
  functiongemma:270m                         gemma3       32K        ✓ native
  dolphin3.0-qwen2.5:0.5b                    qwen2        32K        ○ none
  deepseek-r1:1.5b                           deepseek     128K       ✓ native
```