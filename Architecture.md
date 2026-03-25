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

## Tool Support Detection

Models are tested and cached in `~/.cache/agentnova/tool_support.json`:

```bash
# Test all models
agentnova models --tool-support

# Show cached results
agentnova models
```

Detection logic:
1. Send request with tool schema
2. Check for native `tool_calls` in API response → **native**
3. Check for JSON tool call in text content → **react**
4. Check for "does not support tools" error → **none**