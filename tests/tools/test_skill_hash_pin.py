"""Tests for tools/skill_hash_pin.py — skill content integrity verification."""

import json
import pytest
from pathlib import Path

from tools.skill_hash_pin import (
    pin_skill,
    unpin_skill,
    verify_skill,
    _load_pins,
    _pins,
)


@pytest.fixture(autouse=True)
def clean_pin_state(tmp_path, monkeypatch):
    """Isolate pin state per test."""
    import tools.skill_hash_pin as mod
    mod._pins = {}
    mod._PIN_FILE = tmp_path / ".skill_hashes.json"
    yield
    mod._pins = {}
    mod._PIN_FILE = None


def _make_skill(tmp_path: Path, name: str, content: str = "---\nname: test\n---\nHello") -> Path:
    skill_dir = tmp_path / name
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(content)
    return skill_dir


class TestPinSkill:
    def test_pin_records_hash(self, tmp_path):
        skill_dir = _make_skill(tmp_path, "summarize")
        h = pin_skill("summarize", skill_dir)
        assert h.startswith("sha256:")
        assert len(h) == len("sha256:") + 16

    def test_pin_persists_to_file(self, tmp_path):
        import tools.skill_hash_pin as mod
        skill_dir = _make_skill(tmp_path, "summarize")
        pin_skill("summarize", skill_dir)
        assert mod._PIN_FILE.exists()
        data = json.loads(mod._PIN_FILE.read_text())
        assert "summarize" in data

    def test_pin_updates_on_repin(self, tmp_path):
        skill_dir = _make_skill(tmp_path, "summarize", "v1")
        h1 = pin_skill("summarize", skill_dir)
        (skill_dir / "SKILL.md").write_text("v2")
        h2 = pin_skill("summarize", skill_dir)
        assert h1 != h2


class TestUnpinSkill:
    def test_unpin_removes_entry(self, tmp_path):
        skill_dir = _make_skill(tmp_path, "summarize")
        pin_skill("summarize", skill_dir)
        unpin_skill("summarize")
        import tools.skill_hash_pin as mod
        assert "summarize" not in mod._pins

    def test_unpin_nonexistent_is_noop(self, tmp_path):
        unpin_skill("nonexistent")  # Should not raise


class TestVerifySkill:
    def test_unpinned_skill_passes(self, tmp_path):
        skill_dir = _make_skill(tmp_path, "builtin-skill")
        assert verify_skill("builtin-skill", skill_dir) is True

    def test_pinned_skill_matches(self, tmp_path):
        skill_dir = _make_skill(tmp_path, "summarize")
        pin_skill("summarize", skill_dir)
        assert verify_skill("summarize", skill_dir) is True

    def test_tampered_skill_fails(self, tmp_path):
        skill_dir = _make_skill(tmp_path, "summarize", "original content")
        pin_skill("summarize", skill_dir)
        # Tamper with the skill after pinning
        (skill_dir / "SKILL.md").write_text("tampered content")
        assert verify_skill("summarize", skill_dir) is False

    def test_added_file_fails(self, tmp_path):
        skill_dir = _make_skill(tmp_path, "summarize")
        pin_skill("summarize", skill_dir)
        # Add a new file (e.g., exfiltration script)
        (skill_dir / "helper.py").write_text("import os; os.system('curl ...')")
        assert verify_skill("summarize", skill_dir) is False

    def test_deleted_file_fails(self, tmp_path):
        skill_dir = _make_skill(tmp_path, "summarize")
        (skill_dir / "refs.md").write_text("reference data")
        pin_skill("summarize", skill_dir)
        # Delete the reference file
        (skill_dir / "refs.md").unlink()
        assert verify_skill("summarize", skill_dir) is False


class TestPersistence:
    def test_load_from_disk(self, tmp_path):
        import tools.skill_hash_pin as mod
        skill_dir = _make_skill(tmp_path, "summarize")
        pin_skill("summarize", skill_dir)
        saved_hash = mod._pins["summarize"]
        # Clear in-memory state
        mod._pins = {}
        # Reload from disk
        _load_pins()
        assert mod._pins["summarize"] == saved_hash
