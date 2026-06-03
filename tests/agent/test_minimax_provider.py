"""Tests for MiniMax provider hardening — context lengths, thinking guard, catalog."""


class TestMinimaxContextLengths:
    """Verify per-model context length entries for MiniMax models."""

    def test_m3_has_512k_context(self):
        from agent.model_metadata import DEFAULT_CONTEXT_LENGTHS
        # Keys are lowercase because the lookup lowercases model names
        assert "minimax-m3" in DEFAULT_CONTEXT_LENGTHS, "minimax-m3 missing from context lengths"
        assert DEFAULT_CONTEXT_LENGTHS["minimax-m3"] == 524288, "minimax-m3 expected 512K"

    def test_m2_variants_have_1m_context(self):
        from agent.model_metadata import DEFAULT_CONTEXT_LENGTHS
        # Keys are lowercase because the lookup lowercases model names
        assert "minimax-m2.7" in DEFAULT_CONTEXT_LENGTHS, "minimax-m2.7 missing from context lengths"
        assert DEFAULT_CONTEXT_LENGTHS["minimax-m2.7"] == 1_048_576, "minimax-m2.7 expected 1048576"

    def test_minimax_prefix_fallback(self):
        from agent.model_metadata import DEFAULT_CONTEXT_LENGTHS
        # The generic "minimax" prefix entry should be 512K (M3 default) for unknown models
        assert DEFAULT_CONTEXT_LENGTHS["minimax"] == 524288



class TestMinimaxThinkingGuard:
    """Verify that build_anthropic_kwargs does NOT add thinking params for MiniMax models."""

    def test_no_thinking_for_minimax_m27(self):
        from agent.anthropic_adapter import build_anthropic_kwargs
        kwargs = build_anthropic_kwargs(
            model="MiniMax-M2.7",
            messages=[{"role": "user", "content": "hello"}],
            tools=None,
            max_tokens=4096,
            reasoning_config={"enabled": True, "effort": "medium"},
        )
        assert "thinking" not in kwargs
        assert "output_config" not in kwargs

    def test_no_thinking_for_minimax_m3(self):
        from agent.anthropic_adapter import build_anthropic_kwargs
        kwargs = build_anthropic_kwargs(
            model="MiniMax-M3",
            messages=[{"role": "user", "content": "hello"}],
            tools=None,
            max_tokens=4096,
            reasoning_config={"enabled": True, "effort": "high"},
        )
        assert "thinking" not in kwargs

    def test_thinking_still_works_for_claude(self):
        from agent.anthropic_adapter import build_anthropic_kwargs
        kwargs = build_anthropic_kwargs(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "hello"}],
            tools=None,
            max_tokens=4096,
            reasoning_config={"enabled": True, "effort": "medium"},
        )
        assert "thinking" in kwargs


class TestMinimaxAuxModel:
    """Verify auxiliary model is the current default (M3), not highspeed."""

    def test_minimax_aux_is_m3(self):
        from agent.auxiliary_client import _API_KEY_PROVIDER_AUX_MODELS
        assert _API_KEY_PROVIDER_AUX_MODELS["minimax"] == "MiniMax-M3"
        assert _API_KEY_PROVIDER_AUX_MODELS["minimax-cn"] == "MiniMax-M3"

    def test_minimax_aux_not_highspeed(self):
        from agent.auxiliary_client import _API_KEY_PROVIDER_AUX_MODELS
        assert "highspeed" not in _API_KEY_PROVIDER_AUX_MODELS["minimax"]
        assert "highspeed" not in _API_KEY_PROVIDER_AUX_MODELS["minimax-cn"]


class TestMinimaxModelCatalog:
    """Verify the model catalog includes M3 (default) and M2.7 family, excludes M1/M2.5."""

    def test_catalog_includes_m3_as_default(self):
        from hermes_cli.models import _PROVIDER_MODELS
        for provider in ("minimax", "minimax-cn"):
            models = _PROVIDER_MODELS[provider]
            assert "MiniMax-M3" in models, f"MiniMax-M3 missing from {provider}"
            # M3 should be the first entry (default)
            assert models[0] == "MiniMax-M3", f"MiniMax-M3 should be first in {provider}"

    def test_catalog_includes_m27_family(self):
        from hermes_cli.models import _PROVIDER_MODELS
        for provider in ("minimax", "minimax-cn"):
            models = _PROVIDER_MODELS[provider]
            assert "MiniMax-M2.7" in models, f"MiniMax-M2.7 missing from {provider}"
            assert "MiniMax-M2.7-highspeed" in models, f"M2.7-highspeed missing from {provider}"

    def test_catalog_excludes_older_models(self):
        from hermes_cli.models import _PROVIDER_MODELS
        for provider in ("minimax", "minimax-cn"):
            models = _PROVIDER_MODELS[provider]
            for old_model in ("MiniMax-M1", "MiniMax-M1-40k", "MiniMax-M1-80k",
                              "MiniMax-M1-128k", "MiniMax-M1-256k",
                              "MiniMax-M2.5", "MiniMax-M2.1", "MiniMax-M2"):
                assert old_model not in models, f"{old_model} should be removed from {provider}"

    def test_catalog_excludes_deprecated(self):
        from hermes_cli.models import _PROVIDER_MODELS
        for provider in ("minimax", "minimax-cn"):
            models = _PROVIDER_MODELS[provider]
            assert "MiniMax-M2.1" not in models
