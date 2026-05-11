"""Unit tests for the FastVM terminal backend."""

from __future__ import annotations

import importlib
import io
import re
import tarfile
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest


@dataclass
class _FakeExecResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    timed_out: bool = False


@dataclass
class _FakeVM:
    id: str = "vm-123"
    status: str = "running"


@dataclass
class _FakeSnapshot:
    id: str
    status: str = "ready"
    vm_id: str = "vm-123"


class _FakeVms:
    def __init__(self, events: list[str]):
        self.events = events
        self.launch_calls: list[dict] = []
        self.launch_side_effects: list[object] = []
        self.retrieve_calls: list[str] = []
        self.run_calls: list[tuple[str, list[str], dict]] = []
        self.run_side_effects: list[object] = []
        self.delete_calls: list[str] = []
        self.current = _FakeVM()

    def launch(self, **kwargs):
        self.events.append("launch")
        self.launch_calls.append(kwargs)
        if self.launch_side_effects:
            effect = self.launch_side_effects.pop(0)
            if isinstance(effect, Exception):
                raise effect
            if isinstance(effect, _FakeVM):
                self.current = effect
                return effect
        self.current = _FakeVM(id=f"vm-{len(self.launch_calls)}")
        return self.current

    def retrieve(self, vm_id: str):
        self.retrieve_calls.append(vm_id)
        return self.current

    def run(self, vm_id: str, *, command, **kwargs):
        argv = list(command)
        self.run_calls.append((vm_id, argv, kwargs))
        if self.run_side_effects:
            effect = self.run_side_effects.pop(0)
            if isinstance(effect, Exception):
                raise effect
            if callable(effect):
                return effect(vm_id, argv, kwargs)
            return effect
        script = argv[-1] if argv else ""
        if 'printf %s "$HOME"' in script:
            return _FakeExecResult(stdout="/root")
        match = re.search(r"__HERMES_CWD_[A-Za-z0-9]+__", script)
        if match:
            marker = match.group(0)
            return _FakeExecResult(stdout=f"\n{marker}/root{marker}\n")
        return _FakeExecResult(stdout="")

    def delete(self, vm_id: str):
        self.events.append("delete")
        self.delete_calls.append(vm_id)
        return SimpleNamespace(id=vm_id)


class _FakeSnapshots:
    def __init__(self, events: list[str]):
        self.events = events
        self.create_calls: list[dict] = []
        self.create_side_effects: list[object] = []
        self.retrieve_calls: list[str] = []
        self.delete_calls: list[str] = []

    def create(self, **kwargs):
        self.events.append("snapshot.create")
        self.create_calls.append(kwargs)
        if self.create_side_effects:
            effect = self.create_side_effects.pop(0)
            if isinstance(effect, Exception):
                raise effect
            if isinstance(effect, _FakeSnapshot):
                return effect
        return _FakeSnapshot("snap-new")

    def retrieve(self, snapshot_id: str):
        self.retrieve_calls.append(snapshot_id)
        return _FakeSnapshot(snapshot_id, status="ready")

    def delete(self, snapshot_id: str):
        self.delete_calls.append(snapshot_id)
        return SimpleNamespace(id=snapshot_id)


class _FakeClient:
    def __init__(self):
        self.events: list[str] = []
        self.vms = _FakeVms(self.events)
        self.snapshots = _FakeSnapshots(self.events)
        self.upload_calls: list[tuple[str, str, str]] = []
        self.download_calls: list[tuple[str, str, str]] = []
        self.download_bytes = b""

    def upload(self, vm_id: str, local_path: str, remote_path: str):
        self.upload_calls.append((vm_id, local_path, remote_path))

    def download(self, vm_id: str, remote_path: str, local_path: str):
        self.download_calls.append((vm_id, remote_path, local_path))
        Path(local_path).write_bytes(self.download_bytes)


def _tar_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name, content in entries.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


@pytest.fixture()
def fastvm_module(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.setattr("tools.environments.base.is_interrupted", lambda: False)
    monkeypatch.setattr("tools.credential_files.get_credential_file_mounts", lambda: [])
    monkeypatch.setattr("tools.credential_files.iter_skills_files", lambda **kwargs: [])
    monkeypatch.setattr("tools.credential_files.iter_cache_files", lambda **kwargs: [])
    module = importlib.import_module("tools.environments.fastvm")
    return importlib.reload(module)


@pytest.fixture()
def make_env(fastvm_module, request):
    envs = []

    def _cleanup():
        for env in envs:
            env._sync_manager = None
            env._persistent = False
            env.cleanup()

    request.addfinalizer(_cleanup)

    def _factory(client=None, **kwargs):
        client = client or _FakeClient()
        kwargs.setdefault("task_id", "task-123")
        kwargs.setdefault("cwd", fastvm_module.DEFAULT_FASTVM_CWD)
        kwargs.setdefault("_client", client)
        env = fastvm_module.FastVMEnvironment(**kwargs)
        envs.append(env)
        return env, client

    return _factory


def test_restores_from_saved_snapshot(make_env, fastvm_module):
    fastvm_module._store_snapshot_record(
        "task-123",
        {
            "snapshot_id": "snap-saved",
            "created_at": "2026-05-10T00:00:00+00:00",
            "live_resume": True,
        },
    )

    _env, client = make_env()

    assert client.vms.launch_calls[0]["snapshot_id"] == "snap-saved"
    assert "machine_type" not in client.vms.launch_calls[0]


def test_live_resume_restore_failure_does_not_fall_back(make_env, fastvm_module):
    fastvm_module._store_snapshot_record("task-123", {"snapshot_id": "snap-bad"})
    client = _FakeClient()
    client.vms.launch_side_effects.append(RuntimeError("restore failed"))

    with pytest.raises(RuntimeError, match="refusing to fall back"):
        make_env(client=client, live_resume=True)

    assert len(client.vms.launch_calls) == 1


def test_non_live_restore_failure_falls_back_to_fresh_vm(make_env, fastvm_module):
    fastvm_module._store_snapshot_record("task-123", {"snapshot_id": "snap-bad"})
    client = _FakeClient()
    client.vms.launch_side_effects.append(RuntimeError("restore failed"))

    _env, client = make_env(client=client, live_resume=False)

    assert client.vms.launch_calls[0]["snapshot_id"] == "snap-bad"
    assert client.vms.launch_calls[1]["machine_type"] == "c1m2"
    assert fastvm_module._get_snapshot_record("task-123") is None


def test_cleanup_snapshots_before_deleting_vm(make_env, fastvm_module):
    env, client = make_env()

    env.cleanup()

    assert client.events == ["launch", "snapshot.create", "delete"]
    assert client.snapshots.create_calls[0]["vm_id"] == client.vms.delete_calls[0]
    record = fastvm_module._get_snapshot_record("task-123")
    assert record["snapshot_id"] == "snap-new"
    assert record["live_resume"] is True


def test_cleanup_refuses_to_delete_when_snapshot_fails(make_env):
    env, client = make_env()
    client.snapshots.create_side_effects.append(RuntimeError("snapshot failed"))

    with pytest.raises(RuntimeError, match="refused to delete"):
        env.cleanup()

    assert client.vms.delete_calls == []
    assert env._vm is not None


def test_uploads_managed_files_under_remote_home(make_env, monkeypatch, tmp_path):
    src = tmp_path / "token.txt"
    src.write_text("secret-token", encoding="utf-8")
    monkeypatch.setattr(
        "tools.credential_files.get_credential_file_mounts",
        lambda: [
            {
                "host_path": str(src),
                "container_path": "/root/.hermes/credentials/token.txt",
            }
        ],
    )

    _env, client = make_env()

    assert client.upload_calls == [
        ("vm-1", str(src), "/root/.hermes/credentials/token.txt")
    ]


def test_bulk_download_creates_remote_tar_and_downloads(make_env, tmp_path):
    env, client = make_env()
    client.download_bytes = _tar_bytes({"root/.hermes/cache/state.txt": b"cached"})
    dest = tmp_path / "sync.tar"

    env._fastvm_bulk_download(dest)

    assert client.download_calls
    vm_id, remote_path, local_path = client.download_calls[0]
    assert vm_id == "vm-1"
    assert remote_path.startswith("/tmp/.hermes_sync.")
    assert remote_path.endswith(".tar")
    assert local_path == str(dest)
    assert dest.read_bytes() == client.download_bytes
