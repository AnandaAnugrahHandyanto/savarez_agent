from pathlib import Path

from agent.skill_utils import get_external_skills_dirs


def test_external_skill_dirs_resolve_relative_to_config_path(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes-home"
    shared_skills = tmp_path / "shared-skills"
    other_cwd = tmp_path / "unrelated" / "other-cwd"

    hermes_home.mkdir()
    shared_skills.mkdir()
    other_cwd.mkdir(parents=True)

    (hermes_home / "config.yaml").write_text(
        "skills:\n  external_dirs:\n    - ../shared-skills\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.chdir(other_cwd)

    assert get_external_skills_dirs() == [shared_skills.resolve()]
