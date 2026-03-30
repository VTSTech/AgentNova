# CREDITS.md

AgentNova is built upon the work of many open-source projects, model creators, API designers, and community specifications. This document acknowledges every project, inspiration, API, model creator, and specification that makes AgentNova possible.

---

## Author

**VTSTech (Nigel Todman)** — [https://www.vts-tech.org](https://www.vts-tech.org) · [GitHub](https://github.com/VTSTech)

Licensed under the **MIT License**. Copyright (c) 2026 Nigel Todman.

---

## Inference Backends

These projects provide the runtime environments that AgentNova connects to for local LLM inference.

| Project | Description | Link |
|---------|-------------|------|
| **Ollama** | Local LLM inference server supporting a vast ecosystem of open-weight models with native tool calling and OpenAI-compatible APIs | [https://ollama.com](https://ollama.com) |
| **BitNet** | Microsoft's 1-bit quantized LLM inference engine optimized for extreme CPU efficiency | [https://github.com/microsoft/BitNet](https://github.com/microsoft/BitNet) |

---

## Architectural Inspirations

AgentNova draws design philosophy and patterns from several influential projects and research.

### OpenClaw

AgentNova was **inspired by the architecture of OpenClaw**, rebuilt from scratch for local-first operation. The original OpenClaw project served as the conceptual foundation upon which AgentNova was designed, with a focus on stripping away cloud dependencies and enabling fully local agentic workflows.

### ReAct (Reasoning + Acting)

The core agentic loop in AgentNova implements the **ReAct paradigm** — a framework where language models interleave reasoning traces (Thought) with action execution (Action/Action Input), observe results (Observation), and produce final answers. This pattern, introduced in the paper *"ReAct: Synergizing Reasoning and Acting in Language Models"* (Yao et al., 2022), is the backbone of how AgentNova orchestrates tool-calling with models that lack native function calling support. The unified ReAct prompting system, enhanced observation formatting, and few-shot examples for small models all stem from this research.

### ATLAS-Autonomous

The **retry-with-error-feedback** feature introduced in R04.1 was inspired by the [ATLAS-Autonomous](https://github.com/itigges22/ATLAS) benchmark infrastructure. The ATLAS project demonstrated that giving models a chance to correct failed tool calls before the agent gives up significantly improves success rates on error-prone tasks. AgentNova adopted this concept, implementing it as configurable retry context injection that works across both native tool-calling and ReAct text-based paths.

---

## Specifications & Standards

AgentNova implements and complies with several open specifications and standards. These define how the framework handles API interactions, tool calling, persona management, agent monitoring, and skill packaging.

| Specification | Version | Compliance | Description | Link |
|---------------|:-------:|:----------:|-------------|------|
| **OpenResponses** | 1.0 | 100% | Multi-provider interoperable LLM interface defining items (MessageItem, FunctionCallItem, FunctionCallOutputItem, ReasoningItem), response state machines (queued, in_progress, completed, failed, incomplete, cancelled), tool_choice modes (auto, required, none, specific, allowed_tools), and SSE streaming events | [https://www.openresponses.org/specification](https://www.openresponses.org/specification) |
| **OpenAI Chat Completions API** | — | Full | OpenAI-compatible endpoint format (`/v1/chat/completions`) for cross-platform tool integration. Supports tool_choice, response_format, logprobs, streaming (SSE), and extended parameters (stop, presence_penalty, frequency_penalty, top_p) | [OpenAI API Reference](https://platform.openai.com/docs/api-reference/chat) |
| **Soul Spec** | v0.5 | 100% | ClawSouls specification for persona packages (soul.json manifests, SOUL.md/IDENTITY.md/STYLE.md files, progressive disclosure levels 1-3, calibration examples, embodied agent support) | [https://github.com/clawsouls/soulspec](https://github.com/clawsouls/soulspec) |
| **ACP** | v1.0.5 | Full (mandatory requirements, hints, orphan handling, nudge support, batch ops, shutdown, A2A, JSON-RPC 2.0, primary agent nudge delivery) | Agent Control Panel specification for monitoring, activity logging (READ, WRITE, EDIT, BASH, SEARCH, API, A2A), STOP flag handling, agent-to-agent communication, and health tracking | [VTSTech/ACP-Agent-Control-Panel](https://github.com/VTSTech/ACP-Agent-Control-Panel) |
| **AgentSkills** | — | 100% | Skill packaging specification defining SKILL.md with YAML frontmatter (name, description, license, compatibility, allowed-tools), scripts/references/assets directories, SPDX license validation, and environment compatibility checking | [https://agentskills.io/](https://agentskills.io/) |
| **JSON-RPC 2.0** | 2.0 | Full | Remote procedure call protocol used for A2A (Agent-to-Agent) messaging between agents and the ACP server | [https://www.jsonrpc.org/specification](https://www.jsonrpc.org/specification) |
| **Server-Sent Events (SSE)** | — | Full | Streaming protocol for real-time delivery of OpenResponses lifecycle events (response.queued, response.in_progress, response.output_item.added, response.output_text.delta, etc.) | [W3C Specification](https://html.spec.whatwg.org/multipage/server-sent-events.html) |
| **SPDX License Identifiers** | 3.x | Subset | Standardized license identifier format used for skill license validation. AgentNova validates skill licenses against a curated set of common SPDX identifiers (MIT, Apache-2.0, GPL-3.0, BSD-3-Clause, etc.) including WITH exception support (e.g., "Apache-2.0 WITH LLVM-exception") | [https://spdx.org/licenses/](https://spdx.org/licenses/) |
| **IANA Time Zone Database** | — | Used | Standardized timezone identifiers (e.g., "America/New_York", "Europe/London", "UTC") used by the `get_time` tool via Python's `zoneinfo` module | [IANA Time Zone Database](https://www.iana.org/time-zones) |
| **Keep a Changelog** | 1.0.0 | Used | Changelog formatting standard used for CHANGELOG.md | [https://keepachangelog.com/en/1.0.0/](https://keepachangelog.com/en/1.0.0/) |

---

## Model Creators & Supported Models

AgentNova is optimized to run efficiently on small, local LLMs. The framework includes family-specific configurations (prompting style, stop tokens, tool format, temperature defaults, thinking mode handling) for the following model families and their creators.

### Alibaba Cloud — Qwen Series

The **Qwen** family from Alibaba Cloud is the most extensively configured and tested model family in AgentNova. Multiple model sizes and variants are supported with native tool calling.

| Model | Parameters | Tool Support | Notes |
|-------|:----------:|:------------:|-------|
| **Qwen 2.5** (`qwen2.5`) | 0.5B – 72B | Native (XML) | ChatML format (`<\|im_start\|>`/`<\|im_end\|>`). Primary development target. Excellent performance at all sizes. |
| **Qwen 2.5 Coder** (`qwen2.5-coder`) | 0.5B – 32B | ReAct | Same family as Qwen 2.5 but different template — uses ReAct text parsing instead of native tool calling. |
| **Qwen 3** (`qwen3`) | 0.6B – 235B | Native (XML) | Extended thinking mode with `<think/>` tags. AgentNova sends `/no_think` directive by default for tool-calling workflows. |
| **Qwen 3.5** (`qwen35`) | 0.8B – TBD | Native (XML) | Successor to Qwen 3. Does NOT have thinking mode (simpler template than Qwen 3). |
| **Qwen 2** (`qwen2`) | 0.5B – 72B | Native (XML) | Earlier generation. Native tool support confirmed. |
| **Qwen** (base) | 0.5B – 7B | ReAct | Base Qwen model. Falls back to ReAct text parsing. |

### Meta AI — LLaMA Series

Meta's **LLaMA** family provides strong general-purpose performance with native tool calling support.

| Model | Parameters | Tool Support | Notes |
|-------|:----------:|:------------:|-------|
| **LLaMA 3.3** | 70B | Native | Latest LLaMA generation. Full native tool support. |
| **LLaMA 3.2** | 1B – 3B | Native | Smaller variants ideal for local deployment. |
| **LLaMA 3.1** | 8B – 405B | Native | Extended context (131K tokens). |
| **LLaMA 3** | 8B – 70B | Native | Original LLaMA 3 release. |

### Google — Gemma & FunctionGemma

Google's **Gemma** models offer compact, efficient inference with specific handling requirements.

| Model | Parameters | Tool Support | Notes |
|-------|:----------:|:------------:|-------|
| **Gemma 3** (`gemma3`) | 270M – 27B | None (ReAct) | Requires first-user system prompt style. No native tool calling — AgentNova uses ReAct prompting. Special `no_tools_system_prompt` for pure reasoning. |
| **Gemma 2** (`gemma2`) | 2B – 27B | None (ReAct) | Similar behavior to Gemma 3. |
| **FunctionGemma** | 270M | Native | Specialized function-calling variant. Native tool support confirmed. |

### IBM — Granite Series

IBM's **Granite** models are well-suited for enterprise and tool-calling tasks.

| Model | Parameters | Tool Support | Notes |
|-------|:----------:|:------------:|-------|
| **Granite 4** (`granite4`) | 350M | Native (XML) | Excellent tool-calling performance. Achieved 100% on diagnostic benchmarks at just 350M parameters. |
| **Granite 3.1 MoE** (`granitemoe`) | 1B (active) | Native (XML) | Mixture-of-Experts architecture. Has known schema dump issue and JSON truncation — AgentNova includes specific workarounds. |
| **Granite** (base) | Various | Native (XML) | Base Granite family with IBM-specific role token format (`<\|start_of_role\|>`). |

### DeepSeek

**DeepSeek** provides both standard and reasoning-specialized models.

| Model | Parameters | Tool Support | Notes |
|-------|:----------:|:------------:|-------|
| **DeepSeek-R1** (`deepseek-r1`) | 1.5B – 671B | Native | Reasoning model with extended thinking via `<think/>` tags. AgentNova strips think tags by default. |
| **DeepSeek** (standard) | Various | Native | Standard DeepSeek models including coder variants. |
| **DeepSeek Coder** | 1.3B – 33B | Varies | Code-specialized models. Tool support depends on specific variant. |

### Mistral AI — Mistral & Mixtral

| Model | Parameters | Tool Support | Notes |
|-------|:----------:|:------------:|-------|
| **Mistral** | 7B | Native | Full native tool support. |
| **Mixtral** | 8x7B (47B total) | Native | Mixture-of-Experts model with native tools. |

### Microsoft — Phi

| Model | Parameters | Tool Support | Notes |
|-------|:----------:|:------------:|-------|
| **Phi 3** (`phi3`) | 3.8B – 14B | Native | Microsoft's compact model. Large context window (128K tokens). |

### Community Fine-tunes

| Model | Base | Creator | Notes |
|-------|------|---------|-------|
| **Dolphin 3.0** (Qwen2.5) | 500M | [nchapman](https://huggingface.co/nchapman) | Dolphin fine-tune on Qwen 2.5 base. ChatML format. |
| **Dolphin 3.0** (LLaMA 3) | 1B | nchapman | Dolphin fine-tune on LLaMA 3. |

---

## APIs & Web Services

### DuckDuckGo — Web Search

The built-in `web_search` tool uses **DuckDuckGo Lite** (`https://lite.duckduckgo.com/lite/`) as its primary search endpoint, falling back to **DuckDuckGo HTML** (`https://html.duckduckgo.com/html/`) when Lite returns no results. This provides free, API-key-free web search capability directly from the command line or agent workflow.

### OpenAI Chat Completions API

AgentNova implements the **OpenAI Chat Completions API** format through Ollama's `/v1/chat/completions` endpoint. This enables integration with any tool or middleware that expects the OpenAI request/response format, including `tool_choice`, `response_format`, `logprobs`, `stop`, `presence_penalty`, `frequency_penalty`, `top_p`, and `n` parameters.

### Ollama API

AgentNova communicates with Ollama through two API endpoints:

- **`/api/chat`** — Ollama's native chat API (OpenResponses mode). Supports native tool calling, model listing (`/api/tags`), model inspection (`/api/show`), and streaming.
- **`/v1/chat/completions`** — OpenAI-compatible endpoint (Chat Completions mode). Supports SSE streaming, tool calling, and the full OpenAI parameter set.

### BitNet API

The BitNet backend communicates through a simple completion endpoint:

- **`/completion`** — Text completion API with `prompt`, `n_predict`, `temperature`, and `stop` parameters. No native tool calling support — AgentNova uses ReAct text parsing.

---

## Benchmarks & Evaluation Frameworks

AgentNova's test suite draws on and adapts questions from established evaluation benchmarks to measure reasoning, tool-calling, and knowledge capabilities.

| Benchmark | Source | Usage in AgentNova |
|-----------|--------|-------------------|
| **GSM8K** | [Cobbe et al., 2021](https://arxiv.org/abs/2110.14168) | 50 math word problems adapted for calculator tool-calling evaluation (`test 04_gsm8k_benchmark`) |
| **BIG-bench** | [Srivastava et al., 2022](https://arxiv.org/abs/2210.09261) | Common sense reasoning (25 Q), causal reasoning (25 Q), logical deduction (25 Q), general knowledge (25 Q), and implicit reasoning (25 Q) questions adapted for local LLM evaluation |
| **BIG-bench Hard (BBH)** | [Suzgun et al., 2022](https://arxiv.org/abs/2210.09261) | Reasoning test structure (14 Q across 8 categories: logical deduction, common sense, multi-step, pattern, counter-intuitive, spatial, causal, comparative) |

---

## Development Tools

| Tool | Purpose | Link |
|------|---------|------|
| **pytest** | Unit testing framework (`tests/` directory with 600+ tests covering skills, security, builtins, spec compliance, and agent behavior) | [https://pytest.org](https://pytest.org) |
| **black** | Opinionated Python code formatter (line-length: 100, target: Python 3.9-3.12) | [https://github.com/psf/black](https://github.com/psf/black) |
| **ruff** | Fast Python linter (rules: E, F, W, I) | [https://github.com/astral-sh/ruff](https://github.com/astral-sh/ruff) |
| **setuptools** | Build system and package distribution | [https://setuptools.pypa.io](https://setuptools.pypa.io) |

---

## Python Standard Library

AgentNova proudly uses **zero external dependencies** at runtime. The entire framework — HTTP requests, JSON parsing, tool execution, security validation, streaming, and all backend communication — relies exclusively on the Python standard library (`urllib`, `json`, `subprocess`, `math`, `datetime`, `re`, `os`, `pathlib`, `time`, `uuid`, `collections`, `itertools`, `zoneinfo`, `platform`). This design choice ensures maximum portability, minimal attack surface, and ease of installation.

---

## Additional Acknowledgments

- **Google Colab** — AgentNova provides a [Jupyter notebook](https://colab.research.google.com/github/VTSTech/AgentNova/blob/main/AgentNova.ipynb) for cloud-based experimentation.
- **PyPI** — Package distribution at [https://pypi.org/project/agentnova/](https://pypi.org/project/agentnova/).
- **badgen** and **shields.io** — Badge services used in the README for download counts, license, and commit tracking.
- The broader **local LLM community** — including the Ollama, Hugging Face, and open-source AI communities — whose collective work makes running powerful models locally possible.

---

*Last updated: 2026-03-30 (AgentNova R04.1)*