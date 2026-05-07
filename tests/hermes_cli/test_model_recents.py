"""Tests for hermes_cli.model_recents — the recents store for the /model picker."""

import json
import os

import pytest

from hermes_constants import get_hermes_home


@pytest.fixture
def recents_home(tmp_path, monkeypatch):
    """Isolated HERMES_HOME with no pre-existing recents file."""
    home = tmp_path / "hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    return home


class TestRecordAndLoad:
    def test_fresh_load_returns_empty(self, recents_home):
        """Loading with no store file returns empty list."""
        from hermes_cli.model_recents import load_recent_models
        result = load_recent_models()
        assert result == []

    def test_record_one_then_load(self, recents_home):
        """Recording a single entry then loading returns it."""
        from hermes_cli.model_recents import record_model_selection, load_recent_models
        record_model_selection("ollama-launch", "qwen3.6:35b")
        result = load_recent_models()
        assert len(result) == 1
        assert result[0]["provider"] == "ollama-launch"
        assert result[0]["model"] == "qwen3.6:35b"
        assert result[0]["count"] == 1

    def test_record_same_dedups_and_increments_count(self, recents_home):
        """Selecting the same provider:model twice dedups and bumps count."""
        from hermes_cli.model_recents import record_model_selection, load_recent_models
        record_model_selection("venice", "claude-opus-4")
        record_model_selection("venice", "claude-opus-4")
        result = load_recent_models()
        assert len(result) == 1
        assert result[0]["provider"] == "venice"
        assert result[0]["model"] == "claude-opus-4"
        assert result[0]["count"] == 2

    def test_second_entry_moves_to_front(self, recents_home):
        """Re-selecting an older entry moves it to the front."""
        from hermes_cli.model_recents import record_model_selection, load_recent_models
        record_model_selection("a", "model-a")
        record_model_selection("b", "model-b")
        # Now a is older, b is at front
        record_model_selection("a", "model-a")
        result = load_recent_models()
        assert result[0]["provider"] == "a"
        assert result[0]["model"] == "model-a"
        assert result[0]["count"] == 2

    def test_limit_param_caps_return(self, recents_home):
        """The limit parameter caps the returned list."""
        from hermes_cli.model_recents import record_model_selection, load_recent_models
        for i in range(10):
            record_model_selection(f"prov-{i}", f"model-{i}")
        result = load_recent_models(limit=3)
        assert len(result) == 3
        # Most recent first
        assert result[0]["model"] == "model-9"

    def test_cap_at_20_stored(self, recents_home):
        """Store never grows beyond 20 entries."""
        from hermes_cli.model_recents import record_model_selection, load_recent_models
        for i in range(25):
            record_model_selection(f"prov-{i}", f"model-{i}")
        result = load_recent_models(limit=30)
        assert len(result) == 20
        # Most recent 20 only — prov-24 through prov-5
        assert result[0]["model"] == "model-24"
        assert result[-1]["model"] == "model-5"

    def test_limit_zero_returns_empty(self, recents_home):
        """limit=0 returns empty list."""
        from hermes_cli.model_recents import record_model_selection, load_recent_models
        record_model_selection("p", "m")
        result = load_recent_models(limit=0)
        assert result == []


class TestStoreResilience:
    def test_corrupt_json_resets(self, recents_home):
        """A corrupt JSON store falls back to empty list."""
        store_path = get_hermes_home() / "model_recents.json"
        store_path.write_text("this is not valid json {{{")
        from hermes_cli.model_recents import load_recent_models, record_model_selection
        # Load should return empty
        assert load_recent_models() == []
        # After recording, everything works normally
        record_model_selection("p", "m")
        assert len(load_recent_models()) == 1

    def test_wrong_version_resets(self, recents_home):
        """Unknown version number resets to empty."""
        store_path = get_hermes_home() / "model_recents.json"
        store_path.write_text(json.dumps({"version": 99, "recents": [{"provider": "p", "model": "m", "last_used": "", "count": 1}]}))
        from hermes_cli.model_recents import load_recent_models
        assert load_recent_models() == []

    def test_recents_not_a_list_resets(self, recents_home):
        """Top-level recents is not a list → reset."""
        store_path = get_hermes_home() / "model_recents.json"
        store_path.write_text(json.dumps({"version": 1, "recents": "oops_not_a_list"}))
        from hermes_cli.model_recents import load_recent_models
        assert load_recent_models() == []

    def test_missing_file_is_fine(self, recents_home):
        """No file at all → returns empty, no crash."""
        # recents_home fixture created dir with no file
        from hermes_cli.model_recents import load_recent_models
        assert load_recent_models() == []

    def test_atomic_write_no_tempfile_left(self, recents_home):
        """Successful write doesn't leave temp files behind."""
        from hermes_cli.model_recents import record_model_selection
        record_model_selection("p", "m")
        home = get_hermes_home()
        tmp_files = list(home.glob(".model_recents_*.tmp"))
        assert len(tmp_files) == 0, f"temp files left behind: {tmp_files}"

    def test_clear_removes_file(self, recents_home):
        """clear_recent_models removes the store file."""
        from hermes_cli.model_recents import (
            record_model_selection, load_recent_models, clear_recent_models,
        )
        record_model_selection("p", "m")
        assert len(load_recent_models()) == 1
        clear_recent_models()
        assert load_recent_models() == []
        # File is actually gone
        assert not (get_hermes_home() / "model_recents.json").exists()


class TestPathResolution:
    def test_uses_hermes_home(self, recents_home):
        """Store path resolves via get_hermes_home(), not hardcoded."""
        from hermes_cli.model_recents import record_model_selection
        record_model_selection("p", "m")
        expected = recents_home / "model_recents.json"
        assert expected.exists()
        data = json.loads(expected.read_text())
        assert data["version"] == 1
        assert len(data["recents"]) == 1
