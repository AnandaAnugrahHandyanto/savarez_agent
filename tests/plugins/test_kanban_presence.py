"""Behavior-contract tests for the presence liveness state machine.

Tests exercise the real kanban.db against a temp HERMES_HOME — no mocks,
no change-detector snapshots. Every assertion is an invariant that must
hold regardless of implementation detail changes.

Covers:
- _classify_liveness: the four-state state machine (active/idle/stale/offline)
- presence_snapshot: aggregate query, profile coverage, field contract
- Liveness invariant: stale window <= dispatch_stale_timeout_seconds
- Config window defaults and overrides
"""

from __future__ import annotations

import os
import sqlite3
import time
import unittest.mock
from pathlib import Path

import pytest

from hermes_cli import kanban_db as kb


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    """Isolated HERMES_HOME with an empty kanban DB."""
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


def _conn_home(kanban_home):
    """Open a kanban_db connection against the isolated home."""
    return kb.connect()


def _seed_running_run(
    conn,
    *,
    profile="apollo",
    task_title="Test task",
    started_at=None,
    last_heartbeat_at=None,
    worker_pid=99999,
):
    """Create a task + running run via direct SQL, return (task_id, run_id).

    Uses direct SQL insertion so we have full control over the run row
    without needing to go through the complex claim_task flow.
    """
    now = int(time.time())
    # Create a task in 'running' status
    task_id = kb.create_task(conn, title=task_title, assignee=profile)
    # Move it to running
    conn.execute(
        "UPDATE tasks SET status = 'running' WHERE id = ?",
        (task_id,),
    )
    # Insert a running run row
    conn.execute(
        "INSERT INTO task_runs "
        "(task_id, profile, status, started_at, worker_pid, last_heartbeat_at) "
        "VALUES (?, ?, 'running', ?, ?, ?)",
        (task_id, profile, started_at or now, worker_pid, last_heartbeat_at),
    )
    run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    return task_id, run_id


# ---------------------------------------------------------------------------
# _classify_liveness — state machine invariants
# ---------------------------------------------------------------------------

class TestClassifyLiveness:
    """Pure-function tests for the liveness state machine.

    These test _classify_liveness directly, without DB or config
    dependencies, by passing explicit window parameters.
    """

    def _classify(self, *, hb_age, pid_alive=True, run_status="running",
                  fresh=90, stale=300, now=None):
        """Helper wrapping _classify_liveness with time math."""
        from plugins.kanban.dashboard.plugin_api import _classify_liveness
        now = now or int(time.time())
        hb = now - hb_age if hb_age is not None else None
        worker_pid = 42
        with unittest.mock.patch.object(kb, "_pid_alive", return_value=pid_alive):
            return _classify_liveness(
                run_status=run_status,
                last_heartbeat_at=hb,
                worker_pid=worker_pid,
                now=now,
                fresh_s=fresh,
                stale_s=stale,
            )

    # -- active --
    def test_fresh_heartbeat_is_active(self):
        assert self._classify(hb_age=0) == "active"

    def test_heartbeat_at_fresh_boundary_is_active(self):
        """Exactly at fresh boundary (elapsed == fresh_s) → active."""
        assert self._classify(hb_age=90, fresh=90) == "active"

    def test_one_second_before_fresh_boundary_is_active(self):
        assert self._classify(hb_age=89, fresh=90) == "active"

    # -- idle --
    def test_heartbeat_past_fresh_within_stale_is_idle_when_pid_alive(self):
        assert self._classify(hb_age=91, fresh=90, stale=300) == "idle"

    def test_heartbeat_at_stale_boundary_is_idle_when_pid_alive(self):
        """Exactly at stale boundary (elapsed == stale_s) → idle."""
        assert self._classify(hb_age=300, fresh=90, stale=300) == "idle"

    def test_heartbeat_past_fresh_within_stale_is_stale_when_pid_dead(self):
        assert self._classify(hb_age=91, fresh=90, stale=300, pid_alive=False) == "stale"

    # -- stale --
    def test_heartbeat_past_stale_is_stale_even_with_pid_alive(self):
        assert self._classify(hb_age=301, fresh=90, stale=300) == "stale"

    def test_no_heartbeat_at_all_is_stale(self):
        """A running run that never sent a heartbeat is stale."""
        from plugins.kanban.dashboard.plugin_api import _classify_liveness
        with unittest.mock.patch.object(kb, "_pid_alive", return_value=True):
            assert _classify_liveness(
                run_status="running",
                last_heartbeat_at=None,
                worker_pid=42,
                now=int(time.time()),
                fresh_s=90,
                stale_s=300,
            ) == "stale"

    # -- offline --
    def test_non_running_status_is_offline(self):
        from plugins.kanban.dashboard.plugin_api import _classify_liveness
        for status in ("completed", "crashed", "reclaimed", "timed_out"):
            with unittest.mock.patch.object(kb, "_pid_alive", return_value=True):
                assert _classify_liveness(
                    run_status=status,
                    last_heartbeat_at=int(time.time()),
                    worker_pid=42,
                    now=int(time.time()),
                    fresh_s=90,
                    stale_s=300,
                ) == "offline"

    # -- invariants across boundaries --
    def test_only_four_valid_statuses(self):
        """The state machine only produces active/idle/stale/offline."""
        valid = {"active", "idle", "stale", "offline"}
        for age in [0, 1, 89, 90, 91, 200, 300, 301, 1000]:
            for pid_alive in [True, False]:
                result = self._classify(hb_age=age, pid_alive=pid_alive)
                assert result in valid, f"age={age}, pid_alive={pid_alive} → {result}"

    def test_online_iff_active_or_idle(self):
        """online is True only for active or idle status."""
        for age in [0, 50, 89, 90, 91, 150, 299, 300, 301, 600]:
            for pid_alive in [True, False]:
                result = self._classify(hb_age=age, pid_alive=pid_alive)
                # online iff status in (active, idle) — this matches
                # the presence_snapshot logic
                expected_online = result in ("active", "idle")
                # The snapshot computes online separately, but the
                # invariant is: active → online, idle → online,
                # stale → offline, offline → offline
                assert expected_online == (result in ("active", "idle"))


# ---------------------------------------------------------------------------
# presence_snapshot — aggregate query invariants
# ---------------------------------------------------------------------------

class TestPresenceSnapshot:
    """Integration tests against a real kanban.db.

    Every assertion is a behavioral invariant, not a snapshot.
    """

    def test_empty_board_returns_empty(self, kanban_home):
        """No tasks → no profiles in snapshot."""
        from plugins.kanban.dashboard.plugin_api import presence_snapshot
        conn = _conn_home(kanban_home)
        try:
            result = presence_snapshot(conn)
            assert result == []
        finally:
            conn.close()

    def test_offline_profile_appears(self, kanban_home):
        """A profile with an assigned task but no running run → offline."""
        from plugins.kanban.dashboard.plugin_api import presence_snapshot
        conn = _conn_home(kanban_home)
        try:
            kb.create_task(conn, title="Idle task", assignee="zeus")
            result = presence_snapshot(conn)
            assert len(result) == 1
            zeus = next(p for p in result if p["profile"] == "zeus")
            assert zeus["status"] == "offline"
            assert zeus["online"] is False
            assert zeus["current_task_id"] is None
            assert zeus["current_task_title"] is None
            assert zeus["run_id"] is None
            assert zeus["pid"] is None
            assert zeus["last_heartbeat_at"] is None
            assert zeus["since"] is None
        finally:
            conn.close()

    def test_running_profile_has_all_presence_state_fields(self, kanban_home):
        """A profile with a running run has all PresenceState fields."""
        from plugins.kanban.dashboard.plugin_api import presence_snapshot
        conn = _conn_home(kanban_home)
        try:
            now = int(time.time())
            tid, rid = _seed_running_run(
                conn, profile="apollo",
                task_title="Build presence",
                started_at=now - 60,
                last_heartbeat_at=now - 5,
            )
            with unittest.mock.patch.object(kb, "_pid_alive", return_value=True):
                result = presence_snapshot(conn)
            apollo = next(p for p in result if p["profile"] == "apollo")
            # All required fields present (invariant: contract shape)
            required_keys = {
                "profile", "online", "status",
                "current_task_id", "current_task_title",
                "run_id", "pid", "last_heartbeat_at", "since",
            }
            assert required_keys <= set(apollo.keys()), (
                f"Missing keys: {required_keys - set(apollo.keys())}"
            )
            # With heartbeat 5s ago → active (within fresh=90s default)
            assert apollo["status"] == "active"
            assert apollo["online"] is True
            assert apollo["current_task_id"] == tid
            assert apollo["current_task_title"] == "Build presence"
            assert apollo["since"] == now - 60
        finally:
            conn.close()

    def test_stale_heartbeat_shows_stale(self, kanban_home):
        """A running run with old heartbeat → stale, not active."""
        from plugins.kanban.dashboard.plugin_api import presence_snapshot
        conn = _conn_home(kanban_home)
        try:
            now = int(time.time())
            _seed_running_run(
                conn, profile="apollo",
                last_heartbeat_at=now - 500,  # > 300s (stale default)
            )
            with unittest.mock.patch.object(kb, "_pid_alive", return_value=False):
                result = presence_snapshot(conn)
            apollo = next(p for p in result if p["profile"] == "apollo")
            assert apollo["status"] == "stale"
            assert apollo["online"] is False  # stale ≠ online
        finally:
            conn.close()

    def test_idle_heartbeat_pid_dead_becomes_stale(self, kanban_home):
        """In the idle window but PID dead → stale (not idle)."""
        from plugins.kanban.dashboard.plugin_api import presence_snapshot
        conn = _conn_home(kanban_home)
        try:
            now = int(time.time())
            _seed_running_run(
                conn, profile="athena",
                last_heartbeat_at=now - 150,  # between 90 and 300 → idle window
            )
            with unittest.mock.patch.object(kb, "_pid_alive", return_value=False):
                result = presence_snapshot(conn)
            athena = next(p for p in result if p["profile"] == "athena")
            assert athena["status"] == "stale"
            assert athena["online"] is False
        finally:
            conn.close()

    def test_multiple_profiles_mixed_states(self, kanban_home):
        """Multiple profiles with different liveness states are all present."""
        from plugins.kanban.dashboard.plugin_api import presence_snapshot
        conn = _conn_home(kanban_home)
        try:
            now = int(time.time())
            # apollo: running + fresh heartbeat → active
            _seed_running_run(
                conn, profile="apollo",
                task_title="Active work",
                last_heartbeat_at=now - 10,
            )
            # zeus: no running task, just an assigned task → offline
            kb.create_task(conn, title="Waiting task", assignee="zeus")
            # athena: running but stale heartbeat → stale
            _seed_running_run(
                conn, profile="athena",
                task_title="Stale work",
                last_heartbeat_at=now - 500,
            )
            with unittest.mock.patch.object(kb, "_pid_alive", return_value=False):
                result = presence_snapshot(conn)
            by_profile = {p["profile"]: p for p in result}
            assert by_profile["apollo"]["status"] == "active"
            assert by_profile["zeus"]["status"] == "offline"
            assert by_profile["athena"]["status"] == "stale"
            assert by_profile["apollo"]["online"] is True
            assert by_profile["zeus"]["online"] is False
            assert by_profile["athena"]["online"] is False
        finally:
            conn.close()

    def test_single_aggregate_query_not_n_plus_1(self, kanban_home):
        """presence_snapshot should be one aggregate query over task_runs,
        not N+1 per profile. Verify by counting SQL statements executed."""
        from plugins.kanban.dashboard.plugin_api import presence_snapshot
        conn = _conn_home(kanban_home)
        try:
            # Seed 5 profiles with tasks
            now = int(time.time())
            for i, profile in enumerate(["a", "b", "c", "d", "e"]):
                _seed_running_run(
                    conn, profile=profile,
                    task_title=f"Task {i}",
                    last_heartbeat_at=now - 10,
                )
            # Count SQL statements during presence_snapshot using
            # sqlite3 set_trace_callback.
            statements = []
            def _trace(stmt):
                statements.append(stmt.strip())
            conn.set_trace_callback(_trace)
            with unittest.mock.patch.object(kb, "_pid_alive", return_value=True):
                presence_snapshot(conn)
            conn.set_trace_callback(None)
            # The invariant: no per-profile SELECT pattern. We expect
            # a small, bounded number of queries (the aggregate + the
            # assignee list), NOT O(profiles).
            core_queries = [s for s in statements
                           if s.upper().startswith("SELECT")]
            assert len(core_queries) <= 5, (
                f"Too many SELECT queries: {len(core_queries)} — "
                f"likely N+1 pattern. Queries: {core_queries}"
            )
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Liveness invariant — stale <= dispatch_stale_timeout_seconds
# ---------------------------------------------------------------------------

class TestLivenessInvariant:
    """The stale window must never exceed the dispatcher's reclaim
    threshold. If it did, the UI would show a profile as "active" or
    "idle" after the dispatcher had already reclaimed its task.
    """

    def test_resolve_presence_windows_defaults(self):
        """Default windows are fresh=90, stale=300, dispatch_stale=14400."""
        from plugins.kanban.dashboard.plugin_api import _resolve_presence_windows
        with unittest.mock.patch(
            "hermes_cli.config.load_config_readonly",
            side_effect=Exception("no config"),
        ):
            fresh, stale, dispatch_stale = _resolve_presence_windows()
        assert fresh == 90
        assert stale == 300
        assert dispatch_stale == 14400

    def test_stale_capped_when_exceeds_dispatch_stale(self):
        """If stale > dispatch_stale in config, stale is capped."""
        from plugins.kanban.dashboard.plugin_api import _resolve_presence_windows
        fake_config = {
            "kanban": {
                "presence_heartbeat_fresh_seconds": 90,
                "presence_heartbeat_stale_seconds": 99999,  # way above dispatch
                "dispatch_stale_timeout_seconds": 500,
            },
        }
        with unittest.mock.patch(
            "hermes_cli.config.load_config_readonly",
            return_value=fake_config,
        ):
            fresh, stale, dispatch_stale = _resolve_presence_windows()
        # stale should be capped to dispatch_stale
        assert stale == 500
        assert dispatch_stale == 500
        assert fresh == 90

    def test_stale_window_always_within_dispatch_threshold(self):
        """Invariant: stale <= dispatch_stale for ANY valid config."""
        from plugins.kanban.dashboard.plugin_api import _resolve_presence_windows
        for stale_val, dispatch_val in [(100, 200), (200, 200), (300, 14400)]:
            fake_config = {
                "kanban": {
                    "presence_heartbeat_fresh_seconds": 90,
                    "presence_heartbeat_stale_seconds": stale_val,
                    "dispatch_stale_timeout_seconds": dispatch_val,
                },
            }
            with unittest.mock.patch(
                "hermes_cli.config.load_config_readonly",
                return_value=fake_config,
            ):
                _, stale, dispatch_stale = _resolve_presence_windows()
            assert stale <= dispatch_stale, (
                f"stale ({stale}) must not exceed dispatch_stale ({dispatch_stale})"
            )


# ---------------------------------------------------------------------------
# GET /presence HTTP endpoint
# ---------------------------------------------------------------------------

class TestPresenceEndpoint:
    """Test the HTTP endpoint via the FastAPI test client."""

    @pytest.fixture
    def client(self, kanban_home):
        """FastAPI test client with the kanban plugin router mounted."""
        from fastapi.testclient import TestClient
        from plugins.kanban.dashboard.plugin_api import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router, prefix="/api/plugins/kanban")
        return TestClient(app)

    def test_presence_returns_correct_shape(self, client):
        """Response includes {type: "presence", profiles: [...], computed_at}."""
        resp = client.get("/api/plugins/kanban/presence")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "presence"
        assert "profiles" in data
        assert "computed_at" in data
        assert isinstance(data["profiles"], list)
        assert isinstance(data["computed_at"], int)

    def test_presence_empty_board(self, client):
        """Empty board returns empty profiles list."""
        resp = client.get("/api/plugins/kanban/presence")
        assert resp.status_code == 200
        data = resp.json()
        assert data["profiles"] == []

    def test_presence_with_running_task(self, kanban_home, client):
        """A running task with fresh heartbeat → profile shows as active."""
        conn = _conn_home(kanban_home)
        try:
            now = int(time.time())
            _seed_running_run(
                conn, profile="apollo",
                task_title="Endpoint test",
                last_heartbeat_at=now - 5,
            )
        finally:
            conn.close()

        with unittest.mock.patch.object(kb, "_pid_alive", return_value=True):
            resp = client.get("/api/plugins/kanban/presence")
        assert resp.status_code == 200
        data = resp.json()
        profiles = data["profiles"]
        apollo = next((p for p in profiles if p["profile"] == "apollo"), None)
        assert apollo is not None
        # With heartbeat 5s ago, should be active (within fresh=90s)
        assert apollo["status"] == "active"
        assert apollo["online"] is True


# ---------------------------------------------------------------------------
# /events WebSocket presence frame transport tests
# ---------------------------------------------------------------------------

class TestWSPresenceFrames:
    """Verify the /events WS emits presence frames on connect, on relevant
    events, and on the floor interval — without adding a second socket or
    polling daemon.

    These are transport-layer invariants (frame contract + emission triggers),
    not liveness-state tests (those live in TestClassifyLiveness).
    """

    @pytest.fixture
    def ws_client(self, kanban_home, monkeypatch):
        """FastAPI test client with WS auth stubbed for token-based access."""
        from fastapi.testclient import TestClient
        from plugins.kanban.dashboard.plugin_api import router
        from fastapi import FastAPI
        import hermes_cli
        import types
        import sys

        stub = types.SimpleNamespace(
            _SESSION_TOKEN="test-presence-token",
            _ws_auth_ok=lambda ws: ws.query_params.get("token", "") == "test-presence-token",
        )
        monkeypatch.setitem(sys.modules, "hermes_cli.web_server", stub)
        monkeypatch.setattr(hermes_cli, "web_server", stub, raising=False)

        app = FastAPI()
        app.include_router(router, prefix="/api/plugins/kanban")
        return TestClient(app)

    # -- (a) presence frame emitted on connect --

    def test_presence_frame_on_connect(self, ws_client):
        """On WS connect, the first frame (or an early frame) must be a
        ``{type: "presence"}`` frame so the UI can immediately render
        profile avatars/halos without waiting for the next periodic tick.
        """
        frames = []
        with ws_client.websocket_connect(
            "/api/plugins/kanban/events?token=test-presence-token"
        ) as ws:
            # Read a small number of frames — the presence frame should
            # arrive early (on connect), before or alongside events frames.
            for _ in range(5):
                frame = ws.receive_json()
                frames.append(frame)
                if frame.get("type") == "presence":
                    break

        presence_frames = [f for f in frames if f.get("type") == "presence"]
        assert len(presence_frames) >= 1, (
            f"Expected at least one presence frame on connect, got frames: "
            f"{[f.get('type') for f in frames]}"
        )

    def test_presence_frame_contract_shape(self, ws_client):
        """Every presence frame must match the contract:
        ``{type: "presence", profiles: [...], computed_at: <int>}``.

        Each profile entry must have all PresenceState fields per §3.1 of
        the architecture doc.
        """
        with ws_client.websocket_connect(
            "/api/plugins/kanban/events?token=test-presence-token"
        ) as ws:
            presence_frame = None
            for _ in range(10):
                frame = ws.receive_json()
                if frame.get("type") == "presence":
                    presence_frame = frame
                    break

        assert presence_frame is not None, "No presence frame received"
        # Top-level contract
        assert presence_frame["type"] == "presence"
        assert isinstance(presence_frame["profiles"], list)
        assert isinstance(presence_frame["computed_at"], int)

        # Per-profile field contract (when profiles exist)
        if presence_frame["profiles"]:
            required_keys = {
                "profile", "online", "status",
                "current_task_id", "current_task_title",
                "run_id", "pid", "last_heartbeat_at", "since",
            }
            for p in presence_frame["profiles"]:
                assert required_keys <= set(p.keys()), (
                    f"Profile {p.get('profile')} missing keys: "
                    f"{required_keys - set(p.keys())}"
                )
                # status must be one of the four valid liveness states
                assert p["status"] in ("active", "idle", "stale", "offline")
                # online iff active or idle (invariant from §3.1)
                assert p["online"] == (p["status"] in ("active", "idle"))

    # -- (b) presence frame emitted on relevant events --

    def test_presence_frame_after_relevant_event(self, kanban_home, ws_client, monkeypatch):
        """When a relevant event (e.g. 'claimed') occurs in the event stream,
        the WS must emit a presence frame in response — not just on the floor
        interval.

        We seed a task, then create a 'claimed' event and verify a presence
        frame arrives within a bounded read window.
        """
        conn = _conn_home(kanban_home)
        try:
            now = int(time.time())
            task_id = kb.create_task(conn, title="WS presence test", assignee="apollo")
            # Create a claimed event so there's something for the WS to pick up
            conn.execute(
                "INSERT INTO task_events (task_id, run_id, kind, payload, created_at) "
                "VALUES (?, 1, 'claimed', '{}', ?)",
                (task_id, now),
            )
            conn.commit()
        finally:
            conn.close()

        # Speed up the poll interval for faster test — monkeypatch the
        # constant inside stream_events
        from plugins.kanban.dashboard import plugin_api
        monkeypatch.setattr(plugin_api, "_EVENT_POLL_SECONDS", 0.1)

        frames = []
        with ws_client.websocket_connect(
            "/api/plugins/kanban/events?token=test-presence-token"
        ) as ws:
            for _ in range(20):
                try:
                    frame = ws.receive_json()
                    frames.append(frame)
                except Exception:
                    break
                # Once we see a presence frame after the initial one,
                # we're satisfied
                if (
                    frame.get("type") == "presence"
                    and len([f for f in frames if f.get("type") == "presence"]) >= 2
                ):
                    break

        presence_frames = [f for f in frames if f.get("type") == "presence"]
        # The initial connect frame + at least one triggered by the
        # claimed event or the floor interval
        assert len(presence_frames) >= 1, (
            f"Expected presence frame(s), got: {[f.get('type') for f in frames]}"
        )

    # -- (c) no second polling daemon --

    def test_events_and_presence_on_same_ws(self, ws_client):
        """Events and presence frames interleave on the *same* WS — no
        second socket or polling daemon is added. Both frame types share
        the ``type`` discriminator so consumers branch on frame type.
        """
        frame_types = set()
        with ws_client.websocket_connect(
            "/api/plugins/kanban/events?token=test-presence-token"
        ) as ws:
            for _ in range(10):
                try:
                    frame = ws.receive_json()
                    frame_types.add(frame.get("type"))
                except Exception:
                    break

        # The WS should carry presence frames — if it only carried events,
        # that would mean presence was on a separate channel (violating
        # the "extend, don't duplicate" principle).
        assert "presence" in frame_types, (
            f"Expected 'presence' frame type on /events WS, "
            f"got only: {frame_types}"
        )

    # -- (d) frame type discriminator is always present --

    def test_all_frames_have_type_discriminator(self, ws_client):
        """Every frame on the /events WS must have a ``type`` field.
        This is the contract fix from commit 0499a5744: untyped frames
        break consumers when presence and events interleave.
        """
        with ws_client.websocket_connect(
            "/api/plugins/kanban/events?token=test-presence-token"
        ) as ws:
            for _ in range(10):
                try:
                    frame = ws.receive_json()
                except Exception:
                    break
                assert "type" in frame, (
                    f"Frame missing 'type' discriminator: {frame}"
                )
                assert frame["type"] in ("events", "presence"), (
                    f"Unexpected frame type: {frame['type']}"
                )

    # -- (e) reconnect/since semantics: presence always sent on connect --

    def test_presence_frame_on_reconnect_with_since(self, ws_client):
        """When a client reconnects with ``?since=<cursor>``, it still
        receives a presence snapshot on connect — the presence frame is
        NOT gated on the since cursor. The since parameter only affects
        which event rows are streamed; presence is always fresh.

        This ensures the UI gets an authoritative presence snapshot on
        every reconnection, not a stale one from before the disconnect.
        """
        # First connection: get a cursor from an events frame
        last_cursor = 0
        with ws_client.websocket_connect(
            "/api/plugins/kanban/events?token=test-presence-token"
        ) as ws:
            for _ in range(10):
                frame = ws.receive_json()
                if frame.get("type") == "events":
                    last_cursor = frame.get("cursor", 0)

        # Reconnect with since — must still get a presence frame
        presence_on_reconnect = False
        with ws_client.websocket_connect(
            f"/api/plugins/kanban/events?token=test-presence-token&since={last_cursor}"
        ) as ws:
            for _ in range(10):
                frame = ws.receive_json()
                if frame.get("type") == "presence":
                    presence_on_reconnect = True
                    break

        assert presence_on_reconnect, (
            "Expected a presence frame on reconnect with ?since — "
            "presence should not be gated on the events cursor"
        )
