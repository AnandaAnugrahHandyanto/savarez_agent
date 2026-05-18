"""Local event bus and asset policy for the browser resident 3D companion."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


EVENT_TYPES = {
    "state",
    "emotion",
    "speak_start",
    "speak_end",
    "gesture",
    "look_at",
    "idle",
    "load_model",
}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


@dataclass
class CompanionEventBus:
    """Validate, store, and expose recent companion3d runtime events."""

    repo_root: Path
    config: dict[str, Any]
    events: list[dict[str, Any]] = field(default_factory=list)
    last_state: dict[str, Any] = field(default_factory=dict)

    def reload_config(self, config: dict[str, Any]) -> None:
        self.config = config

    @property
    def companion_config(self) -> dict[str, Any]:
        raw = self.config.get("desktopCompanion3d")
        return raw if isinstance(raw, dict) else {}

    def add_event(self, event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"Unsupported companion3d event type: {event_type}")
        event = {
            "type": event_type,
            "timestamp": _now_ms(),
            "payload": payload or {},
        }
        self.events.append(event)
        self.events = self.events[-100:]
        if event_type in {"state", "emotion", "gesture", "look_at", "idle", "load_model"}:
            self.last_state.update({event_type: event["payload"], "lastEventAt": event["timestamp"]})
        return event

    def status(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.companion_config.get("enabled", True)),
            "browserPort": self.companion_config.get("browserPort", 18795),
            "eventWsPort": self.companion_config.get("eventWsPort", 18796),
            "events": self.events[-10:],
            "state": self.last_state,
        }

    def resolve_model_path(self, model_path: str) -> Path:
        if "://" in model_path:
            raise ValueError("Remote companion3d model URLs are disabled")
        cfg = self.companion_config
        asset_root_raw = cfg.get("assetRoot", "state/companion3d/assets")
        asset_root = Path(asset_root_raw) if isinstance(asset_root_raw, str) else Path("state/companion3d/assets")
        asset_root = asset_root if asset_root.is_absolute() else self.repo_root / asset_root
        asset_root = asset_root.resolve()
        candidate = Path(model_path).expanduser()
        if not candidate.is_absolute():
            candidate = (self.repo_root / candidate).resolve()
        else:
            candidate = candidate.resolve()
        if not _is_relative_to(candidate, asset_root):
            raise ValueError("Companion3D model path must stay under the configured assetRoot")
        allowed_extensions = cfg.get("allowedExtensions", [".vrm", ".glb", ".gltf", ".fbx"])
        allowed = {
            item.lower()
            for item in allowed_extensions
            if isinstance(item, str) and item.startswith(".")
        }
        if candidate.suffix.lower() not in allowed:
            raise ValueError(f"Unsupported companion3d model extension: {candidate.suffix}")
        if not candidate.exists() or not candidate.is_file():
            raise FileNotFoundError(f"Companion3D model not found: {candidate}")
        max_model_size_mb = int(cfg.get("maxModelSizeMb", 150))
        if candidate.stat().st_size > max_model_size_mb * 1024 * 1024:
            raise ValueError("Companion3D model exceeds configured maxModelSizeMb")
        return candidate

