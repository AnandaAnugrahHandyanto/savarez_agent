"""Tests for CLI /goal review and accept command branches."""

from unittest.mock import MagicMock, patch

from cli import HermesCLI


def _make_cli() -> HermesCLI:
    cli_obj = HermesCLI.__new__(HermesCLI)
    cli_obj.config = {}
    cli_obj.console = MagicMock()
    cli_obj.agent = None
    cli_obj.conversation_history = []
    cli_obj.session_id = "cli-goal-review-test"
    cli_obj._pending_input = MagicMock()
    cli_obj._app = None
    return cli_obj


def test_goal_review_preview_and_accept_cli_branches(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))

    from hermes_cli import goals
    from hermes_cli.goals import GoalManager, save_goal

    goals._DB_CACHE.clear()
    try:
        mgr = GoalManager(session_id="cli-goal-review-test")
        mgr.set("Implement Hermes /goal Mads review gate")
        mgr.pause("mads-review-recommended:before_done")
        assert mgr.state is not None
        mgr.state.review_recommended_reason = "before_done"
        save_goal("cli-goal-review-test", mgr.state)

        cli_obj = _make_cli()
        with patch("cli._cprint") as cprint:
            assert cli_obj.process_command("/goal review") is True
        rendered = "\n".join(str(call.args[0]) for call in cprint.call_args_list)
        assert "Mads review packet" in rendered
        assert "Read-only review" in rendered

        with patch("cli._cprint") as cprint:
            assert cli_obj.process_command("/goal accept") is True
        rendered = "\n".join(str(call.args[0]) for call in cprint.call_args_list)
        assert "Goal accepted" in rendered

        accepted = GoalManager(session_id="cli-goal-review-test").state
        assert accepted is not None
        assert accepted.status == "done"
        assert accepted.last_verdict == "done"
    finally:
        goals._DB_CACHE.clear()
