"""Unit tests for hermes_cli/skills_config.py lifecycle command handlers
added for issue #19384 (`hermes skills {stats, archive, restore, prune}`).

These tests mock tools.skill_usage at the module level — never write to the
real ~/.hermes/skills/.usage.json sidecar. Each handler is exercised in
isolation; the sidecar I/O and archive mechanics are covered separately by
tests/tools/test_skill_usage.py.
"""
from datetime import datetime, timedelta, timezone

import pytest

# Ensure tools.skill_usage is loaded so monkeypatch.setattr can find attributes.
import tools.skill_usage  # noqa: F401

from hermes_cli.skills_config import (
    _cmd_archive,
    _cmd_prune,
    _cmd_restore,
    _cmd_stats,
)


def _iso_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _row(name, **overrides):
    """Build a row in the shape of agent_created_report() output."""
    base = {
        "name": name,
        "use_count": 0,
        "view_count": 0,
        "patch_count": 0,
        "last_used_at": None,
        "last_viewed_at": None,
        "last_patched_at": None,
        "created_at": _iso_days_ago(1),
        "state": "active",
        "pinned": False,
        "archived_at": None,
        "last_activity_at": None,
        "activity_count": 0,
    }
    base.update(overrides)
    return base


# ─── _cmd_stats ──────────────────────────────────────────────────────────────

def test_stats_empty_report(monkeypatch, capsys):
    monkeypatch.setattr("tools.skill_usage.agent_created_report", lambda: [])
    _cmd_stats(None)
    out = capsys.readouterr().out
    assert "No agent-created skills tracked yet" in out


def test_stats_renders_rows(monkeypatch, capsys):
    rows = [_row("foo-skill", use_count=3, activity_count=3,
                 last_activity_at=_iso_days_ago(1))]
    monkeypatch.setattr("tools.skill_usage.agent_created_report", lambda: rows)
    _cmd_stats(None)
    out = capsys.readouterr().out
    assert "foo-skill" in out


def test_stats_since_days_filters_old(monkeypatch, capsys):
    rows = [
        _row("recent", use_count=2, activity_count=2,
             last_activity_at=_iso_days_ago(2)),
        _row("ancient", use_count=10, activity_count=10,
             last_activity_at=_iso_days_ago(60)),
    ]
    monkeypatch.setattr("tools.skill_usage.agent_created_report", lambda: rows)
    _cmd_stats(7)
    out = capsys.readouterr().out
    assert "recent" in out
    assert "ancient" not in out


def test_stats_since_days_excludes_no_activity(monkeypatch, capsys):
    """A row with last_activity_at=None doesn't count as 'within last N days'."""
    rows = [_row("never-used", activity_count=0, last_activity_at=None)]
    monkeypatch.setattr("tools.skill_usage.agent_created_report", lambda: rows)
    _cmd_stats(7)
    out = capsys.readouterr().out
    assert "No activity in the last" in out
    assert "never-used" not in out


def test_stats_sort_by_activity_desc(monkeypatch, capsys):
    rows = [
        _row("low", activity_count=1, use_count=1,
             last_activity_at=_iso_days_ago(1)),
        _row("high", activity_count=99, use_count=99,
             last_activity_at=_iso_days_ago(1)),
        _row("mid", activity_count=10, use_count=10,
             last_activity_at=_iso_days_ago(1)),
    ]
    monkeypatch.setattr("tools.skill_usage.agent_created_report", lambda: rows)
    _cmd_stats(None)
    out = capsys.readouterr().out
    pos_high = out.find("high")
    pos_mid = out.find("mid")
    pos_low = out.find("low")
    assert pos_high != -1 and pos_mid != -1 and pos_low != -1
    assert pos_high < pos_mid < pos_low


# ─── _cmd_archive ────────────────────────────────────────────────────────────

def test_archive_pinned_refuses_with_hint(monkeypatch, capsys):
    monkeypatch.setattr(
        "tools.skill_usage.get_record",
        lambda n: _row(n, pinned=True),
    )
    monkeypatch.setattr(
        "tools.skill_usage.archive_skill",
        lambda n: pytest.fail("must not call archive_skill on pinned"),
    )
    with pytest.raises(SystemExit) as exc:
        _cmd_archive("foo")
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "pinned" in err.lower()
    assert "hermes curator unpin" in err


def test_archive_success(monkeypatch, capsys):
    monkeypatch.setattr(
        "tools.skill_usage.get_record",
        lambda n: {"pinned": False},
    )
    monkeypatch.setattr(
        "tools.skill_usage.archive_skill",
        lambda n: (True, "archived to .archive/foo"),
    )
    _cmd_archive("foo")
    out = capsys.readouterr().out
    assert "archived to .archive/foo" in out


def test_archive_failure_exits_nonzero(monkeypatch, capsys):
    monkeypatch.setattr(
        "tools.skill_usage.get_record",
        lambda n: {"pinned": False},
    )
    monkeypatch.setattr(
        "tools.skill_usage.archive_skill",
        lambda n: (False, "skill 'foo' not found"),
    )
    with pytest.raises(SystemExit) as exc:
        _cmd_archive("foo")
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "not found" in err


def test_archive_typo_falls_through_to_archive_skill(monkeypatch, capsys):
    """get_record returns _empty_record (pinned=False) for unknown names —
    the failure mode is archive_skill returning (False, ...), not a phantom
    pinned check."""
    archive_calls = []

    def fake_get_record(name):
        # Mirrors what tools.skill_usage._empty_record() returns.
        return {
            "use_count": 0, "view_count": 0, "patch_count": 0,
            "last_used_at": None, "last_viewed_at": None,
            "last_patched_at": None,
            "created_at": "2026-01-01T00:00:00+00:00",
            "state": "active", "pinned": False, "archived_at": None,
        }

    def fake_archive(name):
        archive_calls.append(name)
        return (False, f"skill '{name}' not found")

    monkeypatch.setattr("tools.skill_usage.get_record", fake_get_record)
    monkeypatch.setattr("tools.skill_usage.archive_skill", fake_archive)
    with pytest.raises(SystemExit) as exc:
        _cmd_archive("typo-skill")
    assert exc.value.code == 1
    assert archive_calls == ["typo-skill"]


# ─── _cmd_restore ────────────────────────────────────────────────────────────

def test_restore_success(monkeypatch, capsys):
    monkeypatch.setattr(
        "tools.skill_usage.restore_skill",
        lambda n: (True, "restored to skills/foo"),
    )
    _cmd_restore("foo")
    out = capsys.readouterr().out
    assert "restored to skills/foo" in out


def test_restore_failure_exits_nonzero(monkeypatch, capsys):
    monkeypatch.setattr(
        "tools.skill_usage.restore_skill",
        lambda n: (False, "skill 'foo' not found in archive"),
    )
    with pytest.raises(SystemExit) as exc:
        _cmd_restore("foo")
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "not found in archive" in err


# ─── _cmd_prune ──────────────────────────────────────────────────────────────

def test_prune_zero_days_rejected(capsys):
    with pytest.raises(SystemExit) as exc:
        _cmd_prune(0, skip_confirm=True, dry_run=False)
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "--days" in err


def test_prune_negative_days_rejected(capsys):
    with pytest.raises(SystemExit) as exc:
        _cmd_prune(-1, skip_confirm=True, dry_run=False)
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "--days" in err


def test_prune_empty_report(monkeypatch, capsys):
    monkeypatch.setattr("tools.skill_usage.agent_created_report", lambda: [])
    monkeypatch.setattr(
        "tools.skill_usage.archive_skill",
        lambda n: pytest.fail("must not archive when report is empty"),
    )
    _cmd_prune(90, skip_confirm=True, dry_run=False)
    out = capsys.readouterr().out
    assert "Nothing to prune" in out


def test_prune_dry_run_does_not_archive(monkeypatch, capsys):
    rows = [_row("old-skill", last_activity_at=_iso_days_ago(120))]
    monkeypatch.setattr("tools.skill_usage.agent_created_report", lambda: rows)
    monkeypatch.setattr(
        "tools.skill_usage.archive_skill",
        lambda n: pytest.fail("dry_run must not archive"),
    )
    _cmd_prune(90, skip_confirm=True, dry_run=True)
    out = capsys.readouterr().out
    assert "old-skill" in out
    assert "Dry run" in out


def test_prune_skip_confirm_archives_each(monkeypatch, capsys):
    archived = []
    rows = [
        _row("a", last_activity_at=_iso_days_ago(120)),
        _row("b", last_activity_at=_iso_days_ago(180)),
    ]
    monkeypatch.setattr("tools.skill_usage.agent_created_report", lambda: rows)

    def fake_archive(name):
        archived.append(name)
        return (True, f"archived {name}")

    monkeypatch.setattr("tools.skill_usage.archive_skill", fake_archive)
    _cmd_prune(90, skip_confirm=True, dry_run=False)
    assert sorted(archived) == ["a", "b"]


def test_prune_user_says_no_aborts(monkeypatch, capsys):
    rows = [_row("old-skill", last_activity_at=_iso_days_ago(120))]
    monkeypatch.setattr("tools.skill_usage.agent_created_report", lambda: rows)
    monkeypatch.setattr(
        "tools.skill_usage.archive_skill",
        lambda n: pytest.fail("user said no — must not archive"),
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")
    _cmd_prune(90, skip_confirm=False, dry_run=False)
    out = capsys.readouterr().out
    assert "Aborted" in out


def test_prune_user_says_yes_archives(monkeypatch, capsys):
    archived = []
    rows = [_row("old-skill", last_activity_at=_iso_days_ago(120))]
    monkeypatch.setattr("tools.skill_usage.agent_created_report", lambda: rows)

    def fake_archive(name):
        archived.append(name)
        return (True, "archived ok")

    monkeypatch.setattr("tools.skill_usage.archive_skill", fake_archive)
    monkeypatch.setattr("builtins.input", lambda _prompt: "y")
    _cmd_prune(90, skip_confirm=False, dry_run=False)
    assert archived == ["old-skill"]


def test_prune_excludes_pinned(monkeypatch, capsys):
    rows = [
        _row("pinned-old", pinned=True,
             last_activity_at=_iso_days_ago(200)),
        _row("unpinned-old", pinned=False,
             last_activity_at=_iso_days_ago(200)),
    ]
    monkeypatch.setattr("tools.skill_usage.agent_created_report", lambda: rows)
    archived = []
    monkeypatch.setattr(
        "tools.skill_usage.archive_skill",
        lambda n: archived.append(n) or (True, "ok"),
    )
    _cmd_prune(90, skip_confirm=True, dry_run=False)
    assert archived == ["unpinned-old"]


def test_prune_excludes_already_archived(monkeypatch, capsys):
    rows = [
        _row("already-arch", state="archived",
             last_activity_at=_iso_days_ago(200)),
        _row("active-old", state="active",
             last_activity_at=_iso_days_ago(200)),
    ]
    monkeypatch.setattr("tools.skill_usage.agent_created_report", lambda: rows)
    archived = []
    monkeypatch.setattr(
        "tools.skill_usage.archive_skill",
        lambda n: archived.append(n) or (True, "ok"),
    )
    _cmd_prune(90, skip_confirm=True, dry_run=False)
    assert archived == ["active-old"]


def test_prune_excludes_recent(monkeypatch, capsys):
    rows = [
        _row("fresh", last_activity_at=_iso_days_ago(10)),
        _row("stale", last_activity_at=_iso_days_ago(100)),
    ]
    monkeypatch.setattr("tools.skill_usage.agent_created_report", lambda: rows)
    archived = []
    monkeypatch.setattr(
        "tools.skill_usage.archive_skill",
        lambda n: archived.append(n) or (True, "ok"),
    )
    _cmd_prune(90, skip_confirm=True, dry_run=False)
    assert archived == ["stale"]


def test_prune_falls_back_to_created_at_for_never_used(monkeypatch, capsys):
    """A skill with no activity but old created_at IS eligible for prune —
    otherwise never-used skills become immortal."""
    rows = [_row("ancient-never-used",
                 last_activity_at=None,
                 created_at=_iso_days_ago(200))]
    monkeypatch.setattr("tools.skill_usage.agent_created_report", lambda: rows)
    archived = []
    monkeypatch.setattr(
        "tools.skill_usage.archive_skill",
        lambda n: archived.append(n) or (True, "ok"),
    )
    _cmd_prune(90, skip_confirm=True, dry_run=False)
    assert archived == ["ancient-never-used"]
