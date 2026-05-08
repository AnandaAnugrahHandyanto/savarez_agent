"""Tests for the protected AI Office dashboard API."""

import pytest

fastapi = pytest.importorskip("fastapi")
from starlette.testclient import TestClient


def test_office_state_requires_dashboard_session_token():
    from hermes_cli.web_server import app

    unauth_client = TestClient(app)

    resp = unauth_client.get("/api/office/state")

    assert resp.status_code == 401


def test_office_state_is_protected_builtin_route_and_returns_read_only_dto():
    from hermes_cli.web_server import app, _PUBLIC_API_PATHS, _SESSION_HEADER_NAME, _SESSION_TOKEN

    assert "/api/office/state" not in _PUBLIC_API_PATHS
    assert not "/api/office/state".startswith("/api/plugins/")

    client = TestClient(app)
    resp = client.get("/api/office/state", headers={_SESSION_HEADER_NAME: _SESSION_TOKEN})

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["schema_version"] == 1
    assert payload["mode"] == "read_only"
    assert payload["display_mode"] == "localhost"
    assert payload["capabilities"]["read_only"] is True
    assert payload["capabilities"]["mutations_enabled"] is False
    assert payload["capabilities"]["remote_mode"] == "unsupported"
    assert payload["redactions"]["policy_version"] == 1
    assert {source["status"] for source in payload["data_sources"]} == {"missing"}


def test_office_state_rejects_common_mutation_methods():
    from hermes_cli.web_server import app, _SESSION_HEADER_NAME, _SESSION_TOKEN

    client = TestClient(app)
    headers = {_SESSION_HEADER_NAME: _SESSION_TOKEN}

    for method in (client.post, client.put, client.patch, client.delete):
        resp = method("/api/office/state", headers=headers)
        assert resp.status_code in {404, 405}
