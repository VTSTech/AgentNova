# ⚛️ AgentNova R03.8

## Test 01 Quick Diagnostic (5 Questions)

> **Updated:** 2026-03-28 - R03.8 testing in progress

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

### OpenResponses Mode Results (R03.6 - resp API Mode)

> Testing with `--api resp` (default) uses Ollama's native OpenResponses API (`/api/chat`)

#### Current Testing (2026-03-28)

> Test params: `--soul nova-helper --timeout 9999 --warmup --num-predict 128 --num-ctx 4096 --temp 0.0`

| Rank | Model | Score | Time | Soul | Tool Mode | Q1 | Q2 | Q3 | Q4 | Q5 | Notes |
|:----:|-------|------:|-----:|:----:|:---------:|:--:|:--:|:--:|:--:|:--:|-------|
| 🥇 | **`qwen2.5:0.5b`** | **5/5 (100%)** | 169.5s | nova-helper | **native** | ✅ | ✅ | ✅ | ✅ | ✅ | 🏆 Perfect score! Fastest! |
| 🥇 | **`qwen2.5-coder:0.5b`** | **5/5 (100%)** | 184.1s | nova-helper | **native** | ✅ | ✅ | ✅ | ✅ | ✅ | 🏆 Coder model joins 100% club! |
| 🥇 | **`granite4:350m`** | **5/5 (100%)** | 188.3s | nova-helper | **native** | ✅ | ✅ | ✅ | ✅ | ✅ | 🏆 Native tools working! |
| 🥇 | **`deepseek-r1:1.5b`** | **5/5 (100%)** | 304.7s | nova-helper | **native** | ✅ | ✅ | ✅ | ✅ | ✅ | 🏆 Perfect score! Reasoning model |
| 🥉 | `gemma3:270m` | **4/5 (80%)** | 425.2s | nova-helper | **native** | ✅ | ✅ | ✅ | ✅ | ❌ 1024 | Q5 reasoning error, improved! |
| 🥉 | `qwen3.5:0.8b` | 4/5 (80%) | 625.8s | nova-helper | native | ❌ empty | ✅ | ✅ | ✅ | ✅ | Q1 empty, very slow |
| 🥉 | `granite3.1-moe:1b` | **4/5 (80%)** | 225.4s | nova-helper | **native** | ✅ | ❌ 53 | ✅ | ✅ | ✅ | Q2 reasoning error, MoE model |
| 5 | `qwen2:0.5b` | 3/5 (60%) | 166.9s | nova-helper | native | ✅ | ✅ | ✅ | ❌ text | ❌ 24 | Q4/Q5 explanation text instead of tools |
| 5 | `qwen3:0.6b` | 3/5 (60%) | 231.3s | nova-helper | native | ❌ empty | ❌ 49 | ✅ | ✅ | ✅ | Q1 empty, Q2 reasoning error |
| 9 | `qwen:0.5b` | 2/5 (40%) | 232.7s | nova-helper | native | ✅ | ❌ 2 | ❌ 3 | ✅ | ❌ 4 | Q2/Q3/Q5 reasoning errors |
| 9 | `nchapman/dolphin3.0-qwen2.5:0.5b` | 2/5 (40%) | 287.1s | nova-helper | native | ❌ empty | ❌ empty | ❌ empty | ✅ | ✅ | Q1-Q3 empty responses |
| 11 | `functiongemma:270m` | 1/5 (20%) | 237.5s | nova-helper | native | ✅ | ❌ 51 | ❌ 1024 | ❌ refused | ❌ refused | Reasoning errors, Q5 refusal |

**Summary:**
- **4 models achieve 100%**: `granite4:350m`, `qwen2.5:0.5b`, `deepseek-r1:1.5b`, `qwen2.5-coder:0.5b`
- **3 models at 80%**: `gemma3:270m`, `qwen3.5:0.8b`, `granite3.1-moe:1b`
- **2 models at 60%**: `qwen2:0.5b`, `qwen3:0.6b`
- **2 models at 40%**: `qwen:0.5b`, `nchapman/dolphin3.0-qwen2.5:0.5b`
- **1 model at 20%**: `functiongemma:270m`

---

### Chat Completions Mode Results (R03.6 - comp API Mode)

> Testing with `--api comp` uses OpenAI-compatible Chat Completions API (`/v1/chat/completions`)
> Test params: `--soul nova-helper --timeout 9999 --warmup --num-predict 128 --num-ctx 4096 --temp 0.0`

| Rank | Model | Score | Time | Soul | Tool Mode | Q1 | Q2 | Q3 | Q4 | Q5 | Notes |
|:----:|-------|------:|-----:|:----:|:---------:|:--:|:--:|:--:|:--:|:--:|-------|
| 🥇 | **`granite4:350m`** | **5/5 (100%)** | 183.0s | nova-helper | **native** | ✅ | ✅ | ✅ | ✅ | ✅ | 🏆 Native tool calling! |
| 🥇 | **`qwen2.5:0.5b`** | **5/5 (100%)** | 169.8s | nova-helper | native | ✅ | ✅ | ✅ | ✅ | ✅ | 🏆 Perfect score! Fastest! |
| 🥇 | **`qwen2.5-coder:0.5b`** | **5/5 (100%)** | 182.7s | nova-helper | **native** | ✅ | ✅ | ✅ | ✅ | ✅ | 🏆 Coder model 100% in comp mode! |
| 🥉 | `granite3.1-moe:1b` | **4/5 (80%)** | 220.2s | nova-helper | **native** | ✅ | ❌ 53 | ✅ | ✅ | ✅ | Q2 reasoning error, MoE model |
| 🥉 | `gemma3:270m` | **4/5 (80%)** | 424.7s | nova-helper | native | ✅ | ✅ | ✅ | ✅ | ❌ 1024 | Q5 reasoning error, improved! |
| 4 | `qwen3:0.6b` | 3/5 (60%) | 476.9s | nova-helper | native | ❌ timeout | ❌ timeout | ✅ | ✅ | ✅ | Q1/Q2 timeouts |
| 4 | `qwen2:0.5b` | 3/5 (60%) | 164.5s | nova-helper | native | ✅ | ✅ | ✅ | ❌ text | ❌ 24 | Q4/Q5 explanation text instead of tools |
| 6 | `nchapman/dolphin3.0-qwen2.5:0.5b` | 2/5 (40%) | 282.8s | nova-helper | native | ❌ empty | ❌ empty | ❌ empty | ✅ | ✅ | Q1-Q3 empty responses |
| 6 | `dolphin3.0-qwen2.5:0.5b` | 2/5 (40%) | 105.7s | nova-helper | ReAct | ✅ | ❌ 4 | ✅ | ❌ 12 | ❌ 10 | Reasoning errors |
| 8 | `functiongemma:270m` | 1/5 (20%) | 225.0s | nova-helper | fallback | ✅ | ❌ calc | ❌ 1024 | ❌ refused | ❌ refused | Reasoning errors, Q5 refusal |
| 8 | `qwen:0.5b` | 1/5 (20%) | 226.3s | nova-helper | native | ❌ text | ❌ text | ❌ 35 | ❌ 0.43 | ✅ | Explanation text instead of tools |
| 10 | `qwen3.5:0.8b` | 0/5 (0%) | 295.3s | nova-helper | native | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ Memory limit - needs re-test |
| 10 | **`deepseek-r1:1.5b`** | **0/5 (0%)** | 445.4s | nova-helper | native | ❌ empty | ❌ empty | ❌ empty | ❌ empty | ❌ empty | ⚠️ Empty responses in comp mode! |

**Key Finding - deepseek-r1:1.5b API Mode Discrepancy:**
- **resp mode**: 100% (5/5) ✅
- **comp mode**: 0% (0/5) ❌ - Empty responses on all questions
- Possible tool calling format incompatibility between OpenResponses and ChatCompletions APIs

---

## Test 02 Tool Tests

> **Updated:** 2026-03-28 - R03.7 first results

Test 02 comprehensively evaluates tool calling across 6 categories.  Phase 1 validates tools directly (no model).  Phase 2 tests the model's ability to select, call, and interpret tools.

**Usage:**
```bash
agentnova test 02 --soul nova-helper --num-ctx 8192 --num-predict 512 --temp 0.1
agentnova test 02 --model-only -m granite4   # Phase 2 only, specific model
agentnova test 02 --tools-only                 # Phase 1 only, no model needed
agentnova test 02 --model-only -m qwen2.5:0.5b --debug
```

### Test Structure

**Phase 1 — Direct Tool Validation** (no model required):
| Category | Tests | Validates |
|----------|:-----:|-----------|
| Calculator | 19 | Math operations, constants, trig, edge cases, security |
| Shell | 11 | Command execution, injection blocking, path traversal |
| File Tools | 7 | Read/write/list, path security, empty files |
| HTTP | 8 | Valid requests, SSRF blocking, scheme validation |
| DateTime | 4 | Date/time formats, timezone handling, invalid input |
| JSON/Text | 5 | JSON parsing, word/char counting, edge cases |

**Phase 2 — Model Tool Calling** (model required):
| Category | Tests | Expected Tool | What It Measures |
|----------|:-----:|:------------:|-----------------|
| Calculator | 5 | calculator | Expression construction, result extraction |
| Shell | 2 | shell | Command formation, result relay |
| DateTime | 2 | get_time / get_date | Tool selection, answer formatting |
| File Tools | 2 | read_file / list_directory | Path handling, content extraction |
| Python REPL | 2 | python_repl | Code generation, result interpretation |
| All Tools | 4 | varies (calculator, shell, get_date, read_file) | **Tool selection from full set** |

---

### Phase 2 Results

> Test params: `--soul nova-helper --num-ctx 8192 --num-predict 512 --temp 0.1 --model-only --timeout 9999`

| Rank | Model | Score | Calc | Shell | DateTime | File | Repl | All Tools | Time | Tool Mode | Notes |
|:----:|-------|------:|:----:|:-----:|:--------:|:----:|:----:|:---------:|:----:|:---------:|-------|
| 🥇 | **`granite4:350m`** | **15/17 (88%)** | 5/5 | 2/2 | 2/2 | 1/2 | 2/2 | 3/4 | ~762s | **native** | 🏆 First tested! Strong calculator/shell |

#### granite4:350m Detailed Breakdown

**Calculator — 5/5 (100%)** ✅
| Test | Prompt | Expected | Got | Tool Used | Steps | Time |
|------|--------|:--------:|:----:|:---------:|:-----:|:----:|
| Basic multiplication | What is 15 times 8? | 120 | 120 | ✅ | 2 | 164.6s |
| Power | What is 2 to the power of 10? | 1024 | 1024 | ✅ | 2 | 10.2s |
| Square root | What is the square root of 144? | 12 | 12 | ✅ | 2 | 10.5s |
| Complex expression | What is (10 + 5) times 3? | 45 | 45 | ✅ | 2 | 11.1s |
| Division | What is 100 divided by 4? | 25 | 25 | ✅ | 2 | 11.4s |

**Shell — 2/2 (100%)** ✅
| Test | Prompt | Expected | Tool Used | Result Location | Time |
|------|--------|----------|:---------:|:---------------:|:----:|
| Echo test | Use shell to echo 'Hello AgentNova' | Hello AgentNova | ✅ | tool result | 95.1s |
| Current directory | What is the current working directory? | (any path) | ✅ | — | 7.7s |

> **Note:** Echo test passed via tool result fallback — model called shell correctly but hallucinated weather in the final answer instead of echoing the result.

**DateTime — 2/2 (100%)** ✅
| Test | Prompt | Tool Used | Result Location | Time |
|------|--------|:---------:|:---------------:|:----:|
| Get date | What is today's date? | ✅ get_date | answer | 96.6s |
| Get time | What time is it? | ✅ get_time | answer | 11.8s |

**File Tools — 1/2 (50%)**
| Test | Prompt | Expected | Tool Used | Result | Time |
|------|--------|----------|:---------:|:-------:|:----:|
| Read file | Read the file at /tmp/.../test.txt | AgentNova | ✅ read_file | tool result | 116.4s |
| List directory | List files in /tmp/.../tmpdir | test.txt | ✅ list_directory | ❌ | 195.0s |

> **Failure:** Model called `list_directory('/tmp')` instead of the full temp directory path `/tmp/tmp6ds0sx5i`. Listed parent directory contents (cloudflared, dap_multiplexer, etc.) which didn't contain `test.txt`.

**Python REPL — 2/2 (100%)** ✅
| Test | Prompt | Expected | Got | Tool Used | Time |
|------|--------|:--------:|:----:|:---------:|:----:|
| Calculate power | Use Python to calculate 2 to the power of 20 | 1048576 | 1048576 | ✅ | 98.6s |
| Math with math module | Use Python to calculate the square root of 144 | 12 | 12.0 | ✅ | 12.3s |

> **Note:** Square root test validates the `numbers_match()` fix — tool returned `12.0` but expected `"12"`. Numeric comparison with tolerance correctly matched.

**All Tools — 3/4 (75%)**
| Test | Prompt | Expected Tool | Correct Tool | Expected Content | Result | Time |
|------|--------|:------------:|:------------:|:---------------:|:------:|:----:|
| Calculator choice | What is 25 times 4? | calculator | ✅ | 100 | ✅ | 229.1s |
| Shell choice | Echo the text 'MultiTool' | shell | ❌ | MultiTool | ❌ | 13.8s |
| Date choice | What is today's date? | get_date | ✅ | (any date) | ✅ | 23.0s |
| File read choice | Read the file at /tmp/.../multi_test.txt | read_file | ✅ | Test content | ✅ | 20.3s |

> **Failure:** Shell choice — model didn't call any tool, responded with "I don't have enough context." This is a known issue with 350M parameter models when the prompt is vague.
>
> **Note:** Date choice passed tool selection despite model passing `{'type': ''}` as a spurious argument — test correctly identified `get_date` as the tool called.

---

### Key Findings (R03.7)

1. **granite4:350m achieves 88% on tool tests** — strongest performance from a sub-500M model
2. **Calculator tool calling is near-perfect** — 10/10 across calculator-specific and all-tools tests, with correct expression construction for all operation types
3. **Native tool calling critical** — all tool calls were native (via API `tool_calls`), no ReAct parsing needed
4. **Float vs integer handling matters** — `numbers_match()` fix prevented false negatives on `12` vs `12.0` in Python REPL
5. **Path handling is a weakness** — model truncated `/tmp/tmp6ds0sx5i` to `/tmp` in the list_directory test
6. **Vague prompts cause refusals** — "Echo the text 'MultiTool'" without explicit "Use shell" caused the model to refuse
7. **Tool result fallback essential** — 3 tests would have failed without the fallback that checks tool results when the model's final answer is wrong
8. **normalize_number last-number extraction** — prevents false display of question numbers instead of answer numbers (e.g., `15` vs `120` in "What is 15 times 8? ... 120")

### Comparison Logic Fixes Applied (R03.7)

Three fixes to `02_tool_test.py` improved result accuracy:

| Fix | Issue | Impact |
|-----|-------|--------|
| `numbers_match()` | `"12" != "12.0"` string comparison | Prevents false negatives on float results |
| `normalize_number` last-number | `"15 times 8 is 120"` → extracted `15` (first) | Now correctly extracts `120` (last) |
| `check_tool_used` strict matching | Substring scan of tool results caused false positives | Eliminates false tool detection |
| DateTime tool result fallback | Only checked `final_answer`, not tool results | Consistent with other test categories |

---

## Test 03 Reasoning Tests

> **Updated:** 2026-03-28 - R03.8 first results

Test 03 evaluates pure reasoning capability across 8 categories (14 questions). No tools are used — this tests the model's ability to reason, deduce, and solve problems through language alone.

**Usage:**
```bash
agentnova test 03 --model deepseek-r1:1.5b
agentnova test 03 --model granite4:350m --timeout 9999
```

### Test Structure

| Category | Tests | What It Measures |
|----------|:-----:|-----------------|
| Logical Deduction | 2 | Formal logic, syllogisms, deductive validity |
| Common Sense | 2 | Everyday knowledge, pragmatic reasoning |
| Multi-step | 2 | Chain-of-thought, sequential reasoning |
| Pattern | 2 | Sequence recognition, abstraction |
| Counter-intuitive | 2 | Overcoming cognitive biases, lateral thinking |
| Spatial | 2 | Mental rotation, geometric reasoning |
| Causal | 1 | Cause-and-effect identification |
| Comparative | 1 | Relative comparison and analysis |

---

### Results

> Test params: `--timeout 9999`

| Rank | Model | Score | Logical | Common | Multi | Pattern | Counter | Spatial | Causal | Compa | Time |
|:----:|-------|------:|:-------:|:------:|:-----:|:-------:|:-------:|:-------:|:------:|:-----:|:----:|
| 🥇 | **`deepseek-r1:1.5b`** | **13/14 (93%)** | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 1/2 | 1/1 | 1/1 | 759.3s |
| 🥈 | `granite3.1-moe:1b` | **8/14 (57%)** | 1/2 | 2/2 | 1/2 | 1/2 | 0/2 | 1/2 | 1/1 | 1/1 | 369.7s |
| 🥉 | `nchapman/dolphin3.0-qwen2.5:0.5b` | **7/14 (50%)** | 2/2 | 0/2 | 1/2 | 1/2 | 0/2 | 2/2 | 1/1 | 0/1 | 212.8s |
| 4 | `granite4:350m` | **6/14 (43%)** | 0/2 | 1/2 | 0/2 | 1/2 | 1/2 | 1/2 | 1/1 | 1/1 | 217.5s |
| 5 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | **5/14 (36%)** | 0/2 | 1/2 | 0/2 | 1/2 | 0/2 | 1/2 | 1/1 | 1/1 | 169.3s |
| 6 | `functiongemma:270m` | **3/14 (21%)** | 0/2 | 1/2 | 0/2 | 1/2 | 0/2 | 0/2 | 1/1 | 0/1 | 453.2s |
| 7 | `gemma3:270m` | **1/14 (7%)** | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 1/1 | 0/1 | 756.0s |

**Summary:**
- **deepseek-r1:1.5b dominates at 93%** — only missed 1 spatial question; reasoning model shows clear advantage
- **granite3.1-moe:1b leads the non-reasoning pack at 57%** — MoE architecture benefits complex reasoning
- **dolphin3.0 at 50%** — strong logical deduction and spatial, but weak common sense
- **Causal reasoning is the easiest category** — all 7 models scored 1/1 (100%)
- **Comparative reasoning is near-universal** — 6/7 models scored 1/1 (only dolphin3.0 missed)
- **Logical deduction separates tiers** — only deepseek-r1 and dolphin3.0 achieved 2/2
- **Counter-intuitive reasoning is the hardest** — most models scored 0/2; only deepseek-r1 (2/2) and granite4 (1/2) passed any
- **gemma3:270m struggles with reasoning** — only causal question passed (7%), despite achieving 80-100% on tool tests
- **No clear correlation between tool proficiency (Test 01/02) and reasoning ability (Test 03)**

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

### Tool Mode Comparison (R03.6)

| Tool Mode | Best Score | Best Model | Description |
|-----------|:----------:|------------|-------------|
| **Native** | **100%** | granite4:350m, qwen2.5:0.5b, deepseek-r1:1.5b, qwen2.5-coder:0.5b | Model uses API tool_calls directly |
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

### Key Findings (R03.6)

1. **qwen2.5-coder:0.5b joins the 100% club!** - Coder model improved from 80% to perfect score!
2. **4 models now achieve 100%** - granite4:350m, qwen2.5:0.5b, deepseek-r1:1.5b, qwen2.5-coder:0.5b
3. **3 models at 80%** - gemma3:270m (improved!), qwen3.5:0.8b, granite3.1-moe:1b
4. **granite3.1-moe:1b debuts at 80%** - MoE architecture with native tools
5. **Native tool calling fully working** - All models with native support can use tools
6. **Soul persona critical** - All tests used nova-helper soul for consistency
7. **resp mode significantly outperforms comp** for qwen family (40-80% gap)
8. **qwen:0.5b regressed to 40%** - Reasoning errors on Q2/Q3/Q5
9. **dolphin3.0 at 40%** - Empty responses on Q1-Q3, may need investigation
10. **functiongemma:270m struggles** - Reasoning errors and refusals

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
⚛️ AgentNova R03.6 Models
  Model                                      Family       Context    Tool Support
  ──────────────────────────────────────────────────────────────────────────────
  gemma3:270m                                gemma3       32K        ○ none
  granite4:350m                              granite      32K        ✓ native
  granite3.1-moe:1b                          granite      32K        ✓ native
  qwen2.5:0.5b                               qwen2        32K        ✓ native
  qwen3:0.6b                                 qwen3        32K        ReAct
  functiongemma:270m                         gemma3       32K        ✓ native
  nchapman/dolphin3.0-qwen2.5:0.5b           qwen2        32K        ○ none
  deepseek-r1:1.5b                           deepseek     128K       ✓ native
```