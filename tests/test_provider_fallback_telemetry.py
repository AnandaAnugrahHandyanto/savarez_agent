from __future__ import annotations

from types import SimpleNamespace

from agent.error_classifier import FailoverReason
from agent import chat_completion_helpers as helpers
from agent.provider_telemetry import sanitize_event


class DummyAgent:
    def __init__(self) -> None:
        self._fallback_index = 0
        self._fallback_chain = [{"provider": "custom", "model": "fallback-model", "base_url": "https://fallback.example/v1"}]
        self._fallback_activated = False
        self._primary_runtime = {"provider": "primary-provider"}
        self.provider = "primary-provider"
        self.model = "primary-model"
        self.base_url = "https://primary.example/v1"
        self.platform = "cli"
        self.session_id = "session-1"
        self._config_context_length = None
        self.client = None
        self.api_key = ""
        self._client_kwargs = {}

    def _try_activate_fallback(self, reason=None):  # pragma: no cover - recursion guard
        return helpers.try_activate_fallback(self, reason)

    def _is_azure_openai_url(self, base_url: str) -> bool:
        return False

    def _is_direct_openai_url(self, base_url: str) -> bool:
        return False

    def _provider_model_requires_responses_api(self, model: str, provider: str | None = None) -> bool:
        return False

    def _anthropic_prompt_cache_policy(self, **kwargs):
        return False, False

    def _ensure_lmstudio_runtime_loaded(self) -> None:
        return None

    def _emit_status(self, message: str) -> None:
        self.last_status = message


def _patch_common(monkeypatch, events):
    monkeypatch.setattr(helpers, "_append_provider_telemetry", lambda event: events.append(sanitize_event(event)))
    monkeypatch.setattr(helpers, "get_provider_request_timeout", lambda provider, model: None)


def test_try_activate_fallback_emits_provider_telemetry(monkeypatch) -> None:
    events = []
    agent = DummyAgent()
    _patch_common(monkeypatch, events)

    import agent.auxiliary_client as auxiliary_client

    monkeypatch.setattr(
        auxiliary_client,
        "resolve_provider_client",
        lambda *args, **kwargs: (SimpleNamespace(base_url="https://fallback.example/v1", api_key="key"), "fallback-model"),
    )

    assert helpers.try_activate_fallback(agent, FailoverReason.rate_limit) is True

    assert agent.provider == "custom"
    assert agent.model == "fallback-model"
    assert len(events) == 1
    event = events[0]
    assert event["event"] == "fallback_activated"
    assert event["status"] == "fallback_activated"
    assert event["failure_kind"] == "rate_limit"
    assert event["provider"] == "primary-provider"
    assert event["model"] == "primary-model"
    assert event["fallback"]["provider"] == "custom"
    assert event["fallback"]["model"] == "fallback-model"


def test_try_activate_fallback_emits_failed_event_when_provider_unconfigured(monkeypatch) -> None:
    events = []
    agent = DummyAgent()
    _patch_common(monkeypatch, events)

    import agent.auxiliary_client as auxiliary_client

    monkeypatch.setattr(auxiliary_client, "resolve_provider_client", lambda *args, **kwargs: (None, None))

    assert helpers.try_activate_fallback(agent, FailoverReason.billing) is False
    assert len(events) == 1
    event = events[0]
    assert event["event"] == "fallback_activation_failed"
    assert event["status"] == "failed"
    assert event["failure_kind"] == "provider_error"
    assert event["fallback"] == {"provider": "custom", "model": "fallback-model"}


def test_try_activate_fallback_emits_failed_event_when_activation_raises(monkeypatch) -> None:
    events = []
    agent = DummyAgent()
    _patch_common(monkeypatch, events)

    import agent.auxiliary_client as auxiliary_client

    def boom(*args, **kwargs):
        raise RuntimeError("token=fake-token-value provider exploded")

    monkeypatch.setattr(auxiliary_client, "resolve_provider_client", boom)

    assert helpers.try_activate_fallback(agent, FailoverReason.rate_limit) is False
    assert len(events) == 1
    event = events[0]
    assert event["event"] == "fallback_activation_failed"
    assert event["status"] == "failed"
    assert event["fallback"] == {"provider": "custom", "model": "fallback-model"}
    assert event["notes"]
    assert "RuntimeError" in event["notes"]
    assert "[REDACTED]" in event["notes"]
    assert "fake-token-value" not in event["notes"]
