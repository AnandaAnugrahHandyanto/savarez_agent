"""Structured artifact event helpers.

This module defines a small, backwards-compatible event envelope for Hermes
Canvas/Artifacts. It deliberately does not wire events into every runtime stream;
callers can opt in by converting an ``artifact_present`` result into this shape
and sending the fallback text to clients that do not understand structured
artifact events.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any


_ARTIFACT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,127}$")
_PREVIEW_URL_PREFIX = "/api/plugins/artifacts/preview/"
_REQUIRED_FIELDS = ("id", "version", "title", "contentType", "path", "url")
_FORBIDDEN_FIELDS = {"content", "html", "source", "sourceContent", "raw", "body"}


class ArtifactEventError(ValueError):
    """Raised when artifact metadata is incomplete or unsafe for event output."""


def _validate_artifact_metadata(artifact: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(artifact, dict):
        raise ArtifactEventError("artifact metadata must be an object")

    forbidden = _FORBIDDEN_FIELDS.intersection(artifact)
    if forbidden:
        raise ArtifactEventError(f"artifact metadata includes raw content fields: {sorted(forbidden)}")

    missing = [field for field in _REQUIRED_FIELDS if field not in artifact]
    if missing:
        raise ArtifactEventError(f"artifact metadata missing required fields: {missing}")

    artifact_id = artifact.get("id")
    if not isinstance(artifact_id, str) or not _ARTIFACT_ID_RE.fullmatch(artifact_id):
        raise ArtifactEventError("invalid artifact id")

    try:
        version = int(artifact.get("version"))
    except (TypeError, ValueError) as exc:
        raise ArtifactEventError("invalid artifact version") from exc
    if version < 1:
        raise ArtifactEventError("artifact version must be >= 1")

    for field in ("title", "contentType", "path", "url"):
        value = artifact.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ArtifactEventError(f"artifact field {field!r} must be a non-empty string")

    url = artifact["url"]
    if not url.startswith(_PREVIEW_URL_PREFIX):
        raise ArtifactEventError("artifact url must use the local artifacts preview API")

    safe = deepcopy(artifact)
    safe["version"] = version
    return safe


def build_artifact_event(artifact: dict[str, Any]) -> dict[str, Any]:
    """Build a stable structured event for rich clients.

    The event is intentionally tiny:

    ``{"type": "artifact", "artifact": {...metadata...}}``

    It carries preview metadata only, never raw artifact contents. Clients that do
    not understand the event can ignore it and render ``render_artifact_fallback_text``.
    """

    return {"type": "artifact", "artifact": _validate_artifact_metadata(artifact)}


def artifact_event_from_tool_result(raw_result: str | dict[str, Any]) -> dict[str, Any] | None:
    """Convert a successful ``artifact_present`` result into an artifact event.

    Returns ``None`` for non-JSON, unsuccessful, or non-artifact tool results so
    callers can use it opportunistically without changing existing tool handling.
    Invalid artifact metadata still raises ``ArtifactEventError`` because that is
    a producer bug, not a normal non-artifact result.
    """

    if isinstance(raw_result, str):
        try:
            data = json.loads(raw_result)
        except json.JSONDecodeError:
            return None
    elif isinstance(raw_result, dict):
        data = raw_result
    else:
        return None

    if not isinstance(data, dict) or data.get("success") is not True:
        return None
    artifact = data.get("artifact")
    if not isinstance(artifact, dict):
        return None
    return build_artifact_event(artifact)


def render_artifact_fallback_text(event: dict[str, Any]) -> str:
    """Render a compact plain-text fallback for clients that ignore events."""

    if not isinstance(event, dict) or event.get("type") != "artifact":
        raise ArtifactEventError("event must be an artifact event")
    artifact = _validate_artifact_metadata(event.get("artifact", {}))
    return (
        f"Artifact ready: {artifact['title']} "
        f"({artifact['contentType']}, v{artifact['version']})\n"
        f"Preview: {artifact['url']}"
    )
