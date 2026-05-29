"""Regression tests: batch_runner.py must be clean of select lint rules."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_batch_runner_has_zero_ruf100_violations() -> None:
    """batch_runner.py must have zero RUF100 (unused-noqa-directive) violations."""
    target = REPO_ROOT / "batch_runner.py"
    assert target.exists(), f"Target file not found: {target}"

    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--select=RUF100",
         str(target), "--output-format=concise"],
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0, (
        "batch_runner.py has RUF100 violation(s):\n"
        f"{result.stdout}\n{result.stderr}"
    )
