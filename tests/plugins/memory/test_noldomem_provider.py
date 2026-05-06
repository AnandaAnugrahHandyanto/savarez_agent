import json
import urllib.error

from plugins.memory.noldomem import NoldoMemMemoryProvider


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_provider_unavailable_without_endpoint_or_key(monkeypatch):
    monkeypatch.delenv("NOLDOMEM_API_URL", raising=False)
    monkeypatch.delenv("NOLDOMEM_API_KEY", raising=False)

    provider = NoldoMemMemoryProvider()

    assert provider.is_available() is False


def test_provider_available_with_endpoint_and_key(monkeypatch):
    monkeypatch.setenv("NOLDOMEM_API_URL", "http://127.0.0.1:8787")
    monkeypatch.setenv("NOLDOMEM_API_KEY", "test-key")

    provider = NoldoMemMemoryProvider()

    assert provider.is_available() is True


def test_provider_available_with_saved_endpoint_and_env_key(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("NOLDOMEM_API_URL", raising=False)
    monkeypatch.setenv("NOLDOMEM_API_KEY", "test-key")
    (tmp_path / "noldomem.json").write_text(
        json.dumps({"api_url": "http://memory.test"}) + "\n",
        encoding="utf-8",
    )

    provider = NoldoMemMemoryProvider()

    assert provider.is_available() is True


def test_provider_setup_schema_mentions_endpoint_and_key():
    provider = NoldoMemMemoryProvider()

    fields = {field["key"]: field for field in provider.get_config_schema()}

    assert {"api_url", "api_key"}.issubset(fields)
    assert fields["api_key"]["secret"] is True
    assert fields["api_key"]["env_var"] == "NOLDOMEM_API_KEY"


def test_recall_uses_api_key_and_formats_bounded_results(monkeypatch, tmp_path):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "results": [
                    {
                        "text": "Embedding server used Qwen3 0.6B with 1024 dimensions.",
                        "memory_type": "fact",
                        "semantic_score": 0.91,
                        "rerank_score": 0.88,
                    },
                    {
                        "text": "This second memory should be clipped by max_recall_results.",
                        "memory_type": "lesson",
                    },
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setenv("NOLDOMEM_API_URL", "http://memory.test")
    monkeypatch.setenv("NOLDOMEM_API_KEY", "test-key")
    provider = NoldoMemMemoryProvider()
    provider.initialize(
        "session-1",
        hermes_home=str(tmp_path),
        agent_identity="coder",
        agent_workspace="workspace-a",
    )
    provider._max_recall_results = 1

    result = provider._recall("embedding dimensions")

    assert captured["url"] == "http://memory.test/v1/recall"
    assert captured["headers"]["X-api-key"] == "test-key"
    assert captured["body"] == {
        "query": "embedding dimensions",
        "agent": "coder",
        "namespace": "workspace-a",
        "limit": 1,
    }
    assert captured["timeout"] == provider._api_timeout
    assert "NoldoMem recalled context" in result
    assert "Qwen3 0.6B" in result
    assert "second memory" not in result


def test_prefetch_returns_cached_background_recall(monkeypatch, tmp_path):
    monkeypatch.setenv("NOLDOMEM_API_URL", "http://memory.test")
    monkeypatch.setenv("NOLDOMEM_API_KEY", "test-key")
    provider = NoldoMemMemoryProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path))
    monkeypatch.setattr(provider, "_recall", lambda query: f"remembered: {query}")

    provider.queue_prefetch("previous query")
    provider._prefetch_thread.join(timeout=1)

    assert provider.prefetch("current query") == "remembered: previous query"
    assert provider.prefetch("current query") == ""


def test_sync_turn_skips_non_primary_context(monkeypatch, tmp_path):
    monkeypatch.setenv("NOLDOMEM_API_URL", "http://memory.test")
    monkeypatch.setenv("NOLDOMEM_API_KEY", "test-key")
    provider = NoldoMemMemoryProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), agent_context="cron")
    monkeypatch.setattr(provider, "_store", lambda text, memory_type="conversation": (_ for _ in ()).throw(AssertionError("should not store")))

    provider.sync_turn("user", "assistant", session_id="session-1")

    assert provider._sync_thread is None


def test_tool_calls_map_to_noldomem_endpoints(monkeypatch, tmp_path):
    calls = []

    def fake_request(path, body):
        calls.append((path, body))
        if path == "/v1/recall":
            return {"results": [{"text": "Stored test memory", "memory_type": "fact"}]}
        return {"ok": True, "id": 123}

    monkeypatch.setenv("NOLDOMEM_API_URL", "http://memory.test")
    monkeypatch.setenv("NOLDOMEM_API_KEY", "test-key")
    provider = NoldoMemMemoryProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), agent_identity="coder")
    monkeypatch.setattr(provider, "_request_json", fake_request)

    recall = json.loads(provider.handle_tool_call("noldomem_recall", {"query": "test", "limit": 3}))
    store = json.loads(provider.handle_tool_call("noldomem_store", {"text": "remember this", "memory_type": "lesson"}))
    pin = json.loads(provider.handle_tool_call("noldomem_pin", {"memory_id": "mem-123"}))

    assert recall["count"] == 1
    assert store["ok"] is True
    assert pin["ok"] is True
    assert calls == [
        ("/v1/recall", {"query": "test", "agent": "coder", "namespace": "default", "limit": 3}),
        ("/v1/store", {"text": "remember this", "agent": "coder", "namespace": "default", "memory_type": "lesson"}),
        ("/v1/pin", {"id": "mem-123", "agent": "coder", "namespace": "default"}),
    ]


def test_http_errors_degrade_to_empty_recall(monkeypatch, tmp_path):
    def fake_urlopen(request, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setenv("NOLDOMEM_API_URL", "http://memory.test")
    monkeypatch.setenv("NOLDOMEM_API_KEY", "test-key")
    provider = NoldoMemMemoryProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path))

    assert provider._recall("anything") == ""
