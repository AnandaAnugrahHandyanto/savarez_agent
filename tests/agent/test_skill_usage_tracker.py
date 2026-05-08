import json
import time

from agent import skill_usage_tracker as tracker


def test_record_and_top_categories(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "_usage_path", lambda: tmp_path / ".skill_usage.json")
    tracker.record_category_use("cat-a")
    tracker.record_category_use("cat-a")
    tracker.record_category_use("cat-b")

    top = tracker.top_categories(within_seconds=3600)
    assert top[0] == "cat-a"
    assert "cat-b" in top


def test_record_corrupted_file_falls_back(tmp_path, monkeypatch):
    path = tmp_path / ".skill_usage.json"
    path.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(tracker, "_usage_path", lambda: path)

    tracker.record_category_use("cat-a")

    assert "cat-a" in tracker.top_categories()


def test_known_clis_pruned_after_window(tmp_path, monkeypatch):
    path = tmp_path / ".skill_known_clis.json"
    monkeypatch.setattr(tracker, "_known_clis_path", lambda: path)
    tracker.record_cli_seen("rg")
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["rg"] = time.time() - (40 * 86400)
    path.write_text(json.dumps(raw), encoding="utf-8")

    assert tracker.is_known_cli("rg", window_days=30) is False

