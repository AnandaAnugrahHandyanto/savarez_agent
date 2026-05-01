import json

from plugins.memory.byterover import ByteRoverMemoryProvider
from plugins.memory.openviking import OpenVikingMemoryProvider
from plugins.memory.mem0 import Mem0MemoryProvider
from plugins.memory.hindsight import HindsightMemoryProvider
from plugins.memory.shared import build_capture_metadata, merge_json_config, sanitize_metadata, stable_memory_fingerprint


def test_byterover_sync_turn_deduplicates_and_includes_metadata(monkeypatch, tmp_path):
    calls = []

    def fake_run_brv(args, timeout=None, cwd=None):
        calls.append({"args": args, "timeout": timeout, "cwd": cwd})
        return {"success": True, "output": "ok"}

    monkeypatch.setattr("plugins.memory.byterover._run_brv", fake_run_brv)

    provider = ByteRoverMemoryProvider()
    provider.initialize("sess-1")
    provider._cwd = str(tmp_path)

    provider.sync_turn("Hello  world", "Answer here")
    provider.sync_turn(" Hello world ", "Answer here ")

    assert len(calls) == 1
    payload = calls[0]["args"][2]
    meta_line, body = payload.split("\n", 1)
    assert meta_line.startswith("[meta] ")
    metadata = json.loads(meta_line[len("[meta] "):])
    assert metadata["source"] == "hermes"
    assert metadata["type"] == "conversation_turn"
    assert metadata["fingerprint"]
    assert "User: Hello  world" in body


def test_byterover_memory_write_deduplicates_and_strips_sensitive_metadata(monkeypatch, tmp_path):
    calls = []

    def fake_run_brv(args, timeout=None, cwd=None):
        calls.append(args)
        return {"success": True, "output": "ok"}

    monkeypatch.setattr("plugins.memory.byterover._run_brv", fake_run_brv)

    provider = ByteRoverMemoryProvider()
    provider.initialize("sess-2")
    provider._cwd = str(tmp_path)

    provider.on_memory_write("add", "user", "Prefers terse answers")
    provider.on_memory_write("add", "user", " prefers terse answers ")

    assert len(calls) == 1
    payload = calls[0][2]
    meta_line, body = payload.split("\n", 1)
    metadata = json.loads(meta_line[len("[meta] "):])
    assert metadata == {
        "action": "add",
        "fingerprint": metadata["fingerprint"],
        "source": "hermes_memory",
        "target": "user",
        "type": "explicit_memory",
    }
    assert "[User profile] Prefers terse answers" in body


class _FakeClient:
    def __init__(self):
        self.posts = []

    def post(self, path, payload=None, **kwargs):
        self.posts.append((path, payload, kwargs))
        return {"ok": True}

    def get(self, path, **kwargs):
        return {"result": {}}

    def health(self):
        return True


def test_openviking_sync_turn_deduplicates_and_attaches_metadata(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr("plugins.memory.openviking._VikingClient", lambda *args, **kwargs: client)

    provider = OpenVikingMemoryProvider()
    provider.initialize("sess-3")
    provider.sync_turn("Hello  world", "Answer here")
    if provider._sync_thread:
        provider._sync_thread.join(timeout=2)
    provider.sync_turn(" hello world ", "Answer here ")
    if provider._sync_thread:
        provider._sync_thread.join(timeout=2)

    assert len(client.posts) == 2
    user_payload = client.posts[0][1]
    assistant_payload = client.posts[1][1]
    assert user_payload["metadata"]["source"] == "hermes"
    assert user_payload["metadata"]["type"] == "conversation_turn"
    assert user_payload["metadata"]["fingerprint"]
    assert assistant_payload["metadata"]["source"] == "hermes"


def test_openviking_memory_write_deduplicates_and_strips_sensitive_metadata(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr("plugins.memory.openviking._VikingClient", lambda *args, **kwargs: client)

    provider = OpenVikingMemoryProvider()
    provider.initialize("sess-4")
    provider.on_memory_write("add", "user", "Prefers terse answers")
    provider.on_memory_write("add", "user", " prefers terse answers ")

    user_posts = [payload for path, payload, _ in client.posts if path.endswith("/messages")]
    assert len(user_posts) == 1
    metadata = user_posts[0]["metadata"]
    assert metadata == {
        "fingerprint": metadata["fingerprint"],
        "source": "hermes_memory",
        "target": "user",
        "type": "explicit_memory",
    }
    assert user_posts[0]["parts"][0]["text"] == "[Memory note — user] Prefers terse answers"


def test_mem0_sync_turn_deduplicates_and_attaches_metadata(monkeypatch):
    calls = []

    class _FakeClient:
        def add(self, messages, **kwargs):
            calls.append({"messages": messages, **kwargs})

    provider = Mem0MemoryProvider()
    provider.initialize("sess-mem0")
    provider._user_id = "u123"
    provider._agent_id = "hermes"
    monkeypatch.setattr(provider, "_get_client", lambda: _FakeClient())

    provider.sync_turn("Hello  world", "Answer here")
    if provider._sync_thread:
        provider._sync_thread.join(timeout=2)
    provider.sync_turn(" hello world ", "Answer here ")
    if provider._sync_thread:
        provider._sync_thread.join(timeout=2)

    assert len(calls) == 1
    metadata = calls[0]["metadata"]
    assert metadata["source"] == "hermes"
    assert metadata["type"] == "conversation_turn"
    assert metadata["fingerprint"]


def test_mem0_memory_write_deduplicates_and_strips_sensitive_metadata(monkeypatch):
    calls = []

    class _FakeClient:
        def add(self, messages, **kwargs):
            calls.append({"messages": messages, **kwargs})

    provider = Mem0MemoryProvider()
    provider.initialize("sess-mem0-write")
    provider._user_id = "u123"
    provider._agent_id = "hermes"
    monkeypatch.setattr(provider, "_get_client", lambda: _FakeClient())

    result1 = json.loads(provider.handle_tool_call("mem0_conclude", {"conclusion": "Prefers terse answers", "metadata": {"user_id": "secret", "trace_id": "abc", "channel": "feishu"}}))
    result2 = json.loads(provider.handle_tool_call("mem0_conclude", {"conclusion": " prefers terse answers "}))

    assert result1["result"] == "Fact stored."
    assert result2["skipped"] is True
    assert len(calls) == 1
    metadata = calls[0]["metadata"]
    assert metadata == {
        "channel": "feishu",
        "fingerprint": metadata["fingerprint"],
        "source": "hermes_memory",
        "type": "explicit_memory",
    }


def test_hindsight_retain_deduplicates_and_attaches_metadata(monkeypatch, tmp_path):
    provider = HindsightMemoryProvider()
    provider.initialize("sess-h1", hermes_home=str(tmp_path), platform="cli")

    calls = []

    class _FakeClient:
        async def aretain(self, **kwargs):
            calls.append(kwargs)

    provider._client = _FakeClient()

    result1 = json.loads(provider.handle_tool_call("hindsight_retain", {"content": "Prefers terse answers", "context": "user preference"}))
    result2 = json.loads(provider.handle_tool_call("hindsight_retain", {"content": " prefers terse answers ", "context": "user preference"}))

    assert result1["result"] == "Memory stored successfully."
    assert result2["skipped"] is True
    assert len(calls) == 1
    metadata = calls[0]["metadata"]
    assert metadata == {
        "context": "user preference",
        "fingerprint": metadata["fingerprint"],
        "source": "hermes_memory",
        "type": "explicit_memory",
    }


def test_shared_helpers_sanitize_metadata_supports_allowlist_and_blocks_sensitive_keys(tmp_path):
    metadata = sanitize_metadata(
        {
            "type": "preference",
            "category": "writing",
            "note": "keep",
            "session_id": "secret",
            "trace_id": "abc",
            "file_path": "/tmp/private.txt",
        },
        allowlist={"type", "category", "note"},
    )

    assert metadata == {
        "type": "preference",
        "category": "writing",
        "note": "keep",
    }


def test_shared_helpers_build_capture_metadata_adds_fingerprint_and_source():
    metadata = build_capture_metadata(
        source="hermes_memory",
        memory_type="explicit_memory",
        content="Prefers terse answers",
        extra={"target": "user"},
    )

    assert metadata["source"] == "hermes_memory"
    assert metadata["type"] == "explicit_memory"
    assert metadata["target"] == "user"
    assert metadata["fingerprint"] == stable_memory_fingerprint("Prefers terse answers")


def test_shared_helpers_merge_json_config_merges_existing_file(tmp_path):
    config_path = tmp_path / "provider.json"
    config_path.write_text('{"api_key": "***"}', encoding="utf-8")

    merge_json_config(config_path, {"user_id": "u1"}, sort_keys=True, trailing_newline=True)

    assert config_path.read_text(encoding="utf-8") == '{\n  "api_key": "***",\n  "user_id": "u1"\n}\n'


def test_mem0_save_config_merges_existing_json(tmp_path):
    config_path = tmp_path / "mem0.json"
    config_path.write_text('{"api_key": "***"}', encoding="utf-8")

    provider = Mem0MemoryProvider()
    provider.save_config({"user_id": "u1"}, str(tmp_path))

    assert json.loads(config_path.read_text(encoding="utf-8")) == {
        "api_key": "***",
        "user_id": "u1",
    }


def test_hindsight_save_config_merges_existing_json(tmp_path):
    config_path = tmp_path / "hindsight" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text('{"mode": "cloud"}', encoding="utf-8")

    provider = HindsightMemoryProvider()
    provider.save_config({"bank_id": "bank-1"}, str(tmp_path))

    assert json.loads(config_path.read_text(encoding="utf-8")) == {
        "mode": "cloud",
        "bank_id": "bank-1",
    }
