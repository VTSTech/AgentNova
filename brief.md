# Codebase Intelligence Brief: AgentNova

> Generated: 04-05-2026 | Auditor: Super-Z | Commit: dae4835 (R04.5)

---

## Project Identity

| Field | Value |
|-------|-------|
| **Purpose** | Minimal, hackable agentic framework for running AI agents entirely locally with Ollama, BitNet, or llama-server/TurboQuant backends. Includes TurboQuant server lifecycle management with Ollama model registry. |
| **Tech Stack** | Python 3.9+, zero runtime dependencies (stdlib only: urllib, json, subprocess, dataclasses, threading, sqlite3, ast, mmap, struct) |
| **Entry Point** | `agentnova/cli.py:main` (CLI) or `from agentnova import Agent` (Python API) |
| **Build/Run** | `pip install -e ".[dev]"` (dev: pytest, black, ruff) |
| **Test Command** | `pytest` (unit) or `python -m agentnova.examples.01_quick_diagnostic` (integration) |
| **Package** | PyPI: `agentnova` · CLI entry points: `agentnova` + `localclaw` (backward-compat) |
| **Version** | 0.4.5 (R04.5) · Status: Alpha |

---

## Architecture Map

```
agentnova/
├── core/           → Data types, models, memory, tool parsing, security helpers, OpenResponses spec, persistent memory (SQLite), model family config
├── tools/          → Tool registry (decorator-based), 19 built-in tools, sandboxed Python REPL
├── backends/       → LLM inference backends (Ollama, LlamaServer with BitNet mode) with dual API (OpenResponses + OpenAI Chat-Completions)
├── backends/ollama_registry.py → Ollama model registry: discovers models from manifests, resolves GGUF blob paths, reads binary headers via mmap (architecture, head_dim, quantization, context_length), TurboQuant compatibility checking, recommended KV cache config
├── skills/         → AgentSkills spec loader (YAML frontmatter, SPDX license validation, compatibility checking)
├── soul/           → Soul Spec v0.5 loader (persona packages with 3-level progressive disclosure)
├── souls/          → Pre-built soul packages: nova-helper (diagnostic), nova-skills (skill-guided)
├── examples/       → 12 benchmark/test suites (basic agent through analogical reasoning, GSM8K 50q)
agent.py            → Core Agent class: OpenResponses agentic loop (prompt → tool → observe → repeat)
agent_mode.py       → Autonomous agent mode: state machine (IDLE → WORKING → PAUSED → STOPPING) with rollback, memory isolation
orchestrator.py     → Multi-agent orchestration: router (keyword/LLM), pipeline (sequential), parallel (threaded)
turbo.py            → TurboQuant server lifecycle manager: start/stop/status detached llama-server processes, persistent state (PID file + JSON state), auto-detect KV cache config from weight quantization, TurboQuant compatibility checking (head_dim ≥ 128)
acp_plugin.py       → ACP v1.0.6: status reporting, activity logging, A2A messaging, batch context manager, health tracking, todo sync
cli.py              → Full CLI: run, chat, agent, models, tools, test, soul, config, version, modelfile, skills, sessions, update, turbo (list/start/stop/status)
config.py           → Centralized config from env vars. Factory functions for dynamic defaults. ACP credentials. TurboQuant config.
shared_args.py      → Shared CLI argument definitions (DRY for run/chat/agent parsers) + SharedConfig dataclass
colors.py           → Shared ANSI color utilities (Color class, pad_colored, visible_len)
model_discovery.py  → Ollama model listing, fuzzy model name matching, benchmark model selection
```

### Skip List

- `localclaw/`, `localclaw-redirect/` — legacy backward-compat redirects, just re-exports
- `audit/` — contains audit page images, not code
- `tests/` — standard pytest unit tests, not critical for framework understanding
- `.git/`, `AgentNova.ipynb` — Colab notebook, not core code
- All `__pycache__/` directories

---

## Critical Files Index

### `agentnova/agent.py` — Core Agentic Loop (1587 lines)
- **Purpose**: Implements the entire OpenResponses agentic loop. Every tool call, Final Answer extraction, error recovery, and tool_choice enforcement flows through here. This IS the framework.
- **Blast radius**: Imported by `cli.py`, `orchestrator.py`, `agent_mode.py`. Every CLI command creates an Agent instance.
- **Key signatures**:
  ```python
  class Agent:
      def __init__(self, model, tools=None, backend=None, max_steps=5,
                   memory_config=None, debug=False, system_prompt=None,
                   soul="nova-helper", soul_level=3, num_ctx=None,
                   temperature=None, top_p=None, num_predict=None,
                   tool_choice="auto", allowed_tools=None, skills_prompt=None,
                   retry_on_error=True, max_tool_retries=2, **kwargs):
          ...
      def run(self, prompt: str, stream: bool = False) -> AgentRun:
          """Main agentic loop. Returns AgentRun with final_answer."""
  ```
- **Critical kwargs** (via `**kwargs`): `response_format` (enables JSON mode, disables tools), `session_id` (activates PersistentMemory), `persistent`/`memory_db` (explicit persistent memory), `confirm_dangerous` (callback for dangerous tool approval)
- **Critical internal state**: `_expecting_final_answer`, `_last_successful_result`, `_error_tracker`, `_response_history`, `_response_format`, `_confirm_dangerous`, `_is_persistent`, `_is_bitnet`
- **BitNet detection** (lines 273-290): Checks MODEL family via `detect_family(model)`, NOT backend type. A non-BitNet model on the BitNet backend gets full context/prompts. Only true BitNet models get tight memory (max_messages=6) and lean default prompt.
- **Gotchas**: `tools` param accepts 4 types (`ToolRegistry | list[str] | list[Tool] | None`). `response_format` and tools are **mutually exclusive** (lines 232-236). `confirm_dangerous` is NOT wired to `tools` param — it's an execution-time gate.

### `agentnova/turbo.py` — TurboQuant Server Lifecycle Manager (661 lines) **[NEW in R04.5]**
- **Purpose**: End-to-end lifecycle management for llama-cpp-turboquant server. Discovers Ollama models from manifests, resolves GGUF blob paths, reads model metadata directly from binary headers, starts/stops detached llama-server processes with full TurboQuant configuration.
- **Blast radius**: Imported by `cli.py` (cmd_turbo). Standalone module — no imports by other core modules.
- **Key types**:
  ```python
  @dataclass
  class TurboState:
      pid: int; model_name: str; blob_path: str; port: int; ctx: int
      cache_type_k: str; cache_type_v: str; turbo_mode: str
      flash_attn: bool; sparsity: float; started_at: float
      # Persistence: save() → ~/.agentnova/turbo.state, load() from file
  
  def start_server(model_name, ...) -> TurboState   # Detached Popen, health poll
  def stop_server(force=False) -> bool               # SIGTERM, 10s wait, SIGKILL fallback
  def get_status() -> Optional[TurboState]            # PID liveness check
  def print_model_list(models, source, backend_url)  # Formatted table with TurboQuant compat
  def print_status(state)                             # Server status with usage examples
  ```
- **Environment variables**: `TURBOQUANT_SERVER_PATH` (default: `llama-server`), `TURBOQUANT_PORT` (default: `8764`), `TURBOQUANT_CTX` (default: `8192`)
- **State persistence**: `~/.agentnova/turbo.state` (JSON) + `~/.agentnova/turbo.pid` (PID file). Survives across CLI invocations. `_get_running_state()` checks PID liveness, auto-cleans stale state.
- **Auto-detection**: If `--turbo-k`/`--turbo-v` not specified, calls `recommended_turbo_config(weight_quant)` from ollama_registry to auto-select optimal KV cache types based on weight quantization.
- **Compatibility check**: Validates `head_dim >= 128` for TurboQuant KV cache block alignment. Warns on incompatible models (no turbo KV), raises RuntimeError if turbo cache types explicitly requested on incompatible model.
- **Gotchas**: Server starts detached (`start_new_session=True`), stdout/stderr/devnull'd. Health check polls `/health` endpoint. No dependency on Ollama being running — reads manifests directly from `~/.ollama/models/`.

### `agentnova/backends/ollama_registry.py` — Ollama Model Registry (481 lines) **[NEW in R04.5]**
- **Purpose**: Discovers Ollama models by reading manifest files from `~/.ollama/models/manifests/`, resolves GGUF blob paths, reads binary GGUF headers via `mmap` to extract architecture, head_dim, n_heads, n_layers, context_length, and weight quantization. Provides TurboQuant compatibility checking and recommended KV cache configuration.
- **Blast radius**: Imported by `turbo.py` (primary consumer). Standalone module.
- **Key types**:
  ```python
  @dataclass
  class OllamaModel:
      name: str; repo: str; tag: str; blob_path: Path; size_bytes: int
      weight_quant: str; architecture: str; head_dim: int; n_heads: int
      n_layers: int; context_length: int
      # Properties: turbo_compatible (head_dim >= 128), size_human, exists

  def discover_models(ollama_dir=None, only_existing=True) -> list[OllamaModel]
  def find_model(model_name, ollama_dir=None) -> Optional[OllamaModel]
  def recommended_turbo_config(weight_quant) -> dict  # K/V cache types + reason
  ```
- **GGUF binary parsing**: Uses `mmap.find()` for fast byte-level key search (no sequential KV parsing). Reads `general.file_type` (uint32) for quantization detection, `general.architecture` (string) for architecture, architecture-specific keys for head_dim/embed_length/block_count/context_length. Maps 37+ GGUF file_type constants including TurboQuant-specific TQ4_1S and TQ3_1S.
- **Recommended TurboQuant config**: High-quality weights (F32/F16/BF16/Q8_0) → symmetric turbo3/turbo3; TurboQuant weights (TQ*) → asymmetric q8_0/turbo4; Lower-bit weights (Q4_K_M and below) → asymmetric q8_0/turbo4. Based on TheTom's turboquant_plus findings.
- **Three-tier model matching**: `find_model()` tries exact (repo+tag), fuzzy (repo only), substring (name containment).
- **Gotchas**: `_GGUF_MAGIC = 0x46554747` (little-endian "GGUF"). `_parse_ollama_name()` handles `library/repo:tag` format. `_filename_heuristic()` has 47 candidate patterns for when GGUF header is unreadable. `OLLAMA_BLOBS_DIR` path resolution: manifest digest `sha256:<hex>` → blob file `sha256-<hex>`.
- **Constants**: `OLLAMA_MODELS_DIR` (`~/.ollama/models`), `_TURBO_D = 128` (TurboQuant head_dim minimum).

### `agentnova/core/tool_parse.py` — Tool Call Extraction (688 lines)
- **Purpose**: Parses tool calls from model text output in 4+ formats. Central to how ReAct tool calling works.
- **Blast radius**: Only imported by `agent.py`, but critical to it.
- **Key signatures**:
  ```python
  class ToolParser:
      def __init__(self, tool_names: list[str])
      def parse(self, content: str) -> list[ParsedCall]
      def is_final_answer(self, content: str) -> bool
      def extract_final_answer(self, content: str) -> str
  ```
- **Supported formats**: Plain ReAct (`Action: name\nAction Input: {json}`), JSON-wrapped ReAct, Markdown code block JSON, simultaneous tool call + Final Answer.
- **R04.4 change**: Added `ast.literal_eval` fallback (line 413-422) for single-quote Python dicts: `{'expression': '15 + 27'}` now handled correctly, not just `{"expression": "15 + 27"}`.
- **Gotchas**: If model outputs both a tool call AND a `Final Answer:` in the same response, the Final Answer takes priority. OpenResponses spec: NO fuzzy matching on tool names in the parser — names must match exactly.

### `agentnova/core/helpers.py` — Fuzzy Matching, Arg Normalization, Security
- **Purpose**: God-module for small model support. Fuzzy tool name matching, argument normalization, expression synthesis from natural language, security utilities (path validation, command blocklist, SSRF protection), repetition detection.
- **Blast radius**: Imported by `builtins.py` (security), `tool_parse.py` (fuzzy matching), `agent.py` (argument synthesis), and transitively everything.
- **Key functions**:
  ```python
  def fuzzy_match(query, candidates, threshold=0.4) -> str | None
  def normalize_args(args, expected_params, tool_name="") -> dict
  def sanitize_command(command) -> tuple[bool, str, str]  # (safe, error, original)
  def validate_path(path, allowed_dirs=None) -> tuple[bool, str]
  def is_safe_url(url, block_ssrf=True) -> tuple[bool, str]
  def detect_and_fix_repetition(text) -> str  # Fix degenerate loops from small models
  ```
- **Gotchas**: `sanitize_command()` returns the ORIGINAL command unmodified — security is purely rejection-based. `validate_path()` allows `/tmp`, `/home`, and system temp dirs. Config default: `["./output", "./data", "/tmp"]`.

### `agentnova/core/model_family_config.py` — Unified Model Family Configuration (530 lines)
- **Purpose**: Single source of truth for all model-family-specific settings: stop tokens, prompt formatting, tool format, temperature, thinking modes, few-shot preferences. Replaces separate `model_config.py`.
- **Blast radius**: Imported by `agent.py`, `backends/ollama.py`, `backends/llama_server.py`, `core/tool_parse.py`.
- **Key functions**:
  ```python
  def detect_family(model_name: str) -> str | None     # Priority-ordered family detection
  def get_family_config(family: str) -> ModelFamilyConfig  # Alias → direct → partial → default
  def get_model_config(model_name: str) -> ModelFamilyConfig  # Unified: detect_family → get_family_config
  ```
- **R04.4 changes**: Family alias system `_FAMILY_ALIASES` (line 327-329): `bitnet → llama` (BitNet 1.58 uses LLaMA 3 tokenizer). `detect_family()` now includes `"bitnet"` in priority list. `get_family_config()` resolves aliases before direct/partial matching.
- **Families**: gemma3, granite, granitemoe, qwen2, qwen3, qwen35, llama, dolphin, deepseek-r1, deepseek (10 families total).
- **Gotchas**: `detect_family()` returns the most specific family string (e.g., "qwen2.5") but `FAMILY_CONFIGS` only stores base families (e.g., "qwen2"). `get_family_config()` bridges this via partial matching.

### `agentnova/core/persistent_memory.py` — SQLite-Backed Persistent Memory (R04.3)
- **Purpose**: `PersistentMemory(Memory)` subclass that persists all messages to `~/.agentnova/memory.db` via SQLite (WAL mode). Same sliding-window behavior as in-memory `Memory`, but full history retained in DB.
- **Blast radius**: Used by `Agent.__init__()` when `session_id` or `persistent=True` is passed.
- **Key API**:
  ```python
  class PersistentMemory(Memory):
      def __init__(self, session_id=None, db_path=None, config=None, auto_save=True):
      def save(self) -> str; def load(self) -> int; def close(self) -> None; def clear(self) -> None
      def list_sessions(db_path=None) -> list[dict]; def delete_session(session_id, db_path=None) -> bool
  ```
- **Schema**: `sessions` + `messages` tables with FK cascade, WAL journal mode.
- **Gotchas**: `close()` must be called on exit or Ctrl+C to flush WAL. CLI handles this via `_build_agent()` exit paths. Python API users MUST call `agent.memory.close()`.

### `agentnova/backends/ollama.py` — Primary Backend
- **Purpose**: Dual API backend supporting both OpenResponses (`/api/chat`) and OpenAI Chat-Completions (`/v1/chat/completions`). Handles streaming, tool support detection, thinking model handling.
- **Blast radius**: Instantiated by `get_backend()` in cli.py and orchestrator.py.
- **Gotchas**: Tool support detection is per-model (NOT per-family). Cache: `~/.cache/agentnova/tool_support.json`.

### `agentnova/backends/llama_server.py` — llama-server / BitNet Backend (merged, R04.2+R04.4+R04.5)
- **Purpose**: `LlamaServerBackend(OllamaBackend)` for llama.cpp / TurboQuant servers. BitNetBackend is now a 63-line thin wrapper that sets `bitnet_mode=True`.
- **Registry aliases**: `llama-server`, `llama_server`, `bitnet` all resolve here.
- **Config**: `LLAMA_SERVER_BASE_URL` (localhost:8764), `BITNET_BASE_URL` (localhost:8765).
- **R04.4 changes**: `/props` fallback for model name discovery. BitNet conversation budgeting (`_BITNET_PROMPT_BUDGET=1024`, `_BITNET_MAX_EXCHANGES=4`). `_sanitize_for_bitnet()` strips crash-prone markdown. `_truncate_for_bitnet()` budget-aware truncation. `repeat_penalty=1.3` for BitNet (was 1.2). Turn-bleed guards (`\nUser:`, `\nAssistant:` stop tokens). Family-aware prompt formatting via `_messages_to_prompt(model=)`.
- **R04.5 change**: Default port changed from `8080` to `8764` to align with TurboQuant.
- **Gotchas**: `_is_actual_bitnet` checks `detect_family(model)`, not `self._bitnet_mode`. Non-BitNet models on the BitNet backend receive full context and family-correct formatting.

### `agentnova/backends/__init__.py` — Backend Registry
- **Purpose**: `_BACKENDS` dict + `get_backend()` factory + `register_backend()`.
- **R04.2 change**: BitNet merged — `_BITNET_ALIASES = {"bitnet"}` routes to `LlamaServerBackend(bitnet_mode=True)`. `BitNetBackend` kept as backward-compat import only.
- **Gotchas**: `get_default_backend()` reads `AGENTNOVA_BACKEND` env var at call time, not import time.

### `agentnova/tools/builtins.py` — All 19 Built-in Tools
- **Purpose**: calculator, shell, read_file, write_file, list_directory, http_get, python_repl, get_time, get_date, web_search, parse_json, count_words, count_chars, read_file_lines, find_files, edit_file, todo.
- **Blast radius**: Instantiated via `make_builtin_registry()` → `BUILTIN_REGISTRY`. Imported by cli.py for every command.
- **Security**: Calculator uses `eval()` with `{"__builtins__": {}}` + `MAX_EXPONENT=10000`. Shell uses `shell=True` with `sanitize_command()`. File ops use `validate_path()`. HTTP uses `is_safe_url()`. Python REPL runs in sandboxed subprocess. Response limits: files 512KB, HTTP 256KB.
- **Audit logging**: `shell()`, `write_file()`, `edit_file()` log to `~/.agentnova/audit.log` (JSON-lines, fire-and-forget).
- **Todo tool**: Dispatch-based (`_todo_dispatch`) with actions: add, list, complete, remove, clear. Module-level `_todo_store` — shared across all agents in same process.
- **Dangerous flag**: `shell`, `write_file`, `edit_file` have `dangerous=True`. Enforced by `confirm_dangerous` callback in Agent.

### `agentnova/core/memory.py` — Conversation Memory
- **Purpose**: Sliding window conversation history with message-count pruning. Preserves system prompt and recent messages.
- **Gotchas**: `_prune_if_needed()` triggers at `max_messages * 0.8` (default 40 messages). NO actual summarization — just drops old messages.

### `agentnova/tools/registry.py` — Tool Registry
- **Purpose**: Manages tool registration (decorator-based), subset creation, JSON Schema generation.
- **Gotchas**: `subset()` uses exact matching only. `get_fuzzy()` threshold is 0.6 (vs helpers.py's 0.4). The `@tool` decorator creates a NEW registry each time.

### `agentnova/config.py` — Central Configuration (241 lines)
- **Purpose**: Single source of truth for all URLs, defaults, security settings, ACP credentials, TurboQuant config.
- **Key defaults**: `OLLAMA_BASE_URL` (localhost:11434), `BITNET_BASE_URL` (localhost:8765), `LLAMA_SERVER_BASE_URL` (localhost:8764), `TURBOQUANT_SERVER_PATH` (llama-server), `TURBOQUANT_PORT` (8764), `TURBOQUANT_CTX` (8192), `DEFAULT_MODEL` (backend-dependent: qwen2.5:0.5b for Ollama, bitnet-b1.58-2b-4t for BitNet, default for llama-server), `MAX_STEPS` (10).
- **R04.5 changes**: Added `TURBOQUANT_SERVER_PATH`, `TURBOQUANT_PORT`, `TURBOQUANT_CTX` env vars. `LLAMA_SERVER_BASE_URL` default changed from `http://localhost:8080` to `http://localhost:8764` to match TurboQuant default port.
- **R04.4 change**: `Config.default_model` uses `_get_default_model()` factory function that re-reads `AGENTNOVA_BACKEND` and `AGENTNOVA_MODEL` on each instantiation. `_get_num_ctx()` also reads fresh.
- **ACP credentials**: `ACP_USER` (default: admin), `ACP_PASS` (default: secret) — env overridable.
- **Gotchas**: Module-level constants ARE set at import time, but `Config` dataclass fields use `default_factory` functions that re-evaluate on each instantiation. `get_config(reload=True)` forces fresh read.

### `agentnova/shared_args.py` — CLI Argument Deduplication (344 lines)
- **Purpose**: `add_agent_args(parser, tools_default)` adds ~20 shared args to run/chat/agent parsers. `SharedConfig` dataclass for example scripts.
- **Covers**: `--model`, `--backend`, `--api`, `--tools`, `--soul`, `--session`, `--response-format`, `--confirm`, `--skills`, `--no-retry`, `--max-retries`, `--truncation`, `--num-ctx`, `--temperature`, `--top-p`, `--timeout`, `--acp`, `--verbose`, `--debug`, `--force-react`.

### `agentnova/cli.py` — Full CLI (1975 lines)
- **Commands**: run, chat, agent, config, models, modelfile, sessions, skills, soul, test, tools, turbo, update, version (alphabetically ordered).
- **R04.5 changes**: New `turbo` subcommand with sub-subcommands: `list` (Ollama models for TurboQuant), `start` (launch llama-server with TurboQuant config), `stop` (graceful shutdown), `status` (running server info). `cmd_models()` — `--tool-support` now checks cache and skips already-tested models; `--no-cache` forces re-test. Help text updated accordingly.
- **Key helpers**: `_build_agent(args, config)` centralizes Agent construction. `_print_session_header()` for chat/agent headers. `_make_confirm_callback()` for `--confirm` flag. `_load_tool_cache()` / `_save_tool_cache()` for atomic tool support cache persistence.
- **Gotchas**: `cmd_models()` uses `get_cached_tool_support()` before testing. `--no-cache` overrides this. Cache file: `~/.cache/agentnova/tool_support.json` (platform-appropriate path).

### `agentnova/orchestrator.py` — Multi-Agent Orchestration (487 lines)
- **Modes**: Router (keyword/LLM), Pipeline (sequential), Parallel (ThreadPoolExecutor).
- **Gotchas**: `_select_agent_with_llm()` hardcodes `get_backend("ollama")`. Pipeline appends `[Previous output: ...]` as plain text. Vote strategy normalizes to lowercase first 100 chars.

### `agentnova/agent_mode.py` — Autonomous Agent Mode (855 lines)
- **State machine**: IDLE → WORKING → PAUSED → STOPPING with pause/resume/rollback.
- **R04.3 addition**: `reset_memory_between_steps` parameter — clears agent memory at start of each step (default False).
- **R04.2 addition**: `_inject_context(memory, step_info)` prepends `[Step N of M] Goal: ...` headers for multi-step tasks.

---

## Request / Execution Lifecycle

```
User Prompt
    │
    ▼
1. Agent.__init__()                                           # agent.py:105
   ├── BitNet detection: detect_family(model) == "bitnet"    # agent.py:281-290
   │   └── (NOT backend type — non-BitNet on BitNet backend OK)
   ├── If _is_bitnet: tighten memory (max=6, keep_recent=4)   # agent.py:297-298
   ├── If session_id or persistent: PersistentMemory()        # core/persistent_memory.py
   │   └── memory.load() → restores from SQLite
   ├── If soul specified: soul/loader.py → load_soul()        # soul/loader.py
   │   ├── build_system_prompt_with_tools(soul, tools, level) # Dynamic tool injection
   │   └── soul.allowed_tools filters tool registry            # Additional tool restriction
   ├── If skills specified: SkillLoader → SkillRegistry        # skills/loader.py
   │   └── to_system_prompt_addition()
   ├── If response_format set → clear tools, force tool_choice="none"  # agent.py:232-236
   ├── If _is_bitnet: lean default prompt (<500 chars)        # agent.py:437-446
   ├── Create ToolParser(tools.names())                        # core/tool_parse.py
   ├── Memory.add("system", system_prompt)                    # core/memory.py
   └── Initialize ErrorRecoveryTracker                          # core/error_recovery.py
    │
    ▼
2. Agent.run(prompt)                                            # agent.py:471
   ├── Create OpenResponses Response object                      # core/openresponses.py
   ├── Memory.add("user", prompt)
    │
    ▼
3. Agentic Loop (for step in range(max_steps))                  # Default: 5 steps
   ├─ 3a. Backend.generate(memory.get_messages())               # backends/ollama.py
   │       ├── Forward model_config.stop_tokens via backend_kwargs["stop"]  # agent.py:_generate
   │       ├── Forward response_format via backend_kwargs (JSON mode)
   │       ├── If api_mode=OPENRE:  POST /api/chat
   │       └── If api_mode=OPENAI:  POST /v1/chat/completions
   │
   ├─ 3b. Check finish_reason (length → incomplete, content_filter → failed)
   │
   ├─ 3c. Check for tool calls (two sources):
   │       ├── NATIVE: backend returns tool_calls in response
   │       └── REACT: ToolParser.parse(content) extracts from text
   │       └── (R04.4) ast.literal_eval fallback for single-quote dicts
   │
   ├─ 3d. If tool calls found:
   │       ├── Final Answer Enforcement: if _expecting_final_answer, force last result
   │       ├── Check confirm_dangerous callback → block if denied
   │       ├── Check allowed_tools → block if not in list
   │       ├── Execute via _execute_tool(name, args, prompt)
   │       ├── Track success/failure in ErrorRecoveryTracker
   │       │   └── On failure + retry_on_error: inject retry context
   │       ├── Set _expecting_final_answer for simple/terminal tool results
   │       └── Continue agentic loop
   │
   ├─ 3e. Check for "Final Answer:" in content
   │       ├── Enforce tool_choice=required if no tools called yet
   │       └── Extract → create MessageItem → break
   │
   └─ 3f. No tool call, no Final Answer → accept as direct response
         (unless tool_choice=required → inject guidance, continue)
```

### TurboQuant Server Lifecycle (R04.5)

```
agentnova turbo start <model>
    │
    ▼
1. start_server(model_name)                                  # turbo.py:216
   ├── Check for existing server via _get_running_state()     # PID liveness check
   │   └── Raises RuntimeError if already running
   ├── Resolve model:
   │   ├── If .gguf file → use directly
   │   └── If Ollama name → find_model() → ollama_registry    # ollama_registry.py
   │       ├── Walk manifests: ~/.ollama/models/manifests/registry.ollama.ai/
   │       ├── Parse JSON manifest → find model layer → resolve blob path
   │       ├── mmap GGUF header → read architecture, head_dim, quantization
   │       └── Check turbo_compatible (head_dim >= 128)
   ├── Auto-detect KV cache config (if not specified):
   │   └── recommended_turbo_config(weight_quant)              # ollama_registry.py:430
   │       ├── F32/F16/BF16/Q8_0 → symmetric turbo3/turbo3
   │       ├── TQ types → asymmetric q8_0/turbo4
   │       └── Q4_K_M and below → asymmetric q8_0/turbo4
   ├── _build_command() → llama-server CLI args              # turbo.py:170
   │   ├── -m <blob_path> -c <ctx> --port <port>
   │   ├── -ctk <K_cache> -ctv <V_cache>
   │   ├── [-fa] [--flash-attn-sparsity <val>] [-t <threads>]
   │   └── [extra args via -- passthrough]
   ├── subprocess.Popen(detached)                             # start_new_session=True
   ├── TurboState.save() → ~/.agentnova/turbo.state
   └── Poll /health endpoint until ready (or timeout)
```

---

## Dependency Graph

```
cli.py ─────────────────────────────────────────────────────────────┐
  ├──→ agent.py ────────────────────────────────────────────────────────┤
  │    ├── core/memory.py                                           │
  │    ├── core/persistent_memory.py → core/memory.py, sqlite3        │
  │    ├── core/tool_parse.py ─→ core/models.py                     │
  │    ├── core/error_recovery.py                                     │
  │    ├── core/openresponses.py ─→ core/models.py                    │
  │    ├── core/helpers.py ─→ (security for all tool operations)      │
  │    ├── core/model_family_config.py (unified)                      │
  │    │    └── _FAMILY_ALIASES: bitnet → llama                       │
  │    ├── tools/registry.py ─→ tools/builtins.py                    │
  │    └── soul/loader.py ─→ soul/types.py                           │
  │                                                                    │
  ├──→ orchestrator.py ─→ agent.py (creates Agent instances per card)   │
  │       └── backends/ (for LLM-based routing)                       │
  │                                                                    │
  ├──→ agent_mode.py ──→ agent.py (wraps in state machine)            │
  ├──→ skills/loader.py (via _load_skills_prompt, optional)          │
  │                                                                    │
  └──→ turbo.py ──→ backends/ollama_registry.py  **[NEW R04.5]**     │
        ├── turbo.py: start_server, stop_server, get_status            │
        ├── ollama_registry.py: discover_models, find_model            │
        ├── ollama_registry.py: _detect_weight_quant (mmap GGUF)       │
        └── ollama_registry.py: recommended_turbo_config               │
                                                                       │
config.py ← referenced by EVERYTHING above                             │
shared_args.py ← referenced by cli.py                                  │
backends/__init__.py ← referenced by agent.py, orchestrator.py        │
  └── _BITNET_ALIASES → routes to LlamaServerBackend(bitnet_mode=True)
core/tool_cache.py ← referenced by types.py, cli.py                  │
acp_plugin.py ← referenced by cli.py (optional import)                │
```

**Highest blast radius changes:**
1. `config.py` — changing a URL or default affects the entire system
2. `core/helpers.py` — changing security behavior affects all built-in tools
3. `agent.py` — changing the agentic loop affects all modes (run, chat, agent, orchestrator)
4. `core/model_family_config.py` — changing family config affects ALL model interactions
5. `backends/ollama_registry.py` — TurboQuant compatibility logic affects turbo.py and model discovery **[NEW R04.5]**

---

## Patterns & Conventions

| Aspect | Pattern |
|---|---|
| API specification | OpenResponses (https://www.openresponses.org/specification) — Items, Response state machine, tool_choice modes |
| Tool calling | Unified ReAct prompting for ALL models — model outputs `Action: name\nAction Input: {json}` |
| Error recovery | Retry-with-error-feedback: inject previous failure context into conversation so model self-corrects. Max 2 retries per failure. |
| Small model support | Fuzzy tool name matching (0.4 threshold), argument normalization with aliases, `ast.literal_eval` for single-quote dicts, repetition detection, `is_small_model()` heuristic, `_fuzzy_match_tool_name()` word mappings |
| Security | Defense-in-depth: command blocklist + injection detection (shell), path whitelist validation (file ops), SSRF pattern blocking (HTTP), sandboxed subprocess (Python REPL), response size limits, header injection prevention, dangerous tool confirmation (`--confirm`), audit logging |
| Persistent memory | SQLite-backed `PersistentMemory` extends in-memory `Memory`; auto-save on every `add()`, lazy DB connection. Session management via `--session <name>`. |
| Backend extensibility | Abstract `BaseBackend` class + `_BACKENDS` dict + `register_backend()`. 2 backend classes: OllamaBackend, LlamaServerBackend (BitNet is thin wrapper). |
| Model family config | Unified `ModelFamilyConfig` dataclass. Family detection → alias resolution → direct match → partial match → default. Family alias system for cross-family sharing. |
| TurboQuant integration | Zero-conversion Ollama model usage. GGUF binary header parsing via mmap. Head_dim ≥ 128 for KV block alignment. Auto-detect KV cache from weight quantization. Detached server lifecycle with PID/state persistence. **[NEW R04.5]** |
| Optional imports | ACP, Soul, and PersistentMemory modules wrapped in `try/except` with fallback to `None`. Check with `if X is not None` before using. |
| CLI argument DRY | `shared_args.py:add_agent_args()` adds shared args. `cli.py:_build_agent()` centralizes Agent construction. |
| Structured output | `--response-format json` → Agent sets `response_format={"type":"json_object"}`, disables tools, forces `tool_choice="none"`. |
| BitNet support | Merged into LlamaServerBackend with `bitnet_mode=True`. Model-family-gated constraints. Prompt budgeting (1024 chars), markdown sanitization, exchange cap (4), tight memory. |
| Server state persistence | `TurboState.save()` → JSON file + PID file. `_get_running_state()` validates PID liveness on load. Survives CLI restarts. **[NEW R04.5]** |

---

## Known Landmines

### Tool support detection is per-model, NOT per-family
```python
qwen2.5:0.5b     → ToolSupportLevel.NATIVE
qwen2.5-coder:0.5b → ToolSupportLevel.REACT     # Same family, different behavior!
# Cache: ~/.cache/agentnova/tool_support.json
# Test: agentnova models --tool-support
# Re-test all: agentnova models --tool-support --no-cache  [R04.5 change]
```

### `calculator()` uses `eval()` — sandboxed but still eval
```python
result = eval(expression, {"__builtins__": {}}, safe_dict)
# DANGEROUS: Adding os, sys, or __import__ to safe_dict breaks the sandbox.
# MAX_EXPONENT=10000 guards against 2**9999999 DoS.
```

### `shell()` runs with `shell=True` — security is purely rejection-based
```python
result = subprocess.run(validated_cmd, shell=True, ...)
# sanitize_command() REJECTS dangerous commands but does NOT modify input.
# Any bypass of the blocklist or injection patterns allows arbitrary execution.
```

### `validate_path()` blocks system directories but allows /tmp, /home
```python
# Config default allowed paths: ["./output", "./data", "/tmp"]
# Extend: Config(allowed_paths=["./output", "./data", "/tmp", "/custom/path"])
```

### Memory pruning drops messages without summarization
```python
# _prune_if_needed() triggers at max_messages * 0.8 (default 40)
# Just DROPS old messages — summarization_threshold name is misleading.
```

### `PersistentMemory.close()` must be called on exit
```python
# CLI handles this via _build_agent() exit paths, but Python API users
# who create Agent(session_id="x") MUST call agent.memory.close()
# or risk WAL journal growth and locked files.
```

### `response_format` and tools are mutually exclusive
```python
# Setting response_format clears all tools and forces tool_choice="none"
# JSON mode breaks ReAct format — the parser misinterprets JSON as tool calls.
# agent.py lines 232-236 enforce this.
```

### BitNet constraints gated by MODEL FAMILY, not backend type
```python
# agent.py line 288: self._is_bitnet = (_model_family == "bitnet")
# A qwen2.5 model on --backend bitnet gets FULL context, NO truncation.
# Only actual BitNet models get tight memory, lean prompt, budgeting.
```

### `_get_default_model()` reads env vars fresh, but module-level constants don't
```python
# config.py: OLLAMA_BASE_URL, BITNET_BASE_URL etc are module-level (import time)
# Config fields use default_factory for dynamic re-evaluation
# get_config(reload=True) to re-read all settings
```

### Web search depends on HTML scraping — fragile
```python
# Scrapes DuckDuckGo Lite and html.duckduckgo.com with regex.
# Any HTML structure change by DuckDuckGo silently breaks web search.
```

### `_todo_store` is module-level global — shared across all agents in same process
```python
# tools/builtins.py line 898: _todo_store: list[dict] = []
# Not per-session. All agents in the same process share the same todo list.
```

### `_parse_frontmatter()` has limited YAML support (skills/loader.py)
```python
# Custom parser — no PyYAML. Handles: key: value, key: "quoted", multiline via indentation.
# DOES NOT handle: nested objects, arrays, null, booleans, numbers without quotes.
```

### TurboQuant server stdout/stderr are discarded
```python
# turbo.py: subprocess.Popen(..., stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
# All server log output is lost. Only health check endpoint is used for readiness.
# Debug issues require running llama-server manually outside of agentnova turbo.
```

### `ollama_registry.py` GGUF parsing depends on key string positioning
```python
# _gguf_find_key() uses mm.find(key_bytes) which finds FIRST occurrence.
# If a key name appears as a substring of another key (e.g., "general.architecture" 
# inside "llama.architecture"), this would fail. Current GGUF spec makes this safe.
```

### `LLAMA_SERVER_BASE_URL` default changed from 8080 to 8764 in R04.5
```python
# Old: http://localhost:8080  (pre-R04.5)
# New: http://localhost:8764  (R04.5+)
# If you have a custom llama-server on port 8080, set:
#   LLAMA_SERVER_BASE_URL=http://localhost:8080 agentnova run ...
```

---

## Active Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Zero runtime dependencies | Python stdlib only (urllib for HTTP) | Maximizes portability, zero supply chain risk |
| Unified ReAct prompting | All models use Action/Action Input format | Consistent parsing, no per-family format detection |
| No tool call fallbacks | Model must explicitly format tool calls | Follows OpenResponses spec |
| Dual API support | OpenResponses + OpenAI Chat-Completions | Spec compliance + ecosystem integration |
| SQLite for persistence | stdlib sqlite3 with WAL mode | Zero-dep persistent memory, transactional safety |
| Path whitelist security | Whitelist-based file access | Defense in depth for agent file operations |
| Calculator via eval | Restricted eval with `__builtins__: {}` | Simplicity + full Python math without writing a parser |
| Thinking models auto-detection | `detect_family()` sets `think=False` for qwen3, deepseek-r1 | Prevents wasting tokens on thinking when tool-calling |
| Tool support per-model | Runtime testing, cached results | Model templates vary within same family |
| Default soul = nova-helper | Every Agent loads a soul unless explicitly disabled | Souls structure small model prompting |
| Dangerous tool confirmation | `--confirm` flag + callback on Agent | Explicit opt-in for destructive operations |
| JSON mode disables tools | Mutually exclusive by design | JSON output format breaks ReAct parsing |
| BitNet merged into llama-server | BitNetBackend = thin wrapper over LlamaServerBackend | Eliminated ~170 lines of duplicated code |
| Family alias system | `_FAMILY_ALIASES` dict for cross-family config sharing | BitNet → llama without duplicating config |
| DEFAULT_MODEL uses factory | `_get_default_model()` re-reads env vars on each call | Fixes frozen-at-import bug for backend switching |
| TurboQuant zero-conversion | Ollama blobs used directly as GGUF files | No `ollama convert` step, instant model loading |
| mmap GGUF header parsing | `mmap.find()` for key search, struct for value extraction | Fast, handles arbitrarily large files, no dependencies |
| Detached server lifecycle | `start_new_session=True` + PID/state file persistence | Server survives CLI exit, resumable via `turbo status/stop` |
| Default llama-server port = 8764 | Matches TurboQuant default | Reduces config friction between Ollama and TurboQuant backends |
| `--tool-support` skips cached models | Check cache before testing, `--no-cache` to override | Avoids slow repeated testing on CPU-only environments |

---

## What's Missing / Incomplete

- **No streaming for ReAct path** — `--stream` flag exists but streaming not fully implemented for the tool calling loop
- **Memory pruning has no summarization** — old messages silently dropped, not summarized
- **Pipeline mode output chaining is plain text** — `[Previous output: ...]` loses formatting and tool results
- **Parallel merge strategies are simplistic** — `vote` normalizes to lowercase first 100 chars; `best` just picks longest
- **`BackendType.OPENAI` and `BackendType.CUSTOM`** — defined in types.py but have no implementations
- **Soul Spec `HEARTBEAT.md`** — referenced in Soul Spec v0.5 but not implemented in loader
- **No ACL per-tool** — `allowed_tools` at Agent level, but no per-role or per-context permission system
- **PersistentMemory has no migration** — schema changes require manual DB deletion
- **No token budget enforcement** — CostTracker in ACP tracks costs but no hard limit in Agent
- **`_todo_store` is module-level global** — shared across all agents in same process (not per-session)
- **`check_compatibility()` in skills loader** — tries to import `packaging.version`, not available in zero-dep mode
- **TurboQuant server logs lost** — stdout/stderr devnull'd, no way to debug server-side issues from CLI **[R04.5]**
- **No `turbo` subcommand auto-completion** — CLI only, no shell completion scripts **[R04.5]**
- **`TurboState` has no schema versioning** — future format changes will break loading old state files **[R04.5]**

---

## Quick Start for Developer

1. Read the **Critical Files Index** above — each entry has purpose, blast radius, and gotchas
2. Trace the **Request / Execution Lifecycle** — this is how the entire system works end-to-end
3. Check **Known Landmines** — these save real debugging time
4. For tool changes → start with `tools/builtins.py` (definitions) and `core/helpers.py` (security)
5. For backend changes → start with `backends/ollama.py`
6. For agent loop changes → start with `agent.py` and `core/tool_parse.py`
7. For multi-agent work → start with `orchestrator.py`
8. For persistent memory → start with `core/persistent_memory.py`
9. For model family config → start with `core/model_family_config.py`
10. For CLI changes → start with `shared_args.py` (arg definitions) and `cli.py:_build_agent()`
11. For TurboQuant changes → start with `turbo.py` (server lifecycle) and `backends/ollama_registry.py` (model discovery) **[NEW R04.5]**
12. Run `pytest` after any change

Do NOT start by reading every file. Use this brief as your map and read only what you need for your specific task.

---

## Token Budget Note

> This brief is approximately **~9,500 tokens** (estimated: 33,000 characters ÷ 3.5). Target maximum: 16,000 tokens. Headroom: ~6,500 tokens (~41% of budget remaining).
