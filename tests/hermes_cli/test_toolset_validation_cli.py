import subprocess
import sys


def _run(*args):
    return subprocess.run(
        [sys.executable, "-m", "hermes_cli.main", "chat", *args],
        capture_output=True,
        text=True,
        timeout=90,
    )


def test_tui_misparse_exits_with_hint():
    # `hermes chat -tui` -> argparse `-t ui` -> unknown toolset -> fail with a --tui hint.
    res = _run("-tui")
    assert res.returncode == 2
    assert "--tui" in res.stderr
    assert "ui" in res.stderr


def test_all_unknown_toolsets_exit_2():
    res = _run("-t", "definitely_not_a_toolset")
    assert res.returncode == 2
    assert "definitely_not_a_toolset" in res.stderr
