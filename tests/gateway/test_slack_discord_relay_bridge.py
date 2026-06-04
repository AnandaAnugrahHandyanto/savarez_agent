import asyncio
import json
import subprocess
from types import SimpleNamespace

from gateway.config import Platform
from gateway.platforms.base import MessageEvent, SendResult
from gateway.session import SessionSource
from gateway.slack_discord_relay import (
    build_discord_relay_message,
    extract_relay_request,
    perform_relay_if_requested,
    _resolve_discord_send_target,
)
from hermes_constants import reset_hermes_home_override, set_hermes_home_override


def _event(text, message_id="s1"):
    return MessageEvent(
        text=text,
        source=SessionSource(
            platform=Platform.SLACK,
            user_id="u1",
            chat_id="C0B5USV2UKU",
            chat_type="group",
            thread_id="1780378250.786259",
        ),
        message_id=message_id,
    )


def test_extract_relay_request_requires_explicit_discord_and_kanban_metadata():
    event = _event("Discord로 중계해줘 discord:#agent-review-lab kanban hermes-ops/t_10c97641")

    req = extract_relay_request(event)

    assert req is not None
    assert req.discord_target == "#agent-review-lab"
    assert req.slack_target == "slack:C0B5USV2UKU:1780378250.786259"
    assert req.kanban_target == "hermes-ops/t_10c97641"
    assert req.idempotency_key.startswith("slack-discord-relay-")


def test_extract_relay_request_accepts_natural_discord_channel_handoff():
    event = _event("이 내용을 디스코드 #agent-review-lab로 넘겨줘. Kanban hermes-ops/t_10c97641")

    req = extract_relay_request(event)

    assert req is not None
    assert req.discord_target == "#agent-review-lab"
    assert req.kanban_target == "hermes-ops/t_10c97641"


def test_extract_relay_request_fail_closed_without_metadata_or_with_secret():
    assert extract_relay_request(_event("Discord로 이 내용을 전달해줘")) is None
    assert (
        extract_relay_request(
            _event(
                "전달 discord:#agent-review-lab hermes-ops/t_10c97641 token=abc12345678901234567890"
            )
        )
        is None
    )


def test_build_discord_relay_message_is_bounded():
    event = _event("relay discord:#agent-review-lab hermes-ops/t_10c97641")
    req = extract_relay_request(event)
    assert req is not None

    message = build_discord_relay_message(req, "x" * 2000)

    assert "[SLACK-DISCORD-RELAY-AUTO]" in message
    assert "hermes-ops/t_10c97641" in message
    assert "slack:C0B5USV2UKU:1780378250.786259" in message
    assert len(message) < 1300


class FakeDiscordAdapter:
    def __init__(self):
        self.calls = []

    async def send(self, chat_id, content, metadata=None):
        self.calls.append((chat_id, content, metadata))
        return SendResult(success=True, message_id="discord-msg-1")


def _write_discord_directory(tmp_path):
    (tmp_path / "channel_directory.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-06-04T00:00:00",
                "platforms": {
                    "discord": [
                        {
                            "id": "1511126777676693636",
                            "name": "agent-review-lab",
                            "guild": "Hermes Test",
                            "type": "channel",
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )


def test_resolve_discord_send_target_accepts_numeric_id_and_channel_name(tmp_path):
    token = set_hermes_home_override(tmp_path)
    try:
        _write_discord_directory(tmp_path)

        assert _resolve_discord_send_target("1511126777676693636") == "1511126777676693636"
        assert _resolve_discord_send_target("#agent-review-lab") == "1511126777676693636"
    finally:
        reset_hermes_home_override(token)


def test_perform_relay_sends_discord_and_kanban_and_dedupes(monkeypatch, tmp_path):
    token = set_hermes_home_override(tmp_path)
    try:
        event = _event("relay discord:#agent-review-lab hermes-ops/t_10c97641")
        _write_discord_directory(tmp_path)
        discord = FakeDiscordAdapter()
        runner = SimpleNamespace(adapters={Platform.DISCORD: discord})
        commands = []

        def fake_run(cmd, text, capture_output, timeout):
            commands.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="Comment added", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        first = asyncio.run(perform_relay_if_requested(runner, event, "done"))
        second = asyncio.run(perform_relay_if_requested(runner, event, "done again"))
        assert first is not None
        assert second is not None

        assert first["status"] == "pass"
        assert second["status"] == "duplicate"
        assert len(discord.calls) == 1
        assert discord.calls[0][0] == "1511126777676693636"
        assert commands[0][:6] == ["hermes", "kanban", "--board", "hermes-ops", "comment", "t_10c97641"]
    finally:
        reset_hermes_home_override(token)
