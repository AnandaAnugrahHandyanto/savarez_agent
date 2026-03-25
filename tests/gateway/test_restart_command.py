"""Tests for /restart gateway slash command."""

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from gateway.config import Platform
from gateway.platforms.base import MessageEvent, SendResult
from gateway.session import SessionSource


def _make_event(text="/restart", platform=Platform.TELEGRAM,
                user_id="12345", chat_id="67890", thread_id=None):
    source = SessionSource(
        platform=platform,
        user_id=user_id,
        chat_id=chat_id,
        user_name="testuser",
        thread_id=thread_id,
    )
    return MessageEvent(text=text, source=source)


def _make_runner():
    from gateway.run import GatewayRunner
    runner = object.__new__(GatewayRunner)
    runner.adapters = {}
    runner._voice_mode = {}
    return runner


def _make_adapter():
    adapter = AsyncMock()
    adapter.send.return_value = SendResult(success=True, message_id="msg-1")
    return adapter


class TestHandleRestartCommand:
    @pytest.mark.asyncio
    async def test_sends_ack_then_spawns_detached_restart_and_writes_marker(self, tmp_path):
        runner = _make_runner()
        event = _make_event(platform=Platform.TELEGRAM, chat_id="99999", thread_id="topic-7")
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()

        mock_popen = MagicMock()
        mock_adapter = _make_adapter()
        runner.adapters = {Platform.TELEGRAM: mock_adapter}

        def fake_which(name):
            if name == "systemd-run":
                return "/usr/bin/systemd-run"
            if name == "systemctl":
                return "/usr/bin/systemctl"
            return None

        with patch("gateway.run._hermes_home", hermes_home), \
             patch("shutil.which", side_effect=fake_which), \
             patch("hermes_cli.gateway.get_service_name", return_value="hermes-gateway"), \
             patch("subprocess.Popen", mock_popen):
            result = await runner._handle_restart_command(event)

        assert result is None
        pending_path = hermes_home / ".restart_pending.json"
        assert pending_path.exists()
        data = json.loads(pending_path.read_text())
        assert data["platform"] == "telegram"
        assert data["chat_id"] == "99999"
        assert data["thread_id"] == "topic-7"

        mock_adapter.send.assert_called_once_with(
            chat_id="99999",
            content="↻ Restarting gateway… I'll message again when I'm back.",
            reply_to=event.message_id,
            metadata={"thread_id": "topic-7"},
        )

        call_args = mock_popen.call_args[0][0]
        assert call_args[:5] == [
            "/usr/bin/systemd-run",
            "--user",
            "--scope",
            "--unit=hermes-restart",
            "--",
        ]
        assert call_args[5:] == [
            "/usr/bin/systemctl",
            "--user",
            "restart",
            "hermes-gateway",
        ]

    @pytest.mark.asyncio
    async def test_refuses_inline_restart_when_systemd_run_missing(self, tmp_path):
        runner = _make_runner()
        event = _make_event()
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()
        mock_adapter = _make_adapter()
        runner.adapters = {Platform.TELEGRAM: mock_adapter}

        def fake_which(name):
            if name == "systemctl":
                return "/usr/bin/systemctl"
            return None

        with patch("gateway.run._hermes_home", hermes_home), \
             patch("shutil.which", side_effect=fake_which), \
             patch("subprocess.Popen") as mock_popen:
            result = await runner._handle_restart_command(event)

        assert "safe in-chat restart is unavailable" in result.lower()
        mock_popen.assert_not_called()
        mock_adapter.send.assert_not_called()
        assert not (hermes_home / ".restart_pending.json").exists()

    @pytest.mark.asyncio
    async def test_aborts_restart_if_ack_send_fails(self, tmp_path):
        runner = _make_runner()
        event = _make_event(platform=Platform.TELEGRAM, chat_id="99999", thread_id="topic-7")
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()

        mock_adapter = _make_adapter()
        mock_adapter.send.return_value = SendResult(success=False, error="network down")
        runner.adapters = {Platform.TELEGRAM: mock_adapter}

        def fake_which(name):
            if name == "systemd-run":
                return "/usr/bin/systemd-run"
            if name == "systemctl":
                return "/usr/bin/systemctl"
            return None

        with patch("gateway.run._hermes_home", hermes_home), \
             patch("shutil.which", side_effect=fake_which), \
             patch("hermes_cli.gateway.get_service_name", return_value="hermes-gateway"), \
             patch("subprocess.Popen") as mock_popen:
            result = await runner._handle_restart_command(event)

        assert "failed to send restart acknowledgement" in result.lower()
        mock_popen.assert_not_called()
        assert not (hermes_home / ".restart_pending.json").exists()


class TestSendRestartNotification:
    @pytest.mark.asyncio
    async def test_sends_restart_notification_and_cleans_up_marker(self, tmp_path):
        runner = _make_runner()
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()
        pending_path = hermes_home / ".restart_pending.json"
        pending_path.write_text(json.dumps({
            "platform": "telegram",
            "chat_id": "111",
            "user_id": "222",
            "thread_id": "topic-9",
        }))

        mock_adapter = _make_adapter()
        runner.adapters = {Platform.TELEGRAM: mock_adapter}

        with patch("gateway.run._hermes_home", hermes_home):
            result = await runner._send_restart_notification()

        assert result is True
        mock_adapter.send.assert_called_once()
        assert mock_adapter.send.call_args[0][0] == "111"
        assert "restarted successfully" in mock_adapter.send.call_args[0][1].lower()
        assert mock_adapter.send.call_args[1]["reply_to"] is None
        assert mock_adapter.send.call_args[1]["metadata"] == {"thread_id": "topic-9"}
        assert not pending_path.exists()

    @pytest.mark.asyncio
    async def test_keeps_marker_when_send_fails_for_retry(self, tmp_path):
        runner = _make_runner()
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()
        pending_path = hermes_home / ".restart_pending.json"
        pending_path.write_text(json.dumps({
            "platform": "telegram",
            "chat_id": "111",
            "user_id": "222",
            "thread_id": "topic-9",
        }))

        mock_adapter = AsyncMock()
        mock_adapter.send.side_effect = RuntimeError("send failed")
        runner.adapters = {Platform.TELEGRAM: mock_adapter}

        with patch("gateway.run._hermes_home", hermes_home):
            result = await runner._send_restart_notification()

        assert result is False
        mock_adapter.send.assert_called_once()
        assert pending_path.exists()


class TestRestartCommandRegistration:
    @pytest.mark.asyncio
    async def test_restart_in_help_output(self):
        runner = _make_runner()
        event = _make_event(text="/help")
        result = await runner._handle_help_command(event)
        assert "/restart" in result

    def test_restart_is_registered_command(self):
        from hermes_cli.commands import resolve_command

        cmd = resolve_command("restart")
        assert cmd is not None
        assert cmd.name == "restart"
        assert cmd.gateway_only is True
