"""Per-avatar action profiles for VRChat existing-avatar OSC control."""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from .vrchat_avatar_registry import AvatarParameterCatalog, AvatarOscParameter, now_ms
from .vrchat_osc_bridge import VrchatOscBridge
from .vrchat_safety_gate import SafetyGateBlocked, VrchatSafetyGate


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized or "action"


def _profile_dir(config: dict[str, Any], repo_root: Path) -> Path:
    avatar_control = (
        config.get("vrchat", {}).get("avatarControl", {})
        if isinstance(config.get("vrchat"), dict)
        else {}
    )
    raw = avatar_control.get("profileDir") if isinstance(avatar_control, dict) else None
    profile_dir = Path(raw) if isinstance(raw, str) and raw else Path("state/vrchat/avatar-profiles")
    return profile_dir if profile_dir.is_absolute() else repo_root / profile_dir


def _step_for(
    parameter: AvatarOscParameter,
    value: bool | int | float | str,
    *,
    duration_ms: int | None = None,
    reset_value: bool | int | float | str | None = None,
) -> dict[str, Any]:
    if parameter.input is None:
        raise ValueError(f"Parameter is not writable: {parameter.name}")
    step: dict[str, Any] = {
        "address": parameter.input.address,
        "name": parameter.name,
        "type": parameter.input.type,
        "value": value,
    }
    if duration_ms is not None:
        step["durationMs"] = duration_ms
    if reset_value is not None:
        step["resetValue"] = reset_value
    return step


def _add_action(
    actions: dict[str, Any],
    key: str,
    label: str,
    step: dict[str, Any],
    *,
    description: str,
    cooldown_ms: int = 1500,
) -> None:
    base_key = _slug(key)
    candidate = base_key
    suffix = 2
    while candidate in actions:
        candidate = f"{base_key}_{suffix}"
        suffix += 1
    actions[candidate] = {
        "label": label,
        "description": description,
        "cooldownMs": cooldown_ms,
        "steps": [step],
    }


def _valid_step_value(osc_type: str, value: Any) -> bool:
    if osc_type == "Bool":
        return isinstance(value, bool)
    if osc_type == "Int":
        return isinstance(value, int) and not isinstance(value, bool)
    if osc_type == "Float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if osc_type == "String":
        return isinstance(value, str)
    return False


def _suggest_parameter_actions(parameter: AvatarOscParameter, actions: dict[str, Any]) -> None:
    if parameter.input is None or parameter.safety == "blocked":
        return
    name = parameter.name
    lower = name.lower()
    osc_type = parameter.input.type
    if lower in {"vrcemote", "emote", "emoteswitch"} or "emote" in lower:
        if osc_type == "Int":
            for value in range(1, 9):
                _add_action(
                    actions,
                    f"{name}_{value}",
                    f"{name} {value}",
                    _step_for(parameter, value, duration_ms=1500, reset_value=0),
                    description="Generated emote candidate. Review the avatar before approving.",
                    cooldown_ms=2500,
                )
        return
    if "gestureleft" in lower or "gestureright" in lower:
        if osc_type == "Int":
            for value in range(0, 8):
                _add_action(
                    actions,
                    f"{name}_{value}",
                    f"{name} {value}",
                    _step_for(parameter, value, duration_ms=800, reset_value=0),
                    description="Generated hand gesture candidate.",
                )
        return
    if any(token in lower for token in ("smile", "happy", "angry", "sad", "surprised", "fun")):
        if osc_type == "Bool":
            _add_action(
                actions,
                name,
                name,
                _step_for(parameter, True, duration_ms=1200, reset_value=False),
                description="Generated expression toggle candidate.",
            )
        elif osc_type == "Float":
            _add_action(
                actions,
                name,
                name,
                _step_for(parameter, 1.0, duration_ms=1200, reset_value=0.0),
                description="Generated expression slider candidate.",
            )
        elif osc_type == "Int":
            _add_action(
                actions,
                name,
                name,
                _step_for(parameter, 1, duration_ms=1200, reset_value=0),
                description="Generated expression int candidate.",
            )
        return
    if any(token in lower for token in ("mouth", "viseme")) or lower in {"a", "i", "u", "e", "o"}:
        if osc_type == "Float":
            _add_action(
                actions,
                f"viseme_{name}",
                f"Viseme {name}",
                _step_for(parameter, 1.0, duration_ms=250, reset_value=0.0),
                description="Generated mouth-shape candidate for local speech sync.",
                cooldown_ms=250,
            )
            if "talk" not in actions:
                _add_action(
                    actions,
                    "talk",
                    "Talk",
                    _step_for(parameter, 0.7, duration_ms=400, reset_value=0.0),
                    description="Generated conservative talk pulse candidate.",
                    cooldown_ms=500,
                )
        return
    if any(token in lower for token in ("tail", "ear")) and osc_type in {"Bool", "Float"}:
        value: bool | float = True if osc_type == "Bool" else 1.0
        reset: bool | float = False if osc_type == "Bool" else 0.0
        _add_action(
            actions,
            name,
            name,
            _step_for(parameter, value, duration_ms=900, reset_value=reset),
            description="Generated body-part motion candidate.",
        )


class AvatarActionProfileStore:
    """Read, suggest, approve, and execute per-avatar action profiles."""

    def __init__(self, repo_root: Path, config: dict[str, Any]) -> None:
        self.repo_root = repo_root
        self.config = config

    def reload_config(self, config: dict[str, Any]) -> None:
        self.config = config

    @property
    def directory(self) -> Path:
        return _profile_dir(self.config, self.repo_root)

    def profile_path(self, avatar_id: str, *, suggested: bool = False) -> Path:
        suffix = ".suggested.json" if suggested else ".json"
        return self.directory / f"{avatar_id}{suffix}"

    def load_profile(self, avatar_id: str, *, suggested: bool = False) -> dict[str, Any] | None:
        path = self.profile_path(avatar_id, suggested=suggested)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8-sig"))

    def write_profile(self, profile: dict[str, Any], *, suggested: bool = False) -> dict[str, Any]:
        avatar_id = str(profile["avatarId"])
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.profile_path(avatar_id, suggested=suggested)
        path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
        return profile

    def suggest_profile(self, catalog: AvatarParameterCatalog) -> dict[str, Any]:
        actions: dict[str, Any] = {}
        for parameter in catalog.parameters:
            _suggest_parameter_actions(parameter, actions)
        denied = [
            parameter.name
            for parameter in catalog.parameters
            if parameter.safety == "blocked" or not parameter.writable
        ]
        profile = {
            "version": 1,
            "avatarId": catalog.avatarId,
            "avatarName": catalog.avatarName,
            "approved": False,
            "createdAt": now_ms(),
            "updatedAt": now_ms(),
            "parameterSourceFile": catalog.sourceFile,
            "actions": actions,
            "deniedParameters": denied,
            "notes": (
                "Suggested by Hypura Harness from VRChat OSC JSON. Review every action "
                "before copying or approving this profile."
            ),
        }
        return self.write_profile(profile, suggested=True)

    def approve_profile(self, avatar_id: str, *, notes: str | None = None) -> dict[str, Any]:
        source = self.load_profile(avatar_id, suggested=True) or self.load_profile(avatar_id)
        if source is None:
            raise FileNotFoundError(f"No suggested or approved profile found for {avatar_id}")
        source["approved"] = True
        source["updatedAt"] = now_ms()
        if notes:
            source["notes"] = notes
        return self.write_profile(source, suggested=False)

    async def execute_action(
        self,
        *,
        action: str,
        profile: dict[str, Any],
        catalog: AvatarParameterCatalog,
        bridge: VrchatOscBridge,
        safety_gate: VrchatSafetyGate,
    ) -> dict[str, Any]:
        if profile.get("avatarId") != catalog.avatarId:
            return {"success": False, "error": "avatar_mismatch"}
        if profile.get("approved") is not True:
            return {"success": False, "error": "profile_not_approved"}
        actions = profile.get("actions")
        if not isinstance(actions, dict) or action not in actions:
            return {"success": False, "error": "unknown_action"}
        binding = actions[action]
        if not isinstance(binding, dict):
            return {"success": False, "error": "invalid_action_binding"}
        steps = binding.get("steps")
        if not isinstance(steps, list) or not steps:
            return {"success": False, "error": "invalid_action_steps"}
        parameter_by_name = {parameter.name: parameter for parameter in catalog.parameters}
        try:
            safety_gate.ensure_action_allowed(
                action,
                int(binding.get("cooldownMs")) if isinstance(binding.get("cooldownMs"), int) else None,
            )
            executed: list[dict[str, Any]] = []
            for raw_step in steps:
                if not isinstance(raw_step, dict):
                    return {"success": False, "error": "invalid_step"}
                name = raw_step.get("name")
                address = raw_step.get("address")
                if not isinstance(name, str) or not isinstance(address, str):
                    return {"success": False, "error": "invalid_step_address"}
                if not address.startswith("/avatar/parameters/"):
                    return {"success": False, "error": "invalid_step_address"}
                parameter = parameter_by_name.get(name)
                if parameter is None or parameter.input is None:
                    return {"success": False, "error": "parameter_not_writable", "parameter": name}
                if parameter.input.address != address:
                    return {"success": False, "error": "parameter_address_mismatch", "parameter": name}
                if parameter.safety == "blocked":
                    return {"success": False, "error": "parameter_blocked", "parameter": name}
                value = raw_step.get("value")
                if not _valid_step_value(parameter.input.type, value):
                    return {"success": False, "error": "invalid_step_value", "parameter": name}
                bridge.send_parameter(address, value)
                executed.append(
                    {"name": name, "address": address, "value": value, "reset": False}
                )
                duration_ms = raw_step.get("durationMs")
                if isinstance(duration_ms, int) and "resetValue" in raw_step:
                    await asyncio.sleep(max(duration_ms, 0) / 1000)
                    safety_gate.ensure_osc_rate()
                    reset_value = raw_step.get("resetValue")
                    if not _valid_step_value(parameter.input.type, reset_value):
                        return {"success": False, "error": "invalid_reset_value", "parameter": name}
                    bridge.send_parameter(address, reset_value)
                    executed.append(
                        {
                            "name": name,
                            "address": address,
                            "value": reset_value,
                            "reset": True,
                        }
                    )
        except SafetyGateBlocked as exc:
            return {"success": False, "error": exc.code, "detail": exc.detail}
        return {"success": True, "action": action, "steps": executed}
