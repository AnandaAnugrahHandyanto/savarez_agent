import json

from tools.kb_tool import kb_tool


class TestKbTool:
    def test_init_creates_wiki_structure(self, tmp_path, monkeypatch):
        wiki_root = tmp_path / "Wiki"
        monkeypatch.setenv("LLM_WIKI_PATH", str(wiki_root))

        result = json.loads(kb_tool(action="init", domain="AI research"))

        assert result["success"] is True
        assert wiki_root.exists()
        assert (wiki_root / "SCHEMA.md").exists()
        assert (wiki_root / "index.md").exists()
        assert (wiki_root / "log.md").exists()
        assert (wiki_root / "raw" / "articles").exists()
        assert (wiki_root / "concepts").exists()
        assert (wiki_root / "entities").exists()

    def test_file_search_and_read_round_trip(self, tmp_path, monkeypatch):
        wiki_root = tmp_path / "Wiki"
        monkeypatch.setenv("LLM_WIKI_PATH", str(wiki_root))

        kb_tool(action="init", domain="AI research")
        kb_tool(
            action="file",
            title="Andrej Karpathy",
            page_type="entity",
            tags="people,ai",
            content="# Andrej Karpathy\n\nResearcher linked to [[transformers]].",
        )
        kb_tool(
            action="file",
            title="Transformers",
            page_type="concept",
            tags="models,architecture",
            content="# Transformers\n\nA neural architecture used across modern LLM systems.",
        )

        search = json.loads(kb_tool(action="search", query="Karpathy"))
        assert search["total_matches"] >= 1
        assert any(item["title"] == "Andrej Karpathy" for item in search["results"])

        page = kb_tool(action="read", page="andrej-karpathy")
        assert "Researcher linked to [[transformers]]" in page

        index_text = kb_tool(action="list")
        assert "Andrej Karpathy" in index_text
        assert "Transformers" in index_text

    def test_lint_reports_broken_links_and_missing_index_entries(self, tmp_path, monkeypatch):
        wiki_root = tmp_path / "Wiki"
        monkeypatch.setenv("LLM_WIKI_PATH", str(wiki_root))

        kb_tool(action="init", domain="AI research")
        kb_tool(
            action="file",
            title="Sparse MoE",
            page_type="concept",
            content="# Sparse MoE\n\nSee also [[missing-page]].",
        )

        lint = json.loads(kb_tool(action="lint"))
        assert lint["success"] is True
        assert "missing-page" in lint["issues"]["broken_wikilinks"]
