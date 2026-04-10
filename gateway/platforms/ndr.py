"""NDR (nostr-double-ratchet) gateway adapter."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, MessageEvent, SendResult
from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

DEFAULT_NDR_COMMAND_TIMEOUT = 30.0
DEFAULT_NDR_SEND_TIMEOUT = 120.0


def check_ndr_requirements(binary: Optional[str] = None) -> bool:
    """Check whether the upstream ndr CLI is available."""
    candidate = (binary or os.getenv("NDR_BIN") or "ndr").strip()
    if not candidate:
        return False
    if os.path.isabs(candidate) or os.sep in candidate:
        return Path(candidate).exists()
    return shutil.which(candidate) is not None


def _resolve_ndr_bin(binary: Optional[str] = None) -> str:
    candidate = str(binary or os.getenv("NDR_BIN") or "ndr").strip()
    return candidate or "ndr"


def _resolve_ndr_data_dir(data_dir: Optional[str | Path] = None) -> Path:
    if data_dir:
        return Path(data_dir)
    env_dir = os.getenv("NDR_DATA_DIR", "").strip()
    if env_dir:
        return Path(env_dir)
    return get_hermes_home() / "platforms" / "ndr"


def _build_ndr_env(data_dir: Path) -> Dict[str, str]:
    env = dict(os.environ)
    env["NDR_DATA_DIR"] = str(data_dir)
    return env


def _parse_ndr_command_output(output: str) -> Optional[Dict[str, Any]]:
    for raw_line in reversed(output.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def resolve_ndr_send_timeout(extra: Optional[Dict[str, Any]] = None) -> float:
    raw_value = None
    if isinstance(extra, dict):
        raw_value = extra.get("send_timeout")
    if raw_value in (None, ""):
        raw_value = os.getenv("NDR_SEND_TIMEOUT", "").strip()
    if raw_value in (None, ""):
        return DEFAULT_NDR_SEND_TIMEOUT
    try:
        timeout = float(raw_value)
    except (TypeError, ValueError):
        return DEFAULT_NDR_SEND_TIMEOUT
    return timeout if timeout > 0 else DEFAULT_NDR_SEND_TIMEOUT


async def run_ndr_json_command(
    *args: str,
    binary: Optional[str] = None,
    data_dir: Optional[str | Path] = None,
    timeout: float = DEFAULT_NDR_COMMAND_TIMEOUT,
) -> Dict[str, Any]:
    ndr_bin = _resolve_ndr_bin(binary)
    ndr_data_dir = _resolve_ndr_data_dir(data_dir)
    proc = await asyncio.create_subprocess_exec(
        ndr_bin,
        "--json",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_build_ndr_env(ndr_data_dir),
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        with contextlib.suppress(Exception):
            proc.kill()
        return {
            "status": "error",
            "command": args[0] if args else "",
            "error": f"ndr command timed out after {timeout:.1f}s",
        }
    stdout_text = stdout.decode("utf-8", "replace")
    stderr_text = stderr.decode("utf-8", "replace")
    payload = _parse_ndr_command_output(stdout_text)
    if payload is None:
        payload = _parse_ndr_command_output(stderr_text)
    if payload is not None:
        return payload
    message = stderr_text.strip() or stdout_text.strip()
    return {
        "status": "error",
        "command": args[0] if args else "",
        "error": message or f"ndr exited with {proc.returncode}",
    }


async def send_ndr_message(
    chat_id: str,
    content: str,
    *,
    binary: Optional[str] = None,
    data_dir: Optional[str | Path] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> SendResult:
    ndr_bin = _resolve_ndr_bin(binary or (extra or {}).get("bin"))
    ndr_data_dir = _resolve_ndr_data_dir(data_dir or (extra or {}).get("data_dir"))
    whoami = await run_ndr_json_command(
        "whoami",
        binary=ndr_bin,
        data_dir=ndr_data_dir,
        timeout=10.0,
    )
    data = whoami.get("data") if isinstance(whoami, dict) else None
    if whoami.get("status") != "ok" or not isinstance(data, dict) or not data.get("logged_in"):
        return SendResult(
            success=False,
            error="ndr is not logged in. Run `ndr login <nsec>` for the configured NDR_DATA_DIR first.",
        )

    payload = await run_ndr_json_command(
        "send",
        chat_id,
        content,
        binary=ndr_bin,
        data_dir=ndr_data_dir,
        timeout=resolve_ndr_send_timeout(extra),
    )
    if payload.get("status") != "ok":
        return SendResult(success=False, error=payload.get("error") or "ndr send failed")

    result_data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    message_id = result_data.get("id") or result_data.get("message_id")
    return SendResult(
        success=True,
        message_id=str(message_id) if message_id else None,
        raw_response=payload,
    )


class NdrAdapter(BasePlatformAdapter):
    """Hermes adapter for nostr-double-ratchet via the upstream ndr CLI."""

    platform = Platform.NDR

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform.NDR)
        extra = config.extra or {}
        self.ndr_bin = _resolve_ndr_bin(extra.get("bin"))
        self.data_dir = _resolve_ndr_data_dir(extra.get("data_dir"))
        self.identity: Dict[str, Any] = {}
        self._listen_process: Optional[asyncio.subprocess.Process] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._stderr_task: Optional[asyncio.Task] = None
        self._identity_lock: Optional[str] = None
        self._listen_started: Optional[asyncio.Future] = None
        self._last_stderr_line: str = ""

    def _build_env(self) -> Dict[str, str]:
        return _build_ndr_env(self.data_dir)

    async def _run_json_command(self, *args: str, timeout: float = 30.0) -> Dict[str, Any]:
        return await run_ndr_json_command(
            *args,
            binary=self.ndr_bin,
            data_dir=self.data_dir,
            timeout=timeout,
        )

    @staticmethod
    def _parse_command_output(output: str) -> Optional[Dict[str, Any]]:
        return _parse_ndr_command_output(output)

    async def _process_listen_line(self, line: str) -> None:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            logger.debug("NDR: ignoring malformed listen line: %s", line)
            return
        if isinstance(payload, dict):
            if self._listen_started and not self._listen_started.done():
                if payload.get("status") == "ok" and payload.get("command") == "listen":
                    self._listen_started.set_result(True)
                    return
                if payload.get("status") == "error":
                    self._listen_started.set_result(payload.get("error") or "ndr listen failed")
                    return
                self._listen_started.set_result(True)
            await self._handle_listen_payload(payload)

    async def _handle_listen_payload(self, payload: Dict[str, Any]) -> None:
        if payload.get("event") != "message":
            return

        content = str(payload.get("content") or "").strip()
        if not content:
            return
        from_pubkey = str(payload.get("from_pubkey") or "")
        if from_pubkey and from_pubkey == str(self.identity.get("pubkey") or ""):
            return

        timestamp = payload.get("timestamp")
        dt = datetime.fromtimestamp(timestamp) if isinstance(timestamp, (int, float)) else datetime.now()
        source = self.build_source(
            chat_id=str(payload.get("chat_id") or ""),
            chat_name=str(payload.get("chat_id") or ""),
            chat_type="dm",
            user_id=from_pubkey,
            user_name=from_pubkey,
        )
        event = MessageEvent(
            text=content,
            source=source,
            raw_message=payload,
            message_id=str(payload.get("message_id") or "") or None,
            timestamp=dt,
        )
        await self.handle_message(event)

    async def _listen_stdout_loop(self) -> None:
        if not self._listen_process or not self._listen_process.stdout:
            return
        try:
            while True:
                line = await self._listen_process.stdout.readline()
                if not line:
                    if self._listen_started and not self._listen_started.done():
                        if self._listen_process and self._listen_process.returncode is None:
                            with contextlib.suppress(Exception):
                                await asyncio.wait_for(self._listen_process.wait(), timeout=1)
                        if not self._last_stderr_line and self._listen_process and self._listen_process.stderr:
                            with contextlib.suppress(Exception):
                                stderr_line = await asyncio.wait_for(self._listen_process.stderr.readline(), timeout=0.1)
                                text = stderr_line.decode("utf-8", "replace").strip()
                                if text:
                                    self._last_stderr_line = text
                        message = self._last_stderr_line or "ndr listen exited before startup completed"
                        self._listen_started.set_result(message)
                    break
                await self._process_listen_line(line.decode("utf-8", "replace").strip())
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if self._listen_started and not self._listen_started.done():
                self._listen_started.set_result(str(exc))
            logger.warning("NDR: listen stdout loop failed: %s", exc)

    async def _listen_stderr_loop(self) -> None:
        if not self._listen_process or not self._listen_process.stderr:
            return
        try:
            while True:
                line = await self._listen_process.stderr.readline()
                if not line:
                    break
                text = line.decode("utf-8", "replace").strip()
                if text:
                    self._last_stderr_line = text
                    logger.debug("NDR stderr: %s", text)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug("NDR: stderr loop ended: %s", exc)

    async def connect(self) -> bool:
        if not check_ndr_requirements(self.ndr_bin):
            self._set_fatal_error("ndr_binary_missing", "ndr binary not found", retryable=False)
            return False

        self.data_dir.mkdir(parents=True, exist_ok=True)
        whoami = await self._run_json_command("whoami", timeout=10.0)
        data = whoami.get("data") if isinstance(whoami, dict) else None
        if whoami.get("status") != "ok" or not isinstance(data, dict) or not data.get("logged_in"):
            self._set_fatal_error(
                "ndr_login_required",
                "ndr is not logged in. Run `ndr login <nsec>` for the configured NDR_DATA_DIR first.",
                retryable=False,
            )
            return False

        self.identity = data
        try:
            from gateway.status import acquire_scoped_lock

            self._identity_lock = str(data.get("npub") or data.get("pubkey") or "")
            if self._identity_lock:
                acquired, existing = acquire_scoped_lock(
                    "ndr-identity",
                    self._identity_lock,
                    metadata={"platform": self.platform.value},
                )
                if not acquired:
                    owner_pid = existing.get("pid") if isinstance(existing, dict) else None
                    self._set_fatal_error(
                        "ndr_identity_lock",
                        "Another local Hermes gateway is already using this NDR identity"
                        + (f" (PID {owner_pid})." if owner_pid else "."),
                        retryable=False,
                    )
                    return False
        except Exception as exc:
            logger.warning("NDR: could not acquire scoped identity lock: %s", exc)

        try:
            self._listen_process = await asyncio.create_subprocess_exec(
                self.ndr_bin,
                "--json",
                "listen",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._build_env(),
            )
        except Exception as exc:
            self._release_lock()
            self._set_fatal_error("ndr_listen_start_failed", f"Failed to start `ndr listen`: {exc}", retryable=False)
            return False

        self._last_stderr_line = ""
        self._listen_started = asyncio.get_running_loop().create_future()
        self._running = True
        self._listen_task = asyncio.create_task(self._listen_stdout_loop())
        try:
            started = await asyncio.wait_for(self._listen_started, timeout=5)
        except asyncio.TimeoutError:
            await self.disconnect()
            self._set_fatal_error("ndr_listen_start_failed", "Timed out waiting for `ndr listen` startup", retryable=False)
            return False

        if started is not True:
            await self.disconnect()
            self._set_fatal_error("ndr_listen_start_failed", f"Failed to start `ndr listen`: {started}", retryable=False)
            return False
        self._stderr_task = asyncio.create_task(self._listen_stderr_loop())
        return True

    def _release_lock(self) -> None:
        if not self._identity_lock:
            return
        try:
            from gateway.status import release_scoped_lock

            release_scoped_lock("ndr-identity", self._identity_lock)
        except Exception:
            pass
        finally:
            self._identity_lock = None

    async def disconnect(self) -> None:
        self._running = False

        for task in (self._listen_task, self._stderr_task):
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self._listen_task = None
        self._stderr_task = None
        self._listen_started = None

        if self._listen_process:
            if self._listen_process.returncode is None:
                self._listen_process.terminate()
                with contextlib.suppress(ProcessLookupError, asyncio.TimeoutError):
                    await asyncio.wait_for(self._listen_process.wait(), timeout=5)
            self._listen_process = None

        self._release_lock()

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        payload = await self._run_json_command(
            "send",
            chat_id,
            content,
            timeout=resolve_ndr_send_timeout(self.config.extra),
        )
        if payload.get("status") != "ok":
            return SendResult(success=False, error=payload.get("error") or "ndr send failed")

        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        message_id = data.get("id") or data.get("message_id")
        return SendResult(success=True, message_id=str(message_id) if message_id else None, raw_response=payload)

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        return {"id": chat_id, "name": chat_id, "type": "dm"}
