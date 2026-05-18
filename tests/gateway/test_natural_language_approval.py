"""Integration tests for the natural-language approval-intent intercept
that routes plain-text replies like "I approve" / "yes" / "execute"
through the same gateway approval path as the ``/approve`` slash command.

Covers the scenarios required by the Telegram approval execution fix:
1. "I approve" executes one pending approval.
2. "approved" executes one pending approval.
3. "yes" executes one pending approval.
4. "execute" / "execute this" executes one pending approval.
5. Multiple pending approvals triggers disambiguation.
6. No pending approvals falls through so "execute this" remains a task.
7. Sensitive approval is ledgered and resumes only through the formal approval queue.
8. Hermes does not ask for approval twice after a valid approval phrase.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

_repo = str(Path(__file__).resolve().parents[2])
if _repo not in sys.path:
    sys.path.insert(0, _repo)

# Importing tools.approval is light — no platform SDKs pulled in.
import tools.approval as approval_module
from tools.approval import (
    _ApprovalEntry,
    _gateway_queues,
    _lock,
    gateway_pending_count,
    list_gateway_pending,
)


SESSION_KEY = "test-nl-approval-session"
OTHER_SESSION_KEY = "test-nl-other-session"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def clean_approval_state():
    """Ensure the per-session approval queue is empty before and after each test.

    Module globals in ``tools/approval.py`` survive across tests in the same
    process; without this fixture, leakage between scenarios would cause
    confusing pass/fail interactions.
    """
    with _lock:
        _gateway_queues.pop(SESSION_KEY, None)
        _gateway_queues.pop(OTHER_SESSION_KEY, None)
    yield
    with _lock:
        _gateway_queues.pop(SESSION_KEY, None)
        _gateway_queues.pop(OTHER_SESSION_KEY, None)


def _seed_pending(
    session_key: str = SESSION_KEY,
    command: str = "rm -rf /tmp/example",
    description: str = "delete a path",
    pattern_keys=("rm",),
) -> _ApprovalEntry:
    """Append a real ``_ApprovalEntry`` to the gateway queue for *session_key*."""
    entry = _ApprovalEntry({
        "command": command,
        "description": description,
        "pattern_key": pattern_keys[0],
        "pattern_keys": list(pattern_keys),
    })
    with _lock:
        _gateway_queues.setdefault(session_key, []).append(entry)
    return entry


def _make_event(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text)


def _make_runner_stub():
    """Minimal ``GatewayRunner`` stub for invoking the intercept as a bound
    method.  The intercept only ever calls ``self._handle_approve_command``
    and ``self._handle_deny_command``; everything else is module-level.
    """
    runner = SimpleNamespace()
    runner._handle_approve_command = AsyncMock(return_value="✅ approved-result")
    runner._handle_deny_command = AsyncMock(return_value="❌ denied-result")
    return runner


async def _call_intercept(runner, event, session_key: str = SESSION_KEY):
    """Invoke ``GatewayRunner._try_natural_language_approval`` as an
    unbound method against the *runner* stub.  Lazy-import to avoid
    pulling in messaging-SDK imports at module load.
    """
    from gateway.run import GatewayRunner

    return await GatewayRunner._try_natural_language_approval(
        runner, event, session_key,
    )


# ---------------------------------------------------------------------------
# Spec-required scenarios 1–4: each approval phrase resolves a single pending
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize("phrase", [
    "I approve",   # spec test 1
    "approved",    # spec test 2
    "yes",         # spec test 3
    "execute",     # spec test 4
    "execute this",
    "execute it",
    "approve",
    "do it",
    "do this",
    "run it",
    "run this",
    "run it now",
    "confirmed",
    "proceed",
])
async def test_approval_phrase_resolves_single_pending(phrase: str) -> None:
    """Each phrase in the spec MUST route a single-pending session to
    ``_handle_approve_command`` (the same code path as ``/approve``).
    """
    _seed_pending()
    assert gateway_pending_count(SESSION_KEY) == 1

    runner = _make_runner_stub()
    event = _make_event(phrase)

    result = await _call_intercept(runner, event)

    # The intercept must have delegated to /approve's handler.  This proves
    # we are NOT bypassing the formal approval gate; we route through the
    # same code path that the slash command uses.
    runner._handle_approve_command.assert_awaited_once_with(event)
    runner._handle_deny_command.assert_not_called()
    assert result == "✅ approved-result"


# ---------------------------------------------------------------------------
# Spec scenario 5: multiple pending approvals trigger disambiguation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_multiple_pending_triggers_disambiguation() -> None:
    """When more than one approval is pending, the intercept must NOT
    guess — it returns a disambiguation message listing the queued
    commands and asks the user to use ``/approve`` (oldest) or
    ``/approve all`` explicitly.
    """
    _seed_pending(command="rm -rf /tmp/one", description="delete /tmp/one")
    _seed_pending(command="aws s3 rm s3://bucket/", description="delete bucket")
    assert gateway_pending_count(SESSION_KEY) == 2

    runner = _make_runner_stub()
    event = _make_event("I approve")

    result = await _call_intercept(runner, event)

    # Must NOT have called the resolve handler — that would resolve the
    # oldest by FIFO, which is exactly the "do not guess" violation the
    # spec warns against.
    runner._handle_approve_command.assert_not_called()
    runner._handle_deny_command.assert_not_called()

    # Must be a disambiguation message that surfaces both commands so the
    # user can choose.  We check substrings rather than exact strings to
    # keep the assertion locale/translation-tolerant.
    assert result is not None
    assert "rm -rf /tmp/one" in result
    assert "aws s3 rm s3://bucket/" in result
    assert "/approve" in result  # the call to action

    # And the queue is still intact — no entry was silently consumed.
    assert gateway_pending_count(SESSION_KEY) == 2


# ---------------------------------------------------------------------------
# Spec scenario 6: zero pending → fall through as a normal task instruction
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_no_pending_approval_phrase_falls_through_to_agent() -> None:
    """A natural-language approval phrase sent with zero pending approvals
    must fall through.  This is what lets "execute this" mean "run the task"
    when no formal approval prompt exists, instead of being swallowed by a
    misleading no-pending-approval message.
    """
    assert gateway_pending_count(SESSION_KEY) == 0
    runner = _make_runner_stub()
    event = _make_event("execute this")

    result = await _call_intercept(runner, event)

    runner._handle_approve_command.assert_not_called()
    runner._handle_deny_command.assert_not_called()
    assert result is None


# ---------------------------------------------------------------------------
# Spec scenario 7: sensitive approval is ledgered and resumes only via formal queue
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sensitive_approval_routes_through_slash_handler_not_a_side_channel() -> None:
    """Architectural invariant: the natural-language intercept MUST route
    through ``_handle_approve_command`` (the same code path as the slash
    command), not call ``resolve_gateway_approval`` directly.

    NOTE on scope — what this test proves and what it doesn't:

    PROVES:  When the intercept fires, the ONLY method it calls is
             ``_handle_approve_command``.  It does NOT reach into
             ``tools.approval`` to mutate queue state out-of-band.
             That establishes routing direction.

    DOES NOT PROVE (intentional — out of unit-test scope):
             That ``_handle_approve_command`` itself goes on to call
             ``resolve_gateway_approval``.  That behaviour belongs to
             the slash-command path and is covered by the existing
             ``tests/tools/test_approval.py`` suite — not this file.

    Why the test stubs ``_handle_approve_command``: the production
    handler depends on heavy GatewayRunner state (translation, adapter
    lookup, typing-indicator services).  Stubbing it isolates the
    intercept's routing logic — which is the only thing this test
    asserts.  ``spy_resolve.assert_not_called()`` proves the intercept
    has no bypass path, not that the slash handler is correct.
    """
    _seed_pending(
        command="export AWS_SECRET_ACCESS_KEY=hunter2",
        description="set AWS credential",
        pattern_keys=("credential_export",),
    )
    runner = _make_runner_stub()
    event = _make_event("approved")

    with patch.object(
        approval_module, "resolve_gateway_approval",
        wraps=approval_module.resolve_gateway_approval,
    ) as spy_resolve:
        result = await _call_intercept(runner, event)

    runner._handle_approve_command.assert_awaited_once_with(event)
    spy_resolve.assert_not_called()
    assert result == "✅ approved-result"


@pytest.mark.asyncio
async def test_sensitive_resolve_actually_drains_queue_when_handler_runs_real() -> None:
    """Complementary to the routing test: when the slash handler IS allowed
    to call into ``resolve_gateway_approval`` (not stubbed), the formal
    queue is genuinely drained and the waiting thread wakes.

    Together with the routing test above, this closes the approval loop without
    needing to import the full GatewayRunner: we test the two halves of
    the chain separately and rely on the production path threading them
    together.
    """
    entry = _seed_pending(command="export OPENAI_API_KEY=hunter2")
    assert entry.result is None
    assert not entry.event.is_set()

    # Real call into the canonical resolver — same function the production
    # _handle_approve_command invokes.
    drained = approval_module.resolve_gateway_approval(SESSION_KEY, "once")

    assert drained == 1, "formal resolver must report exactly one entry drained"
    assert entry.result == "once", "entry must carry the choice the user made"
    assert entry.event.is_set(), "waiting thread must be unblocked"
    # Queue is empty after a single FIFO resolve.
    assert gateway_pending_count(SESSION_KEY) == 0


@pytest.mark.asyncio
async def test_waiting_thread_can_fire_ledger_hook_on_resolve_wakeup() -> None:
    """Mechanism test: a thread blocked on ``_ApprovalEntry.event`` resumes
    cleanly when ``resolve_gateway_approval`` is called, with the entry's
    ``result`` populated.  This is the wake-up half of the ledger flow.

    LIMITATION (honest disclosure): the actual ``_fire_approval_hook``
    call in production lives inside ``tools/approval.py:1290`` (the
    ``prompt_dangerous_approval`` function), which is too heavy to import
    here.  This test uses a *simulator* thread to model what production
    does on wake-up.  Asserting on the simulator's captured-hook list
    proves the resume mechanics (event-set propagation, result delivery)
    work — it does NOT prove that ``prompt_dangerous_approval`` itself
    fires the hook (that belongs to ``tests/tools/test_approval.py``).
    """
    entry = _seed_pending()
    captured_hooks: list[tuple[str, dict]] = []

    def _capture_hook(name: str, **kwargs):
        captured_hooks.append((name, kwargs))

    # An agent-thread simulator: wait on the entry's event, then fire the
    # post_approval_response hook with whatever result was deposited.
    # This mirrors what tools/approval.py:prompt_dangerous_approval does
    # in production when the blocked thread wakes up.
    agent_done = threading.Event()

    def _agent_thread():
        entry.event.wait(timeout=5)
        _capture_hook(
            "post_approval_response",
            command=entry.data.get("command"),
            result=entry.result,
            session_key=SESSION_KEY,
            surface="gateway",
        )
        agent_done.set()

    worker = threading.Thread(target=_agent_thread, daemon=True)
    worker.start()
    # Give the worker a beat to actually call event.wait()
    time.sleep(0.05)

    # Resolve directly via the formal API — this is what the real
    # _handle_approve_command does (we already verified the slash handler
    # is invoked by our intercept in the earlier sensitive-approval test).
    resolved = approval_module.resolve_gateway_approval(SESSION_KEY, "once")
    assert resolved == 1, "formal resolver must have drained exactly one entry"

    # The simulator should fire the ledger hook within a short window.
    assert agent_done.wait(timeout=2.0), "agent thread did not wake up"
    assert captured_hooks, "ledger hook was never invoked"

    name, kwargs = captured_hooks[0]
    assert name == "post_approval_response"
    assert kwargs["result"] == "once"
    assert kwargs["session_key"] == SESSION_KEY
    assert kwargs["surface"] == "gateway"


# ---------------------------------------------------------------------------
# Spec scenario 8: do not ask for approval twice
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_intercept_does_not_double_dispatch() -> None:
    """The intercept must invoke ``_handle_approve_command`` AT MOST ONCE
    for a single approval phrase.  A second call to the intercept on the
    same (already-drained) queue must NOT re-trigger /approve.
    """
    _seed_pending()
    runner = _make_runner_stub()
    event = _make_event("I approve")

    # First call — resolves the only pending entry.
    first = await _call_intercept(runner, event)
    assert first == "✅ approved-result"
    runner._handle_approve_command.assert_awaited_once_with(event)

    # Drain the queue manually to mimic what _handle_approve_command does
    # in production (the stub doesn't actually resolve).  The next intercept
    # call must observe zero pending and fall through — NOT route to
    # _handle_approve_command a second time.
    approval_module.resolve_gateway_approval(SESSION_KEY, "once")
    assert gateway_pending_count(SESSION_KEY) == 0

    second = await _call_intercept(runner, event)
    # Total calls to _handle_approve_command must still be 1.
    runner._handle_approve_command.assert_awaited_once_with(event)
    assert second is None


# ---------------------------------------------------------------------------
# Defensive scenarios — slash commands and conversational text fall through
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_slash_command_falls_through_to_normal_dispatch() -> None:
    """Slash-prefixed input (including ``/approve``) must NOT be intercepted
    here — those go through the normal command pipeline so /approve all,
    /approve session, etc. continue to work with their full argument
    parsing."""
    _seed_pending()
    runner = _make_runner_stub()
    event = _make_event("/approve all")

    result = await _call_intercept(runner, event)

    assert result is None
    runner._handle_approve_command.assert_not_called()
    runner._handle_deny_command.assert_not_called()


@pytest.mark.asyncio
async def test_conversational_text_falls_through() -> None:
    """Free-form conversation (no approve/deny phrase) must NOT be
    intercepted, even when an approval is pending — the user might be
    asking a question instead of replying to the approval prompt."""
    _seed_pending()
    runner = _make_runner_stub()
    event = _make_event("can you tell me why this command is dangerous?")

    result = await _call_intercept(runner, event)

    assert result is None
    runner._handle_approve_command.assert_not_called()


@pytest.mark.asyncio
async def test_session_isolation() -> None:
    """A pending approval in session A must not be drained by a phrase
    arriving for session B."""
    _seed_pending(session_key=OTHER_SESSION_KEY)
    runner = _make_runner_stub()
    event = _make_event("I approve")

    # Intercept is called for SESSION_KEY (the empty session).
    result = await _call_intercept(runner, event, session_key=SESSION_KEY)

    runner._handle_approve_command.assert_not_called()
    assert result is None
    # The other session's queue is still intact.
    assert gateway_pending_count(OTHER_SESSION_KEY) == 1


# ---------------------------------------------------------------------------
# list_gateway_pending — read-only snapshot helper
# ---------------------------------------------------------------------------
class TestListGatewayPending:
    def test_empty_session_returns_empty_list(self) -> None:
        with _lock:
            _gateway_queues.pop(SESSION_KEY, None)
        assert list_gateway_pending(SESSION_KEY) == []
        assert gateway_pending_count(SESSION_KEY) == 0

    def test_returns_snapshot_in_fifo_order(self) -> None:
        _seed_pending(command="cmd1", description="desc1")
        _seed_pending(command="cmd2", description="desc2")
        snapshot = list_gateway_pending(SESSION_KEY)
        assert [s["command"] for s in snapshot] == ["cmd1", "cmd2"]
        assert [s["description"] for s in snapshot] == ["desc1", "desc2"]

    def test_snapshot_is_decoupled_from_queue(self) -> None:
        _seed_pending(command="cmd1")
        snapshot = list_gateway_pending(SESSION_KEY)
        # Drain the queue.
        approval_module.resolve_gateway_approval(SESSION_KEY, "once")
        # The snapshot taken before the drain must still reflect the old state.
        assert len(snapshot) == 1
        # And the live count is now zero.
        assert gateway_pending_count(SESSION_KEY) == 0
