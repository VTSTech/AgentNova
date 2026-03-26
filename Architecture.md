## Architecture

AgentNova is a modular agent framework designed for local LLMs with tool-calling capabilities.

```
agentnova/
├── core/
│   ├── types.py              # Enum types (StepResultType, ToolSupportLevel, BackendType)
│   ├── models.py             # Data models (Tool, ToolParam, StepResult, AgentRun)
│   ├── memory.py             # Sliding window conversation memory
│   ├── tool_parse.py         # ReAct/JSON tool call extraction
│   ├── helpers.py            # Utilities (fuzzy match, expression extraction, security)
│   ├── prompts.py            # Model-specific system prompts and few-shot examples
│   ├── model_config.py       # Model configuration (temperature, max tokens)
│   ├── model_family_config.py # Family-specific behavior (stop tokens, formats)
│   ├── args_normal.py        # Argument normalization for small model hallucinations
│   └── math_prompts.py       # Math-specific prompt templates
│
├── tools/
│   ├── registry.py           # Tool registry with decorator-based registration
│   ├── builtins.py           # Built-in tools (calculator, shell, file ops, http)
│   └── sandboxed_repl.py     # Sandboxed Python REPL execution
│
├── backends/
│   ├── base.py               # Abstract BaseBackend class
│   ├── ollama.py             # Ollama backend (native tools, ReAct)
│   └── bitnet.py             # BitNet backend
│
├── skills/
│   ├── loader.py             # Skill loader (Agent Skills spec)
│   ├── acp/                  # ACP (Agent Control Panel) skill
│   ├── datetime/             # Date/time utilities skill
│   ├── web-search/           # Web search skill
│   └── skill-creator/        # Skill creation utilities
│
├── soul/
│   ├── types.py              # Soul Spec v0.5 data structures
│   └── loader.py             # SoulLoader with progressive disclosure
│
├── souls/
│   └── nova-helper/          # Example coding assistant soul
│       ├── soul.json         # Manifest
│       ├── SOUL.md           # Persona definition
│       ├── IDENTITY.md       # Background
│       └── STYLE.md          # Communication style
│
├── examples/
│   ├── 00_basic_agent.py     # Basic conversation test
│   ├── 01_quick_diagnostic.py # 5-question quick test
│   ├── 02_tool_test.py       # Tool calling tests
│   ├── 03_reasoning_test.py  # Multi-step reasoning
│   ├── 04_gsm8k_benchmark.py # Grade school math
│   ├── 05_common_sense.py    # Common sense reasoning
│   ├── 06_causal_reasoning.py # Cause and effect
│   ├── 07_logical_deduction.py # Syllogisms and logic
│   ├── 08_reading_comprehension.py # Text understanding
│   ├── 09_general_knowledge.py # Geography, science
│   ├── 10_implicit_reasoning.py # Implied meanings
│   └── 11_analogical_reasoning.py # Pattern mapping
│
├── agent.py                  # Main Agent class (ReAct loop, tool support detection)
├── agent_mode.py             # Autonomous agent mode (state machine)
├── orchestrator.py           # Multi-agent orchestration
├── orchestrator_enhanced.py  # Enhanced orchestration with parallel agents
├── acp_plugin.py             # Agent Control Panel integration
├── model_discovery.py        # Dynamic model discovery
├── shared_args.py            # Shared CLI configuration
├── config.py                 # Configuration management
└── cli.py                    # Command-line interface
```

## Key Components

### Agent (`agent.py`)

The main Agent class implements the ReAct loop with three-tier tool support:

- **Native**: Models that support OpenAI-style tool calling via API
- **ReAct**: Models that output `Action: / Action Input:` format
- **None**: Models without tool support (pure reasoning)

Key features:
- Auto-detection of tool support level
- Tool call synthesis for struggling models
- Soul Spec integration for persona/personality
- Streaming support
- Debug output

### Backends (`backends/`)

Pluggable inference backend system:

```python
from agentnova import get_backend

backend = get_backend("ollama", timeout=300)
response = backend.generate(model="qwen2.5:0.5b", messages=[...])
```

### Soul Spec (`soul/`)

ClawSouls Soul Spec v0.5 support for persona packages:

- Progressive disclosure (Level 1-3)
- Tool filtering via `allowedTools`
- System prompt generation from markdown files

```bash
agentnova chat --soul nova-helper --tools get_date,shell
```

### Skills (`skills/`)

Agent Skills spec implementation for loading external skills:

```python
from agentnova.skills import SkillLoader
loader = SkillLoader()
skill = loader.load("web-search")
```

### ACP Plugin (`acp_plugin.py`)

Agent Control Panel integration for monitoring:

- Bootstrap with identity establishment
- Activity logging
- A2A (Agent-to-Agent) JSON-RPC support
- STOP flag handling

```bash
agentnova chat --acp --acp-url https://tunnel.trycloudflare.com
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `run` | Run a single prompt |
| `chat` | Interactive chat mode |
| `agent` | Autonomous agent mode |
| `models` | List available models |
| `tools` | List available tools |
| `test` | Run diagnostic tests |
| `soul` | Inspect a Soul Spec package |
| `config` | Show current configuration |
| `version` | Show version info |

## Common Options

| Option | Commands | Description |
|--------|----------|-------------|
| `-m, --model` | run, chat, agent, test | Model to use |
| `--tools` | run, chat, agent | Comma-separated tool list |
| `--backend` | all | Backend (ollama, bitnet) |
| `--soul` | run, chat, agent | Path to Soul Spec package |
| `--soul-level` | run, chat, agent | Progressive disclosure (1-3) |
| `--num-ctx` | run, chat, agent, test | Context window size |
| `--timeout` | run, chat, agent, test | Request timeout (seconds) |
| `--acp` | run, chat, agent, test | Enable ACP logging |
| `--acp-url` | run, chat, agent, test | ACP server URL |
| `--debug` | run, chat, agent, test | Enable debug output |

## Data Flow

```
User Prompt
     │
     ▼
┌─────────────┐
│    CLI      │ ── parses args
└─────────────┘
     │
     ▼
┌─────────────┐
│   Agent     │ ── loads soul (optional)
│             │ ── detects tool support
│             │ ── builds system prompt
└─────────────┘
     │
     ▼
┌─────────────┐
│   Backend   │ ── sends to Ollama/BitNet
└─────────────┘
     │
     ▼
┌─────────────┐
│ Tool Parser │ ── extracts Action/Action Input
│             │ ── or native tool_calls
└─────────────┘
     │
     ▼
┌─────────────┐
│Tool Registry│ ── executes tool
└─────────────┘
     │
     ▼
┌─────────────┐
│   Memory    │ ── adds Observation
└─────────────┘
     │
     ▼ (loop until Final Answer)
     │
┌─────────────┐
│   Result    │ ── AgentRun with final_answer
└─────────────┘
```

# AgentNova Tool Support & Prompt Building Logic

## Overview

This document describes the complete flow of:
1. **Tool Support Detection** - How AgentNova determines if a model can use tools
2. **Prompt Building** - How system prompts are constructed based on tool support level

---

## Part 1: Tool Support Detection

### Tool Support Levels

| Level | Description | Behavior |
|-------|-------------|----------|
| `NATIVE` | Model uses Ollama's native tool API | Tools passed as JSON schemas, responses contain `tool_calls` |
| `REACT` | Model outputs text-based ReAct format | Parse `Action:` / `Action Input:` from text |
| `NONE` | Model cannot use tools | Simple prompts, calculator fallback only |

### Detection Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Agent.__init__()                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. force_react=True?                                                │
│     └─► _tool_support = REACT, source = "force_react"               │
│                                                                      │
│  2. No tools loaded?                                                 │
│     └─► _tool_support = NONE, source = "no_tools"                   │
│                                                                      │
│  3. Otherwise: _detect_tool_support()                               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  _detect_tool_support()                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Step 1: Check Cache                                                 │
│  ────────────────────                                                │
│  File: ~/.cache/agentnova/tool_support.json                         │
│                                                                      │
│  Cache structure:                                                    │
│  {                                                                   │
│    "qwen2.5:0.5b": {                                                 │
│      "support": "react",                                             │
│      "tested_at": 1711234567.89,                                     │
│      "family": "qwen2.5"                                             │
│    }                                                                 │
│  }                                                                   │
│                                                                      │
│  If cached:                                                          │
│    └─► Return cached level (native/react/none)                      │
│    └─► Set _tool_support_source = "cache(<level>)"                  │
│                                                                      │
│  Step 2: Default (No Auto-Test)                                      │
│  ──────────────────────────                                          │
│  If not cached:                                                      │
│    └─► Return REACT (default for untested models)                   │
│    └─► Set _tool_support_source = "default(react)"                  │
│                                                                      │
│  NOTE: Auto-testing removed to avoid delays on startup.              │
│        Run `agentnova models --tool_support` to test.                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Testing Tool Support (CLI)

```
┌─────────────────────────────────────────────────────────────────────┐
│          agentnova models --tool-support                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  For each model:                                                     │
│  ─────────────────                                                   │
│  backend.test_tool_support(model, force_test=True)                  │
│                                                                      │
│  Test Procedure (OllamaBackend.test_tool_support):                  │
│                                                                      │
│  1. Send request with test tool (get_weather)                       │
│     POST /api/chat                                                   │
│     {                                                                │
│       "model": "qwen2.5:0.5b",                                       │
│       "messages": [{"role": "user",                                  │
│                     "content": "What's the weather in Tokyo?"}],     │
│       "tools": [{"type": "function",                                 │
│                   "function": {"name": "get_weather", ...}}]         │
│     }                                                                │
│                                                                      │
│  2. Check Response:                                                  │
│     ┌───────────────────────────────────────────────────────────┐   │
│     │ HTTP 400 "does not support tools"                          │   │
│     │   └─► NONE (Ollama's explicit rejection)                   │   │
│     │                                                            │   │
│     │ tool_calls in API response (native structure)              │   │
│     │   └─► NATIVE (model uses Ollama tool API)                  │   │
│     │                                                            │   │
│     │ No tool_calls, but content has JSON tool pattern           │   │
│     │   └─► REACT (text-based tool calling)                     │   │
│     │                                                            │   │
│     │ API succeeded, no rejection, no tool calls                 │   │
│     │   └─► REACT (fallback - can parse text)                    │   │
│     └───────────────────────────────────────────────────────────┘   │
│                                                                      │
│  3. Cache result to ~/.cache/agentnova/tool_support.json            │
│                                                                      │
│  4. Unload model (free memory)                                       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Model Family Detection

Tool support is NOT determined by family - it depends on the model's template.
However, family is used for:

1. **Stop tokens** - e.g., `<|im_end|>` for Qwen, `<|eot_id|>` for Llama
2. **Prompt format** - e.g., ChatML for Qwen, Granite format for IBM models
3. **Few-shot style** - compact vs. full examples

```
Family Detection (detect_family in model_family_config.py):
──────────────────────────────────────────────────────────

Model name: "qwen2.5-coder:0.5b"
           ↓
Check substrings in order:
  "qwen2.5" → family = "qwen2.5" ✓
  "qwen2"   → (already matched)
  ...
           ↓
Return: "qwen2.5"
```

---

## Part 2: Prompt Building

### Prompt Building Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Agent.__init__()                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  After tool support detection:                                       │
│  _add_system_prompt()                                                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    _add_system_prompt()                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Case 1: Custom system prompt provided (e.g., from Soul)            │
│  ══════════════════════════════════════════════════════             │
│                                                                      │
│    if self._custom_system_prompt:                                    │
│        system_prompt = self._custom_system_prompt                    │
│                                                                      │
│        # IMPORTANT: Append tool descriptions if tools exist         │
│        if tools and _tool_support != NONE:                          │
│            tool_prompt = get_tool_prompt(tools, tool_support)       │
│            system_prompt = f"{system_prompt}\n\n{tool_prompt}"      │
│                                                                      │
│    memory.add("system", system_prompt)                              │
│                                                                      │
│  Case 2: Default system prompt generation                            │
│  ════════════════════════════════════════                            │
│                                                                      │
│    system_prompt = get_system_prompt(                               │
│        model_name=self.model,                                        │
│        tool_support=self._tool_support.value,                       │
│        tools=self.tools.all()                                        │
│    )                                                                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### get_system_prompt() Logic

```
┌─────────────────────────────────────────────────────────────────────┐
│                get_system_prompt(model, tool_support, tools)        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Step 1: Detect model family                                         │
│  ─────────────────────────────                                       │
│  family = detect_family(model_name)                                 │
│  # e.g., "qwen2.5", "llama3", "gemma3", "dolphin"                   │
│                                                                      │
│  Step 2: Get family config                                           │
│  ────────────────────────────                                        │
│  config = get_family_config(family)                                 │
│  # Contains: stop_tokens, prefers_few_shot, few_shot_style, etc.   │
│                                                                      │
│  Step 3: Build prompt based on tool_support                          │
│  ────────────────────────────────────────────                        │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ tool_support == "none"                                       │    │
│  │                                                              │    │
│  │ if config.no_tools_system_prompt:                           │    │
│  │     return config.no_tools_system_prompt                    │    │
│  │     # Family-specific prompt for non-tool models            │    │
│  │ else:                                                        │    │
│  │     return NO_TOOLS_SYSTEM_PROMPT                           │    │
│  │     # Generic math-friendly prompt                          │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ tool_support == "native"                                     │    │
│  │                                                              │    │
│  │ # Native models get tools via API, not in prompt            │    │
│  │ # Only add usage hints                                       │    │
│  │ hints = get_native_tool_hints(family)                       │    │
│  │ return f"{BASE_SYSTEM_PROMPT}\n\n{hints}"                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ tool_support == "react"                                      │    │
│  │                                                              │    │
│  │ # ReAct models need:                                         │    │
│  │ # 1. Tool descriptions                                       │    │
│  │ # 2. Format instructions (Thought/Action/Action Input)      │    │
│  │ # 3. Few-shot examples (CRITICAL for small models)          │    │
│  │                                                              │    │
│  │ tool_prompt = get_tool_prompt(tools, "react", family)       │    │
│  │ return f"{BASE_SYSTEM_PROMPT}\n\n{tool_prompt}"             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### get_tool_prompt() Logic

```
┌─────────────────────────────────────────────────────────────────────┐
│           get_tool_prompt(tools, tool_support, family)              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Step 1: List available tools                                        │
│  ─────────────────────────────                                       │
│  lines = ["Available tools:"]                                        │
│  for tool in tools:                                                  │
│      lines.append(f"  - {name}: {description}")                      │
│      lines.append(f"    Parameters: {param_list}")                   │
│                                                                      │
│  Example output:                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Available tools:                                               │  │
│  │   - calculator: Evaluate mathematical expressions              │  │
│  │     Parameters: expression: Mathematical expression            │  │
│  │   - shell: Execute shell commands                              │  │
│  │     Parameters: command: Shell command, timeout: Timeout (opt) │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  Step 2: Add format instructions                                     │
│  ──────────────────────────────────                                   │
│                                                                      │
│  if tool_support == "react":                                         │
│      lines.append(get_react_system_suffix(family))                  │
│                                                                      │
│      ┌───────────────────────────────────────────────────────────┐  │
│      │ REACT_SYSTEM_SUFFIX:                                       │  │
│      │                                                            │  │
│      │ You have access to tools. Use the following format:       │  │
│      │                                                            │  │
│      │ Thought: <your reasoning about what to do next>           │  │
│      │ Action: <tool_name>                                        │  │
│      │ Action Input: <JSON object with tool arguments>           │  │
│      │ Observation: <the result will appear here>                │  │
│      │ ... (repeat as needed)                                     │  │
│      │ Thought: I now have enough information.                   │  │
│      │ Final Answer: <your final response to the user>           │  │
│      └───────────────────────────────────────────────────────────┘  │
│                                                                      │
│  Step 3: Add few-shot examples (CRITICAL for ReAct)                 │
│  ──────────────────────────────────────────────────                   │
│                                                                      │
│  style = get_few_shot_style(family)  # "react" or "compact"         │
│                                                                      │
│  if style == "compact":                                              │
│      lines.append(FEW_SHOT_COMPACT)                                 │
│  else:                                                               │
│      lines.append(FEW_SHOT_SUFFIX)                                  │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ FEW_SHOT_SUFFIX (full examples):                              │  │
│  │                                                                │  │
│  │ Example 1 - Multiplication:                                    │  │
│  │ Thought: I need to multiply 15 times 8                         │  │
│  │ Action: calculator                                             │  │
│  │ Action Input: {"expression": "15 * 8"}                         │  │
│  │                                                                │  │
│  │ Example 2 - Power:                                             │  │
│  │ Thought: I need to calculate 2 to the power of 20              │  │
│  │ Action: calculator                                             │  │
│  │ Action Input: {"expression": "2 ** 20"}                        │  │
│  │                                                                │  │
│  │ [... 8 more examples for different tools ...]                  │  │
│  │                                                                │  │
│  │ CRITICAL RULES:                                                │  │
│  │ 1. Action line: just the tool name (no quotes)                 │  │
│  │ 2. Action Input: valid JSON with correct argument names        │  │
│  │ 3. ARGUMENT NAMES BY TOOL:                                     │  │
│  │    - calculator: {"expression": "15 * 8"}                      │  │
│  │    - shell: {"command": "echo Hello"}                          │  │
│  │    - python_repl: {"code": "print(result)"}                    │  │
│  │    ...                                                         │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Part 3: Soul System Prompt Building

### Soul Loading Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Agent.__init__(soul=path)                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. load_soul(path, level=soul_level)                               │
│     └─► SoulLoader.load()                                           │
│                                                                      │
│  2. Filter tools based on soul.allowed_tools                        │
│     if soul.allowed_tools:                                          │
│         self.tools = self.tools.subset(allowed_tools)              │
│                                                                      │
│  3. Build system prompt from soul                                   │
│     if system_prompt is None:                                       │
│         system_prompt = build_soul_prompt(soul, level)              │
│                                                                      │
│  4. Append tool descriptions (CRITICAL!)                            │
│     # Done in _add_system_prompt()                                  │
│     if tools and tool_support != NONE:                              │
│         tool_prompt = get_tool_prompt(tools, tool_support)         │
│         system_prompt += f"\n\n{tool_prompt}"                       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Soul Progressive Disclosure Levels

```
┌─────────────────────────────────────────────────────────────────────┐
│                 Soul Disclosure Levels                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Level 1: Quick Scan                                                 │
│  ─────────────────────                                               │
│  - soul.json manifest only                                          │
│  - name, displayName, description                                   │
│  - allowed_tools, recommended_skills                                │
│                                                                      │
│  Level 2: Full Read (default)                                        │
│  ──────────────────────────                                          │
│  - Everything from Level 1                                          │
│  - SOUL.md (persona)                                                │
│  - IDENTITY.md (identity)                                           │
│                                                                      │
│  Level 3: Deep Dive                                                  │
│  ────────────────                                                    │
│  - Everything from Level 2                                          │
│  - STYLE.md (style guidelines)                                      │
│  - AGENTS.md (agent behavior)                                       │
│  - HEARTBEAT.md (heartbeat behavior)                                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Soul System Prompt Structure

```
┌─────────────────────────────────────────────────────────────────────┐
│                 build_system_prompt(manifest, level)                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Output structure:                                                   │
│                                                                      │
│  # {displayName}                                                     │
│  {description}                                                       │
│  {disclosure.summary}                                                │
│                                                                      │
│  ## Persona                     (Level 2+)                          │
│  {soul_content from SOUL.md}                                         │
│                                                                      │
│  ## Identity                    (Level 2+)                          │
│  {identity_content from IDENTITY.md}                                 │
│                                                                      │
│  ## Style Guidelines            (Level 3)                           │
│  {style_content from STYLE.md}                                       │
│                                                                      │
│  ## Agent Behavior              (Level 3)                           │
│  {agents_content from AGENTS.md}                                     │
│                                                                      │
│  [+ Tool descriptions appended by _add_system_prompt()]             │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Part 4: Complete Flow Diagrams

### NATIVE Tool Support Flow

```
User Prompt: "What is 15 * 8?"
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│ System Prompt (NATIVE mode):                                       │
│                                                                    │
│ You are a helpful AI assistant.                                    │
│                                                                    │
│ TOOL USAGE RULES - YOU MUST CALL TOOLS:                           │
│ 1. MATH QUESTIONS: Always call calculator tool                    │
│    - "times/multiplied" → expression="A * B"                      │
│ 2. SHELL: Use shell tool                                          │
│ ...                                                                │
└───────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│ Ollama API Request:                                                │
│                                                                    │
│ POST /api/chat                                                     │
│ {                                                                  │
│   "model": "llama3.2:latest",                                      │
│   "messages": [...],                                               │
│   "tools": [{"type": "function",                                   │
│               "function": {"name": "calculator", ...}}]            │
│ }                                                                  │
└───────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│ Ollama Response (native tool_calls):                               │
│                                                                    │
│ {                                                                  │
│   "message": {                                                     │
│     "role": "assistant",                                           │
│     "content": "",                                                 │
│     "tool_calls": [{                                               │
│       "id": "call_abc123",                                         │
│       "function": {                                                │
│         "name": "calculator",                                      │
│         "arguments": {"expression": "15 * 8"}                      │
│       }                                                            │
│     }]                                                             │
│   }                                                                │
│ }                                                                  │
└───────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│ Agent processes tool_calls:                                        │
│                                                                    │
│ 1. Extract: name="calculator", args={"expression": "15 * 8"}      │
│ 2. Execute: result = calculator("15 * 8") → "120"                 │
│ 3. Add tool result to memory                                       │
│ 4. Continue to next step                                           │
└───────────────────────────────────────────────────────────────────┘
```

### REACT Tool Support Flow

```
User Prompt: "What is 15 * 8?"
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│ System Prompt (REACT mode):                                        │
│                                                                    │
│ You are a helpful AI assistant.                                    │
│                                                                    │
│ Available tools:                                                   │
│   - calculator: Evaluate mathematical expressions                  │
│     Parameters: expression: Mathematical expression                │
│                                                                    │
│ You have access to tools. Use the following format:               │
│ Thought: <your reasoning>                                          │
│ Action: <tool_name>                                                │
│ Action Input: <JSON with arguments>                               │
│ Observation: <result>                                              │
│ Final Answer: <your response>                                      │
│                                                                    │
│ ════════════════════════════════════════════════════════════      │
│ TOOL USAGE EXAMPLES - Follow this EXACT format:                   │
│ ════════════════════════════════════════════════════════════      │
│                                                                    │
│ Example 1 - Multiplication:                                        │
│ Thought: I need to multiply 15 times 8                             │
│ Action: calculator                                                 │
│ Action Input: {"expression": "15 * 8"}                             │
│ ...                                                                │
└───────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│ Ollama API Request (NO tools parameter):                           │
│                                                                    │
│ POST /api/chat                                                     │
│ {                                                                  │
│   "model": "qwen2.5:0.5b",                                         │
│   "messages": [...],                                               │
│   "tools": null   ← Not passed for REACT models                   │
│ }                                                                  │
└───────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│ Model Response (text-based):                                       │
│                                                                    │
│ Thought: I need to calculate 15 times 8                            │
│ Action: calculator                                                 │
│ Action Input: {"expression": "15 * 8"}                             │
└───────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│ Agent parses ReAct format:                                         │
│                                                                    │
│ 1. ToolParser.parse(content)                                       │
│ 2. Extract: Action="calculator"                                    │
│             Action Input={"expression": "15 * 8"}                  │
│ 3. Execute: result = calculator("15 * 8") → "120"                 │
│ 4. Add Observation to memory                                       │
│ 5. Continue loop for next step                                     │
└───────────────────────────────────────────────────────────────────┘
```

### NONE Tool Support Flow (with Soul)

```
User Prompt: "Read the file at /tmp/test.txt"
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│ System Prompt (NONE mode + Soul):                                  │
│                                                                    │
│ # Nova Helper                                                      │
│ A helpful AI assistant...                                          │
│                                                                    │
│ ## Persona                                                         │
│ You are Nova, a friendly and capable AI assistant...              │
│                                                                    │
│ ## Identity                                                        │
│ Your core identity includes being helpful, accurate...            │
│                                                                    │
│ [+ Tool descriptions appended because soul != None]                │
│                                                                    │
│ Available tools:                                                   │
│   - read_file: Read contents of a file                             │
│     Parameters: file_path: Path to the file                        │
│ ...                                                                │
└───────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│ Model Response (potentially wrong format):                         │
│                                                                    │
│ Final Answer: I cannot read files directly...                      │
│                    OR                                              │
│ Thought: I need to read the file                                   │
│ Action: read_file                                                  │
│ Action Input: {"file_path": "/tmp/test.txt"}                       │
└───────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│ Agent fallback handling:                                           │
│                                                                    │
│ Case A: Model outputs ReAct format                                 │
│ ─────────────────────────────────────                              │
│ 1. Soul+NONE block (lines 648-674) detects ReAct                  │
│ 2. Parse: Action="read_file", args={"file_path": "..."}           │
│ 3. Execute tool                                                    │
│ 4. Success!                                                         │
│                                                                    │
│ Case B: Model outputs "Final Answer" without tools                │
│ ─────────────────────────────────────────────────────              │
│ 1. Check if prompt requires tool (lines 676-745)                  │
│ 2. If "read_file" needed with args → send reminder                │
│ 3. If "get_date" needed (no args) → auto-execute                  │
│                                                                    │
└───────────────────────────────────────────────────────────────────┘
```

---

## Part 5: Key Files Reference

| File | Purpose |
|------|---------|
| `agent.py` | Main agent class, tool support detection, ReAct loop |
| `core/prompts.py` | System prompt templates, few-shot examples, tool prompts |
| `core/model_family_config.py` | Family-specific configs, stop tokens, prompt styles |
| `backends/ollama.py` | Ollama API, tool support testing |
| `soul/loader.py` | Soul package loading, system prompt building |
| `tools/builtins.py` | Tool implementations (calculator, shell, etc.) |
| `core/tool_parse.py` | ReAct format parsing |

---

## Summary

1. **Tool Support Detection**:
   - Cached in `~/.cache/agentnova/tool_support.json`
   - Test via `agentnova models --tool_support`
   - Default: `REACT` for untested models

2. **Prompt Building**:
   - NATIVE: Minimal hints (tools via API)
   - REACT: Full tool descriptions + format instructions + few-shot
   - NONE: Family-specific or generic non-tool prompt

3. **Soul Integration**:
   - Soul provides persona/identity
   - Tools appended separately (CRITICAL!)
   - Level-based disclosure (1-3)

4. **Fallbacks for NONE + Soul**:
   - ReAct parsing from model output
   - Auto-execute for no-arg tools (get_date, get_time)
   - Send reminder for arg-required tools