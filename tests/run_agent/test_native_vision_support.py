"""Tests for native vision passthrough in AIAgent."""
import pytest

from run_agent import AIAgent


def _install_fake_openai(monkeypatch):
    """Stub out OpenAI client and auxiliary dependencies for unit tests."""
    import run_agent as _ra
    from agent import auxiliary_client as _aux

    _DummyClient = type(
        "_DummyClient", (), {"api_key": "***", "base_url": "http://localhost", "_default_headers": None}
    )
    monkeypatch.setattr(
        _aux, "resolve_provider_client", lambda *a, **kw: (_DummyClient(), None)
    )
    monkeypatch.setattr(_ra, "get_tool_definitions", lambda **kw: [])
    monkeypatch.setattr(AIAgent, "_build_system_prompt", lambda self, *a, **kw: "sys")
    monkeypatch.setattr(AIAgent, "_save_trajectory", lambda self, *a, **kw: None)

    _FakeChoice = type(
        "_FakeChoice",
        (),
        {
            "message": type(
                "_Msg", (), {"content": "ok", "tool_calls": None, "reasoning_content": None}
            )(),
            "finish_reason": "stop",
        },
    )
    _FakeResp = type("_FakeResp", (), {"choices": [_FakeChoice()], "usage": None})
    _FakeCompletions = type("_FakeCompletions", (), {"create": lambda *a, **kw: _FakeResp()})
    _FakeOpenAI = type(
        "_FakeOpenAI",
        (),
        {
            "__init__": lambda self, **kw: None,
            "chat": property(
                lambda self: type("_Chat", (), {"completions": _FakeCompletions()})
            ),
        },
    )
    monkeypatch.setattr(_ra, "OpenAI", _FakeOpenAI)


class TestCheckNativeVisionSupport:
    """RED-GREEN for _check_native_vision_support."""

    def test_kimi_for_coding_supports_vision(self, monkeypatch):
        monkeypatch.setattr(AIAgent, "_load_user_vision_native_models", staticmethod(lambda: []))
        monkeypatch.setattr(
            AIAgent, "_fetch_openrouter_vision_support", staticmethod(lambda m: None)
        )
        assert AIAgent._check_native_vision_support(
            "kimi-customize/kimi-for-coding", "kimi-customize", "chat_completions"
        ) is True

    def test_gpt4o_supports_vision(self, monkeypatch):
        monkeypatch.setattr(AIAgent, "_load_user_vision_native_models", staticmethod(lambda: []))
        monkeypatch.setattr(
            AIAgent, "_fetch_openrouter_vision_support", staticmethod(lambda m: None)
        )
        assert AIAgent._check_native_vision_support(
            "gpt-4o", "openai", "chat_completions"
        ) is True

    def test_claude3_supports_vision(self, monkeypatch):
        monkeypatch.setattr(AIAgent, "_load_user_vision_native_models", staticmethod(lambda: []))
        monkeypatch.setattr(
            AIAgent, "_fetch_openrouter_vision_support", staticmethod(lambda m: None)
        )
        assert AIAgent._check_native_vision_support(
            "claude-3-5-sonnet", "anthropic", "chat_completions"
        ) is True

    def test_anthropic_messages_mode_rejected(self):
        """Anthropic messages API needs special image blocks; reject for now."""
        assert AIAgent._check_native_vision_support(
            "claude-3-opus", "anthropic", "anthropic_messages"
        ) is False

    def test_unknown_model_rejected(self, monkeypatch):
        monkeypatch.setattr(AIAgent, "_load_user_vision_native_models", staticmethod(lambda: []))
        monkeypatch.setattr(
            AIAgent, "_fetch_openrouter_vision_support", staticmethod(lambda m: None)
        )
        assert AIAgent._check_native_vision_support(
            "some-random-model", "custom", "chat_completions"
        ) is False

    def test_env_override_true(self, monkeypatch):
        monkeypatch.setenv("VISION_NATIVE_PASSTHROUGH", "true")
        assert AIAgent._check_native_vision_support(
            "anything", "any", "anthropic_messages"
        ) is True

    def test_env_override_false(self, monkeypatch):
        monkeypatch.setenv("VISION_NATIVE_PASSTHROUGH", "false")
        assert AIAgent._check_native_vision_support(
            "gpt-4o", "openai", "chat_completions"
        ) is False

    def test_user_config_override_vision(self, monkeypatch):
        """User-configured agent.vision_native_models should take precedence over auto-detection."""
        monkeypatch.setattr(
            AIAgent, "_load_user_vision_native_models", staticmethod(lambda: ["my-custom-model"])
        )
        monkeypatch.setattr(
            AIAgent, "_fetch_openrouter_vision_support", staticmethod(lambda m: False)
        )
        assert AIAgent._check_native_vision_support(
            "prefix-my-custom-model-suffix", "custom", "chat_completions"
        ) is True

    def test_user_config_override_no_vision(self, monkeypatch):
        """If user config does not match, fall through to automatic detection."""
        monkeypatch.setattr(AIAgent, "_load_user_vision_native_models", staticmethod(lambda: []))
        monkeypatch.setattr(
            AIAgent, "_fetch_openrouter_vision_support", staticmethod(lambda m: True)
        )
        assert AIAgent._check_native_vision_support(
            "anthropic/claude-opus-4", "openrouter", "chat_completions"
        ) is True

    def test_openrouter_api_vision_detected(self, monkeypatch):
        """OpenRouter official API takes precedence for openrouter models."""
        monkeypatch.setattr(AIAgent, "_load_user_vision_native_models", staticmethod(lambda: []))
        monkeypatch.setattr(
            AIAgent, "_fetch_openrouter_vision_support", staticmethod(lambda m: True)
        )
        assert AIAgent._check_native_vision_support(
            "anthropic/claude-opus-4", "openrouter", "chat_completions"
        ) is True

    def test_openrouter_api_no_vision(self, monkeypatch):
        monkeypatch.setattr(AIAgent, "_load_user_vision_native_models", staticmethod(lambda: []))
        monkeypatch.setattr(
            AIAgent, "_fetch_openrouter_vision_support", staticmethod(lambda m: False)
        )
        # Even if it matches a whitelist vision model, OpenRouter API should win
        assert AIAgent._check_native_vision_support(
            "anthropic/claude-opus-4", "openrouter", "chat_completions"
        ) is False

    def test_models_dev_vision_detected(self, monkeypatch):
        """models.dev registry is consulted for non-openrouter providers."""
        monkeypatch.setattr(AIAgent, "_load_user_vision_native_models", staticmethod(lambda: []))
        monkeypatch.setattr(
            AIAgent, "_fetch_openrouter_vision_support", staticmethod(lambda m: None)
        )

        class _FakeCaps:
            supports_vision = True

        monkeypatch.setattr(
            "agent.models_dev.get_model_capabilities", lambda p, m: _FakeCaps()
        )
        assert AIAgent._check_native_vision_support(
            "custom-vision-model", "custom", "chat_completions"
        ) is True

    def test_models_dev_no_vision(self, monkeypatch):
        monkeypatch.setattr(AIAgent, "_load_user_vision_native_models", staticmethod(lambda: []))
        monkeypatch.setattr(
            AIAgent, "_fetch_openrouter_vision_support", staticmethod(lambda m: None)
        )

        class _FakeCaps:
            supports_vision = False

        monkeypatch.setattr(
            "agent.models_dev.get_model_capabilities", lambda p, m: _FakeCaps()
        )
        # Even if model name contains 'gpt-4', models.dev should win over whitelist
        assert AIAgent._check_native_vision_support(
            "custom-gpt-4-clone", "custom", "chat_completions"
        ) is False


class TestRunConversationWithUserMessageContent:
    """RED-GREEN for user_message_content passthrough and persistence."""

    def test_user_message_content_replaces_plain_text_in_api_messages(self, monkeypatch):
        """When user_message_content is provided, the API call should use it."""
        _install_fake_openai(monkeypatch)
        monkeypatch.setattr(AIAgent, "_persist_session", lambda self, *a, **kw: None)

        agent = AIAgent(model="gpt-4o", provider="openai")
        content_parts = [
            {"type": "text", "text": "hello"},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,abc"}},
        ]
        result = agent.run_conversation(
            user_message="hello",
            user_message_content=content_parts,
        )
        assert result["final_response"] == "ok"
        user_msgs = [m for m in result["messages"] if m.get("role") == "user"]
        assert user_msgs[-1]["content"] == content_parts

    def test_persist_user_message_override_stores_plain_text(self, monkeypatch):
        """Transcript/history should get plain text, not base64 payload."""
        _install_fake_openai(monkeypatch)
        persisted = []

        def fake_persist(self, messages, history=None):
            AIAgent._apply_persist_user_message_override(self, messages)
            persisted.extend(messages)

        monkeypatch.setattr(AIAgent, "_persist_session", fake_persist)

        agent = AIAgent(model="gpt-4o", provider="openai")
        content_parts = [
            {"type": "text", "text": "look at this"},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,abc"}},
        ]
        agent.run_conversation(
            user_message="look at this",
            user_message_content=content_parts,
        )

        user_msgs = [m for m in persisted if m.get("role") == "user"]
        assert user_msgs
        assert user_msgs[-1]["content"] == "look at this"
