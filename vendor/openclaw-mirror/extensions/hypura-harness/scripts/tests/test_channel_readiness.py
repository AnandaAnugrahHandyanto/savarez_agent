from __future__ import annotations

import json
import time
from pathlib import Path

from channel_readiness import build_channel_readiness


LINE_USER_ID = "U1234567890abcdef1234567890abcdef"
LINE_GROUP_ID = "C1234567890abcdef1234567890abcdef"


def write_config(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_channel_readiness_reports_missing_line_target_without_secret_values(tmp_path: Path) -> None:
    config_path = tmp_path / "openclaw.json"
    write_config(
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
    assert result["channels"]["line"]["credentialPresence"] == {
        "channelAccessToken": True,
        "channelSecret": True,
    }
    assert result["channels"]["line"]["candidateTargets"] == {
        "directUsers": 0,
        "groups": 0,
        "rooms": 0,
    }
    assert result["channels"]["line"]["liveRoundtripReady"] is False
    serialized = json.dumps(result)
    assert "line-secret-token" not in serialized
    assert "line-channel-secret" not in serialized
    assert "telegram-secret-token" not in serialized


def test_channel_readiness_counts_line_and_telegram_live_targets(tmp_path: Path) -> None:
    config_path = tmp_path / "openclaw.json"
    write_config(
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
    assert result["channels"]["line"]["candidateTargets"] == {
        "directUsers": 1,
        "groups": 1,
        "rooms": 0,
    }
    assert result["channels"]["telegram"]["candidateTargets"] == {
        "directChats": 1,
        "groupChats": 1,
    }


def test_channel_readiness_counts_allow_from_store_targets(tmp_path: Path) -> None:
    config_path = tmp_path / "openclaw.json"
    credentials_dir = tmp_path / "credentials"
    credentials_dir.mkdir()
    write_config(
        config_path,
        {
            "channels": {
                "line": {
                    "channelAccessToken": "line-secret-token",
                    "channelSecret": "line-channel-secret",
                },
                "telegram": {"botToken": "telegram-secret-token"},
            }
        },
    )
    write_config(
        credentials_dir / "line-default-allowFrom.json",
        {"version": 1, "allowFrom": [LINE_USER_ID]},
    )
    write_config(
        credentials_dir / "telegram-default-allowFrom.json",
        {"version": 1, "allowFrom": ["123456789"]},
    )

    result = build_channel_readiness(config_path, tmp_path)

    assert result["liveRoundtripReady"] == {"line": True, "telegram": True}
    assert result["channels"]["line"]["candidateTargets"]["directUsers"] == 1
    assert result["channels"]["telegram"]["candidateTargets"]["directChats"] == 1
    serialized = json.dumps(result)
    assert LINE_USER_ID not in serialized
    assert "123456789" not in serialized


def test_channel_readiness_counts_recent_telegram_sent_message_history_targets(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "openclaw.json"
    sessions_dir = tmp_path / "agents" / "main" / "sessions"
    sessions_dir.mkdir(parents=True)
    write_config(
        config_path,
        {
            "channels": {
                "telegram": {"botToken": "telegram-secret-token"},
            }
        },
    )
    write_config(
        sessions_dir / "sessions.json.telegram-sent-messages.json",
        {"123456789": {"10": int(time.time() * 1000)}},
    )

    result = build_channel_readiness(config_path, tmp_path)

    assert result["liveRoundtripReady"]["telegram"] is True
    assert result["channels"]["telegram"]["candidateTargets"] == {
        "directChats": 1,
        "groupChats": 0,
    }
    serialized = json.dumps(result)
    assert "123456789" not in serialized
    assert "telegram-secret-token" not in serialized


def test_channel_readiness_counts_session_route_targets_without_printing_values(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "openclaw.json"
    sessions_dir = tmp_path / "agents" / "main" / "sessions"
    sessions_dir.mkdir(parents=True)
    write_config(
        config_path,
        {
            "channels": {
                "line": {
                    "channelAccessToken": "line-secret-token",
                    "channelSecret": "line-channel-secret",
                },
                "telegram": {"botToken": "telegram-secret-token"},
            }
        },
    )
    write_config(
        sessions_dir / "sessions.json",
        {
            "line-session": {
                "channel": "line",
                "origin": {"to": f"line:user:{LINE_USER_ID}"},
                "deliveryContext": {"channel": "line", "to": f"line:group:{LINE_GROUP_ID}"},
            },
            "telegram-session": {
                "channel": "telegram",
                "deliveryContext": {"channel": "telegram", "to": "telegram:-1001234567890"},
            },
        },
    )

    result = build_channel_readiness(config_path, tmp_path)

    assert result["liveRoundtripReady"] == {"line": True, "telegram": True}
    assert result["channels"]["line"]["candidateTargets"] == {
        "directUsers": 1,
        "groups": 1,
        "rooms": 0,
    }
    assert result["channels"]["telegram"]["candidateTargets"] == {
        "directChats": 0,
        "groupChats": 1,
    }
    serialized = json.dumps(result)
    assert LINE_USER_ID not in serialized
    assert LINE_GROUP_ID not in serialized
    assert "-1001234567890" not in serialized
    assert "line-secret-token" not in serialized
    assert "telegram-secret-token" not in serialized


def test_channel_readiness_parses_jsonc_without_printing_values(tmp_path: Path) -> None:
    config_path = tmp_path / "openclaw.json"
    config_path.write_text(
        """
        {
          // local desktop config
          "channels": {
            "line": {
              "channelAccessToken": "line-secret-token",
              "channelSecret": "line-channel-secret",
              "allowFrom": ["U1234567890abcdef1234567890abcdef",],
            },
            "telegram": {
              "botToken": "telegram-secret-token",
              "groups": {
                "-1001234567890": {},
              },
            },
          },
        }
        """,
        encoding="utf-8",
    )

    result = build_channel_readiness(config_path, tmp_path)

    assert result["success"] is True
    assert result["channels"]["line"]["liveRoundtripReady"] is True
    assert result["channels"]["telegram"]["liveRoundtripReady"] is True
    serialized = json.dumps(result)
    assert LINE_USER_ID not in serialized
    assert "-1001234567890" not in serialized
