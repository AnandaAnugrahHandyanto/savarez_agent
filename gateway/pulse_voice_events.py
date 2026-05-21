"""Best-effort local voice-out bridge for Pulse/Aegis.

Aegis must not speak raw executor output.  The gateway publishes only short,
purpose-built voice UX events to ``$HERMES_HOME/pulse/voice-out.jsonl`` and
Aegis consumes that file/SSE stream for TTS.

This is intentionally best-effort: failures must never affect chat delivery.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home

_LOCK = threading.Lock()
_MAX_BYTES = 2_000_000
_MAX_TEXT_CHARS = 180
_ALLOWED_KINDS = {"ack", "completion", "error", "question", "progress"}
_MEDIA_RE = re.compile(r"MEDIA:\S+")
_DIRECTIVE_RE = re.compile(r"\[\[[^\]]+\]\]")
_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`]{1,120})`")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^\)]+\)")


def _enabled() -> bool:
    value = str(os.getenv("HERMES_PULSE_VOICE_EVENTS", "1")).strip().lower()
    return value not in {"0", "false", "no", "off"}


def voice_out_path() -> Path:
    """Return the canonical Jarvis-style voice-out JSONL path."""
    return get_hermes_home() / "pulse" / "voice-out.jsonl"


def voice_events_path() -> Path:
    """Return the legacy voice-events JSONL path.

    Kept as a compatibility mirror for older Aegis builds.  New consumers should
    read :func:`voice_out_path`.
    """
    return get_hermes_home() / "pulse" / "voice-events.jsonl"


def _trim_if_needed(path: Path) -> None:
    try:
        if not path.exists() or path.stat().st_size <= _MAX_BYTES:
            return
        data = path.read_bytes()[-(_MAX_BYTES // 2):]
        first_newline = data.find(b"\n")
        if first_newline >= 0:
            data = data[first_newline + 1 :]
        path.write_bytes(data)
    except OSError:
        return


def _first_sentence(text: str) -> str:
    match = re.match(r"^.{1,150}?[.!?。！？](?=\s|$)", text)
    return match.group(0) if match else text


def voice_safe_text(text: str, *, max_chars: int = _MAX_TEXT_CHARS) -> str:
    """Return short text safe enough to speak aloud.

    This intentionally strips code blocks, media tags, markdown links, transport
    directives, bullets/headings, and excess whitespace.  It then keeps only a
    single bounded sentence so executor prose/logs cannot leak into room audio.
    """
    text = str(text or "")
    text = _CODE_FENCE_RE.sub("", text)
    text = _MEDIA_RE.sub("", text)
    text = _DIRECTIVE_RE.sub("", text)
    text = _MARKDOWN_LINK_RE.sub(r"\1", text)
    text = _INLINE_CODE_RE.sub(r"\1", text)
    text = re.sub(r"^[#>*\-•\s]+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    text = _first_sentence(text).strip()
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip(" ,.;:") + "…"
    return text


def completion_voice_text(final_response: str) -> tuple[str, str]:
    """Derive a concise completion/question/error event from executor output."""
    spoken = voice_safe_text(final_response)
    if not spoken:
        return "completion", "Done."
    lowered = spoken.lower()
    if lowered.startswith(("⚠", "error", "failed", "sorry")):
        return "error", spoken
    if "?" in spoken and len(spoken) <= 160:
        return "question", spoken
    if not lowered.startswith(("done", "finished", "completed", "created", "updated", "fixed")):
        spoken = voice_safe_text(f"Done — {spoken}")
    return "completion", spoken


def _write_event(path: Path, event: dict[str, Any]) -> None:
    line = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
    _trim_if_needed(path)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)


def publish_voice_out(kind: str, text: str, **metadata: Any) -> None:
    """Append a canonical voice-out event for local Pulse/Aegis subscribers.

    ``kind`` must be one of ``ack``, ``completion``, ``error``, ``question``, or
    ``progress``.  ``text`` is sanitized and bounded here even if callers forget.
    """
    if not _enabled():
        return
    kind = str(kind or "progress").strip().lower()
    if kind not in _ALLOWED_KINDS:
        kind = "progress"
    text = voice_safe_text(text)
    if not text:
        return
    try:
        event = {
            "id": f"{time.time_ns()}",
            "ts": time.time(),
            "kind": kind,
            "text": text,
            "max_seconds": int(metadata.pop("max_seconds", 4) or 4),
            **{k: v for k, v in metadata.items() if v is not None},
        }
        canonical = voice_out_path()
        legacy = voice_events_path()
        canonical.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            _write_event(canonical, event)
            # Compatibility mirror for older Aegis builds; same canonical schema,
            # not raw delta/commentary.
            if legacy != canonical:
                _write_event(legacy, event)
    except Exception:
        return


def publish_completion_voice_out(final_response: str, **metadata: Any) -> None:
    """Publish a short spoken completion derived from executor final text."""
    kind, text = completion_voice_text(final_response)
    publish_voice_out(kind, text, **metadata)


def publish_voice_event(kind: str, text: str, **metadata: Any) -> None:
    """Backward-compatible wrapper for older gateway call sites.

    Raw streaming ``delta`` events are deliberately ignored.  Interim assistant
    ``commentary`` maps to a short ``progress`` voice-out event because the
    gateway publishes a dedicated turn-start ``ack`` separately.
    """
    legacy_kind = str(kind or "").strip().lower()
    if legacy_kind == "delta":
        return
    mapped = "progress" if legacy_kind == "commentary" else legacy_kind
    publish_voice_out(mapped, text, **metadata)
