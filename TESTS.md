# ⚛️ AgentNova R04.5

## Test 01 Quick Diagnostic (5 Questions)

Test 01 is designed for rapid iteration and debugging. 5 targeted questions identify common failure modes quickly.

> **Updated:** 2026-04-04 - R04.5 OpenResponses (openre) with-soul results in progress (8/12 models)
> **Previous:** 2026-04-01 - R04.4 OpenResponses (openre) with-soul results complete (10/10 models)

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

### OpenResponses Mode Results (R04.5 - openre API Mode, WITH SOUL)

> Testing with `--api openre --soul nova-helper` uses Ollama's native OpenResponses API (`/api/chat`) with the nova-helper soul persona
> Test params: `--timeout 9999 --num-ctx 16768 --num-predict 256 --temp 0.1 --soul nova-helper`
> Environment: CPU-only Google Colab, 12GB RAM, Ollama
> ⏳ **Partial results** — 8 of 12 models tested; remaining 4 pending

| Rank | Model | Size | Score | Time | Q1 | Q2 | Q3 | Q4 | Q5 | vs R04.4 | Notes |
|:----:|-------|-----:|------:|:----:|:--:|:--:|:--:|:--:|:---------:|-------|-------|
| 1 | **`qwen2.5:1.5b`** | 0.92 GB | **5/5 (100%)** | 543.5s | ✅ | ✅ | ✅ | ✅ | ✅ | NEW | First 100% in openre for this model. ~18s/q warm. |
| 2 | `qwen2:0.5b` | 0.33 GB | **4/5 (80%)** | 200.8s | ✅ | ✅ | ✅ | ❌ text | ✅ | 0 | Q4 output reasoning text instead of answer. Same Q4 fail as qwen2.5:0.5b. |
| 2 | `qwen2.5:0.5b` | 0.37 GB | **4/5 (80%)** | 232.4s | ✅ | ✅ | ✅ | ❌ text | ✅ | -1 | Q4 output reasoning text instead of answer. Fastest 80%. |
| 2 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | 0.37 GB | **4/5 (80%)** | 306.7s | ✅ | ✅ | ✅ | ✅ | ❌ empty | +1 | Q5 empty. Coder overthinks some questions. |
| 2 | `qwen3:0.6b` | 0.49 GB | **4/5 (80%)** | 484.9s | ✅ | ✅ | ✅ | ✅ | ❌ 17h | +1 | Q2 fixed (was 49 in R04.4). Q5 persistent time calc error. 382s cold start. |
| 2 | `qwen3.5:0.8b` | 0.96 GB | **4/5 (80%)** | 652.9s | ✅ | ❌ 45 | ✅ | ✅ | ✅ | 0 | Same score as R04.4; exact same Q2 failure (got 45 vs 51). 2x slower (653s vs 321s). |
| 7 | `qwen:0.5b` | 0.37 GB | **1/5 (20%)** | 341.5s | ✅ | ❌ text | ❌ 68 | ❌ 24 | ❌ 24h | -1 | Regression; Q2-Q5 all verbose reasoning, no tool use. Base model too small. |

#### qwen2.5:1.5b Detailed Breakdown

| Question | Category | Expected | Got | Result | Time |
|----------|----------|:--------:|:----:|:------:|:----:|
| Q1 | Simple Math | — | — | ✅ | 473.0s |
| Q2 | Multi-step | — | — | ✅ | 17.4s |
| Q3 | Division | — | — | ✅ | 16.9s |
| Q4 | Word Problem | — | — | ✅ | 19.7s |
| Q5 | Time Calc | — | — | ✅ | 16.4s |

**Key Observations:**
- **473s cold start** on Q1 (model loading), then consistent ~17s per question when warm
- **Only model to achieve 5/5** in R04.5 openre testing so far — handles all question types including word problems and time calculations
- **Native tool caller** (openre) — successfully uses calculator tool for all questions
- **Complementary failures** with 0.5b variants: base model fails Q4 (formatting), coder fails Q5 (time calc), 1.5b handles both
- **2.3x slower** than qwen2.5:0.5b but 100% accurate vs 80% — clear accuracy/speed tradeoff

#### qwen3:0.6b Detailed Breakdown

| Question | Category | Expected | Got | Result | Time |
|----------|----------|:--------:|:----:|:------:|:----:|
| Q1 | Simple Math | — | — | ✅ | 382.0s |
| Q2 | Multi-step | — | — | ✅ | 28.8s |
| Q3 | Division | — | — | ✅ | 27.9s |
| Q4 | Word Problem | — | — | ✅ | 18.6s |
| Q5 | Time Calc | 8 | 17 hours | ❌ | 27.5s |

**Key Observations:**
- **382s cold start** on Q1 (model loading), then consistent ~26s per question when warm
- **Q2 fixed from R04.4** — previously got 49 (off-by-2), now passes cleanly (+1 improvement)
- **Q5 time calc remains persistent** — returns 17 hours instead of 8, same error as R04.4 and R03.9 (openre)
- **Thinking model behavior** — qwen3 uses `<think>` tags which are auto-disabled by model family detection; the ReAct path works reliably for Q1-Q4
- **2.1x slower** than R04.4 (485s vs 230s) — likely due to 382s Q1 cold start on Colab
- **Warm performance strong** — Q2-Q4 at 18-29s each, competitive with faster models

#### qwen:0.5b Detailed Breakdown

| Question | Category | Expected | Got | Result | Time |
|----------|----------|:--------:|:----:|:------:|:----:|
| Q1 | Simple Math | — | — | ✅ | 255.5s |
| Q2 | Multi-step | 51 | text | ❌ | 22.3s |
| Q3 | Division | 4.25 | 68 | ❌ | 15.4s |
| Q4 | Word Problem | 10 | 24 | ❌ | 27.3s |
| Q5 | Time Calc | 8 | 24h | ❌ | 21.0s |

**Key Observations:**
- **Regression from R04.4** — dropped from 2/5 (40%) to 1/5 (20%); Q2 and Q4 that passed in R04.4 now fail
- **No tool use on any question** — model outputs verbose reasoning text for all failures, never calls calculator
- **Q3 hallucinated multiplication** — computed `17 * 4 = 68` instead of `17 / 4 = 4.25`; fundamental math error
- **Q4 wrong operation** — did `Total - 8 + 6` instead of `Total - 8 - 6`, getting 24 instead of 10
- **Q5 persistent** — returns 24 hours, same wrong answer as R04.4
- **Base model too small** — the original `qwen:0.5b` (qwen2 base, not qwen2.5) lacks tool calling capability even with soul guidance
- **255s cold start** on Q1, then consistent ~21s per question when warm

#### Complementary Failure Analysis (R04.5)

| Question | qwen2.5:0.5b | qwen2.5-coder:0.5b | qwen2.5:1.5b | qwen3:0.6b | qwen:0.5b | Weakness |
|----------|:--:|:--:|:--:|:--:|:--:|----------|
| Q2 Multi-step | ✅ | ✅ | ✅ | ✅ | ❌ text | Base qwen:0.5b no tool use |
| Q3 Division | ✅ | ✅ | ✅ | ✅ | ❌ 68 | Base qwen:0.5b hallucinated multiply |
| Q4 Word Problem | ❌ text | ✅ | ✅ | ✅ | ❌ 24 | Both qwen:0.5b fail formatting |
| Q5 Time Calc | ✅ | ❌ empty | ✅ | ❌ 17h | ❌ 24h | Coder empty, qwen3/qwen:0.5b calc error |

> The qwen2.5:1.5b is the only model to clear all 5 questions. All other models fail at least one.

---

### BitNet Backend Results (R04.4 - openre API Mode, WITH SOUL)

> Testing with `--backend bitnet --soul nova-helper` uses the BitNet backend (`http://localhost:8765`) with OpenResponses API and the nova-helper soul persona
> Test params: `--backend bitnet --soul nova-helper --num-ctx 16384 --num-predict 128 --timeout 999 --temp 0.1`
> ✅ **Complete** — 1 model tested

| Rank | Model | Score | Time | Q1 | Q2 | Q3 | Q4 | Q5 | Notes |
|:----:|-------|------:|:----:|:--:|:--:|:--:|:--:|:---------:|-------|
| 1 | **`bitnet-b1.58-2B-4T`** | **4/5 (80%)** | 80.7s | ✅ | ✅ | ✅ | ✅ | ❌ -4 | First BitNet result! Q5 time calc error (expected 8, got -4) |

#### bitnet-b1.58-2B-4T Detailed Breakdown

| Question | Category | Expected | Got | Result | Time |
|----------|----------|:--------:|:----:|:------:|:----:|
| Q1 | Simple Math | — | — | ✅ | 15.6s |
| Q2 | Multi-step | — | — | ✅ | 16.1s |
| Q3 | Division | — | — | ✅ | 15.4s |
| Q4 | Word Problem | — | — | ✅ | 17.1s |
| Q5 | Time Calc | 8 | -4 | ❌ | 16.5s |

**Key Observations:**
- **Fastest aggregate time** — 80.7s total is the quickest of any model/backend combination tested, averaging just 16.1s per question
- **BitNet 1.58-bit quantization viable** — the 2B parameter model with ternary weights achieves 80% accuracy despite aggressive quantization
- **Consistent response latency** — very low variance across questions (15.4s–17.1s), suggesting stable inference performance
- **Q5 time calculation failure** — computed `-4` instead of `8`, indicating a sign error or subtraction order mistake in multi-step time arithmetic
- **Low `num-predict` tolerance** — test ran with only 128 max tokens per response, suggesting the model produces concise tool calls efficiently

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

### OpenResponses Mode Results (R03.9 - resp API Mode, WITH SOUL)

> Testing with `--api openre --soul nova-helper` uses Ollama's native OpenResponses API (`/api/chat`) with the nova-helper soul persona
> Test params: `--api openre --soul nova-helper --num-ctx 32768 --timeout 9999`
> ⏳ **Partial results** — 7 of 10 models tested; remaining 3 pending

| Rank | Model | Score | Time | Q1 | Q2 | Q3 | Q4 | Q5 | Notes |
|:----:|-------|------:|:----:|:--:|:--:|:--:|:--:|-------|-------|
| 1 | **`granite4:350m`** | **5/5 (100%)** | 295.1s | ✅ | ✅ | ✅ | ✅ | ✅ | Perfect score! Consistent across all modes |
| 1 | **`qwen2.5:0.5b`** | **5/5 (100%)** | 249.5s | ✅ | ✅ | ✅ | ✅ | ✅ | Reclaims 100%! Fastest perfect score in resp mode |
| 3 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | **4/5 (80%)** | 301.8s | ✅ | ✅ | ✅ | ✅ | ❌ empty | Q5 empty response |
| 4 | `nchapman/dolphin3.0-qwen2.5:0.5b` | **3/5 (60%)** | 224.4s | ✅ | ❌ 3 | ✅ | ✅ | ❌ 21 | Improved! Q2 off-by-48, Q5 wrong calc |
| 5 | `gemma3:270m` | **2/5 (40%)** | 578.7s | ❌ 405 | ❌ 3 | ✅ | ✅ | ❌ result | Regression; Q1/Q2/Q5 tool artifacts, very slow |
| 5 | `qwen2:0.5b` | **2/5 (40%)** | 286.0s | ✅ | ✅ | ❌ empty | ❌ text | ❌ text | Q3 empty, Q4/Q5 verbose wrong reasoning |
| 7 | `functiongemma:270m` | **1/5 (20%)** | 335.3s | ✅ | ❌ hall. | ❌ 1024 | ❌ refused | ❌ refused | Q2 hallucinated success, Q3 wrong calc, Q4/Q5 refusals |

---

### Chat Completions Mode Results (R03.9 - openai API Mode, WITH SOUL)

> Testing with `--api openai --soul nova-helper` uses OpenAI-compatible Chat Completions API (`/v1/chat/completions`) with the nova-helper soul persona
> Test params: `--api openai --soul nova-helper --num-ctx 32768 --timeout 9999`
> ✅ **Complete** — All 10 models tested

| Rank | Model | Score | Time | Q1 | Q2 | Q3 | Q4 | Q5 | Notes |
|:----:|-------|------:|:----:|:--:|:--:|:--:|:--:|-------|-------|
| 1 | **`granite4:350m`** | **5/5 (100%)** | 293.3s | ✅ | ✅ | ✅ | ✅ | ✅ | Perfect score! Consistent across all modes |
| 2 | `qwen2.5:0.5b` | **4/5 (80%)** | 260.9s | ✅ | ✅ | ✅ | ✅ | ❌ text | Q5 verbose explanation instead of numeric answer |
| 2 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | **4/5 (80%)** | 293.5s | ✅ | ✅ | ✅ | ✅ | ❌ empty | Q5 empty response; instruct quant variant |
| 2 | **`qwen3:0.6b`** | **4/5 (80%)** | 1140.6s | ✅ | ❌ 54 | ✅ | ✅ | ✅ | Q2 off-by-3 (got 54 vs 51); slow (1140s) |
| 5 | `nchapman/dolphin3.0-qwen2.5:0.5b` | **3/5 (60%)** | 203.0s | ✅ | ❌ 43 | ✅ | ✅ | ❌ 17h | Improved! Q2 off-by-one, Q5 reasoning error |
| 5 | `qwen2:0.5b` | **3/5 (60%)** | 256.6s | ✅ | ✅ | ❌ 3.5 | ✅ | ❌ 14h | Q3 division rounding, Q5 time calc error |
| 7 | `qwen3.5:0.8b` | **3/5 (60%)** | 552.2s | ❌ empty | ❌ empty | ✅ | ✅ | ✅ | Massive improvement! Q1/Q2 empty, Q3-Q5 all correct |
| 8 | `gemma3:270m` | **2/5 (40%)** | 613.2s | ❌ 405 | ❌ 3 | ✅ | ✅ | ❌ 1024 | Regression; Q1/Q2 wrong, very slow (613s) |
| 9 | `functiongemma:270m` | **1/5 (20%)** | 344.9s | ✅ | ❌ hall. | ❌ 120 | ❌ refused | ❌ refused | Q2 hallucinated success, Q3 wrong calc, Q4/Q5 refusals |
| 9 | `qwen:0.5b` | **1/5 (20%)** | 279.5s | ❌ 32 | ❌ 41 | ❌ 26 | ❌ 14 | ✅ | Base model too small; Q1-Q4 all wrong despite verbose reasoning |

---

### Chat Completions Mode Results (R03.9 - openai API Mode, NO SOUL)

> Testing with `--api openai` uses OpenAI-compatible Chat Completions API (`/v1/chat/completions`)
> Scores below reflect bare model capability without persona guidance. Not directly comparable to with-soul results.
> Test params: `--api openai` only (default settings, no soul)
> ⏳ **Partial results** — 9 of 10 models tested; remaining 1 pending

| Rank | Model | Score | Time | Q1 | Q2 | Q3 | Q4 | Q5 | Notes |
|:----:|-------|------:|:----:|:--:|:--:|:--:|:--:|-------|-------|
| 1 | **`granite4:350m`** | **5/5 (100%)** | 44.2s | ✅ | ✅ | ✅ | ✅ | ✅ | Perfect score! 4x faster (183 to 44s) |
| 2 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | **4/5 (80%)** | 99.9s | ✅ | ✅ | ✅ | ✅ | ❌ hall. | With --soul; 0/5 without — heavily soul-dependent |
| 3 | `nchapman/dolphin3.0-qwen2.5:0.5b` | **3/5 (60%)** | 31.6s | ✅ | ❌ 49 | ✅ | ✅ | ❌ 10 | Improved even without soul; Q2/Q5 reasoning |
| 3 | `qwen2:0.5b` | **3/5 (60%)** | 22.1s | ✅ | ✅ | ❌ 4.03% | ✅ | ❌ 6 | Stable; different failure pattern |
| 3 | `gemma3:270m` | **3/5 (60%)** | 14.8s | ✅ | ❌ Q1 bleed | ✅ | ✅ | ❌ 10 | Q2 context bleed (no soul isolation) |
| 6 | `qwen2.5:0.5b` | **2/5 (40%)** | 45.7s | ❌ empty | ✅ | ❌ empty | ✅ | ❌ text | Soul-dependent; likely recovers with --soul |
| 7 | `qwen3.5:0.8b` | **0/5 (0%)** | 91.0s | ❌ empty | ❌ empty | ❌ empty | ❌ empty | ❌ empty | All empty responses |
| 7 | `qwen3:0.6b` | **0/5 (0%)** | 138.4s | ❌ empty | ❌ empty | ❌ empty | ❌ empty | ❌ 6 | Soul-dependent; was 3/5 with soul |
| 7 | `qwen:0.5b` | **0/5 (0%)** | 37.3s | ❌ 32 | ❌ 10 | ❌ 10 | ❌ 8 | ❌ 42h | All wrong; base model too small |

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

#### granite4:350m Detailed Breakdown

**Calculator — 5/5 (100%)**

| Test | Prompt | Expected | Got | Tool Used | Steps | Time |
|------|--------|:--------:|:----:|:---------:|:-----:|:----:|
| Basic multiplication | What is 15 times 8? | 120 | 120 | yes | 2 | 164.6s |
| Power | What is 2 to the power of 10? | 1024 | 1024 | yes | 2 | 10.2s |
| Square root | What is the square root of 144? | 12 | 12 | yes | 2 | 10.5s |
| Complex expression | What is (10 + 5) times 3? | 45 | 45 | yes | 2 | 11.1s |
| Division | What is 100 divided by 4? | 25 | 25 | yes | 2 | 11.4s |

**Shell — 2/2 (100%)**

| Test | Prompt | Expected | Tool Used | Result Location | Time |
|------|--------|----------|:---------:|:---------------:|:----:|
| Echo test | Use shell to echo 'Hello AgentNova' | Hello AgentNova | yes | tool result | 95.1s |
| Current directory | What is the current working directory? | (any path) | yes | — | 7.7s |

> **Note:** Echo test passed via tool result fallback — model called shell correctly but hallucinated weather in the final answer instead of echoing the result.

**DateTime — 2/2 (100%)**

| Test | Prompt | Tool Used | Result Location | Time |
|------|--------|:---------:|:---------------:|:----:|
| Get date | What is today's date? | yes (get_date) | answer | 96.6s |
| Get time | What time is it? | yes (get_time) | answer | 11.8s |

**File Tools — 1/2 (50%)**

| Test | Prompt | Expected | Tool Used | Result | Time |
|------|--------|----------|:---------:|:-------:|:----:|
| Read file | Read the file at /tmp/.../test.txt | AgentNova | yes (read_file) | pass | 116.4s |
| List directory | List files in /tmp/.../tmpdir | test.txt | yes (list_directory) | fail | 195.0s |

> **Failure:** Model called `list_directory('/tmp')` instead of the full temp directory path `/tmp/tmp6ds0sx5i`. Listed parent directory contents which didn't contain `test.txt`.

**Python REPL — 2/2 (100%)**

| Test | Prompt | Expected | Got | Tool Used | Time |
|------|--------|:--------:|:----:|:---------:|:----:|
| Calculate power | Use Python to calculate 2 to the power of 20 | 1048576 | 1048576 | yes | 98.6s |
| Math with math module | Use Python to calculate the square root of 144 | 12 | 12.0 | yes | 12.3s |

> **Note:** Square root test validates the `numbers_match()` fix — tool returned `12.0` but expected `"12"`. Numeric comparison with tolerance correctly matched.

**All Tools — 3/4 (75%)**

| Test | Prompt | Expected Tool | Correct Tool | Expected Content | Result | Time |
|------|--------|:------------:|:------------:|:---------------:|:------:|:----:|
| Calculator choice | What is 25 times 4? | calculator | yes | 100 | pass | 229.1s |
| Shell choice | Echo the text 'MultiTool' | shell | no | MultiTool | fail | 13.8s |
| Date choice | What is today's date? | get_date | yes | (any date) | pass | 23.0s |
| File read choice | Read the file at /tmp/.../multi_test.txt | read_file | yes | Test content | pass | 20.3s |

> **Failure:** Shell choice — model didn't call any tool, responded with "I don't have enough context." This is a known issue with 350M parameter models when the prompt is vague.

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
agentnova test 01 --soul nova-helper --num-ctx 16384 --api comp --timeout 9999 --debug
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