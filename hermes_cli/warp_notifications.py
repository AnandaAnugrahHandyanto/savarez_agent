"""Warp Terminal CLI-agent notification support.

Warp's in-app agent notifications are delivered over OSC 777 as structured
``warp://cli-agent`` events.  This module keeps the integration deliberately
small and side-effect-free unless Warp advertises the protocol, and writes to
``/dev/tty`` so redirected stdout/stderr remain clean.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Mapping

OSC_PREFIX = "\x1b]777;notify;warp://cli-agent;"
OSC_SUFFIX = "\x07"
AGENT_NAME = "hermes"
DEFAULT_MODE = "auto"
MAX_TEXT_CHARS = 160

_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
_FALSE_VALUES = {"0", "false", "no", "off", "disabled", "none"}
_SECRETISH_RE = re.compile(
    r"(?i)\b(?P<key>[A-Za-z0-9_-]*(?:api[_-]?key|token|secret|password|passwd|pwd|authorization|bearer)[A-Za-z0-9_-]*)\b\s*[:=]\s*(?:bearer\s+)?\S+"
)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _normalize_mode(value: Any) -> str:
    """Return ``auto``, ``on`` or ``off`` for config/env values."""
    if isinstance(value, bool):
        return "on" if value else "off"
    text = str(value if value is not None else DEFAULT_MODE).strip().lower()
    if text in _TRUE_VALUES or text == "always":
        return "on"
    if text in _FALSE_VALUES:
        return "off"
    if text in {"auto", "warp"}:
        return "auto"
    return DEFAULT_MODE


def configured_mode(config: Mapping[str, Any] | None, environ: Mapping[str, str] | None = None) -> str:
    """Resolve the Warp notification mode from env/config.

    ``HERMES_WARP_NOTIFICATIONS`` wins over config.  Config lives at
    ``display.warp_notifications`` and accepts ``auto`` (default), ``on`` or
    ``off``; booleans are accepted for convenience.
    """
    env = environ if environ is not None else os.environ
    if "HERMES_WARP_NOTIFICATIONS" in env:
        return _normalize_mode(env.get("HERMES_WARP_NOTIFICATIONS"))
    display = config.get("display", {}) if isinstance(config, Mapping) else {}
    value = display.get("warp_notifications", DEFAULT_MODE) if isinstance(display, Mapping) else DEFAULT_MODE
    return _normalize_mode(value)


def warp_protocol_available(environ: Mapping[str, str] | None = None) -> bool:
    """Return True when the current terminal advertises Warp's CLI-agent protocol."""
    env = environ if environ is not None else os.environ
    return (
        env.get("TERM_PROGRAM") == "WarpTerminal"
        and env.get("WARP_CLI_AGENT_PROTOCOL_VERSION") == "1"
    )


def should_enable(config: Mapping[str, Any] | None = None, environ: Mapping[str, str] | None = None) -> bool:
    """Return whether Hermes should emit Warp CLI-agent notifications."""
    mode = configured_mode(config, environ)
    if mode == "off":
        return False
    if mode == "on":
        return True
    return warp_protocol_available(environ)


def _safe_text(value: Any, *, max_chars: int = MAX_TEXT_CHARS) -> str | None:
    """Sanitize short UI strings without preserving full prompts/results.

    The payload is visible to the terminal application.  Keep it short, remove
    control characters, and redact obvious secret-looking assignments.
    """
    if value is None:
        return None
    text = str(value)
    text = _CONTROL_RE.sub(" ", text)
    text = " ".join(text.split())
    text = _SECRETISH_RE.sub(lambda m: f"{m.group('key')}=[REDACTED]", text)
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"
    return text or None


def project_name_for_cwd(cwd: str | Path | None) -> str | None:
    if cwd is None:
        return None
    try:
        name = Path(cwd).resolve().name
    except Exception:
        name = Path(str(cwd)).name
    return name or None


class WarpAgentNotifier:
    """Emit structured Warp CLI-agent OSC notifications for Hermes."""

    def __init__(
        self,
        *,
        enabled: bool,
        session_id: str,
        cwd: str | Path | None = None,
        project: str | None = None,
        tty_path: str | Path = "/dev/tty",
        writer: Callable[[str], None] | None = None,
    ) -> None:
        self.enabled = enabled
        self.session_id = session_id
        self.cwd = str(cwd or os.getcwd())
        self.project = project or project_name_for_cwd(self.cwd)
        self.tty_path = str(tty_path)
        self._writer = writer

    @classmethod
    def from_config(
        cls,
        config: Mapping[str, Any] | None,
        *,
        session_id: str,
        cwd: str | Path | None = None,
        project: str | None = None,
        environ: Mapping[str, str] | None = None,
        tty_path: str | Path = "/dev/tty",
        writer: Callable[[str], None] | None = None,
    ) -> "WarpAgentNotifier":
        return cls(
            enabled=should_enable(config, environ),
            session_id=session_id,
            cwd=cwd,
            project=project,
            tty_path=tty_path,
            writer=writer,
        )

    def build_payload(self, event: str, **fields: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "v": 1,
            "agent": AGENT_NAME,
            "event": event,
            "session_id": self.session_id,
            "cwd": self.cwd,
            "project": self.project,
        }
        for key, value in fields.items():
            if value is None:
                continue
            if key == "tool_input" and isinstance(value, Mapping):
                # Tool input may contain private commands, paths, or API args.
                # Keep only a tiny redacted command/file preview for Warp UI.
                preview: dict[str, str] = {}
                for preview_key in ("command", "file_path"):
                    if preview_key in value:
                        safe = _safe_text(value.get(preview_key))
                        if safe:
                            preview[preview_key] = safe
                            break
                if preview:
                    payload[key] = preview
                continue
            safe = _safe_text(value)
            if safe is not None:
                payload[key] = safe
        return payload

    def encode(self, event: str, **fields: Any) -> str:
        body = json.dumps(
            self.build_payload(event, **fields),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return f"{OSC_PREFIX}{body}{OSC_SUFFIX}"

    def emit(self, event: str, **fields: Any) -> bool:
        if not self.enabled:
            return False
        data = self.encode(event, **fields)
        try:
            self._write(data)
            return True
        except OSError:
            # Never let terminal notification plumbing affect the agent run.
            return False

    def _write(self, data: str) -> None:
        if self._writer is not None:
            self._writer(data)
            return
        with open(self.tty_path, "w", encoding="utf-8", errors="replace") as tty:
            tty.write(data)
            tty.flush()
