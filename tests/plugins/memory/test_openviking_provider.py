import json
from unittest.mock import MagicMock

from plugins.memory.openviking import OpenVikingMemoryProvider


def test_tool_search_sorts_by_raw_score_across_buckets():
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    provider._client.post.return_value = {
        "result": {
            "memories": [
                {"uri": "viking://memories/1", "score": 0.9003, "abstract": "memory result"},
            ],
            "resources": [
                {"uri": "viking://resources/1", "score": 0.9004, "abstract": "resource result"},
            ],
            "skills": [
                {"uri": "viking://skills/1", "score": 0.8999, "abstract": "skill result"},
            ],
            "total": 3,
        }
    }

    result = json.loads(provider._tool_search({"query": "ranking"}))

    assert [entry["uri"] for entry in result["results"]] == [
        "viking://resources/1",
        "viking://memories/1",
        "viking://skills/1",
    ]
    assert [entry["score"] for entry in result["results"]] == [0.9, 0.9, 0.9]
    assert result["total"] == 3


def test_tool_search_sorts_missing_raw_score_after_negative_scores():
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    provider._client.post.return_value = {
        "result": {
            "memories": [
                {"uri": "viking://memories/missing", "abstract": "missing score"},
            ],
            "resources": [
                {"uri": "viking://resources/negative", "score": -0.25, "abstract": "negative score"},
            ],
            "skills": [
                {"uri": "viking://skills/positive", "score": 0.1, "abstract": "positive score"},
            ],
            "total": 3,
        }
    }

    result = json.loads(provider._tool_search({"query": "ranking"}))

    assert [entry["uri"] for entry in result["results"]] == [
        "viking://skills/positive",
        "viking://memories/missing",
        "viking://resources/negative",
    ]
    assert [entry["score"] for entry in result["results"]] == [0.1, 0.0, -0.25]
    assert result["total"] == 3


def test_handle_tool_call_reconnects_after_startup_health_failure(monkeypatch):
    instances = []

    class FakeVikingClient:
        def __init__(self, endpoint, api_key="", account="", user="", agent=""):
            self.endpoint = endpoint
            self.posts = []
            self.index = len(instances)
            instances.append(self)

        def health(self):
            return self.index > 0

        def post(self, path, payload=None, **kwargs):
            self.posts.append((path, payload or {}))
            return {}

    monkeypatch.setenv("OPENVIKING_ENDPOINT", "http://openviking.local")
    monkeypatch.setattr("plugins.memory.openviking._VikingClient", FakeVikingClient)

    provider = OpenVikingMemoryProvider()
    provider.initialize("session-1")

    assert provider._client is None

    result = json.loads(provider.handle_tool_call("viking_remember", {"content": "stable fact"}))

    assert result["status"] == "stored"
    assert len(instances) == 2
    assert instances[1].posts == [
        (
            "/api/v1/sessions/session-1/messages",
            {"role": "user", "parts": [{"type": "text", "text": "[Remember] stable fact"}]},
        )
    ]
