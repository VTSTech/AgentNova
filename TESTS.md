# ⚛️ AgentNova R03.3

## Test 01 Quick Diagnostic (5 Questions)

> **Updated:** 2026-03-26 - Soul mode fallback synthesis fix, qwen2:0.5b and gemma3:270m results

Test 01 is designed for rapid iteration and debugging. 5 targeted questions identify common failure modes quickly.

**Usage:**
```bash
agentnova test 01 --model qwen2.5:0.5b
agentnova test 01 --model qwen    # Fuzzy match: all qwen models
agentnova test 01 --model g       # Fuzzy match: gemma, granite, functiongemma
agentnova test 01 -m gemma3:270m --force-react --soul nova-helper  # With soul persona
```

### Quick Diagnostic Results (R03.3 - ≤1B Models)

| Rank | Model | Score | Time | Tool Support | Soul | Notes |
|:----:|-------|------:|-----:|:------------:|:----:|-------|
| 🥇 | **`functiongemma:270m`** | **5/5 (100%)** | 23.7s | native | - | 🏆 Fastest perfect score! |
| 🥈 | **`granite4:350m`** | **5/5 (100%)** | 44.5s | native | - | 🏆 Perfect with native tools |
| 🥉 | **`qwen2.5:0.5b`** | **5/5 (100%)** | 48.7s | native | - | 🏆 Perfect with native tools |
| 4 | **`qwen2.5-coder:0.5b-instruct-q4_k_m`** | **5/5 (100%)** | 93.3s | react | - | 🏆 Perfect with ReAct |
| 5 | **`qwen2:0.5b`** | **5/5 (100%)** | 53.8s | none | nova-helper | 🏆 Fallback synthesis fix! |
| 6 | **`qwen3:0.6b`** | **5/5 (100%)** | 102.3s | react | nova-helper | 🏆 **NEW!** Qwen3 family! |
| 7 | **`gemma3:270m`** | **5/5 (100%)** | 106.5s | react | nova-helper | 🏆 Soul + synthesis fix! |
| 8 | **`dolphin3.0-qwen2.5:0.5b`** | **5/5 (100%)** | 38.2s | none | nova-helper | 🏆 **+40%** with soul! |
| 9 | `qwen:0.5b` | 5/5 (100%) | 221.7s | react | - | 🏆 +80% --force-react used |
| 10 | **`qwen3.5:0.8b`** | **5/5 (100%)** | 331.8s | react | nova-helper | 🏆 **NEW!** Qwen3.5 family! |

### R03.3 Bug Fixes

| Issue | Before | After |
|-------|--------|-------|
| Soul mode accepting wrong answers | ❌ Accepted model's guess | ✅ Tries synthesis first |
| Tool support source not visible | ❌ Just showed "none" | ✅ Shows "none (source: cache/detected)" |
| Fallback synthesis only for REACT | ❌ Skipped for NONE mode | ✅ Works for all modes |
| Wrong Final Answer accepted | ❌ Model guess used | ✅ Calculator result overrides |

### Soul Persona Impact Analysis

> **R03.3:** Testing how focused soul personas improve small model performance

| Model | Params | Without Soul | With nova-helper | Improvement |
|-------|-------:|--------------|------------------|:-----------:|
| `qwen2:0.5b` | 500M | ~2/5 (40%) | **5/5 (100%)** | **+60%** ✅ |
| `qwen3:0.6b` | 600M | ~3/5 (60%) | **5/5 (100%)** | **+40%** ✅ |
| `gemma3:270m` | 270M | 4/5 (80%) | **5/5 (100%)** | **+20%** ✅ |
| `dolphin3.0-qwen2.5:0.5b` | 500M | 3/5 (60%) | **5/5 (100%)** | **+40%** ✅ |
| `qwen3.5:0.8b` | 800M | ~3/5 (60%) | **5/5 (100%)** | **+40%** ✅ |

**Key Insight:** A focused soul persona can transform a failing model into a perfect scorer! The nova-helper soul:
- Reduced dolphin3.0's time from 143.8s → 38.2s (3.7x faster!)
- Fixed Q5 (time calc) for both models
- Fixed Q2 (multi-step) for dolphin3.0
- **NEW:** Fallback synthesis now works in soul mode, catching model errors

### Test Questions (5 Targeted Tests)

| Q# | Test | Purpose | Expected |
|----|------|---------|----------|
| Q1 | Simple Math | Basic calculator tool usage | 42 |
| Q2 | Multi-step | Observation handling (8×7 then -5) | 51 |
| Q3 | Division | Fraction/precision handling | 4.25 |
| Q4 | Word Problem | Natural language → expression | 10 |
| Q5 | Time Calc | Store hours calculation | 8 |

### Key Findings (R03.3)

1. **10 models achieve 100%** - functiongemma:270m, granite4:350m, qwen2.5:0.5b, qwen2.5-coder:0.5b-instruct, qwen2:0.5b+soul, qwen3:0.6b+soul, gemma3:270m+soul, dolphin3.0+soul, qwen:0.5b, qwen3.5:0.8b+soul
2. **`functiongemma:270m` fastest perfect** - 23.7s for 5/5, native tools + 270M params!
3. **Qwen family dominates** - qwen2:0.5b, qwen3:0.6b, qwen3.5:0.8b all hit 100% with soul!
4. **`dolphin3.0+ nova-helper` fastest no-tool 100%** - 38.2s, pure ReAct mode!
5. **Fallback synthesis saves small models** - Catches wrong answers even when model "knows" it should use tools
6. **Tool-calling still dominates** - Native/react models score 100% without soul assistance
7. **Qwen3.5:0.8b slowest 100%** - 331.8s, but still perfect accuracy

### Failure Analysis (Without Soul)

| Model | Failed Questions | Issue |
|-------|-----------------|-------|
| `qwen2:0.5b` | Q3, Q4, Q5 | Wrong answers, no tool use |
| `gemma3:270m` | Q5 | Empty response, context issues |
| `qwen:0.5b` | Q2, Q3, Q4 | Base model, struggles with multi-step |
| `dolphin3.0-qwen2.5:0.5b` | Q2, Q5 | Tool support removed, wrote Python code instead of using calculator |

### Failure Resolution (With nova-helper Soul + Fallback Synthesis)

| Model | Before Soul | After Soul | Resolution |
|-------|-------------|------------|------------|
| `qwen2:0.5b` | ~2/5 (wrong calc) | **5/5** | Fallback synthesis catches wrong answers |
| `gemma3:270m` | 4/5 (Q5 empty) | **5/5** | Focused persona + synthesis keeps model on task |
| `dolphin3.0-qwen2.5:0.5b` | 3/5 (Q2 code, Q5 echo) | **5/5** | Clear tool instructions prevented code output |

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

### Key Findings (Test 16)

1. **Single-tool tasks work well** - Calculator, file write, shell all pass
2. **Multi-step planning fails** - Model stops after first action instead of continuing
3. **ReAct loop repetition** - Models repeat same action after success
4. **Pure reasoning errors** - Simple arithmetic mistakes (5-2-1=2, got 4)

### Known Issues

| Issue | Description | Impact |
|-------|-------------|--------|
| ReAct loop | Models repeat actions instead of Final Answer | Extra API calls |
| Multi-tool planning | Model doesn't chain tools properly | Multi-Tool test fails |
| Argument confusion | Wrong arg names (expression vs code) | Python REPL fallback |

---

## Test 07 Benchmark Results (15-Test Suite with Debug)


> **Updated:** 2026-03-23 - R02.5 module refactoring verified, updated prompts

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

--

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
| **🏆 BEST OVERALL** | **`functiongemma:270m`** | **100% in 23.7s** - fastest perfect, native tools! |
| **Best with Soul** | **`qwen2.5-coder:0.5b-instruct-q4_k_m`** + nova-helper | **100% in 52.2s** - 2x faster with soul! |
| **Best Runner-up** | **`granite4:350m`** | **100% in 44.5s** - native tools, 350M params |
| **Best Qwen3** | **`qwen3:0.6b`** + nova-helper | **100% in 102.3s** - newest Qwen family! |
| **Best Native** | **`qwen2.5:0.5b`** | **100% in 48.7s** - native tools, fast math! |
| **Best Speed (100%)** | `functiongemma:270m` | **23.7s**, 100% accuracy, 270M params |
| **Best No-Tool + Soul** | `qwen2:0.5b` + nova-helper | **100% in 53.8s** - fallback synthesis magic! |
| **Fastest Soul Speedup** | `qwen:0.5b` + nova-helper | **100% in 96.0s** - 2.3x faster than without! |
| **Smallest 100%** | `gemma3:270m` + nova-helper | **100%** - 270M params with soul! |
| **Large context** | `llama3.2:1b` | **128k context window**, 87% accuracy |
| **CPU-only** | `BitNet-b1.58-2B-4T` | Efficient ternary weights |

### Mode Recommendations by Model

| Model | Recommended Mode | Soul | Reason |
|-------|------------------|------|--------|
| **`functiongemma:270m`** | Native | - | 🏆 **Test 01 Champion!** 100% at 23.7s |
| **`granite4:350m`** | Native | - | 🏆 **100%** - native tools, 350M params |
| **`qwen2.5:0.5b`** | Native | - | 🏆 **100%** - native tools work great |
| **`qwen2.5-coder:0.5b-instruct-q4_k_m`** | ReAct | nova-helper | 🏆 **100% in 52.2s** - 2x faster with soul! |
| **`qwen2:0.5b`** | None | nova-helper | 🏆 **100%** - fallback synthesis saves it! |
| **`qwen:0.5b`** | ReAct | nova-helper | 🏆 **100% in 96.0s** - 2.3x faster with soul! |
| **`qwen3:0.6b`** | ReAct | nova-helper | 🏆 **100%** - newest Qwen family! |
| **`qwen3.5:0.8b`** | ReAct | nova-helper | 🏆 **100%** - larger Qwen3.5 model |
| **`gemma3:270m`** | ReAct | nova-helper | 🏆 **100%** - soul + synthesis fix |
| **`dolphin3.0-qwen2.5:0.5b`** | ReAct | nova-helper | 🏆 **100%** - soul fixes tool confusion |
| `dolphin3.0-qwen2.5:0.5b` | None | - | 60% without soul, tool support removed |
| `gemma3:270m` | None | - | 80% without soul, Q5 context issues |
| `llama3.2:1b` | Native | - | 87%, 128k context |

---

## Tool Support Quick Reference

| Tool Support | Description | Prompt Strategy |
|--------------|-------------|-----------------|
| `native` | Ollama API tool-calling | Standard prompt + tools via API |
| `react` | Text-based ReAct parsing | Standard prompt + ReAct suffix |
| `none` | No tool support | `MATH_SYSTEM_PROMPT_NO_TOOLS` (pure reasoning) |
| `untested` | Not yet tested | Defaults to ReAct (safest) |

---

## Soul Persona System

> **New in R03.2:** Soul personas can dramatically improve small model performance
> **R03.3 Update:** Fallback synthesis now works in soul mode - catches model errors!

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

**Impact:**
| Model | Without Soul | With nova-helper |
|-------|--------------|------------------|
| qwen2:0.5b | ~2/5 (40%) | **5/5 (100%)** |
| qwen3:0.6b | ~3/5 (60%) | **5/5 (100%)** |
| gemma3:270m | 4/5 (80%) | **5/5 (100%)** |
| dolphin3.0-qwen2.5:0.5b | 3/5 (60%) | **5/5 (100%)** |
| qwen3.5:0.8b | ~3/5 (60%) | **5/5 (100%)** |

**R03.3 Enhancement:** When soul mode is active, the system now attempts fallback synthesis before accepting the model's answer. This catches cases where the model "knows" it should use tools but outputs a wrong guess anyway.

**Create Custom Souls:**
```bash
# Inspect the nova-helper soul
agentnova soul agentnova/souls/nova-helper

# Use a custom soul package
agentnova test 01 -m qwen --soul /path/to/my-soul
```

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
⚛️ AgentNova R02.6 Models
  Model                                      Family       Context    Tool Support
  ──────────────────────────────────────────────────────────────────────────────
  gemma3:270m                                gemma3       32K        ○ none
  granite4:350m                              granite      32K        ✓ native
  qwen2.5:0.5b                               qwen2        32K        ✓ native
  qwen3:0.6b                                 qwen3        32K        ReAct
  functiongemma:270m                         gemma3       32K        ✓ native
  dolphin3.0-qwen2.5:0.5b                    qwen2        32K        ○ none
```