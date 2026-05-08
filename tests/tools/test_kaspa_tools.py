import json
from urllib import error

import pytest

from tools import kaspa_tools
from tools.registry import registry
from toolsets import _HERMES_CORE_TOOLS, resolve_toolset


class FakeResponse:
    def __init__(self, status_code=200, body=b"{}"):
        self.status_code = status_code
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def getcode(self):
        return self.status_code

    def read(self):
        return self.body

    def close(self):
        pass


def _json(result):
    return json.loads(result)


def test_registry_entries_and_schemas_exist():
    kaspa_entry = registry.get_entry("kaspa_api_health")
    kasia_entry = registry.get_entry("kasia_indexer_health")

    assert kaspa_entry is not None
    assert kaspa_entry.toolset == "kaspa"
    assert kaspa_entry.schema["parameters"]["properties"]["url"]["type"] == "string"
    assert "timeout_seconds" in kaspa_entry.schema["parameters"]["properties"]

    assert kasia_entry is not None
    assert kasia_entry.toolset == "kaspa"
    assert kasia_entry.schema["parameters"]["properties"]["url"]["type"] == "string"
    assert "timeout_seconds" in kasia_entry.schema["parameters"]["properties"]


def test_toolset_resolves_kaspa_tools():
    assert resolve_toolset("kaspa") == [
        "kasia_indexer_contextual_messages_by_sender",
        "kasia_indexer_handshakes_by_receiver",
        "kasia_indexer_handshakes_by_sender",
        "kasia_indexer_health",
        "kasia_indexer_payments_by_receiver",
        "kasia_indexer_payments_by_sender",
        "kasia_indexer_self_stash_by_owner",
        "kaspa_api_health",
    ]


def test_tools_are_not_in_core_tools():
    assert "kaspa_api_health" not in _HERMES_CORE_TOOLS
    assert "kasia_indexer_health" not in _HERMES_CORE_TOOLS


def test_default_url_behavior_with_env_cleared(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        seen["timeout"] = timeout
        return FakeResponse(200, b'{"healthy": true}')

    monkeypatch.delenv("KASPA_API_URL", raising=False)
    monkeypatch.setattr(kaspa_tools.request, "urlopen", fake_urlopen)

    result = _json(kaspa_tools.kaspa_api_health({}))

    assert result["ok"] is True
    assert result["url"] == "https://api.kaspa.org"
    assert result["endpoint"] == "https://api.kaspa.org/info/health"
    assert result["health"] == {"healthy": True}
    assert seen == {"url": "https://api.kaspa.org/info/health", "timeout": 10}


def test_custom_url_trailing_slash_normalization(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        return FakeResponse(200, b'{"status": "ok"}')

    monkeypatch.setattr(kaspa_tools.request, "urlopen", fake_urlopen)

    result = _json(kaspa_tools.kasia_indexer_health({"url": "https://example.test///"}))

    assert result["ok"] is True
    assert result["url"] == "https://example.test"
    assert result["endpoint"] == "https://example.test/metrics"
    assert result["metrics"] == {"status": "ok"}
    assert seen["url"] == "https://example.test/metrics"


@pytest.mark.parametrize("url", ["", "ftp://example.test", "file:///tmp/x", "example.test"])
def test_normalize_base_url_rejects_invalid_url(url):
    with pytest.raises(ValueError, match="http:// or https://"):
        kaspa_tools._normalize_base_url(url)


@pytest.mark.parametrize("url", ["ftp://example.test", "file:///tmp/x", "example.test"])
def test_invalid_url_rejected(url):
    result = _json(kaspa_tools.kaspa_api_health({"url": url}))
    assert "error" in result
    assert "http:// or https://" in result["error"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, 10),
        ("", 10),
        (0, 1),
        (-10, 1),
        (1, 1),
        (12.9, 12),
        ("30", 30),
        (300, 30),
    ],
)
def test_timeout_coerced_and_clamped(raw, expected):
    assert kaspa_tools._coerce_timeout_seconds(raw) == expected


def test_timeout_rejects_non_number():
    with pytest.raises(ValueError, match="timeout_seconds"):
        kaspa_tools._coerce_timeout_seconds("slow")


def test_happy_path_json_response_for_kaspa_api(monkeypatch):
    def fake_urlopen(req, timeout):
        assert req.full_url == "https://node.example/info/health"
        assert req.headers["User-agent"] == "HermesAgent/KaspaTools"
        assert timeout == 4
        return FakeResponse(200, b'{"server": "up"}')

    monkeypatch.setattr(kaspa_tools.request, "urlopen", fake_urlopen)

    result = _json(kaspa_tools.kaspa_api_health({
        "url": "https://node.example",
        "timeout_seconds": 4,
    }))

    assert result == {
        "ok": True,
        "url": "https://node.example",
        "endpoint": "https://node.example/info/health",
        "status_code": 200,
        "health": {"server": "up"},
    }


def test_happy_path_json_response_for_kasia_indexer(monkeypatch):
    def fake_urlopen(req, timeout):
        assert req.full_url == "https://indexer.example/metrics"
        assert timeout == 8
        return FakeResponse(200, b'{"lag": 0}')

    monkeypatch.setattr(kaspa_tools.request, "urlopen", fake_urlopen)

    result = _json(kaspa_tools.kasia_indexer_health({
        "url": "https://indexer.example",
        "timeout_seconds": 8,
    }))

    assert result == {
        "ok": True,
        "url": "https://indexer.example",
        "endpoint": "https://indexer.example/metrics",
        "status_code": 200,
        "metrics": {"lag": 0},
    }


def test_http_status_response_becomes_json_error(monkeypatch):
    def fake_urlopen(req, timeout):
        return FakeResponse(503, b'{"message": "maintenance"}')

    monkeypatch.setattr(kaspa_tools.request, "urlopen", fake_urlopen)

    result = _json(kaspa_tools.kaspa_api_health({"url": "https://node.example"}))

    assert result["ok"] is False
    assert result["status_code"] == 503
    assert result["url"] == "https://node.example"
    assert result["endpoint"] == "https://node.example/info/health"
    assert result["payload"] == {"message": "maintenance"}
    assert "error" in result


def test_http_error_exception_becomes_json_error(monkeypatch):
    def fake_urlopen(req, timeout):
        raise error.HTTPError(
            req.full_url,
            500,
            "server error",
            hdrs=None,
            fp=FakeResponse(500, b'{"failed": true}'),
        )

    monkeypatch.setattr(kaspa_tools.request, "urlopen", fake_urlopen)

    result = _json(kaspa_tools.kasia_indexer_health({"url": "https://indexer.example"}))

    assert result["ok"] is False
    assert result["status_code"] == 500
    assert result["url"] == "https://indexer.example"
    assert result["endpoint"] == "https://indexer.example/metrics"
    assert result["payload"] == {"failed": True}
    assert "HTTP 500" in result["error"]


def test_network_error_becomes_json_error(monkeypatch):
    def fake_urlopen(req, timeout):
        raise error.URLError("connection refused")

    monkeypatch.setattr(kaspa_tools.request, "urlopen", fake_urlopen)

    result = _json(kaspa_tools.kaspa_api_health({"url": "https://node.example"}))

    assert result["ok"] is False
    assert result["status_code"] is None
    assert result["url"] == "https://node.example"
    assert result["endpoint"] == "https://node.example/info/health"
    assert "Network error" in result["error"]


def test_kasia_indexer_query_encodes_required_and_optional_params(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        seen["timeout"] = timeout
        return FakeResponse(200, b'[{"id": "m1"}]')

    monkeypatch.setattr(kaspa_tools.request, "urlopen", fake_urlopen)

    result = _json(kaspa_tools.kasia_indexer_contextual_messages_by_sender({
        "url": "http://indexer.example",
        "address": "kaspa:qz sender",
        "alias": "00ff",
        "limit": 25,
        "block_time": 123456789,
        "timeout_seconds": 3,
    }))

    assert result == {
        "ok": True,
        "url": "http://indexer.example",
        "endpoint": "http://indexer.example/contextual-messages/by-sender?address=kaspa%3Aqz+sender&alias=00ff&limit=25&block_time=123456789",
        "status_code": 200,
        "items": [{"id": "m1"}],
    }
    assert seen == {"url": result["endpoint"], "timeout": 3}


def test_kasia_indexer_query_rejects_missing_required_param():
    result = _json(kaspa_tools.kasia_indexer_payments_by_sender({"url": "http://indexer.example"}))

    assert result["ok"] is False
    assert "address is required" in result["error"]


def test_kasia_indexer_query_clamps_limit_and_omits_empty_optional_params(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        return FakeResponse(200, b'[]')

    monkeypatch.setattr(kaspa_tools.request, "urlopen", fake_urlopen)

    result = _json(kaspa_tools.kasia_indexer_handshakes_by_receiver({
        "url": "http://indexer.example",
        "address": "kaspa:qreceiver",
        "limit": 5000,
        "block_time": "",
    }))

    assert result["ok"] is True
    assert seen["url"] == "http://indexer.example/handshakes/by-receiver?address=kaspa%3Aqreceiver&limit=1000"


def test_kasia_indexer_self_stash_by_owner_uses_scope_and_owner(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        return FakeResponse(200, b'{"stash": []}')

    monkeypatch.setattr(kaspa_tools.request, "urlopen", fake_urlopen)

    result = _json(kaspa_tools.kasia_indexer_self_stash_by_owner({
        "url": "http://indexer.example",
        "scope": "00",
        "owner": "kaspa:qowner",
    }))

    assert result["ok"] is True
    assert result["items"] == {"stash": []}
    assert seen["url"] == "http://indexer.example/self-stash/by-owner?scope=00&owner=kaspa%3Aqowner"
