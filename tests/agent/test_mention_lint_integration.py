"""Integration tests for mention-lint guardrails wired into write paths.

Exercises the three integration sites:
* tools.cronjob_tools.cronjob(action="create") and update
* tools.skill_manager_tool.skill_manage(action=create/edit/patch/write_file)
* plugins.platforms.discord.adapter.DiscordAdapter.format_message

The cron + skill paths must HARD-REJECT malformed mentions. The Discord
adapter path must WARN-AND-PASS — the content sails through unmodified
and a structured warning is emitted.

See agent/mention_lint.py and writer_ai#125.
"""

from __future__ import annotations

import json
import logging

import pytest


# ─────────────────────────────────────────────────────────────────────
# Cron: HARD REJECT on create
# ─────────────────────────────────────────────────────────────────────

def test_cron_create_rejects_asterisk_mention_in_prompt():
    from tools.cronjob_tools import cronjob

    result = json.loads(cronjob(
        action="create",
        prompt="Daily standup. Ping <@***> Fury at 9am ET with status.",
        schedule="0 9 * * *",
        name="standup-ping",
    ))
    assert result["success"] is False
    assert "Malformed Discord mention" in result["error"]
    assert "cron prompt" in result["error"]


def test_cron_create_accepts_valid_mention():
    from tools.cronjob_tools import cronjob

    # Use a unique name so the test is idempotent.
    result = json.loads(cronjob(
        action="create",
        prompt="Daily standup. Ping <@1508199506150166658> Fury at 9am ET.",
        schedule="0 9 * * *",
        name="mention-lint-valid-test",
    ))
    assert result["success"] is True
    # Clean up.
    cronjob(action="remove", job_id=result["job_id"])


def test_cron_update_rejects_role_mention_in_prompt():
    from tools.cronjob_tools import cronjob

    # Create a clean job we can attempt to update.
    create_res = json.loads(cronjob(
        action="create",
        prompt="placeholder body for update test",
        schedule="0 9 * * *",
        name="mention-lint-update-test",
    ))
    assert create_res["success"] is True
    job_id = create_res["job_id"]
    try:
        update_res = json.loads(cronjob(
            action="update",
            job_id=job_id,
            prompt="Ping <@&1508199352898814126> with status update.",
        ))
        assert update_res["success"] is False
        assert "Malformed Discord mention" in update_res["error"]
        assert "role_mention" in update_res["error"]
    finally:
        cronjob(action="remove", job_id=job_id)


# ─────────────────────────────────────────────────────────────────────
# skill_manage: HARD REJECT on create / edit / patch / write_file
# ─────────────────────────────────────────────────────────────────────

_VALID_SKILL_CONTENT = """---
name: mention-lint-fixture
description: Test fixture for mention-lint integration tests.
---

# Mention Lint Fixture

This skill exists to verify that mention-lint blocks malformed
Discord mention IDs at skill_manage create/edit/patch/write_file.
"""


def test_skill_manage_create_rejects_asterisk_mention():
    from tools.skill_manager_tool import skill_manage

    bad_content = _VALID_SKILL_CONTENT + "\n\nPing <@***> Fury.\n"
    result = json.loads(skill_manage(
        action="create",
        name="mention-lint-fixture-bad",
        content=bad_content,
    ))
    assert result["success"] is False
    assert "Malformed Discord mention" in result["error"]
    assert "SKILL.md" in result["error"]


def test_skill_manage_patch_rejects_malformed_new_string():
    from tools.skill_manager_tool import skill_manage

    # We don't need the patch to find a target; the lint runs BEFORE
    # patch application, so the rejection fires regardless of whether
    # the skill exists. Use a clearly non-existent skill name to keep
    # the test hermetic.
    result = json.loads(skill_manage(
        action="patch",
        name="this-skill-does-not-exist-12345",
        old_string="placeholder",
        new_string="Cc <@bot_id> on this channel.",
    ))
    assert result["success"] is False
    assert "Malformed Discord mention" in result["error"]


# ─────────────────────────────────────────────────────────────────────
# Discord adapter: WARN-AND-PASS on outbound format_message
# ─────────────────────────────────────────────────────────────────────

def test_discord_adapter_warn_and_pass_on_malformed_mention(caplog):
    pytest.importorskip("discord")
    from plugins.platforms.discord.adapter import DiscordAdapter

    # Construct an adapter without actually connecting. format_message
    # is a pure transformation that doesn't touch self._client.
    adapter = DiscordAdapter.__new__(DiscordAdapter)

    payload = "Heads up <@***> Fury — see attached."
    with caplog.at_level(logging.WARNING, logger="plugins.platforms.discord.adapter"):
        out = adapter.format_message(payload)

    # Content must NOT be rewritten. Silent rewriting is the bug we're
    # fixing.
    assert out == payload

    # A structured warning must have been logged.
    warning_records = [
        r for r in caplog.records
        if r.levelno == logging.WARNING and "malformed mention" in r.getMessage()
    ]
    assert warning_records, "Expected a warn-and-pass log for the malformed mention"
    assert "<@***>" in warning_records[0].getMessage()


def test_discord_adapter_allows_role_mentions_in_outbound():
    pytest.importorskip("discord")
    from plugins.platforms.discord.adapter import DiscordAdapter

    adapter = DiscordAdapter.__new__(DiscordAdapter)
    # Role mentions are legitimate for real Discord roles — outbound
    # path should NOT warn.
    payload = "Heads up <@&1508199352898814126> team — meeting in 5."
    out = adapter.format_message(payload)
    assert out == payload


def test_discord_adapter_clean_payload_no_warning(caplog):
    pytest.importorskip("discord")
    from plugins.platforms.discord.adapter import DiscordAdapter

    adapter = DiscordAdapter.__new__(DiscordAdapter)
    payload = "Hey <@1508199506150166658> Fury — all green."
    with caplog.at_level(logging.WARNING, logger="plugins.platforms.discord.adapter"):
        out = adapter.format_message(payload)
    assert out == payload
    warning_records = [
        r for r in caplog.records
        if r.levelno == logging.WARNING and "malformed mention" in r.getMessage()
    ]
    assert not warning_records
