"""Halt flag state for CMH subprocess wrapper foundations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home

HALT_FLAGS_FILENAME = "cmh_halt_flags.json"

_KNOWN_HALT_FLAGS: tuple[str, ...] = (
    "cowork_headless",
    "codex_auto_dispatch",
    "hermes_telegram_acks",
    "all",
)


@dataclass(frozen=True)
class HaltState:
    flags: dict[str, bool]
    malformed: bool = False
    error: str = ""
    path: Path | None = None


@dataclass(frozen=True)
class HaltDecision:
    halted: bool
    active_flag: str
    message: str


def default_halt_flags() -> dict[str, bool]:
    """Return the default fail-open halt flag map."""
    return {key: False for key in _KNOWN_HALT_FLAGS}


def halt_flags_path() -> Path:
    """Return the CMH halt flags file path under HERMES_HOME/state."""
    return get_hermes_home() / "state" / HALT_FLAGS_FILENAME


def load_halt_flags(path: Path | None = None) -> HaltState:
    """Load halt flags, failing closed when persisted state is unreadable."""
    resolved_path = path or halt_flags_path()
    flags = default_halt_flags()

    try:
        raw = resolved_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return HaltState(flags=flags, path=resolved_path)
    except OSError as exc:
        return HaltState(
            flags=flags,
            malformed=True,
            error=str(exc),
            path=resolved_path,
        )

    try:
        loaded: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        return HaltState(
            flags=flags,
            malformed=True,
            error=str(exc),
            path=resolved_path,
        )

    if not isinstance(loaded, dict):
        return HaltState(
            flags=flags,
            malformed=True,
            error="halt flags JSON must be an object",
            path=resolved_path,
        )

    for key in _KNOWN_HALT_FLAGS:
        if key in loaded:
            flags[key] = bool(loaded[key])

    return HaltState(flags=flags, path=resolved_path)


def save_halt_flags(flags: dict[str, bool], path: Path | None = None) -> None:
    """Persist known halt flags as stable JSON."""
    resolved_path = path or halt_flags_path()
    merged = default_halt_flags()
    for key in _KNOWN_HALT_FLAGS:
        if key in flags:
            merged[key] = bool(flags[key])

    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(
        json.dumps(merged, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def is_halted(class_name: str, state: HaltState | None = None) -> HaltDecision:
    """Return whether a subprocess class is halted by current halt flags."""
    current_state = state or load_halt_flags()
    path = current_state.path or halt_flags_path()

    if current_state.malformed:
        return HaltDecision(
            halted=True,
            active_flag="state_error",
            message=f"CMH halt flag state error at {path}: {current_state.error}",
        )

    if current_state.flags.get("all", False):
        return HaltDecision(
            halted=True,
            active_flag="all",
            message=f"CMH subprocess class {class_name} halted by all flag at {path}",
        )

    if current_state.flags.get(class_name, False):
        return HaltDecision(
            halted=True,
            active_flag=class_name,
            message=f"CMH subprocess class {class_name} halted by {class_name} flag at {path}",
        )

    return HaltDecision(
        halted=False,
        active_flag="",
        message=f"CMH subprocess class {class_name} is not halted",
    )
