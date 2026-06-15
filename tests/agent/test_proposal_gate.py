"""Tests for agent/proposal_gate.py (M3 — tool-call proposal gate).

Covers:
- ProposalGate register/ack/reject/clear
- check() raises ProposalPendingError when follow-up tool has a
  pending group; passes through when group is empty
- ack_proposal_id / ack_proposal_group args unlock a call
- tool_requires_acknowledgment schema introspection (flat + x_hermes)
- extract_proposal_from_result JSON parsing
- handle_function_call integration: gate-error returned as tool result
"""

import json
import pytest

from agent.proposal_gate import (
    ProposalGate,
    ProposalPendingError,
    extract_proposal_from_result,
    tool_requires_acknowledgment,
)


# ---------------------------------------------------------------------------
# ProposalGate basic lifecycle
# ---------------------------------------------------------------------------


def test_empty_gate_has_no_pending():
    g = ProposalGate()
    assert not g.has_pending()
    assert g.pending() == []


def test_register_makes_pending_visible():
    g = ProposalGate()
    g.register(proposal_id="p1", tool="delegate_task")
    assert g.has_pending()
    assert g.pending() == [("p1", "delegate_task")]


def test_register_with_group_indexes_by_group():
    g = ProposalGate()
    g.register(proposal_id="p1", proposal_group="g1", tool="delegate_task")
    g.register(proposal_id="p2", proposal_group="g1", tool="delegate_task")
    g.register(proposal_id="p3", proposal_group="g2", tool="cron")
    # Acking the group should clear both p1 and p2
    n = g.ack_group("g1")
    assert n == 2
    assert g.has_pending()  # p3 still there
    assert g.pending() == [("p3", "cron")]


def test_register_is_idempotent_for_same_id():
    g = ProposalGate()
    g.register(proposal_id="p1", tool="a")
    g.register(proposal_id="p1", tool="b")  # ignored
    assert g.pending() == [("p1", "a")]


def test_register_with_empty_proposal_id_is_noop():
    g = ProposalGate()
    g.register(proposal_id="", tool="a")
    assert not g.has_pending()


def test_ack_unknown_proposal_returns_false():
    g = ProposalGate()
    assert g.ack("never-registered") is False


def test_reject_same_as_ack():
    g = ProposalGate()
    g.register(proposal_id="p1", tool="a")
    assert g.reject("p1") is True
    assert not g.has_pending()


def test_clear_drops_everything():
    g = ProposalGate()
    g.register(proposal_id="p1", tool="a")
    g.register(proposal_id="p2", tool="b")
    n = g.clear()
    assert n == 2
    assert not g.has_pending()


# ---------------------------------------------------------------------------
# check() — the core gate behavior
# ---------------------------------------------------------------------------


def test_check_passes_when_no_pending():
    g = ProposalGate()
    g.check(tool="delegate_task", args={"task": "do x"})  # no raise


def test_check_blocks_followup_in_pending_group():
    g = ProposalGate()
    g.register(
        proposal_id="p1",
        proposal_group="g1",
        tool="delegate_task",
    )
    with pytest.raises(ProposalPendingError) as exc:
        g.check(
            tool="delegate_task",
            args={"task": "do y", "proposal_group": "g1"},
        )
    assert exc.value.proposal_id == "p1"
    assert exc.value.proposal_group == "g1"
    assert exc.value.pending_tool == "delegate_task"


def test_check_allows_unrelated_call_during_pending():
    g = ProposalGate()
    g.register(proposal_id="p1", proposal_group="g1", tool="delegate_task")
    # A call WITHOUT a matching proposal_group should pass through
    g.check(tool="delegate_task", args={"task": "do y"})  # no raise
    g.check(tool="read_file", args={"path": "/tmp/x"})  # no raise


def test_check_with_ack_proposal_id_resolves_block():
    g = ProposalGate()
    g.register(
        proposal_id="p1",
        proposal_group="g1",
        tool="delegate_task",
    )
    # Caller passes ack_proposal_id, so the gate acknowledges
    # and lets the call through.
    g.check(
        tool="delegate_task",
        args={"task": "do y", "ack_proposal_id": "p1", "proposal_group": "g1"},
    )
    assert not g.has_pending()


def test_check_with_ack_proposal_group_resolves_block():
    g = ProposalGate()
    g.register(proposal_id="p1", proposal_group="g1", tool="delegate_task")
    g.register(proposal_id="p2", proposal_group="g1", tool="delegate_task")
    g.check(
        tool="delegate_task",
        args={"task": "do y", "ack_proposal_group": "g1", "proposal_group": "g1"},
    )
    # Both proposals in the group should be resolved
    assert not g.has_pending()


def test_check_after_ack_passes():
    g = ProposalGate()
    g.register(proposal_id="p1", proposal_group="g1", tool="delegate_task")
    g.ack("p1")
    # After ack, the follow-up call in the same group should NOT raise.
    g.check(
        tool="delegate_task",
        args={"task": "do y", "proposal_group": "g1"},
    )


# ---------------------------------------------------------------------------
# Error → tool result format
# ---------------------------------------------------------------------------


def test_pending_error_to_tool_error_is_json():
    err = ProposalPendingError(
        "still pending",
        proposal_id="p1",
        proposal_group="g1",
        pending_tool="delegate_task",
        ack_required=["user confirm"],
    )
    s = err.to_tool_error()
    parsed = json.loads(s)
    assert parsed["error"] == "still pending"
    assert parsed["proposal_id"] == "p1"
    assert parsed["proposal_group"] == "g1"
    assert parsed["pending_tool"] == "delegate_task"
    assert parsed["ack_required"] == ["user confirm"]


# ---------------------------------------------------------------------------
# Schema introspection
# ---------------------------------------------------------------------------


def test_tool_requires_acknowledgment_flat_key():
    assert tool_requires_acknowledgment({"requires_acknowledgment": True}) is True


def test_tool_requires_acknowledgment_namespaced_key():
    assert (
        tool_requires_acknowledgment({"x_hermes": {"requires_acknowledgment": True}})
        is True
    )


def test_tool_requires_acknowledgment_defaults_false():
    assert tool_requires_acknowledgment({}) is False
    assert tool_requires_acknowledgment({"name": "foo"}) is False
    assert tool_requires_acknowledgment({"x_hermes": {}}) is False


def test_tool_requires_acknowledgment_handles_bad_input():
    assert tool_requires_acknowledgment(None) is False  # type: ignore[arg-type]
    assert tool_requires_acknowledgment("not a dict") is False  # type: ignore[arg-type]
    assert tool_requires_acknowledgment(42) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# extract_proposal_from_result
# ---------------------------------------------------------------------------


def test_extract_proposal_from_result_clean_json():
    s = json.dumps({
        "success": True,
        "proposal_id": "p1",
        "proposal_group": "g1",
        "ack_required": ["user confirm"],
    })
    pid, group, ack = extract_proposal_from_result(s)
    assert pid == "p1"
    assert group == "g1"
    assert ack == ["user confirm"]


def test_extract_proposal_from_result_wrapped_output():
    """Some tools wrap their output in {'output': '...'}."""
    inner = json.dumps({"proposal_id": "p1"})
    outer = json.dumps({"output": inner, "success": True})
    pid, group, ack = extract_proposal_from_result(outer)
    assert pid == "p1"
    assert group == ""
    assert ack == []


def test_extract_proposal_from_result_no_proposal_key():
    """A tool that didn't opt in returns no proposal metadata."""
    s = json.dumps({"success": True, "data": "ok"})
    pid, group, ack = extract_proposal_from_result(s)
    assert pid == ""
    assert group == ""
    assert ack == []


def test_extract_proposal_from_result_invalid_json_returns_empty():
    pid, group, ack = extract_proposal_from_result("not json at all")
    assert pid == "" and group == "" and ack == []


def test_extract_proposal_from_result_empty_returns_empty():
    pid, group, ack = extract_proposal_from_result("")
    assert pid == "" and group == "" and ack == []


def test_extract_proposal_from_result_handles_non_string():
    pid, group, ack = extract_proposal_from_result(None)  # type: ignore[arg-type]
    assert pid == "" and group == "" and ack == []


def test_extract_proposal_from_result_ack_required_must_be_list():
    """If ack_required is the wrong shape, fall back to empty list."""
    s = json.dumps({"proposal_id": "p1", "ack_required": "not a list"})
    pid, group, ack = extract_proposal_from_result(s)
    assert pid == "p1"
    assert ack == []  # coerced to empty


# ---------------------------------------------------------------------------
# handle_function_call integration
# ---------------------------------------------------------------------------


def test_handle_function_call_registers_proposal_for_opted_in_tool(monkeypatch):
    """End-to-end: a tool whose schema opts in to the gate, and whose
    result contains a proposal_id, should register the proposal."""
    from model_tools import handle_function_call, set_proposal_gate, get_proposal_gate

    # Install a clean gate
    fresh = ProposalGate()
    set_proposal_gate(fresh)

    # Inject a fake tool that opts in to the gate
    from tools import registry as reg
    from tools.registry import ToolEntry

    schema = {
        "name": "fake_gate_tool",
        "description": "test",
        "parameters": {"type": "object", "properties": {}},
        "x_hermes": {"requires_acknowledgment": True},
    }

    def _handler(args, **kwargs):
        return json.dumps({
            "success": True,
            "proposal_id": "p-fake-1",
            "proposal_group": "g-fake-1",
            "ack_required": ["user"],
        })

    reg.registry.register(
        name="fake_gate_tool",
        toolset="test",
        schema=schema,
        handler=_handler,
        check_fn=lambda: True,
    )

    try:
        result = handle_function_call(
            function_name="fake_gate_tool",
            function_args={},
        )
        # The tool ran (didn't return a gate error)
        parsed = json.loads(result)
        assert parsed.get("success") is True
        # The proposal was registered
        assert get_proposal_gate().has_pending()
    finally:
        # Cleanup: remove the registered tool, restore default gate
        reg.registry._tools.pop("fake_gate_tool", None)
        if hasattr(reg.registry, "_tool_to_toolset"):
            reg.registry._tool_to_toolset.pop("fake_gate_tool", None)  # type: ignore[attr-defined]
        set_proposal_gate(None)


def test_handle_function_call_blocks_followup_for_pending_group(monkeypatch):
    """If a proposal is pending, a follow-up call to a gated tool in
    the same group must return a ProposalPendingError JSON."""
    from model_tools import handle_function_call, set_proposal_gate

    fresh = ProposalGate()
    fresh.register(
        proposal_id="p-pending",
        proposal_group="g-blocked",
        tool="fake_gate_tool",
    )
    set_proposal_gate(fresh)

    from tools import registry as reg
    schema = {
        "name": "fake_gate_tool",
        "description": "test",
        "parameters": {"type": "object", "properties": {}},
        "x_hermes": {"requires_acknowledgment": True},
    }

    def _handler(args, **kwargs):
        return json.dumps({"success": True, "value": "ran"})

    reg.registry.register(
        name="fake_gate_tool",
        toolset="test",
        schema=schema,
        handler=_handler,
        check_fn=lambda: True,
    )

    try:
        result = handle_function_call(
            function_name="fake_gate_tool",
            function_args={"proposal_group": "g-blocked"},
        )
        parsed = json.loads(result)
        # The tool did NOT run; the gate blocked it
        assert "error" in parsed
        assert parsed.get("proposal_id") == "p-pending"
        # And the handler wasn't called (no success key)
        assert "success" not in parsed
    finally:
        reg.registry._tools.pop("fake_gate_tool", None)
        if hasattr(reg.registry, "_tool_to_toolset"):
            reg.registry._tool_to_toolset.pop("fake_gate_tool", None)  # type: ignore[attr-defined]
        set_proposal_gate(None)


def test_handle_function_call_passes_through_unrelated_pending(monkeypatch):
    """A pending proposal in group X must not block a call in group Y."""
    from model_tools import handle_function_call, set_proposal_gate

    fresh = ProposalGate()
    fresh.register(
        proposal_id="p-other",
        proposal_group="g-other",
        tool="fake_gate_tool",
    )
    set_proposal_gate(fresh)

    from tools import registry as reg
    schema = {
        "name": "fake_gate_tool",
        "description": "test",
        "parameters": {"type": "object", "properties": {}},
        "x_hermes": {"requires_acknowledgment": True},
    }

    def _handler(args, **kwargs):
        return json.dumps({"success": True})

    reg.registry.register(
        name="fake_gate_tool",
        toolset="test",
        schema=schema,
        handler=_handler,
        check_fn=lambda: True,
    )

    try:
        # Call with a DIFFERENT proposal_group
        result = handle_function_call(
            function_name="fake_gate_tool",
            function_args={"proposal_group": "g-different"},
        )
        parsed = json.loads(result)
        # The tool ran because the groups don't match
        assert parsed.get("success") is True
    finally:
        reg.registry._tools.pop("fake_gate_tool", None)
        if hasattr(reg.registry, "_tool_to_toolset"):
            reg.registry._tool_to_toolset.pop("fake_gate_tool", None)  # type: ignore[attr-defined]
        set_proposal_gate(None)


def test_handle_function_call_ignores_non_opt_in_tool():
    """A tool that doesn't declare requires_acknowledgment must be
    untouched by the gate (no registration, no blocking)."""
    from model_tools import handle_function_call, set_proposal_gate

    fresh = ProposalGate()
    set_proposal_gate(fresh)

    from tools import registry as reg
    schema = {
        "name": "no_gate_tool",
        "description": "test",
        "parameters": {"type": "object", "properties": {}},
        # No x_hermes / no flat key
    }

    def _handler(args, **kwargs):
        return json.dumps({
            "success": True,
            "proposal_id": "should-be-ignored",
        })

    reg.registry.register(
        name="no_gate_tool",
        toolset="test",
        schema=schema,
        handler=_handler,
        check_fn=lambda: True,
    )

    try:
        result = handle_function_call(
            function_name="no_gate_tool",
            function_args={},
        )
        # Gate must NOT have registered the proposal
        assert not fresh.has_pending()
    finally:
        reg.registry._tools.pop("no_gate_tool", None)
        if hasattr(reg.registry, "_tool_to_toolset"):
            reg.registry._tool_to_toolset.pop("no_gate_tool", None)  # type: ignore[attr-defined]
        set_proposal_gate(None)
