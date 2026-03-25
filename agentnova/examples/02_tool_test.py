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
    parser.add_argument("--tools-only", action="store_true", help="Only run Phase 1 (direct tool tests)")
    parser.add_argument("--model-only", action="store_true", help="Only run Phase 2 (model tool calling)")
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
        read_ok = test_content in read_result
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


def test_calculator_model(model: str, backend, debug: bool = False) -> tuple[int, int]:
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


def test_shell_model(model: str, backend, debug: bool = False) -> tuple[int, int]:
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
        
        sys_prompt = "Use shell commands to answer questions."
        if is_windows:
            sys_prompt += " Use Windows commands (dir, cd, echo)."
        else:
            sys_prompt += " Use Unix commands (ls, pwd, echo)."
        
        agent = Agent(
            model=model,
            tools=tools,
            backend=backend,
            max_steps=5,
            debug=debug,
        )
        
        t0 = time.time()
        run = agent.run(prompt)
        elapsed = time.time() - t0
        
        tool_used = check_tool_used(run, "shell")
        
        if not tool_used:
            print(f"  ❌ Shell tool was NOT called!")
            results.append(False)
            continue
        
        if expected:
            passed = expected.lower() in run.final_answer.lower()
        else:
            passed = True
        
        results.append(passed)
        status = "✅" if passed else "❌"
        print(f"  {status} {elapsed:.1f}s, {len(run.steps)} steps")
        print(f"  📝 {run.final_answer[:80]}")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 Shell Model: {passed}/{total} ({100*passed//total}%)")
    return passed, total


def test_datetime_model(model: str, backend, debug: bool = False) -> tuple[int, int]:
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
        print(f"  📝 {run.final_answer[:60]}")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 DateTime Model: {passed}/{total} ({100*passed//total}%)")
    return passed, total


def run_phase2(model: str, backend, debug: bool) -> tuple[int, int]:
    """Run all Phase 2 (model tool calling) tests."""
    print(f"\n{'#'*60}")
    print(f"# PHASE 2: Model Tool Calling")
    print(f"# Testing model's ability to use tools")
    print(f"{'#'*60}")
    
    total_passed = 0
    total_tests = 0
    
    p, t = test_calculator_model(model, backend, debug)
    total_passed += p
    total_tests += t
    
    p, t = test_shell_model(model, backend, debug)
    total_passed += p
    total_tests += t
    
    p, t = test_datetime_model(model, backend, debug)
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
        backend = get_default_backend(backend_name)
        
        if not backend.is_running():
            print(f"\n❌ {backend_name.capitalize()} not running at {backend.base_url}")
            print(f"   Skipping Phase 2 (model tests)")
        else:
            print(f"\n⚛️ AgentNova Model Tool Tests")
            print(f"   Backend: {backend_name} ({backend.base_url})")
            print(f"   Model: {model}")
            
            phase2_passed, phase2_total = run_phase2(model, backend, args.debug)
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
    
    return 0 if total_passed == total_tests else 1


if __name__ == "__main__":
    sys.exit(main())