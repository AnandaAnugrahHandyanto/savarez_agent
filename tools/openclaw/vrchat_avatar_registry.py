"""VRChat existing-avatar OSC config discovery and catalog building."""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

OSC_TYPES = {"Bool", "Int", "Float", "String"}
DEFAULT_BLOCKED_PARAMETER_NAMES = {
    "AFK",
    "MuteSelf",
    "Voice",
    "TrackingType",
    "VRMode",
    "IsOnGround",
    "VelocityX",
    "VelocityY",
    "VelocityZ",
    "Upright",
    "Grounded",
    "Seated",
    "InStation",
    "AvatarVersion",
}


@dataclass(frozen=True)
class AvatarOscEndpoint:
    address: str
    type: str


@dataclass(frozen=True)
class AvatarOscParameter:
    name: str
    input: AvatarOscEndpoint | None
    output: AvatarOscEndpoint | None
    writable: bool
    readable: bool
    inferredRole: str
    safety: str


@dataclass(frozen=True)
class AvatarParameterCatalog:
    avatarId: str
    avatarName: str | None
    sourceFile: str
    loadedAt: int
    parameters: list[AvatarOscParameter]


def now_ms() -> int:
    return int(time.time() * 1000)


def catalog_to_dict(catalog: AvatarParameterCatalog | None) -> dict[str, Any] | None:
    if catalog is None:
        return None
    return asdict(catalog)


def _normalize_type(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    lowered = raw.strip().lower()
    for value in OSC_TYPES:
        if value.lower() == lowered:
            return value
    return None


def _parse_endpoint(raw: Any) -> AvatarOscEndpoint | None:
    if not isinstance(raw, dict):
        return None
    address = raw.get("address")
    osc_type = _normalize_type(raw.get("type"))
    if not isinstance(address, str) or not address or osc_type is None:
        return None
    return AvatarOscEndpoint(address=address, type=osc_type)


def infer_parameter_role(name: str) -> str:
    lower = name.lower()
    if lower in {item.lower() for item in DEFAULT_BLOCKED_PARAMETER_NAMES}:
        return "system"
    if "gesture" in lower:
        return "gesture"
    if "emote" in lower or lower == "vrcemote":
        return "emote"
    if any(token in lower for token in ("face", "expression", "emotion")):
        return "expression"
    if any(token in lower for token in ("smile", "angry", "sad", "surprised", "fun")):
        return "expression"
    if lower in {"a", "i", "u", "e", "o"} or "mouth" in lower or "viseme" in lower:
        return "expression"
    if any(token in lower for token in ("tail", "ear", "toggle")):
        return "toggle"
    if any(token in lower for token in ("slider", "blend", "weight")):
        return "slider"
    return "unknown"


def classify_parameter_safety(name: str, writable: bool, role: str, blocked_names: set[str]) -> str:
    if name.lower() in {item.lower() for item in blocked_names}:
        return "blocked"
    if not writable:
        return "safe"
    if role in {"expression", "emote", "gesture", "toggle", "slider"}:
        return "safe"
    if role == "system":
        return "blocked"
    return "needs_review"


def parse_avatar_config(
    path: Path,
    *,
    expected_avatar_id: str | None = None,
    blocked_names: set[str] | None = None,
) -> AvatarParameterCatalog:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError(f"Avatar OSC config is not an object: {path}")
    avatar_id = raw.get("id")
    if not isinstance(avatar_id, str) or not avatar_id:
        raise ValueError(f"Avatar OSC config missing id: {path}")
    if expected_avatar_id and avatar_id != expected_avatar_id:
        raise ValueError(f"Avatar OSC config id mismatch: {avatar_id} != {expected_avatar_id}")
    avatar_name = raw.get("name") if isinstance(raw.get("name"), str) else None
    raw_parameters = raw.get("parameters")
    if not isinstance(raw_parameters, list):
        raise ValueError(f"Avatar OSC config missing parameters array: {path}")

    blocked = blocked_names or DEFAULT_BLOCKED_PARAMETER_NAMES
    parameters: list[AvatarOscParameter] = []
    for raw_param in raw_parameters:
        if not isinstance(raw_param, dict):
            continue
        name = raw_param.get("name")
        if not isinstance(name, str) or not name:
            continue
        input_endpoint = _parse_endpoint(raw_param.get("input"))
        output_endpoint = _parse_endpoint(raw_param.get("output"))
        writable = input_endpoint is not None
        readable = output_endpoint is not None
        role = infer_parameter_role(name)
        parameters.append(
            AvatarOscParameter(
                name=name,
                input=input_endpoint,
                output=output_endpoint,
                writable=writable,
                readable=readable,
                inferredRole=role,
                safety=classify_parameter_safety(name, writable, role, blocked),
            )
        )

    return AvatarParameterCatalog(
        avatarId=avatar_id,
        avatarName=avatar_name,
        sourceFile=str(path),
        loadedAt=now_ms(),
        parameters=parameters,
    )


def _as_path(value: str, repo_root: Path) -> Path:
    raw = Path(value).expanduser()
    return raw if raw.is_absolute() else repo_root / raw


def resolve_osc_roots(config: dict[str, Any], repo_root: Path) -> list[Path]:
    avatar_control = (
        config.get("vrchat", {}).get("avatarControl", {})
        if isinstance(config.get("vrchat"), dict)
        else {}
    )
    roots: list[Path] = []
    configured = avatar_control.get("oscConfigRoots") if isinstance(avatar_control, dict) else None
    if isinstance(configured, list):
        roots.extend(_as_path(item, repo_root) for item in configured if isinstance(item, str))

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        roots.append(Path(f"{local_app_data}Low") / "VRChat" / "VRChat" / "OSC")
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        roots.append(Path(user_profile) / "AppData" / "LocalLow" / "VRChat" / "VRChat" / "OSC")

    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def discover_avatar_config_file(
    avatar_id: str,
    *,
    config: dict[str, Any],
    repo_root: Path,
) -> Path | None:
    candidates: list[Path] = []
    for root in resolve_osc_roots(config, repo_root):
        candidates.extend(root.glob(f"*/Avatars/{avatar_id}.json"))
    for candidate in candidates:
        try:
            parse_avatar_config(candidate, expected_avatar_id=avatar_id)
            return candidate
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return None


class VrchatAvatarRegistry:
    """Track the current avatar and load its generated OSC parameter catalog."""

    def __init__(self, repo_root: Path, config: dict[str, Any]) -> None:
        self.repo_root = repo_root
        self.config = config
        self.current_avatar_id: str | None = None
        self.catalog: AvatarParameterCatalog | None = None
        self.last_error: str | None = None

    def reload_config(self, config: dict[str, Any]) -> None:
        self.config = config

    def set_current_avatar(self, avatar_id: str) -> AvatarParameterCatalog | None:
        self.current_avatar_id = avatar_id
        return self.load_catalog(avatar_id)

    def load_catalog(self, avatar_id: str | None = None) -> AvatarParameterCatalog | None:
        target_avatar_id = avatar_id or self.current_avatar_id
        if not target_avatar_id:
            self.last_error = "no_current_avatar"
            self.catalog = None
            return None
        avatar_control = (
            self.config.get("vrchat", {}).get("avatarControl", {})
            if isinstance(self.config.get("vrchat"), dict)
            else {}
        )
        blocked_names = DEFAULT_BLOCKED_PARAMETER_NAMES
        if isinstance(avatar_control, dict) and isinstance(
            avatar_control.get("blockedParameterNames"), list
        ):
            blocked_names = {
                item
                for item in avatar_control["blockedParameterNames"]
                if isinstance(item, str) and item
            } | DEFAULT_BLOCKED_PARAMETER_NAMES

        source_file = discover_avatar_config_file(
            target_avatar_id,
            config=self.config,
            repo_root=self.repo_root,
        )
        if source_file is None:
            self.last_error = f"avatar_config_not_found:{target_avatar_id}"
            self.catalog = None
            return None
        try:
            self.catalog = parse_avatar_config(
                source_file,
                expected_avatar_id=target_avatar_id,
                blocked_names=blocked_names,
            )
            self.last_error = None
            return self.catalog
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self.last_error = str(exc)
            self.catalog = None
            return None

