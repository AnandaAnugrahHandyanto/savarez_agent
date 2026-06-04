import asyncio
import subprocess
from types import SimpleNamespace

from gateway.config import Platform
from gateway.discord_recovery import (
    build_recovery_message,
    extract_recovery_request,
    perform_recovery_if_requested,
)
from gateway.platforms.base import MessageEvent, SendResult
from gateway.session import SessionSource
from hermes_constants import set_hermes_home_override, reset_hermes_home_override


def _event(text, message_id="m1"):
    return MessageEvent(
        text=text,
        source=SessionSource(
            platform=Platform.DISCORD,
            user_id="u1",
            chat_id="1511658796219629628",
            chat_type="group",
        ),
        message_id=message_id,
    )


def test_extract_recovery_request_requires_explicit_slack_and_kanban_metadata():
    event = _event(
        "회수해줘 origin slack:C0B5USV2UKU:1780378250.786259 kanban ops-build/t_5dbbda34"
    )

    req = extract_recovery_request(event)

    assert req is not None
    assert req.slack_target == "slack:C0B5USV2UKU:1780378250.786259"
    assert req.kanban_target == "ops-build/t_5dbbda34"
    assert req.idempotency_key.startswith("discord-recovery-")


def test_extract_recovery_request_fail_closed_without_metadata_or_with_secret():
    assert extract_recovery_request(_event("이 메시지를 Slack/Kanban으로 회수해줘")) is None
    assert extract_recovery_request(
        _event(
            "회수 slack:C0B5USV2UKU:1780378250.786259 ops-build/t_5dbbda34 token=abc12345678901234567890"
        )
    ) is None


def test_build_recovery_message_is_bounded():
    event = _event(
        "recovery slack:C0B5USV2UKU:1780378250.786259 ops-build/t_5dbbda34"
    )
    req = extract_recovery_request(event)
    assert req is not None

    message = build_recovery_message(req, "x" * 1000)

    assert "[DISCORD-RECOVERY-AUTO]" in message
    assert "ops-build/t_5dbbda34" in message
    assert len(message) < 1100


class FakeSlackAdapter:
    def __init__(self):
        self.calls = []

    async def send(self, chat_id, content, metadata=None):
        self.calls.append((chat_id, content, metadata))
        return SendResult(success=True, message_id="slack-msg-1")


def test_perform_recovery_sends_slack_and_kanban_and_dedupes(monkeypatch, tmp_path):
    token = set_hermes_home_override(tmp_path)
    try:
        event = _event(
            "recovery slack:C0B5USV2UKU:1780378250.786259 ops-build/t_5dbbda34"
        )
        slack = FakeSlackAdapter()
        runner = SimpleNamespace(adapters={Platform.SLACK: slack})
        commands = []

        def fake_run(cmd, text, capture_output, timeout):
            commands.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="Comment added", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        first = asyncio.run(perform_recovery_if_requested(runner, event, "done"))
        second = asyncio.run(perform_recovery_if_requested(runner, event, "done again"))
        assert first is not None
        assert second is not None

        assert first["status"] == "pass"
        assert second["status"] == "duplicate"
        assert len(slack.calls) == 1
        assert slack.calls[0][0] == "C0B5USV2UKU"
        assert slack.calls[0][2] == {"thread_id": "1780378250.786259"}
        assert commands[0][:6] == ["hermes", "kanban", "--board", "ops-build", "comment", "t_5dbbda34"]
    finally:
        reset_hermes_home_override(token)
