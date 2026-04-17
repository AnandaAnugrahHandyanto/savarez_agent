import json

from tools.session_search_tool import session_search_compact


class _FakeDB:
    def search_messages(self, **kwargs):
        return [
            {
                "session_id": "sess-1",
                "content": "We decided the proof receipt should be canonical.",
                "session_started": 1710000000,
                "source": "cli",
                "model": "gpt-test",
            }
        ]

    def get_session(self, session_id):
        return {"session_id": session_id, "parent_session_id": None, "started_at": 1710000000}


def test_session_search_compact_returns_non_llm_runtime_block():
    payload = session_search_compact("proof receipt", db=_FakeDB(), current_session_id=None, limit=3)

    assert payload["count"] == 1
    assert payload["results"][0]["session_id"] == "sess-1"
    assert "canonical" in payload["block"]
