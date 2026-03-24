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