"""Regression tests for tool-heavy auto-compression tails."""

from pathlib import Path
from types import SimpleNamespace

from agent.conversation_loop import _compression_exhausted_result_if_needed
from agent.context_compressor import ContextCompressor, SUMMARY_PREFIX


def _compressor() -> ContextCompressor:
    c = ContextCompressor(
        model="test-model",
        config_context_length=200_000,
        protect_first_n=1,
        protect_last_n=20,
        summary_target_ratio=0.10,
        quiet_mode=True,
    )
    c.threshold_tokens = 10_000
    c.tail_token_budget = 400
    c.max_summary_tokens = 2_000
    return c


def _tool_pair(i: int, *, size: int = 8_000) -> list[dict]:
    call_id = f"call_{i}"
    return [
        {
            "role": "assistant",
            "content": f"Progress checkpoint {i}: inspecting tool output.",
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "arguments": f'{{"path":"/tmp/file_{i}.txt"}}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": call_id,
            "content": f"file_{i}.txt\n" + ("raw tool output\n" * size),
        },
    ]


def test_tool_heavy_tail_demotes_completed_tool_results_to_evidence(monkeypatch):
    c = _compressor()
    monkeypatch.setattr(c, "_generate_summary", lambda turns, focus_topic=None: SUMMARY_PREFIX + "summary")

    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Inspect many files and keep me posted."},
    ]
    for i in range(12):
        messages.extend(_tool_pair(i, size=900))
    messages.append(
        {
            "role": "assistant",
            "content": "I have inspected the files and am preparing the final answer.",
        }
    )

    compressed = c.compress(messages, current_tokens=80_000)

    tool_messages = [m for m in compressed if m.get("role") == "tool"]
    assert tool_messages
    assert all(len(str(m.get("content") or "")) < 1_000 for m in tool_messages)
    assert any(
        "preparing the final answer" in str(m.get("content") or "")
        for m in compressed
        if m.get("role") == "assistant"
    )


def test_tail_completed_tool_result_without_later_assistant_is_summarized(monkeypatch):
    c = _compressor()
    monkeypatch.setattr(c, "_generate_summary", lambda turns, focus_topic=None: SUMMARY_PREFIX + "summary")

    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Read the large file, then answer."},
    ]
    for i in range(4):
        messages.extend(_tool_pair(i, size=200))
    messages.extend([
        {
            "role": "assistant",
            "content": "I will inspect the file now.",
            "tool_calls": [
                {
                    "id": "call_final",
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "arguments": '{"path":"/tmp/final.txt"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_final",
            "content": "final.txt\n" + ("large raw result\n" * 1_000),
        },
    ])

    compressed = c.compress(messages, current_tokens=80_000)

    final_tool = compressed[-1]
    assert final_tool["role"] == "tool"
    assert final_tool["tool_call_id"] == "call_final"
    assert "[read_file] read /tmp/final.txt" in final_tool["content"]
    assert "large raw result" not in final_tool["content"]
    assert any(
        m.get("role") == "assistant"
        and any(tc.get("id") == "call_final" for tc in m.get("tool_calls", []))
        for m in compressed
    )


def test_reference_only_context_marker_is_not_latest_user_tail_anchor():
    c = _compressor()
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Real current task."},
        {"role": "assistant", "content": "Working on it."},
        {"role": "user", "content": SUMMARY_PREFIX + "\n## Active Task\nOld compacted task."},
        {"role": "assistant", "content": "Continuing from real task."},
    ]

    assert c._find_last_user_message_idx(messages, head_end=1) == 1


def test_repeated_ineffective_compression_marks_exhausted_before_retry():
    c = _compressor()
    c._ineffective_compression_count = 2

    assert c.should_compress(c.threshold_tokens + 1) is False
    assert c._last_compress_aborted is True
    assert c._last_compression_failure_code == "compression_exhausted"


def test_noop_preflight_compression_result_returns_compression_exhausted():
    persisted = []
    agent = SimpleNamespace(
        log_prefix="",
        context_compressor=SimpleNamespace(
            threshold_tokens=10_000,
            _last_compression_failure_code="compression_exhausted",
            _last_summary_error="compression exhausted: no material reduction",
        ),
        _flush_status_buffer=lambda: None,
        _persist_session=lambda messages, history: persisted.append((messages, history)),
    )
    messages = [{"role": "user", "content": "still too large"}]

    result = _compression_exhausted_result_if_needed(
        agent,
        messages,
        conversation_history=["previous"],
        api_call_count=2,
        prompt_tokens=12_000,
    )

    assert result is not None
    assert result["failed"] is True
    assert result["partial"] is True
    assert result["compression_exhausted"] is True
    assert result["messages"] == messages
    assert persisted == [(messages, ["previous"])]


def test_noop_preflight_compression_branch_checks_exhausted_before_break():
    src = Path("agent/conversation_loop.py").read_text(encoding="utf-8")
    noop_idx = src.find("if len(messages) >= _orig_len:")
    exhausted_idx = src.find("_compression_exhausted_result_if_needed", noop_idx)
    break_idx = src.find("break  # Cannot compress further", noop_idx)

    assert noop_idx != -1
    assert exhausted_idx != -1
    assert break_idx != -1
    assert noop_idx < exhausted_idx < break_idx
