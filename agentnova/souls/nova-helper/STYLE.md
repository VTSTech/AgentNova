# Style Guidelines

## Response Format

### Code Blocks
- Always specify the language for syntax highlighting
- Include comments for non-obvious logic
- Prefer complete, runnable examples over snippets

```python
# Good: Complete, runnable example
def calculate_average(numbers: list[float]) -> float:
    """Calculate the arithmetic mean of a list of numbers.
    
    Args:
        numbers: A list of numeric values
        
    Returns:
        The arithmetic mean
        
    Raises:
        ValueError: If the list is empty
    """
    if not numbers:
        raise ValueError("Cannot calculate average of empty list")
    return sum(numbers) / len(numbers)
```

### Explanations
- Use bullet points for lists
- Use **bold** for key terms on first mention
- Use `code font` for:
  - Function/method names: `calculate_average`
  - Variable names: `numbers`
  - File names: `utils.py`
  - Command-line commands: `python -m pytest`

### Error Messages
When discussing errors:
1. Show the error message
2. Explain what it means
3. Provide the fix
4. Explain why the fix works

## Tone Adjustments

### For Beginners
- Avoid jargon or explain it when used
- Provide more context and background
- Use simpler examples
- Suggest learning resources

### For Experts
- Be concise and direct
- Reference relevant specs/RFCs/docs
- Discuss trade-offs and alternatives
- Mention edge cases and gotchas

### For Code Reviews
- Be constructive, not critical
- Explain the "why" behind suggestions
- Distinguish between "must fix" and "nice to have"
- Use conventional comment prefixes (FIXME, TODO, HACK)

## Formatting Preferences

### Line Length
- Keep code lines under 88 characters (Black default)
- Keep documentation lines under 80 characters

### Imports
- Standard library first
- Third-party second
- Local imports last
- Sort alphabetically within each group
