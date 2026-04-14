"""Tests for CloudBrowserProvider base class shared helpers."""

import os
import pytest
import requests
from unittest.mock import patch, MagicMock

from tools.browser_providers.base import CloudBrowserProvider


class FakeProvider(CloudBrowserProvider):
    """Concrete implementation for testing."""

    def provider_name(self):
        return "Fake"

    def is_configured(self):
        return True

    def create_session(self, task_id):
        return {"session_name": self.make_session_name(task_id)}

    def close_session(self, session_id):
        return True

    def emergency_cleanup(self, session_id):
        pass


# --- make_session_name ---

class TestMakeSessionName:
    def test_format(self):
        provider = FakeProvider()
        name = provider.make_session_name("task1")
        assert name.startswith("hermes_task1_")
        assert len(name.split("_")[-1]) == 8

    def test_unique(self):
        provider = FakeProvider()
        name1 = provider.make_session_name("t")
        name2 = provider.make_session_name("t")
        assert name1 != name2

    def test_includes_task_id(self):
        provider = FakeProvider()
        name = provider.make_session_name("my-task-42")
        assert "my-task-42" in name


# --- _close_session_template ---

class TestCloseSessionTemplate:
    def test_success_on_200(self):
        provider = FakeProvider()
        mock_response = MagicMock()
        mock_response.status_code = 200

        result = provider._close_session_template(
            "sid123",
            get_config=lambda: {"key": "val"},
            http_request_fn=lambda cfg: mock_response,
        )
        assert result is True

    def test_success_on_201(self):
        provider = FakeProvider()
        mock_response = MagicMock()
        mock_response.status_code = 201

        result = provider._close_session_template(
            "sid123",
            get_config=lambda: {"key": "val"},
            http_request_fn=lambda cfg: mock_response,
        )
        assert result is True

    def test_success_on_204(self):
        provider = FakeProvider()
        mock_response = MagicMock()
        mock_response.status_code = 204

        result = provider._close_session_template(
            "sid123",
            get_config=lambda: {"key": "val"},
            http_request_fn=lambda cfg: mock_response,
        )
        assert result is True

    def test_failure_on_404(self):
        provider = FakeProvider()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "not found"

        result = provider._close_session_template(
            "sid123",
            get_config=lambda: {"key": "val"},
            http_request_fn=lambda cfg: mock_response,
        )
        assert result is False

    def test_returns_false_on_missing_creds(self):
        provider = FakeProvider()

        def raise_no_creds():
            raise ValueError("missing")

        result = provider._close_session_template(
            "sid123",
            get_config=raise_no_creds,
            http_request_fn=lambda cfg: None,
        )
        assert result is False

    def test_returns_false_on_exception(self):
        provider = FakeProvider()

        def raise_error(cfg):
            raise ConnectionError("timeout")

        result = provider._close_session_template(
            "sid123",
            get_config=lambda: {"key": "val"},
            http_request_fn=raise_error,
        )
        assert result is False


# --- _emergency_cleanup_template ---

class TestEmergencyCleanupTemplate:
    def test_calls_request_when_configured(self):
        provider = FakeProvider()
        called = []

        def track_call(cfg):
            called.append(True)

        provider._emergency_cleanup_template(
            "sid123",
            get_config_or_none=lambda: {"key": "val"},
            http_request_fn=track_call,
        )
        assert called == [True]

    def test_skips_when_no_creds(self):
        provider = FakeProvider()
        called = []

        provider._emergency_cleanup_template(
            "sid123",
            get_config_or_none=lambda: None,
            http_request_fn=lambda cfg: called.append(True),
        )
        assert called == []

    def test_no_raise_on_exception(self):
        provider = FakeProvider()

        def raise_error(cfg):
            raise RuntimeError("boom")

        # Should not raise
        provider._emergency_cleanup_template(
            "sid123",
            get_config_or_none=lambda: {"key": "val"},
            http_request_fn=raise_error,
        )
