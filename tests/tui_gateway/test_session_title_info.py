from types import SimpleNamespace


class FakeSessionDB:
    def __init__(self, titles=None):
        self.titles = dict(titles or {})

    def get_session_title(self, session_id):
        return self.titles.get(session_id, "")

    def set_session_title(self, session_id, title):
        self.titles[session_id] = title
        return True


def _agent():
    return SimpleNamespace(
        model="openrouter/test-model",
        service_tier="",
        reasoning_config={},
        tools=[],
        session_input_tokens=0,
        session_output_tokens=0,
        session_total_tokens=0,
        session_api_calls=0,
    )


def test_session_info_includes_current_session_title(monkeypatch):
    from tui_gateway import server

    db = FakeSessionDB({"durable-session": "Quarterly planning"})
    monkeypatch.setattr(server, "_get_db", lambda: db)

    info = server._session_info(_agent(), session={"session_key": "durable-session"})

    assert info["title"] == "Quarterly planning"


def test_session_title_rpc_emits_updated_session_info(monkeypatch):
    from tui_gateway import server

    db = FakeSessionDB()
    agent = _agent()
    server._sessions["sid-live-title"] = {
        "agent": agent,
        "pending_title": None,
        "session_key": "durable-session",
    }
    monkeypatch.setattr(server, "_get_db", lambda: db)
    emitted = []
    monkeypatch.setattr(
        server,
        "_emit",
        lambda event, sid, payload=None: emitted.append((event, sid, payload)),
    )

    try:
        response = server._methods["session.title"](
            "req-1",
            {"session_id": "sid-live-title", "title": "Manual title"},
        )
    finally:
        server._sessions.pop("sid-live-title", None)

    assert response["result"] == {"pending": False, "title": "Manual title"}
    assert emitted
    event, sid, payload = emitted[-1]
    assert event == "session.info"
    assert sid == "sid-live-title"
    assert payload["title"] == "Manual title"
