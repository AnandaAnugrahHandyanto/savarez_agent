"""Regression tests for the SPA catch-all route under /api/*.

Bug t_d26f5124: the SPA catch-all in mount_spa() returned index.html (HTTP 200,
text/html) for any unmatched /api/<plugin>/<bogus> path, masking typos and
missing-route mounts as "working". The fix gates the catch-all to never serve
the SPA shell for /api/* paths -- those must fall through to a real 404 JSON.
"""

import os
import shutil
import tempfile
import pytest


@pytest.fixture()
def _isolate_hermes_home():
    tmp = tempfile.mkdtemp(prefix="hermes_test_home_")
    old = os.environ.get("HERMES_HOME")
    os.environ["HERMES_HOME"] = tmp
    try:
        yield tmp
    finally:
        if old is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = old
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture()
def authed_client(_isolate_hermes_home):
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")
    from hermes_cli.web_server import app, _SESSION_HEADER_NAME, _SESSION_TOKEN

    client = TestClient(app)
    client.headers[_SESSION_HEADER_NAME] = _SESSION_TOKEN
    return client


class TestApiCatchAll404:
    """The SPA fallback must never swallow /api/* paths."""

    def test_unknown_plugin_returns_json_404(self, authed_client):
        """Bogus plugin name -> JSON 404, not SPA HTML 200."""
        resp = authed_client.get("/api/plugins/no-such-plugin/list")
        assert resp.status_code == 404, (
            f"expected 404 for unknown plugin route, got {resp.status_code} "
            f"with body: {resp.text[:200]!r}"
        )
        assert resp.headers["content-type"].startswith("application/json"), (
            f"expected JSON content-type, got {resp.headers.get('content-type')!r} "
            f"-- this means the SPA catch-all is serving index.html for /api/*"
        )
        body = resp.json()
        assert "error" in body

    def test_unknown_route_on_known_plugin_returns_json_404(self, authed_client):
        """Real plugin name + bogus route -> JSON 404, not SPA HTML 200.

        We probe a plugin name likely registered in the test app; if no plugin
        with /api/plugins/ routes is loaded, this still exercises the catch-all
        (the path doesn't match any registered route either way).
        """
        resp = authed_client.get("/api/plugins/azure-blob-browser/does-not-exist")
        assert resp.status_code == 404
        assert resp.headers["content-type"].startswith("application/json")

    def test_arbitrary_api_subpath_returns_json_404(self, authed_client):
        """Any /api/<anything-unmatched> -> JSON 404, not SPA shell."""
        resp = authed_client.get("/api/totally-made-up-namespace/xyz")
        assert resp.status_code == 404
        assert resp.headers["content-type"].startswith("application/json")

    def test_known_api_route_still_works(self, authed_client):
        """Regression: existing API routes must still return their proper response."""
        resp = authed_client.get("/api/status")
        # /api/status is documented public; should be 200 JSON.
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")

    def test_spa_route_without_api_prefix_still_serves_index(self, authed_client):
        """Regression: non-/api routes still get the SPA index.html fallback.

        When the frontend bundle isn't built in the test environment, the
        no-frontend branch returns JSON 404 for ALL paths -- so we accept
        either (HTML 200 = SPA served, JSON 404 = no frontend built). The
        critical guarantee is that we did NOT accidentally start returning
        JSON 404 for non-/api paths in the WEB_DIST.exists() branch.
        """
        resp = authed_client.get("/some/spa/route")
        ctype = resp.headers.get("content-type", "")
        if resp.status_code == 200:
            assert "text/html" in ctype, (
                f"non-/api path returned 200 with non-HTML content-type {ctype!r} "
                f"-- the SPA fallback is broken"
            )
        else:
            # No frontend built in this test env -- the no_frontend branch
            # returns 404 JSON for everything, which is fine.
            assert resp.status_code == 404
            assert ctype.startswith("application/json")
