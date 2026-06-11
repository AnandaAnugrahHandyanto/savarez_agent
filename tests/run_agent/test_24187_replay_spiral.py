"""#24187 — end-to-end reproduction of the SessionDB replay-loop.

Drives the **real** ``run_conversation()`` across a multi-turn gateway loop
(fresh ``AIAgent`` per inbound message, history reloaded from a real
``hermes_state.SessionDB`` each turn, mocked provider) and proves the
self-reinforcing replay spiral cannot start.

The function-level contract is pinned in ``test_message_sequence_repair.py``;
this closes the gap those tests' docstring calls out — nothing exercised the
bug through the actual ``run_conversation()`` call site.

Production evidence (session 20260609_160142_0c197c39): one interrupted turn
seeded a user/user alternation violation; from then on normally-paced turns
lost their assistant replies — 5 replies generated and delivered to Matrix
with no corresponding rows in state.db, the "Repaired N" counter climbing 1→10.
The test is bug-sensitive: against the pre-fix wiring (repair on the canonical
list) it fails with zero assistant rows persisted and the counter climbing 1→5.
"""

import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from run_agent import AIAgent


def _mock_provider_response(content):
    msg = SimpleNamespace(content=content, tool_calls=None, reasoning=None)
    choice = SimpleNamespace(message=msg, finish_reason="stop")
    return SimpleNamespace(
        choices=[choice],
        model="test/model",
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


def _make_agent(session_db, session_id, reply):
    """A real AIAgent wired to a real SessionDB with a canned provider reply.

    Mirrors the gateway: a fresh agent per inbound message (so
    ``_last_flushed_db_idx`` starts at 0 every turn).
    """
    with (
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        agent = AIAgent(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            session_db=session_db,
            session_id=session_id,
            platform="matrix",
        )
    agent.client = MagicMock()
    agent.client.chat.completions.create.return_value = _mock_provider_response(reply)
    return agent


def test_run_conversation_gateway_loop_persists_every_reply():
    """The replay spiral never starts when driven through the real loop.

    Seed one user/user violation, then run five normally-paced gateway turns
    against the real ``run_conversation()``. Every assistant reply must reach
    SessionDB and the repair counter must stay flat — pre-fix, the replies
    were dropped and the counter escalated 1→5.
    """
    from hermes_state import SessionDB

    repair_counts = []
    _real_repair = AIAgent._repair_message_sequence

    def _recording_repair(self, msgs):
        n = _real_repair(self, msgs)
        repair_counts.append(n)
        return n

    N = 5
    with (
        tempfile.TemporaryDirectory() as tmpdir,
        patch.object(AIAgent, "_repair_message_sequence", _recording_repair),
    ):
        db = SessionDB(db_path=Path(tmpdir) / "state.db")
        sid = "20260609_replay_spiral"
        db.create_session(session_id=sid, source="test")
        # Seed: a turn interrupted before its reply was appended leaves an
        # orphan user row — the single alternation violation that starts it.
        db.append_message(session_id=sid, role="user", content="seed (interrupted turn)")

        for i in range(N):
            # Fresh agent per inbound message; history reloaded from SessionDB.
            history = [
                {"role": r["role"], "content": r["content"]}
                for r in db.get_messages(sid)
            ]
            agent = _make_agent(db, sid, reply=f"answer {i}")
            result = agent.run_conversation(
                f"question {i}", conversation_history=history
            )
            # The model generated and returned the reply every turn (as in
            # production, where all replies were delivered to Matrix).
            assert result["final_response"] == f"answer {i}"

        rows = [(r.get("role"), r.get("content")) for r in db.get_messages(sid)]
        db.close()

    assistant_rows = [c for role, c in rows if role == "assistant"]
    user_rows = [c for role, c in rows if role == "user"]

    # Every reply persisted, in order — the row the bug silently dropped.
    assert assistant_rows == [f"answer {i}" for i in range(N)], assistant_rows
    # User rows: the seed plus one answered question per turn.
    assert user_rows == ["seed (interrupted turn)"] + [
        f"question {i}" for i in range(N)
    ], user_rows
    # No runaway: the repair counter never climbs past the single seed
    # violation. Pre-fix it escalated one-per-turn (1, 2, 3, 4, 5).
    assert max(repair_counts) <= 1, repair_counts
    assert repair_counts != [1, 2, 3, 4, 5]
