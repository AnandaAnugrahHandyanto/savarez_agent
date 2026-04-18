import types

from hermes_cli import callbacks


class DummyCLI:
    _app = None


def test_approval_callback_denies_immediately_without_interactive_client(monkeypatch):
    messages = []
    monkeypatch.setattr(callbacks, "cprint", messages.append)
    monkeypatch.setitem(
        __import__("sys").modules,
        "cli",
        types.SimpleNamespace(CLI_CONFIG={"approvals": {"timeout": 60}}),
    )

    result = callbacks.approval_callback(DummyCLI(), "rm -rf /tmp/demo", "dangerous")

    assert result == "deny"
    assert messages
    assert "no interactive approval client is active" in messages[0]
    assert "Denying command immediately" in messages[0]
