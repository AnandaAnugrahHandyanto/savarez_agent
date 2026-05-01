"""Optional RTK adapter for Hermes terminal execution.

The external RTK binary is optional. This adapter detects it when present and
otherwise fails open so terminal commands execute normally.
"""

from __future__ import annotations

import shutil


class RTKAdapter:
    """Small RTK command-wrapper adapter with no-op fallback behavior."""

    def __init__(self, rtk_path: str | None = None) -> None:
        self.rtk_path = rtk_path or shutil.which("rtk")

    def is_available(self) -> bool:
        return bool(self.rtk_path)

    def should_use_rtk(self, command: str) -> bool:
        if not self.is_available():
            return False
        stripped = command.strip()
        prefixes = (
            "git status",
            "git log",
            "git diff",
            "pytest",
            "python -m pytest",
            "cargo test",
            "go test",
            "npm test",
            "ls ",
            "ls\t",
            "ls -",
        )
        return stripped == "ls" or stripped.startswith(prefixes)

    def wrap_command(self, command: str) -> str:
        if not self.is_available() or not self.should_use_rtk(command):
            return command
        # Conservative integration: keep command unchanged until the installed
        # RTK CLI contract is explicitly validated for this environment.
        return command

    def filter_output(self, command: str, output: str) -> str:
        return output

    def get_stats(self, original_length: int, filtered_length: int) -> dict[str, float]:
        bytes_saved = max(original_length - filtered_length, 0)
        percent_saved = (bytes_saved / original_length * 100.0) if original_length else 0.0
        return {
            "original_length": original_length,
            "filtered_length": filtered_length,
            "bytes_saved": bytes_saved,
            "percent_saved": percent_saved,
        }


_ADAPTER = RTKAdapter()


def get_rtk_adapter() -> RTKAdapter:
    """Return the process-global RTK adapter."""
    return _ADAPTER
