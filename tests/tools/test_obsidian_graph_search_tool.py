from __future__ import annotations

import json
from pathlib import Path

from plugins.memory.obsidian_vault.graph import (
    build_graph,
    build_note_lookup,
    expand_graph,
    resolve_note_reference,
    slugify_path,
)
from plugins.memory.obsidian_vault.paths import save_provider_config
from tools import obsidian_graph_search_tool as tool


def test_graph_parses_wikilinks_backlinks_tags_and_rejects_escape(tmp_path):
    vault = tmp_path / "vault"
    (vault / "20 Projects").mkdir(parents=True)
    (vault / "30 Decisions").mkdir(parents=True)
    (vault / "20 Projects" / "Hermes.md").write_text(
        "---\ntags:\n  - memory/qmd\n---\n# Hermes\nLinks to [[30 Decisions/Hermes Memory Architecture|architecture]] and [[../Outside]].\n",
        encoding="utf-8",
    )
    (vault / "30 Decisions" / "Hermes Memory Architecture.md").write_text(
        "# Architecture\nBack to [[Hermes]] #memory/qmd\n",
        encoding="utf-8",
    )
    (tmp_path / "Outside.md").write_text("nope", encoding="utf-8")

    lookup = build_note_lookup(vault)
    assert lookup[slugify_path("20 Projects/Hermes.md")] == "20 Projects/Hermes.md"
    assert (
        resolve_note_reference(vault, "20 Projects/Hermes.md", "30 Decisions/Hermes Memory Architecture|architecture", lookup)
        == "30 Decisions/Hermes Memory Architecture.md"
    )
    assert resolve_note_reference(vault, "20 Projects/Hermes.md", "../Outside", lookup) is None

    graph = build_graph(vault)
    assert "30 Decisions/Hermes Memory Architecture.md" in graph["20 Projects/Hermes.md"].links
    assert "20 Projects/Hermes.md" in graph["30 Decisions/Hermes Memory Architecture.md"].backlinks
    assert "memory/qmd" in graph["20 Projects/Hermes.md"].tags


def test_expand_graph_returns_seed_and_neighbors(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Seed.md").write_text("# Seed\nSee [[Linked]].\n", encoding="utf-8")
    (vault / "Linked.md").write_text("# Linked\n", encoding="utf-8")
    (vault / "Backlink.md").write_text("# Backlink\nMentions [[Seed]].\n", encoding="utf-8")

    results = expand_graph(vault, {"Seed.md": 0.91}, depth=1, max_neighbors=5)
    by_path = {item.path: item for item in results}
    assert by_path["Seed.md"].reasons == {"semantic_seed"}
    assert "wikilink" in by_path["Linked.md"].reasons
    assert "backlink" in by_path["Backlink.md"].reasons


def test_obsidian_graph_search_pairs_qmd_seed_with_graph(monkeypatch, tmp_path):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    vault = tmp_path / "vault"
    (vault / "20 Projects").mkdir(parents=True)
    (vault / "30 Decisions").mkdir(parents=True)
    (vault / "20 Projects" / "Hermes.md").write_text(
        "# Hermes\nSee [[30 Decisions/Hermes Memory Architecture]].\n",
        encoding="utf-8",
    )
    (vault / "30 Decisions" / "Hermes Memory Architecture.md").write_text(
        "# Hermes Memory Architecture\nQMD plus graph expansion.\n",
        encoding="utf-8",
    )
    save_provider_config(hermes_home, {"vault_path": str(vault)})

    def fake_qmd(query, collections, limit):
        assert query == "Hermes memory"
        assert collections == ["hermes-memory"]
        return [
            {
                "docid": "#abc123",
                "score": 0.93,
                "file": "qmd://hermes-memory/20-projects/hermes.md",
                "title": "Hermes",
                "snippet": "seed snippet",
            }
        ]

    monkeypatch.setattr(tool, "_run_qmd_query", fake_qmd)
    payload = json.loads(
        tool.obsidian_graph_search_tool(
            args={"query": "Hermes memory", "limit": 1, "graph_depth": 1, "max_neighbors": 3}
        )
    )

    paths = [item["path"] for item in payload["results"]]
    assert paths[0] == "20 Projects/Hermes.md"
    assert "30 Decisions/Hermes Memory Architecture.md" in paths
    neighbor = next(item for item in payload["results"] if item["path"].startswith("30 Decisions/"))
    assert neighbor["reasons"] == ["wikilink"]


def test_qmd_interrupted_system_call_returns_structured_error(monkeypatch, tmp_path):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    vault = tmp_path / "vault"
    vault.mkdir()
    save_provider_config(hermes_home, {"vault_path": str(vault)})

    def broken_qmd(query, collections, limit):
        raise RuntimeError("qmd query failed: Interrupted system call")

    monkeypatch.setattr(tool, "_run_qmd_query", broken_qmd)
    payload = json.loads(tool.obsidian_graph_search_tool(args={"query": "memory"}))
    assert "Interrupted system call" in payload["error"]
