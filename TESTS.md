# ⚛️ AgentNova R04.5

## Test 01 Quick Diagnostic (5 Questions)

Test 01 is designed for rapid iteration and debugging. 5 targeted questions identify common failure modes quickly.

> **Updated:** 2026-04-06 - R04.5 OpenResponses (openre) with-soul results refreshed (7 models updated, gemma4:e2b added → 19 models)
> **Previous:** 2026-04-05 - R04.5 ChatCompletions (openai) with-soul results expanded (12→18 models)
> **Previous:** 2026-04-04 - R04.5 ChatCompletions (openai) with-soul results expanded (9→12 models)
> **Previous:** 2026-04-04 - R04.5 OpenResponses (openre) with-soul results complete (16/16 models)

**Usage:**
```bash
agentnova test 01 --model qwen2.5:0.5b
agentnova test 01 --model qwen    # Fuzzy match: all qwen models
agentnova test 01 --model g       # Fuzzy match: gemma, granite, functiongemma
agentnova test 01 -m gemma3:270m --force-react --soul nova-helper  # With soul persona
agentnova test 01 -m granite4:350m --api openai  # Chat Completions API
agentnova test 01 -m qwen:0.5b --num-ctx 8192  # Custom context window
```

---

### OpenResponses Mode Results (R04.5 - openre API Mode, WITH SOUL)

> Testing with `--api openre --soul nova-helper` uses Ollama's native OpenResponses API (`/api/chat`) with the nova-helper soul persona
> Test params: `--timeout 9999 --num-ctx 16768 --num-predict 256 --temp 0.1 --soul nova-helper`
> Environment: CPU-only Google Colab, 12GB RAM, Ollama
> ✅ **Complete** — All 19 models tested

| Rank | Model | Size | Score | Time | Q1 | Q2 | Q3 | Q4 | Q5 | vs R04.4 | Notes |
|:----:|-------|-----:|------:|:----:|:--:|:--:|:--:|:--:|:---------:|-------|-------|
| 1 | **`granite4:350m`** | 0.66 GB | **5/5 (100%)** | 287.7s | ✅ | ✅ | ✅ | ✅ | ✅ | 0 | Fastest 100%. 224s cold, ~16s warm. Smallest at 350M. |
| 1 | **`qwen2.5:1.5b`** | 0.92 GB | **5/5 (100%)** | 543.5s | ✅ | ✅ | ✅ | ✅ | ✅ | NEW | 100% in openre. ~18s/q warm. |
| 1 | **`deepseek-r1:1.5b`** | ~0.91 GB | **5/5 (100%)** | 604.5s | ✅ | ✅ | ✅ | ✅ | ✅ | NEW | Reasoning model; 502s cold, ~26s warm. |
| 1 | **`gemma4:e2b`** | ~2.0 GB | **5/5 (100%)** | 1063.9s | ✅ | ✅ | ✅ | ✅ | ✅ | NEW | Fourth 100% in openre. 660s cold, ~101s warm. |
| 2 | `driaforall/tiny-agent-a:0.5b` | ~0.5 GB | **4/5 (80%)** | 254.0s | ✅ | ✅ | ✅ | ✅ | ❌ empty | NEW | Q1 fixed (was 3/5). Q5 still empty. 7.8s warmup. |
| 2 | `qwen2:0.5b` | 0.33 GB | **4/5 (80%)** | 200.8s | ✅ | ✅ | ✅ | ❌ text | ✅ | 0 | Q4 text instead of answer. |
| 2 | `nchapman/dolphin3.0-qwen2.5:0.5b` | 0.37 GB | **4/5 (80%)** | 208.6s | ✅ | ❌ 39 | ✅ | ✅ | ✅ | -1 | Q2 regression (was 5/5 in R04.4). Fastest 80%. |
| 2 | `qwen2.5:0.5b` | 0.37 GB | **4/5 (80%)** | 232.4s | ✅ | ✅ | ✅ | ❌ text | ✅ | -1 | Q4 text instead of answer. |
| 2 | `granite3.1-moe:1b` | ~0.7 GB | **4/5 (80%)** | 365.3s | ✅ | ❌ 53 | ✅ | ✅ | ✅ | NEW | MoE. Q2 off-by-2 (got 53 vs 51). ~17s warm. |
| 2 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | 0.37 GB | **4/5 (80%)** | 306.7s | ✅ | ✅ | ✅ | ✅ | ❌ empty | +1 | Q5 empty. Coder overthinks some questions. |
| 2 | `qwen3:0.6b` | 0.49 GB | **4/5 (80%)** | 484.9s | ✅ | ✅ | ✅ | ✅ | ❌ 17h | +1 | Q5 persistent time calc error. 382s cold start. |
| 2 | `qwen3.5:0.8b` | 0.96 GB | **4/5 (80%)** | 652.9s | ✅ | ❌ 45 | ✅ | ✅ | ✅ | 0 | Same score as R04.4; exact same Q2 failure (got 45 vs 51). |
| 2 | `llama3.2:1b` | ~1.24 GB | **4/5 (80%)** | 757.2s | ❌ empty | ✅ | ✅ | ✅ | ✅ | NEW | Q1 cold start. Q2-Q5 all pass at ~60s. |
| 3 | `nchapman/dolphin3.0-llama3:1b` | ~1.24 GB | **3/5 (60%)** | 403.6s | ✅ | ❌ 57 | ❌ 5.25 | ✅ | ✅ | NEW | Q2 off-by-6, Q3 division error. ~12s warm. |
| 4 | `gemma3:270m` | 0.27 GB | **2/5 (40%)** | 553.0s | ❌ tmpl | ❌ 3 | ✅ | ✅ | ❌ tmpl | 0 | Q3 fixed. Q2=3, Q5 tmpl. 2x faster than prev run. |
| 5 | `qwen:0.5b` | 0.37 GB | **1/5 (20%)** | 341.5s | ✅ | ❌ text | ❌ 68 | ❌ 24 | ❌ 24h | -1 | No tool use. Base model too small. |
| 5 | `deepseek-coder:1.3b` | ~0.67 GB | **1/5 (20%)** | 1395.0s | ✅ | ❌ 21 | ❌ code | ❌ code | ❌ text | NEW | Q1 fixed, Q5 regressed. No tool use. Slowest (1395s). |
| 6 | `functiongemma:270m` | 0.28 GB | **0/5 (0%)** | 352.6s | ❌ expr | ❌ expr | ❌ 4.0 | ❌ refused | ❌ refused | -1 | Q1-Q2 echo expressions, Q4-Q5 refusals. |
| 6 | `qwen:1.8b` | 1.04 GB | **0/5 (0%)** | 783.2s | ❌ garb. | ❌ garb. | ❌ garb. | ❌ garb. | ❌ garb. | NEW | Complete failure; garbled markdown, unusable.

---

### Chat Completions Mode Results (R04.5 - openai API Mode, WITH SOUL)

> Testing with `--api openai --soul nova-helper --warmup` uses OpenAI-compatible Chat Completions API (`/v1/chat/completions`) with the nova-helper soul persona
> Test params: `--timeout 9999 --num-ctx 16768 --num-predict 256 --temp 0.2 --soul nova-helper --api openai --warmup`
> Environment: CPU-only Google Colab, 12GB RAM, Ollama
> ✅ **Complete** — All 18 models tested

| Rank | Model | Score | Time | Q1 | Q2 | Q3 | Q4 | Q5 | vs R04.4 openai | Notes |
|:----:|-------|------:|:----:|:--:|:--:|:--:|:--:|:---------:|:------:|-------|
| 1 | **`qwen2.5:0.5b`** | **5/5 (100%)** | 239.4s | ✅ | ✅ | ✅ | ✅ | ✅ | 0 | Still perfect. 5.1s on Q5. Warmup: 8.3s. |
| 1 | **`granite4:350m`** | **5/5 (100%)** | 259.1s | ✅ | ✅ | ✅ | ✅ | ✅ | 0 | Still perfect in openai. 205s cold, ~13s warm. Native tool caller. |
| 1 | **`qwen2.5:1.5b`** | **5/5 (100%)** | 564.5s | ✅ | ✅ | ✅ | ✅ | ✅ | NEW | Perfect in openai too. 478s cold, ~22s warm. |
| 1 | **`llama3.2:1b`** | **5/5 (100%)** | 599.8s | ✅ | ✅ | ✅ | ✅ | ✅ | NEW | Perfect in openai! Warmup fixed Q1 cold start from openre (4/5→5/5). ~63s warm. |
| 1 | **`qwen3.5:0.8b`** | **5/5 (100%)** | 830.6s | ✅ | ✅ | ✅ | ✅ | ✅ | +3 | Massive improvement from 2/5! Warmup fixed Q1-Q3 empty. |
| 2 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | **4/5 (80%)** | 302.3s | ✅ | ✅ | ✅ | ✅ | ❌ empty | 0 | Same score; Q5 empty again. Warmup: 1.2s. |
| 2 | `granite3.1-moe:1b` | **4/5 (80%)** | 321.8s | ✅ | ❌ 53 | ✅ | ✅ | ✅ | NEW | Q2 off-by-2 (got 53 vs 51). 276s cold, ~12s warm. MoE architecture. |
| 2 | `qwen3:0.6b` | **4/5 (80%)** | 890.3s | ✅ | ❌ 53 | ✅ | ✅ | ✅ | -1 | Q5 fixed (was 17h), Q2 regression (off-by-2). 464s cold. |
| 3 | `qwen2:0.5b` | **3/5 (60%)** | 224.6s | ✅ | ✅ | ✅ | ❌ 24 | ❌ empty | -1 | Regression from 4/5. Q4 wrong math (24), Q5 empty. |
| 3 | `nchapman/dolphin3.0-llama3:1b` | **3/5 (60%)** | 382.8s | ✅ | ❌ 57 | ❌ 5.25 | ✅ | ✅ | NEW | Same score as openre. Q2 off-by-6, Q3 off-by-1. ~13s warm. |
| 3 | `driaforall/tiny-agent-a:0.5b` | **3/5 (60%)** | 245.0s | ❌ empty | ✅ | ✅ | ✅ | ❌ empty | NEW | Same score as openre. Q1 cold start, Q5 empty. ~25s warm. |
| 4 | `nchapman/dolphin3.0-qwen2.5:0.5b` | **2/5 (40%)** | 247.6s | ❌ 405 | ❌ 43 | ❌ empty | ✅ | ✅ | +1 | Improved from 1/5. Q1=405, Q2 off-by-8, Q3 empty. |
| 4 | `gemma3:270m` | **2/5 (40%)** | 827.5s | ❌ 405 | ❌ 3 | ✅ | ✅ | ❌ empty | +1 | Q3 fixed (was `<the result>` in R04.4). Q1 wrong (405), Q5 empty. |
| 5 | `qwen:0.5b` | **1/5 (20%)** | 346.2s | ✅ | ❌ 561 | ❌ 68 | ❌ 16 | ❌ 24h | +1 | Base model hallucinated math (8*7=560, 17/4=68). No tool use. |
| 5 | `deepseek-coder:1.3b` | **1/5 (20%)** | 1251.1s | ✅ | ❌ empty | ❌ empty | ❌ refused | ❌ empty | 0 | Same score as openre. Slowest model (1251s). Q4 refusal, rest empty. |
| 6 | `functiongemma:270m` | **0/5 (0%)** | 350.9s | ❌ expr | ❌ 35 | ❌ 4.00 | ❌ refused | ❌ refused | 0 | Same score as R04.4. Q1 echoes expression, Q4-Q5 refusals. |
| 6 | `deepseek-r1:1.5b` | **0/5 (0%)** | 764.8s | ❌ empty | ❌ empty | ❌ empty | ❌ empty | ❌ empty | NEW | Catastrophic regression from openre 5/5→0/5. All empty. |
| 6 | `qwen:1.8b` | **0/5 (0%)** | 792.7s | ❌ garb. | ❌ garb. | ❌ garb. | ❌ garb. | ❌ empty | 0 | Same as R04.4; garbled markdown, unusable. |

---

### BitNet Backend Results (R04.4 - openre API Mode, WITH SOUL)

> Testing with `--backend bitnet --soul nova-helper` uses the BitNet backend (`http://localhost:8765`) with OpenResponses API and the nova-helper soul persona
> Test params: `--backend bitnet --soul nova-helper --num-ctx 16384 --num-predict 128 --timeout 999 --temp 0.1`
> ✅ **Complete** — 1 model tested

| Rank | Model | Score | Time | Q1 | Q2 | Q3 | Q4 | Q5 | Notes |
|:----:|-------|------:|:----:|:--:|:--:|:--:|:--:|:---------:|-------|
| 1 | **`bitnet-b1.58-2B-4T`** | **4/5 (80%)** | 80.7s | ✅ | ✅ | ✅ | ✅ | ❌ -4 | First BitNet result! Q5 time calc error (expected 8, got -4) |

---

### Chat Completions Mode Results (R04.4 - openai API Mode, WITH SOUL)

> Testing with `--api openai --soul nova-helper` uses OpenAI-compatible Chat Completions API (`/v1/chat/completions`) with the nova-helper soul persona
> Test params: `--api openai --soul nova-helper --timeout 999`
> ✅ **Complete** — All 10 models tested

| Rank | Model | Score | Time | Q1 | Q2 | Q3 | Q4 | Q5 | vs R03.9 | Notes |
|:----:|-------|------:|:----:|:--:|:--:|:--:|:--:|:---------:|-------|-------|
| 1 | **`qwen2.5:0.5b`** | **5/5 (100%)** | 128.6s | ✅ | ✅ | ✅ | ✅ | ✅ | +1 | Perfect! Q5 fixed, 2x faster |
| 1 | **`qwen3:0.6b`** | **5/5 (100%)** | 417.3s | ✅ | ✅ | ✅ | ✅ | ✅ | +1 | Perfect! Up from 80% in R03.9 |
| 1 | **`granite4:350m`** | **5/5 (100%)** | 158.5s | ✅ | ✅ | ✅ | ✅ | ✅ | 0 | Still perfect; 1.85x faster |
| 4 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | **4/5 (80%)** | 139.8s | ✅ | ❌ 53 | ✅ | ✅ | ✅ | 0 | Q2 calc error (5.8s — skipped tool?) |
| 4 | `qwen2:0.5b` | **4/5 (80%)** | 117.9s | ✅ | ✅ | ✅ | ❌ code | ✅ | +1 | Q3/Q5 fixed; Q4 wrote Python but didn't execute |
| 6 | `qwen3.5:0.8b` | **2/5 (40%)** | 313.7s | ❌ empty | ❌ empty | ❌ empty | ✅ | ✅ | -1 | Regression; Q1-Q3 all empty |
| 7 | `gemma3:270m` | **1/5 (20%)** | 422.9s | ❌ 405 | ❌ 3 | ❌ literal | ✅ | ❌ empty | -1 | Regression; Q3 output literal `<the result>` |
| 8 | `nchapman/dolphin3.0-qwen2.5:0.5b` | **1/5 (20%)** | 155.6s | ❌ 84 | ❌ -3 | ✅ | ❌ empty | ❌ 6h | -2 | Regression; Q1 doubled, Q2 negative |
| 9 | `functiongemma:270m` | **0/5 (0%)** | 172.7s | ❌ expr | ❌ 35 | ❌ 4.0 | ❌ refused | ❌ refused | -1 | Refusals; Q2/Q3 wrong math despite calling tools |
| 10 | `qwen:0.5b` | **0/5 (0%)** | 214.0s | ❌ meta | ❌ 495 | ❌ 41 | ❌ 48 | ❌ 6h | -1 | Base model hallucinated reasoning, no tool use |

---

### OpenResponses Mode Results (R04.4 - openre API Mode, WITH SOUL)

> Testing with `--api openre --soul nova-helper` uses Ollama's native OpenResponses API (`/api/chat`) with the nova-helper soul persona
> Test params: `--api openre --soul nova-helper --timeout 999`
> ✅ **Complete** — All 10 models tested

| Rank | Model | Score | Time | Q1 | Q2 | Q3 | Q4 | Q5 | vs R03.9 | Notes |
|:----:|-------|------:|:----:|:--:|:--:|:--:|:--:|:---------:|-------|-------|
| 1 | **`nchapman/dolphin3.0-qwen2.5:0.5b`** | **5/5 (100%)** | 119.0s | ✅ | ✅ | ✅ | ✅ | ✅ | +3 | Massive improvement! Up from 2/5 |
| 1 | **`qwen2.5:0.5b`** | **5/5 (100%)** | 165.5s | ✅ | ✅ | ✅ | ✅ | ✅ | 0 | Still perfect; 1.5x faster |
| 1 | **`granite4:350m`** | **5/5 (100%)** | 160.3s | ✅ | ✅ | ✅ | ✅ | ✅ | 0 | Still perfect; 1.84x faster |
| 4 | `qwen3.5:0.8b` | **4/5 (80%)** | 321.0s | ✅ | ❌ 45 | ✅ | ✅ | ✅ | +1 | Improved! Q2 off-by-6, Q1 fixed |
| 4 | `qwen2:0.5b` | **4/5 (80%)** | 114.7s | ✅ | ✅ | ✅ | ✅ | ❌ 6.5h | +2 | Big improvement! Q3/Q4 fixed; Q5 reasoning error |
| 6 | `qwen3:0.6b` | **3/5 (60%)** | 229.6s | ✅ | ❌ 49 | ✅ | ✅ | ❌ 17 | -1 | Q5 regression (17 instead of 8) |
| 6 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | **3/5 (60%)** | 157.9s | ✅ | ❌ 53 | ✅ | ✅ | ❌ empty | -1 | Q2 same error; Q5 regression to empty |
| 8 | `gemma3:270m` | **2/5 (40%)** | 423.0s | ❌ 405 | ❌ 3 | ✅ | ✅ | ❌ empty | 0 | Same score; 1.37x faster; Q5 now empty |
| 8 | `qwen:0.5b` | **2/5 (40%)** | 250.8s | ❌ 38 | ✅ | ❌ 87.5 | ✅ | ❌ 24h | 0 | Same score; Q1-Q3 hallucinated math, no tool use |
| 10 | `functiongemma:270m` | **1/5 (20%)** | 168.7s | ✅ | ❌ expr | ❌ 1024 | ❌ refused | ❌ refused | 0 | Same score; Q2 showed expression, Q4/Q5 refused |

---

## Test 02 Tool Tests

> **Updated:** 2026-03-28 - R03.7 first results

Test 02 comprehensively evaluates tool calling across 6 categories. Phase 1 validates tools directly (no model). Phase 2 tests the model's ability to select, call, and interpret tools.

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
| All Tools | 4 | varies | Tool selection from full set |

---

### Phase 2 Results

> Test params: `--soul nova-helper --num-ctx 8192 --num-predict 512 --temp 0.1 --model-only --timeout 9999`

| Rank | Model | Score | Calc | Shell | DateTime | File | Repl | All Tools | Time | Tool Mode | Notes |
|:----:|-------|------:|:----:|:-----:|:--------:|:----:|:----:|:---------:|:----:|:---------:|-------|
| 1 | **`granite4:350m`** | **15/17 (88%)** | 5/5 | 2/2 | 2/2 | 1/2 | 2/2 | 3/4 | ~762s | native | Strong calculator/shell |

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

| Fix | Issue | Impact |
|-----|-------|--------|
| `numbers_match()` | `"12" != "12.0"` string comparison | Prevents false negatives on float results |
| `normalize_number` last-number | `"15 times 8 is 120"` extracted `15` (first) | Now correctly extracts `120` (last) |
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
| 1 | **`deepseek-r1:1.5b`** | **13/14 (93%)** | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 1/2 | 1/1 | 1/1 | 759.3s |
| 2 | `granite3.1-moe:1b` | **8/14 (57%)** | 1/2 | 2/2 | 1/2 | 1/2 | 0/2 | 1/2 | 1/1 | 1/1 | 369.7s |
| 3 | `nchapman/dolphin3.0-qwen2.5:0.5b` | **7/14 (50%)** | 2/2 | 0/2 | 1/2 | 1/2 | 0/2 | 2/2 | 1/1 | 0/1 | 212.8s |
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

### Soul Persona Impact Analysis

> **R03.3:** Soul personas dramatically improve small model performance

| Model | Params | Without Soul | With nova-helper | Improvement |
|-------|-------:|--------------|------------------|:-----------:|
| `qwen2:0.5b` | 500M | ~2/5 (40%) | **5/5 (100%)** | **+60%** |
| `qwen:0.5b` | 500M | 5/5 (221.7s) | **5/5 (96.0s)** | **2.3x faster** |
| `qwen2.5-coder:0.5b` | 494M | 5/5 (93.3s) | **5/5 (52.2s)** | **1.8x faster** |
| `qwen3:0.6b` | 600M | ~3/5 (60%) | **5/5 (100%)** | **+40%** |
| `gemma3:270m` | 270M | 4/5 (80%) | **5/5 (100%)** | **+20%** |
| `dolphin3.0-qwen2.5:0.5b` | 500M | 3/5 (60%) | **5/5 (100%)** | **+40%** |
| `qwen3.5:0.8b` | 800M | ~3/5 (60%) | **5/5 (100%)** | **+40%** |

---

## Soul Persona System

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
agentnova test 01 --soul nova-helper --num-ctx 16384 --api openai --timeout 9999 --debug
```

---

## Testing Tool Support Detection

```bash
# Test all models for native tool support
agentnova models --tool_support

# Results are saved to tested_models.json for future reference
```

Example output (R04.5 — 12 models):
```
⚛ AgentNova - Available Models
  Backend: http://localhost:11434
----------------------------------------------------------------------------------------------------------
  Name                                     Size       Context        openre        openai  Family
----------------------------------------------------------------------------------------------------------
  qwen:1.8b                              1.04 GB         32768       ○ react       ○ react  (qwen2)
  qwen2.5:1.5b                           0.92 GB         32768      ✓ native       ○ react  (qwen2)
  gemma3:270m                            0.27 GB         32768       ○ react       ○ react  (gemma3)
  functiongemma:270m                     0.28 GB         32768      ✓ native      ✓ native  (gemma3)
  granite4:350m                          0.66 GB         32768      ✓ native      ✓ native  (granite)
  qwen3.5:0.8b                           0.96 GB        262144       ○ react      ✓ native  (qwen35)
  qwen3:0.6b                             0.49 GB         40960      ✓ native       ○ react  (qwen3)
  qwen2.5:0.5b                           0.37 GB         32768      ✓ native      ✓ native  (qwen2)
  qwen2:0.5b                             0.33 GB         32768       ○ react       ○ react  (qwen2)
  qwen:0.5b                              0.37 GB         32768       ○ react       ○ react  (qwen2)
  nchapman/dolphin3.0-qwen2.5:0.5b       0.37 GB         32768       ○ react       ○ react  (qwen2)
  qwen2.5-coder:0.5b-instruct-q4_k_m     0.37 GB         32768       ○ react       ○ react  (qwen2)
----------------------------------------------------------------------------------------------------------
Total: 12 models

Legend: ✓ native (API tools) | ○ react (text parsing) | ✗ none (no tools) | ? untested
Context: Max context window from model API
Tool support columns show openre (OpenResponses) and openai (Chat-Completions) results.
Use --tool-support to test both API modes. --tool-support --api openai to test only Chat-Completions.
```