"""Regression tests: tools/code_execution_tool.py must be clean of select lint rules."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_code_execution_tool_has_zero_f401_violations() -> None:
    """tools/code_execution_tool.py must have zero F401 (unused-import) violations."""
    target = REPO_ROOT / "tools" / "code_execution_tool.py"
    assert target.exists(), f"Target file not found: {target}"

    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--select=F401",
         str(target), "--output-format=concise"],
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0, (
        "tools/code_execution_tool.py has F401 violation(s):\n"
        f"{result.stdout}{result.stderr}"
    )


def test_code_execution_tool_has_zero_ruf100_violations() -> None:
    """tools/code_execution_tool.py must have zero RUF100 (unused-noqa-directive) violations."""
    target = REPO_ROOT / "tools" / "code_execution_tool.py"
    assert target.exists(), f"Target file not found: {target}"

    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--select=RUF100",
         str(target), "--output-format=concise"],
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0, (
        "tools/code_execution_tool.py has RUF100 violation(s):\n"
        f"{result.stdout}{result.stderr}"
    )
