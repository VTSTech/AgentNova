## Architecture

AgentNova is a modular agent framework designed for local LLMs with tool-calling capabilities. It implements the OpenResponses specification for multi-provider, interoperable LLM interfaces.

```
agentnova/
├── core/
│   ├── types.py              # Enum types (StepResultType, BackendType, ApiMode)
│   ├── models.py             # Data models (Tool, ToolParam, StepResult, AgentRun)
│   ├── memory.py             # Sliding window conversation memory
│   ├── tool_parse.py         # ReAct/JSON tool call extraction (see Tool Parser section)
│   ├── helpers.py            # Utilities (fuzzy match, argument normalization, security)
│   ├── model_config.py       # Model configuration (temperature, max tokens)
│   ├── model_family_config.py # Family-specific behavior (stop tokens, formats)
│   └── openresponses.py      # OpenResponses specification types
│
├── tools/
│   ├── registry.py           # Tool registry with decorator-based registration
│   ├── builtins.py           # Built-in tools (calculator, shell, file ops, http)
│   └── sandboxed_repl.py     # Sandboxed Python REPL execution
│
├── backends/
│   ├── base.py               # Abstract BaseBackend class
│   ├── ollama.py             # Ollama backend (dual API: OpenResponses + Chat-Completions)
│   └── bitnet.py             # BitNet backend
│
├── skills/
│   ├── loader.py             # Skill loader (Agent Skills spec)
│   └── ...                   # Various skills (web-search, datetime, etc.)
│
├── soul/
│   ├── types.py              # Soul Spec v0.5 data structures
│   └── loader.py             # SoulLoader with progressive disclosure + dynamic tools
│
├── souls/
│   └── nova-helper/          # Default diagnostic assistant soul
│       ├── soul.json         # Manifest
│       ├── SOUL.md           # Persona definition (concise)
│       ├── IDENTITY.md       # Identity (concise)
│       └── STYLE.md          # Communication style (concise)
│
├── examples/                 # Test examples and benchmarks
│
├── agent.py                  # Main Agent class (OpenResponses agentic loop)
├── agent_mode.py             # Autonomous agent mode (state machine)
├── orchestrator.py           # Multi-agent orchestration
└── cli.py                    # Command-line interface
```

---

## Key Components

### Agent (`agent.py`)

The main Agent class implements the **OpenResponses Agentic Loop**:

```
1. Model samples from input
2. If tool call: execute tool, return observation, continue
3. If no tool call: return final output items
```

**Key principle**: All tool calls must come from the model itself. No fallbacks that bypass the AI model.

**Features**:
- Unified ReAct prompting for all models
- Soul Spec integration for persona/personality
- Dynamic tool injection into system prompt
- Default context window: 4096 tokens
- Debug output with OpenResponses item tracking

### OpenResponses Specification (`core/openresponses.py`)

Full implementation of the OpenResponses specification (https://www.openresponses.org/specification):

**Items**: Atomic units of context with lifecycle states
- `MessageItem`: Conversation turns (user/assistant/system)
- `FunctionCallItem`: Tool invocations from the model
- `FunctionCallOutputItem`: Tool execution results
- `ReasoningItem`: Model's internal thought process

**State Machines**:
```
Response: queued → in_progress → completed/failed/incomplete/cancelled
Items: in_progress → completed/failed/incomplete
```

**tool_choice modes**:
| Mode | Behavior |
|------|----------|
| `"auto"` | Model decides whether to call tools (default) |
| `"required"` | Model MUST call at least one tool |
| `"none"` | Model MUST NOT call tools |
| `ToolChoice.specific("name")` | Force specific tool |
| `ToolChoice.allowed_tools([...])` | Restrict to tool list |

```python
from agentnova import Agent
from agentnova.core.openresponses import ToolChoice

# Default: model decides
agent = Agent(model="qwen2.5:0.5b", tools=["calculator"])

# Force tool usage
agent = Agent(model="llama3", tools=["calculator"], tool_choice="required")

# Restrict to specific tools
agent = Agent(
    model="llama3",
    tools=["calculator", "shell", "read_file"],
    allowed_tools=["calculator"]  # Only calculator available
)

# Disable tools
agent = Agent(model="llama3", tools=["calculator"], tool_choice="none")
```

### Tool Parser (`core/tool_parse.py`)

Parses tool calls from model output in multiple formats:

**Supported Formats**:

1. **Plain ReAct format**:
```
Action: calculator
Action Input: {"expression": "15 * 8"}
```

2. **JSON-wrapped ReAct** (from small models):
```json
{
  "action": "calculator",
  "actionInput": {"expression": "15 * 8"}
}
```

3. **Markdown code block JSON**:
```json
{
  "action": "calculator",
  "action_input": {"expression": "15 * 8"}
}
```

4. **With Final Answer** (simultaneous):
```
Action: calculator
Action Input: {"expression": "15 * 8"}
Final Answer: 120
```

**Key variations handled**:
- `action`, `Action`, `ACTION`
- `actionInput`, `action_input`, `Action Input`
- Fuzzy matching for hallucinated tool names

### Soul System (`soul/`)

ClawSouls Soul Spec v0.5 support for persona packages:

**Progressive Disclosure**:
- Level 1: soul.json manifest only
- Level 2: + SOUL.md + IDENTITY.md
- Level 3: + STYLE.md + AGENTS.md + HEARTBEAT.md

**Dynamic Tool Injection**:
The static tool reference in SOUL.md is replaced with actual available tools at runtime:

```python
# Static in SOUL.md:
## Tool Reference (only use if available)
| Tool | When to use | Arguments |
...

# Dynamically replaced with actual tools:
### Tool Reference (only use if available)
| Tool | When to use | Arguments |
|------|-------------|-----------|
| `calculator` | Evaluate mathematical expressions | `{"expression": "..."}` |
```

**Cache Management**:
```python
from agentnova.soul import clear_soul_cache, load_soul

# Clear cache after modifying soul files
clear_soul_cache()

# Force reload from disk
soul = load_soul("nova-helper", reload=True)
```

---

## Data Flow

```
User Prompt
     │
     ▼
┌─────────────┐
│    Agent    │ ── loads soul (optional)
│             │ ── builds system prompt with dynamic tools
│             │ ── creates Response object (OpenResponses)
└─────────────┘
     │
     ▼
┌─────────────┐
│   Backend   │ ── sends to Ollama/BitNet (ReAct prompting)
└─────────────┘
     │
     ▼
┌─────────────┐
│ Tool Parser │ ── extracts tool calls from text
│             │ ── handles: ReAct, JSON-wrapped, markdown
│             │ ── extracts final_answer if present
└─────────────┘
     │
     ▼
┌─────────────┐
│Tool Registry│ ── executes tool (if allowed)
└─────────────┘
     │
     ▼
┌─────────────┐
│   Memory    │ ── adds Observation
└─────────────┘
     │
     ▼ (loop until Final Answer or max_steps)
     │
┌─────────────┐
│   Result    │ ── AgentRun with final_answer
└─────────────┘
```

---

## Tool Calling Strategy

### Unified ReAct Prompting

All models use ReAct prompting regardless of native tool capabilities. This provides:
- Consistent behavior across all models
- Predictable parsing
- Better control for small models

**System Prompt Structure**:
```
# Agent Name
Description

## Core Directives
1. Answer Accurately
2. Follow Instructions
3. Use Tools

### Tool Reference (only use if available)
| Tool | When to use | Arguments |
|------|-------------|-----------|
| `calculator` | Evaluate mathematical expressions | `{"expression": "..."}` |

**CRITICAL RULE**: If a tool is NOT in the available tools list, do NOT try to use it.

## Tool Calling Format (MANDATORY)

When you need to use a tool, output EXACTLY:

Action: <tool_name>
Action Input: <JSON arguments>

**Example**:
Action: calculator
Action Input: {"expression": "15 * 8"}

## Calculator Syntax (CRITICAL)

The calculator uses **Python syntax**. Use these correct formats:

| Natural Language | Correct Python Syntax |
|------------------|----------------------|
| "2 to the power of 10" | `2**10` |
| "square root of 144" | `sqrt(144)` or `144**0.5` |
| "15 times 8" | `15 * 8` |

## After Tool Result - MANDATORY

**IMMEDIATELY after receiving an Observation, output:**

```
Final Answer: <the result>
```

**DO NOT:**
- Call the same tool again with the result
- Call another tool unless you need MORE information

## Error Recovery

If a tool returns an error:
1. STOP and read the error message
2. THINK about what went wrong
3. TRY a different approach - do NOT repeat the same failed call
```

### Enhanced Observation Format

Tool results include contextual guidance to help small models understand the next action:

```python
# Success result - prompts for Final Answer
observation_msg = f"Observation: {result}\n\nNow output: Final Answer: <the result>"

# Error result - prompts for recovery with syntax hint
observation_msg = f"Observation: {error}\n\nNote: Try a different approach. For calculator, use Python syntax (e.g., 2**10 for power)."
```

This guidance is critical for models under 1B parameters that may not understand the ReAct flow without explicit direction.

### No Fallbacks

Following OpenResponses principles, these were removed:
- Greeting short-circuit
- Calculator synthesis for math prompts
- Auto-execution of no-arg tools
- Wrong datetime tool auto-correction
- Empty response retry with hints

The model MUST explicitly format tool calls.

---

## Dual API Support

AgentNova supports both OpenResponses and OpenAI Chat-Completions API endpoints through Ollama. This allows flexibility for different integration scenarios.

### API Modes

| Mode | Flag | Endpoint | Description |
|------|------|----------|-------------|
| **OpenResponses** | `--api resp` | `/api/chat` | Ollama native API (default) |
| **Chat-Completions** | `--api comp` | `/v1/chat/completions` | OpenAI-compatible API |

### When to Use Each Mode

**OpenResponses (`--api resp`)**:
- Default mode for Ollama-native deployments
- Full OpenResponses specification compliance
- Detailed item tracking with `[OpenResponses]` debug output
- Recommended for AgentNova-specific applications

**Chat-Completions (`--api comp`)**:
- OpenAI-compatible endpoint for cross-platform tools
- Cleaner debug output without OpenResponses internals
- Useful when integrating with OpenAI-compatible clients
- Required when using middleware that expects `/v1/chat/completions`

### Debug Output by Mode

**OpenResponses mode** shows internal state tracking:
```
[OpenResponses] tool_choice initialized: type=auto
[OpenResponses] Response created: id=resp_...
[OpenResponses] Response status: in_progress
[OpenResponses] Tool calls detected: 1
[OpenResponses] Parsed: name=calculator, args={'expression': '15 + 27'}
```

**Chat-Completions mode** shows API transport only:
```
[Ollama] Dispatching to OpenAI-compatible API (mode=comp)
[OpenAI-Comp] Request: tools=0
[OpenAI-Comp] Content: Action: calculator...
[OpenAI-Comp] Tool calls: []
```

### Usage

```bash
# Default: OpenResponses API
agentnova chat -m qwen2.5:0.5b

# Chat-Completions API
agentnova chat -m qwen2.5:0.5b --api comp

# With debug output
agentnova test 01 --api comp --debug
```

### Implementation Details

The `OllamaBackend` class handles both APIs:

```python
from agentnova.backends import get_backend
from agentnova.core.types import ApiMode

# OpenResponses mode (default)
backend = get_backend("ollama", api_mode=ApiMode.RESPONSES)

# Chat-Completions mode
backend = get_backend("ollama", api_mode=ApiMode.COMPLETIONS)
```

Both modes use ReAct prompting - tool definitions are not passed to the API. The model outputs tool calls in text format, which are parsed by the Tool Parser.

---

## OpenResponses Compliance for Small Models

Small models (under 1B parameters) require additional guidance to comply with the OpenResponses agentic loop. The following enhancements ensure reliable tool usage:

### Soul Prompt Structure

The nova-helper soul includes structured sections that guide small models:

1. **Tool Reference Table** - Dynamic injection of available tools with argument examples
2. **Tool Calling Format** - Explicit Action/Action Input format with examples
3. **Calculator Syntax Table** - Maps natural language to Python syntax
4. **After Tool Result** - MANDATORY Final Answer output rules
5. **Error Recovery** - STOP/THINK/TRY pattern with common errors

### Decision Point Guidance

Each decision point in the agentic loop has explicit guidance:

| Decision Point | Guidance |
|----------------|----------|
| Should I use a tool? | Tool Reference table with "When to use" |
| How to format tool call? | Exact format with example |
| What syntax for calculator? | Natural language → Python syntax table |
| What to do after result? | MANDATORY Final Answer, with DO NOT rules |
| What if tool errors? | Error Recovery section with recovery example |

### Observation Enhancement

The agent adds contextual hints to tool results:

```python
# In agent.py - Memory.add() for tool results
if result_str.startswith("Error"):
    observation_msg = f"Observation: {result_str}\n\nNote: Try a different approach..."
else:
    observation_msg = f"Observation: {result_str}\n\nNow output: Final Answer: <the result>"
```

This ensures the model always knows what action to take next, preventing common failure modes:
- Re-calling the tool with the result
- Outputting reasoning instead of Final Answer
- Repeating the same failed expression

---

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
| `--api` | run, chat, agent, test | API mode: `resp` (OpenResponses) or `comp` (Chat-Completions) |
| `--soul` | run, chat, agent | Path to Soul Spec package |
| `--soul-level` | run, chat, agent | Progressive disclosure (1-3) |
| `--num-ctx` | run, chat, agent, test | Context window size (default: 4096) |
| `--timeout` | run, chat, agent, test | Request timeout (seconds) |
| `--debug` | run, chat, agent, test | Enable debug output |

---

## Example: Complete Tool Call Flow

```
User: "What is 15 times 8?"

Step 1: Model generates
────────────────────────
Action: calculator
Action Input: {"expression": "15 * 8"}
Final Answer: 120

Step 2: Parser extracts
────────────────────────
[OpenResponses] Tool calls detected: 1
[OpenResponses] Parsed: name=calculator, args={'expression': '15 * 8'}, final_answer=120

Step 3: Tool executed
─────────────────────
Tool: calculator({'expression': '15 * 8'})
Result: 120

Step 4: Final answer used
─────────────────────────
[OpenResponses] Model provided final_answer with tool call
[OpenResponses] Using final_answer: 120

Result: AgentRun(final_answer="120", tool_calls=1, success=True)
```

### Example: Small Model with Enhanced Observation

Small models (under 1B params) receive additional guidance in the Observation:

```
User: "What is 2 to the power of 10?"

Step 1: Model generates (with correct syntax from soul prompt)
─────────────────────────────────────────────────────────────
Action: calculator
Action Input: {"expression": "2**10"}

Step 2: Tool executed
─────────────────────
Tool: calculator({'expression': '2**10'})
Result: 1024

Step 3: Enhanced Observation added to memory
────────────────────────────────────────────
Observation: 1024

Now output: Final Answer: <the result>

Step 4: Model generates Final Answer
────────────────────────────────────
Final Answer: 1024

Result: AgentRun(final_answer="1024", tool_calls=1, success=True)
```

### Example: Error Recovery

When a tool error occurs, the Observation includes recovery guidance:

```
User: "What is 2 to the power of 10?"

Step 1: Model generates (incorrect syntax)
──────────────────────────────────────────
Action: calculator
Action Input: {"expression": "2 to the power of 10"}

Step 2: Tool error
──────────────────
Tool: calculator({'expression': '2 to the power of 10'})
Result: Error evaluating expression: invalid syntax

Step 3: Enhanced Observation with recovery hint
───────────────────────────────────────────────
Observation: Error evaluating expression: invalid syntax

Note: Try a different approach. For calculator, use Python syntax (e.g., 2**10 for power, sqrt(144) for roots).

Step 4: Model recovers with correct syntax
──────────────────────────────────────────
Action: calculator
Action Input: {"expression": "2**10"}

Step 5: Success
──────────────
Observation: 1024

Now output: Final Answer: <the result>

Final Answer: 1024
```

---

## Configuration

### Default Values

| Setting | Default | Description |
|---------|---------|-------------|
| `num_ctx` | 4096 | Context window size for Ollama |
| `max_steps` | 10 | Maximum reasoning steps |
| `tool_choice` | "auto" | Tool invocation mode |
| `soul_level` | 3 | Soul disclosure level |
| `temperature` | 0.7 | Model temperature (varies by model) |

### Model-Specific Configs

Model configurations are defined in `core/model_config.py`:
- Temperature defaults
- Max token limits
- Stop sequences

Family-specific behavior in `core/model_family_config.py`:
- Thinking mode (disabled for qwen3, deepseek-r1)
- Format preferences

---

## Error Handling

### Tool Not Allowed
```
Tool: read_file
Result: Error: Unknown tool 'read_file'. Available tools: ['get_time', 'get_date']
```

### Tool Execution Error
```
Tool: calculator({})
Result: Error: calculator() missing 1 required positional argument: 'expression'
```

### Max Steps Reached
```
Response status: incomplete
Output: "Maximum steps reached without final answer"
```