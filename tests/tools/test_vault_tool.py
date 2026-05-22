"""Tests for tools/vault_tool.py — vault_search and ask_vault."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def vault_root(tmp_path: Path, monkeypatch) -> Path:
    """Set up a temporary vault root and monkeypatch get_hermes_home."""

    # Create a fake HERMES_HOME layout.
    hermes_home = tmp_path / "hermes_home"
    vault = hermes_home / "data" / "development_ideas"
    vault.mkdir(parents=True)

    # Patch get_hermes_home in the vault_tool module so the default root
    # resolves to our tmp directory.
    import tools.vault_tool as vt

    monkeypatch.setattr(vt, "get_hermes_home", lambda: hermes_home)

    return vault


# ---------------------------------------------------------------------------
# Helpers to populate the vault
# ---------------------------------------------------------------------------


def _write_readme(vault: Path, content: str) -> None:
    (vault / "README.md").write_text(content, encoding="utf-8")


def _write_ideas(vault: Path, entries: list[dict]) -> None:
    (vault / "ideas.jsonl").write_text(
        "\n".join(json.dumps(e) for e in entries), encoding="utf-8"
    )


def _write_source(vault: Path, name: str, content: str) -> None:
    sources = vault / "sources"
    sources.mkdir(exist_ok=True)
    (sources / name).write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# vault_search tests
# ---------------------------------------------------------------------------


class TestVaultSearch:
    def test_match_readme(self, vault_root):
        """Finds a match in README.md."""
        _write_readme(vault_root, "# Dev Ideas\n\nBuild a distributed cache system.\n")
        import tools.vault_tool as vt

        result = json.loads(vt.vault_search("distributed cache"))
        assert result["success"] is True
        assert result["total"] >= 1
        assert any("distributed" in m["snippet"].lower() for m in result["matches"])
        assert result["truncated"] is False

    def test_match_jsonl(self, vault_root):
        """Finds a match in ideas.jsonl."""
        _write_ideas(
            vault_root,
            [
                {"title": "Graph Database", "body": "Explore neo4j for recommendation engine"},
                {"title": "Unrelated", "body": "Something completely different"},
            ],
        )
        import tools.vault_tool as vt

        result = json.loads(vt.vault_search("neo4j"))
        assert result["success"] is True
        assert result["total"] == 1
        assert "neo4j" in result["matches"][0]["snippet"].lower()
        assert result["matches"][0]["type"] == "jsonl"

    def test_match_sources(self, vault_root):
        """Finds a match in sources/*.md."""
        _write_source(vault_root, "ref.md", "## Reference\n\nUsing vector embeddings for search.\n")
        import tools.vault_tool as vt

        result = json.loads(vt.vault_search("vector embeddings"))
        assert result["success"] is True
        assert result["total"] >= 1
        assert result["matches"][0]["type"] == "source"

    def test_no_results(self, vault_root):
        """Returns success with empty matches when nothing found."""
        _write_readme(vault_root, "# Ideas\n\nHello world.\n")
        import tools.vault_tool as vt

        result = json.loads(vt.vault_search("zzznomatch"))
        assert result["success"] is True
        assert result["matches"] == []
        assert result["total"] == 0
        assert result["truncated"] is False

    def test_limit_and_truncated(self, vault_root):
        """Respects limit and sets truncated=True when there are more results."""
        # Write README with many matching lines.
        lines = "\n".join(f"idea about caching line {i}" for i in range(20))
        _write_readme(vault_root, lines)
        import tools.vault_tool as vt

        result = json.loads(vt.vault_search("caching", limit=5))
        assert result["success"] is True
        assert len(result["matches"]) == 5
        assert result["total"] > 5
        assert result["truncated"] is True

    def test_empty_query_returns_error(self, vault_root):
        """Empty query returns success=False."""
        import tools.vault_tool as vt

        result = json.loads(vt.vault_search(""))
        assert result["success"] is False
        assert "error" in result

    def test_whitespace_only_query_returns_error(self, vault_root):
        """Whitespace-only query returns success=False."""
        import tools.vault_tool as vt

        result = json.loads(vt.vault_search("   "))
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.parametrize("bad_limit", [0, -1])
    def test_invalid_limit_returns_error(self, vault_root, bad_limit):
        """limit <= 0 returns success=False with appropriate error."""
        _write_readme(vault_root, "some content")
        import tools.vault_tool as vt

        result = json.loads(vt.vault_search("content", limit=bad_limit))
        assert result["success"] is False
        assert "limit" in result["error"].lower()

    def test_include_sources_false(self, vault_root):
        """When include_sources=False, sources/*.md are not searched."""
        _write_source(vault_root, "ref.md", "embedded secrets in source file")
        _write_readme(vault_root, "# Ideas")
        import tools.vault_tool as vt

        result = json.loads(vt.vault_search("embedded secrets", include_sources=False))
        assert result["success"] is True
        assert all(m["type"] != "source" for m in result["matches"])

    def test_absolute_path_override(self, vault_root, tmp_path):
        """Absolute path override works if directory exists."""
        alt = tmp_path / "alt_vault"
        alt.mkdir()
        (alt / "README.md").write_text("unicorn magic here", encoding="utf-8")
        import tools.vault_tool as vt

        result = json.loads(vt.vault_search("unicorn", path=str(alt)))
        assert result["success"] is True
        assert result["total"] >= 1

    def test_absolute_path_nonexistent_returns_error(self, vault_root, tmp_path):
        """Absolute path that doesn't exist returns error."""
        import tools.vault_tool as vt

        result = json.loads(vt.vault_search("x", path=str(tmp_path / "does_not_exist")))
        assert result["success"] is False
        assert "error" in result

    def test_relative_path_traversal_blocked(self, vault_root):
        """Relative path with '..' is rejected."""
        import tools.vault_tool as vt

        result = json.loads(vt.vault_search("x", path="../../../etc"))
        assert result["success"] is False
        assert "error" in result

    def test_result_fields(self, vault_root):
        """Each match has path, type, line, snippet, score fields."""
        _write_readme(vault_root, "This is a machine learning idea.\n")
        import tools.vault_tool as vt

        result = json.loads(vt.vault_search("machine learning"))
        assert result["success"] is True
        assert len(result["matches"]) >= 1
        m = result["matches"][0]
        assert "path" in m
        assert "type" in m
        assert "line" in m
        assert "snippet" in m
        assert "score" in m
        assert m["score"] > 0

    def test_results_sorted_by_score_desc(self, vault_root):
        """Results are returned highest-score first."""
        # Line with exact query match scores higher than line with single term.
        _write_readme(
            vault_root,
            "blockchain ledger concept\n"
            "distributed blockchain ledger technology for secure transactions\n",
        )
        import tools.vault_tool as vt

        result = json.loads(vt.vault_search("blockchain ledger"))
        scores = [m["score"] for m in result["matches"]]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# ask_vault tests
# ---------------------------------------------------------------------------


class TestAskVault:
    def test_basic_ask(self, vault_root):
        """ask_vault returns expected top-level keys."""
        _write_readme(vault_root, "# Ideas\n\nFast key-value store using LSM trees.\n")
        import tools.vault_tool as vt

        result = json.loads(vt.ask_vault("key-value store"))
        assert result["success"] is True
        assert result["mode"] == "extractive"
        assert "answer_summary" in result
        assert "candidate_context" in result
        assert "sources" in result
        assert isinstance(result["candidate_context"], list)

    def test_answer_summary_mentions_extractive(self, vault_root):
        """answer_summary always states it is extractive (no LLM)."""
        _write_ideas(vault_root, [{"title": "Caching", "body": "Use Redis for caching"}])
        import tools.vault_tool as vt

        result = json.loads(vt.ask_vault("caching"))
        assert "extractive" in result["answer_summary"].lower() or "no llm" in result["answer_summary"].lower()

    def test_no_results_answer_summary(self, vault_root):
        """When no matches, answer_summary still mentions extractive search."""
        _write_readme(vault_root, "# Nothing relevant here.")
        import tools.vault_tool as vt

        result = json.loads(vt.ask_vault("zzznomatch"))
        assert result["success"] is True
        assert result["candidate_context"] == []
        assert result["sources"] == []
        assert "no matching" in result["answer_summary"].lower() or "extractive" in result["answer_summary"].lower()

    def test_sources_deduped(self, vault_root):
        """sources list contains unique file paths."""
        content = "\n".join(f"line {i} about kafka" for i in range(5))
        _write_readme(vault_root, content)
        import tools.vault_tool as vt

        result = json.loads(vt.ask_vault("kafka"))
        assert result["success"] is True
        assert len(result["sources"]) == len(set(result["sources"]))

    def test_limit_applied_to_context(self, vault_root):
        """limit restricts candidate_context length."""
        lines = "\n".join(f"spark streaming event {i}" for i in range(20))
        _write_readme(vault_root, lines)
        import tools.vault_tool as vt

        result = json.loads(vt.ask_vault("spark streaming", limit=3))
        assert result["success"] is True
        assert len(result["candidate_context"]) <= 3

    def test_candidate_context_fields(self, vault_root):
        """Each candidate_context entry has source, line, text, score."""
        _write_ideas(vault_root, [{"title": "AI safety", "body": "Alignment research ideas"}])
        import tools.vault_tool as vt

        result = json.loads(vt.ask_vault("alignment"))
        ctx = result["candidate_context"]
        assert len(ctx) >= 1
        for entry in ctx:
            assert "source" in entry
            assert "line" in entry
            assert "text" in entry
            assert "score" in entry

    def test_empty_question_returns_error(self, vault_root):
        """Empty question returns success=False."""
        import tools.vault_tool as vt

        result = json.loads(vt.ask_vault(""))
        assert result["success"] is False
        assert "error" in result

    def test_whitespace_only_question_returns_error(self, vault_root):
        """Whitespace-only question returns success=False."""
        import tools.vault_tool as vt

        result = json.loads(vt.ask_vault("   "))
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.parametrize("bad_limit", [0, -1])
    def test_invalid_limit_returns_error(self, vault_root, bad_limit):
        """limit <= 0 returns success=False with appropriate error."""
        _write_readme(vault_root, "some content")
        import tools.vault_tool as vt

        result = json.loads(vt.ask_vault("content", limit=bad_limit))
        assert result["success"] is False
        assert "limit" in result["error"].lower()

    def test_path_traversal_returns_error(self, vault_root):
        """Relative path with '..' is rejected in ask_vault."""
        import tools.vault_tool as vt

        result = json.loads(vt.ask_vault("anything", path="../../../etc"))
        assert result["success"] is False
        assert "error" in result

    def test_malformed_jsonl_line_does_not_crash(self, vault_root):
        """A malformed JSONL line is skipped; valid subsequent lines are still found."""
        (vault_root / "ideas.jsonl").write_text(
            'this is not json\n'
            '{"title": "Valid Entry", "body": "reachable content after bad line"}\n',
            encoding="utf-8",
        )
        import tools.vault_tool as vt

        result = json.loads(vt.ask_vault("reachable content"))
        assert result["success"] is True
        assert len(result["candidate_context"]) >= 1
        assert any("reachable" in entry["text"].lower() for entry in result["candidate_context"])


# ---------------------------------------------------------------------------
# check_fn / availability
# ---------------------------------------------------------------------------


class TestCheckFn:
    def test_check_fn_true_when_vault_exists(self, vault_root):
        """_check_vault_available returns True when vault dir exists."""
        import tools.vault_tool as vt

        assert vt._check_vault_available() is True

    def test_check_fn_false_when_vault_missing(self, tmp_path, monkeypatch):
        """_check_vault_available returns False when vault dir is absent."""
        import tools.vault_tool as vt

        monkeypatch.setattr(vt, "get_hermes_home", lambda: tmp_path / "nonexistent_home")
        assert vt._check_vault_available() is False
