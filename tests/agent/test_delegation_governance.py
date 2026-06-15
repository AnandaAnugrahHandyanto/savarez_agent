"""Tests for agent/delegation_governance.py (M6).

Covers:
  * ``ResultBudget`` dataclass — defaults, validation, unlimited mode
  * ``ResultBudget.apply`` — passthrough when under budget, head+tail
    split when over budget, marker placement, omitted count
  * ``snapshot_pending`` / ``bridge_proposals`` — diff semantics,
    empty result when no new proposals, fallback tool name
  * ``apply_budget_to_entry`` — mutates entry, sets
    ``summary_truncated`` key, no-op for entries without summary
  * ``attach_proposals_to_entry`` — only adds key when non-empty
  * End-to-end: full child run simulation with gate snapshot
"""

import pytest

from agent.delegation_governance import (
    BridgedProposal,
    ResultBudget,
    apply_budget_to_entry,
    attach_proposals_to_entry,
    bridge_proposals,
    snapshot_pending,
)


# ---------------------------------------------------------------------------
# ResultBudget — construction
# ---------------------------------------------------------------------------


def test_result_budget_defaults_are_unlimited():
    b = ResultBudget()
    assert b.is_unlimited() is True
    assert b.max_chars is None
    assert b.head_ratio == 0.5


def test_result_budget_zero_max_is_treated_as_unlimited():
    """0 / negative should be coerced to None — friendly to typos
    like ``ResultBudget(max_chars=0)`` meaning "off"."""
    assert ResultBudget(max_chars=0).is_unlimited()
    assert ResultBudget(max_chars=-5).is_unlimited()


def test_result_budget_rejects_degenerate_head_ratio():
    """head_ratio outside (0, 1) gets coerced to 0.5 — degenerate
    splits would drop the head or tail entirely."""
    assert ResultBudget(max_chars=100, head_ratio=0.0).head_ratio == 0.5
    assert ResultBudget(max_chars=100, head_ratio=1.0).head_ratio == 0.5
    assert ResultBudget(max_chars=100, head_ratio=-0.5).head_ratio == 0.5


def test_result_budget_frozen():
    b = ResultBudget(max_chars=100)
    with pytest.raises((AttributeError, Exception)):
        b.max_chars = 200  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ResultBudget.apply
# ---------------------------------------------------------------------------


def test_apply_under_budget_passthrough():
    b = ResultBudget(max_chars=100)
    text = "short"
    out, truncated = b.apply(text)
    assert out == text
    assert truncated is False


def test_apply_over_budget_truncates():
    b = ResultBudget(max_chars=20, head_ratio=0.5, marker="X")
    text = "a" * 100
    out, truncated = b.apply(text)
    assert truncated is True
    assert "X" in out
    # Result must be within ~budget+marker overhead
    assert len(out) < 100


def test_apply_omitted_count_in_marker():
    b = ResultBudget(max_chars=20, marker="[..{omitted}..]")
    text = "a" * 100
    out, _ = b.apply(text)
    # 100 chars total, 20 budget → 80 omitted
    assert "80" in out


def test_apply_preserves_head_and_tail():
    """Truncation should keep both the beginning and the end of
    the original text — the user often wants the conclusion."""
    b = ResultBudget(max_chars=30, head_ratio=0.5, marker="...")
    text = "HEAD-CONTENT" + "x" * 200 + "TAIL-END"
    out, truncated = b.apply(text)
    assert truncated is True
    assert "HEAD-CONTENT" in out
    assert "TAIL-END" in out
    # The middle "xxx" run should be gone (or partially gone)
    assert out.count("x") < 200


def test_apply_unlimited_returns_verbatim():
    b = ResultBudget()  # default — unlimited
    text = "a" * 10000
    out, truncated = b.apply(text)
    assert out == text
    assert truncated is False


def test_apply_empty_string_is_noop():
    b = ResultBudget(max_chars=10)
    out, truncated = b.apply("")
    assert out == ""
    assert truncated is False


def test_apply_marker_is_format_string():
    """The marker is a format string; ``{omitted}`` is the only
    substitution point we guarantee."""
    b = ResultBudget(max_chars=10, marker="<<{omitted} chars dropped>>")
    out, _ = b.apply("x" * 100)
    assert "<<90 chars dropped>>" in out


# ---------------------------------------------------------------------------
# snapshot_pending
# ---------------------------------------------------------------------------


def test_snapshot_pending_returns_set_of_ids():
    class _StubGate:
        def pending(self):
            return [("a", "g1"), ("b", "g2")]

    snap = snapshot_pending(_StubGate())
    assert snap == {"a", "b"}


def test_snapshot_pending_none_returns_empty():
    assert snapshot_pending(None) == set()


def test_snapshot_pending_handles_exceptions():
    class _Broken:
        def pending(self):
            raise RuntimeError("boom")

    assert snapshot_pending(_Broken()) == set()


def test_snapshot_pending_handles_missing_method():
    class _NoMethod:
        pass

    assert snapshot_pending(_NoMethod()) == set()


# ---------------------------------------------------------------------------
# bridge_proposals
# ---------------------------------------------------------------------------


def test_bridge_proposals_no_new_returns_empty():
    class _StubGate:
        def __init__(self):
            self._by_id = {
                "a": _FakeProposal("a", "g1", "send_email"),
            }
        def pending(self):
            return [("a", "g1")]

    out = bridge_proposals(_StubGate(), before={"a"}, after={"a"})
    assert out == []


def test_bridge_proposals_returns_new_only():
    class _StubGate:
        def __init__(self):
            self._by_id = {
                "a": _FakeProposal("a", "g1", "send_email"),
                "b": _FakeProposal("b", "g1", "delete_file"),
            }
        def pending(self):
            return [("a", "g1"), ("b", "g1")]

    out = bridge_proposals(_StubGate(), before={"a"}, after={"a", "b"})
    assert len(out) == 1
    assert out[0].proposal_id == "b"
    assert out[0].tool == "delete_file"


def test_bridge_proposals_none_gate():
    assert bridge_proposals(None) == []


def test_bridge_proposals_stale_diff_skipped():
    """A proposal that was registered and *cleared* between
    snapshots should be skipped (no record in _by_id)."""
    class _StubGate:
        def __init__(self):
            self._by_id = {}  # nothing here
        def pending(self):
            return []  # cleared

    # before had nothing; after claims to have "ghost"
    out = bridge_proposals(_StubGate(), before=set(), after={"ghost"})
    assert out == []


def test_bridge_proposals_carries_ack_required():
    class _StubGate:
        def __init__(self):
            self._by_id = {
                "p1": _FakeProposal("p1", "g1", "send_email", ack_required=("delete_file", "write_file")),
            }
        def pending(self):
            return [("p1", "g1")]

    out = bridge_proposals(_StubGate(), before=set(), after={"p1"})
    assert out[0].ack_required == ("delete_file", "write_file")


def test_bridge_proposals_fallback_tool():
    """When the gate's record has no ``tool`` attribute, we fall
    back to the caller-supplied default — defensive against a
    gate implementation that stores a different schema."""
    class _WeirdGate:
        def __init__(self):
            self._by_id = {
                "p1": _FakeProposal("p1", "g1", tool_name=""),  # empty
            }
        def pending(self):
            return [("p1", "g1")]

    out = bridge_proposals(_WeirdGate(), before=set(), after={"p1"}, fallback_tool="custom_tool")
    assert out[0].tool == "custom_tool"


def test_bridge_proposals_default_snapshots():
    """When ``before`` and ``after`` are both omitted, snapshot
    is taken twice — should return empty (no new proposals
    between two consecutive snapshots of the same gate)."""
    class _StubGate:
        def __init__(self):
            self._by_id = {
                "a": _FakeProposal("a", "g1", "send_email"),
            }
        def pending(self):
            return [("a", "g1")]

    out = bridge_proposals(_StubGate())
    assert out == []


# ---------------------------------------------------------------------------
# apply_budget_to_entry
# ---------------------------------------------------------------------------


def test_apply_budget_to_entry_truncates_summary():
    entry = {"summary": "x" * 1000, "status": "completed"}
    b = ResultBudget(max_chars=50)
    out = apply_budget_to_entry(entry, b)
    assert out is entry
    assert out["summary_truncated"] is True
    assert len(out["summary"]) < 1000


def test_apply_budget_to_entry_no_truncation_sets_false():
    entry = {"summary": "short", "status": "completed"}
    b = ResultBudget(max_chars=100)
    apply_budget_to_entry(entry, b)
    assert entry["summary_truncated"] is False


def test_apply_budget_to_entry_no_summary_key_noop():
    entry = {"status": "failed"}
    b = ResultBudget(max_chars=10)
    apply_budget_to_entry(entry, b)
    assert "summary_truncated" not in entry
    assert "summary" not in entry


def test_apply_budget_to_entry_none_budget_noop():
    entry = {"summary": "x" * 1000}
    apply_budget_to_entry(entry, None)
    # Unchanged
    assert "summary_truncated" not in entry
    assert entry["summary"] == "x" * 1000


def test_apply_budget_to_entry_non_string_summary_noop():
    entry = {"summary": 12345}  # not a string
    b = ResultBudget(max_chars=10)
    apply_budget_to_entry(entry, b)
    assert entry["summary"] == 12345


# ---------------------------------------------------------------------------
# attach_proposals_to_entry
# ---------------------------------------------------------------------------


def test_attach_proposals_skips_empty():
    entry = {"status": "completed"}
    attach_proposals_to_entry(entry, [])
    assert "proposals" not in entry


def test_attach_proposals_adds_serializable_list():
    entry = {"status": "completed"}
    proposals = [
        BridgedProposal(
            proposal_id="p1",
            proposal_group="g1",
            tool="send_email",
            ack_required=("delete_file",),
        )
    ]
    attach_proposals_to_entry(entry, proposals)
    assert "proposals" in entry
    assert entry["proposals"] == [
        {
            "proposal_id": "p1",
            "proposal_group": "g1",
            "tool": "send_email",
            "ack_required": ["delete_file"],
        }
    ]


# ---------------------------------------------------------------------------
# End-to-end: child run simulation
# ---------------------------------------------------------------------------


def test_e2e_child_run_with_proposal_and_oversize_summary():
    """Simulate: parent snapshots gate, child runs and triggers a
    gate-tagged tool, child returns a 5000-char summary.  Verify
    the parent sees (a) summary truncated to budget and (b) the
    child's proposal surfaced for ack/reject at the top level."""
    class _StubGate:
        def __init__(self):
            self._by_id = {}
        def pending(self):
            return [(pid, "") for pid in self._by_id]
        def register(self, pid, *, proposal_group, tool, ack_required=()):
            self._by_id[pid] = _FakeProposal(pid, proposal_group, tool, ack_required=ack_required)

    gate = _StubGate()
    before = snapshot_pending(gate)

    # Child runs and hits a gated tool
    gate.register(
        "p-42",
        proposal_group="g-email",
        tool="send_email",
        ack_required=("delete_file",),
    )

    after = snapshot_pending(gate)
    proposals = bridge_proposals(gate, before=before, after=after)

    # Build the entry the parent would receive
    entry = {
        "task_index": 0,
        "status": "completed",
        "summary": "x" * 5000,
        "duration_seconds": 12.3,
    }
    apply_budget_to_entry(entry, ResultBudget(max_chars=500))
    attach_proposals_to_entry(entry, proposals)

    # Verify: summary was truncated, proposals attached
    assert entry["summary_truncated"] is True
    assert len(entry["summary"]) < 5000
    assert entry["proposals"][0]["proposal_id"] == "p-42"
    assert entry["proposals"][0]["tool"] == "send_email"


def test_e2e_child_run_no_proposal_keeps_entry_shape():
    """When the child didn't trigger any gate-tagged tool, the
    entry's JSON shape must stay identical (no 'proposals' key
    added) — this is the backward-compat guarantee."""
    class _StubGate:
        def pending(self):
            return []
        def _by_id(self): return {}  # not used

    gate = _StubGate()
    before = snapshot_pending(gate)
    after = snapshot_pending(gate)  # child did nothing
    proposals = bridge_proposals(gate, before=before, after=after)

    entry = {"task_index": 0, "status": "completed", "summary": "done"}
    apply_budget_to_entry(entry, None)  # no budget
    attach_proposals_to_entry(entry, proposals)

    # No 'proposals' key added, no 'summary_truncated' key added
    assert "proposals" not in entry
    assert "summary_truncated" not in entry
    assert entry == {"task_index": 0, "status": "completed", "summary": "done"}


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class _FakeProposal:
    """Stand-in for agent.proposal_gate._Proposal for unit tests."""

    def __init__(self, proposal_id, proposal_group, tool_name, ack_required=()):
        self.proposal_id = proposal_id
        self.proposal_group = proposal_group
        self.tool = tool_name
        self.ack_required = list(ack_required)
