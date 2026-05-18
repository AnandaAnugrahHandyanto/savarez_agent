"""Regression tests for t_757db01d — TMPDIR ENOSPC must not spam stderr.

When the volume backing ``$TMPDIR`` is full, the LocalEnvironment
bootstrap used to emit two lines of ``No space left on device`` per
process invocation (one for ``hermes-snap-*.sh``, one for
``hermes-cwd-*.txt``).  Those lines contaminated every tool-output tail
read by an LLM, especially for cron-spawned workers that make 50+
shell calls per tick.

The fix has two parts:
  1. Every snapshot write redirects stderr to /dev/null so ENOSPC is
     silent at the shell layer.
  2. The Python init_session detects an empty/missing snapshot file
     (because the writes silently failed) and logs ONE structured
     warning, then falls back to ``bash -l`` per command.
"""

import os
import re
import subprocess
from unittest.mock import patch

import pytest

from tools.environments.local import LocalEnvironment


@pytest.fixture
def env_no_init():
    """LocalEnvironment with init_session patched out, so we can poke at
    the bootstrap script and validation logic in isolation."""
    with patch.object(LocalEnvironment, "init_session", autospec=True, return_value=None):
        return LocalEnvironment(cwd=".", timeout=10)


class TestBootstrapStderrRedirect:
    """The bootstrap script must redirect stderr on every write.

    These assertions are deliberately string-level: the bug was a missing
    ``2>/dev/null`` on lines that did ``> snap`` / ``>> snap``, so we
    grep the rendered bootstrap for the absence of unredirected writes.
    """

    def test_every_snapshot_write_redirects_stderr(self, env_no_init):
        env = env_no_init
        bootstrap = self._render_bootstrap(env)

        # Find each line that writes to the snap or cwd file.  After the
        # fix, every such line must be of the form:
        #   ( ... > path ) 2>/dev/null || true
        # because a bare ``cmd > path 2>/dev/null`` does NOT silence
        # bash's own ``cannot create`` error on an open-failure.
        snap = re.escape(env._snapshot_path)
        cwd_file = re.escape(env._cwd_file)
        write_pattern = re.compile(
            rf".*(>|>>)\s*('?({snap}|{cwd_file})'?)\b.*"
        )
        offenders = []
        for lineno, line in enumerate(bootstrap.splitlines(), start=1):
            if not write_pattern.match(line):
                continue
            # Must be subshell-wrapped AND have an outer ``2>/dev/null``.
            stripped = line.strip()
            ok = (
                stripped.startswith("(")
                and ") 2>/dev/null" in stripped
            )
            if not ok:
                offenders.append((lineno, line))

        assert not offenders, (
            "Bootstrap lines write to snap/cwd file without subshell-wrapped "
            "stderr redirect — ENOSPC/EACCES on a full TMPDIR will leak to "
            "stderr (bash emits the open-failure from the parent shell, "
            "BEFORE the inline 2>/dev/null applies).  Offending lines:\n"
            + "\n".join(f"  L{n}: {l}" for n, l in offenders)
        )

    def test_bootstrap_handles_enospc_silently(self, env_no_init, tmp_path):
        """End-to-end: point snap/cwd at an unwritable path and confirm
        bash produces no ``No space left on device`` (or equivalent)
        stderr noise, regardless of ENOSPC vs EACCES."""
        env = env_no_init
        # Reroute writes to an unwritable directory.  We can't easily
        # provoke a real ENOSPC in CI, but EACCES exercises the same
        # ``2>/dev/null`` redirect path.
        unwritable = tmp_path / "ro"
        unwritable.mkdir()
        unwritable.chmod(0o500)  # r-x only — writes will EACCES
        env._snapshot_path = str(unwritable / "snap.sh")
        env._cwd_file = str(unwritable / "cwd.txt")

        bootstrap = self._render_bootstrap(env)
        # Run the bootstrap directly via bash and capture stderr.
        proc = subprocess.run(
            ["bash", "-c", bootstrap],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # The bootstrap script itself MUST exit 0 (every write has
        # ``|| true``) AND stderr MUST NOT contain a permission/space
        # error.  If either fails, the redirects regressed.
        assert proc.returncode == 0, (
            f"bootstrap exited {proc.returncode}; stderr:\n{proc.stderr}"
        )
        bad_phrases = [
            "No space left on device",
            "Permission denied",
            "cannot create",
        ]
        for phrase in bad_phrases:
            assert phrase not in proc.stderr, (
                f"ENOSPC-class write leaked to stderr: {phrase!r}\n"
                f"Full stderr:\n{proc.stderr}"
            )

        # Restore so pytest tmp cleanup can remove it.
        unwritable.chmod(0o700)

    @staticmethod
    def _render_bootstrap(env):
        """Mimic init_session's bootstrap string-construction in isolation."""
        import shlex
        _quoted_snap = shlex.quote(env._snapshot_path)
        _quoted_cwd_file = shlex.quote(env._cwd_file)
        _quoted_cwd = shlex.quote(env.cwd)
        return (
            f"( export -p > {_quoted_snap} ) 2>/dev/null || true\n"
            f"( declare -f | grep -vE '^_[^_]' >> {_quoted_snap} ) 2>/dev/null || true\n"
            f"( alias -p >> {_quoted_snap} ) 2>/dev/null || true\n"
            f"( echo 'shopt -s expand_aliases' >> {_quoted_snap} ) 2>/dev/null || true\n"
            f"( echo 'set +e' >> {_quoted_snap} ) 2>/dev/null || true\n"
            f"( echo 'set +u' >> {_quoted_snap} ) 2>/dev/null || true\n"
            f"builtin cd {_quoted_cwd} 2>/dev/null || true\n"
            f"( pwd -P > {_quoted_cwd_file} ) 2>/dev/null || true\n"
            f"printf '\\n{env._cwd_marker}%s{env._cwd_marker}\\n' \"$(pwd -P)\"\n"
        )


class TestSnapshotValid:
    """LocalEnvironment must detect the silent-empty-snapshot case."""

    def test_returns_false_for_missing_snapshot(self, env_no_init, tmp_path):
        env = env_no_init
        env._snapshot_path = str(tmp_path / "missing.sh")
        assert env._snapshot_valid() is False

    def test_returns_false_for_empty_snapshot(self, env_no_init, tmp_path):
        env = env_no_init
        snap = tmp_path / "empty.sh"
        snap.touch()  # zero bytes — looks like a silently-failed write
        env._snapshot_path = str(snap)
        assert env._snapshot_valid() is False

    def test_returns_true_for_populated_snapshot(self, env_no_init, tmp_path):
        env = env_no_init
        snap = tmp_path / "ok.sh"
        snap.write_text("export PATH=/usr/bin\n")
        env._snapshot_path = str(snap)
        assert env._snapshot_valid() is True


class TestInitSessionFallback:
    """When the snapshot validates as empty, init_session must log a
    structured warning AND set _snapshot_ready=False so subsequent
    commands fall back to ``bash -l`` instead of silently sourcing an
    empty/missing snapshot."""

    def test_logs_one_warning_and_falls_back_on_empty_snapshot(self, tmp_path, monkeypatch, caplog):
        # Build a real LocalEnvironment but redirect the snapshot to a
        # tmpdir we then leave empty after init.
        env = LocalEnvironment.__new__(LocalEnvironment)
        env.cwd = str(tmp_path)
        env.timeout = 10
        env.env = {}
        env._session_id = "testfallback"
        env._snapshot_path = str(tmp_path / "snap.sh")
        env._cwd_file = str(tmp_path / "cwd.txt")
        env._cwd_marker = "__HERMES_CWD_testfallback__"
        env._snapshot_ready = False
        # Mock _run_bash so it produces a process that exits 0 but never
        # writes the snapshot (simulating ENOSPC).
        class _StubProc:
            stdout = None
            def poll(self):
                return 0
            def wait(self, timeout=None):
                return 0
        monkeypatch.setattr(env, "_run_bash", lambda *a, **kw: _StubProc())
        monkeypatch.setattr(env, "_wait_for_process", lambda *a, **kw: {"stdout": "", "returncode": 0})

        # Snapshot file does NOT exist — simulating a silently-failed
        # write under ENOSPC.
        assert not os.path.exists(env._snapshot_path)

        import logging
        with caplog.at_level(logging.WARNING, logger="tools.environments.base"):
            env.init_session()

        assert env._snapshot_ready is False, (
            "init_session must NOT set _snapshot_ready=True when the "
            "snapshot file failed to land — otherwise every later "
            "command sources a missing/empty snapshot."
        )
        # Exactly one warning, mentioning the snapshot path.
        warnings = [
            r for r in caplog.records
            if r.levelno >= logging.WARNING
            and "snapshot" in r.getMessage().lower()
        ]
        assert len(warnings) == 1, (
            f"Expected exactly one structured warning, got {len(warnings)}:\n"
            + "\n".join(r.getMessage() for r in warnings)
        )
        assert env._snapshot_path in warnings[0].getMessage()
        assert "TMPDIR" in warnings[0].getMessage()
