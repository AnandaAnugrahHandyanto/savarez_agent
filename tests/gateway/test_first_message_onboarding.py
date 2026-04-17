"""Tests for first-message onboarding guidance in the gateway."""

from gateway.run import (
    _build_first_message_onboarding_note,
    _build_project_onboarding_note,
    _mark_project_onboarding_seen,
)


def test_first_message_onboarding_mentions_help_and_plan(tmp_path):
    note = _build_first_message_onboarding_note(
        history=[],
        has_any_sessions=False,
        cwd=str(tmp_path),
    )

    assert "/help" in note
    assert "/plan" in note


def test_first_message_onboarding_mentions_project_context_when_missing(tmp_path):
    note = _build_first_message_onboarding_note(
        history=[],
        has_any_sessions=False,
        cwd=str(tmp_path),
    )

    assert ".hermes.md" in note
    assert "AGENTS.md" in note


def test_first_message_onboarding_skips_project_context_hint_when_present(tmp_path):
    (tmp_path / "AGENTS.md").write_text("rules")

    note = _build_first_message_onboarding_note(
        history=[],
        has_any_sessions=False,
        cwd=str(tmp_path),
    )

    assert "/help" in note
    assert "/plan" in note
    assert ".hermes.md" not in note
    assert "AGENTS.md" not in note


def test_first_message_onboarding_skips_project_context_hint_when_parent_agents_exists(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "AGENTS.md").write_text("rules")
    subdir = tmp_path / "backend" / "src"
    subdir.mkdir(parents=True)

    note = _build_first_message_onboarding_note(
        history=[],
        has_any_sessions=False,
        cwd=str(subdir),
    )

    assert "/help" in note
    assert "/plan" in note
    assert ".hermes.md" not in note
    assert "AGENTS.md" not in note


def test_first_message_onboarding_skips_project_context_hint_when_parent_claude_exists(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "CLAUDE.md").write_text("rules")
    subdir = tmp_path / "frontend" / "src"
    subdir.mkdir(parents=True)

    note = _build_first_message_onboarding_note(
        history=[],
        has_any_sessions=False,
        cwd=str(subdir),
    )

    assert "/help" in note
    assert "/plan" in note
    assert ".hermes.md" not in note
    assert "AGENTS.md" not in note


def test_first_message_onboarding_skips_project_context_hint_when_parent_cursor_rules_exist(tmp_path):
    (tmp_path / ".git").mkdir()
    rules_dir = tmp_path / ".cursor" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "project.mdc").write_text("rules")
    subdir = tmp_path / "mobile" / "app"
    subdir.mkdir(parents=True)

    note = _build_first_message_onboarding_note(
        history=[],
        has_any_sessions=False,
        cwd=str(subdir),
    )

    assert "/help" in note
    assert "/plan" in note
    assert ".hermes.md" not in note
    assert "AGENTS.md" not in note


def test_first_message_onboarding_absent_after_first_session(tmp_path):
    note = _build_first_message_onboarding_note(
        history=[],
        has_any_sessions=True,
        cwd=str(tmp_path),
    )

    assert note == ""


def test_project_onboarding_note_shows_for_missing_context_even_after_first_session(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes_home"))
    note = _build_project_onboarding_note(cwd=str(tmp_path))

    assert ".hermes.md" in note
    assert "AGENTS.md" in note
    assert "/help" not in note


def test_project_onboarding_note_is_suppressed_after_marking_project_seen(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes_home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    project_root = tmp_path / "repo"
    subdir = project_root / "backend" / "src"
    subdir.mkdir(parents=True)
    (project_root / ".git").mkdir()

    first = _build_project_onboarding_note(cwd=str(subdir))
    _mark_project_onboarding_seen(str(subdir))
    second = _build_project_onboarding_note(cwd=str(project_root))

    assert ".hermes.md" in first
    assert second == ""


def test_project_onboarding_note_uses_persistent_state_file(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes_home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    project_root = tmp_path / "repo"
    project_root.mkdir()

    _mark_project_onboarding_seen(str(project_root))
    note = _build_project_onboarding_note(cwd=str(project_root))

    assert note == ""
    assert (hermes_home / ".project_onboarding_state.json").exists()
