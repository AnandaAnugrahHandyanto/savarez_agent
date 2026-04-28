"""Tests for GitHub ChatOps command parsing and run creation."""

from __future__ import annotations


def test_parse_plan_review_fix_explain_status():
    from hermes_cli.code.github_chatops import parse_chatops_commands

    text = """
    @hermes plan a safe implementation
    @hermes review
    @hermes fix failing tests
    @hermes explain this module
    @hermes status
    """
    commands = parse_chatops_commands(text)

    assert [c.command for c in commands] == ["plan", "review", "fix", "explain", "status"]
    assert commands[0].args == "a safe implementation"


def test_non_hermes_comment_ignored():
    from hermes_cli.code.github_chatops import parse_chatops_commands

    assert parse_chatops_commands("please plan this") == []


def test_command_links_context_and_creates_run_and_artifact(tmp_path):
    from hermes_cli.code.github_chatops import GitHubChatOpsService
    from hermes_cli.code.github_integration import GitHubIntegrationDB
    from hermes_cli.code.artifact_ledger import ArtifactLedger

    db_path = tmp_path / "state.db"
    db = GitHubIntegrationDB(db_path=db_path)
    command = db.create_chatops_command(
        delivery_id="delivery-1",
        repo_full_name="nous/hermes",
        issue_number=7,
        pr_number=7,
        comment_id=123,
        sender_login="octo",
        command="plan",
        args="build the thing",
    )
    db.close()

    result = GitHubChatOpsService(db_path=db_path).run_command(command["id"])

    assert result["command"]["repo_full_name"] == "nous/hermes"
    assert result["command"]["issue_number"] == 7
    assert result["run"]["id"]
    assert result["command"]["orchestrated_run_id"] == result["run"]["id"]
    artifacts = ArtifactLedger(db_path=db_path).list_artifacts(
        orchestrated_run_id=result["run"]["id"],
        category="task_intake",
    )
    assert len(artifacts) >= 1


def test_fix_command_stops_at_approval(tmp_path):
    from hermes_cli.code.github_chatops import GitHubChatOpsService
    from hermes_cli.code.github_integration import GitHubIntegrationDB

    db_path = tmp_path / "state.db"
    db = GitHubIntegrationDB(db_path=db_path)
    command = db.create_chatops_command(
        delivery_id="delivery-2",
        repo_full_name="nous/hermes",
        issue_number=8,
        pr_number=None,
        comment_id=124,
        sender_login="octo",
        command="fix",
        args="make tests pass",
    )
    db.close()

    result = GitHubChatOpsService(db_path=db_path).run_command(command["id"])

    assert result["run"]["state"] == "approval"
