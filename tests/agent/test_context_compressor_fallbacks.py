from unittest.mock import patch

from agent.context_compressor import ContextCompressor, SUMMARY_PREFIX


def _make_compressor():
    with patch("agent.context_compressor.get_model_context_length", return_value=100000):
        return ContextCompressor(
            model="test/model",
            threshold_percent=0.5,
            protect_first_n=2,
            protect_last_n=2,
            quiet_mode=True,
        )


def test_pruned_tool_results_preserve_head_and_tail_excerpt():
    compressor = _make_compressor()
    long_tool_output = "A" * 1200 + "MIDDLE" + "Z" * 500
    messages = [
        {"role": "user", "content": "u0"},
        {"role": "assistant", "content": "a1"},
        {"role": "tool", "content": long_tool_output, "tool_call_id": "call_1"},
        {"role": "user", "content": "u3"},
        {"role": "assistant", "content": "a4"},
        {"role": "user", "content": "u5"},
    ]

    pruned, pruned_count = compressor._prune_old_tool_results(messages, protect_tail_count=2)

    assert pruned_count == 1
    content = pruned[2]["content"]
    assert "Earlier tool output trimmed for context" in content
    assert "A" * 50 in content
    assert "Z" * 50 in content
    assert "chars omitted during context trimming" in content


def test_build_raw_fallback_summary_preserves_excerpt():
    compressor = _make_compressor()
    turns = [
        {"role": "user", "content": "用户要求修复压缩并避免丢上下文"},
        {
            "role": "assistant",
            "content": "我去检查 context compressor",
            "tool_calls": [
                {"function": {"name": "read_file", "arguments": '{"path":"agent/context_compressor.py"}'}}
            ],
        },
        {
            "role": "tool",
            "tool_name": "read_file",
            "tool_call_id": "call_2",
            "content": "X" * 1000 + "关键错误: Summary generation was unavailable" + "Y" * 500,
        },
    ]

    summary = compressor._build_raw_fallback_summary(turns)

    assert summary.startswith(SUMMARY_PREFIX)
    assert "## Raw Excerpt" in summary
    assert "[TOOL:read_file]" in summary
    assert "Summary generation was unavailable" in summary
    assert "chars omitted during context trimming" in summary


def test_compress_uses_raw_fallback_when_summary_generation_fails():
    compressor = _make_compressor()
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
        {"role": "user", "content": "third"},
        {"role": "assistant", "content": "fourth"},
        {"role": "tool", "content": "tool-output-" + ("A" * 1200), "tool_call_id": "call_3", "tool_name": "search"},
        {"role": "user", "content": "tail-user"},
        {"role": "assistant", "content": "tail-assistant"},
        {"role": "user", "content": "tail-user-2"},
        {"role": "assistant", "content": "tail-assistant-2"},
    ]

    with patch.object(ContextCompressor, "_generate_summary", return_value=None):
        compressed = compressor.compress(messages, current_tokens=99999)

    contents = [m.get("content", "") for m in compressed]
    joined = "\n".join(contents)
    assert SUMMARY_PREFIX in joined
    assert "## Raw Excerpt" in joined
    assert "tool-output-" in joined
    assert "Summary generation was unavailable, so a compact raw excerpt" in joined
