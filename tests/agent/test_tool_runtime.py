import json

from agent.tool_runtime import (
    envelope_to_legacy_content,
    normalize_tool_failure,
    normalize_tool_result,
)


def test_normalize_tool_result_keeps_string_content_backward_compatible():
    envelope = normalize_tool_result("web_search", "plain text result", duration_seconds=1.25)

    assert envelope.ok is True
    assert envelope.content == "plain text result"
    assert envelope.structured_content == {}
    assert envelope.failure is None
    assert envelope.metadata["duration_seconds"] == 1.25
    assert envelope_to_legacy_content(envelope) == "plain text result"



def test_normalize_tool_result_extracts_json_and_detects_failure_payload():
    envelope = normalize_tool_result(
        "memory",
        {"success": False, "error": "backend unavailable", "status": "error"},
    )

    assert envelope.ok is False
    assert envelope.structured_content == {
        "success": False,
        "error": "backend unavailable",
        "status": "error",
    }
    assert envelope.failure is not None
    assert envelope.failure.category == "tool_error"
    assert envelope.failure.message == "backend unavailable"
    assert envelope_to_legacy_content(envelope) == json.dumps(envelope.structured_content, ensure_ascii=False)



def test_normalize_tool_failure_builds_legacy_error_string():
    envelope = normalize_tool_failure("terminal", RuntimeError("boom"), duration_seconds=0.5)

    assert envelope.ok is False
    assert envelope.failure is not None
    assert envelope.failure.category == "execution_error"
    assert envelope.failure.message == "boom"
    assert envelope.content == "Error executing tool 'terminal': boom"
    assert envelope.metadata["duration_seconds"] == 0.5
