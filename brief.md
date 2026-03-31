# Codebase Intelligence Brief: AgentNova

> Generated: 2026-03-31T15:00:00Z | Auditor: Super-Z-Alpha | Commit: e56447f (R04.2)

---

## Project Identity

| Field | Value |
|-------|-------|
| **Purpose** | Minimal, hackable agentic framework for running AI agents entirely locally with Ollama or BitNet backends |
| **Tech Stack** | Python 3.9+, zero runtime dependencies (stdlib only: urllib, json, subprocess, dataclasses, threading) |
| **Entry Point** | `agentnova/cli.py:main` (CLI) or `from agentnova import Agent` (Python API) |
| **Build/Run** | `pip install -e ".[dev]"` (dev: pytest, black, ruff) |
| **Test Command** | `pytest` (unit) or `python -m agentnova.examples.01_quick_diagnostic` (integration) |
| **Package** | PyPI: `agentnova` · CLI entry points: `agentnova` + `localclaw` (backward-compat) |
| **Version** | 0.4.2-dev (R04.2) · Status: Alpha |

---

## Architecture Map

```
agentnova/
├── core/           → Data types, models, memory, tool parsing, security helpers, OpenResponses spec implementation
├── tools/          → Tool registry (decorator-based), 12 built-in tools, sandboxed Python REPL
├── backends/       → LLM inference backends (Ollama, BitNet) with dual API (OpenResponses + OpenAI Chat-Completions)
├── skills/         → AgentSkills spec loader (YAML frontmatter, SPDX license validation, compatibility checking)
├── soul/           → Soul Spec v0.5 loader (persona packages with 3-level progressive disclosure)
├── souls/          → Pre-built soul packages: nova-helper (diagnostic), nova-skills (skill-guided)
├── examples/       → 12 benchmark/test suites (basic agent through analogical reasoning, GSM8K 50q)
agent.py            → Core Agent class: OpenResponses agentic loop (prompt → tool → observe → repeat)
agent_mode.py       → Autonomous agent mode: state machine (IDLE → RUNNING → PAUSED → STOPPING)
orchestrator.py     → Multi-agent orchestration: router (keyword/LLM), pipeline (sequential), parallel (threaded)
acp_plugin.py       → ACP v1.0.5: status reporting, activity logging, A2A messaging, batch context manager
cli.py              → Full CLI: run, chat, agent, models, tools, test, soul, config, version, modelfile, skills
config.py           → Centralized config from env vars. Single source of truth for all URLs, defaults, security
colors.py           → Shared ANSI color utilities (Color class, pad_colored, visible_len)
model_discovery.py  → Ollama model listing, fuzzy model name matching, benchmark model selection
shared_args.py      → Shared CLI argument definitions (DRY for run/chat/agent parsers)
```

### Skip List

- `localclaw/`, `localclaw-redirect/` — legacy backward-compat redirects, just re-exports
- `audit/` — referenced in docs but empty, not used in codebase
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
      def __init__(self, model: str, tools=None, backend=None, max_steps=5,
                   soul="nova-helper", soul_level=3, num_ctx=None,
                   temperature=None, tool_choice="auto", allowed_tools=None,
                   skills_prompt=None, retry_on_error=True, max_tool_retries=2):
          ...

      def run(self, prompt: str, stream: bool = False) -> AgentRun:
          """Main agentic loop. Returns AgentRun with final_answer."""
  ```
- **Critical internal state**: `_expecting_final_answer` (bool), `_last_successful_result` (str), `_error_tracker` (ErrorRecoveryTracker), `_response_history` (dict). These control the "Final Answer Enforcement" behavior where the agent forces a result if the model loops after a successful tool call.
- **Gotchas**: The `tools` parameter accepts `ToolRegistry | list[str] | list[Tool] | None` — four different types. If passing a list of strings, they MUST match registered tool names exactly (no fuzzy matching at this level). Fuzzy matching happens inside the ToolParser.

### `agentnova/core/tool_parse.py` — Tool Call Extraction
- **Purpose**: Parses tool calls from model text output in 4+ formats. Central to how ReAct tool calling works.
- **Blast radius**: Only imported by `agent.py`, but critical to it.
- **Key signatures**:
  ```python
  class ToolParser:
      def __init__(self, tool_names: list[str]):
          self._names = tool_names  # Used for fuzzy matching

      def parse(self, content: str) -> list[ParsedCall]:
          """Returns list of ParsedCall(name, arguments, final_answer, thought)"""

      def is_final_answer(self, content: str) -> bool:
          """Checks for 'Final Answer:' pattern in text."""

      def extract_final_answer(self, content: str) -> str:
          """Extracts everything after 'Final Answer:'."""
  ```
- **Supported formats**: Plain ReAct (`Action: name\nAction Input: {json}`), JSON-wrapped ReAct (`{"action": "name", "actionInput": {...}}`), Markdown code block JSON, and simultaneous tool call + Final Answer.
- **Gotchas**: The parser handles case-insensitive `Action`/`action`/`ACTION`, both `actionInput` and `action_input`. If the model outputs both a tool call AND a `Final Answer:` in the same response, the Final Answer takes priority (lines 726-762 in agent.py).

### `agentnova/core/helpers.py` — Fuzzy Matching, Arg Normalization, Security
- **Purpose**: God-module for small model support. Fuzzy tool name matching, argument normalization, expression synthesis from natural language, security utilities (path validation, command blocklist, SSRF protection), repetition detection, small model heuristics.
- **Blast radius**: Imported by `builtins.py` (security), `tool_parse.py` (fuzzy matching), `agent.py` (argument synthesis), and indirectly everything through transitive imports.
- **Key functions**:
  ```python
  def fuzzy_match(query: str, candidates: list[str], threshold: float = 0.4) -> str | None:
  def normalize_args(args: dict, expected_params: list[str], tool_name: str = "") -> dict:
  def sanitize_command(command: str) -> tuple[bool, str, str]:
  def validate_path(path: str, allowed_dirs: list[str] | None = None) -> tuple[bool, str]:
  def is_safe_url(url: str, block_ssrf: bool = True) -> tuple[bool, str]:
  def extract_calc_expression(user_input: str) -> str | None:
  def synthesize_tool_args(tool_name: str, args: dict, user_input: str) -> dict:
  ```
- **BLOCKED_COMMANDS** (line 247): rm, sudo, curl, wget, pip, npm, kill, systemctl, chmod, etc. ~40 blocked commands.
- **Gotchas**: `sanitize_command()` returns the original command UNMODIFIED — the security comes from rejection, not transformation. If the blocklist is bypassed, the command runs as-is via `shell=True`. The injection detection rejects `;`, `|`, `&&`, backticks, `$()`, `>${}`, but NOT pipes with zero spaces. `validate_path()` allows `/tmp`, `/home`, and system temp dirs. Config default allowed paths: `["./output", "./data", "/tmp"]`.

### `agentnova/backends/ollama.py` — Primary Backend
- **Purpose**: Dual API backend supporting both OpenResponses (`/api/chat`) and OpenAI Chat-Completions (`/v1/chat/completions`). Handles streaming, tool support detection, and thinking model handling.
- **Blast radius**: Instantiated by `get_backend()` in cli.py and orchestrator.py. All model communication flows here.
- **Key**: `OllamaBackend` extends `BaseBackend`. Has `api_mode` attribute that determines which endpoint format to use. All ReAct prompting happens here — tool definitions are NOT passed to the API; the model outputs tool calls in text format.
- **Gotchas**: Tool support detection is per-model (NOT per-family). `qwen2.5:0.5b` has native tools but `qwen2.5-coder:0.5b` is ReAct-only despite being the same family. Cache lives at `~/.cache/agentnova/tool_support.json`.

### `agentnova/tools/builtins.py` — All 12 Built-in Tools
- **Purpose**: Defines calculator, shell, read_file, write_file, list_directory, http_get, python_repl, get_time, get_date, web_search, parse_json, count_words, count_chars.
- **Blast radius**: Instantiated via `make_builtin_registry()` which creates `BUILTIN_REGISTRY` singleton. Imported by cli.py for every command that uses tools.
- **Key**:
  ```python
  def make_builtin_registry() -> ToolRegistry:
      """Creates registry with all 12 tools. Returns ToolRegistry singleton (BUILTIN_REGISTRY)."""
  ```
- **Security notes**: Calculator uses `eval()` with `{"__builtins__": {}}` and MAX_EXPONENT=10,000. Shell uses `shell=True` with `sanitize_command()` blocklist. File ops use `validate_path()`. HTTP uses `is_safe_url()` for SSRF protection. Python REPL runs in a sandboxed subprocess with only math, json, re, datetime, collections, itertools available. Response size limits: files 512KB, HTTP 256KB.

### `agentnova/core/memory.py` — Conversation Memory
- **Purpose**: Sliding window conversation history with token-based pruning. Preserves system prompt and recent messages.
- **Key**:
  ```python
  class Memory:
      def add(self, role: str, content: str, **kwargs) -> None:
      def add_tool_call(self, role: str, content: str, tool_calls: list[dict]) -> None:
      def add_tool_result(self, tool_call_id: str, name: str, content: str) -> None:
      def get_messages(self) -> list[dict]:  # Includes system prompt first
      def clear(self) -> None:  # Preserves system prompt if configured
  ```
  ```python
  @dataclass
  class MemoryConfig:
      max_messages: int = 50
      max_tokens: int = 4096
      summarization_threshold: float = 0.8
      keep_system: bool = True
      keep_recent: int = 5
  ```
- **Gotchas**: `_prune_if_needed()` is called on every `add()`. It triggers when message count exceeds `max_messages * summarization_threshold` (default: 50 * 0.8 = 40 messages). It removes oldest non-system messages but always keeps the most recent 5 (`keep_recent`). Note: there is NO actual summarization implemented — pruning just drops old messages. `to_dict()` on `Message` converts internal tool_call format to OpenAI Chat-Completions format (arguments dict → JSON string).

### `agentnova/tools/registry.py` — Tool Registry
- **Purpose**: Manages tool registration (including decorator-based), fuzzy lookup, subset creation, and JSON Schema generation.
- **Key**:
  ```python
  class ToolRegistry:
      def register(self, name=None, description="", params=None, dangerous=False, category="general") -> Callable:
          """Decorator for registering tools. Auto-extracts params from function signature."""
      def get_fuzzy(self, name: str, threshold: float = 0.6) -> Tool | None:
      def subset(self, names: list[str]) -> ToolRegistry:
          """Creates sub-registry. Uses EXACT name matching only (no fuzzy)."""
      def to_json_schema(self) -> list[dict]:
  ```
- **Gotchas**: `subset()` uses exact matching only. `get_fuzzy()` has a default threshold of 0.6 (higher than helpers.py's 0.4). The `@tool` decorator at module level creates a NEW ToolRegistry instance each time — it's a convenience for standalone scripts, not for adding to the shared BUILTIN_REGISTRY.

### `agentnova/skills/loader.py` — Skills System
- **Purpose**: Loads SKILL.md files with YAML frontmatter, validates spec compliance (name format, description length 1-1024 chars, SPDX license).
- **Key**:
  ```python
  class Skill:
      name: str          # 1-64 chars, regex validated: ^[a-z0-9]+(-[a-z0-9]+)*$
      description: str   # 1-1024 chars, enforced in __post_init__
      instructions: str  # Markdown body after frontmatter
      license: str | None
      compatibility: str | None
      allowed_tools: list[str]

  class SkillLoader:
      def load(self, skill_name: str, use_cache: bool = True) -> Skill:
      def list_skills(self) -> list[str]:
  ```
- **Gotchas**: `check_compatibility()` tries to import `packaging.version` — not available in zero-dep mode. The custom YAML parser (`_parse_frontmatter`) handles multiline values but has limited edge case support. Skill name in frontmatter MUST match directory name or a `ValueError` is raised.

### `agentnova/orchestrator.py` — Multi-Agent Orchestration
- **Purpose**:
  ```python
  class Orchestrator:
      def __init__(self, mode="router", default_model="qwen2.5:0.5b",
                   router_model=None, merge_strategy="concat", timeout=120.0):
      def register(self, card: AgentCard) -> None:  # Creates Agent if card.agent is None
      def run(self, task: str) -> OrchestratorResult:
  ```
  - **Router mode**: keyword matching (`AgentCard.matches()`) or LLM-based (`_select_agent_with_llm()`). Falls back to first agent if no match.
  - **Pipeline mode**: sequential, chains output of each agent into the next agent's input.
  - **Parallel mode**: `ThreadPoolExecutor`, results merged via strategy (concat/first/vote/best).
  ```python
  @dataclass
  class AgentCard:
      name: str; description: str; capabilities: list[str]; tools: list[str]
      model: str | None; agent: Agent | None; priority: int; timeout: float; fallback: bool
  ```
- **Gotchas**: `_select_agent_with_llm()` hardcodes `get_backend("ollama")` — will fail if Ollama isn't running or default backend is BitNet. Pipeline mode appends previous output as plain text (`[Previous output: ...]`), not as a structured message. Vote merge strategy normalizes to lowercase first 100 chars — common answers that differ only in casing will be treated as identical.

### `agentnova/config.py` — Central Configuration
- **Purpose**: Single source of truth for all URLs, defaults, security settings. Everything reads from here.
- **Key**:
  ```python
  OLLAMA_BASE_URL = "http://localhost:11434"      # Override: env var
  BITNET_BASE_URL = "http://localhost:8765"       # Override: env var + BITNET_TUNNEL
  ACP_BASE_URL = "http://localhost:8766"          # Override: env var ACP_BASE_URL
  DEFAULT_MODEL = "qwen2.5:0.5b"                # Or bitnet-b1.58-2b-4t for BitNet
  MAX_STEPS = 10 (env: AGENTNOVA_MAX_STEPS)
  RETRY_ON_ERROR = True (env: AGENTNOVA_RETRY_ON_ERROR)
  MAX_TOOL_RETRIES = 2 (env: AGENTNOVA_MAX_TOOL_RETRIES)
  ```
  ```python
  @dataclass
  class Config:
      num_ctx: int | None = None  # None means use backend default
      retry_on_error: bool = True
      max_tool_retries: int = 2
      memory_max_messages: int = 50
      memory_max_tokens: int = 4096
  ```
- **Gotchas**: `Config.from_env()` doesn't actually parse env vars — it just calls `Config()` which uses module-level defaults already computed. `get_config()` is a singleton — set `reload=True` to re-read env vars. `num_ctx` of `None` means "let Ollama decide" — but Agent defaults to 8192 if config is also None.

---

## Request / Execution Lifecycle

```
User Prompt
    │
    ▼
1. Agent.__init__()                                           # agent.py:105
   ├── If soul specified: soul/loader.py → load_soul()       # soul/loader.py
   │   └── build_system_prompt_with_tools(soul, tools, level) # Injects available tools
   ├── If skills specified: SkillLoader → SkillRegistry       # skills/loader.py
   │   └── to_system_prompt_addition()                       # Appends to system prompt
   ├── Create ToolParser(tools.names())                        # core/tool_parse.py
   ├── Memory.add("system", system_prompt)                   # core/memory.py
   └── Initialize ErrorRecoveryTracker                         # core/error_recovery.py
    │
    ▼
2. Agent.run(prompt)                                            # agent.py:377
   ├── Create OpenResponses Response object                      # core/openresponses.py
   │   └── Response(model, status=QUEUED, tool_choice)    # State machine: QUEUED → IN_PROGRESS → COMPLETED/FAILED
   ├── Memory.add("user", prompt)
   ├── Create MessageItem, add to Response.input
    │
    ▼
3. Agentic Loop (for step in range(max_steps))                  # Default: 5 steps
   │
   ├─ 3a. Backend.generate(memory.get_messages())               # backends/ollama.py
   │       ├── If api_mode=OPENRE:  POST /api/chat
   │       └── If api_mode=OPENAI:  POST /v1/chat/completions
   │       ├── For thinking models (qwen3, deepseek-r1):
   │       │   └── Auto-sets think=False unless overridden
   │       └── Returns {content, tool_calls, usage, _finish_reason}
   │
   ├─ 3b. Check finish_reason
   │       ├── "length" → mark_incomplete(), break
   │       └── "content_filter" → mark_failed(), break
   │
   ├─ 3c. Check for tool calls (two sources):
   │       ├── NATIVE: backend returns tool_calls in response
   │       │   └── memory.add_tool_call("assistant", content, tool_calls)
   │       └── REACT: ToolParser.parse(content) extracts from text
   │           └── ParsedCall(name, arguments, final_answer, thought)
   │
   ├─ 3d. Final Answer Enforcement
   │       If _expecting_final_answer is True and model tried another tool call:
   │           → Force use of _last_successful_result as the answer
   │
   ├─ 3e. If tool calls found:
   │       ├── Check allowed_tools (block if not in list)
   │       ├── Execute via _execute_tool(name, args, prompt)      # tools/registry.py → handler()
   │       ├── Track success/failure in ErrorRecoveryTracker
   │       │   ├── On failure: is_error_result() → build_retry_context()
   │       │   └── On success: record_success(), reset consecutive counter
   │       ├── Build enhanced observation with guidance:
   │       │   ├── Success: "Observation: {result}\n\nNow output: Final Answer: <the result>"
   │       │   └── Error: "Observation: {error}\n\nNote: Try a different approach..."
   │       ├── Check for simultaneous final_answer in parsed call
   │       │   └── If present → use it, skip loop continuation
   │       └── Continue agentic loop
   │
   ├─ 3f. Check for "Final Answer:" in content
   │       ├── Enforce tool_choice=required if no tools called yet
   │       ├── Extract via ToolParser.extract_final_answer()
   │       ├── Create MessageItem, add to Response.output
   │       └── Break from loop
   │
   └─ 3g. No tool call, no Final Answer → accept as direct response
         (unless tool_choice=required → inject guidance, continue)
```

---

## Dependency Graph

```
cli.py ─────────────────────────────────────────────────────────────┐
  ├──→ agent.py ────────────────────────────────────────────────────────┤
  │    ├── core/memory.py                                           │
  │    ├── core/tool_parse.py ─→ core/models.py                    │
  │    ├── core/error_recovery.py                                     │
  │    ├── core/openresponses.py ─→ core/models.py                   │
  │    ├── core/helpers.py ─→ (security for all tool operations)    │
  │    ├── tools/registry.py ─→ tools/builtins.py                   │
  │    └── soul/loader.py ─→ soul/types.py                        │
  │                                                                    │
  ├──→ orchestrator.py ─→ agent.py (creates Agent instances per card)   │
  │       └── backends/ (for LLM-based routing)                     │
  │                                                                    │
  ├──→ agent_mode.py ──→ agent.py (wraps in state machine)            │
  └──→ skills/loader.py (via _load_skills_prompt, optional)          │
                                                                       │
config.py ← referenced by EVERYTHING above                           │
backends/__init__.py ← referenced by agent.py, orchestrator.py        │
core/model_family_config.py ← referenced by agent.py                  │
core/tool_cache.py ← referenced by types.py, cli.py                  │
```

**Highest blast radius changes:**
1. `config.py` — changing a URL or default affects the entire system
2. `core/helpers.py` — changing security behavior affects all built-in tools
3. `agent.py` — changing the agentic loop affects all modes (run, chat, agent, orchestrator)

---

## Patterns & Conventions

| Aspect | Pattern |
|--------|---------|
| API specification | OpenResponses (https://www.openresponses.org/specification) — 100% compliant: Items, Response state machine, tool_choice modes |
| Tool calling | Unified ReAct prompting for ALL models — model outputs `Action: name\nAction Input: {json}`. Tool definitions are NOT passed to the API. |
| Error recovery | Retry-with-error-feedback: inject previous failure context into conversation so model self-corrects. Max 2 retries per failure (configurable). Escalates after consecutive failures. |
| Small model support | Fuzzy tool name matching (0.4 threshold), argument normalization with aliases, natural language expression extraction, enhanced observations with guidance, repetition detection (`detect_and_fix_repetition()`), `is_small_model()` heuristic |
| Security | Defense-in-depth: command blocklist + injection detection (shell), path whitelist validation (file ops), SSRF pattern blocking (HTTP), sandboxed subprocess (Python REPL), response size limits, header injection prevention |
| Backend extensibility | Abstract `BaseBackend` class + `_BACKENDS` dict + `register_backend()` function |
| Optional imports | ACP and Soul modules wrapped in `try/except` with fallback to `None`. Check with `if ACPPlugin is not None` before using. |
| CLI argument DRY | `shared_args.py` provides shared argument definitions, but run/chat/agent parsers each duplicate ~20 args. New flags must be added to ALL THREE. |
| Module entry points | `pyproject.toml [project.scripts]` defines CLI commands. `__init__.py` controls public API via `__all__`. |
| State machine | `agent_mode.py` implements IDLE → RUNNING → PAUSED → STOPPING with pause/resume/rollback support. |

---

## Known Landmines

### Tool support detection is per-model, NOT per-family
```python
# SAME FAMILY, DIFFERENT CAPABILITIES:
qwen2.5:0.5b     → ToolSupportLevel.NATIVE    # API returns tool_calls structure
qwen2.5-coder:0.5b → ToolSupportLevel.REACT     # Template differs from base!

# Cache lives at ~/.cache/agentnova/tool_support.json
# MUST be populated BEFORE relying on it:
agentnova models --tool-support
```
**Impact**: If you assume all `qwen2.5` models have native tools, you'll break on coder variants. Always test per-model.

### `calculator()` uses `eval()` — sandboxed but still eval
```python
# In tools/builtins.py:101
result = eval(expression, {"__builtins__": {}}, safe_dict)

# Safe because:
# 1. __builtins__ is nulled
# 2. MAX_EXPONENT = 10,000 prevents DoS via 2**9999999
# 3. NaN and Inf are explicitly caught

# DANGEROUS: If a new entry is added to safe_dict that provides
# access to os, sys, or __import__, the sandbox is broken.
```
**Impact**: Adding any entry to `safe_dict` that bridges to Python internals defeats the sandbox. Only add pure math functions.

### `shell()` runs with `shell=True` — security is purely rejection-based
```python
# In tools/builtins.py:156
result = subprocess.run(validated_cmd, shell=True, ...)

# sanitize_command() REJECTS dangerous commands but does NOT modify the input.
# The command returned is the ORIGINAL string (or empty string on rejection).
# Injection detection blocks: ;, |, &&, ||, backticks, $(), ${}, >, <
# BUT: pipes with zero spaces (|cmd) are caught, and leading '=' is stripped.
```
**Impact**: Any bypass of the blocklist or injection patterns allows arbitrary command execution. The `shell=True` choice was deliberate (OS shell interprets the full command string) but means security is entirely dependent on the rejection logic.

### `validate_path()` blocks system directories
```python
# In core/helpers.py:392 (Unix)
critical_system_dirs = ["/etc", "/root", "/var", "/usr", "/bin", "/sbin", "/boot", "/dev", "/proc", "/sys"]

# ALLOWED (without config override):
resolves.startswith("/tmp")      ✓
resolves.startswith("/home")     ✓
resolves.startswith(system_temp) ✓
resolves.startswith(allowed_dir) ✓

# Config default allowed paths: ["./output", "./data", "/tmp"]
```
**Workaround for custom paths**:
```python
# Option 1: Extend via Config
config = Config(allowed_paths=["./output", "./data", "/tmp", "/custom/path"])

# Option 2: Pass to validate_path directly
is_valid, error = validate_path("/custom/path/file.txt", allowed_dirs=["/custom/path"])
```

### Memory pruning drops messages without summarization
```python
# In core/memory.py:148
def _prune_if_needed(self) -> None:
    # Triggers when len(_messages) > max_messages * summarization_threshold
    # Default: 50 * 0.8 = 40 messages
    # It just DROPS old messages — there is NO actual summarization.
    # keep_recent=5 means the 5 most recent messages are always preserved.
```
**Impact**: Long conversations silently lose context. The `summarization_threshold` name is misleading — it's just a pruning threshold, not a summarization trigger.

### `_parse_frontmatter()` has limited YAML support
```python
# In skills/loader.py:350
# Custom parser — no PyYAML dependency
# Handles: key: value, key: "quoted", key: 'quoted', multiline values via indentation
# DOES NOT handle: nested objects, arrays, null, booleans, numbers without quotes
```
**Impact**: Complex frontmatter (nested objects, lists) will parse incorrectly. The parser works for the current AgentSkills spec (which uses simple string values) but would break on richer YAML.

### CLI argument duplication — maintenance risk
```
# Every new flag must be added to THREE parsers in cli.py:
run_parser.add_argument(...)
chat_parser.add_argument(...)  # Same args, repeated 3x
agent_parser.add_argument(...)

# Shared args exist in shared_args.py but each parser still defines
# them independently. This is because each command has slightly
# different defaults (e.g., run defaults tools="calculator",
# chat defaults tools="", agent defaults tools="calculator,shell,write_file").
```
**Impact**: Forgetting to add a flag to all three parsers creates inconsistent CLI behavior.

### Web search depends on HTML scraping — fragile
```python
# In tools/builtins.py:450-578
# Scrapes DuckDuckGo Lite and HTML endpoints with regex
# Patterns: <a class="result-link" href="..."> and <td class="result-snippet">
# FALLBACK: tries html.duckduckgo.com/html/ if lite returns nothing
```
**Impact**: Any HTML structure change by DuckDuckGo will silently break web search. No fallback to an API-based search provider.

---

## Active Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Zero runtime dependencies | Python stdlib only (urllib for HTTP) | Maximizes portability, zero supply chain risk, works on any Python 3.9+ |
| Unified ReAct prompting | All models use Action/Action Input format | Consistent parsing, no need to detect which format a model uses per-family |
| No tool call fallbacks | Model must explicitly format tool calls | Follows OpenResponses spec — prevents the framework from synthesizing answers behind the model's back |
| Dual API support | OpenResponses + OpenAI Chat-Completions | OpenResponses for spec compliance, OpenAI compat for ecosystem integration |
| Path whitelist security | Whitelist-based file access | Defense in depth — even if an agent suggests a path, it's validated |
| Calculator via eval | Restricted eval with `__builtins__: {}` | Simplicity + full Python math expression support without writing a parser |
| Thinking models auto-detection | `detect_family()` sets `think=False` for qwen3, deepseek-r1 | These models waste tokens thinking when tool-calling is the goal |
| Tool support per-model, not per-family | Runtime testing, cached results | Model templates vary within the same family (e.g., base vs. coder variants) |
| Default soul = nova-helper | Every Agent loads a soul unless explicitly disabled | Souls provide structure for small model prompting (tool format, error recovery guidance) |

---

## What's Missing / Incomplete

- **No streaming for ReAct path** — `--stream` flag exists on CLI but streaming is not fully implemented for the tool calling loop
- **No persistent conversation storage** — `Memory` is in-memory only; restarting CLI loses all history. No session save/load.
- **Memory pruning has no summarization** — old messages are silently dropped, not summarized. The `summarization_threshold` name is misleading.
- **Pipeline mode output chaining is plain text** — previous agent output is appended as `[Previous output: ...]` rather than as a structured message. Loses formatting and tool results.
- **Parallel merge strategies are simplistic** — `vote` normalizes to lowercase first 100 chars (fragile); `best` just picks longest answer.
- **`BackendType.OPENAI` and `BackendType.CUSTOM`** are defined in types.py but have no implementations — future stubs only.
- **Soul Spec `AGENTS.md` and `HEARTBEAT.md`** are referenced in the Soul Spec v0.5 but not implemented in the loader.
- **`Tool.dangerous` flag** is informational only — it's set on `shell`, `write_file`, etc. but nothing in the framework enforces it (e.g., requires explicit confirmation).
- **No ACL per-tool** — you can restrict via `allowed_tools` at the Agent level, but there's no per-role or per-context permission system.

---

## Quick Start for Developer

1. Read the **Critical Files Index** above — each entry has function signatures, blast radius, and gotchas
2. Trace the **Request / Execution Lifecycle** — this is how the entire system works end-to-end
3. Check **Known Landmines** — these save real debugging time
4. For tool changes → start with `tools/builtins.py` (definitions) and `core/helpers.py` (security)
5. For backend changes → start with `backends/ollama.py`
6. For agent loop changes → start with `agent.py` and `core/tool_parse.py`
7. For multi-agent work → start with `orchestrator.py`
8. Run `pytest` after any change

Do NOT start by reading every file. Use this brief as your map and read only what you need for your specific task.

---

## Token Budget Note

> This brief is approximately **~7,800 tokens** (estimated: 27,300 characters ÷ 3.5). Target maximum: 16,000 tokens. Headroom: ~8,200 tokens (~51% of budget remaining).
