from types import SimpleNamespace

import hermes_cli


class _FakeStream:
    def __init__(self, encoding="cp1252", errors="strict"):
        self.encoding = encoding
        self.errors = errors
        self.reconfigure_calls = []

    def reconfigure(self, **kwargs):
        self.reconfigure_calls.append(kwargs)
        if "errors" in kwargs:
            self.errors = kwargs["errors"]


def test_windows_non_utf8_console_uses_replace(monkeypatch):
    stream = _FakeStream(encoding="cp1252", errors="strict")
    monkeypatch.setattr(hermes_cli.sys, "platform", "win32")

    hermes_cli._configure_console_error_fallback(stream)

    assert stream.reconfigure_calls == [{"errors": "replace"}]


def test_utf8_console_is_left_unchanged(monkeypatch):
    stream = _FakeStream(encoding="utf-8", errors="strict")
    monkeypatch.setattr(hermes_cli.sys, "platform", "win32")

    hermes_cli._configure_console_error_fallback(stream)

    assert stream.reconfigure_calls == []


def test_stream_without_reconfigure_is_ignored(monkeypatch):
    stream = SimpleNamespace(encoding="cp1252", errors="strict")
    monkeypatch.setattr(hermes_cli.sys, "platform", "win32")

    hermes_cli._configure_console_error_fallback(stream)


def test_existing_safe_error_handler_is_preserved(monkeypatch):
    stream = _FakeStream(encoding="cp1252", errors="backslashreplace")
    monkeypatch.setattr(hermes_cli.sys, "platform", "win32")

    hermes_cli._configure_console_error_fallback(stream)

    assert stream.reconfigure_calls == []
