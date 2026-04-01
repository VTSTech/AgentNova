# Codebase Intelligence Brief: AgentNova

> Generated: 04-01-2026 | Auditor: Super-Z-Alpha | Commit: f07ad23 (R04.4)

---

## Project Identity

| Field | Value |
|-------|-------|
| **Purpose** | Minimal, hackable agentic framework for running AI agents entirely locally with Ollama, BitNet, or llama-server backends |
| **Tech Stack** | Python 3.9+, zero runtime dependencies (stdlib only: urllib, json, subprocess, dataclasses, threading, sqlite3) |
| **Entry Point** | `agentnova/cli.py:main` (CLI) or `from agentnova import Agent` (Python API) |
| **Build/Run** | `pip install -e ".[dev]"` (dev: pytest, black, ruff) |
| **Test Command** | `pytest` (unit) or `python -m agentnova.examples.01_quick_diagnostic` (integration) |
| **Package** | PyPI: `agentnova` · CLI entry points: `agentnova` + `localclaw` (backward-compat) |
| **Version** | 0.4.4-dev (R04.4) · Status: Alpha |

---

## Architecture Map

```
agentnova/
├── core/           → Data types, models, memory, tool parsing, security helpers, OpenResponses spec implementation, persistent memory (SQLite)
├── tools/          → Tool registry (decorator-based), 17 built-in tools, sandboxed Python REPL
├── backends/       → LLM inference backends (Ollama, BitNet, llama-server) with dual API (OpenResponses + OpenAI Chat-Completions)
├── skills/         → AgentSkills spec loader (YAML frontmatter, SPDX license validation, compatibility checking)
├── soul/           → Soul Spec v0.5 loader (persona packages with 3-level progressive disclosure)
├── souls/          → Pre-built soul packages: nova-helper (diagnostic), nova-skills (skill-guided)
├── examples/       → 12 benchmark/test suites (basic agent through analogical reasoning, GSM8K 50q)
agent.py            → Core Agent class: OpenResponses agentic loop (prompt → tool → observe → repeat)
agent_mode.py       → Autonomous agent mode: state machine (IDLE → WORKING → PAUSED → STOPPING) with rollback
orchestrator.py     → Multi-agent orchestration: router (keyword/LLM), pipeline (sequential), parallel (threaded)
acp_plugin.py       → ACP v1.0.6: status reporting, activity logging, A2A messaging, batch context manager, health tracking
cli.py              → Full CLI: run, chat, agent, models, tools, test, soul, config, version, modelfile, skills, sessions, update
config.py           → Centralized config from env vars. Single source of truth for all URLs, defaults, security
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

### `agentnova/agent.py` — Core Agentic Loop
- **Purpose**: Implements the entire OpenResponses agentic loop. Every tool call, Final Answer extraction, error recovery, and tool_choice enforcement flows through here. This IS the framework.
- **Blast radius**: Imported by `cli.py`, `orchestrator.py`, `agent_mode.py`. Every CLI command creates an Agent instance.
- **Key signatures**:
  ```python
  class Agent:
      def __init__(self, model, tools=None, backend=None, max_steps=5,
                   soul="nova-helper", soul_level=3, num_ctx=None,
                   temperature=None, tool_choice="auto", allowed_tools=None,
                   skills_prompt=None, retry_on_error=True, max_tool_retries=2,
                   **kwargs):  # kwargs: persistent, session_id, memory_db, confirm_dangerous, response_format
          ...
      def run(self, prompt: str, stream: bool = False) -> AgentRun:
          """Main agentic loop. Returns AgentRun with final_answer."""
  ```
- **Critical kwargs** (via `**kwargs`): `response_format` (enables JSON mode, disables tools), `session_id` (activates PersistentMemory), `persistent`/`memory_db` (explicit persistent memory), `confirm_dangerous` (callback for dangerous tool approval)
- **Critical internal state**: `_expecting_final_answer`, `_last_successful_result`, `_error_tracker`, `_response_history`, `_response_format`, `_confirm_dangerous`, `_is_persistent`
- **Gotchas**: `tools` param accepts 4 types (`ToolRegistry | list[str] | list[Tool] | None`). `response_format` and tools are **mutually exclusive** — setting JSON mode clears all tools. `confirm_dangerous` is NOT wired to the `tools` parameter — it's an execution-time gate.

### `agentnova/core/tool_parse.py` — Tool Call Extraction
- **Purpose**: Parses tool calls from model text output in 4+ formats. Central to how ReAct tool calling works.
- **Blast radius**: Only imported by `agent.py`, but critical to it.
- **Key signatures**:
  ```python
  class ToolParser:
      def __init__(self, tool_names: list[str]):
      def parse(self, content: str) -> list[ParsedCall]:
      def is_final_answer(self, content: str) -> bool:
      def extract_final_answer(self, content: str) -> str:
  ```
- **Supported formats**: Plain ReAct (`Action: name\nAction Input: {json}`), JSON-wrapped ReAct, Markdown code block JSON, simultaneous tool call + Final Answer.
- **Gotchas**: If model outputs both a tool call AND a `Final Answer:` in the same response, the Final Answer takes priority.

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
  ```
- **Gotchas**: `sanitize_command()` returns the ORIGINAL command unmodified — security is purely rejection-based. `validate_path()` allows `/tmp`, `/home`, and system temp dirs. Config default: `["./output", "./data", "/tmp"]`.

### `agentnova/core/persistent_memory.py` — SQLite-Backed Persistent Memory (NEW R04.3)
- **Purpose**: `PersistentMemory(Memory)` subclass that persists all messages to `~/.agentnova/memory.db` via SQLite (WAL mode). Same sliding-window behavior as in-memory `Memory`, but full history retained in DB.
- **Blast radius**: Used by `Agent.__init__()` when `session_id` or `persistent=True` is passed. Exported from `__init__.py` with graceful fallback.
- **Key API**:
  ```python
  class PersistentMemory(Memory):
      def __init__(self, session_id=None, db_path=None, config=None, auto_save=True):
      def save(self) -> str:        # Idempotent, skips existing by (session_id, seq)
      def load(self) -> int:         # Restores from DB, returns count
      def close(self) -> None:       # Closes SQLite connection
      def clear(self) -> None:       # Clears both memory AND DB rows
      def list_sessions(db_path=None) -> list[dict]:    # Static
      def delete_session(session_id, db_path=None) -> bool:  # Static
  ```
- **Schema**: `sessions` (session_id, model, created_at, updated_at, message_count, metadata) + `messages` (session_id, seq, role, content, tool_calls, tool_call_id, name, timestamp) with FK cascade.
- **Gotchas**: `close()` must be called on exit or Ctrl+C to flush WAL journal. The `_build_agent()` helper in cli.py handles this for all exit paths. If `close()` is missed, the process exit handles it but risks WAL growth.

### `agentnova/backends/ollama.py` — Primary Backend
- **Purpose**: Dual API backend supporting both OpenResponses (`/api/chat`) and OpenAI Chat-Completions (`/v1/chat/completions`). Handles streaming, tool support detection, thinking model handling.
- **Blast radius**: Instantiated by `get_backend()` in cli.py and orchestrator.py. All model communication flows here.
- **Gotchas**: Tool support detection is per-model (NOT per-family). `qwen2.5:0.5b` has native tools but `qwen2.5-coder:0.5b` is ReAct-only. Cache: `~/.cache/agentnova/tool_support.json`.

### `agentnova/backends/llama_server.py` — llama-server Backend (NEW R04.2)
- **Purpose**: `LlamaServerBackend(OllamaBackend)` for llama.cpp / TurboQuant servers. Inherits full OpenAI Chat-Completions pipeline; adds native `/completion` endpoint for OpenRE mode.
- **Registry aliases**: `llama-server` and `llama_server` both resolve here.
- **Config**: `LLAMA_SERVER_BASE_URL` (default: `http://localhost:8080`).

### `agentnova/tools/builtins.py` — All 17 Built-in Tools
- **Purpose**: calculator, shell, read_file, write_file, list_directory, http_get, python_repl, get_time, get_date, web_search, parse_json, count_words, count_chars, read_file_lines, find_files, edit_file, todo.
- **Blast radius**: Instantiated via `make_builtin_registry()` → `BUILTIN_REGISTRY`. Imported by cli.py for every command.
- **Security notes**: Calculator uses `eval()` with `{"__builtins__": {}}`. Shell uses `shell=True` with `sanitize_command()`. File ops use `validate_path()`. HTTP uses `is_safe_url()`. Python REPL runs in sandboxed subprocess. Response limits: files 512KB, HTTP 256KB.
- **Audit logging**: `shell()`, `write_file()`, `edit_file()` log to `~/.agentnova/audit.log` (JSON-lines, fire-and-forget).
- **Todo tool**: Dispatch-based (`_todo_dispatch`) with actions: add, list, complete, remove, clear. Per-agent isolation via `_todo_store` closure.
- **Dangerous flag**: `shell`, `write_file`, `edit_file` have `dangerous=True`. Enforced by `confirm_dangerous` callback in Agent.

### `agentnova/core/memory.py` — Conversation Memory
- **Purpose**: Sliding window conversation history with message-count pruning. Preserves system prompt and recent messages.
- **Gotchas**: `_prune_if_needed()` triggers at `max_messages * 0.8` (default 40 messages). NO actual summarization — just drops old messages. `summarization_threshold` name is misleading.

### `agentnova/tools/registry.py` — Tool Registry
- **Purpose**: Manages tool registration (decorator-based), fuzzy lookup, subset creation, and JSON Schema generation.
- **Gotchas**: `subset()` uses exact matching only. `get_fuzzy()` threshold is 0.6 (vs helpers.py's 0.4). The `@tool` decorator creates a NEW registry each time.

### `agentnova/skills/loader.py` — Skills System
- **Purpose**: Loads SKILL.md files with YAML frontmatter, validates spec compliance (name format, description length, SPDX license).
- **Gotchas**: Custom YAML parser handles simple values but NOT nested objects/arrays. `check_compatibility()` tries to import `packaging.version` — not available in zero-dep mode.

### `agentnova/orchestrator.py` — Multi-Agent Orchestration
- **Modes**: Router (keyword/LLM), Pipeline (sequential), Parallel (ThreadPoolExecutor).
- **Gotchas**: `_select_agent_with_llm()` hardcodes `get_backend("ollama")`. Pipeline appends `[Previous output: ...]` as plain text. Vote strategy normalizes to lowercase first 100 chars.

### `agentnova/config.py` — Central Configuration
- **Purpose**: Single source of truth for all URLs, defaults, security settings.
- **Key defaults**: `OLLAMA_BASE_URL` (localhost:11434), `BITNET_BASE_URL` (localhost:8765), `LLAMA_SERVER_BASE_URL` (localhost:8080), `DEFAULT_MODEL` (qwen2.5:0.5b), `MAX_STEPS` (10).
- **Gotchas**: `Config.from_env()` just calls `Config()` — env vars are read at module import time, not lazily. `get_config(reload=True)` to re-read.

### `agentnova/shared_args.py` — CLI Argument Deduplication
- **Purpose**: `add_agent_args(parser, tools_default)` adds ~20 shared args to run/chat/agent parsers. `SharedConfig` dataclass for example scripts.
- **Covers**: `--model`, `--backend`, `--api`, `--tools`, `--soul`, `--session`, `--response-format`, `--confirm`, `--skills`, `--no-retry`, `--max-retries`, `--truncation`, `--num-ctx`, `--temperature`, `--top-p`, `--timeout`, `--acp`, `--verbose`, `--debug`, `--force-react`.

### `agentnova/cli.py` — Full CLI
- **Commands**: run, chat, agent, models, tools, test, version, config, modelfile, skills, soul, sessions, update.
- **Key helpers**: `_build_agent(args, config)` centralizes Agent construction. `_print_session_header()` for chat/agent headers. `_make_confirm_callback()` for `--confirm` flag.
- **Sessions**: `agentnova sessions` lists/saves persistent memory sessions. `--session <name>` on run/chat/agent activates PersistentMemory.

---

## Request / Execution Lifecycle

```
User Prompt
    │
    ▼
1. Agent.__init__()                                           # agent.py:105
   ├── If session_id or persistent: PersistentMemory()        # core/persistent_memory.py
   │   └── memory.load() → restores from SQLite
   ├── If soul specified: soul/loader.py → load_soul()        # soul/loader.py
   │   └── build_system_prompt_with_tools(soul, tools, level)
   ├── If skills specified: SkillLoader → SkillRegistry        # skills/loader.py
   │   └── to_system_prompt_addition()
   ├── If response_format set → clear tools, force tool_choice="none"
   ├── Create ToolParser(tools.names())                        # core/tool_parse.py
   ├── Memory.add("system", system_prompt)                    # core/memory.py
   └── Initialize ErrorRecoveryTracker                          # core/error_recovery.py
    │
    ▼
2. Agent.run(prompt)                                            # agent.py:429
   ├── Create OpenResponses Response object                      # core/openresponses.py
   ├── Memory.add("user", prompt)
    │
    ▼
3. Agentic Loop (for step in range(max_steps))                  # Default: 5 steps
   ├─ 3a. Backend.generate(memory.get_messages())               # backends/ollama.py
   │       ├── If api_mode=OPENRE:  POST /api/chat
   │       └── If api_mode=OPENAI:  POST /v1/chat/completions
   │       └── Returns {content, tool_calls, usage, _finish_reason}
   │
   ├─ 3b. Check finish_reason (length → incomplete, content_filter → failed)
   │
   ├─ 3c. Check for tool calls (two sources):
   │       ├── NATIVE: backend returns tool_calls in response
   │       └── REACT: ToolParser.parse(content) extracts from text
   │
   ├─ 3d. If tool calls found:
   │       ├── Check confirm_dangerous callback → block if denied
   │       ├── Check allowed_tools → block if not in list
   │       ├── Execute via _execute_tool(name, args, prompt)
   │       ├── Track success/failure in ErrorRecoveryTracker
   │       │   └── On failure + retry_on_error: inject retry context
   │       ├── Check _expecting_final_answer (terminal tools only)
   │       ├── Check for simultaneous final_answer in parsed call
   │       └── Continue agentic loop
   │
   ├─ 3e. Check for "Final Answer:" in content
   │       ├── Enforce tool_choice=required if no tools called yet
   │       └── Extract → create MessageItem → break
   │
   └─ 3f. No tool call, no Final Answer → accept as direct response
         (unless tool_choice=required → inject guidance, continue)
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
  │    ├── tools/registry.py ─→ tools/builtins.py                    │
  │    └── soul/loader.py ─→ soul/types.py                           │
  │                                                                    │
  ├──→ orchestrator.py ─→ agent.py (creates Agent instances per card)   │
  │       └── backends/ (for LLM-based routing)                       │
  │                                                                    │
  ├──→ agent_mode.py ──→ agent.py (wraps in state machine)            │
  └──→ skills/loader.py (via _load_skills_prompt, optional)          │
                                                                       │
config.py ← referenced by EVERYTHING above                             │
shared_args.py ← referenced by cli.py                                  │
backends/__init__.py ← referenced by agent.py, orchestrator.py        │
core/tool_cache.py ← referenced by types.py, cli.py                  │
acp_plugin.py ← referenced by cli.py (optional import)                │
```

**Highest blast radius changes:**
1. `config.py` — changing a URL or default affects the entire system
2. `core/helpers.py` — changing security behavior affects all built-in tools
3. `agent.py` — changing the agentic loop affects all modes (run, chat, agent, orchestrator)

---

## Patterns & Conventions

| Aspect | Pattern |
|---|---|
| API specification | OpenResponses (https://www.openresponses.org/specification) — 100% compliant: Items, Response state machine, tool_choice modes |
| Tool calling | Unified ReAct prompting for ALL models — model outputs `Action: name\nAction Input: {json}`. Tool definitions NOT passed to the API. |
| Error recovery | Retry-with-error-feedback: inject previous failure context into conversation so model self-corrects. Max 2 retries per failure (configurable). |
| Small model support | Fuzzy tool name matching (0.4 threshold), argument normalization with aliases, enhanced observations with guidance, repetition detection, `is_small_model()` heuristic |
| Security | Defense-in-depth: command blocklist + injection detection (shell), path whitelist validation (file ops), SSRF pattern blocking (HTTP), sandboxed subprocess (Python REPL), response size limits, header injection prevention, dangerous tool confirmation (`--confirm`) |
| Persistent memory | SQLite-backed `PersistentMemory` extends in-memory `Memory`; auto-save on every `add()`, lazy DB connection. Session management via `--session <name>`. |
| Backend extensibility | Abstract `BaseBackend` class + `_BACKENDS` dict + `register_backend()` function. 3 backends: ollama, bitnet, llama-server. |
| Optional imports | ACP, Soul, and PersistentMemory modules wrapped in `try/except` with fallback to `None`. Check with `if X is not None` before using. |
| CLI argument DRY | `shared_args.py:add_agent_args()` adds shared args to run/chat/agent parsers. `cli.py:_build_agent()` centralizes Agent construction. |
| Structured output | `--response-format json` → Agent sets `response_format={"type":"json_object"}`, disables tools, forces `tool_choice="none"`. Backend sends `response_format` to API. |
| State machine | `agent_mode.py`: IDLE → WORKING → PAUSED → STOPPING with pause/resume/rollback. `reset_memory_between_steps` for isolated step execution. |
| Audit logging | `~/.agentnova/audit.log`: JSON-lines, fire-and-forget, logs shell/write_file/edit_file outcomes (accepted/rejected/error). |

---

## Known Landmines

### Tool support detection is per-model, NOT per-family
```python
qwen2.5:0.5b     → ToolSupportLevel.NATIVE
qwen2.5-coder:0.5b → ToolSupportLevel.REACT     # Same family, different behavior!
# Cache: ~/.cache/agentnova/tool_support.json
# Test: agentnova models --tool-support
```

### `calculator()` uses `eval()` — sandboxed but still eval
```python
result = eval(expression, {"__builtins__": {}}, safe_dict)
# DANGEROUS: Adding os, sys, or __import__ to safe_dict breaks the sandbox.
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
# Or: validate_path(path, allowed_dirs=["/custom/path"])
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

### `_parse_frontmatter()` has limited YAML support
```python
# Custom parser — no PyYAML. Handles: key: value, key: "quoted", multiline via indentation.
# DOES NOT handle: nested objects, arrays, null, booleans, numbers without quotes.
```

### Web search depends on HTML scraping — fragile
```python
# Scrapes DuckDuckGo Lite and html.duckduckgo.com with regex.
# Any HTML structure change by DuckDuckGo silently breaks web search.
```

### `config.py` reads env vars at import time
```python
# Module-level constants like OLLAMA_BASE_URL are set WHEN THE MODULE IS IMPORTED.
# Changing env vars after import has NO effect unless get_config(reload=True) is called.
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
| Tool support per-model, not per-family | Runtime testing, cached results | Model templates vary within same family |
| Default soul = nova-helper | Every Agent loads a soul unless explicitly disabled | Souls structure small model prompting |
| Dangerous tool confirmation | `--confirm` flag + callback on Agent | Explicit opt-in for destructive operations |
| JSON mode disables tools | Mutually exclusive by design | JSON output format breaks ReAct parsing |

---

## What's Missing / Incomplete

- **No streaming for ReAct path** — `--stream` flag exists but streaming is not fully implemented for the tool calling loop
- **Memory pruning has no summarization** — old messages silently dropped, not summarized
- **Pipeline mode output chaining is plain text** — `[Previous output: ...]` loses formatting and tool results
- **Parallel merge strategies are simplistic** — `vote` normalizes to lowercase first 100 chars; `best` just picks longest
- **`BackendType.OPENAI` and `BackendType.CUSTOM`** — defined in types.py but have no implementations
- **Soul Spec `HEARTBEAT.md`** — referenced in Soul Spec v0.5 but not implemented in loader
- **No ACL per-tool** — `allowed_tools` at Agent level, but no per-role or per-context permission system
- **PersistentMemory has no migration** — schema changes require manual DB deletion
- **No token budget enforcement** — CostTracker in ACP tracks costs but no hard limit in Agent
- **`_todo_store` is module-level global** — shared across all agents in same process (not per-session)

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
9. For CLI changes → start with `shared_args.py` (arg definitions) and `cli.py:_build_agent()`
10. Run `pytest` after any change

Do NOT start by reading every file. Use this brief as your map and read only what you need for your specific task.

---

## Token Budget Note

> This brief is approximately **~8,500 tokens** (estimated: 29,750 characters ÷ 3.5). Target maximum: 16,000 tokens. Headroom: ~7,500 tokens (~47% of budget remaining).
