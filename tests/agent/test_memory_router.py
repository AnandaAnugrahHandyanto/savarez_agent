from __future__ import annotations

from agent.memory_router import route_memory_candidates


class _FakeMemoryStore:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def add(self, target: str, content: str):
        self.calls.append((target, content))
        return {"success": True}


def test_route_memory_candidates_ignores_tool_messages() -> None:
    store = _FakeMemoryStore()
    messages = [
        {"role": "user", "content": "Repo state changed after the migration."},
        {"role": "tool", "content": "secret-token should never be persisted"},
        {"role": "assistant", "content": "Noted."},
    ]

    result = route_memory_candidates(
        invocation_mode="manual",
        session_id="sess-1",
        messages=messages,
        memory_store=store,
        memory_enabled=True,
        user_profile_enabled=False,
        config={},
    )

    assert result["ok"] is True
    assert store.calls == [("memory", "[USER] Repo state changed after the migration.\n[ASSISTANT] Noted.")]
    assert "secret-token" not in result["content"]


def test_route_memory_candidates_respects_disabled_user_profile() -> None:
    store = _FakeMemoryStore()
    messages = [
        {"role": "user", "content": "Please remember that I prefer concise responses."},
        {"role": "assistant", "content": "Got it."},
    ]

    result = route_memory_candidates(
        invocation_mode="manual",
        session_id="sess-2",
        messages=messages,
        memory_store=store,
        memory_enabled=True,
        user_profile_enabled=False,
        config={},
    )

    assert result["ok"] is True
    assert store.calls == []
    native = next(item for item in result["routed"] if item["destination"] == "native_memory")
    assert native["status"] == "no_op"
