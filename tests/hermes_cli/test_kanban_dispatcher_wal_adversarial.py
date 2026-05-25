"""Adversarial verifier tests for kanban-gateway-per-thread-conn-cache.

These tests go beyond the implementer's happy-path coverage and probe:
1. conn.close() on a TLS-cached connection invalidates the cache entry
   (the cached connection becomes closed but the cache still holds it)
2. Multi-slug isolation: different slugs get different connections
3. Same slug from different threads gets different connections (not just None slug)
4. TLS cache is truly per-instance, not class-level
5. Connection state is correct after cache miss recovery

Bug probed: In _kanban_notifier_watcher and _tick_once_for_board, the finally
block calls conn.close() on a TLS-cached connection. This closes the connection
but leaves a stale closed-connection object in the TLS cache. The next call to
_kb_conn() from the same thread returns the already-closed connection instead
of opening a fresh one, causing OperationalError: "Cannot operate on a closed
database."
"""

import sqlite3
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch


def _make_minimal_gateway():
    from gateway.run import GatewayRunner

    with (
        patch("gateway.run.load_gateway_config") as mock_cfg,
        patch.object(GatewayRunner, "_warn_if_docker_media_delivery_is_risky"),
        patch.object(GatewayRunner, "_load_prefill_messages", return_value=[]),
        patch.object(GatewayRunner, "_load_ephemeral_system_prompt", return_value=None),
        patch.object(GatewayRunner, "_load_reasoning_config", return_value={}),
        patch.object(GatewayRunner, "_load_service_tier", return_value=None),
        patch.object(GatewayRunner, "_load_show_reasoning", return_value=False),
        patch.object(GatewayRunner, "_load_busy_input_mode", return_value="interrupt"),
        patch.object(GatewayRunner, "_load_busy_text_mode", return_value="interrupt"),
        patch.object(GatewayRunner, "_load_restart_drain_timeout", return_value=30.0),
        patch.object(GatewayRunner, "_load_provider_routing", return_value={}),
        patch.object(GatewayRunner, "_load_fallback_model", return_value=None),
        patch.object(GatewayRunner, "_load_voice_modes", return_value={}),
        patch.object(GatewayRunner, "_active_profile_name", return_value="test"),
        patch("gateway.run.SessionStore"),
        patch("gateway.run.DeliveryRouter"),
    ):
        cfg = MagicMock()
        cfg.sessions_dir = tempfile.mkdtemp()
        mock_cfg.return_value = cfg
        gw = GatewayRunner()
    return gw


def _make_test_db(tmpdir=None):
    import os
    from hermes_cli import kanban_db as _kb

    if tmpdir is None:
        tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "kanban.db"
    os.environ["HERMES_KANBAN_DB"] = str(db_path)
    conn = _kb.connect(board=None)
    conn.close()
    return db_path


# ---------------------------------------------------------------------------
# ADVERSARIAL TEST 1 — closing a TLS-cached connection corrupts the cache
# ---------------------------------------------------------------------------

def test_closing_tls_cached_connection_invalidates_cache():
    """Closing the returned connection must not leave a stale dead connection in the TLS cache.

    This probes the bug in _collect() and _tick_once_for_board where conn.close()
    is called inside a finally block on the result of self._kb_conn(slug).
    After close(), the cache still holds the now-closed connection object.
    A subsequent _kb_conn(slug) from the same thread returns that closed object
    and any query raises: "Cannot operate on a closed database."

    If the implementation correctly removes the stale entry after close() or
    opens a fresh connection, this test passes. If it doesn't, it fails with
    OperationalError.
    """
    gw = _make_minimal_gateway()
    _make_test_db()

    errors = []

    def worker():
        conn1 = gw._kb_conn(None)
        # Simulate what _collect() does: close the cached connection
        conn1.close()
        # Now call again — should get a WORKING connection, not the closed one
        conn2 = gw._kb_conn(None)
        try:
            conn2.execute("SELECT 1").fetchone()
        except sqlite3.ProgrammingError as e:
            errors.append(f"Got closed connection from cache after close(): {e}")
        except Exception as e:
            errors.append(f"Unexpected error: {e}")

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert not errors, "\n".join(errors)


# ---------------------------------------------------------------------------
# ADVERSARIAL TEST 2 — multi-slug isolation: distinct slugs, distinct connections
# ---------------------------------------------------------------------------

def test_different_slugs_get_different_connections_same_thread():
    """Within the same thread, different slugs must yield different connections."""
    import os
    from hermes_cli import kanban_db as _kb

    tmpdir = tempfile.mkdtemp()
    db1 = Path(tmpdir) / "kanban.db"
    db2 = Path(tmpdir) / "kanban2.db"

    os.environ["HERMES_KANBAN_DB"] = str(db1)
    c = _kb.connect(board=None); c.close()
    os.environ["HERMES_KANBAN_DB"] = str(db2)
    c = _kb.connect(board=None); c.close()
    # Reset to db1 as the default
    os.environ["HERMES_KANBAN_DB"] = str(db1)

    gw = _make_minimal_gateway()

    results = {}

    def worker():
        conn_default = gw._kb_conn(None)
        conn_slug = gw._kb_conn("second")
        results["default_id"] = id(conn_default)
        results["slug_id"] = id(conn_slug)

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert results["default_id"] != results["slug_id"], (
        "_kb_conn(None) and _kb_conn('second') must return different connections"
    )


# ---------------------------------------------------------------------------
# ADVERSARIAL TEST 3 — TLS cache is instance-level, not class-level
# ---------------------------------------------------------------------------

def test_tls_cache_is_per_instance_not_class_level():
    """Two GatewayRunner instances must not share TLS connection state."""
    _make_test_db()

    gw1 = _make_minimal_gateway()
    gw2 = _make_minimal_gateway()

    results = {}

    def worker(gw, key):
        results[key] = id(gw._kb_conn(None))

    t1 = threading.Thread(target=worker, args=(gw1, "gw1"))
    t2 = threading.Thread(target=worker, args=(gw2, "gw2"))
    t1.start(); t1.join()
    t2.start(); t2.join()

    # Different instances must yield different connection objects
    # (They might happen to be different slugs too, but the test is that
    #  gw1's cache and gw2's cache are separate.)
    assert results["gw1"] != results["gw2"], (
        "Two GatewayRunner instances must use separate TLS caches"
    )


# ---------------------------------------------------------------------------
# ADVERSARIAL TEST 4 — slug=None and slug="default" consistency
# ---------------------------------------------------------------------------

def test_slug_none_and_slug_default_consistency():
    """_kb_conn(None) and _kb_conn('default') must return the SAME cached connection.

    The implementation normalises slug to 'default' when None is passed, so
    these two calls from the same thread should hit the same cache bucket.
    """
    _make_test_db()
    gw = _make_minimal_gateway()

    results = {}

    def worker():
        results["none"] = id(gw._kb_conn(None))
        results["default"] = id(gw._kb_conn("default"))

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert results["none"] == results["default"], (
        "_kb_conn(None) and _kb_conn('default') must return the same cached connection"
    )


# ---------------------------------------------------------------------------
# ADVERSARIAL TEST 5 — concurrent slug creation (no cache races)
# ---------------------------------------------------------------------------

def test_concurrent_new_slug_creation_no_races():
    """N threads each calling _kb_conn for the FIRST time must not corrupt the cache."""
    import os
    from hermes_cli import kanban_db as _kb

    tmpdir = tempfile.mkdtemp()
    os.environ["HERMES_KANBAN_DB"] = str(Path(tmpdir) / "kanban.db")
    c = _kb.connect(board=None); c.close()

    gw = _make_minimal_gateway()
    errors = []
    N = 8

    def worker(tid):
        try:
            conn = gw._kb_conn(None)
            # Must be usable
            conn.execute("SELECT 1").fetchone()
        except Exception as e:
            errors.append(f"Thread {tid}: {e}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Errors in concurrent first-access: {errors}"
