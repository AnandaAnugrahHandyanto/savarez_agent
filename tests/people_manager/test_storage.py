from pathlib import Path

from people_manager.storage import (
    access_report,
    create_report,
    get_people_manager_root,
    get_registry_path,
    get_report_path,
    list_reports_by_recency,
    load_registry,
    load_report,
    save_registry,
    touch_report,
)


def test_load_registry_initializes_empty_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    registry = load_registry()

    assert registry["version"] == 1
    assert registry["reports"] == {}
    assert get_people_manager_root().exists()
    assert get_registry_path().exists()


def test_create_report_persists_report_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    report = create_report(
        name="Alice Chen",
        role_title="Head of IR",
        mandate="Own investor communication rhythm",
    )

    assert report["slug"] == "alice-chen"
    assert get_report_path("alice-chen").exists()

    reloaded = load_report("alice-chen")
    assert reloaded["name"] == "Alice Chen"
    assert reloaded["role_charter"]["mandate"] == "Own investor communication rhythm"

    registry = load_registry()
    assert registry["reports"]["alice-chen"]["name"] == "Alice Chen"
    assert registry["reports"]["alice-chen"]["last_accessed_at"]


def test_touch_report_updates_last_touched_at(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    report = create_report(
        name="Alice Chen",
        role_title="Head of IR",
        mandate="Own investor communication rhythm",
    )
    before = load_registry()["reports"][report["slug"]]["last_touched_at"]

    touch_report(report["slug"])

    after = load_registry()["reports"][report["slug"]]["last_touched_at"]
    assert after >= before


def test_access_report_updates_only_last_accessed_at(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    report = create_report(
        name="Alice Chen",
        role_title="Head of IR",
        mandate="Own investor communication rhythm",
    )
    before = load_registry()["reports"][report["slug"]]

    access_report(report["slug"])

    after = load_registry()["reports"][report["slug"]]
    assert after["last_accessed_at"] >= before["last_accessed_at"]
    assert after["last_touched_at"] == before["last_touched_at"]


def test_list_reports_by_recency_newest_first(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    create_report("Alice Chen", "Head of IR", "Own investor communication rhythm")
    create_report("Bob Lee", "COO", "Own execution cadence")
    touch_report("alice-chen")

    reports = list_reports_by_recency()

    assert [r["slug"] for r in reports][:2] == ["alice-chen", "bob-lee"]


def test_storage_stays_under_people_manager_project_root(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    create_report("Alice Chen", "Head of IR", "Own investor communication rhythm")

    root = get_people_manager_root().resolve()
    assert root == (hermes_home / "projects" / "people-manager").resolve()
    assert get_registry_path().resolve().is_relative_to(root)
    assert get_report_path("alice-chen").resolve().is_relative_to(root)


def test_save_registry_round_trip_preserves_report_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    create_report("Alice Chen", "Head of IR", "Own investor communication rhythm")
    registry = load_registry()
    registry["reports"]["alice-chen"]["status"] = "paused"

    save_registry(registry)

    reloaded = load_registry()
    assert reloaded["reports"]["alice-chen"]["status"] == "paused"
