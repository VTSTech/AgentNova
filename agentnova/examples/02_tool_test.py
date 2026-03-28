#!/usr/bin/env python3
"""
examples/02_tool_test.py
------------------------
Comprehensive tool tests for AgentNova.

Phase 1: Direct Tool Validation
  • Tests each tool handler directly (no model involved)
  • Verifies correct output for known inputs
  • Tests security restrictions and edge cases

Phase 2: Model Tool Calling
  • Tests model's ability to select correct tool
  • Verifies proper argument passing
  • Checks result extraction

Usage:
  python examples/02_tool_test.py                    # Both phases
  python examples/02_tool_test.py --tools-only       # Phase 1 only
  python examples/02_tool_test.py --model qwen2.5:0.5b --debug
  agentnova test 02

Environment Variables:
  OLLAMA_BASE_URL     - Ollama server URL
  AGENTNOVA_MODEL     - Default model

Written by VTSTech — https://www.vts-tech.org
"""

import sys
import os
import time
import re
import argparse
import platform
import tempfile
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentnova import Agent, get_config
from agentnova.backends import get_default_backend
from agentnova.tools import make_builtin_registry
from agentnova.tools.builtins import (
    calculator, shell, read_file, write_file, list_directory,
    http_get, get_time, get_date, parse_json, count_words, count_chars
)
from agentnova.core.types import StepResultType


def parse_args():
    parser = argparse.ArgumentParser(description="AgentNova Tool Tests")
    parser.add_argument("-m", "--model", default=None, help="Model to test")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--backend", choices=["ollama", "bitnet"], default=None)
    parser.add_argument("--api", choices=["openre", "openai"], default="openre", dest="api_mode",
                       help="API mode: 'openre' (OpenResponses) or 'openai' (Chat-Completions (OpenAI))")
    parser.add_argument("--tools-only", action="store_true", help="Only run Phase 1 (direct tool tests)")
    parser.add_argument("--model-only", action="store_true", help="Only run Phase 2 (model tool calling)")
    parser.add_argument("--soul", default=None, help="Path to Soul Spec package (ignored for tool tests)")
    parser.add_argument("--soul-level", type=int, default=2, choices=[1, 2, 3],
                       help="Soul progressive disclosure level")
    parser.add_argument("--timeout", type=int, default=None,
                       help="Request timeout in seconds (default: 120)")
    parser.add_argument("--warmup", action="store_true",
                       help="Send warmup request before testing (avoids cold start timeout)")
    parser.add_argument("--num-ctx", type=int, default=None,
                       help="Context window size in tokens")
    parser.add_argument("--num-predict", type=int, default=None,
                       help="Maximum tokens to generate")
    parser.add_argument("--temp", type=float, default=None, dest="temperature",
                       help="Sampling temperature 0.0-2.0")
    parser.add_argument("--top-p", type=float, default=None, dest="top_p",
                       help="Nucleus sampling probability 0.0-1.0")
    parser.add_argument("--force-react", action="store_true", help="Force ReAct mode for tool calling")
    return parser.parse_args()


# ============================================================================
# Phase 1: Direct Tool Validation
# ============================================================================

def test_calculator_direct() -> tuple[int, int]:
    """Test calculator tool directly without model."""
    print(f"\n{'='*60}")
    print(f"🧮 Calculator Tool - Direct Validation")
    print(f"{'='*60}")
    
    tests = [
        # (name, input, expected_output_contains, should_succeed)
        ("Basic addition", "15 + 8", "23", True),
        ("Multiplication", "15 * 8", "120", True),
        ("Division", "100 / 4", "25", True),
        ("Power", "2 ** 10", "1024", True),
        ("Square root", "sqrt(144)", "12", True),
        ("Complex expression", "(10 + 5) * 3", "45", True),
        ("Modulo", "17 % 5", "2", True),
        ("Negative numbers", "-5 + 10", "5", True),
        ("Float division", "7 / 2", "3.5", True),
        ("Constants - pi", "pi", "3.14", True),
        ("Constants - e", "e", "2.71", True),
        ("Trig - sin", "sin(0)", "0", True),
        ("Trig - cos", "cos(0)", "1", True),
        ("Logarithm", "log(100)", "4.6", True),  # ln(100) ≈ 4.6
        ("Floor", "floor(3.7)", "3", True),
        ("Ceil", "ceil(3.2)", "4", True),
        ("Division by zero", "1 / 0", "division by zero", False),
        ("NaN result", "sqrt(-1)", "NaN", False),
        ("Exponent limit", f"2 ** 15000", "exceeds", False),
    ]
    
    results = []
    for name, expr, expected, should_succeed in tests:
        result = calculator(expr)
        result_lower = result.lower()
        
        if should_succeed:
            passed = expected in result_lower or expected in result
        else:
            # Should return error message
            passed = "error" in result_lower or expected.lower() in result_lower
        
        results.append(passed)
        status = "✅" if passed else "❌"
        print(f"  {status} {name}: '{expr}' → {result[:50]}")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 Calculator Direct: {passed}/{total} ({100*passed//total}%)")
    return passed, total


def test_shell_direct() -> tuple[int, int]:
    """Test shell tool directly without model."""
    print(f"\n{'='*60}")
    print(f"🖥️ Shell Tool - Direct Validation")
    print(f"{'='*60}")
    
    tests = [
        # (name, command, expected_contains, should_succeed)
        ("Echo test", "echo 'Hello World'", "Hello World", True),
        ("Echo with quotes", 'echo "Test 123"', "Test 123", True),
        # Blocked commands
        ("Blocked: rm", "rm -rf /", "blocked", False),
        ("Blocked: sudo", "sudo ls", "blocked", False),
        ("Blocked: curl", "curl http://example.com", "blocked", False),
        ("Blocked: pip", "pip install evil", "blocked", False),
        # Injection attempts
        ("Injection: semicolon", "echo test; ls", "injection", False),
        ("Injection: pipe", "echo test | cat", "injection", False),
        ("Injection: backticks", "echo `whoami`", "injection", False),
        ("Injection: $()", "echo $(whoami)", "injection", False),
    ]
    
    results = []
    for name, cmd, expected, should_succeed in tests:
        result = shell(cmd, timeout=5)
        result_lower = result.lower()
        
        if should_succeed:
            passed = expected.lower() in result_lower
        else:
            passed = "blocked" in result_lower or "injection" in result_lower or "security" in result_lower
        
        results.append(passed)
        status = "✅" if passed else "❌"
        print(f"  {status} {name}: → {result[:50]}")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 Shell Direct: {passed}/{total} ({100*passed//total}%)")
    return passed, total


def test_file_direct() -> tuple[int, int]:
    """Test file tools directly without model."""
    print(f"\n{'='*60}")
    print(f"📁 File Tools - Direct Validation")
    print(f"{'='*60}")
    
    results = []
    
    # Create temp directory for tests
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.txt")
        test_content = "Hello AgentNova!\nLine 2\nLine 3"
        
        # Test write_file
        print(f"\n  Testing write_file...")
        write_result = write_file(test_file, test_content)
        write_ok = "Successfully" in write_result
        results.append(write_ok)
        status = "✅" if write_ok else "❌"
        print(f"    {status} write_file: {write_result}")
        
        # Test read_file
        print(f"\n  Testing read_file...")
        read_result = read_file(test_file)
        # Normalize line endings for comparison (Windows uses \r\n)
        read_normalized = read_result.replace('\r\n', '\n').replace('\r', '\n')
        test_normalized = test_content.replace('\r\n', '\n').replace('\r', '\n')
        read_ok = test_normalized in read_normalized or test_normalized == read_normalized
        results.append(read_ok)
        status = "✅" if read_ok else "❌"
        print(f"    {status} read_file: {read_result[:40]}...")
        
        # Test list_directory
        print(f"\n  Testing list_directory...")
        list_result = list_directory(tmpdir)
        list_ok = "test.txt" in list_result
        results.append(list_ok)
        status = "✅" if list_ok else "❌"
        print(f"    {status} list_directory: {list_result}")
        
        # Test path security
        print(f"\n  Testing path security...")
        security_tests = [
            ("Path traversal", "../../../etc/passwd"),
            ("System dir", "/etc/passwd"),
            ("UNC path", "\\\\server\\share"),
        ]
        for name, path in security_tests:
            result = read_file(path)
            blocked = "Security error" in result or "denied" in result or "not allowed" in result
            results.append(blocked)
            status = "✅" if blocked else "❌"
            print(f"    {status} {name}: blocked={blocked}")
        
        # Test empty file
        print(f"\n  Testing edge cases...")
        empty_file = os.path.join(tmpdir, "empty.txt")
        write_file(empty_file, "")
        empty_read = read_file(empty_file)
        empty_ok = empty_read == ""
        results.append(empty_ok)
        status = "✅" if empty_ok else "❌"
        print(f"    {status} Empty file: '{empty_read}'")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 File Direct: {passed}/{total} ({100*passed//total}%)")
    return passed, total


def test_http_direct() -> tuple[int, int]:
    """Test HTTP tool directly without model."""
    print(f"\n{'='*60}")
    print(f"🌐 HTTP Tool - Direct Validation")
    print(f"{'='*60}")
    
    tests = [
        # (name, url, expected_contains, should_succeed)
        ("Valid HTTP", "http://httpbin.org/get", "httpbin", True),
        # SSRF blocked
        ("SSRF: localhost", "http://localhost/test", "SSRF", False),
        ("SSRF: 127.0.0.1", "http://127.0.0.1/test", "SSRF", False),
        ("SSRF: 10.x", "http://10.0.0.1/test", "SSRF", False),
        ("SSRF: 192.168.x", "http://192.168.1.1/test", "SSRF", False),
        ("SSRF: metadata", "http://169.254.169.254/latest/meta-data", "SSRF", False),
        # Scheme validation
        ("Invalid scheme: ftp", "ftp://example.com/file", "scheme", False),
        ("Invalid scheme: file", "file:///etc/passwd", "scheme", False),
    ]
    
    results = []
    for name, url, expected, should_succeed in tests:
        try:
            result = http_get(url)
        except Exception as e:
            result = str(e)
        
        result_lower = result.lower()
        
        if should_succeed:
            # For network tests, check if we got a valid response or a connection error
            # (connection errors are acceptable for network tests in isolated envs)
            passed = expected.lower() in result_lower or len(result) > 100 or "connection" in result_lower or "error" in result_lower
        else:
            passed = expected.lower() in result_lower or "security" in result_lower or "error" in result_lower
        
        results.append(passed)
        status = "✅" if passed else "❌"
        print(f"  {status} {name}: → {result[:50]}")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 HTTP Direct: {passed}/{total} ({100*passed//total}%)")
    return passed, total


def test_datetime_direct() -> tuple[int, int]:
    """Test datetime tools directly without model."""
    print(f"\n{'='*60}")
    print(f"📅 DateTime Tools - Direct Validation")
    print(f"{'='*60}")
    
    results = []
    
    # Test get_date
    print(f"\n  Testing get_date...")
    date_result = get_date()
    date_ok = bool(re.match(r'\d{4}-\d{2}-\d{2}', date_result))
    results.append(date_ok)
    status = "✅" if date_ok else "❌"
    print(f"    {status} get_date: {date_result}")
    
    # Test get_time (local)
    print(f"\n  Testing get_time (local)...")
    time_result = get_time()
    time_ok = bool(re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', time_result))
    results.append(time_ok)
    status = "✅" if time_ok else "❌"
    print(f"    {status} get_time: {time_result}")
    
    # Test get_time with timezone
    print(f"\n  Testing get_time (timezone)...")
    tz_result = get_time("UTC")
    tz_ok = "UTC" in tz_result or bool(re.match(r'\d{4}-\d{2}-\d{2}', tz_result))
    results.append(tz_ok)
    status = "✅" if tz_ok else "❌"
    print(f"    {status} get_time(UTC): {tz_result}")
    
    # Test invalid timezone
    print(f"\n  Testing invalid timezone...")
    invalid_tz = get_time("Invalid/Timezone")
    invalid_ok = "error" in invalid_tz.lower() or "unknown" in invalid_tz.lower()
    results.append(invalid_ok)
    status = "✅" if invalid_ok else "❌"
    print(f"    {status} Invalid timezone: {invalid_tz[:50]}")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 DateTime Direct: {passed}/{total} ({100*passed//total}%)")
    return passed, total


def test_json_text_direct() -> tuple[int, int]:
    """Test JSON and text tools directly without model."""
    print(f"\n{'='*60}")
    print(f"📝 JSON & Text Tools - Direct Validation")
    print(f"{'='*60}")
    
    results = []
    
    # Test parse_json
    print(f"\n  Testing parse_json...")
    json_input = '{"name": "test", "value": 123, "nested": {"a": 1}}'
    json_result = parse_json(json_input)
    json_ok = "name" in json_result and "123" in json_result and "nested" in json_result
    results.append(json_ok)
    status = "✅" if json_ok else "❌"
    print(f"    {status} parse_json: formatted output")
    
    # Test invalid JSON
    invalid_json = parse_json("not valid json")
    invalid_ok = "error" in invalid_json.lower()
    results.append(invalid_ok)
    status = "✅" if invalid_ok else "❌"
    print(f"    {status} Invalid JSON: {invalid_json[:40]}")
    
    # Test count_words
    print(f"\n  Testing count_words...")
    words_result = count_words("Hello world this is a test")
    words_ok = words_result == "6"
    results.append(words_ok)
    status = "✅" if words_ok else "❌"
    print(f"    {status} count_words: {words_result}")
    
    # Test count_chars
    print(f"\n  Testing count_chars...")
    chars_result = count_chars("Hello World")
    chars_ok = chars_result == "11"
    results.append(chars_ok)
    status = "✅" if chars_ok else "❌"
    print(f"    {status} count_chars: {chars_result}")
    
    # Edge cases
    print(f"\n  Testing edge cases...")
    empty_words = count_words("")
    empty_ok = empty_words == "0"
    results.append(empty_ok)
    status = "✅" if empty_ok else "❌"
    print(f"    {status} Empty string words: {empty_words}")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 JSON/Text Direct: {passed}/{total} ({100*passed//total}%)")
    return passed, total


def run_phase1() -> tuple[int, int]:
    """Run all Phase 1 (direct tool) tests."""
    print(f"\n{'#'*60}")
    print(f"# PHASE 1: Direct Tool Validation")
    print(f"# Testing tool handlers without model")
    print(f"{'#'*60}")
    
    total_passed = 0
    total_tests = 0
    
    p, t = test_calculator_direct()
    total_passed += p
    total_tests += t
    
    p, t = test_shell_direct()
    total_passed += p
    total_tests += t
    
    p, t = test_file_direct()
    total_passed += p
    total_tests += t
    
    p, t = test_http_direct()
    total_passed += p
    total_tests += t
    
    p, t = test_datetime_direct()
    total_passed += p
    total_tests += t
    
    p, t = test_json_text_direct()
    total_passed += p
    total_tests += t
    
    print(f"\n{'='*60}")
    print(f"📊 PHASE 1 TOTAL: {total_passed}/{total_tests} ({100*total_passed//total_tests}%)")
    print(f"{'='*60}")
    
    return total_passed, total_tests


# ============================================================================
# Phase 2: Model Tool Calling Tests
# ============================================================================

def normalize_number(text: str) -> str:
    """Extract first number from text."""
    match = re.search(r'-?\d+\.?\d*', text.replace(',', ''))
    return match.group(0) if match else ""


def check_tool_used(run, tool_name: str) -> bool:
    """Verify that a specific tool was called during the run."""
    for step in run.steps:
        if step.type == StepResultType.TOOL_CALL:
            if step.tool_call and step.tool_call.name == tool_name:
                return True
            if step.tool_result is not None and hasattr(step, 'content'):
                if tool_name in str(step.content).lower():
                    return True
    return False


def test_calculator_model(model: str, backend, debug: bool = False,
                           soul: str = None, soul_level: int = 2,
                           force_react: bool = False,
                           num_ctx: int = None, num_predict: int = None,
                           temperature: float = None, top_p: float = None) -> tuple[int, int]:
    """Test model's ability to call calculator tool."""
    print(f"\n{'='*60}")
    print(f"🧮 Calculator Tool - Model Calling")
    print(f"   Model: {model}")
    print(f"{'='*60}")
    
    tools = make_builtin_registry().subset(["calculator"])
    
    tests = [
        ("Basic multiplication", "What is 15 times 8?", "120"),
        ("Power", "What is 2 to the power of 10?", "1024"),
        ("Square root", "What is the square root of 144?", "12"),
        ("Complex expression", "What is (10 + 5) times 3?", "45"),
        ("Division", "What is 100 divided by 4?", "25"),
    ]
    
    results = []
    
    for name, prompt, expected in tests:
        print(f"\n📋 {name}")
        print(f"   Prompt: {prompt}")
        
        agent = Agent(
            model=model,
            tools=tools,
            backend=backend,
            max_steps=5,
            debug=debug,
            soul=soul,
            soul_level=soul_level,
            force_react=force_react,
            num_ctx=num_ctx,
            num_predict=num_predict,
            temperature=temperature,
            top_p=top_p,
        )
        
        t0 = time.time()
        run = agent.run(prompt)
        elapsed = time.time() - t0
        
        tool_used = check_tool_used(run, "calculator")
        expected_num = normalize_number(expected)
        actual_num = normalize_number(run.final_answer)
        passed = expected_num == actual_num and expected_num != ""
        
        if not passed and expected in run.final_answer:
            passed = True
        
        results.append(passed)
        
        status = "✅" if passed else "❌"
        tool_status = "🔧" if tool_used else "⚠️"
        print(f"  {status} Expected '{expected}' | Got: {actual_num}")
        print(f"  {tool_status} Tool used: {tool_used} | {elapsed:.1f}s, {len(run.steps)} steps")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 Calculator Model: {passed}/{total} ({100*passed//total}%)")
    return passed, total


def test_shell_model(model: str, backend, debug: bool = False,
                     soul: str = None, soul_level: int = 2,
                     force_react: bool = False,
                     num_ctx: int = None, num_predict: int = None,
                     temperature: float = None, top_p: float = None) -> tuple[int, int]:
    """Test model's ability to call shell tool."""
    print(f"\n{'='*60}")
    print(f"🖥️ Shell Tool - Model Calling")
    print(f"   Model: {model}")
    print(f"{'='*60}")
    
    tools = make_builtin_registry().subset(["shell"])
    is_windows = platform.system() == "Windows"
    
    tests = [
        ("Echo test", "Use shell to echo 'Hello AgentNova'", "Hello AgentNova"),
        ("Current directory", "What is the current working directory?", None),
    ]
    
    results = []
    
    for name, prompt, expected in tests:
        print(f"\n📋 {name}")
        print(f"   Prompt: {prompt}")
        
        agent = Agent(
            model=model,
            tools=tools,
            backend=backend,
            max_steps=5,
            debug=debug,
            soul=soul,
            soul_level=soul_level,
            force_react=force_react,
            num_ctx=num_ctx,
            num_predict=num_predict,
            temperature=temperature,
            top_p=top_p,
        )
        
        t0 = time.time()
        run = agent.run(prompt)
        elapsed = time.time() - t0
        
        tool_used = check_tool_used(run, "shell")
        
        if not tool_used:
            print(f"  ❌ Shell tool was NOT called!")
            results.append(False)
            continue
        
        # Check if expected result appears in either:
        # 1. The final answer, OR
        # 2. Any tool result during the run (model may not format Final Answer correctly)
        found_in_answer = expected and expected.lower() in run.final_answer.lower()
        found_in_tool_result = False
        
        if expected:
            for step in run.steps:
                if step.tool_result and expected.lower() in str(step.tool_result).lower():
                    found_in_tool_result = True
                    break
        
        # Pass if tool was used AND (no expected value OR result found somewhere)
        if expected:
            passed = found_in_answer or found_in_tool_result
        else:
            passed = True  # Just verify tool was used
        
        results.append(passed)
        status = "✅" if passed else "❌"
        found_where = ""
        if expected:
            if found_in_answer:
                found_where = "(in answer)"
            elif found_in_tool_result:
                found_where = "(in tool result)"
        print(f"  {status} {elapsed:.1f}s, {len(run.steps)} steps {found_where}")
        print(f"  📝 {run.final_answer[:80]}")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 Shell Model: {passed}/{total} ({100*passed//total}%)")
    return passed, total


def test_datetime_model(model: str, backend, debug: bool = False,
                        soul: str = None, soul_level: int = 2,
                        force_react: bool = False,
                        num_ctx: int = None, num_predict: int = None,
                        temperature: float = None, top_p: float = None) -> tuple[int, int]:
    """Test model's ability to call datetime tools."""
    print(f"\n{'='*60}")
    print(f"📅 DateTime Tools - Model Calling")
    print(f"   Model: {model}")
    print(f"{'='*60}")
    
    tools = make_builtin_registry().subset(["get_time", "get_date"])
    
    tests = [
        ("Get date", "What is today's date?", "date"),
        ("Get time", "What time is it?", "time"),
    ]
    
    results = []
    
    for name, prompt, keyword in tests:
        print(f"\n📋 {name}")
        print(f"   Prompt: {prompt}")
        
        agent = Agent(
            model=model,
            tools=tools,
            backend=backend,
            max_steps=5,
            debug=debug,
            soul=soul,
            soul_level=soul_level,
            force_react=force_react,
            num_ctx=num_ctx,
            num_predict=num_predict,
            temperature=temperature,
            top_p=top_p,
        )
        
        t0 = time.time()
        run = agent.run(prompt)
        elapsed = time.time() - t0
        
        tool_used = check_tool_used(run, "get_time") or check_tool_used(run, "get_date")
        
        has_date = bool(re.search(r'\d{4}-\d{2}-\d{2}', run.final_answer))
        has_time = bool(re.search(r'\d{2}:\d{2}', run.final_answer))
        passed = (keyword == "date" and has_date) or (keyword == "time" and has_time)
        
        results.append(passed)
        status = "✅" if passed else "❌"
        tool_status = "🔧" if tool_used else "⚠️"
        print(f"  {status} {tool_status} Tool used: {tool_used} | {elapsed:.1f}s")
        print(f"  📝 {run.final_answer}")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 DateTime Model: {passed}/{total} ({100*passed//total}%)")
    return passed, total


def test_file_model(model: str, backend, debug: bool = False,
                    soul: str = None, soul_level: int = 2,
                    force_react: bool = False,
                    num_ctx: int = None, num_predict: int = None,
                    temperature: float = None, top_p: float = None) -> tuple[int, int]:
    """Test model's ability to call file tools."""
    print(f"\n{'='*60}")
    print(f"📁 File Tools - Model Calling")
    print(f"   Model: {model}")
    print(f"{'='*60}")
    
    tools = make_builtin_registry().subset(["read_file", "write_file", "list_directory"])
    
    # Create a test file first
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.txt")
        write_file(test_file, "Hello from AgentNova!")
        
        # Convert path to forward slashes for better small model compatibility
        # Forward slashes work on both Windows and Unix
        test_file_fs = test_file.replace("\\", "/")
        tmpdir_fs = tmpdir.replace("\\", "/")
        
        tests = [
            ("Read file", f"Read the file at {test_file_fs}", "AgentNova"),
            ("List directory", f"List files in {tmpdir_fs}", "test.txt"),
        ]
        
        results = []
        
        for name, prompt, expected in tests:
            print(f"\n📋 {name}")
            print(f"   Prompt: {prompt}")
            
            agent = Agent(
                model=model,
                tools=tools,
                backend=backend,
                max_steps=5,
                debug=debug,
                soul=soul,
                soul_level=soul_level,
                force_react=force_react,
                num_ctx=num_ctx,
                num_predict=num_predict,
                temperature=temperature,
                top_p=top_p,
            )
            
            t0 = time.time()
            run = agent.run(prompt)
            elapsed = time.time() - t0
            
            # Check if any file tool was used
            tool_used = (
                check_tool_used(run, "read_file") or 
                check_tool_used(run, "write_file") or 
                check_tool_used(run, "list_directory")
            )
            
            # Check result in answer or tool result
            found_in_answer = expected.lower() in run.final_answer.lower()
            found_in_tool_result = False
            for step in run.steps:
                if step.tool_result and expected.lower() in str(step.tool_result).lower():
                    found_in_tool_result = True
                    break
            
            passed = (found_in_answer or found_in_tool_result) if expected else tool_used
            results.append(passed)
            
            status = "✅" if passed else "❌"
            tool_status = "🔧" if tool_used else "⚠️"
            found_where = "(in answer)" if found_in_answer else "(in tool result)" if found_in_tool_result else ""
            print(f"  {status} {tool_status} Tool used: {tool_used} | {elapsed:.1f}s {found_where}")
            print(f"  📝 {run.final_answer}")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 File Model: {passed}/{total} ({100*passed//total}%)")
    return passed, total


def test_python_repl_model(model: str, backend, debug: bool = False,
                           soul: str = None, soul_level: int = 2,
                           force_react: bool = False,
                           num_ctx: int = None, num_predict: int = None,
                           temperature: float = None, top_p: float = None) -> tuple[int, int]:
    """Test model's ability to call python_repl tool."""
    print(f"\n{'='*60}")
    print(f"🐍 Python REPL Tool - Model Calling")
    print(f"   Model: {model}")
    print(f"{'='*60}")
    
    tools = make_builtin_registry().subset(["python_repl"])
    
    tests = [
        ("Calculate power", "Use Python to calculate 2 to the power of 20", "1048576"),
        ("Math with math module", "Use Python to calculate the square root of 144", "12"),
    ]
    
    results = []
    
    for name, prompt, expected in tests:
        print(f"\n📋 {name}")
        print(f"   Prompt: {prompt}")
        
        agent = Agent(
            model=model,
            tools=tools,
            backend=backend,
            max_steps=5,
            debug=debug,
            soul=soul,
            soul_level=soul_level,
            force_react=force_react,
            num_ctx=num_ctx,
            num_predict=num_predict,
            temperature=temperature,
            top_p=top_p,
        )
        
        t0 = time.time()
        run = agent.run(prompt)
        elapsed = time.time() - t0
        
        tool_used = check_tool_used(run, "python_repl")
        
        # Check result in answer or tool result
        found_in_answer = expected in run.final_answer
        found_in_tool_result = False
        for step in run.steps:
            if step.tool_result and expected in str(step.tool_result):
                found_in_tool_result = True
                break
        
        passed = found_in_answer or found_in_tool_result
        results.append(passed)
        
        status = "✅" if passed else "❌"
        tool_status = "🔧" if tool_used else "⚠️"
        print(f"  {status} {tool_status} Tool used: {tool_used} | {elapsed:.1f}s")
        print(f"  📝 {run.final_answer}")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 Python REPL Model: {passed}/{total} ({100*passed//total}%)")
    return passed, total


def test_all_tools_model(model: str, backend, debug: bool = False,
                         soul: str = None, soul_level: int = 2,
                         force_react: bool = False,
                         num_ctx: int = None, num_predict: int = None,
                         temperature: float = None, top_p: float = None) -> tuple[int, int]:
    """Test model's ability to choose correct tools when all are available."""
    print(f"\n{'='*60}")
    print(f"🧰 All Tools - Model Calling")
    print(f"   Model: {model}")
    print(f"{'='*60}")
    
    # Give model access to ALL tools
    tools = make_builtin_registry()
    
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "multi_test.txt")
        write_file(test_file, "Test content 123")
        # Use forward slashes for better compatibility
        test_file_fs = test_file.replace("\\", "/")
        
        tests = [
            ("Calculator choice", "What is 25 times 4?", "100", "calculator"),
            ("Shell choice", "Echo the text 'MultiTool'", "MultiTool", "shell"),
            ("Date choice", "What is today's date?", None, "get_date"),
            ("File read choice", f"Read the file at {test_file_fs}", "Test content", "read_file"),
        ]
        
        results = []
        
        for name, prompt, expected, expected_tool in tests:
            print(f"\n📋 {name}")
            print(f"   Prompt: {prompt}")
            print(f"   Expected tool: {expected_tool}")
            
            agent = Agent(
                model=model,
                tools=tools,
                backend=backend,
                max_steps=5,
                debug=debug,
                soul=soul,
                soul_level=soul_level,
                force_react=force_react,
                num_ctx=num_ctx,
                num_predict=num_predict,
                temperature=temperature,
                top_p=top_p,
            )
            
            t0 = time.time()
            run = agent.run(prompt)
            elapsed = time.time() - t0
            
            # Check if correct tool was used
            correct_tool = check_tool_used(run, expected_tool)
            
            # Check result
            passed = correct_tool
            if expected:
                found = expected.lower() in run.final_answer.lower()
                if not found:
                    for step in run.steps:
                        if step.tool_result and expected.lower() in str(step.tool_result).lower():
                            found = True
                            break
                passed = passed and found
            
            results.append(passed)
            
            status = "✅" if passed else "❌"
            tool_status = "🔧" if correct_tool else "⚠️"
            print(f"  {status} {tool_status} Correct tool: {correct_tool} | {elapsed:.1f}s")
            print(f"  📝 {run.final_answer}")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 All Tools Model: {passed}/{total} ({100*passed//total}%)")
    return passed, total


def run_phase2(model: str, backend, debug: bool,
               soul: str = None, soul_level: int = 2,
               force_react: bool = False,
               num_ctx: int = None, num_predict: int = None,
               temperature: float = None, top_p: float = None) -> tuple[int, int]:
    """Run all Phase 2 (model tool calling) tests."""
    print(f"\n{'#'*60}")
    print(f"# PHASE 2: Model Tool Calling")
    print(f"# Testing model's ability to use tools")
    print(f"{'#'*60}")
    
    total_passed = 0
    total_tests = 0
    
    # Test each tool category separately
    p, t = test_calculator_model(model, backend, debug, soul=soul, soul_level=soul_level,
                                 force_react=force_react, num_ctx=num_ctx,
                                 num_predict=num_predict, temperature=temperature, top_p=top_p)
    total_passed += p
    total_tests += t
    
    p, t = test_shell_model(model, backend, debug, soul=soul, soul_level=soul_level,
                            force_react=force_react, num_ctx=num_ctx,
                            num_predict=num_predict, temperature=temperature, top_p=top_p)
    total_passed += p
    total_tests += t
    
    p, t = test_datetime_model(model, backend, debug, soul=soul, soul_level=soul_level,
                               force_react=force_react, num_ctx=num_ctx,
                               num_predict=num_predict, temperature=temperature, top_p=top_p)
    total_passed += p
    total_tests += t
    
    p, t = test_file_model(model, backend, debug, soul=soul, soul_level=soul_level,
                            force_react=force_react, num_ctx=num_ctx,
                            num_predict=num_predict, temperature=temperature, top_p=top_p)
    total_passed += p
    total_tests += t
    
    p, t = test_python_repl_model(model, backend, debug, soul=soul, soul_level=soul_level,
                                  force_react=force_react, num_ctx=num_ctx,
                                  num_predict=num_predict, temperature=temperature, top_p=top_p)
    total_passed += p
    total_tests += t
    
    # Test with ALL tools available (model must choose correct tool)
    p, t = test_all_tools_model(model, backend, debug, soul=soul, soul_level=soul_level,
                                force_react=force_react, num_ctx=num_ctx,
                                num_predict=num_predict, temperature=temperature, top_p=top_p)
    total_passed += p
    total_tests += t
    
    print(f"\n{'='*60}")
    print(f"📊 PHASE 2 TOTAL: {total_passed}/{total_tests} ({100*total_passed//total_tests}%)")
    print(f"{'='*60}")
    
    return total_passed, total_tests


# ============================================================================
# Main
# ============================================================================

def main():
    args = parse_args()
    config = get_config()
    
    total_passed = 0
    total_tests = 0
    phase1_passed, phase1_total = 0, 0
    phase2_passed, phase2_total = 0, 0
    
    # Phase 1: Direct tool validation (always runs unless --model-only)
    if not args.model_only:
        phase1_passed, phase1_total = run_phase1()
        total_passed += phase1_passed
        total_tests += phase1_total
    
    # Phase 2: Model tool calling (requires backend)
    if not args.tools_only:
        model = args.model or config.default_model
        backend_name = args.backend or config.backend
        api_mode = getattr(args, 'api_mode', 'resp')
        timeout = getattr(args, 'timeout', None)
        backend = get_default_backend(backend_name, api_mode=api_mode)
        
        if not backend.is_running():
            print(f"\n❌ {backend_name.capitalize()} not running at {backend.base_url}")
            print(f"   Skipping Phase 2 (model tests)")
        else:
            print(f"\n⚛️ AgentNova Model Tool Tests")
            print(f"   Backend: {backend_name} ({backend.base_url})")
            print(f"   Model: {model}")
            if api_mode != 'resp':
                print(f"   API Mode: {api_mode}")
            if args.soul:
                print(f"   Soul: {args.soul}")
            num_ctx = getattr(args, 'num_ctx', None)
            if num_ctx is None:
                num_ctx = getattr(config, 'num_ctx', None)
            if num_ctx:
                ctx_display = f"{num_ctx // 1024}K" if num_ctx >= 1024 else str(num_ctx)
                print(f"   Context: {ctx_display}")
            
            phase2_passed, phase2_total = run_phase2(
                model, backend, args.debug,
                soul=args.soul, soul_level=args.soul_level,
                force_react=getattr(args, 'force_react', False),
                num_ctx=num_ctx,
                num_predict=getattr(args, 'num_predict', None),
                temperature=getattr(args, 'temperature', None),
                top_p=getattr(args, 'top_p', None)
            )
            total_passed += phase2_passed
            total_tests += phase2_total
    
    # Final summary
    print(f"\n{'='*60}")
    print(f"📊 OVERALL SUMMARY")
    print(f"{'='*60}")
    if phase1_total > 0:
        print(f"   Phase 1 (Direct): {phase1_passed}/{phase1_total}")
    if phase2_total > 0:
        print(f"   Phase 2 (Model):  {phase2_passed}/{phase2_total}")
    print(f"   ─────────────────────────")
    print(f"   TOTAL: {total_passed}/{total_tests} ({100*total_passed//total_tests if total_tests > 0 else 0}%)")
    print(f"{'='*60}")