from __future__ import annotations

import types

from tools import websocket_compat


def _reset_connect_cache(monkeypatch):
    monkeypatch.setattr(websocket_compat, "_CONNECT", None)
    monkeypatch.setattr(websocket_compat, "_CONNECT_ERROR", None)


def test_websocket_connect_prefers_modern_asyncio_client(monkeypatch):
    _reset_connect_cache(monkeypatch)

    def modern_connect(*args, **kwargs):
        return ("modern", args, kwargs)

    def fake_import_module(name):
        if name == "websockets.asyncio.client":
            return types.SimpleNamespace(connect=modern_connect)
        raise AssertionError(f"unexpected fallback import: {name}")

    monkeypatch.setattr(websocket_compat.importlib, "import_module", fake_import_module)

    assert websocket_compat.websocket_connect("ws://cdp", max_size=1) == (
        "modern",
        ("ws://cdp",),
        {"max_size": 1},
    )


def test_websocket_connect_falls_back_when_top_level_has_no_connect(monkeypatch):
    _reset_connect_cache(monkeypatch)

    def legacy_connect(*args, **kwargs):
        return ("legacy", args, kwargs)

    def fake_import_module(name):
        if name == "websockets.asyncio.client":
            raise ModuleNotFoundError("No module named 'websockets.asyncio'")
        if name == "websockets":
            return types.SimpleNamespace()
        if name == "websockets.client":
            return types.SimpleNamespace(connect=legacy_connect)
        raise AssertionError(f"unexpected fallback import: {name}")

    monkeypatch.setattr(websocket_compat.importlib, "import_module", fake_import_module)

    assert websocket_compat.websocket_connect("ws://cdp") == (
        "legacy",
        ("ws://cdp",),
        {},
    )


def test_websockets_available_false_without_connector(monkeypatch):
    _reset_connect_cache(monkeypatch)

    def fake_import_module(name):
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(websocket_compat.importlib, "import_module", fake_import_module)

    assert websocket_compat.websockets_available() is False
