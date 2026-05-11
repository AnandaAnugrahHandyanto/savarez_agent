"""Contract tests for structured artifact events."""

from __future__ import annotations

import json

import pytest

from agent.artifacts import (
    ArtifactEventError,
    artifact_event_from_tool_result,
    build_artifact_event,
    render_artifact_fallback_text,
)


ARTIFACT = {
    "id": "revenue-dashboard",
    "version": 1,
    "title": "Revenue Dashboard",
    "contentType": "text/html",
    "path": "/tmp/.hermes/artifacts/revenue-dashboard/versions/1/index.html",
    "url": "/api/plugins/artifacts/preview/revenue-dashboard/versions/1/index.html",
}


def test_build_artifact_event_returns_stable_envelope_without_raw_content():
    event = build_artifact_event(ARTIFACT)

    assert event == {
        "type": "artifact",
        "artifact": ARTIFACT,
    }
    assert "content" not in event["artifact"]
    assert "<html" not in json.dumps(event).lower()


def test_artifact_event_from_tool_result_converts_artifact_present_json():
    raw = json.dumps({"success": True, "artifact": ARTIFACT})

    event = artifact_event_from_tool_result(raw)

    assert event["type"] == "artifact"
    assert event["artifact"]["id"] == "revenue-dashboard"
    assert event["artifact"]["url"].startswith("/api/plugins/artifacts/preview/")


def test_render_artifact_fallback_text_keeps_plain_clients_backward_compatible():
    event = build_artifact_event(ARTIFACT)

    text = render_artifact_fallback_text(event)

    assert "Revenue Dashboard" in text
    assert "text/html" in text
    assert "/api/plugins/artifacts/preview/revenue-dashboard/versions/1/index.html" in text
    assert "<html" not in text.lower()


@pytest.mark.parametrize(
    "artifact",
    [
        {**ARTIFACT, "id": "../bad"},
        {**ARTIFACT, "version": 0},
        {**ARTIFACT, "contentType": ""},
        {**ARTIFACT, "url": "https://example.com/remote"},
        {**ARTIFACT, "content": "<html>do not leak</html>"},
    ],
)
def test_build_artifact_event_rejects_unsafe_or_incomplete_metadata(artifact):
    with pytest.raises(ArtifactEventError):
        build_artifact_event(artifact)


def test_artifact_event_from_tool_result_returns_none_for_non_artifact_results():
    assert artifact_event_from_tool_result(json.dumps({"success": True, "output": "ok"})) is None
    assert artifact_event_from_tool_result("not json") is None
    assert artifact_event_from_tool_result(json.dumps({"success": False, "error": "bad"})) is None
