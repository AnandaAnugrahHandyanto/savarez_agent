from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path


def _write_fake_python(path: Path, argv_log: Path) -> None:
    path.write_text(
        f"""#!/usr/bin/env python3
import pathlib
import sys

args = sys.argv[1:]
if args[:2] == ["-c", "import pytest_split"]:
    raise SystemExit(0)
if args[:2] == ["-m", "pytest"]:
    pathlib.Path(r"{argv_log}").write_text("\\n".join(args[2:]) + "\\n")
    raise SystemExit(0)
if args[:2] == ["-m", "pip"]:
    raise SystemExit(0)
raise SystemExit("unexpected argv: " + " ".join(args))
""",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_run_tests_wrapper_handles_empty_args(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    scripts_dir = repo_root / "scripts"
    scripts_dir.mkdir(parents=True)
    source_script = Path(__file__).resolve().parents[1] / "scripts" / "run_tests.sh"
    target_script = scripts_dir / "run_tests.sh"
    shutil.copy2(source_script, target_script)
    target_script.chmod(target_script.stat().st_mode | stat.S_IXUSR)

    argv_log = tmp_path / "pytest-argv.txt"
    fake_python = repo_root / ".venv" / "bin" / "python"
    fake_python.parent.mkdir(parents=True)
    (fake_python.parent / "activate").write_text("# fake activate\n", encoding="utf-8")
    _write_fake_python(fake_python, argv_log)

    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    result = subprocess.run(
        ["/bin/bash", str(target_script)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert argv_log.read_text(encoding="utf-8").splitlines() == [
        "-o",
        "addopts=",
        "-n",
        "4",
        "--ignore=tests/integration",
        "--ignore=tests/e2e",
        "-m",
        "not integration",
    ]
