import json

from agent.display import get_cute_tool_message


def test_delegate_status_message_shows_worker_class_and_model():
    result = json.dumps({
        "results": [{
            "worker_class": "fast_worker",
            "resolved_lane": {"model": "gemini-3-flash-preview"},
        }]
    })
    msg = get_cute_tool_message(
        "delegate_task",
        {"goal": "Audit delegation"},
        1.2,
        result=result,
    )
    assert "fast_worker" in msg
    assert "gemini-3-flash-preview" in msg


def test_delegate_status_message_handles_parallel_tasks_without_result_details():
    msg = get_cute_tool_message(
        "delegate_task",
        {"tasks": [{"goal": "a"}, {"goal": "b"}]},
        0.8,
        result=None,
    )
    assert "2 parallel tasks" in msg
