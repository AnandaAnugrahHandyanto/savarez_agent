"""FastVM execution environment.

Uses the FastVM Python SDK to run Hermes terminal commands in cloud VMs.
Persistent mode snapshots the VM on cleanup, deletes the live VM to stop
compute spend, and restores the task from the latest snapshot on the next use.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import math
import os
import shlex
import threading
import time
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home
from tools.environments.base import (
    BaseEnvironment,
    _ThreadedProcessHandle,
    _load_json_store,
    _save_json_store,
)
from tools.environments.file_sync import (
    FileSyncManager,
    iter_sync_files,
    quoted_mkdir_command,
    quoted_rm_command,
    unique_parent_dirs,
)

logger = logging.getLogger(__name__)

DEFAULT_FASTVM_CWD = "/root"
DEFAULT_FASTVM_MACHINE = "c1m2"
_DEFAULT_DISK_GIB = 50
_SNAPSHOT_STORE_NAME = "fastvm_snapshots.json"
_READY_SNAPSHOT_STATUSES = frozenset({"ready", "completed"})
_ERROR_SNAPSHOT_STATUSES = frozenset({"error", "failed"})
_DEAD_VM_STATUSES = frozenset({"deleted", "deleting", "error", "failed", "stopped"})
_RUNNING_VM_STATUS = "running"
_VM_READY_TIMEOUT = 45
_VM_READY_POLL_INTERVAL = 2.0
_SNAPSHOT_POLL_INTERVAL = 2.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _snapshot_store_path() -> Path:
    return get_hermes_home() / _SNAPSHOT_STORE_NAME


def _load_snapshots() -> dict:
    return _load_json_store(_snapshot_store_path())


def _save_snapshots(data: dict) -> None:
    _save_json_store(_snapshot_store_path(), data)


def _coerce_snapshot_record(value: Any) -> dict[str, Any] | None:
    if isinstance(value, str) and value:
        return {"snapshot_id": value}
    if not isinstance(value, dict):
        return None
    snapshot_id = value.get("snapshot_id")
    if isinstance(snapshot_id, str) and snapshot_id:
        return dict(value)
    return None


def _get_snapshot_record(task_id: str) -> dict[str, Any] | None:
    if not task_id:
        return None
    return _coerce_snapshot_record(_load_snapshots().get(task_id))


def _store_snapshot_record(task_id: str, record: dict[str, Any]) -> None:
    snapshot_id = record.get("snapshot_id")
    if not task_id or not isinstance(snapshot_id, str) or not snapshot_id:
        return
    snapshots = _load_snapshots()
    snapshots[task_id] = record
    _save_snapshots(snapshots)


def _delete_snapshot_record(task_id: str, snapshot_id: str | None = None) -> None:
    if not task_id:
        return
    snapshots = _load_snapshots()
    record = _coerce_snapshot_record(snapshots.get(task_id))
    if record is None:
        return
    existing = record.get("snapshot_id")
    if snapshot_id is not None and existing != snapshot_id:
        return
    snapshots.pop(task_id, None)
    _save_snapshots(snapshots)


def _extract_id(value: Any) -> str | None:
    for attr in ("id", "snapshot_id", "snapshotId", "vm_id", "vmId"):
        candidate = getattr(value, attr, None)
        if isinstance(candidate, str) and candidate:
            return candidate
    if isinstance(value, dict):
        for key in ("id", "snapshot_id", "snapshotId", "vm_id", "vmId"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate:
                return candidate
    return None


def _extract_status(value: Any) -> str:
    status = getattr(value, "status", None)
    if status is None and isinstance(value, dict):
        status = value.get("status")
    return str(status or "").lower()


def _safe_task_label(task_id: str) -> str:
    label = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in task_id)
    return (label or "default")[:24]


class FastVMEnvironment(BaseEnvironment):
    """FastVM cloud VM backend with snapshot-backed sleep/wake."""

    _stdin_mode = "heredoc"
    _snapshot_timeout = 60

    def __init__(
        self,
        machine_type: str = DEFAULT_FASTVM_MACHINE,
        base_snapshot_id: str | None = None,
        cwd: str = DEFAULT_FASTVM_CWD,
        timeout: int = 60,
        disk_gib: int = _DEFAULT_DISK_GIB,
        persistent_filesystem: bool = True,
        live_resume: bool = True,
        task_id: str = "default",
        launch_timeout: int = 300,
        snapshot_timeout: int = 300,
        _client: Any | None = None,
    ):
        requested_cwd = cwd
        super().__init__(cwd=cwd, timeout=timeout)

        self._machine_type = machine_type or DEFAULT_FASTVM_MACHINE
        self._base_snapshot_id = base_snapshot_id or None
        self._disk_gib = max(1, int(disk_gib or _DEFAULT_DISK_GIB))
        self._persistent = persistent_filesystem
        self._live_resume = live_resume
        self._task_id = task_id or "default"
        self._launch_timeout = max(1, int(launch_timeout or 300))
        self._snapshot_timeout_seconds = max(1, int(snapshot_timeout or 300))
        self._requested_cwd = requested_cwd
        self._workspace_root = DEFAULT_FASTVM_CWD
        self._remote_home = DEFAULT_FASTVM_CWD
        self._lock = threading.Lock()
        self._vm: Any | None = None
        self._sync_manager: FileSyncManager | None = None

        if _client is None:
            from fastvm import FastvmClient

            _client = FastvmClient()
        self._client = _client

        self._vm = self._create_vm()
        self._configure_attached_vm(requested_cwd=requested_cwd)
        self._sync_manager.sync(force=True)
        self.init_session()

    def _vm_id(self, vm: Any | None = None) -> str:
        vm = vm or self._vm
        vm_id = _extract_id(vm)
        if not vm_id:
            raise RuntimeError("FastVM VM is not attached")
        return vm_id

    def _launch_metadata(self) -> dict[str, str]:
        return {
            "hermes_backend": "fastvm",
            "hermes_task_id": self._task_id,
            "hermes_live_resume": "true" if self._live_resume else "false",
        }

    def _launch_name(self, *, restore: bool) -> str:
        prefix = "hermes-fastvm-restore" if restore else "hermes-fastvm"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        return f"{prefix}-{_safe_task_label(self._task_id)}-{stamp}"[:64]

    def _create_vm(self) -> Any:
        snapshot_record = _get_snapshot_record(self._task_id) if self._persistent else None
        snapshot_id = snapshot_record.get("snapshot_id") if snapshot_record else None
        if snapshot_id:
            try:
                logger.info(
                    "FastVM: restoring task %s from snapshot %s",
                    self._task_id,
                    snapshot_id,
                )
                return self._client.vms.launch(
                    snapshot_id=snapshot_id,
                    name=self._launch_name(restore=True),
                    metadata=self._launch_metadata(),
                    wait_timeout=self._launch_timeout,
                )
            except Exception as exc:
                if self._live_resume:
                    raise RuntimeError(
                        "FastVM live-resume restore failed for "
                        f"snapshot {snapshot_id}; refusing to fall back to a fresh VM"
                    ) from exc
                logger.warning(
                    "FastVM: failed to restore snapshot %s for task %s; "
                    "falling back to a fresh VM: %s",
                    snapshot_id,
                    self._task_id,
                    exc,
                )
                _delete_snapshot_record(self._task_id, snapshot_id)

        if self._base_snapshot_id:
            logger.info(
                "FastVM: launching task %s from base snapshot %s",
                self._task_id,
                self._base_snapshot_id,
            )
            return self._client.vms.launch(
                snapshot_id=self._base_snapshot_id,
                name=self._launch_name(restore=True),
                metadata=self._launch_metadata(),
                wait_timeout=self._launch_timeout,
            )

        logger.info(
            "FastVM: launching fresh VM for task %s (%s, %d GiB)",
            self._task_id,
            self._machine_type,
            self._disk_gib,
        )
        return self._client.vms.launch(
            machine_type=self._machine_type,
            disk_gi_b=self._disk_gib,
            name=self._launch_name(restore=False),
            metadata=self._launch_metadata(),
            wait_timeout=self._launch_timeout,
        )

    def _wait_for_running(self, vm: Any | None = None) -> Any:
        vm = vm or self._vm
        vm_id = self._vm_id(vm)
        deadline = time.monotonic() + _VM_READY_TIMEOUT
        current = vm
        while True:
            status = _extract_status(current)
            if not status or status == _RUNNING_VM_STATUS:
                return current
            if status in _DEAD_VM_STATUSES:
                raise RuntimeError(f"FastVM VM entered terminal state: {status}")
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"FastVM VM did not reach running state (last status: {status})"
                )
            time.sleep(_VM_READY_POLL_INTERVAL)
            current = self._client.vms.retrieve(vm_id)

    def _detect_remote_home(self) -> str:
        try:
            result = self._client.vms.run(
                self._vm_id(),
                command=["bash", "-lc", 'printf %s "$HOME"'],
                timeout_sec=10,
                timeout=30,
            )
            home = str(getattr(result, "stdout", "") or "").strip()
            if home.startswith("/"):
                return home
        except Exception as exc:
            logger.debug("FastVM: home detection failed for task %s: %s", self._task_id, exc)
        return DEFAULT_FASTVM_CWD

    def _configure_attached_vm(self, *, requested_cwd: str) -> None:
        self._vm = self._wait_for_running(self._vm)
        self._remote_home = self._detect_remote_home()
        self._workspace_root = self._remote_home or DEFAULT_FASTVM_CWD

        container_base = (
            "/.hermes"
            if self._remote_home == "/"
            else f"{self._remote_home.rstrip('/')}/.hermes"
        )
        self._sync_manager = FileSyncManager(
            get_files_fn=lambda: iter_sync_files(container_base),
            upload_fn=self._fastvm_upload,
            delete_fn=self._fastvm_delete,
            bulk_upload_fn=self._fastvm_bulk_upload,
            bulk_download_fn=self._fastvm_bulk_download,
        )

        if requested_cwd == "~":
            self.cwd = self._remote_home
        elif requested_cwd in ("", DEFAULT_FASTVM_CWD):
            self.cwd = self._workspace_root
        else:
            self.cwd = requested_cwd

    def _ensure_vm_ready(self) -> None:
        requested_cwd = self.cwd or self._requested_cwd or DEFAULT_FASTVM_CWD
        if self._vm is None:
            self._vm = self._create_vm()
            self._configure_attached_vm(requested_cwd=requested_cwd)
            return

        try:
            vm = self._client.vms.retrieve(self._vm_id())
        except Exception as exc:
            logger.warning(
                "FastVM: failed to retrieve VM for task %s; recreating from snapshot: %s",
                self._task_id,
                exc,
            )
            self._vm = self._create_vm()
            self._configure_attached_vm(requested_cwd=requested_cwd)
            return

        status = _extract_status(vm)
        if status in _DEAD_VM_STATUSES:
            logger.warning(
                "FastVM: VM entered state %s for task %s; recreating from snapshot",
                status,
                self._task_id,
            )
            self._vm = self._create_vm()
            self._configure_attached_vm(requested_cwd=requested_cwd)
            return

        self._vm = self._wait_for_running(vm)

    def _fastvm_upload(self, host_path: str, remote_path: str) -> None:
        self._fastvm_bulk_upload([(host_path, remote_path)])

    def _fastvm_bulk_upload(self, files: list[tuple[str, str]]) -> None:
        if not files:
            return
        parents = unique_parent_dirs(files)
        if parents:
            result = self._client.vms.run(
                self._vm_id(),
                command=["bash", "-lc", quoted_mkdir_command(parents)],
                timeout_sec=30,
                timeout=60,
            )
            if int(getattr(result, "exit_code", 1)) != 0:
                raise RuntimeError(
                    f"FastVM mkdir failed: {getattr(result, 'stderr', '') or getattr(result, 'stdout', '')}"
                )

        for host_path, remote_path in files:
            self._client.upload(self._vm_id(), host_path, remote_path)

    def _fastvm_delete(self, remote_paths: list[str]) -> None:
        if not remote_paths:
            return
        result = self._client.vms.run(
            self._vm_id(),
            command=["bash", "-lc", quoted_rm_command(remote_paths)],
            timeout_sec=30,
            timeout=60,
        )
        if int(getattr(result, "exit_code", 1)) != 0:
            raise RuntimeError(
                f"FastVM delete failed: {getattr(result, 'stderr', '') or getattr(result, 'stdout', '')}"
            )

    def _fastvm_bulk_download(self, dest_tar_path: Path) -> None:
        remote_hermes = (
            "/.hermes"
            if self._remote_home == "/"
            else f"{self._remote_home.rstrip('/')}/.hermes"
        )
        archive_member = remote_hermes.lstrip("/")
        remote_tar = f"/tmp/.hermes_sync.{os.getpid()}.tar"
        try:
            result = self._client.vms.run(
                self._vm_id(),
                command=[
                    "bash",
                    "-lc",
                    f"tar cf {shlex.quote(remote_tar)} -C / {shlex.quote(archive_member)}",
                ],
                timeout_sec=120,
                timeout=180,
            )
            if int(getattr(result, "exit_code", 1)) != 0:
                raise RuntimeError(
                    f"FastVM bulk download failed: {getattr(result, 'stderr', '') or getattr(result, 'stdout', '')}"
                )
            self._client.download(self._vm_id(), remote_tar, str(dest_tar_path))
        finally:
            try:
                self._client.vms.run(
                    self._vm_id(),
                    command=["bash", "-lc", f"rm -f {shlex.quote(remote_tar)}"],
                    timeout_sec=30,
                    timeout=60,
                )
            except Exception:
                pass

    def _before_execute(self) -> None:
        with self._lock:
            self._ensure_vm_ready()
            if self._sync_manager is not None:
                self._sync_manager.sync()

    def _run_bash(
        self,
        cmd_string: str,
        *,
        login: bool = False,
        timeout: int = 120,
        stdin_data: str | None = None,
    ):
        del stdin_data

        vm_id = self._vm_id()
        lock = self._lock

        def cancel() -> None:
            # FastVM does not currently expose per-exec cancellation. Delete the
            # VM as a last-resort interrupt so runaway foreground commands stop.
            with lock:
                try:
                    self._client.vms.delete(vm_id)
                except Exception:
                    pass
                if self._vm is not None and _extract_id(self._vm) == vm_id:
                    self._vm = None

        def exec_fn() -> tuple[str, int]:
            result = self._client.vms.run(
                vm_id,
                command=["bash", "-lc" if login else "-c", cmd_string],
                timeout_sec=timeout,
                timeout=timeout + 120,
            )
            stdout = str(getattr(result, "stdout", "") or "")
            stderr = str(getattr(result, "stderr", "") or "")
            if stderr and stdout and not stdout.endswith("\n"):
                output = f"{stdout}\n{stderr}"
            else:
                output = stdout + stderr
            exit_code = int(getattr(result, "exit_code", 1))
            if getattr(result, "timed_out", False) and exit_code == 0:
                exit_code = 124
            return output, exit_code

        return _ThreadedProcessHandle(exec_fn, cancel_fn=cancel)

    def _wait_for_snapshot_ready(self, snapshot: Any) -> str | None:
        snapshot_id = _extract_id(snapshot)
        if not snapshot_id:
            return None
        deadline = time.monotonic() + self._snapshot_timeout_seconds
        current = snapshot
        while True:
            status = _extract_status(current)
            if not status or status in _READY_SNAPSHOT_STATUSES:
                return snapshot_id
            if status in _ERROR_SNAPSHOT_STATUSES:
                logger.warning("FastVM: snapshot %s entered state %s", snapshot_id, status)
                return None
            if time.monotonic() >= deadline:
                logger.warning(
                    "FastVM: snapshot %s did not become ready before timeout "
                    "(last status: %s)",
                    snapshot_id,
                    status,
                )
                return None
            time.sleep(_SNAPSHOT_POLL_INTERVAL)
            current = self._client.snapshots.retrieve(snapshot_id)

    def _delete_remote_snapshot(self, snapshot_id: str | None) -> None:
        if not snapshot_id:
            return
        try:
            self._client.snapshots.delete(snapshot_id)
        except Exception as exc:
            logger.debug("FastVM: failed to delete old snapshot %s: %s", snapshot_id, exc)

    def _snapshot_vm(self, vm: Any) -> str | None:
        if not self._persistent or not self._task_id:
            return None
        vm_id = self._vm_id(vm)
        name = (
            f"hermes-{_safe_task_label(self._task_id)}-"
            f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{vm_id[:8]}"
        )[:64]
        try:
            snapshot = self._client.snapshots.create(
                vm_id=vm_id,
                name=name,
                timeout=self._snapshot_timeout_seconds + 30,
            )
        except Exception as exc:
            logger.warning(
                "FastVM: snapshot creation failed for task %s VM %s: %s",
                self._task_id,
                vm_id,
                exc,
            )
            return None

        snapshot_id = self._wait_for_snapshot_ready(snapshot)
        if not snapshot_id:
            return None

        old_record = _get_snapshot_record(self._task_id)
        old_snapshot_id = old_record.get("snapshot_id") if old_record else None
        _store_snapshot_record(
            self._task_id,
            {
                "snapshot_id": snapshot_id,
                "created_at": _utc_now(),
                "source_vm_id": vm_id,
                "machine_type": self._machine_type,
                "base_snapshot_id": self._base_snapshot_id or "",
                "live_resume": self._live_resume,
            },
        )
        if old_snapshot_id and old_snapshot_id != snapshot_id:
            self._delete_remote_snapshot(old_snapshot_id)
        logger.info("FastVM: saved snapshot %s for task %s", snapshot_id, self._task_id)
        return snapshot_id

    def cleanup(self):
        with self._lock:
            vm = self._vm
            sync_manager = self._sync_manager
            if vm is None:
                return

            if sync_manager is not None:
                try:
                    sync_manager.sync_back()
                except Exception as exc:
                    logger.warning(
                        "FastVM: sync_back failed for task %s: %s",
                        self._task_id,
                        exc,
                    )

            snapshot_id = None
            if self._persistent:
                snapshot_id = self._snapshot_vm(vm)
                if not snapshot_id:
                    raise RuntimeError(
                        "FastVM persistent cleanup refused to delete VM "
                        f"{self._vm_id(vm)} because snapshot creation failed"
                    )

            try:
                self._client.vms.delete(self._vm_id(vm))
            except Exception as exc:
                logger.warning(
                    "FastVM: failed to delete VM %s for task %s: %s",
                    self._vm_id(vm),
                    self._task_id,
                    exc,
                )
            finally:
                self._vm = None
                self._sync_manager = None
