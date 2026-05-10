"""Tests for Discord exec-approval command summaries."""

from gateway.platforms import discord as discord_adapter


def test_summarize_git_reset_hard_names_discarded_state():
    summary = discord_adapter._summarize_command_change("git reset --hard origin/main")

    assert "Reset local Git worktree/index to `origin/main`" in summary
    assert "discarding uncommitted changes" in summary


def test_summarize_branch_delete_lists_targets():
    summary = discord_adapter._summarize_command_change("git branch -D old-feature tmp/test")

    assert "Force-delete local Git branch(es): `old-feature`, `tmp/test`" in summary


def test_summarize_rm_lists_filesystem_targets():
    summary = discord_adapter._summarize_command_target("rm -rf build dist", "/tmp/project")

    assert "Filesystem path(s): `build`, `dist`" in summary


def test_summarize_git_reset_uses_workdir_when_provided():
    summary = discord_adapter._summarize_command_target("git reset --hard", "/tmp/project")

    assert "Git working tree and index in `/tmp/project`" in summary


def test_discord_field_value_truncates_to_embed_limit():
    value = discord_adapter._discord_field_value("x" * 1100, limit=20)

    assert len(value) == 20
    assert value.endswith("...")


def test_inline_code_escapes_backticks_and_mentions():
    value = discord_adapter._discord_inline_code("danger` @everyone")

    assert value == "`dangerˋ @\u200beveryone`"
