"""Tests for GitHub metadata sync."""

from __future__ import annotations


class _FakeClient:
    def __init__(self):
        self.calls = []

    def list_paginated(self, path, params=None):
        self.calls.append((path, params or {}))
        if path == "/installation/repositories":
            return [
                {
                    "id": 101,
                    "full_name": "nous/hermes",
                    "owner": {"login": "nous"},
                    "name": "hermes",
                    "default_branch": "main",
                    "private": True,
                    "html_url": "https://github.com/nous/hermes",
                    "clone_url": "https://github.com/nous/hermes.git",
                    "ssh_url": "git@github.com:nous/hermes.git",
                    "archived": False,
                    "disabled": False,
                    "pushed_at": "2026-04-01T00:00:00Z",
                }
            ]
        if path == "/repos/nous/hermes/issues":
            return [
                {
                    "id": 201,
                    "number": 1,
                    "title": "Bug",
                    "state": "open",
                    "user": {"login": "octo"},
                    "labels": [{"name": "bug"}],
                    "assignees": [],
                    "milestone": None,
                    "html_url": "https://github.com/nous/hermes/issues/1",
                    "created_at": "2026-04-01T00:00:00Z",
                    "updated_at": "2026-04-02T00:00:00Z",
                },
                {"id": 202, "pull_request": {"url": "skip"}},
            ]
        if path == "/repos/nous/hermes/pulls":
            return [
                {
                    "id": 301,
                    "number": 2,
                    "title": "PR",
                    "state": "open",
                    "user": {"login": "octo"},
                    "base": {"ref": "main"},
                    "head": {"ref": "feature", "sha": "abc123"},
                    "mergeable": True,
                    "draft": False,
                    "html_url": "https://github.com/nous/hermes/pull/2",
                    "created_at": "2026-04-01T00:00:00Z",
                    "updated_at": "2026-04-02T00:00:00Z",
                }
            ]
        if path == "/repos/nous/hermes/branches":
            return [{"name": "main", "commit": {"sha": "abc123"}, "protected": True}]
        return []


def test_repository_sync_dry_run(tmp_path):
    from hermes_cli.code.github_sync import GitHubSyncService

    result = GitHubSyncService(db_path=tmp_path / "state.db", api_client=_FakeClient()).sync_repositories(
        dry_run=True
    )

    assert result["dry_run"] is True
    assert result["repositories"][0]["full_name"] == "nous/hermes"


def test_repository_issue_pr_and_branch_sync(tmp_path):
    from hermes_cli.code.github_integration import GitHubIntegrationDB
    from hermes_cli.code.github_sync import GitHubSyncService

    db_path = tmp_path / "state.db"
    sync = GitHubSyncService(db_path=db_path, api_client=_FakeClient())

    repos = sync.sync_repositories(dry_run=False)
    issues = sync.sync_issues("nous/hermes")
    pulls = sync.sync_pull_requests("nous/hermes")
    branches = sync.sync_branches("nous/hermes")

    assert repos["synced"] == 1
    assert issues["synced"] == 1
    assert pulls["synced"] == 1
    assert branches["synced"] == 1

    db = GitHubIntegrationDB(db_path=db_path)
    try:
        assert db.get_repository("nous", "hermes")["full_name"] == "nous/hermes"
        assert db.list_issues("nous/hermes")[0]["number"] == 1
        assert db.list_pull_requests("nous/hermes")[0]["number"] == 2
    finally:
        db.close()


def test_pagination_client_called_with_expected_paths(tmp_path):
    from hermes_cli.code.github_sync import GitHubSyncService

    client = _FakeClient()
    sync = GitHubSyncService(db_path=tmp_path / "state.db", api_client=client)
    sync.sync_repositories()
    sync.sync_issues("nous/hermes")

    assert ("/installation/repositories", {}) in client.calls
    assert any(call[0] == "/repos/nous/hermes/issues" for call in client.calls)
