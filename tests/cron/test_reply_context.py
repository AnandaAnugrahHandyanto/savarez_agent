"""Tests for cron/reply_context.py — the gateway-facing skill resolver."""

import json
from unittest.mock import patch


class TestResolveJobName:
    def test_returns_none_when_no_message_id_or_text(self):
        from cron.reply_context import resolve_skill_for_reply

        assert resolve_skill_for_reply("discord", "chan1", None, None) is None

    def test_resolves_via_registry_when_message_id_known(self):
        from cron.reply_context import resolve_skill_for_reply

        with patch("cron.delivery_registry.lookup", return_value="mail-triage"), \
             patch("cron.reply_context._load_job_skills", return_value=["mail-triage-skill"]), \
             patch("cron.reply_context._load_skill_content", return_value="instructions"):
            result = resolve_skill_for_reply("discord", "chan1", "msg-42", "")

        assert result is not None
        assert "mail-triage-skill" in result
        assert "instructions" in result

    def test_falls_back_to_prefix_when_registry_empty(self):
        from cron.reply_context import resolve_skill_for_reply

        with patch("cron.delivery_registry.lookup", return_value=None), \
             patch("cron.reply_context._load_job_skills", return_value=["mail-skill"]), \
             patch("cron.reply_context._load_skill_content", return_value="content"):
            result = resolve_skill_for_reply(
                "discord",
                "chan1",
                "msg-99",
                "Cronjob Response: mail-triage\n-------------\n\nbody",
            )

        assert result is not None
        assert "mail-skill" in result

    def test_prefix_with_no_job_name_returns_none(self):
        from cron.reply_context import resolve_skill_for_reply

        with patch("cron.delivery_registry.lookup", return_value=None):
            result = resolve_skill_for_reply(
                "discord", "chan1", "msg-1", "Cronjob Response: \nbody"
            )

        assert result is None

    def test_registry_takes_precedence_over_prefix(self):
        from cron.reply_context import resolve_skill_for_reply

        # Registry says "job-from-registry"; prefix says "job-from-prefix".
        # Registry should win because it's the more reliable source for
        # multi-chunk replies.
        with patch("cron.delivery_registry.lookup", return_value="job-from-registry"), \
             patch("cron.reply_context._load_job_skills") as mock_skills, \
             patch("cron.reply_context._load_skill_content", return_value="x"):
            mock_skills.return_value = ["skill"]
            resolve_skill_for_reply(
                "discord",
                "chan1",
                "msg-1",
                "Cronjob Response: job-from-prefix\nbody",
            )
            mock_skills.assert_called_once_with("job-from-registry")


class TestSkillLoading:
    def test_returns_none_when_job_has_no_skills(self):
        from cron.reply_context import resolve_skill_for_reply

        with patch("cron.delivery_registry.lookup", return_value="bare-job"), \
             patch("cron.reply_context._load_job_skills", return_value=[]):
            result = resolve_skill_for_reply("discord", "chan1", "msg1", "")

        assert result is None

    def test_returns_none_when_all_skill_loads_fail(self):
        from cron.reply_context import resolve_skill_for_reply

        with patch("cron.delivery_registry.lookup", return_value="job"), \
             patch("cron.reply_context._load_job_skills", return_value=["s1", "s2"]), \
             patch("cron.reply_context._load_skill_content", return_value=None):
            result = resolve_skill_for_reply("discord", "chan1", "msg1", "")

        assert result is None

    def test_loads_multiple_skills_in_order(self):
        from cron.reply_context import resolve_skill_for_reply

        contents = {"alpha": "A-content", "beta": "B-content"}
        with patch("cron.delivery_registry.lookup", return_value="job"), \
             patch("cron.reply_context._load_job_skills", return_value=["alpha", "beta"]), \
             patch("cron.reply_context._load_skill_content", side_effect=lambda n: contents.get(n)):
            result = resolve_skill_for_reply("discord", "chan1", "msg1", "")

        assert result is not None
        assert result.index("A-content") < result.index("B-content")
        assert "alpha" in result
        assert "beta" in result
        assert result.endswith("\n\n")


class TestJobSkillsLoader:
    def test_load_job_skills_handles_skills_field(self):
        from cron.reply_context import _load_job_skills

        with patch(
            "cron.jobs.list_jobs",
            return_value=[{"name": "job-a", "skills": ["s1", "s2"]}],
        ):
            assert _load_job_skills("job-a") == ["s1", "s2"]

    def test_load_job_skills_handles_legacy_skill_field(self):
        from cron.reply_context import _load_job_skills

        with patch(
            "cron.jobs.list_jobs",
            return_value=[{"name": "job-a", "skill": "legacy-skill"}],
        ):
            assert _load_job_skills("job-a") == ["legacy-skill"]

    def test_load_job_skills_strips_and_filters_empty(self):
        from cron.reply_context import _load_job_skills

        with patch(
            "cron.jobs.list_jobs",
            return_value=[{"name": "job-a", "skills": ["  s1  ", "", "s2"]}],
        ):
            assert _load_job_skills("job-a") == ["s1", "s2"]

    def test_load_job_skills_matches_by_id_too(self):
        from cron.reply_context import _load_job_skills

        with patch(
            "cron.jobs.list_jobs",
            return_value=[{"id": "abc123", "name": "job-a", "skills": ["s1"]}],
        ):
            assert _load_job_skills("abc123") == ["s1"]

    def test_load_job_skills_returns_empty_when_unknown(self):
        from cron.reply_context import _load_job_skills

        with patch("cron.jobs.list_jobs", return_value=[]):
            assert _load_job_skills("nope") == []


class TestSkillContentLoader:
    def test_load_skill_content_returns_content_on_success(self):
        from cron.reply_context import _load_skill_content

        with patch(
            "tools.skills_tool.skill_view",
            return_value=json.dumps({"success": True, "content": "instructions here"}),
        ):
            assert _load_skill_content("my-skill") == "instructions here"

    def test_load_skill_content_returns_none_on_failure(self):
        from cron.reply_context import _load_skill_content

        with patch(
            "tools.skills_tool.skill_view",
            return_value=json.dumps({"success": False, "error": "not found"}),
        ):
            assert _load_skill_content("missing") is None

    def test_load_skill_content_swallows_exceptions(self):
        from cron.reply_context import _load_skill_content

        with patch("tools.skills_tool.skill_view", side_effect=RuntimeError("boom")):
            assert _load_skill_content("kaboom") is None
