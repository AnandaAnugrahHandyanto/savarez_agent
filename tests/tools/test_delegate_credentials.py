import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.delegate_tool import _resolve_delegation_credentials


def test_base_url_delegation_uses_provider_credentials_when_api_key_missing():
    cfg = {
        "model": "MiniMax-M2.7",
        "provider": "minimax",
        "base_url": "https://api.minimax.io/v1",
        "api_key": "",
    }
    runtime = {
        "provider": "minimax",
        "base_url": "https://api.minimax.io/v1",
        "api_key": "minimax-test-key",
        "api_mode": "chat_completions",
    }

    with patch.dict("os.environ", {}, clear=False), patch(
        "hermes_cli.runtime_provider.resolve_runtime_provider", return_value=runtime
    ):
        resolved = _resolve_delegation_credentials(cfg, parent_agent=None)

    assert resolved["provider"] == "minimax"
    assert resolved["base_url"] == "https://api.minimax.io/v1"
    assert resolved["api_key"] == "minimax-test-key"
    assert resolved["api_mode"] == "chat_completions"


def test_base_url_delegation_error_mentions_provider_fallback_path():
    cfg = {
        "model": "MiniMax-M2.7",
        "provider": "minimax",
        "base_url": "https://api.minimax.io/v1",
        "api_key": "",
    }

    with patch.dict("os.environ", {}, clear=False), patch(
        "hermes_cli.runtime_provider.resolve_runtime_provider", side_effect=RuntimeError("missing creds")
    ):
        try:
            _resolve_delegation_credentials(cfg, parent_agent=None)
        except ValueError as exc:
            msg = str(exc)
        else:
            raise AssertionError("Expected ValueError when no delegation API key is available")

    assert "delegation.provider" in msg
    assert "OPENAI_API_KEY" in msg
