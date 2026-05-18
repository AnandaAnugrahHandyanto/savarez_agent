"""Tests for tools.openclaw.vrchat_avatar_registry."""

from __future__ import annotations

import json
from pathlib import Path

from tools.openclaw.vrchat_avatar_registry import (
    discover_avatar_config_file,
    parse_avatar_config,
)


def _write_avatar_config(path: Path, avatar_id: str = "avtr_existing") -> None:
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
                ],
            }
        ),
        encoding="utf-8",
    )


def test_discovers_avatar_config_by_avatar_id(tmp_path: Path) -> None:
    root = tmp_path / "OSC"
    config_path = root / "usr_abc" / "Avatars" / "avtr_existing.json"
    _write_avatar_config(config_path)

    found = discover_avatar_config_file(
        "avtr_existing",
        config={"vrchat": {"avatarControl": {"oscConfigRoots": [str(root)]}}},
        repo_root=tmp_path,
    )

    assert found == config_path


def test_parse_catalog_marks_blocked_parameters(tmp_path: Path) -> None:
    config_path = tmp_path / "avatar.json"
    _write_avatar_config(config_path)

    catalog = parse_avatar_config(config_path, expected_avatar_id="avtr_existing")

    smile = next(p for p in catalog.parameters if p.name == "Smile")
    afk = next(p for p in catalog.parameters if p.name == "AFK")
    assert smile.safety == "safe"
    assert afk.safety == "blocked"
