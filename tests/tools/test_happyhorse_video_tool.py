import importlib
import json
from types import SimpleNamespace

import pytest


happyhorse_module = importlib.import_module("tools.happyhorse_video_tool")


def _response(payload, status_code=200):
    class FakeResponse:
        def __init__(self, payload, status_code):
            self._payload = payload
            self.status_code = status_code
            self.text = json.dumps(payload)

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise happyhorse_module.requests.HTTPError(f"http {self.status_code}")

    return FakeResponse(payload, status_code)


def test_check_happyhorse_requirements(monkeypatch):
    monkeypatch.delenv("HAPPYHORSE_API_KEY", raising=False)
    assert happyhorse_module.check_happyhorse_requirements() is False

    monkeypatch.setenv("HAPPYHORSE_API_KEY", "sk-test")
    assert happyhorse_module.check_happyhorse_requirements() is True


def test_handle_video_generate_requires_prompt_when_not_multi_shots():
    result = json.loads(happyhorse_module._handle_video_generate({}))
    assert result["error"] == "prompt is required unless multi_shots=true with multi_prompt provided"


def test_happyhorse_video_generate_submits_text_to_video_request(monkeypatch):
    monkeypatch.setenv("HAPPYHORSE_API_KEY", "sk-test")
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _response({
            "code": 200,
            "message": "success",
            "data": {"task_id": "n92abc123hh10", "status": "IN_PROGRESS"},
        })

    monkeypatch.setattr(happyhorse_module.requests, "post", fake_post)

    result = json.loads(
        happyhorse_module.happyhorse_video_generate(
            prompt="A cinematic sunrise over mountains",
            mode="pro",
            duration=5,
            aspect_ratio="16:9",
        )
    )

    assert captured["url"] == "https://happyhorse.app/api/generate"
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["json"] == {
        "model": "happyhorse-1.0/video",
        "prompt": "A cinematic sunrise over mountains",
        "mode": "pro",
        "duration": 5,
        "aspect_ratio": "16:9",
        "sound": True,
        "cfg_scale": 0.5,
    }
    assert result["success"] is True
    assert result["task_id"] == "n92abc123hh10"
    assert result["status"] == "IN_PROGRESS"


def test_happyhorse_video_generate_polls_until_video_url_ready(monkeypatch):
    monkeypatch.setenv("HAPPYHORSE_API_KEY", "sk-test")
    calls = {"status": 0}

    def fake_post(url, headers=None, json=None, timeout=None):
        return _response({
            "code": 200,
            "message": "success",
            "data": {"task_id": "n92abc123hh10", "status": "IN_PROGRESS"},
        })

    def fake_get(url, headers=None, params=None, timeout=None):
        calls["status"] += 1
        assert url == "https://happyhorse.app/api/status"
        assert params == {"task_id": "n92abc123hh10"}
        if calls["status"] == 1:
            return _response({
                "code": 200,
                "message": "success",
                "data": {"task_id": "n92abc123hh10", "status": "IN_PROGRESS"},
            })
        return _response({
            "code": 200,
            "message": "success",
            "data": {
                "task_id": "n92abc123hh10",
                "status": "COMPLETED",
                "response": {"resultUrls": ["https://cdn.example.com/video.mp4"]},
            },
        })

    monkeypatch.setattr(happyhorse_module.requests, "post", fake_post)
    monkeypatch.setattr(happyhorse_module.requests, "get", fake_get)
    monkeypatch.setattr(happyhorse_module.time, "sleep", lambda _seconds: None)

    result = json.loads(
        happyhorse_module.happyhorse_video_generate(
            prompt="A cinematic sunrise over mountains",
            wait_for_completion=True,
            poll_interval=0,
            timeout=5,
        )
    )

    assert calls["status"] == 2
    assert result["success"] is True
    assert result["status"] == "COMPLETED"
    assert result["video_url"] == "https://cdn.example.com/video.mp4"


def test_happyhorse_video_generate_treats_success_status_as_terminal_with_video_url(monkeypatch):
    monkeypatch.setenv("HAPPYHORSE_API_KEY", "sk-test")

    def fake_post(url, headers=None, json=None, timeout=None):
        return _response({
            "code": 200,
            "message": "success",
            "data": {"task_id": "n92abc123hh10", "status": "IN_PROGRESS"},
        })

    def fake_get(url, headers=None, params=None, timeout=None):
        return _response({
            "code": 200,
            "message": "success",
            "data": {
                "task_id": "n92abc123hh10",
                "status": "SUCCESS",
                "response": {"resultUrls": ["https://cdn.example.com/video-success.mp4"]},
            },
        })

    monkeypatch.setattr(happyhorse_module.requests, "post", fake_post)
    monkeypatch.setattr(happyhorse_module.requests, "get", fake_get)
    monkeypatch.setattr(happyhorse_module.time, "sleep", lambda _seconds: None)

    result = json.loads(
        happyhorse_module.happyhorse_video_generate(
            prompt="A cinematic sunrise over mountains",
            wait_for_completion=True,
            poll_interval=0,
            timeout=5,
        )
    )

    assert result["success"] is True
    assert result["status"] == "SUCCESS"
    assert result["video_url"] == "https://cdn.example.com/video-success.mp4"
    assert "error" not in result


def test_video_generate_tool_registered_and_toolset_resolves():
    from tools.registry import registry
    from toolsets import resolve_toolset

    assert registry.get_toolset_for_tool("video_generate") == "image_gen"
    assert "video_generate" in resolve_toolset("image_gen")
