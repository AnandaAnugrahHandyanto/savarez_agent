"""Tests for same-provider model switch preserving api_key when resolver
returns empty credentials.

When switching models on the same provider (provider_changed=False),
resolve_runtime_provider() may return an empty api_key for providers
that rely on env-var-based key resolution (e.g. opencode-go). The
switch must fall back to the current session api_key rather than
overwriting it with an empty string.

Regression test for #44490.
"""

from unittest.mock import patch

from hermes_cli.model_switch import switch_model


_MOCK_VALIDATION = {
    "accepted": True,
    "persist": True,
    "recognized": True,
    "message": None,
}


def _run_switch(
    raw_input: str,
    current_provider: str,
    current_model: str,
    current_base_url: str,
    current_api_key: str,
    runtime_api_key: str = "",
    runtime_base_url: str = "",
):
    """Run switch_model with mocks that simulate empty resolver output."""
    with (
        patch("hermes_cli.model_switch.resolve_alias", return_value=None),
        patch("hermes_cli.model_switch.list_provider_models", return_value=[]),
        patch(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            return_value={
                "api_key": runtime_api_key,
                "base_url": runtime_base_url,
                "api_mode": "chat_completions",
            },
        ),
        patch(
            "hermes_cli.models.validate_requested_model",
            return_value=_MOCK_VALIDATION,
        ),
        patch("hermes_cli.model_switch.get_model_info", return_value=None),
        patch("hermes_cli.model_switch.get_model_capabilities", return_value=None),
        patch("hermes_cli.models.detect_provider_for_model", return_value=None),
    ):
        return switch_model(
            raw_input=raw_input,
            current_provider=current_provider,
            current_model=current_model,
            current_base_url=current_base_url,
            current_api_key=current_api_key,
        )


class TestSameProviderPreservesKey:
    """Same-provider model switch must keep current api_key when resolver
    returns empty."""

    def test_empty_resolved_key_falls_back_to_current(self):
        result = _run_switch(
            raw_input="kimi-k2.5",
            current_provider="opencode-go",
            current_model="mimo-v2.5",
            current_base_url="https://opencode.ai/zen/go/v1",
            current_api_key="sk-opencode-real-key",
            runtime_api_key="",
            runtime_base_url="https://opencode.ai/zen/go/v1",
        )

        assert result.success, f"switch failed: {result.error_message}"
        assert result.api_key == "sk-opencode-real-key", (
            f"Expected current api_key preserved; got {result.api_key!r}"
        )

    def test_empty_resolved_base_url_falls_back_to_current(self):
        result = _run_switch(
            raw_input="kimi-k2.5",
            current_provider="opencode-go",
            current_model="mimo-v2.5",
            current_base_url="https://opencode.ai/zen/go/v1",
            current_api_key="sk-opencode-real-key",
            runtime_api_key="sk-opencode-real-key",
            runtime_base_url="",
        )

        assert result.success, f"switch failed: {result.error_message}"
        assert result.base_url == "https://opencode.ai/zen/go/v1", (
            f"Expected current base_url preserved; got {result.base_url!r}"
        )

    def test_nonempty_resolved_key_is_used(self):
        result = _run_switch(
            raw_input="kimi-k2.5",
            current_provider="opencode-go",
            current_model="mimo-v2.5",
            current_base_url="https://opencode.ai/zen/go/v1",
            current_api_key="sk-old-key",
            runtime_api_key="sk-rotated-new-key",
            runtime_base_url="https://opencode.ai/zen/go/v1",
        )

        assert result.success, f"switch failed: {result.error_message}"
        assert result.api_key == "sk-rotated-new-key", (
            f"Expected resolved api_key used; got {result.api_key!r}"
        )
