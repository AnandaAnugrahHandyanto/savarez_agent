from tools.process_registry import format_process_notification


def test_format_completion_event():
    evt = {
        "type": "completion",
        "session_id": "proc_abc",
        "command": "sleep 5",
        "exit_code": 0,
        "output": "done",
    }
    result = format_process_notification(evt)
    assert "[IMPORTANT: Background process proc_abc completed" in result
    assert "exit code 0" in result
    assert "Command: sleep 5" in result
    assert "Output:\ndone]" in result


def test_format_watch_match_event():
    evt = {
        "type": "watch_match",
        "session_id": "proc_xyz",
        "command": "tail -f log",
        "pattern": "ERROR",
        "output": "ERROR: disk full",
        "suppressed": 0,
    }
    result = format_process_notification(evt)
    assert 'watch pattern "ERROR"' in result
    assert "Matched output:\nERROR: disk full" in result


def test_format_watch_match_with_suppressed():
    evt = {
        "type": "watch_match",
        "session_id": "proc_xyz",
        "command": "tail -f log",
        "pattern": "WARN",
        "output": "WARN: low mem",
        "suppressed": 3,
    }
    result = format_process_notification(evt)
    assert "3 earlier matches were suppressed" in result


def test_format_watch_disabled_event():
    evt = {
        "type": "watch_disabled",
        "message": "Watch disabled for proc_xyz: too many matches",
    }
    result = format_process_notification(evt)
    assert "[IMPORTANT: Watch disabled for proc_xyz" in result


def test_format_returns_none_for_empty_event():
    # Default type is "completion", session_id defaults to "unknown"
    evt = {}
    result = format_process_notification(evt)
    assert result is not None  # still formats with defaults
    assert "unknown" in result

import queue


def test_drain_notifications_returns_pending_events():
    from tools.process_registry import process_registry

    # Clear any leftover state
    while not process_registry.completion_queue.empty():
        process_registry.completion_queue.get_nowait()

    process_registry.completion_queue.put({
        "type": "completion",
        "session_id": "proc_drain1",
        "command": "echo hi",
        "exit_code": 0,
        "output": "hi",
    })
    process_registry.completion_queue.put({
        "type": "watch_match",
        "session_id": "proc_drain2",
        "command": "tail -f x",
        "pattern": "ERR",
        "output": "ERR found",
        "suppressed": 0,
    })

    try:
        results = process_registry.drain_notifications()
        assert len(results) == 2
        assert results[0][0]["session_id"] == "proc_drain1"
        assert "proc_drain1 completed" in results[0][1]
        assert results[1][0]["session_id"] == "proc_drain2"
        assert "watch pattern" in results[1][1]
    finally:
        while not process_registry.completion_queue.empty():
            process_registry.completion_queue.get_nowait()
        process_registry._completion_consumed.discard("proc_drain1")
        process_registry._completion_consumed.discard("proc_drain2")


def test_drain_notifications_skips_consumed():
    from tools.process_registry import process_registry

    while not process_registry.completion_queue.empty():
        process_registry.completion_queue.get_nowait()

    process_registry._completion_consumed.add("proc_consumed")
    process_registry.completion_queue.put({
        "type": "completion",
        "session_id": "proc_consumed",
        "command": "echo done",
        "exit_code": 0,
        "output": "done",
    })

    try:
        results = process_registry.drain_notifications()
        assert len(results) == 0
    finally:
        process_registry._completion_consumed.discard("proc_consumed")
        while not process_registry.completion_queue.empty():
            process_registry.completion_queue.get_nowait()


def test_drain_notifications_empty_queue():
    from tools.process_registry import process_registry

    while not process_registry.completion_queue.empty():
        process_registry.completion_queue.get_nowait()

    results = process_registry.drain_notifications()
    assert results == []

