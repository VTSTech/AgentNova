# ⚛️ AgentNova R01

## Test 07 Benchmark Results (15-Test Suite)

> ⚠️ **Note:** R01 tests were run concurrently (Test 07 on Colab + Test 14 GSM8K on Desktop sharing same Ollama instance). Timing values are **inflated** compared to dedicated single-test runs. Relative performance between models remains valid.

---

### Sub-1B Models (R01 - Current)

The following sub-1B parameter models were tested on the **15-test benchmark**:

| Rank | Model | Score | Time | Math | Reason | Know | Calc | Code | Δ vs Pre-R01 |
|:----:|-------|------:|-----:|:-----:|:------:|:----:|:----:|:----:|:------------:|
| 🥇 | **`qwen3:0.6b`** | **14/15 (93%)** | 556.3s | 3/3 ✅ | **3/3** ✅ | **3/3** ✅ | 3/3 ✅ | 2/3 | ↑ +93% |
| 🥈 | `granite4:350m` | 11/15 (73%) | 47.3s | 2/3 | 1/3 | 2/3 | 3/3 ✅ | 3/3 ✅ | = |
| 🥈 | `qwen2.5:0.5b` | 11/15 (73%) | 60.1s | 1/3 | 2/3 | 2/3 | 3/3 ✅ | 3/3 ✅ | ↑ +20% |
| 🥈 | `dolphin3.0-qwen2.5:0.5b` | 11/15 (73%) | **39.5s** | 1/3 | 2/3 | 3/3 ✅ | 2/3 | 3/3 ✅ | = |
| 5 | `gemma3:270m` | 8/15 (53%) | 30.6s | 3/3 ✅ | 1/3 | 1/3 | 0/3 ❌ | 3/3 ✅ | = |
| 6 | `functiongemma:270m` | 4/15 (27%) | 60.4s | 0/3 ❌ | 1/3 | 0/3 ❌ | 3/3 ✅ | 0/3 ❌ | ↑ +14% |

#### Category Champions (All Models R01)

| Category | 🏆 Champion | Score | Notes |
|----------|-------------|-------|-------|
| **Math** | `qwen3:0.6b` / `gemma3:270m` / `granite3.1-moe:1b` / `llama3.2:1b` | 3/3 | Tie - all perfect |
| **Reasoning** | **`qwen3:0.6b`** | **3/3** | 🌟 **ONLY model to pass all reasoning!** |
| **Knowledge** | `qwen3:0.6b` / `dolphin3.0-qwen2.5:0.5b` / `granite3.1-moe:1b` | 3/3 | Tie - all perfect |
| **Calc** | `qwen3:0.6b` / `granite3.1-moe:1b` / `llama3.2:1b` / `granite4:350m` / `qwen2.5:0.5b` / `functiongemma:270m` | 3/3 | Tie - all perfect |
| **Code** | `granite3.1-moe:1b` / `granite4:350m` / `qwen2.5:0.5b` / `gemma3:270m` / `dolphin3.0-qwen2.5:0.5b` / `llama3.2:1b` / `dolphin3.0-llama3:1b` | 3/3 | Tie - all perfect |

#### Key Findings (R01)

1. **TIE FOR CHAMPION!** - `qwen3:0.6b` (600M) and `granite3.1-moe:1b` (1B MoE) both achieve **93%**
2. **`granite3.1-moe:1b` is 4x faster** - same 93% accuracy but 142s vs 556s
3. **`qwen3:0.6b` is the ONLY model to pass all 3 reasoning tests**
4. **`qwen2.5:0.5b` achieves 90% GSM8K** - matches 1B models at half the parameters!
5. **MoE efficiency** - `granite3.1-moe:1b` proves MoE architecture excels at this benchmark
6. **Speed vs Accuracy tradeoff:**
   - `granite3.1-moe:1b`: 93% in 142s (fastest champion)
   - `qwen3:0.6b`: 93% in 556s (slowest champion)
   - `dolphin3.0-qwen2.5:0.5b`: 73% in 39.5s (fastest 73%)
7. **Tool support changes** - Several models changed tool support detection (dolphin, llama3.2)
8. **Native tool synthesis working** - qwen2.5:0.5b gets 3/3 Calc with AgentNova's synthesis

#### Tool Support (Sub-1B R01)

| Model | Params | Tool Support | Calc Score | Notes |
|-------|--------|--------------|------------|-------|
| `qwen3:0.6b` | 600M | ReAct | 3/3 ✅ | Excellent tool use |
| `qwen2.5:0.5b` | 500M | native | 3/3 ✅ | Works with synthesis fallback |
| `granite4:350m` | 350M | native | 3/3 ✅ | Excellent tool use |
| `functiongemma:270m` | 270M | native | 3/3 ✅ | Can use tools, can't reason |
| `dolphin3.0-qwen2.5:0.5b` | 500M | none | 2/3 | ⚠️ Was native pre-R01 |
| `gemma3:270m` | 270M | none | 0/3 ❌ | Can reason, can't use tools |

---

### 1B+ Models (R01 - Current)

| Rank | Model | Score | Time | Math | Reason | Know | Calc | Code | Δ vs Pre-R01 |
|:----:|-------|------:|-----:|:-----:|:------:|:----:|:----:|:----:|:------------:|
| 🥇 | **`granite3.1-moe:1b`** | **14/15 (93%)** | 142.3s | 3/3 ✅ | 2/3 | **3/3** ✅ | 3/3 ✅ | **3/3** ✅ | ↑ +13% |
| 🥇 | **`llama3.2:1b`** | **13/15 (87%)** | 283.2s | 3/3 ✅ | 2/3 | 2/3 | 3/3 ✅ | 3/3 ✅ | = |
| 3 | `tinydolphin:1.1b` | 10/15 (67%) | 450.2s | 1/3 | **2/3** | **3/3** ✅ | 1/3 | **3/3** ✅ | ↑ +7% |
| 4 | `nchapman/dolphin3.0-llama3:1b` | 7/15 (47%) | 76.0s | 1/3 | 1/3 | 2/3 | 0/3 ❌ | 3/3 ✅ | = |
| | *More results pending...* | | | | | | | | |

#### 🏆 TIE FOR CHAMPION!

| Model | Score | Time | Notes |
|-------|-------|------|-------|
| **`qwen3:0.6b`** | **93%** | 556.3s | Sub-1B champion, best reasoning |
| **`granite3.1-moe:1b`** | **93%** | **142.3s** ⚡ | 1B MoE, 4x faster! |

**`granite3.1-moe:1b` ties `qwen3:0.6b` at 93% but is 4x faster!**

#### Key Findings (1B+ R01)

1. **`granite3.1-moe:1b` surges to 93%** - improved from 80% with R01, ties for overall champion!
2. **MoE efficiency** - `granite3.1-moe:1b` achieves same 93% as `qwen3:0.6b` but 4x faster
3. **`llama3.2:1b` at 87%** - strong but now 3rd place overall
4. **`dolphin3.0-llama3:1b` unchanged** - 47%, no tool support, strong Code (3/3)

#### Tool Support (1B+ R01)

| Model | Params | Tool Support | Calc Score | Notes |
|-------|--------|--------------|------------|-------|
| `granite3.1-moe:1b` | 1B MoE | ReAct | 3/3 ✅ | Excellent via ReAct |
| `llama3.2:1b` | 1.2B | native | 3/3 ✅ | Was ReAct pre-R01 |
| `tinydolphin:1.1b` | 1.1B | none | 1/3 | Limited tool support |
| `dolphin3.0-llama3:1b` | 1B | none | 0/3 ❌ | No tool support |

---

### 1B+ Models (Pre-R01 - Historical)

*Results from R03.1.1 - will be updated with R01 tests shortly.*

| Rank | Model | Score | Time | Math | Reason | Know | Calc | Code |
|:----:|-------|------:|-----:|:-----:|:------:|:----:|:----:|:----:|
| 🥇 | **`llama3.2:1b`** | **13/15 (87%)** | 106.8s | 3/3 | 2/3 | 2/3 | 3/3 | 3/3 |
| 🥈 | `driaforall/tiny-agent-a:1.5b` | 13/15 (87%) | 136.5s | 3/3 | 2/3 | 2/3 | 3/3 | 3/3 |
| 🥉 | `granite3.1-moe:1b` | 12/15 (80%) | **89.4s** | 3/3 | 2/3 | 2/3 | 3/3 | 2/3 |
| 4 | `tinydolphin:1.1b` | 9/15 (60%) | 63.3s | 2/3 | 1/3 | 3/3 | 1/3 | 2/3 |
| 5 | `deepseek-coder:1.3b` | 9/15 (60%) | 111.3s | 2/3 | 1/3 | 1/3 | 2/3 | 3/3 |
| 6 | `tinyllama:1.1b` | 8/15 (53%) | 68.2s | 1/3 | 1/3 | 2/3 | 2/3 | 2/3 |
| 7 | `nchapman/dolphin3.0-llama3:1b` | 7/15 (47%) | **28.3s** | 1/3 | 1/3 | 1/3 | 1/3 | 3/3 |

#### Category Champions (1B+ Pre-R01)

| Category | 🏆 Champion | Score |
|----------|-------------|-------|
| **Math** | `granite3.1-moe:1b` | 3/3 |
| **Reasoning** | `granite3.1-moe:1b` | 2/3 |
| **Knowledge** | `tinydolphin:1.1b` | 3/3 |
| **Calc** | `llama3.2:1b` | 3/3 |
| **Code** | `nchapman/dolphin3.0-llama3:1b` | 3/3 |

**Key Findings:**
1. **`llama3.2:1b` is the best 1B model** - ties on score with `tiny-agent-a:1.5b` but 30s faster
2. **`granite3.1-moe:1b` wins Math + Reasoning** - fastest among top 3 (89.4s)
3. **`nchapman/dolphin3.0-llama3:1b` is fastest overall** (28.3s) but lowest score - good for Code only
4. **`tinydolphin:1.1b` surprises** - Knowledge champion despite 60% overall

#### Tool Support (1B+ Models)

| Model | Tool Support | Notes |
|-------|--------------|-------|
| `llama3.2:1b` | ReAct | Text-based tool calling |
| `driaforall/tiny-agent-a:1.5b` | ReAct (text JSON) | Outputs JSON as text |
| `granite3.1-moe:1b` | ReAct (text JSON) | Outputs JSON as text |
| `tinydolphin:1.1b` | none | No tool support |
| `deepseek-coder:1.3b` | none | Modelfile missing tool info |
| `tinyllama:1.1b` | none | No tool support |
| `nchapman/dolphin3.0-llama3:1b` | none | No tool support |

---

## GSM8K Benchmark Results

The following models have been tested on a **50-question GSM8K-style benchmark** using the Agent system with tool support detection.

> ⚠️ **Note:** R01 GSM8K tests were run concurrently with Test 07. Timing values are **inflated**.

---

### GSM8K Sub-1B Models (R01 - Current)

| Rank | Model | Score | Accuracy | Time | Tool Support | Δ vs Pre-R01 |
|:----:|-------|------:|--------:|-----:|--------------|:------------:|
| 🥇 | **`qwen2.5:0.5b`** | **45/50** | **90.0%** | 2772.2s | native | ↑ +18% |
| 🥈 | `granite4:350m` | 39/50 | 78.0% | 787.6s | native | ↑ +32% |
| 🥉 | `gemma3:270m` | 31/50 | 62.0% | 242.6s | none | = |
| | *More results pending...* | | | | | |

#### Key Findings (GSM8K R01)

1. **`qwen2.5:0.5b` achieves 90%** - matches `llama3.2:1b` at half the parameters!
2. **R01 native synthesis massive improvement** - 72% → 90% (+18%)
3. **`granite4:350m` improved 46% → 78%** - also huge gains
4. **Sub-500M models now competitive with 1B models** on GSM8K math

---

### GSM8K Sub-1B Models (Pre-R01 - Historical)

*Results from R03.1.0 - kept for reference until R01 tests complete.*

#### Modelfile Prompts (auto-detected tool support)

| Rank | Model | Score | Accuracy | Avg Time | Tool Support | Notes |
|:----:|-------|------:|--------:|--------:|--------------|-------|
| 🥇 | **`nchapman/dolphin3.0-qwen2.5:0.5b`** | **39/50** | **78.0%** | 8.9s | native | 🏆 **Best with native tools!** |
| 🥈 | `qwen2.5:0.5b` | 36/50 | 72.0% | 19.3s | native | Strong performer |
| 🥉 | `gemma3:270m` | 31/50 | 62.0% | **2.7s** | none | ⚡ **Fastest!** Pure reasoning |
| 4 | `granite4:350m` | 23/50 | 46.0% | 23.4s | native | Struggles with native tools |
| 5 | `functiongemma:270m` | 19/50 | 38.0% | 9.6s | native | Designed for tools but underperforms |
| 6 | `qwen3:0.6b` | 4/50 | 8.0% | 27.5s | react | ⚠️ Poor performance |

#### With `--force-react` (text-based ReAct prompting)

| Rank | Model | Score | Accuracy | Avg Time | Tool Support | Notes |
|:----:|-------|------:|--------:|--------:|--------------|-------|
| 🥇 | **`qwen2.5:0.5b`** | **42/50** | **84.0%** | 19.0s | native | 🏆 **Best overall!** |
| 🥈 | `granite4:350m` | 38/50 | 76.0% | 20.1s | native | **+30% vs native mode!** |
| 🥉 | `nchapman/dolphin3.0-qwen2.5:0.5b` | 33/50 | 66.0% | 10.2s | native | Faster but lower accuracy |
| 4 | `gemma3:270m` | 29/50 | 58.0% | **3.2s** | none | Pure reasoning, fast |
| 5 | `functiongemma:270m` | 20/50 | 40.0% | 28.2s | native | Slow, low accuracy |
| 6 | `qwen3:0.6b` | 10/50 | 20.0% | 42.0s | react | Still poor but +12% |

#### GSM8K Mode Comparison

| Model | Modelfile | ReAct | Δ Score | Δ Accuracy | Better Mode |
|-------|-----------|-------|---------|------------|-------------|
| `qwen2.5:0.5b` | 36/50 (72%) | **42/50 (84%)** | +6 | **+12%** | **ReAct** |
| `granite4:350m` | 23/50 (46%) | **38/50 (76%)** | +15 | **+30%** | **ReAct** |
| `dolphin3.0-qwen2.5:0.5b` | **39/50 (78%)** | 33/50 (66%) | -6 | -12% | **Modelfile** |
| `gemma3:270m` | **31/50 (62%)** | 29/50 (58%) | -2 | -4% | **Modelfile** |
| `functiongemma:270m` | 19/50 (38%) | 20/50 (40%) | +1 | +2% | Tie |
| `qwen3:0.6b` | 4/50 (8%) | **10/50 (20%)** | +6 | +12% | ReAct (still bad) |

**Key Findings:**
1. **`granite4:350m` improves 30% with ReAct** - biggest winner (46% → 76%)
2. **`qwen2.5:0.5b` improves 12% with ReAct** - becomes top performer (84%)
3. **`dolphin3.0-qwen2.5:0.5b` drops 12% with ReAct** - better with native tools
4. **`gemma3:270m` slightly worse with ReAct** - pure reasoning is optimal (no tool overhead)

---

### GSM8K 1B+ Models (Pre-R01 - Historical)

*Results from R03.1.1 - will be updated with R01 tests shortly.*

| Rank | Model | Score | Accuracy | Avg Time | Tool Support | Notes |
|:----:|-------|------:|--------:|--------:|--------------|-------|
| 🥇 | **`llama3.2:1b`** | **45/50** | **90.0%** | 12.7s | ReAct | 🏆 **Best 1B model!** |
| 🥈 | `nchapman/dolphin3.0-llama3:1b` | 35/50 | 70.0% | **5.9s** | none | ⚡ **Fastest!** Good accuracy |
| 🥉 | `granite3.1-moe:1b` | 34/50 | 68.0% | 13.4s | ReAct (text JSON) | Solid MoE performer |
| 4 | `tinydolphin:1.1b` | 11/50 | 22.0% | 10.8s | none | Weak math reasoning |
| 5 | `tinyllama:1.1b` | 5/50 | 10.0% | 12.0s | none | Poor performance |
| 6 | `deepseek-coder:1.3b` | 4/50 | 8.0% | 23.3s | none | ❌ Catastrophic failure |

**Key Findings (1B+ GSM8K):**
1. **`llama3.2:1b` dominates** - 90% accuracy, clear winner among 1B+ models
2. **`dolphin3.0-llama3:1b` is fastest** (5.9s) with solid 70% accuracy
3. **`granite3.1-moe:1b` consistent** - 68% matches its 15-test performance (80%)
4. **`deepseek-coder:1.3b` fails** - Despite 60% on 15-test, only 8% on GSM8K math
5. **Tiny models struggle** - Both tinydolphin and tinyllama under 25%

#### 1B+ vs Sub-1B Comparison (GSM8K Pre-R01)

| Rank | Model | Params | Accuracy | Avg Time |
|:----:|-------|-------:|--------:|--------:|
| 🥇 | **`llama3.2:1b`** | 1.2B | **90.0%** | 12.7s |
| 🥈 | `qwen2.5:0.5b` + ReAct | 494M | 84.0% | 19.0s |
| 🥉 | `dolphin3.0-qwen2.5:0.5b` | 494M | 78.0% | 8.9s |
| 4 | `granite4:350m` + ReAct | 350M | 76.0% | 20.1s |
| 5 | `dolphin3.0-llama3:1b` | 1B | 70.0% | **5.9s** |
| 6 | `granite3.1-moe:1b` | 1B MoE | 68.0% | 13.4s |
| 7 | `gemma3:270m` | 270M | 62.0% | 2.7s |

**Insight**: `llama3.2:1b` at 90% outperforms all sub-500M models, but `dolphin3.0-qwen2.5:0.5b` (78%) and `qwen2.5:0.5b` + ReAct (84%) are competitive at half the size.

---

### Key Findings

#### 1. Dolphin Fine-tunes Excel at Tool Calling

| Model | Score | Time | vs Base Model |
|-------|-------|------|---------------|
| `dolphin3.0-qwen2.5:0.5b` | **78%** | 8.9s | — |
| `qwen2.5:0.5b` (base) | 72% | 19.3s | +6% faster, 2x speed |

**Insight**: Dolphin fine-tunes not only improve accuracy but also **halve inference time**.

#### 2. Models Without Tool Support Can Still Perform Well

| Model | Tool Support | Score | Method |
|-------|--------------|-------|--------|
| `gemma3:270m` | **none** | **62%** | Pure reasoning prompt |
| `gemma3:270m` (old) | none | 4% | Wrong prompt (mentioned tools) |

**Insight**: The new `MATH_SYSTEM_PROMPT_NO_TOOLS` improved gemma3:270m from **4% → 62%** (+58%) by removing tool references that confused the model.

#### 3. FunctionGemma Paradox

| Model | Designed For | Tool Support | Score |
|-------|--------------|--------------|-------|
| `functiongemma:270m` | Function calling | native | 38% |
| `gemma3:270m` | General use | none | **62%** |

**Insight**: `functiongemma` is designed for tool calling but underperforms its base model `gemma3` when tools are used. The base model using **pure reasoning** outperforms it!

#### 4. Qwen3 is the Sub-1B Champion (R01 Update)

| Model | Params | Tool Support | Test 07 Score | Time |
|-------|--------|--------------|---------------|------|
| **`qwen3:0.6b`** | 600M | native | **93% (14/15)** | 556.3s |
| `qwen2.5:0.5b` | 500M | native | 73% (11/15) | 60.1s |

**Insight**: `qwen3:0.6b` is the **new sub-1B champion** with 93% accuracy! It's the ONLY model to:
- Pass all 3 reasoning tests (Apples, Sequence, Logic)
- Correctly identify Brasília as Brazil's capital
- Achieve near-perfect scores across Math, Reasoning, Knowledge, and Calc

**Note**: Earlier tests showed poor performance due to configuration issues. With R01 fixes, qwen3:0.6b now excels.

---

### Tool Support Impact

| Model | Tool Support | Prompt Used | Score |
|-------|--------------|-------------|-------|
| `gemma3:270m` | none | `MATH_SYSTEM_PROMPT_NO_TOOLS` | **62%** |
| `granite4:350m` | native | Standard + tools | 46% |
| `functiongemma:270m` | native | Standard + tools | 38% |

**Key Insight**: For sub-500M models, **not using tools** often outperforms native tool calling!

---

## Previous Benchmark: Native Tools (Pre-R03.1.0)

*These results used custom system prompts instead of Modelfile prompts.*

| Rank | Model | Score | Accuracy | Avg Time | Notes |
|:----:|-------|------:|--------:|--------:|-------|
| 🥇 | `nchapman/dolphin3.0-qwen2.5:0.5b` | 34/50 | 68.0% | 4.7s | Best native tool caller |
| 🥈 | `qwen2.5:0.5b` | 33/50 | 66.0% | 13.6s | Strong performer |
| 🥉 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | 25/50 | 50.0% | 12.6s | Good but slower |
| 4 | `nchapman/dolphin3.0-llama3:1b` | 21/50 | 42.0% | 5.6s | Fast inference |
| 5 | `granite4:350m` | 20/50 | 40.0% | 22.5s | Struggles with native tools |
| 6 | `gemma3:270m` | 3/50 | 6.0% | 0.8s | Wrong prompt (mentioned tools) |

---

## Previous Benchmark: With `--force-react` (Text-based ReAct)

| Rank | Model | Score | Time | Avg/Question | Notes |
|:----:|-------|------:|-----:|-------------:|-------|
| 🥇 | **`driaforall/tiny-agent-a:1.5b`** | **47/50 (94%)** | 1470s | ~29s | **Top performer!** |
| 🥈 | `granite4:350m` | 41/50 (82%) | 960s | ~19s | **Best sub-500M!** |
| 🥉 | `nchapman/dolphin3.0-llama3:1b` | 33/50 (66%) | 847s | ~17s | Good reasoning |
| 4 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | 28/50 (56%) | 671s | ~13s | ⚠️ Timed out |

---

## Tested Small Models (≤1.5B parameters)

The following models have been tested with a **15-test benchmark** (3 tests per category: Math, Reasoning, Knowledge, Calc Tool, Code).

### Rankings (R03.1.0 - Updated)

#### Modelfile Prompts (auto-detected tool support)

| Rank | Model | Score | Time | Math | Reason | Know | Calc | Code |
|:----:|-------|------:|-----:|:----:|:------:|:----:|:----:|:----:|
| 🥇 | `nchapman/dolphin3.0-qwen2.5:0.5b` | **11/15 (73%)** | **27.1s** | 1/3 | **2/3** | **3/3** | 2/3 | **3/3** |
| 🥈 | `granite4:350m` | **11/15 (73%)** | 78.4s | 1/3 | 2/3 | 2/3 | **3/3** | 3/3 |
| 🥉 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | 9/15 (60%) | 121.7s | 1/3 | 2/3 | 2/3 | 2/3 | 2/3 |
| 4 | `gemma3:270m` | 8/15 (53%) | **22.8s** | **3/3** | 1/3 | 1/3 | 0/3 | **3/3** |
| 5 | `qwen2.5:0.5b` | 8/15 (53%) | 61.0s | 1/3 | 2/3 | 2/3 | 1/3 | 2/3 |
| 6 | `functiongemma:270m` | 2/15 (13%) | 55.1s | 0/3 | 0/3 | 0/3 | 0/3 | 2/3 |
| 7 | `qwen3:0.6b` | 0/15 (0%) | 197.0s | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |

#### With `--force-react` (text-based ReAct prompting)

| Rank | Model | Score | Time | Math | Reason | Know | Calc | Code |
|:----:|-------|------:|-----:|:----:|:------:|:----:|:----:|:----:|
| 🥇 | `nchapman/dolphin3.0-qwen2.5:0.5b` | **11/15 (73%)** | **24.4s** | 1/3 | **2/3** | **3/3** | 2/3 | **3/3** |
| 🥈 | `granite4:350m` | **11/15 (73%)** | 75.6s | 2/3 | 1/3 | 2/3 | **3/3** | **3/3** |
| 🥉 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | 9/15 (60%) | 111.6s | 1/3 | 2/3 | 2/3 | 2/3 | 2/3 |
| 4 | `gemma3:270m` | 8/15 (53%) | 29.4s | **3/3** | 1/3 | 1/3 | 0/3 | 2/3 |
| 5 | `qwen2.5:0.5b` | 8/15 (53%) | 54.5s | 1/3 | 2/3 | 2/3 | 1/3 | 2/3 |
| 6 | `functiongemma:270m` | 2/15 (13%) | 56.1s | 0/3 | 0/3 | 0/3 | 0/3 | 2/3 |
| 7 | `qwen3:0.6b` | 0/15 (0%) | 199.2s | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |

### Mode Comparison: Modelfile vs --force-react

| Model | Modelfile | ReAct | Δ Score | Δ Time | Better Mode |
|-------|-----------|-------|---------|--------|-------------|
| `dolphin3.0-qwen2.5:0.5b` | 11/15, 27.1s | 11/15, 24.4s | 0 | **-2.7s** | ReAct (faster) |
| `granite4:350m` | 11/15, 78.4s | 11/15, 75.6s | 0 | **-2.8s** | ReAct (faster) |
| `qwen2.5-coder:0.5b` | 9/15, 121.7s | 9/15, 111.6s | 0 | **-10.1s** | ReAct (faster) |
| `gemma3:270m` | 8/15, 22.8s | 8/15, 29.4s | 0 | +6.6s | Modelfile (faster) |
| `qwen2.5:0.5b` | 8/15, 61.0s | 8/15, 54.5s | 0 | **-6.5s** | ReAct (faster) |
| `functiongemma:270m` | 2/15, 55.1s | 2/15, 56.1s | 0 | +1.0s | Tie |
| `qwen3:0.6b` | 0/15, 197.0s | 0/15, 199.2s | 0 | +2.2s | Both fail |

**Key Finding:** `--force-react` is faster for most models, except `gemma3:270m` which doesn't support tools (ReAct adds unnecessary overhead).

### Category Champions

| Category | 🏆 Champion (Modelfile) | 🏆 Champion (ReAct) |
|----------|-------------------------|---------------------|
| **Math** | `gemma3:270m` (3/3) | `gemma3:270m` (3/3) |
| **Reasoning** | `dolphin3.0-qwen2.5:0.5b` (2/3) | `dolphin3.0-qwen2.5:0.5b` (2/3) |
| **Knowledge** | `dolphin3.0-qwen2.5:0.5b` (3/3) | `dolphin3.0-qwen2.5:0.5b` (3/3) |
| **Calc** | `granite4:350m` (3/3) | `granite4:350m` (3/3) |
| **Code** | `gemma3:270m` (3/3) | `dolphin3.0-qwen2.5:0.5b` (3/3) |

### Previous Rankings (Pre-R03.1.0)

*These results used different system prompts and tool detection logic.*

| Rank | Model | Score | Time | Math | Reason | Know | Calc | Code |
|:----:|-------|------:|-----:|:----:|:------:|:----:|:----:|:----:|
| 🥇 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | **14/15 (93%)** | ~80s | **3/3** | 2/3 | 2/3 | **3/3** | **3/3** |
| 🥈 | **`BitNet-b1.58-2B-4T`** (BitNet) | **13/15 (87%)** | ~394s | **3/3** | 2/3 | 2/3 | **3/3** | **3/3** |
| 🥉 | `granite3.1-moe:1b` | **12/15 (80%)** | ~60s | **3/3** | 2/3 | **3/3** | 1/3 | **3/3** |
| 4 | `llama3.2:1b` | **12/15 (80%)** | ~600s | **3/3** | 1/3 | 2/3 | **3/3** | **3/3** |
| 5 | `qwen2-math:1.5b` | 12/15 (80%) | ~611s | **3/3** | **3/3** | **3/3** | ❌ | **3/3** |
| 6 | `gemma3:270m` | 10/15 (67%) | ~75s | **3/3** | 1/3 | 1/3 | 2/3 | **3/3** |
| 7 | `qwen2.5:0.5b` | 10/15 (67%) | ~107s | 1/3 | **3/3** | **3/3** | 0/3 | **3/3** |
| 8 | `qwen3:0.6b` | ~9/12 | ~130s | 2/3 | **3/3** | **3/3** | 0/3 | — |
| 9 | `tinyllama:latest` | 9/15 (60%) | ~587s | 2/3 | 2/3 | **3/3** | 0/3 | 2/3 |
| 10 | `granite4:350m` | 8/15 (53%) | ~97s | 2/3 | 1/3 | 2/3 | 0/3 | **3/3** |
| 11 | `smollm:135m` | 7/15 (47%) | ~285s | 0/3 | 2/3 | 2/3 | 0/3 | **3/3** |
| 12 | `functiongemma:270m` | 1/15 (7%) | ~90s | 0/3 | 0/3 | 0/3 | 0/3 | 1/3 |

---

## BitNet Benchmark Results

AgentNova has been tested with **Microsoft BitNet-b1.58-2B-4T** — a 2B parameter model with 1.58-bit ternary weights.

### Test Results Summary

| Test Suite | Score | Time | Notes |
|------------|-------|------|-------|
| **Model Comparison** (15 tests) | **13/15 (87%)** | 394s | 5 categories |
| **Robust Comparison** (22 tests) | **19/22 (86%)** | ~6min | Incremental save |
| **Comprehensive Test** (7 tests) | **6/7 (86%)** | ~90s | Basic + Reasoning + Code |

### Category Breakdown

| Category | Score | Pass Rate |
|----------|-------|-----------|
| **Math** | 3/3 | 100% ✅ |
| **Code** | 3/3 | 100% ✅ |
| **Calc (with tools)** | 3/3 | 100% ✅ |
| **Reasoning** | 2/3 | 67% |
| **Knowledge** | 2/3 | 67% |

### BitNet vs Ollama Small Models

| Rank | Model | Score | Params | Backend |
|:----:|-------|------:|-------:|---------|
| 🥇 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | 14/15 (93%) | 494M | Ollama |
| 🥈 | **`BitNet-b1.58-2B-4T`** | **13/15 (87%)** | **2B** | **BitNet** |
| 🥉 | `granite3.1-moe:1b` | 12/15 (80%) | 1B MoE | Ollama |
| 4 | `llama3.2:1b` | 12/15 (80%) | 1.2B | Ollama |

---

## Recommendations

| Use Case | Recommended Model | Why |
|----------|-------------------|-----|
| **🏆 BEST OVERALL (tie)** | **`qwen3:0.6b`** / **`granite3.1-moe:1b`** | Both **93%** - choose based on speed needs |
| **Best Speed + Accuracy** | **`granite3.1-moe:1b`** | **93% in 142s** - 4x faster than qwen3! |
| **Best Reasoning** | **`qwen3:0.6b`** | 🌟 **ONLY model to pass all 3 reasoning tests!** |
| **Best GSM8K** | **`qwen2.5:0.5b`** | **90% GSM8K** - matches 1B at half the size! |
| **Best 1B Dense** | `llama3.2:1b` | **87%**, native tools, 128k context |
| **Best Sub-500M** | `qwen2.5:0.5b` | **90% GSM8K**, 73% test 07 |
| **Best Speed (73%+)** | `dolphin3.0-qwen2.5:0.5b` | **39.5s**, 73% accuracy |
| **Best Speed (sub-500M)** | `gemma3:270m` | **30.6s**, pure reasoning |
| **Large context** | `llama3.2:1b` | **128k context window** |
| **CPU-only** | `BitNet-b1.58-2B-4T` | Efficient ternary weights |

### Mode Recommendations by Model

| Model | Recommended Mode | Reason |
|-------|------------------|--------|
| **`qwen3:0.6b`** | ReAct | 🏆 **Co-champion!** 93% accuracy, best reasoning |
| **`granite3.1-moe:1b`** | ReAct | 🏆 **Co-champion!** 93% in 142s, fastest champion |
| **`qwen2.5:0.5b`** | Native | 🎯 **90% GSM8K** - matches 1B at half size! |
| **`llama3.2:1b`** | Native | Now supports native tools, 87% |
| `granite4:350m` | Native | 78% GSM8K, 73% test 07, excellent native tools |
| `dolphin3.0-qwen2.5:0.5b` | None | Tool support changed to none, 73% pure reasoning |
| `gemma3:270m` | None | Cannot use tools, pure reasoning works best |
| `functiongemma:270m` | Native | Can use tools but can't reason directly (27%) |

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
⚛️ AgentNova R00 Models
  Model                                      Family       Context    Tool Support
  ──────────────────────────────────────────────────────────────────────────────
  gemma3:270m                                gemma3       32K        ○ none
  granite4:350m                              granite      32K        ✓ native
  qwen2.5:0.5b                               qwen2        32K        ✓ native
  qwen3:0.6b                                 qwen3        32K        ReAct
  dolphin3.0-qwen2.5:0.5b                    qwen2        32K        ✓ native
```
