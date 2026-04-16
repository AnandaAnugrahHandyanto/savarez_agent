"""
Hermes CLI - Unified command-line interface for Hermes Agent.

Provides subcommands for:
- hermes chat          - Interactive chat (same as ./hermes)
- hermes gateway       - Run gateway in foreground
- hermes gateway start - Start gateway service
- hermes gateway stop  - Stop gateway service  
- hermes setup         - Interactive setup wizard
- hermes status        - Show status of all components
- hermes cron          - Manage cron jobs
"""

import sys


def _configure_console_error_fallback(stream) -> None:
    """Avoid startup crashes on Windows consoles that are not UTF-8 capable."""
    if sys.platform != "win32" or stream is None:
        return

    reconfigure = getattr(stream, "reconfigure", None)
    if not callable(reconfigure):
        return

    encoding = (getattr(stream, "encoding", None) or "").lower().replace("-", "")
    if encoding == "utf8":
        return

    errors = (getattr(stream, "errors", None) or "").lower()
    if errors in {"replace", "backslashreplace", "namereplace", "xmlcharrefreplace"}:
        return

    try:
        reconfigure(errors="replace")
    except Exception:
        pass


def _enable_windows_console_error_fallback() -> None:
    _configure_console_error_fallback(getattr(sys, "stdout", None))
    _configure_console_error_fallback(getattr(sys, "stderr", None))


_enable_windows_console_error_fallback()

__version__ = "0.9.0"
__release_date__ = "2026.4.13"
