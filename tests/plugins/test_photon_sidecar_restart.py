import asyncio

import pytest

from plugins.platforms.photon import adapter as photon_adapter


class _FakeProc:
    def __init__(self, stdout: bytes):
        self._stdout = stdout

    async def communicate(self):
        return self._stdout, b""


@pytest.mark.asyncio
async def test_clear_stale_sidecar_port_falls_back_to_ps_on_macos_lsof_args(monkeypatch):
    """macOS lsof can emit only `au`; use ps argv before deciding not to kill."""

    sidecar_path = str(photon_adapter._SIDECAR_DIR / "index.mjs")
    calls = []

    async def fake_create_subprocess_exec(*args, **kwargs):
        calls.append(args)
        if args[0] == "lsof":
            # p=pid, c=command, a=access mode only. This is the shape seen on macOS.
            return _FakeProc(b"p4242\ncnode\nau\n")
        if args[0] == "ps":
            return _FakeProc(
                f"/opt/homebrew/bin/node {sidecar_path}\n".encode()
            )
        raise AssertionError(f"unexpected subprocess: {args}")

    killed = []

    def fake_killpg(pgid, sig):
        killed.append((pgid, sig))

    def fake_kill(pid, sig):
        if sig == 0:
            raise ProcessLookupError
        killed.append((pid, sig))

    monkeypatch.setattr(photon_adapter.sys, "platform", "darwin")
    monkeypatch.setattr(photon_adapter.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(photon_adapter.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(photon_adapter.os, "killpg", fake_killpg)
    monkeypatch.setattr(photon_adapter.os, "kill", fake_kill)

    obj = object.__new__(photon_adapter.PhotonAdapter)
    obj._sidecar_port = 8799

    await obj._clear_stale_sidecar_port()

    assert calls[0][0] == "lsof"
    assert any(call[0] == "ps" for call in calls)
    assert killed == [(4242, photon_adapter.signal.SIGTERM)]


@pytest.mark.asyncio
async def test_clear_stale_sidecar_port_leaves_unrelated_listener_alone(monkeypatch):
    async def fake_create_subprocess_exec(*args, **kwargs):
        if args[0] == "lsof":
            return _FakeProc(b"p5252\ncnode\nau\n")
        if args[0] == "ps":
            return _FakeProc(b"node /tmp/not-photon/index.mjs\n")
        raise AssertionError(f"unexpected subprocess: {args}")

    killed = []
    monkeypatch.setattr(photon_adapter.sys, "platform", "darwin")
    monkeypatch.setattr(photon_adapter.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(photon_adapter.os, "killpg", lambda *args: killed.append(args))
    monkeypatch.setattr(photon_adapter.os, "kill", lambda *args: killed.append(args))

    obj = object.__new__(photon_adapter.PhotonAdapter)
    obj._sidecar_port = 8799

    await obj._clear_stale_sidecar_port()

    assert killed == []
