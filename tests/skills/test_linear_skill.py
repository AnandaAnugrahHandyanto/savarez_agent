"""Tests for the Linear skill's name->id resolution in create-issue and update-issue.

These tests cover the resolver helpers (`_resolve_label_ids`, `_resolve_user_id`)
and the wiring inside `cmd_create_issue` / `cmd_update_issue` that consumes
them. The script is imported by path because skills/ is not on PYTHONPATH.
"""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
from typing import Any

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills/productivity/linear/scripts/linear_api.py"
)


@pytest.fixture
def linear(monkeypatch):
    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test")
    spec = importlib.util.spec_from_file_location("linear_api_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _scripted_gql(responses: list[Any], record: list[tuple[str, dict]] | None = None):
    """Build a fake ``gql`` that returns ``responses`` in order and records calls."""

    iterator = iter(responses)

    def fake(query: str, variables: dict | None = None) -> Any:
        if record is not None:
            record.append((query, variables or {}))
        try:
            return next(iterator)
        except StopIteration as e:
            raise AssertionError(
                f"gql() called more times than fixture provided. "
                f"Extra call: query={query!r} variables={variables!r}"
            ) from e

    return fake


# ---------- _resolve_label_ids ----------


def test_resolve_label_ids_single(linear, monkeypatch):
    monkeypatch.setattr(
        linear,
        "gql",
        _scripted_gql([
            {"team": {"labels": {"nodes": [
                {"id": "lbl-1", "name": "Bug"},
                {"id": "lbl-2", "name": "P1"},
            ]}}}
        ]),
    )
    assert linear._resolve_label_ids("team-id", ["Bug"]) == ["lbl-1"]


def test_resolve_label_ids_multi(linear, monkeypatch):
    monkeypatch.setattr(
        linear,
        "gql",
        _scripted_gql([
            {"team": {"labels": {"nodes": [
                {"id": "lbl-1", "name": "Bug"},
                {"id": "lbl-2", "name": "P1"},
                {"id": "lbl-3", "name": "Frontend"},
            ]}}}
        ]),
    )
    assert linear._resolve_label_ids("team-id", ["Bug", "Frontend"]) == ["lbl-1", "lbl-3"]


def test_resolve_label_ids_case_insensitive(linear, monkeypatch):
    monkeypatch.setattr(
        linear,
        "gql",
        _scripted_gql([
            {"team": {"labels": {"nodes": [{"id": "lbl-1", "name": "Bug"}]}}}
        ]),
    )
    assert linear._resolve_label_ids("team-id", ["bUg"]) == ["lbl-1"]


def test_resolve_label_ids_not_found_exits(linear, monkeypatch, capsys):
    monkeypatch.setattr(
        linear,
        "gql",
        _scripted_gql([
            {"team": {"labels": {"nodes": [{"id": "lbl-1", "name": "Bug"}]}}}
        ]),
    )
    with pytest.raises(SystemExit) as exc:
        linear._resolve_label_ids("team-id", ["Nonexistent"])
    assert exc.value.code == 1
    assert "Label 'Nonexistent' not found" in capsys.readouterr().err


def test_resolve_label_ids_handles_null_team(linear, monkeypatch, capsys):
    """When the team query returns a null team, error cleanly instead of crashing."""
    monkeypatch.setattr(linear, "gql", _scripted_gql([{"team": None}]))
    with pytest.raises(SystemExit):
        linear._resolve_label_ids("nope", ["Bug"])
    assert "Label 'Bug' not found" in capsys.readouterr().err


# ---------- _resolve_user_id ----------


def test_resolve_user_id_by_name(linear, monkeypatch):
    monkeypatch.setattr(
        linear,
        "gql",
        _scripted_gql([
            {"users": {"nodes": [
                {"id": "u-1", "name": "Alice Smith", "displayName": "alice", "email": "alice@example.com"},
            ]}}
        ]),
    )
    assert linear._resolve_user_id("Alice Smith") == "u-1"


def test_resolve_user_id_by_email(linear, monkeypatch):
    monkeypatch.setattr(
        linear,
        "gql",
        _scripted_gql([
            {"users": {"nodes": [
                {"id": "u-1", "name": "Alice", "displayName": "alice", "email": "alice@example.com"},
            ]}}
        ]),
    )
    assert linear._resolve_user_id("alice@example.com") == "u-1"


def test_resolve_user_id_by_display_name(linear, monkeypatch):
    monkeypatch.setattr(
        linear,
        "gql",
        _scripted_gql([
            {"users": {"nodes": [
                {"id": "u-1", "name": "Alice Smith", "displayName": "alice", "email": "alice@example.com"},
            ]}}
        ]),
    )
    assert linear._resolve_user_id("Alice") == "u-1"  # matches displayName "alice" (case-insensitive)


def test_resolve_user_id_not_found_exits(linear, monkeypatch, capsys):
    monkeypatch.setattr(
        linear,
        "gql",
        _scripted_gql([
            {"users": {"nodes": [{"id": "u-1", "name": "Alice", "displayName": "alice", "email": "alice@example.com"}]}}
        ]),
    )
    with pytest.raises(SystemExit) as exc:
        linear._resolve_user_id("bob@example.com")
    assert exc.value.code == 1
    assert "User 'bob@example.com' not found" in capsys.readouterr().err


def test_resolve_user_id_handles_null_fields(linear, monkeypatch):
    """Linear may return users with null displayName or email — don't crash."""
    monkeypatch.setattr(
        linear,
        "gql",
        _scripted_gql([
            {"users": {"nodes": [
                {"id": "u-1", "name": "Alice", "displayName": None, "email": None},
            ]}}
        ]),
    )
    assert linear._resolve_user_id("Alice") == "u-1"


# ---------- cmd_create_issue wiring ----------


def _ns(**kwargs):
    """Minimal argparse.Namespace stand-in."""
    import argparse
    defaults = {
        "title": None, "team": None, "description": None, "priority": None,
        "label": None, "assignee": None, "parent": None, "identifier": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_create_issue_resolves_labels_and_assignee(linear, monkeypatch, capsys):
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        linear,
        "gql",
        _scripted_gql(
            [
                # 1: _resolve_team_id
                {"teams": {"nodes": [{"id": "team-uuid", "key": "ENG", "name": "Engineering"}]}},
                # 2: _resolve_label_ids
                {"team": {"labels": {"nodes": [
                    {"id": "lbl-bug", "name": "Bug"},
                    {"id": "lbl-p1", "name": "P1"},
                ]}}},
                # 3: _resolve_user_id
                {"users": {"nodes": [
                    {"id": "user-alice", "name": "Alice", "displayName": "alice", "email": "alice@x.io"},
                ]}},
                # 4: issueCreate mutation
                {"issueCreate": {"success": True, "issue": {"id": "i-1", "identifier": "ENG-1", "title": "x", "url": "https://linear/ENG-1"}}},
            ],
            record=calls,
        ),
    )
    args = _ns(title="x", team="ENG", label="Bug,P1", assignee="alice@x.io")
    linear.cmd_create_issue(args)

    # Inspect the mutation payload sent to gql (last call).
    mutation_query, mutation_vars = calls[-1]
    assert "issueCreate" in mutation_query
    sent = mutation_vars["input"]
    assert sent["teamId"] == "team-uuid"
    assert sent["title"] == "x"
    assert sent["labelIds"] == ["lbl-bug", "lbl-p1"]
    assert sent["assigneeId"] == "user-alice"


def test_create_issue_without_label_or_assignee(linear, monkeypatch):
    """When neither flag is set, no resolver queries are issued."""
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        linear,
        "gql",
        _scripted_gql(
            [
                {"teams": {"nodes": [{"id": "team-uuid", "key": "ENG", "name": "Engineering"}]}},
                {"issueCreate": {"success": True, "issue": {"identifier": "ENG-2"}}},
            ],
            record=calls,
        ),
    )
    args = _ns(title="y", team="ENG")
    linear.cmd_create_issue(args)
    sent = calls[-1][1]["input"]
    assert "labelIds" not in sent
    assert "assigneeId" not in sent


def test_create_issue_label_ignores_empty_segments(linear, monkeypatch):
    """`--label ',Bug,'` should parse to `['Bug']`, not crash on the empty segments."""
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        linear,
        "gql",
        _scripted_gql(
            [
                {"teams": {"nodes": [{"id": "team-uuid", "key": "ENG", "name": "Eng"}]}},
                {"team": {"labels": {"nodes": [{"id": "lbl-bug", "name": "Bug"}]}}},
                {"issueCreate": {"success": True, "issue": {"identifier": "ENG-3"}}},
            ],
            record=calls,
        ),
    )
    args = _ns(title="z", team="ENG", label=",Bug, ,")
    linear.cmd_create_issue(args)
    assert calls[-1][1]["input"]["labelIds"] == ["lbl-bug"]


# ---------- cmd_update_issue wiring ----------


def test_update_issue_resolves_via_issue_team(linear, monkeypatch):
    """update-issue must look up the issue's team before resolving labels."""
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        linear,
        "gql",
        _scripted_gql(
            [
                # 1: fetch issue's team id
                {"issue": {"team": {"id": "team-uuid"}}},
                # 2: _resolve_label_ids in that team
                {"team": {"labels": {"nodes": [{"id": "lbl-p1", "name": "P1"}]}}},
                # 3: _resolve_user_id
                {"users": {"nodes": [
                    {"id": "user-bob", "name": "Bob", "displayName": "bob", "email": "bob@x.io"},
                ]}},
                # 4: issueUpdate mutation
                {"issueUpdate": {"success": True, "issue": {"identifier": "ENG-1"}}},
            ],
            record=calls,
        ),
    )
    args = _ns(identifier="ENG-1", label="P1", assignee="Bob")
    linear.cmd_update_issue(args)

    sent = calls[-1][1]["input"]
    assert sent["labelIds"] == ["lbl-p1"]
    assert sent["assigneeId"] == "user-bob"


def test_update_issue_unknown_issue_exits(linear, monkeypatch, capsys):
    monkeypatch.setattr(linear, "gql", _scripted_gql([{"issue": None}]))
    args = _ns(identifier="ENG-999", label="P1")
    with pytest.raises(SystemExit) as exc:
        linear.cmd_update_issue(args)
    assert exc.value.code == 1
    assert "Issue not found: ENG-999" in capsys.readouterr().err


def test_update_issue_title_only_does_not_query_team(linear, monkeypatch):
    """If only --title is given, the issue-team lookup must be skipped."""
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        linear,
        "gql",
        _scripted_gql(
            [{"issueUpdate": {"success": True, "issue": {"identifier": "ENG-1"}}}],
            record=calls,
        ),
    )
    args = _ns(identifier="ENG-1", title="new title")
    linear.cmd_update_issue(args)
    # Exactly one gql call: the mutation.
    assert len(calls) == 1
    assert "issueUpdate" in calls[0][0]
    assert calls[0][1]["input"] == {"title": "new title"}


def test_update_issue_no_fields_exits(linear, monkeypatch, capsys):
    monkeypatch.setattr(linear, "gql", _scripted_gql([]))
    args = _ns(identifier="ENG-1")
    with pytest.raises(SystemExit) as exc:
        linear.cmd_update_issue(args)
    assert exc.value.code == 1
    assert "No update fields provided" in capsys.readouterr().err
