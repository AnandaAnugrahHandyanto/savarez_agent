"""Tests for the offline Hermes/OpenClaw/Codex lane orchestration skeleton."""

from __future__ import annotations

import json
from pathlib import Path

from agent_interop.lane_orchestrator import (
    Lane,
    TaskEnvelope,
    build_task_envelope,
    run_offline_task,
    route_task,
)


def test_route_task_prefers_coding_lane_for_repo_implementation_requests():
    envelope = build_task_envelope(
        request="Implement a pytest-covered refactor in the Hermes repo and run smoke tests",
        source="telegram",
        task_id="task-coding",
    )

    assert route_task(envelope) is Lane.CODEX_IMPLEMENTATION


def test_route_task_prefers_notebooklm_compression_for_research_requests_with_sources(tmp_path):
    source = tmp_path / "research.md"
    source.write_text("# Source\nAgent orchestration notes", encoding="utf-8")
    envelope = build_task_envelope(
        request="Research these sources and create an implementation brief",
        source="telegram",
        task_id="task-research",
        input_artifacts=[source],
    )

    assert route_task(envelope) is Lane.NOTEBOOKLM_COMPRESSION


def test_offline_research_lane_writes_task_artifacts_and_observability_report(tmp_path):
    source = tmp_path / "source.md"
    source.write_text(
        "# Hermes + OpenClaw\nOpenClaw routes tasks. Codex implements code. Hermes records skills.",
        encoding="utf-8",
    )
    envelope = build_task_envelope(
        request="Research OpenClaw Hermes Codex workflow and produce implementation brief",
        source="telegram",
        task_id="task-e2e",
        input_artifacts=[source],
    )

    result = run_offline_task(envelope, output_dir=tmp_path / "run")

    assert result.status == "completed"
    assert result.lane is Lane.NOTEBOOKLM_COMPRESSION
    assert result.report_path.exists()
    assert result.manifest_path.exists()
    assert result.output_artifacts
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["task_id"] == "task-e2e"
    assert manifest["lane"] == "notebooklm_compression"
    assert manifest["status"] == "completed"
    assert manifest["risk"] == "low-offline-dry-run"
    assert manifest["source"] == "telegram"
    assert manifest["agents"] == ["openclaw", "notebooklm", "hermes"]
    assert "implementation_brief" in manifest["output_artifacts"][0]
    report = result.report_path.read_text(encoding="utf-8")
    assert "task-e2e" in report
    assert "NotebookLM compression lane" in report
    assert "No external messages sent" in report


def test_offline_coding_lane_outputs_codex_handoff_without_running_codex(tmp_path):
    envelope = TaskEnvelope(
        task_id="task-codex",
        source="telegram",
        request="Implement task envelope validation in repo",
        lane=Lane.CODEX_IMPLEMENTATION,
        input_artifacts=[],
    )

    result = run_offline_task(envelope, output_dir=tmp_path / "run")

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert result.status == "completed"
    assert manifest["agents"] == ["openclaw", "codex", "hermes"]
    handoff = Path(manifest["output_artifacts"][0]["codex_handoff"])
    assert handoff.exists()
    text = handoff.read_text(encoding="utf-8")
    assert "Codex CLI implementation lane" in text
    assert "isolated worktree" in text
    assert "verification commands" in text


def test_build_task_envelope_rejects_empty_request():
    try:
        build_task_envelope(request="   ", source="telegram", task_id="bad")
    except ValueError as exc:
        assert "request" in str(exc)
    else:  # pragma: no cover - defensive clarity
        raise AssertionError("empty request should be rejected")
