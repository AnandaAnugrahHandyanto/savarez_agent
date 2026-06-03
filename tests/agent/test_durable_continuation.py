"""Tests for durable continuation packet rendering and ledger writes."""

from __future__ import annotations

from pathlib import Path

import pytest

import agent.durable_continuation as durable_continuation

from agent.durable_continuation import (
    DurableContinuationPacket,
    render_job_ledger,
    render_next_run,
    write_durable_continuation,
)


def _packet() -> DurableContinuationPacket:
    return DurableContinuationPacket(
        job_name="Hermes writer helper",
        current_phase="WRITER_IMPLEMENTATION_VERIFIED",
        completed_tasks=["Added packet renderer", "Added atomic writer"],
        pending_tasks=["Update project docs", "Commit verified changes"],
        blockers=["Owner approval required for machine-changing work"],
        changed_files=["agent/durable_continuation.py", "tests/agent/test_durable_continuation.py"],
        evidence_links=["[[Progress Log]]", "[[Job Ledger]]"],
        verification_completed=["Targeted tests passed"],
        remaining_verification=["Independent reviewer pass"],
        exact_next_action="Run reviewer and update AR Beast docs with evidence.",
        do_not_repeat=["Do not rerun the full suite unless targeted tests fail"],
        last_updated="2026-06-03",
    )


def test_render_job_ledger_contains_required_sections_and_values() -> None:
    rendered = render_job_ledger(_packet())

    assert rendered.startswith("# Job Ledger\n")
    assert "Job name: Hermes writer helper" in rendered
    assert "Current phase: `WRITER_IMPLEMENTATION_VERIFIED`" in rendered
    assert "Last updated: 2026-06-03" in rendered
    assert "## Completed tasks" in rendered
    assert "- Added packet renderer" in rendered
    assert "## Pending tasks" in rendered
    assert "1. Update project docs" in rendered
    assert "## Exact next action" in rendered
    assert "Run reviewer and update AR Beast docs with evidence." in rendered


def test_render_next_run_is_compact_continuation_note() -> None:
    rendered = render_next_run(_packet())

    assert rendered.startswith("# NEXT_RUN\n")
    assert "Status: `WRITER_IMPLEMENTATION_VERIFIED`" in rendered
    assert "## Completed" in rendered
    assert "- Added atomic writer" in rendered
    assert "## Remaining work" in rendered
    assert "- Update project docs" in rendered
    assert "## Next action" in rendered
    assert "Run reviewer and update AR Beast docs with evidence." in rendered


def test_writer_creates_docs_atomically_and_returns_paths(tmp_path: Path) -> None:
    result = write_durable_continuation(tmp_path, _packet())

    assert result.job_ledger_path == tmp_path / "docs" / "Job Ledger.md"
    assert result.next_run_path == tmp_path / "docs" / "NEXT_RUN.md"
    assert result.job_ledger_path.read_text(encoding="utf-8") == render_job_ledger(_packet())
    assert result.next_run_path.read_text(encoding="utf-8") == render_next_run(_packet())
    assert not list((tmp_path / "docs").glob("*.tmp"))


def test_writer_rejects_docs_dir_outside_project(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-docs"

    with pytest.raises(ValueError, match="docs_dir must stay inside project_root"):
        write_durable_continuation(tmp_path, _packet(), docs_dir=outside)


def test_writer_accepts_custom_relative_docs_dir(tmp_path: Path) -> None:
    result = write_durable_continuation(tmp_path, _packet(), docs_dir="handoffs/current")

    assert result.job_ledger_path == tmp_path / "handoffs" / "current" / "Job Ledger.md"
    assert result.next_run_path == tmp_path / "handoffs" / "current" / "NEXT_RUN.md"
    assert result.job_ledger_path.exists()
    assert result.next_run_path.exists()


def test_writer_failure_preserves_existing_file_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    target = docs / "Job Ledger.md"
    target.write_text("existing handoff\n", encoding="utf-8")

    def fail_replace(self: Path, target: Path) -> Path:
        if target.name == "Job Ledger.md":
            raise OSError("simulated replace failure")
        return original_replace(self, target)

    original_replace = durable_continuation.Path.replace
    monkeypatch.setattr(durable_continuation.Path, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        write_durable_continuation(tmp_path, _packet())

    assert target.read_text(encoding="utf-8") == "existing handoff\n"
    assert not list(docs.glob("*.tmp"))


def test_blank_packet_values_render_as_none() -> None:
    packet = DurableContinuationPacket(
        job_name="Blank sections",
        current_phase="EMPTY",
        exact_next_action="Stop safely.",
        last_updated="2026-06-03",
    )

    rendered = render_job_ledger(packet)

    assert "## Completed tasks\n\n- None recorded." in rendered
    assert "## Pending tasks\n\n- None recorded." in rendered
    assert "## Blockers\n\n- None recorded." in rendered
