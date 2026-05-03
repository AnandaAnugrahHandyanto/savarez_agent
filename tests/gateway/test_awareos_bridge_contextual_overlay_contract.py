import json

import pytest


def _fake_response(payload: dict):
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    return _Resp()


def test_run_context_eval_uses_get_contextual_overlay_without_raw_body(monkeypatch):
    monkeypatch.setenv("AWAREOS_CONTEXT_EVAL_ENABLED", "1")
    monkeypatch.setenv("AWAREOS_CONTEXT_EVAL_URL", "http://awareos.test/api/kaze/contextual-overlay")
    monkeypatch.setenv("AWAREOS_CONTEXT_EVAL_BEARER_TOKEN", "tok_test")
    monkeypatch.setenv("AWAREOS_CONTEXTUAL_OVERLAY_TZ_OFFSET_MIN", "540")

    from gateway import awareos_bridge as ab

    captured = {}

    def _urlopen(req, timeout=0):
        captured["method"] = req.get_method()
        captured["url"] = req.full_url
        captured["headers"] = dict(req.headers)
        captured["data"] = getattr(req, "data", None)
        assert timeout == 6
        return _fake_response(
            {
                "now": "2026-05-03T00:00:00.000Z",
                "warrants_action": True,
                "prompts": [
                    {
                        "kind": "kriya_missing",
                        "priority": "high",
                        "reason": "No Kriya logged today.",
                        "suggested_action": "Do Kriya.",
                    }
                ],
            }
        )

    monkeypatch.setattr(ab.urllib.request, "urlopen", _urlopen)

    message_text = "calendar tomorrow; secret=DO_NOT_SEND"
    res = ab.run_context_eval(
        message_text=message_text,
        session_key="telegram:1",
        platform="telegram",
        chat_id="1",
        user_id="u",
    )

    assert res is not None
    assert res.ok is True
    assert "kriya_missing" in res.snippet

    assert captured["method"] == "GET"
    assert captured["data"] is None
    assert captured["headers"].get("Authorization") == "Bearer tok_test"
    assert "tz_offset_min=540" in captured["url"]
    assert "calendar_prep_needed=1" in captured["url"]
    assert "DO_NOT_SEND" not in captured["url"]

