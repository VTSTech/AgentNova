# ⚛️ AgentNova

**Status: Alpha**

A minimal, hackable agentic framework engineered for local LLM inference.

## Features

- **Zero dependencies** — Uses Python stdlib only (urllib for HTTP)
- **Ollama + BitNet backends** — Switch with `--backend` flag
- **Three-tier tool support** — Native, ReAct, or none (auto-detected)
- **Small model optimized** — Fuzzy matching, argument normalization
- **Built-in security** — Path validation, command blocklist, SSRF protection
- **Multi-agent orchestration** — Router, pipeline, and parallel modes

## Installation

```bash
# From source
git clone https://github.com/VTSTech/AgentNova.git
cd AgentNova
pip install -e .

# Or from PyPI (when published)
pip install agentnova
```

## Quick Start

### CLI Usage

```bash
# Run a single prompt
agentnova run "What is 15 * 8?" --tools calculator

# Interactive chat
agentnova chat -m qwen2.5:0.5b --tools calculator,shell

# Autonomous agent mode
agentnova agent -m qwen2.5:7b --tools calculator,shell,write_file

# List available models
agentnova models

# List available tools
agentnova tools
```

### Python API

```python
from agentnova import Agent
from agentnova.tools import make_builtin_registry

# Create tools
tools = make_builtin_registry().subset(["calculator", "shell"])

# Create agent
agent = Agent(
    model="qwen2.5:0.5b",
    tools=tools,
    backend="ollama",
)

# Run
result = agent.run("What is 15 * 8?")
print(result.final_answer)
print(f"Completed in {result.total_ms:.0f}ms")
```

### Multi-Agent Orchestration

```python
from agentnova import Agent, Orchestrator, AgentCard

orchestrator = Orchestrator(mode="router")

# Register specialized agents
orchestrator.register(AgentCard(
    name="math_agent",
    description="Handles mathematical calculations",
    capabilities=["calculate", "math", "compute"],
    tools=["calculator"],
))

orchestrator.register(AgentCard(
    name="file_agent",
    description="Handles file operations",
    capabilities=["read", "write", "file"],
    tools=["read_file", "write_file"],
))

# Route tasks to appropriate agent
result = orchestrator.run("Calculate 15 * 8 and save to file")
```

## Architecture

```
agentnova/
├── core/
│   ├── types.py         # Enum types
│   ├── models.py        # Data models
│   ├── memory.py        # Sliding window memory
│   ├── tool_parse.py    # Tool call extraction
│   ├── helpers.py       # Utilities (fuzzy match, security)
│   ├── prompts.py       # Model-specific prompts
│   └── model_config.py  # Model family configurations
├── tools/
│   ├── registry.py      # Tool registry
│   └── builtins.py      # Built-in tools
├── backends/
│   ├── base.py          # Abstract backend
│   ├── ollama.py        # Ollama backend
│   └── bitnet.py        # BitNet backend
├── skills/
│   └── loader.py        # Skill loader
├── agent.py             # Main Agent class
├── agent_mode.py        # Autonomous mode
├── orchestrator.py      # Multi-agent orchestration
├── config.py            # Configuration
└── cli.py               # Command-line interface
```

## Tool Support Levels

AgentNova supports three levels of tool use:

1. **Native** — Models with built-in function calling (qwen2.5, llama3.1+, mistral, etc.)
2. **ReAct** — Text-based tool use via reasoning prompts
3. **None** — Pure reasoning without tools

Tool support is auto-detected based on model family, but can be forced:

```python
agent = Agent(model="qwen2.5:0.5b", force_react=True)
```

## Model Families

Configured model families with optimized prompts:

- **qwen2.5** — Native tool support, excellent performance
- **llama3.1/3.2/3.3** — Native tool support
- **mistral/mixtral** — Native tool support
- **gemma2/gemma3** — ReAct mode, special prompting
- **granite/granitemoe** — Native tool support
- **phi3** — Native tool support
- **deepseek** — Native with `<think/>` tag handling

## Security Features

Built-in security for safe operation:

- **Command blocklist** — Blocks dangerous shell commands (rm, sudo, etc.)
- **Path validation** — Prevents access to sensitive directories
- **SSRF protection** — Blocks requests to local/internal URLs
- **Injection detection** — Detects shell injection patterns

## Configuration

Environment variables:

```bash
# Backend URLs
OLLAMA_BASE_URL=https://your-ollama-server.com    # Default: http://localhost:11434
BITNET_BASE_URL=http://localhost:8765              # BitNet server URL
BITNET_TUNNEL=https://your-tunnel.com              # Alternative BitNet URL
ACP_BASE_URL=http://localhost:8766                 # ACP server URL

# Agent settings
AGENTNOVA_BACKEND=ollama      # Default backend: ollama or bitnet
AGENTNOVA_MODEL=qwen2.5:0.5b  # Default model
AGENTNOVA_MAX_STEPS=10        # Maximum reasoning steps
AGENTNOVA_DEBUG=false         # Enable debug output
```

Check current configuration:
```bash
agentnova config
agentnova config --urls  # Show only URLs
```

## LocalClaw Redirect

The `localclaw` command is provided for backward compatibility:

```bash
# Both work identically
localclaw run "What is 2+2?"
agentnova run "What is 2+2?"
```

## Tests & Examples

AgentNova includes a suite of tests for validating agent capabilities:

```bash
# Basic agent test (no tools)
python -m agentnova.examples.00_basic_agent

# Quick 5-question diagnostic
python -m agentnova.examples.01_quick_diagnostic

# Tool usage tests (calculator, shell, datetime)
python -m agentnova.examples.02_tool_test

# Logic and reasoning tests (BBH-style)
python -m agentnova.examples.03_reasoning_test

# GSM8K math benchmark (50 questions)
python -m agentnova.examples.04_gsm8k_benchmark
```

### Test Categories

| Test | Questions | Focus |
|------|-----------|-------|
| Quick Diagnostic | 5 | Calculator tool, multi-step reasoning |
| Tool Test | 10 | Calculator, shell, datetime tools |
| Reasoning Test | 13 | Logic, deduction, patterns, spatial |
| GSM8K Benchmark | 50 | Math word problems |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run unit tests
pytest

# Format code
black agentnova
ruff check agentnova
```

## License

MIT License - See LICENSE file for details.

## Author

**VTSTech** — [https://www.vts-tech.org](https://www.vts-tech.org)

## Contributing

Contributions welcome! Please read the contributing guidelines first.

## Acknowledgments

- Built for local inference with [Ollama](https://ollama.ai)
- Optimized for small, efficient models
- Inspired by ReAct and other agentic frameworks
