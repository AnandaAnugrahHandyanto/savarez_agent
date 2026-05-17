"""In-process chat session that drives AIAgent and streams events to the browser.

A ChatSession owns:
  - a long-lived AIAgent (constructed once, reused across turns, so the
    prompt cache survives — see AGENTS.md "Important Policies")
  - an asyncio.Queue of SSE-formatted strings (the SSE generator drains it)
  - pending approval/clarify futures (threading.Event + result box per call)
  - a worker thread that runs the sync run_conversation() per turn
  - a cancel event the agent loop can poll between iterations

Why threads + asyncio?  AIAgent.run_conversation is sync and blocking.  It
calls tool/stream callbacks from its own thread.  We bridge those into the
FastAPI event loop via loop.call_soon_threadsafe, then the SSE generator
yields them.

The browser only sees structured events; correlating call_id is the
contract between approval-request events and the POST /approve endpoint.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# How long an idle approval/clarify waits before defaulting to "deny" / "".
_APPROVAL_TIMEOUT_SECONDS = 300
_CLARIFY_TIMEOUT_SECONDS = 300

# How long an idle ChatSession lives before the registry evicts it.
_SESSION_IDLE_TIMEOUT_SECONDS = 60 * 60  # 1 hour


def _sse_format(event: str, data: Dict[str, Any]) -> str:
    """Format a structured event as an SSE frame."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@dataclass
class PendingResponse:
    """A blocked agent-thread call awaiting a browser response."""
    event: threading.Event = field(default_factory=threading.Event)
    result: List[Any] = field(default_factory=lambda: [None])


class ChatSession:
    """One browser tab = one ChatSession.  Owns its AIAgent across turns."""

    def __init__(self, session_id: str, loop: asyncio.AbstractEventLoop):
        self.session_id = session_id
        self.loop = loop
        self.queue: "asyncio.Queue[str]" = asyncio.Queue()
        self.history: List[Dict[str, Any]] = []
        self.agent = None  # lazy — built on first turn
        self.pending_approvals: Dict[str, PendingResponse] = {}
        self.pending_clarifies: Dict[str, PendingResponse] = {}
        self.cancel_event = threading.Event()  # set by /cancel, polled by Step 6
        self.last_activity = time.time()
        self.lock = threading.Lock()
        self._worker: Optional[threading.Thread] = None
        self._closed = False

    # ------------------------------------------------------------------ #
    # Event emission                                                      #
    # ------------------------------------------------------------------ #

    def _emit(self, event_name: str, data: Dict[str, Any]) -> None:
        """Push an SSE-formatted event onto the queue from any thread."""
        if self._closed:
            return
        frame = _sse_format(event_name, data)
        try:
            self.loop.call_soon_threadsafe(self.queue.put_nowait, frame)
        except RuntimeError:
            # Event loop is closed (server shutdown) — drop the event.
            logger.debug("ChatSession %s: event loop closed, dropping %s", self.session_id, event_name)

    # ------------------------------------------------------------------ #
    # Approval / clarify bridges                                          #
    # ------------------------------------------------------------------ #

    def _approval_callback(self, command: str, description: str, *, allow_permanent: bool = True) -> str:
        """Bridges tools/approval.prompt_dangerous_approval → browser modal.

        Called from the agent thread.  Blocks until POST /approve resolves
        the matching call_id or the timeout fires.
        """
        call_id = uuid.uuid4().hex
        pending = PendingResponse()
        self.pending_approvals[call_id] = pending
        self._emit("approval-request", {
            "call_id": call_id,
            "command": command,
            "description": description,
            "allow_permanent": allow_permanent,
        })
        if not pending.event.wait(timeout=_APPROVAL_TIMEOUT_SECONDS):
            # Timed out — clean up and default-deny.
            self.pending_approvals.pop(call_id, None)
            logger.warning("Approval timed out for session %s call %s", self.session_id, call_id)
            return "deny"
        return pending.result[0] or "deny"

    def resolve_approval(self, call_id: str, decision: str) -> bool:
        pending = self.pending_approvals.pop(call_id, None)
        if pending is None:
            return False
        pending.result[0] = decision
        pending.event.set()
        return True

    def _clarify_callback(self, question: str, choices: Optional[List[str]] = None) -> str:
        """Bridges agent's clarify hook → browser modal.

        Returns the chosen option or freeform text.  Empty string on timeout.
        """
        call_id = uuid.uuid4().hex
        pending = PendingResponse()
        self.pending_clarifies[call_id] = pending
        self._emit("clarify-request", {
            "call_id": call_id,
            "question": question,
            "choices": list(choices or []),
        })
        if not pending.event.wait(timeout=_CLARIFY_TIMEOUT_SECONDS):
            self.pending_clarifies.pop(call_id, None)
            logger.warning("Clarify timed out for session %s call %s", self.session_id, call_id)
            return ""
        return pending.result[0] or ""

    def resolve_clarify(self, call_id: str, answer: str) -> bool:
        pending = self.pending_clarifies.pop(call_id, None)
        if pending is None:
            return False
        pending.result[0] = answer
        pending.event.set()
        return True

    # ------------------------------------------------------------------ #
    # Turn execution                                                      #
    # ------------------------------------------------------------------ #

    def _build_agent(self):
        """Lazy-construct AIAgent on first turn.  Reused across turns."""
        if self.agent is not None:
            return self.agent

        # Import inside the method — AIAgent's import chain is heavy.
        from run_agent import AIAgent
        from hermes_cli.config import load_config
        from hermes_cli.runtime_provider import resolve_runtime_provider
        from hermes_state import SessionDB

        cfg = load_config()
        model_cfg = cfg.get("model") if isinstance(cfg.get("model"), dict) else {}
        model = model_cfg.get("default") or model_cfg.get("model") or cfg.get("model") or ""
        if not isinstance(model, str) or not model.strip():
            raise RuntimeError("No model configured. Set `model.default` in ~/.hermes/config.yaml.")

        runtime = resolve_runtime_provider()
        # resolve_runtime_provider returns extra keys AIAgent doesn't accept;
        # filter to the kwargs the constructor actually takes.
        runtime_keys = {"api_key", "base_url", "provider", "api_mode",
                        "command", "args", "acp_command", "acp_args",
                        "credential_pool"}
        runtime_kwargs = {k: v for k, v in runtime.items() if k in runtime_keys}

        # Persist messages to the same SessionDB used by /api/sessions, so the
        # Sessions page sees this chat.
        session_db = SessionDB()
        session_db.create_session(session_id=self.session_id, source="web")

        self.agent = AIAgent(
            model=model,
            **runtime_kwargs,
            quiet_mode=True,
            verbose_logging=False,
            session_id=self.session_id,
            platform="web",
            session_db=session_db,
            clarify_callback=self._clarify_callback,
        )
        return self.agent

    def send(self, user_text: str) -> None:
        """Start a turn in a background worker thread.  Returns immediately.

        Raises if a previous turn is still running.
        """
        with self.lock:
            if self._worker is not None and self._worker.is_alive():
                raise RuntimeError("A turn is already in progress")
            self.cancel_event.clear()
            self.last_activity = time.time()
            t = threading.Thread(target=self._run_turn, args=(user_text,), daemon=True,
                                 name=f"chat-{self.session_id[:8]}")
            self._worker = t
            t.start()

    def _run_turn(self, user_text: str) -> None:
        """Worker-thread entry point.  Runs one agent turn end-to-end."""
        call_id = uuid.uuid4().hex
        self._emit("turn-start", {"call_id": call_id})
        try:
            agent = self._build_agent()
            # Per-turn callbacks — match the gateway pattern (gateway/run.py:8887).
            agent.stream_delta_callback = self._on_stream_delta
            agent.tool_start_callback = self._on_tool_start
            agent.tool_complete_callback = self._on_tool_complete
            # Clear any pending interrupt from a previous turn before starting.
            try:
                agent.clear_interrupt()
            except Exception:
                pass

            # Install web approval handler (module-global in terminal_tool).
            import tools.terminal_tool as _term
            previous = _term._approval_callback  # current value, may be None
            _term.set_approval_callback(self._approval_callback)
            try:
                result = agent.run_conversation(
                    user_text,
                    conversation_history=self.history,
                )
            finally:
                _term.set_approval_callback(previous)

            self.history = result.get("messages", self.history) or self.history
            final_text = result.get("final_response", "") or ""
            self._emit("turn-end", {"call_id": call_id, "final_text": final_text})
        except Exception as e:  # noqa: BLE001
            logger.exception("ChatSession %s turn failed", self.session_id)
            self._emit("error", {"call_id": call_id, "detail": str(e)})
        finally:
            self.last_activity = time.time()

    # ------------------------------------------------------------------ #
    # Per-turn agent callbacks                                            #
    # ------------------------------------------------------------------ #

    def _on_stream_delta(self, delta: str) -> None:
        if delta:
            self._emit("text-delta", {"delta": delta})

    def _on_tool_start(self, call_id: str, name: str, args: Any) -> None:
        # args may be a dict or a JSON string; render a short summary
        summary = ""
        try:
            if isinstance(args, dict):
                summary = json.dumps(args, ensure_ascii=False)[:200]
            else:
                summary = str(args)[:200]
        except Exception:
            summary = ""
        self._emit("tool-call-start", {
            "call_id": call_id,
            "tool": name,
            "args_summary": summary,
        })

    def _on_tool_complete(self, call_id: str, name: str, args: Any, result: Any) -> None:
        ok = True
        summary = ""
        try:
            if isinstance(result, str):
                parsed = json.loads(result) if result.lstrip().startswith("{") else None
                if isinstance(parsed, dict):
                    ok = bool(parsed.get("success", True))
                    summary = parsed.get("error") or parsed.get("message") or ""
                else:
                    summary = result[:200]
            elif isinstance(result, dict):
                ok = bool(result.get("success", True))
                summary = result.get("error") or result.get("message") or ""
        except Exception:
            summary = ""
        self._emit("tool-call-result", {
            "call_id": call_id,
            "tool": name,
            "ok": ok,
            "summary": str(summary)[:200],
        })

    # ------------------------------------------------------------------ #
    # SSE stream + lifecycle                                              #
    # ------------------------------------------------------------------ #

    async def stream(self):
        """Async generator yielding SSE frames for the entire session.

        Stays open until the caller disconnects or .close() is called.
        Multiple turns share the same stream.
        """
        # Initial hello so the client knows the connection is live.
        yield _sse_format("status", {"kind": "connected", "session_id": self.session_id})
        while not self._closed:
            try:
                frame = await asyncio.wait_for(self.queue.get(), timeout=15.0)
                yield frame
            except asyncio.TimeoutError:
                # Heartbeat keeps proxies from idle-killing the connection.
                yield ": keepalive\n\n"
            except asyncio.CancelledError:
                # Client disconnected.
                logger.debug("ChatSession %s stream cancelled", self.session_id)
                break

    def cancel_turn(self) -> bool:
        """Interrupt the agent mid-turn via AIAgent.interrupt().

        AIAgent's interrupt() flips an internal flag the tool loop polls,
        and propagates to any subagents and in-flight tool executions.
        Returns True if there was a turn in progress to cancel.
        """
        self.cancel_event.set()
        running = self._worker is not None and self._worker.is_alive()
        agent = self.agent
        if agent is not None and running:
            try:
                agent.interrupt(message=None)
            except Exception:
                logger.exception("ChatSession %s: agent.interrupt() raised", self.session_id)
        return running

    def close(self) -> None:
        """Tear down the session and unblock any pending waits."""
        self._closed = True
        for p in list(self.pending_approvals.values()):
            p.event.set()
        for p in list(self.pending_clarifies.values()):
            p.event.set()

    # ------------------------------------------------------------------ #
    # History (for reattach)                                              #
    # ------------------------------------------------------------------ #

    def load_history_from_db(self) -> None:
        """Replay messages from SessionDB into self.history.

        Used by the registry when reattaching to a session_id that the
        in-process registry has evicted but the DB still has.
        """
        try:
            from hermes_state import SessionDB
            db = SessionDB()
            self.history = db.get_messages_as_conversation(self.session_id) or []
        except Exception:
            logger.exception("Failed to load history for %s", self.session_id)
            self.history = []


# ====================================================================== #
# Registry                                                                #
# ====================================================================== #

_registry: Dict[str, ChatSession] = {}
_registry_lock = threading.Lock()


def create_session(loop: asyncio.AbstractEventLoop) -> ChatSession:
    """Create a fresh ChatSession with a new UUID session_id."""
    session_id = uuid.uuid4().hex
    sess = ChatSession(session_id, loop)
    with _registry_lock:
        _registry[session_id] = sess
        _evict_idle_locked()
    return sess


def get_or_reattach(session_id: str, loop: asyncio.AbstractEventLoop) -> Optional[ChatSession]:
    """Return an existing session, or rebuild one from SessionDB history.

    Returns None if no record exists anywhere.
    """
    with _registry_lock:
        sess = _registry.get(session_id)
        if sess is not None:
            sess.last_activity = time.time()
            return sess

    # Not in-process — try to reattach from DB.
    try:
        from hermes_state import SessionDB
        db = SessionDB()
        record = db.get_session(session_id)
    except Exception:
        record = None
    if record is None:
        return None

    sess = ChatSession(session_id, loop)
    sess.load_history_from_db()
    with _registry_lock:
        _registry[session_id] = sess
    return sess


def get(session_id: str) -> Optional[ChatSession]:
    with _registry_lock:
        return _registry.get(session_id)


def remove(session_id: str) -> bool:
    with _registry_lock:
        sess = _registry.pop(session_id, None)
    if sess is None:
        return False
    sess.close()
    return True


def _evict_idle_locked() -> None:
    """Drop sessions idle for too long.  Caller holds _registry_lock."""
    now = time.time()
    stale = [
        sid for sid, sess in _registry.items()
        if now - sess.last_activity > _SESSION_IDLE_TIMEOUT_SECONDS
    ]
    for sid in stale:
        sess = _registry.pop(sid)
        sess.close()
        logger.info("Evicted idle chat session %s", sid)
