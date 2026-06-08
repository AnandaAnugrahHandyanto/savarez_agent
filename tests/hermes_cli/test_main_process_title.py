import builtins
import types

from hermes_cli import main


def test_set_process_title_tolerates_missing_ctypes(monkeypatch):
    real_import = builtins.__import__
    imported = []

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        imported.append(name)
        if name == "setproctitle":
            raise ImportError("No module named 'setproctitle'")
        if name == "ctypes":
            raise ModuleNotFoundError("No module named '_ctypes'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    main._set_process_title()

    tracked = [name for name in imported if name in {"ctypes", "platform"}]
    assert tracked == ["ctypes"]


def test_set_process_title_prefers_setproctitle(monkeypatch):
    real_import = builtins.__import__
    calls = []

    fake_setproctitle = types.SimpleNamespace(
        setproctitle=lambda title: calls.append(("setproctitle", title))
    )

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "setproctitle":
            return fake_setproctitle
        if name == "ctypes":
            raise AssertionError("ctypes should not be imported after setproctitle")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    main._set_process_title()

    assert calls == [("setproctitle", "hermes")]


def test_set_process_title_tolerates_ctypes_call_failures(monkeypatch):
    real_import = builtins.__import__

    fake_ctypes = types.SimpleNamespace(
        CDLL=lambda *args, **kwargs: (_ for _ in ()).throw(OSError("libc unavailable"))
    )

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "setproctitle":
            raise ImportError("No module named 'setproctitle'")
        if name == "ctypes":
            return fake_ctypes
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(main.sys, "platform", "linux")

    main._set_process_title()
