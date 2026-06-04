"""Tests for :mod:`agent.copilot_acp_persistent`.

These tests use a stub subprocess so the real GitHub Copilot CLI is never
launched. The stub exposes the same triplet (``stdin`` / ``stdout`` / ``stderr``)
plus ``poll`` / ``terminate`` / ``wait`` / ``kill`` and lets each test drive
the JSON-RPC dialogue line by line.

The goal is to assert four things about the persistent variant:

1. ``initialize`` + ``session/new`` happen once, regardless of how many
   chat completions a client makes against the same instance.
2. ``cancel()`` emits a JSON-RPC ``session/cancel`` notification (no id,
   no response wait) addressed to the cached session id.
3. If the subprocess dies between completions, the next completion
   transparently reboots via ``ensure_started``.
4. The inbound safety surface (``session/request_permission``,
   ``fs/read_text_file``, ``fs/write_text_file``) matches the one-shot
   ``CopilotACPClient`` — deny default + workspace-bounded fs.

All asserts run with a stub process. No real CLI is spawned.
"""

from __future__ import annotations

import io
import json
import os
import queue
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch


# Importing the module under test depends on the rest of the Hermes agent
# package being importable. We use a small bootstrap to make `agent.*` resolve
# against the production install while loading the persistent client out of
# this worktree by file path.
#
# Once this card lands in hermes-agent proper, the bootstrap collapses to a
# plain `from agent.copilot_acp_persistent import PersistentCopilotACPClient`
# — both `_HERMES_AGENT_ROOT` and the importlib detour drop away.
import importlib.util
import sys

_HERMES_AGENT_ROOT = os.environ.get(
    "HERMES_AGENT_ROOT", "/home/filip/.hermes/hermes-agent"
)
if _HERMES_AGENT_ROOT and _HERMES_AGENT_ROOT not in sys.path:
    sys.path.insert(0, _HERMES_AGENT_ROOT)


def _load_persistent_module():
    if "agent.copilot_acp_persistent" in sys.modules:
        return sys.modules["agent.copilot_acp_persistent"]
    candidate = Path(__file__).resolve().parents[2] / "agent" / "copilot_acp_persistent.py"
    if not candidate.exists():
        return importlib.import_module("agent.copilot_acp_persistent")
    spec = importlib.util.spec_from_file_location(
        "agent.copilot_acp_persistent", candidate
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["agent.copilot_acp_persistent"] = module
    spec.loader.exec_module(module)
    return module


PersistentCopilotACPClient = _load_persistent_module().PersistentCopilotACPClient  # noqa: E402


# ── Stub subprocess ──────────────────────────────────────────────────────


class _StubStdout:
    """Iterable stdout backed by a queue + a sentinel for EOF.

    A test pushes JSON-RPC response lines via ``push_line`` and ends the
    stream with ``close_stream``. Iteration blocks until the next line or
    EOF arrives, mirroring how :class:`subprocess.Popen` exposes stdout.
    """

    _EOF = object()

    def __init__(self) -> None:
        self._q: queue.Queue[object] = queue.Queue()

    def push_line(self, line: str) -> None:
        self._q.put(line if line.endswith("\n") else line + "\n")

    def push_json(self, obj: dict) -> None:
        self.push_line(json.dumps(obj))

    def close_stream(self) -> None:
        self._q.put(self._EOF)

    def __iter__(self):
        return self

    def __next__(self) -> str:
        item = self._q.get()
        if item is self._EOF:
            raise StopIteration
        return item  # type: ignore[return-value]


class _StubProcess:
    """Subprocess.Popen-shaped stand-in for tests.

    ``stdin`` captures everything the client wrote (one line per JSON-RPC
    message). ``stdout`` is a driveable iterable; ``stderr`` is a passive
    StringIO. ``poll()`` returns ``None`` until the test calls ``die``.
    """

    def __init__(self) -> None:
        self.stdin = io.StringIO()
        self.stdout = _StubStdout()
        self.stderr = io.StringIO()
        self._returncode: int | None = None
        self.terminated = False
        self.killed = False

    # Subprocess.Popen interface ------------------------------------------------

    def poll(self) -> int | None:
        return self._returncode

    def terminate(self) -> None:
        self.terminated = True
        self._returncode = -15
        self.stdout.close_stream()

    def wait(self, timeout: float | None = None) -> int:
        return self._returncode if self._returncode is not None else 0

    def kill(self) -> None:
        self.killed = True
        self._returncode = -9
        self.stdout.close_stream()

    # Test helpers --------------------------------------------------------------

    def die(self, returncode: int = 1) -> None:
        self._returncode = returncode
        self.stdout.close_stream()

    def stdin_lines(self) -> list[str]:
        return [line for line in self.stdin.getvalue().splitlines() if line.strip()]

    def stdin_messages(self) -> list[dict]:
        return [json.loads(line) for line in self.stdin_lines()]


class _SubprocessFactory:
    """Records the processes it created so tests can inspect them."""

    def __init__(self) -> None:
        self.processes: list[_StubProcess] = []
        self.calls: list[dict] = []

    def __call__(self, cmd, **kwargs) -> _StubProcess:
        self.calls.append({"cmd": cmd, "kwargs": kwargs})
        proc = _StubProcess()
        self.processes.append(proc)
        return proc


def _wait_for(predicate, timeout: float = 2.0, interval: float = 0.01) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


class _ResponderThread:
    """Reads the stub's stdin and emits canned responses.

    Each request method maps to a callback that returns the result dict the
    server should send. ``session_update_emit`` lets a test inject inbound
    ``session/update`` notifications mid-prompt so the streaming buffer code
    path is exercised.
    """

    def __init__(
        self,
        proc: _StubProcess,
        handlers: dict,
        *,
        session_id: str = "sess-1",
        on_prompt_notifications: list[dict] | None = None,
    ) -> None:
        self.proc = proc
        self.handlers = handlers
        self.session_id = session_id
        self.on_prompt_notifications = on_prompt_notifications or []
        self.observed: list[dict] = []
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._stop = threading.Event()

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1)

    def _run(self) -> None:
        seen = 0
        while not self._stop.is_set():
            lines = self.proc.stdin_lines()
            while seen < len(lines) and not self._stop.is_set():
                line = lines[seen]
                seen += 1
                try:
                    msg = json.loads(line)
                except Exception:
                    continue
                self.observed.append(msg)
                method = msg.get("method")
                # Notifications (no id) carry no response.
                if "id" not in msg:
                    continue
                handler = self.handlers.get(method)
                if handler is None:
                    self.proc.stdout.push_json(
                        {
                            "jsonrpc": "2.0",
                            "id": msg["id"],
                            "error": {"code": -32601, "message": f"unknown {method}"},
                        }
                    )
                    continue
                if method == "session/prompt":
                    for notif in self.on_prompt_notifications:
                        self.proc.stdout.push_json(notif)
                result = handler(msg)
                self.proc.stdout.push_json(
                    {"jsonrpc": "2.0", "id": msg["id"], "result": result}
                )
            time.sleep(0.005)


def _default_handlers(session_id: str = "sess-1") -> dict:
    return {
        "initialize": lambda msg: {"protocolVersion": 1},
        "session/new": lambda msg: {"sessionId": session_id},
        "session/prompt": lambda msg: {"stopReason": "end_turn"},
    }


# ── Tests ────────────────────────────────────────────────────────────────


class PersistentClientSessionReuseTests(unittest.TestCase):
    """initialize + session/new fire once, not per completion."""

    def test_session_is_reused_across_completions(self) -> None:
        factory = _SubprocessFactory()
        client = PersistentCopilotACPClient(acp_cwd="/tmp", _subprocess_factory=factory)
        self.addCleanup(client.close)

        # Allow ensure_started + each completion to find a responder.
        try:
            handlers = _default_handlers()
            responder: _ResponderThread | None = None

            agent_chunks = [
                {
                    "jsonrpc": "2.0",
                    "method": "session/update",
                    "params": {
                        "update": {
                            "sessionUpdate": "agent_message_chunk",
                            "content": {"text": "hello"},
                        }
                    },
                }
            ]

            # Boot the subprocess by calling ensure_started so we can attach a
            # responder to the freshly created process before sending prompts.
            ensure_done = threading.Event()
            ensure_err: list[BaseException] = []

            def _do_ensure() -> None:
                try:
                    client.ensure_started()
                except BaseException as exc:  # pragma: no cover
                    ensure_err.append(exc)
                finally:
                    ensure_done.set()

            t = threading.Thread(target=_do_ensure, daemon=True)
            t.start()
            self.assertTrue(_wait_for(lambda: len(factory.processes) >= 1))
            proc = factory.processes[0]
            responder = _ResponderThread(
                proc,
                handlers,
                on_prompt_notifications=agent_chunks,
            )
            responder.start()

            self.assertTrue(ensure_done.wait(timeout=2))
            if ensure_err:
                raise ensure_err[0]

            # Two back-to-back completions should NOT spawn a second process.
            resp1 = client.chat.completions.create(
                model="gpt-test",
                messages=[{"role": "user", "content": "ping"}],
                timeout=2.0,
            )
            resp2 = client.chat.completions.create(
                model="gpt-test",
                messages=[{"role": "user", "content": "again"}],
                timeout=2.0,
            )
        finally:
            if responder is not None:
                responder.stop()

        self.assertEqual(resp1.choices[0].message.content, "hello")
        self.assertEqual(resp2.choices[0].message.content, "hello")
        self.assertEqual(len(factory.processes), 1, "subprocess should boot only once")

        methods = [m.get("method") for m in proc.stdin_messages()]
        self.assertEqual(methods.count("initialize"), 1)
        self.assertEqual(methods.count("session/new"), 1)
        self.assertEqual(methods.count("session/prompt"), 2)


class PersistentClientCancelTests(unittest.TestCase):
    def test_cancel_emits_session_cancel_notification(self) -> None:
        factory = _SubprocessFactory()
        client = PersistentCopilotACPClient(acp_cwd="/tmp", _subprocess_factory=factory)
        self.addCleanup(client.close)

        responder: _ResponderThread | None = None
        try:
            handlers = _default_handlers(session_id="sess-cancel")
            ensure_done = threading.Event()

            def _do_ensure() -> None:
                try:
                    client.ensure_started()
                finally:
                    ensure_done.set()

            threading.Thread(target=_do_ensure, daemon=True).start()
            self.assertTrue(_wait_for(lambda: len(factory.processes) >= 1))
            proc = factory.processes[0]
            responder = _ResponderThread(proc, handlers, session_id="sess-cancel")
            responder.start()
            self.assertTrue(ensure_done.wait(timeout=2))

            client.cancel()
        finally:
            if responder is not None:
                responder.stop()

        msgs = proc.stdin_messages()
        cancels = [m for m in msgs if m.get("method") == "session/cancel"]
        self.assertEqual(len(cancels), 1)
        cancel = cancels[0]
        # session/cancel is a notification: no id.
        self.assertNotIn("id", cancel)
        self.assertEqual(cancel.get("params", {}).get("sessionId"), "sess-cancel")

    def test_cancel_is_noop_when_not_started(self) -> None:
        factory = _SubprocessFactory()
        client = PersistentCopilotACPClient(acp_cwd="/tmp", _subprocess_factory=factory)
        self.addCleanup(client.close)

        client.cancel()  # must not raise, must not boot a process.
        self.assertEqual(factory.processes, [])


class PersistentClientReconnectTests(unittest.TestCase):
    def test_dead_subprocess_is_rebooted_on_next_completion(self) -> None:
        factory = _SubprocessFactory()
        client = PersistentCopilotACPClient(acp_cwd="/tmp", _subprocess_factory=factory)
        self.addCleanup(client.close)

        responders: list[_ResponderThread] = []
        try:
            # Boot the first session.
            ensure_done = threading.Event()

            def _do_ensure() -> None:
                try:
                    client.ensure_started()
                finally:
                    ensure_done.set()

            threading.Thread(target=_do_ensure, daemon=True).start()
            self.assertTrue(_wait_for(lambda: len(factory.processes) >= 1))
            proc1 = factory.processes[0]
            r1 = _ResponderThread(proc1, _default_handlers("sess-1"))
            r1.start()
            responders.append(r1)
            self.assertTrue(ensure_done.wait(timeout=2))

            # Kill the first process to simulate a crash between calls.
            proc1.die(returncode=1)
            r1.stop()

            # Next completion should transparently spawn a fresh subprocess
            # and a fresh session id.
            done = threading.Event()
            result: list = []
            err: list[BaseException] = []

            def _do_call() -> None:
                try:
                    result.append(
                        client.chat.completions.create(
                            model="gpt-test",
                            messages=[{"role": "user", "content": "after-restart"}],
                            timeout=2.0,
                        )
                    )
                except BaseException as exc:  # pragma: no cover
                    err.append(exc)
                finally:
                    done.set()

            threading.Thread(target=_do_call, daemon=True).start()
            self.assertTrue(_wait_for(lambda: len(factory.processes) >= 2))
            proc2 = factory.processes[1]
            r2 = _ResponderThread(
                proc2,
                _default_handlers("sess-2"),
                on_prompt_notifications=[
                    {
                        "jsonrpc": "2.0",
                        "method": "session/update",
                        "params": {
                            "update": {
                                "sessionUpdate": "agent_message_chunk",
                                "content": {"text": "back"},
                            }
                        },
                    }
                ],
            )
            r2.start()
            responders.append(r2)

            self.assertTrue(done.wait(timeout=3))
            if err:
                raise err[0]
        finally:
            for r in responders:
                r.stop()

        self.assertEqual(len(factory.processes), 2, "expected a second process after crash")
        self.assertEqual(result[0].choices[0].message.content, "back")


class PersistentClientSafetyTests(unittest.TestCase):
    """The persistent client's inbound handler must match the one-shot client."""

    def setUp(self) -> None:
        self.client = PersistentCopilotACPClient(acp_cwd="/tmp")

    def _dispatch(self, message: dict, *, cwd: str) -> dict:
        process = _StubProcess()
        handled = self.client._handle_server_message(
            message,
            process=process,
            cwd=cwd,
            text_parts=[],
            reasoning_parts=[],
        )
        self.assertTrue(handled)
        payload = process.stdin.getvalue().strip()
        self.assertTrue(payload)
        return json.loads(payload)

    def test_request_permission_denies_by_default(self) -> None:
        response = self._dispatch(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "session/request_permission",
                "params": {},
            },
            cwd="/tmp",
        )
        outcome = (((response.get("result") or {}).get("outcome") or {}).get("outcome"))
        self.assertEqual(outcome, "cancelled")

    def test_read_text_file_blocks_hub_internals(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir) / "home"
            blocked = home / ".hermes" / "skills" / ".hub" / "index-cache" / "entry.json"
            blocked.parent.mkdir(parents=True, exist_ok=True)
            blocked.write_text('{"token":"sk-test-secret-1234567890"}')

            with patch.dict(
                os.environ,
                {"HOME": str(home), "HERMES_HOME": str(home / ".hermes")},
                clear=False,
            ):
                response = self._dispatch(
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "fs/read_text_file",
                        "params": {"path": str(blocked)},
                    },
                    cwd=str(home),
                )
        self.assertIn("error", response)

    def test_read_text_file_redacts_sensitive_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            secret_file = root / "config.env"
            secret_file.write_text("OPENAI_API_KEY=sk-proj-abc123def456ghi789jkl012")

            with patch("agent.redact._REDACT_ENABLED", True):
                response = self._dispatch(
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "fs/read_text_file",
                        "params": {"path": str(secret_file)},
                    },
                    cwd=str(root),
                )

        content = ((response.get("result") or {}).get("content") or "")
        self.assertNotIn("abc123def456", content)
        self.assertIn("OPENAI_API_KEY=", content)

    def test_write_text_file_reuses_write_denylist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir) / "home"
            target = home / ".ssh" / "id_rsa"
            target.parent.mkdir(parents=True, exist_ok=True)

            with patch(
                "agent.copilot_acp_persistent.is_write_denied",
                return_value=True,
                create=True,
            ):
                response = self._dispatch(
                    {
                        "jsonrpc": "2.0",
                        "id": 4,
                        "method": "fs/write_text_file",
                        "params": {
                            "path": str(target),
                            "content": "fake-private-key",
                        },
                    },
                    cwd=str(home),
                )
        self.assertIn("error", response)
        self.assertFalse(target.exists())

    def test_write_text_file_blocks_path_escapes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            inside = root / "workspace"
            inside.mkdir()
            outside = root / "outside.txt"

            response = self._dispatch(
                {
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "fs/write_text_file",
                    "params": {
                        "path": str(outside),
                        "content": "should-not-write",
                    },
                },
                cwd=str(inside),
            )
        self.assertIn("error", response)
        self.assertFalse(outside.exists())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
