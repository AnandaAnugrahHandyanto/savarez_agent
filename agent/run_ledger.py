"""Durable append-only run ledger for agent recovery context."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.redact import redact_sensitive_text
from hermes_constants import get_hermes_home

try:  # POSIX-first; Windows cross-process locking can come later.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


DEFAULT_RUN_LEDGER_CONFIG = {
    "enabled": True,
    "preview_chars": 4096,
    "blob_threshold_chars": 16384,
    "max_blob_bytes": 10_000_000,
    "max_capsule_events": 200,
    "lock_timeout_seconds": 30,
    "fsync": False,
    "retention_days": 90,
    "max_run_bytes": 268435456,
}


class RunLedgerError(RuntimeError):
    """Raised when a ledger write cannot complete safely."""


@dataclass
class LedgerReadResult:
    events: list[dict[str, Any]] = field(default_factory=list)
    corrupt_lines: list[dict[str, Any]] = field(default_factory=list)


_LOCKS: dict[Path, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()
_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "access_token",
        "accesstoken",
        "refresh_token",
        "refreshtoken",
        "token",
        "password",
        "passwd",
        "secret",
        "credential",
        "credentials",
        "authorization",
        "auth",
        "cookie",
        "private_key",
        "privatekey",
        "access_key",
        "accesskey",
        "session_key",
        "sessionkey",
    }
)
_SENSITIVE_KEY_MARKERS = frozenset(
    {
        "apikey",
        "accesstoken",
        "refreshtoken",
        "password",
        "passwd",
        "secret",
        "credential",
        "authorization",
        "privatekey",
        "accesskey",
        "sessionkey",
    }
)
_REDACTED_VALUE = "[REDACTED]"


def _path_lock(path: Path) -> threading.RLock:
    resolved = path.resolve()
    with _LOCKS_GUARD:
        lock = _LOCKS.get(resolved)
        if lock is None:
            lock = threading.RLock()
            _LOCKS[resolved] = lock
        return lock


def _secure_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for candidate in (path, *path.parents):
        if "runs" not in candidate.parts:
            continue
        with contextlib.suppress(OSError):
            os.chmod(candidate, 0o700)
        if candidate.name == "runs":
            break


def _secure_touch(path: Path) -> None:
    fd = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
    os.close(fd)
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _validate_path_segment(value: str, *, field_name: str) -> str:
    segment = str(value or "").strip()
    if not segment:
        raise ValueError(f"{field_name} is required")
    if segment in {".", ".."} or not _SAFE_SEGMENT_RE.fullmatch(segment):
        raise ValueError(f"unsafe {field_name}: {segment!r}")
    return segment


def _is_sensitive_key(key: Any) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(key).strip().lower())
    if not normalized:
        return False
    return normalized in _SENSITIVE_KEYS or any(marker in normalized for marker in _SENSITIVE_KEY_MARKERS)


def _redact_value(value: Any, *, key: Any = None) -> Any:
    if key is not None and _is_sensitive_key(key):
        return _REDACTED_VALUE
    if isinstance(value, str):
        return redact_sensitive_text(value, force=True)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        return {str(item_key): _redact_value(val, key=item_key) for item_key, val in value.items()}
    return value


def _stable_json(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except TypeError:
        return json.dumps(str(value), ensure_ascii=False)


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written == 0:
            raise OSError("short write while writing run ledger data")
        view = view[written:]


class NullRunLedger:
    run_id = ""
    session_id = ""

    def __bool__(self) -> bool:
        return False

    def append_event(self, *_args, **_kwargs) -> dict[str, Any]:
        return {}

    def tool_started(self, *_args, **_kwargs) -> dict[str, Any]:
        return {}

    def tool_finished(self, *_args, **_kwargs) -> dict[str, Any]:
        return {}

    def tool_failed(self, *_args, **_kwargs) -> dict[str, Any]:
        return {}

    def tool_skipped(self, *_args, **_kwargs) -> dict[str, Any]:
        return {}

    def compression_started(self, *_args, **_kwargs) -> dict[str, Any]:
        return {}

    def read_events(self) -> LedgerReadResult:
        return LedgerReadResult()

    def recover_state(self) -> dict[str, Any]:
        return {"in_flight": {}, "recent_completed_tools": [], "artifact_refs": []}

    def write_state_capsule(self, **_kwargs) -> dict[str, Any]:
        return {}

    def current_event_span(self) -> dict[str, Any]:
        return {
            "start_event_id": None,
            "end_event_id": None,
            "start_seq": None,
            "end_seq": None,
        }

    def event_span(self) -> dict[str, Any]:
        return self.current_event_span()

    def update_session_id(self, session_id: str) -> None:
        self.session_id = session_id or ""


class RunLedger:
    """Append-only run event ledger rooted under ``HERMES_HOME/runs``."""

    schema_version = 1

    def __init__(
        self,
        *,
        run_id: str,
        session_id: str | None = None,
        config: dict[str, Any] | None = None,
        hermes_home: Path | None = None,
    ) -> None:
        self.run_id = _validate_path_segment(str(run_id or ""), field_name="run_id")
        self.session_id = str(session_id or self.run_id)
        self.config = {**DEFAULT_RUN_LEDGER_CONFIG, **(config or {})}
        self.hermes_home = Path(hermes_home) if hermes_home else get_hermes_home()
        self.run_root = self.hermes_home / "runs" / self.run_id
        self.events_path = self.run_root / "events.jsonl"
        self.artifacts_path = self.run_root / "artifacts.json"
        self.lock_path = self.run_root / "events.lock"
        self.capsules_dir = self.run_root / "capsules"
        self.objects_root = self.run_root / "objects" / "sha256"
        self._lock = _path_lock(self.lock_path)

        _secure_mkdir(self.hermes_home / "runs")
        _secure_mkdir(self.run_root)
        _secure_mkdir(self.capsules_dir)
        _secure_mkdir(self.objects_root)
        _secure_touch(self.events_path)
        _secure_touch(self.lock_path)
        self._ensure_artifacts_file()
        self._last_seq = self._scan_last_valid_seq()

    def update_session_id(self, session_id: str) -> None:
        self.session_id = str(session_id or self.session_id)

    @contextlib.contextmanager
    def _exclusive_lock(self):
        timeout = float(self.config.get("lock_timeout_seconds", 30))
        deadline = time.monotonic() + timeout
        with self._lock:
            lock_fh = self.lock_path.open("a+", encoding="utf-8")
            try:
                if fcntl is not None:
                    while True:
                        try:
                            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                            break
                        except BlockingIOError as exc:
                            if time.monotonic() >= deadline:
                                raise RunLedgerError(
                                    f"timed out acquiring run ledger lock for {self.run_id}"
                                ) from exc
                            time.sleep(0.05)
                yield
            finally:
                if fcntl is not None:
                    with contextlib.suppress(OSError):
                        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)
                lock_fh.close()

    def _scan_last_valid_seq(self) -> int:
        last = 0
        if not self.events_path.exists():
            return last
        with self.events_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                seq = event.get("event_seq")
                if isinstance(seq, int) and seq > last:
                    last = seq
        return last

    def _atomic_write(self, path: Path, data: bytes) -> None:
        _secure_mkdir(path.parent)
        tmp_path = path.parent / f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        fd = os.open(tmp_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            _write_all(fd, data)
            if self.config.get("fsync", False):
                os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp_path, path)
        with contextlib.suppress(OSError):
            os.chmod(path, 0o600)
        if self.config.get("fsync", False):
            with contextlib.suppress(OSError):
                dir_fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)

    def _ensure_artifacts_file(self) -> None:
        if not self.artifacts_path.exists() or not self.artifacts_path.read_text(encoding="utf-8").strip():
            self._atomic_write(self.artifacts_path, b"[]\n")
            return
        try:
            parsed = json.loads(self.artifacts_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            parsed = None
        if not isinstance(parsed, list):
            self._atomic_write(self.artifacts_path, b"[]\n")

    def _read_artifacts(self) -> list[dict[str, Any]]:
        self._ensure_artifacts_file()
        try:
            parsed = json.loads(self.artifacts_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return parsed if isinstance(parsed, list) else []

    def _append_artifacts(self, refs: list[dict[str, Any]]) -> None:
        if not refs:
            return
        artifacts = self._read_artifacts()
        artifacts.extend(_redact_value(refs))
        data = json.dumps(artifacts, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
        self._atomic_write(self.artifacts_path, data + b"\n")

    def _run_dir_size(self) -> int:
        total = 0
        if not self.run_root.exists():
            return total
        for path in self.run_root.rglob("*"):
            if path.is_file():
                with contextlib.suppress(OSError):
                    total += path.stat().st_size
        return total

    def _payload_text_and_data(self, value: Any) -> tuple[Any, str]:
        redacted = _redact_value(value)
        text = _stable_json(redacted)
        text = redact_sensitive_text(text, force=True)
        if isinstance(value, str):
            return text, text
        try:
            return json.loads(text), text
        except json.JSONDecodeError:
            return text, text

    def _object_is_valid(self, object_path: Path, *, digest: str, size: int) -> bool:
        try:
            if object_path.stat().st_size != size:
                return False
            hasher = hashlib.sha256()
            with object_path.open("rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    hasher.update(chunk)
            return hasher.hexdigest() == digest
        except OSError:
            return False

    def _prepare_payload(
        self,
        value: Any,
        *,
        artifact_refs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        redacted, text = self._payload_text_and_data(value)
        data = text.encode("utf-8")
        digest = hashlib.sha256(data).hexdigest()
        preview_chars = int(self.config.get("preview_chars", 4096))
        threshold = int(self.config.get("blob_threshold_chars", 16384))
        max_blob_bytes = int(self.config.get("max_blob_bytes", 10_000_000))
        envelope: dict[str, Any] = {
            "preview": text[:preview_chars],
            "sha256": digest,
            "bytes": len(data),
            "redaction_status": "redacted",
            "safe_to_publish": False,
            "truncated": len(text) > preview_chars,
            "truncated_due_to_policy": False,
        }
        if len(text) <= threshold:
            envelope["data"] = redacted
            return envelope

        if len(data) > max_blob_bytes:
            tail = text[-preview_chars:] if preview_chars > 0 else ""
            envelope.update(
                {
                    "tail_preview": tail,
                    "original_redacted_bytes": len(data),
                    "original_redacted_sha256": digest,
                    "truncated": True,
                    "truncated_due_to_policy": True,
                }
            )
            return envelope

        max_run_bytes = int(self.config.get("max_run_bytes", DEFAULT_RUN_LEDGER_CONFIG["max_run_bytes"]))
        if max_run_bytes > 0 and self._run_dir_size() + len(data) > max_run_bytes:
            tail = text[-preview_chars:] if preview_chars > 0 else ""
            envelope.update(
                {
                    "tail_preview": tail,
                    "original_redacted_bytes": len(data),
                    "original_redacted_sha256": digest,
                    "truncated": True,
                    "truncated_due_to_policy": True,
                }
            )
            return envelope

        object_dir = self.objects_root / digest[:2]
        _secure_mkdir(object_dir)
        object_path = object_dir / digest
        if not self._object_is_valid(object_path, digest=digest, size=len(data)):
            self._atomic_write(object_path, data)
        envelope["object_path"] = object_path.relative_to(self.run_root).as_posix()
        artifact_refs.append(
            {
                "type": "blob",
                "sha256": digest,
                "path": envelope["object_path"],
                "bytes": len(data),
                "safe_to_publish": False,
                "redaction_status": "redacted",
            }
        )
        return envelope

    def append_event(
        self,
        event_type: str,
        *,
        session_id: str | None = None,
        tool_name: str | None = None,
        tool_call_id: str | None = None,
        status: str | None = None,
        duration_ms: int | None = None,
        input: Any = None,
        output: Any = None,
        artifact_refs: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._exclusive_lock():
            self._last_seq = self._scan_last_valid_seq()
            seq = self._last_seq + 1
            event_artifact_refs: list[dict[str, Any]] = _redact_value(artifact_refs or [])
            prepared_input = (
                self._prepare_payload(input, artifact_refs=event_artifact_refs)
                if input is not None
                else {}
            )
            prepared_output = (
                self._prepare_payload(output, artifact_refs=event_artifact_refs)
                if output is not None
                else {}
            )
            event = {
                "schema_version": self.schema_version,
                "event_id": f"evt_{seq:09d}",
                "event_seq": seq,
                "timestamp_utc": _utc_now(),
                "run_id": self.run_id,
                "session_id": session_id or self.session_id,
                "type": event_type,
                "tool_name": tool_name,
                "tool_call_id": tool_call_id,
                "status": status,
                "duration_ms": duration_ms,
                "input": prepared_input,
                "output": prepared_output,
                "artifact_refs": event_artifact_refs,
                "metadata": _redact_value(metadata or {}),
            }
            line = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            fd = os.open(self.events_path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
            try:
                if self._events_path_needs_separator():
                    _write_all(fd, b"\n")
                _write_all(fd, line.encode("utf-8"))
                if self.config.get("fsync", False):
                    os.fsync(fd)
            finally:
                os.close(fd)
            with contextlib.suppress(OSError):
                os.chmod(self.events_path, 0o600)
            self._append_artifacts(event_artifact_refs)
            self._last_seq = seq
            return event

    def _events_path_needs_separator(self) -> bool:
        try:
            if self.events_path.stat().st_size == 0:
                return False
            with self.events_path.open("rb") as fh:
                fh.seek(-1, os.SEEK_END)
                return fh.read(1) != b"\n"
        except OSError:
            return False

    def tool_started(
        self,
        *,
        tool_name: str | None = None,
        tool_call_id: str | None = None,
        input: Any = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.append_event(
            "tool.started",
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            status=kwargs.pop("status", "started"),
            input=input,
            **kwargs,
        )

    def tool_finished(
        self,
        *,
        tool_name: str | None = None,
        tool_call_id: str | None = None,
        output: Any = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.append_event(
            "tool.finished",
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            status=kwargs.pop("status", "ok"),
            output=output,
            **kwargs,
        )

    def tool_failed(
        self,
        *,
        tool_name: str | None = None,
        tool_call_id: str | None = None,
        output: Any = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.append_event(
            "tool.failed",
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            status=kwargs.pop("status", "error"),
            output=output,
            **kwargs,
        )

    def tool_skipped(
        self,
        *,
        tool_name: str | None = None,
        tool_call_id: str | None = None,
        output: Any = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.append_event(
            "tool.skipped",
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            status=kwargs.pop("status", "skipped"),
            output=output,
            **kwargs,
        )

    def compression_started(self, **kwargs: Any) -> dict[str, Any]:
        return self.append_event("compression.started", status=kwargs.pop("status", "started"), **kwargs)

    def read_events(self) -> LedgerReadResult:
        result = LedgerReadResult()
        if not self.events_path.exists():
            return result
        with self.events_path.open("r", encoding="utf-8") as fh:
            for line_number, line in enumerate(fh, 1):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    result.corrupt_lines.append(
                        {
                            "line_number": line_number,
                            "error": str(exc),
                            "preview": line[:200],
                        }
                    )
                    continue
                if isinstance(event, dict):
                    result.events.append(event)
                else:
                    result.corrupt_lines.append(
                        {
                            "line_number": line_number,
                            "error": "event is not an object",
                            "preview": line[:200],
                        }
                    )
        return result

    def recover_state(self, *, max_completed: int | None = None) -> dict[str, Any]:
        in_flight: dict[str, dict[str, Any]] = {}
        completed: list[dict[str, Any]] = []
        artifact_refs: list[dict[str, Any]] = []
        terminal_types = {"tool.finished", "tool.failed", "tool.skipped"}
        for event in self.read_events().events:
            call_id = event.get("tool_call_id")
            if event.get("artifact_refs"):
                artifact_refs.extend(event["artifact_refs"])
            if event.get("type") == "tool.started" and call_id:
                in_flight[call_id] = event
            elif event.get("type") in terminal_types and call_id:
                in_flight.pop(call_id, None)
                completed.append(
                    {
                        "event_id": event.get("event_id"),
                        "event_seq": event.get("event_seq"),
                        "tool_name": event.get("tool_name"),
                        "tool_call_id": call_id,
                        "status": event.get("status"),
                        "duration_ms": event.get("duration_ms"),
                        "output": event.get("output") or {},
                    }
                )
        limit = max_completed or int(self.config.get("max_capsule_events", 200))
        return {
            "in_flight": in_flight,
            "recent_completed_tools": completed[-limit:],
            "artifact_refs": artifact_refs,
        }

    def current_event_span(self) -> dict[str, Any]:
        events = self.read_events().events
        if not events:
            return {
                "start_event_id": None,
                "end_event_id": None,
                "start_seq": None,
                "end_seq": None,
            }
        return {
            "start_event_id": events[0].get("event_id"),
            "end_event_id": events[-1].get("event_id"),
            "start_seq": events[0].get("event_seq"),
            "end_seq": events[-1].get("event_seq"),
        }

    def event_span(self) -> dict[str, Any]:
        return self.current_event_span()

    def write_state_capsule(
        self,
        *,
        session_id: str | None = None,
        parent_session_id: str | None = None,
        child_session_id: str | None = None,
        event_span: dict[str, Any] | None = None,
        blockers: list[Any] | None = None,
        next_action: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        recovery = self.recover_state()
        span = event_span or self.current_event_span()
        end_seq = span.get("end_seq") or 0
        capsule_id = f"cap_{end_seq:09d}"
        capsule = {
            "schema_version": self.schema_version,
            "capsule_id": capsule_id,
            "created_utc": _utc_now(),
            "run_id": self.run_id,
            "session_id": session_id or self.session_id,
            "parent_session_id": parent_session_id,
            "child_session_id": child_session_id,
            "event_span": span,
            "in_flight": recovery["in_flight"],
            "recent_completed_tools": recovery["recent_completed_tools"],
            "artifact_refs": recovery["artifact_refs"],
            "blockers": _redact_value(blockers or []),
            "next_action": redact_sensitive_text(next_action or "", force=True),
            "notes": redact_sensitive_text(notes or "", force=True),
            "safe_to_publish": False,
        }
        path = self.capsules_dir / f"{capsule_id}.json"
        data = json.dumps(capsule, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
        self._atomic_write(path, data)
        capsule["relative_path"] = path.relative_to(self.run_root).as_posix()
        self.append_event(
            "compression.capsule",
            session_id=session_id or self.session_id,
            status="ok",
            output={"capsule_path": capsule["relative_path"]},
            artifact_refs=[
                {
                    "type": "state_capsule",
                    "path": capsule["relative_path"],
                    "safe_to_publish": False,
                    "redaction_status": "redacted",
                }
            ],
            metadata={"event_span": span, "capsule_id": capsule_id},
        )
        return capsule
