"""Tests for {args} substitution in exec-type quick commands."""

from gateway.run import _substitute_quick_command_args


class TestSubstituteQuickCommandArgs:
    def test_simple_args_inserted(self):
        out = _substitute_quick_command_args("/bin/echo {args}", "hello")
        assert out == "/bin/echo hello"

    def test_no_placeholder_passes_through(self):
        out = _substitute_quick_command_args("/bin/date", "ignored")
        assert out == "/bin/date"

    def test_empty_args_quoted_as_empty_literal(self):
        # shlex.quote("") -> "''" so the empty arg still occupies a slot
        out = _substitute_quick_command_args("/bin/echo {args}", "")
        assert out == "/bin/echo ''"

    def test_ampersand_does_not_background(self):
        # Without quoting, "eggs & bacon" would fork "eggs" into the
        # background and treat "bacon" as a new command.
        out = _substitute_quick_command_args("/bin/echo {args}", "eggs & bacon")
        assert "&" in out
        assert out.count("'") >= 2  # shell-quoted literal

    def test_semicolon_does_not_chain_commands(self):
        out = _substitute_quick_command_args("/bin/echo {args}", "a; rm -rf /tmp/x")
        assert "; rm" not in out.replace("'", "")[:len("echo a; rm")]  # not raw

    def test_pipe_does_not_pipe(self):
        out = _substitute_quick_command_args("/bin/echo {args}", "x | cat")
        # The pipe character is contained inside the single-quoted literal
        assert "'x | cat'" in out

    def test_dollar_command_substitution_disarmed(self):
        out = _substitute_quick_command_args("/bin/echo {args}", "$(whoami)")
        assert "'$(whoami)'" in out

    def test_backticks_disarmed(self):
        out = _substitute_quick_command_args("/bin/echo {args}", "`whoami`")
        assert "'`whoami`'" in out

    def test_redirection_disarmed(self):
        out = _substitute_quick_command_args("/bin/echo {args}", "x > /tmp/y")
        assert "'x > /tmp/y'" in out

    def test_existing_single_quotes_escaped(self):
        # shlex.quote handles embedded single quotes safely
        out = _substitute_quick_command_args("/bin/echo {args}", "it's fine")
        # shlex.quote produces: 'it'"'"'s fine'
        assert out.startswith("/bin/echo ")
        # The substituted portion must parse back to the original via shlex.split
        import shlex
        tokens = shlex.split(out)
        assert tokens == ["/bin/echo", "it's fine"]

    def test_multiple_placeholders_all_substituted(self):
        out = _substitute_quick_command_args("/bin/echo {args} again {args}", "hi")
        assert out == "/bin/echo hi again hi"

    def test_unicode_passes_through(self):
        out = _substitute_quick_command_args("/bin/echo {args}", "café ☕")
        import shlex
        tokens = shlex.split(out)
        assert tokens == ["/bin/echo", "café ☕"]
