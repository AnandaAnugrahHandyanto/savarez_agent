"""OpenCode credential bridge: OpenClaw OPENCODE_API_KEY + auth-profiles."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_cli.auth import (
    _resolve_openclaw_opencode_api_key,
    get_api_key_provider_status,
    resolve_api_key_provider_credentials,
)


@pytest.fixture
def openclaw_state(tmp_path, monkeypatch):
    state = tmp_path / ".openclaw"
    agent_dir = state / "agents" / "main" / "agent"
    agent_dir.mkdir(parents=True)
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(state))
    return state


class TestOpenCodeEnvFallbacks:
    def test_opencode_zen_accepts_shared_opencode_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENCODE_ZEN_API_KEY", raising=False)
        monkeypatch.setenv("OPENCODE_API_KEY", "sk-opencode-shared")

        creds = resolve_api_key_provider_credentials("opencode-zen")
        assert creds["api_key"] == "sk-opencode-shared"
        assert creds["source"] == "OPENCODE_API_KEY"

    def test_opencode_go_prefers_go_key_then_shared(self, monkeypatch):
        monkeypatch.setenv("OPENCODE_GO_API_KEY", "sk-go-only")
        monkeypatch.setenv("OPENCODE_API_KEY", "sk-shared")

        creds = resolve_api_key_provider_credentials("opencode-go")
        assert creds["api_key"] == "sk-go-only"
        assert creds["source"] == "OPENCODE_GO_API_KEY"

    def test_opencode_go_falls_back_to_zen_then_shared(self, monkeypatch):
        monkeypatch.delenv("OPENCODE_GO_API_KEY", raising=False)
        monkeypatch.setenv("OPENCODE_ZEN_API_KEY", "sk-zen")
        monkeypatch.delenv("OPENCODE_API_KEY", raising=False)

        creds = resolve_api_key_provider_credentials("opencode-go")
        assert creds["api_key"] == "sk-zen"
        assert creds["source"] == "OPENCODE_ZEN_API_KEY"


class TestOpenClawAuthProfilesBridge:
    def test_reads_opencode_profile_key(self, openclaw_state, monkeypatch):
        monkeypatch.delenv("OPENCODE_ZEN_API_KEY", raising=False)
        monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
        monkeypatch.delenv("OPENCODE_GO_API_KEY", raising=False)

        auth_path = openclaw_state / "agents" / "main" / "agent" / "auth-profiles.json"
        auth_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "profiles": {
                        "opencode:default": {
                            "provider": "opencode",
                            "type": "api_key",
                            "key": "sk-from-openclaw-profile",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

        key, source = _resolve_openclaw_opencode_api_key()
        assert key == "sk-from-openclaw-profile"
        assert source == "openclaw:auth-profiles:opencode:default"

        status = get_api_key_provider_status("opencode-zen")
        assert status["configured"] is True
        assert status["key_source"] == "openclaw:auth-profiles:opencode:default"

    def test_reads_opencode_key_from_openclaw_dotenv(self, openclaw_state, monkeypatch):
        monkeypatch.delenv("OPENCODE_ZEN_API_KEY", raising=False)
        monkeypatch.delenv("OPENCODE_API_KEY", raising=False)

        (openclaw_state / ".env").write_text(
            "OPENCODE_API_KEY=sk-openclaw-dotenv\n",
            encoding="utf-8",
        )

        key, source = _resolve_openclaw_opencode_api_key()
        assert key == "sk-openclaw-dotenv"
        assert source == "openclaw:.env:OPENCODE_API_KEY"
