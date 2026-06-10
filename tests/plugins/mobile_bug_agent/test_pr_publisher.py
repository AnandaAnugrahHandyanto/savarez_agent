from __future__ import annotations

import subprocess

import pytest

from plugins.mobile_bug_agent.pr_publisher import DraftPrPublisher, DraftPrPublisherError


VALID_PR_BODY = """## Links
- Linear: https://linear.app/acme/issue/MOB-42
- Slack: https://example.slack.com/archives/C_MOBILE/p1710000000000200

## Verification
Verification passed.

## Proof
- /tmp/monica-proof/screenshot.png
"""


def _mark_git_worktree(path):
    (path / ".git").write_text("gitdir: /tmp/fake-mobile-worktree-git-dir", encoding="utf-8")
    return path


def test_publisher_commits_pushes_and_creates_draft_pr(tmp_path):
    calls = []

    def run_command(args, cwd=None):
        calls.append((args, cwd))
        if args == ["git", "branch", "--show-current"]:
            return "monica/MOB-42-checkout-crash\n"
        if args == ["git", "status", "--porcelain"]:
            return " M src/Checkout.tsx\n"
        if args[:3] == ["git", "diff", "--name-only"]:
            return "src/Checkout.tsx\n"
        if args[:4] == ["gh", "pr", "create", "--draft"]:
            return "https://github.com/acme/mobile/pull/123\n"
        return ""

    publisher = DraftPrPublisher(run_command=run_command)

    url = publisher.publish(
        worktree=_mark_git_worktree(tmp_path),
        branch_name="monica/MOB-42-checkout-crash",
        base_branch="main",
        title="[MOB-42] Fix Android checkout crash",
        body=VALID_PR_BODY,
    )

    assert url == "https://github.com/acme/mobile/pull/123"
    assert calls[0][0] == ["git", "branch", "--show-current"]
    assert calls[1][0] == ["git", "status", "--porcelain"]
    assert calls[2][0] == ["git", "add", "-A"]
    assert calls[3][0] == [
        "git",
        "-c",
        "user.name=Monica",
        "-c",
        "user.email=monica@hermes.local",
        "commit",
        "-m",
        "[MOB-42] Fix Android checkout crash",
    ]
    assert calls[4][0] == ["git", "diff", "--name-only", "origin/main...HEAD"]
    assert calls[5][0] == ["git", "push", "origin", "HEAD:monica/MOB-42-checkout-crash"]
    assert calls[6][0][:4] == ["gh", "pr", "create", "--draft"]
    assert calls[6][1] == tmp_path


def test_publisher_refuses_noop_draft_pr(tmp_path):
    calls = []

    def run_command(args, cwd=None):
        calls.append((args, cwd))
        if args == ["git", "branch", "--show-current"]:
            return "monica/MOB-42-checkout-crash\n"
        if args == ["git", "status", "--porcelain"]:
            return ""
        if args[:3] == ["git", "diff", "--name-only"]:
            return ""
        return ""

    publisher = DraftPrPublisher(run_command=run_command)

    with pytest.raises(DraftPrPublisherError, match="No committed changes"):
        publisher.publish(
            worktree=_mark_git_worktree(tmp_path),
            branch_name="monica/MOB-42-checkout-crash",
            base_branch="main",
            title="[MOB-42] Fix Android checkout crash",
            body=VALID_PR_BODY,
        )

    assert [call[0][0:2] for call in calls] == [
        ["git", "branch"],
        ["git", "status"],
        ["git", "diff"],
    ]


def test_publisher_requires_branch_before_running_commands(tmp_path):
    calls = []

    def run_command(args, cwd=None):
        calls.append((args, cwd))
        return ""

    publisher = DraftPrPublisher(run_command=run_command)

    with pytest.raises(DraftPrPublisherError, match="branch_name is required"):
        publisher.publish(
            worktree=tmp_path,
            branch_name="",
            base_branch="main",
            title="[MOB-42] Fix Android checkout crash",
            body=VALID_PR_BODY,
        )

    assert calls == []


def test_publisher_requires_title_before_running_commands(tmp_path):
    calls = []

    def run_command(args, cwd=None):
        calls.append((args, cwd))
        return ""

    publisher = DraftPrPublisher(run_command=run_command)

    with pytest.raises(DraftPrPublisherError, match="title is required"):
        publisher.publish(
            worktree=tmp_path,
            branch_name="monica/MOB-42-checkout-crash",
            base_branch="main",
            title="   ",
            body=VALID_PR_BODY,
        )

    assert calls == []


def test_publisher_requires_body_before_running_commands(tmp_path):
    calls = []

    def run_command(args, cwd=None):
        calls.append((args, cwd))
        return ""

    publisher = DraftPrPublisher(run_command=run_command)

    with pytest.raises(DraftPrPublisherError, match="body is required"):
        publisher.publish(
            worktree=tmp_path,
            branch_name="monica/MOB-42-checkout-crash",
            base_branch="main",
            title="[MOB-42] Fix Android checkout crash",
            body="",
        )

    assert calls == []


def test_publisher_requires_linear_reference_before_running_commands(tmp_path):
    calls = []

    def run_command(args, cwd=None):
        calls.append((args, cwd))
        return ""

    publisher = DraftPrPublisher(run_command=run_command)

    with pytest.raises(DraftPrPublisherError, match="body must include Linear"):
        publisher.publish(
            worktree=tmp_path,
            branch_name="monica/MOB-42-checkout-crash",
            base_branch="main",
            title="[MOB-42] Fix Android checkout crash",
            body="""## Links
- Slack: https://example.slack.com/archives/C_MOBILE/p1710000000000200

## Verification
Verification passed.
""",
        )

    assert calls == []


def test_publisher_requires_slack_reference_before_running_commands(tmp_path):
    calls = []

    def run_command(args, cwd=None):
        calls.append((args, cwd))
        return ""

    publisher = DraftPrPublisher(run_command=run_command)

    with pytest.raises(DraftPrPublisherError, match="body must include Slack"):
        publisher.publish(
            worktree=tmp_path,
            branch_name="monica/MOB-42-checkout-crash",
            base_branch="main",
            title="[MOB-42] Fix Android checkout crash",
            body="""## Links
- Linear: https://linear.app/acme/issue/MOB-42

## Verification
Verification passed.
""",
        )

    assert calls == []


def test_publisher_requires_verification_evidence_before_running_commands(tmp_path):
    calls = []

    def run_command(args, cwd=None):
        calls.append((args, cwd))
        return ""

    publisher = DraftPrPublisher(run_command=run_command)

    with pytest.raises(DraftPrPublisherError, match="body must include verification"):
        publisher.publish(
            worktree=tmp_path,
            branch_name="monica/MOB-42-checkout-crash",
            base_branch="main",
            title="[MOB-42] Fix Android checkout crash",
            body="""## Links
- Linear: https://linear.app/acme/issue/MOB-42
- Slack: https://example.slack.com/archives/C_MOBILE/p1710000000000200
""",
        )

    assert calls == []


def test_publisher_requires_proof_evidence_before_running_commands(tmp_path):
    calls = []

    def run_command(args, cwd=None):
        calls.append((args, cwd))
        return ""

    publisher = DraftPrPublisher(run_command=run_command)

    with pytest.raises(DraftPrPublisherError, match="body must include proof"):
        publisher.publish(
            worktree=tmp_path,
            branch_name="monica/MOB-42-checkout-crash",
            base_branch="main",
            title="[MOB-42] Fix Android checkout crash",
            body="""## Links
- Linear: https://linear.app/acme/issue/MOB-42
- Slack: https://example.slack.com/archives/C_MOBILE/p1710000000000200

## Verification
Verification passed.
""",
        )

    assert calls == []


def test_publisher_accepts_fenced_verification_output(tmp_path):
    calls = []

    def run_command(args, cwd=None):
        calls.append((args, cwd))
        if args == ["git", "branch", "--show-current"]:
            return "monica/MOB-42-checkout-crash\n"
        if args == ["git", "status", "--porcelain"]:
            return ""
        if args[:3] == ["git", "diff", "--name-only"]:
            return "src/Checkout.tsx\n"
        if args[:4] == ["gh", "pr", "create", "--draft"]:
            return "https://github.com/acme/mobile/pull/123\n"
        return ""

    publisher = DraftPrPublisher(run_command=run_command)

    url = publisher.publish(
        worktree=_mark_git_worktree(tmp_path),
        branch_name="monica/MOB-42-checkout-crash",
        base_branch="main",
        title="[MOB-42] Fix Android checkout crash",
        body="""## Links
- Linear: https://linear.app/acme/issue/MOB-42
- Slack: https://example.slack.com/archives/C_MOBILE/p1710000000000200

## Verification

```
$ npm test
ok
```

## Proof
- /tmp/monica-proof/screenshot.png
""",
    )

    assert url == "https://github.com/acme/mobile/pull/123"
    assert calls[0][0] == ["git", "branch", "--show-current"]


def test_publisher_rejects_unsafe_base_branch_before_running_commands(tmp_path):
    calls = []

    def run_command(args, cwd=None):
        calls.append((args, cwd))
        return ""

    publisher = DraftPrPublisher(run_command=run_command)

    with pytest.raises(DraftPrPublisherError, match="base_branch must be a safe git branch name"):
        publisher.publish(
            worktree=tmp_path,
            branch_name="monica/MOB-42-checkout-crash",
            base_branch="../main",
            title="[MOB-42] Fix Android checkout crash",
            body=VALID_PR_BODY,
        )

    assert calls == []


def test_publisher_rejects_unsafe_head_branch_before_running_commands(tmp_path):
    calls = []

    def run_command(args, cwd=None):
        calls.append((args, cwd))
        return ""

    publisher = DraftPrPublisher(run_command=run_command)

    with pytest.raises(DraftPrPublisherError, match="branch_name must be a safe git branch name"):
        publisher.publish(
            worktree=tmp_path,
            branch_name="../monica/MOB-42",
            base_branch="main",
            title="[MOB-42] Fix Android checkout crash",
            body=VALID_PR_BODY,
        )

    assert calls == []


def test_publisher_requires_existing_worktree_before_running_commands(tmp_path):
    calls = []

    def run_command(args, cwd=None):
        calls.append((args, cwd))
        return ""

    publisher = DraftPrPublisher(run_command=run_command)

    with pytest.raises(DraftPrPublisherError, match="worktree does not exist"):
        publisher.publish(
            worktree=tmp_path / "missing-worktree",
            branch_name="monica/MOB-42-checkout-crash",
            base_branch="main",
            title="[MOB-42] Fix Android checkout crash",
            body=VALID_PR_BODY,
        )

    assert calls == []


def test_publisher_requires_git_worktree_before_running_commands(tmp_path):
    calls = []

    def run_command(args, cwd=None):
        calls.append((args, cwd))
        if args == ["git", "branch", "--show-current"]:
            return "monica/MOB-42-checkout-crash\n"
        if args == ["git", "status", "--porcelain"]:
            return ""
        if args[:3] == ["git", "diff", "--name-only"]:
            return "src/Checkout.tsx\n"
        if args[:4] == ["gh", "pr", "create", "--draft"]:
            return "https://github.com/acme/mobile/pull/123\n"
        return ""

    publisher = DraftPrPublisher(run_command=run_command)

    with pytest.raises(DraftPrPublisherError, match="worktree is not a git worktree"):
        publisher.publish(
            worktree=tmp_path,
            branch_name="monica/MOB-42-checkout-crash",
            base_branch="main",
            title="[MOB-42] Fix Android checkout crash",
            body=VALID_PR_BODY,
        )

    assert calls == []


def test_publisher_refuses_worktree_on_unexpected_branch(tmp_path):
    calls = []

    def run_command(args, cwd=None):
        calls.append((args, cwd))
        if args == ["git", "branch", "--show-current"]:
            return "main\n"
        return ""

    publisher = DraftPrPublisher(run_command=run_command)

    with pytest.raises(DraftPrPublisherError, match="worktree branch mismatch"):
        publisher.publish(
            worktree=_mark_git_worktree(tmp_path),
            branch_name="monica/MOB-42-checkout-crash",
            base_branch="main",
            title="[MOB-42] Fix Android checkout crash",
            body=VALID_PR_BODY,
        )

    assert calls == [(["git", "branch", "--show-current"], tmp_path)]


def test_publisher_uses_existing_committed_diff_without_empty_commit(tmp_path):
    calls = []

    def run_command(args, cwd=None):
        calls.append((args, cwd))
        if args == ["git", "branch", "--show-current"]:
            return "monica/MOB-42-checkout-crash\n"
        if args == ["git", "status", "--porcelain"]:
            return ""
        if args[:3] == ["git", "diff", "--name-only"]:
            return "src/Checkout.tsx\n"
        if args[:4] == ["gh", "pr", "create", "--draft"]:
            return "https://github.com/acme/mobile/pull/123\n"
        return ""

    publisher = DraftPrPublisher(run_command=run_command)

    url = publisher.publish(
        worktree=_mark_git_worktree(tmp_path),
        branch_name="monica/MOB-42-checkout-crash",
        base_branch="main",
        title="[MOB-42] Fix Android checkout crash",
        body=VALID_PR_BODY,
    )

    assert url == "https://github.com/acme/mobile/pull/123"
    assert not any("commit" in call[0] for call in calls)
    assert calls[3][0] == ["git", "push", "origin", "HEAD:monica/MOB-42-checkout-crash"]


def test_publisher_recovers_existing_pr_url_from_gh_create_error(tmp_path):
    calls = []

    def run_command(args, cwd=None):
        calls.append((args, cwd))
        if args == ["git", "branch", "--show-current"]:
            return "monica/MOB-42-checkout-crash\n"
        if args == ["git", "status", "--porcelain"]:
            return ""
        if args[:3] == ["git", "diff", "--name-only"]:
            return "src/Checkout.tsx\n"
        if args[:4] == ["gh", "pr", "create", "--draft"]:
            raise DraftPrPublisherError(
                "command failed (1): gh pr create --draft\n"
                "stderr: a pull request already exists for this branch: "
                "https://github.com/acme/mobile/pull/456"
            )
        return ""

    publisher = DraftPrPublisher(run_command=run_command)

    url = publisher.publish(
        worktree=_mark_git_worktree(tmp_path),
        branch_name="monica/MOB-42-checkout-crash",
        base_branch="main",
        title="[MOB-42] Fix Android checkout crash",
        body=VALID_PR_BODY,
    )

    assert url == "https://github.com/acme/mobile/pull/456"
    assert calls[-1][0][:4] == ["gh", "pr", "create", "--draft"]


def test_publisher_strips_punctuation_from_recovered_pr_url(tmp_path):
    calls = []

    def run_command(args, cwd=None):
        calls.append((args, cwd))
        if args == ["git", "branch", "--show-current"]:
            return "monica/MOB-42-checkout-crash\n"
        if args == ["git", "status", "--porcelain"]:
            return ""
        if args[:3] == ["git", "diff", "--name-only"]:
            return "src/Checkout.tsx\n"
        if args[:4] == ["gh", "pr", "create", "--draft"]:
            raise DraftPrPublisherError(
                "stderr: a pull request already exists for this branch "
                "(https://github.com/acme/mobile/pull/456)."
            )
        return ""

    publisher = DraftPrPublisher(run_command=run_command)

    url = publisher.publish(
        worktree=_mark_git_worktree(tmp_path),
        branch_name="monica/MOB-42-checkout-crash",
        base_branch="main",
        title="[MOB-42] Fix Android checkout crash",
        body=VALID_PR_BODY,
    )

    assert url == "https://github.com/acme/mobile/pull/456"


def test_publisher_missing_executable_raises_typed_error(tmp_path, monkeypatch):
    def missing_run(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("gh")

    monkeypatch.setattr(subprocess, "run", missing_run)
    publisher = DraftPrPublisher()

    with pytest.raises(DraftPrPublisherError, match="executable not found: gh"):
        publisher._default_run(["gh", "pr", "create"], tmp_path)


def test_publisher_nonzero_exit_includes_command_context(tmp_path, monkeypatch):
    def failed_run(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["gh", "pr", "create"],
            returncode=1,
            stdout="stdout detail",
            stderr="stderr detail",
        )

    monkeypatch.setattr(subprocess, "run", failed_run)
    publisher = DraftPrPublisher()

    with pytest.raises(DraftPrPublisherError) as exc_info:
        publisher._default_run(["gh", "pr", "create"], tmp_path)

    message = str(exc_info.value)
    assert "command failed (1): gh pr create" in message
    assert f"cwd: {tmp_path}" in message
    assert "stdout: stdout detail" in message
    assert "stderr: stderr detail" in message
