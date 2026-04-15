import asyncio
import os

from gateway.config import Platform
from gateway.run import GatewayRunner
from gateway.session import SessionContext, SessionSource
from gateway.session_context import (
    get_session_env,
    set_session_vars,
    clear_session_vars,
)
import gateway.session_context as session_context


def test_set_session_env_sets_contextvars(monkeypatch):
    """_set_session_env should populate contextvars, not os.environ."""
    runner = object.__new__(GatewayRunner)
    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-1001",
        chat_name="Group",
        chat_type="group",
        user_id="123456",
        user_name="alice",
        thread_id="17585",
    )
    context = SessionContext(source=source, connected_platforms=[], home_channels={})

    monkeypatch.delenv("HERMES_SESSION_PLATFORM", raising=False)
    monkeypatch.delenv("HERMES_SESSION_CHAT_ID", raising=False)
    monkeypatch.delenv("HERMES_SESSION_CHAT_NAME", raising=False)
    monkeypatch.delenv("HERMES_SESSION_USER_ID", raising=False)
    monkeypatch.delenv("HERMES_SESSION_USER_NAME", raising=False)
    monkeypatch.delenv("HERMES_SESSION_THREAD_ID", raising=False)

    tokens = runner._set_session_env(context)

    # Values should be readable via get_session_env (contextvar path)
    assert get_session_env("HERMES_SESSION_PLATFORM") == "telegram"
    assert get_session_env("HERMES_SESSION_CHAT_ID") == "-1001"
    assert get_session_env("HERMES_SESSION_CHAT_NAME") == "Group"
    assert get_session_env("HERMES_SESSION_USER_ID") == "123456"
    assert get_session_env("HERMES_SESSION_USER_NAME") == "alice"
    assert get_session_env("HERMES_SESSION_THREAD_ID") == "17585"

    # os.environ should NOT be touched
    assert os.getenv("HERMES_SESSION_PLATFORM") is None
    assert os.getenv("HERMES_SESSION_THREAD_ID") is None

    # Clean up
    runner._clear_session_env(tokens)


def test_clear_session_env_restores_previous_state(monkeypatch):
    """_clear_session_env should restore contextvars to their pre-handler values."""
    runner = object.__new__(GatewayRunner)

    monkeypatch.delenv("HERMES_SESSION_PLATFORM", raising=False)
    monkeypatch.delenv("HERMES_SESSION_CHAT_ID", raising=False)
    monkeypatch.delenv("HERMES_SESSION_CHAT_NAME", raising=False)
    monkeypatch.delenv("HERMES_SESSION_USER_ID", raising=False)
    monkeypatch.delenv("HERMES_SESSION_USER_NAME", raising=False)
    monkeypatch.delenv("HERMES_SESSION_THREAD_ID", raising=False)

    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-1001",
        chat_name="Group",
        chat_type="group",
        user_id="123456",
        user_name="alice",
        thread_id="17585",
    )
    context = SessionContext(source=source, connected_platforms=[], home_channels={})

    tokens = runner._set_session_env(context)
    assert get_session_env("HERMES_SESSION_PLATFORM") == "telegram"
    assert get_session_env("HERMES_SESSION_USER_ID") == "123456"

    runner._clear_session_env(tokens)

    # After clear, contextvars should return to defaults (empty)
    assert get_session_env("HERMES_SESSION_PLATFORM") == ""
    assert get_session_env("HERMES_SESSION_CHAT_ID") == ""
    assert get_session_env("HERMES_SESSION_CHAT_NAME") == ""
    assert get_session_env("HERMES_SESSION_USER_ID") == ""
    assert get_session_env("HERMES_SESSION_USER_NAME") == ""
    assert get_session_env("HERMES_SESSION_THREAD_ID") == ""


def test_get_session_env_falls_back_to_os_environ(monkeypatch):
    """get_session_env should fall back to os.environ when contextvar is truly unset."""
    monkeypatch.setenv("HERMES_SESSION_PLATFORM", "discord")
    session_context._SESSION_PLATFORM.set(session_context._UNSET)
    session_context._SESSION_ACTIVE.set(False)

    # No contextvar set — should read from os.environ
    assert get_session_env("HERMES_SESSION_PLATFORM") == "discord"

    # Now set a contextvar — should prefer it
    tokens = set_session_vars(platform="telegram")
    assert get_session_env("HERMES_SESSION_PLATFORM") == "telegram"

    # Clear — should hide the value again instead of leaking stale env state
    clear_session_vars(tokens)
    assert get_session_env("HERMES_SESSION_PLATFORM") == ""


def test_get_session_env_uses_os_environ_when_never_initialized(monkeypatch):
    """A never-initialized variable should still fall back to os.environ."""
    monkeypatch.setenv("HERMES_SESSION_PLATFORM", "discord")
    session_context._SESSION_PLATFORM.set(session_context._UNSET)
    session_context._SESSION_ACTIVE.set(False)

    assert get_session_env("HERMES_SESSION_PLATFORM") == "discord"


def test_session_context_nested_clear_preserves_outer_state(monkeypatch):
    """Inner clear must not erase the outer session context."""
    monkeypatch.delenv("HERMES_SESSION_KEY", raising=False)
    outer = set_session_vars(session_key="outer-session")
    try:
        assert get_session_env("HERMES_SESSION_KEY") == "outer-session"
        inner = set_session_vars(session_key="inner-session")
        try:
            assert get_session_env("HERMES_SESSION_KEY") == "inner-session"
        finally:
            clear_session_vars(inner)
        assert get_session_env("HERMES_SESSION_KEY") == "outer-session"
    finally:
        clear_session_vars(outer)


def test_session_context_multiple_set_clear_cycles(monkeypatch):
    """Repeated set/clear cycles in the same task should remain safe."""
    monkeypatch.delenv("HERMES_SESSION_THREAD_ID", raising=False)

    first = set_session_vars(thread_id="thread-1")
    assert get_session_env("HERMES_SESSION_THREAD_ID") == "thread-1"
    clear_session_vars(first)
    assert get_session_env("HERMES_SESSION_THREAD_ID") == ""

    second = set_session_vars(thread_id="thread-2")
    assert get_session_env("HERMES_SESSION_THREAD_ID") == "thread-2"
    clear_session_vars(second)
    assert get_session_env("HERMES_SESSION_THREAD_ID") == ""


def test_get_session_env_default_when_nothing_set(monkeypatch):
    """get_session_env returns default when neither contextvar nor env is set."""
    monkeypatch.delenv("HERMES_SESSION_PLATFORM", raising=False)

    assert get_session_env("HERMES_SESSION_PLATFORM") == ""
    assert get_session_env("HERMES_SESSION_PLATFORM", "fallback") == "fallback"


def test_session_env_multiple_set_clear_cycles(monkeypatch):
    """Multiple set -> clear cycles should not leak stale values."""
    monkeypatch.delenv("HERMES_SESSION_KEY", raising=False)

    first = set_session_vars(session_key="s1")
    assert get_session_env("HERMES_SESSION_KEY") == "s1"
    clear_session_vars(first)
    assert get_session_env("HERMES_SESSION_KEY") == ""
    assert get_session_env("HERMES_SESSION_KEY", "default") == "default"

    second = set_session_vars(session_key="s2")
    assert get_session_env("HERMES_SESSION_KEY") == "s2"
    clear_session_vars(second)
    assert get_session_env("HERMES_SESSION_KEY") == ""
    assert get_session_env("HERMES_SESSION_KEY", "default") == "default"


def test_session_env_falls_back_to_os_environ_when_never_initialized(monkeypatch):
    """A never-initialized session var should still fall back to os.environ.

    This test must run in a fresh context where the ContextVar has never been
    set (still holds _UNSET). We achieve this by running inside a new
    contextvars.copy_context() so prior test state is invisible.
    """
    import contextvars

    monkeypatch.setenv("HERMES_SESSION_KEY", "env-val")

    result = {}

    def _run():
        # Inside a copied context the vars still carry whatever the current
        # context has. We need a truly virgin context, so reset them manually.
        from gateway.session_context import _SESSION_KEY, _UNSET  # type: ignore

        tok = _SESSION_KEY.set(_UNSET)
        try:
            result["value"] = get_session_env("HERMES_SESSION_KEY")
        finally:
            _SESSION_KEY.reset(tok)

    ctx = contextvars.copy_context()
    ctx.run(_run)

    assert result["value"] == "env-val"


def test_set_session_env_handles_missing_optional_fields():
    """_set_session_env should handle None chat_name and thread_id gracefully."""
    runner = object.__new__(GatewayRunner)
    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-1001",
        chat_name=None,
        chat_type="private",
        thread_id=None,
    )
    context = SessionContext(source=source, connected_platforms=[], home_channels={})

    tokens = runner._set_session_env(context)

    assert get_session_env("HERMES_SESSION_PLATFORM") == "telegram"
    assert get_session_env("HERMES_SESSION_CHAT_ID") == "-1001"
    assert get_session_env("HERMES_SESSION_CHAT_NAME") == ""
    assert get_session_env("HERMES_SESSION_THREAD_ID") == ""

    runner._clear_session_env(tokens)


# ---------------------------------------------------------------------------
# SESSION_KEY contextvars tests
# ---------------------------------------------------------------------------


def test_session_key_set_via_contextvars(monkeypatch):
    """set_session_vars should set HERMES_SESSION_KEY via contextvars."""
    monkeypatch.delenv("HERMES_SESSION_KEY", raising=False)

    tokens = set_session_vars(
        platform="telegram",
        chat_id="-1001",
        session_key="tg:-1001:17585",
    )
    assert get_session_env("HERMES_SESSION_KEY") == "tg:-1001:17585"

    clear_session_vars(tokens)
    assert get_session_env("HERMES_SESSION_KEY") == ""


def test_session_key_falls_back_to_os_environ(monkeypatch):
    """get_session_env for SESSION_KEY should fall back to os.environ when unset."""
    monkeypatch.setenv("HERMES_SESSION_KEY", "env-session-123")
    session_context._SESSION_KEY.set(session_context._UNSET)
    session_context._SESSION_ACTIVE.set(False)

    # No contextvar set — should read from os.environ
    assert get_session_env("HERMES_SESSION_KEY") == "env-session-123"

    # Set contextvar — should prefer it
    tokens = set_session_vars(session_key="ctx-session-456")
    assert get_session_env("HERMES_SESSION_KEY") == "ctx-session-456"

    # Clear — should not fall back to os.environ
    clear_session_vars(tokens)
    assert get_session_env("HERMES_SESSION_KEY") == ""


def test_set_session_env_includes_session_key():
    """_set_session_env should propagate session_key from SessionContext."""
    runner = object.__new__(GatewayRunner)
    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-1001",
        chat_name="Group",
        chat_type="group",
        thread_id="17585",
    )
    context = SessionContext(
        source=source,
        connected_platforms=[],
        home_channels={},
        session_key="tg:-1001:17585",
    )

    # Capture baseline value before setting (may be non-empty from another
    # test in the same pytest-xdist worker sharing the context).
    baseline = get_session_env("HERMES_SESSION_KEY")
    tokens = runner._set_session_env(context)
    assert get_session_env("HERMES_SESSION_KEY") == "tg:-1001:17585"
    runner._clear_session_env(tokens)
    assert get_session_env("HERMES_SESSION_KEY") == baseline



def test_session_key_no_race_condition_with_contextvars(monkeypatch):
    """Prove contextvars isolates SESSION_KEY across concurrent async tasks.

    Two tasks set different session keys. With contextvars each task
    reads back its own value. With os.environ the second task would
    overwrite the first (the old bug).
    """
    monkeypatch.delenv("HERMES_SESSION_KEY", raising=False)

    results = {}

    async def handler(key: str, delay: float):
        tokens = set_session_vars(session_key=key)
        try:
            await asyncio.sleep(delay)
            read_back = get_session_env("HERMES_SESSION_KEY")
            results[key] = read_back
        finally:
            clear_session_vars(tokens)

    async def run():
        task_a = asyncio.create_task(handler("session-A", 0.15))
        await asyncio.sleep(0.05)
        task_b = asyncio.create_task(handler("session-B", 0.05))
        await asyncio.gather(task_a, task_b)

    asyncio.run(run())

    # Both tasks must read back their own session key
    assert results["session-A"] == "session-A", (
        f"Session A got '{results['session-A']}' instead of 'session-A' — race condition!"
    )
    assert results["session-B"] == "session-B", (
        f"Session B got '{results['session-B']}' instead of 'session-B' — race condition!"
    )


def test_clear_session_vars_does_not_fall_back_to_stale_os_environ(monkeypatch):
    monkeypatch.setenv("HERMES_SESSION_THREAD_ID", "leaked-value")

    tokens = set_session_vars(thread_id="real-session")
    try:
        assert get_session_env("HERMES_SESSION_THREAD_ID") == "real-session"
    finally:
        clear_session_vars(tokens)

    assert get_session_env("HERMES_SESSION_THREAD_ID") != "leaked-value"
    assert get_session_env("HERMES_SESSION_THREAD_ID") == ""
