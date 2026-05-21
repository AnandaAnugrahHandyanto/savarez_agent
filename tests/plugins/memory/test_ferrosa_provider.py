"""Regression tests for the Ferrosa memory provider.

The provider must use the same configured HTTPS MCP endpoint as Hermes and
persist full session transcripts via fmem context segments, not just best-effort
entity snippets.
"""

from __future__ import annotations

import json
from pathlib import Path


class RecordingClient:
    def __init__(self):
        self.calls = []

    def call(self, tool_name, arguments):
        self.calls.append((tool_name, arguments))
        if tool_name == "get_stats":
            return {"entity_count": 1, "fold_count": 0}
        if tool_name == "ingest_context_segments":
            return {"segments_created": len(arguments.get("messages", [])), "edges_created": 0}
        if tool_name == "run_consolidation":
            return {"ok": True}
        return {}


def test_resolve_url_reads_hermes_mcp_https_config(tmp_path, monkeypatch):
    from plugins.memory.ferrosa import _resolve_url

    monkeypatch.delenv("FERROSA_MEMORY_URL", raising=False)
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        "mcp_servers:\n"
        "  ferrosa-memory:\n"
        "    url: https://ferrosa_user:ferrosa_user@127.0.0.1:18765/mcp\n"
        "    ssl_verify: false\n"
    )

    assert (
        _resolve_url({}, hermes_home=str(hermes_home))
        == "https://ferrosa_user:ferrosa_user@127.0.0.1:18765/mcp"
    )


def test_saved_plugin_config_overrides_hermes_mcp_config(tmp_path, monkeypatch):
    from plugins.memory.ferrosa import _load_saved_config, _resolve_url

    monkeypatch.delenv("FERROSA_MEMORY_URL", raising=False)
    hermes_home = tmp_path / "hermes"
    plugin_dir = hermes_home / "plugins" / "ferrosa"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "config.json").write_text(json.dumps({"url": "https://saved.example/mcp"}))
    (hermes_home / "config.yaml").write_text(
        "mcp_servers:\n"
        "  ferrosa-memory:\n"
        "    url: https://config.example/mcp\n"
    )

    saved = _load_saved_config(str(hermes_home))
    assert _resolve_url(saved, hermes_home=str(hermes_home)) == "https://saved.example/mcp"


def test_on_session_end_ingests_turn_by_turn_context_segments():
    from plugins.memory.ferrosa import FerrosaMemoryProvider

    provider = FerrosaMemoryProvider()
    client = RecordingClient()
    provider._client = client
    provider._session_id = "20260513_153500_deadbeef"

    provider.on_session_end(
        [
            {"role": "system", "content": "system prompt should not be indexed"},
            {"role": "user", "content": "Evaluate Bright-pro validation with Hermes."},
            {"role": "assistant", "content": "I will inspect fmem storage."},
            {"role": "tool", "content": "tool outputs should be skipped"},
            {"role": "user", "content": [{"type": "text", "text": "Second turn text."}]},
        ]
    )

    ingest_calls = [call for call in client.calls if call[0] == "ingest_context_segments"]
    assert len(ingest_calls) == 1
    args = ingest_calls[0][1]
    assert args["conversation_id"] == "20260513_153500_deadbeef"
    assert args["session_id"] != "20260513_153500_deadbeef"
    assert args["embed_missing"] is True
    assert args["segmentation"]["strategy"] == "hermes_turn_by_turn_v1"
    assert args["segmentation"]["target_tokens"] == 1
    assert [m["role"] for m in args["messages"]] == ["user", "assistant", "user"]
    assert [m["turn_index"] for m in args["messages"]] == [0, 1, 2]
    assert args["messages"][2]["content"] == "Second turn text."
    assert any(call[0] == "run_consolidation" for call in client.calls)


def test_sync_turn_persists_incremental_context_segments_with_temporal_indexes():
    from plugins.memory.ferrosa import FerrosaMemoryProvider

    provider = FerrosaMemoryProvider()
    client = RecordingClient()
    provider._client = client
    provider._session_id = "cli-session"

    provider.sync_turn("first user", "first assistant")
    provider.sync_turn("second user", "second assistant")

    ingest_calls = [call for call in client.calls if call[0] == "ingest_context_segments"]
    assert len(ingest_calls) == 2
    assert [m["turn_index"] for m in ingest_calls[0][1]["messages"]] == [0, 1]
    assert [m["turn_index"] for m in ingest_calls[1][1]["messages"]] == [2, 3]


def test_on_pre_compress_flushes_context_segments_before_messages_are_discarded():
    from plugins.memory.ferrosa import FerrosaMemoryProvider

    provider = FerrosaMemoryProvider()
    client = RecordingClient()
    provider._client = client
    provider._session_id = "compress-session"

    note = provider.on_pre_compress([
        {"role": "user", "content": "Important early context"},
        {"role": "assistant", "content": "Preserve it before compaction"},
    ])

    assert "Ferrosa Memory" in note
    assert any(call[0] == "ingest_context_segments" for call in client.calls)
