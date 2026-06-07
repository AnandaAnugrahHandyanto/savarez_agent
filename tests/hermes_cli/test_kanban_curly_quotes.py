"""Regression tests for curly-quote normalization in /kanban (issue #40915)."""
import pytest
from hermes_cli.kanban import run_slash


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    """Point kanban DB at a temp dir so tests are isolated."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_KANBAN_DB", str(tmp_path / "kanban.db"))
    return tmp_path


def test_curly_double_quotes_create(kanban_home):
    """Curly double quotes (U+201C/U+201D) should be treated like ASCII quotes."""
    out = run_slash('create \u201cship feature\u201d --assignee alice --json')
    # Should not produce a usage error; task should be created
    assert "usage error" not in out.lower(), f"Curly quotes caused usage error: {out}"
    assert "ship feature" in out, f"Title not parsed correctly: {out}"


def test_curly_single_quotes_create(kanban_home):
    """Curly single quotes (U+2018/U+2019) should be treated like ASCII quotes."""
    out = run_slash("create \u2018ship feature\u2019 --assignee bob --json")
    assert "usage error" not in out.lower(), f"Curly single quotes caused usage error: {out}"
    assert "ship feature" in out, f"Title not parsed correctly: {out}"


def test_mixed_curly_and_straight(kanban_home):
    """Mixed curly/straight quotes should work."""
    out = run_slash('create "plain task" --assignee charlie --json')
    assert "usage error" not in out.lower()
    assert "plain task" in out


def test_curly_quotes_inside_straight(kanban_home):
    """Curly quotes inside straight-quoted text should be preserved."""
    out = run_slash('create "Bob\u2019s task" --assignee dana --json')
    assert "usage error" not in out.lower()
    # The curly apostrophe should be preserved in the title
    assert "Bob" in out
