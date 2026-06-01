"""Tests for terminal.shell_init_files / terminal.auto_source_bashrc.

A bash ``-l -c`` invocation does NOT source ``~/.bashrc``, so tools that
register themselves there (nvm, asdf, pyenv) stay invisible to the
environment snapshot built by ``LocalEnvironment.init_session``.  These
tests verify the config-driven prelude that fixes that.
"""

import os
from unittest.mock import patch

import pytest

from tools.environments.local import (
    LocalEnvironment,
    _prepend_shell_init,
    _read_terminal_shell_init_config,
    _resolve_shell_init_files,
)


class TestResolveShellInitFiles:
    def test_auto_sources_bashrc_when_present(self, tmp_path, monkeypatch):
        bashrc = tmp_path / ".bashrc"
        bashrc.write_text('export MARKER=seen\n')
        monkeypatch.setenv("HOME", str(tmp_path))

        # Default config: auto_source_bashrc on, no explicit list.
        with patch(
            "tools.environments.local._read_terminal_shell_init_config",
            return_value=([], True),
        ):
            resolved = _resolve_shell_init_files()

        assert resolved == [str(bashrc)]

    def test_auto_sources_profile_when_present(self, tmp_path, monkeypatch):
        """~/.profile is where ``n`` / ``nvm`` installers typically write
        their PATH export on Debian/Ubuntu, and it has no interactivity
        guard so a non-interactive source actually runs it.
        """
        profile = tmp_path / ".profile"
        profile.write_text('export PATH="$HOME/n/bin:$PATH"\n')
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch(
            "tools.environments.local._read_terminal_shell_init_config",
            return_value=([], True),
        ):
            resolved = _resolve_shell_init_files()

        assert resolved == [str(profile)]

    def test_auto_sources_bash_profile_when_present(self, tmp_path, monkeypatch):
        bash_profile = tmp_path / ".bash_profile"
        bash_profile.write_text('export MARKER=bp\n')
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch(
            "tools.environments.local._read_terminal_shell_init_config",
            return_value=([], True),
        ):
            resolved = _resolve_shell_init_files()

        assert resolved == [str(bash_profile)]

    def test_auto_sources_profile_before_bashrc(self, tmp_path, monkeypatch):
        """Both files present: profile runs first so PATH exports in
        profile take effect even if bashrc short-circuits on the
        non-interactive ``case $- in *i*) ;; *) return;; esac`` guard.
        """
        profile = tmp_path / ".profile"
        profile.write_text('export FROM_PROFILE=1\n')
        bash_profile = tmp_path / ".bash_profile"
        bash_profile.write_text('export FROM_BASH_PROFILE=1\n')
        bashrc = tmp_path / ".bashrc"
        bashrc.write_text('export FROM_BASHRC=1\n')
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch(
            "tools.environments.local._read_terminal_shell_init_config",
            return_value=([], True),
        ):
            resolved = _resolve_shell_init_files()

        assert resolved == [str(profile), str(bash_profile), str(bashrc)]

    def test_skips_bashrc_when_missing(self, tmp_path, monkeypatch):
        # No rc files written.
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch(
            "tools.environments.local._read_terminal_shell_init_config",
            return_value=([], True),
        ):
            resolved = _resolve_shell_init_files()

        assert resolved == []

    def test_auto_source_bashrc_off_suppresses_default(self, tmp_path, monkeypatch):
        bashrc = tmp_path / ".bashrc"
        bashrc.write_text('export MARKER=seen\n')
        profile = tmp_path / ".profile"
        profile.write_text('export MARKER=p\n')
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch(
            "tools.environments.local._read_terminal_shell_init_config",
            return_value=([], False),
        ):
            resolved = _resolve_shell_init_files()

        assert resolved == []

    def test_explicit_list_wins_over_auto(self, tmp_path, monkeypatch):
        bashrc = tmp_path / ".bashrc"
        bashrc.write_text('export FROM_BASHRC=1\n')
        custom = tmp_path / "custom.sh"
        custom.write_text('export FROM_CUSTOM=1\n')
        monkeypatch.setenv("HOME", str(tmp_path))

        # auto_source_bashrc stays True but the explicit list takes precedence.
        with patch(
            "tools.environments.local._read_terminal_shell_init_config",
            return_value=([str(custom)], True),
        ):
            resolved = _resolve_shell_init_files()

        assert resolved == [str(custom)]
        assert str(bashrc) not in resolved

    def test_expands_home_and_env_vars(self, tmp_path, monkeypatch):
        target = tmp_path / "rc" / "custom.sh"
        target.parent.mkdir()
        target.write_text('export A=1\n')
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("CUSTOM_RC_DIR", str(tmp_path / "rc"))

        with patch(
            "tools.environments.local._read_terminal_shell_init_config",
            return_value=(["~/rc/custom.sh"], False),
        ):
            resolved_home = _resolve_shell_init_files()

        with patch(
            "tools.environments.local._read_terminal_shell_init_config",
            return_value=(["${CUSTOM_RC_DIR}/custom.sh"], False),
        ):
            resolved_var = _resolve_shell_init_files()

        assert resolved_home == [str(target)]
        assert resolved_var == [str(target)]

    def test_missing_explicit_files_are_skipped_silently(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch(
            "tools.environments.local._read_terminal_shell_init_config",
            return_value=([str(tmp_path / "does-not-exist.sh")], False),
        ):
            resolved = _resolve_shell_init_files()

        assert resolved == []


class TestPrependShellInit:
    def test_empty_list_returns_command_unchanged(self):
        assert _prepend_shell_init("echo hi", []) == "echo hi"

    def test_prepends_guarded_source_lines(self):
        wrapped = _prepend_shell_init("echo hi", ["/tmp/a.sh", "/tmp/b.sh"])
        assert "echo hi" in wrapped
        # Each file is sourced through a guarded [ -r … ] && . '…' || true
        # pattern so a missing/broken rc can't abort the bootstrap.
        assert "/tmp/a.sh" in wrapped
        assert "/tmp/b.sh" in wrapped
        assert "|| true" in wrapped
        assert "set +e" in wrapped

    def test_escapes_single_quotes(self):
        wrapped = _prepend_shell_init("echo hi", ["/tmp/o'malley.sh"])
        # The path must survive as the shell receives it; embedded single
        # quote is escaped as '\'' rather than breaking the outer quoting.
        assert "o'\\''malley" in wrapped


@pytest.mark.skipif(
    os.environ.get("CI") == "true" and not os.path.isfile("/bin/bash"),
    reason="Requires bash; CI sandbox may strip it.",
)
class TestSnapshotEndToEnd:
    """Spin up a real LocalEnvironment and confirm the snapshot sources
    extra init files."""

    def test_snapshot_picks_up_init_file_exports(self, tmp_path, monkeypatch):
        init_file = tmp_path / "custom-init.sh"
        init_file.write_text(
            'export HERMES_SHELL_INIT_PROBE="probe-ok"\n'
            'export PATH="/opt/shell-init-probe/bin:$PATH"\n'
        )

        with patch(
            "tools.environments.local._read_terminal_shell_init_config",
            return_value=([str(init_file)], False),
        ):
            env = LocalEnvironment(cwd=str(tmp_path), timeout=15)
            try:
                result = env.execute(
                    'echo "PROBE=$HERMES_SHELL_INIT_PROBE"; echo "PATH=$PATH"'
                )
            finally:
                env.cleanup()

        output = result.get("output", "")
        assert "PROBE=probe-ok" in output
        assert "/opt/shell-init-probe/bin" in output

    def test_profile_path_export_survives_bashrc_interactive_guard(
        self, tmp_path, monkeypatch
    ):
        """Reproduces the Debian/Ubuntu + ``n``/``nvm`` case.

        Setup:
          - ``~/.bashrc`` starts with ``case $- in *i*) ;; *) return;; esac``
            (the default on Debian/Ubuntu) and would happily export a PATH
            entry below that guard — but never gets there because a
            non-interactive source short-circuits.
          - ``~/.profile`` exports ``$HOME/fake-n/bin`` onto PATH, no guard.

        Expectation: auto-sourced rc list picks up ``~/.profile`` before
        ``~/.bashrc``, so the snapshot ends up with ``fake-n/bin`` on PATH
        even though the bashrc export is silently skipped.
        """
        fake_n_bin = tmp_path / "fake-n" / "bin"
        fake_n_bin.mkdir(parents=True)

        profile = tmp_path / ".profile"
        profile.write_text(
            f'export PATH="{fake_n_bin}:$PATH"\n'
            'export FROM_PROFILE=profile-ok\n'
        )
        bashrc = tmp_path / ".bashrc"
        bashrc.write_text(
            'case $- in\n'
            '    *i*) ;;\n'
            '      *) return;;\n'
            'esac\n'
            'export FROM_BASHRC=bashrc-should-not-appear\n'
        )

        monkeypatch.setenv("HOME", str(tmp_path))

        with patch(
            "tools.environments.local._read_terminal_shell_init_config",
            return_value=([], True),
        ):
            env = LocalEnvironment(cwd=str(tmp_path), timeout=15)
            try:
                result = env.execute(
                    'echo "PATH=$PATH"; '
                    'echo "FROM_PROFILE=$FROM_PROFILE"; '
                    'echo "FROM_BASHRC=$FROM_BASHRC"'
                )
            finally:
                env.cleanup()

        output = result.get("output", "")
        assert "FROM_PROFILE=profile-ok" in output
        assert str(fake_n_bin) in output
        # bashrc short-circuited on the interactive guard — its export never ran
        assert "FROM_BASHRC=bashrc-should-not-appear" not in output


class TestSnapshotSkipUnderscoreFunctions:
    """Regression test for issue where ``_``-prefixed functions defined in
    the user's shell init files leaked their bodies into the snapshot
    file as top-level bash statements, producing ``local: can only be used
    in a function`` errors and ``exit 127`` on every subsequent command.

    The previous filter ``declare -f | grep -vE '^_[^_]'`` only matched
    the function header line, so the body (including ``local``, ``export``,
    closing brace) was kept verbatim and re-sourced at top level.  The fix
    enumerates function names with ``compgen -A function`` and emits each
    public function's full body via ``declare -f "$name"``, so the body
    is never re-parsed.
    """

    def test_snapshot_excludes_underscore_function_body(
        self, tmp_path, monkeypatch
    ):
        bashrc = tmp_path / ".bashrc"
        bashrc.write_text(
            "_helper() {\n"
            "  local foo=1\n"
            "  export MARKER_LEAK=$foo\n"
            "}\n"
            "keepme() {\n"
            "  local bar=2\n"
            "  echo 'keepme-ran: '$bar\n"
            "}\n"
        )
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch(
            "tools.environments.local._read_terminal_shell_init_config",
            return_value=([], True),
        ):
            env = LocalEnvironment(cwd=str(tmp_path), timeout=15)
            env.init_session()
            try:
                # The snapshot file should be re-sourceable bash.
                import subprocess
                check = subprocess.run(
                    ["bash", "-n", env._snapshot_path],
                    capture_output=True,
                    text=True,
                )
                snap_text = open(env._snapshot_path).read()
            finally:
                env.cleanup()

        assert check.returncode == 0, (
            f"snapshot is not valid bash; stderr={check.stderr!r}\n"
            f"snapshot contents:\n{snap_text}"
        )
        # The private function body must NOT appear at top level.
        # The public function name should still be present.
        assert "local foo=1" not in snap_text, (
            f"private function body leaked into snapshot:\n{snap_text}"
        )
        assert "keepme ()" in snap_text, (
            f"public function should still be captured:\n{snap_text}"
        )

    def test_execute_works_when_bashrc_defines_underscore_functions(
        self, tmp_path, monkeypatch
    ):
        """End-to-end regression: with a bashrc full of _-prefixed helpers,
        a downstream ``echo`` should still return its actual output, not
        the empty / exit 127 we used to see on every call.
        """
        bashrc = tmp_path / ".bashrc"
        bashrc.write_text(
            "_cc_inject_minimax() {\n"
            "  local m=\"${1:-default-model}\"\n"
            "  export ANTHROPIC_BASE_URL='https://example.invalid'\n"
            "}\n"
            "_load_minimax_key_for_claude() {\n"
            "  local _mm_key=\"$HOME/.config/cc-profiles/minimax.key\"\n"
            "  if [[ -f \"$_mm_key\" ]]; then\n"
            "    export MINIMAX_API_KEY='***'\n"
            "  fi\n"
            "}\n"
            "_private_helper() {\n"
            "  local inner=42\n"
            "  echo 'should-never-print: '$inner\n"
            "}\n"
        )
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch(
            "tools.environments.local._read_terminal_shell_init_config",
            return_value=([], True),
        ):
            env = LocalEnvironment(cwd=str(tmp_path), timeout=15)
            try:
                result = env.execute("echo TERMINAL_TOOL_WORKS")
            finally:
                env.cleanup()

        assert result.get("returncode") == 0, (
            f"execute returned non-zero: {result!r}"
        )
        assert "TERMINAL_TOOL_WORKS" in result.get("output", ""), (
            f"expected stdout to contain echo output, got: {result!r}"
        )
        # The private function body must not have leaked into stdout.
        assert "should-never-print" not in result.get("output", "")
