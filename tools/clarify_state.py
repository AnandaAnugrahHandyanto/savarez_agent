"""Blocking gateway clarify state for interactive user questions."""

from __future__ import annotations

import itertools
import threading
from typing import Callable, Optional

_lock = threading.Lock()
_clarify_counter = itertools.count(1)
_gateway_queues: dict[str, list["_ClarifyEntry"]] = {}


class _ClarifyEntry:
    """One pending clarify prompt inside a gateway session."""

    __slots__ = ("event", "clarify_id", "question", "choices", "result")

    def __init__(self, clarify_id: int, question: str, choices: Optional[list[str]]):
        self.event = threading.Event()
        self.clarify_id = clarify_id
        self.question = question
        self.choices = list(choices) if choices else None
        self.result: Optional[str] = None


def _coerce_response(entry: _ClarifyEntry, response: str) -> str:
    """Map numeric replies like '1' or '/2' to the actual choice label."""
    answer = str(response).strip()
    if not entry.choices:
        return answer

    numeric = answer[1:].strip() if answer.startswith("/") else answer
    if numeric.isdigit():
        idx = int(numeric) - 1
        if 0 <= idx < len(entry.choices):
            return entry.choices[idx]
    return answer


def request_gateway_clarify(
    session_key: str,
    question: str,
    choices: Optional[list[str]] = None,
    notify_callback: Optional[Callable[[dict], None]] = None,
    timeout_seconds: int = 300,
) -> str:
    """Block until the user answers a gateway clarify request."""
    if not session_key:
        raise ValueError("session_key is required for gateway clarify requests.")
    if notify_callback is None:
        raise RuntimeError("No notify callback is registered for gateway clarify.")

    clarify_id = next(_clarify_counter)
    entry = _ClarifyEntry(clarify_id=clarify_id, question=question, choices=choices)
    clarify_data = {
        "clarify_id": clarify_id,
        "question": question,
        "choices": list(entry.choices) if entry.choices else None,
    }

    with _lock:
        _gateway_queues.setdefault(session_key, []).append(entry)

    try:
        notify_callback(clarify_data)
    except Exception:
        with _lock:
            queue = _gateway_queues.get(session_key, [])
            if entry in queue:
                queue.remove(entry)
            if not queue:
                _gateway_queues.pop(session_key, None)
        raise

    resolved = entry.event.wait(timeout=timeout_seconds)

    with _lock:
        queue = _gateway_queues.get(session_key, [])
        if entry in queue:
            queue.remove(entry)
        if not queue:
            _gateway_queues.pop(session_key, None)

    if not resolved or entry.result is None:
        raise TimeoutError("Clarify request timed out.")

    return entry.result


def resolve_gateway_clarify(
    session_key: str,
    response: str,
    clarify_id: Optional[int] = None,
) -> int:
    """Resolve a pending clarify request for a session."""
    with _lock:
        queue = _gateway_queues.get(session_key)
        if not queue:
            return 0

        target: Optional[_ClarifyEntry] = None
        if clarify_id is None:
            target = queue.pop(0)
        else:
            for idx, entry in enumerate(queue):
                if entry.clarify_id == clarify_id:
                    target = queue.pop(idx)
                    break
            if target is None:
                return 0

        if not queue:
            _gateway_queues.pop(session_key, None)

    target.result = _coerce_response(target, response)
    target.event.set()
    return 1


def has_blocking_clarify(session_key: str) -> bool:
    """Return True when a session has one or more pending clarify prompts."""
    with _lock:
        return bool(_gateway_queues.get(session_key))


def peek_pending_clarify(session_key: str) -> Optional[dict]:
    """Return metadata for the oldest pending clarify prompt in a session."""
    with _lock:
        queue = _gateway_queues.get(session_key) or []
        if not queue:
            return None
        entry = queue[0]
        return {
            "clarify_id": entry.clarify_id,
            "question": entry.question,
            "choices": list(entry.choices) if entry.choices else None,
        }


def clear_gateway_clarify(session_key: str) -> None:
    """Signal all pending clarifies for a session so blocked threads can exit."""
    with _lock:
        entries = _gateway_queues.pop(session_key, [])
    for entry in entries:
        entry.event.set()
