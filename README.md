# ⚛️ AgentNova R03.6

**Status: Alpha**

A minimal, hackable agentic framework engineered to run **entirely locally** with [Ollama](https://ollama.com) or [BitNet](https://github.com/microsoft/BitNet).

Inspired by the architecture of OpenClaw, rebuilt from scratch for local-first operation.

**Written by [VTSTech](https://www.vts-tech.org)** · [GitHub](https://github.com/VTSTech/AgentNova)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/VTSTech/AgentNova/blob/main/AgentNova.ipynb)
[![GitHub commits](https://badgen.net/github/commits/VTSTech/AgentNova)](https://GitHub.com/VTSTech/AgentNova/commit/) [![GitHub latest commit](https://badgen.net/github/last-commit/VTSTech/AgentNova)](https://GitHub.com/VTSTech/AgentNova/commit/)

[![pip - agentnova](https://img.shields.io/badge/pip-agentnova-2ea44f?logo=PyPi)](https://pypi.org/project/agentnova/) [![PyPI version fury.io](https://badge.fury.io/py/agentnova.svg)](https://pypi.org/project/agentnova/) [![PyPI download month](https://img.shields.io/pypi/dm/agentnova.svg)](https://pypi.org/project/agentnova/) [![PyPI download day](https://img.shields.io/pypi/dd/agentnova.svg)](https://pypi.org/project/agentnova/)

[![License](https://img.shields.io/badge/License-MIT-blue)](#license) [![Go to Python website](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2FVTSTech%2FAgentNova%2Frefs%2Fheads%2Fmain%2Fpyproject.toml&query=project.requires-python&label=python&logo=python&logoColor=white)](https://python.org)

<img width="1378" height="996" alt="image" src="https://github.com/user-attachments/assets/0fe69695-73d9-4ce1-999f-08443f879971" />

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [Architecture.md](https://github.com/VTSTech/AgentNova/blob/main/Architecture.md) | Technical documentation for developers (directory structure, core design, orchestrator modes) |
| [CHANGELOG.md](https://github.com/VTSTech/AgentNova/blob/main/CHANGELOG.md) | Version history and release notes (includes LocalClaw history) |
| [TESTS.md](https://github.com/VTSTech/AgentNova/blob/main/TESTS.md) | Benchmark results, model recommendations, and testing guide |

## Features

- **Zero dependencies** — Uses Python stdlib only (urllib for HTTP)
- **Ollama + BitNet backends** — Switch with `--backend` flag
- **Dual API support** — OpenResponses (`--api resp`) and Chat-Completions (`--api comp`)
- **Three-tier tool support** — Native, ReAct, or none (auto-detected)
- **Small model optimized** — Fuzzy matching, argument normalization
- **Built-in security** — Path validation, command blocklist, SSRF protection
- **Multi-agent orchestration** — Router, pipeline, and parallel modes
- **Soul Spec v0.5** — Persona packages with progressive disclosure
- **ACP v1.0.5 integration** — Agent Control Panel for monitoring and control
- **AgentSkills spec** — Skill loading with SPDX license validation
- **Thinking models support** — Automatic handling of qwen3, deepseek-r1 thinking mode

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

# Use Chat-Completions API (OpenAI-compatible)
agentnova chat -m qwen2.5:0.5b --api comp

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

### Chat-Completions Streaming

```python
from agentnova.backends import get_backend
from agentnova.core.types import ApiMode

# Use Chat-Completions mode with streaming
backend = get_backend("ollama", api_mode=ApiMode.COMPLETIONS)

for chunk in backend.generate_completions_stream(
    model="qwen2.5:0.5b",
    messages=[{"role": "user", "content": "Hello!"}],
    response_format={"type": "json_object"}
):
    print(chunk["delta"], end="", flush=True)
```

### Skill License Validation

```python
from agentnova.skills import validate_spdx_license, parse_compatibility

# Validate SPDX license identifier
valid, msg = validate_spdx_license("MIT")  # (True, "Valid SPDX identifier: MIT")
valid, msg = validate_spdx_license("Custom")  # (False, "Unknown license...")

# Parse compatibility requirements
compat = parse_compatibility("python>=3.8, ollama")
# Returns: {"python": ">=3.8", "runtimes": ["ollama"], "frameworks": []}
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

## Tool Support Levels

AgentNova supports three levels of tool use:

1. **Native** — Models with built-in function calling (qwen2.5, llama3.1+, mistral, granite, functiongemma)
2. **ReAct** — Text-based tool use via reasoning prompts (qwen2.5-coder, qwen3)
3. **None** — Pure reasoning without tools

Tool support is auto-detected by running `agentnova models --tool-support`. Results are cached in `~/.cache/agentnova/tool_support.json`.

```bash
# Test and cache tool support for all models
agentnova models --tool-support

# Re-test (ignore cache)
agentnova models --tool-support --no-cache
```

You can also force ReAct mode:

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

### CLI Options (run, chat, agent)

| Option | Description |
|--------|-------------|
| `--api resp\|comp` | API mode: OpenResponses (default) or Chat-Completions |
| `--response-format text\|json` | Response format (Chat-Completions mode) |
| `--truncation auto\|disabled` | Truncation behavior for long responses |
| `--soul <path>` | Load Soul Spec persona package |
| `--soul-level 1-3` | Progressive disclosure level |
| `--num-ctx <tokens>` | Context window size (default: 4096) |
| `--timeout <seconds>` | Request timeout (default: 120) |
| `--acp` | Enable ACP (Agent Control Panel) logging |
| `--acp-url <url>` | ACP server URL |

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

### Benchmark Results (Quick Diagnostic)

| Model | Score | Time | Tool Support |
|-------|-------|------|-------------|
| functiongemma:270m | 5/5 (100%) | ~20s | native |
| granite4:350m | 5/5 (100%) | ~50s | native |
| qwen2.5:0.5b | 5/5 (100%) | 38s | native |
| qwen2.5-coder:0.5b | 5/5 (100%) | 93s | react |
| qwen3:0.6b | 5/5 (100%) | 70s | react |

All tested models achieve 100% on the Quick Diagnostic. Native models are ~2x faster than ReAct models due to direct API tool calling.

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
