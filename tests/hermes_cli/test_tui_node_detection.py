from __future__ import annotations

import os
import subprocess
from pathlib import Path

import hermes_cli.main as main_mod


def _write_executable(path: Path, body: str = "#!/bin/sh\n") -> None:
    path.write_text(body)
    path.chmod(0o755)


def test_find_node_on_user_shell_path_accepts_shell_managed_node(tmp_path, monkeypatch):
    node_dir = tmp_path / "volta" / "bin"
    node_dir.mkdir(parents=True)
    node = node_dir / "node"
    _write_executable(node)

    fake_shell = tmp_path / "fake-zsh"
    _write_executable(
        fake_shell,
        "#!/bin/sh\n"
        "if [ \"$1\" = \"-ic\" ]; then\n"
        "  printf '%s\\n' 'shell rc banner'\n"
        f"  printf '%s\\n' {node}\n"
        "fi\n",
    )
    monkeypatch.setenv("SHELL", str(fake_shell))

    assert main_mod._find_node_on_user_shell_path() == node.resolve()


def test_ensure_tui_node_uses_user_shell_before_bootstrap(tmp_path, monkeypatch):
    node_dir = tmp_path / "fnm" / "bin"
    node_dir.mkdir(parents=True)
    _write_executable(node_dir / "node")
    _write_executable(node_dir / "npm")

    fake_shell = tmp_path / "fake-zsh"
    _write_executable(
        fake_shell,
        "#!/bin/sh\n"
        "if [ \"$1\" = \"-ic\" ]; then\n"
        f"  printf '%s\\n' {node_dir / 'node'}\n"
        "fi\n",
    )
    monkeypatch.setenv("SHELL", str(fake_shell))
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))

    bootstrap_root = tmp_path / "project"
    helper = bootstrap_root / "scripts" / "lib" / "node-bootstrap.sh"
    helper.parent.mkdir(parents=True)
    helper.write_text("return 99\n")
    monkeypatch.setattr(main_mod, "PROJECT_ROOT", bootstrap_root)

    calls: list[list[str]] = []
    real_run = subprocess.run

    def spy_run(*args, **kwargs):
        calls.append(list(args[0]))
        return real_run(*args, **kwargs)

    monkeypatch.setattr(main_mod.subprocess, "run", spy_run)

    main_mod._ensure_tui_node()

    assert os.environ["PATH"].split(os.pathsep)[0] == str(node_dir)
    assert calls == [[str(fake_shell), "-ic", "command -v node"]]
