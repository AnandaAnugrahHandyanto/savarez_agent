"""Tests for the custom (LLM wiki / second brain) memory provider."""

import json
from unittest.mock import patch

import pytest


def _make_provider(tmp_path, **overrides):
    """Build an initialized provider pointed at *tmp_path* as the vault."""
    from plugins.memory.custom import CustomMemoryProvider

    cfg = {"mode": "files", "dir": str(tmp_path)}
    cfg.update(overrides)
    provider = CustomMemoryProvider()
    with patch("plugins.memory.custom._load_custom_config", return_value=cfg):
        available = provider.is_available()
        provider.initialize("sess-1")
    return provider, available


class TestFilesBackend:
    def _backend(self, tmp_path, write_format="markdown"):
        from plugins.memory.custom import _FilesBackend

        return _FilesBackend(
            root=tmp_path,
            write_subdir="hermes-memory",
            write_format=write_format,
            read_globs=("*.md", "*.txt"),
            max_results=5,
        )

    def test_recall_finds_matching_note(self, tmp_path):
        (tmp_path / "alpha.md").write_text(
            "The deploy key lives in the vault. Rotate the deploy key quarterly.",
            encoding="utf-8",
        )
        (tmp_path / "beta.md").write_text("Unrelated grocery list.", encoding="utf-8")
        hits = self._backend(tmp_path).recall("deploy key rotation", 5)
        assert hits
        assert "alpha.md" in hits[0]
        assert "deploy" in hits[0].lower()

    def test_recall_never_leaks_absolute_path(self, tmp_path):
        (tmp_path / "notes.md").write_text("project phoenix milestone", encoding="utf-8")
        hits = self._backend(tmp_path).recall("phoenix milestone", 5)
        assert hits
        assert str(tmp_path) not in hits[0]  # file name only, not the path

    def test_recall_ignores_too_short_terms(self, tmp_path):
        (tmp_path / "n.md").write_text("content here", encoding="utf-8")
        assert self._backend(tmp_path).recall("a is", 5) == []

    def test_write_turn_markdown_is_recallable(self, tmp_path):
        backend = self._backend(tmp_path, "markdown")
        backend.write_turn("What is the api port?", "The api port is 4042.", "s1")
        note = tmp_path / "hermes-memory" / "session-s1.md"
        assert note.exists()
        text = note.read_text(encoding="utf-8")
        assert text.startswith("---")  # frontmatter written for new markdown notes
        assert "api port" in text
        # round-trip: a written note is recalled on a later query
        assert any("session-s1.md" in h for h in backend.recall("api port", 5))

    def test_write_turn_jsonl_format(self, tmp_path):
        backend = self._backend(tmp_path, "jsonl")
        backend.write_turn("hi", "hello", "s2")
        f = tmp_path / "hermes-memory" / "session-s2.jsonl"
        row = json.loads(f.read_text(encoding="utf-8").strip())
        assert row["user"] == "hi" and row["assistant"] == "hello"

    def test_write_fact_markdown(self, tmp_path):
        backend = self._backend(tmp_path, "markdown")
        backend.write_fact("User prefers metric units")
        facts = (tmp_path / "hermes-memory" / "facts.md").read_text(encoding="utf-8")
        assert "metric units" in facts

    def test_session_id_path_traversal_is_neutralized(self, tmp_path):
        backend = self._backend(tmp_path, "markdown")
        backend.write_turn("u", "a", "../../etc/passwd")
        written = list((tmp_path / "hermes-memory").glob("session-*.md"))
        assert len(written) == 1  # stayed inside write_subdir, no traversal


class TestCustomMemoryProvider:
    def test_unconfigured_is_unavailable(self):
        from plugins.memory.custom import CustomMemoryProvider

        provider = CustomMemoryProvider()
        with patch("plugins.memory.custom._load_custom_config", return_value={}):
            assert provider.is_available() is False

    def test_http_mode_inactive_in_this_version(self, tmp_path):
        from plugins.memory.custom import CustomMemoryProvider

        provider = CustomMemoryProvider()
        with patch(
            "plugins.memory.custom._load_custom_config",
            return_value={"mode": "http", "dir": str(tmp_path)},
        ):
            assert provider.is_available() is False

    def test_available_and_exposes_tools_when_configured(self, tmp_path):
        provider, available = _make_provider(tmp_path)
        assert available is True
        assert provider.get_tool_schemas()

    def test_prefetch_recalls_notes(self, tmp_path):
        (tmp_path / "note.md").write_text(
            "The staging server is named borealis.", encoding="utf-8"
        )
        provider, _ = _make_provider(tmp_path)
        assert "borealis" in provider.prefetch("what is the staging server name")

    def test_sync_turn_writes_and_session_end_flushes(self, tmp_path):
        provider, _ = _make_provider(tmp_path)
        provider.sync_turn("remember X", "ok", session_id="s9")
        provider.on_session_end([])  # joins the background writer
        note = tmp_path / "hermes-memory" / "session-s9.md"
        assert note.exists()
        assert "remember X" in note.read_text(encoding="utf-8")

    def test_memory_add_tool_writes_fact(self, tmp_path):
        provider, _ = _make_provider(tmp_path)
        result = json.loads(provider.handle_tool_call("memory_add", {"content": "deadline is Friday"}))
        assert "saved" in result["result"].lower()
        facts = (tmp_path / "hermes-memory" / "facts.md").read_text(encoding="utf-8")
        assert "Friday" in facts

    def test_memory_search_tool(self, tmp_path):
        (tmp_path / "k.md").write_text("The cache TTL is set to 900 seconds.", encoding="utf-8")
        provider, _ = _make_provider(tmp_path)
        result = json.loads(provider.handle_tool_call("memory_search", {"query": "cache TTL seconds"}))
        assert "900" in result["result"]
