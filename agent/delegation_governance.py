"""Subagent delegation governance — result budget + proposal bridging.

Inspired by holaOS's ``integration-delegation.ts`` (the part that
diffs *before/after* snapshots of a worker run to surface worker
tool-side-effects back to the parent, and the part that caps a
worker's result text so a runaway child can't flood the parent's
context).

Two pieces, both opt-in, both backward compatible:

1. **Result budget** — cap the chars returned in a subagent's
   ``summary`` field; if the worker's full output exceeds the
   budget, keep the head + tail with an explicit ``truncated``
   marker.  This is *not* the same as the subagent's iteration
   budget; it only governs the bytes that flow back into the
   parent's conversation.

2. **Proposal bridging** — subagents that hit a gate-tagged tool
   produce pending :class:`ProposalPendingError`-style proposals on
   the *process-wide* proposal gate.  The parent agent would
   otherwise never see them.  We snapshot the gate before the
   child runs and diff afterwards, so the parent receives the
   child's proposed side-effects as part of the subagent result
   and can decide to ack / reject them at the top level.

Backward compatibility
----------------------
- No-op when ``result_budget_chars`` is None (the default):
  ``summary`` is returned verbatim.  All existing
  delegate_task callers that don't set the kwarg see no change.
- No-op when the proposal gate is empty: ``proposals`` key is
  only added to the entry dict when at least one proposal
  surfaced, so the JSON shape stays identical for the common
  (gate-empty) case.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Result budget
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResultBudget:
    """Per-subagent summary-character budget.

    Attributes
    ----------
    max_chars:
        Hard cap on the chars returned in a subagent's ``summary``
        field.  ``None`` disables truncation entirely (the
        default — backward compatible).  A non-positive value
        is treated as None.

    head_ratio:
        When truncating, the fraction of the budget to use for
        the *head* (start of the summary).  The remainder is
        used for the *tail* (end of the summary).  Defaults to
        0.5 (a 50/50 split) so a subagent that ends with a
        conclusion / signature gets to keep it.

    marker:
        The string placed in the middle of a truncated summary.
        Defaults to a clear ellipsis with a hint about the
        omitted length.
    """

    max_chars: Optional[int] = None
    head_ratio: float = 0.5
    marker: str = "\n\n[... {omitted} chars truncated; raise "
    "ResultBudget.max_chars to keep the full text ...]\n\n"

    def __post_init__(self) -> None:
        # Treat 0/negative max_chars as "no limit" — symmetric
        # with the None default and friendly to "0 means
        # don't budget at all" typos.
        if self.max_chars is not None and self.max_chars <= 0:
            object.__setattr__(self, "max_chars", None)
        if not 0 < self.head_ratio < 1:
            # Reject 0/1/negative — degenerate splits would drop
            # the head or the tail entirely.  The dataclass is
            # frozen so we have to use object.__setattr__.
            object.__setattr__(self, "head_ratio", 0.5)

    def is_unlimited(self) -> bool:
        return self.max_chars is None

    def apply(self, text: str) -> Tuple[str, bool]:
        """Apply the budget to ``text``.

        Returns ``(new_text, was_truncated)``.  When the budget
        is unlimited, returns ``(text, False)`` verbatim.
        """
        if self.max_chars is None or not text:
            return text, False
        if len(text) <= self.max_chars:
            return text, False

        # Compute head/tail split.  Reserve some chars for the
        # marker itself; the marker carries the omitted count.
        marker = self.marker.format(omitted=len(text) - self.max_chars)
        usable = max(self.max_chars - len(marker), 1)
        head_size = max(int(usable * self.head_ratio), 1)
        tail_size = max(usable - head_size, 1)

        # If tail_size would consume the head, prefer head.
        if head_size + tail_size > len(text):
            return text[: self.max_chars] + marker, True

        head = text[:head_size]
        tail = text[-tail_size:] if tail_size > 0 else ""
        return f"{head}{marker}{tail}", True


# ---------------------------------------------------------------------------
# Proposal bridging
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BridgedProposal:
    """A single pending proposal that surfaced during a subagent run.

    Mirrors the JSON shape a parent would receive from the
    proposal-gate tool error so the parent's LLM can act on it
    without needing a separate API call.

    Attributes
    ----------
    proposal_id:
        Stable identifier (so the parent can ack / reject).
    proposal_group:
        Group identifier — the parent can ack the whole group at
        once when several proposals belong to the same workflow
        step.
    tool:
        The tool that registered the proposal.  The parent
        needs to know *which* tool wants to act, not just that
        a proposal exists.
    ack_required:
        Tool names that should be blocked while this proposal
        is pending (from the gate's ``ack_required`` list).
    """

    proposal_id: str
    proposal_group: str
    tool: str
    ack_required: Tuple[str, ...] = ()


def snapshot_pending(gate: Any) -> set:
    """Return the set of pending proposal_ids on ``gate``.

    Thin wrapper over :meth:`ProposalGate.pending` that returns a
    hashable set (gate.pending() yields tuples).  The set is
    suitable for set-difference to find proposals that surfaced
    *after* a snapshot was taken.

    Accepts a duck-typed ``gate`` (``pending()`` returns an
    iterable of (proposal_id, group) tuples).  This keeps the
    module decoupled from the concrete gate class so unit tests
    can pass a stub.
    """
    if gate is None:
        return set()
    pending = getattr(gate, "pending", None)
    if not callable(pending):
        return set()
    try:
        return {pid for pid, _group in pending()}
    except Exception:
        return set()


def bridge_proposals(
    gate: Any,
    *,
    before: Optional[set] = None,
    after: Optional[set] = None,
    fallback_tool: str = "delegate_task",
) -> List[BridgedProposal]:
    """Compute the set of proposals that appeared between two
    snapshots of the gate.

    Parameters
    ----------
    gate:
        A duck-typed gate with ``pending()`` and
        ``_by_id`` (internal map of ``proposal_id -> _Proposal``).
        Use :func:`agent.proposal_gate.get_proposal_gate` for the
        real one.
    before / after:
        Pre-computed pending sets (from
        :func:`snapshot_pending`).  Both default to "compute
        now" if omitted.  In the common case the caller passes
        ``before`` (taken right before the child runs) and lets
        ``after`` default to a fresh snapshot.
    fallback_tool:
        Tool name to record on a bridged proposal when the
        gate's internal record doesn't carry one (defensive —
        the gate's ``_Proposal.tool`` is the source of truth).

    Returns
    -------
    list[BridgedProposal]
        New proposals that appeared in (after - before), with
        their full bridging metadata.  Empty list when nothing
        changed — the caller can skip adding the key to its
        result dict.
    """
    if gate is None:
        return []
    if before is None:
        before = snapshot_pending(gate)
    if after is None:
        after = snapshot_pending(gate)
    new_ids = after - before
    if not new_ids:
        return []

    by_id = getattr(gate, "_by_id", None) or {}
    out: List[BridgedProposal] = []
    for pid in new_ids:
        rec = by_id.get(pid)
        if rec is None:
            # Stale diff: the proposal was registered and then
            # cleared between snapshots.  Skip — there's nothing
            # to bridge.
            continue
        out.append(
            BridgedProposal(
                proposal_id=pid,
                proposal_group=getattr(rec, "proposal_group", "") or "",
                tool=getattr(rec, "tool", "") or fallback_tool,
                ack_required=tuple(
                    getattr(rec, "ack_required", None) or ()
                ),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Top-level helpers
# ---------------------------------------------------------------------------


def apply_budget_to_entry(
    entry: Dict[str, Any],
    budget: Optional[ResultBudget],
) -> Dict[str, Any]:
    """Apply ``budget`` to the ``summary`` field of a subagent
    result entry.  Returns the entry (mutated in place) for
    caller convenience.

    No-op when ``budget`` is None or the entry has no
    ``summary`` key.  Sets a ``summary_truncated`` boolean
    (True/False) so the parent can render a "truncated"
    badge without re-measuring.
    """
    if budget is None or "summary" not in entry:
        return entry
    original = entry.get("summary") or ""
    if not isinstance(original, str):
        return entry
    new_text, was_truncated = budget.apply(original)
    if was_truncated:
        entry["summary"] = new_text
        entry["summary_truncated"] = True
    else:
        # Always set the key (False) so downstream consumers
        # can rely on the schema.
        entry.setdefault("summary_truncated", False)
    return entry


def attach_proposals_to_entry(
    entry: Dict[str, Any],
    proposals: Sequence[BridgedProposal],
) -> Dict[str, Any]:
    """Attach bridged proposals to a subagent result entry.

    Only adds the key when there's at least one proposal —
    keeps the JSON shape identical for the common
    (no-proposal-during-child) case.  Serializes the
    :class:`BridgedProposal` tuples into plain dicts so the
    parent agent's LLM sees a JSON shape it can act on.
    """
    if not proposals:
        return entry
    entry["proposals"] = [
        {
            "proposal_id": p.proposal_id,
            "proposal_group": p.proposal_group,
            "tool": p.tool,
            "ack_required": list(p.ack_required),
        }
        for p in proposals
    ]
    return entry


__all__ = [
    "ResultBudget",
    "BridgedProposal",
    "snapshot_pending",
    "bridge_proposals",
    "apply_budget_to_entry",
    "attach_proposals_to_entry",
]
