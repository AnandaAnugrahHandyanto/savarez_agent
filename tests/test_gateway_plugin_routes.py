"""Gateway: ``/api/*`` must return JSON 404, NOT SPA index.html shell.

Regression test for t_af4699af. Before the fix, the SPA catch-all
(``mount_spa``) served ``index.html`` with HTTP 200 + ``text/html`` for any
unmatched path including unknown ``/api/plugins/<name>/...`` routes. That
silently masked missing/unmounted plugin routes as success and broke every
downstream consumer that did ``res.json()`` after a 2xx check.

The contract this file enforces:

1. ``/api/plugins/<known>/<unmounted>`` -> 404 application/json with
   ``{"error": "no such plugin route"}``.
2. ``/api/plugins/<unknown>/...``        -> 404 application/json with
   ``{"error": "unknown plugin"}``.
3. ``/api/<anything-else-unmatched>``    -> 404 application/json with
   ``{"error": "no such api route"}``.
4. The SPA catch-all still serves the frontend for non-``/api`` paths
   (regression guard: the fix must not break the SPA).
"""

from __future__ import annotations

import pytest


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Authenticated TestClient against the live FastAPI app."""
    try:
        from starlette.testclient import TestClient
    except ImportError:  # pragma: no cover
        pytest.skip("fastapi/starlette not installed")

    # Isolate hermes_home so test runs don't poison the user's real state.db.
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    from hermes_cli.web_server import (
        _SESSION_HEADER_NAME,
        _SESSION_TOKEN,
        app,
    )

    c = TestClient(app)
    c.headers[_SESSION_HEADER_NAME] = _SESSION_TOKEN
    return c


@pytest.fixture
def known_plugin_name(monkeypatch):
    """Force ``_get_dashboard_plugins`` to return at least one known plugin
    so tests don't depend on which plugins are installed on the dev box.
    """
    from hermes_cli import web_server

    fake = [
        {"name": "test-known-plugin", "_dir": "/tmp/fake", "_api_file": None},
    ]
    monkeypatch.setattr(web_server, "_get_dashboard_plugins", lambda *a, **k: fake)
    return "test-known-plugin"


# ---------------------------------------------------------------------------
# AC 1: known plugin, no mounted route -> 404 JSON with "no such plugin route"
# ---------------------------------------------------------------------------


def test_known_plugin_unmounted_route_returns_404_json(client, known_plugin_name):
    resp = client.get(f"/api/plugins/{known_plugin_name}/definitely-not-a-real-route")
    assert resp.status_code == 404, (
        f"Expected 404 for known plugin + unmounted route, got "
        f"{resp.status_code} with body {resp.text[:200]!r}. "
        f"If this is HTTP 200 with HTML, the SPA catch-all is masking /api/* again."
    )
    assert resp.headers["content-type"].startswith("application/json"), (
        f"Expected application/json, got {resp.headers.get('content-type')!r}. "
        f"HTML response means the SPA catch-all served index.html instead of 404."
    )
    body = resp.json()
    assert body.get("error") == "no such plugin route", body
    assert body.get("plugin") == known_plugin_name, body


def test_known_plugin_unmounted_nested_path_returns_404_json(client, known_plugin_name):
    resp = client.get(f"/api/plugins/{known_plugin_name}/nested/deep/path")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert body["error"] == "no such plugin route"
    assert body["path"] == "nested/deep/path"


# ---------------------------------------------------------------------------
# AC 2: unknown plugin -> 404 JSON with "unknown plugin"
# ---------------------------------------------------------------------------


def test_unknown_plugin_returns_404_json(client, known_plugin_name):
    # known_plugin_name fixture pins the known-plugin set so this name is unknown.
    resp = client.get("/api/plugins/totally-bogus-plugin-name/list")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert body["error"] == "unknown plugin"
    assert body["plugin"] == "totally-bogus-plugin-name"


# ---------------------------------------------------------------------------
# AC 3: SPA catch-all match LAST — generic /api/* unmatched -> 404 JSON
# ---------------------------------------------------------------------------


def test_unknown_api_route_returns_404_json(client):
    resp = client.get("/api/this-is-not-a-real-endpoint")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert body["error"] == "no such api route"


def test_unknown_nested_api_route_returns_404_json(client):
    resp = client.get("/api/foo/bar/baz")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert body["error"] == "no such api route"
    assert body["path"] == "foo/bar/baz"


# ---------------------------------------------------------------------------
# Regression guard for AC 3: SPA still works for non-/api paths.
# ---------------------------------------------------------------------------


def test_spa_catchall_still_serves_frontend_for_non_api_paths(client):
    """The SPA catch-all must still match non-``/api`` paths.

    If WEB_DIST doesn't exist in the test env (frontend not built), the
    mount registers a ``no_frontend`` handler that returns JSON 404 instead.
    Either outcome proves the catch-all hasn't been swallowed by the /api
    fallback; only a route-not-found error from FastAPI would be a real
    regression.
    """
    resp = client.get("/some-spa-route")
    # Acceptable outcomes:
    #   - 200 text/html (frontend built, SPA serving index.html)
    #   - 404 application/json with "Frontend not built" (frontend not built)
    # NOT acceptable: 404 with FastAPI's default "Not Found" JSON shape (would
    # mean the SPA catch-all was clobbered).
    assert resp.status_code in (200, 404), resp.status_code
    if resp.status_code == 200:
        assert "html" in resp.headers["content-type"].lower()
    else:
        # Should be the no_frontend handler, not FastAPI's default 404.
        body = resp.json()
        assert "Frontend not built" in body.get("error", ""), body


# ---------------------------------------------------------------------------
# Method coverage: POST/PUT/DELETE/PATCH on unmounted plugin routes also 404 JSON
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["post", "put", "delete", "patch"])
def test_unmounted_plugin_route_non_get_returns_404_json(client, known_plugin_name, method):
    resp = getattr(client, method)(f"/api/plugins/{known_plugin_name}/nope")
    assert resp.status_code == 404, (
        f"{method.upper()} on unmounted plugin route returned {resp.status_code}; "
        "should be 404 JSON."
    )
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json()["error"] == "no such plugin route"


@pytest.mark.parametrize("method", ["post", "put", "delete", "patch"])
def test_unknown_api_route_non_get_returns_404_json(client, method):
    resp = getattr(client, method)("/api/no-such-thing")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json()["error"] == "no such api route"
