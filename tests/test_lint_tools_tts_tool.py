"""Regression test for E741 (ambiguous variable name) in tools/tts_tool.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestToolsTtsToolE741:
    """Guard against E741 (ambiguous variable name) in tools/tts_tool.py."""

    def test_tools_tts_tool_py_has_zero_e741_violations(self) -> None:
        """tools/tts_tool.py must have zero E741 violations."""
        target = REPO_ROOT / "tools" / "tts_tool.py"
        assert target.exists(), f"Target file not found: {target}"

        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--select=E741",
             "--output-format=concise", str(target)],
            capture_output=True, text=True, check=False,
        )

        assert result.returncode == 0, (
            f"tools/tts_tool.py has E741 violations:\n"
            f"{result.stdout}\n"
        )
