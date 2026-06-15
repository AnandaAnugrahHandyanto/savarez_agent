"""Map an A2A ``contextId`` to a persistent Hermes ``AIAgent`` session.

An A2A *context* is a conversation thread; a *task* is one turn within it. We
hold one ``AIAgent`` (plus its rolling history) per context so follow-up
messages on the same ``contextId`` continue the same conversation — the same
relationship ``acp_adapter.session.SessionManager`` maintains for ACP sessions.

Sessions are in-memory only for this cut (no DB persistence; see
``.plans/a2a-protocol.md``). The real ``AIAgent`` build mirrors
``acp_adapter.session._make_agent``; tests inject a fake via ``agent_factory``.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable

# Hermes ships toolset *profiles* (named bundles of tools). A2A uses the
# dedicated ``hermes-a2a`` profile defined in toolsets.py — a non-interactive
# coding/research bundle (no messaging, audio, or clarify UI), suited to
# agent-to-agent task delegation.
A2A_TOOLSET_PROFILE = "hermes-a2a"

# Cap on concurrently-retained contexts so a long-lived server doesn't grow
# unbounded (one AIAgent + history per context). Least-recently-used contexts
# are evicted past this; a follow-up message on an evicted context simply
# starts a fresh session.
DEFAULT_MAX_SESSIONS = 512


# Upper bound on remembered "cancel arrived before the turn started" task ids,
# so a peer spamming cancels for never-seen tasks can't grow the set unbounded.
_MAX_PENDING_CANCELS = 1024


@dataclass
class HermesSession:
    """One A2A context: a Hermes agent, its history, and a cancel signal."""

    context_id: str
    agent: Any  # AIAgent instance (or a test fake)
    history: list[dict[str, Any]] = field(default_factory=list)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)
    # Guards _active_task_id / _cancelled_task_ids. Distinct from ``lock`` (which
    # serializes whole turns) so cancel() can run without waiting for the turn.
    _state_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _active_task_id: str | None = field(default=None, repr=False)
    _cancelled_task_ids: set[str] = field(default_factory=set, repr=False)

    def run_turn(
        self,
        user_text: str,
        task_id: str,
        *,
        callbacks: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run one blocking agent turn and fold the result into history.

        Called from a worker thread (the agent loop is synchronous). Serialized
        per session by ``lock`` so two tasks on the same context can't race the
        same history.

        ``callbacks`` (name -> callable|None) are bound onto the shared agent
        *inside* the lock and cleared afterwards, so two concurrent turns on the
        same context can never cross-wire their streams onto the other's task.
        """
        with self.lock:
            with self._state_lock:
                # A cancel that raced ahead of this turn starting: skip it.
                if task_id in self._cancelled_task_ids:
                    self._cancelled_task_ids.discard(task_id)
                    return {"final_response": None, "interrupted": True}
                # Clean slate: drop any stale cancel/interrupt left by a prior
                # task before we mark this one active, so a cancel targeting
                # *this* task (arriving after this point) is not erased.
                self.cancel_event.clear()
                self._clear_agent_interrupt()
                self._active_task_id = task_id

            agent = self.agent
            if callbacks:
                for name, cb in callbacks.items():
                    setattr(agent, name, cb)
            try:
                result = agent.run_conversation(
                    user_message=user_text,
                    conversation_history=self.history,
                    task_id=task_id,
                    persist_user_message=user_text,
                )
                if isinstance(result, dict):
                    messages = result.get("messages")
                    if isinstance(messages, list):
                        self.history = messages
                    return result
                return {"final_response": str(result)}
            finally:
                if callbacks:
                    for name in callbacks:
                        setattr(agent, name, None)
                with self._state_lock:
                    self._active_task_id = None

    def is_busy(self) -> bool:
        """True while a turn is executing for this context."""
        with self._state_lock:
            return self._active_task_id is not None

    def cancel(self, task_id: str | None = None) -> None:
        """Cancel a turn on this context.

        ``task_id=None`` cancels whatever is currently running. A specific
        ``task_id`` only interrupts the agent when it is the running turn —
        otherwise it is recorded so the turn is skipped if it starts later
        (covers a cancel that races ahead of ``run_turn``). This prevents one
        task's cancel from killing a different concurrent turn on the same
        context.
        """
        with self._state_lock:
            active = self._active_task_id
            if task_id is not None and task_id != active:
                if len(self._cancelled_task_ids) < _MAX_PENDING_CANCELS:
                    self._cancelled_task_ids.add(task_id)
                return
            self.cancel_event.set()
            self._interrupt_agent()

    def _interrupt_agent(self) -> None:
        interrupt = getattr(self.agent, "interrupt", None)
        if callable(interrupt):
            try:
                interrupt()
            except Exception:
                pass

    def _clear_agent_interrupt(self) -> None:
        clear = getattr(self.agent, "clear_interrupt", None)
        if callable(clear):
            try:
                clear()
            except Exception:
                pass


class ContextSessionStore:
    """Thread-safe ``contextId -> HermesSession`` store with lazy agent creation."""

    def __init__(
        self,
        agent_factory: Callable[[], Any] | None = None,
        *,
        cwd: str = ".",
        max_sessions: int = DEFAULT_MAX_SESSIONS,
    ):
        self._agent_factory = agent_factory
        self._cwd = cwd
        self._max_sessions = max_sessions
        # OrderedDict as an LRU: most-recently-used at the end.
        self._sessions: OrderedDict[str, HermesSession] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, context_id: str) -> HermesSession | None:
        with self._lock:
            session = self._sessions.get(context_id)
            if session is not None:
                self._sessions.move_to_end(context_id)
            return session

    def get_or_create(self, context_id: str) -> HermesSession:
        with self._lock:
            session = self._sessions.get(context_id)
            if session is not None:
                self._sessions.move_to_end(context_id)
                return session
            session = HermesSession(
                context_id=context_id,
                agent=self._make_agent(context_id),
            )
            self._sessions[context_id] = session
            self._evict_lru()
            return session

    def remove(self, context_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(context_id, None) is not None

    def _evict_lru(self) -> None:
        """Drop least-recently-used *idle* sessions past the configured cap.

        Sessions with a turn in flight are skipped — evicting one would orphan
        the running worker thread and silently fork its history into a fresh,
        empty agent on the next message. If every session over the cap is busy,
        the store temporarily overshoots rather than corrupting a live turn.

        Caller must hold ``self._lock``.
        """
        if not self._max_sessions:
            return
        while len(self._sessions) > self._max_sessions:
            victim = next(
                (cid for cid, sess in self._sessions.items() if not sess.is_busy()),
                None,
            )
            if victim is None:
                break  # all over-cap sessions are busy; allow temporary overshoot
            del self._sessions[victim]

    def _make_agent(self, context_id: str) -> Any:
        if self._agent_factory is not None:
            return self._agent_factory()

        # Real runtime build — mirrors acp_adapter.session._make_agent so the
        # A2A agent picks up the user's configured provider/model and toolsets.
        from run_agent import AIAgent
        from hermes_cli.config import load_config
        from hermes_cli.runtime_provider import resolve_runtime_provider

        config = load_config()
        model_cfg = config.get("model")
        default_model = ""
        config_provider = None
        if isinstance(model_cfg, dict):
            default_model = str(model_cfg.get("default") or "")
            config_provider = model_cfg.get("provider")
        elif isinstance(model_cfg, str) and model_cfg.strip():
            default_model = model_cfg.strip()

        mcp_servers = [
            name
            for name, cfg in (config.get("mcp_servers") or {}).items()
            if not isinstance(cfg, dict) or cfg.get("enabled", True) is not False
        ]
        enabled_toolsets = [A2A_TOOLSET_PROFILE] + [f"mcp-{n}" for n in mcp_servers]

        kwargs: dict[str, Any] = {
            "platform": "a2a",
            "enabled_toolsets": enabled_toolsets,
            "quiet_mode": True,
            "session_id": context_id,
            "model": default_model,
        }
        try:
            runtime = resolve_runtime_provider(requested=config_provider)
            kwargs.update({
                "provider": runtime.get("provider"),
                "api_mode": runtime.get("api_mode"),
                "base_url": runtime.get("base_url"),
                "api_key": runtime.get("api_key"),
                "command": runtime.get("command"),
                "args": list(runtime.get("args") or []),
            })
        except Exception:
            # Fall back to AIAgent's own default provider resolution.
            pass

        return AIAgent(**kwargs)
