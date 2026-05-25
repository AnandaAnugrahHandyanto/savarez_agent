"""Tests for cron-scoped skill index plumbing."""

from cron.scheduler import _cron_skill_index_scope


def test_cron_skill_index_scope_prefers_skills_list():
    job = {"skill": "legacy-skill", "skills": ["first", " second ", ""]}

    assert _cron_skill_index_scope(job) == ["first", "second"]


def test_cron_skill_index_scope_accepts_legacy_skill():
    job = {"skill": " legacy-skill "}

    assert _cron_skill_index_scope(job) == ["legacy-skill"]


def test_cron_skill_index_scope_accepts_string_skills_value():
    job = {"skills": "single-skill"}

    assert _cron_skill_index_scope(job) == ["single-skill"]


def test_cron_skill_index_scope_empty_without_bound_skills():
    assert _cron_skill_index_scope({}) == []
