"""Readback tests for bundled Kanban protocol guidance docs."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _skill_text(name: str) -> str:
    return (ROOT / "skills" / "devops" / name / "SKILL.md").read_text()


def test_kanban_worker_skill_documents_block_immediate_boundary():
    text = _skill_text("kanban-worker")

    assert "Blocked side-effect or auth boundary after handoff" in text
    assert "GitHub push/open-PR" in text
    assert "kanban_comment" in text
    assert "kanban_block" in text
    assert "do not burn iterations" in text
    assert "separate publisher/finalizer card" in text
    assert "auth-verified publisher profile" in text


def test_kanban_orchestrator_skill_documents_pr_publisher_finalizer_pattern():
    text = _skill_text("kanban-orchestrator")

    assert "Implementation/verification -> GitHub publisher/finalizer" in text
    assert "parents=[implementation_or_verification_task_ids]" in text
    assert "github-pr-workflow" in text
    assert "auth-verified profile" in text
    assert "do not invent a GitHub-only profile name" in text