from pathlib import Path

from people_manager.storage import get_people_manager_root


def test_peopleos_data_root_env_overrides_hermes_home(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes"
    peopleos_root = tmp_path / "peopleos-data"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("PEOPLEOS_DATA_ROOT", str(peopleos_root))

    root = get_people_manager_root()

    assert root == peopleos_root
    assert (peopleos_root / "reports").is_dir()
    assert (peopleos_root / "team-snapshots").is_dir()
    assert not (hermes_home / "projects" / "people-manager").exists()


def test_peopleos_data_root_falls_back_to_profile_project_root(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.delenv("PEOPLEOS_DATA_ROOT", raising=False)

    root = get_people_manager_root()

    assert root == hermes_home / "projects" / "people-manager"
    assert (root / "reports").is_dir()
    assert (root / "team-snapshots").is_dir()
