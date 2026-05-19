"""Tests for _camofox_headers() auth helper and HTTP helper integration."""

import os
import ast
import inspect
from unittest.mock import patch, MagicMock

import pytest

from tools.browser_camofox import (
    _camofox_headers,
    _post,
    _get,
    _get_raw,
    _delete,
)


# ---------------------------------------------------------------------------
# _camofox_headers() unit tests
# ---------------------------------------------------------------------------


def test_headers_returns_bearer_with_access_key(monkeypatch):
    monkeypatch.setenv("CAMOFOX_ACCESS_KEY", "test-access-key")
    monkeypatch.delenv("CAMOFOX_API_KEY", raising=False)
    assert _camofox_headers() == {"Authorization": "Bearer test-access-key"}


def test_headers_falls_back_to_api_key(monkeypatch):
    monkeypatch.delenv("CAMOFOX_ACCESS_KEY", raising=False)
    monkeypatch.setenv("CAMOFOX_API_KEY", "test-api-key")
    assert _camofox_headers() == {"Authorization": "Bearer test-api-key"}


def test_headers_access_key_takes_priority(monkeypatch):
    monkeypatch.setenv("CAMOFOX_ACCESS_KEY", "access")
    monkeypatch.setenv("CAMOFOX_API_KEY", "api")
    assert _camofox_headers() == {"Authorization": "Bearer access"}


def test_headers_returns_empty_when_no_env_vars(monkeypatch):
    monkeypatch.delenv("CAMOFOX_ACCESS_KEY", raising=False)
    monkeypatch.delenv("CAMOFOX_API_KEY", raising=False)
    assert _camofox_headers() == {}


def test_headers_strips_whitespace(monkeypatch):
    monkeypatch.setenv("CAMOFOX_ACCESS_KEY", "  padded-key  ")
    monkeypatch.delenv("CAMOFOX_API_KEY", raising=False)
    result = _camofox_headers()
    assert result == {"Authorization": "Bearer padded-key"}


def test_headers_ignores_empty_string_access_key(monkeypatch):
    monkeypatch.setenv("CAMOFOX_ACCESS_KEY", "")
    monkeypatch.setenv("CAMOFOX_API_KEY", "fallback-key")
    assert _camofox_headers() == {"Authorization": "Bearer fallback-key"}


# ---------------------------------------------------------------------------
# HTTP helpers forward the auth header
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_env(monkeypatch):
    monkeypatch.setenv("CAMOFOX_ACCESS_KEY", "testkey")
    monkeypatch.setenv("CAMOFOX_URL", "http://localhost:9377")


def test_helpers_send_auth_headers(auth_env):
    """All 4 HTTP helpers must forward _camofox_headers() to requests.*."""
    expected_headers = {"Authorization": "Bearer testkey"}

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {}

    with (
        patch(
            "tools.browser_camofox.requests.post", return_value=mock_response
        ) as mock_post,
        patch(
            "tools.browser_camofox.requests.get", return_value=mock_response
        ) as mock_get,
        patch(
            "tools.browser_camofox.requests.delete", return_value=mock_response
        ) as mock_delete,
    ):
        _post("/foo", {})
        _get("/bar")
        _get_raw("/baz")
        _delete("/qux", {})

        # Verify headers kwarg was passed in each call
        _, post_kwargs = mock_post.call_args
        assert post_kwargs.get("headers") == expected_headers, (
            f"_post headers mismatch: {post_kwargs}"
        )

        # _get is called twice (for _get and _get_raw)
        get_calls = mock_get.call_args_list
        assert len(get_calls) == 2
        for i, call in enumerate(get_calls):
            _, kwargs = call
            assert kwargs.get("headers") == expected_headers, (
                f"_get call {i} headers mismatch: {kwargs}"
            )

        _, del_kwargs = mock_delete.call_args
        assert del_kwargs.get("headers") == expected_headers, (
            f"_delete headers mismatch: {del_kwargs}"
        )


def test_health_check_does_not_use_helper():
    """check_camofox_available() must call requests.get directly, not via _get."""
    import tools.browser_camofox as mod

    src = inspect.getsource(mod.check_camofox_available)
    # Should call requests.get directly (not _get)
    assert "requests.get(" in src, (
        "check_camofox_available should call requests.get directly"
    )
    assert "_get(" not in src, (
        "check_camofox_available must NOT use the _get helper (health endpoint is unauthed)"
    )
