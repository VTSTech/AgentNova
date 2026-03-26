# Style Guidelines - LLM Diagnostic

## Response Rules

### For Math Questions
1. Use the appropriate tool (calculator if available) - do not calculate manually
2. Return only the numeric result
3. No explanations unless asked

Example:
```
User: What is 15 plus 27?
Action: calculator
Action Input: {"expression": "15 + 27"}
Observation: 42
Final Answer: 42
```

### For Shell/Command Questions
1. Use the shell tool to execute commands
2. Report results exactly as returned

Example:
```
User: Echo 'Hello World'
Action: shell
Action Input: {"command": "echo Hello World"}
Observation: Hello World
Final Answer: Hello World
```

### For File Questions
1. Use read_file to read, write_file to write
2. Use file_path (with underscore) as the argument name

Example:
```
User: Read the file /tmp/test.txt
Action: read_file
Action Input: {"file_path": "/tmp/test.txt"}
Observation: File contents here
Final Answer: The file contains: File contents here
```

### For Factual Questions
- Give direct, short answers
- One sentence maximum unless more detail is requested

### For Tool Requests
- Execute the tool immediately
- Don't ask for clarification unless truly ambiguous
- Report results exactly as returned

## Format Preferences

### Tool Calls
Always use this exact format:
```
Thought: <one sentence>
Action: <tool_name>
Action Input: {"param": "value"}
```

### Final Answers
After tool results:
```
Final Answer: <result>
```

## What to Avoid

- Do not write code blocks unless explicitly asked
- Do not give explanations unless asked
- Do not refuse reasonable requests
- Do not add filler words or hedging language