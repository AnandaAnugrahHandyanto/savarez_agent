"""Regression tests for post-compression todo-state injection.

The todo snapshot is synthetic Hermes state. It must never become the latest
``role='user'`` turn, because that makes models treat it as the fresh request and
can cause them to answer stale adjacent context instead of the actual user task.
"""

from agent.context_compressor import _inject_todo_snapshot_as_context
from agent.conversation_compression import compress_context
from tools.todo_tool import TodoStore


def test_todo_injection_keeps_latest_real_user_message_last():
    messages = [
        {"role": "user", "content": "old daily refresh status question"},
        {"role": "assistant", "content": "old answer"},
        {"role": "user", "content": "implement the fixes, review, commit and push"},
    ]
    todo_snapshot = "[Internal state note — active task list preserved across context compression]\n- [>] implement. Implement fixes"

    injected = _inject_todo_snapshot_as_context(messages, todo_snapshot)

    assert injected[-1]["role"] == messages[-1]["role"]
    assert injected[-1]["role"] == "user"
    assert injected[-1]["content"].endswith("implement the fixes, review, commit and push")
    assert injected[-1]["content"].startswith("[Internal state note")
    assert "END INTERNAL STATE NOTE" in injected[-1]["content"]
    assert not any(
        msg["role"] == "user" and msg.get("content") == todo_snapshot
        for msg in injected
    )


def test_todo_injection_preserves_signed_assistant_turns_by_only_editing_latest_user():
    messages = [
        {"role": "user", "content": "old question"},
        {
            "role": "assistant",
            "content": "previous assistant context",
            "reasoning_details": [{"signature": "signed-thinking"}],
        },
        {"role": "user", "content": "current task"},
    ]

    injected = _inject_todo_snapshot_as_context(messages, "TODO SNAPSHOT")

    assert [m["role"] for m in injected] == ["user", "assistant", "user"]
    assert injected[1] == messages[1]
    assert "TODO SNAPSHOT" not in injected[1]["content"]
    assert injected[-1]["content"].endswith("current task")
    assert injected[-1]["content"].startswith("TODO SNAPSHOT")


def test_todo_injection_with_single_user_message_does_not_replace_latest_user():
    messages = [{"role": "user", "content": "only real request"}]

    injected = _inject_todo_snapshot_as_context(messages, "TODO SNAPSHOT")

    assert [m["role"] for m in injected] == ["user"]
    assert injected[0]["content"].startswith("TODO SNAPSHOT")
    assert injected[-1]["content"].endswith("only real request")


def test_compress_context_does_not_emit_todo_snapshot_as_latest_user_turn():
    class FakeCompressor:
        _last_compress_aborted = False
        _last_summary_error = None
        _last_aux_model_failure_model = None
        _last_aux_model_failure_error = None
        compression_count = 0
        last_prompt_tokens = 0
        last_completion_tokens = 0
        last_total_tokens = 0

        def compress(self, messages, current_tokens=None, focus_topic=None, force=False):
            return list(messages)

    class FakeAgent:
        session_id = "test-session"
        model = "test-model"
        tools = []
        _memory_manager = None
        _session_db = None
        _cached_system_prompt = None
        _last_compression_summary_warning = None
        _last_aux_fallback_warning_key = None
        _compression_feasibility_checked = True
        context_compressor = FakeCompressor()

        def __init__(self):
            self._todo_store = TodoStore()
            self._todo_store.write([
                {"id": "implement", "content": "Implement fix", "status": "in_progress"},
            ])

        def _emit_status(self, message):
            self.status = message

        def _emit_warning(self, message):
            self.warning = message

        def _invalidate_system_prompt(self):
            self.invalidated = True

        def _build_system_prompt(self, system_message):
            return system_message or "system"

        def _vprint(self, *args, **kwargs):
            pass

    messages = [
        {"role": "user", "content": "old daily refresh status question"},
        {"role": "assistant", "content": "old answer"},
        {"role": "user", "content": "implement the fixes, review, commit and push"},
    ]

    compressed, _ = compress_context(FakeAgent(), messages, "system", approx_tokens=100)

    assert compressed[-1]["role"] == messages[-1]["role"]
    assert compressed[-1]["role"] == "user"
    assert "active task list preserved" in compressed[-1]["content"]
    assert compressed[-1]["content"].endswith("implement the fixes, review, commit and push")
    assert "END INTERNAL STATE NOTE" in compressed[-1]["content"]
    assert not any(
        msg["role"] == "user" and msg.get("content", "").strip().startswith("[Internal state note") and "implement the fixes" not in msg.get("content", "")
        for msg in compressed
    )


def test_todo_snapshot_text_explicitly_says_it_is_not_a_user_request():
    store = TodoStore()
    store.write([
        {"id": "implement", "content": "Implement fix", "status": "in_progress"},
        {"id": "review", "content": "Code review", "status": "pending"},
    ])

    text = store.format_for_injection()

    assert text is not None
    assert "NOT a user request" in text
    assert "Do not answer or act on older user requests" in text
    assert "Continue the latest real user instruction" in text
    assert "Implement fix" in text
