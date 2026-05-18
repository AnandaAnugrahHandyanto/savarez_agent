import os
import subprocess
import sys
import textwrap
from pathlib import Path


def test_slash_worker_exits_on_stdin_eof_even_with_live_non_daemon_threads(tmp_path):
    """The dashboard/TUI slash worker must not survive its parent session.

    A real HermesCLI can leave helper threads alive.  When the TUI gateway or
    browser-backed PTY disappears, stdin reaches EOF; the worker should still
    terminate instead of lingering as an orphaned ``tui_gateway.slash_worker``
    process.
    """
    fake_cli = tmp_path / "cli.py"
    fake_cli.write_text(
        textwrap.dedent(
            """
            import threading
            import time

            class HermesCLI:
                def __init__(self, *args, **kwargs):
                    def spin():
                        while True:
                            time.sleep(60)
                    threading.Thread(target=spin, daemon=False).start()
                    self.console = None

                def process_command(self, command):
                    return None
            """
        )
    )

    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{tmp_path}{os.pathsep}{repo_root}{os.pathsep}{env.get('PYTHONPATH', '')}"
    env["HERMES_SLASH_WORKER_SHUTDOWN_GRACE_S"] = "0.1"

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "tui_gateway.slash_worker",
            "--session-key",
            "test-session",
            "--model",
            "test-model",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    assert proc.stdin is not None
    proc.stdin.close()
    proc.stdin = None

    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate(timeout=2)
        raise AssertionError(
            f"slash_worker stayed alive after stdin EOF; stdout={stdout!r} stderr={stderr!r}"
        )

    assert proc.returncode == 0
