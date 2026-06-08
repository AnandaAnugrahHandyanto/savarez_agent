"""Unit tests for the Upstage Solar provider profile.

Upstage Solar is a plain OpenAI-compatible api-key provider, so this verifies
the profile is registered correctly and wires the expected identity, endpoint,
auth, and catalog fields — the contract every downstream layer (auth, models,
doctor, runtime_provider, transport) reads from.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def upstage_profile():
    """Resolve the registered Upstage profile via the provider registry.

    Importing ``model_tools`` triggers plugin discovery, which registers the
    Upstage profile. Going through ``get_provider_profile`` keeps the test
    honest about the actual registration path (name + alias resolution).
    """
    import model_tools  # noqa: F401
    import providers

    profile = providers.get_provider_profile("upstage")
    assert profile is not None, "upstage provider profile must be registered"
    return profile


class TestUpstageProfile:
    def test_identity_and_endpoint(self, upstage_profile):
        assert upstage_profile.name == "upstage"
        assert upstage_profile.api_mode == "chat_completions"
        assert upstage_profile.auth_type == "api_key"
        assert upstage_profile.base_url == "https://api.upstage.ai/v1"
        assert upstage_profile.get_hostname() == "api.upstage.ai"

    def test_solar_alias_resolves(self):
        import model_tools  # noqa: F401
        import providers

        assert providers.get_provider_profile("solar") is upstage_profile_singleton()

    def test_env_vars(self, upstage_profile):
        # API key first, optional base-url override second (priority order).
        assert upstage_profile.env_vars == ("UPSTAGE_API_KEY", "UPSTAGE_BASE_URL")

    def test_fallback_models_are_solar(self, upstage_profile):
        # Only tool-calling/agentic Solar models belong in the offline catalog.
        assert upstage_profile.fallback_models == (
            "solar-pro3",
            "solar-pro2",
            "solar-mini",
        )

    def test_aux_model_is_cheap_mini(self, upstage_profile):
        assert upstage_profile.default_aux_model == "solar-mini"

    def test_plain_profile_has_no_reasoning_wire_quirks(self, upstage_profile):
        # No reasoning override: Solar uses the generic chat_completions shape,
        # so the profile must not inject extra_body / top-level kwargs.
        extra_body, top_level = upstage_profile.build_api_kwargs_extras(
            reasoning_config={"enabled": True, "effort": "high"}
        )
        assert extra_body == {}
        assert top_level == {}


def upstage_profile_singleton():
    import providers

    return providers.get_provider_profile("upstage")
