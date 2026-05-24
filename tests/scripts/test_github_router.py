from __future__ import annotations

import json

from scripts import github_router as gr


class FakeGH:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def api(self, path: str, *, method: str = "GET", fields=None):
        self.calls.append((method, path, fields or {}))
        key = (method, path)
        if key not in self.responses:
            raise AssertionError(f"unexpected gh api call: {method} {path}")
        value = self.responses[key]
        return value() if callable(value) else value


def test_parse_repos_from_json_config():
    repos = gr.parse_repos_from_env(
        {
            "HERMES_GITHUB_ROUTER_CONFIG": json.dumps(
                {
                    "board": "deepwork",
                    "assignee": "worker",
                    "repos": [
                        {"full_name": "owner/repo", "workspace": "/tmp/repo", "skills": ["github-pr-workflow"]}
                    ],
                }
            )
        }
    )

    assert repos == [
        gr.RepoConfig(
            owner="owner",
            repo="repo",
            workspace="/tmp/repo",
            board="deepwork",
            assignee="worker",
            skills=("github-pr-workflow",),
        )
    ]


def test_parse_dependencies_accepts_depends_on_and_blocked_by():
    assert gr.parse_dependencies("Depends on: #12\nBlocked by: #34, #56\nother #99") == {12, 34, 56}


def test_create_queue_task_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    repo = gr.RepoConfig("owner", "repo", str(tmp_path / "repo"), board="board", max_runtime="90s")

    first = gr.create_queue_task(repo, title="task", body="body", key="owner/repo:issue:1:work")
    second = gr.create_queue_task(repo, title="task", body="body", key="owner/repo:issue:1:work")

    assert first.created is True
    assert second.created is False
    assert second.task_id == first.task_id


def test_issue_work_creates_task_and_tracking_comment(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    repo = gr.RepoConfig("owner", "repo", str(tmp_path / "repo"), board="board", max_runtime="90s")
    issue = {
        "number": 7,
        "title": "Add thing",
        "html_url": "https://github.com/owner/repo/issues/7",
        "labels": [{"name": gr.WORK_LABEL}],
    }
    gh = FakeGH(
        {
            ("GET", "repos/owner/repo/issues?state=open&labels=snowman:work&per_page=100"): [issue],
            ("GET", "repos/owner/repo/issues/7/comments?per_page=100"): [],
            ("POST", "repos/owner/repo/issues/7/comments"): {},
        }
    )

    created = gr.scan_issue_work(gh, repo)

    assert len(created) == 1
    assert "issue #7" in created[0]
    post = gh.calls[-1]
    assert post[0] == "POST"
    assert "owner/repo:issue:7:work" in post[2]["body"]


def test_pr_review_skips_when_checks_are_pending(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    repo = gr.RepoConfig("owner", "repo", str(tmp_path / "repo"), board="board")
    pr = {
        "number": 3,
        "title": "Change",
        "draft": False,
        "html_url": "https://github.com/owner/repo/pull/3",
        "labels": [{"name": gr.REVIEW_LABEL}],
        "head": {"sha": "abc123"},
    }
    gh = FakeGH(
        {
            ("GET", "repos/owner/repo/pulls?state=open&per_page=100"): [pr],
            ("GET", "repos/owner/repo/commits/abc123/check-runs"): {
                "check_runs": [{"status": "in_progress", "conclusion": None}]
            },
        }
    )

    assert gr.scan_pr_review(gh, repo) == []
    assert all(call[0] != "POST" for call in gh.calls)


def test_run_isolates_lane_failures(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    repo = gr.RepoConfig("owner", "repo", str(tmp_path / "repo"), board="board")
    gh = FakeGH({})

    created, errors = gr.run([repo], gh=gh)

    assert created == []
    assert len(errors) == 4
    assert all("owner/repo" in error for error in errors)
