"""Tests for _list_recent_sessions / _show_recent_sessions — `★ LATEST` badge
on the most-recently-active session in the inline recent-sessions list
shown by /history, /resume (no arg), and `sessions` UX entry points.

See issue #17352.
"""

import io
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import MagicMock

import cli as cli_mod


def _make_bare_cli():
    """Build a HermesCLI instance without running __init__ — we only need
    the attributes touched by _list_recent_sessions / _show_recent_sessions.
    """
    instance = cli_mod.HermesCLI.__new__(cli_mod.HermesCLI)
    instance.session_id = "current-session-id"
    instance._session_db = None  # set per-test
    return instance


def test_list_recent_sessions_orders_by_last_active():
    """The inline recent-sessions list must order by *last-active* time so the
    ``★ LATEST`` marker on row 0 is actually the most-recently-touched
    session. Without ``order_by_last_active=True`` the list comes back ordered
    by ``started_at`` and a recently resumed older session is buried below
    newer-but-idle ones."""
    cli = _make_bare_cli()
    fake_db = MagicMock()
    fake_db.list_sessions_rich.return_value = [
        {"id": "sess-a", "title": "Recent", "last_active": 1748080800.0},
        {"id": "sess-b", "title": "Older", "last_active": 1747994400.0},
    ]
    cli._session_db = fake_db

    cli._list_recent_sessions(limit=10)

    fake_db.list_sessions_rich.assert_called_once()
    kwargs = fake_db.list_sessions_rich.call_args.kwargs
    assert kwargs.get("order_by_last_active") is True, (
        "recent-sessions list must request last-active ordering — without it the "
        "first row (which gets the ★ LATEST marker) can be a newer-but-idle session"
    )


def test_list_recent_sessions_excludes_current_session():
    """The current session must not appear in the resume picker — resuming
    your own session is a no-op and clutters the list."""
    cli = _make_bare_cli()
    cli.session_id = "current"
    fake_db = MagicMock()
    fake_db.list_sessions_rich.return_value = [
        {"id": "current", "title": "Me", "last_active": 1748080800.0},
        {"id": "other", "title": "Other", "last_active": 1747994400.0},
    ]
    cli._session_db = fake_db

    result = cli._list_recent_sessions()

    assert [s["id"] for s in result] == ["other"]


def test_show_recent_sessions_marks_first_row_with_latest_star():
    """The first session row (most-recently-active after ordering) must be
    prefixed with ``★`` so users can identify the latest session at a glance.
    Issue #17352."""
    cli = _make_bare_cli()
    cli._list_recent_sessions = lambda limit=10: [
        {"id": "sess-a", "title": "Latest one", "preview": "hello", "last_active": 1748080800.0},
        {"id": "sess-b", "title": "Older one", "preview": "earlier", "last_active": 1747994400.0},
    ]

    buf = io.StringIO()
    with redirect_stdout(buf):
        shown = cli._show_recent_sessions(reason="resume")

    out = buf.getvalue()
    assert shown is True
    assert "★" in out, f"latest-session star marker missing from output:\n{out}"
    # ★ must precede the latest session's title, not the second row.
    star_idx = out.index("★")
    latest_idx = out.index("Latest one")
    older_idx = out.index("Older one")
    assert star_idx < latest_idx < older_idx, (
        "★ must appear on the row of the most-recently-active session, not below it"
    )
    # The legend on the footer should explain the marker so users understand what ★ means.
    assert "★" in out.split("Use /resume")[0] or "most recently active" in out.lower()


def test_show_recent_sessions_returns_false_when_no_sessions():
    """When there are no other sessions to resume, the helper must report so
    the caller can fall back to a different message (e.g. `/history` empty
    state) instead of printing an empty table."""
    cli = _make_bare_cli()
    cli._list_recent_sessions = lambda limit=10: []

    buf = io.StringIO()
    with redirect_stdout(buf):
        shown = cli._show_recent_sessions(reason="resume")

    assert shown is False
    assert "★" not in buf.getvalue()
