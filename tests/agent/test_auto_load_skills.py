"""Tests for skills.auto_load config (#26800)."""

import os
from unittest.mock import patch

import pytest


@pytest.fixture
def hermes_home(tmp_path):
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "skills").mkdir()
    return home


def _read(home):
    from agent.skill_utils import get_auto_load_skills
    with patch.dict(os.environ, {"HERMES_HOME": str(home)}):
        return get_auto_load_skills()


class TestGetAutoLoadSkills:
    def test_no_config_file(self, tmp_path):
        home = tmp_path / "missing"
        assert _read(home) == []

    def test_missing_skills_block(self, hermes_home):
        (hermes_home / "config.yaml").write_text("agent:\n  max_turns: 10\n")
        assert _read(hermes_home) == []

    def test_missing_auto_load_key(self, hermes_home):
        (hermes_home / "config.yaml").write_text(
            "skills:\n  creation_nudge_interval: 15\n"
        )
        assert _read(hermes_home) == []

    def test_empty_list(self, hermes_home):
        (hermes_home / "config.yaml").write_text("skills:\n  auto_load: []\n")
        assert _read(hermes_home) == []

    def test_single_string_value(self, hermes_home):
        (hermes_home / "config.yaml").write_text(
            "skills:\n  auto_load: using-superpowers\n"
        )
        assert _read(hermes_home) == ["using-superpowers"]

    def test_list_value_order_preserved(self, hermes_home):
        (hermes_home / "config.yaml").write_text(
            "skills:\n  auto_load:\n    - alpha\n    - beta\n    - gamma\n"
        )
        assert _read(hermes_home) == ["alpha", "beta", "gamma"]

    def test_duplicates_deduplicated(self, hermes_home):
        (hermes_home / "config.yaml").write_text(
            "skills:\n  auto_load:\n    - alpha\n    - beta\n    - alpha\n"
        )
        assert _read(hermes_home) == ["alpha", "beta"]

    def test_whitespace_stripped_and_empties_dropped(self, hermes_home):
        (hermes_home / "config.yaml").write_text(
            "skills:\n  auto_load:\n    - '  alpha  '\n    - ''\n    - beta\n"
        )
        assert _read(hermes_home) == ["alpha", "beta"]

    def test_invalid_type_returns_empty(self, hermes_home):
        (hermes_home / "config.yaml").write_text("skills:\n  auto_load: 42\n")
        assert _read(hermes_home) == []

    def test_skills_block_not_mapping(self, hermes_home):
        (hermes_home / "config.yaml").write_text("skills: not-a-mapping\n")
        assert _read(hermes_home) == []

    def test_malformed_yaml_swallowed(self, hermes_home):
        (hermes_home / "config.yaml").write_text("skills: [unterminated\n")
        assert _read(hermes_home) == []
