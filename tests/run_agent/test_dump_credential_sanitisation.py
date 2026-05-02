"""Tests for request debug dump credential sanitisation (#8518, #18707).

Verify that _dump_api_request_debug never writes credential material to disk.
"""
import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import only what we need — run_agent is the module under test.
from run_agent import AIAgent


@pytest.fixture()
def agent(tmp_path):
    """Minimal AIAgent with mocked client, logs_dir pointed at tmp_path."""
    with (
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        a = AIAgent(
            api_key="test-key-1234567890",
            base_url="https://api.openai.com/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
        a.client = MagicMock()
        a.client.api_key = "sk-proj-abc123def456ghi789jkl012mno345pqr678"
        a.logs_dir = tmp_path
        a.session_id = "test-dump-sanitise"
        a.api_mode = "chat_completions"
        return a


class TestDumpCredentialSanitisation:
    """Ensure no plaintext credentials leak into request_dump_*.json files."""

    def _dump_and_read(self, agent, api_kwargs, *, reason="test", error=None):
        path = agent._dump_api_request_debug(
            api_kwargs, reason=reason, error=error
        )
        assert path is not None, "dump returned None"
        assert path.exists(), f"dump file not created: {path}"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_api_key_stripped_from_body(self, agent):
        """api_key inside api_kwargs body must not appear in dump."""
        secret = "sk-proj-abc123def456ghi789jkl012mno345pqr678"
        payload = self._dump_and_read(
            agent,
            {
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "hi"}],
                "api_key": secret,
            },
        )
        body_text = json.dumps(payload["request"]["body"])
        assert secret not in body_text
        assert "api_key" not in body_text

    def test_x_api_key_stripped_from_body(self, agent):
        """x_api_key inside api_kwargs body must not appear in dump."""
        secret = "xai-abc123def456ghi789jkl012mno345pqr678"
        payload = self._dump_and_read(
            agent,
            {
                "model": "grok-3",
                "messages": [{"role": "user", "content": "hi"}],
                "x_api_key": secret,
            },
        )
        body_text = json.dumps(payload["request"]["body"])
        assert secret not in body_text

    def test_extra_headers_stripped_from_body(self, agent):
        """extra_headers dict (may contain Authorization) must be removed."""
        secret = "Bearer sk-ant-secret1234567890"
        payload = self._dump_and_read(
            agent,
            {
                "model": "claude-3",
                "messages": [{"role": "user", "content": "hi"}],
                "extra_headers": {"Authorization": secret, "X-API-Key": "key-123"},
            },
        )
        body_text = json.dumps(payload["request"]["body"])
        assert "extra_headers" not in body_text
        assert secret not in body_text
        assert "key-123" not in body_text

    def test_headers_dict_stripped_from_body(self, agent):
        """Top-level headers dict in body must be removed."""
        payload = self._dump_and_read(
            agent,
            {
                "model": "test",
                "messages": [{"role": "user", "content": "hi"}],
                "headers": {"Authorization": "Bearer secret-token-here"},
            },
        )
        body_text = json.dumps(payload["request"]["body"])
        assert "headers" not in body_text
        assert "secret-token-here" not in body_text

    def test_auth_header_masked_in_request_headers(self, agent):
        """Authorization in the synthetic request headers must be masked."""
        payload = self._dump_and_read(
            agent,
            {"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        )
        auth = payload["request"]["headers"].get("Authorization", "")
        # Must not contain the full key
        assert "sk-proj-abc123def456ghi789jkl012mno345pqr678" not in auth
        # Must either be masked or absent
        if auth:
            assert "..." in auth or "***" in auth

    def test_no_timeout_in_body(self, agent):
        """timeout is transport-only and must not appear in dump."""
        payload = self._dump_and_read(
            agent,
            {"model": "gpt-4", "messages": [], "timeout": 120},
        )
        body_text = json.dumps(payload["request"]["body"])
        assert "timeout" not in body_text

    def test_normal_fields_preserved(self, agent):
        """Non-sensitive fields (model, messages, temperature) must survive."""
        payload = self._dump_and_read(
            agent,
            {
                "model": "gpt-4-turbo",
                "messages": [{"role": "user", "content": "hello world"}],
                "temperature": 0.7,
                "max_tokens": 4096,
            },
        )
        body = payload["request"]["body"]
        assert body["model"] == "gpt-4-turbo"
        assert body["temperature"] == 0.7
        assert body["max_tokens"] == 4096
        assert body["messages"][0]["content"] == "hello world"

    def test_full_serialised_dump_contains_no_secrets(self, agent):
        """End-to-end: the entire serialised JSON must contain no raw secrets."""
        secret_key = "sk-proj-abc123def456ghi789jkl012mno345pqr678"
        payload = self._dump_and_read(
            agent,
            {
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "hi"}],
                "api_key": secret_key,
                "extra_headers": {"Authorization": f"Bearer {secret_key}"},
            },
        )
        full_text = json.dumps(payload)
        assert secret_key not in full_text, (
            f"Raw secret found in dump: {secret_key[:12]}..."
        )
