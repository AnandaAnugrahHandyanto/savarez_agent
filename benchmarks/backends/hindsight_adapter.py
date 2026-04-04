"""Benchmark adapter for the Hindsight cloud memory backend.

Hindsight is a hosted memory service accessed via the hindsight_client SDK.
This adapter wraps retain/recall calls in a dedicated thread to avoid event-loop
conflicts with the benchmark harness, matching the pattern used by other adapters.
"""

from __future__ import annotations

import os
import queue
import threading
from typing import Any, Optional

from benchmarks.capabilities import BackendCapabilities
from benchmarks.interface import BenchmarkableStore

BACKEND_NAME = "hindsight"
BACKEND_CAPABILITIES = BackendCapabilities(
    universal_store_recall=True,
)


def _run_in_thread(fn, timeout: float = 30.0):
    """Run *fn* in a daemon thread that has no asyncio event loop.

    This prevents conflicts when the calling thread already owns an event loop
    (e.g. pytest-asyncio or Jupyter environments).
    """
    result_q: queue.Queue = queue.Queue(maxsize=1)

    def _run():
        import asyncio  # noqa: PLC0415

        asyncio.set_event_loop(None)
        try:
            result_q.put(("ok", fn()))
        except Exception as exc:  # noqa: BLE001
            result_q.put(("err", exc))

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    kind, value = result_q.get(timeout=timeout)
    if kind == "err":
        raise value
    return value


class HindsightBenchmarkAdapter(BenchmarkableStore):
    """Adapter exposing the Hindsight cloud backend through BenchmarkableStore."""

    def __init__(self, **kwargs):
        api_key = os.environ.get("HINDSIGHT_API_KEY")
        if not api_key:
            raise RuntimeError(
                "HINDSIGHT_API_KEY environment variable is not set. "
                "Export a valid API key before running Hindsight benchmarks."
            )

        from hindsight_client import Hindsight  # noqa: PLC0415

        self._client = Hindsight(api_key=api_key)
        self._bank_id: str = kwargs.get("bank_id", "benchmark-bank")
        self._budget: str = kwargs.get("budget", "mid")

    # ------------------------------------------------------------------
    # BenchmarkableStore interface
    # ------------------------------------------------------------------

    def store(
        self,
        content: str,
        category: str = "factual",
        scope: str = "global",
        importance: float = 0.5,
    ) -> None:
        del category, scope, importance
        client = self._client
        bank_id = self._bank_id
        _run_in_thread(
            lambda: client.retain(bank_id=bank_id, content=content, context="benchmark")
        )

    def recall(
        self,
        query: str,
        top_k: int = 10,
        scope: Optional[str] = None,
    ) -> list[str]:
        del scope
        client = self._client
        bank_id = self._bank_id
        budget = self._budget
        resp = _run_in_thread(
            lambda: client.recall(bank_id=bank_id, query=query, budget=budget)
        )
        return [r.text for r in resp.results[:top_k]]

    def simulate_time(self, days: float) -> None:
        del days
        # Hindsight is a cloud service with no local time-simulation hook.
        return None

    def simulate_access(self, content_substring: str) -> None:
        del content_substring
        # No rehearsal API available; leave as no-op.
        return None

    def consolidate(self) -> None:
        # Consolidation is managed server-side; no client hook available.
        return None

    def get_stats(self) -> dict[str, Any]:
        return {
            "backend": "hindsight",
            "bank_id": self._bank_id,
            "configured": True,
        }

    def reset(self) -> None:
        # Cloud banks cannot be reset in a benchmark context; no-op.
        return None


BACKEND_CLASS = HindsightBenchmarkAdapter
