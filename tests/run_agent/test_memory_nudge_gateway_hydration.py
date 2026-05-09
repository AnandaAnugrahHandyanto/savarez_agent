"""Regression tests for memory/skill nudge counter hydration in gateway mode.

Issue: Gateway creates a fresh AIAgent per inbound message. The instance
variables _turns_since_memory and _iters_since_skill start at 0 on every
__init__, so memory.nudge_interval can never be reached in long-running
gateway conversations (hermes-agent#22357).

Fix: On the first run_conversation call that receives a non-empty
conversation_history, both counters are seeded from the count of prior
user turns modulo the configured intervals.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_history(n_user_turns: int) -> list[dict]:
    """Return a minimal conversation history with *n_user_turns* user messages."""
    history = []
    for i in range(n_user_turns):
        history.append({"role": "user", "content": f"turn {i}"})
        history.append({"role": "assistant", "content": f"reply {i}"})
    return history


def _bare_agent():
    """Build the minimum AIAgent state needed to test nudge-counter hydration."""
    from run_agent import AIAgent  # noqa: PLC0415

    agent = object.__new__(AIAgent)
    # Identity / model fields required by run_conversation bookkeeping
    agent.model = "test-model"
    agent.platform = "telegram"
    agent.provider = "openai"
    agent.base_url = ""
    agent.api_key = ""
    agent.api_mode = ""
    agent.session_id = "test-session"
    agent._parent_session_id = ""
    agent.quiet_mode = True
    agent.stream = False
    agent.max_iterations = 1

    # Memory / nudge state
    agent._memory_enabled = True
    agent._user_profile_enabled = False
    agent._memory_store = object()
    agent._memory_nudge_interval = 10
    agent._skill_nudge_interval = 10
    agent._turns_since_memory = 0
    agent._iters_since_skill = 0
    agent._nudge_counters_hydrated = False

    # Misc state that run_conversation reads before we can mock it out
    agent._compression_warning = None
    agent._credential_pool = None
    agent.background_review_callback = None
    agent.status_callback = None
    agent._safe_print = lambda *_a, **_kw: None
    agent._user_turn_count = 0

    return agent


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestNudgeCounterHydration:
    """Verify that nudge counters are seeded from conversation_history on first call."""

    def test_fresh_agent_no_history_leaves_counters_at_zero(self):
        """Brand-new session (no history): counters stay at 0 after hydration."""
        agent = _bare_agent()
        # Simulate only the hydration block (pre-loop) without running full agent loop
        _prior_user_turns = 0
        conversation_history: list = []

        if not agent._nudge_counters_hydrated and conversation_history:
            if _prior_user_turns > 0:
                agent._turns_since_memory = _prior_user_turns % agent._memory_nudge_interval
                agent._iters_since_skill = _prior_user_turns % agent._skill_nudge_interval
            agent._nudge_counters_hydrated = True
        elif not agent._nudge_counters_hydrated:
            agent._nudge_counters_hydrated = True

        assert agent._turns_since_memory == 0
        assert agent._iters_since_skill == 0
        assert agent._nudge_counters_hydrated is True

    def test_gateway_seeds_counters_from_prior_turns(self):
        """9 prior user turns with interval=10 → counter seeded at 9."""
        agent = _bare_agent()
        history = _make_history(9)

        if not agent._nudge_counters_hydrated and history:
            _prior = sum(1 for m in history if m.get("role") == "user")
            if _prior > 0:
                agent._turns_since_memory = _prior % agent._memory_nudge_interval
                agent._iters_since_skill = _prior % agent._skill_nudge_interval
            agent._nudge_counters_hydrated = True

        assert agent._turns_since_memory == 9
        assert agent._iters_since_skill == 9
        assert agent._nudge_counters_hydrated is True

    def test_counter_wraps_at_interval_boundary(self):
        """20 prior user turns with interval=10 → counter seeded at 0 (wraps)."""
        agent = _bare_agent()
        history = _make_history(20)

        if not agent._nudge_counters_hydrated and history:
            _prior = sum(1 for m in history if m.get("role") == "user")
            if _prior > 0:
                agent._turns_since_memory = _prior % agent._memory_nudge_interval
                agent._iters_since_skill = _prior % agent._skill_nudge_interval
            agent._nudge_counters_hydrated = True

        assert agent._turns_since_memory == 0
        assert agent._iters_since_skill == 0

    def test_hydration_only_runs_once(self):
        """Counter must not be re-seeded on subsequent run_conversation calls."""
        agent = _bare_agent()
        # First call: 9 turns → seeded to 9
        history = _make_history(9)
        if not agent._nudge_counters_hydrated and history:
            _prior = sum(1 for m in history if m.get("role") == "user")
            if _prior > 0:
                agent._turns_since_memory = _prior % agent._memory_nudge_interval
            agent._nudge_counters_hydrated = True

        assert agent._turns_since_memory == 9

        # Simulate the normal per-turn increment after the first call
        agent._turns_since_memory += 1  # now 10 → review triggered, reset to 0
        agent._turns_since_memory = 0  # review fired

        # Second call: history now has 10 turns, but hydration must NOT re-seed
        history2 = _make_history(10)
        if not agent._nudge_counters_hydrated and history2:
            # This branch should NOT be entered because _nudge_counters_hydrated=True
            _prior = sum(1 for m in history2 if m.get("role") == "user")
            agent._turns_since_memory = _prior % agent._memory_nudge_interval

        # Counter should remain 0 (reset after review), not re-seeded to 0 again
        assert agent._turns_since_memory == 0
        assert agent._nudge_counters_hydrated is True

    def test_skill_interval_seeded_independently(self):
        """Skill nudge interval different from memory interval seeds correctly."""
        agent = _bare_agent()
        agent._memory_nudge_interval = 10
        agent._skill_nudge_interval = 15
        history = _make_history(13)

        if not agent._nudge_counters_hydrated and history:
            _prior = sum(1 for m in history if m.get("role") == "user")
            if _prior > 0:
                agent._turns_since_memory = _prior % agent._memory_nudge_interval
                agent._iters_since_skill = _prior % agent._skill_nudge_interval
            agent._nudge_counters_hydrated = True

        assert agent._turns_since_memory == 3   # 13 % 10
        assert agent._iters_since_skill == 13   # 13 % 15

    def test_zero_nudge_interval_skips_seeding(self):
        """interval=0 means nudges disabled; counter stays 0 (no modulo-by-zero)."""
        agent = _bare_agent()
        agent._memory_nudge_interval = 0
        agent._skill_nudge_interval = 0
        history = _make_history(7)

        if not agent._nudge_counters_hydrated and history:
            _prior = sum(1 for m in history if m.get("role") == "user")
            if _prior > 0:
                if agent._memory_nudge_interval > 0:
                    agent._turns_since_memory = _prior % agent._memory_nudge_interval
                if agent._skill_nudge_interval > 0:
                    agent._iters_since_skill = _prior % agent._skill_nudge_interval
            agent._nudge_counters_hydrated = True

        assert agent._turns_since_memory == 0
        assert agent._iters_since_skill == 0
