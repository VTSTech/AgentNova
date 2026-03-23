# ⚛️ AgentNova R02.5

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

> **Updated:** 2026-03-22 - R02.5 module refactoring verified, updated prompts

Test 07 uses the 15-test benchmark with debug output showing tool support detection, ReAct parsing, and family-specific configuration.

---

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

### R02.5 Key Findings

1. **Pure reasoning dominates!** Top 2 models have `tool_support=none` - no tools needed
2. **`qwen:0.5b` fastest champion** - 14/15 at 45.7s, pure reasoning mode
3. **`dolphin3.0-qwen2.5:0.5b` improved** - 73% → 93% (+20%) from updated no_tools prompt
4. **Three-way tie at 93%** - qwen:0.5b, dolphin3.0-qwen2.5:0.5b, granite3.1-moe:1b
5. **`functiongemma:270m` regression** - 80% → 27%, needs investigation
6. **Module refactoring verified** - All 13 models tested successfully after code split

### R02.5 Prompt Updates

| Family | Change | Impact |
|--------|--------|--------|
| gemma3 | Math-only → general-purpose prompt | Knowledge now works |
| dolphin | Added reasoning, code, Brazil examples | +20% on test 07 |

---

### Category Champions (R02.5)

| Category | 🏆 Champion | Score | Notes |
|----------|-------------|-------|-------|
| **Math** | `qwen:0.5b` | 3/3 | Pure reasoning perfect |
| **Reasoning** | Multiple models | 2/3 | Logic question tricky |
| **Knowledge** | `qwen:0.5b` | 3/3 | Only model with Brazil=Brasilia! |
| **Calc** | Multiple models | 3/3 | Several perfect |
| **Code** | 10 models | 3/3 | Universally easy |

---

### Sub-1B Models (R02.5 - Current)

| Rank | Model | Params | Score | Time | Tool Support | Δ vs R02.2 |
|:----:|-------|-------:|------:|-----:|:-----------:|:--------:|
| 🥇 | **`qwen:0.5b`** | 500M | **14/15 (93%)** | **45.7s** | none | **+20%** ✅ |
| 🥈 | **`dolphin3.0-qwen2.5:0.5b`** | 500M | **14/15 (93%)** | 53.0s | none | **+20%** ✅ |
| 🥉 | `qwen2.5:0.5b` | 500M | 11/15 (73%) | 85.7s | native | = |
| 4 | `granite4:350m` | 350M | 10/15 (67%) | 70.2s | native | -13% |
| 4 | `qwen3:0.6b` | 600M | 10/15 (67%) | 196.1s | react | = |
| 6 | `qwen2.5-coder:0.5b` | 494M | 9/15 (60%) | 132.2s | react | = |
| 7 | `gemma3:270m` | 270M | 9/15 (60%) | 33.9s | none | = |
| 8 | `functiongemma:270m` | 270M | 4/15 (27%) | 52.6s | native | -53% |

#### Sub-1B Key Findings (R02.5)

1. **`qwen:0.5b` is the sub-1B champion** - 93% at 45.7s, pure reasoning!
2. **No-tool models shine** - qwen:0.5b and dolphin3.0-qwen2.5:0.5b both 93%
3. **`functiongemma:270m` needs investigation** - Dropped from 80% to 27%

---

### 1B+ Models (R02.5 - Current)

| Rank | Model | Params | Score | Time | Tool Support | Δ vs R02.2 |
|:----:|-------|-------:|------:|-----:|:-----------:|:--------:|
| 🥇 | **`granite3.1-moe:1b`** | 1B MoE | **14/15 (93%)** | 128.6s | react | = |
| 🥈 | **`llama3.2:1b`** | 1.2B | **13/15 (87%)** | 174.5s | native | = |
| 🥉 | `dolphin3.0-llama3:1b` | 1B | 10/15 (67%) | 70.1s | none | N/A |
| 4 | `tinydolphin:1.1b` | 1.1B | 10/15 (67%) | 137.2s | none | +7% |
| 5 | `tinyllama:1.1b` | 1.1B | 8/15 (53%) | 134.9s | none | = |

#### 1B+ Key Findings (R02.5)

1. **`granite3.1-moe:1b` maintains 93%** - Still the best 1B+ model
2. **`llama3.2:1b` solid at 87%** - Native tool support works well
3. **MoE slower but accurate** - granite3.1-moe takes 128.6s vs 70.1s for dolphin3.0-llama3:1b

---

### Tool Support Impact (R02.5)

| Model | Tool Support | Score | Notes |
|-------|--------------|-------|-------|
| `qwen:0.5b` | none | **93%** | 🏆 Pure reasoning champion! |
| `dolphin3.0-qwen2.5:0.5b` | none | **93%** | 🏆 No tools needed |
| `granite3.1-moe:1b` | react | **93%** | 🏆 ReAct works great |
| `llama3.2:1b` | native | 87% | Native API tool calling |
| `qwen2.5:0.5b` | native | 73% | Empty tool calls, synthesis helps |
| `functiongemma:270m` | native | 27% | ❓ Regression - needs investigation |

**Key Insight**: Pure reasoning (no tools) can outperform tool-assisted models on simple tasks!

---

### All Models Combined (R02.2 - Historical)

| Rank | Model | Params | Score | Time | Tool Support |
|:----:|-------|-------:|------:|-----:|:-----------:|
| 🥇 | **`granite3.1-moe:1b`** | 1B MoE | **14/15 (93%)** | 87.8s | react |
| 🥈 | **`llama3.2:1b`** | 1.2B | **13/15 (87%)** | 150.2s | native |
| 🥉 | `nchapman/dolphin3.0-qwen2.5:0.5b` | 500M | 11/15 (73%) | 27.2s | none |
| 4 | `qwen3:0.6b` | 600M | 10/15 (67%) | 189.3s | react |
| 5 | `tinydolphin:1.1b` | 1.1B | 9/15 (60%) | 130.9s | none |
| 5 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | 494M | 9/15 (60%) | 133.1s | react |
| 7 | `tinyllama:1.1b` | 1.1B | 8/15 (53%) | 127.7s | none |

---

### R02.2 Key Findings

1. **`granite3.1-moe:1b` reached 93%** - Best score with ReAct mode
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

### Sub-1B Models (R02.2 - Historical)

| Rank | Model | Params | Score | Time | Tool Support |
|:----:|-------|-------:|------:|-----:|:-----------:|
| 🥇 | `nchapman/dolphin3.0-qwen2.5:0.5b` | 500M | 11/15 (73%) | **27.2s** | none |
| 🥈 | `qwen3:0.6b` | 600M | 10/15 (67%) | 189.3s | react |
| 🥉 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | 494M | 9/15 (60%) | 133.1s | react |

#### Sub-1B Key Findings (R02.2)

1. **`dolphin3.0-qwen2.5:0.5b` leads at 73%** - Fastest sub-1B at 27.2s
2. **`qwen3:0.6b` restored** - Was 0% (broken), now 67% with `think=False` fix
3. **`qwen2.5-coder:0.5b` improved** - 53% → 60% with ReAct fixes

---

### 1B+ Models (R02.2 - Historical)

| Rank | Model | Params | Score | Time | Tool Support |
|:----:|-------|-------:|------:|-----:|:-----------:|
| 🥇 | **`granite3.1-moe:1b`** | 1B MoE | **14/15 (93%)** | 87.8s | react |
| 🥈 | **`llama3.2:1b`** | 1.2B | **13/15 (87%)** | 150.2s | native |
| 🥉 | `tinydolphin:1.1b` | 1.1B | 9/15 (60%) | 130.9s | none |
| 4 | `tinyllama:1.1b` | 1.1B | 8/15 (53%) | 127.7s | none |

#### 1B+ Key Findings (R02.2)

1. **`granite3.1-moe:1b` dominates at 93%** - Best 1B+ model
2. **`llama3.2:1b` solid at 87%** - Native tool support works well
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

**Key Insight**: R02.2 fixes dramatically improved ReAct models.

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

> **Updated:** 2026-03-22 - R02.5 module refactoring verified

Test 15 is designed for rapid iteration and debugging. 5 targeted questions identify common failure modes quickly.

**Usage:**
```bash
agentnova test 15 --model granite3.1-moe:1b
agentnova test 15 --model all --debug
```

### Quick Diagnostic Results (R02.5)

| Rank | Model | Score | Time | Tool Support | Notes |
|:----:|-------|------:|-----:|:------------:|-------|
| 🥇 | **`dolphin3.0-llama3:1b`** | **5/5 (100%)** | 48.7s | native | 🏆 Fastest perfect score! |
| 🥇 | **`granite4:350m`** | **5/5 (100%)** | 75.2s | native | 🏆 Perfect with native tools |
| 🥇 | **`qwen2.5-coder:0.5b`** | **5/5 (100%)** | 76.0s | react | 🏆 Perfect with ReAct |
| 🥇 | **`qwen3:0.6b`** | **5/5 (100%)** | 151.0s | react | 🏆 Perfect with ReAct |
| 5 | `functiongemma:270m` | 4/5 (80%) | 28.5s | native | Word problem wrong expression |
| 5 | `dolphin3.0-qwen2.5:0.5b` | 4/5 (80%) | 38.4s | none | Pure reasoning, edge case failed |
| 7 | `gemma3:270m` | 3/5 (60%) | 12.8s | none | No tool support, fast |
| 7 | `granite3.1-moe:1b` | 3/5 (60%) | 114.0s | react | Multi-step and edge case failed |
| 7 | `llama3.2:1b` | 3/5 (60%) | 257.1s | native | Hallucinated JSON schema |
| 10 | `qwen2.5:0.5b` | 2/5 (40%) | 76.0s | native | Empty tool calls, synthesis helped |
| 11 | `qwen:0.5b` | 1/5 (20%) | 47.9s | none | No tool support, verbose |
| 11 | `tinyllama:1.1b` | 1/5 (20%) | 107.5s | none | No tool support, verbose |
| 13 | `tinydolphin:1.1b` | 0/5 (0%) | 118.8s | none | No tool support, verbose |

### Test Questions (5 Targeted Tests)

| Q# | Test | Purpose | Expected |
|----|------|---------|----------|
| Q1 | Simple Math | Basic calculator tool usage | 42 |
| Q2 | Multi-step | Observation handling (8×7 then -5) | 51 |
| Q3 | Division | Fraction/precision handling | 4.25 |
| Q4 | Word Problem | Natural language → expression | 10 |
| Q5 | Edge Case | Refusal handling (store hours) | 8 |

### Key Findings (R02.5)

1. **4 models achieve 100%** - dolphin3.0-llama3:1b, granite4:350m, qwen2.5-coder:0.5b, qwen3:0.6b
2. **`dolphin3.0-llama3:1b` fastest perfect** - 48.7s for 5/5, native tools work great
3. **Module refactoring verified** - All 13 models tested successfully after splitting agent.py into 6 modules
4. **Native tool support varies** - granite4 and functiongemma excel with native, qwen2.5:0.5b struggles
5. **ReAct mode saves qwen models** - qwen3:0.6b and qwen2.5-coder:0.5b perfect with ReAct
6. **No-tool models struggle** - dolphin3.0-qwen2.5:0.5b (80%) best of the no-tool-support models
7. **Multi-step Q2 is hardest** - Catches models that don't chain observations correctly
8. **Edge case Q5 catches reasoning errors** - Store hours problem confuses pure reasoning models

### R02.5 Module Refactoring

The agent.py module was split into 6 focused modules:

| Module | Purpose | Lines |
|--------|---------|-------|
| `types.py` | Type aliases (`StepResultType`) | ~10 |
| `models.py` | Dataclasses (`StepResult`, `AgentRun`) | ~30 |
| `prompts.py` | System prompts, few-shot examples, constants | ~180 |
| `helpers.py` | Utility functions (model detection, text processing) | ~200 |
| `args_normal.py` | Argument normalization and synthesis | ~240 |
| `tool_parse.py` | ReAct and JSON tool call parsing | ~370 |

**Result:** All tests pass, backward compatibility maintained via `__init__.py` exports.

### Quick Diagnostic Results (R02.2 - Historical)

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
| **🏆 BEST OVERALL** | **`qwen:0.5b`** | **93% in 45.7s** - fastest champion, pure reasoning! |
| **Best Runner-up** | **`dolphin3.0-qwen2.5:0.5b`** | **93% in 53.0s** - pure reasoning, no tools needed |
| **Best with Tools** | **`granite3.1-moe:1b`** | **93%** - ReAct mode, 1B MoE architecture |
| **Best GSM8K** | **`qwen2.5:0.5b`** | **90% GSM8K** - matches 1B at half the size! |
| **Best Speed (93%)** | `qwen:0.5b` | **45.7s**, 93% accuracy, 500M params |
| **Large context** | `llama3.2:1b` | **128k context window**, 87% accuracy |
| **CPU-only** | `BitNet-b1.58-2B-4T` | Efficient ternary weights |

### Mode Recommendations by Model

| Model | Recommended Mode | Reason |
|-------|------------------|--------|
| **`qwen:0.5b`** | None | 🏆 **Test 07 Champion!** 93% at 45.7s |
| **`dolphin3.0-qwen2.5:0.5b`** | None | 🏆 **93%** - pure reasoning works great |
| **`granite3.1-moe:1b`** | ReAct | 🏆 **93%** - best with tools |
| **`llama3.2:1b`** | Native | 87%, 128k context |
| **`dolphin3.0-llama3:1b`** | Native | 🎯 **100% quick diagnostic, fastest perfect!** |
| **`granite4:350m`** | Native | 🎯 **100% quick diagnostic** |
| **`qwen2.5-coder:0.5b`** | ReAct | 🎯 **100% quick diagnostic**, Code focused |
| **`qwen3:0.6b`** | ReAct | 🎯 **100% quick diagnostic** |
| `qwen2.5:0.5b` | Native | 🎯 **90% GSM8K** - Calc champion |
| `functiongemma:270m` | Native | ⚠️ 27% regression - needs investigation |
| `gemma3:270m` | None | 60%, very fast (33.9s) |
| `tinyllama:1.1b` | None | 53%, verbose responses |
| `tinydolphin:1.1b` | None | 67%, verbose responses |

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
⚛️ AgentNova R02.5 Models
  Model                                      Family       Context    Tool Support
  ──────────────────────────────────────────────────────────────────────────────
  gemma3:270m                                gemma3       32K        ○ none
  granite4:350m                              granite      32K        ✓ native
  qwen2.5:0.5b                               qwen2        32K        ✓ native
  qwen3:0.6b                                 qwen3        32K        ReAct
  dolphin3.0-qwen2.5:0.5b                    qwen2        32K        ○ none
```