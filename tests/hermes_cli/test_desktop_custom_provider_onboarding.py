"""Regression tests for desktop custom provider onboarding endpoints."""

import pytest


pytest.importorskip("fastapi")
pytest.importorskip("starlette")


def _client():
    from starlette.testclient import TestClient
    from hermes_cli.web_server import app, _SESSION_HEADER_NAME, _SESSION_TOKEN

    client = TestClient(app)
    client.headers[_SESSION_HEADER_NAME] = _SESSION_TOKEN
    return client


def test_custom_provider_models_probes_openai_compatible_endpoint(monkeypatch, _isolate_hermes_home):
    from hermes_cli import models as models_mod

    calls = []

    def fake_probe(api_key, base_url, timeout=10.0):
        calls.append((api_key, base_url, timeout))
        return {
            "models": ["model-a", "model-b"],
            "probed_url": "https://llm.example.com/v1/models",
            "resolved_base_url": "https://llm.example.com/v1",
            "suggested_base_url": None,
            "used_fallback": False,
        }

    monkeypatch.setattr(models_mod, "probe_api_models", fake_probe)

    response = _client().post(
        "/api/providers/custom/models",
        json={"base_url": "https://llm.example.com/v1/", "api_key": "sk-test"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "models": ["model-a", "model-b"],
        "probed_url": "https://llm.example.com/v1/models",
        "resolved_base_url": "https://llm.example.com/v1",
        "suggested_base_url": None,
        "used_fallback": False,
        "message": "",
    }
    assert calls == [("sk-test", "https://llm.example.com/v1", 10.0)]


def test_custom_provider_save_persists_named_provider_and_model(_isolate_hermes_home):
    import yaml
    from hermes_constants import get_hermes_home

    response = _client().post(
        "/api/providers/custom",
        json={
            "name": "My LLM",
            "base_url": "https://llm.example.com/v1/",
            "api_key": "sk-test",
            "model": "model-a",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["name"] == "My LLM"
    assert payload["slug"] == "custom:my-llm"
    assert payload["base_url"] == "https://llm.example.com/v1"
    assert payload["model"] == "model-a"

    config = yaml.safe_load((get_hermes_home() / "config.yaml").read_text())
    assert config["custom_providers"] == [
        {
            "name": "My LLM",
            "base_url": "https://llm.example.com/v1",
            "api_key": "sk-test",
            "model": "model-a",
        }
    ]
