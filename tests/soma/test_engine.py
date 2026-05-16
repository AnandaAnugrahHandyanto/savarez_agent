"""Phase-1 proof: SomaEngine drives a fake AIAgent end-to-end.

These tests do NOT call a real model. They verify the wrapper:
  - passes user_message / conversation_history / system_message through
  - returns AIAgent's result dict unchanged
  - works synchronously and via the asyncio.to_thread bridge
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest

# Repo root on sys.path so `soma.*` and `run_agent` import side-by-side.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from soma.engine import EngineConfig, SomaEngine


class _FakeAgent:
    """Mimics the AIAgent API surface that SomaEngine touches."""

    def __init__(self):
        self.calls = []

    def run_conversation(self, user_message, conversation_history=None, system_message=None, **kwargs):
        self.calls.append({
            "user_message": user_message,
            "conversation_history": conversation_history,
            "system_message": system_message,
            "kwargs": kwargs,
        })
        return {
            "final_response": f"echo: {user_message}",
            "messages": (conversation_history or []) + [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": f"echo: {user_message}"},
            ],
            "api_calls": 1,
            "completed": True,
            "partial": False,
            "interrupted": False,
        }


class SomaEngineTest(unittest.TestCase):
    def _engine(self):
        return SomaEngine(EngineConfig(model="fake"), agent=_FakeAgent())

    def test_sync_passes_args_through(self):
        engine = self._engine()
        history = [{"role": "user", "content": "hi"}]
        result = engine.run_turn_sync(
            "make test.txt",
            conversation_history=history,
            system_message="You are Soma.",
        )

        self.assertEqual(result["final_response"], "echo: make test.txt")
        self.assertTrue(result["completed"])
        call = engine._agent.calls[0]
        self.assertEqual(call["user_message"], "make test.txt")
        self.assertEqual(call["conversation_history"], history)
        self.assertEqual(call["system_message"], "You are Soma.")

    def test_async_bridge_returns_same_result(self):
        engine = self._engine()
        result = asyncio.run(engine.run_turn("hello"))
        self.assertEqual(result["final_response"], "echo: hello")
        self.assertEqual(len(engine._agent.calls), 1)

    def test_empty_history_default(self):
        engine = self._engine()
        engine.run_turn_sync("ping")
        self.assertEqual(engine._agent.calls[0]["conversation_history"], [])


if __name__ == "__main__":
    unittest.main()
