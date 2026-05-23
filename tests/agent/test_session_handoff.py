"""Tests for automatic context-refresh handoff generation."""

from types import SimpleNamespace

from agent.session_handoff import maybe_prepare_context_refresh_handoff


class FakeSessionDB:
    def get_session_title(self, session_id):
        return "Hermes Adaptive Titles"


def make_agent(tmp_path, compression_count=2):
    return SimpleNamespace(
        session_id="sess-123",
        _session_db=FakeSessionDB(),
        context_compressor=SimpleNamespace(compression_count=compression_count),
        context_refresh_config={
            "enabled": True,
            "handoff_after_compressions": 2,
            "mode": "prepare_only",
            "write_session_handoff": True,
            "include_sha256": True,
            "max_handoff_lines": 250,
            "handoff_base_dir": str(tmp_path),
        },
        warnings=[],
        _emit_warning=lambda msg: None,
    )


def test_prepares_handoff_at_configured_compression_threshold(tmp_path):
    agent = make_agent(tmp_path, compression_count=2)
    messages = [
        {"role": "user", "content": "Implement adaptive session titles"},
        {"role": "assistant", "content": "Implemented Phase 1"},
    ]

    result = maybe_prepare_context_refresh_handoff(agent, messages, reason="compression_count>=2")

    assert result is not None
    assert result.session_id == "sess-123"
    assert result.path.exists()
    assert result.path.name == "AFTER_SESSION_COMPRESSION_HANDOFF.md"
    assert result.sha256
    assert result.line_count > 0
    assert "Reference session sess-123" in result.resume_prompt

    content = result.path.read_text(encoding="utf-8")
    assert "# Automatic Context Refresh Handoff" in content
    assert "Session ID: sess-123" in content
    assert "Reason: compression_count>=2" in content
    assert "Hermes Adaptive Titles" in content
    assert "Next Valid Actions" in content
    assert "unverified; verify before action" in content

    assert agent._pending_context_refresh["handoff_path"] == str(result.path)
    assert agent._context_refresh_handoff_prepared_for_count == 2


def test_skips_before_compression_threshold(tmp_path):
    agent = make_agent(tmp_path, compression_count=1)

    result = maybe_prepare_context_refresh_handoff(agent, [], reason="compression_count>=2")

    assert result is None
    assert not hasattr(agent, "_pending_context_refresh")


def test_does_not_spam_duplicate_handoff_for_same_compression_count(tmp_path):
    agent = make_agent(tmp_path, compression_count=2)

    first = maybe_prepare_context_refresh_handoff(agent, [], reason="compression_count>=2")
    second = maybe_prepare_context_refresh_handoff(agent, [], reason="compression_count>=2")

    assert first is not None
    assert second is None
