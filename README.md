# ⚛️ AgentNova R02.2

A minimal, hackable agentic framework engineered to run **entirely locally** with [Ollama](https://ollama.com) or [BitNet](https://github.com/microsoft/BitNet).

Inspired by the architecture of OpenClaw, rebuilt from scratch for local-first operation.

**Written by [VTSTech](https://www.vts-tech.org)** · [GitHub](https://github.com/VTSTech/AgentNova)

[![GitHub commits](https://badgen.net/github/commits/VTSTech/AgentNova)](https://GitHub.com/VTSTech/AgentNova/commit/) [![GitHub latest commit](https://badgen.net/github/last-commit/VTSTech/AgentNova)](https://GitHub.com/VTSTech/AgentNova/commit/)

[![PyPi](https://img.shields.io/badge/PyPi-PyPi-2ea44f?logo=PyPi)](https://pypi.org/project/agentnova/)
[![License](https://img.shields.io/badge/License-MIT-blue)](#license) [![Go to Python website](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2FVTSTech%2FAgentNova%2Frefs%2Fheads%2Fmain%2Fpyproject.toml&query=project.requires-python&label=python&logo=python&logoColor=white)](https://python.org)

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [Architecture.md](https://github.com/VTSTech/AgentNova/blob/main/Architecture.md) | Technical documentation for developers (directory structure, core design, orchestrator modes) |
| [CHANGELOG.md](https://github.com/VTSTech/AgentNova/blob/main/CHANGELOG.md) | Version history and release notes (includes LocalClaw history) |
| [TESTS.md](https://github.com/VTSTech/AgentNova/blob/main/TESTS.md) | Benchmark results, model recommendations, and testing guide |

---

## Installation

```bash

# Install from GitHub using pip:
pip install git+https://github.com/VTSTech/AgentNova.git
```

### Backward Compatibility

The package was previously named `localclaw`. For backward compatibility:

```bash
# Old package name still works (shows deprecation warning)
pip install localclaw

# Old CLI command still works
localclaw run "What is the capital of Japan?"  # Redirects to agentnova

# Old imports still work (with deprecation warning)
import localclaw  # Re-exports from agentnova
```

We recommend updating to the new package name:

```python
# Old
import localclaw
from localclaw import Agent

# New
import agentnova
from agentnova import Agent
```

### From Source

```bash
git clone https://github.com/VTSTech/AgentNova.git
cd AgentNova
pip install -e .
```

### No Installation Required

AgentNova uses only Python stdlib — no dependencies! You can also just copy the `agentnova` directory into your project:

```bash
cp -r agentnova /path/to/your/project/
```

---

## Quick Start

### 1. Test Model Tool Support (Recommended First Step)

```bash
# Test all models for native tool support
agentnova models --tool_support

# Results saved to tested_models.json for future reference
```

### 2. Single prompt

```bash
# Simple Q&A
agentnova run "What is the capital of Japan?"

# With streaming output
agentnova run "Tell me a joke." --stream

# Specify a model
agentnova run "Explain quantum computing" -m llama3.2:3b
```

### 3. Interactive chat

```bash
# Start interactive session
agentnova chat -m qwen2.5-coder:0.5b

# With tools enabled
agentnova chat -m llama3.1:8b --tools calculator,shell,read_file,write_file

# With skills loaded
agentnova chat -m llama3.2:3b --skills skill-creator --tools write_file,shell

# Fast mode (reduced context for speed)
agentnova chat -m qwen2.5-coder:0.5b --fast --verbose
```

### 4. Using BitNet backend

```bash
agentnova chat --backend bitnet --force-react
agentnova run "Calculate 17 * 23" --backend bitnet --tools calculator
```

---

## Key Features

- **Zero dependencies** — uses Python stdlib only
- **Ollama + BitNet backends** — switch with `--backend` flag
- **Three-tier tool support** — native, ReAct, or none (auto-detected per model)
- **Agent Skills** — follows [Agent Skills specification](https://agentskills.io/)
- **Small model optimized** — pure reasoning mode for sub-500M models
- **Built-in security** — path validation, command blocklist, SSRF protection

---

## Tool Support Levels

AgentNova automatically detects each model's tool support level:

| Level | Description | When to Use |
|-------|-------------|-------------|
| `native` | Ollama API tool-calling | Models trained for function calling |
| `react` | Text-based ReAct prompting | Models that accept tools but need format guidance |
| `none` | No tool support | Models that reject tools; use pure reasoning |

### Testing Tool Support

```bash
# Test all models
agentnova models --tool_support

# Example output:
  Model                                      Family       Context    Tool Support
  ──────────────────────────────────────────────────────────────────────────────
  gemma3:270m                                gemma3       32K        ○ none
  granite4:350m                              granite      32K        ✓ native
  qwen2.5-coder:0.5b-instruct-q4_k_m         qwen2        32K        ReAct
  functiongemma:270m                         gemma3       32K        ✓ native
```

### Performance by Tool Support

R02.2 benchmark results (15-test suite):

| Model | Params | Tool Support | Score | Time |
|-------|--------|--------------|-------|------|
| **`granite3.1-moe:1b`** | 1B MoE | react | **93% (14/15)** | 87.8s |
| **`llama3.2:1b`** | 1.2B | native | **87% (13/15)** | 150.2s |
| `dolphin3.0-qwen2.5:0.5b` | 500M | none | 73% (11/15) | 27.2s |
| `qwen3:0.6b` | 600M | react | 67% (10/15) | 189.3s |
| `qwen2.5-coder:0.5b` | 494M | react | 60% (9/15) | 133.1s |

**Quick Diagnostic (Test 15 - 5 questions, ~30s/model):**

| Model | Score | Tool Support |
|-------|-------|--------------|
| **`qwen3.5:0.8b`** | **100%** | native |
| **`qwen2.5:0.5b`** | **100%** | react |
| `functiongemma:270m` | 80% | native |
| `granite4:350m` | 80% | native |
| `qwen3:0.6b` | 60% | react |

**Key improvements in R02.2**:
- **+13%** for granite3.1-moe:1b (80% → 93%) from few-shot fix
- **+20%** for llama3.2:1b (67% → 87%) from observation role fix
- **qwen3:0.6b restored** from 0% (broken) with `think=False` API fix
- **qwen3.5:0.8b** new sub-1B champion with 100% on quick diagnostic

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `run "prompt"` | Run single prompt and exit |
| `chat` | Interactive multi-turn conversation |
| `models` | List available Ollama models with tool support info |
| `tools` | List built-in tools |
| `skills` | List available Agent Skills |
| `test [example]` | Run example/test scripts (`--list` to see all) |
| `modelfile [model]` | Show model's Modelfile system prompt |

### Key Flags

| Flag | Description |
|------|-------------|
| `-m`, `--model` | Model name (default: qwen2.5-coder:0.5b) |
| `--tools` | Comma-separated tool list |
| `--skills` | Comma-separated skill list |
| `--backend` | `ollama` or `bitnet` |
| `--stream` | Stream output token-by-token |
| `--fast` | Preset: reduced context for speed |
| `-v`, `--verbose` | Show tool calls and timing |
| `--acp` | Enable ACP (Agent Control Panel) integration |
| `--use-mf-sys` | Use Modelfile system prompt instead of AgentNova default |
| `--force-react` | Force ReAct mode for all models |
| `--debug` | Show debug info (parsed tool calls, fuzzy matching) |
| `--num-ctx` | Context window size for test commands |
| `--num-predict` | Max tokens to predict for test commands |

### Models Command

```bash
# List models with family, context size, and tool support
agentnova models

# Test each model for native tool support (recommended)
agentnova models --tool_support
```

Output shows:
- **Model** - Model name
- **Family** - Model family from Ollama API
- **Context** - Context window size
- **Tool Support** - `✓ native`, `ReAct`, `○ none`, or `untested`

```
⚛️ AgentNova R02.2 Models
  Model                                      Family       Context    Tool Support
  ──────────────────────────────────────────────────────────────────────────────
  gemma3:270m                                gemma3       32K        ○ none
  granite4:350m                              granite      32K        ✓ native
  qwen2.5-coder:0.5b-instruct-q4_k_m         qwen2        32K        ReAct
  functiongemma:270m                         gemma3       32K        untested

  1 model(s) untested. Use --tool_support to detect native support.
```

### Test Command Examples

```bash
# List all available tests
agentnova test --list

# Quick diagnostic - 5 questions, ~30s/model (NEW in R02.2)
agentnova test 15 --model granite3.1-moe:1b
agentnova test 15 --model all --debug

# Run GSM8K benchmark (50 math questions)
agentnova test 14 --acp --timeout 6400

# Run with debug output
agentnova test 02 --debug --verbose
```

---

## Built-in Tools

| Tool | Description |
|------|-------------|
| `calculator` | Evaluate math expressions |
| `python_repl` | Execute Python code |
| `shell` | Run shell commands |
| `read_file` | Read file contents |
| `write_file` | Write content to file |
| `list_directory` | List directory contents |
| `http_get` | HTTP GET request |
| `save_note` / `get_note` | Save and retrieve notes |

---

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `BITNET_BASE_URL` | BitNet server URL | `http://localhost:8765` |
| `ACP_BASE_URL` | ACP (Agent Control Panel) server URL | `http://localhost:8766` |
| `AGENTNOVA_BACKEND` | Backend: `ollama` or `bitnet` | `ollama` |
| `AGENTNOVA_MODEL` | Default model | `qwen2.5-coder:0.5b-instruct-q4_k_m` |
| `AGENTNOVA_SECURITY_MODE` | Security mode: `strict`, `permissive`, `disabled` | `permissive` |

---

## Setup Ollama

```bash
# Make sure Ollama is running:
ollama serve

# Pull a model:
ollama pull qwen2.5-coder:0.5b-instruct-q4_k_m

# Test tool support:
agentnova models --tool_support
```

---

## About

**⚛️ AgentNova ** is written and maintained by **VTSTech**.

- 🌐 Website: [https://www.vts-tech.org](https://www.vts-tech.org)
- 📦 GitHub: [https://github.com/VTSTech/AgentNova](https://github.com/VTSTech/AgentNova)
- 💻 More projects: [https://github.com/VTSTech](https://github.com/VTSTech)

---

For more details, see:
- [Architecture.md](https://github.com/VTSTech/AgentNova/blob/main/Architecture.md) — Technical architecture and design decisions
- [CHANGELOG.md](https://github.com/VTSTech/AgentNova/blob/main/CHANGELOG.md) — Version history and release notes
- [TESTS.md](https://github.com/VTSTech/AgentNova/blob/main/TESTS.md) — Benchmark results and model recommendations
