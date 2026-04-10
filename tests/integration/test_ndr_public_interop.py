"""Opt-in public-relay NDR interoperability harness.

This test is intentionally manual/interactive. It validates the real Hermes
NDR gateway path against an external Iris-compatible client over public relays:

external client -> NdrAdapter -> GatewayRunner._handle_message -> adapter.send -> public transcript

Required environment:
- HERMES_NDR_PUBLIC_DATA_DIR: logged-in NDR data dir for the Hermes-side identity
- HERMES_NDR_PUBLIC_CHAT_ID: existing public NDR chat/session id to validate
- HERMES_NDR_PUBLIC_EXPECT_INBOUND: unique inbound text to wait for after the test starts

Optional environment:
- HERMES_NDR_TEST_BIN: path to upstream ndr binary
- HERMES_NDR_PUBLIC_EXPECT_OUTBOUND: deterministic Hermes reply to assert

Suggested usage:
  1. Export the variables above
  2. Start the test
  3. Send the exact inbound text from Iris or another ndr-compatible client
  4. The test waits for a fresh inbound event, then confirms a fresh outgoing
     assistant reply appears in the NDR transcript after that inbound message
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent
from gateway.platforms.ndr import NdrAdapter
from gateway.session import SessionEntry


pytestmark = pytest.mark.integration


def _find_ndr_bin() -> Path | None:
    candidates = (
        os.getenv("HERMES_NDR_TEST_BIN", "").strip(),
        "/tmp/nostr-double-ratchet/rust/target/debug/ndr",
        shutil.which("ndr") or "",
    )
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return path
    return None


def _require_public_interop_env() -> tuple[Path, Path, str, str, str]:
    ndr_bin = _find_ndr_bin()
    if ndr_bin is None:
        pytest.skip("ndr binary not found for public NDR interop test")
    data_dir_raw = os.getenv("HERMES_NDR_PUBLIC_DATA_DIR", "").strip()
    chat_id = os.getenv("HERMES_NDR_PUBLIC_CHAT_ID", "").strip()
    expected_inbound = os.getenv("HERMES_NDR_PUBLIC_EXPECT_INBOUND", "").strip()
    expected_outbound = os.getenv("HERMES_NDR_PUBLIC_EXPECT_OUTBOUND", "Hermes public NDR OK").strip()
    if not data_dir_raw or not chat_id or not expected_inbound:
        pytest.skip(
            "set HERMES_NDR_PUBLIC_DATA_DIR, HERMES_NDR_PUBLIC_CHAT_ID, "
            "and HERMES_NDR_PUBLIC_EXPECT_INBOUND to run public NDR interop"
        )
    data_dir = Path(data_dir_raw)
    if not data_dir.exists():
        pytest.skip(f"public NDR data dir does not exist: {data_dir}")
    return ndr_bin, data_dir, chat_id, expected_inbound, expected_outbound


async def _run_ndr_json(ndr_bin: Path, data_dir: Path, *args: str, timeout: float = 20.0) -> dict:
    proc = await asyncio.create_subprocess_exec(
        str(ndr_bin),
        "--json",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "NDR_DATA_DIR": str(data_dir)},
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
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


def _message_ids(payload: dict) -> set[str]:
    data = payload.get("data") if isinstance(payload, dict) else None
    messages = data.get("messages") if isinstance(data, dict) else None
    ids: set[str] = set()
    if isinstance(messages, list):
        for message in messages:
            if isinstance(message, dict) and message.get("id"):
                ids.add(str(message["id"]))
    return ids


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


async def _wait_for_async_mock_calls(mock: AsyncMock, count: int = 1, timeout: float = 60.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while mock.await_count < count:
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"expected {count} awaited calls, saw {mock.await_count}")
        await asyncio.sleep(0.05)


async def _wait_for_fresh_outgoing(
    ndr_bin: Path,
    data_dir: Path,
    chat_id: str,
    *,
    baseline_ids: set[str],
    expected_content: str,
    min_timestamp: float,
    timeout: float = 120.0,
) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        payload = await _run_ndr_json(ndr_bin, data_dir, "read", chat_id, timeout=15.0)
        data = payload.get("data") if isinstance(payload, dict) else None
        messages = data.get("messages") if isinstance(data, dict) else None
        if isinstance(messages, list):
            for message in messages:
                if not isinstance(message, dict):
                    continue
                if message.get("id") in baseline_ids:
                    continue
                if message.get("is_outgoing") is not True:
                    continue
                if message.get("content") != expected_content:
                    continue
                if float(message.get("timestamp") or 0) < min_timestamp:
                    continue
                return message
        await asyncio.sleep(2.0)
    raise AssertionError("timed out waiting for fresh outgoing NDR reply in public transcript")


async def _wait_for_fresh_incoming(
    ndr_bin: Path,
    data_dir: Path,
    chat_id: str,
    *,
    baseline_ids: set[str],
    expected_content: str,
    timeout: float = 180.0,
) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        payload = await _run_ndr_json(ndr_bin, data_dir, "read", chat_id, timeout=15.0)
        data = payload.get("data") if isinstance(payload, dict) else None
        messages = data.get("messages") if isinstance(data, dict) else None
        if isinstance(messages, list):
            for message in messages:
                if not isinstance(message, dict):
                    continue
                if message.get("id") in baseline_ids:
                    continue
                if message.get("is_outgoing") is not False:
                    continue
                if message.get("content") != expected_content:
                    continue
                return message
        await asyncio.sleep(2.0)
    raise AssertionError("timed out waiting for fresh incoming NDR message in public transcript")


@pytest.mark.asyncio
@pytest.mark.allow_long_timeout
async def test_public_ndr_interop_fresh_message_roundtrip(monkeypatch, tmp_path):
    import gateway.run as gateway_run

    ndr_bin, data_dir, chat_id, expected_inbound, expected_outbound = _require_public_interop_env()
    baseline_payload = await _run_ndr_json(ndr_bin, data_dir, "read", chat_id, timeout=15.0)
    baseline_ids = _message_ids(baseline_payload)

    adapter = NdrAdapter(
        PlatformConfig(enabled=True, extra={"bin": str(ndr_bin), "data_dir": str(data_dir)})
    )
    session_entry = SessionEntry(
        session_key="ndr-public-interop",
        session_id="ndr-public-interop-session",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.NDR,
        chat_type="dm",
    )
    runner = _make_runner(session_entry, adapter)
    runner._run_agent = AsyncMock(
        return_value={
            "final_response": expected_outbound,
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
    monkeypatch.setenv("NDR_HOME_CHANNEL", chat_id)

    state = {"event": None, "result": None, "error": None}
    matched_event = asyncio.Event()

    async def _wrapped_handle_message(event):
        if (event.text or "").strip() != expected_inbound:
            return None
        state["event"] = event
        try:
            result = await runner._handle_message(event)
            state["result"] = result
            return result
        except Exception as exc:  # pragma: no cover - surfaced via assertion below
            state["error"] = exc
            raise
        finally:
            matched_event.set()

    adapter.set_message_handler(_wrapped_handle_message)
    adapter.set_session_store(runner.session_store)
    assert await adapter.connect() is True

    try:
        try:
            await asyncio.wait_for(matched_event.wait(), timeout=180.0)
        except TimeoutError:
            incoming = await _wait_for_fresh_incoming(
                ndr_bin,
                data_dir,
                chat_id,
                baseline_ids=baseline_ids,
                expected_content=expected_inbound,
            )
            state["event"] = MessageEvent(
                text=expected_inbound,
                source=adapter.build_source(
                    chat_id=chat_id,
                    chat_name=chat_id,
                    chat_type="dm",
                    user_id=str(incoming.get("from_pubkey") or ""),
                    user_name=str(incoming.get("from_pubkey") or ""),
                ),
                raw_message=incoming,
                message_id=str(incoming.get("id") or ""),
                timestamp=datetime.fromtimestamp(float(incoming.get("timestamp") or 0)),
            )
            await adapter.handle_message(state["event"])
            await asyncio.wait_for(matched_event.wait(), timeout=30.0)
        assert state["error"] is None
        assert state["event"] is not None
        if runner._run_agent.await_count:
            await _wait_for_async_mock_calls(runner._run_agent)

        outgoing = await _wait_for_fresh_outgoing(
            ndr_bin,
            data_dir,
            chat_id,
            baseline_ids=baseline_ids,
            expected_content=expected_outbound,
            min_timestamp=state["event"].timestamp.timestamp(),
        )

        assert outgoing["content"] == expected_outbound
        assert outgoing["is_outgoing"] is True
        assert runner._run_agent.await_args.kwargs["message"] == expected_inbound
    finally:
        await adapter.disconnect()
