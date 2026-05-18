"""Tests for tools.openclaw.channel_readiness (ported from hypura-harness)."""

from __future__ import annotations

import json
from pathlib import Path

from tools.openclaw.channel_readiness import build_channel_readiness

LINE_USER_ID = "U1234567890abcdef1234567890abcdef"
LINE_GROUP_ID = "C1234567890abcdef1234567890abcdef"


def _write_config(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_channel_readiness_reports_missing_line_target_without_secret_values(tmp_path: Path) -> None:
    config_path = tmp_path / "openclaw.json"
    _write_config(
        config_path,
        {
            "channels": {
                "line": {
                    "channelAccessToken": "line-secret-token",
                    "channelSecret": "line-channel-secret",
                    "groups": {"custom-1": {"enabled": True}},
                },
                "telegram": {"botToken": "telegram-secret-token"},
            }
        },
    )

    result = build_channel_readiness(config_path, tmp_path)

    assert result["success"] is True
    assert result["channels"]["line"]["liveRoundtripReady"] is False
    serialized = json.dumps(result)
    assert "line-secret-token" not in serialized
    assert "telegram-secret-token" not in serialized


def test_channel_readiness_counts_line_and_telegram_live_targets(tmp_path: Path) -> None:
    config_path = tmp_path / "openclaw.json"
    _write_config(
        config_path,
        {
            "channels": {
                "line": {
                    "channelAccessToken": "line-secret-token",
                    "channelSecret": "line-channel-secret",
                    "allowFrom": [LINE_USER_ID],
                    "groups": {LINE_GROUP_ID: {"enabled": True}},
                },
                "telegram": {
                    "botToken": "telegram-secret-token",
                    "allowFrom": ["123456789"],
                    "groups": {"-1001234567890": {"requireMention": True}},
                },
            }
        },
    )

    result = build_channel_readiness(config_path, tmp_path)

    assert result["liveRoundtripReady"] == {"line": True, "telegram": True}
    assert result["channels"]["line"]["candidateTargets"]["directUsers"] == 1
