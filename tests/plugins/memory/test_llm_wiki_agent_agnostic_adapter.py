"""Hermes integration tests for agent-agnostic LLM Wiki adapter primitives."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import json

import pytest

import hermes_wiki.tool_adapter as tool_adapter_module
from agent.memory_manager import MemoryManager
from hermes_wiki.capabilities import WikiCapabilities, capability_preset
from hermes_wiki.mcp_server import build_mcp_server, mcp_tool_names_for_context
from hermes_wiki.tool_adapter import LLMWikiToolAdapter
from plugins.memory.llm_wiki import LLMWikiMemoryProvider


class FakeConfig:
    def __init__(self, wiki_path):
        self.wiki_path = wiki_path


class FakeSearch:
    def __init__(self) -> None:
        self.calls = []

    def search(self, query, limit=5, exclude_sources=False, search_mode="dense"):
        self.calls.append((query, limit, exclude_sources, search_mode))
        return [
            {
                "page_path": "concepts/example.md",
                "title": "Example",
                "text": "ExactModelName appears here",
                "score": 0.9,
            }
        ]


class FakeEngine:
    def __init__(self) -> None:
        self.search = FakeSearch()
        self.query_calls = []
        self.ingest_calls = []
        self.update_calls = []
        self.reindex_calls = 0

    def status(self):
        return {"wiki": "/tmp/wiki", "total_pages": 1}

    def orient(self):
        return "# Orientation"

    def query(self, question, file_result=False, log_query=False):
        self.query_calls.append((question, file_result, log_query))
        return {"answer": "ok", "file_result": file_result, "log_query": log_query}

    def lint(self, write_log=False):
        return {"issues": [], "write_log": write_log}

    def ingest_file(self, file_path, dry_run=True):
        self.ingest_calls.append((file_path, dry_run))
        return {"file_path": file_path, "dry_run": dry_run}

    def update_page(self, page, body, *, frontmatter_updates=None, source_refs=None, reason="", reindex=True):
        self.update_calls.append((page, body, frontmatter_updates or {}, source_refs or [], reason, reindex))
        return {"page": page, "updated": True, "chunks_indexed": 2}

    def reindex(self):
        self.reindex_calls += 1
        return {"ok": True}


def test_tool_adapter_default_engine_factory_uses_writable_engine_for_trusted_context(monkeypatch):
    constructed = []

    class Engine:
        def __init__(self, config, *, read_only=True):
            constructed.append(read_only)

        def status(self):
            return {"initialized": True}

    monkeypatch.setattr(tool_adapter_module, "WikiEngine", Engine)

    LLMWikiToolAdapter(capabilities=capability_preset("mcp")).call("wiki_status", {})
    LLMWikiToolAdapter(capabilities=capability_preset("primary")).call("wiki_status", {})

    assert constructed == [True, False]


def test_capability_presets_are_host_agnostic_and_safe_by_default():
    mcp = capability_preset("mcp")
    primary = capability_preset("primary")
    unknown = capability_preset("openclaw-worker")

    assert mcp.can_read is True
    assert mcp.can_query is True
    assert mcp.can_ingest is False
    assert unknown == mcp
    assert primary.can_ingest is True
    assert primary.can_mutate_canonical is True


def test_tool_adapter_schemas_are_filtered_to_granted_capabilities():
    mcp_adapter = LLMWikiToolAdapter(engine_factory=FakeEngine, capabilities=capability_preset("mcp"))
    trusted_adapter = LLMWikiToolAdapter(engine_factory=FakeEngine, capabilities=capability_preset("primary"))

    mcp_tool_names = {schema["name"] for schema in mcp_adapter.tool_schemas()}
    trusted_tool_names = {schema["name"] for schema in trusted_adapter.tool_schemas()}

    assert "wiki_capabilities" in mcp_tool_names
    assert "wiki_search" in mcp_tool_names
    assert "wiki_query" in mcp_tool_names
    assert "wiki_propose" not in mcp_tool_names
    assert "wiki_ingest" not in mcp_tool_names
    assert "wiki_reindex" not in mcp_tool_names
    assert "wiki_update" not in mcp_tool_names
    assert "wiki_ingest" in trusted_tool_names
    assert "wiki_reindex" not in trusted_tool_names
    assert "wiki_update" in trusted_tool_names


def test_tool_adapter_reports_capabilities_for_external_agents():
    adapter = LLMWikiToolAdapter(engine_factory=FakeEngine, capabilities=capability_preset("mcp"))

    result = adapter.call("wiki_capabilities", {})

    assert result["can_read"] is True
    assert result["can_query"] is True
    assert result["can_ingest"] is False
    assert result["safe_default"] is True
    assert "wiki_propose" not in result["exposed_tools"]


def test_tool_adapter_rejects_removed_proposal_tool(tmp_path):
    adapter = LLMWikiToolAdapter(config=FakeConfig(tmp_path / "wiki"), engine_factory=FakeEngine, capabilities=capability_preset("mcp"))

    with pytest.raises(KeyError, match="wiki_propose"):
        adapter.call(
            "wiki_propose",
            {
                "title": "Remember adapter contract",
                "source_refs": ["raw/articles/adapter-contract.md"],
                "queue": True,
            },
        )

    assert not (tmp_path / "wiki" / "proposals").exists()


def test_mcp_tool_names_follow_context_capabilities():
    default_names = set(mcp_tool_names_for_context("mcp"))
    trusted_names = set(mcp_tool_names_for_context("primary"))

    assert "wiki_capabilities" in default_names
    assert "wiki_search" in default_names
    assert "wiki_query" in default_names
    assert "wiki_ingest" not in default_names
    assert "wiki_reindex" not in default_names
    assert "wiki_update" not in default_names
    assert "wiki_ingest" in trusted_names
    assert "wiki_reindex" not in trusted_names
    assert "wiki_update" in trusted_names


def test_mcp_server_registers_canonical_update_only_for_trusted_context():
    default_server = build_mcp_server(engine_factory=FakeEngine, context="mcp")
    trusted_server = build_mcp_server(engine_factory=FakeEngine, context="primary")

    default_names = {tool.name for tool in default_server._tool_manager.list_tools()}
    trusted_names = {tool.name for tool in trusted_server._tool_manager.list_tools()}

    assert "wiki_update" not in default_names
    assert "wiki_update" in trusted_names


def test_tool_adapter_denies_mcp_ingest_direct_dispatch_and_preserves_hybrid_search():
    engine = FakeEngine()
    adapter = LLMWikiToolAdapter(engine_factory=lambda: engine, capabilities=capability_preset("mcp"))

    search_result = adapter.call(
        "wiki_search",
        {"query": "ExactModelName", "limit": 99, "exclude_sources": True, "search_mode": "hybrid"},
    )
    try:
        adapter.call("wiki_ingest", {"file_path": "/tmp/source.md", "dry_run": True})
    except PermissionError as exc:
        assert "ingest" in str(exc)
    else:  # pragma: no cover - explicit failure path
        raise AssertionError("ingest direct dispatch should be denied outside primary context")

    assert engine.search.calls == [("ExactModelName", 20, True, "hybrid")]
    assert search_result[0]["page_path"] == "concepts/example.md"
    assert engine.ingest_calls == []


def test_tool_adapter_denies_requested_query_and_lint_writes_without_capability():
    engine = FakeEngine()
    adapter = LLMWikiToolAdapter(engine_factory=lambda: engine, capabilities=capability_preset("mcp"))

    assert adapter.call("wiki_query", {"question": "What next?", "file_result": False, "log_query": False})["answer"] == "ok"

    for tool_name, args, expected in (
        ("wiki_query", {"question": "What next?", "file_result": True}, "mutate_canonical"),
        ("wiki_query", {"question": "What next?", "log_query": True}, "log_query"),
        ("wiki_lint", {"write_log": True}, "write_report"),
    ):
        try:
            adapter.call(tool_name, args)
        except PermissionError as exc:
            assert expected in str(exc)
        else:  # pragma: no cover - explicit failure path
            raise AssertionError(f"{tool_name} should deny requested side effect")

    assert engine.query_calls == [("What next?", False, False)]


def test_tool_adapter_does_not_expose_manual_reindex_tool():
    adapter = LLMWikiToolAdapter(engine_factory=FakeEngine, capabilities=capability_preset("subagent"))

    try:
        adapter.call("wiki_reindex", {})
    except KeyError as exc:
        assert "wiki_reindex" in str(exc)
    else:  # pragma: no cover - explicit failure path
        raise AssertionError("wiki_reindex should not be a manually callable LLM tool")


def test_tool_adapter_denies_canonical_update_without_primary_capability():
    engine = FakeEngine()
    adapter = LLMWikiToolAdapter(engine_factory=lambda: engine, capabilities=capability_preset("mcp"))

    try:
        adapter.call(
            "wiki_update",
            {
                "page": "concepts/memory-policy.md",
                "body": "# Memory Policy\n\nUpdated body.",
                "source_refs": ["raw/articles/source.md"],
                "reason": "source-backed correction",
            },
        )
    except PermissionError as exc:
        assert "mutate_canonical" in str(exc)
    else:  # pragma: no cover - explicit failure path
        raise AssertionError("canonical update should be denied outside primary context")

    assert engine.update_calls == []


def test_tool_adapter_allows_primary_canonical_update():
    engine = FakeEngine()
    adapter = LLMWikiToolAdapter(engine_factory=lambda: engine, capabilities=capability_preset("primary"))

    result = adapter.call(
        "wiki_update",
        {
            "page": "concepts/memory-policy.md",
            "body": "# Memory Policy\n\nUpdated body.",
            "frontmatter_updates": {"confidence": "high"},
            "source_refs": ["raw/articles/source.md"],
            "reason": "source-backed correction",
        },
    )

    assert result == {"page": "concepts/memory-policy.md", "updated": True, "chunks_indexed": 2}
    assert engine.update_calls == [(
        "concepts/memory-policy.md",
        "# Memory Policy\n\nUpdated body.",
        {"confidence": "high"},
        ["raw/articles/source.md"],
        "source-backed correction",
        True,
    )]


def test_hermes_provider_system_prompt_routes_memory_relevant_questions_to_wiki_tools():
    provider = LLMWikiMemoryProvider()

    block = provider.system_prompt_block()

    assert "use wiki_search whenever durable memory could improve correctness" in block
    assert "prior decisions" in block
    assert "preferences" in block
    assert "goals" in block
    assert "what's next" in block
    assert "Do not wait for explicit memory requests" in block
    assert "Prefetch snippets are only hints" in block
    assert "Reference wiki/source pages" in block
    assert "Keep the wiki current" in block
    assert "wiki_search" in block
    assert "wiki_read" in block
    assert "wiki_query" in block
    assert "wiki_update" in block
    assert "wiki_propose" not in block
    assert "proposal" not in block.lower()


def test_hermes_provider_exposes_shared_capability_and_update_tools():
    provider = LLMWikiMemoryProvider()
    tool_names = {schema["name"] for schema in provider.get_tool_schemas()}

    assert "wiki_capabilities" in tool_names
    assert "wiki_propose" not in tool_names
    assert "wiki_search" in tool_names
    assert "wiki_read" in tool_names


def test_hermes_provider_handles_shared_capabilities_tool(tmp_path):
    provider = LLMWikiMemoryProvider()
    provider.initialize("s1", hermes_home=str(tmp_path), agent_context="cron")

    result = json.loads(provider.handle_tool_call("wiki_capabilities", {}))

    assert result["can_read"] is True
    assert "can_queue_proposal" not in result
    assert result["can_ingest"] is False
    assert "wiki_propose" not in result["exposed_tools"]
    assert "wiki_read" in result["exposed_tools"]


def test_hermes_provider_bool_parser_has_no_python_truthiness_fallback():
    source = Path("plugins/memory/llm_wiki/__init__.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    violations = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "_as_bool":
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            if not isinstance(func, ast.Name) or func.id != "bool" or len(child.args) != 1:
                continue
            arg = child.args[0]
            if isinstance(arg, ast.Name) and arg.id == "value":
                violations.append(child.lineno)

    assert violations == []


def test_hermes_provider_bool_args_fail_closed_for_ambiguous_values(monkeypatch, tmp_path):
    engine = FakeEngine()
    provider = LLMWikiMemoryProvider()
    provider.initialize("s1", hermes_home=str(tmp_path), agent_context="primary")
    monkeypatch.setattr(provider, "_engine", lambda: engine)

    query = provider.handle_tool_call(
        "wiki_query",
        {"question": "what", "file_result": ["yes"], "log_query": {"enabled": True}},
    )
    nan_query = provider.handle_tool_call("wiki_query", {"question": "nan", "file_result": math.nan, "log_query": math.nan})
    ingest = json.loads(provider.handle_tool_call("wiki_ingest", {"file_path": "/tmp/source.md", "dry_run": math.nan}))

    assert "file_result': False" in query or '"file_result": false' in query.lower()
    assert "log_query': False" in query or '"log_query": false' in query.lower()
    assert "file_result': False" in nan_query or '"file_result": false' in nan_query.lower()
    assert "log_query': False" in nan_query or '"log_query": false' in nan_query.lower()
    assert ingest["dry_run"] is True
    assert engine.ingest_calls == [("/tmp/source.md", True)]


def test_hermes_provider_handles_shared_introspection_tool(monkeypatch, tmp_path):
    if "wiki_introspect" not in {schema["name"] for schema in LLMWikiToolAdapter(engine_factory=FakeEngine, capabilities=capability_preset("mcp")).tool_schemas()}:
        pytest.skip("standalone hermes-llm-wiki version does not expose wiki_introspect yet")
    engine = FakeEngine()
    provider = LLMWikiMemoryProvider()
    provider.initialize("s1", hermes_home=str(tmp_path), agent_context="cron")
    monkeypatch.setattr(provider, "_engine", lambda: engine)

    payload = json.loads(
        provider.handle_tool_call(
            "wiki_introspect",
            {
                "query": "ExactModelName",
                "top_k": "2",
                "expected_pages": ["concepts/example.md"],
                "compare_modes": True,
            },
        )
    )

    assert payload["passed"] is True
    assert set(payload["modes"]) == {"dense", "sparse", "hybrid"}
    assert payload["modes"]["dense"]["expected_pages"] == ["concepts/example.md"]


def test_hermes_provider_rejects_ambiguous_introspection_mode_args(monkeypatch, tmp_path):
    if "wiki_introspect" not in {schema["name"] for schema in LLMWikiToolAdapter(engine_factory=FakeEngine, capabilities=capability_preset("mcp")).tool_schemas()}:
        pytest.skip("standalone hermes-llm-wiki version does not expose wiki_introspect yet")
    engine = FakeEngine()
    provider = LLMWikiMemoryProvider()
    provider.initialize("s1", hermes_home=str(tmp_path), agent_context="cron")
    monkeypatch.setattr(provider, "_engine", lambda: engine)

    result = provider.handle_tool_call(
        "wiki_introspect",
        {"query": "ExactModelName", "compare_modes": True, "search_mode": "hybrid"},
    )

    assert "Error:" in result
    assert "compare_modes" in result


def test_hermes_provider_rejects_removed_proposal_tool(monkeypatch, tmp_path):
    class AdapterShouldNotBeCalled:
        def call(self, name, args):  # pragma: no cover - failure path
            raise AssertionError("removed proposal tool must not delegate")

    provider = LLMWikiMemoryProvider()
    provider.initialize("s1", hermes_home=str(tmp_path), agent_context="cron")
    monkeypatch.setattr(provider, "_adapter", lambda: AdapterShouldNotBeCalled())

    with pytest.raises(NotImplementedError, match="wiki_propose"):
        provider.handle_tool_call("wiki_propose", {"title": "Removed", "queue": True})

    assert not (tmp_path / "wiki" / "personal" / "proposals").exists()


def test_memory_manager_routes_llm_wiki_shared_tools(tmp_path):
    provider = LLMWikiMemoryProvider()
    provider.initialize("s1", hermes_home=str(tmp_path), agent_context="cron")
    manager = MemoryManager()
    manager.add_provider(provider)

    assert manager.has_tool("wiki_capabilities")
    assert not manager.has_tool("wiki_propose")
    result = json.loads(manager.handle_tool_call("wiki_capabilities", {}))
    assert "can_queue_proposal" not in result


def test_hermes_provider_maps_agent_context_to_generic_capabilities(tmp_path):
    provider = LLMWikiMemoryProvider()
    provider.initialize("s1", hermes_home=str(tmp_path), agent_context="cron")

    assert isinstance(provider._capabilities, WikiCapabilities)
    assert provider._capabilities == capability_preset("cron")
    assert provider._writes_allowed() is False


def test_hermes_provider_returns_error_for_invalid_search_mode(monkeypatch, tmp_path):
    engine = FakeEngine()
    provider = LLMWikiMemoryProvider()
    provider.initialize("s1", hermes_home=str(tmp_path), agent_context="primary")
    monkeypatch.setattr(provider, "_engine", lambda: engine)

    result = provider.handle_tool_call("wiki_search", {"query": "ExactModelName", "search_mode": "bogus"})

    assert "Error:" in result
    assert "search_mode" in result
    assert engine.search.calls == []


def test_hermes_provider_uses_tool_adapter_for_shared_search_semantics(monkeypatch, tmp_path):
    engine = FakeEngine()
    provider = LLMWikiMemoryProvider()
    provider.initialize("s1", hermes_home=str(tmp_path), agent_context="primary")
    monkeypatch.setattr(provider, "_engine", lambda: engine)

    payload = json.loads(
        provider.handle_tool_call(
            "wiki_search",
            {"query": "ExactModelName", "limit": "99", "exclude_sources": "true", "search_mode": "hybrid"},
        )
    )

    assert engine.search.calls == [("ExactModelName", 20, True, "hybrid")]
    assert payload[0]["page_path"] == "concepts/example.md"

def test_disabled_context_provider_blocks_direct_read_tools(monkeypatch, tmp_path):
    page = tmp_path / "wiki" / "personal" / "concepts" / "secret.md"
    page.parent.mkdir(parents=True)
    page.write_text("# Secret\n\nShould not be readable", encoding="utf-8")

    engine = FakeEngine()
    provider = LLMWikiMemoryProvider()
    provider.initialize("s1", hermes_home=str(tmp_path), agent_context="disabled")
    monkeypatch.setattr(provider, "_engine", lambda: engine)

    status = provider.handle_tool_call("wiki_status", {})
    orient = provider.handle_tool_call("wiki_orient", {})
    read = provider.handle_tool_call("wiki_read", {"page": "concepts/secret.md"})

    assert "capability denied" in status.lower()
    assert "capability denied" in orient.lower()
    assert "capability denied" in read.lower()
    assert "Should not be readable" not in read


def test_disabled_context_provider_prefetch_is_noop(monkeypatch, tmp_path):
    provider = LLMWikiMemoryProvider()
    provider.initialize("s1", hermes_home=str(tmp_path), agent_context="disabled")
    monkeypatch.setattr(
        provider,
        "_engine",
        lambda: (_ for _ in ()).throw(AssertionError("disabled prefetch must not load engine")),
    )

    assert provider.prefetch("memory policy") == ""


def test_disabled_context_provider_blocks_direct_query_and_lint(monkeypatch, tmp_path):
    engine = FakeEngine()
    provider = LLMWikiMemoryProvider()
    provider.initialize("s1", hermes_home=str(tmp_path), agent_context="disabled")
    monkeypatch.setattr(provider, "_engine", lambda: engine)

    query = provider.handle_tool_call("wiki_query", {"question": "What should be blocked?"})
    lint = provider.handle_tool_call("wiki_lint", {})

    assert "capability denied" in query.lower()
    assert "capability denied" in lint.lower()
    assert engine.query_calls == []
