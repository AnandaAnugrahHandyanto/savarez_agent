"""Regression coverage for the bundled Himalaya email skill."""

from __future__ import annotations

from pathlib import Path


SKILL_MD = Path(__file__).resolve().parents[2] / "skills/email/himalaya/SKILL.md"


def test_himalaya_skill_frames_cli_as_terminal_invocation() -> None:
    content = SKILL_MD.read_text(encoding="utf-8")

    assert "not** a Hermes Python/API tool" in content
    assert "default_api.himalaya" in content
    assert "send_email(...)" in content
    assert 'terminal(command="himalaya envelope list --output json")' in content
    assert 'terminal(command="himalaya ...")' in content
