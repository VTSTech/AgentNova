# Changelog

All notable changes to AgentNova refactor-1 will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [refactor-1] - 2026-03-24

### Major Architecture Refactoring

Complete reorganization of the codebase for improved modularity, type safety, and maintainability.

### Added

#### New Module Structure
- **`backends/`** - Pluggable inference backend system
  - `base.py` - Abstract `BaseBackend` class with common interface
  - `ollama.py` - Ollama backend implementation
  - `bitnet.py` - BitNet backend implementation
  - Backend registry with `get_backend()` and `register_backend()`
- **`tools/`** - Tool registry system
  - `registry.py` - `ToolRegistry` class with decorator-based tool registration
  - `builtins.py` - Built-in tools (calculator, shell, file operations)
  - `subset()` method for creating filtered tool sets
- **`agent.py`** - Clean Agent class (~700 lines vs main's ~2700 lines)
  - Focused on single responsibility: orchestrate LLM + tools
  - Tool support detection: native, react, or none
  - Auto-synthesis for struggling models
- **`agent_mode.py`** - Autonomous agent mode
  - State machine: IDLE → WORKING → PAUSED → STOPPING
  - Task planning with LLM or heuristic fallback
  - Rollback support for undo operations
- **`orchestrator.py`** - Multi-agent orchestration
  - `AgentCard` for agent discovery
  - Task delegation between agents
- **`model_discovery.py`** - Dynamic model discovery utilities
  - `get_models()` - List available models
  - `pick_best_model()` - Auto-select best available
  - `pick_models_for_benchmark()` - Select benchmark suite
  - `model_exists()` - Check model availability
- **`shared_args.py`** - Shared CLI argument parsing
  - `SharedConfig` dataclass with environment variable fallback
  - `--fast`, `--num-ctx`, `--num-predict`, `--acp`, `--acp-url` flags

#### ACP Plugin Integration
- **`acp_plugin.py`** - Agent Control Panel integration
  - Bootstrap with identity establishment
  - Activity logging via `/api/action`
  - Shell command logging via `/api/shell/add`
  - STOP flag handling with hints processing
  - A2A (Agent-to-Agent) JSON-RPC 2.0 support
  - Agent Card discovery
  - Token budget tracking and cost estimation
  - Clean disconnect (unregister without server shutdown)

#### CLI Improvements
- **ASCII banner** - Braille art banner with color support
- **Tool support testing** - `--tool-support` flag for `models` command
  - Actually tests models by making API calls
  - Results cached in `~/.cache/agentnova/tool_support.json`
  - `--no-cache` to ignore cached results
- **Test subcommand** - `agentnova test <id>` for running diagnostic tests
  - Tests 00-04 available
  - `--list` to show available tests
  - `--acp` for ACP integration during tests
- **Config command** - `agentnova config` to show current configuration
- **Version command** - `agentnova version` with banner

### Changed

#### Type System
- Full type hints throughout codebase
- `BackendType` enum (OLLAMA, BITNET)
- `ToolSupportLevel` enum (NATIVE, REACT, NONE)
- `StepResultType` enum
- Dataclasses: `Tool`, `ToolParam`, `StepResult`, `AgentRun`, `BackendConfig`

#### Backend Interface
- Unified `generate()` and `generate_stream()` methods
- Consistent response format across backends
- `list_models()`, `test_tool_support()`, `is_running()` methods
- `get_model_context_size()` with family-based defaults

#### Tool Registration
- Decorator-based: `@registry.tool(description="...")`
- Automatic JSON schema generation
- Fuzzy name matching for small model hallucinations
- `ToolRegistry.subset(["calculator", "shell"])` for filtered sets

### Removed (from main)
- Monolithic `agent.py` (2700+ lines)
- Inline tool definitions
- Hardcoded model configurations
- Duplicate code paths

### File Structure Comparison

```
main/                           refactor-1/
├── agent.py (2700 lines)       ├── agent.py (700 lines)
├── agent_mode.py               ├── agent_mode.py (cleaned)
├── cli.py (2600 lines)         ├── cli.py (900 lines)
├── core/                       ├── core/
│   ├── agent.py                │   ├── models.py (dataclasses)
│   ├── orchestrator.py         │   ├── types.py (enums)
│   ├── tools.py                │   └── ...
│   └── ...                     ├── backends/
├── bitnet_client.py            │   ├── base.py
├── ollama_client.py            │   ├── ollama.py
└── tested_models.json          │   └── bitnet.py
                                ├── tools/
                                │   ├── registry.py
                                │   └── builtins.py
                                ├── model_discovery.py
                                └── shared_args.py
```

### Test Results (Quick Diagnostic)

| Model | Score | Time | Tool Support |
|-------|-------|------|--------------|
| qwen2.5:0.5b | 5/5 (100%) | 60.5s | native |
| qwen2.5-coder:0.5b | 5/5 (100%) | 37.7s | JSON parsed |
| granite4:350m | 5/5 (100%) | 43.9s | native |
| qwen:0.5b | 0/5 (0%) | 45.0s | react |

### Migration Guide

```python
# Old (main)
from agentnova.core.agent import Agent
from agentnova.core.ollama_client import OllamaClient

client = OllamaClient()
agent = Agent(model="qwen2.5:0.5b", ollama_client=client)

# New (refactor-1)
from agentnova import Agent, get_backend

backend = get_backend("ollama")
agent = Agent(model="qwen2.5:0.5b", backend=backend)

# Or even simpler
from agentnova import Agent
agent = Agent(model="qwen2.5:0.5b")  # Uses default backend
```

### Known Issues
- Skills system simplified (loader only, no built-in skills)
- Examples reduced to 6 core tests
- No `modelfile` or `skills` CLI commands yet

---

For main branch changelog, see: https://github.com/VTSTech/AgentNova/blob/main/CHANGELOG.md
