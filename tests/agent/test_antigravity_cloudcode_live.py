"""Opt-in live smoke for Antigravity Gemini models via Code Assist.

Run manually with:
    HERMES_LIVE_TESTS=1 scripts/run_tests.sh tests/agent/test_antigravity_cloudcode_live.py

This intentionally uses the local Antigravity CLI token file rather than env
credentials, so the normal hermetic env-var scrubber can stay enabled.
"""

from __future__ import annotations

import os

import pytest


LIVE = os.environ.get("HERMES_LIVE_TESTS") == "1"

pytestmark = pytest.mark.skipif(
    not LIVE,
    reason="live-only: set HERMES_LIVE_TESTS=1",
)

RECOMMENDED_GEMINI_AGENT_MODELS = (
    "gemini-3-flash-agent",
    "gemini-3.5-flash-low",
    "gemini-pro-agent",
    "gemini-3.1-pro-low",
)


def test_live_antigravity_recommended_gemini_models_return_sentinel():
    from agent.antigravity_oauth import load_credentials
    from agent.gemini_cloudcode_adapter import GeminiCloudCodeClient

    if load_credentials() is None:
        pytest.skip("Antigravity CLI token file is not configured")

    client = GeminiCloudCodeClient(api_key="dummy", credential_source="antigravity-cli")
    try:
        for model in RECOMMENDED_GEMINI_AGENT_MODELS:
            sentinel = f"hermes-antigravity-live-{model}"
            response = client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": f"Reply with exactly: {sentinel}",
                }],
                temperature=0,
            )
            assert (response.choices[0].message.content or "").strip() == sentinel
    finally:
        client.close()
