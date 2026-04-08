from agent.wiki_command import format_wiki_status, run_wiki_command


class TestWikiCommand:
    def test_status_reports_configured_path(self, tmp_path, monkeypatch):
        wiki_root = tmp_path / "Wiki"
        monkeypatch.setenv("LLM_WIKI_PATH", str(wiki_root))

        output = format_wiki_status()

        assert "Wiki Status" in output
        assert str(wiki_root) in output
        assert "Initialized: no" in output

    def test_init_creates_wiki_and_reports_files(self, tmp_path, monkeypatch):
        wiki_root = tmp_path / "Wiki"
        monkeypatch.setenv("LLM_WIKI_PATH", str(wiki_root))

        output = run_wiki_command("init", "AI research")

        assert "Wiki initialized" in output
        assert str(wiki_root) in output
        assert (wiki_root / "SCHEMA.md").exists()
        assert "Next steps:" in output
        assert "/wiki ingest <url-or-local-file>" in output

    def test_lint_reports_issue_count(self, tmp_path, monkeypatch):
        wiki_root = tmp_path / "Wiki"
        monkeypatch.setenv("LLM_WIKI_PATH", str(wiki_root))

        run_wiki_command("init", "AI research")
        from tools.kb_tool import kb_tool

        kb_tool(
            action="file",
            title="Sparse MoE",
            page_type="concept",
            content="# Sparse MoE\n\nSee [[missing-page]].",
        )

        output = run_wiki_command("lint", "")

        assert "Wiki lint complete" in output
        assert "Issue count:" in output

    def test_ingest_local_markdown_file_copies_raw_and_seeds_article(self, tmp_path, monkeypatch):
        wiki_root = tmp_path / "Wiki"
        source_file = tmp_path / "source.md"
        source_file.write_text(
            "# Mixture of Experts\n\n"
            "OpenAI and Anthropic both study sparse routing systems.\n\n"
            "## Router Design\n"
            "A routing architecture.\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("LLM_WIKI_PATH", str(wiki_root))

        output = run_wiki_command("ingest", str(source_file))

        assert "Wiki ingest complete" in output
        raw_copy = wiki_root / "raw" / "articles" / "source.md"
        assert raw_copy.exists()
        assert "Mixture of Experts" in raw_copy.read_text(encoding="utf-8")
        article_page = wiki_root / "articles" / "mixture-of-experts.md"
        assert article_page.exists()
        assert (wiki_root / "entities" / "openai-and-anthropic.md").exists()
        assert (wiki_root / "concepts" / "router-design.md").exists()
        state_file = wiki_root / ".hermes-wiki-last-ingest.json"
        assert state_file.exists()

    def test_review_reports_last_ingest_and_followups(self, tmp_path, monkeypatch):
        wiki_root = tmp_path / "Wiki"
        source_file = tmp_path / "source.md"
        source_file.write_text(
            "# Mixture of Experts\n\n"
            "OpenAI and Anthropic both study sparse routing systems.\n\n"
            "## Router Design\n"
            "A routing architecture.\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("LLM_WIKI_PATH", str(wiki_root))

        run_wiki_command("ingest", str(source_file))
        output = run_wiki_command("review", "")

        assert "Wiki review" in output
        assert "mixture-of-experts.md" in output
        assert "openai-and-anthropic.md" in output
        assert "Suggested follow-ups:" in output

    def test_review_without_history_reports_next_step(self, tmp_path, monkeypatch):
        wiki_root = tmp_path / "Wiki"
        monkeypatch.setenv("LLM_WIKI_PATH", str(wiki_root))

        output = run_wiki_command("review", "")

        assert "Wiki review unavailable" in output
        assert "Run /wiki ingest <url-or-local-file> first." in output

    def test_map_reports_empty_wiki_next_steps(self, tmp_path, monkeypatch):
        wiki_root = tmp_path / "Wiki"
        monkeypatch.setenv("LLM_WIKI_PATH", str(wiki_root))

        output = run_wiki_command("map", "")

        assert "Wiki Map" in output
        assert "Run /wiki init to create the wiki structure." in output

    def test_map_reports_recent_pages_and_latest_ingest(self, tmp_path, monkeypatch):
        wiki_root = tmp_path / "Wiki"
        source_file = tmp_path / "source.md"
        source_file.write_text(
            "# Mixture of Experts\n\n"
            "OpenAI and Anthropic both study sparse routing systems.\n\n"
            "## Router Design\n"
            "A routing architecture.\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("LLM_WIKI_PATH", str(wiki_root))

        run_wiki_command("ingest", str(source_file))
        output = run_wiki_command("map", "")

        assert "Wiki Map" in output
        assert "Recent Pages:" in output
        assert "articles/mixture-of-experts.md" in output
        assert "Latest Ingest:" in output
        assert str(source_file) in output
        assert "Review the latest ingest and confirm its summary and linked pages before relying on it." in output

    def test_file_query_creates_query_page(self, tmp_path, monkeypatch):
        wiki_root = tmp_path / "Wiki"
        monkeypatch.setenv("LLM_WIKI_PATH", str(wiki_root))

        output = run_wiki_command(
            "file-query",
            "What is the Hermes wiki for? :: It is the persistent markdown memory layer Hermes maintains for durable research knowledge.",
        )

        assert "Wiki query filed" in output
        query_page = wiki_root / "queries" / "what-is-the-hermes-wiki-for.md"
        assert query_page.exists()
        query_text = query_page.read_text(encoding="utf-8")
        assert "## Answer" in query_text
        assert "persistent markdown memory layer" in query_text

    def test_file_query_links_latest_ingest_context(self, tmp_path, monkeypatch):
        wiki_root = tmp_path / "Wiki"
        source_file = tmp_path / "source.md"
        source_file.write_text(
            "# Mixture of Experts\n\n"
            "OpenAI and Anthropic both study sparse routing systems.\n\n"
            "## Router Design\n"
            "A routing architecture.\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("LLM_WIKI_PATH", str(wiki_root))

        run_wiki_command("ingest", str(source_file))
        run_wiki_command(
            "file-query",
            "What did the source say about routing? :: It described a routing architecture and linked it to sparse expert systems research.",
        )

        query_page = wiki_root / "queries" / "what-did-the-source-say-about-routing.md"
        query_text = query_page.read_text(encoding="utf-8")
        assert "[[articles/mixture-of-experts.md|Mixture Of Experts]]" in query_text
        assert "`raw/articles/source.md`" in query_text
        assert "[[entities/openai-and-anthropic.md|Openai And Anthropic]]" in query_text

    def test_compare_creates_comparison_page(self, tmp_path, monkeypatch):
        wiki_root = tmp_path / "Wiki"
        monkeypatch.setenv("LLM_WIKI_PATH", str(wiki_root))

        output = run_wiki_command(
            "compare",
            "Agents SDK vs MCP tools :: Agents SDK => Better for stateful loops and built-in session semantics. || MCP tools => Better for explicit external tool boundaries.",
        )

        assert "Wiki comparison filed" in output
        comparison_page = wiki_root / "comparisons" / "agents-sdk-vs-mcp-tools.md"
        assert comparison_page.exists()
        comparison_text = comparison_page.read_text(encoding="utf-8")
        assert "## Comparison" in comparison_text
        assert "### Agents SDK" in comparison_text
        assert "### MCP tools" in comparison_text

    def test_compare_links_latest_ingest_context(self, tmp_path, monkeypatch):
        wiki_root = tmp_path / "Wiki"
        source_file = tmp_path / "source.md"
        source_file.write_text(
            "# Mixture of Experts\n\n"
            "OpenAI and Anthropic both study sparse routing systems.\n\n"
            "## Router Design\n"
            "A routing architecture.\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("LLM_WIKI_PATH", str(wiki_root))

        run_wiki_command("ingest", str(source_file))
        run_wiki_command(
            "compare",
            "Dense vs sparse routing :: Dense routing => Simpler execution and predictable capacity use. || Sparse routing => Better specialization when routing quality is high.",
        )

        comparison_page = wiki_root / "comparisons" / "dense-vs-sparse-routing.md"
        comparison_text = comparison_page.read_text(encoding="utf-8")
        assert "[[articles/mixture-of-experts.md|Mixture Of Experts]]" in comparison_text
        assert "`raw/articles/source.md`" in comparison_text
        assert "[[concepts/router-design.md|Router Design]]" in comparison_text

    def test_entity_creates_entity_page(self, tmp_path, monkeypatch):
        wiki_root = tmp_path / "Wiki"
        monkeypatch.setenv("LLM_WIKI_PATH", str(wiki_root))

        output = run_wiki_command(
            "entity",
            "OpenAI :: Model provider and research lab relevant to the current topic.",
        )

        assert "Wiki entity filed" in output
        entity_page = wiki_root / "entities" / "openai.md"
        assert entity_page.exists()
        entity_text = entity_page.read_text(encoding="utf-8")
        assert "## Overview" in entity_text
        assert "Model provider and research lab" in entity_text

    def test_entity_links_latest_ingest_context(self, tmp_path, monkeypatch):
        wiki_root = tmp_path / "Wiki"
        source_file = tmp_path / "source.md"
        source_file.write_text(
            "# Mixture of Experts\n\n"
            "OpenAI and Anthropic both study sparse routing systems.\n\n"
            "## Router Design\n"
            "A routing architecture.\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("LLM_WIKI_PATH", str(wiki_root))

        run_wiki_command("ingest", str(source_file))
        run_wiki_command(
            "entity",
            "Anthropic :: Research lab frequently discussed alongside OpenAI in sparse routing work.",
        )

        entity_page = wiki_root / "entities" / "anthropic.md"
        entity_text = entity_page.read_text(encoding="utf-8")
        assert "[[articles/mixture-of-experts.md|Mixture Of Experts]]" in entity_text
        assert "`raw/articles/source.md`" in entity_text
        assert "[[concepts/router-design.md|Router Design]]" in entity_text

    def test_concept_creates_concept_page(self, tmp_path, monkeypatch):
        wiki_root = tmp_path / "Wiki"
        monkeypatch.setenv("LLM_WIKI_PATH", str(wiki_root))

        output = run_wiki_command(
            "concept",
            "Sparse routing :: A routing pattern where only a subset of experts activates for each token.",
        )

        assert "Wiki concept filed" in output
        concept_page = wiki_root / "concepts" / "sparse-routing.md"
        assert concept_page.exists()
        concept_text = concept_page.read_text(encoding="utf-8")
        assert "## Definition" in concept_text
        assert "subset of experts activates" in concept_text

    def test_concept_links_latest_ingest_context(self, tmp_path, monkeypatch):
        wiki_root = tmp_path / "Wiki"
        source_file = tmp_path / "source.md"
        source_file.write_text(
            "# Mixture of Experts\n\n"
            "OpenAI and Anthropic both study sparse routing systems.\n\n"
            "## Router Design\n"
            "A routing architecture.\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("LLM_WIKI_PATH", str(wiki_root))

        run_wiki_command("ingest", str(source_file))
        run_wiki_command(
            "concept",
            "Conditional compute :: A pattern where computation varies depending on the token or input path.",
        )

        concept_page = wiki_root / "concepts" / "conditional-compute.md"
        concept_text = concept_page.read_text(encoding="utf-8")
        assert "[[articles/mixture-of-experts.md|Mixture Of Experts]]" in concept_text
        assert "`raw/articles/source.md`" in concept_text
        assert "[[entities/openai-and-anthropic.md|Openai And Anthropic]]" in concept_text

    def test_help_for_unknown_subcommand(self):
        output = run_wiki_command("unknown", "")
        assert "Unknown /wiki subcommand" in output
