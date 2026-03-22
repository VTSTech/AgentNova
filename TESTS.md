# ⚛️ AgentNova R02.2

## Test 05 Tool Tests (Multi-Platform)

> **Updated:** 2026-03-21 - R02.2 with multi-platform shell command support.

Test 05 tests calculator, shell, and Python REPL tools. Shell commands are now platform-aware (Windows: `cd`/`dir`, Linux: `pwd`/`ls`).

---

### Test 05 Results by Platform

#### Linux (Colab)

| Model | Tool Support | Calculator | Shell | Python REPL | Total | Notes |
|-------|--------------|------------|-------|-------------|-------|-------|
| **`qwen2.5:0.5b`** | native | **5/5 (100%)** | **3/3 (100%)** | 1/3 (33%) | **9/11 (82%)** | Native JSON fallback working |
| `granite3.1-moe:1b` | react | **5/5 (100%)** | 2/3 (66%) | 1/3 (33%) | 8/11 (72%) | Wrong arg names in ReAct |
| `gemma3:270m` | none | 2/5 (40%) | 0/3 (0%) | 0/3 (0%) | 2/11 (18%) | No tool support, guesses answers |

#### Windows (Native)

| Model | Tool Support | Calculator | Shell | Python REPL | Total | Notes |
|-------|--------------|------------|-------|-------------|-------|-------|
| **`granite4:350m`** | native | **5/5 (100%)** | 2/3 (66%) | 2/3 (66%) | **9/11 (81%)** | Best small model on Windows! |
| `qwen2.5-coder:0.5b` | react | 4/5 (80%) | 2/3 (66%) | 1/3 (33%) | 7/11 (63%) | Model math error on `(10+5)*3` |

---

### Multi-Platform Shell Commands (R02)

| Platform | Directory | List Files | Date/Time |
|----------|-----------|------------|-----------|
| **Windows** | `cd` | `dir` | `python_repl` |
| **Linux/Mac** | `pwd` | `ls` | `python_repl` |

**Key Change:** Date/time queries now use `python_repl` (cross-platform) instead of shell `date` command.

---

### Key Findings (Test 05)

1. **`granite4:350m` excellent on Windows** - 81% with native tool calling
2. **Native tool models dominate** - granite4 and qwen2.5 both score 100% on Calculator
3. **Multi-platform fix working** - Windows uses `cd`/`dir`, Linux uses `pwd`/`ls`
4. **Small models struggle with Python REPL** - Need `print()` for output
5. **Model hallucination issue** - Some models ignore tool results and generate unrelated text

---

## Test 07 Benchmark Results (15-Test Suite with Debug)

> **Updated:** 2026-03-21 - R02.2 with critical ReAct fixes (few-shot forcing, observation role, think=False API)

Test 07 uses the 15-test benchmark with debug output showing tool support detection, ReAct parsing, and family-specific configuration.

---

### All Models Combined (R02.2 - Latest)

| Rank | Model | Params | Score | Time | Tool Support | Δ vs R01 |
|:----:|-------|-------:|------:|-----:|:-----------:|:--------:|
| 🥇 | **`granite3.1-moe:1b`** | 1B MoE | **14/15 (93%)** | 87.8s | react | **+13%** ✅ |
| 🥈 | **`llama3.2:1b`** | 1.2B | **13/15 (87%)** | 150.2s | native | **+20%** ✅ |
| 🥉 | `nchapman/dolphin3.0-qwen2.5:0.5b` | 500M | 11/15 (73%) | 27.2s | none | = |
| 4 | `qwen3:0.6b` | 600M | 10/15 (67%) | 189.3s | react | **Fixed** ✅ |
| 5 | `tinydolphin:1.1b` | 1.1B | 9/15 (60%) | 130.9s | none | -7% |
| 5 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | 494M | 9/15 (60%) | 133.1s | react | **+7%** ✅ |
| 7 | `tinyllama:1.1b` | 1.1B | 8/15 (53%) | 127.7s | none | -14% |

---

### R02.2 Key Findings

1. **`granite3.1-moe:1b` now at 93%** - Up from 80%, matches R01 best score!
2. **`llama3.2:1b` massive improvement** - 67% → 87% (+20%) from observation role fix
3. **`qwen3:0.6b` restored** - Was 0% (broken), now 67% with `think=False` API fix
4. **Few-shot forcing works** - ReAct models always get examples, improving Action/Action Input format
5. **Observation role fix** - Tool results now as `user` messages, models respond correctly
6. **`qwen2.5-coder:0.5b` improved** - 53% → 60% with ReAct fixes

### R02.2 Bug Fixes Applied

| Fix | Impact |
|-----|-------|
| ReAct models always get few-shot | +7-20% on ReAct models |
| Observation role → `user` | +20% on llama3.2:1b |
| ReAct loop limit enforcement | Prevents infinite loops |
| `think=False` API parameter | Restores qwen3:0.6b from 0% |
| qwen35 family config added | Correct handling for qwen3.5 |

---

### Category Champions (R02.2)

| Category | 🏆 Champion | Score | Notes |
|----------|-------------|-------|-------|
| **Math** | `granite3.1-moe:1b` | 3/3 | Perfect with ReAct |
| **Reasoning** | `granite3.1-moe:1b` / `llama3.2:1b` | 2/3 | Tie at top |
| **Knowledge** | Multiple models | 3/3 | Several perfect |
| **Calc** | `granite3.1-moe:1b` | 3/3 | ReAct working well |
| **Code** | All tested models | 3/3 | Universally easy |

---

### Sub-1B Models (R02.2 - Current)

| Rank | Model | Params | Score | Time | Tool Support | Δ vs R01 |
|:----:|-------|-------:|------:|-----:|:-----------:|:--------:|
| 🥇 | `nchapman/dolphin3.0-qwen2.5:0.5b` | 500M | 11/15 (73%) | **27.2s** | none | = |
| 🥈 | `qwen3:0.6b` | 600M | 10/15 (67%) | 189.3s | react | **Fixed** ✅ |
| 🥉 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | 494M | 9/15 (60%) | 133.1s | react | **+7%** ✅ |

#### Sub-1B Key Findings (R02.2)

1. **`dolphin3.0-qwen2.5:0.5b` leads at 73%** - Fastest sub-1B at 27.2s
2. **`qwen3:0.6b` restored** - Was 0% (broken), now 67% with `think=False` fix
3. **`qwen2.5-coder:0.5b` improved** - 53% → 60% with ReAct fixes

---

### 1B+ Models (R02.2 - Current)

| Rank | Model | Params | Score | Time | Tool Support | Δ vs R01 |
|:----:|-------|-------:|------:|-----:|:-----------:|:--------:|
| 🥇 | **`granite3.1-moe:1b`** | 1B MoE | **14/15 (93%)** | 87.8s | react | **+13%** ✅ |
| 🥈 | **`llama3.2:1b`** | 1.2B | **13/15 (87%)** | 150.2s | native | **+20%** ✅ |
| 🥉 | `tinydolphin:1.1b` | 1.1B | 9/15 (60%) | 130.9s | none | -7% |
| 4 | `tinyllama:1.1b` | 1.1B | 8/15 (53%) | 127.7s | none | -14% |

#### 1B+ Key Findings (R02.2)

1. **`granite3.1-moe:1b` dominates at 93%** - Up from 80%, best 1B model ever!
2. **`llama3.2:1b` massive improvement** - 67% → 87% from observation role fix
3. **MoE architecture shines** - granite3.1-moe fastest champion at 87.8s

---

### Tool Support Impact (R02.2)

| Model | Tool Support | Score | Notes |
|-------|--------------|-------|-------|
| `granite3.1-moe:1b` | react | **93%** | 🏆 ReAct works great with fixes |
| `llama3.2:1b` | native | **87%** | Massive +20% from observation fix |
| `dolphin3.0-qwen2.5:0.5b` | none | 73% | Pure reasoning, fastest |
| `qwen3:0.6b` | react | 67% | Restored with `think=False` |
| `qwen2.5-coder:0.5b` | react | 60% | +7% from ReAct fixes |

**Key Insight**: R02.2 fixes dramatically improved ReAct models. `granite3.1-moe:1b` went from 80% to 93%!

---

### Model Family Detection (R02 New Feature)

| Model | Family Detected | Family Issues | Tool Format |
|-------|-----------------|---------------|-------------|
| `qwen3:0.6b` | qwen3 | - | `<tool_call\>` |
| `granite3.1-moe:1b` | granitemoe | schema_dump, truncate_json | `<|tool_call|>` |
| `granite4:350m` | granite | - | `<tool_call\>` |
| `qwen2.5:0.5b` | qwen2 | - | `<tool_call\>` |
| `qwen2.5-coder:0.5b` | qwen2 | - | `<tool_call\>` |
| `gemma3:270m` | gemma3 | - | No wrapper |
| `llama3.2:1b` | llama | - | Raw JSON |
| `dolphin3.0-*` | qwen2/llama | - | Varies |

---

## Test 15 Quick Diagnostic (5 Questions)

> **Updated:** 2026-03-22 - Rapid diagnostic for debugging (~30-60s per model)

Test 15 is designed for rapid iteration and debugging. 5 targeted questions identify common failure modes quickly.

**Usage:**
```bash
agentnova test 15 --model granite3.1-moe:1b
agentnova test 15 --model all --debug
```

### Quick Diagnostic Results (R02.2)

| Rank | Model | Score | Time | Tool Support | Notes |
|:----:|-------|------:|-----:|:------------:|-------|
| 🥇 | **`qwen3.5:0.8b`** | **5/5 (100%)** | 569.3s | native | 🏆 Perfect! Native tools work great |
| 🥇 | **`qwen2.5:0.5b`** | **5/5 (100%)** | 76.5s | react | 🏆 Perfect! ReAct mode works great |
| 🥇 | **`qwen2.5-coder:0.5b`** | **5/5 (100%)** | 69.7s | react | 🏆 Perfect! ReAct mode works great |
| 4 | `functiongemma:270m` | 4/5 (80%) | 27.4s | native | Word problem misinterpretation |
| 4 | `granite4:350m` | 4/5 (80%) | 88.2s | native | Synthesis returned raw JSON |
| 4 | `granite3.1-moe:1b` | 4/5 (80%) | 96.5s | react | Multi-step stopped after first op |
| 7 | `llama3.2:1b` | 3/5 (60%) | 256.9s | native | Malformed JSON tool calls |
| 7 | `qwen3:0.6b` | 3/5 (60%) | 119.6s | react | Multi-step extraction issue |
| 7 | `dolphin3.0-qwen2.5:0.5b` | 3/5 (60%) | 41.9s | none | Pure reasoning, division error |
| 7 | `dolphin3.0-llama3:1b` | 3/5 (60%) | 40.5s | none | Pure reasoning, edge case failed |
| 11 | `gemma3:270m` | 2/5 (40%) | 11.4s | none | No tool support |
| 12 | `qwen:0.5b` | 1/5 (20%) | 32s | none | No tool support |
| 12 | `tinydolphin:1.1b` | 1/5 (20%) | 102.4s | none | No tool support, verbose |
| 12 | `tinyllama:1.1b` | 1/5 (20%) | 103.8s | none | No tool support, verbose |

### Test Questions (5 Targeted Tests)

| Q# | Test | Purpose | Expected |
|----|------|---------|----------|
| Q1 | Simple Math | Basic calculator tool usage | 42 |
| Q2 | Multi-step | Observation handling (8×7 then -5) | 51 |
| Q3 | Division | Fraction/precision handling | 4.25 |
| Q4 | Word Problem | Natural language → expression | 10 |
| Q5 | Edge Case | Refusal handling (store hours) | 8 |

### Key Findings (Test 15)

1. **`qwen3.5:0.8b` is the sub-1B champion** - 100% with native tools!
2. **ReAct models perfect** - qwen2.5:0.5b and qwen2.5-coder:0.5b both at 100%
3. **`llama3.2:1b` regression** - Dropped to 60% (from 87% on test 07) - malformed JSON tool calls
4. **`granite3.1-moe:1b` multi-step issue** - Stopped after first operation on Q2 (56 instead of 51)
5. **No-tool models struggle** - Pure reasoning can't match tool usage for math
6. **Multi-step is hardest** - Q2 catches models that don't chain observations
7. **Edge case Q5 catches many** - Store hours problem causes reasoning errors

---

## R01 Results (Historical)

### Test 07 Benchmark Results (15-Test Suite)

> **Updated:** 2026-03-22 - Fresh single-run results with accurate timing.

---

### All Models Combined (R01 - Historical)

| Rank | Model | Params | Score | Time | Math | Reason | Know | Calc | Code |
|:----:|-------|-------:|------:|-----:|:----:|:------:|:----:|:----:|:----:|
| 🥇 | **`granite3.1-moe:1b`** | 1B MoE | **14/15 (93%)** | **95.7s** | 3/3 ✅ | 2/3 | **3/3** ✅ | **3/3** ✅ | **3/3** ✅ |
| 🥈 | `llama3.2:1b` | 1.2B | 13/15 (87%) | 189.3s | 3/3 ✅ | 2/3 | 2/3 | 3/3 ✅ | 3/3 ✅ |
| 🥉 | `qwen3:0.6b` | 600M | 12/15 (80%) | 388.9s | 3/3 ✅ | 2/3 | **3/3** ✅ | 3/3 ✅ | 1/3 |
| 4 | `nchapman/dolphin3.0-qwen2.5:0.5b` | 500M | 11/15 (73%) | **25.7s** | 1/3 | 2/3 | **3/3** ✅ | 2/3 | 3/3 ✅ |
| 4 | `granite4:350m` | 350M | 11/15 (73%) | 49.6s | 2/3 | 1/3 | 2/3 | 3/3 ✅ | 3/3 ✅ |
| 4 | `qwen2.5:0.5b` | 500M | 11/15 (73%) | 62.8s | 1/3 | 2/3 | 2/3 | 3/3 ✅ | 3/3 ✅ |
| 4 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | 494M | 11/15 (73%) | 85.8s | 2/3 | 1/3 | 2/3 | 3/3 ✅ | 3/3 ✅ |
| 8 | `tinyllama:1.1b` | 1.1B | 10/15 (67%) | 226.6s | 1/3 | 2/3 | **3/3** ✅ | 1/3 | 3/3 ✅ |
| 8 | `tinydolphin:1.1b` | 1.1B | 10/15 (67%) | 242.6s | 1/3 | 2/3 | **3/3** ✅ | 1/3 | 3/3 ✅ |
| 10 | `gemma3:270m` | 270M | 8/15 (53%) | 31.1s | **3/3** ✅ | 1/3 | 1/3 | 0/3 ❌ | 3/3 ✅ |
| 11 | `nchapman/dolphin3.0-llama3:1b` | 1B | 7/15 (47%) | 47.7s | 1/3 | 1/3 | 2/3 | 0/3 ❌ | 3/3 ✅ |

---

## GSM8K Benchmark Results

The following models have been tested on a **50-question GSM8K-style benchmark** using the Agent system with tool support detection.

---

### GSM8K Sub-1B Models (R01)

| Rank | Model | Score | Accuracy | Time | Tool Support | Δ vs Pre-R01 |
|:----:|-------|------:|--------:|-----:|--------------|:------------:|
| 🥇 | **`qwen2.5:0.5b`** | **45/50** | **90.0%** | 2772.2s | native | ↑ +18% |
| 🥈 | `granite4:350m` | 39/50 | 78.0% | 787.6s | native | ↑ +32% |
| 🥉 | `gemma3:270m` | 31/50 | 62.0% | 242.6s | none | = |

#### Key Findings (GSM8K R01)

1. **`qwen2.5:0.5b` achieves 90%** - matches `llama3.2:1b` at half the parameters!
2. **R01 native synthesis massive improvement** - 72% → 90% (+18%)
3. **`granite4:350m` improved 46% → 78%** - also huge gains
4. **Sub-500M models now competitive with 1B models** on GSM8K math

---

### GSM8K 1B+ Models (Pre-R01 - Historical)

| Rank | Model | Score | Accuracy | Avg Time | Tool Support | Notes |
|:----:|-------|------:|--------:|--------:|--------------|-------|
| 🥇 | **`llama3.2:1b`** | **45/50** | **90.0%** | 12.7s | ReAct | 🏆 **Best 1B model!** |
| 🥈 | `nchapman/dolphin3.0-llama3:1b` | 35/50 | 70.0% | **5.9s** | none | ⚡ **Fastest!** |
| 🥉 | `granite3.1-moe:1b` | 34/50 | 68.0% | 13.4s | ReAct | Solid MoE performer |
| 4 | `tinydolphin:1.1b` | 11/50 | 22.0% | 10.8s | none | Weak math reasoning |
| 5 | `tinyllama:1.1b` | 5/50 | 10.0% | 12.0s | none | Poor performance |

---

## BitNet Benchmark Results

AgentNova has been tested with **Microsoft BitNet-b1.58-2B-4T** — a 2B parameter model with 1.58-bit ternary weights.

### Test Results Summary

| Test Suite | Score | Time | Notes |
|------------|-------|------|-------|
| **Model Comparison** (15 tests) | **13/15 (87%)** | 394s | 5 categories |
| **Robust Comparison** (22 tests) | **19/22 (86%)** | ~6min | Incremental save |
| **Comprehensive Test** (7 tests) | **6/7 (86%)** | ~90s | Basic + Reasoning + Code |

---

## Recommendations

| Use Case | Recommended Model | Why |
|----------|-------------------|-----|
| **🏆 BEST OVERALL** | **`granite3.1-moe:1b`** | **93% in 87.8s** - best 1B model ever! |
| **Best Runner-up** | **`llama3.2:1b`** | **87%** - massive +20% improvement! |
| **Best Sub-1B** | **`qwen3.5:0.8b`** | **100%** on quick diagnostic, native tools! |
| **Best GSM8K** | **`qwen2.5:0.5b`** | **90% GSM8K** - matches 1B at half the size! |
| **Best Speed (73%+)** | `dolphin3.0-qwen2.5:0.5b` | **27.2s**, 73% accuracy |
| **Large context** | `llama3.2:1b` | **128k context window** |
| **CPU-only** | `BitNet-b1.58-2B-4T` | Efficient ternary weights |

### Mode Recommendations by Model

| Model | Recommended Mode | Reason |
|-------|------------------|--------|
| **`granite3.1-moe:1b`** | ReAct | 🏆 **Champion!** 93% |
| **`llama3.2:1b`** | Native | 87%, 128k context |
| **`qwen3.5:0.8b`** | Native | 🎯 **100% quick diagnostic** - new sub-1B king! |
| **`qwen2.5:0.5b`** | Native | 🎯 **90% GSM8K** - Calc champion |
| **`qwen2.5-coder:0.5b`** | ReAct | 100% quick diagnostic, Code focused |
| `dolphin3.0-qwen2.5:0.5b` | None | 73% pure reasoning, fastest |
| `qwen3:0.6b` | ReAct | 67%, requires `think=False` |
| `functiongemma:270m` | Native | 80% quick diagnostic |
| `granite4:350m` | Native | 80% quick diagnostic |
| `tinyllama:1.1b` | None | 53%, verbose responses |
| `tinydolphin:1.1b` | None | 60%, verbose responses |

---

## Tool Support Quick Reference

| Tool Support | Description | Prompt Strategy |
|--------------|-------------|-----------------|
| `native` | Ollama API tool-calling | Standard prompt + tools via API |
| `react` | Text-based ReAct parsing | Standard prompt + ReAct suffix |
| `none` | No tool support | `MATH_SYSTEM_PROMPT_NO_TOOLS` (pure reasoning) |
| `untested` | Not yet tested | Defaults to ReAct (safest) |

Test your models with:
```bash
agentnova models --tool_support
```

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
⚛️ AgentNova R02 Models
  Model                                      Family       Context    Tool Support
  ──────────────────────────────────────────────────────────────────────────────
  gemma3:270m                                gemma3       32K        ○ none
  granite4:350m                              granite      32K        ✓ native
  qwen2.5:0.5b                               qwen2        32K        ✓ native
  qwen3:0.6b                                 qwen3        32K        ReAct
  dolphin3.0-qwen2.5:0.5b                    qwen2        32K        ○ none
```