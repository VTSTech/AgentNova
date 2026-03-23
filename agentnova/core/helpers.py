"""
⚛️ AgentNova R02.5 — Helpers
Standalone utility functions for the agent system.

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

from __future__ import annotations

import re


def _strip_tool_prefix(result: str) -> str:
    """Strip the 'tool_name → ' prefix added to _successful_results entries."""
    return result.split("→")[-1].strip() if "→" in result else result.strip()


def _extract_calc_expression(prompt: str) -> str | None:
    """
    Extract a calculator expression from a natural language prompt.
    Returns a Python math expression or None if no pattern matches.
    
    Handles:
    - Simple: "What is 15 plus 27?" → "15 + 27"
    - Multi-step: "8 times 7, then subtract 5" → "8 * 7 - 5"
    - Division: "17 divided by 4" → "17 / 4"
    - Power: "X to the power of Y" → "X ** Y"
    - Square root: "square root of X" → "sqrt(X)"
    - Word problems: "sold 8 and 6 from 24" → "24 - 8 - 6"
    """
    q = prompt.strip()
    q_lower = q.lower()
    
    # Op word to symbol mapping
    OP_MAP = {
        'plus': '+', 'add': '+', 'and': '+',
        'minus': '-', 'subtract': '-', 'less': '-',
        'times': '*', 'multiplied': '*', 'multiply': '*',
        'divided': '/', 'divide': '/',
    }
    
    # ---- Multi-step patterns (try first!) ----
    
    # Pattern: "X times Y, then subtract/add Z" or "X times Y then minus Z"
    multi_step = re.search(
        r'(\d+(?:\.\d+)?)\s*(?:times|multiplied?\s*by|\*)\s*(\d+(?:\.\d+)?)[,\s]*(?:then\s+)?(?:subtract|minus|add|plus|plus\s+)?\s*(\d+(?:\.\d+)?)',
        q_lower
    )
    if multi_step:
        nums = multi_step.groups()
        # Determine second operator from context
        if 'subtract' in q_lower or 'minus' in q_lower.split('then')[-1] if 'then' in q_lower else False:
            return f"{nums[0]} * {nums[1]} - {nums[2]}"
        elif 'add' in q_lower or 'plus' in q_lower.split('then')[-1] if 'then' in q_lower else False:
            return f"{nums[0]} * {nums[1]} + {nums[2]}"
        else:
            # Default: look for the word after the second number
            after_second = q_lower[q_lower.find(nums[1])+len(nums[1]):]
            if 'subtract' in after_second or 'minus' in after_second:
                return f"{nums[0]} * {nums[1]} - {nums[2]}"
    
    # Pattern: "X minus Y plus Z" or "X minus Y, then add Z"
    chain_pattern = re.search(
        r'(\d+(?:\.\d+)?)\s*(?:minus|subtract)\s*(\d+(?:\.\d+)?)[,\s]*(?:then\s+)?(?:plus|add)?\s*(\d+(?:\.\d+)?)',
        q_lower
    )
    if chain_pattern:
        nums = chain_pattern.groups()
        return f"{nums[0]} - {nums[1]} + {nums[2]}"
    
    # ---- Explicit math expressions in prompt ----
    
    # Pattern: "compute X minus Y plus Z" (explicit instruction)
    explicit_expr = re.search(
        r'compute\s+(\d+(?:\.\d+)?)\s*(minus|plus|times|divided)\s*(\d+(?:\.\d+)?)(?:\s*(plus|minus|times|divided)\s*(\d+(?:\.\d+)?))?',
        q_lower
    )
    if explicit_expr:
        parts = explicit_expr.groups()
        expr = f"{parts[0]} {OP_MAP.get(parts[1], parts[1])} {parts[2]}"
        if parts[3] and parts[4]:
            expr += f" {OP_MAP.get(parts[3], parts[3])} {parts[4]}"
        return expr
    
    # ---- Word problem patterns ----
    
    # Pattern: "has X ... sell/sold A ... and B" → X - A - B
    word_sold = re.search(
        r'(?:has|had|with)\s*(\d+).*?(?:sell|sold|lost|gave|used|spent)\s*(\d+).*?and\s*(\d+)',
        q_lower
    )
    if word_sold:
        return f"{word_sold.group(1)} - {word_sold.group(2)} - {word_sold.group(3)}"
    
    # Pattern: "left" after numbers suggests subtraction
    if 'left' in q_lower and 'how many' in q_lower:
        numbers = re.findall(r'\d+', q)
        if len(numbers) >= 3:
            # First number is usually the starting amount
            return f"{numbers[0]} - {numbers[1]} - {numbers[2]}"
    
    # ---- Time/duration patterns ----
    
    # Pattern: "opens at X and closes at Y" → (Y - X) mod 12 or Y - X + 12 if Y < X
    time_pattern = re.search(
        r'(?:opens?|starts?)\s*(?:at\s+)?(\d+)(?:\s*(?:am|pm))?[^.]+(?:closes?|ends?)\s*(?:at\s+)?(\d+)(?:\s*(?:am|pm))?',
        q_lower
    )
    if time_pattern:
        start = int(time_pattern.group(1))
        end = int(time_pattern.group(2))
        if end <= start:
            # PM to PM or AM to PM crossing
            return f"{end} - {start} + 12"
        else:
            return f"{end} - {start}"
    
    # ---- Single operations (fallback) ----
    
    # Pattern: "square root of X" or "sqrt of X"
    sqrt_match = re.search(r'square\s*root\s*of\s*(\d+(?:\.\d+)?)', q_lower)
    if not sqrt_match:
        sqrt_match = re.search(r'sqrt\s*of\s*(\d+(?:\.\d+)?)', q_lower)
    if sqrt_match:
        return f"sqrt({sqrt_match.group(1)})"
    
    # Pattern: "X to the power of Y" or "X raised to Y"
    power_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:to\s*the\s*power\s*of|raised\s*to|to\s*the\s*\d*(?:th|st|nd|rd)?\s*power|\*\*|\^)\s*(\d+(?:\.\d+)?)', q_lower)
    if power_match:
        return f"{power_match.group(1)} ** {power_match.group(2)}"
    
    # Pattern: "(X + Y) times Z" - complex expression with parentheses
    complex_times = re.search(r'\(([^)]+)\)\s*(?:times|multiplied\s*by|\*)\s*(\d+(?:\.\d+)?)', q_lower)
    if complex_times:
        inner = complex_times.group(1).replace('plus', '+').replace('minus', '-').replace(' ', ' ')
        inner = re.sub(r'\s+', '', inner)
        return f"({inner}) * {complex_times.group(2)}"
    
    # Pattern: "X times Y" or "X multiplied by Y"
    times_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:times|multiplied\s*by|\*)\s*(\d+(?:\.\d+)?)', q_lower)
    if times_match:
        return f"{times_match.group(1)} * {times_match.group(2)}"
    
    # Pattern: "X divided by Y"
    div_match = re.search(r'(\d+(?:\.\d+)?)\s*divided\s*by\s*(\d+(?:\.\d+)?)', q_lower)
    if div_match:
        return f"{div_match.group(1)} / {div_match.group(2)}"
    
    # Pattern: "X plus Y" or "X minus Y"
    plus_match = re.search(r'(\d+(?:\.\d+)?)\s*plus\s*(\d+(?:\.\d+)?)', q_lower)
    if plus_match:
        return f"{plus_match.group(1)} + {plus_match.group(2)}"
    
    minus_match = re.search(r'(\d+(?:\.\d+)?)\s*minus\s*(\d+(?:\.\d+)?)', q_lower)
    if minus_match:
        return f"{minus_match.group(1)} - {minus_match.group(2)}"
    
    return None


def _extract_echo_text(prompt: str) -> str | None:
    """
    Extract text to echo from a prompt like "Echo the text 'Hello'" or "Print Hello World".
    Returns the text to echo or None.
    """
    q = prompt.strip()
    
    # Pattern: echo 'text' or echo "text" or echo text
    quoted_match = re.search(r"echo\s*['\"]([^'\"]+)['\"]", q, re.IGNORECASE)
    if quoted_match:
        return quoted_match.group(1)
    
    # Pattern: "echo the text 'X'" or "echo text 'X'"
    text_match = re.search(r"echo\s*(?:the\s*)?text\s*['\"]([^'\"]+)['\"]", q, re.IGNORECASE)
    if text_match:
        return text_match.group(1)
    
    # Pattern: "print 'X'" or "print X"
    print_match = re.search(r"print\s*['\"]?([^'\"]+)['\"]?", q, re.IGNORECASE)
    if print_match:
        return print_match.group(1).strip()
    
    # Pattern: "echo X" at end of prompt
    echo_match = re.search(r"echo\s+['\"]?([^'\"]+)['\"]?$", q, re.IGNORECASE)
    if echo_match:
        text = echo_match.group(1).strip()
        if not text.startswith('-'):
            return text
    
    return None


def _is_simple_answered_query(user_input: str, successful_results: list[str]) -> bool:
    """
    Return True when a single successful tool result is sufficient to answer
    the user's question and the agent should synthesize immediately.

    Targets the most common small-model looping patterns:
      - Date/time queries ("what is the date", "what time is it")
      - Simple arithmetic ("what is 2+2", "sqrt of 144")
      - Single-file reads ("show me file.py")
      - Single directory listings

    Deliberately conservative — returns False for anything that might
    genuinely need multiple tool calls (multi-step tasks, comparisons, etc.)
    """
    if not successful_results:
        return False

    lower = user_input.lower().strip()

    # Date/time patterns
    date_time_keywords = [
        "date", "time", "day", "today", "now", "current date",
        "what day", "what time", "year", "month",
    ]
    if any(kw in lower for kw in date_time_keywords):
        return True

    # Simple arithmetic / single calculation
    math_keywords = ["what is", "calculate", "compute", "sqrt", "square root",
                     "result of", "value of", "evaluate"]
    math_ops = ["+", "-", "*", "/", "^", "**", "%"]
    if any(kw in lower for kw in math_keywords) and len(lower) < 60:
        return True
    if sum(1 for op in math_ops if op in lower) >= 1 and len(lower) < 40:
        return True

    # Single file read / single dir listing
    single_file_keywords = ["read", "show", "display", "print", "list", "ls"]
    if any(kw in lower for kw in single_file_keywords) and len(lower.split()) <= 6:
        return True

    return False


def _is_greeting_or_simple(text: str) -> bool:
    """
    Check if the user input is a simple greeting or short message
    that shouldn't require tool usage.
    """
    lower = text.lower().strip()
    greetings = [
        "hi", "hello", "hey", "hola", "howdy", "greetings",
        "good morning", "good afternoon", "good evening",
        "what's up", "whats up", "sup", "yo",
        "thanks", "thank you", "ok", "okay", "yes", "no", "sure",
        "bye", "goodbye", "see you", "cya",
    ]
    
    # Check for exact match or greeting at start
    if lower in greetings:
        return True
    for g in greetings:
        if lower.startswith(g + " "):
            return True
    
    # Very short messages (< 10 chars) are likely simple
    if len(lower) < 10 and not any(c in lower for c in "0123456789+-*/=><"):
        return True
    
    return False


def _is_small_model(model: str) -> bool:
    """
    Heuristic to detect if a model is small (< 2B parameters).
    Small models benefit from few-shot prompting.
    """
    model_lower = model.lower()
    
    # Check for size indicators in model name
    small_indicators = [
        ":0.5b", ":0.6b", ":1b", ":1.5b", ":1.8b",
        "0.5b", "0.6b", "1b", "1.5b",
        "270m", "135m", "350m", "500m", "800m",
        "tiny", "mini", "micro", "small"
    ]
    
    for indicator in small_indicators:
        if indicator in model_lower:
            return True
    
    # Check parameter count after common model names
    param_match = re.search(r'(\d+(?:\.\d+)?)[bm]', model_lower)
    if param_match:
        size_str = param_match.group(1)
        try:
            size = float(size_str)
            if 'm' in model_lower[param_match.end()-1:param_match.end()]:
                return True  # Any million-parameter model is small
            if size < 2:
                return True  # Less than 2 billion
        except ValueError:
            pass
    
    return False


# Repetition detection pattern - catches "Final Answer: X" repeated multiple times
_REPETITION_RE = re.compile(r'(Final Answer:\s*[^\n]+)(\s*\1){2,}', re.IGNORECASE)


def _detect_and_fix_repetition(text: str) -> str:
    """
    Detect and fix repetitive output from small models.
    
    Some models (like qwen3:0.6b) get stuck in loops repeating the same phrase:
        "Final Answer: 120\nFinal Answer: 120\nFinal Answer: 120..."
    
    This function detects such patterns and returns the text with only one instance.
    Also handles general repetition of any phrase 3+ times.
    """
    if not text:
        return text
    
    # Fix "Final Answer:" repetition specifically
    match = _REPETITION_RE.search(text)
    if match:
        text = _REPETITION_RE.sub(r'\1', text)
    
    # Also detect and fix any line repeated 3+ times at the end
    lines = text.split('\n')
    if len(lines) >= 3:
        last_line = lines[-1].strip()
        if last_line:
            repeat_count = 1
            for i in range(len(lines) - 2, -1, -1):
                if lines[i].strip() == last_line:
                    repeat_count += 1
                else:
                    break
            
            if repeat_count >= 3:
                text = '\n'.join(lines[:-repeat_count + 1])
    
    return text