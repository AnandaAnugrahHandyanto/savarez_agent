import os


class _FakeSocket:
    def settimeout(self, _timeout):
        pass

    def connect(self, _addr):
        pass

    def close(self):
        pass


def test_browser_connect_refuses_unresolved_discovery_endpoint(monkeypatch, capsys):
    from cli import HermesCLI

    cli = object.__new__(HermesCLI)
    monkeypatch.delenv("BROWSER_CDP_URL", raising=False)
    monkeypatch.setattr("socket.socket", lambda *a, **kw: _FakeSocket())
    monkeypatch.setattr("tools.browser_tool.cleanup_all_browsers", lambda: None)
    monkeypatch.setattr("tools.browser_tool._ensure_cdp_supervisor", lambda _task_id: None)
    monkeypatch.setattr("tools.browser_tool._resolve_cdp_override", lambda url: url)

    cli._handle_browser_command("/browser connect http://127.0.0.1:9222")

    output = capsys.readouterr().out
    assert "could not resolve a usable CDP websocket" in output
    assert "Browser connected to live Chrome via CDP" not in output
    assert os.environ.get("BROWSER_CDP_URL") is None


def test_browser_connect_stores_resolved_websocket_endpoint(monkeypatch, capsys):
    from cli import HermesCLI

    resolved = "ws://127.0.0.1:9222/devtools/browser/abc123"
    supervisor_starts = []
    cli = object.__new__(HermesCLI)
    monkeypatch.delenv("BROWSER_CDP_URL", raising=False)
    monkeypatch.setattr("socket.socket", lambda *a, **kw: _FakeSocket())
    monkeypatch.setattr("tools.browser_tool.cleanup_all_browsers", lambda: None)
    monkeypatch.setattr(
        "tools.browser_tool._ensure_cdp_supervisor",
        lambda task_id: supervisor_starts.append(task_id),
    )
    monkeypatch.setattr("tools.browser_tool._resolve_cdp_override", lambda url: resolved)

    cli._handle_browser_command("/browser connect http://127.0.0.1:9222")

    output = capsys.readouterr().out
    assert "Browser connected to live Chrome via CDP" in output
    assert f"Endpoint: {resolved}" in output
    assert os.environ["BROWSER_CDP_URL"] == resolved
    assert supervisor_starts == ["default"]
