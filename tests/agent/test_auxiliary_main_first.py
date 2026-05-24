"""Regression tests for the ``auto`` → main-model-first policy.

Prior to this change, aggregator users (OpenRouter / Nous Portal) had aux
tasks routed through a cheap provider-side default (Gemini Flash) while
non-aggregator users got their main model.  This made behavior inconsistent
and surprising — users picked Claude but got Gemini Flash summaries.

The current policy: ``auto`` means "use my main chat model" for every user,
regardless of provider type.  Explicit per-task overrides in ``config.yaml``
(``auxiliary.<task>.provider``) still win.  The cheap fallback chain only
runs when the main provider has no working client.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ── Test isolation ───────────────────────────────────────────────────────────
#
# agent.auxiliary_client holds two module-level dicts:
#   _aux_unhealthy_until     — provider label → expiry timestamp
#   _aux_unhealthy_logged_at — provider label → last-log timestamp
#
# _mark_provider_unhealthy() is called whenever a provider lacks credentials
# (e.g. OPENROUTER_API_KEY absent causes a 60-second "openrouter" entry).
# Tests in other modules (notably test_vision_tools.py) remove env vars and
# invoke resolve_vision_provider_client(), which triggers _try_openrouter() and
# leaves "openrouter" in the cache.  _resolve_auto() then skips the patched
# main provider in Step-1, causing the TestResolveAutoMainFirst tests to see
# None instead of the mock client.
#
# Fix: autouse fixture clears both dicts before and after every test in this
# module so the health cache is always pristine regardless of run order.


@pytest.fixture(autouse=True)
def _reset_unhealthy_cache():
    """Clear the auxiliary-client unhealthy cache around every test."""
    import agent.auxiliary_client as _aux_mod

    _aux_mod._aux_unhealthy_until.clear()
    _aux_mod._aux_unhealthy_logged_at.clear()
    yield
    _aux_mod._aux_unhealthy_until.clear()
    _aux_mod._aux_unhealthy_logged_at.clear()


# ── Text aux tasks — _resolve_auto ──────────────────────────────────────────


class TestResolveAutoMainFirst:
    """_resolve_auto() must prefer main provider + main model for every user."""

    def test_openrouter_main_uses_main_model_for_aux(self, monkeypatch):
        """OpenRouter main user → aux uses their picked OR model, not Gemini Flash."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-test-key")

        with patch(
            "agent.auxiliary_client._read_main_provider",
            return_value="openrouter",
        ), patch(
            "agent.auxiliary_client._read_main_model",
            return_value="anthropic/claude-sonnet-4.6",
        ), patch(
            "agent.auxiliary_client.resolve_provider_client"
        ) as mock_resolve:
            mock_client = MagicMock()
            mock_resolve.return_value = (mock_client, "anthropic/claude-sonnet-4.6")

            from agent.auxiliary_client import _resolve_auto

            client, model = _resolve_auto()

        assert client is mock_client
        assert model == "anthropic/claude-sonnet-4.6"
        # Verify it asked resolve_provider_client for the MAIN provider+model,
        # not a fallback-chain provider
        mock_resolve.assert_called_once()
        assert mock_resolve.call_args.args[0] == "openrouter"
        assert mock_resolve.call_args.args[1] == "anthropic/claude-sonnet-4.6"

    def test_nous_main_uses_main_model_for_aux(self, monkeypatch):
        """Nous Portal main user → aux uses their picked Nous model, not free-tier MiMo."""
        # No OPENROUTER_API_KEY → ensures if main failed we'd fall to chain
        with patch(
            "agent.auxiliary_client._read_main_provider", return_value="nous",
        ), patch(
            "agent.auxiliary_client._read_main_model",
            return_value="anthropic/claude-opus-4.6",
        ), patch(
            "agent.auxiliary_client.resolve_provider_client"
        ) as mock_resolve:
            mock_client = MagicMock()
            mock_resolve.return_value = (mock_client, "anthropic/claude-opus-4.6")

            from agent.auxiliary_client import _resolve_auto

            client, model = _resolve_auto()

        assert client is mock_client
        assert model == "anthropic/claude-opus-4.6"
        assert mock_resolve.call_args.args[0] == "nous"

    def test_non_aggregator_main_still_uses_main(self, monkeypatch):
        """Non-aggregator main (DeepSeek) → unchanged behavior, main model used."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-test")

        with patch(
            "agent.auxiliary_client._read_main_provider", return_value="deepseek",
        ), patch(
            "agent.auxiliary_client._read_main_model", return_value="deepseek-chat",
        ), patch(
            "agent.auxiliary_client.resolve_provider_client"
        ) as mock_resolve:
            mock_client = MagicMock()
            mock_resolve.return_value = (mock_client, "deepseek-chat")

            from agent.auxiliary_client import _resolve_auto

            client, model = _resolve_auto()

        assert client is mock_client
        assert model == "deepseek-chat"
        assert mock_resolve.call_args.args[0] == "deepseek"

    def test_main_unavailable_falls_through_to_chain(self, monkeypatch):
        """Main provider with no working client → fall back to aux chain."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")

        chain_client = MagicMock()
        with patch(
            "agent.auxiliary_client._read_main_provider", return_value="anthropic",
        ), patch(
            "agent.auxiliary_client._read_main_model", return_value="claude-opus",
        ), patch(
            "agent.auxiliary_client.resolve_provider_client",
            return_value=(None, None),  # main provider has no client
        ), patch(
            "agent.auxiliary_client._try_openrouter",
            return_value=(chain_client, "google/gemini-3-flash-preview"),
        ):
            from agent.auxiliary_client import _resolve_auto

            client, model = _resolve_auto()

        assert client is chain_client
        assert model == "google/gemini-3-flash-preview"

    def test_no_main_config_uses_chain_directly(self):
        """No main provider configured → skip step 1, use chain (no regression)."""
        chain_client = MagicMock()
        with patch(
            "agent.auxiliary_client._read_main_provider", return_value="",
        ), patch(
            "agent.auxiliary_client._read_main_model", return_value="",
        ), patch(
            "agent.auxiliary_client._try_openrouter",
            return_value=(chain_client, "google/gemini-3-flash-preview"),
        ):
            from agent.auxiliary_client import _resolve_auto

            client, model = _resolve_auto()

        assert client is chain_client

    def test_runtime_override_wins_over_config(self, monkeypatch):
        """main_runtime kwarg overrides config-read main provider/model."""
        with patch(
            "agent.auxiliary_client._read_main_provider",
            return_value="openrouter",
        ), patch(
            "agent.auxiliary_client._read_main_model", return_value="config-model",
        ), patch(
            "agent.auxiliary_client.resolve_provider_client"
        ) as mock_resolve:
            mock_resolve.return_value = (MagicMock(), "runtime-model")

            from agent.auxiliary_client import _resolve_auto

            _resolve_auto(main_runtime={
                "provider": "anthropic",
                "model": "runtime-model",
                "base_url": "",
                "api_key": "",
                "api_mode": "",
            })

        # Runtime override wins
        assert mock_resolve.call_args.args[0] == "anthropic"
        assert mock_resolve.call_args.args[1] == "runtime-model"


# ── Vision — resolve_vision_provider_client ─────────────────────────────────


class TestResolveVisionMainFirst:
    """Vision auto-detection prefers the main provider first."""

    def test_openrouter_main_vision_uses_main_model(self, monkeypatch):
        """OpenRouter main with vision-capable model → aux vision uses main model."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")

        with patch(
            "agent.auxiliary_client._read_main_provider", return_value="openrouter",
        ), patch(
            "agent.auxiliary_client._read_main_model",
            return_value="anthropic/claude-sonnet-4.6",
        ), patch(
            "agent.auxiliary_client.resolve_provider_client"
        ) as mock_resolve, patch(
            "agent.auxiliary_client._resolve_task_provider_model",
            return_value=("auto", None, None, None, None),
        ):
            mock_client = MagicMock()
            mock_resolve.return_value = (mock_client, "anthropic/claude-sonnet-4.6")

            from agent.auxiliary_client import resolve_vision_provider_client

            provider, client, model = resolve_vision_provider_client()

        assert provider == "openrouter"
        assert client is mock_client
        assert model == "anthropic/claude-sonnet-4.6"
        # Verify it did NOT call the strict vision backend for OpenRouter
        # (which would have used a cheap gemini-flash-preview default)
        mock_resolve.assert_called_once()
        assert mock_resolve.call_args.args[0] == "openrouter"
        assert mock_resolve.call_args.args[1] == "anthropic/claude-sonnet-4.6"
        assert mock_resolve.call_args.kwargs.get("is_vision") is True

    def test_nous_main_vision_uses_paid_nous_vision_backend(self):
        """Paid Nous main → aux vision uses the dedicated Nous vision backend."""
        with patch(
            "agent.auxiliary_client._read_main_provider", return_value="nous",
        ), patch(
            "agent.auxiliary_client._read_main_model",
            return_value="openai/gpt-5",
        ), patch(
            "agent.auxiliary_client._resolve_task_provider_model",
            return_value=("auto", None, None, None, None),
        ), patch(
            "agent.auxiliary_client._resolve_strict_vision_backend",
            return_value=(MagicMock(), "google/gemini-3-flash-preview"),
        ):
            from agent.auxiliary_client import resolve_vision_provider_client

            provider, client, model = resolve_vision_provider_client()

        assert provider == "nous"
        assert client is not None
        assert model == "google/gemini-3-flash-preview"

    def test_nous_main_vision_uses_free_tier_nous_vision_backend(self):
        """Free-tier Nous main → aux vision uses MiMo omni, not the text main model."""
        with patch(
            "agent.auxiliary_client._read_main_provider", return_value="nous",
        ), patch(
            "agent.auxiliary_client._read_main_model",
            return_value="xiaomi/mimo-v2-pro",
        ), patch(
            "agent.auxiliary_client._resolve_task_provider_model",
            return_value=("auto", None, None, None, None),
        ), patch(
            "agent.auxiliary_client._resolve_strict_vision_backend",
            return_value=(MagicMock(), "xiaomi/mimo-v2-omni"),
        ):
            from agent.auxiliary_client import resolve_vision_provider_client

            provider, client, model = resolve_vision_provider_client()

        assert provider == "nous"
        assert client is not None
        assert model == "xiaomi/mimo-v2-omni"

    def test_exotic_provider_with_vision_override_preserved(self):
        """xiaomi → mimo-v2.5 override still wins over main_model."""
        with patch(
            "agent.auxiliary_client._read_main_provider", return_value="xiaomi",
        ), patch(
            "agent.auxiliary_client._read_main_model",
            return_value="mimo-v2-pro",  # text model
        ), patch(
            "agent.auxiliary_client.resolve_provider_client"
        ) as mock_resolve, patch(
            "agent.auxiliary_client._resolve_task_provider_model",
            return_value=("auto", None, None, None, None),
        ):
            mock_resolve.return_value = (MagicMock(), "mimo-v2.5")

            from agent.auxiliary_client import resolve_vision_provider_client

            provider, client, model = resolve_vision_provider_client()

        assert provider == "xiaomi"
        # Should use mimo-v2.5 (vision override), not mimo-v2-pro (text main)
        assert mock_resolve.call_args.args[1] == "mimo-v2.5"
        assert mock_resolve.call_args.kwargs.get("is_vision") is True

    def test_copilot_vision_sets_vision_header(self, monkeypatch):
        """Copilot vision requests include the header required for vision routing."""
        monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "ghu_test-token")

        captured = {}

        def fake_headers(*, is_agent_turn=False, is_vision=False):
            captured["is_agent_turn"] = is_agent_turn
            captured["is_vision"] = is_vision
            return {"Copilot-Vision-Request": "true"} if is_vision else {}

        with patch(
            "agent.auxiliary_client._read_main_provider", return_value="copilot",
        ), patch(
            "agent.auxiliary_client._read_main_model", return_value="configured-copilot-model",
        ), patch(
            "agent.auxiliary_client._resolve_task_provider_model",
            return_value=("auto", None, None, None, None),
        ), patch(
            "agent.auxiliary_client.OpenAI",
        ) as mock_openai, patch(
            "hermes_cli.auth.resolve_api_key_provider_credentials",
            return_value={
                "provider": "copilot",
                "api_key": "copilot-api-token",
                "base_url": "https://api.githubcopilot.com",
            },
        ), patch(
            "hermes_cli.copilot_auth.copilot_request_headers",
            side_effect=fake_headers,
        ):
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            from agent.auxiliary_client import resolve_vision_provider_client

            provider, client, model = resolve_vision_provider_client()

        assert provider == "copilot"
        assert client is mock_client
        assert model == "configured-copilot-model"
        assert captured == {"is_agent_turn": True, "is_vision": True}
        assert mock_openai.call_args.kwargs["default_headers"]["Copilot-Vision-Request"] == "true"

    def test_text_copilot_does_not_set_vision_header(self, monkeypatch):
        """Text Copilot requests keep the vision-only header off."""
        monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "ghu_test-token")

        captured = {}

        def fake_headers(*, is_agent_turn=False, is_vision=False):
            captured["is_agent_turn"] = is_agent_turn
            captured["is_vision"] = is_vision
            return {"Copilot-Vision-Request": "true"} if is_vision else {}

        with patch(
            "agent.auxiliary_client.OpenAI",
        ) as mock_openai, patch(
            "hermes_cli.auth.resolve_api_key_provider_credentials",
            return_value={
                "provider": "copilot",
                "api_key": "copilot-api-token",
                "base_url": "https://api.githubcopilot.com",
            },
        ), patch(
            "hermes_cli.copilot_auth.copilot_request_headers",
            side_effect=fake_headers,
        ):
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            from agent.auxiliary_client import resolve_provider_client

            client, model = resolve_provider_client("copilot", "gpt-5-mini")

        assert client is mock_client
        assert model == "gpt-5-mini"
        assert captured == {"is_agent_turn": True, "is_vision": False}
        assert "default_headers" not in mock_openai.call_args.kwargs

    def test_main_unavailable_vision_falls_through_to_aggregators(self):
        """Main provider fails → fall back to OpenRouter/Nous strict backends."""
        fallback_client = MagicMock()
        with patch(
            "agent.auxiliary_client._read_main_provider", return_value="deepseek",
        ), patch(
            "agent.auxiliary_client._read_main_model", return_value="deepseek-chat",
        ), patch(
            "agent.auxiliary_client.resolve_provider_client",
            return_value=(None, None),
        ), patch(
            "agent.auxiliary_client._resolve_strict_vision_backend",
            return_value=(fallback_client, "google/gemini-3-flash-preview"),
        ), patch(
            "agent.auxiliary_client._resolve_task_provider_model",
            return_value=("auto", None, None, None, None),
        ):
            from agent.auxiliary_client import resolve_vision_provider_client

            provider, client, model = resolve_vision_provider_client()

        assert client is fallback_client
        assert provider in {"openrouter", "nous"}

    def test_explicit_provider_override_still_wins(self):
        """Explicit config override bypasses main-first policy."""
        with patch(
            "agent.auxiliary_client._read_main_provider", return_value="openrouter",
        ), patch(
            "agent.auxiliary_client._read_main_model",
            return_value="anthropic/claude-opus-4.6",
        ), patch(
            "agent.auxiliary_client._resolve_task_provider_model",
            return_value=("nous", None, None, None, None),  # explicit override
        ), patch(
            "agent.auxiliary_client._resolve_strict_vision_backend"
        ) as mock_strict:
            mock_strict.return_value = (MagicMock(), "nous-default-model")

            from agent.auxiliary_client import resolve_vision_provider_client

            provider, client, model = resolve_vision_provider_client()

        # Explicit "nous" override → uses strict backend, NOT main model path
        assert provider == "nous"
        mock_strict.assert_called_once_with("nous", None)


# ── openai-codex vision skip (regression for Telegram OCR failure) ───────────


class TestCodexVisionSkip:
    """openai-codex must be skipped in vision auto-detect (it rejects non-Codex models).

    Regression: when the user's main provider is openai-codex and their main
    model is claude-sonnet-4.6 (or any non-Codex slug), the vision auto-detect
    path used to forward that model straight to the Codex endpoint, which
    rejected it with:
        "claude-sonnet-4.6 model is not supported when using Codex with a
         ChatGPT account"
    Fix: add "openai-codex" to _PROVIDERS_WITHOUT_VISION so auto-detect skips
    it and falls through to OpenRouter/Nous.
    """

    def test_codex_main_provider_skipped_in_vision_auto(self):
        """openai-codex as main provider → vision auto falls through to aggregator."""
        fallback_client = MagicMock()

        with patch(
            "agent.auxiliary_client._read_main_provider", return_value="openai-codex",
        ), patch(
            "agent.auxiliary_client._read_main_model", return_value="claude-sonnet-4.6",
        ), patch(
            "agent.auxiliary_client._resolve_task_provider_model",
            return_value=("auto", None, None, None, None),
        ), patch(
            "agent.auxiliary_client._resolve_strict_vision_backend",
            return_value=(fallback_client, "google/gemini-3-flash-preview"),
        ) as mock_strict, patch(
            "agent.auxiliary_client.resolve_provider_client",
        ) as mock_rpc:
            from agent.auxiliary_client import resolve_vision_provider_client

            provider, client, model = resolve_vision_provider_client()

        # Must NOT have tried resolve_provider_client with openai-codex + claude-sonnet-4.6
        for call in mock_rpc.call_args_list:
            if call.args[0] == "openai-codex":
                assert call.args[1] != "claude-sonnet-4.6", (
                    "resolve_provider_client was called with openai-codex + "
                    "claude-sonnet-4.6 — the Codex endpoint rejects this combo"
                )
        # Must have fallen back to a valid vision backend
        assert client is fallback_client
        assert provider in {"openrouter", "nous"}

    def test_codex_in_providers_without_vision(self):
        """openai-codex must be listed in _PROVIDERS_WITHOUT_VISION."""
        from agent.auxiliary_client import _PROVIDERS_WITHOUT_VISION

        assert "openai-codex" in _PROVIDERS_WITHOUT_VISION, (
            "openai-codex must be in _PROVIDERS_WITHOUT_VISION to prevent "
            "vision auto-detect from forwarding non-Codex models to the "
            "Codex endpoint (which rejects them)"
        )

    def test_codex_main_provider_vision_does_not_call_rpc_with_main_model(self):
        """resolve_provider_client must not be called with (openai-codex, main_model) for vision."""
        with patch(
            "agent.auxiliary_client._read_main_provider", return_value="openai-codex",
        ), patch(
            "agent.auxiliary_client._read_main_model", return_value="claude-sonnet-4.6",
        ), patch(
            "agent.auxiliary_client._resolve_task_provider_model",
            return_value=("auto", None, None, None, None),
        ), patch(
            "agent.auxiliary_client._resolve_strict_vision_backend",
            return_value=(MagicMock(), "google/gemini-3-flash-preview"),
        ), patch(
            "agent.auxiliary_client.resolve_provider_client",
        ) as mock_rpc:
            from agent.auxiliary_client import resolve_vision_provider_client

            resolve_vision_provider_client()

        bad_calls = [
            c for c in mock_rpc.call_args_list
            if len(c.args) >= 2
            and c.args[0] == "openai-codex"
            and c.args[1] == "claude-sonnet-4.6"
        ]
        assert not bad_calls, (
            f"resolve_provider_client called with openai-codex+claude-sonnet-4.6: {bad_calls}"
        )

    def test_explicit_codex_vision_override_still_reaches_rpc(self):
        """Explicit auxiliary.vision.provider=openai-codex still reaches codex resolution path.

        Users who deliberately set auxiliary.vision.provider: openai-codex
        with a compatible model should not be blocked — the skip only applies
        to the auto-detection path.  The explicit path goes through
        _get_cached_client → resolve_provider_client("openai-codex", ...).
        """
        fake_client = MagicMock()

        with patch(
            "agent.auxiliary_client._resolve_task_provider_model",
            return_value=("openai-codex", "codex-mini-latest", None, None, None),
        ), patch(
            "agent.auxiliary_client._get_cached_client",
            return_value=(fake_client, "codex-mini-latest"),
        ) as mock_cached:
            from agent.auxiliary_client import resolve_vision_provider_client

            provider, client, model = resolve_vision_provider_client()

        # Explicit openai-codex: _get_cached_client must be called with "openai-codex"
        assert mock_cached.called, "_get_cached_client should be called for explicit openai-codex"
        call_args = mock_cached.call_args
        assert call_args.args[0] == "openai-codex"
        assert call_args.args[1] == "codex-mini-latest"
        assert provider == "openai-codex"
        assert client is fake_client


# ── Constant cleanup ────────────────────────────────────────────────────────


def test_aggregator_providers_constant_removed():
    """The dead _AGGREGATOR_PROVIDERS constant should no longer live in the module.

    Removed when the main-first policy made the aggregator-skip guard obsolete.
    """
    import agent.auxiliary_client as aux_mod

    assert not hasattr(aux_mod, "_AGGREGATOR_PROVIDERS"), (
        "_AGGREGATOR_PROVIDERS was removed when _resolve_auto stopped "
        "treating aggregators specially. If you re-added it, the main-first "
        "policy may have regressed."
    )
