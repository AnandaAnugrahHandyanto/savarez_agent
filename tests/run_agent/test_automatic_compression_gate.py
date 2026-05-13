"""Tests for proactive automatic compression continuity gate."""

from pathlib import Path


def test_run_agent_gates_proactive_automatic_compression_before_context_compress():
    source = Path("run_agent.py").read_text(encoding="utf-8")

    assert "should_defer_automatic_compression" in source
    assert source.count("should_defer_automatic_compression") >= 2

    preflight_gate = source.index("should_defer_automatic_compression")
    preflight_compress = source.index("messages, active_system_prompt = self._compress_context(")
    assert preflight_gate < preflight_compress

    post_tool_marker = source.index("self._safe_print(\"  ⟳ compacting context…\")")
    post_tool_gate = source.rindex("should_defer_automatic_compression", 0, post_tool_marker)
    assert post_tool_gate < post_tool_marker
