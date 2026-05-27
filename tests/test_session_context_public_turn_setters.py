"""Tests for public per-turn session-key setters in gateway.session_context.

These wrappers mirror tools/approval.py's set_current_session_key /
reset_current_session_key pattern but are deliberately named distinctly
(``turn_session_key``) because they target a different ContextVar
(``_SESSION_KEY`` in gateway.session_context) than the approval-session
ContextVar (``_approval_session_key`` in tools.approval).
"""

from gateway.session_context import (
    _SESSION_KEY,
    set_current_turn_session_key,
    reset_current_turn_session_key,
)


def test_set_and_reset_round_trip():
    # Capture the surrounding-context value BEFORE setting so the post-reset
    # assertion is robust: an outer fixture / parent context could legitimately
    # hold "session-abc" itself, in which case a `!=` check would flake.
    previous = _SESSION_KEY.get()
    token = set_current_turn_session_key("session-abc")
    try:
        assert _SESSION_KEY.get() == "session-abc"
    finally:
        reset_current_turn_session_key(token)
    # After reset, the value returns to whatever it was before set() — the
    # module-level default (the _UNSET sentinel) for a fresh context, or the
    # surrounding context's value if one was already bound.
    assert _SESSION_KEY.get() is previous


def test_nested_set_reset():
    outer = set_current_turn_session_key("outer")
    try:
        assert _SESSION_KEY.get() == "outer"
        inner = set_current_turn_session_key("inner")
        try:
            assert _SESSION_KEY.get() == "inner"
        finally:
            reset_current_turn_session_key(inner)
        assert _SESSION_KEY.get() == "outer"
    finally:
        reset_current_turn_session_key(outer)


def test_empty_string_normalized():
    token = set_current_turn_session_key("")
    try:
        assert _SESSION_KEY.get() == ""
    finally:
        reset_current_turn_session_key(token)


def test_none_normalized_to_empty():
    # set_current_turn_session_key(None) should not raise; treat as "".
    token = set_current_turn_session_key(None)  # type: ignore[arg-type]
    try:
        assert _SESSION_KEY.get() == ""
    finally:
        reset_current_turn_session_key(token)
