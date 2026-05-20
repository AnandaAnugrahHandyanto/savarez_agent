"""Regression coverage for Antigravity Cloud Code client wiring."""

from run_agent import AIAgent


def test_create_openai_client_routes_antigravity_to_cloudcode_client(monkeypatch):
    captured_kwargs = {}

    class FakeGeminiCloudCodeClient:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    monkeypatch.setattr(
        "agent.gemini_cloudcode_adapter.GeminiCloudCodeClient",
        FakeGeminiCloudCodeClient,
    )

    agent = object.__new__(AIAgent)
    agent.provider = "antigravity-cli"
    agent.base_url = "cloudcode-pa://google"
    agent.model = "gemini-3-flash-agent"

    client = agent._create_openai_client(
        {
            "api_key": "antigravity-token",
            "base_url": "cloudcode-pa://google",
            "default_headers": {"x-test": "yes"},
            "organization": "must-be-dropped",
        },
        reason="regression",
        shared=False,
    )

    assert isinstance(client, FakeGeminiCloudCodeClient)
    assert captured_kwargs == {
        "api_key": "antigravity-token",
        "base_url": "cloudcode-pa://google",
        "default_headers": {"x-test": "yes"},
        "credential_source": "antigravity-cli",
    }
