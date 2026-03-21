# ⚛️ AgentNova R02

## Test 07 Benchmark Results (15-Test Suite with Debug)

> **Updated:** 2026-03-22 - R02 release with Model Family Configuration and repetition fixes.

Test 07 uses the 15-test benchmark with debug output showing tool support detection, ReAct parsing, and family-specific configuration.

---

### All Models Combined (R02 - Latest)

| Rank | Model | Params | Score | Time | Math | Reason | Know | Calc | Code | Tool Support |
|:----:|-------|-------:|------:|-----:|:------:|:------:|:----:|:----:|:----:|--------------|
| 🥇 | **`granite3.1-moe:1b`** | 1B MoE | **12/15 (80%)** | **60.6s** | 3/3 ✅ | 2/3 | 3/3 ✅ | 1/3 | 3/3 ✅ | react |
| 🥇 | **`qwen3:0.6b`** | 600M | **12/15 (80%)** | 473.0s | 3/3 ✅ | 3/3 ✅ | 3/3 ✅ | 0/3 ❌ | 3/3 ✅ | react |
| 🥉 | `nchapman/dolphin3.0-qwen2.5:0.5b` | 500M | 11/15 (73%) | **24.5s** | 1/3 | 2/3 | 3/3 ✅ | 2/3 | 3/3 ✅ | none |
| 4 | `qwen2.5:0.5b` | 500M | 11/15 (73%) | 84.2s | 1/3 | 2/3 | 2/3 | 3/3 ✅ | 3/3 ✅ | native |
| 5 | `llama3.2:1b` | 1.2B | 10/15 (67%) | 180.1s | 3/3 ✅ | 2/3 | 2/3 | 0/3 ❌ | 3/3 ✅ | native |
| 5 | `tinyllama:1.1b` | 1.1B | 10/15 (67%) | 253.1s | 1/3 | 2/3 | 3/3 ✅ | 1/3 | 3/3 ✅ | none |
| 5 | `tinydolphin:1.1b` | 1.1B | 10/15 (67%) | 391.9s | 1/3 | 2/3 | 3/3 ✅ | 1/3 | 3/3 ✅ | none |
| 8 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | 494M | 8/15 (53%) | 65.8s | 2/3 | 1/3 | 2/3 | 0/3 ❌ | 3/3 ✅ | react |
| 9 | `nchapman/dolphin3.0-llama3:1b` | 1B | 7/15 (47%) | 43.8s | 1/3 | 1/3 | 2/3 | 0/3 ❌ | 3/3 ✅ | none |

---

### R02 Key Findings

1. **`qwen3:0.6b` is the NEW sub-1B champion at 80%!** - Perfect Math, Reasoning, Knowledge, and Code
2. **`granite3.1-moe:1b` ties at 80% but 8x faster** (60.6s vs 473s) 
3. **Model Family Detection Working** - `granite3.1-moe` shows `family_issues={'schema_dump': True, 'truncate_json': True}`
4. **Repetition Loop Fix Working** - No more 269s timeouts from "Final Answer:" loops
5. **Calc tests challenging for ReAct models** - Many output "Thought:" without completing "Action:"
6. **Code is universally easy** - All models score 100% on Code generation

---

### Category Champions (R02)

| Category | 🏆 Champion | Score | Notes |
|----------|-------------|-------|-------|
| **Math** | `qwen3:0.6b` / `granite3.1-moe:1b` / `llama3.2:1b` | 3/3 | Three-way tie |
| **Reasoning** | **`qwen3:0.6b`** | **3/3** | **Only perfect Reasoning!** |
| **Knowledge** | `qwen3:0.6b` / `granite3.1-moe:1b` / `dolphin3.0-qwen2.5:0.5b` | 3/3 | Three-way tie |
| **Calc** | `granite4:350m` / `qwen2.5:0.5b` | 3/3 | Native tools models dominate |
| **Code** | 9 models | 3/3 | Almost everyone perfect |

---

### Sub-1B Models (R02 - Current)

| Rank | Model | Params | Score | Time | Math | Reason | Know | Calc | Code | Tool Support |
|:----:|-------|-------:|------:|-----:|:------:|:------:|:----:|:----:|:----:|--------------|
| 🥇 | **`qwen3:0.6b`** | 600M | **12/15 (80%)** | 473.0s | 3/3 ✅ | 3/3 ✅ | 3/3 ✅ | 0/3 ❌ | 3/3 ✅ | react |
| 🥈 | `nchapman/dolphin3.0-qwen2.5:0.5b` | 500M | 11/15 (73%) | **24.5s** | 1/3 | 2/3 | 3/3 ✅ | 2/3 | 3/3 ✅ | none |
| 🥈 | `granite4:350m` | 350M | 11/15 (73%) | ~78s | 2/3 | 1/3 | 2/3 | 3/3 ✅ | 3/3 ✅ | native |
| 🥈 | `qwen2.5:0.5b` | 500M | 11/15 (73%) | ~54s | 1/3 | 2/3 | 2/3 | 3/3 ✅ | 3/3 ✅ | native |
| 5 | `gemma3:270m` | 270M | 8/15 (53%) | ~23s | 2/3 | 1/3 | 1/3 | 0/3 ❌ | 3/3 ✅ | none |
| 5 | `qwen2.5-coder:0.5b` | 494M | 8/15 (53%) | 65.8s | 2/3 | 1/3 | 2/3 | 0/3 ❌ | 3/3 ✅ | react |

#### Sub-1B Key Findings (R02)

1. **`qwen3:0.6b` is the sub-1B champion** - 80% with perfect Reasoning (only model!)
2. **Fastest 73%+ model: `dolphin3.0-qwen2.5:0.5b`** at 24.5s
3. **`qwen3:0.6b` Calc issue** - Returns empty responses in ReAct mode (0/3)
4. **Native tools models excel at Calc** - `granite4:350m` and `qwen2.5:0.5b` both 3/3
5. **`gemma3:270m` fastest pure reasoning** - No tool overhead, 23s total

---

### 1B+ Models (R02 - Current)

| Rank | Model | Params | Score | Time | Math | Reason | Know | Calc | Code | Tool Support |
|:----:|-------|-------:|------:|-----:|:------:|:------:|:----:|:----:|:----:|--------------|
| 🥇 | **`granite3.1-moe:1b`** | 1B MoE | **12/15 (80%)** | **60.6s** | 3/3 ✅ | 2/3 | 3/3 ✅ | 1/3 | 3/3 ✅ | react |
| 🥈 | `llama3.2:1b` | 1.2B | 10/15 (67%) | 180.1s | 3/3 ✅ | 2/3 | 2/3 | 0/3 ❌ | 3/3 ✅ | native |
| 3 | `nchapman/dolphin3.0-llama3:1b` | 1B | 7/15 (47%) | 43.8s | 1/3 | 1/3 | 2/3 | 0/3 ❌ | 3/3 ✅ | none |

#### 1B+ Key Findings (R02)

1. **`granite3.1-moe:1b` leads at 80%** - MoE architecture very efficient
2. **`llama3.2:1b` dropped to 67%** - Calc tests failing (0/3)
3. **Dolphin fine-tunes lose tool support** - `dolphin3.0-llama3:1b` at 47%

---

### Tool Support Impact (R02)

| Model | Tool Support | Calc Score | Notes |
|-------|--------------|------------|-------|
| `granite4:350m` | native | 3/3 ✅ | Native API tool calling |
| `qwen2.5:0.5b` | native | 3/3 ✅ | Native + synthesis fallback |
| `granite3.1-moe:1b` | react | 1/3 | Gets "Thought:" but incomplete "Action:" |
| `qwen3:0.6b` | react | 0/3 ❌ | Returns empty in Calc tests |
| `qwen2.5-coder:0.5b` | react | 0/3 ❌ | Gets "Thought:" without "Action:" |
| `dolphin3.0-qwen2.5:0.5b` | none | 2/3 | Pure reasoning, no tools |
| `gemma3:270m` | none | 0/3 ❌ | Pure reasoning, small model |
| `dolphin3.0-llama3:1b` | none | 0/3 ❌ | Pure reasoning, no tools |

**Key Insight**: Native tool models dominate Calc. ReAct models struggle to complete the Action step.

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
| **🏆 BEST OVERALL** | **`granite3.1-moe:1b`** | **80% in 60.6s** - fastest champion! |
| **Best Sub-1B** | **`qwen3:0.6b`** | **80%** - only perfect Reasoning score! |
| **Best GSM8K** | **`qwen2.5:0.5b`** | **90% GSM8K** - matches 1B at half the size! |
| **Best Speed (73%+)** | `nchapman/dolphin3.0-qwen2.5:0.5b` | **24.5s**, 73% accuracy |
| **Best Calc** | `granite4:350m` / `qwen2.5:0.5b` | **3/3 Calc** with native tools |
| **Large context** | `llama3.2:1b` | **128k context window** |
| **CPU-only** | `BitNet-b1.58-2B-4T` | Efficient ternary weights |

### Mode Recommendations by Model

| Model | Recommended Mode | Reason |
|-------|------------------|--------|
| **`granite3.1-moe:1b`** | ReAct | 🏆 **Champion!** 80% in 60.6s |
| **`qwen3:0.6b`** | ReAct | 80%, perfect Reasoning/Knowledge/Code |
| **`qwen2.5:0.5b`** | Native | 🎯 **90% GSM8K** - Calc champion |
| `granite4:350m` | Native | 73%, Calc champion |
| `llama3.2:1b` | Native | 67%, 128k context |
| `nchapman/dolphin3.0-qwen2.5:0.5b` | None | 73% pure reasoning, fastest |
| `gemma3:270m` | None | Cannot use tools, pure reasoning |
| `qwen2.5-coder:0.5b` | ReAct | 53%, Code focused |
| `nchapman/dolphin3.0-llama3:1b` | None | 47%, no tool support |

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
