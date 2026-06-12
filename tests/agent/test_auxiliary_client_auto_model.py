"""Tests for auxiliary auto provider using the live runtime model instead of
stale config when the caller does not explicitly pass a model.

Regression test for #44746.
"""

from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

from agent.auxiliary_client import resolve_provider_client


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in (
        "OPENROUTER_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)
    import agent.auxiliary_client as _aux_mod
    _aux_mod._aux_unhealthy_until.clear()
    _aux_mod._aux_unhealthy_logged_at.clear()
    yield
    _aux_mod._aux_unhealthy_until.clear()
    _aux_mod._aux_unhealthy_logged_at.clear()


class TestAutoDoesNotUseStaleModel:
    """provider=auto should use the model returned by _resolve_auto, not a
    stale value from _read_main_model, when the caller passes no model."""

    def test_auto_uses_runtime_model_not_config_model(self):
        fake_client = MagicMock()
        fake_client.base_url = "https://api.z.ai/v1"

        with (
            patch(
                "agent.auxiliary_client._resolve_auto",
                return_value=(fake_client, "glm-5.1"),
            ),
            patch(
                "agent.auxiliary_client._read_main_model",
                return_value="gpt-5.5",
            ),
            patch(
                "agent.auxiliary_client._get_aux_model_for_provider",
                return_value="",
            ),
            patch(
                "agent.auxiliary_client._validate_proxy_env_urls",
            ),
        ):
            client, model = resolve_provider_client(
                "auto",
                model=None,
                main_runtime={
                    "provider": "zai",
                    "model": "glm-5.1",
                    "base_url": "https://api.z.ai/v1",
                },
            )

        assert client is fake_client
        assert model == "glm-5.1", (
            f"Expected auto-resolved model 'glm-5.1', got stale '{model}'"
        )

    def test_explicit_model_overrides_auto_resolved(self):
        fake_client = MagicMock()
        fake_client.base_url = "https://api.z.ai/v1"

        with (
            patch(
                "agent.auxiliary_client._resolve_auto",
                return_value=(fake_client, "glm-5.1"),
            ),
            patch(
                "agent.auxiliary_client._validate_proxy_env_urls",
            ),
        ):
            client, model = resolve_provider_client(
                "auto",
                model="custom-model-override",
                main_runtime={
                    "provider": "zai",
                    "model": "glm-5.1",
                    "base_url": "https://api.z.ai/v1",
                },
            )

        assert client is fake_client
        assert model == "custom-model-override", (
            f"Expected explicit model override, got '{model}'"
        )
