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

import os
import sys
import tomllib
from pathlib import Path

# Sentinel: version embedded in this file as build-time stamp + runtime fallback.
# At import time the authoritative version is always read from pyproject.toml so
# a git conflict resolution that reverts this file cannot silently downgrade the
# reported version (issue #35070).
_VERSION_FALLBACK = "0.15.1"
_RELEASE_DATE_FALLBACK = "2026.5.29"


def _read_version_from_pyproject():
    """Return ``(version, release_date)`` from ``pyproject.toml``.

    If the file is missing or unparseable the module-level fallback
    constants are returned so the agent can still start.
    """
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    try:
        with open(pyproject, "rb") as fh:
            data = tomllib.load(fh)
        version = data["project"]["version"]
    except (FileNotFoundError, KeyError, tomllib.TOMLDecodeError):
        version = _VERSION_FALLBACK
    return version, _RELEASE_DATE_FALLBACK


__version__, __release_date__ = _read_version_from_pyproject()


def _ensure_utf8():
    """Force UTF-8 stdout/stderr on Windows to prevent UnicodeEncodeError.

    Windows services and terminals default to cp1252, which cannot encode
    box-drawing characters used in CLI output. This causes unhandled
    UnicodeEncodeError crashes on gateway startup.
    """
    if sys.platform != "win32":
        return
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        try:
            if getattr(stream, "encoding", "").lower().replace("-", "") != "utf8":
                new_stream = open(
                    stream.fileno(), "w", encoding="utf-8",
                    buffering=1, closefd=False,
                )
                setattr(sys, stream_name, new_stream)
        except (AttributeError, OSError):
            pass


_ensure_utf8()
