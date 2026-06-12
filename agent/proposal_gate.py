"""Proposal Gate — block tool execution until acknowledged side effects resolve.

Inspired by holaOS's integration-proposal-gate.ts: when the agent emits
one or more ``propose_*`` style tool calls in a turn (e.g. ``delegate_task``,
``mcp_add``, ``cron create``, ``memory add`` with side-effects), the UI may
display confirmation cards.  If the user fires the next turn before those
cards resolve, the old flow would dispatch immediately — running the
side-effect with whatever default the system picked, often silently
half-completing the work.

This module introduces a per-session, per-tool gate.  A tool that
declares ``requires_acknowledgment: True`` and produces a
``proposal_id`` in its result will mark that proposal as
``pending``.  While a proposal is pending, subsequent turns are
**not blocked**, but a follow-up call to the same tool (or any
``ack_required`` tool listed in the same ``pending_group``) that
tries to act on a still-pending proposal is rejected with a
``ProposalPendingError``.  The LLM sees the error and is expected to
ask the user to acknowledge first.

The gate is intentionally:

- In-process (per AIAgent instance).  No cross-process state, no
  persistence beyond the lifetime of the session.  This matches
  holaOS's per-session state model.
- Fail-open: if a tool's schema lacks the new keys, the gate is a
  no-op for that tool.  This keeps backward compatibility with all
  existing tools.
- Thread-safe via a single lock (gate is small; one lock is fine).

Wire-up
-------
- Tools that want to opt in: add ``"requires_acknowledgment": True``
  to their registered schema's metadata (in ``tools/registry.py``).
  Return ``{"proposal_id": "...", "proposal_group": "...", "ack_required": [...]}``
  in the result.  The gate auto-registers the proposal.
- Code that wants to acknowledge: call ``ack_proposal(proposal_id)``
  (or ``ack_proposal_group(group_id)``).  CLI / gateway / API routes
  can expose this.
- Code that wants to clear (e.g. session reset / new session):
  ``clear_session(session_id)``.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class ProposalPendingError(Exception):
    """Raised when a tool call is gated by a pending acknowledgment.

    The error message is suitable for inclusion in the tool result
    returned to the LLM (it explains what is pending and how to
    resolve it).
    """

    def __init__(
        self,
        message: str,
        *,
        proposal_id: str = "",
        proposal_group: str = "",
        pending_tool: str = "",
        ack_required: Optional[List[str]] = None,
    ) -> None:
        super().__init__(message)
        self.proposal_id = proposal_id
        self.proposal_group = proposal_group
        self.pending_tool = pending_tool
        self.ack_required = list(ack_required or [])

    def to_tool_error(self) -> str:
        """Return a JSON string suitable as a tool-call result."""
        import json
        return json.dumps(
            {
                "error": str(self),
                "proposal_id": self.proposal_id,
                "proposal_group": self.proposal_group,
                "pending_tool": self.pending_tool,
                "ack_required": self.ack_required,
            },
            ensure_ascii=False,
        )


@dataclass
class _Proposal:
    """Internal record for a pending proposal."""

    proposal_id: str
    proposal_group: str
    tool: str
    ack_required: List[str] = field(default_factory=list)
    created_at: float = 0.0  # monotonic time, set on registration

    def describe(self) -> str:
        req = ""
        if self.ack_required:
            req = f" (ack_required: {', '.join(self.ack_required)})"
        return f"proposal {self.proposal_id!r} from tool {self.tool!r}{req}"


class ProposalGate:
    """Per-session store of pending acknowledgment-gated tool calls.

    Use one instance per AIAgent (or one per gateway session, if you
    prefer per-session lifetime).  Methods are thread-safe.
    """

    def __init__(self) -> None:
        # proposal_id -> _Proposal
        self._by_id: Dict[str, _Proposal] = {}
        # group_id -> set of proposal_id (so we can ack all at once)
        self._by_group: Dict[str, Set[str]] = {}
        self._lock = threading.Lock()

    # -- Registration ----------------------------------------------------

    def register(
        self,
        *,
        proposal_id: str,
        proposal_group: str = "",
        tool: str,
        ack_required: Optional[Iterable[str]] = None,
    ) -> None:
        """Record a new pending proposal.

        Called by ``handle_function_call`` when a tool returns a
        ``proposal_id`` in its result.  Idempotent: re-registering an
        existing ``proposal_id`` is a no-op.
        """
        if not proposal_id:
            return
        with self._lock:
            if proposal_id in self._by_id:
                return
            import time
            self._by_id[proposal_id] = _Proposal(
                proposal_id=proposal_id,
                proposal_group=proposal_group or "",
                tool=tool,
                ack_required=list(ack_required or []),
                created_at=time.monotonic(),
            )
            if proposal_group:
                self._by_group.setdefault(proposal_group, set()).add(proposal_id)
        logger.debug("proposal_gate: registered %s", proposal_id)

    # -- Check ------------------------------------------------------------

    def check(
        self,
        *,
        tool: str,
        args: Dict[str, Any],
        session_id: str = "",
    ) -> None:
        """Raise :class:`ProposalPendingError` if a follow-up tool is gated.

        The default policy is: any tool that opts in to the gate
        (``requires_acknowledgment`` in its schema, OR explicitly
        names ``ack_required`` fields) cannot run while **any**
        proposal in the same group is pending.

        ``args`` is inspected for an ``ack_proposal_id`` field — if
        the LLM is following up with a targeted ack, we resolve that
        proposal instead of blocking.  This mirrors holaOS's
        "claim pending card" pattern.
        """
        with self._lock:
            # Targeted ack: caller passed ack_proposal_id → resolve it
            # before the rest of the gate logic.
            ack_id = None
            if isinstance(args, dict):
                ack_id = args.get("ack_proposal_id") or None
            if ack_id and ack_id in self._by_id:
                self._ack_locked(ack_id)

            # If a follow-up call passes ack_proposal_group, ack the
            # whole group.
            ack_group = None
            if isinstance(args, dict):
                ack_group = args.get("ack_proposal_group") or None
            if ack_group and ack_group in self._by_group:
                for pid in list(self._by_group[ack_group]):
                    self._ack_locked(pid)

            # After acking, decide whether to block.
            if not self._by_id:
                return

            # Heuristic for "this call is part of a gated group":
            # the args carry ``proposal_group`` matching a pending
            # group, or ``ack_proposal_id/group`` was set (already
            # handled above).
            group = ""
            if isinstance(args, dict):
                group = args.get("proposal_group") or ""
            if not group:
                return  # call is not gated — let it through

            ids = self._by_group.get(group)
            if not ids:
                return
            # Pick one to report (the oldest).
            oldest_id = min(
                (self._by_id[i] for i in ids if i in self._by_id),
                key=lambda p: p.created_at,
            )
            req = oldest_id.ack_required
            raise ProposalPendingError(
                (
                    f"Cannot run {tool!r} because proposal "
                    f"{oldest_id.proposal_id!r} (from "
                    f"{oldest_id.tool!r}) is still pending "
                    "acknowledgment. Ask the user to confirm or "
                    "reject, then re-issue this call with "
                    f"ack_proposal_id={oldest_id.proposal_id!r}."
                ),
                proposal_id=oldest_id.proposal_id,
                proposal_group=oldest_id.proposal_group,
                pending_tool=oldest_id.tool,
                ack_required=req,
            )

    # -- Ack / clear ------------------------------------------------------

    def ack(self, proposal_id: str) -> bool:
        """Acknowledge a single proposal.  Returns True if it existed."""
        with self._lock:
            return self._ack_locked(proposal_id)

    def _ack_locked(self, proposal_id: str) -> bool:
        if proposal_id not in self._by_id:
            return False
        p = self._by_id.pop(proposal_id)
        if p.proposal_group and p.proposal_group in self._by_group:
            self._by_group[p.proposal_group].discard(proposal_id)
            if not self._by_group[p.proposal_group]:
                del self._by_group[p.proposal_group]
        logger.debug("proposal_gate: acked %s", proposal_id)
        return True

    def ack_group(self, group: str) -> int:
        """Acknowledge all proposals in a group.  Returns count removed."""
        with self._lock:
            ids = list(self._by_group.get(group, set()))
        count = 0
        for pid in ids:
            if self.ack(pid):
                count += 1
        return count

    def reject(self, proposal_id: str) -> bool:
        """Reject = same as ack (the proposal is no longer pending)."""
        return self.ack(proposal_id)

    def clear(self) -> int:
        """Drop all pending proposals.  Returns count removed."""
        with self._lock:
            n = len(self._by_id)
            self._by_id.clear()
            self._by_group.clear()
        return n

    # -- Introspection ----------------------------------------------------

    def pending(self) -> List[Tuple[str, str]]:
        """Return ``(proposal_id, tool)`` pairs for all pending proposals."""
        with self._lock:
            return [(p.proposal_id, p.tool) for p in self._by_id.values()]

    def has_pending(self) -> bool:
        with self._lock:
            return bool(self._by_id)


# ---------------------------------------------------------------------------
# Schema introspection helper
# ---------------------------------------------------------------------------


def tool_requires_acknowledgment(schema: Dict[str, Any]) -> bool:
    """Return True if a tool schema opts in to the proposal gate.

    Looks for two places, both non-standard but conventional:
      1. ``schema["x_hermes"]["requires_acknowledgment"]`` (preferred,
         namespaced so it doesn't collide with provider-native keys)
      2. ``schema["requires_acknowledgment"]`` (flat, for ad-hoc tools)

    Tools that don't opt in pass through the gate untouched.
    """
    if not isinstance(schema, dict):
        return False
    flat = schema.get("requires_acknowledgment")
    if flat is True:
        return True
    xh = schema.get("x_hermes")
    if isinstance(xh, dict) and xh.get("requires_acknowledgment") is True:
        return True
    return False


def extract_proposal_from_result(
    result: str,
) -> Tuple[str, str, List[str]]:
    """Parse a tool result string for proposal metadata.

    Returns ``(proposal_id, proposal_group, ack_required)``.  Any
    field can be empty.  If the result isn't JSON, or doesn't
    contain proposal keys, returns three empty values so the caller
    silently skips registration.

    This is intentionally lenient: tools may return JSON wrapped in
    ``"output": "..."`` or with extra escaping; we attempt
    ``json.loads`` once and fall through on failure.
    """
    if not result or not isinstance(result, str):
        return "", "", []
    import json
    # Try to parse the result as JSON.  We may need a second pass
    # if the tool wrapped its payload in ``{"output": "..."}``.
    candidate: Any = None
    try:
        candidate = json.loads(result)
    except Exception:
        candidate = None

    # If we got a string back, try parsing it as JSON too.  This
    # covers the ``{"output": "<json string>"}`` wrapper that some
    # tool helpers emit.
    if isinstance(candidate, str):
        try:
            candidate = json.loads(candidate)
        except Exception:
            return "", "", []

    # If we got a dict with a string ``output`` field, try one more
    # parse (so {"output": "{\"proposal_id\": ...}"} works).
    if (
        isinstance(candidate, dict)
        and isinstance(candidate.get("output"), str)
    ):
        try:
            candidate = json.loads(candidate["output"])
        except Exception:
            return "", "", []

    if not isinstance(candidate, dict):
        return "", "", []
    pid = candidate.get("proposal_id") or ""
    group = candidate.get("proposal_group") or ""
    ack = candidate.get("ack_required") or []
    if not isinstance(ack, list):
        ack = []
    ack = [str(x) for x in ack]
    return (str(pid) if pid else "", str(group) if group else "", ack)


__all__ = [
    "ProposalGate",
    "ProposalPendingError",
    "tool_requires_acknowledgment",
    "extract_proposal_from_result",
]
