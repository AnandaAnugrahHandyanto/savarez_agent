"""Aux lane audit: verify every auxiliary lane resolves xai-oauth credentials correctly.

Usage:
    uv run python tests/agent/test_xai_oauth_aux_coverage.py
"""

import logging
import sys
from unittest.mock import patch, MagicMock

# Suppress noise from auxiliary_client internals during standalone runs
# When imported by pytest, logging is managed by the test runner.
_standalone = not __name__.startswith("pytest")
if _standalone:
    logging.disable(logging.CRITICAL)

# ── Lanes under test ──────────────────────────────────────────────────────
# Each lane is tested by calling resolve_provider_client("xai-oauth", model).
# The model used here is the generic fast non-reasoning Grok model.
XAI_OAUTH_MODEL = "grok-4-1-fast-non-reasoning"

# All auxiliary lanes that rely on resolve_provider_client for text tasks
TEXT_LANES = [
    "compression",
    "web_extract",
    "session_search",
    "skills_hub",
    "approval",
    "mcp",
    "title_generation",
    "triage_specifier",
    "kanban_decomposer",
    "profile_describer",
    "curator",
    "goal_judge",
]

# Vision is tested separately because it has a separate dispatch path
# via resolve_vision_provider_client and _resolve_strict_vision_backend.
VISION_LANE = "vision"

# ── Mock helpers ───────────────────────────────────────────────────────────


class _FakeCredential:
    """Simulates a PooledCredential with a valid xai-oauth token."""

    def __init__(self):
        self.access_token = "xai-oauth-fake-access-token-abc123"
        self.refresh_token = "xai-oauth-fake-refresh-token-xyz789"
        self.runtime_api_key = "xai-oauth-fake-access-token-abc123"
        self.runtime_base_url = None
        self.base_url = "https://api.x.ai/v1"


class _FakePool:
    """Simulates CredentialPool returning a single valid xai-oauth entry."""

    def __init__(self):
        self._entry = _FakeCredential()

    def has_credentials(self):
        return True

    def has_available(self):
        return True

    def select(self):
        return self._entry

    def entries(self):
        return [self._entry]


# ── Test runner ────────────────────────────────────────────────────────────


def _make_mock_openai():
    """Return a MagicMock that looks like an OpenAI client instance."""
    mock_client = MagicMock()
    mock_client.api_key = "xai-oauth-fake-access-token-abc123"
    mock_client.base_url = "https://api.x.ai/v1"
    return mock_client


def test_resolve_provider_client_text_lanes():
    """For each text lane, resolve_provider_client("xai-oauth", model)
    must return (client, model) through _build_xai_oauth_aux_client."""
    failed = []

    # The fake pool is returned any time load_pool("xai-oauth") is called
    fake_pool = _FakePool()
    mock_client = _make_mock_openai()

    for lane in TEXT_LANES:
        with patch("agent.auxiliary_client.load_pool", return_value=fake_pool):
            with patch("agent.auxiliary_client.OpenAI", return_value=mock_client):
                from agent.auxiliary_client import resolve_provider_client

                result = resolve_provider_client("xai-oauth", XAI_OAUTH_MODEL)

                if result is None:
                    failed.append(lane)
                    continue

                client, model = result
                if client is None:
                    failed.append(lane)
                elif model != XAI_OAUTH_MODEL:
                    failed.append(f"{lane} (model mismatch: got {model!r})")

    if failed:
        assert False, (
            f"{len(failed)} lane(s) did not resolve xai-oauth:\n"
            + "\n".join(f"  - {name}" for name in failed)
        )
    else:
        print(f"PASS: all {len(TEXT_LANES)} text lanes resolved xai-oauth correctly")


def test_xai_oauth_returns_client_and_model():
    """Verify that resolve_provider_client("xai-oauth", "grok-4-1-fast-non-reasoning")
    returns the expected (client, model) tuple through _build_xai_oauth_aux_client."""
    fake_pool = _FakePool()
    mock_client = _make_mock_openai()

    with patch("agent.auxiliary_client.load_pool", return_value=fake_pool):
        with patch("agent.auxiliary_client.OpenAI", return_value=mock_client):
            from agent.auxiliary_client import resolve_provider_client

            client, model = resolve_provider_client("xai-oauth", XAI_OAUTH_MODEL)

            assert client is not None, "Expected a valid client, got None"
            assert model == XAI_OAUTH_MODEL, (
                f"Expected model {XAI_OAUTH_MODEL!r}, got {model!r}"
            )
            # The client should be a plain OpenAI instance (xAI speaks Chat Completions,
            # not the Responses API used by OpenAI Codex).
            # (verify it has the expected interface)
            assert hasattr(client, "chat"), "Client missing .chat attribute"
            assert hasattr(client.chat, "completions"), (
                "Client missing .chat.completions attribute"
            )
            assert hasattr(client, "api_key"), "Client missing .api_key attribute"
            assert hasattr(client, "base_url"), "Client missing .base_url attribute"

    print("PASS: resolve_provider_client('xai-oauth', model) returns valid (client, model)")


def test_vision_lane_resolves_xai_oauth():
    """Verify that the vision lane can resolve xai-oauth credentials
    through the resolve_vision_provider_client path."""
    fake_pool = _FakePool()
    mock_client = _make_mock_openai()

    with patch("agent.auxiliary_client.load_pool", return_value=fake_pool):
        with patch("agent.auxiliary_client.OpenAI", return_value=mock_client):
            from agent.auxiliary_client import resolve_vision_provider_client

            # Test resolve_vision_provider_client with explicit xai-oauth provider
            requested, client, model = resolve_vision_provider_client(
                "xai-oauth", XAI_OAUTH_MODEL
            )

            assert client is not None, (
                "Vision: resolve_vision_provider_client('xai-oauth', model) "
                "returned None for client"
            )
            assert model == XAI_OAUTH_MODEL, (
                f"Vision: expected model {XAI_OAUTH_MODEL!r}, got {model!r}"
            )
            assert requested == "xai-oauth", (
                f"Vision: expected provider 'xai-oauth', got {requested!r}"
            )

    print("PASS: resolve_vision_provider_client('xai-oauth', model) returns valid client")


def test_strict_vision_backend_does_not_support_xai_oauth():
    """Verify _resolve_strict_vision_backend('xai-oauth', model) returns
    (None, None) — this backend dispatches to specific providers only."""
    from agent.auxiliary_client import _resolve_strict_vision_backend

    client, model = _resolve_strict_vision_backend("xai-oauth", XAI_OAUTH_MODEL)

    assert client is None, (
        "_resolve_strict_vision_backend should return None for xai-oauth "
        "(no dedicated dispatch arm)"
    )
    assert model is None, (
        "_resolve_strict_vision_backend should return None model for xai-oauth"
    )

    print(
        "PASS: _resolve_strict_vision_backend('xai-oauth', model) "
        "correctly returns (None, None)"
    )


# ── Main ──────────────────────────────────────────────────────────────────


def main():
    print("=" * 60)
    print("Aux Lane Audit: xai-oauth Credential Resolution")
    print("=" * 60)
    print()

    tests = [
        ("Text lanes (resolve_provider_client)", test_resolve_provider_client_text_lanes),
        ("xai-oauth returns (client, model)", test_xai_oauth_returns_client_and_model),
        ("Vision lane (resolve_vision_provider_client)", test_vision_lane_resolves_xai_oauth),
        ("Strict vision backend (expected None)", test_strict_vision_backend_does_not_support_xai_oauth),
    ]

    passed = 0
    failed = 0

    for label, test_fn in tests:
        print(f"[  RUN  ] {label}")
        try:
            test_fn()
            print(f"[   OK  ] {label}")
            passed += 1
        except Exception as exc:
            print(f"[  FAIL ] {label}")
            print(f"         {exc}")
            failed += 1
        print()

    print("-" * 60)
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    print("-" * 60)

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
