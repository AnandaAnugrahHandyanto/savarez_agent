"""Tests for skills/productivity/linear/scripts/linear_api.py.

Covers name->UUID resolution for labels and assignees and its wiring into
create-issue / update-issue, including the hardening that makes it safe on any
workspace: cursor pagination past the 250 page cap, ambiguous-name detection,
additive (non-destructive) label updates, multiple labels per call,
active-user-only assignment, and the `me` shortcut.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "productivity"
    / "linear"
    / "scripts"
    / "linear_api.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("linear_api_skill", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeGQL:
    """Stand-in for gql() that routes by query shape and records mutations.

    Connection responses include pageInfo with hasNextPage=False so the
    paginator terminates after one page (multi-page paging is exercised
    separately against _paginate directly).
    """

    def __init__(self):
        self.teams: list[dict] = []
        self.labels: list[dict] = []                       # team-scoped results
        self.workspace_labels: list[dict] | None = None    # defaults to self.labels
        self.users: list[dict] = []
        self.issue_team_id: str | None = None
        self.issue_labels: list[dict] = []
        self.viewer_id: str | None = None
        self.calls: list[tuple[str, dict | None]] = []
        self.mutation_input: dict | None = None

    def __call__(self, query, variables=None):
        self.calls.append((query, variables))
        q = " ".join(query.split())
        if "issueCreate" in q:
            self.mutation_input = variables["input"]
            return {"issueCreate": {"success": True, "issue": {"identifier": "ENG-1"}}}
        if "issueUpdate" in q:
            self.mutation_input = variables["input"]
            return {"issueUpdate": {"success": True, "issue": {"identifier": variables["id"]}}}
        if "viewer" in q:
            return {"viewer": {"id": self.viewer_id}}
        if "issue(id:" in q and "team" in q:
            return {"issue": {
                "team": {"id": self.issue_team_id},
                "labels": {"nodes": self.issue_labels},
            }}
        if "teams(" in q:
            return {"teams": {"nodes": self.teams, "pageInfo": {"hasNextPage": False}}}
        if "team(id:" in q and "labels(" in q:  # team-scoped label query
            return {"team": {"labels": {"nodes": self.labels, "pageInfo": {"hasNextPage": False}}}}
        if "issueLabels(" in q:  # workspace-wide label query
            nodes = self.workspace_labels if self.workspace_labels is not None else self.labels
            return {"issueLabels": {"nodes": nodes, "pageInfo": {"hasNextPage": False}}}
        if "users(" in q:
            return {"users": {"nodes": self.users, "pageInfo": {"hasNextPage": False}}}
        return {}


@pytest.fixture
def mod(monkeypatch):
    module = load_module()
    monkeypatch.setenv("LINEAR_API_KEY", "test-key")
    return module


@pytest.fixture
def fake(mod, monkeypatch):
    f = FakeGQL()
    monkeypatch.setattr(mod, "gql", f)
    return f


def ns(**kw):
    defaults = dict(
        identifier=None, title=None, description=None, priority=None,
        parent=None, label=None, assignee=None, team=None,
    )
    defaults.update(kw)
    return argparse.Namespace(**defaults)


def user(uid, name=None, display=None, email=None, active=True):
    return {"id": uid, "name": name, "displayName": display, "email": email, "active": active}


# ---------- _paginate ----------

def test_paginate_follows_cursors(mod, monkeypatch):
    pages = [
        {"conn": {"nodes": [{"id": "a"}], "pageInfo": {"hasNextPage": True, "endCursor": "c1"}}},
        {"conn": {"nodes": [{"id": "b"}], "pageInfo": {"hasNextPage": True, "endCursor": "c2"}}},
        {"conn": {"nodes": [{"id": "c"}], "pageInfo": {"hasNextPage": False, "endCursor": None}}},
    ]
    cursors = []

    def fake_gql(query, variables=None):
        cursors.append(variables.get("after"))
        return pages[len(cursors) - 1]

    monkeypatch.setattr(mod, "gql", fake_gql)
    out = mod._paginate("q", ["conn"])
    assert [n["id"] for n in out] == ["a", "b", "c"]
    assert cursors == [None, "c1", "c2"]  # first page sends no cursor, then follows endCursor


def test_paginate_stops_on_repeated_cursor(mod, monkeypatch):
    # Defensive: a server that keeps returning hasNextPage with the same cursor
    # must not loop forever.
    def fake_gql(query, variables=None):
        return {"conn": {"nodes": [{"id": "x"}], "pageInfo": {"hasNextPage": True, "endCursor": "stuck"}}}

    monkeypatch.setattr(mod, "gql", fake_gql)
    out = mod._paginate("q", ["conn"])
    assert [n["id"] for n in out] == ["x", "x"]  # one extra page, then bails on repeat


# ---------- _label_tokens ----------

def test_label_tokens_flattens_repeats_and_commas(mod):
    assert mod._label_tokens(["bug", "p1,p2", " spaced "]) == ["bug", "p1", "p2", "spaced"]
    assert mod._label_tokens(None) == []
    assert mod._label_tokens([" , "]) == []


# ---------- _find_labels ----------

def test_find_labels_exact_and_case_and_trim(mod, fake):
    fake.labels = [{"id": "l1", "name": "Bug"}, {"id": "l2", "name": "Feature"}]
    assert [m["id"] for m in mod._find_labels("  bUg ")] == ["l1"]


def test_find_labels_blank_or_missing(mod, fake):
    fake.labels = [{"id": "l1", "name": "Bug"}]
    assert mod._find_labels("") == []
    assert mod._find_labels("nope") == []


def test_find_labels_skips_null_name(mod, fake):
    fake.labels = [{"id": "l1", "name": None}, {"id": "l2", "name": "Bug"}]
    assert [m["id"] for m in mod._find_labels("Bug")] == ["l2"]


def test_find_labels_team_scoped_passes_team_id(mod, fake):
    fake.labels = [{"id": "l1", "name": "Bug"}]
    mod._find_labels("Bug", "team-9")
    assert any(v and v.get("teamId") == "team-9" for _, v in fake.calls)


def test_find_labels_returns_all_matches(mod, fake):
    fake.labels = [{"id": "l1", "name": "Bug"}, {"id": "l2", "name": "bug"}]
    assert {m["id"] for m in mod._find_labels("bug")} == {"l1", "l2"}


# ---------- _find_users ----------

def test_find_users_by_name_display_email_localpart(mod, fake):
    fake.users = [
        user("u1", name="John Doe", email="john@x.com"),
        user("u2", display="Janie", email="jane@acme.com"),
    ]
    assert [m["id"] for m in mod._find_users("john doe")] == ["u1"]
    assert [m["id"] for m in mod._find_users("janie")] == ["u2"]
    assert [m["id"] for m in mod._find_users("jane@acme.com")] == ["u2"]
    assert [m["id"] for m in mod._find_users("jane")] == ["u2"]  # email local-part


def test_find_users_includes_inactive_and_blank(mod, fake):
    fake.users = [user("u1", name="Ghost", active=False)]
    assert [m["id"] for m in mod._find_users("Ghost")] == ["u1"]
    assert mod._find_users("  ") == []


# ---------- create-issue ----------

def test_create_issue_single_label_and_assignee(mod, fake):
    fake.teams = [{"id": "team-1", "key": "ENG", "name": "Engineering"}]
    fake.labels = [{"id": "l1", "name": "Bug"}]
    fake.users = [user("u1", name="John Doe", email="j@x.com")]
    mod.cmd_create_issue(ns(team="ENG", title="x", label=["Bug"], assignee="John Doe"))
    assert fake.mutation_input["labelIds"] == ["l1"]
    assert fake.mutation_input["assigneeId"] == "u1"


def test_create_issue_multiple_labels_repeated_and_comma(mod, fake):
    fake.teams = [{"id": "team-1", "key": "ENG", "name": "Engineering"}]
    fake.labels = [{"id": "l1", "name": "bug"}, {"id": "l2", "name": "p1"}, {"id": "l3", "name": "ui"}]
    # repeated flag + comma-separated, with a duplicate to prove dedup
    mod.cmd_create_issue(ns(team="ENG", title="x", label=["bug", "p1,ui", "bug"]))
    assert fake.mutation_input["labelIds"] == ["l1", "l2", "l3"]


def test_create_issue_label_not_found_exits(mod, fake):
    fake.teams = [{"id": "team-1", "key": "ENG", "name": "Engineering"}]
    fake.labels = []
    with pytest.raises(SystemExit) as e:
        mod.cmd_create_issue(ns(team="ENG", title="x", label=["Ghost"]))
    assert e.value.code == 1


def test_create_issue_ambiguous_label_exits(mod, fake):
    fake.teams = [{"id": "team-1", "key": "ENG", "name": "Engineering"}]
    fake.labels = [{"id": "l1", "name": "Bug"}, {"id": "l2", "name": "Bug"}]
    with pytest.raises(SystemExit) as e:
        mod.cmd_create_issue(ns(team="ENG", title="x", label=["Bug"]))
    assert e.value.code == 1


def test_create_issue_assignee_me_uses_viewer(mod, fake):
    fake.teams = [{"id": "team-1", "key": "ENG", "name": "Engineering"}]
    fake.viewer_id = "me-123"
    mod.cmd_create_issue(ns(team="ENG", title="x", assignee="me"))
    assert fake.mutation_input["assigneeId"] == "me-123"


def test_create_issue_assignee_inactive_only_exits(mod, fake):
    fake.teams = [{"id": "team-1", "key": "ENG", "name": "Engineering"}]
    fake.users = [user("u1", name="Gone", active=False)]
    with pytest.raises(SystemExit) as e:
        mod.cmd_create_issue(ns(team="ENG", title="x", assignee="Gone"))
    assert e.value.code == 1


def test_create_issue_ambiguous_assignee_exits(mod, fake):
    fake.teams = [{"id": "team-1", "key": "ENG", "name": "Engineering"}]
    fake.users = [user("u1", name="John", active=True), user("u2", display="John", active=True)]
    with pytest.raises(SystemExit) as e:
        mod.cmd_create_issue(ns(team="ENG", title="x", assignee="John"))
    assert e.value.code == 1


# ---------- update-issue ----------

def test_update_issue_label_is_additive(mod, fake):
    fake.issue_team_id = "team-7"
    fake.issue_labels = [{"id": "old-1"}, {"id": "old-2"}]
    fake.labels = [{"id": "l1", "name": "Bug"}]
    mod.cmd_update_issue(ns(identifier="ENG-42", label=["Bug"]))
    assert fake.mutation_input["labelIds"] == ["old-1", "old-2", "l1"]


def test_update_issue_label_dedup(mod, fake):
    fake.issue_team_id = "team-7"
    fake.issue_labels = [{"id": "l1"}]
    fake.labels = [{"id": "l1", "name": "Bug"}]
    mod.cmd_update_issue(ns(identifier="ENG-42", label=["Bug"]))
    assert fake.mutation_input["labelIds"] == ["l1"]


def test_update_issue_multiple_labels_additive(mod, fake):
    fake.issue_team_id = "team-7"
    fake.issue_labels = [{"id": "old-1"}]
    fake.labels = [{"id": "l1", "name": "bug"}, {"id": "l2", "name": "p1"}]
    mod.cmd_update_issue(ns(identifier="ENG-42", label=["bug,p1"]))
    assert fake.mutation_input["labelIds"] == ["old-1", "l1", "l2"]


def test_update_issue_label_workspace_fallback(mod, fake):
    fake.issue_team_id = "team-7"
    fake.labels = []  # team-scoped miss
    fake.workspace_labels = [{"id": "l9", "name": "Bug"}]
    mod.cmd_update_issue(ns(identifier="ENG-42", label=["Bug"]))
    assert fake.mutation_input["labelIds"] == ["l9"]


def test_update_issue_ambiguous_label_exits(mod, fake):
    fake.issue_team_id = "team-7"
    fake.labels = []
    fake.workspace_labels = [{"id": "a", "name": "Bug"}, {"id": "b", "name": "Bug"}]
    with pytest.raises(SystemExit) as e:
        mod.cmd_update_issue(ns(identifier="ENG-42", label=["Bug"]))
    assert e.value.code == 1


def test_update_issue_label_not_found_exits(mod, fake):
    fake.issue_team_id = "team-7"
    fake.labels = []
    with pytest.raises(SystemExit) as e:
        mod.cmd_update_issue(ns(identifier="ENG-42", label=["Ghost"]))
    assert e.value.code == 1


def test_update_issue_explicit_team_resolves_label(mod, fake):
    fake.teams = [{"id": "team-1", "key": "ENG", "name": "Engineering"}]
    fake.labels = [{"id": "l1", "name": "Bug"}]
    mod.cmd_update_issue(ns(identifier="ENG-42", label=["Bug"], team="ENG"))
    assert fake.mutation_input["labelIds"] == ["l1"]


def test_update_issue_resolves_assignee(mod, fake):
    fake.users = [user("u1", name="Jane", email="jane@x.com")]
    mod.cmd_update_issue(ns(identifier="ENG-42", assignee="Jane"))
    assert fake.mutation_input["assigneeId"] == "u1"


def test_update_issue_assignee_me(mod, fake):
    fake.viewer_id = "me-9"
    mod.cmd_update_issue(ns(identifier="ENG-42", assignee="me"))
    assert fake.mutation_input["assigneeId"] == "me-9"


def test_update_issue_assignee_inactive_only_exits(mod, fake):
    fake.users = [user("u1", name="Gone", active=False)]
    with pytest.raises(SystemExit) as e:
        mod.cmd_update_issue(ns(identifier="ENG-42", assignee="Gone"))
    assert e.value.code == 1


def test_update_issue_no_fields_exits(mod, fake):
    with pytest.raises(SystemExit) as e:
        mod.cmd_update_issue(ns(identifier="ENG-42"))
    assert e.value.code == 1
