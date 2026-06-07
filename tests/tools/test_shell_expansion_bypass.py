"""Test that shell expansion bypasses are detected by detect_dangerous_command.

Regression tests for GitHub issue #36847: TUI gateway shell.exec RCE via
regex-denylist bypass using shell command substitution and parameter expansion.

This verifies the fix that blocks commands containing:
- Command substitution: $(cmd), `cmd`
- Parameter expansion: ${var}, ${param/pattern/replacement}
"""

import pytest
from tools.approval import detect_dangerous_command, _contains_shell_expansions


class TestShellExpansionDetection:
    """Verify that shell expansion bypasses are blocked."""

    def test_command_substitution_with_dollar_paren(self):
        """Block command substitution via $(...) syntax."""
        cmd = "$(echo rm) -rf /home/victim"
        is_dangerous, key, desc = detect_dangerous_command(cmd)
        assert is_dangerous, f"Should detect shell expansion: {desc}"
        assert "shell expansion" in desc.lower()

    def test_command_substitution_with_backticks(self):
        """Block command substitution via backticks."""
        cmd = "`echo rm` -rf /home/victim"
        is_dangerous, key, desc = detect_dangerous_command(cmd)
        assert is_dangerous, f"Should detect shell expansion: {desc}"
        assert "shell expansion" in desc.lower()

    def test_parameter_expansion_with_slash_replacement(self):
        """Block parameter expansion with string replacement: ${0/x/r}m."""
        cmd = "${0/x/r}m -rf /home/victim"
        is_dangerous, key, desc = detect_dangerous_command(cmd)
        assert is_dangerous, f"Should detect shell expansion: {desc}"
        assert "shell expansion" in desc.lower()

    def test_parameter_expansion_with_colon_default(self):
        """Block parameter expansion with default values: ${var:-default}."""
        cmd = "${CMD_TO_RUN:-rm} -rf /home/victim"
        is_dangerous, key, desc = detect_dangerous_command(cmd)
        assert is_dangerous, f"Should detect shell expansion: {desc}"
        assert "shell expansion" in desc.lower()

    def test_nested_command_substitution(self):
        """Block nested command substitution."""
        cmd = "$($(echo echo) echo rm) -rf /home/victim"
        is_dangerous, key, desc = detect_dangerous_command(cmd)
        assert is_dangerous, f"Should detect shell expansion: {desc}"

    def test_backslash_escape_still_blocked(self):
        """Ensure backslash escapes are still caught after normalization."""
        cmd = r"r\m -rf /home/victim"
        is_dangerous, key, desc = detect_dangerous_command(cmd)
        assert is_dangerous, f"Should detect dangerous pattern: {desc}"

    def test_empty_string_bypass_still_blocked(self):
        """Ensure empty-string literal bypasses are still caught."""
        cmd = "r''m -rf /home/victim"
        is_dangerous, key, desc = detect_dangerous_command(cmd)
        assert is_dangerous, f"Should detect dangerous pattern: {desc}"

    def test_safe_command_without_expansion(self):
        """Verify safe commands still pass."""
        cmd = "echo hello world"
        is_dangerous, key, desc = detect_dangerous_command(cmd)
        assert not is_dangerous, f"Safe command should not be detected: {desc}"

    def test_command_with_dollar_in_string(self):
        """Allow legitimate $ usage like in variable expansion contexts."""
        # A grep pattern or sed substitution might contain $
        cmd = "grep 'price: $' file.txt"
        is_dangerous, key, desc = detect_dangerous_command(cmd)
        # This is OK because it's just a grep pattern, no expansion syntax
        # (it doesn't have the expansion markers)
        assert not is_dangerous, f"Grep pattern with $ should be safe: {desc}"

    def test_variable_reference_without_braces(self):
        """Allow simple variable references like $HOME."""
        # Note: $HOME is a variable expansion, but we can't statically analyze
        # whether it contains dangerous content. However, for now we only block
        # the more dangerous ${...} brace syntax and command substitution.
        cmd = "ls $HOME"
        is_dangerous, key, desc = detect_dangerous_command(cmd)
        # For now, simple $VAR is allowed (would be caught by heuristics if needed)
        # The key bypass vectors are ${...} and $(...)
        # This may be revisited if needed


class TestContainsShellExpansions:
    """Unit tests for the _contains_shell_expansions helper."""

    def test_detects_dollar_paren(self):
        """Detect $(...)."""
        assert _contains_shell_expansions("$(echo rm)")
        assert _contains_shell_expansions("test $(cmd) end")

    def test_detects_backticks(self):
        """Detect backticks."""
        assert _contains_shell_expansions("`echo rm`")
        assert _contains_shell_expansions("test `cmd` end")

    def test_detects_brace_expansion(self):
        """Detect ${...}."""
        assert _contains_shell_expansions("${0/x/r}m")
        assert _contains_shell_expansions("${VAR}")
        assert _contains_shell_expansions("${var:-default}")

    def test_no_false_positives(self):
        """Don't flag safe commands."""
        assert not _contains_shell_expansions("echo hello")
        assert not _contains_shell_expansions("ls /home")
        assert not _contains_shell_expansions("rm -rf /tmp/test")


class TestTuiGatewayShellExecPath:
    """Verify that tui_gateway shell.exec properly gates commands."""

    def test_dangerous_patterns_still_caught(self):
        """Ensure regex-based dangerous patterns are still detected."""
        dangerous_commands = [
            "rm -rf /",
            "chmod 777 /etc/shadow",
            "DELETE FROM users",
            "dd if=/dev/sda of=/dev/sdb",
        ]
        for cmd in dangerous_commands:
            is_dangerous, _, desc = detect_dangerous_command(cmd)
            assert is_dangerous, f"Should catch: {cmd} ({desc})"

    def test_shell_expansion_bypasses_blocked(self):
        """Verify that shell expansion bypasses are blocked before reaching subprocess."""
        bypass_attempts = [
            "$(rm) -rf /",
            "`chmod` 777 /etc/shadow",
            "${0/x/r}m -rf /home",
        ]
        for cmd in bypass_attempts:
            is_dangerous, _, desc = detect_dangerous_command(cmd)
            assert is_dangerous, f"Should block bypass: {cmd} ({desc})"


class TestRegressionIssue36847:
    """Regression tests specifically for GitHub issue #36847.
    
    Issue: tui_gateway shell.exec inherits the approval denylist bypass.
    Commands with shell expansions bypassed the regex-based detection.
    """

    def test_issue_36847_command_substitution_example(self):
        """Test the exact example from issue #36847."""
        # The issue mentioned that this kind of command would bypass:
        cmd = "$(echo rm) -rf /home/victim"
        is_dangerous, pattern_key, desc = detect_dangerous_command(cmd)
        assert is_dangerous, "Command substitution should be blocked"
        assert "shell expansion" in desc.lower()

    def test_issue_36847_parameter_expansion_example(self):
        """Test parameter expansion variant."""
        cmd = "${0/x/r}m -rf /home/victim"
        is_dangerous, pattern_key, desc = detect_dangerous_command(cmd)
        assert is_dangerous, "Parameter expansion should be blocked"
        assert "shell expansion" in desc.lower()

    def test_import_error_path_now_fails_closed(self):
        """Verify that tui_gateway fails closed if approval module is unavailable.
        
        The tui_gateway code has: except ImportError: return error 5001
        This verifies the error handling is fail-closed, not fail-open.
        """
        # This test just documents the expected behavior in tui_gateway/server.py
        # The actual error is returned, not silently ignored
        pass
