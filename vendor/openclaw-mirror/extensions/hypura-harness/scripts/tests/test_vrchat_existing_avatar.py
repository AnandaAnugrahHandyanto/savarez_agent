import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from hypura.companion_event_bus import CompanionEventBus
from hypura.vrchat_action_profile import AvatarActionProfileStore
from hypura.vrchat_avatar_registry import (
    AvatarOscEndpoint,
    AvatarOscParameter,
    AvatarParameterCatalog,
    VrchatAvatarRegistry,
    discover_avatar_config_file,
    parse_avatar_config,
)
from hypura.vrchat_safety_gate import VrchatSafetyGate


def write_avatar_config(path: Path, avatar_id: str = "avtr_existing") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "id": avatar_id,
                "name": "Existing Avatar",
                "parameters": [
                    {
                        "name": "Smile",
                        "input": {"address": "/avatar/parameters/Smile", "type": "Bool"},
                        "output": {"address": "/avatar/parameters/Smile", "type": "Bool"},
                    },
                    {
                        "name": "AFK",
                        "input": {"address": "/avatar/parameters/AFK", "type": "Bool"},
                    },
                    {
                        "name": "VelocityX",
                        "output": {"address": "/avatar/parameters/VelocityX", "type": "Float"},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_discovers_avatar_config_by_avatar_id(tmp_path: Path) -> None:
    root = tmp_path / "OSC"
    config_path = root / "usr_abc" / "Avatars" / "avtr_existing.json"
    write_avatar_config(config_path)

    found = discover_avatar_config_file(
        "avtr_existing",
        config={"vrchat": {"avatarControl": {"oscConfigRoots": [str(root)]}}},
        repo_root=tmp_path,
    )

    assert found == config_path


def test_parse_catalog_marks_writable_and_blocked_parameters(tmp_path: Path) -> None:
    config_path = tmp_path / "avatar.json"
    write_avatar_config(config_path)

    catalog = parse_avatar_config(config_path, expected_avatar_id="avtr_existing")

    smile = next(parameter for parameter in catalog.parameters if parameter.name == "Smile")
    afk = next(parameter for parameter in catalog.parameters if parameter.name == "AFK")
    velocity = next(parameter for parameter in catalog.parameters if parameter.name == "VelocityX")
    assert smile.writable is True
    assert smile.safety == "safe"
    assert afk.safety == "blocked"
    assert velocity.readable is True
    assert velocity.writable is False


def test_suggested_profile_is_unapproved_and_denies_blocked_parameters(tmp_path: Path) -> None:
    config_path = tmp_path / "avatar.json"
    write_avatar_config(config_path)
    catalog = parse_avatar_config(config_path, expected_avatar_id="avtr_existing")
    store = AvatarActionProfileStore(
        tmp_path,
        {"vrchat": {"avatarControl": {"profileDir": "state/vrchat/avatar-profiles"}}},
    )

    profile = store.suggest_profile(catalog)

    assert profile["approved"] is False
    assert "smile" in profile["actions"]
    assert "AFK" in profile["deniedParameters"]
    assert store.profile_path("avtr_existing", suggested=True).exists()


@pytest.mark.asyncio
async def test_execute_action_requires_approved_matching_profile(tmp_path: Path) -> None:
    catalog = AvatarParameterCatalog(
        avatarId="avtr_existing",
        avatarName="Existing Avatar",
        sourceFile=str(tmp_path / "avatar.json"),
        loadedAt=1,
        parameters=[
            AvatarOscParameter(
                name="Smile",
                input=AvatarOscEndpoint(address="/avatar/parameters/Smile", type="Bool"),
                output=None,
                writable=True,
                readable=False,
                inferredRole="expression",
                safety="safe",
            )
        ],
    )
    profile = {
        "version": 1,
        "avatarId": "avtr_existing",
        "approved": True,
        "actions": {
            "smile": {
                "label": "Smile",
                "cooldownMs": 0,
                "steps": [
                    {
                        "address": "/avatar/parameters/Smile",
                        "name": "Smile",
                        "type": "Bool",
                        "value": True,
                    }
                ],
            }
        },
    }
    store = AvatarActionProfileStore(tmp_path, {})
    bridge = Mock()
    safety = VrchatSafetyGate(global_rate_limit_per_second=100, default_action_cooldown_ms=0)

    result = await store.execute_action(
        action="smile",
        profile=profile,
        catalog=catalog,
        bridge=bridge,
        safety_gate=safety,
    )

    assert result["success"] is True
    bridge.send_parameter.assert_called_once_with("/avatar/parameters/Smile", True)


def test_avatar_registry_reports_missing_config_without_writing(tmp_path: Path) -> None:
    registry = VrchatAvatarRegistry(
        tmp_path,
        {"vrchat": {"avatarControl": {"oscConfigRoots": [str(tmp_path / "OSC")]}}},
    )

    assert registry.set_current_avatar("avtr_missing") is None
    assert registry.last_error == "avatar_config_not_found:avtr_missing"


def test_companion3d_rejects_remote_or_outside_model_paths(tmp_path: Path) -> None:
    bus = CompanionEventBus(
        tmp_path,
        {"desktopCompanion3d": {"assetRoot": "state/companion3d/assets"}},
    )

    with pytest.raises(ValueError, match="Remote companion3d model URLs"):
        bus.resolve_model_path("https://example.com/avatar.vrm")
    with pytest.raises(ValueError, match="assetRoot"):
        bus.resolve_model_path(str(tmp_path / "avatar.vrm"))

