from pathlib import Path

import pytest

import tests.agent.test_skill_commands as skill_command_tests


def test_symlink_category_skips_when_symlinks_unavailable(tmp_path, monkeypatch):
    def _raise_oserror(self, target, target_is_directory=False):
        raise OSError("no symlink")

    monkeypatch.setattr(Path, "symlink_to", _raise_oserror)

    with pytest.raises(pytest.skip.Exception, match="symlinks unavailable"):
        skill_command_tests._symlink_category(
            tmp_path / "skills",
            tmp_path / "repo",
            "linked",
        )
