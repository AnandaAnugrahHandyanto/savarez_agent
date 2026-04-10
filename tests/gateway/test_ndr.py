"""Tests for the NDR (nostr-double-ratchet) gateway adapter."""

import asyncio
import json
import stat
import textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig, _apply_env_overrides


def _make_ndr_adapter(**extra):
    from gateway.platforms.ndr import NdrAdapter

    config = PlatformConfig(enabled=True, extra={"bin": "ndr", **extra})
    return NdrAdapter(config)


def _real_ndr_binary() -> Path | None:
    candidate = Path("/tmp/nostr-double-ratchet/rust/target/debug/ndr")
    return candidate if candidate.exists() else None


def _real_ndr_data_dir(name: str) -> Path | None:
    candidate = Path(f"/tmp/{name}")
    return candidate if candidate.exists() else None


def _require_real_ndr_contract() -> tuple[Path, Path, Path]:
    binary = _real_ndr_binary()
    logged_in = _real_ndr_data_dir("ndr-hermes-probe")
    logged_out = _real_ndr_data_dir("ndr-hermes-empty")
    if not binary or not logged_in or not logged_out:
        pytest.skip("real ndr contract fixtures are not available locally")
    return binary, logged_in, logged_out


def _write_fake_ndr_cli(tmp_path: Path) -> Path:
    script = tmp_path / "fake_ndr.py"
    script.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import os
            import sys
            import time
            from pathlib import Path

            def emit(payload, stream=sys.stdout):
                stream.write(json.dumps(payload) + "\\n")
                stream.flush()

            argv = sys.argv[1:]
            if argv and argv[0] == "--json":
                argv = argv[1:]
            if not argv:
                emit({"status": "error", "command": "", "error": "missing command"}, sys.stderr)
                sys.exit(1)

            command = argv[0]
            data_dir = Path(os.environ["NDR_DATA_DIR"])
            data_dir.mkdir(parents=True, exist_ok=True)
            send_log = data_dir / "send-log.jsonl"

            if command == "whoami":
                emit({
                    "status": "ok",
                    "command": "whoami",
                    "data": {
                        "logged_in": True,
                        "pubkey": "our-pubkey",
                        "npub": "npub1ours",
                    },
                })
                sys.exit(0)

            if command == "send":
                target = argv[1]
                content = argv[2]
                with send_log.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"target": target, "content": content}) + "\\n")
                emit({
                    "status": "ok",
                    "command": "send",
                    "data": {"id": "msg-send-1", "chat_id": target},
                })
                sys.exit(0)

            if command == "listen":
                emit({
                    "status": "ok",
                    "command": "listen",
                    "data": {"message": "Listening for messages and invite responses"},
                })
                emit({
                    "event": "message",
                    "chat_id": "chat-from-script",
                    "message_id": "msg-in-1",
                    "from_pubkey": "peer-pubkey",
                    "content": "hello from fake ndr",
                    "timestamp": 1710000000,
                })
                time.sleep(0.2)
                sys.exit(0)

            emit({"status": "error", "command": command, "error": "unsupported command"}, sys.stderr)
            sys.exit(1)
            """
        ),
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


async def _wait_for_async_mock_calls(mock: AsyncMock, count: int = 1, timeout: float = 1.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while mock.await_count < count:
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"expected {count} awaited calls, saw {mock.await_count}")
        await asyncio.sleep(0.01)


class _FakeReader:
    def __init__(self, lines):
        self._lines = [line if isinstance(line, bytes) else line.encode("utf-8") for line in lines]

    async def readline(self):
        if self._lines:
            return self._lines.pop(0)
        return b""


class _FakeProcess:
    def __init__(self, stdout_lines=None, stderr_lines=None, wait_returncode=0):
        self.stdout = _FakeReader(stdout_lines or [])
        self.stderr = _FakeReader(stderr_lines or [])
        self.returncode = None
        self.terminated = False
        self._wait_returncode = wait_returncode

    def terminate(self):
        self.terminated = True
        self.returncode = self._wait_returncode

    async def wait(self):
        self.returncode = self._wait_returncode
        return self._wait_returncode


class _FakeCommandProcess:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        self._stdout = stdout.encode("utf-8")
        self._stderr = stderr.encode("utf-8")
        self.returncode = returncode
        self.killed = False

    async def communicate(self):
        return self._stdout, self._stderr

    def kill(self):
        self.killed = True


class _SlowCommandProcess(_FakeCommandProcess):
    def __init__(self):
        super().__init__()

    async def communicate(self):
        await asyncio.sleep(0.05)
        return self._stdout, self._stderr


class TestNdrPlatformEnum:
    def test_ndr_enum_exists(self):
        assert Platform.NDR.value == "ndr"


class TestNdrConfigLoading:
    def test_apply_env_overrides_ndr(self, monkeypatch):
        monkeypatch.setenv("NDR_ENABLED", "true")
        monkeypatch.setenv("NDR_BIN", "/usr/local/bin/ndr")
        monkeypatch.setenv("NDR_HOME_CHANNEL", "chat-123")

        config = GatewayConfig()
        _apply_env_overrides(config)

        assert Platform.NDR in config.platforms
        ndr = config.platforms[Platform.NDR]
        assert ndr.enabled is True
        assert ndr.extra["bin"] == "/usr/local/bin/ndr"
        assert ndr.home_channel.chat_id == "chat-123"

    def test_connected_platforms_includes_ndr(self, monkeypatch):
        monkeypatch.setenv("NDR_ENABLED", "true")
        monkeypatch.setenv("NDR_BIN", "/usr/local/bin/ndr")

        config = GatewayConfig()
        _apply_env_overrides(config)

        assert Platform.NDR in config.get_connected_platforms()


class TestNdrRequirements:
    def test_check_requirements_uses_which(self):
        from gateway.platforms.ndr import check_ndr_requirements

        with patch("gateway.platforms.ndr.shutil.which", return_value="/usr/bin/ndr"):
            assert check_ndr_requirements() is True

    def test_check_requirements_missing_binary(self):
        from gateway.platforms.ndr import check_ndr_requirements

        with patch("gateway.platforms.ndr.shutil.which", return_value=None):
            assert check_ndr_requirements() is False


class TestNdrStandaloneSend:
    @pytest.mark.asyncio
    async def test_send_ndr_message_requires_logged_in_identity(self):
        from gateway.platforms.ndr import send_ndr_message

        with patch(
            "gateway.platforms.ndr.run_ndr_json_command",
            new=AsyncMock(
                return_value={"status": "ok", "command": "whoami", "data": {"logged_in": False, "npub": ""}}
            ),
        ):
            result = await send_ndr_message("chat-123", "hello", extra={"bin": "ndr", "data_dir": "/tmp/ndr"})

        assert result.success is False
        assert "ndr is not logged in" in (result.error or "")

    @pytest.mark.asyncio
    async def test_send_ndr_message_sends_without_starting_listener(self):
        from gateway.platforms.ndr import send_ndr_message

        run_mock = AsyncMock(
            side_effect=[
                {"status": "ok", "command": "whoami", "data": {"logged_in": True, "npub": "npub1ours"}},
                {"status": "ok", "command": "send", "data": {"id": "msg-123", "chat_id": "chat-123"}},
            ]
        )

        with patch("gateway.platforms.ndr.run_ndr_json_command", new=run_mock):
            result = await send_ndr_message("chat-123", "hello", extra={"bin": "ndr", "data_dir": "/tmp/ndr"})

        assert result.success is True
        assert result.message_id == "msg-123"
        assert run_mock.await_args_list[0].args == ("whoami",)
        assert run_mock.await_args_list[1].args == ("send", "chat-123", "hello")
        assert run_mock.await_args_list[1].kwargs["timeout"] == 120.0

    def test_resolve_ndr_send_timeout_prefers_extra_then_env(self, monkeypatch):
        from gateway.platforms.ndr import resolve_ndr_send_timeout

        monkeypatch.setenv("NDR_SEND_TIMEOUT", "75")
        assert resolve_ndr_send_timeout({}) == 75.0
        assert resolve_ndr_send_timeout({"send_timeout": "150"}) == 150.0
        assert resolve_ndr_send_timeout({"send_timeout": "not-a-number"}) == 120.0


class TestNdrAdapter:
    def test_init_defaults_to_profile_safe_data_dir(self):
        adapter = _make_ndr_adapter()
        assert adapter.ndr_bin == "ndr"
        assert adapter.data_dir.name == "ndr"
        assert adapter.data_dir.parent.name == "platforms"

    @pytest.mark.asyncio
    async def test_connect_requires_logged_in_identity(self):
        adapter = _make_ndr_adapter()

        with patch("gateway.platforms.ndr.check_ndr_requirements", return_value=True), patch.object(
            adapter,
            "_run_json_command",
            new=AsyncMock(return_value={"status": "ok", "command": "whoami", "data": {"logged_in": False}}),
        ):
            connected = await adapter.connect()

        assert connected is False
        assert adapter.has_fatal_error
        assert adapter.fatal_error_code == "ndr_login_required"

    @pytest.mark.asyncio
    async def test_handle_message_event_dispatches_to_handler(self):
        adapter = _make_ndr_adapter()
        adapter.handle_message = AsyncMock()

        await adapter._handle_listen_payload(
            {
                "event": "message",
                "chat_id": "chat-123",
                "message_id": "msg-1",
                "from_pubkey": "abcdef1234",
                "content": "hello from ndr",
                "timestamp": 1710000000,
            }
        )

        adapter.handle_message.assert_awaited_once()
        event = adapter.handle_message.await_args.args[0]
        assert event.text == "hello from ndr"
        assert event.message_id == "msg-1"
        assert event.source.platform == Platform.NDR
        assert event.source.chat_id == "chat-123"
        assert event.source.user_id == "abcdef1234"

    @pytest.mark.asyncio
    async def test_handle_startup_status_payload_is_ignored(self):
        adapter = _make_ndr_adapter()
        adapter.handle_message = AsyncMock()

        await adapter._handle_listen_payload(
            {
                "status": "ok",
                "command": "listen",
                "data": {"message": "Listening for messages"},
            }
        )

        adapter.handle_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handle_non_message_event_is_ignored(self):
        adapter = _make_ndr_adapter()
        adapter.handle_message = AsyncMock()

        await adapter._handle_listen_payload(
            {
                "event": "typing",
                "chat_id": "chat-123",
                "from_pubkey": "abcdef1234",
                "timestamp": 1710000000,
            }
        )

        adapter.handle_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handle_self_message_event_is_ignored(self):
        adapter = _make_ndr_adapter()
        adapter.handle_message = AsyncMock()
        adapter.identity = {"pubkey": "abcdef1234"}

        await adapter._handle_listen_payload(
            {
                "event": "message",
                "chat_id": "chat-123",
                "message_id": "msg-1",
                "from_pubkey": "abcdef1234",
                "content": "hello from self",
                "timestamp": 1710000000,
            }
        )

        adapter.handle_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_process_line_skips_malformed_json(self):
        adapter = _make_ndr_adapter()
        adapter.handle_message = AsyncMock()

        await adapter._process_listen_line("{not-json")

        adapter.handle_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_uses_chat_id_target(self):
        adapter = _make_ndr_adapter()
        adapter.identity = {"npub": "npub1test"}

        with patch.object(
            adapter,
            "_run_json_command",
            new=AsyncMock(
                return_value={
                    "status": "ok",
                    "command": "send",
                    "data": {"chat_id": "chat-123", "id": "msg-123"},
                }
            ),
        ) as run_mock:
            result = await adapter.send("chat-123", "hello")

        assert result.success is True
        assert result.message_id == "msg-123"
        run_mock.assert_awaited_once_with("send", "chat-123", "hello", timeout=120.0)

    @pytest.mark.asyncio
    async def test_connect_starts_listen_loop_and_dispatches_message(self):
        adapter = _make_ndr_adapter()
        adapter.handle_message = AsyncMock()
        listen_proc = _FakeProcess(
            stdout_lines=[
                '{"status":"ok","command":"listen","data":{"message":"Listening"}}\n',
                '{"event":"message","chat_id":"chat-123","message_id":"msg-1","from_pubkey":"abcdef1234","content":"hi","timestamp":1710000000}\n',
            ]
        )

        with patch("gateway.platforms.ndr.check_ndr_requirements", return_value=True), patch.object(
            adapter,
            "_run_json_command",
            new=AsyncMock(
                return_value={
                    "status": "ok",
                    "command": "whoami",
                    "data": {"logged_in": True, "pubkey": "our-pubkey", "npub": "npub1ours"},
                }
            ),
        ), patch("gateway.status.acquire_scoped_lock", return_value=(True, None)), patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=listen_proc),
        ):
            connected = await adapter.connect()
            assert connected is True
            await adapter._listen_task
            await adapter.disconnect()

        adapter.handle_message.assert_awaited_once()
        event = adapter.handle_message.await_args.args[0]
        assert event.text == "hi"
        assert event.source.chat_id == "chat-123"
        assert event.source.user_id == "abcdef1234"

    @pytest.mark.asyncio
    async def test_connect_fails_when_listen_exits_before_startup(self):
        adapter = _make_ndr_adapter()
        listen_proc = _FakeProcess(stderr_lines=["fatal listen error\n"], wait_returncode=1)

        with patch("gateway.platforms.ndr.check_ndr_requirements", return_value=True), patch.object(
            adapter,
            "_run_json_command",
            new=AsyncMock(
                return_value={
                    "status": "ok",
                    "command": "whoami",
                    "data": {"logged_in": True, "pubkey": "our-pubkey", "npub": "npub1ours"},
                }
            ),
        ), patch("gateway.status.acquire_scoped_lock", return_value=(True, None)), patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=listen_proc),
        ):
            connected = await adapter.connect()

        assert connected is False
        assert adapter.has_fatal_error
        assert adapter.fatal_error_code == "ndr_listen_start_failed"
        assert "fatal listen error" in (adapter.fatal_error_message or "")

    @pytest.mark.asyncio
    async def test_connect_fails_when_listen_startup_payload_is_error(self):
        adapter = _make_ndr_adapter()
        listen_proc = _FakeProcess(
            stdout_lines=['{"status":"error","command":"listen","error":"login required"}\n'],
            wait_returncode=1,
        )

        with patch("gateway.platforms.ndr.check_ndr_requirements", return_value=True), patch.object(
            adapter,
            "_run_json_command",
            new=AsyncMock(
                return_value={
                    "status": "ok",
                    "command": "whoami",
                    "data": {"logged_in": True, "pubkey": "our-pubkey", "npub": "npub1ours"},
                }
            ),
        ), patch("gateway.status.acquire_scoped_lock", return_value=(True, None)), patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=listen_proc),
        ):
            connected = await adapter.connect()

        assert connected is False
        assert adapter.has_fatal_error
        assert adapter.fatal_error_code == "ndr_listen_start_failed"
        assert "login required" in (adapter.fatal_error_message or "")

    @pytest.mark.asyncio
    async def test_send_surfaces_json_error_even_without_command_name(self):
        adapter = _make_ndr_adapter()

        with patch.object(
            adapter,
            "_run_json_command",
            new=AsyncMock(
                return_value={
                    "status": "error",
                    "command": "",
                    "error": "Target is not a pubkey or contact",
                }
            ),
        ):
            result = await adapter.send("npub1badtarget", "hello")

        assert result.success is False
        assert "Target is not a pubkey or contact" in (result.error or "")

    @pytest.mark.asyncio
    async def test_run_json_command_parses_structured_stderr(self):
        adapter = _make_ndr_adapter(bin="/usr/local/bin/ndr")
        proc = _FakeCommandProcess(
            stderr='{"status":"error","command":"","error":"Target is not a pubkey or contact"}\n',
            returncode=1,
        )

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
            payload = await adapter._run_json_command("send", "npub1bad", "hello")

        assert payload["status"] == "error"
        assert payload["error"] == "Target is not a pubkey or contact"

    @pytest.mark.asyncio
    async def test_run_json_command_times_out(self):
        adapter = _make_ndr_adapter(bin="/usr/local/bin/ndr")
        proc = _SlowCommandProcess()

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
            payload = await adapter._run_json_command("whoami", timeout=0.01)

        assert payload["status"] == "error"
        assert "timed out" in payload["error"]
        assert proc.killed is True


class TestNdrAuthorization:
    def test_ndr_in_allowlist_maps(self):
        from gateway.run import GatewayRunner

        gw = GatewayRunner.__new__(GatewayRunner)
        gw.config = GatewayConfig()
        gw.pairing_store = MagicMock()
        gw.pairing_store.is_approved.return_value = False

        source = MagicMock()
        source.platform = Platform.NDR
        source.user_id = "abcdef1234"

        with patch.dict("os.environ", {}, clear=True):
            assert gw._is_user_authorized(source) is False


class TestNdrGatewayRunner:
    def test_create_adapter_returns_ndr_adapter(self):
        from gateway.run import GatewayRunner

        gw = GatewayRunner.__new__(GatewayRunner)
        gw.config = GatewayConfig()
        config = PlatformConfig(enabled=True, extra={"bin": "/usr/local/bin/ndr"})

        with patch("gateway.platforms.ndr.check_ndr_requirements", return_value=True):
            adapter = gw._create_adapter(Platform.NDR, config)

        assert adapter is not None
        assert adapter.platform == Platform.NDR


class TestNdrTooling:
    def test_toolset_exists(self):
        from toolsets import TOOLSETS

        assert "hermes-ndr" in TOOLSETS
        assert "hermes-ndr" in TOOLSETS["hermes-gateway"]["includes"]

    def test_platform_hint_exists(self):
        from agent.prompt_builder import PLATFORM_HINTS

        hint = PLATFORM_HINTS["ndr"]
        assert "double-ratchet" in hint.lower()
        assert "plain text" in hint.lower()


class TestRealNdrContract:
    @pytest.mark.asyncio
    async def test_real_whoami_reports_logged_in_identity(self):
        binary, logged_in, _logged_out = _require_real_ndr_contract()
        adapter = _make_ndr_adapter(bin=str(binary), data_dir=str(logged_in))

        payload = await adapter._run_json_command("whoami", timeout=10.0)

        assert payload["status"] == "ok"
        assert payload["command"] == "whoami"
        assert payload["data"]["logged_in"] is True
        assert payload["data"]["npub"].startswith("npub1")

    @pytest.mark.asyncio
    async def test_real_whoami_reports_logged_out_identity(self):
        binary, _logged_in, logged_out = _require_real_ndr_contract()
        adapter = _make_ndr_adapter(bin=str(binary), data_dir=str(logged_out))

        payload = await adapter._run_json_command("whoami", timeout=10.0)

        assert payload["status"] == "ok"
        assert payload["command"] == "whoami"
        assert payload["data"]["logged_in"] is False
        assert payload["data"]["npub"] == ""

    @pytest.mark.asyncio
    async def test_real_send_surfaces_structured_json_error(self):
        binary, logged_in, _logged_out = _require_real_ndr_contract()
        adapter = _make_ndr_adapter(bin=str(binary), data_dir=str(logged_in))

        payload = await adapter._run_json_command("send", "npub1notarealtarget", "hello", timeout=10.0)

        assert payload["status"] == "error"
        assert "target is not a pubkey or contact" in payload["error"].lower()

    @pytest.mark.asyncio
    async def test_real_connect_starts_and_stops_listen(self):
        binary, logged_in, _logged_out = _require_real_ndr_contract()
        adapter = _make_ndr_adapter(bin=str(binary), data_dir=str(logged_in))

        with patch("gateway.status.acquire_scoped_lock", return_value=(True, None)), patch(
            "gateway.status.release_scoped_lock",
            return_value=None,
        ):
            connected = await adapter.connect()
            try:
                assert connected is True
                assert adapter.identity["logged_in"] is True
                assert adapter.identity["npub"].startswith("npub1")
                assert adapter._listen_process is not None
            finally:
                if connected:
                    await adapter.disconnect()


class TestNdrSubprocessIntegration:
    @pytest.mark.asyncio
    async def test_fake_cli_roundtrip_dispatches_and_sends(self, tmp_path):
        binary = _write_fake_ndr_cli(tmp_path)
        data_dir = tmp_path / "ndr-data"
        adapter = _make_ndr_adapter(bin=str(binary), data_dir=str(data_dir))
        adapter.handle_message = AsyncMock()

        with patch("gateway.status.acquire_scoped_lock", return_value=(True, None)), patch(
            "gateway.status.release_scoped_lock",
            return_value=None,
        ):
            connected = await adapter.connect()
            assert connected is True
            await _wait_for_async_mock_calls(adapter.handle_message)

            inbound_event = adapter.handle_message.await_args.args[0]
            assert inbound_event.text == "hello from fake ndr"
            assert inbound_event.source.chat_id == "chat-from-script"
            assert inbound_event.source.user_id == "peer-pubkey"

            result = await adapter.send("chat-target-123", "reply from hermes")
            assert result.success is True
            assert result.message_id == "msg-send-1"

            await adapter.disconnect()

        send_log = data_dir / "send-log.jsonl"
        lines = send_log.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        payload = json.loads(lines[0])
        assert payload == {"target": "chat-target-123", "content": "reply from hermes"}
