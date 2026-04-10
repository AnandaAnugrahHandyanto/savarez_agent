"""Live local roundtrip for the NDR gateway adapter.

This is an opt-in integration test. It launches a disposable local strfry relay
in Docker, creates two real `ndr` identities against that relay, wires Hermes's
real NDR adapter into a minimal GatewayRunner, and verifies an end-to-end DM:

sender ndr -> Hermes NDR adapter -> GatewayRunner._handle_message -> adapter.send -> sender ndr
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import textwrap
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from urllib.request import urlopen

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.ndr import NdrAdapter
from gateway.session import SessionEntry


pytestmark = pytest.mark.integration

_RELAY_IMAGE = "docker-three-node-infra-relay:latest"
_NDR_BIN_CANDIDATES = (
    os.getenv("HERMES_NDR_TEST_BIN", "").strip(),
    "/tmp/nostr-double-ratchet/rust/target/debug/ndr",
    shutil.which("ndr") or "",
)


@dataclass
class _LocalRelay:
    name: str
    port: int
    root: Path

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}"


def _find_ndr_bin() -> Path | None:
    for candidate in _NDR_BIN_CANDIDATES:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return path
    return None


def _require_live_prereqs() -> Path:
    if not shutil.which("docker"):
        pytest.skip("docker is required for live NDR relay testing")
    ndr_bin = _find_ndr_bin()
    if ndr_bin is None:
        pytest.skip("ndr binary not found for live NDR integration test")
    inspect = subprocess.run(
        ["docker", "image", "inspect", _RELAY_IMAGE],
        capture_output=True,
        text=True,
        check=False,
    )
    if inspect.returncode != 0:
        pytest.skip(f"relay image {_RELAY_IMAGE!r} is not available locally")
    return ndr_bin


def _pick_free_port() -> int:
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def _write_relay_config(root: Path) -> Path:
    config_path = root / "strfry.conf"
    config_path.write_text(
        textwrap.dedent(
            """\
            db = "/var/lib/strfry"

            events {
                rejectEventsNewerThanSeconds = 900
                rejectEventsOlderThanSeconds = 94608000
                rejectEphemeralEventsOlderThanSeconds = 60
                ephemeralEventsLifetimeSeconds = 300
            }

            relay {
                bind = "0.0.0.0"
                port = 7777

                auth {
                    enabled = false
                    serviceUrl = ""
                }
            }
            """
        ),
        encoding="utf-8",
    )
    return config_path


def _start_local_relay(tmp_path: Path) -> _LocalRelay:
    name = f"hermes-ndr-live-{uuid.uuid4().hex[:8]}"
    port = _pick_free_port()
    root = tmp_path / name
    db_dir = root / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    config_path = _write_relay_config(root)

    run = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            name,
            "-p",
            f"{port}:7777",
            "-v",
            f"{db_dir}:/var/lib/strfry",
            "-v",
            f"{config_path}:/usr/src/app/strfry.conf:ro",
            _RELAY_IMAGE,
            "/usr/src/app/strfry.conf",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if run.returncode != 0:
        raise AssertionError(f"failed to start local relay: {run.stderr.strip() or run.stdout.strip()}")

    deadline = time.monotonic() + 5.0
    while True:
        try:
            with urlopen(f"http://127.0.0.1:{port}", timeout=1.0):
                break
        except Exception:
            if time.monotonic() >= deadline:
                raise AssertionError("local relay did not become ready in time")
            time.sleep(0.1)
    return _LocalRelay(name=name, port=port, root=root)


def _stop_local_relay(relay: _LocalRelay) -> None:
    subprocess.run(["docker", "rm", "-f", relay.name], capture_output=True, text=True, check=False)


def _write_identity_config(root: Path, private_key_hex: str, relay_url: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.json").write_text(
        json.dumps({"private_key": private_key_hex, "relays": [relay_url]}, indent=2),
        encoding="utf-8",
    )


async def _run_ndr_json(ndr_bin: Path, data_dir: Path, *args: str, timeout: float = 15.0) -> dict:
    proc = await asyncio.create_subprocess_exec(
        str(ndr_bin),
        "--json",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "NDR_DATA_DIR": str(data_dir)},
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        with suppress(Exception):
            proc.kill()
        raise AssertionError(f"ndr command timed out: {' '.join(args)}")

    for raw in reversed((stdout + b"\n" + stderr).decode("utf-8", "replace").splitlines()):
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise AssertionError(f"ndr command produced no JSON payload: {' '.join(args)}")


async def _start_listen(ndr_bin: Path, data_dir: Path) -> asyncio.subprocess.Process:
    proc = await asyncio.create_subprocess_exec(
        str(ndr_bin),
        "--json",
        "listen",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "NDR_DATA_DIR": str(data_dir)},
    )
    line = await asyncio.wait_for(proc.stdout.readline(), timeout=5.0)
    payload = json.loads(line.decode("utf-8", "replace").strip())
    assert payload["status"] == "ok"
    assert payload["command"] == "listen"
    return proc


async def _wait_for_listen_message(proc: asyncio.subprocess.Process, *, expected_content: str, timeout: float = 10.0) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"timed out waiting for listen event content={expected_content!r}")
        try:
            line = await asyncio.wait_for(
                proc.stdout.readline(),
                timeout=min(1.0, max(0.1, deadline - asyncio.get_running_loop().time())),
            )
        except asyncio.TimeoutError:
            continue
        if not line:
            continue
        payload = json.loads(line.decode("utf-8", "replace").strip())
        if payload.get("event") == "message" and payload.get("content") == expected_content:
            return payload


async def _stop_process(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    proc.terminate()
    with suppress(Exception):
        await asyncio.wait_for(proc.wait(), timeout=3.0)


def _make_runner(session_entry: SessionEntry, adapter: NdrAdapter):
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(platforms={Platform.NDR: adapter.config})
    runner.adapters = {Platform.NDR: adapter}
    runner._voice_mode = {}
    runner.hooks = SimpleNamespace(emit=AsyncMock(), loaded_hooks=False)
    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = session_entry
    runner.session_store.load_transcript.return_value = []
    runner.session_store.has_any_sessions.return_value = True
    runner.session_store.append_to_transcript = MagicMock()
    runner.session_store.rewrite_transcript = MagicMock()
    runner.session_store.update_session = MagicMock()
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._pending_messages = {}
    runner._pending_approvals = {}
    runner._background_tasks = set()
    runner._session_db = None
    runner._reasoning_config = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._show_reasoning = False
    runner._model = "openai/test-model"
    runner._base_url = None
    runner._is_user_authorized = lambda _source: True
    runner._set_session_env = lambda _context: None
    runner._should_send_voice_reply = lambda *_args, **_kwargs: False
    runner._send_voice_reply = AsyncMock()
    runner._capture_gateway_honcho_if_configured = lambda *args, **kwargs: None
    runner._emit_gateway_run_progress = AsyncMock()
    runner.delivery_router = MagicMock()
    runner.pairing_store = MagicMock()
    return runner


async def _wait_for_async_mock_calls(mock: AsyncMock, count: int = 1, timeout: float = 10.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while mock.await_count < count:
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"expected {count} awaited calls, saw {mock.await_count}")
        await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_live_local_ndr_roundtrip_through_hermes_runner(monkeypatch, tmp_path):
    import gateway.run as gateway_run

    ndr_bin = _require_live_prereqs()
    relay = _start_local_relay(tmp_path)
    sender_listener = None
    adapter = None

    bot_dir = tmp_path / "bot-ndr"
    sender_dir = tmp_path / "sender-ndr"
    bot_key = "7163c77ff306f269331cc82d1df851bc8a4662d947fbb0ee088ef8ec2d1a182b"
    sender_key = "c5ccf071d75045a9c4a2102feecfa13705832a8f75ce4b082a66e861cb12e65f"
    _write_identity_config(bot_dir, bot_key, relay.url)
    _write_identity_config(sender_dir, sender_key, relay.url)

    try:
        bot_whoami = await _run_ndr_json(ndr_bin, bot_dir, "whoami")
        sender_whoami = await _run_ndr_json(ndr_bin, sender_dir, "whoami")
        bot_npub = bot_whoami["data"]["npub"]

        published = await _run_ndr_json(ndr_bin, bot_dir, "invite", "publish")
        assert published["status"] == "ok"

        sender_listener = await _start_listen(ndr_bin, sender_dir)

        adapter = NdrAdapter(
            PlatformConfig(
                enabled=True,
                extra={"bin": str(ndr_bin), "data_dir": str(bot_dir)},
            )
        )
        session_entry = SessionEntry(
            session_key="ndr-live-roundtrip",
            session_id="ndr-live-roundtrip-session",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            platform=Platform.NDR,
            chat_type="dm",
        )
        runner = _make_runner(session_entry, adapter)
        runner._run_agent = AsyncMock(
            return_value={
                "final_response": "Hermes local NDR roundtrip OK",
                "messages": [],
                "tools": [],
                "history_offset": 0,
                "last_prompt_tokens": 0,
                "failed": False,
            }
        )

        monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path / "hermes-home")
        monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"})
        monkeypatch.setattr("agent.model_metadata.get_model_context_length", lambda *_args, **_kwargs: 100000)

        handler_state = {"event": None, "result": None, "error": None}
        handler_called = asyncio.Event()

        async def _wrapped_handle_message(event):
            handler_state["event"] = event
            try:
                result = await runner._handle_message(event)
                handler_state["result"] = result
                return result
            except Exception as exc:  # pragma: no cover - surfaced via assertion below
                handler_state["error"] = exc
                raise
            finally:
                handler_called.set()

        adapter.set_message_handler(_wrapped_handle_message)
        adapter.set_session_store(runner.session_store)
        assert await adapter.connect() is True

        outbound = None
        for _attempt in range(3):
            outbound = await _run_ndr_json(
                ndr_bin,
                sender_dir,
                "send",
                bot_npub,
                "hello from sender via live hermes test",
            )
            assert outbound["status"] == "ok"
            try:
                await asyncio.wait_for(handler_called.wait(), timeout=4.0)
                break
            except asyncio.TimeoutError:
                continue

        await asyncio.wait_for(handler_called.wait(), timeout=1.0)
        assert handler_state["event"] is not None
        assert handler_state["error"] is None
        await _wait_for_async_mock_calls(runner._run_agent)
        reply = await _wait_for_listen_message(
            sender_listener,
            expected_content="Hermes local NDR roundtrip OK",
        )

        assert reply["from_pubkey"] == bot_whoami["data"]["pubkey"]
        assert runner._run_agent.await_args.kwargs["message"] == "hello from sender via live hermes test"

        persisted_entries = [call.args[1] for call in runner.session_store.append_to_transcript.call_args_list]
        assert persisted_entries[0]["platform"] == "ndr"
        assert persisted_entries[1]["role"] == "user"
        assert persisted_entries[1]["content"] == "hello from sender via live hermes test"
        assert persisted_entries[2]["role"] == "assistant"
        assert persisted_entries[2]["content"] == "Hermes local NDR roundtrip OK"
        assert sender_whoami["data"]["npub"].startswith("npub1")
    finally:
        if adapter is not None:
            await adapter.disconnect()
        if sender_listener is not None:
            await _stop_process(sender_listener)
        _stop_local_relay(relay)
