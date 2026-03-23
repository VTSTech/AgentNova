# Changelog

All notable changes to AgentNova will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [R02.5] - 2026-03-22 10:49:35 PM

### 📦 Module Refactoring

Major code reorganization for improved maintainability. The monolithic `agent.py` (~2770 lines) has been split into focused single-responsibility modules.

### Added
- **`core/types.py`** - Type aliases (`StepResultType`)
- **`core/models.py`** - Dataclasses (`StepResult`, `AgentRun`) extracted from agent.py
- **`core/prompts.py`** - Few-shot prompts, tool arg aliases, platform constants
- **`core/helpers.py`** - Pure utility functions (no external dependencies)
- **`core/args_normal.py`** - Argument normalization for small model hallucinations
- **`core/tool_parse.py`** - ReAct/JSON parsing, fuzzy tool name matching

### Changed
- **`core/agent.py`** reduced from ~2770 to ~1550 lines
- **Clear dependency graph** - modules import from lower-level modules only
- **Backward compatible** - `from agentnova import Agent, AgentRun, StepResult` still works

### Module Dependency Graph

```
types.py        ← (no dependencies)
models.py       ← types
prompts.py      ← (no dependencies)
helpers.py      ← (no dependencies)
args_normal.py  ← prompts, helpers
tool_parse.py   ← helpers
agent.py        ← ALL above + tools, memory, ollama_client
```

### Benefits
- Each module has a single responsibility
- Easier to test individual components
- Reduced cognitive load when reading/modifying
- All modules remain **zero-dependency** (stdlib only)

---

## [R02.4] - 2026-03-22 3:20:14 PM

### 🔢 Multi-Step Calculation Handling

The synthesis logic has been simplified to always return numeric results directly. Previous attempts to detect and auto-complete incomplete multi-step calculations caused issues when models correctly computed full expressions in a single calculator call.

### Changed
- **Simplified numeric result handling** - All numeric results are now returned directly without LLM synthesis

### Rationale
When a model computes `8 * 7 - 5 = 51` as a single expression, we can't tell from the result alone whether:
1. The model did the full calculation (correct), OR
2. The model only did `8 * 7 = 56` (incomplete)

Auto-completing based on question text causes double-subtraction errors. Returning the numeric result directly is safer.

---

## [R02.3] - 2026-03-22 1:26:41 AM

### 🐛 Critical Fixes: ReAct Mode

Multiple critical bugs fixed that were causing ReAct-mode and thinking-capable models to fail.

### 🎯 Gemma Family Improvements (2026-03-22)

Family-specific optimizations for Google's Gemma models with improved pure reasoning support.

### Added
- **`no_tools_system_prompt` field** in `ModelFamilyConfig` - Allows family-specific prompts for models without tool support
  - Models with `tool_support=none` now get optimized pure reasoning prompts
  - Eliminates confusing tool references that degrade small model performance
- **`get_no_tools_system_prompt()` helper** - Returns family-specific prompt override
- **Optimized gemma3 prompt** for 270M parameter model:
  - Simplified format for small model comprehension
  - Explicit examples for multi-step calculations and word problems
  - No code blocks - just arithmetic output

### Fixed
- **functiongemma:270m tool support detection** - Was incorrectly defaulting to ReAct mode
  - Now correctly detected as `native` tool support
  - Improved from 0% (broken) to 80% (4/5)
- **Test state carryover** - Created fresh `OllamaClient` per question to avoid KV cache pollution

### Impact

| Model | Before | After | Change |
|-------|--------|-------|--------|
| **gemma3:270m** | 2/5 (40%) | 3/5 (60%) | **+50%** |
| **functiongemma:270m** | 0/5 (0%) | 4/5 (80%) | **Fixed** |

### Technical Details
- `gemma3:270m` has no tool support - pure reasoning is optimal
- `functiongemma:270m` has native tool support via Ollama API
- Both models report `family=gemma3` from Ollama API, but have different capabilities
- The `no_tools_system_prompt` provides arithmetic-focused examples instead of tool references

### 🐬 Dolphin Family Detection (2026-03-22)

Dolphin fine-tunes are now detected as a unified family regardless of their base model.

### Added
- **Dolphin family detection** in `get_model_family()` - Checks model name for "dolphin" before API family
  - `nchapman/dolphin3.0-llama3:1b` → `dolphin` (not `llama`)
  - `nchapman/dolphin3.0-qwen2.5:0.5b` → `dolphin` (not `qwen2`)
  - `tinydolphin:1.1b` → `dolphin` (not `llama`)

### Changed
- **Dolphin family config** updated to reflect reality:
  - `tool_format="none"` - Dolphin fine-tunes lose tool support from base models
  - `supports_native_tools=False` - No native tool calling
  - Added `no_tools_system_prompt` with Dolphin-specific examples
  - All Dolphin models share ChatML template (`<|im_start|>`, `<|im_end|>`)

### Technical Details
- Dolphin models share the same template regardless of base model (llama, qwen2, etc.)
- The fine-tuning process removes native tool support
- Internal family name "dolphin" unifies handling across all Dolphin variants

---

## [R02.2] - 2026-03-21 8:29:46 PM

### Fixed
- **ReAct models now always get `_use_few_shot=True`** - Previously, the `prefers_few_shot=False` setting in model family config (e.g., qwen2) was incorrectly applied to ReAct mode, causing models to output malformed Action/Action Input lines
  - Added explicit override in `agent.py`: `if self._tool_support == "react" and self.tools.all(): self._use_few_shot = True`
- **Observation now uses correct message role** - Tool results were being added as `assistant` messages instead of `user` messages, causing models to ignore the Observation content
  - Changed `self.memory.add_assistant(observation)` to `self.memory.add_user(observation)`
- **ReAct loop limit enforcement** - The loop limit checks were missing from the ReAct text-parsing path, allowing infinite loops
  - Added limit check after tool call count increment in ReAct path
- **Thinking mode disabled via API for qwen3** - Qwen3 was returning empty content because thinking mode is enabled by default
  - Added `think` parameter support to `ollama_client.chat()` 
  - Pass `think=False` for models with `needs_think_directive=True` (qwen3, deepseek-r1, etc.)
  - This uses Ollama's native API support instead of prompt-based workaround
- **Qwen3.5 config corrected** - Qwen3.5 has a simple template without thinking mode, unlike Qwen3
  - Set `needs_think_directive=False` for qwen35 family
- **Tool support caching** - `agentnova models --tool_support` now skips already-tested models
  - Added `--retest` flag to force re-testing all models

### Root Causes
1. **Few-shot bug**: The `prefers_few_shot` setting was designed for native tool-calling models, but was incorrectly applied to ReAct-mode models which **require** few-shot examples
2. **Observation role bug**: In the ReAct pattern, Observations must appear as `user` messages for the model to respond to them
3. **Thinking mode bug**: Ollama enables thinking by default for qwen3/deepseek-r1, causing empty content unless `think=False` is passed

### Added
- **Quick Diagnostic Test (test 15)** - 5-question rapid test for debugging (~30-60s per model)
  - `agentnova test 15 --model granite3.1-moe:1b`
  - `agentnova test 15 --model all --debug`
  - Designed for rapid iteration during development
  - Questions target specific failure modes: simple math, multi-step, division, word problems, edge cases

### Impact

| Model | Mode | Before R02.2 | After R02.2 | Change |
|-------|------|---------------|--------------|--------|
| **granite3.1-moe:1b** | react | 80% (12/15) | **93% (14/15)** | **+13%** |
| **llama3.2:1b** | native | 67% (10/15) | **87% (13/15)** | **+20%** |
| **qwen2.5-coder:0.5b** | react | 53% (8/15) | **60% (9/15)** | **+7%** |
| qwen3:0.6b | react | 0% (broken) | **67% (10/15)** | **Fixed** |
| dolphin3.0-qwen2.5:0.5b | none | 73% (11/15) | 73% (11/15) | = |
| qwen3.5:0.8b | native | N/A (new) | **100%** (test 15) | New model |
| qwen2.5:0.5b | react | 73% (11/15) | **100%** (test 15) | **+27%** |

### Quick Diagnostic Results (Test 15 - 5 Questions)

| Model | Score | Time | Tool Support | Notes |
|-------|-------|------|--------------|-------|
| **qwen3.5:0.8b** | **5/5 (100%)** | 569s | native | 🏆 Perfect with native tools |
| **qwen2.5:0.5b** | **5/5 (100%)** | 76.5s | react | 🏆 Perfect with ReAct mode |
| **functiongemma:270m** | 4/5 (80%) | 27.4s | native | Word problem misinterpretation |
| **granite4:350m** | 4/5 (80%) | 88.2s | native | Synthesis returned raw JSON |
| **qwen3:0.6b** | 3/5 (60%) | 119.6s | react | Multi-step extraction issue |
| **gemma3:270m** | 2/5 (40%) | 11.4s | none | No tool support |
| **qwen:0.5b** | 1/5 (20%) | 32s | none | No tool support |

### Technical Details
- ReAct models need few-shot examples to learn: `Thought: ... Action: tool_name Action Input: {"arg": ...}`
- Native models should NOT have few-shot examples (API handles tool calling directly)
- Observations must be `user` role because they represent external input that the model should process
- Thinking-capable models (qwen3, deepseek-r1) require `think=False` in API call to disable thinking mode
- The Ollama API `think` parameter is the proper way to control thinking mode (not prompt-based directives)
- **qwen3.5:0.8b** is the new sub-1B champion with native tool calling (100% on quick diagnostic)

---

## [R02.1] - 2026-03-21 4:11:21 PM

- Possibly last version published to PyPi for awhile
- One line fix I missed in R02, had to completely re-package and bump version just to fix.
- Development is too fast in Alpha to keep PyPi package always up to date
- The current and latest version will always available on GitHub.
- 'pip install git+https://github.com/VTSTech/AgentNova.git' will be the only supported install method for the near future.

## [R02] - 2026-03-21 3:25:54 PM

### 🎯 Model Family Configuration System

Major improvements to model-specific behavior with automatic family detection and family-aware prompting.

### Added
- **Model Family Configuration System** (`core/model_family_config.py`)
  - Automatic model family detection (gemma, granite, qwen2, qwen3, llama, dolphin, etc.)
  - Family-specific tool call formats (`<tool_call\>`, `<|tool_call|>`, raw JSON)
  - Family-specific stop tokens for preventing runaway generation
  - Family-specific ReAct format hints in system prompts
  - Few-shot style preferences per family
  - `get_stop_tokens()` - Returns family-specific stop tokens
  - `get_react_system_suffix()` - Returns family-specific ReAct format hints
  - `get_native_tool_hints()` - Returns hints for native tool mode
  - `should_use_few_shot()` - Determines if few-shot is beneficial
  - `get_few_shot_style()` - Returns appropriate few-shot format

- **Repetition Loop Fixes**
  - Stop token for ReAct mode (`\nFinal Answer:`) to prevent repetition loops
  - Repetition detection regex collapses repeated "Final Answer:" outputs
  - Prevents small models from looping the same text 100+ times (was causing 269s test times)

- **Few-Shot Prompting for Small Models**
  - Automatic few-shot example injection for models <2B parameters
  - Family-aware few-shot styles (native vs ReAct format)
  - Improved accuracy on benchmark tests for small models

- **Interactive Test Controls** (test files 07/08)
  - `[s]tatus` - Show current progress
  - `[b]ypass model` - Skip current model
  - `[q]uit` - Exit test early

- **Debug Output** (optional `--debug` flag)
  - System prompt construction details
  - Response parsing debug info
  - Tool call extraction logging

### Fixed
- Corrupted tool_call tags in model_family_config.py (encoding issue where `<tool_call\>` appeared as `Ȑ`)
- Import order for `get_stop_tokens` function in agent.py
- ReAct parsing for models with non-standard output formats

### Changed
- Agent initialization now detects model family automatically via `model_family` parameter
- Few-shot prompting enabled by default for small models with tools
- Stop tokens merged from family config + ReAct-specific tokens
- Import moved before usage to prevent NameError

### Benchmark Results (Small Models)

| Model | Params | Tool Support | Score | Time |
|-------|--------|--------------|-------|------|
| **granite3.1-moe:1b** | 1B MoE | react | **80% (12/15)** | 60.6s |
| **qwen3:0.6b** | 600M | react | **80% (12/15)** | 473s |
| dolphin3.0-qwen2.5:0.5b | 500M | none | 73% (11/15) | 24.5s |
| qwen2.5:0.5b | 500M | native | 73% (11/15) | 84.2s |
| llama3.2:1b | 1.2B | native | 67% (10/15) | 180.1s |
| tinyllama:1.1b | 1.1B | none | 67% (10/15) | 253.1s |
| tinydolphin:1.1b | 1.1B | none | 67% (10/15) | 391.9s |
| qwen2.5-coder:0.5b | 494M | react | 53% (8/15) | 65.8s |
| dolphin3.0-llama3:1b | 1B | none | 47% (7/15) | 43.8s |

**`granite3.1-moe:1b` and `qwen3:0.6b` tie for champion at 80%!** granite3.1-moe is 8x faster (60.6s vs 473s). qwen3:0.6b is the only model with perfect Reasoning (3/3).

### Technical Details
- New `ModelFamilyConfig` dataclass with per-family settings
- Family detection from model name patterns
- Support for different tool call wrappers:
  - granite4/qwen2.5: `<tool_call\>{"name": "...", "arguments": {...}}<\tool_call>`
  - granite3.1-moe: `<|tool_call|>{"name": "...", "parameters": {...}}`
  - llama3.2: Raw JSON with "parameters" key
  - gemma3: No tool wrapper

---

## [R01] - 2026-03-21 3:52:01 AM

### 🚀 Native Tool Synthesis for Small Models

Major improvements to native tool calling for small models (≤1B parameters). When models struggle to make tool calls, AgentNova now synthesizes them directly from natural language prompts.

### Added
- **Expression extraction from natural language**:
  - `"What is 15 times 8?"` → `15 * 8`
  - `"What is the square root of 144?"` → `sqrt(144)`
  - `"What is (10 + 5) times 3?"` → `(10+5) * 3`
  - `"What is 100 divided by 4?"` → `100 / 4`
  - `"What is 2 to the power of 10?"` → `2 ** 10`
- **Echo text extraction**:
  - `"Echo the text 'Hello AgentNova'"` → `Hello AgentNova`
- **Two-tier empty response retry**:
  1. First retry: Send specific hint with extracted expression
  2. Second retry: Synthesize tool call directly (bypass confused model)
- **Hallucinated tool mention detection**:
  - Detects when model says "we can use the calculator tool" but doesn't call it
  - Synthesizes the tool call automatically
- **Bare expression wrapping for python_repl**:
  - `2**20` → `print(2**20)` (produces visible output instead of `[No output]`)

### Test Results (qwen2.5:0.5b - Native Tool Mode)

| Test Category | R00 | R01 | Improvement |
|---------------|-----|-----|-------------|
| Calculator | 40% | **100%** | **+60%** |
| Shell | 66% | **100%** | **+34%** |
| Python REPL | 66% | **100%** | **+34%** |
| **TOTAL** | **~55%** | **100%** | **+45%** |

### Test Results (qwen2.5-coder:0.5b - ReAct Mode)

| Test Category | R00 | R01 |
|---------------|-----|-----|
| Calculator | 100% | **100%** ✅ |
| Shell | 100% | **100%** ✅ |
| Python REPL | 100% | **100%** ✅ |
| **TOTAL** | **100%** | **100%** ✅ |

### Key Features
- **Backward compatible** - All changes are additive, ReAct mode unchanged
- **Automatic fallback** - Synthesis only triggers when model fails
- **Debug visibility** - `--debug` shows extraction and synthesis steps

### Technical Details
- New `_extract_calc_expression()` helper extracts math expressions from prompts
- New `_extract_echo_text()` helper extracts echo text from prompts
- Native tool retry now tracks `retry_count` for multi-tier fallback
- Bare expression detection checks for print/assignment/import/def/class

---

## [R00] - 2026-03-21 12:35:03 AM

### 🚀 ReAct Prompting Improvements

Significant improvements to ReAct-style tool calling for models without native support.

### Added
- **ReAct few-shot examples** - Proper ReAct format examples in system prompt
  - Shows exact `Thought: / Action: / Action Input:` format
  - Includes calculator and shell examples with expected outputs
  - Helps models understand the ReAct loop pattern
- **Debug output for `--debug` flag**:
  - Full raw LLM response before processing
  - ReAct parsing results with matched groups
  - Helps diagnose tool calling issues

### Changed
- **Improved ReAct regex parsing** in `agent.py`:
  - Now handles backticks around tool names (`` `shell` ``)
  - Supports same-line format: `Action: tool_name Action Input: {...}`
  - More robust quote handling in JSON arguments
- **Shell tool description enhanced** - Now mentions common commands:
  - Lists `pwd`, `date`, `ls` as available commands
  - Helps models understand shell capabilities
  - Improves recognition for system info queries
- **Malformed response handling** in `_remove_tool_schema()`:
  - Catches responses that are just backticks (```, ``, `)
  - Handles empty fence markers (```json, ```python)
  - Returns fallback for content shorter than 3 characters
  - Prevents corrupted final answers
- **Nested value extraction** for fuzzy matching:
  - New `_extract_nested_value()` helper function
  - Extracts values from nested structures like `{"tool_args": {...}}`
  - Improves argument matching for non-standard model outputs

### Test Results (qwen2.5-coder:0.5b)

| Test Category | Before | After | Improvement |
|---------------|--------|-------|-------------|
| Calculator | 27% | **60%** | +33% |
| Shell Echo | Failed (```) | **Passed** | Fixed |

### Key Fixes
- Shell echo test was returning ` ``` ` instead of actual output - now correctly returns `Hello AgentNova`
- Models writing Python code blocks instead of using ReAct for math - now guided by few-shot examples

---

## [R00] - 2026-03-20 

### 🔄 Project Rename & Version Reset

**LocalClaw is now AgentNova!**

This release marks the transition from `localclaw` to `agentnova` as the official package name. The project has been renamed to avoid conflicts with other projects using similar names.

#### What Changed
- **Package name**: `localclaw` → `agentnova`
- **CLI command**: `localclaw` → `agentnova` (old command still works with deprecation warning)
- **Environment variables**: `LOCALCLAW_*` → `AGENTNOVA_*` (old vars still work for backward compatibility)
- **Version reset**: R04.0.0 → R00.0.0 (starting fresh with the new name)
- **Repository**: https://github.com/VTSTech/AgentNova

#### Backward Compatibility
The `localclaw` package is still available as a thin compatibility shim:
```python
import localclaw  # Works, shows deprecation warning, redirects to agentnova
```
```bash
localclaw run "prompt"  # Works, redirects to agentnova
```

#### Migration Guide
```python
# Old (still works, deprecated)
import localclaw
from localclaw import Agent

# New (recommended)
import agentnova
from agentnova import Agent
```

```bash
# Old (still works)
localclaw run "What is the capital of Japan?"
localclaw chat -m llama3.2:3b

# New (recommended)
agentnova run "What is the capital of Japan?"
agentnova chat -m llama3.2:3b
```

---

[R04.0.0] - 03-20-2026 12:02:02 PM

### Major Release - Agent Mode

This release introduces full Agent Mode with autonomous task execution, complete ACP integration for activity logging, and improved final response handling.

### Added
- **Agent Mode - Full Implementation**:
  - `agentnova agent` command for goal-driven autonomous task execution
  - State machine: IDLE → WORKING → IDLE with PAUSED and STOPPING states
  - Message queuing during execution, processed after task completion
  - Rollback support with `/stop` prompting for confirmation
  - Background task execution with real-time progress tracking
  - LLM-based planning with heuristic fallback for small models

- **Agent Mode Slash Commands**:
  - `/status` - Show current agent status and progress
  - `/progress` - Detailed step-by-step breakdown
  - `/plan` - Show the current task plan
  - `/pause` / `/resume` - Pause and resume execution
  - `/stop` - Stop with rollback confirmation
  - `/logs` - View execution history
  - `/reset` - Clear memory and plans

- **`AgentMode` class** in `agent_mode.py`:
  - State management with callbacks
  - Task planning with LLM and heuristic methods
  - Step execution using Agent.run()
  - Execution logging and history
  - Final response tracking across all steps
  - Rollback action helpers (file write/delete, mkdir, shell)

- **ACP Integration for Agent Mode**:
  - User messages logged to ACP when tasks start
  - Final responses logged to ACP on task completion
  - All steps logged with full content (no truncation)
  - `log_user_message()` and `log_assistant_message()` helpers

- **Improved Final Response Display**:
  - Full final response shown on task completion
  - `/status` now includes final_response field
  - format_status() displays full response (up to 10 lines)

### Changed
- **ACP Plugin - Full Message Logging**:
  - `_handle_final()` now logs full answer (not truncated to 100 chars)
  - `log_chat()` details limit increased from 1000 to 4000 chars
  - `log_chat()` result limit increased from 500 to 2000 chars
  - Notes content limit increased from 400 to 2000 chars
  - Note importance changed from "normal" to "high"

- **Version reset**: Starting fresh with AgentNova name (was R04 under LocalClaw)

### Fixed
- Final responses now displayed in full when Agent Mode tasks complete
- ACP receives complete step content instead of truncated messages

### Usage
```bash
# Start agent mode with ACP logging
agentnova agent --model llama3.2:1b --tools calculator,shell --acp

# With verbose output
agentnova agent -m llama3.2:1b --tools calculator,shell -v --acp

# With Modelfile system prompt
agentnova agent --use-mf-sys --tools shell --acp --debug
```

### Verified Working
- `llama3.2:1b` - First model to correctly respond in Agent Mode
- GSM8K champion at 90% accuracy
- Correctly identifies as AgentNova, acknowledges user

---

## [R03.2.0] - 03-20-2026

### Added
- **Agent Mode** - New `agentnova agent` command for autonomous task execution
  - Goal-driven execution: Give tasks and agent works through them autonomously
  - State machine: IDLE → WORKING → IDLE with PAUSED and STOPPING states
  - Message queuing: Messages queued while working, processed after completion
  - Slash commands always respond (even during WORKING state)
  - Rollback support: `/stop` prompts for rollback confirmation
  - Background execution: Tasks run in background thread with progress tracking
  - LLM-based planning with heuristic fallback for small models
  
- **Agent Mode Slash Commands**:
  - `/status` - Show current agent status and progress
  - `/progress` - Detailed step-by-step breakdown
  - `/plan` - Show the current task plan
  - `/pause` / `/resume` - Pause and resume execution
  - `/stop` - Stop with rollback confirmation
  - `/logs` - View execution history
  - `/reset` - Clear memory and plans
  - `/tools`, `/skills`, `/ollama` - Always available

- **`AgentMode` class** in `agent_mode.py`:
  - State management with callbacks
  - Task planning with LLM and heuristic methods
  - Step execution using Agent.run()
  - Execution logging and history
  - Rollback action helpers (file write/delete, mkdir, shell)

- **Data classes for Agent Mode**:
  - `Action` - Atomic action with rollback support
  - `Step` - Collection of actions with status tracking
  - `TaskPlan` - Complete plan with progress tracking

### Changed
- **Simplified planning** - Small models often struggle with complex planning prompts
  - LLM planning only used for complex tasks (verbose mode or long goals)
  - Heuristic planning uses single-step for most simple queries
  - Execution prompts are simple and direct to respect Modelfile system prompts

### Usage
```bash
# Start agent mode
agentnova agent --model llama3.2:1b --tools calculator,shell

# With verbose output
agentnova agent -m llama3.2:1b --tools calculator,shell -v

# With Modelfile system prompt
agentnova agent --use-mf-sys --tools shell
```

---

## [R03.1.1] - 03-20-2026 11:00:59 AM

### Added
- **`--num-ctx`, `--num-predict`, `--fast` flags for test command** - Configure context window and prediction limits for benchmark tests
  - Usage: `agentnova test 14 --num-ctx 4096 --num-predict 256`
  - `--fast` preset: `--num-ctx 2048 --num-predict 128`
  - Enables memory optimization for running benchmarks on resource-constrained systems
- **`shared_args` module** - Centralized CLI argument handling for test scripts
  - `SharedConfig` dataclass for passing configuration to subprocess
  - `add_shared_args()` function for consistent argument parsing
  - Replaces environment variable passing with direct CLI argument forwarding
- **`/ollama` chat command** - Remote Ollama management via HTTP API
  - Works with both local and remote Ollama instances (via Cloudflare tunnels, etc.)
  - Commands: `list`, `pull`, `rm`, `show`, `ps`, `stop`, `cp`, `set-url`
  - No dependency on local `ollama` CLI binary
  - New methods in `OllamaClient`: `pull_model()`, `delete_model()`, `list_running()`, `push_model()`, `create_model()`, `unload_model()`, `copy_model()`

### Fixed
- **`--acp` flag not respected in test scripts** - `14_gsm8k_benchmark.py` wasn't using `shared_args`
  - Updated to import and use `add_shared_args()` and `parse_shared_args()`
  - ACP integration now works correctly with `agentnova test 14 --acp`
- **Syntax error in cli.py line 446** - f-string cannot contain backslash
  - Changed `system.split('\n')` inside f-string to pre-computed `more_lines` variable
  - Python f-strings require backslash expressions to be moved outside the `{}`
- **`/ollama rm` JSON parsing error** - Ollama returns empty response on successful delete
  - Updated `_delete()` to handle empty responses gracefully
  - Returns `{"status": "success"}` for empty responses
- **`/ollama stop` HTTP 404 error** - Model not running causes confusing error
  - Updated `unload_model()` to return `{"status": "not_running"}` instead of throwing error
  - CLI now shows "⚠ Model 'xxx' is not currently running"
- **`re` module import error** - Missing module-level import in cli.py
  - Added `import re` at module level for `_contains_text_tool_call()` function

### Changed
- **Refactored test argument passing** from environment variables to direct CLI arguments
  - Cleaner architecture: args passed via subprocess CLI instead of env vars
  - Test scripts receive `--force-react`, `--use-mf-sys`, `--model`, `--debug`, `--acp` directly
- **Fixed pytest warnings** in test files
  - Changed `return True/False` to proper pytest pattern (use `assert` and `raise`)
  - Tests now pass without `PytestReturnNotNoneWarning`
  - All 37 tests passing with 0 warnings (was 7 warnings)
- **TESTS.md restructured** with comprehensive benchmark comparison
  - Added separate tables for Modelfile prompts vs `--force-react` mode
  - Added "Mode Comparison" table showing which mode is better per model
  - Updated category champions for both modes
- **Tool support detection logic (v2)** - Improved accuracy
  - Added `_contains_text_tool_call()` to detect text-based JSON tool calls
  - Models outputting `{"name": "...", "arguments": {...}}` as TEXT now classified as "react"
  - "native" requires ACTUAL `tool_calls` structure in API response
  - New output message: `→ ReAct (text JSON)` for text-based tool calling
- **Memory optimization** for `--tool_support` testing
  - Models are now unloaded after each tool support test
  - Prevents memory exhaustion when testing multiple models

### Tool Support Detection Results (1B-2B Models)

| Model | Tool Support | Notes |
|-------|--------------|-------|
| `llama3.2:1b` | ✓ native | True native API tool calling |
| `granite3.1-moe:1b` | ReAct (text JSON) | Outputs JSON as text, not native API |
| `driaforall/tiny-agent-a:1.5b` | ReAct | API accepted tools, no native calls |
| `deepseek-coder:1.3b` | ○ none | Modelfile issue (model supports tools) |
| `nchapman/dolphin3.0-llama3:1b` | ○ none | Dolphin fine-tune lost tool support |
| `tinydolphin:1.1b` | ○ none | Too small/old |
| `tinyllama:1.1b` | ○ none | Too small/old |

### Benchmark Results (15-Test Comparison)

#### Modelfile vs --force-react

| Model | Modelfile | ReAct | Δ Time | Better |
|-------|-----------|-------|--------|--------|
| `dolphin3.0-qwen2.5:0.5b` | 11/15, 27.1s | 11/15, 24.4s | -2.7s | ReAct |
| `granite4:350m` | 11/15, 78.4s | 11/15, 75.6s | -2.8s | ReAct |
| `qwen2.5-coder:0.5b` | 9/15, 121.7s | 9/15, 111.6s | -10.1s | ReAct |
| `gemma3:270m` | 8/15, 22.8s | 8/15, 29.4s | +6.6s | Modelfile |
| `qwen2.5:0.5b` | 8/15, 61.0s | 8/15, 54.5s | -6.5s | ReAct |
| `functiongemma:270m` | 2/15, 55.1s | 2/15, 56.1s | +1.0s | Tie |
| `qwen3:0.6b` | 0/15, 197.0s | 0/15, 199.2s | +2.2s | Both fail |

**Key Finding:** `--force-react` is faster for most models, except `gemma3:270m` (no tool support = ReAct adds unnecessary overhead).

### Benchmark Results (GSM8K 50-Question Comparison)

#### Modelfile vs --force-react

| Model | Modelfile | ReAct | Δ Score | Δ Accuracy | Better |
|-------|-----------|-------|---------|------------|--------|
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
4. **`gemma3:270m` slightly worse with ReAct** - pure reasoning is optimal

### Known Issues
- `granite4:350m` detected as "native" but outputs tool calls as text JSON instead of using native API
  - Debug shows `tool_calls_raw=[]` despite `_tool_support=native`
  - May need reclassification to "react" or detection logic refinement
- `qwen3:0.6b` fails completely (0%) in both modes - fundamental issues beyond tool support

---

## [R03.1.0] - 03-19-2026 10:32:24 PM

### Added
- **`get_tool_support()` function** - Exported tool support detection API
  - Returns: `"native"`, `"react"`, `"none"`, or `"untested"`
  - Checks `tested_models.json` only (no heuristic fallback)
  - Usage: `from agentnova import get_tool_support`
  - Enables external tools to query model capabilities before running agents

- **Three-tier tool support system** in Agent class:
  - `"native"` - Model has native Ollama tool-calling (pass tools to API)
  - `"react"` - Model accepts tools but needs text-based ReAct prompting
  - `"none"` - Model explicitly rejects tools (don't pass tools at all)
  - `"untested"` - Not yet tested, defaults to `"react"` (safest)

- **`MATH_SYSTEM_PROMPT_NO_TOOLS`** - New prompt for models without tool support
  - Pure reasoning prompt (no tool references)
  - Step-by-step examples for arithmetic
  - Prevents confusion for models that can't use tools

- **Short-circuit path for non-tool models** - Models with `"none"` support:
  - Skip tool-related prompt construction
  - Skip ReAct loop entirely
  - Return response directly without tool overhead

### Changed
- **Removed heuristic fallback** from `get_tool_support()`:
  - Family-based assumptions were inaccurate (e.g., dolphin fine-tunes lost native support)
  - Now requires explicit testing via `agentnova models --tool_support`
  - Untested models show `"untested"` in models table

- **Agent initialization** now uses `get_tool_support()` for detection:
  - Priority: `force_react` > `tested_models.json` > default to `"react"`
  - New properties: `_tool_support`, `_native_tools`, `_no_tools`
  - `"untested"` treated as `"react"` (safest default)

- **GSM8K benchmark** uses proper prompts by tool support level:
  - `"none"` → `MATH_SYSTEM_PROMPT_NO_TOOLS` (pure reasoning)
  - `"react"` → `MATH_SYSTEM_PROMPT` + ReAct suffix
  - `"native"` → `MATH_SYSTEM_PROMPT` (tools via API)

- **ACP Plugin** updated to v1.0.5:
  - Added `primary_agent` in `/api/whoami` response
  - Nudges delivered only to primary agent (prevents context pollution)

### Fixed
- **Models with `"none"` tool support now get appropriate prompts**
  - Previously used compact prompt that mentioned "calculator tool"
  - Now uses pure reasoning prompt without tool references
  - **Result**: `gemma3:270m` improved from 4% to **64%** on GSM8K (+60%)

### Tool Support Levels

| Level | Description | Prompt | Tools Passed |
|-------|-------------|--------|--------------|
| `"native"` | Native API tool-calling | MATH_SYSTEM_PROMPT | Calculator |
| `"react"` | Text-based ReAct parsing | MATH_SYSTEM_PROMPT + suffix | Calculator |
| `"none"` | No tool support | MATH_SYSTEM_PROMPT_NO_TOOLS | None |
| `"untested"` | Not yet tested | MATH_SYSTEM_PROMPT + suffix | Calculator |

### Example Output
```
⚛️ AgentNova R00 Models
  Model                                      Family       Context    Tool Support
  ──────────────────────────────────────────────────────────────────────────────
  gemma3:270m                                gemma3       32K        ○ none
  granite4:350m                              granite      32K        ✓ native
  qwen2.5-coder:0.5b-instruct-q4_k_m         qwen2        32K        ReAct
  functiongemma:270m                         gemma3       32K        untested

  1 model(s) untested. Use --tool_support to detect native support.
```

### Benchmark Impact
| Model | Tool Support | Before | After | Change |
|-------|--------------|--------|-------|--------|
| `gemma3:270m` | none | 4% | **64%** | **+60%** |

---

## [R03.0.10] - 03-19-2026 4:10:37 PM

### Added
- **Dynamic tool support detection** - Models are now tested individually instead of relying on family-based heuristics
  - New `--tool_support` flag for `models` command: `agentnova models --tool_support`
  - Tests each model using Ollama's native tool API with Modelfile system prompts (no custom prompts)
  - Results persisted to `tested_models.json` for future reference
- **Enhanced `models` command output** - Now displays 4 columns:
  - **Model** - Model name
  - **Family** - Model family from Ollama API
  - **Context** - Context window size
  - **Tool Support** - `✓ native`, `ReAct`, or `○ none`

### Tool Support Detection Logic
Detection is now simplified and more accurate:
1. **Ollama rejection** - HTTP 400 "does not support tools" → `none` (definitive)
2. **Native tool_calls** - Structured response in API → `native` (definitive)
3. **API succeeded** - Model accepted tools but no native tool_calls → `react`

**Key insight**: If Ollama accepts the tools parameter without error, the model CAN use tools. Only HTTP 400 "does not support tools" means truly no support.

### Changed
- **Default tool support** - Untested models now show `ReAct (?)` until tested with `--tool_support`
- **Removed family-based assumptions** - Models are no longer assumed to support tools based on family name

### Example Output
```
⚛️ AgentNova R00 Models · Written by VTSTech · https://www.vts-tech.org · https://github.com/VTSTech/AgentNova
  Model                                      Family       Context    Tool Support
  ──────────────────────────────────────────────────────────────────────────────
  driaforall/tiny-agent-a:1.5b               qwen2        32K        ReAct
  gemma3:270m                                gemma3       32K        ○ none
  granite4:350m                              granite      32K        ✓ native
  qwen2.5-coder:0.5b-instruct-q4_k_m         qwen2        32K        ReAct
```

---

## [R03.0.9] - 03-19-2026 3:13:37 PM

### Added
- **`--acp` flag for test command** - Enables ACP (Agent Control Panel) integration for all test scripts
  - Usage: `agentnova test 01 --acp` or `agentnova test 14_acp`
  - Passes `AGENTNOVA_ACP=1` environment variable to test scripts
  - Provides activity tracking, token counting, and session logging via ACP server
- **`--use-mf-sys` flag for test command** - Use Modelfile system prompts instead of AgentNova defaults
  - Usage: `agentnova test 01 --use-mf-sys --model qwen2.5-coder:0.5b`
  - Passes `AGENTNOVA_USE_MF_SYS=1` environment variable to test scripts
- **`--debug` flag for test command** - Enable debug output for parsed tool calls and fuzzy matching
  - Passes `AGENTNOVA_DEBUG=1` environment variable to test scripts
- **`AGENTNOVA_ACP` environment variable** - Universal ACP control across all examples
  - All example scripts now check this env var to conditionally enable ACP
  - Scripts create model-specific ACP instances for per-model tracking

### Changed
- **Merged `_acp` scripts into base scripts** - No more duplicate files
  - `07_model_comparison.py` now supports `--acp` flag (removed `07_model_comparison_acp.py`)
  - `08_robust_comparison.py` now supports `--acp` flag (removed `08_robust_comparison_acp.py`)
  - `09_expanded_benchmark.py` now supports `--acp` flag (added ACP integration)
  - `11_skill_creator_test.py` now supports `--acp` flag (added ACP integration)
  - `12_batch_operations.py` created from former `12_batch_operations_acp.py` (requires ACP)
  - `13_shutdown_demo.py` created from former `13_shutdown_demo_acp.py` (requires ACP)
  - `14_gsm8k_benchmark.py` created from `gsm8k_agent_benchmark.py` with ACP support
- **Test numbering reorganized**:
  - Test 12: Batch operations (ACP demo)
  - Test 13: Shutdown demo (ACP demo)
  - Test 14: GSM8K benchmark (50 math questions)
  - Removed old `gsm8k` and `gsm8k_acp` test IDs
- **Updated cli.py EXAMPLES dict** with new test entries and `_acp` shorthand mappings
  - Running `agentnova test 07_acp` auto-enables ACP and runs base script
  - All tests now support `--acp`, `--debug`, `--use-mf-sys`, and `--model` flags

### Fixed
- **Syntax error in `08_robust_comparison.py`** - Fixed malformed `get_small_models()` function

### Test Script ACP Support Matrix
| Test | AGENTNOVA_ACP | Notes |
|------|---------------|-------|
| 01-11 | ✅ Conditional | ACP optional, runs without it |
| 12-13 | ✅ Required | Exits gracefully if ACP unavailable |
| 14 | ✅ Conditional | ACP optional, runs without it |

---

## [R03.0.8] - 03-19-2026 2:06:37 AM

### Added
- **`--force-react` flag for test command** - Forces text-based ReAct tool calling for all models
  - Usage: `agentnova test gsm8k --force-react`
  - Passes `AGENTNOVA_FORCE_REACT=1` environment variable to test scripts
  - Essential for models without native tool support (BitNet, some small models)
- **`AGENTNOVA_FORCE_REACT` environment variable** - Controls ReAct mode across all examples
  - Values: `1`, `true`, `yes` to enable
  - Auto-detected by all benchmark and tool examples
  - Forces text-based "Thought/Action/Action Input/Observation" format
- **`MATH_SYSTEM_PROMPT_REACT` prompt** - ReAct-optimized math prompt in `math_prompts.py`
  - Includes explicit format examples for calculator tool usage
  - Shows exact "Action: calculator" / "Action Input: {"expression": ...}" format

### Changed
- **Updated all benchmark examples** to respect `AGENTNOVA_FORCE_REACT`:
  - `gsm8k_agent_benchmark_acp.py` - Full force_react support
  - `07_model_comparison.py` / `_acp.py` - Added force_react parameter
  - `08_robust_comparison.py` / `_acp.py` - Added force_react parameter
  - `09_expanded_benchmark.py` - Added force_react parameter
  - `02_tool_agent.py` / `_acp.py` - Added force_react support
- **Small model auto-detection** - Models with indicators (270m, 350m, 0.5b, 1b, tiny) auto-enable ReAct

### Benchmark Results
- **`granite4:350m` with `--force-react`**: 82% on GSM8K (41/50) - **NEW TOP PERFORMER** for sub-500M models
- **`qwen2.5-coder:0.5b` with `--force-react`**: 60% on GSM8K (30/50)
- ReAct mode significantly outperforms native tool calling for models <1B parameters

---

## [R03.0.7] - 03-18-2026 3:00:37 PM

### Added
- **`--timeout` flag for test command** - Configurable timeout per test
  - Usage: `agentnova test gsm8k --timeout 900` (15 minutes)
  - Default remains 300 seconds (5 minutes)
  - Timeout value shown in error message when exceeded

## [R03.0.6] - 03-18-2026 2:50:37 PM

### Fixed
- **Unused imports in benchmark examples** - Cleaned up `gsm8k_agent_benchmark.py` and `gsm8k_agent_benchmark_acp.py`
  - Removed unused `Tool` and `ToolParam` imports
  - Removed commented-out legacy import in `_acp` version
- **Test runner output visibility** - Removed `capture_output=True` from subprocess
  - Test output now streams directly to terminal in real-time
  - Users can see benchmark progress and results as tests run
- **Hardcoded paths in benchmark tests** - Changed from `/home/z/my-project/download/` to `./`
  - Results and log files now write to current directory
  
---

## [R03.0.5] - 03-18-2026 2:08:37 PM

### Changed
- **Re-enabled ANSI colors** - Set `_NO_COLOR = False` in CLI
  - Colors now display correctly in most terminals
  - Atom emoji ⚛️ displays properly across all commands
### Fixed
- **Test parser for `_acp` suffix tests** - Glob patterns now correctly match ACP test files
  - `gsm8k_acp` now correctly finds `gsm8k_agent_benchmark_acp.py`
  - `gsm8k` now correctly finds `gsm8k_agent_benchmark.py` (filters out `_acp` files)
  - Non-acp tests filter out `_acp` files to prevent wrong matches
- **Import error in `gsm8k_agent_benchmark.py`** - Updated import statement
  - Changed `from agentnova.core.ollama_client import get_default_client` to `from agentnova import get_default_client`
  - Function was moved to main package in earlier release

---

## [R03.0.4] - 03-18-2026

### Fixed
- **Argparse help display in Google Colab** - Disabled all ANSI color codes by default
  - Set `_NO_COLOR = True` unconditionally to eliminate any ANSI escape sequence issues
  - Colors were causing terminal output truncation in Colab's `TERM=screen` environment
  
### Fixed
- **Argparse help display in Google Colab** - Final fix: removed emoji from argparse description entirely
  - Emojis in argparse description cause terminal width calculation issues in Colab's `TERM=screen` environment
  - Removed custom `WideHelpFormatter` class - standard `RawDescriptionHelpFormatter` works fine
  - Help now displays correctly: description, positional arguments, options, examples

### Fixed
- **Argparse help display in Google Colab** - Removed emoji from description (emojis break argparse's width calculation in Colab's terminal)
- Help now displays correctly with positional arguments section visible

### Fixed
- **Argparse help display in Google Colab** - Shortened description and moved URLs to epilog to prevent truncation in environments with non-standard terminals
- Added `WideHelpFormatter` with forced width of 200 characters for better compatibility
- URLs now display correctly in the help epilog section

---

## [R03.0.3] - 03-18-2026

### Fixed
- **Argparse help display in Google Colab** - Added `WideHelpFormatter` with minimum width of 120 characters to fix truncation issues in environments with non-standard terminals (Google Colab, some Docker containers)
- Removed unnecessary Colab color detection - ANSI colors work fine in Colab, the issue was argparse width calculation

---

## [R03.0.2] - 03-18-2026

### Changed
- **Documentation restructure** - README.md split into modular documentation files
  - `README.md` now serves as concise entry point (~180 lines, down from ~420)
  - `Architecture.md` - Technical documentation for developers (directory structure, design decisions, orchestrator modes)
  - `CHANGELOG.md` - Version history and release notes
  - `TESTS.md` - Benchmark results, model recommendations, and testing guide
  - Added Documentation table in README with clear links to all supporting files
- **Fixed version mismatch** - `__init__.py` now correctly shows 0.3.0.2 (was behind at 0.3.0)

---

## [R03] - 03-17-2026

### Added
- **BitNet Backend Support** - Alternative inference backend using Microsoft's BitNet b1.58 2-bit quantization
  - New `BitnetClient` class in `agentnova/bitnet_client.py` (simplified from 667 to 149 lines)
  - Setup helper in `agentnova/bitnet_setup.py` for cloning and compiling BitNet
  - CLI flag `--backend bitnet` to switch from Ollama to BitNet
  - Supported models: `BitNet-b1.58-2B-4T`, `Falcon3-1B-Instruct-1.58bit`, `Falcon3-3B-Instruct-1.58bit`, `Falcon3-7B-Instruct-1.58bit`
  - Model download via `huggingface-cli` or `wget` with automatic safetensors→GGUF conversion
- **Enhanced Security in Built-in Tools**
  - Path validation with configurable allowed directories (`AGENTNOVA_ALLOWED_PATHS`)
  - Command blocklist with dangerous commands blocked (`AGENTNOVA_BLOCKED_COMMANDS`)
  - Dangerous pattern detection (piping to bash, command substitution, device writes)
  - SSRF protection in `http_get` with private IP blocking and DNS rebinding prevention
  - Three security modes: `strict`, `permissive`, `disabled` (`AGENTNOVA_SECURITY_MODE`)
- **ACP Plugin Enhancements**
  - Merged `acp_streaming.py` into `acp_plugin.py` for unified ACP support
  - Added `CostTracker` and `SessionHealth` classes for monitoring
  - JSON-RPC 2.0 support for A2A compliance
  - Agent Card discovery via `/.well-known/agent-card.json`
  - Auto-generated AgentSkills from tool mapping
- **Agent Improvements**
  - Pre-call argument synthesis for missing required arguments
  - Redundant calculator call detection to avoid unnecessary tool invocations
  - Enhanced few-shot prompting for small models
  - Improved date/time query handling with automatic Python code synthesis
- **Test Scripts for BitNet**
  - `test-bitnet.sh` / `test-bitnet.cmd` - Run benchmark tests with BitNet backend

### Changed
- Version tags updated from R02 to R00 across all files
- CLI now supports `--backend ollama|bitnet` flag for backend selection
- Tool system now has comprehensive security validation layer
- ACP streaming functionality consolidated into main plugin
- README.md rewritten with CLI command examples instead of Python code
- README.md added comprehensive BitNet section with model download instructions
- ACP benchmark tests (`07_model_comparison_acp.py`, `08_robust_comparison_acp.py`) now display proper model names for path-style BitNet models

### Fixed
- **ACP model name display** - Path-style model names (e.g., `Falcon3-1B-Instruct-1.58bit/ggml-model-i2_s.gguf`) now show directory name instead of GGUF filename in activity log

### Removed
- `agentnova/acp_streaming.py` - merged into `acp_plugin.py`

### Tested
- BitNet backend with `Falcon3-1B-Instruct-1.58bit` model - ✅ Working
- Model conversion from safetensors to GGUF via `setup_env.py` - ✅ Working
- ACP benchmark tests with BitNet models - ✅ Working

### Known Issues
- BitNet models require `--force-react` as they don't support native tool calling
- BitNet backend requires separate `llama-server` process running
- Intermediate conversion files (~8GB) should be deleted after model setup: `model.safetensors`, `ggml-model-f32.gguf`

---

## [R02] - 03-10-2026

### Added
- **`--stream` flag** for CLI - enables token-by-token streaming output for better UX on slow connections
  - Works in both `run` and `chat` commands
  - Shows output as it's generated instead of waiting for complete response
- **Comprehensive CLI help** - main `-h` now shows all available options for run/chat commands

### Changed
- Version tags updated from R01 to R02 across all files
- **Test output verbosity** - no more truncation, shows full content for debugging

### Fixed
- **Small model tool calling** - Identified working models and optimal settings:
  - `functiongemma:270m` (270M params) - ✅ Works, ~5s response
  - `qwen2.5:0.5b` (494M params) - ✅ Works, ~7s response
  - `granite4:350m` (352M params) - ✅ Works, ~10s response
- **Test integrity issues** - Fixed examples that were providing answers in prompts:
  - `05_tool_tests.py` - Now asks questions without providing expressions/code
  - `10_skills_demo.py` - Agent generates skill content autonomously
  - `11_skill_creator_test.py` - Tests actual skill creation, not copying

### Known Issues
- `smollm:135m` and `gemma3:270m` don't support tools (HTTP 400)
- `qwen2.5-coder:0.5b` and `qwen3:0.6b` output tool calls as text instead of executing

---

## [R01] - 03-09-2026 to 03-10-2026

### Added
- **Fuzzy argument name matching** for tool invocation - handles small model hallucinations of argument names (e.g., `filepath` → `path`, `data` → `content`)
- **Nested tool_args extraction** - handles when models output `{"tool": "name", "tool_args": {...}}` format
- **Test scripts for all platforms**:
  - `test.sh` / `test.cmd` - Run all 11 examples
  - `test-quick.sh` / `test-quick.cmd` - Run 7 quick tests (skips benchmarks)
  - `run.sh` / `run.cmd` - Interactive menu for single example selection
- **Environment variables for test configuration**:
  - `AGENTNOVA_VERBOSE=1` - Show detailed tool calls
  - `AGENTNOVA_TIMEOUT=120` - Timeout per test in seconds
  - `AGENTNOVA_MODEL=<model>` - Override default model
- **Proper exit codes** for all test scripts (0=success, 1=failure)
- **Tool verification** in tests - detects when models hallucinate answers without calling tools
- **YAML validation** for skill files with partial credit for incomplete skills
- **datetime skill** - Date and time utilities
- **web_search skill** - Web search capabilities
- **Example 11**: `11_skill_creator_test.py` - Benchmark skill creation across models

### Changed
- **Trimmed skill-creator SKILL.md** from 373 lines to 111 lines (70% reduction) - made framework-agnostic
- **Improved test verbosity** with detailed step output showing tool calls and results
- **Fixed 08_robust_comparison.py** - no longer deletes results file on startup (proper resumability)
- **Rewrote 05_tool_tests.py** with tool verification and proper expected values for all tests
- **Rewrote 11_skill_creator_test.py** with YAML validation, timeout handling, and detailed error reporting

### Fixed
- **Tool invocation failures** when small models pass wrong argument names
- **False positive test results** when models hallucinate without using tools
- **Resumability bug** in 08_robust_comparison.py that deleted progress on restart

### Technical Details
- Added `_fuzzy_match_args()` method in `agentnova/core/tools.py` with alias dictionary for common argument variants
- Added nested argument extraction in `_normalize_args()` in `agentnova/core/agent.py`
- Argument aliases: `filepath→path`, `data→content`, `expr→expression`, `search→query`, `cmd→command`, `uri→url`

---

## [R00] - 03-09-2026

### Added
- **Skills system** following Agent Skills specification
- **skill-creator skill** - OpenClaw's platform-agnostic skill generator
- **Progressive disclosure** - three-level loading (metadata, instructions, resources)
- **SkillLoader** and **SkillRegistry** for skill management
- **Example 10**: `10_skills_demo.py` - Skills system demonstration
- **CLI improvements** with `/save` and `/load` commands for conversation persistence
- **Remote Ollama support** via environment variables:
  - `OLLAMA_TIMEOUT` - Request timeout
  - `OLLAMA_MAX_RETRIES` - Max retry attempts
  - `OLLAMA_RETRY_DELAY` - Initial retry delay

### Changed
- Renamed from earlier development versions to R00 as first tagged release
- Improved error messages and validation

---

## [R0] - 02-06-2026 to 03-09-2026

### Added
- **Core framework** with zero external dependencies (stdlib only)
- **Agent class** with ReAct loop supporting:
  - Native Ollama tool-calling protocol
  - Text-based ReAct fallback for non-tool models
  - Streaming responses via generator interface
  - Multi-step reasoning with configurable max steps
- **OllamaClient** - Zero-dependency HTTP wrapper using urllib
- **ToolRegistry** - Decorator-based tool registration with:
  - Auto-generated JSON schemas from Python type hints
  - Tool subset selection for different agents
  - Fuzzy tool name matching for small model hallucinations
- **Memory system** - Sliding-window conversation memory with:
  - Optional LLM-based summarization
  - Turn archiving when window fills
- **Orchestrator** - Multi-agent routing with:
  - Router mode (LLM picks best agent)
  - Pipeline mode (sequential chain)
  - Parallel mode (concurrent execution with merge)
- **Built-in tools**:
  - `calculator` - Safe math expression evaluator
  - `shell` - Shell command execution with timeout
  - `read_file` / `write_file` - File I/O
  - `list_directory` - Directory listing
  - `http_get` - HTTP GET requests
  - `web_search` - DuckDuckGo search (no API key)
  - `python_repl` - Python code execution
  - `save_note` / `get_note` / `list_notes` - Note storage
- **Small model support** (≤1.5B parameters):
  - Fuzzy tool name matching
  - Argument auto-fixing
  - JSON response cleaning
  - Unicode normalization
  - ReAct text parsing fallback
- **Examples**:
  - `01_basic_agent.py` - Simple Q&A demo
  - `02_tool_agent.py` - Tool calling demo
  - `03_orchestrator.py` - Multi-agent routing demo
  - `04_comprehensive_test.py` - Full test suite
  - `05_tool_tests.py` - Tool-specific tests
  - `06_interactive_chat.py` - Interactive CLI chat
  - `07_model_comparison.py` - Model benchmark (15 tests)
  - `08_robust_comparison.py` - Progress-saving comparison
  - `09_expanded_benchmark.py` - Expanded benchmark (25 tests)
- **CLI interface** (`cli.py`) with:
  - Chat mode with tool support
  - Model listing
  - Tool listing
  - Skill listing
  - Debug and verbose modes
  - Fast mode for quicker responses

### Supported Models (Tool-calling)
- Meta Llama: llama3, llama3.1, llama3.2, llama3.3
- Mistral AI: mistral, mixtral, mistral-nemo, codestral
- Alibaba Qwen: qwen2, qwen2.5, qwen3, qwen2.5-coder
- Cohere: command-r, command-r7b
- DeepSeek: deepseek, deepseek-coder, deepseek-v2/v3
- Microsoft Phi: phi-3, phi-4
- Google Gemma: functiongemma
- Others: yi, internlm2, solar, glm4, hermes, nemotron

### Tested Small Models (≤1.5B)
| Rank | Model | Score | Notes |
|------|-------|-------|-------|
| 🥇 | qwen2.5-coder:0.5b | 93% | Best overall |
| 🥈 | granite3.1-moe:1b | 80% | Strong knowledge |
| 🥉 | llama3.2:1b | 80% | 128k context |

---

## [R1-R7] - 02-08-2026 to 02-17-2026

Early development iterations building the core framework.

### R7 (02-16-2026 to 02-17-2026)
- 11 commits
- Further refinements and testing

### R6 (02-16-2026)
- 1 commit
- Minor update

### R4 (02-09-2026)
- 8 commits
- Bug fixes and improvements

### R3 (02-09-2026)
- 4 commits
- Feature additions

### R2 (02-08-2026 to 02-09-2026)
- 6 commits
- Core functionality expansion

### R1 (02-08-2026)
- 4 commits
- Initial agent implementation

---

## Version Naming Convention

- **R0, R1, R2...** - Development iterations
- **R00, R01, R02...** - Tagged releases
- Each tagged release includes all changes from development iterations since the previous release

---

## Small Model Tool Calling Guide

### Models that WORK (≤600M params)
| Model | Size | Tool Support | Speed |
|-------|------|--------------|-------|
| `functiongemma:270m` | 270M | ✅ Native | ~5s |
| `qwen2.5:0.5b` | 494M | ✅ Native | ~7s |
| `granite4:350m` | 352M | ✅ Native | ~10s |

### Optimal Settings for Small Models
```python
model_options={
    "temperature": 0.0,    # Deterministic
    "num_ctx": 1024,       # Smaller context
    "num_predict": 512,    # Limit output
}
```

### Models that DON'T work
- `smollm:135m` - No tool support (HTTP 400)
- `gemma3:270m` - No tool support (HTTP 400)
- `qwen2.5-coder:0.5b` - Outputs tool calls as text
- `qwen3:0.6b` - Outputs tool calls as text

---

## Links

- **Repository**: https://github.com/VTSTech/AgentNova
- **Author**: [VTSTech](https://www.vts-tech.org)
- **Inspiration**: OpenClaw

---

*This changelog is maintained by VTSTech. For the full commit history, see [GitHub Commits](https://github.com/VTSTech/AgentNova/commits/main/).*
