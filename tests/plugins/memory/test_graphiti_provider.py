import asyncio
import json

from plugins.memory.graphiti import (
    GraphitiMemoryProvider,
    _extract_json,
    _load_config,
)


class FakeDriver:
    def __init__(self):
        self.queries = []

    async def execute_query(self, query):
        self.queries.append(query)
        if "Episodic" in query:
            return ([
                {"name": "episode-1", "text": "Hermes Graphiti provider uses local Kuzu with Ollama qwen3 embeddings."},
                {"name": "episode-2", "text": "Unrelated memory."},
            ], None, None)
        if "Entity" in query:
            return ([
                {"name": "Ollama qwen3 embeddings", "text": "Local embedding model used by Graphiti provider."},
            ], None, None)
        return ([], None, None)


class FakeGraphiti:
    def __init__(self):
        self.driver = FakeDriver()


def test_extract_json_accepts_markdown_fenced_json():
    assert _extract_json('```json\n{"ok": true}\n```') == {"ok": True}


def test_load_config_reads_file_but_keeps_group_id_empty(tmp_path, monkeypatch):
    monkeypatch.delenv("GRAPHITI_GROUP_ID", raising=False)
    (tmp_path / "graphiti.json").write_text(
        json.dumps({"group_id": "", "kuzu_path": "$HERMES_HOME/custom.kuzu"}),
        encoding="utf-8",
    )

    cfg = _load_config(str(tmp_path))

    assert cfg["group_id"] == ""
    assert cfg["kuzu_path"] == str(tmp_path / "custom.kuzu")


def test_save_config_drops_secret_key(tmp_path):
    provider = GraphitiMemoryProvider()
    provider.save_config({"llm_api_key": "secret-value", "llm_model": "qwen/qwen3.6-plus"}, str(tmp_path))

    stored = json.loads((tmp_path / "graphiti.json").read_text(encoding="utf-8"))

    assert "llm_api_key" not in stored
    assert stored["llm_model"] == "qwen/qwen3.6-plus"


def test_status_reports_key_presence_without_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-value")
    provider = GraphitiMemoryProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), user_id="zidane")

    status = json.loads(provider.handle_tool_call("graphiti_status", {}))

    assert status["provider"] == "graphiti"
    assert status["has_llm_key"] is True
    assert "secret-value" not in json.dumps(status)


def test_fallback_kuzu_search_reads_episode_and_entity_text(tmp_path):
    provider = GraphitiMemoryProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), user_id="zidane")
    object.__setattr__(provider, "_graphiti", FakeGraphiti())

    result = asyncio.run(provider._fallback_kuzu_search("Graphiti Ollama qwen3", 5))

    joined = "\n".join(result)
    assert "episode-1" in joined
    assert "Ollama qwen3 embeddings" in joined
    assert "Unrelated memory" not in joined


def test_tool_schema_exposes_search_remember_and_status():
    provider = GraphitiMemoryProvider()

    names = {schema["name"] for schema in provider.get_tool_schemas()}

    assert names == {"graphiti_search", "graphiti_remember", "graphiti_status"}


def test_search_tool_handles_malformed_top_k_without_raising(tmp_path):
    provider = GraphitiMemoryProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), user_id="zidane")

    result = json.loads(provider.handle_tool_call("graphiti_search", {"query": "Graphiti", "top_k": "not-an-int"}))

    assert "error" in result
    assert "invalid literal" in result["error"]
