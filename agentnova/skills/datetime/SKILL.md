---
name: datetime
description: Get current date, time, timezone information, and perform date calculations. Use when the user asks about today's date, current time, what day it is, timezones, or date arithmetic. Triggers on phrases like "what is today", "what's the date", "current time", "what day is it", "date now", "time now", "what is the date".
---

# DateTime Skill

Answer date/time questions by calling the `python_repl` tool.

## Quick Reference

| Question | Code |
|----------|------|
| "What is today's date?" | `datetime.now().strftime('Today is %A, %B %d, %Y.')` |
| "What time is it?" | `datetime.now().strftime('The time is %I:%M %p.')` |
| "What day is it?" | `datetime.now().strftime('Today is %A.')` |

## How to Call

```
Tool: python_repl
Argument: {"code": "from datetime import datetime\nprint(datetime.now().strftime('Today is %A, %B %d, %Y.'))"}
```

**Important**: Always include the `code` argument with working Python code.
