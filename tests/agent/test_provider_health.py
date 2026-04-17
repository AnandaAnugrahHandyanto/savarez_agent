"""Tests for agent.provider_health local probes."""

from unittest.mock import MagicMock

import pytest

import agent.provider_health as ph


@pytest.fixture
def fake_client_factory():
    """Return a factory: ``make(responses)`` patches httpx.Client to return those status codes per URL path order."""

    def make(path_to_status: dict[str, int]):
        class _Ctx:
            def get(self, url: str):
                from urllib.parse import urlparse

                path = urlparse(url).path or "/"
                code = path_to_status.get(path, 404)
                r = MagicMock()
                r.status_code = code
                return r

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        class _Client:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return _Ctx()

            def __exit__(self, *a):
                return False

        return _Client

    return make


def test_probe_healthz_success(monkeypatch, fake_client_factory):
    monkeypatch.setattr(ph.httpx, "Client", fake_client_factory({"/healthz": 200}))
    assert ph.probe_local_provider_health("http://127.0.0.1:11434/v1") == "/healthz"


def test_probe_fallback_v1_models(monkeypatch, fake_client_factory):
    monkeypatch.setattr(
        ph.httpx,
        "Client",
        fake_client_factory({"/healthz": 404, "/health": 404, "/v1/models": 200}),
    )
    assert ph.probe_local_provider_health("http://127.0.0.1:11434/v1") == "/v1/models"


def test_probe_all_fail(monkeypatch, fake_client_factory):
    monkeypatch.setattr(
        ph.httpx,
        "Client",
        fake_client_factory({"/healthz": 500, "/health": 503, "/v1/models": 500}),
    )
    assert ph.probe_local_provider_health("http://127.0.0.1:11434/v1") is None


def test_maybe_log_sets_flag(monkeypatch, fake_client_factory):
    monkeypatch.setattr(ph.httpx, "Client", fake_client_factory({"/healthz": 200}))
    agent = MagicMock()
    agent.base_url = "http://127.0.0.1:11434/v1"
    agent._model_yaml_cfg = {}
    agent._local_provider_health_probed = False
    ph.maybe_log_local_provider_health(agent)
    assert agent._local_provider_health_probed is True
    ph.maybe_log_local_provider_health(agent)  # second call no-op
